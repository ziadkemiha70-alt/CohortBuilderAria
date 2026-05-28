# ARIA ODM Builder

ARIA ODM Builder est une application Streamlit développée pour structurer des données issues d’ARIA/MOSAIQ en radiothérapie.

Le projet permet d’extraire des données de vie réelle d’ARIA et de les transformer en cohortes de patients structurées par centre d’intérêt, à des fins de recherche clinique.

---

## 1. Principe général

Le pipeline suit l’enchaînement suivant :

```text
Requêtes SQL
    ↓
Script Python d’extraction
    ↓
Fichiers patients CSV/XLSX
    ↓
Application Streamlit
    ↓
Sélection clinique et temporelle
    ↓
Exports structurés et traçables
```

Deux usages sont possibles :

- **avec accès à une base ARIA** : génération des fichiers patients par extraction SQL ;
- **sans accès immédiat à la base** : test de l’application avec les fichiers fictifs du dossier `samples/`.

---

## 2. Structure du dépôt

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

### Rôle des principaux dossiers

| Dossier | Rôle |
|---|---|
| `sql/` | Contient les requêtes SQL utilisées pour générer les fichiers patients. |
| `scripts/` | Contient les scripts Python liés aux extractions SQL et à la préparation des fichiers. |
| `utils/` | Contient les modules utilisés par l’application Streamlit. |
| `conf/` | Contient les fichiers de configuration, le mapping et les profils JSON. |
| `docs/` | Contient la documentation, les notices PDF/LaTeX et les guides. |
| `samples/` | Contient des fichiers fictifs pour tester l’application sans base ARIA/MOSAIQ. |
| `pictures/` | Contient les images utilisées par l’application ou la documentation. |

---


## 3. Installation pour les extractions SQL

Les extractions SQL peuvent utiliser un environnement séparé.

Créer l’environnement dédié :

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

---

## 4. Préparer la connexion SQL

Avant de lancer l’extraction, vérifier le pilote SQL Server disponible :

```powershell
Get-OdbcDriver | Where-Object Name -like "*SQL Server*" | Select-Object Name,Platform
```

Dans le script d’extraction, renseigner ensuite les paramètres de connexion dans la fonction `connecter_bdd()` :

```python
self.connexion = pyodbc.connect(
    "Driver={REMPLIR_ICI_DRIVER};"
    "Server=REMPLIR_ICI_NOM_SERVEUR,REMPLIR_ICI_PORT;"
    "Database=REMPLIR_ICI_NOM_BASE;"
    "Trusted_Connection=yes;"
    "TrustServerCertificate=yes;"
)
```

À remplacer :

- `REMPLIR_ICI_DRIVER` par le nom exact du pilote ODBC détecté ;
- `REMPLIR_ICI_NOM_SERVEUR` par le nom du serveur SQL ;
- `REMPLIR_ICI_PORT` par le port utilisé si nécessaire ;
- `REMPLIR_ICI_NOM_BASE` par le nom de la base ARIA/MOSAIQ.

---

## 5. Lancer les extractions SQL

Depuis le dossier contenant le script principal, lancer :

```powershell
python .\load_final_all.py
```

Le script génère les fichiers patients nécessaires à l’application Streamlit.

### Fichiers attendus

```text
traitement_patient.csv
traitement_patient.xlsx
formulaire_patient.csv
formulaire_patient.xlsx
ethos_patient.csv
ethos_patient.xlsx
```

Le fichier ETHOS peut être optionnel selon le contexte d’utilisation.

Guide détaillé : [`docs/guide_execution_sql.md`](docs/guide_execution_sql.md)

---

## 6. Lancer l’application Streamlit

Depuis la racine du projet, avec l’environnement Streamlit activé :

```powershell
python -m streamlit cache clear
python -m streamlit run app.py
```

L’application s’ouvre ensuite dans le navigateur.

---

## 7. Installation de l’application Streamlit

Depuis la racine du projet, créer un environnement virtuel :

```powershell
python -m venv .venv
```

Activer l’environnement :

```powershell
.\.venv\Scripts\Activate.ps1
```

Installer les dépendances :

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Si PowerShell bloque l’activation de l’environnement, exécuter temporairement :

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

