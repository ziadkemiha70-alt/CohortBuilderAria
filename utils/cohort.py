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
from utils.text import find_col_by_norm, norm_key


def _find_all_alias_columns(columns: List[str], aliases: List[str]) -> List[str]:
    """Trouve les colonnes compatibles avec les alias, dans l'ordre de priorité.

    Le nouveau SQL peut contenir les colonnes `DiagnosisCodes`, `StartDateTime`,
    `LastDateTime`, `Total_dose`, `NbTreatedFrac`, alors que les extractions
    plus anciennes ou ETHOS peuvent encore contenir `DiagnosisCode`,
    `PremiereFractionChamp`, `DoseEffectuée2`, etc.
    """
    norm_to_cols: Dict[str, List[str]] = {}
    for col in columns:
        norm_to_cols.setdefault(norm_key(col), []).append(col)

    found: List[str] = []
    for alias in aliases:
        for col in norm_to_cols.get(norm_key(alias), []):
            if col not in found:
                found.append(col)
    return found


def _first_existing_alias_column(columns: List[str], aliases: List[str]) -> Optional[str]:
    """Retourne le premier alias réellement présent, sans créer de colonne technique.

    Utilisé pour l'identifiant patient affiché : on évite de fusionner `PatientId`
    et `pt_id` dans `_aria_patient_id_resolved`, car ce sont deux identifiants
    différents et ils doivent rester visibles séparément dans l'export.
    """
    cols = _find_all_alias_columns(columns, aliases)
    return cols[0] if cols else None


def _coalesce_treatment_aliases(
    tx: pd.DataFrame, aliases: List[str], resolved_col: str
) -> Optional[str]:
    """Crée une colonne technique unique nouveau SQL + anciens alias.

    Important : la première colonne trouvée dans `aliases` est prioritaire.
    Ainsi `DiagnosisCodes` du nouveau traitement reste prioritaire sur
    `DiagnosisCode` éventuellement présent dans ETHOS après fusion.
    """
    cols = _find_all_alias_columns(list(tx.columns), aliases)
    if not cols:
        return None
    if len(cols) == 1:
        return cols[0]

    values = pd.Series(pd.NA, index=tx.index, dtype="object")
    for col in cols:
        mask = (~nonempty_mask(values)) & nonempty_mask(tx[col])
        values.loc[mask] = tx.loc[mask, col]

    tx[resolved_col] = values
    return resolved_col


def resolve_treatment_columns(tx: pd.DataFrame) -> Dict[str, Optional[str]]:
    """Résout les colonnes traitement compatibles nouveau SQL + anciens exports.

    Nouveaux noms prioritaires :
    - `DiagnosisCodes` pour les CIM10, possiblement multiples dans une cellule ;
    - `StartDateTime` / `LastDateTime` pour les dates RT ;
    - `Total_dose` pour la dose, possiblement écrite `40.05 | 48` ;
    - `NbTreatedFrac` pour les fractions réalisées.
    """
    if tx is None or tx.empty:
        return {
            "patient_id": None,
            "dose": None,
            "nb_fractions": None,
            "start": None,
            "end": None,
            "cim": None,
        }

    return {
        "patient_id": _first_existing_alias_column(
            list(tx.columns),
            [
                "PatientId",
                "Patient ID",
                "IdPatient",
                "Patient_ID",
                "pt_id",
            ],
        ),
        "dose": _coalesce_treatment_aliases(
            tx,
            [
                "Total_dose",
                "Total dose",
                "TotalDose",
                "DosesTotal2",
                "DoseEffectuée2",
                "DoseEffectuee2",
                "Dose effectuée",
                "Dose effectuee",
                "DoseEffectuee",
                "Dose",
            ],
            "_aria_dose_resolved",
        ),
        "nb_fractions": _coalesce_treatment_aliases(
            tx,
            [
                "NbTreatedFrac",
                "Nb Treated Frac",
                "NbFractionsEffectués",
                "NbFractionsEffectues",
                "Nombre fractions",
                "NbFractions",
                "PlannedFrac",
            ],
            "_aria_nb_fractions_resolved",
        ),
        "start": _coalesce_treatment_aliases(
            tx,
            [
                "StartDateTime",
                "Start Date Time",
                "PremiereFractionChamp",
                "Première fraction",
                "Date première fraction",
                "FirstTreatmentDate",
                "StartDate",
            ],
            "_aria_start_resolved",
        ),
        "end": _coalesce_treatment_aliases(
            tx,
            [
                "LastDateTime",
                "Last Date Time",
                "DerniereFractionChamp",
                "Dernière fraction",
                "Date dernière fraction",
                "EndDate",
                "LastTreatmentDate",
            ],
            "_aria_end_resolved",
        ),
        "cim": _coalesce_treatment_aliases(
            tx,
            [
                "DiagnosisCodes",
                "Diagnosis Codes",
                "DiagnosisCode",
                "Diagnosis Code",
                "Code CIM",
                "CIM10",
                "ICD",
                "Code_CIM_Diagnostic",
            ],
            "_aria_cim_resolved",
        ),
    }


