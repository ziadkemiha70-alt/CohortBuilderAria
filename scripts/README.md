# Scripts

Ce dossier contient les scripts Python utilisés pour lancer les requêtes SQL, préparer les données extraites et produire les fichiers d’entrée nécessaires à l’application Streamlit.

## Scripts présents

### `load_final_all.py`

Script principal du dossier `scripts/`.

Il centralise le workflow d’extraction et de préparation : connexion aux sources autorisées, exécution ou chargement des extractions, nettoyage initial, harmonisation des tables et génération de fichiers intermédiaires exploitables par l’application.

C’est le script à consulter en priorité pour comprendre la chaîne complète avant l’utilisation de `app.py`.

### `trait.py`

Script dédié aux données de traitement.

Il regroupe les étapes liées aux informations de radiothérapie : dates de traitement, dose, fractions, technique, machine ou autres champs associés au parcours de traitement.

Il permet de préparer une table de traitement plus propre et plus facilement exploitable dans la suite du pipeline.

### `tox.py`

Script dédié aux informations cliniques ou de toxicité.

Il sert à traiter les données issues des formulaires, à identifier les variables utiles, à préparer les champs cliniques et à faciliter leur intégration avec les données de traitement.

Il intervient dans la construction des variables exploitables pour l’analyse ou le contrôle qualité.

### `sys.py`

Script utilitaire du dossier `scripts/`.

Il contient des fonctions de support utilisées par les autres scripts, par exemple des réglages techniques, des chemins, des fonctions communes ou des éléments nécessaires à l’exécution du workflow.

Il n’est généralement pas le script lancé directement par l’utilisateur.
