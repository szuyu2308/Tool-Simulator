from enum import Enum
from typing import List, Optional, Dict, Any
import uuid

# ==================== ENUMS ====================
class CommandType(Enum):
    CLICK = "Click"
    CROP_IMAGE = "CropImage"
    KEY_PRESS = "KeyPress"
    HOT_KEY = "HotKey"
    TEXT = "Text"
    WAIT = "Wait"
    REPEAT = "Repeat"
    GOTO = "Goto"
    CONDITION = "Condition"

class ButtonType(Enum):
    LEFT = "Left"
    RIGHT = "Right"
    DOUBLE = "Double"
    WHEEL_UP = "WheelUp"
    WHEEL_DOWN = "WheelDown"

class OnFailAction(Enum):
    SKIP = "Skip"
    STOP = "Stop"
    GOTO_LABEL = "GotoLabel"

class ScanMode(Enum):
    EXACT = "Exact"
    MAX_MATCH = "MaxMatch"
    GRID = "Grid"

class TextMode(Enum):
    PASTE = "Paste"
    HUMANIZE = "Humanize"

class WaitType(Enum):
    TIMEOUT = "Timeout"
    PIXEL_COLOR = "PixelColor"
    SCREEN_CHANGE = "ScreenChange"

class HotKeyOrder(Enum):
    SIMULTANEOUS = "Simultaneous"
    SEQUENCE = "Sequence"

# ==================== BASE COMMAND ====================
class Command:
    """Base command class with common properties"""
    def __init__(
        self,
        name: str,
        command_type: CommandType,
        enabled: bool = True,
        parent_id: Optional[str] = None,
        on_fail: OnFailAction = OnFailAction.SKIP,
        on_fail_label: Optional[str] = None,
        variables_out: Optional[List[str]] = None
    ):
        self.id: str = str(uuid.uuid4())
        self.parent_id: Optional[str] = parent_id
        self.name: str = name
        self.type: CommandType = command_type
        self.enabled: bool = enabled
        self.on_fail: OnFailAction = on_fail
        self.on_fail_label: Optional[str] = on_fail_label
        self.variables_out: List[str] = variables_out or []

    def to_dict(self) -> dict:
        """Serialize to dictionary"""
        return {
            "id": self.id,
            "parent_id": self.parent_id,
            "name": self.name,
            "type": self.type.value,
            "enabled": self.enabled,
            "on_fail": self.on_fail.value,
            "on_fail_label": self.on_fail_label,
            "variables_out": self.variables_out
        }

    @staticmethod
    def from_dict(data: dict) -> 'Command':
        """Deserialize from dictionary - to be overridden by subclasses"""
        raise NotImplementedError("Subclasses must implement from_dict")

# ==================== COMMAND SUBCLASSES ====================
class ClickCommand(Command):
    """Click command with position and button type"""
    def __init__(
        self,
        name: str,
        button_type: ButtonType = ButtonType.LEFT,
        x: int = 0,
        y: int = 0,
        humanize_delay_min_ms: int = 50,
        humanize_delay_max_ms: int = 200,
        wheel_delta: Optional[int] = None,
        **kwargs
    ):
        super().__init__(name, CommandType.CLICK, **kwargs)
        self.button_type = button_type
        self.x = x
        self.y = y
        self.humanize_delay_min_ms = humanize_delay_min_ms
        self.humanize_delay_max_ms = humanize_delay_max_ms
        self.wheel_delta = wheel_delta

    def to_dict(self) -> dict:
        data = super().to_dict()
        data.update({
            "button_type": self.button_type.value,
            "x": self.x,
            "y": self.y,
            "humanize_delay_min_ms": self.humanize_delay_min_ms,
            "humanize_delay_max_ms": self.humanize_delay_max_ms,
            "wheel_delta": self.wheel_delta
        })
        return data

    @staticmethod
    def from_dict(data: dict) -> 'ClickCommand':
        return ClickCommand(
            name=data["name"],
            button_type=ButtonType(data.get("button_type", "Left")),
            x=data.get("x", 0),
            y=data.get("y", 0),
            humanize_delay_min_ms=data.get("humanize_delay_min_ms", 50),
            humanize_delay_max_ms=data.get("humanize_delay_max_ms", 200),
            wheel_delta=data.get("wheel_delta"),
            enabled=data.get("enabled", True),
            parent_id=data.get("parent_id"),
            on_fail=OnFailAction(data.get("on_fail", "Skip")),
            on_fail_label=data.get("on_fail_label"),
            variables_out=data.get("variables_out", [])
        )

