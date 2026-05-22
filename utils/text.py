# -*- coding: utf-8 -*-
"""Normalisation texte, colonnes et recherche tolérante."""

import re
import unicodedata
from typing import Any, Dict, Iterable, List

import pandas as pd


def strip_accents(text: Any) -> str:
    text = "" if pd.isna(text) else str(text)
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c))


def repair_mojibake(text: Any) -> str:
    """Répare les libellés du type `DiabÃ¨te` quand le CSV a été lu avec un mauvais encodage.

    La fonction est volontairement prudente : si la réparation échoue ou si le
    texte ne ressemble pas à du mojibake, on renvoie le texte original.
    Elle sert uniquement au matching des noms de colonnes/profils, jamais à
    modifier les valeurs médicales exportées.
    """
    s = "" if pd.isna(text) else str(text)
    if not any(marker in s for marker in ["Ã", "Â", "Å", "â", "œ", "€"]):
        return s
    for enc in ("latin1", "cp1252"):
        try:
            fixed = s.encode(enc, errors="strict").decode("utf-8", errors="strict")
            # On garde la version réparée seulement si elle paraît moins corrompue.
            if sum(fixed.count(m) for m in ["Ã", "Â", "Å", "â", "€"]) < sum(
                s.count(m) for m in ["Ã", "Â", "Å", "â", "€"]
            ):
                return fixed
        except Exception:
            continue
    return s


def norm_display_text(x: Any) -> str:
    s = repair_mojibake(x)
    s = strip_accents(s).lower().strip()
    s = re.sub(r"\s+", " ", s)
    return s


def norm_key(x: Any) -> str:
    s = norm_display_text(x)
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s


def column_match_keys(x: Any) -> List[str]:
    """Clés robustes pour comparer un nom de colonne profil/formulaire.

    On tient compte des accents, espaces multiples, retours ligne, ponctuation
    et mojibake fréquent dans les exports CSV Windows/latin1.
    """
    raw = "" if pd.isna(x) else str(x)
    repaired = repair_mojibake(raw)
    candidates = {raw, repaired, raw.replace("\n", " "), repaired.replace("\n", " ")}
    keys = []
    for c in candidates:
        k = norm_key(c)
        if k and k not in keys:
            keys.append(k)
    return keys


def build_column_lookup(columns: Iterable[str]) -> Dict[str, str]:
    lookup: Dict[str, str] = {}
    for col in columns:
        for k in column_match_keys(col):
            lookup.setdefault(k, col)
    return lookup


def flexible_column_search(
    columns: Iterable[str], query: str, limit: int = 80
) -> List[str]:
    """Recherche tolérante dans les colonnes formulaire.

    Exemple : `diabete`, `diabÃ¨te`, `recid locale`, `brulures mict` trouvent
    la colonne même si les accents/espaces/encodages diffèrent.
    """
    q = norm_display_text(query)
    q_tokens = [t for t in re.split(r"[^a-z0-9]+", q) if t]
    if not q_tokens:
        return []
    scored: List[Tuple[int, str]] = []
    for col in columns:
        txt = norm_display_text(col)
        key = norm_key(col)
        score = 0
        if q in txt or q.replace(" ", "_") in key:
            score += 100
        for tok in q_tokens:
            if tok in txt or tok in key:
                score += 20
        # Bonus si tous les tokens sont présents, même dans le désordre.
        if all(tok in txt or tok in key for tok in q_tokens):
            score += 50
        if score > 0:
            scored.append((score, col))
    scored.sort(key=lambda x: (-x[0], norm_display_text(x[1])))
    return [c for _, c in scored[:limit]]


def find_col_by_norm(columns: Iterable[str], wanted: Iterable[str]) -> str | None:
    nmap = {norm_key(c): c for c in columns}
    for w in wanted:
        if norm_key(w) in nmap:
            return nmap[norm_key(w)]
    return None
