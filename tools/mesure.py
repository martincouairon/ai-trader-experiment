#!/usr/bin/env python3
"""
Moteur de mesure indépendant — AI Trader Experiment.

Toutes les conventions sont celles de PRE-REGISTRATION.md §5. Aucun agent ne
recalcule à la main un chiffre produit ici. Bibliothèque standard uniquement.

Entrées  : data/decisions.csv (registre d'ordres)  ·  data/prices.csv (prix sourcés)
Sorties  : data/fills.csv · data/equity.csv · data/positions.csv · data/benchmark.csv
           data/benchmark-investisseurs.csv · data/metrics-comportement.csv
           reports/mesureur/mesure-<date>.md
Formats  : tools/formats.py (en-têtes exacts), contrôlés par tools/valider-formats.py

Coûts et impôt suivis, en cumul quotidien dans equity.csv : courtage, change,
glissement (en euros, et non plus seulement en points de base), portage, emprunt de
titres, coût des liquidations forcées, et PFU dû par année civile avec report des
moins-values. Le PFU latent (dû si tout était liquidé le jour même) est publié à
part : il permet une comparaison nette d'impôt avec un indice qu'on ne vend pas.

Ce script NE LIT JAMAIS data/trader-ledger.csv, data/charte-trader.md ni reports/trader/.
L'aveuglement est une propriété du protocole, pas une omission.

Usage : python3 tools/mesure.py [--racine .] [--jusqua AAAA-MM-JJ]
"""
import argparse, csv, json, math, os, sys
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import formats as FMT  # noqa: E402  — en-têtes canoniques, voir tools/formats.py

# ----------------------------------------------------------------- conventions (PRE-REGISTRATION §5)
CAPITAL_INITIAL_EUR = 120_000.0
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
GLISSEMENT_LIQUIDATION_FORCEE_PB = 10.0

# ------------------------------------------------------------------ régimes de marge
# Le TRADER choisit son régime (data/regime-marge.csv). Les EXIGENCES de chaque régime
# sont celles d'un vrai courtier et ne sont négociables par personne : c'est la frontière
# entre « l'agent décide de son levier » et « l'agent invente ses contraintes ».
REGIMES = {
    # compte espèces : aucun emprunt, aucune vente à découvert, options vendues garanties en espèces
    "cash": {("action", "long"): (1.00, 1.00), ("etf", "long"): (1.00, 1.00),
             ("etc", "long"): (1.00, 1.00), ("obligation", "long"): (1.00, 1.00),
             ("levier", "long"): (1.00, 1.00), ("option", "long"): (1.00, 1.00),
             ("option", "short"): (1.00, 1.00)},
    # Reg-T (IBKR LLC) : le régime standard d'un compte sur marge
    "reg_t": {("action", "long"): (0.50, 0.25), ("action", "short"): (0.50, 0.30),
              ("etf", "long"): (0.50, 0.25), ("etf", "short"): (0.50, 0.30),
              ("etc", "long"): (0.50, 0.25), ("etc", "short"): (0.50, 0.30),
              ("obligation", "long"): (0.50, 0.25), ("obligation", "short"): (0.50, 0.30),
              ("levier", "long"): (1.00, 1.00), ("levier", "short"): (0.75, 0.75),
              ("option", "long"): (1.00, 1.00), ("option", "short"): (0.20, 0.15),
              ("future", "long"): (0.15, 0.10), ("future", "short"): (0.15, 0.10)},
    # Portfolio Margin : exigence fondée sur le risque, bien plus permissive,
    # mais soumise à un seuil de capitaux propres et à des majorations de concentration
    "portfolio_margin": {("action", "long"): (0.15, 0.15), ("action", "short"): (0.15, 0.15),
                         ("etf", "long"): (0.15, 0.15), ("etf", "short"): (0.15, 0.15),
                         ("etc", "long"): (0.15, 0.15), ("etc", "short"): (0.15, 0.15),
                         ("obligation", "long"): (0.15, 0.15), ("obligation", "short"): (0.15, 0.15),
                         ("levier", "long"): (0.30, 0.30), ("levier", "short"): (0.30, 0.30),
                         ("option", "long"): (1.00, 1.00), ("option", "short"): (0.15, 0.12),
                         ("future", "long"): (0.12, 0.08), ("future", "short"): (0.12, 0.08)},
}
REGIME_DEFAUT = "cash"              # un compte sans convention de marge signée est un compte espèces
PM_SEUIL_OUVERTURE_USD = 110_000.0  # capitaux propres exigés pour ouvrir le Portfolio Margin
PM_SEUIL_MAINTIEN_USD = 100_000.0   # en dessous, rétrogradation d'office en Reg-T
PM_CONCENTRATION = ((0.50, 0.40), (0.30, 0.25))   # (part des capitaux propres, exigence plancher)
DELAI_CHANGEMENT_REGIME_JOURS = 2   # un changement de régime chez un courtier n'est pas instantané
COUSSIN_APRES_LIQUIDATION = 1.20
MULTIPLICATEUR = {"option": 100.0}       # quantité exprimée en contrats
SUR_NOTIONNEL = {("option", "short"), ("future", "long"), ("future", "short")}
REFERENCES = ("IWDA", "CW8", "WPEA")     # IWDA = seule de qualité primaire (IBKR AEB)
TAUX_LIVRET_A = 0.017
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
        self.refs = {r: {} for r in REFERENCES}
        for r in lignes:
            tk = (r.get("ticker") or "").strip()
            d = (r.get("date") or "").strip()[:10]
            if not tk or not d:
                continue
            bar = {"ouverture": f(r.get("ouverture"), None), "cloture": f(r.get("cloture"), None),
                   "haut": f(r.get("haut"), None), "bas": f(r.get("bas"), None),
                   "devise": (r.get("devise") or "EUR").upper(),
                   "source": r.get("source") or "", "qualite": r.get("qualite") or ""}
            u = tk.upper().split(".")[0]
            if u in ("EURUSD", "EUR"):
                self.fx[d] = bar["cloture"] or bar["ouverture"]
            elif u in self.refs:
                self.refs[u][d] = bar["cloture"] or bar["ouverture"]
            self.par_ticker.setdefault(tk, {})[d] = bar

    def dates(self, tk):
        return sorted(self.par_ticker.get(tk, {}))

    def bar(self, tk, d):
        return self.par_ticker.get(tk, {}).get(str(d)[:10])

    def sessions_apres(self, tk, apres, maxi):
        """Les séances cotées STRICTEMENT après la date de décision, dans l'ordre."""
        out = []
        for d in self.dates(tk):
            if jour(d) > jour(apres) and self.bar(tk, d)["ouverture"]:
                out.append((d, self.bar(tk, d)))
                if len(out) >= maxi:
                    break
        return out

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
SESSIONS_GTC = 90          # une validité longue reste finie


