@echo off
chcp 65001 >nul
cd /d %~dp0

echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║        🚀 MACRO AUTO - BUILD DEBUG (PYINSTALLER)             ║
echo ║           Fast build with console for testing/debugging      ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.

:: Configuration
set APP_NAME=MacroAuto
set ICON_FILE=icon.ico

:: Check Python
python --version
if errorlevel 1 (
    echo [ERROR] Python not found!
    pause
    exit /b 1
)

:: Check PyInstaller
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo [INFO] Installing PyInstaller...
    pip install pyinstaller
)

echo.
echo [1/4] Cleaning previous build...
if exist "dist" rmdir /s /q dist
if exist "build" rmdir /s /q build
if exist "*.spec" del /f /q *.spec

echo [2/4] Checking icon...
if not exist "%ICON_FILE%" (
    echo     Creating default icon...
    python -c "from PIL import Image, ImageDraw; img=Image.new('RGBA',(256,256),(45,45,45,255)); draw=ImageDraw.Draw(img); draw.rounded_rectangle([20,20,236,236],radius=30,fill=(70,130,180,255)); img.save('icon.ico',format='ICO',sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])" 2>nul
)

echo.
echo [3/4] Setting debug config...
if not exist "data" mkdir data
echo {"enable_file_logging": true, "enable_console_logging": true, "debug_mode": true} > data\app_config.json

echo [4/4] Building with PyInstaller (DEBUG MODE - with console)...
echo.

pyinstaller --noconfirm ^
    --onefile ^
    --console ^
    --name=%APP_NAME% ^
    --distpath=dist ^
    --manifest=MacroAuto.manifest ^
    --icon=%ICON_FILE% ^
    --add-data "data;data" ^
    --add-data "profiles;profiles" ^
    --add-data "handlers;handlers" ^
    --add-data "detectors;detectors" ^
    --add-data "core;core" ^
    --add-data "emulator;emulator" ^
    --add-data "ui;ui" ^
    --add-data "utils;utils" ^
    --add-data "%ICON_FILE%;." ^
    --hidden-import=tkinter ^
    --hidden-import=tkinter.ttk ^
    --hidden-import=tkinter.filedialog ^
    --hidden-import=tkinter.messagebox ^
    --hidden-import=tkinter.simpledialog ^
    --hidden-import=PIL ^
    --hidden-import=PIL.Image ^
    --hidden-import=PIL.ImageTk ^
    --hidden-import=PIL.ImageGrab ^
    --hidden-import=PIL.ImageDraw ^
    --hidden-import=cv2 ^
    --hidden-import=numpy ^
    --hidden-import=pynput ^
    --hidden-import=pynput.keyboard ^
    --hidden-import=pynput.mouse ^
    --hidden-import=pynput._util.win32 ^
    --hidden-import=pynput.keyboard._win32 ^
    --hidden-import=pynput.mouse._win32 ^
    --hidden-import=win32gui ^
    --hidden-import=win32ui ^
    --hidden-import=win32con ^
    --hidden-import=win32api ^
    --hidden-import=win32clipboard ^
    --hidden-import=win32process ^
    --hidden-import=mss ^
    --hidden-import=pyperclip ^
    --hidden-import=psutil ^
    --hidden-import=dxcam ^
    --hidden-import=pythoncom ^
    --hidden-import=pywintypes ^
    --hidden-import=comtypes ^
    --hidden-import=win32event ^
    --collect-all=pynput ^
    --collect-all=dxcam ^
    --noupx ^
    app.py

if errorlevel 1 (
    echo.
    echo ❌ Build failed!
    goto :error
)

echo.
echo [5/5] Post-build setup...

:: Create runtime folders
if not exist "dist\data" mkdir "dist\data"
if not exist "dist\data\macros" mkdir "dist\data\macros"
if not exist "dist\data\cropped" mkdir "dist\data\cropped"
if not exist "dist\profiles" mkdir "dist\profiles"
if not exist "dist\logs" mkdir "dist\logs"
if not exist "dist\files" mkdir "dist\files"

:: Copy config files
copy /Y "data\*.json" "dist\data\" >nul 2>&1
xcopy /Y /Q /E /I "data\macros" "dist\data\macros" >nul 2>&1
xcopy /Y /Q /E /I "profiles" "dist\profiles" >nul 2>&1

:: Copy icon to dist
copy /Y "%ICON_FILE%" "dist\" >nul 2>&1

:: Cleanup
rmdir /s /q "build" 2>nul
del /q "*.spec" 2>nul

echo     ✅ Build complete!

echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║  ✅ BUILD HOÀN TẤT!                                          ║
echo ╠══════════════════════════════════════════════════════════════╣
echo ║  📦 Output: dist\%APP_NAME%.exe
echo ║  🐛 Mode: DEBUG (console hiện để debug)
echo ║  ✅ Features:
echo ║     • Console output enabled
echo ║     • All dependencies included
echo ║     • Icon support
echo ║     • DPI awareness
echo ╚══════════════════════════════════════════════════════════════╝
echo.

set /p RUN="▶️ Chạy thử exe ngay? (Y/N): "
if /i "%RUN%"=="Y" (
    echo.
    echo 🚀 Đang khởi động...
    start "" "dist\%APP_NAME%.exe"
)

goto :end

:error
echo.
echo ══════════════════════════════════════════════════════════════
echo ❌ CÓ LỖI XẢY RA!
echo.
echo 💡 Kiểm tra:
echo    1. pip install --upgrade pyinstaller
echo    2. pip install -r requirements.txt
echo ══════════════════════════════════════════════════════════════

:end
echo.
pause
