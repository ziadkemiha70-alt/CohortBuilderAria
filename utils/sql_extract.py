# -*- coding: utf-8 -*-
"""Extraction SQL ARIA vers outputs/*.csv et outputs/*.xlsx.

Module isolé du reste de l'application :
- l'import Streamlit reste possible même si pyodbc n'est pas installé ;
- les scripts SQL restent dans sql/ ;
- les fichiers générés gardent les noms attendus par l'onglet Import.

Scripts attendus :
- query_aria__strasbourg.sql  -> traitement_patient.csv/.xlsx
- all_patient_ethos.sql       -> ethos_patient.csv/.xlsx
- all_patient_formulaire.sql  -> formulaire_patient.csv/.xlsx
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

# Ordre volontairement identique à l'ancien script Python : traitement, ETHOS, formulaire.
DEFAULT_SCRIPT_FILES: Dict[str, str] = {
    "traitement_patient": "query_aria__strasbourg.sql",
    "ethos_patient": "all_patient_ethos.sql",
    "formulaire_patient": "all_patient_formulaire.sql",
}

ILLEGAL_EXCEL_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F]")
EXCEL_CELL_LIMIT = 32767


def _load_pyodbc():
    try:
        import pyodbc  # type: ignore
        return pyodbc
    except Exception as exc:  # pragma: no cover - dépend de la machine utilisateur
        raise RuntimeError(
            "pyodbc n'est pas installé ou n'est pas accessible. Installe-le avec : pip install pyodbc"
        ) from exc


def build_connection_string(
    *,
    driver: str,
    server: str,
    database: str,
    trusted_connection: bool = True,
    trust_server_certificate: bool = True,
    username: str = "",
    password: str = "",
) -> str:
    parts: List[str] = [
        f"Driver={{{driver}}}",
        f"Server={server}",
        f"Database={database}",
    ]

    if trusted_connection:
        parts.append("Trusted_Connection=yes")
    else:
        if not username:
            raise ValueError("Nom d'utilisateur SQL manquant.")
        parts.append(f"UID={username}")
        parts.append(f"PWD={password}")

    if trust_server_certificate:
        parts.append("TrustServerCertificate=yes")

    return ";".join(parts) + ";"


def connect_sql(**kwargs):
    pyodbc = _load_pyodbc()
    conn_str = build_connection_string(**kwargs)
    return pyodbc.connect(conn_str)


def test_connection(**kwargs) -> str:
    t0 = time.perf_counter()
    with connect_sql(**kwargs) as conn:
        cur = conn.cursor()
        try:
            cur.execute("SELECT 1")
            cur.fetchone()
        finally:
            cur.close()
    return f"Connexion SQL réussie en {time.perf_counter() - t0:.2f} s."


def read_sql_script(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Script SQL introuvable : {path}")

    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin1"):
        try:
            return path.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="latin1")


def _split_sql_batches(sql_text: str) -> List[str]:
    """Découpe les scripts SQL Server sur les lignes GO isolées.

    Les tables temporaires restent disponibles sur la même connexion entre batches.
    """
    batches: List[str] = []
    current: List[str] = []
    for line in sql_text.splitlines():
        if re.match(r"^\s*GO\s*;?\s*$", line, flags=re.IGNORECASE):
            batch = "\n".join(current).strip()
            if batch:
                batches.append(batch)
            current = []
        else:
            current.append(line)
    batch = "\n".join(current).strip()
    if batch:
        batches.append(batch)
    return batches


def _rows_to_dataframe(rows, columns: List[str]) -> pd.DataFrame:
    # pyodbc.Row n'est pas toujours directement digéré de façon stable par pandas.
    return pd.DataFrame.from_records([tuple(r) for r in rows], columns=columns)


def execute_sql_to_dataframe(conn, sql_path: Path, limit_rows: Optional[int] = None) -> pd.DataFrame:
    """Exécute un script SQL et retourne le dernier result set tabulaire non vide.

    C'est volontairement proche de l'ancien script : on exécute le SQL complet,
    on parcourt les result sets, puis on garde la table finale exploitable.
    """
    sql_text = read_sql_script(sql_path)
    batches = _split_sql_batches(sql_text)
    cursor = conn.cursor()
    last_df = pd.DataFrame()

    try:
        for batch in batches:
            cursor.execute(batch)
            while True:
                if cursor.description is not None:
                    columns = [col[0] for col in cursor.description]
                    if limit_rows is not None and int(limit_rows) > 0:
                        rows = cursor.fetchmany(int(limit_rows))
                    else:
                        rows = cursor.fetchall()
                    candidate = _rows_to_dataframe(rows, columns)
                    # On garde la dernière table exploitable. Si elle est vide mais structurée,
                    # elle reste utile pour diagnostiquer le SQL.
                    last_df = candidate

                try:
                    has_next = cursor.nextset()
                except Exception:
                    has_next = False
                if not has_next:
                    break
    finally:
        cursor.close()

    return last_df


def clean_value_for_export(value):
    """Nettoie les valeurs problématiques pour CSV/XLSX.

    Important pour ARIA : certains champs SQL peuvent contenir du binaire brut
    ou des caractères de contrôle incompatibles Excel.
    """
    if isinstance(value, (bytes, bytearray, memoryview)):
        return f"<BINARY_{len(value)}_BYTES>"

    if isinstance(value, str):
        value = ILLEGAL_EXCEL_RE.sub("", value)
        if len(value) > EXCEL_CELL_LIMIT:
            return value[:EXCEL_CELL_LIMIT]
        return value

    return value


def clean_dataframe_for_export(df: pd.DataFrame) -> pd.DataFrame:
    df_clean = df.copy()
    for col in df_clean.columns:
        if df_clean[col].dtype == "object" or str(df_clean[col].dtype).startswith("string"):
            df_clean[col] = df_clean[col].map(clean_value_for_export)
    return df_clean


def export_dataframe(
    df: pd.DataFrame,
    output_dir: Path,
    base_name: str,
    write_xlsx: bool = True,
) -> Dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    df_export = clean_dataframe_for_export(df)

    csv_path = output_dir / f"{base_name}.csv"
    df_export.to_csv(csv_path, index=False, encoding="utf-8-sig")
    out = {"csv": str(csv_path)}

    if write_xlsx:
        xlsx_path = output_dir / f"{base_name}.xlsx"
        try:
            with pd.ExcelWriter(xlsx_path, engine="xlsxwriter") as writer:
                df_export.to_excel(writer, index=False, sheet_name="Data")
        except Exception:
            # Fallback si xlsxwriter n'est pas installé ; openpyxl est dans requirements_sql.
            with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
                df_export.to_excel(writer, index=False, sheet_name="Data")
        out["xlsx"] = str(xlsx_path)

    return out


def run_extraction_bundle(
    *,
    driver: str,
    server: str,
    database: str,
    trusted_connection: bool = True,
    trust_server_certificate: bool = True,
    username: str = "",
    password: str = "",
    sql_dir: str = "sql",
    output_dir: str = "outputs",
    write_xlsx: bool = True,
    limit_rows: Optional[int] = None,
    run_traitement: bool = True,
    run_formulaire: bool = True,
    run_ethos: bool = True,
) -> List[Dict[str, object]]:
    sql_dir_path = Path(sql_dir)
    output_dir_path = Path(output_dir)

    wanted = {
        "traitement_patient": run_traitement,
        "ethos_patient": run_ethos,
        "formulaire_patient": run_formulaire,
    }

    results: List[Dict[str, object]] = []
    total_t0 = time.perf_counter()

    with connect_sql(
        driver=driver,
        server=server,
        database=database,
        trusted_connection=trusted_connection,
        trust_server_certificate=trust_server_certificate,
        username=username,
        password=password,
    ) as conn:
        for base_name, enabled in wanted.items():
            if not enabled:
                continue

            script_name = DEFAULT_SCRIPT_FILES[base_name]
            script_path = sql_dir_path / script_name
            t0 = time.perf_counter()

            try:
                df = execute_sql_to_dataframe(conn, script_path, limit_rows=limit_rows)
                files = export_dataframe(df, output_dir_path, base_name, write_xlsx=write_xlsx)
                results.append(
                    {
                        "table": base_name,
                        "script": str(script_path),
                        "lignes": int(df.shape[0]),
                        "colonnes": int(df.shape[1]),
                        "csv": files.get("csv", ""),
                        "xlsx": files.get("xlsx", ""),
                        "temps_s": round(time.perf_counter() - t0, 2),
                        "statut": "OK",
                    }
                )
            except Exception as exc:
                results.append(
                    {
                        "table": base_name,
                        "script": str(script_path),
                        "lignes": 0,
                        "colonnes": 0,
                        "csv": "",
                        "xlsx": "",
                        "temps_s": round(time.perf_counter() - t0, 2),
                        "statut": f"ERREUR : {exc}",
                    }
                )

    results.append(
        {
            "table": "TOTAL",
            "script": "",
            "lignes": "",
            "colonnes": "",
            "csv": "",
            "xlsx": "",
            "temps_s": round(time.perf_counter() - total_t0, 2),
            "statut": "FIN",
        }
    )
    return results
