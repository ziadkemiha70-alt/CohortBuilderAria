# -*- coding: utf-8 -*-
"""Profils JSON et nommage des fichiers exportés."""

import json
import re
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

import pandas as pd

from utils.clean import normalize_cim10
from utils.text import norm_key, repair_mojibake, strip_accents

# NOMMAGE DES FICHIERS EXPORTÉS
# ============================================================

# Quelques associations fréquentes. Le mapping et le profil restent prioritaires,
# mais cette table évite d'obtenir un nom générique quand seul un CIM10 est saisi.
CIM10_ZONE_HINTS = {
    "C61": "Prostate",
    "C50": "Sein",
    "C34": "Poumon",
    "C15": "Oesophage",
    "C16": "Estomac",
    "C18": "Colon",
    "C19": "Rectum",
    "C20": "Rectum",
    "C21": "Canal_anal",
    "C22": "Foie",
    "C25": "Pancreas",
    "C32": "Larynx",
    "C53": "Gyneco",
    "C54": "Gyneco",
    "C56": "Gyneco",
    "C62": "Testicule",
    "C64": "Rein",
    "C67": "Vessie",
    "C71": "Crane",
    "C73": "Thyroide",
}


def safe_filename_label(label: Any, default: str = "Export_ODM") -> str:
    """Convertit un libellé médical en nom de fichier Windows-compatible."""
    s = str(label or "").strip()
    if not s:
        return default
    s = repair_mojibake(s)
    s = strip_accents(s)
    s = re.sub(r"[^A-Za-z0-9 _.-]+", "_", s)
    s = re.sub(r"\s+", "_", s).strip("._- ")
    return s or default


def display_zone_label(label: Any, default: str = "Export ODM") -> str:
    """Libellé lisible affiché dans l'interface et utilisé comme base de nommage."""
    s = str(label or "").strip()
    if not s:
        return default
    s = repair_mojibake(s).replace("_", " ").strip()
    # On garde les acronymes courts en majuscules, sinon une casse titre suffit.
    return s.upper() if len(s) <= 4 and s.isalpha() else s.title()


def infer_export_zone_name(
    cim10_text: str,
    mapping_profile_text: str,
    profile_settings: Dict[str, Any],
    mapping_rows: Optional[pd.DataFrame] = None,
) -> str:
    """Déduit le nom métier du fichier final.

    Ordre de priorité : profil JSON, mapping trouvé, table CIM10 minimale, puis nom générique.
    Le résultat sert uniquement au nom des fichiers téléchargés, pas au filtrage médical.
    """
    for key in ("export_zone", "localisation", "profile_name", "_profile_name"):
        val = profile_settings.get(key)
        if val:
            # Les profils générés ont souvent un nom du type profil_PROSTATE_depuis_regle.
            cleaned = re.sub(r"^profil[_ -]*", "", str(val), flags=re.IGNORECASE)
            cleaned = re.sub(
                r"[_ -]*depuis[_ -]*regle.*$", "", cleaned, flags=re.IGNORECASE
            )
            cleaned = re.sub(r"[_ -]*C\d+.*$", "", cleaned, flags=re.IGNORECASE)
            if cleaned.strip():
                return display_zone_label(cleaned)

    if mapping_profile_text:
        first = re.split(r"[,;/|]+", mapping_profile_text)[0].strip()
        if first:
            return display_zone_label(first)

    if mapping_rows is not None and not mapping_rows.empty:
        for col in mapping_rows.columns:
            nk = norm_key(col)
            if any(k in nk for k in ["localisation", "zone", "site", "groupe"]):
                vals = mapping_rows[col].dropna().astype(str)
                vals = [
                    v.strip()
                    for v in vals
                    if v.strip() and v.strip().lower() not in {"nan", "<na>"}
                ]
                if vals:
                    return display_zone_label(vals[0])

    codes = [
        normalize_cim10(pd.Series([x])).iloc[0]
        for x in re.split(r"[,;\s]+", str(cim10_text or ""))
        if x.strip()
    ]
    if len(codes) == 1:
        return display_zone_label(CIM10_ZONE_HINTS.get(str(codes[0]), str(codes[0])))
    if len(codes) > 1:
        return "Multi CIM10"
    return "Tous CIM10"


def export_filenames(zone_label: str) -> Dict[str, str]:
    base = safe_filename_label(zone_label, default="Export_ODM")
    return {
        "xlsx": f"{base}.xlsx",
        "csv": f"{base}.csv",
        "json": f"{base}.json",
        "proof": f"{base}_rapport_preuve.xlsx",
    }




# DÉCODAGE PROFIL : compatibilité settings -> columns
# ============================================================


def _profile_truthy(value: Any) -> bool:
    """Interprète les booléens venant d'un JSON ou d'un DataFrame pandas."""
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


