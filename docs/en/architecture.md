# Technical architecture

## 1. Architectural overview

CohortBuilderAria follows a modular architecture. `app2.py` orchestrates the Streamlit interface and processing sequence, while data-loading, cleaning, cohort, temporal, quality and export operations are implemented in `utils/`.

```text
SQL queries or previously generated files
                ↓
Source discovery and robust loading
                ↓
Column-name normalisation and role resolution
                ↓
Treatment cohort filtering
                ↓
Form-variable and temporal-phase selection
                ↓
Patient-level temporal aggregation
                ↓
Final exports and evidence report
```

## 2. Shared bilingual project structure

```text
CohortBuilderAria/
├── README.md
├── README.fr.md
├── README.en.md
├── app2.py
├── requirements.txt
├── utils/
├── sql/
├── conf/
├── scripts/
├── pictures/
├── samples/
├── docs/
│   ├── fr/
│   └── en/
├── inputs/
├── outputs/
└── .streamlit/secrets.toml
```

Only documentation is separated by language. The executable code, SQL extraction logic, profiles, mappings, images and sample data remain shared.

## 3. Main interface layer

`app2.py` is responsible for:

- Streamlit page configuration;
- initialisation of local SQL settings from `st.secrets`;
- creation of the six main tabs;
- management of session state;
- source-path and extraction-mode selection;
- cohort, column and temporal-setting controls;
- calls to business functions implemented in `utils/`;
- preparation of downloadable artefacts.

Keeping interface orchestration in the entry point and transformations in reusable modules reduces coupling and makes individual pipeline stages easier to validate.

## 4. Responsibilities of `utils/`

| Module | Primary responsibility |
|---|---|
| `display.py` | visual configuration, CSS, logo and application header |
| `sql_extract.py` | ODBC connection, SQL batch execution and extraction-file output |
| `load.py` | robust CSV, ZIP and Excel reading, including chunked processing |
| `clean.py` | key normalisation, non-empty value handling and controlled cleaning |
| `cohort.py` | alias resolution, ETHOS integration, treatment filtering and patient base |
| `mapping.py` | mapping-file reading, ICD-10 search and variable suggestions |
| `profile.py` | JSON profile loading, enrichment, matching and creation |
| `temporal.py` | decoding, temporal-window assignment and form aggregation |
| `quality.py` | quality metrics and pipeline-description tables |
| `export.py` | CSV, Excel and evidence-workbook generation |
| `text.py` | label normalisation and tolerant text search |

## 5. SQL extraction layer

`utils/sql_extract.py` associates each logical output with a SQL script:

| Logical output | SQL script |
|---|---|
| `traitement_patient` | `sql/query_aria__strasbourg.sql` |
| `formulaire_patient` | `sql/all_patient_formulaire.sql` |
| `ethos_patient` | `sql/all_patient_ethos.sql` |

SQL Server `GO` separators are split into successive batches executed on the same connection. This preserves session-scoped temporary tables created by earlier batches.

The extraction layer generates source files consumed by the same loading functions used in existing-file mode. Consequently, later stages do not depend on whether a file was generated immediately or supplied beforehand.

## 6. Loading and normalisation

The loading layer detects common CSV encodings and delimiters and supports CSV, Excel and ZIP-wrapped CSV sources. Large form tables can be processed in chunks to limit peak memory use. Binary checkbox strings are preserved as text so that leading zeroes remain significant.

Column names may vary between extraction versions. The cohort layer resolves known aliases toward common roles such as patient identifier, ICD-10 diagnosis, total dose, delivered fractions, first treatment date and last treatment date.

## 7. Cohort and patient-reference construction

The treatment source is filtered according to ICD-10 and treatment criteria. A normalised join key is derived to associate treatment records, form observations and optional ETHOS data.

The patient-reference table contains one row per join key and provides:

- `startD`: earliest retained radiotherapy date;
- `endD`: latest retained radiotherapy date;
- selected patient- and treatment-level descriptors.

This reference table anchors all temporal calculations.

## 8. Form transformation and temporal aggregation

Selected form columns are transformed into a long representation containing patient, variable, observation date and value. Each observation is assigned a delay relative to `startD` or `endD`, then placed into enabled temporal windows.

Aggregation creates a wide patient-level representation. Depending on phase and value type, the implementation preserves all cumulative observations, retains the first date within non-cumulative windows, resolves repeated numeric observations by maximum, merges binary strings with a logical OR and handles textual differences with the last non-empty value.

## 9. Export and evidence layers

The final patient-level treatment and form tables are joined and exported as CSV or Excel. The evidence workbook records processing parameters, output schema, quality metrics, treatment inconsistencies, duplicates and traceability samples. Its purpose is to make the construction process reviewable without reproducing the complete source datasets inside the documentation.
