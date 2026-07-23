# -*- coding: utf-8 -*-
"""Application Streamlit ARIA ODM Builder — structure d'interface uniquement.

Les fonctions de lecture, nettoyage, mapping, cohorte, temporalité, qualité,
export et profil sont rangées dans le dossier utils/.
"""

import io
import re
from pathlib import Path
from time import perf_counter
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st

from utils.clean import *
from utils.cohort import *
from utils.display import render_header, setup_page
from utils.export import *
from utils.load import *
from utils.mapping import *
from utils.profile import *
from utils.quality import *
from utils.temporal import *
from utils.text import *

try:
    from utils.sql_extract import run_extraction_bundle, test_connection
except Exception as _sql_extract_import_error:
    run_extraction_bundle = None
    test_connection = None
    SQL_EXTRACT_IMPORT_ERROR = _sql_extract_import_error
else:
    SQL_EXTRACT_IMPORT_ERROR = None


class LocalUploadedFile(io.BytesIO):
    """Petit wrapper pour réutiliser les fonctions d'import existantes avec un fichier local.

    Important : ``name`` doit contenir le chemin complet et pas seulement le nom
    du fichier. Certaines couches de lecture/cache Streamlit peuvent réutiliser
    ``uploaded_file.name`` comme chemin ; avec seulement ``traitement_patient.csv``,
    l'app cherchait le fichier à la racine du projet au lieu de ``inputs/`` ou
    ``outputs/``.
    """

    def __init__(self, path: Path):
        self.path = Path(path).resolve()
        super().__init__(self.path.read_bytes())
        self.name = str(self.path)
        self.display_name = self.path.name
        self.size = self.path.stat().st_size


def _resolve_data_dir(data_dir: str) -> Path:
    """Résout le dossier d'entrée/sortie de façon robuste.

    Si Streamlit est lancé depuis un autre dossier, `Path("inputs")` ou
    `Path("outputs")` peut ne pas pointer vers le dossier placé à côté de
    `app2.py`. On teste donc plusieurs emplacements sans modifier le workflow
    existant.
    """
    raw = Path(str(data_dir).strip() or "inputs").expanduser()
    candidates = []
    if raw.is_absolute():
        candidates.append(raw)
    else:
        app_dir = Path(__file__).resolve().parent
        candidates.extend([Path.cwd() / raw, app_dir / raw, app_dir.parent / raw, raw])

    for candidate in candidates:
        if candidate.exists() and candidate.is_dir():
            return candidate.resolve()

    # Si le dossier n'existe pas encore, on renvoie l'emplacement le plus logique.
    return candidates[0].resolve() if candidates else raw.resolve()


def _find_output_file(output_dir: str, base_name: str) -> Optional[Path]:
    root = _resolve_data_dir(output_dir)
    for ext in (".csv", ".xlsx", ".zip"):
        p = root / f"{base_name}{ext}"
        if p.exists() and p.is_file():
            return p.resolve()
    return None


def _wrap_output_file(path: Optional[Path]):
    if path is None:
        return None
    try:
        return LocalUploadedFile(path)
    except Exception:
        return None


def _human_size(path: Optional[Path]) -> str:
    if path is None or not path.exists():
        return "—"
    size = path.stat().st_size
    for unit in ["o", "Ko", "Mo", "Go"]:
        if size < 1024 or unit == "Go":
            return f"{size:.1f} {unit}" if unit != "o" else f"{int(size)} {unit}"
        size /= 1024
    return str(path.stat().st_size)


def _mask_secret_value(value: Any, min_len: int = 8, max_len: int = 16) -> str:
    """Masque une valeur de connexion sans modifier la vraie valeur en mémoire."""
    if value is None:
        return ""
    value_str = str(value)
    if value_str == "":
        return ""
    return "•" * max(min_len, min(len(value_str), max_len))


