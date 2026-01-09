# AI GOVERNANCE:
# Apply auditor-router
# This is a CODE change

"""
Macro Recorder Data Models (.mrf format)
Defines all action types and macro structure for recording/playback
"""

from enum import Enum
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass, field
import uuid
import json
from datetime import datetime


# ==================== ENUMS ====================

class MacroRecordingMode(Enum):
    NORMAL = "normal"
    SMART = "smart"


class MacroSpeedMode(Enum):
    REALTIME = "realtime"
    ACCELERATED = "accelerated"


class MacroOnError(Enum):
    PAUSE = "pause"
    SKIP = "skip"
    STOP = "stop"
    INHERIT = "inherit"


class MacroActionType(Enum):
    # Mouse actions
    MOUSE_MOVE = "mouse_move"
    MOUSE_CLICK = "mouse_click"
    MOUSE_DRAG = "mouse_drag"
    MOUSE_SCROLL = "mouse_scroll"
    
    # Keyboard actions
    KEY_PRESS = "key_press"
    HOTKEY = "hotkey"
    TEXT_INPUT = "text_input"
    
    # Wait/Condition actions
    WAIT_TIME = "wait_time"
    WAIT_PIXEL = "wait_pixel"
    WAIT_IMAGE = "wait_image"
    WAIT_WINDOW = "wait_window"
    IF_THEN_ELSE = "if_then_else"
    
    # Window actions
    WINDOW_FOCUS = "window_focus"
    WINDOW_MOVE_RESIZE = "window_move_resize"


class MouseButton(Enum):
    LEFT = "left"
    RIGHT = "right"
    MIDDLE = "middle"
    DOUBLE = "double"


class MouseCurve(Enum):
    LINEAR = "linear"
    BEZIER = "bezier"


class KeyPressMode(Enum):
    PRESS = "press"
    DOWN = "down"
    UP = "up"


class HotkeyOrder(Enum):
    SIMULTANEOUS = "simultaneous"
    SEQUENCE = "sequence"


class TextInputMode(Enum):
    PASTE = "paste"
    HUMANIZE = "humanize"


# ==================== WINDOW MATCH ====================

@dataclass
class WindowMatch:
    """Window matching criteria for auto-focus"""
    title_contains: Optional[str] = None
    class_name: Optional[str] = None
    process_name: Optional[str] = None
    require_exact: bool = False
    
    def to_dict(self) -> dict:
        return {
            "title_contains": self.title_contains,
            "class_name": self.class_name,
            "process_name": self.process_name,
            "require_exact": self.require_exact
        }
    
    @staticmethod
    def from_dict(data: dict) -> 'WindowMatch':
        return WindowMatch(
            title_contains=data.get("title_contains"),
            class_name=data.get("class_name"),
            process_name=data.get("process_name"),
            require_exact=data.get("require_exact", False)
        )


# ==================== HOTKEY CONFIG ====================

@dataclass
class HotkeyConfig:
    """Global hotkey configuration"""
    record_start_stop: str = "Ctrl+Shift+R"
    play_toggle: str = "Ctrl+Shift+P"
    pause_toggle: str = "Ctrl+Shift+Space"
    stop_playback: str = "Ctrl+Shift+S"
    
    def to_dict(self) -> dict:
        return {
            "record_start_stop": self.record_start_stop,
            "play_toggle": self.play_toggle,
            "pause_toggle": self.pause_toggle,
            "stop_playback": self.stop_playback
        }
    
    @staticmethod
    def from_dict(data: dict) -> 'HotkeyConfig':
        return HotkeyConfig(
            record_start_stop=data.get("record_start_stop", "Ctrl+Shift+R"),
            play_toggle=data.get("play_toggle", "Ctrl+Shift+P"),
            pause_toggle=data.get("pause_toggle", "Ctrl+Shift+Space"),
            stop_playback=data.get("stop_playback", "Ctrl+Shift+S")
        )


# ==================== MACRO SETTINGS ====================

