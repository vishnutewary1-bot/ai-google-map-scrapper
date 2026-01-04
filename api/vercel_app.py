"""
Vercel-compatible FastAPI application
This version excludes Playwright/browser automation (not supported on Vercel)
Scraping must be done locally and data synced to this API
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
import json
import os

# Initialize FastAPI app
app = FastAPI(
    title="MapLeads Pro API",
    description="Google Maps Lead Scraper - Cloud API",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage (for demo - use Vercel Postgres or Supabase in production)
leads_storage: List[Dict] = []
scrape_jobs: List[Dict] = []

# ==================== MODELS ====================

class Lead(BaseModel):
    id: Optional[int] = None
    name: str
    address: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    rating: Optional[float] = None
    reviews_count: Optional[int] = None
    category: Optional[str] = None
    google_maps_url: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    email: Optional[str] = None
    opening_hours: Optional[str] = None
    price_level: Optional[str] = None
    created_at: Optional[str] = None

class LeadBatch(BaseModel):
    leads: List[Lead]
    source: Optional[str] = "local_scraper"

class ScrapeJob(BaseModel):
    query: str
    location: str
    max_results: int = 100
    status: str = "pending"

class GoogleSheetsExport(BaseModel):
    spreadsheet_id: str
    worksheet_name: str = "Leads"
    lead_ids: Optional[List[int]] = None

class LeadScoreRequest(BaseModel):
    lead_ids: Optional[List[int]] = None

# ==================== DASHBOARD ====================

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Main dashboard"""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>MapLeads Pro - Dashboard</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link href="https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css" rel="stylesheet">
        <style>
            .gradient-bg { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }
            .card { background: white; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
        </style>
    </head>
    <body class="bg-gray-100 min-h-screen">
        <nav class="gradient-bg text-white p-4 shadow-lg">
            <div class="container mx-auto flex justify-between items-center">
                <h1 class="text-2xl font-bold">MapLeads Pro</h1>
                <span class="bg-green-400 px-3 py-1 rounded-full text-sm">Cloud API</span>
            </div>
        </nav>

        <div class="container mx-auto p-6">
            <div class="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
                <div class="card p-6">
                    <h3 class="text-gray-500 text-sm">Total Leads</h3>
                    <p class="text-3xl font-bold text-purple-600" id="totalLeads">0</p>
                </div>
                <div class="card p-6">
                    <h3 class="text-gray-500 text-sm">With Phone</h3>
                    <p class="text-3xl font-bold text-green-600" id="withPhone">0</p>
                </div>
                <div class="card p-6">
                    <h3 class="text-gray-500 text-sm">With Email</h3>
                    <p class="text-3xl font-bold text-blue-600" id="withEmail">0</p>
                </div>
                <div class="card p-6">
                    <h3 class="text-gray-500 text-sm">Avg Rating</h3>
                    <p class="text-3xl font-bold text-yellow-600" id="avgRating">0</p>
                </div>
            </div>

            <div class="card p-6 mb-8">
                <h2 class="text-xl font-bold mb-4">Quick Actions</h2>
                <div class="flex flex-wrap gap-4">
                    <a href="/docs" class="bg-purple-600 text-white px-6 py-2 rounded-lg hover:bg-purple-700">API Docs</a>
                    <button onclick="exportCSV()" class="bg-green-600 text-white px-6 py-2 rounded-lg hover:bg-green-700">Export CSV</button>
                    <button onclick="refreshStats()" class="bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700">Refresh</button>
                </div>
            </div>

            <div class="card p-6">
                <h2 class="text-xl font-bold mb-4">Recent Leads</h2>
                <div class="overflow-x-auto">
                    <table class="w-full text-left">
                        <thead class="bg-gray-50">
                            <tr>
                                <th class="p-3">Name</th>
                                <th class="p-3">Phone</th>
                                <th class="p-3">Rating</th>
                                <th class="p-3">Category</th>
                            </tr>
                        </thead>
                        <tbody id="leadsTable">
                            <tr><td colspan="4" class="p-3 text-center text-gray-500">No leads yet. Sync from local scraper.</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>

            <div class="card p-6 mt-8">
                <h2 class="text-xl font-bold mb-4">How to Use</h2>
                <ol class="list-decimal list-inside space-y-2 text-gray-700">
                    <li>Run the scraper locally: <code class="bg-gray-100 px-2 py-1 rounded">python run.py</code></li>
                    <li>Scrape leads using the local dashboard at <code class="bg-gray-100 px-2 py-1 rounded">http://localhost:8000</code></li>
                    <li>Sync leads to cloud using: <code class="bg-gray-100 px-2 py-1 rounded">POST /api/leads/sync</code></li>
                    <li>Export to Google Sheets from anywhere!</li>
                </ol>
            </div>
        </div>

        <script>
            async function refreshStats() {
                const resp = await fetch('/api/stats');
                const data = await resp.json();
                document.getElementById('totalLeads').textContent = data.total_leads;
                document.getElementById('withPhone').textContent = data.with_phone;
                document.getElementById('withEmail').textContent = data.with_email;
                document.getElementById('avgRating').textContent = data.avg_rating.toFixed(1);

                // Load leads
                const leadsResp = await fetch('/api/leads?limit=10');
                const leadsData = await leadsResp.json();
                const tbody = document.getElementById('leadsTable');
                if (leadsData.leads && leadsData.leads.length > 0) {
                    tbody.innerHTML = leadsData.leads.map(lead => `
                        <tr class="border-b">
                            <td class="p-3">${lead.name}</td>
                            <td class="p-3">${lead.phone || '-'}</td>
                            <td class="p-3">${lead.rating || '-'}</td>
                            <td class="p-3">${lead.category || '-'}</td>
                        </tr>
                    `).join('');
                }
            }

            async function exportCSV() {
                window.location.href = '/api/export/csv';
            }

            refreshStats();
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html)

