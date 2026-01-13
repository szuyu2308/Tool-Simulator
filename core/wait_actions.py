# AI GOVERNANCE:
# Apply auditor-router
# This is a CODE change

"""
Wait Actions Module — per UPGRADE_PLAN_V2 spec B1
Implements: WaitTime, WaitPixelColor, WaitScreenChange, WaitHotkey, WaitFile
"""

from __future__ import annotations
import time
import os
import threading
from abc import ABC, abstractmethod
from typing import Optional, Tuple, Callable, Any
from dataclasses import dataclass
import ctypes
from ctypes import wintypes

from utils.logger import log

user32 = ctypes.windll.user32


class WaitResult:
    """Result of a wait operation"""
    def __init__(self, success: bool, timeout: bool = False, message: str = ""):
        self.success = success
        self.timeout = timeout
        self.message = message


class WaitAction(ABC):
    """Base class for all wait actions"""
    
    @abstractmethod
    def wait(self, stop_event: threading.Event) -> WaitResult:
        """
        Execute the wait operation
        
        Args:
            stop_event: Event to check for stop signal
            
        Returns:
            WaitResult indicating success/failure
        """
        pass


class WaitTime(WaitAction):
    """
    Wait for specified duration
    Per spec B1-1: WaitTime(delay_ms: int, variance_ms: int = 0)
    """
    
    def __init__(self, delay_ms: int, variance_ms: int = 0):
        """
        Args:
            delay_ms: Base delay in milliseconds
            variance_ms: Random variance (+/- this value)
        """
        self.delay_ms = delay_ms
        self.variance_ms = variance_ms
    
    def wait(self, stop_event: threading.Event) -> WaitResult:
        """Wait for the specified duration"""
        import random
        
        # Calculate actual delay with variance
        if self.variance_ms > 0:
            variance = random.randint(-self.variance_ms, self.variance_ms)
            actual_delay = max(0, self.delay_ms + variance)
        else:
            actual_delay = self.delay_ms
        
        log(f"[WAIT] WaitTime: {actual_delay}ms")
        
        # Wait in small increments to check stop event
        elapsed = 0
        increment = 50  # Check every 50ms
        
        while elapsed < actual_delay:
            if stop_event.is_set():
                return WaitResult(success=False, message="Stopped by user")
            
            sleep_time = min(increment, actual_delay - elapsed)
            time.sleep(sleep_time / 1000.0)
            elapsed += sleep_time
        
        return WaitResult(success=True, message=f"Waited {actual_delay}ms")


class WaitPixelColor(WaitAction):
    """
    Wait until pixel at (x, y) matches expected color
    Per spec B1-2: WaitPixelColor(x, y, expected_rgb, tolerance, timeout_ms, target_hwnd)
    """
    
    def __init__(self, 
                 x: int, 
                 y: int, 
                 expected_rgb: Tuple[int, int, int],
                 tolerance: int = 0,
                 timeout_ms: int = 30000,
                 target_hwnd: int = 0):
        """
        Args:
            x, y: Pixel coordinates (client coords if target_hwnd set)
            expected_rgb: Expected (R, G, B) color
            tolerance: Color tolerance (0-255)
            timeout_ms: Timeout in milliseconds
            target_hwnd: Target window handle (0 for screen coords)
        """
        self.x = x
        self.y = y
        self.expected_rgb = expected_rgb
        self.tolerance = tolerance
        self.timeout_ms = timeout_ms
        self.target_hwnd = target_hwnd
    
    def wait(self, stop_event: threading.Event) -> WaitResult:
        """Wait until pixel matches expected color"""
        log(f"[WAIT] WaitPixelColor: ({self.x}, {self.y}) expecting {self.expected_rgb} ±{self.tolerance}")
        
        start_time = time.time()
        check_interval = 100  # Check every 100ms
        
        while True:
            if stop_event.is_set():
                return WaitResult(success=False, message="Stopped by user")
            
            # Check timeout
            elapsed = (time.time() - start_time) * 1000
            if elapsed >= self.timeout_ms:
                return WaitResult(success=False, timeout=True, 
                                  message=f"Timeout after {self.timeout_ms}ms")
            
            # Get current pixel color
            screen_x, screen_y = self.x, self.y
            
            # Convert client to screen coords if needed
            if self.target_hwnd:
                pt = wintypes.POINT(self.x, self.y)
                user32.ClientToScreen(self.target_hwnd, ctypes.byref(pt))
                screen_x, screen_y = pt.x, pt.y
            
            # Get pixel color
            hdc = user32.GetDC(0)
            pixel = ctypes.windll.gdi32.GetPixel(hdc, screen_x, screen_y)
            user32.ReleaseDC(0, hdc)
            
            r = pixel & 0xFF
            g = (pixel >> 8) & 0xFF
            b = (pixel >> 16) & 0xFF
            
            # Check if color matches within tolerance
            if (abs(r - self.expected_rgb[0]) <= self.tolerance and
                abs(g - self.expected_rgb[1]) <= self.tolerance and
                abs(b - self.expected_rgb[2]) <= self.tolerance):
                return WaitResult(success=True, 
                                  message=f"Pixel matched: ({r}, {g}, {b})")
            
            time.sleep(check_interval / 1000.0)


