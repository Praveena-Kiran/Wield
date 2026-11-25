"""Browse & Media Studio: input layer, foreground guard, scrolling, actions.

Every Windows call goes through a fake WinApi, so these run anywhere.
"""

import unittest

from backend.automation.controllers.desktop_input import (
    DesktopInput,
    InputUnavailable,
    VK,
    WHEEL_DELTA,
    is_browser,
    key_codes,
)
from backend.gestures.scroll import DEAD_ZONE, ScrollController


class FakeWinApi:
    def __init__(self, foreground="chrome.exe"):
        self.foreground = foreground
        self.keys = []
        self.wheel = []

    def foreground_process(self):
        return self.foreground

    def send_keys(self, codes):
        self.keys.append(list(codes))

    def send_wheel(self, amount):
        self.wheel.append(amount)


class ForegroundGuardTests(unittest.TestCase):

    def test_browsers(self):
        for name in ("chrome.exe", "MSEDGE.EXE", "firefox.exe", "brave.exe"):
            self.assertTrue(is_browser(name), name)
        for name in ("winword.exe", "notepad.exe", "Code.exe", "", None, "chrome"):
            self.assertFalse(is_browser(name), name)

    def test_browser_in_front(self):
        self.assertTrue(DesktopInput(FakeWinApi("msedge.exe")).browser_in_front())
        self.assertFalse(DesktopInput(FakeWinApi("acrord32.exe")).browser_in_front())

    def test_unknown_window_is_not_a_browser(self):
        class Broken(FakeWinApi):
            def foreground_process(self):
                raise InputUnavailable("no")
        self.assertFalse(DesktopInput(Broken()).browser_in_front())


class InputTests(unittest.TestCase):

    def test_key_codes(self):
        self.assertEqual(key_codes(["ctrl", "W"]), [VK["ctrl"], ord("W")])
        self.assertEqual(key_codes(["ctrl", "shift", "tab"]), [0x11, 0x10, 0x09])
        with self.assertRaises(ValueError):
            key_codes(["hyper"])

    def test_scroll_and_press_use_the_api(self):
        api = FakeWinApi()
        inp = DesktopInput(api)
        inp.scroll(240)
        inp.scroll(0)                 # nothing to send
        inp.press(["ctrl", "w"])
        self.assertEqual(api.wheel, [240])
        self.assertEqual(api.keys, [[0x11, 0x57]])

    def test_media_keys(self):
        api = FakeWinApi()
        DesktopInput(api).media("play_pause")
        self.assertEqual(api.keys, [[0xB3]])
        with self.assertRaises(ValueError):
            DesktopInput(api).media("rewind")


class ScrollTests(unittest.TestCase):

    def run_frames(self, scroller, ys, fps=30, start=0.0):
        total = 0
        for i, y in enumerate(ys):
            total += scroller.update(y is not None, y, start + i / fps)
        return total

    def test_hand_above_the_start_scrolls_up_and_below_down(self):
        up = self.run_frames(ScrollController(), [0.5] + [0.3] * 60)
        down = self.run_frames(ScrollController(), [0.5] + [0.7] * 60)
        self.assertGreater(up, 0)
        self.assertLess(down, 0)

    def test_still_hand_and_small_wobbles_do_not_scroll(self):
        wobble = [0.5 + (DEAD_ZONE * 0.6) * (1 if i % 2 else -1) for i in range(90)]
        self.assertEqual(self.run_frames(ScrollController(), wobble), 0)

    def test_holding_keeps_scrolling(self):
        s = ScrollController()
        first = self.run_frames(s, [0.5] + [0.3] * 30)
        second = self.run_frames(s, [0.3] * 30, start=31 / 30)
        self.assertGreater(first, 0)
        self.assertGreater(second, 0)

    def test_further_is_faster_only_when_height_sets_speed(self):
        near = self.run_frames(ScrollController(), [0.5] + [0.42] * 60)
        far = self.run_frames(ScrollController(), [0.5] + [0.2] * 60)
        self.assertGreater(far, near * 2)
        steady_near = self.run_frames(ScrollController(height_sets_speed=False), [0.5] + [0.42] * 60)
        steady_far = self.run_frames(ScrollController(height_sets_speed=False), [0.5] + [0.2] * 60)
        self.assertLess(abs(steady_far - steady_near), WHEEL_DELTA)

    def test_speed_setting(self):
        slow = self.run_frames(ScrollController("slow"), [0.5] + [0.3] * 60)
        fast = self.run_frames(ScrollController("fast"), [0.5] + [0.3] * 60)
        self.assertGreater(fast, slow * 2)

    def test_letting_go_stops_and_the_next_hold_recentres(self):
        s = ScrollController()
        self.run_frames(s, [0.5] + [0.3] * 20)
        self.assertEqual(s.update(False, None, 1.0), 0)
        self.assertFalse(s.active)
        # Starting again high up is the new centre, so it doesn't scroll.
        self.assertEqual(self.run_frames(s, [0.3] * 30, start=2.0), 0)

    def test_jitter_is_smoothed(self):
        import random
        random.seed(5)
        ys = [0.5] + [0.3 + random.uniform(-0.03, 0.03) for _ in range(90)]
        amounts = []
        s = ScrollController()
        for i, y in enumerate(ys):
            amounts.append(s.update(True, y, i / 30))
        self.assertTrue(all(a >= 0 for a in amounts))   # never flips direction


