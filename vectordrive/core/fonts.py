"""Polices : trouver un fichier à partir d'un nom de famille, extraire les
contours exacts des glyphes.

Les contours restent exacts : quadratiques TrueType → `Conic` (w = 1),
cubiques OpenType/CFF → `Cubic`. Aucune approximation avant l'affichage.

Dossiers cherchés : polices Windows (système et utilisateur), et ceux
qu'ajoutent les plugins (`add_dirs`). Les formats de polices propriétaires sont
lus par les plugins (`fontformats`) : sur le poste, jamais redistribués.

Polices monotrait intégrées (`BUILTIN`) : « VD Trait » (`core.strokefont`) et
« VD Géo » (`core.strokegeo`, linéale géométrique) ; toujours là, repérées par
un chemin qui n'est pas un fichier.
"""
from __future__ import annotations

import functools
import logging
import os
import pathlib
import sys
import threading

from . import strokefont, strokegeo
from .geom import Conic, Contour, Cubic, Line, Path, dist

#: polices monotrait intégrées (traits ouverts, gravés en un passage), dans l'ordre des listes de polices
BUILTIN = (strokefont, strokegeo)


def builtin(path):
    """Le module de la police intégrée repérée par ce chemin, sinon None."""
    return next((m for m in BUILTIN if m.is_stroke(path)), None)


def builtin_named(name: str):
    """Le module de la police intégrée de ce nom (tolérant : casse, espaces), sinon None."""
    k = _key(name)
    return next((m for m in BUILTIN if _key(m.NAME) == k), None)

# polices système un peu abîmées (table 'name' mal décalée…) : fontTools s'en
# accommode mais le signale en erreur ; sans conséquence pour le tracé
logging.getLogger('fontTools').setLevel(logging.CRITICAL)

def _platform_dirs(platform: str, home: pathlib.Path, env) -> tuple[tuple, list]:
    """(dossiers de polices de Windows, tous les dossiers où chercher) pour le système `platform` (`sys.platform`).
    macOS et Linux : dans l'ordre du système, celles de l'utilisateur d'abord (la première trouvée d'une famille est
    prise) — macOS : ~/Library/Fonts, /Library/Fonts, /System/Library/Fonts (Arial, sous Supplemental) ; Linux :
    ~/.local/share/fonts, ~/.fonts, /usr/local/share/fonts, /usr/share/fonts. Windows : inchangé."""
    win: list[pathlib.Path] = []
    if platform == 'win32':
        win.append(pathlib.Path(env.get('WINDIR', 'C:/Windows')) / 'Fonts')
        local = env.get('LOCALAPPDATA')
        if local:
            win.append(pathlib.Path(local) / 'Microsoft' / 'Windows' / 'Fonts')
        dirs = win + [home / '.fonts', pathlib.Path('/usr/share/fonts'),
                      pathlib.Path('/Library/Fonts'), home / 'Library' / 'Fonts']
    elif platform == 'darwin':
        dirs = [home / 'Library' / 'Fonts', pathlib.Path('/Library/Fonts'), pathlib.Path('/System/Library/Fonts')]
    else:
        dirs = [home / '.local' / 'share' / 'fonts', home / '.fonts', pathlib.Path('/usr/local/share/fonts'),
                pathlib.Path('/usr/share/fonts')]
    return tuple(win), dirs


