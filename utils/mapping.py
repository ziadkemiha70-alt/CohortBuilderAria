# -*- coding: utf-8 -*-
"""Fonctions liées au mapping CIM10/localisation et à la sélection de colonnes."""

import io
import re
from typing import Any, Iterable, List, Optional, Tuple, Dict

import pandas as pd
import streamlit as st

from utils.clean import normalize_cim10
from utils.load import read_uploaded_table
from utils.text import find_col_by_norm, norm_key


def read_mapping_file(uploaded_file) -> pd.DataFrame:
    """Lit mapping.csv ou mapping.xlsx.

    Le CSV est privilégié pour rester cohérent avec la nouvelle structure du
    projet, mais l'Excel reste accepté pour compatibilité avec les anciens
    fichiers de travail.
    """
    if uploaded_file is None:
        return pd.DataFrame()
    name = uploaded_file.name.lower()
    if name.endswith(".csv"):
        df = read_uploaded_table(uploaded_file)
        if not df.empty:
            df = df.copy()
            df["_sheet_mapping"] = "mapping.csv"
        return df

    raw = uploaded_file.getvalue()
    try:
        xls = pd.ExcelFile(io.BytesIO(raw))
    except Exception:
        return pd.DataFrame()
    frames = []
    for sheet in xls.sheet_names:
        try:
            df = pd.read_excel(xls, sheet_name=sheet, dtype="string")
        except Exception:
            continue
        if not df.empty:
            df = df.copy()
            df["_sheet_mapping"] = sheet
            frames.append(df)
    return (
        pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()
    )


def excel_date_string(x: Any) -> Any:
    if pd.isna(x):
        return pd.NA
    dt = pd.to_datetime(x, errors="coerce")
    if pd.isna(dt):
        return str(x)
    return dt.strftime("%Y-%m-%d")


# ============================================================
# MAPPING / PERTINENCE
# ============================================================


def mapping_find_col(columns: Iterable[str], names: Iterable[str]) -> Optional[str]:
    return find_col_by_norm(columns, names)


def mapping_rows_for_cim(mapping_df: pd.DataFrame, cim10_text: str) -> pd.DataFrame:
    if mapping_df is None or mapping_df.empty or not cim10_text.strip():
        return pd.DataFrame()
    cim_col = mapping_find_col(
        mapping_df.columns, ["CIM 10", "CIM10", "Code CIM", "Code_CIM"]
    )
    if not cim_col:
        return pd.DataFrame()
    requested = [
        normalize_cim10(pd.Series([x])).iloc[0]
        for x in re.split(r"[,;\s]+", cim10_text)
        if x.strip()
    ]
    norm_map = normalize_cim10(mapping_df[cim_col])
    mask = pd.Series(False, index=mapping_df.index)
    for code in requested:
        mask |= norm_map.str.match(
            rf"^{re.escape(str(code))}(?:\.|$)", na=False
        ) | norm_map.eq(str(code))
    return mapping_df[mask].copy()


def mapping_search_rows(
    mapping_df: pd.DataFrame, query: str, max_rows: int = 50
) -> pd.DataFrame:
    if mapping_df is None or mapping_df.empty or not query.strip():
        return pd.DataFrame()
    q = norm_key(query)
    searchable = mapping_df.fillna("").astype(str).agg(" ".join, axis=1).map(norm_key)
    return mapping_df[searchable.str.contains(q, na=False)].head(max_rows).copy()


def compact_mapping_rows(rows: pd.DataFrame) -> pd.DataFrame:
    if rows is None or rows.empty:
        return pd.DataFrame(
            columns=[
                "CIM10",
                "Description",
                "Source mapping",
                "Localisations / requêtes proposées",
            ]
        )
    cim_col = mapping_find_col(
        rows.columns, ["CIM 10", "CIM10", "Code CIM", "Code_CIM"]
    )
    desc_col = mapping_find_col(rows.columns, ["Description", "Libellé", "Libelle"])
    loc_cols = [
        c
        for c in rows.columns
        if c not in {cim_col, desc_col, "_sheet_mapping"} and rows[c].notna().any()
    ]
    compact = []
    for _, r in rows.iterrows():
        vals = []
        for c in loc_cols:
            v = r.get(c, pd.NA)
            if (
                pd.notna(v)
                and str(v).strip()
                and str(v).strip().lower() not in {"nan", "<na>"}
            ):
                vals.append(str(v).strip())
        compact.append(
            {
                "CIM10": r.get(cim_col, "") if cim_col else "",
                "Description": r.get(desc_col, "") if desc_col else "",
                "Source mapping": r.get("_sheet_mapping", ""),
                "Localisations / requêtes proposées": " ; ".join(dict.fromkeys(vals)),
            }
        )
    return pd.DataFrame(compact).drop_duplicates()


def infer_profile_keywords_from_mapping(rows: pd.DataFrame) -> List[str]:
    if rows is None or rows.empty:
        return []
    text = " ".join(rows.fillna("").astype(str).agg(" ".join, axis=1).tolist())
    tokens: List[str] = []
    stop = {
        "BASELINE",
        "AIGU",
        "TARDIF",
        "REQUETE",
        "DESCRIPTION",
        "CIM",
        "LOC",
        "MAPPING",
        "FORMULAIRE",
    }
    for raw in re.split(r"[^A-Za-zÀ-ÿ0-9]+", text):
        t = raw.strip().upper()
        if len(t) < 3 or t in stop or re.match(r"^\d+[A-Z]?$", t):
            continue
        if t not in tokens:
            tokens.append(t)
    return tokens[:16]


