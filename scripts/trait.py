
# ============================================================================
# MODULE : trait.py
# DESCRIPTION : Module de traitement des données de traitement et diagnostics
#              Gestion des fractions, boost, codes CIM-10 et diagnostics
# ============================================================================

from collections import defaultdict

import numpy as np
import pandas as pd
import pyodbc
import sys
import time
import platform
import subprocess
import os
import re
from numba import njit
import gc

# Import des fonctions du module sys.py
from sys import (
    lire_excel_accelere,
    requete_sql,
    convert_csv_to_xlsx,
    save_data_excel,
    save_large_excel,
    save_data_excel_by_multiple_requests,
    add_columns,
    detecter_gpu_systeme,
    installer_dependances_gpu
)

# ============================================================================
# FONCTION : maj_fractions_par_prescription
# OBJECTIF : Met à jour les fractions par prescription avec gestion spéciale ETHOS
# ENTRÉES :
#   - df : DataFrame contenant les données de traitement
# SORTIE : DataFrame mis à jour avec fractions corrigées
# ============================================================================
def maj_fractions_par_prescription(df):
    """
    Met à jour les fractions par prescription avec gestion spéciale pour ETHOS.
    Gère les cas particuliers des machines ETHOS et les prescriptions multiples.
    """
    df = df.copy()
    # Vérification de la colonne DosePerFraction
    if 'DosePerFraction' not in df.columns:
        print("❌ La colonne 'DosePerFraction' n'existe pas dans le DataFrame.")
        return df
    else:
        print("✅ La colonne 'DosePerFraction' existe.")
        # Vérification de chaque ligne
        for idx, row in df.iterrows():
            val = row['DosePerFraction']
            if pd.isna(val) or str(val).strip() == '' or str(val).strip().upper() in ['NA', 'NULL']:
                print(f"❌ Ligne {idx} : valeur manquante ou vide pour DosePerFraction : {val}")
            else:
                print(f"Ligne {idx} : valeur DosePerFraction = {val}")
    
    # Cherche le nom de colonne patient
    patient_col = None
    for col in ['PatientId', 'pt_id']:
        if col in df.columns:
            patient_col = col
            break
    if patient_col is None:
        raise ValueError("Aucune colonne identifiant patient trouvée dans le DataFrame.")
    
    # Traitement par groupe patient + prescription
    for (patient_id, prescription), group in df.groupby([patient_col, 'PrescriptionName']):

        # Si aucune fraction n'a été effectuée
        if group['NbFractionsEffectués'].sum() == 0:
            continue

        machines = group['NomMachine'].dropna().unique()
        machines_lower = [str(m).lower() for m in machines]

        if 'ethos' in machines_lower:
            # 💡 Cas spécial ETHOS
            planned_frac_max = group['PlannedFrac'].max()

            # Compter les plans où au moins une ligne a un 1
            total_effectue = 0
            for plan_id, plan_group in group.groupby('PlanSetupId'):
                if (plan_group['NbFractionsEffectués'] == 1).any():
                    total_effectue += 1

            restant = planned_frac_max - total_effectue

            # Dose par fraction (on prend la première valeur non nulle)
            dose_per_frac = group['DosePerFraction'].dropna().unique()
            dose_par_fraction = dose_per_frac[0] if len(dose_per_frac) > 0 else 0.0
            dose_effectuee = total_effectue * dose_par_fraction

            # 💥 Mise à jour de toutes les lignes du groupe
            df.loc[group.index, 'PlannedFrac'] = planned_frac_max
            df.loc[group.index, 'NbFractionsEffectués'] = total_effectue
            df.loc[group.index, 'NbFractionsRestantes'] = restant
            df.loc[group.index, 'DoseEffectuée2'] = dose_effectuee

            continue  # On saute la suite, c'est un cas ETHOS

        # Cas général : plusieurs plans mais PAS ETHOS
        if group['PlanSetupId'].nunique() > 1:
            total_effectue = 0
            dose_effectuee = 0.0

            for plan_id, plan_group in group.groupby('PlanSetupId'):
                nb_frac = plan_group['NbFractionsEffectués'].max()
                dose_per_frac = plan_group['DosePerFraction'].dropna().unique()
                if len(dose_per_frac) == 1:
                    dose_per_frac = dose_per_frac[0]
                elif len(dose_per_frac) > 1:
                    dose_per_frac = dose_per_frac[0]  # Cas ambigu, on prend la première valeur
                else:
                    print(f"ATTENTION: Aucune dose trouvée pour patient={patient_id}, prescription={prescription}, plan_id={plan_id}")
                    dose_per_frac = 0.0
                total_effectue += nb_frac
                dose_effectuee += nb_frac * dose_per_frac

            planned_frac = group['PlannedFrac'].iloc[0]
            if total_effectue >= planned_frac:
                continue

            restant = planned_frac - total_effectue

            df.loc[group.index, 'NbFractionsEffectués'] = total_effectue
            df.loc[group.index, 'NbFractionsRestantes'] = restant
            df.loc[group.index, 'DoseEffectuée2'] = dose_effectuee

    return df


