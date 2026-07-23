# ============================================================================
# MODULE : sql_io.py
# DESCRIPTION : Module utilitaire pour la gestion des données, sauvegarde Excel,
#              exécution SQL et accélération GPU
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


# ============================================================================
# FONCTION : save_large_excel
# OBJECTIF : Sauvegarde un DataFrame en plusieurs fichiers Excel si nécessaire
# ENTRÉES :
#   - df : DataFrame pandas à sauvegarder
#   - filename_base : Nom de base du fichier Excel
# SORTIE : Fichiers Excel créés (un seul ou plusieurs parties)
# ============================================================================
def save_large_excel(df, filename_base):
    """
    Sauvegarde un DataFrame en plusieurs fichiers Excel si le nombre de colonnes dépasse la limite Excel (16 384).
    Divise automatiquement le fichier en plusieurs parties si nécessaire pour éviter les erreurs Excel.
    """
    MAX_EXCEL_COLS = 16384  # Limite maximale de colonnes pour Excel
    df_clean = df.copy()

    # Nettoyage des caractères illégaux pour Excel
    for col in df_clean.select_dtypes(include=["object"]):
        df_clean[col] = df_clean[col].map(clean_excel_illegal_chars)

    n_cols = df_clean.shape[1]
    
    # Si le fichier est assez petit, sauvegarde directe
    if n_cols <= MAX_EXCEL_COLS:
        writer = pd.ExcelWriter(filename_base, engine='xlsxwriter')
        df_clean.to_excel(writer, index=False, sheet_name="Data")
        writer.close()
        print(f"✅ Fichier sauvegardé : {filename_base} ({df_clean.shape[0]} lignes × {n_cols} colonnes)")
    else:
        # Division en plusieurs fichiers si trop de colonnes
        num_files = (n_cols // MAX_EXCEL_COLS) + 1
        print(f"⚠️  Le fichier est trop grand ({n_cols} colonnes). Division en {num_files} parties...")

        for i in range(num_files):
            start_col = i * MAX_EXCEL_COLS
            end_col = min((i + 1) * MAX_EXCEL_COLS, n_cols)

            # Créer le chunk avec les colonnes sélectionnées
            df_chunk = df_clean.iloc[:, start_col:end_col].copy()

            # Ajouter pt_id au début si il n'est pas déjà dans le chunk
            if 'pt_id' in df_clean.columns and 'pt_id' not in df_chunk.columns:
                df_chunk = pd.concat([df_clean[['pt_id']], df_chunk], axis=1)

            filename = filename_base.replace(".xlsx", f"_part{i + 1}.xlsx")
            writer = pd.ExcelWriter(filename, engine='xlsxwriter')
            df_chunk.to_excel(writer, index=False, sheet_name="Data")
            writer.close()
            print(f"✅ Partie {i + 1} sauvegardée : {filename} ({df_chunk.shape[1]} colonnes)")


# ============================================================================
# FONCTION : save_data_excel_by_multiple_requests
# OBJECTIF : Crée un fichier Excel séparé pour chaque type de requête
# ENTRÉES :
#   - mapped : DataFrame contenant les données des patients
#   - requete_cols : Liste des colonnes contenant les types de requêtes
#   - filename_prefix : Préfixe pour les noms de fichiers (défaut: "map_")
# SORTIE : Fichiers Excel créés (un par type de requête)
# ============================================================================
def save_data_excel_by_multiple_requests(mapped, requete_cols, filename_prefix="map_"):
    """
    Enregistre un fichier Excel par type de requête (déterminée par les colonnes `requete_cols`).
    Utilise `pt_id` comme identifiant unique du patient.
    Crée également un fichier "autre.xlsx" pour les patients sans requête.
    """
    # Affichage des valeurs uniques dans chaque colonne de requête
    for col in requete_cols:
        uniques = mapped[col].dropna().astype(str).str.strip().str.upper().unique()
        print(f"Valeurs uniques dans {col} (normalisées) : {uniques}")

    # Dictionnaire pour regrouper les patients par type de requête
    requete_to_patients = defaultdict(list)
    patients_avec_requete = set()

    # Parcours de chaque ligne pour identifier les requêtes
    for idx, row in mapped.iterrows():
        requetes_patient = set()
        for col in requete_cols:
            if col in row and pd.notna(row[col]) and str(row[col]).strip() != "":
                requete = str(row[col]).strip().upper()
                requete_to_patients[requete].append(row)
                requetes_patient.add(requete)
        if requetes_patient and 'pt_id' in row:
            patients_avec_requete.add(row['pt_id'])

    print("==============================")
    print(f"Nombre total de requêtes trouvées : {len(requete_to_patients)}")
    print("------------------------------")

    # Création d'un fichier Excel pour chaque type de requête
    for requete, patients in requete_to_patients.items():
        df_patients = pd.DataFrame(patients)
        if 'pt_id' in df_patients.columns:
            df_patients = df_patients.drop_duplicates(subset=["pt_id"])
        nom_fichier = f"{filename_prefix}{requete.replace('/', '_').replace(' ', '_')}.xlsx"
        save_large_excel(df_patients, nom_fichier)

    # Création du fichier pour les patients sans aucune requête
    if 'pt_id' in mapped.columns:
        autres = mapped[~mapped['pt_id'].isin(patients_avec_requete)]
        if not autres.empty:
            save_large_excel(autres, "autre.xlsx")
            print(f"Fichier créé : autre.xlsx  |  Nombre de patients : {len(autres)} (sans aucune requête)")

    # Calcul et affichage du nombre total de patients uniques
    all_patients_list = [pd.DataFrame(p) for p in requete_to_patients.values() if len(p) > 0]
    if all_patients_list:
        all_patients = pd.concat(all_patients_list)
        if 'pt_id' in all_patients.columns:
            nb_total_uniques = all_patients.drop_duplicates(subset=["pt_id"]).shape[0]
            print("------------------------------")
            print(f"Nombre total de patients uniques (tous fichiers confondus) : {nb_total_uniques}")
    else:
        print("Aucun patient trouvé dans les requêtes, aucun total unique à afficher.")
    print("==============================")


# ============================================================================
# SECTION : DÉTECTION GPU ET ACCÉLÉRATION
# OBJECTIF : Optimisation des performances selon le matériel disponible
# ============================================================================

# ============================================================================
# FONCTION : detecter_gpu_systeme
# OBJECTIF : Détecte le type d'accélération disponible sur le système
# ENTRÉES : Aucune
# SORTIE : String indiquant le type d'accélération ("numba", "cudf", "cpu")
# ============================================================================
def detecter_gpu_systeme():
    """
    Détection simplifiée - utilise Numba sur Mac, CuDF sur Windows avec GPU NVIDIA
    Retourne le type d'accélération disponible pour optimiser les performances.
    """
    systeme = platform.system()

    if systeme == "Darwin":  # macOS
        try:
            import numba
            print("🍎 Mac détecté - Utilisation de Numba JIT pour accélération")
            return "numba"
        except ImportError:
            print("❌ Numba non installé sur Mac")
            return "cpu"

    elif systeme == "Windows":
        try:
            import cudf
            print("🟢 GPU NVIDIA CuDF détecté")
            return "cudf"
        except ImportError:
            try:
                import numba
                print("⚡ Numba JIT détecté")
                return "numba"
            except ImportError:
                pass

    print("💻 CPU uniquement")
    return "cpu"


# ============================================================================
# FONCTION : installer_dependances_gpu
# OBJECTIF : Installe automatiquement les dépendances pour l'accélération GPU
# ENTRÉES : Aucune
# SORTIE : Message de succès ou d'erreur
# ============================================================================
def installer_dependances_gpu():
    """
    Installation automatique de Numba pour l'accélération JIT
    Utilise pip pour installer la bibliothèque manquante.
    """
    print("📦 Installation de Numba pour accélération...")
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "numba"], check=True)
        print("✅ Numba installé avec succès")
    except Exception as e:
        print(f"❌ Échec installation Numba: {e}")