class CropImageCommand(Command):
    """Image detection command with region and color matching"""
    def __init__(
        self,
        name: str,
        x1: int = 0,
        y1: int = 0,
        x2: int = 0,
        y2: int = 0,
        target_color: tuple = (0, 0, 0),  # RGB tuple
        tolerance: int = 10,
        scan_mode: ScanMode = ScanMode.EXACT,
        output_var: str = "crop_result",
        **kwargs
    ):
        super().__init__(name, CommandType.CROP_IMAGE, **kwargs)
        self.x1 = x1
        self.y1 = y1
        self.x2 = x2
        self.y2 = y2
        self.target_color = target_color
        self.tolerance = tolerance
        self.scan_mode = scan_mode
        self.output_var = output_var

    def to_dict(self) -> dict:
        data = super().to_dict()
        data.update({
            "x1": self.x1,
            "y1": self.y1,
            "x2": self.x2,
            "y2": self.y2,
            "target_color": self.target_color,
            "tolerance": self.tolerance,
            "scan_mode": self.scan_mode.value,
            "output_var": self.output_var
        })
        return data

    @staticmethod
    def from_dict(data: dict) -> 'CropImageCommand':
        return CropImageCommand(
            name=data["name"],
            x1=data.get("x1", 0),
            y1=data.get("y1", 0),
            x2=data.get("x2", 0),
            y2=data.get("y2", 0),
            target_color=tuple(data.get("target_color", [0, 0, 0])),
            tolerance=data.get("tolerance", 10),
            scan_mode=ScanMode(data.get("scan_mode", "Exact")),
            output_var=data.get("output_var", "crop_result"),
            enabled=data.get("enabled", True),
            parent_id=data.get("parent_id"),
            on_fail=OnFailAction(data.get("on_fail", "Skip")),
            on_fail_label=data.get("on_fail_label"),
            variables_out=data.get("variables_out", [])
        )

class KeyPressCommand(Command):
    """Keyboard key press command"""
    def __init__(
        self,
        name: str,
        key: str = "",
        repeat: int = 1,
        delay_between_ms: int = 100,
        **kwargs
    ):
        super().__init__(name, CommandType.KEY_PRESS, **kwargs)
        self.key = key
        self.repeat = repeat
        self.delay_between_ms = delay_between_ms

    def to_dict(self) -> dict:
        data = super().to_dict()
        data.update({
            "key": self.key,
            "repeat": self.repeat,
            "delay_between_ms": self.delay_between_ms
        })
        return data

    @staticmethod
    def from_dict(data: dict) -> 'KeyPressCommand':
        return KeyPressCommand(
            name=data["name"],
            key=data.get("key", ""),
            repeat=data.get("repeat", 1),
            delay_between_ms=data.get("delay_between_ms", 100),
            enabled=data.get("enabled", True),
            parent_id=data.get("parent_id"),
            on_fail=OnFailAction(data.get("on_fail", "Skip")),
            on_fail_label=data.get("on_fail_label"),
            variables_out=data.get("variables_out", [])
        )

class HotKeyCommand(Command):
    """Hotkey combination command"""
    def __init__(
        self,
        name: str,
        keys: List[str] = None,
        hotkey_order: HotKeyOrder = HotKeyOrder.SIMULTANEOUS,
        **kwargs
    ):
        super().__init__(name, CommandType.HOT_KEY, **kwargs)
        self.keys = keys or []
        self.hotkey_order = hotkey_order

    def to_dict(self) -> dict:
        data = super().to_dict()
        data.update({
            "keys": self.keys,
            "hotkey_order": self.hotkey_order.value
        })
        return data

    @staticmethod
    def from_dict(data: dict) -> 'HotKeyCommand':
        return HotKeyCommand(
            name=data["name"],
            keys=data.get("keys", []),
            hotkey_order=HotKeyOrder(data.get("hotkey_order", "Simultaneous")),
            enabled=data.get("enabled", True),
            parent_id=data.get("parent_id"),
            on_fail=OnFailAction(data.get("on_fail", "Skip")),
            on_fail_label=data.get("on_fail_label"),
            variables_out=data.get("variables_out", [])
        )

