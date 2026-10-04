"""
test_app.py : tests automatiques.

Lancer :   python -m unittest -v

Les tests utilisent le mode local (aucune clé API, aucun Internet) et une
base de données temporaire : ils ne touchent pas à tes vraies données.
Le fournisseur d'IA externe est testé avec un FAUX module "anthropic".
"""
import os
import sys
import tempfile
import types
import unittest
from types import SimpleNamespace

# Réglages de test : à définir AVANT d'importer l'application.
_tmp = tempfile.TemporaryDirectory()
os.environ["DATABASE_PATH"] = os.path.join(_tmp.name, "test.db")
os.environ["AI_PROVIDER"] = "local"
os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["RATE_LIMIT_PER_HOUR"] = "1000"

from app import create_app  # noqa: E402
from ai_providers import AnthropicProvider, LocalProvider, ProviderError, build_provider  # noqa: E402
from chatbot import build_system_prompt, prepare_history  # noqa: E402
from config import Config  # noqa: E402
from memory import extract_memory_request  # noqa: E402


def post_json(client, url, data):
    return client.post(url, json=data)


class PagesTest(unittest.TestCase):
    def setUp(self):
        self.client = create_app().test_client()

    def test_all_pages_load(self):
        for url in ("/", "/chat", "/about", "/contact", "/settings"):
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_healthz(self):
        r = self.client.get("/healthz")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json(), {"ok": True})

    def test_unknown_page_is_404(self):
        self.assertEqual(self.client.get("/nimporte-quoi").status_code, 404)
        self.assertEqual(self.client.get("/api/nimporte-quoi").status_code, 404)

    def test_api_key_never_in_pages(self):
        Config.ANTHROPIC_API_KEY = "sk-secret-test"
        try:
            for url in ("/", "/chat", "/api/status", "/static/js/chat.js"):
                response = self.client.get(url)
                self.assertNotIn(b"sk-secret-test", response.data)
                response.close()
        finally:
            Config.ANTHROPIC_API_KEY = ""


class ChatTest(unittest.TestCase):
    def setUp(self):
        self.client = create_app().test_client()

    def test_chat_creates_conversation_and_history(self):
        r = post_json(self.client, "/api/chat", {"message": "Bonjour"})
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertIn("AHMAD AI", data["reply"])
        cid = data["conversation_id"]

        listing = self.client.get("/api/conversations").get_json()["conversations"]
        self.assertEqual([c["id"] for c in listing], [cid])

        r = post_json(self.client, "/api/chat", {"message": "merci", "conversation_id": cid})
        self.assertEqual(r.get_json()["conversation_id"], cid)

        detail = self.client.get(f"/api/conversations/{cid}").get_json()
        self.assertEqual([m["role"] for m in detail["messages"]], ["user", "assistant"] * 2)

    def test_calculation(self):
        r = post_json(self.client, "/api/chat", {"message": "calcule 12 * (3 + 4)"})
        self.assertIn("= 84", r.get_json()["reply"])

    def test_dangerous_expression_is_not_executed(self):
        r = post_json(self.client, "/api/chat", {"message": "calcule 10**100000"})
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("= 1000", r.get_json()["reply"])
        r = post_json(self.client, "/api/chat", {"message": "calcule 5 / 0"})
        self.assertIn("zéro", r.get_json()["reply"])

    def test_validation_errors(self):
        self.assertEqual(post_json(self.client, "/api/chat", {"message": "   "}).status_code, 400)
        self.assertEqual(post_json(self.client, "/api/chat", {}).status_code, 400)
        too_long = "a" * (Config.MAX_MESSAGE_LENGTH + 1)
        self.assertEqual(post_json(self.client, "/api/chat", {"message": too_long}).status_code, 400)
        r = post_json(self.client, "/api/chat", {"message": "salut", "conversation_id": 999})
        self.assertEqual(r.status_code, 404)
        r = post_json(self.client, "/api/chat", {"message": "salut", "conversation_id": "1"})
        self.assertEqual(r.status_code, 400)
        # Une requête qui n'est pas du JSON est refusée
        self.assertEqual(self.client.post("/api/chat", data="message=salut").status_code, 400)

    def test_delete_conversation(self):
        cid = post_json(self.client, "/api/chat", {"message": "Bonjour"}).get_json()["conversation_id"]
        self.assertEqual(self.client.delete(f"/api/conversations/{cid}").status_code, 200)
        self.assertEqual(self.client.get(f"/api/conversations/{cid}").status_code, 404)

    def test_visitors_are_isolated(self):
        cid = post_json(self.client, "/api/chat", {"message": "Bonjour"}).get_json()["conversation_id"]
        other = create_app().test_client()
        other.get("/")  # reçoit son propre cookie
        self.assertEqual(other.get(f"/api/conversations/{cid}").status_code, 404)
        self.assertEqual(other.get("/api/conversations").get_json()["conversations"], [])
        self.assertEqual(other.delete(f"/api/conversations/{cid}").status_code, 404)
        r = post_json(other, "/api/chat", {"message": "salut", "conversation_id": cid})
        self.assertEqual(r.status_code, 404)


