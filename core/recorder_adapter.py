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
        self._ignore_ui_hwnd: Optional[int] = None
        self._running = False
        self._events: List[RecordedEvent] = []
        self._events_lock = threading.Lock()
        self._start_time_ms: int = 0
        
        self._mouse_listener = None
        self._keyboard_listener = None
        self._current_modifiers: List[str] = []
    
    def configure(self, target_hwnd: Optional[int] = None,
                  ignore_ui_hwnd: Optional[int] = None):
        """Configure target and ignore windows per spec A2"""
        self._target_hwnd = target_hwnd
        self._ignore_ui_hwnd = ignore_ui_hwnd
        log(f"[RECORDER] Configured: target={target_hwnd}, ignore_ui={ignore_ui_hwnd}")
    
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
    
    @property
    def is_running(self) -> bool:
        return self._running
    
    def _get_ts_ms(self) -> int:
        """Get current timestamp in ms since start"""
        return int(time.time() * 1000) - self._start_time_ms
    
    def _should_filter_event(self, x_screen: int = None, y_screen: int = None) -> bool:
        """
        Check if event should be filtered per spec A3
        
        Returns True if event should be IGNORED
        """
        # Get foreground window
        fg = WindowHelper.get_foreground_window()
        
        # Ignore events from our UI window
        if self._ignore_ui_hwnd and fg == self._ignore_ui_hwnd:
            return True
        
        # If target window is set, only accept events for that window
        if self._target_hwnd and fg != self._target_hwnd:
            return True
        
        # For mouse events, check if coords are in client area
        if x_screen is not None and y_screen is not None and self._target_hwnd:
            client_x, client_y = WindowHelper.screen_to_client(self._target_hwnd, x_screen, y_screen)
            if not WindowHelper.is_point_in_client(self._target_hwnd, client_x, client_y):
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
        
        if self._should_filter_event(x, y):
            return
        
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
        
        if self._should_filter_event(x, y):
            return
        
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
        
        # Don't filter keyboard by position
        if self._target_hwnd:
            fg = WindowHelper.get_foreground_window()
            if fg != self._target_hwnd and self._ignore_ui_hwnd and fg != self._ignore_ui_hwnd:
                # Only filter if not in target and not control hotkey from UI
                pass  # For now, record all keyboard
        
        key_str, vk = self._key_to_string(key)
        
        # Track modifiers
        if key_str in ('ctrl', 'alt', 'shift', 'cmd'):
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
            
            # Special keys mapping
            special_map = {
                Key.ctrl: 'ctrl', Key.ctrl_l: 'ctrl', Key.ctrl_r: 'ctrl',
                Key.alt: 'alt', Key.alt_l: 'alt', Key.alt_r: 'alt',
                Key.shift: 'shift', Key.shift_l: 'shift', Key.shift_r: 'shift',
                Key.cmd: 'cmd', Key.cmd_l: 'cmd', Key.cmd_r: 'cmd',
                Key.enter: 'enter', Key.space: 'space', Key.tab: 'tab',
                Key.backspace: 'backspace', Key.delete: 'delete',
                Key.escape: 'escape', Key.home: 'home', Key.end: 'end',
                Key.page_up: 'page_up', Key.page_down: 'page_down',
                Key.up: 'up', Key.down: 'down', Key.left: 'left', Key.right: 'right',
                Key.f1: 'f1', Key.f2: 'f2', Key.f3: 'f3', Key.f4: 'f4',
                Key.f5: 'f5', Key.f6: 'f6', Key.f7: 'f7', Key.f8: 'f8',
                Key.f9: 'f9', Key.f10: 'f10', Key.f11: 'f11', Key.f12: 'f12',
            }
            
            if key in special_map:
                return (special_map[key], getattr(key, 'vk', None))
            
            # Regular character
            if hasattr(key, 'char') and key.char:
                return (key.char, getattr(key, 'vk', None))
            
            # Fallback
            return (str(key).replace('Key.', ''), getattr(key, 'vk', None))
        except:
            return (str(key), None)


# ==================== RECORDER FACADE ====================

def get_recorder() -> IRecorderHook:
    """Factory function to get recorder instance"""
    return PynputRecorderHook()