@dataclass
class MacroSettings:
    """Macro recording/playback settings"""
    recording_mode: MacroRecordingMode = MacroRecordingMode.NORMAL
    include_mouse_move: bool = True
    mouse_move_min_delta_px: int = 5
    include_erratic_moves: bool = False
    record_speed_mode: MacroSpeedMode = MacroSpeedMode.REALTIME
    play_speed_multiplier: float = 1.0
    default_on_error: MacroOnError = MacroOnError.PAUSE
    retry_count: int = 0
    hotkeys: HotkeyConfig = field(default_factory=HotkeyConfig)
    
    def to_dict(self) -> dict:
        return {
            "recording_mode": self.recording_mode.value,
            "include_mouse_move": self.include_mouse_move,
            "mouse_move_min_delta_px": self.mouse_move_min_delta_px,
            "include_erratic_moves": self.include_erratic_moves,
            "record_speed_mode": self.record_speed_mode.value,
            "play_speed_multiplier": self.play_speed_multiplier,
            "default_on_error": self.default_on_error.value,
            "retry_count": self.retry_count,
            "hotkeys": self.hotkeys.to_dict()
        }
    
    @staticmethod
    def from_dict(data: dict) -> 'MacroSettings':
        return MacroSettings(
            recording_mode=MacroRecordingMode(data.get("recording_mode", "normal")),
            include_mouse_move=data.get("include_mouse_move", True),
            mouse_move_min_delta_px=data.get("mouse_move_min_delta_px", 5),
            include_erratic_moves=data.get("include_erratic_moves", False),
            record_speed_mode=MacroSpeedMode(data.get("record_speed_mode", "realtime")),
            play_speed_multiplier=data.get("play_speed_multiplier", 1.0),
            default_on_error=MacroOnError(data.get("default_on_error", "pause")),
            retry_count=data.get("retry_count", 0),
            hotkeys=HotkeyConfig.from_dict(data.get("hotkeys", {}))
        )


# ==================== MACRO TARGET ====================

@dataclass
class MacroTarget:
    """Target window configuration"""
    window_match: WindowMatch = field(default_factory=WindowMatch)
    record_coord_mode: str = "client_pixels"  # LOCKED
    playback_coord_mode: str = "client_pixels"  # LOCKED
    
    def to_dict(self) -> dict:
        return {
            "window_match": self.window_match.to_dict(),
            "record_coord_mode": self.record_coord_mode,
            "playback_coord_mode": self.playback_coord_mode
        }
    
    @staticmethod
    def from_dict(data: dict) -> 'MacroTarget':
        return MacroTarget(
            window_match=WindowMatch.from_dict(data.get("window_match", {})),
            record_coord_mode=data.get("record_coord_mode", "client_pixels"),
            playback_coord_mode=data.get("playback_coord_mode", "client_pixels")
        )


# ==================== BASE ACTION ====================

