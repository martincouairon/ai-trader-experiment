#!/usr/bin/env python3
"""Valide le classement quotidien du prévisionniste (expérience 2).

Usage :
    python3 experience-2/tools/valider-classement.py --date AAAA-MM-JJ
    python3 experience-2/tools/valider-classement.py            # toutes les dates

Code de sortie 0 si tout est conforme, 1 sinon. Les écarts sont listés un par ligne.
"""
import argparse
import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
UNIVERS = RACINE / "data" / "univers.csv"
CLASSEMENTS = RACINE / "data" / "classements.csv"
ENTETE = ["date", "horodatage_utc", "ticker", "rang", "raison"]
RE_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
RE_HORO = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
TAILLE = 50
RANGS_AVEC_RAISON = set(range(1, 6)) | set(range(TAILLE - 4, TAILLE + 1))


def lire_univers():
    with open(UNIVERS, newline="", encoding="utf-8") as f:
        return [r["ticker"] for r in csv.DictReader(f)]


def valider(date_cible=None):
    ecarts = []
    univers = lire_univers()
    if len(univers) != TAILLE or len(set(univers)) != TAILLE:
        ecarts.append(f"univers.csv : {len(set(univers))} tickers distincts, {TAILLE} attendus")
    with open(CLASSEMENTS, newline="", encoding="utf-8") as f:
        lecteur = csv.reader(f)
        entete = next(lecteur, None)
        if entete != ENTETE:
            return ecarts + [f"classements.csv : en-tête {entete}, attendu {ENTETE}"]
        par_date = defaultdict(list)
        for n, ligne in enumerate(lecteur, start=2):
            if len(ligne) != len(ENTETE):
                ecarts.append(f"ligne {n} : {len(ligne)} colonnes, {len(ENTETE)} attendues")
                continue
            par_date[ligne[0]].append((n, dict(zip(ENTETE, ligne))))

    dates = [date_cible] if date_cible else sorted(par_date)
    if date_cible and date_cible not in par_date:
        return ecarts + [f"{date_cible} : aucun classement"]

    for d in dates:
        lignes = par_date[d]
        if not RE_DATE.match(d):
            ecarts.append(f"{d} : date au mauvais format (AAAA-MM-JJ)")
        if len(lignes) != TAILLE:
            ecarts.append(f"{d} : {len(lignes)} lignes, {TAILLE} attendues (un seul classement complet par jour)")
        horos = {r["horodatage_utc"] for _, r in lignes}
        if len(horos) != 1:
            ecarts.append(f"{d} : {len(horos)} horodatages différents, un seul attendu")
        for h in horos:
            if not RE_HORO.match(h):
                ecarts.append(f"{d} : horodatage « {h} » au mauvais format (AAAA-MM-JJTHH:MM:SSZ)")
            elif not h.startswith(d):
                ecarts.append(f"{d} : horodatage « {h} » d'une autre date")
        tickers = [r["ticker"] for _, r in lignes]
        inconnus = sorted(set(tickers) - set(univers))
        manquants = sorted(set(univers) - set(tickers))
        doublons = sorted({t for t in tickers if tickers.count(t) > 1})
        if inconnus:
            ecarts.append(f"{d} : tickers hors univers {inconnus}")
        if manquants:
            ecarts.append(f"{d} : tickers manquants {manquants}")
        if doublons:
            ecarts.append(f"{d} : tickers en double {doublons}")
        rangs = []
        for n, r in lignes:
            try:
                rang = int(r["rang"])
            except ValueError:
                ecarts.append(f"ligne {n} : rang « {r['rang']} » non entier")
                continue
            rangs.append(rang)
            if rang in RANGS_AVEC_RAISON and not r["raison"].strip():
                ecarts.append(f"ligne {n} : {r['ticker']} au rang {rang} sans raison (obligatoire pour 1-5 et {TAILLE-4}-{TAILLE})")
        if sorted(rangs) != list(range(1, TAILLE + 1)):
            ecarts.append(f"{d} : les rangs ne forment pas la suite 1 à {TAILLE} sans ex æquo")
    return ecarts


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--date", help="ne valider que ce jour (AAAA-MM-JJ)")
    a = p.parse_args()
    ecarts = valider(a.date)
    if ecarts:
        print("\n".join(f"✗ {e}" for e in ecarts))
        sys.exit(1)
    print(f"✓ classement conforme ({a.date or 'toutes les dates'})")


if __name__ == "__main__":
    main()