def remplir(type_ordre, achat, limite, bar, pb):
    """Sémantique réelle du type d'ordre, à partir de la barre de la séance.
    Retourne (prix, motif_non_execution). Un ordre limité remplit AU PLUS à sa limite
    et ne subit pas de glissement : c'est précisément ce qu'on achète en le posant.
    Un ordre au marché ou déclenché par un stop subit le glissement."""
    t = (type_ordre or "limite").strip().lower()
    o, h, b = bar["ouverture"], bar.get("haut"), bar.get("bas")
    adv = (1 + pb / 10_000.0) if achat else (1 - pb / 10_000.0)
    if "marche" in t or "market" in t:
        return o * adv, None
    if "stop" in t:
        if not limite:
            return None, "ordre stop sans seuil"
        if achat:
            if o >= limite:
                return o * adv, None                      # déjà au-dessus : déclenché à l'ouverture
            if h is not None and h >= limite:
                return limite * adv, None
            return None, f"seuil stop {limite} non atteint (haut {h})"
        if o <= limite:
            return o * adv, None
        if b is not None and b <= limite:
            return limite * adv, None
        return None, f"seuil stop {limite} non atteint (bas {b})"
    # ordre à cours limité
    if not limite:
        return o * adv, None                              # pas de limite donnée : traité au marché
    if achat:
        if o <= limite:
            return o, None                                # exécuté mieux que la limite
        if b is not None and b <= limite:
            return limite, None
        return None, f"limite {limite} non touchée (bas {b})"
    if o >= limite:
        return o, None
    if h is not None and h >= limite:
        return limite, None
    return None, f"limite {limite} non touchée (haut {h})"


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
        type_ordre = (r.get("type_ordre") or "limite").strip()
        limite = f(r.get("limite"), None)
        hor = (r.get("horodatage_utc") or "")[:10]
        mult = f(r.get("multiplicateur"), MULTIPLICATEUR.get(inst, 1.0)) or 1.0
        notionnel = f(r.get("notionnel_sous_jacent"), None)
        gtc = "gtc" in type_ordre.lower() or (r.get("validite") or "").strip().lower() == "gtc"
        base = {
            "id_decision": r.get("id_decision"), "horodatage_decision": r.get("horodatage_utc"),
            "ticker": tk, "instrument": inst, "place": place, "devise": devise,
            "action": act, "sens": sens, "quantite": q, "type_ordre": type_ordre, "limite": limite,
            "validite": "gtc" if gtc else "jour",
            "horizon_annonce": r.get("horizon_annonce"),
            "prix_suppose_trader": f(r.get("prix_suppose"), None),
            "multiplicateur": mult, "notionnel_sous_jacent": notionnel,
            "id_position": (r.get("id_position") or "").strip(),
            "strategie": (r.get("strategie") or "").strip(),
        }
        if inst in ("option", "future") and not notionnel and act in ("ouvrir", "renforcer", "inverser"):
            fills.append({**base, "statut": "non_execute",
                          "motif": "notionnel_sous_jacent non déclaré — exigence de marge inconnue (§1bis)"})
            continue
        achat = (act in ("ouvrir", "renforcer") and sens == "long") or \
                (act in ("reduire", "fermer") and sens == "short")
        pb = glissement_pb(inst, place, r.get("liquidite"))
        sessions = prix.sessions_apres(tk, hor, SESSIONS_GTC if gtc else 1)
        if not sessions:
            fills.append({**base, "statut": "non_execute",
                          "motif": "aucune séance cotée postérieure à la décision dans prices.csv"})
            continue
        px = d_fill = bar = None
        motifs = []
        for d_c, bar_c in sessions:
            p_c, motif = remplir(type_ordre, achat, limite, bar_c, pb)
            if p_c:
                px, d_fill, bar = p_c, d_c, bar_c
                break
            motifs.append(f"{d_c} : {motif}")
        if not px:
            fills.append({**base, "statut": "non_execute", "sessions_testees": len(sessions),
                          "motif": ("ordre " + ("GTC " if gtc else "")
                                    + "non touché — " + " · ".join(motifs[:3])
                                    + (" …" if len(motifs) > 3 else ""))})
            continue
        montant_dev = px * q * mult
        fx = prix.taux(d_fill) if devise == "USD" else 1.0
        courtage, change, detail = frais_ordre(inst, place, q, montant_dev, devise, prix.taux(d_fill))
        montant_eur = montant_dev / fx if devise != "EUR" else montant_dev
        glissement_applique = ("marche" in type_ordre.lower() or "stop" in type_ordre.lower()
                               or not limite)
        # glissement en euros : écart entre le prix servi et le même prix sans glissement
        adv = (1 + pb / 10_000.0) if achat else (1 - pb / 10_000.0)
        glissement_eur = (abs(px - px / adv) * q * mult / (fx if devise != "EUR" else 1.0)
                          if glissement_applique else 0.0)
        fills.append({**base, "statut": "execute", "date_execution": d_fill,
                      "sessions_testees": sessions.index((d_fill, bar)) + 1,
                      "prix_ouverture": round(bar["ouverture"], 6),
                      "glissement_pb": pb if glissement_applique else 0.0,
                      "prix_execution": round(px, 6), "sens_economique": "achat" if achat else "vente",
                      "montant_devise": round(montant_dev, 2), "fx": round(fx, 6),
                      "montant_eur": round(montant_eur, 2),
                      "courtage_eur": courtage, "change_eur": change,
                      "glissement_eur": round(glissement_eur, 4),
                      "cout_total_eur": round(courtage + change, 4),
                      "ecart_prix_suppose_pct": (round(100 * (px - f(r.get("prix_suppose"), px)) / px, 4)
                                                 if f(r.get("prix_suppose"), None) else None),
                      "source_prix": bar["source"], "qualite_prix": bar["qualite"], "detail_frais": detail,
                      "motif": ""})
    return fills


# ----------------------------------------------------------------- carnet, marge et courbe de capitaux propres
def regime_au(declarations, d, equity_veille_eur, fx):
    """Régime en vigueur à la date d : la dernière déclaration du trader dont le délai
    de prise d'effet est écoulé, rétrogradée d'office si le Portfolio Margin n'est plus tenu."""
    courant = REGIME_DEFAUT
    for r in sorted(declarations, key=lambda x: x.get("date_effet", "")):
        de = (r.get("date_effet") or "").strip()[:10]
        reg = (r.get("regime") or "").strip().lower()
        if not de or reg not in REGIMES:
            continue
        if (jour(d) - jour(de)).days >= DELAI_CHANGEMENT_REGIME_JOURS:
            courant = reg
    if courant == "portfolio_margin":
        eq_usd = (equity_veille_eur or 0.0) * (fx or 1.0)
        if eq_usd < PM_SEUIL_MAINTIEN_USD:
            return "reg_t", (f"Portfolio Margin perdu : capitaux propres {eq_usd:,.0f} $ "
                             f"< {PM_SEUIL_MAINTIEN_USD:,.0f} $ — rétrogradation d'office en Reg-T")
    return courant, None


