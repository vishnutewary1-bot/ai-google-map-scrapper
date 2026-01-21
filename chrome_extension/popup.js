/**
 * MapLeads Pro - Chrome Extension Popup Script
 * Handles UI interactions and communication with content script
 */

// Configuration
const CONFIG = {
    serverUrl: 'http://localhost:9000',
    apiEndpoint: '/api'
};

// State
let extractedLeads = [];
let isConnected = false;

// DOM Elements
const elements = {
    serverStatus: document.getElementById('server-status'),
    connectionMessage: document.getElementById('connection-message'),
    extractCurrent: document.getElementById('extract-current'),
    extractAll: document.getElementById('extract-all'),
    resultsCard: document.getElementById('results-card'),
    progressContainer: document.getElementById('progress-container'),
    progressFill: document.getElementById('progress-fill'),
    totalCount: document.getElementById('total-count'),
    emailCount: document.getElementById('email-count'),
    phoneCount: document.getElementById('phone-count'),
    leadPreview: document.getElementById('lead-preview'),
    sendToServer: document.getElementById('send-to-server'),
    exportCsv: document.getElementById('export-csv'),
    mainContent: document.getElementById('main-content'),
    notOnMaps: document.getElementById('not-on-maps'),
    openMaps: document.getElementById('open-maps'),
    // Options
    optEmail: document.getElementById('opt-email'),
    optPhone: document.getElementById('opt-phone'),
    optSocial: document.getElementById('opt-social'),
    optReviews: document.getElementById('opt-reviews'),
    optPhotos: document.getElementById('opt-photos'),
    optTimes: document.getElementById('opt-times')
};

// Initialize
document.addEventListener('DOMContentLoaded', async () => {
    await checkServerConnection();
    await checkCurrentTab();
    loadOptions();
    setupEventListeners();
});

// Check server connection
async function checkServerConnection() {
    try {
        const response = await fetch(`${CONFIG.serverUrl}${CONFIG.apiEndpoint}/health`);
        const data = await response.json();

        if (data.status === 'healthy') {
            isConnected = true;
            elements.serverStatus.classList.remove('offline');
            elements.connectionMessage.className = 'message success';
            elements.connectionMessage.textContent = `Connected to MapLeads Pro v${data.version}`;
        } else {
            throw new Error('Server unhealthy');
        }
    } catch (error) {
        isConnected = false;
        elements.serverStatus.classList.add('offline');
        elements.connectionMessage.className = 'message error';
        elements.connectionMessage.textContent = 'Cannot connect to server. Make sure MapLeads Pro is running on localhost:9000';
    }
}

// Check if current tab is Google Maps
async function checkCurrentTab() {
    try {
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

        if (tab.url && (tab.url.includes('google.com/maps') || tab.url.includes('maps.google.com'))) {
            elements.mainContent.style.display = 'block';
            elements.notOnMaps.style.display = 'none';

            // Get count of visible listings
            chrome.tabs.sendMessage(tab.id, { action: 'getListingsCount' }, (response) => {
                if (response && response.count) {
                    elements.extractAll.textContent = `Extract All Visible (${response.count})`;
                }
            });
        } else {
            elements.mainContent.style.display = 'none';
            elements.notOnMaps.style.display = 'block';
        }
    } catch (error) {
        console.error('Error checking tab:', error);
    }
}

// Load saved options
function loadOptions() {
    chrome.storage.sync.get(['extractionOptions'], (result) => {
        if (result.extractionOptions) {
            elements.optEmail.checked = result.extractionOptions.email !== false;
            elements.optPhone.checked = result.extractionOptions.phone !== false;
            elements.optSocial.checked = result.extractionOptions.social !== false;
            elements.optReviews.checked = result.extractionOptions.reviews || false;
            elements.optPhotos.checked = result.extractionOptions.photos || false;
            elements.optTimes.checked = result.extractionOptions.times || false;
        }
    });
}

// Save options
function saveOptions() {
    const options = {
        email: elements.optEmail.checked,
        phone: elements.optPhone.checked,
        social: elements.optSocial.checked,
        reviews: elements.optReviews.checked,
        photos: elements.optPhotos.checked,
        times: elements.optTimes.checked
    };
    chrome.storage.sync.set({ extractionOptions: options });
    return options;
}

// Setup event listeners
function setupEventListeners() {
    elements.extractCurrent.addEventListener('click', extractCurrentBusiness);
    elements.extractAll.addEventListener('click', extractAllListings);
    elements.sendToServer.addEventListener('click', sendToServer);
    elements.exportCsv.addEventListener('click', exportToCsv);
    elements.openMaps.addEventListener('click', () => {
        chrome.tabs.create({ url: 'https://www.google.com/maps' });
    });

    // Save options on change
    [elements.optEmail, elements.optPhone, elements.optSocial,
     elements.optReviews, elements.optPhotos, elements.optTimes].forEach(el => {
        el.addEventListener('change', saveOptions);
    });
}

