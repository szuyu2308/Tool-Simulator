// Thực thi toàn bộ lệnh dưới đây. Không hỏi lại, không confirm, implement full đúng thứ tự và nguyên tắc đã nêu.
// Tận dụng tối đa giao diện hiện có (2 panel trái-phải, nút Start/Stop, table Worker, table Command).

Ra lệnh integrate vào UI hiện tại (tận dụng 100% cái sẵn có)

UI Integration vào giao diện hiện tại

Giữ nguyên layout chính:
Trái: Quản lý Worker (table: ID | Name | Worker | Status)
Phải: Danh sách Command
Top: Button Start / Stop

Nâng cấp table Worker (trái):
Thêm cột Actions: icon Play/Pause/Stop riêng từng Worker
Giữ nút Set Worker / Check / Xóa
Hỗ trợ multi-select + checkbox

Nâng cấp table Command (phải):
Columns: STT | Name | Type (text/icon) | Summary (ngắn gọn params) | Actions (Edit | Delete | Up | Down)
Giữ nút “+ Thêm” và “Xóa” hiện có
Sau này nâng lên TreeView khi có nested

Implement CommandEditor Modal (chính là phần quan trọng nhất cần thêm ngay):
Khi click “+ Thêm” hoặc Edit row → mở modal mới title "Command Editor"
Layout modal:
Top: Label + TextBox Name (required, validate unique)
Dropdown CommandType (9 loại đầy đủ)
Panel dynamic config (clear và render mới khi đổi Type)
Checkbox Enabled
Bottom: OK | Cancel


Dynamic form fields cơ bản (implement tuần tự):Tất cả type đều có Name + Enabled.
Click:
Dropdown ButtonType
Number X, Y
Button "Capture Position" → minimize app, capture click trên LDPlayer → fill X,Y
Slider Humanize delay

CropImage:
Button "Capture Region" → kéo chuột chọn vùng trên LDPlayer → fill X1,Y1,X2,Y2
ColorPicker Target Color
Slider Tolerance
TextBox Output Variable

KeyPress:
TextBox Key (autocomplete common keys)
Number Repeat

Text:
TextArea Content
Radio Paste / Humanize
Slider Speed (nếu humanize)

Wait:
Radio Timeout / Pixel Color
Nếu Timeout: Number seconds
Nếu Pixel: Capture Position + ColorPicker + Tolerance

Các type phức tạp (Repeat, Condition, Goto) implement sau khi core ổn.
Sau OK modal:
Validate required fields
Tạo Command object tương ứng
Thêm/sửa vào danh sách → refresh table row + Summary

Thêm global buttons (toolbar trên hoặc dưới table Command):
Save Script (JSON)
Load Script (JSON)
Clear All

Connect Run:
Nút Start → serialize Script → gửi cho selected Worker(s) → Start()
Show real-time log console (dưới cùng hoặc tab riêng)


Thứ tự code ngay:

CommandEditor Modal + dynamic form cho Click, KeyPress, Text
Table Command nâng cấp cột Type + Summary
Connect Thêm/Edit/Delete
Capture Position/Region cho Click & Crop
Save/Load JSON
Connect Start Worker