def exigence(regime, inst, sens, valeur_abs, notionnel_eur, phase, equity_eur=None):
    """Exigence de marge d'une position sous le régime en vigueur.
    phase ∈ {'initiale','maintien'}. Retourne (montant, interdit_motif)."""
    table = REGIMES.get(regime, REGIMES["reg_t"])
    taux = table.get((inst, sens))
    if taux is None:
        if regime == "cash":
            return 0.0, f"{inst} {sens} indisponible en compte espèces"
        taux = (0.50, 0.30)
    t = taux[0] if phase == "initiale" else taux[1]
    assiette = notionnel_eur if (inst, sens) in SUR_NOTIONNEL and notionnel_eur else valeur_abs
    if regime == "portfolio_margin" and equity_eur and assiette > 0:
        for part, plancher in PM_CONCENTRATION:
            if assiette > part * equity_eur:
                t = max(t, plancher)
                break
    return t * assiette, None


def cle_position(x):
    """Une ligne d'actions et une option sur le même sous-jacent sont DEUX positions.
    Le trader peut forcer le regroupement avec id_position."""
    idp = (x.get("id_position") or "").strip()
    if idp:
        return idp
    inst = (x.get("instrument") or "action").strip().lower()
    if inst in ("action", "etf", "etc", "obligation"):
        return f"{x['ticker']}|comptant"
    return f"{x['ticker']}|{inst}|{(x.get('sens') or 'long').strip().lower()}"


