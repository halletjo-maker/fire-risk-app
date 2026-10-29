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
| GET | `/fundamentals?id=...` | Module 3 — analyse fondamentale et score /10 |
| GET | `/technical?id=...` | Module 4 — analyse technique (MM100), score /10 et données du graphique |
| GET | `/sentiment?id=...` | Module 5 — actualités 72 h, sentiment par titre, événements, score /10 |
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
- [x] **Module 3** — Analyse fondamentale
- [x] **Module 4** — Analyse technique (MM100)
- [x] **Module 5** — Actualités et sentiment
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
- Les ETF sont proposés d'abord sur une place en euros (Amsterdam, Bruxelles, Paris, XETRA),
  y compris lors d'une recherche par ISIN.

### Analyse fondamentale (Module 3)

| Produit | Critères notés /10 (poids) | Sources |
|---|---|---|
| Action | PER (20) · croissance du CA (15) · marge opérationnelle (15) · dette nette/EBITDA (15) · free cash-flow (10) · dividende (5) · avis des analystes (20) | Yahoo Finance → consensus Boursorama → Google Finance |
| ETF | TER (30) · taille du fonds (25) · nombre de positions (20) · performance depuis le 1er janvier (15) · réplication (10) | justETF → Boursorama → Yahoo |
| Turbo / warrant | distance à la barrière (40) · levier (25) · spread achat/vente (20) · émetteur (15) · échéance (warrants) | Boursorama |
| Crypto | capitalisation (45) · liquidité (30) · offre en circulation / maximale (25) — plafonné à 8/10 | CoinGecko → Yahoo |
| Indice | non applicable (le score global reposera sur la technique et le sentiment) | — |

- Score = moyenne pondérée des critères disponibles ; la part de données trouvées est affichée.
- ETF à levier ou inverse : score plafonné à 4/10 avec avertissement.
- Résultats trimestriels dans les 7 jours : avertissement de volatilité.
- Les fondamentaux sont mis en cache 6 heures.
- **ZoneBourse** bloque les accès automatiques (HTTP 403) : il est remplacé par le
  consensus Boursorama (avis, objectif de cours, prévisions), **justETF** (ETF européens)
  et **CoinGecko** (cryptos, API publique gratuite).

### Analyse technique (Module 4)

| Critère | Poids | Lecture |
|---|---|---|
| ★ **Position vs MM100** | 35 | ✅ AU-DESSUS · ❌ EN-DESSOUS · ⚡ CROISEMENT (dans les 5 dernières séances) + écart en % et pente |
| Tendance MM50 / MM200 | 15 | moyennes alignées à la hausse ou à la baisse |
| RSI (14) | 15 | survente < 30, surachat > 70 |
| MACD (12, 26, 9) | 15 | position vs signal, croisement du jour |
| Bollinger (20, 2) | 10 | position dans les bandes |
| Volume vs moyenne 20 j | 10 | mouvement confirmé ou non par les volumes |

- Historique : Yahoo Finance (2 ans), secours Boursorama.
- Supports / résistances : plus proches plus bas / plus hauts locaux des 6 derniers mois
  (réutilisés pour les stop-loss du Module 7).
- **Turbos / warrants** : l'analyse porte sur le **sous-jacent** (ex. LVMH → MC.PA) ;
  pour un **put**, le score est inversé (10 − score), car un sous-jacent baissier lui est favorable.
- Graphique interactif : chandeliers + MM50 / MM100 / MM200 (+ Bollinger en option),
  MACD et RSI dans des panneaux séparés synchronisés, périodes 3M / 6M / 1A, infobulle,
  vue tableau des 10 dernières séances. Couleurs des moyennes validées pour le daltonisme.

### Actualités et sentiment (Module 5)

- **Sources** : Google News RSS en français (édition Belgique) et en anglais ; NewsAPI en
  plus si `NEWSAPI_KEY` est renseignée dans `.env`.
- **Sélection** : les 10 titres les plus récents (72 h) qui **citent le produit**. Les pages
  de cotation, les doublons et, en anglais, les homonymes sans contexte boursier
  (ex. la ville de Solvay, NY) sont écartés.
- **Sentiment par titre** 🟢 🟡 🔴 : lexique financier FR/EN (« plonge », « abaisse son
  objectif », « beats estimates »…), négations gérées ; les mots repérés sont affichés.
- **Score /10** = 5 + 5 × moyenne (titres de moins de 24 h plus lourds), ramené vers 5 s'il
  y a moins de 5 articles. Verdict : Positif ≥ 6 · Négatif ≤ 4.
- **Événements à venir** (30 jours) : résultats trimestriels, détachement / versement du
  dividende ; avertissement si les résultats tombent dans les 48 h.
- Produit dérivé : actualités du **sous-jacent** ; pour un **put**, score inversé.
- ETF : actualités de l'indice suivi (souvent peu nombreuses → score proche de 5).

### Choix techniques à noter
- **Vite** au lieu de Create React App (abandonné par l'équipe React) — même React, démarrage plus rapide.
- **@hello-pangea/dnd** sera utilisé pour le glisser-déposer (Module 8) : c'est la suite
  maintenue de `react-beautiful-dnd` (archivé), avec exactement la même API.
- **pandas-ta 0.4.71b0** (compatible numpy 2 / pandas 3).
