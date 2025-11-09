// ---------------- INITIALIZE ----------------
let map, startMarker, destMarker, routeControl;

// Load trips on page load
window.onload = () => {
  initMap();
  loadTrips();
};

// ---------------- INIT MAP ----------------
function initMap() {
  map = L.map('map').setView([20.5937, 78.9629], 5); // Center India

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap contributors'
  }).addTo(map);

  // Click to set destination marker
  map.on('click', function(e) {
    setDestinationMarker(e.latlng.lat, e.latlng.lng);
  });
}

// ---------------- OPEN MODAL ----------------
function openTripPlanner() {
  const modal = document.getElementById('tripPlannerModal');
  modal.style.display = 'flex';

  // Initialize the map only when modal opens
  if (!map) {
    map = L.map('map').setView([20.5937, 78.9629], 5); // Center India

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap contributors'
    }).addTo(map);

    // Click to set destination marker
    map.on('click', function(e) {
      setDestinationMarker(e.latlng.lat, e.latlng.lng);
    });
  } else {
    // Refresh map if it already exists
    map.invalidateSize();
  }

  // Set current location as start
  if (navigator.geolocation) {
    navigator.geolocation.getCurrentPosition(position => {
      const lat = position.coords.latitude;
      const lon = position.coords.longitude;
      document.getElementById('start_lat').value = lat;
      document.getElementById('start_lon').value = lon;

      setStartMarker(lat, lon);
      map.setView([lat, lon], 10);
    });
  }
}

// ---------------- CLOSE MODAL ----------------
function closeTripPlanner() {
  const modal = document.getElementById('tripPlannerModal');
  modal.style.display = 'none';
  clearTripForm();
  if (routeControl) {
    map.removeControl(routeControl);
    routeControl = null;
  }
}

// Close modal if clicked outside content
window.onclick = function(event) {
  const modal = document.getElementById('tripPlannerModal');
  if (event.target == modal) {
    closeTripPlanner();
  }
};

// ---------------- CLEAR FORM ----------------
function clearTripForm() {
  document.getElementById('trip_name').value = '';
  document.getElementById('destination').value = '';
  document.getElementById('start_location').value = '';
  document.getElementById('budget').value = '';
  document.getElementById('latitude').value = '';
  document.getElementById('longitude').value = '';
  if (destMarker) map.removeLayer(destMarker);
  destMarker = null;
}

// ---------------- ADD TRIP ----------------
async function addTrip() {
  const trip = {
    trip_name: document.getElementById("trip_name").value,
    destination: document.getElementById("destination").value,
    budget: document.getElementById("budget").value,
    latitude: document.getElementById("latitude").value,
    longitude: document.getElementById("longitude").value
  };

  if (!trip.trip_name || !trip.destination || !trip.latitude || !trip.longitude) {
    alert("Please fill Trip Name, Destination and select a location on map.");
    return;
  }

  const response = await fetch("/add-trip", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(trip)
  });
  const result = await response.json();
  alert(result.message);

  if (result.status === "success") {
    closeTripPlanner();
    loadTrips();
  }
}

// ---------------- LOAD TRIPS ----------------
async function loadTrips() {
  const response = await fetch("/get-trips");
  const data = await response.json();

  const tripList = document.getElementById("trips");
  tripList.innerHTML = "";

  if (data.status !== "success" || data.trips.length === 0) {
    tripList.innerHTML = "<li>No trips planned yet.</li>";
    return;
  }

  data.trips.forEach(trip => {
    const li = document.createElement("li");
    li.innerHTML = `<strong>${trip.trip_name}</strong> → ${trip.destination} <br>
                    <b>Budget:</b> ₹${trip.budget || 0}`;
    li.style.cursor = "pointer";
    li.onclick = () => {
      map.setView([trip.latitude, trip.longitude], 10);
      setDestinationMarker(trip.latitude, trip.longitude);
    };
    tripList.appendChild(li);
  });
}

// ---------------- SET MARKERS ----------------
function setStartMarker(lat, lon) {
  if (startMarker) map.removeLayer(startMarker);
  startMarker = L.marker([lat, lon], {
    icon: L.icon({
      iconUrl:'https://cdn-icons-png.flaticon.com/512/684/684908.png',
      iconSize:[30,30]
    })
  }).addTo(map);
  drawRoute();
}

function setDestinationMarker(lat, lon) {
  if (destMarker) map.removeLayer(destMarker);
  destMarker = L.marker([lat, lon], {
    icon: L.icon({
      iconUrl:'https://cdn-icons-png.flaticon.com/512/252/252025.png',
      iconSize:[30,30]
    })
  }).addTo(map);
  document.getElementById('latitude').value = lat;
  document.getElementById('longitude').value = lon;
  drawRoute();
}

