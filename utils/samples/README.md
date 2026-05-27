# Samples

Ce dossier contient des fichiers fictifs permettant de tester l’application Streamlit sans lancer d’extraction SQL.

## Objectif

Les fichiers présents ici servent à simuler les fichiers d’entrée attendus par l’application.

Ils permettent de tester :

- le chargement des fichiers ;
- le mapping ;
- la construction de cohorte ;
- les variables temporelles ;
- les contrôles qualité ;
- la génération de l’export final.

## Organisation

```text
samples/
├── README.md
├── csv/
│   ├── traitement_patient_demo.csv
│   ├── formulaire_patient_demo.csv
│   └── ethos_patient_demo.csv
└── xlsx/
    ├── traitement_patient_demo.xlsx
    ├── formulaire_patient_demo.xlsx
    └── ethos_patient_demo.xlsx