class WaitScreenChange(WaitAction):
    """
    Wait until region on screen changes
    Per spec B1-3: WaitScreenChange(region: Tuple[x1, y1, x2, y2], threshold, timeout_ms)
    """
    
    def __init__(self,
                 region: Tuple[int, int, int, int],
                 threshold: float = 0.235,
                 timeout_ms: int = 30000,
                 target_hwnd: int = 0):
        """
        Args:
            region: (x1, y1, x2, y2) region to monitor
            threshold: Change threshold (0.0 - 1.0)
            timeout_ms: Timeout in milliseconds
            target_hwnd: Target window handle (0 for screen coords)
        """
        self.region = region
        self.threshold = threshold
        self.timeout_ms = timeout_ms
        self.target_hwnd = target_hwnd
    
    def _capture_region(self) -> Optional[bytes]:
        """Capture region as raw pixel data"""
        try:
            import mss
            
            x1, y1, x2, y2 = self.region
            
            # Convert client to screen coords if needed
            if self.target_hwnd:
                pt1 = wintypes.POINT(x1, y1)
                pt2 = wintypes.POINT(x2, y2)
                user32.ClientToScreen(self.target_hwnd, ctypes.byref(pt1))
                user32.ClientToScreen(self.target_hwnd, ctypes.byref(pt2))
                x1, y1 = pt1.x, pt1.y
                x2, y2 = pt2.x, pt2.y
            
            with mss.mss() as sct:
                monitor = {"left": x1, "top": y1, "width": x2 - x1, "height": y2 - y1}
                img = sct.grab(monitor)
                return img.raw
        except Exception as e:
            log(f"[WAIT] Screen capture error: {e}")
            return None
    
    def _calculate_difference(self, data1: bytes, data2: bytes) -> float:
        """Calculate difference ratio between two images"""
        if not data1 or not data2 or len(data1) != len(data2):
            return 1.0
        
        diff_count = 0
        total = len(data1)
        
        for i in range(0, total, 4):  # BGRA format
            if (data1[i] != data2[i] or 
                data1[i+1] != data2[i+1] or 
                data1[i+2] != data2[i+2]):
                diff_count += 1
        
        return diff_count / (total / 4)
    
    def wait(self, stop_event: threading.Event) -> WaitResult:
        """Wait until screen region changes"""
        log(f"[WAIT] WaitScreenChange: region {self.region}, threshold {self.threshold}")
        
        # Capture initial state
        initial_data = self._capture_region()
        if not initial_data:
            return WaitResult(success=False, message="Failed to capture initial screen")
        
        start_time = time.time()
        check_interval = 200  # Check every 200ms
        
        while True:
            if stop_event.is_set():
                return WaitResult(success=False, message="Stopped by user")
            
            # Check timeout
            elapsed = (time.time() - start_time) * 1000
            if elapsed >= self.timeout_ms:
                return WaitResult(success=False, timeout=True,
                                  message=f"No change detected within {self.timeout_ms}ms")
            
            # Capture current state
            current_data = self._capture_region()
            if not current_data:
                time.sleep(check_interval / 1000.0)
                continue
            
            # Calculate difference
            diff = self._calculate_difference(initial_data, current_data)
            
            if diff >= self.threshold:
                return WaitResult(success=True,
                                  message=f"Screen changed: {diff:.2%} difference")
            
            time.sleep(check_interval / 1000.0)


