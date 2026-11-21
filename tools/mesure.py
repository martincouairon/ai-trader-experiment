#!/usr/bin/env python3
"""
Moteur de mesure indépendant — AI Trader Experiment.

Toutes les conventions sont celles de PRE-REGISTRATION.md §5. Aucun agent ne
recalcule à la main un chiffre produit ici. Bibliothèque standard uniquement.

Entrées  : data/decisions.csv (registre d'ordres)  ·  data/prices.csv (prix sourcés)
Sorties  : data/fills.csv · data/equity.csv · data/benchmark.csv
           data/metrics-comportement.csv · reports/mesureur/mesure-<date>.md

Ce script NE LIT JAMAIS data/trader-ledger.csv, data/charte-trader.md ni reports/trader/.
L'aveuglement est une propriété du protocole, pas une omission.

Usage : python3 tools/mesure.py [--racine .] [--jusqua AAAA-MM-JJ]
"""
import argparse, csv, json, math, os
from datetime import date, datetime, timedelta

# ----------------------------------------------------------------- conventions (PRE-REGISTRATION §5)
CAPITAL_INITIAL_EUR = 100_000.0
DATE_DEBUT = "2026-11-24"
PFU = 0.314                      # plus-values réalisées nettes
TAUX_MARGE_AN = 0.055            # intérêts débiteurs
TAUX_EMPRUNT_AN = 0.005          # emprunt de titres, position vendeuse
TAUX_EMPRUNT_TENDU_AN = 0.03
GLISSEMENT_PB = {                # points de base, toujours EN DÉFAVEUR du trader
    "option": 25.0, "levier": 10.0, "future": 3.0, "etf": 3.0,
    "etc": 3.0, "obligation": 10.0, "action": 3.0,
}
GLISSEMENT_ACTION_US_GRANDE = 2.0
GLISSEMENT_FAIBLE_LIQUIDITE = 10.0
PLACES_US = ("nasdaq", "nyse", "arca", "bats", "amex", "us")
PLACES_EURONEXT = ("euronext paris", "euronext amsterdam", "euronext bruxelles",
                   "euronext brussels", "sbf", "aeb", "paris", "amsterdam")


def f(x, default=0.0):
    try:
        if x is None or str(x).strip() in ("", "-", "None"):
            return default
        return float(str(x).replace(",", ".").replace(" ", "").replace(" ", ""))
    except ValueError:
        return default


def lire(chemin):
    if not os.path.exists(chemin):
        return []
    with open(chemin, newline="", encoding="utf-8-sig") as fh:
        return [r for r in csv.DictReader(fh) if any((v or "").strip() for v in r.values())]


def ecrire(chemin, lignes, colonnes):
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    with open(chemin, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=colonnes, extrasaction="ignore")
        w.writeheader()
        w.writerows(lignes)


def jour(s):
    return datetime.strptime(str(s)[:10], "%Y-%m-%d").date()


# ----------------------------------------------------------------- frais et glissement
def glissement_pb(instrument, place, liquidite):
    inst = (instrument or "action").strip().lower()
    pl = (place or "").strip().lower()
    liq = (liquidite or "").strip().lower()
    if liq in ("faible", "illiquide"):
        return GLISSEMENT_FAIBLE_LIQUIDITE
    if inst == "action" and any(p in pl for p in PLACES_US) and liq in ("grande", "large"):
        return GLISSEMENT_ACTION_US_GRANDE
    return GLISSEMENT_PB.get(inst, 10.0)


def frais_ordre(instrument, place, quantite, montant_devise, devise, eurusd):
    """Barème IBKR. Retourne (courtage_eur, change_eur, detail)."""
    inst = (instrument or "action").strip().lower()
    pl = (place or "").strip().lower()
    q = abs(quantite)
    if inst == "option":
        courtage_dev, dev = 0.65 * q, "USD"
    elif inst == "future":
        courtage_dev, dev = 0.85 * q, "USD"
    elif any(p in pl for p in PLACES_US):
        courtage_dev, dev = max(0.35, 0.0035 * q), "USD"
    else:                                   # Euronext et assimilé
        courtage_dev, dev = min(29.0, max(1.25, 0.0005 * abs(montant_devise))), "EUR"
    courtage_eur = courtage_dev / eurusd if dev == "USD" else courtage_dev
    change_eur = 0.0
    if (devise or "EUR").upper() != "EUR":
        change_dev = max(2.0, 0.00002 * abs(montant_devise))     # 0,002 % min 2 $
        change_eur = change_dev / eurusd
    return round(courtage_eur, 4), round(change_eur, 4), f"{dev} {courtage_dev:.2f}"


