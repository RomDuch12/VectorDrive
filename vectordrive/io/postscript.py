"""EPS, PostScript et Illustrator ancien (AI ≤ 8) : lecture et écriture.

Lecture reprise de TauDrive (`engrave/vecimport.read_postscript`, même
auteur), adaptée pour **garder les Bézier** au lieu de les aplatir :

* en-tête binaire DOS des EPS Windows retiré ;
* lecture après le prologue (`%%EndProlog`, `%%EndSetup`…) : le prologue
  définit des procédures qu'il serait vain d'interpréter ;
* opérateurs de tracé PostScript et abrégés Illustrator (m, l/L, c/C,
  v/V, y/Y, h, f/F, s/S, b/B, n/N…), matrice (concat, cm, scale,
  translate), gsave/grestore ; blocs `{…}` sautés ; détourages écartés ;
* un tracé rempli (f, F, b, B, fill, eofill…) est une surface : ses contours sont
  fermés, comme le fait le remplissage lui-même.

Écriture : EPS 3.0 en points, une couleur de trait par outil.
"""
from __future__ import annotations

import pathlib
import re
import struct

from ..core.document import Document, Group, Layer, Shape
from ..core.geom import Affine, Conic, Contour, Cubic, Line, Path, PathBuilder, close_returning, dist

PT_MM = 25.4 / 72.0

_PS_PATH = {'m': 2, 'mo': 2, 'moveto': 2, 'l': 2, 'L': 2, 'li': 2, 'lineto': 2,
            'c': 6, 'C': 6, 'cv': 6, 'curveto': 6, 'v': 4, 'V': 4, 'y': 4, 'Y': 4,
            'rmoveto': 2, 'rlineto': 2, 'rcurveto': 6}
_PS_END = {'f', 'F', 'ef', 'eof', 's', 'S', 'b', 'B', 'n', 'N', '@', 'fill', 'stroke',
           'eofill', 'closepath_stroke', 'sf', 'ef*'}
#: opérateurs qui peignent une surface : le remplissage ferme alors chaque tracé de lui-même
_PS_FILL = ('f', 'F', 'fill', 'eofill', 'f*', 'b', 'B', 'ef', 'eof', 'ef*')
_PS_BODY = ('%%EndPageSetup', '%%EndSetup', '%%EndProlog')
_PS_TOKEN = re.compile(rb'%[^\r\n]*|\((?:[^()\\]|\\.)*\)|<[^>]*>|[\[\]{}]|[^\s\[\]{}()<>%]+')


class PostScriptError(ValueError):
    pass


def postscript_section(raw: bytes) -> bytes:
    """Partie PostScript d'un EPS (en-tête binaire DOS retiré)."""
    if raw[:4] == b'\xc5\xd0\xd3\xc6':
        start, length = struct.unpack('<II', raw[4:12])
        if 0 < start < len(raw):
            return raw[start:start + length] if length else raw[start:]
    return raw


def _closed_surface(p: Path) -> Path:
    """Les contours d'une surface peinte, fermés (un trait droit seul reste un trait)."""
    out = []
    for c in p.contours:
        segs = list(c.segments)
        if c.closed or not segs or (len(segs) == 1 and isinstance(segs[0], Line)):
            out.append(c)
            continue
        if dist(c.end, c.start) > 1e-9:
            segs.append(Line(c.end, c.start))
        out.append(Contour(segs, True))
    return Path(out)


class _State:
    def __init__(self):
        self.ctm = Affine()
        self.stack: list[Affine] = []
        self.items: list[Shape] = []
        self.b: PathBuilder | None = None
        self.images = 0
        self.clip = False
        self.paint = [None, None]                        # couleurs du trait et du fond

    def builder(self) -> PathBuilder:
        if self.b is None:
            self.b = PathBuilder(Affine.scaling(PT_MM) @ self.ctm)
        return self.b

    def end(self, keep: bool = True, op: str = ''):
        if self.b is not None:
            p = self.b.path()
            if p and keep and not self.clip:
                fill_only = op in ('f', 'F', 'fill', 'eofill', 'f*')
                if op in _PS_FILL:
                    p = _closed_surface(p)
                else:
                    p = close_returning(p)               # tiré jusqu'à son départ, sans closepath : fermé aussi
                sh = Shape(path=p)
                sh.extra['_color'] = (self.paint[1] if fill_only else self.paint[0]) or self.paint[0] or self.paint[1]
                self.items.append(sh)
        self.b = None
        self.clip = False


