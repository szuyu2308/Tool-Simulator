#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Test the fix for set_worker_dialog ldplayer_list"""

from initialize_workers import detect_ldplayer_windows

windows = detect_ldplayer_windows()
print(f"Type: {type(windows)}")
print(f"Length: {len(windows)}")

if windows:
    w = windows[0]
    print(f"\nFirst window type: {type(w)}")
    print(f"First window keys: {w.keys()}")
    print(f"hwnd: {w['hwnd']}")
    print(f"title: {w['title']}")
    
    # Test list comprehension (THE FIX)
    ldplayer_list = [(w['hwnd'], w['title']) for w in windows]
    print(f"\nList comprehension result: {ldplayer_list}")
    print("✓ Fix is correct!")
else:
    print("No windows found")
