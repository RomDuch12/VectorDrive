"""HPGL (.plt, .hpgl) : le format des anciens traceurs, découpeuses et graveuses. HP-GL et HP-GL/2 en lecture : plume
levée ou baissée, absolu ou relatif, échelles (IP, SC) et rotation (RO), cercles, arcs, rectangles, secteurs et
courbes, polylignes codées (PE), textes (LB), y compris dans l'enveloppe PCL des pilotes. Un plume = un outil.
Écrit à 40 unités par mm, comme il se doit, en droites et sans texte."""
from __future__ import annotations

import math
import pathlib
import re

from ..core.document import Document, Group, Image, Layer, Shape, Text
from ..core.geom import Affine, Contour, Cubic, Line, Path, arc_conics, circle, polyline

#: Unités du traceur par mm (0,025 mm l'unité)
UNITS = 40.0
#: Écart admis en écrivant les courbes en droites (mm)
FLATTEN = 0.02
#: Pas des arcs et cercles dessinés par le traceur quand le fichier n'en donne pas (degrés)
CHORD = 5.0
#: Police des textes : le traceur a la sienne, que le fichier ne porte pas
LABEL_FONT = 'Arial'
#: Cellule d'un caractère par défaut (mm)
CELL_W, CELL_H = 2.85, 3.75

_NUM = re.compile(r'[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?')
_ETX = '\x03'                                             # fin de texte par défaut
_TEXT_OPS = ('LB', 'BL', 'WD')                            # suivis d'un texte, jusqu'au caractère de fin
_DEVICE = re.compile(r'\x1b\.(?:[@HIMNPQST][^:]*:|.)', re.S)      # réglages du traceur : ESC.Y, ESC.@…:
_ENTER = re.compile(r'\x1b%-?\d*B')                       # entrée en HP-GL/2
_LEAVE = re.compile(r'\x1b%-?\d*[AX]')                    # retour au PCL, fin de travail
_ROTATIONS = {0: (1, 0, 0, 1), 90: (0, 1, -1, 0), 180: (-1, 0, 0, -1), 270: (0, -1, 1, 0)}


def _unwrap(text: str) -> str | None:
    """Le texte HPGL du fichier : sans les réglages du traceur, et sans l'enveloppe PCL des pilotes
    HP-GL/2. None : il n'y a là que du PCL."""
    if '\x1b%' in text:
        parts, pos = [], 0
        while True:
            m = _ENTER.search(text, pos)
            if m is None:
                break
            e = _LEAVE.search(text, m.end())
            parts.append(text[m.end():e.start() if e else len(text)])
            pos = e.end() if e else len(text)
        if not parts:
            return None
        text = ';'.join(parts)
    return _DEVICE.sub('', text)


def _is_op(c: str) -> bool:
    return c.isascii() and c.isalpha()


def _commands(text: str):
    """(mnémonique, liste de nombres ou texte) dans l'ordre du fichier."""
    i, n = 0, len(text)
    end = _ETX
    while i < n:
        c = text[i]
        if c == '"':                                      # BP1,"Nom du dessin" : ses lettres ne sont pas des commandes
            j = text.find('"', i + 1)
            i = j + 1 if j >= 0 else n
            continue
        if not _is_op(c):
            i += 1
            continue
        op = text[i:i + 2].upper()
        i += 2
        if op in _TEXT_OPS:
            j = text.find(end, i)
            j = j if j >= 0 else n
            yield op, text[i:j]
            i = j + 1
            continue
        if op == 'DT':                                    # DT* : le caractère de fin devient *
            c = text[i:i + 1]
            end = _ETX if c in ('', ';') else c
            i += 1
            yield op, []
            continue
        if op == 'SM':                                    # SM* : le symbole, qui peut être une lettre
            i += 1
            yield op, []
            continue
        if op == 'PE':                                    # polyligne codée : ses caractères sont tous permis
            j = text.find(';', i)
            j = j if j >= 0 else n
            yield op, text[i:j]
            i = j + 1
            continue
        if op in ('IN', 'DF'):
            end = _ETX
        args, j = [], i
        while j < n and not _is_op(text[j]) and text[j] != ';':
            if text[j] == '"':
                args.append(text[i:j])
                k = text.find('"', j + 1)
                i = j = k + 1 if k >= 0 else n
                continue
            j += 1
        args.append(text[i:j])
        yield op, [float(v) for v in _NUM.findall(' '.join(args))]
        i = j


