#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Initialize workers from detected LDPlayer windows
Integrates with ADB to set correct resolution per emulator
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.tech import win32gui
from core.worker import Worker
from core.adb_manager import ADBManager
from utils.logger import log

# =============================================================================
# EMULATOR DETECTION - ADB-BASED (Most Reliable)
# Only detect windows that have active ADB connections
# =============================================================================

# Known emulator ADB port patterns (for matching hwnd to adb device)
EMULATOR_ADB_PORTS = {
    # LDPlayer: emulator-5554, emulator-5556, ...
    "emulator": {"type": "LDPlayer", "port_start": 5554, "port_end": 5600},
    # NoxPlayer: 127.0.0.1:62001, 127.0.0.1:62025, ...
    "62": {"type": "NoxPlayer", "port_start": 62001, "port_end": 62100},
    # MEmu: 127.0.0.1:21503, 127.0.0.1:21513, ...
    "21": {"type": "MEmu", "port_start": 21503, "port_end": 21600},
    # MuMu: 127.0.0.1:7555, ...
    "75": {"type": "MuMu", "port_start": 7555, "port_end": 7600},
    # BlueStacks: 127.0.0.1:5555, ...
    "55": {"type": "BlueStacks", "port_start": 5555, "port_end": 5600},
}

# Window class names for emulators (used to find window for ADB device)
EMULATOR_WINDOW_CLASSES = [
    "LDPlayerMainFrame", "LDPlayerMainWindow",  # LDPlayer
    "Qt5QWindowIcon", "Qt5152QWindowIcon",  # Nox, MuMu, BlueStacks
    "BlueStacksApp",  # BlueStacks
    "neaborwndclass",  # MuMu
    "QtWindow",  # MEmu
]

# Exclude these classes completely
EXCLUDED_CLASSES = [
    "TkTopLevel", "Tk",  # Tkinter (our UI)
    "Chrome_WidgetWin_1",  # Chrome
    "MozillaWindowClass",  # Firefox  
    "CASCADIA_HOSTING_WINDOW_CLASS",  # Windows Terminal
    "ConsoleWindowClass",  # CMD/PowerShell
    "Notepad",  # Notepad
    "CabinetWClass",  # File Explorer
    "Shell_TrayWnd",  # Taskbar
]


def get_adb_devices():
    """Get list of connected ADB devices"""
    adb = ADBManager()
    return adb.get_devices()


def identify_emulator_type(device_id):
    """Identify emulator type from ADB device ID"""
    if not device_id:
        return "Unknown"
    
    device_lower = device_id.lower()
    
    # LDPlayer: emulator-5554
    if device_lower.startswith("emulator-"):
        return "LDPlayer"
    
    # IP:port format
    if ":" in device_id:
        try:
            port = int(device_id.split(":")[-1])
            if 62001 <= port <= 62100:
                return "NoxPlayer"
            elif 21503 <= port <= 21600:
                return "MEmu"
            elif 7555 <= port <= 7600:
                return "MuMu"
            elif 5555 <= port <= 5600:
                return "BlueStacks"
        except:
            pass
    
    return "Unknown"


