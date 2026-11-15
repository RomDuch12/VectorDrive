"""Mode portable : VectorDrive lancé depuis une clé USB ou un partage sans
installation.

Il est actif quand un fichier `VectorDrive.ini` se trouve à côté de
l'exécutable (la version portable est livrée avec ce fichier vide) :

* les réglages (options F10, polices, plaques…) vont dans ce fichier au
  lieu du registre du poste — ils suivent la clé ;
* les données de travail (cache des polices, fichiers de récupération)
  vont dans le dossier `donnees` à côté de l'exécutable ;
* une mise à jour remplace le contenu du dossier par celui de l'archive
  portable de la nouvelle version (réglages et données gardés), puis
  relance VectorDrive ;
* une version neuve décompressée dans un autre dossier, à côté de la
  précédente, propose à son premier lancement d'en reprendre les réglages
  et les données (`offer_previous`) : rien n'est copié sans réponse, rien
  n'est changé dans l'ancien dossier.

`VECTORDRIVE_SETTINGS` (tests) garde la priorité sur tout le reste ;
`VECTORDRIVE_PORTABLE_DIR` désigne le dossier de l'application depuis les
sources (essais).
"""
from __future__ import annotations

import os
import pathlib
import subprocess
import sys
import tempfile
import zipfile

INI = 'VectorDrive.ini'
DATA = 'donnees'


def app_dir() -> pathlib.Path | None:
    """Dossier de l'exécutable empaqueté (ou de l'essai), sinon None."""
    forced = os.environ.get('VECTORDRIVE_PORTABLE_DIR')
    if forced:
        return pathlib.Path(forced)
    if getattr(sys, 'frozen', False):
        return pathlib.Path(sys.executable).resolve().parent
    return None


def is_portable() -> bool:
    d = app_dir()
    return d is not None and (d / INI).is_file()


def settings():
    """QSettings de l'application : fichier des tests, fichier portable ou
    registre du poste."""
    from PySide6.QtCore import QSettings
    ini = os.environ.get('VECTORDRIVE_SETTINGS')
    if ini:
        return QSettings(ini, QSettings.Format.IniFormat)
    if is_portable():
        return QSettings(str(app_dir() / INI), QSettings.Format.IniFormat)
    s = QSettings(ORG, 'VectorDrive')
    if not s.allKeys():
        _migrate(s)
    return s


#: éditeur des réglages du poste (registre) ; avant la v0.95 : « BFM »
ORG = 'VectorDrive'
OLD_ORGS = ('BFM',)


def _migrate(new) -> None:
    """Réglages d'une version antérieure (rangés sous un autre éditeur)
    repris une fois."""
    from PySide6.QtCore import QSettings
    for org in OLD_ORGS:
        old = QSettings(org, 'VectorDrive')
        keys = old.allKeys()
        if keys:
            for k in keys:
                new.setValue(k, old.value(k))
            new.sync()
            return


#: clé posée dans un VectorDrive.ini neuf après la question : elle n'est posée qu'une fois
ADOPTED_KEY = 'portable/reprise'
#: dossiers de `donnees` laissés à l'ancienne version (fichiers de récupération de ses dessins)
NOT_ADOPTED = ('recuperation',)


def _has_settings(ini: pathlib.Path) -> bool:
    from PySide6.QtCore import QSettings
    return ini.is_file() and bool(QSettings(str(ini), QSettings.Format.IniFormat).allKeys())


def previous_portable(app: pathlib.Path | None = None) -> pathlib.Path | None:
    """Le dossier d'une autre version portable posée à côté de celle-ci (dossiers voisins du dossier décompressé), qui a des
    réglages ; la plus récemment utilisée. None : aucune."""
    app = pathlib.Path(app or app_dir() or '')
    box = app.parent
    found = []
    try:
        near = [d for d in box.parent.iterdir() if d.is_dir() and d != box]
    except OSError:
        return None
    for d in near:
        for cand in (d / 'VectorDrive', d):
            if (cand / 'VectorDrive.exe').is_file() and _has_settings(cand / INI):
                found.append(cand)
                break
    return max(found, key=lambda c: (c / INI).stat().st_mtime) if found else None


def adopt(src: pathlib.Path, dst: pathlib.Path | None = None) -> int:
    """Les réglages de la version portable `src` copiés dans le VectorDrive.ini de `dst` (celle-ci), puis ses données (`donnees`, sans
    les fichiers de récupération, et `bibliotheque`), fichier par fichier, sans jamais remplacer un fichier déjà là. Rend le nombre de
    fichiers copiés."""
    import shutil
    from PySide6.QtCore import QSettings
    dst = pathlib.Path(dst or app_dir())
    old = QSettings(str(src / INI), QSettings.Format.IniFormat)
    new = QSettings(str(dst / INI), QSettings.Format.IniFormat)
    for k in old.allKeys():
        new.setValue(k, old.value(k))
    new.setValue(ADOPTED_KEY, src.parent.name if src.name == 'VectorDrive' else src.name)
    new.sync()
    n = 0
    for sub in (DATA, 'bibliotheque'):
        base = src / sub
        if not base.is_dir():
            continue
        for f in base.rglob('*'):
            rel = f.relative_to(base)
            if not f.is_file() or (sub == DATA and rel.parts and rel.parts[0] in NOT_ADOPTED):
                continue
            to = dst / sub / rel
            if to.exists():
                continue
            to.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, to)
            n += 1
    return n


