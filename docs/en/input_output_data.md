# Input and output data

## 1. Accepted file formats and source discovery

Depending on the source and loading mode, CohortBuilderAria accepts:

- CSV files;
- XLSX workbooks;
- ZIP archives containing a CSV file.

The application searches for the following logical base names:

```text
traitement_patient
formulaire_patient
ethos_patient
```

When several supported representations exist, the search priority is `.csv`, then `.xlsx`, then `.zip`.

## 2. `traitement_patient`: primary cohort source

This source defines the treatment cohort and may include:

- technical and functional patient identifiers;
- one or more ICD-10 diagnosis codes;
- first- and last-fraction dates;
- total delivered dose;
- delivered and planned fraction counts;
- plan, technique, machine and other treatment descriptors;
- tumour information, including indexed `TNM_n` / `Date_staged_n` pairs.

Exact column names may vary between extraction versions. The application recognises multiple aliases for structurally important fields and maps them to common internal roles.

For reliable processing, the source must provide enough information to resolve at least a patient key, diagnosis and treatment dates. Dose and fraction criteria are applied only when the corresponding values can be interpreted.

## 3. `formulaire_patient`: dated observation source

This source contains observations from forms and questionnaires. Two columns are structurally required:

| Column | Role |
|---|---|
| `pt_id` | identifier used to associate the observation with a cohort patient |
| `date_event` | date assigned to the observation |

All remaining columns are candidate variables that can be selected in the interface. During final construction, only selected variables are reloaded, which limits memory consumption for very wide form tables.

Values may be numeric, textual, dates, categorical codes or binary checkbox strings. Binary strings must remain text so that leading zeroes are not lost.

## 4. `ethos_patient`: optional complementary source

This source is optional. The application retains usable ETHOS rows according to available dates and non-zero delivered-dose information, then integrates them with the treatment cohort.

ETHOS data enrich the selected patient population. They do not independently redefine the main ICD-10 cohort when standard treatment data are present.

## 5. Mapping file

The mapping may be supplied as CSV or Excel. It can associate ICD-10 codes with descriptions, anatomical localisations, groups or variable suggestions.

The mapping is an assistance layer: it supports interpretation and selection but does not determine whether the processing pipeline can execute.

## 6. JSON profile

A JSON profile records a reusable extraction configuration, including selected variables, export names, temporal phases and aggregation-related settings. Profile structure and matching behaviour are described in [JSON profiles](json_profiles.md).

## 7. Generated outputs

| Output | Content |
|---|---|
| Final Excel export | one row per patient with selected treatment and form-derived columns |
| Final CSV export | equivalent patient-level content using a semicolon-separated text format |
| Evidence report | parameters, quality checks, schema and traceability samples |
| JSON profile | reusable representation of the current extraction configuration |

Output names are derived from the selected localisation, profile name or ICD-10 criteria.

## 8. Missing values and empty columns

Missing values are represented as `NA` in final exports. Columns that are entirely missing for the selected cohort are identified before download and may be removed from the final output.

An entirely empty output column does not necessarily indicate a processing failure. It may result from:

- a selected variable not being populated in the cohort;
- a temporal phase with no observation in the configured window;
- a profile variable not being present in the current source;
- a cohort definition that excludes patients carrying the selected observation.
