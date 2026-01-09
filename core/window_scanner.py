from core.tech import win32gui, win32con

def get_client_rect(hwnd):
        left, top, right, bottom = win32gui.GetClientRect(hwnd)
        # Convert client (0,0) → screen
        screen_left_top = win32gui.ClientToScreen(hwnd, (0, 0))
        width = right - left
        height = bottom - top
        return (
            screen_left_top[0],
            screen_left_top[1],
            width,
            height
        )

class WindowScanner:
    def __init__(self, logger):
        self.logger = logger

    def scan(self):
        self.logger.info("Starting LDPlayer window discovery")

        window_infos = []
        windows = list_ldplayer_windows()
        self.logger.info(f"Found {len(windows)} LDPlayer windows")

        for hwnd, title, _ in windows:
            try:
                client_rect = get_client_rect(hwnd)

                wi = WindowInfo(hwnd, title, client_rect)
                wi.preview = capture_region(client_rect)
                if wi.preview is None:
                    wi.status = "FAIL"
                    self.logger.warning(f"Preview empty: {title}")
                else:
                    wi.status = "WAIT"

                window_infos.append(wi)
                self.logger.info(f"Detected window: {title} | {wi.status}")
            except Exception as e:
                self.logger.error(f"Error scanning window {title}: {e}")

