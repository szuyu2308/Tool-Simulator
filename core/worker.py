from core.tech import win32gui, logging, mss
from core.adb_manager import ADBManager
from core.models import Script, Command, CommandType, OnFailAction
from core.emulator import EmulatorInstance, ClientRect
from core.capture import get_capture_manager, CaptureManager, Frame
from core.input import InputManager, ButtonType as InputButtonType, HotKeyOrder
from utils.logger import log
import time
import threading
import numpy as np
from typing import Dict, Any, Optional

# Global ADB instance (reuse across workers to avoid redundant instance creation)
_global_adb_manager = None

def get_adb_manager():
    """Get or create global ADB manager instance (singleton pattern)"""
    global _global_adb_manager
    if _global_adb_manager is None:
        _global_adb_manager = ADBManager()
    return _global_adb_manager

class WorkerStatus:
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    STOPPED = "STOPPED"
    ERROR = "ERROR"
    NOT_READY = "NOT_READY"
    BUSY = "BUSY"  # Legacy compatibility

    def __init__(self, worker_id, hwnd, client_rect, res_width=None, res_height=None, adb_device=None, adb_manager=None, logger=None):
        """
        Initialize worker with resolution detection
        
        Args:
            worker_id (int): Unique worker identifier
            hwnd (int): Windows handle
            client_rect (tuple): (x, y, w, h) of client area on screen
            res_width (int, optional): Explicit resolution width. If None, auto-detect via ADB
            res_height (int, optional): Explicit resolution height. If None, auto-detect via ADB
            adb_device (str, optional): ADB device ID (e.g., "emulator-5554", "127.0.0.1:21503")
            adb_manager (ADBManager, optional): Reuse existing ADB manager. If None, use global singleton
            logger (logging.Logger, optional): Custom logger
        """
        self.id = worker_id
        self.hwnd = hwnd

        # Client area thật (screen coord)
        self.client_x, self.client_y, self.client_w, self.client_h = client_rect
        
        # Create ClientRect object for coordinate conversion
        self.client_rect = ClientRect(
            x=self.client_x,
            y=self.client_y,
            w=self.client_w,
            h=self.client_h
        )

        # ADB device identifier (e.g., "emulator-5554" hoặc "127.0.0.1:21503")
        self.adb_device = adb_device

        # Resolution logic (LD config)
        # Nếu không truyền res_width/res_height, sẽ auto-detect qua ADB
        if res_width is None or res_height is None:
            adb = adb_manager or get_adb_manager()
            detected = adb.query_resolution(adb_device) if adb_device else None
            if detected:
                res_width, res_height = detected
                log(f"[WORKER] {self.id}: Auto-detected resolution {res_width}x{res_height} from ADB device {adb_device}")
            else:
                # Fallback to client area dimensions
                res_width = self.client_w
                res_height = self.client_h
                log(f"[WORKER] {self.id}: Using fallback resolution {res_width}x{res_height} (client area)")
        
        self.res_width = res_width
        self.res_height = res_height

        # Scale local → screen
        # scale_x = window_width / game_resolution_width
        # This allows mapping from game coords to screen coords
        self.scale_x = self.client_w / self.res_width
        self.scale_y = self.client_h / self.res_height
        
        log(f"[WORKER] {self.id}: Scale factors = {self.scale_x:.3f}x, {self.scale_y:.3f}y")

        # Runtime state
        self.status = WorkerStatus.IDLE
        self.current_command = None
        self.command_config = None

        # Logger
        self.logger = logger or logging.getLogger(f"Worker-{self.id}")

        # Screen capturer (legacy)
        self._sct = mss.mss()
        
        # New providers
        self._capture_manager: CaptureManager = get_capture_manager()
        self._input_manager: Optional[InputManager] = None
        self._init_providers()
    
    def _init_providers(self):
        """Initialize input/capture providers"""
        adb = get_adb_manager()
        self._input_manager = InputManager(
            hwnd=self.hwnd,
            client_rect=self.client_rect,
            adb_manager=adb,
            adb_serial=self.adb_device
        )
        log(f"[WORKER] {self.id}: Providers initialized (Capture: {self._capture_manager.active_provider_name})")