# ==================== LEADS API ====================

@app.get("/api/leads")
async def get_leads(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    category: Optional[str] = None
):
    """Get all leads"""
    filtered = leads_storage
    if category:
        filtered = [l for l in leads_storage if l.get('category') == category]

    return {
        "leads": filtered[offset:offset+limit],
        "total": len(filtered),
        "limit": limit,
        "offset": offset
    }

@app.post("/api/leads/sync")
async def sync_leads(batch: LeadBatch):
    """Sync leads from local scraper to cloud"""
    global leads_storage

    added = 0
    for lead in batch.leads:
        lead_dict = lead.dict()
        lead_dict['id'] = len(leads_storage) + 1
        lead_dict['created_at'] = datetime.now().isoformat()
        lead_dict['synced_from'] = batch.source
        leads_storage.append(lead_dict)
        added += 1

    return {
        "success": True,
        "added": added,
        "total_leads": len(leads_storage)
    }

@app.get("/api/leads/{lead_id}")
async def get_lead(lead_id: int):
    """Get single lead by ID"""
    for lead in leads_storage:
        if lead.get('id') == lead_id:
            return lead
    raise HTTPException(status_code=404, detail="Lead not found")

@app.delete("/api/leads/{lead_id}")
async def delete_lead(lead_id: int):
    """Delete a lead"""
    global leads_storage
    leads_storage = [l for l in leads_storage if l.get('id') != lead_id]
    return {"success": True}

@app.delete("/api/leads")
async def delete_all_leads():
    """Delete all leads"""
    global leads_storage
    count = len(leads_storage)
    leads_storage = []
    return {"success": True, "deleted": count}

# ==================== STATS ====================

@app.get("/api/stats")
async def get_stats():
    """Get dashboard statistics"""
    total = len(leads_storage)
    with_phone = len([l for l in leads_storage if l.get('phone')])
    with_email = len([l for l in leads_storage if l.get('email')])
    ratings = [l.get('rating', 0) for l in leads_storage if l.get('rating')]
    avg_rating = sum(ratings) / len(ratings) if ratings else 0

    return {
        "total_leads": total,
        "with_phone": with_phone,
        "with_email": with_email,
        "avg_rating": avg_rating
    }

# ==================== EXPORT ====================

@app.get("/api/export/csv")
async def export_csv():
    """Export leads to CSV"""
    if not leads_storage:
        return JSONResponse(content={"error": "No leads to export"}, status_code=400)

    import csv
    from io import StringIO

    output = StringIO()
    if leads_storage:
        writer = csv.DictWriter(output, fieldnames=leads_storage[0].keys())
        writer.writeheader()
        writer.writerows(leads_storage)

    from fastapi.responses import Response
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=leads.csv"}
    )

