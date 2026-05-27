# ARIA ODM Builder

ARIA ODM Builder est une application Streamlit développée dans le cadre d’un projet de structuration de données ARIA/MOSAIQ en radiothérapie.

Le projet vise à transformer des extractions issues du système d’information de radiothérapie en exports patients structurés, contrôlés et traçables pour un usage de recherche clinique.

## Workflow général

```text
Requêtes SQL
    ↓
Script Python d’extraction
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
├── samples/
├── scripts/
├── sql/
└── utils/
```

## Rôle des principaux dossiers

- [`sql/`](sql/) : requêtes SQL utilisées pour générer les fichiers d’entrée.
- [`scripts/`](scripts/) : scripts Python liés aux extractions SQL et à la préparation des fichiers.
- [`utils/`](utils/) : modules Python utilisés par l’application Streamlit.
- [`conf/`](conf/) : fichiers de configuration, mapping et profils JSON.
- [`docs/`](docs/) : documentation du projet, guides et supports LaTeX/PDF.
- [`samples/`](samples/) : fichiers fictifs permettant de tester l’application sans extraction SQL.
- [`pictures/`](pictures/) : images utilisées par l’application ou la documentation.

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

## Lancer les extractions SQL

Depuis la racine du projet :

```powershell
python scripts/load_final_all.py
```

Le script génère les fichiers d’entrée au format CSV et Excel.

Guide détaillé : [Guide d’exécution SQL](docs/guide_execution_sql.md)

## Lancer l’application Streamlit

Depuis la racine du projet, avec l’environnement Streamlit activé :

```powershell
python -m streamlit cache clear
python -m streamlit run app.py
```

L’application s’ouvre ensuite dans le navigateur.

## Documentation

| Document | Rôle |
|---|---|
| [Vue d’ensemble du pipeline](docs/overview_github.pdf) | Diaporama visuel à lire en premier pour comprendre l’architecture du projet. |
| [Source LaTeX de la vue d’ensemble](docs/overview_github.tex) | Source modifiable du diaporama. |
| [Documentation utilisateur détaillée](docs/documentation.tex) | Documentation technique et utilisateur détaillée. |
| [Guide d’exécution SQL](docs/guide_execution_sql.md) | Guide pour créer l’environnement SQL, lancer les requêtes et générer les fichiers d’entrée. |
| [Scénarios utilisateur](docs/scenarios.md) | Scénarios d’utilisation de l’application. |
| [Source LaTeX des scénarios](docs/scenarios.tex) | Source modifiable des scénarios. |

## Données de démonstration

Le dossier [`samples/`](samples/) contient des fichiers fictifs permettant de tester l’application sans accès à une base ARIA/MOSAIQ.

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

## Remarque sur les noms de fichiers

Les liens de documentation supposent les noms suivants dans `docs/` :

```text
overview_github.pdf
overview_github.tex
documentation.tex
guide_execution_sql.md
scenarios.md
scenarios.tex
```

Si un fichier porte un autre nom, renommer le fichier ou adapter le lien correspondant dans ce README.
