/* ==========================================================
   chat.js : le fonctionnement de la page de discussion
   ========================================================== */
(function () {
  "use strict";

  var api = window.AhmadAI.api;

  var els = {
    messages: document.getElementById("messages"),
    welcome: document.getElementById("welcome"),
    form: document.getElementById("chat-form"),
    input: document.getElementById("message-input"),
    sendBtn: document.getElementById("send-btn"),
    list: document.getElementById("conversation-list"),
    historyEmpty: document.getElementById("history-empty"),
    sidebar: document.getElementById("sidebar"),
    overlay: document.getElementById("overlay"),
    banner: document.getElementById("status-banner")
  };

  var currentId = null;   // identifiant de la conversation ouverte (null = nouvelle)
  var sending = false;    // vrai pendant qu'on attend la réponse de l'IA

  /* ---------- Outils d'affichage ---------- */

  // Empêche le texte d'être interprété comme du HTML (sécurité contre l'injection de code).
  function escapeHtml(text) {
    return text
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  // Met en forme la réponse de l'IA : blocs de code, `code`, **gras**, retours à la ligne.
  // Le texte est d'abord "échappé", donc aucun HTML venant de l'IA ne peut s'exécuter.
  function formatText(raw) {
    return raw.split("```").map(function (part, i) {
      if (i % 2 === 1) {
        var code = part.replace(/^[a-zA-Z0-9_+-]*\n/, "").replace(/\n$/, "");
        return "<pre><code>" + escapeHtml(code) + "</code></pre>";
      }
      var t = escapeHtml(part);
      t = t.replace(/`([^`\n]+)`/g, "<code>$1</code>");
      t = t.replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>");
      return t.replace(/\n/g, "<br>");
    }).join("");
  }

  function scrollToBottom() {
    els.messages.scrollTop = els.messages.scrollHeight;
  }

  function hideWelcome() {
    if (els.welcome) { els.welcome.remove(); els.welcome = null; }
  }

  function showWelcome() {
    els.messages.innerHTML = "";
    // Le message d'accueil est recréé à partir de la copie gardée au démarrage
    els.messages.appendChild(welcomeClone.cloneNode(true));
    els.welcome = els.messages.querySelector(".welcome");
    bindChips();
  }

  function addMessage(role, text, options) {
    options = options || {};
    hideWelcome();

    var row = document.createElement("div");
    row.className = "msg " + role + (options.error ? " error" : "");

    var avatar = document.createElement("div");
    avatar.className = "avatar";
    avatar.textContent = role === "user" ? "🙂" : "🧠";

    var bubble = document.createElement("div");
    bubble.className = "bubble";
    if (role === "assistant" && !options.error) {
      bubble.innerHTML = formatText(text);
    } else {
      bubble.textContent = text;
    }

    row.appendChild(avatar);
    row.appendChild(bubble);
    els.messages.appendChild(row);
    scrollToBottom();
    return row;
  }

  function addTyping() {
    hideWelcome();
    var row = document.createElement("div");
    row.className = "msg assistant";
    row.innerHTML =
      '<div class="avatar">🧠</div>' +
      '<div class="bubble"><span class="typing"><span></span><span></span><span></span></span></div>';
    els.messages.appendChild(row);
    scrollToBottom();
    return row;
  }

  function addMemoryNote(fact) {
    var note = document.createElement("div");
    note.className = "memory-note";
    note.textContent = "🧠 Mémorisé : " + fact;
    els.messages.appendChild(note);
    scrollToBottom();
  }

  function setSending(value) {
    sending = value;
    els.sendBtn.disabled = value;
    els.sendBtn.textContent = value ? "…" : "Envoyer";
  }

  function autoResize() {
    els.input.style.height = "auto";
    els.input.style.height = Math.min(els.input.scrollHeight, 160) + "px";
  }

  /* ---------- Barre latérale (historique) ---------- */

  function openSidebar() { els.sidebar.classList.add("open"); els.overlay.hidden = false; }
  function closeSidebar() { els.sidebar.classList.remove("open"); els.overlay.hidden = true; }

  function updateUrl() {
    var url = currentId ? "/chat?c=" + currentId : "/chat";
    window.history.replaceState(null, "", url);
  }

  function renderConversations(conversations) {
    els.list.innerHTML = "";
    els.historyEmpty.hidden = conversations.length > 0;

    conversations.forEach(function (c) {
      var li = document.createElement("li");
      li.className = "conversation-item" + (c.id === currentId ? " active" : "");

      var open = document.createElement("button");
      open.type = "button";
      open.className = "conversation-open";
      open.textContent = c.title;
      open.title = c.title;
      open.addEventListener("click", function () { openConversation(c.id); });

      var del = document.createElement("button");
      del.type = "button";
      del.className = "conversation-delete";
      del.setAttribute("aria-label", "Supprimer la conversation");
      del.textContent = "🗑";
      del.addEventListener("click", function () { deleteConversation(c.id); });

      li.appendChild(open);
      li.appendChild(del);
      els.list.appendChild(li);
    });
  }

  async function loadConversations() {
    try {
      var data = await api("/api/conversations");
      renderConversations(data.conversations);
    } catch (err) {
      window.AhmadAI.toast(err.message, "error");
    }
  }

  async function openConversation(id) {
    try {
      var data = await api("/api/conversations/" + id);
      currentId = id;
      els.messages.innerHTML = "";
      els.welcome = null;
      data.messages.forEach(function (m) { addMessage(m.role, m.content); });
      updateUrl();
      closeSidebar();
      loadConversations();
    } catch (err) {
      window.AhmadAI.toast(err.message, "error");
      newConversation();
    }
  }

  async function deleteConversation(id) {
    if (!window.confirm("Supprimer cette conversation ?")) return;
    try {
      await api("/api/conversations/" + id, { method: "DELETE" });
      if (id === currentId) newConversation();
      loadConversations();
    } catch (err) {
      window.AhmadAI.toast(err.message, "error");
    }
  }

  function newConversation() {
    currentId = null;
    updateUrl();
    showWelcome();
    closeSidebar();
    loadConversations();
    els.input.focus();
  }

  /* ---------- Envoi d'un message ---------- */

  async function sendMessage(text) {
    text = text.trim();
    if (!text || sending) return;

    setSending(true);
    var userRow = addMessage("user", text);
    els.input.value = "";
    autoResize();
    var typing = addTyping();

    try {
      var data = await api("/api/chat", {
        method: "POST",
        body: { message: text, conversation_id: currentId }
      });
      typing.remove();
      addMessage("assistant", data.reply);
      if (data.memory_saved) addMemoryNote(data.memory_saved);
      currentId = data.conversation_id;
      updateUrl();
      loadConversations();
    } catch (err) {
      typing.remove();
      userRow.remove();                 // on retire le message non envoyé...
      addMessage("assistant", err.message, { error: true });
      els.input.value = text;           // ...et on le remet dans la zone de saisie
      autoResize();
    } finally {
      setSending(false);
      els.input.focus();
    }
  }

  /* ---------- Événements ---------- */

  els.form.addEventListener("submit", function (event) {
    event.preventDefault();
    sendMessage(els.input.value);
  });

  els.input.addEventListener("input", autoResize);

  // Entrée = envoyer, Maj+Entrée = nouvelle ligne. Sur téléphone, Entrée = nouvelle ligne.
  els.input.addEventListener("keydown", function (event) {
    var touchDevice = window.matchMedia && window.matchMedia("(pointer: coarse)").matches;
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing && !touchDevice) {
      event.preventDefault();
      sendMessage(els.input.value);
    }
  });

  function bindChips() {
    document.querySelectorAll(".chip").forEach(function (chip) {
      chip.addEventListener("click", function () { sendMessage(chip.textContent); });
    });
  }

  document.getElementById("new-chat-btn").addEventListener("click", newConversation);
  document.getElementById("new-chat-top").addEventListener("click", newConversation);
  document.getElementById("sidebar-toggle").addEventListener("click", openSidebar);
  els.overlay.addEventListener("click", closeSidebar);

  /* ---------- Démarrage ---------- */

  // On garde une copie du message d'accueil pour pouvoir le réafficher.
  var welcomeClone = els.welcome.cloneNode(true);
  bindChips();

  (async function start() {
    try {
      var status = await api("/api/status");
      if (status.provider === "local") {
        els.banner.innerHTML =
          "⚠️ <strong>Mode local</strong> : je suis un petit assistant à règles, pas une vraie IA. " +
          'Pour activer une IA externe, voir la page <a href="/about">À propos</a> et le README.';
        els.banner.hidden = false;
      }
    } catch (err) { /* le bandeau est facultatif */ }

    await loadConversations();

    var wanted = parseInt(new URLSearchParams(window.location.search).get("c"), 10);
    if (wanted) openConversation(wanted);
  })();
})();
