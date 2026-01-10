# AI GOVERNANCE:
# Apply auditor-router
# This is a CODE change

"""
Recorder Adapter — IRecorderHook interface per UPGRADE_PLAN_V2 spec A2
Provides clean abstraction between UI and recording backend
"""

from __future__ import annotations
from typing import Optional, List, Callable, Tuple
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from enum import Enum
import ctypes
from ctypes import wintypes
import time
import threading

from utils.logger import log

user32 = ctypes.windll.user32


# ==================== RECORDED EVENT (per spec A2) ====================

class RecordedEventKind(Enum):
    """Event kinds per spec A2"""
    MOUSE_MOVE = "mouse_move"
    MOUSE_DOWN = "mouse_down"
    MOUSE_UP = "mouse_up"
    WHEEL = "wheel"
    KEY_DOWN = "key_down"
    KEY_UP = "key_up"
    TEXT = "text"


@dataclass
class RecordedEvent:
    """
    Raw recorded event per spec A2
    
    Attributes:
        ts_ms: Timestamp in milliseconds since recording start
        kind: Event type
        x_screen, y_screen: Screen coordinates (for mouse)
        x_client, y_client: Client coordinates (converted)
        key, vk_code, scan_code: Keyboard data
        wheel_delta: Wheel scroll amount
        modifiers: Modifier keys snapshot
        button: Mouse button name
    """
    ts_ms: int
    kind: RecordedEventKind
    x_screen: Optional[int] = None
    y_screen: Optional[int] = None
    x_client: Optional[int] = None
    y_client: Optional[int] = None
    key: Optional[str] = None
    vk_code: Optional[int] = None
    scan_code: Optional[int] = None
    wheel_delta: Optional[int] = None
    modifiers: List[str] = field(default_factory=list)
    button: Optional[str] = None
    hwnd: Optional[int] = None


# ==================== INTERFACE (per spec A2) ====================

class IRecorderHook(ABC):
    """
    Abstract recorder hook interface per spec A2
    
    Methods:
        configure(target_hwnd, ignore_ui_hwnd): Set target and UI windows
        start(): Begin recording
        stop(): Stop and return events
        is_running: Check if active
    """
    
    @abstractmethod
    def configure(self, target_hwnd: Optional[int] = None, 
                  ignore_ui_hwnd: Optional[int] = None):
        """
        Configure the recorder
        
        Args:
            target_hwnd: Only record events for this window (filter others)
            ignore_ui_hwnd: Ignore events from UI window
        """
        pass
    
    @abstractmethod
    def start(self):
        """Start recording"""
        pass
    
    @abstractmethod
    def stop(self) -> List[RecordedEvent]:
        """
        Stop recording (idempotent per spec A4)
        
        Returns:
            List of recorded events
        """
        pass
    
    @property
    @abstractmethod
    def is_running(self) -> bool:
        """Check if recorder is active"""
        pass


# ==================== WINDOW UTILS ====================

class WindowHelper:
    """Window manipulation utilities"""
    
    @staticmethod
    def get_foreground_window() -> int:
        return user32.GetForegroundWindow()
    
    @staticmethod
    def get_window_rect(hwnd: int) -> Tuple[int, int, int, int]:
        """Get window rect: (left, top, right, bottom)"""
        rect = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        return (rect.left, rect.top, rect.right, rect.bottom)
    
    @staticmethod
    def get_client_rect(hwnd: int) -> Tuple[int, int, int, int]:
        """Get client rect: (0, 0, width, height)"""
        rect = wintypes.RECT()
        user32.GetClientRect(hwnd, ctypes.byref(rect))
        return (0, 0, rect.right, rect.bottom)
    
    @staticmethod
    def screen_to_client(hwnd: int, x: int, y: int) -> Tuple[int, int]:
        """Convert screen coords to client coords"""
        pt = wintypes.POINT(x, y)
        user32.ScreenToClient(hwnd, ctypes.byref(pt))
        return (pt.x, pt.y)
    
    @staticmethod
    def client_to_screen(hwnd: int, x: int, y: int) -> Tuple[int, int]:
        """Convert client coords to screen coords"""
        pt = wintypes.POINT(x, y)
        user32.ClientToScreen(hwnd, ctypes.byref(pt))
        return (pt.x, pt.y)
    
    @staticmethod
    def is_point_in_client(hwnd: int, client_x: int, client_y: int) -> bool:
        """Check if point is inside client area"""
        rect = wintypes.RECT()
        user32.GetClientRect(hwnd, ctypes.byref(rect))
        return 0 <= client_x < rect.right and 0 <= client_y < rect.bottom
    
    @staticmethod
    def get_window_title(hwnd: int) -> str:
        length = user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return ""
        buff = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buff, length + 1)
        return buff.value