@app.get("/api/export/json")
async def export_json():
    """Export leads to JSON"""
    return JSONResponse(content={"leads": leads_storage})

@app.post("/api/export/google-sheets")
async def export_to_google_sheets(request: GoogleSheetsExport):
    """Export leads to Google Sheets"""
    try:
        import gspread
        from google.oauth2.service_account import Credentials

        # Get credentials from environment variable (JSON string)
        creds_json = os.environ.get('GOOGLE_CREDENTIALS_JSON')
        if not creds_json:
            raise HTTPException(status_code=500, detail="Google credentials not configured")

        creds_dict = json.loads(creds_json)

        SCOPES = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]

        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        client = gspread.authorize(creds)

        # Open spreadsheet
        spreadsheet = client.open_by_key(request.spreadsheet_id)

        # Get or create worksheet
        try:
            worksheet = spreadsheet.worksheet(request.worksheet_name)
        except gspread.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(title=request.worksheet_name, rows=1000, cols=20)

        # Prepare data
        if request.lead_ids:
            export_leads = [l for l in leads_storage if l.get('id') in request.lead_ids]
        else:
            export_leads = leads_storage

        if not export_leads:
            raise HTTPException(status_code=400, detail="No leads to export")

        # Headers
        headers = ['Name', 'Phone', 'Email', 'Website', 'Address', 'Rating', 'Reviews', 'Category', 'Google Maps URL']

        # Prepare rows
        rows = [headers]
        for lead in export_leads:
            rows.append([
                lead.get('name', ''),
                lead.get('phone', ''),
                lead.get('email', ''),
                lead.get('website', ''),
                lead.get('address', ''),
                str(lead.get('rating', '')),
                str(lead.get('reviews_count', '')),
                lead.get('category', ''),
                lead.get('google_maps_url', '')
            ])

        # Clear and update
        worksheet.clear()
        worksheet.update('A1', rows)

        return {
            "success": True,
            "exported": len(export_leads),
            "spreadsheet_id": request.spreadsheet_id,
            "worksheet": request.worksheet_name
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==================== LEAD SCORING ====================

@app.post("/api/leads/score")
async def score_leads(request: LeadScoreRequest):
    """Score leads based on data quality"""
    scored = []

    target_leads = leads_storage
    if request.lead_ids:
        target_leads = [l for l in leads_storage if l.get('id') in request.lead_ids]

    for lead in target_leads:
        score = 0

        # Contact info (40 points)
        if lead.get('phone'): score += 20
        if lead.get('email'): score += 20

        # Online presence (20 points)
        if lead.get('website'): score += 20

        # Reputation (25 points)
        rating = lead.get('rating', 0)
        if rating >= 4.5: score += 25
        elif rating >= 4.0: score += 20
        elif rating >= 3.5: score += 15
        elif rating >= 3.0: score += 10

        # Engagement (15 points)
        reviews = lead.get('reviews_count', 0)
        if reviews >= 100: score += 15
        elif reviews >= 50: score += 12
        elif reviews >= 20: score += 8
        elif reviews >= 5: score += 5

        # Update lead with score
        lead['score'] = score
        lead['score_label'] = 'Hot' if score >= 80 else 'Warm' if score >= 50 else 'Cold'
        scored.append(lead)

    return {
        "success": True,
        "scored": len(scored),
        "leads": scored
    }

# ==================== INTEGRATIONS STATUS ====================

@app.get("/api/integrations/status")
async def get_integrations_status():
    """Check status of all integrations"""
    return {
        "google_sheets": {
            "enabled": os.environ.get('GOOGLE_SHEETS_ENABLED', 'false').lower() == 'true',
            "configured": bool(os.environ.get('GOOGLE_CREDENTIALS_JSON'))
        },
        "database": {
            "type": "in-memory",
            "note": "Use Vercel Postgres or Supabase for persistence"
        },
        "scraper": {
            "note": "Run scraper locally and sync leads via /api/leads/sync"
        }
    }

# ==================== HEALTH ====================

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    }