def offer_previous(ask=None) -> pathlib.Path | None:
    """Au premier lancement d'une version portable neuve (VectorDrive.ini encore vide), s'il y a une version portable à côté :
    `ask(dossier)` (par défaut une question) décide de reprendre ses réglages et ses données. Dans les deux cas la question n'est plus
    posée. Rend le dossier repris, sinon None."""
    if os.environ.get('VECTORDRIVE_SETTINGS') or not is_portable():
        return None
    ini = app_dir() / INI
    if _has_settings(ini):
        return None
    src = previous_portable()
    if src is None:
        return None
    if ask is None:
        ask = _ask_adopt
    name = src.parent.name if src.name == 'VectorDrive' else src.name
    if ask(name):
        adopt(src)
        return src
    from PySide6.QtCore import QSettings
    s = QSettings(str(ini), QSettings.Format.IniFormat)
    s.setValue(ADOPTED_KEY, 'non')
    s.sync()
    return None


def _ask_adopt(name: str) -> bool:
    from PySide6.QtWidgets import QMessageBox
    from .i18n import tr
    box = QMessageBox(QMessageBox.Icon.Question, tr('VectorDrive portable'),
                      tr('Première ouverture de cette version portable. Reprendre les réglages et les données de la version posée à '
                         'côté (« {0} ») ?').format(name))
    box.setInformativeText(tr('Options, derniers dossiers, outils, modèles, thèmes et polices ajoutées. Rien n\'est changé dans '
                              'l\'ancien dossier. La question n\'est posée qu\'une fois.'))
    yes = box.addButton(tr('Reprendre ses réglages'), QMessageBox.ButtonRole.AcceptRole)
    box.addButton(tr('Partir de zéro'), QMessageBox.ButtonRole.RejectRole)
    box.setDefaultButton(yes)
    box.exec()
    return box.clickedButton() is yes


def data_dir() -> pathlib.Path:
    """Dossier des données de travail (cache, récupération)."""
    if is_portable():
        d = app_dir() / DATA
    else:
        d = pathlib.Path(os.environ.get('LOCALAPPDATA') or pathlib.Path.home()) / 'VectorDrive'
    return d


def launch_portable_update(archive, *, pid: int | None = None, target: pathlib.Path | None = None,
                           start: bool = True) -> pathlib.Path:
    """Décompresse l'archive portable et lance un script qui attend la fin de
    VectorDrive, recopie le nouveau contenu sur le dossier (sans toucher à
    `VectorDrive.ini` ni à `donnees`) puis relance l'exécutable. Renvoie le
    chemin du script."""
    target = pathlib.Path(target or app_dir())
    work = pathlib.Path(tempfile.mkdtemp(prefix='vectordrive_portable_'))
    with zipfile.ZipFile(archive) as z:
        z.extractall(work)
    # l'archive contient un dossier VectorDrive/ (ou directement les fichiers)
    src = work / 'VectorDrive' if (work / 'VectorDrive' / 'VectorDrive.exe').exists() else work
    pid = pid or os.getpid()
    script = work / 'appliquer_maj.cmd'
    script.write_text('\r\n'.join([
        '@echo off',
        ':attente',
        f'tasklist /FI "PID eq {pid}" 2>nul | find "{pid}" >nul && (timeout /t 1 /nobreak >nul & goto attente)',
        f'robocopy "{src}" "{target}" /E /XF {INI} /XD {DATA} /R:3 /W:1 /NFL /NDL /NJH /NJS >nul',
        f'start "" "{target / "VectorDrive.exe"}"',
        '',
    ]), encoding='cp1252')
    if start:
        subprocess.Popen(['cmd', '/c', str(script)], close_fds=True,
                         creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    return script


def make_archive(dist_dir: pathlib.Path, out: pathlib.Path) -> pathlib.Path:
    """Archive portable : le dossier de l'application et un VectorDrive.ini
    vide (qui active le mode portable)."""
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for f in sorted(dist_dir.rglob('*')):
            if f.is_file():
                z.write(f, pathlib.PurePosixPath('VectorDrive') / f.relative_to(dist_dir).as_posix())
        z.writestr('VectorDrive/' + INI, '; VectorDrive portable : réglages enregistrés ici\n')
    return out
