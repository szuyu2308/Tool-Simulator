# UI Merge Spec — Remove Macro Recorder UI, Integrate Record/Play/Pause/Stop Into Existing Tool UI

**Date:** 2026-01-09  
**Target Repo:** `szuyu2308/Tool-Simulator` (Python + Tkinter)  
**Target OS:** Windows 10/11  
**Goal:** Loại bỏ “Macro Recorder Engine” UI riêng (window riêng như hình) và **tối ưu toàn bộ chức năng Record/Actions** vào UI hiện tại (2 panel trái–phải).  
**Reference UI:** ![image1](image1)

---

## 0) Scope Lock (Không làm gì ngoài scope)

- **Không tạo app mới / không tạo UI window Macro Recorder riêng**.
- **Giữ layout chính** (2 panel trái–phải) như app hiện tại.
- Nâng cấp UI và behavior theo các điểm bên dưới, dùng lại tối đa code/logic đã có (Command list, Save/Load, worker list).
- “Record” ở đây là **record hành vi người dùng thành 1 block command/script action list**, không phải xây product Macro Recorder độc lập.

---

## 1) UI Changes (LOCKED)

### 1.1 Top Toolbar: Replace Start/Stop → Record/Play/Pause/Stop
Hiện tại UI có Start/Stop (đang chạy MacroLauncher). Thay thế bằng 4 nút vận hành chính:

- **Record** (toggle)  
- **Play**
- **Pause/Resume** (toggle)
- **Stop**

**Hotkeys mặc định** (global/system-wide):
- Record toggle: `Ctrl+Shift+R`
- Play: `Ctrl+Shift+P`
- Pause/Resume: `Ctrl+Shift+Space`
- Stop: `Ctrl+Shift+S`

> Hotkeys phải hoạt động khi app không focus (system-wide). Nếu xung đột, phải show cảnh báo và cho đổi.

### 1.2 Remove Macro Recorder Window
- Loại bỏ/không tạo window “Macro Recorder Engine” riêng như hình ![image1](image1).
- Tất cả thao tác Add/Delete/Edit/Up/Down actions thực hiện trực tiếp trên panel “Danh sách Command” hiện tại.

### 1.3 Right Panel: Replace Macro Actions Table Columns
Thay bảng bên phải (đang là Command list kiểu STT/Name/Type/Summary/Actions) thành bảng “Action List” theo cột:

**New columns (LOCKED):**
1. `#`
2. `Action`
3. `Value`
4. `Label`
5. `Comment`

**Row enable/disable (“On”)**:
- Không còn cột “On” riêng.
- Thay bằng:
  - checkbox trong cột `Action` (hoặc style “Action (✓/✗)”).
  - hoặc thêm icon/toggle trên row (tuỳ khả năng Treeview Tkinter).
- Behavior: disabled action vẫn giữ trong list, bị skip khi play.

### 1.4 Keep Existing Buttons On Command Panel But Repurpose
Các button hiện có ở panel Command:
- `+ Thêm` (Add)
- `🗑 Xóa` (Delete)
- `↑` / `↓` (Up/Down)
- Save/Load

**Tất cả giữ lại**, nhưng nội dung và hành vi thay đổi:
- `+ Thêm`: mở dialog **Add Action** (UI giống bên trái trong ![image1](image1))
- `Xóa`: xóa action selected
- `Up/Down`: reorder action
- `Save/Load`: save/load “Action script” (JSON) theo format thống nhất (xem mục 4)

---

## 2) Recording Behavior (LOCKED)

### 2.1 What Record Captures
Khi user bấm **Record**, tool bắt đầu capture theo thời gian thực, tuần tự:

- Mouse:
  - click (left/right/middle/double)
  - move (OPTIONAL: chỉ record khi cần; mặc định bỏ move để script gọn)
  - drag (nếu phát hiện giữ chuột và di chuyển)
  - wheel
- Keyboard:
  - key press (bao gồm modifiers Ctrl/Alt/Shift)
  - hotkey combos
  - text input (optional: gom thành Text action nếu detect chuỗi ký tự)

- Wait:
  - Insert wait delays theo timeline giữa các event (ms)

### 2.2 Coordinate Space (LOCKED)
- Record tọa độ theo **client pixels** của target window (emulator client area).
- Cách xác định target window:
  1) Nếu user đã “Set Worker” chọn emulator instance cụ thể → record theo instance đó.
  2) Nếu chưa chọn → record yêu cầu user click chọn window target 1 lần (picker overlay đơn giản).

**Rule:** Record phải bỏ qua event ngoài target window (trừ hotkeys điều khiển).

### 2.3 Record Output Integration: “Record returns into 1 command in command list”
Sau khi Stop Record:
- Toàn bộ actions vừa record được **đóng gói** thành **1 item** trong danh sách hiện có.
- Item này có thể là:
  - một `RecordedActionBlockCommand` (đề xuất) chứa `actions: List[Action]`
  - hoặc map sang `Script.sequence` dạng commands tương ứng (Click/KeyPress/Text/Wait...) theo model hiện có.

**LOCKED requirement:** “Record sẽ lưu hết chức năng hiện có của app (Trả về vào 1 command trong danh sách command)”
- Nghĩa là: Record không tạo nhiều “command rows” rời rạc, mà tạo **một block** đại diện.

### 2.4 Smart Defaults (để tool usable)
- Mouse move:
  - default OFF (đỡ rác)
  - nếu bật: có threshold ignore jitter (>= 3px)
- Text:
  - nếu detect nhiều key printable liên tục: gom thành Text action
- Wait:
  - tự động insert `Wait(ms=delta)` giữa các event

---

## 3) Playback Behavior (LOCKED)

