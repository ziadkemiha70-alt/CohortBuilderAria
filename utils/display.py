# -*- coding: utf-8 -*-
"""Affichage commun Streamlit : configuration, CSS et en-tête."""

from pathlib import Path

import streamlit as st

PICTURES_DIR = Path("pictures")


def find_logo_path(pictures_dir: Path = PICTURES_DIR):
    """Retourne le chemin du logo si une image est trouvée dans pictures/ ou assets/."""
    candidates = [
        pictures_dir / "logo_strauss.png",
        pictures_dir / "logo_institut_strauss.png",
        pictures_dir / "logo.png",
        pictures_dir / "strauss.png",
        Path("assets") / "logo_strauss.png",
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate

    if pictures_dir.exists():
        image_files = sorted(
            [
                p
                for p in pictures_dir.iterdir()
                if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
            ]
        )
        preferred = [
            p
            for p in image_files
            if "logo" in p.stem.lower() or "strauss" in p.stem.lower()
        ]

        if preferred:
            return preferred[0]
        if len(image_files) == 1:
            return image_files[0]

    return None


def setup_page() -> None:
    """Configure la page et injecte le CSS léger de l'application."""
    st.set_page_config(page_title="ARIA ODM Builder — Institut Strauss", layout="wide")
    st.markdown(
        """
        <style>
        :root {
            --strauss-cyan: #27B4E8;
            --strauss-blue: #243FC4;
            --strauss-blue-dark: #162A8F;
            --strauss-soft: rgba(39, 180, 232, 0.10);
            --strauss-border: rgba(36, 63, 196, 0.18);
        }

        .block-container {
            padding-top: 2.2rem;
            padding-bottom: 2rem;
            max-width: 1600px;
        }

        .okbox, .smallnote, .warnbox, .badbox {
            padding: .8rem 1rem;
            border-radius: 15px;
            margin: .35rem 0;
            border: 1px solid var(--strauss-border);
        }
        .okbox { background: rgba(20, 184, 166, .10); }
        .smallnote { background: var(--strauss-soft); }
        .warnbox { background: rgba(245, 158, 11, .12); border-color: rgba(245, 158, 11, .40); }
        .badbox { background: rgba(239, 68, 68, .12); border-color: rgba(239, 68, 68, .40); }

        .stTabs [data-baseweb="tab-list"] {
            gap: .35rem;
            flex-wrap: wrap;
        }
        .stTabs [data-baseweb="tab"] {
            border-radius: 999px;
            padding: .45rem .9rem;
            border: 1px solid var(--strauss-border);
        }
        .stTabs [aria-selected="true"] {
            background: linear-gradient(135deg, var(--strauss-cyan), var(--strauss-blue)) !important;
            color: white !important;
        }

        .stDownloadButton button, .stButton button {
            border-radius: 999px;
            font-weight: 700;
        }

        .stepgrid {
            display: grid;
            grid-template-columns: repeat(5, minmax(0, 1fr));
            gap: .85rem;
            margin: .8rem 0 1.1rem 0;
        }
        .stepcard {
            border: 1px solid var(--strauss-border);
            border-radius: 19px;
            padding: 1rem;
            min-height: 138px;
            background: var(--strauss-soft);
        }
        .stepnum {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 32px;
            height: 32px;
            border-radius: 999px;
            background: linear-gradient(135deg, var(--strauss-cyan), var(--strauss-blue));
            color: #fff;
            font-weight: 900;
            margin-bottom: .55rem;
        }
        .steptitle { font-weight: 900; color: var(--strauss-blue-dark); margin-bottom: .25rem; }
        .steptext { font-size: .91rem; line-height: 1.35; }

        .pill {
            display: inline-block;
            padding: .25rem .65rem;
            border-radius: 999px;
            background: var(--strauss-soft);
            border: 1px solid var(--strauss-border);
            font-weight: 800;
            font-size: .84rem;
            margin: .15rem .2rem .15rem 0;
        }

        .progress-wrap {
            border: 1px solid var(--strauss-border);
            border-radius: 18px;
            padding: .9rem 1rem;
            margin: .5rem 0 1rem 0;
        }
        .progress-line {
            height: 10px;
            background: rgba(148, 163, 184, .35);
            border-radius: 999px;
            overflow: hidden;
            margin: .65rem 0 .35rem;
        }
        .progress-line > div {
            height: 100%;
            background: linear-gradient(90deg, var(--strauss-cyan), var(--strauss-blue));
            border-radius: 999px;
        }
        .mini-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: .75rem;
        }

        @media (max-width: 1200px) {
            .stepgrid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
            .mini-grid { grid-template-columns: 1fr; }
        }
        @media (max-width: 720px) {
            .stepgrid { grid-template-columns: 1fr; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header() -> None:
    """Affiche le logo externe et le titre de l'application."""
    logo_path = find_logo_path()
    st.markdown("<div style='height: 0.8rem;'></div>", unsafe_allow_html=True)

    header_logo_col, header_title_col = st.columns([1.15, 4.85])

    with header_logo_col:
        if logo_path is not None:
            st.image(str(logo_path), width=210)
        else:
            st.warning("Logo introuvable dans le dossier pictures/.")

    with header_title_col:
        st.title("ARIA ODM Builder — assistant guidé d’extraction")
        st.caption(
            "Construire un export patient unique à partir des traitements et des formulaires, "
            "sans fichier règle écrit à la main."
        )

    st.markdown("<div style='height: 0.4rem;'></div>", unsafe_allow_html=True)
