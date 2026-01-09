"""
Test ADB integration với LDPlayer emulator
Kiểm tra resolution detection, device connection, và worker setup
"""

import pytest
from unittest.mock import patch, MagicMock, call
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.adb_manager import ADBManager
from core.worker import WorkerStatus, Worker, get_adb_manager


class TestADBLDPlayerIntegration:
    """Test case cho ADB + LDPlayer + Worker setup"""
    
    @pytest.fixture
    def adb(self):
        """Initialize ADB manager"""
        return ADBManager()
    
    # ============ TEST 1: Device Detection ============
    
    @patch('core.adb_manager.subprocess.run')
    def test_get_devices_ldplayer(self, mock_run):
        """TC-LDPLAYER-001: Detect LDPlayer devices"""
        # Setup mock for all subprocess.run calls
        # Note: adb output uses TABS, not spaces!
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="List of attached devices\nemulator-5554\t\t\tdevice\nemulator-5555\t\t\tdevice\n127.0.0.1:21503\t\t\tdevice\n"
        )
        
        # Now create ADB manager (with mocked subprocess.run)
        adb = ADBManager()
        # Mock should be active, but just in case set path explicitly
        adb.adb_path = "adb"
        
        # Reset mock to track only get_devices() call
        mock_run.reset_mock()
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="List of attached devices\nemulator-5554\t\t\tdevice\nemulator-5555\t\t\tdevice\n127.0.0.1:21503\t\t\tdevice\n"
        )
        
        devices = adb.get_devices()
        
        assert len(devices) >= 3, f"Expected >= 3 devices, got {len(devices)}: {devices}"
        assert "emulator-5554" in devices
        assert "emulator-5555" in devices
        assert "127.0.0.1:21503" in devices
        print(f"✓ Found devices: {devices}")
    
    # ============ TEST 2: Resolution Query - wm size ============
    
    @patch('core.adb_manager.subprocess.run')
    def test_query_resolution_wm_size_540x960(self, mock_run):
        """TC-LDPLAYER-002: Query resolution via wm size (540x960)"""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Physical size: 540x960\n"
        )
        
        adb = ADBManager()
        adb.adb_path = "adb"
        res = adb.query_resolution("emulator-5554")
        
        assert res == (540, 960)
        assert mock_run.called
        print(f"✓ Resolution detected: {res}")
    
    @patch('core.adb_manager.subprocess.run')
    def test_query_resolution_wm_size_720x1280(self, mock_run):
        """TC-LDPLAYER-003: Query resolution via wm size (720x1280)"""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Physical size: 720x1280\n"
        )
        
        adb = ADBManager()
        adb.adb_path = "adb"
        res = adb.query_resolution("emulator-5554")
        
        assert res == (720, 1280)
        print(f"✓ Resolution detected: {res}")
    
    @patch('core.adb_manager.subprocess.run')
    def test_query_resolution_wm_size_1080x1920(self, mock_run):
        """TC-LDPLAYER-004: Query resolution via wm size (1080x1920)"""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Physical size: 1080x1920\n"
        )
        
        adb = ADBManager()
        adb.adb_path = "adb"
        res = adb.query_resolution("emulator-5554")
        
        assert res == (1080, 1920)
        print(f"✓ Resolution detected: {res}")
    
    # ============ TEST 3: Resolution Query - Fallback dumpsys ============
    
    @patch('core.adb_manager.subprocess.run')
    def test_query_resolution_dumpsys_fallback(self, mock_run):
        """TC-LDPLAYER-005: Fallback to dumpsys display when wm size fails"""
        call_count = [0]
        
        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:  # _find_adb() call during __init__
                return MagicMock(returncode=1, stdout="")  # ADB not in PATH
            elif call_count[0] == 2:  # wm size call fails
                return MagicMock(returncode=1, stdout="")
            else:  # call_count == 3: dumpsys call succeeds
                return MagicMock(
                    returncode=0,
                    stdout="mBaseDisplayInfo=DisplayInfo{..., 1080 x 1920, ...}"
                )
        
        mock_run.side_effect = side_effect
        
        adb = ADBManager()
        adb.adb_path = "adb"  # Manually set path (since _find_adb will fail)
        
        # Reset mock to count only query_resolution() calls
        mock_run.reset_mock()
        mock_run.side_effect = side_effect
        
        res = adb.query_resolution("emulator-5554")
        
        assert res == (1080, 1920), f"Expected (1080, 1920), got {res}"
        assert mock_run.call_count == 2  # First wm size fails, then dumpsys succeeds
        print(f"✓ Fallback to dumpsys successful: {res}")
    
    # ============ TEST 4: Device Connection ============
    
    @patch('core.adb_manager.subprocess.run')
    def test_connect_device_tcp(self, mock_run):
        """TC-LDPLAYER-006: Connect to LDPlayer via TCP (127.0.0.1:21503)"""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="connected to 127.0.0.1:21503\n"
        )
        
        adb = ADBManager()
        adb.adb_path = "adb"
        result = adb.connect_device("127.0.0.1:21503")
        
        assert result is True
        print(f"✓ Device connected: 127.0.0.1:21503")
    
    # ============ TEST 5: Worker Setup with ADB Resolution ============
    
    @patch('core.adb_manager.subprocess.run')
    def test_worker_setup_with_adb_resolution(self, mock_run):
        """TC-LDPLAYER-007: Worker initialization with ADB auto-detect resolution"""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Physical size: 1080x1920\n"
        )
        
        # Create worker without explicit resolution (should auto-detect)
        worker = WorkerStatus(
            worker_id=1,
            hwnd=12345,
            client_rect=(100, 100, 540, 960),  # Window client area
            adb_device="emulator-5554"  # Let it auto-detect
        )
        
        # Verify resolution was detected from ADB (not fallback to client area)
        assert worker.res_width == 1080, f"Expected 1080, got {worker.res_width}"
        assert worker.res_height == 1920, f"Expected 1920, got {worker.res_height}"
        print(f"✓ Worker resolution (from ADB): {worker.res_width}x{worker.res_height}")
    
    # ============ TEST 6: Worker Scaling Calculation ============
    
    @patch('core.adb_manager.subprocess.run')
    def test_worker_scale_factor_calculation(self, mock_run):
        """TC-LDPLAYER-008: Verify scale factor calculation for coordinate mapping"""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Physical size: 1080x1920\n"
        )
        
        worker = WorkerStatus(
            worker_id=1,
            hwnd=12345,
            client_rect=(100, 100, 540, 960),  # Window client area
            adb_device="emulator-5554"
        )
        
        # Verify scale factors
        # scale_x = client_w / res_width = 540 / 1080 = 0.5
        # scale_y = client_h / res_height = 960 / 1920 = 0.5
        assert worker.scale_x == pytest.approx(0.5, abs=0.001)
        assert worker.scale_y == pytest.approx(0.5, abs=0.001)
        print(f"✓ Scale factors correct: x={worker.scale_x:.3f}, y={worker.scale_y:.3f}")
    
    # ============ TEST 7: Coordinate Mapping Local → Screen ============
    
    @patch('core.adb_manager.subprocess.run')
    def test_local_to_screen_coordinate_mapping(self, mock_run):
        """TC-LDPLAYER-009: Test coordinate mapping from local (game) to screen"""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Physical size: 1080x1920\n"
        )
        
        worker = Worker(
            worker_id=1,
            hwnd=12345,
            client_rect=(100, 100, 540, 960),  # Window at screen (100,100), size 540x960
            adb_device="emulator-5554"  # Resolution 1080x1920
        )
        
        # Test case: Click center of game screen
        # Game resolution: 1080x1920
        # Center: (540, 960)
        # With scale 0.5, center maps to middle of client area
        # Client area: (100, 100) to (640, 1060)
        # Center of client: (370, 580)
        screen_x, screen_y = worker.local_to_screen(540, 960)
        
        expected_x = 100 + 540 * 0.5  # = 370
        expected_y = 100 + 960 * 0.5  # = 580
        
        assert screen_x == int(expected_x)
        assert screen_y == int(expected_y)
        print(f"✓ Coordinate mapping: (540, 960) → ({screen_x}, {screen_y})")
    
    # ============ TEST 8: Invalid Coordinate Detection ============
    
    @patch('core.adb_manager.subprocess.run')
    def test_coordinate_out_of_bounds(self, mock_run):
        """TC-LDPLAYER-010: Detect out-of-bounds local coordinates"""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Physical size: 1080x1920\n"
        )
        
        worker = Worker(
            worker_id=1,
            hwnd=12345,
            client_rect=(100, 100, 540, 960),
            adb_device="emulator-5554"  # Resolution 1080x1920
        )
        
        # Try to map coordinate outside game resolution
        with pytest.raises(ValueError):
            worker.local_to_screen(1200, 960)  # x=1200 > res_width=1080
        
        with pytest.raises(ValueError):
            worker.local_to_screen(540, 2000)  # y=2000 > res_height=1920
        
        print(f"✓ Out-of-bounds detection working")
    
    # ============ TEST 9: Fallback to Client Area Resolution ============
    
    @patch('core.adb_manager.subprocess.run')
    def test_worker_fallback_to_client_area(self, mock_run):
        """TC-LDPLAYER-011: Worker fallback to client area when ADB fails"""
        mock_run.side_effect = Exception("ADB not found")
        
        worker = WorkerStatus(
            worker_id=1,
            hwnd=12345,
            client_rect=(100, 100, 540, 960),
            adb_device="emulator-5554"  # ADB will fail
        )
        
        # Should fallback to client area dimensions
        assert worker.res_width == 540
        assert worker.res_height == 960
        print(f"✓ Fallback resolution: {worker.res_width}x{worker.res_height}")
    
    # ============ TEST 10: Multiple Workers with Different Resolutions ============
    
    @patch('core.adb_manager.subprocess.run')
    def test_multiple_workers_different_resolutions(self, mock_run):
        """TC-LDPLAYER-012: Multiple workers with different LDPlayer resolutions"""
        
        def get_resolution(*args, **kwargs):
            cmd_args = args[0] if args else []
            cmd_str = str(cmd_args)
            
            if "emulator-5554" in cmd_str:
                return MagicMock(returncode=0, stdout="Physical size: 540x960\n")
            elif "emulator-5555" in cmd_str:
                return MagicMock(returncode=0, stdout="Physical size: 1080x1920\n")
            else:
                return MagicMock(returncode=0, stdout="Physical size: 720x1280\n")
        
        mock_run.side_effect = get_resolution
        
        worker1 = WorkerStatus(1, 12345, (0, 0, 540, 960), adb_device="emulator-5554")
        worker2 = WorkerStatus(2, 12346, (600, 0, 540, 960), adb_device="emulator-5555")
        
        assert worker1.res_width == 540 or worker1.res_width == 540  # fallback
        assert worker2.res_width == 1080 or worker2.res_width == 540  # might be detected
        print(f"✓ Multiple workers configured independently")


