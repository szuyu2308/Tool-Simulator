# AI GOVERNANCE:
# Apply auditor-router
# This is a CODE change

"""
Capture UX Utilities — XY and Region capture per UPGRADE_PLAN_V2 spec C
Provides silent capture (no popup) with UI hiding
"""

from __future__ import annotations
import tkinter as tk
from tkinter import ttk
import ctypes
from ctypes import wintypes
import threading
import time
from typing import Optional, Tuple, Callable
from dataclasses import dataclass

from utils.logger import log

user32 = ctypes.windll.user32


@dataclass
class CaptureResult:
    """Result of capture operation"""
    success: bool
    x: int = 0
    y: int = 0
    x2: int = 0  # For region capture
    y2: int = 0  # For region capture
    hwnd: int = 0  # Target window
    client_coords: bool = True  # True if coords are client, False if screen


class CaptureOverlay:
    """
    Fullscreen transparent overlay for capture operations
    Per spec C1, C2: No popup, hide UI while capturing
    """
    
    def __init__(self, root: tk.Tk, target_hwnd: Optional[int] = None):
        """
        Initialize capture overlay
        
        Args:
            root: Parent Tk root window
            target_hwnd: Optional target window for client coord conversion
        """
        self._root = root
        self._target_hwnd = target_hwnd
        self._overlay: Optional[tk.Toplevel] = None
        self._canvas: Optional[tk.Canvas] = None
        self._result: Optional[CaptureResult] = None
        self._callback: Optional[Callable[[CaptureResult], None]] = None
        
        # Region capture state
        self._start_x = 0
        self._start_y = 0
        self._rect_id = None
        self._size_text_id = None
        self._is_dragging = False
        
        # Mode
        self._mode = "xy"  # "xy" or "region"
    
    def capture_xy(self, callback: Callable[[CaptureResult], None]):
        """
        Capture single XY position per spec C1
        - Hide UI immediately
        - Show crosshair cursor
        - User click -> capture position
        - Restore UI
        
        Args:
            callback: Function to call with CaptureResult
        """
        self._mode = "xy"
        self._callback = callback
        self._show_overlay()
    
    def capture_region(self, callback: Callable[[CaptureResult], None]):
        """
        Capture region (snipping-tool style) per spec C2
        - Snipping overlay (topmost, transparent)
        - Click-drag to draw rectangle
        - Show live rectangle border + size
        - Release mouse -> return coords
        
        Args:
            callback: Function to call with CaptureResult
        """
        self._mode = "region"
        self._callback = callback
        self._show_overlay()
    
    def _show_overlay(self):
        """Show fullscreen capture overlay"""
        # Hide main window first (per spec C1, C2)
        self._root.withdraw()
        self._root.update()
        
        # Small delay for window to hide
        time.sleep(0.1)
        
        # Create fullscreen overlay
        self._overlay = tk.Toplevel(self._root)
        self._overlay.attributes('-fullscreen', True)
        self._overlay.attributes('-topmost', True)
        self._overlay.attributes('-alpha', 0.3)  # Semi-transparent
        self._overlay.configure(bg='black')
        
        # Remove window decorations
        self._overlay.overrideredirect(True)
        
        # Create canvas for drawing
        screen_w = self._overlay.winfo_screenwidth()
        screen_h = self._overlay.winfo_screenheight()
        
        self._canvas = tk.Canvas(
            self._overlay, 
            width=screen_w, 
            height=screen_h,
            bg='gray20',
            highlightthickness=0
        )
        self._canvas.pack(fill="both", expand=True)
        
        # Set cursor based on mode
        if self._mode == "xy":
            self._overlay.config(cursor="crosshair")
            self._canvas.create_text(
                screen_w // 2, 50,
                text="Click to capture position (ESC to cancel)",
                fill="white", font=("Arial", 16, "bold")
            )
        else:
            self._overlay.config(cursor="cross")
            self._canvas.create_text(
                screen_w // 2, 50,
                text="Click and drag to select region (ESC to cancel)",
                fill="white", font=("Arial", 16, "bold")
            )
        
        # Bind events
        self._canvas.bind("<Button-1>", self._on_click)
        self._canvas.bind("<B1-Motion>", self._on_drag)
        self._canvas.bind("<ButtonRelease-1>", self._on_release)
        self._overlay.bind("<Escape>", self._on_cancel)
        
        # Focus overlay
        self._overlay.focus_force()
    
    def _on_click(self, event):
        """Handle mouse click"""
        if self._mode == "xy":
            # Single click capture
            self._finish_capture(event.x_root, event.y_root)
        else:
            # Start region selection
            self._start_x = event.x_root
            self._start_y = event.y_root
            self._is_dragging = True
            
            # Draw initial rectangle
            self._rect_id = self._canvas.create_rectangle(
                event.x, event.y, event.x, event.y,
                outline="red", width=2
            )
            self._size_text_id = self._canvas.create_text(
                event.x + 5, event.y - 15,
                text="0 x 0", fill="yellow", font=("Arial", 10), anchor="nw"
            )
    
    def _on_drag(self, event):
        """Handle mouse drag (for region selection)"""
        if self._mode != "region" or not self._is_dragging:
            return
        
        # Update rectangle
        if self._rect_id:
            # Convert to canvas coords
            start_canvas_x = self._start_x - self._overlay.winfo_rootx()
            start_canvas_y = self._start_y - self._overlay.winfo_rooty()
            
            self._canvas.coords(
                self._rect_id,
                start_canvas_x, start_canvas_y,
                event.x, event.y
            )
            
            # Update size text
            width = abs(event.x_root - self._start_x)
            height = abs(event.y_root - self._start_y)
            
            self._canvas.itemconfig(
                self._size_text_id,
                text=f"{width} x {height}"
            )
            self._canvas.coords(
                self._size_text_id,
                min(start_canvas_x, event.x) + 5,
                min(start_canvas_y, event.y) - 20
            )
    
    def _on_release(self, event):
        """Handle mouse release (for region selection)"""
        if self._mode != "region" or not self._is_dragging:
            return
        
        self._is_dragging = False
        self._finish_region_capture(
            self._start_x, self._start_y,
            event.x_root, event.y_root
        )
    
    def _on_cancel(self, event):
        """Handle ESC key - cancel capture"""
        self._close_overlay()
        self._root.deiconify()
        
        if self._callback:
            self._callback(CaptureResult(success=False))
    
    def _finish_capture(self, screen_x: int, screen_y: int):
        """Finish single point capture"""
        self._close_overlay()
        self._root.deiconify()
        
        # Convert to client coords if target window is set
        client_x, client_y = screen_x, screen_y
        is_client = False
        
        if self._target_hwnd:
            pt = wintypes.POINT(screen_x, screen_y)
            user32.ScreenToClient(self._target_hwnd, ctypes.byref(pt))
            client_x, client_y = pt.x, pt.y
            is_client = True
        
        result = CaptureResult(
            success=True,
            x=client_x,
            y=client_y,
            hwnd=self._target_hwnd or 0,
            client_coords=is_client
        )
        
        log(f"[CAPTURE] XY captured: ({client_x}, {client_y}) {'client' if is_client else 'screen'}")
        
        if self._callback:
            self._callback(result)
    
    def _finish_region_capture(self, x1: int, y1: int, x2: int, y2: int):
        """Finish region capture"""
        self._close_overlay()
        self._root.deiconify()
        
        # Normalize coordinates (ensure x1,y1 is top-left)
        left = min(x1, x2)
        top = min(y1, y2)
        right = max(x1, x2)
        bottom = max(y1, y2)
        
        # Convert to client coords if target window is set
        is_client = False
        if self._target_hwnd:
            pt1 = wintypes.POINT(left, top)
            pt2 = wintypes.POINT(right, bottom)
            user32.ScreenToClient(self._target_hwnd, ctypes.byref(pt1))
            user32.ScreenToClient(self._target_hwnd, ctypes.byref(pt2))
            left, top = pt1.x, pt1.y
            right, bottom = pt2.x, pt2.y
            is_client = True
        
        result = CaptureResult(
            success=True,
            x=left,
            y=top,
            x2=right,
            y2=bottom,
            hwnd=self._target_hwnd or 0,
            client_coords=is_client
        )
        
        log(f"[CAPTURE] Region captured: ({left}, {top}) - ({right}, {bottom}) {'client' if is_client else 'screen'}")
        
        if self._callback:
            self._callback(result)
    
    def _close_overlay(self):
        """Close overlay window"""
        if self._overlay:
            self._overlay.destroy()
            self._overlay = None
            self._canvas = None


