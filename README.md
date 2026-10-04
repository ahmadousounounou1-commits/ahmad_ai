# AHMAD AI

Une application web de discussion avec une IA, écrite en Python (Flask), HTML, CSS et JavaScript.

Elle fonctionne **tout de suite en mode local** (sans Internet, sans clé), et devient une vraie IA dès que tu ajoutes une clé API.

---

## 1. Ce que fait l'application

- Chat moderne, adapté au téléphone et à l'ordinateur
- Historique des conversations et bouton « Nouvelle conversation »
- Mémoire : « Souviens-toi que… » (visible et modifiable dans Paramètres)
- Paramètres : thème clair / sombre / automatique, nom, longueur des réponses, instructions personnalisées, mémoire on/off
- Pages : Accueil, À propos, Contact (formulaire qui enregistre les messages), Paramètres
- Clé API protégée : elle reste sur le serveur, jamais dans le navigateur
- Architecture prévue pour ajouter d'autres IA ou fonctions plus tard

---

## 2. Technologies utilisées

| Technologie | Rôle | Pourquoi ce choix |
|---|---|---|
| **Python 3.10+** | Le serveur (le « backend ») | Simple à lire, langage n°1 en IA |
| **Flask** | Framework web : pages + API | Petit et facile pour un débutant |
| **SQLite** | Base de données (un seul fichier) | Rien à installer, inclus dans Python |
| **Bibliothèque `anthropic`** | Appeler l'IA externe | Gère la connexion et les erreurs |
| **python-dotenv** | Lire le fichier `.env` (secrets) | Garde la clé hors du code |
| **HTML / CSS** | Structure et apparence des pages | Standard du web |
| **JavaScript (sans framework)** | Fait vivre le chat dans le navigateur | Aucun outil de compilation à apprendre |
| **gunicorn** | Serveur pour la mise en ligne (Linux) | Standard en production |

**Internet est nécessaire** seulement pour l'IA externe (l'API). L'API est **payante à l'usage** : vérifie les tarifs sur le site du fournisseur. Le mode local est gratuit.

---

## 3. Architecture et fichiers

```
ahmad_ai/
├── app.py               ← démarre le serveur : pages + API
├── chatbot.py           ← organise une conversation (instructions, historique, mémoire)
├── ai_providers.py      ← les « cerveaux » : IA externe ou mode local
├── memory.py            ← règles de la mémoire
├── database.py          ← tout ce qui touche à la base de données
├── config.py            ← réglages lus depuis .env
├── rate_limit.py        ← limite les messages par heure
├── test_app.py          ← tests automatiques
├── requirements.txt     ← liste des bibliothèques à installer
├── .env.example         ← modèle de configuration (à copier en .env)
├── .gitignore           ← empêche d'envoyer .env sur GitHub
├── README.md            ← ce guide
├── data/                ← la base de données est créée ici
├── templates/           ← les pages HTML
│   ├── base.html        ← menu, thème, pied de page (commun à toutes les pages)
│   ├── index.html       ← accueil
│   ├── chat.html        ← chat
│   ├── about.html       ← « C'est quoi AHMAD AI ? »
│   ├── contact.html     ← contact
│   ├── settings.html    ← paramètres
│   └── 404.html         ← page introuvable
└── static/
    ├── css/style.css    ← apparence (thèmes clair/sombre, mobile)
    └── js/
        ├── common.js    ← thème, menu mobile, fonction api(), notifications
        ├── chat.js      ← le chat
        ├── settings.js  ← page Paramètres
        └── contact.js   ← formulaire de contact
```

### Le rôle de chaque fichier, simplement

| Fichier | Son rôle |
|---|---|
| `app.py` | Le **standard téléphonique** : il reçoit les demandes du navigateur (afficher une page, envoyer un message…) et les transmet au bon endroit. Il identifie aussi chaque visiteur avec un cookie anonyme. |
| `chatbot.py` | Le **chef d'orchestre** d'un message : vérifie le texte, récupère l'historique, enregistre un souvenir, prépare les instructions pour l'IA, appelle l'IA, sauvegarde. |
| `ai_providers.py` | Les **cerveaux**. `AnthropicProvider` appelle une vraie IA. `LocalProvider` est un petit assistant à règles (calcul, date, mémoire, quelques définitions). Pour ajouter une autre IA : ajoute une classe avec `generate()` et branche-la dans `build_provider()`. |
| `memory.py` | Reconnaît « souviens-toi que… » et enregistre le souvenir (50 maximum, 300 caractères chacun). |
| `database.py` | Crée les tables (conversations, messages, mémoire, paramètres, contact) et contient toutes les requêtes SQL. |
| `config.py` | Lit les réglages (clé, modèle, limites). **C'est ici que la clé secrète est lue, côté serveur uniquement.** |
| `rate_limit.py` | Protège ton budget : par défaut 40 messages par heure et par adresse IP. |
| `templates/*.html` | Le contenu des pages. `base.html` est le cadre commun. |
| `static/css/style.css` | Les couleurs, les thèmes clair/sombre, l'adaptation au téléphone. |
| `static/js/*.js` | Le comportement dans le navigateur. Le JavaScript ne parle qu'à **ton** serveur (`/api/...`), jamais directement à l'IA. |
| `test_app.py` | Vérifie que tout fonctionne (23 tests). |