_WINDOWS_DIRS, FONT_DIRS = _platform_dirs(sys.platform, pathlib.Path.home(), os.environ)
#: dossiers des polices installées dans le système (sous Windows, les siens seulement), hors ceux des plugins et des
#: réglages : les autres logiciels (TypeEdit) y trouvent les mêmes polices
SYSTEM_FONT_DIRS: tuple = _WINDOWS_DIRS if sys.platform == 'win32' else tuple(FONT_DIRS)
#: familles (clés) qu'une police TrueType / OpenType de SYSTEM_FONT_DIRS fournit, quel que soit le fichier retenu
#: par `families` (rempli avec lui)
SYSTEM_KEYS: set = set()
#: nom de famille affiché des polices TrueType / OpenType trouvées, par clé (listes de polices : celles que Qt ne
#: connaît pas, installées après son lancement ou dans un dossier ajouté)
NAMES: dict = {}
#: signature des dossiers de polices et clés de l'inventaire au premier inventaire, puis à chaque `rescan`
_SIG: list | None = None
_KNOWN: set = set()
#: coup d'œil aux dossiers où l'on installe des polices (`_quick_signature`) au dernier `rescan`
_QUICK: list | None = None
#: clés apparues à chaque inventaire refait par `rescan` (sa longueur : la génération des listes de polices)
_HISTORY: list = []
#: un inventaire à la fois (les fils de calcul des aperçus en demandent aussi)
_LOCK = threading.RLock()
#: fichiers de polices lus par le cœur ; les plugins en ajoutent (`fontformats`)
FONT_EXT = ('.ttf', '.otf', '.ttc', '.svg')


def _font_ext() -> tuple:
    from . import fontformats
    return FONT_EXT + tuple(fontformats.FORMATS)


def _is_svg(path) -> bool:
    return str(path).lower().endswith('.svg')


def add_dirs(dirs) -> None:
    """Dossiers de polices en plus (plugins) ; la liste des familles est
    refaite au prochain usage."""
    added = False
    for d in dirs:
        d = pathlib.Path(d)
        if d not in FONT_DIRS:
            FONT_DIRS.append(d)
            added = True
    if added:
        families.cache_clear()

#: polices lues par les plugins (`fontformats`) trouvées : nom affiché → fichier (pour les listes de polices)
PLUGIN_FONTS: dict[str, str] = {}
#: polices SVG trouvées : nom affiché → fichier
SVG_FONTS: dict[str, str] = {}
FALLBACK = ('Arial', 'Liberation Sans', 'DejaVu Sans', 'Helvetica')


def add_font_dir(path) -> None:
    p = pathlib.Path(path)
    if p not in FONT_DIRS:
        FONT_DIRS.insert(0, p)
        families.cache_clear()


def _key(name: str) -> str:
    return ''.join(ch for ch in name.lower() if ch.isalnum())


def cache_file() -> pathlib.Path:
    """Inventaire des polices en cache (VECTORDRIVE_CACHE pour les tests)."""
    d = os.environ.get('VECTORDRIVE_CACHE')
    if d:
        return pathlib.Path(d) / 'VectorDrive' / 'polices.json'
    from .. import portable                         # mode portable : à côté de l'exe
    return portable.data_dir() / 'polices.json'


def user_font_dir() -> pathlib.Path:
    """Le dossier des polices ajoutées par l'utilisateur (VECTORDRIVE_CACHE pour les tests)."""
    d = os.environ.get('VECTORDRIVE_CACHE')
    if d:
        return pathlib.Path(d) / 'VectorDrive' / 'polices'
    from .. import portable
    return portable.data_dir() / 'polices'


def _dirs() -> list[pathlib.Path]:
    return [*FONT_DIRS, user_font_dir()]


def _signature() -> list:
    """Dossiers de polices et dates de leurs sous-dossiers : change dès
    qu'une police est ajoutée ou retirée."""
    sig = []
    for d in _dirs():
        if not d.is_dir():
            continue
        stamps = []
        for root, dirs, files in os.walk(d):
            try:
                stamps.append(round(os.stat(root).st_mtime, 3))
            except OSError:
                pass
            stamps.append(len(files))
        sig.append([str(d), stamps])
    from . import fontformats
    sig.append(['formats', sorted(f'{e} {f.reader}' for e, f in fontformats.FORMATS.items())])
    # un format en plus ou en moins, ou son lecteur changé (plugin mis à jour) : inventaire refait
    return sig


CACHE_VERSION = 5                                     # 5 : noms affichés des familles (round 989)