class TextCommand(Command):
    """Text input command"""
    def __init__(
        self,
        name: str,
        content: str = "",
        text_mode: TextMode = TextMode.PASTE,
        speed_min_cps: int = 10,
        speed_max_cps: int = 30,
        focus_x: Optional[int] = None,
        focus_y: Optional[int] = None,
        **kwargs
    ):
        super().__init__(name, CommandType.TEXT, **kwargs)
        self.content = content
        self.text_mode = text_mode
        self.speed_min_cps = speed_min_cps
        self.speed_max_cps = speed_max_cps
        self.focus_x = focus_x
        self.focus_y = focus_y

    def to_dict(self) -> dict:
        data = super().to_dict()
        data.update({
            "content": self.content,
            "text_mode": self.text_mode.value,
            "speed_min_cps": self.speed_min_cps,
            "speed_max_cps": self.speed_max_cps,
            "focus_x": self.focus_x,
            "focus_y": self.focus_y
        })
        return data

    @staticmethod
    def from_dict(data: dict) -> 'TextCommand':
        return TextCommand(
            name=data["name"],
            content=data.get("content", ""),
            text_mode=TextMode(data.get("text_mode", "Paste")),
            speed_min_cps=data.get("speed_min_cps", 10),
            speed_max_cps=data.get("speed_max_cps", 30),
            focus_x=data.get("focus_x"),
            focus_y=data.get("focus_y"),
            enabled=data.get("enabled", True),
            parent_id=data.get("parent_id"),
            on_fail=OnFailAction(data.get("on_fail", "Skip")),
            on_fail_label=data.get("on_fail_label"),
            variables_out=data.get("variables_out", [])
        )

class WaitCommand(Command):
    """Wait command with various wait types"""
    def __init__(
        self,
        name: str,
        wait_type: WaitType = WaitType.TIMEOUT,
        timeout_sec: int = 30,
        pixel_x: Optional[int] = None,
        pixel_y: Optional[int] = None,
        pixel_color: Optional[tuple] = None,
        pixel_tolerance: Optional[int] = None,
        screen_threshold: float = 0.9,
        region_x1: Optional[int] = None,
        region_y1: Optional[int] = None,
        region_x2: Optional[int] = None,
        region_y2: Optional[int] = None,
        **kwargs
    ):
        super().__init__(name, CommandType.WAIT, **kwargs)
        self.wait_type = wait_type
        self.timeout_sec = timeout_sec
        self.pixel_x = pixel_x
        self.pixel_y = pixel_y
        self.pixel_color = pixel_color
        self.pixel_tolerance = pixel_tolerance
        self.screen_threshold = screen_threshold
        self.region_x1 = region_x1
        self.region_y1 = region_y1
        self.region_x2 = region_x2
        self.region_y2 = region_y2

    def to_dict(self) -> dict:
        data = super().to_dict()
        data.update({
            "wait_type": self.wait_type.value,
            "timeout_sec": self.timeout_sec,
            "pixel_x": self.pixel_x,
            "pixel_y": self.pixel_y,
            "pixel_color": self.pixel_color,
            "pixel_tolerance": self.pixel_tolerance,
            "screen_threshold": self.screen_threshold,
            "region_x1": self.region_x1,
            "region_y1": self.region_y1,
            "region_x2": self.region_x2,
            "region_y2": self.region_y2
        })
        return data

    @staticmethod
    def from_dict(data: dict) -> 'WaitCommand':
        return WaitCommand(
            name=data["name"],
            wait_type=WaitType(data.get("wait_type", "Timeout")),
            timeout_sec=data.get("timeout_sec", 30),
            pixel_x=data.get("pixel_x"),
            pixel_y=data.get("pixel_y"),
            pixel_color=tuple(data["pixel_color"]) if data.get("pixel_color") else None,
            pixel_tolerance=data.get("pixel_tolerance"),
            screen_threshold=data.get("screen_threshold", 0.9),
            region_x1=data.get("region_x1"),
            region_y1=data.get("region_y1"),
            region_x2=data.get("region_x2"),
            region_y2=data.get("region_y2"),
            enabled=data.get("enabled", True),
            parent_id=data.get("parent_id"),
            on_fail=OnFailAction(data.get("on_fail", "Skip")),
            on_fail_label=data.get("on_fail_label"),
            variables_out=data.get("variables_out", [])
        )

