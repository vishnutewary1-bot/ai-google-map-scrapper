// MapLeads Pro v2.0 - Frontend Application
// Updated for new modular API structure

const API_URL = window.location.origin + '/api';
const WS_URL = window.location.origin.replace('http', 'ws') + '/ws';

let ws = null;
let charts = {};
let currentLeadsPage = 1;
let leadsPerPage = 50;
let totalLeads = 0;

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    console.log('MapLeads Pro v2.0 initializing...');
    loadStats();
    loadRecentJobs();
    connectWebSocket();
    checkHealth();

    setInterval(loadStats, 30000);
    setInterval(loadRecentJobs, 60000);
});

// Page Navigation
function showPage(pageName, evt) {
    document.querySelectorAll('.nav-item').forEach(item => item.classList.remove('active'));

    if (evt && evt.target) {
        const navItem = evt.target.closest('.nav-item');
        if (navItem) navItem.classList.add('active');
    } else {
        document.querySelectorAll('.nav-item').forEach(item => {
            const span = item.querySelector('span');
            if (span && span.textContent.toLowerCase().includes(pageName.toLowerCase())) {
                item.classList.add('active');
            }
        });
    }

    document.querySelectorAll('.page').forEach(page => page.classList.remove('active'));
    const targetPage = document.getElementById('page-' + pageName);
    if (targetPage) targetPage.classList.add('active');

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

    if (pageName === 'jobs') loadJobs();
    if (pageName === 'leads') loadLeads();
    if (pageName === 'analytics') loadAnalytics();
    if (pageName === 'settings') loadSettingsData();
    if (pageName === 'export') loadExports();
}

// Load Statistics
async function loadStats() {
    try {
        const response = await fetch(`${API_URL}/stats`);
        if (!response.ok) throw new Error('Failed to load stats');
        const stats = await response.json();

        document.getElementById('stat-total').textContent = (stats.total_leads || 0).toLocaleString();
        document.getElementById('stat-phone').textContent = (stats.leads_with_phone || 0).toLocaleString();
        document.getElementById('stat-email').textContent = (stats.leads_with_email || 0).toLocaleString();
        document.getElementById('stat-quality').textContent = (stats.avg_quality_score || 0).toFixed(1) + '%';

        const total = stats.total_leads || 0;
        const phonePercent = total > 0 ? ((stats.leads_with_phone || 0) / total * 100).toFixed(1) : 0;
        const emailPercent = total > 0 ? ((stats.leads_with_email || 0) / total * 100).toFixed(1) : 0;

        document.getElementById('stat-phone-percent').textContent = phonePercent + '% of total';
        document.getElementById('stat-email-percent').textContent = emailPercent + '% of total';

        const quality = stats.avg_quality_score || 0;
        let qualityDesc = 'No data';
        if (quality >= 80) qualityDesc = 'Excellent';
        else if (quality >= 60) qualityDesc = 'Good';
        else if (quality >= 40) qualityDesc = 'Fair';
        else if (quality > 0) qualityDesc = 'Poor';
        document.getElementById('stat-quality-desc').textContent = qualityDesc;

        if (stats.leads_today !== undefined) {
            const todayEl = document.getElementById('stat-today-trend');
            if (todayEl) todayEl.textContent = `+${stats.leads_today} today`;
        }

        // Update dashboard quality chart
        updateDashboardQualityChart(stats);

    } catch (error) {
        console.error('Error loading stats:', error);
    }
}

