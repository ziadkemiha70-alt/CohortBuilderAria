# Troubleshooting

## The application does not start

Verify Python and reinstall the declared dependencies with the same interpreter:

```powershell
python --version
python -m pip install -r requirements.txt
python -m streamlit run app2.py
```

When `python` is not recognised, the Python installation directory is not available through the current Windows `Path`, or the terminal was opened before the environment change.

## `No module named streamlit` or another missing module

Run:

```powershell
python -m pip install -r requirements.txt
```

Then launch Streamlit with the same `python` command. Using different Python installations for package installation and execution produces this error even when the package exists elsewhere on the workstation.

## No ODBC driver is available

List drivers visible to pyodbc:

```powershell
python -c "import pyodbc; print(pyodbc.drivers())"
```

Install or select an available Microsoft ODBC Driver for SQL Server, then set `driver` in `.streamlit/secrets.toml` to the exact reported name.

## ODBC error `IM002`

`IM002` indicates that the configured data source or driver name cannot be resolved. Confirm that:

- the driver is installed for the workstation architecture;
- its name exactly matches `pyodbc.drivers()`;
- the `driver` value does not contain a spelling difference;
- Streamlit was restarted after configuration changes.

## SQL login error `18456`

Error `18456` means that SQL Server was reached but rejected authentication. With `trusted_connection = true`, the current Windows account is used. Test the same server through SQL Server Management Studio using Windows Authentication. If SSMS also fails, the database administrator must verify login and database permissions.

## General SQL connection failure

Check, in order:

1. ODBC driver name;
2. server name and TCP port;
3. database name;
4. access to the institution network;
5. authentication mode;
6. `trust_server_certificate` value;
7. Windows or SQL account permissions.

Use **Tester la connexion** before starting the three extractions.

## SQL script not found

The configured `sql/` directory must contain:

```text
query_aria__strasbourg.sql
all_patient_formulaire.sql
all_patient_ethos.sql
```

Also verify the **Dossier des scripts SQL** value in the **Import** tab.

## Source files are not detected

Check:

- the input directory selected in **Import**;
- the logical base name of each file;
- the `.csv`, `.xlsx` or `.zip` extension;
- read permissions on the directory;
- whether the file is nested one folder deeper than expected.

## Required `pt_id` or `date_event` column is missing

Both columns are required in `formulaire_patient`. Check the file header and confirm that delimiter parsing has not shifted the columns.

## CSV reading error or shifted columns

The loader handles common delimiters and double quotes. When parsing fails:

- confirm that every row uses the same delimiter;
- check for unclosed quote characters;
- re-export as UTF-8 CSV using comma or semicolon;
- stop the application, clear the Streamlit cache with the command below, and restart;
- test a smaller sample containing the same problematic row structure.

## Clear the Streamlit cache

Stop the application with `Ctrl + C`, then run:

```powershell
python -m streamlit cache clear
python -m streamlit run app2.py
```

This procedure is useful when an old file, an old CSV header, or a previous version of a function still appears to be used after a correction.

## Memory error with a large form table

Prefer direct CSV or ZIP-wrapped CSV, reduce the number of selected variables and leave optional counters disabled. The construction pipeline reloads selected columns in chunks to reduce peak memory use.

## No treatment patient matches the form source

Compare `pt_id` values across the sources and review:

- leading zeroes;
- decimal suffixes introduced by Excel;
- use of a technical identifier versus a displayed identifier;
- empty cells;
- invisible or non-numeric characters;
- different identifier systems without a shared value.

The application normalises identifiers but cannot infer a correspondence when the two sources contain unrelated identifiers.

## The profile does not find some variables

Open the profile-matching diagnostic. Confirm the stored source label and use tolerant search. Accents, spaces and common encoding variations are handled, but a genuinely renamed variable requires manual association.

## The export contains many `NA` columns

Review enabled phases, temporal windows and actual value availability in the selected cohort. Entirely empty columns can be removed at download time. Also check whether the profile was created from a form version containing variables absent from the current source.
