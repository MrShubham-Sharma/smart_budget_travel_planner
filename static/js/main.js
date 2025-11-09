document.addEventListener("DOMContentLoaded", () => {

  // ------------------ LOGIN FORM ------------------
  const loginForm = document.getElementById('loginForm');
  if (loginForm) {
    loginForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const email = document.getElementById('email').value;
      const password = document.getElementById('password').value;
      const messageEl = document.getElementById('message');

      try {
        const res = await fetch('/login', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({email, password})
        });
        const data = await res.json();
        if(data.status === 'success'){
          window.location.href = data.redirect;
        } else {
          messageEl.innerText = data.message;
        }
      } catch(err) {
        messageEl.innerText = "Server Error!";
      }
    });
  }

  // ------------------ SIGNUP FORM ------------------
  const signupForm = document.getElementById('signupForm');
  if (signupForm) {
    signupForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const name = document.getElementById('name').value;
      const email = document.getElementById('email').value;
      const password = document.getElementById('password').value;
      const messageEl = document.getElementById('message');

      try {
        const res = await fetch('/signup', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({name, email, password})
        });
        const data = await res.json();
        if(data.status === 'success'){
          window.location.href = data.redirect;
        } else {
          messageEl.innerText = data.message;
        }
      } catch(err) {
        messageEl.innerText = "Server Error!";
      }
    });
  }

});
