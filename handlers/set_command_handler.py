from core.state_machine import StateResult


class SetCommandHandler:
    """
    State type: SET_COMMAND

    params:
      - command_name: str            (tên command cần phát)
      - command_config: dict | None  (config cho command mới, optional)
      - target_worker: str | None    (id worker khác, optional – để sau)
    """

    def execute(self, worker, state, context):
        params = state.get("params", {})

        command_name = params.get("command_name")
        command_config = params.get("command_config")

        if not command_name:
            return {
                "status": StateResult.FAIL,
                "data": {}
            }

        # Phát command cho chính worker hiện tại
        ok = worker.set_command(command_name, command_config)

        if not ok:
            return {
                "status": StateResult.FAIL,
                "data": {}
            }

        return {
            "status": StateResult.SUCCESS,
            "data": {}
        }