function updateDashboardQualityChart(stats) {
    const ctx = document.getElementById('dashboardQualityChart');
    if (!ctx) return;

    if (charts.dashboardQuality) charts.dashboardQuality.destroy();

    charts.dashboardQuality = new Chart(ctx.getContext('2d'), {
        type: 'doughnut',
        data: {
            labels: ['High (70+)', 'Medium (40-69)', 'Low (<40)'],
            datasets: [{
                data: [
                    stats.high_quality_leads || 0,
                    stats.medium_quality_leads || 0,
                    stats.low_quality_leads || 0
                ],
                backgroundColor: ['#10b981', '#f59e0b', '#ef4444']
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { position: 'bottom' } }
        }
    });
}

// Load Recent Jobs
async function loadRecentJobs() {
    try {
        const response = await fetch(`${API_URL}/jobs?limit=5`);
        if (!response.ok) throw new Error('Failed to load jobs');
        const data = await response.json();
        const jobs = data.jobs || [];

        const tbody = document.getElementById('recentJobsBody');
        if (!tbody) return;

        if (jobs.length === 0) {
            tbody.innerHTML = '<tr><td colspan="3" class="empty-state"><i class="fas fa-inbox"></i><p>No jobs yet</p></td></tr>';
            return;
        }

        tbody.innerHTML = jobs.map(job => `
            <tr>
                <td>
                    <strong>#${job.job_id}</strong><br>
                    <small style="color: var(--gray-500);">${job.search_query}${job.location ? ' in ' + job.location : ''}</small>
                </td>
                <td>${getStatusBadge(job.status)}</td>
                <td>
                    <div style="margin-bottom: 0.25rem;">${job.results_count || 0} / ${job.max_results}</div>
                    <div class="progress"><div class="progress-bar" style="width: ${getProgress(job)}%"></div></div>
                </td>
            </tr>
        `).join('');

        // Update running jobs badge
        const runningJobs = jobs.filter(j => j.status === 'running').length;
        const badge = document.getElementById('runningJobsBadge');
        if (badge) {
            if (runningJobs > 0) {
                badge.textContent = runningJobs;
                badge.style.display = 'inline';
            } else {
                badge.style.display = 'none';
            }
        }

    } catch (error) {
        console.error('Error loading recent jobs:', error);
    }
}

// Load All Jobs
async function loadJobs() {
    try {
        const response = await fetch(`${API_URL}/jobs?limit=100`);
        if (!response.ok) throw new Error('Failed to load jobs');
        const data = await response.json();
        const jobs = data.jobs || [];

        const tbody = document.getElementById('jobsBody');
        if (!tbody) return;

        if (jobs.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="empty-state"><i class="fas fa-inbox"></i><p>No jobs yet</p></td></tr>';
            return;
        }

        tbody.innerHTML = jobs.map(job => `
            <tr>
                <td><strong>#${job.job_id}</strong></td>
                <td>${job.search_query}</td>
                <td>${job.location || '-'}</td>
                <td>${getStatusBadge(job.status)}</td>
                <td>
                    <div style="margin-bottom: 0.25rem;">${job.results_count || 0} / ${job.max_results}</div>
                    <div class="progress"><div class="progress-bar" style="width: ${getProgress(job)}%"></div></div>
                </td>
                <td>${formatDate(job.created_at)}</td>
                <td>
                    <button class="action-btn" onclick="viewJobDetails(${job.job_id})" title="View"><i class="fas fa-eye"></i></button>
                    ${job.status === 'failed' ? `<button class="action-btn action-btn-success" onclick="retryJob(${job.job_id})" title="Retry"><i class="fas fa-redo"></i></button>` : ''}
                    ${job.status !== 'running' ? `<button class="action-btn action-btn-danger" onclick="deleteJob(${job.job_id})" title="Delete"><i class="fas fa-trash"></i></button>` : ''}
                </td>
            </tr>
        `).join('');

    } catch (error) {
        console.error('Error loading jobs:', error);
        showNotification('Failed to load jobs', 'error');
    }
}

// Load Leads
async function loadLeads(page = 1) {
    try {
        showLoading(true);
        currentLeadsPage = page;
        const offset = (page - 1) * leadsPerPage;

        let url = `${API_URL}/leads?limit=${leadsPerPage}&offset=${offset}`;

        // Add filters
        const search = document.getElementById('filterSearch')?.value;
        const city = document.getElementById('filterCity')?.value;
        const category = document.getElementById('filterCategory')?.value;
        const minQuality = document.getElementById('filterMinQuality')?.value;

        if (search) url += `&search=${encodeURIComponent(search)}`;
        if (city) url += `&city=${encodeURIComponent(city)}`;
        if (category) url += `&category=${encodeURIComponent(category)}`;
        if (minQuality) url += `&min_quality=${minQuality}`;

        if (document.getElementById('filterHasPhone')?.checked) url += '&has_phone=true';
        if (document.getElementById('filterHasEmail')?.checked) url += '&has_email=true';
        if (document.getElementById('filterHasWebsite')?.checked) url += '&has_website=true';

        const response = await fetch(url);
        if (!response.ok) throw new Error('Failed to load leads');
        const data = await response.json();

        const leads = data.leads || [];
        totalLeads = data.total || 0;

        document.getElementById('leadsCount').textContent = totalLeads.toLocaleString();

        const tbody = document.getElementById('leadsBody');
        if (!tbody) return;

        if (leads.length === 0) {
            tbody.innerHTML = '<tr><td colspan="8" class="empty-state"><i class="fas fa-inbox"></i><p>No leads found</p></td></tr>';
            document.getElementById('leadsPagination').innerHTML = '';
            showLoading(false);
            return;
        }

        tbody.innerHTML = leads.map(lead => `
            <tr>
                <td><input type="checkbox" class="lead-checkbox" data-id="${lead.id}"></td>
                <td>
                    <strong>${lead.business_name || 'N/A'}</strong>
                    ${lead.website ? `<br><a href="${lead.website}" target="_blank" style="font-size: 0.8125rem; color: var(--primary);"><i class="fas fa-external-link-alt"></i> Website</a>` : ''}
                </td>
                <td>${lead.category || '-'}</td>
                <td>${lead.city || '-'}${lead.pincode ? ', ' + lead.pincode : ''}</td>
                <td>
                    ${lead.phone ? `<a href="tel:${lead.phone}">${lead.phone}</a>` : '-'}
                    ${lead.email ? `<br><a href="mailto:${lead.email}" style="font-size: 0.8125rem;">${lead.email}</a>` : ''}
                </td>
                <td>${lead.rating ? lead.rating.toFixed(1) + ' <i class="fas fa-star" style="color: #f59e0b;"></i>' : '-'}</td>
                <td>${getQualityBadge(lead.quality_score)}</td>
                <td>
                    <button class="action-btn" onclick="viewLeadDetails(${lead.id})" title="View"><i class="fas fa-eye"></i></button>
                    <button class="action-btn action-btn-danger" onclick="deleteLead(${lead.id})" title="Delete"><i class="fas fa-trash"></i></button>
                </td>
            </tr>
        `).join('');

        // Add event listeners to individual checkboxes
        document.querySelectorAll('.lead-checkbox').forEach(cb => {
            cb.addEventListener('change', updateSelectedCount);
        });

        // Initialize select all functionality
        initSelectAll();

        // Reset select all checkbox and count
        const selectAllCheckbox = document.getElementById('selectAll');
        if (selectAllCheckbox) selectAllCheckbox.checked = false;
        updateSelectedCount();

        // Pagination
        renderPagination();
        showLoading(false);

    } catch (error) {
        console.error('Error loading leads:', error);
        showNotification('Failed to load leads', 'error');
        showLoading(false);
    }
}

function renderPagination() {
    const totalPages = Math.ceil(totalLeads / leadsPerPage);
    const pagination = document.getElementById('leadsPagination');
    if (!pagination || totalPages <= 1) {
        if (pagination) pagination.innerHTML = '';
        return;
    }

    let html = '';
    html += `<button class="pagination-btn" onclick="loadLeads(${currentLeadsPage - 1})" ${currentLeadsPage === 1 ? 'disabled' : ''}><i class="fas fa-chevron-left"></i></button>`;

    const maxVisible = 5;
    let start = Math.max(1, currentLeadsPage - 2);
    let end = Math.min(totalPages, start + maxVisible - 1);
    if (end - start < maxVisible - 1) start = Math.max(1, end - maxVisible + 1);

    if (start > 1) {
        html += `<button class="pagination-btn" onclick="loadLeads(1)">1</button>`;
        if (start > 2) html += `<span style="padding: 0 0.5rem;">...</span>`;
    }

    for (let i = start; i <= end; i++) {
        html += `<button class="pagination-btn ${i === currentLeadsPage ? 'active' : ''}" onclick="loadLeads(${i})">${i}</button>`;
    }

    if (end < totalPages) {
        if (end < totalPages - 1) html += `<span style="padding: 0 0.5rem;">...</span>`;
        html += `<button class="pagination-btn" onclick="loadLeads(${totalPages})">${totalPages}</button>`;
    }

    html += `<button class="pagination-btn" onclick="loadLeads(${currentLeadsPage + 1})" ${currentLeadsPage === totalPages ? 'disabled' : ''}><i class="fas fa-chevron-right"></i></button>`;

    pagination.innerHTML = html;
}

// Filters
function applyFilters() {
    loadLeads(1);
}

function applyAdvancedFilters() {
    loadLeads(1);
}

function saveFilterPreset() {
    const filters = {
        search: document.getElementById('filterSearch')?.value,
        city: document.getElementById('filterCity')?.value,
        category: document.getElementById('filterCategory')?.value,
        minQuality: document.getElementById('filterMinQuality')?.value,
        hasPhone: document.getElementById('filterHasPhone')?.checked,
        hasEmail: document.getElementById('filterHasEmail')?.checked,
        hasWebsite: document.getElementById('filterHasWebsite')?.checked
    };
    localStorage.setItem('leadFilterPreset', JSON.stringify(filters));
    showNotification('Filter preset saved!', 'success');
}

function clearFilters() {
    document.getElementById('filterSearch').value = '';
    document.getElementById('filterCity').value = '';
    document.getElementById('filterCategory').value = '';
    document.getElementById('filterMinQuality').value = '';
    if (document.getElementById('filterHasPhone')) document.getElementById('filterHasPhone').checked = false;
    if (document.getElementById('filterHasEmail')) document.getElementById('filterHasEmail').checked = false;
    if (document.getElementById('filterHasWebsite')) document.getElementById('filterHasWebsite').checked = false;
    loadLeads(1);
    showNotification('Filters cleared', 'info');
}

function applyQuickFilter(filterType) {
    clearFilters();
    switch (filterType) {
        case 'high_quality':
            document.getElementById('filterMinQuality').value = '70';
            break;
        case 'with_email':
            document.getElementById('filterHasEmail').checked = true;
            break;
        case 'with_phone':
            document.getElementById('filterHasPhone').checked = true;
            break;
        case 'top_rated':
            // Would need min_rating filter
            break;
    }
    loadLeads(1);
}

// Start Scraping
async function startScrape(event) {
    event.preventDefault();

    const searchQuery = document.getElementById('searchQuery').value;
    const location = document.getElementById('searchLocation').value;
    const maxResults = parseInt(document.getElementById('maxResults').value) || 50;

    if (!searchQuery || searchQuery.trim() === '') {
        showNotification('Please enter a search query', 'error');
        return false;
    }

    const extractEmails = document.getElementById('extractEmails')?.value === 'true';
    const extractSocial = document.getElementById('extractSocial')?.value === 'true';
    const headless = document.getElementById('headlessMode')?.checked !== false;

    const data = {
        search_query: searchQuery.trim(),
        location: location?.trim() || null,
        max_results: maxResults,
        extract_emails: extractEmails,
        extract_social: extractSocial,
        headless: headless
    };

    try {
        showLoading(true);
        showNotification('Starting scrape job...', 'info');

        const response = await fetch(`${API_URL}/scrape`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });

        const result = await response.json();

        if (!response.ok) throw new Error(result.detail || 'Failed to start scrape');

        showNotification(`Scraping started! Job #${result.job_id}`, 'success');
        document.getElementById('scrapeForm').reset();

        if (document.getElementById('headlessMode')) document.getElementById('headlessMode').checked = true;
        if (document.getElementById('deduplicateResults')) document.getElementById('deduplicateResults').checked = true;

        setTimeout(() => {
            showPage('jobs');
            loadJobs();
        }, 1500);

        showLoading(false);
        return false;

    } catch (error) {
        console.error('Error starting scrape:', error);
        showNotification('Failed to start scraping: ' + error.message, 'error');
        showLoading(false);
        return false;
    }
}

