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


class GestureWorker(QObject):

    gesture_detected = Signal(str, float)

    # An event to run: {"name", "gesture", "action", "value"}
    custom_event_detected = Signal(dict)

    # Scroll the window in front by this many wheel units (+ up), and the
    # direction now ("up", "down" or "" when held still).
    scroll_requested = Signal(int, str)

    status_changed = Signal(str)
    error = Signal(str)

    # Emitted when run() has fully exited and the camera is released.
    finished = Signal()

    def __init__(
        self,
        profile_name="presentation",
        custom_studio=None
    ):
        super().__init__()

        self.profile_name = profile_name
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
        self.require_arm = self.settings["require_arm"]
        self.arm_gesture = self.settings["arm_gesture"]
        self.arm_timeout = self.settings["arm_timeout"]
        self.armed = False
        self._armed_until = 0.0

        # -----------------------------------------------------
        # EVENTS
        # -----------------------------------------------------
        # A custom studio brings its own events; built-in studios use a
        # profile, converted to the same event format. Custom studio events
        # are the studio's own list, so edits made while running apply.

        if self.custom_studio is not None:

            self.events = self.custom_studio.get("events", [])

        else:

            profile_manager = ProfileManager()
            profile_manager.load(profile_name)

            self.events = profile_events(
                profile_manager.current_profile
            )

        # -----------------------------------------------------
        # LIVE SCROLLING (Browse & Media Studio)
        # -----------------------------------------------------
        # Poses mapped to "Scroll" scroll while held instead of running once.

        self.scroll_poses = {
            event["gesture"] for event in self.events
            if event.get("action") == "Scroll" and event.get("gesture")
        }
        self.events = [e for e in self.events if e.get("action") != "Scroll"]
        self.scroller = ScrollController(
            speed=self.settings["browse_scroll_speed"],
            height_sets_speed=self.settings["browse_scroll_by_height"],
        )
        self._motions_quiet_until = 0.0
        self._scroll_direction = ""

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

            # -------------------------------------------------
            # LIVE SCROLLING (while the scroll pose is held)
            # -------------------------------------------------

            if self.scroll_poses and self._scroll(gesture, confidence, now):
                continue

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

        holding = self._pose(gesture, confidence) in self.scroll_poses
        if holding and self.require_arm and not self.armed:
            holding = False

        amount = self.scroller.update(holding, self._hand_height() if holding else None, now)

        direction = self.scroller.direction or ""
        if holding and direction != self._scroll_direction:
            self._scroll_direction = direction
            self.scroll_requested.emit(0, direction)

        if not holding:
            if self._scroll_direction or self.scroller.active:
                self._scroll_direction = ""
            return False

        if self.require_arm:
            self._set_armed(True)      # still in use

        if amount:
            self.scroll_requested.emit(amount, direction)

        # Nothing else fires while scrolling, and for a moment after.
        self.stabilizer.update(None, 0.0)
        self._motions_quiet_until = now + 0.6
        return True

    def _handle_motion(self, motion, confidence):

        self.gesture_detected.emit(motion, confidence)

        self._trigger(motion)

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

    def _trigger(self, gesture):
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

            print(f"🎯 Event matched: {event.get('name')} (triggered by {gesture})")

            self.custom_event_detected.emit(event)

    @Slot()
    def stop(self):

        self._stop_requested = True