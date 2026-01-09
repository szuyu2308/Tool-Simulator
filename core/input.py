"""
IInputProvider and ITextProvider implementations
Client-pixel coordinate input with SendInput/PostMessage/ADB fallback
"""

from __future__ import annotations
from typing import Optional, List, Tuple, TYPE_CHECKING
from abc import ABC, abstractmethod
from enum import Enum
import ctypes
from ctypes import wintypes
import time
import random
import threading

from utils.logger import log

if TYPE_CHECKING:
    from core.emulator import ClientRect

# Import enums from models (single source of truth)
from core.models import ButtonType, HotKeyOrder

# Windows API structures and constants
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# Input constants
INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_WHEEL = 0x0800
MOUSEEVENTF_ABSOLUTE = 0x8000

KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004

# Virtual key codes
VK_CODES = {
    'BACKSPACE': 0x08, 'TAB': 0x09, 'ENTER': 0x0D, 'SHIFT': 0x10,
    'CTRL': 0x11, 'ALT': 0x12, 'PAUSE': 0x13, 'CAPSLOCK': 0x14,
    'ESCAPE': 0x1B, 'SPACE': 0x20, 'PAGEUP': 0x21, 'PAGEDOWN': 0x22,
    'END': 0x23, 'HOME': 0x24, 'LEFT': 0x25, 'UP': 0x26,
    'RIGHT': 0x27, 'DOWN': 0x28, 'INSERT': 0x2D, 'DELETE': 0x2E,
    'F1': 0x70, 'F2': 0x71, 'F3': 0x72, 'F4': 0x73, 'F5': 0x74,
    'F6': 0x75, 'F7': 0x76, 'F8': 0x77, 'F9': 0x78, 'F10': 0x79,
    'F11': 0x7A, 'F12': 0x7B, 'NUMLOCK': 0x90, 'SCROLL': 0x91,
    'LSHIFT': 0xA0, 'RSHIFT': 0xA1, 'LCTRL': 0xA2, 'RCTRL': 0xA3,
    'LALT': 0xA4, 'RALT': 0xA5,
}


def _get_vk_code(key: str) -> int:
    """Get virtual key code for key string (module-level for reuse)"""
    key_upper = key.upper()
    
    # Check special keys
    if key_upper in VK_CODES:
        return VK_CODES[key_upper]
    
    # Single character
    if len(key) == 1:
        return user32.VkKeyScanW(ord(key)) & 0xFF
    
    return 0


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))
    ]


class INPUT_UNION(ctypes.Union):
    _fields_ = [
        ("mi", MOUSEINPUT),
        ("ki", KEYBDINPUT)
    ]


class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", wintypes.DWORD),
        ("union", INPUT_UNION)
    ]


# Note: ButtonType and HotKeyOrder imported from core.models


