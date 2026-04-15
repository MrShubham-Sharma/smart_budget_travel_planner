/**
 * TripWise AI Chatbot v3.0
 * - Real-time fetch to /api/chat backend NLP engine
 * - 50+ intent patterns (handled server-side)
 * - Wikipedia live lookup fallback
 * - Contextual memory within session
 * - GPS location + Nearby facility commands via CMD:: protocol
 * - Proper typing indicator, error handling, input sanitization
 */

window.getChatbotResponse = null; // Deprecated — now handled server-side via fetch

// ─── Chatbot State (session memory) ───
const ChatbotState = {
    history: [],      // Stores last 5 exchanges for context
    isTyping: false,  // Prevent double-sends
    retryCount: 0     // Track consecutive API failures
};

/**
 * Main entry point called from dashboard.js App.Chatbot.send()
 * Accepts raw user input, manages the full send/receive/render cycle.
 */
window.handleChatbotMessage = async function(rawInput) {
    const input = (rawInput || '').trim();
    if (!input || ChatbotState.isTyping) return;
    if (input.length > 500) {
        appendChatMessage('bot', '⚠️ Message too long. Please keep it under 500 characters.');
        return;
    }

    // Add to history
    ChatbotState.history.push({ role: 'user', text: input });
    if (ChatbotState.history.length > 10) ChatbotState.history.shift();

    // Show typing indicator
    ChatbotState.isTyping = true;
    showTypingIndicator();

    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: input, history: ChatbotState.history.slice(-4) }),
            signal: AbortSignal.timeout(8000) // 8s timeout
        });

        hideTypingIndicator();

        if (!response.ok) {
            throw new Error(`Server responded with ${response.status}`);
        }

        const data = await response.json();
        const reply = data.reply || "I'm having trouble responding. Please try again!";
        ChatbotState.retryCount = 0;

        // Handle special CMD:: commands
        if (reply.startsWith('CMD::')) {
            processChatCommand(reply);
        } else {
            appendChatMessage('bot', reply);
            ChatbotState.history.push({ role: 'bot', text: reply });
        }

    } catch (err) {
        hideTypingIndicator();
        ChatbotState.retryCount++;

        if (err.name === 'TimeoutError' || err.name === 'AbortError') {
            appendChatMessage('bot',
                '⏱️ The server is taking too long. Please check your connection and try again.');
        } else if (ChatbotState.retryCount >= 3) {
            // Fallback to local responses after 3 consecutive failures
            const localReply = getLocalFallback(input);
            appendChatMessage('bot', localReply + '<br><br><i>(Offline mode — server unreachable)</i>');
        } else {
            appendChatMessage('bot',
                '⚠️ Connection error. Please ensure the app server is running and try again.');
        }
    } finally {
        ChatbotState.isTyping = false;
    }
};

/**
 * Process special CMD:: directives returned by the server.
 * Opens real Google Maps searches and live map links.
 */