// ---------------- FETCH SUGGESTIONS ----------------
async function fetchStartSuggestions() {
  const query = document.getElementById("start_location").value;
  if (query.length < 2) return;

  const res = await fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(query)}`);
  const data = await res.json();

  const suggestions = document.getElementById("start_suggestions");
  suggestions.innerHTML = "";

  data.forEach(loc => {
    const li = document.createElement("li");
    li.textContent = loc.display_name;
    li.onclick = () => {
      document.getElementById("start_location").value = loc.display_name;
      document.getElementById("start_lat").value = loc.lat;
      document.getElementById("start_lon").value = loc.lon;
      setStartMarker(loc.lat, loc.lon);
      suggestions.innerHTML = "";
    };
    suggestions.appendChild(li);
  });
}

async function fetchDestSuggestions() {
  const query = document.getElementById("destination").value;
  if (query.length < 2) return;

  const res = await fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(query)}`);
  const data = await res.json();

  const suggestions = document.getElementById("dest_suggestions");
  suggestions.innerHTML = "";

  data.forEach(loc => {
    const li = document.createElement("li");
    li.textContent = loc.display_name;
    li.onclick = () => {
      document.getElementById("destination").value = loc.display_name;
      document.getElementById("latitude").value = loc.lat;
      document.getElementById("longitude").value = loc.lon;
      setDestinationMarker(loc.lat, loc.lon);
      suggestions.innerHTML = "";
    };
    suggestions.appendChild(li);
  });
}

// ---------------- DEBOUNCE INPUTS ----------------
let startTimeout, destTimeout;

document.getElementById("start_location").addEventListener("input", () => {
  clearTimeout(startTimeout);
  startTimeout = setTimeout(fetchStartSuggestions, 300);
});

document.getElementById("destination").addEventListener("input", () => {
  clearTimeout(destTimeout);
  destTimeout = setTimeout(fetchDestSuggestions, 300);
});

// ---------------- DRAW ROUTE ----------------
function drawRoute() {
  const startLat = parseFloat(document.getElementById("start_lat").value);
  const startLon = parseFloat(document.getElementById("start_lon").value);
  const destLat = parseFloat(document.getElementById("latitude").value);
  const destLon = parseFloat(document.getElementById("longitude").value);

  if (!startLat || !startLon || !destLat || !destLon) return;

  if (routeControl) map.removeControl(routeControl);

  routeControl = L.Routing.control({
    waypoints: [
      L.latLng(startLat, startLon),
      L.latLng(destLat, destLon)
    ],
    routeWhileDragging: false,
    show: false,
    draggableWaypoints: false
  }).addTo(map);
}
// ------------------- TRIP PLANNER -------------------

function openTripPlanner() {
    document.getElementById("tripPlannerModal").style.display = "flex";
}

function closeTripPlanner() {
    document.getElementById("tripPlannerModal").style.display = "none";
}

// Add trip
async function addTrip() {
    const trip_name = document.getElementById("trip_name").value;
    const destination = document.getElementById("destination").value;
    const budget = document.getElementById("budget").value;
    const latitude = document.getElementById("latitude").value;
    const longitude = document.getElementById("longitude").value;

    if (!trip_name || !destination || !latitude || !longitude) {
        alert("Please fill in all required fields!");
        return;
    }

    const response = await fetch("/add-trip", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            trip_name,
            destination,
            budget,
            latitude,
            longitude
        })
    }).then(res => res.json());

    if (response.status === "success") {
        alert("Trip added successfully!");
        closeTripPlanner();
        openMyTripsModal(); // Open trips modal automatically
        loadMyTrips();      // Refresh trips list
    } else {
        alert(response.message || "Failed to add trip");
    }
}

// ------------------- MY TRIPS -------------------

let myTripsMap, myTripsMarkers = [];

// Open My Trips Modal
function openMyTripsModal() {
    document.getElementById("myTripsModal").style.display = "flex";
    loadMyTrips(); // Load trips when modal opens
}

// Close My Trips Modal
function closeMyTripsModal() {
    document.getElementById("myTripsModal").style.display = "none";
}

// Load trips from backend and show in list
async function loadMyTrips() {
    const response = await fetch("/get-trips");
    const data = await response.json();

    if (data.status !== "success") {
        alert(data.message || "Failed to load trips");
        return;
    }

    const tripsList = document.getElementById("myTripsList");
    tripsList.innerHTML = ""; // Clear previous list
    clearMapMarkers();

    data.trips.forEach(trip => {
        // Create list item
        const li = document.createElement("li");
        li.textContent = `${trip.trip_name} - ${trip.destination} (Budget: ${trip.budget || 0})`;
        li.style.cursor = "pointer";
        li.onclick = () => showTripOnMap(trip);
        tripsList.appendChild(li);

        // Add marker for map
        addMapMarker(trip);
    });

    initMyTripsMap();
}

// Initialize or refresh My Trips map
function initMyTripsMap() {
    if (!myTripsMap) {
        myTripsMap = L.map("myTripsMap").setView([20.5937, 78.9629], 5); // Center India
        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
            attribution: "&copy; OpenStreetMap contributors"
        }).addTo(myTripsMap);
    } else {
        myTripsMap.invalidateSize();
    }
}

