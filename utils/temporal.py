# -*- coding: utf-8 -*-
"""Fenêtres temporelles et agrégation des formulaires."""

import re
from typing import Any, Dict, List, Tuple

import pandas as pd
import streamlit as st

from utils.clean import join_nonempty_keep_order, nonempty_mask, normalize_pt_key
from utils.load import _iter_csv_chunks_from_upload
from utils.mapping import excel_date_string

DEFAULT_AVANT_WEEKS = [71, 48, 41, 40, 37, 29, 13, 10, 8, 7, 6, 5, 4, 3, 2, 1]
DEFAULT_PENDANT_WEEKS = [1, 2, 3, 4, 5, 6, 7]
DEFAULT_APRES_WEEKS = [1, 8]
DEFAULT_MONTH_BINS = [
    (1, 1, "Mois 01"),
    (2, 4, "Mois 02 - 04"),
    (5, 7, "Mois 05 - 07"),
    (8, 10, "Mois 08 - 10"),
    (11, 13, "Mois 11 - 13"),
    (14, 16, "Mois 14 - 16"),
    (17, 19, "Mois 17 - 19"),
    (20, 22, "Mois 20 - 22"),
    (23, 25, "Mois 23 - 25"),
    (26, 31, "Mois 26 - 31"),
    (32, 37, "Mois 32 - 37"),
    (38, 43, "Mois 38 - 43"),
    (44, 49, "Mois 44 - 49"),
    (50, 55, "Mois 50 - 55"),
    (56, 61, "Mois 56 - 61"),
    (62, 9999, "Mois 62 et plus"),
]


def parse_int_list(text: str, default: List[int]) -> List[int]:
    if not str(text).strip():
        return default
    vals: List[int] = []
    for x in re.split(r"[,;\s]+", str(text)):
        if not x.strip():
            continue
        try:
            vals.append(int(x))
        except ValueError:
            pass
    return vals or default


def build_schema_for_item(
    item: str,
    phases: Dict[str, bool],
    avant_weeks: List[int],
    pendant_weeks: List[int],
    apres_weeks: List[int],
    month_bins: List[Tuple[int, int, str]],
) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []

    def add(col: str, block: str, bucket: str = ""):
        rows.append(
            {"item": item, "bloc": block, "bucket": bucket, "colonne_export": col}
        )

    if phases.get("Cumul", True):
        for suf in ["", "_Date", "_Delai"]:
            add(f"{item}_Cumul{suf}", "Cumul")
    if phases.get("Avant RT", False):
        for suf in ["", "_Date", "_Delai"]:
            add(f"{item}_CumulAnteRT{suf}", "Avant RT", "CumulAnteRT")
        for w in avant_weeks:
            ww = f"{w:03d}"
            for suf in ["", "_Date", "_Delai"]:
                add(f"{item}_AvantRT_Semaine_{ww}{suf}", "Avant RT", f"Semaine {ww}")
    if phases.get("Aigu", False):
        for suf in ["", "_Date", "_Delai"]:
            add(f"{item}_CumulAigu{suf}", "Aigu", "CumulAigu")
        for w in pendant_weeks:
            ww = f"{w:03d}"
            for suf in ["", "_Date", "_Delai"]:
                add(f"{item}_PendantRT_Semaines_{ww}{suf}", "Aigu", f"Semaine {ww}")
    if phases.get("Tardif", False):
        for suf in ["", "_Date", "_Delai"]:
            add(f"{item}_CumulTardif{suf}", "Tardif", "CumulTardif")
        for w in apres_weeks:
            ww = f"{w:03d}"
            for suf in ["", "_Date", "_Delai"]:
                add(f"{item}_ApresRT_Semaine_{ww}{suf}", "Tardif", f"Semaine {ww}")
        for _, _, label in month_bins:
            for suf in ["", "_Date", "_Delai"]:
                add(f"{item}_{label}{suf}", "Tardif", label)
    return rows


