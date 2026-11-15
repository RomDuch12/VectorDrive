"""Enroulement des parcours sur un cylindre ou un cône, usinés sur une
machine 3 axes (TypeEdit : FAO ▸ Enroulement cylindrique / conique,
`ID_CMDFAO_CYL_MAPPING`, `ID_CMDFAO_CON_MAPPING`).

La pièce est couchée, son axe parallèle à Y (`*_y`) ou à X (`*_x`). Le
dessin, à plat, s'enroule autour d'elle : l'écart à la génératrice du
dessus (`origin`, mesuré en travers de l'axe) devient un arc de la
circonférence de rayon `radius` (comme TypeEdit : « la circonférence donnée
par le premier rayon correspond à l'axe 0X »), puis la profondeur est
reprise à la verticale du point de la surface (projection parallèle :
l'outil reste vertical). Cône : rayon `radius` à la cote 0 de l'axe,
`radius2` à la cote `length`, axe horizontal ; les lignes du dessin
parallèles à l'axe suivent ses génératrices.

Repère : Z = 0 sur le dessus de la pièce, à la génératrice `origin` et à
la cote 0 de l'axe. Les mouvements au dégagement gardent leur hauteur,
relevée du point le plus haut de la surface ; les autres suivent la
surface, découpés pour que la flèche des cordes reste sous la tolérance.
Tout cas douteux (rayon nul, dessin au-delà de la pointe du cône ou de
plus d'un quart de tour, arcs) est refusé : rien n'est écrit plutôt
qu'un parcours faux.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from .model import Move

MODES = {
    'none': 'Aucun',
    'cylindre_y': 'Cylindre, axe selon Y',
    'cylindre_x': 'Cylindre, axe selon X',
    'cone_y': 'Cône, axe selon Y',
    'cone_x': 'Cône, axe selon X',
    'surface': 'Surface d\'une pièce STEP (projection parallèle)',
    'locale': 'Surface d\'une pièce, le long d\'une courbe guide (projection locale)',
}
#: angle depuis le dessus (°) au-delà duquel on prévient : l'outil vertical attaque en biais
WARN_ANGLE = 60.0
#: au-delà, refusé (l'outil frôlerait le flanc de la pièce)
MAX_ANGLE = 85.0


@dataclass
class Wrap:
    mode: str
    radius: float
    origin: float = 0.0
    radius2: float = 0.0
    length: float = 0.0

    @classmethod
    def of(cls, op) -> 'Wrap | None':
        """L'enroulement d'une opération (None : à plat)."""
        mode = getattr(op, 'wrap', 'none') or 'none'
        if mode == 'none':
            return None
        return cls(mode, float(getattr(op, 'wrap_radius', 0.0) or 0.0), float(getattr(op, 'wrap_origin', 0.0) or 0.0),
                   float(getattr(op, 'wrap_radius2', 0.0) or 0.0), float(getattr(op, 'wrap_length', 0.0) or 0.0))

    @property
    def cone(self) -> bool:
        return self.mode.startswith('cone')

    def problem(self) -> str:
        """Réglage impossible (texte), ou vide."""
        if self.mode not in MODES:
            return f'enroulement « {self.mode} » inconnu'
        if self.mode == 'surface':
            return ''
        if self.radius <= 0:
            return 'enroulement : rayon de la pièce à indiquer'
        if self.cone and (self.radius2 <= 0 or self.length <= 0):
            return 'enroulement conique : second rayon et longueur entre les deux rayons à indiquer'
        return ''

    def split(self, x: float, y: float) -> tuple[float, float]:
        """(en travers de l'axe, le long de l'axe)."""
        return (x, y) if self.mode.endswith('_y') else (y, x)

    def join(self, u: float, a: float) -> tuple[float, float]:
        return (u, a) if self.mode.endswith('_y') else (a, u)

    def radius_at(self, a: float) -> float:
        if not self.cone:
            return self.radius
        return self.radius + (self.radius2 - self.radius) * a / self.length

    def angle(self, u: float) -> float:
        """Angle (rad) depuis la génératrice du dessus."""
        return (u - self.origin) / self.radius

    def surface(self, x: float, y: float) -> tuple[float, float, float]:
        """Point de la surface sous le point (x, y) du dessin enroulé : (X, Y, Z)."""
        u, a = self.split(x, y)
        t, r = self.angle(u), self.radius_at(a)
        X, Y = self.join(self.origin + r * math.sin(t), a)
        return X, Y, r * math.cos(t) - self.radius


def apply(moves: list[Move], wrap: Wrap, safe_z: float, tol: float = 0.01) -> tuple[list[Move], list[str]]:
    """Parcours enroulé et avertissements ; liste vide si refusé."""
    p = wrap.problem()
    if p:
        return [], [p]
    if not moves:
        return [], []
    if any(m.is_arc for m in moves):
        return [], ['enroulement : parcours avec des arcs (importé) — non pris en charge']
    low = [m for m in moves if m.z < safe_z - 1e-9]
    axial = [wrap.split(m.x, m.y)[1] for m in moves]
    if min(wrap.radius_at(a) for a in axial) <= tol:
        return [], ['enroulement conique : le dessin dépasse la pointe du cône']
    worst = max((abs(wrap.angle(wrap.split(m.x, m.y)[0])) for m in low), default=0.0)
    if math.degrees(worst) > MAX_ANGLE:
        return [], [f'enroulement : le dessin couvre {math.degrees(worst):.0f}° depuis le dessus de la pièce '
                    f'(au plus {MAX_ANGLE:.0f}°) — rien d\'écrit']
    warnings = []
    if math.degrees(worst) > WARN_ANGLE:
        warnings.append(f'enroulement : jusqu\'à {math.degrees(worst):.0f}° depuis le dessus — l\'outil vertical '
                        'attaque la surface en biais, vérifier')
    r_max = max(wrap.radius_at(a) for a in axial)
    top = r_max - wrap.radius if wrap.cone else 0.0          # point le plus haut de la surface (θ = 0)
    step = 2 * math.acos(1 - tol / r_max) if tol < r_max else math.pi / 8
    step = min(step, math.radians(5))

    def mapped(kind, x, y, z, high, fin=False):
        X, Y, zs = wrap.surface(x, y)
        return Move(kind, X, Y, z + top if high else zs + z, fin=fin)

    out = []
    prev = None
    for m in moves:
        high = m.z >= safe_z - 1e-9
        if prev is not None and not (high and prev[3]):
            t0 = wrap.angle(wrap.split(prev[0], prev[1])[0])
            t1 = wrap.angle(wrap.split(m.x, m.y)[0])
            n = math.ceil(abs(t1 - t0) / step - 1e-9)
            for k in range(1, n):
                f = k / n
                x, y, z = (prev[0] + f * (m.x - prev[0]), prev[1] + f * (m.y - prev[1]),
                           prev[2] + f * (m.z - prev[2]))
                out.append(mapped(m.kind, x, y, z, z >= safe_z - 1e-9, m.fin))
        out.append(mapped(m.kind, m.x, m.y, m.z, high, m.fin))
        prev = (m.x, m.y, m.z, high)
    return out, warnings


class SurfaceMap:
    """Hauteur de la surface d'une pièce maillée vue de dessus, dessus de la
    pièce à Z = 0 (comme la finition 3D), lue par interpolation bilinéaire ;
    nan hors de la pièce."""

    def __init__(self, tris, bounds, res: float):
        import numpy as np
        from .advanced import heightmap_from_triangles
        tris = np.asarray(tris, dtype=float)
        self.top = float(tris.reshape(-1, 3)[:, 2].max())
        x0, y0, x1, y1 = bounds
        self.res = max(res, (x1 - x0) / 2000, (y1 - y0) / 2000, 1e-3)
        self.x0, self.y0 = x0 - self.res, y0 - self.res
        self.nx = int(math.ceil((x1 - x0) / self.res)) + 3
        self.ny = int(math.ceil((y1 - y0) / self.res)) + 3
        self.H = heightmap_from_triangles(tris, self.x0, self.y0, self.nx, self.ny, self.res) - self.top

    def z(self, x: float, y: float) -> float:
        fi, fj = (x - self.x0) / self.res, (y - self.y0) / self.res
        i, j = int(math.floor(fi)), int(math.floor(fj))
        if not (0 <= i < self.nx - 1 and 0 <= j < self.ny - 1):
            return math.nan
        c = self.H[j:j + 2, i:i + 2]
        if not all(math.isfinite(v) for v in c.flat):
            return math.nan
        u, v = fi - i, fj - j
        return float((1 - u) * (1 - v) * c[0, 0] + u * (1 - v) * c[0, 1] + (1 - u) * v * c[1, 0] + u * v * c[1, 1])


def project(moves: list[Move], smap: SurfaceMap, safe_z: float, step: float) -> tuple[list[Move], list[str]]:
    """Parcours projeté verticalement sur la surface (projection parallèle) :
    au-dessous du dégagement, Z = surface + profondeur, segments découpés
    au pas `step` ; refus (liste vide) si un point tombe hors de la pièce."""
    if any(m.is_arc for m in moves):
        return [], ['projection : parcours avec des arcs (importé) — non pris en charge']
    out, prev = [], None
    for m in moves:
        high = m.z >= safe_z - 1e-9
        pts = []
        if prev is not None and not (high and prev[3]):
            n = max(1, math.ceil(math.hypot(m.x - prev[0], m.y - prev[1]) / step - 1e-9))
            pts = [(prev[0] + (m.x - prev[0]) * k / n, prev[1] + (m.y - prev[1]) * k / n,
                    prev[2] + (m.z - prev[2]) * k / n) for k in range(1, n)]
        for x, y, z in pts + [(m.x, m.y, m.z)]:
            if z >= safe_z - 1e-9:
                out.append(Move(m.kind, x, y, z, fin=m.fin))
                continue
            zs = smap.z(x, y)
            if not math.isfinite(zs):
                return [], [f'projection : le parcours sort de la pièce (X {x:.2f}, Y {y:.2f}) — rien d\'écrit']
            out.append(Move(m.kind, x, y, zs + z, fin=m.fin))
        prev = (m.x, m.y, m.z, high)
    return out, []


def _guide3d(smap: SurfaceMap, guide, step: float):
    """Courbe guide (points XY) posée sur la surface, redécoupée au pas
    `step` : (points 3D, abscisses curvilignes 3D) ; None si elle sort."""
    pts = [tuple(p[:2]) for p in guide]
    dense = [pts[0]]
    for a, b in zip(pts, pts[1:]):
        n = max(1, int(math.ceil(math.dist(a, b) / step)))
        dense += [(a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n) for k in range(1, n + 1)]
    G = []
    for x, y in dense:
        z = smap.z(x, y)
        if not math.isfinite(z):
            return None
        G.append((x, y, z))
    S = [0.0]
    for a, b in zip(G, G[1:]):
        S.append(S[-1] + math.dist(a, b))
    return G, S


def _normal(smap: SurfaceMap, x: float, y: float):
    h = smap.res
    zx = (smap.z(x + h, y) - smap.z(x - h, y)) / (2 * h)
    zy = (smap.z(x, y + h) - smap.z(x, y - h)) / (2 * h)
    if not (math.isfinite(zx) and math.isfinite(zy)):
        return (0.0, 0.0, 1.0)
    n = math.sqrt(zx * zx + zy * zy + 1)
    return (-zx / n, -zy / n, 1 / n)


def local_project(moves: list[Move], smap: SurfaceMap, guide, safe_z: float, step: float,
                  ref=None) -> tuple[list[Move], list[str]]:
    """Projection locale (TypeEdit) : le dessin à plat est posé le long de la
    courbe guide sur la surface — son point de référence (coin bas-gauche
    des parcours, ou `ref`) au départ de la guide ; l'abscisse devient la
    longueur parcourue SUR la surface le long de la guide, l'ordonnée un
    écart sur la surface, perpendiculaire à la guide (repère : tangente,
    normale de la surface) ; la profondeur est reprise à la verticale (outil
    vertical, machine 3 axes). Refus si le dessin dépasse la guide ou la pièce."""
    if any(m.is_arc for m in moves):
        return [], ['projection locale : parcours avec des arcs (importé) — non pris en charge']
    if not guide or len(guide) < 2:
        return [], ['projection locale : pas de courbe guide (sélectionner la courbe, puis « Projection locale »)']
    g = _guide3d(smap, guide, step)
    if g is None:
        return [], ['projection locale : la courbe guide sort de la pièce — rien d\'écrit']
    G, S = g
    low = [m for m in moves if m.z < safe_z - 1e-9]
    if ref is None:
        ref = (min(m.x for m in low), min(m.y for m in low)) if low else (0.0, 0.0)
    total = S[-1]

    def frame(u):
        import bisect
        i = min(max(0, bisect.bisect_right(S, u) - 1), len(S) - 2)
        t = 0.0 if S[i + 1] <= S[i] else (u - S[i]) / (S[i + 1] - S[i])
        a, b = G[i], G[i + 1]
        P = tuple(a[k] + (b[k] - a[k]) * t for k in range(3))
        T = tuple(b[k] - a[k] for k in range(3))
        tn = math.sqrt(sum(c * c for c in T)) or 1.0
        T = tuple(c / tn for c in T)
        N = _normal(smap, P[0], P[1])
        B = (N[1] * T[2] - N[2] * T[1], N[2] * T[0] - N[0] * T[2], N[0] * T[1] - N[1] * T[0])
        bn = math.sqrt(sum(c * c for c in B)) or 1.0
        return P, tuple(c / bn for c in B)
    out, prev = [], None
    for m in moves:
        high = m.z >= safe_z - 1e-9
        pts = []
        if prev is not None and not (high and prev[3]):
            n = max(1, math.ceil(math.hypot(m.x - prev[0], m.y - prev[1]) / step - 1e-9))
            pts = [(prev[0] + (m.x - prev[0]) * k / n, prev[1] + (m.y - prev[1]) * k / n,
                    prev[2] + (m.z - prev[2]) * k / n) for k in range(1, n)]
        for x, y, z in pts + [(m.x, m.y, m.z)]:
            u, v = x - ref[0], y - ref[1]
            if u < -1e-6 or u > total + 1e-6:
                return [], [f'projection locale : le dessin dépasse la courbe guide ({u:.2f} mm sur {total:.2f}) '
                            '— rien d\'écrit']
            P, B = frame(min(max(u, 0.0), total))
            qx, qy = P[0] + v * B[0], P[1] + v * B[1]
            if z >= safe_z - 1e-9:
                out.append(Move(m.kind, qx, qy, z, fin=m.fin))
                continue
            zs = smap.z(qx, qy)
            if not math.isfinite(zs):
                return [], [f'projection locale : le parcours sort de la pièce (X {qx:.2f}, Y {qy:.2f}) — rien d\'écrit']
            out.append(Move(m.kind, qx, qy, zs + z, fin=m.fin))
        prev = (m.x, m.y, m.z, high)
    return out, [f'projection locale : {total:.2f} mm de courbe guide sur la surface']


def wrap_path(path, wrap: Wrap, tol: float = 0.01):
    """Dessin enroulé vu de dessus (TypeEdit : enroulement cylindrique ou
    conique de l'onglet CAO) : chaque contour aplati, découpé pour suivre la
    courbure, ses points posés par `surface` ; None si le dessin dépasse le
    quart de tour (ou la pointe du cône)."""
    from ..core.geom import Contour, Line, Path
    if wrap.problem():
        return None
    r_max = max(wrap.radius, wrap.radius2 if wrap.cone else 0.0)
    step = min(2 * math.acos(1 - tol / r_max) if tol < r_max else math.pi / 8, math.radians(5))
    out = []
    for c in path.contours:
        pts = c.flatten(tol)
        if len(pts) < 2:
            continue
        dense = [pts[0]]
        for a, b in zip(pts, pts[1:]):
            ta = wrap.angle(wrap.split(*a)[0])
            tb = wrap.angle(wrap.split(*b)[0])
            n = max(1, math.ceil(abs(tb - ta) / step - 1e-9))
            dense += [(a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n) for k in range(1, n + 1)]
        mapped = []
        for x, y in dense:
            u, a = wrap.split(x, y)
            if abs(math.degrees(wrap.angle(u))) > 90.0 or wrap.radius_at(a) <= 0:
                return None
            X, Y, _z = wrap.surface(x, y)
            mapped.append((X, Y))
        segs = [Line(p, q) for p, q in zip(mapped, mapped[1:]) if math.dist(p, q) > 1e-12]
        if segs:
            out.append(Contour(segs, c.closed))
    return Path(out)


def describe(wrap: Wrap) -> str:
    """Rappel pour le programme et la liste des parcours."""
    what = MODES.get(wrap.mode, wrap.mode)
    if wrap.mode == 'surface':
        return 'projeté sur la pièce STEP, dessus de la pièce à Z = 0 — à simuler'
    if wrap.cone:
        dims = f'R {wrap.radius:g} à {wrap.radius2:g} mm sur {wrap.length:g} mm'
    else:
        dims = f'R {wrap.radius:g} mm'
    return (f'enroulé : {what.lower()}, {dims}, dessus de la pièce en {"X" if wrap.mode.endswith("_y") else "Y"} = '
            f'{wrap.origin:g} (Z = 0) — à simuler')