# ============================================================================
# FONCTION : lire_excel_accelere
# OBJECTIF : Lecture optimisée des fichiers Excel avec mesure du temps
# ENTRÉES :
#   - filename : Chemin vers le fichier Excel
#   - engine : Moteur de lecture Excel (défaut: 'openpyxl')
# SORTIE : DataFrame pandas ou DataFrame vide en cas d'erreur
# ============================================================================
def lire_excel_accelere(filename, engine='openpyxl'):
    """
    Lecture accélérée des fichiers Excel avec mesure des performances
    Affiche le temps de lecture et le nombre de lignes lues.
    """
    print(f"📖 Lecture accélérée de {filename}...")
    start_time = time.time()

    try:
        # Lecture avec optimisations
        df = pd.read_excel(filename, engine=engine)
        read_time = time.time() - start_time
        print(f"✅ Fichier lu en {read_time:.3f} secondes - {len(df)} lignes")
        return df
    except Exception as e:
        print(f"❌ Erreur lecture {filename}: {e}")
        return pd.DataFrame()


# ============================================================================
# FONCTION : clean_excel_illegal_chars
# OBJECTIF : Nettoie les caractères illégaux pour Excel
# ENTRÉES :
#   - val : Valeur à nettoyer (string ou autre type)
# SORTIE : Valeur nettoyée
# ============================================================================
def clean_excel_illegal_chars(val):
    """
    Supprime les caractères de contrôle illégaux pour Excel
    Utilise une expression régulière pour identifier et supprimer ces caractères.
    """
    if isinstance(val, str):
        ILLEGAL_CHARACTERS_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F]")
        return ILLEGAL_CHARACTERS_RE.sub("", val)
    return val


