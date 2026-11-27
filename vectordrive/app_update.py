"""Mise à jour de l'application par un dossier de versions (demande du 24/11 : « Bouton maj App trouve la dernière
(par défaut dans P:\\Partage\\LOGICIEL\\) copie le zip dans mes documents, dézippe, quitte l'app en cours et charge la
nouvelle en reprenant ou non ses param et éventuellement met à jour le raccourci barre des tâches / menu Démarrer »).
Demande du 26/11 : « Ne pas supprimer de versions antérieures automatiquement » — aucune ancienne version n'est
jamais supprimée : chacune reste, avec son dossier.

Le « dossier VD » (réglage `maj/dossier_vd`, d'office `Documents/VectorDrive`) tient une version par sous-dossier :

    <dossier VD>/
        zips/VectorDrive-1.14.0-portable.zip        l'archive copiée
        VectorDrive-1.14.0/                         la version (marque `.vd_version.json`)
            VectorDrive/VectorDrive.exe, VectorDrive.ini, donnees/…
        VectorDrive-1.13.0/                         les précédentes, toujours là

Ce module est la logique seule, sans interface : tout passe par ses paramètres (dossiers, lanceur, sonde du canal
d'instance, `runner` des raccourcis), ce qui le laisse essayer dans des dossiers temporaires. `MainWindow.app_update`
l'enchaîne.

Règles de sûreté : la mise à jour n'efface que ses propres dossiers provisoires (`.vd_installation_…`, marqués dès
leur création, enfants directs du dossier VD, chemins résolus), la copie abîmée d'une archive dans `zips/` (une autre
archive de même nom y est mise de côté, jamais effacée) et, dans la nouvelle version, le sous-dossier d'onglets
qu'elle y a écrit (`donnees/session_maj/…`), une fois rouvert ou si cette version n'a pas démarré ; un lien
ou une jonction n'est jamais suivi ; un dossier de ce nom qui ne porte pas la marque `.vd_version.json`, ou dont le
nom n'est pas celui de sa marque, n'est jamais repris ni écrasé ; un dossier VD qui serait la racine d'un lecteur, le
dossier de l'utilisateur, ses Documents, son Bureau, ses Téléchargements, la racine de OneDrive ou le dossier où
chercher est refusé (`unsafe_root`). Aucun droit d'administrateur, rien dans le registre. `VECTORDRIVE_APP_UPDATE`
(essais) : dossier qui remplace Documents, le dossier où chercher et ceux des raccourcis — PowerShell, le lanceur et
la sonde d'office s'y refusent alors.
"""
from __future__ import annotations

import base64
import datetime
import filecmp
import json
import os
import pathlib
import re
import shutil
import stat
import subprocess
import sys
import time
import zipfile
import zlib
from typing import NamedTuple

from .core import progress as P
from .i18n import tr
from .portable import ADOPTED_KEY, DATA, INI, NOT_ADOPTED
from .update import parse_version

#: où chercher la dernière version, d'office (la demande) ; réglage F10 › Mises à jour
DEFAULT_SOURCE = 'P:\\Partage\\LOGICIEL'
SOURCE_KEY, FOLDER_KEY = 'maj/dossier_source', 'maj/dossier_vd'
#: essais : dossier qui tient lieu de Documents (`versions`), de dossier où chercher (`source`) et de dossiers des
#: raccourcis (`raccourcis`) ; rien n'est alors lancé pour de vrai
ENV = 'VECTORDRIVE_APP_UPDATE'
#: fichier qui signe « dossier créé par cette mise à jour » : sans lui, un dossier n'est jamais repris ni effacé
MARK = '.vd_version.json'
#: attente (s), d'office, de la nouvelle version sur le canal d'instance unique
START_TIMEOUT = 30.0
#: suffixe de la copie de secours d'un fichier de la nouvelle version remplacé par la reprise
BACKUP = '.avant_reprise'
#: suffixe d'une archive de `zips/` mise de côté parce qu'une autre, de même nom, la remplace
ASIDE = '.ancienne'
#: suffixe d'un fichier en cours d'écriture : il ne remplace le vrai (`os.replace`) qu'une fois complet
PART = '.vd_copie'
LIBRARY = 'bibliotheque'
ZIPS = 'zips'
EXE = 'VectorDrive.exe'
#: les onglets passés par une mise à jour (relecture du 26/11) : un sous-dossier par passage dans `donnees/session_maj`
#: de la nouvelle version — jamais sa propre session (`donnees/session`), qui peut tenir ses dessins non enregistrés
HANDOVER_DIR = DATA + '/session_maj'
#: dans un passage : le nombre de réouvertures tentées (un plantage pendant la réouverture ne boucle pas)
TRIES = 'tentatives.txt'
MAX_TRIES = 2
#: suffixe de l'index d'un passage rouvert en entier (renommé d'un coup : il ne sera plus jamais rouvert)
DONE = '.rouvert'
#: témoin d'un passage rouvert en entier : un fichier neuf, écrit avant tout (l'index peut être verrouillé)
WITNESS = 'rouvert'
#: dossiers de `donnees` jamais repris : récupération, et les sessions — les onglets passent par `HANDOVER_DIR`
#: (copier la session de l'ancienne version mélangerait ses dessins à ceux qu'une version déjà là aurait gardés)
NOT_CARRIED = (*NOT_ADOPTED, 'session', 'session_maj')
#: préfixe du dossier de travail d'une décompression en cours, dans le dossier VD
STAGING = '.vd_installation_'
VERSION_RE = r'\d+\.\d+\.\d+'
ZIP_RE = re.compile(rf'^VectorDrive(?:-(?P<ed>[^\\/:]+?))?-(?P<v>{VERSION_RE})-portable\.zip$', re.IGNORECASE)
DIR_RE = re.compile(rf'^VectorDrive(?:-(?P<ed>[^\\/:]+?))?-(?P<v>{VERSION_RE})(?:-portable)?$', re.IGNORECASE)
_BAD_NAME = re.compile(r'[\\/:*?"<>|]')
#: une archive qui se dit de VectorDrive sans avoir le nom d'une archive portable (« …-portable (1).zip »)
_ODD = re.compile(r'^VectorDrive.*\.zip$', re.IGNORECASE)
#: entrées d'une archive jamais décompressées : la marque ne vient que de cette mise à jour
_RESERVED = {n.lower() for n in (MARK, 'VectorDrive/' + MARK)}


class AppUpdateError(Exception):
    """Mise à jour impossible : le texte est montré tel quel."""


class Found(NamedTuple):
    """Une archive portable trouvée : (chemin, version, édition — vide : sans édition)."""
    path: pathlib.Path
    version: str
    edition: str = ''


class Installed(NamedTuple):
    """Une version en place dans le dossier VD ; `reused` : elle y était déjà."""
    folder: pathlib.Path
    exe: pathlib.Path
    version: str
    edition: str
    reused: bool


class Book(NamedTuple):
    """Le carnet de clients du BAT d'une reprise (`carry_book`) : `added`, les clients ajoutés, dont `logos` avec leur
    logo ; `kept`, ceux déjà là, gardés tels quels ; `chosen`, le dossier choisi par l'ancienne version (rien n'est
    alors copié) ; `shared`, le dossier choisi ici, où rien n'est versé d'office, et `waiting`, les clients de
    l'ancienne alors laissés chez elle ; `replaced`, la copie de secours (« fichier → copie ») ; `failed`."""
    added: int = 0
    logos: int = 0
    kept: int = 0
    chosen: str = ''
    shared: str = ''
    waiting: int = 0
    replaced: list = []
    failed: list = []


class Carried(NamedTuple):
    """La reprise : `copied`, le nombre de fichiers copiés ; `failed`, ceux qui n'ont pas pu l'être (« chemin :
    raison ») ; `skipped`, ceux que la nouvelle version avait déjà, différents, et qu'elle garde ; `files`, la liste
    [chemin relatif au dossier de l'application, taille, date en ns] des fichiers de l'ancienne version repris tels
    quels (copiés, ou déjà là à l'identique). `failed` ou `skipped` non vide : la reprise n'est pas complète, et
    c'est dit (l'ancienne version, elle, reste toujours, avec ses fichiers). `book` : le carnet de clients du BAT
    (`carry_book` ; ses échecs sont aussi dans `failed`)."""
    copied: int
    failed: list
    skipped: list
    files: list
    book: Book = Book()


# --- dossiers ---------------------------------------------------------------------------------------------------
def _setting(settings, key: str) -> str:
    return str(settings.value(key, '') or '').strip() if settings is not None else ''


def default_versions_dir() -> pathlib.Path:
    """Le dossier VD d'office : « VectorDrive » dans les Documents de l'utilisateur."""
    forced = os.environ.get(ENV)
    if forced:
        return pathlib.Path(forced) / 'versions'
    docs = ''
    try:
        from PySide6.QtCore import QStandardPaths
        docs = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
    except Exception:                                    # noqa: BLE001 — sans Qt : le dossier habituel
        pass
    return pathlib.Path(docs or pathlib.Path.home() / 'Documents') / 'VectorDrive'


def versions_dir(settings=None) -> pathlib.Path:
    """Le « dossier VD » : celui des versions de VectorDrive (réglage `maj/dossier_vd` ; vide : celui d'office)."""
    v = _setting(settings, FOLDER_KEY)
    return pathlib.Path(v) if v else default_versions_dir()


def source_dir(settings=None) -> pathlib.Path:
    """Le dossier où chercher la dernière version (réglage `maj/dossier_source` ; vide : celui d'office, qu'un plugin
    peut changer)."""
    v = _setting(settings, SOURCE_KEY)
    forced = os.environ.get(ENV)
    if forced and (not v or v.rstrip('\\/').lower() == DEFAULT_SOURCE.lower()):
        return pathlib.Path(forced) / 'source'           # essais : jamais le vrai lecteur
    if v:
        return pathlib.Path(v)
    from .plugins import default
    return pathlib.Path(str(default('options', SOURCE_KEY, DEFAULT_SOURCE) or DEFAULT_SOURCE))


def folder_name(version: str, edition: str = '') -> str:
    return f'VectorDrive{"-" + edition if edition else ""}-{version}'


def zip_name(version: str, edition: str = '') -> str:
    return folder_name(version, edition) + '-portable.zip'


def version_folder(root, version: str, edition: str = '') -> pathlib.Path:
    """Le sous-dossier du dossier VD où vit cette version."""
    return pathlib.Path(root) / folder_name(version, edition)


def exe_of(folder) -> pathlib.Path | None:
    """L'exécutable d'une version décompressée (l'archive contient un dossier VectorDrive/, ou les fichiers)."""
    for cand in (pathlib.Path(folder) / 'VectorDrive' / EXE, pathlib.Path(folder) / EXE):
        if cand.is_file():
            return cand
    return None


def _norm(p) -> str:
    return os.path.normcase(os.path.abspath(str(p)))


def _real(p) -> str:
    return os.path.normcase(str(pathlib.Path(p).resolve()))


def _is_link(p) -> bool:
    """Lien symbolique ou jonction : jamais suivi, jamais pris pour un dossier à nous."""
    return os.path.islink(p) or bool(getattr(os.path, 'isjunction', lambda _p: False)(p))


def _child_of(folder, root) -> bool:
    """`folder` est un enfant direct de `root`, chemins résolus (ni lien ni « .. » ne font sortir du dossier)."""
    try:
        return _real(pathlib.Path(folder).resolve().parent) == _real(root)
    except OSError:
        return False


