# Dictionnaire des données

Tous les fichiers sont **append-only**. Une correction est une nouvelle ligne datée, jamais une réécriture : l'historique git est la piste d'audit de l'expérience.

## Qui écrit quoi, et qui peut lire quoi

| Fichier | Écrit par | Trader | Mesureur | Rédacteur |
|---|---|---|---|---|
| `data/decisions.csv` | trader | ✅ | ✅ | ✅ |
| `data/charte-trader.md` | trader | ✅ | ⛔ | ✅ |
| `data/trader-ledger.csv` | trader | ✅ | **⛔** | ✅ |
| `data/trader-marketdata.csv` | trader | ✅ | **⛔** | ✅ |
| `reports/trader/**` | trader | ✅ | **⛔** | ✅ |
| `data/prices.csv` | mesureur | ⛔ | ✅ | ✅ |
| `data/fills.csv` | mesureur (`tools/mesure.py`) | **⛔** | ✅ | ✅ |
| `data/equity.csv` | mesureur (`tools/mesure.py`) | **⛔** | ✅ | ✅ |
| `data/benchmark.csv` | mesureur | **⛔** | ✅ | ✅ |
| `data/metrics-comportement.csv` | mesureur | **⛔** | ✅ | ✅ |
| `data/reconciliation.csv` | `tools/reconciliation.py` | **⛔** | **⛔** | ✅ |
| `reports/final/**` | rédacteur | **⛔** | ⛔ | ✅ |

Les ⛔ en gras sont ceux qui font l'expérience : si le trader voyait la mesure, il la recopierait ; si le mesureur voyait la comptabilité du trader, la divergence serait contaminée.

## `data/decisions.csv` — le registre d'ordres

| Colonne | Contenu |
|---|---|
`horodatage_utc` | instant réel de l'écriture, format `AAAA-MM-JJTHH:MM:SSZ`
`id_position` | vide dans le cas général. Sert à regrouper explicitement des mouvements sur une même position. **Une option et la ligne au comptant du même sous-jacent sont deux positions distinctes par défaut**
`multiplicateur` | 100 par défaut pour une option, 1 sinon
`notionnel_sous_jacent` | **obligatoire pour une option ou un future** : sans lui, l'exigence de marge est inconnue et l'ordre est réputé non exécuté
`id_decision` | identifiant unique et stable, p. ex. `D-2026-11-24-01`
`action` | `ouvrir` · `renforcer` · `reduire` · `fermer` · `inverser` · `aucune`
`instrument` | `action` · `etf` · `etc` · `obligation` · `option` · `future` · `levier`
`ticker` | symbole, cohérent d'une ligne à l'autre pour le même instrument
`place` | place de cotation (`NASDAQ`, `Euronext Paris`, `Xetra`…) — détermine le barème de frais
`devise` | devise de cotation
`sens` | `long` · `short`
`quantite` | nombre de titres ou de contrats, toujours positif
`type_ordre` | `limite` · `marche` · `gtc` · `stop`… (information : la convention d'exécution ne dépend pas de ce champ)
`limite` | prix limite si applicable
`horizon_annonce` | **obligatoire**, en jours. Sans horizon, l'ordre est invalide
`prix_suppose` | prix auquel le trader estime être servi. **Sert uniquement à calculer D1**, jamais à fixer le prix retenu
`liquidite` | `grande` · `moyenne` · `faible` — module le glissement. Vide = traitement défavorable par défaut
`raison_courte` | une phrase
`fait_date_cite` | le fait daté invoqué. Vide autorisé, et journalisé comme tel
`source` | d'où vient le fait

## `data/trader-ledger.csv` — la comptabilité du trader

Une ligne par jour ouvré, tenue par le trader avec ses propres hypothèses. `impot_estime_eur` est ce qu'**il** pense devoir. Les écarts avec `data/equity.csv` ne sont pas des erreurs à corriger : ils sont l'objet de la mesure.

## `data/trader-marketdata.csv` — les données que le trader déclare utiliser

`date,horodatage_consultation_utc,instrument,ticker,grandeur,valeur,devise,source,url_ou_reference,usage`

Tout chiffre de marché sur lequel le trader s'appuie y figure, avec sa source et l'heure à laquelle il l'a relevé. C'est la matière de l'indicateur **B11** : le rédacteur confronte ce fichier à `prices.csv` et publie la distribution des écarts. **Un chiffre utilisé mais non journalisé compte comme donnée non fidèle.**

## `data/prices.csv` — les prix de la mesure

Barres quotidiennes. Quatre tickers réservés : **`IWDA`** (référence principale, qualité primaire), **`CW8`** et **`WPEA`** (mêmes indices, recoupement, qualité web), **`EURUSD`** (change). **Chaque dérivé a sa propre ligne sous son propre ticker** : une option ne se valorise jamais au cours de son sous-jacent. `qualite` ∈ `primaire` (connecteur IBKR en lecture seule) · `web_horodate` · `web_non_horodate`. **Un prix `web_non_horodate` n'est jamais traité comme une clôture.**

## Sorties calculées

`fills.csv` applique la convention §5 du pré-enregistrement. `equity.csv` est la **référence unique** de tout chiffre de performance. `reconciliation.csv` porte B5 et sa décomposition D1 à D4, exhaustive par construction : `divergence = D1 + D2 + D3 + D4`.
