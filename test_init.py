#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test worker initialization
"""

from initialize_workers import initialize_workers_from_ldplayer

if __name__ == "__main__":
    print("\n" + "="*80)
    print("Testing worker initialization...")
    print("="*80 + "\n")
    
    workers = initialize_workers_from_ldplayer()
    
    print(f"\n✓ Initialized {len(workers)} worker(s):\n")
    for i, w in enumerate(workers, 1):
        print(f"{i}. Worker:")
        print(f"   - ID: {w.id}")
        print(f"   - Status: {w.status}")
        if w.hwnd:
            print(f"   - HWND: 0x{w.hwnd:08x}")
        print(f"   - Client Size: {w.client_w}x{w.client_h}")
        print(f"   - Resolution: {w.res_width}x{w.res_height}")
        print(f"   - ADB Device: {w.adb_device}")
        print()
    
    print("="*80)
    print(f"RESULT: Total {len(workers)} worker(s) initialized successfully")
    print("="*80)
