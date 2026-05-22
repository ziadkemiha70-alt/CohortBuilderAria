# -*- coding: utf-8 -*-
"""Construction de cohorte depuis traitement_patient et intégration ETHOS."""

import re
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st

from utils.clean import (
    first_nonempty,
    join_unique_nonempty,
    nonempty_mask,
    normalize_cim10,
)
from utils.text import find_col_by_norm


def resolve_treatment_columns(tx: pd.DataFrame) -> Dict[str, Optional[str]]:
    return {
        "patient_id": find_col_by_norm(
            tx.columns, ["PatientId", "Patient ID", "IdPatient", "Patient_ID"]
        ),
        "dose": find_col_by_norm(
            tx.columns,
            ["DoseEffectuée2", "DoseEffectuee2", "Dose effectuée", "DoseEffectuee"],
        ),
        "nb_fractions": find_col_by_norm(
            tx.columns,
            ["NbFractionsEffectués", "NbFractionsEffectues", "Nombre fractions"],
        ),
        "start": find_col_by_norm(
            tx.columns,
            ["PremiereFractionChamp", "Première fraction", "Date première fraction"],
        ),
        "end": find_col_by_norm(
            tx.columns,
            ["DerniereFractionChamp", "Dernière fraction", "Date dernière fraction"],
        ),
        "cim": find_col_by_norm(
            tx.columns, ["DiagnosisCode", "Code CIM", "CIM10", "Code_CIM_Diagnostic"]
        ),
    }


def _is_nonempty_column(df: pd.DataFrame, col: Optional[str]) -> pd.Series:
    if col is None or col not in df.columns:
        return pd.Series(False, index=df.index)
    return nonempty_mask(df[col])


def prepare_ethos_treatment(ethos: pd.DataFrame) -> pd.DataFrame:
    """Prépare le fichier ETHOS comme source de traitement supplémentaire.

    ETHOS contient beaucoup de lignes associées à des plans, volumes, organes ou
    prescriptions. Pour ne pas polluer la cohorte, on garde uniquement les lignes
    réellement exploitables côté traitement : dates de début/fin et dose réalisée
    renseignées. On ne filtre pas uniquement sur NomMachine == ETHOS, car certaines
    lignes datées peuvent avoir une machine vide.
    """
    if ethos is None or ethos.empty:
        return pd.DataFrame()

    out = ethos.copy()
    out["_source_traitement"] = "ethos"

    cols = resolve_treatment_columns(out)
    start_col = cols.get("start")
    end_col = cols.get("end")
    dose_col = cols.get("dose")

    required_masks = []
    for col in [start_col, end_col, dose_col]:
        if col and col in out.columns:
            required_masks.append(_is_nonempty_column(out, col))

    if required_masks:
        keep = required_masks[0].copy()
        for mask in required_masks[1:]:
            keep &= mask
        out = out[keep].copy()

    if dose_col and dose_col in out.columns:
        dose = pd.to_numeric(
            out[dose_col].astype("string").str.replace(",", ".", regex=False),
            errors="coerce",
        )
        out = out[dose.fillna(0) != 0].copy()

    return out.drop_duplicates(ignore_index=True)


def merge_standard_and_ethos_treatments(
    standard_tx: pd.DataFrame,
    ethos_tx: pd.DataFrame,
) -> pd.DataFrame:
    """Fusionne traitement_patient standard et ethos_patient optionnel."""
    standard = standard_tx.copy() if standard_tx is not None else pd.DataFrame()
    if not standard.empty:
        standard["_source_traitement"] = "standard"

    ethos = prepare_ethos_treatment(ethos_tx)

    if standard.empty and ethos.empty:
        return pd.DataFrame()
    if ethos.empty:
        return standard.drop_duplicates(ignore_index=True)
    if standard.empty:
        return ethos.drop_duplicates(ignore_index=True)

    merged = pd.concat([standard, ethos], ignore_index=True, sort=False)
    return merged.drop_duplicates(ignore_index=True)


