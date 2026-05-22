# -*- coding: utf-8 -*-
"""Nettoyage, clés patient et nettoyage skrub contrôlé."""

from typing import Any, Iterable, List, Optional, Tuple

import pandas as pd

from utils.text import norm_key, strip_accents

try:
    from skrub import Cleaner

    SKRUB_AVAILABLE = True
except Exception:
    Cleaner = None
    SKRUB_AVAILABLE = False


def normalize_pt_key(series: pd.Series) -> pd.Series:
    s = series.astype("string").str.strip()
    s = s.str.replace(r"\.0$", "", regex=True)
    s = s.str.replace(r"\D", "", regex=True)
    s = s.str.lstrip("0")
    return s.replace("", pd.NA)


def build_join_key(
    df: pd.DataFrame,
    primary: str = "pt_id",
    fallback_candidates: Optional[List[str]] = None,
) -> pd.Series:
    """Construit une clé de jointure robuste.

    Priorité : `pt_id` technique long, car c'est la clé fiable du formulaire.
    Si `pt_id` est absent ou vide pour certaines lignes de traitement, on utilise un identifiant
    patient public disponible (`PatientId`, `Patient ID`, etc.) uniquement comme fallback.
    Cela évite qu'un CIM10 présent dans traitement_patient disparaisse parce que `pt_id` est vide.
    """
    fallback_candidates = fallback_candidates or [
        "PatientId",
        "Patient ID",
        "IdPatient",
        "Patient_ID",
    ]
    if primary in df.columns:
        key = normalize_pt_key(df[primary])
    else:
        key = pd.Series(pd.NA, index=df.index, dtype="string")
    for cand in fallback_candidates:
        if cand in df.columns:
            fb = normalize_pt_key(df[cand])
            key = key.where(key.notna(), fb)
    return key.replace("", pd.NA)


def normalize_cim10(series: pd.Series) -> pd.Series:
    s = (
        series.astype("string")
        .fillna("")
        .map(lambda x: strip_accents(x).upper().strip())
    )
    s = s.str.replace(" ", "", regex=False).str.replace("-", ".", regex=False)
    s = s.str.replace(r"[^A-Z0-9\.]", "", regex=True)
    return s


def nonempty_mask(series: pd.Series) -> pd.Series:
    s = series.astype("string").str.strip()
    return s.notna() & ~s.isin(["", "nan", "NaN", "<NA>", "None", "NA"])


def is_skrub_protected_column(col: Any) -> bool:
    """Colonnes à ne jamais confier à skrub.

    Objectif : bénéficier de skrub uniquement pour un nettoyage léger de colonnes
    peu sensibles, tout en protégeant les identifiants, dates, CIM10, doses,
    libellés médicaux et colonnes techniques utilisées par le pipeline.
    """
    nk = norm_key(col)
    protected_tokens = [
        "id",
        "patient",
        "pt",
        "join_key",
        "date",
        "heure",
        "time",
        "cim",
        "diagnos",
        "diagnosis",
        "code",
        "dose",
        "fraction",
        "start",
        "end",
        "naissance",
        "age",
        "sex",
        "sexe",
        "nom",
        "prenom",
        "firstname",
        "lastname",
    ]
    if nk in {"pt_id", "_pt_join_key", "patient_id", "date_event"}:
        return True
    return any(tok in nk for tok in protected_tokens)


def skrub_safe_candidates(
    df: pd.DataFrame, max_unique_ratio: float = 0.35, sample_rows: int = 8000
) -> List[str]:
    """Détecte des colonnes candidates au nettoyage skrub contrôlé.

    Version mémoire-sûre : on évalue la cardinalité sur un échantillon, pas
    sur tout le formulaire. Cela évite les erreurs mémoire avec les grands CSV
    ARIA/formulaire.
    """
    out: List[str] = []
    if df is None or df.empty:
        return out
    sample = df.head(min(len(df), sample_rows))
    n = max(len(sample), 1)
    for c in sample.columns:
        if is_skrub_protected_column(c):
            continue
        if not (
            pd.api.types.is_object_dtype(sample[c])
            or pd.api.types.is_string_dtype(sample[c])
        ):
            continue
        try:
            nunique = int(sample[c].nunique(dropna=True))
        except Exception:
            continue
        if nunique == 0:
            continue
        if (nunique / n) <= max_unique_ratio:
            out.append(c)
    return out