def special_dirs() -> list[pathlib.Path]:
    """Les dossiers de l'utilisateur qui ne peuvent pas être eux-mêmes le dossier VD — seulement l'un de leurs
    sous-dossiers : Documents, Bureau, Téléchargements (là où Windows les place, même redirigés sur le réseau ou dans
    OneDrive, et à leur place habituelle), la racine de OneDrive (personnel ou professionnel)."""
    home = pathlib.Path.home()
    out = [home / 'Documents', home / 'Desktop', home / 'Downloads', home / 'OneDrive']
    try:
        from PySide6.QtCore import QStandardPaths as S
        for loc in (S.StandardLocation.DocumentsLocation, S.StandardLocation.DesktopLocation,
                    S.StandardLocation.DownloadLocation):
            v = S.writableLocation(loc)
            if v:
                out.append(pathlib.Path(v))
    except Exception:                                    # noqa: BLE001 — sans Qt : les places habituelles
        pass
    for key in ('OneDrive', 'OneDriveConsumer', 'OneDriveCommercial'):
        v = os.environ.get(key, '').strip()
        if v:
            out.append(pathlib.Path(v))
    return out


def unsafe_root(root, source=None, special=None) -> str:
    """Pourquoi ce dossier ne peut pas être le dossier VD ('' : il le peut) : racine d'un lecteur (ou d'un partage),
    dossier de l'utilisateur, l'un de `special` (d'office `special_dirs()` : Documents, Bureau, Téléchargements,
    racine de OneDrive — un de leurs sous-dossiers convient), dossier où chercher la dernière version (chemins
    résolus)."""
    try:
        p = pathlib.Path(root).resolve()
        home = _real(pathlib.Path.home())
    except (OSError, RuntimeError) as ex:
        return tr('Dossier VD inutilisable : {0}').format(f'{root} ({ex})')
    if p.parent == p:
        return tr('Dossier VD refusé : {0} est la racine d’un lecteur ; choisir un sous-dossier (F10 › Mises à '
                  'jour).').format(p)
    if _real(p) == home:
        return tr('Dossier VD refusé : {0} est votre dossier personnel ; choisir un sous-dossier (F10 › Mises à '
                  'jour).').format(p)
    for s in (special_dirs() if special is None else special):
        try:
            hit = _real(s) == _real(p)
        except (OSError, RuntimeError):
            hit = False
        if hit:
            return tr('Dossier VD refusé : {0} est l’un de vos dossiers (Documents, Bureau, Téléchargements, '
                      'OneDrive) ; choisir un sous-dossier, par exemple {1} (F10 › Mises à jour).').format(
                          p, p / 'VectorDrive')
    try:
        same = source is not None and _real(p) == _real(source)
    except (OSError, RuntimeError):
        same = False
    if same:
        return tr('Dossier VD refusé : {0} est aussi le dossier où chercher la dernière version.').format(p)
    return ''


# --- chercher ---------------------------------------------------------------------------------------------------
def scan(source, odd: list | None = None) -> list[Found]:
    """Les archives portables `VectorDrive{-édition}-X.Y.Z-portable.zip` du dossier et de ses sous-dossiers directs
    (pas plus loin). Dossier injoignable : `AppUpdateError`. À appeler dans un fil (un partage absent fait attendre).
    `odd` : y sont ajoutés les noms des archives `VectorDrive….zip` ignorées parce que leur nom n'a pas cette forme
    (« … (1).zip », copie renommée), pour le dire."""
    src = pathlib.Path(source)
    try:
        with os.scandir(src) as it:
            entries = list(it)
    except OSError as ex:
        raise AppUpdateError(tr('Dossier où chercher la dernière version injoignable : {0}').format(
            f'{src} ({ex.strerror or ex})')) from ex
    out: list[Found] = []

    def take(e) -> None:
        m = ZIP_RE.match(e.name)
        if m and e.is_file():
            out.append(Found(pathlib.Path(e.path), m['v'], m['ed'] or ''))
        elif odd is not None and _ODD.match(e.name) and e.is_file():
            odd.append(e.name)

    for e in entries:
        P.check()
        try:
            if e.is_dir():
                with os.scandir(e.path) as sub:
                    for f in sub:
                        take(f)
            else:
                take(e)
        except OSError:                                  # sous-dossier illisible : les autres comptent
            continue
    return out


def latest_of(found, edition: str | None = None) -> Found | None:
    """La plus récente (versions comparées en nombres : 1.10.0 > 1.9.0) des archives de l'édition demandée — vide ou
    None : celles sans édition. Jamais une autre édition que celle de l'application en cours : un plugin d'édition
    ne s'ajoute ni ne se perd par une mise à jour. À version égale, la moins enfouie."""
    ed = (edition or '').lower()
    same = [f for f in found if f.edition.lower() == ed]
    return max(same, key=lambda f: (parse_version(f.version), -len(f.path.parts)), default=None)


def find_latest(source, edition: str | None = None) -> Found | None:
    """(chemin, version, édition) de la dernière archive portable de `source` pour cette édition, ou None."""
    return latest_of(scan(source), edition)


def current_edition(app_dir=None, manifest: str = '') -> str:
    """L'édition de l'application en cours : celle de la marque de son dossier, sinon celle du nom de son dossier
    (`VectorDrive-XXX-1.2.3`, tel que décompressé), sinon celle du manifeste de mise à jour que suit son plugin
    (`vectordrive-xxx-latest.json`) ; vide : sans édition."""
    if app_dir is not None:
        folders = (pathlib.Path(app_dir), pathlib.Path(app_dir).parent)
        for d in folders:
            info = read_mark(d)
            if info and info['edition']:
                return info['edition']
        for d in folders:
            m = DIR_RE.match(d.name)
            if m and m['ed']:
                return m['ed']
    m = re.match(r'^vectordrive-(.+)-latest\.json$', manifest or '', re.IGNORECASE)
    return m[1] if m else ''


# --- installer --------------------------------------------------------------------------------------------------
def read_mark(folder) -> dict | None:
    """La marque d'un dossier de version (version, édition, date, origine), ou None : pas de marque, ou illisible."""
    try:
        d = json.loads((pathlib.Path(folder) / MARK).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    if not isinstance(d, dict) or not re.fullmatch(VERSION_RE, str(d.get('version', ''))):
        return None
    ed = str(d.get('edition', '') or '')
    if _BAD_NAME.search(ed):
        return None
    return {**d, 'version': str(d['version']), 'edition': ed}


def version_of_app(app_dir) -> tuple[pathlib.Path, dict] | None:
    """(dossier de version, marque) quand le dossier d'application `app_dir` est celui d'une version marquée (son
    exécutable dans `VectorDrive/` ou à la racine du dossier de version) ; None sinon."""
    if app_dir is None:
        return None
    app = pathlib.Path(app_dir)
    for cand in (app.parent, app):
        info = read_mark(cand)
        exe = exe_of(cand) if info is not None else None
        if exe is not None and _norm(exe.parent) == _norm(app):
            return cand, info
    return None


def _write_json(path: pathlib.Path, data: dict) -> None:
    """Écrit un petit fichier JSON d'un coup : sous un nom provisoire, puis `os.replace` (jamais à moitié)."""
    part = path.with_name(path.name + PART)
    try:
        part.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding='utf-8')
        os.replace(part, path)
    except BaseException:
        part.unlink(missing_ok=True)
        raise


def _report(fraction: float, text: str = '') -> None:
    P.check()
    t = P.current()
    if t is not None:
        t.report(fraction, text or None)


def _entries(path) -> list | None:
    """Le contenu d'une archive (nom, taille, CRC de chaque entrée), ou None : illisible."""
    try:
        with zipfile.ZipFile(path) as z:
            return sorted((i.filename, i.file_size, i.CRC) for i in z.infolist())
    except (OSError, ValueError, zipfile.BadZipFile, zlib.error, EOFError):
        return None


def _same_archive(a: pathlib.Path, b: pathlib.Path) -> bool:
    """`b` est déjà une copie de `a` : même taille, archive lisible, mêmes entrées (noms, tailles, CRC)."""
    try:
        if not b.is_file() or _is_link(b) or b.stat().st_size != a.stat().st_size:
            return False
    except OSError:
        return False
    mine = _entries(b)
    return mine is not None and mine == _entries(a)


def _copy_archive(src: pathlib.Path, dst: pathlib.Path) -> None:
    """L'archive copiée par morceaux (avancement, annulation), sous un nom provisoire ; sa taille est vérifiée. Un
    fichier de ce nom déjà dans `zips/` n'est repris que s'il est la même archive (`_same_archive`) ; sinon il est mis
    de côté sous un autre nom (`….ancienne`, `….ancienne2`…), jamais effacé (relecture du 26/11)."""
    size = src.stat().st_size
    if _norm(src) == _norm(dst) or _same_archive(src, dst):     # cherchée dans ce dossier même, ou déjà copiée
        return
    part = dst.with_name(dst.name + '.part')
    done = 0
    try:
        with open(src, 'rb') as fi, open(part, 'wb') as fo:
            while True:
                chunk = fi.read(1 << 20)
                if not chunk:
                    break
                fo.write(chunk)
                done += len(chunk)
                _report(0.5 * done / max(1, size), tr('Copie de l’archive'))
        if part.stat().st_size != size:
            raise AppUpdateError(tr('Copie incomplète de {0} : mise à jour arrêtée.').format(src.name))
        if os.path.lexists(dst):                         # une autre archive de ce nom : gardée, à côté
            aside, i = dst.with_name(dst.name + ASIDE), 1
            while os.path.lexists(aside):
                i += 1
                aside = dst.with_name(f'{dst.name}{ASIDE}{i}')
            os.replace(dst, aside)
        os.replace(part, dst)
    except BaseException:
        part.unlink(missing_ok=True)
        raise


def check_archive(z: zipfile.ZipFile) -> None:
    """Refuse une archive piégée ou incomplète : entrée à chemin absolu, à lecteur, à « .. », lien symbolique ;
    `VectorDrive.exe` absent ; `VectorDrive.ini` absent à côté de lui (relecture du 26/11 : la version ne serait pas
    portable — ses réglages et les onglets passés ne seraient jamais lus)."""
    names = set()
    for info in z.infolist():
        name = info.filename.replace('\\', '/')
        if name.startswith('/') or re.match(r'^[A-Za-z]:', name) or '..' in name.split('/') \
                or stat.S_ISLNK(info.external_attr >> 16):
            raise AppUpdateError(tr('Archive refusée : entrée « {0} » hors du dossier.').format(info.filename))
        names.add(name.lower())
    where = next((d for d in ('vectordrive/', '') if f'{d}{EXE}'.lower() in names), None)
    if where is None:
        raise AppUpdateError(tr('Archive refusée : VectorDrive.exe n’y est pas.'))
    if f'{where}{INI}'.lower() not in names:
        raise AppUpdateError(tr('Archive refusée : VectorDrive.ini n’y est pas à côté de VectorDrive.exe (la version '
                                'ne serait pas portable).'))


def _rename(src: pathlib.Path, dst: pathlib.Path) -> None:
    """Renomme un dossier ; quelques essais (un antivirus tient parfois un fichier tout juste écrit)."""
    for attempt in range(4):
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            if attempt == 3:
                raise
            time.sleep(0.5)


