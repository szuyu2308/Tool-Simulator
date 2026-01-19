# 📋 HƯỚNG DẪN SỬ DỤNG BUILD SCRIPTS

## 📂 Tổng quan các file .bat

| File | Mục đích | Builder | Console | Khi nào dùng |
|------|----------|---------|---------|--------------|
| **dev_run_python.bat** | Chạy trực tiếp bằng Python | Python | ✅ | Development/testing code |
| **build_pyinstaller_debug.bat** | Build nhanh để test | PyInstaller | ✅ | Test nhanh (3-5 phút) |
| **build_nuitka_production.bat** | Build production tối ưu | Nuitka | ❌ | Release cuối cùng (10-15 phút) |
| **build_installer_setup.bat** | Build + tạo installer | Nuitka + Inno | ❌ | Phân phối cho người dùng |

---

## 🚀 Chi tiết từng script

### 1. **dev_run_python.bat** - Development Mode
```
✅ Chạy trực tiếp Python (không build exe)
⚡ Siêu nhanh - khởi động ngay lập tức
🐛 Debug trực tiếp trong code
📦 Cần Python đã cài đặt
```

**Khi nào dùng:**
- Đang viết code, test feature
- Debug lỗi
- Thay đổi code liên tục

**Lệnh:**
```bash
.\dev_run_python.bat
```

---

### 2. **build_pyinstaller_debug.bat** - Fast Testing Build
```
✅ Build nhanh với PyInstaller (3-5 phút)
🐛 Console window hiện (xem log/debug)
📦 Single exe file
⚡ Dùng để test build trước khi release
```

**Khi nào dùng:**
- Test xem build có lỗi không
- Kiểm tra dependencies đầy đủ chưa
- Cần build nhanh để gửi cho người khác test

**Đặc điểm:**
- ✅ Console window hiện ra (xem log)
- ✅ Debug mode enabled
- ✅ File logging enabled
- ⚡ Build nhanh hơn Nuitka ~70%
- 📊 Size lớn hơn Nuitka ~20-30%

**Lệnh:**
```bash
.\build_pyinstaller_debug.bat
```

**Output:**
```
dist\MacroAuto.exe (40-50 MB)
```

---

### 3. **build_nuitka_production.bat** - Production Release
```
✅ Build tối ưu với Nuitka (10-15 phút)
🔒 Mã hóa bytecode (bảo mật cao)
⚡ Performance tốt nhất (~10-20% nhanh hơn PyInstaller)
📦 File size nhỏ hơn
❌ Ẩn console (cho end-user)
```

**Khi nào dùng:**
- Build bản release cuối cùng
- Cần performance tốt nhất
- Muốn bảo mật code (compile to C)
- Gửi cho khách hàng/end-user

**Đặc điểm:**
- ❌ Console ẩn (clean UI)
- 📦 Release mode
- 🔒 Bytecode encrypted
- ⚡ Startup nhanh (onefile mode)
- 📊 Size nhỏ hơn PyInstaller ~20-30%

**Lệnh:**
```bash
.\build_nuitka_production.bat
```

**Output:**
```
dist\MacroAuto.exe (30-40 MB)
```

---

### 4. **build_installer_setup.bat** - Full Distribution Package
```
✅ Tự động build Nuitka + tạo installer
📦 Windows Installer (.exe) với Inno Setup
🎯 Dành cho phân phối end-user
📋 Có uninstaller, Start Menu shortcuts
```

**Khi nào dùng:**
- Phân phối cho người dùng cuối
- Cần installer chuyên nghiệp
- Tạo Start Menu shortcuts
- Có uninstall program

**Yêu cầu:**
- Inno Setup 6.x đã cài đặt
- Link: https://jrsoftware.org/isdl.php

**Đặc điểm:**
- ✅ Tự động chạy build_nuitka_production.bat
- ✅ Tạo installer với Inno Setup
- ✅ Start Menu shortcuts
- ✅ Uninstaller
- ✅ Custom installation path
- ✅ File associations (nếu có)

