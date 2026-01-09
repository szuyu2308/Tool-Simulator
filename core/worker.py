from core.tech import win32gui, logging, mss
from core.adb_manager import ADBManager
from core.models import Script, Command, CommandType, OnFailAction
from utils.logger import log
import time
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
    BUSY = "BUSY"
    ERROR = "ERROR"

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

        # Screen capturer
        self._sct = mss.mss()

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
        """Execute Wait command with polling"""
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
            # Poll pixel color every 100ms
            while time.time() - start_time < timeout:
                # TODO: Implement pixel color check
                # For now, just timeout
                time.sleep(0.1)
                
                if self.stopped:
                    return False, None
            
            log(f"[WORKER {self.id}] Wait: PixelColor timeout")
            return False, None
        
        elif cmd.wait_type == WaitType.SCREEN_CHANGE:
            # Poll screen change every 100ms
            # TODO: Implement screen change detection
            while time.time() - start_time < timeout:
                time.sleep(0.1)
                
                if self.stopped:
                    return False, None
            
            log(f"[WORKER {self.id}] Wait: ScreenChange timeout")
            return False, None
        
        return True, None

    def _execute_condition(self, cmd, script: Script) -> tuple:
        """Execute Condition command with expression evaluation"""
        from core.models import ConditionCommand
        if not isinstance(cmd, ConditionCommand):
            return False, None
        
        # Simple expression evaluation
        # TODO: Implement proper expression parser
        # For now, use eval with restricted globals
        try:
            result = eval(cmd.expr, {"__builtins__": {}}, {"variables": self.variables})
            log(f"[WORKER {self.id}] Condition '{cmd.expr}' = {result}")
            
            if result:
                # True branch
                if cmd.then_label:
                    next_cmd = script.get_command_by_label(cmd.then_label)
                    if next_cmd:
                        return True, next_cmd.id
                # TODO: Execute nested_then commands
            else:
                # False branch
                if cmd.else_label:
                    next_cmd = script.get_command_by_label(cmd.else_label)
                    if next_cmd:
                        return True, next_cmd.id
                # TODO: Execute nested_else commands
            
            return True, None
            
        except Exception as e:
            log(f"[WORKER {self.id}] Condition eval error: {e}")
            return False, None

    def _execute_repeat(self, cmd, script: Script) -> tuple:
        """Execute Repeat command with nested commands"""
        from core.models import RepeatCommand
        if not isinstance(cmd, RepeatCommand):
            return False, None
        
        log(f"[WORKER {self.id}] Repeat: count={cmd.count}, until={cmd.until_condition_expr}")
        
        # TODO: Implement repeat logic with isolated variables
        # For now, just execute inner commands once
        iteration = 0
        max_count = cmd.count if cmd.count > 0 else 999999
        
        while iteration < max_count and self.iteration_count < script.max_iterations:
            iteration += 1
            
            # Check until condition
            if cmd.until_condition_expr:
                try:
                    result = eval(cmd.until_condition_expr, {"__builtins__": {}}, {"variables": self.variables})
                    if result:
                        log(f"[WORKER {self.id}] Repeat: Until condition met after {iteration} iterations")
                        break
                except Exception as e:
                    log(f"[WORKER {self.id}] Repeat: Until condition eval error: {e}")
            
            # Execute inner commands
            # TODO: Implement nested command execution
            if self.stopped:
                return False, None
        
        return True, None

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
        """Execute Click command"""
        from core.models import ClickCommand
        if not isinstance(cmd, ClickCommand):
            return False
        
        log(f"[WORKER {self.id}] Click: {cmd.button_type.value} at ({cmd.x}, {cmd.y})")
        
        # TODO: Implement actual click with humanization
        # For now, just log
        time.sleep(0.1)  # Simulate action
        
        return True

    def _execute_keypress(self, cmd) -> bool:
        """Execute KeyPress command"""
        from core.models import KeyPressCommand
        if not isinstance(cmd, KeyPressCommand):
            return False
        
        log(f"[WORKER {self.id}] KeyPress: {cmd.key} x{cmd.repeat}")
        
        # TODO: Implement actual keypress
        time.sleep(0.1)  # Simulate action
        
        return True

    def _execute_text(self, cmd) -> bool:
        """Execute Text command"""
        from core.models import TextCommand
        if not isinstance(cmd, TextCommand):
            return False
        
        log(f"[WORKER {self.id}] Text: '{cmd.content}' mode={cmd.text_mode.value}")
        
        # TODO: Implement actual text input
        time.sleep(0.1)  # Simulate action
        
        return True

    def _execute_crop_image(self, cmd) -> bool:
        """Execute CropImage command"""
        from core.models import CropImageCommand
        if not isinstance(cmd, CropImageCommand):
            return False
        
        log(f"[WORKER {self.id}] CropImage: region=({cmd.x1},{cmd.y1})-({cmd.x2},{cmd.y2}) color={cmd.target_color}")
        
        # TODO: Implement actual image detection
        # For now, set dummy result
        self.variables[cmd.output_var] = {
            "x": cmd.x1,
            "y": cmd.y1,
            "confidence": 0.0
        }
        
        time.sleep(0.1)  # Simulate action
        return True

    def _execute_hotkey(self, cmd) -> bool:
        """Execute HotKey command"""
        from core.models import HotKeyCommand
        if not isinstance(cmd, HotKeyCommand):
            return False
        
        log(f"[WORKER {self.id}] HotKey: {'+'.join(cmd.keys)} order={cmd.hotkey_order.value}")
        
        # TODO: Implement actual hotkey
        time.sleep(0.1)  # Simulate action
        
        return True

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
