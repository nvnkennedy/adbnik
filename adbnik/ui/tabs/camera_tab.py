"""USB / built-in camera: OpenCV preview when available (fast); Qt Multimedia fallback."""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional, Tuple, TYPE_CHECKING

from PyQt5.QtCore import QEventLoop, QSize, Qt, QTimer, QUrl
from PyQt5.QtGui import QDesktopServices, QFont, QIcon, QImage, QPixmap
from PyQt5.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from ..camera_opencv import (
    CameraIndexProbeThread,
    FrameGrabThread,
    OpenCvVideoRecorder,
    list_camera_indices,
    opencv_available,
)
from ..file_dialogs import get_existing_directory

if TYPE_CHECKING:
    from PyQt5.QtMultimedia import QCamera, QCameraImageCapture, QMediaRecorder

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
    QCamera = None  # type: ignore
    _QT_MULTIMEDIA = False


class CameraTab(QWidget):
    """Live preview (OpenCV thread when installed), snapshots, MP4 recording."""

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

        self._opencv_mode = bool(opencv_available())
        self._preview_on = False
        self._cv_thread: Optional[FrameGrabThread] = None
        self._cv_index: Optional[int] = None
        self._last_cv_frame: Optional[QImage] = None
        self._cv_writer: Optional[OpenCvVideoRecorder] = None

        self._camera: Optional["QCamera"] = None
        self._image_capture: Optional["QCameraImageCapture"] = None
        self._recorder: Optional["QMediaRecorder"] = None
        self._recording = False
        self._paused = False
        self._last_record_path: Optional[str] = None
        self._cam_probe: Optional[CameraIndexProbeThread] = None

        self.setAutoFillBackground(True)
        try:
            self.setAttribute(Qt.WA_StyledBackground, True)
        except Exception:
            pass

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        top_strip = QHBoxLayout()
        top_strip.setContentsMargins(12, 10, 12, 6)
        top_strip.setSpacing(12)
        self._status = QLabel("Stopped")
        self._status.setObjectName("CameraStatusLabel")
        stf = QFont("Segoe UI", 11)
        self._status.setFont(stf)
        top_strip.addWidget(self._status)
        top_strip.addStretch()
        dev_lbl = QLabel("Camera")
        dev_lbl.setObjectName("CameraDeviceLabel")
        top_strip.addWidget(dev_lbl)
        self._combo = QComboBox()
        self._combo.setMinimumWidth(280)
        self._combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        top_strip.addWidget(self._combo, 1)
        root.addLayout(top_strip)

        path_strip = QHBoxLayout()
        path_strip.setContentsMargins(12, 0, 12, 8)
        self._path_label = QLabel(self._format_save_label())
        self._path_label.setWordWrap(True)
        self._path_label.setObjectName("CameraPathLabel")
        path_strip.addWidget(self._path_label, 1)
        root.addLayout(path_strip)

        preview_panel = QWidget()
        preview_panel.setObjectName("CameraPreviewPanel")
        pv_layout = QVBoxLayout(preview_panel)
        pv_layout.setContentsMargins(0, 0, 0, 0)
        pv_layout.setSpacing(0)

        if self._opencv_mode:
            self._view = QLabel()
            self._view.setMinimumSize(64, 48)
            self._view.setAlignment(Qt.AlignCenter)
            self._view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            try:
                self._view.setAttribute(Qt.WA_OpaquePaintEvent, True)
            except Exception:
                pass
            pv_layout.addWidget(self._view, 1)
        elif _QT_MULTIMEDIA:
            self._view = QVideoWidget()
            self._view.setMinimumSize(64, 48)
            self._view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            self._view.setAspectRatioMode(Qt.IgnoreAspectRatio)
            pv_layout.addWidget(self._view, 1)
        else:
            self._view = QLabel(
                "Install opencv-python-headless or use a PyQt5 build with Qt Multimedia."
            )
            self._view.setAlignment(Qt.AlignCenter)
            pv_layout.addWidget(self._view, 1)

        root.addWidget(preview_panel, 1)

        st = self.style()
        controls = QFrame()
        controls.setObjectName("CameraControlBar")
        controls.setFrameShape(QFrame.NoFrame)
        ctl_row = QHBoxLayout(controls)
        ctl_row.setContentsMargins(10, 10, 10, 10)
        ctl_row.setSpacing(8)

        def mk_btn(text: str, icon: QIcon, tip: str, slot) -> QPushButton:
            b = QPushButton(text)
            b.setObjectName("CameraChromeBtn")
            b.setIcon(icon)
            b.setIconSize(QSize(20, 20))
            b.setToolTip(tip)
            b.setCursor(Qt.PointingHandCursor)
            b.setAutoDefault(False)
            b.setDefault(False)
            b.clicked.connect(slot)
            b.setMinimumHeight(36)
            b.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
            return b

        self._btn_start = mk_btn(
            "Start preview",
            st.standardIcon(QStyle.SP_MediaPlay),
            "Turn on the camera preview",
            self._on_start,
        )
        self._btn_stop = mk_btn(
            "Stop preview",
            st.standardIcon(QStyle.SP_MediaStop),
            "Turn off the camera preview",
            self._on_stop,
        )
        self._btn_pause = mk_btn(
            "Pause preview",
            st.standardIcon(QStyle.SP_MediaPause),
            "Pause or resume the preview stream",
            self._on_pause,
        )
        self._btn_rec_start = mk_btn(
            "Start video recording",
            st.standardIcon(QStyle.SP_DialogSaveButton),
            "Start recording video (MP4) to the save folder",
            self._on_start_recording,
        )
        self._btn_rec_stop = mk_btn(
            "Stop video recording",
            st.standardIcon(QStyle.SP_MediaStop),
            "Stop recording and finalize the MP4 file",
            self._on_stop_recording,
        )
        self._btn_photo = mk_btn(
            "Take photo",
            st.standardIcon(QStyle.SP_FileDialogContentsView),
            "Save a snapshot (JPEG) to the save folder",
            self._on_photo,
        )
        self._btn_folder = mk_btn(
            "Save folder…",
            st.standardIcon(QStyle.SP_DialogOpenButton),
            "Choose where photos and videos are saved",
            self._pick_folder,
        )
        self._btn_restart = mk_btn(
            "Restart camera",
            st.standardIcon(QStyle.SP_BrowserReload),
            "Stop and restart the selected camera",
            self._on_restart,
        )

        for b in (
            self._btn_start,
            self._btn_stop,
            self._btn_pause,
            self._btn_rec_start,
            self._btn_rec_stop,
            self._btn_photo,
            self._btn_folder,
            self._btn_restart,
        ):
            ctl_row.addWidget(b)
        ctl_row.addStretch()
        root.addWidget(controls, 0)

        self._footer = QLabel(
            "Photos and videos use the save folder above. OpenCV drives preview and recording for smooth capture."
        )
        self._footer.setWordWrap(True)
        self._footer.setObjectName("CameraFooterLabel")
        self._footer.setContentsMargins(12, 4, 12, 8)
        root.addWidget(self._footer, 0)

        if self._opencv_mode:
            self._combo.addItem("(detecting cameras…)", None)
            QTimer.singleShot(0, self._start_opencv_probe)
        else:
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

    def _start_opencv_probe(self) -> None:
        if self._cam_probe is not None and self._cam_probe.isRunning():
            return
        th = CameraIndexProbeThread()
        th.indices_ready.connect(self._on_opencv_indices, Qt.QueuedConnection)
        th.finished.connect(th.deleteLater)
        self._cam_probe = th
        th.start()

    def _make_device_entries(self, ids: List[int]) -> List[Tuple[int, str]]:
        if not ids:
            return []
        ordered = sorted(ids)
        if _QT_MULTIMEDIA:
            infos = QCameraInfo.availableCameras()
            out: List[Tuple[int, str]] = []
            for k, idx in enumerate(ordered):
                if k < len(infos):
                    out.append((idx, infos[k].description()))
                else:
                    out.append((idx, f"Camera ({idx})"))
            return out
        return [(idx, f"Camera ({idx})") for idx in ordered]

    def _on_opencv_indices(self, ids: List[int]) -> None:
        self._combo.blockSignals(True)
        self._combo.clear()
        if not ids:
            self._combo.addItem("(no camera detected)", None)
        else:
            for idx, label in self._make_device_entries(ids):
                self._combo.addItem(label, idx)
        self._combo.blockSignals(False)

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
        if self._opencv_mode:
            ids = list_camera_indices()
            if not ids:
                self._combo.addItem("(no camera detected)", None)
            else:
                for idx, label in self._make_device_entries(ids):
                    self._combo.addItem(label, idx)
            self._combo.blockSignals(False)
            return
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

    def _selected_cv_index(self) -> Optional[int]:
        idx = self._combo.currentIndex()
        data = self._combo.itemData(idx)
        if data is None:
            return None
        try:
            return int(data)
        except (TypeError, ValueError):
            return None

    def _selected_camera_info(self):
        if not _QT_MULTIMEDIA or self._opencv_mode:
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
        if self._preview_on:
            self._on_stop()

    def _offer_open_saved(self, path: Path) -> None:
        if not path.is_file():
            return
        box = QMessageBox(self)
        box.setWindowTitle("Saved")
        box.setIcon(QMessageBox.Information)
        box.setText("File saved.")
        box.setInformativeText(str(path))
        box.setStandardButtons(QMessageBox.Ok)
        open_btn = box.addButton("Open file", QMessageBox.ActionRole)
        box.exec_()
        if box.clickedButton() == open_btn:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.resolve())))

    def _on_image_saved(self, _id: int, file_name: str) -> None:
        p = Path(file_name)
        if p.is_file():
            self._offer_open_saved(p)

    def _sync_wait_recorder_stopped(self, rec: "QMediaRecorder", timeout_s: float = 3.0) -> None:
        if not _QT_MULTIMEDIA:
            return
        deadline = time.monotonic() + timeout_s
        while rec.state() != QMediaRecorder.StoppedState and time.monotonic() < deadline:
            QApplication.processEvents(QEventLoop.AllEvents, 50)
            time.sleep(0.015)

    def _finalize_cv_writer(self, *, offer_open: bool) -> None:
        if self._cv_thread is not None:
            try:
                self._cv_thread.set_emit_bgr_for_record(False)
            except Exception:
                pass
        path: Optional[str] = None
        if self._cv_writer is not None:
            try:
                path = str(self._cv_writer.path)
                self._cv_writer.close()
            except Exception:
                pass
            self._cv_writer = None
        self._recording = False
        self._apply_button_states()
        if path:
            pth = Path(str(path))
            if pth.is_file() and pth.stat().st_size > 0:
                self._append_log(f"Camera: video saved — {pth}")
                if offer_open:
                    self._offer_open_saved(pth)
            elif pth.is_file():
                self._append_log(f"Camera: video file is empty — {pth}")

    def _finalize_recorder_sync(self, *, offer_open: bool) -> None:
        if self._opencv_mode:
            self._finalize_cv_writer(offer_open=offer_open)
            return
        rec = self._recorder
        if rec is None:
            return
        path = self._last_record_path
        try:
            rec.stop()
        except Exception:
            pass
        self._sync_wait_recorder_stopped(rec)
        self._recorder = None
        self._recording = False
        self._last_record_path = None
        self._apply_button_states()
        try:
            rec.deleteLater()
        except Exception:
            pass
        if path:
            pth = Path(path)
            if pth.is_file() and pth.stat().st_size > 0:
                self._append_log(f"Camera: video saved — {pth}")
                if offer_open:
                    self._offer_open_saved(pth)
            elif pth.is_file():
                self._append_log(f"Camera: video file is empty — {pth}")

    def _poll_recording_finished(
        self, rec: "QMediaRecorder", path: Optional[str], offer_open: bool, attempt: int
    ) -> None:
        if not _QT_MULTIMEDIA:
            return
        if self._recorder is not rec:
            return
        stopped = rec.state() == QMediaRecorder.StoppedState
        if stopped or attempt > 120:
            if attempt > 120 and not stopped:
                self._append_log("Camera: recording finalize timed out — file may be incomplete")
            self._recorder = None
            self._recording = False
            self._last_record_path = None
            self._apply_button_states()
            try:
                rec.deleteLater()
            except Exception:
                pass
            if stopped and path:
                pth = Path(path)
                if pth.is_file() and pth.stat().st_size > 0:
                    self._append_log(f"Camera: video saved — {pth}")
                    if offer_open:
                        self._offer_open_saved(pth)
                elif pth.is_file():
                    self._append_log(f"Camera: video file is empty — {pth}")
            return
        QTimer.singleShot(35, lambda: self._poll_recording_finished(rec, path, offer_open, attempt + 1))

    def _stop_recording_safe(self, *, offer_open: bool = True) -> None:
        if self._opencv_mode:
            self._finalize_cv_writer(offer_open=offer_open)
            return
        if self._recorder is None:
            self._recording = False
            self._apply_button_states()
            return
        rec = self._recorder
        path = self._last_record_path
        try:
            rec.stop()
        except Exception:
            pass
        self._poll_recording_finished(rec, path, offer_open, 0)

    def _stop_cv_thread(self) -> None:
        if self._cv_thread is None:
            return
        try:
            self._cv_thread.stop()
            self._cv_thread.wait(4000)
        except Exception:
            pass
        self._cv_thread = None
        self._preview_on = False

    def _start_cv_thread(self, index: int) -> None:
        self._stop_cv_thread()
        self._cv_index = index
        th = FrameGrabThread(index, 1280, 720, 30.0)
        th.frame_ready.connect(self._on_cv_frame)
        th.bgr_ready.connect(self._on_cv_bgr_frame)
        th.failed.connect(self._on_cv_failed)
        th.start()
        self._cv_thread = th
        self._preview_on = True
        self._paused = False
        self._status.setText("Running")
        self._append_log(f"Camera: started (OpenCV · device {index})")

    def _on_cv_bgr_frame(self, bgr: object) -> None:
        w = self._cv_writer
        if w is None or bgr is None:
            return
        try:
            w.write_frame_bgr(bgr)
        except Exception:
            pass

    def _paint_preview_label(self) -> None:
        if not self.isVisible():
            return
        if (
            not self._opencv_mode
            or not isinstance(self._view, QLabel)
            or self._last_cv_frame is None
            or self._last_cv_frame.isNull()
        ):
            return
        pix = QPixmap.fromImage(self._last_cv_frame)
        self._view.setPixmap(
            pix.scaled(self._view.size(), Qt.KeepAspectRatio, Qt.FastTransformation)
        )

    def _on_cv_frame(self, img: object) -> None:
        if not isinstance(img, QImage):
            return
        self._last_cv_frame = img
        if not self._opencv_mode or not isinstance(self._view, QLabel):
            return
        if not self.isVisible():
            return
        self._paint_preview_label()

    def _on_cv_failed(self, msg: str) -> None:
        self._append_log(f"Camera: OpenCV error — {msg}")
        QMessageBox.warning(self, "Camera", msg)
        self._stop_cv_thread()
        self._status.setText("Stopped")
        self._apply_button_states()

    def _clear_preview_surface(self) -> None:
        if self._opencv_mode and isinstance(self._view, QLabel):
            self._view.clear()
        self._last_cv_frame = None

    def pause_for_background(self) -> None:
        self._finalize_recorder_sync(offer_open=False)
        if self._opencv_mode:
            self._stop_cv_thread()
            self._paused = True
            self._status.setText("Paused")
            self._clear_preview_surface()
            self._apply_button_states()
            return
        if self._camera is None:
            return
        try:
            self._camera.stop()
        except Exception:
            pass
        self._paused = True
        self._status.setText("Paused")
        self._clear_preview_surface()
        self._apply_button_states()

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        self._clear_preview_surface()

    def _teardown_camera(self) -> None:
        self._finalize_recorder_sync(offer_open=False)
        self._stop_cv_thread()
        self._last_cv_frame = None
        self._cv_index = None
        if self._image_capture is not None:
            self._image_capture = None
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
        self._preview_on = False

    def _on_start(self) -> None:
        if self._opencv_mode:
            if self._paused and self._cv_index is not None:
                self._start_cv_thread(self._cv_index)
                self._apply_button_states()
                return
            ix = self._selected_cv_index()
            if ix is None:
                QMessageBox.warning(self, "Camera", "Select a camera device first.")
                return
            self._teardown_camera()
            self._start_cv_thread(ix)
            self._apply_button_states()
            return

        if not _QT_MULTIMEDIA:
            QMessageBox.information(self, "Camera", "Qt Multimedia is not available.")
            return
        if self._camera is not None and self._paused:
            try:
                self._camera.start()
                self._paused = False
                self._preview_on = True
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
                    cap_px = 1920

                    def area(s):
                        r = s.resolution()
                        return r.width() * r.height()

                    under = [s for s in opts if s.resolution().width() <= cap_px]
                    pool = under if under else opts
                    best = max(pool, key=area)
                    cam.setViewfinderSettings(best)
                else:
                    vs = QCameraViewfinderSettings()
                    vs.setResolution(QSize(1280, 720))
                    cam.setViewfinderSettings(vs)
            except Exception:
                pass
            cap = QCameraImageCapture(cam)
            try:
                cap.imageSaved.connect(self._on_image_saved)
            except Exception:
                pass
            self._camera = cam
            self._image_capture = cap
            cam.start()
            self._paused = False
            self._preview_on = True
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
        if self._opencv_mode:
            if not self._preview_on:
                return
            self._finalize_recorder_sync(offer_open=False)
            if self._paused:
                if self._cv_index is not None:
                    self._start_cv_thread(self._cv_index)
                self._status.setText("Running")
            else:
                self._stop_cv_thread()
                self._paused = True
                self._status.setText("Paused")
            self._apply_button_states()
            return
        if self._camera is None:
            return
        self._finalize_recorder_sync(offer_open=False)
        try:
            if self._paused:
                self._camera.start()
                self._paused = False
                self._preview_on = True
                self._status.setText("Running")
            else:
                self._camera.stop()
                self._paused = True
                self._preview_on = False
                self._status.setText("Paused")
        except Exception as exc:
            self._append_log(f"Camera: pause failed — {exc}")
        self._apply_button_states()

    def _on_restart(self) -> None:
        self._on_stop()
        self._on_start()

    def _on_photo(self) -> None:
        if self._opencv_mode:
            if self._last_cv_frame is None or self._last_cv_frame.isNull():
                QMessageBox.information(self, "Camera", "Start the camera and wait for a frame.")
                return
            dest_dir = self._ensure_output_dir()
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = dest_dir / f"adbnik_capture_{ts}.jpg"
            try:
                if self._last_cv_frame.save(str(path), "JPEG", quality=92):
                    self._append_log(f"Camera: snapshot → {path}")
                    self._status.setText(f"Saved {path.name}")
                    self._offer_open_saved(path)
                else:
                    QMessageBox.warning(self, "Camera", "Could not save image.")
            except Exception as exc:
                QMessageBox.warning(self, "Camera", str(exc))
            self._apply_button_states()
            return
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

    def _on_start_recording(self) -> None:
        if self._recording:
            return
        if self._opencv_mode:
            if not self._preview_on or self._paused:
                QMessageBox.information(self, "Camera", "Start the camera before recording.")
                return
            if self._last_cv_frame is None or self._last_cv_frame.isNull():
                QMessageBox.information(self, "Camera", "Wait until preview shows a frame.")
                return
            dest_dir = self._ensure_output_dir()
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            out = dest_dir / f"adbnik_video_{ts}.mp4"
            try:
                w, h = self._last_cv_frame.width(), self._last_cv_frame.height()
                self._cv_writer = OpenCvVideoRecorder(out, (w, h), 30.0)
                self._recording = True
                if self._cv_thread is not None:
                    self._cv_thread.set_emit_bgr_for_record(True)
                self._append_log(f"Camera: recording (OpenCV) → {out}")
                self._status.setText("Recording…")
            except Exception as exc:
                self._append_log(f"Camera: record failed — {exc}")
                QMessageBox.warning(self, "Recording unavailable", str(exc))
            self._apply_button_states()
            return

        if not _QT_MULTIMEDIA:
            return
        if self._camera is None:
            QMessageBox.information(self, "Camera", "Start the camera before recording.")
            return
        if self._paused:
            QMessageBox.information(self, "Camera", "Resume preview (Start) before recording.")
            return
        dest_dir = self._ensure_output_dir()
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out = dest_dir / f"adbnik_video_{ts}.mp4"
        try:
            rec = QMediaRecorder(self._camera)
            rec.setOutputLocation(QUrl.fromLocalFile(str(out.resolve())))
            rec.record()
            self._recorder = rec
            self._recording = True
            self._last_record_path = str(out.resolve())
            self._append_log(f"Camera: recording → {out}")
            self._status.setText("Recording…")
        except Exception as exc:
            self._append_log(f"Camera: record failed — {exc}")
            QMessageBox.warning(
                self,
                "Recording unavailable",
                f"{exc}\n\nTry another camera driver or install OS codecs.",
            )
        self._apply_button_states()

    def _on_stop_recording(self) -> None:
        if not self._recording:
            return
        if self._opencv_mode:
            self._append_log("Camera: stopping recording…")
            self._finalize_cv_writer(offer_open=True)
            self._status.setText("Running")
            self._apply_button_states()
            return
        self._append_log("Camera: stopping recording…")
        self._stop_recording_safe()
        self._status.setText("Running" if self._camera and not self._paused else "Paused")
        self._apply_button_states()

    def _apply_button_states(self) -> None:
        running = self._preview_on and not self._paused
        paused = self._paused and (self._cv_index is not None or self._camera is not None)
        active = self._preview_on or self._camera is not None or self._cv_index is not None
        self._btn_start.setEnabled(not self._preview_on or self._paused)
        self._btn_stop.setEnabled(active)
        self._btn_pause.setEnabled(active)
        self._btn_restart.setEnabled(True)
        self._btn_photo.setEnabled(running or paused)
        self._btn_rec_start.setEnabled(running and not self._recording)
        self._btn_rec_stop.setEnabled(self._recording)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._paint_preview_label()

    def shutdown(self, *, fast: bool = False) -> None:
        try:
            self._on_stop()
        except Exception:
            pass