// Bulk Scrape
async function startBulkScrape(event) {
    event.preventDefault();

    const searchQuery = document.getElementById('bulkQuery').value.trim();
    if (!searchQuery) {
        showNotification('Please enter a search query', 'error');
        return false;
    }

    const locations = document.getElementById('bulkLocations').value
        .split(/[\n,]/)
        .map(l => l.trim())
        .filter(l => l.length > 0);

    if (locations.length === 0) {
        showNotification('Please enter at least one location', 'error');
        return false;
    }

    const maxResultsPerLocation = parseInt(document.getElementById('bulkMaxResults').value) || 50;
    const delayBetween = parseInt(document.getElementById('bulkDelay').value) || 60;
    const extractEmails = document.getElementById('bulkExtractEmails')?.checked !== false;

    // Build searches array - API expects an array of ScrapeRequest objects
    const searches = locations.map(location => ({
        search_query: searchQuery,
        location: location,
        max_results: maxResultsPerLocation,
        extract_emails: extractEmails,
        extract_social: true,
        extract_contacts: true,
        extract_insights: true,
        extract_reviews: false,
        extract_popular_times: false,
        enrich_from_website: extractEmails,
        export_excel: true,
        export_sheets: false,
        headless: true
    }));

    const data = {
        searches: searches,
        delay_between: delayBetween
    };

    try {
        showLoading(true);
        showNotification(`Starting bulk scrape for ${locations.length} locations...`, 'info');

        const response = await fetch(`${API_URL}/bulk-scrape`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || 'Failed to start bulk scrape');
        }

        const result = await response.json();
        showNotification(`Bulk scraping started! Job #${result.job_id} - ${locations.length} locations queued.`, 'success');

        document.getElementById('bulkScrapeForm').reset();
        setTimeout(() => showPage('jobs'), 1500);
        showLoading(false);

    } catch (error) {
        console.error('Error starting bulk scrape:', error);
        showNotification('Failed to start bulk scraping: ' + error.message, 'error');
        showLoading(false);
    }

    return false;
}

// Export Data
async function exportData(event) {
    event.preventDefault();

    const filters = {};
    if (document.getElementById('exportHasPhone')?.checked) filters.has_phone = true;
    if (document.getElementById('exportHasEmail')?.checked) filters.has_email = true;

    const city = document.getElementById('exportCity')?.value;
    if (city) filters.city = city;

    const minQuality = parseInt(document.getElementById('exportMinQuality')?.value);
    if (minQuality > 0) filters.min_quality = minQuality;

    const data = {
        format: document.getElementById('exportFormat').value,
        filters: filters
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

        if (result.success && result.download_url) {
            showNotification(`Export successful! ${result.records_exported} leads exported.`, 'success');
            window.open(API_URL.replace('/api', '') + result.download_url, '_blank');
        } else if (result.records_exported > 0) {
            showNotification(`Exported ${result.records_exported} leads`, 'success');
        } else {
            showNotification(result.error || 'Export completed', 'warning');
        }

        loadExports();
        showLoading(false);

    } catch (error) {
        console.error('Error exporting data:', error);
        showNotification('Export failed: ' + error.message, 'error');
        showLoading(false);
    }

    return false;
}

async function loadExports() {
    try {
        const response = await fetch(`${API_URL}/export/list`);
        if (!response.ok) return;

        const data = await response.json();
        const exports = data.exports || [];
        const container = document.getElementById('exportsList');
        if (!container) return;

        if (exports.length === 0) {
            container.innerHTML = '<div class="empty-state"><i class="fas fa-file-download"></i><p>No exports yet</p></div>';
            return;
        }

        container.innerHTML = exports.slice(0, 5).map(exp => `
            <div style="display: flex; justify-content: space-between; align-items: center; padding: 0.75rem; border-bottom: 1px solid var(--border-color);">
                <div>
                    <strong>${exp.filename}</strong>
                    <div style="font-size: 0.8125rem; color: var(--gray-500);">${formatBytes(exp.size)} - ${formatDate(exp.created_at)}</div>
                </div>
                <a href="${API_URL.replace('/api', '')}${exp.download_url}" class="btn btn-sm btn-outline" download><i class="fas fa-download"></i></a>
            </div>
        `).join('');

    } catch (error) {
        console.error('Error loading exports:', error);
    }
}