def derouler(fills, prix, jusqua, declarations=None):
    """Rejoue les exécutions jour par jour, avec marge, portage et liquidation forcée.
    Les futures sont tenus en marge de variation : aucun décaissement à l'entrée,
    la variation quotidienne passe en trésorerie, la position ne porte pas de valeur."""
    executes = sorted([x for x in fills if x["statut"] == "execute"], key=lambda x: x["date_execution"])
    d0, d1 = jour(DATE_DEBUT), jour(jusqua)
    par_jour = {}
    for x in executes:
        par_jour.setdefault(x["date_execution"], []).append(x)

    pos = {}          # ticker -> q, cout_eur, devise, place, inst, sens, notionnel_u, mult, dernier_px
    cash = CAPITAL_INITIAL_EUR
    pv_realisee = 0.0
    frais_cum = change_cum = portage_cum = emprunt_cum = 0.0
    glissement_cum = liquidation_cum = 0.0
    pv_par_annee, frais_par_annee = {}, {}   # base du PFU, année civile par année civile
    lignes, evenements, instantanes = [], [], []
    liquidation_en_attente = 0.0        # fraction à liquider à l'ouverture suivante
    nb_appels = 0
    declarations = declarations or []
    equity_veille = CAPITAL_INITIAL_EUR
    regime_veille = None

    def appliquer(x, q_signee, pr):
        """Applique un mouvement de q_signee unités au prix unitaire pr (devise), frais inclus hors."""
        nonlocal cash, pv_realisee
        annee = str(x.get("date_execution") or x.get("_date") or "")[:4]
        tk, inst = x["ticker"], x["instrument"]
        cle = cle_position(x)
        mult = f(x.get("multiplicateur"), 1.0) or 1.0
        fx = f(x.get("fx"), 1.0) or 1.0
        p = pos.setdefault(cle, {"q": 0.0, "cout_eur": 0.0, "ticker": tk, "devise": x["devise"], "place": x["place"],
                                "inst": inst, "sens": x["sens"], "mult": mult,
                                "notionnel_u": (f(x.get("notionnel_sous_jacent"), 0.0) / abs(f(x.get("quantite"), 1.0) or 1.0)),
                                "dernier_px": pr})
        if x.get("strategie") and x.get("action") in ("ouvrir", "renforcer", "inverser"):
            p["strategie"] = x["strategie"]
        montant_eur = pr * abs(q_signee) * mult / fx
        if inst == "future":
            p["q"] += q_signee            # pas de décaissement : marge de variation
            p["dernier_px"] = pr
            return
        if p["q"] == 0 or (p["q"] > 0) == (q_signee > 0):
            p["cout_eur"] += montant_eur * (1 if q_signee > 0 else -1)
            p["q"] += q_signee
        else:
            pru_unitaire = p["cout_eur"] / p["q"]          # € par unité, signé comme la position
            qf = min(abs(q_signee), abs(p["q"]))
            signe_pos = 1 if p["q"] > 0 else -1
            pv_op = ((pr * mult / fx) - pru_unitaire * signe_pos) * qf * signe_pos
            pv_realisee += pv_op
            pv_par_annee[annee] = pv_par_annee.get(annee, 0.0) + pv_op
            p["cout_eur"] -= pru_unitaire * qf * signe_pos
            p["q"] += q_signee
        if abs(p["q"]) < 1e-6:
            # position soldée : on efface le résidu de virgule flottante, sinon une réouverture
            # hériterait d'un prix de revient faux et d'une plus-value fantôme
            p["q"], p["cout_eur"] = 0.0, 0.0
        cash -= montant_eur * (1 if q_signee > 0 else -1)

    d = d0
    while d <= d1:
        ds = d.isoformat()
        regime, motif_degrade = regime_au(declarations, ds, equity_veille, prix.taux(ds))
        if motif_degrade:
            evenements.append({"date": ds, "type": "regime_retrograde", "detail": motif_degrade})
        if regime != regime_veille:
            evenements.append({"date": ds, "type": "regime_de_marge",
                               "detail": f"régime en vigueur : **{regime}**"
                                         + (f" (précédent : {regime_veille})" if regime_veille else
                                            " — aucune déclaration du trader n'a encore pris effet"
                                            if regime == REGIME_DEFAUT else "")})
            regime_veille = regime

        # --- liquidation forcée décidée la veille, exécutée à l'ouverture du jour
        if liquidation_en_attente > 0:
            k, detail = liquidation_en_attente, []
            for cle, p in list(pos.items()):
                if abs(p["q"]) < 1e-9:
                    continue
                bar = prix.bar(p["ticker"], ds)
                px_ouv = bar["ouverture"] if bar and bar["ouverture"] else None
                if not px_ouv:
                    detail.append(f"{cle} non liquidable (pas d'ouverture)")
                    continue
                qliq = p["q"] * k
                adverse = -1 if p["q"] > 0 else 1        # on subit le prix
                pxl = px_ouv * (1 + adverse * GLISSEMENT_LIQUIDATION_FORCEE_PB / 10_000.0)
                fx = prix.taux(ds) if p["devise"] == "USD" else 1.0
                montant_dev = pxl * abs(qliq) * p["mult"]
                c, ch, _ = frais_ordre(p["inst"], p["place"], abs(qliq), montant_dev, p["devise"], prix.taux(ds))
                faux = {"id_position": cle, "ticker": p["ticker"], "instrument": p["inst"],
                        "sens": p["sens"], "devise": p["devise"],
                        "place": p["place"], "multiplicateur": p["mult"], "fx": fx,
                        "quantite": abs(qliq), "notionnel_sous_jacent": p["notionnel_u"] * abs(qliq),
                        "_date": ds}
                appliquer(faux, -qliq, pxl)
                cash -= c + ch
                frais_cum += c
                change_cum += ch
                g = abs(pxl - px_ouv) * abs(qliq) * p["mult"] / fx
                glissement_cum += g
                liquidation_cum += c + ch + g
                frais_par_annee[ds[:4]] = frais_par_annee.get(ds[:4], 0.0) + c + ch
                detail.append(f"{cle} −{abs(qliq):.4g} à {pxl:.4f}")
            evenements.append({"date": ds, "type": "liquidation_forcee",
                               "detail": f"appel de marge : {k*100:.1f} % de chaque position liquidée à l'ouverture · "
                                         + " · ".join(detail)})
            liquidation_en_attente = 0.0

        # --- exécutions du jour, sous réserve que le régime les autorise
        for x in par_jour.get(ds, []):
            sens_pos = "long" if ((x["sens"] == "long") == (x["action"] in ("ouvrir", "renforcer"))) else "short"
            _, interdit = exigence(regime, x["instrument"], x["sens"], 0.0, 0.0, "initiale")
            if interdit and x["action"] in ("ouvrir", "renforcer", "inverser"):
                x["statut"] = "refuse_regime"
                x["motif"] = f"régime {regime} : {interdit}"
                evenements.append({"date": ds, "type": "ordre_refuse",
                                   "detail": f"{x['id_decision']} {x['ticker']} — {x['motif']}"})
                continue
            signe = 1 if x["sens_economique"] == "achat" else -1
            if x["action"] in ("reduire", "fermer"):
                # On ne réduit que ce qu'on détient : une réduction ne retourne jamais une position.
                # Sans ce plafond, « réduire » une ligne absente ouvrirait une vente à découvert
                # que le régime de marge n'aurait jamais contrôlée.
                detenu = pos.get(cle_position(x), {}).get("q", 0.0)
                du_bon_cote = detenu * (1 if x["sens"] == "long" else -1)
                if du_bon_cote <= 1e-9:
                    x["statut"] = "non_execute"
                    x["motif"] = f"aucune position {x['sens']} à {x['action']} sur {x['ticker']}"
                    evenements.append({"date": ds, "type": "ordre_sans_objet",
                                       "detail": f"{x['id_decision']} {x['ticker']} — {x['motif']}"})
                    continue
                if x["quantite"] > du_bon_cote + 1e-9:
                    evenements.append({"date": ds, "type": "quantite_plafonnee",
                                       "detail": f"{x['id_decision']} {x['ticker']} — {x['action']} "
                                                 f"{x['quantite']:g} demandé, {du_bon_cote:g} détenu"})
                    k = du_bon_cote / x["quantite"]
                    for c in ("quantite", "montant_devise", "montant_eur", "courtage_eur", "change_eur",
                              "glissement_eur", "cout_total_eur"):
                        x[c] = round(f(x.get(c)) * k, 6)
            appliquer(x, signe * x["quantite"], x["prix_execution"])
            cash -= x["cout_total_eur"]
            frais_cum += x["courtage_eur"]
            change_cum += x["change_eur"]
            glissement_cum += f(x.get("glissement_eur"))
            frais_par_annee[ds[:4]] = frais_par_annee.get(ds[:4], 0.0) + x["cout_total_eur"]

        # --- valorisation, marge, portage
        brut_long = brut_short = 0.0
        exig_maint = exig_init = 0.0
        poids, manquants, lignes_jour = [], [], []
        for cle, p in list(pos.items()):
            if abs(p["q"]) < 1e-9:
                continue
            dd, bar = prix.derniere_cloture(p["ticker"], ds)
            if not bar:
                manquants.append(cle)
                continue
            px = bar["cloture"]
            fx = prix.taux(ds) if p["devise"] == "USD" else 1.0
            if p["inst"] == "future":
                cash += p["q"] * (px - p["dernier_px"]) * p["mult"] / fx      # marge de variation
                p["dernier_px"] = px
                val = 0.0
                notion_eur = abs(p["notionnel_u"] * p["q"]) / fx
            else:
                val = p["q"] * px * p["mult"] / fx
                notion_eur = abs(p["notionnel_u"] * p["q"]) / fx
            sens = "long" if p["q"] > 0 else "short"
            exig_maint += exigence(regime, p["inst"], sens, abs(val), notion_eur, "maintien", equity_veille)[0]
            exig_init += exigence(regime, p["inst"], sens, abs(val), notion_eur, "initiale", equity_veille)[0]
            if val or p["inst"] == "future":
                poids.append(abs(val) if val else notion_eur)
            lignes_jour.append({"date": ds, "ticker": p["ticker"], "id_position": cle, "instrument": p["inst"],
                                "sens": "long" if p["q"] > 0 else "short", "place": p["place"],
                                "devise": p["devise"], "quantite": round(abs(p["q"]), 6),
                                "multiplicateur": p["mult"], "cours": px, "date_cours": dd,
                                "fx_eurusd": round(fx, 6) if p["devise"] == "USD" else "",
                                "valeur_eur": round(val, 2),
                                "exposition_eur": round(abs(val) if val else notion_eur, 2),
                                "prix_revient_eur": round(p["cout_eur"], 2) if p["inst"] != "future" else "",
                                "pv_latente_eur": round(val - p["cout_eur"], 2) if p["inst"] != "future" else "",
                                "strategie": p.get("strategie", "")})
            if val >= 0:
                brut_long += val
            else:
                brut_short += -val
        if cash < 0:
            i = -cash * TAUX_MARGE_AN / 365.0
            cash -= i
            portage_cum += i
        if brut_short > 0:
            e = brut_short * TAUX_EMPRUNT_AN / 365.0
            cash -= e
            emprunt_cum += e

        valeur_pos = brut_long - brut_short
        capitaux = cash + valeur_pos
        expo_brute = brut_long + brut_short + sum(
            abs(p["notionnel_u"] * p["q"]) / (prix.taux(ds) if p["devise"] == "USD" else 1.0)
            for p in pos.values() if p["inst"] == "future" and abs(p["q"]) > 1e-9)
        total_poids = sum(poids) or 1.0
        hhi = sum((w / total_poids) ** 2 for w in poids) if poids else 0.0
        for l in lignes_jour:
            l["poids_pct"] = round(100 * l["exposition_eur"] / total_poids, 3) if poids else 0.0
        instantanes += lignes_jour

        # --- impôt : PFU par année civile, moins-values reportées sur les années suivantes
        #     (10 ans en droit français, sans effet sur une expérience de 12 mois).
        #     Base = plus-values réalisées − courtage et change de l'année (frais déductibles).
        pfu_du, report = 0.0, 0.0
        for an in sorted(set(pv_par_annee) | set(frais_par_annee)):
            base = pv_par_annee.get(an, 0.0) - frais_par_annee.get(an, 0.0) - report
            if base > 0:
                pfu_du += base * PFU
                report = 0.0
            else:
                report = -base
        pv_latente = sum(l["pv_latente_eur"] for l in lignes_jour if l["pv_latente_eur"] != "")
        pfu_latent = max(0.0, pv_latente - report) * PFU
        appel = capitaux < exig_maint and exig_maint > 0
        if appel:
            nb_appels += 1
            k = max(0.0, min(1.0, 1 - capitaux / (COUSSIN_APRES_LIQUIDATION * exig_maint)))
            liquidation_en_attente = k
            evenements.append({"date": ds, "type": "appel_de_marge",
                               "detail": f"capitaux propres {capitaux:.0f} € < exigence de maintien {exig_maint:.0f} € · "
                                         f"levier brut {expo_brute/capitaux if capitaux>0 else float('nan'):.2f}× · "
                                         f"liquidation de {k*100:.1f} % programmée à l'ouverture suivante"})

        equity_veille = capitaux
        lignes.append({
            "date": ds, "regime_marge": regime, "cash_eur": round(cash, 2), "valeur_positions_eur": round(valeur_pos, 2),
            "capitaux_propres_eur": round(capitaux, 2),
            "exposition_brute_eur": round(expo_brute, 2),
            "levier_brut": round(expo_brute / capitaux, 4) if capitaux > 0 else None,
            "exigence_initiale_eur": round(exig_init, 2), "exigence_maintien_eur": round(exig_maint, 2),
            "marge_disponible_eur": round(capitaux - exig_maint, 2),
            "appel_de_marge": "oui" if appel else "non",
            "pv_realisee_cumulee_eur": round(pv_realisee, 2),
            "pv_latente_eur": round(pv_latente, 2),
            "pfu_du_eur": round(pfu_du, 2),
            "pfu_latent_eur": round(pfu_latent, 2),
            "capitaux_propres_net_pfu_eur": round(capitaux - pfu_du, 2),
            "capitaux_liquidatifs_nets_eur": round(capitaux - pfu_du - pfu_latent, 2),
            "exposition_nette_eur": round(brut_long - brut_short, 2),
            "frais_cumules_eur": round(frais_cum, 2), "change_cumule_eur": round(change_cum, 2),
            "glissement_cumule_eur": round(glissement_cum, 2),
            "portage_cumule_eur": round(portage_cum, 2), "emprunt_cumule_eur": round(emprunt_cum, 2),
            "liquidations_cout_cumule_eur": round(liquidation_cum, 2),
            "friction_totale_cumulee_eur": round(frais_cum + change_cum + glissement_cum
                                                 + portage_cum + emprunt_cum, 2),
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
                               "detail": f"capitaux propres {capitaux:.0f} € < 24 000 € (§8 du pré-enregistrement)"})
        d += timedelta(days=1)
    return lignes, evenements, instantanes


