"""Textes variables (comme TypeEdit : Variables, Insérer un texte variable,
Séries, Date et Heure).

Un texte variable porte des marques `|Nom|` : à l'affichage d'un état (une
ligne du tableau), chaque marque prend la valeur de la variable sur cette
ligne. `|Date|` et `|Heure|` prennent la date et l'heure du moment,
suivies au besoin d'un format (`|Date dd/MM/yyyy|`, `|Heure HH:mm|`, codes
de TypeEdit). Une marque inconnue reste telle quelle.

Le tableau des variables (noms en colonnes, une ligne par état) est gardé
dans le document (`doc.extra['variables']`) ; le modèle de chaque texte
variable dans `text.extra['template']`.
"""
from __future__ import annotations

import datetime
import re
from dataclasses import dataclass, field

TOKEN = re.compile(r'\|([^|\n]+)\|')
DAYS = ['lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche']
MONTHS = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre',
          'novembre', 'décembre']
DATE_DEFAULT = 'dd/MM/yyyy'
TIME_DEFAULT = 'HH:mm'


@dataclass
class VarTable:
    names: list = field(default_factory=list)
    rows: list = field(default_factory=list)        # [[valeur par variable]]
    current: int = 0                                # état affiché (ligne)

    def to_dict(self) -> dict:
        return {'names': list(self.names), 'rows': [list(r) for r in self.rows], 'current': self.current}

    @classmethod
    def from_dict(cls, d) -> 'VarTable':
        d = d or {}
        names = [str(n) for n in d.get('names', [])]
        rows = [[str(v) for v in r] + [''] * (len(names) - len(r)) for r in d.get('rows', [])]
        return cls(names, [r[:len(names)] for r in rows], int(d.get('current', 0) or 0))

    def add_variable(self, name: str, values=()) -> None:
        name = name.strip()
        if not name or name in self.names:
            raise ValueError(f'variable « {name} » vide ou déjà là')
        self.names.append(name)
        values = list(values)
        while len(self.rows) < len(values):
            self.rows.append([''] * (len(self.names) - 1))
        for i, r in enumerate(self.rows):
            r.append(values[i] if i < len(values) else '')

    def remove_variable(self, name: str) -> None:
        i = self.names.index(name)
        del self.names[i]
        for r in self.rows:
            del r[i]

    def rename(self, old: str, new: str) -> None:
        new = new.strip()
        if not new or (new != old and new in self.names):
            raise ValueError(f'nom « {new} » vide ou déjà pris')
        self.names[self.names.index(old)] = new

    def row(self, k: int | None = None) -> dict:
        k = self.current if k is None else k
        if not self.rows:
            return {}
        k = max(0, min(k, len(self.rows) - 1))
        return dict(zip(self.names, self.rows[k]))


def table_of(doc) -> VarTable:
    return VarTable.from_dict(doc.extra.get('variables') if isinstance(doc.extra, dict) else None)


def store(doc, table: VarTable) -> None:
    doc.extra['variables'] = table.to_dict()


# --- date et heure (codes de TypeEdit) -----------------------------------------------------
_CODES = re.compile(r'dddd|ddd|dd|d|MMMM|MMM|MM|M|yyyy|yy|y|HH|H|hh|h|mm|m|ss|s|tt|t')


def format_datetime(fmt: str, dt: datetime.datetime) -> str:
    """Format de TypeEdit (d, dd, ddd, dddd, M…MMMM, y, yy, yyyy, h, hh, H,
    HH, m, mm, s, ss, t, tt) ; le reste est recopié."""
    h12 = dt.hour % 12 or 12
    am = 'AM' if dt.hour < 12 else 'PM'
    val = {'d': str(dt.day), 'dd': f'{dt.day:02d}', 'ddd': DAYS[dt.weekday()][:3], 'dddd': DAYS[dt.weekday()],
           'M': str(dt.month), 'MM': f'{dt.month:02d}', 'MMM': MONTHS[dt.month - 1][:3],
           'MMMM': MONTHS[dt.month - 1], 'y': str(dt.year % 10), 'yy': f'{dt.year % 100:02d}',
           'yyyy': f'{dt.year:04d}', 'h': str(h12), 'hh': f'{h12:02d}', 'H': str(dt.hour),
           'HH': f'{dt.hour:02d}', 'm': str(dt.minute), 'mm': f'{dt.minute:02d}', 's': str(dt.second),
           'ss': f'{dt.second:02d}', 't': am[0], 'tt': am}
    return _CODES.sub(lambda m: val[m.group(0)], fmt)


