# ============================================================================
# MODULE : toxicites.py
# DESCRIPTION : Module de traitement des toxicités et calculs temporels
#              Gestion des fenêtres temporelles, fusion de données et agrégation
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
try:
    from numba import njit
except Exception:
    njit = None
import gc

# Import des fonctions utilitaires
from utils.sql_io import (
    lire_excel_accelere,
    requete_sql,
    convert_csv_to_xlsx,
    save_data_excel,
    save_large_excel,
    save_data_excel_by_multiple_requests,
    add_columns,
    detecter_gpu_systeme,
    installer_dependances_gpu,
)

# ============================================================================
# FONCTION : get_fenetre_temporelle
# OBJECTIF : Détermine la fenêtre temporelle d'un événement par rapport à la radiothérapie
# ENTRÉES :
#   - row : Ligne de données contenant les dates et pt_id
# SORTIE : String indiquant la fenêtre temporelle ou None
# ============================================================================
def get_fenetre_temporelle(row):
    """
    Calcule la fenêtre temporelle d'un événement par rapport aux dates de radiothérapie.
    Gère les périodes avant RT, pendant RT (aiguë) et après RT (tardive).
    """
    # Gérer les différents noms possibles des colonnes
    premiere = None
    derniere = None

    # Chercher les colonnes avec différents suffixes
    for col in row.index:
        if 'PremiereFractionChamp' in col:
            premiere = row[col]
            break

    for col in row.index:
        if 'DerniereFractionChamp' in col:
            derniere = row[col]
            break

    date_event = row['date_event']

    if pd.isna(premiere) or pd.isna(derniere) or pd.isna(date_event):
        return None

    delai_premiere = (date_event - premiere).days
    delai_derniere = (date_event - derniere).days

    # Avant RT : par pas de 7 jrs puis 30 jrs, référence = 1ère séance
    if date_event < premiere:
        # Debug spécifique pour le patient 32040000000000014023
        if row['pt_id'] == '32040000000000014023':
            print(
                f"DEBUG PATIENT: pt_id={row['pt_id']}, date_event={date_event}, premiere={premiere}, delai_premiere={delai_premiere}")

        if delai_premiere < -180:
            return "AvantRT_<180j"
        elif -180 <= delai_premiere < -160:
            return "AvantRT_180-160j"
        elif -160 <= delai_premiere < -130:
            return "AvantRT_159-130j"
        elif -130 <= delai_premiere < -100:
            return "AvantRT_129-100j"
        elif -100 <= delai_premiere < -70:
            return "AvantRT_99-70j"
        elif -70 <= delai_premiere < -40:
            return "AvantRT_69-40j"
        elif -40 <= delai_premiere < 0:
            return "AvantRT_39-1j"


    # Pendant/Aigu : par pas de 7 jrs, référence = 1ère séance, jusqu'à 90 jrs après
    elif delai_premiere <= 90:
        semaine = delai_premiere // 7 + 1
        return f"Aigu_Semaine_{semaine:02d}"

    # Après RT/Tardif : par mois/tranches, référence = dernière séance
    else:
        if delai_derniere < 1:  # Avant la dernière séance
            return None

        mois = delai_derniere // 30 + 1

        if mois == 1:
            return "Tardif_Mois_01"
        elif mois == 2:
            return "Tardif_Mois_02"
        elif mois == 3:
            return "Tardif_Mois_03"
        elif mois == 4:
            return "Tardif_Mois_04"
        elif 5 <= mois <= 7:
            return "Tardif_Mois_05-07"
        elif 8 <= mois <= 10:
            return "Tardif_Mois_08-10"
        elif 11 <= mois <= 13:
            return "Tardif_Mois_11-13"
        elif 14 <= mois <= 16:
            return "Tardif_Mois_14-16"
        elif 17 <= mois <= 19:
            return "Tardif_Mois_17-19"
        elif 20 <= mois <= 22:
            return "Tardif_Mois_20-22"
        elif 23 <= mois <= 26:
            return "Tardif_Mois_23-26"
        elif 27 <= mois <= 33:
            return "Tardif_Mois_27-33"
        elif 34 <= mois <= 38:
            return "Tardif_Mois_34-38"
        elif 39 <= mois <= 45:
            return "Tardif_Mois_39-45"
        elif 46 <= mois <= 51:
            return "Tardif_Mois_46-51"
        elif 52 <= mois <= 58:
            return "Tardif_Mois_52-58"
        elif 59 <= mois <= 62:
            return "Tardif_Mois_59-62"
        elif mois > 62:
            return "Tardif_Mois_>62"
        else:
            return None


