/**
 * Rule-Based Chatbot Logic
 * This file is separate to keep the dashboard.js file clean.
 * It's imported by dashboard.html and called by App.Chatbot.getResponse()
 */

window.getChatbotResponse = function(input) {
    const i = input.toLowerCase().trim();

    // 1. Greetings
    if (i.includes("hello") || i.includes("hi") || i.includes("hey") || i.includes("morning") || i.includes("evening")) {
        return "Hi there! I'm your Smart Travel Assistant. 👋 I can help you find nearby places, give safety tips, check weather advice, or manage your budget. What do you need?";
    }

    // 2. Emergency
    if (i.includes("emergency") || i.includes("danger") || i.includes("stuck") || i.includes("help me") || i.includes("police") || i.includes("hospital")) {
        return "⚠️ I'm sorry to hear that. Please stay calm. Here are the national emergency numbers for India:<br><ul><li><b>Police:</b> 100 or 112</li><li><b>Ambulance:</b> 108</li><li><b>Fire:</b> 101</li></ul> If you are outside India, please dial 911 or your local equivalent immediately.";
    }

    // 3. Location
    if (i.includes("where am i") || i.includes("my location") || i.includes("find me") || i.includes("lost")) {
        if (navigator.geolocation) {
            navigator.geolocation.getCurrentPosition(pos => {
                const lat = pos.coords.latitude;
                const lon = pos.coords.longitude;
                const mapLink = `https://www.openstreetmap.org/?mlat=${lat}&mlon=${lon}#map=16/${lat}/${lon}`;
                
                const chatWindow = document.getElementById('chatWindow');
                if (chatWindow) {
                    const msgDiv = document.createElement('div');
                    msgDiv.className = `chat-message bot`;
                    msgDiv.innerHTML = `<p>📍 I've found your exact coordinates! <br><a href="${mapLink}" target="_blank" style="color: #00c6ff;">Click here to reveal your location on the map.</a></p>`;
                    chatWindow.appendChild(msgDiv);
                    chatWindow.scrollTop = chatWindow.scrollHeight;
                }
            }, () => {
                const chatWindow = document.getElementById('chatWindow');
                 if (chatWindow) {
                    const msgDiv = document.createElement('div');
                    msgDiv.className = `chat-message bot`;
                    msgDiv.innerHTML = `<p>Sorry, I couldn't access your GPS. Please make sure you've enabled location permissions for this site.</p>`;
                    chatWindow.appendChild(msgDiv);
                    chatWindow.scrollTop = chatWindow.scrollHeight;
                }
            });
            return "Pinging your device's GPS chip... Please wait a second.";
        } else {
            return "Sorry, your browser doesn't support geolocation tracking.";
        }
    }
    
    // 4. Safety Tips
    if (i.includes("safety") || i.includes("tips") || i.includes("secure") || i.includes("scam")) {
        return "Here are my top travel safety rules:<br><ul><li>Keep digital copies of your passport/ID on your phone.</li><li>Avoid walking alone in unlit alleys at night.</li><li>Never leave drinks unattended.</li><li>Use your hotel safe for valuables.</li><li>Use a VPN on public airport/cafe Wi-Fi.</li></ul>";
    }

    // 5. Help / Capabilities
    if (i.includes("help") || i.includes("what can you do") || i.includes("features") || i.includes("menu")) {
        return "I am wired into your dashboard! I can: <br><ul><li>Find you <b>'nearby ATMs/food'</b></li><li>Give you <b>'safety tips'</b></li><li>Provide emergency <b>'contacts'</b></li><li>Find out <b>'where am I'</b></li><li>Offer <b>'weather advice'</b></li></ul> Try typing one of those!";
    }
    
    // 6. Nearby (Enhanced) - Includes facility routing for hospitals/fuel
    if (i.includes("find nearby") || i.includes("where is the nearest") || i.includes("atm") || i.includes("fuel") || i.includes("petrol") || i.includes("restaurant") || i.includes("food") || i.includes("famous place") || i.includes("attraction") || i.includes("facilities") || i.includes("facility")) {
        if (i.includes("atm") || i.includes("fuel") || i.includes("petrol") || i.includes("restaurant") || i.includes("food") || i.includes("hospital") || i.includes("facilities") || i.includes("facility")) {
            return 'CMD::NEARBY_AMENITIES';
        }
        return 'CMD::NEARBY_ATTRACTIONS';
    }

    // 7. Weather Info
    if (i.includes("weather") || i.includes("rain") || i.includes("hot") || i.includes("umbrella")) {
        return "☀️ While I don't have a live radar display, I recommend packing layers! If you are traveling in monsoon or winter, always keep a small folding umbrella or light jacket in your daypack. Always check the local forecast before heading out for a trek!";
    }
    
    // 8. Flight / Booking Info
    if (i.includes("flight") || i.includes("hotel") || i.includes("book") || i.includes("ticket")) {
        return "✈️ I don't handle direct bookings just yet, but I recommend checking out Skyscanner or Google Flights for tickets, and Booking.com or Agoda for stays. Stick to our Budget Planner when booking to make sure you stay within your limits!";
    }

    // 9. Budget Planner triggers
    if (i.includes("budget") || i.includes("expense") || i.includes("money") || i.includes("spend")) {
        return "💰 You can manage your money by clicking the 'Budget Tracker' card on the dashboard. I will automatically calculate your spending based on your daily travel style (Luxury, Mid-Range, or Backpacker).";
    }

    // 10. Thank you / Bye
    if (i.includes("thanks") || i.includes("thank you") || i.includes("awesome") || i.includes("cool")) {
        return "You're very welcome! I'm always here to help. Have a fantastic trip! 🌍";
    }
    if (i.includes("bye") || i.includes("goodbye")) {
        return "Safe travels! See you later! ✈️";
    }

    // Default Fallback
    return "I'm sorry, I process travel-related commands. Try asking me for 'safety tips', 'emergency help', 'find ATMs', or 'where am I'.";
}