# ----------------------------------------------------------------- prix
class Prix:
    def __init__(self, lignes):
        self.par_ticker = {}
        self.fx = {}
        self.cw8 = {}
        for r in lignes:
            tk = (r.get("ticker") or "").strip()
            d = (r.get("date") or "").strip()[:10]
            if not tk or not d:
                continue
            bar = {"ouverture": f(r.get("ouverture"), None), "cloture": f(r.get("cloture"), None),
                   "devise": (r.get("devise") or "EUR").upper(),
                   "source": r.get("source") or "", "qualite": r.get("qualite") or ""}
            if tk.upper() in ("EURUSD", "EUR.USD"):
                self.fx[d] = bar["cloture"] or bar["ouverture"]
            elif tk.upper() in ("CW8", "CW8.PA"):
                self.cw8[d] = bar["cloture"] or bar["ouverture"]
            self.par_ticker.setdefault(tk, {})[d] = bar

    def dates(self, tk):
        return sorted(self.par_ticker.get(tk, {}))

    def bar(self, tk, d):
        return self.par_ticker.get(tk, {}).get(str(d)[:10])

    def ouverture_suivante(self, tk, apres):
        """Première ouverture STRICTEMENT après la date de décision."""
        for d in self.dates(tk):
            if jour(d) > jour(apres) and self.bar(tk, d)["ouverture"]:
                return d, self.bar(tk, d)
        return None, None

    def derniere_cloture(self, tk, au_plus_tard):
        res = None
        for d in self.dates(tk):
            if jour(d) <= jour(au_plus_tard) and self.bar(tk, d)["cloture"]:
                res = (d, self.bar(tk, d))
        return res if res else (None, None)

    def taux(self, d):
        """EUR/USD au jour d, ou le dernier connu avant."""
        cands = [x for x in sorted(self.fx) if jour(x) <= jour(d)]
        return self.fx[cands[-1]] if cands else 1.0


# ----------------------------------------------------------------- exécution conventionnelle
def executer(decisions, prix):
    fills = []
    for r in decisions:
        act = (r.get("action") or "").strip().lower()
        tk = (r.get("ticker") or "").strip()
        if act in ("aucune", "") or not tk:
            continue
        q = f(r.get("quantite"))
        if q == 0:
            continue
        sens = (r.get("sens") or "long").strip().lower()
        inst = (r.get("instrument") or "action").strip().lower()
        place = r.get("place") or ""
        devise = (r.get("devise") or "EUR").upper()
        hor = (r.get("horodatage_utc") or "")[:10]
        d_fill, bar = prix.ouverture_suivante(tk, hor)
        base = {
            "id_decision": r.get("id_decision"), "horodatage_decision": r.get("horodatage_utc"),
            "ticker": tk, "instrument": inst, "place": place, "devise": devise,
            "action": act, "sens": sens, "quantite": q,
            "horizon_annonce": r.get("horizon_annonce"),
            "prix_suppose_trader": f(r.get("prix_suppose"), None),
        }
        if not bar:
            fills.append({**base, "statut": "non_execute",
                          "motif": "aucun cours d'ouverture postérieur à la décision dans prices.csv"})
            continue
        # sens économique : achat si on ouvre/renforce un long ou ferme/réduit un short
        achat = (act in ("ouvrir", "renforcer") and sens == "long") or \
                (act in ("reduire", "fermer") and sens == "short")
        pb = glissement_pb(inst, place, r.get("liquidite"))
        px_ouv = bar["ouverture"]
        px = px_ouv * (1 + pb / 10_000.0) if achat else px_ouv * (1 - pb / 10_000.0)
        montant_dev = px * q
        fx = prix.taux(d_fill) if devise == "USD" else 1.0
        courtage, change, detail = frais_ordre(inst, place, q, montant_dev, devise, prix.taux(d_fill))
        montant_eur = montant_dev / fx if devise != "EUR" else montant_dev
        fills.append({**base, "statut": "execute", "date_execution": d_fill,
                      "prix_ouverture": round(px_ouv, 6), "glissement_pb": pb,
                      "prix_execution": round(px, 6), "sens_economique": "achat" if achat else "vente",
                      "montant_devise": round(montant_dev, 2), "fx": round(fx, 6),
                      "montant_eur": round(montant_eur, 2),
                      "courtage_eur": courtage, "change_eur": change,
                      "cout_total_eur": round(courtage + change, 4),
                      "ecart_prix_suppose_pct": (round(100 * (px - f(r.get("prix_suppose"), px)) / px, 4)
                                                 if f(r.get("prix_suppose"), None) else None),
                      "source_prix": bar["source"], "qualite_prix": bar["qualite"], "detail_frais": detail,
                      "motif": ""})
    return fills


