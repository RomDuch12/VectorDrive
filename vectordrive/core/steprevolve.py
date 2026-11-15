"""Une pièce de révolution STEP en vraies faces tirée d'un demi-profil fermé
du dessin (« Pièce du dessin », forme tournée ; onglet Design STEP).

Le profil (mm, Y vers le haut) tourne autour d'un axe : un trait droit
choisi avec lui (contour ouvert d'une seule droite), sinon la verticale par
son point le plus à gauche. Dans la pièce, l'axe est Z (vers le haut du
trait, ou vers sa droite s'il est horizontal), le bas du profil à Z = 0.

- une droite du profil donne un cylindre, un cône ou un plan (disque,
  couronne) ;
- un arc centré sur l'axe donne une sphère ; les autres arcs et les courbes
  sont ramenés à des cônes, à `TOL` près ;
- une pointe sur l'axe est arrêtée à `TIP` de l'axe (le noyau ne fait pas
  de cercle de rayon nul).

Chaque contour fermé est une pièce. Un profil qui passe de l'autre côté de
l'axe, qui se recoupe, deux profils qui se touchent ou l'un dans l'autre
(un vide fermé) : refusés (`stepdraw.DrawError`).
"""
from __future__ import annotations

import math

from . import brep as B
from . import stepdraw as SD
from .geom import Line

TOL = SD.TOL
#: rayon (mm) gardé au bout d'une pointe sur l'axe
TIP = 0.05
#: sous ce rayon (mm), un point est sur l'axe
ON_AXIS = 1e-6
#: sous ce rayon (mm), un sommet du dessin est ramené sur l'axe
SNAP = TOL


def _axis_line(c) -> tuple | None:
    """(origine, direction unitaire) d'un contour ouvert fait de droites alignées, sinon None."""
    if c.closed or not c.segments or not all(isinstance(s, Line) for s in c.segments):
        return None
    a, b = c.segments[0].start, c.segments[-1].end
    L = math.dist(a, b)
    if L < 1e-6:
        return None
    u = ((b[0] - a[0]) / L, (b[1] - a[1]) / L)
    for s in c.segments:
        for p in (s.start, s.end):
            if abs((p[0] - a[0]) * u[1] - (p[1] - a[1]) * u[0]) > 1e-6:
                return None
    if u[1] < -1e-9 or (abs(u[1]) <= 1e-9 and u[0] < 0):     # vers le haut, ou vers la droite
        u = (-u[0], -u[1])
    return (float(a[0]), float(a[1])), u


def parse(path, tol: float = TOL) -> tuple:
    """(boucles fermées, axe (origine, direction) ou None, contours ouverts laissés)."""
    lps, left = SD.loops(path, tol)
    axes = [ax for c in path.contours if (ax := _axis_line(c)) is not None]
    if len(axes) > 1:
        raise SD.DrawError('plusieurs traits droits : un seul, pour l\'axe')
    return lps, (axes[0] if axes else None), left - len(axes)


def _plane_loop(lp):
    """(points, bulges) d'une boucle du dessin ; un cercle : quatre quarts."""
    if isinstance(lp, B.Circle):
        pts = [(lp.cx + lp.r * math.cos(a), lp.cy + lp.r * math.sin(a)) for a in (0, math.pi / 2, math.pi, 1.5 * math.pi)]
        return pts, [math.tan(math.pi / 8)] * 4
    return list(lp.pts), list(lp.bulges or [0.0] * len(lp.pts))


def _left(pts: list, bulges: list) -> float:
    """Abscisse du point le plus à gauche de la boucle, arcs compris."""
    x = min(p[0] for p in pts)
    for sg in B._segments(B.Poly(pts, bulges), 0.0, 0.0, 1.0):
        if sg[0] == 'arc':
            _k, c, R, a0, a1, _s = sg
            lo, hi = sorted((a0, a1))
            if any(lo <= math.pi + k * B.TWO_PI <= hi for k in (-2, -1, 0, 1)):
                x = min(x, c[0] - R)
    return x


