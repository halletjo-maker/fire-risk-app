// Fiches de vulgarisation. Les règles « Dans l'application » reprennent exactement le calcul
// du backend (services/technical.py, fundamentals.py, decision.py, report.py, targets.py) :
// toute modification de ces règles doit être reportée ici.

export const CATEGORIES = [
  { key: 'bases', label: 'Bien démarrer' },
  { key: 'produits', label: 'Les produits' },
  { key: 'technique', label: 'Analyse technique' },
  { key: 'fondamentale', label: 'Analyse fondamentale' },
  { key: 'actualites', label: 'Actualités' },
  { key: 'fiscalite', label: 'Fiscalité belge' },
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
  {
    slug: 'diversifier-gerer-risque',
    category: 'bases',
    emoji: '⚖️',
    title: 'Diversifier et gérer le risque',
    minutes: 4,
    oneLiner: 'Ne jamais tout miser sur un seul produit, décider à l’avance combien on accepte de perdre, et laisser le temps faire son travail.',
    intro: [
      'Personne, ni toi ni un algorithme, ne sait ce que fera une action demain. La seule chose que tu contrôles vraiment, c’est le risque que tu prends : combien tu places, où, et quand tu acceptes de couper une perte.',
    ],
    sections: [
      {
        title: 'Les règles de bon sens',
        bullets: [
          'Diversifie : plusieurs entreprises, plusieurs secteurs, plusieurs zones (Europe, États-Unis, Asie). Un ETF monde le fait en un seul achat.',
          'Limite chaque ligne : une seule action ne devrait représenter qu’une petite part de ton portefeuille (souvent 5 à 10 %).',
          'Décide ta sortie avant d’entrer : un stop-loss pour limiter la perte, un objectif pour prendre ton bénéfice.',
          'Garde une épargne de précaution à part : n’investis en Bourse que l’argent dont tu n’auras pas besoin avant plusieurs années.',
          'Les frais grignotent la performance : trop d’allers-retours coûtent cher.',
        ],
      },
      {
        title: 'Pourquoi les pertes font si mal',
        paras: [
          'Perdre 50 % demande ensuite +100 % pour revenir au point de départ ; perdre 20 % demande +25 %. Couper tôt une petite perte est donc beaucoup plus facile à rattraper qu’une grosse.',
        ],
      },
    ],
    inApp: [
      'Portefeuilles fictifs : au plus 10 lignes d’environ 10 % chacune, stop suiveur, pas de rachat d’un titre vendu depuis moins de 5 jours, frais estimés 0,1 % par ordre (1 € minimum).',
      'Filtre de marché : aucun nouvel achat quand l’ETF MSCI World est sous sa MM100 (marché mondial baissier) ; les ventes continuent.',
      'Liste « Monde » : environ un tiers Amériques, un tiers Europe, un tiers Asie-Pacifique.',
      'Rapport mensuel : comparaison avec un ETF MSCI World, pour savoir si la méthode fait mieux qu’un placement passif.',
    ],
    traps: [
      'Plusieurs actions du même secteur (par exemple cinq valeurs technologiques américaines) ne font pas une vraie diversification.',
      'Déplacer son stop-loss vers le bas « pour laisser une chance » transforme une petite perte en grosse perte.',
      'Juger une méthode sur quelques jours : il faut plusieurs mois et la comparer à un repère (MSCI World).',
    ],
    keyPoints: [
      'Diversifier, limiter chaque ligne, décider sa sortie à l’avance.',
      'Une perte de 50 % demande +100 % pour être effacée.',
    ],
    related: ['supports-resistances-stop-loss', 'produits-action-etf-crypto', 'lire-les-scores'],
  },
  {
    slug: 'produits-action-etf-crypto',
    category: 'produits',
    emoji: '🧺',
    title: 'Action, ETF ou crypto : quelles différences ?',
    minutes: 4,
    oneLiner: 'Une action, c’est un morceau d’entreprise ; un ETF, un panier de centaines d’actions ; une crypto, un actif numérique sans entreprise derrière.',
    intro: [
      'Ces trois produits s’achètent chez un courtier mais n’ont pas du tout le même niveau de risque. L’application les analyse donc avec des critères différents.',
    ],
    sections: [
      {
        title: 'En résumé',
        bullets: [
          'Action : une part d’une entreprise. Tu profites de sa réussite (cours, dividendes) mais tu subis ses difficultés. Risque concentré sur une seule société.',
          'ETF (fonds indiciel coté) : un panier qui réplique un indice (par exemple le MSCI World, environ 1 400 entreprises de pays développés). Diversifié et peu cher : idéal pour la base d’un portefeuille.',
          'Crypto : actif numérique (Bitcoin, Ether…) sans bénéfices ni dividendes. Très volatil : des variations de 10 % en une journée sont courantes.',
        ],
      },
      {
        title: 'Bien choisir un ETF',
        bullets: [
          'Les frais annuels (TER) : moins de 0,3 % par an, c’est bien.',
          'La taille du fonds : un très petit fonds peut fermer.',
          'Capitalisant (les dividendes sont réinvestis) ou distribuant (ils sont versés).',
          'Réplication physique (le fonds détient les titres) ou synthétique (contrat d’échange avec une banque).',
        ],
      },
    ],
    inApp: [
      'Actions : analyse fondamentale complète (voir les fiches PER et santé financière).',
      'ETF : frais TER (30 %) — moins de 0,1 % : 9,5/10 · 0,1–0,2 : 9 · 0,2–0,3 : 8 · 0,3–0,5 : 6,5 · 0,5–0,8 : 5 · plus : 3. Taille (25 %) — moins de 50 M : 3/10 · 50–100 M : 4,5 · 100–500 M : 6 · 500 M–1 Md : 8 · plus : 9. Nombre de positions (20 %) — moins de 20 : 3,5/10 · 20–50 : 5 · 50–100 : 7 · 100–500 : 8,5 · plus : 9,5. Performance depuis le 1er janvier (15 %) et réplication (10 % : physique 8/10, synthétique 6,5).',
      'ETF à effet de levier ou inverse : score fondamental plafonné à 4/10 (réservé au très court terme).',
      'Cryptos : capitalisation (45 %) — moins de 100 M : 2,5/10 · jusqu’à 1 Md : 4,5 · jusqu’à 10 Md : 6,5 · jusqu’à 100 Md : 8 · plus : 9. Liquidité, volume 24 h / capitalisation (30 %) — moins de 0,5 % : 4 · 0,5–2 % : 6 · 2–5 % : 7,5 · plus : 8,5. Offre en circulation / maximale (25 %) — moins de 50 % : 5,5 · 50–90 % : 7 · plus : 8,5 · offre illimitée : 5.',
    ],
    traps: [
      'Un ETF sectoriel ou d’un seul pays reste concentré : ce n’est pas un ETF monde.',
      'Le passé ne garantit rien : une performance récente spectaculaire n’annonce pas la suite.',
      'Cryptos : garde-les à une petite part du total, et méfie-toi des promesses de gains rapides.',
    ],
    keyPoints: [
      'Action = une entreprise ; ETF = un panier ; crypto = un actif numérique très volatil.',
      'Pour un ETF, regarde d’abord les frais et la taille.',
    ],
    related: ['turbos-warrants', 'diversifier-gerer-risque', 'sante-financiere'],
  },
  {
    slug: 'turbos-warrants',
    category: 'produits',
    emoji: '⚡',
    title: 'Turbos et warrants : le levier',
    minutes: 4,
    oneLiner: 'Des produits qui amplifient les variations d’un sous-jacent (action, indice…) : les gains comme les pertes, jusqu’à la perte totale.',
    intro: [
      'Un turbo « call » gagne quand le sous-jacent monte, un turbo « put » quand il baisse. Avec un levier de 5, une hausse de 2 % du sous-jacent fait environ +10 % sur le turbo… et une baisse de 2 % environ −10 %.',
      'Le turbo a une barrière désactivante : si le sous-jacent la touche, le turbo s’arrête et ne vaut presque plus rien. Ce sont des produits émis par des banques, destinés au court terme.',
    ],
    sections: [
      {
        title: 'Les notions à connaître',
        bullets: [
          'Levier : combien de fois les variations sont amplifiées.',
          'Barrière : le niveau qui désactive le produit. Plus elle est proche, plus le risque de tout perdre est grand.',
          'Échéance : la date de fin. Sur un warrant, la valeur temps fond à l’approche de l’échéance.',
          'Spread : l’écart entre prix d’achat et prix de vente, un coût caché à chaque aller-retour.',
          'Émetteur : la banque qui garantit le produit ; si elle fait défaut, le produit peut ne pas être remboursé.',
        ],
      },
    ],
    inApp: [
      'Analyse technique et sentiment réalisés sur le sous-jacent ; pour un put, ces scores sont inversés (une baisse du sous-jacent est favorable).',
      'Distance à la barrière (40 %) — moins de 3 % : 1/10 · 3–5 % : 2,5 · 5–10 % : 4,5 · 10–15 % : 6 · 15–25 % : 7,5 · 25–40 % : 8,5 · plus : 9.',
      'Échéance (15 %, ou 30 % sans barrière) — moins de 30 jours : 2/10 · jusqu’à 90 : 4 · jusqu’à 180 : 6 · jusqu’à 365 : 7,5 · plus : 8,5.',
      'Levier (25 %) — moins de 2 : 9/10 · 2–5 : 8 · 5–10 : 6 · 10–20 : 4 · 20 et plus : 2.',
      'Spread (20 %) — moins de 0,5 % : 9/10 · 0,5–1 % : 8 · 1–2 % : 6,5 · 2–5 % : 4 · plus : 2. Émetteur (15 %) : grande banque reconnue 8/10, autre 6.',
      'Stop-loss : calculé sur le sous-jacent puis traduit en prix du turbo ; il doit se déclencher bien avant la barrière.',
    ],
    traps: [
      'La perte totale est possible, et rapide : une mauvaise nouvelle la nuit peut faire toucher la barrière à l’ouverture.',
      'Un levier élevé transforme le bruit normal du marché en grosses variations.',
      'Ce n’est pas un placement : c’est un outil de court terme, à petite dose.',
    ],
    keyPoints: [
      'Levier × variation du sous-jacent ≈ variation du turbo.',
      'Barrière proche = danger ; garde toujours une bonne marge.',
    ],
    related: ['produits-action-etf-crypto', 'supports-resistances-stop-loss', 'diversifier-gerer-risque'],
  },
  {
    slug: 'sentiment-actualites',
    category: 'actualites',
    emoji: '📰',
    title: 'Le sentiment des actualités',
    minutes: 3,
    oneLiner: 'L’application lit les titres de presse récents et mesure s’ils sont plutôt positifs ou négatifs pour le produit.',
    intro: [
      'Une annonce de résultats, un rachat, un procès ou un rappel de produits peuvent faire bouger un cours en quelques minutes. Le score « sentiment » résume le ton des titres d’actualité des derniers jours.',
    ],
    sections: [
      {
        title: 'Comment c’est calculé',
        bullets: [
          'Sources : Google Actualités en français et en anglais (et NewsAPI si configuré), titres des 72 dernières heures, 10 au maximum.',
          'Chaque titre est classé positif, neutre ou négatif selon des mots-clés (« bondit », « record », « relève ses prévisions » / « chute », « avertissement », « enquête »…), en tenant compte des négations.',
          'Les titres de moins de 24 h comptent plus (poids 1), ceux de 24 à 48 h un peu moins (0,7), les plus anciens 0,5.',
          'Score = 5 + 5 × ton moyen, ramené vers 5 quand il y a moins de 5 articles (peu d’information = neutralité).',
        ],
      },
    ],
    inApp: [
      '20 % du score global.',
      'Verdict : positif à partir de 6/10, négatif à 4/10 ou moins, neutre entre les deux.',
      'Turbo ou warrant put : score inversé.',
      'Les prochains événements (publication de résultats, détachement du dividende dans les 30 jours) sont affichés quand ils sont connus.',
    ],
    traps: [
      'Un titre peut être trompeur : « chute moins forte que prévu » est en réalité une bonne nouvelle.',
      'L’actualité est déjà souvent intégrée dans le cours au moment où tu la lis.',
      'Avant une publication de résultats, le cours peut bouger fortement dans les deux sens : prudence.',
    ],
    keyPoints: [
      'Le sentiment donne la température du moment, pas la valeur de l’entreprise.',
      'Lis toujours les titres eux-mêmes avant de décider.',
    ],
    related: ['lire-les-scores', 'valorisation-per'],
  },
  {
    slug: 'taxe-plus-values',
    category: 'fiscalite',
    emoji: '🧾',
    title: 'La taxe sur les plus-values (depuis 2026)',
    minutes: 5,
    updated: 'novembre 2026',
    oneLiner: "Depuis le 1er janvier 2026, le gain réalisé en vendant une action, un ETF, un fonds, une obligation ou une crypto est taxé à 10 %, après une franchise de 10 000 € par personne et par an.",
    intro: [
      "Jusqu'en 2025, un particulier belge qui gérait son portefeuille « en bon père de famille » ne payait pas d'impôt sur ses plus-values. La loi d'avril 2026 (publiée au Moniteur belge le 21 avril 2026) a changé cela, avec effet au 1er janvier 2026.",
      "Seul le gain réalisé, c'est-à-dire au moment de la vente, est visé. Tant que tu gardes un titre, rien n'est dû, même s'il a fortement monté.",
    ],
    sections: [
      {
        title: "L'essentiel",
        bullets: [
          'Taux : 10 % de la plus-value réalisée.',
          'Produits concernés : actions, ETF, fonds, obligations, cryptomonnaies, et certains contrats d’assurance-placement.',
          'Franchise : les 10 000 premiers euros de plus-values de l’année sont exonérés, par personne (un couple a donc deux franchises). Le montant est indexé chaque année.',
          'Franchise non utilisée : on peut en reporter au plus 1 000 € par an, pendant cinq ans maximum (jusqu’à 15 000 € de franchise une année donnée).',
        ],
      },
      {
        title: 'Et ce que je possédais avant 2026 ?',
        paras: [
          "Les gains acquis avant 2026 restent hors taxe. Pour un titre acheté avant 2026, le point de départ du calcul est sa valeur au 31 décembre 2025 (le cours de clôture pour un titre coté).",
          "Si tu l'avais payé plus cher que ce cours, tu peux utiliser ton vrai prix d'achat pour les ventes faites jusqu'au 31 décembre 2030, à condition de pouvoir le prouver (avis d'exécution, relevé). Garde ces documents.",
        ],
      },
      {
        title: 'Exemple',
        bullets: [
          'Action achetée 40 € en 2023, cotée 50 € au 31/12/2025, vendue 70 € en 2026.',
          'Gain taxable : 70 − 50 = 20 € par action (les 10 € gagnés avant 2026 sont exonérés).',
          'Si tes gains de l’année ne dépassent pas 10 000 €, tu ne paies finalement rien, mais il faut le demander dans ta déclaration.',
        ],
      },
      {
        title: 'Les pertes',
        paras: [
          "Une moins-value réalisée peut être déduite des plus-values de la même année, de la même catégorie (le régime à 10 %). Une perte qui n'a pas servi dans l'année ne se reporte pas sur les années suivantes.",
        ],
      },
      {
        title: 'Qui paie ? La banque ou toi',
        bullets: [
          'Banque ou courtier en Belgique (Saxo a une succursale belge) : il retient en principe les 10 % à chaque vente. Il ne connaît ni ta franchise ni tes pertes chez d’autres intermédiaires : tu récupères le trop-payé via ta déclaration.',
          '« Opt-out » : tu peux demander qu’il ne retienne rien ; tu déclares alors toi-même tes plus-values. Chaque intermédiaire fixe sa date limite (chez Saxo, c’était le 30 juin 2026).',
          'Courtier étranger sans présence en Belgique : en général rien n’est retenu ; c’est à toi de calculer et de déclarer.',
          'Première déclaration concernée : celle de 2027, pour les revenus 2026.',
        ],
      },
      {
        title: 'Autres régimes (hors de cette fiche)',
        bullets: [
          'Participations importantes (au moins 20 % d’une société) : règles spécifiques.',
          '« Plus-values internes » (revendre ses titres à sa propre société) : 33 %.',
          'Opérations spéculatives ou anormales : taxation plus lourde possible.',
        ],
      },
    ],
    inApp: [
      'Les portefeuilles fictifs et les rapports ne calculent pas cette taxe : leurs performances sont avant impôts.',
      'Les objectifs de vente de l’outil ne tiennent pas compte de la franchise annuelle : à toi de répartir tes ventes si c’est utile.',
    ],
    traps: [
      'Croire que la franchise est automatique : elle se demande dans la déclaration annuelle.',
      'Perdre les preuves d’achat d’avant 2026 : sans elles, impossible de faire valoir un prix d’achat plus élevé que le cours du 31/12/2025.',
      'Compter sur une perte de l’an passé : elle ne se reporte pas.',
      'Oublier un compte chez un courtier étranger : la déclaration reste obligatoire.',
    ],
    keyPoints: [
      '10 % sur le gain réalisé depuis le 1er janvier 2026, après 10 000 € de franchise par personne et par an.',
      'Les gains d’avant 2026 ne sont pas taxés.',
      'Garde tes avis d’achat et de vente, et vérifie ta déclaration 2027.',
      'Règles récentes et parfois précisées en cours de route : en cas de doute, demande au SPF Finances ou à un comptable.',
    ],
    sources: [
      ['Belfius : exonérations et réductions possibles', 'https://www.belfius.be/webapps/fr/selfcare/belfius/epargner-investir/outils-services/exonerations-réductions-possibles-taxe-sur-les-plus-values'],
      ['Bolero : exonération et moins-values', 'https://www.bolero.be/fr/campagnes/la-taxe-sur-les-plus-values-chez-bolero/exoneration-et-moins-values-dans-le-cadre-de-la-taxe-sur-les-plus-values'],
      ['Saxo : impôt sur les plus-values et opt-out', 'https://www.help.saxo/hc/fr-be/articles/36192904266525-Imp%C3%B4t-sur-les-plus-values-et-opt-out-comment-faire-un-choix'],
      ['Baker Tilly : impact pour les investisseurs', 'https://bakertilly.be/fr/news/taxe-sur-les-plus-values-des-actifs-financiers-a-partir-de-2026-impact-sur-les-investisseurs/'],
    ],
    related: ['tob-taxe-de-bourse', 'dividendes-precompte'],
  },
  {
    slug: 'tob-taxe-de-bourse',
    category: 'fiscalite',
    emoji: '🏦',
    title: 'La taxe sur les opérations de Bourse (TOB)',
    minutes: 3,
    updated: 'novembre 2026',
    oneLiner: "Chaque achat et chaque vente en Bourse paie une petite taxe : 0,12 %, 0,35 % ou 1,32 % selon le produit, avec un plafond par opération.",
    intro: [
      "La TOB existe depuis longtemps et s'ajoute aux frais du courtier. Elle est due même si tu perds de l'argent sur l'opération.",
    ],
    sections: [
      {
        title: 'Les trois taux',
        bullets: [
          '0,35 % (maximum 1 600 € par opération) : actions, et ETF non enregistrés dans l’Espace économique européen.',
          '0,12 % (maximum 1 300 €) : ETF et fonds cotés enregistrés dans l’Espace économique européen, obligations, SIR belges.',
          '1,32 % (maximum 4 000 €) : fonds et ETF de capitalisation (qui réinvestissent les dividendes) enregistrés en Belgique.',
        ],
      },
      {
        title: 'Le piège des ETF de capitalisation',
        paras: [
          "Beaucoup d'ETF populaires sur le monde entier existent en version « capitalisation » enregistrée en Belgique : ils paient alors 1,32 % à l'achat et à la vente, contre 0,12 % pour un ETF comparable non enregistré en Belgique. Sur 5 000 €, cela fait 66 € au lieu de 6 €. Regarde la fiche du produit chez ton courtier avant d'acheter.",
        ],
      },
      {
        title: 'Qui la paie ?',
        bullets: [
          'Courtier belge (dont la succursale belge de Saxo) : il la retient automatiquement, tu n’as rien à faire.',
          'Courtier étranger qui ne s’en charge pas : tu dois la déclarer et la payer toi-même au SPF Finances, au plus tard le dernier jour ouvrable du deuxième mois qui suit l’opération.',
        ],
      },
    ],
    inApp: [
      'Les portefeuilles fictifs comptent 0,1 % de frais par opération (minimum 1 €) : c’est une moyenne simplifiée, la TOB réelle peut être plus élevée.',
    ],
    traps: [
      'Multiplier les petits allers-retours : TOB et frais sont payés à chaque fois.',
      'Acheter un ETF de capitalisation enregistré en Belgique sans le savoir : 1,32 % à l’entrée et à la sortie.',
      'Oublier de payer la TOB chez un courtier étranger : des amendes sont prévues.',
    ],
    keyPoints: [
      'Actions : 0,35 %. ETF européens : souvent 0,12 %. Capitalisation enregistrée en Belgique : 1,32 %.',
      'La TOB s’ajoute aux frais du courtier, à l’achat comme à la vente.',
    ],
    sources: [
      ['Test-Achats : la taxe sur les opérations de Bourse', 'https://www.test-achats.be/invest/fiscalite-et-droits/taxation/dossiers/taxe-de-bourse/taxe-operation-bourse'],
      ['Circulaire 2026/C/42 (FAQ TOB, mars 2026)', 'https://blog.oeccbb.be/fr/article/circulaire-2026c42-faq-tob-taxe-sur-les-operations-de-bourse-version-2/30750'],
      ['Wikifin : les taxes sur vos investissements', 'https://www.wikifin.be/fr/impots-emploi-et-revenus/declaration-dimpots/vos-revenus-mobiliers/les-taxes-sur-vos'],
    ],
    related: ['taxe-plus-values', 'produits-action-etf-crypto'],
  },
  {
    slug: 'dividendes-precompte',
    category: 'fiscalite',
    emoji: '💶',
    title: 'Dividendes, précompte et compte à l’étranger',
    minutes: 4,
    updated: 'novembre 2026',
    oneLiner: "Les dividendes sont taxés à 30 % (le précompte mobilier), mais une petite partie peut être récupérée ; un compte à l'étranger doit être signalé.",
    intro: [
      "Quand une société te verse un dividende, une partie part directement en impôt avant d'arriver sur ton compte. Voici les règles principales pour un particulier belge.",
    ],
    sections: [
      {
        title: 'Le précompte mobilier : 30 %',
        bullets: [
          'Dividendes et intérêts : 30 % retenus à la source par ta banque ou ton courtier belge.',
          'Action étrangère : le pays de la société retient d’abord sa propre taxe (par exemple 15 % aux États-Unis avec le formulaire W-8BEN), puis la Belgique prend 30 % sur le reste.',
          'Exemple : 100 € de dividende américain → 15 € pour les États-Unis → 25,50 € pour la Belgique → 59,50 € pour toi.',
        ],
      },
      {
        title: 'La part que tu peux récupérer',
        paras: [
          "Les premiers 833 € de dividendes d'actions de l'année (revenus 2025) sont exonérés, par personne. Comme le précompte a déjà été retenu, tu le récupères via ta déclaration (cadre VII, code 1437), jusqu'à 249,90 €. Le montant est revu chaque année.",
          "Les dividendes d'ETF et de fonds n'ouvrent pas droit à cette exonération.",
        ],
      },
      {
        title: 'Fonds obligataires : la taxe Reynders',
        paras: [
          "Si un fonds investit plus de 10 % en obligations, la part de ton gain qui vient des intérêts est taxée à 30 % à la vente. Cette part n'est pas taxée une seconde fois par la taxe sur les plus-values.",
        ],
      },
      {
        title: 'Gros portefeuilles : la taxe sur les comptes-titres',
        paras: [
          "Au-delà d'une valeur moyenne d'un million d'euros sur un compte-titres, une taxe annuelle s'applique : 0,30 % depuis le 1er juin 2026 (0,15 % avant).",
        ],
      },
      {
        title: 'Compte à l’étranger : deux démarches',
        bullets: [
          'Une seule fois : signaler le compte au Point de contact central de la Banque nationale (en ligne avec ta carte d’identité ou itsme).',
          'Chaque année : cocher son existence au cadre XIII de ta déclaration, avec le pays.',
          'Cela vaut aussi pour les comptes-titres et les comptes crypto à l’étranger. Un compte auprès d’une succursale belge (comme Saxo Belgique) n’est pas un compte étranger.',
        ],
      },
    ],
    inApp: [
      'Le rendement du dividende affiché par l’outil est brut, avant toute taxe.',
    ],
    traps: [
      'Comparer des rendements de dividende sans tenir compte des 30 % (et de la taxe étrangère).',
      'Ne pas réclamer les 833 € exonérés : l’argent reste au fisc.',
      'Oublier le cadre XIII pour un compte chez un courtier ou une plateforme crypto à l’étranger.',
    ],
    keyPoints: [
      '30 % de précompte sur les dividendes, en partie récupérable pour les actions.',
      'Un compte à l’étranger : déclaration à la Banque nationale une fois, puis cadre XIII chaque année.',
    ],
    sources: [
      ['Crelan : exonération des dividendes (FAQ)', 'https://www.crelan.be/fr/particuliers/article/exoneration-dividendes-faq'],
      ['Wikifin : déclarer vos comptes à l’étranger', 'https://www.wikifin.be/fr/impots-emploi-et-revenus/declaration-dimpots/vos-revenus-mobiliers/declarer-vos-comptes-letranger'],
      ['BNP Paribas Fortis : taxe annuelle sur les comptes-titres', 'https://www.bnpparibasfortis.be/fr/public/particuliers/epargner-et-placer/taxe-compte-titre'],
      ['Pareto : la taxe Reynders', 'https://pareto.be/fr/tout-savoir/optimisation-fiscale/taxes/taxe-reynders/'],
    ],
    related: ['taxe-plus-values', 'tob-taxe-de-bourse'],
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
  ter: 'produits-action-etf-crypto',
  size: 'produits-action-etf-crypto',
  holdings: 'produits-action-etf-crypto',
  ytd: 'produits-action-etf-crypto',
  replication: 'produits-action-etf-crypto',
  mcap: 'produits-action-etf-crypto',
  liquidity: 'produits-action-etf-crypto',
  supply: 'produits-action-etf-crypto',
  barrier: 'turbos-warrants',
  maturity: 'turbos-warrants',
  leverage: 'turbos-warrants',
  spread: 'turbos-warrants',
  issuer: 'turbos-warrants',
}
