"""
"Your window": the camera seen through a foggy pane you can write on with
your finger. Shown on Home.

Layers, painted every frame:
    1. the base: the mirrored camera image (cover-fit), or a soft placeholder
       scene while the camera is off
    2. fog: a blurred, lightened copy of the base
    3. the writing mask cuts holes in the fog. It has two parts:
         - saved: the note the user saved (fog_note.png), kept between runs
         - live: new strokes, which slowly fog over unless saved

Only the mask is ever saved, never a camera image.

Hand control (see backend/fog.py): point to write, fist to pause, hold an
open palm for a second to wipe the window clean.
"""

import os
import time

from PySide6.QtCore import QPointF, QRectF, QSize, QThread, Qt, Signal, Slot
from PySide6.QtGui import (
    QColor,
    QImage,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import QSizePolicy, QWidget

from frontend.components.gesture_recorder_dialog import CameraPreviewWorker
from backend.fog import PenState, PointSmoother, fingertip, hand_mode, note_path
from backend.settings import gesture_settings


MASK_SIZE = QSize(960, 340)       # mask resolution (stretched to the widget)
# Pen sizes (chosen in Settings), as a fraction of the mask height.
STROKE_WIDTHS = {"thin": 0.045, "medium": 0.075, "thick": 0.115}
DEFAULT_STROKE = "medium"
MAX_JUMP = 0.18                   # ignore jumps larger than this (fraction of width)
MIN_STEP = 0.3                    # skip moves smaller than this × pen width
WIPE_HOLD_SECONDS = 1.0
FADE_EVERY_SECONDS = 0.5          # live strokes fog over: ~half gone in 30 s
FADE_ALPHA = 252

FILTERS = ("fog", "clear", "mono")

# Two fogs, chosen in Settings. Writing wipes the fog away and leaves a
# soft line of "ink" in a colour that contrasts with that fog, so it reads
# whatever the camera shows behind it.
FOG_STYLES = {
    "white": {
        "fog": QColor(236, 238, 242, 175),
        "ink": QColor(28, 26, 32, 170),
        "hint": QColor("#3A3F4B"),
    },
    "black": {
        "fog": QColor(14, 13, 16, 185),
        "ink": QColor(250, 246, 238, 190),
        "hint": QColor("#D9D4CC"),
    },
}
DEFAULT_FOG = "white"

SCENE_BASE = QColor("#2A2E38")
SCENE_SHAPES = (QColor("#3A3F4B"), QColor("#4A4535"), QColor("#343A48"))


def _new_mask():
    image = QImage(MASK_SIZE, QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.transparent)
    return image


def _mask_is_empty(image):
    # Sample a grid instead of every pixel; strokes are wide.
    for y in range(0, image.height(), 8):
        for x in range(0, image.width(), 8):
            if image.pixelColor(x, y).alpha() > 20:
                return False
    return True


class FogWindow(QWidget):

    # Short user-facing status ("Writing", "Paused", "Wiped", errors)
    status_changed = Signal(str)
    camera_state_changed = Signal(bool)

    def __init__(self, parent=None):

        super().__init__(parent)

        self.setMinimumHeight(220)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setAccessibleName("Your window: a foggy camera view you can write on")

        self.filter = "fog"
        self.fog_colour = DEFAULT_FOG
        self.stroke = DEFAULT_STROKE
        self.apply_settings()
        self.frame = None              # latest camera QImage
        self.saved = _new_mask()
        self.live = _new_mask()

        self._stroke = []               # last few smoothed points of this stroke
        self._smoother = PointSmoother()
        self._pen = PenState()
        self._wipe_since = None
        self._last_fade = time.monotonic()
        self._mode = None

        self.thread = None
        self.worker = None

        self.load_note()

    # -----------------------------------------------------
    # NOTE (saved mask)
    # -----------------------------------------------------

    def load_note(self):

        path = note_path()

        if os.path.isfile(path):
            image = QImage(path)
            if not image.isNull():
                self.saved = image.convertToFormat(
                    QImage.Format_ARGB32_Premultiplied
                ).scaled(MASK_SIZE)

        self.update()

    def has_writing(self):
        return not (_mask_is_empty(self.saved) and _mask_is_empty(self.live))

    def save_note(self):
        """Keep everything written so far. An empty window removes the note."""

        painter = QPainter(self.saved)
        painter.drawImage(0, 0, self.live)
        painter.end()

        self.live = _new_mask()
        path = note_path()

        if _mask_is_empty(self.saved):
            if os.path.isfile(path):
                os.remove(path)
            self.status_changed.emit("Window cleared")
        else:
            self.saved.save(path, "PNG")
            self.status_changed.emit("Note saved")

        self.update()

    def wipe(self):
        """Clear the window (the saved file only changes when you save)."""
        self.saved = _new_mask()
        self.live = _new_mask()
        self._end_stroke()
        self.status_changed.emit("Wiped clean. Save to keep it empty.")
        self.update()

    def apply_settings(self, settings=None):
        """Re-read the fog colour and pen size from Settings."""
        settings = settings or gesture_settings.load()
        colour = settings.get("fog_colour", DEFAULT_FOG)
        self.fog_colour = colour if colour in FOG_STYLES else DEFAULT_FOG
        stroke = settings.get("fog_stroke", DEFAULT_STROKE)
        self.stroke = stroke if stroke in STROKE_WIDTHS else DEFAULT_STROKE
        self.update()

    @property
    def stroke_width(self):
        """Pen width in mask pixels."""
        return MASK_SIZE.height() * STROKE_WIDTHS[self.stroke]

    @property
    def style(self):
        return FOG_STYLES[self.fog_colour]

    def set_filter(self, name):
        if name in FILTERS:
            self.filter = name
            self.update()

    # -----------------------------------------------------
    # CAMERA
    # -----------------------------------------------------

    @property
    def camera_running(self):
        return self.worker is not None

    def start_camera(self):

        if self.worker is not None:
            return

        self.thread = QThread(self)
        self.worker = CameraPreviewWorker(draw_skeleton=False)
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.frame_ready.connect(self._on_frame)
        self.worker.hand_landmarks.connect(self._on_landmarks)
        self.worker.error.connect(self._on_error)
        self.worker.finished.connect(self.thread.quit)

        self.thread.start()
        self.camera_state_changed.emit(True)
        self.status_changed.emit("Point to write · fist to pause · open palm to wipe")

    def stop_camera(self):

        worker, thread = self.worker, self.thread
        self.worker = None
        self.thread = None

        if worker is not None:
            worker.stop()

        if thread is not None:
            # Keep a reference until the thread really ends (it may be
            # waiting on a slow webcam); destroying a running QThread aborts.
            self._retiring = getattr(self, "_retiring", [])
            self._retiring.append(thread)
            thread.finished.connect(lambda t=thread: self._retiring.remove(t) if t in self._retiring else None)

        self.frame = None
        self._end_stroke()
        self._pen.reset()
        self.camera_state_changed.emit(False)
        self.update()

    def wait_for_camera(self, ms=5000):
        """Block until stopped camera threads finish (used when closing)."""
        for thread in list(getattr(self, "_retiring", [])):
            thread.wait(ms)

    @Slot(str)
    def _on_error(self, message):
        self.stop_camera()
        self.status_changed.emit(message.split("\n")[0])

    @Slot(QImage, object, object, float)
    def _on_frame(self, image, vector, builtin, confidence):

        if self.worker is None:
            return

        self.frame = image

        now = time.monotonic()
        if now - self._last_fade >= FADE_EVERY_SECONDS:
            self._last_fade = now
            painter = QPainter(self.live)
            painter.setCompositionMode(QPainter.CompositionMode_DestinationIn)
            painter.fillRect(self.live.rect(), QColor(0, 0, 0, FADE_ALPHA))
            painter.end()

        self.update()

    # -----------------------------------------------------
    # WRITING
    # -----------------------------------------------------

    def _image_rect(self, size=None):
        """Where the cover-fitted camera image sits in widget coordinates."""

        size = size or (self.frame.size() if self.frame is not None else QSize(4, 3))
        w, h = self.width(), self.height()
        scale = max(w / size.width(), h / size.height())
        iw, ih = size.width() * scale, size.height() * scale
        return QRectF((w - iw) / 2, (h - ih) / 2, iw, ih)

    def _to_mask(self, point):
        """Image-normalised (x, y) -> mask pixel coordinates, or None if off-screen."""

        rect = self._image_rect()
        wx = rect.x() + point[0] * rect.width()
        wy = rect.y() + point[1] * rect.height()

        if not (0 <= wx <= self.width() and 0 <= wy <= self.height()):
            return None

        return QPointF(
            wx / max(self.width(), 1) * MASK_SIZE.width(),
            wy / max(self.height(), 1) * MASK_SIZE.height(),
        )

    def _pen_painter(self):
        # A solid stroke; the soft, fingertip-on-glass edge comes from
        # blurring the whole mask when painting (see _soft_mask). Drawing a
        # soft edge per segment made overlapping halos look dotted.
        painter = QPainter(self.live)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor(0, 0, 0, 255), self.stroke_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.setBrush(Qt.NoBrush)
        return painter

    @staticmethod
    def _mid(a, b):
        return QPointF((a.x() + b.x()) / 2, (a.y() + b.y()) / 2)

    def _add_point(self, point):
        """
        Extend the stroke to `point`. Segments are quadratic curves through
        the midpoints of successive points (each point is the control), so
        the line bends smoothly instead of zig-zagging between samples.
        """

        if point is None:
            return                          # nowhere to draw (off the edge)

        pts = self._stroke
        pts.append(point)
        del pts[:-3]

        painter = self._pen_painter()

        if len(pts) == 1:
            painter.drawLine(point, point)                 # a dot
        elif len(pts) == 2:
            painter.drawLine(pts[0], self._mid(pts[0], pts[1]))
        else:
            path = QPainterPath(self._mid(pts[0], pts[1]))
            path.quadTo(pts[1], self._mid(pts[1], pts[2]))
            painter.drawPath(path)

        painter.end()

    def _end_stroke(self):
        """Finish the line to the last point and start afresh next time."""

        pts = self._stroke
        if len(pts) >= 2:
            painter = self._pen_painter()
            painter.drawLine(self._mid(pts[-2], pts[-1]), pts[-1])
            painter.end()

        self._stroke = []
        self._smoother.reset()

    def handle_hand(self, landmarks, now=None):
        """Process one frame's landmarks (public so it can be tested)."""

        now = now if now is not None else time.monotonic()
        raw = hand_mode(landmarks)
        mode = self._pen.update(raw, now)

        if mode != self._mode:
            self._mode = mode
            if mode == "write":
                self.status_changed.emit("Writing…")
            elif mode == "pause":
                self.status_changed.emit("Paused")

        if mode == "wipe":
            self._end_stroke()
            if self._wipe_since is None:
                self._wipe_since = now
            elif now - self._wipe_since >= WIPE_HOLD_SECONDS:
                self._wipe_since = None
                self.wipe()
            return

        self._wipe_since = None

        if mode != "write":
            if self._stroke:
                self._end_stroke()
                self.update()
            return

        if raw != "write":
            return      # a short flicker: keep the stroke, draw nothing

        point = self._to_mask(self._smoother(fingertip(landmarks), now))

        if point is None:
            self._end_stroke()
            return

        if self._stroke:
            last = self._stroke[-1]
            jump = (point - last).manhattanLength() / MASK_SIZE.width()
            if jump > MAX_JUMP:
                self._end_stroke()          # tracking glitch: start a new stroke
                point = self._to_mask(self._smoother(fingertip(landmarks), now))
                if point is None:           # ...and it's off the edge now
                    return
            elif (point - last).manhattanLength() < self.stroke_width * MIN_STEP:
                return                      # too small a move: wait for more

        self._add_point(point)
        self.update()

    @Slot(object)
    def _on_landmarks(self, landmarks):
        if self.worker is not None:
            self.handle_hand(landmarks)

    # -----------------------------------------------------
    # PAINTING
    # -----------------------------------------------------

    def _scene(self, w, h):
        """The placeholder 'room' behind the fog while the camera is off."""

        image = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
        image.fill(SCENE_BASE)

        p = QPainter(image)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(SCENE_SHAPES[0])
        p.drawRoundedRect(QRectF(w * 0.2, h * 0.18, w * 0.34, h * 1.1), w * 0.17, w * 0.17)
        p.setBrush(SCENE_SHAPES[1])
        p.drawRoundedRect(QRectF(w * 0.74, h * 0.12, w * 0.18, h * 0.46), 10, 10)
        p.setBrush(SCENE_SHAPES[2])
        p.drawEllipse(QPointF(w * 0.62, h * 0.86), w * 0.12, h * 0.3)
        p.end()

        return image

    def _base(self, w, h):

        if self.frame is None:
            return self._scene(w, h)

        image = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
        image.fill(Qt.black)

        p = QPainter(image)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.drawImage(self._image_rect(), self.frame)
        p.end()

        if self.filter == "mono":
            image = image.convertToFormat(QImage.Format_Grayscale8).convertToFormat(
                QImage.Format_ARGB32_Premultiplied
            )

        return image

    def _fog(self, base):
        """Blur (downscale + smooth upscale) and lighten."""

        w, h = base.width(), base.height()
        small = base.scaled(max(w // 18, 1), max(h // 18, 1), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        fog = small.scaled(w, h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation).convertToFormat(
            QImage.Format_ARGB32_Premultiplied
        )

        p = QPainter(fog)
        p.fillRect(fog.rect(), self.style["fog"])
        p.end()

        return fog

    def _soft_mask(self, w, h):
        """Saved + live writing at widget size, with softened edges."""

        mask = QImage(MASK_SIZE, QImage.Format_ARGB32_Premultiplied)
        mask.fill(Qt.transparent)
        p = QPainter(mask)
        p.drawImage(0, 0, self.saved)
        p.drawImage(0, 0, self.live)
        p.end()

        # Downscale + smooth upscale = a cheap blur of the edges.
        small = mask.scaled(
            max(MASK_SIZE.width() // 6, 1), max(MASK_SIZE.height() // 6, 1),
            Qt.IgnoreAspectRatio, Qt.SmoothTransformation,
        )
        return small.scaled(w, h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)

    def paintEvent(self, event):

        w, h = self.width(), self.height()
        if w <= 0 or h <= 0:
            return

        base = self._base(w, h)

        if self.filter != "clear":

            fog = self._fog(base)
            mask = self._soft_mask(w, h)

            # Cut the writing out of the fog.
            p = QPainter(fog)
            p.setCompositionMode(QPainter.CompositionMode_DestinationOut)
            p.drawImage(0, 0, mask)
            p.end()

            # Ink: the same strokes in a colour that contrasts with the fog.
            p = QPainter(mask)
            p.setCompositionMode(QPainter.CompositionMode_SourceIn)
            p.fillRect(mask.rect(), self.style["ink"])
            p.end()

            p = QPainter(base)
            p.drawImage(0, 0, fog)
            p.drawImage(0, 0, mask)
            p.end()

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        clip = QPainterPath()
        clip.addRoundedRect(QRectF(0, 0, w, h), 18, 18)
        painter.setClipPath(clip)
        painter.drawImage(0, 0, base)

        if self.filter != "clear" and self.frame is None and not self.has_writing():
            painter.setPen(self.style["hint"])
            font = painter.font()
            font.setPointSize(12)
            painter.setFont(font)
            painter.drawText(
                QRectF(0, 0, w, h),
                Qt.AlignCenter,
                "Start the camera, then point your finger to write on the fog",
            )

        painter.end()

    def showEvent(self, event):
        # Pick up changes made in Settings.
        self.apply_settings()
        super().showEvent(event)

    def hideEvent(self, event):
        # Leaving Home: free the camera for studios.
        self.stop_camera()
        super().hideEvent(event)