function processChatCommand(cmd) {

    // ─── FIND NEARBY: Opens live Google Maps search ───
    if (cmd.startsWith('CMD::FIND_NEARBY::')) {
        const facility = cmd.replace('CMD::FIND_NEARBY::', '');

        // Try to get user's GPS first for a more accurate map link
        if (navigator.geolocation) {
            appendChatMessage('bot', `🔍 Getting your location to find the nearest <b>${facility}</b>...`);
            navigator.geolocation.getCurrentPosition(
                (pos) => {
                    const lat = pos.coords.latitude;
                    const lon = pos.coords.longitude;
                    // Google Maps search: nearest facility near coordinates
                    const gmapsUrl = `https://www.google.com/maps/search/${encodeURIComponent(facility)}/@${lat},${lon},15z`;
                    const osmUrl = `https://www.openstreetmap.org/search?query=${encodeURIComponent(facility)}&lat=${lat}&lon=${lon}`;
                    appendChatMessage('bot',
                        `📍 Found your location! Here's the nearest <b>${facility}</b>:<br><br>` +
                        `<a href="${gmapsUrl}" target="_blank" rel="noopener" style="color:#38bdf8; font-weight:600;">` +
                        `🗺️ Open on Google Maps</a><br>` +
                        `<a href="${osmUrl}" target="_blank" rel="noopener" style="color:#a78bfa; font-size:0.9rem;">` +
                        `🌐 Or open on OpenStreetMap</a>`
                    );
                },
                () => {
                    // GPS denied — give a generic map search anyway
                    const gmapsUrl = `https://www.google.com/maps/search/${encodeURIComponent(facility + ' near me')}`;
                    appendChatMessage('bot',
                        `🔍 Search for <b>${facility}</b> on Google Maps:<br><br>` +
                        `<a href="${gmapsUrl}" target="_blank" rel="noopener" style="color:#38bdf8; font-weight:600;">` +
                        `🗺️ Find ${facility} near me</a><br><br>` +
                        `<i>(Enable location for a more precise result)</i>`
                    );
                },
                { timeout: 6000 }
            );
        } else {
            const gmapsUrl = `https://www.google.com/maps/search/${encodeURIComponent(facility + ' near me')}`;
            appendChatMessage('bot',
                `<a href="${gmapsUrl}" target="_blank" rel="noopener" style="color:#38bdf8;">` +
                `🗺️ Search for ${facility} on Google Maps</a>`);
        }
        return;
    }

    // ─── LOCATE ME: Shows exact GPS coordinates + map link ───
    if (cmd === 'CMD::LOCATE_ME') {
        appendChatMessage('bot', '📡 Checking your GPS... please allow location access.');
        if (!navigator.geolocation) {
            appendChatMessage('bot', '❌ Your browser does not support geolocation.');
            return;
        }
        navigator.geolocation.getCurrentPosition(
            (pos) => {
                const lat = pos.coords.latitude.toFixed(6);
                const lon = pos.coords.longitude.toFixed(6);
                const acc = Math.round(pos.coords.accuracy);
                const gmapsUrl = `https://www.google.com/maps?q=${lat},${lon}`;
                const osmUrl = `https://www.openstreetmap.org/?mlat=${lat}&mlon=${lon}#map=16/${lat}/${lon}`;
                appendChatMessage('bot',
                    `📍 <b>Your Location Found!</b><br>` +
                    `<code>${lat}, ${lon}</code><br>` +
                    `<small>Accuracy: ±${acc}m</small><br><br>` +
                    `<a href="${gmapsUrl}" target="_blank" rel="noopener" style="color:#38bdf8; font-weight:600;">🗺️ View on Google Maps</a><br>` +
                    `<a href="${osmUrl}" target="_blank" rel="noopener" style="color:#a78bfa; font-size:0.9rem;">🌐 View on OpenStreetMap</a>`
                );
            },
            (err) => {
                const msgs = {
                    1: 'Location permission denied. Enable it in your browser settings.',
                    2: 'GPS signal unavailable. Move to an open area.',
                    3: 'Location request timed out. Try again.'
                };
                appendChatMessage('bot', `❌ ${msgs[err.code] || 'GPS error.'}`);
            },
            { timeout: 10000, maximumAge: 60000, enableHighAccuracy: true }
        );
        return;
    }

    // ─── NEARBY ATTRACTIONS: Opens Google Maps tourist searches ───
    if (cmd === 'CMD::NEARBY_ATTRACTIONS') {
        if (navigator.geolocation) {
            appendChatMessage('bot', '🗺️ Finding tourist attractions near you...');
            navigator.geolocation.getCurrentPosition(
                (pos) => {
                    const lat = pos.coords.latitude;
                    const lon = pos.coords.longitude;
                    const gmapsUrl = `https://www.google.com/maps/search/tourist+attractions/@${lat},${lon},14z`;
                    appendChatMessage('bot',
                        `🏛️ <b>Tourist Attractions Near You:</b><br><br>` +
                        `<a href="${gmapsUrl}" target="_blank" rel="noopener" style="color:#38bdf8; font-weight:600;">🗺️ Open on Google Maps</a><br><br>` +
                        `Or use the <b>Nearby Attractions</b> card on your dashboard for a detailed list with descriptions!`
                    );
                },
                () => {
                    const gmapsUrl = `https://www.google.com/maps/search/tourist+attractions+near+me`;
                    appendChatMessage('bot',
                        `<a href="${gmapsUrl}" target="_blank" rel="noopener" style="color:#38bdf8;">🗺️ Find tourist attractions near me</a>`);
                },
                { timeout: 6000 }
            );
        } else {
            appendChatMessage('bot',
                `<a href="https://www.google.com/maps/search/tourist+attractions+near+me" target="_blank" style="color:#38bdf8;">🗺️ Find tourist attractions on Google Maps</a>`);
        }
        return;
    }

    // Unrecognised command fallback
    appendChatMessage('bot', 'Processing your request...');
}

