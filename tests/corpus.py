"""Corpus de fichiers réels (dessins, symboles, bases d'outils) : jamais
dans le dépôt.

Chaque fichier ou dossier est désigné par une **clé** ; où il se trouve
sur le poste est écrit dans `tests/corpus_local.json` (non versionné) ou
dans le fichier JSON désigné par la variable `VD_CORPUS` :

    {"vnd_verite": "D:/…/dessin.vnd", "symboles": "D:/…/Symbols", …}

Une clé absente donne un chemin qui n'existe pas : le test est sauté.
Clés employées : vnd_verite, dxf_verite, dossier_verite (dessin de
référence exporté en VND, DXF, SVG, PDF, PNG, SimPl) ; symboles,
smb_cote_laterale, smb_cotes_axes, smb_marqueur, smb_pdf, symboles_perso, symboles_bat, smb_textes, smb_textes_2, smb_centre, smb_montage ; dossier_corpus,
dxf_reel_1 ; step ; bases_outils (bases .Dbt et fiches .MAH) ;
dessins_gvt, gvt_exemple ; vnd_datron_1, vnd_datron_2 ; cielle_cljob ; vnm_codebarre
(modèle TypeEdit avec code-barres CObBCode).
"""
from __future__ import annotations

import functools
import json
import os
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
ABSENT = HERE / '__corpus_absent__'


@functools.lru_cache(maxsize=1)
def table() -> dict:
    f = os.environ.get('VD_CORPUS') or str(HERE / 'corpus_local.json')
    try:
        return json.loads(pathlib.Path(f).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def corpus(key: str) -> pathlib.Path:
    """Chemin du fichier ou dossier `key` sur ce poste (inexistant si inconnu)."""
    v = table().get(key)
    return pathlib.Path(v) if v else ABSENT / key
