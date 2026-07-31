# Testing and validation

## 1. Validation objective

Validation confirms that a modified version preserves the expected behaviour of source loading, cohort filtering, temporal classification, aggregation, decoding and output generation.

## 2. Minimum fictitious test dataset

Use a synthetic dataset containing at least:

- several patients and ICD-10 codes;
- standard and ETHOS treatment records;
- observations before, during and after radiotherapy;
- numeric, textual and binary values;
- exact duplicates;
- a profile variable absent from the current form file;
- a zero dose and a multi-value dose;
- several TNM records for one patient.

The repository `samples/` directory is the natural location for demonstration files. Test expectations should be documented independently from the production sources.

## 3. Functional scenarios

| Scenario | Expected result |
|---|---|
| clean application launch | the six main tabs are accessible |
| existing-file mode | available treatment, form and ETHOS sources are detected |
| SQL connection test | a success message is displayed when configuration and permissions are valid |
| simple ICD-10 filter | only matching patients are retained |
| several ICD-10 values in one cell | one requested code is sufficient to retain the row |
| multi-value dose | at least one non-zero value retains the treatment when that criterion is enabled |
| ETHOS integration | eligible cohort patients are enriched |
| JSON profile loading | matched variables are preselected |
| binary code | leading zeroes and decoding meaning are preserved |
| exact duplicate | duplicate is counted and removed when the option is enabled |
| export construction | Excel, CSV, evidence report and profile are generated |

## 4. Temporal boundary validation

For every enabled phase, create observation dates exactly at window boundaries and immediately before and after them. Verify:

- assignment to the intended week or month interval;
- delay calculation against the selected reference;
- first-observation rule for non-cumulative windows;
- chronological preservation for cumulative columns;
- behaviour when `startD` or `endD` is missing.

## 5. Generated-file validation

Check:

- one final row per patient key;
- presence of selected treatment columns;
- exclusion of internal `_aria_*` columns;
- missing-value representation as `NA`;
- correspondence between announced schema and generated columns;
- successful opening of Excel workbooks without repair warnings;
- consistency between final patient count and evidence-report metrics;
- successful reload of the generated JSON profile.

## 6. Regression checklist after code changes

A change affecting loading, cleaning, cohort, profile, temporal or export modules should be followed by:

1. application launch test;
2. file-based test with the synthetic dataset;
3. affected unit or functional scenario;
4. boundary-date review when temporal code changes;
5. comparison of generated schema and evidence metrics;
6. opening of all downloaded artefacts.

## 7. Acceptance criteria

A version is accepted when all applicable scenarios pass, no blocking error appears in the interface, generated files open correctly and every warning reported by the evidence workbook is understood and documented.