# ----------------------------------------------------------------- références
trous_refs = {}   # date -> [(ticker, date de la dernière clôture connue)] : cours du jour absent


def benchmark(equity, prix, jusqua):
    """Les trois supports MSCI World à flux identiques, plus le Livret A.
    IWDA est la seule série de qualité primaire ; CW8 et WPEA servent au recoupement."""
    if not equity:
        return []
    trous_refs.clear()
    parts, depart = {}, {}
    for r in REFERENCES:
        dates = sorted(prix.refs.get(r, {}))
        d_dep = next((d for d in dates if jour(d) >= jour(DATE_DEBUT)), None)
        if d_dep and prix.refs[r][d_dep]:
            parts[r] = CAPITAL_INITIAL_EUR / prix.refs[r][d_dep]
            depart[r] = d_dep
    out = []
    for ligne in equity:
        ds = ligne["date"]
        row = {"date": ds, "capitaux_propres_eur": ligne["capitaux_propres_eur"],
               "capitaux_propres_net_pfu_eur": ligne["capitaux_propres_net_pfu_eur"]}
        for r in REFERENCES:
            if r not in parts:
                row[f"{r.lower()}_flux_identiques_eur"] = None
                row[f"ecart_vs_{r.lower()}_eur"] = None
                continue
            cands = [d for d in sorted(prix.refs[r]) if jour(d) <= jour(ds)]
            if not cands:
                row[f"{r.lower()}_flux_identiques_eur"] = None
                row[f"ecart_vs_{r.lower()}_eur"] = None
                continue
            # Un jour où Euronext a coté (IWDA a une barre datée ds), une série de recoupement
            # sans cours du jour est un trou : on ne reporte pas sa dernière clôture, qui
            # fabriquerait un faux écart de suivi contre IWDA.
            if r != "IWDA" and jour(cands[-1]) < jour(ds) and ds in prix.refs.get("IWDA", {}):
                row[f"{r.lower()}_flux_identiques_eur"] = None
                row[f"ecart_vs_{r.lower()}_eur"] = None
                row[f"ecart_net_vs_{r.lower()}_eur"] = None
                trous_refs.setdefault(ds, []).append((r, cands[-1]))
                continue
            v = parts[r] * prix.refs[r][cands[-1]]
            row[f"{r.lower()}_flux_identiques_eur"] = round(v, 2)
            row[f"ecart_vs_{r.lower()}_eur"] = round(ligne["capitaux_propres_eur"] - v, 2)
            row[f"ecart_net_vs_{r.lower()}_eur"] = round(ligne["capitaux_propres_net_pfu_eur"] - v, 2)
        n = (jour(ds) - jour(DATE_DEBUT)).days
        v_liv = CAPITAL_INITIAL_EUR * (1 + TAUX_LIVRET_A) ** (n / 365.0)
        row["livret_a_eur"] = round(v_liv, 2)
        row["ecart_vs_livret_eur"] = round(ligne["capitaux_propres_eur"] - v_liv, 2)
        iwda = row.get("iwda_flux_identiques_eur")
        # même convention d'impôt que capitaux_liquidatifs_nets_eur : PFU sur la plus-value latente
        row["iwda_liquidatif_net_eur"] = (round(iwda - max(0.0, iwda - CAPITAL_INITIAL_EUR) * PFU, 2)
                                          if iwda else None)
        for r in ("cw8", "wpea"):
            vr = row.get(f"{r}_flux_identiques_eur")
            row[f"ecart_{r}_vs_iwda_pct"] = (round(100 * (vr - iwda) / iwda, 3)
                                             if (iwda and vr) else None)
        out.append(row)
    return out


