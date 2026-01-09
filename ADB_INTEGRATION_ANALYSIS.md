## PHÂN TÍCH VÀ CẢI THIỆN ADB INTEGRATION - CODE PROTOCOL

### 📊 TÓAN BỘ CHANGES

---

### **1. FILE CHANGES**

#### **A) [core/adb_manager.py](core/adb_manager.py)**
**Type B/C Risk Fix**

**Changes:**
- ✅ Thêm docstring chi tiết cho class
- ✅ Cải thiện `query_resolution()`:
  - Thêm validation device_id format
  - Thêm try-except chi tiết cho mỗi subprocess call
  - Phân tách timeout handling (TimeoutExpired vs Exception)
  - Log message chi tiết ở mỗi bước (wm size → dumpsys → fail)
  - Validate ADB path trước khi sử dụng

**Diff Summary:**
```python
# BEFORE: Generic exception handling
except Exception as e:
    log(f"[ADB] Failed to query resolution for {device_id}: {e}")
    return None

# AFTER: Specific error handling with detailed logs
except subprocess.TimeoutExpired:
    log(f"[ADB] {device_id}: wm size timeout (5s)")
except Exception as e:
    log(f"[ADB] {device_id}: wm size failed: {e}")

# Fallback to dumpsys with same detailed approach
```

**Risk Mitigation:**
- Regex parse lỗi → log pattern không match → debug dễ hơn
- Device không kết nối → return None (fallback worker to client area)
- Timeout → clear log message, không hang

---

#### **B) [core/worker.py](core/worker.py)**
**Type C Risk Fix - ADB Instance Management**

**Changes:**
- ✅ Thêm global singleton `get_adb_manager()`
- ✅ Thêm parameter `adb_manager` to `WorkerStatus.__init__()`
- ✅ Reuse ADB instance thay vì tạo lại mỗi worker
- ✅ Thêm docstring cho init
- ✅ Log scale factors để debug coordinate mapping

**Diff Summary:**
```python
# BEFORE: Create new ADB instance per worker
if res_width is None or res_height is None:
    adb = ADBManager()  # ❌ Creates new instance every time
    detected = adb.query_resolution(adb_device)

# AFTER: Reuse global singleton
def get_adb_manager():
    global _global_adb_manager
    if _global_adb_manager is None:
        _global_adb_manager = ADBManager()
    return _global_adb_manager

# In WorkerStatus.__init__:
adb = adb_manager or get_adb_manager()  # ✅ Reuse instance
```

**Manfaat:**
- Mengurangi subprocess calls (faster initialization)
- Menghindari multiple ADB instance overhead
- Memungkinkan dependency injection (adb_manager parameter)

---

### **2. TEST SUITES**

#### **A) [tests/test_adb_ldplayer.py](tests/test_adb_ldplayer.py)**
**Comprehensive Unit Tests dengan Mock**

**Coverage:**
- TC-LDPLAYER-001: Device detection
- TC-LDPLAYER-002 to 004: Resolution query (multiple resolutions: 540x960, 720x1280, 1080x1920)
- TC-LDPLAYER-005: Fallback dumpsys handling
- TC-LDPLAYER-006: TCP device connection
- TC-LDPLAYER-007: Worker auto-detect resolution
- TC-LDPLAYER-008: Scale factor calculation
- TC-LDPLAYER-009: Coordinate mapping validation
- TC-LDPLAYER-010: Out-of-bounds detection
- TC-LDPLAYER-011: Fallback when ADB fails
- TC-LDPLAYER-012: Multiple workers with different resolutions
- TC-LDPLAYER-013: Timeout handling
- TC-LDPLAYER-014: Invalid device ID
- TC-LDPLAYER-015: ADB not installed

**Chạy:**
```bash
python -m pytest tests/test_adb_ldplayer.py -v -s
```

---

#### **B) [test_adb_real.py](test_adb_real.py)**
**Integration Test với LDPlayer Thực Tế**

**Tests:**
1. TEST 1: ADB installation check
2. TEST 2: Device detection
3. TEST 3: Resolution query per device
4. TEST 4: Worker setup with auto-detection
5. TEST 5: Singleton pattern verification
6. TEST 6: Multiple device support

**Chạy (cần LDPlayer emulator đang chạy):**
```bash
python test_adb_real.py
```

**Output Example:**
```
============================================================
  TEST 1: ADB Installation Check
============================================================
✓ ADB found at: C:\Program Files\LDPlayer\LDPlayer9\adb.exe
✓ ADB version check: OK

============================================================
  TEST 2: Device Detection
============================================================
✓ Found 2 device(s):
   1. emulator-5554
   2. 127.0.0.1:21503

============================================================
  TEST 3: Resolution Query
============================================================
✓ emulator-5554              → 540x960
✓ 127.0.0.1:21503            → 1080x1920
```