def install(zip_path, versions_dir, *, version: str | None = None, edition: str | None = None,
            special=None) -> Installed:
    """Met la version de l'archive en place dans le dossier VD : l'archive copiée dans `zips/` (taille vérifiée),
    vérifiée (`check_archive`), décompressée dans un dossier provisoire marqué dès sa création (sans la marque
    qu'elle contiendrait), marquée (`.vd_version.json`), puis le dossier renommé
    `VectorDrive{-édition}-{version}`. La version y est déjà, complète et marquée : elle est reprise telle quelle ; un
    dossier de ce nom sans la marque n'est pas à nous : refus, jamais écrasé. Annulable (`core.progress`) : rien
    d'à moitié fait ne reste. `special` : les dossiers de l'utilisateur de `unsafe_root`, calculés dans le fil de
    l'interface (d'office : `special_dirs()`)."""
    src = pathlib.Path(zip_path)
    root = pathlib.Path(versions_dir)
    problem = unsafe_root(root, special=special)
    if problem:
        raise AppUpdateError(problem)
    m = ZIP_RE.match(src.name)
    version = version or (m['v'] if m else '')
    if edition is None:
        edition = (m['ed'] or '') if m else ''
    if not re.fullmatch(VERSION_RE, version) or _BAD_NAME.search(edition):
        raise AppUpdateError(tr('Archive sans numéro de version : {0}').format(src.name))
    dest = version_folder(root, version, edition)
    if os.path.lexists(dest):
        exe, there = exe_of(dest), read_mark(dest)
        if exe is None or _is_link(dest) or there is None or not named_as_marked(dest, there):
            raise AppUpdateError(tr('Le dossier {0} existe déjà et ne vient pas de cette mise à jour : le renommer ou '
                                    'le supprimer, puis recommencer.').format(dest))
        return Installed(dest, exe, version, edition, True)
    zips = root / ZIPS
    try:
        if _is_link(zips):
            raise OSError(tr('« zips » est un lien'))
        zips.mkdir(parents=True, exist_ok=True)
    except OSError as ex:
        raise AppUpdateError(tr('Dossier VD inutilisable : {0}').format(f'{root} ({ex.strerror or ex})')) from ex
    kept = zips / zip_name(version, edition)
    _copy_archive(src, kept)
    stage = root / (STAGING + dest.name)
    if os.path.lexists(stage):                           # reste d'une installation interrompue
        if _is_link(stage) or read_mark(stage) is None:
            raise AppUpdateError(tr('Le dossier provisoire {0} ne porte pas la marque de cette mise à jour : le '
                                    'supprimer à la main, puis recommencer.').format(stage))
        _remove_tree(stage, root)
    mark = {'version': version, 'edition': edition, 'date': datetime.datetime.now().isoformat(timespec='seconds'),
            'source': str(src), 'zip': kept.name}
    try:
        with zipfile.ZipFile(kept) as z:
            check_archive(z)
            infos = [i for i in z.infolist() if i.filename.replace('\\', '/').lower() not in _RESERVED]
            total = max(1, sum(i.file_size for i in infos))
            done = 0
            stage.mkdir()
            _write_json(stage / MARK, {**mark, 'etat': 'installation'})   # à nous dès sa création
            for info in infos:
                z.extract(info, stage)
                done += info.file_size
                _report(0.5 + 0.5 * done / total, tr('Décompression'))
        if exe_of(stage) is None:
            raise AppUpdateError(tr('Archive refusée : VectorDrive.exe n’y est pas.'))
        _write_json(stage / MARK, mark)
        P.check()                                        # dernier moment pour renoncer
        _rename(stage, dest)
    except (zipfile.BadZipFile, zlib.error, EOFError) as ex:     # archive abîmée (copie tronquée, CRC, flux coupé)
        _discard(stage, root)
        if _norm(kept) != _norm(src):
            kept.unlink(missing_ok=True)                 # copie abîmée : à refaire la prochaine fois
        raise AppUpdateError(tr('Archive illisible : {0}').format(f'{src.name} ({ex})')) from ex
    except BaseException:
        _discard(stage, root)
        raise
    return Installed(dest, exe_of(dest), version, edition, False)


def _writable(func, path, _exc) -> None:
    """Fichier en lecture seule : rendu modifiable, puis effacé."""
    os.chmod(path, stat.S_IWRITE)
    func(path)


def _remove_tree(folder: pathlib.Path, root) -> None:
    """Efface un dossier provisoire du dossier VD : enfant direct, jamais un lien, toujours marqué."""
    if _is_link(folder) or not _child_of(folder, root) or read_mark(folder) is None:
        raise AppUpdateError(tr('Dossier hors du dossier VD : {0}').format(folder))
    shutil.rmtree(folder, onexc=_writable)               # ne suit ni lien ni jonction


def _discard(stage: pathlib.Path, root) -> None:
    """Le dossier provisoire d'une installation qui n'aboutit pas : effacé s'il est marqué, ou s'il est vide."""
    try:
        if not os.path.lexists(stage):
            return
        if read_mark(stage) is None and not _is_link(stage):
            stage.rmdir()                                # vide seulement (rien d'écrit encore) ; sinon : laissé
        else:
            _remove_tree(stage, root)
    except (OSError, AppUpdateError):
        pass


def named_as_marked(folder, info: dict) -> bool:
    """Le nom du dossier est celui que `install` donne à la version de sa marque (`folder_name`), ou ce nom précédé
    du préfixe d'une installation en cours : une copie (« … - Copie », « …(2) ») ou un dossier renommé à la main n'est
    jamais pris pour cette version, même s'il porte la marque."""
    want = folder_name(info['version'], info['edition']).lower()
    return pathlib.Path(folder).name.lower() in (want, STAGING.lower() + want)


# --- onglets passés à la nouvelle version (relecture du 26/11) -----------------------------------------------------
def handover_root(app_dir) -> pathlib.Path:
    """Le dossier des onglets passés par les mises à jour, dans le dossier d'application d'une version portable."""
    return pathlib.Path(app_dir).joinpath(*HANDOVER_DIR.split('/'))


def new_handover(app_dir) -> pathlib.Path:
    """Un sous-dossier neuf, à ce passage seul (date et numéro au hasard) : rien de déjà là n'y est jamais écrit ni
    effacé — un passage d'avant pas encore rouvert reste à côté."""
    import uuid
    root = handover_root(app_dir)
    if _is_link(root):
        raise AppUpdateError(tr('Dossier hors du dossier VD : {0}').format(root))
    root.mkdir(parents=True, exist_ok=True)
    folder = root / (datetime.datetime.now().strftime('%Y%m%d-%H%M%S-') + uuid.uuid4().hex[:6])
    folder.mkdir()
    return folder


def pending_handovers(root) -> list[pathlib.Path]:
    """Les passages à rouvrir, du plus ancien au plus récent : les sous-dossiers directs (pas des liens) qui ont un
    index de session et pas de témoin `rouvert`."""
    root = pathlib.Path(root)
    try:
        subs = sorted(p for p in root.iterdir() if p.is_dir() and not _is_link(p))
    except OSError:
        return []
    return [p for p in subs if (p / 'session.json').is_file() and not (p / WITNESS).exists()]


