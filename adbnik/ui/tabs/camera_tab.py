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
    QButtonGroup,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStyle,
    QToolButton,
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


class _PreviewStack(QWidget):
    """Full-area preview with an interactive overlay stacked above it (Windows Camera–style)."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._preview: Optional[QWidget] = None
        self._overlay: Optional[QWidget] = None

    def set_preview(self, widget: QWidget) -> None:
        self._preview = widget
        widget.setParent(self)

    def set_overlay(self, widget: QWidget) -> None:
        self._overlay = widget
        widget.setParent(self)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        r = self.rect()
        if self._preview is not None:
            self._preview.setGeometry(r)
        if self._overlay is not None:
            self._overlay.setGeometry(r)
            self._overlay.raise_()


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
        self._photo_mode = True
        self._last_thumb_path: Optional[Path] = None

        self.setAutoFillBackground(True)
        try:
            self.setAttribute(Qt.WA_StyledBackground, True)
        except Exception:
            pass

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        chrome = QWidget()
        chrome.setObjectName("CameraChromeStrip")
        chrome_lay = QHBoxLayout(chrome)
        chrome_lay.setContentsMargins(8, 5, 8, 4)
        chrome_lay.setSpacing(8)
        self._status = QLabel("Stopped · select a camera in ⚙ or rotate ▸")
        self._status.setObjectName("CameraStatusLabel")
        self._status.setFont(QFont("Segoe UI", 10))
        chrome_lay.addWidget(self._status, 1)

        self._combo = QComboBox()
        self._combo.setMinimumWidth(200)
        self._combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._combo.hide()

        root.addWidget(chrome, 0)

        preview_panel = QWidget()
        preview_panel.setObjectName("CameraPreviewPanel")
        pv_outer = QVBoxLayout(preview_panel)
        pv_outer.setContentsMargins(0, 0, 0, 0)
        pv_outer.setSpacing(0)

        self._stack = _PreviewStack()

        if self._opencv_mode:
            self._view = QLabel()
            self._view.setMinimumSize(64, 48)
            self._view.setAlignment(Qt.AlignCenter)
            self._view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            try:
                self._view.setAttribute(Qt.WA_OpaquePaintEvent, True)
            except Exception:
                pass
        elif _QT_MULTIMEDIA:
            self._view = QVideoWidget()
            self._view.setMinimumSize(64, 48)
            self._view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            self._view.setAspectRatioMode(Qt.IgnoreAspectRatio)
        else:
            self._view = QLabel(
                "Install opencv-python-headless or use a PyQt5 build with Qt Multimedia."
            )
            self._view.setAlignment(Qt.AlignCenter)

        self._stack.set_preview(self._view)

        overlay = QWidget()
        overlay.setObjectName("CameraOverlayHost")
        ov = QHBoxLayout(overlay)
        ov.setContentsMargins(0, 0, 0, 0)
        ov.setSpacing(0)

        left_rail = QWidget()
        left_rail.setObjectName("CameraOverlayRailLeft")
        lv = QVBoxLayout(left_rail)
        lv.setContentsMargins(8, 12, 8, 12)
        lv.setSpacing(10)

        st = self.style()
        self._btn_gear = QToolButton()
        self._btn_gear.setObjectName("CameraOverlayToolBtn")
        self._btn_gear.setText("⚙")
        self._btn_gear.setToolTip("Menu · save folder, start/stop, pause")
        self._btn_gear.setCursor(Qt.PointingHandCursor)
        self._btn_gear.setPopupMode(QToolButton.InstantPopup)
        self._gear_menu = QMenu(self)
        self._build_gear_menu()
        self._btn_gear.setMenu(self._gear_menu)

        self._btn_pause = QToolButton()
        self._btn_pause.setObjectName("CameraOverlayToolBtn")
        self._btn_pause.setIcon(st.standardIcon(QStyle.SP_MediaPause))
        self._btn_pause.setIconSize(QSize(22, 22))
        self._btn_pause.setToolTip("Pause or resume preview")
        self._btn_pause.setCursor(Qt.PointingHandCursor)
        self._btn_pause.clicked.connect(self._on_pause)

        lv.addWidget(self._btn_gear)
        lv.addWidget(self._btn_pause)
        lv.addStretch()
        for text in ("WB · auto", "Focus · auto", "ISO · auto"):
            lab = QLabel(text)
            lab.setObjectName("CameraOverlayHint")
            lab.setAlignment(Qt.AlignHCenter)
            lv.addWidget(lab)

        right_rail = QWidget()
        right_rail.setObjectName("CameraOverlayRailRight")
        rv = QVBoxLayout(right_rail)
        rv.setContentsMargins(8, 12, 8, 12)
        rv.setSpacing(12)

        self._btn_switch = QToolButton()
        self._btn_switch.setObjectName("CameraOverlayToolBtn")
        self._btn_switch.setIcon(st.standardIcon(QStyle.SP_BrowserReload))
        self._btn_switch.setIconSize(QSize(24, 24))
        self._btn_switch.setToolTip("Switch camera (next device)")
        self._btn_switch.setCursor(Qt.PointingHandCursor)
        self._btn_switch.clicked.connect(self._on_rotate_camera)

        mode_row = QWidget()
        mr = QHBoxLayout(mode_row)
        mr.setContentsMargins(0, 0, 0, 0)
        mr.setSpacing(6)
        self._btn_mode_photo = QToolButton()
        self._btn_mode_photo.setObjectName("CameraModeBtn")
        self._btn_mode_photo.setCheckable(True)
        self._btn_mode_photo.setChecked(True)
        self._btn_mode_photo.setIcon(st.standardIcon(QStyle.SP_FileDialogContentsView))
        self._btn_mode_photo.setToolTip("Photo mode")
        self._btn_mode_photo.setCursor(Qt.PointingHandCursor)
        self._btn_mode_video = QToolButton()
        self._btn_mode_video.setObjectName("CameraModeBtn")
        self._btn_mode_video.setCheckable(True)
        self._btn_mode_video.setIcon(st.standardIcon(QStyle.SP_MediaPlay))
        self._btn_mode_video.setToolTip("Video mode")
        self._btn_mode_video.setCursor(Qt.PointingHandCursor)
        self._mode_group = QButtonGroup(self)
        self._mode_group.setExclusive(True)
        self._mode_group.addButton(self._btn_mode_photo, 0)
        self._mode_group.addButton(self._btn_mode_video, 1)
        self._btn_mode_photo.clicked.connect(lambda: self._set_photo_mode(True))
        self._btn_mode_video.clicked.connect(lambda: self._set_photo_mode(False))
        mr.addWidget(self._btn_mode_photo)
        mr.addWidget(self._btn_mode_video)

        self._btn_shutter = QPushButton()
        self._btn_shutter.setObjectName("CameraShutterBtn")
        self._btn_shutter.setIcon(st.standardIcon(QStyle.SP_DialogYesButton))
        self._btn_shutter.setIconSize(QSize(36, 36))
        self._btn_shutter.setMinimumSize(76, 76)
        self._btn_shutter.setCursor(Qt.PointingHandCursor)
        self._btn_shutter.clicked.connect(self._on_shutter_primary)

        self._gallery_thumb = QToolButton()
        self._gallery_thumb.setObjectName("CameraGalleryThumb")
        self._gallery_thumb.setFixedSize(72, 72)
        self._gallery_thumb.setToolTip("Open last saved photo")
        self._gallery_thumb.setCursor(Qt.PointingHandCursor)
        self._gallery_thumb.clicked.connect(self._on_gallery_click)

        rv.addWidget(self._btn_switch, 0, Qt.AlignHCenter)
        rv.addWidget(mode_row, 0, Qt.AlignHCenter)
        rv.addStretch()
        rv.addWidget(self._btn_shutter, 0, Qt.AlignHCenter)
        rv.addWidget(self._gallery_thumb, 0, Qt.AlignHCenter)

        ov.addWidget(left_rail, 0)
        ov.addStretch(1)
        ov.addWidget(right_rail, 0)

        self._stack.set_overlay(overlay)
        pv_outer.addWidget(self._stack, 1)
        root.addWidget(preview_panel, 1)

        if self._opencv_mode:
            self._combo.addItem("(detecting cameras…)", None)
            QTimer.singleShot(0, self._start_opencv_probe)
        else:
            self._refresh_devices()
        self._combo.currentIndexChanged.connect(self._on_device_changed)
        self._apply_button_states()
        self._sync_shutter_look()

    def _build_gear_menu(self) -> None:
        m = self._gear_menu
        m.clear()
        a_start = m.addAction("Start preview")
        a_start.triggered.connect(self._on_start)
        a_stop = m.addAction("Stop preview")
        a_stop.triggered.connect(self._on_stop)
        m.addSeparator()
        a_folder = m.addAction("Save folder…")
        a_folder.triggered.connect(self._pick_folder)
        a_restart = m.addAction("Restart camera")
        a_restart.triggered.connect(self._on_restart)

    def _set_photo_mode(self, photo: bool) -> None:
        self._photo_mode = photo
        self._btn_mode_photo.setChecked(photo)
        self._btn_mode_video.setChecked(not photo)
        self._sync_shutter_look()

    def _sync_shutter_look(self) -> None:
        st = self.style()
        if self._recording:
            self._btn_shutter.setIcon(st.standardIcon(QStyle.SP_MediaStop))
            self._btn_shutter.setToolTip("Stop recording")
            self._btn_shutter.setProperty("state", "record_stop")
        elif self._photo_mode:
            self._btn_shutter.setIcon(st.standardIcon(QStyle.SP_DialogYesButton))
            self._btn_shutter.setToolTip("Photo · capture (starts preview if needed)")
            self._btn_shutter.setProperty("state", "photo")
        else:
            self._btn_shutter.setIcon(st.standardIcon(QStyle.SP_MediaPlay))
            self._btn_shutter.setToolTip("Video · start recording (starts preview if needed)")
            self._btn_shutter.setProperty("state", "video")
        self._btn_shutter.style().unpolish(self._btn_shutter)
        self._btn_shutter.style().polish(self._btn_shutter)

    def _on_shutter_primary(self) -> None:
        if not self._preview_on or self._paused:
            if not self._has_valid_device():
                QMessageBox.warning(self, "Camera", "No camera available.")
                return
            self._on_start()
            return
        if self._photo_mode:
            self._on_photo()
            return
        if self._recording:
            self._on_stop_recording()
        else:
            self._on_start_recording()

    def _has_valid_device(self) -> bool:
        if self._opencv_mode:
            return self._selected_cv_index() is not None
        if _QT_MULTIMEDIA:
            return self._selected_camera_info() is not None
        return False

    def _valid_camera_count(self) -> int:
        n = 0
        for i in range(self._combo.count()):
            if self._combo.itemData(i) is not None:
                n += 1
        return n

    def _on_rotate_camera(self) -> None:
        n = self._combo.count()
        if n < 2:
            return
        start = self._combo.currentIndex()
        for step in range(1, n + 1):
            j = (start + step) % n
            if self._combo.itemData(j) is not None:
                self._combo.setCurrentIndex(j)
                self._status.setText(f"Switched · {self._combo.currentText()}")
                return

    def _on_gallery_click(self) -> None:
        p = self._last_thumb_path
        if p is not None and p.is_file():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(p.resolve())))

    def _update_gallery_thumb(self, path: Path) -> None:
        if not path.is_file():
            return
        suf = path.suffix.lower()
        if suf not in (".jpg", ".jpeg", ".png", ".webp", ".bmp"):
            return
        pix = QPixmap(str(path))
        if pix.isNull():
            return
        self._gallery_thumb.setIcon(QIcon(pix.scaled(68, 68, Qt.KeepAspectRatio, Qt.SmoothTransformation)))
        self._last_thumb_path = path.resolve()

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
        self._apply_button_states()

    def _pick_folder(self) -> None:
        start = (self._get_output_dir() or "").strip() or str(Path.home() / "Pictures")
        d = get_existing_directory(self, "Photos & videos save folder", start)
        if not d:
            return
        self._set_output_dir(d)
        self._append_log(f"Camera: save folder → {d}")
        self._status.setText(self._format_save_label())

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
        self._update_gallery_thumb(path)
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
        self._sync_shutter_look()
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
        self._sync_shutter_look()
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
            self._sync_shutter_look()
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
            self._sync_shutter_look()
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
        th = FrameGrabThread(index, 960, 540, 30.0)
        th.frame_ready.connect(self._on_cv_frame)
        th.bgr_ready.connect(self._on_cv_bgr_frame)
        th.failed.connect(self._on_cv_failed)
        th.start()
        self._cv_thread = th
        self._preview_on = True
        self._paused = False
        label = self._combo.currentText() if self._combo.currentIndex() >= 0 else str(index)
        self._status.setText(f"Running · {label}")
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
                    cap_px = 1280

                    def area(s):
                        r = s.resolution()
                        return r.width() * r.height()

                    under = [s for s in opts if s.resolution().width() <= cap_px]
                    pool = under if under else opts
                    best = max(pool, key=area)
                    cam.setViewfinderSettings(best)
                else:
                    vs = QCameraViewfinderSettings()
                    vs.setResolution(QSize(960, 540))
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
            self._status.setText(f"Running · {info.description()}")
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
            self._sync_shutter_look()
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
        self._sync_shutter_look()
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
        active = self._preview_on or self._camera is not None or self._cv_index is not None
        n_valid = self._valid_camera_count()
        self._btn_switch.setEnabled(n_valid >= 2)
        self._btn_pause.setEnabled(active)
        self._gear_menu.setEnabled(True)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._paint_preview_label()

    def shutdown(self, *, fast: bool = False) -> None:
        try:
            self._on_stop()
        except Exception:
            pass