function exportSelected() {
    const selected = document.querySelectorAll('.lead-checkbox:checked');
    if (selected.length === 0) {
        showNotification('Please select leads to export', 'warning');
        return;
    }
    showPage('export');
}

// Select All functionality
function initSelectAll() {
    const selectAllCheckbox = document.getElementById('selectAll');
    if (selectAllCheckbox) {
        selectAllCheckbox.addEventListener('change', function() {
            const checkboxes = document.querySelectorAll('.lead-checkbox');
            checkboxes.forEach(cb => cb.checked = this.checked);
            updateSelectedCount();
        });
    }
}

function updateSelectedCount() {
    const selected = document.querySelectorAll('.lead-checkbox:checked');
    const countEl = document.getElementById('selectedCount');
    if (countEl) {
        if (selected.length > 0) {
            countEl.textContent = `${selected.length} selected`;
        } else {
            countEl.textContent = '';
        }
    }

    // Update select all checkbox state
    const selectAllCheckbox = document.getElementById('selectAll');
    const allCheckboxes = document.querySelectorAll('.lead-checkbox');
    if (selectAllCheckbox && allCheckboxes.length > 0) {
        selectAllCheckbox.checked = selected.length === allCheckboxes.length;
        selectAllCheckbox.indeterminate = selected.length > 0 && selected.length < allCheckboxes.length;
    }
}

// Delete selected leads
async function deleteSelected() {
    const selected = document.querySelectorAll('.lead-checkbox:checked');
    if (selected.length === 0) {
        showNotification('Please select leads to delete', 'warning');
        return;
    }

    if (!confirm(`Are you sure you want to delete ${selected.length} lead(s)? This action cannot be undone.`)) {
        return;
    }

    showLoading(true);

    // Collect all selected lead IDs
    const leadIds = Array.from(selected).map(cb => parseInt(cb.dataset.id));

    try {
        // Use bulk delete API for efficiency
        const response = await fetch(`${API_URL}/leads/bulk-delete`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(leadIds)
        });

        if (response.ok) {
            const result = await response.json();
            showNotification(`Successfully deleted ${result.deleted} lead(s)`, 'success');
            loadLeads(currentLeadsPage);
            loadStats();
        } else {
            throw new Error('Bulk delete failed');
        }
    } catch (error) {
        console.error('Error deleting leads:', error);
        showNotification('Failed to delete leads', 'error');
    }

    showLoading(false);

    // Reset select all checkbox
    const selectAllCheckbox = document.getElementById('selectAll');
    if (selectAllCheckbox) selectAllCheckbox.checked = false;
    updateSelectedCount();
}

// Select all leads on current page
function selectAllLeads() {
    const checkboxes = document.querySelectorAll('.lead-checkbox');
    checkboxes.forEach(cb => cb.checked = true);
    const selectAllCheckbox = document.getElementById('selectAll');
    if (selectAllCheckbox) selectAllCheckbox.checked = true;
    updateSelectedCount();
    showNotification(`Selected ${checkboxes.length} leads on this page`, 'info');
}

// Deselect all leads
function deselectAllLeads() {
    const checkboxes = document.querySelectorAll('.lead-checkbox');
    checkboxes.forEach(cb => cb.checked = false);
    const selectAllCheckbox = document.getElementById('selectAll');
    if (selectAllCheckbox) selectAllCheckbox.checked = false;
    updateSelectedCount();
    showNotification('All leads deselected', 'info');
}

// Invert selection - select unselected leads and deselect selected ones
// Useful workflow: Select All -> Deselect leads you want to KEEP -> Delete Selected
function invertSelection() {
    const checkboxes = document.querySelectorAll('.lead-checkbox');
    let selectedCount = 0;
    let deselectedCount = 0;

    checkboxes.forEach(cb => {
        if (cb.checked) {
            cb.checked = false;
            deselectedCount++;
        } else {
            cb.checked = true;
            selectedCount++;
        }
    });

    updateSelectedCount();
    showNotification(`Selection inverted: ${selectedCount} selected, ${deselectedCount} deselected`, 'info');
}

// Delete ALL leads in the database
async function deleteAllLeads() {
    if (!confirm(`WARNING: This will delete ALL ${totalLeads} leads from the database!\n\nThis action CANNOT be undone.\n\nAre you absolutely sure?`)) {
        return;
    }

    // Double confirmation for safety
    const confirmText = prompt(`To confirm deletion of ALL ${totalLeads} leads, type "DELETE ALL" below:`);
    if (confirmText !== 'DELETE ALL') {
        showNotification('Deletion cancelled - confirmation text did not match', 'warning');
        return;
    }

    showLoading(true);
    showNotification('Deleting all leads... This may take a moment.', 'info');

    try {
        // Fetch all lead IDs first
        const response = await fetch(`${API_URL}/leads?limit=10000`);
        if (!response.ok) throw new Error('Failed to fetch leads');

        const data = await response.json();
        const allLeadIds = data.leads.map(lead => lead.id);

        if (allLeadIds.length === 0) {
            showNotification('No leads to delete', 'warning');
            showLoading(false);
            return;
        }

        // Delete in batches of 100 for efficiency
        const batchSize = 100;
        let totalDeleted = 0;

        for (let i = 0; i < allLeadIds.length; i += batchSize) {
            const batch = allLeadIds.slice(i, i + batchSize);
            const deleteResponse = await fetch(`${API_URL}/leads/bulk-delete`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(batch)
            });

            if (deleteResponse.ok) {
                const result = await deleteResponse.json();
                totalDeleted += result.deleted;
            }
        }

        showNotification(`Successfully deleted ${totalDeleted} leads!`, 'success');
        loadLeads(1);
        loadStats();

    } catch (error) {
        console.error('Error deleting all leads:', error);
        showNotification('Failed to delete all leads: ' + error.message, 'error');
    }

    showLoading(false);
}

