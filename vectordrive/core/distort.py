"""Déformations de contours (comme les effets « Distorsion » des logiciels
de dessin vectoriel) :

* **zigzag** : le tracé ondule de part et d'autre de lui-même, en pointes
  ou en vagues arrondies, d'une amplitude et d'une longueur d'onde données ;
* **rugosité** : chaque point du tracé écarté au hasard le long de la
  normale (graine fixe : le même résultat à chaque fois) ;
* **contracter / dilater** : les nœuds vont vers le centre et les poignées
  s'en écartent (dilater, bords bombés) ou l'inverse (contracter, pointes) ;
* **torsion** : rotation d'autant plus forte qu'on est près du centre ;
* **festons** : le tracé devient une suite d'arcs réguliers bombés vers
  l'extérieur (comme le nuage de révision des DAO, d'après CADCraft), qui
  se rejoignent aux coins.

Les contours fermés restent fermés ; rien n'est changé en place.
"""
from __future__ import annotations

import math
import random

from .geom import Conic, Contour, Cubic, Line, Path, Point, bulge_segment


def _resample(c: Contour, step: float) -> list[Point]:
    """Points régulièrement espacés (≈ `step`) le long du contour, extrémités
    comprises (fermé : sans répéter le départ)."""
    P = c.flatten(min(step / 8, 0.01))
    seg = [math.dist(a, b) for a, b in zip(P, P[1:])]
    L = sum(seg)
    if L <= 1e-12:
        return P[:1]
    n = max(2, int(round(L / max(step, 1e-6))))
    targets = [L * k / n for k in range(n if c.closed else n + 1)]
    out, acc, i = [], 0.0, 0
    for t in targets:
        while i < len(seg) - 1 and acc + seg[i] < t:
            acc += seg[i]
            i += 1
        f = (t - acc) / seg[i] if seg[i] > 1e-12 else 0.0
        a, b = P[i], P[i + 1]
        out.append((a[0] + f * (b[0] - a[0]), a[1] + f * (b[1] - a[1])))
    return out


def _normals(pts: list[Point], closed: bool) -> list[tuple[float, float]]:
    n = len(pts)
    out = []
    for i in range(n):
        a = pts[(i - 1) % n] if (closed or i > 0) else pts[i]
        b = pts[(i + 1) % n] if (closed or i < n - 1) else pts[i]
        dx, dy = b[0] - a[0], b[1] - a[1]
        L = math.hypot(dx, dy) or 1.0
        out.append((-dy / L, dx / L))
    return out


def _polyline(pts: list[Point], closed: bool) -> Contour:
    ring = pts + [pts[0]] if closed else pts
    return Contour([Line(a, b) for a, b in zip(ring, ring[1:]) if a != b], closed)


def _smooth(pts: list[Point], closed: bool) -> Contour:
    """Courbe lisse passant par les milieux, les points servant de contrôles
    (B-spline quadratique) : les vagues du zigzag arrondi."""
    n = len(pts)
    if n < 3:
        return _polyline(pts, closed)
    mid = lambda a, b: ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)       # noqa: E731
    segs = []
    if closed:
        for i in range(n):
            a, b, c = pts[i - 1], pts[i], pts[(i + 1) % n]
            segs.append(Conic(mid(a, b), b, mid(b, c), 1.0))
        return Contour(segs, True)
    segs.append(Line(pts[0], mid(pts[0], pts[1])))
    for i in range(1, n - 1):
        segs.append(Conic(mid(pts[i - 1], pts[i]), pts[i], mid(pts[i], pts[i + 1]), 1.0))
    segs.append(Line(mid(pts[-2], pts[-1]), pts[-1]))
    return Contour(segs, False)


