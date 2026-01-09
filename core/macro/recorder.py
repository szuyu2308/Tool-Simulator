# AI GOVERNANCE:
# Apply auditor-router
# This is a CODE change

"""
Macro Recorder Engine - Global Input Hooks
Records mouse/keyboard events with window focus tracking
Uses pynput for cross-platform global hooks
"""

from __future__ import annotations
from typing import Optional, List, Callable, Tuple, Dict, Any
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from enum import Enum
import ctypes
from ctypes import wintypes
import time
import threading
import queue

from utils.logger import log

# Windows API for coordinate conversion and window detection
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# Constants
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205
WM_MBUTTONDOWN = 0x0207
WM_MBUTTONUP = 0x0208
WM_MOUSEWHEEL = 0x020A


# ==================== RAW EVENT TYPES ====================

class RawEventType(Enum):
    MOUSE_MOVE = "mouse_move"
    MOUSE_DOWN = "mouse_down"
    MOUSE_UP = "mouse_up"
    MOUSE_SCROLL = "mouse_scroll"
    KEY_DOWN = "key_down"
    KEY_UP = "key_up"
    WINDOW_FOCUS = "window_focus"


@dataclass
class RawEvent:
    """Raw input event from global hooks"""
    event_type: RawEventType
    timestamp: float  # time.perf_counter()
    
    # Mouse data (client coords)
    x: Optional[int] = None
    y: Optional[int] = None
    button: Optional[str] = None  # left, right, middle
    scroll_delta: Optional[int] = None
    
    # Keyboard data
    key: Optional[str] = None
    vk_code: Optional[int] = None
    
    # Window data
    hwnd: Optional[int] = None
    window_title: Optional[str] = None
    window_class: Optional[str] = None


# ==================== RECORDER HOOK INTERFACE ====================

class IRecorderHook(ABC):
    """Abstract interface for input hooks (swappable implementation)"""
    
    @abstractmethod
    def start(self, callback: Callable[[RawEvent], None]):
        """Start listening for input events"""
        pass
    
    @abstractmethod
    def stop(self):
        """Stop listening"""
        pass
    
    @abstractmethod
    def is_running(self) -> bool:
        """Check if hook is active"""
        pass


# ==================== WINDOW UTILITIES ====================

class WindowUtils:
    """Windows API utilities for window management"""
    
    @staticmethod
    def get_foreground_window() -> int:
        """Get current foreground window handle"""
        return user32.GetForegroundWindow()
    
    @staticmethod
    def get_window_title(hwnd: int) -> str:
        """Get window title"""
        length = user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return ""
        buff = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buff, length + 1)
        return buff.value
    
    @staticmethod
    def get_window_class(hwnd: int) -> str:
        """Get window class name"""
        buff = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, buff, 256)
        return buff.value
    
    @staticmethod
    def get_window_process_name(hwnd: int) -> str:
        """Get process name for window"""
        import psutil
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        try:
            proc = psutil.Process(pid.value)
            return proc.name()
        except:
            return ""
    
    @staticmethod
    def get_client_rect(hwnd: int) -> Tuple[int, int, int, int]:
        """Get client area rect (screen coords): (x, y, w, h)"""
        rect = wintypes.RECT()
        user32.GetClientRect(hwnd, ctypes.byref(rect))
        
        # Convert client origin to screen coords
        pt = wintypes.POINT(0, 0)
        user32.ClientToScreen(hwnd, ctypes.byref(pt))
        
        return (pt.x, pt.y, rect.right, rect.bottom)
    
    @staticmethod
    def screen_to_client(hwnd: int, screen_x: int, screen_y: int) -> Tuple[int, int]:
        """Convert screen coordinates to client coordinates"""
        pt = wintypes.POINT(screen_x, screen_y)
        user32.ScreenToClient(hwnd, ctypes.byref(pt))
        return (pt.x, pt.y)
    
    @staticmethod
    def is_point_in_client(hwnd: int, client_x: int, client_y: int) -> bool:
        """Check if point is inside client area"""
        rect = wintypes.RECT()
        user32.GetClientRect(hwnd, ctypes.byref(rect))
        return 0 <= client_x < rect.right and 0 <= client_y < rect.bottom
    
    @staticmethod
    def find_windows_by_match(title_contains: str = None, 
                               class_name: str = None,
                               process_name: str = None) -> List[int]:
        """Find windows matching criteria"""
        results = []
        
        def enum_callback(hwnd, _):
            if not user32.IsWindowVisible(hwnd):
                return True
            
            if title_contains:
                title = WindowUtils.get_window_title(hwnd)
                if title_contains.lower() not in title.lower():
                    return True
            
            if class_name:
                cls = WindowUtils.get_window_class(hwnd)
                if class_name.lower() != cls.lower():
                    return True
            
            if process_name:
                proc = WindowUtils.get_window_process_name(hwnd)
                if process_name.lower() != proc.lower():
                    return True
            
            results.append(hwnd)
            return True
        
        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.POINTER(ctypes.c_int))
        user32.EnumWindows(WNDENUMPROC(enum_callback), 0)
        
        return results