def is_skrub_auto_allowed_column(col: Any, table_label: str) -> bool:
    """Autorise skrub automatiquement uniquement sur des colonnes très peu risquées.

    On ne nettoie pas les identifiants, dates, CIM10, doses, diagnostics, valeurs
    cliniques ou libellés médicaux. L'usage automatique est réservé à quelques
    champs catégoriels/logistiques qui n'entrent pas dans les calculs de dates,
    de cohortes ou de valeurs médicales exportées.
    """
    if is_skrub_protected_column(col):
        return False
    nk = norm_key(col)

    # Termes explicitement exclus : toxicités, symptômes, biologie, récidive,
    # champs cliniques libres ou colonnes qui peuvent porter une valeur médicale.
    denied = [
        "proct",
        "diabet",
        "amyotroph",
        "diarrh",
        "brulur",
        "miction",
        "dysur",
        "pollaki",
        "ipss",
        "psa",
        "recid",
        "toxic",
        "grade",
        "ecog",
        "performance",
        "douleur",
        "poids",
        "taille",
        "hormono",
        "anteced",
        "atcd",
        "clinique",
        "examen",
        "conclusion",
        "note",
        "traitement_prescrit",
        "dose_delivree",
        "localisation",
    ]
    if any(tok in nk for tok in denied):
        return False

    allowed_common = [
        "site",
        "technique",
        "machine",
        "modalite",
        "orientation",
        "position",
        "contention",
        "transport",
        "accessoire",
        "checklist",
        "preparation",
        "dolist",
        "workflow",
        "scanner",
        "decubitus",
    ]

    # Dans traitement_patient, quelques champs catégoriels sont utiles pour
    # homogénéiser l'affichage. Dans formulaire_patient, on reste encore plus
    # prudent : principalement logistique/checklists/accessoires.
    if table_label == "traitement_patient":
        return any(tok in nk for tok in allowed_common)
    if table_label == "formulaire_patient":
        return any(
            tok in nk
            for tok in [
                "transport",
                "accessoire",
                "checklist",
                "preparation",
                "dolist",
                "contention",
                "position",
                "orientation",
                "scanner",
            ]
        )
    return False


def skrub_auto_columns(df: pd.DataFrame, table_label: str) -> List[str]:
    """Colonnes nettoyées automatiquement par skrub.

    Mémoire-sûr : pour les très grands formulaires, on désactive skrub sur le
    formulaire complet. Le nettoyage explicite interne reste appliqué et les
    colonnes sensibles sont inchangées.
    """
    if df is None or df.empty:
        return []
    # Le formulaire ARIA est très large : Cleaner peut allouer beaucoup de
    # mémoire pour un gain faible. On le laisse actif pour les petits fichiers
    # ou pour traitement_patient, mais on le coupe sur les grands formulaires.
    if table_label == "formulaire_patient" and len(df) > 50000:
        return []
    candidates = skrub_safe_candidates(df, max_unique_ratio=0.25, sample_rows=8000)
    return [c for c in candidates if is_skrub_auto_allowed_column(c, table_label)]


def clean_with_skrub_safe(
    df: pd.DataFrame, columns: List[str], label: str
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Applique skrub uniquement aux colonnes automatiquement jugées sûres.

    Retourne le DataFrame nettoyé et un petit rapport de traçabilité. Si skrub
    n'est pas installé ou si une erreur survient, le DataFrame original est
    conservé.
    """
    cols = [c for c in columns if c in df.columns and not is_skrub_protected_column(c)]
    report_rows = []
    if not cols:
        return df, pd.DataFrame(columns=["table", "colonne", "statut", "details"])
    if not SKRUB_AVAILABLE:
        for c in cols:
            report_rows.append(
                {
                    "table": label,
                    "colonne": c,
                    "statut": "SKRUB_NON_INSTALLE",
                    "details": "Nettoyage ignoré",
                }
            )
        return df, pd.DataFrame(report_rows)
    out = df.copy()
    try:
        before_na = {c: int(out[c].isna().sum()) for c in cols}
        cleaned = Cleaner().fit_transform(out[cols].copy())
        for c in cols:
            if c in cleaned.columns:
                out[c] = cleaned[c]
                after_na = int(out[c].isna().sum())
                report_rows.append(
                    {
                        "table": label,
                        "colonne": c,
                        "statut": "NETTOYE_SKRUB",
                        "details": f"NA avant={before_na[c]} ; NA après={after_na}",
                    }
                )
            else:
                report_rows.append(
                    {
                        "table": label,
                        "colonne": c,
                        "statut": "IGNOREE",
                        "details": "Colonne absente après Cleaner",
                    }
                )
    except Exception as exc:
        for c in cols:
            report_rows.append(
                {
                    "table": label,
                    "colonne": c,
                    "statut": "ERREUR_SKRUB",
                    "details": str(exc),
                }
            )
        return df, pd.DataFrame(report_rows)
    return out, pd.DataFrame(report_rows)


def first_nonempty(series: pd.Series):
    s = series[nonempty_mask(series)]
    return s.iloc[0] if not s.empty else pd.NA


def join_unique_nonempty(series: pd.Series) -> Any:
    s = series[nonempty_mask(series)].astype(str).drop_duplicates()
    return " ; ".join(s.tolist()) if not s.empty else pd.NA


def join_nonempty_keep_order(series: pd.Series) -> Any:
    vals = [
        str(v).strip()
        for v in series
        if pd.notna(v)
        and str(v).strip() not in {"", "nan", "NaN", "<NA>", "None", "NA"}
    ]
    return " ; ".join(vals) if vals else pd.NA


def find_col_by_norm(columns: Iterable[str], wanted: Iterable[str]) -> Optional[str]:
    nmap = {norm_key(c): c for c in columns}
    for w in wanted:
        if norm_key(w) in nmap:
            return nmap[norm_key(w)]
    return None
