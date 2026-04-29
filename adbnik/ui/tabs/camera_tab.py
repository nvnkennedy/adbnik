"""USB / built-in camera preview, photo capture, and optional video recording (Qt Multimedia)."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from PyQt5.QtCore import QSize, Qt, QUrl
from PyQt5.QtGui import QFont, QIcon
from PyQt5.QtWidgets import (
    QComboBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from ..file_dialogs import get_existing_directory

try:
    from PyQt5.QtMultimedia import (
        QCamera,
        QCameraImageCapture,
        QCameraInfo,
        QMediaRecorder,
    )
    from PyQt5.QtMultimediaWidgets import QVideoWidget

    _QT_MULTIMEDIA = True
except Exception:
    _QT_MULTIMEDIA = False


class CameraTab(QWidget):
    """Live preview, snapshots, and MP4 recording on a worker-friendly path (separate from UI thread)."""

    def __init__(
        self,
        append_log: Callable[[str], None],
        *,
        get_output_dir: Callable[[], str],
        set_output_dir: Callable[[str], None],
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.setObjectName("CameraTabRoot")
        self._append_log = append_log
        self._get_output_dir = get_output_dir
        self._set_output_dir = set_output_dir

        self._camera: Optional["QCamera"] = None
        self._image_capture: Optional["QCameraImageCapture"] = None
        self._recorder: Optional["QMediaRecorder"] = None
        self._recording = False
        self._paused = False

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        title_row = QHBoxLayout()
        title = QLabel("Camera")
        title.setObjectName("CameraTitleLabel")
        f = QFont("Segoe UI", 14)
        f.setWeight(QFont.DemiBold)
        title.setFont(f)
        title_row.addWidget(title)
        title_row.addStretch()
        self._status = QLabel("Stopped")
        self._status.setObjectName("CameraStatusLabel")
        title_row.addWidget(self._status)
        root.addLayout(title_row)

        top = QHBoxLayout()
        self._combo = QComboBox()
        self._combo.setMinimumWidth(260)
        self._combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        top.addWidget(QLabel("Device:"), 0)
        top.addWidget(self._combo, 1)
        root.addLayout(top)

        st = self.style()
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        def mk_btn(text: str, icon: QIcon, tip: str, slot) -> QPushButton:
            b = QPushButton(text)
            b.setObjectName("CameraChromeBtn")
            b.setIcon(icon)
            b.setIconSize(QSize(18, 18))
            b.setToolTip(tip)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(slot)
            b.setMinimumHeight(40)
            b.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
            return b

        self._btn_start = mk_btn(
            "Start", st.standardIcon(QStyle.SP_MediaPlay), "Start camera preview", self._on_start
        )
        self._btn_stop = mk_btn(
            "Stop", st.standardIcon(QStyle.SP_MediaStop), "Stop camera", self._on_stop
        )
        self._btn_pause = mk_btn(
            "Pause", st.standardIcon(QStyle.SP_MediaPause), "Pause preview", self._on_pause
        )
        self._btn_restart = mk_btn(
            "Restart",
            st.standardIcon(QStyle.SP_BrowserReload),
            "Stop and start the selected camera",
            self._on_restart,
        )
        self._btn_folder = mk_btn(
            "Save folder",
            st.standardIcon(QStyle.SP_DialogOpenButton),
            "Choose folder for photos and videos",
            self._pick_folder,
        )
        self._btn_photo = mk_btn(
            "Photo",
            st.standardIcon(QStyle.SP_DialogSaveButton),
            "Save a snapshot (JPEG)",
            self._on_photo,
        )
        self._btn_record = mk_btn(
            "Record",
            st.standardIcon(QStyle.SP_MediaPlay),
            "Toggle MP4 recording",
            self._on_toggle_record,
        )
        self._btn_record.setCheckable(True)

        for b in (
            self._btn_start,
            self._btn_stop,
            self._btn_pause,
            self._btn_restart,
            self._btn_folder,
            self._btn_photo,
            self._btn_record,
        ):
            btn_row.addWidget(b)
        btn_row.addStretch()
        root.addLayout(btn_row)

        self._path_label = QLabel(self._format_save_label())
        self._path_label.setWordWrap(True)
        self._path_label.setObjectName("CameraPathLabel")
        root.addWidget(self._path_label)

        video_box = QGroupBox("Preview")
        video_box.setObjectName("CameraPreviewGroup")
        vb = QVBoxLayout(video_box)
        vb.setContentsMargins(6, 12, 6, 6)

        if _QT_MULTIMEDIA:
            self._view = QVideoWidget()
            self._view.setMinimumSize(480, 270)
            self._view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            # Fill the tab; pair with highest viewfinder resolution on Start to limit softness.
            self._view.setAspectRatioMode(Qt.IgnoreAspectRatio)
            self._view.setStyleSheet("background-color:#0f172a;border-radius:10px;")
            vb.addWidget(self._view, 1)
        else:
            self._view = QLabel(
                "Qt Multimedia is not available in this build.\n"
                "Install PyQt5 with multimedia extras or update video drivers."
            )
            self._view.setAlignment(Qt.AlignCenter)
            vb.addWidget(self._view, 1)

        root.addWidget(video_box, 10)

        self._footer = QLabel(
            "Photos/videos save to the folder above. Recording stops automatically when you pause or leave this tab."
        )
        self._footer.setWordWrap(True)
        self._footer.setObjectName("CameraFooterLabel")
        self._footer.setMaximumHeight(52)
        root.addWidget(self._footer, 0)

        self._refresh_devices()
        self._combo.currentIndexChanged.connect(self._on_device_changed)
        self._apply_button_states()

    def _format_save_label(self) -> str:
        p = (self._get_output_dir() or "").strip()
        if not p:
            p = str(Path.home() / "Pictures" / "adbnik_camera")
        return f"Save folder: {p}"

    def _ensure_output_dir(self) -> Path:
        raw = (self._get_output_dir() or "").strip()
        base = Path(raw) if raw else Path.home() / "Pictures" / "adbnik_camera"
        try:
            base.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        return base

    def _pick_folder(self) -> None:
        start = (self._get_output_dir() or "").strip() or str(Path.home() / "Pictures")
        d = get_existing_directory(self, "Photos & videos save folder", start)
        if not d:
            return
        self._set_output_dir(d)
        self._path_label.setText(self._format_save_label())
        self._append_log(f"Camera: save folder → {d}")

    def _refresh_devices(self) -> None:
        self._combo.blockSignals(True)
        self._combo.clear()
        if not _QT_MULTIMEDIA:
            self._combo.addItem("(no multimedia backend)", None)
            self._combo.blockSignals(False)
            return
        cams = QCameraInfo.availableCameras()
        if not cams:
            self._combo.addItem("(no camera detected)", None)
        else:
            for info in cams:
                self._combo.addItem(info.description(), info.deviceName())
        self._combo.blockSignals(False)

    def _selected_camera_info(self):
        if not _QT_MULTIMEDIA:
            return None
        idx = self._combo.currentIndex()
        name = self._combo.itemData(idx)
        if not name:
            return None
        for info in QCameraInfo.availableCameras():
            if info.deviceName() == name:
                return info
        return None

    def _on_device_changed(self, _i: int) -> None:
        if self._camera is not None:
            self._on_stop()

    def _stop_recording_safe(self) -> None:
        """Stop MP4 capture without leaving the UI checked 'recording'."""
        if self._recorder is None:
            self._recording = False
            try:
                self._btn_record.blockSignals(True)
                self._btn_record.setChecked(False)
                self._btn_record.blockSignals(False)
            except Exception:
                pass
            return
        try:
            self._recorder.stop()
        except Exception:
            pass
        self._recorder = None
        self._recording = False
        try:
            self._btn_record.blockSignals(True)
            self._btn_record.setChecked(False)
            self._btn_record.blockSignals(False)
        except Exception:
            pass

    def pause_for_background(self) -> None:
        """Pause preview when leaving the Camera tab — fast return without full teardown."""
        self._stop_recording_safe()
        if self._camera is None:
            return
        try:
            self._camera.stop()
        except Exception:
            pass
        self._paused = True
        self._status.setText("Paused")
        self._apply_button_states()

    def _teardown_camera(self) -> None:
        self._stop_recording_safe()
        if self._image_capture is not None:
            try:
                self._image_capture = None
            except Exception:
                pass
        if self._camera is not None:
            try:
                self._camera.stop()
            except Exception:
                pass
            try:
                self._camera.unload()
            except Exception:
                pass
            self._camera = None
        self._image_capture = None
        self._paused = False

    def _on_start(self) -> None:
        if not _QT_MULTIMEDIA:
            QMessageBox.information(self, "Camera", "Qt Multimedia is not available.")
            return
        # Resume after tab-background pause (same device object — avoids slow recreate).
        if self._camera is not None and self._paused:
            try:
                self._camera.start()
                self._paused = False
                self._status.setText("Running")
                self._append_log("Camera: resumed")
                self._apply_button_states()
                return
            except Exception as exc:
                self._append_log(f"Camera: resume failed — {exc}")
                self._teardown_camera()

        info = self._selected_camera_info()
        if info is None:
            QMessageBox.warning(self, "Camera", "Select a camera device first.")
            return
        self._teardown_camera()
        try:
            cam = QCamera(info)
            cam.setViewfinder(self._view)
            try:
                from PyQt5.QtMultimedia import QCameraViewfinderSettings

                opts = cam.supportedViewfinderSettings()
                if opts:
                    best = max(
                        opts,
                        key=lambda s: s.resolution().width() * s.resolution().height(),
                    )
                    cam.setViewfinderSettings(best)
                else:
                    vs = QCameraViewfinderSettings()
                    vs.setResolution(QSize(1280, 720))
                    cam.setViewfinderSettings(vs)
            except Exception:
                pass
            cap = QCameraImageCapture(cam)
            self._camera = cam
            self._image_capture = cap
            cam.start()
            self._paused = False
            self._status.setText("Running")
            self._append_log(f"Camera: started ({info.description()})")
        except Exception as exc:
            self._append_log(f"Camera: start failed — {exc}")
            QMessageBox.warning(self, "Camera", str(exc))
            self._teardown_camera()
        self._apply_button_states()

    def _on_stop(self) -> None:
        self._teardown_camera()
        self._status.setText("Stopped")
        self._append_log("Camera: stopped")
        self._apply_button_states()

    def _on_pause(self) -> None:
        if self._camera is None:
            return
        self._stop_recording_safe()
        try:
            if self._paused:
                self._camera.start()
                self._paused = False
                self._status.setText("Running")
            else:
                self._camera.stop()
                self._paused = True
                self._status.setText("Paused")
        except Exception as exc:
            self._append_log(f"Camera: pause failed — {exc}")
        self._apply_button_states()

    def _on_restart(self) -> None:
        self._on_stop()
        self._on_start()

    def _on_photo(self) -> None:
        if self._image_capture is None or self._camera is None:
            QMessageBox.information(self, "Camera", "Start the camera first.")
            return
        dest_dir = self._ensure_output_dir()
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = dest_dir / f"adbnik_capture_{ts}.jpg"
        try:
            self._image_capture.capture(str(path))
            self._append_log(f"Camera: snapshot → {path}")
            self._status.setText(f"Saved {path.name}")
        except Exception as exc:
            QMessageBox.warning(self, "Camera", str(exc))

    def _on_toggle_record(self) -> None:
        if not _QT_MULTIMEDIA:
            return
        want = self._btn_record.isChecked()
        if self._camera is None:
            self._btn_record.setChecked(False)
            QMessageBox.information(self, "Camera", "Start the camera before recording.")
            return
        if self._paused:
            self._btn_record.setChecked(False)
            QMessageBox.information(self, "Camera", "Resume preview (Start) before recording.")
            return
        if want:
            dest_dir = self._ensure_output_dir()
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            out = dest_dir / f"adbnik_video_{ts}.mp4"
            try:
                rec = QMediaRecorder(self._camera)
                rec.setOutputLocation(QUrl.fromLocalFile(str(out.resolve())))
                rec.record()
                self._recorder = rec
                self._recording = True
                self._append_log(f"Camera: recording → {out}")
                self._status.setText("Recording…")
            except Exception as exc:
                self._btn_record.setChecked(False)
                self._append_log(f"Camera: record failed — {exc}")
                QMessageBox.warning(
                    self,
                    "Recording unavailable",
                    f"{exc}\n\nTry another camera driver or install OS codecs.",
                )
        else:
            self._stop_recording_safe()
            self._append_log("Camera: recording stopped")
            self._status.setText("Running" if self._camera and not self._paused else "Paused")
        self._apply_button_states()

    def _apply_button_states(self) -> None:
        running = self._camera is not None and not self._paused
        paused = self._camera is not None and self._paused
        self._btn_start.setEnabled(self._camera is None or paused)
        self._btn_stop.setEnabled(self._camera is not None)
        self._btn_pause.setEnabled(self._camera is not None)
        self._btn_restart.setEnabled(True)
        self._btn_photo.setEnabled(running or paused)
        self._btn_record.setEnabled(running)

    def shutdown(self, *, fast: bool = False) -> None:
        """Stop camera when the app exits (does not destroy the tab widget)."""
        try:
            self._on_stop()
        except Exception:
            pass
