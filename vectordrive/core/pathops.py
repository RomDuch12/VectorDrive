"""Opérations sur les tracés : booléens, offset, contour de trait,
suppression des auto-intersections.

Moteur : `vdpathops`, extension Rust construite sur `vectorcraft-pathops`
(ArtCraft, MIT OR Apache-2.0) — booléens robustes **sur les courbes**, sans
aplatissement. Repli : shapely (GEOS), qui travaille sur des polygones
aplatis à 0,002 mm.

Les arcs exacts (coniques w < 1) passent en cubiques à 0,1 µm près : le
moteur ne connaît pas les coniques rationnelles.
"""
from __future__ import annotations

import os
import threading

from .geom import Conic, Contour, Cubic, Line, Path, dist

try:
    from .. import vdpathops as _native        # type: ignore[attr-defined]
except ImportError:                              # pragma: no cover
    _native = None

FLATTEN = 0.002

#: Délai (s) laissé au moteur natif ; au-delà, l'appel est abandonné et
#: shapely prend le relais (le moteur boucle sur de rares tracés
#: pathologiques ; il calcule sans le verrou de Python, le fil abandonné
#: n'empêche donc rien d'avancer).
NATIVE_TIMEOUT = float(os.environ.get('VECTORDRIVE_NATIF_DELAI', '20'))
#: Délai supplémentaire par opération de tracé (s) : 130 000 segments → +130 s.
NATIVE_PER_OP = 0.001
#: Appels abandonnés depuis le lancement (diagnostic).
stuck_calls: list[str] = []


class _NativeFailed(Exception):
    pass


class _Worker:
    """Fil de travail du moteur natif ; remplacé s'il reste bloqué."""

    def __init__(self):
        import queue
        self.jobs: 'queue.Queue' = queue.Queue()
        self.thread = threading.Thread(target=self._loop, daemon=True, name='vdpathops')
        self.thread.start()

    def _loop(self):
        while True:
            name, args, out, done = self.jobs.get()
            try:
                out['r'] = getattr(_native, name)(*args)
            except BaseException as ex:            # erreur ou panique du moteur (PanicException) : repli
                out['e'] = ex
            done.set()


_worker: _Worker | None = None
_worker_lock = threading.Lock()


def _call(name: str, *args):
    """Appel du moteur natif dans le fil de travail, avec délai ;
    _NativeFailed si le délai est dépassé (le fil est alors abandonné et
    remplacé) ou si le moteur renvoie une erreur."""
    global _worker
    # délai proportionnel à la taille : les très gros dessins (130 000
    # segments : 34 s de décalage) ne doivent pas être coupés ; les vraies
    # boucles sans fin sont arrêtées à la source (linesweeper borné)
    n = sum(len(a) for a in args if isinstance(a, list))
    delay = NATIVE_TIMEOUT + n * NATIVE_PER_OP
    with _worker_lock:
        if _worker is None:
            _worker = _Worker()
        w = _worker
        out: dict = {}
        done = threading.Event()
        w.jobs.put((name, args, out, done))
        if not done.wait(delay):
            stuck_calls.append(name)
            _worker = None
            raise _NativeFailed(f'{name} : délai de {delay:g} s dépassé')
    if 'e' in out:
        raise _NativeFailed(str(out['e']))
    return out['r']


def available() -> str:
    return 'vectorcraft-pathops' if _native is not None else 'shapely'


# --- conversions -----------------------------------------------------------------

def to_ops(path: Path, *, close_open: bool = False) -> list:
    ops = []
    for c in path.contours:
        if not c.segments:
            continue
        ops.append((0, list(c.start)))
        for s in c.segments:
            if isinstance(s, Line):
                ops.append((1, list(s.p1)))
            elif isinstance(s, Cubic):
                ops.append((3, [*s.p1, *s.p2, *s.p3]))
            elif isinstance(s, Conic):
                if abs(s.w - 1) < 1e-12:
                    ops.append((2, [*s.p1, *s.p2]))
                else:
                    for cb in s.to_cubics(1e-4):
                        ops.append((3, [*cb.p1, *cb.p2, *cb.p3]))
        if c.closed or close_open:
            ops.append((4, []))
    return ops


