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
function showPage(pageName) {
    // Update nav items
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.remove('active');
    });
    event.target.closest('.nav-item').classList.add('active');

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
        showNotification(`Export successful! ${result.count} leads exported to ${result.filepath}`, 'success');

        showLoading(false);

    } catch (error) {
        console.error('Error exporting data:', error);
        showNotification('Export failed: ' + error.message, 'error');
        showLoading(false);
    }
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
function loadSavedSettings() {
    const settings = localStorage.getItem('scraperSettings');
    if (settings) {
        const parsed = JSON.parse(settings);
        // Apply settings if needed
    }
}

function loadSettingsData() {
    // Load current settings from API or localStorage
    const settings = localStorage.getItem('scraperSettings');
    if (settings) {
        const parsed = JSON.parse(settings);
        document.getElementById('settingMaxRequests').value = parsed.max_requests || 100;
        document.getElementById('settingDelay').value = parsed.delay || 2;
        document.getElementById('settingHeadless').value = parsed.headless || 'true';
        document.getElementById('settingDeduplicate').value = parsed.deduplicate || 'true';
    }
}

async function saveSettings(event) {
    event.preventDefault();

    const settings = {
        max_requests: parseInt(document.getElementById('settingMaxRequests').value),
        delay: parseFloat(document.getElementById('settingDelay').value),
        headless: document.getElementById('settingHeadless').value === 'true',
        deduplicate: document.getElementById('settingDeduplicate').value === 'true'
    };

    localStorage.setItem('scraperSettings', JSON.stringify(settings));
    showNotification('Settings saved successfully!', 'success');
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

function applyFilters() {
    if (leadsDataTable) {
        const search = document.getElementById('filterSearch').value;
        leadsDataTable.search(search).draw();
    }
}

// View lead details (to be implemented)
function viewLeadDetails(id) {
    showNotification('Lead details view coming soon!', 'info');
}

// View job details (to be implemented)
function viewJobDetails(id) {
    showNotification('Job details view coming soon!', 'info');
}

// Retry job (to be implemented)
function retryJob(id) {
    showNotification('Job retry coming soon!', 'info');
}

// Delete lead (to be implemented)
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
function showExportModal() {
    const selected = document.querySelectorAll('.lead-select:checked');
    if (selected.length === 0) {
        showNotification('Please select leads to export', 'warning');
        return;
    }
    showNotification(`Export ${selected.length} selected leads feature coming soon!`, 'info');
}
