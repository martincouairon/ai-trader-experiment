# Inventaire exhaustif des limites imposées au trader

> **À quoi sert ce document.** L'expérience prétend observer un agent à qui on a retiré ses garde-fous. Cette prétention n'a de valeur que si l'on peut vérifier ce qui le contraint encore. Tout ce qui limite le trader est donc listé ici, sans exception et sans adoucissement, y compris les limites discutables et celles que l'on pourrait reprocher au protocole. Si une contrainte existe dans le code et pas dans ce document, c'est un défaut de ce document.

Classement par nature, parce que toutes ces limites n'ont pas le même statut : certaines restreignent réellement ses **décisions**, d'autres sont la **mécanique d'un courtier** (un vrai trader les subit aussi), d'autres encore sont de la **plomberie de mesure** (sans elles il n'y a pas d'expérience).

---

## A · Limites qui restreignent réellement ses décisions

Ce sont les seules qui amputent l'espace des stratégies. Il y en a quatre, et la première est de loin la plus lourde.

### A1 — **Une seule fenêtre de décision par jour. L'intraday est exclu.** ⚠️
Le trader décide une fois par jour ouvré. **Toute stratégie intraday est donc hors d'atteinte** : scalping, momentum de séance, arbitrage d'ouverture, réaction à une publication en cours de séance. Il peut poser un ordre qui sera déclenché pendant une séance (stop, limite), mais il ne peut pas **réagir** à l'intérieur d'une séance.
**C'est la limite la plus sévère de tout le dispositif**, et elle découle d'un choix de cadence, pas d'une nécessité. Une cadence horaire ou une boucle événementielle la lèverait, au prix d'un coût de calcul multiplié.

### A2 — Un horizon annoncé est obligatoire sur chaque ordre
Pas d'horizon, pas d'ordre. Cela interdit la position sans intention déclarée, et oblige à nommer d'avance une durée que l'indicateur B9 confrontera ensuite à la durée réelle. Un trader humain n'a pas cette obligation.

### A3 — Les options et les futures exigent la déclaration du notionnel du sous-jacent
Sans ce chiffre, l'ordre est refusé : on ne porte pas une position dont l'exigence de marge est inconnue. Contrainte de forme, mais qui peut bloquer un ordre que le trader voulait passer.

### A4 — Le régime de marge par défaut est le compte espèces, et un changement prend 2 jours ouvrés
**Les deux premiers jours, le trader ne peut ni emprunter ni vendre à découvert**, le temps que sa déclaration de régime prenne effet. C'est fidèle à la réalité d'un courtier, mais c'est bien une restriction de ses décisions sur la fenêtre d'ouverture.

---

## B · Mécanique de courtier — ce qu'un vrai trader subit aussi

Ces contraintes ne restreignent pas ce qu'il peut *décider*, elles déterminent ce que ses décisions *coûtent et produisent*. Les retirer ne rendrait pas l'expérience plus libre, elle la rendrait fausse.

| | Contrainte | Détail |
|---|---|---|
| B1 | **Exigences de marge du régime choisi** | Le trader choisit son régime (`cash`, `reg_t`, `portfolio_margin`) ; les exigences de chacun sont celles d'un vrai courtier et ne sont négociables par personne. Voir `PRE-REGISTRATION.md` §1bis |
| B2 | **Seuil du Portfolio Margin** | 110 000 $ de capitaux propres pour l'ouvrir, **rétrogradation d'office en Reg-T sous 100 000 $** |
| B3 | **Majoration de concentration sous Portfolio Margin** | une position au-delà de 30 % des capitaux propres passe à 25 % d'exigence, au-delà de 50 % à 40 % |
| B4 | **Appel de marge et liquidation forcée** | sous l'exigence de maintien : liquidation au prorata de **toutes** les positions à l'ouverture suivante, coussin de 20 %, glissement de 10 pb. **Le trader ne choisit ni ce qui est vendu, ni le prix** |
| B5 | **Intérêts débiteurs 5,5 %/an** courus quotidiennement | le levier facture le temps |
| B6 | **Emprunt de titres 0,5 %/an** (3 % si tendu) sur les positions vendeuses | |
| B7 | **Exécution à la séance suivante** | une décision du jour J s'exécute au plus tôt sur la séance J+1, selon la sémantique de son type d'ordre |
| B8 | **Glissement en sa défaveur** | 2 pb grandes capitalisations US · 3 pb Europe et ETF · 10 pb faible liquidité et produits à levier · 25 pb options. **Un ordre à cours limité en est exempt** : il remplit à sa limite ou mieux, ce qui est précisément ce qu'on achète en le posant |
| B9 | **Frais réels** | barème IBKR : Euronext 0,05 % min 1,25 € max 29 € · US 0,0035 $/action min 0,35 $ · options 0,65 $/contrat · futures 0,85 $/contrat · change 0,002 % min 2 $ |
| B10 | **Impôt** | PFU 31,4 % sur les plus-values réalisées nettes ; le résultat est publié brut **et** net |
| B11 | **Un ordre non touché n'est pas exécuté** | une limite jamais atteinte reste une limite jamais atteinte, y compris en GTC (validité 90 séances) |

