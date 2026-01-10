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

def detect_ldplayer_windows():
    """Detect active LDPlayer emulator windows - improved matching"""
    windows = []
    
    def enum_handler(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return
        
        title = win32gui.GetWindowText(hwnd)
        if not title:
            return
        
        class_name = win32gui.GetClassName(hwnd)
        
        # EXCLUDE: Tkinter windows (from our own UI)
        if class_name == "TkTopLevel" or class_name == "Tk":
            return
        
        # Improved matching: check for common LDPlayer window characteristics
        is_ldplayer = (
            class_name == "LDPlayerMainFrame" or  # Official LDPlayer class
            class_name == "LDPlayerMainWindow" or
            ("LDPlayer" in title and class_name != "TkTopLevel") or  # Title match but not Tkinter
            (title.startswith("LD") and len(title) < 50)  # Short LD* titles (not full app names)
        )
        
        if is_ldplayer:
            try:
                rect = win32gui.GetWindowRect(hwnd)
                x, y, right, bottom = rect
                width = right - x
                height = bottom - y
                
                # Filter by minimum size (LDPlayer emulator window should be reasonably large)
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
                    'client_rect': (x, y, width, height)
                })
            except Exception as e:
                log(f"[DETECT] Failed to get rect for {title}: {e}")
    
    try:
        win32gui.EnumWindows(enum_handler, None)
    except Exception as e:
        log(f"[DETECT] EnumWindows failed: {e}")
    
    return windows

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