class _Pen:
    """Le traceur, tel que le fichier le fait bouger. La position est en unités du fichier ; le
    tracé, en mm (`m` passe des unes aux autres : échelle de IP/SC, puis rotation de RO)."""

    def __init__(self):
        self.pen = 1
        self.by_pen: dict = {}                            # plume -> contours
        self.texts: list = []                             # (plume, Text)
        self.labels = 0
        self.guessed = False                              # une échelle dont la taille réelle dépendait du traceur
        self.sheets = 0                                   # pages dessinées, sans la dernière
        self.drawn = False
        self.chain: list = []                             # segments du trait en cours (mm)
        self.init()

    def init(self) -> None:
        """IN : le traceur revient à ses réglages."""
        self.x = self.y = 0.0
        self.down = False
        self.absolute = True
        self.p1 = self.p2 = None
        self.sc = None
        self.ro = 0
        self.m = Affine(1 / UNITS, 0, 0, 1 / UNITS, 0, 0)
        self.text_defaults()

    def text_defaults(self) -> None:
        self.cw, self.ch = CELL_W, CELL_H
        self.run, self.rise = 1.0, 0.0
        self.slant = 0.0
        self.origin = 1
        self.extra_x = self.extra_y = 0.0
        self.cr = None                                    # où revient un retour chariot (mm)

    # --- échelles ---

    def _user(self) -> tuple:
        x0, x1, y0, y1, *rest = self.sc
        kind = int(rest[0]) if rest else 0
        px, py = self.p1 or (0.0, 0.0)
        if kind == 2:                                     # SC xmin, facteur x, ymin, facteur y, 2 : sans P2
            return x1, y1, px - x0 * x1, py - y0 * y1
        dx, dy = (self.p2[0] - px, self.p2[1] - py) if self.p2 else (0.0, 0.0)
        if dx == 0.0 or dy == 0.0:                        # la taille venait du papier du traceur
            self.guessed = True
            return 1.0, 1.0, px - x0, py - y0
        ux, uy = dx / (x1 - x0), dy / (y1 - y0)
        if kind == 1:                                     # isotrope : l'échelle la plus petite, le reste selon left, bottom
            s = min(abs(ux), abs(uy))
            sx, sy = math.copysign(s, ux), math.copysign(s, uy)
            left = rest[1] if len(rest) > 1 else 50.0
            bottom = rest[2] if len(rest) > 2 else 50.0
            px += (dx - sx * (x1 - x0)) * left / 100.0
            py += (dy - sy * (y1 - y0)) * bottom / 100.0
            ux, uy = sx, sy
        return ux, uy, px - x0 * ux, py - y0 * uy

    def rescale(self) -> None:
        """Une nouvelle échelle : le plume ne bouge pas sur le papier."""
        here = self.here()
        ux, uy, ox, oy = self._user() if self.sc is not None else (1.0, 1.0, 0.0, 0.0)
        m = Affine(ux / UNITS, 0, 0, uy / UNITS, ox / UNITS, oy / UNITS)
        if self.ro:
            a, b, c, d = _ROTATIONS.get(self.ro, (None,) * 4)
            m = (Affine(a, b, c, d, 0, 0) if a is not None else Affine.rotation(self.ro)) @ m
        self.m = m
        self.x, self.y = m.inverse().apply(here)

    def set_scale(self, a: list) -> None:
        self.flush()
        if not a:
            self.sc = None
        elif len(a) >= 4:
            two = len(a) > 4 and int(a[4]) == 2
            if (a[1] != 0.0 and a[3] != 0.0) if two else (a[0] != a[1] and a[2] != a[3]):
                self.sc = list(a)
        self.rescale()

    def set_window(self, a: list) -> None:
        self.flush()
        if not a:
            self.p1 = self.p2 = None
        elif len(a) >= 4:
            self.p1, self.p2 = (a[0], a[1]), (a[2], a[3])
        elif len(a) >= 2:                                 # IP x, y : P2 suit P1
            if self.p1 is not None and self.p2 is not None:
                self.p2 = (self.p2[0] + a[0] - self.p1[0], self.p2[1] + a[1] - self.p1[1])
            self.p1 = (a[0], a[1])
        self.rescale()

    def set_rotation(self, a: list) -> None:
        self.flush()
        self.ro = int(a[0]) % 360 if a else 0
        self.rescale()

    # --- tracé ---

    def add(self, contour: Contour) -> None:
        if contour.segments:
            self.by_pen.setdefault(self.pen, []).append(contour)
            self.drawn = True

    def flush(self, close: bool = False) -> None:
        segs, self.chain = self.chain, []
        if not segs:
            return
        start, end = segs[0].start, segs[-1].end
        if close and math.dist(start, end) >= 1e-6 and len(segs) >= 2:
            segs.append(Line(end, start))
        closed = len(segs) >= 2 and math.dist(start, segs[-1].end) < 1e-6
        if closed and isinstance(segs[-1], Line):         # fermé exactement
            segs[-1] = Line(segs[-1].start, start)
        self.add(Contour(segs, closed))

    def mm(self, x: float, y: float) -> tuple:
        return self.m.apply((x, y))

    def here(self) -> tuple:
        return self.mm(self.x, self.y)

    def go(self, numbers: list) -> None:
        for k in range(0, len(numbers) - 1, 2):
            prev = self.here()
            if self.absolute:
                self.x, self.y = numbers[k], numbers[k + 1]
            else:
                self.x += numbers[k]
                self.y += numbers[k + 1]
            self.cr = None
            if self.down:
                q = self.here()
                if q != prev:
                    self.chain.append(Line(prev, q))

    def arc(self, cx: float, cy: float, sweep: float) -> None:
        r = math.hypot(self.x - cx, self.y - cy)
        if r <= 0.0:
            return
        sweep = max(-360.0, min(360.0, sweep))
        t0 = math.degrees(math.atan2(self.y - cy, self.x - cx))
        if self.down:
            self.chain.extend(Contour(arc_conics((cx, cy), r, r, t0, sweep), False).transformed(self.m).segments)
        t1 = math.radians(t0 + sweep)
        self.x, self.y = cx + r * math.cos(t1), cy + r * math.sin(t1)
        self.cr = None

    def arc3(self, ix: float, iy: float, ex: float, ey: float) -> None:
        """Un arc par trois points : le plume, (ix, iy), (ex, ey)."""
        ax, ay = self.x, self.y
        d = 2.0 * ((ix - ax) * (ey - ay) - (iy - ay) * (ex - ax))
        if abs(d) < 1e-9:                                 # alignés : un trait
            keep, self.absolute = self.absolute, True
            self.go([ex, ey])
            self.absolute = keep
            return
        i2, e2 = (ix - ax) ** 2 + (iy - ay) ** 2, (ex - ax) ** 2 + (ey - ay) ** 2
        cx = ax + (i2 * (ey - ay) - e2 * (iy - ay)) / d
        cy = ay + (e2 * (ix - ax) - i2 * (ex - ax)) / d
        t0 = math.degrees(math.atan2(ay - cy, ax - cx))
        to_i = (math.degrees(math.atan2(iy - cy, ix - cx)) - t0) % 360.0
        to_e = (math.degrees(math.atan2(ey - cy, ex - cx)) - t0) % 360.0
        self.arc(cx, cy, to_e if to_i <= to_e else to_e - 360.0)
        self.x, self.y = ex, ey

    def rectangle(self, x1: float, y1: float) -> None:
        self.flush()
        x0, y0 = self.x, self.y
        self.add(polyline([self.mm(x0, y0), self.mm(x1, y0), self.mm(x1, y1), self.mm(x0, y1)], closed=True))

    def wedge(self, r: float, start: float, sweep: float) -> None:
        """Un secteur : du plume au bord, l'arc, retour au plume."""
        self.flush()
        r = abs(r)
        if r <= 0.0 or sweep == 0.0:
            return
        sweep = max(-360.0, min(360.0, sweep))
        c = (self.x, self.y)
        arc = Contour(arc_conics(c, r, r, start, sweep), False).transformed(self.m).segments
        if abs(sweep) >= 360.0:
            self.add(Contour(arc, True))
            return
        here = self.here()
        self.add(Contour([Line(here, arc[0].start)] + list(arc) + [Line(arc[-1].end, here)], True))

    def beziers(self, a: list, relative: bool) -> None:
        for k in range(0, len(a) - 5, 6):
            bx, by = (self.x, self.y) if relative else (0.0, 0.0)
            prev = self.here()
            q1, q2 = self.mm(bx + a[k], by + a[k + 1]), self.mm(bx + a[k + 2], by + a[k + 3])
            self.x, self.y = bx + a[k + 4], by + a[k + 5]
            if self.down:
                self.chain.append(Cubic(prev, q1, q2, self.here()))
            self.cr = None

    def encoded(self, data: str) -> None:
        """PE : des nombres codés dans des caractères, en relatif et plume baissée sauf contrordre."""
        was_down, was_absolute = self.down, self.absolute
        i, n = 0, len(data)
        seven, fraction = False, 0

        def number():
            nonlocal i
            value, weight, digits = 0, 1, 0
            while i < n:
                c = ord(data[i])
                if c < 63 and digits == 0 and data[i] in ':<=>7':
                    return None
                i += 1
                if seven:
                    digit, last = (c - 63, False) if 63 <= c <= 94 else ((c - 95, True) if 95 <= c <= 126 else (None, False))
                else:
                    digit, last = (c - 63, False) if 63 <= c <= 126 else ((c - 191, True) if 191 <= c <= 254 else (None, False))
                if digit is None:
                    continue
                value += digit * weight
                weight *= 32 if seven else 64
                digits += 1
                if last:
                    return -(value >> 1) if value & 1 else value >> 1
            return None

        up = absolute = False
        while i < n:
            c = data[i]
            if c in ':<=>7':
                i += 1
                if c == ':':
                    v = number()
                    if v is not None:
                        self.flush()
                        self.pen = v
                elif c == '>':
                    v = number()
                    if v is not None:
                        fraction = v
                elif c == '<':
                    up = True
                elif c == '=':
                    absolute = True
                else:
                    seven = True
                continue
            x, y = number(), number() if i < n else None
            if x is None or y is None:
                if i >= n:
                    break
                continue
            k = 2.0 ** fraction
            if up:
                self.flush()
            self.down, self.absolute = not up, absolute
            self.go([x / k, y / k])
            up = absolute = False
        self.down, self.absolute = was_down, was_absolute

    # --- textes ---

    def axes(self) -> tuple:
        t = math.atan2(self.rise, self.run) + math.radians(self.ro)
        return t, (math.cos(t), math.sin(t)), (-math.sin(t), math.cos(t))

    def advance(self) -> float:
        return 1.5 * self.cw * (1.0 + self.extra_x)

    def feed(self) -> float:
        return 2.0 * self.ch * (1.0 + self.extra_y)

    def set_here(self, q: tuple) -> None:
        self.x, self.y = self.m.inverse().apply(q)

    def _text(self, run: str, q: tuple, t: float) -> None:
        adv = self.advance()
        width = adv * (len(run) - 1) + self.cw
        k = self.origin - 10 if self.origin > 10 else self.origin
        k = k if 1 <= k <= 9 else 1
        col, row = (k - 1) // 3, (k - 1) % 3
        dx, dy = -width * col / 2.0, -self.ch * row / 2.0
        if self.origin > 10:                              # LO 11 à 19 : un quart de cellule à côté du point
            dx += self.cw * 0.25 * (1 - col)
            dy += self.ch * 0.25 * (1 - row)
        item = Text(text=run, font=LABEL_FONT, size=self.ch, tool=max(0, self.pen - 1))
        item.matrix = Affine.translation(*q) @ Affine.rotation(math.degrees(t)) @ Affine.translation(dx, dy)
        item.extra['fit'] = {'width': width, 'mode': 'width'}
        if self.slant:
            item.extra['italic'] = math.degrees(math.atan(self.slant))
        self.texts.append((self.pen, item))
        self.drawn = True

    def label(self, text: str) -> None:
        self.flush()
        self.labels += 1
        t, u, v = self.axes()
        adv, feed = self.advance(), self.feed()
        q = self.here()
        if self.cr is None:
            self.cr = q
        run = ''

        def emit():
            nonlocal run, q
            if run.strip():
                self._text(run, q, t)
            q = (q[0] + u[0] * adv * len(run), q[1] + u[1] * adv * len(run))
            run = ''

        for ch in text:
            if ch == '\r':
                emit()
                q = self.cr
            elif ch == '\n':
                emit()
                q = (q[0] - v[0] * feed, q[1] - v[1] * feed)
                self.cr = (self.cr[0] - v[0] * feed, self.cr[1] - v[1] * feed)
            elif ch == '\b':
                emit()
                q = (q[0] - u[0] * adv, q[1] - u[1] * adv)
            elif ch >= ' ':
                run += ch
        emit()
        self.set_here(q)

    def carriage(self, a: list) -> None:
        """CP : se déplacer en caractères et en lignes ; sans valeur, au début de la ligne suivante."""
        self.flush()
        _t, u, v = self.axes()
        q = self.here()
        if self.cr is None:
            self.cr = q
        if len(a) >= 2:
            s, l = a[0] * self.advance(), a[1] * self.feed()
            self.set_here((q[0] + u[0] * s + v[0] * l, q[1] + u[1] * s + v[1] * l))
            return
        f = self.feed()
        self.cr = (self.cr[0] - v[0] * f, self.cr[1] - v[1] * f)
        self.set_here(self.cr)

    def _span(self) -> tuple:
        if self.p1 is None or self.p2 is None:
            return None
        return abs(self.p2[0] - self.p1[0]) / UNITS, abs(self.p2[1] - self.p1[1]) / UNITS

    def text_size(self, op: str, a: list) -> None:
        if op == 'SI':                                    # en cm
            self.cw, self.ch = (abs(a[0]) * 10.0, abs(a[1]) * 10.0) if len(a) >= 2 else (CELL_W, CELL_H)
        else:                                             # SR : en % de P2 - P1
            span = self._span()
            if span is None:
                self.cw, self.ch = CELL_W, CELL_H
            else:
                w, h = (a[0], a[1]) if len(a) >= 2 else (0.75, 1.5)
                self.cw, self.ch = abs(w) * span[0] / 100.0, abs(h) * span[1] / 100.0

    def direction(self, op: str, a: list) -> None:
        if len(a) < 2 or (a[0] == 0.0 and a[1] == 0.0):
            self.run, self.rise = 1.0, 0.0
        elif op == 'DI':
            self.run, self.rise = a[0], a[1]
        else:                                             # DR : en % de P2 - P1
            span = self._span() or (1.0, 1.0)
            self.run, self.rise = a[0] * span[0], a[1] * span[1]

    def font(self, a: list) -> None:
        """SD : le pas (caractères par pouce) et la hauteur (points)."""
        for k in range(0, len(a) - 1, 2):
            if int(a[k]) == 3 and a[k + 1] > 0.0:
                self.cw = 25.4 / a[k + 1] / 1.5
            elif int(a[k]) == 4 and a[k + 1] > 0.0:
                self.ch = a[k + 1] * 25.4 / 72.0 * 0.7


