"""Onglets fermés gardés (demande du 24/11 : « Tout onglet jamais enregistré (ou modifié non enregistré) à la fermeture
l'est silencieusement dans le dossier programme pour pouvoir être réouvert (en silencieux, fichier toujours noté non
enregistré à l'ouverture), à la manière de npp »).

Un onglet modifié ou jamais enregistré qu'on ferme n'est plus proposé à l'enregistrement : son dessin (et ses parcours
calculés) est écrit ici, sans question, et revient par « Rouvrir un onglet fermé » (même après un redémarrage), toujours
noté non enregistré — à enregistrer quand on le décide. Le fichier de l'utilisateur n'est jamais écrit.

Dossier : `onglets_fermes/` des données de VectorDrive (le dossier du programme pour une version portable ;
`VECTORDRIVE_CLOSED_TABS` : un autre dossier, pour les essais). Un dessin par onglet (`<uid>.vdz`, ses parcours dans
`<uid>.vdp`) et l'index (`index.json`), le dernier fermé en tête, au plus `MAX` (les plus anciens sont oubliés, leur
dessin effacé). Un verrou : deux fenêtres ouvertes à la fois n'écrivent jamais l'index ensemble.
"""
from __future__ import annotations

import json
import os
import pathlib
import time

INDEX = 'index.json'
LOCK = 'index.lock'
#: au plus tant d'onglets gardés
MAX = 25
#: attente du verrou (ms) ; au-delà : OSError, la fermeture repose la question
LOCK_MS = 5000


def folder() -> pathlib.Path:
    if os.environ.get('VECTORDRIVE_CLOSED_TABS'):
        return pathlib.Path(os.environ['VECTORDRIVE_CLOSED_TABS'])
    from ..portable import data_dir
    return data_dir() / 'onglets_fermes'


class Kept:
    """Un onglet gardé : `uid` (celui de l'onglet), `file` (son dessin, dans le dossier), `paths` (ses parcours, ou
    None), `cam` (ce qu'on savait de leur calcul), `path` (le fichier dont il vient, ou None : jamais enregistré),
    `source` (le fichier importé), `title` (le nom montré), `custom` (le nom donné à l'onglet par « Renommer… », ou
    ''), `pinned` (épinglé), `when` (heure de fermeture)."""

    def __init__(self, d: dict, where: pathlib.Path):
        self.uid = str(d.get('uid') or '')
        self.file = str(d.get('file') or '')
        self.paths = d.get('paths') or None
        self.cam = d.get('cam')
        self.path = d.get('path') or None
        self.source = d.get('source') or None
        self.title = str(d.get('title') or '')
        self.custom = str(d.get('custom') or '')
        self.pinned = bool(d.get('pinned'))
        self.when = float(d.get('when') or 0.0)
        st = d.get('stamp')
        self.stamp = tuple(st) if isinstance(st, (list, tuple)) and len(st) == 2 else None
        self.where = where

    def name(self) -> str:
        if self.title:
            return self.title
        src = self.path or self.source
        return pathlib.Path(src).name if src else '?'

    def as_dict(self) -> dict:
        return {'uid': self.uid, 'file': self.file, 'paths': self.paths, 'cam': self.cam, 'path': self.path,
                'source': self.source, 'title': self.title, 'when': self.when,
                'stamp': list(self.stamp) if self.stamp else None, 'custom': self.custom, 'pinned': self.pinned}

    def __repr__(self) -> str:                           # noqa: D105
        return f'Kept({self.name()!r})'


class _Locked:
    """Le dossier tenu le temps d'une écriture (QLockFile : un verrou abandonné par une fenêtre plantée est repris)."""

    def __init__(self, d: pathlib.Path):
        self.d = d

    def __enter__(self):
        from PySide6.QtCore import QLockFile
        self.d.mkdir(parents=True, exist_ok=True)
        self.lock = QLockFile(str(self.d / LOCK))
        self.lock.setStaleLockTime(30000)
        if not self.lock.tryLock(LOCK_MS):
            raise OSError('onglets gardés : dossier tenu par une autre fenêtre')
        return self

    def __exit__(self, *exc):
        self.lock.unlock()
        return False


def _read(d: pathlib.Path, strict: bool = False) -> list[dict]:
    """L'index ; `strict` : un index présent mais illisible (tenu par un antivirus, abîmé) lève OSError — pour
    l'écrire, on ne repart jamais d'un index vide qui ferait oublier les autres onglets gardés."""
    try:
        data = json.loads((d / INDEX).read_text(encoding='utf-8'))
    except FileNotFoundError:
        return []
    except (OSError, ValueError) as ex:
        if strict:
            raise OSError(f'onglets gardés : index illisible ({ex})') from ex
        return []
    return [e for e in data if isinstance(e, dict) and e.get('uid') and e.get('file')] if isinstance(data, list) \
        else []


