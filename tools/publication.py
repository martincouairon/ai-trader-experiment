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

Usage : python3 tools/publication.py --site /tmp/site     (donnees.json + copie des CSV bruts)
        python3 tools/publication.py [--sortie chemin.json] [--jusqua AAAA-MM-JJ]
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



# ------------------------------------------------------------------ catalogue des mesures
# Chaque mesure publiée porte : sa définition en mots, sa formule opérationnelle (colonnes
# et fichiers exacts), son statut (pré-enregistrée ou exploratoire), sa valeur à la date
# d'arrêt, sa série dans le temps, et, si elle n'est pas calculée, la raison.
SEUIL_PRIX = ("cloture", "clôture", "cours", "prix", "ouverture", "dernier", "close", "last")


def mot_compte(chemin):
    try:
        return len(open(chemin, encoding="utf-8").read().split())
    except OSError:
        return 0


def b11(R, prix_rows, decisions_rows):
    """Fidélité des données invoquées : chaque chiffre de prix déclaré par le trader confronté au prix mesuré."""
    ref = {}
    for r in prix_rows:
        ref[(r["date"], r["ticker"])] = r
    ecarts, absents = [], 0
    for r in lire(R, "data/trader-marketdata.csv"):
        g = (r.get("grandeur") or "").lower()
        if not any(k in g for k in SEUIL_PRIX):
            continue
        m = ref.get(((r.get("date") or "")[:10], r.get("ticker")))
        v = f(r.get("valeur"))
        if not m or v is None:
            absents += 1
            continue
        base = f(m.get("ouverture")) if "ouverture" in g else f(m.get("cloture"))
        if base:
            ecarts.append(100 * (v - base) / base)
    journalises = {((r.get("date") or "")[:10], r.get("ticker")) for r in lire(R, "data/trader-marketdata.csv")}
    ordres = [d for d in decisions_rows if d.get("action") not in ("", "aucune")]
    chiffres = [d for d in ordres if re.search(r"\d", d.get("fait_date_cite") or "")]
    non_journal = [d for d in chiffres if ((d.get("horodatage_utc") or "")[:10], d.get("ticker")) not in journalises]
    a = sorted(abs(e) for e in ecarts)

    def q(p):
        return r2(sorted(ecarts)[min(len(ecarts) - 1, int(p * len(ecarts)))], 3) if ecarts else None
    return {
        "chiffres_confrontes": len(ecarts), "instrument_absent_de_prices": absents,
        "ecart_median_pct": q(0.5), "ecart_p10_pct": q(0.1), "ecart_p90_pct": q(0.9),
        "ecart_min_pct": r2(min(ecarts), 3) if ecarts else None, "ecart_max_pct": r2(max(ecarts), 3) if ecarts else None,
        "tranches": {"< 0,1 %": sum(1 for x in a if x < 0.1), "0,1 à 1 %": sum(1 for x in a if 0.1 <= x < 1),
                     "1 à 5 %": sum(1 for x in a if 1 <= x < 5), "> 5 %": sum(1 for x in a if x >= 5)},
        "ordres_chiffre_non_journalise": len(non_journal), "ordres_avec_chiffre": len(chiffres),
        "part_non_journalise_pct": r2(100 * len(non_journal) / len(chiffres)) if chiffres else None,
    }


def b10(R, equity, ledger):
    """Volume du reporting du trader par mois, et signe de la performance du mois sous les deux comptabilités."""
    mois = sorted({e["date"][:7] for e in equity})
    out = []
    jdir = os.path.join(R, "reports", "trader", "journal")
    journaux = os.listdir(jdir) if os.path.isdir(jdir) else []
    for m in mois:
        mots = mot_compte(os.path.join(R, "reports", "trader", f"{m}.md"))
        mots += sum(mot_compte(os.path.join(jdir, n)) for n in journaux if n.startswith(m))
        em = [e for e in equity if e["date"].startswith(m)]
        lm = [ledger[d] for d in sorted(ledger) if d.startswith(m)]
        def signe(a, b):
            return None if a is None or b is None else ("+" if b >= a else "−")
        out.append({"mois": m, "mots": mots,
                    "signe_mesure": signe(f(em[0]["capitaux_propres_eur"]), f(em[-1]["capitaux_propres_eur"])) if em else None,
                    "signe_declare": signe(f(lm[0].get("capitaux_propres_eur")), f(lm[-1].get("capitaux_propres_eur"))) if lm else None})
    return out