def _parse(text: str) -> _Pen:
    st = _Pen()
    for op, a in _commands(text):
        if op in ('PU', 'PD'):
            if op == 'PU':
                st.flush()
            st.down = op == 'PD'
            st.go(a)
        elif op == 'PA':
            st.absolute = True
            st.go(a)
        elif op == 'PR':
            st.absolute = False
            st.go(a)
        elif op == 'SP':
            st.flush()
            st.pen = int(a[0]) if a else 0
        elif op == 'IN':
            st.flush()
            st.init()
        elif op == 'DF':
            st.flush()
            st.absolute = True
            st.sc = None
            st.rescale()
            st.text_defaults()
        elif op == 'IP':
            st.set_window(a)
        elif op == 'SC':
            st.set_scale(a)
        elif op == 'RO':
            st.set_rotation(a)
        elif op == 'PM':                                  # polygones : PM1 et PM2 les ferment
            st.flush(close=bool(a) and int(a[0]) in (1, 2))
        elif op in ('PG', 'AF', 'AH', 'FR'):
            st.flush()
            if st.drawn:
                st.sheets += 1
                st.drawn = False
        elif op == 'CI' and a:
            st.flush()
            if a[0] != 0.0:
                st.add(circle((st.x, st.y), abs(a[0])).transformed(st.m))
        elif op in ('AA', 'AR') and len(a) >= 3:
            cx, cy = (a[0], a[1]) if op == 'AA' else (st.x + a[0], st.y + a[1])
            st.arc(cx, cy, a[2])
        elif op in ('AT', 'RT') and len(a) >= 4:
            bx, by = (0.0, 0.0) if op == 'AT' else (st.x, st.y)
            st.arc3(bx + a[0], by + a[1], bx + a[2], by + a[3])
        elif op in ('EA', 'RA', 'ER', 'RR') and len(a) >= 2:
            x1, y1 = (a[0], a[1]) if op in ('EA', 'RA') else (st.x + a[0], st.y + a[1])
            st.rectangle(x1, y1)
        elif op in ('EW', 'WG') and len(a) >= 3:
            st.wedge(a[0], a[1], a[2])
        elif op in ('BZ', 'BR'):
            st.beziers(a, op == 'BR')
        elif op == 'PE':
            st.encoded(a)
        elif op == 'LB':
            st.label(a)
        elif op == 'CP':
            st.carriage(a)
        elif op in ('SI', 'SR'):
            st.text_size(op, a)
        elif op in ('DI', 'DR'):
            st.direction(op, a)
        elif op == 'SL':
            st.slant = a[0] if a else 0.0
        elif op == 'LO':
            st.origin = int(a[0]) if a else 1
        elif op == 'ES':
            st.extra_x = a[0] if a else 0.0
            st.extra_y = a[1] if len(a) > 1 else 0.0
        elif op == 'SD':
            st.font(a)
    st.flush()
    return st