def read_handover(folder, version: int) -> dict | None:
    """L'index d'un passage (`session.json`), ou None : illisible, verrouillé, pas un index, ou écrit par une version
    à venir (`version` : celle des sessions que cette version lit ; une plus ancienne est acceptée). None : le passage
    n'est jamais réécrit ni effacé (2e relecture du 26/11)."""
    try:
        data = json.loads((pathlib.Path(folder) / 'session.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    v = data.get('version') if isinstance(data, dict) else None
    if not isinstance(v, int) or isinstance(v, bool) or not 1 <= v <= version \
            or not isinstance(data.get('docs'), list) or not all(isinstance(e, dict) for e in data['docs']):
        return None
    return data


def retire_handover(folder) -> bool:
    """Un passage rouvert en entier : d'abord un témoin neuf (`rouvert`, qu'aucun antivirus ne tient encore), puis son
    index renommé d'un coup (`session.json.rouvert`) — l'un ou l'autre suffit : il ne sera plus jamais rouvert, même
    si l'effacement qui suit échoue —, puis le dossier effacé (`drop_handover`). Vrai si le passage ne peut plus
    revenir ; faux : ni témoin ni renommage (3e relecture du 26/11)."""
    folder = pathlib.Path(folder)
    marked = False
    try:
        (folder / WITNESS).write_bytes(b'')
        marked = True
    except OSError:
        pass
    try:
        os.replace(folder / 'session.json', folder / ('session.json' + DONE))
        marked = True
    except OSError:
        pass
    if marked:
        drop_handover(folder)                            # raté : nettoyé au lancement suivant (`sweep_handovers`)
    return marked


def sweep_handovers(root) -> int:
    """Au lancement : les passages déjà rouverts (témoin `rouvert`, index présent ou non ; ou `session.json.rouvert`
    sans index) dont l'effacement avait échoué sont effacés, et les sous-dossiers vides ; rien d'autre. Rend leur
    nombre."""
    root = pathlib.Path(root)
    n = 0
    try:
        subs = [p for p in root.iterdir() if p.is_dir() and not _is_link(p)]
    except OSError:
        return 0
    for p in subs:
        try:
            done = (p / WITNESS).is_file() \
                or (p / ('session.json' + DONE)).is_file() and not (p / 'session.json').exists()
            empty = not any(p.iterdir())
        except OSError:
            continue
        if (done or empty) and drop_handover(p):
            n += 1
    return n


def tries_of(folder) -> int:
    try:
        return int((pathlib.Path(folder) / TRIES).read_text(encoding='ascii').strip() or 0)
    except (OSError, ValueError):
        return 0


def note_try(folder, n: int) -> None:
    """Retient `n` réouvertures tentées, avant la tentative (un plantage pendant elle compte)."""
    part = pathlib.Path(folder) / (TRIES + PART)
    part.write_text(str(int(n)), encoding='ascii')
    os.replace(part, pathlib.Path(folder) / TRIES)


def drop_handover(folder) -> bool:
    """Efface un passage rouvert (ou d'une version qui n'a pas démarré) : seulement un sous-dossier direct du dossier
    des passages, pas un lien. Vrai si effacé ; le dossier des passages, vide, part aussi."""
    folder = pathlib.Path(folder)
    root = folder.parent
    if _is_link(folder) or _is_link(root) or [root.parent.name, root.name] != HANDOVER_DIR.split('/') \
            or not folder.is_dir():
        return False
    try:
        shutil.rmtree(folder, onexc=_writable)           # ne suit ni lien ni jonction
    except OSError:
        return False
    try:
        root.rmdir()                                     # vide seulement
    except OSError:
        pass
    return True


# --- reprendre les réglages ---------------------------------------------------------------------------------------
def settings_state(ini) -> bool | None:
    """Le fichier de réglages a au moins une valeur (celui d'une archive neuve n'a qu'un commentaire ; la note
    « reprise=… » de `decline_settings` n'en est pas une) ; None : illisible."""
    try:
        text = pathlib.Path(ini).read_text(encoding='utf-8', errors='replace')
    except OSError:
        return None
    note = ADOPTED_KEY.split('/')[1] + '='
    return any('=' in ln and not ln.startswith((';', '#', note)) for ln in map(str.strip, text.splitlines()))


def has_settings(ini) -> bool:
    """`settings_state`, illisible compté comme sans valeur (pour décider d'une reprise, pas d'une suppression)."""
    return bool(settings_state(ini))


def already_there(dest) -> tuple[bool, bool]:
    """(la version est déjà dans le dossier VD, marquée et complète ; son VectorDrive.ini a déjà des valeurs)."""
    exe, info = exe_of(dest), read_mark(dest)
    if exe is None or info is None or not named_as_marked(dest, info):
        return False, False
    return True, has_settings(exe.parent / INI)


def _older(a: pathlib.Path, b: pathlib.Path) -> bool:
    return a.stat().st_mtime < b.stat().st_mtime


def _backup(dst: pathlib.Path) -> pathlib.Path:
    """Copie de secours d'un fichier de la nouvelle version, avant que la reprise le remplace."""
    to = dst.with_name(dst.name + BACKUP)
    i = 1
    while to.exists():
        i += 1
        to = dst.with_name(f'{dst.name}{BACKUP}{i}')
    shutil.copy2(dst, to)
    return to


def _crc(path) -> int | None:
    crc = 0
    try:
        with open(path, 'rb') as f:
            for chunk in iter(lambda: f.read(1 << 20), b''):
                crc = zlib.crc32(chunk, crc)
    except OSError:
        return None
    return crc & 0xFFFFFFFF


def _shipped(root, info: dict) -> dict | None:
    """Les fichiers de l'archive gardée dans `zips/` pour cette version : {chemin relatif au dossier de version, en
    minuscules : (taille, CRC)} ; None : archive absente ou illisible."""
    try:
        with zipfile.ZipFile(pathlib.Path(root) / ZIPS / zip_name(info['version'], info['edition'])) as z:
            return {i.filename.replace('\\', '/').rstrip('/').lower(): (i.file_size, i.CRC) for i in z.infolist()
                    if not i.is_dir()}
    except (OSError, ValueError, zipfile.BadZipFile, zlib.error, EOFError):
        return None


def _shipped_app(app: pathlib.Path) -> dict | None:
    """`_shipped` pour un dossier d'application, les chemins relatifs à lui ; None : pas une version marquée, ou son
    archive n'est pas lisible."""
    where = version_of_app(app)
    if where is None:
        return None
    folder, info = where
    ship = _shipped(folder.parent, info)
    if ship is None:
        return None
    prefix = '' if _norm(folder) == _norm(app) else app.name.lower() + '/'
    return {k[len(prefix):]: v for k, v in ship.items() if k.startswith(prefix)}


def _untouched(path, key: str, ship: dict | None, st) -> bool:
    """Le fichier est celui de l'archive, tel quel (même taille, même CRC) : livré, pas à l'utilisateur."""
    want = ship.get(key.lower()) if ship is not None else None
    return want is not None and want[0] == st.st_size and _crc(path) == want[1]


#: le carnet de clients du BAT (`io.clients`), dans `donnees` : son `clients.json` et ses logos ne sont jamais copiés
#: fichier par fichier — fusionnés (`carry_book`, demande du 27/11 : « maj garder le carnet client ») ; ses autres
#: fichiers suivent la règle des données
BOOK_SUB = 'clients'


def _book_file(rel: pathlib.Path, name: str) -> bool:
    """`donnees/<rel>/<name>` est un fichier du carnet de clients : son `clients.json` ou un de ses logos."""
    from .io import clients as CL
    parts = [p.lower() for p in rel.parts]
    return bool(parts) and parts[0] == BOOK_SUB and ((len(parts) == 1 and name.lower() == CL.FILE)
                                                     or (len(parts) > 1 and parts[1] == CL.LOGOS))


def chosen_book(where) -> str:
    """Le dossier du carnet de clients choisi par une version (réglage `bat/clients`, F10 › BAT : un dossier partagé…)
    — `where` : ses réglages (QSettings) ou son VectorDrive.ini, lu seulement ; '' : celui de ses données."""
    from PySide6.QtCore import QSettings
    from .io import clients as CL
    s = where if hasattr(where, 'value') else QSettings(str(where), QSettings.Format.IniFormat)
    return str(s.value(CL.SETTING, '') or '').strip().strip('"')


def book_taken(book: Book, where) -> bool:
    """Le dossier choisi par l'ancienne version (`book.chosen`) est celui de cette version (`where` : ses réglages ou
    son VectorDrive.ini) — chemins comparés comme texte, sans accès au réseau."""
    return bool(book.chosen) and _norm(chosen_book(where)) == _norm(book.chosen)


def carry_book(old_app, new_app, here: str | None = None) -> Book:
    """Le carnet de clients du BAT de l'ancienne version (demande du 27/11 : « maj garder le carnet client ») :
    - elle pointait vers un dossier choisi (réseau…) : rien n'est copié, son réglage suit les autres (`chosen`) ;
    - cette version a un dossier choisi (`here`, d'office lu dans son VectorDrive.ini) : peut-être partagé par
      d'autres postes — rien n'y est versé d'office, ni copie de secours (`shared`, `waiting`, dit dans le bilan) ;
    - sinon son carnet (`donnees/clients`) va dans `donnees/clients` d'ici : copié s'il n'y en a pas, sinon fusionné
      (`io.clients.merge`) — clients d'ici gardés tels quels, ceux qui manquent ajoutés avec leur logo, rien
      d'écrasé, le `clients.json` d'ici copié d'abord (`….avant_reprise`) ; illisible : jamais perdu (dit).
    Rien n'est écrit dans l'ancien dossier."""
    from .io import clients as CL
    old, new = pathlib.Path(old_app), pathlib.Path(new_app)
    chosen = chosen_book(old / INI)
    if chosen:
        return Book(chosen=chosen)
    src = old / DATA / BOOK_SUB
    if _is_link(src) or not (src / CL.FILE).is_file():
        return Book()
    here = chosen_book(new / INI) if here is None else here
    if here:
        return Book(shared=here, waiting=len(CL.load(src)))
    target = new / DATA / BOOK_SUB
    try:
        m = CL.merge(src, target, backup=lambda f: f'{f} → {_backup(f).name}')
    except OSError as ex:
        return Book(failed=[f'{target} : {ex.strerror or ex}'])
    return Book(len(m.added), m.logos, m.kept, replaced=m.replaced, failed=m.failed)


def carry_settings(old_app_dir, new_app_dir, *, ini: bool = True, keep: bool = False,
                   stop: list | None = None, book_here: str | None = None) -> Carried:
    """« Reprendre ses paramètres » : `VectorDrive.ini`, le dossier `donnees` et la bibliothèque interne
    (`bibliotheque`, à côté de l'exécutable : symboles ajoutés, « Logos BAT », « Favoris ») de l'application en cours
    (portable) copiés dans la nouvelle. Fusion prudente : dans `donnees`, un fichier déjà là n'est remplacé que s'il
    est plus ancien (les réglages : aussi s'ils sont encore vides), et jamais sans copie de secours
    (`….avant_reprise`) ; dans `bibliotheque`, seuls les fichiers absents de la nouvelle version sont copiés — jamais
    un fichier qu'elle fournit n'est écrasé ; les fichiers de récupération et les verrous restent à l'ancienne
    version. Chaque copie s'écrit sous un nom provisoire, vérifiée (taille, fichier d'origine inchangé), puis prend la
    place du fichier (`os.replace`). Un fichier gardé par la nouvelle version, de contenu différent, n'est pas repris
    (`skipped`) — sauf s'il est celui de l'archive de l'ancienne, tel quel (livré, pas à l'utilisateur). Application
    en cours non portable (`old_app_dir` None, ou sans VectorDrive.ini : réglages dans le registre du poste) : rien à
    copier. `ini` faux : `VectorDrive.ini` laissé (la reprise d'une ancienne version pose ses réglages un par un,
    `merge_settings`) ; `keep` : aucun fichier de `donnees` déjà là n'est remplacé. Fichiers provisoires (`.tmp`,
    `.vd_copie`) jamais repris. `stop` (une liste) : Annuler, pris entre deux fichiers, n'est pas levé — la copie
    s'arrête, `stop` reçoit vrai et ce qui a été copié est rendu tel quel. Le carnet de clients du BAT n'est pas
    copié fichier par fichier : `carry_book` (`book_here` : le dossier choisi du carnet de cette version, '' : ses
    données ; None : lu dans son VectorDrive.ini). Rend `Carried` : rien n'est passé sous silence."""
    failed: list[str] = []
    skipped: list[str] = []
    files: list[list] = []
    if old_app_dir is None:
        return Carried(0, failed, skipped, files)
    old, new = pathlib.Path(old_app_dir), pathlib.Path(new_app_dir)
    if not (old / INI).is_file() or _norm(old) == _norm(new):
        return Carried(0, failed, skipped, files)
    ship = _shipped_app(old)
    count = [0]

    def put(src: pathlib.Path, dst: pathlib.Path, inner: str, replace, precious) -> None:
        try:
            st = src.stat()
            if dst.exists():
                if not replace(dst, src):
                    if filecmp.cmp(src, dst, shallow=False):
                        files.append([inner, st.st_size, st.st_mtime_ns])     # déjà là, identique : repris
                    elif not _untouched(src, inner, ship, st):
                        skipped.append(str(src))         # la nouvelle version garde le sien : pas repris
                    return
                if precious(dst):
                    _backup(dst)
            dst.parent.mkdir(parents=True, exist_ok=True)
            part = dst.with_name(dst.name + PART)
            try:
                shutil.copy2(src, part)
                if part.stat().st_size != st.st_size:
                    raise OSError(tr('copie incomplète'))
                after = src.stat()
                if (after.st_size, after.st_mtime_ns) != (st.st_size, st.st_mtime_ns):
                    raise OSError(tr('modifié pendant la copie'))
                os.replace(part, dst)
            except BaseException:
                part.unlink(missing_ok=True)
                raise
        except OSError as ex:
            failed.append(f'{src} : {ex.strerror or ex}')
            return
        files.append([inner, st.st_size, st.st_mtime_ns])
        count[0] += 1

    if ini and settings_state(old / INI) is not False:   # des réglages (ou illisible : la copie le dira)
        put(old / INI, new / INI, INI, lambda d, s: not has_settings(d) or _older(d, s),
            lambda d: settings_state(d) is not False)
    try:
        for sub in (DATA, LIBRARY):
            base = old / sub
            if not os.path.lexists(base):
                continue
            if _is_link(base) or not base.is_dir():          # jonction : jamais suivie, donc pas reprise
                skipped.append(str(base))
                continue
            def bad(ex, failed=failed):
                failed.append(f'{ex.filename} : {ex.strerror}')
            for folder, dirs, names in os.walk(base, onerror=bad):
                here = pathlib.Path(folder)
                rel = here.relative_to(base)
                if sub == DATA and not rel.parts:
                    dirs[:] = [d for d in dirs if d not in NOT_CARRIED]
                for d in list(dirs):
                    if _is_link(here / d):
                        dirs.remove(d)
                        skipped.append(str(here / d))
                for name in names:
                    P.check()
                    if name.lower().endswith(('.lock', '.tmp', PART)):     # verrous, fichiers en cours d'écriture
                        continue
                    if sub == DATA and _book_file(rel, name):        # le carnet de clients : fusionné à part
                        continue
                    src = here / name
                    if _is_link(src):
                        skipped.append(str(src))
                        continue
                    put(src, new / sub / rel / name, (pathlib.PurePosixPath(sub) / rel.as_posix() / name).as_posix(),
                        lambda d, s: not keep and sub == DATA and _older(d, s), lambda d: d.stat().st_size > 0)
    except P.Cancelled:
        if stop is None:
            raise
        stop.append(True)                                # Annuler : ce qui est copié est rendu
    if stop:                                             # arrêtée : le carnet n'est pas fusionné (dit par `stopped`)
        return Carried(count[0], failed, skipped, files, Book(chosen=chosen_book(old / INI)))
    book = carry_book(old, new, book_here)
    return Carried(count[0], failed + list(book.failed), skipped, files, book)


# --- reprendre une ancienne version portable (demandes du 27/11) ----------------------------------------------------
#: les dossiers favoris (fenêtre Ouvrir) et les dossiers de la bibli : comptés dans le bilan d'une reprise
FAVORITES_KEY, BIBLI_KEY = 'navigateur/favoris', 'navigateur/dossiers'
#: dans `donnees` : ce qui ne dit rien de l'usage d'une version (caches, journal) — pas compté dans son contenu
_NOT_CONTENT = {'polices.json', 'favoris_index.json', 'symboles_textes.json', 'erreurs.txt', 'formes_polices'}
#: la session d'une version portable, dans `donnees`
SESSION_SUB = 'session'
#: « Mes outils », dans `donnees` : fusionnés à la reprise (jamais remplacés ni perdus)
TOOLS_REL = ('outils', 'tools.json')
#: une version servie pour de vrai : une session et au moins autant de réglages (une version lancée pour essai n'a que
#: ceux de sa fenêtre)
REAL_KEYS = 10
#: reprise coupée : au plus autant de tentatives (la marque les compte), puis abandon, dit dans le bilan
ADOPT_TRIES = 2
#: reprise à la main (cette version a déjà ses réglages) : ces listes sont réunies, celles d'ici d'abord, sans
#: doublon — listes de réglages, listes en texte « ; », listes en JSON ; les autres réglages déjà posés ici restent
UNION_LISTS = ('navigateur/favoris', 'navigateur/dossiers', 'symboles/favoris', 'symboles/dossiers', 'ruban/favoris')
UNION_JOINED = ('polices/dossiers', 'symboles/dossiers_extra', 'plugins/dossiers')
UNION_JSON = ('outils/favoris',)
#: parmi elles, celles qui ne sont pas des chemins (des commandes du ruban) : comparées telles quelles
UNION_NOT_PATHS = ('ruban/favoris',)
#: reprise à la main : ces réglages, vides ici (la fenêtre des options écrit chaque champ, vide compris : « vide » y
#: dit « d'office »), prennent la valeur de l'ancienne version — le dossier choisi du carnet de clients (seulement si
#: le carnet des données d'ici est vide : `adopt_previous`)
FILL_EMPTY = ('bat/clients',)


class Adopted(NamedTuple):
    """Une reprise d'ancienne version (`adopt_previous`) : `name`, son nom (le dossier décompressé) ; `folder`, son
    dossier d'application ; `copied`, les fichiers copiés (réglages compris) ; `tabs`, les onglets passés avec leurs
    parcours et le mémo de leur calcul ; `handover`, leur passage (`donnees/session_maj/…`) ou None ; `favorites`,
    `bibli` : les dossiers favoris et les dossiers de la bibli repris ; `failed` (« chemin : raison ») et `skipped`
    (fichiers que cette version garde) ; `replaced` : les fichiers de cette version remplacés, chacun avec sa copie de
    secours (« fichier → copie ») ; `stopped` : la copie a été arrêtée (Annuler) ; `kept` : réglages déjà posés ici,
    gardés (reprise à la main) ; `language` : la langue reprise, qui ne s'applique qu'au prochain lancement ('' :
    inchangée) ; `book`, le carnet de clients du BAT (`Book`), `book_taken`, le dossier choisi par l'ancienne version
    repris ici, `book_here`, le dossier choisi ici (gardé), `book_local`, les clients du carnet des données d'ici,
    gardé parce qu'il n'est pas vide (le dossier choisi par l'ancienne n'est alors pas repris) — rien n'est passé
    sous silence."""
    name: str
    folder: str
    copied: int
    tabs: int
    handover: pathlib.Path | None
    favorites: int
    bibli: int
    failed: list
    skipped: list
    replaced: list = []
    stopped: bool = False
    kept: int = 0
    language: str = ''
    book: Book = Book()
    book_taken: bool = False
    book_here: str = ''
    book_local: int = 0


class Candidate(NamedTuple):
    """Une ancienne version portable proposée à la reprise : son dossier d'application, son nom, sa version (lue de
    sa marque ou de son nom ; '' : inconnue), sa dernière utilisation (date, 0 : inconnue), les onglets de sa session,
    les fichiers de sa bibliothèque, ses dossiers favoris, les dossiers de sa bibli, ses réglages, ses fichiers de
    données (hors session, récupération, caches), son édition ('' : sans)."""
    app: pathlib.Path
    name: str
    version: str
    last_use: float
    tabs: int
    library: int
    favorites: int
    bibli: int
    keys: int
    files: int
    edition: str = ''


def same_place(a, b) -> bool:
    """Le même dossier : chemins comparés tels quels, puis résolus (jonction, lien, lecteur réseau ou chemin UNC)."""
    if _norm(a) == _norm(b):
        return True
    try:
        return _real(a) == _real(b)
    except (OSError, RuntimeError, ValueError):
        return False


def version_label(app) -> str:
    """Le nom d'une version portable : le dossier décompressé (celui qui contient `VectorDrive/`)."""
    app = pathlib.Path(app)
    return app.parent.name if app.name.lower() == 'vectordrive' else app.name


def _listed(value) -> list:
    """Une liste des réglages (INI : une liste d'un seul élément relue en texte)."""
    if value is None or value == '':
        return []
    return [value] if isinstance(value, str) else [v for v in value if v]


def old_app_of(folder) -> pathlib.Path | None:
    """Le dossier d'application d'une version portable de VectorDrive qui a servi : `folder` lui-même ou son
    `VectorDrive/` — VectorDrive.exe et un VectorDrive.ini qui a des valeurs. None : ce n'en est pas une."""
    folder = pathlib.Path(folder)
    for cand in (folder, folder / 'VectorDrive'):
        try:
            if (cand / EXE).is_file() and has_settings(cand / INI):
                return cand
        except OSError:
            pass
    return None


def _count_files(base: pathlib.Path, skip=(), cap: int = 200_000) -> int:
    """Les fichiers d'un dossier (liens jamais suivis) ; `skip` : noms de dossiers ou de fichiers du premier niveau
    laissés de côté."""
    n = 0
    if not base.is_dir() or _is_link(base):
        return 0
    for folder, dirs, names in os.walk(base):
        here = pathlib.Path(folder)
        top = here == base
        dirs[:] = [d for d in dirs if not _is_link(here / d) and not (top and d in skip)]
        n += sum(1 for x in names if not (top and x in skip))
        if n >= cap:
            break
    return n


def describe(app) -> Candidate:
    """Ce qu'une ancienne version portable a à reprendre (retour terrain du 27/11 : la version reprise d'office
    n'était pas celle de tous les jours) — lu seulement, rien n'est écrit dans son dossier."""
    from PySide6.QtCore import QSettings
    app = pathlib.Path(app)
    s = QSettings(str(app / INI), QSettings.Format.IniFormat)
    keys = [k for k in s.allKeys() if k != ADOPTED_KEY]
    index = app / DATA / SESSION_SUB / 'session.json'
    tabs = 0
    try:
        data = json.loads(index.read_text(encoding='utf-8'))
        tabs = sum(1 for e in data.get('docs') or [] if isinstance(e, dict) and (e.get('file') or e.get('path')))
    except (OSError, ValueError, AttributeError, TypeError):
        pass
    stamps = []
    for p in (app / INI, index):
        try:
            stamps.append(p.stat().st_mtime)
        except OSError:
            pass
    info = read_mark(app.parent) or read_mark(app) or {}
    m = re.search(VERSION_RE, version_label(app))
    version = str(info.get('version') or (m.group(0) if m else ''))
    d = DIR_RE.match(version_label(app))
    edition = str(info.get('edition') or (d['ed'] if d and d['ed'] else ''))
    return Candidate(app, version_label(app), version, max(stamps, default=0.0), tabs,
                     _count_files(app / LIBRARY), len(_listed(s.value(FAVORITES_KEY))),
                     len(_listed(s.value(BIBLI_KEY))), len(keys),
                     _count_files(app / DATA, set(NOT_CARRIED) | _NOT_CONTENT), edition)


def user_content(c: Candidate) -> int:
    """Ce que l'utilisateur a mis dans une version : onglets, bibliothèque, favoris, dossiers de la bibli, données."""
    return c.tabs + c.library + c.favorites + c.bibli + c.files


def real_use(c: Candidate) -> bool:
    """La version a servi pour de vrai : une session et de vrais réglages (`REAL_KEYS`)."""
    return c.tabs > 0 and c.keys >= REAL_KEYS


def _band(n: int) -> int:
    """Des contenus proches (à moitié près) tombent dans la même tranche : la dernière utilisation les départage."""
    import math
    return 0 if n <= 0 else 1 + int(math.log(n) / math.log(1.5))


def preferred(cands, edition: str = '') -> list:
    """Les versions proposées, la présélectionnée d'abord (2e relecture du 27/11) : celles de la même édition que
    cette version (`edition`) ; puis celles qui ont servi pour de vrai (`real_use`), la plus récemment utilisée en
    tête — une vieille version très remplie ne passe plus devant la plus récente qui a une session et de vrais
    réglages ; sinon le plus de contenu à l'utilisateur (`user_content`, par tranches : des contenus proches sont
    départagés par la dernière utilisation), puis le plus de réglages. Une version lancée une fois pour essai
    (réglages de fenêtre, aucune donnée) ne passe jamais devant celle de tous les jours parce que son VectorDrive.ini
    est plus récent. Toutes sont montrées : l'utilisateur choisit."""
    ed = (edition or '').lower()

    def rank(c):
        real = real_use(c)
        return ((c.edition or '').lower() == ed, real, c.last_use if real else 0.0, _band(user_content(c)),
                c.last_use, c.keys)
    return sorted(cands, key=rank, reverse=True)


def guess_previous(app, versions_root=None) -> pathlib.Path | None:
    """Le dossier proposé par « Reprendre d’une ancienne version… » : la version portable posée à côté, sinon la plus
    récente du dossier VD qui a servi — jamais celle-ci (chemins résolus : `same_place`)."""
    from .portable import previous_portable
    app = pathlib.Path(app)
    near = previous_portable(app)
    if near is not None:
        return near
    best = None
    try:
        subs = list(pathlib.Path(versions_root).iterdir()) if versions_root else []
    except OSError:
        subs = []
    for d in subs:
        m = DIR_RE.match(d.name)
        if m is None or _is_link(d) or not d.is_dir():
            continue
        cand = old_app_of(d)
        if cand is None or same_place(cand, app):
            continue
        v = parse_version(m.group('v'))
        if best is None or v > best[0]:
            best = (v, cand)
    return best[1] if best else None


def read_settings(old_ini) -> tuple[dict, list]:
    """Les réglages de l'ancienne version, lus seulement : ({clé : valeur}, échecs)."""
    from PySide6.QtCore import QSettings
    old_ini = pathlib.Path(old_ini)
    if settings_state(old_ini) is None:
        return {}, [f'{old_ini} : {tr("illisible")}']
    old = QSettings(str(old_ini), QSettings.Format.IniFormat)
    return {k: old.value(k) for k in old.allKeys() if not k.startswith('portable/')}, []


def _dedup(items, paths: bool = True) -> list:
    """Sans doublon, dans l'ordre ; `paths` : des chemins, comparés sans casse ni séparateur (`os.path.normcase`) ;
    sinon tels quels (des noms de commandes : « Copier » et « copier » restent deux)."""
    seen, out = set(), []
    for x in items:
        s = str(x).strip()
        k = os.path.normcase(s) if paths else s
        if s and k not in seen:
            seen.add(k)
            out.append(s)
    return out


def _union(key: str, here, theirs):
    """La réunion d'une liste connue (`UNION_*`), celle d'ici d'abord, sans doublon ; None : pas une de ces listes,
    ou rien de neuf à y ajouter."""
    paths = key not in UNION_NOT_PATHS
    if key in UNION_LISTS:
        a, b = _listed(here), _listed(theirs)
        out = _dedup(list(map(str, a)) + list(map(str, b)), paths)
        return out if len(out) > len(_dedup(map(str, a), paths)) else None
    if key in UNION_JOINED:
        a = [x for x in str(here or '').split(';')]
        out = _dedup(a + str(theirs or '').split(';'), paths)
        return ';'.join(out) if len(out) > len(_dedup(a, paths)) else None
    if key in UNION_JSON:
        def load(v):
            try:
                got = json.loads(v) if isinstance(v, str) and v else []
            except ValueError:
                got = []
            return [str(k) for k in got] if isinstance(got, list) else []
        a = load(here)
        out = list(dict.fromkeys(a + load(theirs)))
        return json.dumps(out, ensure_ascii=False) if len(out) > len(dict.fromkeys(a)) else None
    return None


def merge_settings(values: dict, settings, label: str, tag: str = '') -> tuple[int, list, list, int]:
    """Les réglages de l'ancienne version (`values`, `read_settings`) posés dans `settings` (ceux de cette version).
    Premier lancement (aucun réglage ici) : tous. Reprise à la main (2e relecture du 27/11 : des favoris ajoutés ici
    se perdaient) : un réglage déjà posé ici reste, sauf les listes de favoris et de dossiers connues (`UNION_*`),
    réunies, celles d'ici d'abord, sans doublon, et ceux de `FILL_EMPTY` restés vides ici (le dossier choisi du
    carnet de clients). Le fichier de cette version, s'il avait déjà des valeurs, est d'abord
    copié (`….avant_reprise`) ; sans cette copie, rien n'est changé. La note de reprise (`ADOPTED_KEY`, et l'étiquette
    `tag` sous `DONE_KEY` : la marque « reprise en cours » ne compte plus, même si elle n'a pas pu être effacée) est
    posée en dernier. Rend (1 si repris, sinon 0 ; échecs ; remplacés « fichier → copie » ; réglages d'ici gardés)."""
    from PySide6.QtCore import QSettings
    from .portable import DONE_KEY
    mine = pathlib.Path(settings.fileName())
    replaced = []
    here = {k for k in settings.allKeys() if not k.startswith('portable/')}
    if values and settings.format() == QSettings.Format.IniFormat and mine.is_file() and has_settings(mine):
        try:
            settings.sync()
            replaced.append(f'{mine} → {_backup(mine).name}')
        except OSError as ex:
            return 0, [f'{mine} : {ex.strerror or ex}'], [], 0
    kept = 0
    for k, v in values.items():
        if k in here and not (k in FILL_EMPTY and _blank(settings.value(k)) and not _blank(v)):
            merged = _union(k, settings.value(k), v)
            if merged is None:
                if str(settings.value(k)) != str(v):
                    kept += 1
                continue
            v = merged
        settings.setValue(k, v)
    settings.sync()
    settings.setValue(ADOPTED_KEY, label)
    if tag:
        settings.setValue(DONE_KEY, tag)
    settings.sync()
    if settings.status() != QSettings.Status.NoError:
        return 0, [f'{mine} : {tr("réglages non enregistrés")}'], replaced, kept
    return (1 if values else 0), [], replaced, kept


def _blank(value) -> bool:
    """Un réglage vide (rien, ou un texte d'espaces et de guillemets)."""
    return value is None or str(value).strip().strip('"') == ''


def session_kept(values: dict) -> bool:
    """L'ancienne version gardait sa session (option « Fermer sans question et tout rouvrir », d'office oui) : sinon
    son `donnees/session` est celle d'autrefois, jamais rouverte."""
    return str(values.get('options/session', True)).strip().lower() not in ('false', '0', 'non', 'no', 'off')


def _copy_in(src: pathlib.Path, dst: pathlib.Path) -> None:
    """Copie sous un nom provisoire, vérifiée (taille), puis mise en place d'un coup (`os.replace`)."""
    part = dst.with_name(dst.name + PART)
    try:
        shutil.copy2(src, part)
        if part.stat().st_size != src.stat().st_size:
            raise OSError(tr('copie incomplète'))
        os.replace(part, dst)
    except BaseException:
        part.unlink(missing_ok=True)
        raise


def _tagged_handover(new_app, tag: str) -> tuple[pathlib.Path | None, dict | None]:
    """Le passage déjà écrit par une reprise interrompue (`tag` dans son index), pas encore rouvert."""
    if not tag:
        return None, None
    for f in pending_handovers(handover_root(new_app)):
        try:
            data = json.loads((f / 'session.json').read_text(encoding='utf-8'))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict) and data.get('reprise') == tag:
            return f, data
    return None, None


def pass_session(old_app, new_app, version: int, tag: str = '') -> tuple[int, pathlib.Path | None, list]:
    """La session de l'ancienne version (`donnees/session` : ses onglets enregistrés ou non, épinglés, renommés, leur
    ordre, l'onglet actif, les parcours calculés et le mémo de leur calcul) passée comme une mise à jour : copiée
    dans un passage neuf de cette version (`new_handover`), que `MainWindow.reopen_after_update` rouvre — jamais dans
    sa propre session, jamais un verrou ni un fichier en cours d'écriture. L'index (celui qui a été lu et vérifié)
    est écrit en dernier : un passage à moitié copié n'est jamais vu. L'index de l'ancienne est relu après la copie :
    changé entre-temps (« Reprendre sans attendre » : l'ancienne, ouverte, enregistre sa session toute seule), la
    copie est refaite une fois, puis c'est dit. `tag` : la reprise en cours (`ADOPTING`) — un passage qu'elle a déjà
    écrit avant d'être interrompue est repris tel quel, jamais doublé. Sans index lisible, ou sans onglet : rien
    n'est passé, sans erreur. Annulée (entre deux fichiers) : le passage commencé est effacé. Rend (onglets passés,
    passage ou None, échecs)."""
    done, data = _tagged_handover(new_app, tag)
    if done is not None:
        return len(data.get('docs') or []), done, []
    src = pathlib.Path(old_app) / DATA / SESSION_SUB
    failed: list[str] = []
    for attempt in (1, 2):
        index = read_handover(src, version)
        if index is None:
            if (src / 'session.json').exists():          # illisible, ou d'une version plus récente : dit
                failed.append(f'{src / "session.json"} : ' + tr('session illisible ou d’une version plus récente : '
                                                               'onglets non repris'))
            return 0, None, failed
        docs = [e for e in index['docs'] if e.get('file') or e.get('path')]
        if not docs:
            return 0, None, failed
        try:
            folder = new_handover(new_app)
        except (OSError, AppUpdateError) as ex:
            return 0, None, failed + [f'{handover_root(new_app)} : {getattr(ex, "strerror", None) or ex}']
        bad = []
        try:
            try:
                names = sorted(src.iterdir())
            except OSError as ex:
                names = []
                bad.append(f'{src} : {ex.strerror or ex}')
            for f in names:
                P.check()                                # Annuler : entre deux fichiers
                low = f.name.lower()
                if low == 'session.json' or low.endswith(('.lock', '.tmp', PART)) or low in (WITNESS, TRIES) \
                        or _is_link(f) or not f.is_file():
                    continue
                try:
                    _copy_in(f, folder / f.name)
                except OSError as ex:
                    bad.append(f'{f} : {ex.strerror or ex}')
        except BaseException:
            drop_handover(folder)
            raise
        again = read_handover(src, version)
        if again == index:
            break
        if attempt == 1:
            drop_handover(folder)                        # enregistrée pendant la copie : refaite une fois
            continue
        bad.append(f'{src} : ' + tr('session enregistrée par l’ancienne version pendant la copie, deux fois : '
                                    'onglets repris tels qu’au début de la copie, peut-être incomplets'))
    failed += bad
    try:
        part = folder / ('session.json' + PART)
        body = {**index, 'docs': docs}
        if tag:
            body['reprise'] = tag
        part.write_text(json.dumps(body, ensure_ascii=False, indent=1), encoding='utf-8')
        os.replace(part, folder / 'session.json')
    except OSError as ex:
        drop_handover(folder)
        return 0, None, failed + [f'{src / "session.json"} : {ex.strerror or ex}']
    return len(docs), folder, failed


def merge_tools(old_app, new_app) -> tuple[bool, list, list]:
    """« Mes outils » (`donnees/outils/tools.json`) déjà là dans cette version : ceux de l'ancienne y sont ajoutés,
    sans doublon (comme l'import d'un .vdparam ; un identifiant déjà pris ici est renouvelé), ses dossiers aussi,
    après la copie de secours du fichier — jamais un outil ajouté ici n'est perdu. Rend (fait, remplacés
    « fichier → copie », échecs)."""
    from .cam import toollib
    src = pathlib.Path(old_app).joinpath(DATA, *TOOLS_REL)
    dst = pathlib.Path(new_app).joinpath(DATA, *TOOLS_REL)
    try:
        if not src.is_file() or _is_link(src) or not dst.is_file() or filecmp.cmp(src, dst, shallow=False):
            return False, [], []
        theirs, mine = toollib.load(src), toollib.load(dst)
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as ex:
        return False, [], [f'{src} : {tr("Mes outils non fusionnés")} ({ex})']
    ids = {t.id for t in mine}
    added = []
    for t in theirs:
        if toollib.find_duplicate(t, mine + added) is None:
            if t.id in ids:
                t.id = toollib.new_id()
            ids.add(t.id)
            added.append(t)
    folders = toollib.load_folders(dst)
    extra = [f for f in toollib.load_folders(src) if f not in folders]
    if not added and not extra:
        return True, [], []
    try:
        bk = _backup(dst)
        toollib.save(mine + added, dst, folders + extra)
    except OSError as ex:
        return False, [], [f'{dst} : {ex.strerror or ex}']
    return True, [f'{dst} → {bk.name}'], []


def _run_direct(fn):
    return fn()


#: Annuler : le temps laissé au fichier en cours pour finir avant le bilan (secondes)
STOP_WAIT_S = 120.0
#: dossiers des données jamais balayés par `sweep_parts` : ceux que la fenêtre ouverte écrit elle-même
_SWEEP_SKIP = ('session', 'session_maj', 'recuperation', 'sauvegardes', 'onglets_fermes')


def sweep_parts(new_app) -> list:
    """Une reprise coupée reprise : les copies à moitié écrites (`PART`, `.vd_copie`) restées dans les données et la
    bibliothèque de cette version sont effacées (jamais dans les dossiers que la fenêtre écrit elle-même). Rend les
    échecs (« chemin : raison »)."""
    failed: list = []
    for sub in (DATA, LIBRARY):
        root = pathlib.Path(new_app) / sub
        if not root.is_dir():
            continue
        for here, dirs, files in os.walk(root):
            if pathlib.Path(here) == root:
                dirs[:] = [d for d in dirs if d.lower() not in _SWEEP_SKIP]
            for f in files:
                if f.lower().endswith(PART):
                    p = pathlib.Path(here) / f
                    try:
                        p.unlink()
                    except OSError as ex:
                        failed.append(f'{p} : {ex.strerror or ex}')
    return failed


def wait_done(done, timeout_s: float) -> bool:
    """Après Annuler, le fichier en cours finit (`done`, un `threading.Event`) : attendu `timeout_s` secondes au plus.
    Sur le fil de l'interface, jamais figé sans rien montrer : une petite fenêtre « Fin du fichier en cours… » et une
    boucle d'évènements (comme `ui.progress.run`). Rend vrai si fini."""
    if done.is_set():
        return True
    from PySide6.QtCore import QThread
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None or QThread.currentThread() is not app.thread():
        return done.wait(timeout_s)
    from PySide6.QtCore import QEventLoop, Qt, QTimer
    from PySide6.QtWidgets import QProgressDialog

    class Box(QProgressDialog):
        def reject(self):                                # Échap : l'attente reste (bornée)
            pass

        def closeEvent(self, e):                         # la croix : de même
            e.ignore()
    box = Box(tr('Fin du fichier en cours…'), '', 0, 0)
    box.setWindowTitle(tr('Reprise de l’ancienne version'))
    box.setCancelButton(None)
    box.setWindowModality(Qt.WindowModality.ApplicationModal)
    box.setMinimumDuration(0)
    box.show()
    loop = QEventLoop()
    end = time.monotonic() + timeout_s
    timer = QTimer()
    timer.setInterval(100)
    timer.timeout.connect(lambda: (done.is_set() or time.monotonic() >= end) and loop.quit())
    timer.start()
    try:
        loop.exec()
    finally:
        timer.stop()
        box.hide()
        box.deleteLater()
    return done.is_set()


def adopt_previous(old_app, new_app, *, settings=None, keep: bool = True, session_version: int | None = None,
                   progress=None) -> Adopted:
    """Reprendre une ancienne version portable (premier lancement : `portable.offer_previous` ; à la main : F10 ›
    Mises à jour › « Reprendre d’une ancienne version… »). Dans cet ordre (relectures du 27/11 : une reprise coupée ne
    doit rien perdre ni rien doubler) :
    - la marque « reprise en cours » (`portable.ADOPTING`, dans le dossier de cette version : source, étiquette,
      tentatives, étapes faites) ;
    - la session de l'ancienne passée comme une mise à jour (`pass_session`), une seule fois : l'étape est retenue
      dans la marque, jamais refaite ;
    - ses données et sa bibliothèque (`carry_settings`, fichier par fichier, une erreur n'arrêtant pas le reste ;
      `keep` : rien de déjà là n'est remplacé), son carnet de clients fusionné dans celui des données d'ici
      (`carry_book` ; jamais dans un dossier choisi ici), « Mes outils » fusionnés (`merge_tools`) ;
    - ses réglages (`merge_settings`) et la note de reprise en dernier ; la marque effacée. Le dossier choisi du
      carnet de clients de l'ancienne n'est repris que si celui des données d'ici est vide (sinon gardé, dit).
    Coupée (processus arrêté) : la marque reste, `portable.adoption_pending` est vrai et le lancement suivant la
    termine ; après `ADOPT_TRIES` tentatives, elle est abandonnée (réglages posés, dit dans le bilan). Une erreur
    pendant les copies est dite et la reprise finit quand même. Les copies passent par `progress(fn)` (d'office :
    directement ; `portable.offer_previous` montre une fenêtre de progression) ; Annuler (entre deux fichiers) : la
    copie s'arrête — le fichier en cours fini avant le bilan, qui compte ce qui a vraiment été copié —, les réglages
    sont posés quand même (`stopped`). Jamais sa récupération, sa session elle-même ni un verrou ; rien n'est écrit
    dans l'ancien dossier. `settings` : les réglages de cette version (d'office son VectorDrive.ini)."""
    import threading
    import uuid
    from PySide6.QtCore import QSettings
    from . import i18n
    from .portable import adoption_mark, drop_adoption_mark, write_adoption_mark
    old, new = pathlib.Path(old_app), pathlib.Path(new_app)
    name = version_label(old)
    if same_place(old, new):
        return Adopted(name, str(old), 0, 0, None, 0, 0, [f'{old} : {tr("la version en cours")}'], [], [], False)
    if settings is None:
        settings = QSettings(str(new / INI), QSettings.Format.IniFormat)
    values, failed = read_settings(old / INI)
    from .io import clients as CL
    here_book = chosen_book(settings)                    # le carnet d'ici : son dossier choisi, sinon les données
    local = CL._raw(new / DATA / BOOK_SUB)               # avant les copies ; None : illisible, compté plein
    mark = adoption_mark(new)
    same = mark is not None and same_place(mark['source'], old)
    tag = mark['tag'] if same else uuid.uuid4().hex[:12]
    tries = (int(mark.get('tries') or 0) if same else 0) + 1
    session_done = bool(same and mark.get('session'))
    abandon = tries > ADOPT_TRIES

    def note(**more) -> None:
        try:
            write_adoption_mark(new, old, tag, tries=tries, **more)
        except OSError as ex:
            failed.append(f'{new} : {ex.strerror or ex}')
    if same:                                             # coupée : ses copies à moitié écrites (`PART`) effacées
        failed.extend(sweep_parts(new))
    if abandon:
        failed.append(f'{old} : ' + tr('reprise abandonnée après {0} tentatives interrompues : les fichiers déjà '
                                       'copiés restent ; « Reprendre d’une ancienne version… » (F10) la refait sans '
                                       'rien remplacer').format(ADOPT_TRIES))
    else:
        note(session=session_done)                       # tentative comptée avant les copies
    if session_version is None:
        from .ui import session
        session_version = session.VERSION
    got: dict = {}
    stop: list = []
    done = threading.Event()

    def copy_all():
        try:
            if session_done or abandon:                  # passée par une tentative d'avant : jamais repassée, comptée
                folder, data = _tagged_handover(new, tag)
                got['session'] = (len(data.get('docs') or []) if data else 0, folder, [])
            if abandon:
                return got
            if not session_done and session_kept(values):
                got['session'] = pass_session(old, new, session_version, tag)
                note(session=True)
            got['carried'] = carry_settings(old, new, ini=False, keep=keep, stop=stop, book_here=here_book)
            if not stop:
                got['tools'] = merge_tools(old, new)
        except P.Cancelled:
            stop.append(True)
        except Exception as ex:                          # noqa: BLE001 — dit, et la reprise finit quand même
            got['error'] = f'{old} : ' + tr('copie interrompue par une erreur ({0})').format(ex)
        finally:
            done.set()
        return got

    try:
        (progress or _run_direct)(copy_all)
    except P.Cancelled:                                  # la fenêtre rend la main aussitôt : le fichier en cours finit
        stop.append(True)
    if not wait_done(done, STOP_WAIT_S):
        failed.append(f'{old} : ' + tr('copie encore en cours : le décompte est provisoire'))
    tabs, folder, bad = got.get('session') or (0, None, [])
    carried = got.get('carried') or Carried(0, [], [], [])
    merged, replaced, tool_bad = got.get('tools') or (False, [], [])
    skipped = list(carried.skipped)
    if merged:
        skipped = [s for s in skipped if not same_place(s, old.joinpath(DATA, *TOOLS_REL))]
    if got.get('error'):
        failed.append(got['error'])
    old_book = '' if _blank(values.get(CL.SETTING)) else str(values[CL.SETTING]).strip().strip('"')
    book_local = 0
    if old_book and not here_book and (local is None or local):     # le carnet d'ici n'est pas vide : il reste
        values = {k: v for k, v in values.items() if k != CL.SETTING}
        book_local = len(CL.load(new / DATA / BOOK_SUB)) or len(local or [])
    n, bad_settings, more, kept = merge_settings(values, settings, name, tag)
    drop_adoption_mark(new)                              # raté : la note `DONE_KEY` suffit à ne plus reprendre
    book = carried.book if carried.book.chosen or not old_book else carried.book._replace(chosen=old_book)
    lang = str(settings.value('options/langue', '') or '')
    language = lang if lang in i18n.LANGUAGES and lang != i18n.language() else ''
    return Adopted(name, str(old), n + carried.copied + (1 if replaced else 0), tabs, folder,
                   len(_listed(values.get(FAVORITES_KEY))), len(_listed(values.get(BIBLI_KEY))),
                   failed + bad + carried.failed + tool_bad + bad_settings, skipped,
                   more + list(book.replaced) + replaced, bool(stop), kept, language, book,
                   book_taken(book, settings), here_book, book_local)


def decline_settings(new_app_dir) -> bool:
    """Rien n'est repris (case décochée, ou application en cours non portable) : la nouvelle version, encore sans
    réglages, ne reposera pas la question à son premier lancement (`portable.offer_previous`). Vrai si c'est noté."""
    ini = pathlib.Path(new_app_dir) / INI
    if not ini.is_file() or has_settings(ini) or ADOPTED_KEY.split('/')[1] + '=' in ini.read_text(
            encoding='utf-8', errors='replace'):
        return False
    section, key = ADOPTED_KEY.split('/')
    with open(ini, 'a', encoding='utf-8') as f:
        f.write(f'\n[{section}]\n{key}=non\n')
    return True


# --- raccourcis -------------------------------------------------------------------------------------------------
def shortcut_dirs() -> dict[str, pathlib.Path]:
    """Les dossiers de raccourcis de l'utilisateur : menu Démarrer, bureau, barre des tâches (épinglés)."""
    forced = os.environ.get(ENV)
    if forced:
        base = pathlib.Path(forced) / 'raccourcis'
        return {'demarrer': base / 'demarrer', 'bureau': base / 'bureau', 'barre': base / 'barre'}
    appdata = os.environ.get('APPDATA')
    if sys.platform != 'win32' or not appdata:
        return {}
    desk = ''
    try:
        from PySide6.QtCore import QStandardPaths
        desk = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DesktopLocation)
    except Exception:                                    # noqa: BLE001 — sans Qt : le dossier habituel
        pass
    ms = pathlib.Path(appdata) / 'Microsoft'
    return {'demarrer': ms / 'Windows' / 'Start Menu' / 'Programs',
            'bureau': pathlib.Path(desk or pathlib.Path.home() / 'Desktop'),
            'barre': ms / 'Internet Explorer' / 'Quick Launch' / 'User Pinned' / 'TaskBar'}


