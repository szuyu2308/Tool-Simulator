# AI GOVERNANCE:
# Apply auditor-router
# This is a CODE change

"""
Macro Playback Engine
Replays macro actions using SendInput with timing control
"""

from __future__ import annotations
from typing import Optional, List, Callable, Tuple, Dict, Any
from dataclasses import dataclass
from enum import Enum
import ctypes
from ctypes import wintypes
import time
import threading
import random
import math

from .models import (
    Macro, MacroAction, MacroActionType, MacroSettings, MacroOnError,
    MouseMoveAction, MouseClickAction, MouseDragAction, MouseScrollAction,
    KeyPressAction, HotkeyAction, TextInputAction, WaitTimeAction,
    WaitPixelAction, WaitImageAction, WaitWindowAction, IfThenElseAction,
    WindowFocusAction, WindowMoveResizeAction,
    MouseButton, MouseCurve, KeyPressMode, HotkeyOrder, TextInputMode,
    WindowMatch
)
from .recorder import WindowUtils

from utils.logger import log

# Windows API
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

SW_RESTORE = 9
SW_SHOW = 5


# ==================== INPUT STRUCTURES ====================

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


# Virtual key codes
VK_CODES = {
    'backspace': 0x08, 'tab': 0x09, 'enter': 0x0D, 'shift': 0x10,
    'ctrl': 0x11, 'alt': 0x12, 'pause': 0x13, 'capslock': 0x14,
    'escape': 0x1B, 'space': 0x20, 'pageup': 0x21, 'pagedown': 0x22,
    'end': 0x23, 'home': 0x24, 'left': 0x25, 'up': 0x26,
    'right': 0x27, 'down': 0x28, 'insert': 0x2D, 'delete': 0x2E,
    'f1': 0x70, 'f2': 0x71, 'f3': 0x72, 'f4': 0x73, 'f5': 0x74,
    'f6': 0x75, 'f7': 0x76, 'f8': 0x77, 'f9': 0x78, 'f10': 0x79,
    'f11': 0x7A, 'f12': 0x7B,
}


def get_vk_code(key: str) -> int:
    """Get virtual key code for key string"""
    key_lower = key.lower()
    
    if key_lower in VK_CODES:
        return VK_CODES[key_lower]
    
    if len(key) == 1:
        return user32.VkKeyScanW(ord(key)) & 0xFF
    
    return 0


# ==================== PLAYBACK STATE ====================

class PlaybackState(Enum):
    IDLE = "idle"
    PLAYING = "playing"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class PlaybackContext:
    """Context for macro playback"""
    hwnd: Optional[int] = None  # Target window handle
    client_rect: Optional[Tuple[int, int, int, int]] = None  # (x, y, w, h)
    speed_multiplier: float = 1.0
    current_action_idx: int = 0
    start_time: float = 0.0
    variables: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.variables is None:
            self.variables = {}


# ==================== PLAYBACK ENGINE ====================