def _extract_cim10_tokens(value: Any) -> List[str]:
    """Extrait les codes CIM10 d'une cellule, même si plusieurs codes sont présents.

    Exemples acceptés : `C61`, `C61 | C50.9`, `C61;D07.5`, `C61 - prostate`.
    """
    if pd.isna(value):
        return []
    raw = str(value).upper().replace("-", ".")
    tokens = re.findall(r"[A-Z][0-9]{2}(?:\.[0-9A-Z]+)?", raw)
    return [str(t).strip() for t in tokens if str(t).strip()]


def _series_matches_cim10(series: pd.Series, wanted: List[str]) -> pd.Series:
    """Retourne True si au moins un code CIM10 de la cellule commence par un code demandé."""
    if series is None or not wanted:
        return pd.Series(True, index=series.index if series is not None else None)

    wanted_norm = (
        normalize_cim10(pd.Series(wanted, dtype="string"))
        .dropna()
        .astype(str)
        .tolist()
    )
    wanted_norm = [w for w in wanted_norm if w]
    if not wanted_norm:
        return pd.Series(True, index=series.index)

    def _match_one(value: Any) -> bool:
        tokens = _extract_cim10_tokens(value)
        if not tokens:
            # Fallback ancien comportement pour les cellules déjà simples.
            normalized = normalize_cim10(pd.Series([value], dtype="string")).iloc[0]
            tokens = [str(normalized)] if str(normalized) else []
        return any(tok.startswith(w) for tok in tokens for w in wanted_norm)

    return series.apply(_match_one)


def _dose_has_nonzero_value(value: Any) -> bool:
    """Vrai si une cellule dose contient au moins une valeur numérique non nulle.

    Le nouveau SQL peut écrire `Total_dose` sous forme multi-valeurs, par exemple
    `40.05 | 48`. Un `pd.to_numeric` strict transforme cela en NaN et supprime
    à tort des patients. Ici, on extrait toutes les valeurs numériques présentes.
    """
    if pd.isna(value):
        return False
    s = str(value).strip()
    if not s or s.lower() in {"nan", "none", "<na>", "na"}:
        return False
    s = s.replace(",", ".")
    numbers = re.findall(r"[-+]?\d+(?:\.\d+)?", s)
    if not numbers:
        return False
    for number in numbers:
        try:
            if abs(float(number)) > 0:
                return True
        except Exception:
            continue
    return False


def _dose_nonzero_mask(series: pd.Series) -> pd.Series:
    if series is None:
        return pd.Series(dtype=bool)
    return series.apply(_dose_has_nonzero_value).fillna(False).astype(bool)

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
        out = out[_dose_nonzero_mask(out[dose_col])].copy()

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


def filter_cohort(
    tx: pd.DataFrame,
    tx_cols: Dict[str, Optional[str]],
    cim10_text: str,
    mode_cim10: str,
    dose_non_nulle: bool,
) -> pd.DataFrame:
    """Filtre la cohorte traitement.

    Correction nouveau SQL :
    - le CIM10 est recherché dans `DiagnosisCodes` comme liste de codes, pas
      comme simple chaîne ;
    - la dose non nulle accepte `Total_dose` contenant plusieurs valeurs comme
      `40.05 | 48` ;
    - si un fichier ETHOS est fusionné, la cohorte est définie sur le traitement
      principal (`_source_traitement == standard`). ETHOS enrichit ensuite les
      patients retenus, mais ne peut plus faire entrer ou sortir un patient de
      la cohorte principale.
    """
    out = tx.copy()

    def _row_filter(frame: pd.DataFrame) -> pd.Series:
        mask = pd.Series(True, index=frame.index)

        cim_col = tx_cols.get("cim")
        if cim_col and cim_col in frame.columns and str(cim10_text).strip():
            raw_wanted = [
                c for c in re.split(r"[,;\s]+", str(cim10_text)) if c.strip()
            ]
            wanted = (
                normalize_cim10(pd.Series(raw_wanted, dtype="string"))
                .dropna()
                .astype(str)
                .tolist()
            )
            wanted = [w for w in wanted if w]
            mask &= _series_matches_cim10(frame[cim_col], wanted)

        dose_col = tx_cols.get("dose")
        if dose_non_nulle and dose_col and dose_col in frame.columns:
            mask &= _dose_nonzero_mask(frame[dose_col])

        return mask.fillna(False).astype(bool)

    source_col = "_source_traitement"
    has_standard_source = (
        source_col in out.columns
        and out[source_col].astype("string").str.lower().eq("standard").any()
    )

    # Cas fusion standard + ETHOS : le traitement principal définit la cohorte.
    # Sans ça, les anciennes colonnes ETHOS peuvent faire entrer des patients
    # alors que le nouveau traitement principal ne passe pas le filtre dose/CIM10.
    if has_standard_source and "_pt_join_key" in out.columns:
        src = out[source_col].astype("string").str.lower()
        standard = out[src.eq("standard")].copy()
        standard_mask = _row_filter(standard)

        if mode_cim10 == "CIM10 général patient":
            keep_keys = set(standard.loc[standard_mask, "_pt_join_key"].dropna())
            return out[out["_pt_join_key"].isin(keep_keys)].copy()

        keep_keys = set(standard.loc[standard_mask, "_pt_join_key"].dropna())
        keep_standard_rows = src.eq("standard") & out.index.isin(standard.index[standard_mask])
        keep_non_standard_for_patients = (~src.eq("standard")) & out["_pt_join_key"].isin(keep_keys)
        return out[keep_standard_rows | keep_non_standard_for_patients].copy()

    # Cas simple : pas de source standard identifiée, on filtre le tableau tel quel.
    row_mask = _row_filter(out)
    if mode_cim10 == "CIM10 général patient" and "_pt_join_key" in out.columns:
        keep_keys = set(out.loc[row_mask, "_pt_join_key"].dropna())
        return out[out["_pt_join_key"].isin(keep_keys)].copy()
    return out[row_mask].copy()