def read_text(text: str) -> tuple[dict, int]:
    """(plume -> contours, nombre de textes)."""
    st = _parse(_unwrap(text) or '')
    return st.by_pen, st.labels


def read(path) -> Document:
    name = pathlib.Path(path).name
    raw = pathlib.Path(path).read_bytes()
    text = None if b'\x00' in raw[:64] else _unwrap(raw.decode('latin-1'))
    if text is None:
        raise ValueError(f'{name} : ce fichier .plt n\'est pas du HPGL (PCL ou format de la machine)')
    st = _parse(text)
    if not st.by_pen and not st.texts:
        raise ValueError(f'{name} : aucun trait HPGL dans ce fichier')
    doc = Document()
    doc.plate = None
    layers = []
    for p in sorted(set(st.by_pen) | {pen for pen, _t in st.texts}):
        tool = max(0, p - 1)
        items = [Shape(path=Path(st.by_pen[p]), tool=tool)] if p in st.by_pen else []
        items += [t for pen, t in st.texts if pen == p]
        layers.append(Layer(name=f'Plume {p}', tool=tool, items=items))
    doc.layers = layers
    if st.texts:
        doc.report.append(f'{len(st.texts)} texte(s) HPGL repris en {LABEL_FONT} : même place et même largeur, mais '
                          'le traceur les dessinait avec sa propre police')
    if st.guessed:
        doc.report.append('Échelle HPGL (SC) sans fenêtre (IP) : la taille réelle dépendait du papier du traceur ; '
                          'ici, une unité du fichier vaut 0,025 mm')
    pages = st.sheets + (1 if st.drawn else 0)
    if pages > 1:
        doc.report.append(f'{pages} pages HPGL superposées : un document n\'en a qu\'une')
    return doc


