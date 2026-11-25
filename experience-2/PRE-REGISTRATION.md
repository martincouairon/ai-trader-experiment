# Pré-enregistrement — Expérience 2 : prévisions relatives quotidiennes

> **BROUILLON À RELIRE — rien n'est publié ni figé.** Les points marqués **[À TRANCHER]** attendent une décision. Une fois validé, ce fichier est commité **avant la première prévision**, puis figé : toute modification ultérieure invalide l'expérience, et l'historique git le prouve dans les deux sens.

## 0 · D'où vient cette expérience

L'expérience 1 (pré-enregistrée le 2026-11-21, premier ordre le 2026-11-24) laissait à l'agent une liberté totale et l'évaluait sur la seule croissance nette de son capital. L'agent a écrit une charte de type cœur-satellite : au moins 80 % dans un ETF MSCI World (IWDA) conservé jusqu'à la fin, aucun levier, régime cash. Il a acheté ce cœur le premier jour, puis n'a plus rien décidé. Cette réponse est cohérente avec l'objectif qu'on lui avait donné. Mais elle ne permet pas de mesurer une capacité de gestion active : un portefeuille qui réplique l'indice suit l'indice. L'expérience 1 est close à la date de mise en route de l'expérience 2 ; son résultat est publié tel quel.

L'expérience 2 pose une autre question, et elle est construite pour pouvoir y répondre en quelques mois au lieu de plusieurs décennies.

## 1 · La question

**L'agent sait-il prévoir la performance relative de grandes valeurs les unes par rapport aux autres, d'un jour sur l'autre ? Et un portefeuille construit à partir de ces prévisions surperforme-t-il, net de frais, les ETF larges en gestion passive ?**

Deux principes, repris de la gestion multi-stratégies, rendent la mesure possible sur une courte durée :
1. **Le marché est retiré de la mesure.** L'agent ne prévoit pas si le marché monte ou baisse ; il classe des valeurs entre elles. Le résultat ne dépend plus des ±15 % annuels du marché, qui n'ont rien à voir avec sa compétence.
2. **Les paris sont nombreux et indépendants.** Chaque jour, l'agent classe tout l'univers. Cela fait des milliers de prévisions sur la durée, au lieu d'un seul pari de portefeuille.

## 2 · Le protocole