### Le trajet d'un message

```
1. Tu écris "Explique-moi Python" et tu cliques sur Envoyer
2. chat.js envoie le texte à ton serveur : POST /api/chat
3. app.py vérifie la limite d'envois, puis appelle chatbot.py
4. chatbot.py récupère l'historique + la mémoire, prépare les instructions
5. ai_providers.py envoie le tout à l'IA (avec la clé secrète, côté serveur)
6. La réponse revient, est sauvegardée dans la base de données
7. chat.js affiche la réponse dans la conversation
```

### Comment la mémoire fonctionne

L'application ne retient **que** ce que tu demandes explicitement (« souviens-toi que… », « retiens que… », « mémorise… ») ou ce que tu ajoutes dans Paramètres. À chaque message, les souvenirs sont ajoutés aux instructions de l'IA. Ce n'est pas une mémoire « magique » : c'est une liste de notes que tu contrôles.

### Comment les visiteurs sont séparés

Chaque navigateur reçoit un identifiant aléatoire dans un cookie. Les conversations, la mémoire et les paramètres sont liés à cet identifiant : une personne ne voit pas les données d'une autre. **Ce n'est pas un vrai système de comptes** : si on efface les cookies, on perd l'accès à son historique. Les comptes utilisateurs sont une amélioration possible (voir §9).

---

## 4. Installer et lancer en local

### Étape 1 : installer Python et VS Code
Python 3.10 ou plus récent (python.org). **Sur Windows, coche « Add Python to PATH »** pendant l'installation. Installe aussi Visual Studio Code.

### Étape 2 : ouvrir le projet
Dézippe le dossier `ahmad_ai`, ouvre-le dans VS Code (Fichier → Ouvrir le dossier), puis ouvre un terminal (Terminal → Nouveau terminal).

### Étape 3 : créer l'environnement et installer

**Windows**
```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

**macOS / Linux**
```
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

(Le `venv` est une « boîte » qui garde les bibliothèques du projet séparées du reste de l'ordinateur. Quand il est actif, tu vois `(venv)` au début de la ligne du terminal.)

### Étape 4 : lancer
```
python app.py
```
Ouvre **http://127.0.0.1:5000** dans ton navigateur. Pour arrêter : `Ctrl + C` dans le terminal.

Sans clé API, un bandeau orange indique le **mode local**. C'est normal.

### Lancer les tests
```
python -m unittest -v
```

### Lire les messages reçus par la page Contact
```
flask --app app messages
```

---

## 5. Connecter une vraie IA (clé API, sans jamais l'exposer)

1. Crée un compte sur **console.anthropic.com**, ajoute du crédit si nécessaire, puis crée une clé API. (Internet et un compte sont requis ; l'API est payante à l'usage.)
2. Ouvre ton fichier **`.env`** (pas `.env.example`) et remplis :
   ```
   ANTHROPIC_API_KEY=ta_clé_ici
   AI_PROVIDER=auto
   ```
3. Arrête le serveur (`Ctrl + C`) puis relance `python app.py`.
4. Le bandeau « Mode local » disparaît. Dans Paramètres → Informations techniques, tu vois le modèle utilisé.

**Pourquoi la clé est en sécurité :**
- Elle est lue par `config.py` depuis l'environnement, **côté serveur**.
- Le JavaScript ne l'a jamais : il appelle seulement `/api/chat` sur ton serveur.
- `.gitignore` empêche d'envoyer `.env` sur GitHub.
- Si tu la publies par accident : **supprime-la immédiatement** dans la console et crée-en une nouvelle.

Le modèle se change avec `AI_MODEL` dans `.env` (sans toucher au code).

---

## 6. Mettre en ligne (exemple avec Render)

Render propose une offre gratuite pour les petits services web (à vérifier sur leur site). Elle a des limites, voir plus bas.

1. **Envoie le projet sur GitHub** (dépôt privé conseillé). Vérifie que `.env` n'est **pas** envoyé (c'est le rôle de `.gitignore`).
   ```
   git init
   git add .
   git commit -m "AHMAD AI"
   ```
   Puis crée un dépôt sur github.com et suis les 2-3 commandes qu'il te donne (`git remote add…`, `git push…`).
2. Sur **render.com** : *New → Web Service*, connecte ton dépôt GitHub.
3. Renseigne :
   - **Build Command** : `pip install -r requirements.txt`
   - **Start Command** : `gunicorn app:app`
