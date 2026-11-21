# Comment l'expérience tourne réellement

Ce dossier rend public **le mécanisme d'exécution**, pas seulement les règles. Les prompts ci-dessous sont ceux qui sont réellement envoyés aux agents, verbatim.

## Le dispositif

Les trois agents sont des sessions **Claude** distinctes, déclenchées par des tâches planifiées. Chacune est une session neuve, sans mémoire de la précédente : tout ce qu'un agent sait de son passé, il le lit dans les fichiers de ce dépôt. C'est ce qui rend l'expérience reproductible et auditable — et c'est aussi ce qui rend l'aveuglement mécanique plutôt que déclaratif.

| Tâche | Quand | Agent | Prompt |
|---|---|---|---|
| Décision | chaque jour ouvré, **13h00 UTC**, avant l'ouverture américaine | trader | `tache-trader.md` |
| Mesure | chaque jour ouvré, **22h30 UTC**, après la clôture américaine | mesureur | `tache-mesureur.md` |
| Réconciliation et rapport | le 1er de chaque mois | rédacteur | `tache-mensuelle.md` |

**Deux tâches séparées plutôt qu'une seule session qui jouerait les deux rôles** : c'est le point de conception le plus important du dispositif. Une seule session verrait les deux comptabilités et l'aveuglement ne reposerait plus que sur sa discipline. Deux sessions distinctes, à neuf heures d'intervalle, avec des listes de fichiers d'entrée disjointes, le rendent structurel.

## Le décalage d'une séance

La convention exécute à la séance suivante. La mesure du soir porte donc sur les décisions de la veille, pas de la journée : le trader du jour J est mesuré le soir de J+1. Un ordre à cours limité non touché reste en attente s'il est GTC, jusqu'à 90 séances.

## Vérifier que l'expérience n'a pas été altérée

```
python3 runner/verifier-protocole.py
```

Le script contrôle, à partir de l'historique git et du contenu du dépôt : que `PRE-REGISTRATION.md` n'a pas été modifié depuis sa publication, qu'aucune ligne n'a été retirée d'un fichier de données (append-only), que les en-têtes attendus sont intacts, et qu'aucune prédiction n'a été introduite après coup. **N'importe qui peut le lancer**, c'est l'intérêt d'un dépôt public.