// Analytics
async function loadAnalytics() {
    try {
        // Load quality analytics
        const qualityResponse = await fetch(`${API_URL}/analytics/quality`);
        if (qualityResponse.ok) {
            const quality = await qualityResponse.json();
            document.getElementById('analytics-high-quality').textContent = (quality.high_quality_leads || 0).toLocaleString();
            document.getElementById('analytics-medium-quality').textContent = (quality.medium_quality_leads || 0).toLocaleString();
            document.getElementById('analytics-low-quality').textContent = (quality.low_quality_leads || 0).toLocaleString();
        }

        // Load stats for charts
        const statsResponse = await fetch(`${API_URL}/stats`);
        if (statsResponse.ok) {
            const stats = await statsResponse.json();

            // Categories chart
            if (stats.top_categories && stats.top_categories.length > 0) {
                const ctxCategories = document.getElementById('categoriesChart');
                if (ctxCategories) {
                    if (charts.categories) charts.categories.destroy();
                    charts.categories = new Chart(ctxCategories.getContext('2d'), {
                        type: 'bar',
                        data: {
                            labels: stats.top_categories.map(c => c.category || 'Unknown'),
                            datasets: [{
                                label: 'Leads',
                                data: stats.top_categories.map(c => c.count),
                                backgroundColor: 'rgba(99, 102, 241, 0.8)'
                            }]
                        },
                        options: {
                            responsive: true,
                            maintainAspectRatio: false,
                            plugins: { legend: { display: false } }
                        }
                    });
                }
            }

            // Cities chart
            if (stats.top_cities && stats.top_cities.length > 0) {
                const ctxCities = document.getElementById('citiesChart');
                if (ctxCities) {
                    if (charts.cities) charts.cities.destroy();
                    charts.cities = new Chart(ctxCities.getContext('2d'), {
                        type: 'bar',
                        data: {
                            labels: stats.top_cities.map(c => c.city || 'Unknown'),
                            datasets: [{
                                label: 'Leads',
                                data: stats.top_cities.map(c => c.count),
                                backgroundColor: 'rgba(16, 185, 129, 0.8)'
                            }]
                        },
                        options: {
                            responsive: true,
                            maintainAspectRatio: false,
                            plugins: { legend: { display: false } }
                        }
                    });
                }
            }
        }

    } catch (error) {
        console.error('Error loading analytics:', error);
    }
}

// Settings
async function loadSettingsData() {
    checkHealth();
}

async function saveSettings(event) {
    event.preventDefault();

    const settings = {
        delay_between_requests_min: parseFloat(document.getElementById('settingDelay').value),
        headless_mode: document.getElementById('settingHeadless').value === 'true',
        auto_deduplicate: document.getElementById('settingDeduplicate').value === 'true'
    };

    localStorage.setItem('scraperSettings', JSON.stringify(settings));
    showNotification('Settings saved!', 'success');
    return false;
}

async function checkHealth() {
    try {
        const response = await fetch(`${API_URL}/health`);
        if (response.ok) {
            const health = await response.json();

            const apiEl = document.getElementById('health-api');
            const dbEl = document.getElementById('health-db');
            const versionEl = document.getElementById('health-version');

            if (apiEl) {
                apiEl.textContent = health.status === 'healthy' ? 'Online' : health.status;
                apiEl.className = 'value ' + (health.status === 'healthy' ? 'good' : 'bad');
            }

            if (dbEl) {
                dbEl.textContent = health.database || 'Unknown';
                dbEl.className = 'value ' + (health.database === 'connected' ? 'good' : 'warning');
            }

            if (versionEl) {
                versionEl.textContent = health.version || '-';
            }

            // Update WebSocket status
            const wsStatus = document.getElementById('wsStatus');
            const wsDot = document.getElementById('wsStatusDot');
            if (wsStatus) wsStatus.textContent = 'Connected';
            if (wsDot) wsDot.classList.remove('disconnected');
        }
    } catch (error) {
        console.error('Health check failed:', error);
        const apiEl = document.getElementById('health-api');
        if (apiEl) {
            apiEl.textContent = 'Offline';
            apiEl.className = 'value bad';
        }
    }
}

// WebSocket Connection
function connectWebSocket() {
    try {
        ws = new WebSocket(WS_URL);

        ws.onopen = () => {
            console.log('WebSocket connected');
            const wsStatus = document.getElementById('wsStatus');
            const wsDot = document.getElementById('wsStatusDot');
            if (wsStatus) wsStatus.textContent = 'Connected';
            if (wsDot) wsDot.classList.remove('disconnected');
        };

        ws.onmessage = (event) => {
            try {
                const message = JSON.parse(event.data);
                handleWebSocketMessage(message);
            } catch (e) {
                console.error('WS message parse error:', e);
            }
        };

        ws.onerror = (error) => {
            console.error('WebSocket error:', error);
        };

        ws.onclose = () => {
            console.log('WebSocket disconnected');
            const wsStatus = document.getElementById('wsStatus');
            const wsDot = document.getElementById('wsStatusDot');
            if (wsStatus) wsStatus.textContent = 'Disconnected';
            if (wsDot) wsDot.classList.add('disconnected');
            setTimeout(connectWebSocket, 5000);
        };

    } catch (error) {
        console.error('Failed to connect WebSocket:', error);
    }
}

function handleWebSocketMessage(message) {
    console.log('WebSocket message:', message);

    if (message.type === 'job_update' || message.type === 'progress') {
        loadRecentJobs();
        if (document.getElementById('page-jobs').classList.contains('active')) {
            loadJobs();
        }
    }

    if (message.type === 'job_completed' || message.type === 'completed') {
        showNotification(`Job completed! ${message.leads_scraped || message.results_count || 0} leads scraped.`, 'success');
        loadStats();
        loadRecentJobs();
    }

    if (message.type === 'job_failed' || message.type === 'failed') {
        showNotification(`Job failed: ${message.error || 'Unknown error'}`, 'error');
        loadRecentJobs();
    }
}

