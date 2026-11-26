"""Les fenêtres de choix de fichier et de dossier retiennent le dernier chemin choisi (demande du 18/11 soir : « tout
appli : un chemin file/folder précis est retenu pour la prochaine fois »).

Toutes les fenêtres de l'application et des plugins (`QFileDialog.getOpenFileName`, `getOpenFileNames`,
`getSaveFileName`, `getExistingDirectory`) passent par ici : chacune — reconnue à l'endroit du code qui l'ouvre et à
son titre — retient le dossier où l'on a choisi. Elle y rouvre quand le code ne propose rien de précis (rien, un nom
de fichier nu, le dossier personnel ou Documents) ; un chemin que le code propose à dessein (le dossier du dessin
pour son programme, la valeur d'un champ, le dossier qu'une fenêtre retient déjà elle-même) est gardé. Une fenêtre
jamais ouverte : le dernier dossier choisi dans l'application. Un dossier disparu (clé USB) n'est pas proposé ; un
partage réseau n'est pas testé (un serveur hors d'atteinte gèlerait l'interface). F10 › Dossiers de travail : une
fenêtre qui a sa ligne (son départ rendu par `workdirs.start_folder` ou `program_dir`, noté par `workdirs.issue`)
garde ce départ s'il est son dossier fixé ou son dernier utilisé encore là (même Documents ou le Bureau) ; « Autres
fenêtres de fichiers » fixé ne vaut que pour les fenêtres sans ligne, quand elles ne proposent rien de précis (un
dossier fixé sur un partage : attente de `workdirs.REMOTE_WAIT` au plus la première fois).

    from . import pathmemory
    pathmemory.install()          # une fois, au lancement
"""
from __future__ import annotations

import hashlib
import os
import pathlib
import sys

from PySide6.QtWidgets import QFileDialog

#: les réglages : « chemins_retenus/<fenêtre> » et « chemins_retenus/dernier »
PREFIX = 'chemins_retenus/'
LAST = PREFIX + 'dernier'
#: les fonctions de Qt remplacées : genre → nom
_KINDS = {'open': 'getOpenFileName', 'open_many': 'getOpenFileNames', 'save': 'getSaveFileName',
          'dir': 'getExistingDirectory'}


def _settings():
    from ..portable import settings
    return settings()


def key_of(kind: str, caption: str, frame) -> str:
    """La fenêtre : l'endroit du code qui l'ouvre (module avec son paquet, fonction), son genre et son titre."""
    code = frame.f_code if frame is not None else None
    if code is None:
        where = '?'
    else:
        mod = (getattr(frame, 'f_globals', None) or {}).get('__name__') or pathlib.Path(code.co_filename).stem
        where = f"{mod}.{getattr(code, 'co_qualname', code.co_name)}"
    return hashlib.sha1(f'{where}|{kind}|{caption}'.encode('utf-8')).hexdigest()[:16]


def _remote(path) -> bool:
    """Un partage réseau (\\\\serveur\\…, ou une lettre de lecteur réseau) : on ne le teste pas — un serveur hors
    d'atteinte gèlerait l'interface le temps du délai du réseau ; la fenêtre de Qt s'en charge."""
    p = str(path or '').replace('/', '\\')
    if p.startswith('\\\\'):
        return True
    if sys.platform == 'win32' and len(p) >= 2 and p[1] == ':':
        try:
            import ctypes
            return ctypes.windll.kernel32.GetDriveTypeW(p[:2] + '\\') == 4      # DRIVE_REMOTE
        except Exception:                                # noqa: BLE001
            return False
    return False


def _exists(path, folder_only: bool = True) -> bool:
    if not path:
        return False
    if _remote(path):
        return True
    try:
        return os.path.isdir(str(path)) if folder_only else os.path.exists(str(path))
    except (OSError, ValueError):
        return False


def _usable(folder) -> bool:
    return _exists(folder)


def _generic(path) -> bool:
    """Un dossier « par défaut » que le code propose faute de mieux (dossier personnel, Documents, Bureau, dossier
    courant) : le dossier retenu passe devant."""
    try:
        p = os.path.normcase(os.path.abspath(str(path))).rstrip('\\/')
        home = pathlib.Path.home()
        places = (home, home / 'Documents', home / 'Desktop', home / 'Bureau', pathlib.Path.cwd())
        return p in {os.path.normcase(str(x)).rstrip('\\/') for x in places}
    except (OSError, ValueError):
        return False


def _deliberate(given: str, kind: str) -> bool:
    """Le chemin que le code propose est-il voulu (le dossier du dessin, la valeur d'un champ, le nom calculé d'un
    programme dans son dossier) ? Oui s'il existe, ou son dossier — sauf un dossier générique ; un partage réseau :
    oui, sans le tester."""
    if not given:
        return False
    if _remote(given):
        return True
    if _exists(given, folder_only=False):
        return os.path.isfile(given) or not _generic(given)
    parent = os.path.dirname(given.rstrip('\\/'))
    if kind == 'dir' or not parent:
        return False                                     # un nom de fichier nu : à poser dans le dossier retenu
    return _exists(parent) and not _generic(parent)