def from_ops(ops) -> Path:
    contours: list[Contour] = []
    cur: list = []
    start = pos = None

    def flush(closed):
        nonlocal cur
        if cur:
            contours.append(Contour(cur, closed))
        cur = []

    for code, v in ops:
        if code == 0:
            flush(False)
            start = pos = (v[0], v[1])
        elif code == 1:
            p = (v[0], v[1])
            if dist(pos, p) > 1e-12:
                cur.append(Line(pos, p))
            pos = p
        elif code == 2:
            p = (v[2], v[3])
            cur.append(Conic(pos, (v[0], v[1]), p, 1.0))
            pos = p
        elif code == 3:
            p = (v[4], v[5])
            cur.append(Cubic(pos, (v[0], v[1]), (v[2], v[3]), p))
            pos = p
        elif code == 4:
            if cur and start is not None and dist(pos, start) > 1e-9:
                cur.append(Line(pos, start))
            flush(True)
            pos = start
    flush(False)
    return Path(contours)


# --- repli shapely ---------------------------------------------------------------

def _to_shapely(path: Path):
    from shapely.geometry import Polygon
    polys = []
    for pts in path.flatten(FLATTEN):
        if len(pts) >= 4:
            polys.append(Polygon(pts).buffer(0))
    if not polys:
        return Polygon()
    # pair-impair : xor deux à deux en arbre (n log n au lieu de n² : les
    # dessins de centaines de contours restaient bloqués de longues minutes)
    while len(polys) > 1:
        nxt = [polys[i].symmetric_difference(polys[i + 1]) for i in range(0, len(polys) - 1, 2)]
        if len(polys) % 2:
            nxt.append(polys[-1])
        polys = nxt
    return polys[0]


def _from_shapely(geom) -> Path:
    from shapely.geometry import Polygon
    from .geom import polyline
    polys = [geom] if isinstance(geom, Polygon) else list(getattr(geom, 'geoms', []))
    out = []
    for p in polys:
        if p.is_empty or not isinstance(p, Polygon):
            continue
        out.append(polyline(list(p.exterior.coords)[:-1], closed=True))
        for r in p.interiors:
            out.append(polyline(list(r.coords)[:-1], closed=True))
    return Path(out)


# --- opérations -------------------------------------------------------------------

def boolean(a: Path, b: Path, op: str) -> Path:
    """op : 'union', 'intersect', 'difference' (a − b), 'xor'."""
    if _native is not None:
        try:
            return from_ops(_call('boolean', to_ops(a, close_open=True), to_ops(b, close_open=True), op))
        except _NativeFailed:
            pass
    ga, gb = _to_shapely(a), _to_shapely(b)
    fn = {'union': ga.union, 'intersect': ga.intersection,
          'difference': ga.difference, 'xor': ga.symmetric_difference}[op]
    return _from_shapely(fn(gb))


def union_all(paths: list[Path]) -> Path:
    """Réunion de tous les tracés. Par groupes de tracés dont les cadres se
    chevauchent (deux groupes disjoints n'ont rien à fusionner : leurs
    contours sont mis bout à bout), chaque groupe deux à deux en arbre —
    l'accumulation dans un seul tracé de plus en plus gros coûtait le carré
    du nombre d'objets (1 900 objets : plusieurs minutes)."""
    return _combine_all(paths, 'union', 'Union : objet {0} sur {1}')


def xor_all(paths: list[Path]) -> Path:
    """Exclusion de tous les tracés (elle est associative) : comme `union_all` — deux groupes disjoints n'ont
    rien à exclure entre eux (contours mis bout à bout), chaque groupe deux à deux en arbre. Le pli dans un seul
    tracé de plus en plus gros coûtait le carré du nombre d'objets (1 500 objets : plusieurs minutes)."""
    return _combine_all(paths, 'xor', 'Exclusion : objet {0} sur {1}')


