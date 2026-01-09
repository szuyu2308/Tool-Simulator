from core.tech import cv2, np, time
from core.state_machine import StateResult


class ImageScanHandler:
    """
    State type: IMAGE_SCAN

    params:
      - image_path: str          (đường dẫn template)
      - threshold: float         (mặc định 0.85)
      - timeout: float           (giây, mặc định 3.0)
      - retry_interval: float    (giây giữa các lần scan, mặc định 0.1)
      - return_center: bool      (trả tâm ảnh, mặc định True)
    """

    def execute(self, worker, state, context):
        params = state.get("params", {})
        image_path = params.get("image_path")
        threshold = params.get("threshold", 0.85)
        timeout = params.get("timeout", 3.0)
        retry_interval = params.get("retry_interval", 0.1)
        return_center = params.get("return_center", True)

        if not image_path:
            return {
                "status": StateResult.FAIL,
                "data": {}
            }

        template = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        if template is None:
            return {
                "status": StateResult.FAIL,
                "data": {}
            }

        th, tw = template.shape[:2]

        start_time = time.time()

        while True:
            if time.time() - start_time >= timeout:
                return {
                    "status": StateResult.FAIL,
                    "data": {}
                }

            frame = worker.capture()
            if frame is None:
                time.sleep(retry_interval)
                continue

            img = np.array(frame)
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

            result = cv2.matchTemplate(gray, template, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

            if max_val >= threshold:
                x, y = max_loc

                if return_center:
                    x += tw // 2
                    y += th // 2

                # Convert screen coord → local coord
                local_x = int(x / worker.scale_x)
                local_y = int(y / worker.scale_y)

                return {
                    "status": StateResult.SUCCESS,
                    "data": {
                        "x": local_x,
                        "y": local_y
                    }
                }

            time.sleep(retry_interval)
