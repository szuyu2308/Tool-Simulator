from core.tech import time
from core.state_machine import StateResult


class VerifyHandler:
    """
    State type: VERIFY

    params:
      - check_key: str        (key trong context cần kiểm tra)
      - expected: any         (giá trị mong đợi)
      - timeout: float        (giây, mặc định 2.0)
      - retry_interval: float (giây, mặc định 0.1)

    Ý nghĩa:
      - Dùng để xác nhận hậu kiểm sau action
      - Không click
      - Không scan ảnh
      - Chỉ kiểm tra context / trạng thái logic
    """

    def execute(self, worker, state, context):
        params = state.get("params", {})
        check_key = params.get("check_key")
        expected = params.get("expected")
        timeout = params.get("timeout", 2.0)
        retry_interval = params.get("retry_interval", 0.1)

        if not check_key:
            return {
                "status": StateResult.FAIL,
                "data": {}
            }

        start_time = time.time()

        while True:
            value = context.get(check_key)

            if value == expected:
                return {
                    "status": StateResult.SUCCESS,
                    "data": {}
                }

            if time.time() - start_time >= timeout:
                return {
                    "status": StateResult.FAIL,
                    "data": {}
                }

            time.sleep(retry_interval)
