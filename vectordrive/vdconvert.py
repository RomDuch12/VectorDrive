"""VD-convert : le convertisseur seul (comme TauConvert à côté de TauDrive). Un petit programme à part,
`VD-convert.exe`, qui ne fait que trois choses :

* **convertir** les dessins que lui envoie le clic droit de l'explorateur (« Convertir avec VectorDrive ▸ en DXF,
  en SVG, en PDF, en EPS ») — le même lecteur et le même écrivain que VectorDrive, sans plugin ni fenêtre de dessin ;
* **s'installer** sous le compte de l'utilisateur (`%LOCALAPPDATA%\\Programs\\VD-convert`, aucun droit
  d'administrateur) : copie de son dossier, menu de l'explorateur, entrée « Applications » de Windows pour le
  désinstaller ; avant cela il **cherche les autres versions** — un autre VD-convert installé ailleurs ou plus
  ancien, le menu posé par VectorDrive ou par une copie déplacée, une inscription orpheline — et les retire
  proprement (clés du registre, dossier d'une autre installation de VD-convert) pour les remplacer ;
* **se désinstaller** (bouton, ou « Applications » de Windows) : menu, entrée, dossier.

Le menu est partagé avec VectorDrive (mêmes clés que `shellmenu`) : un poste n'a jamais deux sous-menus
« Convertir avec VectorDrive ». L'application complète n'est jamais désinstallée par VD-convert : seul son menu
de l'explorateur est remplacé.

Rien n'est écrit hors de HKEY_CURRENT_USER. Un dossier n'est supprimé que s'il porte la marque `VD-convert.version`
et `VD-convert.exe` (posés par l'installation) : jamais un dossier de l'utilisateur. Le registre et les fichiers
passent par des fonctions données (`MemoryReg` pour les essais) : les essais ne touchent ni au registre ni au
dossier des programmes.
"""
from __future__ import annotations

import os
import pathlib
import shutil
import stat
import sys
from dataclasses import dataclass, field

from . import shellmenu as SM

NAME = 'VD-convert'
EXE = 'VD-convert.exe'
#: marque posée dans le dossier installé : sa présence autorise la suppression du dossier
MARK = 'VD-convert.version'
UNINSTALL_ROOT = r'Software\Microsoft\Windows\CurrentVersion\Uninstall'
UNINSTALL_KEY = UNINSTALL_ROOT + '\\' + NAME


def version() -> str:
    from . import __version__
    return __version__


# --- le registre --------------------------------------------------------------------------------------------------
class WinReg:
    """HKEY_CURRENT_USER (Windows seulement)."""

    def read(self, key: str, name: str = '') -> str | None:
        return SM._winreg_read(key, name)

    def write(self, key: str, values: dict) -> None:
        import winreg
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key) as k:
            for n, v in values.items():
                if isinstance(v, bool) or isinstance(v, int):
                    winreg.SetValueEx(k, n or None, 0, winreg.REG_DWORD, int(v))
                else:
                    winreg.SetValueEx(k, n or None, 0, winreg.REG_SZ, str(v))

    def delete(self, key: str) -> bool:
        return SM._winreg_delete_tree(key)

    def subkeys(self, key: str) -> list:
        import winreg
        out = []
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as k:
                i = 0
                while True:
                    try:
                        out.append(winreg.EnumKey(k, i))
                    except OSError:
                        break
                    i += 1
        except OSError:
            pass
        return out

    def notify(self) -> None:
        SM._notify()


