/* ==========================================================
   contact.js : envoi du formulaire de contact
   ========================================================== */
(function () {
  "use strict";

  var api = window.AhmadAI.api;
  var form = document.getElementById("contact-form");
  var button = document.getElementById("contact-submit");
  var feedback = document.getElementById("contact-feedback");

  function show(message, kind) {
    feedback.textContent = message;
    feedback.className = "feedback " + kind;
  }

  form.addEventListener("submit", async function (event) {
    event.preventDefault();
    show("", "");
    button.disabled = true;

    try {
      await api("/api/contact", {
        method: "POST",
        body: {
          name: form.elements.name.value,
          email: form.elements.email.value,
          message: form.elements.message.value,
          website: form.elements.website.value
        }
      });
      form.reset();
      show("Merci ! Ton message a bien été envoyé.", "ok");
    } catch (err) {
      show(err.message, "error");
    } finally {
      button.disabled = false;
    }
  });
})();
