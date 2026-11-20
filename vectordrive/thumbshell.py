"""Vignettes des dessins dans l'explorateur Windows : VND, DXF, SMB, SVG,
AI, EPS, VDZ (et PDF si aucun autre logiciel n'en fournit déjà).

Un fournisseur de vignettes (`ressources/vignettes/VectorDriveVignettes.cs`,
compilé à la pose par le csc de .NET Framework 4, présent sur tout Windows)
est déclaré à l'explorateur. Il ne dessine rien : il demande l'image au
serveur de vignettes de VectorDrive (`VectorDrive --vignettes-serveur`) par
un tube nommé. Le serveur est lancé à la première demande, sans fenêtre, et
s'arrête seul après deux minutes sans travail ; il trace avec la vignette
du navigateur Ouvrir (`ui.symbols.preview_image`). L'explorateur garde
ensuite les vignettes dans son cache.

**Rien n'est écrit hors de `HKEY_CURRENT_USER`** (comme le menu de
l'explorateur, `shellmenu`) : pas de droits d'administrateur, retrait aussi
simple que la pose. Une extension dont un autre logiciel fournit déjà les
vignettes n'est pas prise ; au retrait, seules nos déclarations sont ôtées.
Le registre n'est touché que par `install` et `uninstall`, appelés à la
demande de l'utilisateur ; `plan` décrit les clés sans rien écrire.
"""
from __future__ import annotations

import os
import pathlib
import sys

from .shellmenu import CLASSES, _notify, _winreg_delete_tree, _winreg_read, _winreg_write, available, executable

#: identifiant du fournisseur (le même que dans VectorDriveVignettes.cs)
CLSID = '{6E1C2E8A-3B4F-4C5D-9A7B-0D2E5F6A8B91}'
#: interface IThumbnailProvider : la clé ShellEx des vignettes
THUMB_IID = '{e357fccd-a995-4576-b01f-234630154e96}'
CLASS = 'VectorDrive.Vignettes.Fournisseur'
ASSEMBLY = 'VectorDriveVignettes, Version=0.0.0.0, Culture=neutral, PublicKeyToken=null'
#: réglages lus par le fournisseur (programme du serveur)
SETTINGS_KEY = r'Software\VectorDrive\Vignettes'
PIPE = r'\\.\pipe\vectordrive_vignettes'
#: dessins proposés
EXTS = ('.vnd', '.dxf', '.smb', '.svg', '.ai', '.eps', '.pdf', '.vdz')
#: programmes machine en vignette (parcours vu de dessus, ui.nc_preview) — sans les extensions trop
#: communes ailleurs (.iso : images de disque, .h : sources C, .din, .ptp)
PROGRAM_EXTS = ('.nc', '.tap', '.ngc', '.gcode', '.gc', '.cnc', '.mpf', '.spf', '.eia')


def all_exts() -> tuple:
    """Dessins, programmes machine, et programmes des lecteurs des plugins (SimPL…)."""
    out = list(EXTS) + list(PROGRAM_EXTS)
    try:
        from .plugins import REGISTRY
        for _label, exts, _read, _sniff in REGISTRY.nc_readers:
            out += [e.lower() for e in exts or () if e.lower() not in out]
    except Exception:                                    # registre des plugins indisponible
        pass
    return tuple(out)
SERVER_ARG = '--vignettes-serveur'
#: arrêt du serveur sans demande (s)
IDLE = 120
MAX_SIZE = 1024
_APP = None


def source() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parent / 'ressources' / 'vignettes' / 'VectorDriveVignettes.cs'


def dll_dir() -> pathlib.Path:
    base = os.environ.get('LOCALAPPDATA') or str(pathlib.Path.home())
    return pathlib.Path(base) / 'VectorDrive' / 'vignettes'


def compiler() -> pathlib.Path | None:
    root = pathlib.Path(os.environ.get('WINDIR', r'C:\Windows')) / 'Microsoft.NET'
    for sub in ('Framework64', 'Framework'):
        c = root / sub / 'v4.0.30319' / 'csc.exe'
        if c.is_file():
            return c
    return None


