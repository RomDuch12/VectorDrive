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
  n'est changé dans l'ancien dossier ; plusieurs : on choisit laquelle ;
  ses onglets (parcours calculés compris) passent comme à une mise à jour.

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


def settings(migrate: bool = True):
    """QSettings de l'application : fichier des tests, fichier portable ou
    registre du poste. `migrate=False` : pour lire seulement (le pont MCP) — les
    réglages d'un ancien éditeur ne sont pas repris à cette occasion."""
    from PySide6.QtCore import QSettings
    ini = os.environ.get('VECTORDRIVE_SETTINGS')
    if ini:
        return QSettings(ini, QSettings.Format.IniFormat)
    if is_portable():
        return QSettings(str(app_dir() / INI), QSettings.Format.IniFormat)
    s = QSettings(ORG, 'VectorDrive')
    if migrate and not s.allKeys():
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
#: réponse « Réessayer » de la question quand l'ancienne version est encore ouverte : re-tester
RETRY = 'reessayer'
#: le verrou de la session d'une version (`MainWindow.start_session`) : seulement lu ici, jamais pris ni effacé
SESSION_LOCK = 'session.lock'
#: la reprise faite à ce lancement (`offer_previous`, `app_update.Adopted`) : la fenêtre en dit le bilan
LAST = None
#: dans le dossier de cette version : la marque « reprise en cours » (posée avant les copies, effacée après les
#: réglages ; restée là, le lancement suivant termine la reprise) et le verrou de la question (un second lancement
#: attend qu'elle soit finie)
ADOPTING = 'reprise_en_cours.json'
ADOPT_LOCK = 'reprise.lock'
#: l'étiquette de la dernière reprise finie, dans VectorDrive.ini : une marque restée (effacement raté) ne compte plus
DONE_KEY = 'portable/reprise_faite'
#: un second lancement attend la question d'un autre au plus ce temps (ms), puis démarre sans reprise
ADOPT_WAIT_MS = 180_000
#: réponse « plus tard » (bouton, Échap, fermeture) : rien n'est posé par la question ; la fenêtre écrivant ensuite
#: ses réglages, elle ne revient pas — F10 › Mises à jour › « Reprendre d’une ancienne version… »
LATER = 'plus_tard'
#: ce lancement a attendu la question d'un autre (`offer_previous`) : son fichier passe à la fenêtre de l'autre
WAITED = False
#: le délai écoulé, un autre lancement fait encore la reprise : ce lancement passe son fichier à l'autre ou le dit
#: (`tell_busy`), et se ferme — jamais deux fenêtres sur la même reprise
BUSY = False
#: « Ouvrir quand même » pendant l'attente : la fenêtre s'ouvre sans reprise et sans rouvrir les passages
FORCED = False
#: pourquoi `_adoption_lock` n'a pas pris le verrou : '', 'delai', 'erreur' ou 'ouvrir'
WAIT_END = ''


def _has_settings(ini: pathlib.Path) -> bool:
    from PySide6.QtCore import QSettings
    return ini.is_file() and bool(QSettings(str(ini), QSettings.Format.IniFormat).allKeys())


def _label(app: pathlib.Path) -> str:
    return app.parent.name if app.name == 'VectorDrive' else app.name


def _is_link_path(p) -> bool:
    return os.path.islink(p) or bool(getattr(os.path, 'isjunction', lambda _p: False)(p))


def _neighbors(app: pathlib.Path | None = None) -> list[pathlib.Path]:
    """Les dossiers d'application des autres versions portables posées à côté de celle-ci (dossiers voisins du
    dossier décompressé) qui ont des réglages. Rapide : ni description ni fenêtre."""
    app = pathlib.Path(app or app_dir() or '')
    box = app.parent
    mine = {os.path.normcase(os.path.abspath(p)) for p in (box, app)}
    try:
        mine |= {os.path.normcase(os.path.realpath(p)) for p in (box, app)}      # une seule fois
    except (OSError, ValueError):
        pass

    def is_mine(p) -> bool:                              # chemin résolu seulement pour un lien ou une jonction
        if os.path.normcase(os.path.abspath(p)) in mine:
            return True
        return _is_link_path(p) and os.path.normcase(os.path.realpath(p)) in mine
    try:
        near = [d for d in box.parent.iterdir() if d.is_dir() and not is_mine(d)]
    except OSError:
        return []
    found = []
    for d in near:
        for cand in (d / 'VectorDrive', d):
            try:
                ok = (cand / 'VectorDrive.exe').is_file() and _has_settings(cand / INI) and not is_mine(cand)
            except OSError:
                ok = False
            if ok:
                found.append(cand)
                break
    return found