class MemoryTest(unittest.TestCase):
    def setUp(self):
        self.client = create_app().test_client()

    def test_extract_memory_request(self):
        self.assertEqual(extract_memory_request("Souviens-toi que j'aime le foot."), "j'aime le foot")
        self.assertEqual(extract_memory_request("retiens : mon examen est lundi"), "mon examen est lundi")
        self.assertEqual(extract_memory_request("mémorise que je m'appelle Ali"), "je m'appelle Ali")
        self.assertIsNone(extract_memory_request("Bonjour, comment ça va ?"))
        self.assertIsNone(extract_memory_request("je voudrais que tu retiens ça"))

    def test_memory_flow(self):
        r = post_json(self.client, "/api/chat", {"message": "Souviens-toi que j'aime le football"})
        self.assertEqual(r.get_json()["memory_saved"], "j'aime le football")
        memories = self.client.get("/api/memories").get_json()["memories"]
        self.assertEqual([m["content"] for m in memories], ["j'aime le football"])

        r = post_json(self.client, "/api/chat", {"message": "Que sais-tu de moi ?"})
        self.assertIn("j'aime le football", r.get_json()["reply"])

        mid = memories[0]["id"]
        self.assertEqual(self.client.delete(f"/api/memories/{mid}").status_code, 200)
        self.assertEqual(self.client.get("/api/memories").get_json()["memories"], [])

    def test_memory_disabled(self):
        self.client.put("/api/settings", json={"memory_enabled": False})
        r = post_json(self.client, "/api/chat", {"message": "Souviens-toi que je suis en 1ère TI"})
        self.assertIsNone(r.get_json()["memory_saved"])
        self.assertEqual(self.client.get("/api/memories").get_json()["memories"], [])

    def test_manual_memory_add(self):
        r = post_json(self.client, "/api/memories", {"content": "J'habite à Maroua"})
        self.assertEqual(r.status_code, 201)
        r = post_json(self.client, "/api/memories", {"content": "J'habite à Maroua"})
        self.assertEqual(r.get_json()["status"], "exists")
        self.assertEqual(post_json(self.client, "/api/memories", {"content": " "}).status_code, 400)


class SettingsAndContactTest(unittest.TestCase):
    def setUp(self):
        self.client = create_app().test_client()

    def test_settings(self):
        s = self.client.get("/api/settings").get_json()
        self.assertEqual(s, {"display_name": "", "response_style": "normal", "memory_enabled": True,
                                "custom_instructions": ""})
        r = self.client.put("/api/settings", json={"display_name": "Ali", "response_style": "short"})
        self.assertEqual(r.get_json()["display_name"], "Ali")
        self.assertEqual(self.client.put("/api/settings", json={"response_style": "x"}).status_code, 400)
        self.assertEqual(self.client.put("/api/settings", json={"memory_enabled": "oui"}).status_code, 400)
        r = self.client.put("/api/settings", json={"custom_instructions": "  Explique avec des exemples.  "})
        self.assertEqual(r.get_json()["custom_instructions"], "Explique avec des exemples.")
        self.assertEqual(self.client.put("/api/settings", json={"custom_instructions": "a" * 501}).status_code, 400)
        self.assertEqual(self.client.put("/api/settings", json={"custom_instructions": 5}).status_code, 400)
        self.assertEqual(self.client.put("/api/settings", json={"display_name": "a" * 41}).status_code, 400)

    def test_contact(self):
        ok = {"name": "Ali", "email": "ali@example.com", "message": "Bonjour, super projet !"}
        self.assertEqual(post_json(self.client, "/api/contact", ok).status_code, 200)
        self.assertEqual(post_json(self.client, "/api/contact", {**ok, "email": "pas-un-email"}).status_code, 400)
        self.assertEqual(post_json(self.client, "/api/contact", {**ok, "message": "hi"}).status_code, 400)
        # Le champ piège : réponse "ok" mais rien n'est enregistré
        self.assertEqual(post_json(self.client, "/api/contact", {**ok, "website": "http://spam"}).status_code, 200)


