# ROLE: SENIOR PYTHON AUTOMATION ENGINEER
You are an expert in Python, ADB, and Image Processing. You focus on robust error handling, clean code (PEP8), and performance optimization.

# TASK: FIX STABILITY ISSUES IN `execute_crop_image_command`
Fix the `TimeoutError` crash in `worker/execution.py` when ADB or the emulator lags.

## 1. CONTEXT & PROBLEM
- **Target File:** `worker/execution.py`
- **Target Function:** `execute_crop_image_command`
- **Current Behavior:** The worker crashes with `TimeoutError` when `adb_capture_screen` takes longer than 15s.
- **Root Cause:** Lack of retry mechanism and failure handling logic when the device is laggy or offline.

## 2. ERROR TRACE
```text
File "worker/execution.py", line 148, in execute_crop_image_command
screen = adb_capture_screen(region)
File "utils/adb_utils.py", line 67, in adb_capture_screen
raise TimeoutError("ADB screencap timeout after 15s")