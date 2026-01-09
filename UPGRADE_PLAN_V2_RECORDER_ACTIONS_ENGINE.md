# Upgrade Plan V2 — Fix Record API + Full Wait/Image/Flow Actions + Capture UX + Debug/Test/Cleanup

**Date:** 2026-01-09  
**Target:** Tools_LDplayer (Tkinter UI + multi-worker + script/actions)  
**Goal:** Đạt mức tính năng tương đương nhóm Wait/Image/Flow cơ bản như Macro Recorder Enterprise 4.x (không copy UI riêng), tối ưu thao tác capture XY/Region, thêm debug/test rồi auto-clean.

---

## A) Critical Bugfix: Recorder API Contract

### A1. Problem
UI đang gọi:
- `self._recorder.set_target_window(target_hwnd)`
nhưng `MacroRecorder` không có method này -> crash khi Record.

### A2. Solution (LOCKED): Introduce `IRecorderHook` interface
Không để UI phụ thuộc trực tiếp vào class cụ thể. Tạo lớp adapter chuẩn.

**Interface đề xuất:**
- `configure(target_hwnd: int | None, ignore_ui_hwnd: int | None)`
- `start()`
- `stop() -> list[RecordedEvent]`
- `is_running -> bool`

**RecordedEvent** (raw, trước khi convert sang Action):
- `ts_ms`
- `kind`: mouse_move | mouse_down | mouse_up | wheel | key_down | key_up | text (optional)
- `x_screen, y_screen` (nếu là mouse)
- `key`/`vk_code`/`scan_code` (nếu là keyboard)
- `wheel_delta` (nếu wheel)
- `modifiers` snapshot

### A3. Window filtering rule (to replace `set_target_window`)
Nếu hook backend không hỗ trợ “target hwnd filtering”, thì implement filter ở layer convert:
- Khi event xảy ra:
  - Lấy `fg = GetForegroundWindow()`
  - Nếu `fg != target_hwnd` => ignore (trừ hotkeys control Record/Stop/Play/Pause)
- Với mouse events:
  - Convert `(x_screen,y_screen)` -> client coords bằng `ScreenToClient(target_hwnd, pt)`
  - Nếu point outside client rect => ignore

### A4. Stop behavior
- `stop()` phải idempotent (gọi 2 lần không crash).
- UI `_stop_all()` phải check recorder running trước khi stop.

**Acceptance:** Không còn exception Tkinter callback khi Stop/Stop All.

---

## B) Action Set Expansion (Your missing features)

> All actions stored in the unified “Action list” table (#, Action, Value, Label, Comment).

### B1. WAIT Actions (must-have)
Implement these action types:

1) `WaitTime(ms, variance_ms?)`
2) `WaitPixelColor(x,y,rgb,tolerance,timeout_ms,poll_ms=100)`
3) `WaitScreenChange(region?, threshold, timeout_ms, poll_ms=100)`
4) `WaitHotkey(keys, timeout_ms?)`
5) `WaitText(region, text, mode=contains|regex?, timeout_ms)`  *(OCR-based, see Image/OCR section)*
6) `WaitFile(path, mode=exists|changed|deleted, timeout_ms, poll_ms=250)`

**Notes:**
- Wait poll defaults 100ms for pixel/screen change; file can be 250ms to reduce IO.
- Wait actions must support early success (return before timeout).

### B2. IMAGE Actions (must-have)
1) `FindImage(template, region?, threshold, timeout_ms?, output_var?)`
2) `CaptureImage(region?, save_path?, copy_clipboard?, output_var?)`

**Implementation constraints:**
- Capture uses BetterCam→DXCam→mss (same pipeline).
- FindImage uses OpenCV template matching (cv2.matchTemplate) with threshold; region optional.
- OutputVar stores match result: `{x,y,confidence}` in variables.

### B3. WHEEL Action (improve config)
Action: `Wheel(x,y, direction, amount, speed?)`
- direction: up/down
- amount: integer steps (or delta)
- bind x,y (client coords)
- speed: optional delay between wheel ticks

### B4. REPEAT / FLOW CONTROL (must-have)
1) `Repeat(count: int=1, infinite: bool=false, max_iterations_guard: int)`  
   - Supports repeating:
     - “next action range” (block) OR label-based loop.
   - UI: choose repeat mode:
     - Repeat N times
     - Repeat infinite (guard by MaxIterations)

2) `Label(name)`  
   - Just a marker row with `Label` column filled.

3) `Goto(label, condition_expr?)`  
   - UI: dropdown list of existing labels.
   - Condition expr evaluated by safe evaluator (no raw eval).

4) `EmbedMacro(file_path, inline_mode=inline|call, params?)`  
   - “Embed macro files”: load another action JSON and execute:
     - inline: expand actions into current runtime stack
     - call: execute then return

