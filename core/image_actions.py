# AI GOVERNANCE:
# Apply auditor-router
# This is a CODE change

"""
Image Actions Module — per UPGRADE_PLAN_V2 spec B2
Implements: FindImage, CaptureImage with OpenCV template matching
"""

from __future__ import annotations
import os
import time
import threading
from typing import Optional, Tuple, List
from dataclasses import dataclass
import ctypes
from ctypes import wintypes
from pathlib import Path

from utils.logger import log

user32 = ctypes.windll.user32

# Optional OpenCV import
try:
    import cv2
    import numpy as np
    HAS_OPENCV = True
except ImportError:
    HAS_OPENCV = False
    log("[IMAGE] OpenCV not available - image actions disabled")


@dataclass
class ImageMatch:
    """Result of image matching"""
    found: bool
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0
    confidence: float = 0.0
    center_x: int = 0
    center_y: int = 0


@dataclass
class CaptureImageResult:
    """Result of image capture"""
    success: bool
    path: str = ""
    width: int = 0
    height: int = 0
    message: str = ""


def _capture_screen_region(region: Optional[Tuple[int, int, int, int]] = None,
                           target_hwnd: int = 0) -> Optional['np.ndarray']:
    """
    Capture screen region as numpy array
    
    Args:
        region: (x1, y1, x2, y2) or None for full screen
        target_hwnd: Target window handle for coord conversion
        
    Returns:
        numpy array (BGR format) or None
    """
    if not HAS_OPENCV:
        return None
    
    try:
        import mss
        
        with mss.mss() as sct:
            if region:
                x1, y1, x2, y2 = region
                
                # Convert client to screen coords if needed
                if target_hwnd:
                    pt1 = wintypes.POINT(x1, y1)
                    pt2 = wintypes.POINT(x2, y2)
                    user32.ClientToScreen(target_hwnd, ctypes.byref(pt1))
                    user32.ClientToScreen(target_hwnd, ctypes.byref(pt2))
                    x1, y1 = pt1.x, pt1.y
                    x2, y2 = pt2.x, pt2.y
                
                monitor = {
                    "left": x1,
                    "top": y1,
                    "width": x2 - x1,
                    "height": y2 - y1
                }
            else:
                # Full primary monitor
                monitor = sct.monitors[1]
            
            img = sct.grab(monitor)
            
            # Convert to numpy array (BGR format for OpenCV)
            arr = np.array(img)
            # MSS captures BGRA, convert to BGR
            return cv2.cvtColor(arr, cv2.COLOR_BGRA2BGR)
            
    except Exception as e:
        log(f"[IMAGE] Capture error: {e}")
        return None


def _capture_window(hwnd: int) -> Optional['np.ndarray']:
    """
    Capture specific window content
    
    Args:
        hwnd: Window handle
        
    Returns:
        numpy array (BGR format) or None
    """
    if not HAS_OPENCV:
        return None
    
    try:
        # Get window rect
        rect = wintypes.RECT()
        user32.GetClientRect(hwnd, ctypes.byref(rect))
        
        # Get window position
        pt = wintypes.POINT(0, 0)
        user32.ClientToScreen(hwnd, ctypes.byref(pt))
        
        x1, y1 = pt.x, pt.y
        x2 = x1 + rect.right
        y2 = y1 + rect.bottom
        
        return _capture_screen_region((x1, y1, x2, y2), target_hwnd=0)
        
    except Exception as e:
        log(f"[IMAGE] Window capture error: {e}")
        return None


