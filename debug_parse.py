#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Debug device parsing"""

stdout_str = "List of attached devices\nemulator-5554          device\nemulator-5555          device\n127.0.0.1:21503       device\n"

print("Raw stdout:")
print(repr(stdout_str))
print("\n" + "="*60 + "\n")

devices = []
for line in stdout_str.split('\n'):
    line = line.strip()
    print(f"Processing: [{line}]")
    
    if not line:
        print("  → Empty line, skip")
        continue
    
    has_tab = '\t' in line
    has_device = 'device' in line
    
    print(f"  Has TAB: {has_tab}, Has 'device': {has_device}")
    
    if line and '\t' in line and 'device' in line:
        print(f"  ✓ MATCH!")
        device_id = line.split('\t')[0]
        devices.append(device_id)
        print(f"    Device ID: {device_id}")
    else:
        print(f"  ✗ Skip")

print("\n" + "="*60)
print(f"Final devices: {devices}")
print(f"Count: {len(devices)}")
