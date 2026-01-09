"""
EmulatorInstance and CapabilitySet classes
Multi-emulator support with client-pixel coordinates
"""

from typing import List, Optional, Tuple, Dict, Any
from dataclasses import dataclass, field
from enum import Enum
import ctypes
from ctypes import wintypes


# Windows API imports
user32 = ctypes.windll.user32


class CaptureMethod(Enum):
    BETTERCAM = "BetterCam"
    DXCAM = "DXCam"
    MSS = "MSS"


class InputMethod(Enum):
    SEND_INPUT = "SendInput"
    POST_MESSAGE = "PostMessage"
    ADB = "ADB"


class TextMethod(Enum):
    CLIPBOARD_PASTE = "ClipboardPaste"
    ADB_INPUT_TEXT = "ADBInputText"


@dataclass
class CapabilitySet:
    """Capabilities for an emulator instance"""
    capture: List[CaptureMethod] = field(default_factory=lambda: [
        CaptureMethod.BETTERCAM,
        CaptureMethod.DXCAM,
        CaptureMethod.MSS
    ])
    input: List[InputMethod] = field(default_factory=lambda: [
        InputMethod.SEND_INPUT,
        InputMethod.POST_MESSAGE,
        InputMethod.ADB
    ])
    text: List[TextMethod] = field(default_factory=lambda: [
        TextMethod.CLIPBOARD_PASTE,
        TextMethod.ADB_INPUT_TEXT
    ])


@dataclass
class ClientRect:
    """Client area rectangle in screen coordinates"""
    x: int  # Left position on screen
    y: int  # Top position on screen
    w: int  # Width
    h: int  # Height
    
    def client_to_screen(self, cx: int, cy: int) -> Tuple[int, int]:
        """Convert client coordinates to screen coordinates"""
        return (self.x + cx, self.y + cy)
    
    def contains(self, cx: int, cy: int) -> bool:
        """Check if client coordinates are within bounds"""
        return 0 <= cx < self.w and 0 <= cy < self.h
    
    def as_tuple(self) -> Tuple[int, int, int, int]:
        return (self.x, self.y, self.w, self.h)


@dataclass
class EmulatorInstance:
    """
    Represents one running emulator instance.
    All coordinates are in CLIENT PIXEL SPACE.
    """
    instance_id: str
    hwnd: int  # Top-level window handle
    client_rect_screen: ClientRect  # Client area in screen coordinates
    vendor: Optional[str] = None  # Informational only (LDPlayer, Nox, etc.)
    input_hwnd: Optional[int] = None  # Child window for input (if different)
    adb_serial: Optional[str] = None  # ADB device serial (e.g., "emulator-5554")
    capabilities: CapabilitySet = field(default_factory=CapabilitySet)
    
    @staticmethod
    def get_client_rect_screen(hwnd: int) -> Optional[ClientRect]:
        """
        Get accurate client area in screen coordinates.
        Uses GetClientRect + ClientToScreen for precision.
        """
        try:
            # Get client area dimensions
            rect = wintypes.RECT()
            if not user32.GetClientRect(hwnd, ctypes.byref(rect)):
                return None
            
            client_w = rect.right - rect.left
            client_h = rect.bottom - rect.top
            
            # Convert client (0,0) to screen coordinates
            point = wintypes.POINT(0, 0)
            if not user32.ClientToScreen(hwnd, ctypes.byref(point)):
                return None
            
            return ClientRect(
                x=point.x,
                y=point.y,
                w=client_w,
                h=client_h
            )
        except Exception:
            return None
    
    def refresh_client_rect(self) -> bool:
        """Refresh client rect from current window state"""
        new_rect = self.get_client_rect_screen(self.hwnd)
        if new_rect:
            self.client_rect_screen = new_rect
            return True
        return False
    
    def is_valid(self) -> bool:
        """Check if the emulator window is still valid"""
        return user32.IsWindow(self.hwnd) != 0
    
    def is_visible(self) -> bool:
        """Check if the emulator window is visible (not minimized)"""
        return (self.is_valid() and 
                user32.IsWindowVisible(self.hwnd) != 0 and
                user32.IsIconic(self.hwnd) == 0)
    
    def __repr__(self):
        vendor_str = f" ({self.vendor})" if self.vendor else ""
        adb_str = f" [{self.adb_serial}]" if self.adb_serial else ""
        return (f"<EmulatorInstance {self.instance_id}{vendor_str}{adb_str} "
                f"hwnd={self.hwnd} rect={self.client_rect_screen.as_tuple()}>")