class MemoryReg:
    """Un registre en mémoire (essais, aperçu) : clés insensibles à la casse, comme celui de Windows."""

    def __init__(self):
        self.keys = {}                                   # clé en minuscules → (clé, {nom: valeur})

    def read(self, key: str, name: str = '') -> str | None:
        got = self.keys.get(key.lower())
        if got is None:
            return None
        v = got[1].get(name.lower())
        return None if v is None else str(v)

    def write(self, key: str, values: dict) -> None:
        parts = key.split('\\')
        for i in range(1, len(parts) + 1):               # les parents existent aussi
            k = '\\'.join(parts[:i])
            self.keys.setdefault(k.lower(), (k, {}))
        self.keys[key.lower()][1].update({n.lower(): v for n, v in values.items()})

    def delete(self, key: str) -> bool:
        low = key.lower()
        gone = [k for k in self.keys if k == low or k.startswith(low + '\\')]
        for k in gone:
            del self.keys[k]
        return bool(gone)

    def subkeys(self, key: str) -> list:
        low = key.lower() + '\\'
        return sorted({v[0].split('\\')[key.count('\\') + 1] for k, v in self.keys.items()
                       if k.startswith(low)})

    def notify(self) -> None:
        pass


def default_reg():
    if not SM.available():
        raise OSError('VD-convert : Windows seulement')
    return WinReg()


# --- où, et quoi ----------------------------------------------------------------------------------------------------
def install_dir() -> pathlib.Path:
    """`%LOCALAPPDATA%\\Programs\\VD-convert` (VECTORDRIVE_VDCONVERT_DIR pour les essais)."""
    env = os.environ.get('VECTORDRIVE_VDCONVERT_DIR')
    if env:
        return pathlib.Path(env)
    base = os.environ.get('LOCALAPPDATA') or str(pathlib.Path.home() / 'AppData' / 'Local')
    return pathlib.Path(base) / 'Programs' / NAME


def running_dir() -> pathlib.Path | None:
    """Le dossier du VD-convert empaqueté en cours (None en développement)."""
    return pathlib.Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else None


def dev_program() -> tuple:
    """En développement : `pythonw` (pas de console) et `VDConvert.py` à la racine."""
    script = pathlib.Path(__file__).resolve().parents[1] / 'VDConvert.py'
    py = pathlib.Path(sys.executable)
    quiet = py.with_name('pythonw.exe')
    return str(quiet if quiet.is_file() else py), [str(script)]


def _norm(p) -> str:
    return os.path.normcase(os.path.normpath(str(p))) if p else ''


def program_of(command: str) -> str:
    """Le programme d'une commande du registre : le premier chemin, ou le script après python(w).exe."""
    import shlex
    try:
        parts = shlex.split(command or '', posix=False)
    except ValueError:
        parts = (command or '').split()
    parts = [p.strip('"') for p in parts]
    if not parts:
        return ''
    if pathlib.Path(parts[0]).name.lower() in ('python.exe', 'pythonw.exe', 'python', 'pythonw') and len(parts) > 1:
        return parts[1]
    return parts[0]


def is_ours(program: str, verb: str = '', sub: str = '') -> bool:
    """Un menu de la famille : le verbe « VectorDrive.* » ou un sous-menu « VectorDrive.* » (ceux que posent
    VectorDrive et VD-convert, toutes versions) ; un verbe d'un autre logiciel, même s'il lance VectorDrive, n'en est
    pas un (jamais retiré)."""
    return verb.lower().startswith('vectordrive.') or (sub or '').lower().startswith('vectordrive.')


def label_of(program: str) -> str:
    name = pathlib.Path(program).name.lower()
    return NAME if name.startswith(('vd-convert', 'vdconvert')) else 'VectorDrive'


def exe_version(path) -> str:
    """La version inscrite dans un exécutable Windows (« 0.994.0 »), '' si illisible."""
    if sys.platform != 'win32' or not path or not pathlib.Path(path).is_file():
        return ''
    try:
        import ctypes
        from ctypes import wintypes
        ver = ctypes.windll.version
        size = ver.GetFileVersionInfoSizeW(str(path), None)
        if not size:
            return ''
        buf = ctypes.create_string_buffer(size)
        if not ver.GetFileVersionInfoW(str(path), 0, size, buf):
            return ''
        p, n = ctypes.c_void_p(), wintypes.UINT()
        if not ver.VerQueryValueW(buf, '\\', ctypes.byref(p), ctypes.byref(n)) or n.value < 52:
            return ''
        fixed = (ctypes.c_uint32 * 13).from_address(p.value)
        ms, ls = fixed[2], fixed[3]
        return f'{ms >> 16}.{ms & 0xFFFF}.{ls >> 16}'
    except Exception:                                    # noqa: BLE001 — une version illisible n'empêche rien
        return ''


