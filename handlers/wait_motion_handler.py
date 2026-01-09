from core.tech import time, cv2, np
from core.state_machine import StateResult


class WaitMotionHandler:
    """
    State type: WAIT_MOTION

    params:
      - motion_threshold: float  (mức thay đổi pixel, ví dụ 0.02)
      - stable_time: float       (giây màn hình phải ổn định, ví dụ 0.8)
      - timeout: float           (giây tối đa chờ, ví dụ 6.0)
      - sample_interval: float   (giây giữa các frame, mặc định 0.05)
    """

    def execute(self, worker, state, context):
        params = state.get("params", {})
        motion_threshold = params.get("motion_threshold", 0.02)
        stable_time = params.get("stable_time", 0.8)
        timeout = params.get("timeout", 6.0)
        sample_interval = params.get("sample_interval", 0.05)

        start_time = time.time()
        stable_start = None
        prev_gray = None

        while True:
            now = time.time()

            if now - start_time >= timeout:
                return {
                    "status": StateResult.FAIL,
                    "data": {}
                }

            frame = worker.capture()
            if frame is None:
                time.sleep(sample_interval)
                continue

            img = np.array(frame)
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

            if prev_gray is None:
                prev_gray = gray
                time.sleep(sample_interval)
                continue

            diff = cv2.absdiff(prev_gray, gray)
            motion_ratio = np.mean(diff) / 255.0
            prev_gray = gray

            # Có chuyển động
            if motion_ratio >= motion_threshold:
                stable_start = None
                time.sleep(sample_interval)
                continue

            # Ít chuyển động → bắt đầu tính ổn định
            if stable_start is None:
                stable_start = now

            if now - stable_start >= stable_time:
                return {
                    "status": StateResult.SUCCESS,
                    "data": {}
                }

            time.sleep(sample_interval)
