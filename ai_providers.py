"""
ai_providers.py : les "cerveaux" que AHMAD AI peut utiliser.

Un "fournisseur" (provider) est une classe qui sait faire UNE chose :
    generate(system_prompt, messages, context) -> texte de la réponse

Il y en a deux :

1. AnthropicProvider : appelle une vraie IA (un modèle de langage) via
   son API. Nécessite Internet, une clé API et un compte. La clé est lue
   côté serveur (variable d'environnement) : elle n'est jamais envoyée
   au navigateur.

2. LocalProvider : un petit assistant À RÈGLES, sans Internet. Il sert à
   tester l'application gratuitement. Ce n'est PAS une IA comparable à
   ChatGPT ou Claude : il ne comprend que quelques sujets.

Pour ajouter une autre IA plus tard : crée une nouvelle classe avec la
méthode generate(), puis ajoute-la dans build_provider(). Le reste de
l'application n'aura pas besoin de changer.
"""
import ast
import operator
import re
import unicodedata
from datetime import datetime


class ProviderError(Exception):
    """Erreur avec un message lisible par l'utilisateur."""


class BaseProvider:
    name = "base"
    label = "Base"

    def generate(self, system_prompt, messages, context=None):
        raise NotImplementedError


# ======================================================================
# 1. IA externe (API Anthropic)
# ======================================================================
class AnthropicProvider(BaseProvider):
    name = "anthropic"

    def __init__(self, api_key, model, max_tokens):
        try:
            import anthropic
        except ImportError as exc:
            raise ProviderError(
                "Le paquet 'anthropic' n'est pas installé. "
                "Lance : pip install -r requirements.txt"
            ) from exc
        self._anthropic = anthropic
        self.client = anthropic.Anthropic(api_key=api_key, timeout=60.0)
        self.model = model
        self.max_tokens = max_tokens
        self.label = model

    def generate(self, system_prompt, messages, context=None):
        a = self._anthropic
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=system_prompt,
                messages=messages,
            )
        except a.AuthenticationError as exc:
            raise ProviderError(
                "La clé API est refusée. Vérifie ANTHROPIC_API_KEY dans ton fichier .env."
            ) from exc
        except a.PermissionDeniedError as exc:
            raise ProviderError("Ta clé API n'a pas la permission d'utiliser ce modèle.") from exc
        except a.NotFoundError as exc:
            raise ProviderError(
                f"Le modèle « {self.model} » est introuvable. Vérifie AI_MODEL dans .env."
            ) from exc
        except a.RateLimitError as exc:
            raise ProviderError(
                "Trop de demandes envoyées à l'IA. Attends un moment puis réessaie."
            ) from exc
        except a.APIConnectionError as exc:
            raise ProviderError(
                "Impossible de joindre le service d'IA. Vérifie ta connexion Internet."
            ) from exc
        except a.APIStatusError as exc:
            raise ProviderError(
                f"Le service d'IA a renvoyé une erreur (code {exc.status_code})."
            ) from exc

        # La réponse est une liste de "blocs" : on assemble ceux qui sont du texte.
        text = "".join(b.text for b in response.content if getattr(b, "type", "") == "text")
        text = text.strip()
        if not text:
            raise ProviderError("L'IA a renvoyé une réponse vide. Réessaie.")
        return text


# ======================================================================
# 2. Mode local (assistant à règles, sans Internet)
# ======================================================================
def _normalize(text):
    """Minuscules, sans accents, apostrophes simples : facilite la comparaison."""
    text = text.lower().replace("’", "'")
    text = unicodedata.normalize("NFD", text)
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


_OPERATIONS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}
_LIMIT = 1e100


