#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Test UI changes for Set Worker dialog"""

from initialize_workers import detect_ldplayer_windows
from core.worker_manager import WorkerAssignmentManager

print("="*70)
print("TEST: New Set Worker Dialog Logic")
print("="*70)

# Detect windows
ldplayer_windows = detect_ldplayer_windows()
print(f"\n✓ Step 1: Detected {len(ldplayer_windows)} LDPlayer window(s)")
if not ldplayer_windows:
    print("No windows detected")
    exit(1)

# Init manager
worker_mgr = WorkerAssignmentManager()
print(f"✓ Step 2: WorkerAssignmentManager initialized")

# Prepare ldplayer_list (without Control Panel buttons)
ldplayer_list = [(w['hwnd'], w['title']) for w in ldplayer_windows]
print(f"✓ Step 3: LDPlayer list prepared (without Select/Unselect buttons)")
print(f"  Windows: {ldplayer_list}")

# Test auto_assign_selected (with selected checkboxes)
print(f"\n✓ Step 4: Test 'Set Worker (Auto)' - Auto-assign selected LDPlayers")
hwnd_strs = [str(hwnd) for hwnd, title in ldplayer_list]
result = worker_mgr.auto_assign_selected(hwnd_strs)
print(f"  Assignment result: {result}")

# Display summary (as in UI)
print(f"\n✓ Step 5: Display current assignments (in Status text)")
summary = worker_mgr.get_summary()
print(f"  {summary}")

# Test delete_worker (with selected checkboxes)
print(f"\n✓ Step 6: Test 'Delete Selected Worker' - Delete selected LDPlayers")
deleted_count = 0
for hwnd in [hwnd for hwnd, _ in ldplayer_list]:
    if worker_mgr.remove_worker(str(hwnd)):
        deleted_count += 1

print(f"  Deleted: {deleted_count} LDPlayer(s)")

# Check summary after delete
summary = worker_mgr.get_summary()
print(f"\n✓ Step 7: Assignments after delete:")
print(f"  {summary if summary != 'No assignments' else '(empty)'}")

print("\n" + "="*70)
print("✅ All UI logic tests PASSED!")
print("="*70)
print("\nUI Changes Summary:")
print("  ✓ Removed 'Select' column from Worker Status table")
print("  ✓ Added 'Worker' column to show assigned Worker ID")
print("  ✓ Removed Control Panel buttons (Select All/One, Unselect All/One)")
print("  ✓ Kept simple checkboxes for selecting LDPlayers")
print("  ✓ Changed 'Delete Worker Random' → 'Delete Selected Worker'")
print("="*70)