class MacroPlayer:
    """
    Macro Playback Engine
    Plays back recorded macro actions with timing and error handling
    """
    
    def __init__(self):
        self._state = PlaybackState.IDLE
        self._macro: Optional[Macro] = None
        self._context: Optional[PlaybackContext] = None
        
        # Thread management
        self._playback_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._pause_event.set()  # Not paused initially
        
        # Callbacks
        self._on_state_change: Optional[Callable[[PlaybackState], None]] = None
        self._on_action_start: Optional[Callable[[int, MacroAction], None]] = None
        self._on_action_complete: Optional[Callable[[int, MacroAction, bool], None]] = None
        self._on_error: Optional[Callable[[int, MacroAction, Exception], None]] = None
    
    @property
    def state(self) -> PlaybackState:
        return self._state
    
    @property
    def is_playing(self) -> bool:
        return self._state == PlaybackState.PLAYING
    
    @property
    def current_action_index(self) -> int:
        if self._context:
            return self._context.current_action_idx
        return 0
    
    def set_callbacks(self,
                      on_state_change: Callable[[PlaybackState], None] = None,
                      on_action_start: Callable[[int, MacroAction], None] = None,
                      on_action_complete: Callable[[int, MacroAction, bool], None] = None,
                      on_error: Callable[[int, MacroAction, Exception], None] = None):
        """Set playback callbacks"""
        self._on_state_change = on_state_change
        self._on_action_start = on_action_start
        self._on_action_complete = on_action_complete
        self._on_error = on_error
    
    def play(self, macro: Macro, hwnd: Optional[int] = None, speed: float = 1.0):
        """
        Start macro playback
        
        Args:
            macro: Macro to play
            hwnd: Target window handle (optional)
            speed: Playback speed multiplier
        """
        if self._state == PlaybackState.PLAYING:
            return
        
        self._macro = macro
        self._stop_event.clear()
        self._pause_event.set()
        
        # Resolve target window if not provided
        if hwnd is None and macro.target.window_match.title_contains:
            windows = WindowUtils.find_windows_by_match(
                title_contains=macro.target.window_match.title_contains,
                class_name=macro.target.window_match.class_name,
                process_name=macro.target.window_match.process_name
            )
            if windows:
                hwnd = windows[0]
        
        # Get client rect if we have a window
        client_rect = None
        if hwnd:
            client_rect = WindowUtils.get_client_rect(hwnd)
        
        # Create context
        self._context = PlaybackContext(
            hwnd=hwnd,
            client_rect=client_rect,
            speed_multiplier=speed * macro.settings.play_speed_multiplier,
            start_time=time.perf_counter()
        )
        
        # Start playback thread
        self._playback_thread = threading.Thread(target=self._playback_loop, daemon=True)
        self._playback_thread.start()
        
        self._set_state(PlaybackState.PLAYING)
        log(f"[PLAYER] Playback started: {macro.name} ({len(macro.actions)} actions)")
    
    def stop(self):
        """Stop playback"""
        if self._state == PlaybackState.IDLE:
            return
        
        self._stop_event.set()
        self._pause_event.set()  # Unpause to allow thread to exit
        
        if self._playback_thread:
            self._playback_thread.join(timeout=2.0)
            self._playback_thread = None
        
        self._set_state(PlaybackState.STOPPED)
        log("[PLAYER] Playback stopped")
    
    def pause(self):
        """Pause playback"""
        if self._state != PlaybackState.PLAYING:
            return
        
        self._pause_event.clear()
        self._set_state(PlaybackState.PAUSED)
        log("[PLAYER] Playback paused")
    
    def resume(self):
        """Resume playback"""
        if self._state != PlaybackState.PAUSED:
            return
        
        self._pause_event.set()
        self._set_state(PlaybackState.PLAYING)
        log("[PLAYER] Playback resumed")
    
    def toggle_pause(self):
        """Toggle pause state"""
        if self._state == PlaybackState.PLAYING:
            self.pause()
        elif self._state == PlaybackState.PAUSED:
            self.resume()
    
    def _set_state(self, state: PlaybackState):
        """Set state and notify callback"""
        self._state = state
        if self._on_state_change:
            self._on_state_change(state)
    
    def _playback_loop(self):
        """Main playback loop"""
        if not self._macro or not self._context:
            return
        
        actions = self._macro.actions
        last_t_ms = 0
        
        for idx, action in enumerate(actions):
            # Check stop
            if self._stop_event.is_set():
                break
            
            # Wait for pause to clear
            self._pause_event.wait()
            
            if self._stop_event.is_set():
                break
            
            # Skip disabled actions
            if not action.enabled:
                continue
            
            self._context.current_action_idx = idx
            
            # Calculate delay from last action
            if action.t_ms > last_t_ms:
                delay_ms = action.t_ms - last_t_ms
                scaled_delay = delay_ms / self._context.speed_multiplier
                
                if scaled_delay > 0:
                    # Interruptible sleep
                    self._interruptible_sleep(scaled_delay / 1000.0)
                    
                    if self._stop_event.is_set():
                        break
            
            last_t_ms = action.t_ms
            
            # Execute action
            if self._on_action_start:
                self._on_action_start(idx, action)
            
            success = self._execute_action(action)
            
            if self._on_action_complete:
                self._on_action_complete(idx, action, success)
            
            if not success:
                # Handle error based on action/macro settings
                on_error = action.on_error
                if on_error == MacroOnError.INHERIT:
                    on_error = self._macro.settings.default_on_error
                
                if on_error == MacroOnError.STOP:
                    self._set_state(PlaybackState.ERROR)
                    break
                elif on_error == MacroOnError.PAUSE:
                    self.pause()
                # SKIP continues to next action
        
        # Playback complete
        if self._state == PlaybackState.PLAYING:
            self._set_state(PlaybackState.IDLE)
            log("[PLAYER] Playback completed")
    
    def _interruptible_sleep(self, seconds: float):
        """Sleep that can be interrupted by stop event"""
        interval = 0.05  # 50ms check interval
        elapsed = 0.0
        
        while elapsed < seconds and not self._stop_event.is_set():
            self._pause_event.wait()  # Wait if paused
            
            if self._stop_event.is_set():
                break
            
            remaining = seconds - elapsed
            sleep_time = min(interval, remaining)
            time.sleep(sleep_time)
            elapsed += sleep_time
    
    def _execute_action(self, action: MacroAction) -> bool:
        """Execute single action"""
        try:
            if isinstance(action, MouseMoveAction):
                return self._execute_mouse_move(action)
            elif isinstance(action, MouseClickAction):
                return self._execute_mouse_click(action)
            elif isinstance(action, MouseDragAction):
                return self._execute_mouse_drag(action)
            elif isinstance(action, MouseScrollAction):
                return self._execute_mouse_scroll(action)
            elif isinstance(action, KeyPressAction):
                return self._execute_key_press(action)
            elif isinstance(action, HotkeyAction):
                return self._execute_hotkey(action)
            elif isinstance(action, TextInputAction):
                return self._execute_text_input(action)
            elif isinstance(action, WaitTimeAction):
                return self._execute_wait_time(action)
            elif isinstance(action, WaitPixelAction):
                return self._execute_wait_pixel(action)
            elif isinstance(action, WaitWindowAction):
                return self._execute_wait_window(action)
            elif isinstance(action, WindowFocusAction):
                return self._execute_window_focus(action)
            elif isinstance(action, WindowMoveResizeAction):
                return self._execute_window_move_resize(action)
            else:
                log(f"[PLAYER] Unknown action type: {type(action)}")
                return False
                
        except Exception as e:
            log(f"[PLAYER] Action error: {e}")
            if self._on_error:
                self._on_error(self._context.current_action_idx, action, e)
            return False
    
    # ==================== ACTION EXECUTORS ====================
    
    def _client_to_screen(self, x: int, y: int) -> Tuple[int, int]:
        """Convert client coords to screen coords"""
        if self._context and self._context.client_rect:
            cx, cy, _, _ = self._context.client_rect
            return (cx + x, cy + y)
        return (x, y)
    
    def _screen_to_absolute(self, x: int, y: int) -> Tuple[int, int]:
        """Convert screen coords to absolute (0-65535)"""
        width = user32.GetSystemMetrics(0)
        height = user32.GetSystemMetrics(1)
        abs_x = int(x * 65536 / width)
        abs_y = int(y * 65536 / height)
        return abs_x, abs_y
    
    def _move_mouse(self, screen_x: int, screen_y: int):
        """Move mouse to screen position"""
        abs_x, abs_y = self._screen_to_absolute(screen_x, screen_y)
        
        move_input = INPUT()
        move_input.type = INPUT_MOUSE
        move_input.union.mi.dx = abs_x
        move_input.union.mi.dy = abs_y
        move_input.union.mi.dwFlags = MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE
        user32.SendInput(1, ctypes.byref(move_input), ctypes.sizeof(INPUT))
    
    def _execute_mouse_move(self, action: MouseMoveAction) -> bool:
        """Execute mouse move action"""
        if action.path and len(action.path) > 1:
            # Animate along path
            for x, y, _ in action.path:
                screen_x, screen_y = self._client_to_screen(x, y)
                self._move_mouse(screen_x, screen_y)
                time.sleep(0.01)  # Small delay between points
        else:
            screen_x, screen_y = self._client_to_screen(action.x, action.y)
            self._move_mouse(screen_x, screen_y)
        
        return True
    
    def _execute_mouse_click(self, action: MouseClickAction) -> bool:
        """Execute mouse click action"""
        # Add jitter if specified
        jitter_x = random.randint(-action.jitter_px, action.jitter_px) if action.jitter_px else 0
        jitter_y = random.randint(-action.jitter_px, action.jitter_px) if action.jitter_px else 0
        
        screen_x, screen_y = self._client_to_screen(action.x + jitter_x, action.y + jitter_y)
        self._move_mouse(screen_x, screen_y)
        time.sleep(0.01)
        
        # Determine button flags
        button = action.button
        if button == MouseButton.LEFT:
            down_flag, up_flag = MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP
        elif button == MouseButton.RIGHT:
            down_flag, up_flag = MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP
        elif button == MouseButton.MIDDLE:
            down_flag, up_flag = MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP
        elif button == MouseButton.DOUBLE:
            # Double click
            for _ in range(2):
                self._do_click(MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP)
                time.sleep(0.05)
            return True
        else:
            down_flag, up_flag = MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP
        
        # Execute click(s)
        for _ in range(action.repeat):
            self._do_click(down_flag, up_flag, action.hold_ms)
            if action.repeat > 1:
                time.sleep(0.05)
        
        return True
    
    def _do_click(self, down_flag: int, up_flag: int, hold_ms: int = None):
        """Perform single click"""
        # Mouse down
        down_input = INPUT()
        down_input.type = INPUT_MOUSE
        down_input.union.mi.dwFlags = down_flag
        user32.SendInput(1, ctypes.byref(down_input), ctypes.sizeof(INPUT))
        
        # Hold if specified
        if hold_ms:
            time.sleep(hold_ms / 1000.0)
        else:
            time.sleep(0.02)
        
        # Mouse up
        up_input = INPUT()
        up_input.type = INPUT_MOUSE
        up_input.union.mi.dwFlags = up_flag
        user32.SendInput(1, ctypes.byref(up_input), ctypes.sizeof(INPUT))
    
    def _execute_mouse_drag(self, action: MouseDragAction) -> bool:
        """Execute mouse drag action"""
        # Move to start
        start_screen = self._client_to_screen(action.x1, action.y1)
        end_screen = self._client_to_screen(action.x2, action.y2)
        
        self._move_mouse(*start_screen)
        time.sleep(0.02)
        
        # Mouse down
        if action.button == MouseButton.RIGHT:
            down_flag, up_flag = MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP
        else:
            down_flag, up_flag = MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP
        
        down_input = INPUT()
        down_input.type = INPUT_MOUSE
        down_input.union.mi.dwFlags = down_flag
        user32.SendInput(1, ctypes.byref(down_input), ctypes.sizeof(INPUT))
        
        time.sleep(0.02)
        
        # Interpolate drag path
        if action.path:
            for x, y, _ in action.path:
                screen_x, screen_y = self._client_to_screen(x, y)
                self._move_mouse(screen_x, screen_y)
                time.sleep(0.01)
        else:
            # Simple linear interpolation
            steps = max(10, action.duration_ms // 20)
            for i in range(steps):
                t = i / steps
                x = int(start_screen[0] + t * (end_screen[0] - start_screen[0]))
                y = int(start_screen[1] + t * (end_screen[1] - start_screen[1]))
                self._move_mouse(x, y)
                time.sleep(action.duration_ms / steps / 1000.0)
        
        # Move to end and release
        self._move_mouse(*end_screen)
        time.sleep(0.02)
        
        up_input = INPUT()
        up_input.type = INPUT_MOUSE
        up_input.union.mi.dwFlags = up_flag
        user32.SendInput(1, ctypes.byref(up_input), ctypes.sizeof(INPUT))
        
        return True
    
    def _execute_mouse_scroll(self, action: MouseScrollAction) -> bool:
        """Execute mouse scroll action"""
        screen_x, screen_y = self._client_to_screen(action.x, action.y)
        self._move_mouse(screen_x, screen_y)
        time.sleep(0.01)
        
        wheel_input = INPUT()
        wheel_input.type = INPUT_MOUSE
        wheel_input.union.mi.dwFlags = MOUSEEVENTF_WHEEL
        
        delta = action.delta * 120  # Standard wheel delta
        if action.direction == "down":
            delta = -delta
        
        wheel_input.union.mi.mouseData = delta
        user32.SendInput(1, ctypes.byref(wheel_input), ctypes.sizeof(INPUT))
        
        return True
    
    def _execute_key_press(self, action: KeyPressAction) -> bool:
        """Execute key press action"""
        vk = get_vk_code(action.key)
        if vk == 0:
            log(f"[PLAYER] Unknown key: {action.key}")
            return False
        
        for i in range(action.repeat):
            if action.mode in (KeyPressMode.PRESS, KeyPressMode.DOWN):
                down_input = INPUT()
                down_input.type = INPUT_KEYBOARD
                down_input.union.ki.wVk = vk
                user32.SendInput(1, ctypes.byref(down_input), ctypes.sizeof(INPUT))
            
            if action.mode == KeyPressMode.PRESS:
                time.sleep(0.02)
            
            if action.mode in (KeyPressMode.PRESS, KeyPressMode.UP):
                up_input = INPUT()
                up_input.type = INPUT_KEYBOARD
                up_input.union.ki.wVk = vk
                up_input.union.ki.dwFlags = KEYEVENTF_KEYUP
                user32.SendInput(1, ctypes.byref(up_input), ctypes.sizeof(INPUT))
            
            if i < action.repeat - 1:
                time.sleep(action.delay_between_ms / 1000.0)
        
        return True
    
    def _execute_hotkey(self, action: HotkeyAction) -> bool:
        """Execute hotkey action"""
        vk_codes = [get_vk_code(k) for k in action.keys]
        if 0 in vk_codes:
            log(f"[PLAYER] Unknown key in hotkey: {action.keys}")
            return False
        
        if action.order == HotkeyOrder.SIMULTANEOUS:
            # Press all down
            for vk in vk_codes:
                down_input = INPUT()
                down_input.type = INPUT_KEYBOARD
                down_input.union.ki.wVk = vk
                user32.SendInput(1, ctypes.byref(down_input), ctypes.sizeof(INPUT))
                time.sleep(0.01)
            
            time.sleep(0.05)
            
            # Release all
            for vk in reversed(vk_codes):
                up_input = INPUT()
                up_input.type = INPUT_KEYBOARD
                up_input.union.ki.wVk = vk
                up_input.union.ki.dwFlags = KEYEVENTF_KEYUP
                user32.SendInput(1, ctypes.byref(up_input), ctypes.sizeof(INPUT))
                time.sleep(0.01)
        else:
            # Sequential
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
                time.sleep(0.02)
        
        return True
    
    def _execute_text_input(self, action: TextInputAction) -> bool:
        """Execute text input action"""
        # Optional focus click
        if action.focus_x is not None and action.focus_y is not None:
            screen_x, screen_y = self._client_to_screen(action.focus_x, action.focus_y)
            self._move_mouse(screen_x, screen_y)
            time.sleep(0.01)
            self._do_click(MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP)
            time.sleep(0.1)
        
        if action.mode == TextInputMode.PASTE:
            # Use clipboard paste
            try:
                import pyperclip
                pyperclip.copy(action.text)
                # Ctrl+V
                self._execute_hotkey(HotkeyAction(keys=['ctrl', 'v']))
            except ImportError:
                # Fallback to unicode input
                self._type_unicode(action.text)
        else:
            # Humanize - type character by character
            for char in action.text:
                delay = 1.0 / random.uniform(action.cps_min, action.cps_max)
                self._type_unicode(char)
                time.sleep(delay)
        
        return True
    
    def _type_unicode(self, text: str):
        """Type text using unicode input"""
        for char in text:
            # Key down with unicode
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
    
    def _execute_wait_time(self, action: WaitTimeAction) -> bool:
        """Execute wait time action"""
        wait_ms = action.ms
        if action.variance_ms:
            wait_ms += random.randint(-action.variance_ms, action.variance_ms)
        
        scaled_wait = wait_ms / self._context.speed_multiplier
        self._interruptible_sleep(scaled_wait / 1000.0)
        
        return not self._stop_event.is_set()
    
    def _execute_wait_pixel(self, action: WaitPixelAction) -> bool:
        """Execute wait for pixel color"""
        # This requires capture - simplified implementation
        log(f"[PLAYER] WaitPixel: ({action.x},{action.y}) = RGB{action.rgb}")
        
        start = time.perf_counter()
        timeout_sec = action.timeout_ms / 1000.0
        
        while (time.perf_counter() - start) < timeout_sec:
            if self._stop_event.is_set():
                return False
            
            # TODO: Implement actual pixel capture and comparison
            # For now, just wait
            time.sleep(action.poll_ms / 1000.0)
        
        log("[PLAYER] WaitPixel timeout")
        return False
    
    def _execute_wait_window(self, action: WaitWindowAction) -> bool:
        """Execute wait for window"""
        start = time.perf_counter()
        timeout_sec = action.timeout_ms / 1000.0
        
        while (time.perf_counter() - start) < timeout_sec:
            if self._stop_event.is_set():
                return False
            
            windows = WindowUtils.find_windows_by_match(
                title_contains=action.window_match.title_contains,
                class_name=action.window_match.class_name,
                process_name=action.window_match.process_name
            )
            
            if windows:
                log(f"[PLAYER] Window found: {action.window_match.title_contains}")
                return True
            
            time.sleep(0.1)
        
        log("[PLAYER] WaitWindow timeout")
        return False
    
    def _execute_window_focus(self, action: WindowFocusAction) -> bool:
        """Execute window focus action"""
        windows = WindowUtils.find_windows_by_match(
            title_contains=action.window_match.title_contains,
            class_name=action.window_match.class_name,
            process_name=action.window_match.process_name
        )
        
        if not windows:
            log(f"[PLAYER] Window not found: {action.window_match.title_contains}")
            return False
        
        hwnd = windows[0]
        
        if action.restore_if_minimized:
            if user32.IsIconic(hwnd):
                user32.ShowWindow(hwnd, SW_RESTORE)
                time.sleep(0.1)
        
        user32.SetForegroundWindow(hwnd)
        
        # Update context
        if self._context:
            self._context.hwnd = hwnd
            self._context.client_rect = WindowUtils.get_client_rect(hwnd)
        
        return True
    
    def _execute_window_move_resize(self, action: WindowMoveResizeAction) -> bool:
        """Execute window move/resize action"""
        if not self._context or not self._context.hwnd:
            return False
        
        user32.MoveWindow(
            self._context.hwnd,
            action.x, action.y,
            action.w, action.h,
            True  # Repaint
        )
        
        # Update client rect
        self._context.client_rect = WindowUtils.get_client_rect(self._context.hwnd)
        
        return True
    
    def shutdown(self):
        """Clean shutdown"""
        self.stop()