class IInputProvider(ABC):
    """Abstract input provider interface"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        pass
    
    @abstractmethod
    def click(self, screen_x: int, screen_y: int, button: ButtonType,
              wheel_delta: int = 0) -> bool:
        """Perform click at screen coordinates"""
        pass
    
    @abstractmethod
    def keypress(self, key: str, repeat: int = 1, delay_ms: int = 100) -> bool:
        """Press key with optional repeat"""
        pass
    
    @abstractmethod
    def hotkey(self, keys: List[str], order: HotKeyOrder) -> bool:
        """Press hotkey combination"""
        pass


class SendInputProvider(IInputProvider):
    """SendInput-based input provider (primary, most reliable)"""
    
    @property
    def name(self) -> str:
        return "SendInput"
    
    def _get_screen_metrics(self) -> Tuple[int, int]:
        """Get screen size for absolute coordinates"""
        width = user32.GetSystemMetrics(0)  # SM_CXSCREEN
        height = user32.GetSystemMetrics(1)  # SM_CYSCREEN
        return width, height
    
    def _screen_to_absolute(self, x: int, y: int) -> Tuple[int, int]:
        """Convert screen coords to absolute (0-65535 range)"""
        width, height = self._get_screen_metrics()
        abs_x = int(x * 65536 / width)
        abs_y = int(y * 65536 / height)
        return abs_x, abs_y
    
    def click(self, screen_x: int, screen_y: int, button: ButtonType,
              wheel_delta: int = 0) -> bool:
        try:
            abs_x, abs_y = self._screen_to_absolute(screen_x, screen_y)
            
            # Move mouse
            move_input = INPUT()
            move_input.type = INPUT_MOUSE
            move_input.union.mi.dx = abs_x
            move_input.union.mi.dy = abs_y
            move_input.union.mi.dwFlags = MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE
            user32.SendInput(1, ctypes.byref(move_input), ctypes.sizeof(INPUT))
            
            time.sleep(0.01)  # Small delay for move
            
            # Determine button flags
            if button == ButtonType.LEFT:
                down_flag = MOUSEEVENTF_LEFTDOWN
                up_flag = MOUSEEVENTF_LEFTUP
            elif button == ButtonType.RIGHT:
                down_flag = MOUSEEVENTF_RIGHTDOWN
                up_flag = MOUSEEVENTF_RIGHTUP
            elif button == ButtonType.MIDDLE:
                down_flag = MOUSEEVENTF_MIDDLEDOWN
                up_flag = MOUSEEVENTF_MIDDLEUP
            elif button == ButtonType.DOUBLE:
                # Double click = two left clicks
                for _ in range(2):
                    self._do_click(MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP)
                    time.sleep(0.05)
                return True
            elif button in (ButtonType.WHEEL_UP, ButtonType.WHEEL_DOWN):
                return self._do_wheel(button, wheel_delta)
            else:
                return False
            
            return self._do_click(down_flag, up_flag)
            
        except Exception as e:
            log(f"[INPUT] SendInput click error: {e}")
            return False
    
    def _do_click(self, down_flag: int, up_flag: int) -> bool:
        """Perform single click (down + up)"""
        # Mouse down
        down_input = INPUT()
        down_input.type = INPUT_MOUSE
        down_input.union.mi.dwFlags = down_flag
        user32.SendInput(1, ctypes.byref(down_input), ctypes.sizeof(INPUT))
        
        time.sleep(0.02)
        
        # Mouse up
        up_input = INPUT()
        up_input.type = INPUT_MOUSE
        up_input.union.mi.dwFlags = up_flag
        user32.SendInput(1, ctypes.byref(up_input), ctypes.sizeof(INPUT))
        
        return True
    
    def _do_wheel(self, direction: ButtonType, delta: int = 0) -> bool:
        """Perform mouse wheel"""
        wheel_input = INPUT()
        wheel_input.type = INPUT_MOUSE
        wheel_input.union.mi.dwFlags = MOUSEEVENTF_WHEEL
        
        # Default delta is 120 (one notch)
        if delta == 0:
            delta = 120
        
        if direction == ButtonType.WHEEL_DOWN:
            delta = -delta
        
        wheel_input.union.mi.mouseData = delta
        user32.SendInput(1, ctypes.byref(wheel_input), ctypes.sizeof(INPUT))
        return True
    
    def keypress(self, key: str, repeat: int = 1, delay_ms: int = 100) -> bool:
        try:
            vk = _get_vk_code(key)
            if vk == 0:
                log(f"[INPUT] Unknown key: {key}")
                return False
            
            for i in range(repeat):
                # Key down
                down_input = INPUT()
                down_input.type = INPUT_KEYBOARD
                down_input.union.ki.wVk = vk
                user32.SendInput(1, ctypes.byref(down_input), ctypes.sizeof(INPUT))
                
                time.sleep(0.02)
                
                # Key up
                up_input = INPUT()
                up_input.type = INPUT_KEYBOARD
                up_input.union.ki.wVk = vk
                up_input.union.ki.dwFlags = KEYEVENTF_KEYUP
                user32.SendInput(1, ctypes.byref(up_input), ctypes.sizeof(INPUT))
                
                if i < repeat - 1:
                    time.sleep(delay_ms / 1000.0)
            
            return True
            
        except Exception as e:
            log(f"[INPUT] SendInput keypress error: {e}")
            return False
    
    def hotkey(self, keys: List[str], order: HotKeyOrder) -> bool:
        try:
            vk_codes = [_get_vk_code(k) for k in keys]
            if 0 in vk_codes:
                log(f"[INPUT] Unknown key in hotkey: {keys}")
                return False
            
            if order == HotKeyOrder.SIMULTANEOUS:
                # Press all down, then all up
                for vk in vk_codes:
                    down_input = INPUT()
                    down_input.type = INPUT_KEYBOARD
                    down_input.union.ki.wVk = vk
                    user32.SendInput(1, ctypes.byref(down_input), ctypes.sizeof(INPUT))
                    time.sleep(0.01)
                
                time.sleep(0.05)
                
                for vk in reversed(vk_codes):
                    up_input = INPUT()
                    up_input.type = INPUT_KEYBOARD
                    up_input.union.ki.wVk = vk
                    up_input.union.ki.dwFlags = KEYEVENTF_KEYUP
                    user32.SendInput(1, ctypes.byref(up_input), ctypes.sizeof(INPUT))
                    time.sleep(0.01)
            else:
                # Sequential: press and release each
                for vk in vk_codes:
                    down_input = INPUT()
                    down_input.type = INPUT_KEYBOARD
                    down_input.union.ki.wVk = vk
                    user32.SendInput(1, ctypes.byref(down_input), ctypes.sizeof(INPUT))
                    time.sleep(0.02)
                    
                    up_input = INPUT()
                    up_input.type = INPUT_KEYBOARD
                    up_input.union.ki.wVk = vk
                    up_input.union.ki.dwFlags = KEYEVENTF_KEYUP
                    user32.SendInput(1, ctypes.byref(up_input), ctypes.sizeof(INPUT))
                    time.sleep(0.05)
            
            return True
            
        except Exception as e:
            log(f"[INPUT] SendInput hotkey error: {e}")
            return False


class PostMessageProvider(IInputProvider):
    """PostMessage-based input (background, less reliable)"""
    
    WM_LBUTTONDOWN = 0x0201
    WM_LBUTTONUP = 0x0202
    WM_RBUTTONDOWN = 0x0204
    WM_RBUTTONUP = 0x0205
    WM_MBUTTONDOWN = 0x0207
    WM_MBUTTONUP = 0x0208
    WM_MOUSEWHEEL = 0x020A
    WM_KEYDOWN = 0x0100
    WM_KEYUP = 0x0101
    
    def __init__(self, hwnd: int):
        self.hwnd = hwnd
    
    @property
    def name(self) -> str:
        return "PostMessage"
    
    def click(self, client_x: int, client_y: int, button: ButtonType,
              wheel_delta: int = 0) -> bool:
        """Click using PostMessage (client coordinates)"""
        try:
            lparam = (client_y << 16) | (client_x & 0xFFFF)
            
            if button == ButtonType.LEFT:
                user32.PostMessageW(self.hwnd, self.WM_LBUTTONDOWN, 1, lparam)
                time.sleep(0.02)
                user32.PostMessageW(self.hwnd, self.WM_LBUTTONUP, 0, lparam)
            elif button == ButtonType.RIGHT:
                user32.PostMessageW(self.hwnd, self.WM_RBUTTONDOWN, 2, lparam)
                time.sleep(0.02)
                user32.PostMessageW(self.hwnd, self.WM_RBUTTONUP, 0, lparam)
            elif button == ButtonType.MIDDLE:
                user32.PostMessageW(self.hwnd, self.WM_MBUTTONDOWN, 16, lparam)
                time.sleep(0.02)
                user32.PostMessageW(self.hwnd, self.WM_MBUTTONUP, 0, lparam)
            elif button == ButtonType.DOUBLE:
                for _ in range(2):
                    user32.PostMessageW(self.hwnd, self.WM_LBUTTONDOWN, 1, lparam)
                    time.sleep(0.02)
                    user32.PostMessageW(self.hwnd, self.WM_LBUTTONUP, 0, lparam)
                    time.sleep(0.05)
            elif button in (ButtonType.WHEEL_UP, ButtonType.WHEEL_DOWN):
                delta = wheel_delta if wheel_delta else 120
                if button == ButtonType.WHEEL_DOWN:
                    delta = -delta
                wparam = (delta << 16)
                user32.PostMessageW(self.hwnd, self.WM_MOUSEWHEEL, wparam, lparam)
            
            return True
            
        except Exception as e:
            log(f"[INPUT] PostMessage click error: {e}")
            return False
    
    def keypress(self, key: str, repeat: int = 1, delay_ms: int = 100) -> bool:
        try:
            vk = _get_vk_code(key)  # Use module-level function
            if vk == 0:
                return False
            
            for i in range(repeat):
                user32.PostMessageW(self.hwnd, self.WM_KEYDOWN, vk, 0)
                time.sleep(0.02)
                user32.PostMessageW(self.hwnd, self.WM_KEYUP, vk, 0)
                
                if i < repeat - 1:
                    time.sleep(delay_ms / 1000.0)
            
            return True
            
        except Exception as e:
            log(f"[INPUT] PostMessage keypress error: {e}")
            return False
    
    def hotkey(self, keys: List[str], order: HotKeyOrder) -> bool:
        # PostMessage hotkey is unreliable, use sequential only
        for key in keys:
            self.keypress(key)
            time.sleep(0.05)
        return True


class ITextProvider(ABC):
    """Abstract text input provider"""
    
    @abstractmethod
    def paste_text(self, text: str, focus_x: int = None, focus_y: int = None) -> bool:
        pass
    
    @abstractmethod
    def type_text_humanize(self, text: str, cps_min: int, cps_max: int,
                           focus_x: int = None, focus_y: int = None) -> bool:
        pass


class ClipboardTextProvider(ITextProvider):
    """Clipboard paste text provider (primary)"""
    
    def __init__(self, input_provider: IInputProvider, hwnd: int):
        self.input = input_provider
        self.hwnd = hwnd
        self._lock = threading.Lock()
    
    def paste_text(self, text: str, focus_x: int = None, focus_y: int = None) -> bool:
        try:
            with self._lock:
                # Click to focus if coordinates provided
                if focus_x is not None and focus_y is not None:
                    self.input.click(focus_x, focus_y, ButtonType.LEFT)
                    time.sleep(0.1)
                
                # Copy to clipboard
                if not self._set_clipboard(text):
                    return False
                
                # Ctrl+V
                self.input.hotkey(["CTRL", "V"], HotKeyOrder.SIMULTANEOUS)
                time.sleep(0.1)
                
                return True
                
        except Exception as e:
            log(f"[TEXT] Clipboard paste error: {e}")
            return False
    
    def _set_clipboard(self, text: str) -> bool:
        """Set clipboard content"""
        try:
            user32.OpenClipboard(0)
            user32.EmptyClipboard()
            
            # Encode as UTF-16
            data = text.encode('utf-16-le') + b'\x00\x00'
            h_global = kernel32.GlobalAlloc(0x0042, len(data))  # GMEM_MOVEABLE | GMEM_ZEROINIT
            
            ptr = kernel32.GlobalLock(h_global)
            ctypes.memmove(ptr, data, len(data))
            kernel32.GlobalUnlock(h_global)
            
            user32.SetClipboardData(13, h_global)  # CF_UNICODETEXT
            user32.CloseClipboard()
            
            return True
            
        except Exception as e:
            log(f"[TEXT] Set clipboard error: {e}")
            try:
                user32.CloseClipboard()
            except:
                pass
            return False
    
    def type_text_humanize(self, text: str, cps_min: int, cps_max: int,
                           focus_x: int = None, focus_y: int = None) -> bool:
        try:
            # Click to focus if coordinates provided
            if focus_x is not None and focus_y is not None:
                self.input.click(focus_x, focus_y, ButtonType.LEFT)
                time.sleep(0.1)
            
            # Type each character with random delay
            for char in text:
                # Send character via SendInput Unicode
                self._send_unicode_char(char)
                
                # Random delay based on CPS
                delay = 1.0 / random.uniform(cps_min, cps_max)
                time.sleep(delay)
            
            return True
            
        except Exception as e:
            log(f"[TEXT] Humanize type error: {e}")
            return False
    
    def _send_unicode_char(self, char: str):
        """Send single unicode character"""
        # Key down
        down_input = INPUT()
        down_input.type = INPUT_KEYBOARD
        down_input.union.ki.wVk = 0
        down_input.union.ki.wScan = ord(char)
        down_input.union.ki.dwFlags = KEYEVENTF_UNICODE
        user32.SendInput(1, ctypes.byref(down_input), ctypes.sizeof(INPUT))
        
        # Key up
        up_input = INPUT()
        up_input.type = INPUT_KEYBOARD
        up_input.union.ki.wVk = 0
        up_input.union.ki.wScan = ord(char)
        up_input.union.ki.dwFlags = KEYEVENTF_UNICODE | KEYEVENTF_KEYUP
        user32.SendInput(1, ctypes.byref(up_input), ctypes.sizeof(INPUT))


class ADBTextProvider(ITextProvider):
    """ADB text input provider (fallback)"""
    
    def __init__(self, adb_manager, adb_serial: str):
        self.adb = adb_manager
        self.serial = adb_serial
    
    def paste_text(self, text: str, focus_x: int = None, focus_y: int = None) -> bool:
        try:
            if not self.serial:
                return False
            
            # ADB input text (note: limited Unicode support)
            # Escape special characters
            escaped = text.replace("'", "\\'").replace('"', '\\"').replace(' ', '%s')
            cmd = f"input text '{escaped}'"
            
            return self.adb.shell(self.serial, cmd)
            
        except Exception as e:
            log(f"[TEXT] ADB paste error: {e}")
            return False
    
    def type_text_humanize(self, text: str, cps_min: int, cps_max: int,
                           focus_x: int = None, focus_y: int = None) -> bool:
        # ADB doesn't support humanize, fall back to paste
        return self.paste_text(text, focus_x, focus_y)


class InputManager:
    """
    Manages input providers for an emulator instance.
    Handles client → screen coordinate conversion.
    """
    
    def __init__(self, hwnd: int, client_rect: 'ClientRect', adb_manager=None, adb_serial: str = None):
        self.hwnd = hwnd
        self.client_rect = client_rect
        self.adb_manager = adb_manager
        self.adb_serial = adb_serial
        
        # Initialize providers
        self.send_input = SendInputProvider()
        self.post_message = PostMessageProvider(hwnd)
        self.clipboard_text = ClipboardTextProvider(self.send_input, hwnd)
        
        if adb_manager and adb_serial:
            self.adb_text = ADBTextProvider(adb_manager, adb_serial)
        else:
            self.adb_text = None
    
    def click(self, client_x: int, client_y: int, button: ButtonType,
              humanize_delay_min: int = 50, humanize_delay_max: int = 200,
              wheel_delta: int = 0) -> bool:
        """
        Click at client coordinates with optional humanization.
        Converts client → screen coordinates automatically.
        """
        # Validate bounds
        if not self.client_rect.contains(client_x, client_y):
            log(f"[INPUT] Click out of bounds: ({client_x}, {client_y})")
            return False
        
        # Convert to screen coordinates
        screen_x, screen_y = self.client_rect.client_to_screen(client_x, client_y)
        
        # Add humanize jitter
        if humanize_delay_max > 0:
            jitter_x = random.randint(-2, 2)
            jitter_y = random.randint(-2, 2)
            screen_x += jitter_x
            screen_y += jitter_y
        
        # Random delay before click
        delay = random.uniform(humanize_delay_min / 1000.0, humanize_delay_max / 1000.0)
        time.sleep(delay)
        
        # Use SendInput (primary)
        return self.send_input.click(screen_x, screen_y, button, wheel_delta)
    
    def keypress(self, key: str, repeat: int = 1, delay_ms: int = 100) -> bool:
        """Press key with repeat"""
        return self.send_input.keypress(key, repeat, delay_ms)
    
    def hotkey(self, keys: List[str], order: HotKeyOrder) -> bool:
        """Press hotkey combination"""
        return self.send_input.hotkey(keys, order)
    
    def paste_text(self, text: str, focus_x: int = None, focus_y: int = None) -> bool:
        """Paste text with optional focus click (client coords)"""
        # Convert focus coords to screen if provided
        if focus_x is not None and focus_y is not None:
            screen_x, screen_y = self.client_rect.client_to_screen(focus_x, focus_y)
        else:
            screen_x, screen_y = None, None
        
        # Try clipboard first
        if self.clipboard_text.paste_text(text, screen_x, screen_y):
            return True
        
        # Fallback to ADB
        if self.adb_text:
            return self.adb_text.paste_text(text, focus_x, focus_y)
        
        return False
    
    def type_text_humanize(self, text: str, cps_min: int = 10, cps_max: int = 30,
                           focus_x: int = None, focus_y: int = None) -> bool:
        """Type text with humanized delays (client coords for focus)"""
        # Convert focus coords to screen if provided
        if focus_x is not None and focus_y is not None:
            screen_x, screen_y = self.client_rect.client_to_screen(focus_x, focus_y)
        else:
            screen_x, screen_y = None, None
        
        return self.clipboard_text.type_text_humanize(text, cps_min, cps_max, screen_x, screen_y)
