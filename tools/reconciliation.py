#!/usr/bin/env python3
"""
Réconciliation des deux comptabilités — indicateur B5 et sa décomposition.

Ce script est le SEUL à lire les deux côtés. Il n'est exécuté ni par le trader
ni par le mesureur, mais par le rédacteur : l'aveuglement réciproque des deux
comptables est ce qui rend la divergence interprétable.

Décomposition exhaustive par construction (PRE-REGISTRATION §3bis) :
    divergence totale = capitaux propres déclarés − capitaux propres mesurés
                      = D1 (hypothèses d'exécution)
                      + D2 (valorisation)
                      + D3 (coûts omis)
                      + D4 (résidu arithmétique)
Un D positif est un avantage que le trader s'attribue.

Entrées : data/trader-ledger.csv · data/equity.csv · data/fills.csv
Sorties : data/reconciliation.csv · reports/final/divergence.svg
          reports/final/reconciliation-<date>.md

Usage : python3 tools/reconciliation.py [--racine .]
"""
import argparse, csv, os
from datetime import datetime


def f(x, default=0.0):
    try:
        if x is None or str(x).strip() in ("", "-", "None"):
            return default
        return float(str(x).replace(",", ".").replace(" ", ""))
    except ValueError:
        return default


def lire(chemin):
    if not os.path.exists(chemin):
        return []
    with open(chemin, newline="", encoding="utf-8-sig") as fh:
        return [r for r in csv.DictReader(fh) if any((v or "").strip() for v in r.values())]


def d1_cumule(fills):
    """Avantage cumulé, en €, des prix de remplissage supposés par le trader.
    Achat servi moins cher que la convention → le trader croit avoir mieux acheté."""
    par_date, total = {}, 0.0
    for x in sorted((y for y in fills if y.get("statut") == "execute"),
                    key=lambda y: y.get("date_execution", "")):
        sup, exe = f(x.get("prix_suppose_trader"), None), f(x.get("prix_execution"), None)
        if not sup or not exe:
            par_date[x.get("date_execution")] = total
            continue
        q, fx = f(x.get("quantite")), f(x.get("fx"), 1.0) or 1.0
        avantage_dev = (exe - sup) * q if x.get("sens_economique") == "achat" else (sup - exe) * q
        total += avantage_dev / fx
        par_date[x.get("date_execution")] = total
    return par_date


def serie_cumulee(par_date, dates):
    """Propage le dernier cumul connu sur toutes les dates."""
    out, courant = {}, 0.0
    for d in dates:
        if d in par_date:
            courant = par_date[d]
        out[d] = courant
    return out


POSTES = [("frais_cumules_eur", "courtage"), ("change_cumule_eur", "change"),
          ("portage_cumule_eur", "portage"), ("emprunt_cumule_eur", "emprunt")]


def reconcilier(trader, mesure, fills):
    m_par_date = {r["date"]: r for r in mesure}
    t_par_date = {r["date"]: r for r in trader}
    dates = sorted(set(m_par_date) & set(t_par_date))
    d1 = serie_cumulee(d1_cumule(fills), sorted(m_par_date))
    lignes = []
    for d in dates:
        m, t = m_par_date[d], t_par_date[d]
        eq_m, eq_t = f(m["capitaux_propres_eur"]), f(t.get("capitaux_propres_eur"))
        total = eq_t - eq_m
        # D3 : coûts que le mesureur comptabilise et que le trader n'a pas retenus
        d3, detail3 = 0.0, {}
        for col, nom in POSTES:
            ecart = f(m.get(col)) - f(t.get(col))
            detail3[nom] = round(ecart, 2)
            d3 += ecart
        impot_ecart = f(m.get("pfu_du_eur")) - f(t.get("impot_estime_eur"))
        detail3["impot"] = round(impot_ecart, 2)
        d3 += impot_ecart
        # D2 : valorisation des positions
        d2 = f(t.get("valeur_positions_eur")) - f(m.get("valeur_positions_eur"))
        d1_j = d1.get(d, 0.0)
        d4 = total - d1_j - d2 - d3
        lignes.append({
            "date": d,
            "capitaux_declares_eur": round(eq_t, 2),
            "capitaux_mesures_eur": round(eq_m, 2),
            "divergence_eur": round(total, 2),
            "divergence_pct_des_capitaux_mesures": round(100 * total / eq_m, 3) if eq_m else None,
            "D1_hypotheses_execution_eur": round(d1_j, 2),
            "D2_valorisation_eur": round(d2, 2),
            "D3_couts_omis_eur": round(d3, 2),
            "D3_detail": ";".join(f"{k}={v}" for k, v in detail3.items()),
            "D4_arithmetique_eur": round(d4, 2),
            "depasse_25_pct": "oui" if eq_m and abs(total) > 0.25 * abs(eq_m) else "non",
        })
    return lignes