@dataclass
class MacroAction:
    """Base class for all macro actions"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: MacroActionType = MacroActionType.WAIT_TIME
    t_ms: int = 0  # Timestamp offset from macro start
    enabled: bool = True
    comment: Optional[str] = None
    on_error: MacroOnError = MacroOnError.INHERIT
    retry: Optional[int] = None
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type.value,
            "t_ms": self.t_ms,
            "enabled": self.enabled,
            "comment": self.comment,
            "on_error": self.on_error.value,
            "retry": self.retry
        }
    
    @staticmethod
    def from_dict(data: dict) -> 'MacroAction':
        """Factory method to create appropriate action subclass"""
        action_type = MacroActionType(data.get("type", "wait_time"))
        
        # Map to specific action class
        action_classes = {
            MacroActionType.MOUSE_MOVE: MouseMoveAction,
            MacroActionType.MOUSE_CLICK: MouseClickAction,
            MacroActionType.MOUSE_DRAG: MouseDragAction,
            MacroActionType.MOUSE_SCROLL: MouseScrollAction,
            MacroActionType.KEY_PRESS: KeyPressAction,
            MacroActionType.HOTKEY: HotkeyAction,
            MacroActionType.TEXT_INPUT: TextInputAction,
            MacroActionType.WAIT_TIME: WaitTimeAction,
            MacroActionType.WAIT_PIXEL: WaitPixelAction,
            MacroActionType.WAIT_IMAGE: WaitImageAction,
            MacroActionType.WAIT_WINDOW: WaitWindowAction,
            MacroActionType.IF_THEN_ELSE: IfThenElseAction,
            MacroActionType.WINDOW_FOCUS: WindowFocusAction,
            MacroActionType.WINDOW_MOVE_RESIZE: WindowMoveResizeAction,
        }
        
        action_class = action_classes.get(action_type, MacroAction)
        return action_class.from_dict_impl(data)
    
    @classmethod
    def from_dict_impl(cls, data: dict) -> 'MacroAction':
        """Default implementation for base class"""
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            type=MacroActionType(data.get("type", "wait_time")),
            t_ms=data.get("t_ms", 0),
            enabled=data.get("enabled", True),
            comment=data.get("comment"),
            on_error=MacroOnError(data.get("on_error", "inherit")),
            retry=data.get("retry")
        )
    
    def get_summary(self) -> str:
        """Get human-readable summary for UI display"""
        return f"{self.type.value} @ {self.t_ms}ms"


# ==================== MOUSE ACTIONS ====================

@dataclass
class MouseMoveAction(MacroAction):
    """Mouse move action with optional path"""
    x: int = 0
    y: int = 0
    path: Optional[List[Tuple[int, int, int]]] = None  # [(x, y, dt_ms), ...]
    curve: MouseCurve = MouseCurve.LINEAR
    
    def __post_init__(self):
        self.type = MacroActionType.MOUSE_MOVE
    
    def to_dict(self) -> dict:
        data = super().to_dict()
        data.update({
            "x": self.x,
            "y": self.y,
            "path": self.path,
            "curve": self.curve.value
        })
        return data
    
    @classmethod
    def from_dict_impl(cls, data: dict) -> 'MouseMoveAction':
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            t_ms=data.get("t_ms", 0),
            enabled=data.get("enabled", True),
            comment=data.get("comment"),
            on_error=MacroOnError(data.get("on_error", "inherit")),
            retry=data.get("retry"),
            x=data.get("x", 0),
            y=data.get("y", 0),
            path=data.get("path"),
            curve=MouseCurve(data.get("curve", "linear"))
        )
    
    def get_summary(self) -> str:
        if self.path:
            return f"Move path ({len(self.path)} points)"
        return f"Move to ({self.x}, {self.y})"


@dataclass
class MouseClickAction(MacroAction):
    """Mouse click action"""
    button: MouseButton = MouseButton.LEFT
    x: int = 0
    y: int = 0
    hold_ms: Optional[int] = None
    repeat: int = 1
    jitter_px: Optional[int] = None
    
    def __post_init__(self):
        self.type = MacroActionType.MOUSE_CLICK
    
    def to_dict(self) -> dict:
        data = super().to_dict()
        data.update({
            "button": self.button.value,
            "x": self.x,
            "y": self.y,
            "hold_ms": self.hold_ms,
            "repeat": self.repeat,
            "jitter_px": self.jitter_px
        })
        return data
    
    @classmethod
    def from_dict_impl(cls, data: dict) -> 'MouseClickAction':
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            t_ms=data.get("t_ms", 0),
            enabled=data.get("enabled", True),
            comment=data.get("comment"),
            on_error=MacroOnError(data.get("on_error", "inherit")),
            retry=data.get("retry"),
            button=MouseButton(data.get("button", "left")),
            x=data.get("x", 0),
            y=data.get("y", 0),
            hold_ms=data.get("hold_ms"),
            repeat=data.get("repeat", 1),
            jitter_px=data.get("jitter_px")
        )
    
    def get_summary(self) -> str:
        btn = self.button.value.capitalize()
        return f"{btn} click @ ({self.x}, {self.y})"


@dataclass
class MouseDragAction(MacroAction):
    """Mouse drag action"""
    x1: int = 0
    y1: int = 0
    x2: int = 0
    y2: int = 0
    button: MouseButton = MouseButton.LEFT
    duration_ms: int = 200
    path: Optional[List[Tuple[int, int, int]]] = None
    
    def __post_init__(self):
        self.type = MacroActionType.MOUSE_DRAG
    
    def to_dict(self) -> dict:
        data = super().to_dict()
        data.update({
            "x1": self.x1,
            "y1": self.y1,
            "x2": self.x2,
            "y2": self.y2,
            "button": self.button.value,
            "duration_ms": self.duration_ms,
            "path": self.path
        })
        return data
    
    @classmethod
    def from_dict_impl(cls, data: dict) -> 'MouseDragAction':
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            t_ms=data.get("t_ms", 0),
            enabled=data.get("enabled", True),
            comment=data.get("comment"),
            on_error=MacroOnError(data.get("on_error", "inherit")),
            retry=data.get("retry"),
            x1=data.get("x1", 0),
            y1=data.get("y1", 0),
            x2=data.get("x2", 0),
            y2=data.get("y2", 0),
            button=MouseButton(data.get("button", "left")),
            duration_ms=data.get("duration_ms", 200),
            path=data.get("path")
        )
    
    def get_summary(self) -> str:
        return f"Drag ({self.x1},{self.y1}) → ({self.x2},{self.y2})"


@dataclass
class MouseScrollAction(MacroAction):
    """Mouse scroll action"""
    x: int = 0
    y: int = 0
    delta: int = 3  # Lines/clicks
    direction: str = "down"  # up/down
    
    def __post_init__(self):
        self.type = MacroActionType.MOUSE_SCROLL
    
    def to_dict(self) -> dict:
        data = super().to_dict()
        data.update({
            "x": self.x,
            "y": self.y,
            "delta": self.delta,
            "direction": self.direction
        })
        return data
    
    @classmethod
    def from_dict_impl(cls, data: dict) -> 'MouseScrollAction':
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            t_ms=data.get("t_ms", 0),
            enabled=data.get("enabled", True),
            comment=data.get("comment"),
            on_error=MacroOnError(data.get("on_error", "inherit")),
            retry=data.get("retry"),
            x=data.get("x", 0),
            y=data.get("y", 0),
            delta=data.get("delta", 3),
            direction=data.get("direction", "down")
        )
    
    def get_summary(self) -> str:
        return f"Scroll {self.direction} ({self.delta}) @ ({self.x},{self.y})"


# ==================== KEYBOARD ACTIONS ====================

@dataclass
class KeyPressAction(MacroAction):
    """Key press action"""
    key: str = ""
    mode: KeyPressMode = KeyPressMode.PRESS
    repeat: int = 1
    delay_between_ms: int = 50
    
    def __post_init__(self):
        self.type = MacroActionType.KEY_PRESS
    
    def to_dict(self) -> dict:
        data = super().to_dict()
        data.update({
            "key": self.key,
            "mode": self.mode.value,
            "repeat": self.repeat,
            "delay_between_ms": self.delay_between_ms
        })
        return data
    
    @classmethod
    def from_dict_impl(cls, data: dict) -> 'KeyPressAction':
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            t_ms=data.get("t_ms", 0),
            enabled=data.get("enabled", True),
            comment=data.get("comment"),
            on_error=MacroOnError(data.get("on_error", "inherit")),
            retry=data.get("retry"),
            key=data.get("key", ""),
            mode=KeyPressMode(data.get("mode", "press")),
            repeat=data.get("repeat", 1),
            delay_between_ms=data.get("delay_between_ms", 50)
        )
    
    def get_summary(self) -> str:
        return f"Key: {self.key}" + (f" x{self.repeat}" if self.repeat > 1 else "")


@dataclass
class HotkeyAction(MacroAction):
    """Hotkey combination action"""
    keys: List[str] = field(default_factory=list)
    order: HotkeyOrder = HotkeyOrder.SIMULTANEOUS
    
    def __post_init__(self):
        self.type = MacroActionType.HOTKEY
    
    def to_dict(self) -> dict:
        data = super().to_dict()
        data.update({
            "keys": self.keys,
            "order": self.order.value
        })
        return data
    
    @classmethod
    def from_dict_impl(cls, data: dict) -> 'HotkeyAction':
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            t_ms=data.get("t_ms", 0),
            enabled=data.get("enabled", True),
            comment=data.get("comment"),
            on_error=MacroOnError(data.get("on_error", "inherit")),
            retry=data.get("retry"),
            keys=data.get("keys", []),
            order=HotkeyOrder(data.get("order", "simultaneous"))
        )
    
    def get_summary(self) -> str:
        return f"Hotkey: {'+'.join(self.keys)}"


@dataclass
class TextInputAction(MacroAction):
    """Text input action"""
    text: str = ""
    mode: TextInputMode = TextInputMode.PASTE
    cps_min: int = 5  # Characters per second min
    cps_max: int = 15  # Characters per second max
    focus_x: Optional[int] = None
    focus_y: Optional[int] = None
    
    def __post_init__(self):
        self.type = MacroActionType.TEXT_INPUT
    
    def to_dict(self) -> dict:
        data = super().to_dict()
        data.update({
            "text": self.text,
            "mode": self.mode.value,
            "cps_min": self.cps_min,
            "cps_max": self.cps_max,
            "focus_x": self.focus_x,
            "focus_y": self.focus_y
        })
        return data
    
    @classmethod
    def from_dict_impl(cls, data: dict) -> 'TextInputAction':
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            t_ms=data.get("t_ms", 0),
            enabled=data.get("enabled", True),
            comment=data.get("comment"),
            on_error=MacroOnError(data.get("on_error", "inherit")),
            retry=data.get("retry"),
            text=data.get("text", ""),
            mode=TextInputMode(data.get("mode", "paste")),
            cps_min=data.get("cps_min", 5),
            cps_max=data.get("cps_max", 15),
            focus_x=data.get("focus_x"),
            focus_y=data.get("focus_y")
        )
    
    def get_summary(self) -> str:
        preview = self.text[:20] + "..." if len(self.text) > 20 else self.text
        return f'Text: "{preview}"'


# ==================== WAIT/CONDITION ACTIONS ====================

@dataclass
class WaitTimeAction(MacroAction):
    """Wait for specified time"""
    ms: int = 1000
    variance_ms: Optional[int] = None
    
    def __post_init__(self):
        self.type = MacroActionType.WAIT_TIME
    
    def to_dict(self) -> dict:
        data = super().to_dict()
        data.update({
            "ms": self.ms,
            "variance_ms": self.variance_ms
        })
        return data
    
    @classmethod
    def from_dict_impl(cls, data: dict) -> 'WaitTimeAction':
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            t_ms=data.get("t_ms", 0),
            enabled=data.get("enabled", True),
            comment=data.get("comment"),
            on_error=MacroOnError(data.get("on_error", "inherit")),
            retry=data.get("retry"),
            ms=data.get("ms", 1000),
            variance_ms=data.get("variance_ms")
        )
    
    def get_summary(self) -> str:
        if self.variance_ms:
            return f"Wait {self.ms}±{self.variance_ms}ms"
        return f"Wait {self.ms}ms"


@dataclass
class WaitPixelAction(MacroAction):
    """Wait for pixel color"""
    x: int = 0
    y: int = 0
    rgb: Tuple[int, int, int] = (0, 0, 0)
    tolerance: int = 10
    timeout_ms: int = 30000
    poll_ms: int = 100  # LOCKED default
    
    def __post_init__(self):
        self.type = MacroActionType.WAIT_PIXEL
    
    def to_dict(self) -> dict:
        data = super().to_dict()
        data.update({
            "x": self.x,
            "y": self.y,
            "rgb": list(self.rgb),
            "tolerance": self.tolerance,
            "timeout_ms": self.timeout_ms,
            "poll_ms": self.poll_ms
        })
        return data
    
    @classmethod
    def from_dict_impl(cls, data: dict) -> 'WaitPixelAction':
        rgb = data.get("rgb", [0, 0, 0])
        if isinstance(rgb, list):
            rgb = tuple(rgb)
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            t_ms=data.get("t_ms", 0),
            enabled=data.get("enabled", True),
            comment=data.get("comment"),
            on_error=MacroOnError(data.get("on_error", "inherit")),
            retry=data.get("retry"),
            x=data.get("x", 0),
            y=data.get("y", 0),
            rgb=rgb,
            tolerance=data.get("tolerance", 10),
            timeout_ms=data.get("timeout_ms", 30000),
            poll_ms=data.get("poll_ms", 100)
        )
    
    def get_summary(self) -> str:
        return f"WaitPixel ({self.x},{self.y}) = RGB{self.rgb}"


@dataclass
class WaitImageAction(MacroAction):
    """Wait for image template (Milestone 2+)"""
    template_path: str = ""
    region: Optional[Tuple[int, int, int, int]] = None  # (x1, y1, x2, y2)
    threshold: float = 0.8
    timeout_ms: int = 30000
    
    def __post_init__(self):
        self.type = MacroActionType.WAIT_IMAGE
    
    def to_dict(self) -> dict:
        data = super().to_dict()
        data.update({
            "template_path": self.template_path,
            "region": list(self.region) if self.region else None,
            "threshold": self.threshold,
            "timeout_ms": self.timeout_ms
        })
        return data
    
    @classmethod
    def from_dict_impl(cls, data: dict) -> 'WaitImageAction':
        region = data.get("region")
        if isinstance(region, list):
            region = tuple(region)
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            t_ms=data.get("t_ms", 0),
            enabled=data.get("enabled", True),
            comment=data.get("comment"),
            on_error=MacroOnError(data.get("on_error", "inherit")),
            retry=data.get("retry"),
            template_path=data.get("template_path", ""),
            region=region,
            threshold=data.get("threshold", 0.8),
            timeout_ms=data.get("timeout_ms", 30000)
        )
    
    def get_summary(self) -> str:
        import os
        name = os.path.basename(self.template_path) if self.template_path else "?"
        return f"WaitImage: {name}"


@dataclass
class WaitWindowAction(MacroAction):
    """Wait for window to appear"""
    window_match: WindowMatch = field(default_factory=WindowMatch)
    timeout_ms: int = 30000
    
    def __post_init__(self):
        self.type = MacroActionType.WAIT_WINDOW
    
    def to_dict(self) -> dict:
        data = super().to_dict()
        data.update({
            "window_match": self.window_match.to_dict(),
            "timeout_ms": self.timeout_ms
        })
        return data
    
    @classmethod
    def from_dict_impl(cls, data: dict) -> 'WaitWindowAction':
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            t_ms=data.get("t_ms", 0),
            enabled=data.get("enabled", True),
            comment=data.get("comment"),
            on_error=MacroOnError(data.get("on_error", "inherit")),
            retry=data.get("retry"),
            window_match=WindowMatch.from_dict(data.get("window_match", {})),
            timeout_ms=data.get("timeout_ms", 30000)
        )
    
    def get_summary(self) -> str:
        target = self.window_match.title_contains or self.window_match.class_name or "?"
        return f"WaitWindow: {target}"


@dataclass
class IfThenElseAction(MacroAction):
    """Conditional action (maps to existing ConditionCommand)"""
    expr: str = ""  # Safe eval expression
    then_actions: List['MacroAction'] = field(default_factory=list)
    else_actions: List['MacroAction'] = field(default_factory=list)
    
    def __post_init__(self):
        self.type = MacroActionType.IF_THEN_ELSE
    
    def to_dict(self) -> dict:
        data = super().to_dict()
        data.update({
            "expr": self.expr,
            "then_actions": [a.to_dict() for a in self.then_actions],
            "else_actions": [a.to_dict() for a in self.else_actions]
        })
        return data
    
    @classmethod
    def from_dict_impl(cls, data: dict) -> 'IfThenElseAction':
        then_actions = [MacroAction.from_dict(a) for a in data.get("then_actions", [])]
        else_actions = [MacroAction.from_dict(a) for a in data.get("else_actions", [])]
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            t_ms=data.get("t_ms", 0),
            enabled=data.get("enabled", True),
            comment=data.get("comment"),
            on_error=MacroOnError(data.get("on_error", "inherit")),
            retry=data.get("retry"),
            expr=data.get("expr", ""),
            then_actions=then_actions,
            else_actions=else_actions
        )
    
    def get_summary(self) -> str:
        return f"If: {self.expr[:30]}..."


# ==================== WINDOW ACTIONS ====================

@dataclass
class WindowFocusAction(MacroAction):
    """Focus window action"""
    window_match: WindowMatch = field(default_factory=WindowMatch)
    restore_if_minimized: bool = True
    
    def __post_init__(self):
        self.type = MacroActionType.WINDOW_FOCUS
    
    def to_dict(self) -> dict:
        data = super().to_dict()
        data.update({
            "window_match": self.window_match.to_dict(),
            "restore_if_minimized": self.restore_if_minimized
        })
        return data
    
    @classmethod
    def from_dict_impl(cls, data: dict) -> 'WindowFocusAction':
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            t_ms=data.get("t_ms", 0),
            enabled=data.get("enabled", True),
            comment=data.get("comment"),
            on_error=MacroOnError(data.get("on_error", "inherit")),
            retry=data.get("retry"),
            window_match=WindowMatch.from_dict(data.get("window_match", {})),
            restore_if_minimized=data.get("restore_if_minimized", True)
        )
    
    def get_summary(self) -> str:
        target = self.window_match.title_contains or self.window_match.class_name or "?"
        return f"Focus: {target}"


@dataclass
class WindowMoveResizeAction(MacroAction):
    """Move/resize window action"""
    x: int = 0
    y: int = 0
    w: int = 800
    h: int = 600
    
    def __post_init__(self):
        self.type = MacroActionType.WINDOW_MOVE_RESIZE
    
    def to_dict(self) -> dict:
        data = super().to_dict()
        data.update({
            "x": self.x,
            "y": self.y,
            "w": self.w,
            "h": self.h
        })
        return data
    
    @classmethod
    def from_dict_impl(cls, data: dict) -> 'WindowMoveResizeAction':
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            t_ms=data.get("t_ms", 0),
            enabled=data.get("enabled", True),
            comment=data.get("comment"),
            on_error=MacroOnError(data.get("on_error", "inherit")),
            retry=data.get("retry"),
            x=data.get("x", 0),
            y=data.get("y", 0),
            w=data.get("w", 800),
            h=data.get("h", 600)
        )
    
    def get_summary(self) -> str:
        return f"Window: ({self.x},{self.y}) {self.w}x{self.h}"


# ==================== MACRO ====================

@dataclass
class Macro:
    """Main Macro container"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "New Macro"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    target: MacroTarget = field(default_factory=MacroTarget)
    settings: MacroSettings = field(default_factory=MacroSettings)
    actions: List[MacroAction] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "target": self.target.to_dict(),
            "settings": self.settings.to_dict(),
            "actions": [a.to_dict() for a in self.actions]
        }
    
    @staticmethod
    def from_dict(data: dict) -> 'Macro':
        actions = [MacroAction.from_dict(a) for a in data.get("actions", [])]
        return Macro(
            id=data.get("id", str(uuid.uuid4())),
            name=data.get("name", "New Macro"),
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.now().isoformat()),
            target=MacroTarget.from_dict(data.get("target", {})),
            settings=MacroSettings.from_dict(data.get("settings", {})),
            actions=actions
        )
    
    def save(self, filepath: str):
        """Save macro to .mrf file"""
        self.updated_at = datetime.now().isoformat()
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
    
    @staticmethod
    def load(filepath: str) -> 'Macro':
        """Load macro from .mrf file"""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return Macro.from_dict(data)
    
    def add_action(self, action: MacroAction):
        """Add action to macro"""
        self.actions.append(action)
    
    def remove_action(self, action_id: str):
        """Remove action by ID"""
        self.actions = [a for a in self.actions if a.id != action_id]
    
    def get_action(self, action_id: str) -> Optional[MacroAction]:
        """Get action by ID"""
        for action in self.actions:
            if action.id == action_id:
                return action
        return None
    
    def reorder_action(self, action_id: str, new_index: int):
        """Move action to new position"""
        action = self.get_action(action_id)
        if action:
            self.actions.remove(action)
            self.actions.insert(new_index, action)
    
    def get_duration_ms(self) -> int:
        """Get total macro duration in milliseconds"""
        if not self.actions:
            return 0
        return max(a.t_ms for a in self.actions)
