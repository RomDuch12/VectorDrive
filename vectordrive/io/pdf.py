"""PDF et Illustrator ≥ 9 (qui est un PDF) : lecture et écriture.

Lecture : pypdf (BSD) décode la structure et les flux ; on interprète
nous-mêmes les opérateurs de tracé (m l c v y h re), la matrice courante
(cm, q/Q) et les XObjects de formulaire (Do). Le dessin est lu tel qu'il
s'affiche, comme le montre Inkscape : une page = un calque, et les calques du
fichier (contenu optionnel, ce que deviennent les calques d'Illustrator)
deviennent des calques, masqués s'ils le sont dans le fichier ; le détourage
(W n) coupe ce qu'il contient ; un aplat blanc est retiré de ce qu'il recouvre
et rangé dans un calque masqué, sans quoi il deviendrait un contour à graver.

Écriture : PDF 1.4 minimal écrit à la main, une page aux dimensions du
dessin (ou de la plaque), un trait par outil, les images à leur pleine
résolution sans perte. Le PDF n'a pas de coniques : les arcs passent en
cubiques à 0,1 µm près.
"""
from __future__ import annotations

import pathlib

from ..core.document import Document, Group, Image, Layer, Shape, Text
from ..core.geom import Affine, Conic, Contour, Cubic, Line, Path, PathBuilder, close_returning, dist

PT_MM = 25.4 / 72


class PdfError(ValueError):
    pass


def sniff(path) -> str:
    with pathlib.Path(path).open('rb') as f:
        head = f.read(1024)
    if b'%PDF' in head:
        return 'pdf'
    if head.startswith(b'%!PS') or head[:4] == b'\xc5\xd0\xd3\xc6':
        return 'postscript'
    return 'inconnu'


def read(path) -> Document:
    kind = sniff(path)
    if kind == 'postscript':
        from . import postscript
        return postscript.read(path)
    if kind != 'pdf':
        raise PdfError('ce fichier n\'est ni un PDF ni un Illustrator compatible PDF')
    try:
        from pypdf import PdfReader
    except ImportError as ex:
        raise PdfError('pypdf manquant (pip install pypdf)') from ex
    reader = PdfReader(str(path), strict=False)
    doc = Document(layers=[], source_path=str(path), source_format='pdf')
    from .colors import ToolColors
    colors = ToolColors(doc)                             # une couleur = un outil (F10 › Fichiers)
    texts, font_notes = 0, set()
    ocgs = _optional_groups(reader, doc.report)
    by_name: dict[str, Layer] = {}
    for n, page in enumerate(reader.pages, 1):
        layer = Layer(name=f'Page {n}')
        box = page.mediabox
        base = Affine.scaling(PT_MM) @ Affine.translation(-float(box.left), -float(box.bottom))
        contents = page.get_contents()
        if contents is None:
            doc.layers.append(layer)
            continue
        _run(_operations(contents, reader), base, page.get('/Resources'), reader, layer.items, doc.report, 0,
             colors, ocgs)
        if TEXT_REMARK in doc.report:
            n = _texts(page, base, layer.items, font_notes)
            texts += n
            if n:
                doc.report.remove(TEXT_REMARK)
        _place_page(doc, layer, ocgs, by_name)
    if texts:
        doc.report.append(f'{texts} texte(s) PDF repris en textes vivants')
        doc.report.extend(sorted(font_notes))
    if not doc.layers:
        doc.layers.append(Layer())
    from .colors import black_first
    black_first(doc, colors)
    return doc


# --- textes ------------------------------------------------------------------

TEXT_REMARK = 'texte PDF non vectorisé (polices) : à convertir en contours'
#: polices de base du PDF → polices du poste
_BASE14 = {'helvetica': 'Arial', 'times': 'Times New Roman', 'courier': 'Courier New', 'symbol': 'Arial',
           'zapfdingbats': 'Arial', 'arialmt': 'Arial', 'timesnewromanpsmt': 'Times New Roman',
           'timesnewromanps': 'Times New Roman', 'couriernewpsmt': 'Courier New', 'couriernewps': 'Courier New'}