def _seen(sig: list, fam: dict) -> dict:
    """Le premier inventaire : sa signature et ses clés, d'où partent les comparaisons de `rescan` (un inventaire refait
    par un autre chemin — dossier ajouté, police enregistrée — ne les change pas)."""
    global _SIG, _KNOWN
    if _SIG is None:
        _SIG, _KNOWN = sig, set(fam)
    return fam


@functools.lru_cache(maxsize=1)
def families() -> dict[str, tuple[str, int]]:
    """Nom de famille (et nom complet) normalisé → (fichier, indice dans
    une collection .ttc). ~1 s sur un poste Windows la première fois, puis
    lu dans un cache disque tant que les dossiers de polices ne changent pas.
    Un inventaire à la fois : un fil d'aperçu attend celui en cours."""
    with _LOCK:
        return _families()


def _families() -> dict[str, tuple[str, int]]:
    import json
    sig = _signature()
    cf = cache_file()
    try:
        data = json.loads(cf.read_text(encoding='utf-8'))
        if data.get('version') == CACHE_VERSION and data.get('sig') == sig:
            PLUGIN_FONTS.clear()
            PLUGIN_FONTS.update(data.get('plugins', {}))
            SVG_FONTS.clear()
            SVG_FONTS.update(data.get('svg', {}))
            SYSTEM_KEYS.clear()
            SYSTEM_KEYS.update(data.get('systeme', []))
            NAMES.clear()
            NAMES.update(data.get('noms', {}))
            return _seen(sig, {k: (v[0], int(v[1])) for k, v in data['familles'].items()})
    except (OSError, ValueError, KeyError, TypeError, IndexError):
        pass
    out = _scan()
    try:
        cf.parent.mkdir(parents=True, exist_ok=True)
        cf.write_text(json.dumps({'version': CACHE_VERSION, 'sig': sig, 'plugins': PLUGIN_FONTS, 'svg': SVG_FONTS,
                                  'systeme': sorted(SYSTEM_KEYS), 'noms': NAMES, 'familles': {k: list(v) for k, v in out.items()}}, ensure_ascii=False),
                      encoding='utf-8')
    except OSError:
        pass
    return _seen(sig, out)


def _scan() -> dict[str, tuple[str, int]]:
    from fontTools.ttLib import TTCollection, TTFont
    from . import fontformats, svgfonts
    out: dict[str, tuple[str, int]] = {}
    PLUGIN_FONTS.clear()
    SVG_FONTS.clear()
    SYSTEM_KEYS.clear()
    NAMES.clear()
    exts = _font_ext()
    for d in _dirs():
        if not d.is_dir():
            continue
        system = d in SYSTEM_FONT_DIRS
        for f in d.rglob('*'):
            if f.suffix.lower() not in exts:
                continue
            fmt = fontformats.of(f)
            svg = fmt is None and _is_svg(f)
            if fmt is not None or svg:
                try:
                    name = fmt.font_name(f) if fmt is not None else svgfonts.font_name(f)
                except Exception:                        # lecteur d'un plugin en défaut : le nom du fichier
                    name = None
                if svg and not name:                     # un dessin, pas une police
                    continue
                for n in {name or '', f.stem.strip()}:
                    if n:
                        out.setdefault(_key(n), (str(f), 0))
                if name:
                    (SVG_FONTS if svg else PLUGIN_FONTS).setdefault(name, str(f))
                continue
            try:
                fonts = TTCollection(str(f)).fonts if f.suffix.lower() == '.ttc' else [TTFont(str(f), lazy=True)]
            except Exception:
                continue
            for idx, ft in enumerate(fonts):
                try:
                    names = ft['name']
                except Exception:
                    ft.close()
                    continue
                fam = names.getDebugName(1) or ''
                sub = names.getDebugName(2) or ''
                full = names.getDebugName(4) or ''
                for n in {full, fam if sub.lower() in ('regular', 'normal', 'standard', 'roman', '') else ''}:
                    if n:
                        out.setdefault(_key(n), (str(f), idx))
                        if system:
                            SYSTEM_KEYS.add(_key(n))
                if fam:
                    out.setdefault(_key(fam), (str(f), idx))
                    NAMES.setdefault(_key(fam), fam)
                    if system:
                        SYSTEM_KEYS.add(_key(fam))
                ft.close()
    return out


