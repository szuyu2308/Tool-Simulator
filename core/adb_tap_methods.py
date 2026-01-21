"""
ADB Tap Methods - Multiple protocols for touch input simulation

Provides different methods to simulate touch on Android emulators:
1. SendeventProtocolA - Classic sendevent sequence
2. SendeventProtocolB - Modern multitouch with slots
3. MinitouchClient - High-performance minitouch binary

Each protocol bypasses different anti-cheat detection methods.
"""

import subprocess
import time
import socket
import os
import sys
from abc import ABC, abstractmethod
from utils.logger import log

# Windows: Hide console window
if sys.platform == 'win32':
    CREATE_NO_WINDOW = 0x08000000
else:
    CREATE_NO_WINDOW = 0


class ADBTapMethod(ABC):
    """Base class for ADB tap methods"""
    
    name = "base"
    description = "Base tap method"
    
    def __init__(self, adb_path="adb"):
        self.adb_path = adb_path
        self._last_error = None
    
    @abstractmethod
    def tap(self, x, y, duration_ms, device_id, caps=None):
        """
        Execute tap at coordinates
        
        Args:
            x: X coordinate (screen pixels)
            y: Y coordinate (screen pixels)
            duration_ms: Hold duration in milliseconds
            device_id: ADB device serial (e.g., "emulator-5554")
            caps: Device capabilities dict (from ADBManager.get_device_capabilities)
        
        Returns:
            bool: Success
        """
        pass
    
    def get_last_error(self):
        return self._last_error
    
    def _run_adb(self, args, timeout=3):
        """Run ADB command with hidden window"""
        try:
            cmd = [self.adb_path] + args
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                creationflags=CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            return result
        except subprocess.TimeoutExpired:
            self._last_error = f"ADB timeout ({timeout}s)"
            return None
        except Exception as e:
            self._last_error = str(e)
            return None
# Paste này vào adb_tap_methods.py để REPLACE cả class SendeventProtocolA và SendeventProtocolB

