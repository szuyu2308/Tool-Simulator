# ROLE: SENIOR PYTHON AUTOMATION ENGINEER
You are an expert in Python Backend, ADB Automation, and Image Processing. 
You strictly follow **PEP 8** standards, use **Type Hinting** (PEP 484), and prioritize performance/stability.

# TASK: REFACTOR & OPTIMIZE `worker/execution.py`
**Goal:** Fix timeout crashes, optimize logic, and clean up the codebase.

## 1. ANALYSIS & REQUIREMENTS (PYTHON SPECIFIC)
- **Target File:** `worker/execution.py`
- **Language Level:** Python 3.10+
- **Style Guide:** PEP 8 (Black Formatter, line-length=88).
- **Naming Convention:** 
  - Classes: `PascalCase` (e.g., `ExecutionWorker`)
  - Functions/Variables: `snake_case` (e.g., `execute_crop_command`, `retry_count`)
  - Constants: `UPPER_CASE` (e.g., `MAX_RETRIES`)

## 2. CRITICAL FIXES (LOGIC & STABILITY)
1.  **Retry Mechanism (Exponential Backoff):**
    - Wrap `adb_capture_screen` and critical ADB commands in a retry loop.
    - Logic: Retry 3 times → Sleep 1s, 2s, 4s.
    - If all fail: Raise `CustomCommandFailError` (do not return silent `None` or `False`).
2.  **Error Handling:**
    - Use specific `try-except` blocks (catch `TimeoutError`, `ConnectionError`).
    - **Never** use bare `except:` without logging the specific error trace.
3.  **Process Management:**
    - Ensure thread safety if using `threading` or `multiprocessing`.
    - Use `with` statements (Context Managers) for file/socket operations to prevent memory leaks.

## 3. PERFORMANCE OPTIMIZATION
1.  **Screen Capture Strategy:**
    - Priority 1: Use `dxcam` (if on Windows/Nox/LDPlayer) for <10ms capture.
    - Priority 2: Use `mss` for desktop capture.
    - Priority 3: Use `adb shell screencap` (slowest, fallback only).
    - **Caching:** Cache screen data for 300-500ms if multiple checks happen in the same tick.
2.  **Input Methods:**
    - Use `pywin32` or `ctypes` (`SendInput`) for clicks to bypass ADB latency when possible.
    - Only use ADB for special Android keys (Home, Back, AppSwitch).

## 4. CLEAN CODE & LOGGING
1.  **Remove Debug Noise:**
    - **DELETE**: `print()`, `pprint()`, `debug=True` flags, and commented-out code.
    - **KEEP**: `logger.error()` for exceptions, `logger.info()` for critical state changes only.
2.  **Type Hinting:**
    - Add types to ALL function signatures.
    - Example: `def capture(region: Tuple[int, int, int, int]) -> Optional[np.ndarray]:`
3.  **Refactoring:**
    - Break down functions longer than 50 lines.
    - Move purely utility functions (math, string parsing) to `utils/`.

## 5. EXECUTION PLAN
1.  Parse the current `worker/execution.py`.
2.  Refactor `execute_crop_image_command` to include the Retry/Backoff logic.
3.  Replace all legacy debugging prints with the `logging` module.
4.  Format the final code using Black style.
5.  **Output ONLY the refined code. No explanations.**

# COMMAND: EXECUTE NOW