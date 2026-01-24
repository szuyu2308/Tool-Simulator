# 🎮 Macro Auto - LDPlayer Automation Framework

![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)
![Platform](https://img.shields.io/badge/Platform-Windows%2010%2F11-lightgrey.svg)
![License](https://img.shields.io/badge/License-Proprietary-red.svg)
![Status](https://img.shields.io/badge/Status-Active-success.svg)

**Macro Auto** là framework tự động hóa hiệu suất cao dành cho giả lập LDPlayer, được thiết kế cho các tác vụ phức tạp đòi hỏi xử lý ảnh thời gian thực (Computer Vision) và điều khiển ADB đa luồng.

---

## 📑 Mục Lục
- [Features](#-features)
- [Project Architecture](#-project-architecture)
- [Prerequisites](#-prerequisites)
- [Installation & Setup](#-installation--setup)
- [Development Guide](#-development-guide)
- [Troubleshooting](#-troubleshooting)
- [Maintainers](#-maintainers)

---

## ✨ Features

### Core Automation
- **Multi-threaded Worker System**: Mỗi giả lập được quản lý bởi một `Worker` thread riêng biệt, đảm bảo hiệu năng tối đa và không chặn (non-blocking) UI.
- **Hybrid Control**: Kết hợp giữa **ADB Shell** (gửi lệnh tap/swipe ngầm) và **Win32 API** (điều khiển cửa sổ) để tối ưu độ chính xác.
- **Smart Wait**: Cơ chế chờ thông minh dựa trên màu điểm ảnh (Pixel Color), thay đổi màn hình (Screen Change), hoặc tìm kiếm ảnh (Template Matching).

### Visual Intelligence
- **OpenCV Integration**: Sử dụng thuật toán Template Matching đa tầng (Multi-scale) để tìm hình ảnh với độ chính xác cao.
- **High-Performance Capture**: Tích hợp `dxcam` (DirectX) và `mss` để chụp màn hình với độ trễ thấp (<10ms).

### Macro Engine
- **Logic Flow**: Hỗ trợ đầy đủ `Label`, `Goto`, `Loop`, `If/Else` giúp tạo các kịch bản logic phức tạp.
- **Embedded Macros**: Khả năng nhúng (gọi) các macro con, giúp tái sử dụng code và module hóa kịch bản.

---

## 📂 Project Architecture

Cấu trúc dự án tuân theo mô hình **Modular Monolith**:

```
Tools_LDplayer/
├── app.py                     # 🚀 Entry Point (Main Application)
├── core/                      # 🧠 Business Logic Layer
│   ├── action_engine.py       # Xử lý thực thi lệnh (Click, Wait, Find...)
│   ├── flow_control.py        # Điều hướng luồng (Goto, Loop, If)
│   ├── adb_manager.py         # Giao tiếp với Android Debug Bridge
│   └── worker.py              # Thread quản lý từng giả lập
├── ui/                        # 🎨 Presentation Layer (Tkinter)
│   ├── main_ui.py             # Giao diện chính
│   └── components/            # Các widget tái sử dụng
├── handlers/                  # 🔌 Message Handlers
│   └── ...                    # Xử lý sự kiện từ UI xuống Core
├── emulator/                  # 📱 Emulator Abstraction
│   └── ...                    # Wrapper cho LDPlayer instances
├── detectors/                 # 👁️ Detection Algorithms
│   └── ...                    # Logic nhận diện hình ảnh/trạng thái
├── data/                      # 💾 Persistence
│   ├── macros/                # File kịch bản .json/.macro
│   └── app_config.json        # Cấu hình ứng dụng
├── files/                     # 📦 External Binaries
│   └── adb.exe                # ADB Tool (bundled)
└── utils/                     # 🛠️ Shared Utilities
    └── logger.py              # Centralized logging
```

---

## 📋 Prerequisites

Trước khi bắt đầu, đảm bảo hệ thống đáp ứng các yêu cầu sau:

### System Requirements
- **OS**: Windows 10 hoặc Windows 11 (64-bit).
- **RAM**: Tối thiểu 8GB (Khuyến nghị 16GB nếu chạy nhiều giả lập).
- **Emulator**: LDPlayer 9.0+ (Phiên bản 64-bit ổn định nhất).

### Software Requirements
- **Python**: Phiên bản `3.10.x` hoặc `3.11.x`.
- **Visual C++ Redistributable**: Cần thiết cho `opencv` và `dxcam`.

---

## ⚡ Installation & Setup

### 1. Environment Setup
Khuyến nghị sử dụng `venv` để cách ly môi trường phát triển:

```powershell
# Tạo virtual environment
python -m venv venv

# Kích hoạt môi trường (Windows)
.\venv\Scripts\activate
```

### 2. Install Dependencies
Cài đặt các thư viện cần thiết từ `requirements.txt`:

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

> **Note**: Nếu gặp lỗi khi cài `dxcam`, hãy đảm bảo bạn đã cài Build Tools for Visual Studio.

### 3. Emulator Configuration (QUAN TRỌNG)
Để tool có thể điều khiển giả lập, bạn **phải** bật ADB Debugging:
1. Mở **LDPlayer**.
2. Settings (`⚙️`) -> **Other Settings**.
3. **ADB Debugging**: Chọn **Open Local Connection**.
4. **Root Permission**: Khuyến nghị **Enable**.
5. Save & Restart giả lập.

---

## 💻 Development Guide

### Running Locally
Khởi chạy ứng dụng ở chế độ Development:

```bash
python app.py
```

### Adding New Actions
Để thêm một Action mới vào hệ thống:
1. Định nghĩa Action Type trong `core/models.py`.
2. Thêm logic xử lý trong `core/action_engine.py`.
3. Cập nhật UI render trong `ui/main_ui.py`.

### Code Style
- Tuân thủ **PEP 8**.
- Sử dụng Type Hints cho tất cả function signature.
- Comment docstring cho các class/function phức tạp.

---

## ⚠️ Troubleshooting

### Common Issues

#### 🔴 Error: `ImportError: DLL load failed while importing cv2`
- **Nguyên nhân**: Thiếu Visual C++ Redistributable hoặc bản Windows N thiếu Media Feature Pack.
- **Khắc phục**: Cài [VC++ Redist x64](https://aka.ms/vs/17/release/vc_redist.x64.exe).

#### 🔴 Error: `No ADB devices found`
- **Nguyên nhân**: Giả lập chưa bật ADB hoặc port ADB bị chiếm.
- **Khắc phục**: 
  - Chạy `adb kill-server` rồi `adb start-server`.
  - Kiểm tra lại setting ADB trong LDPlayer.

#### 🔴 Performance Issues (Lag)
- **Nguyên nhân**: `dxcam` không được hỗ trợ hoặc GPU quá tải.
- **Khắc phục**: Chuyển sang chế độ capture `mss` trong Config hoặc giảm FPS giả lập xuống 30.

---

## 📦 Build Instructions

Hiện tại các script build (`.bat`) không có sẵn trong repository. Để đóng gói thành `.exe`:

1. Cài đặt PyInstaller: `pip install pyinstaller`
2. Chạy lệnh build thủ công:
```bash
pyinstaller --noconfirm --onedir --windowed --icon "icon.ico" --name "MacroAuto" --add-data "files;files" --add-data "data;data" app.py
```

---

## � License
Copyright © 2026 **Szuyu**. All rights reserved.
Developed for internal automation. Unauthorized distribution is prohibited.