def keys_of(name: str) -> set:
    """Les clés sous lesquelles l'inventaire peut connaître cette police (« Gras » → « Bold »…)."""
    k = _key(name)
    return {k, k.replace('gras', 'bold'), k.replace('italique', 'italic')}


def _quick_signature() -> list:
    """Coup d'œil aux dossiers où l'on installe des polices — ceux du système et celui des polices ajoutées — sans
    les parcourir (date et nombre d'entrées), et aux formats des plugins : pas les dossiers des réglages ni des plugins
    (un partage réseau injoignable ne fige pas la fenêtre à chaque retour)."""
    out = []
    for d in (*SYSTEM_FONT_DIRS, user_font_dir()):
        try:
            out.append([str(d), os.stat(d).st_mtime_ns, len(os.listdir(d))])
        except OSError:
            out.append([str(d), None, 0])
    from . import fontformats
    out.append(sorted(f'{e} {f.reader}' for e, f in fontformats.FORMATS.items()))
    return out


def rebase() -> None:
    """Les polices de maintenant comme point de départ de `rescan` : au lancement, une fois ajoutés les dossiers des
    réglages et des plugins (leurs polices ne sont pas des polices installées)."""
    global _SIG, _KNOWN, _QUICK
    fam = families()
    _SIG, _KNOWN, _QUICK = _signature(), set(fam), _quick_signature()


def rescan() -> dict | None:
    """Une police installée depuis le dernier `rescan` (ou le point de départ) : l'inventaire est refait. Rend {clé :
    nom affiché} des familles apparues (vide : des polices retirées seulement), None si rien n'a bougé. Coût sans
    changement : un coup d'œil aux dossiers où l'on installe des polices (`_quick_signature`) ; s'ils ont bougé, un
    parcours de tous les dossiers. Un dossier illisible : OSError."""
    global _SIG, _KNOWN, _QUICK
    if _SIG is None:
        families()
        _QUICK = _quick_signature()
        return None
    quick = _quick_signature()
    if quick == _QUICK:
        return None
    _QUICK = quick
    sig = _signature()
    if sig == _SIG:
        return None
    refresh()
    after = families()
    shown = {_key(n): n for n in (*PLUGIN_FONTS, *SVG_FONTS)}
    keys = {k for k in after if k not in _KNOWN}       # noms complets, noms de fichier compris : les textes s'y réfèrent
    new = {k: NAMES.get(k) or shown.get(k) for k in keys if NAMES.get(k) or shown.get(k)}
    _SIG, _KNOWN = sig, set(after)
    _HISTORY.append(keys)
    return new


def generation() -> int:
    """Nombre d'inventaires refaits par `rescan` : une liste de polices remplie avant une génération plus récente
    est à refaire."""
    return len(_HISTORY)


def added_since(gen: int) -> set:
    """Clés des familles apparues depuis la génération `gen`."""
    return set().union(*_HISTORY[max(0, gen):])


def unlisted_families(listed) -> list[str]:
    """Familles TrueType / OpenType de l'inventaire absentes de `listed` (les noms que Qt connaît) : celles des
    dossiers ajoutés, et celles installées dans le système depuis le lancement (Qt lit les polices du système à son
    lancement : les autres familles du système y sont, sous leur nom à lui)."""
    families()
    names, system = dict(NAMES), set(SYSTEM_KEYS)       # un inventaire d'un autre fil peut les refaire en même temps
    seen = {_key(n) for n in listed}
    late = added_since(0)
    return sorted((n for k, n in names.items() if k not in seen and (k not in system or k in late)), key=str.lower)


def is_available(name: str) -> bool:
    """La police existe sur le poste (sans police de remplacement)."""
    k = _key(name)
    if builtin_named(name) is not None:
        return True
    fam = families()
    return any(c in fam for c in (k, k.replace('gras', 'bold'), k.replace('italique', 'italic')))


