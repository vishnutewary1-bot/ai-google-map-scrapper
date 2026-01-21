/**
 * MapLeads Pro - Chrome Extension Content Script
 * Extracts business data from Google Maps pages
 */

// Selectors for Google Maps elements
const SELECTORS = {
    businessName: 'h1.DUwDvf, h1[data-attrid="title"]',
    rating: 'span.ceNzKf, div.F7nice span[aria-hidden="true"]',
    reviewCount: 'span.UY7F9, span[aria-label*="review"]',
    category: 'button.DkEaL, span.DkEaL',
    address: 'button[data-item-id="address"], div[data-item-id="address"]',
    phone: 'button[data-item-id*="phone"], a[data-item-id*="phone"]',
    website: 'a[data-item-id="authority"]',
    hours: 'div[data-hide-tooltip-on-mouse-move="true"]',
    priceLevel: 'span.mgr77e span',
    listingItem: 'div.Nv2PK, a.hfpxzc',
    listingPanel: 'div[role="main"]',
    photos: 'button.aoRNLd img, div.RWPxGd img',
    reviewsContainer: 'div.jftiEf',
    reviewText: 'span.wiI7pd',
    reviewerName: 'div.d4r55',
    reviewRating: 'span.kvMYJc',
    popularTimes: 'div.C7xf8b'
};

// Listen for messages from popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === 'getListingsCount') {
        const listings = document.querySelectorAll(SELECTORS.listingItem);
        sendResponse({ count: listings.length });
    }
    else if (request.action === 'extractCurrent') {
        extractCurrentBusiness(request.options).then(sendResponse);
        return true; // Keep channel open for async
    }
    else if (request.action === 'extractAll') {
        extractAllListings(request.options).then(sendResponse);
        return true;
    }
});

// Extract current business details
async function extractCurrentBusiness(options) {
    try {
        const data = {
            business_name: getTextContent(SELECTORS.businessName),
            rating: parseFloat(getTextContent(SELECTORS.rating)) || null,
            review_count: parseReviewCount(getTextContent(SELECTORS.reviewCount)),
            category: getTextContent(SELECTORS.category),
            maps_url: window.location.href,
            scraped_at: new Date().toISOString()
        };

        // Extract place_id from URL
        const placeIdMatch = window.location.href.match(/place\/([^\/]+)/);
        if (placeIdMatch) {
            data.place_id = placeIdMatch[1];
        }

        // Phone
        const phoneEl = document.querySelector(SELECTORS.phone);
        if (phoneEl) {
            const phoneText = phoneEl.textContent || phoneEl.getAttribute('aria-label') || '';
            data.phone = cleanPhone(phoneText);
        }

        // Website
        const websiteEl = document.querySelector(SELECTORS.website);
        if (websiteEl) {
            data.website = websiteEl.href || websiteEl.getAttribute('data-value');
        }

        // Address
        const addressEl = document.querySelector(SELECTORS.address);
        if (addressEl) {
            const fullAddress = addressEl.textContent || addressEl.getAttribute('aria-label') || '';
            data.full_address = fullAddress;
            const parsed = parseAddress(fullAddress);
            data.address = parsed.street;
            data.city = parsed.city;
            data.state = parsed.state;
            data.pin_code = parsed.pincode;
            data.country = parsed.country;
        }

        // Coordinates from URL
        const coordMatch = window.location.href.match(/@(-?\d+\.\d+),(-?\d+\.\d+)/);
        if (coordMatch) {
            data.latitude = parseFloat(coordMatch[1]);
            data.longitude = parseFloat(coordMatch[2]);
        }

        // Price level
        const priceEl = document.querySelector(SELECTORS.priceLevel);
        if (priceEl) {
            data.price_level = priceEl.textContent;
        }

        // Photos
        if (options.photos) {
            data.photos = extractPhotos();
        }

        // Reviews
        if (options.reviews) {
            data.reviews = extractReviews();
        }

        // Popular times
        if (options.times) {
            data.popular_times = extractPopularTimes();
        }

        // Social media from page (if visible)
        if (options.social) {
            data.social_facebook = findSocialLink('facebook');
            data.social_instagram = findSocialLink('instagram');
            data.social_linkedin = findSocialLink('linkedin');
            data.social_twitter = findSocialLink('twitter');
        }

        return { success: true, lead: data };

    } catch (error) {
        console.error('Extraction error:', error);
        return { success: false, error: error.message };
    }
}