# ============================================================================
# FONCTION : calculer_metriques_toxicite_cpu
# OBJECTIF : Calcule les métriques de toxicité avec optimisation CPU
# ENTRÉES :
#   - df : DataFrame contenant les données de toxicité
# SORTIE : DataFrame avec métriques calculées
# ============================================================================
def calculer_metriques_toxicite_cpu(df):
    """
    Version CPU optimisée pour le calcul des métriques de toxicité.
    Utilise des opérations vectorisées pandas pour de meilleures performances.
    """
    print("\n=== Calcul métriques CPU optimisé (fenêtres personnalisées) ===")
    date_columns = ["date_event", "PremiereFractionChamp", "DerniereFractionChamp"]
    for col in date_columns:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')

    # Calcul du délai selon la période
    df["Delai"] = None  # Initialisation

    # Masques pour les différentes périodes
    avant_rt = df["date_event"] < df["PremiereFractionChamp"]
    pendant_rt = (df["date_event"] >= df["PremiereFractionChamp"]) & ((df["date_event"] - df["PremiereFractionChamp"]).dt.days <= 90)
    apres_rt = (df["date_event"] - df["DerniereFractionChamp"]).dt.days > 0

    # Délai par rapport à la 1ère séance pour avant et pendant
    df.loc[avant_rt | pendant_rt, "Delai"] = (df.loc[avant_rt | pendant_rt, "date_event"] - df.loc[avant_rt | pendant_rt, "PremiereFractionChamp"]).dt.days

    # Délai par rapport à la dernière séance pour après
    df.loc[apres_rt, "Delai"] = (df.loc[apres_rt, "date_event"] - df.loc[apres_rt, "DerniereFractionChamp"]).dt.days

    # Calcul de la fenêtre temporelle
    df["FenetreTemporelle"] = df.apply(get_fenetre_temporelle, axis=1)

    # Ajout de la colonne TypeToxicite pour la réorganisation
    if "tox" in df.columns:
        df["TypeToxicite"] = df["tox"].astype(str) + "_" + df["FenetreTemporelle"].astype(str)
    else:
        df["TypeToxicite"] = df["FenetreTemporelle"].astype(str)

    return df


