"""
app.py : le point d'entrée de l'application AHMAD AI.

Il fait deux choses :
1. Afficher les PAGES du site (accueil, chat, à propos, contact, paramètres).
2. Répondre à l'API que le JavaScript du navigateur appelle
   (envoyer un message, lire l'historique, gérer la mémoire, etc.).

La clé API de l'IA reste ici, côté serveur. Le navigateur ne la voit jamais.

Lancer en local :   python app.py
En production :     gunicorn app:app
"""
import re
import secrets
from datetime import datetime

import click
from flask import Flask, g, jsonify, render_template, request
from werkzeug.middleware.proxy_fix import ProxyFix

import database as db
import memory as mem
from ai_providers import ProviderError, build_provider
from chatbot import ChatError, handle_message
from config import Config
from rate_limit import RateLimiter

OWNER_COOKIE = "ahmad_uid"
OWNER_PATTERN = re.compile(r"^[0-9a-f]{32}$")
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
RESPONSE_STYLES = ("short", "normal", "detailed")


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    app.config["MAX_CONTENT_LENGTH"] = 64 * 1024  # refuse les requêtes de plus de 64 Ko
    # Mise en cache des fichiers statiques (CSS/JS) par le navigateur : accélère les visites suivantes.
    # 0 en débogage (pour voir tes changements immédiatement), 1 jour en production.
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0 if Config.DEBUG else 86400

    # Derrière le proxy d'un hébergeur, on doit lui faire confiance pour connaître la vraie IP.
    if Config.TRUST_PROXY:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    db.init_app(app)
    provider = build_provider(Config)  # peut lever ProviderError (message clair au démarrage)
    chat_limiter = RateLimiter(Config.RATE_LIMIT_PER_HOUR, 3600)
    contact_limiter = RateLimiter(5, 3600)

    # ------------------------------------------------------------------
    # Identification du visiteur (cookie anonyme)
    # ------------------------------------------------------------------
    @app.before_request
    def identify_owner():
        uid = request.cookies.get(OWNER_COOKIE, "")
        if OWNER_PATTERN.match(uid):
            g.owner_id, g.new_owner = uid, False
        else:
            g.owner_id, g.new_owner = secrets.token_hex(16), True

    @app.after_request
    def finish_response(response):
        if g.get("new_owner") and request.endpoint != "static":
            response.set_cookie(
                OWNER_COOKIE, g.owner_id,
                max_age=60 * 60 * 24 * 365, httponly=True, samesite="Lax",
                secure=request.is_secure,
            )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        if request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.context_processor
    def inject_globals():
        return {
            "creator_name": Config.CREATOR_NAME,
            "contact_email": Config.CONTACT_EMAIL,
            "contact_whatsapp": re.sub(r"\D", "", Config.CONTACT_WHATSAPP),
            "current_year": datetime.now().year,
        }

    # ------------------------------------------------------------------
    # Outils pour l'API
    # ------------------------------------------------------------------
    def json_error(message, status=400):
        return jsonify({"error": message}), status

    def json_body():
        data = request.get_json(silent=True)  # None si ce n'est pas du JSON
        return data if isinstance(data, dict) else {}

    # ------------------------------------------------------------------
    # PAGES
    # ------------------------------------------------------------------
    @app.route("/")
    def home():
        return render_template("index.html", page="home")

    @app.route("/chat")
    def chat():
        return render_template("chat.html", page="chat")

    @app.route("/about")
    def about():
        return render_template("about.html", page="about")

    @app.route("/contact")
    def contact():
        return render_template("contact.html", page="contact")

    @app.route("/settings")
    def settings_page():
        return render_template("settings.html", page="settings")

    # Vérification de vie : utilisée par l'hébergeur pour savoir que le serveur répond.
    @app.get("/healthz")
    def healthz():
        return jsonify({"ok": True}), 200

    @app.errorhandler(404)
    def not_found(_error):
        if request.path.startswith("/api/"):
            return json_error("Ressource introuvable.", 404)
        return render_template("404.html", page=""), 404

    @app.errorhandler(413)
    def too_large(_error):
        return json_error("Requête trop volumineuse.", 413)

    # ------------------------------------------------------------------
    # API : état
    # ------------------------------------------------------------------
    @app.get("/api/status")
    def api_status():
        return jsonify({
            "provider": provider.name,
            "model": provider.label,
            "max_message_length": Config.MAX_MESSAGE_LENGTH,
        })

    # ------------------------------------------------------------------
    # API : chat
    # ------------------------------------------------------------------
    @app.post("/api/chat")
    def api_chat():
        if not chat_limiter.allow(request.remote_addr):
            return json_error("Trop de messages envoyés. Réessaie dans un moment.", 429)

        data = json_body()
        message = data.get("message")
        conversation_id = data.get("conversation_id")
        if not isinstance(message, str):
            return json_error("Le message est manquant.")
        if conversation_id is not None and (
            not isinstance(conversation_id, int) or isinstance(conversation_id, bool)
        ):
            return json_error("Identifiant de conversation invalide.")

        try:
            result = handle_message(provider, Config, g.owner_id, conversation_id, message)
        except ChatError as exc:
            return json_error(str(exc), exc.status)
        except ProviderError as exc:
            return json_error(str(exc), 502)
        except Exception:  # erreur inattendue : on la garde dans les logs, pas dans la réponse
            app.logger.exception("Erreur inattendue dans /api/chat")
            return json_error("Erreur interne du serveur.", 500)
        return jsonify(result)

    # ------------------------------------------------------------------
    # API : historique des conversations
    # ------------------------------------------------------------------
    @app.get("/api/conversations")
    def api_list_conversations():
        return jsonify({"conversations": db.list_conversations(g.owner_id)})

    @app.get("/api/conversations/<int:conversation_id>")
    def api_get_conversation(conversation_id):
        conversation = db.get_conversation(g.owner_id, conversation_id)
        if conversation is None:
            return json_error("Conversation introuvable.", 404)
        return jsonify({"conversation": conversation, "messages": db.get_messages(conversation_id)})

    @app.delete("/api/conversations/<int:conversation_id>")
    def api_delete_conversation(conversation_id):
        if not db.delete_conversation(g.owner_id, conversation_id):
            return json_error("Conversation introuvable.", 404)
        return jsonify({"ok": True})

    @app.delete("/api/conversations")
    def api_delete_all_conversations():
        db.delete_all_conversations(g.owner_id)
        return jsonify({"ok": True})

    # ------------------------------------------------------------------
    # API : mémoire
    # ------------------------------------------------------------------
    @app.get("/api/memories")
    def api_list_memories():
        return jsonify({"memories": db.list_memories(g.owner_id), "max": mem.MAX_MEMORIES})

    @app.post("/api/memories")
    def api_add_memory():
        content = json_body().get("content")
        if not isinstance(content, str) or not content.strip():
            return json_error("Écris l'information à retenir.")
        status = mem.save_fact(g.owner_id, content)
        if status == "full":
            return json_error(f"Mémoire pleine ({mem.MAX_MEMORIES} éléments maximum).")
        return jsonify({"status": status}), (201 if status == "saved" else 200)

    @app.delete("/api/memories/<int:memory_id>")
    def api_delete_memory(memory_id):
        if not db.delete_memory(g.owner_id, memory_id):
            return json_error("Souvenir introuvable.", 404)
        return jsonify({"ok": True})

    @app.delete("/api/memories")
    def api_delete_all_memories():
        db.delete_all_memories(g.owner_id)
        return jsonify({"ok": True})

    # ------------------------------------------------------------------
    # API : paramètres
    # ------------------------------------------------------------------
    def settings_for_json(owner_id):
        s = db.get_settings(owner_id)
        return {
            "display_name": s["display_name"],
            "response_style": s["response_style"],
            "memory_enabled": s["memory_enabled"] == "1",
            "custom_instructions": s["custom_instructions"],
        }

    @app.get("/api/settings")
    def api_get_settings():
        return jsonify(settings_for_json(g.owner_id))

    @app.put("/api/settings")
    def api_put_settings():
        data = json_body()
        new_values = {}

        if "display_name" in data:
            name = data["display_name"]
            if not isinstance(name, str) or len(name.strip()) > 40:
                return json_error("Le nom doit faire 40 caractères maximum.")
            new_values["display_name"] = " ".join(name.split())
        if "response_style" in data:
            if data["response_style"] not in RESPONSE_STYLES:
                return json_error("Style de réponse invalide.")
            new_values["response_style"] = data["response_style"]
        if "custom_instructions" in data:
            text = data["custom_instructions"]
            if not isinstance(text, str) or len(text.strip()) > 500:
                return json_error("Les instructions doivent faire 500 caractères maximum.")
            new_values["custom_instructions"] = text.strip()
        if "memory_enabled" in data:
            if not isinstance(data["memory_enabled"], bool):
                return json_error("Valeur invalide pour la mémoire.")
            new_values["memory_enabled"] = "1" if data["memory_enabled"] else "0"

        db.save_settings(g.owner_id, new_values)
        return jsonify(settings_for_json(g.owner_id))

    # ------------------------------------------------------------------
    # API : contact
    # ------------------------------------------------------------------
    @app.post("/api/contact")
    def api_contact():
        if not contact_limiter.allow(request.remote_addr):
            return json_error("Trop de messages envoyés. Réessaie plus tard.", 429)

        data = json_body()
        if data.get("website"):  # champ piège caché : seuls les robots le remplissent
            return jsonify({"ok": True})

        name = str(data.get("name", "")).strip()
        email = str(data.get("email", "")).strip()
        message = str(data.get("message", "")).strip()
        if not (2 <= len(name) <= 80):
            return json_error("Écris ton nom (2 à 80 caractères).")
        if not EMAIL_PATTERN.match(email) or len(email) > 120:
            return json_error("Adresse e-mail invalide.")
        if not (5 <= len(message) <= 2000):
            return json_error("Ton message doit faire entre 5 et 2000 caractères.")

        db.save_contact_message(name, email, message)
        return jsonify({"ok": True})

    # ------------------------------------------------------------------
    # Commande pour lire les messages reçus :  flask --app app messages
    # ------------------------------------------------------------------
    @app.cli.command("messages")
    def show_contact_messages():
        """Affiche les messages envoyés depuis la page Contact."""
        messages = db.list_contact_messages()
        if not messages:
            click.echo("Aucun message reçu pour le moment.")
        for m in messages:
            click.echo(f"[{m['created_at']}] {m['name']} <{m['email']}>\n{m['message']}\n" + "-" * 40)

    return app


app = create_app()

if __name__ == "__main__":
    import os

    app.run(host="127.0.0.1", port=int(os.getenv("PORT", "5000")), debug=Config.DEBUG)
