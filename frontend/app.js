// Configuration
const API_URL = window.location.origin + '/api';
const WS_URL = window.location.origin.replace('http', 'ws') + '/ws';

let ws = null;
let leadsDataTable = null;
let jobsDataTable = null;
let charts = {};

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    console.log('Dashboard initializing...');

    // Load initial data
    loadStats();
    loadRecentJobs();
    connectWebSocket();

    // Set up auto-refresh
    setInterval(loadStats, 30000); // Every 30 seconds
    setInterval(loadRecentJobs, 60000); // Every minute

    // Initialize settings from localStorage
    loadSavedSettings();
});

// Page Navigation
function showPage(pageName, evt) {
    // Update nav items
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.remove('active');
    });

    // Handle the event properly - evt might be undefined if called programmatically
    if (evt && evt.target) {
        const navItem = evt.target.closest('.nav-item');
        if (navItem) {
            navItem.classList.add('active');
        }
    } else {
        // Find and activate the correct nav item by page name
        document.querySelectorAll('.nav-item').forEach(item => {
            if (item.textContent.toLowerCase().includes(pageName.toLowerCase()) ||
                item.querySelector('span')?.textContent.toLowerCase().includes(pageName.toLowerCase())) {
                item.classList.add('active');
            }
        });
    }

    // Update pages
    document.querySelectorAll('.page').forEach(page => {
        page.classList.remove('active');
    });
    document.getElementById('page-' + pageName).classList.add('active');

    // Update page title
    const titles = {
        'dashboard': 'Dashboard',
        'scraper': 'New Scrape Job',
        'jobs': 'Jobs Management',
        'leads': 'Leads Database',
        'bulk': 'Bulk Scraping',
        'export': 'Export Data',
        'analytics': 'Analytics',
        'settings': 'Settings'
    };
    document.getElementById('pageTitle').textContent = titles[pageName] || pageName;

    // Load page-specific data
    if (pageName === 'jobs') loadJobs();
    if (pageName === 'leads') loadLeads();
    if (pageName === 'analytics') loadAnalytics();
    if (pageName === 'settings') loadSettingsData();
}

// Load Statistics
async function loadStats() {
    try {
        const response = await fetch(`${API_URL}/stats`);
        const stats = await response.json();

        // Update stat cards
        document.getElementById('stat-total').textContent = stats.total_leads.toLocaleString();
        document.getElementById('stat-phone').textContent = stats.leads_with_phone.toLocaleString();
        document.getElementById('stat-email').textContent = stats.leads_with_email.toLocaleString();
        document.getElementById('stat-quality').textContent = stats.average_quality_score.toFixed(1) + '%';

        // Calculate percentages
        const phonePercent = stats.total_leads > 0 ? (stats.leads_with_phone / stats.total_leads * 100).toFixed(1) : 0;
        const emailPercent = stats.total_leads > 0 ? (stats.leads_with_email / stats.total_leads * 100).toFixed(1) : 0;

        document.getElementById('stat-phone-percent').textContent = phonePercent + '% of total';
        document.getElementById('stat-email-percent').textContent = emailPercent + '% of total';

        // Quality description
        const quality = stats.average_quality_score;
        let qualityDesc = 'No data';
        if (quality >= 80) qualityDesc = 'Excellent';
        else if (quality >= 60) qualityDesc = 'Good';
        else if (quality >= 40) qualityDesc = 'Fair';
        else if (quality > 0) qualityDesc = 'Poor';
        document.getElementById('stat-quality-desc').textContent = qualityDesc;

        // Update system info
        document.getElementById('sysInfoLeads').textContent = stats.total_leads.toLocaleString();

    } catch (error) {
        console.error('Error loading stats:', error);
        showNotification('Failed to load statistics', 'error');
    }
}

// Load Recent Jobs
async function loadRecentJobs() {
    try {
        const response = await fetch(`${API_URL}/jobs?limit=5`);
        const jobs = await response.json();

        const tbody = document.getElementById('recentJobsBody');

        if (jobs.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; padding: 2rem;">No jobs yet</td></tr>';
            return;
        }

        tbody.innerHTML = jobs.map(job => `
            <tr>
                <td><strong>#${job.id}</strong></td>
                <td>${job.search_query} ${job.location ? 'in ' + job.location : ''}</td>
                <td>${getStatusBadge(job.status)}</td>
                <td>
                    <div style="margin-bottom: 0.25rem;">${job.leads_scraped} / ${job.leads_target}</div>
                    <div class="progress">
                        <div class="progress-bar" style="width: ${getProgress(job)}%"></div>
                    </div>
                </td>
                <td>${formatDate(job.started_at)}</td>
            </tr>
        `).join('');

    } catch (error) {
        console.error('Error loading recent jobs:', error);
    }
}

// Load All Jobs
async function loadJobs() {
    try {
        const response = await fetch(`${API_URL}/jobs?limit=100`);
        const jobs = await response.json();

        const tbody = document.getElementById('jobsBody');
        tbody.innerHTML = jobs.map(job => `
            <tr>
                <td><strong>#${job.id}</strong></td>
                <td>${job.search_query}</td>
                <td>${job.location || '-'}</td>
                <td>${getStatusBadge(job.status)}</td>
                <td>
                    <div style="margin-bottom: 0.25rem;">${job.leads_scraped} / ${job.leads_target}</div>
                    <div class="progress">
                        <div class="progress-bar" style="width: ${getProgress(job)}%"></div>
                    </div>
                </td>
                <td>${formatDate(job.started_at)}</td>
                <td>${job.completed_at ? formatDate(job.completed_at) : '-'}</td>
                <td>
                    <button class="action-btn" onclick="viewJobDetails(${job.id})" title="View Details">
                        <i class="fas fa-eye"></i>
                    </button>
                    ${job.status === 'failed' ? `
                        <button class="action-btn" onclick="retryJob(${job.id})" title="Retry">
                            <i class="fas fa-redo"></i>
                        </button>
                    ` : ''}
                    ${job.status === 'running' ? `
                        <button class="action-btn" onclick="pauseJob(${job.id})" title="Pause">
                            <i class="fas fa-pause"></i>
                        </button>
                    ` : ''}
                    ${job.status === 'paused' ? `
                        <button class="action-btn" onclick="resumeJob(${job.id})" title="Resume">
                            <i class="fas fa-play"></i>
                        </button>
                    ` : ''}
                    ${job.status !== 'running' ? `
                        <button class="action-btn action-btn-danger" onclick="deleteJob(${job.id})" title="Delete">
                            <i class="fas fa-trash"></i>
                        </button>
                    ` : ''}
                </td>
            </tr>
        `).join('');

        // Update system info
        document.getElementById('sysInfoJobs').textContent = jobs.length.toLocaleString();

        // Initialize DataTable if not already initialized
        if (jobsDataTable) {
            jobsDataTable.destroy();
        }
        jobsDataTable = new DataTable('#jobsTable', {
            order: [[0, 'desc']],
            pageLength: 25
        });

    } catch (error) {
        console.error('Error loading jobs:', error);
        showNotification('Failed to load jobs', 'error');
    }
}