# ============================================================================
# FONCTION : calculer_metriques_toxicite_numba_simple
# OBJECTIF : Calcule les métriques avec Numba JIT pour accélération
# ENTRÉES :
#   - df : DataFrame contenant les données de toxicité
# SORTIE : DataFrame avec métriques calculées ou fallback CPU
# ============================================================================
def calculer_metriques_toxicite_numba_simple(df):
    """
    Version simplifiée du calcul des métriques avec Numba JIT.
    Utilise l'accélération JIT pour améliorer les performances.
    Fallback automatique vers CPU en cas d'erreur.
    """
    print("\n=== Calcul métriques Numba simplifié ===")

    try:
        # Créer un nouveau DataFrame pour les résultats
        resultats = df.copy()

        # Calculer la semaine par rapport à la première fraction
        resultats['Semaine'] = None
        for idx in resultats.index:
            delai = resultats.loc[idx, 'Delai']
            if pd.notna(delai):
                # Pour AvantRT
                if delai < 0:
                    semaine = -(abs(delai) // 7)
                # Pour Aigu et Tardif
                else:
                    semaine = delai // 7
                resultats.loc[idx, 'Semaine'] = semaine

        # Déterminer la période
        resultats['Periode'] = None
        resultats['TypeToxicite'] = None

        for idx in resultats.index:
            delai = resultats.loc[idx, 'Delai']
            fenetre = resultats.loc[idx, 'FenetreTemporelle']
            if pd.notna(delai) and pd.notna(fenetre):
                # AvantRT
                if delai < 0:
                    resultats.loc[idx, 'Periode'] = 'AvantRT'
                    semaine = resultats.loc[idx, 'Semaine']
                    resultats.loc[idx, 'TypeToxicite'] = f'AvantRT_Semaine_{semaine:02d}'
                # Aigu (0-90 jours)
                elif delai <= 90:
                    resultats.loc[idx, 'Periode'] = 'Aigu'
                    semaine = resultats.loc[idx, 'Semaine']
                    resultats.loc[idx, 'TypeToxicite'] = f'Aigu_Semaine_{semaine:03d}'
                # Tardif (>90 jours)
                else:
                    resultats.loc[idx, 'Periode'] = 'Tardif'
                    semaine = resultats.loc[idx, 'Semaine']
                    resultats.loc[idx, 'TypeToxicite'] = f'Tardif_Semaine_{semaine:03d}'

        print(f"✅ Métriques calculées: {len(resultats)} lignes")
        return resultats

    except Exception as e:
        print(f"❌ Erreur Numba, fallback CPU: {e}")
        return calculer_metriques_toxicite_cpu(df)




# ============================================================================
# FONCTION : analyse_toxicites_all_and_date
# OBJECTIF : Analyse complète des toxicités avec ajout des dates de traitement
# ENTRÉES :
#   - toxicity_data : DataFrame des données de toxicité
#   - traitement_data : DataFrame des données de traitement
#   - filename : Nom du fichier de sortie
# SORTIE : DataFrame avec métriques calculées et sauvegardé
# ============================================================================
def analyse_toxicites_all_and_date(toxicity_data, traitement_data, filename):
    """
    Fonction wrapper qui ajoute les dates de première et dernière fraction selon pt_id.
    Effectue une analyse complète des toxicités avec calcul des métriques temporelles.
    """
    print(f"\n=== Traitement toxicités avec dates de traitement pour {toxicity_data['pt_id'].nunique()} patients ===")

    # Harmoniser le type de pt_id
    toxicity_data['pt_id'] = toxicity_data['pt_id'].astype(str)
    traitement_data['pt_id'] = traitement_data['pt_id'].astype(str)

    # Nettoyage des colonnes inutiles
    cols_to_drop = [col for col in ["PatientID", "ToxicityID", "Ligne"] if col in toxicity_data.columns]
    toxicites = toxicity_data.drop(columns=cols_to_drop)

    if "pt_id" not in toxicites.columns or "pt_id" not in traitement_data.columns:
        print("Clé de jointure manquante pour ajouter les fractions.")
        return toxicites

    # Formatage des dates
    for col in ["PremiereFractionChamp", "DerniereFractionChamp"]:
        if col in traitement_data.columns:
            traitement_data[col] = pd.to_datetime(traitement_data[col], errors='coerce')
    if "date_event" in toxicites.columns:
        toxicites["date_event"] = pd.to_datetime(toxicites["date_event"], errors='coerce')

    result = []
    patients_traites = set()

    # Traitement ligne par ligne pour associer les dates de traitement
    for idx, tox_row in toxicites.iterrows():
        pt_id = tox_row["pt_id"]
        date_event = tox_row["date_event"]
        patients_traites.add(pt_id)

        # On récupère toutes les paires (Premiere, Derniere) pour ce patient
        patient_fractions = traitement_data[traitement_data["pt_id"] == pt_id]
        premiere = None
        derniere = None

        if not patient_fractions.empty:
            # Chercher une correspondance exacte d'abord
            match = patient_fractions[patient_fractions["PremiereFractionChamp"] == date_event]
            if not match.empty:
                premiere = date_event
                derniere = match.iloc[0]["DerniereFractionChamp"]
            else:
                # Si pas de correspondance exacte, prendre la première fraction du patient
                premiere = patient_fractions["PremiereFractionChamp"].iloc[0] if not patient_fractions["PremiereFractionChamp"].isna().all() else None
                derniere = patient_fractions["DerniereFractionChamp"].iloc[0] if not patient_fractions["DerniereFractionChamp"].isna().all() else None

        # Créer le dictionnaire avec toutes les colonnes importantes
        row_dict = {
            "pt_id": pt_id,
            "date_event": date_event,
            "PremiereFractionChamp": premiere,
            "DerniereFractionChamp": derniere
        }

        # Ajouter toutes les colonnes de toxicité
        for col in toxicites.columns:
            if col not in ["pt_id", "date_event"]:
                row_dict[col] = tox_row.get(col)

        result.append(row_dict)

    df_final = pd.DataFrame(result)

    print(f"Nombre de patients traités : {len(patients_traites)}")
    print(f"Nombre de lignes avant suppression des doublons : {len(df_final)}")

    # Supprime les doublons sur pt_id ET date_event (garde la première occurrence)
    if "date_event" in df_final.columns and "pt_id" in df_final.columns:
        df_final = df_final.drop_duplicates(subset=["pt_id", "date_event"], keep="first")
        print(f"Nombre de lignes après suppression des doublons : {len(df_final)}")

    # Calculer les métriques temporelles
    df_metriques = calculer_metriques_toxicite_numba_simple(df_final)
    print(f"✅ Métriques calculées : {len(df_metriques)} lignes")

    save_data_excel(df_metriques, filename)

    return df_metriques



# ============================================================================
# FONCTION : fusionner_toxicites_fractions_cpu
# OBJECTIF : Fusion optimisée des données de toxicité et de traitement (CPU)
# ENTRÉES :
#   - toxicity_data : DataFrame des données de toxicité
#   - traitement_data : DataFrame des données de traitement
# SORTIE : DataFrame fusionné avec opérations vectorisées
# ============================================================================
def fusionner_toxicites_fractions_cpu(toxicity_data, traitement_data):
    """
    Version CPU optimisée avec vectorisation pandas.
    Utilise des opérations vectorisées pour de meilleures performances.
    """
    print("\n=== Fusion CPU optimisée ===")

    # Nettoyage des colonnes
    cols_to_drop = [col for col in ["PatientID", "ToxicityID", "Ligne"] if col in toxicity_data.columns]
    toxicites = toxicity_data.drop(columns=cols_to_drop)

    if "pt_id" not in toxicites.columns or "pt_id" not in traitement_data.columns:
        return toxicites

    # Conversion des dates vectorisée
    for col in ["PremiereFractionChamp", "DerniereFractionChamp"]:
        if col in traitement_data.columns:
            traitement_data[col] = pd.to_datetime(traitement_data[col], errors='coerce')

    if "date_event" in toxicites.columns:
        toxicites["date_event"] = pd.to_datetime(toxicites["date_event"], errors='coerce')

    # Fusion optimisée avec merge
    result = toxicites.merge(
        traitement_data[["pt_id", "PremiereFractionChamp", "DerniereFractionChamp"]],
        on="pt_id",
        how="left"
    )

    # Suppression des doublons vectorisée
    if "date_event" in result.columns and "pt_id" in result.columns:
        result = result.drop_duplicates(subset=["pt_id", "date_event"], keep="first")

    return result


# ============================================================================
# FONCTION : fusionner_toxicites_fractions_numba_simple
# OBJECTIF : Fusion optimisée avec Numba JIT pour accélération
# ENTRÉES :
#   - toxicity_data : DataFrame des données de toxicité
#   - traitement_data : DataFrame des données de traitement
# SORTIE : DataFrame fusionné avec délais calculés par Numba
# ============================================================================
def fusionner_toxicites_fractions_numba_simple(toxicity_data, traitement_data):
    """
    Version Numba JIT pour la fusion des données avec calcul accéléré des délais.
    Utilise Numba JIT pour optimiser les calculs de délais temporels.
    """
    print("\n=== Fusion Numba simplifiée ===")

    try:
        import numba
        from numba import jit

        @jit(nopython=True)
        def calculer_delais_numba(dates_event, dates_premiere):
            """
            Fonction Numba JIT pour calculer les délais entre dates.
            Conversion optimisée de nanosecondes vers jours.
            """
            n = len(dates_event)
            delais = np.empty(n, dtype=np.int64)

            for i in range(n):
                if dates_premiere[i] > 0 and dates_event[i] > 0:
                    # Conversion correcte : nanosecondes -> jours
                    delais[i] = (dates_event[i] - dates_premiere[i]) // (24 * 3600 * 1_000_000_000)
                else:
                    delais[i] = 0

            return delais

        # Nettoyage des colonnes
        cols_to_drop = [col for col in ["PatientID", "ToxicityID", "Ligne"] if col in toxicity_data.columns]
        toxicites = toxicity_data.drop(columns=cols_to_drop)

        if "pt_id" not in toxicites.columns or "pt_id" not in traitement_data.columns:
            return toxicites

        # Conversion des dates
        for col in ["PremiereFractionChamp", "DerniereFractionChamp"]:
            if col in traitement_data.columns:
                traitement_data[col] = pd.to_datetime(traitement_data[col], errors='coerce')

        if "date_event" in toxicites.columns:
            toxicites["date_event"] = pd.to_datetime(toxicites["date_event"], errors='coerce')

        # Fusion simple avec merge pandas optimisé
        result = toxicites.merge(
            traitement_data[["pt_id", "PremiereFractionChamp", "DerniereFractionChamp"]],
            on="pt_id",
            how="left"
        )

        # Calcul des délais avec Numba
        if not result.empty and "date_event" in result.columns and "PremiereFractionChamp" in result.columns:
            dates_event = result['date_event'].values.astype(np.int64)
            dates_premiere = result['PremiereFractionChamp'].values.astype(np.int64)

            delais = calculer_delais_numba(dates_event, dates_premiere)
            result['Delai'] = delais

            # Vérification des délais
            delais_valides = delais[delais != 0]
            if len(delais_valides) > 0:
                print(f"🔍 Vérification délais - Min: {delais_valides.min()}, Max: {delais_valides.max()}, Moy: {delais_valides.mean():.1f} jours")
                print(f"🔍 Nombre de délais valides: {len(delais_valides)} sur {len(delais)}")

        # Suppression des doublons
        if "date_event" in result.columns and "pt_id" in result.columns:
            result = result.drop_duplicates(subset=["pt_id", "date_event"], keep="first")

        print(f"✅ Fusion terminée: {len(result)} lignes")
        return result

    except Exception as e:
        print(f"❌ Erreur Numba, fallback CPU: {e}")
        return fusionner_toxicites_fractions_cpu(toxicity_data, traitement_data)


# ============================================================================
# FONCTION : creer_toxicites_agregees_sans_cumuls
# OBJECTIF : Création de toxicités agrégées par patient sans cumuls
# ENTRÉES :
#   - filename_tox : Chemin vers le fichier de toxicité
#   - filename_traitement : Chemin vers le fichier de traitement
#   - filename_output : Nom du fichier de sortie (défaut: "toxicites_agregees_sans_cumuls.xlsx")
# SORTIE : DataFrame agrégé et fichier Excel créé
# ============================================================================
def creer_toxicites_agregees_sans_cumuls(filename_tox, filename_traitement,
                                         filename_output="toxicites_agregees_sans_cumuls.xlsx"):
    """
    Crée un fichier Excel avec les toxicités agrégées par patient SANS les colonnes min/max/cumul.
    Pour chaque toxicité et chaque fenêtre temporelle, inclut :
    - La valeur (même si null)
    - Le délai entre première fraction et date_event
    - La date_event
    """
    print(f"\n=== Création toxicités agrégées SANS cumuls ===")

    # Charger les données
    print("Chargement des données...")
    df_tox = lire_excel_accelere(filename_tox)
    print(f"✅ {filename_tox} chargé : {len(df_tox)} lignes, {len(df_tox.columns)} colonnes")

    df_traitement = lire_excel_accelere(filename_traitement)
    print(f"✅ {filename_traitement} chargé : {len(df_traitement)} lignes, {len(df_traitement.columns)} colonnes")

    # Fusionner toxicité et traitement pour les dates
    df_fusionne = fusionner_toxicites_fractions_numba_simple(df_tox, df_traitement)
    print(f"✅ Fusion terminée : {len(df_fusionne)} lignes")

    # Afficher les colonnes disponibles pour debug
    print(f"Colonnes après fusion : {list(df_fusionne.columns)[:10]}...")

    # Identifier les colonnes de toxicité (exclure les colonnes de dates, IDs et statistiques)
    colonnes_exclues = ['pt_id', 'date_event', 'fenetre_temporelle']

    # Ajouter les colonnes qui peuvent ne pas exister
    colonnes_optionnelles = ['PremiereFractionChamp', 'DerniereFractionChamp', 'delai_premiere', 'delai_derniere']
    for col in colonnes_optionnelles:
        if col in df_fusionne.columns:
            colonnes_exclues.append(col)

    # Exclure les colonnes avec min/max/cumul dans le nom
    colonnes_tox = []
    for col in df_fusionne.columns:
        if col not in colonnes_exclues:
            # Exclure les colonnes qui contiennent min, max, cumul, moyenne, ecart
            if not any(mot in col.lower() for mot in ['min', 'max', 'cumul', 'moyenne', 'ecart', 'nombre']):
                colonnes_tox.append(col)

    print(f"✅ Colonnes de toxicité identifiées : {len(colonnes_tox)}")
    print(f"Exemples de colonnes tox : {colonnes_tox[:5]}")

    # Calculer les fenêtres temporelles pour chaque ligne
    print("Calcul des fenêtres temporelles...")
    df_fusionne['fenetre_temporelle'] = df_fusionne.apply(get_fenetre_temporelle, axis=1)

    # Filtrer les lignes avec des fenêtres temporelles valides
    df_filtre = df_fusionne[df_fusionne['fenetre_temporelle'].notna()].copy()
    print(f"✅ Lignes avec fenêtres temporelles valides : {len(df_filtre)}")

    # Identifier toutes les fenêtres temporelles uniques
    fenetres_uniques = sorted(df_filtre['fenetre_temporelle'].unique())
    print(f"✅ Fenêtres temporelles trouvées : {len(fenetres_uniques)}")
    print(f"Exemples de fenêtres : {fenetres_uniques[:10]}")

    # Debug : afficher toutes les périodes trouvées
    print("\n=== DEBUG : Toutes les périodes trouvées ===")
    for i, periode in enumerate(fenetres_uniques):
        print(f"  {i + 1:2d}. {periode}")

    # OPTIMISATION : Utiliser des opérations vectorisées pandas
    print("\n=== Création de la structure de données optimisée ===")

    # Créer un DataFrame vide avec pt_id comme index
    patients_uniques = df_filtre['pt_id'].unique()
    print(f"Nombre total de patients à traiter : {len(patients_uniques)}")

    # Créer un dictionnaire pour stocker les données par patient
    resultats_dict = {}

    # Identifier la colonne de délai
    delai_col = None
    for col in df_fusionne.columns:
        if 'delai' in col.lower() and 'premiere' in col.lower():
            delai_col = col
            break

    print(f"Colonne de délai identifiée : {delai_col}")

    # Debug : afficher toutes les colonnes contenant "delai"
    colonnes_delai = [col for col in df_fusionne.columns if 'delai' in col.lower()]
    print(f"Toutes les colonnes contenant 'delai' : {colonnes_delai}")

    # Pour chaque patient, utiliser des opérations vectorisées
    for i, pt_id in enumerate(patients_uniques):
        if i % 100 == 0:
            print(f"  Traitement patient {i + 1}/{len(patients_uniques)} : {pt_id}")

        # Filtrer les données pour ce patient
        df_patient = df_filtre[df_filtre['pt_id'] == pt_id]

        # Initialiser la ligne du patient
        ligne_patient = {'pt_id': pt_id}

        # Pour chaque toxicité et période, utiliser des opérations vectorisées
        for tox in colonnes_tox:
            for fenetre in fenetres_uniques:
                # Filtrer les données pour cette combinaison
                mask = (df_patient['fenetre_temporelle'] == fenetre)
                df_combinaison = df_patient[mask]

                if len(df_combinaison) > 0:
                    # Créer les noms de colonnes
                    nom_valeur = f"{tox}_{fenetre}_valeur"
                    nom_delai = f"{tox}_{fenetre}_delai"
                    nom_date = f"{tox}_{fenetre}_date"

                    # Collecter toutes les valeurs pour cette combinaison
                    valeurs = []
                    delais = []
                    dates = []

                    for _, row in df_combinaison.iterrows():
                        # Collecter la valeur de toxicité - nettoyer les décimales inutiles
                        if pd.notna(row[tox]):
                            valeur = row[tox]
                            # Convertir en entier si c'est un nombre entier
                            if isinstance(valeur, (int, float)) and valeur == int(valeur):
                                valeur = int(valeur)
                            valeurs.append(str(valeur))

                        # Collecter le délai - nettoyer les décimales inutiles
                        if delai_col and pd.notna(row[delai_col]):
                            delai = row[delai_col]
                            # Convertir en entier si c'est un nombre entier
                            if isinstance(delai, (int, float)) and delai == int(delai):
                                delai = int(delai)
                            delais.append(str(delai))

                        # Collecter la date - garder seulement la date sans l'heure
                        if pd.notna(row['date_event']):
                            date_event = row['date_event']
                            # Si c'est un datetime, extraire seulement la date
                            if hasattr(date_event, 'date'):
                                date_str = date_event.date().strftime('%Y-%m-%d')
                            else:
                                # Si c'est déjà une string, essayer de parser et reformater
                                try:
                                    from datetime import datetime
                                    if isinstance(date_event, str):
                                        # Parser la date et reformater
                                        parsed_date = datetime.strptime(date_event, '%Y-%m-%d %H:%M:%S')
                                        date_str = parsed_date.strftime('%Y-%m-%d')
                                    else:
                                        date_str = str(date_event)
                                except:
                                    date_str = str(date_event)
                            dates.append(date_str)

                    # Debug pour un patient spécifique
                    if pt_id == '32040000000000014023' and tox == 'ecog_aigu' and fenetre == 'AvantRT_39-1j':
                        print(f"DEBUG patient {pt_id}, tox {tox}, fenetre {fenetre}:")
                        print(f"  - Nombre de lignes trouvées: {len(df_combinaison)}")
                        print(f"  - Valeurs: {valeurs}")
                        print(f"  - Delais: {delais}")
                        print(f"  - Dates: {dates}")
                        print(f"  - Colonne delai_col: {delai_col}")
                        for idx, row in df_combinaison.iterrows():
                            print(
                                f"    Ligne {idx}: tox={row[tox]}, delai={row.get(delai_col, 'N/A')}, date={row.get('date_event', 'N/A')}")

                    # Concaténer les valeurs avec ";"
                    if valeurs:
                        ligne_patient[nom_valeur] = ";".join(valeurs)

                    if delais:
                        ligne_patient[nom_delai] = ";".join(delais)

                    if dates:
                        ligne_patient[nom_date] = ";".join(dates)

        # Ajouter la ligne du patient au dictionnaire
        resultats_dict[pt_id] = ligne_patient

    print(f"✅ Structure de données créée pour {len(resultats_dict)} patients")

    # Convertir en DataFrame
    print("Conversion en DataFrame...")
    resultats = list(resultats_dict.values())
    df_resultat = pd.DataFrame(resultats)

    print(f"✅ DataFrame créé : {len(df_resultat)} patients, {len(df_resultat.columns)} colonnes")

    # Sauvegarder le fichier
    print(f"Sauvegarde du fichier {filename_output}...")
    save_large_excel(df_resultat, filename_output)
    print(f"✅ Fichier {filename_output} sauvegardé")

    return df_resultat


# ============================================================================
# FONCTION : creer_toxicites_agregees_sans_cumuls_ultra_optimisee
# OBJECTIF : Version ultra-optimisée avec opérations pandas 100% vectorisées
# ENTRÉES :
#   - filename_tox : Chemin vers le fichier de toxicité
#   - filename_traitement : Chemin vers le fichier de traitement
#   - filename_output : Nom du fichier de sortie (défaut: "toxicites_agregees_sans_cumuls.xlsx")
# SORTIE : DataFrame agrégé ultra-optimisé et fichier Excel créé
# ============================================================================
def creer_toxicites_agregees_sans_cumuls_ultra_optimisee(filename_tox, filename_traitement,
                                                         filename_output="toxicites_agregees_sans_cumuls.xlsx"):
    """
    Version ULTRA-OPTIMISÉE avec opérations pandas 100% vectorisées.
    Utilise des techniques avancées de vectorisation pour des performances maximales.
    """
    print(f"\n=== Création toxicités agrégées (VERSION ULTRA-OPTIMISÉE) ===")

    # Charger les données
    print("Chargement des données...")
    df_tox = lire_excel_accelere(filename_tox)
    print(f"✅ {filename_tox} chargé : {len(df_tox)} lignes")

    df_traitement = lire_excel_accelere(filename_traitement)
    print(f"✅ {filename_traitement} chargé : {len(df_traitement)} lignes")

    # Fusionner toxicité et traitement
    df_fusionne = fusionner_toxicites_fractions_numba_simple(df_tox, df_traitement)
    print(f"✅ Fusion terminée : {len(df_fusionne)} lignes")

    # OPTIMISATION 1: Calcul vectorisé des fenêtres temporelles
    print("Calcul ULTRA-VECTORISÉ des fenêtres temporelles...")
    start_time = time.time()

    # Identifier les colonnes de dates
    premiere_col = None
    derniere_col = None
    for col in df_fusionne.columns:
        if 'PremiereFractionChamp' in col:
            premiere_col = col
        elif 'DerniereFractionChamp' in col:
            derniere_col = col

    if premiere_col is None or derniere_col is None:
        print("❌ Colonnes de dates non trouvées")
        return None

    # Calcul vectorisé des délais
    df_fusionne['delai_premiere'] = (df_fusionne['date_event'] - df_fusionne[premiere_col]).dt.days
    df_fusionne['delai_derniere'] = (df_fusionne['date_event'] - df_fusionne[derniere_col]).dt.days

    # OPTIMISATION 2: Calcul vectorisé des fenêtres temporelles sans apply
    conditions = []
    choices = []

    # Avant RT
    mask_avant = df_fusionne['date_event'] < df_fusionne[premiere_col]
    delai_premiere = df_fusionne['delai_premiere']

    conditions.extend([
        mask_avant & (delai_premiere < -180),
        mask_avant & (delai_premiere >= -180) & (delai_premiere < -160),
        mask_avant & (delai_premiere >= -160) & (delai_premiere < -130),
        mask_avant & (delai_premiere >= -130) & (delai_premiere < -100),
        mask_avant & (delai_premiere >= -100) & (delai_premiere < -70),
        mask_avant & (delai_premiere >= -70) & (delai_premiere < -40),
        mask_avant & (delai_premiere >= -40) & (delai_premiere < 0)
    ])
    choices.extend([
        "AvantRT_<180j", "AvantRT_180-160j", "AvantRT_159-130j", "AvantRT_129-100j",
        "AvantRT_99-70j", "AvantRT_69-40j", "AvantRT_39-1j"
    ])

    # Pendant/Aigu
    mask_pendant = (df_fusionne['date_event'] >= df_fusionne[premiere_col]) & (delai_premiere <= 90)
    semaine = (delai_premiere // 7 + 1).astype(str).str.zfill(2)
    df_fusionne.loc[mask_pendant, 'fenetre_temporelle'] = "Aigu_Semaine_" + semaine

    # Après RT/Tardif
    mask_apres = (df_fusionne['date_event'] >= df_fusionne[premiere_col]) & (delai_premiere > 90) & (
                df_fusionne['delai_derniere'] >= 1)
    delai_derniere = df_fusionne['delai_derniere']
    mois = (delai_derniere // 30 + 1)

    # Conditions pour les mois tardifs
    conditions.extend([
        mask_apres & (mois == 1), mask_apres & (mois == 2), mask_apres & (mois == 3), mask_apres & (mois == 4),
        mask_apres & (mois >= 5) & (mois <= 7), mask_apres & (mois >= 8) & (mois <= 10),
        mask_apres & (mois >= 11) & (mois <= 13), mask_apres & (mois >= 14) & (mois <= 16),
        mask_apres & (mois >= 17) & (mois <= 19), mask_apres & (mois >= 20) & (mois <= 22),
        mask_apres & (mois >= 23) & (mois <= 26), mask_apres & (mois >= 27) & (mois <= 33),
        mask_apres & (mois >= 34) & (mois <= 38), mask_apres & (mois >= 39) & (mois <= 45),
        mask_apres & (mois >= 46) & (mois <= 51), mask_apres & (mois >= 52) & (mois <= 58),
        mask_apres & (mois >= 59) & (mois <= 62), mask_apres & (mois > 62)
    ])
    choices.extend([
        "Tardif_Mois_01", "Tardif_Mois_02", "Tardif_Mois_03", "Tardif_Mois_04",
        "Tardif_Mois_05-07", "Tardif_Mois_08-10", "Tardif_Mois_11-13", "Tardif_Mois_14-16",
        "Tardif_Mois_17-19", "Tardif_Mois_20-22", "Tardif_Mois_23-26", "Tardif_Mois_27-33",
        "Tardif_Mois_34-38", "Tardif_Mois_39-45", "Tardif_Mois_46-51", "Tardif_Mois_52-58",
        "Tardif_Mois_59-62", "Tardif_Mois_>62"
    ])

    # Appliquer toutes les conditions vectorisées
    df_fusionne['fenetre_temporelle'] = np.select(conditions, choices, default=None)

    fenetre_time = time.time() - start_time
    print(f"✅ Fenêtres temporelles calculées en {fenetre_time:.2f} secondes")

    # Filtrer les lignes valides
    df_filtre = df_fusionne[df_fusionne['fenetre_temporelle'].notna()].copy()
    print(f"✅ Lignes avec fenêtres valides : {len(df_filtre)}")

    # Identifier les colonnes de toxicité de manière DYNAMIQUE depuis le fichier tox_clean
    print("\n=== IDENTIFICATION DYNAMIQUE DES COLONNES DE TOXICITÉ (VERSION ULTRA-OPTIMISÉE) ===")
    print(f"Toutes les colonnes disponibles dans le fichier fusionné :")
    for i, col in enumerate(df_fusionne.columns, 1):
        print(f"  {i:2d}. {col}")

    # Colonnes à exclure (techniques et métadonnées)
    colonnes_exclues = ['pt_id', 'date_event', 'fenetre_temporelle', 'delai_premiere', 'delai_derniere', premiere_col,
                        derniere_col]

    # Colonnes spécifiques pour le traitement des périodes temporelles (NON toxicités)
    colonnes_traitement_temporel = [
        'PremiereFractionChamp_x', 'DerniereFractionChamp_x', 'PremiereFractionChamp_y', 'DerniereFractionChamp_y',
        'Delai', 'FenetreTemporelle', 'Semaine', 'Periode', 'TypeToxicite'
    ]

    # Ajouter les colonnes de traitement temporel qui existent
    for col in colonnes_traitement_temporel:
        if col in df_fusionne.columns:
            colonnes_exclues.append(col)

    print(f"\nColonnes exclues (techniques) : {colonnes_exclues}")
    print(
        f"Colonnes de traitement temporel exclues : {[col for col in colonnes_traitement_temporel if col in df_fusionne.columns]}")

    # Identifier les colonnes de toxicité de manière DYNAMIQUE
    colonnes_tox = []
    colonnes_exclues_par_mot_cle = []

    for col in df_fusionne.columns:
        if col not in colonnes_exclues:
            # Exclure les colonnes qui contiennent min, max, cumul, moyenne, ecart
            if not any(mot in col.lower() for mot in ['min', 'max', 'cumul', 'moyenne', 'ecart', 'nombre']):
                colonnes_tox.append(col)
            else:
                colonnes_exclues_par_mot_cle.append(col)

    print(f"\nColonnes exclues par mot-clé (min/max/cumul/etc.) : {colonnes_exclues_par_mot_cle}")
    print(f"\n✅ Colonnes de toxicité identifiées DYNAMIQUEMENT : {len(colonnes_tox)}")
    print("Liste complète des toxicités trouvées :")
    for i, tox in enumerate(colonnes_tox, 1):
        print(f"  {i:2d}. {tox}")

    # Afficher toutes les périodes temporelles identifiées APRÈS la reconnaissance des toxicités
    print("\n=== PÉRIODES TEMPORELLES IDENTIFIÉES (VERSION ULTRA-OPTIMISÉE) ===")
    fenetres_possibles = [
        "AvantRT_<180j", "AvantRT_180-160j", "AvantRT_159-130j", "AvantRT_129-100j",
        "AvantRT_99-70j", "AvantRT_69-40j", "AvantRT_39-1j"
    ]

    # Ajouter les fenêtres aiguës (semaines 1-13)
    for semaine in range(1, 14):
        fenetres_possibles.append(f"Aigu_Semaine_{str(semaine).zfill(2)}")

    # Ajouter les fenêtres tardives
    fenetres_tardives = [
        "Tardif_Mois_01", "Tardif_Mois_02", "Tardif_Mois_03", "Tardif_Mois_04",
        "Tardif_Mois_05-07", "Tardif_Mois_08-10", "Tardif_Mois_11-13", "Tardif_Mois_14-16",
        "Tardif_Mois_17-19", "Tardif_Mois_20-22", "Tardif_Mois_23-26", "Tardif_Mois_27-33",
        "Tardif_Mois_34-38", "Tardif_Mois_39-45", "Tardif_Mois_46-51", "Tardif_Mois_52-58",
        "Tardif_Mois_59-62", "Tardif_Mois_>62"
    ]
    fenetres_possibles.extend(fenetres_tardives)

    print(f"✅ Périodes temporelles identifiées : {len(fenetres_possibles)}")
    print("Liste complète des périodes temporelles :")
    for i, periode in enumerate(fenetres_possibles, 1):
        print(f"  {i:2d}. {periode}")

    # Obtenir UNIQUEMENT les fenêtres temporelles qui existent dans les données
    fenetres_uniques = sorted(df_filtre['fenetre_temporelle'].unique())

    print(f"\n✅ {len(colonnes_tox)} toxicités, {len(fenetres_uniques)} fenêtres (dynamiques)")

    # OPTIMISATION 3: Agrégation vectorisée par groupby
    print("\n=== Agrégation VECTORISÉE par groupby ===")
    start_time = time.time()

    # Créer les colonnes de résultat UNIQUEMENT pour les combinaisons qui existent
    colonnes_resultat = ['pt_id']
    for tox in colonnes_tox:
        for fenetre in fenetres_uniques:
            colonnes_resultat.extend([f"{tox}_{fenetre}_valeur", f"{tox}_{fenetre}_delai", f"{tox}_{fenetre}_date"])

    # Créer DataFrame résultat
    patients_uniques = df_fusionne['pt_id'].unique()  # Utiliser df_fusionne pour avoir TOUS les patients
    df_resultat = pd.DataFrame(index=range(len(patients_uniques)), columns=colonnes_resultat)
    df_resultat['pt_id'] = patients_uniques

    # OPTIMISATION 4: Traitement par groupby au lieu de boucles
    for tox in colonnes_tox:
        print(f"  Traitement toxicité: {tox}")

        for fenetre in fenetres_uniques:
            # Filtrer les données pour cette combinaison
            mask = (df_filtre['fenetre_temporelle'] == fenetre)
            df_combinaison = df_filtre[mask]

            if len(df_combinaison) > 0:
                # Groupby par patient pour cette combinaison
                grouped = df_combinaison.groupby('pt_id').agg({
                    tox: lambda x: ';'.join(
                        [str(int(val) if isinstance(val, (int, float)) and val == int(val) else val) for val in
                         x.dropna()]),
                    'delai_premiere': lambda x: ';'.join(
                        [str(int(val) if isinstance(val, (int, float)) and val == int(val) else val) for val in
                         x.dropna()]),
                    'date_event': lambda x: ';'.join(
                        [val.date().strftime('%Y-%m-%d') if hasattr(val, 'date') else str(val) for val in x.dropna()])
                }).reset_index()

                # Assigner les résultats
                for _, row in grouped.iterrows():
                    pt_id = row['pt_id']
                    row_idx = df_resultat[df_resultat['pt_id'] == pt_id].index[0]

                    if pd.notna(row[tox]):
                        df_resultat.loc[row_idx, f"{tox}_{fenetre}_valeur"] = row[tox]
                    if pd.notna(row['delai_premiere']):
                        df_resultat.loc[row_idx, f"{tox}_{fenetre}_delai"] = row['delai_premiere']
                    if pd.notna(row['date_event']):
                        df_resultat.loc[row_idx, f"{tox}_{fenetre}_date"] = row['date_event']

    aggregation_time = time.time() - start_time
    print(f"✅ Agrégation terminée en {aggregation_time:.2f} secondes")

    print(f"✅ DataFrame créé : {len(df_resultat)} patients, {len(df_resultat.columns)} colonnes")

    # Sauvegarder
    print(f"Sauvegarde du fichier {filename_output}...")
    save_large_excel(df_resultat, filename_output)
    print(f"✅ Fichier {filename_output} sauvegardé")

    total_time = time.time() - start_time
    print(f"⏱️ Temps total d'exécution : {total_time:.2f} secondes")

    return df_resultat
