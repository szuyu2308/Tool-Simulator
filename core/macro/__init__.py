# AI GOVERNANCE:
# Apply auditor-router
# This is a CODE change

"""
Macro Recorder Package
Provides recording, playback, and editing of macro actions
"""

from .models import (
    Macro, MacroAction, MacroActionType, MacroSettings, MacroTarget,
    MacroRecordingMode, MacroSpeedMode, MacroOnError,
    WindowMatch, HotkeyConfig,
    MouseMoveAction, MouseClickAction, MouseDragAction, MouseScrollAction,
    KeyPressAction, HotkeyAction, TextInputAction,
    WaitTimeAction, WaitPixelAction, WaitImageAction, WaitWindowAction,
    IfThenElseAction, WindowFocusAction, WindowMoveResizeAction,
    MouseButton, MouseCurve, KeyPressMode, HotkeyOrder, TextInputMode
)

from .recorder import (
    MacroRecorder, RecorderState,
    RawEvent, RawEventType,
    IRecorderHook, PynputHook,
    WindowUtils, GlobalHotkeyManager
)

from .processor import (
    MacroEventProcessor,
    create_macro_from_events,
    rdp_simplify
)

from .player import (
    MacroPlayer, PlaybackState, PlaybackContext
)

from .manager import (
    MacroManager,
    get_macro_manager
)


__all__ = [
    # Models
    'Macro', 'MacroAction', 'MacroActionType', 'MacroSettings', 'MacroTarget',
    'MacroRecordingMode', 'MacroSpeedMode', 'MacroOnError',
    'WindowMatch', 'HotkeyConfig',
    
    # Action types
    'MouseMoveAction', 'MouseClickAction', 'MouseDragAction', 'MouseScrollAction',
    'KeyPressAction', 'HotkeyAction', 'TextInputAction',
    'WaitTimeAction', 'WaitPixelAction', 'WaitImageAction', 'WaitWindowAction',
    'IfThenElseAction', 'WindowFocusAction', 'WindowMoveResizeAction',
    
    # Enums
    'MouseButton', 'MouseCurve', 'KeyPressMode', 'HotkeyOrder', 'TextInputMode',
    
    # Recorder
    'MacroRecorder', 'RecorderState',
    'RawEvent', 'RawEventType',
    'IRecorderHook', 'PynputHook',
    'WindowUtils', 'GlobalHotkeyManager',
    
    # Processor
    'MacroEventProcessor', 'create_macro_from_events', 'rdp_simplify',
    
    # Player
    'MacroPlayer', 'PlaybackState', 'PlaybackContext',
    
    # Manager
    'MacroManager', 'get_macro_manager',
]
