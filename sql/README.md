# SQL

Ce dossier contient les requêtes SQL utilisées pour générer les fichiers d’entrée de l’application.

Les requêtes sont exécutées en amont du pipeline Python. Elles permettent de produire les fichiers sources qui seront ensuite préparés par les scripts Python, puis chargés dans l’interface Streamlit.

## Fichiers utilisés

### `all_patient_traitement.sql`

Requête dédiée aux informations de traitement.

Elle sert à extraire les données nécessaires pour décrire le parcours de radiothérapie : patient, traitement, dates, dose, fractions, technique ou autres informations utiles selon la structure disponible.

Le fichier produit constitue la source principale pour construire la cohorte et les variables liées au traitement.

### `all_patient_formulaire.sql`

Requête dédiée aux formulaires cliniques.

Elle sert à extraire les informations saisies dans les formulaires patients : événements datés, variables cliniques, champs de suivi ou éléments nécessaires à la construction des variables longitudinales.

Le fichier produit est ensuite croisé avec les données de traitement afin d’enrichir l’export patient final.

### `all_patient_ethos.sql`

Requête dédiée à une source complémentaire optionnelle.

Elle peut être utilisée pour extraire des informations liées à un flux spécifique, par exemple un flux adaptatif ou une source additionnelle utile au projet.

Ce fichier n’est pas forcément obligatoire pour tous les scénarios, mais il permet d’ajouter des variables complémentaires lorsque la source est disponible.

## Place dans le workflow

```text
Requêtes SQL
    ↓
Fichiers sources
    ↓
Scripts Python de préparation
    ↓
Application Streamlit
    ↓
Export final et rapport qualité
