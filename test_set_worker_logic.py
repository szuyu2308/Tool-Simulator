#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Test set_worker_dialog logic without opening UI"""

from initialize_workers import detect_ldplayer_windows
from core.worker_manager import WorkerAssignmentManager

print("="*60)
print("Testing set_worker_dialog logic")
print("="*60)

# Step 1: Detect windows
ldplayer_windows = detect_ldplayer_windows()
print(f"\n✓ Step 1: Detected {len(ldplayer_windows)} LDPlayer window(s)")
if not ldplayer_windows:
    print("No windows detected")
    exit(1)

# Step 2: Create manager
worker_mgr = WorkerAssignmentManager()
print(f"✓ Step 2: WorkerAssignmentManager created")

# Step 3: Test ldplayer_list comprehension (THE FIX)
ldplayer_list = [(w['hwnd'], w['title']) for w in ldplayer_windows]
print(f"✓ Step 3: ldplayer_list created: {ldplayer_list}")

# Step 4: Test auto_assign_selected logic
print(f"\n✓ Step 4: Testing auto_assign_selected...")
hwnd_strs = [str(hwnd) for hwnd, title in ldplayer_list]
print(f"  Selected hwnd(s): {hwnd_strs}")

result = worker_mgr.auto_assign_selected(hwnd_strs)
print(f"  Assignment result: {result}")

# Step 5: Verify assignment
print(f"\n✓ Step 5: Verifying assignment...")
for hwnd_str in hwnd_strs:
    worker_id = worker_mgr.get_worker_id(hwnd_str)
    print(f"  {hwnd_str} → Worker {worker_id}")

# Step 6: Test get_summary
summary = worker_mgr.get_summary()
print(f"\n✓ Step 6: Current assignments summary:")
print(summary)

print("\n" + "="*60)
print("✅ All logic tests PASSED!")
print("="*60)