def shortcut_targets(dirs=None) -> list[pathlib.Path]:
    """Les raccourcis (.lnk) du menu Démarrer (lui et ses sous-dossiers directs), du bureau et de la barre des
    tâches."""
    dirs = shortcut_dirs() if dirs is None else dirs
    out: list[pathlib.Path] = []
    for kind, d in dirs.items():
        d = pathlib.Path(d)
        try:
            found = sorted(d.glob('*.lnk')) + (sorted(d.glob('*/*.lnk')) if kind == 'demarrer' else [])
        except OSError:
            continue
        out += [p for p in found if p.is_file()]
    return out


def _mentions_exe(lnk: pathlib.Path) -> bool:
    """Le raccourci nomme VectorDrive.exe (texte ANSI ou UTF-16 du fichier .lnk) : seuls ceux-là sont lus par
    PowerShell."""
    try:
        data = lnk.read_bytes().lower()
    except OSError:
        return False
    name = EXE.lower()
    return name.encode('ascii') in data or name.encode('utf-16-le') in data


def _edition_in(path, versions_dir) -> str | None:
    """L'édition du dossier de version (du dossier VD) où se trouve `path` ; None : il n'est pas dans une version."""
    if versions_dir is None:
        return None
    t, root = _norm(path), _norm(versions_dir) + os.sep
    if not t.startswith(root):
        return None
    m = DIR_RE.match(t[len(root):].split(os.sep)[0])
    return (m['ed'] or '').lower() if m else None