def read_bytes(raw: bytes) -> tuple[list[Shape], list[str]]:
    ps = postscript_section(raw)
    if not ps.lstrip()[:2] == b'%!':
        raise PostScriptError('ce n\'est pas un fichier PostScript')
    start = 0
    for mark in _PS_BODY:
        i = ps.find(mark.encode('latin-1'))
        if i >= 0:
            start = max(start, i + len(mark))
    body = ps[start:]
    st = _State()
    stack: list[float] = []
    array: list[float] | None = None
    depth = 0
    for m in _PS_TOKEN.finditer(body):
        tok = m.group()
        if tok[:1] == b'%':
            continue
        if tok == b'{':
            depth += 1
            continue
        if tok == b'}':
            depth = max(0, depth - 1)
            continue
        if depth:
            continue
        if tok == b'[':
            array = []
            continue
        if tok == b']':
            stack = list(array or [])
            array = None
            continue
        if tok[:1] in b'(<':
            continue
        text = tok.decode('latin-1')
        try:
            num = float(text)
        except ValueError:
            num = None
        if num is not None:
            (array if array is not None else stack).append(num)
            if len(stack) > 64:
                del stack[:-64]
            continue
        _operator(st, text, stack)
    st.end()
    report = []
    if st.images:
        report.append(f'{st.images} image(s) matricielle(s) ignorée(s)')
    return st.items, report


def _operator(st: _State, op: str, stack: list[float]) -> None:
    need = _PS_PATH.get(op)
    if need is not None:
        if len(stack) >= need:
            a = stack[-need:]
            b = st.builder()
            pos = b.position
            if op in ('m', 'mo', 'moveto'):
                b.move_to((a[0], a[1]))
            elif op == 'rmoveto':
                b.move_to(((pos or (0, 0))[0] + a[0], (pos or (0, 0))[1] + a[1]))
            elif op in ('l', 'L', 'li', 'lineto'):
                b.line_to((a[0], a[1]))
            elif op == 'rlineto' and pos:
                b.line_to((pos[0] + a[0], pos[1] + a[1]))
            elif op in ('c', 'C', 'cv', 'curveto'):
                b.cubic_to((a[0], a[1]), (a[2], a[3]), (a[4], a[5]))
            elif op == 'rcurveto' and pos:
                x, y = pos
                b.cubic_to((x + a[0], y + a[1]), (x + a[2], y + a[3]), (x + a[4], y + a[5]))
            elif op in ('v', 'V') and pos:
                b.cubic_to(pos, (a[0], a[1]), (a[2], a[3]))
            elif op in ('y', 'Y'):
                b.cubic_to((a[0], a[1]), (a[2], a[3]), (a[2], a[3]))
        stack.clear()
        return
    if op in ('image', 'colorimage', 'imagemask'):
        st.images += 1
    elif op in _PS_END:
        if op in ('s', 'b', 'f', 'closepath_stroke') and st.b is not None:
            st.b.close() if op in ('s', 'b', 'closepath_stroke') else None
        st.end(op=op)
    elif op in ('gsave', 'q', 'save'):
        st.stack.append((st.ctm, list(st.paint)))
    elif op in ('grestore', 'Q', 'restore'):
        if st.stack:
            st.ctm, st.paint[:] = st.stack.pop()
    elif op in ('setrgbcolor', 'setgray', 'setcmykcolor'):
        from .colors import from_operands
        n = {'setrgbcolor': 3, 'setgray': 1, 'setcmykcolor': 4}[op]
        if len(stack) >= n:
            c = from_operands(stack[-n:])
            st.paint[:] = [c, c]
    elif op in ('K', 'k', 'G', 'g', 'XA', 'Xa'):         # Illustrator : trait (majuscule) ou fond
        from .colors import from_operands
        n = {'K': 4, 'k': 4, 'G': 1, 'g': 1, 'XA': 3, 'Xa': 3}[op]
        if len(stack) >= n:
            st.paint[0 if op in ('K', 'G', 'XA') else 1] = from_operands(stack[-n:])
    elif op in ('ct', 'concat', 'cm'):
        if len(stack) >= 6:
            st.ctm = st.ctm @ Affine(*stack[-6:])
    elif op == 'setmatrix':
        if len(stack) >= 6:
            st.ctm = Affine(*stack[-6:])
    elif op == 'scale' and len(stack) >= 2:
        st.ctm = st.ctm @ Affine.scaling(stack[-2], stack[-1])
    elif op == 'translate' and len(stack) >= 2:
        st.ctm = st.ctm @ Affine.translation(stack[-2], stack[-1])
    elif op == 'rotate' and stack:
        st.ctm = st.ctm @ Affine.rotation(stack[-1])
    elif op in ('np', 'newpath'):
        st.end(keep=False)
    elif op in ('cp', 'closepath', 'h', 'H'):
        if st.b is not None:
            st.b.close()
        return
    elif op in ('clp', 'eclp', 'clip', 'eoclip', 'W', 'W*'):
        st.clip = True                      # détourage : jamais gravé
    stack.clear()