def _pdf_font(base_font: str | None, notes: set) -> tuple[str, float, bool]:
    """Nom /BaseFont (« /ABCDEF+Arial-BoldMT ») → (police du poste, hauteur
    des capitales / corps, italique) ; Arial si elle manque (noté)."""
    import re
    from ..core import fonts
    name = str(base_font or '').lstrip('/')
    name = re.sub(r'^[A-Z]{6}\+', '', name)                       # préfixe de sous-ensemble
    fam, _, style = name.partition('-')
    if ',' in fam:
        fam, _, style = fam.partition(',')
    low = (fam + style).lower()
    bold = 'bold' in low or 'black' in low or 'heavy' in low
    italic = 'italic' in low or 'oblique' in low
    fam = re.sub(r'(PSMT|MT|PS)$', '', fam)
    family = _BASE14.get(fam.lower()) or re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', fam).strip()
    chosen = None
    for cand in ([f'{family} Bold'] if bold else []) + [family]:
        if family and fonts.is_available(cand):
            chosen = cand
            break
    if chosen is None:
        if family:
            notes.add(f'police PDF « {name} » absente : Arial')
        chosen = 'Arial Bold' if bold and fonts.is_available('Arial Bold') else 'Arial'
    f = fonts.find_font(chosen)
    ratio = 0.716
    if f:
        m = fonts.metrics(*f)
        ratio = m['cap'] / m['upem']
        try:
            chosen = fonts.load(*f)['name'].getDebugName(4) or chosen
        except Exception:
            pass
    return chosen, ratio, italic


def _texts(page, base: Affine, out: list, notes: set) -> int:
    """Textes de la page (pypdf : chaîne décodée, matrices, police, corps)
    → textes vivants, ligne de base à l'origine du texte."""
    import math
    runs: list = []

    def visitor(text, cm, tm, font, size):
        if text and text.strip():
            runs.append((text, list(cm), list(tm), font, size))
    try:
        page.extract_text(visitor_text=visitor)
    except Exception:                                  # pypdf n'a pas su lire les polices : remarque gardée
        return 0
    n = 0
    for text, cm, tm, font, size in runs:
        try:
            M = base @ Affine(*(float(v) for v in cm)) @ Affine(*(float(v) for v in tm))
            p0 = M.apply((0.0, 0.0))
            p1 = M.apply((1.0, 0.0))
            s = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
            fam, ratio, italic = _pdf_font(font.get('/BaseFont') if font else None, notes)
            cap = float(size or 0) * s * ratio
            if cap <= 0:
                continue
            t = Text(text=text.rstrip('\n').strip('\r'), font=fam, size=cap, align='left')
            if italic:
                t.extra['italic'] = 12.0
            t.matrix = Affine.translation(p0[0], p0[1]) @ Affine.rotation(
                math.degrees(math.atan2(p1[1] - p0[1], p1[0] - p0[0])))
            out.append(t)
            n += 1
        except (TypeError, ValueError, AttributeError):
            continue
    return n


def _num(v) -> float:
    return float(v)


import re as _re

#: jetons d'un flux de contenu sans chaînes, tableaux ni dictionnaires : nombres, noms, opérateurs, commentaires
_TOKEN = _re.compile(rb'%[^\r\n]*|/[^\s/\[\]<>(){}%]*|[^\s/\[\]<>(){}%]+')
#: un flux qui en contient est laissé à pypdf (chaînes, tableaux, dictionnaires, images en ligne)
_COMPLEX = _re.compile(rb'[\[\]<>()]|(?<![A-Za-z])BI(?![A-Za-z])')
_NUMBER = _re.compile(rb'[+-]?(?:\d+\.?\d*|\.\d+)$')


