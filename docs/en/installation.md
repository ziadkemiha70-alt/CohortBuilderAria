# Installation and startup

## 1. Purpose of this document

This guide covers the initial workstation setup, Python dependency installation, optional SQL Server connectivity and the first application launch. It does not describe cohort construction; that workflow is documented in [User guide](user_guide.md).

## 2. Workstation prerequisites

The workstation must provide:

- Windows 10 or Windows 11;
- a Python interpreter compatible with the versions declared in `requirements.txt`;
- read access to the project directory;
- write access to the local input and output directories used by the application;
- a Microsoft ODBC Driver for SQL Server when direct SQL extraction is required;
- network access to the ARIA SQL Server when direct extraction is used.

The application can also run without SQL access by loading previously extracted files.

## 3. Standard startup sequence

Open PowerShell in the project directory and run:

```powershell
cd "C:\path\to\CohortBuilderAria"
python -m pip install -r requirements.txt
python -m streamlit run app2.py
```

The dependency installation includes the libraries declared by the project, notably Streamlit, pandas, NumPy, pyodbc, openpyxl, xlsxwriter and skrub. Running `pip` through `python -m pip` ensures that dependencies are installed for the same interpreter that launches Streamlit.

## 4. SQL configuration file

For direct SQL extraction, create the following local file:

```text
.streamlit/secrets.toml
```

Example using Windows authentication:

```toml
[database]
driver = "ODBC Driver 18 for SQL Server"
server = "SERVER_NAME,1433"
database = "DATABASE_NAME"
username = ""
password = ""
trusted_connection = true
trust_server_certificate = true
```

Configuration fields:

| Field | Meaning |
|---|---|
| `driver` | Exact name of an installed ODBC SQL Server driver |
| `server` | SQL Server host name and, when required, TCP port |
| `database` | Database opened after authentication |
| `username` / `password` | SQL credentials only when SQL authentication is explicitly used |
| `trusted_connection` | Uses the current Windows account when set to `true` |
| `trust_server_certificate` | Accepts the server certificate without validating its chain |

The driver name must exactly match a driver reported by pyodbc. Depending on the workstation, the available value may be `ODBC Driver 17 for SQL Server` or `ODBC Driver 18 for SQL Server`.

## 5. Environment verification

Check Python:

```powershell
python --version
```

Check the installed packages and Streamlit:

```powershell
python -m pip --version
python -m streamlit --version
```

List the ODBC drivers visible to Python:

```powershell
python -c "import pyodbc; print(pyodbc.drivers())"
```

The value configured as `driver` in `secrets.toml` must appear exactly in this list.

## 6. Clear the Streamlit cache

After replacing a file, changing the code, or modifying the loading logic, stop the application with `Ctrl + C`, then run:

```powershell
python -m streamlit cache clear
python -m streamlit run app2.py
```

The first command clears Streamlit's persisted cache. The second command restarts the application with the updated files and functions.

## 7. First launch checklist

After running `python -m streamlit run app2.py`, confirm that:

1. the application header is displayed;
2. the tabs **Accueil**, **Import**, **Construction**, **Contrôle qualité**, **Sources** and **Profil** are available;
3. the **Import** tab offers both SQL extraction and existing-file modes;
4. the SQL connection test succeeds when direct extraction is configured;
5. no Python import error is displayed in PowerShell.

The application interface remains in French. English documentation therefore reproduces implementation labels in French whenever they must be located in the UI.

## 8. Operation without SQL Server access

Direct SQL connectivity is not required for file-based operation. Place previously generated sources in `inputs/`, or select another input directory in the **Import** tab. The expected source names and supported formats are described in [Input and output data](input_output_data.md).

## 9. Recommended local directory state

A typical executable project contains:

```text
CohortBuilderAria/
├── app2.py
├── requirements.txt
├── utils/
├── sql/
├── conf/
├── inputs/
├── outputs/
└── .streamlit/
    └── secrets.toml
```

The bilingual documentation does not create a second executable application. Both languages refer to this same directory and same configuration.