class DeviceProvider:
    """
    IDeviceProvider implementation - Multi-emulator discovery
    Enumerates emulator windows via WinAPI
    """
    
    # Known emulator window patterns (class name, title patterns)
    EMULATOR_PATTERNS = [
        # LDPlayer
        {"class": "LDPlayerMainFrame", "vendor": "LDPlayer"},
        {"title_contains": "LDPlayer", "vendor": "LDPlayer"},
        # Nox
        {"class": "Qt5QWindowIcon", "title_contains": "NoxPlayer", "vendor": "Nox"},
        {"title_contains": "NoxPlayer", "vendor": "Nox"},
        # MuMu
        {"class": "Qt5QWindowIcon", "title_contains": "MuMu", "vendor": "MuMu"},
        {"title_contains": "MuMu", "vendor": "MuMu"},
        # BlueStacks
        {"class": "Qt5154QWindowOwnDCIcon", "vendor": "BlueStacks"},
        {"title_contains": "BlueStacks", "vendor": "BlueStacks"},
        # MEmu
        {"title_contains": "MEmu", "vendor": "MEmu"},
        # Generic Android emulator
        {"title_contains": "Android", "vendor": "Generic"},
    ]
    
    def __init__(self):
        self._instances: Dict[int, EmulatorInstance] = {}
        self._adb_devices: List[str] = []
    
    def enumerate_windows(self) -> List[EmulatorInstance]:
        """
        Enumerate all emulator windows.
        Returns list of EmulatorInstance with accurate client_rect_screen.
        """
        instances = []
        windows = []
        
        # Callback for EnumWindows
        def enum_callback(hwnd, lparam):
            if user32.IsWindowVisible(hwnd):
                windows.append(hwnd)
            return True
        
        WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        user32.EnumWindows(WNDENUMPROC(enum_callback), 0)
        
        # Check each window against patterns
        for hwnd in windows:
            vendor = self._match_emulator_pattern(hwnd)
            if vendor:
                instance = self._create_instance(hwnd, vendor)
                if instance:
                    instances.append(instance)
        
        return instances
    
    def _match_emulator_pattern(self, hwnd: int) -> Optional[str]:
        """Match window against known emulator patterns"""
        try:
            # Get window class name
            class_name = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, class_name, 256)
            class_str = class_name.value
            
            # Get window title
            title_len = user32.GetWindowTextLengthW(hwnd) + 1
            title = ctypes.create_unicode_buffer(title_len)
            user32.GetWindowTextW(hwnd, title, title_len)
            title_str = title.value
            
            # Match against patterns
            for pattern in self.EMULATOR_PATTERNS:
                if "class" in pattern and pattern["class"] == class_str:
                    if "title_contains" in pattern:
                        if pattern["title_contains"].lower() in title_str.lower():
                            return pattern["vendor"]
                    else:
                        return pattern["vendor"]
                elif "title_contains" in pattern:
                    if pattern["title_contains"].lower() in title_str.lower():
                        return pattern["vendor"]
            
            return None
        except Exception:
            return None
    
    def _create_instance(self, hwnd: int, vendor: str) -> Optional[EmulatorInstance]:
        """Create EmulatorInstance from window handle"""
        client_rect = EmulatorInstance.get_client_rect_screen(hwnd)
        if not client_rect or client_rect.w < 100 or client_rect.h < 100:
            return None  # Too small, probably not the main window
        
        # Get window title for instance_id
        title_len = user32.GetWindowTextLengthW(hwnd) + 1
        title = ctypes.create_unicode_buffer(title_len)
        user32.GetWindowTextW(hwnd, title, title_len)
        
        instance_id = title.value if title.value else f"Emulator_{hwnd}"
        
        return EmulatorInstance(
            instance_id=instance_id,
            hwnd=hwnd,
            client_rect_screen=client_rect,
            vendor=vendor,
            capabilities=CapabilitySet()
        )
    
    def pair_with_adb(self, instances: List[EmulatorInstance], 
                      adb_devices: List[str],
                      user_mapping: Optional[Dict[str, str]] = None) -> None:
        """
        Pair emulator instances with ADB devices.
        Priority: user_mapping > vendor plugin > heuristic
        """
        if not adb_devices:
            return
        
        # First: apply user mapping
        if user_mapping:
            for instance in instances:
                if instance.instance_id in user_mapping:
                    serial = user_mapping[instance.instance_id]
                    if serial in adb_devices:
                        instance.adb_serial = serial
        
        # Second: heuristic pairing for unassigned
        unassigned_devices = [d for d in adb_devices 
                             if not any(i.adb_serial == d for i in instances)]
        unassigned_instances = [i for i in instances if not i.adb_serial]
        
        # Simple 1:1 pairing by order
        for instance, device in zip(unassigned_instances, unassigned_devices):
            instance.adb_serial = device