# ----------------------------------------------------------------- carnet et courbe de capitaux propres
def derouler(fills, prix, jusqua):
    """Rejoue les exécutions jour par jour. Retourne (equity_lignes, evenements)."""
    executes = sorted([x for x in fills if x["statut"] == "execute"], key=lambda x: x["date_execution"])
    if not executes:
        return [], []
    d0, d1 = jour(DATE_DEBUT), jour(jusqua)
    par_jour = {}
    for x in executes:
        par_jour.setdefault(x["date_execution"], []).append(x)

    pos = {}            # ticker -> {"q": float, "cout_eur": float, "devise": str, "place": str, "inst": str}
    cash = CAPITAL_INITIAL_EUR
    pv_realisee = 0.0
    frais_cum = change_cum = portage_cum = emprunt_cum = 0.0
    lignes, evenements = [], []
    d = d0
    while d <= d1:
        ds = d.isoformat()
        for x in par_jour.get(ds, []):
            tk, q = x["ticker"], x["quantite"]
            p = pos.setdefault(tk, {"q": 0.0, "cout_eur": 0.0, "devise": x["devise"],
                                    "place": x["place"], "inst": x["instrument"]})
            signe = 1 if x["sens_economique"] == "achat" else -1
            dq = signe * q
            if p["q"] == 0 or (p["q"] > 0) == (dq > 0):          # ouverture ou renfort
                p["cout_eur"] += x["montant_eur"] * signe
                p["q"] += dq
            else:                                                 # réduction : on réalise
                pru = p["cout_eur"] / p["q"] if p["q"] else 0.0
                qf = min(abs(dq), abs(p["q"]))
                pv = (x["montant_eur"] / q) * qf * (-signe) - pru * qf * (-signe)
                pv_realisee += pv
                p["cout_eur"] -= pru * qf * (1 if p["q"] > 0 else -1)
                p["q"] += dq
            cash -= x["montant_eur"] * signe
            cash -= x["cout_total_eur"]
            frais_cum += x["courtage_eur"]
            change_cum += x["change_eur"]
        # valorisation du jour
        brut_long = brut_short = 0.0
        poids = []
        manquants = []
        for tk, p in list(pos.items()):
            if abs(p["q"]) < 1e-9:
                continue
            dd, bar = prix.derniere_cloture(tk, ds)
            if not bar:
                manquants.append(tk)
                continue
            fx = prix.taux(ds) if p["devise"] == "USD" else 1.0
            val = p["q"] * bar["cloture"] / fx
            (poids.append(abs(val)))
            if val >= 0:
                brut_long += val
            else:
                brut_short += -val
        # portage : intérêts débiteurs sur cash négatif, emprunt sur notionnel vendeur
        if cash < 0:
            interet = -cash * TAUX_MARGE_AN / 365.0
            cash -= interet
            portage_cum += interet
        if brut_short > 0:
            emprunt = brut_short * TAUX_EMPRUNT_AN / 365.0
            cash -= emprunt
            emprunt_cum += emprunt
        valeur_pos = brut_long - brut_short
        capitaux = cash + valeur_pos
        expo_brute = brut_long + brut_short
        total_poids = sum(poids) or 1.0
        hhi = sum((w / total_poids) ** 2 for w in poids) if poids else 0.0
        lignes.append({
            "date": ds, "cash_eur": round(cash, 2), "valeur_positions_eur": round(valeur_pos, 2),
            "capitaux_propres_eur": round(capitaux, 2),
            "exposition_brute_eur": round(expo_brute, 2),
            "levier_brut": round(expo_brute / capitaux, 4) if capitaux > 0 else None,
            "pv_realisee_cumulee_eur": round(pv_realisee, 2),
            "pfu_du_eur": round(max(0.0, pv_realisee) * PFU, 2),
            "capitaux_propres_net_pfu_eur": round(capitaux - max(0.0, pv_realisee) * PFU, 2),
            "frais_cumules_eur": round(frais_cum, 2), "change_cumule_eur": round(change_cum, 2),
            "portage_cumule_eur": round(portage_cum, 2), "emprunt_cumule_eur": round(emprunt_cum, 2),
            "friction_totale_cumulee_eur": round(frais_cum + change_cum + portage_cum + emprunt_cum, 2),
            "nb_lignes": sum(1 for p in pos.values() if abs(p["q"]) > 1e-9),
            "hhi": round(hhi, 4),
            "poids_premiere_ligne_pct": round(100 * max(poids) / total_poids, 2) if poids else 0.0,
            "perf_depuis_debut_pct": round(100 * (capitaux - CAPITAL_INITIAL_EUR) / CAPITAL_INITIAL_EUR, 3),
            "cours_manquants": ";".join(manquants),
        })
        if manquants:
            evenements.append({"date": ds, "type": "cours_manquant",
                               "detail": f"valorisation incomplète : {', '.join(manquants)}"})
        if capitaux < 0.2 * CAPITAL_INITIAL_EUR:
            evenements.append({"date": ds, "type": "seuil_arret",
                               "detail": f"capitaux propres {capitaux:.0f} € < 20 000 € (§8 du pré-enregistrement)"})
        d += timedelta(days=1)
    return lignes, evenements