# ==================== PYNPUT-BASED RECORDER (per spec A2, A3) ====================

class PynputRecorderHook(IRecorderHook):
    """
    Recorder hook implementation using pynput
    Implements IRecorderHook interface per spec A2
    """
    
    def __init__(self):
        self._target_hwnd: Optional[int] = None
        self._ignore_ui_hwnds: set = set()  # Multiple UI windows to ignore
        self._running = False
        self._paused = False  # Pause state
        self._events: List[RecordedEvent] = []
        self._events_lock = threading.Lock()
        self._start_time_ms: int = 0
        self._pause_time_ms: int = 0  # Track time spent paused
        
        self._mouse_listener = None
        self._keyboard_listener = None
        self._current_modifiers: List[str] = []
    
    def configure(self, target_hwnd: Optional[int] = None,
                  ignore_ui_hwnd: Optional[int] = None):
        """Configure target and ignore windows per spec A2"""
        self._target_hwnd = target_hwnd
        if ignore_ui_hwnd:
            self._ignore_ui_hwnds.add(ignore_ui_hwnd)
        log(f"[RECORDER] Configured: target={target_hwnd}, ignore_ui={self._ignore_ui_hwnds}")
    
    def add_ignore_hwnd(self, hwnd: int):
        """Add additional hwnd to ignore list (e.g., recording toolbar)"""
        if hwnd:
            self._ignore_ui_hwnds.add(hwnd)
            log(f"[RECORDER] Added ignore hwnd: {hwnd}")
    
    def start(self):
        """Start recording"""
        if self._running:
            return
        
        self._running = True
        self._events.clear()
        self._start_time_ms = int(time.time() * 1000)
        self._current_modifiers = []
        
        try:
            from pynput import mouse, keyboard
            
            self._mouse_listener = mouse.Listener(
                on_move=self._on_mouse_move,
                on_click=self._on_mouse_click,
                on_scroll=self._on_mouse_scroll
            )
            self._mouse_listener.start()
            
            self._keyboard_listener = keyboard.Listener(
                on_press=self._on_key_press,
                on_release=self._on_key_release
            )
            self._keyboard_listener.start()
            
            log("[RECORDER] PynputRecorderHook started")
        except ImportError as e:
            self._running = False
            log(f"[RECORDER] ERROR: pynput not installed: {e}")
            raise
    
    def stop(self) -> List[RecordedEvent]:
        """Stop recording (idempotent per spec A4)"""
        if not self._running:
            return []
        
        self._running = False
        
        if self._mouse_listener:
            try:
                self._mouse_listener.stop()
            except:
                pass
            self._mouse_listener = None
        
        if self._keyboard_listener:
            try:
                self._keyboard_listener.stop()
            except:
                pass
            self._keyboard_listener = None
        
        with self._events_lock:
            events = list(self._events)
        
        log(f"[RECORDER] Stopped. {len(events)} events captured")
        return events
    
    def pause(self):
        """Pause recording - events will be ignored until resume"""
        if self._running and not self._paused:
            self._paused = True
            self._pause_start = int(time.time() * 1000)
            log("[RECORDER] Paused")
    
    def resume(self):
        """Resume recording after pause"""
        if self._running and self._paused:
            # Add paused duration to offset
            self._pause_time_ms += int(time.time() * 1000) - self._pause_start
            self._paused = False
            log("[RECORDER] Resumed")
    
    @property
    def is_running(self) -> bool:
        return self._running
    
    @property
    def is_paused(self) -> bool:
        return self._paused
    
    def _get_ts_ms(self) -> int:
        """Get current timestamp in ms since start (excluding paused time)"""
        return int(time.time() * 1000) - self._start_time_ms - self._pause_time_ms
    
    def _should_filter_event(self, x_screen: int = None, y_screen: int = None) -> bool:
        """
        Check if event should be filtered per spec A3
        
        Returns True if event should be IGNORED
        """
        # Ignore events while paused or not running
        if self._paused or not self._running:
            return True
        
        # If NO target window (Full Screen mode) - record everything
        if not self._target_hwnd:
            return False
        
        # If target window is set, check by COORDS
        if x_screen is not None and y_screen is not None:
            # Check if click is within target window bounds
            try:
                rect = WindowHelper.get_window_rect(self._target_hwnd)
                if rect[0] <= x_screen <= rect[2] and rect[1] <= y_screen <= rect[3]:
                    return False  # Accept - coords are in target window
                else:
                    return True  # Outside target
            except:
                pass
        
        # For keyboard events, check foreground
        fg = WindowHelper.get_foreground_window()
        if fg != self._target_hwnd:
            return True
        
        return False
    
    def _add_event(self, event: RecordedEvent):
        """Add event to buffer (thread-safe)"""
        with self._events_lock:
            self._events.append(event)
    
    def _on_mouse_move(self, x: int, y: int):
        """Handle mouse move"""
        if not self._running:
            return
        
        if self._should_filter_event(x, y):
            return
        
        # Convert to client coords if target window set
        client_x, client_y = None, None
        if self._target_hwnd:
            client_x, client_y = WindowHelper.screen_to_client(self._target_hwnd, x, y)
        
        event = RecordedEvent(
            ts_ms=self._get_ts_ms(),
            kind=RecordedEventKind.MOUSE_MOVE,
            x_screen=x,
            y_screen=y,
            x_client=client_x,
            y_client=client_y,
            hwnd=self._target_hwnd or WindowHelper.get_foreground_window(),
            modifiers=list(self._current_modifiers)
        )
        self._add_event(event)
    
    def _on_mouse_click(self, x: int, y: int, button, pressed: bool):
        """Handle mouse click"""
        if not self._running:
            return
        
        log(f"[RECORDER] Mouse {'down' if pressed else 'up'} at ({x}, {y}) button={button}")
        
        if self._should_filter_event(x, y):
            return  # Don't spam log for filtered events
        
        # Map button
        button_map = {
            'Button.left': 'left',
            'Button.right': 'right',
            'Button.middle': 'middle'
        }
        button_str = button_map.get(str(button), 'left')
        
        # Convert to client coords
        client_x, client_y = None, None
        if self._target_hwnd:
            client_x, client_y = WindowHelper.screen_to_client(self._target_hwnd, x, y)
        
        event = RecordedEvent(
            ts_ms=self._get_ts_ms(),
            kind=RecordedEventKind.MOUSE_DOWN if pressed else RecordedEventKind.MOUSE_UP,
            x_screen=x,
            y_screen=y,
            x_client=client_x,
            y_client=client_y,
            button=button_str,
            hwnd=self._target_hwnd or WindowHelper.get_foreground_window(),
            modifiers=list(self._current_modifiers)
        )
        self._add_event(event)
    
    def _on_mouse_scroll(self, x: int, y: int, dx: int, dy: int):
        """Handle mouse scroll"""
        if not self._running:
            return
        
        log(f"[RECORDER] Scroll at ({x}, {y}) dx={dx} dy={dy}")
        
        if self._should_filter_event(x, y):
            return  # Don't spam log for filtered events
        
        client_x, client_y = None, None
        if self._target_hwnd:
            client_x, client_y = WindowHelper.screen_to_client(self._target_hwnd, x, y)
        
        event = RecordedEvent(
            ts_ms=self._get_ts_ms(),
            kind=RecordedEventKind.WHEEL,
            x_screen=x,
            y_screen=y,
            x_client=client_x,
            y_client=client_y,
            wheel_delta=dy * 120,  # Convert to standard delta
            hwnd=self._target_hwnd or WindowHelper.get_foreground_window(),
            modifiers=list(self._current_modifiers)
        )
        self._add_event(event)
    
    def _on_key_press(self, key):
        """Handle key press"""
        if not self._running:
            return
        
        # Don't filter keyboard by position - record all keys
        key_str, vk = self._key_to_string(key)
        log(f"[RECORDER] Key down: {key_str} (vk={vk})")
        
        # Track modifiers
        if key_str in ('ctrl', 'ctrl_l', 'ctrl_r', 'alt', 'shift', 'win'):
            if key_str not in self._current_modifiers:
                self._current_modifiers.append(key_str)
        
        event = RecordedEvent(
            ts_ms=self._get_ts_ms(),
            kind=RecordedEventKind.KEY_DOWN,
            key=key_str,
            vk_code=vk,
            hwnd=WindowHelper.get_foreground_window(),
            modifiers=list(self._current_modifiers)
        )
        self._add_event(event)
    
    def _on_key_release(self, key):
        """Handle key release"""
        if not self._running:
            return
        
        key_str, vk = self._key_to_string(key)
        
        # Update modifiers
        if key_str in self._current_modifiers:
            self._current_modifiers.remove(key_str)
        
        event = RecordedEvent(
            ts_ms=self._get_ts_ms(),
            kind=RecordedEventKind.KEY_UP,
            key=key_str,
            vk_code=vk,
            hwnd=WindowHelper.get_foreground_window(),
            modifiers=list(self._current_modifiers)
        )
        self._add_event(event)
    
    def _key_to_string(self, key) -> Tuple[str, Optional[int]]:
        """Convert pynput key to string and VK code"""
        try:
            from pynput.keyboard import Key
            
            # Build special_map dynamically to avoid missing key errors
            special_map = {}
            key_mappings = [
                ('ctrl', 'ctrl'), ('ctrl_l', 'ctrl'), ('ctrl_r', 'ctrl'),
                ('alt', 'alt'), ('alt_l', 'alt'), ('alt_r', 'alt'), ('alt_gr', 'alt_gr'),
                ('shift', 'shift'), ('shift_l', 'shift'), ('shift_r', 'shift'),
                ('cmd', 'win'), ('cmd_l', 'win'), ('cmd_r', 'win'),
                ('enter', 'enter'), ('space', 'space'), ('tab', 'tab'),
                ('backspace', 'backspace'), ('delete', 'delete'),
                ('esc', 'escape'), ('escape', 'escape'),
                ('home', 'home'), ('end', 'end'),
                ('page_up', 'page_up'), ('page_down', 'page_down'),
                ('up', 'up'), ('down', 'down'), ('left', 'left'), ('right', 'right'),
                ('f1', 'f1'), ('f2', 'f2'), ('f3', 'f3'), ('f4', 'f4'),
                ('f5', 'f5'), ('f6', 'f6'), ('f7', 'f7'), ('f8', 'f8'),
                ('f9', 'f9'), ('f10', 'f10'), ('f11', 'f11'), ('f12', 'f12'),
                ('caps_lock', 'caps_lock'), ('num_lock', 'num_lock'),
                ('scroll_lock', 'scroll_lock'), ('print_screen', 'print_screen'),
                ('pause', 'pause'), ('insert', 'insert'),
            ]
            
            for attr, name in key_mappings:
                if hasattr(Key, attr):
                    special_map[getattr(Key, attr)] = name
            
            if key in special_map:
                return (special_map[key], getattr(key, 'vk', None))
            
            # Regular character
            if hasattr(key, 'char') and key.char:
                return (key.char, getattr(key, 'vk', None))
            
            # Fallback - clean up Key. prefix
            key_str = str(key).replace('Key.', '')
            return (key_str, getattr(key, 'vk', None))
        except Exception as e:
            log(f"[RECORDER] Key conversion error: {key} -> {e}")
            return (str(key).replace('Key.', ''), None)


# ==================== RECORDER FACADE ====================

def get_recorder() -> IRecorderHook:
    """Factory function to get recorder instance"""
    return PynputRecorderHook()
