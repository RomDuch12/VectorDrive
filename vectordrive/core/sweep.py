"""Balayage de courbes (TypeEdit ▸ TypeArt ▸ Balayage), en carte de hauteurs :

* **balayage simple** (cadres, moulures) : le profil est posé par son
  point gauche sur le chemin fermé et balayé tout le long, à l'intérieur
  du chemin s'il tourne dans le sens trigonométrique, à l'extérieur s'il
  tourne dans le sens horaire (comme TypeEdit ; ou côté imposé) ; coins
  aigus, chanfreinés ou arrondis ;
* **tube** : le profil, posé par le milieu du bas de son cadre, suit le
  chemin (ouvert ou fermé) des deux côtés — sa moitié gauche à gauche du
  chemin, sa moitié droite à droite ;
* **entre deux chemins** : le profil est tendu, à chaque station, du
  premier chemin au second (son point gauche sur le premier) ; avec un
  second profil, la section passe peu à peu de l'un à l'autre (morphing) ;
  hauteur gardée, ou proportionnelle à l'écart des chemins.

Le profil est une courbe dessinée de profil : abscisse = distance au
chemin, ordonnée = hauteur (depuis le bas du profil). Sa hauteur en x est
le haut de la courbe à cet endroit (enveloppe supérieure).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from . import galbe as GB

KINDS = (('simple', 'Balayage simple'), ('tube', 'Tube'), ('deux_chemins', 'Entre deux chemins'))
CORNERS = (('aigu', 'Aigus'), ('chanfrein', 'Chanfreinés'), ('arrondi', 'Arrondis'))
SIDES = (('auto', 'Selon le sens du chemin'), ('interieur', 'Intérieur'), ('exterieur', 'Extérieur'))


@dataclass
class SweepSpec:
    kind: str = 'simple'
    corners: str = 'aigu'
    side: str = 'auto'
    scale_z: float = 1.0            # hauteur du profil × (compression)
    resolution: float = 0.1
    margin: float = 1.0
    mode: str = 'ajouter'
    limit: bool = False
    proportional: bool = False      # entre deux chemins : hauteur × écart local / largeur du profil


def envelope(points, xs):
    """Haut de la courbe (polyligne `points`) au-dessus de chaque x de `xs`
    (numpy) ; nan hors de la courbe."""
    import numpy as np
    xs = np.asarray(xs, float)
    out = np.full(xs.shape, np.nan)
    P = list(points)
    for (ax, ay), (bx, by) in zip(P, P[1:]):
        lo, hi = min(ax, bx), max(ax, bx)
        m = (xs >= lo) & (xs <= hi)
        if not m.any():
            continue
        if abs(bx - ax) < 1e-12:
            y = np.full(int(m.sum()), max(ay, by))
        else:
            y = ay + (xs[m] - ax) * (by - ay) / (bx - ax)
        out[m] = np.fmax(out[m], y)
    return out


def profile_table(points, step: float):
    """(x, h) du profil : x depuis son point le plus à gauche, h depuis son
    bas ; pas `step`."""
    import numpy as np
    P = np.asarray(points, float)
    x0, y0 = float(P[:, 0].min()), float(P[:, 1].min())
    w = float(P[:, 0].max()) - x0
    n = max(2, int(math.ceil(w / max(1e-6, step))) + 1)
    xs = np.linspace(x0, x0 + w, n)
    h = envelope([(x, y) for x, y in P], xs) - y0
    h = np.where(np.isnan(h), 0.0, h)
    return xs - x0, h


def _join(corners: str) -> str:
    return {'aigu': 'mitre', 'chanfrein': 'bevel'}.get(corners, 'round')


def _levels(base, xs, ys, idx, width: float, step: float, join: str, outward: bool):
    """Distance « par décalages » des points idx à `base` : premier niveau
    de décalage (onglet, biseau) qui les atteint, au milieu de la tranche ;
    nan au-delà de `width`."""
    import numpy as np
    import shapely
    n = max(2, min(200, int(math.ceil(width / max(step, 1e-6)))))
    dl = width / n
    todo = np.arange(idx.size)
    out = np.full(idx.size, np.nan)
    for i in range(1, n + 1):
        if not todo.size:
            break
        lv = i * dl
        off = base.buffer(lv if outward else -lv, join_style=join, mitre_limit=50.0)
        gx, gy = xs[idx[todo]], ys[idx[todo]]
        if off.is_empty:
            hit = np.ones(todo.size, bool)
        elif outward:
            hit = shapely.contains_xy(off, gx, gy)
        else:
            hit = ~shapely.contains_xy(off, gx, gy)
        out[todo[hit]] = lv - dl / 2
        todo = todo[~hit]
    return out, dl


def simple_distance(path_poly, X, Y, side: str, corners: str, width: float, step: float):
    """Distance au chemin (polygone shapely) du côté du balayage, selon le
    type de coins ; nan de l'autre côté ou au-delà de `width`.

    À l'extérieur : décalages du chemin vers l'extérieur (coins aigus en
    onglet, chanfreinés en biseau, arrondis : distance exacte). À
    l'intérieur, les coins du cadre se forment côté intérieur : aigus par
    décalages vers l'intérieur ; chanfreinés ou arrondis autour du « cœur »
    (le chemin rentré de toute la largeur du profil)."""
    import numpy as np
    import shapely
    xs, ys = X.ravel(), Y.ravel()
    inside = shapely.contains_xy(path_poly, xs, ys)
    want_inside = side == 'interieur'
    idx = np.flatnonzero(inside if want_inside else ~inside)
    d = np.full(xs.size, np.nan)
    exact = shapely.distance(shapely.points(xs[idx], ys[idx]), path_poly.exterior)
    near = exact <= width * (1.0 if corners == 'arrondi' and not want_inside else 50.0)
    idx, exact = idx[near], exact[near]
    if not want_inside:
        if corners == 'arrondi':
            d[idx] = exact
        else:
            lv, dl = _levels(path_poly, xs, ys, idx, width, step, _join(corners), True)
            # sur les côtés droits, la distance exacte (sans marches)
            d[idx] = np.where(np.isnan(lv), np.nan, np.where(np.abs(lv - exact) <= dl, exact, lv))
    elif corners == 'aigu':
        lv, dl = _levels(path_poly, xs, ys, idx, width, step, 'mitre', False)
        d[idx] = np.where(np.isnan(lv), np.nan, np.where(np.abs(lv - exact) <= dl, exact, lv))
    else:
        core = path_poly.buffer(-width, join_style='mitre', mitre_limit=50.0)
        if core.is_empty:
            d[idx] = exact
        else:
            in_core = shapely.contains_xy(core, xs[idx], ys[idx])
            if corners == 'arrondi':
                to_core = shapely.distance(shapely.points(xs[idx], ys[idx]), core)
            else:
                to_core, _dl = _levels(core, xs, ys, idx, width, step, 'bevel', True)
            dd = width - to_core
            d[idx] = np.where(in_core | (dd < 0), np.nan, dd)
    d[d > width] = np.nan
    return d.reshape(X.shape)


def tube_distance(line, X, Y):
    """(distance au chemin, côté : +1 à gauche du sens de parcours, −1 à droite)."""
    import numpy as np
    import shapely
    pts = shapely.points(X.ravel(), Y.ravel())
    d = shapely.distance(pts, line)
    t = shapely.line_locate_point(line, pts)
    L = line.length
    a = shapely.line_interpolate_point(line, np.clip(t - 1e-3, 0, L))
    b = shapely.line_interpolate_point(line, np.clip(t + 1e-3, 0, L))
    ax, ay = shapely.get_x(a), shapely.get_y(a)
    bx, by = shapely.get_x(b), shapely.get_y(b)
    cross = (bx - ax) * (Y.ravel() - ay) - (by - ay) * (X.ravel() - ax)
    return d.reshape(X.shape), np.where(cross >= 0, 1.0, -1.0).reshape(X.shape)


def _stations(pts, closed: bool, n: int):
    """n points répartis à abscisse curviligne égale (fermé : retour au départ)."""
    import numpy as np
    P = np.asarray(list(pts) + ([pts[0]] if closed else []), float)
    d = np.concatenate([[0.0], np.cumsum(np.hypot(*np.diff(P, axis=0).T))])
    t = np.linspace(0.0, d[-1], n)
    return np.column_stack([np.interp(t, d, P[:, 0]), np.interp(t, d, P[:, 1])])


def _match_rails(a, b, closed: bool):
    """Second chemin mis dans le sens du premier (et, fermé, départ au plus
    près du départ du premier) : sans quoi la surface se noue."""
    import math as _m
    a, b = list(a), list(b)
    if closed:
        def area(p):
            return sum(p[i][0] * p[(i + 1) % len(p)][1] - p[(i + 1) % len(p)][0] * p[i][1] for i in range(len(p)))
        if (area(a) > 0) != (area(b) > 0):
            b = b[::-1]
        k = min(range(len(b)), key=lambda i: _m.dist(b[i], a[0]))
        return a, b[k:] + b[:k]
    if _m.dist(a[0], b[0]) + _m.dist(a[-1], b[-1]) > _m.dist(a[0], b[-1]) + _m.dist(a[-1], b[0]):
        b = b[::-1]
    return a, b


def two_rails_field(A, B, prof1, prof2=None, proportional: bool = False):
    """field(X, Y) du balayage entre les chemins échantillonnés A et B (n × 2,
    mêmes stations) : chaque quadrilatère A_i A_i+1 B_i+1 B_i inversé en
    (u, v) bilinéaire ; v = position sur la section (0 sur A, 1 sur B)."""
    import numpy as np
    px1, ph1 = prof1
    W1 = float(px1[-1]) or 1.0
    if prof2 is not None:
        px2, ph2 = prof2
        W2 = float(px2[-1]) or 1.0
    n = len(A)

    def height(v, t, width):
        h = np.interp(v * W1, px1, ph1)
        if prof2 is not None:
            h = (1 - t) * h + t * np.interp(v * W2, px2, ph2)
        if proportional:
            h = h * width / (W1 if prof2 is None else (1 - t) * W1 + t * W2)
        return h

    def field(X, Y):
        H = np.zeros(X.shape)
        ok = np.zeros(X.shape, bool)
        xs, ys = X[0], Y[:, 0]
        res_x = abs(xs[1] - xs[0]) if len(xs) > 1 else 1.0
        res_y = abs(ys[1] - ys[0]) if len(ys) > 1 else 1.0
        for i in range(n - 1):
            a, b, c, d = A[i], A[i + 1], B[i + 1], B[i]
            q = np.array([a, b, c, d])
            lo, hi = q.min(axis=0), q.max(axis=0)
            ii = np.nonzero((xs >= lo[0] - res_x) & (xs <= hi[0] + res_x))[0]
            jj = np.nonzero((ys >= lo[1] - res_y) & (ys <= hi[1] + res_y))[0]
            if not len(ii) or not len(jj):
                continue
            sx, sy = np.meshgrid(xs[ii], ys[jj])
            e, f, g = b - a, d - a, a - b + c - d
            hx, hy = sx - a[0], sy - a[1]
            k2 = g[0] * f[1] - g[1] * f[0]
            k1 = (e[0] * f[1] - e[1] * f[0]) + (hx * g[1] - hy * g[0])
            k0 = hx * e[1] - hy * e[0]
            with np.errstate(all='ignore'):
                if abs(k2) < 1e-12:
                    vs = [-k0 / k1]
                else:
                    w = np.sqrt(np.where(k1 * k1 - 4 * k0 * k2 >= 0, k1 * k1 - 4 * k0 * k2, np.nan))
                    vs = [(-k1 - w) / (2 * k2), (-k1 + w) / (2 * k2)]
                for v in vs:
                    dx, dy = e[0] + g[0] * v, e[1] + g[1] * v
                    u = np.where(np.abs(dx) >= np.abs(dy), (hx - f[0] * v) / dx, (hy - f[1] * v) / dy)
                    m = (u >= -1e-9) & (u <= 1 + 1e-9) & (v >= -1e-9) & (v <= 1 + 1e-9)
                    if not m.any():
                        continue
                    t = (i + np.clip(u, 0, 1)) / (n - 1)
                    pa = a + np.multiply.outer(np.clip(u, 0, 1), e)
                    pb = d + np.multiply.outer(np.clip(u, 0, 1), c - d)
                    width = np.hypot(*(pb - pa).transpose(2, 0, 1))
                    hv = np.where(m, height(np.clip(v, 0, 1), t, width), 0.0)
                    sub_h = H[np.ix_(jj, ii)]
                    sub_ok = ok[np.ix_(jj, ii)]
                    H[np.ix_(jj, ii)] = np.where(m & (~sub_ok | (hv > sub_h)), hv, sub_h)
                    ok[np.ix_(jj, ii)] = sub_ok | m
        return H, ok
    return field


def sweep_two(rail_a, rail_b, closed: bool, profile_pts, spec: SweepSpec, tool: int = 0, onto=None,
              profile2_pts=None):
    """Image du balayage du profil (ou de deux profils) entre deux chemins."""
    import numpy as np
    from .typeart import _apply
    step = max(0.005, spec.resolution / 2)
    px, ph = profile_table(profile_pts, step)
    prof2 = None
    if profile2_pts is not None:
        px2, ph2 = profile_table(profile2_pts, step)
        prof2 = (px2, ph2 * spec.scale_z)
    if float(px[-1]) <= 0 or len(rail_a) < 2 or len(rail_b) < 2:
        return None
    a, b = _match_rails(rail_a, rail_b, closed)
    La = sum(math.dist(p, q) for p, q in zip(a, a[1:]))
    Lb = sum(math.dist(p, q) for p, q in zip(b, b[1:]))
    n = int(min(4000, max(8, math.ceil(max(La, Lb) / max(0.05, spec.resolution)))))
    A, B = _stations(a, closed, n), _stations(b, closed, n)
    field = two_rails_field(A, B, (px, ph * spec.scale_z), prof2, spec.proportional)
    allp = np.vstack([A, B])
    lo, hi = allp.min(axis=0), allp.max(axis=0)
    return _apply((float(lo[0]), float(lo[1]), float(hi[0]), float(hi[1])), spec, field, tool, onto,
                  'Balayage entre deux chemins')


def sweep(path_pts, closed: bool, profile_pts, spec: SweepSpec, tool: int = 0, onto=None):
    """Image du balayage du profil le long du chemin."""
    import numpy as np
    import shapely
    from .typeart import _apply
    from .geom import Contour, polyline
    px, ph = profile_table(profile_pts, max(0.005, spec.resolution / 2))
    ph = ph * spec.scale_z
    W = float(px[-1])
    if W <= 0 or len(path_pts) < 2:
        return None
    if spec.kind == 'simple':
        if not closed or len(path_pts) < 3:
            raise ValueError('le balayage simple demande un chemin fermé')
        poly = shapely.Polygon(path_pts)
        if not poly.is_valid:
            poly = poly.buffer(0)
        side = spec.side
        if side == 'auto':
            ccw = Contour(polyline(path_pts, closed=True).segments, True).signed_area() > 0
            side = 'interieur' if ccw else 'exterieur'
        b = poly.bounds
        bounds = b if side == 'interieur' else (b[0] - W, b[1] - W, b[2] + W, b[3] + W)

        def field(X, Y):
            d = simple_distance(poly, X, Y, side, spec.corners, W, spec.resolution)
            ok = ~np.isnan(d)
            return np.where(ok, np.interp(np.nan_to_num(d), px, ph), 0.0), ok
        return _apply(bounds, spec, field, tool, onto, 'Balayage')
    line = shapely.LineString(list(path_pts) + ([path_pts[0]] if closed else []))
    mid = W / 2
    b = line.bounds

    def field(X, Y):
        d, s = tube_distance(line, X, Y)
        x = mid - s * d                                   # à gauche du chemin : moitié gauche du profil
        ok = (x >= 0) & (x <= W)
        return np.where(ok, np.interp(np.clip(x, 0, W), px, ph), 0.0), ok
    return _apply((b[0] - mid, b[1] - mid, b[2] + mid, b[3] + mid), spec, field, tool, onto, 'Tube')
