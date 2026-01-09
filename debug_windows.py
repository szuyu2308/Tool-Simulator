#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Debug script: List all visible windows and identify LDPlayer ones
"""

from core.tech import win32gui
import sys

def list_all_windows():
    """List ALL visible windows"""
    windows = []
    
    def enum_handler(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return
        
        title = win32gui.GetWindowText(hwnd)
        class_name = win32gui.GetClassName(hwnd)
        
        if title:  # Only list windows with title
            rect = win32gui.GetWindowRect(hwnd)
            x, y, right, bottom = rect
            width = right - x
            height = bottom - y
            
            windows.append({
                'hwnd': hwnd,
                'title': title,
                'class': class_name,
                'rect': (x, y, width, height),
                'size': f"{width}x{height}"
            })
    
    try:
        win32gui.EnumWindows(enum_handler, None)
    except Exception as e:
        print(f"EnumWindows failed: {e}")
    
    return windows

def identify_ldplayer(windows):
    """Identify which windows are LDPlayer"""
    ldplayer_windows = []
    other_windows = []
    
    for w in windows:
        title = w['title']
        class_name = w['class']
        
        # EXCLUDE: Tkinter windows (from our own UI)
        if class_name == "TkTopLevel" or class_name == "Tk":
            other_windows.append(w)
            continue
        
        # Improved matching: check for common LDPlayer window characteristics
        is_ldplayer = (
            class_name == "LDPlayerMainFrame" or  # Official LDPlayer class
            class_name == "LDPlayerMainWindow" or
            ("LDPlayer" in title and class_name != "TkTopLevel") or  # Title match but not Tkinter
            (title.startswith("LD") and len(title) < 50)  # Short LD* titles
        )
        
        if is_ldplayer:
            ldplayer_windows.append(w)
        else:
            other_windows.append(w)
    
    return ldplayer_windows, other_windows

if __name__ == "__main__":
    print(f"\n{'='*80}")
    print("DEBUG: Window Enumeration & LDPlayer Detection")
    print(f"{'='*80}\n")
    
    # Step 1: List all windows
    print("Step 1: Listing ALL visible windows...")
    all_windows = list_all_windows()
    print(f"Total: {len(all_windows)} window(s)\n")
    
    for i, w in enumerate(all_windows, 1):
        print(f"{i}. Title: '{w['title']}'")
        print(f"   Class: {w['class']}")
        print(f"   Size: {w['size']}")
        print(f"   Position: ({w['rect'][0]}, {w['rect'][1]})")
        print(f"   HWND: 0x{w['hwnd']:08x}")
        print()
    
    # Step 2: Identify LDPlayer
    print(f"{'='*80}")
    print("Step 2: Identifying LDPlayer windows...")
    ldplayer_wins, other_wins = identify_ldplayer(all_windows)
    
    print(f"\n✓ LDPlayer windows: {len(ldplayer_wins)}")
    for i, w in enumerate(ldplayer_wins, 1):
        print(f"   {i}. {w['title']} ({w['size']})")
    
    print(f"\n✗ Other windows: {len(other_wins)}")
    for i, w in enumerate(other_wins, 1):
        if len(w['title']) < 50:
            print(f"   {i}. {w['title']}")
        else:
            print(f"   {i}. {w['title'][:50]}...")
    
    print(f"\n{'='*80}\n")
    
    # Step 3: Query ADB
    print("Step 3: Querying ADB devices...")
    from core.adb_manager import ADBManager
    
    adb = ADBManager()
    devices = adb.get_devices()
    
    if devices:
        print(f"✓ Found {len(devices)} ADB device(s):")
        for d in devices:
            print(f"   - {d}")
    else:
        print("✗ No ADB devices found")
    
    print(f"\n{'='*80}\n")
