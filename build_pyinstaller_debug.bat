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
    
    :: Check if PIL is installed
    python -c "import PIL" 2>nul
    if errorlevel 1 (
        echo     [WARNING] PIL not installed. Installing Pillow...
        pip install Pillow
    )
    
    python -c "from PIL import Image, ImageDraw; img=Image.new('RGBA',(256,256),(45,45,45,255)); draw=ImageDraw.Draw(img); draw.rounded_rectangle([20,20,236,236],radius=30,fill=(70,130,180,255)); img.save('icon.ico',format='ICO',sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])"
    
    if errorlevel 1 (
        echo     [ERROR] Failed to create icon!
        pause
        exit /b 1
    )
    
    if not exist "%ICON_FILE%" (
        echo     [ERROR] Icon file was not created!
        pause
        exit /b 1
    )
    
    echo     ✅ Icon created successfully!
)

echo.
echo [3/4] Checking ADB...
:: Try to find ADB from LDPlayer
set "ADB_FOUND=0"
set "ADB_SOURCE="

if exist "C:\Program Files\LDPlayer\LDPlayer9\adb.exe" (
    set "ADB_SOURCE=C:\Program Files\LDPlayer\LDPlayer9\adb.exe"
    set "ADB_FOUND=1"
) else if exist "C:\Program Files\LDPlayer\LDPlayer4.0\adb.exe" (
    set "ADB_SOURCE=C:\Program Files\LDPlayer\LDPlayer4.0\adb.exe"
    set "ADB_FOUND=1"
) else if exist "C:\Program Files (x86)\LDPlayer\LDPlayer9\adb.exe" (
    set "ADB_SOURCE=C:\Program Files (x86)\LDPlayer\LDPlayer9\adb.exe"
    set "ADB_FOUND=1"
)

if "%ADB_FOUND%"=="1" (
    echo     ✅ Found ADB at: %ADB_SOURCE%
    if not exist "files" mkdir files
    copy /Y "%ADB_SOURCE%" "files\adb.exe" >nul 2>&1
    
    :: Also copy ADB DLLs if they exist (needed for ADB to work)
    set "ADB_DIR=%ADB_SOURCE%\.."
    if exist "%ADB_DIR%\AdbWinApi.dll" copy /Y "%ADB_DIR%\AdbWinApi.dll" "files\" >nul 2>&1
    if exist "%ADB_DIR%\AdbWinUsbApi.dll" copy /Y "%ADB_DIR%\AdbWinUsbApi.dll" "files\" >nul 2>&1
    
    echo     ✅ ADB and dependencies copied to files folder
    set "ADB_BINARY_ARG=--add-binary files\adb.exe;files"
    
    :: Add DLL binaries if they exist
    if exist "files\AdbWinApi.dll" (
        set "ADB_BINARY_ARG=%ADB_BINARY_ARG% --add-binary files\AdbWinApi.dll;files"
    )
    if exist "files\AdbWinUsbApi.dll" (
        set "ADB_BINARY_ARG=%ADB_BINARY_ARG% --add-binary files\AdbWinUsbApi.dll;files"
    )
) else (
    echo     ⚠️ ADB not found in LDPlayer directories
    echo     App will try to use system ADB from PATH
    set "ADB_BINARY_ARG="
)

:: Check for minitouch binaries
echo.
echo [3.5/4] Checking minitouch binaries...
set "MINITOUCH_ARG="
if exist "files\minitouch-arm" (
    echo     ✅ Found minitouch-arm
    set "MINITOUCH_ARG=--add-binary files\minitouch-arm;files"
)
if exist "files\minitouch-arm64" (
    echo     ✅ Found minitouch-arm64
    set "MINITOUCH_ARG=%MINITOUCH_ARG% --add-binary files\minitouch-arm64;files"
)
if exist "files\minitouch-x86" (
    echo     ✅ Found minitouch-x86
    set "MINITOUCH_ARG=%MINITOUCH_ARG% --add-binary files\minitouch-x86;files"
)
if exist "files\minitouch-x86_64" (
    echo     ✅ Found minitouch-x86_64
    set "MINITOUCH_ARG=%MINITOUCH_ARG% --add-binary files\minitouch-x86_64;files"
)
if "%MINITOUCH_ARG%"=="" (
    echo     ⚠️ Minitouch binaries not found in files folder
    echo     To enable minitouch support, download from: https://github.com/ABI-ETH/stf-minitouch/releases
    echo     Place minitouch-arm, minitouch-x86, etc. in files folder
)

echo.
echo [4/4] Setting debug config...
if not exist "data" mkdir data
echo {"enable_file_logging": true, "enable_console_logging": true, "debug_mode": true} > data\app_config.json

echo [5/5] Building with PyInstaller (DEBUG MODE - with console)...
echo.

:: Get absolute path for icon
set "ABS_ICON_PATH=%~dp0%ICON_FILE%"
echo     Icon path: %ABS_ICON_PATH%

if not exist "%ABS_ICON_PATH%" (
    echo     [ERROR] Icon file not found at: %ABS_ICON_PATH%
    pause
    exit /b 1
)

pyinstaller --noconfirm ^
    --onefile ^
    --console ^
    --name=%APP_NAME% ^
    --distpath=dist ^
    --manifest=MacroAuto.manifest ^
    --icon="%ABS_ICON_PATH%" ^
    --add-data "data;data" ^
    --add-data "profiles;profiles" ^
    --add-data "handlers;handlers" ^
    --add-data "detectors;detectors" ^
    --add-data "core;core" ^
    --add-data "emulator;emulator" ^
    --add-data "ui;ui" ^
    --add-data "utils;utils" ^
    --add-data "%ABS_ICON_PATH%;." ^
    %ADB_BINARY_ARG% ^
    %MINITOUCH_ARG% ^
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
    --hidden-import=uiautomator2 ^
    --hidden-import=adbutils ^
    --hidden-import=lxml ^
    --hidden-import=retry2 ^
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

:: Verify exe was created
if not exist "dist\%APP_NAME%.exe" (
    echo.
    echo ❌ EXE file was not created!
    goto :error
)

echo     ✅ EXE created successfully!
echo.
echo [6/6] Post-build setup...

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
if exist "%ICON_FILE%" (
    copy /Y "%ICON_FILE%" "dist\"
    if errorlevel 1 (
        echo     [WARNING] Failed to copy icon to dist folder
    ) else (
        echo     ✅ Icon copied to dist folder
    )
) else (
    echo     [WARNING] Icon file not found, skipping copy
)

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