// View Lead Details
async function viewLeadDetails(id) {
    try {
        showLoading(true);
        const response = await fetch(`${API_URL}/leads/${id}`);
        if (!response.ok) throw new Error('Failed to load lead');

        const lead = await response.json();
        showLoading(false);

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
                                <div class="detail-row"><span class="label">Address:</span> <span>${lead.address || 'N/A'}</span></div>
                                <div class="detail-row"><span class="label">City:</span> <span>${lead.city || 'N/A'}</span></div>
                                <div class="detail-row"><span class="label">State:</span> <span>${lead.state || 'N/A'}</span></div>
                                <div class="detail-row"><span class="label">Pin Code:</span> <span>${lead.pincode || 'N/A'}</span></div>
                            </div>
                            <div class="detail-section">
                                <h3>Business Info</h3>
                                <div class="detail-row"><span class="label">Category:</span> <span>${lead.category || 'N/A'}</span></div>
                                <div class="detail-row"><span class="label">Rating:</span> <span>${lead.rating ? lead.rating + ' ★' : 'N/A'}</span></div>
                                <div class="detail-row"><span class="label">Reviews:</span> <span>${lead.review_count || 'N/A'}</span></div>
                                <div class="detail-row"><span class="label">Quality:</span> <span>${getQualityBadge(lead.quality_score)}</span></div>
                            </div>
                            <div class="detail-section">
                                <h3>Social Media</h3>
                                <div class="detail-row"><span class="label">Facebook:</span> <span>${lead.facebook ? `<a href="${lead.facebook}" target="_blank">View</a>` : 'N/A'}</span></div>
                                <div class="detail-row"><span class="label">Instagram:</span> <span>${lead.instagram ? `<a href="${lead.instagram}" target="_blank">View</a>` : 'N/A'}</span></div>
                                <div class="detail-row"><span class="label">LinkedIn:</span> <span>${lead.linkedin ? `<a href="${lead.linkedin}" target="_blank">View</a>` : 'N/A'}</span></div>
                                <div class="detail-row"><span class="label">Twitter:</span> <span>${lead.twitter ? `<a href="${lead.twitter}" target="_blank">View</a>` : 'N/A'}</span></div>
                            </div>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button class="btn btn-secondary" onclick="closeLeadModal()">Close</button>
                        ${lead.maps_url ? `<a href="${lead.maps_url}" target="_blank" class="btn btn-primary"><i class="fas fa-map-marker-alt"></i> Open in Maps</a>` : ''}
                    </div>
                </div>
            </div>
        `;

        document.body.insertAdjacentHTML('beforeend', modalHtml);

    } catch (error) {
        showLoading(false);
        console.error('Error loading lead:', error);
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

// View Job Details
async function viewJobDetails(id) {
    try {
        showLoading(true);
        const response = await fetch(`${API_URL}/jobs/${id}`);
        if (!response.ok) throw new Error('Failed to load job');

        const job = await response.json();
        showLoading(false);

        const modalHtml = `
            <div class="modal-overlay" id="jobModal" onclick="closeModal(event)">
                <div class="modal-content" onclick="event.stopPropagation()" style="max-width: 500px;">
                    <div class="modal-header">
                        <h2>Job #${job.job_id} Details</h2>
                        <button class="modal-close" onclick="closeJobModal()">&times;</button>
                    </div>
                    <div class="modal-body">
                        <div class="detail-section">
                            <div class="detail-row"><span class="label">Search Query:</span> <span>${job.search_query}</span></div>
                            <div class="detail-row"><span class="label">Location:</span> <span>${job.location || 'N/A'}</span></div>
                            <div class="detail-row"><span class="label">Status:</span> <span>${getStatusBadge(job.status)}</span></div>
                            <div class="detail-row"><span class="label">Progress:</span> <span>${job.results_count || 0} / ${job.max_results}</span></div>
                            <div class="detail-row"><span class="label">Error:</span> <span>${job.error_message || 'None'}</span></div>
                            <div class="detail-row"><span class="label">Started:</span> <span>${formatDate(job.started_at)}</span></div>
                            <div class="detail-row"><span class="label">Completed:</span> <span>${job.completed_at ? formatDate(job.completed_at) : 'N/A'}</span></div>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button class="btn btn-secondary" onclick="closeJobModal()">Close</button>
                        ${job.status === 'failed' ? `<button class="btn btn-primary" onclick="retryJob(${job.job_id}); closeJobModal();">Retry</button>` : ''}
                    </div>
                </div>
            </div>
        `;

        document.body.insertAdjacentHTML('beforeend', modalHtml);

    } catch (error) {
        showLoading(false);
        console.error('Error loading job:', error);
        showNotification('Failed to load job details', 'error');
    }
}

function closeJobModal() {
    const modal = document.getElementById('jobModal');
    if (modal) modal.remove();
}

// Job Actions
async function retryJob(id) {
    try {
        showLoading(true);
        const response = await fetch(`${API_URL}/jobs/${id}/retry`, { method: 'POST' });
        if (!response.ok) throw new Error('Retry failed');

        showNotification(`Job #${id} queued for retry`, 'success');
        loadJobs();
        loadRecentJobs();
        showLoading(false);

    } catch (error) {
        showLoading(false);
        console.error('Error retrying job:', error);
        showNotification('Failed to retry job', 'error');
    }
}

async function deleteJob(id) {
    if (!confirm('Are you sure you want to delete this job?')) return;

    try {
        const response = await fetch(`${API_URL}/jobs/${id}`, { method: 'DELETE' });
        if (!response.ok) throw new Error('Delete failed');

        showNotification(`Job #${id} deleted`, 'success');
        loadJobs();
        loadRecentJobs();

    } catch (error) {
        console.error('Error deleting job:', error);
        showNotification('Failed to delete job', 'error');
    }
}

async function deleteLead(id) {
    if (!confirm('Are you sure you want to delete this lead?')) return;

    try {
        const response = await fetch(`${API_URL}/leads/${id}`, { method: 'DELETE' });
        if (!response.ok) throw new Error('Delete failed');

        showNotification('Lead deleted', 'success');
        loadLeads(currentLeadsPage);
        loadStats();

    } catch (error) {
        console.error('Error deleting lead:', error);
        showNotification('Failed to delete lead', 'error');
    }
}

// Utility Functions
function getStatusBadge(status) {
    const badges = {
        'completed': '<span class="badge badge-success">Completed</span>',
        'running': '<span class="badge badge-info">Running</span>',
        'pending': '<span class="badge badge-warning">Pending</span>',
        'failed': '<span class="badge badge-danger">Failed</span>',
        'paused': '<span class="badge badge-secondary">Paused</span>'
    };
    return badges[status] || `<span class="badge badge-secondary">${status}</span>`;
}

function getQualityBadge(score) {
    score = score || 0;
    if (score >= 70) return `<span class="badge badge-success">${score}%</span>`;
    if (score >= 40) return `<span class="badge badge-warning">${score}%</span>`;
    return `<span class="badge badge-danger">${score}%</span>`;
}

function getProgress(job) {
    const target = job.max_results || 0;
    const current = job.results_count || 0;
    if (target === 0) return 0;
    return Math.min(100, (current / target) * 100);
}

function formatDate(dateString) {
    if (!dateString) return '-';
    const date = new Date(dateString);
    return date.toLocaleString();
}

