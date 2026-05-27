# Guide d’exécution des requêtes SQL

Ce guide explique comment lancer le script d’extraction SQL depuis Visual Studio Code afin de produire les fichiers d’entrée utilisés ensuite par l’application Streamlit.

## Objectif

Le script d’extraction permet d’interroger la base ARIA/MOSAIQ autorisée et de générer les fichiers nécessaires au chargement dans l’application.

Le principe général est le suivant :

```text
Requêtes SQL
    ↓
Script Python d’extraction
    ↓
Fichiers CSV et Excel
    ↓
Application Streamlit
```

## 1. Se placer dans le dossier du projet

Ouvrir le projet dans Visual Studio Code, puis ouvrir un terminal :

```text
Terminal > New Terminal
```

Se placer à la racine du dépôt, c’est-à-dire le dossier qui contient notamment :

```text
app.py
scripts/
sql/
docs/
requirements_sql.txt
```

Exemple :

```powershell
cd "chemin\vers\votre\projet"
```

## 2. Créer un environnement Python dédié à l’extraction SQL

Le fichier `requirements.txt` concerne principalement l’application Streamlit.

Pour l’extraction SQL, il est recommandé de créer un environnement séparé plus léger :

```powershell
python -m venv .venv_sql
```

Si `python` n’est pas reconnu, utiliser le chemin complet vers Python :

```powershell
& "C:\Program Files\Python314\python.exe" -m venv .venv_sql
```

## 3. Activer l’environnement SQL

Sous Windows PowerShell :

```powershell
.\.venv_sql\Scripts\Activate.ps1
```

Si PowerShell bloque l’activation :

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv_sql\Scripts\Activate.ps1
```

Lorsque l’environnement est activé, le terminal affiche généralement :

```text
(.venv_sql)
```

## 4. Installer les dépendances SQL

Installer les dépendances nécessaires à l’extraction :

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements_sql.txt
```

Le fichier `requirements_sql.txt` contient les bibliothèques nécessaires pour :

- se connecter à SQL Server ;
- récupérer les résultats des requêtes ;
- manipuler les tableaux avec pandas ;
- générer les fichiers CSV et Excel.

## 5. Vérifier le driver SQL Server

Le poste doit disposer d’un driver ODBC SQL Server compatible avec la chaîne de connexion utilisée dans le script.

Le plus courant est :

```text
ODBC Driver 17 for SQL Server
```

ou :

```text
ODBC Driver 18 for SQL Server
```

Si le script indique :

```python
Driver={ODBC Driver 17 for SQL Server}
```

alors le driver 17 doit être installé sur le poste, ou bien le nom du driver doit être adapté dans le script.

## 6. Vérifier la connexion à la base

Dans le script d’extraction, vérifier la fonction de connexion à la base.

Le bloc de connexion a généralement cette forme :

```python
self.connexion = pyodbc.connect(
    "Driver={ODBC Driver 17 for SQL Server};"
    "Server=REMPLIR_ICI_NOM_SERVEUR,REMPLIR_ICI_PORT;"
    "Database=REMPLIR_ICI_NOM_BASE;"
    "Trusted_Connection=yes;"
    "TrustServerCertificate=yes;"
)
```

Les champs à renseigner localement sont :

```text
REMPLIR_ICI_NOM_SERVEUR
REMPLIR_ICI_PORT
REMPLIR_ICI_NOM_BASE
```

Si l’environnement utilise un identifiant et un mot de passe, la connexion peut prendre la forme suivante :

```python
self.connexion = pyodbc.connect(
    "Driver={ODBC Driver 17 for SQL Server};"
    "Server=REMPLIR_ICI_NOM_SERVEUR,REMPLIR_ICI_PORT;"
    "Database=REMPLIR_ICI_NOM_BASE;"
    "UID=REMPLIR_ICI_UTILISATEUR;"
    "PWD=REMPLIR_ICI_MOT_DE_PASSE;"
    "TrustServerCertificate=yes;"
)
```

## 7. Vérifier l’emplacement des requêtes SQL

Se placer dans le dossier du projet puis vérifier que le dossier `sql/` contient les requêtes nécessaires.

Dans le script d’extraction, les chemins doivent pointer vers ce dossier, par exemple :

```python
requete_sql(
    "sql/nom_de_la_requete.sql",
    self.connexion,
    "nom_du_fichier_de_sortie.csv",
    to_csv=True,
)
```

Si le script cherche directement une requête sans préfixe `sql/`, cela signifie qu’il cherche le fichier dans le dossier courant. Dans ce cas, il faut soit lancer le script depuis le bon dossier, soit adapter le chemin.

## 8. Lancer l’extraction

Depuis la racine du projet :

```powershell
python scripts/load_final_all.py
```

Si `python` n’est pas reconnu :

```powershell
& "C:\Program Files\Python314\python.exe" scripts/load_final_all.py
```

Le script lance les requêtes, récupère les résultats et génère les fichiers d’entrée.

## 9. Fichiers générés

Le script génère les fichiers nécessaires au chargement dans Streamlit, en général sous deux formats :

```text
.csv
.xlsx
```

Le CSV est utile pour les traitements automatisés et les gros volumes.  
Le fichier Excel est pratique pour la relecture manuelle et le chargement dans l’interface.

## 10. Utilisation dans Streamlit

Une fois les fichiers générés, activer l’environnement utilisé pour Streamlit, puis lancer l’application :

```powershell
python -m streamlit cache clear
python -m streamlit run app.py
```

Si `python` n’est pas reconnu :

```powershell
& "C:\Program Files\Python314\python.exe" -m streamlit cache clear
& "C:\Program Files\Python314\python.exe" -m streamlit run app.py
```

Dans l’interface Streamlit, charger les fichiers générés par l’extraction.

## 11. Résumé du workflow

```text
1. Se placer dans le dossier du projet
2. Activer l’environnement SQL
3. Installer les dépendances depuis requirements_sql.txt
4. Vérifier la connexion SQL Server
5. Vérifier les chemins vers les requêtes
6. Lancer scripts/load_final_all.py
7. Récupérer les fichiers CSV/XLSX générés
8. Les charger dans l’application Streamlit
```

## 12. Problèmes fréquents

### `python` n’est pas reconnu

Utiliser le chemin complet vers Python :

```powershell
& "C:\Program Files\Python314\python.exe" --version
```

### `pyodbc` ne s’installe pas ou ne fonctionne pas

Vérifier que Python est correctement installé et que le driver ODBC SQL Server est présent sur le poste.

### Erreur de connexion SQL Server

Vérifier :

- le nom du serveur ;
- le port ;
- le nom de la base ;
- le driver ODBC ;
- les droits d’accès ;
- le mode d’authentification.

### Fichier SQL introuvable

Vérifier que le terminal est placé à la racine du projet et que le chemin vers la requête est correct.

### L’extraction fonctionne mais Streamlit ne voit pas les fichiers

Vérifier l’emplacement où les fichiers sont générés, puis les charger depuis cet emplacement dans l’interface Streamlit.
