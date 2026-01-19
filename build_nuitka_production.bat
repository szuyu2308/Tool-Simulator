@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
cd /d %~dp0

echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║           🚀 MACRO AUTO - BUILD EXE (NUITKA)                 ║
echo ║       Tốc độ nhanh + Bảo mật cao + Mã hóa bytecode           ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.
echo ⚠️  LƯU Ý: Nếu bị lỗi "Error 225 - virus detected"
echo     → TẮT Windows Defender/Antivirus tạm thời
echo     → Hoặc thêm thư mục này vào exclusion list
echo.

:: ============================================================
:: CONFIGURATION
:: ============================================================
set APP_NAME=MacroAuto
set MAIN_FILE=app.py
set ICON_FILE=icon.ico
set OUTPUT_DIR=dist
set VERSION=1.0.0
set COMPANY=Szuyu
set DESCRIPTION=Macro Automation Tool for Emulators

:: DEBUG MODE: set to "1" to enable console (for debugging), "0" to hide console (for release)
set DEBUG_MODE=0

:: Fix Python encoding issues
set PYTHONIOENCODING=utf-8

:: ============================================================
:: CHECK REQUIREMENTS
:: ============================================================
echo.
echo [1/5] Kiểm tra môi trường...

python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python chưa được cài đặt!
    goto :error
)
for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYTHON_VER=%%v
echo     ✅ Python %PYTHON_VER%

:: Check/Install Nuitka
python -c "import nuitka" >nul 2>&1
if errorlevel 1 (
    echo     📦 Đang cài đặt Nuitka...
    pip install nuitka ordered-set zstandard --quiet
)
echo     ✅ Nuitka OK

:: Check required Python packages
echo     📦 Kiểm tra dependencies...
python -c "import tkinter" >nul 2>&1 || (echo     ❌ tkinter missing! && goto :error)
python -c "import PIL" >nul 2>&1 || (echo     ⚠️ Installing Pillow... && pip install Pillow -q)
python -c "import cv2" >nul 2>&1 || (echo     ⚠️ Installing opencv-python... && pip install opencv-python -q)
python -c "import mss" >nul 2>&1 || (echo     ⚠️ Installing mss... && pip install mss -q)
python -c "import win32gui" >nul 2>&1 || (echo     ⚠️ Installing pywin32... && pip install pywin32 -q)
python -c "import pynput" >nul 2>&1 || (echo     ⚠️ Installing pynput... && pip install pynput -q)
python -c "import numpy" >nul 2>&1 || (echo     ⚠️ Installing numpy... && pip install numpy -q)
python -c "import psutil" >nul 2>&1 || (echo     ⚠️ Installing psutil... && pip install psutil -q)
python -c "import pyperclip" >nul 2>&1 || (echo     ⚠️ Installing pyperclip... && pip install pyperclip -q)
python -c "import dxcam" >nul 2>&1 || (echo     ⚠️ Installing dxcam... && pip install dxcam -q)
echo     ✅ Dependencies OK

:: Check for C compiler
where cl >nul 2>&1
if errorlevel 1 (
    where gcc >nul 2>&1
    if errorlevel 1 (
        echo     ⚠️ Không tìm thấy C compiler (MSVC/MinGW)
        echo     📦 Nuitka sẽ tự download MinGW64...
    ) else (
        echo     ✅ GCC Compiler OK
    )
) else (
    echo     ✅ MSVC Compiler OK
)

:: ============================================================
:: CHECK/CREATE ICON
:: ============================================================
echo.
echo [2/5] Kiểm tra icon...
if not exist "%ICON_FILE%" (
    echo     ⚠️ Không tìm thấy %ICON_FILE%
    echo     📦 Tạo icon mặc định...
    
    :: Create icon using inline Python - escape special chars for batch
    python -c "from PIL import Image,ImageDraw;img=Image.new('RGBA',(256,256),(45,45,45,255));draw=ImageDraw.Draw(img);draw.rounded_rectangle([20,20,236,236],radius=30,fill=(70,130,180,255));img.save('icon.ico',format='ICO',sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)]);print('Icon created!')" 2>nul
    
    if not exist "%ICON_FILE%" (
        echo     ⚠️ Không thể tạo icon, sẽ build không có icon
    )
)
if exist "%ICON_FILE%" (
    echo     ✅ Icon OK: %ICON_FILE%
)