def stream_bytes(obj) -> bytes | None:
    """Contenu décodé d'un flux de page (ou d'une liste de flux, mis bout à
    bout) ; None si pypdf ne sait pas le décoder ici."""
    try:
        if hasattr(obj, 'get_data'):
            return obj.get_data()
        parts = []
        for item in obj:
            item = item.get_object()
            parts.append(item.get_data())
        return b'\n'.join(parts)
    except Exception:                                    # filtre inconnu, flux abîmé : pypdf s'en charge
        return None


def fast_operations(data: bytes) -> list | None:
    """[(opérandes, opérateur)] d'un flux de tracés simple, comme
    pypdf.ContentStream.operations mais 20 fois plus vite (un BAT de 10 000
    gravures : 2,5 millions d'objets pypdf) ; None : flux à laisser à pypdf
    (chaînes de texte, tableaux, dictionnaires, images en ligne)."""
    if data is None or _COMPLEX.search(data):
        return None
    ops: list = []
    operands: list = []
    for tok in _TOKEN.findall(data):
        c = tok[:1]
        if c == b'%':
            continue
        if c == b'/':
            operands.append(tok.decode('latin-1'))
        elif _NUMBER.match(tok):
            operands.append(float(tok))
        elif tok in (b'true', b'false', b'null'):
            return None                                  # opérande inattendu dans un flux de tracés
        else:
            ops.append((operands, tok.decode('latin-1')))
            operands = []
    return ops


def _operations(contents, reader) -> list:
    """Opérations d'un flux : découpage rapide si possible, sinon pypdf."""
    ops = fast_operations(stream_bytes(contents))
    if ops is not None:
        return ops
    from pypdf.generic import ContentStream
    return ContentStream(contents, reader).operations


def _optional_groups(reader, report: list) -> dict:
    """Calques du fichier (contenu optionnel, configuration par défaut) : {n° d'objet : (nom, visible)}."""
    try:
        props = reader.trailer['/Root'].get_object().get('/OCProperties')
        if props is None:
            return {}
        props = props.get_object()
        conf = props['/D'].get_object()

        def ids(key):
            out = set()
            for ref in conf.get(key) or []:
                if hasattr(ref, 'idnum'):
                    out.add(ref.idnum)
            return out
        off, on = ids('/OFF'), ids('/ON')
        base_off = conf.get('/BaseState') == '/OFF'
        groups = {}
        for ref in props.get('/OCGs') or []:
            if not hasattr(ref, 'idnum'):
                continue
            name = str(ref.get_object().get('/Name') or f'Calque {ref.idnum}')
            groups[ref.idnum] = (name, ref.idnum in on if base_off else ref.idnum not in off)
        return groups
    except (KeyError, AttributeError, TypeError, ValueError) as ex:
        report.append(f'calques du fichier non lus : {ex}')
        return {}


def _oc_group(ref, ocgs: dict):
    """(nom, visible) du calque d'un objet de contenu optionnel (groupe, ou liste de groupes) ; None sinon."""
    if ref is None or not ocgs:
        return None
    if hasattr(ref, 'idnum') and ref.idnum in ocgs:
        return ocgs[ref.idnum]
    obj = ref.get_object() if hasattr(ref, 'get_object') else ref
    if not hasattr(obj, 'raw_get') or '/OCGs' not in obj:
        return None
    members = obj.raw_get('/OCGs')                       # liste de groupes : sa visibilité suit le premier
    if hasattr(members, 'idnum') and members.idnum in ocgs:
        return ocgs[members.idnum]
    members = members.get_object() if hasattr(members, 'get_object') else members
    if hasattr(members, 'raw_get'):
        return None
    for m in members or []:
        if hasattr(m, 'idnum') and m.idnum in ocgs:
            return ocgs[m.idnum]
    return None


def _marked_group(operands, resources, ocgs: dict):
    """Calque d'un « /OC /MCn BDC » : par les propriétés des ressources."""
    if not ocgs or len(operands) < 2 or operands[0] != '/OC' or resources is None:
        return None
    res = resources.get_object() if hasattr(resources, 'get_object') else resources
    props = res.get('/Properties')
    if props is None:
        return None
    props = props.get_object()
    return _oc_group(props.raw_get(operands[1]) if operands[1] in props else None, ocgs)


