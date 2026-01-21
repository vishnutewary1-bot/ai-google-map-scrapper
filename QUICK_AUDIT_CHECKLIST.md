# Quick Code Audit Checklist
## MapLeads Pro - Execute This Systematically

---

## 🔴 CRITICAL CHECKS (Do First)

### Security Scan
```
□ Search: verify=False         → Find insecure SSL
□ Search: except:              → Find bare exception handlers
□ Search: password|secret|key  → Find hardcoded credentials
□ Search: @app.get|@app.post   → Check if auth middleware exists
□ Search: sql|query|execute    → Check for SQL injection
□ Search: innerHTML|document.write → Check for XSS
```

### Authentication Status
```
□ api/middleware.py     → Is JWT middleware implemented?
□ api/routes/*.py       → Are routes protected?
□ config/settings.py    → Is AUTH_ENABLED used?
```

---

## 🟡 CODE QUALITY CHECKS

### Duplicate Code Search
```
□ crm_integrations.py:236-256 vs 455-473  → _fetch_leads() duplicate
□ Search: def extract_email              → Check for duplicates
□ Search: def extract_phone              → Check for duplicates
□ Search: async def fetch                → Check for duplicates
```

### Unused Code Detection
```
□ Run: pylint --disable=all --enable=W0611,W0612 *.py
□ Search: # TODO|# FIXME                 → Unresolved todos
□ Search: def .*\(                       → Then check if called
```

### Type Hint Issues
```
□ Search: Optional[callable]  → Should be Optional[Callable]
□ Search: def .*\):$         → Missing return types
□ Search: -> None:           → Verify actually returns None
```

---

## 🟢 INTEGRATION CHECKS

### Feature Connection Status
| Feature | Check Command | Expected |
|---------|---------------|----------|
| CAPTCHA | `grep -r "captcha_solver" browser_engine.py` | Should find import & usage |
| Proxy | `grep -r "proxy_manager" browser_engine.py` | Should find import & usage |
| Email Verify | `grep -r "email_verification" scrape_service.py` | Should find import & usage |
| Lead Scoring | `grep -r "lead_scoring" lead_service.py` | Should find auto-trigger |
| Scheduler | `grep -r "scheduler" routes/` | Should find API endpoints |

---

## 🔵 FILE-BY-FILE AUDIT ORDER

### Priority 1: Core Scraper
```
1. □ scraper/browser_engine.py
   - Anti-detection working?
   - Proxy integration?
   - CAPTCHA integration?

2. □ scraper/unified_scraper.py
   - Error handling complete?
   - Progress callbacks?
   - Deduplication integrated?

3. □ scraper/extractors/maps_extractor.py
   - All selectors current?
   - Fallbacks working?
   - Address parsing correct?
```

### Priority 2: API Layer
```
4. □ api/app.py
   - Auth middleware?
   - CORS correct?
   - Error handlers?

5. □ api/routes/scraping.py
   - Input validation?
   - Error responses?
   - Job tracking?

6. □ api/routes/leads.py
   - All filters working?
   - Pagination correct?
   - Bulk operations?

7. □ api/routes/export.py
   - All formats working?
   - Large file handling?
   - Error handling?
```

### Priority 3: Database
```
8. □ database/models.py
   - Foreign keys defined?
   - Indexes added?
   - All columns used?

9. □ database/connection.py
   - Pooling configured?
   - Transactions handled?
```

### Priority 4: Utilities
```
10. □ utils/exporter.py
11. □ utils/crm_integrations.py (known duplicate)
12. □ utils/email_verification.py (check integration)
13. □ utils/lead_scoring.py (check auto-trigger)
14. □ utils/deduplicator.py (check integration)
```

### Priority 5: Frontend
```
15. □ frontend/app.js
    - Console errors?
    - WebSocket reconnection?
    - Error handling?
```

---

## 📋 TESTING REQUIREMENTS

### Must Test Before Deploy
```
□ python run.py                    → Server starts
□ curl localhost:9000/api/health   → Returns OK
□ POST /api/scrape                 → Scraping works
□ GET /api/leads                   → Leads return
□ GET /api/export/excel            → Excel downloads
□ GET /api/export/csv              → CSV downloads
□ GET /api/export/json             → JSON downloads
□ WebSocket connection             → Real-time updates
```

### Export Format Verification
```
□ Excel: Open in Excel, check columns
□ CSV: Open in text editor, check encoding
□ JSON: Validate structure
□ 1000+ rows: No memory crash
□ Special chars: Hindi/Chinese/emoji preserved
```

---

## 🚀 PRE-GITHUB CHECKLIST

```
□ .env removed from git
□ .gitignore complete
□ No passwords in code
□ README.md updated
□ Tests passing
□ Lint passing
□ All features verified
```

---

## OUTPUT FILES TO CREATE

```
ISSUES.md           → All issues found
REMEDIATION_PLAN.md → Fix plan
tests/              → Test suite
.github/workflows/  → CI/CD
```

---

*Execute this checklist systematically for complete audit*
