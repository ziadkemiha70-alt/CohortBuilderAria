# CohortBuilderAria — English Documentation

[Version française](README.fr.md) · [Language selection](README.md)

CohortBuilderAria is a Streamlit application for building radiotherapy cohorts from ARIA extractions. It supports treatment filtering, form-variable selection, temporal organisation of observations relative to radiotherapy, optional ETHOS enrichment, and the generation of analysis-ready exports together with an evidence report.

## Quick start

Open PowerShell in the project directory and run:

```powershell
cd "C:\path\to\CohortBuilderAria"
python -m pip install -r requirements.txt
python -m streamlit run app2.py
```

After replacing a file or modifying the code, stop the application with `Ctrl + C`, clear the Streamlit cache, and restart it:

```powershell
python -m streamlit cache clear
python -m streamlit run app2.py
```

The application opens in the default web browser. First-time setup, ODBC requirements and SQL configuration are described in [Installation and startup](docs/en/installation.md).

## Main capabilities

- run the ARIA SQL extraction from the application or load previously generated files;
- define a cohort from one or more ICD-10 codes and treatment-level criteria;
- optionally enrich eligible patients with ETHOS treatment records;
- select, search, rename and categorise form variables;
- arrange observations into cumulative, pre-RT, acute and late phases;
- preserve TNM/date pairs and selected treatment descriptors;
- save and reload reusable JSON extraction profiles;
- export the final cohort as Excel or CSV;
- generate an evidence workbook describing parameters, quality checks and traceability samples.

## Documentation map

| Need | Document |
|---|---|
| Install and start the application | [Installation and startup](docs/en/installation.md) |
| Build and export a cohort | [User guide](docs/en/user_guide.md) |
| Understand the code organisation | [Technical architecture](docs/en/architecture.md) |
| Review accepted inputs and generated outputs | [Input and output data](docs/en/input_output_data.md) |
| Configure a reusable extraction profile | [JSON profiles](docs/en/json_profiles.md) |
| Understand temporal windows and aggregation | [Temporal logic](docs/en/temporal_logic.md) |
| Interpret quality checks and the evidence report | [Quality controls](docs/en/quality_controls.md) |
| Validate a modified version | [Testing and validation](docs/en/testing_validation.md) |
| Diagnose common errors | [Troubleshooting](docs/en/troubleshooting.md) |

A printable technical summary is available as [CohortBuilderAria Technical Documentation](docs/en/CohortBuilderAria_Technical_Documentation_EN.docx).

## Shared project structure

```text
CohortBuilderAria/
├── README.md                    Language selector
├── README.fr.md                 French project overview
├── README.en.md                 English project overview
├── requirements.txt            Shared Python dependencies
├── app2.py                      Shared Streamlit entry point
├── utils/                       Shared loading, cohort, temporal and export modules
├── sql/                         Shared ARIA extraction queries
├── conf/                        Shared mapping files and JSON profiles
├── scripts/                     Shared complementary scripts
├── pictures/                    Shared interface assets
├── samples/                     Shared fictitious demonstration datasets
└── docs/
    ├── README.md                Documentation language selector
    ├── fr/                      Complete French documentation
    └── en/                      Complete English documentation
```

The executable project is not duplicated by language. Only explanatory documents are translated. File names, Python identifiers, SQL object names, profile keys and interface labels are preserved exactly when they refer to the implementation.