_WHITE = '#ffffff'
#: détourages calculés au plus par fichier (au-delà : dessin gardé entier, et dit)
CLIP_MAX = 5000
EPS_MM = 1e-6


def _axis_rect(p: Path) -> bool:
    """Le chemin est un seul rectangle aux côtés parallèles aux axes."""
    if len(p.contours) != 1:
        return False
    segs = p.contours[0].segments
    if not 3 <= len(segs) <= 5 or not all(isinstance(s, Line) for s in segs):
        return False
    return all(abs(s.p0[0] - s.p1[0]) < EPS_MM or abs(s.p0[1] - s.p1[1]) < EPS_MM for s in segs)


def _clipped(shape: Shape, clip: Path, budget: list) -> Shape | None:
    """La forme coupée par le détourage ; None si elle est toute dehors. Un tracé ouvert qui déborde est
    gardé entier (seules les surfaces se coupent)."""
    from ..core import pathops
    sb, cb = shape.path.bbox(), clip.bbox()
    if not sb or not cb:
        return shape
    if sb[2] < cb[0] - EPS_MM or sb[0] > cb[2] + EPS_MM or sb[3] < cb[1] - EPS_MM or sb[1] > cb[3] + EPS_MM:
        return None
    inside = sb[0] >= cb[0] - EPS_MM and sb[1] >= cb[1] - EPS_MM and sb[2] <= cb[2] + EPS_MM and sb[3] <= cb[3] + EPS_MM
    if inside and _axis_rect(clip):
        return shape
    if not all(c.closed for c in shape.path.contours):
        return shape
    if budget[0] <= 0:
        budget[1] = True
        return shape
    budget[0] -= 1
    try:
        cut = pathops.boolean(shape.path, clip, 'intersect')
        if not cut or not cut.contours:
            return None
        before = pathops.area(shape.path)
        if before > 0 and pathops.area(cut) >= before * (1 - 1e-6):
            return shape                                 # rien de coupé : les courbes d'origine
    except Exception:                                    # noqa: BLE001 — moteur en défaut : forme entière
        return shape
    shape.path = cut
    return shape


def _closed_surface(p: Path) -> Path:
    """Contours d'une surface peinte, fermés : le PDF les ferme implicitement au remplissage."""
    if all(c.closed for c in p.contours):
        return p
    out = []
    for c in p.contours:
        if c.closed or not c.segments:
            out.append(c)
            continue
        segs = list(c.segments)
        if dist(c.end, c.start) > 1e-9:
            segs.append(Line(c.end, c.start))
        out.append(Contour(segs, True))
    return Path(out)


def _nonzero(p: Path, budget: list) -> Path:
    """Surface peinte en règle non nulle (celle du PDF) : VectorDrive remplit en pair-impair. Un tracé qui se
    recouvre (coin d'un trait vectorisé…) est réuni ; sinon il garde ses courbes d'origine."""
    from ..core import pathops
    if budget[0] <= 0 or not p.contours or not all(c.closed for c in p.contours):
        return p
    budget[0] -= 1
    try:
        nz = pathops.normalize(p, evenodd=False)
        a_nz = pathops.area(nz)
        if a_nz > 0 and abs(a_nz - pathops.area(pathops.normalize(p, evenodd=True))) > a_nz * 1e-5:
            return nz
    except Exception:                                    # noqa: BLE001 — moteur en défaut : tracé d'origine
        pass
    return p