def is_variable(name: str) -> bool:
    """Police à axes de variation (Bahnschrift…) : TypeEdit 13 ne la reconnaît pas, même installée."""
    found = find_font(name)
    if not found:
        return False
    try:
        return 'fvar' in load(*found)
    except Exception:
        return False


def installed(name: str) -> bool:
    """Police TrueType ou OpenType installée dans le système (un de ses dossiers de polices) : un autre logiciel,
    TypeEdit par exemple, la trouve aussi — même si VectorDrive en prend une copie d'un dossier ajouté. Non pour les
    polices intégrées de VectorDrive, les polices SVG et celles des seuls dossiers de VectorDrive (polices ajoutées,
    dossiers des réglages ou des plugins)."""
    if builtin_named(name) is not None:
        return False
    families()                                         # inventaire, et SYSTEM_KEYS, à jour
    k = _key(name)
    return any(c in SYSTEM_KEYS for c in (k, k.replace('gras', 'bold'), k.replace('italique', 'italic')))


def find_font(name: str) -> tuple[str, int] | None:
    """Fichier d'une police par son nom (tolérant : casse, espaces, « Gras »
    → « Bold »)."""
    k = _key(name)
    own = builtin_named(name)
    if own is not None:
        return own.PATH, 0
    fam = families()
    for cand in (k, k.replace('gras', 'bold'), k.replace('italique', 'italic')):
        if cand in fam:
            return fam[cand]
    for fb in FALLBACK:
        if _key(fb) in fam:
            return fam[_key(fb)]
    return None


@functools.lru_cache(maxsize=32)
def load(path: str, index: int = 0):
    from fontTools.ttLib import TTFont
    return TTFont(path, fontNumber=index)


class _Pen:
    """Stylo fontTools → segments exacts (unités de la police)."""

    def __init__(self):
        self.contours: list[Contour] = []
        self.cur: list = []
        self.start = None
        self.pos = None

    def moveTo(self, p):
        self._flush(False)
        self.start = self.pos = tuple(p)

    def lineTo(self, p):
        p = tuple(p)
        if dist(self.pos, p) > 1e-9:
            self.cur.append(Line(self.pos, p))
        self.pos = p

    def curveTo(self, *pts):
        # plusieurs contrôles cubiques successifs (rare) : découpage implicite
        pts = [tuple(p) for p in pts]
        while len(pts) > 3:
            c1, c2 = pts[0], pts[1]
            mid = ((c2[0] + pts[2][0]) / 2, (c2[1] + pts[2][1]) / 2)
            self.cur.append(Cubic(self.pos, c1, c2, mid))
            self.pos = mid
            pts = pts[2:]
        c1, c2, p = pts
        self.cur.append(Cubic(self.pos, c1, c2, p))
        self.pos = p

    def qCurveTo(self, *pts):
        pts = [tuple(p) if p is not None else None for p in pts]
        if pts[-1] is None:                 # contour sans point sur la courbe
            pts = pts[:-1]
            first = ((pts[-1][0] + pts[0][0]) / 2, (pts[-1][1] + pts[0][1]) / 2)
            self.moveTo(first)
            pts = pts + [first]
        *ctrls, end = pts
        for i, c in enumerate(ctrls):
            if i < len(ctrls) - 1:
                n = ctrls[i + 1]
                p = ((c[0] + n[0]) / 2, (c[1] + n[1]) / 2)
            else:
                p = end
            self.cur.append(Conic(self.pos, c, p, 1.0))
            self.pos = p

    def closePath(self):
        if self.cur and dist(self.pos, self.start) > 1e-9:
            self.cur.append(Line(self.pos, self.start))
        self._flush(True)

    def endPath(self):
        self._flush(False)

    def addComponent(self, glyphName, transformation):
        raise NotImplementedError       # résolu par DecomposingPen

    def _flush(self, closed):
        if self.cur:
            self.contours.append(Contour(self.cur, closed))
        self.cur = []