---

### **3. KIỂM THỬ SCENARIOS**

#### **Scenario 1: Detect LDPlayer Resolution (540x960)**
```
Device: emulator-5554
ADB cmd: adb -s emulator-5554 shell wm size
Output: Physical size: 540x960

→ WorkerStatus init:
  - res_width = 540, res_height = 960
  - client_w = 540, client_h = 960 (or other window size)
  - scale_x = client_w / 540
  - scale_y = client_h / 960

→ Coordinate test:
  - Game (0, 0) → Screen (100, 100)  # Top-left
  - Game (270, 480) → Screen (235, 340)  # Center
```

#### **Scenario 2: Fallback when wm size fails**
```
Device: emulator-5554
ADB cmd 1: adb -s emulator-5554 shell wm size
→ FAIL (returncode != 0)

ADB cmd 2: adb -s emulator-5554 shell dumpsys display
→ SUCCESS: Returns "1080x1920"

→ WorkerStatus:
  - res_width = 1080, res_height = 1920 (from dumpsys)
```

#### **Scenario 3: ADB Timeout**
```
Device: emulator-5554
ADB cmd: subprocess.TimeoutExpired (5s)

→ Caught and logged: "[ADB] emulator-5554: wm size timeout (5s)"
→ Return None from query_resolution()
→ WorkerStatus: Fallback to client_w x client_h
```

#### **Scenario 4: Multiple Workers**
```
Worker 1: emulator-5554 (540x960)
Worker 2: 127.0.0.1:21503 (1080x1920)

→ Both reuse same global ADB instance
→ Each has independent resolution & scale factors
→ Coordinate mapping works correctly per worker
```

---

### **4. RISK MITIGATION TABLE**

| Risk | Type | Before | After | Status |
|------|------|--------|-------|--------|
| ADB executable not found | A | Return empty device list | Log warning, handle gracefully | ✅ |
| Resolution regex parse error | B | Silent fail, fallback | Detailed log of regex attempt | ✅ |
| Timeout not caught | B | App hang | Explicit TimeoutExpired catch | ✅ |
| Device ID validation | B | No validation | Validate format before ADB call | ✅ |
| ADB instance leak | C | Create new per worker | Singleton global instance | ✅ |
| Scale factor wrong | B | No logging | Log scale_x, scale_y per worker | ✅ |
| Coordinate out-of-bounds | A | RuntimeError | Explicit ValueError with details | ✅ |

---

### **5. VALIDATION CHECKLIST**

**Before Running Macro:**
- [ ] ADB installed (test_adb_real.py TEST 1)
- [ ] LDPlayer emulator running (test_adb_real.py TEST 2)
- [ ] Resolution detected correctly (test_adb_real.py TEST 3)
- [ ] Workers initialized with correct scale (check_status button in UI)
- [ ] Coordinate mapping tested (TEST 4)

**Command Execution:**
- [ ] Check worker.is_inside(x, y) before mapping
- [ ] Use worker.local_to_screen(x, y) for all game coordinates
- [ ] Verify scale_x, scale_y in UI status message

---

### **6. HOW TO VERIFY**

**1. Unit Tests (Mock-based):**
```bash
cd s:\Tools_LDplayer
python -m pytest tests/test_adb_ldplayer.py -v
```

**2. Real Integration Test:**
```bash
# Start LDPlayer emulator(s) first!
python test_adb_real.py
```

**3. UI Check (manual):**
- Open app.py (run MainUI)
- Set Worker → Select LDPlayer
- Click "🔍 Check" button
- Verify: Resolution (ADB), Client Area, Scale factors

---

### **7. NOTES**

**ADB Resolution Priority:**
1. wm size (preferred, most accurate)
2. dumpsys display (fallback)
3. client_w x client_h (last resort)

**Device ID Format:**
- Serial device: "emulator-5554", "emulator-5555"
- TCP device: "127.0.0.1:21503", "192.168.1.100:5555"

**Scale Factor Calculation:**
- scale_x = window_width / game_resolution_width
- scale_y = window_height / game_resolution_height
- For 1080x1920 game on 540x960 window: scale = 0.5x

**Singleton Pattern:**
- `get_adb_manager()` returns global ADB instance
- Can pass custom instance via `adb_manager` parameter
- Reduces ADB subprocess calls

---

### **8. NEXT STEPS (Optional)**

1. Add retry logic for ADB commands (up to 3 retries)
2. Cache resolution for faster worker initialization
3. Monitor ADB connection state periodically
4. Add device selection dialog in UI
5. Store resolution per device in profiles/device_config.json

---

**Status: ✅ READY FOR REVIEW**

Bạn có thể run `python test_adb_real.py` để test với LDPlayer emulator thực tế.

