#!/usr/bin/env python3
"""
Validateur de formats — chaque agent le lance avant de commiter.

Applique `tools/formats.py` à toutes les données : en-tête exact, dates et
horodatages, vocabulaires fermés, nombres, champs obligatoires, identifiants
uniques, nommage des journaux. Bibliothèque standard uniquement.

Usage :
    python3 tools/valider-formats.py              # tout le dépôt
    python3 tools/valider-formats.py --nouvelles  # seulement les lignes pas encore commitées

Code de sortie 0 si tout est conforme, 1 sinon. Le mode --nouvelles est celui des
agents : une ligne déjà publiée ne se corrige jamais (append-only), une ligne que
l'on vient d'écrire se corrige avant le commit.
"""
import argparse, csv, io, os, re, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import formats as F  # noqa: E402

NOMBRE = re.compile(r"^-?\d+(\.\d+)?([eE][-+]?\d+)?$")


class Rapport:
    def __init__(self):
        self.erreurs = []

    def err(self, fichier, ligne, msg):
        self.erreurs.append(f"{fichier}:{ligne} — {msg}")


def lignes_publiees(R, rel):
    """Nombre de lignes de données déjà présentes dans HEAD (0 si le fichier n'y est pas)."""
    try:
        txt = subprocess.run(["git", "-C", R, "show", f"HEAD:{rel}"], capture_output=True,
                             text=True, check=True).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return 0
    return max(0, len([l for l in txt.splitlines() if l.strip()]) - 1)


def est_nombre(v):
    return bool(NOMBRE.match(v))


def verifier_champs(rap, rel, n, r, regles):
    for col, regle in regles.items():
        v = (r.get(col) or "").strip()
        oblig, kind = regle[0], regle[1]
        if not v:
            if oblig:
                rap.err(rel, n, f"`{col}` obligatoire, vide")
            continue
        if kind == "date" and not re.match(F.DATE, v):
            rap.err(rel, n, f"`{col}` = « {v} » : attendu AAAA-MM-JJ")
        elif kind == "horodatage" and not re.match(F.HORODATAGE, v):
            rap.err(rel, n, f"`{col}` = « {v} » : attendu AAAA-MM-JJTHH:MM:SSZ")
        elif kind == "nombre" and not est_nombre(v):
            rap.err(rel, n, f"`{col}` = « {v} » : nombre attendu, point décimal, sans espace ni symbole")
        elif kind == "positif" and (not est_nombre(v) or float(v) <= 0):
            rap.err(rel, n, f"`{col}` = « {v} » : nombre strictement positif attendu")
        elif kind == "devise" and not re.match(F.DEVISE, v):
            rap.err(rel, n, f"`{col}` = « {v} » : code ISO à trois lettres attendu (EUR, USD…)")
        elif isinstance(kind, tuple) and v not in kind:
            rap.err(rel, n, f"`{col}` = « {v} » : valeurs permises {', '.join(kind)}")