// Extract all visible listings
async function extractAllListings(options) {
    try {
        const listings = document.querySelectorAll(SELECTORS.listingItem);
        const leads = [];
        const total = listings.length;

        for (let i = 0; i < listings.length; i++) {
            // Report progress
            chrome.runtime.sendMessage({
                action: 'extractionProgress',
                current: i + 1,
                total: total
            });

            const listing = listings[i];

            try {
                // Click on listing
                listing.click();
                await sleep(1500); // Wait for panel to load

                // Extract data
                const result = await extractCurrentBusiness(options);

                if (result.success && result.lead.business_name) {
                    leads.push(result.lead);
                }

                // Small delay between extractions
                await sleep(500);

            } catch (err) {
                console.warn('Failed to extract listing:', err);
            }
        }

        return { success: true, leads: leads };

    } catch (error) {
        console.error('Bulk extraction error:', error);
        return { success: false, error: error.message };
    }
}

// Helper: Get text content
function getTextContent(selector) {
    const el = document.querySelector(selector);
    return el ? el.textContent.trim() : null;
}

// Helper: Parse review count
function parseReviewCount(text) {
    if (!text) return null;
    const match = text.match(/[\d,]+/);
    return match ? parseInt(match[0].replace(/,/g, ''), 10) : null;
}

// Helper: Clean phone number
function cleanPhone(phone) {
    if (!phone) return null;
    // Remove non-digit chars except + at start
    return phone.replace(/[^\d+]/g, '').replace(/^\+/, '+') || null;
}

// Helper: Parse address
function parseAddress(fullAddress) {
    const result = {
        street: null,
        city: null,
        state: null,
        pincode: null,
        country: null
    };

    if (!fullAddress) return result;

    // Split by comma
    const parts = fullAddress.split(',').map(p => p.trim());

    if (parts.length >= 1) result.street = parts[0];
    if (parts.length >= 2) result.city = parts[1];
    if (parts.length >= 3) {
        // Try to extract state and pincode
        const statePin = parts[2];
        const pincodeMatch = statePin.match(/\d{5,6}/);
        if (pincodeMatch) {
            result.pincode = pincodeMatch[0];
            result.state = statePin.replace(pincodeMatch[0], '').trim();
        } else {
            result.state = statePin;
        }
    }
    if (parts.length >= 4) result.country = parts[parts.length - 1];

    return result;
}

// Helper: Extract photos
function extractPhotos() {
    const photos = [];
    const imgs = document.querySelectorAll(SELECTORS.photos);

    imgs.forEach(img => {
        let src = img.src;
        // Get higher resolution version
        if (src && src.includes('googleusercontent.com')) {
            src = src.replace(/=w\d+-h\d+/, '=w800-h600');
        }
        if (src && !photos.includes(src)) {
            photos.push(src);
        }
    });

    return photos.slice(0, 10); // Max 10 photos
}

// Helper: Extract reviews
function extractReviews() {
    const reviews = [];
    const reviewElements = document.querySelectorAll(SELECTORS.reviewsContainer);

    reviewElements.forEach((reviewEl, index) => {
        if (index >= 5) return; // Max 5 reviews

        const review = {
            reviewer_name: null,
            rating: null,
            text: null,
            date: null
        };

        const nameEl = reviewEl.querySelector(SELECTORS.reviewerName);
        if (nameEl) review.reviewer_name = nameEl.textContent.trim();

        const ratingEl = reviewEl.querySelector(SELECTORS.reviewRating);
        if (ratingEl) {
            const ariaLabel = ratingEl.getAttribute('aria-label');
            if (ariaLabel) {
                const match = ariaLabel.match(/(\d)/);
                if (match) review.rating = parseInt(match[1], 10);
            }
        }

        const textEl = reviewEl.querySelector(SELECTORS.reviewText);
        if (textEl) review.text = textEl.textContent.trim();

        if (review.reviewer_name || review.text) {
            reviews.push(review);
        }
    });

    return reviews;
}