def get_all_visible_windows():
    """Get all visible windows with their info"""
    windows = []
    
    def enum_handler(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return
        
        title = win32gui.GetWindowText(hwnd)
        if not title:
            return
        
        class_name = win32gui.GetClassName(hwnd)
        
        # Skip excluded classes
        if class_name in EXCLUDED_CLASSES:
            return
        
        try:
            rect = win32gui.GetWindowRect(hwnd)
            x, y, right, bottom = rect
            width = right - x
            height = bottom - y
            
            # Filter by minimum size (emulator windows are large)
            if width < 300 or height < 300:
                return
            
            windows.append({
                'hwnd': hwnd,
                'title': title,
                'class': class_name,
                'x': x,
                'y': y,
                'width': width,
                'height': height,
            })
        except:
            pass
    
    try:
        win32gui.EnumWindows(enum_handler, None)
    except Exception as e:
        log(f"[DETECT] EnumWindows failed: {e}")
    
    return windows


def detect_emulator_windows(emulator_types=None):
    """
    Detect emulator windows by checking ADB devices first.
    Only windows that correspond to ADB devices are returned.
    
    This is more reliable than window title matching.
    """
    # Step 1: Get all ADB devices
    adb_devices = get_adb_devices()
    
    if not adb_devices:
        log("[DETECT] No ADB devices found - no emulators detected")
        return []
    
    log(f"[DETECT] Found {len(adb_devices)} ADB device(s): {adb_devices}")
    
    # Step 2: Get all visible windows that could be emulators
    all_windows = get_all_visible_windows()
    
    # Filter to only emulator-like windows (by class name)
    potential_emulators = []
    for w in all_windows:
        # Check if class name matches known emulator classes
        if w['class'] in EMULATOR_WINDOW_CLASSES:
            potential_emulators.append(w)
        # Also check title for emulator keywords (as backup)
        elif any(kw in w['title'] for kw in ['LDPlayer', 'BlueStacks', 'NoxPlayer', 'MuMu', 'MEmu']):
            potential_emulators.append(w)
    
    log(f"[DETECT] Found {len(potential_emulators)} potential emulator window(s)")
    
    # Step 3: Match ADB devices to windows
    # For now, we assume each ADB device has a window
    # We return windows up to the number of ADB devices
    
    results = []
    for i, device_id in enumerate(adb_devices):
        emu_type = identify_emulator_type(device_id)
        
        # Try to find matching window
        matched_window = None
        
        # For each potential emulator window, try to match by emulator type
        for w in potential_emulators:
            if w in [r for r in results]:  # Already used
                continue
            
            # Match by class name or title
            if emu_type == "LDPlayer" and ("LDPlayer" in w['class'] or "LDPlayer" in w['title']):
                matched_window = w
                break
            elif emu_type == "NoxPlayer" and ("Nox" in w['title'] or "Qt5152" in w['class']):
                matched_window = w
                break
            elif emu_type == "BlueStacks" and "BlueStacks" in w['title']:
                matched_window = w
                break
            elif emu_type == "MuMu" and "MuMu" in w['title']:
                matched_window = w
                break
            elif emu_type == "MEmu" and "MEmu" in w['title']:
                matched_window = w
                break
        
        # If no specific match, use next available window
        if not matched_window and potential_emulators:
            for w in potential_emulators:
                if w not in [r for r in results]:
                    matched_window = w
                    break
        
        if matched_window:
            results.append({
                'hwnd': matched_window['hwnd'],
                'title': matched_window['title'],
                'class': matched_window['class'],
                'emulator_type': emu_type,
                'adb_device': device_id,
                'x': matched_window['x'],
                'y': matched_window['y'],
                'width': matched_window['width'],
                'height': matched_window['height'],
                'client_rect': (matched_window['x'], matched_window['y'], 
                               matched_window['width'], matched_window['height'])
            })
            log(f"[DETECT] Matched ADB {device_id} ({emu_type}) → {matched_window['title']}")
    
    log(f"[DETECT] Total detected: {len(results)} emulator(s)")
    return results


def detect_ldplayer_windows():
    """Backward compatible function - now uses ADB-based detection"""
    return detect_emulator_windows()


# Keep old config for reference
ENABLED_EMULATORS = ["LDPlayer", "BlueStacks", "NoxPlayer", "MuMu", "MEmu"]

def get_enabled_emulators():
    """Get list of enabled emulators"""
    return ENABLED_EMULATORS

def set_enabled_emulators(emulator_list):
    """Set which emulators to detect"""
    global ENABLED_EMULATORS
    ENABLED_EMULATORS = emulator_list


def query_ldplayer_devices():
    """Query ADB for LDPlayer device IDs"""
    adb = ADBManager()
    devices = adb.get_devices()
    return devices

def match_windows_to_devices(windows, devices):
    """
    Match detected LDPlayer windows to ADB devices
    
    Strategy:
    1. If only 1 window → match to first device
    2. If multiple windows → try to match by device count
    3. Return list of (window, device) pairs
    """
    pairs = []
    
    # Simple matching: assume windows in order match devices in order
    for i, window in enumerate(windows):
        if i < len(devices):
            pairs.append((window, devices[i]))
        else:
            pairs.append((window, None))  # No matching device
    
    return pairs

def initialize_workers_from_ldplayer():
    """
    Full initialization pipeline with fallback:
    1. Try to detect LDPlayer windows
    2. Query ADB devices
    3. Match windows to devices (with fallback)
    4. Create Worker objects
    
    Fallback strategy:
    - If windows detected but < devices → create fake window from ADB device
    - If no windows but devices exist → create from ADB only (screen will update later)
    """
    
    print(f"\n{'='*60}")
    print(f"Initializing Workers from LDPlayer")
    print(f"{'='*60}\n")
    
    # Step 1: Detect windows
    print("Step 1: Detecting LDPlayer windows...")
    windows = detect_ldplayer_windows()
    
    if not windows:
        print("✗ No LDPlayer windows detected via EnumWindows")
        print("  (Will try fallback: ADB devices only)")
    else:
        print(f"✓ Found {len(windows)} window(s):")
        for i, w in enumerate(windows, 1):
            print(f"   {i}. {w['title']} | {w['width']}x{w['height']} at ({w['x']}, {w['y']})")
    
    # Step 2: Query ADB devices
    print("\nStep 2: Querying ADB devices...")
    devices = query_ldplayer_devices()
    
    if not devices:
        print("✗ No ADB devices found")
        print("   (App sẽ chạy không có worker - dùng Refresh sau khi mở LDPlayer)")
        print(f"\n{'='*60}")
        print(f"✓ Initialized 0 worker(s) - Standalone mode")
        print(f"{'='*60}\n")
        return []  # Return empty, app vẫn chạy bình thường
    
    print(f"✓ Found {len(devices)} device(s):")
    for i, d in enumerate(devices, 1):
        print(f"   {i}. {d}")
    
    # Step 3: Match windows to devices with fallback
    print("\nStep 3: Matching windows to devices...")
    pairs = match_windows_to_devices(windows, devices)
    
    # FALLBACK: If more devices than windows, create synthetic windows
    if len(devices) > len(windows):
        print(f"\n⚠ More devices ({len(devices)}) than windows ({len(windows)})")
        print("  Creating synthetic window entries from ADB devices...")
        
        for device in devices[len(windows):]:
            # Create synthetic window entry (will be detected at runtime)
            synthetic_window = {
                'hwnd': None,  # Will be detected later
                'title': f"LDPlayer-{device}",
                'x': 0,
                'y': 0,
                'width': 540,  # Default LDPlayer resolution
                'height': 960,
                'client_rect': (0, 0, 540, 960)
            }
            pairs.append((synthetic_window, device))
            print(f"   ✓ {synthetic_window['title']} → {device}")
    
    for window, device in pairs:
        if device:
            print(f"   ✓ {window['title']} → {device}")
        else:
            print(f"   ⚠ {window['title']} → (no matching device)")
    
    # Step 4: Create workers with ADB resolution
    print("\nStep 4: Creating workers with auto-detected resolution...")
    workers = []
    
    for worker_id, (window, device) in enumerate(pairs, start=1):
        try:
            # If hwnd is None (synthetic), will try to detect it later
            worker = Worker(
                worker_id=worker_id,
                hwnd=window['hwnd'],
                client_rect=window['client_rect'],
                res_width=None,  # Will be auto-detected via ADB
                res_height=None,
                adb_device=device
            )
            workers.append(worker)
            
            print(f"✓ Worker {worker_id}:")
            print(f"   Window: {window['title']}")
            print(f"   Device: {device if device else '(none)'}")
            print(f"   Resolution: {worker.res_width}x{worker.res_height}")
            print(f"   Window Size: {worker.client_w}x{worker.client_h}")
            print(f"   Scale: {worker.scale_x:.3f}x, {worker.scale_y:.3f}y")
            
        except Exception as e:
            print(f"✗ Worker {worker_id} failed: {e}")
            import traceback
            traceback.print_exc()
    
    print(f"\n{'='*60}")
    print(f"✓ Initialized {len(workers)} worker(s)")
    print(f"{'='*60}\n")
    
    return workers

if __name__ == "__main__":
    # Test the initialization
    workers = initialize_workers_from_ldplayer()
    
    if workers:
        print("\nWorkers ready for use:")
        for w in workers:
            print(f"  - Worker {w.id}: {w.res_width}x{w.res_height}")