def _run(ops, ctm: Affine, resources, reader, out: list, report: list, depth: int, colors=None, ocgs=None,
         group=None, budget=None) -> None:
    from .colors import from_operands
    stack: list = []
    b = PathBuilder(ctm)
    clip_pending = False
    clip = None                                          # détourage courant (en mm)
    marks: list = []                                     # contenu marqué : calque de chaque niveau
    budget = [CLIP_MAX, False] if budget is None else budget
    text_seen = False
    paint = [None, None]                                 # couleurs du trait et du fond (état graphique)

    def current_group():
        return next((m for m in reversed(marks) if m), group)

    def emit(fill: bool, stroke: bool = True, nonzero: bool = False):
        nonlocal b, clip
        p = b.path()
        if p:
            if fill:
                p = _closed_surface(p)                   # une surface peinte se ferme d'elle-même
            else:
                p = close_returning(p)                   # tiré jusqu'à son départ, sans « h » : fermé aussi
            if fill and nonzero:
                p = _nonzero(p, budget)
            white = fill and (paint[1] or '').lower() == _WHITE
            color = paint[0] if stroke and paint[0] else paint[1] if fill else paint[0]
            mask = white and not stroke                  # aplat blanc seul : pas d'encre, pas de contour à graver
            shape = Shape(path=p, filled=fill and not white,
                          tool=colors.tool(color) if colors is not None and not mask else 0)
            if white:
                shape.extra['pdf_blanc'] = 'aplat' if mask else 'contour'
            g = current_group()
            if g:
                shape.extra['pdf_calque'] = g
            if clip is not None:
                shape = _clipped(shape, clip, budget)
            if shape is not None:
                out.append(shape)
            if clip_pending:                             # « W f » : tracé peint, puis détourage
                clip = _intersect_clip(clip, p)
        b = PathBuilder(ctm)

    for operands, op in ops:
        o = op.decode('latin-1') if isinstance(op, bytes) else op
        try:
            if o == 'q':
                stack.append((ctm, list(paint), clip))
            elif o == 'Q':
                if stack:
                    ctm, paint[:], clip = stack.pop()
                b.matrix = ctm
            elif o == 'BMC':
                marks.append(None)
            elif o == 'BDC':
                marks.append(_marked_group(operands, resources, ocgs))
            elif o == 'EMC':
                if marks:
                    marks.pop()
            elif o in ('RG', 'G', 'K', 'SC', 'SCN'):
                c = from_operands([v for v in operands if not isinstance(v, str) or v[:1] != '/'])
                paint[0] = c or paint[0]
            elif o in ('rg', 'g', 'k', 'sc', 'scn'):
                c = from_operands([v for v in operands if not isinstance(v, str) or v[:1] != '/'])
                paint[1] = c or paint[1]
            elif o == 'cm':
                ctm = ctm @ Affine(*(_num(v) for v in operands))
                b.matrix = ctm
            elif o == 'm':
                b.move_to((_num(operands[0]), _num(operands[1])))
            elif o == 'l':
                b.line_to((_num(operands[0]), _num(operands[1])))
            elif o == 'c':
                v = [_num(x) for x in operands]
                b.cubic_to((v[0], v[1]), (v[2], v[3]), (v[4], v[5]))
            elif o == 'v':
                v = [_num(x) for x in operands]
                cur = b.position or (v[0], v[1])
                b.cubic_to(cur, (v[0], v[1]), (v[2], v[3]))
            elif o == 'y':
                v = [_num(x) for x in operands]
                b.cubic_to((v[0], v[1]), (v[2], v[3]), (v[2], v[3]))
            elif o == 'h':
                b.close()
            elif o == 're':
                x, y, w, h = (_num(v) for v in operands)
                b.move_to((x, y))
                b.line_to((x + w, y))
                b.line_to((x + w, y + h))
                b.line_to((x, y + h))
                b.close()
            elif o in ('S', 's'):
                if o == 's':
                    b.close()
                emit(False)
                clip_pending = False
            elif o in ('f', 'F', 'f*', 'B', 'B*', 'b', 'b*'):
                if o in ('b', 'b*'):
                    b.close()
                emit(True, stroke=o in ('B', 'B*', 'b', 'b*'), nonzero=o in ('f', 'F', 'B', 'b'))
                clip_pending = False
            elif o in ('W', 'W*'):
                clip_pending = True
            elif o == 'n':
                if clip_pending and b.path():
                    clip = _intersect_clip(clip, b.path())
                b = PathBuilder(ctm)
                clip_pending = False
            elif o in ('Tj', 'TJ', "'", '"'):            # du texte montré (un bloc BT … ET vide n'en est pas)
                g = current_group()
                if g is None or g[1]:                    # le texte d'un calque masqué reste masqué
                    text_seen = True
            elif o == 'Do' and resources is not None and depth < 12:
                name = operands[0]
                xobjs = resources.get_object().get('/XObject') if hasattr(resources, 'get_object') else resources.get('/XObject')
                if xobjs is None:
                    continue
                xo = xobjs.get_object().get(name)
                if xo is None:
                    continue
                xo = xo.get_object()
                if xo.get('/Subtype') != '/Form':
                    continue
                m = xo.get('/Matrix')
                fm = Affine(*(float(v) for v in m)) if m else Affine()
                own = _oc_group(xo.raw_get('/OC'), ocgs) if '/OC' in xo else None
                _run(_operations(xo, reader), ctm @ fm, xo.get('/Resources') or resources, reader, out,
                     report, depth + 1, colors, ocgs, own or current_group(), budget)
        except (IndexError, ValueError, TypeError) as ex:
            report.append(f'opérateur {o} ignoré : {ex}')
    if text_seen and TEXT_REMARK not in report:
        report.append(TEXT_REMARK)
    if depth == 0 and budget[1]:
        report.append(f'détourage appliqué aux {CLIP_MAX} premières formes seulement')


