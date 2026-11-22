# Rapport d'expérience — Trader IA

> Source de la prose du rapport publié sur https://martincouairon.github.io/projects/trader-ia.html.
> Un titre `## <id>` par zone `<!-- TEXTE:<id> -->` des pages. Les chiffres, figures et tableaux ne sont pas ici :
> la page les trace depuis `donnees.json`, produit par `tools/publication.py`. Voir `agents/30-redacteur.md`.

## resume

Un agent d'IA gère seul un portefeuille notionnel de 120 000 €, sans plafond de levier, de concentration ni de rotation. Il tient lui-même sa comptabilité ; un second agent, qui n'a jamais accès ni à ses comptes ni à son raisonnement, établit la mesure de référence à partir du seul registre d'ordres. L'écart entre les deux comptabilités est l'objet principal de l'étude : il dit si l'agent se mesure honnêtement, et par quel mécanisme il se trompe quand il se trompe. La performance, elle, est rapportée contre l'indice monde, le Livret A et quelques investisseurs connus, mais elle ne prouvera rien : douze mois sont trop courts pour distinguer le talent du hasard.

**État au 22 novembre 2026 : l'expérience n'a pas commencé.** La première décision est fixée au 24 novembre. Toutes les figures ci-dessous attendent leurs données.

## auto-mesure

C'est le résultat que l'expérience a été conçue pour produire, et il passe avant la performance. Deux courbes : ce que le trader croit valoir, ce qu'il vaut. L'aire qui les sépare est un biais ; sa décomposition dit d'où il vient. Un biais nul est un résultat. Un biais systématiquement favorable au trader en est un autre.

## performance

La performance est lue base 100, à flux identiques : chaque référence reçoit 120 000 € le même jour que le trader. Le Livret A sert de taux sans risque. Les investisseurs connus sont représentés par leur véhicule coté — Berkshire Hathaway pour Warren Buffett, Pershing Square Holdings pour Bill Ackman, ARK Innovation pour Cathie Wood, Carmignac Patrimoine pour Édouard Carmignac. Un véhicule n'est pas un portefeuille : c'est un repère public, et la comparaison est exploratoire.

## composition

Le portefeuille est décrit par la part de chaque ligne dans l'exposition brute, jour après jour. La stratégie est celle que le trader déclare pour chaque ordre, dans un vocabulaire fermé de quatorze étiquettes ; elle est reportée sur les positions qu'il détient. La composition est mesurée, l'étiquette est déclarée : une dérive entre la stratégie annoncée dans la charte et celle qui pèse réellement dans le carnet se lit ici.

## risque

Un rendement brut ne vaut rien seul. Le tableau le décline en trois couches — avant frais, net de frais, net d'impôt — puis le rapporte au risque pris pour l'obtenir. Les mesures marquées _pré-enregistré_ figuraient au protocole avant le premier ordre ; les autres ont été ajoutées ensuite et ne sont qu'exploratoires. Aucun ratio n'est calculé avant vingt séances : en dessous, il ne mesure que du bruit.

## couts

Un carnet sans frais a toujours l'air brillant : c'est le premier gisement de faux alpha. Chaque poste est suivi en euros et en points de rendement, côté mesure et côté trader. Un poste que le trader ne tient pas est en lui-même une information — il alimente directement D3.

## comportement

Les indicateurs comportementaux sont les résultats primaires de l'expérience. Ils sont publiés tels que le mesureur les calcule, y compris ceux qui ne sont pas encore calculables. B6 et B11 — la vérifiabilité du raisonnement et la fidélité des données invoquées — sont établis par le rédacteur, seul à pouvoir lire à la fois ce que le trader dit avoir vu et ce qui était réellement coté.

## charte

Au premier jour, le trader écrit sa propre charte : sa stratégie, ses règles, ce qui le ferait sortir d'une position. Personne ne la lui impose et personne ne la lui fera respecter. Chaque règle sera citée ici, datée, en regard de ce qui a été fait ; chaque violation compte pour B4.

_La charte n'est pas encore écrite._

## discussion

Ce que ce rapport ne pourra pas conclure est fixé d'avance, et c'est ce qui l'empêche de dériver vers le récit.

- **Aucune conclusion de compétence ne peut être tirée du rendement**, quel qu'il soit : sur douze mois, la puissance statistique ne le permet pas.
- Un gain comme une perte reste indiscernable du hasard tant que le témoin aléatoire n'est pas franchi au-delà du 95ᵉ centile.
- Aucune règle d'investissement ne peut être tirée de l'expérience, et rien ici n'est une recommandation.
- Le résultat ne peut être comparé à aucune attente : aucune prédiction n'a été déposée avant le premier ordre, délibérément.
- Toute analyse qui ne figurait pas au pré-enregistrement est étiquetée _exploratoire_.

## confusion

- **Connu avant le départ — places sans prix primaire.** CW8, WPEA et Carmignac Patrimoine ne sont disponibles qu'en qualité web horodatée : le connecteur Interactive Brokers n'a aucun droit de données sur Euronext Paris.
- **Connu avant le départ — véhicules d'investisseurs.** Berkshire Hathaway est une holding industrielle autant qu'un portefeuille ; Pershing Square Holdings cote avec une décote sur sa valeur d'actif. Le repère est public, pas fidèle.
        

_Les changements de modèle, les trous de données, les ordres non exécutés faute de prix et les autres événements journalisés seront ajoutés ici, datés._

## journal

- 2026-11-22 — Page créée, avant le premier ordre. Aucune donnée.
- 2026-11-22 — Ébauche de mise en forme, sans données.
- 2026-11-22 — Refonte en rapport : structure académique, figures tracées depuis un jeu de données unique, registre des décisions sur une page dédiée. Aucune donnée.

## synthese-decisions

Cette page tient deux registres en regard. Le premier est celui du trader : ce qu'il a décidé, pourquoi, sur quel fait. Le second est celui du mesureur : à quel prix l'ordre a réellement été servi, ce qu'il a coûté, ou pourquoi il ne l'a pas été. Le motif est cité tel que le trader l'a écrit, entre guillemets : c'est une pièce, pas un fait. Le raisonnement complet de chaque fenêtre est lié à sa source.

Chaque semaine, cette synthèse résumera les grandes lignes du raisonnement du trader — les thèses qu'il installe, celles qu'il abandonne, les justifications qui reviennent — sans les juger.

_Aucune décision avant le 24 novembre 2026._