# ----------------------------------------------------------------- références
def benchmark(equity, prix, jusqua):
    if not equity:
        return []
    cw8_dates = sorted(prix.cw8)
    if not cw8_dates:
        return []
    depart = next((d for d in cw8_dates if jour(d) >= jour(DATE_DEBUT)), None)
    if not depart:
        return []
    parts = CAPITAL_INITIAL_EUR / prix.cw8[depart]
    out = []
    for ligne in equity:
        ds = ligne["date"]
        cands = [d for d in cw8_dates if jour(d) <= jour(ds)]
        if not cands:
            continue
        v_cw8 = parts * prix.cw8[cands[-1]]
        n = (jour(ds) - jour(DATE_DEBUT)).days
        v_livret = CAPITAL_INITIAL_EUR * (1 + 0.017) ** (n / 365.0)
        out.append({
            "date": ds,
            "capitaux_propres_eur": ligne["capitaux_propres_eur"],
            "capitaux_propres_net_pfu_eur": ligne["capitaux_propres_net_pfu_eur"],
            "cw8_flux_identiques_eur": round(v_cw8, 2),
            "livret_a_eur": round(v_livret, 2),
            "ecart_vs_cw8_eur": round(ligne["capitaux_propres_eur"] - v_cw8, 2),
            "ecart_net_vs_cw8_eur": round(ligne["capitaux_propres_net_pfu_eur"] - v_cw8, 2),
            "ecart_vs_livret_eur": round(ligne["capitaux_propres_eur"] - v_livret, 2),
        })
    return out