| Paramètre | Valeur |
|---|---|
| Univers | **les 50 plus grandes capitalisations de sociétés américaines**, cotées à New York, relevées le 2026-11-25 ; liste figée en annexe A et dans `experience-2/data/univers.csv`. Les sociétés étrangères cotées aux États-Unis sont exclues |
| Fenêtre de décision | **une par jour ouvré américain, 13h08 UTC**, avant l'ouverture de New York toute l'année (14h30 UTC en hiver, 13h30 UTC en été) |
| Ce que l'agent produit | un **classement complet des 50 valeurs**, de 1 (meilleure performance relative attendue) à 50, sans ex æquo ni omission ; une raison courte pour les 5 premières et les 5 dernières. Format : `experience-2/data/classements.csv`, contrôlé par `experience-2/tools/valider-classement.py` ; mandat : `experience-2/agents/10-previsionniste.md` |
| Horizon de chaque prévision | **une séance** : de l'ouverture du jour de la décision à l'ouverture de la séance suivante |
| Durée | **126 séances** (environ six mois) à partir de la première prévision, puis arrêt. Aucune analyse intermédiaire ne peut prolonger ni écourter l'expérience |
| Première prévision | **[À TRANCHER]** |
| Modèle | celui de la tâche planifiée, journalisé à chaque exécution ; un changement de modèle est un facteur de confusion déclaré |
| Accès aux données | cours sur Interactive Brokers en lecture seule (liste fermée d'outils), actualité publique sur le web. Aucun accès aux mesures, aux résultats ni au rapport |

Un classement manquant (exécution échouée, fichier invalide) est enregistré comme manquant, n'est pas remplacé et compte dans les statistiques de couverture. Un classement incomplet ou invalide est traité comme manquant.

## 3 · Ce qui est mesuré

### 3.1 Mesure principale — la qualité des prévisions

Pour chaque jour *t* : **IC_t**, la corrélation de rang de Spearman entre le classement de l'agent et le rendement réalisé des 50 valeurs sur l'horizon (ouverture *t* → ouverture *t+1*). Le rendement réalisé est mesuré par rapport à la moyenne de l'univers, ce qui ne change pas la corrélation de rang mais rend explicite que seul l'ordre relatif compte.

**Statistique testée :** la moyenne des IC_t sur les 126 séances. **Test :** t de Student sur la série quotidienne, avec erreurs de Newey-West (5 retards). **Seuil :** bilatéral, α = 5 %. **Hypothèse nulle :** IC moyen = 0, c'est-à-dire aucune capacité de prévision.

### 3.2 Mesure secondaire — la surperformance par rapport à la gestion passive

Un **portefeuille de recouvrement**, neutre au marché, est construit chaque jour à partir du classement :
- **achat** à parts égales des 10 premières valeurs, **vente à découvert** à parts égales des 10 dernières ;
- capital de référence de 120 000 € investi dans l'ETF large ; recouvrement de **60 000 € à l'achat et 60 000 € à la vente** (50 % du capital de chaque côté) **[PROPOSÉ, À CONFIRMER]**, rééquilibré chaque jour à l'ouverture ;
- frais, glissement et coût d'emprunt appliqués selon la convention d'exécution reprise de l'expérience 1 (barème IBKR, glissement de 2 pb pour les grandes capitalisations américaines, emprunt à 0,5 %/an, change au franchissement de devise).

Le **portefeuille actif** est égal à l'ETF large plus ce recouvrement. Sa surperformance par rapport à la gestion passive est donc, par construction, **le rendement net du recouvrement**. Elle est publiée face à **IWDA** (référence principale), **CW8** et **WPEA**, en brut et net de frais. Le résultat net d'impôt est publié en complément, au PFU de 31,4 %.

### 3.3 Mesures complémentaires, déclarées comme telles

- IC moyen par décile de confiance de l'agent (ses 5 premières et 5 dernières contre le milieu du classement) ;
- stabilité du classement d'un jour sur l'autre (rotation implicite) et coût de cette rotation ;
- couverture : part des jours avec un classement valide ;
- **témoin aléatoire** : 1 000 classements tirés au hasard chaque jour, pour situer l'IC de l'agent dans la distribution du hasard sur la même période.

Toute autre analyse est exploratoire et signalée comme telle.

## 4 · Ce que l'expérience peut conclure, et ce qu'elle ne peut pas conclure

**Puissance.** Sous l'hypothèse nulle, l'écart-type d'un IC quotidien sur 50 valeurs est d'environ 0,14. En le majorant de 50 % pour tenir compte des corrélations entre valeurs d'un même secteur, un IC moyen vrai de **0,05** donnerait un t d'environ **2,6** sur 126 séances : il serait détecté. Un IC vrai de **0,03** donnerait un t d'environ 1,6 : il ne le serait pas. **L'expérience est dimensionnée pour détecter une capacité de prévision de l'ordre de 0,05 ou plus, pas en dessous.**

- Un résultat non significatif **ne prouve pas l'absence** de capacité : il établit qu'une capacité éventuelle est inférieure à ce que le protocole sait détecter. L'intervalle de confiance est publié dans tous les cas.
- Un IC significatif établit une **capacité de classement** sur cet univers et cette période. Il n'établit pas que le portefeuille de recouvrement serait rentable à une autre échelle, sur un autre univers ou à une autre période.
- La surperformance nette (§3.2) dépend des frais et du coût d'emprunt retenus ; elle est publiée comme une mesure, sans conclusion de compétence au-delà de ce que permet l'IC.
- Aucune attente sur l'issue n'est déposée.

## 5 · Ensemble d'information et aveuglement

L'agent qui prévoit ne reçoit jamais les rendements réalisés calculés par le mesureur, ni son IC, ni le résultat du portefeuille de recouvrement. Il peut consulter les cours publics, comme tout investisseur. Le mesureur ne lit jamais les raisons de l'agent. La séparation des rôles de l'expérience 1 (prévisionniste, mesureur, rédacteur) est conservée.

## 6 · Données et calculs

- Prix d'ouverture des 50 valeurs relevés chaque jour par le mesureur sur Interactive Brokers (qualité primaire). Un prix manquant retire la valeur du calcul de l'IC du jour, et le fait est journalisé ; au-delà de 5 valeurs manquantes, l'IC du jour est déclaré manquant.
- Opérations sur titres (dividendes, divisions) : rendements calculés sur les cours ajustés fournis par Interactive Brokers ; à défaut, ajustement à partir des annonces officielles de la société, journalisé **[PROPOSÉ, À CONFIRMER]**.
- Tous les calculs sont faits par des scripts publiés dans le dépôt avant la première prévision ; aucun chiffre n'est calculé à la main.

## 7 · Arrêt

L'expérience s'arrête après la 126ᵉ séance. Elle ne s'arrête pas avant, quel que soit le résultat intermédiaire. Une panne prolongée de plus de 10 séances consécutives est déclarée et fait l'objet d'une décision publiée, prise sans consulter les résultats.

## 8 · Ce qu'il reste à établir avant la première prévision

1. **La date de première prévision** [À TRANCHER], une fois les outils de mesure prêts et testés à blanc.
2. **Le `contract_id` IBKR de chaque valeur** de l'univers, relevé par le mesureur avant la première prévision. Une valeur qu'IBKR ne couvre pas en qualité primaire est signalée ; elle reste dans l'univers et son prix est relevé sur le web, avec la qualité indiquée.
3. **Confirmation** du notionnel du recouvrement (§3.2) et de la source d'ajustement des opérations sur titres (§6).

L'expérience 2 vit dans le dossier `experience-2/` du dépôt `ai-trader-experiment`. Le pré-enregistrement de l'expérience 1, à la racine, n'est pas modifié.

## Annexe A — Univers (figé le 2026-11-25)

Source : classement des sociétés cotées aux États-Unis par capitalisation boursière (stockanalysis.com, consulté le 2026-11-25), sociétés étrangères exclues. Le rang est celui de ce classement après exclusion.

| Rang | Ticker | Société |
|---|---|---|
| 1 | `NVDA` | NVIDIA |
| 2 | `GOOGL` | Alphabet (classe A) |
| 3 | `AAPL` | Apple |
| 4 | `MSFT` | Microsoft |
| 5 | `AMZN` | Amazon.com |
| 6 | `AVGO` | Broadcom |
| 7 | `META` | Meta Platforms |
| 8 | `TSLA` | Tesla |
| 9 | `WMT` | Walmart |
| 10 | `BRK.B` | Berkshire Hathaway (classe B) |
| 11 | `JPM` | JPMorgan Chase |
| 12 | `LLY` | Eli Lilly |
| 13 | `XOM` | Exxon Mobil |
| 14 | `V` | Visa |
| 15 | `MU` | Micron Technology |
| 16 | `AMD` | Advanced Micro Devices |
| 17 | `JNJ` | Johnson & Johnson |
| 18 | `INTC` | Intel |
| 19 | `ORCL` | Oracle |
| 20 | `COST` | Costco Wholesale |
| 21 | `MA` | Mastercard |
| 22 | `CAT` | Caterpillar |
| 23 | `NFLX` | Netflix |
| 24 | `CVX` | Chevron |
| 25 | `BAC` | Bank of America |
| 26 | `ABBV` | AbbVie |
| 27 | `CSCO` | Cisco Systems |
| 28 | `PG` | Procter & Gamble |
| 29 | `KO` | Coca-Cola |
| 30 | `UNH` | UnitedHealth Group |
| 31 | `PLTR` | Palantir Technologies |
| 32 | `HD` | Home Depot |
| 33 | `LRCX` | Lam Research |
| 34 | `AMAT` | Applied Materials |
| 35 | `GE` | GE Aerospace |
| 36 | `MS` | Morgan Stanley |
| 37 | `GEV` | GE Vernova |
| 38 | `GS` | Goldman Sachs |
| 39 | `MRK` | Merck & Co. |
| 40 | `PM` | Philip Morris International |
| 41 | `TXN` | Texas Instruments |
| 42 | `WFC` | Wells Fargo |
| 43 | `RTX` | RTX |
| 44 | `LIN` | Linde |
| 45 | `KLAC` | KLA |
| 46 | `AXP` | American Express |
| 47 | `C` | Citigroup |
| 48 | `ANET` | Arista Networks |
| 49 | `IBM` | IBM |
| 50 | `PEP` | PepsiCo |
