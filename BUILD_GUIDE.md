# Build & Installer Guide

## 🎯 BUILD CÓ INSTALLER - HƯỚNG DẪN ĐẦY ĐỦ

### ✅ Checklist trước khi build

**Phải có:**
- [x] Python đã cài (đã có)
- [x] File `icon.ico` trong thư mục gốc (đã có)
- [ ] **Inno Setup 6.x** - TẢI TẠI: https://jrsoftware.org/isdl.php
- [ ] **Tắt Windows Defender Real-time Protection** (tạm thời)

**Kiểm tra settings:**
- Mở `build.bat`
- Tìm dòng 24: `set DEBUG_MODE=0` (0 = ẩn console, 1 = hiện console debug)

---

## 🚀 CÁCH CHẠY

### Chạy 1 lệnh duy nhất - Có installer luôn:

```bash
build_installer.bat
```

**Script này tự động:**
1. ✅ Build exe với Nuitka → `dist\AutoTool.dist\AutoTool.exe`
2. ✅ Tạo installer với Inno Setup → `installer_output\AutoTool_Setup_v1.0.0.exe`

---

## 📦 OUTPUT SAU KHI BUILD

```
s:\Tools_LDplayer\
├── dist\
│   └── AutoTool.dist\          ← Thư mục app standalone
│       ├── AutoTool.exe        ← File chạy chính (có thể bị Defender chặn)
│       └── *.dll, *.pyd ...    ← Dependencies
│
└── installer_output\
    └── AutoTool_Setup_v1.0.0.exe  ← INSTALLER PHÁT HÀNH (file này gửi cho user)
```

---

## 🛡️ NÊU GẶP: "Virus detected" / File bị xóa

**⚠️ Đây là FALSE-POSITIVE phổ biến!** `Trojan:Win32/Wacatac.C!ml` là detection sai.

### ✅ Xác nhận app an toàn:
- Code Python sạch 100% (chỉ là Tkinter GUI)
- Không có: exec, eval, subprocess độc hại, tải file từ internet
- Nuitka compile Python → C nên Defender nhầm là malware obfuscated

### 🔓 Allow file ngay (cho máy dev):

#### Cách 1: Qua Protection History
1. Mở Windows Security → Virus & threat protection → Protection history
2. Tìm `AutoTool.exe` → Click **Actions** → **Allow on device**

#### Cách 2: PowerShell (Recommend)
```powershell
# PowerShell as Admin
Add-MpPreference -ExclusionPath "S:\Tools_LDplayer\dist"
Add-MpPreference -ExclusionPath "S:\Tools_LDplayer\installer_output"
```

### 🚀 Giải pháp khi phát hành cho user:

1. **Ký số (Authenticode)** - HIỆU QUẢ NHẤT:
   ```bash
   # Cần chứng chỉ code signing (DigiCert, Sectigo...)
   signtool sign /a /tr http://timestamp.digicert.com /td sha256 installer_output\AutoTool_Setup_v1.0.0.exe
   ```

2. **Submit lên Microsoft** để gỡ false-positive:
   - Link: https://www.microsoft.com/en-us/wdsi/filesubmission
   - Upload file + giải thích là legitimate app
   - Microsoft sẽ review và whitelist (1-3 ngày)

3. **Hướng dẫn user** (trong README):
   ```
   ⚠️ Windows Defender có thể báo virus - đây là false-positive!
   → Click "Actions" → "Allow on device" để chạy app
   ```

### 🛠️ Trước khi build (để test dễ hơn):
```powershell
# PowerShell as Admin - Tắt Real-time protection
Set-MpPreference -DisableRealtimeMonitoring $true
Add-MpPreference -ExclusionPath "S:\Tools_LDplayer\dist"
```

### ✅ Sau khi build xong:
```powershell
# Bật lại Defender
Set-MpPreference -DisableRealtimeMonitoring $false
```

---

## 🐛 NẾU APP TẮT NGAY (DEBUG)

### Bước 1: Bật debug mode
Mở `build.bat`, dòng 24:
```bat
set DEBUG_MODE=1    :: Đổi từ 0 → 1
```

### Bước 2: Build lại (chỉ exe, không cần installer)
```bash
build.bat
```

### Bước 3: Chạy và xem lỗi
```bash
dist\AutoTool.dist\AutoTool.exe
```
Console sẽ hiện lỗi Python → Copy lỗi để fix

### Bước 4: Sau khi fix xong
Đổi lại `DEBUG_MODE=0` → Chạy `build_installer.bat`

---

## 📋 CHECKLIST PHÁT HÀNH

- [ ] Build với `DEBUG_MODE=0`
- [ ] Test `dist\AutoTool.dist\AutoTool.exe` chạy OK
- [ ] Có file installer: `installer_output\AutoTool_Setup_v1.0.0.exe`
- [ ] Test installer trên máy sạch
- [ ] (Khuyên) Ký số cho installer: `signtool sign /a AutoTool_Setup_v1.0.0.exe`
- [ ] Gửi file installer cho người dùng

---

## 🎯 TÓM TẮT NHANH

**File chạy:** `build_installer.bat`  
**Output:** `installer_output\AutoTool_Setup_v1.0.0.exe`  
**Gửi cho user:** File installer (không gửi exe rời)
- `dist\AutoTool.dist\AutoTool.exe` - App standalone
- `installer_output\AutoTool_Setup_v1.0.0.exe` - Installer

---

## ⚙️ Tuỳ chỉnh

### Sửa thông tin app (build_installer.iss)
```iss
#define MyAppName "Auto Tool"          → Tên app
#define MyAppVersion "1.0.0"           → Phiên bản
#define MyAppPublisher "Your Company"  → Tên công ty
#define MyAppURL "https://..."         → Website
```

### Tắt/bật console (build.bat)
```bat
set DEBUG_MODE=0  :: Release: ẩn console
set DEBUG_MODE=1  :: Debug: hiện console để thấy lỗi
```

---

## 🛡️ Giảm false-positive Windows Defender

### Đã làm:
✅ Dùng `--standalone` thay vì `--onefile`  
✅ Không tự sửa Defender settings  
✅ Build output sạch sẽ, dễ scan

### Nên làm thêm:
🔐 Ký số (Authenticode) cho installer → **Hiệu quả nhất**  
📤 Submit file lên Microsoft Security Intelligence nếu bị false-positive  
📋 Tạo file checksum (SHA256) để user verify

---

## 📋 Checklist phát hành

- [ ] Build với `DEBUG_MODE=0`
- [ ] Test app chạy OK không có lỗi
- [ ] Chạy `build_installer.bat`
- [ ] Test installer trên máy sạch
- [ ] (Khuyên) Ký số cho installer
- [ ] Tạo file README/hướng dẫn sử dụng
- [ ] Phát hành

---

## 🆘 Troubleshooting

### "Error 225 - virus detected"
→ Đã build standalone nên giảm được, nhưng nếu vẫn dính:
- Tạm tắt Defender khi build
- Hoặc ký số cho file

### "App tắt ngay không có lỗi"
→ Bật `DEBUG_MODE=1` để thấy console

### "Không tìm thấy Inno Setup"
→ Cài tại: https://jrsoftware.org/isdl.php

### "Thiếu DLL khi chạy"
→ Nuitka đã bundle hết, nếu vẫn thiếu: thêm plugin tương ứng