# ==================== PYNPUT HOOK IMPLEMENTATION ====================

class PynputHook(IRecorderHook):
    """Global input hook using pynput library"""
    
    def __init__(self, target_hwnd: Optional[int] = None):
        """
        Initialize hook
        
        Args:
            target_hwnd: If set, only record events for this window (convert to client coords)
                        If None, record all events with screen coords
        """
        self._target_hwnd = target_hwnd
        self._callback: Optional[Callable[[RawEvent], None]] = None
        self._running = False
        
        self._mouse_listener = None
        self._keyboard_listener = None
        self._focus_thread: Optional[threading.Thread] = None
        self._stop_focus = threading.Event()
        
        self._last_foreground_hwnd: Optional[int] = None
        
    def start(self, callback: Callable[[RawEvent], None]):
        """Start listening for input events"""
        if self._running:
            return
        
        self._callback = callback
        self._running = True
        self._stop_focus.clear()
        
        try:
            from pynput import mouse, keyboard
            
            # Mouse listener
            self._mouse_listener = mouse.Listener(
                on_move=self._on_mouse_move,
                on_click=self._on_mouse_click,
                on_scroll=self._on_mouse_scroll
            )
            self._mouse_listener.start()
            
            # Keyboard listener
            self._keyboard_listener = keyboard.Listener(
                on_press=self._on_key_press,
                on_release=self._on_key_release
            )
            self._keyboard_listener.start()
            
            # Window focus polling thread
            self._focus_thread = threading.Thread(target=self._poll_focus, daemon=True)
            self._focus_thread.start()
            
            log("[RECORDER] PynputHook started")
            
        except ImportError:
            log("[RECORDER] ERROR: pynput not installed. Install with: pip install pynput")
            self._running = False
            raise
    
    def stop(self):
        """Stop listening"""
        if not self._running:
            return
        
        self._running = False
        self._stop_focus.set()
        
        if self._mouse_listener:
            self._mouse_listener.stop()
            self._mouse_listener = None
        
        if self._keyboard_listener:
            self._keyboard_listener.stop()
            self._keyboard_listener = None
        
        if self._focus_thread:
            self._focus_thread.join(timeout=1.0)
            self._focus_thread = None
        
        log("[RECORDER] PynputHook stopped")
    
    def is_running(self) -> bool:
        return self._running
    
    def _convert_coords(self, screen_x: int, screen_y: int) -> Tuple[Optional[int], Optional[int], Optional[int]]:
        """
        Convert screen coords to client coords if target window is set
        Returns: (client_x, client_y, hwnd) or (None, None, None) if outside target
        """
        if self._target_hwnd:
            client_x, client_y = WindowUtils.screen_to_client(self._target_hwnd, screen_x, screen_y)
            if WindowUtils.is_point_in_client(self._target_hwnd, client_x, client_y):
                return (client_x, client_y, self._target_hwnd)
            return (None, None, None)  # Outside target window
        
        # No target - use foreground window
        hwnd = WindowUtils.get_foreground_window()
        if hwnd:
            client_x, client_y = WindowUtils.screen_to_client(hwnd, screen_x, screen_y)
            return (client_x, client_y, hwnd)
        
        return (screen_x, screen_y, None)  # Fallback to screen coords
    
    def _on_mouse_move(self, x: int, y: int):
        """Handle mouse move event"""
        if not self._callback or not self._running:
            return
        
        client_x, client_y, hwnd = self._convert_coords(x, y)
        if client_x is None:
            return  # Outside target window
        
        event = RawEvent(
            event_type=RawEventType.MOUSE_MOVE,
            timestamp=time.perf_counter(),
            x=client_x,
            y=client_y,
            hwnd=hwnd
        )
        self._callback(event)
    
    def _on_mouse_click(self, x: int, y: int, button, pressed: bool):
        """Handle mouse click event"""
        if not self._callback or not self._running:
            return
        
        client_x, client_y, hwnd = self._convert_coords(x, y)
        if client_x is None:
            return
        
        # Map pynput button to string
        button_map = {
            'Button.left': 'left',
            'Button.right': 'right',
            'Button.middle': 'middle'
        }
        button_str = button_map.get(str(button), 'left')
        
        event = RawEvent(
            event_type=RawEventType.MOUSE_DOWN if pressed else RawEventType.MOUSE_UP,
            timestamp=time.perf_counter(),
            x=client_x,
            y=client_y,
            button=button_str,
            hwnd=hwnd
        )
        self._callback(event)
    
    def _on_mouse_scroll(self, x: int, y: int, dx: int, dy: int):
        """Handle mouse scroll event"""
        if not self._callback or not self._running:
            return
        
        client_x, client_y, hwnd = self._convert_coords(x, y)
        if client_x is None:
            return
        
        event = RawEvent(
            event_type=RawEventType.MOUSE_SCROLL,
            timestamp=time.perf_counter(),
            x=client_x,
            y=client_y,
            scroll_delta=dy,
            hwnd=hwnd
        )
        self._callback(event)
    
    def _on_key_press(self, key):
        """Handle key press event"""
        if not self._callback or not self._running:
            return
        
        key_str, vk = self._key_to_string(key)
        
        event = RawEvent(
            event_type=RawEventType.KEY_DOWN,
            timestamp=time.perf_counter(),
            key=key_str,
            vk_code=vk,
            hwnd=WindowUtils.get_foreground_window()
        )
        self._callback(event)
    
    def _on_key_release(self, key):
        """Handle key release event"""
        if not self._callback or not self._running:
            return
        
        key_str, vk = self._key_to_string(key)
        
        event = RawEvent(
            event_type=RawEventType.KEY_UP,
            timestamp=time.perf_counter(),
            key=key_str,
            vk_code=vk,
            hwnd=WindowUtils.get_foreground_window()
        )
        self._callback(event)
    
    def _key_to_string(self, key) -> Tuple[str, Optional[int]]:
        """Convert pynput key to string and VK code"""
        try:
            # Regular character key
            if hasattr(key, 'char') and key.char:
                return (key.char, None)
            
            # Special key
            if hasattr(key, 'vk'):
                vk = key.vk
            else:
                vk = None
            
            # Named key
            name = str(key).replace('Key.', '')
            return (name, vk)
        except:
            return (str(key), None)
    
    def _poll_focus(self):
        """Poll foreground window for focus changes"""
        while not self._stop_focus.wait(0.05):  # 50ms interval
            if not self._running:
                break
            
            hwnd = WindowUtils.get_foreground_window()
            
            if hwnd != self._last_foreground_hwnd:
                self._last_foreground_hwnd = hwnd
                
                if self._callback and hwnd:
                    event = RawEvent(
                        event_type=RawEventType.WINDOW_FOCUS,
                        timestamp=time.perf_counter(),
                        hwnd=hwnd,
                        window_title=WindowUtils.get_window_title(hwnd),
                        window_class=WindowUtils.get_window_class(hwnd)
                    )
                    self._callback(event)