def build_ethos_integration_report(
    standard_tx: pd.DataFrame,
    ethos_tx: pd.DataFrame,
    merged_tx: pd.DataFrame,
) -> pd.DataFrame:
    """Rapport court de traçabilité pour l'intégration ETHOS."""
    rows: List[Dict[str, Any]] = []

    def _patient_count(df: pd.DataFrame) -> int:
        if df is None or df.empty:
            return 0
        patient_col = find_col_by_norm(
            df.columns, ["PatientId", "Patient ID", "IdPatient", "Patient_ID", "pt_id"]
        )
        if not patient_col:
            return 0
        return int(
            df[patient_col]
            .dropna()
            .astype(str)
            .str.strip()
            .replace("", pd.NA)
            .dropna()
            .nunique()
        )

    rows.append(
        {
            "contrôle": "Lignes traitement standard lues",
            "résultat": int(len(standard_tx)) if standard_tx is not None else 0,
            "niveau": "Info",
        }
    )
    rows.append(
        {
            "contrôle": "Patients traitement standard lus",
            "résultat": _patient_count(standard_tx),
            "niveau": "Info",
        }
    )

    if ethos_tx is None or ethos_tx.empty:
        rows.append(
            {
                "contrôle": "Fichier ETHOS chargé",
                "résultat": "Non",
                "niveau": "Info",
            }
        )
        return pd.DataFrame(rows)

    ethos_prepared = prepare_ethos_treatment(ethos_tx)
    rows.extend(
        [
            {
                "contrôle": "Fichier ETHOS chargé",
                "résultat": "Oui",
                "niveau": "Info",
            },
            {
                "contrôle": "Lignes ETHOS lues",
                "résultat": int(len(ethos_tx)),
                "niveau": "Info",
            },
            {
                "contrôle": "Patients ETHOS lus",
                "résultat": _patient_count(ethos_tx),
                "niveau": "Info",
            },
            {
                "contrôle": "Lignes ETHOS conservées après filtre dates + dose",
                "résultat": int(len(ethos_prepared)),
                "niveau": "OK" if len(ethos_prepared) > 0 else "A vérifier",
            },
            {
                "contrôle": "Patients ETHOS conservés après filtre",
                "résultat": _patient_count(ethos_prepared),
                "niveau": "OK" if _patient_count(ethos_prepared) > 0 else "A vérifier",
            },
            {
                "contrôle": "Lignes traitement totales après fusion",
                "résultat": int(len(merged_tx)) if merged_tx is not None else 0,
                "niveau": "Info",
            },
        ]
    )

    return pd.DataFrame(rows)


@st.cache_data(show_spinner=False)
def filter_cohort(
    tx: pd.DataFrame,
    tx_cols: Dict[str, Optional[str]],
    cim10_text: str,
    mode_cim10: str,
    dose_non_nulle: bool,
) -> pd.DataFrame:
    out = tx.copy()
    cim_col = tx_cols.get("cim")
    if cim_col and cim10_text.strip():
        raw_wanted = [c for c in re.split(r"[,;\s]+", cim10_text) if c.strip()]
        wanted = (
            normalize_cim10(pd.Series(raw_wanted, dtype="string"))
            .dropna()
            .astype(str)
            .tolist()
        )
        wanted = [w for w in wanted if w]
        norm = normalize_cim10(out[cim_col])
        cim_mask = (
            norm.apply(lambda v: any(str(v).startswith(w) for w in wanted))
            if wanted
            else pd.Series(True, index=out.index)
        )
        if mode_cim10 == "CIM10 général patient":
            keep_keys = set(out.loc[cim_mask, "_pt_join_key"].dropna())
            out = out[out["_pt_join_key"].isin(keep_keys)].copy()
        else:
            out = out[cim_mask].copy()
    if dose_non_nulle and tx_cols.get("dose") and tx_cols["dose"] in out.columns:
        dose = pd.to_numeric(
            out[tx_cols["dose"]].astype("string").str.replace(",", ".", regex=False),
            errors="coerce",
        )
        out = out[dose.fillna(0) != 0].copy()
    return out