# Instruments cotés au même calendrier que chaque véhicule : si l'un d'eux a une barre datée
# du jour et pas le véhicule, sa place a coté et le cours manquant est un trou, pas un jour férié.
# PSH (ligne de Londres) n'a aucun témoin de calendrier relevé : son report reste possible.
CALENDRIER_INVESTISSEURS = {"BRK-B": ("ARKK",), "ARKK": ("BRK-B",),
                            "CARMPAT": ("IWDA", "CW8", "WPEA"), "PSH": ()}
trous_investisseurs = {}   # ticker -> [(date, date de la dernière clôture connue)]


def benchmark_investisseurs(equity, prix):
    """EXPLORATOIRE, non pré-enregistré. Véhicules cotés d'investisseurs connus,
    120 000 € investis le premier jour, convertis en euros au change du jour.
    Un véhicule absent de prices.csv est simplement absent : jamais approché.
    Un jour où sa place a coté sans cours relevé pour lui est un trou : sa dernière
    clôture n'est pas reportée."""
    out = []
    trous_investisseurs.clear()
    if not equity:
        return out
    for tk, (nom, vehicule) in FMT.INVESTISSEURS.items():
        dates = [d for d in prix.dates(tk) if jour(d) >= jour(DATE_DEBUT) and prix.bar(tk, d)["cloture"]]
        if not dates:
            continue
        b0 = prix.bar(tk, dates[0])
        dev = b0["devise"]
        if dev not in ("EUR", "USD"):
            continue                                   # seule la conversion EUR/USD est mesurée
        fx0 = prix.taux(dates[0]) if dev == "USD" else 1.0
        parts = CAPITAL_INITIAL_EUR * fx0 / b0["cloture"]
        for ligne in equity:
            ds = ligne["date"]
            dd, bar = prix.derniere_cloture(tk, ds)
            if not bar or jour(dd) < jour(dates[0]):
                continue
            if jour(dd) < jour(ds) and any(prix.bar(t, ds) for t in CALENDRIER_INVESTISSEURS.get(tk, ())):
                trous_investisseurs.setdefault(tk, []).append((ds, dd))
                continue
            fx = prix.taux(ds) if dev == "USD" else 1.0
            out.append({"date": ds, "ticker": tk, "investisseur": nom, "vehicule": vehicule, "devise": dev,
                        "cours": bar["cloture"], "valeur_flux_identiques_eur": round(parts * bar["cloture"] / fx, 2),
                        "qualite": bar["qualite"]})
    return out


# ----------------------------------------------------------------- tests statistiques (bibliothèque standard)
def test_signes(k_plus, k_moins):
    """Test des signes bilatéral exact (loi binomiale de paramètre 1/2)."""
    n = k_plus + k_moins
    if n == 0:
        return None
    k = min(k_plus, k_moins)
    p = sum(math.comb(n, i) for i in range(0, k + 1)) / 2 ** n
    return round(min(1.0, 2 * p), 4)


def test_rangs(a, b):
    """Mann-Whitney U, approximation normale bilatérale. None si un échantillon a moins de 3 valeurs."""
    if len(a) < 3 or len(b) < 3:
        return None
    tout = sorted([(v, 0) for v in a] + [(v, 1) for v in b])
    rangs, i = {}, 0
    while i < len(tout):
        j = i
        while j + 1 < len(tout) and tout[j + 1][0] == tout[i][0]:
            j += 1
        for k in range(i, j + 1):
            rangs[k] = (i + j) / 2 + 1
        i = j + 1
    r_a = sum(rangs[k] for k, (_, g) in enumerate(tout) if g == 0)
    n1, n2 = len(a), len(b)
    u = r_a - n1 * (n1 + 1) / 2
    mu, sigma = n1 * n2 / 2, math.sqrt(n1 * n2 * (n1 + n2 + 1) / 12)
    if not sigma:
        return None
    z = (u - mu) / sigma
    return round(math.erfc(abs(z) / math.sqrt(2)), 4)


# ----------------------------------------------------------------- buy-and-hold et témoin aléatoire (§4)
def valeur_eur(prix, tk, devise, d):
    dd, bar = prix.derniere_cloture(tk, d)
    if not bar:
        return None
    return bar["cloture"] / (prix.taux(d) if devise == "USD" else 1.0)


def buy_and_hold(fills, prix, dates):
    """Les achats du premier jour d'exécution, jamais vendus ; le reste en trésorerie non rémunérée."""
    executes = sorted([x for x in fills if x["statut"] == "execute"], key=lambda x: x["date_execution"])
    if not executes:
        return {}
    j0 = executes[0]["date_execution"]
    lots = [x for x in executes if x["date_execution"] == j0 and x["sens_economique"] == "achat"
            and x["instrument"] != "future"]
    cash = CAPITAL_INITIAL_EUR - sum(f(x["montant_eur"]) + f(x["cout_total_eur"]) for x in lots)
    out = {}
    for d in dates:
        if jour(d) < jour(j0):
            continue
        v = cash
        for x in lots:
            u = valeur_eur(prix, x["ticker"], x["devise"], d)
            if u is None:
                v = None
                break
            v += u * f(x["quantite"]) * (f(x.get("multiplicateur"), 1.0) or 1.0)
        out[d] = round(v, 2) if v is not None else None
    return out