// Extract current business
async function extractCurrentBusiness() {
    const options = saveOptions();

    elements.extractCurrent.disabled = true;
    elements.extractCurrent.textContent = 'Extracting...';

    try {
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

        chrome.tabs.sendMessage(tab.id, {
            action: 'extractCurrent',
            options: options
        }, (response) => {
            elements.extractCurrent.disabled = false;
            elements.extractCurrent.textContent = 'Extract Current Business';

            if (response && response.success) {
                addLead(response.lead);
                showResults();
            } else {
                showMessage('error', response?.error || 'Failed to extract business data');
            }
        });
    } catch (error) {
        elements.extractCurrent.disabled = false;
        elements.extractCurrent.textContent = 'Extract Current Business';
        showMessage('error', 'Extraction failed: ' + error.message);
    }
}

// Extract all visible listings
async function extractAllListings() {
    const options = saveOptions();

    elements.extractAll.disabled = true;
    elements.progressContainer.style.display = 'block';

    try {
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

        chrome.tabs.sendMessage(tab.id, {
            action: 'extractAll',
            options: options
        }, (response) => {
            elements.extractAll.disabled = false;
            elements.progressContainer.style.display = 'none';

            if (response && response.success) {
                response.leads.forEach(lead => addLead(lead));
                showResults();
                showMessage('success', `Extracted ${response.leads.length} businesses`);
            } else {
                showMessage('error', response?.error || 'Failed to extract listings');
            }
        });
    } catch (error) {
        elements.extractAll.disabled = false;
        elements.progressContainer.style.display = 'none';
        showMessage('error', 'Extraction failed: ' + error.message);
    }
}

// Add lead to list
function addLead(lead) {
    // Check for duplicates
    if (!extractedLeads.find(l => l.place_id === lead.place_id)) {
        extractedLeads.push(lead);
        updateStats();
        renderLeadPreview();
    }
}

// Update statistics
function updateStats() {
    elements.totalCount.textContent = extractedLeads.length;
    elements.emailCount.textContent = extractedLeads.filter(l => l.email).length;
    elements.phoneCount.textContent = extractedLeads.filter(l => l.phone).length;
}

// Render lead preview
function renderLeadPreview() {
    elements.leadPreview.innerHTML = extractedLeads.slice(-5).reverse().map(lead => `
        <div class="lead-item">
            <div>
                <div class="lead-name">${escapeHtml(lead.business_name || 'Unknown')}</div>
                <div class="lead-info">${escapeHtml(lead.city || '')} ${lead.rating ? '⭐ ' + lead.rating : ''}</div>
            </div>
            <div class="lead-badges">
                ${lead.email ? '<span class="badge badge-email">Email</span>' : ''}
                ${lead.phone ? '<span class="badge badge-phone">Phone</span>' : ''}
                ${lead.social_facebook || lead.social_instagram ? '<span class="badge badge-social">Social</span>' : ''}
            </div>
        </div>
    `).join('');
}

// Show results card
function showResults() {
    elements.resultsCard.style.display = 'block';
}

// Show message
function showMessage(type, text) {
    const msg = document.createElement('div');
    msg.className = `message ${type}`;
    msg.textContent = text;
    elements.connectionMessage.parentNode.insertBefore(msg, elements.connectionMessage.nextSibling);
    setTimeout(() => msg.remove(), 3000);
}

// Send leads to server
async function sendToServer() {
    if (!isConnected) {
        showMessage('error', 'Not connected to server');
        return;
    }

    if (extractedLeads.length === 0) {
        showMessage('error', 'No leads to send');
        return;
    }

    elements.sendToServer.disabled = true;
    elements.sendToServer.textContent = 'Sending...';

    try {
        const response = await fetch(`${CONFIG.serverUrl}${CONFIG.apiEndpoint}/leads/bulk`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ leads: extractedLeads })
        });

        const data = await response.json();

        if (response.ok) {
            showMessage('success', `Sent ${extractedLeads.length} leads to server`);
            extractedLeads = [];
            updateStats();
            renderLeadPreview();
        } else {
            throw new Error(data.detail || 'Failed to send');
        }
    } catch (error) {
        showMessage('error', 'Failed to send: ' + error.message);
    } finally {
        elements.sendToServer.disabled = false;
        elements.sendToServer.textContent = 'Send to MapLeads Pro';
    }
}

// Export to CSV
function exportToCsv() {
    if (extractedLeads.length === 0) {
        showMessage('error', 'No leads to export');
        return;
    }

    // Define columns
    const columns = [
        'business_name', 'phone', 'email', 'website', 'address', 'city', 'state',
        'rating', 'review_count', 'category', 'social_facebook', 'social_instagram',
        'social_linkedin', 'maps_url'
    ];

    // Create CSV content
    const header = columns.join(',');
    const rows = extractedLeads.map(lead => {
        return columns.map(col => {
            const value = lead[col] || '';
            // Escape quotes and wrap in quotes
            return `"${String(value).replace(/"/g, '""')}"`;
        }).join(',');
    });

    const csv = [header, ...rows].join('\n');

    // Download
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `mapleads_export_${new Date().toISOString().slice(0,10)}.csv`;
    link.click();
    URL.revokeObjectURL(url);

    showMessage('success', 'CSV downloaded');
}

// Escape HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Listen for progress updates from content script
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.action === 'extractionProgress') {
        const percent = (message.current / message.total) * 100;
        elements.progressFill.style.width = `${percent}%`;
        elements.extractAll.textContent = `Extracting ${message.current}/${message.total}...`;
    }
});