TUMOR_DATA_KEYWORDS = [
    "stg",
    "stage",
    "stad",
    "tnm",
    "tumor",
    "tumour",
    "tumeur",
    "crit",
    "critere",
    "criteria",
    "desc",
    "description",
    "histo",
    "histologie",
    "histology",
    "grade",
    "gleason",
    "isup",
    "psa",
    "nccn",
    "risk",
    "risque",
    "classification",
    "extension",
    "metast",
    "m0",
    "m1",
    "n0",
    "n1",
    "t1",
    "t2",
    "t3",
    "t4",
]


def detect_tumor_data_columns(columns: List[str]) -> List[str]:
    """Repère les colonnes de données tumorales/stadification à conserver.

    Exemple de colonnes attendues : stg_crit_desc, stg_desc, tnm, gleason,
    grade, etc. La détection reste volontairement large mais limitée aux noms de
    colonnes, afin d'ajouter ces informations dans la partie traitement sans
    toucher au formulaire.
    """
    detected: List[str] = []
    for col in columns:
        key = str(col).lower().replace(" ", "_")
        if any(token in key for token in TUMOR_DATA_KEYWORDS):
            detected.append(col)
    return detected


def _normalized_unique_values(series: pd.Series, value_type: str = "text") -> List[str]:
    """Renvoie les valeurs uniques normalisées, stables et lisibles."""
    if series is None:
        return []
    s = series[nonempty_mask(series)].copy()
    if s.empty:
        return []

    if value_type == "date":
        dt = pd.to_datetime(s, errors="coerce")
        vals = [d.strftime("%Y-%m-%d") for d in dt.dropna().drop_duplicates()]
        # On conserve aussi les valeurs non convertibles si elles existent.
        bad = s[dt.isna()].astype(str).str.strip().drop_duplicates().tolist()
        vals.extend([v for v in bad if v])
        return sorted(dict.fromkeys(vals))

    if value_type == "numeric":
        num = pd.to_numeric(
            s.astype("string").str.replace(",", ".", regex=False), errors="coerce"
        )
        vals = []
        for v in num.dropna().drop_duplicates().tolist():
            if float(v).is_integer():
                vals.append(str(int(v)))
            else:
                vals.append(("%.6f" % float(v)).rstrip("0").rstrip("."))
        bad = s[num.isna()].astype(str).str.strip().drop_duplicates().tolist()
        vals.extend([v for v in bad if v])
        return sorted(dict.fromkeys(vals))

    vals = s.astype(str).str.strip().drop_duplicates().tolist()
    return sorted(dict.fromkeys([v for v in vals if v]))


def _unique_count(series: pd.Series, value_type: str = "text") -> int:
    return len(_normalized_unique_values(series, value_type=value_type))


def _unique_join(series: pd.Series, value_type: str = "text") -> Any:
    vals = _normalized_unique_values(series, value_type=value_type)
    return " ; ".join(vals) if vals else pd.NA


