"""Points minimaux (demande du 27/11 : « Fonctions décalage avec congés et autres et lissages minimiser le nombre de
point en courbe et utiliser les points hors courbe ») : un tracé rendu avec le moins de nœuds possible sur la courbe,
à un écart toléré près — comme le dessinerait TypeEdit : des droites, des **arcs de cercle exacts** (coniques, un
morceau par quart de tour au plus) et des Bézier cubiques dont les points hors courbe portent la forme.

Les décalages, booléens, Pathfinder et lissages rendent souvent des tracés trop chargés : le moteur des booléens coupe
chaque arc en seize Bézier par quart de cercle, shapely rend des polygones de points serrés, le lissage une B-spline à
pas régulier. `minimal_path(tracé, tol)` les reprend contour par contour :

- **coins vifs gardés** : un changement de direction de plus de CORNER_DEG degrés reste un coin ; entre deux coins, le
  morceau est lisse et se traite à part ;
- **droites** : les droites qui se suivent alignées (à `tol` près) n'en font qu'une ; une suite d'au moins trois
  petites droites presque dans le prolongement l'une de l'autre est lue comme les points d'une courbe (polygone de
  shapely, vectorisation) — une droite nettement plus longue que ses voisines y reste une droite ;
- **arcs** : les morceaux qui suivent un même cercle (à `tol` près, ajustement aux moindres carrés, centre ramené sur
  la médiatrice de la corde pour passer exactement par les deux bouts) deviennent un arc exact, de 1 à 4 coniques
  selon l'angle ; un cercle entier : 4 coniques. Un arc reconnu doit couvrir au moins deux segments d'origine et
  ARC_MIN_DEG degrés, sauf s'il était déjà un arc exact (sinon tout petit morceau de courbe passerait pour un arc) ;
- **le reste** : Bézier cubiques ajustées aux moindres carrés, coupées au point le plus éloigné tant que l'écart
  dépasse la tolérance (méthode de Schneider, `fitcurve.fit_points`), tangentes prises sur les morceaux voisins :
  la jonction reste lisse (G1) ;
- **arcs ou Bézier** : le morceau est refait avec tous les arcs reconnus, avec les plus grands seulement (BIG_ARC_DEG
  degrés au moins), puis sans eux (une courbe quelconque, une ellipse, se rend mieux en quelques Bézier qu'en une
  suite d'arcs) ; le moins d'éléments l'emporte — un arc compte pour un, quel que soit son angle — et les arcs à
  égalité ;
- **contour fermé sans coin** : sa couture est mise à une jonction entre deux morceaux (pas de nœud de couture au
  milieu d'un arc ou d'une courbe) ;
- **contrôle** : chaque morceau refait est comparé à l'original, dans les deux sens (points de l'un à la ligne de
  l'autre) ; au-delà de la tolérance, ou sans nœud gagné, l'original reste.
"""
from __future__ import annotations

import math

import numpy as np

from . import fitcurve
from .geom import Conic, Contour, Cubic, Line, Path, dist

#: écart toléré d'office (mm)
TOLERANCE = 0.01
#: au-delà de ce changement de direction (degrés), un nœud est un coin vif
CORNER_DEG = 15.0
#: un arc reconnu plus court (degrés), ou fait d'un seul segment, ne compte que s'il était déjà un arc exact
ARC_MIN_DEG = 10.0
#: essai intermédiaire : seuls les arcs reconnus d'au moins BIG_ARC_DEG degrés sont gardés
BIG_ARC_DEG = 45.0
#: dans une suite de petites droites, une droite plus longue que LONG_LINE fois leur longueur médiane reste une droite
LONG_LINE = 4.0
#: au-delà (segments d'un contour), le contour reste tel quel (calcul trop long pour l'interface)
MAX_SEGMENTS = 20000
#: un cercle plus grand (mm) est une droite
R_MAX = 1e5
#: part de la tolérance laissée aux ajustements (le reste couvre l'échantillonnage du contrôle)
FIT_SHARE = 0.8
#: seuil du contrôle (part de la tolérance) : les deux tracés y sont aplatis au seizième de la tolérance, l'écart vrai
#: est au plus l'écart mesuré plus deux fois cet aplatissement — il reste sous la tolérance
CHECK_SHARE = 1.0 - 2.0 / 16.0
#: un segment plus petit (part de la tolérance) a une direction de hasard : il ne compte pas pour trouver les coins
SPECK_SHARE = 0.25


