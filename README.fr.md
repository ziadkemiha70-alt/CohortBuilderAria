# CohortBuilderAria — Documentation française

[English version](README.en.md) · [Sélection de la langue](README.md)

CohortBuilderAria est une application Streamlit dédiée à la construction de cohortes de radiothérapie à partir d'extractions ARIA. Elle permet de filtrer les traitements, sélectionner les variables de formulaire, organiser les observations selon leur temporalité par rapport à la radiothérapie et produire des exports accompagnés d'un rapport de contrôle.

## Démarrage rapide

Ouvrir PowerShell dans le dossier du projet, puis exécuter :

```powershell
cd "C:\chemin\vers\CohortBuilderAria"
python -m pip install -r requirements.txt
python -m streamlit run app2.py
```

Après le remplacement d'un fichier ou une modification du code, arrêter l'application avec `Ctrl + C`, vider le cache Streamlit, puis relancer :

```powershell
python -m streamlit cache clear
python -m streamlit run app2.py
```

L'application s'ouvre dans le navigateur. La première installation et la configuration de la connexion sont détaillées dans [documentation d’installation](docs/fr/installation.md).

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
| Installer et lancer l'application | [Installation](docs/fr/installation.md) |
| Réaliser un export | [Guide utilisateur](docs/fr/guide_utilisateur.md) |
| Comprendre l'organisation du code | [Architecture](docs/fr/architecture.md) |
| Connaître les fichiers attendus | [Données d'entrée et sorties](docs/fr/donnees_entree.md) |
| Configurer un profil d'extraction | [Profils JSON](docs/fr/profils_json.md) |
| Comprendre les fenêtres temporelles | [Temporalités](docs/fr/temporalites.md) |
| Interpréter les contrôles | [Contrôles qualité](docs/fr/controles_qualite.md) |
| Vérifier une nouvelle version | [Tests et validation](docs/fr/tests_validation.md) |
| Résoudre une erreur | [Dépannage](docs/fr/depannage.md) |

Une synthèse imprimable est disponible dans [docs/fr/Documentation_CohortBuilderAria_FR.docx](docs/fr/Documentation_CohortBuilderAria_FR.docx).

## Organisation du projet

```text
CohortBuilderAria/
├── README.md                    Sélecteur de langue
├── README.fr.md                 Présentation française
├── README.en.md                 English overview
├── requirements.txt            Dépendances Python partagées
├── app2.py                      Point d'entrée Streamlit partagé
├── utils/                       Modules Python partagés
├── sql/                         Requêtes SQL partagées
├── conf/                        Mapping et profils JSON partagés
├── scripts/                     Scripts complémentaires partagés
├── pictures/                    Ressources graphiques partagées
├── samples/                     Jeux d'exemple partagés et README bilingues
└── docs/
    ├── README.md                Sélecteur de langue de la documentation
    ├── fr/                      Documentation française complète
    └── en/                      Complete English documentation
```

Le code, les requêtes, les profils et les données d'exemple ne sont présents qu'une seule fois. Seuls les documents de lecture sont déclinés dans les deux langues.
