#!/usr/bin/env python3
"""
Publication — assemble toutes les données de l'expérience en un seul fichier JSON,
au format constant `trader-ia/1`, que la page publique lit pour tracer ses graphiques.

Le rédacteur ne recopie aucun chiffre à la main dans la page : il lance ce script,
et il écrit la prose. Le script est déterministe, il ne fait que lire et calculer.

Ce qui est pré-enregistré (§3, §4) et ce qui est exploratoire est marqué champ par
champ (`statut`). Les mesures de risque ajoutées après coup — Sortino, Calmar, bêta,
ratio d'information, VaR, comparaison aux investisseurs connus — sont exploratoires.

Entrées : tout `data/`, `reports/trader/journal/`, le verdict de runner/verifier-protocole.py
Sortie  : <site>/projects/trader-ia/donnees.json  (par défaut reports/final/donnees.json)

Usage : python3 tools/publication.py [--racine .] [--sortie chemin.json] [--jusqua AAAA-MM-JJ]
"""
import argparse, csv, json, math, os, re, subprocess, sys
from datetime import date, datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import formats as FMT  # noqa: E402

SCHEMA = "trader-ia/1"
CAPITAL = 120_000.0
DEBUT, FIN = "2026-11-24", "2027-11-24"
TAUX_SANS_RISQUE = 0.017          # Livret A, la référence sans risque du protocole
JOURS_AN = 252
N_MIN_STATS = 20                  # en dessous, une volatilité ou un ratio ne veut rien dire
TOP_LIGNES = 8
REPO = "https://github.com/martincouairon/ai-trader-experiment/blob/main/"


def f(x, default=None):
    try:
        if x is None or str(x).strip() in ("", "-", "None", "nan"):
            return default
        return float(str(x))
    except ValueError:
        return default


def lire(R, rel):
    p = os.path.join(R, rel)
    if not os.path.exists(p):
        return []
    with open(p, newline="", encoding="utf-8-sig") as fh:
        return [r for r in csv.DictReader(fh) if any((v or "").strip() for v in r.values())]


def r2(x, n=2):
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else round(x, n)


def ouvre(d):
    return datetime.strptime(d, "%Y-%m-%d").weekday() < 5


# ------------------------------------------------------------------ statistiques
def rendements(valeurs):
    out = []
    for a, b in zip(valeurs, valeurs[1:]):
        if a and b:
            out.append(b / a - 1)
    return out


def ecart_type(x):
    if len(x) < 2:
        return None
    m = sum(x) / len(x)
    return math.sqrt(sum((v - m) ** 2 for v in x) / (len(x) - 1))


def perte_max(valeurs, dates):
    pic, pic_d, pire, deb, fin = None, None, 0.0, None, None
    for v, d in zip(valeurs, dates):
        if v is None:
            continue
        if pic is None or v > pic:
            pic, pic_d = v, d
        dd = v / pic - 1
        if dd < pire:
            pire, deb, fin = dd, pic_d, d
    return pire, deb, fin