def _write(d: pathlib.Path, entries: list[dict]) -> None:
    tmp = d / f'{INDEX}.{os.getpid()}.tmp'
    tmp.write_text(json.dumps(entries, ensure_ascii=False, indent=1), encoding='utf-8')
    tmp.replace(d / INDEX)


def _files_of(e: dict) -> list[str]:
    return [pathlib.Path(str(x)).name for x in (e.get('file'), e.get('paths')) if x]


def entries(where: pathlib.Path | None = None) -> list[Kept]:
    """Les onglets gardés dont le dessin est là, le dernier fermé d'abord."""
    d = pathlib.Path(where) if where is not None else folder()
    out = [Kept(e, d) for e in _read(d)]
    return sorted((k for k in out if (d / pathlib.Path(k.file).name).is_file()), key=lambda k: -k.when)


def keep(tab, title: str = '', where: pathlib.Path | None = None, paths: bytes | None = None,
         cam=None, stamp=None) -> Kept:
    """Écrit le dessin de l'onglet `tab` (DocTab) — et ses parcours (`paths` : octets de `session.paths_bytes`, `cam` :
    le mémo de leur calcul ; `stamp` : (date fine, taille) de son fichier tel qu'il avait été lu, pour l'avertissement
    « changé sur le disque » à l'enregistrement) ; rend son entrée. Le même onglet gardé une seconde fois remplace le
    premier. OSError : rien n'a pu être écrit (disque plein, droits, verrou, index illisible…)."""
    from ..io import native
    d = pathlib.Path(where) if where is not None else folder()
    snap = native.snapshot(tab.doc)
    with _Locked(d):
        name = f'{tab.uid}.vdz'
        native.write_atomic(snap, d / name, level=1)
        pname = None
        if paths:
            pname = f'{tab.uid}.vdp'
            tmp = d / (pname + '.tmp')
            tmp.write_bytes(paths)
            tmp.replace(d / pname)
        else:
            (d / f'{tab.uid}.vdp').unlink(missing_ok=True)
        old = [e for e in _read(d, strict=True) if e.get('uid') != tab.uid]
        when = max([time.time()] + [float(e.get('when') or 0.0) + 1e-3 for e in old])
        k = Kept({'uid': tab.uid, 'file': name, 'paths': pname, 'cam': cam, 'path': tab.path,
                  'source': getattr(tab.doc, 'source_path', None) or None, 'title': title, 'when': when,
                  'stamp': list(stamp) if stamp else None, 'custom': getattr(tab, 'title', ''),
                  'pinned': bool(getattr(tab, 'pinned', False))}, d)
        lst = [k.as_dict()] + old
        _write(d, lst[:MAX])
        used = {n for e in lst[:MAX] for n in _files_of(e)}
        for e in lst[MAX:]:                              # les plus anciens : oubliés, leur dessin effacé
            for n in _files_of(e):
                if n not in used:
                    (d / n).unlink(missing_ok=True)
    return k


def forget(uid: str, where: pathlib.Path | None = None) -> bool:
    """L'onglet `uid` n'est plus à rendre (enregistré, ou fermé sans rien à garder) : son entrée et ses fichiers
    retirés. Rend vrai s'il y en avait une."""
    d = pathlib.Path(where) if where is not None else folder()
    if not (d / INDEX).exists():
        return False
    try:
        with _Locked(d):
            lst = _read(d)
            gone = [e for e in lst if e.get('uid') == uid]
            if not gone:
                return False
            _write(d, [e for e in lst if e.get('uid') != uid])
            for e in gone:
                for n in _files_of(e):
                    (d / n).unlink(missing_ok=True)
    except OSError:
        return False
    return True


def drop(k: Kept) -> None:
    """Retire un onglet gardé (son dessin effacé)."""
    if not forget(k.uid, k.where):
        for n in _files_of(k.as_dict()):
            (k.where / n).unlink(missing_ok=True)


def load(k: Kept):
    """Le dessin d'un onglet gardé, relu, et ses parcours — l'entrée reste (`drop` une fois l'onglet ouvert). Rend
    (Document — sa `source_path` remise —, parcours ou None), ou lève l'erreur de lecture du dessin."""
    from ..io import registry
    doc = registry.open_document(str(k.where / pathlib.Path(k.file).name))
    doc.source_path = k.source or k.path or ''
    tps = None
    if k.paths:
        from . import session
        try:
            tps = session.paths_from_bytes((k.where / pathlib.Path(k.paths).name).read_bytes())
        except Exception:                                # noqa: BLE001 — parcours abîmés : à recalculer, le dessin revient
            tps = None
    return doc, tps