@functools.lru_cache(maxsize=32)
def characters(name: str) -> tuple:
    """Caractères dessinés par une police (sa table des caractères), dans
    l'ordre des codes, sans les caractères de contrôle."""
    ff = find_font(name) if is_available(name) else None   # find_font retomberait sur Arial
    if not ff:
        return ()
    own = builtin(ff[0])
    if own is not None:
        return own.characters()
    from . import fontformats, svgfonts
    try:
        fmt = fontformats.of(ff[0])
        if fmt is not None:
            codes = fmt.characters(ff[0]) if fmt.characters is not None else ()
        elif _is_svg(ff[0]):
            codes = svgfonts.load(ff[0]).index.keys()
        else:
            codes = (load(ff[0], ff[1]).getBestCmap() or {}).keys()
    except Exception:                                  # police illisible : rien à proposer
        return ()
    return tuple(chr(c) for c in sorted(codes) if c >= 0x20 and not 0x7F <= c < 0xA0 and c <= 0x10FFFF)


@functools.lru_cache(maxsize=8)
def char_set(name: str) -> frozenset:
    return frozenset(characters(name))


@functools.lru_cache(maxsize=16384)
def glyph(path: str, index: int, char: str) -> tuple[Path, float]:
    """(contour en unités de police, avance horizontale), gardé pour la séance
    (un BAT de milliers de cotes relisait chaque chiffre dans la police) ; le
    tracé rendu est partagé : on le transforme, on ne le modifie pas."""
    own = builtin(path)
    if own is not None:
        return own.glyph(char)
    from . import fontformats, svgfonts
    fmt = fontformats.of(path)
    if fmt is not None:
        return fontformats.read_glyph(fmt, path, char)
    if _is_svg(path):
        return svgfonts.glyph(path, char)
    from fontTools.pens.recordingPen import DecomposingRecordingPen
    f = load(path, index)
    cmap = f.getBestCmap() or {}
    gname = cmap.get(ord(char))
    gs = f.getGlyphSet()
    if gname is None or gname not in gs:
        return Path(), f['hmtx'].metrics.get('.notdef', (0, 0))[0] if 'hmtx' in f else 0.0
    rec = DecomposingRecordingPen(gs)
    gs[gname].draw(rec)
    pen = _Pen()
    for op, args in rec.value:
        getattr(pen, op)(*args)
    pen._flush(False)
    return Path(pen.contours), float(gs[gname].width)


@functools.lru_cache(maxsize=64)
def metrics(path: str, index: int = 0) -> dict:
    """Métriques utiles. La hauteur de capitales est **mesurée** sur le
    « H » (la valeur déclarée par la police peut différer d'une unité) ;
    à défaut, valeur déclarée, puis 70 % de l'ascendante. Polices
    lues par un plugin, polices SVG : leurs propres mesures."""
    own = builtin(path)
    if own is not None:
        return own.metrics()
    from . import fontformats, svgfonts
    fmt = fontformats.of(path)
    if fmt is not None:
        return fontformats.read_metrics(fmt, path)
    if _is_svg(path):
        return svgfonts.metrics(path)
    f = load(path, index)
    hh = f['hhea']
    os2 = f['OS/2'] if 'OS/2' in f else None
    cap = 0.0
    g, _adv = glyph(path, index, 'H')
    if g:
        bb = g.bbox()
        cap = bb[3]
    if cap <= 0:
        cap = float(getattr(os2, 'sCapHeight', 0) or hh.ascent * 0.7)
    return {'upem': float(f['head'].unitsPerEm), 'ascent': float(hh.ascent),
            'descent': float(-hh.descent), 'cap': cap}


# --- crénage --------------------------------------------------------------------

_KERN_CACHE: dict = {}