// Load Leads
async function loadLeads() {
    try {
        showLoading(true);
        const response = await fetch(`${API_URL}/leads?limit=1000`);
        const leads = await response.json();

        const tbody = document.getElementById('leadsBody');
        tbody.innerHTML = leads.map((lead, index) => `
            <tr>
                <td><input type="checkbox" class="lead-select" data-id="${lead.id}"></td>
                <td><strong>${lead.business_name}</strong></td>
                <td>${lead.category || '-'}</td>
                <td>${lead.city || '-'}</td>
                <td>${lead.phone ? `<a href="tel:${lead.phone}">${lead.phone}</a>` : '-'}</td>
                <td>${lead.email || '-'}</td>
                <td>${lead.website ? `<a href="${lead.website}" target="_blank"><i class="fas fa-external-link-alt"></i></a>` : '-'}</td>
                <td>${lead.rating ? lead.rating + ' ★' : '-'}</td>
                <td>${getQualityBadge(lead.data_quality_score)}</td>
                <td>
                    <button class="action-btn" onclick="viewLeadDetails(${lead.id})" title="View Details">
                        <i class="fas fa-eye"></i>
                    </button>
                    <button class="action-btn" onclick="deleteLead(${lead.id})" title="Delete">
                        <i class="fas fa-trash"></i>
                    </button>
                </td>
            </tr>
        `).join('');

        // Initialize DataTable
        if (leadsDataTable) {
            leadsDataTable.destroy();
        }
        leadsDataTable = new DataTable('#leadsTable', {
            order: [[8, 'desc']], // Sort by quality
            pageLength: 50,
            dom: 'Bfrtip'
        });

        // Select all checkbox
        document.getElementById('selectAll').addEventListener('change', function() {
            document.querySelectorAll('.lead-select').forEach(cb => {
                cb.checked = this.checked;
            });
        });

        showLoading(false);

    } catch (error) {
        console.error('Error loading leads:', error);
        showNotification('Failed to load leads', 'error');
        showLoading(false);
    }
}

// Start Scraping
async function startScrape(event) {
    event.preventDefault();

    const data = {
        search_query: document.getElementById('searchQuery').value,
        location: document.getElementById('searchLocation').value || null,
        max_results: parseInt(document.getElementById('maxResults').value),
        extract_emails: document.getElementById('extractEmails').value === 'true',
        use_proxies: document.getElementById('useProxies').checked,
        headless: document.getElementById('headlessMode').checked
    };

    try {
        showLoading(true);
        const response = await fetch(`${API_URL}/scrape`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });

        if (!response.ok) throw new Error('Failed to start scrape');

        const job = await response.json();
        showNotification(`Scraping started! Job #${job.id}`, 'success');

        // Reset form
        document.getElementById('scrapeForm').reset();

        // Switch to jobs page
        setTimeout(() => {
            showPage('jobs');
        }, 1500);

        showLoading(false);

    } catch (error) {
        console.error('Error starting scrape:', error);
        showNotification('Failed to start scraping: ' + error.message, 'error');
        showLoading(false);
    }
}

// Start Bulk Scraping
async function startBulkScrape(event) {
    event.preventDefault();

    const locations = document.getElementById('bulkLocations').value
        .split(',')
        .map(l => l.trim())
        .filter(l => l.length > 0);

    const data = {
        search_query: document.getElementById('bulkQuery').value,
        locations: locations,
        max_results_per_location: parseInt(document.getElementById('bulkMaxResults').value),
        delay_between_locations: parseInt(document.getElementById('bulkDelay').value),
        extract_emails: document.getElementById('bulkExtractEmails').checked
    };

    try {
        showLoading(true);
        const response = await fetch(`${API_URL}/bulk-scrape`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });

        if (!response.ok) throw new Error('Failed to start bulk scrape');

        const result = await response.json();
        showNotification(`Bulk scraping started for ${locations.length} locations!`, 'success');

        // Reset form
        document.getElementById('bulkScrapeForm').reset();

        // Switch to jobs page
        setTimeout(() => {
            showPage('jobs');
        }, 1500);

        showLoading(false);

    } catch (error) {
        console.error('Error starting bulk scrape:', error);
        showNotification('Failed to start bulk scraping: ' + error.message, 'error');
        showLoading(false);
    }
}

// Export Data
async function exportData(event) {
    event.preventDefault();

    const filters = {};
    if (document.getElementById('exportFilterPhone').checked) filters.has_phone = true;
    if (document.getElementById('exportFilterWebsite').checked) filters.has_website = true;
    if (document.getElementById('exportFilterEmail').checked) filters.has_email = true;

    const city = document.getElementById('exportFilterCity').value;
    if (city) filters.city = city;

    const minQuality = parseInt(document.getElementById('exportMinQuality').value);
    if (minQuality > 0) filters.min_quality_score = minQuality;

    const data = {
        format: document.getElementById('exportFormat').value,
        filters: filters,
        filename: `leads_export_${Date.now()}`
    };

    try {
        showLoading(true);
        const response = await fetch(`${API_URL}/export`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });

        if (!response.ok) throw new Error('Export failed');

        const result = await response.json();
        showNotification(`Export successful! ${result.count} leads exported. Downloading...`, 'success');

        // Trigger file download
        const filename = result.filepath.split(/[/\\]/).pop();
        downloadExportFile(filename);

        showLoading(false);

    } catch (error) {
        console.error('Error exporting data:', error);
        showNotification('Export failed: ' + error.message, 'error');
        showLoading(false);
    }
}