# --- petits outils ------------------------------------------------------------------

def _unit(v):
    n = math.hypot(v[0], v[1])
    return (v[0] / n, v[1] / n) if n > 1e-15 else None


def _start_tangent(seg):
    p = seg.controls()
    for q in p[1:]:
        u = _unit((q[0] - p[0][0], q[1] - p[0][1]))
        if u is not None:
            return u
    return None


def _end_tangent(seg):
    p = seg.controls()
    for q in reversed(p[:-1]):
        u = _unit((p[-1][0] - q[0], p[-1][1] - q[1]))
        if u is not None:
            return u
    return None


def _turn_deg(a, b) -> float:
    if a is None or b is None:
        return 0.0
    return math.degrees(math.atan2(abs(a[0] * b[1] - a[1] * b[0]), a[0] * b[0] + a[1] * b[1]))


def _samples(seg, tol: float) -> np.ndarray:
    """Points du segment, bouts compris : une droite, ses bouts et son milieu (le plus loin d'un cercle) ; une courbe,
    aplatie au seizième de la tolérance (5 points au moins)."""
    if isinstance(seg, Line):
        (x0, y0), (x1, y1) = seg.p0, seg.p1
        return np.array([(x0, y0), ((x0 + x1) / 2, (y0 + y1) / 2), (x1, y1)], float)
    pts = [seg.start] + list(seg.flatten(tol / 16))
    if len(pts) < 5:
        pts = [seg.point(t) for t in (0.0, 0.25, 0.5, 0.75, 1.0)]
    return np.asarray(pts, float)


def _exact_arc(seg) -> bool:
    return isinstance(seg, Conic) and seg.circle_params() is not None


def _straight(seg, tol: float) -> bool:
    if isinstance(seg, Line):
        return True
    p = seg.controls()
    a, b = p[0], p[-1]
    L = dist(a, b)
    if L < 1e-9:
        return False
    for q in p[1:-1]:
        t = ((q[0] - a[0]) * (b[0] - a[0]) + (q[1] - a[1]) * (b[1] - a[1])) / (L * L)
        h = abs((q[0] - a[0]) * (b[1] - a[1]) - (q[1] - a[1]) * (b[0] - a[0])) / L
        if h > tol / 4 or not -1e-9 <= t <= 1 + 1e-9:
            return False
    return True


def node_count(path: Path) -> int:
    """Nœuds sur la courbe d'un tracé (extrémités des segments, la couture d'un fermé comptée une fois)."""
    return sum(len(c.nodes()) for c in path.contours)


# --- ajustements ------------------------------------------------------------------

def _longest(lo: int, stop: int, ok) -> int:
    """La plus grande fin v (lo ≤ v ≤ stop) telle que ok(v), ok(lo) étant acquis : au galop, puis par dichotomie."""
    step, hi = 1, None
    while lo < stop:
        v = min(stop, lo + step)
        if not ok(v):
            hi = v
            break
        lo, step = v, step * 2
    while hi is not None and hi - lo > 1:
        mid = (lo + hi) // 2
        if ok(mid):
            lo = mid
        else:
            hi = mid
    return lo


def _fits_line(P: np.ndarray, tol: float) -> bool:
    a, b = P[0], P[-1]
    v = b - a
    L = float(np.hypot(*v))
    if L < 1e-9:
        return False
    d = P - a
    h = np.abs(d[:, 0] * v[1] - d[:, 1] * v[0]) / L
    t = (d @ v) / L
    return bool(h.max() <= tol and t.min() >= -tol and t.max() <= L + tol and (np.diff(t) >= -tol).all())


