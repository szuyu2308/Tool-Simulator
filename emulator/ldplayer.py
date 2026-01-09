import win32gui

def is_ldplayer_window(hwnd):
    title = win32gui.GetWindowText(hwnd)
    return "LDPlayer" in title or title.startswith("LD")

def get_window_rect(hwnd):
    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    return left, top, right - left, bottom - top

def list_ldplayer_windows():
    windows = []

    def enum_handler(hwnd, _):
        if win32gui.IsWindowVisible(hwnd) and is_ldplayer_window(hwnd):
            title = win32gui.GetWindowText(hwnd)
            rect = get_window_rect(hwnd)
            windows.append((hwnd, title, rect))

    win32gui.EnumWindows(enum_handler, None)
    return windows