def remembered(key: str, settings=None) -> str:
    """Le dossier retenu pour cette fenêtre, '' : aucun (ou disparu)."""
    st = settings or _settings()
    v = str(st.value(PREFIX + key, '') or '')
    return v if _usable(v) else ''


def propose(key: str, given: str, kind: str, settings=None) -> str:
    """Le chemin à proposer. Celui que le code propose à dessein (`_deliberate`) est gardé. Sinon (rien, un nom de
    fichier nu, un dossier générique, un dossier disparu) : le dossier retenu pour cette fenêtre, avec le nom de
    fichier proposé ; sinon le dernier dossier choisi dans l'application ; sinon ce que le code propose."""
    st = settings or _settings()
    given = str(given or '')
    from . import workdirs
    usage, how, folder = workdirs.issued(given)          # une fenêtre qui a sa ligne dans les dossiers de travail
    if usage is not None:
        if how == workdirs.FIXED and workdirs.is_fixed_path(st, given, usage):
            return given                                 # son dossier fixé (même Documents) : tel quel
        if how == workdirs.LAST and _exists(folder):
            return given                                 # son dernier utilisé encore là (même le Bureau) : tel quel
                                                         # (supprimé : le dossier retenu, plus bas)
    if _deliberate(given, kind):
        return given
    last = (workdirs.fixed_folder(st, 'autres') if usage is None else '') or remembered(key, st)
    if not last:
        anywhere = str(st.value(LAST, '') or '')
        last = anywhere if _usable(anywhere) else ''
    if not last:
        return given
    if not given or kind == 'dir' or os.path.isdir(given):
        return last
    name = pathlib.Path(given).name                      # un nom de fichier proposé : gardé, dans le dossier retenu
    return str(pathlib.Path(last) / name) if name else last


def remember(key: str, result, kind: str, settings=None) -> str:
    """Le dossier du chemin choisi retenu pour cette fenêtre et comme dernier dossier ; rend ce dossier ('' : rien
    choisi)."""
    if kind == 'dir':
        path = result if isinstance(result, str) else ''
    elif kind == 'open_many':
        files = result[0] if isinstance(result, tuple) else result
        path = files[0] if files else ''
    else:
        path = result[0] if isinstance(result, tuple) else result
    path = str(path or '')
    if not path:
        return ''
    folder = path if kind == 'dir' else str(pathlib.Path(path).parent)
    if not _usable(folder):
        return ''
    st = settings or _settings()
    st.setValue(PREFIX + key, folder)
    st.setValue(LAST, folder)
    return folder


def _wrap(kind: str, orig):
    def chooser(*args, **kw):
        args = list(args)

        def get(i, name):
            return args[i] if len(args) > i else kw.get(name, '')

        def put(i, name, v):
            if len(args) > i:
                args[i] = v
            else:
                kw[name] = v
        caption = str(get(1, 'caption') or '')
        key = key_of(kind, caption, sys._getframe(1))
        try:
            st = _settings()
            put(2, 'dir', propose(key, str(get(2, 'dir') or ''), kind, st))
        except Exception:                                # noqa: BLE001 — sans réglages : la fenêtre telle quelle
            st = None
        result = chooser.vd_orig(*args, **kw)
        if st is not None:
            try:
                remember(key, result, kind, st)
            except Exception:                            # noqa: BLE001
                pass
        return result
    chooser.vd_pathmemory = True
    chooser.vd_orig = orig                               # chaque enveloppe garde la sienne (un essai qui remet une
                                                         # enveloppe après un faux ne laisse pas ce faux derrière lui)
    chooser.__doc__ = f'QFileDialog.{_KINDS[kind]} qui retient le dernier dossier (voir vectordrive.ui.pathmemory).'
    return chooser


def install() -> bool:
    """Les fenêtres de choix de fichier de Qt remplacées par celles qui retiennent le chemin (une seule fois) ; rend
    vrai si elles le sont."""
    for kind, name in _KINDS.items():
        cur = getattr(QFileDialog, name)
        if getattr(cur, 'vd_pathmemory', False):
            continue
        setattr(QFileDialog, name, staticmethod(_wrap(kind, cur)))
    return installed()


def uninstall() -> None:
    """Les fenêtres de Qt d'origine remises (essais)."""
    for name in _KINDS.values():
        cur = getattr(QFileDialog, name)
        if getattr(cur, 'vd_pathmemory', False):
            setattr(QFileDialog, name, staticmethod(cur.vd_orig))


def original(kind: str):
    """La fonction qu'enveloppe la fenêtre de ce genre (None : pas posée)."""
    return getattr(getattr(QFileDialog, _KINDS[kind]), 'vd_orig', None)


def installed() -> bool:
    return all(getattr(getattr(QFileDialog, n), 'vd_pathmemory', False) for n in _KINDS.values())