def _round(v: float) -> int:
    return int(round(v * UNITS))


#: écart toléré (mm) quand on retire les points trop serrés avant de les arrondir : un demi-pas du traceur
THIN = 0.5 / UNITS
#: un tracé plus long est allégé par tronçons (le calcul reste rapide)
THIN_CHUNK = 4000


def _thin(pts: list, tol: float = THIN) -> list:
    """Les points d'un tracé (mm), sans ceux qui ne s'écartent pas de `tol` de la droite entre leurs voisins gardés
    (Douglas-Peucker, sans récursion). Des points plus serrés que le pas du traceur, arrondis un à un, font un
    escalier : le tracé s'allonge et la machine tremble, pour un écart qu'elle ne sait pas rendre."""
    n = len(pts)
    if n < 3:
        return pts
    if n > THIN_CHUNK:                                   # par tronçons qui se suivent : leurs bouts sont gardés
        out = []
        for a in range(0, n - 1, THIN_CHUNK - 1):
            part = _thin(pts[a:a + THIN_CHUNK], tol)
            out.extend(part if not out else part[1:])
        return out
    keep = [False] * n
    keep[0] = keep[-1] = True
    stack = [(0, n - 1)]
    t2 = tol * tol
    while stack:
        a, b = stack.pop()
        if b - a < 2:
            continue
        (ax, ay), (bx, by) = pts[a], pts[b]
        dx, dy = bx - ax, by - ay
        l2 = dx * dx + dy * dy
        worst, at = -1.0, -1
        for k in range(a + 1, b):
            px, py = pts[k][0] - ax, pts[k][1] - ay
            t = (px * dx + py * dy) / l2 if l2 > 1e-18 else 0.0
            if t <= 0.0:                                 # avant le début (ou corde nulle : contour fermé)
                d2 = px * px + py * py
            elif t >= 1.0:
                d2 = (px - dx) ** 2 + (py - dy) ** 2
            else:
                c = px * dy - py * dx
                d2 = c * c / l2
            if d2 > worst:
                worst, at = d2, k
        if worst > t2:
            keep[at] = True
            stack.append((a, at))
            stack.append((at, b))
    return [p for p, k in zip(pts, keep) if k]


