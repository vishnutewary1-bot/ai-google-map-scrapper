@echo off
echo ========================================
echo Setting up Environment Configuration
echo ========================================
echo.

if exist .env (
    echo WARNING: .env file already exists
    set /p OVERWRITE="Do you want to overwrite it? (y/n): "
    if /i not "%OVERWRITE%"=="y" (
        echo Keeping existing .env file
        goto :EOF
    )
)

echo Creating .env file from template...
copy .env.example .env >nul

echo.
echo Please provide the following configuration details:
echo.

set /p DB_HOST="PostgreSQL Host (default: localhost): "
if "%DB_HOST%"=="" set DB_HOST=localhost

set /p DB_PORT="PostgreSQL Port (default: 5432): "
if "%DB_PORT%"=="" set DB_PORT=5432

set /p DB_NAME="Database Name (default: google_maps_scraper): "
if "%DB_NAME%"=="" set DB_NAME=google_maps_scraper

set /p DB_USER="Database User (default: postgres): "
if "%DB_USER%"=="" set DB_USER=postgres

set /p DB_PASSWORD="Database Password: "
if "%DB_PASSWORD%"=="" set DB_PASSWORD=postgres

echo.
echo Updating .env file...

powershell -Command "(Get-Content .env) -replace 'DB_HOST=.*', 'DB_HOST=%DB_HOST%' | Set-Content .env"
powershell -Command "(Get-Content .env) -replace 'DB_PORT=.*', 'DB_PORT=%DB_PORT%' | Set-Content .env"
powershell -Command "(Get-Content .env) -replace 'DB_NAME=.*', 'DB_NAME=%DB_NAME%' | Set-Content .env"
powershell -Command "(Get-Content .env) -replace 'DB_USER=.*', 'DB_USER=%DB_USER%' | Set-Content .env"
powershell -Command "(Get-Content .env) -replace 'DB_PASSWORD=.*', 'DB_PASSWORD=%DB_PASSWORD%' | Set-Content .env"

echo.
echo ========================================
echo Environment configuration complete!
echo ========================================
echo.
echo Configuration saved to .env
echo.
pause
