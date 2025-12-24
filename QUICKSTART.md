# Quick Start Guide

Get up and running in 5 minutes!

## 🚀 Fastest Setup (Windows)

1. **Right-click** `install_windows.bat` → **"Run as administrator"**
2. **Double-click** `setup_env.bat` (enter database credentials)
3. **Double-click** `setup_database.bat` (create database)
4. **Double-click** `run_tests.bat` (verify everything works)

Done! 🎉

## 📋 What You Need

- Windows 10/11
- Administrator access
- 5-10 minutes

## ✅ Verify Installation

After running the scripts above, you should see:

```
✓ Python 3.11+ installed
✓ PostgreSQL installed
✓ All dependencies installed
✓ Playwright browser ready
✓ Database initialized
✓ Test scrape successful
```

## 🎯 First Scrape

```bash
py main.py scrape "pizza in New York" --max-results 10
```

## 📊 View Results

**Option 1: Web Dashboard**
```bash
py -m uvicorn api.main:app --reload
```
Open: http://localhost:8000

**Option 2: Export to CSV**
```bash
py main.py export --format csv --output leads.csv
```

**Option 3: View Stats**
```bash
py main.py stats
```

## 🔥 Common Commands

```bash
# Scrape with email extraction
py main.py scrape "hotels in Miami" --extract-emails --max-results 50

# Export leads with phone numbers only
py main.py export --format csv --has-phone --output calls.csv

# Bulk scrape multiple cities
py main.py bulk-scrape --locations "NYC,LA,Chicago" --query "restaurants"

# Start web dashboard
py -m uvicorn api.main:app --host 0.0.0.0 --port 8000
```

## ❓ Having Issues?

See [SETUP_WINDOWS.md](SETUP_WINDOWS.md) for detailed troubleshooting.

## 📖 Full Documentation

See [google-maps-scraper-prd.md](google-maps-scraper-prd.md) for complete feature list.
