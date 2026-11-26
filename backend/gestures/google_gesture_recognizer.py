import os

import cv2
import mediapipe as mp

from backend.paths import model_path as bundled_model_path


# Re-exported for existing imports.
from backend.gestures.gesture_names import BUILTIN_GESTURES, BUILTIN_GESTURE_NAMES, POINTING_DOWN, POINTING_UP  # noqa: E402,F401
from backend.gestures.pointing import pointing  # noqa: E402

# How sure a pointing read from the hand points counts as (above the
# stabiliser's threshold: the finger test is strict).
POINTING_CONFIDENCE = 0.8


class GoogleGestureRecognizer:

    def __init__(self):

        model_path = bundled_model_path("gesture_recognizer.task")

        if not os.path.exists(model_path):
            raise FileNotFoundError(
                f"Gesture model not found at {model_path}"
            )

        BaseOptions = mp.tasks.BaseOptions 
        GestureRecognizer = mp.tasks.vision.GestureRecognizer 
        GestureRecognizerOptions = mp.tasks.vision.GestureRecognizerOptions 
        VisionRunningMode = mp.tasks.vision.RunningMode

        with open(model_path, "rb") as f:
            model_buffer = f.read()

        options = GestureRecognizerOptions(
            base_options=BaseOptions(
                model_asset_buffer=model_buffer
            ),
            running_mode=VisionRunningMode.IMAGE
        )

        self.recognizer = GestureRecognizer.create_from_options(options)

        self.last_landmarks = None
        self.last_image_landmarks = None
        self.last_handedness = None

    def detect(self, frame):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        mp_image = mp.Image(
            image_format=mp.ImageFormat.SRGB,
            data=rgb
        )

        result = self.recognizer.recognize(mp_image)

        # Keep the landmarks from this frame so custom gestures can be
        # matched without running MediaPipe a second time.
        self.last_landmarks = None
        self.last_image_landmarks = None
        self.last_handedness = None

        if result.hand_world_landmarks:
            self.last_landmarks = result.hand_world_landmarks[0]

        if result.hand_landmarks:
            self.last_image_landmarks = result.hand_landmarks[0]

        if result.handedness:
            self.last_handedness = result.handedness[0][0].category_name

        gesture, confidence = None, 0.0

        if result.gestures:
            gesture = BUILTIN_GESTURES.get(result.gestures[0][0].category_name)
            confidence = result.gestures[0][0].score

        # MediaPipe has no "pointing down" (and sometimes misses pointing
        # up): read the finger from the hand points instead.
        if gesture is None and self.last_image_landmarks is not None:
            direction = pointing(self.last_image_landmarks)
            if direction == "down":
                return POINTING_DOWN, POINTING_CONFIDENCE
            if direction == "up":
                return POINTING_UP, POINTING_CONFIDENCE

        return gesture, confidence