# ==================== GLOBAL HOTKEY MANAGER ====================

class GlobalHotkeyManager:
    """Manages global hotkeys for recording/playback control"""
    
    def __init__(self):
        self._hotkeys: Dict[str, Callable] = {}
        self._listener = None
        self._running = False
        self._current_keys = set()
        self._lock = threading.Lock()
    
    def register(self, hotkey: str, callback: Callable):
        """
        Register a global hotkey
        
        Args:
            hotkey: Key combination like "Ctrl+Shift+R"
            callback: Function to call when hotkey is pressed
        """
        normalized = self._normalize_hotkey(hotkey)
        self._hotkeys[normalized] = callback
        log(f"[HOTKEY] Registered: {hotkey} -> {normalized}")
    
    def unregister(self, hotkey: str):
        """Unregister a hotkey"""
        normalized = self._normalize_hotkey(hotkey)
        if normalized in self._hotkeys:
            del self._hotkeys[normalized]
    
    def start(self):
        """Start listening for hotkeys"""
        if self._running:
            return
        
        self._running = True
        
        try:
            from pynput import keyboard
            
            self._listener = keyboard.Listener(
                on_press=self._on_key_press,
                on_release=self._on_key_release
            )
            self._listener.start()
            log("[HOTKEY] GlobalHotkeyManager started")
            
        except ImportError:
            log("[HOTKEY] ERROR: pynput not installed")
            self._running = False
    
    def stop(self):
        """Stop listening"""
        if not self._running:
            return
        
        self._running = False
        
        if self._listener:
            self._listener.stop()
            self._listener = None
        
        log("[HOTKEY] GlobalHotkeyManager stopped")
    
    def _normalize_hotkey(self, hotkey: str) -> str:
        """Normalize hotkey string to consistent format"""
        parts = [p.strip().lower() for p in hotkey.split('+')]
        
        # Normalize modifier names
        normalized = []
        for p in parts:
            if p in ('ctrl', 'control'):
                normalized.append('ctrl')
            elif p in ('alt', 'menu'):
                normalized.append('alt')
            elif p in ('shift',):
                normalized.append('shift')
            elif p in ('win', 'cmd', 'super'):
                normalized.append('cmd')
            else:
                normalized.append(p)
        
        # Sort modifiers first, then key
        modifiers = sorted([p for p in normalized if p in ('ctrl', 'alt', 'shift', 'cmd')])
        keys = [p for p in normalized if p not in ('ctrl', 'alt', 'shift', 'cmd')]
        
        return '+'.join(modifiers + keys)
    
    def _on_key_press(self, key):
        """Handle key press"""
        with self._lock:
            key_name = self._get_key_name(key)
            if key_name:
                self._current_keys.add(key_name)
                self._check_hotkeys()
    
    def _on_key_release(self, key):
        """Handle key release"""
        with self._lock:
            key_name = self._get_key_name(key)
            if key_name:
                self._current_keys.discard(key_name)
    
    def _get_key_name(self, key) -> Optional[str]:
        """Get normalized key name"""
        try:
            # Check for special keys
            from pynput.keyboard import Key
            
            special_map = {
                Key.ctrl: 'ctrl',
                Key.ctrl_l: 'ctrl',
                Key.ctrl_r: 'ctrl',
                Key.alt: 'alt',
                Key.alt_l: 'alt',
                Key.alt_r: 'alt',
                Key.shift: 'shift',
                Key.shift_l: 'shift',
                Key.shift_r: 'shift',
                Key.cmd: 'cmd',
                Key.cmd_l: 'cmd',
                Key.cmd_r: 'cmd',
            }
            
            if key in special_map:
                return special_map[key]
            
            # Regular character
            if hasattr(key, 'char') and key.char:
                return key.char.lower()
            
            # Named key
            return str(key).replace('Key.', '').lower()
            
        except:
            return None
    
    def _check_hotkeys(self):
        """Check if current keys match any registered hotkey"""
        current = '+'.join(sorted(self._current_keys))
        
        for hotkey, callback in self._hotkeys.items():
            if current == hotkey:
                # Execute callback in separate thread to not block listener
                threading.Thread(target=callback, daemon=True).start()


