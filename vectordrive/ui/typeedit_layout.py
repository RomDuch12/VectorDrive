"""Disposition du ruban de TypeEdit 13, lue dans le TypeEdit installé sur le
poste (script de ruban `res/RIBBON/ScriptRibbonUI_TE.txt` et libellés des
DLL de langue, lus seulement : rien de Gravotech n'est copié dans
VectorDrive) : onglets, groupes, commandes dans leur ordre, onglets
contextuels ouverts par les boutons « Mode » et « Opérations ».

Les commandes TypeEdit sont reliées aux actions de VectorDrive par
`shortcuts.TE_ACTIONS` ; celles qui n'ont pas d'équivalent sont laissées de
côté.
"""
from __future__ import annotations

import os
import pathlib
import re
import struct
from dataclasses import dataclass, field


@dataclass
class TEPanel:
    title: str
    commands: list = field(default_factory=list)     # [(commande TypeEdit, grand bouton)]


@dataclass
class TETab:
    title: str
    panels: list = field(default_factory=list)
    context: str | None = None                       # onglet contextuel : sa clé
    exit_command: str | None = None                  # bouton de retour


@dataclass
class TELayout:
    tabs: list = field(default_factory=list)         # onglets ordinaires, dans l'ordre
    contexts: dict = field(default_factory=dict)     # clé de contexte → onglet contextuel
    modes: dict = field(default_factory=dict)        # commande → clé de contexte (boutons Mode / Opérations)
    main_menu: list = field(default_factory=list)    # commandes du menu principal
    quick: list = field(default_factory=list)        # barre d'accès rapide (CONFIG/QATSettings_TE.INI)
    quick_on_top: bool = True                        # au-dessus du ruban
    source: str = ''


# --- table de chaînes d'une DLL de langue (sans dépendance) -----------------------------
def string_table(path) -> dict[int, str]:
    """Chaînes (ressources RT_STRING) d'une DLL Windows : id → texte."""
    data = pathlib.Path(path).read_bytes()
    if data[:2] != b'MZ':
        return {}
    pe = struct.unpack_from('<I', data, 0x3C)[0]
    if data[pe:pe + 4] != b'PE\0\0':
        return {}
    nsec = struct.unpack_from('<H', data, pe + 6)[0]
    opt_size = struct.unpack_from('<H', data, pe + 20)[0]
    opt = pe + 24
    magic = struct.unpack_from('<H', data, opt)[0]
    dd = opt + (96 if magic == 0x10B else 112)          # répertoires de données (32 / 64 bits)
    res_rva = struct.unpack_from('<I', data, dd + 2 * 8)[0]
    if not res_rva:
        return {}
    secs = []
    for i in range(nsec):
        s = opt + opt_size + 40 * i
        vsize, va, rsize, raw = struct.unpack_from('<IIII', data, s + 8)
        secs.append((va, max(vsize, rsize), raw))

    def off(rva):
        for va, size, raw in secs:
            if va <= rva < va + size:
                return raw + rva - va
        raise ValueError('adresse hors des sections')
    base = off(res_rva)

    def entries(d):
        named, ids = struct.unpack_from('<HH', data, base + d + 12)
        for k in range(named + ids):
            name, target = struct.unpack_from('<II', data, base + d + 16 + 8 * k)
            yield name, target

    out = {}
    for tid, t in entries(0):
        if tid != 6 or not t & 0x80000000:               # RT_STRING
            continue
        for bid, b in entries(t & 0x7FFFFFFF):
            if not b & 0x80000000:
                continue
            for _lang, leaf in entries(b & 0x7FFFFFFF):
                if leaf & 0x80000000:
                    continue
                rva, size = struct.unpack_from('<II', data, base + leaf)
                blob = data[off(rva):off(rva) + size]
                pos, first = 0, (bid - 1) * 16
                for i in range(16):
                    if pos + 2 > len(blob):
                        break
                    n = struct.unpack_from('<H', blob, pos)[0]
                    pos += 2
                    if n:
                        out[first + i] = blob[pos:pos + 2 * n].decode('utf-16-le', 'replace')
                    pos += 2 * n
    return out


# --- script de ruban ------------------------------------------------------------------
_SET = re.compile(r'^set\s+(\w+)\s*=\s*(\w+)\.(\w+)\s*\(([^)]*)\)', re.I)
_CMD = re.compile(r'^cmd\s*=\s*"([^"]+)"', re.I)
_CALL = re.compile(r'^(?:set\s+(\w+)\s*=\s*)?(\w+)\.(\w+)\s*\(?([^)]*)\)?', re.I)
_BUTTONS = {'addbutton': 1, 'addradiobutton': 0, 'addcheckbox': 0, 'addforgallery': 1, 'addplacedbutton': 1}


def _strip(line: str) -> str:
    out, q = [], False
    for ch in line:
        if ch == '"':
            q = not q
        if ch == "'" and not q:
            break
        out.append(ch)
    return ''.join(out).strip()


def _args(text: str) -> list[str]:
    return [a.strip() for a in text.split(',')] if text.strip() else []