def _fit_circle(P: np.ndarray, tol: float):
    """(centre, rayon, angle de départ en degrés, balayage signé en degrés) du cercle qui passe à `tol` de tous les
    points, exactement par le premier et le dernier (un tour entier si ce sont les mêmes) ; None sinon."""
    if len(P) < 3:
        return None
    m = P.mean(axis=0)
    X = P - m
    A = np.column_stack([X[:, 0], X[:, 1], np.ones(len(X))])
    sol, *_ = np.linalg.lstsq(A, (X ** 2).sum(axis=1), rcond=None)
    c = np.array([sol[0] / 2, sol[1] / 2]) + m
    if not np.isfinite(c).all():
        return None
    S, E = P[0], P[-1]
    chord = E - S
    L = float(np.hypot(*chord))
    if L > 1e-9:                                         # centre sur la médiatrice : l'arc passe par les deux bouts
        n = np.array([-chord[1], chord[0]]) / L
        mid = (S + E) / 2
        c = mid + n * float((c - mid) @ n)
    r = float(np.hypot(*(S - c)))
    if not 1e-6 < r < R_MAX:
        return None
    if float(np.abs(np.hypot(*(P - c).T) - r).max()) > tol:
        return None
    a = np.unwrap(np.arctan2(P[:, 1] - c[1], P[:, 0] - c[0]))
    d = np.diff(a)
    sweep = float(a[-1] - a[0])
    sign = 1.0 if sweep >= 0 else -1.0
    if (d * sign < -1e-6).any():                         # l'arc revient en arrière : pas un cercle parcouru
        return None
    if L <= 1e-9:
        if abs(abs(sweep) - 2 * math.pi) > 1e-3:
            return None
        sweep = 2 * math.pi * sign
    elif abs(sweep) >= 2 * math.pi:
        return None
    return (float(c[0]), float(c[1])), r, math.degrees(float(a[0])), math.degrees(sweep)


def _arc_segments(S, E, circle) -> list:
    """L'arc exact de S à E sur le cercle (coniques de 90° au plus, 1 à 4)."""
    (cx, cy), r, a0, sweep = circle
    n = max(1, math.ceil((abs(sweep) - 0.05) / 90.0))
    step = math.radians(sweep) / n
    w = math.cos(step / 2)
    t = math.radians(a0)
    k = r / w
    pts = [S]
    for i in range(1, n):
        pts.append((cx + r * math.cos(t + i * step), cy + r * math.sin(t + i * step)))
    pts.append(E)
    out = []
    for i in range(n):
        mid = t + (i + 0.5) * step
        out.append(Conic(pts[i], (cx + k * math.cos(mid), cy + k * math.sin(mid)), pts[i + 1], w))
    return out


def _bezier(P: np.ndarray, t0, t1, tol: float) -> list:
    """Bézier (ou droites) passant à `tol` des points ; t0 tangente de départ, t1 tangente d'arrivée (sortante)."""
    keep = np.r_[True, np.hypot(*np.diff(P, axis=0).T) > 1e-12]
    P = P[keep]
    if len(P) < 2:
        return []
    if t0 is None:
        t0 = _unit(tuple(P[1] - P[0]))
    if t1 is None:
        t1 = _unit(tuple(P[-1] - P[-2]))
    a = np.asarray(t0, float)
    b = -np.asarray(t1, float)                           # fitcurve : tangente de fin orientée vers l'intérieur
    return [fitcurve._to_segment(c, tol) for c in fitcurve.fit_points(P, a, b, tol)]


def _chained(segs: list) -> list:
    """Chaque segment part exactement de la fin du précédent."""
    out = []
    for s in segs:
        if out and out[-1].end != s.start:
            p = out[-1].end
            if isinstance(s, Line):
                s = Line(p, s.p1)
            elif isinstance(s, Cubic):
                s = Cubic(p, s.p1, s.p2, s.p3)
            else:
                s = Conic(p, s.p1, s.p2, s.w)
        out.append(s)
    return out


