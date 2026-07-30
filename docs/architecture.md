# Architecture technique

## 1. Vue d'ensemble

L'application suit une architecture modulaire : `app2.py` gère l'interface et l'enchaînement des étapes, tandis que les transformations sont regroupées dans `utils/`.

```text
Sources SQL ou fichiers
        ↓
Chargement et normalisation
        ↓
Résolution des colonnes traitement
        ↓
Filtrage de la cohorte
        ↓
Sélection des variables et temporalités
        ↓
Agrégation patient
        ↓
Exports et rapport de preuve
```

## 2. Arborescence technique

```text
CohortBuilderAria/
├── app2.py
├── requirements.txt
├── utils/
├── sql/
├── conf/
├── scripts/
├── pictures/
├── samples/
├── docs/
├── inputs/
├── outputs/
└── .streamlit/secrets.toml
```

Le `README.md` placé à la racine constitue le point d'entrée de la documentation. Le dossier `docs/` contient les guides thématiques. Les dossiers `inputs/`, `outputs/` et `.streamlit/` correspondent à l'environnement local d'exécution.

## 3. Interface principale

`app2.py` assure :

- la configuration de la page ;
- l'initialisation des paramètres SQL depuis `st.secrets` ;
- la gestion des onglets et de l'état de session ;
- la sélection des sources, variables et paramètres ;
- l'appel des fonctions métier ;
- la préparation des téléchargements.

## 4. Modules du dossier `utils/`

| Module | Responsabilité principale |
|---|---|
| `display.py` | configuration visuelle, CSS, logo et en-tête |
| `sql_extract.py` | connexion SQL, exécution des scripts et export des extractions |
| `load.py` | lecture robuste CSV, ZIP et Excel, y compris en streaming |
| `clean.py` | normalisation des clés, valeurs non vides et nettoyage contrôlé |
| `cohort.py` | résolution des alias, intégration ETHOS, filtrage et base patient |
| `mapping.py` | lecture du mapping, recherche CIM10 et suggestions de variables |
| `profile.py` | chargement, enrichissement et création des profils JSON |
| `temporal.py` | décodage, fenêtres temporelles et agrégation des formulaires |
| `quality.py` | contrôles qualité et description du pipeline |
| `export.py` | génération des fichiers CSV, Excel et du rapport de preuve |
| `text.py` | normalisation des libellés et recherche tolérante |

## 5. Extraction SQL

`utils/sql_extract.py` associe les sorties suivantes aux requêtes :

| Sortie | Requête |
|---|---|
| `traitement_patient` | `sql/query_aria__strasbourg.sql` |
| `formulaire_patient` | `sql/all_patient_formulaire.sql` |
| `ethos_patient` | `sql/all_patient_ethos.sql` |

Les instructions `GO` sont découpées en lots successifs sur une même connexion afin de préserver les tables temporaires SQL Server.

## 6. Lecture des données

Le module de chargement détecte l'encodage et le séparateur des CSV. Les grands formulaires sont parcourus par morceaux afin de limiter l'utilisation mémoire. Les codes binaires de cases à cocher sont conservés comme chaînes pour préserver leurs zéros initiaux.

## 7. Construction de la cohorte

Les noms de colonnes issus de plusieurs versions d'extraction sont résolus vers des rôles communs : identifiant patient, CIM10, dose, nombre de fractions, date de début et date de fin. Une clé de jointure normalisée est ensuite construite pour rapprocher traitements et formulaires.

## 8. Construction de l'export

La base patient contient une ligne par clé de jointure, avec la première date de traitement `startD` et la dernière date `endD`. Les observations de formulaire sont converties en format long, réparties dans les fenêtres choisies puis agrégées dans un tableau final à une ligne par patient.