def _gpos_kern_subtables(f) -> list:
    """Sous-tables de paires (GPOS, type 2, extensions comprises) des
    recherches de la fonction « kern », prêtes à interroger."""
    if 'GPOS' not in f:
        return []
    g = f['GPOS'].table
    if not g.FeatureList or not g.LookupList:
        return []
    idx = sorted({i for fr in g.FeatureList.FeatureRecord if fr.FeatureTag == 'kern'
                  for i in fr.Feature.LookupListIndex})
    out = []
    for li in idx:
        lk = g.LookupList.Lookup[li]
        for st in lk.SubTable:
            typ = lk.LookupType
            if typ == 9:
                typ, st = st.ExtensionLookupType, st.ExtSubTable
            if typ != 2:
                continue
            cov = list(st.Coverage.glyphs) if st.Coverage else []
            if st.Format == 1:
                m = {}
                for first, ps in zip(cov, st.PairSet):
                    m[first] = {r.SecondGlyph: getattr(r.Value1, 'XAdvance', 0) or 0
                                for r in ps.PairValueRecord if r.Value1 is not None}
                out.append(('pair', m))
            elif st.Format == 2:
                cd1 = st.ClassDef1.classDefs if st.ClassDef1 else {}
                cd2 = st.ClassDef2.classDefs if st.ClassDef2 else {}
                mat = [[getattr(c2.Value1, 'XAdvance', 0) or 0 if c2.Value1 is not None else 0
                        for c2 in c1.Class2Record] for c1 in st.Class1Record]
                out.append(('class', (set(cov), cd1, cd2, mat)))
    return out


def svg_families() -> list[str]:
    """Noms des polices SVG trouvées, triés."""
    families()
    return sorted(SVG_FONTS, key=str.lower)


def refresh() -> None:
    """Une police vient d'être ajoutée : refaire l'inventaire."""
    families.cache_clear()
    characters.cache_clear()
    char_set.cache_clear()


def font_changed() -> None:
    """Une police vient d'être réécrite : oublier tout ce qu'on en a gardé, jusqu'à l'inventaire sur le disque :
    son nom a pu changer sans que la signature des dossiers bouge."""
    from . import fontformats, svgfonts
    try:
        cache_file().unlink(missing_ok=True)
    except OSError:
        pass
    refresh()
    glyph.cache_clear()
    metrics.cache_clear()
    _KERN_CACHE.clear()
    for fmt in fontformats.registered():
        if fmt.clear is not None:
            fmt.clear()
    svgfonts.glyph.cache_clear()
    svgfonts.load.cache_clear()


def plugin_families() -> list[str]:
    """Noms des polices lues par les plugins (`fontformats`), triés."""
    families()
    return sorted(PLUGIN_FONTS, key=str.lower)


def kerning(path: str, index: int = 0):
    """Fonction (glyphe gauche, glyphe droit) → crénage en unités de la
    police : GPOS (fonction « kern ») si la police en a, sinon la table
    « kern » classique — comme les moteurs de rendu."""
    key = (path, index)
    fn = _KERN_CACHE.get(key)
    if fn is not None:
        return fn
    f = load(path, index)
    subs = _gpos_kern_subtables(f)
    cache: dict = {}
    if subs:
        def fn(a: str, b: str) -> float:
            k = (a, b)
            if k in cache:
                return cache[k]
            v = 0.0
            for kind, data in subs:
                if kind == 'pair':
                    d = data.get(a)
                    if d is not None and b in d:
                        v = float(d[b])
                        break
                else:
                    cov, cd1, cd2, mat = data
                    if a in cov:
                        c1, c2 = cd1.get(a, 0), cd2.get(b, 0)
                        if c1 < len(mat) and c2 < len(mat[c1]):
                            v = float(mat[c1][c2])
                        break
            cache[k] = v
            return v
    elif 'kern' in f:
        tables = [getattr(t, 'kernTable', {}) for t in f['kern'].kernTables]

        def fn(a: str, b: str) -> float:
            for t in tables:
                v = t.get((a, b))
                if v:
                    return float(v)
            return 0.0
    else:
        def fn(a: str, b: str) -> float:
            return 0.0
    _KERN_CACHE[key] = fn
    return fn
