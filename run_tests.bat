@echo off
echo ========================================
echo Google Maps Scraper - Test Suite
echo ========================================
echo.

echo Step 1: Running setup verification...
echo ----------------------------------------
py test_setup.py
if %errorLevel% neq 0 (
    echo.
    echo ERROR: Setup verification failed!
    echo Please check the error messages above and fix any issues.
    pause
    exit /b 1
)

echo.
echo Step 2: Initializing database tables...
echo ----------------------------------------
py main.py init-db
if %errorLevel% neq 0 (
    echo.
    echo ERROR: Database initialization failed!
    pause
    exit /b 1
)

echo.
echo Step 3: Running a small test scrape...
echo ----------------------------------------
echo Testing with "pizza in New York" (max 5 results)
echo.
py main.py scrape "pizza in New York" --max-results 5 --headless
if %errorLevel% neq 0 (
    echo.
    echo ERROR: Test scrape failed!
    pause
    exit /b 1
)

echo.
echo Step 4: Checking scraped data...
echo ----------------------------------------
py main.py stats

echo.
echo Step 5: Testing export functionality...
echo ----------------------------------------
py main.py export --format csv --output test_export.csv
if exist test_export.csv (
    echo ✓ Export successful! Check test_export.csv
) else (
    echo WARNING: Export file not created
)

echo.
echo ========================================
echo All tests completed successfully!
echo ========================================
echo.
echo Your scraper is ready to use. Try:
echo   py main.py scrape "your search query" --max-results 10
echo   py main.py stats
echo   py main.py export --format csv --output leads.csv
echo.
echo To start the web dashboard:
echo   py -m uvicorn api.main:app --reload
echo   Then open: http://localhost:8000
echo.
pause
