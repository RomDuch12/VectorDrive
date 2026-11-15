"""Modèles de dessin (« Ouvrir / Enregistrer modèle » de TypeEdit) : un
dessin de départ — plaque, cartouche, repères, textes à compléter — enregistré
sous un nom ; « Nouveau d'après un modèle » en ouvre une copie sans nom.

Modèles de l'utilisateur : fichiers VDZ du dossier `modeles_dessin` des
données (`VECTORDRIVE_DOC_TEMPLATES` pour les essais) ; ceux des plugins :
`api.add_templates('dessin', {nom: chemin})` ; ceux du TypeEdit installé
sur le poste (`.vnm` du dossier Models, lus comme des VND ;
`VECTORDRIVE_NO_TYPEEDIT=1` les ignore).
"""
from __future__ import annotations

import os
import pathlib
import re

KIND = 'dessin'


def user_dir() -> pathlib.Path:
    env = os.environ.get('VECTORDRIVE_DOC_TEMPLATES')
    if env:
        return pathlib.Path(env)
    from ..portable import data_dir
    return data_dir() / 'modeles_dessin'


def _file(name: str) -> pathlib.Path:
    # le nom tel quel (seuls les caractères interdits par Windows sont remplacés)
    stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', '_', name).strip(' .') or 'modele'
    return user_dir() / f'{stem}.vdz'


def typeedit_models() -> dict[str, str]:
    """Modèles du TypeEdit installé : {« TypeEdit : dossier / nom » : chemin}."""
    import glob
    if os.environ.get('VECTORDRIVE_NO_TYPEEDIT') == '1':
        return {}
    out = {}
    roots = glob.glob(os.path.join(os.environ.get('PROGRAMDATA', 'C:/ProgramData'), 'Gravotech', 'TypeEdit_*', 'Models'))
    for root in sorted(roots, reverse=True):
        for f in sorted(pathlib.Path(root).rglob('*.vnm')):
            rel = f.relative_to(root).with_suffix('')
            out.setdefault('TypeEdit : ' + ' / '.join(rel.parts), str(f))
    return out


def templates() -> dict[str, tuple[str, str]]:
    """{nom: (origine, chemin)} : TypeEdit du poste, plugins, puis
    l'utilisateur (prioritaire)."""
    from ..plugins import REGISTRY
    out = {name: ('TypeEdit', path) for name, path in typeedit_models().items()}
    for name, path in (REGISTRY.templates.get(KIND) or {}).items():
        if pathlib.Path(str(path)).is_file():
            out[str(name)] = ('plugin', str(path))
    d = user_dir()
    if d.is_dir():
        for f in sorted(d.glob('*.vdz')):
            out[f.stem] = ('utilisateur', str(f))
    return out


def save(doc, name: str) -> pathlib.Path:
    """Le dessin enregistré comme modèle (VDZ), sans sa pièce 3D, ni ses
    surfaces posées, ni le VND dont il vient (un nouveau dessin n'y est pas lié
    en douce ; un contenu de surface y est signalé, pas usiné à côté)."""
    from . import model3d, native
    from ..core import surface2d
    f = _file(name)
    f.parent.mkdir(parents=True, exist_ok=True)
    keep, extra, marks = doc.source_path, doc.extra, [(L, L.extra) for L in doc.layers]
    try:
        doc.source_path = ''
        doc.extra = {k: v for k, v in extra.items() if k not in (model3d.SOURCE_KEY, 'vnd_source', 'vnd_signature')}
        for L, e in marks:
            L.extra = {k: v for k, v in e.items() if k != surface2d.KEY}
        native.write(doc, f)
    finally:
        doc.source_path, doc.extra = keep, extra
        for L, e in marks:
            L.extra = e
    return f


def delete(name: str) -> bool:
    f = _file(name)
    if f.is_file():
        f.unlink()
        return True
    return False
