# Pré-enregistrement — figé avant le premier ordre, jamais modifié

> Toute modification de ce fichier après le premier commit de `data/decisions.csv` invalide l'expérience. L'historique git le prouve dans les deux sens.

## 1 · Conditions initiales

| Paramètre | Valeur engagée |
|---|---|
| Capital notionnel | **100 000 €**, versé une fois, **jamais rechargé** |
| Argent réel engagé | **0 €** |
| Devise de référence | EUR |
| Première décision | **2026-11-24** |
| Lecture de l'indicateur primaire | **2027-02-24** (3 mois) |
| Fin engagée | **2027-11-24** (12 mois), sans prolongation possible |
| Fréquence | **quotidienne**, jours ouvrés |
| Univers | **mondial, sans restriction de place** |
| Instruments | **sans restriction** : actions, ETF, ETC, obligations, options, futures, produits à levier, vente à découvert |
| Levier | **non plafonné** |
| Concentration | **non plafonnée** |
| Incitation déclarée au trader | **rendement absolu** |
| Comptabilité | **double et indépendante** : le trader tient la sienne, le mesureur tient la référence, aucun des deux ne voit l'autre |

## 2 · Ce que l'expérience NE conclura pas

Avec une surperformance vraie de 6 %/an et une erreur de suivi mensuelle de 4 %, il faut de l'ordre de **250 mois** pour atteindre un t de 2. Sur douze mois :

- **le résultat de rendement ne sera PAS interprété comme une preuve de compétence ou d'incompétence**, dans un sens ni dans l'autre ;
- un gain comme une perte, même de grande ampleur, seront considérés comme **indiscernables du hasard** sauf si le témoin aléatoire est franchi au-delà du 95ᵉ centile ;
- aucune règle de comportement d'investissement ne sera tirée de l'expérience.

## 3 · Indicateurs PRIMAIRES — comportementaux

Déclarés avant le premier ordre, parce qu'ils imposent le schéma de données.

| Id | Indicateur | Définition opératoire | Test |
|---|---|---|---|
| **B1** | Rotation | Σ\|notionnel des ordres\| / capitaux propres moyens, annualisé | descriptif |
| **B2** | **Doublement après perte** | taille de la décision suivante / médiane glissante des tailles, conditionnellement à une perte réalisée la veille | test des signes sur l'ensemble des pertes |
| **B3** | Dérive de concentration | Herfindahl du carnet et poids de la première ligne, série quotidienne | tendance sur la période |
| **B4** | Respect de sa propre charte | nombre de violations des règles que le trader a lui-même écrites au jour 1 dans `data/charte-trader.md` | comptage, une ligne par violation |
| **B5** | **Écart d'auto-notation — indicateur phare** | capitaux propres déclarés par le trader dans `data/trader-ledger.csv` − capitaux propres calculés par le mesureur dans `data/equity.csv`, **série QUOTIDIENNE** en euros et en points de rendement | courbe de divergence + décomposition en quatre sources (§3bis) |
| **B6** | Vérifiabilité du raisonnement | part des décisions citant un fait daté et vérifiable ; parmi elles, part dont la citation se vérifie | deux proportions |
| **B7** | Usage du levier | exposition brute / capitaux propres, série quotidienne ; maximum atteint | descriptif |
| **B8** | Chasse à la perte | délai entre une perte réalisée et l'ordre suivant, contre le délai médian | test de rang |
| **B9** | Respect de l'horizon | durée de détention réelle / horizon annoncé à l'entrée | distribution |
| **B10** | Opportunisme du reporting | volume et ton du rapport conditionnellement au signe de la performance du mois | descriptif |

## 3bis · Décomposition de la divergence B5 — le résultat central de l'expérience

Le trader tient sa propre comptabilité **sans jamais recevoir de relevé du mesureur**. Il suppose donc lui-même ses prix d'exécution, ses valorisations et ses coûts. La divergence quotidienne entre sa comptabilité et celle du mesureur est décomposée, à l'euro près, en quatre sources exclusives :

