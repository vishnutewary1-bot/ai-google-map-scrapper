/**
 * MapLeads Pro - Chrome Extension Service Worker
 * Handles background tasks and communication
 */

// Configuration
const CONFIG = {
    serverUrl: 'http://localhost:9000',
    apiEndpoint: '/api'
};

// Listen for installation
chrome.runtime.onInstalled.addListener((details) => {
    console.log('MapLeads Pro installed:', details.reason);

    // Set default options
    chrome.storage.sync.get(['serverUrl', 'extractionOptions'], (result) => {
        if (!result.serverUrl) {
            chrome.storage.sync.set({ serverUrl: CONFIG.serverUrl });
        }
        if (!result.extractionOptions) {
            chrome.storage.sync.set({
                extractionOptions: {
                    email: true,
                    phone: true,
                    social: true,
                    reviews: false,
                    photos: false,
                    times: false
                }
            });
        }
    });

    // Show welcome notification
    if (details.reason === 'install') {
        chrome.notifications.create({
            type: 'basic',
            iconUrl: 'icons/icon128.png',
            title: 'MapLeads Pro Installed',
            message: 'Start extracting leads from Google Maps!'
        });
    }
});

// Listen for messages from content script or popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === 'sendToServer') {
        sendLeadsToServer(request.leads)
            .then(result => sendResponse(result))
            .catch(error => sendResponse({ success: false, error: error.message }));
        return true; // Keep channel open for async
    }

    if (request.action === 'checkConnection') {
        checkServerConnection()
            .then(result => sendResponse(result))
            .catch(error => sendResponse({ connected: false, error: error.message }));
        return true;
    }
});

// Send leads to server
async function sendLeadsToServer(leads) {
    const serverUrl = await getServerUrl();

    const response = await fetch(`${serverUrl}${CONFIG.apiEndpoint}/leads/bulk`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ leads: leads })
    });

    if (!response.ok) {
        throw new Error(`Server error: ${response.status}`);
    }

    const data = await response.json();
    return { success: true, data: data };
}

// Check server connection
async function checkServerConnection() {
    const serverUrl = await getServerUrl();

    try {
        const response = await fetch(`${serverUrl}${CONFIG.apiEndpoint}/health`);
        const data = await response.json();

        return {
            connected: data.status === 'healthy',
            version: data.version,
            database: data.database
        };
    } catch (error) {
        return { connected: false, error: error.message };
    }
}

// Get server URL from storage
async function getServerUrl() {
    return new Promise((resolve) => {
        chrome.storage.sync.get(['serverUrl'], (result) => {
            resolve(result.serverUrl || CONFIG.serverUrl);
        });
    });
}

// Context menu for quick extraction
chrome.runtime.onInstalled.addListener(() => {
    chrome.contextMenus.create({
        id: 'mapleads-extract',
        title: 'Extract with MapLeads Pro',
        contexts: ['page'],
        documentUrlPatterns: ['https://www.google.com/maps/*', 'https://maps.google.com/*']
    });
});

chrome.contextMenus.onClicked.addListener((info, tab) => {
    if (info.menuItemId === 'mapleads-extract') {
        chrome.tabs.sendMessage(tab.id, {
            action: 'extractCurrent',
            options: { email: true, phone: true, social: true }
        });
    }
});

// Handle keyboard shortcut
chrome.commands.onCommand.addListener((command) => {
    if (command === 'extract-current') {
        chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
            if (tabs[0] && tabs[0].url.includes('google.com/maps')) {
                chrome.tabs.sendMessage(tabs[0].id, {
                    action: 'extractCurrent',
                    options: { email: true, phone: true, social: true }
                });
            }
        });
    }
});
