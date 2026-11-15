"""Menu contextuel de l'explorateur Windows : « Convertir avec VectorDrive ▸
en DXF, en SVG, en PDF, en EPS, Traitement par lots… » sur les dessins, et
« Traitement par lots avec VectorDrive » sur les dossiers (TauDrive :
shellmenu). Le traitement par lots s'ouvre dans la fenêtre de VectorDrive
(déjà ouverte ou lancée) avec les fichiers choisis : plusieurs fichiers
sélectionnés arrivent dans la même liste.

La conversion est celle de la ligne de commande (`VectorDrive --convert
fichier --to dxf --keep`) : même lecteur et même écrivain que l'application
ouverte ; un fichier de même nom n'est jamais écrasé (« nom (2).dxf »).

**Rien n'est écrit hors de `HKEY_CURRENT_USER`** : pas de droits
d'administrateur, aucun autre compte touché, retrait aussi simple que la
pose ; seul le chemin du programme est inscrit, `check` le contrôle après
une mise à jour. Windows 11 range ces entrées sous « Afficher plus
d'options » (menu classique, Maj+F10).

Le registre n'est touché que par `install` et `uninstall`, appelés à la
demande de l'utilisateur ; `plan` décrit les clés sans rien écrire (essais).
"""
from __future__ import annotations

import pathlib
import sys

#: racine des associations, sous le compte de l'utilisateur
CLASSES = r'Software\Classes'
VERB = 'VectorDrive.Convertir'
TITLE = 'Convertir avec VectorDrive'
#: dessins proposés à la conversion
SOURCES = ('.vnd', '.vdz', '.dxf', '.svg', '.pdf', '.ai', '.eps', '.ps', '.smb', '.gvt', '.vnm')
#: formats de sortie (pas de VND ni de programme machine depuis l'explorateur)
TARGETS = (('dxf', 'DXF'), ('svg', 'SVG'), ('pdf', 'PDF'), ('eps', 'EPS'))
LOTS_VERB = 'VectorDrive.Lots'
LOTS_TITLE = 'Traitement par lots…'
LOTS_DIR_TITLE = 'Traitement par lots avec VectorDrive'
#: dossiers : clé du verbe (sous Software\Classes)
DIR_KEY = rf'Directory\shell\{LOTS_VERB}'


def available() -> bool:
    return sys.platform == 'win32'


def executable() -> tuple[str, list[str]]:
    """Programme à lancer et ses arguments fixes : l'exécutable installé, ou
    en développement `pythonw` (pas de console) et `VectorDrive.py`."""
    if getattr(sys, 'frozen', False):
        return sys.executable, []
    script = pathlib.Path(__file__).resolve().parents[1] / 'VectorDrive.py'
    py = pathlib.Path(sys.executable)
    quiet = py.with_name('pythonw.exe')
    return str(quiet if quiet.is_file() else py), [str(script)]


def command(kind: str, program: tuple[str, list[str]] | None = None) -> str:
    exe, before = program or executable()
    return ' '.join([f'"{exe}"'] + [f'"{a}"' for a in before] + ['--convert', '"%1"', '--to', kind, '--keep'])


def lots_command(program: tuple[str, list[str]] | None = None) -> str:
    exe, before = program or executable()
    return ' '.join([f'"{exe}"'] + [f'"{a}"' for a in before] + ['--lots', '"%1"'])


def targets_for(ext: str) -> list[tuple[str, str]]:
    src = ext.lstrip('.').lower()
    return [(k, lab) for k, lab in TARGETS if k != src and not (src == 'ps' and k == 'eps')]