def _edges(pts: list, bulges: list, tol: float) -> list:
    """Arêtes du profil (r, z) : ('line', p, q) ou ('sphere', p, q, zc, R) pour un arc centré sur l'axe ; les
    autres arcs en cordes à `tol` près."""
    out = []
    for sg in B._segments(B.Poly(pts, bulges), 0.0, 0.0, 1.0):
        if sg[0] == 'line':
            out.append(('line', sg[1], sg[2]))
            continue
        _k, c, R, a0, a1, _s = sg
        p = (c[0] + R * math.cos(a0), c[1] + R * math.sin(a0))
        q = (c[0] + R * math.cos(a1), c[1] + R * math.sin(a1))
        if abs(c[0]) <= ON_AXIS:
            out.append(('sphere', p, q, c[1], R))
            continue
        lo, hi = sorted((a0, a1))
        if abs(c[0] - R) <= SNAP and any(lo - 1e-9 <= math.pi + k * B.TWO_PI <= hi + 1e-9 for k in (-2, -1, 0, 1)):
            raise SD.DrawError('arc tangent à l\'axe : le finir sur l\'axe par un trait, ou l\'en écarter')
        n = 1 if R <= tol else max(1, math.ceil(abs(a1 - a0) / (2 * math.acos(1 - tol / R))))
        ring = [p] + [(c[0] + R * math.cos(a0 + (a1 - a0) * i / n), c[1] + R * math.sin(a0 + (a1 - a0) * i / n))
                      for i in range(1, n)] + [q]
        out += [('line', a, b) for a, b in zip(ring, ring[1:])]
    return out


def _snap(e):
    """Rayons négligeables ramenés à 0 (sur l'axe)."""
    fix = lambda p: (0.0 if abs(p[0]) <= SNAP else p[0], p[1])        # noqa: E731
    return (e[0], fix(e[1]), fix(e[2])) + tuple(e[3:])


def _same_carrier(e, f) -> bool:
    """Deux arêtes qui se suivent sur la même droite ou la même sphère."""
    if e[0] != f[0]:
        return False
    if e[0] == 'sphere':
        return abs(e[3] - f[3]) < 1e-9 and abs(e[4] - f[4]) < 1e-9
    (x0, y0), (x1, y1), (x2, y2) = e[1], e[2], f[2]
    cross = (x1 - x0) * (y2 - y1) - (y1 - y0) * (x2 - x1)
    return abs(cross) <= 1e-9 * max(1.0, math.dist(e[1], e[2]) * math.dist(f[1], f[2])) \
        and (x1 - x0) * (x2 - x1) + (y1 - y0) * (y2 - y1) > 0


def _merge(edges: list) -> list:
    out = []
    for e in edges:
        if out and _same_carrier(out[-1], e):
            out[-1] = (e[0], out[-1][1], e[2]) + tuple(e[3:])
        else:
            out.append(e)
    while len(out) > 2 and _same_carrier(out[-1], out[0]):
        out[0] = (out[0][0], out[-1][1], out[0][2]) + tuple(out[0][3:])
        out.pop()
    return out


def _axis(e) -> bool:
    return e[0] == 'line' and e[1][0] == 0.0 and e[2][0] == 0.0


def _flat(e) -> bool:
    return abs(e[2][1] - e[1][1]) <= 1e-9


def _cut_at_tip(e, apex_first: bool):
    """Le point de l'arête où le rayon vaut TIP, depuis la pointe sur l'axe."""
    apex, far = (e[1], e[2]) if apex_first else (e[2], e[1])
    if e[0] == 'sphere':
        zc, R = e[3], e[4]
        if R <= 2 * TIP:
            raise SD.DrawError(f'sphère de moins de {2 * TIP:g} mm sur l\'axe')
        return (TIP, zc + math.copysign(math.sqrt(R * R - TIP * TIP), apex[1] - zc))
    if far[0] <= 2 * TIP:
        raise SD.DrawError(f'pointe plus courte que {2 * TIP:g} mm sur l\'axe (un arc tangent à l\'axe : l\'en écarter)')
    t = TIP / far[0]
    return (TIP, apex[1] + (far[1] - apex[1]) * t)


def _tips(edges: list) -> list:
    """Les pointes sur l'axe arrêtées à TIP : un petit disque au bout (le cône, la sphère gardés)."""
    n = len(edges)
    out = list(edges)
    for i in range(n):
        a, b = out[i], out[(i + 1) % n]                     # se rejoignent en a[2] == b[1]
        if a[2][0] != 0.0 or (_axis(a) and _axis(b)):
            continue
        if _axis(a) and not _flat(b):                       # l'axe monte (ou descend) jusqu'à la pointe de b
            t = _cut_at_tip(b, True)
            out[i] = ('line', a[1], (0.0, t[1]))
            out[(i + 1) % n] = (b[0], t, b[2]) + tuple(b[3:])
            out.insert(i + 1, ('line', (0.0, t[1]), t))
            return _tips(out)
        if _axis(b) and not _flat(a):
            t = _cut_at_tip(a, False)
            out[i] = (a[0], a[1], t) + tuple(a[3:])
            out[(i + 1) % n] = ('line', (0.0, t[1]), b[2])
            out.insert(i + 1, ('line', t, (0.0, t[1])))
            return _tips(out)
        if not _axis(a) and not _axis(b) and not (_flat(a) or _flat(b)):
            raise SD.DrawError('profil pincé sur l\'axe : deux pièces jointes en un point')
        if _flat(a) and not _axis(b):                       # creux en pointe sur un disque : trou de TIP
            v, t = (TIP, a[2][1]), _cut_at_tip(b, True)
            out[i] = (a[0], a[1], v) + tuple(a[3:])
            out[(i + 1) % n] = (b[0], t, b[2]) + tuple(b[3:])
            out.insert(i + 1, ('line', v, t))
            return _tips(out)
        if _flat(b) and not _axis(a):
            v, t = (TIP, b[1][1]), _cut_at_tip(a, False)
            out[i] = (a[0], a[1], t) + tuple(a[3:])
            out[(i + 1) % n] = (b[0], v, b[2]) + tuple(b[3:])
            out.insert(i + 1, ('line', t, v))
            return _tips(out)
    return out