def parse(text: str, strings: dict[int, str]) -> TELayout:
    """Script de ruban TypeEdit → disposition. `strings` : libellés (id →
    texte) des DLL de langue ; sans libellé, l'identifiant est gardé."""
    lay = TELayout()
    tabs: dict[str, TETab] = {}
    panels: dict[str, TEPanel] = {}
    buttons: dict[str, str] = {}                     # variable du bouton → commande
    cmd = None

    def label(arg: str) -> str:
        try:
            n = int(arg)
        except ValueError:
            return arg
        return strings.get(n, str(n))

    for raw in text.splitlines():
        line = _strip(raw)
        if not line:
            continue
        m = _CMD.match(line)
        if m:
            cmd = m.group(1)
            continue
        m = _SET.match(line)
        if m and m.group(2).lower() == 'configproduct':
            var, meth, args = m.group(1), m.group(3).lower(), _args(m.group(4))
            if meth == 'addcategoryfromid':
                t = TETab(label(args[0]))
                tabs[var] = t
                lay.tabs.append(t)
            elif meth == 'addcontextcategoryfromid':
                t = TETab(label(args[0]), context=args[2] if len(args) > 2 else var)
                tabs[var] = t
                lay.contexts[t.context] = t
            elif meth == 'addmainpanelfromid':
                panels[var] = TEPanel(label(args[0]))
            continue
        if m and m.group(2) in tabs and m.group(3).lower() in ('addpanelfromid', 'addpanelrapidofromid'):
            p = TEPanel(label(_args(m.group(4))[0]))
            panels[m.group(1)] = p
            tabs[m.group(2)].panels.append(p)
            continue
        m = _CALL.match(line)
        if not m:
            continue
        target, obj, meth, args = m.group(1), m.group(2), m.group(3).lower(), _args(m.group(4))
        if obj in panels and meth in _BUTTONS and cmd:
            big = len(args) > 1 and args[1].lower() == 'true' if meth == 'addbutton' else False
            p = panels[obj]
            if obj == 'mainPanel' or p.title == strings.get(702, '702'):
                if cmd not in lay.main_menu:
                    lay.main_menu.append(cmd)
            elif all(c != cmd for c, _b in p.commands):
                p.commands.append((cmd, big))
            if target:
                buttons[target] = cmd
        elif obj in panels and meth == 'addmainpanelbutton' and cmd:
            lay.main_menu.append(cmd)
        elif obj in buttons and meth == 'setcontextid' and args:
            lay.modes[buttons[obj]] = args[0]
        elif obj in buttons and meth == 'settypeexitcontextcategory':
            for t in lay.contexts.values():
                if any(c == buttons[obj] for p in t.panels for c, _b in p.commands):
                    t.exit_command = buttons[obj]
    return lay


def quick_access(text: str) -> tuple[list[str], bool]:
    """Barre d'accès rapide d'un QATSettings_*.INI : (commandes, au-dessus
    du ruban). Seules les `NbCommand` premières entrées comptent."""
    vals = {}
    for line in text.splitlines():
        k, sep, v = line.partition('=')
        if sep:
            vals[k.strip().upper()] = v.strip()
    try:
        n = int(vals.get('NBCOMMAND', '0'))
    except ValueError:
        n = 0
    cmds = [vals[f'QAT_CMD_{i}'] for i in range(n) if vals.get(f'QAT_CMD_{i}')]
    return cmds, vals.get('STATEONTOP', '1') != '0'


#: fichiers de la barre d'accès rapide, dans l'ordre de préférence
QAT_FILES = ('QATSettings_TE.INI', 'QATSettings_TE_USER.INI', 'QATSettings_TE_DEFAULT.INI')


# --- TypeEdit installé ------------------------------------------------------------------
LANG_DIRS = {'fr': 'FR', 'en': 'US', 'de': 'GE', 'it': 'IT', 'es': 'SP'}
LABEL_DLLS = ('TypeEditDLL{0}.dll', 'Pltf{0}.dll')

_cache: dict = {}


def installed(version: int = 13, lang: str = 'fr') -> TELayout | None:
    """Disposition du TypeEdit `version` installé (lue une fois), ou None."""
    key = (version, lang)
    if key in _cache:
        return _cache[key]
    _cache[key] = None
    if os.environ.get('VECTORDRIVE_NO_TYPEEDIT') == '1':
        return None
    from .themes import ribbon_script_files
    files = ribbon_script_files(version)
    if not files:
        return None
    script = pathlib.Path(files[0])
    root = script.parents[2]
    strings: dict[int, str] = {}
    for d in dict.fromkeys((LANG_DIRS.get(lang, 'FR'), 'FR')):
        for pat in LABEL_DLLS:
            for base in (root / 'LANGUAGE' / d, root / 'EXE'):
                f = base / pat.format(d)
                if f.is_file():
                    try:
                        for k, v in string_table(f).items():
                            strings.setdefault(k, v)
                    except (OSError, ValueError, struct.error):
                        pass
        if strings:
            break
    b = script.read_bytes()
    text = b.decode('utf-16', 'replace') if b[:2] in (b'\xff\xfe', b'\xfe\xff') else b.decode('latin-1')
    lay = parse(text, strings)
    lay.source = str(script)
    for name in QAT_FILES:
        f = root / 'CONFIG' / name
        if f.is_file():
            q = f.read_bytes()
            lay.quick, lay.quick_on_top = quick_access(
                q.decode('utf-16', 'replace') if q[:2] in (b'\xff\xfe', b'\xfe\xff') else q.decode('latin-1'))
            if lay.quick:
                break
    _cache[key] = lay
    return lay
