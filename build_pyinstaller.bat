@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
cd /d %~dp0

echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║         🔒 AUTO TOOL - BUILD EXE (PYINSTALLER)               ║
echo ║            Backup option với mã hóa AES-256                  ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.

:: ============================================================
:: CONFIGURATION  
:: ============================================================
set APP_NAME=AutoTool
set MAIN_FILE=app.py
set OUTPUT_DIR=dist
set ENCRYPTION_KEY=AutoTool2026SecretKey

:: ============================================================
:: CHECK REQUIREMENTS
:: ============================================================
echo [1/4] Kiểm tra môi trường...

python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python chưa được cài đặt!
    goto :error
)
echo     ✅ Python OK

:: Check/Install PyInstaller with encryption support
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo     📦 Đang cài đặt PyInstaller...
    pip install pyinstaller --quiet
)
pip show tinyaes >nul 2>&1
if errorlevel 1 (
    echo     📦 Đang cài đặt tinyaes (mã hóa)...
    pip install tinyaes --quiet
)
echo     ✅ PyInstaller + Encryption OK

:: ============================================================
:: CLEAN OLD BUILD
:: ============================================================
echo.
echo [2/4] Dọn dẹp build cũ...
if exist "%OUTPUT_DIR%" rmdir /s /q "%OUTPUT_DIR%" 2>nul
if exist "build" rmdir /s /q "build" 2>nul
if exist "*.spec" del /q "*.spec" 2>nul
echo     ✅ Đã dọn dẹp

:: ============================================================
:: BUILD WITH PYINSTALLER
:: ============================================================
echo.
echo [3/4] 🔨 Đang build EXE với PyInstaller...
echo     🔒 Mã hóa bytecode với key 16 ký tự
echo.

pyinstaller ^
    --noconfirm ^
    --onefile ^
    --console ^
    --name=%APP_NAME% ^
    --distpath=%OUTPUT_DIR% ^
    --workpath=build ^
    --key=%ENCRYPTION_KEY:~0,16% ^
    --add-data "data;data" ^
    --add-data "profiles;profiles" ^
    --add-data "handlers;handlers" ^
    --add-data "detectors;detectors" ^
    --add-data "core;core" ^
    --add-data "emulator;emulator" ^
    --add-data "ui;ui" ^
    --add-data "utils;utils" ^
    --hidden-import=tkinter ^
    --hidden-import=PIL ^
    --hidden-import=cv2 ^
    --hidden-import=numpy ^
    --hidden-import=pynput ^
    --hidden-import=win32gui ^
    --hidden-import=win32con ^
    --hidden-import=win32api ^
    --collect-all=pynput ^
    --noupx ^
    %MAIN_FILE%

if errorlevel 1 (
    echo.
    echo ❌ Build thất bại!
    goto :error
)

:: ============================================================
:: COPY ADDITIONAL FILES
:: ============================================================
echo.
echo [4/4] 📁 Tạo cấu trúc thư mục...

:: Create runtime folders
if not exist "%OUTPUT_DIR%\data" mkdir "%OUTPUT_DIR%\data"
if not exist "%OUTPUT_DIR%\data\macros" mkdir "%OUTPUT_DIR%\data\macros"
if not exist "%OUTPUT_DIR%\data\cropped" mkdir "%OUTPUT_DIR%\data\cropped"
if not exist "%OUTPUT_DIR%\profiles" mkdir "%OUTPUT_DIR%\profiles"
if not exist "%OUTPUT_DIR%\logs" mkdir "%OUTPUT_DIR%\logs"

:: Copy config files
copy /Y "data\*.json" "%OUTPUT_DIR%\data\" >nul 2>&1

:: Copy macros
xcopy /Y /Q /E /I "data\macros" "%OUTPUT_DIR%\data\macros" >nul 2>&1

:: Copy profiles
xcopy /Y /Q /E /I "profiles" "%OUTPUT_DIR%\profiles" >nul 2>&1

echo     ✅ Đã tạo xong

:: Cleanup
rmdir /s /q "build" 2>nul
del /q "*.spec" 2>nul

:: ============================================================
:: DONE
:: ============================================================
echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║  ✅ BUILD HOÀN TẤT!
echo ║  
echo ║  📦 Output: %OUTPUT_DIR%\%APP_NAME%.exe
echo ║  🔒 Mã hóa: AES-256 bytecode encryption
echo ║  
echo ║  ⚠️ Lưu ý PyInstaller:
echo ║     • Khởi động chậm hơn Nuitka (cần extract)
echo ║     • Nhưng tương thích tốt hơn
echo ╚══════════════════════════════════════════════════════════════╝
echo.

:: Show file size
for %%A in ("%OUTPUT_DIR%\%APP_NAME%.exe") do (
    set size=%%~zA
    set /a sizeMB=!size!/1048576
    echo 📊 Kích thước: !sizeMB! MB
)
echo.

set /p RUN="▶️ Chạy thử exe ngay? (Y/N): "
if /i "%RUN%"=="Y" (
    start "" "%OUTPUT_DIR%\%APP_NAME%.exe"
)

goto :end

:error
echo.
echo ══════════════════════════════════════════════════════════════
echo ❌ BUILD THẤT BẠI!
echo.
echo 💡 Thử:
echo    pip install pyinstaller tinyaes --upgrade
echo ══════════════════════════════════════════════════════════════

:end
echo.
pause