### 3.1 Play
- Play sẽ thực thi:
  - Nếu đang chọn một “RecordedActionBlockCommand” → chạy block đó
  - Hoặc chạy toàn bộ action list (tuỳ “mode” bạn chọn; mặc định chạy toàn list)

- Play target:
  - Selected Worker(s) ở panel trái.
  - Mỗi worker chạy riêng thread.

### 3.2 Pause/Resume
- Pause dừng execution loop nhưng không mất state.
- Resume tiếp tục từ action hiện tại.
- UI phải phản ánh trạng thái (status text + disable/enable buttons hợp lý).

### 3.3 Stop
- Stop hủy run ngay lập tức.
- Reset current pointer về đầu.

### 3.4 Error Handling
Per action:
- Nếu fail: apply OnFail hoặc global setting:
  - Skip / Stop / (optional) Goto label
- Log đầy đủ.

---

## 4) Action Model (LOCKED) + JSON Save/Load

### 4.1 Action Schema (new)
Define lightweight action objects (không cần full Macro Recorder product):

Common fields:
- `id: uuid`
- `enabled: bool`
- `action: string` (e.g. CLICK, WAIT, KEY_PRESS, HOTKEY, WHEEL, DRAG, TEXT)
- `value: object|string|number` (tuỳ action)
- `label: string?`
- `comment: string?`

Examples:
- CLICK:
  - `value = {"button":"left","x":123,"y":456}`
- WAIT:
  - `value = {"ms": 250}`
- KEY_PRESS:
  - `value = {"key":"A","repeat":1}`
- HOTKEY:
  - `value = {"keys":["Ctrl","V"],"order":"simultaneous"}`
- WHEEL:
  - `value = {"delta": -120, "x":123,"y":456}`

### 4.2 File format
- Save/Load JSON file stores:
  - `version`
  - `target_window_match` (optional metadata)
  - `actions: []`

### 4.3 Backward compatibility
- Nếu đang có Script commands JSON (current `Script.to_dict()`):
  - Tool có thể giữ “Save Script” riêng, hoặc unify sau.
- Milestone 1: ưu tiên giữ hiện trạng Save/Load Script nhưng bổ sung Save/Load Actions.

---

## 5) “Add Action” Dialog (Replace Macro Recorder Add UI into existing “+ Thêm”)

### 5.1 Dialog layout (match ![image1](image1))
Title: `Add Action`

Fields:
- Dropdown `Type` (Action type)
- Panel `Configuration` (dynamic)
- Checkbox `Enabled`
- Textbox `Comment`
- Buttons: Save / Cancel

### 5.2 Action Types supported in Milestone order
**Milestone 1 (core):**
- Click
- Wait (Time)
- Key Press
- HotKey
- Wheel

**Milestone 2:**
- Drag
- Wait Window (title contains, timeout)
- Wait Pixel (x,y,color,tolerance,timeout)
- Text (paste/humanize)

**Milestone 3 (vision):**
- Wait Image / Search Image / OCR (optional, only if vision pipeline ready)

### 5.3 Mapping to table columns
- `Action`: type name (kèm enabled state)
- `Value`: short summary string (render from config)
- `Label`: optional label for jumps/sections (future)
- `Comment`: free text

---

## 6) Library Choices (Strong + Practical, Windows 10/11)

### 6.1 Capture (playback/vision)
- BetterCam primary (as documented in official sources)[[1]](https://github.com/RootKit-Org/BetterCam)[[2]](https://github.com/RootKit-Org/BetterCam/blob/main/README.md)[[3]](https://pypi.org/project/bettercam/)
- DXCam fallback
- mss final fallback

### 6.2 Input (playback)
- WinAPI SendInput for mouse/keyboard (stable)
- Optional PostMessage (toggle)
- ADB fallback for text/keyevent only

### 6.3 Recording hooks (global)
- Must use a Windows global mouse/keyboard hook library.
- Implement behind an abstraction `IRecorderHook` so swapping libs does not affect engine/UI.
- Requirements:
  - global hotkeys
  - capture mouse click/wheel/drag
  - capture key down/up + modifiers
  - high event rate without freezing Tkinter UI

> Exact library selection should be validated by a spike/prototype because hook stability varies by environment. This spec requires abstraction to avoid lock-in.

---

## 7) Integration Plan (Implementation Order)

### Step 1 — UI swap top bar
- Replace Start/Stop with Record/Play/Pause/Stop
- Wire button states + hotkeys

### Step 2 — Replace right table to Action list columns
- Update Treeview columns to `#, Action, Value, Label, Comment`
- Implement Add/Delete/Up/Down for actions

### Step 3 — Add Action Dialog
- Implement dynamic form for Milestone 1 actions
- Create action objects and refresh table

### Step 4 — Record pipeline
- Implement record start/stop with global hooks
- Convert events to actions:
  - click/wheel/key/hotkey + wait(ms)
- On stop: create **one block command** (or one action list object) and insert into command list OR directly into action list (choose one mode; must satisfy requirement “return into 1 command”)

### Step 5 — Playback engine
- Execute selected actions on selected workers
- Pause/Resume/Stop
- Logging console in UI

---

## 8) Acceptance Criteria (Must pass)

1. App không còn mở “Macro Recorder Engine” window như ![image1](image1).
2. Toolbar top có 4 nút: Record/Play/Pause/Stop; hotkeys hoạt động global.
3. “+ Thêm” mở Add Action dialog với UI tương tự ![image1](image1), thêm action vào bảng.
4. Bảng actions hiển thị đúng 5 cột: `#, Action, Value, Label, Comment`.
5. Record -> Stop tạo ra 1 block tương ứng trong danh sách (đúng yêu cầu “trả về 1 command”).
6. Play chạy được trên selected worker(s), pause/resume/stop hoạt động.
7. Không phá layout 2 panel hiện tại.

---