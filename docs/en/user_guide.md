# User guide

## 1. Scope

This guide describes the complete operational path from source selection to final export. The application interface remains in French; therefore, exact interface labels are shown in bold as they appear in the application.

## 2. Choose the import mode

Open the **Import** tab and select one of the two available modes:

- **Faire l'extraction SQL ici**: the application executes the SQL scripts located in the configured `sql/` directory and writes the requested extraction files;
- **Extraction déjà faite**: the application loads source files already present in the selected directory.

Both modes feed the same loading, normalisation, cohort-building, temporal aggregation and export pipeline. The difference concerns only how the source files are obtained.

## 3. Load and verify the sources

The three source roles are:

| Source | Role | Required status |
|---|---|---|
| `traitement_patient` | treatment records, dates, dose, fractions, diagnosis and technical descriptors | primary source |
| `formulaire_patient` | dated observations from forms and questionnaires | required for form-variable extraction |
| `ethos_patient` | complementary ETHOS treatment records | optional |

The mapping file and JSON profile are optional:

- the mapping assists ICD-10 interpretation, localisation naming and variable suggestions;
- the JSON profile restores a previously saved selection of variables, export names, temporal phases and related settings.

Before proceeding, review the source status displayed by the application. Missing optional sources should not block the main pipeline; missing primary source information must be corrected.

## 4. Define the treatment cohort

In the **Construction** tab:

1. enter one or more ICD-10 codes;
2. select the ICD-10 matching mode offered by the interface;
3. enable the non-zero-dose criterion when the study definition requires completed or delivered treatment;
4. review the displayed row count and unique-patient count;
5. confirm that the selected treatments correspond to the intended clinical localisation.

The standard treatment source defines the primary cohort. When an ETHOS source is loaded, eligible ETHOS records enrich patients already retained by the main cohort logic; they do not replace the main ICD-10 selection rule.

## 5. Select treatment-level columns

The application resolves several historical extraction column names into shared roles, including patient identifier, diagnosis, total dose, fractions, first treatment date and last treatment date.

Select the treatment descriptors that must appear in the final file. Internal compatibility columns created by the application are used during processing but excluded from the final export. When available, indexed tumour staging pairs such as `TNM_1` / `Date_staged_1`, `TNM_2` / `Date_staged_2`, and subsequent pairs are detected and can be preserved.

Before continuing, check that the chosen columns are meaningful at one row per patient. The evidence report will flag treatment fields that contain multiple distinct values for the same patient.

## 6. Select form variables

The variable-selection table supports the following operations:

- include or exclude a form variable;
- edit the final export name;
- review the variable category and relevance score;
- search with tolerance for accents, spaces, punctuation and common encoding variations;
- optionally compute value and patient counters.

Counter computation is intentionally optional because very wide form extractions may be large. Keeping it disabled improves interface responsiveness during initial selection. The application reloads only selected variables when the final export is built.

## 7. Configure temporal phases

For every included variable, select the required phases:

- **Cumul**: all available observations;
- **Avant RT**: observations before the first retained radiotherapy date;
- **Pendant RT / Aigu**: observations from treatment start during acute follow-up;
- **Après RT / Tardif**: observations after the last retained radiotherapy date.

Expert controls allow the default week and month windows to be adjusted. Detailed phase definitions, output-column naming and aggregation rules are provided in [Temporal logic](temporal_logic.md).

## 8. Build or recalculate the export

Click **Construire / recalculer**. The application then:

1. reloads the selected form columns only;
2. normalises identifiers and associates form observations with cohort patients;
3. builds one patient reference row with `startD` and `endD`;
4. calculates delays between each observation date and the configured radiotherapy reference date;
5. assigns observations to cumulative, pre-RT, acute and late windows;
6. applies optional binary-code decoding and duplicate handling;
7. aggregates repeated observations according to the implemented rules;
8. joins treatment-level and form-derived outputs;
9. computes quality metrics and evidence-report tables.

A recalculation should be triggered after changing cohort criteria, selected treatment columns, form-variable inclusion, export names, temporal phases or profile-decoding settings.

## 9. Review the result before download

Review at least:

- final patient count;
- treatment-to-form matching rates;
- availability of `startD` and `endD`;
- warnings concerning multiple doses, dates, fractions or machines;
- columns reported as entirely missing;
- any profile variables that were not found in the current form source.

The application may offer removal of columns containing only missing values. This operation changes only the downloaded representation; it does not alter the source files.

## 10. Download the outputs

The interface can produce:

- final Excel export;
- final CSV export;
- Excel evidence report;
- JSON profile representing the current selection.

The final export is organised as one row per patient. The evidence report should be retained with the export because it documents selection parameters, quality checks, output schema and traceability samples.