def _deviation(a: np.ndarray, b: np.ndarray) -> float:
    """Écart entre deux suites de points serrées : le plus grand écart d'un point de l'une à la ligne de l'autre."""
    import shapely
    if len(a) < 2 or len(b) < 2:
        return math.inf
    la, lb = shapely.LineString(a), shapely.LineString(b)
    return float(max(shapely.distance(lb, shapely.points(a[:, 0], a[:, 1])).max(),
                     shapely.distance(la, shapely.points(b[:, 0], b[:, 1])).max()))


def _polyline(segs: list, tol: float) -> np.ndarray:
    parts = [_samples(s, tol) for s in segs]
    return np.concatenate([parts[0]] + [p[1:] for p in parts[1:]]) if parts else np.zeros((0, 2))


# --- un morceau lisse ---------------------------------------------------------------

class _Run:
    """Un morceau sans coin : ses segments, leurs points, ses unités (droites alignées réunies, courbes une à une)."""

    def __init__(self, segs: list, tol: float):
        self.segs = segs
        self.tol = tol
        self.ftol = tol * FIT_SHARE
        pts = [_samples(s, tol) for s in segs]
        # tous les points d'un tenant (le départ d'un segment est l'arrivée du précédent) ; segment k : de off[k] à
        # off[k + 1] compris — les points de plusieurs segments se prennent d'une tranche, sans recopie
        self.off = np.r_[0, np.cumsum([len(p) - 1 for p in pts])]
        self.flat = np.concatenate([pts[0]] + [p[1:] for p in pts[1:]])
        self.nodes = np.asarray([segs[0].start] + [s.end for s in segs], float)
        self.units = self._units()

    def points(self, i0: int, i1: int) -> np.ndarray:
        return self.flat[self.off[i0]:self.off[i1] + 1]

    def _units(self) -> list:
        """[début, fin, sorte] : 'L' droites alignées réunies, 'C' une courbe. Des segments droits (à un quart de
        l'écart près), seuls les nœuds sont à contrôler ; la plus longue suite alignée se cherche au galop."""
        out = []
        i, n = 0, len(self.segs)
        straight = [_straight(s, self.ftol) for s in self.segs]
        while i < n:
            if not straight[i]:
                out.append([i, i + 1, 'C'])
                i += 1
                continue
            stop = i + 1
            while stop < n and straight[stop]:
                stop += 1
            j = _longest(i + 1, stop, lambda v: _fits_line(self.nodes[i:v + 1], self.ftol * 0.75))
            out.append([i, j, 'L'])
            i = j
        return out

    def _anchors(self) -> list:
        """Les droites qui restent droites : seules ou par deux, ou bien plus longues que leurs voisines ; les autres,
        par trois au moins, sont les points d'une courbe."""
        u = self.units
        lens = [dist(self.segs[a].start, self.segs[b - 1].end) if k == 'L' else 0.0 for a, b, k in u]
        anchor = [False] * len(u)
        i = 0
        while i < len(u):
            if u[i][2] != 'L':
                i += 1
                continue
            j = i
            while j < len(u) and u[j][2] == 'L':
                j += 1
            if j - i < 3:
                for k in range(i, j):
                    anchor[k] = True
            else:
                med = float(np.median(lens[i:j]))
                for k in range(i, j):
                    anchor[k] = lens[k] > LONG_LINE * med
            i = j
        return anchor

    def _longest_arc(self, u0: int, stop: int):
        """La plus longue suite d'unités depuis u0 (avant `stop`) qui suit un cercle : (fin, cercle) ou None."""
        u = self.units

        def fit(v):
            return _fit_circle(self.points(u[u0][0], u[v - 1][1]), self.ftol)
        lo = u0 + 1
        c = fit(lo)
        if c is None and u[u0][2] == 'L' and lo < stop:   # une droite seule ne fait pas un cercle : deux au moins
            lo += 1
            c = fit(lo)
        if c is None:
            return None
        best, step, hi = (lo, c), 1, None
        while lo < stop:                                  # recherche au galop, puis par dichotomie
            v = min(stop, lo + step)
            c = fit(v)
            if c is None:
                hi = v
                break
            best, lo = (v, c), v
            step *= 2
        while hi is not None and hi - lo > 1:
            mid = (lo + hi) // 2
            c = fit(mid)
            if c is None:
                hi = mid
            else:
                best, lo = (mid, c), mid
        return best

    def pieces(self) -> list:
        """[sorte, unité de début, unité de fin, cercle] : 'L' droite, 'A' arc, 'F' courbe libre."""
        u = self.units
        anchor = self._anchors()
        # une vraie droite arrête un arc ; un morceau de courbe presque droit (le bout d'un arc coupé par le moteur
        # des booléens, un côté droit d'une courbe lissée) peut en faire partie, sinon il devient une droite
        hard = [a and any(isinstance(s, Line) for s in self.segs[x:y]) for a, (x, y, _k) in zip(anchor, u)]
        out = []
        i = 0
        while i < len(u):
            if hard[i]:
                out.append(['L', i, i + 1, None])
                i += 1
                continue
            stop = i
            while stop < len(u) and not hard[stop]:
                stop += 1
            got = self._longest_arc(i, stop)
            if got is not None:
                v, circle = got
                exact = any(_exact_arc(s) for a, b, _k in u[i:v] for s in self.segs[a:b])
                if exact or (abs(circle[3]) >= ARC_MIN_DEG and u[v - 1][1] - u[i][0] >= 2):
                    out.append(['A', i, v, circle])
                    i = v
                    continue
            if anchor[i]:
                out.append(['L', i, i + 1, None])
                i += 1
                continue
            if out and out[-1][0] == 'F':
                out[-1][2] = i + 1
            else:
                out.append(['F', i, i + 1, None])
            i += 1
        return out

    def build(self, pieces: list, ring: bool) -> list:
        """Les segments refaits du morceau, pièce par pièce (une pièce sans gain garde ses segments d'origine)."""
        u, segs = self.units, self.segs
        made: list = [None] * len(pieces)
        for k, (kind, a, b, circle) in enumerate(pieces):
            i0, i1 = u[a][0], u[b - 1][1]
            S, E = segs[i0].start, segs[i1 - 1].end
            if kind == 'L':
                made[k] = [Line(S, E)]
            elif kind == 'A':
                made[k] = _arc_segments(S, E, circle)
        for k, (kind, a, b, _c) in enumerate(pieces):
            if kind != 'F':
                continue
            i0, i1 = u[a][0], u[b - 1][1]
            P = self.points(i0, i1)
            whole = ring and len(pieces) == 1
            prev = made[k - 1] if (k > 0 or ring) and len(pieces) > 1 else None
            nxt = made[(k + 1) % len(pieces)] if (k + 1 < len(pieces) or ring) and len(pieces) > 1 else None
            t0 = _end_tangent(prev[-1]) if prev else _start_tangent(segs[i0])
            t1 = _start_tangent(nxt[0]) if nxt else _end_tangent(segs[i1 - 1])
            if whole:                                    # couture d'une boucle lisse : tangente commune
                t0 = _unit(tuple(P[1] - P[-2]))
                t1 = t0
            fit = _bezier(P, t0, t1, self.ftol)
            made[k] = fit if fit and len(fit) < i1 - i0 else list(segs[i0:i1])
        return made

    def _free(self, pieces: list, below: float = math.inf) -> list:
        """Les mêmes pièces, les arcs reconnus de moins de `below` degrés (pas ceux qui étaient déjà des arcs exacts)
        rendus aux courbes libres : sur une courbe quelconque, quelques Bézier font parfois mieux qu'une suite
        d'arcs."""
        u, out = self.units, []
        for kind, a, b, circle in pieces:
            if kind == 'A' and abs(circle[3]) < below and \
                    not any(_exact_arc(s) for x, y, _k in u[a:b] for s in self.segs[x:y]):
                kind, circle = 'F', None
            if kind == 'F' and out and out[-1][0] == 'F':
                out[-1][2] = b
            else:
                out.append([kind, a, b, circle])
        return out

    def result(self, ring: bool) -> list:
        """Les segments refaits — avec les arcs reconnus, ou sans eux : le moins d'éléments l'emporte (un arc compte
        pour un), les arcs à égalité —, contrôlés contre l'original ; l'original s'il n'y a rien à gagner ou si
        l'écart dépasse la tolérance."""
        pieces = self.pieces()
        tries = []
        for p in (pieces, self._free(pieces, BIG_ARC_DEG), self._free(pieces)):   # tous les arcs, les grands, aucun
            if p not in tries:
                tries.append(p)
        best, cost = list(self.segs), len(self.segs)
        for p in tries:
            made = self.build(p, ring)
            n = sum(1 if piece[0] == 'A' else len(m) for piece, m in zip(p, made))
            out = _chained([s for m in made for s in m])
            if n < cost and _deviation(_polyline(out, self.tol), self.flat) <= self.tol * CHECK_SHARE:
                best, cost = out, n
        self.cost = cost
        return best