def _intersect_clip(clip: Path | None, new: Path) -> Path:
    """Nouveau détourage : le tracé, dans le détourage courant."""
    if clip is None:
        return new
    from ..core import pathops
    try:
        return pathops.boolean(clip, new, 'intersect')
    except Exception:                                    # noqa: BLE001 — moteur en défaut : le dernier tracé
        return new


def _knock_out(items: list, report: list) -> list:
    """L'encre du calque comme elle s'affiche : un aplat blanc (avec ou sans contour) est retiré des surfaces
    peintes avant lui ; rend les aplats blancs sans contour (ni encre ni contour à graver)."""
    from ..core import pathops
    masks, painted, cut = [], [], 0
    for it in list(items):
        kind = it.extra.get('pdf_blanc')
        if kind and it.path.contours and all(c.closed for c in it.path.contours):
            mb = it.path.bbox()
            for prev in list(painted):
                pb = prev.path.bbox()
                if not (pb and mb) or pb[2] <= mb[0] or pb[0] >= mb[2] or pb[3] <= mb[1] or pb[1] >= mb[3]:
                    continue
                try:
                    left = pathops.boolean(prev.path, it.path, 'difference')
                    before = pathops.area(prev.path)
                except Exception:                        # noqa: BLE001 — moteur en défaut : forme gardée
                    continue
                if not left or not left.contours:
                    items.remove(prev)
                    painted.remove(prev)
                    cut += 1
                elif pathops.area(left) < before * (1 - 1e-6):
                    prev.path = left
                    cut += 1
        if kind == 'aplat':
            items.remove(it)
            masks.append(it)
        elif getattr(it, 'filled', False):               # (les textes n'ont pas de surface à recouper)
            painted.append(it)
        it.extra.pop('pdf_blanc', None)
    if cut:
        report.append(f'{cut} forme(s) recoupée(s) par les aplats blancs posés dessus')
    return masks


def _place_page(doc: Document, page: Layer, ocgs: dict, by_name: dict) -> None:
    """Formes d'une page rangées dans leurs calques, dans l'ordre du fichier ; une page sans calques reste
    un calque. Les aplats blancs vont dans un calque masqué à part (« … (blanc) »)."""
    groups: dict = {}
    for it in page.items:
        g = it.extra.pop('pdf_calque', None) if isinstance(it, Shape) else None
        groups.setdefault(g, []).append(it)
    if not groups:
        groups[None] = []

    def layer(name, visible, *, known):
        L = by_name.get(name) if known else None
        if L is None:
            L = Layer(name=name, visible=visible)
            if known:
                by_name[name] = L
            doc.layers.append(L)
        return L
    for g, items in groups.items():
        L = layer(g[0], g[1], known=True) if g else page
        if not g:
            doc.layers.append(page)
            page.items = []
        masks = _knock_out(items, doc.report)
        L.items.extend(items)
        if masks:
            layer(f'{L.name} (blanc)', False, known=True).items.extend(masks)