def _ours(target: str, old_exe, versions_dir, edition: str) -> bool:
    """La cible est le VectorDrive.exe de l'ancienne version, ou celui d'une version de la MÊME édition du dossier
    VD (le raccourci d'une autre édition reste à elle)."""
    if old_exe is not None and _norm(target) == _norm(old_exe):
        return True
    return _edition_in(target, versions_dir) == edition.lower()


def _ask(runner, action: str, items: list, key: str) -> list:
    """La demande passée au `runner` par paquets (ligne de commande de PowerShell bornée) ; une réponse par élément."""
    out: list = []
    for i in range(0, len(items), 20):
        part = items[i:i + 20]
        got = list((runner({'action': action, 'liens': part}) or {}).get(key) or [])
        out += [str(x or '') for x in got[:len(part)]] + [''] * (len(part) - len(got))
    return out


def retarget_shortcuts(old_exe, new_exe, runner=None, *, dirs=None, versions_dir=None, edition: str | None = None,
                       create: bool = True) -> dict:
    """Chaque raccourci (menu Démarrer, bureau, barre des tâches) dont la cible est le VectorDrive.exe de l'ancienne
    version (`old_exe`) ou d'une version de la même édition (`edition` ; None : celle du dossier de `new_exe`) du
    dossier VD pointe désormais vers `new_exe` (cible et dossier de démarrage ; son icône n'est pas touchée) ; aucun
    raccourci de VectorDrive dans le menu Démarrer : « VectorDrive » y est créé (`create`) — sauf si un fichier de
    ce nom y est déjà, qui lance autre chose : il n'est pas réécrit.
    `runner(demande) -> réponse` lit et écrit les .lnk (d'office `run_powershell`) : {'action': 'lire', 'liens':
    [chemins]} → {'cibles': [...]}, {'action': 'ecrire', 'liens': [{'lien', 'cible', 'dossier', 'description'}]} →
    {'erreurs': [...]} ('' : fait). Jamais d'exception : rend {'changes': [...], 'cree': chemin ou None, 'erreurs':
    [...]} — une erreur de raccourci n'empêche pas la mise à jour."""
    out: dict = {'changes': [], 'cree': None, 'erreurs': []}
    runner = runner or run_powershell
    new_exe = pathlib.Path(new_exe)
    try:
        if edition is None:
            edition = _edition_in(new_exe, versions_dir) or ''
        dirs = shortcut_dirs() if dirs is None else {k: pathlib.Path(v) for k, v in dirs.items()}
        links = [p for p in shortcut_targets(dirs) if _mentions_exe(p)]
        targets = _ask(runner, 'lire', [str(p) for p in links], 'cibles') if links else []
        start = dirs.get('demarrer')
        in_start = False
        writes = []
        for p, t in zip(links, targets):
            if pathlib.PureWindowsPath(t).name.lower() != EXE.lower():
                continue
            if start is not None and _norm(p).startswith(_norm(start) + os.sep):
                in_start = True
            if _norm(t) != _norm(new_exe) and _ours(t, old_exe, versions_dir, edition):
                writes.append({'lien': str(p), 'cible': str(new_exe), 'dossier': str(new_exe.parent),
                               'description': ''})
        made = None
        if create and start is not None and not in_start and not os.path.lexists(start / 'VectorDrive.lnk'):
            start.mkdir(parents=True, exist_ok=True)
            made = start / 'VectorDrive.lnk'
            writes.append({'lien': str(made), 'cible': str(new_exe), 'dossier': str(new_exe.parent),
                           'description': 'VectorDrive'})
        errors = _ask(runner, 'ecrire', writes, 'erreurs') if writes else []
        for w, err in zip(writes, errors):
            if err:
                out['erreurs'].append(f'{w["lien"]} : {err}')
            elif made is not None and w['lien'] == str(made):
                out['cree'] = made
            else:
                out['changes'].append(pathlib.Path(w['lien']))
    except Exception as ex:                              # noqa: BLE001 — jamais une mise à jour empêchée pour cela
        out['erreurs'].append(str(ex) or ex.__class__.__name__)
    return out


