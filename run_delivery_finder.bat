@echo off
title Delivery Swing Finder - Setup ^& Run
color 0A

echo ============================================
echo  DELIVERY SWING FINDER - Auto Setup ^& Run
echo ============================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found!
    echo Download from: https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during install.
    pause
    exit /b 1
)
echo [OK] Python found
python --version

:: Check pip
pip --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] pip not found. Reinstall Python with pip included.
    pause
    exit /b 1
)
echo [OK] pip found
echo.

:: Install dependencies
echo [STEP 1] Installing dependencies...
pip install playwright yfinance pandas tabulate colorama --quiet
if errorlevel 1 (
    echo [ERROR] pip install failed. Check internet connection.
    pause
    exit /b 1
)
echo [OK] Dependencies installed
echo.

:: Install Playwright Chromium
echo [STEP 2] Installing Playwright Chromium (one-time ~150MB)...
playwright install chromium
if errorlevel 1 (
    echo [WARN] Playwright install may have failed. Trying anyway...
)
echo [OK] Chromium ready
echo.

:: Check script exists
if not exist "%~dp0delivery_swing_finder.py" (
    echo [ERROR] delivery_swing_finder.py not found!
    echo Place it in the same folder as this BAT file: %~dp0
    pause
    exit /b 1
)

:: Run it
echo [STEP 3] Running Delivery Swing Finder...
echo.
python "%~dp0delivery_swing_finder.py" --index "Nifty 50" --top 15

echo.
echo ============================================
echo  Done! CSV saved in: %~dp0
echo ============================================
pause
