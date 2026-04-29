"""Optional OpenCV capture — faster preview and recording than Qt Multimedia on many Windows setups."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from PyQt5.QtCore import QObject, Qt, QThread, pyqtSignal
from PyQt5.QtGui import QImage, QPixmap

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


def list_camera_indices(max_probe: int = 8) -> List[int]:
    """Return indices where ``VideoCapture(i)`` opens (best-effort)."""
    if not _HAS_CV2:
        return []
    found: List[int] = []
    backend = cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_ANY
    for i in range(max_probe):
        cap = cv2.VideoCapture(i, backend)
        try:
            if cap.isOpened():
                found.append(i)
        finally:
            cap.release()
    return found


def _fourcc_mp4() -> int:
    assert cv2 is not None
    return cv2.VideoWriter_fourcc(*"mp4v")


class FrameGrabThread(QThread):
    """Reads frames off the UI thread; emits RGB ``QImage`` copies."""

    frame_ready = pyqtSignal(object)  # QImage
    failed = pyqtSignal(str)

    def __init__(self, index: int, width: int, height: int, fps: float, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._index = index
        self._width = max(160, min(width, 1920))
        self._height = max(120, min(height, 1080))
        self._fps = max(8.0, min(fps, 60.0))
        self._running = False

    def stop(self) -> None:
        self._running = False

    def run(self) -> None:
        if not _HAS_CV2:
            self.failed.emit("OpenCV is not available.")
            return
        backend = cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_ANY
        cap = cv2.VideoCapture(self._index, backend)
        if not cap.isOpened():
            self.failed.emit(f"Cannot open camera index {self._index}.")
            return
        try:
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, float(self._width))
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, float(self._height))
            cap.set(cv2.CAP_PROP_FPS, self._fps)
        except Exception:
            pass
        self._running = True
        interval_ms = max(8, int(1000.0 / self._fps))
        while self._running:
            ok, frame = cap.read()
            if ok and frame is not None and np is not None:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                hh, ww, _ch = rgb.shape
                if ww > 960:
                    scale = 960.0 / float(ww)
                    rgb = cv2.resize(
                        rgb,
                        (max(1, int(ww * scale)), max(1, int(hh * scale))),
                        interpolation=cv2.INTER_AREA,
                    )
                hh, ww, _ch = rgb.shape
                bytes_per_line = 3 * ww
                img = QImage(rgb.data, ww, hh, bytes_per_line, QImage.Format_RGB888).copy()
                self.frame_ready.emit(img)
            self.msleep(interval_ms)
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