def powershell_exe() -> str:
    """Le PowerShell de Windows, par son chemin complet (jamais un homonyme du dossier courant ou du PATH)."""
    root = os.environ.get('SystemRoot') or os.environ.get('WINDIR') or 'C:\\Windows'
    return str(pathlib.Path(root) / 'System32' / 'WindowsPowerShell' / 'v1.0' / 'powershell.exe')


def ps_script(request: dict) -> str:
    """Le script PowerShell d'une demande (`retarget_shortcuts`) : objet COM `WScript.Shell`, la demande et la réponse
    en JSON codé en base64 — aucun chemin dans le texte du script, aucun souci d'accents ni de guillemets. Seuls la
    cible et le dossier de démarrage d'un raccourci sont écrits (et la description d'un raccourci créé)."""
    b64 = base64.b64encode(json.dumps(request, ensure_ascii=False).encode('utf-8')).decode('ascii')
    return '; '.join((
        "$ErrorActionPreference = 'Stop'",
        f"$req = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('{b64}')) | ConvertFrom-Json",
        '$sh = New-Object -ComObject WScript.Shell',
        '$out = @()',
        "foreach ($l in $req.liens) { if ($req.action -eq 'lire') "
        "{ try { $out += [string]$sh.CreateShortcut($l).TargetPath } catch { $out += '' } } else "
        "{ try { $s = $sh.CreateShortcut($l.lien); $s.TargetPath = $l.cible; $s.WorkingDirectory = $l.dossier; "
        "if ($l.description) { $s.Description = $l.description }; $s.Save(); "
        "$out += '' } catch { $out += [string]$_.Exception.Message } } }",
        '[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes((ConvertTo-Json -InputObject @($out) -Compress)))'))