def _combine_all(paths: list[Path], op: str, label: str) -> Path:
    paths = [p for p in paths if p.contours]
    if not paths:
        return Path()
    if len(paths) == 1:                              # (l'exclusion d'un seul tracé le rend normalisé, fermé)
        return paths[0] if op == 'union' else boolean(paths[0], Path(), 'union')
    from . import progress
    boxes = [p.bbox() for p in paths]
    parent = list(range(len(paths)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    order = sorted(range(len(paths)), key=lambda i: boxes[i][0])
    active: list = []                                    # balayage en x : cadres encore ouverts
    for i in order:
        x0, y0, x1, y1 = boxes[i]
        active = [j for j in active if boxes[j][2] >= x0 - 1e-9]
        for j in active:
            if boxes[j][1] <= y1 + 1e-9 and boxes[j][3] >= y0 - 1e-9:
                a, b = find(i), find(j)
                if a != b:
                    parent[a] = b
        active.append(i)
    groups: dict = {}
    for i in range(len(paths)):
        groups.setdefault(find(i), []).append(paths[i])
    total = sum(max(len(g) - 1, 1) for g in groups.values()) or 1
    done = 0
    out = []
    for g in groups.values():
        if len(g) == 1:                              # une forme seule (les trous d'une plaque) : avancement et
            progress.step(done, total, label)        # annulation aussi
            level = [boolean(g[0], Path(), 'union')]
            done += 1
        else:
            level = g
        while len(level) > 1:
            nxt = []
            for k in range(0, len(level) - 1, 2):
                progress.step(done, total, label)
                nxt.append(boolean(level[k], level[k + 1], op))
                done += 1
            if len(level) % 2:
                nxt.append(level[-1])
            level = nxt
        out += level[0].contours
    return Path(out)


#: Décaler, réunion : aire commune (mm²) en deçà de laquelle deux tracés ne font que se toucher
TOUCH_AREA = 1e-4
#: … et largeur (mm) de la bande, le long du plus petit, en deçà de laquelle il est dans l'autre
INSIDE_BAND = 0.01
#: … écart (mm) des bords au-delà duquel deux morceaux ne se croisent sûrement pas (examen rapide, en lignes brisées)
APART = 0.02
#: au-delà de ce nombre de contours fermés, `regions` rend le tracé entier
REGION_MAX = 3000


def regions(path: Path) -> list[Path]:
    """Les morceaux pleins d'un tracé, en pair-impair, ses contours d'origine gardés tels quels : chaque contour fermé
    de profondeur paire avec ses trous (les contours fermés juste dedans) ; un contour ouvert, à lui seul. Au-delà de
    `REGION_MAX` contours fermés : le tracé entier, un seul morceau."""
    import numpy as np
    closed = [c for c in path.contours if c.closed]
    alone = [Path([c]) for c in path.contours if not c.closed]
    if len(closed) <= 1 or len(closed) > REGION_MAX:
        return ([Path(closed)] if closed else []) + alone
    pts, size, boxes = [], [], []
    for c in closed:
        p = np.array(c.flatten(FLATTEN), float)
        pts.append(p)
        if len(p) < 3:
            size.append(0.0)
            boxes.append(None)
            continue
        x, y = p[:, 0], p[:, 1]
        size.append(abs(float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))) / 2)
        boxes.append((x.min(), y.min(), x.max(), y.max()))

    def inside(q, p):
        x0, y0 = p[:, 0], p[:, 1]
        x1, y1 = np.roll(x0, -1), np.roll(y0, -1)
        with np.errstate(divide='ignore', invalid='ignore'):
            cross = ((y0 > q[1]) != (y1 > q[1])) & (q[0] < (x1 - x0) * (q[1] - y0) / (y1 - y0) + x0)
        return bool(np.count_nonzero(cross) % 2)
    order = sorted(range(len(closed)), key=lambda k: (-size[k], k))
    parent, depth = {}, {}
    for pos, k in enumerate(order):
        par = None
        if boxes[k] is not None:
            q = pts[k][0]
            for j in reversed(order[:pos]):              # du plus petit au plus grand : le plus proche qui l'entoure
                b = boxes[j]
                if b is not None and b[0] <= q[0] <= b[2] and b[1] <= q[1] <= b[3] and inside(q, pts[j]):
                    par = j
                    break
        parent[k] = par
        depth[k] = 0 if par is None else depth[par] + 1
    out = []
    for k in range(len(closed)):
        if depth[k] % 2 == 0:
            out.append(Path([closed[k]] + [closed[j] for j in range(len(closed)) if parent[j] == k]))
    return out + alone


