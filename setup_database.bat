@echo off
echo ========================================
echo PostgreSQL Database Setup
echo ========================================
echo.

echo This script will create the PostgreSQL database and user.
echo.

set /p DB_NAME="Database Name (default: google_maps_scraper): "
if "%DB_NAME%"=="" set DB_NAME=google_maps_scraper

set /p DB_USER="Database User (default: scraper_user): "
if "%DB_USER%"=="" set DB_USER=scraper_user

set /p DB_PASSWORD="Database Password (default: scraper_password): "
if "%DB_PASSWORD%"=="" set DB_PASSWORD=scraper_password

set /p POSTGRES_PASSWORD="PostgreSQL Admin Password (postgres user): "

echo.
echo Creating database and user...
echo.

REM Create database and user
psql -U postgres -c "CREATE DATABASE %DB_NAME%;" 2>nul
if %errorLevel% equ 0 (
    echo ✓ Database '%DB_NAME%' created successfully
) else (
    echo ! Database '%DB_NAME%' might already exist
)

psql -U postgres -c "CREATE USER %DB_USER% WITH PASSWORD '%DB_PASSWORD%';" 2>nul
if %errorLevel% equ 0 (
    echo ✓ User '%DB_USER%' created successfully
) else (
    echo ! User '%DB_USER%' might already exist
)

psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE %DB_NAME% TO %DB_USER%;" 2>nul
echo ✓ Privileges granted to '%DB_USER%'

psql -U postgres -d %DB_NAME% -c "GRANT ALL ON SCHEMA public TO %DB_USER%;" 2>nul
echo ✓ Schema privileges granted

echo.
echo ========================================
echo Database setup complete!
echo ========================================
echo.
echo Database: %DB_NAME%
echo User: %DB_USER%
echo Password: %DB_PASSWORD%
echo.
echo Make sure to update these credentials in your .env file
echo.
pause