REGLES = {
    "data/trader-ledger.csv": {
        "date": (1, "date"), "horodatage_utc": (1, "horodatage"),
        **{c: (1, "nombre") for c in ("capitaux_propres_eur", "cash_eur", "valeur_positions_eur",
                                       "pv_realisee_cumulee_eur", "frais_cumules_eur", "change_cumule_eur",
                                       "portage_cumule_eur", "emprunt_cumule_eur", "impot_estime_eur",
                                       "pv_latente_eur", "exposition_brute_eur")},
        "regime_marge": (1, F.REGIMES),
    },
    "data/trader-positions.csv": {
        "date": (1, "date"), "horodatage_utc": (1, "horodatage"), "ticker": (1, "texte"),
        "instrument": (1, F.INSTRUMENTS), "sens": (1, F.SENS), "quantite": (1, "positif"),
        "multiplicateur": (1, "positif"), "devise": (1, "devise"), "prix_revient": (1, "nombre"),
        "marque": (1, "nombre"), "source_marque": (1, "texte"), "fx_eurusd": (0, "positif"),
        "valeur_eur": (1, "nombre"),
    },
    "data/trader-marketdata.csv": {
        "date": (1, "date"), "horodatage_consultation_utc": (1, "horodatage"), "ticker": (1, "texte"),
        "grandeur": (1, "texte"), "valeur": (1, "nombre"), "source": (1, "texte"), "usage": (1, "texte"),
        "devise": (0, "devise"),
    },
    "data/regime-marge.csv": {
        "date_declaration": (1, "date"), "date_effet": (1, "date"), "regime": (1, F.REGIMES),
        "capitaux_propres_declares_eur": (1, "nombre"), "motif": (1, "texte"),
    },
    "data/prices.csv": {
        "date": (1, "date"), "ticker": (1, "texte"), "devise": (1, "devise"), "ouverture": (0, "nombre"),
        "haut": (0, "nombre"), "bas": (0, "nombre"), "cloture": (0, "nombre"), "source": (1, "texte"),
        "qualite": (1, F.QUALITES),
    },
}


def valider_decisions(rap, rel, n, r, ids):
    action = (r.get("action") or "").strip()
    verifier_champs(rap, rel, n, r, {"horodatage_utc": (1, "horodatage"), "id_decision": (1, "texte"),
                                     "action": (1, F.ACTIONS), "raison_courte": (1, "texte")})
    idd = (r.get("id_decision") or "").strip()
    if idd:
        if not re.match(r"^D-\d{4}-\d{2}-\d{2}-\d{2,3}$", idd):
            rap.err(rel, n, f"`id_decision` = « {idd} » : attendu D-AAAA-MM-JJ-NN")
        elif (r.get("horodatage_utc") or "")[:10] and idd[2:12] != (r.get("horodatage_utc") or "")[:10]:
            rap.err(rel, n, f"`id_decision` {idd} ne porte pas la date de son horodatage")
        if idd in ids:
            rap.err(rel, n, f"`id_decision` {idd} déjà utilisé ligne {ids[idd]}")
        ids[idd] = n
    if action == "aucune" or action not in F.ACTIONS:
        return
    verifier_champs(rap, rel, n, r, {
        "instrument": (1, F.INSTRUMENTS), "ticker": (1, "texte"), "place": (1, "texte"),
        "devise": (1, "devise"), "sens": (1, F.SENS), "quantite": (1, "positif"),
        "multiplicateur": (0, "positif"), "type_ordre": (1, F.TYPES_ORDRE), "limite": (0, "positif"),
        "horizon_annonce": (1, "positif"), "prix_suppose": (1, "positif"), "liquidite": (0, F.LIQUIDITE),
        "notionnel_sous_jacent": (0, "positif"), "strategie": (1, tuple(F.STRATEGIES)),
        "fait_date_cite": (1, "texte"),
    })
    t = (r.get("type_ordre") or "").strip()
    if t in ("limite", "gtc", "stop", "stop_limite") and not (r.get("limite") or "").strip():
        rap.err(rel, n, f"ordre `{t}` sans `limite`")
    inst = (r.get("instrument") or "").strip()
    if inst in ("option", "future") and action in ("ouvrir", "renforcer", "inverser") \
            and not (r.get("notionnel_sous_jacent") or "").strip():
        rap.err(rel, n, f"{inst} sans `notionnel_sous_jacent` : l'ordre sera réputé non exécuté")
    if inst == "option" and not re.search(r"[CP]\d", (r.get("ticker") or "")):
        rap.err(rel, n, "option sans ticker propre (ex. NVDA-C200-JAN27) : elle ne sera pas valorisable")
    fait = (r.get("fait_date_cite") or "").strip()
    if fait and fait != "-" and not (r.get("source") or "").strip():
        rap.err(rel, n, "fait cité sans `source`")


