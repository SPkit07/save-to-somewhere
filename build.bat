@echo off
REM ==========================================
REM Build Desktop Application with PyInstaller
REM with Install Option
REM ==========================================

setlocal enabledelayedexpansion

cd /d "%~dp0"

echo.
echo ===============================================
echo  Excel Processor - Build & Install
echo ===============================================
echo.
echo Choose an option:
echo.
echo   1 = Build .exe only
echo   2 = Build and Install
echo   3 = Install existing .exe
echo   0 = Exit
echo.
set /p choice="Enter your choice (0-3): "

if "%choice%"=="0" exit /b 0
if "%choice%"=="1" goto BUILD_ONLY
if "%choice%"=="2" goto BUILD_AND_INSTALL
if "%choice%"=="3" goto INSTALL_ONLY

echo Invalid choice! Exiting...
pause
exit /b 1

:BUILD_ONLY
cls
echo.
echo ===============================================
echo  Step 1: Building Desktop Application (.exe)
echo ===============================================
echo.

call :BUILD_EXE
if %ERRORLEVEL% NEQ 0 exit /b 1

echo.
echo ===============================================
echo  ✅ Build Complete!
echo ===============================================
echo.
echo 📁 Output: dist\ExcelProcessor.exe
echo.
echo Next steps:
echo   1. Go to dist folder
echo   2. Double-click ExcelProcessor.exe
echo   3. Done!
echo.
pause
exit /b 0

:BUILD_AND_INSTALL
cls
echo.
echo ===============================================
echo  Step 1: Building Desktop Application (.exe)
echo ===============================================
echo.

call :BUILD_EXE
if %ERRORLEVEL% NEQ 0 exit /b 1

echo.
echo ===============================================
echo  Step 2: Installing Application
echo ===============================================
echo.

call :INSTALL_APP
if %ERRORLEVEL% NEQ 0 exit /b 1

echo.
echo ===============================================
echo  ✅ Installation Complete!
echo ===============================================
echo.
pause
exit /b 0

:INSTALL_ONLY
cls
echo.
echo ===============================================
echo  Installing Existing Application
echo ===============================================
echo.

if not exist "dist\ExcelProcessor.exe" (
    echo ❌ Error: dist\ExcelProcessor.exe not found
    echo Please build the .exe first using option 1 or 2
    echo.
    pause
    exit /b 1
)

call :INSTALL_APP
if %ERRORLEVEL% NEQ 0 exit /b 1

echo.
echo ✅ Installation Complete!
echo.
pause
exit /b 0

REM ===============================================
REM SUBROUTINE: BUILD_EXE
REM ===============================================
:BUILD_EXE

REM ใช้อินเทอร์พรีตเตอร์ Python หลักในเครื่อง
echo Using global Python environment...

echo.
echo - Installing build dependencies...
pip install eel pyinstaller --quiet

echo.
echo - Preparing web files...
if exist "web" rmdir /s /q web
mkdir web
copy index.html web\ >nul 2>&1
copy script.js web\ >nul 2>&1
echo ✅ UI files ready

echo.
echo - Cleaning old build files...
if exist "dist" rmdir /s /q dist
if exist "build" rmdir /s /q build
if exist "ExcelProcessor.spec" del ExcelProcessor.spec

echo.
echo - Creating executable...
echo.

python -m PyInstaller ^
    --name "ExcelProcessor" ^
    --onefile ^
    --windowed ^
    --add-data "web;web" ^
    --add-data "config.json;." ^
    --hidden-import=pandas ^
    --hidden-import=numpy ^
    --hidden-import=openpyxl ^
    --hidden-import=eel ^
    --collect-all=eel ^
    main.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ❌ Build failed - check error messages above
    pause
    exit /b 1
)

echo.
echo ✅ Executable created successfully
exit /b 0

REM ===============================================
REM SUBROUTINE: INSTALL_APP
REM ===============================================
:INSTALL_APP

if not exist "dist\ExcelProcessor.exe" (
    echo ❌ Error: dist\ExcelProcessor.exe not found
    exit /b 1
)

REM สร้างโฟลเดอร์ Program Files
set INSTALL_DIR=%ProgramFiles%\ExcelProcessor
echo Installing to: %INSTALL_DIR%

