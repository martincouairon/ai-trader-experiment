# AI Trader Experiment — un agent sans contraintes, mesuré par un autre

**Ceci n'est pas un conseil en investissement. Aucun argent réel n'est engagé. Aucun ordre n'est transmis à un courtier.**

Ce dépôt est le journal public d'une expérience : on laisse un agent d'IA décider librement d'investissements, chaque jour, sur un portefeuille **notionnel** de 100 000 €, et on mesure ce qu'il fait avec un second agent qui n'a pas accès à son raisonnement.

La question posée n'est pas « est-ce que l'IA sait investir ? ». Sur un an, cette question n'a pas de réponse statistiquement valide, et le protocole l'écrit noir sur blanc avant de commencer. La question est : **que fait un agent à qui on retire les garde-fous, et à qui on dit que sa performance est ce qui compte ?**

## Les trois agents

| Agent | Rôle | Ce qu'il voit | Ce qu'il ne voit pas |
|---|---|---|---|
| **Trader** (`agents/10-trader.md`) | décide chaque jour, sans aucune contrainte d'instrument, de levier ou de concentration, **et tient sa propre comptabilité** | ses décisions passées, **ses propres livres**, le marché, l'actualité | **la comptabilité du mesureur**, et toute analyse de son comportement |
| **Mesureur** (`agents/20-mesureur.md`) | applique la convention d'exécution, valorise, calcule tous les indicateurs | le registre d'ordres et les prix | **le raisonnement du trader, ses rapports et sa comptabilité** |
| **Rédacteur** (`agents/30-redacteur.md`) | assemble le rapport d'expérience | les sorties du mesureur comme faits, la prose du trader comme pièce à conviction | — |

## Les règles qui rendent l'expérience lisible

1. **Deux comptabilités avancent en parallèle, et aucune ne voit l'autre.** Le trader tient ses livres — y compris ses hypothèses de prix d'exécution, ses valorisations et ses coûts. Le mesureur tient la référence à partir du seul registre d'ordres et des prix réels. **La divergence entre les deux est l'indicateur phare de l'expérience** (B5), publiée en série quotidienne et décomposée en quatre sources : hypothèses d'exécution, valorisation, coûts omis, arithmétique. Le trader ne reçoit jamais le relevé du mesureur — s'il le recevait, il le recopierait et le biais s'annulerait par construction.
2. **Aucun backtest.** L'expérience avance en temps réel uniquement. Un agent avec accès au web ne peut pas être empêché de savoir ce qui s'est produit sur une date passée.
3. **Append-only.** Un commit horodaté par décision, jamais de `force-push`, jamais de réécriture d'une ligne publiée. L'historique git **est** la piste d'audit.
4. **Le rendement brut ne vaut rien seul.** Toute performance est publiée contre l'indice monde à flux identiques, contre le Livret A, et contre un témoin aléatoire.
5. **Le trader choisit son levier, le courtier fixe ses exigences.** Il déclare son régime de marge — compte espèces, Reg-T ou Portfolio Margin — et le protocole ne lui impose aucun plafond. En revanche les exigences de chaque régime sont celles d'un vrai courtier : seuil d'éligibilité, majoration de concentration, délai de 2 jours pour changer de régime, appel de marge avec liquidation forcée, et perte du Portfolio Margin sous 100 000 $.
6. **Les frais, le change, le portage du levier, le coût d'emprunt des titres vendus à découvert et l'impôt sont modélisés.** Un carnet levé sans coût de financement a l'air brillant : c'est le premier gisement de faux alpha.
7. **Aucun agent n'a accès à un outil de passage d'ordre.** Jamais, dans aucun bras, même « pour tester ».

## Ce qui limite le trader, et ce qui ne le limite pas

**[`LIMITES-DU-TRADER.md`](LIMITES-DU-TRADER.md) en donne l'inventaire exhaustif**, limites discutables incluses. En résumé : quatre contraintes seulement pèsent réellement sur ses décisions, et **la plus lourde de loin est la cadence quotidienne, qui exclut tout l'intraday**. Tout le reste est soit la mécanique d'un vrai courtier (marge, portage, appel de marge, frais, impôt), soit la plomberie sans laquelle il n'y a pas de mesure (append-only, traçabilité des données, aveuglement réciproque).

Ne sont **pas** limités : le levier (il choisit son régime), la concentration, les instruments, la géographie, la rotation, l'obligation de justifier, de diversifier ou de se couvrir. Personne ne révise ses décisions et rien ne pénalise son risque.

## Comment ça tourne, et comment le vérifier

Le dossier [`runner/`](runner/) publie **le mécanisme d'exécution lui-même** : les prompts verbatim des trois tâches planifiées, les horaires, et pourquoi le trader et le mesureur tournent dans deux sessions distinctes à neuf heures d'intervalle plutôt que dans une seule.

```
python3 runner/verifier-protocole.py
```

Six contrôles mécaniques, exécutables par n'importe qui : le pré-enregistrement n'a pas bougé depuis le premier ordre, aucune ligne de données n'a été retirée, les schémas sont intacts, aucune prédiction n'a été glissée après coup, le mesureur n'a pas touché aux fichiers qui lui sont interdits, et aucun outil de passage d'ordre n'est utilisé nulle part.

## Résultats

Le graphique central est la **courbe à deux séries** : capitaux propres déclarés par le trader contre capitaux propres mesurés indépendamment, avec l'aire entre les deux ventilée par source de divergence.

Les indicateurs primaires sont **comportementaux** (`data/metrics-comportement.csv`) et saturent vers le troisième mois. Les indicateurs de rendement sont secondaires et explicitement sous-dimensionnés : voir la section « Puissance statistique » du `PROTOCOL.md`.

Le pré-enregistrement (`PRE-REGISTRATION.md`) est figé avant le premier ordre et n'est jamais modifié. Tout ce qui n'y figure pas est, par construction, une analyse exploratoire.

## Avertissement

Rien dans ce dépôt ne constitue une recommandation personnalisée, une offre, ou une incitation à investir. Les décisions publiées sont produites par un modèle de langage auquel on a délibérément retiré ses garde-fous, dans le cadre d'une expérience sur son comportement. **Les suivre serait une très mauvaise idée, et c'est en partie ce que l'expérience cherche à documenter.** Investir comporte un risque de perte en capital.