# ============================================================================
# FONCTION : save_data_excel_safe
# OBJECTIF : Sauvegarde sécurisée en Excel avec vérification de taille
# ENTRÉES :
#   - df : DataFrame pandas à sauvegarder
#   - filename : Nom du fichier de sortie
# SORTIE : Fichier Excel ou CSV selon la taille
# ============================================================================
def save_data_excel_safe(df, filename):
    """
    Sauvegarde sécurisée qui vérifie la taille du fichier
    Si le fichier est trop volumineux pour Excel, sauvegarde automatiquement en CSV.
    """
    df_clean = df.copy()
    
    # Nettoyage des caractères illégaux
    for col in df_clean.select_dtypes(["object"]):
        df_clean[col] = df_clean[col].map(clean_excel_illegal_chars)
    
    # Vérifier si le fichier sera trop volumineux pour Excel
    if len(df_clean.columns) > 16000 or len(df_clean) > 1000000:
        print(f"⚠️ Fichier trop volumineux pour Excel ({len(df_clean)} lignes, {len(df_clean.columns)} colonnes)")
        print(f"💾 Sauvegarde en CSV : {filename.replace('.xlsx', '.csv')}")
        df_clean.to_csv(filename.replace('.xlsx', '.csv'), index=False)
    else:
        df_clean.to_excel(filename, index=False)
        print(f"✅ Données sauvegardées dans {filename}")


# ============================================================================
# FONCTION : save_data_excel
# OBJECTIF : Sauvegarde simple en Excel sans vérification de taille
# ENTRÉES :
#   - df : DataFrame pandas à sauvegarder
#   - filename : Nom du fichier de sortie
# SORTIE : Fichier Excel créé
# ============================================================================
def save_data_excel(df, filename):
    """
    Sauvegarde directement en XLSX sans vérification de taille
    Version simple pour les fichiers de taille modérée.
    """
    df_clean = df.copy()
    
    # Nettoyage des caractères illégaux
    for col in df_clean.select_dtypes(["object"]):
        df_clean[col] = df_clean[col].map(clean_excel_illegal_chars)

    df_clean.to_excel(filename, index=False)
    print(f"✅ Données sauvegardées dans {filename}")