class WaitHotkey(WaitAction):
    """
    Wait until user presses a specific hotkey
    Per spec B1-4: WaitHotkey(key_combo: str, timeout_ms: int)
    """
    
    def __init__(self, key_combo: str, timeout_ms: int = 0):
        """
        Args:
            key_combo: Key combination (e.g., "ctrl+shift+a", "F5")
            timeout_ms: Timeout in milliseconds (0 = no timeout)
        """
        self.key_combo = key_combo.lower()
        self.timeout_ms = timeout_ms
        self._triggered = threading.Event()
    
    def _parse_key_combo(self) -> Tuple[set, str]:
        """Parse key combo into modifiers and key"""
        parts = self.key_combo.split('+')
        
        modifiers = set()
        key = ""
        
        for part in parts:
            part = part.strip()
            if part in ('ctrl', 'control'):
                modifiers.add('ctrl')
            elif part in ('alt',):
                modifiers.add('alt')
            elif part in ('shift',):
                modifiers.add('shift')
            elif part in ('win', 'super', 'meta'):
                modifiers.add('win')
            else:
                key = part
        
        return modifiers, key
    
    def wait(self, stop_event: threading.Event) -> WaitResult:
        """Wait for hotkey press"""
        log(f"[WAIT] WaitHotkey: waiting for {self.key_combo}")
        
        from pynput import keyboard
        
        expected_modifiers, expected_key = self._parse_key_combo()
        current_modifiers: set = set()
        
        def on_press(key):
            nonlocal current_modifiers
            
            try:
                # Check for modifier keys
                if key == keyboard.Key.ctrl_l or key == keyboard.Key.ctrl_r:
                    current_modifiers.add('ctrl')
                elif key == keyboard.Key.alt_l or key == keyboard.Key.alt_r:
                    current_modifiers.add('alt')
                elif key == keyboard.Key.shift or key == keyboard.Key.shift_r:
                    current_modifiers.add('shift')
                elif key == keyboard.Key.cmd or key == keyboard.Key.cmd_r:
                    current_modifiers.add('win')
                else:
                    # Get key name
                    key_name = ""
                    if hasattr(key, 'char') and key.char:
                        key_name = key.char.lower()
                    elif hasattr(key, 'name'):
                        key_name = key.name.lower()
                    
                    # Check if combo matches
                    if (key_name == expected_key and 
                        current_modifiers == expected_modifiers):
                        self._triggered.set()
                        return False  # Stop listener
            except Exception:
                pass
        
        def on_release(key):
            nonlocal current_modifiers
            
            try:
                if key == keyboard.Key.ctrl_l or key == keyboard.Key.ctrl_r:
                    current_modifiers.discard('ctrl')
                elif key == keyboard.Key.alt_l or key == keyboard.Key.alt_r:
                    current_modifiers.discard('alt')
                elif key == keyboard.Key.shift or key == keyboard.Key.shift_r:
                    current_modifiers.discard('shift')
                elif key == keyboard.Key.cmd or key == keyboard.Key.cmd_r:
                    current_modifiers.discard('win')
            except Exception:
                pass
        
        # Start listener
        listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        listener.start()
        
        try:
            start_time = time.time()
            
            while True:
                if stop_event.is_set():
                    return WaitResult(success=False, message="Stopped by user")
                
                if self._triggered.is_set():
                    return WaitResult(success=True, 
                                      message=f"Hotkey {self.key_combo} pressed")
                
                # Check timeout
                if self.timeout_ms > 0:
                    elapsed = (time.time() - start_time) * 1000
                    if elapsed >= self.timeout_ms:
                        return WaitResult(success=False, timeout=True,
                                          message=f"Timeout after {self.timeout_ms}ms")
                
                time.sleep(0.05)  # Check every 50ms
        finally:
            listener.stop()


