# -*- coding: utf-8 -*-
"""Exports CSV/XLSX final et rapport preuve."""

import io
from typing import Dict

import pandas as pd
import streamlit as st


def export_safe_df(df: pd.DataFrame) -> pd.DataFrame:
    """Prépare un DataFrame pour export sans casser les colonnes category.

    Les CSV sont lus en chaînes simples pour éviter les conflits de catégories pandas. Avant export, on remplace les valeurs manquantes par la chaîne `NA`.
    """
    if df is None or df.empty:
        return pd.DataFrame() if df is None else df.copy()
    safe = df.copy()
    for c in safe.columns:
        if pd.api.types.is_categorical_dtype(safe[c]):
            safe[c] = safe[c].astype(object)
    return safe.where(pd.notna(safe), "NA")


@st.cache_data(show_spinner=False)
def dataframe_to_csv_bytes(df: pd.DataFrame) -> bytes:
    return export_safe_df(df).to_csv(index=False, sep=";").encode("utf-8-sig")


@st.cache_data(show_spinner=False)
def workbook_bytes_final(df: pd.DataFrame) -> bytes:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        safe = export_safe_df(df)
        safe.to_excel(writer, index=False, sheet_name="Export_final")
        wb = writer.book
        ws = writer.sheets["Export_final"]
        header_fmt = wb.add_format(
            {"bold": True, "bg_color": "#243FC4", "font_color": "#FFFFFF", "border": 1}
        )
        cum_fmt = wb.add_format({"bg_color": "#EAF5FF"})
        avant_fmt = wb.add_format({"bg_color": "#F0F4FF"})
        aigu_fmt = wb.add_format({"bg_color": "#FFF3E6"})
        tardif_fmt = wb.add_format({"bg_color": "#EFFFF5"})
        base_fmt = wb.add_format({"bg_color": "#F8FAFC"})
        for j, col in enumerate(safe.columns):
            ws.write(0, j, col, header_fmt)
            width = min(max(len(str(col)) + 2, 12), 42)
            ws.set_column(j, j, width)
            fmt = base_fmt
            if "CumulAnteRT" in col or "AvantRT" in col:
                fmt = avant_fmt
            elif "CumulAigu" in col or "PendantRT" in col:
                fmt = aigu_fmt
            elif "CumulTardif" in col or "ApresRT" in col or "Mois " in col:
                fmt = tardif_fmt
            elif "_Cumul" in col:
                fmt = cum_fmt
            ws.set_column(j, j, width, fmt)
        ws.freeze_panes(1, 1)
        ws.autofilter(0, 0, max(len(safe), 1), max(len(safe.columns) - 1, 0))
    return output.getvalue()


@st.cache_data(show_spinner=False)
def workbook_bytes_proof(sheets: Dict[str, pd.DataFrame]) -> bytes:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        wb = writer.book
        header = wb.add_format(
            {"bold": True, "bg_color": "#162A8F", "font_color": "#FFFFFF", "border": 1}
        )
        ok = wb.add_format({"bg_color": "#ECFDF5", "font_color": "#047857"})
        warn = wb.add_format({"bg_color": "#FFF7ED", "font_color": "#B45309"})
        for name, df in sheets.items():
            safe = export_safe_df(df)
            sheet = name[:31]
            safe.to_excel(writer, index=False, sheet_name=sheet)
            ws = writer.sheets[sheet]
            for j, col in enumerate(safe.columns):
                ws.write(0, j, col, header)
                ws.set_column(j, j, min(max(len(str(col)) + 2, 12), 45))
            ws.freeze_panes(1, 0)
            if "niveau" in safe.columns:
                idx = list(safe.columns).index("niveau")
                for i, val in enumerate(safe["niveau"].astype(str).tolist(), start=1):
                    ws.write(i, idx, val, ok if val == "OK" else warn)
    return output.getvalue()
