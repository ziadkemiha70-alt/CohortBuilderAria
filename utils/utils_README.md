# Utils

Ce dossier contient les modules Python utilisés par l’application Streamlit.

## Rôle du dossier

Les fonctions du dossier `utils/` permettent de séparer la logique métier de l’interface `app.py`.

Cette organisation rend le code plus lisible, plus maintenable et plus facile à tester.

## Types de modules

Selon la version du projet, ce dossier peut contenir des modules pour :

```text
chargement des fichiers
nettoyage des données
mapping des colonnes
construction de cohorte
calcul des variables temporelles
contrôles qualité
exports
affichage Streamlit
gestion des profils JSON
```

## Module important : temporalité

Le module lié aux fenêtres temporelles gère notamment :

- la normalisation des dates ;
- le calcul des délais par rapport au début ou à la fin de la radiothérapie ;
- l’agrégation des variables cliniques par période ;
- la distinction entre colonnes cumulatives et non cumulatives.

## Utilisation

Les modules de `utils/` ne sont généralement pas lancés directement.

Ils sont importés par :

```text
app.py
```

## Documentation associée

Pour comprendre le workflow global, consulter :

- [Vue d’ensemble du pipeline](../docs/overview_github.pdf)
- [Documentation utilisateur détaillée](../docs/documentation.tex)
- [Guide d’exécution SQL](../docs/guide_execution_sql.md)