def valider_csv(R, rel, attendu, rap, nouvelles):
    chemin = os.path.join(R, rel)
    if not os.path.exists(chemin):
        return
    with open(chemin, newline="", encoding="utf-8") as fh:
        brut = fh.read()
    if brut.startswith("﻿"):
        rap.err(rel, 1, "BOM UTF-8 en tête de fichier")
        brut = brut.lstrip("﻿")
    lecteur = csv.reader(io.StringIO(brut))
    tete = next(lecteur, [])
    if tete != attendu:
        manquantes = [c for c in attendu if c not in tete]
        en_trop = [c for c in tete if c not in attendu]
        detail = []
        if manquantes:
            detail.append("manquantes : " + ", ".join(manquantes))
        if en_trop:
            detail.append("en trop : " + ", ".join(en_trop))
        if not detail:
            detail.append("ordre des colonnes différent")
        rap.err(rel, 1, "en-tête non conforme à tools/formats.py — " + " · ".join(detail))
        return
    deja = lignes_publiees(R, rel) if nouvelles else 0
    ids = {}
    n_donnee = 0
    for i, row in enumerate(lecteur, start=2):
        if not any(c.strip() for c in row):
            continue
        n_donnee += 1
        if len(row) != len(attendu):
            if n_donnee > deja:
                rap.err(rel, i, f"{len(row)} champs au lieu de {len(attendu)} (virgule non protégée ?)")
            continue
        r = dict(zip(attendu, row))
        if rel == "data/decisions.csv":
            sous = Rapport()
            valider_decisions(sous, rel, i, r, ids)
            if n_donnee > deja:
                rap.erreurs += sous.erreurs
        elif rel in REGLES and n_donnee > deja:
            verifier_champs(rap, rel, i, r, REGLES[rel])


def valider_journaux(R, rap, nouvelles):
    base = os.path.join(R, "reports")
    if not os.path.isdir(base):
        return
    suivis = set()
    if nouvelles:
        try:
            out = subprocess.run(["git", "-C", R, "ls-files", "reports"], capture_output=True,
                                 text=True, check=True).stdout
            suivis = set(out.split())
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
    for dossier, motif in (("reports/trader", None), ("reports/mesureur", F.NOTE_MESUREUR)):
        racine = os.path.join(R, dossier)
        for d, _, fichiers in os.walk(racine):
            for nom in fichiers:
                if nom.startswith(".") or not nom.endswith(".md"):
                    continue
                rel = os.path.relpath(os.path.join(d, nom), R).replace(os.sep, "/")
                if rel in suivis:
                    continue
                if dossier == "reports/trader":
                    ok = re.match(F.JOURNAL_TRADER, rel) or re.match(F.RAPPORT_TRADER, rel)
                    attendu = "reports/trader/journal/AAAA-MM-JJ-HHMM.md (1308, 1608 ou 1908) ou reports/trader/AAAA-MM.md"
                else:
                    ok = re.match(motif, rel)
                    attendu = "reports/mesureur/mesure-AAAA-MM-JJ.md"
                if not ok:
                    rap.err(rel, 0, f"nom de fichier non conforme, attendu {attendu}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--racine", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ap.add_argument("--nouvelles", action="store_true",
                    help="ne contrôler que les lignes et fichiers pas encore commités")
    a = ap.parse_args()
    rap = Rapport()
    for rel, attendu in F.FICHIERS.items():
        valider_csv(a.racine, rel, attendu, rap, a.nouvelles)
    valider_journaux(a.racine, rap, a.nouvelles)
    portee = "lignes non commitées" if a.nouvelles else "tout le dépôt"
    if rap.erreurs:
        print(f"✗ {len(rap.erreurs)} écart(s) de format ({portee}, {F.VERSION}) :")
        for e in rap.erreurs:
            print("  - " + e)
        sys.exit(1)
    print(f"✓ formats conformes ({portee}, {F.VERSION})")


if __name__ == "__main__":
    main()