def _ring(segs: list, tol: float) -> list:
    """Une boucle sans coin : la couture là où elle est, au début de sa dernière pièce (la première la continue
    peut-être : deux courbes libres, deux arcs du même cercle, le bout d'un arc) ou au début de sa première droite ;
    le moins d'éléments l'emporte."""
    run = _Run(segs, tol)
    p = run.pieces()
    starts = [0]
    if len(p) > 1:
        starts.append(run.units[p[-1][1]][0])
    line = next((k for k, s in enumerate(segs) if isinstance(s, Line)), 0)
    starts.append(line)
    best, cost = None, None
    for k in dict.fromkeys(starts):
        r = run if k == 0 else _Run(segs[k:] + segs[:k], tol)
        out = r.result(True)
        if best is None or r.cost < cost:
            best, cost = out, r.cost
    return best


# --- contours et tracés --------------------------------------------------------------

def _corners(segs: list, closed: bool, corner: float, tol: float) -> list:
    """Les jonctions qui sont des coins vifs (virage de plus de `corner` degrés). Un micro-segment (moins de
    SPECK_SHARE × tol, direction de hasard : jonctions du moteur des booléens) ne compte pas : le virage se mesure
    par-dessus lui, et le coin se met à son départ."""
    n = len(segs)
    speck = [max(dist(s.start, q) for q in s.controls()) < tol * SPECK_SHARE for s in segs]
    if all(speck):
        return []
    out = []
    for k in range(0 if closed else 1, n):
        if speck[k - 1]:                                 # mesuré à la jonction d'avant (ou bout d'un ouvert)
            continue
        j = k
        while speck[j % n] and (closed or j < n - 1) and j - k < n:
            j += 1
        if speck[j % n]:                                 # rien de mesurable après : bout d'un ouvert
            continue
        if _turn_deg(_end_tangent(segs[k - 1]), _start_tangent(segs[j % n])) > corner:
            out.append(k)
    return out