def run_powershell(request: dict, timeout: float = 30.0) -> dict:
    """Le `runner` d'office de `retarget_shortcuts` : PowerShell sans fenêtre ni profil, délai borné, dans
    l'environnement nettoyé de celui de l'exécutable empaqueté (`child_env`). Ne touche pas au registre, ne demande
    aucun droit."""
    if os.environ.get(ENV):
        raise AppUpdateError('essais : PowerShell n’est jamais lancé')
    if sys.platform != 'win32':
        raise AppUpdateError(tr('Les raccourcis ne se mettent à jour que sous Windows.'))
    try:
        r = subprocess.run([powershell_exe(), '-NoProfile', '-NonInteractive', '-WindowStyle', 'Hidden', '-Command',
                            ps_script(request)], capture_output=True, timeout=timeout, stdin=subprocess.DEVNULL,
                           creationflags=0x08000000, cwd=os.environ.get('TEMP') or None,     # CREATE_NO_WINDOW
                           env=child_env())
        data = json.loads(base64.b64decode(r.stdout.split()[-1]).decode('utf-8'))
    except (OSError, subprocess.TimeoutExpired, ValueError, IndexError) as ex:
        raise AppUpdateError(tr('PowerShell n’a pas mis les raccourcis à jour : {0}').format(
            str(ex) or ex.__class__.__name__)) from ex
    key = 'cibles' if request.get('action') == 'lire' else 'erreurs'
    return {key: [str(x or '') for x in (data if isinstance(data, list) else [data])]}


# --- lancer -----------------------------------------------------------------------------------------------------
def frozen_dirs() -> list[str]:
    """Les dossiers de l'exécutable empaqueté qui tourne (PyInstaller : `sys._MEIPASS`, le dossier `_internal`, et
    celui de l'exécutable) ; vide depuis les sources."""
    if not getattr(sys, 'frozen', False):
        return []
    out = []
    for d in (getattr(sys, '_MEIPASS', None), os.path.dirname(sys.executable or '')):
        if d:
            out.append(d)
    return out


def _inside(value: str, bases) -> bool:
    if not value or not os.path.isabs(value):            # « 1 », « offscreen » : pas un chemin
        return False
    v = _norm(value)
    return any(v == b or v.startswith(b.rstrip(os.sep) + os.sep) for b in bases)


def child_env(environ=None, bases=None) -> dict:
    """L'environnement passé à un programme lancé (la nouvelle version, PowerShell) : celui du processus, sans ce que
    PyInstaller y a mis pour l'exécutable qui tourne — variables `_PYI_…` et `_MEIPASS2`, toute variable qui pointe
    dans ses dossiers (`QT_PLUGIN_PATH`, `QML2_IMPORT_PATH` des greffons de Qt, `SSL_CERT_FILE`…), ses entrées de
    `PATH` — et avec `PYINSTALLER_RESET_ENVIRONMENT=1` : la nouvelle version est une autre application, pas un
    sous-processus. `bases` : ces dossiers (d'office `frozen_dirs()`)."""
    env = dict(os.environ if environ is None else environ)
    bases = [_norm(b) for b in (frozen_dirs() if bases is None else bases) if b]
    out = {}
    for k, v in env.items():
        up = k.upper()
        if up.startswith('_PYI_') or up in ('_MEIPASS', '_MEIPASS2'):
            continue
        parts = str(v).split(os.pathsep)
        if bases and any(_inside(x, bases) for x in parts):
            if up != 'PATH':
                continue                                 # pointe dans l'ancienne version : à elle seule
            v = os.pathsep.join(x for x in parts if x and not _inside(x, bases))
            if not v:
                continue
        out[k] = v
    out['PYINSTALLER_RESET_ENVIRONMENT'] = '1'
    return out


def _dll_directory(value):
    """Pose le dossier de DLL du processus (None : celui d'office de Windows) et rend l'ancien ('' : aucun). Un
    exécutable empaqueté en a un (PyInstaller : son dossier `_internal`), que le processus lancé hériterait."""
    import ctypes
    k = ctypes.windll.kernel32
    buf = ctypes.create_unicode_buffer(32768)
    n = k.GetDllDirectoryW(len(buf), buf)
    k.SetDllDirectoryW(value)
    return buf.value if n else ''


def launch(new_exe, popen=None):
    """Lance la nouvelle version, détachée (hors du groupe et, si Windows le permet, du « job » de celle-ci), sans
    l'attendre, dans son dossier, avec `child_env()` et sans entrée ni sortie héritées ; rend son processus
    (`wait_started` dit si elle répond). Exécutable empaqueté : le dossier de DLL de celle qui tourne est écarté le
    temps du lancement, puis rétabli — que le lancement réussisse ou non."""
    exe = pathlib.Path(new_exe)
    if popen is None and os.environ.get(ENV):
        raise AppUpdateError('essais : aucun exécutable n’est lancé')
    if not exe.is_file():
        raise AppUpdateError(tr('Exécutable introuvable : {0}').format(exe))
    flags = (0x00000008 | 0x00000200) if sys.platform == 'win32' else 0   # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    swapped = None
    if flags and getattr(sys, 'frozen', False):
        try:
            swapped = _dll_directory(None)
        except (AttributeError, OSError):
            pass
    popen = popen or subprocess.Popen
    how = {'cwd': str(exe.parent), 'env': child_env(), 'close_fds': True, 'stdin': subprocess.DEVNULL,
           'stdout': subprocess.DEVNULL, 'stderr': subprocess.DEVNULL}
    try:
        try:                                             # CREATE_BREAKAWAY_FROM_JOB : elle survit à sa fermeture
            proc = popen([str(exe)], creationflags=(flags | 0x01000000) if flags else 0, **how)
        except OSError:
            if not flags:
                raise
            proc = popen([str(exe)], creationflags=flags, **how)
    finally:
        if swapped is not None:
            try:
                _dll_directory(swapped or None)
            except (AttributeError, OSError):
                pass
    return proc if proc is not None else True


def answers(name: str | None = None) -> bool:
    """Une fenêtre de VectorDrive écoute sur le canal d'instance unique (`ui.instance.channel` : « VectorDrive- »
    suivi du nom de l'utilisateur, le même pour toutes les versions). Sous Windows, le tube nommé est seulement
    cherché (`WaitNamedPipe`), sans s'y connecter : rien n'est envoyé à la fenêtre. Essais (`VECTORDRIVE_APP_UPDATE`)
    sans nom donné : refusé."""
    if name is None:
        if os.environ.get(ENV):
            raise AppUpdateError('essais : le canal d’instance n’est jamais interrogé')
        from .ui.instance import channel
        name = channel()
    if sys.platform == 'win32':
        import _winapi
        try:
            _winapi.WaitNamedPipe('\\\\.\\pipe\\' + name, 1)
        except OSError as ex:
            return getattr(ex, 'winerror', None) == 121  # ERROR_SEM_TIMEOUT : il existe, occupé à l'instant
        return True
    import tempfile
    return os.path.exists(os.path.join(tempfile.gettempdir(), name))


def wait_started(proc, probe=None, timeout: float = START_TIMEOUT, step: float = 0.25) -> str:
    """Attend que la version lancée réponde sur le canal d'instance unique (`probe`, d'office `answers`) — elle n'y
    écoute qu'une fois sa fenêtre prête — tant que son processus vit, `timeout` secondes au plus, annulable
    (`core.progress`). Rend 'ok', 'arretee' (son processus s'est arrêté) ou 'muette' (pas de réponse à temps). Un
    lanceur qui ne rend pas de processus : seul le canal compte."""
    poll = getattr(proc, 'poll', None)
    probe = probe or answers
    t0 = time.monotonic()
    while True:
        elapsed = time.monotonic() - t0
        _report(min(1.0, elapsed / timeout) if timeout > 0 else 1.0, tr('En attente de la nouvelle version'))
        if poll is not None and poll() is not None:
            return 'arretee'
        if probe():
            return 'arretee' if poll is not None and poll() is not None else 'ok'
        if elapsed >= timeout:
            return 'muette'
        time.sleep(step)
