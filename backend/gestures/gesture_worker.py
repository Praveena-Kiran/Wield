import time

import cv2

from PySide6.QtCore import QObject, Signal, Slot

from backend.gestures.google_gesture_recognizer import GoogleGestureRecognizer
from backend.gestures.gesture_stabilizer import GestureStabilizer
from backend.gestures.frame_pacer import FramePacer
from backend.gestures.custom_gestures import CustomGestureMatcher
from backend.gestures.motions import HandMotionRecognizer, hand_points
from backend.settings import gesture_settings
from backend.profile_manager import ProfileManager
from backend.automation.events import events_for_gesture, profile_events
from backend.gestures.scroll import ScrollController
from backend.gestures.hold import HoldTracker
from backend.gestures.hand_mouse import HandMouse


# Hold-and-move volume: wheel units (from ScrollController) per volume step.
VOLUME_UNITS_PER_STEP = 300

# Hands-free mode ("auto"): which built-in studio's gestures to use for the
# app in front. Anything not listed uses Browse & Media.
AUTO_STUDIOS = {
    "powerpnt.exe": "presentation",
    "pptview.exe": "presentation",
}
AUTO_DEFAULT = "browse"
AUTO_CHECK_SECONDS = 0.5

# Hands-free voice phrases that wake Wield up or send it back to sleep.
WAKE_EVENTS = [
    {"name": "Wake up", "gesture": "🎤 wake up", "action": "App", "value": "activate"},
    {"name": "Wake up", "gesture": "🎤 start watching", "action": "App", "value": "activate"},
    {"name": "Go to sleep", "gesture": "🎤 go to sleep", "action": "App", "value": "deactivate"},
    {"name": "Go to sleep", "gesture": "🎤 stop watching", "action": "App", "value": "deactivate"},
]


def studio_for_app(process_name):
    """Hands-free mode: the studio whose gestures fit the app in front."""
    return AUTO_STUDIOS.get((process_name or "").lower(), AUTO_DEFAULT)


def _load_profile(name):
    manager = ProfileManager()
    manager.load(name)
    return manager.current_profile


def _desktop_foreground():
    from backend.automation.controllers.desktop_input import DesktopInput
    return DesktopInput().foreground_process