def zigzag(path: Path, amplitude: float, wavelength: float, smooth: bool = False) -> Path:
    """Zigzag : un point toutes les demi-longueurs d'onde, écarté alternativement
    de ±amplitude ; `smooth` : vagues arrondies."""
    out = []
    for c in path.contours:
        if not c.segments:
            continue
        pts = _resample(c, max(1e-3, wavelength / 2))
        if c.closed and len(pts) % 2:                       # nombre pair : la vague se referme
            pts = _resample(c, max(1e-3, wavelength / 2) * len(pts) / (len(pts) + 1))
        ns = _normals(pts, c.closed)
        moved = [(p[0] + n[0] * amplitude * (1 if i % 2 else -1), p[1] + n[1] * amplitude * (1 if i % 2 else -1))
                 for i, (p, n) in enumerate(zip(pts, ns))]
        if not c.closed:                                    # les bouts restent en place
            moved[0], moved[-1] = pts[0], pts[-1]
        out.append(_smooth(moved, c.closed) if smooth else _polyline(moved, c.closed))
    return Path(out)


def roughen(path: Path, size: float, detail: float, seed: int = 1) -> Path:
    """Rugosité : un point tous les 1/`detail` mm, écarté au hasard (±size)
    le long de la normale."""
    rnd = random.Random(seed)
    out = []
    for c in path.contours:
        if not c.segments:
            continue
        pts = _resample(c, 1.0 / max(1e-3, detail))
        ns = _normals(pts, c.closed)
        out.append(_polyline([(p[0] + n[0] * k, p[1] + n[1] * k) for p, n in zip(pts, ns)
                              for k in [rnd.uniform(-size, size)]], c.closed))
    return Path(out)


def _center(path: Path) -> Point:
    b = path.bbox()
    return ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)


def pucker_bloat(path: Path, amount: float) -> Path:
    """`amount` > 0 : dilater (nœuds vers le centre, poignées vers
    l'extérieur) ; < 0 : contracter. En fraction (0,5 = 50 %)."""
    from .nodes import _as_cubic
    cx, cy = _center(path)

    def move(p, k):
        return (p[0] + k * (p[0] - cx), p[1] + k * (p[1] - cy))
    out = []
    for c in path.contours:
        segs = []
        for s in c.segments:
            q = _as_cubic(s)
            segs.append(Cubic(move(q.p0, -amount), move(q.p1, amount), move(q.p2, amount), move(q.p3, -amount)))
        out.append(Contour(segs, c.closed))
    return Path(out)


#: raccord de segments qui tourne de plus de CORNER degrés : un coin (les festons s'y rejoignent)
CORNER = 20.0
#: festons d'un contour au plus
MAX_ARCS = 20000


def _dir(P: list[Point], end: bool) -> tuple[float, float] | None:
    """Direction au départ (ou à l'arrivée) d'une polyligne, None si elle n'a
    pas de longueur."""
    Q = P[::-1] if end else P
    for q in Q[1:]:
        dx, dy = q[0] - Q[0][0], q[1] - Q[0][1]
        L = math.hypot(dx, dy)
        if L > 1e-9:
            return (-dx / L, -dy / L) if end else (dx / L, dy / L)
    return None


def _runs(c: Contour, tol: float) -> tuple[list[list[Point]], bool]:
    """Polylignes d'un coin à l'autre ; (polylignes, bouclé) — bouclé : fermé
    sans coin, une seule polyligne qui revient à son départ."""
    segs = list(c.segments)
    if c.closed and math.dist(segs[-1].end, segs[0].start) > 1e-9:
        segs.append(Line(segs[-1].end, segs[0].start))          # fermeture implicite
    polys = [[s.start] + s.flatten(tol) for s in segs]          # flatten : sans le départ
    keep = [i for i, P in enumerate(polys) if _dir(P, False) is not None]
    polys = [polys[i] for i in keep]
    if not polys:
        return [], False
    n = len(polys)

    def corner(i):                                              # coin au départ de la polyligne i
        if i == 0 and not c.closed:
            return True
        a, b = _dir(polys[i - 1], True), _dir(polys[i], False)
        cos = max(-1.0, min(1.0, a[0] * b[0] + a[1] * b[1]))
        return math.degrees(math.acos(cos)) > CORNER
    corners = [i for i in range(n) if corner(i)]
    if not corners:
        whole = [polys[0][0]]
        for P in polys:
            whole += P[1:]
        return [whole], c.closed
    start = corners[0]
    order = list(range(start, n)) + (list(range(start)) if c.closed else [])
    runs, cur = [], None
    for i in order:
        if i in corners or cur is None:
            cur = [polys[i][0]]
            runs.append(cur)
        cur += polys[i][1:]
    return runs, False


