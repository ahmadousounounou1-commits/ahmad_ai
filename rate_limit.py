"""
rate_limit.py : limite le nombre de messages par heure et par adresse IP.

Pourquoi ? Quand ton site est en ligne, chaque message envoyé à l'IA
consomme ta clé API (donc de l'argent). Sans limite, quelqu'un pourrait
vider ton crédit en quelques minutes.

Limite : le compteur est gardé en mémoire dans le processus. Si ton
hébergeur lance plusieurs processus, chacun a son propre compteur.
C'est suffisant pour un début ; plus tard on pourra utiliser Redis.
"""
import time
from collections import defaultdict, deque
from threading import Lock


class RateLimiter:
    def __init__(self, max_calls, period_seconds):
        self.max_calls = max_calls
        self.period = period_seconds
        self._calls = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key):
        """Renvoie True si l'appel est autorisé, False si la limite est atteinte."""
        now = time.time()
        with self._lock:
            calls = self._calls[key]
            while calls and calls[0] <= now - self.period:
                calls.popleft()
            if len(calls) >= self.max_calls:
                return False
            calls.append(now)
            return True
