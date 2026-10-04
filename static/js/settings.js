/* ==========================================================
   settings.js : la page Paramètres
   ========================================================== */
(function () {
  "use strict";

  var api = window.AhmadAI.api;
  var toast = window.AhmadAI.toast;

  var themeSelect = document.getElementById("theme-select");
  var nameInput = document.getElementById("display-name");
  var styleSelect = document.getElementById("response-style");
  var memoryEnabled = document.getElementById("memory-enabled");
  var customInput = document.getElementById("custom-instructions");
  var memoryList = document.getElementById("memory-list");
  var memoryEmpty = document.getElementById("memory-empty");
  var memoryInput = document.getElementById("memory-input");
  var techInfo = document.getElementById("tech-info");

  /* ---------- Thème (gardé dans le navigateur) ---------- */
  themeSelect.value = window.AhmadAI.savedTheme();
  themeSelect.addEventListener("change", function () {
    window.AhmadAI.setTheme(themeSelect.value);
  });

  /* ---------- Profil et réponses (gardés sur le serveur) ---------- */
  async function loadSettings() {
    try {
      var s = await api("/api/settings");
      nameInput.value = s.display_name;
      styleSelect.value = s.response_style;
      memoryEnabled.checked = s.memory_enabled;
      customInput.value = s.custom_instructions;
    } catch (err) {
      toast(err.message, "error");
    }
  }

  document.getElementById("save-settings").addEventListener("click", async function () {
    try {
      await api("/api/settings", {
        method: "PUT",
        body: {
          display_name: nameInput.value,
          response_style: styleSelect.value,
          memory_enabled: memoryEnabled.checked,
          custom_instructions: customInput.value
        }
      });
      toast("Paramètres enregistrés ✅");
    } catch (err) {
      toast(err.message, "error");
    }
  });

  /* ---------- Mémoire ---------- */
  function renderMemories(memories) {
    memoryList.innerHTML = "";
    memoryEmpty.hidden = memories.length > 0;

    memories.forEach(function (m) {
      var li = document.createElement("li");
      var span = document.createElement("span");
      span.textContent = m.content;   // textContent : pas d'injection de HTML

      var del = document.createElement("button");
      del.type = "button";
      del.setAttribute("aria-label", "Supprimer ce souvenir");
      del.textContent = "✕";
      del.addEventListener("click", async function () {
        try {
          await api("/api/memories/" + m.id, { method: "DELETE" });
          loadMemories();
        } catch (err) {
          toast(err.message, "error");
        }
      });

      li.appendChild(span);
      li.appendChild(del);
      memoryList.appendChild(li);
    });
  }

  async function loadMemories() {
    try {
      var data = await api("/api/memories");
      renderMemories(data.memories);
    } catch (err) {
      toast(err.message, "error");
    }
  }

  document.getElementById("memory-add").addEventListener("click", async function () {
    var content = memoryInput.value.trim();
    if (!content) return;
    try {
      var result = await api("/api/memories", { method: "POST", body: { content: content } });
      memoryInput.value = "";
      toast(result.status === "exists" ? "Ce souvenir existe déjà." : "Souvenir ajouté ✅");
      loadMemories();
    } catch (err) {
      toast(err.message, "error");
    }
  });

  memoryInput.addEventListener("keydown", function (event) {
    if (event.key === "Enter") {
      event.preventDefault();
      document.getElementById("memory-add").click();
    }
  });

  document.getElementById("memory-clear").addEventListener("click", async function () {
    if (!window.confirm("Effacer toute la mémoire ?")) return;
    try {
      await api("/api/memories", { method: "DELETE" });
      loadMemories();
      toast("Mémoire effacée");
    } catch (err) {
      toast(err.message, "error");
    }
  });

  /* ---------- Données ---------- */
  document.getElementById("delete-conversations").addEventListener("click", async function () {
    if (!window.confirm("Supprimer TOUTES tes conversations ? Cette action est définitive.")) return;
    try {
      await api("/api/conversations", { method: "DELETE" });
      toast("Conversations supprimées");
    } catch (err) {
      toast(err.message, "error");
    }
  });

  /* ---------- Informations techniques ---------- */
  async function loadStatus() {
    try {
      var s = await api("/api/status");
      techInfo.textContent = s.provider === "local"
        ? "Mode local (assistant à règles, sans IA externe)."
        : "IA externe connectée : modèle « " + s.model + " ».";
    } catch (err) {
      techInfo.textContent = "État indisponible.";
    }
  }

  loadSettings();
  loadMemories();
  loadStatus();
})();
