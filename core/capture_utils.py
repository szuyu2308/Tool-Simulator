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
        
        # Constrain bounds (for emulator capture)
        # Format: (x1, y1, x2, y2) - screen coords
        self._constrain_bounds: Optional[Tuple[int, int, int, int]] = None
        self._bounds_rect_id = None
    
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
            # Show different text if constrained to emulator
            if self._constrain_bounds:
                self._canvas.create_text(
                    screen_w // 2, 50,
                    text="Click and drag within EMULATOR bounds (ESC to cancel)",
                    fill="yellow", font=("Arial", 16, "bold")
                )
            else:
                self._canvas.create_text(
                    screen_w // 2, 50,
                    text="Click and drag to select region (ESC to cancel)",
                    fill="white", font=("Arial", 16, "bold")
                )
        
        # Draw constrain bounds if set (emulator boundary)
        if self._constrain_bounds:
            bx1, by1, bx2, by2 = self._constrain_bounds
            # Draw highlighted rectangle around emulator area
            self._bounds_rect_id = self._canvas.create_rectangle(
                bx1, by1, bx2, by2,
                outline="#00FF00", width=3, dash=(10, 5)
            )
            # Add label
            self._canvas.create_text(
                (bx1 + bx2) // 2, by1 - 20,
                text="📱 Emulator Area",
                fill="#00FF00", font=("Arial", 12, "bold")
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
        # Check if click is within constrain bounds (if set)
        if self._constrain_bounds:
            bx1, by1, bx2, by2 = self._constrain_bounds
            if not (bx1 <= event.x_root <= bx2 and by1 <= event.y_root <= by2):
                # Click outside bounds - show warning flash
                if self._bounds_rect_id:
                    self._canvas.itemconfig(self._bounds_rect_id, outline="#FF0000", width=5)
                    self._overlay.after(200, lambda: self._canvas.itemconfig(
                        self._bounds_rect_id, outline="#00FF00", width=3))
                return
        
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
        
        # Constrain to bounds if set
        drag_x = event.x_root
        drag_y = event.y_root
        if self._constrain_bounds:
            bx1, by1, bx2, by2 = self._constrain_bounds
            drag_x = max(bx1, min(bx2, drag_x))
            drag_y = max(by1, min(by2, drag_y))
        
        # Update rectangle
        if self._rect_id:
            # Convert to canvas coords
            start_canvas_x = self._start_x - self._overlay.winfo_rootx()
            start_canvas_y = self._start_y - self._overlay.winfo_rooty()
            end_canvas_x = drag_x - self._overlay.winfo_rootx()
            end_canvas_y = drag_y - self._overlay.winfo_rooty()
            
            self._canvas.coords(
                self._rect_id,
                start_canvas_x, start_canvas_y,
                end_canvas_x, end_canvas_y
            )
            
            # Update size text
            width = abs(drag_x - self._start_x)
            height = abs(drag_y - self._start_y)
            
            self._canvas.itemconfig(
                self._size_text_id,
                text=f"{width} x {height}"
            )
            self._canvas.coords(
                self._size_text_id,
                min(start_canvas_x, end_canvas_x) + 5,
                min(start_canvas_y, end_canvas_y) - 20
            )
    
    def _on_release(self, event):
        """Handle mouse release (for region selection)"""
        if self._mode != "region" or not self._is_dragging:
            return
        
        self._is_dragging = False
        
        # Constrain end point to bounds if set
        end_x = event.x_root
        end_y = event.y_root
        if self._constrain_bounds:
            bx1, by1, bx2, by2 = self._constrain_bounds
            end_x = max(bx1, min(bx2, end_x))
            end_y = max(by1, min(by2, end_y))
        
        self._finish_region_capture(
            self._start_x, self._start_y,
            end_x, end_y
        )
    
    def _on_cancel(self, event):
        """Handle ESC key - cancel capture"""
        # Ensure main window is fully hidden and not captured
        self._root.withdraw()
        try:
            self._root.overrideredirect(True)
            self._root.lower()
        except Exception:
            pass
        self._close_overlay()
        # Wait a short moment to ensure all windows are hidden
        import time
        time.sleep(0.15)
        self._root.deiconify()
        try:
            self._root.overrideredirect(False)
        except Exception:
            pass
        
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
    
    def _hide_gui(self):
        """Hide the main GUI window completely."""
        self._root.withdraw()
        try:
            self._root.overrideredirect(True)
            self._root.lower()
        except Exception as e:
            log(f"[CAPTURE] Failed to fully hide GUI: {e}")
        time.sleep(0.2)  # Ensure the window is fully hidden

    def _restore_gui(self):
        """Restore the main GUI window."""
        self._root.deiconify()
        try:
            self._root.overrideredirect(False)
        except Exception as e:
            log(f"[CAPTURE] Failed to restore GUI: {e}")

    def _finish_region_capture(self, x1: int, y1: int, x2: int, y2: int):
        """Finish region capture, use OpenCV to crop, save to files/ and clipboard"""
        import os
        import cv2
        import numpy as np
        try:
            from PIL import ImageGrab, Image
        except ImportError:
            ImageGrab = None
            Image = None

        # CRITICAL: Close overlay and hide GUI BEFORE capturing screen
        # Order matters: overlay first, then GUI, then wait for screen to update
        self._close_overlay()
        self._hide_gui()
        
        # Force window manager to process the hide
        self._root.update_idletasks()
        self._root.update()
        
        # Wait for screen to fully update (Windows needs time to redraw)
        time.sleep(0.25)

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

        img_path = None
        clipboard_ok = False
        pil_img = None  # Store PIL image for preview
        
        # Capture the region as an image (screen coordinates) using OpenCV
        if ImageGrab is not None and Image is not None:
            bbox = (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
            try:
                img = ImageGrab.grab(bbox)
                img_np = np.array(img)
                img_cv = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
                
                # Save to files/ with unique name
                os.makedirs('files', exist_ok=True)
                import datetime
                ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
                img_path = os.path.join('files', f'crop_{ts}.png')
                cv2.imwrite(img_path, img_cv)
                
                # Keep PIL image for preview
                pil_img = Image.fromarray(cv2.cvtColor(img_cv, cv2.COLOR_BGR2RGB))
                
                # Copy to clipboard (Windows only)
                try:
                    import io
                    import win32clipboard
                    
                    output = io.BytesIO()
                    pil_img.convert("RGB").save(output, "BMP")
                    data = output.getvalue()[14:]  # Skip BMP header
                    output.close()
                    
                    win32clipboard.OpenClipboard()
                    win32clipboard.EmptyClipboard()
                    win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
                    win32clipboard.CloseClipboard()
                    clipboard_ok = True
                    log(f"[CAPTURE] Image copied to clipboard successfully")
                except Exception as e:
                    log(f"[CAPTURE] Failed to copy image to clipboard: {e}")
            except Exception as e:
                log(f"[CAPTURE] OpenCV crop error: {e}")
        else:
            log("[CAPTURE] PIL.ImageGrab not available, cannot capture region image.")

        result = CaptureResult(
            success=True,
            x=left,
            y=top,
            x2=right,
            y2=bottom,
            hwnd=self._target_hwnd or 0,
            client_coords=is_client
        )
        # Attach image path, clipboard status, and PIL image for preview logic
        result.img_path = img_path
        result.clipboard_ok = clipboard_ok
        result.pil_image = pil_img  # For preview without re-reading from disk

        log(f"[CAPTURE] Region captured: ({left}, {top}) - ({right}, {bottom}) {'client' if is_client else 'screen'}; img_path={img_path}; clipboard={clipboard_ok}")

        self._restore_gui()  # Restore GUI after capture

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
