# 🎮 Macro Auto - Automation Tool for LDPlayer

**Công cụ tự động hóa macro cho giả lập LDPlayer với ADB Tap và Image Recognition**

---

## ✨ Features

- 🎯 **Multi-Worker Support** - Điều khiển nhiều giả lập cùng lúc
- 🖼️ **Image Recognition** - Tìm hình ảnh trên màn hình với OpenCV
- 📱 **ADB Control** - Tap, swipe sử dụng ADB/uiautomator2
- 💾 **Macro System** - Load/Save macro với embedded images
- 🎨 **Modern UI** - Dark theme với Tkinter
- 🔄 **Goto Logic** - Flow control với labels và conditional jumps

---

## 📋 Requirements

- **Python 3.10+** (khuyến nghị 3.10 hoặc 3.11)
- **Windows 10/11** (64-bit)
- **LDPlayer 9** hoặc **LDPlayer 4.0**
- **ADB Debug enabled** trong giả lập

---

## 🚀 Quick Start

### 1. Clone Repository
```bash
git clone <repository-url>
cd Tools_LDplayer
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Enable ADB in LDPlayer
1. Mở LDPlayer
2. Settings → Khác → Debug ADB → **Kết Nối Local**
3. Restart giả lập

### 4. Run Application
```bash
python app.py
```

---

## 🔨 Building EXE

Có 3 cách build tùy theo nhu cầu:

### Option 1: PyInstaller Debug (Nhanh nhất - cho testing)
```bash
build_pyinstaller_debug.bat
```
- ✅ Build nhanh (~2-3 phút)
- ✅ Console hiển thị (dễ debug)
- ✅ File size: ~50-60 MB
- ❌ Không tối ưu

### Option 2: PyInstaller Release (Cho end-users)
```bash
build_pyinstaller_release.bat
```
- ✅ Build nhanh (~2-3 phút)
- ✅ Ẩn console (clean UI)
- ✅ File size: ~50-60 MB
- ✅ Đã tối ưu cơ bản

### Option 3: Nuitka Production (Tốt nhất - cho release)
```bash
build_nuitka_production.bat
```
- ⏱️ Build chậm (~5-15 phút - lần đầu lâu hơn)
- ✅ Ẩn console
- ✅ File size: ~40-50 MB
- ✅ Tối ưu tốt nhất
- ✅ Mã hóa bytecode
- ⚠️ Có thể bị Windows Defender chặn (thêm exclusion)

---

## 📂 Project Structure

```
Tools_LDplayer/
├── app.py                          # Entry point
├── requirements.txt                # Dependencies
├── icon.ico                        # App icon
├── MacroAuto.manifest              # DPI awareness
│
├── build_pyinstaller_debug.bat     # Debug build
├── build_pyinstaller_release.bat   # Release build
├── build_nuitka_production.bat     # Production build
│
├── core/                           # Core modules
│   ├── action_engine.py
│   ├── adb_manager.py
│   ├── wait_actions.py
│   └── ...
│
├── ui/                             # UI modules
│   └── main_ui.py
│
├── data/                           # Runtime data
│   ├── macros/                     # Saved macros
│   └── app_config.json
│
├── files/                          # Binaries
│   ├── adb.exe                     # (auto-copied)
│   └── minitouch-*                 # (optional)
│
└── dist/                          # Build output
    └── MacroAuto.exe
```

---

## 🎯 Usage

### Basic Workflow
1. **Check Giả Lập** - Detect emulators
2. **Set Worker** - Assign emulators to workers
3. **Load Macro** - Load .macro files
4. **Play All** - Run on all workers

### Creating Macros
1. Click **FIND_IMAGE** → Crop screen
2. Configure threshold, retry, goto logic
3. Add mouse action (Left click, etc.)
4. **Save** macro

### Multi-File Load
- Select multiple files (Ctrl+Click or Shift+Click)
- Click **Load**
- All files appended to action list

---

## 🛠️ Troubleshooting

### "No ADB devices found"
- Enable ADB Debug in LDPlayer
- Restart emulator
- Check `adb devices` in cmd

### "Images not found after ungroup"
- Fixed in latest version
- Re-save macro to update format

### Build fails with "Error 225"
- Windows Defender blocking Nuitka
- Add project folder to exclusion list
- Or use PyInstaller instead

---

## 📝 Dependencies

All dependencies auto-installed via requirements.txt:
- **pywin32** - Windows API
- **Pillow** - Image processing
- **opencv-python** - Computer vision
- **numpy** - Numerical operations
- **mss/dxcam** - Screen capture
- **pynput** - Input simulation
- **uiautomator2** - ADB automation
- **adbutils** - ADB client

---

## 📄 License

Copyright 2026 Szuyu. All rights reserved.

---

## 🤝 Support

Nếu gặp vấn đề, check:
1. Python version (3.10+ required)
2. All dependencies installed (`pip install -r requirements.txt`)
3. ADB enabled trong giả lập
4. Windows Defender không block

---

**Built with ❤️ using Python + Tkinter + OpenCV + ADB**