def profil(valeurs, dates, reference=None):
    """Rendement, risque et rendement ajusté du risque d'une série de valeurs liquidatives."""
    vals = [v for v in valeurs if v is not None]
    if len(vals) < 2:
        return None
    r = rendements(vals)
    n = len(r)
    total = vals[-1] / CAPITAL - 1
    jours = max(1, (datetime.strptime(dates[-1], "%Y-%m-%d") - datetime.strptime(DEBUT, "%Y-%m-%d")).days)
    annualise = (1 + total) ** (365.0 / jours) - 1 if jours >= 90 else None
    pm, pm_deb, pm_fin = perte_max(valeurs, dates)
    out = {"rendement_pct": r2(100 * total), "rendement_annualise_pct": r2(100 * annualise) if annualise is not None else None,
           "perte_max_pct": r2(100 * pm), "perte_max_du": pm_deb, "perte_max_au": pm_fin, "n": n,
           "volatilite_pct": None, "sharpe": None, "sortino": None, "calmar": None, "var95_jour_pct": None,
           "beta": None, "alpha_pct": None, "tracking_error_pct": None, "ratio_information": None,
           "jours_positifs_pct": r2(100 * sum(1 for x in r if x > 0) / n) if n else None}
    if n < N_MIN_STATS:
        return out
    rf_j = (1 + TAUX_SANS_RISQUE) ** (1 / JOURS_AN) - 1
    sd = ecart_type(r)
    moy = sum(r) / n
    vol = sd * math.sqrt(JOURS_AN)
    out["volatilite_pct"] = r2(100 * vol)
    out["sharpe"] = r2((moy - rf_j) / sd * math.sqrt(JOURS_AN)) if sd else None
    neg = [min(0.0, x - rf_j) for x in r]
    dsd = math.sqrt(sum(x * x for x in neg) / n)
    out["sortino"] = r2((moy - rf_j) / dsd * math.sqrt(JOURS_AN)) if dsd else None
    ann = (1 + moy) ** JOURS_AN - 1
    out["calmar"] = r2(ann / abs(pm)) if pm else None
    tri = sorted(r)
    out["var95_jour_pct"] = r2(100 * tri[max(0, int(0.05 * n) - 1)])
    if reference:
        ref = [v for v in reference if v is not None]
        rr = rendements(ref)
        k = min(len(rr), n)
        if k >= N_MIN_STATS:
            a, b = r[-k:], rr[-k:]
            ma, mb = sum(a) / k, sum(b) / k
            cov = sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (k - 1)
            vb = ecart_type(b) ** 2
            if vb:
                beta = cov / vb
                out["beta"] = r2(beta)
                out["alpha_pct"] = r2(100 * ((ma - rf_j) - beta * (mb - rf_j)) * JOURS_AN)
            diff = [x - y for x, y in zip(a, b)]
            te = ecart_type(diff)
            if te:
                out["tracking_error_pct"] = r2(100 * te * math.sqrt(JOURS_AN))
                out["ratio_information"] = r2(sum(diff) / k / te * math.sqrt(JOURS_AN))
    return out


# ------------------------------------------------------------------ verdict du vérificateur
def verdict(R):
    try:
        res = subprocess.run([sys.executable, os.path.join(R, "runner", "verifier-protocole.py"), "--racine", R],
                             capture_output=True, text=True, timeout=120)
    except Exception as e:  # noqa: BLE001
        return {"ok": None, "texte": f"vérificateur non exécuté : {e}", "controles": []}
    controles = []
    for l in res.stdout.splitlines():
        m = re.match(r"^\s+(✅|❌|·)\s+(\d+) · ([^—]+?)(?: — (.*))?$", l)
        if m:
            controles.append({"id": int(m.group(2)), "titre": m.group(3).strip(),
                              "etat": {"✅": "ok", "❌": "echec", "·": "na"}[m.group(1)],
                              "detail": (m.group(4) or "").strip()})
    v = next((l for l in res.stdout.splitlines() if l.startswith("VERDICT")), "")
    return {"ok": res.returncode == 0, "texte": v.replace("VERDICT : ", ""), "controles": controles}