:: ============================================================
:: CLEAN OLD BUILD
:: ============================================================
echo.
echo [3/5] Dọn dẹp build cũ...
if exist "%OUTPUT_DIR%" rmdir /s /q "%OUTPUT_DIR%" 2>nul
if exist "*.build" rmdir /s /q "*.build" 2>nul
if exist "%APP_NAME%.build" rmdir /s /q "%APP_NAME%.build" 2>nul
if exist "%APP_NAME%.dist" rmdir /s /q "%APP_NAME%.dist" 2>nul
if exist "%APP_NAME%.onefile-build" rmdir /s /q "%APP_NAME%.onefile-build" 2>nul
if exist "app.build" rmdir /s /q "app.build" 2>nul
if exist "app.dist" rmdir /s /q "app.dist" 2>nul
if exist "app.onefile-build" rmdir /s /q "app.onefile-build" 2>nul
echo     ✅ Đã dọn dẹp

:: ============================================================
:: SET APP CONFIG BASED ON DEBUG MODE
:: ============================================================
echo.
echo [4/5] Thiết lập app config...
if not exist "data" mkdir data

if "%DEBUG_MODE%"=="0" (
    echo     🐛 DEBUG CONFIG: Console logging enabled
    echo {"enable_file_logging": true, "enable_console_logging": true, "debug_mode": true} > data\app_config.json
) else (
    echo     📦 RELEASE CONFIG: File logging only
    echo {"enable_file_logging": true, "enable_console_logging": false, "debug_mode": false} > data\app_config.json
)
echo     ✅ Config đã được thiết lập

:: ============================================================
:: BUILD WITH NUITKA
:: ============================================================
echo.
echo [5/5] 🔨 Đang build với Nuitka...
echo     ⏳ Quá trình này mất 3-15 phút (lần đầu lâu hơn)

if "%DEBUG_MODE%"=="1" (
    echo     🐛 DEBUG MODE: Console sẽ hiện để debug lỗi
    set CONSOLE_MODE=--windows-console-mode=force
) else (
    echo     📦 RELEASE MODE: Ẩn console
    set CONSOLE_MODE=--windows-console-mode=disable
)
echo.

:: Build command with all necessary options
python -m nuitka ^
    --standalone ^
    --onefile ^
    --onefile-tempdir-spec="{CACHE_DIR}/%COMPANY%/%APP_NAME%/%VERSION%" ^
    --company-name="%COMPANY%" ^
    --product-name="%APP_NAME%" ^
    --product-version="%VERSION%" ^
    --file-version="%VERSION%.0" ^
    --file-description="%DESCRIPTION%" ^
    --copyright="Copyright 2026 %COMPANY%" ^
    %CONSOLE_MODE% ^
    --output-dir=%OUTPUT_DIR% ^
    --output-filename=%APP_NAME%.exe ^
    --windows-icon-from-ico=%ICON_FILE% ^
    --enable-plugin=tk-inter ^
    --enable-plugin=multiprocessing ^
    --nofollow-import-to=*.tests ^
    --nofollow-import-to=*.test ^
    --nofollow-import-to=unittest ^
    --nofollow-import-to=pytest ^
    --include-package=tkinter ^
    --include-package=PIL ^
    --include-package=cv2 ^
    --include-package=mss ^
    --include-package=numpy ^
    --include-package=pynput ^
    --include-package=psutil ^
    --include-package=pyperclip ^
    --include-package=dxcam ^
    --include-package=win32gui ^
    --include-package=win32ui ^
    --include-package=win32con ^
    --include-package=win32api ^
    --include-package=win32clipboard ^
    --include-package=win32process ^
    --include-package=win32event ^
    --include-package=pythoncom ^
    --include-package=pywintypes ^
    --include-package=comtypes ^
    --include-module=tkinter.ttk ^
    --include-module=tkinter.filedialog ^
    --include-module=tkinter.messagebox ^
    --include-module=tkinter.simpledialog ^
    --include-module=tkinter.colorchooser ^
    --include-module=PIL.Image ^
    --include-module=PIL.ImageTk ^
    --include-module=PIL.ImageGrab ^
    --include-module=PIL.ImageDraw ^
    --include-module=PIL.ImageFilter ^
    --include-module=PIL.ImageOps ^
    --include-module=pynput.keyboard ^
    --include-module=pynput.mouse ^
    --include-module=pynput._util.win32 ^
    --include-module=pynput.keyboard._win32 ^
    --include-module=pynput.mouse._win32 ^
    --include-data-dir=data=data ^
    --include-data-dir=profiles=profiles ^
    --include-data-files=%ICON_FILE%=%ICON_FILE% ^
    --follow-imports ^
    --prefer-source-code ^
    --assume-yes-for-downloads ^
    --remove-output ^
    --lto=no ^
    --jobs=4 ^
    --show-progress ^
    --show-memory ^
    %MAIN_FILE%

