# Windows Installation Guide

Complete step-by-step guide to set up the Google Maps Lead Scraper on Windows.

## Prerequisites

- Windows 10/11
- Administrator access
- Internet connection

## Quick Setup (Automated)

### Option 1: Full Automated Installation

1. **Right-click** on `install_windows.bat` and select **"Run as administrator"**
2. Wait for the installation to complete (10-15 minutes)
3. Follow the post-installation steps below

### Option 2: Step-by-Step Installation

Follow these steps in order:

#### Step 1: Install Python & Dependencies

Right-click `install_windows.bat` and select "Run as administrator"

This will:
- Install Python 3.11
- Install all Python dependencies
- Install Playwright Chromium browser
- Install PostgreSQL

#### Step 2: Configure Environment

Double-click `setup_env.bat` and provide:
- PostgreSQL host (default: localhost)
- PostgreSQL port (default: 5432)
- Database name (default: google_maps_scraper)
- Database user (default: postgres)
- Database password

#### Step 3: Setup Database

Double-click `setup_database.bat` to:
- Create the database
- Create database user
- Grant necessary privileges

#### Step 4: Run Tests

Double-click `run_tests.bat` to:
- Verify installation
- Initialize database tables
- Run a test scrape
- Test export functionality

## Manual Installation

If automated scripts fail, follow these manual steps:

### 1. Install Python 3.11+

Download from: https://www.python.org/downloads/

**Important:** Check "Add Python to PATH" during installation

### 2. Install PostgreSQL

Download from: https://www.postgresql.org/download/windows/

During installation:
- Remember the postgres user password
- Use default port 5432

### 3. Install Dependencies

Open Command Prompt or PowerShell:

```bash
# Upgrade pip
py -m pip install --upgrade pip

# Install Python packages
py -m pip install -r requirements.txt

# Install Playwright browsers
py -m playwright install chromium
```

### 4. Configure Database

Open pgAdmin or use psql:

```sql
CREATE DATABASE google_maps_scraper;
CREATE USER scraper_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE google_maps_scraper TO scraper_user;
\c google_maps_scraper
GRANT ALL ON SCHEMA public TO scraper_user;
```

### 5. Configure Environment

Copy `.env.example` to `.env` and update:

```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=google_maps_scraper
DB_USER=scraper_user
DB_PASSWORD=your_password
```

### 6. Initialize Database

```bash
py main.py init-db
```

### 7. Test Installation

```bash
py test_setup.py
```

## Usage

### CLI Commands

```bash
# Run a scrape
py main.py scrape "pizza in New York" --max-results 50

# View statistics
py main.py stats

# Export leads
py main.py export --format csv --output leads.csv

# Export with filters
py main.py export --format csv --output leads.csv --has-phone --has-email
```

### Web Dashboard

```bash
# Start the web server
py -m uvicorn api.main:app --reload

# Open browser to:
http://localhost:8000
```

### Advanced Features

```bash
# Bulk scraping multiple locations
py main.py bulk-scrape --locations "New York,Los Angeles,Chicago" --query "restaurants"

# Scrape with email enrichment
py main.py scrape "hotels in Miami" --max-results 100 --extract-emails

# Export for cold calling
py main.py export --format cold-calling --has-phone --output calls.csv
```

## Troubleshooting

### Python not found

1. Close all terminals/command prompts
2. Reinstall Python with "Add to PATH" checked
3. Reopen terminal and try again

### PostgreSQL connection failed

1. Check PostgreSQL service is running:
   - Open Services (Win + R, type `services.msc`)
   - Find "postgresql-x64-16" service
   - Ensure it's running

2. Verify credentials in `.env` file

3. Test connection:
   ```bash
   psql -U postgres -h localhost
   ```

### Playwright browser installation failed

```bash
# Install manually
py -m playwright install chromium

# If still failing, install system dependencies
py -m playwright install-deps chromium
```

### Permission denied errors

Run Command Prompt or PowerShell as Administrator

### Module not found errors

```bash
# Reinstall dependencies
py -m pip install -r requirements.txt --force-reinstall
```

## Next Steps

1. ✅ Installation complete
2. ✅ Database configured
3. ✅ Test scrape successful
4. 🚀 Start scraping leads!
5. 📊 Use web dashboard for monitoring
6. 📤 Export leads in various formats

## Performance Tips

- Use `--headless` flag for faster scraping
- Adjust `MAX_REQUESTS_PER_HOUR` in `.env` to avoid rate limits
- Enable proxy rotation for high-volume scraping
- Use bulk scraping for multiple locations

## Support

For issues, check:
- [PRD Document](google-maps-scraper-prd.md) for feature details
- Test logs in console output
- PostgreSQL logs in PostgreSQL data directory
