# -*- coding: utf-8 -*-
"""Fenêtres temporelles et agrégation des formulaires."""

import json
import re
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st

from utils.clean import join_nonempty_keep_order, nonempty_mask, normalize_pt_key
from utils.load import _iter_csv_chunks_from_upload
from utils.mapping import excel_date_string
from utils.text import norm_key

TEMPORAL_FIX_VERSION = "FINAL_2026_06_23_PERF_AND_PROFILE_DECODING"

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


def is_binary_checkbox_code(value: Any) -> bool:
    """Vrai pour les codes de cases à cocher de type 00100 ou 01001."""
    if pd.isna(value):
        return False
    s = str(value).strip()
    if s.lower() in {"", "nan", "<na>", "none", "na"}:
        return False
    s = re.sub(r"\.0+$", "", s)
    return bool(re.fullmatch(r"[01]{2,}", s))


def merge_binary_checkbox_codes(values: List[str]) -> str:
    """Fusionne plusieurs codes binaires par OU logique en préservant les zéros."""
    cleaned = [re.sub(r"\.0+$", "", str(v).strip()) for v in values]
    width = max(len(v) for v in cleaned)
    padded = [v.zfill(width) for v in cleaned]
    return "".join(
        "1" if any(v[i] == "1" for v in padded) else "0" for i in range(width)
    )


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


def append_empty_export_columns(out: pd.DataFrame, columns: List[str]) -> pd.DataFrame:
    """Ajoute plusieurs colonnes vides en une seule opération pandas.

    Pandas émet un `PerformanceWarning: DataFrame is highly fragmented` quand
    on ajoute des centaines de colonnes une par une avec `out[col] = ...`.
    Ici on construit les colonnes vides en bloc puis on concatène une seule fois,
    ce qui garde exactement le même résultat exporté mais évite la fragmentation.
    """
    if not columns:
        return out
    empty_block = pd.DataFrame({col: pd.NA for col in columns}, index=out.index)
    return pd.concat([out, empty_block], axis=1, copy=False)



def _is_truthy(value: Any) -> bool:
    """Interprète proprement les booléens issus d'un JSON/DataFrame profil."""
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    try:
        if pd.isna(value):
            return False
    except Exception:
        pass
    return str(value).strip().lower() in {"true", "1", "oui", "yes", "y", "vrai"}


def _safe_json_table(value: Any) -> Dict[str, Any]:
    """Récupère une table de décodage depuis dict ou chaîne JSON."""
    if isinstance(value, dict):
        return value
    if value is None:
        return {}
    try:
        if pd.isna(value):
            return {}
    except Exception:
        pass
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def _binary_code(value: Any, expected_length: Optional[int] = None) -> Optional[str]:
    """Normalise une valeur ARIA binaire en chaîne de 0/1.

    Exemples :
    - `0100` reste `0100` ;
    - `100.0` devient `100` ;
    - si la longueur attendue vaut 4, `10` devient `0010`.

    Cette correction par zfill est appliquée uniquement aux colonnes qui ont une
    table de décodage active dans le profil, donc elle ne touche pas les doses.
    """
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    raw = str(value).strip()
    if raw.lower() in {"", "nan", "<na>", "none", "na"}:
        return None
    raw = re.sub(r"\.0+$", "", raw)
    raw = re.sub(r"\s+", "", raw)
    if not re.fullmatch(r"[01]+", raw):
        return None
    if expected_length and len(raw) < expected_length:
        raw = raw.zfill(expected_length)
    return raw


def _entry_output(entry: Any, output_mode: str, fallback_label: str) -> Any:
    """Convertit une entrée de table en grade ou libellé."""
    if isinstance(entry, dict):
        if output_mode == "grade" and "grade" in entry:
            return entry.get("grade")
        if "label" in entry:
            return entry.get("label")
        if "grade" in entry:
            return entry.get("grade")
    return fallback_label