class SendeventProtocolA(ADBTapMethod):
    """
    Sendevent Protocol A - FIXED for LDPlayer rotation
    """
    
    name = "sendevent_a"
    description = "Sendevent Protocol A (Full sequence)"
    
    # Event codes
    EV_SYN = 0
    EV_KEY = 1
    EV_ABS = 3
    
    SYN_REPORT = 0
    BTN_TOUCH = 330
    
    ABS_MT_TRACKING_ID = 57
    ABS_MT_POSITION_X = 53
    ABS_MT_POSITION_Y = 54
    ABS_MT_PRESSURE = 58
    
    def tap(self, x, y, duration_ms, device_id, caps=None):
        """Execute tap with CORRECTED rotation formula"""
        try:
            if not caps:
                caps = {
                    "touch_device": "/dev/input/event2",
                    "max_x": 32767,
                    "max_y": 32767,
                    "has_pressure": True,
                    "has_btn_touch": True
                }
            
            device = caps.get("touch_device", "/dev/input/event2")
            max_x = caps.get("max_x", 32767)
            max_y = caps.get("max_y", 32767)
            
            screen_width, screen_height = self._get_screen_size(device_id)
            if not screen_width:
                screen_width, screen_height = 1080, 1920
            
            # LDPlayer handles rotation internally - always use DIRECT mapping
            is_rotated = False
            
            log(f"[TAP-A] DEBUG: screen={screen_width}x{screen_height}, touch_max={max_x}x{max_y}, is_rotated={is_rotated}")
            
            # Direct mapping: screen coords -> touch coords (scaled to touch device range)
            abs_x = int((x * max_x) / screen_width)
            abs_y = int((y * max_y) / screen_height)
            log(f"[TAP-A] Direct: screen({x},{y}) -> touch({abs_x},{abs_y})")
            
            # Clamp
            abs_x = max(0, min(abs_x, max_x))
            abs_y = max(0, min(abs_y, max_y))
            
            # Build events
            events = []
            events.append(f"sendevent {device} {self.EV_ABS} {self.ABS_MT_TRACKING_ID} 1")
            events.append(f"sendevent {device} {self.EV_ABS} {self.ABS_MT_POSITION_X} {abs_x}")
            events.append(f"sendevent {device} {self.EV_ABS} {self.ABS_MT_POSITION_Y} {abs_y}")
            
            if caps.get("has_pressure"):
                events.append(f"sendevent {device} {self.EV_ABS} {self.ABS_MT_PRESSURE} 1")
            
            if caps.get("has_btn_touch", True):
                events.append(f"sendevent {device} {self.EV_KEY} {self.BTN_TOUCH} 1")
            
            events.append(f"sendevent {device} {self.EV_SYN} {self.SYN_REPORT} 0")
            
            # Execute touch down
            result = self._run_adb(["-s", device_id, "shell", " && ".join(events)], timeout=2)
            if result is None or result.returncode != 0:
                self._last_error = "Touch down failed"
                return False
            
            # Hold
            if duration_ms > 0:
                time.sleep(duration_ms / 1000.0)
            
            # Touch up
            up_events = []
            if caps.get("has_btn_touch", True):
                up_events.append(f"sendevent {device} {self.EV_KEY} {self.BTN_TOUCH} 0")
            up_events.append(f"sendevent {device} {self.EV_ABS} {self.ABS_MT_TRACKING_ID} -1")
            up_events.append(f"sendevent {device} {self.EV_SYN} {self.SYN_REPORT} 0")
            
            result = self._run_adb(["-s", device_id, "shell", " && ".join(up_events)], timeout=2)
            if result is None or result.returncode != 0:
                self._last_error = "Touch up failed"
                return False
            
            log(f"[TAP-A] SUCCESS: tap({x},{y}) -> abs({abs_x},{abs_y})")
            return True
            
        except Exception as e:
            self._last_error = str(e)
            return False
    
    def _get_screen_size(self, device_id):
        try:
            result = self._run_adb(["-s", device_id, "shell", "wm", "size"], timeout=2)
            if result and result.returncode == 0:
                import re
                match = re.search(r'(\d+)x(\d+)', result.stdout)
                if match:
                    return int(match.group(1)), int(match.group(2))
        except:
            pass
        return None, None


