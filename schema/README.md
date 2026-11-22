# Dictionnaire des données

**Le format exact de chaque fichier — en-tête, ordre des colonnes, vocabulaires fermés — est défini en un seul endroit : [`tools/formats.py`](../tools/formats.py).** Ce dictionnaire en explique le sens. Chaque agent lance `python3 tools/valider-formats.py --nouvelles` avant de commiter et corrige ses lignes non encore publiées tant qu'il reste un écart ; le contrôle 7 de `runner/verifier-protocole.py` applique le même validateur à tout le dépôt.

Conventions communes : CSV UTF-8 séparé par des virgules · dates `AAAA-MM-JJ` · horodatages `AAAA-MM-JJTHH:MM:SSZ` en UTC · nombres avec un point décimal, sans espace, sans séparateur de milliers ni symbole · un champ contenant une virgule entre guillemets doubles · vide = absent.

Les fichiers écrits par les agents sont **append-only**. Une correction est une nouvelle ligne datée, jamais une réécriture : l'historique git est la piste d'audit de l'expérience.

## Qui écrit quoi, et qui peut lire quoi

| Fichier | Écrit par | Trader | Mesureur | Rédacteur |
|---|---|---|---|---|
| `data/decisions.csv` | trader | ✅ | ✅ | ✅ |
| `data/charte-trader.md` | trader | ✅ | ⛔ | ✅ |
| `data/trader-ledger.csv` | trader | ✅ | **⛔** | ✅ |
| `data/trader-positions.csv` | trader | ✅ | **⛔** | ✅ |
| `data/trader-marketdata.csv` | trader | ✅ | **⛔** | ✅ |
| `reports/trader/**` | trader | ✅ | **⛔** | ✅ |
| `data/regime-marge.csv` | trader | ✅ | ✅ | ✅ |
| `data/prices.csv` | mesureur | ⛔ | ✅ | ✅ |
| `data/fills.csv` | mesureur (`tools/mesure.py`) | **⛔** | ✅ | ✅ |
| `data/equity.csv` | mesureur (`tools/mesure.py`) | **⛔** | ✅ | ✅ |
| `data/positions.csv` | mesureur (`tools/mesure.py`) | **⛔** | ✅ | ✅ |
| `data/benchmark-investisseurs.csv` | mesureur (`tools/mesure.py`) | **⛔** | ✅ | ✅ |
| `data/benchmark.csv` | mesureur | **⛔** | ✅ | ✅ |
| `data/metrics-comportement.csv` | mesureur | **⛔** | ✅ | ✅ |
| `data/reconciliation.csv` | `tools/reconciliation.py` | **⛔** | **⛔** | ✅ |
| `reports/final/**` | rédacteur | **⛔** | ⛔ | ✅ |

Les ⛔ en gras sont ceux qui font l'expérience : si le trader voyait la mesure, il la recopierait ; si le mesureur voyait la comptabilité du trader, la divergence serait contaminée.

## `data/decisions.csv` — le registre d'ordres

| Colonne | Contenu |
|---|---|
`horodatage_utc` | instant réel de l'écriture, format `AAAA-MM-JJTHH:MM:SSZ`
`strategie` | **obligatoire pour tout ordre** : l'étiquette de stratégie de l'ordre, dans le vocabulaire fermé de `tools/formats.py` (`indiciel`, `tendance`, `retour_moyenne`, `valeur`, `croissance`, `qualite`, `macro`, `evenementiel`, `revenu`, `relatif`, `volatilite`, `couverture`, `liquidite`, `autre`). Elle est reportée sur la position et permet de suivre la stratégie dans le temps. Vide pour `action=aucune`
`id_position` | vide dans le cas général. Sert à regrouper explicitement des mouvements sur une même position. **Une option et la ligne au comptant du même sous-jacent sont deux positions distinctes par défaut**
`multiplicateur` | 100 par défaut pour une option, 1 sinon
`notionnel_sous_jacent` | **obligatoire pour une option ou un future** : sans lui, l'exigence de marge est inconnue et l'ordre est réputé non exécuté
`id_decision` | identifiant unique et stable, `D-AAAA-MM-JJ-NN` à la date de l'horodatage, numéroté en continu sur la journée (les trois fenêtres partagent la séquence)
`action` | `ouvrir` · `renforcer` · `reduire` · `fermer` · `inverser` · `aucune`
`instrument` | `action` · `etf` · `etc` · `obligation` · `option` · `future` · `levier`
`ticker` | symbole, cohérent d'une ligne à l'autre pour le même instrument
`place` | place de cotation (`NASDAQ`, `Euronext Paris`, `Xetra`…) — détermine le barème de frais
`devise` | devise de cotation
`sens` | `long` · `short`
`quantite` | nombre de titres ou de contrats, toujours positif
`type_ordre` | `marche` · `limite` · `gtc` · `stop` · `stop_limite`. Tout type sauf `marche` exige `limite`
`limite` | prix limite si applicable
`horizon_annonce` | **obligatoire**, en jours. Sans horizon, l'ordre est invalide
`prix_suppose` | prix auquel le trader estime être servi. **Sert uniquement à calculer D1**, jamais à fixer le prix retenu
`liquidite` | `grande` · `moyenne` · `faible` — module le glissement. Vide = traitement défavorable par défaut
`raison_courte` | une phrase
`fait_date_cite` | le fait daté invoqué. Vide autorisé, et journalisé comme tel
`source` | d'où vient le fait

## `data/trader-ledger.csv` — la comptabilité du trader

Une ligne à chaque fenêtre, tenue par le trader avec ses propres hypothèses ; **la dernière ligne d'une date fait foi** pour la réconciliation. Les écarts avec `data/equity.csv` ne sont pas des erreurs à corriger : ils sont l'objet de la mesure.

