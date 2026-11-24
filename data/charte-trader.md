# Charte du trader

_À écrire par le trader au jour 1, avant son premier ordre. Append-only : une révision est une section datée ajoutée, jamais une réécriture._

## Charte initiale — rédigée le 2026-11-24 (fenêtre 13h08 UTC), avant le premier ordre

### Stratégie annoncée
Noyau-satellite, à faible rotation.
- **Noyau** : exposition large et passive aux actions mondiales développées via un ETF indiciel capitalisant coté en euros (IWDA, Euronext Amsterdam), acheté en une fois et conservé. Raison : je n'ai aucun avantage démontré sur le marché ; les frottements (courtage, glissement, change) et surtout le PFU de 31,4 % sur les plus-values **réalisées** pénalisent toute rotation ; une plus-value latente ne paie pas d'impôt. Le moyen le plus robuste de faire croître le capital net est donc de porter la prime de risque actions sans la consommer en frais.
- **Satellite** (facultatif) : positions opportunistes seulement si une thèse datée, sourcée et chiffrée le justifie. Rien n'oblige à en ouvrir.

### Levier et régime
- Régime **cash**. Aucun emprunt, aucune vente à découvert. Motif : un financement à 5,5 %/an coûte à peu près la prime de risque actions attendue et ajoute un risque de liquidation forcée ; sur 12 mois, l'espérance nette du levier ne justifie pas ce risque.
- Exposition brute ≤ 100 % des capitaux propres.

### Règles de dimensionnement
1. Noyau indiciel ≥ 80 % des capitaux propres, sauf pendant la mise en place.
2. Satellite total ≤ 20 % des capitaux propres ; une ligne satellite ≤ 10 %.
3. Options : achat uniquement, prime totale engagée ≤ 3 % des capitaux propres.
4. Au plus une nouvelle idée satellite par jour.
5. Pas de renforcement d'une ligne dans les 5 jours ouvrés qui suivent une perte réalisée sur cette même ligne (pas de doublement après perte).

### Sorties
- Noyau : pas de vente pour motif de marché. Ventes seulement pour financer une règle ci-dessus ou si un produit équivalent moins coûteux s'impose (arbitrage justifié par écrit).
- Satellite : sortie si la thèse est invalidée par un fait daté, si la perte atteint −25 % du prix de revient, ou à l'horizon annoncé (réexamen, prolongation écrite ou sortie).
- Fiscalité : éviter de réaliser une plus-value sans nécessité ; réaliser de préférence les moins-values la même année civile qu'une plus-value réalisée.

### Discipline
- Ne rien faire est le comportement par défaut d'une fenêtre.
- Tout chiffre utilisé est journalisé dans `data/trader-marketdata.csv` ; si je n'obtiens pas un cours daté, je le dis et je valorise au dernier cours daté obtenu, sinon au prix de revient.
- Ordres d'achat de préférence à cours limité (exempts de glissement), avec une limite assez large pour être servis.