def _edges_at(e, h: float, from_end: bool):
    """Le point de la droite `e` à la hauteur h (en valeur absolue) de son bout `from_end`."""
    v, far = (e[2], e[1]) if from_end else (e[1], e[2])
    t = h / abs(far[1] - v[1])
    return (v[0] + (far[0] - v[0]) * t, v[1] + (far[1] - v[1]) * t)


def _extrema(edges: list) -> list:
    """Une arête vive tout en bas ou tout en haut (deux parois qui partent du même cercle, tore, couteau) :
    coupée d'un petit plat de TIP de large (le noyau ne fait pas deux cercles confondus), à la hauteur où les
    parois sont écartées de TIP — la pièce n'en est raccourcie que d'autant."""
    n = len(edges)
    for i in range(n):
        a, b = edges[i], edges[(i + 1) % n]
        v = a[2]
        if v[0] == 0.0 or _flat(a) or _flat(b) or (a[1][1] - v[1]) * (b[2][1] - v[1]) <= 0:
            continue
        if a[0] != 'line' or b[0] != 'line':
            raise SD.DrawError('arête vive entre une sphère et une paroi tout en haut ou tout en bas : '
                               'y dessiner un petit plat')
        ka, kb = ((e[2][0] - e[1][0]) / (e[2][1] - e[1][1]) for e in (a, b))      # dr/dz des deux parois
        h = min(max(TIP / max(abs(ka - kb), 1e-12), TIP / 5), abs(a[1][1] - v[1]) / 2, abs(b[2][1] - v[1]) / 2)
        pa, pb = _edges_at(a, h, True), _edges_at(b, h, False)
        if abs(pa[0] - pb[0]) < TIP / 2:
            raise SD.DrawError('arête vive trop fine en haut ou en bas du profil')
        out = list(edges)
        out[i] = ('line', a[1], pa)
        out[(i + 1) % n] = ('line', pb, b[2])
        out.insert(i + 1, ('line', pa, pb))
        return _extrema(out)
    return edges


def _ring(edges: list) -> list:
    """Points du profil pour les contrôles (sphères en cordes fines)."""
    pts = []
    for e in edges:
        pts.append(e[1])
        if e[0] == 'sphere':
            zc, R = e[3], e[4]
            u0 = math.atan2(e[1][1] - zc, e[1][0])
            u1 = math.atan2(e[2][1] - zc, e[2][0])
            k = max(2, int(abs(u1 - u0) * 64))
            pts += [(R * math.cos(u0 + (u1 - u0) * i / k), zc + R * math.sin(u0 + (u1 - u0) * i / k)) for i in range(1, k)]
    return pts


def _radius(e, z: float) -> float:
    if e[0] == 'sphere':
        return math.sqrt(max(0.0, e[4] ** 2 - (z - e[3]) ** 2))
    (r0, z0), (r1, z1) = e[1], e[2]
    return r0 + (r1 - r0) * (z - z0) / (z1 - z0)


def _slabs(edges: list, dz: float) -> list:
    """Tranches entre les cotes des sommets : chaque arête qui traverse la tranche y est un cercle (cylindre,
    cône ou zone de sphère) ; l'axe n'en donne pas."""
    zs = sorted({round(e[1][1], 9) for e in edges} | {round(e[3], 9) for e in edges if e[0] == 'sphere'
                                                       and min(e[1][1], e[2][1]) < e[3] < max(e[1][1], e[2][1])})
    levels = [zs[0]]
    for z in zs[1:]:
        if z - levels[-1] > 1e-7:
            levels.append(z)
    slabs = []
    for za, zb in zip(levels, levels[1:]):
        loops = []
        for e in edges:
            lo, hi = sorted((e[1][1], e[2][1]))
            if _axis(e) or _flat(e) or lo > za + 1e-7 or hi < zb - 1e-7:
                continue
            ra, rb = _radius(e, za), _radius(e, zb)
            if e[0] == 'sphere':
                loops.append(B.Circle(0.0, 0.0, ra, sphere=(e[3] - dz, e[4])))
            else:
                loops.append(B.Circle(0.0, 0.0, ra, None if abs(rb - ra) < B.EPS else rb))
        if loops:
            slabs.append(B.Slab(za - dz, zb - dz, loops))
    return slabs