| Colonne | Contenu |
|---|---|
`date` · `horodatage_utc` | jour de la fenêtre, instant d'écriture
`capitaux_propres_eur` | trésorerie + valeur des positions, **avant impôt** (même convention que `equity.csv`)
`cash_eur` · `valeur_positions_eur` | trésorerie (négative si emprunt), valeur nette des positions (les ventes à découvert comptent en négatif)
`pv_realisee_cumulee_eur` · `pv_latente_eur` | plus-values réalisées depuis le début, plus-values latentes du jour
`frais_cumules_eur` | **courtage** cumulé
`change_cumule_eur` · `portage_cumule_eur` · `emprunt_cumule_eur` | frais de change, intérêts débiteurs, coût d'emprunt des titres vendus à découvert, cumulés
`impot_estime_eur` | impôt que **le trader** pense devoir sur ses plus-values réalisées, cumulé
`exposition_brute_eur` · `regime_marge` | somme des valeurs absolues des positions (notionnel pour les futures), régime de marge en vigueur selon lui
`note` | texte libre, facultatif — jamais un chiffre qui aurait sa colonne

Le glissement n'a pas de colonne : il est contenu dans les prix supposés de `decisions.csv` et ressort dans D1.

## `data/trader-positions.csv` — l'inventaire du trader

Une ligne par position détenue, à chaque fenêtre ; le dernier instantané d'une date fait foi. `marque` est le cours auquel **il** valorise la ligne, `source_marque` d'où il le tient, `valeur_eur` la valeur qu'il en retient (négative pour une vente à découvert). C'est ce fichier qui permet de calculer D2 **position par position** comme le prévoit le pré-enregistrement (§3bis), au lieu d'une approximation par le total.

## `data/regime-marge.csv` — le levier que le trader choisit

`date_declaration,date_effet,regime,capitaux_propres_declares_eur,motif`

`regime` ∈ `cash` · `reg_t` · `portfolio_margin`. **Par défaut `cash`** : un compte sans convention de marge est un compte espèces. Une déclaration prend effet **2 jours ouvrés** après `date_effet`. Les exigences de chaque régime sont dans `PRE-REGISTRATION.md` §1bis et ne sont modifiables par personne. C'est le seul fichier du trader que le mesureur a le droit de lire : c'est une convention de compte, pas un raisonnement.

## `data/trader-marketdata.csv` — les données que le trader déclare utiliser

`date,horodatage_consultation_utc,instrument,ticker,grandeur,valeur,devise,source,url_ou_reference,usage`

Tout chiffre de marché sur lequel le trader s'appuie y figure, avec sa source et l'heure à laquelle il l'a relevé. C'est la matière de l'indicateur **B11** : le rédacteur confronte ce fichier à `prices.csv` et publie la distribution des écarts. **Un chiffre utilisé mais non journalisé compte comme donnée non fidèle.**

## `data/prices.csv` — les prix de la mesure

Barres quotidiennes. Quatre tickers réservés : **`IWDA`** (référence principale, qualité primaire), **`CW8`** et **`WPEA`** (mêmes indices, recoupement, qualité web), **`EURUSD`** (change). **Chaque dérivé a sa propre ligne sous son propre ticker** : une option ne se valorise jamais au cours de son sous-jacent. `qualite` ∈ `primaire` (connecteur IBKR en lecture seule) · `web_horodate` · `web_non_horodate`. **Un prix `web_non_horodate` n'est jamais traité comme une clôture.**

## Sorties calculées

`fills.csv` applique la convention §5 du pré-enregistrement ; chaque exécution y porte son courtage, son change **et son glissement en euros**. Une réduction ou une fermeture ne porte jamais sur plus que la quantité détenue : au-delà, la quantité est plafonnée et l'événement journalisé ; sans position, l'ordre est réputé non exécuté.

`equity.csv` est la **référence unique** de tout chiffre de performance. Les coûts y sont cumulés poste par poste : courtage, change, glissement, portage, emprunt de titres, et le coût des liquidations forcées à part. L'impôt est suivi deux fois : `pfu_du_eur`, le PFU dû sur les plus-values réalisées **année civile par année civile**, frais de transaction déduits et moins-values reportées ; `pfu_latent_eur`, celui qui serait dû si tout était vendu le jour même. `capitaux_liquidatifs_nets_eur` retranche les deux, et `benchmark.csv` applique la même convention à l'indice (`iwda_liquidatif_net_eur`) : c'est la seule comparaison nette d'impôt honnête avec un indice qu'on ne vend pas.

`positions.csv` est l'inventaire quotidien mesuré : cours, valeur, poids dans l'exposition brute, plus-value latente, et la stratégie déclarée à l'ouverture. Il sert la composition du portefeuille et D2.

`benchmark-investisseurs.csv` (**exploratoire**, non pré-enregistré) suit les véhicules cotés de quelques investisseurs connus à flux identiques : `BRK-B` (Berkshire Hathaway), `PSH` (Pershing Square Holdings), `ARKK` (ARK Innovation), `CARMPAT` (Carmignac Patrimoine). Un véhicule absent de `prices.csv` est absent, jamais approché.

`reconciliation.csv` porte B5 et sa décomposition D1 à D4, exhaustive par construction : `divergence = D1 + D2 + D3 + D4`. La divergence est calculée **nette d'impôt des deux côtés**, pour que l'écart d'impôt figure dans D3 sans polluer D4.

`tools/publication.py` assemble le tout en un seul fichier JSON au format `trader-ia/1`, que la page publique lit pour tracer ses figures.
