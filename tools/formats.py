#!/usr/bin/env python3
"""
Formats canoniques de toutes les données de l'expérience — source unique.

Chaque fichier écrit par un agent ou par un script a ici son en-tête exact, dans
l'ordre, et les règles que chaque ligne doit respecter. `tools/valider-formats.py`
les applique, `tools/mesure.py` et `tools/publication.py` les importent : un format
ne peut donc pas dériver d'un script à l'autre sans que ce fichier change, et ce
changement se lit dans l'historique git.

Conventions communes à tous les fichiers :
- CSV séparé par des virgules, UTF-8, première ligne = en-tête exact ci-dessous ;
- dates `AAAA-MM-JJ`, horodatages `AAAA-MM-JJTHH:MM:SSZ` (UTC) ;
- nombres avec un point décimal, sans séparateur de milliers ni symbole (« 1234.5 », jamais « 1 234,5 € ») ;
- un champ qui contient une virgule est entre guillemets doubles ;
- vide = donnée absente. « - » n'est permis que là où il est dit permis.
"""

VERSION = "formats/2"

DATE = r"^\d{4}-\d{2}-\d{2}$"
HORODATAGE = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"
DEVISE = r"^[A-Z]{3}$"

ACTIONS = ("ouvrir", "renforcer", "reduire", "fermer", "inverser", "aucune")
INSTRUMENTS = ("action", "etf", "etc", "obligation", "option", "future", "levier")
SENS = ("long", "short")
TYPES_ORDRE = ("marche", "limite", "gtc", "stop", "stop_limite")
LIQUIDITE = ("grande", "moyenne", "faible")
QUALITES = ("primaire", "web_horodate", "web_non_horodate")
REGIMES = ("cash", "reg_t", "portfolio_margin")

# Étiquette de stratégie que le trader déclare pour chaque ordre. Vocabulaire fermé
# pour que la stratégie puisse être suivie dans le temps ; « autre » est toujours permis.
STRATEGIES = {
    "indiciel": "exposition large et passive à un marché",
    "tendance": "suivi de tendance, momentum",
    "retour_moyenne": "pari sur un retour à la moyenne",
    "valeur": "titre jugé sous-évalué",
    "croissance": "croissance des résultats",
    "qualite": "rentabilité, bilan, avantage durable",
    "macro": "pari sur une variable macroéconomique (taux, change, matières premières)",
    "evenementiel": "événement daté : résultats, fusion, décision réglementaire",
    "revenu": "dividende, coupon, prime d'option",
    "relatif": "paire ou écart entre deux actifs",
    "volatilite": "pari sur la volatilité elle-même",
    "couverture": "réduction d'un risque déjà porté",
    "liquidite": "mise en attente, gestion de trésorerie",
    "autre": "aucune des catégories ci-dessus",
}

# ------------------------------------------------------------------ fichiers écrits par le TRADER
DECISIONS = ["horodatage_utc", "id_decision", "id_position", "action", "instrument", "ticker", "place",
             "devise", "sens", "quantite", "multiplicateur", "type_ordre", "limite", "horizon_annonce",
             "prix_suppose", "liquidite", "notionnel_sous_jacent", "strategie", "raison_courte",
             "fait_date_cite", "source"]

TRADER_LEDGER = ["date", "capitaux_propres_eur", "cash_eur", "valeur_positions_eur", "pv_realisee_cumulee_eur",
                 "frais_cumules_eur", "change_cumule_eur", "portage_cumule_eur", "emprunt_cumule_eur",
                 "impot_estime_eur", "note", "horodatage_utc", "pv_latente_eur", "exposition_brute_eur",
                 "regime_marge"]

TRADER_POSITIONS = ["date", "horodatage_utc", "ticker", "id_position", "instrument", "sens", "quantite",
                    "multiplicateur", "devise", "prix_revient", "marque", "source_marque", "fx_eurusd",
                    "valeur_eur"]

TRADER_MARKETDATA = ["date", "horodatage_consultation_utc", "instrument", "ticker", "grandeur", "valeur",
                     "devise", "source", "url_ou_reference", "usage"]

REGIME_MARGE = ["date_declaration", "date_effet", "regime", "capitaux_propres_declares_eur", "motif"]

# ------------------------------------------------------------------ fichiers écrits par le MESUREUR
PRICES = ["date", "ticker", "devise", "ouverture", "haut", "bas", "cloture", "source", "qualite"]

# ------------------------------------------------------------------ sorties de tools/mesure.py
FILLS = ["id_decision", "horodatage_decision", "date_execution", "ticker", "instrument", "place", "devise",
         "action", "sens", "sens_economique", "quantite", "horizon_annonce", "strategie", "prix_ouverture",
         "glissement_pb", "id_position", "type_ordre", "limite", "validite", "sessions_testees",
         "prix_execution", "prix_suppose_trader", "ecart_prix_suppose_pct", "multiplicateur",
         "notionnel_sous_jacent", "montant_devise", "fx", "montant_eur", "courtage_eur", "change_eur",
         "glissement_eur", "cout_total_eur", "statut", "source_prix", "qualite_prix", "detail_frais", "motif"]