function formatBytes(bytes) {
    if (!bytes) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

function showNotification(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    if (!container) {
        console.log(`[${type.toUpperCase()}] ${message}`);
        return;
    }

    const icons = {
        success: 'check-circle',
        error: 'exclamation-circle',
        warning: 'exclamation-triangle',
        info: 'info-circle'
    };

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
        <div class="toast-icon"><i class="fas fa-${icons[type] || 'info-circle'}"></i></div>
        <div class="toast-content">
            <div class="toast-title">${type.charAt(0).toUpperCase() + type.slice(1)}</div>
            <div class="toast-message">${message}</div>
        </div>
        <button class="toast-close" onclick="this.parentElement.remove()">&times;</button>
    `;

    container.appendChild(toast);
    setTimeout(() => {
        toast.style.animation = 'slideOut 0.3s ease forwards';
        setTimeout(() => toast.remove(), 300);
    }, 5000);
}

function showLoading(show) {
    const overlay = document.getElementById('loadingOverlay');
    if (overlay) {
        if (show) overlay.classList.add('active');
        else overlay.classList.remove('active');
    }
}

function refreshData() {
    loadStats();
    loadRecentJobs();

    const activePage = document.querySelector('.page.active');
    if (activePage) {
        const pageId = activePage.id.replace('page-', '');
        if (pageId === 'jobs') loadJobs();
        if (pageId === 'leads') loadLeads(currentLeadsPage);
        if (pageId === 'analytics') loadAnalytics();
        if (pageId === 'export') loadExports();
    }

    showNotification('Data refreshed', 'success');
}

function resetForm() {
    const form = document.getElementById('scrapeForm');
    if (form) {
        form.reset();
        if (document.getElementById('headlessMode')) document.getElementById('headlessMode').checked = true;
        if (document.getElementById('deduplicateResults')) document.getElementById('deduplicateResults').checked = true;

        document.querySelectorAll('.feature-card').forEach(card => {
            const input = card.querySelector('input[type="hidden"]');
            if (input) {
                if (['extractEmails', 'extractSocial', 'extractInsights'].includes(input.id)) {
                    card.classList.add('active');
                    input.value = 'true';
                } else {
                    card.classList.remove('active');
                    input.value = 'false';
                }
            }
        });

        showNotification('Form reset', 'info');
    }
}

// Add CSS animation for toast close
const style = document.createElement('style');
style.textContent = `@keyframes slideOut { from { transform: translateX(0); opacity: 1; } to { transform: translateX(100%); opacity: 0; } }`;
document.head.appendChild(style);

// ==================== NEW FEATURES (v2.0) ====================

// Geo Search
function setGeoLocation(lat, lng) {
    document.getElementById('geoLat').value = lat;
    document.getElementById('geoLng').value = lng;
}

async function startGeoSearch(event) {
    event.preventDefault();

    const data = {
        search_query: document.getElementById('geoQuery').value.trim(),
        latitude: parseFloat(document.getElementById('geoLat').value),
        longitude: parseFloat(document.getElementById('geoLng').value),
        radius_km: parseFloat(document.getElementById('geoRadius').value) || 5,
        grid_size: parseInt(document.getElementById('geoGrid').value) || 3,
        max_results: parseInt(document.getElementById('geoMaxResults').value) || 50,
        extract_emails: true,
        extract_social: true
    };

    try {
        showLoading(true);
        const response = await fetch(`${API_URL}/geo-scrape`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });

        const result = await response.json();

        if (!response.ok) throw new Error(result.detail || 'Geo search failed');

        showNotification(`Geo search started! Job #${result.job_id} - ${result.grid_points} grid points`, 'success');
        document.getElementById('geoSearchForm').reset();
        setTimeout(() => showPage('jobs'), 1500);

    } catch (error) {
        console.error('Geo search error:', error);
        showNotification('Geo search failed: ' + error.message, 'error');
    } finally {
        showLoading(false);
    }

    return false;
}