def crossing_groups(paths: list[Path], owners: list | None = None) -> list[list[int]]:
    """Décaler, réunion des décalages qui se croisent : groupes (indices croissants, deux au moins) de morceaux
    (`regions`) dont les surfaces se chevauchent en partie, de proche en proche. Ni ceux qui se touchent seulement
    (aire commune sous `TOUCH_AREA`), ni ceux qui sont l'un dans l'autre (une lettre dans son cadre : l'aire commune
    est celle du plus petit, à une bande de `INSIDE_BAND` près le long de son contour) ; un morceau dans un autre
    morceau de son groupe en est retiré (la réunion l'effacerait : une lettre dans un cadre qui croise une autre forme).
    `owners` : le tracé d'où vient chaque morceau ; deux morceaux d'un même tracé ne sont pas comparés. Les cadres
    d'abord (balayage en x), puis un examen rapide en lignes brisées (bords écartés de plus de `APART` : l'un dans
    l'autre ou à part), l'aire exacte de l'intersection pour les autres."""
    from . import progress
    n = len(paths)
    owners = list(range(n)) if owners is None else list(owners)
    boxes = [p.bbox() if p.contours else None for p in paths]
    own: dict = {}
    flat: dict = {}

    def size(i):
        if i not in own:
            own[i] = (abs(area(paths[i])), paths[i].length())
        return own[i]

    def rough(i):
        if i not in flat:
            try:
                g = _to_shapely(paths[i])
                flat[i] = None if g.is_empty else g
            except Exception:                            # noqa: BLE001 — pas d'examen rapide : l'aire exacte
                flat[i] = None
        return flat[i]

    def relation(i, j):
        """'cross', ('inside', petit, grand), ou None."""
        a, b = rough(i), rough(j)
        if a is not None and b is not None:
            try:
                if a.boundary.distance(b.boundary) > APART:
                    if not a.intersects(b):
                        return None
                    return ('inside', i, j) if a.area <= b.area else ('inside', j, i)
            except Exception:                            # noqa: BLE001
                pass
        common = abs(area(boolean(paths[i], paths[j], 'intersect')))
        if common <= TOUCH_AREA:
            return None
        (si, pi), (sj, pj) = size(i), size(j)
        small, per = (si, pi) if si <= sj else (sj, pj)
        if small - common > max(TOUCH_AREA, INSIDE_BAND * per):
            return 'cross'
        return ('inside', i, j) if si <= sj else ('inside', j, i)
    order = sorted((i for i in range(n) if boxes[i] is not None), key=lambda i: boxes[i][0])
    pairs = []
    active: list = []
    for i in order:
        x0, y0, x1, y1 = boxes[i]
        active = [j for j in active if boxes[j][2] >= x0 - 1e-9]
        pairs += [(i, j) for j in active if owners[i] != owners[j]
                  and not (boxes[j][1] > y1 + 1e-9 or boxes[j][3] < y0 - 1e-9)]
        active.append(i)
    cross, within = [], set()
    for done, (i, j) in enumerate(pairs):
        progress.step(done, len(pairs), 'Réunion des décalages : {0} sur {1}')
        r = relation(i, j)
        if r == 'cross':
            cross.append((i, j))
        elif r is not None:
            within.add((r[1], r[2]))

    def components(members, edges):
        parent = {i: i for i in members}

        def find(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i
        for i, j in edges:
            if i in parent and j in parent:
                parent[find(i)] = find(j)
        groups: dict = {}
        for i in members:
            groups.setdefault(find(i), []).append(i)
        return [sorted(g) for g in groups.values() if len(g) > 1]
    out = []
    for g in components(set(i for e in cross for i in e), cross):
        inner = {s for s, b in within if s in g and b in g}  # dans un autre du groupe : la réunion l'effacerait
        out += components(set(g) - inner, cross) if inner else [g]
    return sorted(out)


def offset(path: Path, delta: float, join: str = 'round', miter_limit: float = 4.0) -> Path:
    """Décalage : delta > 0 grossit les contours fermés, delta < 0 les
    amincit ; un contour ouvert devient le contour de son trait.

    Les contours fermés sont d'abord normalisés (règle pair-impair, comme
    partout ailleurs) : le moteur suit la règle non nulle et bouchait les
    trous tracés dans le même sens que leur contour extérieur."""
    closed = [c for c in path.contours if c.closed and c.segments]
    if closed and _native is not None:
        norm = normalize(Path(closed))
        opened = [c for c in path.contours if not c.closed]
        if norm.contours:
            path = Path(norm.contours + opened)
        elif delta > 0:
            # rien ne reste en pair-impair (contours tracés deux fois, pic d'aire nulle) : chaque contour compte comme un
            # trait, à bouts ronds comme dans le calcul exact (`parallel.offset_region`) ; tel quel, le moteur (règle
            # non nulle) remplissait les doublons
            return outline_stroke(Path(closed + opened), 2 * delta, join, 'round')
        elif delta < 0:                     # un retrait ne laisse rien
            return Path()
    if _native is not None:
        try:
            return from_ops(_call('offset', to_ops(path), delta, join, miter_limit))
        except _NativeFailed:
            pass
    from shapely import BufferJoinStyle
    js = {'round': BufferJoinStyle.round, 'miter': BufferJoinStyle.mitre,
          'bevel': BufferJoinStyle.bevel}[join]
    return _from_shapely(_to_shapely(path).buffer(delta, join_style=js, mitre_limit=miter_limit))


def outline_stroke(path: Path, width: float, join: str = 'round', cap: str = 'round') -> Path:
    if _native is not None:
        try:
            return from_ops(_call('outline_stroke', to_ops(path), width, join, cap))
        except _NativeFailed:
            pass
    from shapely.geometry import LineString
    from shapely.ops import unary_union
    lines = [LineString(p) for p in path.flatten(FLATTEN) if len(p) > 1]
    return _from_shapely(unary_union([ln.buffer(width / 2) for ln in lines]))


def normalize(path: Path, evenodd: bool = True) -> Path:
    """Supprime auto-intersections et recouvrements (région pair-impair ;
    `evenodd=False` : règle non nulle, p. ex. réunion en un appel de
    nombreux contours orientés dans le même sens)."""
    if _native is not None:
        try:
            return from_ops(_call('normalize', to_ops(path, close_open=True), evenodd))
        except _NativeFailed:
            pass
    if not evenodd:
        from shapely.geometry import Polygon
        from shapely.ops import unary_union
        polys = [Polygon(pts).buffer(0) for pts in path.flatten(FLATTEN) if len(pts) >= 4]
        return _from_shapely(unary_union(polys)) if polys else Path()
    return _from_shapely(_to_shapely(path))


def area(path: Path, evenodd: bool = True) -> float:
    """Aire de la surface remplie (règle pair-impair ; `evenodd=False` : non nulle), recouvrements comptés une fois."""
    if _native is not None:
        try:
            return _call('area', to_ops(path, close_open=True), evenodd)
        except _NativeFailed:
            pass
    return (_to_shapely(path) if evenodd else _shapely_nonzero(path)).area


def _shapely_nonzero(path: Path):
    """Surface non nulle en shapely (repli de `area` / `fill_areas` : sans retenter le moteur natif, qui vient
    d'échouer ou de dépasser son délai) ; même calcul que le repli de `normalize`."""
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    polys = [Polygon(pts).buffer(0) for pts in path.flatten(FLATTEN) if len(pts) >= 4]
    return unary_union(polys) if polys else Polygon()


def fill_areas(path: Path) -> tuple[float, float]:
    """(aire pair-impair, aire non nulle) de la surface remplie : différentes si le tracé se recouvre dans le même
    sens. Le tracé n'est converti qu'une fois ; `area` normalise lui-même (pas besoin de `normalize` avant)."""
    if _native is not None:
        try:
            ops = to_ops(path, close_open=True)
            return _call('area', ops, True), _call('area', ops, False)
        except _NativeFailed:
            pass
    return _to_shapely(path).area, _shapely_nonzero(path).area