def tokens(text: str) -> list[str]:
    """Noms des marques d'un texte, dans l'ordre (sans doublon)."""
    out = []
    for m in TOKEN.finditer(text or ''):
        n = m.group(1).strip()
        if n not in out:
            out.append(n)
    return out


def render(template: str, values: dict, now: datetime.datetime | None = None) -> str:
    """Le texte d'un état : chaque `|Nom|` remplacé par sa valeur."""
    now = now or datetime.datetime.now()

    def sub(m):
        name = m.group(1).strip()
        if name in values:
            return str(values[name])
        head, _, fmt = name.partition(' ')
        if head.lower() == 'date':
            return format_datetime(fmt.strip() or DATE_DEFAULT, now)
        if head.lower() == 'heure':
            return format_datetime(fmt.strip() or TIME_DEFAULT, now)
        return m.group(0)
    return TOKEN.sub(sub, template or '')


# --- séries ------------------------------------------------------------------------------------
def _alpha(n: int) -> str:
    """1 → A, 26 → Z, 27 → AA (colonnes de tableur)."""
    s = ''
    n = max(1, n)
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def series(start: int = 1, step: int = 1, count: int = 10, *, end: int | None = None, kind: str = 'numérique',
           width: str = '', before: str = '', after: str = '') -> list[str]:
    """Valeurs d'une série (TypeEdit : Séries) : de `start`, au pas `step`,
    `count` valeurs ou jusqu'à `end` ; numérique, alphabétique (A, B… AA)
    ou alphanumérique (A1, A2… : la lettre change tous les 10 nombres) ;
    `width` : format à nombre de chiffres constant (« ### » → 007) ;
    texte avant et après."""
    step = step or 1
    if end is not None:
        count = max(0, (end - start) // step + 1)
    out = []
    for i in range(max(0, count)):
        n = start + i * step
        if kind == 'alphabétique':
            core = _alpha(n)
        elif kind == 'alphanumérique':
            q, r = divmod(max(0, n - 1), 10)
            core = f'{_alpha(q + 1)}{r + 1}'
        else:
            core = str(n)
            if width and '#' in width:
                k = width.count('#')
                core = width.replace('#' * k, str(n).zfill(k), 1) if '#' * k in width else str(n).zfill(k)
        out.append(f'{before}{core}{after}')
    return out


def decode_text(raw: bytes) -> str:
    """Le texte d'un fichier de données : Unicode (avec ou sans marque de début, comme l'écrit le Bloc-notes), UTF-8,
    sinon la page de code de Windows. Ne lève jamais d'erreur."""
    for mark, enc in ((b'\xff\xfe\x00\x00', 'utf-32-le'), (b'\x00\x00\xfe\xff', 'utf-32-be'), (b'\xef\xbb\xbf', 'utf-8-sig'),
                      (b'\xff\xfe', 'utf-16-le'), (b'\xfe\xff', 'utf-16-be')):
        if raw.startswith(mark):
            return raw[len(mark) if enc != 'utf-8-sig' else 0:].decode(enc, errors='replace')
    sample = raw[:4096]
    if len(sample) >= 4:                                 # UTF-16 sans marque : un octet nul sur deux, ou presque
        odd, even = sample[1::2].count(0), sample[0::2].count(0)
        if odd > len(sample) * 0.2 and even == 0:
            return raw.decode('utf-16-le', errors='replace')
        if even > len(sample) * 0.2 and odd == 0:
            return raw.decode('utf-16-be', errors='replace')
    try:
        return raw.decode('utf-8')
    except UnicodeDecodeError:
        return raw.decode('cp1252', errors='replace')


def split_lines(text: str, line_sep: str | None = None) -> list[str]:
    """Les lignes du fichier, vides comprises : leur numéro est celui que montre l'aperçu."""
    text = text or ''
    if line_sep:
        out = text.split(line_sep)
        out = [ln.strip('\r\n') for ln in out]
    else:
        out = text.splitlines()
    return out


def parse_widths(text: str) -> list[int]:
    """« 5,10,3 » : la largeur de chaque colonne, en caractères. Ce qui n'est pas un nombre entier positif est ignoré."""
    out = []
    for part in str(text or '').replace(';', ',').split(','):
        part = part.strip()
        if part.isdigit() and int(part) > 0:
            out.append(int(part))
    return out


def _fixed_cells(line: str, widths: list[int]) -> list[str]:
    """Une ligne en colonnes de largeur donnée. Une seule largeur : toutes les colonnes. Le reste forme une dernière colonne."""
    cells, at = [], 0
    if len(widths) == 1:
        while at < len(line):
            cells.append(line[at:at + widths[0]])
            at += widths[0]
    else:
        for w in widths:
            cells.append(line[at:at + w])
            at += w
        if line[at:].strip():
            cells.append(line[at:])
    return cells


def _sep_cells(line: str, sep: str) -> list[str]:
    """Une ligne en colonnes. Un séparateur d'un seul caractère respecte les guillemets, comme à la sortie d'un tableur."""
    if len(sep) == 1:
        import csv
        for row in csv.reader([line], delimiter=sep):
            return row
        return ['']
    return line.split(sep)


def parse_data(text: str, *, sep: str | None = None, header: bool = True, start: int = 0, line_sep: str | None = None,
               widths: list | None = None, group: bool = False) -> VarTable:
    """Données importées (texte brut : une ligne par état, valeurs séparées
    par un point-virgule ou une tabulation, devinés sinon) ; `header` : la
    première ligne porte les noms (sinon VAR1, VAR2…) ; `start` : le numéro de
    la première ligne lue ; `line_sep` : autre séparateur de lignes ; `widths` :
    colonnes de largeur constante ; `group` : une seule des lignes identiques qui se suivent."""
    lines = [ln for ln in split_lines(text, line_sep)[max(int(start), 0):] if ln.strip()]
    if not lines:
        return VarTable()
    if widths:
        cells = [[c.strip() for c in _fixed_cells(ln, widths)] for ln in lines]
    else:
        if sep is None:
            sep = max(('\t', ';', ','), key=lambda c: lines[0].count(c))
        cells = [[c.strip() for c in _sep_cells(ln, sep)] for ln in lines]
    width = max(len(r) for r in cells)
    if header:
        names = cells[0] + [f'VAR{i + 1}' for i in range(len(cells[0]), width)]
        names = [n or f'VAR{i + 1}' for i, n in enumerate(names)]
        cells = cells[1:]
    else:
        names = [f'VAR{i + 1}' for i in range(width)]
    rows = [r + [''] * (width - len(r)) for r in cells]
    if group:
        rows = [r for i, r in enumerate(rows) if i == 0 or r != rows[i - 1]]
    return VarTable(names, rows)


def variable_texts(doc) -> list:
    """Textes du dessin qui ont des marques (ou un modèle gardé)."""
    from .document import Text
    return [t for t in doc.iter_leaves() if isinstance(t, Text)
            and ('template' in t.extra or TOKEN.search(t.text or ''))]


def apply_row(doc, k: int | None = None, now=None) -> list:
    """Affiche l'état `k` (la ligne) : chaque texte variable prend ses valeurs
    (modèle gardé au premier passage) ; rend les textes changés."""
    from . import text as TX
    from .document import drop_source_object
    table = table_of(doc)
    if k is not None:
        table.current = max(0, min(k, max(0, len(table.rows) - 1)))
        store(doc, table)
    values = table.row()
    changed = []
    for t in variable_texts(doc):
        tpl = t.extra.setdefault('template', t.text)
        new = render(tpl, values, now)
        if new != t.text:
            t.text = new
            drop_source_object(t)                        # le texte n'est plus l'objet du fichier d'origine
            try:
                t.outline = TX.outline_for(t)
            except Exception:                            # police absente : contour gardé
                pass
            changed.append(t)
    return changed


def has_clock(template: str) -> bool:
    """Le modèle porte-t-il une date ou une heure (|Date…|, |Heure…|) ?"""
    return any(n.partition(' ')[0].lower() in ('date', 'heure') for n in tokens(template))


def refresh_dates(doc, now=None, *, dry: bool = False) -> list:
    """Textes datés remis à la date du moment, avec les valeurs de l'état
    affiché (TauDrive : la date est réévaluée à chaque export) ; rend ceux
    qui changent — `dry` : sans rien toucher. Les états produits, devenus
    de simples textes, gardent la leur."""
    from . import text as TX
    from .document import drop_source_object
    values = table_of(doc).row()
    out = []
    for t in variable_texts(doc):
        tpl = t.extra.get('template', t.text)
        if not has_clock(tpl):
            continue
        new = render(tpl, values, now)
        if new == t.text:
            continue
        out.append(t)
        if dry:
            continue
        t.extra.setdefault('template', tpl)
        t.text = new
        drop_source_object(t)
        try:
            t.outline = TX.outline_for(t)
        except Exception:                                # police absente : contour gardé
            pass
    return out


def show_templates(doc) -> list:
    """Remet les marques (`|Nom|`) à la place des valeurs."""
    from . import text as TX
    from .document import drop_source_object
    out = []
    for t in variable_texts(doc):
        tpl = t.extra.get('template')
        if tpl is not None and t.text != tpl:
            t.text = tpl
            drop_source_object(t)
            try:
                t.outline = TX.outline_for(t)
            except Exception:
                pass
            out.append(t)
    return out


# --- production ----------------------------------------------------------------------------------
#: écart entre deux plaques suivantes (mm), comme l'imbrication
PLATE_GAP = 10.0


def uses_variables(items: list) -> bool:
    """Un de ces objets est-il un texte à marques (ou à modèle gardé) ?"""
    from .document import Group, Text
    for it in items:
        if isinstance(it, Group):
            if uses_variables(it.children):
                return True
        elif isinstance(it, Text) and ('template' in it.extra or TOKEN.search(it.text or '')):
            return True
    return False


def fill_values(it, values: dict, now=None) -> None:
    """Remplit les textes variables de cet objet : ils deviennent de simples textes."""
    from . import text as TX
    from .document import Group, Text
    if isinstance(it, Group):
        for ch in it.children:
            fill_values(ch, values, now)
    elif isinstance(it, Text) and ('template' in it.extra or TOKEN.search(it.text or '')):
        tpl = it.extra.get('template', it.text)
        it.extra = {kk: v for kk, v in it.extra.items() if kk != 'template'}
        it.text = render(tpl, values, now)
        try:
            it.outline = TX.outline_for(it)
        except Exception:
            pass


def produce(items: list, table: VarTable, box=None, *, first: int = 0, last: int | None = None,
            gap: float = 2.0, margin: float = 3.0, now=None) -> tuple[list, dict]:
    """Un exemplaire de `items` par état (lignes `first` à `last`) : chacun
    groupé (« État n »), ses textes variables remplis et devenus de simples
    textes, rangé en grille dans `box` (la plaque : de gauche à droite puis
    de haut en bas ; plaques suivantes à droite), sinon en ligne à droite des
    originaux. Rend (groupes, disposition)."""
    from .document import Group
    from .duplicate import _copy, fill_layout
    from .geom import Affine, bbox_union
    bb = bbox_union(it.bbox() for it in items)
    if not bb or not table.rows:
        return [], {}
    last = len(table.rows) - 1 if last is None else min(last, len(table.rows) - 1)
    states = list(range(max(0, first), last + 1))
    w, h = bb[2] - bb[0], bb[3] - bb[1]
    lay = fill_layout(w, h, box, gap, gap, margin) if box else None
    if not lay or lay['cols'] * lay['rows'] == 0:
        lay = {'cols': len(states), 'rows': 1, 'origin': (bb[2] + gap, bb[1]), 'w': w, 'h': h, 'rotated': False}
        pw = 0.0
    else:
        pw = box[2] - box[0] + PLATE_GAP
    per = lay['cols'] * lay['rows']
    ox, oy = lay['origin']
    out = []
    for n, k in enumerate(states):
        plate, cell = divmod(n, per)
        i, j = cell % lay['cols'], cell // lay['cols']
        x = ox + plate * pw + i * (w + gap)
        y = oy + (lay['rows'] - 1 - j) * (h + gap)               # première rangée en haut
        m = Affine.translation(x - bb[0], y - bb[1])
        copies = [_copy(it, m) for it in items]
        values = table.row(k)
        for c in copies:
            fill_values(c, values, now)
        out.append(Group(name=f'État {k + 1}', children=copies))
    lay = dict(lay, states=len(states), plates=(len(states) + per - 1) // per if per else 1)
    return out, lay