# ============================================================================
# FONCTION : boost
# OBJECTIF : Concatène les phases PRIMARY et BOOST pour chaque patient
# ENTRÉES :
#   - df : DataFrame contenant les données de traitement
# SORTIE : DataFrame avec phases concaténées
# ============================================================================
def boost(df):
    """
    Concatène les phases PRIMARY et BOOST pour chaque patient.
    Combine les informations de base et de boost en une seule ligne par patient.
    """
    import pandas as pd

    # Nettoyage
    df['PhaseType'] = df['PhaseType'].astype(str).str.strip().str.upper()
    df['PlanSetupId'] = df['PlanSetupId'].astype(str).str.strip()

    # Conversion des dates
    df['PremiereFractionChamp'] = pd.to_datetime(df['PremiereFractionChamp'], errors='coerce')
    df['DerniereFractionChamp'] = pd.to_datetime(df['DerniereFractionChamp'], errors='coerce')

    lignes_finales = []

    # Colonnes à concaténer comme base + boost
    colonnes_a_concat = [
        "DosePerFraction", "PlannedFrac", "NbFractionsEffectués", "NbFractionsRestantes",
        "DosesTotal2", "DoseEffectuée2", "PrescriptionName", "PrescriptionTemplateName"
    ]

    # Traitement par patient
    for patient_id, group in df.groupby('PatientId'):
        # Filtrer les lignes où PremiereFractionChamp n'est pas NaN
        groupe_non_nul = group.dropna(subset=['PremiereFractionChamp'])
        if groupe_non_nul.empty:
            continue  # ou passer, ou gérer autrement selon ton besoin
        ligne_base = groupe_non_nul.loc[groupe_non_nul['PremiereFractionChamp'].idxmin()].copy()

        # PhaseType concaténé
        phase_types = group['PhaseType'].dropna().unique()
        phase_order = ['PRIMARY', 'BOOST']
        phase_concat = ' + '.join(pt for pt in phase_order if pt in phase_types)

        # Première fraction
        first_fraction = group['PremiereFractionChamp'].min()

        # Dernière fraction : date base + boost
        base_last = ligne_base['DerniereFractionChamp']
        boost_last_dates = group.loc[group['PhaseType'] == "BOOST", 'DerniereFractionChamp'].dropna()
        if not boost_last_dates.empty:
            boost_last = boost_last_dates.max()
            if pd.notna(base_last):
                #last_concat = base_last.strftime("%Y-%m-%d") + ' + ' + boost_last.strftime("%Y-%m-%d")
                last_concat = boost_last.strftime("%Y-%m-%d")
            else:
                last_concat = boost_last.strftime("%Y-%m-%d")
        else:
            last_concat = base_last.strftime("%Y-%m-%d") if pd.notna(base_last) else ""

        # PlanSetup concaténé
        plan_concat = '+'.join(group['PlanSetupId'].dropna().unique())

        # Concaténation des colonnes supplémentaires
        for col in colonnes_a_concat:
            base_val = ligne_base[col]
            boost_vals = group.loc[group['PhaseType'] == "BOOST", col].dropna()
            if not boost_vals.empty:
                boost_val = boost_vals.iloc[0]
                ligne_base[col] = f"{base_val} + {boost_val}"
            else:
                ligne_base[col] = base_val

        # Mise à jour
        ligne_base['PhaseType'] = phase_concat
        ligne_base['PremiereFractionChamp'] = first_fraction
        ligne_base['DerniereFractionChamp'] = last_concat
        ligne_base['PlanSetupId'] = plan_concat

        lignes_finales.append(ligne_base)

    return pd.DataFrame(lignes_finales)