/**
 * Offline fallback for when the server is completely unreachable.
 * Basic keyword matching for critical use cases.
 */
function getLocalFallback(input) {
    const m = input.toLowerCase();
    if (m.includes('emergency') || m.includes('help me') || m.includes('sos')) {
        return '⚠️ <b>Emergency Numbers (India):</b><br>Police: 100/112 | Ambulance: 108 | Fire: 101';
    }
    if (m.includes('budget') || m.includes('cost')) {
        return '💰 Budget tips: ₹800-1500/day (budget) | ₹2000-5000/day (mid) | ₹8000+/day (luxury)';
    }
    if (m.includes('safe') || m.includes('safety')) {
        return '🛡️ Keep copies of IDs, use only official transport, avoid unlit areas at night.';
    }
    return 'I am your travel assistant for India trips. For emergencies call 112 (universal) or Police: 100, Ambulance: 108. Ask me about safety, budget, transport or Indian destinations!';
}

/**
 * Appends a message bubble to the chat window.
 * Supports HTML content for rich responses.
 */
function appendChatMessage(sender, htmlContent) {
    const chatWindow = document.getElementById('chatWindow');
    if (!chatWindow) return;

    const msgDiv = document.createElement('div');
    msgDiv.className = `chat-message ${sender} anim-slide-up`;
    msgDiv.innerHTML = `<p>${htmlContent}</p>`;

    // Animate in with a premium spring feel
    msgDiv.style.opacity = '0';
    msgDiv.style.transform = 'translateY(16px) scale(0.96)';
    chatWindow.appendChild(msgDiv);

    // Force reflow
    msgDiv.offsetHeight;

    requestAnimationFrame(() => {
        msgDiv.style.transition = 'opacity 0.4s ease, transform 0.5s cubic-bezier(0.175, 0.885, 0.32, 1.275)';
        msgDiv.style.opacity = '1';
        msgDiv.style.transform = 'translateY(0) scale(1)';
    });

    chatWindow.scrollTop = chatWindow.scrollHeight;
}

/**
 * Shows the animated typing indicator bubble.
 */
function showTypingIndicator() {
    const indicator = document.getElementById('bot-typing-indicator');
    if (indicator) indicator.style.display = 'flex';
    const chatWindow = document.getElementById('chatWindow');
    if (chatWindow) chatWindow.scrollTop = chatWindow.scrollHeight;
}

/**
 * Hides the typing indicator bubble.
 */
function hideTypingIndicator() {
    const indicator = document.getElementById('bot-typing-indicator');
    if (indicator) indicator.style.display = 'none';
}

/**
 * Clears the chat history (both UI and memory).
 */
window.clearChatHistory = function() {
    ChatbotState.history = [];
    const chatWindow = document.getElementById('chatWindow');
    if (!chatWindow) return;
    // Keep only the first welcome message
    const messages = chatWindow.querySelectorAll('.chat-message');
    messages.forEach((msg, i) => { if (i > 0) msg.remove(); });
};