class RepeatCommand(Command):
    """Repeat command with nested commands"""
    def __init__(
        self,
        name: str,
        count: int = 0,  # 0 = infinite (limited by max_iterations)
        until_condition_expr: Optional[str] = None,
        inner_commands: Optional[List[Command]] = None,
        **kwargs
    ):
        super().__init__(name, CommandType.REPEAT, **kwargs)
        self.count = count
        self.until_condition_expr = until_condition_expr
        self.inner_commands = inner_commands or []

    def to_dict(self) -> dict:
        data = super().to_dict()
        data.update({
            "count": self.count,
            "until_condition_expr": self.until_condition_expr,
            "inner_commands": [cmd.to_dict() for cmd in self.inner_commands]
        })
        return data

    @staticmethod
    def from_dict(data: dict) -> 'RepeatCommand':
        # Inner commands will be deserialized recursively
        inner_cmds = []
        for cmd_data in data.get("inner_commands", []):
            cmd_type = CommandType(cmd_data["type"])
            cmd_class = COMMAND_TYPE_MAP.get(cmd_type)
            if cmd_class:
                inner_cmds.append(cmd_class.from_dict(cmd_data))
        
        return RepeatCommand(
            name=data["name"],
            count=data.get("count", 0),
            until_condition_expr=data.get("until_condition_expr"),
            inner_commands=inner_cmds,
            enabled=data.get("enabled", True),
            parent_id=data.get("parent_id"),
            on_fail=OnFailAction(data.get("on_fail", "Skip")),
            on_fail_label=data.get("on_fail_label"),
            variables_out=data.get("variables_out", [])
        )

class GotoCommand(Command):
    """Goto command with optional condition"""
    def __init__(
        self,
        name: str,
        target_label: str = "",
        condition_expr: Optional[str] = None,
        **kwargs
    ):
        super().__init__(name, CommandType.GOTO, **kwargs)
        self.target_label = target_label
        self.condition_expr = condition_expr

    def to_dict(self) -> dict:
        data = super().to_dict()
        data.update({
            "target_label": self.target_label,
            "condition_expr": self.condition_expr
        })
        return data

    @staticmethod
    def from_dict(data: dict) -> 'GotoCommand':
        return GotoCommand(
            name=data["name"],
            target_label=data.get("target_label", ""),
            condition_expr=data.get("condition_expr"),
            enabled=data.get("enabled", True),
            parent_id=data.get("parent_id"),
            on_fail=OnFailAction(data.get("on_fail", "Skip")),
            on_fail_label=data.get("on_fail_label"),
            variables_out=data.get("variables_out", [])
        )

class ConditionCommand(Command):
    """Conditional branching command"""
    def __init__(
        self,
        name: str,
        expr: str = "",
        then_label: Optional[str] = None,
        else_label: Optional[str] = None,
        nested_then: Optional[List[Command]] = None,
        nested_else: Optional[List[Command]] = None,
        **kwargs
    ):
        super().__init__(name, CommandType.CONDITION, **kwargs)
        self.expr = expr
        self.then_label = then_label
        self.else_label = else_label
        self.nested_then = nested_then or []
        self.nested_else = nested_else or []

    def to_dict(self) -> dict:
        data = super().to_dict()
        data.update({
            "expr": self.expr,
            "then_label": self.then_label,
            "else_label": self.else_label,
            "nested_then": [cmd.to_dict() for cmd in self.nested_then],
            "nested_else": [cmd.to_dict() for cmd in self.nested_else]
        })
        return data

    @staticmethod
    def from_dict(data: dict) -> 'ConditionCommand':
        # Nested commands deserialization
        nested_then = []
        for cmd_data in data.get("nested_then", []):
            cmd_type = CommandType(cmd_data["type"])
            cmd_class = COMMAND_TYPE_MAP.get(cmd_type)
            if cmd_class:
                nested_then.append(cmd_class.from_dict(cmd_data))
        
        nested_else = []
        for cmd_data in data.get("nested_else", []):
            cmd_type = CommandType(cmd_data["type"])
            cmd_class = COMMAND_TYPE_MAP.get(cmd_type)
            if cmd_class:
                nested_else.append(cmd_class.from_dict(cmd_data))
        
        return ConditionCommand(
            name=data["name"],
            expr=data.get("expr", ""),
            then_label=data.get("then_label"),
            else_label=data.get("else_label"),
            nested_then=nested_then,
            nested_else=nested_else,
            enabled=data.get("enabled", True),
            parent_id=data.get("parent_id"),
            on_fail=OnFailAction(data.get("on_fail", "Skip")),
            on_fail_label=data.get("on_fail_label"),
            variables_out=data.get("variables_out", [])
        )