class ProvidersTest(unittest.TestCase):
    def test_default_is_local_without_key(self):
        self.assertIsInstance(build_provider(Config), LocalProvider)

    def test_anthropic_without_key_fails_clearly(self):
        cfg = SimpleNamespace(AI_PROVIDER="anthropic", ANTHROPIC_API_KEY="", AI_MODEL="m", MAX_OUTPUT_TOKENS=10)
        with self.assertRaises(ProviderError):
            build_provider(cfg)

    def test_custom_instructions_reach_the_prompt(self):
        settings = {"display_name": "", "response_style": "normal", "custom_instructions": "Corrige mes fautes."}
        prompt = build_system_prompt("Ahmadou", settings, [], True)
        self.assertIn("Corrige mes fautes.", prompt)
        settings["custom_instructions"] = ""
        self.assertNotIn("Préférences personnelles", build_system_prompt("Ahmadou", settings, [], True))

    def test_prepare_history_starts_with_user(self):
        stored = [
            {"role": "assistant", "content": "a"},
            {"role": "user", "content": "b"},
            {"role": "assistant", "content": "c"},
        ]
        self.assertEqual([m["role"] for m in prepare_history(stored, 10)], ["user", "assistant"])
        self.assertEqual([m["role"] for m in prepare_history(stored, 2)], ["user", "assistant"])
        self.assertEqual([m["role"] for m in prepare_history(stored, 1)], [])


class FakeAnthropicTest(unittest.TestCase):
    """Teste AnthropicProvider avec un faux module (pas d'Internet, pas de clé)."""

    def setUp(self):
        fake = types.ModuleType("anthropic")

        class APIError(Exception):
            pass

        class APIConnectionError(APIError):
            pass

        class APIStatusError(APIError):
            status_code = 500

        class AuthenticationError(APIStatusError):
            status_code = 401

        class PermissionDeniedError(APIStatusError):
            status_code = 403

        class NotFoundError(APIStatusError):
            status_code = 404

        class RateLimitError(APIStatusError):
            status_code = 429

        for cls in (APIConnectionError, APIStatusError, AuthenticationError,
                    PermissionDeniedError, NotFoundError, RateLimitError):
            setattr(fake, cls.__name__, cls)

        self.calls = []
        self.next_result = None
        outer = self

        class Messages:
            def create(self, **kwargs):
                outer.calls.append(kwargs)
                if isinstance(outer.next_result, Exception):
                    raise outer.next_result
                return outer.next_result

        class Anthropic:
            def __init__(self, api_key, timeout):
                self.messages = Messages()

        fake.Anthropic = Anthropic
        self.fake = fake
        self._old = sys.modules.get("anthropic")
        sys.modules["anthropic"] = fake
        self.provider = AnthropicProvider("cle", "modele-test", 123)

    def tearDown(self):
        if self._old is None:
            sys.modules.pop("anthropic", None)
        else:
            sys.modules["anthropic"] = self._old

    def test_success_sends_expected_request(self):
        self.next_result = SimpleNamespace(content=[SimpleNamespace(type="text", text=" Salut ! ")])
        text = self.provider.generate("SYSTEME", [{"role": "user", "content": "yo"}])
        self.assertEqual(text, "Salut !")
        call = self.calls[0]
        self.assertEqual(call["model"], "modele-test")
        self.assertEqual(call["max_tokens"], 123)
        self.assertEqual(call["system"], "SYSTEME")
        self.assertEqual(call["messages"], [{"role": "user", "content": "yo"}])

    def test_errors_are_translated(self):
        for error, word in (
            (self.fake.AuthenticationError(), "clé API"),
            (self.fake.RateLimitError(), "Trop de demandes"),
            (self.fake.NotFoundError(), "introuvable"),
            (self.fake.APIConnectionError(), "Internet"),
            (self.fake.APIStatusError(), "500"),
        ):
            self.next_result = error
            with self.assertRaises(ProviderError) as ctx:
                self.provider.generate("s", [{"role": "user", "content": "x"}])
            self.assertIn(word, str(ctx.exception))

    def test_empty_answer_is_an_error(self):
        self.next_result = SimpleNamespace(content=[])
        with self.assertRaises(ProviderError):
            self.provider.generate("s", [{"role": "user", "content": "x"}])


if __name__ == "__main__":
    unittest.main()
