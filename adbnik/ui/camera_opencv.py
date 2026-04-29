"""Optional OpenCV capture — faster preview and recording than Qt Multimedia on many Windows setups."""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import List, Optional, Tuple

from PyQt5.QtCore import QObject, QThread, pyqtSignal
from PyQt5.QtGui import QImage

try:
    import cv2
    import numpy as np

    _HAS_CV2 = True
except Exception:
    cv2 = None  # type: ignore
    np = None  # type: ignore
    _HAS_CV2 = False


def opencv_available() -> bool:
    return bool(_HAS_CV2)


def _windows_capture_apis():
    """Prefer MSMF (often lower latency); fall back to DirectShow then default."""
    if sys.platform != "win32":
        return (cv2.CAP_ANY,)
    apis = []
    if hasattr(cv2, "CAP_MSMF"):
        apis.append(cv2.CAP_MSMF)
    apis.append(cv2.CAP_DSHOW)
    apis.append(cv2.CAP_ANY)
    return tuple(apis)


def list_camera_indices(max_probe: int = 6) -> List[int]:
    """Return indices where ``VideoCapture(i)`` opens (best-effort)."""
    if not _HAS_CV2:
        return []
    found: List[int] = []
    apis = _windows_capture_apis()
    for i in range(max_probe):
        opened = False
        for api in apis:
            cap = cv2.VideoCapture(i, api)
            try:
                if cap.isOpened():
                    found.append(i)
                    opened = True
                    break
            finally:
                cap.release()
        if not opened:
            continue
    return found


def _fourcc_mp4() -> int:
    assert cv2 is not None
    return cv2.VideoWriter_fourcc(*"mp4v")


class FrameGrabThread(QThread):
    """Reads frames off the UI thread; emits RGB ``QImage`` copies."""

    frame_ready = pyqtSignal(object)  # QImage
    bgr_ready = pyqtSignal(object)  # numpy BGR (scaled, same size as preview) for recording
    failed = pyqtSignal(str)

    def __init__(self, index: int, width: int, height: int, fps: float, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._index = index
        self._width = max(160, min(width, 1920))
        self._height = max(120, min(height, 1080))
        self._fps = max(8.0, min(fps, 60.0))
        self._running = False
        self._emit_bgr_for_record = False

    def set_emit_bgr_for_record(self, enabled: bool) -> None:
        """When True, emit ``bgr_ready`` with scaled BGR frames (for MP4; avoids RGB→BGR round-trip)."""
        self._emit_bgr_for_record = bool(enabled)

    def stop(self) -> None:
        self._running = False

    def run(self) -> None:
        if not _HAS_CV2:
            self.failed.emit("OpenCV is not available.")
            return
        cap = None
        for api in _windows_capture_apis():
            c = cv2.VideoCapture(self._index, api)
            if c.isOpened():
                cap = c
                break
            c.release()
        if cap is None:
            self.failed.emit(f"Cannot open camera index {self._index}.")
            return
        try:
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, float(self._width))
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, float(self._height))
            cap.set(cv2.CAP_PROP_FPS, self._fps)
            try:
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            except Exception:
                pass
        except Exception:
            pass
        self._running = True
        # Pace capture to UI/recording rate — avoids flooding the GUI thread with signals.
        preview_hz = 28.0
        record_hz = min(30.0, float(self._fps))
        # Keep preview frames sharp on large tabs (scale in QLabel uses SmoothTransformation).
        preview_max_w = 1920
        next_deadline = 0.0
        while self._running:
            period = (1.0 / record_hz) if self._emit_bgr_for_record else (1.0 / preview_hz)
            now = time.perf_counter()
            if now < next_deadline:
                time.sleep(min(next_deadline - now, 0.05))
                continue
            next_deadline = time.perf_counter() + period
            ok, frame = cap.read()
            if not ok or frame is None or np is None:
                continue
            hh, ww = frame.shape[:2]
            work_bgr = frame
            if ww > preview_max_w:
                scale = preview_max_w / float(ww)
                nw = max(1, int(ww * scale))
                nh = max(1, int(hh * scale))
                work_bgr = cv2.resize(work_bgr, (nw, nh), interpolation=cv2.INTER_LINEAR)
            rgb = cv2.cvtColor(work_bgr, cv2.COLOR_BGR2RGB)
            h2, w2, _ch = rgb.shape
            bpl = 3 * w2
            img = QImage(rgb.data, w2, h2, bpl, QImage.Format_RGB888).copy()
            self.frame_ready.emit(img)
            if self._emit_bgr_for_record:
                self.bgr_ready.emit(work_bgr.copy())
        cap.release()


class OpenCvVideoRecorder:
    """Minimal MP4 writer using OpenCV (finalize on ``close`` — no long Qt finalize wait)."""

    def __init__(self, path: Path, size: Tuple[int, int], fps: float):
        if not _HAS_CV2:
            raise RuntimeError("OpenCV not installed")
        self.path = path
        self._size = size
        self._fps = fps
        fourcc = _fourcc_mp4()
        self._writer = cv2.VideoWriter(str(path), fourcc, fps, size)
        if not self._writer.isOpened():
            raise RuntimeError("VideoWriter refused this codec/path — try a different folder or shorter path.")

    def write_frame_bgr(self, frame) -> None:
        if self._writer is not None:
            self._writer.write(frame)

    def close(self) -> None:
        if self._writer is not None:
            self._writer.release()
            self._writer = None


def bgr_from_qimage(img: QImage):
    """BGR ndarray for VideoWriter from RGB ``QImage`` (handles stride padding)."""
    if not _HAS_CV2 or np is None or cv2 is None:
        return None
    img = img.convertToFormat(QImage.Format_RGB888)
    w, h = img.width(), img.height()
    bpl = img.bytesPerLine()
    expected = bpl * h
    bits = img.bits()
    try:
        buf = bits.asstring(expected)  # PyQt5 sip.voidptr
    except Exception:
        buf = bytes(bits)
    arr = np.frombuffer(buf, dtype=np.uint8).reshape((h, bpl))
    arr = arr[:, : w * 3].reshape(h, w, 3).copy()
    return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)


class CameraIndexProbeThread(QThread):
    """Enumerate USB cameras off the GUI thread (``list_camera_indices`` can block)."""

    indices_ready = pyqtSignal(list)

    def run(self) -> None:
        if not _HAS_CV2:
            self.indices_ready.emit([])
            return
        self.indices_ready.emit(list_camera_indices())