EQUITY = ["date", "regime_marge", "cash_eur", "valeur_positions_eur", "capitaux_propres_eur",
          "capitaux_propres_net_pfu_eur", "capitaux_liquidatifs_nets_eur",
          "exposition_brute_eur", "exposition_nette_eur", "levier_brut", "exigence_initiale_eur",
          "exigence_maintien_eur", "marge_disponible_eur", "appel_de_marge",
          "pv_realisee_cumulee_eur", "pv_latente_eur", "pfu_du_eur", "pfu_latent_eur",
          "frais_cumules_eur", "change_cumule_eur", "glissement_cumule_eur", "portage_cumule_eur",
          "emprunt_cumule_eur", "liquidations_cout_cumule_eur", "friction_totale_cumulee_eur",
          "nb_lignes", "hhi", "poids_premiere_ligne_pct", "perf_depuis_debut_pct", "cours_manquants"]

POSITIONS = ["date", "ticker", "id_position", "instrument", "sens", "place", "devise", "quantite",
             "multiplicateur", "cours", "date_cours", "fx_eurusd", "valeur_eur", "exposition_eur",
             "poids_pct", "prix_revient_eur", "pv_latente_eur", "strategie"]

BENCHMARK = ["date", "capitaux_propres_eur", "capitaux_propres_net_pfu_eur",
             "iwda_flux_identiques_eur", "ecart_vs_iwda_eur", "ecart_net_vs_iwda_eur",
             "cw8_flux_identiques_eur", "ecart_vs_cw8_eur", "ecart_net_vs_cw8_eur", "ecart_cw8_vs_iwda_pct",
             "wpea_flux_identiques_eur", "ecart_vs_wpea_eur", "ecart_net_vs_wpea_eur", "ecart_wpea_vs_iwda_pct",
             "livret_a_eur", "ecart_vs_livret_eur", "iwda_liquidatif_net_eur"]

# Comparaison EXPLORATOIRE, non pré-enregistrée : véhicules cotés d'investisseurs connus,
# à flux identiques (120 000 € investis le premier jour). Un véhicule coté n'est pas le
# portefeuille de son gérant : c'est un repère public, pas une réplique.
INVESTISSEURS = {
    "BRK-B": ("Warren Buffett", "Berkshire Hathaway (classe B), NYSE"),
    "PSH": ("Bill Ackman", "Pershing Square Holdings, Euronext Amsterdam"),
    "ARKK": ("Cathie Wood", "ARK Innovation ETF, NYSE Arca"),
    "CARMPAT": ("Édouard Carmignac", "Carmignac Patrimoine A EUR Acc (FR0010135103), valeur liquidative"),
}
BENCHMARK_INVESTISSEURS = ["date", "ticker", "investisseur", "vehicule", "devise", "cours",
                           "valeur_flux_identiques_eur", "qualite"]

METRICS = ["indicateur", "valeur", "n", "note"]

# ------------------------------------------------------------------ sortie de tools/reconciliation.py
RECONCILIATION = ["date", "capitaux_declares_eur", "capitaux_mesures_eur", "impot_declare_eur",
                  "impot_mesure_eur", "capitaux_declares_nets_eur", "capitaux_mesures_nets_eur",
                  "divergence_eur", "divergence_pct_des_capitaux_mesures",
                  "D1_hypotheses_execution_eur", "D2_valorisation_eur", "D2_methode", "D3_couts_omis_eur",
                  "D3_detail", "D4_arithmetique_eur", "depasse_25_pct"]

# ------------------------------------------------------------------ fichiers de journal
JOURNAL_TRADER = r"^reports/trader/journal/\d{4}-\d{2}-\d{2}-(1308|1608|1908)\.md$"
RAPPORT_TRADER = r"^reports/trader/\d{4}-\d{2}\.md$"
NOTE_MESUREUR = r"^reports/mesureur/mesure-\d{4}-\d{2}-\d{2}\.md$"

FICHIERS = {
    "data/decisions.csv": DECISIONS,
    "data/trader-ledger.csv": TRADER_LEDGER,
    "data/trader-positions.csv": TRADER_POSITIONS,
    "data/trader-marketdata.csv": TRADER_MARKETDATA,
    "data/regime-marge.csv": REGIME_MARGE,
    "data/prices.csv": PRICES,
    "data/fills.csv": FILLS,
    "data/equity.csv": EQUITY,
    "data/positions.csv": POSITIONS,
    "data/benchmark.csv": BENCHMARK,
    "data/benchmark-investisseurs.csv": BENCHMARK_INVESTISSEURS,
    "data/metrics-comportement.csv": METRICS,
    "data/reconciliation.csv": RECONCILIATION,
}
