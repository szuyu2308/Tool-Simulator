from core.tech import win32api, win32con, time
from core.state_machine import ActionResult
from core.vision import MotionDetector
from core.tech import time
from utils.logger import log

_motion_cache = {}


def wait_motion(worker, action: dict):
    timeout = action.get("timeout", 10)
    key = worker.hwnd

    if key not in _motion_cache:
        _motion_cache[key] = {
            "detector": MotionDetector(),
            "start": time.time()
        }

    data = _motion_cache[key]
    detector = data["detector"]

    frame = worker.capture()

    if detector.update(frame):
        log("[WAIT_MOTION] Màn hình ổn định")
        del _motion_cache[key]
        return {"result": ActionResult.SUCCESS}

    if time.time() - data["start"] > timeout:
        log("[WAIT_MOTION] Timeout")
        del _motion_cache[key]
        return {"result": ActionResult.FAIL}

    return {"result": ActionResult.RETRY}


class MouseAction:
    """
    TẤT CẢ action chuột PHẢI đi qua Worker
    - Nhận local coord (theo res LD)
    - Convert qua worker.local_to_screen()
    - Không cho phép screen coord trực tiếp
    """

    @staticmethod
    def _move_to(worker, x, y):
        screen_x, screen_y = worker.local_to_screen(x, y)
        win32api.SetCursorPos((screen_x, screen_y))

    @staticmethod
    def left_click(worker, x, y, delay=0.05):
        worker.focus()
        MouseAction._move_to(worker, x, y)

        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0)
        time.sleep(delay)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0)

    @staticmethod
    def right_click(worker, x, y, delay=0.05):
        worker.focus()
        MouseAction._move_to(worker, x, y)

        win32api.mouse_event(win32con.MOUSEEVENTF_RIGHTDOWN, 0, 0)
        time.sleep(delay)
        win32api.mouse_event(win32con.MOUSEEVENTF_RIGHTUP, 0, 0)

    @staticmethod
    def middle_click(worker, x, y, delay=0.05):
        worker.focus()
        MouseAction._move_to(worker, x, y)

        win32api.mouse_event(win32con.MOUSEEVENTF_MIDDLEDOWN, 0, 0)
        time.sleep(delay)
        win32api.mouse_event(win32con.MOUSEEVENTF_MIDDLEUP, 0, 0)

    @staticmethod
    def drag(worker, x1, y1, x2, y2, hold_delay=0.1, move_delay=0.01):
        """
        Drag từ (x1,y1) → (x2,y2) theo local coord
        """
        worker.focus()

        sx1, sy1 = worker.local_to_screen(x1, y1)
        sx2, sy2 = worker.local_to_screen(x2, y2)

        win32api.SetCursorPos((sx1, sy1))
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0)

        time.sleep(hold_delay)

        win32api.SetCursorPos((sx2, sy2))
        time.sleep(move_delay)

        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0)

    @staticmethod
    def wheel(worker, x, y, delta):
        """
        delta > 0 : wheel up
        delta < 0 : wheel down
        """
        worker.focus()
        MouseAction._move_to(worker, x, y)

        win32api.mouse_event(
            win32con.MOUSEEVENTF_WHEEL,
            0,
            0,
            delta,
            0
        )