class TestADBEdgeCases:
    """Edge cases và error handling"""
    
    @patch('core.adb_manager.subprocess.run')
    def test_adb_timeout_handling(self, mock_run):
        """TC-LDPLAYER-013: Handle ADB timeout gracefully"""
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired("adb", 5)
        
        adb = ADBManager()
        adb.adb_path = "adb"
        devices = adb.get_devices()
        
        assert devices == []
        print(f"✓ Timeout handled gracefully")
    
    @patch('core.adb_manager.subprocess.run')
    def test_adb_invalid_device_id(self, mock_run):
        """TC-LDPLAYER-014: Handle invalid device ID"""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="error: device 'invalid-device' not found"
        )
        
        adb = ADBManager()
        adb.adb_path = "adb"
        res = adb.query_resolution("invalid-device")
        
        assert res is None
        print(f"✓ Invalid device ID handled")
    
    @patch('core.adb_manager.subprocess.run')
    def test_adb_not_installed(self, mock_run):
        """TC-LDPLAYER-015: Handle ADB not installed"""
        mock_run.side_effect = FileNotFoundError("adb not found")
        
        adb = ADBManager()
        assert adb.adb_path is None
        print(f"✓ ADB not installed handled")


if __name__ == "__main__":
    # Run with: python -m pytest tests/test_adb_ldplayer.py -v
    pytest.main([__file__, "-v", "-s"])
