/**
 * main.js — Vanilla JavaScript for MediBook
 *
 * Features:
 *  - Confirmation dialogs before destructive actions
 *  - Auto-dismiss flash messages after 5 seconds
 *  - Mobile nav toggle
 *  - Client-side password match validation on register
 *  - Slot selection feedback
 */

document.addEventListener("DOMContentLoaded", function () {

  /* ── Mobile navigation toggle ──────────────────────────────── */
  var menuToggle = document.getElementById("menu-toggle");
  var navMenu    = document.getElementById("nav-menu");

  if (menuToggle && navMenu) {
    menuToggle.addEventListener("click", function () {
      navMenu.classList.toggle("open");
    });

    // Close nav when clicking outside
    document.addEventListener("click", function (e) {
      if (!menuToggle.contains(e.target) && !navMenu.contains(e.target)) {
        navMenu.classList.remove("open");
      }
    });
  }


  /* ── Confirmation dialogs ───────────────────────────────────── */
  // Usage in HTML: <form data-confirm="Are you sure?"> ... </form>
  document.querySelectorAll("form[data-confirm]").forEach(function (form) {
    form.addEventListener("submit", function (e) {
      var message = form.getAttribute("data-confirm");
      if (!confirm(message)) {
        e.preventDefault();
      }
    });
  });

  // Usage on buttons/links: <button data-confirm-btn="Are you sure?">
  document.querySelectorAll("[data-confirm-btn]").forEach(function (el) {
    el.addEventListener("click", function (e) {
      var message = el.getAttribute("data-confirm-btn");
      if (!confirm(message)) {
        e.preventDefault();
      }
    });
  });


  /* ── Auto-dismiss flash messages after 5 s ──────────────────── */
  var alerts = document.querySelectorAll(".alert");
  if (alerts.length) {
    setTimeout(function () {
      alerts.forEach(function (alert) {
        alert.style.transition = "opacity 0.5s ease";
        alert.style.opacity    = "0";
        setTimeout(function () {
          if (alert.parentNode) alert.parentNode.removeChild(alert);
        }, 500);
      });
    }, 5000);
  }


  /* ── Register form: password match validation ───────────────── */
  var registerForm = document.getElementById("register-form");
  if (registerForm) {
    registerForm.addEventListener("submit", function (e) {
      var password = document.getElementById("password");
      var confirm  = document.getElementById("confirm_password");

      if (!password || !confirm) return;

      if (password.value.length < 6) {
        e.preventDefault();
        showError(password, "Password must be at least 6 characters.");
        return;
      }

      if (password.value !== confirm.value) {
        e.preventDefault();
        showError(confirm, "Passwords do not match.");
        return;
      }
    });
  }


  /* ── Slot selection: highlight chosen slot ──────────────────── */
  document.querySelectorAll(".slot-radio").forEach(function (radio) {
    radio.addEventListener("change", function () {
      // Remove highlight from all labels
      document.querySelectorAll(".slot-label").forEach(function (lbl) {
        lbl.style.fontWeight = "";
      });
      // Highlight the selected one
      var label = document.querySelector('label[for="' + radio.id + '"]');
      if (label) label.style.fontWeight = "700";
    });
  });


  /* ── Book appointment: require slot selection before submit ──── */
  var bookForm = document.getElementById("book-form");
  if (bookForm) {
    bookForm.addEventListener("submit", function (e) {
      var selected = bookForm.querySelector(".slot-radio:checked");
      if (!selected) {
        e.preventDefault();
        alert("Please select a time slot before booking.");
      }
    });
  }


  /* ── Helper: show inline error under an input ───────────────── */
  function showError(input, message) {
    // Remove any existing error for this input
    var existing = input.parentNode.querySelector(".inline-error");
    if (existing) existing.parentNode.removeChild(existing);

    var span = document.createElement("span");
    span.className   = "inline-error form-hint";
    span.style.color = "#dc2626";
    span.textContent = message;
    input.parentNode.appendChild(span);
    input.focus();

    // Auto-remove after 4 seconds
    setTimeout(function () {
      if (span.parentNode) span.parentNode.removeChild(span);
    }, 4000);
  }

});
