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
set ICON_FILE=icon.ico
set OUTPUT_DIR=dist

:: Fix Python encoding issues
set PYTHONIOENCODING=utf-8

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
echo [3/4] 🔨 Đang build EXE với Nuitka...
echo     ⏳ Quá trình này mất 3-10 phút (lần đầu lâu hơn)
echo.

python -m nuitka ^
    --standalone ^
    --onefile ^
    --windows-console-mode=force ^
    --output-dir=%OUTPUT_DIR% ^
    --output-filename=%APP_NAME%.exe ^
    --enable-plugin=tk-inter ^
    --enable-plugin=numpy ^
    --enable-plugin=multiprocessing ^
    --follow-imports ^
    --follow-stdlib ^
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
    goto :error
)

:: ============================================================
:: DONE
:: ============================================================
echo.
echo [4/4] ✅ BUILD HOÀN TẤT!
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
    echo ⚠️ Cửa sổ console sẽ mở để xem lỗi (nếu có)
    echo.
    cd "%OUTPUT_DIR%"
    "%APP_NAME%.exe"
    echo.
    echo ══════════════════════════════════════════════════════════════
    if errorlevel 1 (
        echo ❌ App thoát với lỗi! Kiểm tra thông báo bên trên.
    ) else (
        echo ✅ App đã thoát bình thường
    )
    echo ══════════════════════════════════════════════════════════════
    cd ..
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