def _samples(pts: list, bulges: list) -> list:
    """Sommets et milieux des arcs de la boucle : de quel côté de l'axe elle est."""
    out = list(pts)
    for sg in B._segments(B.Poly(pts, bulges), 0.0, 0.0, 1.0):
        if sg[0] == 'arc':
            _k, c, R, a0, a1, _s = sg
            out.append((c[0] + R * math.cos((a0 + a1) / 2), c[1] + R * math.sin((a0 + a1) / 2)))
    return out


def profiles(path, tol: float = TOL) -> tuple:
    """(arêtes (r, z) de chaque profil, d'où vient l'axe : 'trait' ou 'gauche', ouverts laissés)."""
    lps, axis, left = parse(path, tol)
    if not lps:
        raise SD.DrawError('aucun contour fermé')
    plane = [_plane_loop(lp) for lp in lps]
    if axis is None:
        o, u = (min(_left(pts, bl) for pts, bl in plane), 0.0), (0.0, 1.0)
    else:
        o, u = axis
    n = (u[1], -u[0])
    rs = [(x - o[0]) * n[0] + (y - o[1]) * n[1] for pts, bl in plane for x, y in _samples(pts, bl)]
    if max(rs) <= ON_AXIS:                                  # tout à gauche de l'axe : on le regarde de l'autre côté
        n = (-n[0], -n[1])
    det = n[0] * u[1] - n[1] * u[0]
    out = []
    for pts, bl in plane:
        rz = [((x - o[0]) * n[0] + (y - o[1]) * n[1], (x - o[0]) * u[0] + (y - o[1]) * u[1]) for x, y in pts]
        es = [_snap(e) for e in _edges(rz, [b * det for b in bl], tol)]
        if min(min(e[1][0], e[2][0]) for e in es) < -ON_AXIS or \
                any(e[0] == 'line' and e[1][0] * e[2][0] < 0 for e in es):
            raise SD.DrawError('profil des deux côtés de l\'axe : le dessiner d\'un seul côté')
        es = _merge(es)
        if sum(map(_axis, es)) > 1:
            raise SD.DrawError('profil qui touche l\'axe en plusieurs traits : un vide fermé dans la pièce')
        out.append(_extrema(_tips(es)))
    return out, ('trait' if axis is not None else 'gauche'), left


def bodies(path, name: str = 'piece', tol: float = TOL) -> list:
    """Les pièces de révolution, une par contour fermé de `path` ; DrawError si impossible."""
    from shapely.geometry import LinearRing, Polygon
    profs, _axis_from, _left = profiles(path, tol)
    polys = []
    for es in profs:
        pts = _ring(es)
        if len(pts) < 3 or abs(B._area(pts)) <= B.EPS or not LinearRing(pts).is_simple:
            raise SD.DrawError('profil qui se recoupe ou sans surface')
        polys.append(Polygon(pts))
    for i, p in enumerate(polys):
        for q in polys[i + 1:]:
            if p.intersects(q):
                raise SD.DrawError('profils qui se touchent, ou l\'un dans l\'autre (un vide fermé dans la pièce)')
    dz = round(min(min(e[1][1] for e in es) for es in profs), 9)
    order = sorted(range(len(profs)), key=lambda i: (polys[i].bounds[1], polys[i].bounds[0]))
    out = []
    for k, i in enumerate(order):
        b = B.Body(name if len(profs) == 1 else f'{name}_{k + 1}', _slabs(profs[i], dz))
        try:
            B.check(b)
        except B.BrepError as ex:
            raise SD.DrawError(str(ex).split(' : ', 1)[-1]) from None
        out.append(b)
    return out


def summary(path, tol: float = TOL) -> dict:
    """Profils, axe (« trait » choisi ou bord « gauche »), contours ouverts laissés, Ø maxi et hauteur."""
    profs, axis_from, left = profiles(path, tol)
    rmax = max(max(e[1][0], e[2][0], e[4] if e[0] == 'sphere' and min(e[1][1], e[2][1]) <= e[3] <= max(e[1][1], e[2][1])
                   else 0.0) for es in profs for e in es)
    zs = [e[1][1] for es in profs for e in es]
    return {'profiles': len(profs), 'axis': axis_from, 'open': left, 'diameter': 2 * rmax, 'height': max(zs) - min(zs)}
