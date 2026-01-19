# =============================================================================
# DPI AWARENESS - CRITICAL for Windows High DPI displays
# Must be called BEFORE any tkinter imports
# =============================================================================
import ctypes
import sys
import os

def set_dpi_awareness():
    """
    Set DPI awareness for Windows to prevent UI scaling issues.
    This must be called BEFORE creating any windows/UI.
    
    Without this, exe builds will have blurry/resized UI on high DPI screens.
    """
    if sys.platform == 'win32':
        try:
            # Windows 10 1607+ (Anniversary Update)
            # PROCESS_PER_MONITOR_DPI_AWARE_V2 = 2
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except AttributeError:
            try:
                # Windows 8.1+
                # PROCESS_PER_MONITOR_DPI_AWARE = 2
                ctypes.windll.shcore.SetProcessDpiAwareness(1)
            except AttributeError:
                try:
                    # Windows Vista+
                    ctypes.windll.user32.SetProcessDPIAware()
                except:
                    pass
        except Exception as e:
            # Already set or not supported
            pass

def set_app_user_model_id():
    """
    Set Windows App User Model ID for proper taskbar grouping and icon display.
    This ensures the app icon shows correctly in taskbar instead of Python icon.
    """
    if sys.platform == 'win32':
        try:
            app_id = 'Szuyu.MacroAuto.1.0.0'
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
        except Exception:
            pass

# MUST call before any UI imports
set_dpi_awareness()
set_app_user_model_id()

# =============================================================================
# MAIN APPLICATION
# =============================================================================
from ui.main_ui import MainUI

def get_icon_path():
    """Get icon path, handling both development and frozen (exe) modes."""
    if getattr(sys, 'frozen', False):
        # Running as exe - icon might be in temp dir or alongside exe
        base_path = os.path.dirname(sys.executable)
    else:
        # Running as script
        base_path = os.path.dirname(os.path.abspath(__file__))
    
    icon_path = os.path.join(base_path, 'icon.ico')
    if os.path.exists(icon_path):
        return icon_path
    return None

def initialize_workers_fast():
    """No auto-scan - return empty list. User must use Set Worker dialog."""
    print("[APP] Starting in standalone mode")
    print("[APP] Use 'Set Worker' button to assign LDPlayer instances")
    return []

# No auto-scan - workers start empty
workers = initialize_workers_fast()

ui = MainUI(workers)

# Set window icon for both window title bar and taskbar
icon_path = get_icon_path()
if icon_path:
    try:
        ui.root.iconbitmap(icon_path)
    except Exception as e:
        print(f"[APP] Could not set icon: {e}")

ui.root.mainloop()
