# SQL

Ce dossier contient les requêtes SQL utilisées pour générer les fichiers d’entrée de l’application Streamlit.

## Rôle du dossier

Les requêtes SQL sont exécutées en amont du pipeline Python.  
Elles permettent de produire les fichiers sources qui seront ensuite chargés dans l’application.

## Requêtes

Les requêtes sont organisées par source de données :

```text
traitement
formulaires
ETHOS ou source complémentaire
```

Les noms exacts des fichiers peuvent varier selon l’organisation locale du projet.

## Utilisation

Les requêtes sont lancées par le script :

```text
scripts/load_final_all.py
```

Le guide complet est disponible ici :

[Guide d’exécution SQL](../docs/guide_execution_sql.md)

## Sorties attendues

Après exécution, le pipeline produit des fichiers d’entrée au format CSV et Excel :

```text
traitement_patient.csv / traitement_patient.xlsx
formulaire_patient.csv / formulaire_patient.xlsx
ethos_patient.csv / ethos_patient.xlsx
```

## Remarque

Ce dossier contient uniquement les requêtes.  
La connexion à la base et l’exécution sont gérées par le script Python d’extraction.