# ============================================================================
# FONCTION : requete_sql
# OBJECTIF : Exécute un script SQL et sauvegarde les résultats
# ENTRÉES :
#   - chemin_sql : Chemin vers le fichier SQL
#   - connexion : Connexion à la base de données
#   - out_path : Chemin de sortie pour les résultats
#   - encoding : Encodage du fichier SQL (défaut: "utf-8")
#   - multi_sheet : Si True, crée plusieurs feuilles Excel (défaut: False)
#   - to_csv : Si True, sauvegarde en CSV (défaut: False)
# SORTIE : DataFrame(s) des résultats ou None
# ============================================================================
def requete_sql(chemin_sql, connexion, out_path, encoding="utf-8", multi_sheet=False, to_csv=False):
    """
    Exécute un script SQL complet, sauvegarde le(s) DataFrame(s) du/des SELECT dans un fichier Excel ou CSV.
    Si multi_sheet=True, chaque jeu de résultats est une feuille Excel (non supporté en CSV).
    Si to_csv=True, sauvegarde en CSV (seulement le premier SELECT).
    """
    t0 = time.time()
    
    # Lecture du fichier SQL
    with open(chemin_sql, "r", encoding=encoding) as f:
        sql_script = f.read()
    
    # Supprimer le BOM s'il existe
    if sql_script.startswith('\ufeff'):
        sql_script = sql_script.replace('\ufeff', '', 1)
    
    # Supprimer tous les GO (en début ou fin de ligne)
    import re
    sql_script = re.sub(r'(?im)^\\s*GO\\s*$', '', sql_script)
    
    # Exécution de la requête SQL
    cursor = connexion.cursor()
    results = []
    sheet_names = []
    idx = 1
    
    while True:
        cursor.execute(sql_script) if idx == 1 else None
        if cursor.description is not None:
            columns = [col[0] for col in cursor.description]
            rows = cursor.fetchall()
            df = pd.DataFrame.from_records(rows, columns=columns)
            results.append(df)
            sheet_names.append(f"Feuille{idx}")
        if not cursor.nextset():
            break
        idx += 1
    
    cursor.close()
    t1 = time.time()
    print(f"⏱️ Temps d'exécution SQL : {t1-t0:.2f} secondes")
    
    # Sauvegarde des résultats selon le format demandé
    if results:
        if to_csv:
            results[0].to_csv(out_path, index=False)
            print(f"✅ Résultat sauvegardé en CSV dans {out_path}")
        elif multi_sheet and len(results) > 1:
            with pd.ExcelWriter(out_path) as writer:
                for df, name in zip(results, sheet_names):
                    df.to_excel(writer, sheet_name=name, index=False)
            print(f"✅ Résultats multiples sauvegardés dans {out_path} ({len(results)} feuilles)")
        else:
            save_data_excel(results[0], out_path)
            print(f"✅ Résultat sauvegardé dans {out_path}")
        return results if multi_sheet else results[0]
    else:
        print(f"❌ Aucun résultat à sauvegarder pour {out_path}")
        return None


# ============================================================================
# FONCTION : convert_csv_to_xlsx
# OBJECTIF : Convertit un gros fichier CSV en XLSX par morceaux
# ENTRÉES :
#   - csv_path : Chemin vers le fichier CSV source
#   - xlsx_path : Chemin vers le fichier Excel de destination
#   - chunksize : Taille des morceaux pour la lecture (défaut: 50000)
# SORTIE : Fichier Excel créé
# ============================================================================
def convert_csv_to_xlsx(csv_path, xlsx_path, chunksize=50000):
    """
    Convertit un gros CSV en XLSX par morceaux, en limitant la RAM.
    Écrit tous les chunks dans la même feuille Excel.
    Utilise le garbage collector pour libérer la mémoire.
    """
    print(f"Conversion du CSV {csv_path} vers {xlsx_path} ...")
    writer = pd.ExcelWriter(xlsx_path, engine='xlsxwriter')
    total_rows = 0
    n_cols = 0

    # Lecture et écriture par morceaux pour économiser la RAM
    for i, chunk in enumerate(pd.read_csv(csv_path, chunksize=chunksize, low_memory=False)):
        # Calcul de la position de départ pour écrire ce chunk
        startrow = total_rows
        chunk.to_excel(writer, index=False, header=(i == 0), startrow=startrow)
        total_rows += len(chunk)
        n_cols = len(chunk.columns)
        print(f"  - {total_rows} lignes écrites...")
        
        # Libération de la mémoire
        del chunk
        gc.collect()

    writer.close()
    print(f"✅ Conversion terminée : {xlsx_path} ({total_rows} lignes) ({n_cols} colonnes)")


# ============================================================================
# FONCTION : add_columns
# OBJECTIF : Ajouter des colonnes à un DataFrame à une position précise
# ENTRÉES :
#   - data : DataFrame à modifier
#   - columns : liste des noms de colonnes à ajouter
# SORTIE : DataFrame modifié avec les nouvelles colonnes
# ============================================================================
def add_columns(data, columns):
    """
    Ajoute les colonnes spécifiées juste après 'DiagnosisCode' et avant 'laterality_desc' si possible.
    Si une colonne existe déjà, elle est ignorée et aucune valeur n'est écrasée.
    """
    # On prépare la liste des colonnes finales
    cols = list(data.columns)
    try:
        idx_diag = cols.index('DiagnosisCode')
    except ValueError:
        idx_diag = len(cols) - 1  # Si pas trouvé, on ajoute à la fin

    # On ajoute les colonnes si elles n'existent pas déjà
    for col in columns:
        if col not in data.columns:
            # On insère la colonne à la bonne position
            insert_at = idx_diag + 1
            cols.insert(insert_at, col)
            data[col] = None
            idx_diag += 1  # Pour que les suivantes soient insérées juste après

    # On réorganise les colonnes pour respecter l'ordre souhaité
    data = data.reindex(columns=cols)
    return data