TNM_POSITIONED_RE = re.compile(r"^TNM_[1-9][0-9]*$", flags=re.IGNORECASE)
TNM_DATE_POSITIONED_RE = re.compile(r"^Date_staged_[1-9][0-9]*$", flags=re.IGNORECASE)

# Anciens champs TNM/staging à ne plus sélectionner automatiquement quand le SQL V11
# fournit les couples TNM_n / Date_staged_n.
LEGACY_TNM_EXPORT_KEYS = {
    "stg_crit_desc",
    "crit_desc",
    "date_staged",
    "tnm_all",
    "tnm_actif",
    "tnm_non_actif",
    "tnm_non_actifs",
    "tnm_autres",
    "tnm_nb_lignes",
    "tnm_nombre_lignes",
    "tnm_multiple",
    "base_actif",
    "base_autres",
    "base_cumul",
    "tnm_cumul",
    "stade_tumoral",
    "stade_nodal",
    "stade_metastase",
    "cncr_stage",
}


def _tnm_position(col: str) -> int:
    """Position de tri pour TNM_1, Date_staged_1, TNM_2, Date_staged_2, etc."""
    m = re.search(r"_(\d+)$", str(col))
    return int(m.group(1)) if m else 9999


def detect_tumor_data_columns(columns: List[str]) -> List[str]:
    """Repère uniquement les nouvelles colonnes TNM V11 à conserver.

    Le SQL V11 expose une saisie ARIA sous forme d'un couple :
    `TNM_1` / `Date_staged_1`, puis `TNM_2` / `Date_staged_2`, etc.
    On ne sélectionne donc plus automatiquement les anciens champs redondants
    `stg_crit_desc`, `crit_desc`, `TNM_actif`, `Stade_Tumoral`, etc.
    """
    tnm_cols = [c for c in columns if TNM_POSITIONED_RE.match(str(c))]
    date_cols = [c for c in columns if TNM_DATE_POSITIONED_RE.match(str(c))]

    ordered: List[str] = []
    max_pos = max([_tnm_position(c) for c in tnm_cols + date_cols], default=0)
    for pos in range(1, max_pos + 1):
        for col in (f"TNM_{pos}", f"Date_staged_{pos}"):
            if col in columns and col not in ordered:
                ordered.append(col)
    return ordered


def sanitize_treatment_columns(columns: List[str], selected: List[str]) -> List[str]:
    """Nettoie une sélection de colonnes traitement avant `st.multiselect`.

    Objectifs :
    - supprimer les colonnes demandées par un ancien profil mais absentes du nouveau SQL ;
    - retirer les anciens champs TNM redondants ;
    - ajouter automatiquement TNM_1/Date_staged_1... quand ils existent ;
    - éviter les colonnes techniques `_aria_*` dans l'export utilisateur.
    """
    available = list(columns)
    selected = list(selected or [])
    out: List[str] = []

    for col in selected:
        if col not in available:
            continue
        key = norm_key(col)
        if key in LEGACY_TNM_EXPORT_KEYS:
            continue
        if key.startswith("aria_") or str(col).startswith("_aria_"):
            continue
        if col not in out:
            out.append(col)

    for col in detect_tumor_data_columns(available):
        if col not in out:
            out.append(col)

    return out

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
