/**
 * Authentication Script
 * Handles signup and login form submissions.
 */

document.addEventListener("DOMContentLoaded", () => {
    const loginForm = document.getElementById('loginForm');
    const signupForm = document.getElementById('signupForm');

    if (loginForm) {
        loginForm.addEventListener('submit', handleLogin);
    }

    if (signupForm) {
        signupForm.addEventListener('submit', handleSignup);
        const passInput = document.getElementById('password');
        if(passInput) {
            passInput.addEventListener('input', window.checkStrength);
        }
    }
});

/**
 * Handles the login form submission
 */
async function handleLogin(e) {
    e.preventDefault();
    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;
    const rememberCheckbox = document.getElementById('remember');
    const remember = rememberCheckbox ? rememberCheckbox.checked : false;
    
    const messageEl = document.getElementById('message');
    const btnText = document.getElementById('loginBtnText');
    const loader = document.getElementById('loginLoader');

    if (!messageEl) return;
    
    // UI Loading State
    if(btnText) btnText.style.display = 'none';
    if(loader) loader.style.display = 'inline-block';

    const data = { email, password, remember };

    try {
        const response = await fetch('/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data),
        });

        const result = await response.json();

        if (result.status === 'success') {
            showMessage(messageEl, 'Login successful! Redirecting...', 'success');
            window.location.href = result.redirect;
        } else {
            showMessage(messageEl, result.message, 'error');
            if(btnText) btnText.style.display = 'inline-block';
            if(loader) loader.style.display = 'none';
        }
    } catch (error) {
        showMessage(messageEl, 'An error occurred. Please try again.', 'error');
        if(btnText) btnText.style.display = 'inline-block';
        if(loader) loader.style.display = 'none';
    }
}

/**
 * Handles the signup form submission
 */
async function handleSignup(e) {
    e.preventDefault();
    const name = document.getElementById('name').value;
    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;
    const messageEl = document.getElementById('message');
    const btnText = document.getElementById('signupBtnText');
    const loader = document.getElementById('signupLoader');

    if (!messageEl) return;
    
    if (password.length < 6) {
        showMessage(messageEl, 'Error: Password must be at least 6 characters.', 'error');
        return;
    }
    
    // UI Loading State
    if(btnText) btnText.style.display = 'none';
    if(loader) loader.style.display = 'inline-block';

    const data = { name, email, password };

    try {
        const response = await fetch('/signup', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data),
        });

        const result = await response.json();

        if (result.status === 'success') {
            showMessage(messageEl, 'Signup successful! Redirecting to login...', 'success');
            setTimeout(() => {
                window.location.href = result.redirect;
            }, 2000);
        } else {
            showMessage(messageEl, result.message, 'error');
            if(btnText) btnText.style.display = 'inline-block';
            if(loader) loader.style.display = 'none';
        }
    } catch (error) {
        showMessage(messageEl, 'An error occurred. Please try again.', 'error');
        if(btnText) btnText.style.display = 'inline-block';
        if(loader) loader.style.display = 'none';
    }
}

// Global scope required for inline HTML onkeyup
window.checkStrength = function() {
    const val = document.getElementById('password').value;
    const meter = document.getElementById('password-strength-bar');
    const txt = document.getElementById('password-feedback');
    if(!meter) return;
    
    if (val.length === 0) {
        meter.style.width = '0%';
        txt.innerHTML = '';
        return;
    }
    
    let strength = 0;
    if (val.length > 5) strength += 20;
    if (val.length > 8) strength += 20;
    if (/[A-Z]/.test(val)) strength += 20;
    if (/[0-9]/.test(val)) strength += 20;
    if (/[^A-Za-z0-9]/.test(val)) strength += 20;

    meter.style.width = strength + '%';
    
    if (strength < 40) {
        meter.style.background = '#ef4444'; // Red
        txt.innerHTML = 'Weak (add numbers/symbols)';
        txt.style.color = '#ef4444';
    } else if (strength < 80) {
        meter.style.background = '#f59e0b'; // Yellow
        txt.innerHTML = 'Moderate (add uppercase/special chars)';
        txt.style.color = '#f59e0b';
    } else {
        meter.style.background = '#10b981'; // Green
        txt.innerHTML = 'Strong password ✅';
        txt.style.color = '#10b981';
    }
};

/**
 * Utility to show messages on the auth forms
 */
function showMessage(element, message, type) {
    if (!element) return;
    element.textContent = message;
    element.className = `form-message ${type}`;
    element.style.display = 'block';
}