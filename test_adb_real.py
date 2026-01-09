#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test script để verify ADB setup với LDPlayer thực tế
Chạy: python test_adb_real.py

Yêu cầu:
1. LDPlayer được cài đặt
2. ADB accessible từ PATH hoặc LDPlayer directory
3. LDPlayer emulator đang chạy
"""

import subprocess
import sys
import time
from core.adb_manager import ADBManager
from core.worker import get_adb_manager
from utils.logger import log

def print_section(title):
    """Print formatted section header"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

def test_adb_installation():
    """Test 1: Check if ADB is installed"""
    print_section("TEST 1: ADB Installation Check")
    
    adb = ADBManager()
    if adb.adb_path:
        print(f"✓ ADB found at: {adb.adb_path}")
        
        # Get ADB version
        try:
            result = subprocess.run(
                [adb.adb_path, "version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            print(f"✓ ADB version check: OK")
            print(result.stdout.strip())
        except Exception as e:
            print(f"✗ Failed to get ADB version: {e}")
            return False
    else:
        print(f"✗ ADB not found")
        return False
    
    return True

def test_device_detection():
    """Test 2: Detect connected emulator devices"""
    print_section("TEST 2: Device Detection")
    
    adb = ADBManager()
    devices = adb.get_devices()
    
    if not devices:
        print(f"✗ No devices found")
        print(f"   - Ensure LDPlayer emulator is running")
        print(f"   - Check: adb devices")
        return False
    
    print(f"✓ Found {len(devices)} device(s):")
    for i, device in enumerate(devices, 1):
        print(f"   {i}. {device}")
    
    return True

def test_resolution_query():
    """Test 3: Query resolution from each device"""
    print_section("TEST 3: Resolution Query")
    
    adb = ADBManager()
    devices = adb.get_devices()
    
    if not devices:
        print(f"✗ No devices to query")
        return False
    
    all_success = True
    for device in devices:
        resolution = adb.query_resolution(device)
        if resolution:
            width, height = resolution
            print(f"✓ {device:25} → {width}x{height}")
        else:
            print(f"✗ {device:25} → Failed to query resolution")
            all_success = False
    
    return all_success

def test_worker_setup():
    """Test 4: Setup workers with auto-detected resolution"""
    print_section("TEST 4: Worker Setup with Resolution Detection")
    
    adb = ADBManager()
    devices = adb.get_devices()
    
    if not devices:
        print(f"✗ No devices available")
        return False
    
    from core.worker import WorkerStatus
    
    # Simulate worker setup for first device
    device = devices[0]
    resolution = adb.query_resolution(device)
    
    if not resolution:
        print(f"✗ Cannot get resolution for {device}")
        return False
    
    res_width, res_height = resolution
    
    # Create worker with simulated window dimensions
    # Assume window is 540x960 (typical emulator window)
    try:
        worker = WorkerStatus(
            worker_id=1,
            hwnd=0,  # Dummy handle
            client_rect=(100, 100, 540, 960),  # Simulated window at (100,100), size 540x960
            adb_device=device,
            adb_manager=adb
        )
        
        print(f"✓ Worker created successfully:")
        print(f"   Device: {device}")
        print(f"   Game Resolution: {worker.res_width}x{worker.res_height}")
        print(f"   Window Size: {worker.client_w}x{worker.client_h}")
        print(f"   Scale Factor: {worker.scale_x:.3f}x, {worker.scale_y:.3f}y")
        
        # Test coordinate mapping
        print(f"\n   Coordinate Mapping Test:")
        test_coords = [
            (0, 0),           # Top-left
            (res_width//2, res_height//2),  # Center
            (res_width-1, res_height-1),    # Bottom-right
        ]
        
        for local_x, local_y in test_coords:
            screen_x, screen_y = worker.local_to_screen(local_x, local_y)
            print(f"   - Game ({local_x:4}, {local_y:4}) → Screen ({screen_x:4}, {screen_y:4})")
        
        return True
    
    except Exception as e:
        print(f"✗ Worker setup failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_global_adb_singleton():
    """Test 5: Verify global ADB manager singleton"""
    print_section("TEST 5: Global ADB Manager Singleton")
    
    adb1 = get_adb_manager()
    adb2 = get_adb_manager()
    
    if adb1 is adb2:
        print(f"✓ Singleton pattern working correctly")
        print(f"   Same instance: {id(adb1)} == {id(adb2)}")
        return True
    else:
        print(f"✗ Singleton pattern failed")
        return False

def test_multiple_devices():
    """Test 6: Handle multiple emulator instances"""
    print_section("TEST 6: Multiple Device Support")
    
    adb = ADBManager()
    devices = adb.get_devices()
    
    if len(devices) < 2:
        print(f"⚠ Only {len(devices)} device(s) available (need 2+ for this test)")
        if len(devices) == 1:
            print(f"  Using single device instead")
    
    from core.worker import WorkerStatus
    
    workers = []
    for i, device in enumerate(devices[:3]):  # Test up to 3 devices
        try:
            worker = WorkerStatus(
                worker_id=i+1,
                hwnd=0,
                client_rect=(100 + i*600, 100, 540, 960),
                adb_device=device,
                adb_manager=adb
            )
            workers.append(worker)
            print(f"✓ Worker {i+1} ({device}): {worker.res_width}x{worker.res_height}")
        except Exception as e:
            print(f"✗ Worker {i+1} ({device}): {e}")
            return False
    
    if workers:
        print(f"\n✓ Successfully created {len(workers)} workers")
        return True
    else:
        return False

def main():
    """Run all tests"""
    print(f"\n{'#'*60}")
    print(f"# ADB + LDPlayer Integration Test")
    print(f"# Run with LDPlayer emulator(s) active")
    print(f"{'#'*60}")
    
    tests = [
        ("ADB Installation", test_adb_installation),
        ("Device Detection", test_device_detection),
        ("Resolution Query", test_resolution_query),
        ("Worker Setup", test_worker_setup),
        ("Singleton Pattern", test_global_adb_singleton),
        ("Multiple Devices", test_multiple_devices),
    ]
    
    results = {}
    for name, test_func in tests:
        try:
            results[name] = test_func()
        except Exception as e:
            print(f"\n✗ Test failed with exception: {e}")
            import traceback
            traceback.print_exc()
            results[name] = False
        
        time.sleep(0.5)  # Brief pause between tests
    
    # Summary
    print_section("TEST SUMMARY")
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}  {name}")
    
    print(f"\nResult: {passed}/{total} tests passed")
    
    if passed == total:
        print(f"\n✓ All tests passed! ADB setup is ready.")
        return 0
    else:
        print(f"\n✗ Some tests failed. Check errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
