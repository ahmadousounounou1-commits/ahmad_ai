/* ==========================================================
   common.js : code partagé par toutes les pages
   - thème clair / sombre
   - menu sur téléphone
   - fonction api() pour parler au serveur
   - petites notifications (toast)
   ========================================================== */
(function () {
  "use strict";

  /* ---------- Thème ---------- */
  var THEME_KEY = "ahmad_theme";
  var themeButton = document.getElementById("theme-toggle");

  function savedTheme() {
    try { return localStorage.getItem(THEME_KEY) || "system"; } catch (e) { return "system"; }
  }

  function isDark(choice) {
    if (choice === "dark") return true;
    if (choice === "light") return false;
    return !!(window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches);
  }

  function applyTheme(choice) {
    var dark = isDark(choice);
    document.documentElement.setAttribute("data-theme", dark ? "dark" : "light");
    if (themeButton) themeButton.textContent = dark ? "☀️" : "🌙";
  }

  function setTheme(choice) {
    try { localStorage.setItem(THEME_KEY, choice); } catch (e) { /* stockage bloqué : on ignore */ }
    applyTheme(choice);
  }

  applyTheme(savedTheme());

  if (themeButton) {
    themeButton.addEventListener("click", function () {
      var dark = document.documentElement.getAttribute("data-theme") === "dark";
      setTheme(dark ? "light" : "dark");
      var select = document.getElementById("theme-select");
      if (select) select.value = dark ? "light" : "dark";
    });
  }

  // Si le choix est "automatique", on suit les changements de l'appareil.
  if (window.matchMedia) {
    var media = window.matchMedia("(prefers-color-scheme: dark)");
    var onChange = function () { if (savedTheme() === "system") applyTheme("system"); };
    if (media.addEventListener) media.addEventListener("change", onChange);
  }

  /* ---------- Menu mobile ---------- */
  var navToggle = document.getElementById("nav-toggle");
  var navLinks = document.getElementById("nav-links");
  if (navToggle && navLinks) {
    navToggle.addEventListener("click", function () {
      var open = navLinks.classList.toggle("open");
      navToggle.setAttribute("aria-expanded", open ? "true" : "false");
    });
  }

  /* ---------- Notifications ---------- */
  function toast(message, type) {
    var container = document.getElementById("toast-container");
    if (!container) return;
    var el = document.createElement("div");
    el.className = "toast" + (type === "error" ? " error" : "");
    el.textContent = message;
    container.appendChild(el);
    setTimeout(function () { el.remove(); }, 3500);
  }

  /* ---------- Appels au serveur ---------- */
  // api("/api/chat", { method: "POST", body: { message: "Salut" } })
  async function api(path, options) {
    var opts = Object.assign({ method: "GET", headers: {} }, options || {});
    if (opts.body !== undefined && typeof opts.body !== "string") {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(opts.body);
    }

    var response;
    try {
      response = await fetch(path, opts);
    } catch (e) {
      throw new Error("Impossible de joindre le serveur. Vérifie ta connexion.");
    }

    var data = {};
    try { data = await response.json(); } catch (e) { /* réponse sans JSON */ }

    if (!response.ok) {
      throw new Error(data.error || "Erreur " + response.status);
    }
    return data;
  }

  // On expose ces outils aux autres fichiers JavaScript.
  window.AhmadAI = { api: api, toast: toast, setTheme: setTheme, savedTheme: savedTheme };
})();