def _decode_profile_value(value: Any, table: Dict[str, Any], meta: Dict[str, Any]) -> Any:
    """Décode une valeur formulaire selon la table portée par le profil JSON."""
    if not table:
        return value

    decode_type = str(meta.get("type", "")).lower()
    output_mode = str(meta.get("output", "labels")).lower()
    if "graded" in decode_type or output_mode == "grade":
        output_mode = "grade"

    expected_length = meta.get("binary_length")
    try:
        expected_length = int(float(expected_length)) if expected_length not in (None, "") else None
    except Exception:
        expected_length = None

    raw = str(value).strip() if value is not None and not pd.isna(value) else ""
    raw_no_float = re.sub(r"\.0+$", "", raw)

    # Cas direct : valeur déjà numérique/grade et table du type {"0": ..., "1": ...}
    for key in (raw, raw_no_float):
        if key in table:
            return _entry_output(table[key], output_mode, key)

    code = _binary_code(value, expected_length=expected_length)
    if code is None:
        return value
    if set(code) == {"0"}:
        return pd.NA

    # Correspondance exacte, y compris après restauration des zéros à gauche.
    if code in table:
        return _entry_output(table[code], output_mode, code)

    width = expected_length or max((len(str(k)) for k in table.keys()), default=len(code))
    if len(code) != width:
        # Dernière tentative prudente : alignement à droite si les zéros à gauche
        # ont disparu lors de la lecture Excel/CSV.
        code = code.zfill(width)
        if code in table:
            return _entry_output(table[code], output_mode, code)

    # Multi-sélection : 1010 -> libellé position 1 + libellé position 3.
    labels: List[Any] = []
    grades: List[float] = []
    for i, bit in enumerate(code):
        if bit != "1":
            continue
        one_hot = "".join("1" if j == i else "0" for j in range(len(code)))
        entry = table.get(one_hot)
        if entry is None:
            continue
        decoded = _entry_output(entry, output_mode, one_hot)
        if output_mode == "grade":
            num = pd.to_numeric(pd.Series([decoded]), errors="coerce").iloc[0]
            if pd.notna(num):
                grades.append(float(num))
            elif decoded not in labels:
                labels.append(decoded)
        elif decoded not in labels:
            labels.append(decoded)

    if output_mode == "grade" and grades:
        max_grade = max(grades)
        return int(max_grade) if float(max_grade).is_integer() else max_grade
    if labels:
        return " ; ".join(str(x) for x in labels if pd.notna(x) and str(x).strip())
    return value


def _decoding_meta_from_row(row: pd.Series) -> Optional[Dict[str, Any]]:
    """Construit la config de décodage depuis une ligne du profil JSON.

    Cela rend le décodage indépendant de `app.py` : dès que le profil contient
    `Décodage actif`, `Type décodage` et `Table décodage`, `temporal.py` sait
    appliquer la conversion avant l'agrégation.
    """
    if not _is_truthy(row.get("Décodage actif", False)):
        return None
    table = _safe_json_table(row.get("Table décodage"))
    if not table:
        return None
    output = row.get("Décodage sortie", "labels")
    dtype = row.get("Type décodage", "")
    return {
        "table": {str(k).strip(): v for k, v in table.items()},
        "type": "" if pd.isna(dtype) else str(dtype),
        "output": "labels" if pd.isna(output) else str(output),
        "binary_length": row.get("Longueur code binaire", None),
    }


