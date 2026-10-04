"""
database.py : tout ce qui touche à la base de données.

On utilise SQLite : une base de données stockée dans UN SEUL fichier
(data/ahmad_ai.db). Rien à installer : SQLite est inclus dans Python.

Chaque visiteur est identifié par un "owner_id" (un identifiant aléatoire
gardé dans un cookie). Ses conversations, sa mémoire et ses paramètres
sont séparés de ceux des autres visiteurs.
"""
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from flask import current_app, g

SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id    TEXT NOT NULL,
    title       TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_conversations_owner
    ON conversations (owner_id, updated_at);

CREATE TABLE IF NOT EXISTS messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL REFERENCES conversations (id) ON DELETE CASCADE,
    role            TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content         TEXT NOT NULL,
    created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_conversation
    ON messages (conversation_id, id);

CREATE TABLE IF NOT EXISTS memories (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id    TEXT NOT NULL,
    content     TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    UNIQUE (owner_id, content)
);

CREATE TABLE IF NOT EXISTS settings (
    owner_id TEXT NOT NULL,
    key      TEXT NOT NULL,
    value    TEXT NOT NULL,
    PRIMARY KEY (owner_id, key)
);

CREATE TABLE IF NOT EXISTS contact_messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    email       TEXT NOT NULL,
    message     TEXT NOT NULL,
    created_at  TEXT NOT NULL
);
"""

DEFAULT_SETTINGS = {
    "display_name": "",
    "response_style": "normal",  # short | normal | detailed
    "memory_enabled": "1",       # "1" = oui, "0" = non
    "custom_instructions": "",   # consignes personnelles pour l'assistant (500 caractères max)
}


def now():
    """Date et heure actuelles (UTC), en texte."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ------------------------------------------------------------------
# Connexion
# ------------------------------------------------------------------
def get_db():
    """Ouvre la connexion (une seule par requête) et la réutilise."""
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE_PATH"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_app(app):
    """Crée le dossier et les tables au démarrage, et branche la fermeture."""
    Path(app.config["DATABASE_PATH"]).parent.mkdir(parents=True, exist_ok=True)
    app.teardown_appcontext(close_db)
    with app.app_context():
        get_db().executescript(SCHEMA)
        get_db().commit()


# ------------------------------------------------------------------
# Conversations et messages
# ------------------------------------------------------------------
def create_conversation(owner_id, title):
    db = get_db()
    t = now()
    cur = db.execute(
        "INSERT INTO conversations (owner_id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
        (owner_id, title, t, t),
    )
    db.commit()
    return cur.lastrowid


def list_conversations(owner_id):
    rows = get_db().execute(
        "SELECT id, title, updated_at FROM conversations "
        "WHERE owner_id = ? ORDER BY updated_at DESC, id DESC",
        (owner_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_conversation(owner_id, conversation_id):
    """Renvoie la conversation SEULEMENT si elle appartient à ce visiteur."""
    row = get_db().execute(
        "SELECT id, title, updated_at FROM conversations WHERE id = ? AND owner_id = ?",
        (conversation_id, owner_id),
    ).fetchone()
    return dict(row) if row else None


def get_messages(conversation_id):
    rows = get_db().execute(
        "SELECT role, content, created_at FROM messages WHERE conversation_id = ? ORDER BY id",
        (conversation_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def add_message(conversation_id, role, content):
    db = get_db()
    t = now()
    db.execute(
        "INSERT INTO messages (conversation_id, role, content, created_at) VALUES (?, ?, ?, ?)",
        (conversation_id, role, content, t),
    )
    db.execute("UPDATE conversations SET updated_at = ? WHERE id = ?", (t, conversation_id))
    db.commit()


def delete_conversation(owner_id, conversation_id):
    db = get_db()
    cur = db.execute(
        "DELETE FROM conversations WHERE id = ? AND owner_id = ?",
        (conversation_id, owner_id),
    )
    db.commit()
    return cur.rowcount > 0


def delete_all_conversations(owner_id):
    db = get_db()
    db.execute("DELETE FROM conversations WHERE owner_id = ?", (owner_id,))
    db.commit()


# ------------------------------------------------------------------
# Mémoire
# ------------------------------------------------------------------
def list_memories(owner_id):
    rows = get_db().execute(
        "SELECT id, content, created_at FROM memories WHERE owner_id = ? ORDER BY id",
        (owner_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def count_memories(owner_id):
    row = get_db().execute(
        "SELECT COUNT(*) AS n FROM memories WHERE owner_id = ?", (owner_id,)
    ).fetchone()
    return row["n"]


def add_memory(owner_id, content):
    """Ajoute un souvenir. Renvoie False s'il existait déjà."""
    db = get_db()
    cur = db.execute(
        "INSERT OR IGNORE INTO memories (owner_id, content, created_at) VALUES (?, ?, ?)",
        (owner_id, content, now()),
    )
    db.commit()
    return cur.rowcount > 0


def delete_memory(owner_id, memory_id):
    db = get_db()
    cur = db.execute(
        "DELETE FROM memories WHERE id = ? AND owner_id = ?", (memory_id, owner_id)
    )
    db.commit()
    return cur.rowcount > 0


def delete_all_memories(owner_id):
    db = get_db()
    db.execute("DELETE FROM memories WHERE owner_id = ?", (owner_id,))
    db.commit()


# ------------------------------------------------------------------
# Paramètres
# ------------------------------------------------------------------
def get_settings(owner_id):
    """Paramètres du visiteur (valeurs par défaut si rien n'est enregistré)."""
    settings = dict(DEFAULT_SETTINGS)
    rows = get_db().execute(
        "SELECT key, value FROM settings WHERE owner_id = ?", (owner_id,)
    ).fetchall()
    for row in rows:
        if row["key"] in settings:
            settings[row["key"]] = row["value"]
    return settings


def save_settings(owner_id, values):
    db = get_db()
    for key, value in values.items():
        if key in DEFAULT_SETTINGS:
            db.execute(
                "INSERT INTO settings (owner_id, key, value) VALUES (?, ?, ?) "
                "ON CONFLICT (owner_id, key) DO UPDATE SET value = excluded.value",
                (owner_id, key, str(value)),
            )
    db.commit()


# ------------------------------------------------------------------
# Messages de contact
# ------------------------------------------------------------------
def save_contact_message(name, email, message):
    db = get_db()
    db.execute(
        "INSERT INTO contact_messages (name, email, message, created_at) VALUES (?, ?, ?, ?)",
        (name, email, message, now()),
    )
    db.commit()


def list_contact_messages():
    rows = get_db().execute(
        "SELECT id, name, email, message, created_at FROM contact_messages ORDER BY id DESC"
    ).fetchall()
    return [dict(r) for r in rows]
