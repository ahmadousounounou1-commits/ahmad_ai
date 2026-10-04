"""
config.py : les réglages de l'application AHMAD AI.

Ce fichier lit les "variables d'environnement" (des réglages que l'on
place en dehors du code) et, en local, le fichier .env.
Avantage : la clé API secrète n'est JAMAIS écrite dans le code et
n'est JAMAIS envoyée au navigateur.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

# Lit le fichier .env (s'il existe) et ajoute ses valeurs aux variables d'environnement.
load_dotenv(BASE_DIR / ".env")


def _int(name, default):
    """Lit un nombre entier dans l'environnement (valeur par défaut si absent ou invalide)."""
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


def _bool(name, default=False):
    """Lit un booléen (1 / true / yes / oui) dans l'environnement."""
    valeur = os.getenv(name, "1" if default else "0")
    return valeur.strip().lower() in ("1", "true", "yes", "oui")


class Config:
    # --- IA ---
    AI_PROVIDER = os.getenv("AI_PROVIDER", "auto").strip().lower()
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
    AI_MODEL = os.getenv("AI_MODEL", "claude-sonnet-5").strip()
    MAX_OUTPUT_TOKENS = _int("MAX_OUTPUT_TOKENS", 1000)

    # --- Limites ---
    MAX_HISTORY_MESSAGES = _int("MAX_HISTORY_MESSAGES", 20)
    MAX_MESSAGE_LENGTH = _int("MAX_MESSAGE_LENGTH", 4000)
    RATE_LIMIT_PER_HOUR = _int("RATE_LIMIT_PER_HOUR", 40)

    # --- Base de données (un simple fichier SQLite) ---
    DATABASE_PATH = os.getenv("DATABASE_PATH", str(BASE_DIR / "data" / "ahmad_ai.db"))

    # --- Créateur (page Contact) ---
    CREATOR_NAME = os.getenv("CREATOR_NAME", "Ahmadou").strip()
    CONTACT_EMAIL = os.getenv("CONTACT_EMAIL", "").strip()
    CONTACT_WHATSAPP = os.getenv("CONTACT_WHATSAPP", "").strip()

    # --- Technique ---
    DEBUG = _bool("FLASK_DEBUG", False)
    TRUST_PROXY = _bool("TRUST_PROXY", False)
