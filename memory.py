"""
memory.py : la mémoire d'AHMAD AI.

Comment ça marche (volontairement simple) :
1. Si l'utilisateur écrit "Souviens-toi que ..." (ou "retiens que ...",
   "mémorise ..."), l'information est enregistrée dans la base de données.
2. À chaque nouveau message, les informations mémorisées sont ajoutées
   aux instructions données à l'IA. Elle peut donc s'en servir.
3. L'utilisateur peut voir, ajouter et supprimer ses souvenirs dans
   la page Paramètres.

Ce n'est PAS une mémoire "magique" : l'application ne retient que ce
qu'on lui demande explicitement de retenir.
"""
import re

import database as db

MAX_MEMORIES = 50        # nombre maximum de souvenirs par visiteur
MAX_MEMORY_LENGTH = 300  # longueur maximum d'un souvenir (en caractères)

# Reconnaît : "souviens-toi que ...", "retiens que ...", "mémorise : ...", etc.
_TRIGGER = re.compile(
    r"^\s*(?:souviens[\s-]+toi|rappelle[\s-]+toi|retiens|m[ée]morise|n['’]oublie\s+pas)"
    r"\s*(?:que\s+|qu['’]|:\s*)?(?P<fait>.+)$",
    re.IGNORECASE | re.DOTALL,
)


def clean_fact(text):
    """Nettoie un souvenir : espaces en trop, longueur maximum."""
    fact = " ".join(text.split())
    return fact[:MAX_MEMORY_LENGTH].strip()


def extract_memory_request(text):
    """Renvoie l'information à retenir si le message la demande, sinon None."""
    match = _TRIGGER.match(text)
    if not match:
        return None
    fact = clean_fact(match.group("fait")).rstrip(".!")
    return fact or None


def save_fact(owner_id, fact):
    """Enregistre un souvenir. Renvoie "saved", "exists" ou "full"."""
    fact = clean_fact(fact)
    if not fact:
        return "empty"
    if db.count_memories(owner_id) >= MAX_MEMORIES:
        return "full"
    return "saved" if db.add_memory(owner_id, fact) else "exists"