class FindImage:
    """
    Find template image on screen using OpenCV template matching
    Per spec B2-1: FindImage(template_path, region, threshold, timeout_ms, method)
    """
    
    METHOD_TM_CCOEFF_NORMED = cv2.TM_CCOEFF_NORMED if HAS_OPENCV else 5
    METHOD_TM_SQDIFF_NORMED = cv2.TM_SQDIFF_NORMED if HAS_OPENCV else 1
    
    def __init__(self,
                 template_path: str,
                 region: Optional[Tuple[int, int, int, int]] = None,
                 threshold: float = 0.8,
                 timeout_ms: int = 5000,
                 target_hwnd: int = 0,
                 method: int = 5):  # TM_CCOEFF_NORMED
        """
        Args:
            template_path: Path to template image file
            region: (x1, y1, x2, y2) search region or None for full screen
            threshold: Confidence threshold (0.0 - 1.0)
            timeout_ms: Search timeout in milliseconds
            target_hwnd: Target window handle (0 for screen)
            method: OpenCV matching method
        """
        self.template_path = template_path
        self.region = region
        self.threshold = threshold
        self.timeout_ms = timeout_ms
        self.target_hwnd = target_hwnd
        self.method = method
        
        self._template: Optional['np.ndarray'] = None
    
    def _load_template(self) -> bool:
        """Load template image"""
        if not HAS_OPENCV:
            log("[IMAGE] OpenCV not available")
            return False
        
        if not os.path.exists(self.template_path):
            log(f"[IMAGE] Template not found: {self.template_path}")
            return False
        
        try:
            self._template = cv2.imread(self.template_path)
            if self._template is None:
                log(f"[IMAGE] Failed to load template: {self.template_path}")
                return False
            return True
        except Exception as e:
            log(f"[IMAGE] Template load error: {e}")
            return False
    
    def _verify_match(self, screen: 'np.ndarray', top_left: Tuple[int, int]) -> float:
        """
        Verify match by extracting the matched region and comparing with template.
        Returns verified confidence score.
        """
        if self._template is None:
            return 0.0
        
        h, w = self._template.shape[:2]
        x, y = top_left
        
        # Check bounds
        if y + h > screen.shape[0] or x + w > screen.shape[1]:
            return 0.0
        
        # Extract matched region from screenshot
        matched_region = screen[y:y+h, x:x+w]
        
        # Compare using multiple methods for robust verification
        try:
            # Method 1: Normalized cross-correlation
            result = cv2.matchTemplate(matched_region, self._template, cv2.TM_CCOEFF_NORMED)
            ncc_score = result[0, 0] if result.size > 0 else 0.0
            
            # Method 2: Structural similarity (pixel difference)
            diff = cv2.absdiff(matched_region, self._template)
            gray_diff = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY) if len(diff.shape) == 3 else diff
            similarity = 1.0 - (np.mean(gray_diff) / 255.0)
            
            # Combined score (weighted average)
            verified_confidence = 0.7 * ncc_score + 0.3 * similarity
            
            return max(0.0, min(1.0, verified_confidence))
            
        except Exception as e:
            log(f"[IMAGE] Verify match error: {e}")
            return 0.0
    
    def find_once(self) -> ImageMatch:
        """
        Search for template once (no timeout)
        Verifies match by comparing extracted region with template.
        
        Returns:
            ImageMatch result
        """
        if not HAS_OPENCV:
            return ImageMatch(found=False)
        
        if self._template is None:
            if not self._load_template():
                return ImageMatch(found=False)
        
        # Capture screen/region
        offset_x = 0
        offset_y = 0
        
        if self.target_hwnd:
            # Capture full window
            screen = _capture_window(self.target_hwnd)
            
            # If region specified, crop the screenshot to region
            if screen is not None and self.region:
                x1, y1, x2, y2 = self.region
                # Validate region bounds
                if y2 > screen.shape[0]:
                    y2 = screen.shape[0]
                if x2 > screen.shape[1]:
                    x2 = screen.shape[1]
                if x1 >= x2 or y1 >= y2:
                    log(f"[IMAGE] Invalid region: ({x1},{y1},{x2},{y2})")
                    return ImageMatch(found=False)
                    
                # Region is in client coords, crop from full window screenshot
                screen = screen[y1:y2, x1:x2]
                # Save offset for later coordinate adjustment
                offset_x = x1
                offset_y = y1
                log(f"[IMAGE] Searching in region ({x1},{y1})-({x2},{y2}), cropped size: {screen.shape[1]}x{screen.shape[0]}")
        else:
            # Screen capture mode
            screen = _capture_screen_region(self.region, self.target_hwnd)
            # If region specified, offset is already in region coords
            if self.region:
                offset_x = self.region[0]
                offset_y = self.region[1]
        
        if screen is None:
            return ImageMatch(found=False)
        
        # Check if template fits in search area
        th, tw = self._template.shape[:2]
        sh, sw = screen.shape[:2]
        if tw > sw or th > sh:
            log(f"[IMAGE] Template ({tw}x{th}) larger than search area ({sw}x{sh})")
            return ImageMatch(found=False)
        
        # Template matching
        try:
            result = cv2.matchTemplate(screen, self._template, self.method)
            
            # Find best match
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
            
            # For TM_SQDIFF methods, minimum is best match
            if self.method in (cv2.TM_SQDIFF, cv2.TM_SQDIFF_NORMED):
                initial_confidence = 1.0 - min_val
                top_left = min_loc
            else:
                initial_confidence = max_val
                top_left = max_loc
            
            log(f"[IMAGE] Template match at ({top_left[0]},{top_left[1]}) initial_conf={initial_confidence:.3f}")
            
            # VERIFY: Extract matched region and compare with template
            verified_confidence = self._verify_match(screen, top_left)
            log(f"[IMAGE] Verified confidence: {verified_confidence:.3f} (threshold={self.threshold})")
            
            # Use verified confidence for final decision
            if verified_confidence >= self.threshold:
                h, w = self._template.shape[:2]
                
                # Calculate absolute position in window/screen coords
                # top_left is relative to cropped screenshot, add offset to get absolute coords
                x = top_left[0] + offset_x
                y = top_left[1] + offset_y
                
                log(f"[IMAGE] MATCH VERIFIED at ({x},{y}) conf={verified_confidence:.3f}")
                
                return ImageMatch(
                    found=True,
                    x=x,
                    y=y,
                    width=w,
                    height=h,
                    confidence=verified_confidence,
                    center_x=x + w // 2,
                    center_y=y + h // 2
                )
            
            log(f"[IMAGE] Match rejected: verified_conf={verified_confidence:.3f} < threshold={self.threshold}")
            return ImageMatch(found=False, confidence=verified_confidence)
            
        except Exception as e:
            log(f"[IMAGE] Template matching error: {e}")
            return ImageMatch(found=False)
    
    def find(self, stop_event: Optional[threading.Event] = None) -> ImageMatch:
        """
        Search for template with timeout
        
        Args:
            stop_event: Optional event to check for stop signal
            
        Returns:
            ImageMatch result
        """
        log(f"[IMAGE] FindImage: {self.template_path}, threshold={self.threshold}")
        
        if not self._load_template():
            return ImageMatch(found=False)
        
        start_time = time.time()
        check_interval = 100  # Check every 100ms
        
        while True:
            if stop_event and stop_event.is_set():
                return ImageMatch(found=False)
            
            # Check timeout
            elapsed = (time.time() - start_time) * 1000
            if elapsed >= self.timeout_ms:
                log(f"[IMAGE] FindImage timeout after {self.timeout_ms}ms")
                return ImageMatch(found=False)
            
            # Search
            match = self.find_once()
            if match.found:
                log(f"[IMAGE] Found at ({match.x}, {match.y}) confidence={match.confidence:.2f}")
                return match
            
            time.sleep(check_interval / 1000.0)
    
    def find_all(self, max_results: int = 10) -> List[ImageMatch]:
        """
        Find all occurrences of template
        
        Args:
            max_results: Maximum number of results
            
        Returns:
            List of ImageMatch results
        """
        if not HAS_OPENCV:
            return []
        
        if self._template is None:
            if not self._load_template():
                return []
        
        # Capture screen/region
        offset_x = 0
        offset_y = 0
        
        if self.target_hwnd:
            # Capture full window
            screen = _capture_window(self.target_hwnd)
            
            # If region specified, crop the screenshot to region
            if screen is not None and self.region:
                x1, y1, x2, y2 = self.region
                # Region is in client coords, crop from full window screenshot
                screen = screen[y1:y2, x1:x2]
                # Save offset for later coordinate adjustment
                offset_x = x1
                offset_y = y1
        else:
            # Screen capture mode
            screen = _capture_screen_region(self.region, self.target_hwnd)
            # If region specified, offset is already in region coords
            if self.region:
                offset_x = self.region[0]
                offset_y = self.region[1]
        
        if screen is None:
            return []
        
        try:
            result = cv2.matchTemplate(screen, self._template, self.method)
            h, w = self._template.shape[:2]
            
            matches = []
            
            # Find locations above threshold
            if self.method in (cv2.TM_SQDIFF, cv2.TM_SQDIFF_NORMED):
                locations = np.where(result <= (1 - self.threshold))
            else:
                locations = np.where(result >= self.threshold)
            
            for pt in zip(*locations[::-1]):
                x, y = pt
                
                # Get confidence at this location
                confidence = result[y, x]
                if self.method in (cv2.TM_SQDIFF, cv2.TM_SQDIFF_NORMED):
                    confidence = 1.0 - confidence
                
                # Calculate absolute position in window/screen coords
                # x, y are relative to cropped screenshot, add offset to get absolute coords
                match = ImageMatch(
                    found=True,
                    x=x + offset_x,
                    y=y + offset_y,
                    width=w,
                    height=h,
                    confidence=confidence,
                    center_x=x + offset_x + w // 2,
                    center_y=y + offset_y + h // 2
                )
                matches.append(match)
                
                if len(matches) >= max_results:
                    break
            
            # Sort by confidence (descending)
            matches.sort(key=lambda m: m.confidence, reverse=True)
            
            return matches
            
        except Exception as e:
            log(f"[IMAGE] Find all error: {e}")
            return []


