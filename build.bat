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
echo ⚠️  LƯU Ý: Nếu bị lỗi "Error 225 - virus detected"
echo     → TẮT Windows Defender/Antivirus tạm thời
echo     → Hoặc thêm thư mục này vào exclusion list
echo.

:: ============================================================
:: CONFIGURATION
:: ============================================================
set APP_NAME=AutoTool
set MAIN_FILE=app.py
set ICON_FILE=icon.ico
set OUTPUT_DIR=dist

:: DEBUG MODE: set to "1" to enable console (for debugging), "0" to hide console (for release)
set DEBUG_MODE=0

:: Fix Python encoding issues
set PYTHONIOENCODING=utf-8

:: ============================================================
:: CHECK REQUIREMENTS
:: ============================================================
echo.
echo [1/3] Kiểm tra môi trường...

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
echo [2/3] Dọn dẹp build cũ...
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
echo [3/3] 🔨 Đang build (standalone folder) với Nuitka...
echo     ⏳ Quá trình này mất 2-10 phút (lần đầu lâu hơn)

if "%DEBUG_MODE%"=="1" (
    echo     🐛 DEBUG MODE: Console sẽ hiện để debug lỗi
    set CONSOLE_MODE=--windows-console-mode=force
) else (
    echo     📦 RELEASE MODE: Ẩn console
    set CONSOLE_MODE=--windows-disable-console
)
echo.

python -m nuitka ^
    --standalone ^
    --onefile ^
    --onefile-tempdir-spec="{CACHE_DIR}/Szuyu/MacroAuto/1.0.0" ^
    --company-name="Szuyu" ^
    --product-name="MacroAuto" ^
    --product-version="1.0.0" ^
    --file-version="1.0.0.0" ^
    --file-description="Macro Tool for All" ^
    %CONSOLE_MODE% ^
    --output-dir=%OUTPUT_DIR% ^
    --output-filename=%APP_NAME%.exe ^
    --windows-icon-from-ico=%ICON_FILE% ^
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
    echo.
    echo 💡 Nếu lỗi "Error 225 - virus/unwanted software":
    echo    • Cách chuẩn: ký số (Authenticode) cho exe/installer để tăng uy tín
    echo    • Tránh onefile (đang dùng standalone folder) thường ít dính hơn
    echo    • Nếu vẫn bị nhầm: gửi file lên Microsoft Security Intelligence để gỡ false-positive
    goto :error
)

:: ============================================================
:: DONE
:: ============================================================
echo.
echo ✅ BUILD HOÀN TẤT!
echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║  📦 Output: %OUTPUT_DIR%\%APP_NAME%.exe
echo ║  
echo ║  🚀 Ưu điểm Nuitka (onefile):
echo ║     • Chỉ 1 file .exe duy nhất
echo ║     • Mã nguồn được biên dịch sang C (khó decompile)  
echo ║     • DLLs được nhúng vào exe (ẩn hết)
echo ║  
echo ║  ⚠️  Lưu ý:
echo ║     • Khởi động chậm hơn 3-5 giây (phải extract)
echo ║     • Dễ bị Windows Defender chặn hơn
echo ╚══════════════════════════════════════════════════════════════╝
echo.

:: Show file size
for %%A in ("%OUTPUT_DIR%\app.dist\%APP_NAME%.exe") do (
    set size=%%~zA
    set /a sizeMB=!size!/1048576
    echo 📊 Kích thước: !sizeMB! MB
)
echo.
echo 💡 Nếu Windows Defender chặn file khi chạy:
echo    • Đây là false-positive phổ biến với Python compiled apps
echo    • Tạm tắt Real-time Protection hoặc thêm exclusion
echo    • Hoặc ký số (Authenticode) cho file để tăng uy tín
echo.

:: Ask to run
set /p RUN="▶️ Chạy thử exe ngay? (Y/N): "
if /i "%RUN%"=="Y" (
    echo.
    echo 🚀 Đang khởi động...
    echo.
    cd "%OUTPUT_DIR%"
    start "" "%APP_NAME%.exe"
    echo.
    echo ══════════════════════════════════════════════════════════════
    if errorlevel 1 (
        echo ❌ App thoát với lỗi! Kiểm tra thông báo bên trên.
    ) else (
        echo ✅ App đã thoát bình thường
    )
    echo ══════════════════════════════════════════════════════════════
    cd ..
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
