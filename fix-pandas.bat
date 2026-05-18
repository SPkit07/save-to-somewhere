@echo off
REM ==========================================
REM Fix Pandas Build Issue on Windows
REM ==========================================

echo.
echo ===============================================
echo  Fixing Pandas Installation Error
echo ===============================================
echo.

REM Check Python version
python --version

echo.
echo Step 1: Installing pre-built wheels first...
echo.

REM Try installing pandas with binary wheels
pip install --only-binary :all: pandas numpy openpyxl

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Step 2: Trying alternative approach...
    echo Upgrading pip and installing dependencies...
    echo.
    
    python -m pip install --upgrade pip setuptools wheel
    
    echo.
    echo Installing pandas with wheel support...
    pip install pandas openpyxl numpy
    
    if %ERRORLEVEL% NEQ 0 (
        echo.
        echo ====================================================
        echo ERROR: Still having issues with pandas build
        echo ====================================================
        echo.
        echo Solution 1: Install Visual C++ Build Tools
        echo   Download from:
        echo   https://visualstudio.microsoft.com/downloads/
        echo   Search for "Visual Studio Build Tools"
        echo.
        echo Solution 2: Use Python pre-built pandas wheels
        echo   pip install pandas --no-build-isolation
        echo.
        echo Solution 3: Use conda instead of pip
        echo   conda install pandas numpy openpyxl
        echo.
        pause
        exit /b 1
    )
)

echo.
echo ===============================================
echo  Installation Complete!
echo ===============================================
echo.
echo Now run: pip install -r requirements.txt
echo.
pause