// Download exported file
function downloadExportFile(filename) {
    const downloadUrl = `${API_URL}/export/download/${filename}`;
    const link = document.createElement('a');
    link.href = downloadUrl;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

// Load Analytics
async function loadAnalytics() {
    try {
        const response = await fetch(`${API_URL}/analytics`);
        const data = await response.json();

        // Categories Chart
        if (charts.categories) charts.categories.destroy();
        const ctxCategories = document.getElementById('categoriesChart').getContext('2d');
        charts.categories = new Chart(ctxCategories, {
            type: 'bar',
            data: {
                labels: data.top_categories.map(c => c.category),
                datasets: [{
                    label: 'Number of Leads',
                    data: data.top_categories.map(c => c.count),
                    backgroundColor: 'rgba(102, 126, 234, 0.8)'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    title: {
                        display: true,
                        text: 'Top Categories'
                    }
                }
            }
        });

        // Quality Distribution Chart
        if (charts.quality) charts.quality.destroy();
        const ctxQuality = document.getElementById('qualityChart').getContext('2d');
        charts.quality = new Chart(ctxQuality, {
            type: 'doughnut',
            data: {
                labels: ['Excellent (80-100%)', 'Good (60-79%)', 'Fair (40-59%)', 'Poor (0-39%)'],
                datasets: [{
                    data: data.quality_distribution,
                    backgroundColor: [
                        'rgba(16, 185, 129, 0.8)',
                        'rgba(59, 130, 246, 0.8)',
                        'rgba(245, 158, 11, 0.8)',
                        'rgba(239, 68, 68, 0.8)'
                    ]
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    title: {
                        display: true,
                        text: 'Quality Score Distribution'
                    }
                }
            }
        });

        // Activity Chart
        if (charts.activity) charts.activity.destroy();
        const ctxActivity = document.getElementById('activityChart').getContext('2d');
        charts.activity = new Chart(ctxActivity, {
            type: 'line',
            data: {
                labels: data.activity_timeline.map(a => a.date),
                datasets: [{
                    label: 'Leads Scraped',
                    data: data.activity_timeline.map(a => a.count),
                    borderColor: 'rgba(102, 126, 234, 1)',
                    backgroundColor: 'rgba(102, 126, 234, 0.1)',
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    title: {
                        display: true,
                        text: 'Scraping Activity (Last 7 Days)'
                    }
                }
            }
        });

    } catch (error) {
        console.error('Error loading analytics:', error);
        showNotification('Failed to load analytics', 'error');
    }
}

// Settings
async function loadSavedSettings() {
    try {
        const response = await fetch(`${API_URL}/settings`);
        if (response.ok) {
            const data = await response.json();
            // Store in localStorage as backup
            localStorage.setItem('scraperSettings', JSON.stringify(data.settings));
        }
    } catch (error) {
        console.error('Error loading settings from API:', error);
        // Fall back to localStorage
    }
}

async function loadSettingsData() {
    try {
        // Try to load from API first
        const response = await fetch(`${API_URL}/settings`);
        if (response.ok) {
            const data = await response.json();
            const settings = data.settings;

            document.getElementById('settingMaxRequests').value = settings.max_requests_per_hour || 100;
            document.getElementById('settingDelay').value = settings.delay_between_requests_min || 3;
            document.getElementById('settingHeadless').value = settings.headless_mode ? 'true' : 'false';
            document.getElementById('settingDeduplicate').value = settings.auto_deduplicate ? 'true' : 'false';

            // Also load system health
            loadSystemHealth();
            return;
        }
    } catch (error) {
        console.error('Error loading settings from API:', error);
    }

    // Fall back to localStorage
    const settings = localStorage.getItem('scraperSettings');
    if (settings) {
        const parsed = JSON.parse(settings);
        document.getElementById('settingMaxRequests').value = parsed.max_requests_per_hour || parsed.max_requests || 100;
        document.getElementById('settingDelay').value = parsed.delay_between_requests_min || parsed.delay || 3;
        document.getElementById('settingHeadless').value = (parsed.headless_mode !== undefined ? parsed.headless_mode : parsed.headless) ? 'true' : 'false';
        document.getElementById('settingDeduplicate').value = (parsed.auto_deduplicate !== undefined ? parsed.auto_deduplicate : parsed.deduplicate) ? 'true' : 'false';
    }
}

async function saveSettings(event) {
    event.preventDefault();

    const settings = {
        max_requests_per_hour: parseInt(document.getElementById('settingMaxRequests').value),
        delay_between_requests_min: parseFloat(document.getElementById('settingDelay').value),
        headless_mode: document.getElementById('settingHeadless').value === 'true',
        auto_deduplicate: document.getElementById('settingDeduplicate').value === 'true'
    };

    try {
        // Save to backend API
        const response = await fetch(`${API_URL}/settings`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(settings)
        });

        if (response.ok) {
            // Also save to localStorage as backup
            localStorage.setItem('scraperSettings', JSON.stringify(settings));
            showNotification('Settings saved successfully!', 'success');
        } else {
            throw new Error('Failed to save settings to server');
        }
    } catch (error) {
        console.error('Error saving settings:', error);
        // Still save to localStorage
        localStorage.setItem('scraperSettings', JSON.stringify(settings));
        showNotification('Settings saved locally (server unavailable)', 'warning');
    }
}

// Load system health information
async function loadSystemHealth() {
    try {
        const response = await fetch(`${API_URL}/health`);
        if (response.ok) {
            const health = await response.json();

            // Update UI with health info if elements exist
            const healthContainer = document.getElementById('systemHealth');
            if (healthContainer) {
                if (health.system && typeof health.system === 'object') {
                    healthContainer.innerHTML = `
                        <div class="health-item">
                            <span class="label">CPU Usage:</span>
                            <span class="value">${health.system.cpu_percent}%</span>
                        </div>
                        <div class="health-item">
                            <span class="label">Memory Usage:</span>
                            <span class="value">${health.system.memory_percent}% (${health.system.memory_used_gb}GB / ${health.system.memory_total_gb}GB)</span>
                        </div>
                        <div class="health-item">
                            <span class="label">Disk Usage:</span>
                            <span class="value">${health.system.disk_percent}% (${health.system.disk_free_gb}GB free)</span>
                        </div>
                        <div class="health-item">
                            <span class="label">Database:</span>
                            <span class="value ${health.database === 'healthy' ? 'text-success' : 'text-danger'}">${health.database}</span>
                        </div>
                        <div class="health-item">
                            <span class="label">Active Scrapers:</span>
                            <span class="value">${health.active_scrapers}</span>
                        </div>
                        <div class="health-item">
                            <span class="label">WebSocket Connections:</span>
                            <span class="value">${health.websocket_connections}</span>
                        </div>
                    `;
                } else {
                    healthContainer.innerHTML = `<p>System health: ${health.system || 'Unknown'}</p>`;
                }
            }
        }
    } catch (error) {
        console.error('Error loading system health:', error);
    }
}

// WebSocket Connection
function connectWebSocket() {
    try {
        ws = new WebSocket(WS_URL);

        ws.onopen = () => {
            console.log('WebSocket connected');
            document.getElementById('wsStatus').textContent = 'Connected';
            document.getElementById('wsStatus').className = 'badge badge-success';
        };

        ws.onmessage = (event) => {
            const message = JSON.parse(event.data);
            handleWebSocketMessage(message);
        };

        ws.onerror = (error) => {
            console.error('WebSocket error:', error);
            document.getElementById('wsStatus').textContent = 'Error';
            document.getElementById('wsStatus').className = 'badge badge-danger';
        };

        ws.onclose = () => {
            console.log('WebSocket disconnected');
            document.getElementById('wsStatus').textContent = 'Disconnected';
            document.getElementById('wsStatus').className = 'badge badge-warning';

            // Reconnect after 5 seconds
            setTimeout(connectWebSocket, 5000);
        };

    } catch (error) {
        console.error('Failed to connect WebSocket:', error);
    }
}

function handleWebSocketMessage(message) {
    console.log('WebSocket message:', message);

    if (message.type === 'job_update') {
        // Update job progress in real-time
        loadRecentJobs();
        if (document.getElementById('page-jobs').classList.contains('active')) {
            loadJobs();
        }
    }

    if (message.type === 'job_completed') {
        showNotification(`Job #${message.job_id} completed! ${message.results_count} leads scraped.`, 'success');
        loadStats();
        loadRecentJobs();
    }

    if (message.type === 'job_failed') {
        showNotification(`Job #${message.job_id} failed: ${message.error}`, 'error');
        loadRecentJobs();
    }

    if (message.type === 'new_lead') {
        // Optionally refresh leads table
        if (document.getElementById('page-leads').classList.contains('active')) {
            loadLeads();
        }
    }
}

// Utility Functions
function getStatusBadge(status) {
    const badges = {
        'completed': '<span class="badge badge-success">Completed</span>',
        'running': '<span class="badge badge-info">Running</span>',
        'pending': '<span class="badge badge-warning">Pending</span>',
        'failed': '<span class="badge badge-danger">Failed</span>'
    };
    return badges[status] || '<span class="badge badge-secondary">' + status + '</span>';
}

function getQualityBadge(score) {
    if (score >= 80) return `<span class="badge badge-success">${score}%</span>`;
    if (score >= 60) return `<span class="badge badge-info">${score}%</span>`;
    if (score >= 40) return `<span class="badge badge-warning">${score}%</span>`;
    return `<span class="badge badge-danger">${score}%</span>`;
}

function getProgress(job) {
    if (job.leads_target === 0) return 0;
    return Math.min(100, (job.leads_scraped / job.leads_target) * 100);
}

function formatDate(dateString) {
    if (!dateString) return '-';
    const date = new Date(dateString);
    return date.toLocaleString();
}

function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;

    const icon = type === 'success' ? 'check-circle' :
                 type === 'error' ? 'exclamation-circle' :
                 type === 'warning' ? 'exclamation-triangle' : 'info-circle';

    notification.innerHTML = `
        <i class="fas fa-${icon}"></i>
        <span>${message}</span>
    `;

    document.body.appendChild(notification);

    setTimeout(() => {
        notification.style.animation = 'slideIn 0.3s ease reverse';
        setTimeout(() => notification.remove(), 300);
    }, 5000);
}

function showLoading(show) {
    const overlay = document.getElementById('loadingOverlay');
    if (show) {
        overlay.classList.add('active');
    } else {
        overlay.classList.remove('active');
    }
}

function refreshData() {
    loadStats();
    loadRecentJobs();

    const activePage = document.querySelector('.page.active').id.replace('page-', '');
    if (activePage === 'jobs') loadJobs();
    if (activePage === 'leads') loadLeads();
    if (activePage === 'analytics') loadAnalytics();

    showNotification('Data refreshed', 'success');
}

// Advanced Filter Functions
function applyAdvancedFilters() {
    showLoading(true);

    // Build query parameters from all filter fields
    const params = new URLSearchParams();

    // General search
    const generalSearch = document.getElementById('filterGeneralSearch').value;
    if (generalSearch) params.append('search', generalSearch);

    // Location filters
    const city = document.getElementById('filterCity').value;
    const state = document.getElementById('filterState').value;
    const pinCode = document.getElementById('filterPinCode').value;
    if (city) params.append('city', city);
    if (state) params.append('state', state);
    if (pinCode) params.append('pin_code', pinCode);

    // Contact filters
    if (document.getElementById('filterHasPhone').checked) params.append('has_phone', 'true');
    if (document.getElementById('filterHasEmail').checked) params.append('has_email', 'true');
    if (document.getElementById('filterHasWebsite').checked) params.append('has_website', 'true');

    // Category filters
    const category = document.getElementById('filterCategory').value;
    const searchQuery = document.getElementById('filterSearchQuery').value;
    if (category) params.append('category', category);
    if (searchQuery) params.append('search_query', searchQuery);

    // Quality & Rating filters
    const minQuality = document.getElementById('filterMinQuality').value;
    const maxQuality = document.getElementById('filterMaxQuality').value;
    const minRating = document.getElementById('filterMinRating').value;
    const maxRating = document.getElementById('filterMaxRating').value;
    const minReviews = document.getElementById('filterMinReviews').value;
    const priceLevel = document.getElementById('filterPriceLevel').value;

    if (minQuality) params.append('min_quality', minQuality);
    if (maxQuality) params.append('max_quality', maxQuality);
    if (minRating) params.append('min_rating', minRating);
    if (maxRating) params.append('max_rating', maxRating);
    if (minReviews) params.append('min_reviews', minReviews);
    if (priceLevel) params.append('price_level', priceLevel);

    // Social media filters
    if (document.getElementById('filterHasFacebook').checked) params.append('has_facebook', 'true');
    if (document.getElementById('filterHasInstagram').checked) params.append('has_instagram', 'true');
    if (document.getElementById('filterHasTwitter').checked) params.append('has_twitter', 'true');
    if (document.getElementById('filterHasLinkedIn').checked) params.append('has_linkedin', 'true');

    // Fetch filtered leads
    fetch(`${API_URL}/leads?${params.toString()}`)
        .then(response => response.json())
        .then(leads => {
            // Update table
            const tbody = document.getElementById('leadsBody');
            tbody.innerHTML = leads.map((lead, index) => `
                <tr>
                    <td><input type="checkbox" class="lead-select" data-id="${lead.id}"></td>
                    <td><strong>${lead.business_name}</strong></td>
                    <td>${lead.category || '-'}</td>
                    <td>${lead.city || '-'}</td>
                    <td>${lead.phone ? `<a href="tel:${lead.phone}">${lead.phone}</a>` : '-'}</td>
                    <td>${lead.email || '-'}</td>
                    <td>${lead.website ? `<a href="${lead.website}" target="_blank"><i class="fas fa-external-link-alt"></i></a>` : '-'}</td>
                    <td>${lead.rating ? lead.rating + ' ★' : '-'}</td>
                    <td>${getQualityBadge(lead.data_quality_score)}</td>
                    <td>
                        <button class="action-btn" onclick="viewLeadDetails(${lead.id})" title="View Details">
                            <i class="fas fa-eye"></i>
                        </button>
                        <button class="action-btn" onclick="deleteLead(${lead.id})" title="Delete">
                            <i class="fas fa-trash"></i>
                        </button>
                    </td>
                </tr>
            `).join('');

            // Reinitialize DataTable
            if (leadsDataTable) {
                leadsDataTable.destroy();
            }
            leadsDataTable = new DataTable('#leadsTable', {
                order: [[8, 'desc']], // Sort by quality
                pageLength: 50
            });

            // Show filter summary
            updateFilterSummary(params);
            showNotification(`Found ${leads.length} leads matching your filters`, 'success');
            showLoading(false);
        })
        .catch(error => {
            console.error('Error applying filters:', error);
            showNotification('Failed to apply filters', 'error');
            showLoading(false);
        });
}

function clearFilters() {
    // Clear all filter inputs
    document.getElementById('filterGeneralSearch').value = '';
    document.getElementById('filterCity').value = '';
    document.getElementById('filterState').value = '';
    document.getElementById('filterPinCode').value = '';
    document.getElementById('filterCategory').value = '';
    document.getElementById('filterSearchQuery').value = '';
    document.getElementById('filterMinQuality').value = '';
    document.getElementById('filterMaxQuality').value = '';
    document.getElementById('filterMinRating').value = '';
    document.getElementById('filterMaxRating').value = '';
    document.getElementById('filterMinReviews').value = '';
    document.getElementById('filterPriceLevel').value = '';

    // Clear checkboxes
    document.getElementById('filterHasPhone').checked = false;
    document.getElementById('filterHasEmail').checked = false;
    document.getElementById('filterHasWebsite').checked = false;
    document.getElementById('filterHasFacebook').checked = false;
    document.getElementById('filterHasInstagram').checked = false;
    document.getElementById('filterHasTwitter').checked = false;
    document.getElementById('filterHasLinkedIn').checked = false;

    // Hide filter summary
    document.getElementById('filterSummary').style.display = 'none';

    // Reload all leads
    loadLeads();
    showNotification('Filters cleared', 'success');
}

function updateFilterSummary(params) {
    const summary = document.getElementById('filterSummary');
    const tagsContainer = document.getElementById('filterTags');

    if (params.toString()) {
        const tags = [];

        // Build filter tags
        for (const [key, value] of params.entries()) {
            let label = key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
            let displayValue = value === 'true' ? '✓' : value;
            tags.push(`
                <span class="badge badge-info" style="cursor: pointer;" onclick="removeFilter('${key}')">
                    ${label}: ${displayValue}
                    <i class="fas fa-times" style="margin-left: 0.25rem;"></i>
                </span>
            `);
        }

        tagsContainer.innerHTML = tags.join('');
        summary.style.display = 'block';
    } else {
        summary.style.display = 'none';
    }
}

function removeFilter(filterKey) {
    // Map filter key to input element
    const filterMap = {
        'search': 'filterGeneralSearch',
        'city': 'filterCity',
        'state': 'filterState',
        'pin_code': 'filterPinCode',
        'category': 'filterCategory',
        'search_query': 'filterSearchQuery',
        'min_quality': 'filterMinQuality',
        'max_quality': 'filterMaxQuality',
        'min_rating': 'filterMinRating',
        'max_rating': 'filterMaxRating',
        'min_reviews': 'filterMinReviews',
        'price_level': 'filterPriceLevel',
        'has_phone': 'filterHasPhone',
        'has_email': 'filterHasEmail',
        'has_website': 'filterHasWebsite',
        'has_facebook': 'filterHasFacebook',
        'has_instagram': 'filterHasInstagram',
        'has_twitter': 'filterHasTwitter',
        'has_linkedin': 'filterHasLinkedIn'
    };

    const elementId = filterMap[filterKey];
    if (elementId) {
        const element = document.getElementById(elementId);
        if (element.type === 'checkbox') {
            element.checked = false;
        } else {
            element.value = '';
        }
    }

    // Reapply filters
    applyAdvancedFilters();
}

function saveFilterPreset() {
    const presetName = prompt('Enter a name for this filter preset:');
    if (!presetName) return;

    const preset = {
        generalSearch: document.getElementById('filterGeneralSearch').value,
        city: document.getElementById('filterCity').value,
        state: document.getElementById('filterState').value,
        pinCode: document.getElementById('filterPinCode').value,
        category: document.getElementById('filterCategory').value,
        searchQuery: document.getElementById('filterSearchQuery').value,
        minQuality: document.getElementById('filterMinQuality').value,
        maxQuality: document.getElementById('filterMaxQuality').value,
        minRating: document.getElementById('filterMinRating').value,
        maxRating: document.getElementById('filterMaxRating').value,
        minReviews: document.getElementById('filterMinReviews').value,
        priceLevel: document.getElementById('filterPriceLevel').value,
        hasPhone: document.getElementById('filterHasPhone').checked,
        hasEmail: document.getElementById('filterHasEmail').checked,
        hasWebsite: document.getElementById('filterHasWebsite').checked,
        hasFacebook: document.getElementById('filterHasFacebook').checked,
        hasInstagram: document.getElementById('filterHasInstagram').checked,
        hasTwitter: document.getElementById('filterHasTwitter').checked,
        hasLinkedIn: document.getElementById('filterHasLinkedIn').checked
    };

    // Save to localStorage
    const presets = JSON.parse(localStorage.getItem('filterPresets') || '{}');
    presets[presetName] = preset;
    localStorage.setItem('filterPresets', JSON.stringify(presets));

    showNotification(`Filter preset "${presetName}" saved!`, 'success');
}

// Load smart filter presets from API
async function loadFilterPresets() {
    try {
        const response = await fetch(`${API_URL}/filter-presets`);
        if (response.ok) {
            const data = await response.json();
            return data.presets;
        }
    } catch (error) {
        console.error('Error loading filter presets:', error);
    }
    return {};
}

// Apply a smart filter preset
async function applyFilterPreset(presetKey) {
    const presets = await loadFilterPresets();
    const preset = presets[presetKey];

    if (!preset) {
        showNotification('Preset not found', 'error');
        return;
    }

    // Clear existing filters
    clearFilters();

    // Apply preset filters
    const filters = preset.filters;

    if (filters.min_quality) {
        document.getElementById('filterMinQuality').value = filters.min_quality;
    }
    if (filters.has_phone) {
        document.getElementById('filterHasPhone').checked = true;
    }
    if (filters.has_email) {
        document.getElementById('filterHasEmail').checked = true;
    }
    if (filters.has_website) {
        document.getElementById('filterHasWebsite').checked = true;
    }
    if (filters.has_facebook) {
        document.getElementById('filterHasFacebook').checked = true;
    }
    if (filters.min_rating) {
        document.getElementById('filterMinRating').value = filters.min_rating;
    }
    if (filters.min_reviews) {
        document.getElementById('filterMinReviews').value = filters.min_reviews;
    }

    // Apply the filters
    applyAdvancedFilters();
    showNotification(`Applied preset: ${preset.name}`, 'success');
}

// Quick filter buttons for common presets
function initQuickFilters() {
    const quickFiltersHtml = `
        <div class="quick-filters" style="margin-bottom: 1rem;">
            <span style="font-weight: 500; margin-right: 0.5rem;">Quick Filters:</span>
            <button class="btn btn-sm btn-outline" onclick="applyFilterPreset('high_quality')">High Quality</button>
            <button class="btn btn-sm btn-outline" onclick="applyFilterPreset('cold_call_ready')">Cold Call Ready</button>
            <button class="btn btn-sm btn-outline" onclick="applyFilterPreset('email_campaign')">Email Campaign</button>
            <button class="btn btn-sm btn-outline" onclick="applyFilterPreset('complete_contact')">Complete Contact</button>
            <button class="btn btn-sm btn-outline" onclick="applyFilterPreset('top_rated')">Top Rated</button>
        </div>
    `;

    // Insert quick filters before the leads table filter section if it exists
    const filterSection = document.querySelector('.leads-filter-section, .filter-section, #leadsFilters');
    if (filterSection) {
        filterSection.insertAdjacentHTML('afterbegin', quickFiltersHtml);
    }
}

// Legacy function for backward compatibility
function applyFilters() {
    applyAdvancedFilters();
}

// View lead details
async function viewLeadDetails(id) {
    try {
        showLoading(true);
        const response = await fetch(`${API_URL}/leads/${id}`);

        if (!response.ok) throw new Error('Failed to load lead details');

        const lead = await response.json();
        showLoading(false);

        // Create modal HTML
        const modalHtml = `
            <div class="modal-overlay" id="leadModal" onclick="closeModal(event)">
                <div class="modal-content" onclick="event.stopPropagation()">
                    <div class="modal-header">
                        <h2>${lead.business_name || 'Business Details'}</h2>
                        <button class="modal-close" onclick="closeLeadModal()">&times;</button>
                    </div>
                    <div class="modal-body">
                        <div class="lead-details-grid">
                            <div class="detail-section">
                                <h3>Contact Information</h3>
                                <div class="detail-row"><span class="label">Phone:</span> <span>${lead.phone || 'N/A'}</span></div>
                                <div class="detail-row"><span class="label">Email:</span> <span>${lead.email || 'N/A'}</span></div>
                                <div class="detail-row"><span class="label">Website:</span> <span>${lead.website ? `<a href="${lead.website}" target="_blank">${lead.website}</a>` : 'N/A'}</span></div>
                            </div>
                            <div class="detail-section">
                                <h3>Location</h3>
                                <div class="detail-row"><span class="label">Address:</span> <span>${lead.full_address || 'N/A'}</span></div>
                                <div class="detail-row"><span class="label">City:</span> <span>${lead.city || 'N/A'}</span></div>
                                <div class="detail-row"><span class="label">State:</span> <span>${lead.state || 'N/A'}</span></div>
                                <div class="detail-row"><span class="label">Pin Code:</span> <span>${lead.pin_code || 'N/A'}</span></div>
                            </div>
                            <div class="detail-section">
                                <h3>Business Info</h3>
                                <div class="detail-row"><span class="label">Category:</span> <span>${lead.category || 'N/A'}</span></div>
                                <div class="detail-row"><span class="label">Rating:</span> <span>${lead.rating ? lead.rating + ' ★' : 'N/A'}</span></div>
                                <div class="detail-row"><span class="label">Reviews:</span> <span>${lead.review_count || 'N/A'}</span></div>
                                <div class="detail-row"><span class="label">Price Level:</span> <span>${lead.price_level || 'N/A'}</span></div>
                                <div class="detail-row"><span class="label">Quality Score:</span> <span>${getQualityBadge(lead.data_quality_score)}</span></div>
                            </div>
                            <div class="detail-section">
                                <h3>Social Media</h3>
                                <div class="detail-row"><span class="label">Facebook:</span> <span>${lead.social_facebook ? `<a href="${lead.social_facebook}" target="_blank">View</a>` : 'N/A'}</span></div>
                                <div class="detail-row"><span class="label">Instagram:</span> <span>${lead.social_instagram ? `<a href="${lead.social_instagram}" target="_blank">View</a>` : 'N/A'}</span></div>
                                <div class="detail-row"><span class="label">Twitter:</span> <span>${lead.social_twitter ? `<a href="${lead.social_twitter}" target="_blank">View</a>` : 'N/A'}</span></div>
                                <div class="detail-row"><span class="label">LinkedIn:</span> <span>${lead.social_linkedin ? `<a href="${lead.social_linkedin}" target="_blank">View</a>` : 'N/A'}</span></div>
                            </div>
                            <div class="detail-section">
                                <h3>Business Hours</h3>
                                <div class="detail-row"><span class="label">Monday:</span> <span>${lead.hours_monday || 'N/A'}</span></div>
                                <div class="detail-row"><span class="label">Tuesday:</span> <span>${lead.hours_tuesday || 'N/A'}</span></div>
                                <div class="detail-row"><span class="label">Wednesday:</span> <span>${lead.hours_wednesday || 'N/A'}</span></div>
                                <div class="detail-row"><span class="label">Thursday:</span> <span>${lead.hours_thursday || 'N/A'}</span></div>
                                <div class="detail-row"><span class="label">Friday:</span> <span>${lead.hours_friday || 'N/A'}</span></div>
                                <div class="detail-row"><span class="label">Saturday:</span> <span>${lead.hours_saturday || 'N/A'}</span></div>
                                <div class="detail-row"><span class="label">Sunday:</span> <span>${lead.hours_sunday || 'N/A'}</span></div>
                            </div>
                            <div class="detail-section">
                                <h3>Metadata</h3>
                                <div class="detail-row"><span class="label">Place ID:</span> <span>${lead.place_id || 'N/A'}</span></div>
                                <div class="detail-row"><span class="label">Maps URL:</span> <span>${lead.maps_url ? `<a href="${lead.maps_url}" target="_blank">Open in Maps</a>` : 'N/A'}</span></div>
                                <div class="detail-row"><span class="label">Coordinates:</span> <span>${lead.latitude && lead.longitude ? `${lead.latitude}, ${lead.longitude}` : 'N/A'}</span></div>
                                <div class="detail-row"><span class="label">Scraped At:</span> <span>${formatDate(lead.scraped_at)}</span></div>
                                <div class="detail-row"><span class="label">Search Query:</span> <span>${lead.search_query || 'N/A'}</span></div>
                            </div>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button class="btn btn-secondary" onclick="closeLeadModal()">Close</button>
                        <button class="btn btn-primary" onclick="editLead(${lead.id})">Edit</button>
                    </div>
                </div>
            </div>
        `;

        // Add modal to page
        document.body.insertAdjacentHTML('beforeend', modalHtml);

        // Add modal styles if not already present
        if (!document.getElementById('modalStyles')) {
            const styles = document.createElement('style');
            styles.id = 'modalStyles';
            styles.textContent = `
                .modal-overlay { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 1000; }
                .modal-content { background: var(--card-bg, #fff); border-radius: 12px; width: 90%; max-width: 900px; max-height: 90vh; overflow: hidden; display: flex; flex-direction: column; }
                .modal-header { display: flex; justify-content: space-between; align-items: center; padding: 1rem 1.5rem; border-bottom: 1px solid var(--border-color, #e0e0e0); }
                .modal-header h2 { margin: 0; font-size: 1.25rem; }
                .modal-close { background: none; border: none; font-size: 1.5rem; cursor: pointer; color: var(--text-secondary, #666); }
                .modal-body { padding: 1.5rem; overflow-y: auto; flex: 1; }
                .modal-footer { padding: 1rem 1.5rem; border-top: 1px solid var(--border-color, #e0e0e0); display: flex; justify-content: flex-end; gap: 0.5rem; }
                .lead-details-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1.5rem; }
                .detail-section { background: var(--bg-secondary, #f5f5f5); padding: 1rem; border-radius: 8px; }
                .detail-section h3 { margin: 0 0 0.75rem 0; font-size: 0.875rem; text-transform: uppercase; color: var(--text-secondary, #666); }
                .detail-row { display: flex; justify-content: space-between; padding: 0.375rem 0; border-bottom: 1px solid var(--border-color, #e0e0e0); }
                .detail-row:last-child { border-bottom: none; }
                .detail-row .label { font-weight: 500; color: var(--text-secondary, #666); }
            `;
            document.head.appendChild(styles);
        }

    } catch (error) {
        showLoading(false);
        console.error('Error loading lead details:', error);
        showNotification('Failed to load lead details', 'error');
    }
}

function closeLeadModal() {
    const modal = document.getElementById('leadModal');
    if (modal) modal.remove();
}

function closeModal(event) {
    if (event.target.classList.contains('modal-overlay')) {
        event.target.remove();
    }
}

// Edit lead (shows edit form)
async function editLead(id) {
    closeLeadModal();

    try {
        showLoading(true);
        const response = await fetch(`${API_URL}/leads/${id}`);

        if (!response.ok) throw new Error('Failed to load lead');

        const lead = await response.json();
        showLoading(false);

        // Create edit modal HTML
        const modalHtml = `
            <div class="modal-overlay" id="editLeadModal" onclick="closeModal(event)">
                <div class="modal-content" onclick="event.stopPropagation()" style="max-width: 600px;">
                    <div class="modal-header">
                        <h2>Edit Lead</h2>
                        <button class="modal-close" onclick="closeEditLeadModal()">&times;</button>
                    </div>
                    <div class="modal-body">
                        <form id="editLeadForm" onsubmit="submitEditLead(event, ${id})">
                            <div class="form-grid" style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;">
                                <div class="form-group">
                                    <label>Business Name</label>
                                    <input type="text" id="editBusinessName" value="${lead.business_name || ''}" class="form-control">
                                </div>
                                <div class="form-group">
                                    <label>Category</label>
                                    <input type="text" id="editCategory" value="${lead.category || ''}" class="form-control">
                                </div>
                                <div class="form-group">
                                    <label>Phone</label>
                                    <input type="text" id="editPhone" value="${lead.phone || ''}" class="form-control">
                                </div>
                                <div class="form-group">
                                    <label>Email</label>
                                    <input type="email" id="editEmail" value="${lead.email || ''}" class="form-control">
                                </div>
                                <div class="form-group" style="grid-column: span 2;">
                                    <label>Website</label>
                                    <input type="url" id="editWebsite" value="${lead.website || ''}" class="form-control">
                                </div>
                                <div class="form-group" style="grid-column: span 2;">
                                    <label>Full Address</label>
                                    <input type="text" id="editFullAddress" value="${lead.full_address || ''}" class="form-control">
                                </div>
                                <div class="form-group">
                                    <label>City</label>
                                    <input type="text" id="editCity" value="${lead.city || ''}" class="form-control">
                                </div>
                                <div class="form-group">
                                    <label>State</label>
                                    <input type="text" id="editState" value="${lead.state || ''}" class="form-control">
                                </div>
                                <div class="form-group">
                                    <label>Pin Code</label>
                                    <input type="text" id="editPinCode" value="${lead.pin_code || ''}" class="form-control">
                                </div>
                            </div>
                        </form>
                    </div>
                    <div class="modal-footer">
                        <button class="btn btn-secondary" onclick="closeEditLeadModal()">Cancel</button>
                        <button class="btn btn-primary" onclick="document.getElementById('editLeadForm').dispatchEvent(new Event('submit'))">Save Changes</button>
                    </div>
                </div>
            </div>
        `;

        document.body.insertAdjacentHTML('beforeend', modalHtml);

    } catch (error) {
        showLoading(false);
        console.error('Error loading lead for edit:', error);
        showNotification('Failed to load lead for editing', 'error');
    }
}

function closeEditLeadModal() {
    const modal = document.getElementById('editLeadModal');
    if (modal) modal.remove();
}

async function submitEditLead(event, id) {
    event.preventDefault();

    const updateData = {
        business_name: document.getElementById('editBusinessName').value || null,
        category: document.getElementById('editCategory').value || null,
        phone: document.getElementById('editPhone').value || null,
        email: document.getElementById('editEmail').value || null,
        website: document.getElementById('editWebsite').value || null,
        full_address: document.getElementById('editFullAddress').value || null,
        city: document.getElementById('editCity').value || null,
        state: document.getElementById('editState').value || null,
        pin_code: document.getElementById('editPinCode').value || null
    };

    try {
        showLoading(true);
        const response = await fetch(`${API_URL}/leads/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(updateData)
        });

        if (!response.ok) throw new Error('Update failed');

        showNotification('Lead updated successfully', 'success');
        closeEditLeadModal();
        loadLeads();
        showLoading(false);

    } catch (error) {
        showLoading(false);
        console.error('Error updating lead:', error);
        showNotification('Failed to update lead: ' + error.message, 'error');
    }
}

// View job details
async function viewJobDetails(id) {
    try {
        showLoading(true);
        const response = await fetch(`${API_URL}/jobs/${id}`);

        if (!response.ok) throw new Error('Failed to load job details');

        const job = await response.json();
        showLoading(false);

        const modalHtml = `
            <div class="modal-overlay" id="jobModal" onclick="closeModal(event)">
                <div class="modal-content" onclick="event.stopPropagation()" style="max-width: 600px;">
                    <div class="modal-header">
                        <h2>Job #${job.id} Details</h2>
                        <button class="modal-close" onclick="closeJobModal()">&times;</button>
                    </div>
                    <div class="modal-body">
                        <div class="detail-section">
                            <div class="detail-row"><span class="label">Search Query:</span> <span>${job.search_query}</span></div>
                            <div class="detail-row"><span class="label">Location:</span> <span>${job.location || 'N/A'}</span></div>
                            <div class="detail-row"><span class="label">Status:</span> <span>${getStatusBadge(job.status)}</span></div>
                            <div class="detail-row"><span class="label">Progress:</span> <span>${job.leads_scraped} / ${job.leads_target}</span></div>
                            <div class="detail-row"><span class="label">Error Count:</span> <span>${job.error_count}</span></div>
                            <div class="detail-row"><span class="label">Last Error:</span> <span>${job.last_error || 'None'}</span></div>
                            <div class="detail-row"><span class="label">Started At:</span> <span>${formatDate(job.started_at)}</span></div>
                            <div class="detail-row"><span class="label">Completed At:</span> <span>${job.completed_at ? formatDate(job.completed_at) : 'N/A'}</span></div>
                            <div class="detail-row"><span class="label">Created At:</span> <span>${formatDate(job.created_at)}</span></div>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button class="btn btn-secondary" onclick="closeJobModal()">Close</button>
                        ${job.status === 'failed' ? `<button class="btn btn-primary" onclick="retryJob(${job.id}); closeJobModal();">Retry Job</button>` : ''}
                        ${job.status === 'running' ? `<button class="btn btn-warning" onclick="pauseJob(${job.id}); closeJobModal();">Pause</button>` : ''}
                        ${job.status === 'paused' ? `<button class="btn btn-success" onclick="resumeJob(${job.id}); closeJobModal();">Resume</button>` : ''}
                    </div>
                </div>
            </div>
        `;

        document.body.insertAdjacentHTML('beforeend', modalHtml);

    } catch (error) {
        showLoading(false);
        console.error('Error loading job details:', error);
        showNotification('Failed to load job details', 'error');
    }
}

function closeJobModal() {
    const modal = document.getElementById('jobModal');
    if (modal) modal.remove();
}

// Retry job
async function retryJob(id) {
    try {
        showLoading(true);
        const response = await fetch(`${API_URL}/jobs/${id}/retry`, {
            method: 'POST'
        });

        if (!response.ok) throw new Error('Retry failed');

        showNotification(`Job #${id} queued for retry`, 'success');
        loadJobs();
        loadRecentJobs();
        showLoading(false);

    } catch (error) {
        showLoading(false);
        console.error('Error retrying job:', error);
        showNotification('Failed to retry job: ' + error.message, 'error');
    }
}

// Pause job
async function pauseJob(id) {
    try {
        const response = await fetch(`${API_URL}/jobs/${id}/pause`, {
            method: 'POST'
        });

        if (!response.ok) throw new Error('Pause failed');

        showNotification(`Job #${id} paused`, 'success');
        loadJobs();
        loadRecentJobs();

    } catch (error) {
        console.error('Error pausing job:', error);
        showNotification('Failed to pause job: ' + error.message, 'error');
    }
}

// Resume job
async function resumeJob(id) {
    try {
        const response = await fetch(`${API_URL}/jobs/${id}/resume`, {
            method: 'POST'
        });

        if (!response.ok) throw new Error('Resume failed');

        showNotification(`Job #${id} resumed`, 'success');
        loadJobs();
        loadRecentJobs();

    } catch (error) {
        console.error('Error resuming job:', error);
        showNotification('Failed to resume job: ' + error.message, 'error');
    }
}

// Delete job
async function deleteJob(id) {
    if (!confirm('Are you sure you want to delete this job?')) return;

    try {
        const response = await fetch(`${API_URL}/jobs/${id}`, {
            method: 'DELETE'
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Delete failed');
        }

        showNotification(`Job #${id} deleted`, 'success');
        loadJobs();
        loadRecentJobs();

    } catch (error) {
        console.error('Error deleting job:', error);
        showNotification('Failed to delete job: ' + error.message, 'error');
    }
}

// Delete lead
async function deleteLead(id) {
    if (!confirm('Are you sure you want to delete this lead?')) return;

    try {
        const response = await fetch(`${API_URL}/leads/${id}`, {
            method: 'DELETE'
        });

        if (!response.ok) throw new Error('Delete failed');

        showNotification('Lead deleted successfully', 'success');
        loadLeads();
        loadStats();

    } catch (error) {
        showNotification('Failed to delete lead', 'error');
    }
}

// Export selected leads
async function showExportModal() {
    const selected = document.querySelectorAll('.lead-select:checked');
    if (selected.length === 0) {
        showNotification('Please select leads to export', 'warning');
        return;
    }

    const leadIds = Array.from(selected).map(cb => parseInt(cb.dataset.id));

    // Show format selection modal
    const format = prompt('Enter export format (csv or json):', 'csv');
    if (!format) return;

    if (!['csv', 'json'].includes(format.toLowerCase())) {
        showNotification('Invalid format. Use csv or json.', 'error');
        return;
    }

    try {
        showLoading(true);
        const response = await fetch(`${API_URL}/export/selected`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                lead_ids: leadIds,
                format: format.toLowerCase()
            })
        });

        if (!response.ok) throw new Error('Export failed');

        const result = await response.json();
        showNotification(`Exported ${result.count} leads. Downloading...`, 'success');

        // Trigger download
        downloadExportFile(result.filename);

        showLoading(false);

    } catch (error) {
        showLoading(false);
        console.error('Error exporting selected leads:', error);
        showNotification('Export failed: ' + error.message, 'error');
    }
}