4. Dans **Environment** (variables d'environnement), ajoute :

   | Variable | Valeur |
   |---|---|
   | `ANTHROPIC_API_KEY` | ta clé secrète |
   | `AI_PROVIDER` | `anthropic` |
   | `TRUST_PROXY` | `1` |
   | `CREATOR_NAME` | ton nom |
   | `CONTACT_EMAIL` | ton e-mail (facultatif) |

   Ne mets **pas** `FLASK_DEBUG=1` en ligne. Si le build échoue à cause de la version de Python, ajoute la variable `PYTHON_VERSION` (vérifie le format dans la documentation de Render).
5. Lance le déploiement. Render te donne une adresse en `https://…onrender.com`.

### Limites à connaître avant de partager ton site

- **Offre gratuite :** le service s'endort après environ 15 minutes sans visite ; la première requête suivante est lente.
- **Base de données :** sans « disque persistant », les fichiers sont perdus à chaque redéploiement ou redémarrage : l'historique et la mémoire disparaissent. Solutions : disque persistant (option de l'hébergeur, généralement payante, puis `DATABASE_PATH` vers ce disque) ou, plus tard, une base PostgreSQL.
- **Coût :** chaque message consomme ta clé API. Le site limite déjà à 40 messages par heure et par adresse IP (`RATE_LIMIT_PER_HOUR`). Fixe aussi une **limite de dépense** dans la console de ton fournisseur d'IA.
- **Site public = clé partagée :** tout visiteur utilise ta clé. Pour un usage privé, ne diffuse pas l'adresse, ou ajoute plus tard un système de comptes.
- **HTTPS** est fourni automatiquement par Render.

---

## 7. Erreurs fréquentes

| Message ou problème | Solution |
|---|---|
| `python n'est pas reconnu` | Réinstalle Python en cochant « Add Python to PATH », puis rouvre le terminal. |
| `ModuleNotFoundError: No module named 'flask'` | Le `venv` n'est pas activé, ou l'installation n'est pas faite : refais l'étape 3. |
| Windows bloque `venv\Scripts\activate` | Utilise l'Invite de commandes (cmd) au lieu de PowerShell. |
| `Address already in use` | Un autre programme utilise le port 5000. Lance avec un autre port : `set PORT=5001` (Windows) ou `PORT=5001 python app.py` (macOS/Linux). |
| Le bandeau « Mode local » reste affiché | La clé n'est pas lue : le fichier doit s'appeler `.env` (pas `.env.example`), être dans le dossier du projet, et le serveur doit être relancé. |
| « La clé API est refusée » | Clé mal copiée, expirée ou supprimée : crée-en une nouvelle. |
| « Le modèle … est introuvable » | Corrige `AI_MODEL` dans `.env`. |
| « Impossible de joindre le service d'IA » | Vérifie ta connexion Internet. |
| « Trop de messages envoyés » | Tu as atteint `RATE_LIMIT_PER_HOUR`. Attends ou augmente la valeur. |
| Le fichier `.env` reste invisible | Dans VS Code, il apparaît dans l'explorateur ; sous Windows, active l'affichage des fichiers cachés. |

---

## 8. Comprendre le code : par où commencer

1. `templates/chat.html` : la structure de la page de chat.
2. `static/js/chat.js` : ce qui se passe quand on clique sur Envoyer (`sendMessage`).
3. `app.py` : la route `/api/chat`.
4. `chatbot.py` : `handle_message`, le trajet complet.
5. `ai_providers.py` : comment l'IA est appelée.

Tous les fichiers contiennent des commentaires en français.

---

## 9. Ajouter des fonctions plus tard

- **Une autre IA** : nouvelle classe dans `ai_providers.py` (méthode `generate`) + une ligne dans `build_provider()`.
- **Génération d'exercices** : ajoute un module (par exemple `exercices.py`) qui prépare des instructions spéciales, une route `/api/exercices` dans `app.py`, et un bouton dans `chat.js`.
- **Catégories de conversations** : ajoute une colonne `category` dans la table `conversations` (`database.py`) et un filtre dans la barre latérale.
- **Comptes utilisateurs** : remplace le cookie anonyme (`identify_owner` dans `app.py`) par une vraie connexion.
- **Réponse en direct (mot par mot)** : possible avec le « streaming » de l'API ; plus avancé.

---

## 10. Sécurité : les bonnes habitudes

- Ne mets **jamais** une clé API dans un fichier HTML, CSS ou JavaScript.
- Ne partage jamais ton fichier `.env`.
- N'écris pas de mots de passe ni de numéros de carte dans le chat : en mode IA externe, les messages sont envoyés au fournisseur de l'IA.
- Une IA peut se tromper ou inventer (« hallucination ») : vérifie les informations importantes.
