# Scripts

Ce dossier contient les scripts Python utilisés pour lancer les extractions SQL et produire les fichiers d’entrée nécessaires à l’application Streamlit.

## Script principal

### `load_final_all.py`

Script principal d’extraction.

Il se connecte à la base SQL Server autorisée, exécute les requêtes du dossier `sql/`, récupère les résultats et génère les fichiers d’entrée au format CSV et Excel.

Les fichiers produits sont ensuite chargés dans l’application Streamlit.

## Fichiers générés

Le script peut générer les fichiers suivants :

```text
traitement_patient.csv
traitement_patient.xlsx
ethos_patient.csv
ethos_patient.xlsx
formulaire_patient.csv
formulaire_patient.xlsx
```

## Exécution

Depuis la racine du projet :

```powershell
python scripts/load_final_all.py
```

## Documentation associée

Le guide complet d’exécution SQL est disponible ici :

[Guide d’exécution SQL](../docs/guide_execution_sql.md)

## Environnement Python

Les dépendances minimales pour l’extraction SQL sont listées dans :

```text
requirements_sql.txt
```

Installation recommandée :

```powershell
python -m venv .venv_sql
.\.venv_sql\Scripts\Activate.ps1
python -m pip install -r requirements_sql.txt
```

## Remarque

Le dossier `scripts/` sert uniquement aux étapes d’extraction et de préparation.  
L’application interactive est lancée séparément avec `app.py`.
