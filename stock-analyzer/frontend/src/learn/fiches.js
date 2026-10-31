// Fiches de vulgarisation. Les règles « Dans l'application » reprennent exactement le calcul
// du backend (services/technical.py, fundamentals.py, decision.py, report.py, targets.py) :
// toute modification de ces règles doit être reportée ici.

export const CATEGORIES = [
  { key: 'bases', label: 'Bien démarrer' },
  { key: 'technique', label: 'Analyse technique' },
  { key: 'fondamentale', label: 'Analyse fondamentale' },
]

export const FICHES = [
  {
    slug: 'lire-les-scores',
    category: 'bases',
    emoji: '🧭',
    title: "Lire l'analyse de l'application",
    minutes: 4,
    oneLiner: "Trois regards sur un produit (l'entreprise, son cours, l'actualité) résumés en une note sur 10 et un signal.",
    intro: [
      "Avant d'acheter, on se pose trois questions : l'entreprise est-elle solide ? Le cours est-il dans une bonne dynamique ? Que dit l'actualité ? L'application y répond avec trois analyses notées sur 10, puis les combine en un score global.",
    ],
    sections: [
      {
        title: 'Les trois analyses',
        bullets: [
          "Fondamentale : la santé de l'entreprise (valorisation, croissance, rentabilité, dette, trésorerie, dividende, avis des analystes).",
          'Technique : le comportement du cours (moyenne mobile 100 jours, tendances, RSI, MACD, Bollinger, volumes).',
          'Sentiment : le ton des actualités récentes (titres de presse positifs, neutres ou négatifs).',
        ],
      },
      {
        title: 'Le score global',
        paras: [
          'Score global = 35 % fondamental + 45 % technique + 20 % sentiment. Si une analyse ne s’applique pas (par exemple le fondamental d’un indice), son poids est réparti sur les autres.',
        ],
        bullets: [
          '7,5 ou plus : conditions favorables — signal 🟢 ACHAT.',
          'De 5 à 7,4 : prudence — signal 🟡 NEUTRE.',
          'Moins de 5 : conditions défavorables — signal 🔴 VENTE.',
          "L'onglet VENTE (pour qui détient déjà le produit) affiche 10 − score global.",
        ],
      },
      {
        title: 'Les lignes « Achat » et « Vente » des watchlists',
        bullets: [
          'Achat ≤ X : tendance haussière, achat sur repli vers la MM100 ou le support.',
          'Achat ≈ X : le cours est déjà dans la zone d’achat.',
          'Achat ≥ X : tendance baissière, attendre que le cours repasse au-dessus de la MM100 (+1 %).',
          'Vente Y : objectif de prise de bénéfice (prochaine résistance, ou estimation selon la volatilité).',
        ],
      },
    ],
    inApp: [
      'Turbo ou warrant PUT : l’analyse porte sur le sous-jacent et les scores technique et sentiment sont inversés (une baisse du sous-jacent est favorable à un put).',
      'Listes larges (IPO, Monde) : le score affiché est uniquement technique ; touche une société pour son analyse complète.',
    ],
    traps: [
      'Un score n’est pas une prédiction : un 8/10 peut baisser, un 3/10 peut monter.',
      'Un seul produit ne doit jamais représenter une grosse part de ton épargne : diversifie.',
      'Les données viennent de sources publiques gratuites : un chiffre peut être absent ou en retard.',
    ],
    keyPoints: [
      'Trois analyses, un score global pondéré, trois signaux.',
      'C’est une aide à la décision, pas un conseil en investissement.',
    ],
    related: ['moyenne-mobile-100', 'valorisation-per', 'supports-resistances-stop-loss'],
  },
  {
    slug: 'moyenne-mobile-100',
    category: 'technique',
    emoji: '📈',
    title: 'La moyenne mobile 100 jours (MM100)',
    minutes: 4,
    oneLiner: 'La moyenne des 100 derniers cours de clôture : elle gomme le bruit quotidien et montre la tendance de fond.',
    illustration: 'mm100',
    intro: [
      'Chaque jour, on additionne les cours de clôture des 100 dernières séances (environ 5 mois de Bourse) et on divise par 100. Le lendemain, on ajoute le nouveau cours et on retire le plus ancien : la moyenne « glisse », d’où son nom de moyenne mobile.',
      'Exemple : si les 100 dernières clôtures font en moyenne 50 €, la MM100 vaut 50 €. Un cours à 55 € est 10 % au-dessus de sa MM100.',
    ],
    sections: [
      {
        title: 'Comment la lire',
        bullets: [
          'Cours au-dessus de la MM100 : tendance de fond haussière.',
          'Cours en dessous : tendance de fond baissière.',
          'Le cours traverse la MM100 : possible changement de tendance (croisement haussier ou baissier).',
          'La pente compte aussi : une MM100 qui monte confirme la hausse.',
        ],
      },
      {
        title: 'Ses cousines : MM50 et MM200',
        paras: [
          'La MM50 réagit plus vite (court terme), la MM200 plus lentement (long terme). Quand la MM50 passe au-dessus de la MM200, on parle de « croix dorée » (plutôt positif) ; l’inverse s’appelle « croix de la mort ».',
        ],
      },
    ],
    inApp: [
      'C’est le critère principal : 35 % du score technique.',
      'Croisement haussier dans les 5 dernières séances : 8/10. Croisement baissier : 2,5/10.',
      'Au-dessus : 8,5/10 si l’écart est de moins de 10 %, 7,5 entre 10 et 20 %, 6 au-delà de 20 % (trop éloigné, risque de correction).',
      'En dessous : 3,5/10 jusqu’à −5 %, 2 entre −5 et −15 %, 1,5 au-delà de −15 %.',
      'Pente de la MM100 sur 10 séances : +0,5 si elle monte, −0,5 si elle baisse.',
      'Alignement des moyennes (15 % du score technique) : 9/10 si cours > MM50 > MM100 > MM200, 7 si MM50 > MM200, 5 si le cours repasse au-dessus de la MM50, 3 sinon.',
      'Les cours « Achat ≤ / ≥ » des watchlists sont calculés à partir de la MM100.',
    ],
    traps: [
      'C’est un indicateur en retard : il confirme une tendance, il ne l’annonce pas.',
      'Dans un marché sans direction, le cours croise souvent la moyenne : faux signaux à répétition.',
      'Il faut au moins 100 séances d’historique : pour une introduction en Bourse récente, l’application affiche « Historique trop court ».',
    ],
    keyPoints: [
      'Au-dessus = le vent souffle dans le dos ; en dessous = vent de face.',
      'Un croisement récent mérite attention, surtout s’il est confirmé par les volumes et le MACD.',
    ],
    related: ['macd', 'supports-resistances-stop-loss', 'rsi'],
  },
  {
    slug: 'rsi',
    category: 'technique',
    emoji: '🌡️',
    title: 'Le RSI : le thermomètre du marché',
    minutes: 3,
    oneLiner: 'Une note de 0 à 100 qui mesure la vigueur des hausses par rapport aux baisses des 14 dernières séances.',
    illustration: 'rsi',
    intro: [
      'Le RSI (Relative Strength Index, inventé par J. Welles Wilder en 1978) compare la moyenne des hausses à la moyenne des baisses sur 14 séances : RSI = 100 − 100 / (1 + hausses moyennes / baisses moyennes).',
      'S’il n’y a eu que des hausses, il tend vers 100 ; que des baisses, vers 0 ; autant de hausses que de baisses, il est proche de 50.',
    ],
    sections: [
      {
        title: 'Comment le lire',
        bullets: [
          'Au-dessus de 70 : « surachat » — le cours a beaucoup monté, un repli est fréquent.',
          'Sous 30 : « survente » — le cours a beaucoup baissé, un rebond technique est possible.',
          'Entre 45 et 70 : dynamique saine.',
        ],
      },
    ],
    inApp: [
      '15 % du score technique.',
      'RSI < 30 : 6/10 (rebond possible) · 30 à 45 : 5/10 (momentum faible) · 45 à 60 : 7/10 (sain) · 60 à 70 : 7,5/10 · 70 et plus : 3,5/10 (risque de repli).',
    ],
    traps: [
      'Dans une forte tendance haussière, le RSI peut rester au-dessus de 70 pendant des semaines : surachat ne veut pas dire « vends tout de suite ».',
      'Un RSI bas sur une entreprise en difficulté peut continuer à baisser : la survente n’est pas une garantie de rebond.',
      'Divergence : quand le cours fait un nouveau sommet mais pas le RSI, la hausse s’essouffle souvent.',
    ],
    keyPoints: [
      '70 = chaud, 30 = froid, 50 = équilibre.',
      'À utiliser avec la tendance de fond (MM100), jamais seul.',
    ],
    related: ['moyenne-mobile-100', 'macd', 'bollinger-volumes'],
  },
  {
    slug: 'macd',
    category: 'technique',
    emoji: '🔀',
    title: 'Le MACD : la dynamique en marche',
    minutes: 3,
    oneLiner: 'L’écart entre une moyenne rapide et une moyenne lente du cours, pour voir si la dynamique accélère ou ralentit.',
    illustration: 'macd',
    intro: [
      'MACD signifie Moving Average Convergence Divergence. On calcule une moyenne mobile exponentielle sur 12 séances (rapide) et une sur 26 séances (lente). Le MACD est la différence entre les deux. Sa propre moyenne sur 9 séances s’appelle la ligne de signal.',
      'L’histogramme (en barres) montre l’écart entre le MACD et son signal : des barres qui grandissent indiquent une dynamique qui accélère.',
    ],
    sections: [
      {
        title: 'Comment le lire',
        bullets: [
          'MACD au-dessus de son signal : dynamique positive.',
          'MACD sous son signal : dynamique négative.',
          'Le croisement des deux lignes est un signal suivi par beaucoup d’investisseurs.',
        ],
      },
    ],
    inApp: [
      '15 % du score technique, réglages classiques (12, 26, 9).',
      'MACD au-dessus du signal : 8/10 si l’écart grandit, 7/10 sinon.',
      'MACD sous le signal : 4,5/10 si l’écart se réduit (la baisse s’atténue), 3/10 sinon.',
      'Un croisement du jour est signalé dans le commentaire.',
    ],
    traps: [
      'Comme toute moyenne, il réagit avec retard.',
      'En marché sans tendance, les croisements se multiplient et se contredisent.',
    ],
    keyPoints: [
      'MACD > signal = l’accélérateur est enfoncé.',
      'Plus fiable quand il va dans le même sens que la MM100.',
    ],
    related: ['moyenne-mobile-100', 'rsi'],
  },
  {
    slug: 'bollinger-volumes',
    category: 'technique',
    emoji: '🎯',
    title: 'Bandes de Bollinger et volumes',
    minutes: 3,
    oneLiner: 'Une enveloppe autour du cours qui s’élargit quand le marché s’agite, et le volume qui confirme (ou non) les mouvements.',
    illustration: 'bollinger',
    intro: [
      'Les bandes de Bollinger (John Bollinger, années 1980) entourent la moyenne mobile 20 jours, à 2 écarts-types au-dessus et en dessous. Environ 9 cours sur 10 restent à l’intérieur.',
      'Les bandes s’écartent quand la volatilité augmente et se resserrent quand le marché se calme — un resserrement précède souvent un mouvement plus marqué.',
    ],
    sections: [
      {
        title: 'Et le volume ?',
        paras: [
          'Le volume est le nombre de titres échangés dans la journée. Une hausse sur de gros volumes est plus crédible : beaucoup d’investisseurs y participent. Une baisse sur de gros volumes traduit une vraie pression vendeuse.',
        ],
      },
    ],
    inApp: [
      'Bollinger : 10 % du score technique. Au-dessus de la bande haute : 4/10 (excès à la hausse) · moitié haute : 7/10 · moitié basse : 5/10 · sous la bande basse : 5,5/10 (excès à la baisse, rebond possible).',
      'Volume : 10 % du score technique. Volume du jour au moins 1,5 × la moyenne 20 jours : 8,5/10 si le cours monte, 3/10 s’il baisse. Sinon 6/10.',
      'Les bandes peuvent être affichées sur le graphique de l’analyse technique.',
    ],
    traps: [
      'Toucher la bande haute ne signifie pas « vendre » : dans une forte hausse, le cours peut longer la bande haute.',
      'Un volume exceptionnel peut venir d’un événement ponctuel (résultats, rachat, indice) : lis l’actualité.',
    ],
    keyPoints: [
      'Bandes larges = marché agité ; bandes serrées = calme avant un mouvement.',
      'Pas de volume, pas de conviction.',
    ],
    related: ['rsi', 'supports-resistances-stop-loss'],
  },
  {
    slug: 'supports-resistances-stop-loss',
    category: 'technique',
    emoji: '🛡️',
    title: 'Supports, résistances et stop-loss',
    minutes: 4,
    oneLiner: 'Les « planchers » et « plafonds » où le cours a tendance à rebondir ou caler, et le stop-loss qui limite les pertes.',
    illustration: 'levels',
    intro: [
      'Un support est une zone de prix où la baisse s’est arrêtée, parce que des acheteurs s’y sont manifestés. Une résistance est une zone où la hausse a calé, parce que des vendeurs en ont profité.',
      'Quand un support est cassé, il devient souvent une résistance (et inversement) : les investisseurs se souviennent des prix.',
    ],
    sections: [
      {
        title: 'Le stop-loss',
        paras: [
          'Un stop-loss est un ordre de vente automatique placé chez ton courtier : si le cours tombe sous un prix fixé, l’action est vendue. Il ne garantit pas de gagner, il empêche une petite perte de devenir grande.',
        ],
      },
    ],
    inApp: [
      'Support et résistance = plus proches points bas et hauts marquants des 6 derniers mois (130 séances), sous et au-dessus du cours.',
      'Rapport : stop-loss conseillé 1 % sous le support s’il est entre −3 % et −12 % du cours ; sinon, le pourcentage (−5, −8 ou −12 %) le plus proche de 2 × la variation moyenne quotidienne (ATR 14).',
      'Watchlists : objectif « Vente » = prochaine résistance si elle laisse au moins 2 % de marge, sinon 3 × la variation moyenne quotidienne (au moins +5 %).',
      'Portefeuilles fictifs : stop suiveur — il monte avec le plus haut atteint depuis l’achat pour protéger les gains.',
    ],
    traps: [
      'Un stop trop serré te fait sortir à cause du simple bruit du marché.',
      'Si le cours ouvre bien plus bas que ton stop (mauvaise nouvelle la nuit), tu seras vendu au premier prix disponible, plus bas que prévu.',
      'Turbos : le stop doit se déclencher bien avant la barrière désactivante.',
    ],
    keyPoints: [
      'Décide de ta porte de sortie avant d’entrer.',
      'Support = plancher ; résistance = plafond ; un niveau cassé change de rôle.',
    ],
    related: ['moyenne-mobile-100', 'bollinger-volumes', 'lire-les-scores'],
  },
  {
    slug: 'valorisation-per',
    category: 'fondamentale',
    emoji: '🏷️',
    title: 'Le PER : est-ce cher ?',
    minutes: 4,
    oneLiner: 'Le prix de l’action divisé par le bénéfice par action : combien d’années de bénéfices tu paies.',
    intro: [
      'PER signifie Price Earnings Ratio (en français : cours / bénéfice). Une action à 100 € dont l’entreprise gagne 5 € par action a un PER de 20 : tu paies 20 années de bénéfices actuels.',
      'Un PER élevé n’est pas forcément mauvais : le marché anticipe une forte croissance des bénéfices. Un PER bas n’est pas forcément une affaire : le marché anticipe peut-être un déclin.',
    ],
    sections: [
      {
        title: 'Comment le lire',
        bullets: [
          'Compare le PER à celui des concurrents du même secteur : une banque a souvent un PER de 8 à 12, une entreprise technologique en croissance de 25 à 40.',
          'Compare-le à la croissance : un PER de 30 avec des bénéfices qui doublent en 3 ans peut être raisonnable.',
          'Le PER « attendu » utilise les bénéfices prévus de l’année prochaine ; le PER « historique », ceux de l’année passée.',
        ],
      },
      {
        title: 'L’avis des analystes',
        paras: [
          'Des analystes de banques publient un objectif de cours à 12 mois et une recommandation (acheter, conserver, vendre). L’écart entre leur objectif moyen et le cours actuel donne une idée de leur optimisme.',
        ],
      },
    ],
    inApp: [
      'PER : 20 % du score fondamental, PER attendu en priorité, sinon historique.',
      'PER < 8 : 8/10 (très bon marché, mais vérifier qu’il n’y a pas de problème caché) · 8–12 : 9/10 · 12–16 : 8/10 · 16–20 : 7/10 · 20–25 : 6/10 · 25–35 : 4,5/10 · 35–50 : 3/10 · 50 et plus : 2/10.',
      'Entreprise en perte : 2/10 (le PER n’a pas de sens).',
      'Avis des analystes : 20 % du score fondamental (10 % s’ils sont moins de 3), selon le potentiel jusqu’à leur objectif de cours et leur recommandation moyenne.',
    ],
    traps: [
      'Le « piège de valeur » : un PER très bas peut cacher des bénéfices sur le point de s’effondrer.',
      'Entreprises cycliques (matières premières, automobile) : leur PER est souvent le plus bas au sommet du cycle, juste avant la baisse.',
      'Les analystes se trompent aussi, et révisent souvent leurs objectifs après coup.',
    ],
    keyPoints: [
      'PER = années de bénéfices payées.',
      'Toujours le comparer au secteur et à la croissance.',
    ],
    related: ['sante-financiere', 'lire-les-scores'],
  },
  {
    slug: 'sante-financiere',
    category: 'fondamentale',
    emoji: '🩺',
    title: 'La santé financière d’une entreprise',
    minutes: 5,
    oneLiner: 'Croissance, rentabilité, dette, trésorerie et dividende : le bilan de santé derrière le cours.',
    intro: [
      'Une entreprise solide vend de plus en plus, gagne de l’argent sur chaque vente, n’est pas étranglée par ses dettes et génère du cash. C’est ce que mesurent les critères fondamentaux de l’application.',
    ],
    sections: [
      {
        title: 'Les cinq indicateurs',
        bullets: [
          'Croissance du chiffre d’affaires : l’évolution des ventes sur un an.',
          'Marge opérationnelle : ce qu’il reste du chiffre d’affaires après les coûts d’exploitation (résultat opérationnel / chiffre d’affaires). 20 % de marge = 20 € gagnés sur 100 € de ventes.',
          'Dette nette / EBITDA : le nombre d’années de bénéfice d’exploitation (avant amortissements) qu’il faudrait pour rembourser les dettes, trésorerie déduite.',
          'Rendement du free cash-flow : le cash réellement généré, après investissements, rapporté à la valeur boursière.',
          'Rendement du dividende : le dividende annuel rapporté au cours.',
        ],
      },
    ],
    inApp: [
      'Croissance (15 %) : moins de −10 % : 2/10 · −10 à 0 % : 4 · 0 à 5 % : 5,5 · 5 à 10 % : 7 · 10 à 20 % : 8,5 · 20 % et plus : 9,5.',
      'Marge opérationnelle (15 %) : négative : 1,5/10 · 0 à 5 % : 4 · 5 à 10 % : 5,5 · 10 à 15 % : 7 · 15 à 25 % : 8,5 · 25 % et plus : 9,5.',
      'Dette nette / EBITDA (15 %) : plus de trésorerie que de dettes : 9,5/10 · moins de 1 × : 9 · 1 à 2 × : 7,5 · 2 à 3 × : 5,5 · 3 à 4 × : 3,5 · 4 × et plus : 2. Non calculé pour les banques et assurances.',
      'Free cash-flow (10 %) : négatif : 2/10 · 0 à 2 % : 5 · 2 à 4 % : 6,5 · 4 à 6 % : 8 · 6 % et plus : 9.',
      'Dividende (5 %) : aucun : 5/10 (normal pour une valeur de croissance) · moins de 2 % : 6,5 · 2 à 4 % : 7,5 · 4 à 7 % : 8 · 7 % et plus : 6 (vérifier qu’il est soutenable) · dividende supérieur aux bénéfices : 3.',
    ],
    traps: [
      'Une forte croissance avec des pertes qui se creusent n’est pas une bonne nouvelle.',
      'Un dividende très élevé est parfois le signe d’un cours qui s’est effondré, et le dividende risque d’être réduit.',
      'Les chiffres sont annuels : un mauvais trimestre peut ne pas encore apparaître.',
    ],
    keyPoints: [
      'Vendre plus, gagner sur chaque vente, peu de dettes, du cash : la recette d’une entreprise solide.',
      'Aucun critère ne suffit seul : regarde l’ensemble.',
    ],
    related: ['valorisation-per', 'lire-les-scores'],
  },
]

export const FICHES_BY_SLUG = Object.fromEntries(FICHES.map((f) => [f.slug, f]))

// Critère de l'analyse → fiche qui l'explique (petits « ? » de l'outil)
export const CRITERION_FICHE = {
  mm100: 'moyenne-mobile-100',
  trend: 'moyenne-mobile-100',
  rsi: 'rsi',
  macd: 'macd',
  bollinger: 'bollinger-volumes',
  volume: 'bollinger-volumes',
  per: 'valorisation-per',
  analysts: 'valorisation-per',
  growth: 'sante-financiere',
  margin: 'sante-financiere',
  debt: 'sante-financiere',
  fcf: 'sante-financiere',
  dividend: 'sante-financiere',
}