def _profile_explicit_false(value: Any) -> bool:
    """Vrai seulement si le profil désactive explicitement le décodage."""
    if isinstance(value, bool):
        return value is False
    if value is None:
        return False
    try:
        if pd.isna(value):
            return False
    except Exception:
        pass
    return str(value).strip().lower() in {"false", "0", "non", "no", "n", "faux"}


def _binary_table_length(table: Dict[str, Any]) -> Optional[int]:
    """Déduit la longueur d'un code binaire à partir des clés de table."""
    lengths = []
    for key in table.keys():
        s = str(key).strip()
        if re.fullmatch(r"[01]{2,}", s):
            lengths.append(len(s))
    return max(lengths) if lengths else None


def enrich_config_with_decoding_from_settings(
    config: pd.DataFrame, settings: Dict[str, Any]
) -> pd.DataFrame:
    """Applique les règles `settings.binary_choice_decode` aux lignes `columns`.

    Cette fonction garde le profil universel : aucune règle médicale n'est codée
    en dur ici. Si le JSON contient une table de décodage centralisée dans
    `settings.binary_choice_decode.tables`, elle est recopiée sur la ligne de la
    colonne correspondante dans `config`, pour que `temporal.py` puisse décoder
    l'item pendant l'agrégation.

    Priorités de sécurité :
    - ne décode rien si aucune table n'existe dans le JSON ;
    - ne modifie pas une ligne où `Décodage actif` vaut explicitement false ;
    - ne touche pas aux colonnes non présentes dans le profil.
    """
    if config is None or config.empty:
        return config

    decode_cfg = settings.get("binary_choice_decode", {})
    if not isinstance(decode_cfg, dict) or not decode_cfg.get("enabled", True):
        return config

    tables = decode_cfg.get("tables") or decode_cfg.get("binary_choice_tables") or {}
    meta = decode_cfg.get("meta") or {}
    if not isinstance(tables, dict) or not tables:
        return config

    table_lookup: Dict[str, Tuple[str, Dict[str, Any]]] = {}
    for name, table in tables.items():
        if isinstance(table, dict) and table:
            table_lookup.setdefault(norm_key(name), (str(name), table))

    if not table_lookup:
        return config

    out = config.copy()
    for idx, row in out.iterrows():
        current_flag = row.get("Décodage actif", None)
        if _profile_explicit_false(current_flag):
            continue

        candidates = [
            row.get("Colonne formulaire", ""),
            row.get("Nom export", ""),
            row.get("Colonne profil originale", ""),
        ]

        match = None
        for candidate in candidates:
            key = norm_key(candidate)
            if key in table_lookup:
                match = table_lookup[key]
                break
        if match is None:
            continue

        table_name, table = match
        m = meta.get(table_name, {}) if isinstance(meta, dict) else {}
        if not isinstance(m, dict):
            m = {}

        out.at[idx, "Décodage actif"] = True
        out.at[idx, "Type décodage"] = m.get("type", row.get("Type décodage", "binary_multiselect_id"))
        out.at[idx, "Décodage sortie"] = m.get("output", row.get("Décodage sortie", "labels"))
        out.at[idx, "Règle agrégation"] = m.get(
            "aggregation", row.get("Règle agrégation", "logical_or_then_labels")
        )
        out.at[idx, "Table décodage"] = table
        out.at[idx, "Longueur code binaire"] = m.get(
            "binary_length", row.get("Longueur code binaire", _binary_table_length(table))
        )
        if not row.get("Source décodage") or str(row.get("Source décodage")).lower() in {"nan", "<na>"}:
            out.at[idx, "Source décodage"] = "settings.binary_choice_decode"

    return out


def build_profile(config: pd.DataFrame, settings: Dict[str, Any]) -> bytes:
    payload = {
        "version": "ARIA_ODM_profile_v1",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "settings": settings,
        "columns": (
            config.to_dict(orient="records")
            if config is not None and not config.empty
            else []
        ),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


def load_profile(uploaded) -> Tuple[Dict[str, Any], pd.DataFrame]:
    if uploaded is None:
        return {}, pd.DataFrame()
    payload = json.loads(uploaded.getvalue().decode("utf-8"))
    settings = dict(payload.get("settings", {}))
    # Le nom du profil est utile pour nommer les exports, mais il ne doit pas
    # remplacer les paramètres saisis ensuite par l'utilisateur.
    if payload.get("profile_name"):
        settings.setdefault("_profile_name", payload.get("profile_name"))
    if payload.get("description"):
        settings.setdefault("_profile_description", payload.get("description"))
    config = pd.DataFrame(payload.get("columns", []))
    config = enrich_config_with_decoding_from_settings(config, settings)
    return settings, config