def _init_sql_session_defaults() -> None:
    """Initialise une seule fois les valeurs SQL utilisées par l'onglet Import."""

    db = st.secrets["database"]

    defaults = {
        "aria_sql_driver": db["driver"],
        "aria_sql_server": db["server"],
        "aria_sql_database": db["database"],
        "aria_sql_username": db.get("username", ""),
        "aria_sql_password": db.get("password", ""),
        "aria_sql_reveal_connection": False,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


setup_page()
render_header()

# ============================================================
# APP — CHARGEMENT / ONGLETS
# ============================================================

tab_home, tab_import, tab_build, tab_quality, tab_sources, tab_profile = st.tabs(
    [
        "0. Accueil",
        "1. Import",
        "2. Construction",
        "3. Contrôle qualité",
        "4. Sources",
        "5. Profil",
    ]
)

with st.sidebar:
    st.header("Navigation")
    app_mode = st.radio("Mode d'utilisation", ["Simple", "Expert"], index=1)
    st.caption(
        "Simple = interface courte. Expert = fenêtres temporelles et paramètres avancés."
    )

# Variables d'import. Elles peuvent venir soit des fichiers inputs/, soit du mode manuel.
treatment_file = None
form_file = None
ethos_file = None
mapping_file = None
profile_file = None

with tab_import:
    st.subheader("Import des fichiers")
    st.markdown(
        '<div class="smallnote">Deux modes : lancer l’extraction SQL depuis l’application, ou utiliser les fichiers déjà générés dans <code>inputs/</code>.</div>',
        unsafe_allow_html=True,
    )
    with st.expander("Description des fichiers d’entrée", expanded=False):
        st.markdown("""
            ### `traitement_patient`

            Le fichier `traitement_patient` regroupe les informations liées aux traitements
            de radiothérapie et constitue la base principale de construction de la cohorte.

            Il peut notamment contenir les identifiants patient, les diagnostics CIM10,
            les prescriptions, les informations de fractionnement, les doses délivrées,
            les dates de première et dernière fraction, les techniques de traitement,
            ainsi que les informations machine et plan de traitement.

            ---

            ### `formulaire_patient`

            Le fichier `formulaire_patient` rassemble les données issues des formulaires
            cliniques et du suivi patient, avec une organisation centrée sur les événements datés.

            Ces informations sont ensuite rapprochées de la cohorte traitement afin
            d’enrichir l’export final.

            ---

            ### `ethos_patient`

            Le fichier `ethos_patient` correspond à une extraction spécifique des traitements
            réalisés sur la plateforme ETHOS. Il reste optionnel.
            """)

    import_choice = st.radio(
        "Mode d'import",
        [
            "1) Faire l'extraction SQL ici",
            "2) Extraction déjà faite : utiliser les fichiers inputs/",
        ],
        horizontal=False,
        help="Les deux modes aboutissent aux mêmes fichiers attendus : traitement_patient, formulaire_patient et ethos_patient optionnel.",
    )

    input_dir_value_raw = st.text_input(
        "Dossier des fichiers d'entrée",
        value=st.session_state.get("aria_input_dir", "inputs"),
        help="L'app cherchera automatiquement traitement_patient.csv/.xlsx, formulaire_patient.csv/.xlsx et ethos_patient.csv/.xlsx dans ce dossier. Mets outputs si tu veux garder l'ancien fonctionnement.",
    )
    input_dir_value = str(input_dir_value_raw).strip() or "inputs"
    st.session_state["aria_input_dir"] = input_dir_value

    if import_choice.startswith("1)"):
        st.markdown("### Extraction SQL depuis Streamlit")
        st.caption(
            f"Cette partie est isolée : elle génère uniquement les fichiers cochés dans `{input_dir_value}/`, "
            "puis le reste de l'app continue comme avant."
        )

        _init_sql_session_defaults()

        col_sql_title, col_sql_eye = st.columns([0.82, 0.18])
        with col_sql_title:
            st.markdown("#### Paramètres de connexion")
        with col_sql_eye:
            eye_label = "👁️ Révéler" if not st.session_state["aria_sql_reveal_connection"] else "🙈 Masquer"
            if st.button(
                eye_label,
                key="aria_sql_reveal_button",
                help="Afficher ou masquer les informations de connexion SQL pour le partage d’écran.",
            ):
                st.session_state["aria_sql_reveal_connection"] = not st.session_state["aria_sql_reveal_connection"]
                st.rerun()

        show_sql_conn = bool(st.session_state["aria_sql_reveal_connection"])

        with st.form("sql_extraction_form"):
            col_a, col_b = st.columns(2)
            with col_a:
                if show_sql_conn:
                    sql_driver = st.text_input(
                        "Driver ODBC",
                        value=st.session_state["aria_sql_driver"],
                        key="aria_sql_driver_input",
                    )
                    sql_server = st.text_input(
                        "Serveur SQL",
                        value=st.session_state["aria_sql_server"],
                        key="aria_sql_server_input",
                    )
                    sql_database = st.text_input(
                        "Base de données",
                        value=st.session_state["aria_sql_database"],
                        key="aria_sql_database_input",
                    )
                    st.session_state["aria_sql_driver"] = sql_driver
                    st.session_state["aria_sql_server"] = sql_server
                    st.session_state["aria_sql_database"] = sql_database
                else:
                    st.text_input(
                        "Driver ODBC",
                        value=_mask_secret_value(st.session_state["aria_sql_driver"]),
                        disabled=True,
                        key="aria_sql_driver_masked",
                    )
                    st.text_input(
                        "Serveur SQL",
                        value=_mask_secret_value(st.session_state["aria_sql_server"]),
                        disabled=True,
                        key="aria_sql_server_masked",
                    )
                    st.text_input(
                        "Base de données",
                        value=_mask_secret_value(st.session_state["aria_sql_database"]),
                        disabled=True,
                        key="aria_sql_database_masked",
                    )
                    sql_driver = st.session_state["aria_sql_driver"]
                    sql_server = st.session_state["aria_sql_server"]
                    sql_database = st.session_state["aria_sql_database"]
                    st.caption("Infos masquées pour le partage d’écran. Clique sur 👁️ Révéler pour les modifier.")

                sql_dir = st.text_input("Dossier des scripts SQL", value="sql")
            with col_b:
                trusted_connection = st.checkbox("Authentification Windows", value=True)
                trust_server_certificate = st.checkbox("TrustServerCertificate", value=True)
                write_xlsx = st.checkbox("Générer aussi les fichiers Excel .xlsx", value=True)
                limit_rows_raw = st.number_input(
                    "Limiter à N lignes pour test (0 = aucune limite)",
                    min_value=0,
                    value=0,
                    step=100,
                )

            username = ""
            password = ""
            if not trusted_connection:
                if show_sql_conn:
                    username = st.text_input(
                        "Utilisateur SQL",
                        value=st.session_state.get("aria_sql_username", ""),
                        key="aria_sql_username_input",
                    )
                    password = st.text_input(
                        "Mot de passe SQL",
                        value=st.session_state.get("aria_sql_password", ""),
                        type="password",
                        key="aria_sql_password_input",
                    )
                    st.session_state["aria_sql_username"] = username
                    st.session_state["aria_sql_password"] = password
                else:
                    st.text_input(
                        "Utilisateur SQL",
                        value=_mask_secret_value(st.session_state.get("aria_sql_username", "")),
                        disabled=True,
                        key="aria_sql_username_masked",
                    )
                    st.text_input(
                        "Mot de passe SQL",
                        value=_mask_secret_value(st.session_state.get("aria_sql_password", "")),
                        disabled=True,
                        type="password",
                        key="aria_sql_password_masked",
                    )
                    username = st.session_state.get("aria_sql_username", "")
                    password = st.session_state.get("aria_sql_password", "")

            st.markdown("Fichiers à extraire")
            col_ext_1, col_ext_2, col_ext_3 = st.columns(3)
            with col_ext_1:
                extract_traitement = st.checkbox(
                    "traitement_patient",
                    value=True,
                    help="Script : sql/query_aria__strasbourg.sql",
                )
            with col_ext_2:
                extract_formulaire = st.checkbox(
                    "formulaire_patient",
                    value=True,
                    help="Script : sql/all_patient_formulaire.sql",
                )
            with col_ext_3:
                extract_ethos = st.checkbox(
                    "ethos_patient",
                    value=True,
                    help="Script : sql/all_patient_ethos.sql",
                )

            st.markdown("Scripts attendus dans le dossier SQL :")
            st.code(
                "query_aria__strasbourg.sql      -> traitement_patient\n"
                "all_patient_formulaire.sql     -> formulaire_patient\n"
                "all_patient_ethos.sql          -> ethos_patient",
                language="text",
            )

            col_run_1, col_run_2 = st.columns(2)
            with col_run_1:
                test_sql = st.form_submit_button("Tester la connexion")
            with col_run_2:
                run_sql = st.form_submit_button("Lancer extraction sélectionnée")

        common_sql_kwargs = dict(
            driver=sql_driver,
            server=sql_server,
            database=sql_database,
            trusted_connection=trusted_connection,
            trust_server_certificate=trust_server_certificate,
            username=username,
            password=password,
        )

        selected_extracts = {
            "traitement_patient": bool(extract_traitement),
            "formulaire_patient": bool(extract_formulaire),
            "ethos_patient": bool(extract_ethos),
        }

        if SQL_EXTRACT_IMPORT_ERROR is not None:
            st.error(f"Module d'extraction SQL indisponible : {SQL_EXTRACT_IMPORT_ERROR}")
        elif test_sql:
            try:
                assert test_connection is not None
                st.success(test_connection(**common_sql_kwargs))
            except Exception as exc:
                st.error(f"Connexion SQL impossible : {exc}")
        elif run_sql:
            if not any(selected_extracts.values()):
                st.warning("Coche au moins un fichier à extraire.")
            else:
                try:
                    assert run_extraction_bundle is not None
                    with st.spinner("Extraction SQL en cours..."):
                        extraction_results = run_extraction_bundle(
                            **common_sql_kwargs,
                            sql_dir=sql_dir,
                            output_dir=input_dir_value,
                            write_xlsx=write_xlsx,
                            limit_rows=None if int(limit_rows_raw) == 0 else int(limit_rows_raw),
                            run_traitement=selected_extracts["traitement_patient"],
                            run_formulaire=selected_extracts["formulaire_patient"],
                            run_ethos=selected_extracts["ethos_patient"],
                        )
                    st.session_state["aria_last_sql_extraction_results"] = extraction_results
                    st.success(
                        "Extraction SQL terminée. Les fichiers générés sont maintenant repris automatiquement ci-dessous."
                    )
                except Exception as exc:
                    st.error(f"Erreur pendant l'extraction SQL : {exc}")

        if "aria_last_sql_extraction_results" in st.session_state:
            with st.expander("Derniers logs d'extraction SQL", expanded=True):
                logs_df = pd.DataFrame(st.session_state["aria_last_sql_extraction_results"]).astype(str)
                st.dataframe(logs_df, use_container_width=True)

    else:
        st.markdown("### Extraction déjà faite")
        st.caption("L'application cherche directement les fichiers avec les bons noms dans le dossier indiqué.")

    # Dans les deux modes, on récupère automatiquement les fichiers d'entrée depuis inputs/ par défaut.
    traitement_path = _find_output_file(input_dir_value, "traitement_patient")
    formulaire_path = _find_output_file(input_dir_value, "formulaire_patient")
    ethos_path = _find_output_file(input_dir_value, "ethos_patient")

    detection_df = pd.DataFrame(
        [
            {"fichier attendu": "traitement_patient", "trouvé": "Oui" if traitement_path else "Non", "chemin": str(traitement_path or ""), "taille": _human_size(traitement_path)},
            {"fichier attendu": "formulaire_patient", "trouvé": "Oui" if formulaire_path else "Non", "chemin": str(formulaire_path or ""), "taille": _human_size(formulaire_path)},
            {"fichier attendu": "ethos_patient", "trouvé": "Oui" if ethos_path else "Non", "chemin": str(ethos_path or ""), "taille": _human_size(ethos_path)},
        ]
    )
    st.markdown("### Fichiers détectés")
    st.dataframe(detection_df.astype(str), use_container_width=True)

    treatment_file = _wrap_output_file(traitement_path)
    form_file = _wrap_output_file(formulaire_path)
    ethos_file = _wrap_output_file(ethos_path)

    if treatment_file and form_file:
        st.success("Fichiers traitement et formulaire détectés : le reste de l'application peut démarrer.")
    else:
        st.warning(f"Fichiers principaux incomplets dans {input_dir_value}/. Tu peux utiliser le mode manuel ci-dessous sans toucher au reste de l'app.")

    with st.expander("Mode manuel / dépannage", expanded=not (treatment_file and form_file)):
        st.caption("Fallback conservé pour ne pas casser l'ancien fonctionnement.")
        manual_treatment_file = st.file_uploader(
            "1. traitement_patient.csv/.zip/.xlsx",
            type=["csv", "zip", "xlsx"],
            help="Table traitement avec pt_id, CIM10, dates RT et dose.",
        )
        manual_form_file = st.file_uploader(
            "2. formulaire_patient.csv/.zip/.xlsx",
            type=["csv", "zip", "xlsx"],
            help="Formulaire large avec pt_id, date_event et items.",
        )
        manual_ethos_file = st.file_uploader(
            "3. ethos_patient.csv optionnel",
            type=["csv", "zip", "xlsx"],
            help="Fichier traitement ETHOS optionnel.",
        )
        if manual_treatment_file is not None:
            treatment_file = manual_treatment_file
        if manual_form_file is not None:
            form_file = manual_form_file
        if manual_ethos_file is not None:
            ethos_file = manual_ethos_file

    mapping_file = st.file_uploader(
        "4. mapping.csv optionnel",
        type=["csv", "xlsx"],
        help="Aide CIM10/localisation. Ne remplace pas la validation utilisateur.",
    )
    profile_file = st.file_uploader(
        "5. Profil JSON optionnel",
        type=["json"],
        help="Recharge une sélection de colonnes déjà validée.",
    )

if not treatment_file or not form_file:
    with tab_home:
        st.info(
            "Prendre sous la main les fichiers d'entrées désirés puis de déplacer dans l'onglet Import pour démarrer."
        )
    st.stop()

try:
    tx_standard = read_uploaded_table(treatment_file)
    tx_ethos = load_ethos_table(ethos_file) if ethos_file else pd.DataFrame()
    tx = merge_standard_and_ethos_treatments(tx_standard, tx_ethos)
    ethos_report = build_ethos_integration_report(tx_standard, tx_ethos, tx)
    fm, form_all_columns = load_form_meta_only(form_file)
    mapping_df = read_mapping_file(mapping_file) if mapping_file else pd.DataFrame()
    profile_settings, profile_config = (
        load_profile(profile_file) if profile_file else ({}, pd.DataFrame())
    )
except MemoryError as exc:
    st.error(
        "Erreur mémoire pendant la lecture des fichiers. "
        "Cette version lit le formulaire en streaming par petits morceaux, mais si l'erreur persiste, "
        "ferme les autres applications, relance VS Code puis réessaie avec les fichiers ZIP originaux. "
        f"Détail : {exc}"
    )
    st.stop()
except Exception as exc:
    st.error(f"Erreur de lecture des fichiers : {exc}")
    st.stop()

# Nettoyage automatique avec skrub : aucune option utilisateur.
# Les colonnes sensibles sont protégées et seules quelques colonnes catégorielles/logistiques
# peu risquées sont nettoyées automatiquement. Si skrub n'est pas installé, le pipeline continue.
skrub_report_frames: List[pd.DataFrame] = []
if SKRUB_AVAILABLE:
    tx_auto_skrub_cols = skrub_auto_columns(tx, "traitement_patient")
    fm_auto_skrub_cols = skrub_auto_columns(fm, "formulaire_patient")
    tx, rep_tx = clean_with_skrub_safe(tx, tx_auto_skrub_cols, "traitement_patient")
    fm, rep_fm = clean_with_skrub_safe(fm, fm_auto_skrub_cols, "formulaire_patient")
    if len(fm) > 50000 and not fm_auto_skrub_cols:
        rep_fm = pd.concat(
            [
                rep_fm,
                pd.DataFrame(
                    [
                        {
                            "table": "formulaire_patient",
                            "colonne": "",
                            "statut": "SKRUB_IGNORE_MEMOIRE",
                            "details": "Formulaire volumineux : skrub ignoré pour éviter les erreurs mémoire ; nettoyage explicite interne conservé",
                        }
                    ]
                ),
            ],
            ignore_index=True,
        )
    skrub_report_frames = [rep_tx, rep_fm]
else:
    skrub_report_frames = [
        pd.DataFrame(
            [
                {
                    "table": "global",
                    "colonne": "",
                    "statut": "SKRUB_NON_INSTALLE",
                    "details": "Pipeline exécuté avec nettoyage explicite interne uniquement",
                }
            ]
        )
    ]

skrub_report = (
    pd.concat(skrub_report_frames, ignore_index=True, sort=False)
    if skrub_report_frames
    else pd.DataFrame(columns=["table", "colonne", "statut", "details"])
)

if "pt_id" not in tx.columns or "pt_id" not in fm.columns:
    st.error(
        "La colonne `pt_id` est obligatoire dans traitement et formulaire pour réaliser le join technique."
    )
    st.stop()
if "date_event" not in fm.columns:
    st.error(
        "La colonne `date_event` est obligatoire dans le formulaire pour calculer dates, délais, semaines et mois."
    )
    st.stop()

tx["_pt_join_key"] = build_join_key(tx, primary="pt_id")
fm["_pt_join_key"] = build_join_key(fm, primary="pt_id")
tx_cols = resolve_treatment_columns(tx)
if not tx_cols.get("cim"):
    st.error(
        "Impossible de trouver la colonne CIM10 / DiagnosisCode dans traitement_patient."
    )
    st.stop()

available_cim = sorted(
    normalize_cim10(tx[tx_cols["cim"]])
    .dropna()
    .astype(str)
    .replace("", pd.NA)
    .dropna()
    .unique()
    .tolist()
)
common_default = profile_settings.get("cim10") or (
    "C61" if "C61" in available_cim else (available_cim[0] if available_cim else "")
)
form_meta_cols = {"pt_id", "_pt_join_key", "date_event"}
form_candidates = [c for c in form_all_columns if c not in form_meta_cols]

tumor_treatment_cols = detect_tumor_data_columns(list(tx.columns))
recommended_treatment = [
    c
    for c in [
        tx_cols.get("cim"),
        tx_cols.get("start"),
        tx_cols.get("end"),
        tx_cols.get("dose"),
        tx_cols.get("nb_fractions"),
        find_col_by_norm(tx.columns, ["FirstName", "Prénom"]),
        find_col_by_norm(tx.columns, ["LastName", "Nom"]),
        find_col_by_norm(tx.columns, ["Sex", "Sexe"]),
        find_col_by_norm(tx.columns, ["Naissance", "Date_Naissance"]),
        find_col_by_norm(tx.columns, ["PrescriptionName"]),
        find_col_by_norm(tx.columns, ["Site"]),
        find_col_by_norm(tx.columns, ["Technique"]),
        find_col_by_norm(tx.columns, ["NomMachine"]),
        find_col_by_norm(tx.columns, ["TechniqueId"]),
        "_source_traitement" if "_source_traitement" in tx.columns else None,
    ]
    + tumor_treatment_cols
    if c
]
_seen = set()
recommended_treatment = [
    c for c in recommended_treatment if not (c in _seen or _seen.add(c))
]


# Compatibilité profils anciens/nouveau SQL : Streamlit refuse les valeurs par défaut
# d'un multiselect si elles ne sont pas exactement présentes dans les options.
# On filtre donc les colonnes absentes et on tente de mapper les anciens noms
# vers les nouveaux noms SQL lorsque c'est évident.
def resolve_multiselect_existing_defaults(options: List[str], defaults: Any) -> List[str]:
    if defaults is None:
        return []
    if isinstance(defaults, str):
        raw_defaults = [defaults]
    else:
        try:
            raw_defaults = list(defaults)
        except TypeError:
            raw_defaults = [defaults]

    options = list(options)
    option_set = set(options)
    resolved: List[str] = []

    alias_map = {
        # Ancien SQL -> nouveau SQL traitement principal
        "DiagnosisCode": ["DiagnosisCodes", "DiagnosisCode", "CIM10", "ICD"],
        "PremiereFractionChamp": ["StartDateTime", "PremiereFractionChamp"],
        "DerniereFractionChamp": ["LastDateTime", "DerniereFractionChamp"],
        "DoseEffectuée2": ["Total_dose", "DoseEffectuée2", "DoseEffectuee2"],
        "DoseEffectuee2": ["Total_dose", "DoseEffectuee2", "DoseEffectuée2"],
        "DosesTotal2": ["Total_dose", "DosesTotal2"],
        "NbFractionsEffectués": ["NbTreatedFrac", "NbFractionsEffectués", "NbFractionsEffectues"],
        "NbFractionsEffectues": ["NbTreatedFrac", "NbFractionsEffectues", "NbFractionsEffectués"],
        "DosePerFraction": ["Dose_per_fraction", "DosePerFraction"],
        "Naissance": ["DateOfBirth", "Naissance"],
        "Age": ["AgeAtStart", "AgeToday", "Age"],
        "Technique": ["TechniquePrescription", "Technique"],
        "TechniqueId": ["TechniquePrescription", "TechniqueId"],
        "DiagPrimaire": ["DiagnosisDescriptions", "DiagPrimaire"],
        "Description": ["DiagnosisDescriptions", "Description"],
        "PatientStatus": ["Status", "PatientStatus"],
        "PrescriptionTemplateName": ["PrescriptionName", "PrescriptionTemplateName"],
        # Variantes tumorales singulier/pluriel du nouveau SQL
        "cncr_stage": ["cncr_stages", "cncr_stage"],
        "stg_crit_desc": ["stg_crit_descs_from_pt_dx", "stg_crit_desc"],
        "crit_desc": ["crit_descs", "crit_desc"],
        "date_staged": ["date_stageds", "date_staged"],
        "tumor_size": ["tumor_sizes", "tumor_size"],
        "ki67_pct": ["ki67_pcts", "ki67_pct"],
        "morph_cd": ["morph_cds", "morph_cd"],
        "invasive_ind": ["invasive_inds", "invasive_ind"],
        "gleason_prmy": ["gleason_prmys", "gleason_prmy"],
        "gleason_scndy": ["gleason_scndys", "gleason_scndy"],
        "gleason_total": ["gleason_totals", "gleason_total"],
        "multifocal_ind": ["multifocal_inds", "multifocal_ind"],
        "HistologyTableName": ["HistologyTableNames", "HistologyTableName"],
    }

    def add_candidate(candidate: Any) -> bool:
        if candidate is None:
            return False
        cand = str(candidate)
        if cand in option_set and cand not in resolved:
            resolved.append(cand)
            return True
        # Matching tolérant accents/espaces/casse via find_col_by_norm.
        match = find_col_by_norm(options, [cand])
        if match and match not in resolved:
            resolved.append(match)
            return True
        return False

    for default_col in raw_defaults:
        if add_candidate(default_col):
            continue
        for alias in alias_map.get(str(default_col), []):
            if add_candidate(alias):
                break

    return resolved

# ============================================================
# ÉTAT SESSION
# ============================================================

# État session
if "last_result" not in st.session_state:
    st.session_state.last_result = None
if "current_config" not in st.session_state:
    st.session_state.current_config = pd.DataFrame()


def merge_previous_selection_state(base_config: pd.DataFrame) -> pd.DataFrame:
    """Réinjecte les choix déjà faits dans la table de sélection.

    Streamlit relance le script à chaque interaction ; cette fonction évite de
    perdre les cases cochées, noms export et temporalités quand l'utilisateur
    filtre/recherche sans reconstruire l'export.
    """
    previous = st.session_state.get("current_config")
    if previous is None or previous.empty or base_config.empty:
        return base_config
    if "Colonne formulaire" not in previous.columns or "Colonne formulaire" not in base_config.columns:
        return base_config

    editable_cols = ["Inclure", "Nom export", "Cumul", "Avant RT", "Aigu", "Tardif"]
    prev_idx = previous.drop_duplicates("Colonne formulaire").set_index("Colonne formulaire")
    out = base_config.copy()
    for col in editable_cols:
        if col in prev_idx.columns and col in out.columns:
            mask = out["Colonne formulaire"].isin(prev_idx.index)
            out.loc[mask, col] = out.loc[mask, "Colonne formulaire"].map(prev_idx[col])
    return out

with tab_home:
    st.subheader("Vue d'ensemble")
    st.markdown(
        """
        <div class="stepgrid">
          <div class="stepcard"><div class="stepnum">1</div><div class="steptitle">Charger</div><div class="steptext">Importer traitement et formulaire. Le mapping est une aide optionnelle.</div></div>
          <div class="stepcard"><div class="stepnum">2</div><div class="steptitle">Cohorte</div><div class="steptext">Choisir un CIM10, plusieurs CIM10 ou tous les CIM10.</div></div>
          <div class="stepcard"><div class="stepnum">3</div><div class="steptitle">Colonnes</div><div class="steptext">Sélectionner les informations cliniques pertinentes dans le formulaire.</div></div>
          <div class="stepcard"><div class="stepnum">4</div><div class="steptitle">Temporalités</div><div class="steptext">Cocher cumul, avant RT, aigu ou tardif pour chaque donnée.</div></div>
          <div class="stepcard"><div class="stepnum">5</div><div class="steptitle">Exporter</div><div class="steptext">Télécharger un fichier final propre et un rapport de preuve.</div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    progress = 0
    progress += 1 if treatment_file is not None else 0
    progress += 1 if form_file is not None else 0
    progress += 1 if tx_cols.get("cim") else 0
    progress += 1 if "date_event" in fm.columns else 0
    progress += 1 if st.session_state.last_result is not None else 0
    pct = int(100 * progress / 5)
    st.markdown(
        f'<div class="progress-wrap"><b>Avancement</b><div class="progress-line"><div style="width:{pct}%"></div></div>{pct}% — fichiers, cohorte, sélection et export.</div>',
        unsafe_allow_html=True,
    )
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Lignes traitement", f"{len(tx):,}".replace(",", " "))
    c2.metric(
        "Patients traitement", f"{tx['_pt_join_key'].nunique():,}".replace(",", " ")
    )
    c3.metric("Lignes formulaire", f"{len(fm):,}".replace(",", " "))
    c4.metric("Colonnes formulaire", len(form_candidates))
    if "_source_traitement" in tx.columns:
        source_counts_home = (
            tx.groupby("_source_traitement")["_pt_join_key"]
            .nunique()
            .reset_index(name="patients")
        )
        with st.expander("Sources traitement intégrées", expanded=False):
            st.dataframe(source_counts_home, width="stretch", hide_index=True)
    st.markdown("#### Ce que l'outil produit")
    st.markdown(
        """
        <div class="mini-grid">
          <div class="okbox"><b>Export final</b><br>Une ligne par patient, Patient ID visible, vides remplacés par NA.</div>
          <div class="okbox"><b>Schéma ODM générique</b><br>Cumul, avant RT, aigu/pending RT, tardif/après RT, semaines et mois.</div>
          <div class="okbox"><b>Rapport preuve</b><br>Pipeline, sélection, mapping, qualité, colonnes générées.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with tab_sources:
    st.subheader("Sources et dictionnaire des colonnes")
    c1, c2, c3 = st.columns(3)
    c1.metric("CIM10 disponibles", len(available_cim))
    c2.metric("Mapping chargé", "Oui" if not mapping_df.empty else "Non")
    c3.metric("Mode", app_mode)
    if not ethos_report.empty:
        with st.expander("Intégration ETHOS", expanded=ethos_file is not None):
            st.dataframe(ethos_report, width="stretch", hide_index=True)
            st.caption(
                "ETHOS est traité comme un fichier traitement optionnel. "
                "Les lignes ETHOS non datées ou non dosées sont ignorées avant la fusion."
            )
    if SKRUB_AVAILABLE:
        st.caption(
            "skrub disponible : nettoyage automatique limité aux colonnes sûres/logistiques."
        )
    else:
        st.caption("skrub non installé : nettoyage explicite interne uniquement.")
    if not skrub_report.empty:
        with st.expander("Rapport nettoyage automatique skrub"):
            st.dataframe(skrub_report, width="stretch", hide_index=True)
    with st.expander("Liste des CIM10 disponibles"):
        st.dataframe(
            pd.DataFrame({"CIM10": available_cim}), width="stretch", hide_index=True
        )
    st.markdown("#### Colonnes formulaire détectées")
    search_col = st.text_input(
        "Rechercher une colonne", value="", key="search_source_cols"
    )
    rows = []
    for c in form_candidates:
        cat, rec, score = classify_column(c)
        rows.append(
            {
                "colonne_formulaire": c,
                "catégorie estimée": cat,
                "recommandation": rec,
                "score": score,
            }
        )
    col_dict = pd.DataFrame(rows).sort_values(
        ["score", "colonne_formulaire"], ascending=[False, True]
    )
    if search_col.strip():
        col_dict = col_dict[
            col_dict["colonne_formulaire"]
            .astype(str)
            .str.contains(search_col, case=False, na=False)
        ]
    st.dataframe(col_dict, width="stretch", hide_index=True)
    if not mapping_df.empty:
        st.markdown("#### Aperçu mapping")
        st.dataframe(mapping_df.head(100), width="stretch")

with tab_build:
    st.subheader("Construction de l'export")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        mode_cim10 = st.selectbox(
            "Mode CIM10",
            ["CIM10 pour le traitement considéré", "CIM10 général patient"],
            index=(
                0
                if profile_settings.get("mode_cim10") != "CIM10 général patient"
                else 1
            ),
        )
    with c2:
        cim10_text = st.text_input(
            "CIM10 à inclure",
            value=common_default,
            help="Exemples : C61 ou C50,C34. Laisser vide = tous les CIM10.",
        )
    with c3:
        dose_non_nulle = st.checkbox(
            "Dose non nulle",
            value=bool(profile_settings.get("dose_non_nulle", True)),
            key="dose_non_nulle_checkbox",
        )
    with c4:
        delay_reference = st.selectbox(
            "Référence délais",
            ["Début RT / startD", "Fin RT / endD"],
            index=(
                0 if profile_settings.get("delay_reference") != "Fin RT / endD" else 1
            ),
        )

    # Évite d'afficher un ancien résultat construit pour C61 quand l'utilisateur vient de saisir un autre CIM10.
    current_cohort_signature = {
        "cim10": cim10_text.strip(),
        "mode_cim10": mode_cim10,
        "dose_non_nulle": bool(dose_non_nulle),
        "delay_reference": delay_reference,
    }
    if st.session_state.get("last_cohort_signature") != current_cohort_signature:
        st.session_state.last_result = None
        st.session_state.last_cohort_signature = current_cohort_signature

    mapping_profile_text = ""
    mapping_rows_current = pd.DataFrame()
    suggested_cols: List[str] = []
    st.markdown("#### Aide mapping")
    if mapping_df.empty:
        st.info(
            "Mapping non chargé : l'app fonctionne, mais les suggestions seront basées seulement sur les noms de colonnes formulaire."
        )
    else:
        rows_cim = mapping_rows_for_cim(mapping_df, cim10_text)
        mapping_rows_current = rows_cim.copy()
        qmap = st.text_input(
            "Recherche libre dans mapping",
            value="",
            placeholder="prostate, sein, poumon, ORL...",
            key="qmap",
        )
        rows_search = (
            mapping_search_rows(mapping_df, qmap) if qmap.strip() else pd.DataFrame()
        )
        rows_help = rows_cim if not rows_cim.empty else rows_search
        if mapping_rows_current.empty and not rows_help.empty:
            mapping_rows_current = rows_help.copy()
        if not rows_help.empty:
            compact = compact_mapping_rows(rows_help)
            st.dataframe(compact, width="stretch", hide_index=True)
            keywords = infer_profile_keywords_from_mapping(rows_help)
            mapping_profile_text = ", ".join(keywords[:6])
            st.markdown(
                "Profil détecté : "
                + " ".join([f'<span class="pill">{k}</span>' for k in keywords[:8]]),
                unsafe_allow_html=True,
            )
            suggested_cols = suggest_columns_from_mapping_and_profile(
                form_candidates, keywords
            )
        else:
            st.warning(
                "Aucune ligne mapping trouvée. Tu peux construire l'export manuellement."
            )

    export_zone_label = infer_export_zone_name(
        cim10_text, mapping_profile_text, profile_settings, mapping_rows_current
    )
    file_names = export_filenames(export_zone_label)
    st.markdown(
        f'<div class="smallnote"><b>Nom de zone utilisé pour les exports :</b> {export_zone_label}<br>'
        f'Fichiers prévus : <code>{file_names["xlsx"]}</code> et <code>{file_names["json"]}</code></div>',
        unsafe_allow_html=True,
    )

    with st.expander(
        "Paramètres expert des fenêtres temporelles", expanded=(app_mode == "Expert")
    ):
        avant_text = st.text_input(
            "Semaines avant RT",
            value=", ".join(
                map(str, profile_settings.get("avant_weeks", DEFAULT_AVANT_WEEKS))
            ),
        )
        pendant_text = st.text_input(
            "Semaines pendant RT",
            value=", ".join(
                map(str, profile_settings.get("pendant_weeks", DEFAULT_PENDANT_WEEKS))
            ),
        )
        apres_text = st.text_input(
            "Semaines après RT",
            value=", ".join(
                map(str, profile_settings.get("apres_weeks", DEFAULT_APRES_WEEKS))
            ),
        )
        deduplicate = st.checkbox(
            "Supprimer les doublons exacts patient + item + date + valeur",
            value=bool(profile_settings.get("deduplicate", True)),
        )
        enable_profiling = st.checkbox(
            "Activer un profiling simple du calcul", value=False
        )
        st.caption(
            "Les mois tardifs utilisent les groupes standards : 01, 02-04, 05-07, ..., 62 et plus."
        )
    avant_weeks = parse_int_list(avant_text, DEFAULT_AVANT_WEEKS)
    pendant_weeks = parse_int_list(pendant_text, DEFAULT_PENDANT_WEEKS)
    apres_weeks = parse_int_list(apres_text, DEFAULT_APRES_WEEKS)

    treatment_options = [c for c in tx.columns if c != "_pt_join_key"]

    # Par défaut, on garde toutes les colonnes traitement visibles, sauf les
    # colonnes techniques/résolues qui servent uniquement aux calculs internes.
    # Cela évite de retrouver dans l'export des colonnes comme :
    # Aria Simu Resolved, Aria nombre fraction, Aria 2 Resolved, ou leurs
    # équivalents techniques `_aria_*_resolved`.
    DEFAULT_EXCLUDED_TREATMENT_COLUMN_LABELS = {
        "Aria Simu Resolved",
        "Aria nombre fraction",
        "Aria 2 Resolved",
        "_aria_patient_id_resolved",
        "_aria_dose_resolved",
        "_aria_nb_fractions_resolved",
        "_aria_start_resolved",
        "_aria_end_resolved",
        "_aria_cim_resolved",
    }
    DEFAULT_EXCLUDED_TREATMENT_COLUMN_KEYS = {
        norm_key(c) for c in DEFAULT_EXCLUDED_TREATMENT_COLUMN_LABELS
    }

    def _is_default_excluded_treatment_column(col: Any) -> bool:
        nk = norm_key(col)
        if nk in DEFAULT_EXCLUDED_TREATMENT_COLUMN_KEYS:
            return True
        # Sécurité : toutes les colonnes techniques créées par resolve_treatment_columns
        # ont cette forme. Elles sont utiles en interne mais ne doivent pas être
        # cochées par défaut dans les colonnes traitement exportées.
        if nk.startswith("aria_") and nk.endswith("resolved"):
            return True
        return False

    auto_excluded_treatment_cols = [
        c for c in treatment_options if _is_default_excluded_treatment_column(c)
    ]
    auto_treatment_default = [
        c for c in treatment_options if not _is_default_excluded_treatment_column(c)
    ]

    # Compatibilité TNM V11 : un ancien profil JSON peut encore demander des
    # colonnes redondantes/obsolètes comme stg_crit_desc, crit_desc, TNM_actif,
    # Stade_Tumoral, etc. Ici, on part volontairement du défaut complet
    # traitement_patient actuel, puis sanitize_treatment_columns nettoie si besoin.
    raw_treatment_default = resolve_multiselect_existing_defaults(
        treatment_options, auto_treatment_default
    )

    if "sanitize_treatment_columns" in globals():
        treatment_default = sanitize_treatment_columns(
            treatment_options, raw_treatment_default
        )
    else:
        treatment_default = raw_treatment_default

    treatment_cols = st.multiselect(
        "Colonnes traitement à garder",
        options=treatment_options,
        default=treatment_default,
        help=(
            "Par défaut, toutes les colonnes traitement sont cochées, sauf les colonnes "
            "techniques/résolues Aria Simu Resolved, Aria nombre fraction, Aria 2 Resolved "
            "et les colonnes internes `_aria_*_resolved`."
        ),
    )
    if auto_excluded_treatment_cols:
        with st.expander("Colonnes traitement décochées par défaut", expanded=False):
            st.dataframe(
                pd.DataFrame({"Colonne exclue par défaut": auto_excluded_treatment_cols}),
                width="stretch",
                hide_index=True,
            )
    cohort = filter_cohort(tx, tx_cols, cim10_text, mode_cim10, dose_non_nulle)
    patient_base = build_patient_base(cohort, tx_cols, treatment_cols)
    treatment_consistency = build_treatment_consistency_report(cohort, tx_cols)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Lignes traitement cohorte", f"{len(cohort):,}".replace(",", " "))
    c2.metric(
        "Patients cohorte",
        f"{patient_base['_pt_join_key'].nunique():,}".replace(",", " "),
    )
    c3.metric("Avec startD", int(patient_base["startD"].notna().sum()))
    c4.metric("Avec endD", int(patient_base["endD"].notna().sum()))
    # Interface plus sobre : les alertes et listes techniques restent disponibles,
    # mais ne prennent plus toute la place dans l'onglet Construction.
    if (not treatment_consistency.empty) or tumor_treatment_cols:
        with st.expander("Diagnostic cohorte", expanded=False):
            if not treatment_consistency.empty:
                st.warning(
                    f"{treatment_consistency['_pt_join_key'].nunique()} patient(s) ont plusieurs valeurs distinctes "
                    "pour une dose, une date, un nombre de fractions ou une machine. "
                    "Le détail sera disponible dans le rapport qualité et le rapport preuve."
                )
            if tumor_treatment_cols:
                st.markdown("**Données tumorales détectées et conservées**")
                st.write(tumor_treatment_cols)
    if len(cohort) > 0 and patient_base.empty:
        st.warning(
            "Le CIM10 est présent dans traitement_patient, mais aucune clé patient exploitable n'a permis de construire une base patient."
        )
    elif not patient_base.empty:
        n_join_form = (
            int(
                patient_base["_pt_join_key"]
                .isin(set(fm["_pt_join_key"].dropna().astype(str)))
                .sum()
            )
            if "_pt_join_key" in patient_base.columns and "_pt_join_key" in fm.columns
            else 0
        )
        if n_join_form == 0:
            st.warning(
                "Aucun patient de cette cohorte ne matche le formulaire avec la clé disponible. L'export contiendra les informations traitement, mais les colonnes formulaire seront à NA."
            )

    st.markdown("#### Sélection visuelle des colonnes formulaire")
    st.markdown(
        '<div class="smallnote"><b>Mode rapide Streamlit</b> : l’application ne scanne plus tout le formulaire à chaque clic. '
        "Les compteurs de valeurs par colonne sont donc désactivés par défaut et l’export relit uniquement les items sélectionnés au moment du bouton final.</div>",
        unsafe_allow_html=True,
    )

    compute_counts_now = st.checkbox(
        "Calculer les compteurs formulaire maintenant (plus lent)",
        value=False,
        key="compute_form_counts_now",
        help="Optionnel : scanne le formulaire pour remplir les colonnes Valeurs/Patients. À laisser décoché pour une interface rapide.",
    )
    cohort_keys_for_counts = (
        set(patient_base["_pt_join_key"].dropna().astype(str))
        if "_pt_join_key" in patient_base.columns
        else set()
    )
    if compute_counts_now:
        with st.spinner(
            "Calcul mémoire-sûr des valeurs non vides par colonne formulaire..."
        ):
            counts_df = compute_form_column_stats_streaming(
                form_file, form_candidates, cohort_keys_for_counts, chunksize=2500
            )
    else:
        counts_df = pd.DataFrame(
            columns=["Colonne formulaire", "Valeurs cohorte", "Patients cohorte"]
        )

    counts_map_val = (
        dict(zip(counts_df["Colonne formulaire"], counts_df["Valeurs cohorte"]))
        if not counts_df.empty
        else {}
    )
    counts_map_pat = (
        dict(zip(counts_df["Colonne formulaire"], counts_df["Patients cohorte"]))
        if not counts_df.empty
        else {}
    )

    # IMPORTANT : un profil JSON sert de base éditable, il ne verrouille pas la sélection.
    # On affiche donc TOUJOURS toutes les colonnes du formulaire :
    # - les colonnes du profil sont pré-cochées avec leurs phases sauvegardées ;
    # - les autres colonnes restent visibles et peuvent être ajoutées à la main ;
    # - le profil exporté après construction contiendra la sélection modifiée.
    profile_lookup: Dict[str, Dict[str, Any]] = {}
    missing_profile_cols: List[str] = []
    repaired_profile_matches: List[Dict[str, str]] = []
    form_lookup = build_column_lookup(form_candidates)
    has_loaded_profile = (
        not profile_config.empty and "Colonne formulaire" in profile_config.columns
    )
    if has_loaded_profile:
        # Matching robuste profil JSON -> formulaire actuel.
        # On ne se limite pas à `Colonne formulaire`, car un profil peut avoir été
        # généré depuis regle.xlsx avec un libellé export ou un libellé règle.
        # On teste donc plusieurs champs, toujours sans fuzzy automatique médical :
        # uniquement normalisation accents/espaces/retours ligne/mojibake.
        profile_match_debug_rows: List[Dict[str, str]] = []
        candidate_profile_fields = [
            "Colonne formulaire",
            "Nom export",
            "Libellé règle",
            "Libellé source candidat",
            "Colonne profil originale",
        ]
        for _, pr in profile_config.iterrows():
            primary_col_name = str(pr.get("Colonne formulaire", ""))
            matched_col = None
            matched_from = ""
            matched_key = ""

            raw_candidates: List[str] = []
            for field in candidate_profile_fields:
                val = pr.get(field, "")
                if (
                    pd.notna(val)
                    and str(val).strip()
                    and str(val) not in raw_candidates
                ):
                    raw_candidates.append(str(val))

            # 1) Correspondance exacte sur n'importe quel champ candidat.
            for cand in raw_candidates:
                if cand in form_candidates:
                    matched_col = cand
                    matched_from = "exact:" + (
                        next(
                            (
                                f
                                for f in candidate_profile_fields
                                if str(pr.get(f, "")) == cand
                            ),
                            "champ",
                        )
                    )
                    break

            # 2) Correspondance normalisée stricte sur accents/espaces/encodage.
            if matched_col is None:
                for cand in raw_candidates:
                    for k in column_match_keys(cand):
                        if k in form_lookup:
                            matched_col = form_lookup[k]
                            matched_from = "normalisé:" + cand
                            matched_key = k
                            break
                    if matched_col is not None:
                        break

            if matched_col:
                row = pr.to_dict()
                row["Colonne formulaire"] = matched_col
                row["Colonne profil originale"] = primary_col_name
                profile_lookup[matched_col] = row
                profile_match_debug_rows.append(
                    {
                        "Colonne profil principale": primary_col_name,
                        "Colonne formulaire retrouvée": matched_col,
                        "Méthode": matched_from or "exact",
                        "Clé normalisée": matched_key or norm_key(matched_col),
                    }
                )
                if matched_col != primary_col_name:
                    repaired_profile_matches.append(
                        {
                            "Colonne profil": primary_col_name,
                            "Colonne formulaire retrouvée": matched_col,
                            "Méthode": matched_from
                            or "matching flexible accents/espaces/encodage",
                        }
                    )
            elif primary_col_name.strip():
                missing_profile_cols.append(primary_col_name)
        st.info(
            f"Profil JSON chargé : {len(profile_lookup)} colonnes retrouvées dans le formulaire. "
            "Tu peux ajouter ou retirer des colonnes ci-dessous ; le profil n'est pas verrouillé."
        )
        if repaired_profile_matches:
            with st.expander(
                f"{len(repaired_profile_matches)} colonnes du profil retrouvées par matching flexible",
                expanded=False,
            ):
                st.dataframe(
                    pd.DataFrame(repaired_profile_matches),
                    width="stretch",
                    hide_index=True,
                )
        if has_loaded_profile:
            with st.expander(
                "Diagnostic matching profil JSON ↔ formulaire", expanded=False
            ):
                st.write(
                    {
                        "colonnes_dans_le_profil": int(len(profile_config)),
                        "colonnes_retrouvees": int(len(profile_lookup)),
                        "colonnes_non_trouvees": int(len(missing_profile_cols)),
                        "colonnes_formulaire_disponibles": int(len(form_candidates)),
                    }
                )
                if "profile_match_debug_rows" in locals() and profile_match_debug_rows:
                    st.dataframe(
                        pd.DataFrame(profile_match_debug_rows),
                        width="stretch",
                        hide_index=True,
                    )
        if missing_profile_cols:
            with st.expander(
                f"{len(missing_profile_cols)} colonnes du profil encore absentes du formulaire actuel",
                expanded=False,
            ):
                st.dataframe(
                    pd.DataFrame(
                        {"Colonnes profil non retrouvées": missing_profile_cols}
                    ),
                    width="stretch",
                    hide_index=True,
                )
                st.caption(
                    "Si une colonne te semble pourtant présente, utilise la recherche flexible ci-dessous : elle ignore accents, espaces, retours ligne et encodage mojibake."
                )

    selected_set = set(suggested_cols)
    if not selected_set and not has_loaded_profile:
        # proposer les meilleurs scores cliniques sans inclure automatiquement toutes les colonnes
        scores = [(classify_column(c)[2], c) for c in form_candidates]
        selected_set = {
            c for score, c in sorted(scores, reverse=True)[:20] if score >= 78
        }

    st.markdown("##### Ajouter des colonnes manuellement")
    manual_query = st.text_input(
        "Recherche flexible dans le formulaire",
        value="",
        placeholder="ex : diabete, proctite, recid locale, brulures mict, PSA...",
        key="manual_flexible_search",
        help="Recherche tolérante : accents, majuscules, espaces, retours ligne et encodages du type DiabÃ¨te sont ignorés.",
    )
    manual_options = (
        flexible_column_search(form_candidates, manual_query, limit=120)
        if manual_query.strip()
        else []
    )
    manual_add_cols = st.multiselect(
        "Colonnes à ajouter à la sélection",
        options=manual_options,
        default=[],
        key="manual_add_columns",
        help="Les colonnes choisies ici seront cochées dans la table, même si elles ne viennent pas du profil JSON.",
    )
    manual_add_set = set(manual_add_cols)

    rows = []
    for c in form_candidates:
        cat, rec, score = classify_column(c)
        default_phases = phase_defaults_for_column(c)
        pr = profile_lookup.get(c)
        if pr is not None:
            # Le profil a priorité sur les valeurs par défaut, mais la ligne reste éditable.
            nom_export = pr.get("Nom export", c) or c
            inclure = bool(pr.get("Inclure", True))
            phases = {
                "Cumul": bool(pr.get("Cumul", default_phases.get("Cumul", True))),
                "Avant RT": bool(
                    pr.get("Avant RT", default_phases.get("Avant RT", False))
                ),
                "Aigu": bool(pr.get("Aigu", default_phases.get("Aigu", False))),
                "Tardif": bool(pr.get("Tardif", default_phases.get("Tardif", False))),
            }
            source_sel = "Profil JSON"
        else:
            nom_export = c
            inclure = (c in selected_set if not has_loaded_profile else False) or (
                c in manual_add_set
            )
            phases = default_phases
            source_sel = (
                "Ajout manuel"
                if c in manual_add_set
                else ("Suggestion" if inclure else "Manuel")
            )

        # IMPORTANT DÉCODAGE : si la ligne vient du profil JSON, on repart de
        # toute la ligne originale `pr` avant d'ajouter les champs d'interface.
        # Sinon on perd les champs cachés indispensables au décodage binaire :
        # `Décodage actif`, `Type décodage`, `Décodage sortie`,
        # `Table décodage`, `Longueur code binaire`, etc.
        # C'était la cause typique du retour des valeurs 1000/0100/10/01.
        if pr is None:
            row_out = {}
        elif hasattr(pr, "to_dict"):
            # pr peut être une ligne pandas Series lorsqu'elle vient directement du profil.
            row_out = pr.to_dict()
        elif isinstance(pr, dict):
            # pr peut aussi déjà être un dict après matching flexible dans profile_lookup.
            row_out = dict(pr)
        else:
            try:
                row_out = dict(pr)
            except Exception:
                row_out = {}
        row_out.update(
            {
                "Inclure": inclure,
                "Colonne formulaire": c,
                "Nom export": nom_export,
                "Source sélection": source_sel,
                "Catégorie": cat,
                "Pertinence": rec,
                "Score": score,
                "Valeurs cohorte": int(counts_map_val.get(c, 0)),
                "Patients cohorte": int(counts_map_pat.get(c, 0)),
                **phases,
            }
        )
        rows.append(row_out)
    base_config = (
        pd.DataFrame(rows)
        .sort_values(
            [
                "Inclure",
                "Source sélection",
                "Score",
                "Patients cohorte",
                "Colonne formulaire",
            ],
            ascending=[False, True, False, False, True],
        )
        .reset_index(drop=True)
    )
    base_config = merge_previous_selection_state(base_config)

    search_select = st.text_input(
        "Filtrer la table de sélection",
        value="",
        placeholder="ex : proctite, diabete, récidive locale...",
        key="filter_selection",
    )
    display_config = base_config.copy()
    if search_select.strip():
        # Filtre flexible : accents/espaces/encodages ignorés, et recherche dans toutes les métadonnées de la ligne.
        q_tokens = [
            t for t in re.split(r"[^a-z0-9]+", norm_display_text(search_select)) if t
        ]

        def _row_match(row: pd.Series) -> bool:
            txt = norm_display_text(" ".join([str(v) for v in row.values]))
            return all(tok in txt for tok in q_tokens) if q_tokens else True

        mask = display_config.apply(_row_match, axis=1)
        display_config = display_config[mask].copy()
    else:
        # Mode rapide : ne pas afficher les 1000+ colonnes du formulaire.
        # On montre seulement les colonnes cochées/profil/suggestion/ajout manuel.
        source_col = display_config.get("Source sélection", pd.Series("", index=display_config.index)).astype(str)
        keep_fast = (
            display_config.get("Inclure", False).astype(bool)
            | source_col.isin(["Profil JSON", "Ajout manuel", "Suggestion"])
        )
        display_config = display_config[keep_fast].copy()
        if display_config.empty:
            display_config = base_config.head(80).copy()
        st.caption(
            "Affichage rapide : seules les colonnes sélectionnées/profil/suggestion sont affichées. "
            "Utilise la recherche pour retrouver une autre colonne du formulaire."
        )

    st.markdown("##### 1) Sélectionner les items")
    selection_columns = [
        "Inclure",
        "Colonne formulaire",
        "Nom export",
        "Source sélection",
        "Valeurs cohorte",
        "Patients cohorte",
        "Score",
    ]
    display_selection = display_config[
        [c for c in selection_columns if c in display_config.columns]
    ].copy()

    edited = st.data_editor(
        display_selection,
        width="stretch",
        hide_index=True,
        height=430,
        column_config={
            "Inclure": st.column_config.CheckboxColumn("Inclure"),
            "Colonne formulaire": st.column_config.TextColumn(
                "Colonne formulaire", disabled=True
            ),
            "Nom export": st.column_config.TextColumn("Nom export"),
            "Source sélection": st.column_config.TextColumn(
                "Source", disabled=True
            ),
            "Score": st.column_config.NumberColumn(
                "Score",
                disabled=True,
                help="Score heuristique basé sur le nom de la colonne.",
            ),
            "Valeurs cohorte": st.column_config.NumberColumn(
                "Valeurs",
                disabled=True,
                help="Nombre de cellules non vides dans le formulaire pour les patients de la cohorte.",
            ),
            "Patients cohorte": st.column_config.NumberColumn(
                "Patients",
                disabled=True,
                help="Nombre de patients de la cohorte avec au moins une valeur pour cette colonne.",
            ),
        },
        key="selection_table",
    )
    # Si la table est filtrée, `edited` ne contient que les lignes visibles.
    # On réinjecte donc les modifications dans la configuration complète pour
    # ne pas perdre les colonnes du profil ou les sélections déjà cochées.
    config = base_config.copy()
    if not edited.empty and "Colonne formulaire" in edited.columns:
        editable_cols = ["Inclure", "Nom export"]
        edited_idx = edited.set_index("Colonne formulaire")
        for col in editable_cols:
            if col in edited_idx.columns:
                mask = config["Colonne formulaire"].isin(edited_idx.index)
                config.loc[mask, col] = config.loc[mask, "Colonne formulaire"].map(
                    edited_idx[col]
                )

    included = (
        config[config.get("Inclure", False).astype(bool)].copy()
        if not config.empty
        else pd.DataFrame()
    )

    st.markdown("##### 2) Sélectionner les temporalités")
    if included.empty:
        st.info("Sélectionne au moins un item formulaire pour régler les fenêtres temporelles.")
    else:
        st.caption(
            "Les temporalités sont réglées uniquement sur les items inclus. "
            "Les trois tableaux ci-dessous alimentent les colonnes Avant RT, Pendant RT et Après RT de l'export."
        )
        temporal_source = included[
            [
                c
                for c in [
                    "Colonne formulaire",
                    "Nom export",
                    "Valeurs cohorte",
                    "Patients cohorte",
                    "Avant RT",
                    "Aigu",
                    "Tardif",
                ]
                if c in included.columns
            ]
        ].copy()
        temporal_source = temporal_source.sort_values(
            ["Patients cohorte", "Nom export"], ascending=[False, True]
        ).reset_index(drop=True)

        def _apply_temporal_editor(
            title: str,
            phase_col: str,
            checkbox_label: str,
            key: str,
            help_text: str,
        ) -> None:
            if phase_col not in temporal_source.columns:
                return
            st.markdown(f"###### {title}")
            phase_df = temporal_source[
                [
                    "Colonne formulaire",
                    "Nom export",
                    "Patients cohorte",
                    "Valeurs cohorte",
                    phase_col,
                ]
            ].copy()
            phase_df = phase_df.rename(columns={phase_col: checkbox_label})
            edited_phase = st.data_editor(
                phase_df,
                width="stretch",
                hide_index=True,
                height=min(360, max(170, 38 * (len(phase_df) + 1))),
                column_order=[
                    checkbox_label,
                    "Nom export",
                    "Patients cohorte",
                    "Valeurs cohorte",
                    "Colonne formulaire",
                ],
                column_config={
                    checkbox_label: st.column_config.CheckboxColumn(
                        checkbox_label, help=help_text
                    ),
                    "Nom export": st.column_config.TextColumn("Item", disabled=True),
                    "Colonne formulaire": st.column_config.TextColumn(
                        "Colonne source", disabled=True
                    ),
                    "Patients cohorte": st.column_config.NumberColumn(
                        "Patients", disabled=True
                    ),
                    "Valeurs cohorte": st.column_config.NumberColumn(
                        "Valeurs", disabled=True
                    ),
                },
                key=key,
            )
            if not edited_phase.empty and "Colonne formulaire" in edited_phase.columns:
                edited_idx = edited_phase.set_index("Colonne formulaire")
                if checkbox_label in edited_idx.columns:
                    mask = config["Colonne formulaire"].isin(edited_idx.index)
                    config.loc[mask, phase_col] = (
                        config.loc[mask, "Colonne formulaire"]
                        .map(edited_idx[checkbox_label])
                        .fillna(False)
                        .astype(bool)
                    )

        _apply_temporal_editor(
            "Avant RT",
            "Avant RT",
            "Avant RT",
            "temporal_avant_rt_table",
            "Créer les colonnes CumulAnteRT et semaines AvantRT pour cet item.",
        )
        _apply_temporal_editor(
            "Pendant RT",
            "Aigu",
            "Pendant RT",
            "temporal_pendant_rt_table",
            "Créer les colonnes CumulAigu et semaines PendantRT pour cet item.",
        )
        _apply_temporal_editor(
            "Après RT",
            "Tardif",
            "Après RT",
            "temporal_apres_rt_table",
            "Créer les colonnes CumulTardif, semaines AprèsRT et mois tardifs pour cet item.",
        )

    st.session_state.current_config = config
    included = (
        config[config.get("Inclure", False).astype(bool)].copy()
        if not config.empty
        else pd.DataFrame()
    )

    schema_preview_rows: List[Dict[str, str]] = []
    for _, r in included.iterrows():
        phases = {
            "Cumul": bool(r.get("Cumul", True)),
            "Avant RT": bool(r.get("Avant RT", False)),
            "Aigu": bool(r.get("Aigu", False)),
            "Tardif": bool(r.get("Tardif", False)),
        }
        schema_preview_rows.extend(
            build_schema_for_item(
                str(r.get("Nom export") or r["Colonne formulaire"]),
                phases,
                avant_weeks,
                pendant_weeks,
                apres_weeks,
                DEFAULT_MONTH_BINS,
            )
        )

    st.markdown("##### Résumé")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Items inclus", len(included))
    c2.metric("Colonnes export prévues", len(schema_preview_rows))
    c3.metric("Patients", int(patient_base["_pt_join_key"].nunique()))
    c4.metric("Mode", app_mode)
    if included.empty:
        st.warning("Aucune colonne incluse pour le moment.")

    build_btn = st.button(
        "Construire / recalculer",
        type="primary",
        disabled=included.empty or patient_base.empty,
    )
    if build_btn:
        with st.spinner("Construction de l'export et du rapport preuve..."):
            profiling_rows: List[Dict[str, Any]] = []

            def _mark_step(label: str, start_time: float) -> None:
                if enable_profiling:
                    profiling_rows.append(
                        {
                            "étape": label,
                            "durée_secondes": round(perf_counter() - start_time, 3),
                        }
                    )

            selected_cols = included["Colonne formulaire"].tolist()
            t0 = perf_counter()
            forms_long, duplicates = prepare_forms_long_streaming(
                form_file,
                patient_base,
                selected_cols,
                deduplicate=deduplicate,
                chunksize=2500,
            )
            _mark_step("Préparation formulaire long", t0)
            t0 = perf_counter()
            odm_block, schema_df = build_generic_item_block(
                patient_base,
                forms_long,
                included,
                delay_reference,
                avant_weeks,
                pendant_weeks,
                apres_weeks,
                DEFAULT_MONTH_BINS,
            )
            _mark_step("Construction bloc ODM", t0)
            t0 = perf_counter()
            treatment_public = patient_base.drop(
                columns=["_pt_join_key"], errors="ignore"
            ).copy()
            treatment_public["startD"] = treatment_public["startD"].map(
                excel_date_string
            )
            treatment_public["endD"] = treatment_public["endD"].map(excel_date_string)
            final = (
                treatment_public.merge(odm_block, on="Patient ID", how="left")
                if "Patient ID" in treatment_public.columns
                else odm_block
            )
            final = export_safe_df(final)
            _mark_step("Assemblage export final", t0)
            protected_export_cols = {"Patient ID"}
            empty_cols = [
                c
                for c in final.columns
                if c not in protected_export_cols
                and final[c].astype(str).eq("NA").all()
            ]
            empty_cols_df = pd.DataFrame({"colonne_export_100pct_NA": empty_cols})
            selection_df = included.copy()
            selection_df["nb_valeurs_formulaire_total"] = [
                int(counts_map_val.get(c, 0))
                for c in selection_df["Colonne formulaire"]
            ]
            selection_df["nb_patients_avec_valeur_cohorte"] = [
                int(forms_long.loc[forms_long["item"].eq(c), "_pt_join_key"].nunique())
                for c in selection_df["Colonne formulaire"]
            ]
            summary = pd.DataFrame(
                [
                    {"métrique": "Zone export", "valeur": export_zone_label},
                    {"métrique": "Mode CIM10", "valeur": mode_cim10},
                    {"métrique": "CIM10", "valeur": cim10_text or "Tous"},
                    {"métrique": "Dose non nulle", "valeur": dose_non_nulle},
                    {"métrique": "Mapping chargé", "valeur": not mapping_df.empty},
                    {
                        "métrique": "Profil mapping détecté",
                        "valeur": mapping_profile_text or "NA",
                    },
                    {
                        "métrique": "Patients",
                        "valeur": int(patient_base["_pt_join_key"].nunique()),
                    },
                    {
                        "métrique": "Colonnes formulaire incluses",
                        "valeur": len(included),
                    },
                    {"métrique": "Colonnes ODM générées", "valeur": len(schema_df)},
                    {"métrique": "Colonnes export final", "valeur": final.shape[1]},
                    {"métrique": "Colonnes 100% NA", "valeur": len(empty_cols)},
                    {"métrique": "Référence délai", "valeur": delay_reference},
                    {"métrique": "Doublons supprimés", "valeur": deduplicate},
                    {
                        "métrique": "Fichier ETHOS chargé",
                        "valeur": ethos_file is not None,
                    },
                ]
            )
            if "_source_traitement" in patient_base.columns:
                source_summary = (
                    patient_base.groupby("_source_traitement", dropna=False)[
                        "_pt_join_key"
                    ]
                    .nunique()
                    .reset_index(name="patients")
                )
                for _, src_row in source_summary.iterrows():
                    summary = pd.concat(
                        [
                            summary,
                            pd.DataFrame(
                                [
                                    {
                                        "métrique": f"Patients source traitement {src_row['_source_traitement']}",
                                        "valeur": int(src_row["patients"]),
                                    }
                                ]
                            ),
                        ],
                        ignore_index=True,
                    )
            dist = pd.DataFrame()
            if tx_cols.get("cim") in cohort.columns:
                tmp = cohort.copy()
                tmp["CIM10_norm"] = normalize_cim10(tmp[tx_cols["cim"]])
                dist = (
                    tmp.groupby("CIM10_norm", dropna=False)
                    .agg(
                        lignes_traitement=("_pt_join_key", "size"),
                        patients=("_pt_join_key", "nunique"),
                    )
                    .reset_index()
                )
            quality = build_quality_report(
                tx,
                fm,
                cohort,
                patient_base,
                forms_long,
                included,
                duplicates,
                treatment_consistency,
            )
            pipeline = build_pipeline_sheet(
                {
                    "export_zone": export_zone_label,
                    "mode_cim10": mode_cim10,
                    "cim10": cim10_text,
                    "dose_non_nulle": dose_non_nulle,
                    "mapping_used": not mapping_df.empty,
                    "mapping_profile": mapping_profile_text,
                    "delay_reference": delay_reference,
                    "ethos_used": ethos_file is not None,
                }
            )
            mapping_help = (
                compact_mapping_rows(mapping_rows_for_cim(mapping_df, cim10_text))
                if not mapping_df.empty
                else pd.DataFrame()
            )
            proof_sheets = {
                "Pipeline": pipeline,
                "Resume": summary,
                "Qualite": quality,
                "Distribution_CIM10": dist,
                "Selection_colonnes": selection_df,
                "Schema_colonnes": schema_df,
                "Colonnes_100pct_NA": empty_cols_df,
                "Aide_mapping": mapping_help,
                "Skrub_nettoyage": skrub_report,
                "Ethos_integration": ethos_report,
                "Traitement_incoherences": treatment_consistency,
                "Doublons_exact_sample": duplicates.head(5000),
                "Formulaire_long_sample": forms_long.head(10000),
            }
            if enable_profiling:
                proof_sheets["Profiling"] = pd.DataFrame(profiling_rows)
            t0 = perf_counter()
            final_xlsx = workbook_bytes_final(final)
            proof_xlsx = workbook_bytes_proof(proof_sheets)
            final_csv = dataframe_to_csv_bytes(final)
            _mark_step("Génération fichiers", t0)
            # IMPORTANT DÉCODAGE : on conserve les réglages du profil chargé,
            # notamment `settings.binary_choice_decode`, avant d'écraser les
            # paramètres pilotés par l'interface. Sans ça, un profil sauvegardé
            # depuis Streamlit perd les tables de décodage centralisées.
            profile_settings_out = dict(profile_settings) if isinstance(profile_settings, dict) else {}
            profile_settings_out.update(
                {
                    "export_zone": export_zone_label,
                    "mode_cim10": mode_cim10,
                    "cim10": cim10_text,
                    "dose_non_nulle": dose_non_nulle,
                    "delay_reference": delay_reference,
                    "treatment_cols": treatment_cols,
                    "avant_weeks": avant_weeks,
                    "pendant_weeks": pendant_weeks,
                    "apres_weeks": apres_weeks,
                    "deduplicate": deduplicate,
                }
            )
            profile_bytes = build_profile(included, profile_settings_out)
            file_names_result = export_filenames(export_zone_label)
            st.session_state.last_result = {
                "final": final,
                "empty_cols": empty_cols,
                "quality": quality,
                "summary": summary,
                "schema": schema_df,
                "selection": selection_df,
                "treatment_consistency": treatment_consistency,
                "profiling": pd.DataFrame(profiling_rows),
                "final_xlsx": final_xlsx,
                "proof_xlsx": proof_xlsx,
                "final_csv": final_csv,
                "profile_bytes": profile_bytes,
                "export_zone": export_zone_label,
                "file_names": file_names_result,
            }
        st.success("Fichiers construits.")

    if st.session_state.last_result is not None:
        res = st.session_state.last_result
        st.markdown("#### Résultat construit")
        c1, c2, c3 = st.columns(3)
        c1.metric("Patients", res["final"].shape[0])
        c2.metric("Colonnes export", res["final"].shape[1])
        c3.metric("Colonnes ODM", len(res["schema"]))
        with st.expander("Aperçu export final (25 premières lignes)", expanded=False):
            st.dataframe(res["final"].head(25), width="stretch")
        if res.get("profiling") is not None and not res["profiling"].empty:
            with st.expander("Profiling simple du dernier calcul"):
                st.dataframe(res["profiling"], width="stretch", hide_index=True)

        empty_cols = res.get("empty_cols", [])
        if empty_cols:
            st.markdown(
                f'<div class="warnbox"><b>{len(empty_cols)} colonnes seront 100 % NA</b> dans l’export final. '
                "Tu peux les garder pour conserver un schéma complet, ou les retirer pour obtenir un fichier plus lisible.</div>",
                unsafe_allow_html=True,
            )
            with st.expander("Voir les colonnes totalement vides"):
                st.dataframe(
                    pd.DataFrame({"Colonnes 100% NA": empty_cols}),
                    width="stretch",
                    hide_index=True,
                )
            keep_empty_cols = st.radio(
                "Exporter les colonnes totalement vides ?",
                ["Oui, garder le schéma complet", "Non, retirer les colonnes 100% NA"],
                index=1,  # Choix par défaut : export plus lisible, sans colonnes entièrement vides.
                horizontal=True,
                key="keep_empty_cols_export",
            )
        else:
            st.success("Aucune colonne totalement vide détectée dans l’export final.")
            keep_empty_cols = "Oui, garder le schéma complet"

        final_for_download = (
            res["final"]
            if keep_empty_cols.startswith("Oui")
            else res["final"].drop(columns=empty_cols, errors="ignore")
        )
        final_xlsx_download = workbook_bytes_final(final_for_download)
        final_csv_download = dataframe_to_csv_bytes(final_for_download)

        file_names = res.get(
            "file_names", export_filenames(res.get("export_zone", "Export_ODM"))
        )
        d1, d2, d3, d4 = st.columns(4)
        d1.download_button(
            "Export final Excel",
            final_xlsx_download,
            file_names["xlsx"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        d2.download_button(
            "Rapport preuve Excel",
            res["proof_xlsx"],
            file_names["proof"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        d3.download_button(
            "Export final CSV", final_csv_download, file_names["csv"], "text/csv"
        )
        d4.download_button(
            "Sauvegarder profil JSON",
            res["profile_bytes"],
            file_names["json"],
            "application/json",
        )

with tab_quality:
    st.subheader("Contrôle qualité")
    if st.session_state.last_result is None:
        st.info(
            "Construis d'abord un export dans l'onglet Construction pour afficher les contrôles qualité complets."
        )
    else:
        q = st.session_state.last_result["quality"]
        st.dataframe(q, width="stretch", hide_index=True)
        ok_count = int((q["niveau"] == "OK").sum()) if "niveau" in q.columns else 0
        st.metric("Contrôles OK", f"{ok_count} / {len(q)}")
        if "A vérifier" in set(q["niveau"].astype(str)):
            st.markdown(
                '<div class="warnbox">Certains contrôles demandent une vérification manuelle avant exploitation.</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div class="okbox">Aucun contrôle bloquant détecté.</div>',
                unsafe_allow_html=True,
            )
        treatment_consistency = st.session_state.last_result.get(
            "treatment_consistency", pd.DataFrame()
        )
        st.markdown("#### Cohérence des données traitement")
        if treatment_consistency is None or treatment_consistency.empty:
            st.success(
                "Aucune multiplicité détectée pour les doses, dates, fractions ou machines."
            )
        else:
            st.warning(
                "Des patients ont plusieurs valeurs distinctes pour au moins une donnée traitement. "
                "Il faut vérifier si cela correspond à plusieurs plans/fractions ou à une incohérence."
            )
            st.dataframe(treatment_consistency, width="stretch", hide_index=True)

        st.markdown("#### Colonnes générées")
        st.dataframe(
            st.session_state.last_result["schema"].head(500),
            width="stretch",
            hide_index=True,
        )

with tab_profile:
    st.subheader("Profils d'extraction")
    st.markdown(
        '<div class="smallnote">Un profil JSON remplace l’ancien fichier règle dans l’usage quotidien : il mémorise les colonnes incluses, leurs noms export, les phases cochées et les paramètres temporels.</div>',
        unsafe_allow_html=True,
    )

    current_profile_table = st.session_state.get("current_config")
    if current_profile_table is not None and not current_profile_table.empty:
        current_profile_table = current_profile_table.copy()
        st.markdown("#### Tableau complet des items formulaire")
        st.caption(
            "Ce tableau contient tous les items détectés dans formulaire_patient : "
            "les items déjà cochés dans le JSON et les items non cochés. "
            "Tu peux cocher un item ici, modifier son nom export et ses temporalités, "
            "puis retourner dans Construction pour recalculer ou télécharger un profil JSON."
        )

        total_items = int(len(current_profile_table))
        included_items = int(current_profile_table.get("Inclure", False).astype(bool).sum())
        c1, c2, c3 = st.columns(3)
        c1.metric("Items formulaire", total_items)
        c2.metric("Items cochés", included_items)
        c3.metric("Items non cochés", max(total_items - included_items, 0))

        profile_filter = st.text_input(
            "Filtrer les items du formulaire",
            value="",
            placeholder="ex : sécheresse, récidive, dysurie, radiodermite...",
            key="profile_items_filter",
        )
        profile_display = current_profile_table.copy()
        if profile_filter.strip():
            q_tokens = [
                t
                for t in re.split(r"[^a-z0-9]+", norm_display_text(profile_filter))
                if t
            ]

            def _profile_row_match(row: pd.Series) -> bool:
                txt = norm_display_text(" ".join([str(v) for v in row.values]))
                return all(tok in txt for tok in q_tokens) if q_tokens else True

            profile_display = profile_display[
                profile_display.apply(_profile_row_match, axis=1)
            ].copy()

        profile_columns = [
            "Inclure",
            "Colonne formulaire",
            "Nom export",
            "Source sélection",
            "Cumul",
            "Avant RT",
            "Aigu",
            "Tardif",
            "Valeurs cohorte",
            "Patients cohorte",
            "Score",
        ]
        profile_display = profile_display[
            [c for c in profile_columns if c in profile_display.columns]
        ].copy()

        edited_profile_table = st.data_editor(
            profile_display,
            width="stretch",
            hide_index=True,
            height=520,
            column_order=[c for c in profile_columns if c in profile_display.columns],
            column_config={
                "Inclure": st.column_config.CheckboxColumn("Inclure"),
                "Colonne formulaire": st.column_config.TextColumn(
                    "Colonne formulaire", disabled=True
                ),
                "Nom export": st.column_config.TextColumn("Nom export"),
                "Source sélection": st.column_config.TextColumn("Source", disabled=True),
                "Cumul": st.column_config.CheckboxColumn("Cumul"),
                "Avant RT": st.column_config.CheckboxColumn("Avant RT"),
                "Aigu": st.column_config.CheckboxColumn("Aigu"),
                "Tardif": st.column_config.CheckboxColumn("Tardif"),
                "Valeurs cohorte": st.column_config.NumberColumn("Valeurs", disabled=True),
                "Patients cohorte": st.column_config.NumberColumn("Patients", disabled=True),
                "Score": st.column_config.NumberColumn("Score", disabled=True),
            },
            key="profile_full_items_table",
        )

        # Réinjecte les modifications du tableau Profil dans la config globale.
        # Au prochain rerun, l'onglet Construction reprend ces choix via
        # merge_previous_selection_state().
        full_profile_config = current_profile_table.copy()
        if (
            not edited_profile_table.empty
            and "Colonne formulaire" in edited_profile_table.columns
            and "Colonne formulaire" in full_profile_config.columns
        ):
            editable_profile_cols = [
                "Inclure",
                "Nom export",
                "Cumul",
                "Avant RT",
                "Aigu",
                "Tardif",
            ]
            edited_idx = edited_profile_table.set_index("Colonne formulaire")
            for col in editable_profile_cols:
                if col in edited_idx.columns and col in full_profile_config.columns:
                    mask = full_profile_config["Colonne formulaire"].isin(edited_idx.index)
                    full_profile_config.loc[mask, col] = full_profile_config.loc[
                        mask, "Colonne formulaire"
                    ].map(edited_idx[col])
            st.session_state.current_config = full_profile_config

        included_profile_now = full_profile_config[
            full_profile_config.get("Inclure", False).astype(bool)
        ].copy()
        if not included_profile_now.empty:
            profile_settings_table_out = (
                dict(profile_settings) if isinstance(profile_settings, dict) else {}
            )
            profile_settings_table_out.update(
                {
                    "export_zone": export_zone_label,
                    "mode_cim10": mode_cim10,
                    "cim10": cim10_text,
                    "dose_non_nulle": dose_non_nulle,
                    "delay_reference": delay_reference,
                    "treatment_cols": treatment_cols,
                    "avant_weeks": avant_weeks,
                    "pendant_weeks": pendant_weeks,
                    "apres_weeks": apres_weeks,
                    "deduplicate": deduplicate,
                }
            )
            profile_table_bytes = build_profile(
                included_profile_now, profile_settings_table_out
            )
            st.download_button(
                "Télécharger le profil JSON depuis ce tableau",
                profile_table_bytes,
                export_filenames(export_zone_label)["json"],
                "application/json",
                key="download_profile_from_full_table",
            )
        else:
            st.info("Aucun item coché dans le tableau Profil pour générer un JSON.")

    if not profile_config.empty:
        st.success("Profil JSON chargé comme base modifiable.")
        st.markdown(
            "Le profil préremplit les colonnes et les phases dans l'onglet Construction. "
            "Le tableau complet ci-dessus permet aussi d'ajouter des items du formulaire au profil."
        )
        with st.expander("Voir le profil JSON chargé", expanded=False):
            st.dataframe(profile_config, width="stretch", hide_index=True)
    elif st.session_state.last_result is not None:
        file_names = st.session_state.last_result.get(
            "file_names",
            export_filenames(
                st.session_state.last_result.get("export_zone", "Export_ODM")
            ),
        )
        st.download_button(
            "Télécharger le profil du dernier export",
            st.session_state.last_result["profile_bytes"],
            file_names["json"],
            "application/json",
        )
    elif current_profile_table is None or current_profile_table.empty:
        st.info(
            "Construis un export pour générer un profil, ou charge un profil JSON dans la barre latérale."
        )

if __name__ == "__main__":
    pass