def minimal_contour(c: Contour, tol: float = TOLERANCE, corner: float = CORNER_DEG) -> Contour:
    """Le contour avec le moins de nœuds possible à `tol` près (droites, arcs exacts, Bézier) ; tel quel s'il n'y a
    rien à gagner."""
    segs = [s for s in c.segments if max(dist(s.start, q) for q in s.controls()) > 1e-9]
    if len(segs) < 2 or len(segs) > MAX_SEGMENTS or tol <= 0:
        return c
    closed = c.closed
    if closed and dist(segs[-1].end, segs[0].start) > 1e-9:
        segs.append(Line(segs[-1].end, segs[0].start))
    n = len(segs)
    cuts = _corners(segs, closed, corner, tol)
    if closed and not cuts:                              # boucle lisse : couture à une jonction de pièces
        out = _ring(segs, tol)
    else:
        if closed:                                       # le contour part d'un coin
            segs = segs[cuts[0]:] + segs[:cuts[0]]
            cuts = [(k - cuts[0]) % n for k in cuts]
        bounds = sorted(set([0] + cuts + [n]))
        out = []
        for a, b in zip(bounds, bounds[1:]):
            out += _Run(segs[a:b], tol).result(False) if b - a > 1 else segs[a:b]
    if len(out) >= len(c.segments):
        return c
    new = Contour(_chained(out), closed)
    if not _simple(new, tol) and _simple(c, tol):        # un col plus étroit que la tolérance s'est refermé
        return c
    return new