# --- les autres versions -------------------------------------------------------------------------------------------
@dataclass
class Other:
    """Une autre version trouvée : `kind` 'menu' (un menu de l'explorateur qui appelle un autre programme) ou
    'install' (une autre installation de VD-convert) ; `keys` : ce qu'il faut retirer du registre ; `folder` : le
    dossier d'une installation (supprimé seulement s'il porte la marque)."""
    kind: str
    program: str = ''
    version: str = ''
    keys: list = field(default_factory=list)
    folder: str = ''

    def text(self) -> str:
        what = label_of(self.program) if self.program else NAME
        v = f' {self.version}' if self.version else ''
        if self.kind == 'install':
            return f'{NAME}{v} installé dans {self.folder}'
        gone = '' if not self.program or pathlib.Path(self.program).exists() else ' (programme introuvable)'
        app = ' — menu de l\'application, elle reste installée' if what == 'VectorDrive' else ''
        return f'menu de l\'explorateur de {what}{v} : {self.program}{gone}{app}'


def _commands(reg, sk: str) -> list:
    return [program_of(c) for c in (reg.read(rf'{sk}\shell\{s}\command', '') for s in reg.subkeys(sk + r'\shell'))
            if c]


def registrations(reg) -> list:
    """Les menus de la famille posés sous HKEY_CURRENT_USER : [(clés à retirer, programme)]. Cherche sous chaque
    extension des dessins et sous les dossiers les verbes « VectorDrive.* » (ou qui renvoient à un sous-menu
    « VectorDrive.* »), et les sous-menus « VectorDrive.Convertir.<ext> » restés seuls (orphelins)."""
    out, seen = [], set()
    bases = [rf'{SM.CLASSES}\SystemFileAssociations\{e}\shell' for e in SM.SOURCES] + \
            [rf'{SM.CLASSES}\Directory\shell']
    for base in bases:
        for verb in reg.subkeys(base):
            vk = base + '\\' + verb
            sub = reg.read(vk, 'ExtendedSubCommandsKey') or ''
            if not is_ours('', verb, sub):
                continue
            keys, progs = [vk], []
            cmd = reg.read(vk + r'\command', '')
            if cmd:
                progs.append(program_of(cmd))
            if sub:
                sk = rf'{SM.CLASSES}\{sub}'
                progs += _commands(reg, sk)
                keys.append(sk)
            seen.update(k.lower() for k in keys)
            out.append((keys, progs[0] if progs else ''))
    for e in SM.SOURCES:                                 # sous-menus orphelins (le verbe qui y renvoyait : parti)
        sk = rf'{SM.CLASSES}\{SM.VERB}.{e.lstrip(".")}'
        if sk.lower() in seen or not reg.subkeys(sk + r'\shell'):
            continue
        progs = _commands(reg, sk)
        out.append(([sk], progs[0] if progs else ''))
    return out


def find_others(reg, me: str | None) -> list:
    """Les autres versions : menus qui n'appellent pas `me` (chemin de ce VD-convert), autres installations."""
    found = {}
    for keys, prog in registrations(reg):
        if me and prog and _norm(prog) == _norm(me):
            continue
        o = found.setdefault(_norm(prog), Other('menu', prog, exe_version(prog)))
        o.keys += [k for k in keys if k not in o.keys]
    here = _norm(pathlib.Path(me).parent) if me else ''
    out = list(found.values())
    for sk in reg.subkeys(UNINSTALL_ROOT):
        key = UNINSTALL_ROOT + '\\' + sk
        disp = reg.read(key, 'DisplayName') or ''
        if not (sk.lower().startswith(NAME.lower()) or disp.lower().startswith(NAME.lower())):
            continue
        loc = reg.read(key, 'InstallLocation') or ''
        if here and _norm(loc) == here:
            continue                                     # la nôtre : reprise sur place par `install`
        out.append(Other('install', str(pathlib.Path(loc) / EXE) if loc else '', reg.read(key, 'DisplayVersion') or '',
                         [key], loc))
    return out