class CaptureImage:
    """
    Capture screen region and save to file
    Per spec B2-2: CaptureImage(region, save_path, format)
    """
    
    def __init__(self,
                 region: Optional[Tuple[int, int, int, int]] = None,
                 save_path: str = "",
                 format: str = "png",
                 target_hwnd: int = 0):
        """
        Args:
            region: (x1, y1, x2, y2) capture region or None for full screen
            save_path: Path to save image (auto-generated if empty)
            format: Image format (png, jpg, bmp)
            target_hwnd: Target window handle for coord conversion
        """
        self.region = region
        self.save_path = save_path
        self.format = format.lower()
        self.target_hwnd = target_hwnd
    
    def capture(self) -> CaptureImageResult:
        """
        Capture and save image
        
        Returns:
            CaptureImageResult
        """
        if not HAS_OPENCV:
            return CaptureImageResult(
                success=False,
                message="OpenCV not available"
            )
        
        log(f"[IMAGE] CaptureImage: region={self.region}")
        
        # Capture screen
        if self.target_hwnd and self.region is None:
            screen = _capture_window(self.target_hwnd)
        else:
            screen = _capture_screen_region(self.region, self.target_hwnd)
        
        if screen is None:
            return CaptureImageResult(
                success=False,
                message="Failed to capture screen"
            )
        
        # Generate path if not provided
        save_path = self.save_path
        if not save_path:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            save_path = f"capture_{timestamp}.{self.format}"
        
        # Ensure directory exists
        save_dir = os.path.dirname(save_path)
        if save_dir and not os.path.exists(save_dir):
            os.makedirs(save_dir, exist_ok=True)
        
        # Save image
        try:
            success = cv2.imwrite(save_path, screen)
            
            if success:
                h, w = screen.shape[:2]
                return CaptureImageResult(
                    success=True,
                    path=save_path,
                    width=w,
                    height=h,
                    message=f"Saved to {save_path}"
                )
            else:
                return CaptureImageResult(
                    success=False,
                    message=f"Failed to save to {save_path}"
                )
                
        except Exception as e:
            return CaptureImageResult(
                success=False,
                message=f"Save error: {e}"
            )


