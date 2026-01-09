# AI GOVERNANCE:
# Apply auditor-router
# This is a CODE change

"""
Action Engine — Unified execution engine per UPGRADE_PLAN_V2 spec
Integrates: Mouse/Keyboard, Wait Actions, Image Actions, Flow Control
"""

from __future__ import annotations
import time
import threading
import ctypes
from ctypes import wintypes
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass
from enum import Enum

from utils.logger import log
from core.wait_actions import (
    WaitTime, WaitPixelColor, WaitScreenChange, WaitHotkey, WaitFile,
    create_wait_action, WaitResult
)
from core.image_actions import (
    FindImage, CaptureImage, find_image, capture_image, 
    ImageMatch, image_actions_available
)
from core.flow_control import (
    FlowController, FlowState, is_flow_control_action,
    create_label_action, create_goto_action
)

user32 = ctypes.windll.user32


class ActionStatus(Enum):
    """Status of action execution"""
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    TIMEOUT = "timeout"
    STOPPED = "stopped"


@dataclass
class ActionResult:
    """Result of action execution"""
    status: ActionStatus
    message: str = ""
    data: Optional[Any] = None
    duration_ms: int = 0


class ActionEngine:
    """
    Unified action execution engine
    Handles all action types with proper flow control
    """
    
    def __init__(self, 
                 target_hwnd: int = 0,
                 macros_dir: str = "data/macros",
                 debug_mode: bool = False):
        """
        Args:
            target_hwnd: Target window handle for actions
            macros_dir: Directory containing macro files
            debug_mode: Enable debug logging
        """
        self.target_hwnd = target_hwnd
        self.macros_dir = macros_dir
        self.debug_mode = debug_mode
        
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._pause_event.set()  # Not paused by default
        
        self._is_running = False
        self._current_index = 0
        self._actions: List[Dict[str, Any]] = []
        self._flow_controller: Optional[FlowController] = None
        
        # Callbacks
        self._on_action_start: Optional[Callable[[int, Dict], None]] = None
        self._on_action_complete: Optional[Callable[[int, ActionResult], None]] = None
        self._on_execution_complete: Optional[Callable[[bool], None]] = None
        
        # Variables for actions to share data
        self._variables: Dict[str, Any] = {}
    
    def set_target_window(self, hwnd: int):
        """Set target window for actions"""
        self.target_hwnd = hwnd
    
    def set_callbacks(self,
                      on_action_start: Optional[Callable[[int, Dict], None]] = None,
                      on_action_complete: Optional[Callable[[int, ActionResult], None]] = None,
                      on_execution_complete: Optional[Callable[[bool], None]] = None):
        """Set execution callbacks"""
        self._on_action_start = on_action_start
        self._on_action_complete = on_action_complete
        self._on_execution_complete = on_execution_complete
    
    def load_actions(self, actions: List[Dict[str, Any]]):
        """
        Load actions for execution
        
        Args:
            actions: List of action dictionaries
        """
        self._actions = actions
        self._flow_controller = FlowController(actions, self.macros_dir)
        self._current_index = 0
        log(f"[ENGINE] Loaded {len(actions)} actions")
    
    def start(self):
        """Start execution in background thread"""
        if self._is_running:
            log("[ENGINE] Already running")
            return
        
        if not self._actions:
            log("[ENGINE] No actions to execute")
            return
        
        self._stop_event.clear()
        self._pause_event.set()
        self._is_running = True
        self._current_index = 0
        
        thread = threading.Thread(target=self._execution_loop, daemon=True)
        thread.start()
    
    def stop(self):
        """Stop execution"""
        self._stop_event.set()
        self._pause_event.set()  # Unpause to allow stop
        self._is_running = False
        log("[ENGINE] Stop requested")
    
    def pause(self):
        """Pause execution"""
        self._pause_event.clear()
        log("[ENGINE] Paused")
    
    def resume(self):
        """Resume execution"""
        self._pause_event.set()
        log("[ENGINE] Resumed")
    
    def is_running(self) -> bool:
        """Check if engine is running"""
        return self._is_running
    
    def is_paused(self) -> bool:
        """Check if engine is paused"""
        return not self._pause_event.is_set()
    
    def get_variable(self, name: str, default: Any = None) -> Any:
        """Get a shared variable"""
        return self._variables.get(name, default)
    
    def set_variable(self, name: str, value: Any):
        """Set a shared variable"""
        self._variables[name] = value
    
    def _execution_loop(self):
        """Main execution loop"""
        log("[ENGINE] Execution started")
        
        try:
            while self._current_index < len(self._actions):
                # Check stop
                if self._stop_event.is_set():
                    break
                
                # Wait if paused
                self._pause_event.wait()
                if self._stop_event.is_set():
                    break
                
                # Get current action
                action = self._actions[self._current_index]
                
                # Notify start
                if self._on_action_start:
                    self._on_action_start(self._current_index, action)
                
                # Execute action
                start_time = time.time()
                result = self._execute_action(action)
                result.duration_ms = int((time.time() - start_time) * 1000)
                
                # Notify complete
                if self._on_action_complete:
                    self._on_action_complete(self._current_index, result)
                
                # Handle flow control
                if self._flow_controller:
                    next_index = self._flow_controller.get_next_index(self._current_index)
                    
                    # Check for flow control action
                    if is_flow_control_action(action.get("type", "")):
                        jump_to = self._flow_controller.process_flow_action(
                            action, self._current_index
                        )
                        if jump_to is not None:
                            self._current_index = jump_to
                            continue
                    
                    self._current_index = next_index
                else:
                    self._current_index += 1
                
                # Check if we've gone past the end (for embedded macros)
                if (self._current_index >= len(self._actions) and 
                    self._flow_controller and 
                    self._flow_controller.is_in_embedded_macro()):
                    return_index = self._flow_controller.return_from_embed()
                    if return_index is not None:
                        self._actions = self._flow_controller.actions
                        self._current_index = return_index
            
            success = not self._stop_event.is_set()
            log(f"[ENGINE] Execution {'completed' if success else 'stopped'}")
            
            if self._on_execution_complete:
                self._on_execution_complete(success)
                
        except Exception as e:
            log(f"[ENGINE] Execution error: {e}")
            if self._on_execution_complete:
                self._on_execution_complete(False)
        finally:
            self._is_running = False
    
    def _execute_action(self, action: Dict[str, Any]) -> ActionResult:
        """Execute a single action"""
        action_type = action.get("type", "")
        params = action.get("params", {})
        
        if self.debug_mode:
            log(f"[ENGINE] Executing: {action_type} {params}")
        
        try:
            # Route to appropriate handler
            if action_type in ("MouseClick", "Click"):
                return self._exec_mouse_click(params)
            
            elif action_type in ("MouseMove", "Move"):
                return self._exec_mouse_move(params)
            
            elif action_type == "MouseDrag":
                return self._exec_mouse_drag(params)
            
            elif action_type in ("KeyPress", "Key"):
                return self._exec_key_press(params)
            
            elif action_type == "KeyType":
                return self._exec_key_type(params)
            
            elif action_type == "Delay":
                return self._exec_delay(params)
            
            elif action_type == "WaitTime":
                return self._exec_wait_time(params)
            
            elif action_type == "WaitPixelColor":
                return self._exec_wait_pixel_color(params)
            
            elif action_type == "WaitScreenChange":
                return self._exec_wait_screen_change(params)
            
            elif action_type == "WaitHotkey":
                return self._exec_wait_hotkey(params)
            
            elif action_type == "WaitFile":
                return self._exec_wait_file(params)
            
            elif action_type == "FindImage":
                return self._exec_find_image(params)
            
            elif action_type == "CaptureImage":
                return self._exec_capture_image(params)
            
            elif action_type in ("Label", "Goto", "Repeat", "EmbedMacro"):
                # Flow control handled separately
                return ActionResult(status=ActionStatus.SUCCESS)
            
            elif action_type == "SetVariable":
                return self._exec_set_variable(params)
            
            elif action_type == "Comment":
                return ActionResult(status=ActionStatus.SUCCESS, message="Comment")
            
            else:
                log(f"[ENGINE] Unknown action type: {action_type}")
                return ActionResult(
                    status=ActionStatus.SKIPPED,
                    message=f"Unknown action: {action_type}"
                )
                
        except Exception as e:
            log(f"[ENGINE] Action error: {e}")
            return ActionResult(
                status=ActionStatus.FAILED,
                message=str(e)
            )
    
    def _exec_mouse_click(self, params: dict) -> ActionResult:
        """Execute mouse click"""
        x = params.get("x", 0)
        y = params.get("y", 0)
        button = params.get("button", "left")
        clicks = params.get("clicks", 1)
        
        # Convert client to screen coords
        screen_x, screen_y = x, y
        if self.target_hwnd:
            pt = wintypes.POINT(x, y)
            user32.ClientToScreen(self.target_hwnd, ctypes.byref(pt))
            screen_x, screen_y = pt.x, pt.y
        
        # Move cursor
        user32.SetCursorPos(screen_x, screen_y)
        time.sleep(0.01)
        
        # Click
        if button == "left":
            down_flag, up_flag = 0x0002, 0x0004
        elif button == "right":
            down_flag, up_flag = 0x0008, 0x0010
        elif button == "middle":
            down_flag, up_flag = 0x0020, 0x0040
        else:
            down_flag, up_flag = 0x0002, 0x0004
        
        for _ in range(clicks):
            user32.mouse_event(down_flag, 0, 0, 0, 0)
            time.sleep(0.01)
            user32.mouse_event(up_flag, 0, 0, 0, 0)
            time.sleep(0.01)
        
        return ActionResult(
            status=ActionStatus.SUCCESS,
            message=f"Click at ({x}, {y})"
        )
    
    def _exec_mouse_move(self, params: dict) -> ActionResult:
        """Execute mouse move"""
        x = params.get("x", 0)
        y = params.get("y", 0)
        
        # Convert client to screen coords
        screen_x, screen_y = x, y
        if self.target_hwnd:
            pt = wintypes.POINT(x, y)
            user32.ClientToScreen(self.target_hwnd, ctypes.byref(pt))
            screen_x, screen_y = pt.x, pt.y
        
        user32.SetCursorPos(screen_x, screen_y)
        
        return ActionResult(
            status=ActionStatus.SUCCESS,
            message=f"Move to ({x}, {y})"
        )
    
    def _exec_mouse_drag(self, params: dict) -> ActionResult:
        """Execute mouse drag"""
        x1 = params.get("x1", params.get("start_x", 0))
        y1 = params.get("y1", params.get("start_y", 0))
        x2 = params.get("x2", params.get("end_x", 0))
        y2 = params.get("y2", params.get("end_y", 0))
        button = params.get("button", "left")
        
        # Convert to screen coords
        if self.target_hwnd:
            pt1 = wintypes.POINT(x1, y1)
            pt2 = wintypes.POINT(x2, y2)
            user32.ClientToScreen(self.target_hwnd, ctypes.byref(pt1))
            user32.ClientToScreen(self.target_hwnd, ctypes.byref(pt2))
            x1, y1 = pt1.x, pt1.y
            x2, y2 = pt2.x, pt2.y
        
        # Button flags
        if button == "left":
            down_flag, up_flag = 0x0002, 0x0004
        elif button == "right":
            down_flag, up_flag = 0x0008, 0x0010
        else:
            down_flag, up_flag = 0x0002, 0x0004
        
        # Move to start, press, drag, release
        user32.SetCursorPos(x1, y1)
        time.sleep(0.01)
        user32.mouse_event(down_flag, 0, 0, 0, 0)
        time.sleep(0.05)
        user32.SetCursorPos(x2, y2)
        time.sleep(0.05)
        user32.mouse_event(up_flag, 0, 0, 0, 0)
        
        return ActionResult(
            status=ActionStatus.SUCCESS,
            message=f"Drag ({x1}, {y1}) -> ({x2}, {y2})"
        )
    
    def _exec_key_press(self, params: dict) -> ActionResult:
        """Execute key press"""
        key = params.get("key", "")
        modifiers = params.get("modifiers", [])
        
        if not key:
            return ActionResult(status=ActionStatus.FAILED, message="No key specified")
        
        # Virtual key codes
        VK_MAP = {
            'a': 0x41, 'b': 0x42, 'c': 0x43, 'd': 0x44, 'e': 0x45,
            'f': 0x46, 'g': 0x47, 'h': 0x48, 'i': 0x49, 'j': 0x4A,
            'k': 0x4B, 'l': 0x4C, 'm': 0x4D, 'n': 0x4E, 'o': 0x4F,
            'p': 0x50, 'q': 0x51, 'r': 0x52, 's': 0x53, 't': 0x54,
            'u': 0x55, 'v': 0x56, 'w': 0x57, 'x': 0x58, 'y': 0x59,
            'z': 0x5A,
            '0': 0x30, '1': 0x31, '2': 0x32, '3': 0x33, '4': 0x34,
            '5': 0x35, '6': 0x36, '7': 0x37, '8': 0x38, '9': 0x39,
            'space': 0x20, 'enter': 0x0D, 'return': 0x0D, 'tab': 0x09,
            'escape': 0x1B, 'esc': 0x1B, 'backspace': 0x08, 'delete': 0x2E,
            'up': 0x26, 'down': 0x28, 'left': 0x25, 'right': 0x27,
            'home': 0x24, 'end': 0x23, 'pageup': 0x21, 'pagedown': 0x22,
            'f1': 0x70, 'f2': 0x71, 'f3': 0x72, 'f4': 0x73, 'f5': 0x74,
            'f6': 0x75, 'f7': 0x76, 'f8': 0x77, 'f9': 0x78, 'f10': 0x79,
            'f11': 0x7A, 'f12': 0x7B,
            'ctrl': 0x11, 'control': 0x11, 'alt': 0x12, 'shift': 0x10,
            'win': 0x5B, 'windows': 0x5B
        }
        
        def press_key(vk):
            user32.keybd_event(vk, 0, 0, 0)
        
        def release_key(vk):
            user32.keybd_event(vk, 0, 0x0002, 0)
        
        # Press modifiers
        mod_vks = []
        for mod in modifiers:
            mod_lower = mod.lower()
            if mod_lower in VK_MAP:
                vk = VK_MAP[mod_lower]
                mod_vks.append(vk)
                press_key(vk)
        
        # Press main key
        key_lower = key.lower()
        if key_lower in VK_MAP:
            vk = VK_MAP[key_lower]
            press_key(vk)
            time.sleep(0.01)
            release_key(vk)
        
        # Release modifiers (reverse order)
        for vk in reversed(mod_vks):
            release_key(vk)
        
        return ActionResult(
            status=ActionStatus.SUCCESS,
            message=f"Key: {'+'.join(modifiers + [key]) if modifiers else key}"
        )
    
    def _exec_key_type(self, params: dict) -> ActionResult:
        """Execute typing text"""
        text = params.get("text", "")
        
        if not text:
            return ActionResult(status=ActionStatus.FAILED, message="No text specified")
        
        # Use SendInput for Unicode text
        for char in text:
            # Key down
            user32.keybd_event(0, ord(char), 0x0004, 0)  # KEYEVENTF_UNICODE
            time.sleep(0.01)
            # Key up
            user32.keybd_event(0, ord(char), 0x0004 | 0x0002, 0)
            time.sleep(0.01)
        
        return ActionResult(
            status=ActionStatus.SUCCESS,
            message=f"Type: {text[:20]}{'...' if len(text) > 20 else ''}"
        )
    
    def _exec_delay(self, params: dict) -> ActionResult:
        """Execute delay"""
        ms = params.get("ms", params.get("delay_ms", 1000))
        
        wait = WaitTime(delay_ms=ms)
        result = wait.wait(self._stop_event)
        
        return ActionResult(
            status=ActionStatus.SUCCESS if result.success else ActionStatus.STOPPED,
            message=f"Delay {ms}ms"
        )
    
    def _exec_wait_time(self, params: dict) -> ActionResult:
        """Execute WaitTime action"""
        wait = WaitTime(
            delay_ms=params.get("delay_ms", 1000),
            variance_ms=params.get("variance_ms", 0)
        )
        result = wait.wait(self._stop_event)
        
        status = ActionStatus.SUCCESS if result.success else ActionStatus.STOPPED
        return ActionResult(status=status, message=result.message)
    
    def _exec_wait_pixel_color(self, params: dict) -> ActionResult:
        """Execute WaitPixelColor action"""
        rgb = params.get("expected_rgb", (0, 0, 0))
        if isinstance(rgb, str):
            rgb = rgb.lstrip('#')
            rgb = tuple(int(rgb[i:i+2], 16) for i in (0, 2, 4))
        
        wait = WaitPixelColor(
            x=params.get("x", 0),
            y=params.get("y", 0),
            expected_rgb=rgb,
            tolerance=params.get("tolerance", 0),
            timeout_ms=params.get("timeout_ms", 30000),
            target_hwnd=params.get("target_hwnd", self.target_hwnd)
        )
        result = wait.wait(self._stop_event)
        
        if result.timeout:
            status = ActionStatus.TIMEOUT
        elif result.success:
            status = ActionStatus.SUCCESS
        else:
            status = ActionStatus.STOPPED
        
        return ActionResult(status=status, message=result.message)
    
    def _exec_wait_screen_change(self, params: dict) -> ActionResult:
        """Execute WaitScreenChange action"""
        region = params.get("region", (0, 0, 100, 100))
        if isinstance(region, list):
            region = tuple(region)
        
        wait = WaitScreenChange(
            region=region,
            threshold=params.get("threshold", 0.05),
            timeout_ms=params.get("timeout_ms", 30000),
            target_hwnd=params.get("target_hwnd", self.target_hwnd)
        )
        result = wait.wait(self._stop_event)
        
        if result.timeout:
            status = ActionStatus.TIMEOUT
        elif result.success:
            status = ActionStatus.SUCCESS
        else:
            status = ActionStatus.STOPPED
        
        return ActionResult(status=status, message=result.message)
    
    def _exec_wait_hotkey(self, params: dict) -> ActionResult:
        """Execute WaitHotkey action"""
        wait = WaitHotkey(
            key_combo=params.get("key_combo", "F5"),
            timeout_ms=params.get("timeout_ms", 0)
        )
        result = wait.wait(self._stop_event)
        
        if result.timeout:
            status = ActionStatus.TIMEOUT
        elif result.success:
            status = ActionStatus.SUCCESS
        else:
            status = ActionStatus.STOPPED
        
        return ActionResult(status=status, message=result.message)
    
    def _exec_wait_file(self, params: dict) -> ActionResult:
        """Execute WaitFile action"""
        wait = WaitFile(
            path=params.get("path", ""),
            condition=params.get("condition", "exists"),
            timeout_ms=params.get("timeout_ms", 30000)
        )
        result = wait.wait(self._stop_event)
        
        if result.timeout:
            status = ActionStatus.TIMEOUT
        elif result.success:
            status = ActionStatus.SUCCESS
        else:
            status = ActionStatus.STOPPED
        
        return ActionResult(status=status, message=result.message)
    
    def _exec_find_image(self, params: dict) -> ActionResult:
        """Execute FindImage action"""
        if not image_actions_available():
            return ActionResult(
                status=ActionStatus.FAILED,
                message="OpenCV not available"
            )
        
        region = params.get("region")
        if isinstance(region, list):
            region = tuple(region)
        
        finder = FindImage(
            template_path=params.get("template_path", ""),
            region=region,
            threshold=params.get("threshold", 0.8),
            timeout_ms=params.get("timeout_ms", 5000),
            target_hwnd=params.get("target_hwnd", self.target_hwnd)
        )
        
        match = finder.find(self._stop_event)
        
        if match.found:
            # Store result in variables for subsequent actions
            self._variables["last_image_x"] = match.center_x
            self._variables["last_image_y"] = match.center_y
            self._variables["last_image_found"] = True
            
            return ActionResult(
                status=ActionStatus.SUCCESS,
                message=f"Found at ({match.center_x}, {match.center_y})",
                data=match
            )
        else:
            self._variables["last_image_found"] = False
            return ActionResult(
                status=ActionStatus.FAILED,
                message="Image not found"
            )
    
    def _exec_capture_image(self, params: dict) -> ActionResult:
        """Execute CaptureImage action"""
        if not image_actions_available():
            return ActionResult(
                status=ActionStatus.FAILED,
                message="OpenCV not available"
            )
        
        region = params.get("region")
        if isinstance(region, list):
            region = tuple(region)
        
        capturer = CaptureImage(
            region=region,
            save_path=params.get("save_path", ""),
            format=params.get("format", "png"),
            target_hwnd=params.get("target_hwnd", self.target_hwnd)
        )
        
        result = capturer.capture()
        
        if result.success:
            return ActionResult(
                status=ActionStatus.SUCCESS,
                message=f"Saved to {result.path}",
                data=result
            )
        else:
            return ActionResult(
                status=ActionStatus.FAILED,
                message=result.message
            )
    
    def _exec_set_variable(self, params: dict) -> ActionResult:
        """Execute SetVariable action"""
        name = params.get("name", "")
        value = params.get("value")
        
        if not name:
            return ActionResult(status=ActionStatus.FAILED, message="No variable name")
        
        self._variables[name] = value
        
        return ActionResult(
            status=ActionStatus.SUCCESS,
            message=f"Set {name} = {value}"
        )


def create_action_engine(target_hwnd: int = 0, debug_mode: bool = False) -> ActionEngine:
    """
    Factory function to create ActionEngine
    
    Args:
        target_hwnd: Target window handle
        debug_mode: Enable debug logging
        
    Returns:
        ActionEngine instance
    """
    return ActionEngine(target_hwnd=target_hwnd, debug_mode=debug_mode)