# ==================== RECORDER STATE MACHINE ====================

class RecorderState(Enum):
    IDLE = "idle"
    RECORDING = "recording"
    PAUSED = "paused"


class MacroRecorder:
    """
    Main Macro Recorder - coordinates hooks, events, and consolidation
    """
    
    def __init__(self, target_hwnd: Optional[int] = None):
        """
        Initialize recorder
        
        Args:
            target_hwnd: Target window handle (optional, for window-specific recording)
        """
        self._target_hwnd = target_hwnd
        self._state = RecorderState.IDLE
        
        # Components
        self._hook: Optional[IRecorderHook] = None
        self._hotkey_manager = GlobalHotkeyManager()
        
        # Raw events buffer
        self._raw_events: List[RawEvent] = []
        self._events_lock = threading.Lock()
        
        # Recording state
        self._start_time: Optional[float] = None
        
        # Callbacks
        self._on_state_change: Optional[Callable[[RecorderState], None]] = None
        self._on_event: Optional[Callable[[RawEvent], None]] = None
        
        # Settings
        self._include_mouse_move = True
        self._mouse_move_min_delta = 5
    
    @property
    def state(self) -> RecorderState:
        return self._state
    
    @property
    def is_recording(self) -> bool:
        return self._state == RecorderState.RECORDING
    
    @property
    def raw_events(self) -> List[RawEvent]:
        with self._events_lock:
            return list(self._raw_events)
    
    def set_callbacks(self, 
                      on_state_change: Callable[[RecorderState], None] = None,
                      on_event: Callable[[RawEvent], None] = None):
        """Set callbacks for state changes and events"""
        self._on_state_change = on_state_change
        self._on_event = on_event
    
    def set_settings(self, include_mouse_move: bool = True, mouse_move_min_delta: int = 5):
        """Update recording settings"""
        self._include_mouse_move = include_mouse_move
        self._mouse_move_min_delta = mouse_move_min_delta
    
    def setup_hotkeys(self, record_toggle: str = "Ctrl+Shift+R", 
                      stop: str = "Ctrl+Shift+S"):
        """Setup global hotkeys"""
        self._hotkey_manager.register(record_toggle, self.toggle_recording)
        self._hotkey_manager.register(stop, self.stop_recording)
        self._hotkey_manager.start()
    
    def start_recording(self):
        """Start recording"""
        if self._state != RecorderState.IDLE:
            return
        
        # Clear previous events
        with self._events_lock:
            self._raw_events.clear()
        
        # Initialize hook
        self._hook = PynputHook(target_hwnd=self._target_hwnd)
        self._hook.start(self._on_raw_event)
        
        self._start_time = time.perf_counter()
        self._set_state(RecorderState.RECORDING)
        
        log("[RECORDER] Recording started")
    
    def stop_recording(self):
        """Stop recording"""
        if self._state == RecorderState.IDLE:
            return
        
        if self._hook:
            self._hook.stop()
            self._hook = None
        
        self._set_state(RecorderState.IDLE)
        log(f"[RECORDER] Recording stopped. {len(self._raw_events)} events captured")
    
    def pause_recording(self):
        """Pause recording"""
        if self._state != RecorderState.RECORDING:
            return
        
        self._set_state(RecorderState.PAUSED)
        log("[RECORDER] Recording paused")
    
    def resume_recording(self):
        """Resume recording"""
        if self._state != RecorderState.PAUSED:
            return
        
        self._set_state(RecorderState.RECORDING)
        log("[RECORDER] Recording resumed")
    
    def toggle_recording(self):
        """Toggle recording on/off"""
        if self._state == RecorderState.IDLE:
            self.start_recording()
        else:
            self.stop_recording()
    
    def _set_state(self, state: RecorderState):
        """Set state and notify callback"""
        self._state = state
        if self._on_state_change:
            self._on_state_change(state)
    
    def _on_raw_event(self, event: RawEvent):
        """Handle raw event from hook"""
        if self._state != RecorderState.RECORDING:
            return
        
        # Filter mouse moves if needed
        if event.event_type == RawEventType.MOUSE_MOVE:
            if not self._include_mouse_move:
                return
            
            # Check minimum delta
            with self._events_lock:
                if self._raw_events:
                    last = self._raw_events[-1]
                    if last.event_type == RawEventType.MOUSE_MOVE:
                        if last.x is not None and event.x is not None:
                            dx = abs(event.x - last.x)
                            dy = abs(event.y - last.y)
                            if dx < self._mouse_move_min_delta and dy < self._mouse_move_min_delta:
                                return
        
        with self._events_lock:
            self._raw_events.append(event)
        
        if self._on_event:
            self._on_event(event)
    
    def get_events_since(self, start_time: float) -> List[RawEvent]:
        """Get events since given timestamp"""
        with self._events_lock:
            return [e for e in self._raw_events if e.timestamp >= start_time]
    
    def shutdown(self):
        """Clean shutdown"""
        self.stop_recording()
        self._hotkey_manager.stop()
