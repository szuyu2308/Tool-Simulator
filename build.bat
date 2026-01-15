@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
cd /d %~dp0

echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║           🚀 AUTO TOOL - BUILD EXE (NUITKA)                  ║
echo ║       Tốc độ nhanh + Bảo mật cao + Mã hóa bytecode           ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.

:: ============================================================
:: CONFIGURATION
:: ============================================================
set APP_NAME=AutoTool
set MAIN_FILE=app.py
set ICON_FILE=
set OUTPUT_DIR=dist

:: ============================================================
:: CHECK REQUIREMENTS
:: ============================================================
echo [1/5] Kiểm tra môi trường...

python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python chưa được cài đặt!
    goto :error
)
echo     ✅ Python OK

:: Check/Install Nuitka
python -c "import nuitka" >nul 2>&1
if errorlevel 1 (
    echo     📦 Đang cài đặt Nuitka...
    pip install nuitka ordered-set zstandard --quiet
)
echo     ✅ Nuitka OK

:: Check for C compiler
where cl >nul 2>&1
if errorlevel 1 (
    where gcc >nul 2>&1
    if errorlevel 1 (
        echo     ⚠️ Không tìm thấy C compiler (MSVC/MinGW)
        echo     📦 Đang cài đặt MinGW64...
        python -m nuitka --mingw64 --version >nul 2>&1
    )
)
echo     ✅ C Compiler OK

:: ============================================================
:: CLEAN OLD BUILD
:: ============================================================
echo.
echo [2/5] Dọn dẹp build cũ...
if exist "%OUTPUT_DIR%" rmdir /s /q "%OUTPUT_DIR%" 2>nul
if exist "*.build" rmdir /s /q "*.build" 2>nul
if exist "%APP_NAME%.build" rmdir /s /q "%APP_NAME%.build" 2>nul
if exist "%APP_NAME%.dist" rmdir /s /q "%APP_NAME%.dist" 2>nul
if exist "%APP_NAME%.onefile-build" rmdir /s /q "%APP_NAME%.onefile-build" 2>nul
echo     ✅ Đã dọn dẹp

:: ============================================================
:: BUILD WITH NUITKA
:: ============================================================
echo.
echo [3/5] 🔨 Đang build EXE với Nuitka...
echo     ⏳ Quá trình này mất 3-10 phút (lần đầu lâu hơn)
echo.

python -m nuitka ^
    --standalone ^
    --onefile ^
    --windows-console-mode=attach ^
    --output-dir=%OUTPUT_DIR% ^
    --output-filename=%APP_NAME%.exe ^
    --enable-plugin=tk-inter ^
    --include-data-dir=data=data ^
    --include-data-dir=profiles=profiles ^
    --include-data-dir=handlers=handlers ^
    --include-data-dir=detectors=detectors ^
    --follow-imports ^
    --assume-yes-for-downloads ^
    --remove-output ^
    --lto=yes ^
    --jobs=4 ^
    --show-progress ^
    --show-memory ^
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
echo [4/5] 📁 Sao chép files bổ sung...

:: Create necessary folders in dist if onefile didn't include them
if not exist "%OUTPUT_DIR%\data" mkdir "%OUTPUT_DIR%\data"
if not exist "%OUTPUT_DIR%\data\macros" mkdir "%OUTPUT_DIR%\data\macros"
if not exist "%OUTPUT_DIR%\profiles" mkdir "%OUTPUT_DIR%\profiles"
if not exist "%OUTPUT_DIR%\logs" mkdir "%OUTPUT_DIR%\logs"

:: Copy data files (json configs)
xcopy /Y /Q "data\*.json" "%OUTPUT_DIR%\data\" >nul 2>&1

:: Copy profiles
xcopy /Y /Q /E /I "profiles" "%OUTPUT_DIR%\profiles" >nul 2>&1

:: Copy macros
xcopy /Y /Q /E /I "data\macros" "%OUTPUT_DIR%\data\macros" >nul 2>&1

echo     ✅ Đã sao chép

:: ============================================================
:: DONE
:: ============================================================
echo.
echo [5/5] ✅ BUILD HOÀN TẤT!
echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║  📦 Output: %OUTPUT_DIR%\%APP_NAME%.exe
echo ║  
echo ║  🚀 Ưu điểm Nuitka:
echo ║     • Khởi động NHANH hơn PyInstaller 2-5x
echo ║     • Mã nguồn được biên dịch sang C (khó decompile)  
echo ║     • Kích thước nhỏ hơn
echo ║     • Không cần extract khi chạy
echo ╚══════════════════════════════════════════════════════════════╝
echo.

:: Show file size
for %%A in ("%OUTPUT_DIR%\%APP_NAME%.exe") do (
    set size=%%~zA
    set /a sizeMB=!size!/1048576
    echo 📊 Kích thước: !sizeMB! MB
)
echo.

:: Ask to run
set /p RUN="▶️ Chạy thử exe ngay? (Y/N): "
if /i "%RUN%"=="Y" (
    echo.
    echo 🚀 Đang khởi động...
    start "" "%OUTPUT_DIR%\%APP_NAME%.exe"
)

goto :end

:error
echo.
echo ══════════════════════════════════════════════════════════════
echo ❌ CÓ LỖI XẢY RA!
echo.
echo 💡 Thử các cách sau:
echo    1. Cài Visual Studio Build Tools (khuyên dùng)
echo    2. Hoặc chạy: pip install mingw64
echo    3. Kiểm tra Python path trong System Environment
echo ══════════════════════════════════════════════════════════════

:end
echo.
pause