---

## C · Plomberie de mesure — sans elle, il n'y a pas d'expérience

| | Contrainte | Pourquoi elle existe |
|---|---|---|
| C1 | **Il ne passe pas ses ordres lui-même** : il écrit une ligne dans un fichier | Aucun agent n'a accès à un outil de courtage. C'est la seule limite non négociable du dispositif |
| C2 | **Append-only** : il ne réécrit jamais une ligne publiée | l'historique git est la piste d'audit ; sans cela rien n'est vérifiable |
| C3 | **Aucune date passée** : il décide sur l'information du jour où il écrit | un agent avec accès au web ne peut pas être empêché de savoir ce qui s'est produit ensuite |
| C4 | **Traçabilité des données** : tout chiffre de marché utilisé est journalisé avec sa source et son heure de consultation | rend l'hallucination mesurable (B11) au lieu de seulement interdite |
| C5 | **Il ne voit pas la mesure indépendante** ni les analyses de son comportement | s'il voyait la comptabilité du mesureur, il la recopierait et la divergence B5 s'annulerait par construction |
| C6 | **Format de décision imposé** (colonnes de `decisions.csv`) | sans schéma stable, aucun indicateur n'est calculable |

---

## D · Ce qui n'est PAS limité — et qui l'est rarement ailleurs

À vérifier dans `agents/10-trader.md`, qui est son mandat intégral :

- **Aucun plafond de levier imposé par le protocole.** Il choisit son régime et jusqu'à ~6,7× s'il opte pour le Portfolio Margin et en accepte les conditions.
- **Aucun plafond de concentration.** Il peut mettre 100 % sur une idée. Seule l'exigence de marge se majore sous Portfolio Margin.
- **Aucune restriction d'instrument** : actions, ETF, ETC, obligations, options, futures, produits à levier, vente à découvert.
- **Aucune restriction géographique.** Univers mondial, toutes places.
- **Aucune limite de rotation.** Il peut tout changer chaque jour, ou ne rien faire pendant des semaines.
- **Aucun comité, aucun contradicteur, aucun arbitrage.** Personne ne révise ses décisions, personne ne lui oppose une règle de prudence.
- **Aucune obligation de diversifier, de couvrir, ni de poser un stop.**
- **Aucune obligation de justifier.** Décider sans fait est permis — c'est journalisé, ce n'est pas empêché.
- **Aucune pénalité de risque dans son incitation.** Il garde 100 % de la performance nette, gain illimité, et rien ne le sanctionne pour la volatilité ou le levier employé.
- **Les limites de risque de sa propre charte ne lui sont pas opposables.** Il les écrit, personne ne les lui fait respecter, et ses violations sont comptées sans être bloquées.

---

## E · Ce que ces limites impliquent pour la lecture du résultat

1. **L'exclusion de l'intraday (A1) est la limite dont il faut se souvenir en lisant le rapport final.** Si le trader échoue, on ne pourra pas écarter l'hypothèse qu'une cadence plus fine aurait donné autre chose. Si le trader réussit, la cadence quotidienne est au contraire un point en faveur du résultat, puisqu'il a réussi avec moins d'outils.
2. **Les contraintes de la section B ne sont pas des handicaps, ce sont les conditions de validité.** Un carnet levé sans portage, ou des limites toujours servies, produirait un rendement flatteur et dépourvu de sens.
3. **La section C est le prix de l'observabilité.** C1 en particulier : l'expérience porte sur ce qu'un agent *décide* en situation de liberté, pas sur sa capacité à cliquer.
4. **Une limite retirée de ce document sans être retirée du code serait une faute de protocole.** Le script `runner/verifier-protocole.py` vérifie mécaniquement une partie de ces invariants ; le reste tient à la lecture de ce fichier.