class Worker(WorkerStatus):
    """Worker class that extends WorkerStatus with action methods and script execution"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Script execution state
        self.variables: Dict[str, Any] = {}  # Runtime variables (copy from global + local)
        self.iteration_count: int = 0        # Current iteration count
        self.paused: bool = False            # Pause flag
        self.stopped: bool = False           # Stop flag
        self.current_script: Optional[Script] = None  # Currently running script
        
        # Execution thread
        self._execution_thread: Optional[threading.Thread] = None
        
    def set_command(self, command_name, command_config):
        if self.status != WorkerStatus.IDLE:
            self.logger.warning(
            f"[{self.id}] Worker đang BUSY, không nhận command {command_name}"
            )
            return False

        self.current_command = command_name
        self.command_config = command_config
        self.status = WorkerStatus.BUSY
        self.logger.info(f"[WORKER] Nhận lệnh: {command_name}")
        return True

    def focus(self):
        try:
            win32gui.SetForegroundWindow(self.hwnd)
        except Exception as e:
            self.logger.error(f"[{self.id}] Focus window failed: {e}")

    def capture(self):
        """
        Capture đúng vùng LDPlayer (client area)
        """
        monitor = {
            "left": self.client_x,
            "top": self.client_y,
            "width": self.client_w,
            "height": self.client_h,
        }
        return self._sct.grab(monitor)


    def is_inside(self, x, y):
        return 0 <= x <= self.res_width and 0 <= y <= self.res_height

    def local_to_screen(self, x, y):
        if not self.is_inside(x, y):
            raise ValueError(
                f"[{self.id}] Local coord out of bound: ({x},{y})"
            )

        screen_x = int(self.client_x + x * self.scale_x)
        screen_y = int(self.client_y + y * self.scale_y)
        return screen_x, screen_y
    
    def is_ready(self) -> bool:
        try:
            if not win32gui.IsWindow(self.hwnd):
                return False

            if win32gui.IsIconic(self.hwnd):
                return False

            frame = self.capture()
            if frame is None:
                return False

            return True
        except Exception as e:
            log(f"[WORKER] Worker {self.id} not ready: {e}")
            return False

    def finish_command(self):
        self.current_command = None
        self.command_config = None
        self.status = WorkerStatus.IDLE

    def validate_resolution(self) -> tuple:
        """
        Validate resolution hiện tại của emulator có khớp với expected resolution không
        Returns: (is_valid: bool, current_resolution: tuple, expected_resolution: tuple, message: str)
        """
        if not self.adb_device:
            return (True, None, (self.res_width, self.res_height), "No ADB device, skipping validation")
        
        adb = ADBManager()
        current = adb.query_resolution(self.adb_device)
        expected = (self.res_width, self.res_height)
        
        if not current:
            return (False, None, expected, f"Failed to query resolution from device {self.adb_device}")
        
        is_match = current == expected
        
        if is_match:
            msg = f"✓ Resolution matched: {current[0]}x{current[1]}"
            return (True, current, expected, msg)
        else:
            msg = f"✗ Resolution mismatch: Device={current[0]}x{current[1]}, Expected={expected[0]}x{expected[1]}"
            return (False, current, expected, msg)
    
    def lock_resolution(self, target_width, target_height) -> bool:
        """
        Lock emulator resolution về target value (requires ADB + LDPlayer settings)
        Note: Thực tế LDPlayer lock resolution là qua config hoặc ADB shell setprop
        Returns: True nếu thành công
        """
        if not self.adb_device:
            log(f"[WORKER {self.id}] No ADB device, cannot lock resolution")
            return False
        
        try:
            adb = ADBManager()
            
            # Cách 1: Thử dùng ADB shell wm size reset / wm size WxH
            # (nhưng thường yêu cầu root)
            log(f"[WORKER {self.id}] Attempting to lock resolution to {target_width}x{target_height}")
            
            # Cách 2: Query hiện tại và cảnh báo nếu khác
            current = adb.query_resolution(self.adb_device)
            if current and current != (target_width, target_height):
                log(f"[WORKER {self.id}] WARNING: Cannot lock resolution via ADB (no root)")
                log(f"[WORKER {self.id}] Current: {current[0]}x{current[1]}, Target: {target_width}x{target_height}")
                return False
            
            log(f"[WORKER {self.id}] Resolution locked (or already matches): {target_width}x{target_height}")
            return True
        except Exception as e:
            log(f"[WORKER {self.id}] Lock resolution error: {e}")
            return False

    # ==================== SCRIPT EXECUTION ====================
    def start(self, script: Script):
        """
        Execute script following the architecture specification
        
        Execution Flow:
        1. Copy Script.VariablesGlobal → Worker.Variables
        2. Build LabelMap from all Command names
        3. Execute commands sequentially with iteration limit
        4. Handle logic types (Wait, Condition, Repeat, Goto)
        5. Handle action types (Click, KeyPress, Text, etc.)
        6. Apply OnFail handling on failure
        7. Update Variables from VariablesOut
        8. Support Pause/Resume/Stop
        """
        self.current_script = script
        self.stopped = False
        self.paused = False
        self.iteration_count = 0
        
        # Step 1: Copy global variables
        self.variables = script.variables_global.copy()
        log(f"[WORKER {self.id}] Starting script with {len(script.sequence)} commands")
        
        # Step 2: Build label map (already done in Script.__init__)
        # script.label_map is ready
        
        # Step 3: Start execution from first command
        if not script.sequence:
            log(f"[WORKER {self.id}] Script is empty")
            return
        
        current_id = script.sequence[0].id
        
        # Step 4: Main execution loop
        while current_id and self.iteration_count < script.max_iterations and not self.stopped:
            # Handle pause
            while self.paused and not self.stopped:
                time.sleep(0.1)
            
            if self.stopped:
                break
            
            self.iteration_count += 1
            
            # Get command by ID
            cmd = script.get_command_by_id(current_id)
            if not cmd:
                log(f"[WORKER {self.id}] Command ID {current_id} not found, stopping")
                break
            
            # Skip if disabled
            if not cmd.enabled:
                log(f"[WORKER {self.id}] Command '{cmd.name}' disabled, skipping")
                current_id = self._get_next_command_id(script, current_id)
                continue
            
            log(f"[WORKER {self.id}] [{self.iteration_count}] Executing: {cmd.name} ({cmd.type.value})")
            
            # Execute command with error handling
            try:
                success, next_id = self._execute_command(cmd, script)
                
                if success:
                    # Normal flow: use returned next_id or sequential next
                    if next_id:
                        current_id = next_id
                    else:
                        current_id = self._get_next_command_id(script, current_id)
                else:
                    # Command failed, apply OnFail action
                    current_id = self._handle_on_fail(cmd, script, current_id)
                    
            except Exception as e:
                log(f"[WORKER {self.id}] Exception in command '{cmd.name}': {e}")
                self.logger.error(f"Command exception: {e}", exc_info=True)
                
                # Apply OnFail or stop
                current_id = self._handle_on_fail(cmd, script, current_id)
        
        # Execution finished
        if self.iteration_count >= script.max_iterations:
            log(f"[WORKER {self.id}] Script stopped: Max iterations reached ({script.max_iterations})")
        elif self.stopped:
            log(f"[WORKER {self.id}] Script stopped by user")
        else:
            log(f"[WORKER {self.id}] Script completed successfully")
        
        self.current_script = None

    def pause(self):
        """Pause script execution"""
        self.paused = True
        log(f"[WORKER {self.id}] Script paused")

    def resume(self):
        """Resume script execution"""
        self.paused = False
        log(f"[WORKER {self.id}] Script resumed")

    def stop(self):
        """Stop script execution"""
        self.stopped = True
        log(f"[WORKER {self.id}] Script stop requested")

    def _execute_command(self, cmd: Command, script: Script) -> tuple:
        """
        Execute a single command
        Returns: (success: bool, next_command_id: Optional[str])
        """
        # Logic types handle control flow
        if cmd.type == CommandType.WAIT:
            return self._execute_wait(cmd)
        elif cmd.type == CommandType.CONDITION:
            return self._execute_condition(cmd, script)
        elif cmd.type == CommandType.REPEAT:
            return self._execute_repeat(cmd, script)
        elif cmd.type == CommandType.GOTO:
            return self._execute_goto(cmd, script)
        
        # Action types perform actions
        elif cmd.type == CommandType.CLICK:
            return self._execute_click(cmd), None
        elif cmd.type == CommandType.KEY_PRESS:
            return self._execute_keypress(cmd), None
        elif cmd.type == CommandType.TEXT:
            return self._execute_text(cmd), None
        elif cmd.type == CommandType.CROP_IMAGE:
            return self._execute_crop_image(cmd), None
        elif cmd.type == CommandType.HOT_KEY:
            return self._execute_hotkey(cmd), None
        else:
            log(f"[WORKER {self.id}] Unknown command type: {cmd.type}")
            return False, None

    def _execute_wait(self, cmd) -> tuple:
        """Execute Wait command with polling using CaptureManager"""
        from core.models import WaitCommand, WaitType
        if not isinstance(cmd, WaitCommand):
            return False, None
        
        log(f"[WORKER {self.id}] Wait: {cmd.wait_type.value} for {cmd.timeout_sec}s")
        
        start_time = time.time()
        timeout = cmd.timeout_sec
        
        if cmd.wait_type == WaitType.TIMEOUT:
            # Simple timeout
            time.sleep(timeout)
            return True, None
        
        elif cmd.wait_type == WaitType.PIXEL_COLOR:
            # Poll pixel color with WAIT_TTL (0.1s refresh)
            target_color = cmd.pixel_color
            target_x, target_y = cmd.pixel_x, cmd.pixel_y
            tolerance = cmd.pixel_tolerance or 10
            
            if not target_color or target_x is None or target_y is None:
                log(f"[WORKER {self.id}] Wait: PixelColor missing parameters")
                return False, None
            
            while time.time() - start_time < timeout:
                # Get fresh frame with force_refresh for Wait polling
                frame = self._capture_manager.get_frame(
                    hwnd=self.hwnd,
                    x=self.client_rect.x,
                    y=self.client_rect.y,
                    w=self.client_rect.w,
                    h=self.client_rect.h,
                    force_refresh=True  # Use WAIT_TTL (0.1s)
                )
                
                if frame and frame.pixels is not None:
                    # Check pixel at target location
                    if 0 <= target_y < frame.height and 0 <= target_x < frame.width:
                        pixel = frame.pixels[target_y, target_x]
                        # pixel is BGR
                        pixel_b, pixel_g, pixel_r = pixel[0], pixel[1], pixel[2]
                        target_r, target_g, target_b = target_color[0], target_color[1], target_color[2]
                        
                        diff = abs(pixel_r - target_r) + abs(pixel_g - target_g) + abs(pixel_b - target_b)
                        
                        if diff <= tolerance * 3:
                            log(f"[WORKER {self.id}] Wait: PixelColor matched at ({target_x},{target_y})")
                            return True, None
                
                time.sleep(0.1)  # Poll interval
                
                if self.stopped:
                    return False, None
            
            log(f"[WORKER {self.id}] Wait: PixelColor timeout")
            return False, None
        
        elif cmd.wait_type == WaitType.SCREEN_CHANGE:
            # Poll screen change detection
            prev_frame = None
            change_threshold = cmd.screen_threshold or 0.05  # 5% change
            
            while time.time() - start_time < timeout:
                # Get fresh frame
                frame = self._capture_manager.get_frame(
                    hwnd=self.hwnd,
                    x=self.client_rect.x,
                    y=self.client_rect.y,
                    w=self.client_rect.w,
                    h=self.client_rect.h,
                    force_refresh=True
                )
                
                if frame and frame.pixels is not None:
                    if prev_frame is not None:
                        # Calculate frame difference
                        diff = np.abs(frame.pixels.astype(float) - prev_frame.astype(float))
                        change_ratio = np.mean(diff) / 255.0
                        
                        if change_ratio >= change_threshold:
                            log(f"[WORKER {self.id}] Wait: ScreenChange detected (ratio={change_ratio:.3f})")
                            return True, None
                    
                    prev_frame = frame.pixels.copy()
                
                time.sleep(0.1)
                
                if self.stopped:
                    return False, None
            
            log(f"[WORKER {self.id}] Wait: ScreenChange timeout")
            return False, None
        
        return True, None

    def _execute_condition(self, cmd, script: Script) -> tuple:
        """Execute Condition command with expression evaluation and nested commands"""
        from core.models import ConditionCommand
        if not isinstance(cmd, ConditionCommand):
            return False, None
        
        # Expression evaluation with restricted globals for safety
        try:
            result = eval(cmd.expr, {"__builtins__": {}}, {"variables": self.variables})
            log(f"[WORKER {self.id}] Condition '{cmd.expr}' = {result}")
            
            if result:
                # True branch
                # Priority: nested_then > then_label
                if cmd.nested_then:
                    self._execute_nested_commands(cmd.nested_then, script, self.variables)
                elif cmd.then_label:
                    next_cmd = script.get_command_by_label(cmd.then_label)
                    if next_cmd:
                        return True, next_cmd.id
            else:
                # False branch
                # Priority: nested_else > else_label
                if cmd.nested_else:
                    self._execute_nested_commands(cmd.nested_else, script, self.variables)
                elif cmd.else_label:
                    next_cmd = script.get_command_by_label(cmd.else_label)
                    if next_cmd:
                        return True, next_cmd.id
            
            return True, None
            
        except Exception as e:
            log(f"[WORKER {self.id}] Condition eval error: {e}")
            return False, None

    def _execute_repeat(self, cmd, script: Script) -> tuple:
        """Execute Repeat command with nested commands and isolated variables"""
        from core.models import RepeatCommand
        if not isinstance(cmd, RepeatCommand):
            return False, None
        
        log(f"[WORKER {self.id}] Repeat: count={cmd.count}, until={cmd.until_condition_expr}")
        
        # Max count: 0 = infinite (limited by MaxIterations)
        max_count = cmd.count if cmd.count > 0 else script.max_iterations
        iteration = 0
        
        while iteration < max_count and self.iteration_count < script.max_iterations and not self.stopped:
            iteration += 1
            
            # Handle pause
            while self.paused and not self.stopped:
                time.sleep(0.1)
            
            if self.stopped:
                return False, None
            
            # Isolate variables for this iteration (copy current state)
            loop_variables = self.variables.copy()
            loop_variables["_loop_index"] = iteration
            
            log(f"[WORKER {self.id}] Repeat iteration {iteration}/{max_count}")
            
            # Execute inner commands
            inner_success = self._execute_nested_commands(cmd.inner_commands, script, loop_variables)
            
            # Merge loop variables back (exclude _loop_index)
            for key, value in loop_variables.items():
                if not key.startswith("_loop_"):
                    self.variables[key] = value
            
            # Check until condition AFTER each iteration
            if cmd.until_condition_expr:
                try:
                    result = eval(cmd.until_condition_expr, {"__builtins__": {}}, {"variables": self.variables})
                    if result:
                        log(f"[WORKER {self.id}] Repeat: Until condition met after {iteration} iterations")
                        break
                except Exception as e:
                    log(f"[WORKER {self.id}] Repeat: Until condition eval error: {e}")
            
            self.iteration_count += 1
        
        return True, None
    
    def _execute_nested_commands(self, commands: list, script: Script, local_vars: dict) -> bool:
        """Execute a list of nested commands with local variable scope"""
        if not commands:
            return True
        
        # Temporarily swap variables
        original_vars = self.variables
        self.variables = local_vars
        
        try:
            for cmd in commands:
                if self.stopped:
                    return False
                
                # Handle pause
                while self.paused and not self.stopped:
                    time.sleep(0.1)
                
                if not cmd.enabled:
                    continue
                
                log(f"[WORKER {self.id}] (nested) Executing: {cmd.name} ({cmd.type.value})")
                
                try:
                    success, next_id = self._execute_command(cmd, script)
                    
                    if not success:
                        # Handle OnFail for nested commands
                        if cmd.on_fail == OnFailAction.STOP:
                            log(f"[WORKER {self.id}] (nested) OnFail=Stop, aborting")
                            return False
                        elif cmd.on_fail == OnFailAction.GOTO_LABEL:
                            # GotoLabel in nested context breaks out
                            log(f"[WORKER {self.id}] (nested) OnFail=GotoLabel, breaking")
                            return False
                        # Skip continues to next command
                
                except Exception as e:
                    log(f"[WORKER {self.id}] (nested) Error in '{cmd.name}': {e}")
                    if cmd.on_fail == OnFailAction.STOP:
                        return False
            
            return True
        finally:
            # Restore original variables (but keep modifications in local_vars)
            self.variables = original_vars

    def _execute_goto(self, cmd, script: Script) -> tuple:
        """Execute Goto command with optional condition"""
        from core.models import GotoCommand
        if not isinstance(cmd, GotoCommand):
            return False, None
        
        # Check condition if exists
        if cmd.condition_expr:
            try:
                result = eval(cmd.condition_expr, {"__builtins__": {}}, {"variables": self.variables})
                if not result:
                    log(f"[WORKER {self.id}] Goto: Condition not met, skipping")
                    return True, None
            except Exception as e:
                log(f"[WORKER {self.id}] Goto: Condition eval error: {e}")
                return False, None
        
        # Jump to target label
        target_cmd = script.get_command_by_label(cmd.target_label)
        if not target_cmd:
            log(f"[WORKER {self.id}] Goto: Label '{cmd.target_label}' not found")
            return False, None
        
        log(f"[WORKER {self.id}] Goto: Jumping to '{cmd.target_label}'")
        return True, target_cmd.id

    def _execute_click(self, cmd) -> bool:
        """Execute Click command using InputManager"""
        from core.models import ClickCommand, ButtonType
        if not isinstance(cmd, ClickCommand):
            return False
        
        log(f"[WORKER {self.id}] Click: {cmd.button_type.value} at ({cmd.x}, {cmd.y})")
        
        # Map ButtonType enum to InputButtonType
        button_map = {
            ButtonType.LEFT: InputButtonType.LEFT,
            ButtonType.RIGHT: InputButtonType.RIGHT,
            ButtonType.DOUBLE: InputButtonType.DOUBLE,
            ButtonType.WHEEL_UP: InputButtonType.WHEEL_UP,
            ButtonType.WHEEL_DOWN: InputButtonType.WHEEL_DOWN,
        }
        
        input_button = button_map.get(cmd.button_type, InputButtonType.LEFT)
        
        # Execute click via InputManager (client coordinates)
        success = self._input_manager.click(
            client_x=cmd.x,
            client_y=cmd.y,
            button=input_button,
            humanize_delay_min=cmd.humanize_delay_min_ms,
            humanize_delay_max=cmd.humanize_delay_max_ms,
            wheel_delta=cmd.wheel_delta or 0
        )
        
        return success

    def _execute_keypress(self, cmd) -> bool:
        """Execute KeyPress command using InputManager"""
        from core.models import KeyPressCommand
        if not isinstance(cmd, KeyPressCommand):
            return False
        
        log(f"[WORKER {self.id}] KeyPress: {cmd.key} x{cmd.repeat}")
        
        # Execute keypress via InputManager
        success = self._input_manager.keypress(
            key=cmd.key,
            repeat=cmd.repeat,
            delay_ms=cmd.delay_between_ms
        )
        
        return success

    def _execute_text(self, cmd) -> bool:
        """Execute Text command using InputManager"""
        from core.models import TextCommand, TextMode
        if not isinstance(cmd, TextCommand):
            return False
        
        log(f"[WORKER {self.id}] Text: '{cmd.content[:30]}...' mode={cmd.text_mode.value}")
        
        if cmd.text_mode == TextMode.PASTE:
            success = self._input_manager.paste_text(
                text=cmd.content,
                focus_x=cmd.focus_x,
                focus_y=cmd.focus_y
            )
        else:  # HUMANIZE
            success = self._input_manager.type_text_humanize(
                text=cmd.content,
                cps_min=cmd.speed_min_cps,
                cps_max=cmd.speed_max_cps,
                focus_x=cmd.focus_x,
                focus_y=cmd.focus_y
            )
        
        return success

    def _execute_crop_image(self, cmd) -> bool:
        """Execute CropImage command using CaptureManager"""
        from core.models import CropImageCommand, ScanMode
        if not isinstance(cmd, CropImageCommand):
            return False
        
        log(f"[WORKER {self.id}] CropImage: region=({cmd.x1},{cmd.y1})-({cmd.x2},{cmd.y2}) color={cmd.target_color}")
        
        # Get fresh frame
        frame = self._capture_manager.get_frame(
            hwnd=self.hwnd,
            x=self.client_rect.x,
            y=self.client_rect.y,
            w=self.client_rect.w,
            h=self.client_rect.h
        )
        
        if not frame:
            log(f"[WORKER {self.id}] CropImage: Failed to capture frame")
            self.variables[cmd.output_var] = None
            return False
        
        # Extract region
        region = frame.pixels[cmd.y1:cmd.y2, cmd.x1:cmd.x2]
        
        # Search for target color
        result = self._find_color_in_region(
            region, cmd.target_color, cmd.tolerance, cmd.scan_mode, cmd.x1, cmd.y1
        )
        
        # Store result in variables
        self.variables[cmd.output_var] = result
        
        if result:
            log(f"[WORKER {self.id}] CropImage: Found at ({result['x']}, {result['y']}) conf={result['confidence']:.2f}")
        else:
            log(f"[WORKER {self.id}] CropImage: Color not found")
        
        return result is not None
    
    def _find_color_in_region(self, region: np.ndarray, target_color: tuple, 
                              tolerance: int, scan_mode, offset_x: int, offset_y: int) -> Optional[dict]:
        """Find target color in region"""
        from core.models import ScanMode
        
        if region.size == 0:
            return None
        
        # Target color is RGB, image is BGR
        target_b, target_g, target_r = target_color[2], target_color[1], target_color[0]
        
        # Create color difference mask
        diff_b = np.abs(region[:, :, 0].astype(int) - target_b)
        diff_g = np.abs(region[:, :, 1].astype(int) - target_g)
        diff_r = np.abs(region[:, :, 2].astype(int) - target_r)
        
        total_diff = diff_b + diff_g + diff_r
        
        if scan_mode == ScanMode.EXACT:
            # Find exact match within tolerance
            matches = np.where(total_diff <= tolerance * 3)
            if len(matches[0]) > 0:
                # Return first match
                y, x = matches[0][0], matches[1][0]
                confidence = 1.0 - (total_diff[y, x] / (255 * 3))
                return {
                    "x": offset_x + x,
                    "y": offset_y + y,
                    "confidence": float(confidence)
                }
        
        elif scan_mode == ScanMode.MAX_MATCH:
            # Find best match
            min_idx = np.unravel_index(np.argmin(total_diff), total_diff.shape)
            y, x = min_idx
            min_diff = total_diff[y, x]
            
            if min_diff <= tolerance * 3:
                confidence = 1.0 - (min_diff / (255 * 3))
                return {
                    "x": offset_x + x,
                    "y": offset_y + y,
                    "confidence": float(confidence)
                }
        
        elif scan_mode == ScanMode.GRID:
            # Grid search (sample every 10 pixels)
            step = 10
            best_match = None
            best_diff = float('inf')
            
            for y in range(0, region.shape[0], step):
                for x in range(0, region.shape[1], step):
                    diff = total_diff[y, x]
                    if diff < best_diff:
                        best_diff = diff
                        best_match = (x, y)
            
            if best_match and best_diff <= tolerance * 3:
                confidence = 1.0 - (best_diff / (255 * 3))
                return {
                    "x": offset_x + best_match[0],
                    "y": offset_y + best_match[1],
                    "confidence": float(confidence)
                }
        
        return None

    def _execute_hotkey(self, cmd) -> bool:
        """Execute HotKey command using InputManager"""
        from core.models import HotKeyCommand, HotKeyOrder as ModelHotKeyOrder
        if not isinstance(cmd, HotKeyCommand):
            return False
        
        log(f"[WORKER {self.id}] HotKey: {'+'.join(cmd.keys)} order={cmd.hotkey_order.value}")
        
        # Map HotKeyOrder enum
        order = HotKeyOrder.SIMULTANEOUS if cmd.hotkey_order == ModelHotKeyOrder.SIMULTANEOUS else HotKeyOrder.SEQUENCE
        
        # Execute hotkey via InputManager
        success = self._input_manager.hotkey(cmd.keys, order)
        
        return success

    def _handle_on_fail(self, cmd: Command, script: Script, current_id: str) -> Optional[str]:
        """
        Handle command failure according to OnFail action
        Returns: next command ID or None to stop
        """
        if cmd.on_fail == OnFailAction.SKIP:
            log(f"[WORKER {self.id}] OnFail: Skip to next command")
            return self._get_next_command_id(script, current_id)
        
        elif cmd.on_fail == OnFailAction.STOP:
            log(f"[WORKER {self.id}] OnFail: Stop script")
            self.stopped = True
            return None
        
        elif cmd.on_fail == OnFailAction.GOTO_LABEL:
            if cmd.on_fail_label:
                target_cmd = script.get_command_by_label(cmd.on_fail_label)
                if target_cmd:
                    log(f"[WORKER {self.id}] OnFail: Goto '{cmd.on_fail_label}'")
                    return target_cmd.id
            
            log(f"[WORKER {self.id}] OnFail: Label not found, skipping")
            return self._get_next_command_id(script, current_id)
        
        return None

    def _get_next_command_id(self, script: Script, current_id: str) -> Optional[str]:
        """Get next command ID in sequence"""
        for i, cmd in enumerate(script.sequence):
            if cmd.id == current_id:
                if i + 1 < len(script.sequence):
                    return script.sequence[i + 1].id
                return None
        return None