# ------------------------------------------------------------------ décisions
def fenetre(horodatage):
    try:
        h = datetime.strptime(horodatage, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return None
    minutes = h.hour * 60 + h.minute
    for nom, debut in (("1908", 19 * 60 + 8), ("1608", 16 * 60 + 8), ("1308", 13 * 60 + 8)):
        if minutes >= debut:
            return nom
    return "1308"


def decisions(R, fills):
    par_id = {x["id_decision"]: x for x in fills}
    journaux = set()
    jdir = os.path.join(R, "reports", "trader", "journal")
    if os.path.isdir(jdir):
        journaux = {n for n in os.listdir(jdir) if n.endswith(".md")}
    out = []
    for r in lire(R, "data/decisions.csv"):
        h = r.get("horodatage_utc", "")
        fen = fenetre(h)
        nom_j = f"{h[:10]}-{fen}.md" if fen else None
        x = par_id.get(r.get("id_decision"))
        exe = None
        if x:
            exe = {"statut": x.get("statut"), "date": x.get("date_execution") or None,
                   "prix": f(x.get("prix_execution")), "montant_eur": f(x.get("montant_eur")),
                   "couts_eur": r2((f(x.get("cout_total_eur"), 0) or 0) + (f(x.get("glissement_eur"), 0) or 0)),
                   "ecart_prix_suppose_pct": f(x.get("ecart_prix_suppose_pct")), "motif": x.get("motif") or ""}
        out.append({
            "id": r.get("id_decision"), "horodatage": h, "date": h[:10], "fenetre": fen,
            "action": r.get("action"), "instrument": r.get("instrument") or None, "ticker": r.get("ticker") or None,
            "place": r.get("place") or None, "devise": r.get("devise") or None, "sens": r.get("sens") or None,
            "quantite": f(r.get("quantite")), "type_ordre": r.get("type_ordre") or None, "limite": f(r.get("limite")),
            "horizon_j": f(r.get("horizon_annonce")), "prix_suppose": f(r.get("prix_suppose")),
            "strategie": r.get("strategie") or None, "raison": r.get("raison_courte") or "",
            "fait": r.get("fait_date_cite") or "", "source": r.get("source") or "",
            "journal": (REPO + "reports/trader/journal/" + nom_j) if nom_j in journaux else None,
            "execution": exe,
        })
    return out


# ------------------------------------------------------------------ composition
def composition(positions, dates):
    if not positions:
        return None
    par_date = {}
    for p in positions:
        par_date.setdefault(p["date"], []).append(p)
    expo_max = {}
    for p in positions:
        tk = p["ticker"]
        expo_max[tk] = max(expo_max.get(tk, 0.0), f(p.get("poids_pct"), 0) or 0)
    top = [tk for tk, _ in sorted(expo_max.items(), key=lambda kv: -kv[1])[:TOP_LIGNES]]

    def serie(cle_fn):
        cles, table = [], {}
        for d in dates:
            for p in par_date.get(d, []):
                k = cle_fn(p)
                if k not in table:
                    table[k] = [0.0] * len(dates)
                    cles.append(k)
        for i, d in enumerate(dates):
            for p in par_date.get(d, []):
                table[cle_fn(p)][i] += f(p.get("exposition_eur"), 0) or 0
        return [{"cle": k, "valeurs": [r2(v) for v in table[k]]} for k in cles]

    return {
        "lignes": serie(lambda p: p["ticker"] if p["ticker"] in top else "autres"),
        "instruments": serie(lambda p: p.get("instrument") or "inconnu"),
        "strategies": serie(lambda p: p.get("strategie") or "non déclarée"),
        "sens": serie(lambda p: p.get("sens") or "long"),
        "devises": serie(lambda p: p.get("devise") or "EUR"),
        "dernier_jour": [{"ticker": p["ticker"], "instrument": p.get("instrument"), "sens": p.get("sens"),
                          "strategie": p.get("strategie") or None, "valeur_eur": f(p.get("valeur_eur")),
                          "poids_pct": f(p.get("poids_pct")), "pv_latente_eur": f(p.get("pv_latente_eur"))}
                         for p in sorted(par_date.get(dates[-1], []), key=lambda q: -(f(q.get("poids_pct"), 0) or 0))]
        if dates else [],
    }


# ------------------------------------------------------------------ assemblage
def assembler(R, jusqua=None):
    equity = [e for e in lire(R, "data/equity.csv") if ouvre(e["date"]) and (not jusqua or e["date"] <= jusqua)]
    bench = {b["date"]: b for b in lire(R, "data/benchmark.csv")}
    ledger = {}
    for l in lire(R, "data/trader-ledger.csv"):
        ledger[l["date"]] = l                      # la dernière ligne d'une date fait foi
    recon = {r["date"]: r for r in lire(R, "data/reconciliation.csv")}
    fills = lire(R, "data/fills.csv")
    positions = [p for p in lire(R, "data/positions.csv") if ouvre(p["date"])]
    inv_rows = lire(R, "data/benchmark-investisseurs.csv")
    metrics = lire(R, "data/metrics-comportement.csv")

    dates = [e["date"] for e in equity]
    col = lambda rows, k: [f(r.get(k)) for r in rows]  # noqa: E731
    mesure = col(equity, "capitaux_propres_eur")
    friction = col(equity, "friction_totale_cumulee_eur")
    brut = [r2(m + (fr or 0)) if m is not None else None for m, fr in zip(mesure, friction)]
    declare = [f(ledger.get(d, {}).get("capitaux_propres_eur")) for d in dates]
    declare_net = [(v - (f(ledger[d].get("impot_estime_eur"), 0) or 0)) if v is not None else None
                   for v, d in zip(declare, dates)]
    iwda = [f(bench.get(d, {}).get("iwda_flux_identiques_eur")) for d in dates]

    investisseurs = {}
    for r in inv_rows:
        investisseurs.setdefault(r["ticker"], {"nom": r["investisseur"], "vehicule": r["vehicule"],
                                               "qualite": r["qualite"], "par_date": {}})
        investisseurs[r["ticker"]]["par_date"][r["date"]] = f(r["valeur_flux_identiques_eur"])
    inv_series = {tk: {"nom": v["nom"], "vehicule": v["vehicule"], "qualite": v["qualite"],
                       "valeurs": [v["par_date"].get(d) for d in dates]} for tk, v in investisseurs.items()}

    series = {
        "dates": dates,
        "mesure": mesure,
        "mesure_brut": brut,
        "mesure_net_impot": col(equity, "capitaux_propres_net_pfu_eur"),
        "mesure_liquidatif_net": col(equity, "capitaux_liquidatifs_nets_eur"),
        "declare": declare,
        "declare_net_impot": [r2(v) for v in declare_net],
        "divergence": [f(recon.get(d, {}).get("divergence_eur")) for d in dates],
        "D1": [f(recon.get(d, {}).get("D1_hypotheses_execution_eur")) for d in dates],
        "D2": [f(recon.get(d, {}).get("D2_valorisation_eur")) for d in dates],
        "D3": [f(recon.get(d, {}).get("D3_couts_omis_eur")) for d in dates],
        "D4": [f(recon.get(d, {}).get("D4_arithmetique_eur")) for d in dates],
        "iwda": iwda,
        "iwda_liquidatif_net": [f(bench.get(d, {}).get("iwda_liquidatif_net_eur")) for d in dates],
        "cw8": [f(bench.get(d, {}).get("cw8_flux_identiques_eur")) for d in dates],
        "wpea": [f(bench.get(d, {}).get("wpea_flux_identiques_eur")) for d in dates],
        "livret_a": [f(bench.get(d, {}).get("livret_a_eur")) for d in dates],
        "investisseurs": inv_series,
        "levier_brut": col(equity, "levier_brut"),
        "hhi": col(equity, "hhi"),
        "poids_premiere_ligne_pct": col(equity, "poids_premiere_ligne_pct"),
        "nb_lignes": col(equity, "nb_lignes"),
        "exposition_brute": col(equity, "exposition_brute_eur"),
        "exposition_nette": col(equity, "exposition_nette_eur"),
    }

    # ---- profils de performance, côte à côte
    profils = {}
    if dates:
        profils = {
            "mesure_brut": {"libelle": "Trader — mesuré, avant frais et impôt", "statut": "pre_enregistre",
                            **(profil(brut, dates, iwda) or {})},
            "mesure": {"libelle": "Trader — mesuré, net de frais", "statut": "pre_enregistre",
                       **(profil(mesure, dates, iwda) or {})},
            "mesure_liquidatif_net": {"libelle": "Trader — mesuré, net de frais et d'impôt (si tout était vendu)",
                                      "statut": "pre_enregistre",
                                      **(profil(series["mesure_liquidatif_net"], dates, iwda) or {})},
            "declare": {"libelle": "Trader — déclaré par le trader", "statut": "piece",
                        **(profil(declare, dates, iwda) or {})},
            "iwda": {"libelle": "MSCI World (IWDA)", "statut": "pre_enregistre", **(profil(iwda, dates) or {})},
            "iwda_liquidatif_net": {"libelle": "MSCI World (IWDA), net d'impôt si vendu", "statut": "pre_enregistre",
                                    **(profil(series["iwda_liquidatif_net"], dates) or {})},
            "livret_a": {"libelle": "Livret A", "statut": "pre_enregistre",
                         **(profil(series["livret_a"], dates) or {})},
        }
        for tk, v in inv_series.items():
            p = profil(v["valeurs"], dates, iwda)
            if p:
                profils["inv_" + tk] = {"libelle": f"{v['nom']} — {v['vehicule']}", "statut": "exploratoire", **p}

    # ---- coûts et impôt, par poste, en euros et en points de rendement
    couts = None
    if equity:
        e = equity[-1]
        l = ledger.get(e["date"], {})
        postes = [("courtage", "frais_cumules_eur", "frais_cumules_eur"),
                  ("change", "change_cumule_eur", "change_cumule_eur"),
                  ("glissement", "glissement_cumule_eur", None),
                  ("portage", "portage_cumule_eur", "portage_cumule_eur"),
                  ("emprunt de titres", "emprunt_cumule_eur", "emprunt_cumule_eur"),
                  ("impôt dû (PFU)", "pfu_du_eur", "impot_estime_eur"),
                  ("impôt latent (PFU si tout était vendu)", "pfu_latent_eur", None)]
        couts = {"date": e["date"],
                 "dont_liquidations_forcees_eur": f(e.get("liquidations_cout_cumule_eur")),
                 "postes": [{"poste": nom, "mesure_eur": f(e.get(cm)), "declare_eur": f(l.get(ct)) if ct else None,
                             "points_de_rendement": r2(100 * (f(e.get(cm), 0) or 0) / CAPITAL, 3)}
                            for nom, cm, ct in postes]}
        # l'impôt latent n'est pas un coût subi : il est publié, jamais additionné au total
        couts["total_mesure_eur"] = r2(sum(p["mesure_eur"] or 0 for p in couts["postes"] if "latent" not in p["poste"]))
        couts["total_points"] = r2(100 * couts["total_mesure_eur"] / CAPITAL, 3)

    # ---- activité
    exe = [x for x in fills if x.get("statut") == "execute"]
    dec = decisions(R, fills)
    actifs = [d for d in dec if d["action"] != "aucune"]
    activite = {
        "fenetres_avec_decision": len({(d["date"], d["fenetre"]) for d in dec}),
        "decisions": len(dec), "ordres": len(actifs), "fenetres_sans_ordre": len([d for d in dec if d["action"] == "aucune"]),
        "ordres_executes": len(exe), "ordres_non_executes": len([x for x in fills if x.get("statut") != "execute"]),
        "notionnel_echange_eur": r2(sum(abs(f(x.get("montant_eur"), 0) or 0) for x in exe)),
        "faits_cites_pct": r2(100 * len([d for d in actifs if d["fait"] and d["fait"] != "-"]) / len(actifs)) if actifs else None,
        "strategies_declarees": {s: len([d for d in actifs if d["strategie"] == s]) for s in
                                 sorted({d["strategie"] for d in actifs if d["strategie"]})},
    }

    derniere = equity[-1] if equity else {}
    concentration = {
        "nb_lignes": f(derniere.get("nb_lignes")), "hhi": f(derniere.get("hhi")),
        "nb_effectif_lignes": r2(1 / f(derniere.get("hhi"))) if f(derniere.get("hhi")) else None,
        "poids_premiere_ligne_pct": f(derniere.get("poids_premiere_ligne_pct")),
        "levier_brut": f(derniere.get("levier_brut")),
        "levier_brut_max": max((v for v in series["levier_brut"] if v is not None), default=None),
        "exposition_nette_eur": f(derniere.get("exposition_nette_eur")),
        "appels_de_marge": sum(1 for e in equity if e.get("appel_de_marge") == "oui"),
        "regime_marge": derniere.get("regime_marge"),
    }

    rec_fin = recon.get(dates[-1]) if dates else None
    divergence = None
    if rec_fin:
        divergence = {k: f(rec_fin.get(k)) for k in FMT.RECONCILIATION if k not in ("date", "D3_detail", "D2_methode", "depasse_25_pct")}
        divergence["date"] = rec_fin["date"]
        divergence["D2_methode"] = rec_fin.get("D2_methode")
        divergence["D3_detail"] = dict(kv.split("=") for kv in (rec_fin.get("D3_detail") or "").split(";") if "=" in kv)
        divergence["jours_garde_fou_25"] = [r["date"] for r in recon.values() if r.get("depasse_25_pct") == "oui"]

    return {
        "schema": SCHEMA, "formats": FMT.VERSION,
        "genere_le": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "arret_des_donnees": dates[-1] if dates else None,
        "debut": DEBUT, "fin_engagee": FIN, "capital_initial_eur": CAPITAL,
        "verificateur": verdict(R),
        "series": series,
        "profils": profils,
        "couts": couts,
        "concentration": concentration,
        "activite": activite,
        "divergence": divergence,
        "comportement": [{"indicateur": m["indicateur"], "valeur": m["valeur"], "n": m["n"], "note": m["note"]}
                         for m in metrics],
        "composition": composition(positions, dates),
        "strategies": FMT.STRATEGIES,
        "decisions": dec,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--racine", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ap.add_argument("--sortie", default=None)
    ap.add_argument("--jusqua", default=None)
    a = ap.parse_args()
    sortie = a.sortie or os.path.join(a.racine, "reports", "final", "donnees.json")
    os.makedirs(os.path.dirname(os.path.abspath(sortie)), exist_ok=True)
    data = assembler(a.racine, a.jusqua)
    with open(sortie, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, separators=(",", ":"))
    print(f"{sortie} · schéma {SCHEMA} · {len(data['series']['dates'])} jours · "
          f"{len(data['decisions'])} décisions · vérificateur : {data['verificateur']['texte']}")


if __name__ == "__main__":
    main()