def _along(P: list[Point], step: float) -> list[Point]:
    """Départs de festons égaux (≈ `step`) le long d'une polyligne, son départ
    compris, son arrivée exclue."""
    seg = [math.dist(a, b) for a, b in zip(P, P[1:])]
    L = sum(seg)
    k = max(1, int(round(L / step)))
    out, acc, i = [], 0.0, 0
    for t in (L * j / k for j in range(k)):
        while i < len(seg) - 1 and acc + seg[i] < t:
            acc += seg[i]
            i += 1
        f = (t - acc) / seg[i] if seg[i] > 1e-12 else 0.0
        a, b = P[i], P[i + 1]
        out.append((a[0] + f * (b[0] - a[0]), a[1] + f * (b[1] - a[1])))
    return out


def scallop(path: Path, step: float, bulge: float = 0.5, inward: bool = False) -> Path:
    """Festons : chaque contour devient une suite d'arcs d'une corde ≈ `step`
    mm, bombés vers l'extérieur (vers l'intérieur : `inward` ; contour ouvert :
    à droite du sens de parcours). `bulge` = tan(¼ de l'angle de l'arc) :
    0,5 comme le nuage de révision des DAO (arcs de 106°), 1 en demi-cercles.
    Les festons se rejoignent aux coins ; le sens des contours est gardé."""
    if not (step > 0) or not math.isfinite(step):
        return path
    bulge = max(0.05, min(1.0, abs(float(bulge))))
    out = []
    for c in path.contours:
        if not c.segments:
            continue
        tol = min(step / 50, 0.001)
        runs, looped = _runs(c, tol)
        if not runs:
            continue
        length = sum(math.dist(a, b) for P in runs for a, b in zip(P, P[1:]))
        st = max(step, length / MAX_ARCS)
        pts = [p for P in runs for p in _along(P, st)]
        if not c.closed:
            pts.append(runs[-1][-1])
        if len(pts) < 2:
            continue
        side = 1.0
        if c.closed:
            side = 1.0 if c.signed_area() > 0 else -1.0             # anti-horaire : l'extérieur est à droite
        b = bulge * side * (-1.0 if inward else 1.0)
        pairs = list(zip(pts, pts[1:])) + ([(pts[-1], pts[0])] if c.closed else [])
        segs = [s for p, q in pairs if math.dist(p, q) > 1e-9 for s in bulge_segment(p, q, b)]
        out.append(Contour(segs, c.closed))
    return Path(out)


def twist(path: Path, angle: float, step: float = 0.5) -> Path:
    """Torsion : rotation de `angle`° au centre, nulle au point le plus
    éloigné, sur le tracé rééchantillonné tous les `step` mm."""
    cx, cy = _center(path)
    out = []
    pts_all = []
    for c in path.contours:
        pts_all.append(_resample(c, step) if c.segments else [])
    R = max((math.hypot(p[0] - cx, p[1] - cy) for pts in pts_all for p in pts), default=0.0)
    if R <= 1e-12:
        return path
    for c, pts in zip(path.contours, pts_all):
        if not pts:
            continue
        moved = []
        for x, y in pts:
            dx, dy = x - cx, y - cy
            a = math.radians(angle) * (1 - math.hypot(dx, dy) / R)
            ca, sa = math.cos(a), math.sin(a)
            moved.append((cx + ca * dx - sa * dy, cy + sa * dx + ca * dy))
        out.append(_polyline(moved, c.closed))
    return Path(out)