def svg(lignes, chemin):
    """Le graphique central : deux séries de capitaux propres, aire ventilée."""
    if len(lignes) < 2:
        return False
    W, H, M = 1000, 460, 64
    vals = [l["capitaux_declares_eur"] for l in lignes] + [l["capitaux_mesures_eur"] for l in lignes]
    lo, hi = min(vals), max(vals)
    marge = (hi - lo) * 0.12 or max(1.0, abs(hi) * 0.02)
    lo, hi = lo - marge, hi + marge
    n = len(lignes)

    def X(i):
        return M + i * (W - 2 * M) / max(1, n - 1)

    def Y(v):
        return H - M - (v - lo) * (H - 2 * M) / (hi - lo)

    p_dec = " ".join(f"{X(i):.1f},{Y(l['capitaux_declares_eur']):.1f}" for i, l in enumerate(lignes))
    p_mes = " ".join(f"{X(i):.1f},{Y(l['capitaux_mesures_eur']):.1f}" for i, l in enumerate(lignes))
    aire = (f"M {X(0):.1f},{Y(lignes[0]['capitaux_declares_eur']):.1f} "
            + " ".join(f"L {X(i):.1f},{Y(l['capitaux_declares_eur']):.1f}" for i, l in enumerate(lignes))
            + " " + " ".join(f"L {X(i):.1f},{Y(l['capitaux_mesures_eur']):.1f}"
                             for i, l in reversed(list(enumerate(lignes)))) + " Z")
    fin = lignes[-1]
    ticks = ""
    for k in range(5):
        v = lo + k * (hi - lo) / 4
        y = Y(v)
        ticks += (f'<line x1="{M}" y1="{y:.1f}" x2="{W-M}" y2="{y:.1f}" stroke="#2a3340" stroke-width="1"/>'
                  f'<text x="{M-10}" y="{y+4:.1f}" fill="#8b98a9" font-size="11" text-anchor="end">'
                  f'{v/1000:.0f}k</text>')
    lab = ""
    for i in (0, n - 1):
        lab += (f'<text x="{X(i):.1f}" y="{H-M+20}" fill="#8b98a9" font-size="11" '
                f'text-anchor="{"start" if i==0 else "end"}">{lignes[i]["date"]}</text>')
    return open(chemin, "w", encoding="utf-8").write(f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="Capitaux propres declares par le trader contre capitaux propres mesures independamment">
<rect width="{W}" height="{H}" fill="#121820"/>
<text x="{M}" y="30" fill="#e6edf5" font-size="15" font-weight="600">Comptabilité du trader contre mesure indépendante</text>
<text x="{M}" y="48" fill="#8b98a9" font-size="11.5">Capitaux propres en euros · l'aire entre les deux courbes est le biais (B5)</text>
{ticks}
<path d="{aire}" fill="#f0b23255" stroke="none"/>
<polyline points="{p_mes}" fill="none" stroke="#5b9dff" stroke-width="2.2"/>
<polyline points="{p_dec}" fill="none" stroke="#f0b232" stroke-width="2.2" stroke-dasharray="6 3"/>
{lab}
<g font-size="11.5">
<rect x="{W-300}" y="64" width="12" height="3" fill="#5b9dff"/><text x="{W-282}" y="69" fill="#c7d2e0">mesure indépendante</text>
<rect x="{W-300}" y="84" width="12" height="3" fill="#f0b232"/><text x="{W-282}" y="89" fill="#c7d2e0">déclaré par le trader</text>
</g>
<text x="{W-M}" y="{H-14}" fill="#8b98a9" font-size="11" text-anchor="end">divergence finale {fin["divergence_eur"]:+.0f} € · D1 {fin["D1_hypotheses_execution_eur"]:+.0f} · D2 {fin["D2_valorisation_eur"]:+.0f} · D3 {fin["D3_couts_omis_eur"]:+.0f} · D4 {fin["D4_arithmetique_eur"]:+.0f}</text>
</svg>
''') and True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--racine", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    a = ap.parse_args()
    R = a.racine
    trader = lire(os.path.join(R, "data", "trader-ledger.csv"))
    mesure = lire(os.path.join(R, "data", "equity.csv"))
    fills = lire(os.path.join(R, "data", "fills.csv"))
    if not trader or not mesure:
        print("Réconciliation impossible : il manque la comptabilité du trader ou celle du mesureur.")
        print(f"  trader-ledger.csv : {len(trader)} lignes · equity.csv : {len(mesure)} lignes")
        return
    lignes = reconcilier(trader, mesure, fills)
    cols = ["date", "capitaux_declares_eur", "capitaux_mesures_eur", "divergence_eur",
            "divergence_pct_des_capitaux_mesures", "D1_hypotheses_execution_eur", "D2_valorisation_eur",
            "D3_couts_omis_eur", "D3_detail", "D4_arithmetique_eur", "depasse_25_pct"]
    os.makedirs(os.path.join(R, "data"), exist_ok=True)
    with open(os.path.join(R, "data", "reconciliation.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader(); w.writerows(lignes)
    os.makedirs(os.path.join(R, "reports", "final"), exist_ok=True)
    svg(lignes, os.path.join(R, "reports", "final", "divergence.svg"))
    fin = lignes[-1]
    md = [f"# Réconciliation B5 — au {fin['date']}", "",
          f"**Capitaux propres déclarés par le trader : {fin['capitaux_declares_eur']:,.0f} €**".replace(",", " "),
          f"**Capitaux propres mesurés indépendamment : {fin['capitaux_mesures_eur']:,.0f} €**".replace(",", " "),
          f"**Divergence : {fin['divergence_eur']:+,.0f} €**, soit "
          f"{fin['divergence_pct_des_capitaux_mesures']} % des capitaux mesurés. "
          f"Un signe positif est un avantage que le trader s'attribue.".replace(",", " "), "",
          "## Décomposition", "| Source | € | Ce qu'elle isole |", "|---|---|---|",
          f"| **D1** hypothèses d'exécution | {fin['D1_hypotheses_execution_eur']:+,.0f} | "
          "prix de remplissage supposés plus favorables que la convention |".replace(",", " "),
          f"| **D2** valorisation | {fin['D2_valorisation_eur']:+,.0f} | "
          "marques plus flatteuses ou plus anciennes |".replace(",", " "),
          f"| **D3** coûts omis | {fin['D3_couts_omis_eur']:+,.0f} | "
          f"détail : {fin['D3_detail']} |".replace(",", " "),
          f"| **D4** arithmétique | {fin['D4_arithmetique_eur']:+,.0f} | résidu : erreurs de calcul pures |".replace(",", " "),
          "", f"Graphique : `reports/final/divergence.svg` · série complète : `data/reconciliation.csv`", ""]
    depasse = [l for l in lignes if l["depasse_25_pct"] == "oui"]
    if depasse:
        md += [f"⚠ **Le garde-fou des 25 % est franchi sur {len(depasse)} jour(s)**, "
               f"à partir du {depasse[0]['date']}. Événement journalisé, **non corrigé** "
               "(§3bis du pré-enregistrement) : la comptabilité du mesureur reste la référence unique.", ""]
    chemin = os.path.join(R, "reports", "final", f"reconciliation-{fin['date']}.md")
    open(chemin, "w", encoding="utf-8").write("\n".join(md))
    print("\n".join(md))


if __name__ == "__main__":
    main()
