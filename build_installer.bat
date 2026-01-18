@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
cd /d %~dp0

echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║     🚀 MACRO AUTO - BUILD EXE + INSTALLER (Full Workflow)    ║
echo ║           Nuitka Onefile → Inno Setup Installer              ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.

:: ============================================================
:: STEP 0: Kiểm tra Inno Setup trước
:: ============================================================
echo.
echo ═══════════════════════════════════════════════════════════════
echo [0/3] 🔍 KIỂM TRA INNO SETUP
echo ═══════════════════════════════════════════════════════════════
echo.

:: Tìm đường dẫn Inno Setup
set "ISCC_PATH="

if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" (
    set "ISCC_PATH=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
    goto :inno_found
)

if exist "C:\Program Files\Inno Setup 6\ISCC.exe" (
    set "ISCC_PATH=C:\Program Files\Inno Setup 6\ISCC.exe"
    goto :inno_found
)

:: Không tìm thấy
echo ❌ KHÔNG TÌM THẤY INNO SETUP!
echo.
echo 💡 Cài đặt Inno Setup trước khi tiếp tục:
echo    1. Tải tại: https://jrsoftware.org/isdl.php
echo    2. Cài phiên bản 6.x (Unicode)
echo    3. Để nguyên đường dẫn mặc định khi cài
echo    4. Chạy lại script này
echo.
pause
goto :error

:inno_found
echo     ✅ Tìm thấy: %ISCC_PATH%
echo.

:: ============================================================
:: STEP 1: Thêm Windows Defender Exclusion
:: ============================================================
echo ═══════════════════════════════════════════════════════════════
echo [1/3] 🛡️  THÊM WINDOWS DEFENDER EXCLUSION
echo ═══════════════════════════════════════════════════════════════
echo.

powershell -Command "Add-MpPreference -ExclusionPath '%CD%\dist' -ErrorAction SilentlyContinue" 2>nul
powershell -Command "Add-MpPreference -ExclusionPath '%CD%\installer_output' -ErrorAction SilentlyContinue" 2>nul

echo     ✅ Đã thêm exclusion cho dist\ và installer_output\
echo     💡 Giúp tránh Defender chặn file khi build
echo.

:: ============================================================
:: STEP 2: BUILD EXE với Nuitka
:: ============================================================
echo.
echo ═══════════════════════════════════════════════════════════════
echo [2/3] 🔨 BUILD EXE với Nuitka
echo ═══════════════════════════════════════════════════════════════
echo.

call build.bat
if errorlevel 1 (
    echo.
    echo ❌ Build exe thất bại! Dừng lại.
    goto :error
)

echo.
echo ✅ Build exe thành công!
echo.

:: ============================================================
:: STEP 3: Tạo INSTALLER với Inno Setup
:: ============================================================
echo.
echo ═══════════════════════════════════════════════════════════════
echo [3/3] 📦 TẠO INSTALLER với Inno Setup
echo ═══════════════════════════════════════════════════════════════
echo.
echo     🔨 Đang compile installer...
echo.

"%ISCC_PATH%" build_installer.iss

if errorlevel 1 (
    echo.
    echo ❌ Tạo installer thất bại!
    goto :error
)

:: ============================================================
:: DONE
:: ============================================================
echo.
echo ══════════════════════════════════════════════════════════════
echo ✅ HOÀN TẤT TOÀN BỘ!
echo ══════════════════════════════════════════════════════════════
echo.
echo 📦 Output files:
echo    • EXE:       dist\AutoTool.exe (onefile - 1 file duy nhất!)
echo    • Installer: installer_output\MacroAuto_Setup_v1.0.0.exe
echo.
echo 🚀 Ưu điểm:
echo    • Nuitka Onefile: Chỉ 1 file exe duy nhất
echo    • Code compiled → C (bảo mật cao, khó decompile)
echo    • Installer: Chuyên nghiệp, dễ phát hành
echo.
echo 💡 Bước tiếp theo:
echo    1. Test installer: installer_output\MacroAuto_Setup_v1.0.0.exe
echo    2. Ký số (khuyên dùng): signtool sign /a MacroAuto_Setup_v1.0.0.exe
echo    3. Phát hành cho người dùng
echo.

goto :end

:error
echo.
echo ══════════════════════════════════════════════════════════════
echo ❌ CÓ LỖI XẢY RA!
echo ══════════════════════════════════════════════════════════════

:end
echo.
pause