class VideoAndMediaTests(unittest.TestCase):

    def controller(self, foreground="chrome.exe"):
        from backend.automation.browse_media import BrowseMediaController
        self.api = FakeWinApi(foreground)
        return BrowseMediaController(DesktopInput(self.api))

    def test_youtube_keys_in_a_browser(self):
        c = self.controller("chrome.exe")
        for command, key in (("video_play_pause", "k"), ("video_forward_10", "l"),
                             ("video_back_10", "j"), ("video_forward_5", "right"),
                             ("video_back_5", "left")):
            c.execute(command)
            self.assertEqual(self.api.keys[-1], [VK[key]], command)

    def test_letters_are_never_typed_outside_a_browser(self):
        from backend.automation.browse_media import NotInBrowser
        for app in ("winword.exe", "notepad.exe", "slack.exe", ""):
            c = self.controller(app)
            with self.assertRaises(NotInBrowser):
                c.execute("video_play_pause")
            self.assertEqual(self.api.keys, [], app)

    def test_media_keys_work_with_any_app_in_front(self):
        c = self.controller("spotify.exe")
        c.execute("play_pause")
        c.execute("next")
        c.execute("previous")
        self.assertEqual(self.api.keys, [[0xB3], [0xB0], [0xB1]])

    def test_unknown_command(self):
        with self.assertRaises(ValueError):
            self.controller().execute("explode")

    def test_every_studio_action_maps_to_a_command(self):
        from backend.automation import browse_media as B
        for code in B.ACTIONS:
            name, action, value = B.PROFILE_ACTIONS[code]
            if action == "Scroll":
                continue
            self.assertIn(value, B.COMMANDS, code)

    def test_runner_uses_the_controller(self):
        from backend.automation.browse_media import BrowseMediaController
        from backend.automation.flow_manager import FlowManager
        runner = FlowManager.__new__(FlowManager)
        api = FakeWinApi("firefox.exe")
        runner.browse_media = BrowseMediaController(DesktopInput(api))
        runner.execute_custom_event({"name": "Play", "action": "Browser", "value": "video_play_pause"})
        runner.execute_custom_event({"name": "Next", "action": "Media", "value": "next"})
        self.assertEqual(api.keys, [[VK["k"]], [0xB0]])


class TabTests(unittest.TestCase):

    def test_tab_shortcuts_in_a_browser(self):
        from backend.automation.browse_media import BrowseMediaController
        api = FakeWinApi("brave.exe")
        c = BrowseMediaController(DesktopInput(api))
        for command in ("tab_close", "tab_reopen", "tab_next", "tab_previous"):
            c.execute(command)
        self.assertEqual(api.keys, [
            [0x11, ord("W")],
            [0x11, 0x10, ord("T")],
            [0x11, 0x09],
            [0x11, 0x10, 0x09],
        ])

    def test_tabs_are_never_closed_in_other_apps(self):
        from backend.automation.browse_media import BrowseMediaController, NotInBrowser
        api = FakeWinApi("code.exe")   # Ctrl+W would close a file in VS Code
        with self.assertRaises(NotInBrowser):
            BrowseMediaController(DesktopInput(api)).execute("tab_close")
        self.assertEqual(api.keys, [])

    def test_closing_a_tab_needs_a_hold(self):
        from backend.automation.events import profile_events
        events = profile_events({"gesture_map": {"✊ Fist": "browse_tab_close",
                                                 "☝️ Pointing Up": "browse_tab_next"}})
        close = next(e for e in events if e["value"] == "tab_close")
        nxt = next(e for e in events if e["value"] == "tab_next")
        self.assertEqual(close["hold_seconds"], 1.0)
        self.assertNotIn("hold_seconds", nxt)


