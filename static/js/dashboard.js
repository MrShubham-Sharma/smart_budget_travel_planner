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
    this.Interactions.init(); // Initialize premium interactions
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

    // Modal closing (overlay clicks) — tripPlannerModal deliberately excluded
    // so users don't lose their form data by accidentally clicking outside
    window.addEventListener('click', (event) => {
      if (event.target === this.Elements.myTripsModal) this.Trip.closeMyTripsModal();
      if (event.target === this.Elements.budgetTrackerModal) this.Budget.closeBudgetTracker();
      if (event.target === this.Elements.chatbotModal) this.Chatbot.close();
    });

    // Suggestion input debouncing & Keyboard Navigation
    if (this.Elements.start_location) {
      this.Elements.start_location.addEventListener("input", () => {
        clearTimeout(this.State.startTimeout);
        this.State.startTimeout = setTimeout(() => this.Map.fetchSuggestions('start'), 300);
      });
      this.Elements.start_location.addEventListener("keydown", (e) => this.Map.handleSuggestionsKeydown(e, 'start'));
    }
    if (this.Elements.destination) {
      this.Elements.destination.addEventListener("input", () => {
        clearTimeout(this.State.destTimeout);
        this.State.destTimeout = setTimeout(() => {
          this.Map.fetchSuggestions('dest');
          // Auto-recalculate budget if form is ready
          setTimeout(() => this.Budget.autoRecalculateBudget(), 500);
        }, 300);
      });
      this.Elements.destination.addEventListener("keydown", (e) => this.Map.handleSuggestionsKeydown(e, 'dest'));
    }

    // "My Trips" list event delegation
    if (this.Elements.myTripsList) {
      this.Elements.myTripsList.addEventListener('click', this.Trip.handleMyTripsClick.bind(this.Trip));
    }

    // Close suggestions on outside click
    document.addEventListener('click', (e) => {
      if (this.Elements.start_suggestions && !e.target.closest('.input-with-icon')) {
        this.Elements.start_suggestions.innerHTML = '';
      }
      if (this.Elements.dest_suggestions && !e.target.closest('.input-with-icon')) {
        this.Elements.dest_suggestions.innerHTML = '';
      }
    });

    // Budget Calculator radio buttons
    document.querySelectorAll('input[name="traveler_type"]').forEach(radio => {
      radio.addEventListener('change', (e) => {
        if (this.Elements.group_size_wrapper) {
          this.Elements.group_size_wrapper.style.display = (e.target.value === 'group') ? 'block' : 'none';
        }
        // Auto-recalculate budget when traveler type changes
        setTimeout(() => this.Budget.autoRecalculateBudget(), 100);
      });
    });

    // Auto-recalculate budget when key fields change
    ['start_date', 'end_date', 'group_size'].forEach(fieldId => {
      const el = document.getElementById(fieldId);
      if (el) {
        el.addEventListener('change', () => {
          setTimeout(() => this.Budget.autoRecalculateBudget(), 300);
        });
      }
    });

    // Auto-recalculate when budget-related radio buttons change
    ['travel_style', 'food_type', 'stay_type'].forEach(radioName => {
      document.querySelectorAll(`input[name="${radioName}"]`).forEach(radio => {
        radio.addEventListener('change', () => {
          setTimeout(() => this.Budget.autoRecalculateBudget(), 300);
        });
      });
    });

    // Auto-recalculate when family checkbox changes
    const familyEl = document.getElementById('is_family');
    if (familyEl) {
      familyEl.addEventListener('change', () => {
        setTimeout(() => this.Budget.autoRecalculateBudget(), 300);
      });
    }
  },

  // NEW: Load trips for auto-selection
  loadTripsForAutoSelect: async function () {
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

    if (target.classList.contains('card')) {
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
      case 'itinerary': this.Itinerary.openSelector(); break;
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
      }).on('routesfound', function (e) {
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
        if (suggestionsEl) suggestionsEl.innerHTML = "";
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
    },

    handleSuggestionsKeydown: function (e, type) {
      const isStart = (type === 'start');
      const suggestionsEl = isStart ? App.Elements.start_suggestions : App.Elements.dest_suggestions;
      if (!suggestionsEl) return;

      const items = suggestionsEl.querySelectorAll('li');
      if (items.length === 0) return;

      let currentIndex = -1;
      items.forEach((item, index) => {
        if (item.classList.contains('highlighted')) {
          currentIndex = index;
        }
      });

      if (e.key === 'ArrowDown') {
        e.preventDefault();
        if (currentIndex < items.length - 1) {
          if (currentIndex >= 0) items[currentIndex].classList.remove('highlighted');
          items[currentIndex + 1].classList.add('highlighted');
          items[currentIndex + 1].scrollIntoView({ block: 'nearest' });
        }
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        if (currentIndex > 0) {
          items[currentIndex].classList.remove('highlighted');
          items[currentIndex - 1].classList.add('highlighted');
          items[currentIndex - 1].scrollIntoView({ block: 'nearest' });
        }
      } else if (e.key === 'Enter') {
        e.preventDefault();
        if (currentIndex >= 0 && currentIndex < items.length) {
          items[currentIndex].click();
        }
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
      // Reset stay_type radio to default
      const defaultStay = document.getElementById('stay_budget_hotel');
      if (defaultStay) defaultStay.checked = true;
      if (App.State.destMarker && App.State.map) {
        App.State.map.removeLayer(App.State.destMarker);
        App.State.destMarker = null;
      }
    },

    addTrip: async function () {
      const stayTypeEl = document.querySelector('input[name="stay_type"]:checked');
      const trip = {
        trip_name: App.Util.getVal("trip_name"),
        destination: App.Util.getVal("destination"),
        start_date: App.Util.getVal("start_date"),
        end_date: App.Util.getVal("end_date"),
        budget: App.Util.getVal("budget") || 0,
        latitude: App.Util.getVal("latitude"),
        longitude: App.Util.getVal("longitude"),
        stay_type: stayTypeEl ? stayTypeEl.value : "budget_hotel"
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
      solo: { budget: 800, mid: 2000, luxury: 6000 },
      group: { budget: 600, mid: 1500, luxury: 4500 }  // Per person (shared accommodation discount)
    },

    estimateBudget: async function (silent = false) {
      const destination = App.Util.getVal('destination');
      const start_date = App.Util.getVal('start_date');
      const end_date = App.Util.getVal('end_date');

      // ── 1. Destination is required and must be in India ─────────────────
      if (!destination || destination.trim() === '') {
        const destInput = document.getElementById('destination');
        if (destInput) {
          destInput.style.border = '2px solid #ef4444';
          destInput.placeholder = '⚠️ Please enter a destination first!';
          destInput.focus();
          setTimeout(() => {
            destInput.style.border = '';
            destInput.placeholder = 'e.g., Goa, India';
          }, 3000);
        }
        return;
      }
      // ── 2. Dates are required ───────────────────────────────────────────
      if (!start_date || !end_date) {
        return alert('Please select Start and End dates first.');
      }
      const startDate = new Date(start_date);
      const endDate = new Date(end_date);
      if (isNaN(startDate) || isNaN(endDate) || endDate < startDate) {
        return alert('Please select valid Start and End dates.');
      }

      // ── 3. Read all form values fresh every single call ─────────────────
      const numDays = Math.max(1, Math.ceil((endDate - startDate) / (1000 * 60 * 60 * 24)));
      const travelerType = document.querySelector('input[name="traveler_type"]:checked')?.value || 'solo';
      const groupSize = (travelerType === 'group') ? (parseInt(App.Util.getVal('group_size')) || 1) : 1;
      const travelStyle = document.querySelector('input[name="travel_style"]:checked')?.value || 'mid';
      const foodType = document.querySelector('input[name="food_type"]:checked')?.value || 'dhaba';
      const stayType = (document.querySelector('input[name="stay_type"]:checked')?.value) || 'budget_hotel';
      const isFamily = document.getElementById('is_family')?.checked || false;

      // ── 4. Auto-detect season from travel month ─────────────────────────
      const startMonth = startDate.getMonth() + 1;
      let season = 'shoulder';
      if ([12, 1, 6, 7].includes(startMonth)) season = 'peak';
      else if ([2, 3, 8, 9].includes(startMonth)) season = 'off-peak';

      // ── 5. Auto-detect booking window ──────────────────────────────────
      const daysFromNow = Math.ceil((startDate - new Date()) / (1000 * 60 * 60 * 24));
      let booking = 'normal';
      if (daysFromNow <= 3) booking = 'last-minute';
      else if (daysFromNow >= 30) booking = 'advance';

      App.Util.setVal('budget', 'Calculating...');

      // ── 6. Call the ML API ──────────────────────────────────────────────
      try {
        const res = await fetch('/api/predict-budget', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            days: numDays,
            group_size: groupSize,
            travel_style: travelStyle,
            food_type: foodType,
            season: season,
            booking: booking,
            stay_type: stayType,
            is_family: isFamily,
            destination: destination
          })
        });
        const data = await res.json();
        if (data.status === 'success') {
          const total = Math.ceil(data.estimated_budget);
          const perPerson = Math.ceil(data.cost_per_person);
          App.Util.setVal('budget', total);

          const bookingLabel = { 'last-minute': 'Last Minute 🔥', 'normal': 'Normal', 'advance': 'Advance ✅' }[booking];
          const foodLabel = foodType.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
          const stayLabel = stayType.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
          const familyLabel = isFamily ? '👨‍👩‍👧‍👦 Family Travel (20% discount applied)' : 'Individual/Group Travel';
          
          if (!silent) {
            alert(
              `🧮 ML Budget Estimate

👥 Travelers  : ${groupSize} person(s) — ${travelerType}
🎒 Style      : ${travelStyle}  |  🍛 Food: ${foodLabel}
🏨 Stay       : ${stayLabel}
👨‍👩‍👧‍👦 Family    : ${familyLabel}
📅 Duration   : ${numDays} day(s)  |  Season: ${season}
📆 Booking    : ${bookingLabel}

💰 Per Person  : ₹${perPerson.toLocaleString('en-IN')}
━━━━━━━━━━━━━━━━━━━━━━━━
✈️ Total Budget : ₹${total.toLocaleString('en-IN')}
(includes stay + food + local transport)`
            );
          }
        } else {
          App.Util.setVal('budget', '');
          if (!silent) {
            alert('Budget error: ' + (data.message || 'Unknown error'));
          }
        }
      } catch (e) {
        console.error('estimateBudget error:', e);
        App.Util.setVal('budget', '');
        if (!silent) {
          alert('Failed to reach ML API. Is the server running?');
        }
      }
    },

    // Auto-recalculate budget when destination or key fields change
    autoRecalculateBudget: async function () {
      const destination = App.Util.getVal('destination');
      const start_date = App.Util.getVal('start_date');
      const end_date = App.Util.getVal('end_date');

      // Only auto-recalculate if we have the minimum required fields
      if (!destination || !start_date || !end_date) {
        return; // Not enough info yet
      }

      // Check if dates are valid
      const startDate = new Date(start_date);
      const endDate = new Date(end_date);
      if (isNaN(startDate) || isNaN(endDate) || endDate < startDate) {
        return; // Invalid dates
      }

      // Show subtle calculating indicator
      const budgetEl = document.getElementById('budget');
      if (budgetEl) {
        budgetEl.style.opacity = '0.7';
        budgetEl.placeholder = 'Recalculating...';
      }

      try {
        // Use the same logic as estimateBudget but without alerts
        await this.estimateBudget();
      } catch (e) {
        console.log('Auto-recalculation skipped:', e.message);
      } finally {
        // Restore normal appearance
        if (budgetEl) {
          budgetEl.style.opacity = '1';
          const currentVal = App.Util.getVal('budget');
          budgetEl.placeholder = currentVal ? '' : 'Click \'Calculate\' to estimate';
        }
      }
    },

    // ✅ Clear the trip form back to defaults
    clearTripForm: function () {
      ['trip_name', 'destination', 'start_location', 'budget', 'latitude', 'longitude', 'start_lat', 'start_lon']
        .forEach(id => App.Util.setVal(id, ''));
      const startDateEl = document.getElementById('start_date');
      const endDateEl = document.getElementById('end_date');
      if (startDateEl) startDateEl.value = '';
      if (endDateEl) endDateEl.value = '';

      // Reset radios to defaults
      const defaultRadios = {
        travel_style: 'budget',
        food_type: 'dhaba',
        stay_type: 'budget_hotel',
        traveler_type: 'solo'
      };
      Object.entries(defaultRadios).forEach(([name, val]) => {
        const el = document.querySelector(`input[name="${name}"][value="${val}"]`);
        if (el) el.checked = true;
      });

      // Reset family checkbox
      const familyEl = document.getElementById('is_family');
      if (familyEl) familyEl.checked = false;

      // Reset group size
      const gsEl = document.getElementById('group_size');
      if (gsEl) gsEl.value = '1';
      gsEl?.style && (gsEl.style.display = 'none');

      App.Util.setVal('budget', '');
      const budgetEl = document.getElementById('budget');
      if (budgetEl) budgetEl.placeholder = "Click 'Calculate' to estimate";
    },

    openBudgetPlanner: function () {
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
      const today = new Date();
      today.setHours(0, 0, 0, 0);

      App.State.allTrips.forEach(trip => {
        const li = document.createElement("li");
        li.style.cursor = "pointer";
        li.style.padding = "12px";
        li.style.borderBottom = "1px solid rgba(255,255,255,0.1)";

        // Work out trip status relative to today
        const startDate = trip.start_date ? new Date(trip.start_date) : null;
        const endDate = trip.end_date ? new Date(trip.end_date) : null;
        let statusBadge = '';
        let statusWarn = '';

        if (startDate) {
          startDate.setHours(0, 0, 0, 0);
          if (endDate) endDate.setHours(0, 0, 0, 0);

          const daysToStart = Math.ceil((startDate - today) / 86400000);

          if (daysToStart > 0) {
            // Future trip
            statusBadge = `<span style="background:#f59e0b;color:#000;border-radius:4px;padding:1px 6px;font-size:0.75rem;margin-left:6px;">In ${daysToStart}d</span>`;
            statusWarn = `<div style="color:#f59e0b;font-size:0.78rem;margin-top:3px;">⚠️ Trip starts ${startDate.toDateString()} — ETA will reflect the planned travel date.</div>`;
          } else if (endDate && today > endDate) {
            // Past trip
            statusBadge = `<span style="background:#ef4444;color:#fff;border-radius:4px;padding:1px 6px;font-size:0.75rem;margin-left:6px;">Past</span>`;
            statusWarn = `<div style="color:#ef4444;font-size:0.78rem;margin-top:3px;">⚠️ This trip ended on ${endDate.toDateString()}. ETA uses today's time.</div>`;
          } else {
            // Active / ongoing trip
            statusBadge = `<span style="background:#22c55e;color:#000;border-radius:4px;padding:1px 6px;font-size:0.75rem;margin-left:6px;">Active ✓</span>`;
          }
        }

        const dateLabel = startDate ? `<small style="opacity:0.7;"> | 📅 ${startDate.toDateString()}</small>` : '';
        li.innerHTML = `
              <div><strong>${App.Util.escapeHtml(trip.trip_name)}</strong>${statusBadge} &mdash; ${App.Util.escapeHtml(trip.destination)}${dateLabel}</div>
              ${statusWarn}
          `;
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
            createMarker: function (i, wp, n) {
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
        if (err.code === 1) errorMsg = "Location permission denied. Please enable it in your browser settings.";
        if (err.code === 2) errorMsg = "Location position unavailable. Check your network or GPS.";
        alert(errorMsg);
        this.stopLiveTracking(true); // silent stop
      }, { enableHighAccuracy: true, maximumAge: 0, timeout: 10000 });
    },

    // ML ETA — uses trip's start_date as travel reference for future trips
    updateMLEta: async function (distanceKm) {
      if (distanceKm <= 0) return;
      try {
        // Use trip's planned start_date if it's in the future, else use now
        const trip = App.State.activeTripForTracking;
        let referenceTime = new Date(); // default: right now

        if (trip && trip.start_date) {
          const tripStart = new Date(trip.start_date);
          tripStart.setHours(8, 0, 0, 0); // Assume 8 AM departure on trip day
          if (tripStart > new Date()) {
            referenceTime = tripStart; // future trip → use planned start
          }
        }

        const hour = referenceTime.getHours();
        const dayType = (referenceTime.getDay() === 0 || referenceTime.getDay() === 6) ? 'weekend' : 'weekday';

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
          // Arrival = referenceTime + travel duration
          const arrival = new Date(referenceTime.getTime() + durationMins * 60000);

          const dateStr = arrival.toLocaleDateString([], { day: 'numeric', month: 'short', year: 'numeric' });
          const timeStr = arrival.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

          // Label: "Planned Arrival" for future trips, "ETA" for live/current
          const isFuture = referenceTime > new Date();
          const label = isFuture ? '📅 Planned Arrival' : '🚗 ETA';
          const subLabel = isFuture
            ? `Departs ${referenceTime.toDateString()} at ${referenceTime.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`
            : `${Math.ceil(durationMins)} min remaining`;

          if (document.getElementById('route-eta')) {
            document.getElementById('route-summary').style.display = 'block';
            document.getElementById('route-eta').innerHTML =
              `<span style="font-size:0.8rem;opacity:0.7;">${label}</span><br>
                         <strong>${timeStr}</strong> &nbsp;<span style="opacity:0.8;">(${dateStr})</span>
                         <br><span style="color:#aaa;font-size:0.85rem;font-weight:normal;">${subLabel}</span>`;
          }
        }
      } catch (e) { console.error("ML ETA failed", e); }
    },

    recalculateRoute: function () {
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
    // ─── Nearby Places with REAL Names (Wikipedia Geosearch) ─────────────────
    // Uses Wikipedia's free Geosearch API — no API key, fast CDN.
    // Returns actual named places (temples, forts, parks, etc.) near GPS coords.
    openNearbyAttractions: async function (filterType = 'attractions') {

      const SKELETON = [...Array(5)].map(() => `
        <div style="background:rgba(255,255,255,0.06);border-radius:10px;padding:14px;
                    display:flex;align-items:center;gap:12px;margin-bottom:8px;">
          <div style="width:36px;height:36px;border-radius:50%;background:rgba(255,255,255,0.1);
                      animation:pulse 1.4s ease infinite;flex-shrink:0;"></div>
          <div style="flex:1;">
            <div style="height:12px;background:rgba(255,255,255,0.1);border-radius:6px;
                        margin-bottom:8px;animation:pulse 1.4s ease infinite;"></div>
            <div style="height:10px;width:55%;background:rgba(255,255,255,0.07);border-radius:6px;
                        animation:pulse 1.4s ease infinite;"></div>
          </div>
        </div>`).join('');

      const title = filterType === 'amenities' ? '🏥 Nearby Facilities' : '🗺️ Famous & Historical Places';

      // Show skeleton immediately
      App.Util.showModal(`
        <h3 style="margin-bottom:6px;">${title}</h3>
        <p style="color:#64748b;font-size:0.82rem;margin:0 0 14px;">Fetching real places near you…</p>
        ${SKELETON}
      `);

      // ── Get coordinates ──
      let lat = null, lon = null;
      if (App.Util.getVal('latitude') && App.Util.getVal('longitude')) {
        lat = parseFloat(App.Util.getVal('latitude'));
        lon = parseFloat(App.Util.getVal('longitude'));
      } else if (App._userLat) {
        lat = App._userLat;
        lon = App._userLon;
      } else {
        try {
          const pos = await App.Util.getCurrentPosition();
          lat = pos.coords.latitude;
          lon = pos.coords.longitude;
          App._userLat = lat;
          App._userLon = lon;
        } catch (e) { /* no GPS */ }
      }

      if (!lat) {
        App.Util.showModal(`
            <h3>${title}</h3>
            <p style="color:#f87171;">📍 Could not get your location. Please enable location services or plan a trip first.</p>
            <div class="modal-buttons"><button onclick="App.Budget.closeBudgetTracker()" class="btn-close">Close</button></div>`);
        return;
      }

      // ── Wikipedia Geosearch API ──
      // Returns up to 500 named Wikipedia articles near coordinates
      // Completely free, no API key, fast Wikipedia CDN
      const radius = 10000; // 10km
      const limit = 500;
      const wikiUrl = `https://en.wikipedia.org/w/api.php?` +
        `action=query&list=geosearch` +
        `&gscoord=${lat}|${lon}` +
        `&gsradius=${radius}` +
        `&gslimit=${limit}` +
        `&format=json&origin=*`;

      let places = [];
      try {
        const res = await fetch(wikiUrl);
        const data = await res.json();
        const rawPlaces = data?.query?.geosearch || [];
        // ── BLACKLIST: Exclude all non-tourist places ──────────────────────────────
        // Schools, hospitals, government offices, stations, residential areas, etc.
        const BLACKLIST = new RegExp('\\b(' + [
          // Education
          'school', 'college', 'university', 'institute', 'academy', 'polytechnic',
          'vidyalaya', 'vidyamandir', 'mahavidyalaya', 'convent', 'seminary',
          // Medical
          'hospital', 'clinic', 'dispensary', 'nursing home', 'health cent',
          'medical cent', 'primary health', 'phc', 'chc', 'community health',
          // Transport / Transit
          'railway station', 'train station', 'metro station', 'bus stand',
          'bus terminal', 'bus depot', 'bus stop', 'auto stand', 'taxi stand',
          'junction station', 'airport terminal', 'railway junction',
          // Government / Admin
          'assembly', 'vidhan sabha', 'secretariat', 'collectorate', 'tehsildar',
          'tehsil', 'taluka', 'mandal', 'taluk', 'block office', 'panchayat office',
          'municipal office', 'corporation office', 'government office',
          'district court', 'high court', 'court complex', 'police station',
          'police headquarters', 'fire station', 'post office', 'sub post office',
          'income tax', 'customs office', 'passport office', 'ration shop',
          // Residential / Locality
          'colony', 'residential', 'society', 'apartment', 'flat', 'housing',
          'layout', 'extension', 'nagar', 'vihar', 'enclave', 'township',
          'phase\\s*\\d', 'sector\\s*\\d', 'block\\s*[a-z\\d]',
          // Banking / Finance
          'bank', 'atm', 'finance office',
          // Religious — local/small (keep only famous ones via whitelist)
          // Industry / Utility
          'factory', 'power plant', 'sewage', 'water treatment', 'pumping station',
          'telephone exchange', 'substation', 'warehouse', 'godown',
          // Sports — local venues
          'playground', 'sports complex', 'indoor stadium', 'multipurpose hall',
        ].join('|') + ')\\b', 'i');

        // Apply filter: must NOT match blacklist
        places = rawPlaces.filter(p => {
          const titleLower = p.title.toLowerCase();
          if (BLACKLIST.test(titleLower)) return false; // Exclude non-tourist venues
          return true;
        });

        // Limit the final displayed list to top 30 to not overwhelm the UI
        places = places.slice(0, 30);
      } catch (err) {
        console.error('Wikipedia Geosearch failed:', err);
      }

      // ── Smart icon based on place name keywords (tourist places only) ──
      const getIcon = (name) => {
        const n = name.toLowerCase();
        if (/fort|killa|qila|castle|palace|mahal|haveli/.test(n))
          return { icon: 'fa-chess-rook', color: '#f59e0b' };
        if (/temple|mandir|devi|shiva|ganesh|hanuman|ram|kali|balaji|tirupati|jain|gurudwara|gurdwara|ashram|math/.test(n))
          return { icon: 'fa-place-of-worship', color: '#a78bfa' };
        if (/mosque|masjid|dargah|mazar|shrine|tomb|mausoleum/.test(n))
          return { icon: 'fa-place-of-worship', color: '#34d399' };
        if (/church|cathedral|chapel|basilica|abbey|monastery/.test(n))
          return { icon: 'fa-place-of-worship', color: '#60a5fa' };
        if (/stupa|pagoda/.test(n))
          return { icon: 'fa-dharmachakra', color: '#fbbf24' };
        if (/museum|gallery|art|heritage|cultural|planetarium|science centre|aquarium|observatory/.test(n))
          return { icon: 'fa-landmark', color: '#38bdf8' };
        if (/ruin|archaeo|monument|memorial|pillar|stambha|arch|gate|darwaza|cenotaph|chhatri|stepwell|baori|vav|bawdi/.test(n))
          return { icon: 'fa-monument', color: '#fbbf24' };
        if (/cave|cavern|lena|gufa|grotto/.test(n))
          return { icon: 'fa-mountain', color: '#6ee7b7' };
        if (/waterfall|falls|dam|lake|reservoir|kund|tirth|ghat/.test(n))
          return { icon: 'fa-water', color: '#38bdf8' };
        if (/river|stream/.test(n))
          return { icon: 'fa-water', color: '#60a5fa' };
        if (/national park|sanctuary|wildlife|biosphere|reserve|forest|jungle/.test(n))
          return { icon: 'fa-tree', color: '#4ade80' };
        if (/garden|botanical|rose garden|rock garden/.test(n))
          return { icon: 'fa-leaf', color: '#86efac' };
        if (/beach|coast|island|bay|cape|peninsula/.test(n))
          return { icon: 'fa-umbrella-beach', color: '#fbbf24' };
        if (/hill|peak|mountain|valley|gorge|canyon|cliff|viewpoint|lookout/.test(n))
          return { icon: 'fa-mountain', color: '#a3e635' };
        if (/zoo|safari/.test(n))
          return { icon: 'fa-paw', color: '#f472b6' };
        if (/lighthouse|tower|minaret|clock tower/.test(n))
          return { icon: 'fa-broadcast-tower', color: '#94a3b8' };
        if (/amphitheatre|auditorium|opera house/.test(n))
          return { icon: 'fa-theater-masks', color: '#fb923c' };
        return { icon: 'fa-map-marker-alt', color: '#38bdf8' };
      };

      // ── Expose cached places + title so the detail view can rebuild the list ──
      App.Nearby._cachedPlaces = places;
      App.Nearby._cachedTitle = title;
      App.Nearby._cachedLat = lat;
      App.Nearby._cachedLon = lon;
      App.Nearby._getIcon = getIcon;

      App.Nearby._renderList();
    },

    // Render the list of places into the modal (called on load and on "Back")
    _renderList: function () {
      const places = App.Nearby._cachedPlaces;
      const title = App.Nearby._cachedTitle;
      const lat = App.Nearby._cachedLat;
      const lon = App.Nearby._cachedLon;
      const getIcon = App.Nearby._getIcon;

      const items = places.map((p, idx) => {
        const { icon, color } = getIcon(p.title);
        const distKm = (p.dist / 1000).toFixed(1);
        const mapsUrl = `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(p.title)}&query=${p.lat},${p.lon}`;

        return `
            <div style="display:flex;align-items:center;gap:12px;padding:11px 10px;
                        background:rgba(255,255,255,0.04);border-radius:10px;margin-bottom:6px;
                        border:1px solid rgba(255,255,255,0.06);transition:background 0.2s;"
                 onmouseover="this.style.background='rgba(56,189,248,0.06)'"
                 onmouseout="this.style.background='rgba(255,255,255,0.04)'">
              <div style="width:36px;height:36px;border-radius:50%;background:rgba(0,0,0,0.3);
                          display:flex;align-items:center;justify-content:center;flex-shrink:0;">
                <i class="fas ${icon}" style="color:${color};font-size:0.95rem;"></i>
              </div>
              <div style="flex:1;min-width:0;">
                <div style="font-weight:600;font-size:0.92rem;white-space:nowrap;
                            overflow:hidden;text-overflow:ellipsis;">${p.title}</div>
                <div style="color:#64748b;font-size:0.8rem;margin-top:2px;">
                  <span style="color:#34d399;">📍 ${distKm} km away</span>
                </div>
              </div>
              <div style="display:flex;gap:6px;flex-shrink:0;">
                <!-- Info button: fetches Wikipedia summary inline -->
                <button onclick="App.Nearby._showPlaceDetail(${idx})"
                        title="See summary"
                        style="width:30px;height:30px;border-radius:8px;background:rgba(167,139,250,0.15);
                               border:none;cursor:pointer;display:flex;align-items:center;justify-content:center;">
                  <i class="fas fa-info-circle" style="color:#a78bfa;font-size:0.85rem;"></i>
                </button>
                <!-- Maps button -->
                <a href="${mapsUrl}" target="_blank" rel="noopener"
                   title="Open in Google Maps"
                   style="width:30px;height:30px;border-radius:8px;background:rgba(56,189,248,0.15);
                          display:flex;align-items:center;justify-content:center;text-decoration:none;">
                  <i class="fas fa-map-pin" style="color:#38bdf8;font-size:0.8rem;"></i>
                </a>
              </div>
            </div>`;
      }).join('');

      const distBadge = `<span style="color:#34d399;font-size:0.8rem;">
        <i class="fas fa-crosshairs"></i> ${lat.toFixed(4)}, ${lon.toFixed(4)} · within 10km
      </span>`;

      // Handle empty state gracefully
      const bodyContent = places.length === 0
        ? `<div style="text-align:center;padding:30px 20px;">
             <div style="font-size:3rem;margin-bottom:14px;">🏛️</div>
             <h4 style="color:#f1f5f9;margin-bottom:8px;">No Famous Places Found Nearby</h4>
             <p style="color:#64748b;font-size:0.88rem;line-height:1.6;">
               No historical, religious or tourist attractions were found within 10 km of your location.<br>
               Try searching from a different destination or a major city.
             </p>
           </div>`
        : `<div style="max-height:420px;overflow-y:auto;padding-right:4px;">${items}</div>`;

      App.Util.showModal(`
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;flex-wrap:wrap;gap:6px;">
          <h3 style="margin:0;">${title}</h3>
          ${distBadge}
        </div>
        <p style="color:#64748b;font-size:0.8rem;margin:2px 0 14px;">
          <span style="color:${places.length > 0 ? '#34d399' : '#f87171'};">
            ${places.length} famous &amp; historical places
          </span>
          &nbsp;·&nbsp; Showing temples, forts, monuments, parks &amp; more
        </p>
        ${bodyContent}
        <div class="modal-buttons" style="margin-top:12px;">
          <button onclick="App.Budget.closeBudgetTracker()" class="btn-close">Close</button>
        </div>`);
    },

    // Show inline Wikipedia summary for a place (no new tab)
    _showPlaceDetail: async function (idx) {
      const p = App.Nearby._cachedPlaces[idx];
      const getIcon = App.Nearby._getIcon;
      const { icon, color } = getIcon(p.title);
      const distKm = (p.dist / 1000).toFixed(1);
      const mapsUrl = `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(p.title)}&query=${p.lat},${p.lon}`;

      // Show loading state
      App.Util.showModal(`
        <button onclick="App.Nearby._renderList()"
                style="background:none;border:none;color:#38bdf8;cursor:pointer;font-size:0.9rem;margin-bottom:12px;padding:0;display:flex;align-items:center;gap:6px;">
          <i class="fas fa-arrow-left"></i> Back to list
        </button>
        <div style="display:flex;align-items:center;gap:12px;margin-bottom:16px;">
          <div style="width:44px;height:44px;border-radius:50%;background:rgba(0,0,0,0.3);
                      display:flex;align-items:center;justify-content:center;flex-shrink:0;">
            <i class="fas ${icon}" style="color:${color};font-size:1.1rem;"></i>
          </div>
          <div>
            <h3 style="margin:0;font-size:1rem;">${p.title}</h3>
            <span style="color:#34d399;font-size:0.8rem;">📍 ${distKm} km away</span>
          </div>
        </div>
        <div style="background:rgba(255,255,255,0.04);border-radius:10px;padding:16px;margin-bottom:14px;">
          <div style="text-align:center;padding:20px 0;">
            <i class="fas fa-spinner fa-spin" style="color:#38bdf8;font-size:1.5rem;"></i>
            <p style="color:#64748b;margin-top:8px;font-size:0.85rem;">Fetching summary…</p>
          </div>
        </div>`);

      // Fetch Wikipedia REST summary (same as chatbot uses)
      let summaryHtml = '';
      let thumbnailHtml = '';
      try {
        const wikiApiUrl = `https://en.wikipedia.org/api/rest_v1/page/summary/${encodeURIComponent(p.title.replace(/ /g, '_'))}`;
        const res = await fetch(wikiApiUrl, { headers: { 'User-Agent': 'TripWise/1.0' } });
        const data = await res.json();

        if (data.extract && data.extract.length > 40) {
          // Show 3 sentences max (same as chatbot)
          const sentences = data.extract.split('. ').slice(0, 3).join('. ') + '.';
          summaryHtml = `<p style="color:#cbd5e1;font-size:0.9rem;line-height:1.6;margin:0;">${sentences}</p>`;
        } else {
          summaryHtml = `<p style="color:#64748b;font-size:0.9rem;">No summary available for this place.</p>`;
        }

        if (data.thumbnail?.source) {
          thumbnailHtml = `<img src="${data.thumbnail.source}"
                                   alt="${p.title}"
                                   style="width:100%;max-height:160px;object-fit:cover;border-radius:10px;margin-bottom:12px;">`;
        }
      } catch (err) {
        summaryHtml = `<p style="color:#64748b;font-size:0.9rem;">Could not fetch details right now.</p>`;
      }

      // Render the detail view
      App.Util.showModal(`
        <button onclick="App.Nearby._renderList()"
                style="background:none;border:none;color:#38bdf8;cursor:pointer;font-size:0.9rem;
                       margin-bottom:12px;padding:0;display:flex;align-items:center;gap:6px;">
          <i class="fas fa-arrow-left"></i> Back to list
        </button>

        <div style="display:flex;align-items:center;gap:12px;margin-bottom:14px;">
          <div style="width:44px;height:44px;border-radius:50%;background:rgba(0,0,0,0.3);
                      display:flex;align-items:center;justify-content:center;flex-shrink:0;">
            <i class="fas ${icon}" style="color:${color};font-size:1.1rem;"></i>
          </div>
          <div>
            <h3 style="margin:0;font-size:1.05rem;line-height:1.3;">${p.title}</h3>
            <span style="color:#34d399;font-size:0.8rem;">📍 ${distKm} km away</span>
          </div>
        </div>

        ${thumbnailHtml}

        <div style="background:rgba(255,255,255,0.04);border-radius:10px;padding:14px;margin-bottom:14px;
                    border-left:3px solid ${color};">
          ${summaryHtml}
          <p style="color:#475569;font-size:0.75rem;margin:10px 0 0;border-top:1px solid rgba(255,255,255,0.06);padding-top:8px;">
            <i class="fas fa-globe" style="color:#64748b;"></i> Source: Wikipedia
          </p>
        </div>

        <a href="${mapsUrl}" target="_blank" rel="noopener"
           style="display:flex;align-items:center;justify-content:center;gap:8px;
                  background:rgba(56,189,248,0.15);border:1px solid rgba(56,189,248,0.3);
                  border-radius:10px;padding:12px;text-decoration:none;color:#38bdf8;
                  font-weight:600;font-size:0.9rem;margin-bottom:14px;transition:background 0.2s;"
           onmouseover="this.style.background='rgba(56,189,248,0.25)'"
           onmouseout="this.style.background='rgba(56,189,248,0.15)'">
          <i class="fas fa-map-marker-alt"></i> Open in Google Maps
        </a>

        <div class="modal-buttons">
          <button onclick="App.Budget.closeBudgetTracker()" class="btn-close">Close</button>
        </div>`);
    },

    // Stubs — kept for backward compat
    getOverpassQuery: function () { return ''; },
    formatPlace: function () { return ''; },


  },

  Tips: {
    openTravelTips: function () {
      // NEW: More tips, categorized
      const tipCategories = {
        "Safety & Security": [
          "Carry your Aadhaar Card / Voter ID — required for hotel check-ins and train travel in India.",
          "Share your live location with family using apps like WhatsApp or Google Maps.",
          "Avoid walking alone at night in poorly lit or unfamiliar areas.",
          "Use a money belt or secure pouch for your cash, cards, and phone.",
          "Be cautious with public Wi-Fi. Use mobile data or a VPN for online banking.",
          "Research local safety concerns in your destination before arriving.",
          "Keep emergency contacts saved: Local police (100), Ambulance (108), Fire (101)."
        ],
        "Packing Essentials": [
          "Pack a basic first-aid kit (band-aids, pain relievers, antiseptic wipes, ORS packets).",
          "A portable power bank is essential for long journeys and areas with power cuts.",
          "Bring a reusable water bottle to stay hydrated and reduce plastic waste.",
          "Pack one 'smart' outfit for temple visits or formal occasions.",
          "Roll your clothes instead of folding to save space and reduce wrinkles.",
          "Bring mosquito repellent, sunscreen, and comfortable walking shoes for Indian weather."
        ],
        "Budget & Money": [
          "Inform your bank of your travel plans to avoid blocked cards.",
          "Carry a mix of cash and cards. ATMs are widely available but may charge fees.",
          "Eat at local dhabas and street food stalls for authentic, budget-friendly meals.",
          "Use public transport (buses, metros, local trains) instead of expensive cabs.",
          "Look for government-run tourist information centers for free advice and maps.",
          "Avoid exchanging money at airports; use banks or ATMs for better rates."
        ],
        "Local Culture & Etiquette": [
          "Learn basic Hindi phrases: 'Namaste' (hello), 'Dhanyavaad' (thank you), 'Maaf kijiye' (excuse me).",
          "Dress modestly when visiting temples and religious sites.",
          "Remove shoes when entering homes, temples, and mosques.",
          "Be respectful when taking photos of people. Always ask for permission first.",
          "Try local cuisine but be polite if you don't like spicy food.",
          "Understand the concept of 'Indian Standard Time' — things often run late!"
        ],
        "Indian Travel Specific": [
          "Book train tickets via IRCTC app/website — it's reliable and has Tatkal option.",
          "Download offline maps and keep physical maps as backup.",
          "Carry extra cash for tolls, parking, and small purchases.",
          "Respect local customs: Don't eat with left hand, cover head in gurdwaras.",
          "Stay hydrated and avoid street food if you have a sensitive stomach.",
          "Use apps like RedBus, MakeMyTrip for bus and hotel bookings."
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
    init: function () {
      if (App.Elements.chatSendBtn) {
        App.Elements.chatSendBtn.addEventListener('click', this.sendMessage.bind(this));
        App.Elements.chatInput.addEventListener('keypress', (e) => {
          if (e.key === 'Enter') this.sendMessage();
        });
      }
    },
    open: function () {
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
          if (App.Elements.chatWindow) {
            App.Elements.chatWindow.parentElement.insertBefore(chipsDiv, App.Elements.chatInput.parentElement);
          }
        }
      }
      if (App.Elements.chatInput) App.Elements.chatInput.focus();
    },
    sendQuick: function (text) {
      if (App.Elements.chatInput) {
        App.Elements.chatInput.value = text;
        this.sendMessage();
      }
    },
    close: function () {
      if (App.Elements.chatbotModal) App.Elements.chatbotModal.classList.remove('show');
    },
    sendMessage: async function () {
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
    addMessage: function (message, sender) {
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
    getResponse: function (input) {
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
    // Haversine distance in km (rounded to 1 decimal)
    calcDist: function (lat1, lon1, lat2, lon2) {
      if (!lat1 || !lon1 || !lat2 || !lon2) return null;
      const R = 6371;
      const dLat = (lat2 - lat1) * Math.PI / 180;
      const dLon = (lon2 - lon1) * Math.PI / 180;
      const a = Math.sin(dLat / 2) * Math.sin(dLat / 2)
        + Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180)
        * Math.sin(dLon / 2) * Math.sin(dLon / 2);
      return (R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))).toFixed(1);
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
    getCurrentPosition: function () {
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
    isNear: function (element, lat, lon) {
      const R = 6371e3; // metres
      const lat1 = element.lat * Math.PI / 180;
      const lat2 = lat * Math.PI / 180;
      const deltaLat = (lat - element.lat) * Math.PI / 180;
      const deltaLon = (lon - element.lon) * Math.PI / 180;

      const a = Math.sin(deltaLat / 2) * Math.sin(deltaLat / 2) +
        Math.cos(lat1) * Math.cos(lat2) *
        Math.sin(deltaLon / 2) * Math.sin(deltaLon / 2);
      const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
      const d = R * c; // in metres
      return d < 11000; // 11km radius for grouping
    }
  }, // <--- added comma here for new property

  // ---------------------------------
  // 11. ITINERARY MODULE
  // ---------------------------------
  Itinerary: {
    openSelector: async function() {
      const modal = document.getElementById('itinerarySelectorModal');
      const list  = document.getElementById('itineraryTripsList');
      if (!modal || !list) return;

      list.innerHTML = '<li style="padding:12px;opacity:0.7;">⏳ Loading your trips…</li>';
      modal.classList.add('show');

      try {
        const res  = await fetch('/get-trips');
        const data = await res.json();

        if (data.status === 'success' && data.trips && data.trips.length > 0) {
          list.innerHTML = '';
          data.trips.forEach(trip => {
            const start = new Date(trip.start_date);
            const end   = new Date(trip.end_date);
            const days  = Math.max(1, Math.ceil((end - start) / 86400000));
            const hasCoords = trip.latitude && trip.longitude;

            const li = document.createElement('li');
            li.style.cssText = 'display:flex;justify-content:space-between;align-items:center;padding:12px;border-bottom:1px solid rgba(255,255,255,0.08);gap:10px;';

            // Info section (safe to set via innerHTML — no user-JS involved)
            const info = document.createElement('div');
            info.innerHTML = `
              <strong style="font-size:0.95rem;">${trip.trip_name}</strong>
              <div style="font-size:0.8rem;opacity:0.75;margin-top:3px;">📍 ${trip.destination} &nbsp;•&nbsp; ${days} day${days>1?'s':''} &nbsp;•&nbsp; ₹${trip.budget.toLocaleString('en-IN')}</div>
            `;

            // Button created as a real DOM element — addEventListener avoids double-quote
            // conflicts that break onclick="...JSON.stringify(destination)..." in HTML
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.textContent = '🗺️ Build';
            btn.style.cssText = 'flex-shrink:0;padding:7px 16px;border-radius:20px;font-size:0.82rem;font-weight:600;background:linear-gradient(135deg,#38bdf8,#2575fc);border:none;color:#fff;cursor:pointer;';
            btn.addEventListener('click', () => {
              App.Itinerary.generateTimeline(trip.latitude, trip.longitude, days, trip.destination);
            });

            li.appendChild(info);
            li.appendChild(btn);
            list.appendChild(li);
          });
        } else {
          list.innerHTML = '<li style="padding:16px;text-align:center;opacity:0.7;">No trips saved yet. Use "Plan Trip" first.</li>';
        }
      } catch (err) {
        console.error('Itinerary openSelector error:', err);
        list.innerHTML = '<li style="padding:12px;color:#f87171;">❌ Error loading trips.</li>';
      }
    },

    closeSelector: function() {
      const m = document.getElementById('itinerarySelectorModal');
      if (m) m.classList.remove('show');
    },

    generateTimeline: async function(lat, lon, days, destinationName) {
      // Close the trip-selector modal first
      this.closeSelector();

      const modal     = document.getElementById('itineraryDisplayModal');
      const container = document.getElementById('itinerary-container');
      const subtitle  = document.getElementById('itinerary-subtitle');
      if (!modal || !container) return;

      subtitle.textContent = `Generating itinerary for ${destinationName}…`;
      container.innerHTML  = `
        <div style="text-align:center;padding:50px 0;">
          <div style="font-size:2.5rem;animation:pulse 1.5s infinite;">⏳</div>
          <p style="margin-top:14px;opacity:0.6;font-size:0.9rem;">Reading Wikipedia Geodata…</p>
        </div>`;
      modal.classList.add('show');

      try {
        // --- If the trip has no saved coords, geocode the destination first ---
        if (!lat || !lon || lat === 'null' || lon === 'null') {
          container.innerHTML = `<div style="text-align:center;padding:30px;"><div style="font-size:1.5rem;">🔍</div><p style="opacity:0.7;font-size:0.85rem;">Geocoding ${destinationName}…</p></div>`;
          const geoRes  = await fetch(`https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(destinationName)}&format=json&limit=1`, {headers:{'User-Agent':'SmartTravelPlanner/1.0'}});
          const geoData = await geoRes.json();
          if (!geoData || geoData.length === 0) {
            container.innerHTML = `<p style="color:#f87171;text-align:center;">❌ Could not find "${destinationName}" on the map. Try editing the trip to add more detail to the destination name.</p>`;
            return;
          }
          lat = parseFloat(geoData[0].lat);
          lon = parseFloat(geoData[0].lon);
          container.innerHTML = `<div style="text-align:center;padding:30px;"><div style="font-size:1.5rem;">✅</div><p style="opacity:0.7;font-size:0.85rem;">Found ${destinationName}! Fetching landmarks…</p></div>`;
        }

        const res  = await fetch(`/api/itinerary-generator?lat=${lat}&lon=${lon}&days=${days}`);
        const data = await res.json();

        if (data.status !== 'success') {
          container.innerHTML = `<p style="color:#f87171;text-align:center;padding:20px;">⚠️ ${data.message || 'No landmarks found near this destination.'}</p>`;
          return;
        }

        subtitle.textContent = `${days}-day itinerary · ${data.total_places} landmarks near ${destinationName}`;
        container.innerHTML = '';

        data.itinerary.forEach(day => {
          const dayDiv = document.createElement('div');
          dayDiv.className = 'timeline-day';
          dayDiv.innerHTML = `<h3>📅 Day ${day.day}</h3>`;

          const timelineDiv = document.createElement('div');
          timelineDiv.className = 'timeline';

          day.activities.forEach(act => {
            const imgHtml = act.image
              ? `<img src="${act.image}" class="timeline-img" alt="${act.title}" loading="lazy" onerror="this.style.display='none'">`
              : `<div class="timeline-img" style="display:flex;align-items:center;justify-content:center;background:linear-gradient(135deg,#fca311,#f76b1c);color:#fff;font-size:1.8rem;font-weight:700;">${act.title.charAt(0)}</div>`;

            const item = document.createElement('div');
            item.className = 'timeline-item';
            item.innerHTML = `
              ${imgHtml}
              <div class="timeline-content">
                <h4>${act.title}</h4>
                <p>${act.summary || 'A notable landmark worth visiting.'}</p>
                <div style="margin-top:8px;display:flex;gap:8px;flex-wrap:wrap;">
                  <span style="font-size:0.75rem;background:rgba(56,189,248,0.12);color:#38bdf8;
                              border:1px solid rgba(56,189,248,0.3);border-radius:20px;padding:3px 10px;">
                    📍 ${(act.dist !== undefined ? (act.dist/1000).toFixed(1)+' km away' : 'Landmark')}
                  </span>
                  <button onclick="App.Itinerary._showMapWidget('${encodeURIComponent(act.title)}',${act.lat},${act.lon})"
                          style="font-size:0.75rem;background:rgba(37,117,252,0.12);color:#60a5fa;
                                 border:1px solid rgba(37,117,252,0.3);border-radius:20px;padding:3px 10px;
                                 cursor:pointer;">
                    🗺️ Map Preview
                  </button>
                </div>
              </div>`;
            timelineDiv.appendChild(item);
          });

          dayDiv.appendChild(timelineDiv);
          container.appendChild(dayDiv);
        });

      } catch (err) {
        console.error('generateTimeline error:', err);
        container.innerHTML = `<p style="color:#f87171;text-align:center;padding:20px;">❌ Failed to connect to the itinerary engine. Check your internet connection.</p>`;
      }
    },

    // Inline map widget — no external redirect
    _showMapWidget: function(encodedTitle, lat, lon) {
      const title = decodeURIComponent(encodedTitle);
      const mapUrl = `https://www.openstreetmap.org/export/embed.html?bbox=${lon-0.02},${lat-0.02},${lon+0.02},${lat+0.02}&layer=mapnik&marker=${lat},${lon}`;
      // Show inside a toast-style overlay inside the modal container
      const container = document.getElementById('itinerary-container');
      const overlay = document.createElement('div');
      overlay.id = 'itinerary-map-overlay';
      overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.75);z-index:99999;display:flex;align-items:center;justify-content:center;padding:20px;';
      overlay.innerHTML = `
        <div style="background:#1e293b;border-radius:16px;width:100%;max-width:560px;overflow:hidden;box-shadow:0 25px 50px rgba(0,0,0,0.5);">
          <div style="padding:16px 20px;display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid rgba(255,255,255,0.1);">
            <strong style="color:#fff;font-size:0.95rem;">📍 ${title}</strong>
            <button onclick="document.getElementById('itinerary-map-overlay').remove()"
                    style="background:none;border:none;color:#94a3b8;font-size:1.4rem;cursor:pointer;line-height:1;">×</button>
          </div>
          <iframe src="${mapUrl}" width="100%" height="300" frameborder="0" scrolling="no"
                  style="display:block;border:none;" title="Map of ${title}"></iframe>
          <div style="padding:12px 20px;">
            <a href="https://www.openstreetmap.org/?mlat=${lat}&mlon=${lon}" target="_blank" rel="noopener"
               style="font-size:0.82rem;color:#38bdf8;text-decoration:none;">🔗 Open full map in new tab</a>
          </div>
        </div>`;
      overlay.addEventListener('click', e => { if (e.target === overlay) overlay.remove(); });
      document.body.appendChild(overlay);
    },

    closeDisplay: function() {
      const m = document.getElementById('itineraryDisplayModal');
      if (m) m.classList.remove('show');
    }
  },

  // ---------------------------------
  // 9. INTERACTIONS MODULE (MAGNETIC & MICRO)
  // ---------------------------------
  Interactions: {
    init: function() {
      this.initMagneticEffects();
      this.initButtonGlows();
    },

    initMagneticEffects: function() {
      const targets = document.querySelectorAll('.magnetic-target');
      targets.forEach(target => {
        // Wrap content if not already wrapped
        if (!target.querySelector('.magnetic-wrap')) {
          target.innerHTML = `<div class="magnetic-wrap">${target.innerHTML}</div>`;
        }

        const wrap = target.querySelector('.magnetic-wrap');

        target.addEventListener('mousemove', (e) => {
          const rect = target.getBoundingClientRect();
          const x = e.clientX - rect.left - rect.width / 2;
          const y = e.clientY - rect.top - rect.height / 2;

          // Pull wrap towards cursor (magnetic effect)
          wrap.style.transform = `translate(${x * 0.25}px, ${y * 0.25}px)`;
        });

        target.addEventListener('mouseleave', () => {
          wrap.style.transform = `translate(0px, 0px)`;
        });
      });
    },

    initButtonGlows: function() {
      const btns = document.querySelectorAll('button:not(.btn-close), .card.option-card');
      btns.forEach(btn => {
        btn.addEventListener('mousedown', () => {
          btn.style.transform = 'scale(0.96)';
          btn.style.filter = 'brightness(1.1)';
        });
        const resetStyles = () => {
          btn.style.transform = '';
          btn.style.filter = '';
        };
        btn.addEventListener('mouseup', resetStyles);
        btn.addEventListener('mouseleave', resetStyles);
      });
    }
  },

  // ---------------------------------
  // 10. UTILITIES
  // ---------------------------------
  Util: {
    getVal: function (id) {
      const el = document.getElementById(id);
      return el ? el.value : "";
    },
    setVal: function (id, val) {
      const el = document.getElementById(id);
      if (el) el.value = val;
    },
    escapeHtml: function (str) {
      if (!str) return "";
      return str.replace(/[&<>"']/g, m => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
      }[m]));
    }
  }
};

// ---------------------------------
// 10. APP ENTRY POINT
// ---------------------------------
window.onload = () => {
  try {
    App.init();
  } catch (e) {
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
function clearTripForm() { App.Budget.clearTripForm(); }