def safe_folder(folder) -> bool:
    """Un dossier installé par VD-convert (marque et exécutable) : le seul qu'on supprime."""
    if not folder:
        return False
    f = pathlib.Path(folder)
    return f.is_absolute() and f.is_dir() and (f / MARK).is_file() and (f / EXE).is_file()


def _writable(path) -> None:
    """Retire l'attribut lecture seule (un dossier copié d'un partage réseau) : sinon Windows refuse l'effacement."""
    try:
        os.chmod(path, os.stat(path).st_mode | stat.S_IWRITE)
    except OSError:
        pass


def _rmtree(path) -> None:
    """Supprime un dossier, fichiers en lecture seule compris ; ce qui résiste (ouvert) reste."""
    def force(func, p, _exc):
        _writable(p)
        try:
            func(p)
        except OSError:
            pass
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=force)
    else:                                                # pragma: no cover
        shutil.rmtree(path, onerror=force)


def _unlink(path) -> None:
    try:
        pathlib.Path(path).unlink(missing_ok=True)
    except PermissionError:
        _writable(path)
        pathlib.Path(path).unlink(missing_ok=True)


def wipe(folder) -> None:
    """Supprime un dossier installé dans l'ordre qui le garde reconnu tant qu'il en reste quelque chose : tout sauf
    l'exécutable et la marque, puis l'exécutable s'il ne reste rien d'autre, puis la marque et le dossier (un
    fichier encore ouvert — une conversion qui tourne — laisse un dossier que `safe_folder` reconnaît toujours)."""
    f = pathlib.Path(folder)
    if not f.is_dir():
        return
    for p in f.iterdir():
        if p.name in (EXE, MARK):
            continue
        try:
            _rmtree(p) if p.is_dir() and not p.is_symlink() else _unlink(p)
        except OSError:
            pass
    try:
        if any(p.name not in (EXE, MARK) for p in f.iterdir()):
            return
        _unlink(f / EXE)
        _unlink(f / MARK)
        f.rmdir()
    except OSError:
        pass


def in_use(folder) -> bool:
    """L'exécutable de `folder` tourne-t-il (VD-convert ouvert, une conversion lancée au clic droit) ? Windows refuse
    d'ouvrir en écriture un exécutable en cours."""
    exe = pathlib.Path(folder) / EXE
    if not exe.is_file():
        return False
    try:
        with open(exe, 'r+b'):
            return False
    except OSError as ex:                                # 32 : partage refusé (il tourne) ; 5 : lecture seule
        return getattr(ex, 'winerror', None) == 32


def remove_others(reg, others, rmtree=None, keep=()) -> list:
    """Retire les autres versions ; rend ce qui a été fait (lignes lisibles). `keep` : des dossiers jamais supprimés
    (la cible, la source, celui du programme en cours)."""
    rmtree = rmtree or wipe
    kept = {_norm(k) for k in keep if k}
    done = []
    for o in others:
        n = sum(1 for k in o.keys if reg.delete(k))
        line = o.text() + (f' : {n} clé(s) retirée(s)' if n else '')
        if o.kind == 'install' and o.folder and _norm(o.folder) not in kept:
            if safe_folder(o.folder):
                rmtree(o.folder)
                line += ', dossier supprimé'
            elif pathlib.Path(o.folder).exists():
                line += ', dossier laissé (pas une installation de VD-convert)'
        done.append(line)
    return done


# --- installer, désinstaller -----------------------------------------------------------------------------------------
#: ce qu'on copie du dossier du programme : l'exécutable et ses bibliothèques, rien d'autre (un zip décompressé à
#: plat dans Téléchargements ne recopie pas les fichiers de l'utilisateur)
PAYLOAD = (EXE, '_internal')