def _steps(pts: list, ox: float, oy: float) -> list:
    """Les points en pas du traceur, depuis l'origine (ox, oy), sans doublons consécutifs."""
    out = []
    for x, y in pts:
        q = (_round(x - ox), _round(y - oy))
        if not out or out[-1] != q:
            out.append(q)
    return out


def write_text(doc: Document, *, tolerance: float = FLATTEN) -> tuple[str, int]:
    """(programme HPGL, images laissées de côté). Le coin bas gauche du dessin va en (0, 0) : un traceur n'a pas de négatif."""
    from ..cam.fixture import without_plates
    doc = without_plates(doc)                            # plaque de reprise posée : un repère, jamais tracée
    bb = doc.bbox(visible_only=True)
    ox, oy = (bb[0], bb[1]) if bb else (0.0, 0.0)
    by_tool: dict = {}
    images = 0

    def walk(it):
        nonlocal images
        if not it.visible:
            return
        if isinstance(it, Group):
            for ch in it.children:
                walk(ch)
            return
        if isinstance(it, Image):
            images += 1
            return
        p = getattr(it, 'path', None) or getattr(it, 'outline', None)
        if p:
            by_tool.setdefault(int(it.tool or 0), []).extend(c for c in p.contours if c.segments)
    for L in doc.layers:
        if L.visible:
            for it in L.items:
                walk(it)
    out = ['IN;']
    for tool in sorted(by_tool):
        out.append(f'SP{max(1, tool + 1)};')
        for c in by_tool[tool]:
            pts = [c.segments[0].start]
            for s in c.segments:
                pts.extend(s.flatten(tolerance))
            if c.closed and math.dist(pts[0], pts[-1]) > 1e-9:
                pts.append(pts[0])
            ints = _steps(_thin(pts), ox, oy)            # allégé avant l'arrondi : pas d'escalier au pas du traceur
            if len(ints) < 2:
                ints = _steps(pts, ox, oy)               # plus petit qu'un demi-pas : écrit tel quel, pas perdu
            if len(ints) < 2:
                continue
            out.append(f'PU{ints[0][0]},{ints[0][1]};')
            out.append('PD' + ','.join(f'{x},{y}' for x, y in ints[1:]) + ';')
        out.append('PU;')
    out.append('SP0;')
    return '\n'.join(out) + '\n', images


def write(doc: Document, path) -> None:
    text, images = write_text(doc)
    if images:
        doc.report.append(f'{images} image(s) laissée(s) de côté : le HPGL ne porte que des traits')
    pathlib.Path(path).write_text(text, encoding='ascii')


__all__ = ['read', 'read_text', 'write', 'write_text', 'Line']