def previous_portables(app: pathlib.Path | None = None) -> list:
    """Toutes les versions portables posées à côté, décrites (`app_update.describe` : version, édition, dernière
    utilisation, onglets, bibliothèque, dossiers favoris…), la présélectionnée d'abord (`app_update.preferred` : même
    édition que celle-ci, puis la plus récente qui a servi pour de vrai…). Retour terrain du 27/11 (« reprendre ses
    réglages oublie … dossiers favoris ») : avant, seule celle dont VectorDrive.ini était le plus récent était
    proposée — une version lancée une fois pour essai passait devant celle de tous les jours."""
    from . import app_update as AU
    app = pathlib.Path(app or app_dir() or '')
    return AU.preferred([AU.describe(c) for c in _neighbors(app)], AU.current_edition(app))


def previous_portable(app: pathlib.Path | None = None) -> pathlib.Path | None:
    """Le dossier de la version posée à côté présélectionnée (`previous_portables`) ; None : aucune."""
    found = previous_portables(app)
    return found[0].app if found else None


def _writable(app: pathlib.Path) -> bool:
    """Le dossier de cette version et son VectorDrive.ini s'écrivent (ouverts en ajout sans rien écrire, un fichier
    provisoire créé puis effacé) : sinon aucune reprise n'est possible, ni même retenue la réponse."""
    try:
        ini = app / INI
        if ini.exists():
            with open(ini, 'ab'):
                pass
        with tempfile.TemporaryFile(dir=app):
            pass
    except OSError:
        return False
    return True


def adoption_mark(app) -> dict | None:
    """La marque « reprise en cours » de la version `app` ({'source', 'tag', 'tries', 'session'}), ou None — aussi
    quand VectorDrive.ini dit cette reprise finie (`DONE_KEY` : la marque n'a pas pu être effacée ; nouvel essai)."""
    import json
    from PySide6.QtCore import QSettings
    f = pathlib.Path(app) / ADOPTING
    try:
        data = json.loads(f.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or not isinstance(data.get('source'), str) or not isinstance(data.get('tag'), str):
        return None
    ini = pathlib.Path(app) / INI
    if ini.is_file() and str(QSettings(str(ini), QSettings.Format.IniFormat).value(DONE_KEY, '')) == data['tag']:
        drop_adoption_mark(app)
        return None
    return data


def write_adoption_mark(app, source, tag: str, *, tries: int = 1, session: bool = False) -> None:
    """Pose la marque « reprise en cours » (d'un coup : nom provisoire, puis `os.replace`) : la source, l'étiquette,
    les tentatives faites, la session déjà passée ou non."""
    import datetime
    import json
    app = pathlib.Path(app)
    part = app / (ADOPTING + '.tmp')
    part.write_text(json.dumps({'source': str(source), 'tag': tag, 'tries': int(tries), 'session': bool(session),
                                'date': datetime.datetime.now().isoformat(timespec='seconds')},
                               ensure_ascii=False), encoding='utf-8')
    os.replace(part, app / ADOPTING)


def drop_adoption_mark(app) -> None:
    try:
        (pathlib.Path(app) / ADOPTING).unlink(missing_ok=True)
    except OSError:
        pass


def adoption_pending() -> bool:
    """Une reprise attend (demande du 27/11) : version portable dont le dossier s'écrit (`_writable` : sinon rien ne
    serait jamais retenu et chaque lancement ouvrirait une fenêtre de plus), et une reprise commencée puis coupée
    (`ADOPTING`), ou VectorDrive.ini encore sans valeur (la question n'a jamais été posée) et une version posée à
    côté. Rapide, sans fenêtre : `VectorDrive.py` ne passe alors pas ce lancement à la fenêtre déjà ouverte —
    l'ancienne version, encore ouverte, l'aurait reçu et celle-ci se serait arrêtée sans rien proposer."""
    if os.environ.get('VECTORDRIVE_SETTINGS') or not is_portable():
        return False
    app = app_dir()
    if adoption_mark(app) is None and (_has_settings(app / INI) or not _neighbors(app)):
        return False
    return _writable(app)


def launch_adopting(new_window: bool, lots) -> bool:
    """Au lancement (`VectorDrive.py`) : une reprise attend (`adoption_pending`) — jamais pour une fenêtre à part ni
    le traitement par lots (son chemin à lui reste tel quel) ; une erreur : faux (jamais un lancement empêché)."""
    if new_window or lots:
        return False
    try:
        return adoption_pending()
    except Exception:                                    # noqa: BLE001
        return False


def _k32():
    import ctypes
    from ctypes import wintypes
    k = ctypes.WinDLL('kernel32', use_last_error=True)
    k.OpenProcess.restype = wintypes.HANDLE
    k.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    k.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
    k.QueryFullProcessImageNameW.argtypes = (wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                                             ctypes.POINTER(wintypes.DWORD))
    k.CloseHandle.argtypes = (wintypes.HANDLE,)
    return k


def _image_of(k, h) -> str:
    import ctypes
    from ctypes import wintypes
    buf = ctypes.create_unicode_buffer(32768)
    size = wintypes.DWORD(len(buf))
    return buf.value if k.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)) else ''


