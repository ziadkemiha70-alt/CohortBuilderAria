# ARIA ODM Builder

ARIA ODM Builder est une application Streamlit développée dans le cadre d’un projet de structuration de données ARIA/MOSAIQ en radiothérapie.

Le projet vise à transformer des extractions issues du système d’information de radiothérapie en exports patients structurés, contrôlés et traçables pour un usage de recherche clinique.

## Workflow général

```text
Requêtes SQL
    ↓
Scripts Python de préparation
    ↓
Fichiers d’entrée CSV/XLSX
    ↓
Application Streamlit
    ↓
Contrôles qualité
    ↓
Exports structurés