def _size_kb(folder: pathlib.Path) -> int:
    try:
        return int(sum(f.stat().st_size for f in folder.rglob('*') if f.is_file()) / 1024)
    except OSError:
        return 0


def _leftover(p: pathlib.Path) -> bool:
    """Un reste d'installation (`.nouveau`, `.ancien`) : rien d'autre que l'exécutable, `_internal` et la marque."""
    try:
        return p.is_dir() and all(c.name in PAYLOAD + (MARK,) for c in p.iterdir())
    except OSError:
        return False


def _clear_leftover(p: pathlib.Path, rmtree) -> None:
    """Retire un reste d'installation ; refuse un dossier qui n'en est pas un (rien n'a changé)."""
    if not p.exists():
        return
    if not _leftover(p):
        raise OSError(f'{p} existe et n\'est pas un reste de {NAME} : rien n\'est remplacé')
    rmtree(p)
    if p.exists():
        raise OSError(f'{p} (reste d\'une installation précédente) est encore utilisé : fermez VD-convert et les '
                      f'conversions en cours, puis recommencez — rien n\'a changé')


def _copy_payload(source: pathlib.Path, dest: pathlib.Path, copytree) -> None:
    dest.mkdir(parents=True)
    shutil.copy2(source / EXE, dest / EXE)
    if (source / '_internal').is_dir():
        copytree(source / '_internal', dest / '_internal')
    for root, _dirs, files in os.walk(dest):             # une source en lecture seule : la copie, elle, s'efface
        for name in files:
            _writable(os.path.join(root, name))


def install(reg=None, source=None, target=None, *, copytree=None, rmtree=None) -> dict:
    """Installe ce VD-convert. Dans l'ordre, pour ne rien casser si une étape échoue : copie de l'exécutable et de
    `_internal` de `source` (le dossier du programme en cours) dans un dossier à côté de `target` (install_dir()) ;
    l'ancienne version de `target` mise de côté par un renommage (refusé si elle est ouverte : rien n'a changé) ; la
    copie renommée en `target` ; ALORS seulement les autres versions retirées, le menu posé, l'entrée « Applications »
    écrite ; l'ancienne version supprimée. `source` None (développement) : le menu appelle ce script sur place, sans
    copie ni entrée. Rend {'exe', 'removed', 'copied'}."""
    reg = reg or default_reg()
    copytree = copytree or shutil.copytree
    others_rm = rmtree                                   # les autres installations : `wipe` d'office
    rmtree = rmtree or _rmtree
    import time
    if source is None:
        program = dev_program()
        prog = program[1][0]
        removed = remove_others(reg, find_others(reg, prog), others_rm)
        SM.install(write=reg.write, program=program, lots=False)
        reg.notify()
        return {'exe': prog, 'removed': removed, 'copied': False}
    source, target = pathlib.Path(source), pathlib.Path(target or install_dir())
    if not (source / EXE).is_file():
        raise OSError(f'{EXE} introuvable dans {source}')
    exe = target / EXE
    copied = _norm(source) != _norm(target)
    if copied and target.exists() and any(target.iterdir()) and not safe_folder(target):
        raise OSError(f'{target} existe et n\'est pas une installation de {NAME} : rien n\'est remplacé')
    others = find_others(reg, str(exe))
    old = None
    if copied:
        stage = target.with_name(target.name + '.nouveau')
        old = target.with_name(target.name + '.ancien')
        if _norm(source) in (_norm(stage), _norm(old)):
            raise OSError(f'{source} est un reste d\'installation : lancez VD-convert depuis le dossier téléchargé — '
                          f'rien n\'a changé')
        busy = OSError(f'{target} est utilisé (VD-convert ouvert, une conversion en cours ?) : fermez-le et '
                       f'recommencez — rien n\'a changé')
        if target.exists() and in_use(target):
            raise busy
        _clear_leftover(stage, rmtree)
        _clear_leftover(old, rmtree)
        try:
            _copy_payload(source, stage, copytree)
        except OSError:
            rmtree(stage)
            raise
        moved = False
        if target.exists():
            try:
                target.rename(old)                       # refusé si l'ancienne version est ouverte : rien n'a changé
                moved = True
            except OSError as ex:
                rmtree(stage)
                raise busy from ex
        for attempt in range(4):                         # un antivirus qui lit la copie fraîche : quelques essais
            try:
                stage.rename(target)
                break
            except OSError as ex:
                if attempt < 3:
                    time.sleep(0.5)
                    continue
                if moved:                                # l'ancienne version remise en place : rien n'a changé
                    try:
                        old.rename(target)
                    except OSError:
                        pass
                rmtree(stage)
                raise OSError(f'{stage} n\'a pas pu devenir {target} (un antivirus l\'analyse ?) : recommencez dans '
                              f'un instant — rien n\'a changé') from ex
        if not moved:
            old = None
    (target / MARK).write_text(version() + '\n', encoding='utf-8')
    removed = remove_others(reg, others, others_rm, keep=(target, source, running_dir()))
    SM.install(write=reg.write, program=(str(exe), []), lots=False)
    reg.write(UNINSTALL_KEY, {
        'DisplayName': NAME, 'DisplayVersion': version(), 'Publisher': 'VectorDrive',
        'DisplayIcon': f'{exe},0', 'InstallLocation': str(target),
        'UninstallString': f'"{exe}" --desinstaller', 'QuietUninstallString': f'"{exe}" --desinstaller --silencieux',
        'NoModify': 1, 'NoRepair': 1, 'EstimatedSize': _size_kb(target)})
    if old is not None:
        rmtree(old)
    reg.notify()
    return {'exe': str(exe), 'removed': removed, 'copied': copied}


