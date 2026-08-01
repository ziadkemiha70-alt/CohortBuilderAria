# -*- coding: utf-8 -*-
"""
Pipeline ARIA simple : 3 SQL -> 3 CSV + 3 XLSX

- Traitement : query_aria__strasbourg.sql
- ETHOS      : all_patient_ethos.sql
- Formulaire : all_patient_formulaire.sql

Aucune fusion, aucun mapping, aucun regle.xlsx.
Le script peut être lancé depuis la racine OU depuis le dossier scripts/.
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Optional
import streamlit as st
import pandas as pd
import pyodbc


# =============================================================================
# Chemins projet
# =============================================================================
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent if SCRIPT_DIR.name.lower() == "scripts" else SCRIPT_DIR
SQL_DIR = PROJECT_ROOT / "sql"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# =============================================================================
# Nettoyage export
# =============================================================================
ILLEGAL_EXCEL_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F]")
EXCEL_CELL_LIMIT = 32767


def clean_value_for_export(value):
    """Nettoie les valeurs problématiques pour CSV/XLSX."""
    if isinstance(value, (bytes, bytearray, memoryview)):
        return f"<BINARY_{len(value)}_BYTES>"

    if isinstance(value, str):
        value = ILLEGAL_EXCEL_RE.sub("", value)
        # Excel tronque de toute façon au-delà de 32767 caractères.
        # On le fait explicitement pour éviter les warnings xlsxwriter.
        if len(value) > EXCEL_CELL_LIMIT:
            return value[:EXCEL_CELL_LIMIT]
        return value

    return value


def clean_dataframe_for_export(df: pd.DataFrame) -> pd.DataFrame:
    """Prépare une copie du DataFrame pour l'export."""
    df_clean = df.copy()
    for col in df_clean.columns:
        if df_clean[col].dtype == "object" or str(df_clean[col].dtype).startswith("string"):
            df_clean[col] = df_clean[col].map(clean_value_for_export)
    return df_clean


def save_csv_and_xlsx(df: pd.DataFrame, output_stem: str) -> None:
    """Sauvegarde un DataFrame en CSV et XLSX dans outputs/."""
    csv_path = OUTPUT_DIR / f"{output_stem}.csv"
    xlsx_path = OUTPUT_DIR / f"{output_stem}.xlsx"

    df_export = clean_dataframe_for_export(df)

    df_export.to_csv(csv_path, index=False, encoding="utf-8-sig")
    print(f"✅ CSV sauvegardé  : {csv_path} ({df_export.shape[0]} lignes × {df_export.shape[1]} colonnes)")

    with pd.ExcelWriter(xlsx_path, engine="xlsxwriter") as writer:
        df_export.to_excel(writer, index=False, sheet_name="Data")
    print(f"✅ XLSX sauvegardé : {xlsx_path} ({df_export.shape[0]} lignes × {df_export.shape[1]} colonnes)")


# =============================================================================
# SQL
# =============================================================================
def read_sql_file(sql_path: Path) -> str:
    """Lit un fichier SQL et supprime les éventuels GO isolés."""
    if not sql_path.exists():
        raise FileNotFoundError(f"Fichier SQL introuvable : {sql_path}")

    sql_script = sql_path.read_text(encoding="utf-8-sig")
    sql_script = re.sub(r"(?im)^\s*GO\s*$", "", sql_script)
    return sql_script


def execute_sql_to_dataframe(connexion: pyodbc.Connection, sql_path: Path) -> pd.DataFrame:
    """Exécute un script SQL complet et retourne le premier jeu de résultats SELECT."""
    print(f"\n🚀 Exécution SQL : {sql_path.name}")
    t0 = time.time()
    sql_script = read_sql_file(sql_path)

    cursor = connexion.cursor()
    try:
        cursor.execute(sql_script)

        while True:
            if cursor.description is not None:
                columns = [col[0] for col in cursor.description]
                rows = cursor.fetchall()
                df = pd.DataFrame.from_records(rows, columns=columns)
                print(f"⏱️ Temps SQL : {time.time() - t0:.2f} secondes")
                print(f"✅ Résultat : {df.shape[0]} lignes × {df.shape[1]} colonnes")
                return df

            if not cursor.nextset():
                break

        print(f"⚠️ Aucun SELECT exploitable retourné par {sql_path.name}")
        return pd.DataFrame()

    finally:
        cursor.close()


# =============================================================================
# Classe principale avec TES identifiants / connexion
# =============================================================================
class AnalyseurPatient:
    def __init__(self):
        self.connexion: Optional[pyodbc.Connection] = None
        self.cursor: Optional[pyodbc.Cursor] = None

    def connecter_bdd(self):
    try:
        db = st.secrets["database"]

        self.connexion = pyodbc.connect(
            f"DRIVER={{{db['driver']}}};"
            f"SERVER={db['server']};"
            f"DATABASE={db['database']};"
            f"Trusted_Connection={'yes' if db.get('trusted_connection', True) else 'no'};"
            f"TrustServerCertificate={'yes' if db.get('trust_server_certificate', True) else 'no'};"
        )

        self.cursor = self.connexion.cursor()
        print("Connexion à la base de données réussie ✅")

    except Exception as e:
        print("Erreur de connexion à la base de données ❌")
        print(e)
        raise

    def fermer_bdd(self):
        if self.cursor is not None:
            try:
                self.cursor.close()
            except Exception:
                pass
            self.cursor = None

        if self.connexion is not None:
            try:
                self.connexion.close()
            except Exception:
                pass
            self.connexion = None

    def executer_requete(self, sql_filename: str, output_stem: str) -> None:
        if self.connexion is None:
            raise RuntimeError("Connexion non initialisée. Appelle connecter_bdd() avant.")

        sql_path = SQL_DIR / sql_filename
        df = execute_sql_to_dataframe(self.connexion, sql_path)
        save_csv_and_xlsx(df, output_stem)

    def executer(self):
        print("==============================================")
        print("PIPELINE ARIA SIMPLE : 3 SQL -> 3 CSV + 3 XLSX")
        print("==============================================")
        print(f"Racine projet : {PROJECT_ROOT}")
        print(f"Dossier SQL   : {SQL_DIR}")
        print(f"Sorties       : {OUTPUT_DIR}")

        t0 = time.time()
        self.connecter_bdd()

        try:
            # 1) Nouveau traitement Strasbourg
            self.executer_requete(
                "query_aria__strasbourg.sql",
                "traitement_patient",
            )

            # 2) ETHOS conservé séparé
            self.executer_requete(
                "all_patient_ethos.sql",
                "ethos_patient",
            )

            # 3) Formulaires / toxicités / questionnaires
            self.executer_requete(
                "all_patient_formulaire.sql",
                "formulaire_patient",
            )

        finally:
            self.fermer_bdd()

        print("\n🎉 Extractions terminées")
        print(f"⏱️ Temps total : {(time.time() - t0) / 60:.2f} minutes")
        print("\nFichiers attendus :")
        print("- outputs/traitement_patient.csv")
        print("- outputs/traitement_patient.xlsx")
        print("- outputs/ethos_patient.csv")
        print("- outputs/ethos_patient.xlsx")
        print("- outputs/formulaire_patient.csv")
        print("- outputs/formulaire_patient.xlsx")


if __name__ == "__main__":
    AnalyseurPatient().executer()