class SendeventProtocolB(ADBTapMethod):
    """
    Sendevent Protocol B - FIXED for LDPlayer rotation
    """
    
    name = "sendevent_b"
    description = "Sendevent Protocol B (Slot-based)"
    
    # Event codes
    EV_SYN = 0
    EV_KEY = 1
    EV_ABS = 3
    
    SYN_REPORT = 0
    BTN_TOUCH = 330
    
    ABS_MT_SLOT = 47
    ABS_MT_TRACKING_ID = 57
    ABS_MT_POSITION_X = 53
    ABS_MT_POSITION_Y = 54
    ABS_MT_PRESSURE = 58
    
    def tap(self, x, y, duration_ms, device_id, caps=None):
        """Execute tap with CORRECTED rotation formula"""
        try:
            if not caps:
                caps = {
                    "touch_device": "/dev/input/event2",
                    "max_x": 32767,
                    "max_y": 32767,
                    "has_pressure": True,
                    "has_slot": True
                }
            
            device = caps.get("touch_device", "/dev/input/event2")
            max_x = caps.get("max_x", 32767)
            max_y = caps.get("max_y", 32767)
            
            screen_width, screen_height = self._get_screen_size(device_id)
            if not screen_width:
                screen_width, screen_height = 1080, 1920
            
            # Debug logging
            log(f"[TAP-B] DEBUG: screen={screen_width}x{screen_height}, touch_max={max_x}x{max_y}")
            
            # LDPlayer handles rotation internally - always use DIRECT mapping
            # Do NOT apply rotation formula, even if orientations differ
            # The touch coordinates map directly to screen coordinates
            is_rotated = False  # Force direct mapping for LDPlayer
            
            log(f"[TAP-B] DEBUG: is_rotated={is_rotated} (LDPlayer handles rotation internally)")
            
            # Direct mapping: screen coords -> touch coords (scaled to touch device range)
            abs_x = int((x * max_x) / screen_width)
            abs_y = int((y * max_y) / screen_height)
            log(f"[TAP-B] Direct: screen({x},{y}) -> touch({abs_x},{abs_y})")
            
            abs_x = max(0, min(abs_x, max_x))
            abs_y = max(0, min(abs_y, max_y))
            
            # Build events with slot
            events = []
            events.append(f"sendevent {device} {self.EV_ABS} {self.ABS_MT_SLOT} 0")
            events.append(f"sendevent {device} {self.EV_ABS} {self.ABS_MT_TRACKING_ID} 1")
            events.append(f"sendevent {device} {self.EV_ABS} {self.ABS_MT_POSITION_X} {abs_x}")
            events.append(f"sendevent {device} {self.EV_ABS} {self.ABS_MT_POSITION_Y} {abs_y}")
            
            if caps.get("has_pressure"):
                events.append(f"sendevent {device} {self.EV_ABS} {self.ABS_MT_PRESSURE} 1")
            
            events.append(f"sendevent {device} {self.EV_KEY} {self.BTN_TOUCH} 1")
            events.append(f"sendevent {device} {self.EV_SYN} {self.SYN_REPORT} 0")
            
            result = self._run_adb(["-s", device_id, "shell", " && ".join(events)], timeout=2)
            if result is None or result.returncode != 0:
                self._last_error = "Touch down failed"
                return False
            
            if duration_ms > 0:
                time.sleep(duration_ms / 1000.0)
            
            up_events = [
                f"sendevent {device} {self.EV_ABS} {self.ABS_MT_SLOT} 0",
                f"sendevent {device} {self.EV_KEY} {self.BTN_TOUCH} 0",
                f"sendevent {device} {self.EV_ABS} {self.ABS_MT_TRACKING_ID} -1",
                f"sendevent {device} {self.EV_SYN} {self.SYN_REPORT} 0"
            ]
            
            result = self._run_adb(["-s", device_id, "shell", " && ".join(up_events)], timeout=2)
            if result is None or result.returncode != 0:
                self._last_error = "Touch up failed"
                return False
            
            log(f"[TAP-B] SUCCESS: tap({x},{y}) -> abs({abs_x},{abs_y})")
            return True
            
        except Exception as e:
            self._last_error = str(e)
            return False
    
    def _get_screen_size(self, device_id):
        try:
            result = self._run_adb(["-s", device_id, "shell", "wm", "size"], timeout=2)
            if result and result.returncode == 0:
                import re
                match = re.search(r'(\d+)x(\d+)', result.stdout)
                if match:
                    return int(match.group(1)), int(match.group(2))
        except:
            pass
        return None, None


