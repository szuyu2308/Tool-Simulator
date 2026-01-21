# utils/console_manager.py
"""
Console Manager - Ẩn/hiện console window trong windowed mode
Hữu ích cho debugging khi cần
"""

import sys

if sys.platform == 'win32':
    import ctypes
    from ctypes import wintypes
    
    # Windows API constants
    SW_HIDE = 0
    SW_SHOW = 5
    
    # Get console window handle
    kernel32 = ctypes.windll.kernel32
    user32 = ctypes.windll.user32
    
    GetConsoleWindow = kernel32.GetConsoleWindow
    GetConsoleWindow.restype = wintypes.HWND
    
    ShowWindow = user32.ShowWindow
    ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    ShowWindow.restype = wintypes.BOOL
    
    class ConsoleManager:
        """Quản lý console window"""
        
        def __init__(self):
            self.console_hwnd = GetConsoleWindow()
            self.visible = True  # Mặc định hiện
        
        def hide(self):
            """Ẩn console window"""
            if self.console_hwnd:
                ShowWindow(self.console_hwnd, SW_HIDE)
                self.visible = False
        
        def show(self):
            """Hiện console window"""
            if self.console_hwnd:
                ShowWindow(self.console_hwnd, SW_SHOW)
                self.visible = True
        
        def toggle(self):
            """Toggle console visibility"""
            if self.visible:
                self.hide()
            else:
                self.show()
        
        def is_visible(self):
            """Check if console is visible"""
            return self.visible
    
else:
    # Non-Windows fallback
    class ConsoleManager:
        def __init__(self):
            pass
        
        def hide(self):
            pass
        
        def show(self):
            pass
        
        def toggle(self):
            pass
        
        def is_visible(self):
            return False


# Singleton instance
_console_manager = None

def get_console_manager():
    """Get global console manager instance"""
    global _console_manager
    if _console_manager is None:
        _console_manager = ConsoleManager()
    return _console_manager
