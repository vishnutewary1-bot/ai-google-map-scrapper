# MapLeads Pro - Remediation Plan

**Created:** 2026-01-21
**Status:** In Progress

---

## Phase 1: Critical Security Fixes (IMMEDIATE)

### 1.1 Fix SSL Verification (SEC-001)
**File:** `utils/contact_extractor.py`
**Time:** 5 mins

```python
# Change line 198 from:
verify=False

# To:
verify=True  # Or remove the parameter entirely
```

### 1.2 Fix CORS Configuration (SEC-002)
**File:** `api/middleware.py`

```python
# Change from allow_origins=["*"] to:
from config.settings import get_settings

settings = get_settings()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,  # Add to settings.py
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)
```

**Add to `config/settings.py`:**
```python
cors_origins: List[str] = ["http://localhost:8000", "http://localhost:3000"]
```

### 1.3 Implement JWT Authentication (SEC-003)
**File:** `api/middleware.py`

Add JWT verification middleware:
```python
from jose import JWTError, jwt
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer(auto_error=False)

async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not settings.auth_enabled:
        return None

    if not credentials:
        raise HTTPException(status_code=401, detail="Missing authentication token")

    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret_key,
            algorithms=["HS256"]
        )
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
```

### 1.4 Secure JWT Secret (SEC-004)
**File:** `config/settings.py`

Add validation:
```python
@validator('jwt_secret_key')
def validate_jwt_secret(cls, v):
    if v == "your-super-secret-key-change-this-in-production":
        import warnings
        warnings.warn("Using default JWT secret! Set JWT_SECRET_KEY in .env")
    if len(v) < 32:
        raise ValueError("JWT secret must be at least 32 characters")
    return v
```

---

## Phase 2: Database Fixes

### 2.1 Add Job-Lead Relationship (DB-001)
**File:** `database/models.py`

```python
class BusinessLead(Base):
    # Add after existing columns:
    job_id = Column(Integer, ForeignKey('scrape_jobs.id'), nullable=True, index=True)

    # Add relationship
    job = relationship("ScrapeJob", back_populates="leads")

class ScrapeJob(Base):
    # Add relationship
    leads = relationship("BusinessLead", back_populates="job")
```

### 2.2 Add Database Indexes (DB-002)
**File:** `database/models.py`

```python
# Add index=True to these columns:
city = Column(String(100), index=True)
category = Column(String(200), index=True)
phone = Column(String(50), index=True)
email = Column(String(255), index=True)
place_id = Column(String(255), unique=True, index=True)
```

---

## Phase 3: Integration Fixes

### 3.1 Integrate CAPTCHA Solver (INT-001)
**File:** `scraper/browser_engine.py`

```python
# Add import at top:
from utils.captcha_solver import CaptchaSolver

class BrowserEngine:
    def __init__(self):
        self.captcha_solver = CaptchaSolver()

    async def handle_captcha(self, page):
        """Detect and solve CAPTCHA if present."""
        captcha_detected = await page.query_selector('[class*="captcha"]')
        if captcha_detected:
            await self.captcha_solver.solve(page)
```

### 3.2 Integrate Proxy Manager (INT-002)
**File:** `scraper/browser_engine.py`

```python
# Add to launch_browser():
from utils.proxy_manager import ProxyManager

proxy_manager = ProxyManager()
proxy = proxy_manager.get_proxy()

if proxy:
    browser = await playwright.chromium.launch(
        proxy={"server": proxy}
    )
```

### 3.3 Add Rate Limiting to Scrape Endpoint (API-002)
**File:** `api/routes/scraping.py`

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.post("/scrape")
@limiter.limit("5/minute")  # 5 scrape requests per minute
async def scrape(request: Request, scrape_request: ScrapeRequest):
    ...
```

---

## Phase 4: Code Quality Fixes

### 4.1 Remove Duplicate _fetch_leads() (CQ-002)
**File:** `utils/crm_integrations.py`

1. Keep the first implementation (lines 236-256)
2. Delete duplicate at lines 455-473
3. Ensure all callers reference the single method

### 4.2 Fix Bare Exception Handlers (SEC-005)
**File:** `utils/email_verification.py`

```python
# Change from:
except:
    return []

# To:
except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.NoNameservers) as e:
    logger.debug(f"DNS resolution failed: {e}")
    return []
```

### 4.3 Remove sys.path.insert Anti-Pattern (CQ-001)
Create proper package structure with `pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[project]
name = "mapleads-pro"
version = "2.0.0"
dependencies = [
    "fastapi>=0.100.0",
    "playwright>=1.40.0",
    "sqlalchemy>=2.0.0",
    # ... other dependencies
]
```

---

## Phase 5: Testing

### 5.1 Create Test Directory Structure
```
tests/
├── __init__.py
├── conftest.py
├── test_api/
│   ├── __init__.py
│   ├── test_scraping.py
│   ├── test_leads.py
│   └── test_export.py
├── test_scraper/
│   ├── __init__.py
│   ├── test_browser_engine.py
│   └── test_maps_extractor.py
├── test_utils/
│   ├── __init__.py
│   ├── test_deduplicator.py
│   └── test_lead_scoring.py
└── test_database/
    ├── __init__.py
    └── test_models.py
```

### 5.2 Create Test Configuration
**File:** `tests/conftest.py`

```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.app import create_app
from database.models import Base

@pytest.fixture
def test_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine)
    yield TestingSessionLocal()

@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)
```

---

## Phase 6: CI/CD Setup

### 6.1 Create GitHub Actions Workflow
**File:** `.github/workflows/ci.yml`

```yaml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-asyncio
      - name: Run tests
        run: pytest tests/ -v

  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Lint with ruff
        run: |
          pip install ruff
          ruff check .
```

---

## Phase 7: Pre-Deployment Checklist

### 7.1 Update .gitignore
```gitignore
# Environment
.env
.env.local
*.env

# Python
__pycache__/
*.py[cod]
.venv/
venv/

# IDE
.vscode/
.idea/

# Logs
logs/
*.log

# Database
*.db
*.sqlite

# Exports
exports/

# OS
.DS_Store
Thumbs.db
```

### 7.2 Update README.md
- Installation instructions
- Environment setup
- API documentation link
- Contributing guidelines

### 7.3 Final Security Check
- [ ] All `.env` files in .gitignore
- [ ] No hardcoded passwords/keys in code
- [ ] SSL verification enabled
- [ ] CORS restricted to specific origins
- [ ] Authentication implemented

---

## Execution Order Summary

| Step | Description | Priority | Status |
|------|-------------|----------|--------|
| 1 | Fix SSL verification | P0 | Pending |
| 2 | Fix CORS configuration | P0 | Pending |
| 3 | Implement JWT auth | P0 | Pending |
| 4 | Secure JWT secret | P0 | Pending |
| 5 | Add job-lead FK | P1 | Pending |
| 6 | Add DB indexes | P1 | Pending |
| 7 | Integrate CAPTCHA | P1 | Pending |
| 8 | Integrate proxy | P1 | Pending |
| 9 | Add rate limiting | P1 | Pending |
| 10 | Remove duplicate code | P2 | Pending |
| 11 | Fix bare exceptions | P2 | Pending |
| 12 | Create test suite | P2 | Pending |
| 13 | Setup CI/CD | P2 | Pending |
| 14 | Update docs | P3 | Pending |

---

*Update this document as fixes are implemented.*