def plan(program: tuple[str, list[str]] | None = None) -> list[tuple[str, dict]]:
    """Clés à poser sous HKEY_CURRENT_USER et leurs valeurs ('' : valeur par
    défaut) : un sous-menu par extension (jamais « DXF en DXF »), et le verbe
    posé sur l'extension qui y renvoie."""
    program = program or executable()
    icon = f'{program[0]},0'
    out = []
    for ext in SOURCES:
        sub = f'{VERB}.{ext.lstrip(".")}'
        for rank, (kind, label) in enumerate(targets_for(ext), start=1):
            key = rf'{CLASSES}\{sub}\shell\{rank:02d}{kind}'
            out.append((key, {'MUIVerb': f'en {label}', 'Icon': icon}))
            out.append((key + r'\command', {'': command(kind, program)}))
        key = rf'{CLASSES}\{sub}\shell\90lots'
        out.append((key, {'MUIVerb': LOTS_TITLE, 'Icon': icon, 'MultiSelectModel': 'Player'}))
        out.append((key + r'\command', {'': lots_command(program)}))
        # Windows ajoute lui-même le « \shell » final de la clé du sous-menu
        out.append((rf'{CLASSES}\SystemFileAssociations\{ext}\shell\{VERB}',
                    {'MUIVerb': TITLE, 'Icon': icon, 'ExtendedSubCommandsKey': sub}))
    out.append((rf'{CLASSES}\{DIR_KEY}', {'MUIVerb': LOTS_DIR_TITLE, 'Icon': icon}))
    out.append((rf'{CLASSES}\{DIR_KEY}\command', {'': lots_command(program)}))
    return out


def _roots() -> list[str]:
    """Clés racines posées (à retirer avec leur contenu)."""
    return ([rf'{CLASSES}\{VERB}.{e.lstrip(".")}' for e in SOURCES] +
            [rf'{CLASSES}\SystemFileAssociations\{e}\shell\{VERB}' for e in SOURCES] +
            [rf'{CLASSES}\{DIR_KEY}'])


def _winreg_write(key: str, values: dict) -> None:
    import winreg
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key) as k:
        for name, v in values.items():
            winreg.SetValueEx(k, name or None, 0, winreg.REG_SZ, v)


def _winreg_delete_tree(key: str) -> bool:
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key, 0, winreg.KEY_ALL_ACCESS) as k:
            while True:
                try:
                    child = winreg.EnumKey(k, 0)
                except OSError:
                    break
                _winreg_delete_tree(key + '\\' + child)
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key)
        return True
    except FileNotFoundError:
        return False


def _winreg_read(key: str, name: str) -> str | None:
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as k:
            return str(winreg.QueryValueEx(k, name or None)[0])
    except OSError:
        return None


def _notify() -> None:
    """Prévenir l'explorateur que les associations ont changé."""
    try:
        import ctypes
        ctypes.windll.shell32.SHChangeNotify(0x08000000, 0, None, None)
    except Exception:
        pass


def install(write=None, program=None) -> int:
    """Pose le menu (sous HKEY_CURRENT_USER) ; rend le nombre d'extensions."""
    if write is None:
        if not available():
            raise OSError('menu de l\'explorateur : Windows seulement')
        write = _winreg_write
    for key, values in plan(program):
        write(key, values)
    if write is _winreg_write:
        _notify()
    return len(SOURCES)


def uninstall(delete=None) -> int:
    """Retire tout ce qu'`install` a posé ; rend le nombre de clés ôtées."""
    if delete is None:
        if not available():
            return 0
        delete = _winreg_delete_tree
    n = sum(1 for key in _roots() if delete(key))
    if delete is _winreg_delete_tree:
        _notify()
    return n


def check(read=None, program=None) -> tuple[bool, str]:
    """(posé et à jour, explication) : chaque commande inscrite désigne-t-elle
    bien ce programme ?"""
    if read is None:
        if not available():
            return False, 'Windows seulement.'
        read = _winreg_read
    want = dict(plan(program))
    posed = [k for k in want if k.endswith(rf'\shell\{VERB}')]
    if not any(read(k, 'MUIVerb') for k in posed):
        return False, 'Non installé.'
    stale = [k for k, v in want.items() if '' in v and read(k, '') != v['']]
    if stale:
        return False, f'{len(stale)} commande(s) désignent un autre programme (mise à jour ?) : réinstaller.'
    return True, f'Installé pour {len(SOURCES)} type(s) de fichier.'
