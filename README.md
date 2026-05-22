# ARIA ODM Builder

Application Streamlit développée dans le cadre d’un projet de structuration de données ARIA/MOSAIQ en radiothérapie.

Le projet permet :
- le chargement des fichiers traitement et formulaire ;
- le filtrage d’une cohorte par code CIM10 ;
- l’application de profils JSON ;
- la génération d’exports structurés ;
- la création de variables temporelles ;
- quelques contrôles qualité et éléments de traçabilité.

## Structure

- `app.py` : interface Streamlit principale
- `utils/` : fonctions de traitement
- `conf/` : fichiers de configuration et profils
- `sql/` : requêtes SQL utilisées pour générer les fichiers d’entrée
- `scripts/` : scripts Python liés aux extractions SQL
- `inputs/` : fichiers locaux
- `outputs/` : exports générés localement

## Lancement

```bash
pip install -r requirements.txt
streamlit run app.py
```
