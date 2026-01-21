import subprocess
import re
import os
import sys
from utils.logger import log

# For Windows: Hide console window when running subprocess
if sys.platform == 'win32':
    import ctypes
    # CREATE_NO_WINDOW flag
    CREATE_NO_WINDOW = 0x08000000
else:
    CREATE_NO_WINDOW = 0

class ADBManager:
    """Quản lý ADB kết nối tới LDPlayer emulator
    
    Tích hợp với LDPlayer emulator để:
    1. Detect emulator instances
    2. Query resolution của emulator
    3. Connect via TCP/Serial
    """
    
    def __init__(self):
        self.adb_path = self._find_adb()
        if not self.adb_path:
            log("[ADB] WARNING: ADB not found in PATH")
        else:
            log(f"[ADB] Found ADB at: {self.adb_path}")
    
    def _find_adb(self):
        """Tìm ADB executable trong PATH hoặc LDPlayer directory"""
        # Cách 0: Check bundled ADB (trong files/ folder của exe)
        # PyInstaller extracts to sys._MEIPASS when --onefile
        bundled_paths = []
        
        # For PyInstaller --onefile (temp directory)
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            # Running in PyInstaller bundle
            base_path = sys._MEIPASS
            bundled_paths.append(os.path.join(base_path, "files", "adb.exe"))
            log(f"[ADB] PyInstaller mode, base path: {base_path}")
        
        # For normal Python or PyInstaller --onedir
        bundled_paths.extend([
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "files", "adb.exe"),
            os.path.join(os.getcwd(), "files", "adb.exe"),
            os.path.join(os.path.dirname(sys.executable if getattr(sys, 'frozen', False) else __file__), "files", "adb.exe"),
        ])
        
        for path in bundled_paths:
            abs_path = os.path.abspath(path)
            if os.path.exists(abs_path):
                log(f"[ADB] Using bundled ADB: {abs_path}")
                return abs_path
            else:
                log(f"[ADB] Checked: {abs_path} - not found")
        
        # Cách 1: Check PATH
        try:
            result = subprocess.run(
                ["adb", "version"],
                capture_output=True,
                timeout=2,
                creationflags=CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            if result.returncode == 0:
                return "adb"
        except Exception:
            pass
        
        # Cách 2: Check LDPlayer directory
        possible_paths = [
            r"C:\Program Files\LDPlayer\LDPlayer9\adb.exe",
            r"C:\Program Files\LDPlayer\LDPlayer4.0\adb.exe",
            r"C:\Program Files (x86)\LDPlayer\LDPlayer9\adb.exe",
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                return path
        
        return None
    
    def get_devices(self):
        """Lấy danh sách emulator instances"""
        if not self.adb_path:
            return []
        
        try:
            result = subprocess.run(
                [self.adb_path, "devices"],
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            
            devices = []
            for line in result.stdout.split('\n'):
                line = line.strip()
                if line and '\t' in line and 'device' in line:
                    device_id = line.split('\t')[0]
                    devices.append(device_id)
            
            return devices
        except Exception as e:
            log(f"[ADB] Failed to get devices: {e}")
            return []
    
    def query_resolution(self, device_id="emulator-5554"):
        """
        Query resolution từ emulator via ADB
        
        Args:
            device_id (str): Device ID (e.g., "emulator-5554", "127.0.0.1:21503")
        
        Returns:
            tuple: (width, height) hoặc None nếu thất bại
        
        Phương pháp:
            1. Thử wm size (preferred)
            2. Fallback dumpsys display
            3. Return None nếu tất cả fail
        """
        if not self.adb_path:
            log(f"[ADB] {device_id}: ADB not found, cannot query resolution")
            return None
        
        # Validate device_id format
        if not device_id or not isinstance(device_id, str):
            log(f"[ADB] Invalid device_id: {device_id}")
            return None
        
        try:
            # Cách 1: wm size (Android API, most reliable)
            try:
                result = subprocess.run(
                    [self.adb_path, "-s", device_id, "shell", "wm", "size"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    creationflags=CREATE_NO_WINDOW if sys.platform == 'win32' else 0
                )
                
                if result.returncode == 0:
                    # Output: "Physical size: 540x960"
                    match = re.search(r'(\d+)x(\d+)', result.stdout)
                    if match:
                        width, height = int(match.group(1)), int(match.group(2))
                        log(f"[ADB] {device_id}: Resolution {width}x{height} (wm size)")
                        return (width, height)
                    else:
                        log(f"[ADB] {device_id}: wm size returned unexpected format: {result.stdout}")
            except subprocess.TimeoutExpired:
                log(f"[ADB] {device_id}: wm size timeout (5s)")
            except Exception as e:
                log(f"[ADB] {device_id}: wm size failed: {e}")
            
            # Cách 2: dumpsys display (fallback)
            try:
                result = subprocess.run(
                    [self.adb_path, "-s", device_id, "shell", "dumpsys", "display"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    creationflags=CREATE_NO_WINDOW if sys.platform == 'win32' else 0
                )
                
                if result.returncode == 0:
                    # Look for resolution pattern like "1080 x 1920" or "1080x1920"
                    # Regex allows optional spaces around 'x': \s*
                    match = re.search(r'(\d{3,4})\s*x\s*(\d{3,4})', result.stdout)
                    if match:
                        width, height = int(match.group(1)), int(match.group(2))
                        log(f"[ADB] {device_id}: Resolution {width}x{height} (dumpsys fallback)")
                        return (width, height)
                    else:
                        log(f"[ADB] {device_id}: dumpsys no resolution pattern found")
            except subprocess.TimeoutExpired:
                log(f"[ADB] {device_id}: dumpsys timeout (5s)")
            except Exception as e:
                log(f"[ADB] {device_id}: dumpsys failed: {e}")
        
        except Exception as e:
            log(f"[ADB] {device_id}: Unexpected error querying resolution: {e}")
        
        return None
    
    def connect_device(self, device_address):
        """
        Kết nối tới device (e.g., 127.0.0.1:21503)
        """
        if not self.adb_path:
            return False
        
        try:
            result = subprocess.run(
                [self.adb_path, "connect", device_address],
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            
            if "connected" in result.stdout.lower():
                log(f"[ADB] Connected to {device_address}")
                return True
            else:
                log(f"[ADB] Failed to connect to {device_address}: {result.stdout}")
                return False
        except Exception as e:
            log(f"[ADB] Connection error: {e}")
            return False