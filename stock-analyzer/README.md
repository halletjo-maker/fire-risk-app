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
Ensuite : **Mon profil → Alertes mail → « Mail de test »**.

Tant que le SMTP n'est pas configuré, les alertes ne sont pas perdues : elles apparaissent
dans l'historique (profil) et sont enregistrées en fichiers `.eml` dans `backend/data/outbox/`.

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
| PATCH / DELETE | `/watchlists/{id}` | Renommer, changer la couleur / supprimer (produits + alertes) |
| POST | `/watchlists/{id}/duplicate` | Dupliquer (produits copiés, alertes non copiées) |
| GET / POST | `/watchlists/{id}/items` | Produits suivis / ajouter un produit (score calculé en arrière-plan) |
| DELETE | `/watchlists/{id}/items/{item}` | Retirer un produit (ses alertes sont supprimées) |
| PUT | `/watchlists/{id}/items/order` | Nouvel ordre (glisser-déposer) |
| POST | `/watchlists/{id}/refresh` | Rafraîchissement immédiat |
| GET / PUT | `/alerts/item/{item}` | Alertes d'un produit (5 types, activée, fréquence) |
| GET | `/alerts/history` | Dernières alertes déclenchées |
| POST | `/alerts/test` | Envoie un mail de test (vérifie le SMTP) |
| POST | `/alerts/check` | Vérifie les alertes tout de suite |
| GET | `/alerts/unsubscribe/{jeton}` | Lien de désinscription (pied de mail) |
| GET | `/search?q=...` | Propositions (nom, ticker, ISIN, mot-clé) avec type détecté |
| GET | `/quote?id=...` | Cours d'un produit (`yf:NOW`, `bo:/bourse/...`) avec fallback |
| GET | `/fundamentals?id=...` | Module 3 — analyse fondamentale et score /10 |
| GET | `/technical?id=...` | Module 4 — analyse technique (MM100), score /10 et données du graphique |
| GET | `/sentiment?id=...` | Module 5 — actualités 72 h, sentiment par titre, événements, score /10 |
| GET | `/decision?id=...` | Module 6 — score global, décision ACHAT / VENTE (+ historique) |
| GET | `/report?id=...` | Module 7 — rapport justificatif complet |
| GET | `/analyze?q=...` | Identification + cours (+ enregistrement dans l'historique). Scores aux Modules 3 à 6 |

---

## 📱 Démo hors ligne

Une version de démonstration, sans serveur, peut être générée en un seul fichier HTML :
l'API est simulée dans la page (`frontend/src/demo/mockApi.js`) à partir de réponses réelles
enregistrées, injectées dans `window.__DEMO_DATA__`. Compte, watchlists et alertes y sont
conservés dans le navigateur ; aucun mail n'est envoyé et les cours ne sont pas mis à jour.

```bash
cd frontend
npm run build:demo        # → dist-demo/index.html (il reste à y injecter les données)
```

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
- [x] **Module 6** — Décision Achat / Vente
- [x] **Module 7** — Rapport justificatif
- [x] **Module 8** — Watchlists multiples
- [x] **Module 9** — Alertes mail

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

### Décision (Module 6)

**Score global = Fondamental × 0,35 + Technique × 0,45 + Sentiment × 0,20**

| Score | Onglet ACHAT | Onglet VENTE (score de vente = 10 − score global) |
|---|---|---|
| ≥ 7,5 | ✅ CONDITIONS FAVORABLES À L'ACHAT | ✅ CONDITIONS FAVORABLES À LA VENTE |
| 5 à 7,4 | ⚠️ PRUDENCE | ⚠️ PRUDENCE (conserver avec stop-loss) |
| < 5 | ❌ CONDITIONS DÉFAVORABLES + **avertissement fort** | ❌ CONDITIONS DÉFAVORABLES À LA VENTE (conserver) |

- Analyse non applicable (ex. fondamental d'un indice) : poids redistribués et signalés.
- Points d'appui / de vigilance en langage clair (position vs MM100, qualité, actualité),
  alerte si fondamental et technique divergent de 3 points ou plus, et si des résultats
  tombent dans les 48 h.
- Signal des watchlists : 🟢 ACHAT ≥ 7,5 · 🟡 NEUTRE · 🔴 VENTE < 5.
- L'enchaînement complet (`services/analysis.py`) est réutilisé par les watchlists et les
  alertes ; chaque décision est enregistrée dans `analysis_history`.

### Rapport justificatif (Module 7)

- **Résumé exécutif** en 3 phrases (score et verdict, tendance vs MM100 + qualité, actualité / résultats).
- **Forces / faiblesses** : critères notés ≥ 7 / ≤ 4 des trois analyses.
- **Position vs MM100** expliquée en langage clair.
- **Stop-loss** : 1 % sous le support technique, −5 %, −8 %, −12 %. Le niveau ★ conseillé est le
  support s'il est entre −3 % et −12 %, sinon le % le plus proche de 2 × la volatilité
  quotidienne (ATR 14). Turbos : stop calculé sur le support/la résistance du sous-jacent
  et traduit en prix du turbo ; volatilité multipliée par le levier.
- **3 alternatives** cliquables : même secteur (valeurs proches selon Yahoo, la mieux placée
  techniquement), ETF sectoriel MSCI World en euros (Xtrackers, XETRA) ou ETF monde,
  valeur défensive cotée en euros (Ahold Delhaize, Sanofi, Iberdrola, Unilever, Elia).
- **Sources + horodatage + avertissement MiFID II** ; bouton « Partager » (texte copié ou
  partage natif sur téléphone).

### Watchlists (Module 8)

- Watchlists illimitées, nom + couleur (8 choix) ; créer, renommer, dupliquer, supprimer
  (confirmation « Supprimer la watchlist [NOM] et ses [X] produits ? »).
- Ajout depuis la fiche produit (bouton « Ajouter à une watchlist », création possible à la volée).
- Chaque produit : 🟢 achat (≥ 7,5) · 🟡 neutre · 🔴 vente (< 5), prix, variation du jour,
  score global /10 ; 🔔 si des alertes sont actives.
- Rafraîchissement : tâche de fond APScheduler toutes les 15 min (chaque produit analysé une
  seule fois même s'il est dans plusieurs watchlists) + rechargement automatique de l'écran.
- Retrait : ✕ (au survol sur PC, toujours visible sur mobile) avec confirmation ; les alertes
  du produit sont supprimées.
- Glisser-déposer : `@hello-pangea/dnd` (suite maintenue de `react-beautiful-dnd`, même API),
  au doigt, à la souris ou au clavier (Espace + flèches).
- PC : barre latérale avec chaque watchlist dépliable (menu déroulant de ses produits) ;
  mobile : sélecteur en haut d'écran, watchlist affichée en premier.

### Alertes mail (Module 9)

| Type | Se déclenche quand… |
|---|---|
| 🚨 Signal fort | le score global **passe** à 7,5/10 ou plus |
| 📉 Alerte baisse | le score global **passe** sous 5/10 |
| 📊 Croisement MM100 | le prix croise sa MM100 (hausse ou baisse) |
| 📰 Actualité importante | le sentiment des titres passe sous 3/10 |
| 💰 Résultats à venir | des résultats trimestriels tombent dans moins de 48 h (une fois par date) |

- Réglage par produit (🔔 dans la watchlist) : chaque type activable séparément, fréquence
  max. **immédiate · 1×/jour · 1×/semaine** (une alerte trop rapprochée reste en attente et
  part à la fin du délai si la condition tient toujours).
- Un mail part quand la condition **devient** vraie, pas à chaque vérification.
- Vérification toutes les 15 min (APScheduler), 3 min après le rafraîchissement des watchlists.
- Mail : objet `[SIGNAL ACHAT ✅] ServiceNow (NOW) — Score 8,2/10`, résumé en 5 lignes,
  bouton « Voir l'analyse complète » (`APP_PUBLIC_URL/?analyse=…`), lien de désinscription.
- Envoi : `smtplib` (STARTTLS port 587 ou SSL port 465), paramètres dans `.env`.

### Choix techniques à noter
- **Vite** au lieu de Create React App (abandonné par l'équipe React) — même React, démarrage plus rapide.
- **@hello-pangea/dnd** pour le glisser-déposer : suite maintenue de `react-beautiful-dnd`
  (archivé), avec exactement la même API.
- **pandas-ta 0.4.71b0** (compatible numpy 2 / pandas 3).