# --- écriture ----------------------------------------------------------------

def _hex_rgb(c: str) -> tuple[float, float, float]:
    c = c.lstrip('#')
    if len(c) != 6:
        return (0.0, 0.0, 0.0)
    return tuple(int(c[i:i + 2], 16) / 255 for i in (0, 2, 4))


def _f(v: float) -> str:
    s = f'{v:.4f}'.rstrip('0').rstrip('.')
    return '0' if s in ('-0', '') else s


def path_ops(p: Path, m: Affine) -> list[str]:
    ops = []
    a, b, c_, d, e, f = m.a, m.b, m.c, m.d, m.e, m.f

    def P(q):                                            # m.apply(q) formaté, sans appels intermédiaires
        x, y = q
        return _f(a * x + c_ * y + e) + ' ' + _f(b * x + d * y + f)
    for c in p.contours:
        if not c.segments:
            continue
        ops.append(f'{P(c.start)} m')
        for s in c.segments:
            if isinstance(s, Line):
                ops.append(f'{P(s.p1)} l')
            elif isinstance(s, Cubic):
                ops.append(f'{P(s.p1)} {P(s.p2)} {P(s.p3)} c')
            elif isinstance(s, Conic):
                for cb in s.to_cubics():
                    ops.append(f'{P(cb.p1)} {P(cb.p2)} {P(cb.p3)} c')
        if c.closed:
            ops.append('h')
    return ops


def write(doc: Document, path, *, margin_mm: float = 5.0, line_width_mm: float = 0.1) -> None:
    bb = doc.bbox(include_plate=True) or (0, 0, 100, 100)
    x0, y0, x1, y1 = bb
    x0 -= margin_mm
    y0 -= margin_mm
    x1 += margin_mm
    y1 += margin_mm
    m = Affine.scaling(1 / PT_MM) @ Affine.translation(-x0, -y0)
    W, H = (x1 - x0) / PT_MM, (y1 - y0) / PT_MM
    ops = [f'{_f(line_width_mm / PT_MM)} w', '1 J 1 j']
    if doc.plate and doc.plate.visible:
        from ..core.geom import rect
        pl = doc.plate
        ops.append('0.6 0.6 0.6 RG')
        ops += path_ops(Path([rect(pl.x, pl.y, pl.width, pl.height, pl.corner_radius)]), m)
        ops.append('S')

    images = []

    def emit(it):
        if not it.visible:
            return
        if isinstance(it, Group):
            for ch in it.children:
                emit(ch)
            return
        if isinstance(it, Image):
            from .proof import PDF_UNIT, image_streams
            st = image_streams(it)
            if st is not None:
                t = m @ it.matrix @ PDF_UNIT
                ops.append(f'q {_f(t.a)} {_f(t.b)} {_f(t.c)} {_f(t.d)} {_f(t.e)} {_f(t.f)} cm /Im{len(images)} Do Q')
                images.append(st)
            return
        p = getattr(it, 'path', None) or getattr(it, 'outline', None)
        if not p:
            return
        r, g, b = _hex_rgb(doc.item_color(it))
        ops.append(f'{_f(r)} {_f(g)} {_f(b)} RG')
        if getattr(it, 'filled', False):
            ops.append(f'{_f(r)} {_f(g)} {_f(b)} rg')
        ops.extend(path_ops(p, m))
        ops.append('f*' if getattr(it, 'filled', False) else 'S')

    for L in doc.layers:
        if L.visible:
            for it in L.items:
                emit(it)
    from .proof import pdf_bytes
    pathlib.Path(path).write_bytes(pdf_bytes(ops, W, H, images, pathlib.Path(path).stem))