// Add marker to My Trips map
function addMapMarker(trip) {
    if (!myTripsMap) return;
    const marker = L.marker([trip.latitude, trip.longitude]).addTo(myTripsMap)
        .bindPopup(`<b>${trip.trip_name}</b><br>${trip.destination}<br>Budget: ₹${trip.budget || 0}`);
    myTripsMarkers.push(marker);
}

// Clear markers from My Trips map
function clearMapMarkers() {
    if (!myTripsMarkers) return;
    myTripsMarkers.forEach(marker => myTripsMap.removeLayer(marker));
    myTripsMarkers = [];
}

// Show selected trip on My Trips map
function showTripOnMap(trip) {
    if (!myTripsMap) initMyTripsMap();
    myTripsMap.setView([trip.latitude, trip.longitude], 10);
}

// ------------------- EDIT TRIP -------------------

function closeEditPanel() {
    document.getElementById("editTripContainer").style.display = "none";
}

function openEditPanel(trip) {
    const container = document.getElementById("editTripContainer");
    container.style.display = "block";
    document.getElementById("edit_trip_id").value = trip.id;
    document.getElementById("edit_trip_name").value = trip.trip_name;
    document.getElementById("edit_destination").value = trip.destination;
    document.getElementById("edit_budget").value = trip.budget;
    document.getElementById("edit_latitude").value = trip.latitude;
    document.getElementById("edit_longitude").value = trip.longitude;

    // Optionally set markers and route on map
    if (trip.latitude && trip.longitude) {
        setDestinationMarker(trip.latitude, trip.longitude);
        const startLat = parseFloat(document.getElementById("start_lat").value);
        const startLon = parseFloat(document.getElementById("start_lon").value);
        if (startLat && startLon) drawRoute();
    }
}

async function saveTripEdits() {
    const trip_id = document.getElementById("edit_trip_id").value;
    const trip_name = document.getElementById("edit_trip_name").value;
    const destination = document.getElementById("edit_destination").value;
    const budget = document.getElementById("edit_budget").value;
    const latitude = document.getElementById("edit_latitude").value;
    const longitude = document.getElementById("edit_longitude").value;

    const response = await fetch("/update-trip", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ trip_id })({
            trip_id, trip_name, destination, budget, latitude, longitude
        })
    }).then(res => res.json());

    if (response.status === "success") {
        alert("Trip updated!");
        closeEditPanel();
        loadMyTrips();
        // Update route after editing
        if (latitude && longitude) setDestinationMarker(latitude, longitude);
        drawRoute();
    } else {
        alert(response.message || "Failed to update trip");
    }
}

// ------------------- DELETE TRIP -------------------
async function deleteTrip(trip_id) {
    if (!trip_id) return;

    if (!confirm("Are you sure you want to delete this trip?")) return;

    const response = await fetch("/delete-trip", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ trip_id })
    }).then(res => res.json());

    if (response.status === "success") {
        alert("Trip deleted!");
        loadMyTrips(); // Refresh trip list
        // Remove route and destination marker
        if (destMarker) {
            map.removeLayer(destMarker);
            destMarker = null;
        }
        if (routeControl) {
            map.removeControl(routeControl);
            routeControl = null;
        }
    } else {
        alert(response.message || "Failed to delete trip");
    }
}

// ------------------- LOAD MY TRIPS WITH EDIT & DELETE -------------------
async function loadMyTrips() {
    const response = await fetch("/get-trips");
    const data = await response.json();

    if (data.status !== "success") {
        alert(data.message || "Failed to load trips");
        return;
    }

    const tripsList = document.getElementById("myTripsList");
    tripsList.innerHTML = ""; // Clear previous list
    clearMapMarkers();         // Clear existing map markers

    data.trips.forEach(trip => {
        const li = document.createElement("li");
        li.style.display = "flex";
        li.style.justifyContent = "space-between";
        li.style.alignItems = "center";
        li.style.marginBottom = "6px";

        // Trip info (click to edit)
        const info = document.createElement("span");
        info.textContent = `${trip.trip_name} - ${trip.destination} (Budget: ${trip.budget || 0})`;
        info.style.cursor = "pointer";
        info.onclick = () => openEditPanel(trip);

        // Delete button
        const delBtn = document.createElement("button");
        delBtn.textContent = "Delete";
        delBtn.style.background = "#d9534f";
        delBtn.style.color = "#fff";
        delBtn.style.border = "none";
        delBtn.style.borderRadius = "6px";
        delBtn.style.padding = "4px 8px";
        delBtn.style.cursor = "pointer";
        delBtn.onclick = async (e) => {
            e.stopPropagation(); // prevent opening edit panel
            if (!confirm("Are you sure you want to delete this trip?")) return;

            const res = await fetch("/delete-trip", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ trip_id: trip.id })
            }).then(res => res.json());

            if (res.status === "success") {
                alert("Trip deleted!");
                loadMyTrips(); // Refresh list and markers
            } else {
                alert(res.message || "Failed to delete trip");
            }
        };

        li.appendChild(info);
        li.appendChild(delBtn);
        tripsList.appendChild(li);

        // Add marker for map
        addMapMarker(trip);
    });

    initMyTripsMap();
}
