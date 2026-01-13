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
    
    # Class-level flag to prevent concurrent captures
    _is_active = False
    
    @classmethod
    def force_reset(cls):
        """Force reset the active flag - use if capture gets stuck"""
        cls._is_active = False
        log("[CAPTURE] Force reset active flag")
    
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
        self._initialized = False  # Track if init completed
        
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
        # Prevent concurrent captures
        if CaptureOverlay._is_active:
            log("[CAPTURE] Another capture is active, please wait...")
            if callback:
                callback(CaptureResult(success=False))
            return
        
        CaptureOverlay._is_active = True
        self._mode = "xy"
        self._callback = callback
        try:
            self._show_overlay()
        except Exception as e:
            log(f"[CAPTURE] Failed to show overlay: {e}")
            CaptureOverlay._is_active = False  # Reset on failure
            try:
                self._root.deiconify()  # Restore GUI
            except:
                pass
            if callback:
                callback(CaptureResult(success=False))
    
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
        # Prevent concurrent captures
        if CaptureOverlay._is_active:
            log("[CAPTURE] Another capture is active, please wait...")
            if callback:
                callback(CaptureResult(success=False))
            return
        
        CaptureOverlay._is_active = True
        self._mode = "region"
        self._callback = callback
        try:
            self._show_overlay()
        except Exception as e:
            log(f"[CAPTURE] Failed to show overlay: {e}")
            CaptureOverlay._is_active = False  # Reset on failure
            try:
                self._root.deiconify()  # Restore GUI
            except:
                pass
            if callback:
                callback(CaptureResult(success=False))
    
    def _show_overlay(self):
        """Show fullscreen capture overlay - simplified version"""
        # Hide main window
        self._root.withdraw()
        self._root.update_idletasks()
        
        # Get screen dimensions BEFORE creating overlay
        screen_w = self._root.winfo_screenwidth()
        screen_h = self._root.winfo_screenheight()
        
        # Create overlay window
        self._overlay = tk.Toplevel(self._root)
        self._overlay.title("Capture")
        
        # Set geometry to cover full screen at position 0,0
        self._overlay.geometry(f"{screen_w}x{screen_h}+0+0")
        
        # Configure window
        self._overlay.configure(bg='gray20')
        self._overlay.attributes('-topmost', True)
        self._overlay.attributes('-alpha', 0.4)
        
        # Remove title bar AFTER setting geometry
        self._overlay.overrideredirect(True)
        
        # Create canvas
        self._canvas = tk.Canvas(
            self._overlay, 
            width=screen_w, 
            height=screen_h,
            bg='gray20',
            highlightthickness=0,
            cursor="cross"
        )
        self._canvas.pack(fill="both", expand=True)
        
        # Instructions text
        if self._constrain_bounds:
            self._canvas.create_text(
                screen_w // 2, 30,
                text="🎯 Click and DRAG to select region (ESC to cancel)",
                fill="yellow", font=("Arial", 14, "bold")
            )
            # Draw emulator bounds
            bx1, by1, bx2, by2 = self._constrain_bounds
            self._bounds_rect_id = self._canvas.create_rectangle(
                bx1, by1, bx2, by2,
                outline="#00FF00", width=3, dash=(8, 4)
            )
            self._canvas.create_text(
                (bx1 + bx2) // 2, by1 - 15,
                text="📱 Emulator",
                fill="#00FF00", font=("Arial", 11, "bold")
            )
        else:
            self._canvas.create_text(
                screen_w // 2, 30,
                text="🎯 Click and DRAG to select region (ESC to cancel)",
                fill="white", font=("Arial", 14, "bold")
            )
        
        # Bind mouse events to CANVAS
        self._canvas.bind("<ButtonPress-1>", self._on_click)
        self._canvas.bind("<B1-Motion>", self._on_drag)
        self._canvas.bind("<ButtonRelease-1>", self._on_release)
        
        # Bind keyboard to OVERLAY
        self._overlay.bind("<Escape>", self._on_cancel)
        self._overlay.bind("<Key>", lambda e: self._on_cancel(e) if e.keysym == "Escape" else None)
        
        # CRITICAL: Update window, then grab focus
        self._overlay.update()
        self._overlay.lift()
        self._overlay.focus_force()
        
        # Grab all events (this is key for receiving mouse events)
        try:
            self._overlay.grab_set()
        except:
            pass
    
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
        
        # Validate region has actual size (not just a click)
        width = abs(end_x - self._start_x)
        height = abs(end_y - self._start_y)
        if width < 5 or height < 5:
            log(f"[CAPTURE] Region too small ({width}x{height}), need at least 5x5 pixels")
            # Flash warning and let user try again
            if self._rect_id:
                self._canvas.itemconfig(self._rect_id, outline="#FF0000", width=4)
                self._overlay.after(300, lambda: self._canvas.itemconfig(
                    self._rect_id, outline="red", width=2) if self._rect_id else None)
            self._is_dragging = False  # Reset to allow retry
            return
        
        self._finish_region_capture(
            self._start_x, self._start_y,
            end_x, end_y
        )
    
    def _on_cancel(self, event):
        """Handle ESC key - cancel capture"""
        # Close overlay FIRST (this resets _is_active flag)
        self._close_overlay()
        
        # Restore GUI
        try:
            self._root.deiconify()
            self._root.lift()
            self._root.focus_force()
        except Exception as e:
            log(f"[CAPTURE] Restore warning: {e}")
        
        # Callback with failure
        if self._callback:
            callback = self._callback
            self._callback = None  # Prevent double callback
            callback(CaptureResult(success=False))
    
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
        
        # Callback with result (prevent double callback)
        if self._callback:
            callback = self._callback
            self._callback = None
            callback(result)

    def _restore_gui(self):
        """Restore the main GUI window."""
        self._root.deiconify()
        try:
            self._root.overrideredirect(False)
        except Exception as e:
            log(f"[CAPTURE] Failed to restore GUI: {e}")

    def _finish_region_capture(self, x1: int, y1: int, x2: int, y2: int):
        """Finish region capture - capture from target window directly"""
        import os
        import cv2
        import numpy as np
        try:
            from PIL import Image
        except ImportError:
            Image = None

        # Store screen coords before closing overlay
        screen_x1, screen_y1 = min(x1, x2), min(y1, y2)
        screen_x2, screen_y2 = max(x1, x2), max(y1, y2)
        
        # Close overlay FIRST
        try:
            self._close_overlay()
        except Exception as e:
            log(f"[CAPTURE] Close overlay error: {e}")
            CaptureOverlay._is_active = False

        # Convert to client coords for result
        left, top, right, bottom = screen_x1, screen_y1, screen_x2, screen_y2
        is_client = False
        
        if self._target_hwnd:
            pt1 = wintypes.POINT(screen_x1, screen_y1)
            pt2 = wintypes.POINT(screen_x2, screen_y2)
            user32.ScreenToClient(self._target_hwnd, ctypes.byref(pt1))
            user32.ScreenToClient(self._target_hwnd, ctypes.byref(pt2))
            left, top = pt1.x, pt1.y
            right, bottom = pt2.x, pt2.y
            is_client = True

        img_path = None
        clipboard_ok = False
        pil_img = None

        # Capture directly from target window using Win32 API
        if self._target_hwnd and Image is not None:
            try:
                pil_img = self._capture_window_region(
                    self._target_hwnd, 
                    left, top, right, bottom
                )
                if pil_img:
                    # Save to files/
                    os.makedirs('files', exist_ok=True)
                    import datetime
                    ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
                    img_path = os.path.join('files', f'crop_{ts}.png')
                    pil_img.save(img_path)
                    
                    # Copy to clipboard
                    try:
                        import io
                        import win32clipboard
                        output = io.BytesIO()
                        pil_img.convert("RGB").save(output, "BMP")
                        data = output.getvalue()[14:]
                        output.close()
                        win32clipboard.OpenClipboard()
                        win32clipboard.EmptyClipboard()
                        win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
                        win32clipboard.CloseClipboard()
                        clipboard_ok = True
                    except Exception as e:
                        log(f"[CAPTURE] Clipboard error: {e}")
            except Exception as e:
                log(f"[CAPTURE] Window capture error: {e}")
        
        # Fallback: try screen grab if window capture failed
        if pil_img is None:
            try:
                from PIL import ImageGrab
                # Need to wait for overlay to fully close
                self._root.update_idletasks()
                self._root.after(100)  # Small delay
                self._root.update()
                
                bbox = (screen_x1, screen_y1, screen_x2, screen_y2)
                pil_img = ImageGrab.grab(bbox)
                if pil_img:
                    os.makedirs('files', exist_ok=True)
                    import datetime
                    ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
                    img_path = os.path.join('files', f'crop_{ts}.png')
                    pil_img.save(img_path)
            except Exception as e:
                log(f"[CAPTURE] Screen grab fallback error: {e}")

        result = CaptureResult(
            success=True,
            x=left,
            y=top,
            x2=right,
            y2=bottom,
            hwnd=self._target_hwnd or 0,
            client_coords=is_client
        )
        result.img_path = img_path
        result.clipboard_ok = clipboard_ok
        result.pil_image = pil_img

        log(f"[CAPTURE] Region captured: ({left}, {top}) - ({right}, {bottom}) {'client' if is_client else 'screen'}; img_path={img_path}")

        # Restore GUI
        try:
            self._root.deiconify()
            self._root.lift()
        except Exception as e:
            log(f"[CAPTURE] Restore error: {e}")

        # Callback
        if self._callback:
            callback = self._callback
            self._callback = None
            try:
                callback(result)
            except Exception as e:
                log(f"[CAPTURE] Callback error: {e}")
    
    def _capture_window_region(self, hwnd: int, x1: int, y1: int, x2: int, y2: int):
        """Capture a region from a window using Win32 API (doesn't require window to be visible)"""
        try:
            from PIL import Image
            import win32gui
            import win32ui
            import win32con
            
            # Get window dimensions
            left, top, wnd_right, wnd_bottom = win32gui.GetClientRect(hwnd)
            width = wnd_right - left
            height = wnd_bottom - top
            
            # Clamp region to window bounds
            x1 = max(0, min(width, x1))
            y1 = max(0, min(height, y1))
            x2 = max(0, min(width, x2))
            y2 = max(0, min(height, y2))
            
            if x2 <= x1 or y2 <= y1:
                log(f"[CAPTURE] Invalid region: ({x1},{y1})-({x2},{y2})")
                return None
            
            # Create device contexts
            hwnd_dc = win32gui.GetWindowDC(hwnd)
            mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
            save_dc = mfc_dc.CreateCompatibleDC()
            
            # Create bitmap
            bitmap = win32ui.CreateBitmap()
            bitmap.CreateCompatibleBitmap(mfc_dc, width, height)
            save_dc.SelectObject(bitmap)
            
            # Copy window content to bitmap
            # Use PrintWindow for better compatibility
            result = ctypes.windll.user32.PrintWindow(hwnd, save_dc.GetSafeHdc(), 3)  # PW_RENDERFULLCONTENT=2, PW_CLIENTONLY=1, combined=3
            
            if result == 0:
                # Fallback to BitBlt
                save_dc.BitBlt((0, 0), (width, height), mfc_dc, (0, 0), win32con.SRCCOPY)
            
            # Get bitmap info
            bmp_info = bitmap.GetInfo()
            bmp_str = bitmap.GetBitmapBits(True)
            
            # Create PIL image
            img = Image.frombuffer(
                'RGB',
                (bmp_info['bmWidth'], bmp_info['bmHeight']),
                bmp_str, 'raw', 'BGRX', 0, 1
            )
            
            # Cleanup
            win32gui.DeleteObject(bitmap.GetHandle())
            save_dc.DeleteDC()
            mfc_dc.DeleteDC()
            win32gui.ReleaseDC(hwnd, hwnd_dc)
            
            # Crop to region
            cropped = img.crop((x1, y1, x2, y2))
            return cropped
            
        except Exception as e:
            log(f"[CAPTURE] Win32 capture error: {e}")
            return None
    
    def _close_overlay(self):
        """Close overlay window - thorough cleanup"""
        # Reset class-level active flag FIRST
        CaptureOverlay._is_active = False
        
        if self._overlay:
            try:
                # Release grab first
                self._overlay.grab_release()
            except:
                pass
            
            try:
                # Unbind all events
                if self._canvas:
                    self._canvas.unbind("<ButtonPress-1>")
                    self._canvas.unbind("<B1-Motion>")
                    self._canvas.unbind("<ButtonRelease-1>")
                self._overlay.unbind("<Escape>")
                self._overlay.unbind("<Key>")
            except Exception as e:
                log(f"[CAPTURE] Unbind warning: {e}")
            
            try:
                self._overlay.destroy()
            except Exception as e:
                log(f"[CAPTURE] Destroy warning: {e}")
            
            self._overlay = None
            self._canvas = None
        
        # Reset all instance state
        self._is_dragging = False
        self._rect_id = None
        self._size_text_id = None
        self._bounds_rect_id = None
        self._start_x = 0
        self._start_y = 0
        
        # Force Tkinter to process pending events
        try:
            self._root.update_idletasks()
        except Exception:
            pass


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