def _simple(c: Contour, tol: float) -> bool:
    g = _line_of(c, tol)
    return g is None or bool(g.is_simple)


def minimal_path(path: Path, tol: float = TOLERANCE, corner: float = CORNER_DEG) -> Path:
    """Le tracé avec le moins de nœuds possible, contour par contour (fonction du module : calculable dans un autre
    processus, `workers.adaptive_map`)."""
    if tol <= 0 or not path.contours:
        return path
    out = [minimal_contour(c, tol, corner) for c in path.contours]
    if all(a is b for a, b in zip(out, path.contours)):
        return path
    out = _kept_apart(path.contours, out, tol)
    if all(a is b for a, b in zip(out, path.contours)):
        return path
    return Path(out)


def _line_of(c: Contour, tol: float):
    import shapely
    pts = c.flatten(tol / 4) if c.segments else []
    if c.closed and len(pts) > 1:
        pts = list(pts) + [pts[0]]
    return shapely.LineString(pts) if len(pts) > 1 else None


def _kept_apart(orig: list, out: list, tol: float) -> list:
    """Les contours d'un tracé sont refaits chacun à part : un trou, une île ou un col plus étroit que deux fois la
    tolérance pourrait se croiser avec son voisin refait. Deux contours qui se croisent après et pas avant reprennent
    leur tracé d'origine (tant qu'il en reste)."""
    import shapely
    out = list(out)
    if len(out) < 2:
        return out
    old = [None] * len(out)
    for _ in range(len(out)):                            # un contour repris peut croiser un autre refait : on recommence
        lines = [_line_of(c, tol) for c in out]
        idx = [k for k, g in enumerate(lines) if g is not None]
        tree = shapely.STRtree([lines[k] for k in idx])
        back = set()
        for i in range(len(out)):
            if out[i] is orig[i] or lines[i] is None:
                continue
            for jj in tree.query(lines[i], predicate='intersects'):
                j = idx[int(jj)]
                if j == i:
                    continue
                for k in (i, j):
                    if old[k] is None:
                        old[k] = _line_of(orig[k], tol)
                if old[i] is not None and old[j] is not None and shapely.intersects(old[i], old[j]):
                    continue                             # ils se croisaient déjà
                back |= {k for k in (i, j) if out[k] is not orig[k]}
        if not back:
            break
        for k in back:
            out[k] = orig[k]
    return out


def smooth(path: Path, length: float, sharpness: float, tol: float, fit: float, report: dict | None = None) -> Path:
    """La Courbe lisse (`smoothcurve.smooth`), puis aux points minimaux à l'écart `fit` (0 : telle quelle) : la même
    sortie pour la commande, l'aperçu de l'outil Lissage C∞ et l'assistant. `report['deviation']` : l'écart au
    contour d'origine, mesuré sur le tracé rendu."""
    from . import smoothcurve as SC
    out = SC.smooth(path, length, sharpness, tol, report)
    if fit <= 0:
        return out
    got = minimal_path(out, fit)
    if report is not None and got is not out:
        report['deviation'] = max(float(report.get('deviation', 0.0)), SC.deviation(path, got, tol))
    return got


def minimal_paths(paths: list, tol: float) -> list:
    """`minimal_path` de chaque tracé ; `tol` ≤ 0 (interrupteur coupé) : les tracés tels quels. Un long travail
    passe sur plusieurs processus."""
    if tol <= 0 or not paths:
        return list(paths)
    from . import workers
    return workers.adaptive_map(minimal_path, [(p, tol) for p in paths])


def minimal_pairs(pairs: list, tol: float) -> list:
    """[(tracé, outil)] → les mêmes, tracés avec le moins de nœuds possible (`minimal_paths`)."""
    pairs = list(pairs)
    if tol <= 0 or not pairs:
        return pairs
    return list(zip(minimal_paths([p for p, _t in pairs], tol), [t for _p, t in pairs]))
