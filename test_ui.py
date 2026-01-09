#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test UI với mock workers
Dùng để test nút Check All mà không cần LDPlayer thực tế
"""

from unittest.mock import MagicMock, patch
from core.worker import Worker
from ui.main_ui import MainUI

# Create mock workers
def create_mock_worker(worker_id, res_width=540, res_height=960):
    """Create a mock worker for testing UI"""
    worker = MagicMock(spec=Worker)
    worker.id = worker_id
    worker.hwnd = 12345 + worker_id
    worker.adb_device = f"emulator-554{worker_id}"
    worker.res_width = res_width
    worker.res_height = res_height
    worker.client_w = 540
    worker.client_h = 960
    worker.scale_x = worker.client_w / res_width
    worker.scale_y = worker.client_h / res_height
    worker.current_command = None
    worker.is_ready = MagicMock(return_value=True)
    return worker

# Create 3 test workers
workers = [
    create_mock_worker(1, 540, 960),
    create_mock_worker(2, 1080, 1920),
    create_mock_worker(3, 720, 1280),
]

print(f"Created {len(workers)} mock workers")
print("\nStarting UI...")
print("Click '🔍 Check All' button to test")
print("Click '🔍 Check' button and select a worker to see details")

# Start UI
ui = MainUI(workers)
ui.root.mainloop()