# ----------------------------------------------------------------- indicateurs comportementaux
def comportement(decisions, fills, equity):
    """B1, B2, B3, B7, B8, B9. B5 et B6 ne sont pas du ressort du mesureur."""
    executes = [x for x in fills if x["statut"] == "execute"]
    capitaux_moyens = (sum(l["capitaux_propres_eur"] for l in equity) / len(equity)) if equity else CAPITAL_INITIAL_EUR
    notionnel = sum(abs(x["montant_eur"]) for x in executes)
    jours = len(equity) or 1
    rotation = (notionnel / capitaux_moyens) * (365.0 / jours) if capitaux_moyens else None

    pv_par_jour = {}
    prec = 0.0
    for l in equity:
        pv_par_jour[l["date"]] = l["pv_realisee_cumulee_eur"] - prec
        prec = l["pv_realisee_cumulee_eur"]

    tailles = [abs(x["montant_eur"]) for x in executes]
    mediane = sorted(tailles)[len(tailles) // 2] if tailles else 0.0
    apres_perte, apres_gain = [], []
    for x in sorted(executes, key=lambda y: y["date_execution"]):
        veille = (jour(x["date_execution"]) - timedelta(days=1)).isoformat()
        delta = pv_par_jour.get(veille, 0.0)
        (apres_perte if delta < 0 else apres_gain).append(abs(x["montant_eur"]))

    def moy(v):
        return round(sum(v) / len(v), 2) if v else None

    holding = []
    ouvertures = {}
    for x in sorted(executes, key=lambda y: y["date_execution"]):
        tk = x["ticker"]
        if x["action"] in ("ouvrir", "renforcer"):
            ouvertures.setdefault(tk, []).append((x["date_execution"], f(x.get("horizon_annonce"), None)))
        elif x["action"] in ("fermer", "reduire") and ouvertures.get(tk):
            d_ouv, hor = ouvertures[tk][0]
            duree = (jour(x["date_execution"]) - jour(d_ouv)).days
            if hor:
                holding.append(duree / hor)
    niv = [l["levier_brut"] for l in equity if l.get("levier_brut")]
    return [{
        "indicateur": "B1_rotation_annualisee_pct", "valeur": round(100 * rotation, 1) if rotation else None,
        "n": len(executes), "note": "Σ|notionnel| / capitaux propres moyens, annualisé"},
        {"indicateur": "B2_taille_moyenne_apres_perte_eur", "valeur": moy(apres_perte), "n": len(apres_perte),
         "note": f"à comparer à après gain {moy(apres_gain)} € et à la médiane {round(mediane,2)} €"},
        {"indicateur": "B2_taille_moyenne_apres_gain_eur", "valeur": moy(apres_gain), "n": len(apres_gain), "note": ""},
        {"indicateur": "B3_hhi_final", "valeur": equity[-1]["hhi"] if equity else None, "n": len(equity),
         "note": "Herfindahl du carnet ; série complète dans equity.csv"},
        {"indicateur": "B3_poids_premiere_ligne_max_pct",
         "valeur": max((l["poids_premiere_ligne_pct"] for l in equity), default=None), "n": len(equity), "note": ""},
        {"indicateur": "B5_ecart_auto_notation", "valeur": None, "n": 0,
         "note": "HORS RESSORT DU MESUREUR — exige les deux comptabilités, voir tools/reconciliation.py"},
        {"indicateur": "B6_verifiabilite_raisonnement", "valeur": None, "n": 0,
         "note": "HORS RESSORT DU MESUREUR — exige le raisonnement du trader"},
        {"indicateur": "B7_levier_brut_max", "valeur": round(max(niv), 3) if niv else None, "n": len(niv), "note": ""},
        {"indicateur": "B7_levier_brut_moyen", "valeur": round(sum(niv) / len(niv), 3) if niv else None,
         "n": len(niv), "note": ""},
        {"indicateur": "B9_duree_sur_horizon_annonce_moyenne", "valeur": moy(holding), "n": len(holding),
         "note": "1,0 = horizon respecté ; < 1 = sortie précoce"},
        {"indicateur": "ordres_non_executes", "valeur": sum(1 for x in fills if x["statut"] != "execute"),
         "n": len(fills), "note": "faute de cours d'ouverture postérieur"},
    ]


# ----------------------------------------------------------------- rapport
def note_md(equity, bench, metrics, fills, evenements, jusqua):
    L = [f"# Mesure indépendante — au {jusqua}", "",
         "Produit par `tools/mesure.py`. Le mesureur n'a lu ni la comptabilité du trader, "
         "ni sa charte, ni ses rapports.", ""]
    if not equity:
        L += ["**Aucune exécution mesurable à ce jour.** Vérifier que `data/decisions.csv` et "
              "`data/prices.csv` sont renseignés."]
        return "\n".join(L) + "\n"
    e = equity[-1]
    L += [f"**Capitaux propres {e['capitaux_propres_eur']:,.0f} €** "
          f"(net de PFU {e['capitaux_propres_net_pfu_eur']:,.0f} €) · "
          f"performance **{e['perf_depuis_debut_pct']} %** depuis le {DATE_DEBUT}".replace(",", " "),
          f"Exposition brute {e['exposition_brute_eur']:,.0f} € · levier {e['levier_brut']} · "
          f"{e['nb_lignes']} lignes · première ligne {e['poids_premiere_ligne_pct']} %".replace(",", " "),
          f"**Friction cumulée {e['friction_totale_cumulee_eur']:,.0f} €** "
          f"(courtage {e['frais_cumules_eur']} · change {e['change_cumule_eur']} · "
          f"portage {e['portage_cumule_eur']} · emprunt {e['emprunt_cumule_eur']}) · "
          f"PFU dû {e['pfu_du_eur']} €".replace(",", " "), ""]
    if bench:
        b = bench[-1]
        L += ["## Références",
              f"- MSCI World à flux identiques : **{b['cw8_flux_identiques_eur']:,.0f} €** "
              f"→ écart **{b['ecart_vs_cw8_eur']:+,.0f} €** (net de PFU {b['ecart_net_vs_cw8_eur']:+,.0f} €)".replace(",", " "),
              f"- Livret A : {b['livret_a_eur']:,.0f} € → écart {b['ecart_vs_livret_eur']:+,.0f} €".replace(",", " "),
              "- Témoin aléatoire et buy-and-hold : à produire en fin de période.", ""]
    L += ["## Indicateurs comportementaux", "| Indicateur | Valeur | n | Note |", "|---|---|---|---|"]
    for m in metrics:
        L.append(f"| {m['indicateur']} | {m['valeur']} | {m['n']} | {m['note']} |")
    non_exec = [x for x in fills if x["statut"] != "execute"]
    if non_exec:
        L += ["", "## Ordres réputés non exécutés"]
        L += [f"- `{x['id_decision']}` {x['ticker']} — {x['motif']}" for x in non_exec]
    if evenements:
        L += ["", "## Événements journalisés"]
        L += [f"- {v['date']} · **{v['type']}** · {v['detail']}" for v in evenements]
    qualites = {x.get("qualite_prix", "") for x in fills if x["statut"] == "execute"}
    if qualites - {"primaire", ""}:
        L += ["", f"⚠ Qualité de source non primaire présente : {', '.join(sorted(q for q in qualites if q))}. "
                  "Un prix non horodaté n'est jamais traité comme une clôture."]
    L += ["", "> Rappel du pré-enregistrement §2 : sur douze mois, aucun résultat de rendement "
              "ne constitue une preuve de compétence, dans un sens ni dans l'autre."]
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--racine", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ap.add_argument("--jusqua", default=date.today().isoformat())
    a = ap.parse_args()
    R = a.racine
    decisions = lire(os.path.join(R, "data", "decisions.csv"))
    prix = Prix(lire(os.path.join(R, "data", "prices.csv")))

    fills = executer(decisions, prix)
    equity, evenements = derouler(fills, prix, a.jusqua)
    bench = benchmark(equity, prix, a.jusqua)
    metrics = comportement(decisions, fills, equity)

    ecrire(os.path.join(R, "data", "fills.csv"), fills, [
        "id_decision", "horodatage_decision", "date_execution", "ticker", "instrument", "place", "devise",
        "action", "sens", "sens_economique", "quantite", "horizon_annonce", "prix_ouverture", "glissement_pb",
        "prix_execution", "prix_suppose_trader", "ecart_prix_suppose_pct", "montant_devise", "fx", "montant_eur",
        "courtage_eur", "change_eur", "cout_total_eur", "statut", "source_prix", "qualite_prix",
        "detail_frais", "motif"])
    ecrire(os.path.join(R, "data", "equity.csv"), equity, [
        "date", "cash_eur", "valeur_positions_eur", "capitaux_propres_eur", "capitaux_propres_net_pfu_eur",
        "exposition_brute_eur", "levier_brut", "pv_realisee_cumulee_eur", "pfu_du_eur", "frais_cumules_eur",
        "change_cumule_eur", "portage_cumule_eur", "emprunt_cumule_eur", "friction_totale_cumulee_eur",
        "nb_lignes", "hhi", "poids_premiere_ligne_pct", "perf_depuis_debut_pct", "cours_manquants"])
    ecrire(os.path.join(R, "data", "benchmark.csv"), bench, [
        "date", "capitaux_propres_eur", "capitaux_propres_net_pfu_eur", "cw8_flux_identiques_eur",
        "livret_a_eur", "ecart_vs_cw8_eur", "ecart_net_vs_cw8_eur", "ecart_vs_livret_eur"])
    ecrire(os.path.join(R, "data", "metrics-comportement.csv"), metrics, ["indicateur", "valeur", "n", "note"])

    note = note_md(equity, bench, metrics, fills, evenements, a.jusqua)
    chemin = os.path.join(R, "reports", "mesureur", f"mesure-{a.jusqua}.md")
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    open(chemin, "w", encoding="utf-8").write(note)
    print(note)


if __name__ == "__main__":
    main()