def delete_later(folder) -> None:
    """Supprime `folder` quand ce programme est fermé (on ne peut pas effacer l'exécutable qui tourne) : un
    PowerShell caché attend la fin du processus, efface tout sauf l'exécutable et la marque, puis l'exécutable
    s'il ne reste rien, puis la marque (un échec laisse un dossier encore reconnu, que la prochaine installation reprend)."""
    import subprocess
    f = str(pathlib.Path(folder)).replace("'", "''")
    mark = MARK.replace("'", "''")
    exe = EXE.replace("'", "''")
    fexe = str(pathlib.Path(folder) / EXE).replace("'", "''")
    keep =f"$_.Name -ne '{mark}' -and $_.Name -ne '{exe}'"
    rest = f"Get-ChildItem -LiteralPath '{f}' -Force | Where-Object {{ $_.Name -ne '{mark}' }}"
    script = (f"Wait-Process -Id {os.getpid()} -ErrorAction SilentlyContinue; Start-Sleep -Milliseconds 300; "
              f"Get-ChildItem -LiteralPath '{f}' -Force | Where-Object {{ {keep} }} | "
              f"Remove-Item -Recurse -Force -ErrorAction SilentlyContinue; "
              f"if (-not (Get-ChildItem -LiteralPath '{f}' -Force | Where-Object {{ {keep} }})) "
              f"{{ Remove-Item -LiteralPath '{fexe}' -Force -ErrorAction SilentlyContinue; "
              f"if (-not ({rest})) {{ Remove-Item -LiteralPath '{f}' -Recurse -Force }} }}")
    args = ['powershell', '-NoProfile', '-NonInteractive', '-WindowStyle', 'Hidden', '-Command', script]
    flags = 0x08000000 | 0x00000200                      # CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP
    try:                                                 # hors du « job » du parent : il survit à sa fermeture
        subprocess.Popen(args, creationflags=flags | 0x01000000, cwd=os.environ.get('TEMP') or None, close_fds=True)
    except OSError:                                      # sortie du job refusée : lancé quand même
        subprocess.Popen(args, creationflags=flags, cwd=os.environ.get('TEMP') or None, close_fds=True)