def prepare_forms_long(
    fm: pd.DataFrame,
    patient_base: pd.DataFrame,
    selected_cols: List[str],
    deduplicate: bool,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    needed = ["pt_id", "_pt_join_key", "date_event"] + selected_cols
    missing = [
        c for c in ["pt_id", "_pt_join_key", "date_event"] if c not in fm.columns
    ]
    if missing:
        raise ValueError(f"Colonnes manquantes dans le formulaire : {missing}")
    cohort_keys = set(patient_base["_pt_join_key"].dropna())
    work = fm[[c for c in needed if c in fm.columns]].copy()
    work = work[work["_pt_join_key"].isin(cohort_keys)].copy()
    if not selected_cols:
        return pd.DataFrame(), pd.DataFrame()
    long = work.melt(
        id_vars=["pt_id", "_pt_join_key", "date_event"],
        value_vars=[c for c in selected_cols if c in work.columns],
        var_name="item",
        value_name="Donnee",
    )
    long = long[nonempty_mask(long["Donnee"])].copy()
    long["DateHeure"] = pd.to_datetime(long["date_event"], errors="coerce")
    long = long.merge(
        patient_base[["_pt_join_key", "startD", "endD"]], on="_pt_join_key", how="left"
    )
    long["delai_startD_jours"] = (long["DateHeure"] - long["startD"]).dt.days
    long["delai_endD_jours"] = (long["DateHeure"] - long["endD"]).dt.days
    dup_cols = ["_pt_join_key", "item", "DateHeure", "Donnee"]
    duplicates = long[long.duplicated(dup_cols, keep=False)].copy()
    if deduplicate:
        long = long.drop_duplicates(dup_cols, keep="first").copy()
    return (
        long.sort_values(["_pt_join_key", "item", "DateHeure"], kind="stable"),
        duplicates,
    )


def aggregate_subset(
    sub: pd.DataFrame, out: pd.DataFrame, prefix: str, delay_reference: str
) -> pd.DataFrame:
    val_col, date_col, delay_col = prefix, f"{prefix}_Date", f"{prefix}_Delai"
    delay_src = (
        "delai_endD_jours"
        if delay_reference == "Fin RT / endD"
        else "delai_startD_jours"
    )
    if sub.empty:
        out[val_col] = pd.NA
        out[date_col] = pd.NA
        out[delay_col] = pd.NA
        return out
    sub = sub.copy()
    sub["_date_str"] = sub["DateHeure"].map(excel_date_string)
    agg = (
        sub.groupby("_pt_join_key", as_index=False, sort=False)
        .agg(
            _val=("Donnee", join_nonempty_keep_order),
            _date=("_date_str", join_nonempty_keep_order),
            _delay=(delay_src, join_nonempty_keep_order),
        )
        .rename(columns={"_val": val_col, "_date": date_col, "_delay": delay_col})
    )
    return out.merge(agg, on="_pt_join_key", how="left", validate="1:1")


@st.cache_data(show_spinner=False)
def build_generic_item_block(
    patient_base: pd.DataFrame,
    forms_long: pd.DataFrame,
    config: pd.DataFrame,
    delay_reference: str,
    avant_weeks: List[int],
    pendant_weeks: List[int],
    apres_weeks: List[int],
    month_bins: List[Tuple[int, int, str]],
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    out = (
        patient_base[["_pt_join_key", "Patient ID"]]
        .drop_duplicates("_pt_join_key")
        .copy()
    )
    schema_rows: List[Dict[str, str]] = []
    if forms_long.empty or config.empty:
        return out.drop(columns=["_pt_join_key"], errors="ignore"), pd.DataFrame()
    for _, row in config.iterrows():
        if not bool(row.get("Inclure", True)):
            continue
        item = str(row["Nom export"] or row["Colonne formulaire"])
        source = str(row["Colonne formulaire"])
        phases = {
            "Cumul": bool(row.get("Cumul", True)),
            "Avant RT": bool(row.get("Avant RT", False)),
            "Aigu": bool(row.get("Aigu", False)),
            "Tardif": bool(row.get("Tardif", False)),
        }
        item_long = forms_long[forms_long["item"].eq(source)].copy()
        for r in build_schema_for_item(
            item, phases, avant_weeks, pendant_weeks, apres_weeks, month_bins
        ):
            r["colonne_formulaire_source"] = source
            schema_rows.append(r)
        if phases.get("Cumul", True):
            out = aggregate_subset(item_long, out, f"{item}_Cumul", delay_reference)
        if phases.get("Avant RT", False):
            avant = item_long[
                (
                    item_long["DateHeure"]
                    >= item_long["startD"] - pd.Timedelta(days=5000)
                )
                & (item_long["DateHeure"] < item_long["startD"])
            ].copy()
            out = aggregate_subset(avant, out, f"{item}_CumulAnteRT", delay_reference)
            for w in avant_weeks:
                lo = item_long["startD"] - pd.to_timedelta(7 * w, unit="D")
                hi = item_long["startD"] - pd.to_timedelta(7 * (w - 1), unit="D")
                sub = item_long[
                    (item_long["DateHeure"] >= lo) & (item_long["DateHeure"] < hi)
                ].copy()
                out = aggregate_subset(
                    sub, out, f"{item}_AvantRT_Semaine_{w:03d}", delay_reference
                )
        if phases.get("Aigu", False):
            aigu = item_long[
                (item_long["DateHeure"] >= item_long["startD"])
                & (item_long["DateHeure"] <= item_long["endD"])
            ].copy()
            out = aggregate_subset(aigu, out, f"{item}_CumulAigu", delay_reference)
            for w in pendant_weeks:
                lo = item_long["startD"] + pd.to_timedelta(7 * (w - 1), unit="D")
                hi = item_long["startD"] + pd.to_timedelta(7 * w, unit="D")
                if w == max(pendant_weeks):
                    sub = item_long[
                        (item_long["DateHeure"] >= lo)
                        & (item_long["DateHeure"] <= item_long["endD"])
                    ].copy()
                else:
                    sub = item_long[
                        (item_long["DateHeure"] >= lo) & (item_long["DateHeure"] < hi)
                    ].copy()
                out = aggregate_subset(
                    sub, out, f"{item}_PendantRT_Semaines_{w:03d}", delay_reference
                )
        if phases.get("Tardif", False):
            tardif = item_long[item_long["DateHeure"] > item_long["endD"]].copy()
            out = aggregate_subset(tardif, out, f"{item}_CumulTardif", delay_reference)
            for w in apres_weeks:
                lo = item_long["endD"] + pd.to_timedelta(7 * (w - 1), unit="D")
                hi = item_long["endD"] + pd.to_timedelta(7 * w, unit="D")
                sub = item_long[
                    (item_long["DateHeure"] > item_long["endD"])
                    & (item_long["DateHeure"] >= lo)
                    & (item_long["DateHeure"] < hi)
                ].copy()
                out = aggregate_subset(
                    sub, out, f"{item}_ApresRT_Semaine_{w:03d}", delay_reference
                )
            months_after = (
                item_long["DateHeure"] - item_long["endD"]
            ).dt.days / 30.4375
            for m1, m2, label in month_bins:
                mask = (
                    months_after >= m1
                    if m2 >= 9999
                    else ((months_after >= m1) & (months_after <= m2))
                )
                sub = item_long[
                    (item_long["DateHeure"] > item_long["endD"]) & mask
                ].copy()
                out = aggregate_subset(sub, out, f"{item}_{label}", delay_reference)
    return out.drop(columns=["_pt_join_key"], errors="ignore"), pd.DataFrame(
        schema_rows
    )