**Safety:**
- Maintain global `MaxIterations` across embedded execution to prevent infinite recursion.

---

## C) Capture UX Requirements (XY + Region) — No popup, Hide UI

### C1. Capture Position (x,y)
Requirement:
- Khi user bấm “Capture XY”:
  - Hide/minimize tool UI immediately (no messagebox).
  - Show crosshair cursor.
  - User click vào emulator window -> capture position.
  - Restore tool UI and fill x,y into fields.
- Must capture **client coords** for target hwnd.

### C2. Capture Region (Snipping-tool style)
Requirement:
- Snipping overlay window (topmost, transparent):
  - click-drag to draw rectangle
  - show live rectangle border + size
  - release mouse => return (x1,y1,x2,y2) client coords
- No modal messageboxes during capture.
- Works even when emulator is behind? (at least must work when emulator is visible).

### C3. Library strategy (no-bloat, practical)
- Use WinAPI + tkinter overlay (Toplevel fullscreen transparent) for region select (works reliably).
- Use WinAPI hooks to capture click for XY (or overlay crosshair).
- Do not rely on heavy external GUI frameworks.

---

## D) Execution Engine Requirements (Wait/Image/Flow)

### D1. Capture caching policy refinement
- Default cache TTL = 1.0s.
- For WaitPixelColor / WaitScreenChange / FindImage polling:
  - force_refresh each poll OR TTL=0.1s.
- Must be per-worker thread-safe.

### D2. Variables and outputs
- FindImage/CaptureImage store output into variables if output_var is set.
- Goto/Condition can reference variables.
- Repeat and EmbedMacro must isolate local vars optionally, but commit whitelisted outputs.

### D3. Safe expression evaluator (no raw eval)
- Replace python `eval` in:
  - condition_expr
  - goto condition
  - repeat until condition (if used)
- Must support at least:
  - boolean ops: and/or/not
  - comparisons
  - dict access for variables

---

## E) UI Changes (Integrate all into existing UI)

### E1. Table columns (LOCKED)
Right table columns:
- `# | Action | Value | Label | Comment`

### E2. Add Action button
Button “+ Thêm” opens “Add Action” dialog (like your screenshot).
Dialog supports dynamic config for:
- Wait (all variants)
- Image (find/capture)
- Wheel
- Repeat
- Goto/Label
- EmbedMacro
- Existing Click/KeyPress/Text/HotKey

### E3. Label management
- When user adds a Label action: add to label registry.
- Goto dropdown reads from registry (auto-refresh).

---

## F) Debug + Test + Auto Cleanup (Your requirement)

### F1. Debug mode (runtime)
Add a toggle “Debug”:
- When enabled:
  - log each action start/end + duration
  - if Wait/Image fails: optionally dump a screenshot of the region
  - store debug artifacts in `./debug_runs/<timestamp>/...`

### F2. Test scripts (automated)
Add a `tests/` or `debug/` runner that can:
- Run action list against a mock capture provider (static images) to validate:
  - WaitPixelColor
  - ScreenChange detection
  - FindImage matching threshold logic
- Run coordinate conversion tests (client<->screen) using synthetic rect.

### F3. Auto cleanup policy (LOCKED)
- Debug artifacts auto-delete:
  - on app exit, OR
  - keep last N runs (e.g. 3), delete older
- Tests should not leave files in repo root.

**Acceptance:** Sau khi chạy debug/test, không để “rác” tràn lan; chỉ giữ theo policy.

---

## G) Implementation Order (Do in this exact order)

1) Fix Recorder crash via `IRecorderHook` + filtering (remove `set_target_window` dependency).
2) Implement capture UX (XY + Region) without messagebox; hide UI while capturing.
3) Implement Wait actions: Time, PixelColor, ScreenChange, Hotkey, File.
4) Implement Image actions: CaptureImage + FindImage (OpenCV).
5) Implement Flow: Label, Goto, Repeat, EmbedMacro.
6) Integrate UI “Add Action” dialog for all types + table column replacement.
7) Add Debug/Test + cleanup.

---

## H) Acceptance Checklist

- [ ] Record works; no AttributeError; Stop/Stop All safe.
- [ ] Capture XY/Region works silently (no popup), returns correct client coords.
- [ ] Wait supports: pixel color, screen change, hotkey, text (OCR), file.
- [ ] Image supports: find image, capture image (screenshot region).
- [ ] Wheel supports direction + amount + (x,y).
- [ ] Repeat supports finite & infinite (guarded).
- [ ] Goto supports label selection.
- [ ] EmbedMacro loads and executes other macro/action files.
- [ ] Debug artifacts are created only in debug mode and cleaned by policy.

---