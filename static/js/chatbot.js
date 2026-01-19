/**
 * Rule-Based Chatbot Logic
 * This file is separate to keep the dashboard.js file clean.
 * It's imported by dashboard.html and called by App.Chatbot.getResponse()
 */

// We attach this to the window to make it globally accessible to App.js
window.getChatbotResponse = function(input) {
    const i = input.toLowerCase().trim();

    // 1. Greetings
    if (i.includes("hello") || i.includes("hi") || i.includes("hey")) {
        return "Hi there! I'm your travel assistant. How can I help you? You can ask for 'safety tips', 'emergency contacts', or 'where am I'.";
    }

    // 2. Emergency
    if (i.includes("emergency") || i.includes("danger") || i.includes("stuck") || i.includes("help me")) {
        return "I'm sorry to hear that. Please stay calm. Here are the national emergency numbers for India:<br><ul><li><b>Police:</b> 100 or 112</li><li><b>Ambulance:</b> 108</li><li><b>Fire:</b> 101</li></ul>";
    }

    // 3. Location
    if (i.includes("where am i") || i.includes("my location") || i.includes("find me")) {
        if (navigator.geolocation) {
            navigator.geolocation.getCurrentPosition(pos => {
                const lat = pos.coords.latitude;
                const lon = pos.coords.longitude;
                const mapLink = `https://www.openstreetmap.org/?mlat=${lat}&mlon=${lon}#map=16/${lat}/${lon}`;
                
                // This is a hack to add a response from an async call
                // We find the chat window and add the message directly.
                const chatWindow = document.getElementById('chatWindow');
                if (chatWindow) {
                    const msgDiv = document.createElement('div');
                    msgDiv.className = `chat-message bot`;
                    msgDiv.innerHTML = `<p>I've found your location! <br><a href="${mapLink}" target="_blank" style="color: #00c6ff;">Click here to see it on a map.</a></p>`;
                    chatWindow.appendChild(msgDiv);
                    chatWindow.scrollTop = chatWindow.scrollHeight;
                }

            }, () => {
                // Handle error
                const chatWindow = document.getElementById('chatWindow');
                 if (chatWindow) {
                    const msgDiv = document.createElement('div');
                    msgDiv.className = `chat-message bot`;
                    msgDiv.innerHTML = `<p>Sorry, I couldn't get your location. Please make sure you've enabled location permissions for this site.</p>`;
                    chatWindow.appendChild(msgDiv);
                    chatWindow.scrollTop = chatWindow.scrollHeight;
                }
            });
            return "Getting your current location... please wait.";
        } else {
            return "Sorry, your browser doesn't support Geolocation.";
        }
    }
    
    // 4. Safety Tips
    if (i.includes("safety") || i.includes("tips")) {
        return "Here are some quick safety tips:<br><ul><li>Keep copies of your important documents.</li><li>Share your itinerary with family.</li><li>Avoid walking alone in unfamiliar areas at night.</li><li>Use a money belt for cash and passport.</li></ul>";
    }

    // 5. Help / Capabilities
    if (i.includes("help") || i.includes("what can you do")) {
        return "I can help you with: <br><ul><li><b>'safety tips'</b></li><li><b>'emergency contacts'</b></li><li><b>'where am i'</b> to find your location</li><li><b>'find nearby atm/fuel'</b></li></ul>";
    }
    
    // 6. Nearby (Enhanced)
    if (i.includes("find nearby") || i.includes("where is the nearest")) {
         // This is a "command" - it tells the main app to do something
         if (i.includes("atm") || i.includes("fuel") || i.includes("petrol") || i.includes("restaurant") || i.includes("food") || i.includes("famous place")) {
            // We return a special code 'CMD::NEARBY'
            return 'CMD::NEARBY';
         }
         return "I can find nearby attractions, fuel, and ATMs. Please click the 'Nearby Attractions' card on the dashboard or ask me to 'find nearby fuel'.";
    }

    // 7. Thank you / Bye
    if (i.includes("thanks") || i.includes("thank you") || i.includes("bye")) {
        return "You're welcome! Safe travels!";
    }

    // Default Fallback
    return "I'm sorry, I don't understand that. You can ask me for 'help', 'safety tips', 'emergency contacts', or 'where am I'.";
}