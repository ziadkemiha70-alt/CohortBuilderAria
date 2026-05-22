# -*- coding: utf-8 -*-
"""Rapports de contrôle qualité et traçabilité pipeline."""

from typing import Any, Dict

import pandas as pd


def _safe_ratio_ok(numer: int, denom: int, threshold: float = 0.95) -> bool:
    if denom == 0:
        return False
    return (numer / denom) >= threshold


def build_quality_report(
    tx: pd.DataFrame,
    fm: pd.DataFrame,
    cohort: pd.DataFrame,
    patient_base: pd.DataFrame,
    forms_long: pd.DataFrame,
    config: pd.DataFrame,
    duplicates: pd.DataFrame,
    treatment_consistency: pd.DataFrame | None = None,
) -> pd.DataFrame:
    tx_keys = tx["_pt_join_key"].dropna().drop_duplicates()
    fm_keys = set(fm["_pt_join_key"].dropna())
    cohort_keys = cohort["_pt_join_key"].dropna().drop_duplicates()

    tx_in_form = int(tx_keys.isin(fm_keys).sum())
    cohort_in_form = int(cohort_keys.isin(fm_keys).sum())
    tx_n = int(tx_keys.nunique())
    cohort_n = int(cohort_keys.nunique())

    rows = [
        {
            "controle": "Patients traitement retrouvés dans formulaire",
            "resultat": f"{tx_in_form} / {tx_n}",
            "niveau": "OK" if _safe_ratio_ok(tx_in_form, tx_n) else "A vérifier",
        },
        {
            "controle": "Patients cohorte retrouvés dans formulaire",
            "resultat": f"{cohort_in_form} / {cohort_n}",
            "niveau": (
                "OK" if _safe_ratio_ok(cohort_in_form, cohort_n) else "A vérifier"
            ),
        },
        {
            "controle": "Patients avec startD",
            "resultat": f"{int(patient_base['startD'].notna().sum())} / {int(patient_base['_pt_join_key'].nunique())}",
            "niveau": "OK",
        },
        {
            "controle": "Patients avec endD",
            "resultat": f"{int(patient_base['endD'].notna().sum())} / {int(patient_base['_pt_join_key'].nunique())}",
            "niveau": "OK",
        },
        {
            "controle": "Colonnes sélectionnées",
            "resultat": (
                int(config["Inclure"].sum())
                if not config.empty and "Inclure" in config.columns
                else 0
            ),
            "niveau": "OK",
        },
        {
            "controle": "Valeurs formulaire longues conservées",
            "resultat": int(len(forms_long)),
            "niveau": "OK" if len(forms_long) > 0 else "A vérifier",
        },
        {
            "controle": "Doublons exacts patient/item/date/valeur",
            "resultat": int(len(duplicates)),
            "niveau": "OK" if len(duplicates) == 0 else "Info",
        },
        {
            "controle": "Dates formulaire invalides dans sélection",
            "resultat": (
                int(forms_long["DateHeure"].isna().sum()) if not forms_long.empty else 0
            ),
            "niveau": (
                "OK"
                if forms_long.empty or forms_long["DateHeure"].isna().sum() == 0
                else "A vérifier"
            ),
        },
    ]

    if "_source_traitement" in tx.columns and "_pt_join_key" in tx.columns:
        source_counts = (
            tx.dropna(subset=["_pt_join_key"])
            .groupby("_source_traitement", dropna=False)["_pt_join_key"]
            .nunique()
            .reset_index(name="patients")
        )
        for _, row in source_counts.iterrows():
            rows.append(
                {
                    "controle": f"Patients source traitement : {row['_source_traitement']}",
                    "resultat": int(row["patients"]),
                    "niveau": "Info",
                }
            )

    if "_source_traitement" in cohort.columns and "_pt_join_key" in cohort.columns:
        cohort_source_counts = (
            cohort.dropna(subset=["_pt_join_key"])
            .groupby("_source_traitement", dropna=False)["_pt_join_key"]
            .nunique()
            .reset_index(name="patients")
        )
        for _, row in cohort_source_counts.iterrows():
            rows.append(
                {
                    "controle": f"Patients cohorte source : {row['_source_traitement']}",
                    "resultat": int(row["patients"]),
                    "niveau": "Info",
                }
            )

    if treatment_consistency is not None and not treatment_consistency.empty:
        rows.append(
            {
                "controle": "Patients avec plusieurs valeurs de dose/date/fractions/machine",
                "resultat": (
                    int(treatment_consistency["_pt_join_key"].nunique())
                    if "_pt_join_key" in treatment_consistency.columns
                    else int(len(treatment_consistency))
                ),
                "niveau": "A vérifier",
            }
        )
        conflict_by_type = (
            treatment_consistency.groupby("champ", dropna=False)
            .size()
            .reset_index(name="patients_concernes")
        )
        for _, row in conflict_by_type.iterrows():
            rows.append(
                {
                    "controle": f"Détail incohérences traitement : {row['champ']}",
                    "resultat": int(row["patients_concernes"]),
                    "niveau": "A vérifier",
                }
            )
    else:
        rows.append(
            {
                "controle": "Unicité dose/date/fractions/machine par patient",
                "resultat": "Aucune incohérence détectée",
                "niveau": "OK",
            }
        )

    return pd.DataFrame(rows)


def build_pipeline_sheet(params: Dict[str, Any]) -> pd.DataFrame:
    ethos_text = (
        " ; ETHOS optionnel intégré comme traitement supplémentaire"
        if params.get("ethos_used")
        else ""
    )
    rows = [
        {
            "ordre": 0,
            "étape": "Chargement",
            "objectif": "Importer traitement_patient et formulaire_patient. mapping.csv reste optionnel."
            + ethos_text,
            "contrôle": "pt_id et date_event disponibles",
        },
        {
            "ordre": 1,
            "étape": "Choix CIM10",
            "objectif": f"Mode={params.get('mode_cim10')}; CIM10={params.get('cim10') or 'Tous'}; dose_non_nulle={params.get('dose_non_nulle')}",
            "contrôle": "cohorte patient créée",
        },
        {
            "ordre": 2,
            "étape": "Aide mapping",
            "objectif": f"Mapping chargé={params.get('mapping_used')}; profil={params.get('mapping_profile') or 'NA'}",
            "contrôle": "suggestions non bloquantes",
        },
        {
            "ordre": 3,
            "étape": "Sélection colonnes",
            "objectif": "Choisir les colonnes formulaire à transformer en colonnes ODM génériques.",
            "contrôle": "table de sélection validée",
        },
        {
            "ordre": 4,
            "étape": "Temporalités",
            "objectif": "Cocher Cumul / Avant RT / Aigu / Tardif pour chaque item.",
            "contrôle": "schéma dérivé généré",
        },
        {
            "ordre": 5,
            "étape": "Fenêtres",
            "objectif": "Avant RT en semaines avant startD, aigu pendant RT, tardif après endD en semaines/mois.",
            "contrôle": f"délais référencés sur {params.get('delay_reference')}",
        },
        {
            "ordre": 6,
            "étape": "Contrôle qualité",
            "objectif": "Vérifier join, dates, valeurs, doublons, sources traitement et colonnes générées.",
            "contrôle": "onglet Qualité",
        },
        {
            "ordre": 7,
            "étape": "Exports",
            "objectif": "Créer un export final propre et un rapport de preuve.",
            "contrôle": "NA remplace les vides",
        },
    ]
    return pd.DataFrame(rows)