// Helper: Extract popular times
function extractPopularTimes() {
    const data = {};
    const daysOfWeek = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];

    const timesContainer = document.querySelector(SELECTORS.popularTimes);
    if (!timesContainer) return null;

    // Try to extract bar heights as percentages
    const bars = timesContainer.querySelectorAll('div[role="img"]');
    bars.forEach((bar, index) => {
        const ariaLabel = bar.getAttribute('aria-label');
        if (ariaLabel) {
            const match = ariaLabel.match(/(\d+)%.*?(\d+)\s*(AM|PM)/i);
            if (match) {
                const percent = parseInt(match[1], 10);
                const hour = parseInt(match[2], 10);
                const period = match[3].toUpperCase();

                // Determine day (simplified - assumes current day view)
                const today = daysOfWeek[new Date().getDay()];
                if (!data[today]) data[today] = {};

                // Convert to 24hr format
                let hour24 = hour;
                if (period === 'PM' && hour !== 12) hour24 += 12;
                if (period === 'AM' && hour === 12) hour24 = 0;

                data[today][hour24] = percent;
            }
        }
    });

    return Object.keys(data).length > 0 ? data : null;
}

// Helper: Find social media links
function findSocialLink(platform) {
    const patterns = {
        facebook: /facebook\.com\//i,
        instagram: /instagram\.com\//i,
        linkedin: /linkedin\.com\//i,
        twitter: /twitter\.com\/|x\.com\//i
    };

    const links = document.querySelectorAll('a[href]');
    for (const link of links) {
        if (patterns[platform] && patterns[platform].test(link.href)) {
            return link.href;
        }
    }
    return null;
}

// Helper: Sleep
function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

// Inject floating action button
function injectFAB() {
    if (document.getElementById('mapleads-fab')) return;

    const fab = document.createElement('div');
    fab.id = 'mapleads-fab';
    fab.innerHTML = `
        <button id="mapleads-extract-btn" title="Extract with MapLeads Pro">
            <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                <polyline points="7 10 12 15 17 10"/>
                <line x1="12" y1="15" x2="12" y2="3"/>
            </svg>
        </button>
    `;

    document.body.appendChild(fab);

    document.getElementById('mapleads-extract-btn').addEventListener('click', async () => {
        const result = await extractCurrentBusiness({ email: true, phone: true, social: true });
        if (result.success) {
            showToast(`Extracted: ${result.lead.business_name}`);
            // Store in local storage for popup
            chrome.storage.local.get(['pendingLeads'], (data) => {
                const leads = data.pendingLeads || [];
                leads.push(result.lead);
                chrome.storage.local.set({ pendingLeads: leads });
            });
        } else {
            showToast('Extraction failed', 'error');
        }
    });
}

// Show toast notification
function showToast(message, type = 'success') {
    const existing = document.getElementById('mapleads-toast');
    if (existing) existing.remove();

    const toast = document.createElement('div');
    toast.id = 'mapleads-toast';
    toast.className = type;
    toast.textContent = message;
    document.body.appendChild(toast);

    setTimeout(() => toast.remove(), 3000);
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', injectFAB);
} else {
    injectFAB();
}

// Re-inject FAB on navigation (SPA)
let lastUrl = location.href;
new MutationObserver(() => {
    if (location.href !== lastUrl) {
        lastUrl = location.href;
        setTimeout(injectFAB, 1000);
    }
}).observe(document.body, { subtree: true, childList: true });
