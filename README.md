# MapLeads Pro - Google Maps Lead Scraper

A powerful, full-featured Google Maps lead scraper with AI-powered enrichment, multi-format export, and CRM integrations.

## Features

- **Google Maps Scraping**: Extract business leads from Google Maps with detailed information
- **Contact Enrichment**: Extract emails, phone numbers, and contact persons from business websites
- **Social Media Discovery**: Find Facebook, Instagram, LinkedIn, Twitter, and YouTube profiles
- **Lead Scoring**: AI-powered lead quality scoring with grade assignments
- **Email Verification**: Verify email deliverability with multiple providers
- **Advanced Deduplication**: Fuzzy matching and geographic proximity detection
- **Multi-Format Export**: Excel, CSV, JSON, Google Sheets
- **CRM Integration**: HubSpot and Salesforce connectors
- **Real-time Progress**: WebSocket-based live updates during scraping
- **Scheduling**: Schedule recurring scrape jobs

## Quick Start

### Prerequisites

- Python 3.11+
- Playwright browsers

### Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/mapleads-pro.git
cd mapleads-pro
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows
```

3. Install dependencies:
```bash
pip install -r requirements-local.txt
```

4. Install Playwright browsers:
```bash
playwright install chromium
```

5. Configure environment:
```bash
cp .env.example .env
# Edit .env with your settings
```

6. Run the server:
```bash
python run.py
```

7. Open in browser:
- Frontend: http://localhost:9000/app
- API Docs: http://localhost:9000/api/docs
- Health Check: http://localhost:9000/api/health

## Configuration

Copy `.env.example` to `.env` and configure:

### Required Settings
- `DB_TYPE`: Database type (`sqlite` or `postgresql`)
- `DB_NAME`: Database name

### Optional Integrations
- `CAPTCHA_API_KEY`: 2Captcha API key for CAPTCHA solving
- `GOOGLE_CREDENTIALS_PATH`: Path to Google Sheets credentials
- `HUBSPOT_ACCESS_TOKEN`: HubSpot CRM integration
- `SALESFORCE_*`: Salesforce CRM integration
- `OPENAI_API_KEY`: AI-powered lead scoring

## API Endpoints

### Scraping
- `POST /api/scrape` - Start a new scraping job
- `GET /api/jobs` - List all scraping jobs
- `GET /api/jobs/{id}` - Get job status

### Leads
- `GET /api/leads` - List leads with filtering and pagination
- `GET /api/leads/{id}` - Get lead details
- `DELETE /api/leads/{id}` - Delete a lead

### Export
- `POST /api/export` - Export leads (excel, csv, json)
- `GET /api/export/download/{filename}` - Download exported file

### Analytics
- `GET /api/analytics/overview` - Dashboard statistics
- `GET /api/analytics/quality` - Lead quality distribution

## Architecture

```
mapleads-pro/
├── api/                 # FastAPI application
│   ├── routes/         # API endpoints
│   ├── schemas/        # Pydantic models
│   └── services/       # Business logic
├── scraper/            # Scraping engine
│   ├── extractors/     # Data extractors
│   └── browser_engine.py
├── database/           # SQLAlchemy models
├── utils/              # Utilities
│   ├── crm_integrations.py
│   ├── email_verification.py
│   └── lead_scoring.py
├── frontend/           # Static web UI
└── config/             # Configuration
```

## Security Notes

- Never commit `.env` files with real credentials
- Set a strong `JWT_SECRET_KEY` for production
- Configure CORS origins for production deployment
- Enable authentication for public deployments

## License

MIT License

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request