def read(path) -> Document:
    raw = pathlib.Path(path).read_bytes()
    items, report = read_bytes(raw)
    doc = Document(layers=[Layer(name=pathlib.Path(path).stem, items=items)],
                   source_path=str(path), source_format='eps')
    doc.report = report
    from .colors import ToolColors
    colors = ToolColors(doc)                             # une couleur = un outil (F10 › Fichiers)
    for it in items:
        it.tool = colors.tool(it.extra.pop('_color', None))
    from .colors import black_first
    black_first(doc, colors)
    return doc


# --- écriture --------------------------------------------------------------------

def _f(v: float) -> str:
    s = f'{v:.4f}'.rstrip('0').rstrip('.')
    return '0' if s in ('-0', '') else s


def write(doc: Document, path, *, line_width_mm: float = 0.1) -> None:
    bb = doc.bbox(include_plate=True) or (0, 0, 100, 100)
    m = Affine.scaling(1 / PT_MM) @ Affine.translation(-bb[0], -bb[1])
    W, H = (bb[2] - bb[0]) / PT_MM, (bb[3] - bb[1]) / PT_MM
    out = ['%!PS-Adobe-3.0 EPSF-3.0', f'%%BoundingBox: 0 0 {int(W + 0.999)} {int(H + 0.999)}',
           f'%%HiResBoundingBox: 0 0 {_f(W)} {_f(H)}', '%%Creator: VectorDrive',
           f'%%Title: ({pathlib.Path(path).stem})', '%%EndComments', '%%EndProlog', '%%Page: 1 1',
           f'{_f(line_width_mm / PT_MM)} setlinewidth 1 setlinejoin 1 setlinecap']
    P = lambda q: ' '.join(_f(v) for v in m.apply(q))

    def emit(it):
        if not it.visible:
            return
        if isinstance(it, Group):
            for ch in it.children:
                emit(ch)
            return
        p = getattr(it, 'path', None) or getattr(it, 'outline', None)
        if not p:
            return
        col = doc.item_color(it).lstrip('#')
        r, g, b = (int(col[i:i + 2], 16) / 255 for i in (0, 2, 4))
        out.append(f'{_f(r)} {_f(g)} {_f(b)} setrgbcolor newpath')
        for c in p.contours:
            if not c.segments:
                continue
            out.append(f'{P(c.start)} moveto')
            for s in c.segments:
                if isinstance(s, Line):
                    out.append(f'{P(s.p1)} lineto')
                elif isinstance(s, Cubic):
                    out.append(f'{P(s.p1)} {P(s.p2)} {P(s.p3)} curveto')
                elif isinstance(s, Conic):
                    for cb in s.to_cubics():
                        out.append(f'{P(cb.p1)} {P(cb.p2)} {P(cb.p3)} curveto')
            if c.closed:
                out.append('closepath')
        out.append('eofill' if getattr(it, 'filled', False) else 'stroke')

    for L in doc.layers:
        if L.visible:
            for it in L.items:
                emit(it)
    out += ['showpage', '%%EOF', '']
    pathlib.Path(path).write_text('\n'.join(out), encoding='latin-1', errors='replace')