if errorlevel 1 (
    echo.
    echo ❌ Build thất bại!
    echo.
    echo 💡 Các nguyên nhân phổ biến:
    echo    • Error 225: Windows Defender chặn - tạm tắt hoặc thêm exclusion
    echo    • Missing module: pip install ^<module_name^>
    echo    • C compiler: Cài Visual Studio Build Tools hoặc MinGW
    echo.
    goto :error
)

:: ============================================================
:: POST-BUILD: FIND EXE AND CREATE FOLDERS
:: ============================================================
echo.
echo [Post-Build] Kiểm tra và hoàn tất...

:: Find the actual exe location
set "EXE_PATH="
if exist "%OUTPUT_DIR%\%APP_NAME%.exe" (
    set "EXE_PATH=%OUTPUT_DIR%\%APP_NAME%.exe"
) else (
    echo ❌ Không tìm thấy file .exe output!
    goto :error
)

echo     ✅ Output: %EXE_PATH%

:: Create runtime folders in dist
if not exist "%OUTPUT_DIR%\logs" mkdir "%OUTPUT_DIR%\logs"
if not exist "%OUTPUT_DIR%\files" mkdir "%OUTPUT_DIR%\files"

:: Get file size
for %%A in ("%EXE_PATH%") do (
    set size=%%~zA
    set /a sizeMB=!size!/1048576
)

:: ============================================================
:: DONE
:: ============================================================
echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║  ✅ BUILD HOÀN TẤT!                                          ║
echo ╠══════════════════════════════════════════════════════════════╣
echo ║  📦 Output: %EXE_PATH%
echo ║  📊 Size: !sizeMB! MB
echo ║  🏷️  Version: %VERSION%
if "%DEBUG_MODE%"=="1" (
echo ║  🐛 Mode: DEBUG (console hiện)
) else (
echo ║  📦 Mode: RELEASE (ẩn console)
)
echo ╠══════════════════════════════════════════════════════════════╣
echo ║  ✅ Included:                                                ║
echo ║     • Tkinter GUI + all dialogs                              ║
echo ║     • PIL/Pillow (image processing)                          ║
echo ║     • OpenCV (computer vision)                               ║
echo ║     • MSS + DXCam (screen capture)                           ║
echo ║     • PyWin32 (Windows API)                                  ║
echo ║     • pynput (input simulation)                              ║
echo ║     • All core modules                                       ║
echo ║  ✅ Features:                                                ║
echo ║     • DPI awareness (per-monitor v2)                         ║
echo ║     • Taskbar icon support                                   ║
echo ║     • Windows 10/11 compatibility                            ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.

:: Ask to run
set /p RUN="▶️ Chạy thử exe ngay? (Y/N): "
if /i "%RUN%"=="Y" (
    echo.
    echo 🚀 Đang khởi động...
    echo    (Lần đầu chạy có thể mất 5-10s để extract files...)
    start "" "%EXE_PATH%"
)

goto :end

:error
echo.
echo ══════════════════════════════════════════════════════════════
echo ❌ CÓ LỖI XẢY RA!
echo.
echo 💡 Thử các cách sau:
echo    1. pip install --upgrade nuitka
echo    2. pip install -r requirements.txt
echo    3. Tắt Windows Defender tạm thời
echo    4. Chạy CMD với quyền Administrator
echo ══════════════════════════════════════════════════════════════

:end
echo.
pause
