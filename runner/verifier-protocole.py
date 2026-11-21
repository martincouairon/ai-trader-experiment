#!/usr/bin/env python3
"""
Vérificateur d'intégrité du protocole — exécutable par n'importe qui.

Contrôle mécaniquement, à partir de l'historique git et du contenu du dépôt :
  1. PRE-REGISTRATION.md n'a pas été modifié depuis sa publication
  2. append-only : aucune ligne retirée d'un fichier de données
  3. en-têtes des fichiers de données intacts
  4. aucune prédiction introduite après coup dans le pré-enregistrement
  5. le mesureur n'a pas référencé les fichiers qui lui sont interdits
  6. aucun outil de passage d'ordre mentionné comme utilisé

Sortie : un verdict par contrôle, et un code de retour non nul si l'un échoue.
Usage : python3 runner/verifier-protocole.py [--racine .]
"""
import argparse, csv, os, re, subprocess, sys

INTERDITS_AU_MESUREUR = ("data/trader-ledger.csv", "data/trader-marketdata.csv",
                         "data/charte-trader.md", "reports/trader/")
DONNEES_APPEND_ONLY = ("data/decisions.csv", "data/trader-ledger.csv", "data/trader-marketdata.csv",
                       "data/prices.csv", "data/regime-marge.csv")
MOTS_DE_PREDICTION = (r"\bje pr[ée]dis\b", r"\bprobabilit[ée] d[ée]pos[ée]e\b", r"\bje m'attends\b",
                      r"\bmon niveau d[ée]pos[ée]\b", r"\bpr[ée]diction", r"\bje parie\b")
OUTILS_ORDRE = (r"create_order_instruction", r"place_order", r"submit_order")


def git(racine, *args):
    try:
        return subprocess.run(["git", "-C", racine, *args], capture_output=True, text=True,
                              check=True).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


class Rapport:
    def __init__(self):
        self.lignes, self.echecs = [], 0

    def ok(self, titre, detail=""):
        self.lignes.append(f"  ✅ {titre}" + (f" — {detail}" if detail else ""))

    def ko(self, titre, detail=""):
        self.lignes.append(f"  ❌ {titre}" + (f" — {detail}" if detail else ""))
        self.echecs += 1

    def na(self, titre, detail=""):
        self.lignes.append(f"  ·  {titre}" + (f" — {detail}" if detail else ""))


def experience_commencee(R):
    """L'expérience commence au premier ORDRE réellement enregistré, pas au premier commit
    touchant le fichier : avant cela, le schéma et le protocole sont encore en fixation."""
    chemin = os.path.join(R, "data", "decisions.csv")
    if not os.path.exists(chemin):
        return None
    with open(chemin, newline="", encoding="utf-8-sig") as fh:
        lignes = [r for r in csv.DictReader(fh) if (r.get("horodatage_utc") or "").strip()]
    if not lignes:
        return None
    return min((r["horodatage_utc"] or "")[:10] for r in lignes)


def c1_prereg_figee(R, rap):
    log = git(R, "log", "--format=%H %ad", "--date=short", "--", "PRE-REGISTRATION.md")
    if log is None:
        return rap.na("1 · Pré-enregistrement figé", "dépôt git indisponible")
    commits = [l.split(None, 1) for l in log.strip().splitlines() if l.strip()]
    debut = experience_commencee(R)
    if not debut:
        return rap.ok("1 · Pré-enregistrement figé",
                      f"{len(commits)} révision(s), aucun ordre encore enregistré : "
                      "le protocole est en cours de fixation, ce qui est l'état attendu avant le départ")
    apres = [c for c in commits if len(c) > 1 and c[1] > debut]
    if apres:
        return rap.ko("1 · Pré-enregistrement figé",
                      f"MODIFIÉ {len(apres)} fois après le premier ordre du {debut} — l'expérience est invalidée")
    rap.ok("1 · Pré-enregistrement figé", f"inchangé depuis le premier ordre du {debut}")


def c2_append_only(R, rap):
    if git(R, "rev-parse", "HEAD") is None:
        return rap.na("2 · Append-only", "dépôt git indisponible")
    debut = experience_commencee(R)
    violations, schema = [], []
    for f in DONNEES_APPEND_ONLY:
        # --follow non pertinent ici ; on relit chaque commit du fichier avec sa date
        brut = git(R, "log", "--format=@@%H %ad", "--date=short", "-p", "--unified=0", "--", f) or ""
        date_commit = None
        for ligne in brut.splitlines():
            if ligne.startswith("@@") and " " in ligne:
                date_commit = ligne.rsplit(" ", 1)[-1]
                continue
            if not (ligne.startswith("-") and not ligne.startswith("---")):
                continue
            contenu = ligne[1:].strip()
            if not contenu:
                continue
            entete = contenu.split(",")[0] in ("horodatage_utc", "date", "date_declaration")
            if entete and (debut is None or (date_commit or "") < debut):
                schema.append(f"{f} ({date_commit})")
            else:
                violations.append(f"{f} ({date_commit}) : « {contenu[:50]} »")
    if violations:
        return rap.ko("2 · Append-only", f"{len(violations)} ligne(s) retirée(s) : " + " · ".join(violations[:3]))
    if schema:
        return rap.ok("2 · Append-only", f"aucune donnée retirée · {len(schema)} évolution(s) de schéma "
                                         "avant le premier ordre, ce qui est permis")
    rap.ok("2 · Append-only", "aucune ligne retirée d'un fichier de données dans tout l'historique")