REM ตรวจสอบ administrative privileges
net session >nul 2>&1
if %errorLevel% NEQ 0 (
    echo.
    echo ⚠️  This installation requires Administrator privileges
    echo Please run as Administrator
    echo.
    pause
    exit /b 1
)

echo.
echo - Creating installation directory...
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"

echo - Copying files...
copy "dist\ExcelProcessor.exe" "%INSTALL_DIR%\" >nul 2>&1
if exist "config.json" copy "config.json" "%INSTALL_DIR%\" >nul 2>&1
if exist "config.py" copy "config.py" "%INSTALL_DIR%\" >nul 2>&1

echo - Creating Start Menu shortcut...
set APPDATA_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs
if not exist "%APPDATA_DIR%" mkdir "%APPDATA_DIR%"

REM Create shortcut using VBScript
set SHORTCUT_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\ExcelProcessor
if not exist "%SHORTCUT_DIR%" mkdir "%SHORTCUT_DIR%"

call :CREATE_SHORTCUT "%INSTALL_DIR%\ExcelProcessor.exe" "%SHORTCUT_DIR%\Excel Processor.lnk"

echo - Creating desktop shortcut...
set DESKTOP=%USERPROFILE%\Desktop
call :CREATE_SHORTCUT "%INSTALL_DIR%\ExcelProcessor.exe" "%DESKTOP%\ExcelProcessor.lnk"

echo - Creating uninstall script...
call :CREATE_UNINSTALLER

echo.
echo ✅ Installation completed successfully!
echo.
echo 📍 Shortcuts created:
echo   - Start Menu: Excel Processor
echo   - Desktop: ExcelProcessor
echo.
echo Application installed to: %INSTALL_DIR%
echo.

exit /b 0

REM ===============================================
REM SUBROUTINE: CREATE_SHORTCUT
REM ===============================================
:CREATE_SHORTCUT
setlocal enabledelayedexpansion
set EXE_PATH=%~1
set SHORTCUT_PATH=%~2

REM Create VBScript to make shortcut
set TEMP_VBS=%TEMP%\CreateShortcut.vbs

(
    echo Set oWS = WScript.CreateObject("WScript.Shell"^)
    echo sLinkFile = "%SHORTCUT_PATH%"
    echo Set oLink = oWS.CreateShortcut(sLinkFile^)
    echo oLink.TargetPath = "%EXE_PATH%"
    echo oLink.WorkingDirectory = "%INSTALL_DIR%"
    echo oLink.Description = "Excel Processor"
    echo oLink.Save
) > "!TEMP_VBS!"

cscript.exe "!TEMP_VBS!" >nul 2>&1
del "!TEMP_VBS!" >nul 2>&1

endlocal
exit /b 0

REM ===============================================
REM SUBROUTINE: CREATE_UNINSTALLER
REM ===============================================
:CREATE_UNINSTALLER

set UNINSTALL_BATCH=%INSTALL_DIR%\Uninstall.bat
set DESKTOP_SHORTCUT=%USERPROFILE%\Desktop\ExcelProcessor.lnk
set STARTMENU_SHORTCUT=%APPDATA%\Microsoft\Windows\Start Menu\Programs\ExcelProcessor

(
    echo @echo off
    echo title Excel Processor Uninstaller
    echo.
    echo echo.
    echo echo ===============================================
    echo echo  Uninstalling Excel Processor
    echo echo ===============================================
    echo echo.
    echo.
    echo net session ^>nul 2^>^&1
    echo if %%errorLevel%% NEQ 0 ^(
    echo     echo This uninstall requires Administrator privileges
    echo     pause
    echo     exit /b 1
    echo ^)
    echo.
    echo echo - Removing shortcuts...
    echo if exist "%DESKTOP_SHORTCUT%" del "%DESKTOP_SHORTCUT%"
    echo if exist "%STARTMENU_SHORTCUT%" rmdir /s /q "%STARTMENU_SHORTCUT%"
    echo.
    echo echo - Removing installation directory...
    echo if exist "%INSTALL_DIR%" rmdir /s /q "%INSTALL_DIR%"
    echo.
    echo echo.
    echo echo ✅ Uninstall Complete!
    echo echo.
    echo pause
) > "%UNINSTALL_BATCH%"

echo ✅ Uninstaller created: %INSTALL_DIR%\Uninstall.bat

exit /b 0

REM ===============================================
REM END OF SCRIPT
REM ===============================================