class GestureWorker(QObject):

    gesture_detected = Signal(str, float)

    # An event to run: {"name", "gesture", "action", "value"}
    custom_event_detected = Signal(dict)

    # Scroll the window in front by this many wheel units (+ up), and the
    # direction now ("up", "down" or "" when held still).
    scroll_requested = Signal(int, str)

    # Change the volume by this many steps (+ louder), while a volume pose
    # is held and moved; and the direction now ("up", "down" or "").
    volume_requested = Signal(int, str)

    # A held action filling up: (event name, 0..1). 0 = let go / cancelled.
    hold_progress = Signal(str, float)

    # Hand mouse: what to do with the pointer this frame, e.g.
    # [("move", x, y), ("left_down",), ("left_up",), ("right_click",)].
    mouse_ops = Signal(list)

    # Hand mouse switched on / off (by voice, a gesture, or a held fist).
    mouse_mode_changed = Signal(bool)

    # Hands-free mode switched to another studio's gestures ("presentation"
    # or "browse") because a different app came to the front.
    studio_changed = Signal(str)

    status_changed = Signal(str)
    error = Signal(str)

    # Emitted when run() has fully exited and the camera is released.
    finished = Signal()

    def __init__(
        self,
        profile_name="presentation",
        custom_studio=None,
        foreground=None,
    ):
        super().__init__()

        self.profile_name = profile_name

        # Hands-free mode: always watching, woken by the activation gesture,
        # with the gestures of the studio that fits the app in front.
        self.auto = profile_name == "auto"
        self._foreground = foreground
        self.custom_studio = custom_studio
        self.running = False

        # Set by stop(). Separate from `running` so a stop requested before
        # run() starts (e.g. leaving a studio straight away) still counts.
        self._stop_requested = False

        # Accessibility settings (Settings page): matching strictness,
        # hold time and the optional activation gesture.
        self.settings = gesture_settings.load()
        limits = gesture_settings.thresholds(self.settings)

        self.stabilizer = GestureStabilizer(
            confidence_threshold=limits["min_confidence"],
            hold_time=limits["hold_time"],
        )
        self.recognizer = GoogleGestureRecognizer()

        # The user's own recorded gestures (see Gesture Studio).
        self.custom_matcher = CustomGestureMatcher.from_store(
            max_distance=limits["pose_max_distance"]
        )

        # Motions: built-in swipes plus the user's recorded movements.
        self.motions = HandMotionRecognizer(
            max_distance=limits["motion_max_distance"],
            swipe_min_straightness=limits["swipe_min_straightness"],
            swipe_max_angle=limits["swipe_max_angle"],
        )

        # Activation ("arm") gesture: when required, nothing runs until it
        # is made, and Wield switches off after arm_timeout idle seconds.
        self.require_arm = self.settings["require_arm"] or self.auto
        self.arm_gesture = self.settings["arm_gesture"]
        self.arm_timeout = (
            self.settings["hands_free_timeout"] if self.auto else self.settings["arm_timeout"]
        )
        self.armed = False
        self._armed_until = 0.0

        # -----------------------------------------------------
        # EVENTS
        # -----------------------------------------------------
        # A custom studio brings its own events; built-in studios use a
        # profile, converted to the same event format. Custom studio events
        # are the studio's own list, so edits made while running apply.

        self._moving = None              # "scroll" / "volume" while held
        self._volume_units = 0.0
        self.scroller = ScrollController(
            speed=self.settings["browse_scroll_speed"],
            height_sets_speed=self.settings["browse_scroll_by_height"],
        )
        self._motions_quiet_until = 0.0
        self._scroll_direction = ""

        # Hand mouse: while on, the hand moves the pointer and pinches
        # click; nothing else runs. Switched from the UI thread through
        # request_mouse(), applied at the next frame.
        self.mouse_mode = False
        self._mouse_request = None
        self.hand_mouse = HandMouse()

        if self.custom_studio is not None:

            events = self.custom_studio.get("events", [])

        elif self.auto:

            # Both built-in studios, switched by the app in front.
            self.studio_events = {
                name: profile_events(_load_profile(name))
                for name in ("presentation", "browse")
            }
            self.studio = None
            self._last_studio_check = -1e9
            events = self.studio_events[AUTO_DEFAULT]

        else:

            events = profile_events(_load_profile(profile_name))

        self._use_events(events)

    def _use_events(self, events):
        """
        Set the events to run. Poses mapped to "Scroll" (or "VolumeHold")
        work while held instead (move the hand up or down to scroll, or
        change the volume), and some actions need a held pose first.
        """

        hold_and_move = {"Scroll": "scroll", "VolumeHold": "volume", "ScrollPoint": "point"}

        # pose -> "scroll" | "volume" | "point_up" | "point_down"
        self.scroll_poses = {}
        for event in events:
            kind = hold_and_move.get(event.get("action"))
            if kind and event.get("gesture"):
                if kind == "point":
                    kind = "point_down" if event.get("value") == "down" else "point_up"
                self.scroll_poses[event["gesture"]] = kind
        if self.scroll_poses or any(e.get("action") in hold_and_move for e in events):
            self.events = [e for e in events if e.get("action") not in hold_and_move]
        else:
            # The same list object, so edits to a running custom studio apply.
            self.events = events

        # Deliberate actions (closing a tab): the pose must be held, with
        # a bar filling up on screen, before they run.
        self.holds = HoldTracker(self.events)

        self.scroller.reset()
        self._moving = None

    @property
    def voice_events(self):
        """
        Everything voice can trigger: this studio's phrases (hands-free:
        both studios' and the wake words), plus "help" everywhere.
        """
        from backend.cheat_sheet import HELP_EVENTS
        if not self.auto:
            return list(self.events) + HELP_EVENTS
        both = [e for events in self.studio_events.values() for e in events]
        return both + WAKE_EVENTS + HELP_EVENTS

    def _check_studio(self, now):
        """Hands-free mode: follow the app in front (every half second)."""

        if now - self._last_studio_check < AUTO_CHECK_SECONDS:
            return
        self._last_studio_check = now

        try:
            if self._foreground is None:
                self._foreground = _desktop_foreground()
            studio = studio_for_app(self._foreground())
        except Exception:  # noqa: BLE001 - keep the current one
            return

        if studio != self.studio:
            self.studio = studio
            self._use_events(self.studio_events[studio])
            self.studio_changed.emit(studio)

    def _open_camera(self, attempts=4, delay=0.75):
        """
        Open the webcam, retrying briefly: on Windows the previous studio
        may still be releasing it.
        """

        for attempt in range(attempts):

            if self._stop_requested:
                return None

            camera = cv2.VideoCapture(0)

            if camera.isOpened():
                return camera

            camera.release()

            if attempt < attempts - 1:
                time.sleep(delay)

        return None

    @Slot()
    def run(self):

        try:
            self._run()
        finally:
            self.running = False
            self.finished.emit()

    def _run(self):

        if self._stop_requested:
            return

        self.running = True

        camera = self._open_camera()

        if camera is None:

            if not self._stop_requested:
                self.error.emit(
                    "Could not open webcam. Check that no other app "
                    "is using it."
                )

            return

        try:
            self._loop(camera)
        finally:
            camera.release()

        self.status_changed.emit(
            "STOPPED"
        )

    def _loop(self, camera):

        self.status_changed.emit("READY")

        pacer = FramePacer()

        while not self._stop_requested:

            # Slow down while no hand is in view (saves CPU).
            pacer.wait(self.recognizer.last_image_landmarks is not None)

            success, frame = camera.read()

            if not success:

                self.error.emit(
                    "Could not read webcam."
                )

                break

            frame = cv2.flip(
                frame,
                1
            )

            gesture, confidence = (
                self.recognizer.detect(frame)
            )

            now = time.monotonic()

            if self.auto:
                self._check_studio(now)

            # -------------------------------------------------
            # HAND MOUSE (nothing else while it's on)
            # -------------------------------------------------

            if self._mouse_request is not None:
                self._set_mouse_mode(self._mouse_request)
                self._mouse_request = None

            if self.mouse_mode:
                self._mouse_frame(now)
                continue

            # -------------------------------------------------
            # LIVE SCROLLING (while the scroll pose is held)
            # -------------------------------------------------

            if self.scroll_poses and self._scroll(gesture, confidence, now):
                continue

            if self.holds.events:
                self._update_holds(gesture, confidence, now)

            # -------------------------------------------------
            # MOTIONS (swipes, waves...)
            # -------------------------------------------------

            h, w = frame.shape[:2]

            motion = self.motions.update(
                now,
                hand_points(self.recognizer.last_image_landmarks, w / h),
            )

            # Just after scrolling, the hand dropping back isn't a swipe.
            if motion and now >= self._motions_quiet_until:
                self._handle_motion(*motion)

            # While the hand is moving, ignore poses so a swipe can't
            # trigger "open palm" half way through.
            if self.motions.active:
                self.stabilizer.update(None, 0.0)
                continue

            # A recorded custom gesture takes priority. Recording rejects
            # poses that look like built-in gestures, so the two don't clash.
            if self.custom_matcher.has_gestures():

                custom_gesture, custom_confidence = (
                    self.custom_matcher.match(
                        self.recognizer.last_landmarks,
                        self.recognizer.last_handedness
                    )
                )

                if custom_gesture:
                    gesture = custom_gesture
                    confidence = custom_confidence

            confirmed_gesture = (
                self.stabilizer.update(
                    gesture,
                    confidence
                )
            )

            if self.require_arm:
                self._check_arm_timeout()

            if not confirmed_gesture:
                continue

            # -------------------------------------------------
            # GESTURE DETECTED
            # -------------------------------------------------

            self.gesture_detected.emit(
                confirmed_gesture,
                confidence
            )

            self._trigger(confirmed_gesture)

    def request_mouse(self, on):
        """Turn the hand mouse on or off (safe to call from the UI thread)."""
        self._mouse_request = bool(on)

    def _set_mouse_mode(self, on):
        if on == self.mouse_mode:
            return
        if not on and self.hand_mouse.left_down:
            self.mouse_ops.emit([("left_up",)])
        self.mouse_mode = on
        self.hand_mouse.reset()
        self.scroller.reset()
        self.stabilizer.update(None, 0.0)
        self.mouse_mode_changed.emit(on)

    def _mouse_frame(self, now):
        ops = self.hand_mouse.update(self.recognizer.last_image_landmarks, now)
        if self.recognizer.last_image_landmarks and self.require_arm:
            self._set_armed(True)          # in use: don't fall asleep
        if ("exit",) in ops:
            ops = [op for op in ops if op != ("exit",)]
            if ops:
                self.mouse_ops.emit(ops)
            self._set_mouse_mode(False)
            return
        if ops:
            self.mouse_ops.emit(ops)
        self._motions_quiet_until = now + 0.6

    def _pose(self, gesture, confidence):
        """This frame's pose (built-in or recorded), or None."""

        if self.custom_matcher.has_gestures():
            custom, custom_confidence = self.custom_matcher.match(
                self.recognizer.last_landmarks,
                self.recognizer.last_handedness,
            )
            if custom:
                return custom
        if gesture and confidence >= self.stabilizer.confidence_threshold:
            return gesture
        return None

    def _hand_height(self):
        """Palm height in 0..1 image coordinates (0 = top), or None."""
        lm = self.recognizer.last_image_landmarks
        if not lm or len(lm) < 10:
            return None
        y = lambda p: p.y if hasattr(p, "y") else p[1]
        return (y(lm[0]) + y(lm[9])) / 2

    def _scroll(self, gesture, confidence, now):
        """
        Scroll while a scroll pose is held. Returns True if this frame was
        used for scrolling (so it doesn't also trigger anything else).
        """

        kind = self.scroll_poses.get(self._pose(gesture, confidence))
        if kind and self.require_arm and not self.armed:
            kind = None

        # Switching straight from the scroll pose to the volume pose starts afresh.
        if kind != self._moving:
            self.scroller.reset()
            self._volume_units = 0.0
            self._scroll_direction = ""
            self._moving = kind

        holding = kind is not None
        pointing = {"point_up": "up", "point_down": "down"}.get(kind)
        amount = self.scroller.update(
            holding, self._hand_height() if holding else None, now, direction=pointing,
        )

        signal = self.volume_requested if kind == "volume" else self.scroll_requested

        direction = self.scroller.direction or ""
        if holding and direction != self._scroll_direction:
            self._scroll_direction = direction
            signal.emit(0, direction)

        if not holding:
            return False

        if self.require_arm:
            self._set_armed(True)      # still in use

        if amount and kind in ("scroll", "point_up", "point_down"):
            self.scroll_requested.emit(amount, direction)

        elif amount and kind == "volume":
            # Gentler than scrolling: one volume step (2%) per this many units.
            self._volume_units += amount
            steps = int(self._volume_units / VOLUME_UNITS_PER_STEP)
            if steps:
                self._volume_units -= steps * VOLUME_UNITS_PER_STEP
                self.volume_requested.emit(steps, direction)

        # Nothing else fires while scrolling, and for a moment after.
        self.stabilizer.update(None, 0.0)
        self._motions_quiet_until = now + 0.6
        return True

    def _update_holds(self, gesture, confidence, now):
        """Fill (or cancel) the bar of a held action; run it when full."""

        pose = self._pose(gesture, confidence)
        if self.require_arm and not self.armed:
            pose = None

        for name, progress, event in self.holds.update(pose, now):
            self.hold_progress.emit(name, progress)
            if event is not None:
                if self.require_arm:
                    self._set_armed(True)
                print(f"🎯 Event matched: {name} (held {event['gesture']})")
                self.custom_event_detected.emit(event)

    def _handle_motion(self, motion, confidence):

        self.gesture_detected.emit(motion, confidence)

        self._trigger(motion, motion=True)

    # -----------------------------------------------------
    # TRIGGERING (with the optional activation gesture)
    # -----------------------------------------------------

    def _set_armed(self, armed):

        if armed:
            self._armed_until = time.monotonic() + self.arm_timeout

        if armed != self.armed:
            self.armed = armed
            self.status_changed.emit("ARMED" if armed else "DISARMED")

    def _check_arm_timeout(self):

        if self.armed and time.monotonic() > self._armed_until:
            self._set_armed(False)

    def _trigger(self, gesture, motion=False):
        """Run the events for a recognised gesture or motion."""

        self._check_arm_timeout()

        if self.require_arm:

            if gesture == self.arm_gesture:
                self._set_armed(True)
                return

            if not self.armed:
                return

            # Still in use: keep Wield active.
            self._set_armed(True)

        # Every studio is a list of events; run the ones this
        # gesture triggers (see backend/automation/events.py).
        for event in events_for_gesture(self.events, gesture):

            # Wield's own actions (activate/deactivate) arm or disarm
            # when the activation setting is on; the status line reports it.
            if event.get("action") in ("App", "LensFlow"):
                if self.require_arm:
                    self._set_armed(event.get("value") != "deactivate")
                continue

            # Held actions run from _update_holds when a pose is held long
            # enough (a motion can't be held, so it runs straight away).
            if event.get("hold_seconds") and not motion:
                continue

            print(f"🎯 Event matched: {event.get('name')} (triggered by {gesture})")

            self.custom_event_detected.emit(event)

    @Slot()
    def stop(self):

        self._stop_requested = True