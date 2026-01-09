# core/state_machine.py

from enum import Enum
from core.tech import time
from utils.logger import log


class ActionResult(Enum):
    SUCCESS = "SUCCESS"
    FAIL = "FAIL"
    RETRY = "RETRY"
    END = "END"


class StateMachine:
    def __init__(self, worker, actions: list, command_name: str):
        self.worker = worker
        self.actions = actions
        self.command_name = command_name
        self.index = 0
        self.start_time = time.time()
        self.active = True

        log(f"[STATE] Khởi động command: {command_name}")

    def step(self):
        if not self.active:
            return

        if self.index >= len(self.actions):
            log("[STATE] Hết action → kết thúc command")
            self.active = False
            return

        action = self.actions[self.index]
        action_type = action.get("type")

        log(f"[STATE] Thực thi action {self.index}: {action_type}")

        result = self.execute_action(action)

        self.handle_result(result, action)

    def execute_action(self, action: dict) -> dict:
        try:
            handler = action["handler"]
            return handler(self.worker, action)
        except Exception as e:
            log(f"[ERROR] Action exception: {e}")
            return {
                "result": ActionResult.FAIL,
                "message": str(e)
            }

    def handle_result(self, result: dict, action: dict):
        status = result.get("result")

        if status == ActionResult.SUCCESS:
            log("[STATE] SUCCESS → next")
            self.index += 1

        elif status == ActionResult.RETRY:
            log("[STATE] RETRY → giữ action hiện tại")

        elif status == ActionResult.FAIL:
            log("[STATE] FAIL → kết thúc command")
            self.active = False

        elif status == ActionResult.END:
            log("[STATE] END → kết thúc command")
            self.active = False

        else:
            log("[STATE] RESULT không hợp lệ → FAIL")
            self.active = False
