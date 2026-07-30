# CohortBuilderAria

CohortBuilderAria est une application Streamlit dédiée à la construction de cohortes de radiothérapie à partir d'extractions ARIA. Elle permet de filtrer les traitements, sélectionner les variables de formulaire, organiser les observations selon leur temporalité par rapport à la radiothérapie et produire des exports accompagnés d'un rapport de contrôle.

## Démarrage rapide

Ouvrir PowerShell dans le dossier du projet, puis exécuter :

```powershell
cd "C:\chemin\vers\CohortBuilderAria"
python -m pip install -r requirements.txt
python -m streamlit run app2.py
```

L'application s'ouvre dans le navigateur. La première installation et la configuration de la connexion sont détaillées dans [docs/installation.md](docs/installation.md).

## Fonctions principales

- extraction des tables ARIA depuis SQL Server ou utilisation de fichiers déjà générés ;
- construction d'une cohorte à partir de codes CIM10 et de critères de traitement ;
- intégration optionnelle des données ETHOS ;
- sélection et renommage des variables issues des formulaires ;
- répartition des observations en phases cumulée, avant RT, aiguë et tardive ;
- sauvegarde et réutilisation de profils JSON ;
- export Excel, CSV et rapport de preuve.

## Documentation

| Besoin | Document |
|---|---|
| Installer et lancer l'application | [Installation](docs/installation.md) |
| Réaliser un export | [Guide utilisateur](docs/guide_utilisateur.md) |
| Comprendre l'organisation du code | [Architecture](docs/architecture.md) |
| Connaître les fichiers attendus | [Données d'entrée et sorties](docs/donnees_entree.md) |
| Configurer un profil d'extraction | [Profils JSON](docs/profils_json.md) |
| Comprendre les fenêtres temporelles | [Temporalités](docs/temporalites.md) |
| Interpréter les contrôles | [Contrôles qualité](docs/controles_qualite.md) |
| Vérifier une nouvelle version | [Tests et validation](docs/tests_validation.md) |
| Résoudre une erreur | [Dépannage](docs/depannage.md) |

Une synthèse imprimable est disponible dans [docs/Documentation_CohortBuilderAria.docx](docs/Documentation_CohortBuilderAria.docx).

## Organisation du projet

```text
CohortBuilderAria/
├── README.md                  Présentation et démarrage rapide
├── requirements.txt          Dépendances Python
├── app2.py                    Point d'entrée de l'application Streamlit
├── utils/                     Modules de chargement, cohorte, temporalités et export
├── sql/                       Requêtes d'extraction ARIA
├── conf/                      Mapping et profils fournis avec le projet
├── scripts/                   Scripts d'extraction ou d'exploitation complémentaires
├── pictures/                  Ressources graphiques de l'interface
├── samples/                   Jeux d'exemple et données fictives de validation
├── docs/                      Documentation détaillée du projet
│   ├── README.md              Sommaire de la documentation
│   ├── installation.md
│   ├── guide_utilisateur.md
│   ├── architecture.md
│   ├── donnees_entree.md
│   ├── profils_json.md
│   ├── temporalites.md
│   ├── controles_qualite.md
│   ├── tests_validation.md
│   ├── depannage.md
│   └── Documentation_CohortBuilderAria.docx
├── inputs/                    Fichiers d'entrée locaux
├── outputs/                   Fichiers produits par l'extraction SQL
└── .streamlit/
    └── secrets.toml           Configuration locale de la connexion SQL
```

Le rôle détaillé des modules est présenté dans [docs/architecture.md](docs/architecture.md).
