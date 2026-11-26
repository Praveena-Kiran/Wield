"""
Real keyboard / mouse-wheel input on Windows, and which app is in front.

    inp = DesktopInput()
    inp.foreground_process()     # "chrome.exe", or "" if unknown
    inp.browser_in_front()       # True for Chrome, Edge, Firefox, Brave ...
    inp.scroll(240)              # mouse wheel: + up, - down (120 = one notch)
    inp.press(["ctrl", "w"])     # a key combination
    inp.media("play_pause")      # Windows media keys (work in the background)
    inp.volume(+5)               # volume keys: 5 steps up (each about 2%)
    inp.lock()                   # lock the computer
    inp.move_to(0.5, 0.5)        # pointer to the middle of the main screen
    inp.button("left", True)     # left button down (False = up)
    inp.click("right")           # a right click ("left", "right"; double=True)
    inp.type_digits(12)          # type "12", one key at a time
    inp.clipboard_text()         # what's on the clipboard ("" if nothing)

Everything goes through SendInput (ctypes), the same path as a real
keyboard and mouse, so apps can't tell the difference. The Windows calls
live in WinApi; tests pass a fake instead (see tests/test_browse_media.py).
On other systems every method raises InputUnavailable.
"""

import ctypes
import os
import platform


class InputUnavailable(RuntimeError):
    pass


BROWSER_PROCESSES = {
    "chrome.exe",
    "msedge.exe",
    "firefox.exe",
    "brave.exe",
}

WHEEL_DELTA = 120   # one notch of a normal mouse wheel

# Virtual-key codes (winuser.h).
VK = {
    "backspace": 0x08, "tab": 0x09, "enter": 0x0D, "shift": 0x10, "ctrl": 0x11,
    "alt": 0x12, "win": 0x5B, "esc": 0x1B, "space": 0x20, "pageup": 0x21, "pagedown": 0x22,
    "end": 0x23, "home": 0x24, "left": 0x25, "up": 0x26, "right": 0x27,
    "down": 0x28, "media_next": 0xB0, "media_previous": 0xB1,
    "media_stop": 0xB2, "media_play_pause": 0xB3,
    "volume_mute": 0xAD, "volume_down": 0xAE, "volume_up": 0xAF,
    "f11": 0x7A,
}
VK.update({chr(c).lower(): c for c in range(ord("A"), ord("Z") + 1)})
VK.update({str(d): 0x30 + d for d in range(10)})

# Keys that need the "extended" flag to be read correctly.
EXTENDED = {VK[k] for k in ("win", "left", "up", "right", "down", "pageup", "pagedown",
                            "home", "end", "media_next", "media_previous",
                            "media_stop", "media_play_pause",
                            "volume_mute", "volume_down", "volume_up")}

MEDIA_KEYS = {
    "play_pause": "media_play_pause",
    "next": "media_next",
    "previous": "media_previous",
    "stop": "media_stop",
    "mute": "volume_mute",
}


def is_browser(process_name):
    return (process_name or "").strip().lower() in BROWSER_PROCESSES


def key_codes(keys):
    """["ctrl", "W"] -> [0x11, 0x57]; ValueError for an unknown key."""
    codes = []
    for key in keys:
        code = VK.get(str(key).strip().lower())
        if code is None:
            raise ValueError(f'Unknown key "{key}".')
        codes.append(code)
    return codes


# ---------------------------------------------------------------------
# WINDOWS (ctypes)
# ---------------------------------------------------------------------

