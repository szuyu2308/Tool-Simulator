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
    
    def _analyze_colors(self, data: bytes) -> dict:
        """Analyze color distribution in captured data"""
        if not data:
            return {}
        
        from collections import Counter
        
        color_counts = Counter()
        total_pixels = len(data) // 4
        
        # Sample every pixel (BGRA format)
        for i in range(0, len(data), 4):
            b, g, r = data[i], data[i+1], data[i+2]
            # Group similar colors (round to reduce noise)
            r_rounded = (r // 10) * 10
            g_rounded = (g // 10) * 10
            b_rounded = (b // 10) * 10
            color_counts[(r_rounded, g_rounded, b_rounded)] += 1
        
        # Get top 5 colors
        top_colors = color_counts.most_common(5)
        
        result = {
            "total_pixels": total_pixels,
            "unique_colors": len(color_counts),
            "top_colors": [
                {
                    "rgb": color,
                    "count": count,
                    "percentage": (count / total_pixels) * 100
                }
                for color, count in top_colors
            ]
        }
        
        return result
    
    def _count_color_pixels(self, data: bytes, target_rgb: Tuple[int, int, int], tolerance: int = 30) -> float:
        """Count percentage of pixels matching target color"""
        if not data:
            return 0.0
        
        match_count = 0
        total_pixels = len(data) // 4
        r_target, g_target, b_target = target_rgb
        
        for i in range(0, len(data), 4):
            b, g, r = data[i], data[i+1], data[i+2]
            
            if (abs(r - r_target) <= tolerance and
                abs(g - g_target) <= tolerance and
                abs(b - b_target) <= tolerance):
                match_count += 1
        
        return (match_count / total_pixels) if total_pixels > 0 else 0.0
    
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
        log(f"[WAIT_SCREEN_CHANGE] Starting monitor")
        log(f"  → Region: {self.region}")
        log(f"  → Threshold: {self.threshold * 100:.1f}% (change needed to pass)")
        log(f"  → Timeout: {self.timeout_ms}ms")
        
        # Capture initial state
        initial_data = self._capture_region()
        if not initial_data:
            return WaitResult(success=False, message="Failed to capture initial screen")
        
        # Analyze initial colors
        log(f"[WAIT_SCREEN_CHANGE] Baseline captured, analyzing colors...")
        color_info = self._analyze_colors(initial_data)
        log(f"[WAIT_SCREEN_CHANGE] Region stats:")
        log(f"  → Total pixels: {color_info.get('total_pixels', 0)}")
        log(f"  → Unique colors: {color_info.get('unique_colors', 0)}")
        log(f"[WAIT_SCREEN_CHANGE] Top 5 colors (rounded to ±10):")
        for idx, color_data in enumerate(color_info.get('top_colors', []), 1):
            rgb = color_data['rgb']
            pct = color_data['percentage']
            log(f"  {idx}. RGB{rgb} → {pct:.2f}%")
        
        log(f"[WAIT_SCREEN_CHANGE] Monitoring changes...")
        
        start_time = time.time()
        check_interval = 200  # Check every 200ms
        check_count = 0
        
        while True:
            if stop_event.is_set():
                return WaitResult(success=False, message="Stopped by user")
            
            # Check timeout
            elapsed = (time.time() - start_time) * 1000
            if elapsed >= self.timeout_ms:
                log(f"[WAIT_SCREEN_CHANGE] ✗ TIMEOUT after {elapsed:.0f}ms ({check_count} checks)")
                return WaitResult(success=False, timeout=True,
                                  message=f"No change detected within {self.timeout_ms}ms")
            
            # Capture current state
            current_data = self._capture_region()
            if not current_data:
                time.sleep(check_interval / 1000.0)
                continue
            
            # Calculate difference
            diff = self._calculate_difference(initial_data, current_data)
            check_count += 1
            
            # Analyze current colors every 5 checks (every ~1 second)
            if check_count % 5 == 0:
                current_colors = self._analyze_colors(current_data)
                top_color = current_colors.get('top_colors', [{}])[0]
                if top_color:
                    rgb = top_color.get('rgb', (0,0,0))
                    pct = top_color.get('percentage', 0)
                    log(f"[WAIT_SCREEN_CHANGE] Check #{check_count}: {diff*100:.2f}% changed | Top color: RGB{rgb} ({pct:.1f}%)")
            else:
                log(f"[WAIT_SCREEN_CHANGE] Check #{check_count}: {diff*100:.2f}% changed (need {self.threshold*100:.1f}%)")
            
            if diff >= self.threshold:
                # Log final color info when passed
                final_colors = self._analyze_colors(current_data)
                log(f"[WAIT_SCREEN_CHANGE] ✓ PASSED! Change detected: {diff*100:.2f}% after {elapsed:.0f}ms")
                log(f"[WAIT_SCREEN_CHANGE] Final top color: RGB{final_colors.get('top_colors', [{}])[0].get('rgb', (0,0,0))}")
                return WaitResult(success=True,
                                  message=f"Screen changed: {diff:.2%} difference")
            
            time.sleep(check_interval / 1000.0)


class WaitColorDisappear(WaitAction):
    """
    Wait until a specific color disappears from region (for spin arc detection)
    Supports auto-detect mode to track multiple top colors automatically
    """
    
    def __init__(self,
                 region: Tuple[int, int, int, int],
                 target_rgb: Tuple[int, int, int] = None,
                 tolerance: int = 30,
                 disappear_threshold: float = 0.01,
                 timeout_ms: int = 30000,
                 target_hwnd: int = 0,
                 auto_detect: bool = False,
                 auto_detect_count: int = 3,
                 stable_count_exit: int = 0):
        """
        Args:
            region: (x1, y1, x2, y2) region to monitor
            target_rgb: RGB color to track (ignored if auto_detect=True)
            tolerance: Color matching tolerance (0-255 per channel)
            disappear_threshold: When color % drops below this, consider disappeared (0.01 = 1%)
            timeout_ms: Timeout in milliseconds
            target_hwnd: Target window handle
            auto_detect: Auto-detect top colors from baseline
            auto_detect_count: Number of top colors to track (default 3)
            stable_count_exit: If N consecutive checks have identical values, exit (0 = disabled)
        """
        self.region = region
        self.target_rgb = target_rgb
        self.tolerance = tolerance
        self.disappear_threshold = disappear_threshold
        self.timeout_ms = timeout_ms
        self.target_hwnd = target_hwnd
        self.auto_detect = auto_detect
        self.auto_detect_count = auto_detect_count
        self.stable_count_exit = stable_count_exit
        self.tracked_colors = []  # Will be populated if auto_detect=True
    
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
            
            log(f"[WAIT_COLOR_DISAPPEAR] Debug: Capture coords: ({x1}, {y1}) → ({x2}, {y2}), size: {x2-x1}x{y2-y1}")
            
            with mss.mss() as sct:
                monitor = {"left": x1, "top": y1, "width": x2 - x1, "height": y2 - y1}
                img = sct.grab(monitor)
                return img.raw
        except Exception as e:
            log(f"[WAIT_COLOR] Capture error: {e}")
            return None
    
    def _analyze_top_colors(self, data: bytes, count: int = 3) -> list:
        """Analyze and return top N colors from data"""
        if not data:
            return []
        
        from collections import Counter
        
        color_counts = Counter()
        
        # Sample every pixel (BGRA format)
        for i in range(0, len(data), 4):
            b, g, r = data[i], data[i+1], data[i+2]
            # Don't round - use exact colors to avoid everything becoming (0,0,0)
            color_counts[(r, g, b)] += 1
        
        # Filter out pure black/white (likely background)
        filtered_colors = [(color, cnt) for color, cnt in color_counts.items() 
                          if color != (0, 0, 0) and color != (255, 255, 255)]
        
        # If all colors filtered, use original
        if not filtered_colors:
            filtered_colors = list(color_counts.items())
        
        # Get top N colors
        top_colors = sorted(filtered_colors, key=lambda x: x[1], reverse=True)[:count]
        total_pixels = len(data) // 4
        
        result = []
        for color, pixel_count in top_colors:
            percentage = (pixel_count / total_pixels) * 100
            result.append({
                "rgb": color,
                "count": pixel_count,
                "percentage": percentage
            })
        
        # Log all unique colors for debugging
        log(f"[WAIT_COLOR_DISAPPEAR] Debug: Total unique colors in region: {len(color_counts)}")
        if len(color_counts) <= 20:
            log(f"[WAIT_COLOR_DISAPPEAR] Debug: All colors found:")
            for idx, (color, cnt) in enumerate(sorted(color_counts.items(), key=lambda x: x[1], reverse=True)[:20], 1):
                pct = (cnt / total_pixels) * 100
                log(f"    {idx}. RGB{color} → {pct:.2f}%")
        
        return result
    
    def _count_color_pixels(self, data: bytes, target_rgb: Tuple[int, int, int] = None) -> float:
        """Count percentage of pixels matching target color(s)"""
        if not data:
            return 0.0
        
        # If auto-detect mode, count all tracked colors
        if self.auto_detect and self.tracked_colors:
            match_count = 0
            total_pixels = len(data) // 4
            
            for i in range(0, len(data), 4):
                b, g, r = data[i], data[i+1], data[i+2]
                
                # Check if pixel matches any tracked color
                for color_info in self.tracked_colors:
                    r_target, g_target, b_target = color_info["rgb"]
                    if (abs(r - r_target) <= self.tolerance and
                        abs(g - g_target) <= self.tolerance and
                        abs(b - b_target) <= self.tolerance):
                        match_count += 1
                        break  # Don't double-count same pixel
            
            return (match_count / total_pixels) if total_pixels > 0 else 0.0
        
        # Manual mode - count single color
        if target_rgb is None:
            target_rgb = self.target_rgb
        
        match_count = 0
        total_pixels = len(data) // 4
        r_target, g_target, b_target = target_rgb
        
        for i in range(0, len(data), 4):
            b, g, r = data[i], data[i+1], data[i+2]
            
            if (abs(r - r_target) <= self.tolerance and
                abs(g - g_target) <= self.tolerance and
                abs(b - b_target) <= self.tolerance):
                match_count += 1
        
        return (match_count / total_pixels) if total_pixels > 0 else 0.0
    
    def wait(self, stop_event: threading.Event) -> WaitResult:
        """Wait until target color(s) disappear"""
        log(f"[WAIT_COLOR_DISAPPEAR] Starting monitor")
        log(f"  → Region: {self.region}")
        log(f"  → Tolerance: ±{self.tolerance}")
        log(f"  → Disappear threshold: {self.disappear_threshold*100:.1f}%")
        log(f"  → Timeout: {self.timeout_ms}ms")
        
        # Auto-detect mode: Find ANIMATED colors (high variance) vs static colors (low variance)
        if self.auto_detect:
            log(f"[WAIT_COLOR_DISAPPEAR] 🔍 Auto-detecting ANIMATED colors (spin arc)...")
            
            # Take 5 samples over 2 seconds
            samples = []
            sample_interval = 0.4  # 400ms between samples = 2 seconds total
            
            for i in range(5):
                if stop_event.is_set():
                    return WaitResult(success=False, message="Stopped by user")
                
                data = self._capture_region()
                if not data:
                    return WaitResult(success=False, message="Failed to capture sample")
                
                # Count percentage for each unique color
                from collections import Counter
                color_counts = Counter()
                for j in range(0, len(data), 4):
                    b, g, r = data[j], data[j+1], data[j+2]
                    color_counts[(r, g, b)] += 1
                
                total_pixels = len(data) // 4
                color_percentages = {color: (count / total_pixels) * 100 
                                   for color, count in color_counts.items()}
                samples.append(color_percentages)
                
                log(f"[WAIT_COLOR_DISAPPEAR] Sample {i+1}/5: {len(color_counts)} unique colors")
                
                if i < 4:  # Don't sleep after last sample
                    time.sleep(sample_interval)
            
            # Calculate variance for each color
            all_colors = set()
            for sample in samples:
                all_colors.update(sample.keys())
            
            color_variances = {}
            for color in all_colors:
                # Get percentages across all 5 samples (0 if color not present)
                percentages = [sample.get(color, 0.0) for sample in samples]
                avg = sum(percentages) / len(percentages)
                variance = sum((p - avg) ** 2 for p in percentages) / len(percentages)
                color_variances[color] = {
                    'variance': variance,
                    'avg_percentage': avg,
                    'percentages': percentages
                }
            
            # Filter: Only keep colors with HIGH variance (animated = spin arc)
            # Static colors (background) have variance ~0
            variance_threshold = 1.0  # Colors with variance > 1.0% are animated
            animated_colors = [(color, data) for color, data in color_variances.items() 
                             if data['variance'] > variance_threshold]
            
            # Sort by variance (most animated first)
            animated_colors.sort(key=lambda x: x[1]['variance'], reverse=True)
            
            # Filter out black/white
            animated_colors = [(color, data) for color, data in animated_colors
                             if color != (0, 0, 0) and color != (255, 255, 255)]
            
            if not animated_colors:
                log(f"[WAIT_COLOR_DISAPPEAR] ⚠️ No animated colors found (all colors static)")
                log(f"[WAIT_COLOR_DISAPPEAR] This may not be a spinning arc region")
                # Fall back to tracking top colors by percentage
                last_sample_colors = self._analyze_top_colors(self._capture_region(), self.auto_detect_count)
                self.tracked_colors = last_sample_colors
            else:
                # Track top N animated colors
                top_animated = animated_colors[:self.auto_detect_count]
                self.tracked_colors = [
                    {
                        'rgb': color,
                        'percentage': data['avg_percentage'],
                        'variance': data['variance']
                    }
                    for color, data in top_animated
                ]
            
            log(f"[WAIT_COLOR_DISAPPEAR] Tracking {len(self.tracked_colors)} ANIMATED colors:")
            for idx, color_info in enumerate(self.tracked_colors, 1):
                rgb = color_info['rgb']
                avg_pct = color_info.get('percentage', 0)
                var = color_info.get('variance', 0)
                log(f"  {idx}. RGB{rgb} → Avg: {avg_pct:.2f}%, Variance: {var:.2f}%")
        else:
            # Manual mode - log target color
            log(f"  → Target RGB: {self.target_rgb}")
        
        # Capture fresh baseline after auto-detect
        initial_data = self._capture_region()
        if not initial_data:
            return WaitResult(success=False, message="Failed to capture baseline")
        
        # Check initial percentage
        initial_percentage = self._count_color_pixels(initial_data)
        baseline_percentage = initial_percentage * 100
        log(f"[WAIT_COLOR_DISAPPEAR] Baseline: {baseline_percentage:.2f}% of tracked color(s) remaining")
        
        start_time = time.time()
        check_interval = 200  # Check every 200ms
        check_count = 0
        
        # Track recent percentages for stability check
        recent_pcts = []
        stability_window = 5  # Check last 5 samples
        
        # Track consecutive identical values for stable exit
        last_pct = None
        identical_count = 0
        
        while True:
            if stop_event.is_set():
                return WaitResult(success=False, message="Stopped by user")
            
            # Check timeout
            elapsed = (time.time() - start_time) * 1000
            if elapsed >= self.timeout_ms:
                log(f"[WAIT_COLOR_DISAPPEAR] ✗ TIMEOUT after {elapsed:.0f}ms")
                return WaitResult(success=False, timeout=True,
                                  message=f"Color did not disappear within {self.timeout_ms}ms")
            
            # Capture and check color percentage
            current_data = self._capture_region()
            if not current_data:
                time.sleep(check_interval / 1000.0)
                continue
            
            color_pct = self._count_color_pixels(current_data)
            check_count += 1
            recent_pcts.append(color_pct)
            
            # Track identical consecutive values
            if self.stable_count_exit > 0:
                pct_rounded = round(color_pct * 100, 2)  # Round to 2 decimals
                if last_pct is not None and pct_rounded == last_pct:
                    identical_count += 1
                else:
                    identical_count = 1
                    last_pct = pct_rounded
                
                # Exit if same value repeated N times (spin arc gone, only static background)
                if identical_count >= self.stable_count_exit:
                    log(f"[WAIT_COLOR_DISAPPEAR] ✓ STABLE EXIT: Value {pct_rounded:.2f}% repeated {identical_count} times")
                    log(f"[WAIT_COLOR_DISAPPEAR] Spin arc disappeared, only static background remains")
                    return WaitResult(success=True, 
                                    message=f"Stable background detected after {elapsed:.0f}ms")
            
            # Keep only last N samples
            if len(recent_pcts) > stability_window:
                recent_pcts.pop(0)
            
            # Calculate stability (variance of recent checks)
            if len(recent_pcts) >= stability_window:
                avg_pct = sum(recent_pcts) / len(recent_pcts)
                variance = max(recent_pcts) - min(recent_pcts)
                
                log(f"[WAIT_COLOR_DISAPPEAR] Check #{check_count}: {color_pct*100:.2f}% | Avg: {avg_pct*100:.2f}%, Variance: {variance*100:.2f}%")
                
                # Check if stable + low (spin arc disappeared and stabilized)
                # Stable: variance < 0.5% over last 5 checks
                # Low: average < disappear_threshold * 2 (with some headroom)
                stable_threshold = 0.005  # 0.5% variance
                low_threshold = self.disappear_threshold * 2  # 2x disappear threshold
                
                if variance <= stable_threshold and avg_pct <= low_threshold:
                    log(f"[WAIT_COLOR_DISAPPEAR] ✓ STABLE & LOW! Avg: {avg_pct*100:.2f}%, Variance: {variance*100:.2f}% after {elapsed:.0f}ms")
                    return WaitResult(success=True,
                                      message=f"Color disappeared and stable: {avg_pct:.2%} avg")
            else:
                log(f"[WAIT_COLOR_DISAPPEAR] Check #{check_count}: {color_pct*100:.2f}% pixels match (collecting stability data...)")
            
            # Also check simple threshold for quick detection (if goes below threshold immediately)
            if color_pct <= self.disappear_threshold:
                log(f"[WAIT_COLOR_DISAPPEAR] ✓ COLOR DISAPPEARED! {color_pct*100:.2f}% after {elapsed:.0f}ms")
                return WaitResult(success=True,
                                  message=f"Color disappeared: {color_pct:.2%} remaining")
            
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