def classify_column(col: str) -> Tuple[str, str, int]:
    """Retourne catégorie, recommandation, score de pertinence."""
    nk = norm_key(col)
    ignore = [
        "checklist",
        "do_list",
        "dolist",
        "accessoires",
        "preparation_nc",
        "merm",
        "phy",
        "sec_",
        "transport",
        "contention",
        "orientation",
        "marquer",
        "posibras",
        "cale",
        "scanner",
        "machine",
        "gouttieres",
        "urgence",
        "info_effets",
        "presence_medecin",
        "presence_physicien",
        "dossier_physique",
        "copie",
        "demande_adaptatif",
    ]
    recurrence = ["recidive", "controle_tumoral", "statut_maladie", "date_evaluation"]
    bio = ["psa", "ca_125", "ca_19_9", "afp", "scc"]
    prostate = [
        "proctite",
        "dysurie",
        "brulures_mictionnelles",
        "pollakiurie",
        "frequence_urinaire",
        "miction_imperieuse",
        "ipss",
        "rectorrag",
        "nombre_de_lever",
        "nombre_de_protection",
        "toucher_rectal",
    ]
    toxicity = [
        "diarrhee",
        "nausee",
        "vomissement",
        "douleur",
        "incontinence",
        "dyspnee",
        "toux",
        "radiodermite",
        "mucite",
        "fibrose",
        "secheresse",
        "dysphagie",
        "oesophagite",
        "pneumonite",
        "amyotrophie",
        "bouffees",
        "dyserection",
    ]
    baseline = [
        "diabete",
        "atcd",
        "antecedent",
        "tabac",
        "alcool",
        "poids",
        "taille",
        "allergie",
        "statut_socio",
        "traitement_insuline",
        "dyslipidemie",
    ]
    if any(w in nk for w in ignore):
        return "Workflow / logistique", "À ignorer", 5
    if any(w in nk for w in recurrence):
        return "Récidive / contrôle", "Pertinent", 85
    if any(w in nk for w in prostate):
        return "Clinique PROSTATE / URO", "Très pertinent", 92
    if any(w in nk for w in bio):
        return "Biologie / marqueur", "Pertinent", 82
    if any(w in nk for w in toxicity):
        return "Toxicité clinique", "Très pertinent", 88
    if any(w in nk for w in baseline):
        return "Antécédent / baseline", "Pertinent", 78
    return "Autre colonne formulaire", "À vérifier", 45


def phase_defaults_for_column(col: str) -> Dict[str, bool]:
    nk = norm_key(col)
    recurrence = ["recidive", "date_evaluation_recidive", "controle_tumoral"]
    baseline_only = [
        "diabete",
        "atcd",
        "antecedent",
        "tabac",
        "alcool",
        "poids_habituel",
        "taille",
        "statut_socio",
        "allergie",
        "dyslipidemie",
    ]
    aigu_tardif = [
        "proctite",
        "diarrhee",
        "dysurie",
        "brulures",
        "pollakiurie",
        "frequence_urinaire",
        "imperiosite",
        "incontinence",
        "rectorrag",
    ]
    tardif = [
        "amyotrophie",
        "bouffees",
        "dyserection",
        "fibrose",
        "telangiectasies",
        "secheresse",
    ]
    if any(w in nk for w in recurrence):
        return {"Cumul": True, "Avant RT": False, "Aigu": False, "Tardif": True}
    if any(w in nk for w in baseline_only):
        return {"Cumul": True, "Avant RT": True, "Aigu": False, "Tardif": False}
    if any(w in nk for w in aigu_tardif):
        return {"Cumul": True, "Avant RT": False, "Aigu": True, "Tardif": True}
    if any(w in nk for w in tardif):
        return {"Cumul": True, "Avant RT": False, "Aigu": False, "Tardif": True}
    return {"Cumul": True, "Avant RT": False, "Aigu": False, "Tardif": False}


def suggest_columns_from_mapping_and_profile(
    form_candidates: List[str], keywords: List[str], max_cols: int = 35
) -> List[str]:
    k = {norm_key(x) for x in keywords}
    wanted: List[str] = []
    if {"prostate", "uro", "urologie"} & k:
        wanted = [
            "Proctite",
            "Dysurie",
            "Brûlures mictionnelles",
            "Fréquence urinaire",
            "Miction impérieuse",
            "Pollakiurie",
            "Nombre de lever nocturne",
            "Nombre de protection utilisées /j",
            "PSA",
            "IPSS",
            "Toucher rectal",
            "Hormonothérapie en cours (prostate)",
            "Tolérance hormonothérapie prostate",
            "Diabète",
            "Traitement insuline",
            "Antécédent de radiothérapie",
            "Antécédents carcinologiques familliaux",
            "Antécédents médico chirurgicaux personnels",
            "Récidive locale",
            "Date évaluation récidive locale",
            "Récidive à distance",
            "Date évaluation récidive à distance",
            "Récidive régionale",
            "Date évaluation récidive régionale",
            "Bouffées de chaleur ",
            "Amyotrophie",
            "Diarrhée",
        ]
    out: List[str] = []
    for w in wanted:
        c = find_col_by_norm(form_candidates, [w])
        if c and c not in out:
            out.append(c)
    if not out:
        scored = []
        for c in form_candidates:
            _, _, score = classify_column(c)
            if score >= 78:
                scored.append((score, c))
        out = [c for _, c in sorted(scored, reverse=True)[:max_cols]]
    return out[:max_cols]
