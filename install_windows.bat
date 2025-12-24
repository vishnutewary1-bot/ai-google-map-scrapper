@echo off
echo ========================================
echo Google Maps Scraper - Windows Setup
echo ========================================
echo.

REM Check if running as administrator
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo ERROR: This script requires Administrator privileges
    echo Please right-click and select "Run as administrator"
    pause
    exit /b 1
)

echo Step 1: Installing Python 3.11 via winget...
echo ----------------------------------------
winget install -e --id Python.Python.3.11 --silent --accept-package-agreements --accept-source-agreements
if %errorLevel% neq 0 (
    echo ERROR: Failed to install Python
    echo Please install Python manually from https://www.python.org/downloads/
    pause
    exit /b 1
)

echo.
echo Step 2: Refreshing environment variables...
echo ----------------------------------------
refreshenv

echo.
echo Step 3: Verifying Python installation...
echo ----------------------------------------
timeout /t 5 /nobreak >nul
py --version
if %errorLevel% neq 0 (
    python --version
    if %errorLevel% neq 0 (
        echo ERROR: Python not found in PATH
        echo Please close this window and reopen a new terminal
        pause
        exit /b 1
    )
)

echo.
echo Step 4: Upgrading pip...
echo ----------------------------------------
py -m pip install --upgrade pip

echo.
echo Step 5: Installing Python dependencies...
echo ----------------------------------------
py -m pip install -r requirements.txt
if %errorLevel% neq 0 (
    echo ERROR: Failed to install Python dependencies
    pause
    exit /b 1
)

echo.
echo Step 6: Installing Playwright browsers...
echo ----------------------------------------
py -m playwright install chromium
if %errorLevel% neq 0 (
    echo ERROR: Failed to install Playwright browsers
    pause
    exit /b 1
)

echo.
echo Step 7: Installing PostgreSQL...
echo ----------------------------------------
winget install -e --id PostgreSQL.PostgreSQL.16 --silent --accept-package-agreements --accept-source-agreements
if %errorLevel% neq 0 (
    echo WARNING: Failed to install PostgreSQL automatically
    echo Please install PostgreSQL manually from https://www.postgresql.org/download/windows/
)

echo.
echo ========================================
echo Installation Complete!
echo ========================================
echo.
echo Next steps:
echo 1. Configure PostgreSQL (create database and user)
echo 2. Copy .env.example to .env and update settings
echo 3. Run: py main.py init-db
echo 4. Run: py test_setup.py
echo.
pause
