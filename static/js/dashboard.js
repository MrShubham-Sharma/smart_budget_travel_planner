/**
 * Enhanced Dashboard Script
 *
 * NOW INCLUDES:
 * - Live Route Tracker with ETA (FIXED: Stable, non-recalculating version)
 * - Nearby-on-Route attractions (FIXED: Finds famous places)
 * - Smart Budget Estimator (Solo/Group, Style)
 * - Upgraded Budget Tracker UI
 * - Chatbot integration
 * - NEW UI Animations
 * - Auto-select most recent trip for Live Tracker and Budget Tracker
 */

// ---------------------------------
// 1. APPLICATION NAMESPACE
// ---------------------------------
const App = {
  // 🔹 State
  State: {
    map: null,
    startMarker: null,
    destMarker: null,
    routeControl: null, // For Live ETA & Planner
    myTripsMap: null,
    myTripsMarkers: [],
    liveMarker: null,
    watchId: null,
    startTimeout: null,
    destTimeout: null,
    activeTripForTracking: null, // Stores data of the trip being tracked
    isTrackingInitialized: false, // Flag for live tracker
    allTrips: [], // Store all trips for quick access
  },

  // 🔹 Elements
  Elements: {},

  // ---------------------------------
  // 2. INITIALIZATION
  // ---------------------------------
  init: function () {
    this.cacheElements();
    this.attachGlobalHandlers();
    this.Map.initMainMap();
    App.Chatbot.init(); // Initialize the chatbot listeners
    this.loadTripsForAutoSelect(); // Load trips for auto-selection
  },

  cacheElements: function () {
    const ids = [
      'map', 'tripPlannerModal', 'myTripsModal', 'budgetTrackerModal',
      'budgetTrackerModalContent', 'trips', 'myTripsList', 'myTripsMap',
      'start_location', 'destination', 'start_suggestions', 'dest_suggestions',
      'start_lat', 'start_lon', 'latitude', 'longitude', 'trip_name', 'budget',
      'start_date', 'end_date', // New fields
      'group_size_wrapper', 'group_size', // Budget calculator
      'editTripContainer', 'edit_trip_id', 'edit_trip_name', 'edit_destination',
      'edit_budget', 'edit_latitude', 'edit_longitude',
      'route-summary', 'route-dist', 'route-eta', 'recalculate-route-btn', // ETA box & button
      'liveTrackSelectorModal', 'liveTrackTripsList', 'trip-planner-fields', // Live Tracker fixes
      'chatbotModal', 'chatWindow', 'chatInput', 'chatSendBtn', 'bot-typing-indicator', // Chatbot
      'chatbot-float-btn' // Floating button
    ];
    ids.forEach(id => {
      this.Elements[id] = document.getElementById(id);
    });
  },

  attachGlobalHandlers: function () {
    // Card clicks
    document.querySelectorAll('.card.option-card').forEach(card => {
      card.addEventListener('click', this.handleCardClick.bind(this));
    });
    
    // Nav link clicks
    document.querySelectorAll('.top-nav a[data-action]').forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            this.handleCardClick(e);
        });
    });

    // Modal closing (overlay clicks)
    window.addEventListener('click', (event) => {
      if (event.target === this.Elements.tripPlannerModal) this.Trip.closeTripPlanner();
      if (event.target === this.Elements.myTripsModal) this.Trip.closeMyTripsModal();
      if (event.target === this.Elements.budgetTrackerModal) this.Budget.closeBudgetTracker();
      if (event.target === this.Elements.chatbotModal) this.Chatbot.close();
    });

    // Suggestion input debouncing
    if (this.Elements.start_location) {
      this.Elements.start_location.addEventListener("input", () => {
        clearTimeout(this.State.startTimeout);
        this.State.startTimeout = setTimeout(() => this.Map.fetchSuggestions('start'), 300);
      });
    }
    if (this.Elements.destination) {
      this.Elements.destination.addEventListener("input", () => {
        clearTimeout(this.State.destTimeout);
        this.State.destTimeout = setTimeout(() => this.Map.fetchSuggestions('dest'), 300);
      });
    }
    
    // "My Trips" list event delegation
    if (this.Elements.myTripsList) {
        this.Elements.myTripsList.addEventListener('click', this.Trip.handleMyTripsClick.bind(this.Trip));
    }
    
    // Budget Calculator radio buttons
    document.querySelectorAll('input[name="traveler_type"]').forEach(radio => {
        radio.addEventListener('change', (e) => {
            if (this.Elements.group_size_wrapper) {
                this.Elements.group_size_wrapper.style.display = (e.target.value === 'group') ? 'block' : 'none';
            }
        });
    });
  },

  // NEW: Load trips for auto-selection
  loadTripsForAutoSelect: async function() {
    try {
      const response = await fetch("/get-trips");
      const data = await response.json();
      
      if (data.status === "success" && data.trips && data.trips.length > 0) {
        this.State.allTrips = data.trips;
        // Auto-select the most recent trip (last in list or by highest ID)
        const mostRecentTrip = data.trips[data.trips.length - 1];
        this.State.activeTripForTracking = mostRecentTrip;
        console.log("Auto-selected trip:", mostRecentTrip.trip_name);
      }
    } catch (err) {
      console.error("Failed to load trips for auto-select:", err);
    }
  },

  // ---------------------------------
  // 3. CARD ACTION HANDLER
  // ---------------------------------
  handleCardClick: function (e) {
    const target = e.currentTarget;
    
    if(target.classList.contains('card')) {
        target.classList.add('card-active');
        setTimeout(() => target.classList.remove('card-active'), 400);
    }

    const action = target.getAttribute('data-action') || this.getCardActionFromTitle(target);
    
    switch (action) {
      case 'plan': this.Trip.openTripPlanner(); break;
      case 'budget': this.Budget.openBudgetPlanner(); break;
      case 'nearby': this.Nearby.openNearbyAttractions(); break;
      case 'live': this.Track.openTripSelector(); break;
      case 'tips': this.Tips.openTravelTips(); break;
      case 'my-trips': this.Trip.openMyTripsModal(); break;
      case 'chatbot': this.Chatbot.open(); break;
      default: console.warn('Unknown action:', action);
    }
  },

  getCardActionFromTitle: function (card) {
    if (!card.classList.contains('card')) return '';
    const title = (card.querySelector('h3') && card.querySelector('h3').innerText) || '';
    const t = title.toLowerCase();
    if (t.includes('plan')) return 'plan';
    if (t.includes('my trips')) return 'my-trips';
    if (t.includes('budget planner') || t.includes('budget')) return 'budget';
    if (t.includes('nearby') || t.includes('attraction')) return 'nearby';
    if (t.includes('live')) return 'live';
    if (t.includes('tips')) return 'tips';
    if (t.includes('assistant')) return 'chatbot';
    return '';
  },

  // ---------------------------------
  // 4. MAP & GEOLOCATION MODULE
  // ---------------------------------
  Map: {
    initMainMap: function () {
      try {
        if (!App.State.map && App.Elements.map) {
          App.State.map = L.map(App.Elements.map).setView([20.5937, 78.9629], 5);
          L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; OpenStreetMap contributors'
          }).addTo(App.State.map);

          App.State.map.on('click', (e) => {
            if (!App.State.routeControl) {
                this.setDestinationMarker(e.latlng.lat, e.latlng.lng);
            }
          });
        } else if (App.State.map) {
          App.State.map.invalidateSize();
        }
      } catch (err) {
        console.error("initMainMap error:", err);
      }
    },

    initMyTripsMap: function () {
      try {
        if (!App.State.myTripsMap && App.Elements.myTripsMap) {
          App.State.myTripsMap = L.map(App.Elements.myTripsMap).setView([20.5937, 78.9629], 5);
          L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
            attribution: "&copy; OpenStreetMap contributors"
          }).addTo(App.State.myTripsMap);
        } else if (App.State.myTripsMap) {
          App.State.myTripsMap.invalidateSize();
        }
      } catch (err) {
        console.error("initMyTripsMap error:", err);
      }
    },

    setStartMarker: function (lat, lon) {
      if (!App.State.map) this.initMainMap();
      if (App.State.startMarker) App.State.map.removeLayer(App.State.startMarker);
      App.State.startMarker = L.marker([lat, lon], {
        icon: L.icon({
          iconUrl: 'https://cdn-icons-png.flaticon.com/512/684/684908.png',
          iconSize: [30, 30]
        })
      }).addTo(App.State.map);
      this.drawRoute();
    },

    setDestinationMarker: function (lat, lon) {
      if (!App.State.map) this.initMainMap();
      if (App.State.destMarker) App.State.map.removeLayer(App.State.destMarker);
      App.State.destMarker = L.marker([lat, lon], {
        icon: L.icon({
          iconUrl: 'https://cdn-icons-png.flaticon.com/512/252/252025.png',
          iconSize: [30, 30]
        })
      }).addTo(App.State.map);
      App.Util.setVal('latitude', lat);
      App.Util.setVal('longitude', lon);
      this.drawRoute();
    },

    drawRoute: function () {
      if (!App.State.map) return;
      App.Track.stopLiveTracking(true); // Stop any active live tracking

      const startLat = parseFloat(App.Util.getVal("start_lat") || 0);
      const startLon = parseFloat(App.Util.getVal("start_lon") || 0);
      const destLat = parseFloat(App.Util.getVal("latitude") || 0);
      const destLon = parseFloat(App.Util.getVal("longitude") || 0);

      if (!startLat || !startLon || !destLat || !destLon) return;

      if (App.State.routeControl) {
        App.State.map.removeControl(App.State.routeControl);
      }

      App.State.routeControl = L.Routing.control({
        waypoints: [L.latLng(startLat, startLon), L.latLng(destLat, destLon)],
        routeWhileDragging: false,
        show: false,
        draggableWaypoints: false
      }).on('routesfound', function(e) {
          // Store route info for budget planner
          App.State.routeControl._routes = e.routes;
      }).addTo(App.State.map);
    },

    fetchSuggestions: async function (type) {
      const isStart = (type === 'start');
      const queryEl = isStart ? App.Elements.start_location : App.Elements.destination;
      const query = queryEl ? queryEl.value : '';
      const suggestionsEl = isStart ? App.Elements.start_suggestions : App.Elements.dest_suggestions;

      if (!query || query.length < 2 || !suggestionsEl) {
        if(suggestionsEl) suggestionsEl.innerHTML = "";
        return;
      }

      try {
        const res = await fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(query)}`);
        const data = await res.json();
        suggestionsEl.innerHTML = "";

        data.slice(0, 5).forEach(loc => {
          const li = document.createElement("li");
          li.textContent = loc.display_name;
          li.onclick = () => {
            if (isStart) {
              App.Util.setVal('start_location', loc.display_name);
              App.Util.setVal('start_lat', loc.lat);
              App.Util.setVal('start_lon', loc.lon);
              this.setStartMarker(loc.lat, loc.lon);
            } else {
              App.Util.setVal('destination', loc.display_name);
              App.Util.setVal('latitude', loc.lat);
              App.Util.setVal('longitude', loc.lon);
              this.setDestinationMarker(loc.lat, loc.lon);
            }
            suggestionsEl.innerHTML = "";
          };
          suggestionsEl.appendChild(li);
        });
      } catch (err) {
        console.warn(`fetchSuggestions (${type}) error:`, err);
      }
    }
  },

  // ---------------------------------
  // 5. TRIP MANAGEMENT MODULE
  // ---------------------------------
  Trip: {
    openTripPlanner: function (isLiveTracking = false) {
      if (!App.Elements.tripPlannerModal) return;
      
      // Show/hide UI elements based on mode
      if (App.Elements['route-summary']) {
          App.Elements['route-summary'].style.display = isLiveTracking ? 'block' : 'none';
      }
      if (App.Elements['recalculate-route-btn']) {
          App.Elements['recalculate-route-btn'].style.display = isLiveTracking ? 'block' : 'none';
      }
      
      if (App.Elements['trip-planner-fields']) {
          App.Elements['trip-planner-fields'].style.display = isLiveTracking ? 'none' : 'block';
      }
      
      App.Elements.tripPlannerModal.classList.add('show');
      App.Map.initMainMap();
      setTimeout(() => { if (App.State.map) App.State.map.invalidateSize(); }, 300);

      if (navigator.geolocation && !isLiveTracking) {
        navigator.geolocation.getCurrentPosition(position => {
          const { latitude, longitude } = position.coords;
          App.Util.setVal('start_location', "My Current Location");
          App.Util.setVal('start_lat', latitude);
          App.Util.setVal('start_lon', longitude);
          App.Map.setStartMarker(latitude, longitude);
          if (App.State.map) App.State.map.setView([latitude, longitude], 10);
        }, err => {
          console.warn("Geolocation in trip planner failed:", err);
        });
      }
    },

    closeTripPlanner: function () {
      if (App.Elements.tripPlannerModal) App.Elements.tripPlannerModal.classList.remove('show');
      this.clearTripForm();
      App.Track.stopLiveTracking(true); // silent stop
    },

    clearTripForm: function () {
      ['trip_name', 'destination', 'start_location', 'budget', 'latitude', 'longitude', 'start_lat', 'start_lon', 'start_date', 'end_date']
        .forEach(id => App.Util.setVal(id, ''));
      if (App.State.destMarker && App.State.map) {
        App.State.map.removeLayer(App.State.destMarker);
        App.State.destMarker = null;
      }
    },

    addTrip: async function () {
      const trip = {
        trip_name: App.Util.getVal("trip_name"),
        destination: App.Util.getVal("destination"),
        start_date: App.Util.getVal("start_date"),
        end_date: App.Util.getVal("end_date"),
        budget: App.Util.getVal("budget") || 0,
        latitude: App.Util.getVal("latitude"),
        longitude: App.Util.getVal("longitude")
      };

      if (!trip.trip_name || !trip.destination || !trip.latitude || !trip.longitude) {
        alert("Please fill Trip Name, Destination and select a location on map.");
        return;
      }

      try {
        const response = await fetch("/add-trip", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(trip)
        });
        const result = await response.json();
        alert(result.message || "Response received");
        if (result.status === "success") {
          this.closeTripPlanner();
          // Reload trips for auto-selection
          App.loadTripsForAutoSelect();
        }
      } catch (err) {
        console.error("addTrip error:", err);
        alert("Failed to add trip (check console)");
      }
    },

    openMyTripsModal: function () {
      if (!App.Elements.myTripsModal) return;
      App.Elements.myTripsModal.classList.add('show');
      this.loadMyTripsList();
      App.Map.initMyTripsMap();
      setTimeout(() => { if (App.State.myTripsMap) App.State.myTripsMap.invalidateSize(); }, 300);
    },

    closeMyTripsModal: function () {
      if (App.Elements.myTripsModal) App.Elements.myTripsModal.classList.remove('show');
      this.closeEditPanel();
    },

    loadMyTripsList: async function () {
      if (!App.Elements.myTripsList) return;
      App.Elements.myTripsList.innerHTML = "<li>Loading...</li>";

      try {
        const response = await fetch("/get-trips");
        const data = await response.json();
        
        App.Elements.myTripsList.innerHTML = "";
        this.clearMapMarkers();

        if (data.status !== "success" || !data.trips || data.trips.length === 0) {
           App.Elements.myTripsList.innerHTML = "<li>No trips found. Create a trip first!</li>";
           return;
        }
        
        // Store trips for auto-selection
        App.State.allTrips = data.trips;
        
        const fragment = document.createDocumentFragment();
        data.trips.forEach(trip => {
          const li = document.createElement("li");
          li.innerHTML = `
            <span class="trip-info" data-action="view-trip" data-trip-id="${trip.id}">
              <strong>${App.Util.escapeHtml(trip.trip_name)}</strong> - ${App.Util.escapeHtml(trip.destination)}
            </span>
            <div class="trip-actions">
              <button data-action="track-trip" data-trip-id="${trip.id}" title="Track this Trip"><i class="fas fa-route"></i></button>
              <button data-action="open-budget" data-trip-id="${trip.id}" title="View Budget"><i class="fas fa-wallet"></i></button>
              <button data-action="edit-trip" data-trip-id="${trip.id}" title="Edit Trip"><i class="fas fa-edit"></i></button>
              <button data-action="delete-trip" data-trip-id="${trip.id}" class="btn-delete" title="Delete Trip"><i class="fas fa-trash"></i></button>
            </div>
          `;
          li.dataset.trip = JSON.stringify(trip);
          fragment.appendChild(li);
          this.addMapMarker(trip);
        });
        App.Elements.myTripsList.appendChild(fragment);

      } catch (err) {
        console.error("loadMyTripsList error:", err);
        App.Elements.myTripsList.innerHTML = "<li>Error loading trips.</li>";
      }
    },
    
    handleMyTripsClick: async function (e) {
        const target = e.target.closest('[data-action]');
        if (!target) return;
        
        const action = target.dataset.action;
        const tripId = target.dataset.tripId;
        const li = target.closest('li[data-trip]');
        const tripData = li ? JSON.parse(li.dataset.trip) : null;
        
        if (!tripData) return;
        
        switch (action) {
            case 'view-trip':
                this.showTripOnMap(tripData);
                break;
            case 'track-trip':
                App.State.activeTripForTracking = tripData;
                this.closeMyTripsModal();
                App.Track.startLiveTracking();
                break;
            case 'open-budget':
                this.closeMyTripsModal();
                App.Budget.openBudgetTracker(tripId);
                break;
            case 'edit-trip':
                this.openEditPanel(tripData);
                break;
            case 'delete-trip':
                await this.deleteTrip(tripId);
                break;
        }
    },

    addMapMarker: function (trip) {
      if (!App.State.myTripsMap) App.Map.initMyTripsMap();
      if (!App.State.myTripsMap) return;
      const marker = L.marker([trip.latitude, trip.longitude]).addTo(App.State.myTripsMap)
        .bindPopup(`<b>${App.Util.escapeHtml(trip.trip_name)}</b><br>${App.Util.escapeHtml(trip.destination)}<br>Budget: ₹${trip.budget || 0}`);
      App.State.myTripsMarkers.push(marker);
    },

    clearMapMarkers: function () {
      if (!App.State.myTripsMarkers || !App.State.myTripsMap) return;
      App.State.myTripsMarkers.forEach(marker => App.State.myTripsMap.removeLayer(marker));
      App.State.myTripsMarkers = [];
    },

    showTripOnMap: function (trip) {
      if (!App.State.myTripsMap) App.Map.initMyTripsMap();
      App.State.myTripsMap.setView([trip.latitude, trip.longitude], 10);
    },

    openEditPanel: function (trip) {
      if (!App.Elements.editTripContainer) return;
      App.Elements.editTripContainer.style.display = "block";
      App.Util.setVal("edit_trip_id", trip.id);
      App.Util.setVal("edit_trip_name", trip.trip_name);
      App.Util.setVal("edit_destination", trip.destination);
      App.Util.setVal("edit_budget", trip.budget || '');
      App.Util.setVal("edit_latitude", trip.latitude || '');
      App.Util.setVal("edit_longitude", trip.longitude || '');
    },

    closeEditPanel: function () {
      if (App.Elements.editTripContainer) App.Elements.editTripContainer.style.display = "none";
    },

    saveTripEdits: async function () {
      const trip = {
        trip_id: App.Util.getVal("edit_trip_id"),
        trip_name: App.Util.getVal("edit_trip_name"),
        destination: App.Util.getVal("edit_destination"),
        budget: App.Util.getVal("edit_budget"),
        latitude: App.Util.getVal("edit_latitude"),
        longitude: App.Util.getVal("edit_longitude")
      };

      if (!trip.trip_id) return alert("No trip selected");

      try {
        const response = await fetch("/update-trip", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(trip)
        });
        const data = await response.json();
        alert(data.message || "Update response");
        if (data.status === "success") {
          this.closeEditPanel();
          this.loadMyTripsList();
          // Reload trips for auto-selection
          App.loadTripsForAutoSelect();
        }
      } catch (err) {
        console.error("saveTripEdits error:", err);
        alert("Failed to update (see console)");
      }
    },

    deleteTrip: async function (trip_id) {
      if (!trip_id) return;
      if (!confirm("Are you sure you want to delete this trip?")) return;

      try {
        const response = await fetch("/delete-trip", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ trip_id })
        });
        const data = await response.json();
        alert(data.message || "Delete response");
        if (data.status === "success") {
          this.loadMyTripsList();
          // Reload trips for auto-selection
          App.loadTripsForAutoSelect();
        }
      } catch (err) {
        console.error("deleteTrip error:", err);
        alert("Failed to delete (see console)");
      }
    }
  },

  // ---------------------------------
  // 6. BUDGET MODULE (ENHANCED)
  // ---------------------------------
  Budget: {
    // Daily cost profiles (per person) — realistic Indian travel estimates
    // Includes: accommodation share + food + local transport + misc
    Profiles: {
        solo:  { budget: 800,  mid: 2000, luxury: 6000 },
        group: { budget: 600,  mid: 1500, luxury: 4500 }  // Per person (shared accommodation discount)
    },
    
    estimateBudget: async function() {
        const start_date = App.Util.getVal('start_date');
        const end_date = App.Util.getVal('end_date');
        const group_size = parseInt(App.Util.getVal('group_size')) || 1;
        const travel_style = document.querySelector('input[name="travel_style"]:checked')?.value || 'mid';
        const food_type = document.querySelector('input[name="food_type"]:checked')?.value || 'casual';
        
        // Calculate days cleanly
        let days = 1;
        if (start_date && end_date) {
            const start = new Date(start_date);
            const end = new Date(end_date);
            if(end >= start) {
               days = Math.max(1, Math.ceil((end - start) / (1000 * 60 * 60 * 24)));
            }
        }
        
        App.Util.setVal('budget', 'Loading ML...');
        
        try {
            const res = await fetch('/api/predict-budget', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ days, group_size, travel_style, food_type })
            });
            const data = await res.json();
            if (data.status === 'success') {
                App.Util.setVal('budget', Math.ceil(data.estimated_budget));
            } else {
                App.Util.setVal('budget', '');
                console.error("Budget ML Error:", data.message);
            }
        } catch(e) {
            console.error(e);
            App.Util.setVal('budget', '');
        }
    },
    
    openBudgetPlanner: function() {
      if (!App.State.allTrips || App.State.allTrips.length === 0) {
          return App.Util.showModal(`<h3>No Trips Found</h3><p>Please plan a trip first before adding expenses.</p><div class="modal-buttons text-center"><button onclick="App.Util.closeModal()" class="btn-close">Close</button></div>`);
      }
      
      let html = `<h3>Select Trip for Budget Tracker</h3>
                  <p>Which trip would you like to manage expenses for?</p>
                  <ul class="trip-list" style="max-height: 300px; overflow-y: auto;">`;
      
      // Iterate through all trips and create selector buttons
      App.State.allTrips.forEach(trip => {
          html += `
          <li style="padding: 10px; border-bottom: 1px solid #eee; display: flex; justify-content: space-between; align-items: center;">
              <div>
                  <strong>${App.Util.escapeHtml(trip.trip_name)}</strong><br>
                  <small><i class="fas fa-map-marker-alt"></i> ${App.Util.escapeHtml(trip.destination)}</small>
              </div>
              <button class="btn-primary" onclick="App.Budget.closeBudgetTracker(); App.Budget.openBudgetTracker(${trip.id})" style="padding: 5px 15px; font-size: 0.9rem;">
                  <i class="fas fa-wallet"></i> Select
              </button>
          </li>`;
      });
      
      html += `</ul><div class="modal-buttons text-center" style="margin-top: 15px;"><button onclick="App.Budget.closeBudgetTracker()" class="btn-close">Cancel</button></div>`;
      App.Util.showModal(html);
    },
  
    openBudgetTracker: async function (trip_id) {
        App.Util.showModal('<h3>Loading Expenses...</h3>');
      try {
        const res = await fetch(`/get-expenses/${trip_id}`);
        const data = await res.json();
        
        if (data.status !== 'success') {
            throw new Error(data.message);
        }

        // FIX: Safely parse budget values - guard against null/undefined to prevent NaN crash
        const tripBudget = parseFloat(data.trip_budget) || 0;
        const totalSpent = parseFloat(data.total_spent) || 0;
        const remaining = parseFloat(data.remaining_budget) || (tripBudget - totalSpent);

        let html = `<h3>Trip Expenses</h3>`;
        html += `
            <div class="budget-summary">
                <div>
                    <span>Total Budget</span>
                    <strong>₹${tripBudget.toFixed(2)}</strong>
                </div>
                <div>
                    <span>Total Spent</span>
                    <strong>₹${totalSpent.toFixed(2)}</strong>
                </div>
                <div>
                    <span>Remaining</span>
                    <strong class="${remaining < 0 ? 'error' : 'success'}">
                        ₹${remaining.toFixed(2)}
                    </strong>
                </div>
            </div>
        `;
        html += `<ul>`;
        if (data.expenses && data.expenses.length) {
          data.expenses.forEach(e => {
            html += `<li>
                        <strong>${App.Util.escapeHtml(e[2])}</strong> - ₹${e[3]}
                        ${e[4] ? `<br><small>${App.Util.escapeHtml(e[4])}</small>` : ''}
                     </li>`;
          });
        } else {
          html += `<li>No expenses yet.</li>`;
        }
        html += `</ul>
                 <div class="modal-buttons">
                    <button onclick="App.Budget.showAddExpenseForm(${trip_id})">Add Expense</button>
                    <button onclick="App.Budget.closeBudgetTracker()" class="btn-close">Close</button>
                 </div>`;
        App.Util.showModal(html);
      } catch (err) {
        console.error("openBudgetTracker error:", err);
        App.Util.showModal(`<h3>Error</h3><p>${err.message || 'Failed to load expenses.'}</p><div class="modal-buttons"><button onclick="App.Budget.closeBudgetTracker()" class="btn-close">Close</button></div>`);
      }
    },

    closeBudgetTracker: function () {
      if (App.Elements.budgetTrackerModal) App.Elements.budgetTrackerModal.classList.remove('show');
    },

    showAddExpenseForm: function (trip_id) {
      const formHtml = `
        <h3>Add Expense</h3>
        <label for="expCategory">Category:</label>
        <input id="expCategory" placeholder="e.g., Food, Transport">
        <label for="expAmount">Amount (₹):</label>
        <input id="expAmount" placeholder="e.g., 500" type="number">
        <label for="expDesc">Description (Optional):</label>
        <input id="expDesc" placeholder="e.g., Lunch at hotel">
        <div class="modal-buttons">
            <button onclick="App.Budget.saveExpense(${trip_id})">Save</button>
            <button onclick="App.Budget.openBudgetTracker(${trip_id})" class="btn-close">Back</button>
        </div>
      `;
      App.Util.showModal(formHtml);
    },

    saveExpense: async function (trip_id) {
      const category = document.getElementById("expCategory").value;
      const amount = document.getElementById("expAmount").value;
      const description = document.getElementById("expDesc").value;

      if (!category || !amount) return alert("Category and amount required");

      try {
        const res = await fetch("/add-expense", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ trip_id, category, amount, description })
        });
        const data = await res.json();
        if (data.status === "success") {
          this.openBudgetTracker(trip_id);
        } else {
          alert(data.message || "Failed to add expense");
        }
      } catch (err) {
        console.error("saveExpense error:", err);
        alert("Failed to add expense (see console)");
      }
    },

    /**
     * NEW: Smart Budget Estimator
     */
    estimateBudget: async function() {
        // 0. CHECK LOCATION COMPATIBILITY (India Only)
        // Ensure the autocomplete result contains 'india'
        const destinationStr = App.Util.getVal('destination') || '';
        if (destinationStr.trim() !== '' && !destinationStr.toLowerCase().includes('india')) {
            alert("Sorry, our Machine Learning Budget Engine currently only supports travel within India.");
            App.Util.setVal('budget', '');
            return;
        }

        // 1. Get number of days from trip dates
        const startDateStr = App.Util.getVal('start_date');
        const endDateStr = App.Util.getVal('end_date');
        if (!startDateStr || !endDateStr) {
            return alert("Please select Start and End dates first.");
        }
        const startDate = new Date(startDateStr);
        const endDate = new Date(endDateStr);
        if (isNaN(startDate) || isNaN(endDate) || endDate < startDate) {
            return alert("Please select a valid Start and End date.");
        }
        const numDays = Math.ceil(Math.abs(endDate - startDate) / (1000 * 60 * 60 * 24)) + 1;

        // 2. Get traveler profile
        const travelerType = document.querySelector('input[name="traveler_type"]:checked').value;
        const groupSize = (travelerType === 'group') ? (parseInt(App.Elements.group_size.value) || 1) : 1;
        const travelStyle = document.querySelector('input[name="travel_style"]:checked').value;
        const foodType = document.querySelector('input[name="food_type"]:checked').value;

        // Calculate Peak Season based on highly-traveled months (12, 1, 6, 7)
        const startMonth = startDate.getMonth() + 1;
        let calcSeason = 'shoulder';
        if ([12, 1, 6, 7].includes(startMonth)) calcSeason = 'peak';
        else if ([2, 3, 8, 9].includes(startMonth)) calcSeason = 'off-peak';

        App.Util.setVal('budget', 'Loading ML Matrix...');

        // 3. Request ML Budget Prediction
        try {
            const response = await fetch('/api/predict-budget', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    days: numDays,
                    traveler_type: travelerType,
                    group_size: groupSize,
                    travel_style: travelStyle,
                    food_type: foodType,
                    season: calcSeason
                })
            });
            const data = await response.json();

            if (data.status === 'success') {
                const estimatedBudget = data.estimated_budget;
                // 4. Fill the budget field
                App.Util.setVal('budget', estimatedBudget);
                alert(`ML Budget Estimate:\n
Travelers : ${groupSize} person(s) [${travelerType}, Hotel: ${travelStyle}, Food: ${foodType}]
Duration  : ${numDays} day(s)
Base Rate : ₹${data.cost_per_person}/person for ${numDays} days
---------------------------------
Total Estimated Budget: ₹${estimatedBudget}
(covers stay, food & local transport)`);
            } else {
                alert("Error predicting budget: " + data.message);
                App.Util.setVal('budget', '');
            }
        } catch (err) {
            console.error("estimateBudget error:", err);
            alert("Failed to reach ML API (see console)");
            App.Util.setVal('budget', '');
        }
    }
  },

  // ---------------------------------
  // 7. OTHER FEATURES MODULE (ENHANCED)
  // ---------------------------------
  Track: {
    openTripSelector: function () {
      if (!navigator.geolocation) {
          return alert("Geolocation not supported by your browser.");
      }
      if (App.State.watchId !== null) {
          alert("Live tracking is already active.");
          return;
      }
      if (!App.State.allTrips || App.State.allTrips.length === 0) {
          alert("You don't have any trips to track. Please plan a trip first.");
          App.Trip.openTripPlanner();
          return;
      }
      
      if (App.Elements.liveTrackSelectorModal) {
          App.Elements.liveTrackSelectorModal.classList.add('show');
          this.loadTrackingTrips();
      }
    },
    
    closeTripSelector: function () {
      if (App.Elements.liveTrackSelectorModal) {
          App.Elements.liveTrackSelectorModal.classList.remove('show');
      }
    },

    loadTrackingTrips: function () {
      const listEl = App.Elements.liveTrackTripsList;
      if (!listEl) return;
      listEl.innerHTML = "";
      
      App.State.allTrips.forEach(trip => {
          const li = document.createElement("li");
          li.style.cursor = "pointer";
          li.style.padding = "10px";
          li.style.borderBottom = "1px solid #ddd";
          li.innerHTML = `<strong>${App.Util.escapeHtml(trip.trip_name)}</strong> - ${App.Util.escapeHtml(trip.destination)}`;
          li.onclick = () => {
              this.closeTripSelector();
              this.startLiveTracking(trip);
          };
          listEl.appendChild(li);
      });
    },

    startLiveTracking: function (selectedTrip) {
      if (App.State.watchId !== null) {
          alert("Live tracking is already active.");
          return;
      }
      
      App.State.activeTripForTracking = selectedTrip;
      const trip = selectedTrip;
      const destLat = trip.latitude;
      const destLon = trip.longitude;
      
      alert(`Starting live tracking for: ${trip.trip_name}.\nOpening map...`);
      App.Trip.openTripPlanner(true); // Open map in tracking mode
      App.State.isTrackingInitialized = false; // Reset flag

      App.State.watchId = navigator.geolocation.watchPosition(pos => {
        const { latitude, longitude } = pos.coords;
        if (!App.State.map) return; 

        const startPoint = L.latLng(latitude, longitude);
        const endPoint = L.latLng(destLat, destLon);
        
        if (!App.State.isTrackingInitialized) {
            // --- This is the FIRST run ---
            App.State.isTrackingInitialized = true;
            
             // Create route control for Leaflet
            App.State.routeControl = L.Routing.control({
                waypoints: [startPoint, endPoint],
                routeWhileDragging: false,
                show: true, // Show the route instructions
                createMarker: function(i, wp, n) {
                    if (i === 0) { // Start marker (user's location)
                        App.State.liveMarker = L.marker(wp.latLng, {
                            icon: L.icon({
                                iconUrl: 'https://cdn-icons-png.flaticon.com/512/854/854878.png',
                                iconSize: [35, 35]
                            }),
                            draggable: false // Make user marker not draggable
                        }).bindPopup("Your Location");
                        return App.State.liveMarker;
                    } else { // Destination marker
                        return L.marker(wp.latLng, {
                            icon: L.icon({
                                iconUrl: 'https://cdn-icons-png.flaticon.com/512/252/252025.png',
                                iconSize: [30, 30]
                            }),
                            draggable: false
                        }).bindPopup(trip.destination);
                    }
                }
            }).on('routesfound', (e) => {
                // This listener updates the ETA box
                const summary = e.routes[0].summary;
                const distanceKm = summary.totalDistance / 1000;
                
                if (App.Elements['route-dist']) App.Elements['route-dist'].textContent = `${distanceKm.toFixed(1)} km`;
                
                // Request ML ETA
                this.updateMLEta(distanceKm);
            }).addTo(App.State.map);
            
        } else {
            // --- This is a SUBSEQUENT run ---
            
            // 1. Always update the marker's visual position (this is cheap)
            if (App.State.liveMarker) {
                App.State.liveMarker.setLatLng(startPoint);
            }
            // 2. Pan the map to the new position if it's out of view
            if (!App.State.map.getBounds().contains(startPoint)) {
                App.State.map.panTo(startPoint);
            }
            // 3. Update continuous ETA (Distance check)
            const remainingDistMeters = startPoint.distanceTo(endPoint);
            const remainingDistKm = remainingDistMeters / 1000;
            if (App.Elements['route-dist']) App.Elements['route-dist'].textContent = `${remainingDistKm.toFixed(1)} km (Linear)`;
            
            // Debounce ML ETA calls (every 500m moved) to avoid spam
            if (!this.lastEtaDist || Math.abs(this.lastEtaDist - remainingDistKm) > 0.5) {
                this.lastEtaDist = remainingDistKm;
                this.updateMLEta(remainingDistKm);
            }
        }

      }, err => {
        console.error("live tracking error:", err);
        let errorMsg = "Unable to get live location. Please ensure location services are enabled.";
        if(err.code === 1) errorMsg = "Location permission denied. Please enable it in your browser settings.";
        if(err.code === 2) errorMsg = "Location position unavailable. Check your network or GPS.";
        alert(errorMsg);
        this.stopLiveTracking(true); // silent stop
      }, { enableHighAccuracy: true, maximumAge: 0, timeout: 10000 });
    },
    
    // Extracted ML ETA function integrating the new Hypercube
    updateMLEta: async function(distanceKm) {
        if (distanceKm <= 0) return;
        try {
            const now = new Date();
            const hour = now.getHours();
            const dayOfWeek = now.getDay();
            const dayType = (dayOfWeek === 0 || dayOfWeek === 6) ? 'weekend' : 'weekday';
            
            const weatherSelect = document.getElementById('live_weather');
            const weather = weatherSelect ? weatherSelect.value : 'clear';
            
            const res = await fetch('/api/predict-eta', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    distance_km: distanceKm, 
                    hour_of_day: hour, 
                    day_type: dayType, 
                    weather: weather 
                })
            });
            const data = await res.json();
            if (data.status === 'success') {
                const durationMins = data.duration_minutes;
                const eta = new Date(Date.now() + durationMins * 60000);
                
                // Format explicitly with Date (e.g. 11/12/2026, 04:30 PM)
                let dateStr = eta.toLocaleDateString([], { month: 'short', day: 'numeric' });
                let timeStr = eta.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
                
                // We use document.getElementById instead of App.Elements incase caching detached it
                if (document.getElementById('route-eta')) {
                    document.getElementById('route-summary').style.display = 'block';
                    document.getElementById('route-eta').innerHTML = `${timeStr} (${dateStr})
                                                           <br><span style="color:#aaa; font-size:0.9rem; font-weight: normal;">${Math.ceil(durationMins)} min remaining</span>`;
                }
            }
        } catch(e) { console.error("ML ETA failed", e); }
    },
    
    recalculateRoute: function() {
        if (!App.State.isTrackingInitialized || !App.State.liveMarker || !App.State.routeControl) {
            return alert("Tracking is not active.");
        }
        
        const currentPos = App.State.liveMarker.getLatLng();
        const waypoints = App.State.routeControl.getWaypoints();
        const destPos = waypoints[waypoints.length - 1].latLng; // Get the last waypoint (destination)
        
        App.Elements['route-dist'].textContent = 'Recalculating...';
        App.Elements['route-eta'].textContent = '...';
        
        // This forces the control to find a new route
        App.State.routeControl.setWaypoints([currentPos, destPos]);
    },

    stopLiveTracking: function (silent = false) {
      if (App.State.watchId !== null) {
        navigator.geolocation.clearWatch(App.State.watchId);
        App.State.watchId = null;
      }
      if (App.State.routeControl) {
        if (App.State.map) App.State.map.removeControl(App.State.routeControl);
        App.State.routeControl = null;
      }
      if (App.State.liveMarker) {
          if (App.State.map) App.State.map.removeLayer(App.State.liveMarker);
          App.State.liveMarker = null;
      }
      App.State.activeTripForTracking = null;
      App.State.isTrackingInitialized = false;
      this.lastEtaDist = null;
      
      if (App.Elements['route-summary']) App.Elements['route-summary'].style.display = 'none';
      if (App.Elements['recalculate-route-btn']) App.Elements['recalculate-route-btn'].style.display = 'none';
      
      if (!silent) alert("Live tracking stopped.");
    }
  },

  Nearby: {
    openNearbyAttractions: async function (filterType = 'attractions') {
      let lat, lon, midLat, midLon, endLat, endLon;
      let queryMode = 'destination';
      const radius = 3000; // Reduced to 3km to prevent Overpass timeouts!
      let query = `[out:json][timeout:15];(`;
      
      let title = filterType === 'amenities' ? 'Finding nearby facilities...' : 'Finding famous places...';
      App.Util.showModal(`<h3><i class="fas fa-search-location"></i> ${title}</h3>`);

      // 1. Check if a live route is active
      if (App.State.routeControl && App.State.routeControl._routes) {
            const route = App.State.routeControl._routes[0];
            const waypoints = App.State.routeControl.getWaypoints();
            const midpoint = route.coordinates[Math.floor(route.coordinates.length / 2)];
            
            lat = waypoints[0].latLng.lat;
            lon = waypoints[0].latLng.lng;
            midLat = midpoint.lat;
            midLon = midpoint.lng;
            endLat = waypoints[waypoints.length - 1].latLng.lat;
            endLon = waypoints[waypoints.length - 1].latLng.lng;
            queryMode = 'route';
            
            query += this.getOverpassQuery(lat, lon, radius, filterType) + 
                     this.getOverpassQuery(midLat, midLon, radius, filterType) + 
                     this.getOverpassQuery(endLat, endLon, radius, filterType);
            
      // 2. Fallback: Check for a planned destination (from Plan a Trip)
      } else if (App.Util.getVal('latitude') && App.Util.getVal('longitude')) {
            lat = parseFloat(App.Util.getVal('latitude'));
            lon = parseFloat(App.Util.getVal('longitude'));
            query += this.getOverpassQuery(lat, lon, radius, filterType);
            
      // 3. Fallback: Get user's current location
      } else {
          try {
              const pos = await App.Util.getCurrentPosition();
              lat = pos.coords.latitude;
              lon = pos.coords.longitude;
              query += this.getOverpassQuery(lat, lon, radius, filterType);
              queryMode = 'current_location';
          } catch (err) {
              App.Util.showModal(`<h3>Error</h3><p>Could not get your location. Please enable location services or plan a trip first.</p><div class="modal-buttons"><button onclick="App.Budget.closeBudgetTracker()" class="btn-close">Close</button></div>`);
              return;
          }
      }
      
      query += `);out center 40;`; // Get 40 results

      try {
        // Try Kumi Systems first (often faster and less rate-limited than main overpass-api.de)
        const url = 'https://overpass.kumi.systems/api/interpreter';
        let res = await fetch(url, { method: 'POST', body: query });
        
        // Fallback if Kumi fails
        if (!res.ok) {
             res = await fetch('https://overpass-api.de/api/interpreter', { method: 'POST', body: query });
        }
        
        const data = await res.json();
        let html = `<h3>Famous Places & Attractions</h3>`;

        if (data.elements && data.elements.length) {
            html += '<ul style="list-style:none; padding: 0; max-height: 400px; overflow-y: auto;">';
            if (queryMode === 'route') {
                // Group results
                html += "<h4><i class='fas fa-map-marker-alt'></i> Near Your Start</h4>";
                data.elements.filter(e => App.Util.isNear(e, lat, lon)).forEach(e => html += this.formatPlace(e));
                html += "<h4><i class='fas fa-route'></i> Along Your Route</h4>";
                data.elements.filter(e => App.Util.isNear(e, midLat, midLon)).forEach(e => html += this.formatPlace(e));
                html += "<h4><i class='fas fa-flag-checkered'></i> Near Your Destination</h4>";
                data.elements.filter(e => App.Util.isNear(e, endLat, endLon)).forEach(e => html += this.formatPlace(e));
            } else {
                html += `<h4><i class='fas fa-map-marker-alt'></i> Near ${queryMode === 'destination' ? 'Your Destination' : 'You'}</h4>`;
                data.elements.forEach(e => html += this.formatPlace(e));
            }
            html += '</ul>';
        } else {
          html += `<p>No nearby attractions or facilities found.</p>`;
        }
        App.Util.showModal(html + `<div class="modal-buttons text-center"><button onclick="App.Budget.closeBudgetTracker()" class="btn-close">Close</button></div>`);
      } catch (err) {
        console.error("openNearbyAttractions error:", err);
        App.Util.showModal('<h3>Error</h3><p>Failed to fetch nearby attractions. The Overpass API may be busy. Please try again in a moment.</p><div class="modal-buttons"><button onclick="App.Budget.closeBudgetTracker()" class="btn-close">Close</button></div>');
      }
    },
    
    // Helper to build complex Overpass queries
    getOverpassQuery: function(lat, lon, radius, filterType = 'attractions') {
        let q = '';
        if (filterType === 'attractions' || filterType === 'all') {
            q += `
              node(around:${radius},${lat},${lon})[tourism~"attraction|museum|viewpoint|monument|theme_park|gallery|zoo"];
              node(around:${radius},${lat},${lon})[historic~"castle|fort|ruins|archaeological_site|monument|memorial"];
            `;
        }
        if (filterType === 'amenities' || filterType === 'all') {
            q += `
              node(around:${radius},${lat},${lon})[amenity~"atm|fuel|restaurant|cafe|hospital"];
            `;
        }
        return q;
    },
    
    // Helper function for formatting nearby places
    formatPlace: function(e) {
        const name = e.tags?.name || "Unnamed";
        // FILTER: Skip 'unknown' or unnamed places to keep UI clean
        if (name === "Unnamed" || name.trim() === "") return '';
        
        let type = e.tags?.tourism || e.tags?.amenity || e.tags?.historic || '';
        type = type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()); // Capitalize
        
        // Extract exact coordinates to build Google Maps Link
        const lat = e.lat || e.center?.lat;
        const lon = e.lon || e.center?.lon;
        const mapLink = lat && lon ? `https://www.google.com/maps/search/?api=1&query=${lat},${lon}` : '#';
        
        let icon = 'fa-map-pin'; // default
        if (['Fuel'].includes(type)) icon = 'fa-gas-pump';
        if (['Atm'].includes(type)) icon = 'fa-credit-card';
        if (['Restaurant', 'Cafe'].includes(type)) icon = 'fa-utensils';
        if (['Museum', 'Monument', 'Castle', 'Fort', 'Ruins', 'Archaeological Site', 'Memorial', 'Gallery'].includes(type)) icon = 'fa-landmark';
        if (['Viewpoint', 'Attraction', 'Theme Park', 'Zoo'].includes(type)) icon = 'fa-binoculars';
        
        return `<li style="padding: 10px; border-bottom: 1px solid #111; margin-bottom: 5px; background: rgba(0,0,0,0.1); border-radius: 8px;">
                    <a href="${mapLink}" target="_blank" style="text-decoration:none; color:inherit; display:block;">
                        <strong><i class="fas ${icon}" style="color:var(--primary); margin-right: 5px;"></i> ${App.Util.escapeHtml(name)}</strong><br>
                        <small style="color:#aaa;">${App.Util.escapeHtml(type)} • Click to Open Maps <i class="fas fa-external-link-alt" style="font-size:0.7em;"></i></small>
                    </a>
                 </li>`;
    }
  },

  Tips: {
    openTravelTips: function () {
      // NEW: More tips, categorized
      const tipCategories = {
          "Safety & Security": [
              "Always keep copies of your important documents (passport, ID, visa).",
              "Share your itinerary with family or friends back home.",
              "Avoid walking alone at night in poorly lit or unfamiliar areas.",
              "Use a money belt or secure pouch for your cash, cards, and passport.",
              "Be wary of public Wi-Fi. Use a VPN for sensitive transactions.",
              "Research common scams in your destination."
          ],
          "Packing Essentials": [
              "Pack a basic first-aid kit (band-aids, pain relievers, antiseptic wipes).",
              "A portable power bank is a lifesaver for long days.",
              "Bring a reusable water bottle to stay hydrated and reduce plastic waste.",
              "Pack one 'smart' outfit for unexpected formal occasions.",
              "Roll your clothes instead of folding to save space and reduce wrinkles.",
              "Bring universal power adapters."
          ],
          "Budget & Money": [
              "Inform your bank of your travel plans to avoid blocked cards.",
              "Carry a mix of cash and cards. Have a backup card stored separately.",
              "Eat where the locals eat. It's often cheaper and more authentic.",
              "Use public transportation instead of taxis or ride-shares.",
              "Look for free walking tours or city passes for attractions.",
              "Avoid currency exchange kiosks at airports; they have the worst rates."
          ],
          "Local Culture & Etiquette": [
              "Learn a few basic phrases in the local language (Hello, Thank You, Excuse Me).",
              "Research local customs and dress codes, especially for religious sites.",
              "Be respectful when taking photos of people. Always ask for permission first.",
              "Understand the local tipping culture.",
              "Try the local cuisine, but be polite if you don't like something."
          ]
      };

      // NEW: Build accordion HTML
      let html = `<h3><i class="fas fa-lightbulb"></i> Smart Travel Tips</h3>`;
      html += `<div class="tips-accordion">`;
      
      for (const category in tipCategories) {
          html += `<div class="tip-category">
                        <div class="tip-header">
                            <h4>${App.Util.escapeHtml(category)}</h4>
                            <i class="fas fa-chevron-down"></i>
                        </div>
                        <div class="tip-content">
                            <ul>
                                ${tipCategories[category].map(tip => `<li>${App.Util.escapeHtml(tip)}</li>`).join('')}
                            </ul>
                        </div>
                   </div>`;
      }
      
      html += `</div><div class="modal-buttons text-center"><button onclick="App.Budget.closeBudgetTracker()" class="btn-close">Close</button></div>`;
      
      App.Util.showModal(html);
      
      // Add click listeners for the new accordion
      document.querySelectorAll('.tip-header').forEach(header => {
          header.addEventListener('click', () => {
              header.parentElement.classList.toggle('active');
          });
      });
    }
  },
  
  // ---------------------------------
  // 8. NEW CHATBOT MODULE
  // ---------------------------------
  Chatbot: {
      init: function() {
          if (App.Elements.chatSendBtn) {
              App.Elements.chatSendBtn.addEventListener('click', this.sendMessage.bind(this));
              App.Elements.chatInput.addEventListener('keypress', (e) => {
                  if (e.key === 'Enter') this.sendMessage();
              });
          }
      },
      open: function() {
          if (App.Elements.chatbotModal) {
              App.Elements.chatbotModal.classList.add('show');
              // Append generic suggestion chips if they don't exist yet
              if (!document.getElementById('chatbot-chips')) {
                 const chipsDiv = document.createElement('div');
                 chipsDiv.id = 'chatbot-chips';
                 chipsDiv.style.cssText = "display: flex; gap: 8px; padding: 10px; overflow-x: auto; background: rgba(0,0,0,0.2);";
                 chipsDiv.innerHTML = `
                    <button class="chip" onclick="App.Chatbot.sendQuick('Find Nearby Facilities')" style="white-space:nowrap; padding: 5px 12px; border-radius: 20px; font-size: 0.8rem; background: var(--primary); border: none; color:auto; cursor:pointer;">🏥 Facilities</button>
                    <button class="chip" onclick="App.Chatbot.sendQuick('Safety Tips')" style="white-space:nowrap; padding: 5px 12px; border-radius: 20px; font-size: 0.8rem; background: var(--primary); border: none; color:auto; cursor:pointer;">🛡️ Safety</button>
                    <button class="chip" onclick="App.Chatbot.sendQuick('Where am I?')" style="white-space:nowrap; padding: 5px 12px; border-radius: 20px; font-size: 0.8rem; background: var(--primary); border: none; color:auto; cursor:pointer;">📍 Location</button>
                 `;
                 if(App.Elements.chatWindow) {
                     App.Elements.chatWindow.parentElement.insertBefore(chipsDiv, App.Elements.chatInput.parentElement);
                 }
              }
          }
          if (App.Elements.chatInput) App.Elements.chatInput.focus();
      },
      sendQuick: function(text) {
          if (App.Elements.chatInput) {
              App.Elements.chatInput.value = text;
              this.sendMessage();
          }
      },
      close: function() {
          if (App.Elements.chatbotModal) App.Elements.chatbotModal.classList.remove('show');
      },
      sendMessage: async function() {
          const input = App.Elements.chatInput ? App.Elements.chatInput.value.trim() : '';
          if (!input) return;
          if (input.length > 500) {
              this.addMessage('⚠️ Please keep messages under 500 characters.', 'bot');
              return;
          }
          
          this.addMessage(input, 'user');
          App.Elements.chatInput.value = "";
          
          // Show typing indicator immediately
          if (App.Elements['bot-typing-indicator']) {
              App.Elements['bot-typing-indicator'].style.display = 'flex';
          }
          if (App.Elements.chatWindow) {
              App.Elements.chatWindow.scrollTop = App.Elements.chatWindow.scrollHeight;
          }
          
          // ─── Call the AI backend via handleChatbotMessage from chatbot.js ───
          if (typeof window.handleChatbotMessage === 'function') {
              await window.handleChatbotMessage(input);
          } else {
              // Fallback if chatbot.js fails to load
              if (App.Elements['bot-typing-indicator']) {
                  App.Elements['bot-typing-indicator'].style.display = 'none';
              }
              this.addMessage('⚠️ AI module offline. Emergency numbers: Police 100/112, Ambulance 108.', 'bot');
          }
      },
      addMessage: function(message, sender) {
          const msgDiv = document.createElement('div');
          msgDiv.className = `chat-message ${sender}`;
          msgDiv.innerHTML = `<p>${message}</p>`; // Allow HTML from chatbot
          msgDiv.style.opacity = '0';
          msgDiv.style.transform = 'translateY(8px)';
          
          // Insert before typing indicator
          if (App.Elements.chatWindow && App.Elements['bot-typing-indicator']) {
            App.Elements.chatWindow.insertBefore(msgDiv, App.Elements['bot-typing-indicator']);
            App.Elements.chatWindow.scrollTop = App.Elements.chatWindow.scrollHeight;
          }
          
          // Animate in
          requestAnimationFrame(() => {
              msgDiv.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
              msgDiv.style.opacity = '1';
              msgDiv.style.transform = 'translateY(0)';
          });
      },
      // Legacy getResponse kept for backward compat — no longer used
      getResponse: function(input) {
          return "Please upgrade — using async backend now.";
      }
  },
  
  // ---------------------------------
  // 9. UTILITIES
  // ---------------------------------
  Util: {
    getVal: function (id) {
        const el = App.Elements[id] || document.getElementById(id);
        return el ? el.value : '';
    },
    setVal: function (id, value) {
        const el = App.Elements[id] || document.getElementById(id);
        if (el) el.value = value;
    },
    escapeHtml: function (text) {
      if (!text) return '';
      return String(text).replace(/[&<>"']/g, function (m) {
        return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[m];
      });
    },
    showModal: function (htmlContent) {
      if (App.Elements.budgetTrackerModal && App.Elements.budgetTrackerModalContent) {
        App.Elements.budgetTrackerModalContent.innerHTML = htmlContent;
        App.Elements.budgetTrackerModal.classList.add("show");
      } else {
        console.error("Modal elements not found");
      }
    },
    // NEW: Promise-based Geolocation
    getCurrentPosition: function() {
        return new Promise((resolve, reject) => {
            if (!navigator.geolocation) {
                reject(new Error("Geolocation not supported."));
            }
            navigator.geolocation.getCurrentPosition(resolve, reject, {
                enableHighAccuracy: true,
                timeout: 5000,
                maximumAge: 0
            });
        });
    },
    // Helper function to check if a point is near a coordinate
    isNear: function(element, lat, lon) {
        const R = 6371e3; // metres
        const lat1 = element.lat * Math.PI/180;
        const lat2 = lat * Math.PI/180;
        const deltaLat = (lat-element.lat) * Math.PI/180;
        const deltaLon = (lon-element.lon) * Math.PI/180;

        const a = Math.sin(deltaLat/2) * Math.sin(deltaLat/2) +
                  Math.cos(lat1) * Math.cos(lat2) *
                  Math.sin(deltaLon/2) * Math.sin(deltaLon/2);
        const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
        const d = R * c; // in metres
        return d < 11000; // 11km radius for grouping
    }
  }
};

// ---------------------------------
// 10. APP ENTRY POINT
// ---------------------------------
window.onload = () => {
    try {
        App.init();
    } catch(e) {
        console.error("Failed to initialize app:", e);
        document.body.innerHTML = "<h1 style='color:red; text-align: center; margin-top: 50px;'>Error: Application failed to load.</h1><p style='text-align: center;'>This is likely due to a mismatch between dashboard.html and dashboard.js. Please ensure all files are updated.</p>";
    }
};

// Global bridge functions
function addTrip() { App.Trip.addTrip(); }
function closeTripPlanner() { App.Trip.closeTripPlanner(); }
function saveTripEdits() { App.Trip.saveTripEdits(); }
function closeEditPanel() { App.Trip.closeEditPanel(); }
function closeMyTripsModal() { App.Trip.closeMyTripsModal(); }