def find_image(template_path: str,
               region: Optional[Tuple[int, int, int, int]] = None,
               threshold: float = 0.8,
               timeout_ms: int = 5000,
               target_hwnd: int = 0) -> ImageMatch:
    """
    Convenience function to find an image
    
    Args:
        template_path: Path to template image
        region: Search region or None for full screen
        threshold: Confidence threshold
        timeout_ms: Timeout in milliseconds
        target_hwnd: Target window handle
        
    Returns:
        ImageMatch result
    """
    finder = FindImage(
        template_path=template_path,
        region=region,
        threshold=threshold,
        timeout_ms=timeout_ms,
        target_hwnd=target_hwnd
    )
    return finder.find()


def capture_image(region: Optional[Tuple[int, int, int, int]] = None,
                  save_path: str = "",
                  format: str = "png",
                  target_hwnd: int = 0) -> CaptureImageResult:
    """
    Convenience function to capture an image
    
    Args:
        region: Capture region or None for full screen
        save_path: Path to save image
        format: Image format
        target_hwnd: Target window handle
        
    Returns:
        CaptureImageResult
    """
    capturer = CaptureImage(
        region=region,
        save_path=save_path,
        format=format,
        target_hwnd=target_hwnd
    )
    return capturer.capture()


def image_actions_available() -> bool:
    """Check if image actions are available (OpenCV installed)"""
    return HAS_OPENCV