**Lệnh:**
```bash
.\build_installer_setup.bat
```

**Output:**
```
dist\MacroAutoSetup.exe (installer)
```

---

## 🔄 Workflow khuyến nghị

### Development Phase (Đang code)
```
1. Edit code
2. .\dev_run_python.bat (test ngay)
3. Lặp lại bước 1-2
```

### Pre-Release Testing
```
1. Code đã ổn định
2. .\build_pyinstaller_debug.bat (test build nhanh)
3. Chạy exe, test trên máy khác
4. Fix bugs nếu có → quay lại bước 1
```

### Final Release
```
1. Code đã hoàn thiện
2. .\build_nuitka_production.bat (build tối ưu)
3. Test kỹ exe
4. .\build_installer_setup.bat (tạo installer)
5. Phân phối MacroAutoSetup.exe
```

---

## ⚙️ So sánh chi tiết

| Tiêu chí | PyInstaller Debug | Nuitka Production |
|----------|------------------|------------------|
| **Build time** | 3-5 phút | 10-15 phút |
| **File size** | 40-50 MB | 30-40 MB |
| **Performance** | Standard | +10-20% faster |
| **Security** | Python bytecode | Compiled to C |
| **Console** | ✅ Hiện | ❌ Ẩn |
| **Debug** | ✅ Easy | ❌ Harder |
| **Startup** | ~2-3s | ~1-2s |
| **Dùng cho** | Testing | Production |

---

## 📦 Packages được include (tất cả builds)

Tất cả build scripts đều include đầy đủ:

### GUI & Graphics
- ✅ Tkinter (GUI framework)
- ✅ PIL/Pillow (image processing)
- ✅ OpenCV (computer vision)

### System & Windows API
- ✅ PyWin32 (win32gui, win32ui, win32con, etc.)
- ✅ pynput (keyboard/mouse simulation)
- ✅ psutil (system info)

### Screen Capture
- ✅ MSS (fast screenshot)
- ✅ DXCam (DirectX capture)

### Utilities
- ✅ numpy (numerical computing)
- ✅ pyperclip (clipboard)
- ✅ comtypes (COM objects)

### App Features
- ✅ DPI awareness (per-monitor v2)
- ✅ Taskbar icon support
- ✅ Window icon support
- ✅ Windows 10/11 compatibility

---

## 🛠️ Troubleshooting

### Build failed / Module not found
```bash
pip install -r requirements.txt
pip install --upgrade nuitka pyinstaller
```

### Windows Defender blocks (Error 225)
```
1. Open Windows Security
2. Virus & threat protection settings
3. Exclusions → Add folder
4. Thêm thư mục S:\Tools_LDplayer
5. Build lại
```

### Icon không hiện
- Kiểm tra file `icon.ico` tồn tại
- Build scripts tự tạo icon nếu thiếu

### Nuitka quá chậm
- Dùng `build_pyinstaller_debug.bat` để test nhanh
- Chỉ dùng Nuitka cho bản release cuối

---

## 📝 Notes

1. **Đồng bộ packages:** Tất cả scripts đã được đồng bộ với cùng packages và options
2. **Icon support:** Tất cả builds đều support icon (window + taskbar)
3. **DPI awareness:** Xử lý trong code (app.py), không cần manifest file
4. **Config files:** Scripts tự động tạo `data\app_config.json` phù hợp với mode

---

## 🎯 Quick Reference

**Tôi muốn...**
- ✅ Test code nhanh → `dev_run_python.bat`
- ✅ Test build có lỗi không → `build_pyinstaller_debug.bat`
- ✅ Build bản release → `build_nuitka_production.bat`
- ✅ Tạo installer → `build_installer_setup.bat`

**Lưu ý:**
- File outputs luôn ở folder `dist\`
- Logs ở folder `logs\` (nếu có)
- Build scripts tự động tạo folders cần thiết