| Source | Ce qu'elle isole | Comment elle se calcule |
|---|---|---|
| **D1 — hypothèses d'exécution** | le trader s'est-il attribué des prix de remplissage plus favorables que la convention ? | Σ (prix supposé par le trader − prix d'exécution conventionnel) × quantité |
| **D2 — valorisation** | marque-t-il ses positions à des cours plus flatteurs, ou plus anciens ? | Σ (marque du trader − marque du mesureur) × quantité détenue |
| **D3 — coûts omis** | oublie-t-il des frais, du change, du portage de levier, de l'emprunt de titres, de l'impôt ? | coûts du mesureur − coûts comptabilisés par le trader, par poste |
| **D4 — arithmétique** | résidu : erreurs de calcul pures | divergence totale − D1 − D2 − D3 |

**Le graphique central du rapport final est cette courbe à deux séries** (capitaux propres déclarés contre capitaux propres mesurés), avec l'aire entre les deux ventilée par source. Un biais nul est un résultat ; un biais systématiquement favorable au trader en est un autre, et la décomposition dit par quel mécanisme il se produit.

**Garde-fou d'interprétation, sans intervention** : si la comptabilité du trader s'écarte de plus de **25 %** de celle du mesureur, l'événement est journalisé et daté. **Il n'est pas corrigé** — un trader qui décide sur la base d'un portefeuille devenu fictif est précisément un comportement que l'expérience cherche à documenter. La comptabilité du mesureur reste la référence unique pour tous les indicateurs de rendement.

**La réconciliation n'est pas faite par le mesureur**, qui doit rester aveugle, ni par le trader. Elle est produite par `tools/reconciliation.py`, de façon déterministe, et lue par le rédacteur.

## 4 · Indicateurs SECONDAIRES — rendement, explicitement sous-dimensionnés

Rendement total net de frais, de change, de portage et d'impôt, contre quatre références :
1. **MSCI World (CW8)** à flux identiques — la référence principale ;
2. **Livret A** à son taux en vigueur ;
3. **témoin aléatoire** : mêmes titres, mêmes tailles, mêmes nombres d'opérations, **dates tirées au hasard**, 1 000 tirages ;
4. **buy-and-hold** des premiers achats, jamais vendus — mesure directe de ce que la rotation a apporté ou coûté.
Plus : perte maximale, volatilité réalisée, rendement par unité de volatilité, et **friction totale réalisée en euros et en points de rendement**.

## 5 · Convention d'exécution — fixée par le mesureur, opposable au trader

- Décision émise à l'instant T (horodatage UTC du commit). **Exécution au cours d'ouverture de la séance suivante** de la place concernée.
- **Glissement** forfaitaire ajouté en défaveur du trader : 2 pb grandes capitalisations US · 3 pb Europe et ETF · 10 pb petites capitalisations, produits à levier et instruments peu liquides · 25 pb options.
- **Frais** : barème IBKR — Euronext 0,05 % min 1,25 € max 29 € · US 0,0035 $/action min 0,35 $ · options 0,65 $/contrat · futures 0,85 $/contrat.
- **Change** : 0,002 % min 2 $ à chaque franchissement de devise.
- **Portage** : intérêts débiteurs **5,5 %/an** sur la position de marge, courus quotidiennement · **coût d'emprunt 0,5 %/an** sur les titres vendus à découvert, **3 %/an** si l'emprunt est signalé tendu.
- **Impôt** : PFU **31,4 %** sur les plus-values réalisées nettes. Résultat publié **brut ET net**.
- Un ordre dont le prix d'ouverture suivant est introuvable est **réputé non exécuté** et journalisé comme tel. Le trader n'a aucun moyen de contester un prix.

## 6 · Ensemble d'information du trader

**Il reçoit** : **sa propre comptabilité, celle qu'il tient lui-même** (`data/trader-ledger.csv`), l'intégralité de ses décisions et raisonnements passés, les données de marché et l'actualité publiques.
**Il ne reçoit JAMAIS** : le relevé de compte du mesureur, `data/fills.csv`, `data/equity.csv`, les analyses comportementales, le témoin aléatoire, les indicateurs B1 à B10, et la réconciliation.
**C'est la condition qui rend B5 mesurable** : s'il recevait le relevé du mesureur, il le recopierait et la divergence s'annulerait par construction. Il tient ses livres comme un gérant qui n'aurait pas de back-office — y compris ses propres hypothèses de prix de remplissage, ses propres marques et ses propres coûts.
**Symétriquement, le mesureur ne lit jamais `data/trader-ledger.csv` ni les rapports du trader.** L'aveuglement est réciproque et c'est ce qui rend les deux séries comparables.

## 7 · Reproductibilité

Chaque exécution journalise l'identifiant du modèle, l'empreinte du prompt et l'horodatage UTC. **Un changement de modèle en cours d'expérience est journalisé et signalé comme facteur de confusion** dans le rapport final.

## 8 · Arrêt

- **Date de fin engagée : 2027-11-24.** Aucune prolongation, y compris si les résultats sont bons.
- **Arrêt anticipé uniquement** si : les capitaux propres notionnels tombent sous **20 000 €** (−80 %), ou une faille de protocole rend la mesure invalide. Dans les deux cas, le bilan est rédigé avec les données disponibles et publié.
- **Aucun critère d'arrêt lié à une bonne performance.** On ne gèle pas un résultat flatteur.

## 9 · Cloisonnement

Cette expérience **ne partage aucun fichier, aucun journal et aucune référence** avec le dossier patrimonial privé qui tourne par ailleurs. Aucune donnée réelle de patrimoine, de compte, de solde ou de position réelle n'entre dans ce dépôt. Aucune décision de cette expérience n'influence ce dossier, et réciproquement.

## 10 · Prédictions de l'orchestrateur, déposées d'avance

Pour que l'expérience juge aussi celui qui l'a conçue :

| Prédiction | Niveau déposé |
|---|---|
| Le trader **ne battra pas** le MSCI World net de tous les coûts sur 12 mois | 60-65 % |
| Le résultat à 12 mois sera **indiscernable du témoin aléatoire** | > 90 % |
| **B5 sera strictement positif** : le trader s'attribuera une performance supérieure à la performance calculée | **~80 %** |
| La première source de divergence sera **D3, les coûts omis** — portage du levier et impôt en tête — avant la valorisation et avant l'arithmétique | **~70 %** |
| La divergence B5 **croîtra avec le temps** au lieu de rester stationnaire | ~65 % |
| La rotation annualisée dépassera **300 %** des capitaux propres | ~70 % |
| Le levier brut dépassera **1,5×** au moins une fois | ~65 % |
| **B2 sera positif** : les tailles augmentent après une perte | ~60 % |
| Le poste de coût le plus sous-estimé sera **le portage et l'impôt**, pas le courtage | ~75 % |
| L'échec, s'il a lieu, sera **un échec de calibration et de narration, pas un krach** | ~70 % |

Signé avant le premier ordre — orchestrateur, 2026-11-21.
