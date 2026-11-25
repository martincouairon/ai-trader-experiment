# Rapport d'expérience — Trader IA

> Source de la prose du rapport publié sur https://martincouairon.github.io/projects/trader-ia.html.
> Un titre `## <id>` par zone `<!-- TEXTE:<id> -->` des pages. Les chiffres, figures et tableaux ne sont pas ici :
> la page les trace depuis `donnees.json`, produit par `tools/publication.py`. Voir `agents/30-redacteur.md`.

## resume

Nous voulons savoir comment un agent d'IA gère un portefeuille lorsqu'aucune contrainte de levier, de concentration ou de rotation ne lui est imposée, et s'il mesure correctement sa propre performance.

L'agent décide trois fois par jour ouvré sur un portefeuille notionnel de 120 000 € et tient sa propre comptabilité. Un second agent, sans accès à cette comptabilité ni au raisonnement du premier, établit une comptabilité de référence à partir du registre d'ordres et des prix de marché. Nous mesurons l'écart entre les deux comptabilités, douze indicateurs de comportement, les coûts et l'impôt, et la performance comparée au MSCI World, au Livret A, à un témoin aléatoire et à quatre véhicules d'investisseurs connus.

État au 22 novembre 2026 : l'expérience n'a pas commencé. La première décision est fixée au 24 novembre 2026. Aucune mesure n'est disponible.

## auto-mesure

Aucune donnée à ce jour.

## performance

Aucune donnée à ce jour.

## composition

Aucune donnée à ce jour.

## risque

Aucune donnée à ce jour. Les ratios ne sont calculés qu'à partir de vingt séances.

## couts

Aucune donnée à ce jour.

## comportement

Aucune donnée à ce jour.

## charte

Le trader rédige sa charte (stratégie, règles, critères de sortie) au premier jour. Chaque règle est citée ici avec sa date, et chaque décision qui la contredit est comptée (B4). La charte n'est pas encore écrite.

## limites

- Sur douze mois, un écart de rendement, positif ou négatif, ne permet pas de conclure à une compétence ou à une incompétence.
- Un gain ou une perte est considéré comme indiscernable du hasard tant que le résultat du trader ne dépasse pas le 95ᵉ centile du témoin aléatoire.
- L'expérience ne permet pas d'établir de règle d'investissement. Rien dans ce rapport n'est une recommandation.
- Aucune prédiction n'a été déposée avant le premier ordre ; les résultats ne sont comparés à aucune attente.
- Les analyses qui ne figuraient pas au pré-enregistrement sont signalées comme exploratoires.

## confusion

- Connu avant le départ : CW8, WPEA et Carmignac Patrimoine sont relevés sur le web (qualité « web horodaté »), le connecteur Interactive Brokers n'ayant pas de droits de données sur Euronext Paris.
- Connu avant le départ : les véhicules d'investisseurs ne reproduisent pas le portefeuille de leur gérant. Berkshire Hathaway est une holding qui détient aussi des sociétés non cotées ; Pershing Square Holdings cote avec une décote sur sa valeur d'actif.
- 2026-11-26 — Changement de prompt en cours d'expérience : à partir de la fenêtre de 13h08 UTC, le trader peut lire des cours sur Interactive Brokers (outils de lecture de prix uniquement) et appliquer lui-même la règle du pupitre pour savoir si un ordre a été servi. Auparavant, il ne disposait que de sources web, souvent périmées ou non datées. Les écarts de prix déclarés (D1, B11) avant et après cette date ne sont pas directement comparables. Le pré-enregistrement n'est pas modifié : son §6 donnait déjà au trader accès aux données de marché publiques.

## journal

- 2026-11-22 — Page créée, avant le premier ordre. Aucune donnée.
- 2026-11-22 — Ébauche de mise en forme, sans données.
- 2026-11-22 — Refonte en rapport : figures tracées depuis un jeu de données unique, page des décisions. Aucune donnée.
- 2026-11-22 — Rédaction simplifiée ; pages Calculs et Données ; ajout du témoin aléatoire, du buy-and-hold et des indicateurs B2 (test), B8, B10 et B11 calculés automatiquement. Aucune donnée.

## synthese-decisions

Aucune décision à ce jour. La première est fixée au 24 novembre 2026.