def log_dir() -> pathlib.Path:
    return pathlib.Path(os.environ.get('LOCALAPPDATA') or pathlib.Path.home()) / NAME


def _release(log: pathlib.Path) -> None:
    """Le journal tenu ouvert par l'exécutable fenêtré (sortie redirigée) : fermé, la sortie vers nul, pour que
    Windows le laisse effacer."""
    out = sys.stdout
    name = getattr(out, 'name', None)
    if isinstance(name, str) and _norm(name) == _norm(log):
        try:
            out.close()
        except OSError:
            pass
        sys.stdout = sys.stderr = open(os.devnull, 'w', encoding='utf-8')


def uninstall(reg=None, folder=None, *, program=None, rmtree=None, later=None) -> list:
    """Désinstalle VD-convert de `folder` (install_dir()) : ses menus (et ses inscriptions orphelines ou celles de
    `program`, le script en développement), son entrée, son journal, son dossier (à la fermeture s'il est celui du
    programme en cours). Le menu de VectorDrive n'est pas touché. Rend ce qui a été fait."""
    reg = reg or default_reg()
    folder = pathlib.Path(folder or install_dir())
    rmtree = rmtree or wipe
    later = later or delete_later
    done = []
    mine = {_norm(folder / EXE)} | ({_norm(program)} if program else set())
    for keys, prog in registrations(reg):
        if (prog and _norm(prog) in mine) or (label_of(prog) == NAME and not pathlib.Path(prog).exists()):
            n = sum(1 for k in keys if reg.delete(k))
            if n:
                done.append(f'menu de l\'explorateur : {n} clé(s) retirée(s)')
    for sk in reg.subkeys(UNINSTALL_ROOT):
        key = UNINSTALL_ROOT + '\\' + sk
        if sk.lower() == NAME.lower() and _norm(reg.read(key, 'InstallLocation') or '') in (_norm(folder), ''):
            reg.delete(key)
            done.append('entrée « Applications » retirée')
    logs = log_dir()
    if (logs / 'VD-convert.log').is_file():
        _release(logs / 'VD-convert.log')
        try:
            (logs / 'VD-convert.log').unlink()
            logs.rmdir()                                 # vide seulement
        except OSError:
            pass
    if safe_folder(folder):
        run = running_dir()
        if run is not None and _norm(run) == _norm(folder):
            later(folder)
            done.append(f'dossier {folder} supprimé à la fermeture')
        else:
            rmtree(folder)
            done.append(f'dossier {folder} supprimé')
    reg.notify()
    return done


def status(reg, program: tuple) -> tuple:
    """(posé et à jour, explication, autres versions) pour le programme `program` (exe, [script])."""
    me = program[1][0] if program[1] else program[0]
    others = find_others(reg, me)
    ok, why = SM.check(read=reg.read, program=program, lots=False)
    return ok, why, others


# --- convertir --------------------------------------------------------------------------------------------------------
def convert(src, fmt: str, out_dir=None, keep: bool = True) -> tuple:
    """Convertit `src` en `fmt` (dxf, svg, pdf, eps) à côté de lui (ou dans `out_dir`, créé au besoin) ; jamais
    d'écrasement avec `keep`. Rend (chemin écrit, remarques de lecture)."""
    from .io import registry
    fmt = str(fmt).lstrip('.').lower()
    if fmt not in dict(SM.TARGETS):
        raise ValueError(f'format de sortie inconnu : {fmt} ({", ".join(k for k, _ in SM.TARGETS)})')
    p = pathlib.Path(src)
    doc = registry.open_document(str(p))
    folder = pathlib.Path(out_dir) if out_dir else p.parent
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / f'{p.stem}.{fmt}'
    if keep and dest.exists():
        n = 2
        while (folder / f'{p.stem} ({n}).{fmt}').exists():
            n += 1
        dest = folder / f'{p.stem} ({n}).{fmt}'
    registry.save_document(doc, dest)
    return dest, list(getattr(doc, 'report', []) or [])