class MinitouchClient(ADBTapMethod):
    """
    Minitouch - High-performance touch simulation
    
    Uses minitouch binary (from openstf/minitouch) for fast, reliable touch.
    Communicates via socket for low latency.
    
    Requires:
        - minitouch binary pushed to /data/local/tmp/minitouch
        - minitouch running on device (via adb shell)
        - Socket connection to device (port forwarding)
    
    Protocol:
        d <contact> <x> <y> <pressure>  - Touch down
        m <contact> <x> <y> <pressure>  - Touch move
        u <contact>                      - Touch up
        c                                - Commit
        w <ms>                           - Wait
    """
    
    name = "minitouch"
    description = "Minitouch (High-performance)"
    
    _instances = {}  # Cache running instances per device
    
    def __init__(self, adb_path="adb"):
        super().__init__(adb_path)
        self._socket = None
        self._port = None
        self._process = None
    
    def tap(self, x, y, duration_ms, device_id, caps=None):
        """Execute tap using minitouch"""
        try:
            # Ensure minitouch is running
            if not self._ensure_minitouch_running(device_id):
                self._last_error = "Failed to start minitouch"
                return False
            
            # Get max coordinates from minitouch banner
            max_x = self._max_x if hasattr(self, '_max_x') else 32767
            max_y = self._max_y if hasattr(self, '_max_y') else 32767
            
            # Get screen size for conversion
            screen_width, screen_height = self._get_screen_size(device_id)
            if not screen_width:
                screen_width, screen_height = 1080, 1920
            
            # Convert coordinates
            touch_x = int((x * max_x) / screen_width)
            touch_y = int((y * max_y) / screen_height)
            touch_x = max(0, min(touch_x, max_x))
            touch_y = max(0, min(touch_y, max_y))
            
            pressure = 50
            contact = 0  # Finger index
            
            # Send touch down
            self._send_minitouch_cmd(f"d {contact} {touch_x} {touch_y} {pressure}\nc\n")
            
            # Hold
            if duration_ms > 0:
                time.sleep(duration_ms / 1000.0)
            
            # Send touch up
            self._send_minitouch_cmd(f"u {contact}\nc\n")
            
            log(f"[MINITOUCH] {device_id}: tap({x},{y}) -> ({touch_x},{touch_y}) duration={duration_ms}ms")
            return True
            
        except Exception as e:
            self._last_error = str(e)
            log(f"[MINITOUCH] Error: {e}")
            self._cleanup()
            return False
    
    def _ensure_minitouch_running(self, device_id):
        """Ensure minitouch is installed and running"""
        # Check if already running
        if self._socket and self._port:
            try:
                # Test connection
                self._socket.send(b"")
                return True
            except:
                self._cleanup()
        
        # Check if minitouch binary exists on device
        if not self._check_minitouch_installed(device_id):
            # Try to push minitouch
            if not self._push_minitouch(device_id):
                return False
        
        # Start minitouch process
        return self._start_minitouch(device_id)
    
    def _check_minitouch_installed(self, device_id):
        """Check if minitouch is installed on device"""
        result = self._run_adb(["-s", device_id, "shell", "ls", "/data/local/tmp/minitouch"], timeout=2)
        return result and result.returncode == 0 and "No such file" not in result.stdout + result.stderr
    
    def _push_minitouch(self, device_id):
        """Push minitouch binary to device"""
        # Get architecture
        result = self._run_adb(["-s", device_id, "shell", "getprop", "ro.product.cpu.abi"], timeout=2)
        if not result or result.returncode != 0:
            self._last_error = "Cannot detect device architecture"
            return False
        
        arch = result.stdout.strip()
        log(f"[MINITOUCH] Device architecture: {arch}")
        
        # Map architecture to binary
        arch_map = {
            "armeabi-v7a": "minitouch-arm",
            "arm64-v8a": "minitouch-arm64",
            "x86": "minitouch-x86",
            "x86_64": "minitouch-x86_64",
        }
        
        # Also check for partial matches
        binary_name = None
        for key, value in arch_map.items():
            if key in arch or arch in key:
                binary_name = value
                break
        
        if not binary_name:
            # Default to arm for emulators
            binary_name = "minitouch-x86" if "x86" in arch else "minitouch-arm"
        
        # Find binary path
        binary_paths = []
        
        # PyInstaller bundle
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            binary_paths.append(os.path.join(sys._MEIPASS, "files", binary_name))
        
        # Development paths
        binary_paths.extend([
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "files", binary_name),
            os.path.join(os.getcwd(), "files", binary_name),
        ])
        
        binary_path = None
        for path in binary_paths:
            if os.path.exists(path):
                binary_path = path
                break
        
        if not binary_path:
            self._last_error = f"Minitouch binary not found: {binary_name}"
            log(f"[MINITOUCH] Binary not found. Searched: {binary_paths}")
            return False
        
        # Push binary
        log(f"[MINITOUCH] Pushing {binary_path} to device...")
        result = self._run_adb(["-s", device_id, "push", binary_path, "/data/local/tmp/minitouch"], timeout=10)
        if not result or result.returncode != 0:
            self._last_error = f"Failed to push minitouch: {result.stderr if result else 'timeout'}"
            return False
        
        # Make executable
        result = self._run_adb(["-s", device_id, "shell", "chmod", "755", "/data/local/tmp/minitouch"], timeout=2)
        if not result or result.returncode != 0:
            self._last_error = "Failed to chmod minitouch"
            return False
        
        log(f"[MINITOUCH] Successfully installed on {device_id}")
        return True
    
    def _start_minitouch(self, device_id):
        """Start minitouch on device and establish socket connection"""
        import threading
        
        # Find available port
        self._port = self._find_available_port()
        
        # Forward port
        result = self._run_adb(["-s", device_id, "forward", f"tcp:{self._port}", "localabstract:minitouch"], timeout=2)
        if not result or result.returncode != 0:
            self._last_error = f"Port forward failed: {result.stderr if result else 'timeout'}"
            return False
        
        # Start minitouch process in background
        try:
            cmd = [self.adb_path, "-s", device_id, "shell", "/data/local/tmp/minitouch"]
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
        except Exception as e:
            self._last_error = f"Failed to start minitouch process: {e}"
            return False
        
        # Wait for minitouch to start
        time.sleep(0.5)
        
        # Connect socket
        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.settimeout(2)
            self._socket.connect(("127.0.0.1", self._port))
            
            # Read banner to get max coordinates
            banner = self._socket.recv(1024).decode('utf-8', errors='ignore')
            self._parse_minitouch_banner(banner)
            
            log(f"[MINITOUCH] Connected on port {self._port}")
            return True
            
        except socket.timeout:
            self._last_error = "Socket connection timeout"
            self._cleanup()
            return False
        except Exception as e:
            self._last_error = f"Socket connection failed: {e}"
            self._cleanup()
            return False
    
    def _parse_minitouch_banner(self, banner):
        """Parse minitouch banner to get max coordinates"""
        # Banner format: "v <version>\n^ <max_contacts> <max_x> <max_y> <max_pressure>\n..."
        for line in banner.split('\n'):
            if line.startswith('^'):
                parts = line.split()
                if len(parts) >= 4:
                    self._max_contacts = int(parts[1])
                    self._max_x = int(parts[2])
                    self._max_y = int(parts[3])
                    self._max_pressure = int(parts[4]) if len(parts) > 4 else 255
                    log(f"[MINITOUCH] Max coords: {self._max_x}x{self._max_y}, pressure: {self._max_pressure}")
                break
    
    def _send_minitouch_cmd(self, cmd):
        """Send command to minitouch"""
        if not self._socket:
            raise Exception("Minitouch socket not connected")
        self._socket.send(cmd.encode('utf-8'))
    
    def _find_available_port(self):
        """Find an available port"""
        import random
        return random.randint(20000, 30000)
    
    def _get_screen_size(self, device_id):
        """Get screen size via wm size"""
        try:
            result = self._run_adb(["-s", device_id, "shell", "wm", "size"], timeout=2)
            if result and result.returncode == 0:
                import re
                match = re.search(r'(\d+)x(\d+)', result.stdout)
                if match:
                    return int(match.group(1)), int(match.group(2))
        except:
            pass
        return None, None
    
    def _cleanup(self):
        """Cleanup resources"""
        if self._socket:
            try:
                self._socket.close()
            except:
                pass
            self._socket = None
        
        if self._process:
            try:
                self._process.terminate()
            except:
                pass
            self._process = None
        
        self._port = None


