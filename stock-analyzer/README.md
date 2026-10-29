# 📈 Analyse Boursière

Application web d'analyse boursière personnelle : recherche d'un produit (action, ETF, turbo,
warrant, crypto, indice), score global /10, recommandation d'achat ou de vente, stop-loss,
watchlists multiples et alertes par mail.

Elle tourne **sur ton PC** et reste accessible **depuis ton téléphone** via le réseau local (Wi-Fi).

> ⚠️ Les informations produites sont indicatives et ne constituent pas un conseil en
> investissement au sens de la directive MiFID II.

---

## 🧱 Stack

| Partie | Technologie |
|---|---|
| Backend | Python 3.11+ · FastAPI · APScheduler · SQLite |
| Données | yfinance · Google Finance / Boursorama / ZoneBourse (scraping) · Google News RSS · NewsAPI |
| Analyse technique | pandas-ta |
| Mail | smtplib (Python natif) |
| Frontend | React 18 · Vite · TailwindCSS · Recharts · lucide-react |

---

## ✅ Prérequis

- **Python 3.11 ou plus récent** — https://www.python.org/downloads/
  (Windows : cocher *« Add Python to PATH »* à l'installation)
- **Node.js 20 ou plus récent** — https://nodejs.org/ (version LTS)
- Git (facultatif)

Vérifier :
```bash
python --version     # ou python3 --version
node --version
```

---

## 🚀 Installation (une seule fois)

### 1. Configuration
```bash
cd stock-analyzer
cp .env.example .env          # Windows : copy .env.example .env
```
Ouvre `.env` et complète au minimum les lignes SMTP si tu veux les alertes mail
(voir [Configurer Gmail](#-configurer-lenvoi-de-mails-gmail)). Tout le reste fonctionne sans.

### 2. Backend
```bash
cd backend
python -m venv .venv
# macOS / Linux :
source .venv/bin/activate
# Windows (PowerShell) :
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 3. Frontend
```bash
cd ../frontend
npm install
```

---

## ▶️ Lancement

**Le plus simple :**
- Windows : double-clic sur `start.bat`
- macOS / Linux : `./start.sh`

**Ou manuellement, dans deux terminaux :**
```bash
# Terminal 1 — backend (http://localhost:8000)
cd backend
source .venv/bin/activate            # Windows : .venv\Scripts\activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2 — frontend (http://localhost:3000)
cd frontend
npm run dev
```

Puis ouvre **http://localhost:3000**.
La documentation interactive de l'API est sur **http://localhost:8000/docs**.

---

## 📱 Accès depuis le téléphone (réseau local)

1. Le PC et le téléphone doivent être sur le **même Wi-Fi**.
2. Trouve l'adresse IP du PC :
   - Windows : `ipconfig` → ligne *Adresse IPv4* (ex. `192.168.1.20`)
   - macOS : `ipconfig getifaddr en0`
   - Linux : `hostname -I`
3. Sur le téléphone, ouvre `http://192.168.1.20:3000`.
4. Si ça ne charge pas : autorise **Python** et **Node.js** dans le pare-feu
   (Windows le demande au premier lancement → cocher *Réseaux privés*).

Le téléphone n'a besoin que du port **3000** : le frontend relaie les appels `/api/...` vers le
backend (port 8000) de la même machine.

Pense à mettre cette adresse dans `APP_PUBLIC_URL` du `.env` pour que les liens des mails
d'alerte fonctionnent depuis le téléphone.

---

## ✉️ Configurer l'envoi de mails (Gmail)

1. Active la **validation en 2 étapes** sur ton compte Google.
2. Va sur https://myaccount.google.com/apppasswords et crée un mot de passe d'application.
3. Dans `.env` :
   ```env
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USER=ton_mail@gmail.com
   SMTP_PASSWORD=xxxx xxxx xxxx xxxx
   SMTP_FROM=ton_mail@gmail.com
   ```
Outlook / Hotmail : `SMTP_HOST=smtp-mail.outlook.com`, port `587`.

L'encart **« État du serveur »** de l'application indique si le SMTP est bien détecté.

---

## 🗂️ Structure du projet

```
stock-analyzer/
├── .env.example            Variables de configuration (à copier en .env)
├── start.sh / start.bat    Lancement en un clic
├── backend/
│   ├── requirements.txt
│   ├── data/               Base SQLite (créée automatiquement)
│   ├── app/
│   │   ├── main.py         Application FastAPI (CORS, démarrage, routes)
│   │   ├── config.py       Lecture du .env + constantes
│   │   ├── database.py     Connexion SQLite + schéma complet
│   │   ├── scheduler.py    Tâches de fond APScheduler (toutes les 15 min)
│   │   ├── deps.py         Identification de l'utilisateur (en-tête X-User-Email)
│   │   ├── routers/        health · users · watchlists · analyze
│   │   └── services/
│   │       ├── sources/    yfinance, scraping, actualités (Modules 2-5)
│   │       ├── analysis/   scores, décision, rapport (Modules 3-7)
│   │       └── mail/       alertes SMTP (Module 9)
│   └── tests/              Tests pytest
└── frontend/
    ├── vite.config.js      Port 3000, accès LAN, relais /api → backend
    ├── tailwind.config.js  Thème sombre (#0D1117, #00FF88, #FF4444)
    └── src/
        ├── App.jsx         Démarrage : utilisateur mémorisé ou écran d'accueil
        ├── lib/api.js      Client HTTP
        └── components/     LoginScreen, AppLayout, Sidebar, MobileHeader,
                            WatchlistSelector, MainArea, BackendStatus
```

### Base de données

| Table | Contenu |
|---|---|
| `users` | Utilisateurs (identifiés par mail) |
| `app_settings` | Utilisateur actif mémorisé |
| `watchlists` | Nom, couleur (8 choix), ordre |
| `watchlist_items` | Produits suivis + dernier prix / score / signal |
| `alerts` | Alertes par produit : type, activée, fréquence, jeton de désinscription |
| `analysis_history` | Historique des analyses (scores, verdict, sources, rapport) |
| `data_cache` | Cache des réponses des sources (limite le scraping) |

Supprimer une watchlist supprime ses produits ; supprimer un produit supprime ses alertes
(cascade SQLite).

### API (étape actuelle)

| Méthode | Route | Rôle |
|---|---|---|
| GET | `/health` | État : base, tâches de fond, configuration |
| POST | `/users/login` | Identification par mail (création si nouveau) |
| GET | `/users/current` | Utilisateur mémorisé |
| POST | `/users/logout` | Changer d'utilisateur |
| GET | `/users/known` | Comptes déjà utilisés (choix rapide) |
| GET | `/users/me` | Profil + statistiques (en-tête `X-User-Email`) |
| GET / POST | `/watchlists` | Lister / créer (en-tête `X-User-Email`) |
| GET | `/search?q=...` | Propositions (nom, ticker, ISIN, mot-clé) avec type détecté |
| GET | `/quote?id=...` | Cours d'un produit (`yf:NOW`, `bo:/bourse/...`) avec fallback |
| GET | `/analyze?q=...` | Identification + cours (+ enregistrement dans l'historique). Scores aux Modules 3 à 6 |

---

## 🧪 Tests

```bash
cd backend
source .venv/bin/activate
python -m pytest -q
```

---

## 🗺️ Avancement

- [x] **Étape 0** — Structure, backend FastAPI, SQLite, APScheduler, layout React
- [x] **Module 1** — Identification utilisateur (profil, comptes récents)
- [x] **Module 2** — Recherche et identification du produit
- [ ] Module 3 — Analyse fondamentale
- [ ] Module 4 — Analyse technique (MM100)
- [ ] Module 5 — Actualités et sentiment
- [ ] Module 6 — Décision Achat / Vente
- [ ] Module 7 — Rapport justificatif
- [ ] Module 8 — Watchlists multiples
- [ ] Module 9 — Alertes mail

### Sources de données (Module 2)

| Ordre | Source | Utilisée pour |
|---|---|---|
| 1 | Yahoo Finance (yfinance) | Actions, ETF, crypto, indices — recherche par nom, ticker ou ISIN |
| 2 | Google Finance | Secours si Yahoo ne répond pas (prix + variation) |
| 3 | Boursorama | Turbos et warrants (émetteur, barrière, levier, parité…) + dernier secours |

- Si une source échoue, la suivante est essayée sans erreur visible ; l'interface indique la
  source utilisée (✓) et celles qui n'ont pas répondu (barrées).
- La variation du jour est **recalculée** à partir de l'historique : la « clôture veille »
  fournie directement par Yahoo est parfois fausse.
- Les cryptos sont proposées d'abord en **EUR** (BTC-EUR avant BTC-USD).
- Un délai de `SCRAPING_DELAY_SECONDS` est respecté entre deux requêtes vers un même site,
  et les résultats sont mis en cache (recherche : 30 min, cours : 1 min).
- ZoneBourse (fondamentaux européens) sera branché au Module 3.

### Choix techniques à noter
- **Vite** au lieu de Create React App (abandonné par l'équipe React) — même React, démarrage plus rapide.
- **@hello-pangea/dnd** sera utilisé pour le glisser-déposer (Module 8) : c'est la suite
  maintenue de `react-beautiful-dnd` (archivé), avec exactement la même API.
- **pandas-ta 0.4.71b0** (compatible numpy 2 / pandas 3).
