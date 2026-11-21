# Comment l'expérience tourne réellement

Ce dossier rend public **le mécanisme d'exécution**, pas seulement les règles. Les prompts ci-dessous sont ceux qui sont réellement envoyés aux agents, verbatim.

## Le dispositif

Les trois agents sont des sessions **Claude** distinctes, déclenchées par des tâches planifiées. Chacune est une session neuve, sans mémoire de la précédente : tout ce qu'un agent sait de son passé, il le lit dans les fichiers de ce dépôt. C'est ce qui rend l'expérience reproductible et auditable — et c'est aussi ce qui rend l'aveuglement mécanique plutôt que déclaratif.

| Tâche | Quand | Agent | Prompt |
|---|---|---|---|
| Décisions | chaque jour ouvré, **13h08, 16h08 et 19h08 UTC** : une seule tâche, trois déclenchements | trader | `tache-trader.md` |
| Mesure | chaque jour ouvré, **22h41 UTC**, après la clôture américaine | mesureur | `tache-mesureur.md` |
| Réconciliation et rapport | le 1er de chaque mois | rédacteur | `tache-mensuelle.md` |

**Deux tâches séparées plutôt qu'une seule session qui jouerait les deux rôles** : c'est le point de conception le plus important du dispositif. Une seule session verrait les deux comptabilités et l'aveuglement ne reposerait plus que sur sa discipline. Des sessions distinctes, la mesure venant après la dernière fenêtre du trader, avec des listes de fichiers d'entrée disjointes, le rendent structurel.

## Le décalage d'une séance

La convention exécute à la séance suivante. La mesure du soir porte donc sur les décisions de la veille, pas de la journée : le trader du jour J est mesuré le soir de J+1. Un ordre à cours limité non touché reste en attente s'il est GTC, jusqu'à 90 séances.

## Vérifier que l'expérience n'a pas été altérée

```
python3 runner/verifier-protocole.py
```

Le script contrôle, à partir de l'historique git et du contenu du dépôt : que `PRE-REGISTRATION.md` n'a pas été modifié depuis sa publication, qu'aucune ligne n'a été retirée d'un fichier de données (append-only), que les en-têtes attendus sont intacts, et qu'aucune prédiction n'a été introduite après coup. **N'importe qui peut le lancer**, c'est l'intérêt d'un dépôt public.

## Où vivent les commits

Les trois tâches s'exécutent **dans le cloud**, sans dépendre d'un ordinateur allumé. Chaque exécution clone le dépôt depuis GitHub, committe et pousse directement ; l'horodatage UTC du commit est celui de la décision. L'environnement d'exécution est effacé à la fin de chaque session : un commit qui n'a pas été poussé est perdu. C'est pourquoi chaque prompt impose de pousser avant de terminer, et, si le push échoue malgré tout, de reproduire le patch complet dans la réponse finale de la session pour qu'il puisse être appliqué à la main, avec sa date d'origine.

## La fenêtre de décision et le sur-trading

Tripler la cadence crée un risque de sur-rotation par simple effet de convocation : un agent réveillé trois fois peut se croire tenu d'agir trois fois. Le prompt du trader le neutralise explicitement (« C'est une occasion de décider, pas un quota à remplir »), et les frais, le change, le portage et l'impôt sont imputés à chaque aller-retour.