def decode_item_long_from_profile_row(item_long: pd.DataFrame, row: pd.Series) -> pd.DataFrame:
    """Applique le décodage profil sur la colonne `Donnee` d'un item long."""
    meta = _decoding_meta_from_row(row)
    if meta is None or item_long.empty or "Donnee" not in item_long.columns:
        return item_long
    out = item_long.copy()
    table = meta.pop("table")
    out["Donnee"] = out["Donnee"].map(lambda v: _decode_profile_value(v, table, meta))
    out = out[nonempty_mask(out["Donnee"])].copy()
    return out


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

    # Normalisation des dates au jour.
    # Cela évite les décalages d'un jour lorsque startD/endD contiennent une heure.
    long["DateHeure"] = pd.to_datetime(
        long["date_event"], errors="coerce"
    ).dt.normalize()

    long = long.merge(
        patient_base[["_pt_join_key", "startD", "endD"]],
        on="_pt_join_key",
        how="left",
    )

    long["startD"] = pd.to_datetime(long["startD"], errors="coerce").dt.normalize()
    long["endD"] = pd.to_datetime(long["endD"], errors="coerce").dt.normalize()

    long["delai_startD_jours"] = (long["DateHeure"] - long["startD"]).dt.days
    long["delai_endD_jours"] = (long["DateHeure"] - long["endD"]).dt.days

    # Diagnostics uniquement pour les doublons strictement identiques.
    # Les valeurs multiples le même jour sont résolues dans aggregate_subset().
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

    if sub.empty:
        return append_empty_export_columns(out, [val_col, date_col, delay_col])

    sub = sub.copy()

    # Normalisation forte des dates juste avant l'export.
    sub["DateHeure"] = pd.to_datetime(sub["DateHeure"], errors="coerce").dt.normalize()

    if "startD" in sub.columns:
        sub["startD"] = pd.to_datetime(sub["startD"], errors="coerce").dt.normalize()
    if "endD" in sub.columns:
        sub["endD"] = pd.to_datetime(sub["endD"], errors="coerce").dt.normalize()

    # Recalcul du délai à partir des dates normalisées.
    if delay_reference == "Fin RT / endD" and "endD" in sub.columns:
        sub["_delay_export"] = (sub["DateHeure"] - sub["endD"]).dt.days
    elif "startD" in sub.columns:
        sub["_delay_export"] = (sub["DateHeure"] - sub["startD"]).dt.days
    else:
        delay_src = (
            "delai_endD_jours"
            if delay_reference == "Fin RT / endD"
            else "delai_startD_jours"
        )
        sub["_delay_export"] = sub[delay_src] if delay_src in sub.columns else pd.NA

    sub["_date_str"] = sub["DateHeure"].map(excel_date_string)
    sub["_donnee_str"] = sub["Donnee"].astype(str).str.strip()

    def resolve_values_same_day(values: pd.Series) -> str:
        """Résout plusieurs valeurs observées pour une même variable le même jour.

        Règle :
        - valeurs identiques : garder une seule valeur ;
        - valeurs numériques : garder la valeur maximale ;
        - valeurs textuelles : garder la dernière valeur non vide.
        """
        vals = [
            str(v).strip()
            for v in values
            if pd.notna(v)
            and str(v).strip()
            and str(v).strip().lower() not in {"nan", "<na>", "na"}
        ]

        unique_vals = list(dict.fromkeys(vals))

        if not unique_vals:
            return pd.NA

        # Codes binaires de cases à cocher : ne jamais convertir en nombre.
        # Exemple : 00100 doit rester 00100, et plusieurs codes le même jour
        # sont fusionnés par OU logique (00100 + 00001 -> 00101).
        if all(is_binary_checkbox_code(v) for v in unique_vals):
            return merge_binary_checkbox_codes(unique_vals)

        if len(unique_vals) == 1:
            one = unique_vals[0]
            num = pd.to_numeric(pd.Series([one.replace(",", ".")]), errors="coerce")
            if num.notna().all():
                val = float(num.iloc[0])
                return str(int(val)) if val.is_integer() else str(val)
            return one

        numeric_vals = pd.to_numeric(
            pd.Series(unique_vals).str.replace(",", ".", regex=False),
            errors="coerce",
        )

        if numeric_vals.notna().all():
            max_val = float(numeric_vals.max())
            return str(int(max_val)) if max_val.is_integer() else str(max_val)

        return unique_vals[-1]

    # Étape 1 : une seule ligne par patient + variable + date.
    by_date = (
        sub.groupby(
            ["_pt_join_key", "item", "DateHeure"],
            as_index=False,
            sort=False,
            dropna=False,
        )
        .agg(
            _val=("_donnee_str", resolve_values_same_day),
            _date=("_date_str", "first"),
            _delay=("_delay_export", "first"),
        )
        .sort_values(["_pt_join_key", "DateHeure"], kind="stable")
    )

    # Règle demandée :
    # - colonnes cumulatives : garder toutes les observations ;
    # - colonnes non cumulatives : garder uniquement la première date de la fenêtre.
    is_cumulative_column = "Cumul" in prefix

    if not is_cumulative_column:
        first_by_patient = (
            by_date.groupby("_pt_join_key", as_index=False, sort=False)
            .first()
            .rename(columns={"_val": val_col, "_date": date_col, "_delay": delay_col})
        )
        return out.merge(
            first_by_patient[["_pt_join_key", val_col, date_col, delay_col]],
            on="_pt_join_key",
            how="left",
            validate="1:1",
        )

    agg = (
        by_date.groupby("_pt_join_key", as_index=False, sort=False)
        .agg(
            _val=("_val", join_nonempty_keep_order),
            _date=("_date", join_nonempty_keep_order),
            _delay=("_delay", join_nonempty_keep_order),
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
        return out.drop(columns=["_pt_join_key"], errors="ignore").copy(), pd.DataFrame()

    # Accès direct par item normalisé : évite de rescanner tout `forms_long`
    # et corrige les différences invisibles de noms de colonnes
    # (espaces finaux, espaces insécables, accents/mojibake réparables).
    forms_work = forms_long.copy()
    forms_work["_item_norm"] = forms_work["item"].map(norm_key)
    forms_by_item = {
        str(item_norm): grp.drop(columns=["_item_norm"], errors="ignore")
        for item_norm, grp in forms_work.groupby("_item_norm", sort=False, observed=True)
    }
    empty_item_long = forms_long.iloc[0:0].copy()
    max_pendant_week = max(pendant_weeks) if pendant_weeks else None

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
        item_long = forms_by_item.get(norm_key(source), empty_item_long)
        item_long = decode_item_long_from_profile_row(item_long, row)
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
            ]
            out = aggregate_subset(avant, out, f"{item}_CumulAnteRT", delay_reference)
            for w in avant_weeks:
                lo = item_long["startD"] - pd.to_timedelta(7 * w, unit="D")
                hi = item_long["startD"] - pd.to_timedelta(7 * (w - 1), unit="D")
                sub = item_long[
                    (item_long["DateHeure"] >= lo) & (item_long["DateHeure"] < hi)
                ]
                out = aggregate_subset(
                    sub, out, f"{item}_AvantRT_Semaine_{w:03d}", delay_reference
                )
        if phases.get("Aigu", False):
            aigu = item_long[
                (item_long["DateHeure"] >= item_long["startD"])
                & (item_long["DateHeure"] <= item_long["endD"])
            ]
            out = aggregate_subset(aigu, out, f"{item}_CumulAigu", delay_reference)
            for w in pendant_weeks:
                lo = item_long["startD"] + pd.to_timedelta(7 * (w - 1), unit="D")
                hi = item_long["startD"] + pd.to_timedelta(7 * w, unit="D")
                if max_pendant_week is not None and w == max_pendant_week:
                    sub = item_long[
                        (item_long["DateHeure"] >= lo)
                        & (item_long["DateHeure"] <= item_long["endD"])
                    ].copy()
                else:
                    sub = item_long[
                        (item_long["DateHeure"] >= lo) & (item_long["DateHeure"] < hi)
                    ]
                out = aggregate_subset(
                    sub, out, f"{item}_PendantRT_Semaines_{w:03d}", delay_reference
                )
        if phases.get("Tardif", False):
            tardif = item_long[item_long["DateHeure"] > item_long["endD"]]
            out = aggregate_subset(tardif, out, f"{item}_CumulTardif", delay_reference)
            for w in apres_weeks:
                lo = item_long["endD"] + pd.to_timedelta(7 * (w - 1), unit="D")
                hi = item_long["endD"] + pd.to_timedelta(7 * w, unit="D")
                sub = item_long[
                    (item_long["DateHeure"] > item_long["endD"])
                    & (item_long["DateHeure"] >= lo)
                    & (item_long["DateHeure"] < hi)
                ]
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
                ]
                out = aggregate_subset(sub, out, f"{item}_{label}", delay_reference)
    return out.drop(columns=["_pt_join_key"], errors="ignore").copy(), pd.DataFrame(
        schema_rows
    )