# ==================== DISPATCHER ====================

class ADBTapDispatcher:
    """
    Dispatcher for ADB tap methods with auto-detection and fallback
    
    Usage:
        dispatcher = ADBTapDispatcher(adb_path)
        success = dispatcher.tap(x, y, duration, device_id, method="auto")
    """
    
    METHODS = {
        "sendevent_a": SendeventProtocolA,
        "sendevent_b": SendeventProtocolB,
        "minitouch": MinitouchClient,
    }
    
    def __init__(self, adb_path="adb", adb_manager=None):
        self.adb_path = adb_path
        self.adb_manager = adb_manager
        self._method_instances = {}
        self._last_method = None
        self._last_error = None
    
    def get_method(self, method_name):
        """Get or create method instance"""
        if method_name not in self._method_instances:
            if method_name in self.METHODS:
                self._method_instances[method_name] = self.METHODS[method_name](self.adb_path)
        return self._method_instances.get(method_name)
    
    def tap(self, x, y, duration_ms, device_id, method="auto", caps=None):
        """
        Execute tap with specified or auto-detected method
        
        Args:
            x, y: Screen coordinates
            duration_ms: Hold duration
            device_id: ADB device serial
            method: "auto", "sendevent_a", "sendevent_b", or "minitouch"
            caps: Device capabilities (auto-detected if None)
        
        Returns:
            bool: Success
        """
        # Get device capabilities
        if not caps and self.adb_manager:
            caps = self.adb_manager.get_device_capabilities(device_id)
        
        if method == "auto":
            return self._tap_auto(x, y, duration_ms, device_id, caps)
        
        # Use specific method
        tap_method = self.get_method(method)
        if not tap_method:
            self._last_error = f"Unknown method: {method}"
            return False
        
        success = tap_method.tap(x, y, duration_ms, device_id, caps)
        self._last_method = method
        
        if not success:
            self._last_error = tap_method.get_last_error()
        
        return success
    
    def _tap_auto(self, x, y, duration_ms, device_id, caps):
        """
        Auto-detect best method with fallback chain
        
        Priority:
            1. minitouch (fastest, if available)
            2. sendevent_b (if device supports slots)
            3. sendevent_a (most compatible)
        """
        # Determine protocol from capabilities
        protocol = caps.get("protocol", "A") if caps else "A"
        
        # Try methods in order
        methods_to_try = []
        
        # Check if minitouch binary exists
        minitouch_path = self._find_minitouch_binary()
        if minitouch_path:
            methods_to_try.append("minitouch")
        
        # Add sendevent methods based on protocol
        if protocol == "B" and caps and caps.get("has_slot"):
            methods_to_try.append("sendevent_b")
            methods_to_try.append("sendevent_a")
        else:
            methods_to_try.append("sendevent_a")
            methods_to_try.append("sendevent_b")
        
        # Try each method
        for method_name in methods_to_try:
            tap_method = self.get_method(method_name)
            if tap_method:
                log(f"[TAP-AUTO] Trying {method_name}...")
                success = tap_method.tap(x, y, duration_ms, device_id, caps)
                
                if success:
                    self._last_method = method_name
                    log(f"[TAP-AUTO] Success with {method_name}")
                    return True
                else:
                    log(f"[TAP-AUTO] {method_name} failed: {tap_method.get_last_error()}")
        
        self._last_error = "All tap methods failed"
        return False
    
    def _find_minitouch_binary(self):
        """Check if minitouch binary exists"""
        paths = []
        
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            paths.append(os.path.join(sys._MEIPASS, "files"))
        
        paths.extend([
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "files"),
            os.path.join(os.getcwd(), "files"),
        ])
        
        for path in paths:
            for binary in ["minitouch-arm", "minitouch-x86", "minitouch-arm64"]:
                full_path = os.path.join(path, binary)
                if os.path.exists(full_path):
                    return full_path
        
        return None
    
    def get_last_method(self):
        """Get the last method used"""
        return self._last_method
    
    def get_last_error(self):
        """Get the last error"""
        return self._last_error
    
    def get_available_methods(self):
        """Get list of available methods"""
        methods = ["auto", "sendevent_a", "sendevent_b"]
        
        if self._find_minitouch_binary():
            methods.append("minitouch")
        
        return methods


# ==================== CONVENIENCE FUNCTION ====================

def create_tap_dispatcher(adb_manager=None):
    """Create a tap dispatcher with ADB manager"""
    adb_path = "adb"
    if adb_manager and adb_manager.adb_path:
        adb_path = adb_manager.adb_path
    
    return ADBTapDispatcher(adb_path, adb_manager)