# ============================================================================
# FONCTION : get_first_cim10_code
# OBJECTIF : Retourne le premier code CIM-10 pour chaque patient
# ENTRÉES :
#   - data : DataFrame contenant les données avec codes CIM-10
# SORTIE : Series avec premier code CIM-10 par patient
# ============================================================================
def get_first_cim10_code(data):
    """
    Doit retourner le premier code CIM10 pour chaque patient.
    Trie par date de première fraction et prend le premier code pour chaque patient.
    """
    if 'PremiereFractionChamp' not in data.columns or 'pt_id' not in data.columns:
        raise ValueError("Colonnes 'PremiereFractionChamp' ou 'pt_id' absentes des données ❌")

    # Grouper par patient et prendre le premier code pour chaque patient
    first_codes = (
        data.sort_values('PremiereFractionChamp')
        .groupby('pt_id', as_index=True)['DiagnosisCode']
        .first()
    )
    return first_codes


# ============================================================================
# FONCTION : get_line_first_fraction_with_additional_columns
# OBJECTIF : Retourne la ligne de première fraction enrichie avec colonnes supplémentaires
# ENTRÉES :
#   - data : DataFrame contenant les données de traitement
# SORTIE : DataFrame avec une ligne par patient enrichie
# ============================================================================
def get_line_first_fraction_with_additional_columns(data):
    """
    Retourne pour chaque patient la ligne la plus ancienne (par 'PremiereFractionChamp') enrichie avec les colonnes
    supplémentaires. Si une valeur est absente dans cette ligne, on la récupère ailleurs
    dans le DataFrame (première valeur non nulle et non 'NULL' ou vide trouvée) pour ce même patient.
    """
    additional_columns = [
        "crit_desc", "date_staged", "Stade_Tumoral", "Stade_Nodal", "Stade_Metastase",
        "Facteur_HER2", "Recepteur_Estrogene", "Recepteur_Progesterone",
        "Score_Oncologique", "Age_Diagnostic", "Niveau_PSA", "Grade_Histologique", "Autres"
    ]

    if data.empty or 'PremiereFractionChamp' not in data.columns or 'pt_id' not in data.columns:
        return pd.DataFrame()

    # Initialisation de la liste qui contiendra les résultats pour chaque patient
    result_rows = []

    # Pour chaque patient unique
    for pt_id in data['pt_id'].unique():
        # Filtrer les données pour ce patient
        patient_data = data[data['pt_id'] == pt_id]

        # Obtenir la ligne avec la première fraction pour ce patient
        patient_data_sorted = patient_data.sort_values(by='PremiereFractionChamp')
        if patient_data_sorted.empty:
            continue  # ou return None, ou passe au suivant selon le contexte
        ligne = patient_data_sorted.iloc[0].copy()

        # Pour chaque colonne additionnelle
        for col in additional_columns:
            if col in patient_data.columns:
                valeur = ligne.get(col)
                if pd.isna(valeur) or str(valeur).strip().upper() in ["", "NA", "NULL"]:
                    # Filtrer les lignes valides pour ce patient uniquement
                    serie_filtree = (patient_data[col]
                                     .dropna()
                                     .astype(str)
                                     .apply(str.strip)
                                     .replace(["", "NULL", "NA"], pd.NA)
                                     .dropna())
                    ligne[col] = serie_filtree.iloc[0] if not serie_filtree.empty else None
            else:
                ligne[col] = None

        result_rows.append(ligne)

    # Convertir la liste de résultats en DataFrame
    result_df = pd.DataFrame(result_rows)

    print(f"Nombre de patients traités : {len(result_df)}")

    return result_df