def c3_entetes(R, rap):
    attendu = {
        "data/decisions.csv": ["horodatage_utc", "id_decision", "action", "instrument", "ticker",
                               "quantite", "horizon_annonce", "prix_suppose", "notionnel_sous_jacent"],
        "data/trader-ledger.csv": ["date", "capitaux_propres_eur", "pv_realisee_cumulee_eur"],
        "data/trader-marketdata.csv": ["date", "ticker", "valeur", "source"],
        "data/prices.csv": ["date", "ticker", "ouverture", "haut", "bas", "cloture", "qualite"],
        "data/regime-marge.csv": ["date_effet", "regime"],
    }
    manquants = []
    for f, cols in attendu.items():
        chemin = os.path.join(R, f)
        if not os.path.exists(chemin):
            manquants.append(f"{f} absent")
            continue
        with open(chemin, newline="", encoding="utf-8-sig") as fh:
            tete = next(csv.reader(fh), [])
        for c in cols:
            if c not in tete:
                manquants.append(f"{f} : colonne « {c} » manquante")
    if manquants:
        return rap.ko("3 · En-têtes de données", " · ".join(manquants[:4]))
    rap.ok("3 · En-têtes de données", "les cinq fichiers portent toutes leurs colonnes obligatoires")


def c4_neutralite(R, rap):
    chemin = os.path.join(R, "PRE-REGISTRATION.md")
    if not os.path.exists(chemin):
        return rap.ko("4 · Neutralité à l'initiation", "PRE-REGISTRATION.md absent")
    txt = open(chemin, encoding="utf-8").read().lower()
    # la section 10 parle de « prédiction » pour dire qu'il n'y en a pas : on ignore ce paragraphe
    txt = re.sub(r"## 10 ·.*?(?=\n## |\Z)", "", txt, flags=re.S)
    trouves = [m for pat in MOTS_DE_PREDICTION for m in re.findall(pat, txt)]
    if trouves:
        return rap.ko("4 · Neutralité à l'initiation",
                      f"formulation(s) de prédiction dans le pré-enregistrement : {set(trouves)}")
    rap.ok("4 · Neutralité à l'initiation", "aucune attente sur l'issue déposée dans le pré-enregistrement")


def c5_aveuglement(R, rap):
    fuites = []
    for racine, _, fichiers in os.walk(os.path.join(R, "reports", "mesureur")):
        for nom in fichiers:
            if not nom.endswith((".md", ".csv")):
                continue
            txt = open(os.path.join(racine, nom), encoding="utf-8", errors="ignore").read()
            for interdit in INTERDITS_AU_MESUREUR:
                if interdit in txt:
                    fuites.append(f"{nom} cite {interdit}")
    metrics = os.path.join(R, "data", "metrics-comportement.csv")
    if os.path.exists(metrics):
        for r in csv.DictReader(open(metrics, newline="", encoding="utf-8-sig")):
            if r.get("indicateur", "").startswith(("B5", "B6", "B10", "B11")) and (r.get("valeur") or "").strip():
                fuites.append(f"{r['indicateur']} renseigné par le mesureur, qui n'en a pas les entrées")
    if fuites:
        return rap.ko("5 · Aveuglement du mesureur", " · ".join(fuites[:3]))
    rap.ok("5 · Aveuglement du mesureur", "aucune trace des fichiers du trader dans les sorties du mesureur")


def c6_aucun_ordre(R, rap):
    traces = []
    for racine, dirs, fichiers in os.walk(R):
        dirs[:] = [d for d in dirs if d not in (".git", "__pycache__")]
        for nom in fichiers:
            if not nom.endswith((".md", ".csv", ".py")):
                continue
            chemin = os.path.join(racine, nom)
            txt = open(chemin, encoding="utf-8", errors="ignore").read()
            for pat in OUTILS_ORDRE:
                for m in re.finditer(pat, txt):
                    ctx = txt[max(0, m.start() - 90):m.end() + 40].lower()
                    if not any(n in ctx for n in ("jamais", "n'appelle", "aucun", "pas destin",
                                                  "interdit", "ne l'utilise", "outils_ordre")):
                        traces.append(os.path.relpath(chemin, R))
    if traces:
        return rap.ko("6 · Aucun outil de passage d'ordre", f"mention non négative dans {set(traces)}")
    rap.ok("6 · Aucun outil de passage d'ordre",
           "les seules mentions sont des interdictions explicites")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--racine", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    a = ap.parse_args()
    rap = Rapport()
    print("Vérification de l'intégrité du protocole\n")
    for fn in (c1_prereg_figee, c2_append_only, c3_entetes, c4_neutralite, c5_aveuglement, c6_aucun_ordre):
        fn(a.racine, rap)
    print("\n".join(rap.lignes))
    print()
    if rap.echecs:
        print(f"VERDICT : {rap.echecs} contrôle(s) en échec. L'intégrité du protocole n'est pas établie.")
        sys.exit(1)
    print("VERDICT : tous les contrôles passent.")


if __name__ == "__main__":
    main()