def _process(pid: int) -> tuple[bool, str]:
    """(le processus `pid` vit ; le nom de son exécutable sans extension, '' : illisible)."""
    if pid <= 0:
        return False, ''
    if sys.platform == 'win32':
        import ctypes
        from ctypes import wintypes
        k = _k32()
        h = k.OpenProcess(0x1000, False, pid)           # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return ctypes.get_last_error() == 5, ''      # accès refusé : il vit (un autre compte)
        try:
            code = wintypes.DWORD()
            if k.GetExitCodeProcess(h, ctypes.byref(code)) and code.value != 259:     # STILL_ACTIVE
                return False, ''
            image = _image_of(k, h)
            return True, pathlib.PureWindowsPath(image).stem if image else ''
        finally:
            k.CloseHandle(h)
    try:
        os.kill(pid, 0)
    except PermissionError:
        return True, ''
    except OSError:
        return False, ''
    return True, ''


def _processes() -> list[tuple[int, str]]:
    """Les processus lancés : [(numéro, exécutable)] (Windows ; ceux d'un autre compte, illisibles, ne sont pas
    vus), sans celui-ci. Rien n'est envoyé à aucun d'eux."""
    if sys.platform != 'win32':
        return []
    import ctypes
    from ctypes import wintypes
    psapi = ctypes.WinDLL('psapi', use_last_error=True)
    arr = (wintypes.DWORD * 8192)()
    got = wintypes.DWORD()
    if not psapi.EnumProcesses(arr, ctypes.sizeof(arr), ctypes.byref(got)):
        return []
    k = _k32()
    me = os.getpid()
    out = []
    for pid in arr[:got.value // ctypes.sizeof(wintypes.DWORD)]:
        if not pid or pid == me:
            continue
        h = k.OpenProcess(0x1000, False, pid)
        if not h:
            continue
        try:
            image = _image_of(k, h)
        finally:
            k.CloseHandle(h)
        if image:
            out.append((int(pid), image))
    return out


def _image_paths() -> list[str]:
    """Les exécutables des processus lancés (`_processes`)."""
    return [image for _pid, image in _processes()]


def _windowed_pids() -> set[int]:
    """Les processus qui ont une fenêtre visible de premier niveau (Windows : `EnumWindows`, sans propriétaire) —
    seulement lues, rien ne leur est envoyé."""
    if sys.platform != 'win32':
        return set()
    import ctypes
    from ctypes import wintypes
    u = ctypes.WinDLL('user32', use_last_error=True)
    proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    u.EnumWindows.argtypes = (proc, wintypes.LPARAM)
    u.IsWindowVisible.argtypes = (wintypes.HWND,)
    u.GetWindow.argtypes = (wintypes.HWND, wintypes.UINT)
    u.GetWindow.restype = wintypes.HWND
    u.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
    out: set[int] = set()

    def each(hwnd, _param):
        if u.IsWindowVisible(hwnd) and not u.GetWindow(hwnd, 4):     # GW_OWNER : fenêtre de premier niveau
            pid = wintypes.DWORD()
            u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            out.add(int(pid.value))
        return True
    callback = proc(each)
    u.EnumWindows(callback, 0)
    return out


def running_from(app) -> bool:
    """Une fenêtre de la version `app` est ouverte : un processus lancé depuis son VectorDrive.exe, qui a une fenêtre
    visible de premier niveau (2e relecture du 27/11 : ouverte avec sa session coupée, elle ne tient aucun verrou de
    session ; 3e : son pont MCP `--mcp` ou son serveur de vignettes, sans fenêtre, ne comptent pas). Le canal
    d'instance ne dit pas quelle version l'écoute : les processus sont seulement listés, rien ne leur est envoyé.
    Jamais bloquant : une erreur vaut « pas ouverte »."""
    try:
        want = os.path.normcase(os.path.realpath(pathlib.Path(app) / 'VectorDrive.exe'))
        hits = {pid for pid, image in _processes() if os.path.basename(image).lower() == 'vectordrive.exe'
                and os.path.normcase(os.path.realpath(image)) == want}
        return bool(hits) and bool(hits & _windowed_pids())
    except Exception:                                    # noqa: BLE001
        return False


def _local_host(host: str) -> bool:
    """Le nom de poste écrit dans un verrou est celui-ci : Qt (Windows) y met COMPUTERNAME (NetBIOS, en capitales,
    15 caractères au plus) ; `QSysInfo.machineHostName` est gardé en second. Sans casse."""
    from PySide6.QtCore import QSysInfo
    names = {QSysInfo.machineHostName().lower()}
    if os.environ.get('COMPUTERNAME'):
        names.add(os.environ['COMPUTERNAME'].lower())
    return str(host).lower() in names


def session_held(app) -> bool:
    """La version portable `app` est ouverte : un processus tourne depuis son exécutable (`running_from`), ou une
    fenêtre tient sa session (`donnees/session/session.lock`, `MainWindow.start_session`). Le verrou est seulement lu
    (`QLockFile.getLockInfo`) : jamais pris, modifié ni effacé — mort (son processus arrêté, son numéro repris par un
    autre programme, ou celui de ce processus-ci) il reste tel quel, et ne compte pas. Tenu depuis un autre poste :
    compté tenu (rien ne permet de le vérifier d'ici)."""
    if running_from(app):
        return True
    lock = pathlib.Path(app) / DATA / 'session' / SESSION_LOCK
    try:
        if not lock.is_file():
            return False
    except OSError:
        return False
    from PySide6.QtCore import QLockFile
    try:
        pid, host, name = QLockFile(str(lock)).getLockInfo()
    except (TypeError, ValueError):
        return False
    if not pid:
        return False
    if host and not _local_host(host):                   # un autre poste : rien ne permet de le vérifier d'ici
        return True
    if int(pid) == os.getpid():                          # pas l'ancienne version : un numéro repris
        return False
    alive, exe = _process(int(pid))
    if not alive:
        return False
    return not (exe and name and exe.lower() != pathlib.PurePath(str(name)).stem.lower())   # numéro repris


def adopt(src: pathlib.Path, dst: pathlib.Path | None = None, *, settings=None, keep: bool = True, progress=None):
    """Reprend la version portable `src` dans `dst` (celle-ci) : `app_update.adopt_previous` — sa session passée
    d'abord comme une mise à jour (onglets, dessins modifiés, parcours calculés, mémo du calcul), ses données et sa
    bibliothèque fichier par fichier (`keep` : rien de déjà là n'est remplacé ; « Mes outils » fusionnés), ses
    réglages en dernier (dossiers favoris et de la bibli compris), sans récupération ni verrou. `progress(fn)` : les
    copies. Rend `app_update.Adopted` : fichiers, onglets, remplacés, échecs."""
    from . import app_update as AU
    return AU.adopt_previous(pathlib.Path(src), pathlib.Path(dst or app_dir()), settings=settings, keep=keep,
                             progress=progress)


def _decline(ini: pathlib.Path) -> None:
    from PySide6.QtCore import QSettings
    s = QSettings(str(ini), QSettings.Format.IniFormat)
    s.setValue(ADOPTED_KEY, 'non')
    s.sync()


def _free_stale(lock) -> bool:
    """`reprise.lock` tenu (3e relecture du 27/11 : un verrou laissé par un autre poste — clé USB, partage — ou par
    une reprise coupée n'était jamais repris) : écrit par un autre poste, ou par un processus de ce poste qui ne
    tourne plus (ou dont le numéro est repris par un autre programme) → effacé (`removeStaleLockFile`). Sous Windows
    l'effacement échoue tant qu'un processus vivant tient le fichier ouvert, d'ici ou d'ailleurs : c'est le test de
    vie. Jamais celui de ce processus. Rend vrai si effacé."""
    try:
        pid, host, name = lock.getLockInfo()
    except (TypeError, ValueError):
        pid, host, name = 0, '', ''
    if pid and (not host or _local_host(host)):
        if int(pid) == os.getpid():
            return False
        alive, exe = _process(int(pid))
        if alive and not (exe and name and exe.lower() != pathlib.PurePath(str(name)).stem.lower()):
            return False                                 # un autre lancement, vivant : il finit d'abord
    try:
        return bool(lock.removeStaleLockFile())
    except Exception:                                    # noqa: BLE001
        return False


def _adoption_lock(app: pathlib.Path, wait_ms: int = 0, waiting=None):
    """Le verrou de la question (`ADOPT_LOCK`, dans le dossier de cette version : un second lancement pendant la
    question attend qu'elle soit finie, jamais deux questions) : QLockFile pris, ou None, la raison dans `WAIT_END` —
    'delai' (`wait_ms` écoulé, toujours borné : le verrou est tenu par un vivant), 'erreur' (toute autre erreur que
    « tenu par un autre » : droits, erreur inconnue — jamais une boucle sans fin), 'ouvrir' (`waiting()`, appelé
    entre deux essais, a rendu faux : « Ouvrir quand même »). Un verrou mort (`_free_stale`) est effacé et repris."""
    global WAIT_END
    import time
    from PySide6.QtCore import QLockFile
    lock = QLockFile(str(app / ADOPT_LOCK))
    lock.setStaleLockTime(0)
    end = time.monotonic() + max(0, wait_ms) / 1000
    WAIT_END = ''
    while True:
        if lock.tryLock(0):
            return lock
        if lock.error() != QLockFile.LockError.LockFailedError:
            WAIT_END = 'erreur'
            return None
        if _free_stale(lock) and lock.tryLock(0):
            return lock
        if time.monotonic() >= end:
            WAIT_END = 'delai'
            return None
        if waiting is None:
            time.sleep(0.2)
        elif not waiting():
            WAIT_END = 'ouvrir'
            return None


class _WaitBox:
    """La petite fenêtre d'un second lancement qui attend la reprise d'un autre (3e relecture du 27/11 : jamais une
    attente invisible) : « Reprise en cours dans une autre fenêtre de VectorDrive… » et « Ouvrir quand même ».
    Appelée entre deux essais du verrou : laisse vivre la fenêtre 200 ms, rend faux une fois le bouton cliqué. Échap
    et la croix ne font rien (l'attente reste bornée)."""

    def __init__(self):
        self.dialog = None
        self.forced = False

    def __call__(self) -> bool:
        from PySide6.QtCore import QEventLoop, QTimer
        if self.dialog is None:
            self.dialog = self._build()
        loop = QEventLoop()
        QTimer.singleShot(200, loop.quit)
        loop.exec()
        return not self.forced

    def _build(self):
        from PySide6.QtWidgets import QDialog, QLabel, QPushButton, QVBoxLayout
        from .i18n import tr

        class Box(QDialog):
            def reject(self):                            # Échap : on attend toujours
                pass

            def closeEvent(self, e):                     # la croix : de même
                e.ignore()
        dlg = Box()
        dlg.setWindowTitle(tr('VectorDrive portable'))
        lay = QVBoxLayout(dlg)
        lay.addWidget(QLabel(tr('Une reprise d’une ancienne version est en cours, sur ce poste ou un autre… Ce '
                                'lancement attend qu’elle soit finie (3 min au plus).')))
        btn = QPushButton(tr('Ouvrir quand même'))
        btn.setObjectName('adoptOpenAnyway')
        btn.clicked.connect(lambda: setattr(self, 'forced', True))
        lay.addWidget(btn)
        dlg.show()
        return dlg

    def close(self) -> None:
        if self.dialog is not None:
            self.dialog.hide()
            self.dialog.deleteLater()
            self.dialog = None


def tell_busy(paths=()) -> bool:
    """Le délai écoulé pendant qu'un autre lancement fait encore la reprise (`BUSY`) et son canal pas encore ouvert :
    ce lancement le dit, avec ses fichiers (`paths` : un chemin ou une liste) à rouvrir ensuite, et se ferme —
    jamais deux fenêtres sur la même reprise (3e relecture) — sauf « Ouvrir quand même » (4e relecture) : rend
    vrai. Fermer, Échap, la croix : faux."""
    from PySide6.QtWidgets import QApplication, QMessageBox
    from .i18n import tr
    if QApplication.instance() is None:
        return False
    names = [paths] if isinstance(paths, str) else list(paths or [])
    names = [str(n) for n in names if n]
    box = QMessageBox(QMessageBox.Icon.Information, tr('VectorDrive portable'),
                      tr('Une reprise d’une ancienne version est en cours, sur ce poste ou un autre : la fenêtre '
                         'de VectorDrive s’ouvrira à la fin de la copie.'))
    if names:
        box.setInformativeText(tr('À rouvrir ensuite : {0}').format(' ; '.join(names)))
    close = box.addButton(tr('Fermer'), QMessageBox.ButtonRole.RejectRole)
    anyway = box.addButton(tr('Ouvrir quand même'), QMessageBox.ButtonRole.ActionRole)
    box.setDefaultButton(close)
    box.setEscapeButton(close)
    box.exec()
    return box.clickedButton() is anyway


def run_with_progress(fn, parent=None):
    """Les copies d'une reprise dans une petite fenêtre de progression (avant la fenêtre principale au premier
    lancement), Annuler pris entre deux fichiers (`core.progress.check`) ; sans application Qt : directement."""
    from PySide6.QtWidgets import QApplication
    if QApplication.instance() is None:
        return fn()
    from .core import progress as CP
    from .i18n import tr
    from .ui import progress as UP

    def work():
        t = CP.current()
        if t is not None:
            t.fraction = -1.0                            # durée inconnue : barre animée
            t.text = tr('Onglets, bibliothèque, données… (Annuler : entre deux fichiers)')
        return fn()
    return UP.run(parent, tr('Reprise de l’ancienne version : copie des fichiers'), work)


def offer_previous(ask=None, choose=None, progress=None, wait_ms: int | None = None,
                   waiting=None, busy: bool = True) -> pathlib.Path | None:
    """Au premier lancement d'une version portable neuve (VectorDrive.ini encore vide), s'il y a des versions
    portables à côté : plusieurs, `choose(candidats)` (d'office une liste où choisir, `_choose_previous`) rend celle
    à reprendre ou None ; une seule, `ask(nom)` (d'office une question qui montre son dossier) décide. Encore ouverte
    (`session_held`) : `ask(nom, held=True)` rend `RETRY` (re-tester), vrai (reprendre sans attendre : la dernière
    session qu'elle a enregistrée), `LATER` (plus tard : rien de posé, la marque d'une reprise coupée gardée) ou
    faux. Une reprise coupée (`ADOPTING`) est terminée sans nouvelle question (seulement celle de l'ancienne encore
    ouverte). Un second lancement pendant la question attend qu'elle soit finie (`_adoption_lock`, `wait_ms`, d'office
    `ADOPT_WAIT_MS` ; `waiting()` entre deux essais, d'office la petite fenêtre `_WaitBox`) puis ne redemande jamais
    rien (`WAITED`) ; « Ouvrir quand même » : `FORCED` ; le délai écoulé, l'autre la fait encore : `BUSY` (ce
    lancement passe son fichier à l'autre, ou le dit, et se ferme). Un verrou mort (autre poste, processus arrêté) est
    repris. Dossier non inscriptible : rien. Échap ou fermeture (`LATER`) : rien n'est posé par la question, mais la
    fenêtre qui s'ouvre écrit ses réglages (place, barre des tâches) : elle ne revient pas — plus tard, c'est F10 ›
    Mises à jour › « Reprendre d’une ancienne version… » (dit dans la question). Les copies : `progress(fn)`, d'office
    une fenêtre de progression (`run_with_progress`). `busy` faux (un script lancé, 4e relecture) : un verrou tenu
    par un vivant → aucune attente, ni `BUSY` : le lancement continue sans reprise. Rend le dossier repris (le bilan
    dans `LAST`), sinon None."""
    global WAITED, BUSY, FORCED
    if os.environ.get('VECTORDRIVE_SETTINGS') or not is_portable():
        return None
    app = app_dir()
    ini = app / INI
    if (adoption_mark(app) is None and _has_settings(ini)) or not _writable(app):
        return None
    lock = _adoption_lock(app)
    if lock is None and WAIT_END == 'delai' and busy:    # un autre lancement pose la question : il finit d'abord
        box = None
        if waiting is None:
            from PySide6.QtWidgets import QApplication
            box = _WaitBox() if QApplication.instance() is not None else None
        try:
            lock = _adoption_lock(app, ADOPT_WAIT_MS if wait_ms is None else wait_ms,
                                  waiting if waiting is not None else box)
        finally:
            if box is not None:
                box.close()
        if lock is None:
            if WAIT_END == 'ouvrir':                     # « Ouvrir quand même » : sans reprise, sans son passage
                FORCED = True
            elif WAIT_END == 'delai':                    # tenu par un vivant : l'autre copie encore
                BUSY = True
            return None
        WAITED = True
    if lock is None:                                     # verrou en erreur : lancement sans reprise
        return None
    try:
        mark = adoption_mark(app)
        if mark is None and (WAITED or _has_settings(ini)):   # répondu par l'autre (même « plus tard ») : jamais
            return None                                       # redemandé
        return _offer(app, ini, mark, ask, choose, progress or run_with_progress)
    finally:
        lock.unlock()


def _offer(app, ini, mark, ask, choose, progress):
    if mark is not None:
        from . import app_update as AU
        src = AU.old_app_of(mark['source'])
        if src is not None:                              # coupée : terminée, déjà acceptée
            return _adopt_now(app, ini, src, ask, progress, chosen=True)
        drop_adoption_mark(app)                          # l'ancienne n'est plus là : rien à terminer
        if _has_settings(ini):
            return None
    found = previous_portables(app)
    if not found:
        return None
    chosen = False
    if len(found) > 1:
        pick = (choose or _choose_previous)(found)
        if pick is None or (isinstance(pick, str) and pick == LATER):
            if pick is None:                             # « Partir de zéro » ; Échap : plus tard (F10)
                _decline(ini)
            return None
        src, chosen = pick.app, True
    else:
        src = found[0].app
    return _adopt_now(app, ini, src, ask, progress, chosen)


def _adopt_now(app, ini, src, ask, progress, chosen: bool):
    global LAST
    name = _label(src)
    if ask is None:
        def ask(n, held=False, _src=src):
            return _ask_adopt(n, held, path=_src)
    held = session_held(src)
    while True:
        answer = ask(name, held=True) if held else (True if chosen else ask(name))
        if answer != RETRY:
            break
        held, chosen = session_held(src), True           # fermée : la reprise demandée se fait
    if isinstance(answer, str) and answer == LATER:      # plus tard : rien de posé (marque d'une coupée gardée)
        return None
    if answer:
        LAST = adopt(src, app, progress=progress)
        return src
    drop_adoption_mark(app)
    if not _has_settings(ini):
        _decline(ini)
    return None


def _ask_adopt(name: str, held: bool = False, path=None, manual: bool = False):
    """La question du premier lancement ; `held` : l'ancienne version est encore ouverte (Réessayer → `RETRY`, aussi
    pour Échap et la croix ; « Reprendre sans attendre » → vrai ; « Plus tard » → `LATER`, rien de posé, la marque
    d'une reprise coupée gardée ; « Partir de zéro » → faux). `manual` (F10 › « Reprendre d’une ancienne
    version… ») : « Annuler » au lieu de « Partir de zéro », sans « Plus tard ». Sans `held` : « Reprendre ses
    réglages » → vrai, « Partir de zéro » → faux, « Plus tard » (aussi Échap et la croix) → `LATER` — la question ne
    revient pas (la fenêtre écrit ses réglages) : elle dit où la retrouver (F10)."""
    from PySide6.QtWidgets import QMessageBox
    from .i18n import tr
    where = '\n' + tr('Dossier : {0}').format(path) if path else ''
    later_text = tr('Plus tard : F10 › Mises à jour › « Reprendre d’une ancienne version… ».')
    if held:
        box = QMessageBox(QMessageBox.Icon.Warning, tr('VectorDrive portable'),
                          tr('La version « {0} » est encore ouverte : fermez-la d’abord, ses onglets non enregistrés '
                             'seront repris tels qu’elle les garde.').format(name) + where)
        box.setInformativeText(tr('« Reprendre sans attendre » prend la dernière session qu’elle a enregistrée '
                                  'automatiquement : ce qu’elle change ensuite reste dans l’ancienne version. Rien '
                                  'n’est changé dans l’ancien dossier.') + ('' if manual else '\n' + later_text))
        again = box.addButton(tr('Réessayer'), QMessageBox.ButtonRole.AcceptRole)
        now = box.addButton(tr('Reprendre sans attendre'), QMessageBox.ButtonRole.ActionRole)
        later = None if manual else box.addButton(tr('Plus tard'), QMessageBox.ButtonRole.ActionRole)
        box.addButton(tr('Annuler') if manual else tr('Partir de zéro'), QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(again)
        box.setEscapeButton(again)                       # Échap : jamais « Partir de zéro » par mégarde
        box.exec()
        hit = box.clickedButton()
        if later is not None and hit is later:
            return LATER
        return RETRY if hit is again or hit is None else hit is now
    box = QMessageBox(QMessageBox.Icon.Question, tr('VectorDrive portable'),
                      tr('Première ouverture de cette version portable. Reprendre les réglages et les données de la '
                         'version posée à côté (« {0} ») ?').format(name) + where)
    box.setInformativeText(tr('Options, derniers dossiers, dossiers favoris, outils, modèles, thèmes, polices '
                              'ajoutées, bibliothèque, carnet de clients du BAT (fusionné avec celui d’ici), et les '
                              'onglets ouverts avec leurs parcours. Rien n’est changé dans l’ancien dossier. La '
                              'question n’est posée qu’une fois.') + '\n' + later_text)
    yes = box.addButton(tr('Reprendre ses réglages'), QMessageBox.ButtonRole.AcceptRole)
    zero = box.addButton(tr('Partir de zéro'), QMessageBox.ButtonRole.DestructiveRole)
    later = box.addButton(tr('Plus tard'), QMessageBox.ButtonRole.RejectRole)
    box.setEscapeButton(later)                           # Échap, la croix : plus tard, rien de posé
    box.setDefaultButton(yes)
    box.exec()
    hit = box.clickedButton()
    return True if hit is yes else False if hit is zero else LATER


def candidate_text(c) -> str:
    """Une ancienne version, en clair, dans la liste du choix (son édition comprise)."""
    import datetime
    from .i18n import tr
    head = c.name + (' — ' + tr('version {0}').format(c.version) if c.version else '') \
        + (' — ' + tr('édition {0}').format(c.edition) if getattr(c, 'edition', '') else '')
    used = tr('dernière utilisation : {0}').format(datetime.datetime.fromtimestamp(c.last_use).strftime(
        '%d/%m/%Y %H:%M')) if c.last_use else tr('jamais utilisée')
    return head + '\n' + ' · '.join((used, tr('{0} onglet(s)').format(c.tabs),
                                     tr('{0} fichier(s) de bibliothèque').format(c.library),
                                     tr('{0} dossier(s) favori(s)').format(c.favorites),
                                     tr('{0} dossier(s) de la bibli').format(c.bibli),
                                     tr('{0} réglage(s)').format(c.keys)))


def _choose_dialog(cands):
    """La liste où choisir la version à reprendre (plusieurs posées à côté) : (fenêtre, liste, libellé du dossier) —
    rien n'est montré ici (`_choose_previous` l'ouvre)."""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QListWidget, QVBoxLayout
    from .i18n import tr
    dlg = QDialog()
    dlg.setWindowTitle(tr('VectorDrive portable'))
    lay = QVBoxLayout(dlg)
    intro = QLabel(tr('Première ouverture de cette version portable. Plusieurs versions portables sont posées à '
                      'côté : laquelle reprendre (réglages, dossiers favoris, bibliothèque, carnet de clients, '
                      'données, onglets avec leurs parcours) ?'))
    intro.setWordWrap(True)
    lay.addWidget(intro)
    lst = QListWidget()
    lst.setObjectName('adoptChoices')
    lst.addItems([candidate_text(c) for c in cands])
    lay.addWidget(lst)
    where = QLabel()
    where.setObjectName('adoptPath')
    where.setWordWrap(True)
    where.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    lay.addWidget(where)
    lst.currentRowChanged.connect(lambda r: where.setText(tr('Dossier : {0}').format(cands[r].app)
                                                          if 0 <= r < len(cands) else ''))
    lst.setCurrentRow(0)
    note = QLabel(tr('Présélectionnée : la même édition que celle-ci, puis la plus récemment utilisée qui a une '
                     'session et de vrais réglages, sinon celle qui a le plus de contenu à vous (onglets, '
                     'bibliothèque, favoris, données ; à contenu proche, la plus récente). Rien n’est changé dans les '
                     'anciens dossiers. La question n’est posée qu’une fois.'))
    note.setWordWrap(True)
    lay.addWidget(note)
    bb = QDialogButtonBox()
    yes = bb.addButton(tr('Reprendre celle-ci'), QDialogButtonBox.ButtonRole.AcceptRole)
    zero = bb.addButton(tr('Partir de zéro'), QDialogButtonBox.ButtonRole.RejectRole)
    zero.setObjectName('adoptZero')
    zero.clicked.connect(lambda _=False: dlg.setProperty('vd_zero', True))    # Échap, croix : pas ce bouton
    yes.setDefault(True)
    bb.accepted.connect(dlg.accept)
    bb.rejected.connect(dlg.reject)
    lst.itemDoubleClicked.connect(lambda _item: dlg.accept())
    lay.addWidget(bb)
    dlg.resize(720, 420)
    return dlg, lst, where


def _choose_previous(cands):
    """La version choisie ; None : « Partir de zéro » ; `LATER` : Échap ou fermeture (plus tard : F10)."""
    dlg, lst, _where = _choose_dialog(cands)
    if not dlg.exec():
        return None if dlg.property('vd_zero') else LATER
    r = lst.currentRow()
    return cands[r] if 0 <= r < len(cands) else None


def data_dir() -> pathlib.Path:
    """Dossier des données de travail (cache, récupération)."""
    if is_portable():
        d = app_dir() / DATA
    elif sys.platform == 'darwin':                  # macOS : le dossier des données d'application
        d = pathlib.Path.home() / 'Library' / 'Application Support' / 'VectorDrive'
        old = pathlib.Path.home() / 'VectorDrive'   # celui des premières versions macOS (jusqu'à 0.889.0)
        if not d.exists() and old.is_dir():
            d = old                                 # gardé tel quel : outils, séances, plugins y restent
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