---

## 8. Utilisation dans Streamlit

### Étape 1 — Importer les fichiers

Dans l’onglet **Import**, charger les fichiers suivants :

```text
traitement_patient.csv / .xlsx / .zip
formulaire_patient.csv / .xlsx / .zip
ethos_patient.csv / .xlsx / .zip    optionnel
mapping.csv                         optionnel
profil JSON                         optionnel
```

Le dossier `samples/` permet de tester l’application avec des fichiers fictifs si aucune base ARIA/MOSAIQ n’est disponible.

### Étape 2 — Choisir la cohorte

Dans l’onglet **Construction**, sélectionner :

- le mode de sélection CIM10 ;
- le ou les codes CIM10 à inclure ;
- les éventuels critères associés, par exemple dose non nulle ;
- la référence temporelle utilisée pour les délais.

Le mapping peut aider à relier les codes CIM10, les localisations et les colonnes cliniques attendues.

### Étape 3 — Sélectionner les colonnes cliniques

L’application propose une table de sélection des colonnes formulaire.

Pour chaque variable, l’utilisateur peut :

- inclure ou exclure la colonne ;
- modifier le nom exporté ;
- vérifier le nombre de valeurs disponibles dans la cohorte ;
- ajuster la pertinence clinique de la sélection.

### Étape 4 — Définir les temporalités

Pour chaque variable sélectionnée, cocher les temporalités à générer :

```text
Cumul
Avant RT
Aigu / Pendant RT
Tardif / Après RT
```

Ces choix permettent de produire des variables structurées selon les périodes cliniques d’intérêt.

### Étape 5 — Construire et exporter

Après validation des colonnes et temporalités, cliquer sur :

```text
Construire / recalculer
```

L’application génère ensuite les exports disponibles :

- export final Excel ;
- export final CSV ;
- rapport de preuve Excel ;
- profil JSON.

Le profil JSON permet de sauvegarder les colonnes, noms d’export et temporalités sélectionnées afin de réutiliser la même configuration lors d’une prochaine extraction.

Le rapport qualité est en cours de développement et peut évoluer selon les besoins du projet.

---

## 9. Données de démonstration

Le dossier `samples/` contient des fichiers fictifs permettant de tester l’application sans accès à une base ARIA/MOSAIQ.

Ces fichiers servent uniquement à vérifier :

- le lancement de l’application ;
- le chargement des fichiers ;
- le fonctionnement du mapping ;
- la construction d’une cohorte ;
- la génération des exports.

---

## 10. Documentation

| Document | Rôle |
|---|---|
| [`docs/overview_github.pdf`](docs/overview_github.pdf) | Notice visuelle du dépôt GitHub. |
| [`docs/overview_github.tex`](docs/overview_github.tex) | Source LaTeX modifiable de la notice visuelle. |
| [`docs/documentation.tex`](docs/documentation.tex) | Documentation utilisateur détaillée. |
| [`docs/guide_execution_sql.md`](docs/guide_execution_sql.md) | Guide d’exécution des extractions SQL. |
| [`docs/scenarios.md`](docs/scenarios.md) | Scénarios d’utilisation de l’application. |
| [`docs/scenarios.tex`](docs/scenarios.tex) | Source LaTeX des scénarios. |

---

## 11. Résumé opérationnel

```text
1. Installer les dépendances Streamlit
2. Préparer l’environnement SQL si une extraction ARIA/MOSAIQ est nécessaire
3. Vérifier le pilote ODBC et les paramètres de connexion
4. Lancer le script d’extraction SQL
5. Vérifier les fichiers CSV/XLSX générés
6. Lancer l’application Streamlit
7. Importer les fichiers patients
8. Choisir le CIM10, la localisation et les colonnes cliniques
9. Sélectionner les temporalités avant / pendant / après RT
10. Recalculer puis exporter les résultats
11. Sauvegarder le profil JSON pour réutiliser la configuration
```

---

## 12. Remarque sur les noms de fichiers

Les liens de documentation supposent les noms suivants dans `docs/` :

```text
overview_github.pdf
overview_github.tex
documentation.tex
guide_execution_sql.md
scenarios.md
scenarios.tex
```