# ============================================================================
# FONCTION : apply_mapping_cim10
# OBJECTIF : Applique un mapping de codes CIM-10 pour enrichir les données
# ENTRÉES :
#   - data_df : DataFrame des données principales
#   - mapping_df : DataFrame contenant le mapping CIM-10
# SORTIE : DataFrame enrichi avec les données du mapping
# ============================================================================
def apply_mapping_cim10(data_df, mapping_df):
    """
    Applique un mapping de codes CIM-10 pour enrichir les données.
    Associe chaque code diagnostic avec les informations du mapping.
    """
    print("\n=== Colonnes disponibles dans mapping_df ===")
    print(mapping_df.columns.tolist())

    # Vérification de l'existence de la colonne
    if 'CIM 10' not in mapping_df.columns:
        print("⚠️ La colonne 'CIM 10' n'existe pas.")
        print("Colonnes disponibles :", mapping_df.columns.tolist())
        raise ValueError("La colonne 'CIM 10' est manquante dans le fichier de mapping")

    mapping_df['CIM 10'] = mapping_df['CIM 10'].astype(str).str.strip().str.upper()
    # ... reste du code

    result_rows = []
    for _, row in data_df.iterrows():
        code = str(row['DiagnosisCode']).strip().upper()
        ligne_mapping = mapping_df[mapping_df['CIM 10'] == code]

        if not ligne_mapping.empty:
            # Renommer les colonnes du mapping si elles existent déjà
            rename_dict = {col: f"{col}_mapping"
                           for col in ligne_mapping.columns
                           if col in data_df.columns and col != 'CIM 10'}
            ligne_mapping = ligne_mapping.rename(columns=rename_dict)

            # Fusionner les données
            row_enrichie = pd.concat([pd.Series(row), ligne_mapping.iloc[0]])
            result_rows.append(row_enrichie)
        else:
            result_rows.append(pd.Series(row))

    return pd.DataFrame(result_rows)


# ============================================================================
# FONCTION : select_cim
# OBJECTIF : Sélectionne les patients avec des codes CIM-10 spécifiques
# ENTRÉES :
#   - df : DataFrame contenant les codes diagnostics
# SORTIE : DataFrame filtré avec les codes CIM-10 spécifiés
# ============================================================================
def select_cim(df):
    """
    Sélectionne les lignes avec des codes CIM-10 spécifiques (C50.%, C61.%, C79.5) dans la colonne DiagnosisCode.
    Retourne un DataFrame avec les patients ayant ces codes diagnostics.
    """
    # Création du masque pour les codes CIM-10 recherchés
    mask = (df['DiagnosisCode'].str.contains('C50', na=False) |
            df['DiagnosisCode'].str.contains('C61', na=False) |
            df['DiagnosisCode'].str.contains('C79', na=False))

    # Sélection des lignes correspondant aux codes CIM-10 spécifiés
    df_filtered = df[mask].copy()

    if df_filtered.empty:
        print("Aucun patient trouvé avec les codes CIM-10 spécifiés (C50.%, C61.%, C79.5)")
        return pd.DataFrame()

    print(f"Nombre de patients trouvés avec les codes CIM-10 spécifiés : {len(df_filtered)}")
    return df_filtered


# ============================================================================
# FONCTION : get_primary_and_complete_diag
# OBJECTIF : Retourne les diagnostics primaires et complets pour chaque patient
# ENTRÉES :
#   - data : DataFrame contenant les données de diagnostic
# SORTIE : DataFrame avec diagnostics primaires et complets
# ============================================================================
def get_primary_and_complete_diag(data):
    """
    Retourne les diagnostics primaires et complets pour chaque patient.
    Identifie le diagnostic principal et concatène tous les diagnostics.
    """
    if data.empty:
        return pd.DataFrame({'pt_id': [], 'DiagPrimaire': [], 'DiagComplet': []})

    result = []
    for pt_id in data['pt_id'].unique():
        patient_data = data[data['pt_id'] == pt_id]
        prmy_dx_ids = patient_data['prmy_dx_id'].dropna().unique()
        diag_primaire = None

        if len(prmy_dx_ids) > 0:
            id_primaire = prmy_dx_ids[0]
            ligne_primaire = patient_data[patient_data['pt_dx_id'] == id_primaire]
            if not ligne_primaire.empty:
                diag_primaire = ligne_primaire.iloc[0]['DiagnosisCode']

        diag_complet = " + ".join(patient_data['DiagnosisCode'].dropna().unique())

        result.append({
            'pt_id': pt_id,
            'DiagPrimaire': diag_primaire,
            'DiagComplet': diag_complet
        })

    return pd.DataFrame(result)

