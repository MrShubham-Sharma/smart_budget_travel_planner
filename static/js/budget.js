/**
 * 💰 UPDATED SMART BUDGET CALCULATOR (No KM)
 * Logic: (Daily Rate based on Style * Days) * Number of People
 */

window.calculateSmartBudget = function() {
    // 1. Get Inputs from your HTML
    const travelerType = document.querySelector('input[name="travelerType"]:checked')?.value; // 'solo' or 'group'
    const travelStyle = document.querySelector('input[name="travelStyle"]:checked')?.value; // 'budget', 'mid', 'luxury'
    const numPeopleInput = document.getElementById('numPeople'); // Your "How many?" input
    const numDays = 5; // Default trip duration or pull from an input if you have one

    // 2. Validation
    let numPeople = parseInt(numPeopleInput.value) || 1;
    if (travelerType === 'solo') numPeople = 1; // Force 1 if solo is selected

    // 3. Define Rates (Per Person, Per Day)
    const rates = {
        'budget': 1500,  // Cheap hostels, street food
        'mid-range': 4000, // Hotels, nice cafes
        'luxury': 10000   // Resorts, fine dining
    };

    // 4. Calculate Logic
    const dailyRate = rates[travelStyle] || 4000;
    const totalEstimate = dailyRate * numDays * numPeople;

    // 5. Update UI
    const estimateDisplay = document.getElementById('estimatedBudgetDisplay'); // Your (₹) input field
    if (estimateDisplay) {
        estimateDisplay.value = totalEstimate;
    }

    // 6. Alert Summary (Matches your screenshot style)
    alert(
        `Smart Budget Calculated:\n\n` +
        `Traveler Type: ${travelerType} (${numPeople} person/s)\n` +
        `Style: ${travelStyle}\n` +
        `--------------------------\n` +
        `Total Estimated Cost: ₹${totalEstimate}\n` +
        `(${numDays} days * ₹${dailyRate}/day * ${numPeople} person/s)`
    );

    // Automatically set this as your "Total Budget" in the tracker
    window.budgetState.total = totalEstimate;
    if (typeof updateBudgetUI === "function") {
        updateBudgetUI();
    }
};