def _safe_eval(node):
    """Calcule une expression mathématique SANS utiliser eval() (qui serait dangereux)."""
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return node.value
        raise ValueError("Valeur non autorisée")
    if isinstance(node, ast.BinOp) and type(node.op) in _OPERATIONS:
        left = _safe_eval(node.left)
        right = _safe_eval(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > 100:
            raise ValueError("Exposant trop grand")
        result = _OPERATIONS[type(node.op)](left, right)
    elif isinstance(node, ast.UnaryOp) and type(node.op) in _OPERATIONS:
        result = _OPERATIONS[type(node.op)](_safe_eval(node.operand))
    else:
        raise ValueError("Expression non autorisée")
    if isinstance(result, complex) or abs(result) > _LIMIT:
        raise ValueError("Résultat trop grand")
    return result


_MATH_CHARS = re.compile(r"[\d\s+\-*/().,^×÷]{3,}")


def _find_expression(text):
    """Cherche un calcul dans la phrase. Renvoie None si rien de sûr."""
    text = re.sub(r"(?<=\d)\s*[xX]\s*(?=\d)", "*", text)  # "3 x 4" -> "3*4"
    best = None
    for chunk in _MATH_CHARS.findall(text):
        chunk = chunk.strip()
        if re.search(r"\d", chunk) and re.search(r"[+\-*/^×÷]", chunk):
            if best is None or len(chunk) > len(best):
                best = chunk
    if best is None or len(best) > 60:
        return None
    # On ne calcule que si l'utilisateur parle de calcul, ou si le message est surtout un calcul.
    mentions_math = re.search(r"calcul|combien|resultat|=", _normalize(text))
    mostly_math = len(best) >= 0.6 * len(text.strip())
    return best if (mentions_math or mostly_math) else None


def _format_number(value):
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return str(round(value, 6))
    return str(value)


# Petite base de connaissances : (mots-clés, réponse). Les mots-clés sont sans accents.
_KNOWLEDGE = [
    (
        ["mode local", "vraie ia", "chatgpt", "pourquoi tu es limite", "tu comprends"],
        "En mode local, je suis un petit programme à règles : je reconnais des mots-clés et "
        "j'applique des réponses écrites à l'avance. Je ne suis pas comparable à ChatGPT ou "
        "Claude, qui sont de vrais modèles de langage. Pour activer une vraie IA, ajoute une "
        "clé API dans le fichier .env (voir le README).",
    ),
    (
        ["intelligence artificielle", "l'ia", "c'est quoi l'ia"],
        "L'intelligence artificielle (IA) regroupe des techniques qui permettent à une machine "
        "d'accomplir des tâches qui demandent normalement de l'intelligence humaine : reconnaître "
        "une image, comprendre une phrase, faire une prédiction. Une IA ne pense pas comme un "
        "humain : elle calcule à partir de données.",
    ),
    (
        ["machine learning", "apprentissage automatique"],
        "Le Machine Learning (apprentissage automatique) est une partie de l'IA : au lieu "
        "d'écrire toutes les règles à la main, on donne des exemples à la machine et elle "
        "trouve elle-même les règles.",
    ),
    (
        ["deep learning", "reseau de neurones", "reseaux de neurones"],
        "Le Deep Learning utilise des réseaux de neurones artificiels à plusieurs couches. "
        "C'est la technique derrière la reconnaissance d'images et les modèles de langage modernes.",
    ),
    (
        ["python"],
        "Python est un langage de programmation simple à lire, très utilisé en intelligence "
        "artificielle. Une première ligne : print(\"Bonjour\") affiche Bonjour à l'écran.",
    ),
    (
        ["merci"],
        "Avec plaisir ! N'hésite pas si tu as une autre question.",
    ),
]

_HELP = (
    "En mode local, je sais faire ces choses :\n"
    "- Calculer : « calcule 12 * (3 + 4) »\n"
    "- Donner la date : « quelle est la date ? »\n"
    "- Retenir une information : « souviens-toi que j'aime le football »\n"
    "- Te dire ce que j'ai retenu : « que sais-tu de moi ? »\n"
    "- Expliquer quelques notions : IA, machine learning, deep learning, Python\n\n"
    "Pour de vraies conversations, connecte une IA externe (voir le README)."
)

_JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
_MOIS = [
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]


def _contains(text, phrase):
    return re.search(r"\b" + re.escape(phrase) + r"\b", text) is not None


class LocalProvider(BaseProvider):
    name = "local"
    label = "Mode local"

    def generate(self, system_prompt, messages, context=None):
        context = context or {}
        raw = messages[-1]["content"]
        text = _normalize(raw)
        display_name = context.get("display_name") or ""

        # 1. Un souvenir vient d'être enregistré
        event = context.get("memory_event")
        if event and event["status"] in ("saved", "exists"):
            if event["status"] == "saved":
                return f"C'est noté, je retiens : « {event['fact']} »."
            return f"Je le savais déjà : « {event['fact']} »."

        # 2. L'utilisateur demande ce qui est en mémoire
        if any(p in text for p in ("que sais-tu de moi", "que sais tu de moi", "qu'as-tu retenu",
                                   "que retiens-tu", "ta memoire", "mes souvenirs")):
            memories = context.get("memories") or []
            if not memories:
                return "Je n'ai encore rien en mémoire. Dis-moi par exemple : « souviens-toi que je m'appelle Ali »."
            lignes = "\n".join(f"- {m}" for m in memories)
            return f"Voici ce que j'ai en mémoire :\n{lignes}"

        # 3. Salutations
        if re.match(r"^(bonjour|salut|bonsoir|coucou|hello|salam)\b", text):
            nom = f" {display_name}" if display_name else ""
            return f"Bonjour{nom} ! Je suis AHMAD AI. Tape « aide » pour voir ce que je sais faire."

        # 4. Calculs
        expression = _find_expression(raw)
        if expression:
            try:
                python_expr = (
                    expression.replace("×", "*").replace("÷", "/").replace("^", "**").replace(",", ".")
                )
                result = _safe_eval(ast.parse(python_expr, mode="eval"))
                return f"{expression} = {_format_number(result)}"
            except ZeroDivisionError:
                return "On ne peut pas diviser par zéro."
            except (ValueError, SyntaxError, ArithmeticError):
                pass  # on essaie les autres réponses

        # 5. Date et heure (celles du serveur)
        if "quelle date" in text or "quel jour" in text or "date d'aujourd" in text:
            d = datetime.now()
            return f"Nous sommes le {_JOURS[d.weekday()]} {d.day} {_MOIS[d.month - 1]} {d.year} (date du serveur)."
        if "quelle heure" in text:
            return f"Il est {datetime.now().strftime('%H:%M')} (heure du serveur)."

        # 6. Aide
        if text.strip() in ("aide", "help") or any(
            p in text for p in ("que peux-tu faire", "que sais-tu faire", "tu peux faire quoi")
        ):
            return _HELP

        # 7. Identité
        if any(p in text for p in ("qui es-tu", "qui es tu", "tu es qui", "comment tu t'appelles",
                                   "ton nom")):
            creator = context.get("creator_name") or "son créateur"
            return (
                f"Je suis AHMAD AI, un assistant créé par {creator}. Je fonctionne actuellement "
                "en mode local : je suis un petit programme à règles, pas une IA avancée."
            )

        # 8. Petite base de connaissances : on prend l'entrée qui correspond le mieux
        best_answer, best_score = None, 0
        for keywords, answer in _KNOWLEDGE:
            score = sum(1 for k in keywords if _contains(text, k))
            if score > best_score:
                best_answer, best_score = answer, score
        if best_answer:
            return best_answer

        # 9. Réponse par défaut
        return (
            "Je suis en mode local : je ne comprends que quelques sujets (calculs, date, "
            "quelques définitions, mémoire). Tape « aide » pour voir la liste. "
            "Pour de vraies conversations, connecte une IA externe (voir le README)."
        )


# ======================================================================
# Choix du fournisseur
# ======================================================================
def build_provider(config):
    """Choisit le fournisseur selon AI_PROVIDER et la présence d'une clé API."""
    choice = config.AI_PROVIDER
    if choice not in ("auto", "anthropic", "local"):
        raise ProviderError("AI_PROVIDER doit valoir : auto, anthropic ou local.")

    if choice == "anthropic" or (choice == "auto" and config.ANTHROPIC_API_KEY):
        if not config.ANTHROPIC_API_KEY:
            raise ProviderError(
                "AI_PROVIDER=anthropic mais ANTHROPIC_API_KEY est vide. "
                "Ajoute ta clé dans le fichier .env."
            )
        return AnthropicProvider(config.ANTHROPIC_API_KEY, config.AI_MODEL, config.MAX_OUTPUT_TOKENS)

    return LocalProvider()
