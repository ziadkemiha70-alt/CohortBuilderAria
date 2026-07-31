# JSON profiles

## 1. Purpose

A JSON profile stores a reusable extraction configuration. It preserves variable and temporal choices while leaving source files unchanged. A profile can be applied to a later extraction built from sources with the same conceptual structure.

## 2. General structure

```json
{
  "version": "ARIA_ODM_profile_v1",
  "created_at": "2026-07-30T09:00:00",
  "settings": {},
  "columns": []
}
```

| Key | Meaning |
|---|---|
| `version` | profile-format identifier |
| `created_at` | profile-creation timestamp |
| `settings` | general extraction and aggregation parameters |
| `columns` | form-variable configuration entries |

Key names are part of the implementation contract and are not translated in the English documentation.

## 3. General settings

Depending on the version and current selection, `settings` may contain:

- export area or output name;
- ICD-10 matching mode and selected code values;
- non-zero-dose criterion;
- temporal-delay reference;
- selected treatment columns;
- configured week lists;
- exact-duplicate handling;
- binary-code decoding tables.

A setting is applied only when it is supported by the current application version and compatible with the loaded sources.

## 4. Form-variable entries

Each object in `columns` may contain the following fields:

| Field | Function |
|---|---|
| `Inclure` | enables the variable |
| `Colonne formulaire` | exact source-column name stored by the profile |
| `Nom export` | name used in the final export |
| `Cumul` | enables cumulative output columns |
| `Avant RT` | enables pre-treatment windows |
| `Aigu` | enables acute/during-treatment windows |
| `Tardif` | enables late/post-treatment windows |
| decoding fields | describe optional binary-position conversion |

French field names are preserved because they are consumed by the application.

## 5. Matching a profile to a new form source

When a profile is loaded, the application searches for each stored source column in the current form table. Matching tolerates differences involving:

- accents;
- spaces;
- punctuation;
- line breaks;
- common text-encoding defects.

Variables that cannot be matched are listed in the profile diagnostic. The profile remains editable, allowing variables to be added, removed, manually associated or renamed before export construction.

## 6. Binary-choice decoding

Some form systems store multiple checkbox positions as strings such as `00100` or `01001`. A decoding table can map each position to a label or grade.

When multiple positions are active, the configured decoding mode can:

- combine active labels;
- preserve a derived maximum grade;
- retain the original value when no valid decoding rule is available.

Binary values must be handled as strings. Numeric conversion would remove leading zeroes and alter positional meaning.

## 7. Profile lifecycle

A typical profile workflow is:

1. load the treatment and form sources;
2. define the cohort and variable selection;
3. configure export names and temporal phases;
4. build and review the output;
5. use **Sauvegarder profil JSON** to download the current configuration;
6. load the profile during a later extraction;
7. review the matching diagnostic before rebuilding the export.

A profile accelerates repeated configuration; it does not replace source validation or the evidence-report review.
