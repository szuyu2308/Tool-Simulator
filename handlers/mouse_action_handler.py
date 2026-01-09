from core.state_machine import StateResult
from core.action import MouseAction


class MouseActionHandler:
    """
    State type: MOUSE_ACTION

    params:
      - action: str        (left | right | middle | drag | wheel)
      - x: int             (local coord, optional – lấy từ context nếu thiếu)
      - y: int             (local coord, optional – lấy từ context nếu thiếu)
      - x2: int            (drag end x – local coord, chỉ dùng cho drag)
      - y2: int            (drag end y – local coord, chỉ dùng cho drag)
      - wheel_delta: int   (vd: 120 / -120, chỉ dùng cho wheel)
      - delay: float       (click delay, optional)
    """

    def execute(self, worker, state, context):
        params = state.get("params", {})

        action = params.get("action")
        x = params.get("x", context.get("x"))
        y = params.get("y", context.get("y"))

        if action is None:
            return {
                "status": StateResult.FAIL,
                "data": {}
            }

        try:
            if action == "left":
                MouseAction.left_click(worker, x, y, params.get("delay", 0.05))

            elif action == "right":
                MouseAction.right_click(worker, x, y, params.get("delay", 0.05))

            elif action == "middle":
                MouseAction.middle_click(worker, x, y, params.get("delay", 0.05))

            elif action == "drag":
                x2 = params.get("x2")
                y2 = params.get("y2")
                if x2 is None or y2 is None:
                    return {
                        "status": StateResult.FAIL,
                        "data": {}
                    }
                MouseAction.drag(
                    worker,
                    x, y,
                    x2, y2,
                    params.get("hold_delay", 0.1),
                    params.get("move_delay", 0.01)
                )

            elif action == "wheel":
                delta = params.get("wheel_delta")
                if delta is None:
                    return {
                        "status": StateResult.FAIL,
                        "data": {}
                    }
                MouseAction.wheel(worker, x, y, delta)

            else:
                return {
                    "status": StateResult.FAIL,
                    "data": {}
                }

            return {
                "status": StateResult.SUCCESS,
                "data": {}
            }

        except Exception:
            return {
                "status": StateResult.FAIL,
                "data": {}
            }
