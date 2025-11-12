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
    }
});

/**
 * Handles the login form submission
 */
async function handleLogin(e) {
    e.preventDefault();
    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;
    const messageEl = document.getElementById('message'); // Get the message p tag

    if (!messageEl) {
        console.error('Message element not found');
        return;
    }

    const data = { email, password };

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
        }
    } catch (error) {
        showMessage(messageEl, 'An error occurred. Please try again.', 'error');
        console.error('Login error:', error);
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
    const messageEl = document.getElementById('message'); // Get the message p tag

    if (!messageEl) {
        console.error('Message element not found');
        return;
    }

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
        }
    } catch (error) {
        showMessage(messageEl, 'An error occurred. Please try again.', 'error');
        console.error('Signup error:', error);
    }
}

/**
 * Utility to show messages on the auth forms
 */
function showMessage(element, message, type) {
    if (!element) return;
    element.textContent = message;
    element.className = `form-message ${type}`;
    element.style.display = 'block';
}