def build_treatment_consistency_report(
    cohort_tx: pd.DataFrame,
    tx_cols: Dict[str, Optional[str]],
) -> pd.DataFrame:
    """Contrôle les incohérences de traitement après ajout éventuel d'ETHOS.

    Le but est de repérer les patients qui ont plusieurs valeurs différentes
    pour les informations censées être uniques ou quasi uniques dans l'export :
    dose, nombre de fractions, date de première fraction, date de dernière
    fraction et éventuellement machine.

    Important : TechniqueId est volontairement exclu. Un même patient peut avoir
    plusieurs techniques légitimes, par exemple "STATIC ; ARC". Ces valeurs
    restent agrégées dans l'export, mais ne sont pas signalées comme incohérences.
    """
    if cohort_tx is None or cohort_tx.empty or "_pt_join_key" not in cohort_tx.columns:
        return pd.DataFrame(
            columns=[
                "_pt_join_key",
                "patient",
                "source",
                "champ",
                "nombre de valeurs distinctes",
                "valeurs trouvées",
                "niveau",
            ]
        )

    tx = cohort_tx.copy()
    checks = []
    candidates = {
        "Date première fraction": (tx_cols.get("start"), "date"),
        "Date dernière fraction": (tx_cols.get("end"), "date"),
        "Dose réalisée": (tx_cols.get("dose"), "numeric"),
        "Nombre de fractions": (tx_cols.get("nb_fractions"), "numeric"),
        # TechniqueId n'est pas contrôlé : plusieurs techniques par patient
        # peuvent être normales, par exemple STATIC ; ARC.
        "NomMachine": (find_col_by_norm(tx.columns, ["NomMachine", "Machine"]), "text"),
    }

    patient_col = (
        tx_cols.get("patient_id") if tx_cols.get("patient_id") in tx.columns else None
    )
    rows: List[Dict[str, Any]] = []
    for label, (col, kind) in candidates.items():
        if not col or col not in tx.columns:
            continue
        grouped = tx.groupby("_pt_join_key", dropna=True, sort=False)
        for key, sub in grouped:
            vals = _normalized_unique_values(sub[col], kind)
            n = len(vals)
            if n <= 1:
                continue
            pid = first_nonempty(sub[patient_col]) if patient_col else key
            rows.append(
                {
                    "_pt_join_key": key,
                    "patient": pid,
                    "source": _unique_join(
                        sub.get("_source_traitement", pd.Series(dtype=object))
                    ),
                    "champ": label,
                    "colonne_source": col,
                    "nombre de valeurs distinctes": n,
                    "valeurs trouvées": " ; ".join(vals),
                    "niveau": "A vérifier",
                }
            )

    return pd.DataFrame(rows)


@st.cache_data(show_spinner=False)
def build_patient_base(
    cohort_tx: pd.DataFrame,
    tx_cols: Dict[str, Optional[str]],
    treatment_cols: List[str],
) -> pd.DataFrame:
    tx = cohort_tx.copy()
    tx["_start_dt"] = (
        pd.to_datetime(tx[tx_cols["start"]], errors="coerce")
        if tx_cols.get("start")
        else pd.NaT
    )
    tx["_end_dt"] = (
        pd.to_datetime(tx[tx_cols["end"]], errors="coerce")
        if tx_cols.get("end")
        else pd.NaT
    )
    agg: Dict[str, Any] = {"_start_dt": "min", "_end_dt": "max"}
    if tx_cols.get("patient_id") and tx_cols["patient_id"] in tx.columns:
        agg[tx_cols["patient_id"]] = first_nonempty
    else:
        agg["pt_id"] = first_nonempty

    if "_source_traitement" in tx.columns:
        agg["_source_traitement"] = join_unique_nonempty

    date_like_cols = {tx_cols.get("start"), tx_cols.get("end")}
    numeric_like_cols = {tx_cols.get("dose"), tx_cols.get("nb_fractions")}

    for c in treatment_cols:
        if c in tx.columns and c not in agg and c != "_pt_join_key":
            if c == tx_cols.get("start"):
                agg[c] = lambda s: pd.to_datetime(s, errors="coerce").min()
            elif c == tx_cols.get("end"):
                agg[c] = lambda s: pd.to_datetime(s, errors="coerce").max()
            elif c in date_like_cols:
                agg[c] = lambda s: _unique_join(s, value_type="date")
            elif c in numeric_like_cols:
                agg[c] = lambda s: _unique_join(s, value_type="numeric")
            else:
                agg[c] = join_unique_nonempty

    out = tx.groupby("_pt_join_key", as_index=False, sort=False).agg(agg)
    out = out.rename(columns={"_start_dt": "startD", "_end_dt": "endD"})
    patient_id_col = (
        tx_cols.get("patient_id")
        if tx_cols.get("patient_id") in out.columns
        else "pt_id"
    )
    out = out.rename(columns={patient_id_col: "Patient ID"})
    if "Patient ID" not in out.columns:
        out["Patient ID"] = out["_pt_join_key"]
    return out