// Webhooks
async function registerWebhook(event) {
    event.preventDefault();

    const events = Array.from(document.querySelectorAll('input[name="webhookEvents"]:checked'))
        .map(cb => cb.value);

    const data = {
        name: document.getElementById('webhookName').value.trim(),
        url: document.getElementById('webhookUrl').value.trim(),
        secret: document.getElementById('webhookSecret').value.trim() || null,
        events: events.length > 0 ? events : ['job.completed', 'lead.created']
    };

    try {
        showLoading(true);
        const response = await fetch(`${API_URL}/webhooks/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });

        const result = await response.json();

        if (!response.ok) throw new Error(result.detail || 'Registration failed');

        showNotification(`Webhook "${data.name}" registered successfully!`, 'success');
        document.getElementById('webhookForm').reset();
        loadWebhooks();

    } catch (error) {
        console.error('Webhook registration error:', error);
        showNotification('Failed to register webhook: ' + error.message, 'error');
    } finally {
        showLoading(false);
    }

    return false;
}

async function loadWebhooks() {
    try {
        const response = await fetch(`${API_URL}/webhooks`);
        const data = await response.json();

        const container = document.getElementById('webhooksList');
        if (!container) return;

        const webhooks = data.registered_webhooks || [];

        if (webhooks.length === 0) {
            container.innerHTML = '<div class="empty-state"><i class="fas fa-inbox"></i><p>No webhooks registered</p></div>';
            return;
        }

        container.innerHTML = webhooks.map(wh => `
            <div style="display: flex; justify-content: space-between; align-items: center; padding: 1rem; border-bottom: 1px solid var(--border);">
                <div>
                    <strong>${wh.name}</strong>
                    <div style="font-size: 0.8125rem; color: var(--gray);">${wh.url}</div>
                    <div style="font-size: 0.75rem; margin-top: 0.25rem;">
                        ${wh.events.map(e => `<span class="badge badge-info">${e}</span>`).join(' ')}
                    </div>
                </div>
                <div>
                    <button class="action-btn" onclick="testWebhook('${wh.name}')" title="Test"><i class="fas fa-paper-plane"></i></button>
                    <button class="action-btn action-btn-danger" onclick="deleteWebhook('${wh.name}')" title="Delete"><i class="fas fa-trash"></i></button>
                </div>
            </div>
        `).join('');

    } catch (error) {
        console.error('Failed to load webhooks:', error);
    }
}

async function testWebhook(name) {
    try {
        const response = await fetch(`${API_URL}/webhooks/test`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ webhook_name: name, event_type: 'test' })
        });

        const result = await response.json();

        if (result.success) {
            showNotification(`Test webhook sent to "${name}"`, 'success');
        } else {
            showNotification(`Test failed: ${result.message}`, 'warning');
        }

    } catch (error) {
        showNotification('Test failed: ' + error.message, 'error');
    }
}

async function deleteWebhook(name) {
    if (!confirm(`Delete webhook "${name}"?`)) return;

    try {
        const response = await fetch(`${API_URL}/webhooks/${name}`, { method: 'DELETE' });

        if (response.ok) {
            showNotification(`Webhook "${name}" deleted`, 'success');
            loadWebhooks();
        }
    } catch (error) {
        showNotification('Failed to delete webhook', 'error');
    }
}

// Sentiment Analysis
async function analyzeSentiment(event) {
    event.preventDefault();

    const leadId = document.getElementById('sentimentLeadId').value;
    const text = document.getElementById('sentimentText').value.trim();

    const data = {};
    if (leadId) data.lead_id = parseInt(leadId);
    if (text) data.text = text;

    if (!leadId && !text) {
        showNotification('Please enter a lead ID or text to analyze', 'warning');
        return false;
    }

    try {
        showLoading(true);
        const response = await fetch(`${API_URL}/sentiment/analyze`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });

        const result = await response.json();

        if (!response.ok) throw new Error(result.detail || 'Analysis failed');

        // Display results
        const resultsDiv = document.getElementById('sentimentResults');
        const statsDiv = document.getElementById('sentimentStats');

        statsDiv.innerHTML = `
            <div class="stat-card ${result.overall_sentiment === 'positive' ? 'success' : result.overall_sentiment === 'negative' ? 'danger' : 'warning'}">
                <h3>Overall Sentiment</h3>
                <div class="value">${result.overall_sentiment}</div>
            </div>
            <div class="stat-card info">
                <h3>Sentiment Score</h3>
                <div class="value">${result.sentiment_score}/100</div>
            </div>
            <div class="stat-card success">
                <h3>Positive</h3>
                <div class="value">${result.positive_count || 0}</div>
            </div>
            <div class="stat-card danger">
                <h3>Negative</h3>
                <div class="value">${result.negative_count || 0}</div>
            </div>
        `;

        resultsDiv.style.display = 'block';
        showNotification('Sentiment analysis complete', 'success');

    } catch (error) {
        console.error('Sentiment analysis error:', error);
        showNotification('Analysis failed: ' + error.message, 'error');
    } finally {
        showLoading(false);
    }

    return false;
}

// Competitor Comparison
async function compareCompetitors(event) {
    event.preventDefault();

    const idsText = document.getElementById('compareLeadIds').value;
    const leadIds = idsText.split(',').map(id => parseInt(id.trim())).filter(id => !isNaN(id));

    if (leadIds.length < 2) {
        showNotification('Please enter at least 2 lead IDs', 'warning');
        return false;
    }

    try {
        showLoading(true);
        const response = await fetch(`${API_URL}/compare`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ lead_ids: leadIds })
        });

        const result = await response.json();

        if (!response.ok) throw new Error(result.detail || 'Comparison failed');

        // Display results
        const resultsDiv = document.getElementById('comparisonResults');
        let html = '<h4 style="margin-bottom: 1rem;">Comparison Results</h4>';

        if (result.winner_summary) {
            html += '<div class="stats-grid">';
            for (const [category, winner] of Object.entries(result.winner_summary)) {
                html += `
                    <div class="stat-card">
                        <h3>${category.replace(/_/g, ' ').toUpperCase()}</h3>
                        <div class="value" style="font-size: 1rem;">${winner}</div>
                    </div>
                `;
            }
            html += '</div>';
        }

        if (result.insights && result.insights.length > 0) {
            html += '<h4 style="margin: 1.5rem 0 1rem;">Insights</h4><ul>';
            result.insights.forEach(insight => {
                html += `<li style="margin-bottom: 0.5rem;">${insight}</li>`;
            });
            html += '</ul>';
        }

        resultsDiv.innerHTML = html;
        resultsDiv.style.display = 'block';
        showNotification(`Compared ${result.businesses_compared} businesses`, 'success');

    } catch (error) {
        console.error('Comparison error:', error);
        showNotification('Comparison failed: ' + error.message, 'error');
    } finally {
        showLoading(false);
    }

    return false;
}

// Email Template Generator
let lastGeneratedEmail = { subject: '', body: '' };

async function generateEmailTemplate(event) {
    event.preventDefault();

    const data = {
        lead_id: parseInt(document.getElementById('emailLeadId').value),
        template_type: document.getElementById('emailTemplateType').value,
        sender_name: document.getElementById('emailSenderName').value.trim(),
        sender_company: document.getElementById('emailSenderCompany').value.trim(),
        sender_title: document.getElementById('emailSenderTitle').value.trim() || null,
        custom_value_proposition: document.getElementById('emailValueProp').value.trim() || null
    };

    try {
        showLoading(true);
        const response = await fetch(`${API_URL}/email-template`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });

        const result = await response.json();

        if (!response.ok) throw new Error(result.detail || 'Generation failed');

        // Store for copy
        lastGeneratedEmail = { subject: result.subject, body: result.body };

        // Display result
        const resultDiv = document.getElementById('emailTemplateResult');
        const previewDiv = document.getElementById('emailPreview');

        previewDiv.innerHTML = `
            <div style="margin-bottom: 1rem;">
                <strong>Subject:</strong><br>
                <span style="color: var(--primary);">${result.subject}</span>
            </div>
            <div>
                <strong>Body:</strong><br>
                <pre style="white-space: pre-wrap; font-family: inherit; margin-top: 0.5rem;">${result.body}</pre>
            </div>
            <div style="margin-top: 1rem; padding-top: 1rem; border-top: 1px solid var(--border);">
                <span class="badge badge-info">Personalization Score: ${(result.personalization_score * 100).toFixed(0)}%</span>
            </div>
        `;

        resultDiv.style.display = 'block';
        showNotification('Email template generated!', 'success');

    } catch (error) {
        console.error('Email generation error:', error);
        showNotification('Generation failed: ' + error.message, 'error');
    } finally {
        showLoading(false);
    }

    return false;
}

function copyEmail() {
    const text = `Subject: ${lastGeneratedEmail.subject}\n\n${lastGeneratedEmail.body}`;
    navigator.clipboard.writeText(text).then(() => {
        showNotification('Email copied to clipboard!', 'success');
    }).catch(() => {
        showNotification('Failed to copy', 'error');
    });
}

// Integrations Status
async function loadIntegrations() {
    try {
        const response = await fetch(`${API_URL}/integrations/status`);
        const data = await response.json();

        // Display integrations
        const integrationsGrid = document.getElementById('integrationsGrid');
        if (integrationsGrid && data.integrations) {
            integrationsGrid.innerHTML = Object.entries(data.integrations).map(([name, status]) => {
                const isConfigured = status.configured || status.enabled;
                return `
                    <div class="stat-card ${isConfigured ? 'success' : ''}">
                        <h3>${name.replace(/_/g, ' ').toUpperCase()}</h3>
                        <div class="value" style="font-size: 1rem;">${isConfigured ? 'Configured' : 'Not Configured'}</div>
                        ${status.enabled !== undefined ? `<div class="sub-text">${status.enabled ? 'Enabled' : 'Disabled'}</div>` : ''}
                    </div>
                `;
            }).join('');
        }

        // Display features
        const featuresGrid = document.getElementById('featuresGrid');
        if (featuresGrid && data.new_features) {
            featuresGrid.innerHTML = Object.entries(data.new_features).map(([name, feature]) => {
                const isEnabled = feature.enabled || feature.configured;
                return `
                    <div class="stat-card ${isEnabled ? 'success' : 'warning'}">
                        <h3>${name.replace(/_/g, ' ').toUpperCase()}</h3>
                        <div class="value" style="font-size: 1rem;">${isEnabled ? 'Active' : 'Inactive'}</div>
                        <div class="sub-text">${feature.description || ''}</div>
                    </div>
                `;
            }).join('');
        }

    } catch (error) {
        console.error('Failed to load integrations:', error);
    }
}

// Update page navigation for new pages
const originalShowPage = showPage;
showPage = function(pageName, evt) {
    // Add new page titles
    const newTitles = {
        'geo-search': 'Geo Search',
        'webhooks': 'Webhooks',
        'sentiment': 'Sentiment Analysis',
        'compare': 'Competitor Comparison',
        'emails': 'Email Templates',
        'integrations': 'Integrations'
    };

    originalShowPage(pageName, evt);

    if (newTitles[pageName]) {
        document.getElementById('pageTitle').textContent = newTitles[pageName];
    }

    // Load page-specific data
    if (pageName === 'webhooks') loadWebhooks();
    if (pageName === 'integrations') loadIntegrations();
};