def build(out_dir: pathlib.Path | None = None, exe: bool = False) -> pathlib.Path:
    """Compile le fournisseur (DLL ; `exe` : l'outil d'essai) ; rend son chemin."""
    import subprocess
    csc = compiler()
    if csc is None:
        raise OSError('compilateur .NET Framework 4 (csc.exe) introuvable')
    out_dir = out_dir or dll_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / ('VectorDriveVignettes' + ('.exe' if exe else '.dll'))
    r = subprocess.run([str(csc), '/nologo', '/optimize+', '/target:' + ('exe' if exe else 'library'),
                        '/r:System.Drawing.dll', f'/out:{out}', str(source())],
                       capture_output=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if r.returncode != 0 or not out.is_file():
        raise OSError('compilation du fournisseur de vignettes : '
                      + r.stdout.decode('cp850', 'replace').strip()[-400:])
    return out


def ext_key(ext: str) -> str:
    return rf'{CLASSES}\{ext}\ShellEx\{THUMB_IID}'


def other_provider(ext: str) -> str | None:
    """Fournisseur de vignettes déjà déclaré par un autre logiciel pour
    `ext` (compte ou machine), sinon None."""
    import winreg
    for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for key in (ext_key(ext), rf'{CLASSES}\SystemFileAssociations\{ext}\ShellEx\{THUMB_IID}'):
            try:
                with winreg.OpenKey(root, key) as k:
                    v = str(winreg.QueryValueEx(k, None)[0])
            except OSError:
                continue
            if v and v.upper() != CLSID.upper():
                return v
    return None


def plan(dll: pathlib.Path, exts=EXTS, program: tuple[str, list[str]] | None = None) -> list[tuple[str, dict]]:
    """Clés à poser sous HKEY_CURRENT_USER et leurs valeurs ('' : valeur par défaut)."""
    exe, before = program or executable()
    clsid = rf'{CLASSES}\CLSID\{CLSID}'
    # sans DisableProcessIsolation : chargé dans un processus à part (COM Surrogate), un
    # plantage ne touche pas l'explorateur
    out = [(clsid, {'': 'VectorDrive — vignettes des dessins'}),
           (clsid + r'\InprocServer32', {'': 'mscoree.dll', 'ThreadingModel': 'Both', 'Class': CLASS,
                                         'Assembly': ASSEMBLY, 'RuntimeVersion': 'v4.0.30319',
                                         'CodeBase': pathlib.Path(dll).as_uri()}),
           (SETTINGS_KEY, {'Programme': exe,
                           'Arguments': ' '.join([f'"{a}"' for a in before] + [SERVER_ARG])})]
    out += [(ext_key(e), {'': CLSID}) for e in exts]
    return out


def install(exts=None, write=None, program=None, dll: pathlib.Path | None = None) -> tuple[list[str], list[str]]:
    """Compile et déclare le fournisseur ; rend (extensions prises, extensions
    laissées à un autre logiciel)."""
    if write is None:
        if not available():
            raise OSError('vignettes de l\'explorateur : Windows seulement')
        write = _winreg_write
    exts = list(exts or EXTS)
    taken = [e for e in exts if write is not _winreg_write or other_provider(e) is None]
    left = [e for e in exts if e not in taken]
    dll = dll or build()
    for key, values in plan(dll, taken, program):
        write(key, values)
    if write is _winreg_write:
        _notify()
    return taken, left


def uninstall(delete=None, read=None) -> int:
    """Retire ce qu'`install` a posé (et seulement cela) ; rend le nombre de clés ôtées."""
    if delete is None:
        if not available():
            return 0
        delete, read = _winreg_delete_tree, _winreg_read
    n = 0
    for e in all_exts():
        if (read(ext_key(e), '') or '').upper() == CLSID.upper() and delete(ext_key(e)):
            n += 1
    for key in (rf'{CLASSES}\CLSID\{CLSID}', SETTINGS_KEY):
        if delete(key):
            n += 1
    if delete is _winreg_delete_tree:
        _notify()
    return n


def dll_of(code_base: str) -> pathlib.Path:
    """Fichier d'une adresse file:/// (CodeBase : espaces et accents encodés)."""
    from urllib.parse import urlparse
    from urllib.request import url2pathname
    u = urlparse(code_base)
    return pathlib.Path(url2pathname((f'//{u.netloc}' if u.netloc else '') + u.path))


def installed_exts(read=None) -> list[str]:
    read = read or _winreg_read
    return [e for e in all_exts() if (read(ext_key(e), '') or '').upper() == CLSID.upper()]


def check(read=None, program=None) -> tuple[bool, str]:
    """(posé et à jour, explication)."""
    if read is None:
        if not available():
            return False, 'Windows seulement.'
        read = _winreg_read
    exts = installed_exts(read)
    if not exts:
        return False, 'Non installé.'
    exe, before = program or executable()
    code = read(rf'{CLASSES}\CLSID\{CLSID}\InprocServer32', 'CodeBase') or ''
    if read(SETTINGS_KEY, 'Programme') != exe:
        return False, 'Le serveur de vignettes désigne un autre programme (mise à jour ?) : réinstaller.'
    if code.startswith('file:') and not dll_of(code).exists():
        return False, 'Fournisseur de vignettes introuvable : réinstaller.'
    return True, f'Vignettes installées pour {", ".join(e.lstrip(".").upper() for e in exts)}.'


# --- serveur -------------------------------------------------------------------------------
def render(request: bytes) -> bytes:
    """« VIGNETTE\\t<taille>\\t<chemin> » → PNG (b'' : pas de vignette)."""
    try:
        kind, size, path = request.decode('utf-8').split('\t', 2)
        size = max(16, min(MAX_SIZE, int(size)))
    except (UnicodeDecodeError, ValueError):
        return b''
    p = pathlib.Path(path)
    if kind != 'VIGNETTE' or p.suffix.lower() not in all_exts() or not p.is_file():
        return b''
    from PySide6.QtCore import QBuffer, QIODevice
    from .ui.symbols import preview_image
    img = preview_image(p, size)
    if img is None or img.isNull():
        return b''
    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    img.save(buf, 'PNG')
    return bytes(buf.data())


#: processus de tracé du serveur (l'explorateur demande plusieurs vignettes à la fois ; le fournisseur
#: abandonne une demande au bout de 25 s : un dossier de gros dessins servi un par un en perdait)
RENDER_PROCESSES = 4
_RENDER_POOL = None


def _start_render_process() -> None:
    """Processus de tracé : application Qt sans fenêtre, lecteurs des plugins ;
    s'arrête avec le serveur."""
    global _APP
    from . import winpaths  # noqa: F401 — lecteur verrouillé : « absent » comme dans l'application
    from .core import workers
    workers.exit_with_parent()
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    from PySide6.QtGui import QGuiApplication
    _APP = QGuiApplication.instance() or QGuiApplication(sys.argv[:1])
    try:
        from . import plugins
        plugins.load()
    except Exception:                                    # noqa: BLE001 — plugin en défaut : vignettes du cœur
        pass


def render_pool():
    """Processus de tracé (créés à la première demande)."""
    global _RENDER_POOL
    if _RENDER_POOL is None:
        import multiprocessing
        from concurrent.futures import ProcessPoolExecutor
        from .core import workers
        _RENDER_POOL = ProcessPoolExecutor(max(1, min(RENDER_PROCESSES, workers.process_limit())),
                                           mp_context=multiprocessing.get_context('spawn'),
                                           initializer=_start_render_process)
    return _RENDER_POOL


def handle(conn, renderer=None) -> None:
    """Une demande du fournisseur : lue, tracée (processus de tracé, sinon
    sur place), répondue ; la connexion est fermée."""
    try:
        req = conn.recv_bytes(65536)
        try:
            rep = renderer(req) if renderer is not None else render_pool().submit(render, req).result(timeout=60)
        except Exception:                                # noqa: BLE001 — processus en défaut : tracé sur place
            try:
                rep = render(req)
            except Exception:                            # noqa: BLE001 — dessin illisible : pas de vignette
                rep = b''
        conn.send_bytes(rep)
    except (OSError, EOFError):
        pass
    finally:
        conn.close()


def serve(idle: float = IDLE, address: str = PIPE) -> int:
    """Serveur de vignettes : plusieurs demandes à la fois (une par fil,
    tracées sur les processus de tracé) ; s'arrête après `idle` secondes
    sans demande. Un serveur déjà lancé : rend 0 tout de suite."""
    import threading
    import time
    from multiprocessing.connection import Listener
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    from PySide6.QtGui import QGuiApplication
    global _APP
    _APP = QGuiApplication.instance() or QGuiApplication(sys.argv[:1])   # polices, images
    try:                                                 # lecteurs de programmes des plugins (SimPL…)
        from . import plugins
        plugins.load()
    except Exception:                                    # noqa: BLE001 — plugin en défaut : vignettes du cœur
        pass
    try:
        listener = Listener(address, family='AF_PIPE')
    except OSError:
        return 0                                         # un autre serveur répond déjà
    last = [time.monotonic()]

    def watchdog():
        while time.monotonic() - last[0] < idle:
            time.sleep(1.0)
        from .core import workers
        workers.terminate_pool(_RENDER_POOL)             # pas de processus de tracé orphelins
        os._exit(0)
    threading.Thread(target=watchdog, daemon=True).start()
    busy = [0]
    lock = threading.Lock()

    def job(conn):
        try:
            handle(conn)
        finally:
            with lock:
                busy[0] -= 1
            last[0] = time.monotonic()

    def watch_busy():                                    # pas d'arrêt pendant un tracé en cours
        while True:
            time.sleep(1.0)
            if busy[0]:
                last[0] = time.monotonic()
    threading.Thread(target=watch_busy, daemon=True).start()
    while True:
        try:
            conn = listener.accept()
        except OSError:
            continue
        last[0] = time.monotonic()
        with lock:
            busy[0] += 1
        threading.Thread(target=job, args=(conn,), daemon=True).start()