class WinApi:
    """The few Windows calls Wield needs. Only built on Windows."""

    INPUT_MOUSE = 0
    INPUT_KEYBOARD = 1
    KEYEVENTF_EXTENDEDKEY = 0x0001
    KEYEVENTF_KEYUP = 0x0002
    MOUSEEVENTF_WHEEL = 0x0800
    MOUSEEVENTF_MOVE = 0x0001
    MOUSEEVENTF_ABSOLUTE = 0x8000
    MOUSE_BUTTONS = {          # (down, up)
        "left": (0x0002, 0x0004),
        "right": (0x0008, 0x0010),
    }
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

    def __init__(self):
        from ctypes import wintypes

        self.user32 = ctypes.WinDLL("user32", use_last_error=True)
        self.kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        ulong_ptr = ctypes.c_size_t

        class MOUSEINPUT(ctypes.Structure):
            _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                        ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                        ("time", wintypes.DWORD), ("dwExtraInfo", ulong_ptr)]

        class KEYBDINPUT(ctypes.Structure):
            _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                        ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                        ("dwExtraInfo", ulong_ptr)]

        class HARDWAREINPUT(ctypes.Structure):
            _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD),
                        ("wParamH", wintypes.WORD)]

        class _U(ctypes.Union):
            _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]

        class INPUT(ctypes.Structure):
            _anonymous_ = ("u",)
            _fields_ = [("type", wintypes.DWORD), ("u", _U)]

        self.INPUT = INPUT
        self.user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
        self.user32.SendInput.restype = wintypes.UINT
        self.user32.GetForegroundWindow.restype = wintypes.HWND
        self.user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
        self.kernel32.OpenProcess.restype = wintypes.HANDLE
        self.kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        self.kernel32.QueryFullProcessImageNameW.argtypes = (
            wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD))
        self.kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
        self._wintypes = wintypes

    def _send(self, inputs):
        array = (self.INPUT * len(inputs))(*inputs)
        sent = self.user32.SendInput(len(inputs), array, ctypes.sizeof(self.INPUT))
        if sent != len(inputs):
            raise InputUnavailable(
                "Windows blocked the input. If the app in front runs as "
                "administrator, run Wield as administrator too."
            )

    def send_keys(self, codes):
        """Press the keys in order, then release them in reverse."""
        def key(code, up):
            flags = (self.KEYEVENTF_KEYUP if up else 0) | (
                self.KEYEVENTF_EXTENDEDKEY if code in EXTENDED else 0)
            event = self.INPUT(type=self.INPUT_KEYBOARD)
            event.ki.wVk = code
            event.ki.dwFlags = flags
            return event

        self._send([key(c, False) for c in codes] + [key(c, True) for c in reversed(codes)])

    def _wheel_event(self, amount):
        event = self.INPUT(type=self.INPUT_MOUSE)
        event.mi.mouseData = ctypes.c_uint32(int(amount)).value   # signed in a DWORD
        event.mi.dwFlags = self.MOUSEEVENTF_WHEEL
        return event

    def send_wheel(self, amount, ctrl=False):
        """Turn the wheel; with ctrl=True, Ctrl is held (zoom in most apps)."""
        if not ctrl:
            self._send([self._wheel_event(amount)])
            return
        down = self.INPUT(type=self.INPUT_KEYBOARD)
        down.ki.wVk = VK["ctrl"]
        up = self.INPUT(type=self.INPUT_KEYBOARD)
        up.ki.wVk = VK["ctrl"]
        up.ki.dwFlags = self.KEYEVENTF_KEYUP
        self._send([down, self._wheel_event(amount), up])

    def send_move(self, x, y):
        """Pointer to (x, y), 0..1 across the main screen."""
        event = self.INPUT(type=self.INPUT_MOUSE)
        event.mi.dx = int(min(max(x, 0.0), 1.0) * 65535)
        event.mi.dy = int(min(max(y, 0.0), 1.0) * 65535)
        event.mi.dwFlags = self.MOUSEEVENTF_MOVE | self.MOUSEEVENTF_ABSOLUTE
        self._send([event])

    def send_button(self, button, down):
        event = self.INPUT(type=self.INPUT_MOUSE)
        event.mi.dwFlags = self.MOUSE_BUTTONS[button][0 if down else 1]
        self._send([event])

    def lock_workstation(self):
        if not self.user32.LockWorkStation():
            raise InputUnavailable("Windows didn't lock the computer.")

    def foreground_process(self):
        wintypes = self._wintypes
        hwnd = self.user32.GetForegroundWindow()
        if not hwnd:
            return ""
        pid = wintypes.DWORD()
        self.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        handle = self.kernel32.OpenProcess(self.PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
        if not handle:
            return ""
        try:
            size = wintypes.DWORD(1024)
            buffer = ctypes.create_unicode_buffer(size.value)
            if not self.kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
                return ""
            return os.path.basename(buffer.value).lower()
        finally:
            self.kernel32.CloseHandle(handle)


# ---------------------------------------------------------------------
# PUBLIC
# ---------------------------------------------------------------------

class DesktopInput:

    def __init__(self, api=None):
        self._api = api

    @property
    def api(self):
        if self._api is None:
            if platform.system() != "Windows":
                raise InputUnavailable("Scrolling, media and tab control work on Windows only.")
            self._api = WinApi()
        return self._api

    def foreground_process(self):
        try:
            return self.api.foreground_process() or ""
        except InputUnavailable:
            return ""

    def browser_in_front(self):
        return is_browser(self.foreground_process())

    def scroll(self, amount):
        amount = int(amount)
        if amount:
            self.api.send_wheel(amount)

    def press(self, keys):
        self.api.send_keys(key_codes(keys))

    def type_digits(self, number):
        for digit in str(int(number)):
            self.api.send_keys(key_codes([digit]))

    def clipboard_text(self):
        try:
            from PySide6.QtGui import QGuiApplication
            return QGuiApplication.clipboard().text() or ""
        except Exception:  # noqa: BLE001 - no Qt / no clipboard
            return ""

    def set_clipboard_text(self, text):
        try:
            from PySide6.QtGui import QGuiApplication
            QGuiApplication.clipboard().setText(text or "")
        except Exception:  # noqa: BLE001
            pass

    def zoom(self, steps):
        """Zoom in (+) or out (-) with Ctrl + mouse wheel: browsers, PDFs, Word."""
        steps = int(steps)
        if steps:
            self.api.send_wheel(steps * WHEEL_DELTA, ctrl=True)

    def volume(self, steps):
        """Press volume up (+) or down (-) this many times (about 2% each)."""
        steps = int(steps)
        if steps:
            key = VK["volume_up"] if steps > 0 else VK["volume_down"]
            for _ in range(min(abs(steps), 50)):
                self.api.send_keys([key])

    def move_to(self, x, y):
        self.api.send_move(x, y)

    def button(self, button, down):
        if button not in ("left", "right"):
            raise ValueError(f'Unknown mouse button "{button}".')
        self.api.send_button(button, down)

    def click(self, button="left", double=False):
        for _ in range(2 if double else 1):
            self.button(button, True)
            self.button(button, False)

    def lock(self):
        """Lock the computer (like Win+L, which apps can't send)."""
        self.api.lock_workstation()

    def media(self, name):
        key = MEDIA_KEYS.get(name)
        if key is None:
            raise ValueError(f'Unknown media key "{name}".')
        self.api.send_keys([VK[key]])
