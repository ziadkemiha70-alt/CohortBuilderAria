# ARIA ODM Builder

ARIA ODM Builder est une application Streamlit développée dans le cadre d’un projet de structuration de données ARIA/MOSAIQ en radiothérapie.

Le projet vise à transformer des extractions issues du système d’information de radiothérapie en exports patients structurés, contrôlés et traçables pour un usage de recherche clinique.

## Workflow général

```text
Requêtes SQL
    ↓
Scripts Python d’extraction
    ↓
Fichiers d’entrée CSV/XLSX
    ↓
Application Streamlit
    ↓
Contrôles qualité
    ↓
Exports structurés
```

## Fonctionnalités principales

Le projet permet :

- le chargement de fichiers de traitement, formulaires et ETHOS ;
- le filtrage d’une cohorte par code CIM10 ;
- l’application de profils JSON ;
- la création de variables temporelles ;
- la génération d’exports structurés ;
- la production de contrôles qualité et d’éléments de traçabilité.

## Structure du dépôt

```text
ARIA_ODM_Builder/
├── README.md
├── app.py
├── requirements.txt
├── requirements_sql.txt
├── conf/
├── docs/
├── pictures/
├── scripts/
├── sql/
├── utils/
└── samples/
```

## Rôle des dossiers et fichiers

- `sql/` : requêtes SQL utilisées pour générer les fichiers d’entrée ;
- `scripts/` : scripts Python liés aux extractions SQL et à la préparation des fichiers ;
- `app.py` : application Streamlit principale ;
- `utils/` : fonctions utilisées par l’application ;
- `conf/` : fichiers de configuration, mapping et profils JSON ;
- `docs/` : documentation du projet ;
- `samples/` : fichiers fictifs permettant de tester l’application sans extraction SQL ;
- `pictures/` : images utilisées par l’application ou la documentation ;
- `requirements.txt` : dépendances nécessaires à l’application Streamlit ;
- `requirements_sql.txt` : dépendances minimales nécessaires aux extractions SQL.

## Installation de l’application Streamlit

Créer un environnement virtuel :

```powershell
python -m venv .venv
```

Activer l’environnement sous Windows :

```powershell
.\.venv\Scripts\Activate.ps1
```

Installer les dépendances de l’application :

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Installation pour les extractions SQL

Les extractions SQL peuvent utiliser un environnement séparé plus léger.

Créer un environnement dédié :

```powershell
python -m venv .venv_sql
```

Activer l’environnement :

```powershell
.\.venv_sql\Scripts\Activate.ps1
```

Installer les dépendances SQL :

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements_sql.txt
```

Le fichier `requirements_sql.txt` contient uniquement les bibliothèques nécessaires pour exécuter les requêtes SQL, récupérer les résultats et générer les fichiers CSV/XLSX.

## Lancer les extractions SQL

Depuis la racine du projet :

```powershell
python scripts/load_final_all.py
```

Le script génère les fichiers d’entrée au format CSV et Excel.

## Lancer l’application Streamlit

Depuis la racine du projet, avec l’environnement Streamlit activé :

```powershell
python -m streamlit cache clear
python -m streamlit run app.py
```

L’application s’ouvre ensuite dans le navigateur.

## Exécution des requêtes SQL

Le guide détaillé pour lancer les requêtes SQL et générer les fichiers d’entrée est disponible ici :

[Guide d’exécution SQL](docs/guide_execution_sql.md)

## Documentation

Documents recommandés :

- [Vue d’ensemble du pipeline](docs/overview_github.pdf)
- [Documentation utilisateur détaillée](docs/documentation_utilisateur.pdf)
- [Guide d’exécution SQL](docs/guide_execution_sql.md)

## Données de démonstration

Le dossier `samples/` contient des fichiers fictifs permettant de tester l’application sans accès à une base ARIA/MOSAIQ.

Ces fichiers servent uniquement à vérifier le fonctionnement du pipeline et de l’interface Streamlit.

## Résumé d’utilisation

```text
1. Générer les fichiers d’entrée avec les requêtes SQL ou utiliser les fichiers de démonstration
2. Lancer app.py avec Streamlit
3. Charger les fichiers de traitement, formulaires et ETHOS
4. Sélectionner un mapping et un profil JSON
5. Construire la cohorte
6. Vérifier les contrôles qualité
7. Exporter les résultats structurés
```