class WaitFile(WaitAction):
    """
    Wait until a file exists or changes
    Per spec B1-5: WaitFile(path: str, condition: str, timeout_ms: int)
    """
    
    CONDITION_EXISTS = "exists"
    CONDITION_NOT_EXISTS = "not_exists"
    CONDITION_MODIFIED = "modified"
    
    def __init__(self, 
                 path: str, 
                 condition: str = "exists",
                 timeout_ms: int = 30000):
        """
        Args:
            path: File path to check
            condition: "exists", "not_exists", or "modified"
            timeout_ms: Timeout in milliseconds
        """
        self.path = path
        self.condition = condition
        self.timeout_ms = timeout_ms
    
    def wait(self, stop_event: threading.Event) -> WaitResult:
        """Wait for file condition"""
        log(f"[WAIT] WaitFile: {self.path} condition={self.condition}")
        
        # Get initial state for "modified" condition
        initial_mtime = None
        if self.condition == self.CONDITION_MODIFIED:
            if os.path.exists(self.path):
                initial_mtime = os.path.getmtime(self.path)
            else:
                return WaitResult(success=False, 
                                  message=f"File does not exist: {self.path}")
        
        start_time = time.time()
        check_interval = 500  # Check every 500ms
        
        while True:
            if stop_event.is_set():
                return WaitResult(success=False, message="Stopped by user")
            
            # Check timeout
            elapsed = (time.time() - start_time) * 1000
            if elapsed >= self.timeout_ms:
                return WaitResult(success=False, timeout=True,
                                  message=f"Timeout after {self.timeout_ms}ms")
            
            file_exists = os.path.exists(self.path)
            
            if self.condition == self.CONDITION_EXISTS:
                if file_exists:
                    return WaitResult(success=True, 
                                      message=f"File exists: {self.path}")
            
            elif self.condition == self.CONDITION_NOT_EXISTS:
                if not file_exists:
                    return WaitResult(success=True,
                                      message=f"File removed: {self.path}")
            
            elif self.condition == self.CONDITION_MODIFIED:
                if file_exists:
                    current_mtime = os.path.getmtime(self.path)
                    if initial_mtime is not None and current_mtime != initial_mtime:
                        return WaitResult(success=True,
                                          message=f"File modified: {self.path}")
            
            time.sleep(check_interval / 1000.0)


def create_wait_action(action_type: str, params: dict) -> Optional[WaitAction]:
    """
    Factory function to create wait actions from parameters
    
    Args:
        action_type: Type of wait action
        params: Dictionary of parameters
        
    Returns:
        WaitAction instance or None if invalid
    """
    try:
        if action_type == "WaitTime":
            return WaitTime(
                delay_ms=params.get("delay_ms", 1000),
                variance_ms=params.get("variance_ms", 0)
            )
        
        elif action_type == "WaitPixelColor":
            rgb = params.get("expected_rgb", (0, 0, 0))
            if isinstance(rgb, str):
                # Parse hex color
                rgb = rgb.lstrip('#')
                rgb = tuple(int(rgb[i:i+2], 16) for i in (0, 2, 4))
            return WaitPixelColor(
                x=params.get("x", 0),
                y=params.get("y", 0),
                expected_rgb=rgb,
                tolerance=params.get("tolerance", 0),
                timeout_ms=params.get("timeout_ms", 30000),
                target_hwnd=params.get("target_hwnd", 0)
            )
        
        elif action_type == "WaitScreenChange":
            region = params.get("region", (0, 0, 100, 100))
            if isinstance(region, list):
                region = tuple(region)
            return WaitScreenChange(
                region=region,
                threshold=params.get("threshold", 0.05),
                timeout_ms=params.get("timeout_ms", 30000),
                target_hwnd=params.get("target_hwnd", 0)
            )
        
        elif action_type == "WaitHotkey":
            return WaitHotkey(
                key_combo=params.get("key_combo", "F5"),
                timeout_ms=params.get("timeout_ms", 0)
            )
        
        elif action_type == "WaitFile":
            return WaitFile(
                path=params.get("path", ""),
                condition=params.get("condition", "exists"),
                timeout_ms=params.get("timeout_ms", 30000)
            )
        
        else:
            log(f"[WAIT] Unknown wait action type: {action_type}")
            return None
            
    except Exception as e:
        log(f"[WAIT] Error creating wait action: {e}")
        return None