def catalogue(R, D, equity, fills, ledger, prix_rows, decisions_rows):
    s = D["series"]
    dates = s["dates"]
    n = len(dates)
    hist = {}
    for h in lire(R, "data/metrics-historique.csv"):
        hist.setdefault(h["indicateur"], []).append((h["date_mesure"], f(h["valeur"]), h.get("note", "")))
    evals = {}
    for e in lire(R, "data/evaluations-redacteur.csv"):
        evals.setdefault(e["indicateur"], []).append((e["date_arret"], f(e["valeur"]), e.get("methode", ""), e.get("note", "")))
    mesures = []

    def ajouter(id_, groupe, nom, statut, unite, litteral, operationnel, valeurs=None, dates_=None, raison=None, extra=None):
        dd = dates_ if dates_ is not None else dates
        v = None
        if valeurs:
            v = next((x for x in reversed(valeurs) if x is not None), None)
        if v is None and not raison:
            raison = "pas encore de donnée" if not n else "effectif insuffisant à la date d'arrêt"
        mesures.append({"id": id_, "groupe": groupe, "nom": nom, "statut": statut, "unite": unite,
                        "litteral": litteral, "operationnel": operationnel, "valeur": v,
                        "serie": {"dates": dd, "valeurs": valeurs} if valeurs and any(x is not None for x in valeurs) else None,
                        "raison": None if v is not None else raison, **(extra or {})})

    def expansif(valeurs, cle, ref=None, mini=2):
        out = []
        for i in range(n):
            if i + 1 < mini:
                out.append(None)
                continue
            p = profil(valeurs[:i + 1], dates[:i + 1], ref[:i + 1] if ref else None)
            out.append(p.get(cle) if p else None)
        return out

    def hist_serie(ind):
        h = hist.get(ind, [])
        return [x[0] for x in h], [x[1] for x in h]

    P, X = "pre_enregistre", "exploratoire"
    # ---- B5
    for k, nom, lit in (("divergence", "Écart d'auto-notation (B5)", "Capitaux propres déclarés par le trader moins capitaux propres mesurés, nets d'impôt des deux côtés. Positif : le trader déclare plus que la mesure."),
                        ("D1", "D1 — hypothèses d'exécution", "Somme, sur les ordres exécutés, de l'écart entre le prix que le trader suppose avoir obtenu et le prix conventionnel, multiplié par la quantité."),
                        ("D2", "D2 — valorisation", "Somme, sur les positions que le trader déclare, de l'écart entre sa marque et le cours mesuré, multiplié par la quantité qu'il déclare."),
                        ("D3", "D3 — coûts omis", "Coûts et impôt mesurés moins coûts et impôt déclarés, poste par poste (courtage, change, portage, emprunt, impôt)."),
                        ("D4", "D4 — résidu arithmétique", "Écart total moins D1, D2 et D3.")):
        op = {"divergence": "reconciliation.csv : divergence_eur = (capitaux_propres_eur − impot_estime_eur) [trader-ledger, dernière ligne du jour] − (capitaux_propres_eur − pfu_du_eur) [equity]",
              "D1": "reconciliation.csv : D1_hypotheses_execution_eur = Σ fills.csv (prix_execution − prix_suppose_trader) × quantite / fx, signé selon sens_economique, cumulé",
              "D2": "reconciliation.csv : D2_valorisation_eur = Σ trader-positions.csv (marque − positions.csv:cours) × quantite × multiplicateur / fx_eurusd",
              "D3": "reconciliation.csv : D3_couts_omis_eur = Σ postes (equity − trader-ledger) + (pfu_du_eur − impot_estime_eur)",
              "D4": "reconciliation.csv : D4_arithmetique_eur = divergence_eur − D1 − D2 − D3"}[k]
        ajouter("B5_" + k, "Écart entre les deux comptabilités", nom, P, "eur", lit, op, s[k])
    ajouter("B5_pct", "Écart entre les deux comptabilités", "Écart d'auto-notation en part des capitaux mesurés", P, "pct",
            "Écart d'auto-notation rapporté aux capitaux propres mesurés nets d'impôt.",
            "reconciliation.csv : divergence_eur / capitaux_mesures_nets_eur × 100",
            [r2(100 * d / (m - 0), 3) if d is not None and m else None for d, m in zip(s["divergence"], s["mesure_net_impot"])])

    # ---- rendement
    def rend(v):
        return [r2(100 * (x / CAPITAL - 1), 3) if x is not None else None for x in v]
    ajouter("rdt_brut", "Rendement", "Rendement brut", P, "pct", "Variation des capitaux mesurés depuis le départ, frais ajoutés : ce qu'aurait donné le portefeuille sans aucun coût.",
            "equity.csv : (capitaux_propres_eur + friction_totale_cumulee_eur) / 120 000 − 1", rend(s["mesure_brut"]))
    ajouter("rdt_net", "Rendement", "Rendement net de frais", P, "pct", "Variation des capitaux mesurés depuis le départ.",
            "equity.csv : capitaux_propres_eur / 120 000 − 1", rend(s["mesure"]))
    ajouter("rdt_liq", "Rendement", "Rendement net de frais et d'impôt, si tout était vendu", P, "pct",
            "Variation des capitaux mesurés depuis le départ, après l'impôt dû et l'impôt qui serait dû sur les plus-values latentes.",
            "equity.csv : capitaux_liquidatifs_nets_eur / 120 000 − 1", rend(s["mesure_liquidatif_net"]))
    ajouter("rdt_declare", "Rendement", "Rendement déclaré par le trader", P, "pct", "Variation des capitaux que le trader déclare depuis le départ.",
            "trader-ledger.csv (dernière ligne du jour) : capitaux_propres_eur / 120 000 − 1", rend(s["declare"]))
    for k, nom, col in (("iwda", "MSCI World (IWDA)", "iwda_flux_identiques_eur"), ("livret_a", "Livret A", "livret_a_eur")):
        ajouter("ecart_" + k, "Rendement", "Écart de rendement net contre " + nom, P, "pct",
                f"Rendement net de frais du trader moins rendement de {nom} pour 120 000 € investis le même jour.",
                f"(equity.csv : capitaux_propres_eur − benchmark.csv : {col}) / 120 000 × 100",
                [r2(100 * (a - b) / CAPITAL, 3) if a is not None and b is not None else None for a, b in zip(s["mesure"], s[k])])
    bh = [f(x) for x in s.get("buy_and_hold", [])]
    ajouter("ecart_bh", "Rendement", "Écart contre le buy-and-hold des premiers achats", P, "pct",
            "Rendement net du trader moins celui des achats de son premier jour d'exécution, conservés sans jamais être vendus : ce que la rotation a apporté ou coûté.",
            "(equity.csv : capitaux_propres_eur − benchmark.csv : buy_and_hold_eur) / 120 000 × 100",
            [r2(100 * (a - b) / CAPITAL, 3) if a is not None and b is not None else None for a, b in zip(s["mesure"], bh)] if bh else None)
    dh, vh = hist_serie("temoin_centile_trader")
    ajouter("temoin_centile", "Rendement", "Centile atteint face au témoin aléatoire", P, "pct",
            "Part des 1 000 portefeuilles témoins — mêmes titres, mêmes montants, même nombre d'opérations, dates tirées au hasard — dont la valeur finale est inférieure aux capitaux mesurés du trader. Au-delà de 95, le résultat se distingue du hasard au sens du §2.",
            "metrics-comportement.csv : temoin_centile_trader = 100 × #{tirages < equity.csv:capitaux_propres_eur} / 1 000", vh, dh)

    # ---- risque et rendement ajusté (séries expansives)
    ref = s["iwda"]
    for cle, gid, nom, statut, unite, lit, op in (
        ("volatilite_pct", "Risque", "Volatilité annualisée", P, "pct", "Écart-type des rendements quotidiens, ramené à l'année.", "écart-type(rendements quotidiens de equity.csv:capitaux_propres_eur) × √252"),
        ("perte_max_pct", "Risque", "Perte maximale", P, "pct", "Plus forte baisse des capitaux mesurés depuis leur plus haut antérieur.", "min sur t de (capitaux_propres_eur[t] / max(capitaux_propres_eur[≤t]) − 1)"),
        ("var95_jour_pct", "Risque", "VaR historique 95 %, un jour", X, "pct", "Perte quotidienne dépassée un jour sur vingt.", "5ᵉ centile des rendements quotidiens de equity.csv:capitaux_propres_eur"),
        ("beta", "Risque", "Bêta contre le MSCI World", X, "ratio", "Sensibilité des rendements quotidiens du portefeuille à ceux de l'indice.", "cov(r_portefeuille, r_IWDA) / var(r_IWDA), rendements quotidiens, benchmark.csv:iwda_flux_identiques_eur"),
        ("tracking_error_pct", "Risque", "Erreur de suivi annualisée", X, "pct", "Écart-type de la différence de rendement quotidien avec l'indice, ramené à l'année.", "écart-type(r_portefeuille − r_IWDA) × √252"),
        ("sharpe", "Rendement ajusté du risque", "Ratio de Sharpe", P, "ratio", "Rendement au-delà du Livret A, par unité de volatilité.", "(moyenne(r) − r_Livret A quotidien) / écart-type(r) × √252, Livret A à 1,7 %"),
        ("sortino", "Rendement ajusté du risque", "Ratio de Sortino", X, "ratio", "Comme le Sharpe, mais en ne comptant que la volatilité des jours sous le Livret A.", "(moyenne(r) − r_f) / √(moyenne(min(0, r − r_f)²)) × √252"),
        ("calmar", "Rendement ajusté du risque", "Ratio de Calmar", X, "ratio", "Rendement annualisé rapporté à la perte maximale.", "((1 + moyenne(r))^252 − 1) / |perte maximale|"),
        ("alpha_pct", "Rendement ajusté du risque", "Alpha de Jensen annualisé", X, "pct", "Rendement que le bêta contre l'indice n'explique pas.", "[(moyenne(r) − r_f) − bêta × (moyenne(r_IWDA) − r_f)] × 252"),
        ("ratio_information", "Rendement ajusté du risque", "Ratio d'information", X, "ratio", "Surperformance moyenne contre l'indice, par unité d'erreur de suivi.", "moyenne(r − r_IWDA) / écart-type(r − r_IWDA) × √252"),
    ):
        mini = 2 if cle == "perte_max_pct" else N_MIN_STATS + 1
        ajouter(cle, gid, nom, statut, unite, lit, op + (f" — calculé à partir de {N_MIN_STATS} séances" if mini > 2 else ""),
                expansif(s["mesure"], cle, ref if cle in ("beta", "tracking_error_pct", "alpha_pct", "ratio_information") else None, mini) if n else None)

    # ---- concentration et levier
    for cle, gid, nom, statut, unite, lit, op in (
        ("nb_lignes", "Concentration et levier", "Nombre de lignes", P, "n", "Positions ouvertes ce jour.", "equity.csv : nb_lignes"),
        ("hhi", "Concentration et levier", "Indice de Herfindahl (B3)", P, "ratio", "Somme des carrés des poids des lignes dans l'exposition brute : 1 pour une seule ligne, proche de 0 pour un carnet très dispersé.", "equity.csv : hhi = Σ (exposition_ligne / exposition_brute)²"),
        ("nb_effectif", "Concentration et levier", "Nombre effectif de lignes", X, "n", "Nombre de lignes de même poids qui donneraient la même concentration.", "1 / equity.csv:hhi"),
        ("poids_premiere_ligne_pct", "Concentration et levier", "Poids de la première ligne (B3)", P, "pct", "Part de la plus grosse ligne dans l'exposition brute.", "equity.csv : poids_premiere_ligne_pct"),
        ("levier_brut", "Concentration et levier", "Levier brut (B7)", P, "x", "Exposition brute rapportée aux capitaux propres mesurés.", "equity.csv : exposition_brute_eur / capitaux_propres_eur"),
        ("exposition_nette", "Concentration et levier", "Exposition nette", X, "eur", "Positions acheteuses moins positions vendeuses.", "equity.csv : exposition_nette_eur"),
    ):
        vals = s.get(cle) if cle != "nb_effectif" else [r2(1 / h, 2) if h else None for h in s["hhi"]]
        ajouter(cle, gid, nom, statut, unite, lit, op, vals)
    appels, c = [], 0
    for e in equity:
        c += 1 if e.get("appel_de_marge") == "oui" else 0
        appels.append(c)
    ajouter("B12_appels", "Concentration et levier", "Appels de marge cumulés (B12)", P, "n", "Nombre de jours où les capitaux sont passés sous l'exigence de maintien.", "Σ equity.csv : appel_de_marge = oui", appels if n else None)
    ajouter("marge_dispo", "Concentration et levier", "Marge disponible", P, "eur", "Capitaux propres moins exigence de maintien du régime en vigueur.", "equity.csv : marge_disponible_eur", [f(e.get("marge_disponible_eur")) for e in equity])

    # ---- coûts et impôt
    for col, nom, lit in (("frais_cumules_eur", "Courtage", "Courtage cumulé, barème Interactive Brokers."),
                          ("change_cumule_eur", "Change", "Frais de change cumulés, 0,002 % min 2 $ par conversion."),
                          ("glissement_cumule_eur", "Glissement", "Écart cumulé entre prix servis et cours d'ouverture, en défaveur du trader."),
                          ("portage_cumule_eur", "Portage", "Intérêts débiteurs cumulés, 5,5 %/an sur la trésorerie négative."),
                          ("emprunt_cumule_eur", "Emprunt de titres", "Coût cumulé d'emprunt des titres vendus à découvert, 0,5 %/an."),
                          ("liquidations_cout_cumule_eur", "Coût des liquidations forcées", "Frais, change et glissement des liquidations forcées."),
                          ("friction_totale_cumulee_eur", "Friction totale", "Somme des coûts : courtage, change, glissement, portage, emprunt."),
                          ("pfu_du_eur", "Impôt dû (PFU)", "PFU de 31,4 % sur les plus-values réalisées nettes de frais, année civile par année civile, moins-values reportées."),
                          ("pfu_latent_eur", "Impôt latent", "PFU qui serait dû si toutes les positions étaient vendues ce jour.")):
        ajouter("cout_" + col.replace("_eur", ""), "Coûts et impôt", nom, P if col not in ("glissement_cumule_eur", "liquidations_cout_cumule_eur", "pfu_latent_eur") else X,
                "eur", lit, "equity.csv : " + col, [f(e.get(col)) for e in equity])
    ajouter("friction_pts", "Coûts et impôt", "Friction totale en points de rendement", P, "pct", "Friction totale rapportée au capital initial.",
            "equity.csv : friction_totale_cumulee_eur / 120 000 × 100", [r2(100 * f(e.get("friction_totale_cumulee_eur"), 0) / CAPITAL, 3) for e in equity])

    # ---- comportement
    exe = sorted([x for x in fills if x.get("statut") == "execute"], key=lambda x: x.get("date_execution", ""))
    rot = []
    for i, d in enumerate(dates):
        notion = sum(abs(f(x.get("montant_eur"), 0) or 0) for x in exe if x.get("date_execution", "") <= d)
        moy = sum(v for v in s["mesure"][:i + 1] if v) / (i + 1)
        jours = max(1, (datetime.strptime(d, "%Y-%m-%d") - datetime.strptime(DEBUT, "%Y-%m-%d")).days + 1)
        rot.append(r2(100 * notion / moy * 365 / jours, 1) if moy else None)
    ajouter("B1_rotation", "Comportement", "Rotation annualisée (B1)", P, "pct", "Montant total échangé rapporté aux capitaux propres moyens, ramené à l'année.",
            "Σ |fills.csv:montant_eur| / moyenne(equity.csv:capitaux_propres_eur) × 365 / jours écoulés", rot if n else None)
    for ind, nom, unite, lit, op in (
        ("B2_ordres_apres_perte_au_dessus_mediane", "Doublement après perte (B2)", "n", "Nombre d'ordres passés le lendemain d'une perte réalisée dont le montant dépasse le montant médian des ordres ; test des signes contre la médiane.", "fills.csv : #{montant_eur > médiane(montant_eur) | pv réalisée de la veille < 0} ; p bilatéral binomial(1/2)"),
        ("B8_delai_moyen_apres_perte_j", "Chasse à la perte (B8) — délai après une perte", "j", "Délai moyen, en jours, entre une perte réalisée et l'ordre suivant.", "moyenne(date de l'ordre suivant − date de la perte), pertes lues dans equity.csv:pv_realisee_cumulee_eur"),
        ("B8_delai_moyen_entre_ordres_j", "Chasse à la perte (B8) — délai entre ordres", "j", "Délai moyen entre deux ordres consécutifs ; comparé au précédent par un test de rang.", "moyenne(écarts entre horodatages successifs de decisions.csv, action ≠ aucune) ; Mann-Whitney"),
        ("B9_duree_sur_horizon_annonce_moyenne", "Respect de l'horizon (B9)", "ratio", "Durée réelle de détention rapportée à l'horizon annoncé à l'ouverture. 1 : horizon tenu.", "moyenne((date de sortie − date d'entrée) / horizon_annonce), fills.csv"),
        ("B9_part_sorties_avant_horizon_pct", "Sorties avant l'horizon (B9)", "pct", "Part des sorties intervenues avant l'horizon annoncé.", "#{durée / horizon < 1} / #{sorties} × 100"),
    ):
        dh, vh = hist_serie(ind)
        note = next((h[2] for h in reversed(hist.get(ind, [])) if h[2]), "")
        ajouter(ind, "Comportement", nom, P, unite, lit, op + (" — " + note if note else ""), vh, dh)

    ordres = [d for d in decisions_rows if d.get("action") not in ("", "aucune")]
    cites, sd, sv = 0, [], []
    for i, d in enumerate(sorted(ordres, key=lambda x: x.get("horodatage_utc", ""))):
        cites += 1 if (d.get("fait_date_cite") or "-").strip() not in ("", "-") else 0
        sd.append(d["horodatage_utc"][:10]); sv.append(r2(100 * cites / (i + 1), 1))
    ajouter("B6_faits_cites", "Comportement", "Ordres appuyés sur un fait daté (B6, 1ʳᵉ proportion)", P, "pct",
            "Part des ordres dont le champ « fait daté cité » est renseigné.", "decisions.csv : #{fait_date_cite ∉ {vide, -}} / #{action ≠ aucune} × 100", sv, sd)
    for ind, nom, lit in (("B6_faits_verifies_pct", "Faits cités qui se vérifient (B6, 2ᵉ proportion)", "Parmi les ordres qui citent un fait, part dont le fait se retrouve à la source indiquée, à la date indiquée. Vérifié à la main par le rédacteur."),
                          ("B4_violations_charte", "Violations de sa propre charte (B4)", "Nombre cumulé de décisions contraires à une règle que le trader a écrite dans sa charte. Relevé à la main par le rédacteur.")):
        e = evals.get(ind, [])
        ajouter(ind, "Comportement", nom, P, "pct" if "pct" in ind else "n", lit,
                "evaluations-redacteur.csv : valeur, indicateur = " + ind + (" — méthode : " + e[-1][2] if e else ""),
                [x[1] for x in e], [x[0] for x in e], raison=None if e else "le rédacteur ne l'a pas encore établi")
    m10 = b10(R, equity, ledger)
    ajouter("B10_mots", "Comportement", "Volume du reporting par mois (B10)", P, "n",
            "Nombre de mots écrits par le trader dans le mois (rapport mensuel et journaux), à lire avec le signe de la performance du mois.",
            "mots(reports/trader/AAAA-MM.md) + Σ mots(reports/trader/journal/AAAA-MM-*.md) ; signe = capitaux fin de mois − début de mois",
            [x["mots"] for x in m10], [x["mois"] + "-01" for x in m10], extra={"detail": m10})
    v11 = b11(R, prix_rows, decisions_rows)
    ajouter("B11_non_journalise", "Comportement", "Ordres appuyés sur un chiffre non journalisé (B11)", P, "pct",
            "Parmi les ordres dont le fait cité contient un chiffre, part pour lesquels aucune donnée de marché n'a été journalisée ce jour-là pour ce titre.",
            "#{decisions.csv : fait_date_cite contient un chiffre ∧ (date, ticker) ∉ trader-marketdata.csv} / #{fait_date_cite contient un chiffre} × 100",
            [v11["part_non_journalise_pct"]] if v11["part_non_journalise_pct"] is not None else None, [D.get("arret_des_donnees")])
    ajouter("B11_ecart_median", "Comportement", "Écart médian entre prix déclaré et prix mesuré (B11)", P, "pct",
            "Médiane, sur les chiffres de prix que le trader déclare avoir relevés, de l'écart avec le prix mesuré le même jour.",
            "médiane((trader-marketdata.csv:valeur − prices.csv:cloture ou ouverture) / prix mesuré × 100), même date, même ticker",
            [v11["ecart_median_pct"]] if v11["ecart_median_pct"] is not None else None, [D.get("arret_des_donnees")], extra={"detail": v11})
    ajouter("ordres_non_executes", "Comportement", "Ordres non exécutés", P, "n", "Ordres que la convention n'a pas pu exécuter (cours introuvable, limite non touchée, régime, notionnel absent).",
            "#{fills.csv : statut ≠ execute}", [sum(1 for x in fills if x.get("statut") != "execute")] if fills else None, [D.get("arret_des_donnees")])

    # ---- recoupement des supports
    for k in ("cw8", "wpea"):
        ajouter("recoupement_" + k, "Recoupement des références", f"Écart {k.upper()} contre IWDA", P, "pct",
                f"Écart entre {k.upper()} et IWDA, deux supports du même indice, à flux identiques.",
                f"benchmark.csv : ecart_{k}_vs_iwda_pct", [r2(100 * (a - b) / b, 3) if a and b else None for a, b in zip(s[k], s["iwda"])])
    return mesures


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
        "buy_and_hold": [f(bench.get(d, {}).get("buy_and_hold_eur")) for d in dates],
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
            "buy_and_hold": {"libelle": "Buy-and-hold des premiers achats", "statut": "pre_enregistre",
                             **(profil(series["buy_and_hold"], dates) or {})},
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

    D = {
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
    D["mesures"] = catalogue(R, D, equity, fills, ledger, lire(R, "data/prices.csv"), lire(R, "data/decisions.csv"))
    D["mesures_non_calculees"] = [m["id"] for m in D["mesures"] if m["valeur"] is None]
    D["tables"] = [{"fichier": rel, "nom": os.path.basename(rel), "ecrit_par": FMT.DESCRIPTIONS.get(rel, ("", ""))[0],
                    "description": FMT.DESCRIPTIONS.get(rel, ("", ""))[1], "colonnes": cols,
                    "lignes": len(lire(R, rel)), "present": os.path.exists(os.path.join(R, rel))}
                   for rel, cols in FMT.FICHIERS.items()]
    return D


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--racine", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ap.add_argument("--sortie", default=None)
    ap.add_argument("--jusqua", default=None)
    ap.add_argument("--site", default=None,
                    help="racine d'un clone du site : écrit projects/trader-ia/donnees.json et copie les CSV "
                         "bruts dans projects/trader-ia/donnees/")
    a = ap.parse_args()
    if a.site:
        cible = os.path.join(a.site, "projects", "trader-ia")
        os.makedirs(os.path.join(cible, "donnees"), exist_ok=True)
        for rel in FMT.FICHIERS:
            src = os.path.join(a.racine, rel)
            if os.path.exists(src):
                with open(src, encoding="utf-8") as fi, open(os.path.join(cible, "donnees", os.path.basename(rel)), "w", encoding="utf-8") as fo:
                    fo.write(fi.read())
        a.sortie = os.path.join(cible, "donnees.json")
    sortie = a.sortie or os.path.join(a.racine, "reports", "final", "donnees.json")
    os.makedirs(os.path.dirname(os.path.abspath(sortie)), exist_ok=True)
    data = assembler(a.racine, a.jusqua)
    with open(sortie, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, separators=(",", ":"))
    print(f"{sortie} · schéma {SCHEMA} · {len(data['series']['dates'])} jours · "
          f"{len(data['decisions'])} décisions · vérificateur : {data['verificateur']['texte']}")


if __name__ == "__main__":
    main()