class HoldTrackerTests(unittest.TestCase):

    def tracker(self):
        from backend.gestures.hold import HoldTracker
        return HoldTracker([
            {"name": "Close tab", "gesture": "✊ Fist", "action": "Browser",
             "value": "tab_close", "hold_seconds": 1.0},
            {"name": "Next tab", "gesture": "☝️ Pointing Up", "action": "Browser",
             "value": "tab_next"},
        ])

    def test_fires_once_after_the_full_hold_with_progress(self):
        t = self.tracker()
        progress, fired = [], []
        for i in range(30):                       # 1.45 s at 20 fps
            for name, p, event in t.update("✊ Fist", i * 0.05):
                progress.append(p)
                if event:
                    fired.append(event["value"])
        self.assertEqual(fired, ["tab_close"])
        self.assertEqual(progress[0], 0.0)
        self.assertTrue(all(a <= b for a, b in zip(progress, progress[1:])))

    def test_letting_go_early_cancels(self):
        t = self.tracker()
        for i in range(10):                       # 0.45 s
            t.update("✊ Fist", i * 0.05)
        updates = t.update(None, 0.5)
        self.assertEqual(updates, [("Close tab", 0.0, None)])
        # Holding again starts from zero.
        self.assertEqual(t.update("✊ Fist", 0.6)[0][1], 0.0)

    def test_must_release_before_firing_again(self):
        t = self.tracker()
        fired = [e for i in range(60) for _, _, e in t.update("✊ Fist", i * 0.05) if e]
        self.assertEqual(len(fired), 1)

    def test_ordinary_poses_are_ignored(self):
        self.assertEqual(self.tracker().update("☝️ Pointing Up", 0.0), [])


class ProfileTests(unittest.TestCase):

    def test_default_profile_and_events(self):
        import json
        import os
        from backend.automation.events import profile_events
        from backend.paths import DEFAULT_CONFIG_DIR

        with open(os.path.join(DEFAULT_CONFIG_DIR, "profiles", "browse.json"), encoding="utf-8") as f:
            profile = json.load(f)
        events = profile_events(profile)
        scroll = [e for e in events if e["action"] == "Scroll"]
        self.assertEqual([e["gesture"] for e in scroll], ["✌️ Peace"])

    def test_scroll_never_runs_as_a_one_off(self):
        from backend.automation.flow_manager import FlowManager
        # The runner accepts it and does nothing (the worker scrolls live).
        FlowManager.execute_custom_event(
            FlowManager.__new__(FlowManager), {"name": "Scroll", "action": "Scroll", "value": "hold"}
        )


if __name__ == "__main__":
    unittest.main()


try:
    import cv2  # noqa: F401
    import PySide6  # noqa: F401
    HAVE_WORKER = True
except ImportError:  # CI's unit-test job installs only the standard library
    HAVE_WORKER = False


@unittest.skipUnless(HAVE_WORKER, "cv2 / PySide6 not installed")
class WorkerScrollTests(unittest.TestCase):

    def setUp(self):
        import os
        import tempfile
        from unittest import mock
        self.tmp = tempfile.TemporaryDirectory()
        env = mock.patch.dict(os.environ, {"WIELD_DATA_DIR": self.tmp.name})
        env.start()
        self.addCleanup(env.stop)
        self.addCleanup(self.tmp.cleanup)

        from backend.gestures.gesture_worker import GestureWorker
        self.worker = GestureWorker("browse")
        self.scrolls = []
        self.worker.scroll_requested.connect(lambda amount, d: self.scrolls.append(amount))

    def hand_at(self, y):
        class P:
            def __init__(self, y):
                self.x, self.y = 0.5, y
        self.worker.recognizer.last_image_landmarks = [P(y)] * 21

    def test_holding_the_scroll_pose_scrolls_and_nothing_else_fires(self):
        events = []
        self.worker.custom_event_detected.connect(events.append)
        self.assertIn("✌️ Peace", self.worker.scroll_poses)
        self.assertFalse(any(e["action"] == "Scroll" for e in self.worker.events))

        self.hand_at(0.5)
        self.assertTrue(self.worker._scroll("✌️ Peace", 0.9, 0.0))
        for i in range(1, 40):
            self.hand_at(0.3)
            self.worker._scroll("✌️ Peace", 0.9, i / 30)
        self.assertGreater(sum(a for a in self.scrolls if a), 0)
        self.assertEqual(events, [])

    def test_close_tab_only_after_holding_the_fist(self):
        events, progress = [], []
        self.worker.custom_event_detected.connect(events.append)
        self.worker.hold_progress.connect(lambda name, p: progress.append(p))

        # The fist being recognised doesn't close the tab straight away...
        self.worker._trigger("✊ Fist")
        self.assertEqual(events, [])

        # ...holding it for a second does, with the bar filling up.
        for i in range(25):
            self.worker._update_holds("✊ Fist", 0.9, i * 0.05)
        self.assertEqual([e["value"] for e in events], ["tab_close"])
        self.assertGreater(len(progress), 5)

    def test_other_poses_are_not_scrolling(self):
        self.hand_at(0.3)
        self.assertFalse(self.worker._scroll("👍 Thumbs Up", 0.9, 0.0))
        self.assertEqual(self.scrolls, [])