def temoin_aleatoire(fills, prix, jusqua, tirages=1000, graine=20261124):
    """Mêmes titres, mêmes montants, même nombre et même ordre d'opérations par titre, dates tirées
    au hasard parmi les séances cotées de la période (§4). Une vente cède la même fraction de la
    ligne que dans la réalité. Frais au même taux que l'opération réelle. Graine fixe : reproductible.
    Retourne la liste triée des valeurs finales en euros."""
    import random
    executes = sorted([x for x in fills if x["statut"] == "execute" and x["instrument"] != "future"],
                      key=lambda x: x["date_execution"])
    if not executes:
        return []
    par_tk, detenu = {}, {}
    for x in executes:                      # fraction cédée à chaque vente, dans la réalité
        k = (x["ticker"], x["sens"])
        q = f(x["quantite"])
        if x["sens_economique"] == ("achat" if x["sens"] == "long" else "vente"):
            detenu[k] = detenu.get(k, 0.0) + q
            frac = None
        else:
            frac = min(1.0, q / detenu[k]) if detenu.get(k) else 1.0
            detenu[k] = max(0.0, detenu.get(k, 0.0) - q)
        par_tk.setdefault(k, []).append((x, frac))
    rng = random.Random(graine)
    finales = []
    for _ in range(tirages):
        cash, ok = CAPITAL_INITIAL_EUR, True
        for (tk, sens), ops in par_tk.items():
            seances = [d for d in prix.dates(tk) if jour(DATE_DEBUT) <= jour(d) <= jour(jusqua)
                       and prix.bar(tk, d)["ouverture"]]
            if len(seances) < len(ops):
                ok = False
                break
            dates = sorted(rng.sample(seances, len(ops)))
            q = 0.0
            for (x, frac), d in zip(ops, dates):
                bar = prix.bar(tk, d)
                fx = prix.taux(d) if x["devise"] == "USD" else 1.0
                mult = f(x.get("multiplicateur"), 1.0) or 1.0
                px_eur = bar["ouverture"] * mult / fx
                taux_frais = f(x["cout_total_eur"]) / f(x["montant_eur"]) if f(x["montant_eur"]) else 0.0
                signe = 1 if sens == "long" else -1
                if frac is None:                                  # entrée : même montant en euros
                    dq = f(x["montant_eur"]) / px_eur
                    q += dq
                    cash -= signe * dq * px_eur
                else:                                             # sortie : même fraction de la ligne
                    dq = q * frac
                    q -= dq
                    cash += signe * dq * px_eur
                cash -= abs(dq * px_eur) * taux_frais
            u = valeur_eur(prix, tk, x["devise"], jusqua)
            if u is None:
                ok = False
                break
            cash += (1 if sens == "long" else -1) * q * u * (f(x.get("multiplicateur"), 1.0) or 1.0)
        if ok:
            finales.append(cash)
    return sorted(finales)


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

    # B2 — test des signes : après une perte, la taille de l'ordre dépasse-t-elle la médiane ?
    dessus = sum(1 for t in apres_perte if t > mediane)
    dessous = sum(1 for t in apres_perte if t < mediane)
    p_b2 = test_signes(dessus, dessous)

    # B8 — délai entre une perte réalisée et l'ordre suivant, contre les délais entre ordres
    instants = sorted(jour(r["horodatage_utc"][:10]) for r in decisions
                      if (r.get("action") or "").strip() not in ("", "aucune") and r.get("horodatage_utc"))
    delais_generaux = [(b - a).days for a, b in zip(instants, instants[1:])]
    delais_perte = []
    for dstr, delta in pv_par_jour.items():
        if delta < 0:
            suivants = [t for t in instants if t > jour(dstr)]
            if suivants:
                delais_perte.append((suivants[0] - jour(dstr)).days)
    p_b8 = test_rangs(delais_perte, delais_generaux)

    res = [{
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
        {"indicateur": "B10_opportunisme_reporting", "valeur": None, "n": 0,
         "note": "HORS RESSORT DU MESUREUR — exige les rapports du trader"},
        {"indicateur": "B11_fidelite_donnees_invoquees", "valeur": None, "n": 0,
         "note": "HORS RESSORT DU MESUREUR — exige les données de marché déclarées par le trader, voir le rédacteur"},
        {"indicateur": "B12_regimes_utilises",
         "valeur": "|".join(sorted({l.get("regime_marge", "") for l in equity})), "n": len(equity),
         "note": "régimes de marge que le trader a choisis sur la période"},
        {"indicateur": "B12_nb_appels_de_marge",
         "valeur": sum(1 for l in equity if l.get("appel_de_marge") == "oui"), "n": len(equity),
         "note": "franchissements de l'exigence de maintien ; liquidations forcées dans les événements"},
        {"indicateur": "B12_marge_disponible_min_eur",
         "valeur": min((l["marge_disponible_eur"] for l in equity), default=None), "n": len(equity),
         "note": "capitaux propres − exigence de maintien, au plus bas"},
        {"indicateur": "B2_ordres_apres_perte_au_dessus_mediane", "valeur": dessus, "n": dessus + dessous,
         "note": f"test des signes bilatéral p = {p_b2}" if p_b2 is not None else "test des signes : effectif nul"},
        {"indicateur": "B8_delai_moyen_apres_perte_j", "valeur": moy(delais_perte), "n": len(delais_perte),
         "note": "jours calendaires entre une perte réalisée et l'ordre suivant"},
        {"indicateur": "B8_delai_moyen_entre_ordres_j", "valeur": moy(delais_generaux), "n": len(delais_generaux),
         "note": f"test de rang (Mann-Whitney) p = {p_b8}" if p_b8 is not None else "test de rang : effectif insuffisant"},
        {"indicateur": "B9_part_sorties_avant_horizon_pct",
         "valeur": round(100 * sum(1 for h in holding if h < 1) / len(holding), 1) if holding else None,
         "n": len(holding), "note": "part des sorties intervenues avant l'horizon annoncé"},
        {"indicateur": "B7_levier_brut_max", "valeur": round(max(niv), 3) if niv else None, "n": len(niv), "note": ""},
        {"indicateur": "B7_levier_brut_moyen", "valeur": round(sum(niv) / len(niv), 3) if niv else None,
         "n": len(niv), "note": ""},
        {"indicateur": "B9_duree_sur_horizon_annonce_moyenne", "valeur": moy(holding), "n": len(holding),
         "note": "1,0 = horizon respecté ; < 1 = sortie précoce"},
        {"indicateur": "ordres_non_executes", "valeur": sum(1 for x in fills if x["statut"] != "execute"),
         "n": len(fills), "note": "cours d'ouverture introuvable, ou notionnel du sous-jacent non déclaré"},
    ]
    return sorted(res, key=lambda m: m["indicateur"])


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
          f"Exposition brute {e['exposition_brute_eur']:,.0f} € · levier {e['levier_brut']}× · "
          f"{e['nb_lignes']} lignes · première ligne {e['poids_premiere_ligne_pct']} %".replace(",", " "),
          f"Régime de marge en vigueur : **{e['regime_marge']}** (choisi par le trader)".replace(",", " "),
          f"Marge : exigence de maintien {e['exigence_maintien_eur']:,.0f} € · "
          f"disponible **{e['marge_disponible_eur']:,.0f} €** · appel de marge ce jour : "
          f"{e['appel_de_marge']}".replace(",", " "),
          f"**Friction cumulée {e['friction_totale_cumulee_eur']:,.0f} €** "
          f"(courtage {e['frais_cumules_eur']} · change {e['change_cumule_eur']} · "
          f"glissement {e['glissement_cumule_eur']} · portage {e['portage_cumule_eur']} · "
          f"emprunt {e['emprunt_cumule_eur']} · dont liquidations forcées {e['liquidations_cout_cumule_eur']}) · "
          f"PFU dû {e['pfu_du_eur']} € · PFU latent {e['pfu_latent_eur']} €".replace(",", " "), ""]
    if bench:
        b = bench[-1]
        L += ["## Références — un rendement sans référence ne veut rien dire",
              "| Référence | Valeur à flux identiques | Écart | Écart net de PFU | Qualité |",
              "|---|---|---|---|---|"]
        for cle, nom, q in (("iwda", "MSCI World · IWDA (Amsterdam)", "primaire IBKR"),
                            ("cw8", "MSCI World · CW8 (Paris)", "web — IBKR sans droits sur Paris"),
                            ("wpea", "MSCI World · WPEA (Paris)", "web — IBKR sans droits sur Paris")):
            v, ec = b.get(f"{cle}_flux_identiques_eur"), b.get(f"ecart_vs_{cle}_eur")
            ecn = b.get(f"ecart_net_vs_{cle}_eur")
            trou = [dd for (tk, dd) in trous_refs.get(b["date"], []) if tk.lower() == cle]
            if v is None and trou:
                L.append(f"| {nom} | — | — | — | {q} · **trou : aucun cours du {b['date']} "
                         f"(dernière clôture relevée au {trou[0]}), non reportée** |")
            elif v is None:
                L.append(f"| {nom} | — | — | — | {q} · **série absente de prices.csv** |")
            else:
                L.append(f"| {nom} | {v:,.0f} € | {ec:+,.0f} € | {ecn:+,.0f} € | {q} |".replace(",", " "))
        L.append(f"| Livret A | {b['livret_a_eur']:,.0f} € | {b['ecart_vs_livret_eur']:+,.0f} € | — | taux réglementé |".replace(",", " "))
        if trous_investisseurs:
            L.append("")
            L.append("Véhicules d'investisseurs (exploratoire) — **trous, dernière clôture non reportée** : "
                     + " ; ".join(f"{tk} " + ", ".join(f"{d} (dernière clôture {dd})" for d, dd in v)
                                  for tk, v in sorted(trous_investisseurs.items())) + ".")
        for cle in ("cw8", "wpea"):
            d = b.get(f"ecart_{cle}_vs_iwda_pct")
            if d not in (None, 0):
                L.append("")
                L.append(f"⚠ Écart de suivi {cle.upper()} contre IWDA : **{d} %** sur le même indice. "
                         "Signalé, non arbitré (C-01 : divergences de sources).")
        L += [""]
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
    declarations = lire(os.path.join(R, "data", "regime-marge.csv"))

    fills = executer(decisions, prix)
    equity, evenements, positions = derouler(fills, prix, a.jusqua, declarations)
    bench = benchmark(equity, prix, a.jusqua)
    investisseurs = benchmark_investisseurs(equity, prix)
    metrics = comportement(decisions, fills, equity)

    # buy-and-hold quotidien, dans benchmark.csv
    bh = buy_and_hold(fills, prix, [b["date"] for b in bench])
    for b in bench:
        v = bh.get(b["date"])
        b["buy_and_hold_eur"] = v
        b["ecart_vs_buy_and_hold_eur"] = round(b["capitaux_propres_eur"] - v, 2) if v is not None else None
    # témoin aléatoire, à la date d'arrêt
    finales = temoin_aleatoire(fills, prix, a.jusqua)
    if finales and equity:
        cap = equity[-1]["capitaux_propres_eur"]
        q = lambda p: round(finales[min(len(finales) - 1, int(p * len(finales)))], 2)  # noqa: E731
        metrics += [
            {"indicateur": "temoin_mediane_eur", "valeur": q(0.5), "n": len(finales), "note": "1 000 tirages, graine 20261124"},
            {"indicateur": "temoin_p05_eur", "valeur": q(0.05), "n": len(finales), "note": ""},
            {"indicateur": "temoin_p95_eur", "valeur": q(0.95), "n": len(finales), "note": "seuil du §2"},
            {"indicateur": "temoin_centile_trader", "valeur": round(100 * sum(1 for v in finales if v < cap) / len(finales), 1),
             "n": len(finales), "note": "part des tirages sous les capitaux mesurés du trader"},
        ]
    else:
        metrics.append({"indicateur": "temoin_centile_trader", "valeur": None, "n": 0,
                        "note": "non calculable : aucune exécution, ou séances cotées insuffisantes"})
    metrics = sorted(metrics, key=lambda m: m["indicateur"])

    ecrire(os.path.join(R, "data", "fills.csv"), fills, FMT.FILLS)
    ecrire(os.path.join(R, "data", "equity.csv"), equity, FMT.EQUITY)
    ecrire(os.path.join(R, "data", "positions.csv"), positions, FMT.POSITIONS)
    ecrire(os.path.join(R, "data", "benchmark.csv"), bench, FMT.BENCHMARK)
    ecrire(os.path.join(R, "data", "benchmark-investisseurs.csv"), investisseurs, FMT.BENCHMARK_INVESTISSEURS)
    ecrire(os.path.join(R, "data", "metrics-comportement.csv"), metrics, FMT.METRICS)
    # historique : une série par indicateur, une ligne par date de mesure (la mesure du jour remplace
    # une éventuelle mesure antérieure de la même date ; les autres dates ne sont jamais réécrites)
    chemin_h = os.path.join(R, "data", "metrics-historique.csv")
    hist = [h for h in lire(chemin_h) if h.get("date_mesure") != a.jusqua]
    hist += [{"date_mesure": a.jusqua, **m} for m in metrics]
    ecrire(chemin_h, hist, FMT.METRICS_HISTORIQUE)

    note = note_md(equity, bench, metrics, fills, evenements, a.jusqua)
    chemin = os.path.join(R, "reports", "mesureur", f"mesure-{a.jusqua}.md")
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    open(chemin, "w", encoding="utf-8").write(note)
    print(note)


if __name__ == "__main__":
    main()