# Command type mapping for deserialization
COMMAND_TYPE_MAP = {
    CommandType.CLICK: ClickCommand,
    CommandType.CROP_IMAGE: CropImageCommand,
    CommandType.KEY_PRESS: KeyPressCommand,
    CommandType.HOT_KEY: HotKeyCommand,
    CommandType.TEXT: TextCommand,
    CommandType.WAIT: WaitCommand,
    CommandType.REPEAT: RepeatCommand,
    CommandType.GOTO: GotoCommand,
    CommandType.CONDITION: ConditionCommand
}

# ==================== SCRIPT ====================
class Script:
    """Script container with execution sequence and variables"""
    def __init__(
        self,
        sequence: Optional[List[Command]] = None,
        variables_global: Optional[Dict[str, Any]] = None,
        max_iterations: int = 10000,
        on_error_handler: Optional[Command] = None
    ):
        self.sequence: List[Command] = sequence or []
        self.label_map: Dict[str, str] = {}  # Name → Command ID
        self.variables_global: Dict[str, Any] = variables_global or {}
        self.max_iterations: int = max_iterations
        self.on_error_handler: Optional[Command] = on_error_handler
        
        # Build label map
        self._build_label_map()

    def _build_label_map(self):
        """Build label map from all commands"""
        self.label_map = {}
        for cmd in self.sequence:
            if cmd.name:
                self.label_map[cmd.name] = cmd.id

    def get_command_by_id(self, cmd_id: str) -> Optional[Command]:
        """Get command by ID"""
        for cmd in self.sequence:
            if cmd.id == cmd_id:
                return cmd
        return None

    def get_command_by_label(self, label: str) -> Optional[Command]:
        """Get command by label (name)"""
        cmd_id = self.label_map.get(label)
        if cmd_id:
            return self.get_command_by_id(cmd_id)
        return None

    def to_dict(self) -> dict:
        """Serialize script to dictionary"""
        return {
            "sequence": [cmd.to_dict() for cmd in self.sequence],
            "variables_global": self.variables_global,
            "max_iterations": self.max_iterations,
            "on_error_handler": self.on_error_handler.to_dict() if self.on_error_handler else None
        }

    @staticmethod
    def from_dict(data: dict) -> 'Script':
        """Deserialize script from dictionary"""
        sequence = []
        for cmd_data in data.get("sequence", []):
            cmd_type = CommandType(cmd_data["type"])
            cmd_class = COMMAND_TYPE_MAP.get(cmd_type)
            if cmd_class:
                sequence.append(cmd_class.from_dict(cmd_data))
        
        on_error = None
        if data.get("on_error_handler"):
            err_type = CommandType(data["on_error_handler"]["type"])
            err_class = COMMAND_TYPE_MAP.get(err_type)
            if err_class:
                on_error = err_class.from_dict(data["on_error_handler"])
        
        return Script(
            sequence=sequence,
            variables_global=data.get("variables_global", {}),
            max_iterations=data.get("max_iterations", 10000),
            on_error_handler=on_error
        )

# ==================== LEGACY SUPPORT ====================
class WindowInfo:
    def __init__(self, hwnd: int, title: str, rect: tuple):
        self.hwnd = hwnd            # window handle
        self.title = title          # window title
        self.rect = rect            # (x, y, w, h)

        self.status = "UNKNOWN"     # READY / WAIT / FAIL
        self.preview = None         # ảnh preview (numpy array)

    def __repr__(self):
        return f"<WindowInfo {self.title} | {self.status}>"