class QuickCapture:
    """
    Quick capture utilities for use in UI
    Provides simple methods to capture XY or Region
    """
    
    def __init__(self, root: tk.Tk):
        self._root = root
        self._target_hwnd: Optional[int] = None
        self._pending_result: Optional[CaptureResult] = None
        self._event = threading.Event()
    
    def set_target_window(self, hwnd: int):
        """Set target window for client coord conversion"""
        self._target_hwnd = hwnd
    
    def capture_xy_async(self, 
                         x_var: tk.IntVar, 
                         y_var: tk.IntVar,
                         on_complete: Optional[Callable[[], None]] = None):
        """
        Capture XY position and set to IntVars
        Non-blocking: updates variables when capture completes
        
        Args:
            x_var: Tkinter variable for X coordinate
            y_var: Tkinter variable for Y coordinate
            on_complete: Optional callback when done
        """
        def callback(result: CaptureResult):
            if result.success:
                x_var.set(result.x)
                y_var.set(result.y)
            if on_complete:
                on_complete()
        
        overlay = CaptureOverlay(self._root, self._target_hwnd)
        overlay.capture_xy(callback)
    
    def capture_region_async(self,
                             x1_var: tk.IntVar,
                             y1_var: tk.IntVar,
                             x2_var: tk.IntVar,
                             y2_var: tk.IntVar,
                             on_complete: Optional[Callable[[], None]] = None):
        """
        Capture region and set to IntVars
        Non-blocking: updates variables when capture completes
        
        Args:
            x1_var, y1_var: Top-left coordinates
            x2_var, y2_var: Bottom-right coordinates
            on_complete: Optional callback when done
        """
        def callback(result: CaptureResult):
            if result.success:
                x1_var.set(result.x)
                y1_var.set(result.y)
                x2_var.set(result.x2)
                y2_var.set(result.y2)
            if on_complete:
                on_complete()
        
        overlay = CaptureOverlay(self._root, self._target_hwnd)
        overlay.capture_region(callback)
    
    def capture_xy_blocking(self) -> Optional[Tuple[int, int]]:
        """
        Capture XY position (blocking)
        
        Returns:
            (x, y) tuple or None if cancelled
        """
        self._event.clear()
        self._pending_result = None
        
        def callback(result: CaptureResult):
            self._pending_result = result
            self._event.set()
        
        # Must run in main thread
        overlay = CaptureOverlay(self._root, self._target_hwnd)
        overlay.capture_xy(callback)
        
        # Wait for result (with timeout)
        self._event.wait(timeout=60)
        
        if self._pending_result and self._pending_result.success:
            return (self._pending_result.x, self._pending_result.y)
        return None


def get_cursor_position() -> Tuple[int, int]:
    """Get current cursor position (screen coords)"""
    pt = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    return (pt.x, pt.y)


def get_pixel_color(x: int, y: int) -> Tuple[int, int, int]:
    """Get pixel color at position (screen coords)"""
    hdc = user32.GetDC(0)
    pixel = ctypes.windll.gdi32.GetPixel(hdc, x, y)
    user32.ReleaseDC(0, hdc)
    
    r = pixel & 0xFF
    g = (pixel >> 8) & 0xFF
    b = (pixel >> 16) & 0xFF
    
    return (r, g, b)
