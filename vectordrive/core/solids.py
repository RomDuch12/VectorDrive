"""Volumes 3D (modélisation solide) : primitives, extrusion (avec
dépouille), révolution, booléens, propriétés de masse.

Chaque volume est un maillage fermé (sommets, triangles) ; les opérations
passent par Manifold (`manifold3d`, Apache-2.0), qui garantit des maillages
étanches et des booléens robustes. Sans `manifold3d`, `available()` est
faux et les opérations lèvent SolidError (le reste de VectorDrive marche).

Repère : celui du dessin (mm), Z vers le haut, Z = 0 sur le plan du dessin.

Ressort et filetage ISO modélisé : portés de SolidCraft (MIT OR Apache-2.0,
© 2026 SolidCraft contributors, utilisé sous MIT) — `crates/doc/src/eval.rs`
(Coil, `thread_groove`, `ISO_COARSE`, `thread_for`) et
`crates/kernel/src/helix.rs` (`sweep_helix_mesh`) ; de même les perçages
(`hole_tools_and_prisms`), le tube (Pipe), le volume englobant
(BoundingSolid), la nervure (Rib, Web), le bossage (Boss,
`crates/doc/src/eval_more.rs`), le relief enroulé sur un cylindre
(Emboss, `crates/kernel/src/emboss.rs`), les profilés (FrameMember,
`crates/doc/src/frame.rs`), les pièces plastiques (Lip, SnapFit, Rest,
`crates/doc/src/eval_more.rs`), la tôlerie avec ses développés
(SheetContour, SheetBase, SheetFlange, SheetFold, SheetUnfold,
`crates/doc/src/sheet.rs`),
l'échelle par axe (Scale) et les cellules (BoundaryFill,
`crates/doc/src/eval.rs`).
"""
from __future__ import annotations

import base64
import io
import math
import uuid
from dataclasses import dataclass, field

import numpy as np

#: couleur des volumes sans couleur (aluminium, comme les modèles 3D)
ALU = (0.70, 0.74, 0.80)

#: facettes d'un tour complet (cercles, sphères, révolutions)
SEGMENTS = 96


class SolidError(ValueError):
    pass


def _m():
    try:
        import manifold3d
    except ImportError as ex:                            # pragma: no cover — installé avec VectorDrive
        raise SolidError('module manifold3d absent : volumes 3D indisponibles') from ex
    return manifold3d


def available() -> bool:
    try:
        _m()
    except SolidError:
        return False
    return True


@dataclass
class Solid:
    verts: np.ndarray                                    # (n, 3) mm
    tris: np.ndarray                                     # (m, 3) indices
    name: str = ''
    color: tuple = ALU
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    visible: bool = True

    # --- Manifold -------------------------------------------------------------------
    def manifold(self):
        M = _m()
        mesh = M.Mesh(vert_properties=np.asarray(self.verts, dtype=np.float32),
                      tri_verts=np.asarray(self.tris, dtype=np.uint32))
        man = M.Manifold(mesh)
        if man.status() != M.Error.NoError:
            raise SolidError(f'maillage non fermé : {man.status()}')
        return man

    @classmethod
    def from_manifold(cls, man, name: str = '', color: tuple = ALU) -> 'Solid':
        mesh = man.to_mesh()
        v = np.asarray(mesh.vert_properties, dtype=np.float64)[:, :3]
        t = np.asarray(mesh.tri_verts, dtype=np.int64)
        return cls(v, t, name, tuple(color))

    def copy(self, **kw) -> 'Solid':
        d = dict(verts=self.verts.copy(), tris=self.tris.copy(), name=self.name, color=self.color,
                 visible=self.visible)
        d.update(kw)
        return Solid(**d)

    # --- mesures --------------------------------------------------------------------
    def is_empty(self) -> bool:
        return len(self.tris) == 0

    def triangles(self) -> np.ndarray:
        """(m, 3, 3) : les triangles en coordonnées (affichage, STL)."""
        return self.verts[self.tris] if len(self.tris) else np.zeros((0, 3, 3))

    def bounds(self) -> tuple:
        if not len(self.verts):
            return (0.0,) * 6
        lo, hi = self.verts.min(axis=0), self.verts.max(axis=0)
        return (*map(float, lo), *map(float, hi))

    def volume(self) -> float:
        t = self.triangles()
        return float(np.einsum('ij,ij->i', t[:, 0], np.cross(t[:, 1], t[:, 2])).sum() / 6.0) if len(t) else 0.0

    def area(self) -> float:
        t = self.triangles()
        return float(np.linalg.norm(np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0]), axis=1).sum() / 2.0) \
            if len(t) else 0.0

    def centroid(self) -> tuple:
        """Centre de gravité (volume plein, densité uniforme)."""
        t = self.triangles()
        if not len(t):
            return (0.0, 0.0, 0.0)
        v6 = np.einsum('ij,ij->i', t[:, 0], np.cross(t[:, 1], t[:, 2]))
        tot = v6.sum()
        if abs(tot) < 1e-12:
            return tuple(map(float, self.verts.mean(axis=0)))
        c = (t.sum(axis=1) / 4.0 * v6[:, None]).sum(axis=0) / tot
        return tuple(map(float, c))

    def transformed(self, m4) -> 'Solid':
        """Volume déplacé par une matrice 4×4 (ou 3×4) ; une symétrie
        retourne les triangles pour garder les faces vers l'extérieur."""
        m4 = np.asarray(m4, dtype=np.float64)
        R, T = m4[:3, :3], m4[:3, 3]
        v = self.verts @ R.T + T
        t = self.tris[:, ::-1].copy() if np.linalg.det(R) < 0 else self.tris.copy()
        return self.copy(verts=v, tris=t)

    # --- enregistrement --------------------------------------------------------------
    def to_dict(self) -> dict:
        buf = io.BytesIO()
        np.savez_compressed(buf, v=self.verts.astype(np.float64), t=self.tris.astype(np.int32))
        return {'id': self.id, 'name': self.name, 'color': list(self.color), 'visible': self.visible,
                'mesh': base64.b64encode(buf.getvalue()).decode('ascii')}

    @classmethod
    def from_dict(cls, d: dict) -> 'Solid':
        z = np.load(io.BytesIO(base64.b64decode(d['mesh'])))
        return cls(z['v'].astype(np.float64), z['t'].astype(np.int64), d.get('name', ''),
                   tuple(d.get('color', ALU)), d.get('id') or uuid.uuid4().hex[:12], bool(d.get('visible', True)))


def _solid(man, name: str) -> Solid:
    if man.is_empty():
        raise SolidError('volume vide')
    return Solid.from_manifold(man, name)


# --- primitives -------------------------------------------------------------------------
def box(x0: float, y0: float, z0: float, dx: float, dy: float, dz: float) -> Solid:
    """Pavé d'un coin (x0, y0, z0) et de ses côtés (signés)."""
    M = _m()
    if min(abs(dx), abs(dy), abs(dz)) < 1e-9:
        raise SolidError('pavé plat')
    man = M.Manifold.cube((abs(dx), abs(dy), abs(dz))).translate(
        (min(x0, x0 + dx), min(y0, y0 + dy), min(z0, z0 + dz)))
    return _solid(man, 'Pavé')


def wedge(x0: float, y0: float, z0: float, dx: float, dy: float, dz: float) -> Solid:
    """Coin : pavé coupé en biais, pleine hauteur sur le bord x0, nul sur
    le bord x0 + dx (comme WEDGE)."""
    M = _m()
    if min(abs(dx), abs(dy), abs(dz)) < 1e-9:
        raise SolidError('coin plat')
    tri = M.CrossSection([np.array([[0, 0], [abs(dx), 0], [0, abs(dz)]], dtype=float)])
    man = M.Manifold.extrude(tri, abs(dy)).rotate((90, 0, 0)).translate((0, abs(dy), 0))
    if dx < 0:
        man = man.mirror((1, 0, 0)).translate((abs(dx), 0, 0))
    return _solid(man.translate((min(x0, x0 + dx), min(y0, y0 + dy), min(z0, z0 + dz))), 'Coin')


def cylinder(cx: float, cy: float, z0: float, r: float, h: float, r_top: float | None = None,
             segments: int = SEGMENTS) -> Solid:
    """Cylindre (ou tronc de cône si `r_top` diffère) d'axe vertical."""
    M = _m()
    rt = r if r_top is None else r_top
    if r <= 0 and rt <= 0 or abs(h) < 1e-9:
        raise SolidError('cylindre nul')
    man = M.Manifold.cylinder(abs(h), max(r, 0.0), max(rt, 0.0), segments)
    if h < 0:
        man = man.mirror((0, 0, 1))
    return _solid(man.translate((cx, cy, z0)), 'Cylindre' if r_top is None else 'Cône')


def cone(cx: float, cy: float, z0: float, r: float, h: float, r_top: float = 0.0,
         segments: int = SEGMENTS) -> Solid:
    s = cylinder(cx, cy, z0, r, h, r_top, segments)
    s.name = 'Cône'
    return s


def sphere(cx: float, cy: float, cz: float, r: float, segments: int = SEGMENTS) -> Solid:
    M = _m()
    if r <= 0:
        raise SolidError('rayon nul')
    return _solid(M.Manifold.sphere(r, segments).translate((cx, cy, cz)), 'Sphère')


def pyramid(cx: float, cy: float, z0: float, sides: int, r: float, h: float, r_top: float = 0.0,
            inscribed: bool = True, angle: float = 90.0) -> Solid:
    """Pyramide (ou tronc) à `sides` côtés ; `r` : rayon du cercle
    circonscrit (`inscribed` : polygone inscrit) ou inscrit."""
    M = _m()
    sides = max(3, int(sides))
    k = 1.0 if inscribed else 1.0 / math.cos(math.pi / sides)
    if r <= 0 or abs(h) < 1e-9:
        raise SolidError('pyramide nulle')
    a0 = math.radians(angle)
    pts = np.array([[r * k * math.cos(a0 + 2 * math.pi * i / sides), r * k * math.sin(a0 + 2 * math.pi * i / sides)]
                    for i in range(sides)])
    man = M.Manifold.extrude(M.CrossSection([pts]), abs(h), 0, 0.0, (r_top / r, r_top / r))
    if h < 0:
        man = man.mirror((0, 0, 1))
    return _solid(man.translate((cx, cy, z0)), 'Pyramide')


def torus(cx: float, cy: float, cz: float, R: float, r: float, segments: int = SEGMENTS) -> Solid:
    """Tore d'axe vertical : rayon `R` (centre du tube), rayon du tube `r`."""
    M = _m()
    if r <= 0 or R <= 0:
        raise SolidError('tore nul')
    circle = M.CrossSection.circle(r, max(16, segments // 2)).translate((R, 0))
    if R - r < 1e-9:                                     # tore sans trou : le tube ne passe pas l'axe
        circle = circle ^ M.CrossSection.square((R + r + 1, 2 * r + 2)).translate((0, -r - 1))
    return _solid(M.Manifold.revolve(circle, segments).translate((cx, cy, cz)), 'Tore')


# --- depuis la 2D -----------------------------------------------------------------------
def region(path, tol: float = 0.02):
    """Contours fermés d'un tracé (core.geom.Path) → section Manifold
    (règle pair-impair : les trous restent des trous)."""
    M = _m()
    polys = []
    for c in path.contours:
        if not c.closed or not c.segments:
            continue
        pts = np.asarray(c.flatten(tol), dtype=float)
        if len(pts) > 1 and np.allclose(pts[0], pts[-1]):
            pts = pts[:-1]
        if len(pts) >= 3:
            polys.append(pts)
    if not polys:
        raise SolidError('aucun contour fermé')
    return M.CrossSection(polys, M.FillRule.EvenOdd)


def extrude(path, height: float, z0: float = 0.0, taper_deg: float = 0.0, tol: float = 0.02) -> Solid:
    """Les contours fermés de `path` tirés de `height` (négatif : vers le
    bas) ; `taper_deg` : angle de dépouille (positif : les flancs rentrent,
    comme EXTRUDE › Dépouille)."""
    M = _m()
    cs = region(path, tol)
    h = abs(height)
    if h < 1e-9:
        raise SolidError('hauteur nulle')
    man = M.Manifold.extrude(cs, h)
    if abs(taper_deg) > 1e-9:
        if abs(taper_deg) >= 89.0:
            raise SolidError('dépouille trop forte')
        t = h * math.tan(math.radians(abs(taper_deg)))
        cone_ = M.Manifold.cylinder(h, 0.0, t, 48)       # rayon 0 en bas, t en haut
        if taper_deg > 0:                                # rentrant : on érode par le complément
            x0, y0, x1, y1 = cs.bounds()
            pad = t + 1.0
            big = M.CrossSection.square((x1 - x0 + 2 * pad, y1 - y0 + 2 * pad)).translate((x0 - pad, y0 - pad))
            comp = M.Manifold.extrude(big - cs, h)
            man = man - M.Manifold.minkowski_sum(comp, cone_)
        else:                                            # sortant
            slab = M.Manifold.extrude(M.CrossSection.square((1, 1)), h)
            grown = M.Manifold.minkowski_sum(man, cone_)
            x0, y0, z_, x1, y1, z1 = grown.bounding_box()
            man = grown ^ slab.scale((x1 - x0 + 2, y1 - y0 + 2, 1)).translate((x0 - 1, y0 - 1, 0))
    if height < 0:
        man = man.mirror((0, 0, 1))
    return _solid(man.translate((0, 0, z0)), 'Extrusion')


def extent_sides(direction: str, d: float, d2: float = 0.0) -> tuple:
    """(bas, haut) d'une extrusion depuis le plan du dessin (SolidCraft :
    `extent_sides`) : 'plus' : d, son signe donne le côté ; 'sym' : d en
    tout, moitié de chaque côté ; 'deux' : d d'un côté, d2 de l'autre."""
    d, d2 = float(d), float(d2)
    if direction == 'sym':
        return -abs(d) / 2, abs(d) / 2
    if direction == 'deux':
        other = d2 if d < 0 else -d2
        return min(other, d), max(other, d)
    return min(0.0, d), max(0.0, d)


def through_all_distance(solids: list, z0: float = 0.0) -> float:
    """Hauteur qui traverse tous les `solids` depuis le plan Z = z0, d'un
    côté comme de l'autre (SolidCraft : `through_all_distance`)."""
    far, any_ = 0.0, False
    for s in solids:
        if s.is_empty():
            continue
        any_ = True
        x0, y0, za, x1, y1, zb = s.bounds()
        far = max(far, abs(za - z0), abs(zb - z0))
    if not any_:
        raise SolidError('à travers tout : aucun volume à traverser')
    return far * 1.02 + 1.0


def extrude_between(path, lo: float, hi: float, z0: float = 0.0, taper_deg: float = 0.0,
                    tol: float = 0.02) -> Solid:
    """Les contours fermés de `path` tirés de z0 + lo à z0 + hi ; la
    dépouille part du plan du dessin, donc d'un seul côté (comme SolidCraft)."""
    if hi - lo < 1e-9:
        raise SolidError('hauteur nulle')
    if abs(taper_deg) > 1e-9:
        if lo < -1e-9 and hi > 1e-9:
            raise SolidError('dépouille sur un seul côté')
        if lo >= -1e-9:
            return extrude(path, hi - lo, z0 + lo, taper_deg, tol)
        return extrude(path, lo - hi, z0 + hi, taper_deg, tol)
    return extrude(path, hi - lo, z0 + lo, 0.0, tol)


def revolve(path, axis=((0.0, 0.0), (0.0, 1.0)), angle: float = 360.0, start: float = 0.0,
            segments: int = SEGMENTS, tol: float = 0.02) -> Solid:
    """Les contours fermés de `path` (dans le plan du dessin) tournés
    autour d'un axe du plan donné par deux points, de `angle` degrés à
    partir de `start` (REVOLVE), dans le sens direct autour de l'axe (règle
    de la main droite : autour de +X, +Y passe vers +Z)."""
    M = _m()
    (ax, ay), (bx, by) = axis
    d = math.hypot(bx - ax, by - ay)
    if d < 1e-9:
        raise SolidError('axe nul')
    ux, uy = (bx - ax) / d, (by - ay) / d
    cs = region(path, tol)
    # repère local : axe → Y, sa normale (à droite de l'axe) → X
    rot = cs.translate((-ax, -ay))
    ang = math.degrees(math.atan2(ux, uy))              # tourner pour amener l'axe sur +Y
    rot = rot.rotate(ang)
    x0, _y0, x1, _y1 = rot.bounds()
    if x0 < -1e-6 and x1 > 1e-6:
        raise SolidError('le profil traverse l\'axe')
    if x1 <= 1e-6:                                       # profil à gauche : axe retourné, angles opposés
        return revolve(path, (axis[1], axis[0]), -angle, -start, segments, tol)
    sweep = max(-360.0, min(360.0, angle))
    if abs(sweep) < 1e-6:
        raise SolidError('angle nul')
    n = max(3, int(round(segments * abs(sweep) / 360.0)))
    man = M.Manifold.revolve(rot, n, abs(sweep))         # autour de Z local : (x, y) → (r, z)
    if sweep < 0:
        man = man.mirror((0, 1, 0))
    if start:
        man = man.rotate((0, 0, start))
    # Z local (axe) → l'axe du dessin, dans le plan XY ; X local → la normale du plan
    th = math.radians(-ang)
    ex = (math.cos(th), math.sin(th), 0.0)               # X local tourné dans le plan
    ez = (ux, uy, 0.0)                                   # axe
    ey = np.cross(ez, ex)                                # hors du plan
    m4 = np.eye(4)
    m4[:3, 0], m4[:3, 1], m4[:3, 2] = ex, ey, ez
    m4[:3, 3] = (ax, ay, 0.0)
    s = _solid(man, 'Révolution')
    return s.transformed(m4)


# --- booléens ---------------------------------------------------------------------------
def boolean(op: str, solids: list) -> Solid:
    """'union' de tous, 'subtract' : le premier moins les autres,
    'intersect' : la partie commune à tous."""
    M = _m()
    if len(solids) < (1 if op == 'union' else 2):
        raise SolidError('pas assez de volumes')
    mans = [s.manifold() for s in solids]
    if op == 'union':
        man = M.Manifold.batch_boolean(mans, M.OpType.Add)
    elif op == 'subtract':
        man = mans[0] - M.Manifold.batch_boolean(mans[1:], M.OpType.Add)
    elif op == 'intersect':
        man = M.Manifold.batch_boolean(mans, M.OpType.Intersect)
    else:
        raise SolidError(op)
    s = _solid(man, solids[0].name)
    s.color = solids[0].color
    return s


def massprop(s: Solid, density: float = 0.0) -> dict:
    """Volume (mm³), aire (mm²), centre de gravité, encombrement ; masse
    (g) si `density` (g/cm³) est donnée (MASSPROP)."""
    v = s.volume()
    d = {'volume': v, 'area': s.area(), 'centroid': s.centroid(), 'bounds': s.bounds()}
    if density > 0:
        d['mass'] = v / 1000.0 * density
    return d


# --- dans le dessin ---------------------------------------------------------------------
# Un volume est une forme du dessin : son tracé est sa silhouette vue de dessus, son
# maillage est dans extra['solide'] (repère propre + matrice de placement 4×4). Sélection,
# calques, annulation, enregistrement et transformations 2D marchent comme pour toute forme ;
# une transformation 2D se reporte sur la matrice (le maillage n'est pas réécrit).
KEY = 'solide'

_decoded: dict = {}


def silhouette(s: Solid):
    """Contour vu de dessus (core.geom.Path de segments droits)."""
    from .geom import Contour, Line, Path
    M = _m()
    if s.is_empty():
        return Path([])
    cs = M.CrossSection(s.manifold().project().to_polygons(), M.FillRule.Positive)
    out = []
    for poly in cs.to_polygons():
        pts = [tuple(map(float, q)) for q in poly]
        segs = [Line(a, b) for a, b in zip(pts, pts[1:] + pts[:1]) if math.dist(a, b) > 1e-9]
        if len(segs) >= 3:
            out.append(Contour(segs, True))
    return Path(out)


def make_shape(s: Solid, tool: int = 0):
    """Forme du dessin portant le volume `s`."""
    from .document import Shape
    sd = s.to_dict()
    sd['m'] = np.eye(4).ravel().tolist()
    return Shape(path=silhouette(s), tool=tool, name=s.name, extra={KEY: sd})


def is_solid(it) -> bool:
    return isinstance(getattr(it, 'extra', None), dict) and isinstance(it.extra.get(KEY), dict)


def of_item(it) -> Solid | None:
    """Le volume d'une forme (placé), ou None."""
    if not is_solid(it):
        return None
    sd = it.extra[KEY]
    key = sd['mesh']
    base = _decoded.get(key)
    if base is None:
        base = Solid.from_dict(sd)
        if len(_decoded) > 256:
            _decoded.clear()
        _decoded[key] = base
    s = base.copy(name=it.name or sd.get('name', ''), color=tuple(sd.get('color', ALU)))
    s.id = it.id
    m = np.asarray(sd.get('m') or np.eye(4).ravel(), dtype=np.float64).reshape(4, 4)
    return s if np.allclose(m, np.eye(4)) else s.transformed(m)


def with_solid(it, s: Solid):
    """La forme `it` portant désormais le volume `s` (même nom, outil,
    identifiant) — après un booléen, une coupe…"""
    import copy as _copy
    c = _copy.copy(it)
    sd = s.to_dict()
    sd['m'] = np.eye(4).ravel().tolist()
    sd['color'] = list(it.extra[KEY].get('color', ALU)) if is_solid(it) else sd['color']
    c.extra = dict(getattr(it, 'extra', {}) or {}, **{KEY: sd})
    c.path = silhouette(s)
    return c


def transformed_extra(sd: dict, m) -> dict:
    """extra['solide'] après la transformation 2D `m` (core.geom.Affine) :
    XY suivent ; Z suit une similitude (même rapport), pas un étirement."""
    det = m.a * m.d - m.b * m.c
    similar = abs(m.a - m.d) < 1e-9 and abs(m.b + m.c) < 1e-9 or abs(m.a + m.d) < 1e-9 and abs(m.b - m.c) < 1e-9
    kz = math.sqrt(abs(det)) if similar else 1.0
    A = np.array([[m.a, m.c, 0, m.e], [m.b, m.d, 0, m.f], [0, 0, kz, 0], [0, 0, 0, 1]], dtype=np.float64)
    cur = np.asarray(sd.get('m') or np.eye(4).ravel(), dtype=np.float64).reshape(4, 4)
    return dict(sd, m=(A @ cur).ravel().tolist())


def doc_solids(doc, visible_only: bool = True) -> list:
    """[(forme, volume placé)] du dessin, calques cachés exclus si demandé."""
    out = []

    def walk(items):
        for it in items:
            if visible_only and not getattr(it, 'visible', True):
                continue
            ch = getattr(it, 'children', None)
            if ch is not None:
                walk(ch)
            elif is_solid(it):
                s = of_item(it)
                if s is not None:
                    out.append((it, s))
    for L in doc.layers:
        if visible_only and not getattr(L, 'visible', True):
            continue
        walk(L.items)
    return out


def to_model(solids: list, name: str = 'Volumes', edges: bool = True):
    """Volumes → io.model3d.Model3D (plan de travail 3D) ; `edges` faux :
    sans arêtes (bornes, hauteurs : plus rapide)."""
    from ..io.model3d import Model3D, sharp_edges
    tris = [s.triangles() for s in solids if not s.is_empty()]
    if not tris:
        return None
    T = np.concatenate(tris)
    C = np.concatenate([np.tile(np.asarray(s.color, dtype=float), (len(s.tris), 1)) for s in solids
                        if not s.is_empty()])
    B = np.concatenate([np.full(len(s.tris), k, dtype=np.int64) for k, s in
                        enumerate(s for s in solids if not s.is_empty())])
    names = [getattr(s, 'name', '') or f'Volume {k + 1}' for k, s in enumerate(s for s in solids if not s.is_empty())]
    segs = sharp_edges(T) if edges else np.zeros((0, 2, 3), dtype=np.float32)
    return Model3D(T, C, segs, name=name, parts=len(tris), faces=len(T), body_of=B, body_names=names)


# --- maillages, reliefs -----------------------------------------------------------------
def from_triangles(T, name: str = 'Volume', tol: float = 1e-6) -> Solid:
    """Triangles (n, 3, 3) — un STL — en volume : sommets fusionnés ;
    SolidError si le maillage n'est pas fermé."""
    T = np.asarray(T, dtype=np.float64).reshape(-1, 3, 3)
    if not len(T):
        raise SolidError('aucun triangle')
    P = T.reshape(-1, 3)
    key = np.round(P / tol).astype(np.int64)
    uniq, inv = np.unique(key, axis=0, return_inverse=True)
    verts = np.zeros((len(uniq), 3))
    np.add.at(verts, inv.ravel(), P)
    verts /= np.bincount(inv.ravel(), minlength=len(uniq))[:, None]
    tris = inv.reshape(-1, 3)
    ok = (tris[:, 0] != tris[:, 1]) & (tris[:, 1] != tris[:, 2]) & (tris[:, 0] != tris[:, 2])
    s = Solid(verts, tris[ok], name)
    man = s.manifold()                                   # contrôle : fermé, orienté
    if man.volume() < 0:
        s.tris = s.tris[:, ::-1].copy()
    return Solid.from_manifold(s.manifold(), name)


def from_heightmap(H, x0: float, y1: float, res: float, floor: float = 2.0, max_cells: int = 250_000,
                   name: str = 'Relief') -> Solid:
    """Relief (carte de hauteurs, lignes du haut vers le bas) en volume :
    dessus aux hauteurs de la carte, dessous `floor` mm sous son point le
    plus bas ; la carte est allégée au-delà de `max_cells` points."""
    from ..io.stl_write import heightmap_mesh
    H = np.asarray(H, dtype=np.float64)
    stride = max(1, int(np.ceil(np.sqrt(H.size / max(1000, int(max_cells))))))
    T = heightmap_mesh(H, x0, y1, res, max(floor, 1e-3), stride)
    lo = float(H[::stride, ::stride].min())
    T[..., 2] += lo - max(floor, 1e-3)                    # dessus : les vraies hauteurs
    return from_triangles(T, name)


def heights(solids: list, res: float = 0.1, margin: float = 1.0, max_cells: int = 4_000_000):
    """Vue de dessus des volumes en carte de hauteurs (le plus haut point
    de matière à chaque pas ; 0 hors des volumes) : (H, x0, y1, pas)."""
    tris = [s.triangles() for s in solids if not s.is_empty()]
    if not tris:
        raise SolidError('aucun volume')
    T = np.concatenate(tris)
    lo, hi = T.reshape(-1, 3).min(axis=0), T.reshape(-1, 3).max(axis=0)
    x0, y0, x1, y1 = lo[0] - margin, lo[1] - margin, hi[0] + margin, hi[1] + margin
    res = max(res, math.sqrt((x1 - x0) * (y1 - y0) / max_cells))
    nx, ny = max(1, int(math.ceil((x1 - x0) / res))), max(1, int(math.ceil((y1 - y0) / res)))
    H = np.full((ny, nx), -np.inf)
    N = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
    for t in T[N[:, 2] > 1e-12]:                         # faces tournées vers le haut : le dessus
        (ax, ay, az), (bx, by, bz), (cx, cy, cz) = t
        j0 = max(0, int((min(ax, bx, cx) - x0) / res - 0.5))
        j1 = min(nx - 1, int((max(ax, bx, cx) - x0) / res - 0.5) + 1)
        i0 = max(0, int((y1 - max(ay, by, cy)) / res - 0.5))
        i1 = min(ny - 1, int((y1 - min(ay, by, cy)) / res - 0.5) + 1)
        if j1 < j0 or i1 < i0:
            continue
        px = x0 + (np.arange(j0, j1 + 1) + 0.5) * res
        py = y1 - (np.arange(i0, i1 + 1) + 0.5) * res
        X, Y = np.meshgrid(px, py)
        det = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(det) < 1e-18:
            continue
        l1 = ((by - cy) * (X - cx) + (cx - bx) * (Y - cy)) / det
        l2 = ((cy - ay) * (X - cx) + (ax - cx) * (Y - cy)) / det
        l3 = 1.0 - l1 - l2
        inside = (l1 >= -1e-9) & (l2 >= -1e-9) & (l3 >= -1e-9)
        if not inside.any():
            continue
        Z = l1 * az + l2 * bz + l3 * cz
        sub = H[i0:i1 + 1, j0:j1 + 1]
        np.maximum(sub, np.where(inside, Z, -np.inf), out=sub)
    H[~np.isfinite(H)] = 0.0
    return H, x0, y1, res


# --- transformations 3D, coupes ---------------------------------------------------------
def rotation(axis: str, angle: float, center=(0.0, 0.0, 0.0)) -> np.ndarray:
    """Matrice 4×4 : rotation de `angle` degrés autour d'un axe X, Y ou Z
    passant par `center` (sens direct)."""
    a = math.radians(angle)
    c, s = math.cos(a), math.sin(a)
    R = {'x': [[1, 0, 0], [0, c, -s], [0, s, c]], 'y': [[c, 0, s], [0, 1, 0], [-s, 0, c]],
         'z': [[c, -s, 0], [s, c, 0], [0, 0, 1]]}[axis]
    m = np.eye(4)
    m[:3, :3] = R
    C = np.asarray(center, dtype=np.float64)
    m[:3, 3] = C - m[:3, :3] @ C
    return m


def permutation(bounds, shift_x: float = 0.0) -> np.ndarray:
    """Matrice 4×4 : X Y Z devient Z X Y. La boîte `bounds` garde son centre en X et Y et son dessous ; trois fois de
    suite rendent la pièce d'origine. `shift_x` : décalage en X du résultat."""
    x0, y0, z0, x1, y1, z1 = bounds
    m = np.eye(4)
    m[:3, :3] = [[0, 0, 1], [1, 0, 0], [0, 1, 0]]
    centre = np.array([(x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2])
    wanted = np.array([centre[0] + shift_x, centre[1], z0 + (y1 - y0) / 2])
    m[:3, 3] = wanted - m[:3, :3] @ centre
    return m


def translation(dx: float = 0.0, dy: float = 0.0, dz: float = 0.0) -> np.ndarray:
    m = np.eye(4)
    m[:3, 3] = (dx, dy, dz)
    return m


ALIGN_MODES = ('none', 'min', 'centre', 'max', 'after', 'before')


def align_offset(box: tuple, ref: tuple, modes: tuple, gap: float = 0.0) -> tuple:
    """Déplacement (dx, dy, dz) qui aligne l'encombrement `box` sur `ref`,
    axe par axe : 'none' ; 'min', 'centre', 'max' : côtés mini, centres ou
    côtés maxi alignés ; 'after' : contre le côté maxi de la référence (posé
    dessus en Z), 'before' : contre son côté mini (dessous en Z) ; `gap` :
    jeu laissé pour 'after' et 'before'."""
    out = []
    for k, mode in enumerate(modes):
        lo, hi, rlo, rhi = box[k], box[k + 3], ref[k], ref[k + 3]
        out.append({'none': 0.0, 'min': rlo - lo, 'centre': (rlo + rhi - lo - hi) / 2, 'max': rhi - hi,
                    'after': rhi + gap - lo, 'before': rlo - gap - hi}[mode])
    return tuple(out)


def scaling(fx: float, fy: float, fz: float, center=(0.0, 0.0, 0.0)) -> np.ndarray:
    """Matrice 4×4 : échelle par axe autour de `center` (SCALE, d'après
    SolidCraft) ; facteurs strictement positifs (une symétrie passe par
    MIRROR)."""
    f = np.array([float(fx), float(fy), float(fz)])
    if not np.all(f > 0):
        raise SolidError('facteurs d\'échelle : strictement positifs')
    m = np.diag([f[0], f[1], f[2], 1.0])
    C = np.asarray(center, dtype=np.float64)
    m[:3, 3] = C - f * C
    return m


def mirror_z(z: float = 0.0) -> np.ndarray:
    """Symétrie par le plan horizontal Z = z (MIRROR3D › XY)."""
    m = np.diag([1.0, 1.0, -1.0, 1.0])
    m[2, 3] = 2 * z
    return m


def split(s: Solid, normal, offset: float) -> tuple:
    """Coupe par le plan n·p = offset (SLICE) : (côté de la normale, autre
    côté), None pour un côté vide."""
    a, b = s.manifold().split_by_plane(tuple(map(float, normal)), float(offset))
    out = []
    for man, tag in ((a, '+'), (b, '-')):
        if man.is_empty() or man.volume() < 1e-9:
            out.append(None)
        else:
            r = Solid.from_manifold(man, s.name, s.color)
            out.append(r)
    return tuple(out)


def line_plane(a, b) -> tuple:
    """Plan vertical passant par le trait a → b du dessin (SolidCraft : plan
    d'une ligne d'esquisse, selon la normale de l'esquisse) : (normale,
    décalage) pour `split` ; la normale pointe à droite du sens du trait."""
    dx, dy = float(b[0]) - float(a[0]), float(b[1]) - float(a[1])
    n = math.hypot(dx, dy)
    if n < 1e-9:
        raise ValueError('trait de longueur nulle')
    nx, ny = dy / n, -dx / n
    return (nx, ny, 0.0), nx * float(a[0]) + ny * float(a[1])


def section(s: Solid, z: float):
    """Section horizontale à la hauteur z (SECTION) : core.geom.Path."""
    from .geom import Contour, Line, Path
    out = []
    for poly in s.manifold().slice(float(z)).to_polygons():
        pts = [tuple(map(float, q)) for q in poly]
        segs = [Line(a, b) for a, b in zip(pts, pts[1:] + pts[:1]) if math.dist(a, b) > 1e-9]
        if len(segs) >= 3:
            out.append(Contour(segs, True))
    return Path(out)


#: vues à plat : repère de la vue (X à droite, Y en haut, Z vers l'observateur) en lignes
VIEWS_FLAT = {'dessus': ((1, 0, 0), (0, 1, 0), (0, 0, 1)),      # depuis +Z
              'face': ((1, 0, 0), (0, 0, 1), (0, -1, 0)),       # depuis −Y : X à droite, Z en haut
              'cote': ((0, 1, 0), (0, 0, 1), (1, 0, 0))}        # depuis +X : Y à droite, Z en haut


def flatshot(s: Solid, view: str = 'dessus'):
    """Contour du volume vu de dessus, de face (depuis −Y) ou de côté
    (depuis +X), à plat dans le plan du dessin (FLATSHOT, silhouette)."""
    m = np.eye(4)
    m[:3, :3] = VIEWS_FLAT[view]
    return silhouette(s if view == 'dessus' else s.transformed(m))


def components(s: Solid) -> list:
    """Corps disjoints d'un volume (SEPARATE)."""
    return [Solid.from_manifold(m, s.name, s.color) for m in s.manifold().decompose() if not m.is_empty()]


def boundary_cells(solids: list, pieces: bool = True, cavities: bool = False) -> list:
    """Cellules délimitées par les volumes (BOUNDARY FILL, d'après
    SolidCraft) : chaque morceau d'un seul tenant dans certains volumes et
    hors des autres (`pieces`), et chaque vide qu'ils enferment entièrement
    (`cavities` : l'empreinte d'un moule fermé, l'intérieur d'une boîte et
    de son couvercle)."""
    M = _m()
    if not 1 <= len(solids) <= 8:
        raise SolidError('cellules : de 1 à 8 volumes')
    mans = [s.manifold() for s in solids]
    out = []
    if pieces:
        for mask in range(1, 2 ** len(mans)):
            ins = [m for i, m in enumerate(mans) if mask >> i & 1]
            acc = ins[0]
            for m in ins[1:]:
                acc = acc ^ m
            for i, m in enumerate(mans):
                if not mask >> i & 1 and not acc.is_empty():
                    acc = acc - m
            for part in ([] if acc.is_empty() else acc.decompose()):
                if not part.is_empty() and part.volume() > 1e-9:
                    out.append(Solid.from_manifold(part, 'Cellule', solids[(mask & -mask).bit_length() - 1].color))
    if cavities:
        u = mans[0]
        for m in mans[1:]:
            u = u + m
        x0, y0, z0, x1, y1, z1 = u.bounding_box()
        pad = 1.0
        room = M.Manifold.cube((x1 - x0 + 2 * pad, y1 - y0 + 2 * pad, z1 - z0 + 2 * pad)).translate(
            (x0 - pad, y0 - pad, z0 - pad))
        for part in (room - u).decompose():
            b = part.bounding_box()
            if (part.volume() > 1e-9 and b[0] > x0 - pad + 1e-6 and b[1] > y0 - pad + 1e-6 and b[2] > z0 - pad + 1e-6
                    and b[3] < x1 + pad - 1e-6 and b[4] < y1 + pad - 1e-6 and b[5] < z1 + pad - 1e-6):
                out.append(Solid.from_manifold(part, 'Cavité', (0.85, 0.55, 0.35)))
    if not out:
        raise SolidError('aucune cellule')
    return out


def interference(solids: list) -> list:
    """Volumes communs à chaque paire (INTERFERE) : [(i, j, volume commun)]."""
    out = []
    mans = [s.manifold() for s in solids]
    for i in range(len(mans)):
        for j in range(i + 1, len(mans)):
            common = mans[i] ^ mans[j]
            if not common.is_empty() and common.volume() > 1e-9:
                out.append((i, j, Solid.from_manifold(common, f'{solids[i].name} ∩ {solids[j].name}', (0.85, 0.2, 0.2))))
    return out


def _box_gap(a: tuple, b: tuple) -> float:
    """Écart entre deux encombrements (0 s'ils se touchent ou se recoupent)."""
    d = [max(0.0, a[k] - b[k + 3], b[k] - a[k + 3]) for k in range(3)]
    return math.sqrt(sum(v * v for v in d))


def _box_far(a: tuple, b: tuple) -> float:
    """Plus grande distance entre deux points des deux encombrements."""
    d = [max(abs(a[k + 3] - b[k]), abs(b[k + 3] - a[k])) for k in range(3)]
    return math.sqrt(sum(v * v for v in d))


def _closest_vertices(a: Solid, b: Solid, chunk: int = 2048) -> tuple:
    """Les deux sommets les plus proches des maillages de a et de b : le lieu
    du jeu, à la finesse du maillage près."""
    va = np.unique(a.triangles().reshape(-1, 3), axis=0)
    vb = np.unique(b.triangles().reshape(-1, 3), axis=0)
    best, pa, pb = math.inf, va[0], vb[0]
    for k in range(0, len(va), chunk):
        d = ((va[k:k + chunk, None, :] - vb[None, :, :]) ** 2).sum(axis=2)
        i, j = np.unravel_index(int(np.argmin(d)), d.shape)
        if d[i, j] < best:
            best, pa, pb = float(d[i, j]), va[k + i], vb[j]
    return tuple(float(v) for v in pa), tuple(float(v) for v in pb)


def clearance(solids: list, gap: float = 0.0, min_volume: float = 0.01, tolerance: float = 1e-6) -> dict:
    """Jeu entre volumes (SolidCraft : inspect.clearance) : paires qui se
    chevauchent (volume commun > `min_volume`), en contact, ou plus proches
    que `gap` (distance, lieu), et le plus proche voisin de chacun. Une paire
    est écartée sur ses encombrements quand ils sont plus loin que le jeu et
    que les plus proches voisins des deux déjà trouvés. Rend {'overlaps':
    [(i, j, volume)], 'contacts': [(i, j)], 'near': [(i, j, distance, pa,
    pb)], 'nearest': [(j, distance) ou None], 'pruned': nombre}."""
    n = len(solids)
    mans = [s.manifold() for s in solids]
    boxes = [s.bounds() for s in solids]
    pairs = sorted(((_box_gap(boxes[i], boxes[j]), i, j) for i in range(n) for j in range(i + 1, n)))
    best = [math.inf] * n
    nearest = [None] * n
    out = {'overlaps': [], 'contacts': [], 'near': [], 'nearest': nearest, 'pruned': 0}
    for bg, i, j in pairs:
        if bg > gap and bg >= best[i] and bg >= best[j]:
            out['pruned'] += 1
            continue
        d = None
        if bg <= tolerance:
            common = mans[i] ^ mans[j]
            if not common.is_empty():
                v = common.volume()
                if v > min_volume:
                    out['overlaps'].append((i, j, v))
                else:
                    out['contacts'].append((i, j))
                d = 0.0
        if d is None:
            d = float(mans[i].min_gap(mans[j], _box_far(boxes[i], boxes[j]) + 1.0))
            if d <= tolerance:
                out['contacts'].append((i, j))
                d = 0.0
            elif d < gap:
                pa, pb = _closest_vertices(solids[i], solids[j])
                out['near'].append((i, j, d, pa, pb))
        for a, b in ((i, j), (j, i)):
            if d < best[a]:
                best[a], nearest[a] = d, (b, d)
    out['near'].sort(key=lambda t: t[2])
    return out


def _closest_on_triangles(p, a, b, c):
    """Points des triangles abc les plus proches des points p, par paires
    (diffusion numpy) — Ericson, Real-Time Collision Detection 5.1.5, comme
    SolidCraft `closest_on_triangle` ; régions posées de la moins prioritaire
    (intérieur) à la plus prioritaire (sommet a)."""
    ab, ac = b - a, c - a
    ap, bp, cp = p - a, p - b, p - c
    d1, d2 = (ab * ap).sum(-1), (ac * ap).sum(-1)
    d3, d4 = (ab * bp).sum(-1), (ac * bp).sum(-1)
    d5, d6 = (ab * cp).sum(-1), (ac * cp).sum(-1)
    va, vb, vc = d3 * d6 - d5 * d4, d5 * d2 - d1 * d6, d1 * d4 - d3 * d2

    def ratio(num, den):
        with np.errstate(divide='ignore', invalid='ignore'):
            return np.where(np.abs(den) > 1e-300, num / den, 0.0)[..., None]

    den = va + vb + vc
    q = a + ab * ratio(vb, den) + ac * ratio(vc, den)
    for mask, point in (
            ((va <= 0) & (d4 - d3 >= 0) & (d5 - d6 >= 0), lambda: b + (c - b) * ratio(d4 - d3, (d4 - d3) + (d5 - d6))),
            ((vb <= 0) & (d2 >= 0) & (d6 <= 0), lambda: a + ac * ratio(d2, d2 - d6)),
            ((d6 >= 0) & (d5 <= d6), lambda: np.broadcast_to(c, q.shape)),
            ((vc <= 0) & (d1 >= 0) & (d3 <= 0), lambda: a + ab * ratio(d1, d1 - d3)),
            ((d3 >= 0) & (d4 <= d3), lambda: np.broadcast_to(b, q.shape)),
            ((d1 <= 0) & (d2 <= 0), lambda: np.broadcast_to(a, q.shape))):
        if mask.any():
            q = np.where(mask[..., None], point(), q)
    return q


def _morton(P) -> np.ndarray:
    """Clés de Morton (10 bits par axe) : des paquets de points voisins."""
    lo, span = P.min(0), np.ptp(P, axis=0)
    q = np.clip(((P - lo) / np.where(span > 0, span, 1.0) * 1023).astype(np.uint64), 0, 1023)

    def spread(x):
        x = (x | (x << np.uint64(16))) & np.uint64(0x030000FF)
        x = (x | (x << np.uint64(8))) & np.uint64(0x0300F00F)
        x = (x | (x << np.uint64(4))) & np.uint64(0x030C30C3)
        return (x | (x << np.uint64(2))) & np.uint64(0x09249249)
    return spread(q[:, 0]) | (spread(q[:, 1]) << np.uint64(1)) | (spread(q[:, 2]) << np.uint64(2))


def surface_distance(points, T, chunk: int = 32, budget: int = 400_000) -> tuple:
    """Distance de chaque point (n, 3) à la surface des triangles T (m, 3, 3)
    et le point atteint. Points pris par paquets voisins (ordre de Morton) ;
    pour un paquet, les triangles dont l'encombrement est à portée r du sien,
    r doublée tant qu'un point n'a rien trouvé à moins de r (alors exact)."""
    P = np.asarray(points, float)
    T = np.asarray(T, float)
    n = len(P)
    dist, near = np.full(n, np.inf), np.zeros((n, 3))
    if n == 0 or len(T) == 0:
        return dist, near
    tmin, tmax = T.min(axis=1), T.max(axis=1)
    r0 = max(float(np.median(np.linalg.norm(tmax - tmin, axis=1))), 1e-6)
    order = np.argsort(_morton(P), kind='stable')
    for k in range(0, n, chunk):
        idx = order[k:k + chunk]
        pc = P[idx]
        r = r0
        while True:
            lo, hi = pc.min(0) - r, pc.max(0) + r
            cand = T[(tmax >= lo).all(1) & (tmin <= hi).all(1)]
            best = np.full(len(pc), np.inf)
            bq = np.zeros((len(pc), 3))
            step = max(1, budget // len(pc))
            for t in range(0, len(cand), step):
                sub = cand[t:t + step]
                q = _closest_on_triangles(pc[:, None, :], sub[None, :, 0], sub[None, :, 1], sub[None, :, 2])
                d2 = ((q - pc[:, None, :]) ** 2).sum(-1)
                j = d2.argmin(1)
                rr = np.arange(len(pc))
                better = d2[rr, j] < best
                best[better] = d2[rr, j][better]
                bq[better] = q[rr, j][better]
            if len(cand) == len(T) or float(best.max()) <= r * r:
                break
            r *= 2
        dist[idx], near[idx] = np.sqrt(best), bq
    return dist, near


def surface_samples(s: Solid, spacing: float = 0.5, max_points: int = 12_000) -> tuple:
    """Points de la surface (n, 3) et l'aire que chacun représente (n) : chaque
    triangle partagé en k² petits triangles (k : son plus long côté sur
    `spacing`), au centre de chacun ; l'espacement grandit si les points
    dépassent `max_points` (SolidCraft : échantillons de compare)."""
    T = s.triangles()
    e = np.stack([np.linalg.norm(T[:, 1] - T[:, 0], axis=1), np.linalg.norm(T[:, 2] - T[:, 1], axis=1),
                  np.linalg.norm(T[:, 0] - T[:, 2], axis=1)], axis=1).max(axis=1)
    area = 0.5 * np.linalg.norm(np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]), axis=1)
    sp = max(float(spacing), 1e-6)
    while True:
        k = np.maximum(1, np.ceil(e / sp)).astype(int)
        if int((k * k).sum()) <= max_points or int(k.max()) == 1:
            break
        sp *= 1.5
    pts, w = [], []
    for kk in np.unique(k):
        sel, ar = T[k == kk], area[k == kk]
        uv = [((i + 1 / 3) / kk, (j + 1 / 3) / kk) for i in range(kk) for j in range(kk - i)]
        uv += [((i + 2 / 3) / kk, (j + 2 / 3) / kk) for i in range(kk) for j in range(kk - i - 1)]
        uv = np.array(uv)
        p = sel[:, None, 0] + uv[None, :, 0:1] * (sel[:, None, 1] - sel[:, None, 0]) + \
            uv[None, :, 1:2] * (sel[:, None, 2] - sel[:, None, 0])
        pts.append(p.reshape(-1, 3))
        w.append(np.repeat(ar / (kk * kk), len(uv)))
    return np.concatenate(pts), np.concatenate(w)


def _deviation(points, weights, T, tol: float) -> dict:
    d, _q = surface_distance(points, T)
    i = int(np.argmax(d))
    return {'max': float(d[i]), 'at': tuple(float(v) for v in points[i]),
            'mean': float((d * weights).sum() / max(weights.sum(), 1e-300)),
            'beyond_area': float(weights[d > tol].sum()), 'area': float(weights.sum())}


def compare(a: Solid, b: Solid, tolerance: float = 0.01, spacing: float = 0.5, max_points: int = 12_000) -> dict:
    """Deux versions d'une pièce posées l'une sur l'autre (SolidCraft :
    inspect.compare) : écarts de la surface de a à celle de b et l'inverse
    (maximum, lieu, moyenne, aire au-delà de la tolérance) ; régions où un
    seul des deux a de la matière (a − b, b − a, en corps séparés), sans les
    copeaux plus minces que la tolérance ; `identical` s'il n'en reste aucune."""
    Ta, Tb = a.triangles(), b.triangles()
    out = {'a': massprop(a), 'b': massprop(b), 'tolerance': float(tolerance)}
    out['difference'] = out['b']['volume'] - out['a']['volume']
    pa, wa = surface_samples(a, spacing, max_points)
    pb, wb = surface_samples(b, spacing, max_points)
    out['a_to_b'] = _deviation(pa, wa, Tb, tolerance)
    out['b_to_a'] = _deviation(pb, wb, Ta, tolerance)
    regions = []
    for side, first, second, T_other in (('a', a, b, Tb), ('b', b, a, Ta)):
        rest = Solid.from_manifold(first.manifold() - second.manifold(), first.name)
        if rest.is_empty():
            continue
        for piece in components(rest):
            V, _w = surface_samples(piece, spacing, 5000)
            d, _q = surface_distance(V, T_other)
            i = int(np.argmax(d))
            if d[i] <= tolerance:
                continue                                  # copeau d'arrondi : les surfaces s'accordent
            piece.color = (0.88, 0.19, 0.19) if side == 'a' else (0.18, 0.62, 0.27)
            regions.append({'side': side, 'volume': piece.volume(), 'center': piece.centroid(),
                            'bounds': piece.bounds(), 'max_deviation': float(d[i]),
                            'at': tuple(float(v) for v in V[i]), 'solid': piece})
    regions.sort(key=lambda r: -r['volume'])
    out['regions'] = regions
    out['identical'] = not regions
    out['max'] = max(out['a_to_b']['max'], out['b_to_a']['max'])
    return out


# --- balayage, lissage entre sections, mur ----------------------------------------------
def _plane2d(ring: np.ndarray) -> np.ndarray:
    """Points d'un anneau plan exprimés dans son plan (pour trianguler le
    bouchon), vus du côté de sa normale (sens où ils tournent)."""
    c = ring.mean(axis=0)
    n = np.zeros(3)
    for p, q in zip(ring, np.roll(ring, -1, axis=0)):    # normale de Newell
        n += np.cross(p - c, q - c)
    n /= max(np.linalg.norm(n), 1e-12)
    u = ring[0] - c
    u -= n * u.dot(n)
    u /= max(np.linalg.norm(u), 1e-12)
    v = np.cross(n, u)
    return np.stack([(ring - c) @ u, (ring - c) @ v], axis=1)


def _ring_mesh(rings: list, closed_path: bool):
    """Anneaux de même nombre de points ((n, 3) chacun) reliés en tube ;
    bouts bouchés si le chemin est ouvert. L'orientation est corrigée
    ensuite (_closed_solid)."""
    M = _m()
    k = len(rings[0])
    V = np.vstack(rings)
    tris = []
    m = len(rings)
    for i in range(m if closed_path else m - 1):
        a0, b0 = i * k, ((i + 1) % m) * k
        for j in range(k):
            j1 = (j + 1) % k
            tris.append((a0 + j, b0 + j, b0 + j1))
            tris.append((a0 + j, b0 + j1, a0 + j1))
    if not closed_path:
        # bouchons : leurs arêtes en sens inverse de celles du tube (j → j+1 au départ,
        # j+1 → j à l'arrivée) ; triangulate garde le sens des points donnés
        for idx, rev in ((0, False), (m - 1, True)):
            cap = np.asarray(M.triangulate([_plane2d(rings[idx])]), dtype=np.int64)
            if rev:
                cap = cap[:, ::-1]
            tris += [tuple(x + idx * k) for x in cap]
    return V, np.asarray(tris, dtype=np.int64)


def _closed_solid(V, T, name: str) -> Solid:
    s = Solid(np.asarray(V, dtype=np.float64), np.asarray(T, dtype=np.int64), name)
    try:
        man = s.manifold()
    except SolidError:
        s.tris = s.tris[:, ::-1].copy()
        man = s.manifold()
    if man.volume() < 0:
        s.tris = s.tris[:, ::-1].copy()
        man = s.manifold()
    return _solid(man, name)


def _stations(path_contour, tol: float):
    """Points du chemin (n, 2) et indicateur fermé."""
    pts = np.asarray(path_contour.flatten(tol), dtype=float)
    closed = bool(path_contour.closed)
    if closed and len(pts) > 2 and np.allclose(pts[0], pts[-1]):
        pts = pts[:-1]
    keep = [0] + [i for i in range(1, len(pts)) if np.linalg.norm(pts[i] - pts[i - 1]) > 1e-9]
    return pts[keep], closed


def sweep(path_contour, profile, z: float = 0.0, twist: float = 0.0, scale_end: float = 1.0,
          base=None, tol: float = 0.05) -> Solid:
    """Balayage (SWEEP) : le profil (formes fermées, trous compris) dressé
    perpendiculairement au chemin du plan (un contour, ouvert ou fermé) et
    tiré le long de lui ; le point `base` du profil (défaut : le centre de
    son encombrement) suit le chemin à la hauteur `z`. X du profil → à
    gauche du chemin, Y du profil → Z. Torsion (°) et échelle d'arrivée en
    option ; les coins sont pris en onglet."""
    P, closed = _stations(path_contour, tol)
    if len(P) < 2:
        raise SolidError('chemin trop court')
    if abs(twist) > 1e-9 or abs(scale_end - 1.0) > 1e-9:
        # torsion, échelle : assez de stations pour que les faces suivent (≤ 3° de torsion chacune)
        need = max(16, int(math.ceil(abs(twist) / 3.0)))
        Q = np.vstack([P, P[:1]]) if closed else P
        lens = np.linalg.norm(np.diff(Q, axis=0), axis=1)
        dense = []
        for i, ln in enumerate(lens):
            k = max(1, int(math.ceil(need * ln / max(lens.sum(), 1e-12))))
            dense += [Q[i] + (Q[i + 1] - Q[i]) * j / k for j in range(k)]
        if not closed:
            dense.append(Q[-1])
        P = np.asarray(dense)
    cs = region(profile, tol)
    polys = [np.asarray(p, dtype=float) for p in cs.to_polygons() if len(p) >= 3]
    if base is None:
        x0, y0, x1, y1 = profile.bbox()
        base = ((x0 + x1) / 2, (y0 + y1) / 2)
    bx, by = base
    n = len(P)
    seg = np.diff(np.vstack([P, P[:1]]) if closed else P, axis=0)
    seg /= np.linalg.norm(seg, axis=1)[:, None]
    L = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])
    total = L[-1] + (np.linalg.norm(P[0] - P[-1]) if closed else 0.0)
    frames = []
    for i in range(n):
        if closed:
            tin, tout = seg[i - 1], seg[i % len(seg)]
        else:
            tin, tout = seg[max(i - 1, 0)], seg[min(i, len(seg) - 1)]
        t = tin + tout
        t = t / max(np.linalg.norm(t), 1e-12)
        left = np.array([-t[1], t[0]])
        c = max(0.2, float(np.dot(left, np.array([-tin[1], tin[0]]))))   # onglet : 1 / cos(demi-angle)
        frames.append((left, 1.0 / c))
    M = _m()
    mans = []
    for poly in polys:
        q = poly - (bx, by)
        rings = []
        for i, (left, miter) in enumerate(frames):
            f = L[i] / total if total > 0 else 0.0
            a = math.radians(twist * f)
            k = 1.0 + (scale_end - 1.0) * f
            ca, sa = math.cos(a), math.sin(a)
            u = (q[:, 0] * ca - q[:, 1] * sa) * k
            v = (q[:, 0] * sa + q[:, 1] * ca) * k
            xy = P[i] + np.outer(u * miter, left)
            rings.append(np.column_stack([xy, z + v]))
        V, T = _ring_mesh(rings, closed)
        mans.append(_closed_solid(V, T, 'Balayage').manifold())
    mans.sort(key=lambda m: -abs(m.volume()))
    out = mans[0]
    for m in mans[1:]:                                   # un contour dans un autre : un trou
        out = out - m if (out ^ m).volume() > 0.5 * abs(m.volume()) else out + m
    return _solid(out, 'Balayage')


def _resample(pts: np.ndarray, n: int) -> np.ndarray:
    """Contour fermé ré-échantillonné en n points également espacés."""
    Q = np.vstack([pts, pts[:1]])
    d = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(Q, axis=0), axis=1))])
    t = np.linspace(0, d[-1], n, endpoint=False)
    return np.column_stack([np.interp(t, d, Q[:, 0]), np.interp(t, d, Q[:, 1])])


def loft(contours: list, zs: list, smooth: bool = False, samples: int = 0, tol: float = 0.05) -> Solid:
    """Lissage entre sections (LOFT) : des contours fermés du plan, chacun
    posé à sa hauteur (zs), reliés dans l'ordre ; `smooth` : passage
    arrondi d'une section à l'autre (sinon réglé, en droites)."""
    if len(contours) < 2 or len(contours) != len(zs):
        raise SolidError('il faut au moins deux sections, chacune à sa hauteur')
    polys = []
    for c in contours:
        p = np.asarray(c.flatten(tol), dtype=float)
        if len(p) > 2 and np.allclose(p[0], p[-1]):
            p = p[:-1]
        if len(p) < 3:
            raise SolidError('section trop petite')
        area = 0.5 * np.sum(p[:, 0] * np.roll(p[:, 1], -1) - np.roll(p[:, 0], -1) * p[:, 1])
        polys.append(p if area > 0 else p[::-1])
    n = samples or max(32, min(400, max(len(p) for p in polys)))
    R = [_resample(p, n) for p in polys]
    for i in range(1, len(R)):                           # départs alignés : décalage de moindre torsion
        prev = R[i - 1] - R[i - 1].mean(axis=0)
        cur = R[i] - R[i].mean(axis=0)
        best = min(range(n), key=lambda s: float(np.sum((np.roll(cur, -s, axis=0) - prev) ** 2)))
        R[i] = np.roll(R[i], -best, axis=0)
    rings = [np.column_stack([r, np.full(n, float(z))]) for r, z in zip(R, zs)]
    if smooth and len(rings) > 2:                        # Catmull-Rom d'une section à l'autre
        dense, steps = [], 8
        G = [rings[0]] + rings + [rings[-1]]
        for i in range(1, len(G) - 2):
            p0, p1, p2, p3 = G[i - 1], G[i], G[i + 1], G[i + 2]
            for s in range(steps):
                t = s / steps
                dense.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                                    + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
        dense.append(rings[-1])
        rings = dense
    return _closed_solid(*_ring_mesh(rings, False), 'Lissage')


def polysolid(path_contour, width: float, height: float, justify: str = 'centre', z: float = 0.0,
              tol: float = 0.05) -> Solid:
    """Mur (POLYSOLID) : section rectangulaire largeur × hauteur tirée le
    long du chemin ; `justify` : 'gauche', 'centre' ou 'droite' du chemin."""
    from .geom import Path, rect
    if width <= 0 or height <= 0:
        raise SolidError('mur nul')
    off = {'gauche': 0.0, 'centre': -width / 2, 'droite': -width}[justify]
    s = sweep(path_contour, Path([rect(off, 0.0, width, height)]), z, base=(0.0, 0.0), tol=tol)
    s.name = 'Mur'
    return s


# --- coque, arrondis, décalage, tirer / pousser, lissage ---------------------------------
def _ball(r: float, segments: int = 16):
    return _m().Manifold.sphere(abs(r), max(8, int(segments)))


def _grow(man, r: float, segments: int = 16):
    """Manifold grossi de r (somme de Minkowski avec une boule)."""
    return _m().Manifold.minkowski_sum(man, _ball(r, segments))


def _shrink(man, r: float, segments: int = 16):
    """Manifold aminci de r : le complément, grossi, est ôté."""
    M = _m()
    x0, y0, z0, x1, y1, z1 = man.bounding_box()
    pad = abs(r) * 2 + 1.0
    big = M.Manifold.cube((x1 - x0 + 2 * pad, y1 - y0 + 2 * pad, z1 - z0 + 2 * pad)).translate(
        (x0 - pad, y0 - pad, z0 - pad))
    return man - _grow(big - man, r, segments)


def offset(s: Solid, d: float, segments: int = 16) -> Solid:
    """Volume décalé de d (positif : grossi, arêtes arrondies ; négatif :
    aminci)."""
    if abs(d) < 1e-9:
        return s.copy()
    man = _grow(s.manifold(), d, segments) if d > 0 else _shrink(s.manifold(), -d, segments)
    r = _solid(man, s.name)
    r.color = s.color
    return r


SHELL_SIDES = ('+z', '-z', '-x', '+x', '-y', '+y')


def shell(s: Solid, thickness: float, open_top: bool = False, segments: int = 16, open_sides=(),
          direction: str = 'inside') -> Solid:
    """Coque (SOLIDEDIT › Coque ; SolidCraft : solid.shell) : le volume
    évidé, parois d'épaisseur `thickness` ; `open_sides` : côtés par où
    l'intérieur débouche, parmi SHELL_SIDES ('+z' : le dessus, comme
    `open_top`) ; `direction` : 'inside' (parois prises dans le volume),
    'outside' (autour de lui : il devient le vide) ou 'both' (moitié de
    chaque côté)."""
    M = _m()
    if thickness <= 0:
        raise SolidError('épaisseur nulle')
    man = s.manifold()
    t = float(thickness)
    if direction == 'outside':
        outer, inner = _grow(man, t, segments), man
    elif direction == 'both':
        outer, inner = _grow(man, t / 2, segments), _shrink(man, t / 2, segments)
    else:
        outer, inner = man, _shrink(man, t, segments)
    if inner.is_empty():
        raise SolidError('épaisseur trop forte : rien ne reste à évider')
    sides = [k for k in SHELL_SIDES if k in set(open_sides) | ({'+z'} if open_top else set())]
    ob, ib = outer.bounding_box(), inner.bounding_box()
    cuts = [inner]
    for side in sides:                                   # l'intérieur prolongé de ce côté (Minkowski d'un trait)
        k, sign = 'xyz'.index(side[1]), (1 if side[0] == '+' else -1)
        h = (ob[k + 3] - ib[k] if sign > 0 else ib[k + 3] - ob[k]) + 1.0
        size, at = [2e-4, 2e-4, 2e-4], [-1e-4, -1e-4, -1e-4]
        size[k], at[k] = h, (0.0 if sign > 0 else -h)
        cuts.append(M.Manifold.minkowski_sum(inner, M.Manifold.cube(tuple(size)).translate(tuple(at))))
    r = _solid(outer - M.Manifold.batch_boolean(cuts, M.OpType.Add), s.name)
    r.color = s.color
    return r


def round_edges(s: Solid, radius: float, concave: bool = False, segments: int = 16) -> Solid:
    """Arêtes vives arrondies au rayon donné (FILLETEDGE, toutes à la fois) :
    les arêtes saillantes (aminci puis regrossi) ; `concave` : les arêtes
    rentrantes aussi (grossi puis aminci)."""
    if radius <= 0:
        raise SolidError('rayon nul')
    man = s.manifold()
    inner = _shrink(man, radius, segments)
    if inner.is_empty():
        raise SolidError('rayon trop grand pour ce volume')
    man = _grow(inner, radius, segments)
    if concave:
        man = _shrink(_grow(man, radius, segments), radius, segments)
    r = _solid(man, s.name)
    r.color = s.color
    return r


def presspull(s: Solid, path, height: float, z0: float | None = None, tol: float = 0.02) -> Solid:
    """Tirer / pousser (PRESSPULL) : la région fermée `path`, posée sur le
    dessus du volume (ou à z0), tirée vers le haut (height > 0 : ajoutée)
    ou poussée dans la matière (height < 0 : creusée)."""
    if abs(height) < 1e-9:
        raise SolidError('hauteur nulle')
    top = s.bounds()[5] if z0 is None else float(z0)
    tool = extrude(path, abs(height), top if height > 0 else top - abs(height), tol=tol)
    return boolean('union' if height > 0 else 'subtract', [s, tool])


def smooth(s: Solid, steps: int = 2, sharp_angle: float = 52.5) -> Solid:
    """Maillage lissé (MESHSMOOTH) : chaque arête coupée en `steps`, les
    arêtes plus vives que `sharp_angle` gardées."""
    man = s.manifold().smooth_out(float(sharp_angle)).refine(max(1, int(steps)))
    r = _solid(man, s.name)
    r.color = s.color
    return r


# --- ressort, filetage ISO (d'après SolidCraft) -----------------------------------------
#: filetages métriques ISO à pas gros (ISO 261) : (diamètre nominal, pas), mm
ISO_COARSE = ((1.6, 0.35), (2.0, 0.4), (2.5, 0.45), (3.0, 0.5), (4.0, 0.7), (5.0, 0.8), (6.0, 1.0),
              (8.0, 1.25), (10.0, 1.5), (12.0, 1.75), (14.0, 2.0), (16.0, 2.0), (18.0, 2.5), (20.0, 2.5),
              (22.0, 2.5), (24.0, 3.0), (27.0, 3.0), (30.0, 3.5), (36.0, 4.0), (42.0, 4.5), (48.0, 5.0),
              (56.0, 5.5))

#: tours d'un ressort au plus, d'un filetage modélisé au plus
COIL_TURNS = 200
THREAD_TURNS = 190


def parse_metric(s: str) -> tuple:
    """« M8 » (pas gros) ou « M8x1 » → (diamètre nominal, pas) en mm ;
    SolidError si la désignation n'est pas comprise."""
    t = str(s).strip().upper().replace(',', '.').replace('×', 'X')
    try:
        if not t.startswith('M'):
            raise ValueError
        d, sep, p = t[1:].partition('X')
        d = float(d)
        p = float(p) if sep else next(q for n, q in ISO_COARSE if abs(n - d) < 1e-9)
    except (ValueError, StopIteration):
        raise SolidError(f'filetage non compris : « {s} » (M8, M8x1…)') from None
    if not (math.isfinite(d) and math.isfinite(p) and 0 < p < d):
        raise SolidError(f'filetage non compris : « {s} » (M8, M8x1…)')
    return d, p


def format_metric(d: float, p: float) -> str:
    """(8, 1.25) → « M8 » (pas gros) ; (8, 1) → « M8x1 »."""
    if any(abs(n - d) < 1e-9 and abs(q - p) < 1e-9 for n, q in ISO_COARSE):
        return f'M{d:g}'
    return f'M{d:g}x{p:g}'


def metric_for(diameter: float, internal: bool = False):
    """Filetage ISO à pas gros (diamètre, pas) d'un cylindre de ce diamètre :
    une tige a le diamètre nominal, un trou celui du perçage (nominal - pas) ;
    le plus proche à 15 % près, sinon None."""
    def want(nq):
        return nq[0] - nq[1] if internal else nq[0]
    best = min(ISO_COARSE, key=lambda nq: abs(want(nq) - diameter))
    return best if abs(want(best) - diameter) <= 0.15 * diameter else None


def _helix(section, cx: float, cy: float, z0: float, pitch: float, turns: float, per_turn: int,
           left: bool = False, start: float = 0.0, name: str = 'Hélice') -> Solid:
    """Section plane (points (rayon, hauteur) dans le demi-plan de l'axe à
    `start` degrés de X) vissée autour de l'axe vertical (cx, cy) : `turns`
    tours, montée de `pitch` par tour, `per_turn` sections par tour ; à
    droite (sens direct en montant) ou à gauche. Bouts plats."""
    sec = np.asarray(section, dtype=float)
    n = max(2, int(math.ceil(turns * per_turn)))
    sgn = -1.0 if left else 1.0
    a0 = math.radians(start)
    rings = []
    for i in range(n + 1):
        t = turns * i / n
        a = a0 + sgn * 2.0 * math.pi * t
        rings.append(np.column_stack([cx + sec[:, 0] * math.cos(a), cy + sec[:, 0] * math.sin(a),
                                      z0 + sec[:, 1] + pitch * t]))
    V, T = _ring_mesh(rings, False)
    return _closed_solid(V, T, name)


def coil(cx: float, cy: float, z0: float, diameter: float, pitch: float, turns: float, size: float,
         square: bool = False, position: int = 0, start: float = 0.0, left: bool = False) -> Solid:
    """Ressort (COIL) d'axe vertical en (cx, cy), posé sur Z0 : section ronde
    (ou carrée) de taille `size` enroulée sur `turns` tours au pas `pitch`.
    `position` : diamètre pris au milieu de la section (0), section dedans
    (-1 : diamètre hors tout) ou dehors (1 : diamètre intérieur). Départ à
    `start` degrés de l'axe X ; `left` : enroulé à gauche."""
    d, s, n, p = float(diameter), float(size), float(turns), float(pitch)
    if not (d > 0 and s > 0 and n > 0 and p >= 0):
        raise SolidError('diamètre, section, pas et tours du ressort : positifs')
    if n > COIL_TURNS:
        raise SolidError(f'ressort limité à {COIL_TURNS} tours')
    r = d / 2 + max(-1, min(1, int(position))) * s / 2
    if r <= s / 2 + 1e-9:
        raise SolidError('la section du ressort touche son axe')
    if n > 1 - s / (2 * math.pi * r) and p <= s:          # la spire revient sur elle-même
        raise SolidError(f'le ressort se recoupe : le pas doit dépasser la section ({s:g} mm)')
    h = s / 2
    if square:
        sec = [(r - h, 0.0), (r + h, 0.0), (r + h, s), (r - h, s)]
    else:
        sec = [(r + h * math.cos(2 * math.pi * i / 24), h + h * math.sin(2 * math.pi * i / 24)) for i in range(24)]
    return _helix(sec, cx, cy, float(z0), p, n, 72, left, start, 'Ressort')


def _thread_groove(cx: float, cy: float, d: float, p: float, z0: float, z1: float, radius: float,
                   internal: bool, left: bool = False, open_ends=(True, True)) -> Solid:
    """Le creux hélicoïdal entre les filets d'un filetage ISO modélisé
    (profil de base ISO 68-1, flancs à 60°), de Z0 à Z1, à creuser dans une
    tige (extérieur) ou dans la paroi d'un trou (intérieur) de rayon
    `radius`. Un bout ouvert (`open_ends` : bas, haut) dépasse d'un pas."""
    h = p * math.sqrt(3) / 2
    slope = math.tan(math.pi / 6)
    if not (p > 1e-3 and z1 - z0 > 1e-6):
        raise SolidError('filetage trop court')
    if (z1 - z0) / p > THREAD_TURNS:
        raise SolidError(f'filetage modélisé limité à {THREAD_TURNS} tours ({THREAD_TURNS * p:.0f} mm à ce pas)')
    basic = 5 * h / 8
    depth = d / 2 - radius if internal else radius - (d / 2 - basic)
    if not depth >= basic / 4:
        raise SolidError('trou trop large pour ce filetage' if internal else 'tige trop fine pour ce filetage')
    if internal:                                         # de la paroi au diamètre nominal (fond plat P/8)
        r_in = min(radius, d / 2 - basic) - 0.1 * p
        r0, w0, r1, w1 = r_in, (p / 8 + 2 * (d / 2 - r_in) * slope) / 2, d / 2, p / 16
    else:                                                # du fond (5H/8 sous le nominal, plat P/4) au dehors
        r_root = d / 2 - basic
        r_out = max(radius, d / 2) + 0.05 * p
        r0, w0, r1, w1 = r_root, p / 8, r_out, (p / 4 + 2 * (r_out - r_root) * slope) / 2
    if 2 * max(w0, w1) >= 0.98 * p:
        raise SolidError('trou trop étroit pour ce filetage' if internal else 'tige trop grosse pour ce filetage')
    s0 = z0 - p if open_ends[0] else z0
    s1 = z1 + p if open_ends[1] else z1
    # corde à moins de 1 % du pas sur le rayon extérieur, 48 sections par tour au moins
    outer = max(abs(r0), abs(r1))
    per_turn = max(48, math.ceil(math.pi / math.acos(1 - min(0.01 * p / outer, 1.0))))
    if per_turn > 720:
        raise SolidError('filetage trop fin pour ce diamètre')
    sec = [(r0, -w0), (r1, -w1), (r1, w1), (r0, w0)]
    return _helix(sec, cx, cy, s0, p, (s1 - s0) / p, per_turn, left, name='Filet')


def threaded_rod(cx: float, cy: float, z0: float, length: float, designation: str = 'M8', left: bool = False,
                 chamfer: bool = True) -> Solid:
    """Tige filetée d'axe vertical en (cx, cy), de Z0 à Z0 + longueur :
    filetage ISO modélisé sur toute la longueur, bouts chanfreinés à 45°
    jusqu'au fond de filet si `chamfer`."""
    M = _m()
    d, p = parse_metric(designation)
    L = float(length)
    if L <= 0:
        raise SolidError('longueur nulle')
    R = d / 2
    c = min(5 * p * math.sqrt(3) / 16, L / 4) if chamfer else 0.0
    poly = ([(0.0, 0.0), (R - c, 0.0), (R, c), (R, L - c), (R - c, L), (0.0, L)] if c > 1e-9
            else [(0.0, 0.0), (R, 0.0), (R, L), (0.0, L)])
    blank = M.Manifold.revolve(M.CrossSection([np.array(poly, dtype=float)]), SEGMENTS).translate((cx, cy, z0))
    groove = _thread_groove(cx, cy, d, p, z0, z0 + L, R, False, left)
    return _solid(blank - groove.manifold(), f'Tige filetée {format_metric(d, p)}')


def tapped_hole(s: Solid, cx: float, cy: float, designation: str = 'M8', depth: float = 10.0,
                through: bool = False, top: float | None = None, left: bool = False) -> Solid:
    """Taraudage d'axe vertical en (cx, cy) dans le volume `s`, depuis `top`
    (défaut : le dessus du volume) vers le bas : perçage au diamètre nominal
    moins le pas, filet ISO modélisé sur `depth` (débouchant : sur tout le
    volume). Un trou borgne est percé 2 pas plus bas que le filet et fini en
    pointe à 118°."""
    d, p = parse_metric(designation)
    _x0, _y0, zb, _x1, _y1, zt = s.bounds()
    if top is not None:
        zt = float(top)
    rd = (d - p) / 2
    if through:
        if zt - zb <= 1e-9:
            raise SolidError('volume plat')
        tools = [cylinder(cx, cy, zb - 1.0, rd, zt - zb + 2.0),
                 _thread_groove(cx, cy, d, p, zb, zt, rd, True, left)]
    else:
        depth = float(depth)
        if depth <= 0:
            raise SolidError('profondeur nulle')
        dd = depth + 2 * p
        tools = [cylinder(cx, cy, zt - dd, rd, dd + 1.0),
                 cone(cx, cy, zt - dd, rd, -rd / math.tan(math.radians(59.0))),
                 _thread_groove(cx, cy, d, p, zt - depth, zt, rd, True, left, (False, True))]
    out = boolean('subtract', [s] + tools)
    out.name, out.color = s.name, s.color
    return out


# --- perçages, tube, volume englobant (d'après SolidCraft) ------------------------------
#: genres de perçage
HOLES = {'simple': 'Simple', 'lame': 'Lamé', 'fraise': 'Fraisé'}


def _revolved(prof, cx: float, cy: float, z0: float, segments: int = SEGMENTS):
    """Profil (rayon, hauteur) tourné autour de l'axe vertical (cx, cy), sa
    hauteur 0 à Z0 : Manifold."""
    M = _m()
    P = np.asarray(prof, dtype=float)
    if (P[:, 0] * np.roll(P[:, 1], -1) - np.roll(P[:, 0], -1) * P[:, 1]).sum() < 0:   # sens direct
        P = P[::-1].copy()
    return M.Manifold.revolve(M.CrossSection([P]), segments).translate((cx, cy, z0))


def hole(s: Solid, cx: float, cy: float, diameter: float, depth: float | None = None, kind: str = 'simple',
         point: bool = False, tip_angle: float = 118.0, cb_diameter: float = 0.0, cb_depth: float = 0.0,
         cs_diameter: float = 0.0, cs_angle: float = 90.0, top: float | None = None) -> Solid:
    """Perçage (HOLE) d'axe vertical en (cx, cy) dans le volume `s`, depuis
    `top` (défaut : le dessus du volume) : simple, lamé (lamage
    `cb_diameter` × `cb_depth` ; 0 : 1,8 × le diamètre, profond du
    diamètre) ou fraisé (fraisure de `cs_diameter` à `cs_angle` degrés ;
    0 : 2 × le diamètre). `depth` None : débouchant ; un trou borgne peut
    finir en pointe de foret de `tip_angle` degrés (`point`)."""
    r = float(diameter) / 2
    if not r > 1e-6:
        raise SolidError('diamètre du perçage nul')
    _x0, _y0, zb, _x1, _y1, zt = s.bounds()
    if top is not None:
        zt = float(top)
    m = max(0.1, 0.01 * (zt - zb))                       # le profil dépasse du dessus
    tip = 0.0
    if depth is None:
        b = -(zt - zb) - 1.0                             # à travers tout
    else:
        b = -float(depth)
        if b >= 0:
            raise SolidError('profondeur du perçage nulle')
        half = math.radians(float(tip_angle)) / 2
        if point and 1e-3 < half < math.pi / 2 - 1e-6:
            tip = r / math.tan(half)
    prof = [(0.0, m)]
    if kind == 'lame':
        rc = float(cb_diameter) / 2 if cb_diameter > 0 else 1.8 * r
        dc = float(cb_depth) if cb_depth > 0 else 2 * r
        if not (rc > r and -dc > b):
            raise SolidError('le lamage doit être plus large et moins profond que le trou')
        prof += [(rc, m), (rc, -dc), (r, -dc)]
    elif kind == 'fraise':
        rc = float(cs_diameter) / 2 if cs_diameter > 0 else 2 * r
        half = math.radians(float(cs_angle)) / 2
        if not (rc > r and 1e-3 < half < math.pi / 2 - 1e-6):
            raise SolidError('la fraisure doit être plus large que le trou')
        t = (rc - r) / math.tan(half)
        if -t <= b:
            raise SolidError('la fraisure est plus profonde que le trou')
        prof += [(rc + m * math.tan(half), m), (r, -t)]
    else:
        prof += [(r, m)]
    prof += [(r, b), (0.0, b - tip)]
    out = _solid(s.manifold() - _revolved(prof, cx, cy, zt), s.name)
    out.color = s.color
    return out


def pipe(path_contour, diameter: float, wall: float = 0.0, z: float | None = None, tol: float = 0.05) -> Solid:
    """Tube (PIPE) le long d'un contour du plan, ouvert ou fermé : plein, ou
    creux de paroi `wall` ; son axe à la hauteur `z` (défaut : le rayon,
    posé sur le plan). Coins en onglet."""
    from .geom import Path, circle
    rad, w = float(diameter) / 2, float(wall)
    if not rad > 0:
        raise SolidError('diamètre du tube nul')
    if not 0 <= w < rad:
        raise SolidError('paroi du tube : entre 0 (plein) et le rayon')
    prof = [circle((0.0, 0.0), rad)] + ([circle((0.0, 0.0), rad - w)] if w > 0 else [])
    s = sweep(path_contour, Path(prof), z=rad if z is None else float(z), base=(0.0, 0.0), tol=tol)
    s.name = 'Tube'
    return s


def bounding(solids: list, margin: float = 0.0, shape: str = 'pave') -> Solid:
    """Volume englobant (BOUNDING SOLID) des volumes donnés, grossi de
    `margin` : pavé, ou cylindre d'axe vertical centré sur l'encombrement
    (`shape` 'cylindre' : brut de tournage), ses facettes hors de la matière."""
    if not solids:
        raise SolidError('aucun volume à englober')
    V = np.vstack([s.verts for s in solids])
    m = float(margin)
    lo, hi = V.min(axis=0) - m, V.max(axis=0) + m
    if shape == 'cylindre':
        cx, cy = (V[:, 0].min() + V[:, 0].max()) / 2, (V[:, 1].min() + V[:, 1].max()) / 2
        r = (float(np.hypot(V[:, 0] - cx, V[:, 1] - cy).max()) + m) / math.cos(math.pi / SEGMENTS)
        out = cylinder(cx, cy, float(lo[2]), r, float(hi[2] - lo[2]))
    else:
        out = box(*map(float, lo), *map(float, hi - lo))
    out.name = 'Volume englobant'
    return out


# --- nervure, bossage (d'après SolidCraft) ----------------------------------------------
def top_at(s: Solid, x: float, y: float, eps: float = 1e-3):
    """Z du dessus de la matière du volume au point (x, y) du plan (le
    premier point touché en descendant d'en haut), ou None s'il n'y a pas de
    matière sous ce point."""
    M = _m()
    _x0, _y0, zb, _x1, _y1, zt = s.bounds()
    needle = M.Manifold.cube((2 * eps, 2 * eps, zt - zb + 2.0)).translate((x - eps, y - eps, zb - 1.0))
    hit = s.manifold() ^ needle
    if hit.is_empty() or hit.volume() <= 0:
        return None
    return float(hit.bounding_box()[5])


def rib(s: Solid, path_contour, thickness: float, top: float | None = None, extend: bool = True,
        tol: float = 0.05) -> Solid:
    """Nervure (RIB, WEB) : mur d'épaisseur `thickness` centré sur un trait
    du plan, du dessous du volume jusqu'à `top` (défaut : son dessus),
    réuni au volume. `extend` : un trait ouvert est prolongé à ses deux bouts
    et le mur coupé par l'enveloppe convexe du volume (il va d'une paroi à
    l'autre) ; sinon il est coupé par le volume englobant."""
    from .geom import Contour, Line
    t = float(thickness)
    if not t > 0:
        raise SolidError('épaisseur de la nervure nulle')
    x0, y0, zb, x1, y1, zt = s.bounds()
    z1 = zt if top is None else float(top)
    if not z1 > zb + 1e-6:
        raise SolidError('la nervure s\'arrête sous le volume')
    c = path_contour
    if extend and not c.closed:
        P, _closed = _stations(c, tol)
        if len(P) < 2:
            raise SolidError('trait trop court')
        d = math.hypot(x1 - x0, y1 - y0) + t
        t0 = (P[1] - P[0]) / np.linalg.norm(P[1] - P[0])
        t1 = (P[-1] - P[-2]) / np.linalg.norm(P[-1] - P[-2])
        c = Contour([Line(tuple(map(float, P[0] - t0 * d)), tuple(map(float, P[0])))] + list(c.segments)
                    + [Line(tuple(map(float, P[-1])), tuple(map(float, P[-1] + t1 * d)))])
    wall = polysolid(c, t, z1 - zb, 'centre', zb, tol).manifold()
    limit = s.manifold().hull() if extend else box(x0, y0, zb, x1 - x0, y1 - y0, zt - zb).manifold()
    piece = wall ^ limit
    if piece.is_empty():
        raise SolidError('la nervure ne touche pas le volume')
    out = _solid(s.manifold() + piece, s.name)
    out.color = s.color
    return out


def boss(s: Solid, x: float, y: float, diameter: float, height: float, hole_diameter: float = 0.0,
         hole_depth: float = 0.0, draft: float = 0.0, ribs: int = 0, rib_thickness: float = 0.0,
         rib_length: float = 0.0, rib_offset: float = 0.0, z0: float | None = None) -> Solid:
    """Bossage plastique (BOSS) posé en (x, y) sur le dessus de la matière
    (ou à Z0) : fût rond en dépouille (`draft` degrés), trou de
    `hole_diameter` sur `hole_depth` depuis le haut (0 : toute la hauteur),
    `ribs` nervures rayonnantes d'épaisseur `rib_thickness` (0 : 0,3 × le
    rayon), de portée `rib_length` (0 : le rayon), arrêtées `rib_offset`
    sous le haut. Réuni au volume."""
    M = _m()
    r0, h = float(diameter) / 2, float(height)
    if not (r0 > 0 and h > 0):
        raise SolidError('diamètre et hauteur du bossage : positifs')
    base = (top_at(s, x, y) if z0 is None else float(z0))
    if base is None:
        base = s.bounds()[2]
    dr = math.radians(float(draft))
    r_top = r0 - h * math.tan(dr)
    if r_top <= 0:
        raise SolidError('la dépouille ferme le bossage avant son haut')
    delta = min(max(h * 0.05, 1e-3), 0.5)                # les outils entrent un peu dans la matière
    tools = [cylinder(x, y, base - delta, r0 + delta * math.tan(dr), h + delta, r_top)]
    n = int(round(ribs))
    if not 0 <= n <= 64:
        raise SolidError('0 à 64 nervures')
    if n:
        t = float(rib_thickness) or r0 * 0.3
        ln = float(rib_length) or r0
        hr = h - float(rib_offset)
        if not (t > 0 and ln > 0 and hr > 0):
            raise SolidError('nervures du bossage : épaisseur, portée et hauteur positives')
        for k in range(n):
            a = 2 * math.pi * k / n
            u, v = np.array([math.cos(a), math.sin(a)]), np.array([-math.sin(a), math.cos(a)])
            pts = [np.array([x, y]) + u * pu + v * pv for pu, pv in
                   ((r0 * 0.5, -t / 2), (r0 + ln, -t / 2), (r0 + ln, t / 2), (r0 * 0.5, t / 2))]
            man = M.Manifold.extrude(M.CrossSection([np.array(pts)]), hr + delta).translate((0, 0, base - delta))
            tools.append(_solid(man, 'Nervure'))
    out = boolean('union', [s] + tools)
    hd = float(hole_diameter)
    if hd > 0:
        rh = hd / 2
        depth = float(hole_depth) or h
        if not (rh < r_top and depth > 0):
            raise SolidError('le trou doit tenir dans le bossage')
        out = boolean('subtract', [out, cylinder(x, y, base + h - depth, rh, depth + delta)])
    out.name, out.color = s.name, s.color
    return out


# --- relief enroulé sur un cylindre (d'après SolidCraft) --------------------------------
def lying_cylinder(s: Solid, tol: float = 0.01):
    """(axe 'x' ou 'y', (centre sur l'autre axe du plan, Z du centre),
    rayon) d'un volume cylindrique couché, d'après son encombrement (largeur
    et hauteur égales), ou None."""
    x0, y0, z0, x1, y1, z1 = s.bounds()
    dz = z1 - z0
    for axis, d, c in (('x', y1 - y0, (y0 + y1) / 2), ('y', x1 - x0, (x0 + x1) / 2)):
        if dz > 0 and abs(d - dz) <= tol * max(d, dz):
            return axis, (c, (z0 + z1) / 2), max(d, dz) / 2
    return None


def wrap_emboss(s: Solid, path, depth: float, deboss: bool = False, axis: str = 'auto', radius: float = 0.0,
                tol: float = 0.02) -> Solid:
    """Relief (EMBOSS) ou gravure des contours fermés de `path`, dessinés
    vus de dessus, enroulés sur le volume cylindrique couché `s` : le long
    de l'axe ('x' ou 'y' ; 'auto' : d'après l'encombrement) rien ne change,
    l'écart à la ligne de dessus devient l'arc parcouru sur le pourtour.
    Relief de `depth` hors de la surface, ou gravure de `depth` dedans ;
    rayon d'après l'encombrement si `radius` est 0."""
    M = _m()
    d = float(depth)
    if not d > 0:
        raise SolidError('profondeur nulle')
    x0, y0, z0, x1, y1, z1 = s.bounds()
    if axis in ('x', 'y'):
        c = (y0 + y1) / 2 if axis == 'x' else (x0 + x1) / 2
        zc, r = (z0 + z1) / 2, (z1 - z0) / 2
    else:
        found = lying_cylinder(s)
        if found is None:
            raise SolidError('le volume n\'est pas un cylindre couché (axe X ou Y)')
        axis, (c, zc), r = found
    if radius > 0:
        r = float(radius)
    if not r > 0 or (deboss and d >= r):
        raise SolidError('gravure plus profonde que le rayon')
    eps = max(0.05, 0.01 * r)                           # l'outil entre un peu dans la matière (relief) ou en sort
    w0, w1 = (-d, eps) if deboss else (-eps, d)
    man = M.Manifold.extrude(region(path, tol), w1 - w0).translate((0.0, 0.0, w0))
    man = man.refine_to_length(max(2 * math.pi * r / SEGMENTS, 0.05))
    flat = Solid.from_manifold(man)
    X, Y, W = flat.verts[:, 0], flat.verts[:, 1], flat.verts[:, 2]
    v = (Y if axis == 'x' else X) - c                   # arc depuis la ligne de dessus
    if np.abs(v).max() >= 0.98 * math.pi * r:
        raise SolidError('le dessin fait plus d\'un demi-tour de part et d\'autre de la ligne de dessus')
    th, rho = v / r, r + W
    a, b = c + rho * np.sin(th), zc + rho * np.cos(th)
    V = np.column_stack([X, a, b]) if axis == 'x' else np.column_stack([a, Y, b])
    tool = _closed_solid(V, flat.tris, 'Relief')
    out = boolean('subtract' if deboss else 'union', [s, tool])
    out.name, out.color = s.name, s.color
    return out


# --- profilés (d'après SolidCraft) -------------------------------------------------------
#: sections de profilé
PROFILES = {'plat': 'Plat', 'rond': 'Rond plein', 'tube_rect': 'Tube rectangulaire', 'tube_rond': 'Tube rond',
            'corniere': 'Cornière', 'u': 'Profilé en U', 'i': 'Poutrelle en I'}


def profile_path(kind: str, width: float, height: float = 0.0, thickness: float = 0.0, web: float = 0.0):
    """Section d'un profilé (core.geom.Path), X en travers et Y en hauteur,
    centrée sur son encombrement : plat et tube rectangulaire `width` ×
    `height`, rond et tube rond de diamètre `width`, cornière (ailes de
    `thickness`), U (âme verticale de `web`, ailes de `thickness` tournées
    vers +X), I (semelles de `thickness`, âme de `web`). Paroi des tubes :
    `thickness` ; `web` 0 : `thickness`."""
    from .geom import Path, circle, polyline, rect
    w, t = float(width), float(thickness)
    h = float(height) if kind not in ('rond', 'tube_rond') else w
    e = float(web) or t
    if not (w > 0 and h > 0):
        raise SolidError('dimensions du profilé nulles')
    if kind not in ('plat', 'rond') and not (0 < t < min(w, h) / 2 and 0 < e < w):
        raise SolidError('épaisseur du profilé : positive et plus petite que la moitié de la section')
    x0, y0 = -w / 2, -h / 2
    if kind == 'plat':
        cs = [rect(x0, y0, w, h)]
    elif kind == 'rond':
        cs = [circle((0.0, 0.0), w / 2)]
    elif kind == 'tube_rect':
        cs = [rect(x0, y0, w, h), rect(x0 + t, y0 + t, w - 2 * t, h - 2 * t)]
    elif kind == 'tube_rond':
        cs = [circle((0.0, 0.0), w / 2), circle((0.0, 0.0), w / 2 - t)]
    elif kind == 'corniere':
        pts = [(0, 0), (w, 0), (w, t), (t, t), (t, h), (0, h)]
        cs = [polyline([(x0 + x, y0 + y) for x, y in pts], closed=True)]
    elif kind == 'u':
        pts = [(0, 0), (w, 0), (w, t), (e, t), (e, h - t), (w, h - t), (w, h), (0, h)]
        cs = [polyline([(x0 + x, y0 + y) for x, y in pts], closed=True)]
    elif kind == 'i':
        a, b = (w - e) / 2, (w + e) / 2
        pts = [(0, 0), (w, 0), (w, t), (b, t), (b, h - t), (w, h - t), (w, h), (0, h), (0, h - t), (a, h - t),
               (a, t), (0, t)]
        cs = [polyline([(x0 + x, y0 + y) for x, y in pts], closed=True)]
    else:
        raise SolidError(f'profilé inconnu : {kind}')
    return Path(cs)


def member(path_contour, kind: str, width: float, height: float = 0.0, thickness: float = 0.0, web: float = 0.0,
           z: float = 0.0, on_plane: bool = True, tol: float = 0.05) -> Solid:
    """Profilé (FRAME MEMBER) couché le long d'un contour du plan, ouvert
    ou fermé, coins en onglet : posé à Z par le dessous de sa section
    (`on_plane`) ou par son centre. X de la section : à gauche du trait."""
    prof = profile_path(kind, width, height, thickness, web)
    h = float(width) if kind in ('rond', 'tube_rond') else float(height)
    s = sweep(path_contour, prof, z=float(z), base=(0.0, -h / 2 if on_plane else 0.0), tol=tol)
    s.name = PROFILES.get(kind, 'Profilé')
    return s


def post(x: float, y: float, z0: float, length: float, kind: str, width: float, height: float = 0.0,
         thickness: float = 0.0, web: float = 0.0, angle: float = 0.0, tol: float = 0.02) -> Solid:
    """Poteau : profilé vertical de `length` posé en (x, y) à Z0, sa section
    tournée de `angle` degrés et centrée sur le point."""
    from .geom import Affine
    if not float(length) > 0:
        raise SolidError('longueur du poteau nulle')
    prof = profile_path(kind, width, height, thickness, web)
    prof = prof.transformed(Affine.translation(x, y) @ Affine.rotation(float(angle)))
    s = extrude(prof, float(length), float(z0), tol=tol)
    s.name = PROFILES.get(kind, 'Profilé')
    return s


# --- pièces plastiques : lèvre, rainure, clip, appui (d'après SolidCraft) ------------------
def _ring_area(p: np.ndarray) -> float:
    x, y = p[:, 0], p[:, 1]
    return 0.5 * float((x * np.roll(y, -1) - np.roll(x, -1) * y).sum())


def _plastic_bite(size: float) -> float:
    """Entrée d'une pièce plastique dans la matière qu'elle rejoint."""
    return min(max(size * 0.05, 1e-3), 0.5)


def lip(s: Solid, width: float, height: float, groove: bool = False, gap: float = 0.0,
        outside: bool = False) -> Solid:
    """Lèvre (LIP : bande levée de `height`) ou rainure (GROOVE : bande
    creusée) sur le dessus d'un volume coqué, contre l'arête intérieure de
    son bord (autour de l'ouverture) ou, `outside`, contre l'arête
    extérieure. La rainure est élargie et creusée de `gap` (jeu) : la lèvre
    d'une moitié entre dans la rainure de l'autre."""
    M = _m()
    w, h, g = float(width), float(height), float(gap)
    what = 'de la rainure' if groove else 'de la lèvre'
    if not (w > 0 and h > 0):
        raise SolidError(f'largeur et hauteur {what} : positives')
    if g < 0:
        raise SolidError('le jeu de la rainure ne peut pas être négatif')
    zb, zt = s.bounds()[2], s.bounds()[5]
    polys = [np.asarray(p, dtype=float) for p in s.manifold().slice(zt - max(1e-3, (zt - zb) * 1e-4)).to_polygons()]
    outers = sorted((p for p in polys if _ring_area(p) > 0), key=_ring_area, reverse=True)
    if not outers:
        raise SolidError('pas de bord sur le dessus du volume')
    O = M.CrossSection([outers[0]])
    holes = [hc for p in polys if _ring_area(p) < 0
             and ((hc := M.CrossSection([p[::-1]])) ^ O).area() > 0.5 * hc.area()]
    holes.sort(key=lambda c: c.area(), reverse=True)
    if len(holes) > 1 and holes[1].area() > 0.5 * holes[0].area():   # un bord court autour d'une seule ouverture
        raise SolidError('le dessus a plusieurs ouvertures semblables : pas de bord unique')
    if not outside and not holes:
        raise SolidError('le dessus n\'a pas d\'ouverture : choisissez un volume coqué ouvert')
    bw = w + g if groove else w
    free = bw if groove else 0.0                         # la rainure déborde dans le vide : pas de paroi confondue
    J = M.JoinType.Miter
    if outside:
        band = O.offset(free, J) - O.offset(-bw, J)
        fits = not holes or (holes[0] - O.offset(-bw, J)).area() < 1e-6
    else:
        band = holes[0].offset(bw, J) - holes[0].offset(-free, J)
        fits = (holes[0].offset(bw, J) - O).area() < 1e-6
    if not fits:
        raise SolidError(f'largeur {what} : plus que le bord')
    d = _plastic_bite(h)
    if groove:
        out = s.manifold() - M.Manifold.extrude(band, h + g + d).translate((0, 0, zt - h - g))
    else:
        out = s.manifold() + M.Manifold.extrude(band, h + d).translate((0, 0, zt - d))
    r = _solid(out, s.name)
    r.color = s.color
    return r


def snap_fit(x: float, y: float, z0: float, length: float, thickness: float, width: float, catch_depth: float,
             catch_length: float, angle: float = 0.0, base_height: float = 0.0, join: bool = False) -> Solid:
    """Clip (SNAP FIT) : bras vertical en porte-à-faux de `length` au-dessus
    de Z0, d'épaisseur `thickness` et de largeur `width`, centré sur (x, y),
    crochet en bout qui dépasse de `catch_depth` vers `angle` (degrés dans
    le plan) sur `catch_length` : face d'arrêt plate, rampe jusqu'au bout.
    Le pied descend de `base_height` sous Z0 ; `join` : il entre en plus un
    peu dans la matière qu'il rejoint."""
    M = _m()
    ln, t, w, cd, cl = (float(v) for v in (length, thickness, width, catch_depth, catch_length))
    bh = float(base_height)
    if not (min(ln, t, w, cd, cl) > 0 and bh >= 0):
        raise SolidError('dimensions du clip : positives')
    if not cl < ln:
        raise SolidError('le crochet doit être plus court que le bras')
    y0 = -bh - (_plastic_bite(ln) if join else 0.0)
    side = np.array([(-t / 2, y0), (t / 2, y0), (t / 2, ln - cl), (t / 2 + cd, ln - cl), (t / 2, ln), (-t / 2, ln)])
    man = M.Manifold.extrude(M.CrossSection([side]), w).translate((0, 0, -w / 2))
    man = man.rotate((90.0, 0.0, float(angle))).translate((float(x), float(y), float(z0)))   # profil debout
    return _solid(man, 'Clip')


def rest(x: float, y: float, z0: float, width: float, height: float, length: float = 0.0, angle: float = 0.0,
         draft: float = 0.0, thickness: float = 0.0, join: bool = False) -> Solid:
    """Appui (REST) : plot rond de diamètre `width` ou, `length` > 0,
    rectangulaire `length` × `width` (longueur vers `angle` degrés), centré
    sur (x, y), haut de `height` au-dessus de Z0, en dépouille (`draft`
    degrés), plein ou creux (paroi `thickness`), mesuré à Z0 ; `join` : le
    pied entre un peu dans la matière qu'il rejoint."""
    from .geom import Affine, Path, circle, rect
    w, h, ln, t = float(width), float(height), float(length), float(thickness)
    if not (w > 0 and h > 0 and ln >= 0 and t >= 0):
        raise SolidError('dimensions de l\'appui : positives')
    small = min(w, ln or w)
    if t and 2 * t >= small:
        raise SolidError('la paroi de l\'appui doit être plus mince que sa demi-largeur')
    dr = math.radians(float(draft))
    if not abs(dr) < 1.0:
        raise SolidError('dépouille de l\'appui : moins de 57°')
    if 2 * h * math.tan(dr) >= (t or small):
        raise SolidError('la dépouille ferme l\'appui avant son haut')
    b = _plastic_bite(h) if join else 0.0
    e = b * math.tan(dr)                                 # mesuré à Z0 : le pied, plus bas, est plus large

    def shape(grow):
        if ln:
            return rect(-ln / 2 - grow, -w / 2 - grow, ln + 2 * grow, w + 2 * grow)
        return circle((0.0, 0.0), w / 2 + grow)

    path = Path([shape(e)] + ([shape(-t - e)] if t else []))
    path = path.transformed(Affine.translation(float(x), float(y)) @ Affine.rotation(float(angle)))
    out = extrude(path, h + b, float(z0) - b, taper_deg=float(draft))
    out.name = 'Appui'
    return out


# --- tôle pliée et développé (d'après SolidCraft) ---------------------------------------
def _sheet_chain(path_contour, thickness: float, radius: float, left: bool):
    """Plis d'une tôle tracée par une chaîne ouverte de traits droits (une
    face de la tôle, matière à gauche ou à droite) : (sommets, plis, longueurs
    des traits) ; un pli par sommet intérieur : (angle signé en radians,
    rayon sur la chaîne, distance de tangence). Le rayon intérieur est
    `radius` : la chaîne a `radius` + `thickness` quand elle tourne vers la
    matière (elle est la face extérieure du pli)."""
    from .geom import Line
    c = path_contour
    if c.closed or not c.segments or not all(isinstance(g, Line) for g in c.segments):
        raise SolidError('tôle : une chaîne ouverte de traits droits')
    t, r = float(thickness), float(radius)
    if not (t > 0 and r >= 0):
        raise SolidError('tôle : épaisseur positive, rayon de pliage positif ou nul')
    P = [np.asarray(c.segments[0].p0, dtype=float)]
    for g in c.segments:
        q = np.asarray(g.p1, dtype=float)
        if np.linalg.norm(q - P[-1]) > 1e-9:
            P.append(q)
    if len(P) < 2:
        raise SolidError('tôle : trait de longueur nulle')
    s = 1.0 if left else -1.0
    bends = []
    for i in range(1, len(P) - 1):
        a, b = P[i] - P[i - 1], P[i + 1] - P[i]
        th = math.atan2(a[0] * b[1] - a[1] * b[0], float(a @ b))
        if abs(th) < 1e-9:
            bends.append((0.0, 0.0, 0.0))
            continue
        if abs(th) > math.pi - 1e-3:
            raise SolidError('tôle : pli rabattu à 180° impossible')
        rc = r + t if th * s > 0 else r
        bends.append((th, rc, rc * math.tan(abs(th) / 2)))
    lengths = [float(np.linalg.norm(P[i + 1] - P[i])) for i in range(len(P) - 1)]
    for i, ln in enumerate(lengths):
        used = (bends[i - 1][2] if i >= 1 else 0.0) + (bends[i][2] if i < len(bends) else 0.0)
        if used > ln + 1e-9:
            raise SolidError('tôle : trait trop court pour ses plis')
    return P, bends, lengths


def _sheet_hems(bends, lengths, hems, gap: float):
    """Ourlets (longueur au début, à la fin, jeu) vérifiés : chaque retour
    tient sur le plat de son trait."""
    hs, he = (float(v) for v in hems)
    g = float(gap)
    if hs < 0 or he < 0 or g < 0:
        raise SolidError('ourlet : longueur et jeu positifs ou nuls')
    if len(lengths) == 1:
        ok = hs + he <= lengths[0] + 1e-9
    else:
        ok = hs <= lengths[0] - bends[0][2] + 1e-9 and he <= lengths[-1] - bends[-1][2] + 1e-9
    if not ok:
        raise SolidError('ourlet : plus long que le plat de son trait')
    return hs, he, g


def sheet_section(path_contour, thickness: float, radius: float, left: bool = True, tol: float = 0.02,
                  hems=(0.0, 0.0), gap: float = 0.0) -> np.ndarray:
    """Section d'une tôle pliée vue de dessus (sommets, sens direct) : la
    chaîne de traits est une face, l'autre à `thickness` du côté de la
    matière, plis concentriques au rayon intérieur `radius`. `hems` :
    longueurs des ourlets au début et à la fin (0 : sans), retours à 180°
    vers la matière à `gap` de l'autre face."""
    P, bends, lengths = _sheet_chain(path_contour, thickness, radius, left)
    hs, he, g = _sheet_hems(bends, lengths, hems, gap)
    s, t = (1.0 if left else -1.0), float(thickness)

    def unit(v):
        return v / np.linalg.norm(v)

    def lnorm(d):
        return np.array([-d[1], d[0]])

    face, other = [], []
    d = unit(P[1] - P[0])
    face.append(P[0])
    other.append(P[0] + s * t * lnorm(d))
    for k, (th, rc, tg) in enumerate(bends):
        if th == 0.0:
            continue
        i = k + 1
        din = unit(P[i] - P[i - 1])
        turn = 1.0 if th > 0 else -1.0
        u0 = -turn * lnorm(din)                          # du centre du pli vers son début
        C = P[i] - din * tg - u0 * rc
        rho = rc + t
        step = 2 * math.acos(max(-1.0, 1 - tol / rho)) if rho > tol else math.pi / 8
        n = max(2, int(math.ceil(abs(th) / step)))
        for j in range(n + 1):
            a = th * j / n
            u = np.array([u0[0] * math.cos(a) - u0[1] * math.sin(a), u0[0] * math.sin(a) + u0[1] * math.cos(a)])
            p = C + u * rc
            face.append(p)
            other.append(p - s * t * turn * u)           # normale à gauche de la tangente : -turn·u
    d = unit(P[-1] - P[-2])
    face.append(P[-1])
    other.append(P[-1] + s * t * lnorm(d))

    def hem(E, dd, m, length):
        """Ourlet au bout E (dd : sens sortant ; m : de la face tracée vers la
        matière) : (face tracée, autre face) depuis le bout."""
        rc = g / 2
        ro, C = rc + t, E + m * (t + rc)
        step = 2 * math.acos(max(-1.0, 1 - tol / ro)) if ro > tol else math.pi / 8
        n = max(4, int(math.ceil(math.pi / step)))
        us = [-m * math.cos(math.pi * j / n) + dd * math.sin(math.pi * j / n) for j in range(n + 1)]
        return ([C + u * ro for u in us] + [C + m * ro - dd * length],
                [C + u * rc for u in us] + [C + m * rc - dd * length])

    if hs > 0:
        d0 = unit(P[1] - P[0])
        f0, o0 = hem(P[0], -d0, s * lnorm(d0), hs)
        face, other = f0[::-1] + face, o0[::-1] + other
    if he > 0:
        f1, o1 = hem(P[-1], d, s * lnorm(d), he)
        face, other = face + f1, other + o1
    ring = [q for q in face + other[::-1]]
    ring = np.array([q for j, q in enumerate(ring) if np.linalg.norm(q - ring[j - 1]) > 1e-9])
    x, y = ring[:, 0], ring[:, 1]
    if (x * np.roll(y, -1) - np.roll(x, -1) * y).sum() < 0:
        ring = ring[::-1].copy()
    return ring


def sheet(path_contour, thickness: float, height: float, radius: float, left: bool = True, z: float = 0.0,
          tol: float = 0.02, hems=(0.0, 0.0), gap: float = 0.0) -> Solid:
    """Tôle pliée (CONTOUR FLANGE) debout, haute de `height` à partir de Z,
    le long d'une chaîne ouverte de traits droits, ourlets en option (voir
    sheet_section)."""
    M = _m()
    h = float(height)
    if not h > 0:
        raise SolidError('tôle : hauteur positive')
    ring = sheet_section(path_contour, thickness, radius, left, tol, hems, gap)
    man = M.Manifold.extrude(M.CrossSection([ring]), h).translate((0, 0, float(z)))
    return _solid(man, 'Tôle pliée')


def sheet_flat(path_contour, thickness: float, radius: float, k_factor: float = 0.44, left: bool = True,
               hems=(0.0, 0.0), gap: float = 0.0):
    """Développé d'une tôle pliée : (longueur développée, plis) ; chaque pli
    (abscisse de son axe, angle en degrés, début et fin de sa zone) le long
    du flan, la zone valant angle × (rayon intérieur + K × épaisseur) — un
    ourlet : π × (jeu / 2 + K × épaisseur), à 180°. Angle positif : la face
    tracée est à l'extérieur du pli."""
    P, bends, lengths = _sheet_chain(path_contour, thickness, radius, left)
    hs, he, g = _sheet_hems(bends, lengths, hems, gap)
    k, r, t = float(k_factor), float(radius), float(thickness)
    if not 0 <= k <= 1:
        raise SolidError('facteur K : entre 0 et 1')
    s = 1.0 if left else -1.0
    bh = math.pi * (g / 2 + k * t)
    x, out = 0.0, []
    if hs > 0:
        out.append((hs + bh / 2, 180.0, hs, hs + bh))
        x = hs + bh
    for i, ln in enumerate(lengths):
        x += ln - (bends[i - 1][2] if i >= 1 else 0.0) - (bends[i][2] if i < len(bends) else 0.0)
        if i < len(bends) and bends[i][0] != 0.0:
            th = bends[i][0]
            ba = abs(th) * (r + k * t)
            out.append((x + ba / 2, math.degrees(abs(th)) * (1 if th * s > 0 else -1), x, x + ba))
            x += ba
    if he > 0:
        out.append((x + bh / 2, 180.0, x, x + bh))
        x += bh + he
    return x, out


def _tray_base(contour, thickness: float, height: float, radius: float):
    """Fond d'un bac en tôle : le contour (convexe, traits droits, sens
    direct) rentré de rayon + épaisseur, côté par côté (sommets)."""
    from .geom import Line
    t, h, r = float(thickness), float(height), float(radius)
    if not (t > 0 and r >= 0):
        raise SolidError('tôle : épaisseur positive, rayon de pliage positif ou nul')
    if not h > r + t:
        raise SolidError('bac : bords plus hauts que rayon + épaisseur')
    if not contour.closed or not contour.segments or not all(isinstance(g, Line) for g in contour.segments):
        raise SolidError('bac : un contour fermé de traits droits')
    P = [np.asarray(g.p0, dtype=float) for g in contour.segments]
    P = [p for i, p in enumerate(P) if np.linalg.norm(p - P[i - 1]) > 1e-9]
    if _ring_area(np.array(P)) < 0:
        P = P[::-1]
    keep = []
    for i, p in enumerate(P):
        a, b = p - P[i - 1], P[(i + 1) % len(P)] - p
        cr = a[0] * b[1] - a[1] * b[0]
        if cr < -1e-9 * np.linalg.norm(a) * np.linalg.norm(b):
            raise SolidError('bac : contour convexe seulement')
        if abs(cr) > 1e-9 * np.linalg.norm(a) * np.linalg.norm(b) or float(a @ b) < 0:
            keep.append(p)                               # sommets alignés retirés
    P = np.array(keep)
    if len(P) < 3:
        raise SolidError('bac : contour plat')
    d, n = r + t, len(P)
    lines = []
    for i in range(n):
        e = (P[(i + 1) % n] - P[i]) / np.linalg.norm(P[(i + 1) % n] - P[i])
        lines.append((P[i] + np.array([-e[1], e[0]]) * d, e))
    Q = []
    for i in range(n):
        (p1, e1), (p2, e2) = lines[i - 1], lines[i]
        w = p2 - p1
        Q.append(p1 + e1 * (w[0] * e2[1] - w[1] * e2[0]) / (e1[0] * e2[1] - e1[1] * e2[0]))
    Q = np.array(Q)
    for i in range(n):
        if float((Q[(i + 1) % n] - Q[i]) @ (P[(i + 1) % n] - P[i])) <= 1e-9:
            raise SolidError('bac : contour trop petit pour ses bords')
    return Q


def tray(contour, thickness: float, height: float, radius: float, z: float = 0.0, tol: float = 0.02) -> Solid:
    """Bac en tôle (SHEET BASE + EDGE FLANGE) : fond plat à Z dans le
    contour (convexe, traits droits) et, sur chaque côté, un bord tombé
    relevé à 90° au rayon intérieur `radius`, haut de `height` sous tout ;
    le contour donne l'extérieur des bords, coins ouverts."""
    M = _m()
    Q = _tray_base(contour, thickness, height, radius)
    t, h, r, z = float(thickness), float(height), float(radius), float(z)
    ro = r + t
    n = max(2, int(math.ceil((math.pi / 2) / (2 * math.acos(max(-1.0, 1 - tol / ro)))))) if ro > tol else 2
    ph = [math.pi / 2 * j / n for j in range(n + 1)]
    eps = 0.01 * t                                       # le bord entre un peu dans le fond
    sec = ([(-eps, 0.0)] + [(ro * math.sin(a), ro - ro * math.cos(a)) for a in ph] + [(ro, h), (r, h)]
           + [(r * math.sin(a), ro - r * math.cos(a)) for a in ph[::-1]] + [(-eps, t)])
    sec = np.array([q for i, q in enumerate(sec) if i == 0 or math.dist(q, sec[i - 1]) > 1e-9])
    cs = M.CrossSection([sec])
    out = M.Manifold.extrude(M.CrossSection([Q]), t).translate((0, 0, z))
    for i in range(len(Q)):
        A, B = Q[i], Q[(i + 1) % len(Q)]
        ln = float(np.linalg.norm(B - A))
        e = (B - A) / ln
        no = np.array([e[1], -e[0]])                     # normale extérieure (contour en sens direct)
        m = np.array([[no[0], 0.0, -e[0], B[0]], [no[1], 0.0, -e[1], B[1]], [0.0, 1.0, 0.0, z]])
        out = out + M.Manifold.extrude(cs, ln).transform(m)
    return _solid(out, 'Bac en tôle')


def tray_flat(contour, thickness: float, height: float, radius: float, k_factor: float = 0.44):
    """Développé du bac en tôle : (flan en croix, sommets en sens direct ;
    axes de pli [(début, fin)]). Chaque côté du fond est prolongé de la zone
    de pli, π/2 × (rayon intérieur + K × épaisseur), puis du bord droit."""
    Q = _tray_base(contour, thickness, height, radius)
    t, h, r, k = float(thickness), float(height), float(radius), float(k_factor)
    if not 0 <= k <= 1:
        raise SolidError('facteur K : entre 0 et 1')
    ba = math.pi / 2 * (r + k * t)
    ext = ba + h - r - t
    ring, axes = [], []
    for i in range(len(Q)):
        A, B = Q[i], Q[(i + 1) % len(Q)]
        e = (B - A) / np.linalg.norm(B - A)
        no = np.array([e[1], -e[0]])
        ring += [A, A + no * ext, B + no * ext, B]
        axes.append((tuple(map(float, A + no * ba / 2)), tuple(map(float, B + no * ba / 2))))
    ring = np.array([q for i, q in enumerate(ring) if np.linalg.norm(q - ring[i - 1]) > 1e-9])
    return ring, axes


FOLD_POSITIONS = ('axe', 'debut', 'fin', 'moule')


def _cs_pts(cs) -> np.ndarray:
    polys = [np.asarray(q, dtype=float) for q in cs.to_polygons() if len(q)]
    return np.concatenate(polys) if polys else np.zeros((0, 2))


def _cs_centroid(cs) -> np.ndarray:
    a, c = 0.0, np.zeros(2)
    for q in cs.to_polygons():
        q = np.asarray(q, dtype=float)
        if len(q) < 3:
            continue
        x, y = q[:, 0], q[:, 1]
        x2, y2 = np.roll(x, -1), np.roll(y, -1)
        w = x * y2 - x2 * y
        a += w.sum() / 2
        c += np.array([((x + x2) * w).sum(), ((y + y2) * w).sum()]) / 6
    return c / a if abs(a) > 1e-12 else _cs_pts(cs).mean(axis=0)


def _fold_map(P, n, d, s0, ba, th, t, r, k, down):
    """Pli d'une tôle plate (épaisseur t sur Z = 0) : P (N, 3) → (N, 3).
    En deçà de la zone (n·p < s0) rien ne bouge, dans la zone la tôle
    s'enroule autour de l'axe du pli, au-delà elle tourne d'un bloc."""
    u = P[:, :2] @ n - s0
    v = P[:, :2] @ d
    z = P[:, 2]
    rn = r + k * t
    phi = np.clip(u, 0.0, ba) / rn
    rho = r + z if down else r + t - z
    X, Z = rho * np.sin(phi), (-r + rho * np.cos(phi)) if down else (t + r - rho * np.cos(phi))
    a, c, s = u - ba, math.cos(th), math.sin(th)
    if down:
        Xr, Zr = a * c + (z + r) * s, -r - a * s + (z + r) * c
    else:
        Xr, Zr = a * c - (z - t - r) * s, t + r + a * s + (z - t - r) * c
    X = np.where(u <= 0, u, np.where(u >= ba, Xr, X))
    Z = np.where(u <= 0, z, np.where(u >= ba, Zr, Z))
    return np.column_stack([(s0 + X)[:, None] * n + v[:, None] * d, Z])


def sheet_fold(path, lines, thickness: float, radius: float, angle: float = 90.0, k_factor: float = 0.44,
               position: str = 'axe', down: bool = False, z: float = 0.0, tol: float = 0.02) -> Solid:
    """Tôle plate pliée le long de traits (SHEET FOLD, d'après SolidCraft) :
    le flan (contours fermés de `path`, les trous restent des trous), épais
    de `thickness` sur Z, plié de `angle` degrés vers le haut (vers le bas
    avec `down`) le long de chaque trait de `lines` [((x0, y0), (x1, y1))],
    au rayon intérieur `radius`. La plus grande partie reste à plat, chaque
    pli lève le côté le plus petit ; la zone de pli, large de
    angle × (rayon + K × épaisseur), a le trait au milieu (`position`
    'axe'), à son début côté fixe ('debut'), à sa fin ('fin') ou sur la
    ligne de moule, où se croisent les faces extérieures prolongées
    ('moule'). Un trait plie les morceaux du flan qu'il traverse."""
    M = _m()
    t, r, k, th = float(thickness), float(radius), float(k_factor), math.radians(float(angle))
    if t <= 0:
        raise SolidError('épaisseur nulle')
    if r <= 0:
        raise SolidError('rayon de pliage : plus grand que 0')
    if not 1e-6 < th <= math.pi + 1e-9:
        raise SolidError('angle de pliage : entre 0 et 180°')
    if not 0 <= k <= 1:
        raise SolidError('facteur K : entre 0 et 1')
    if position not in FOLD_POSITIONS:
        raise SolidError(f'position du pli inconnue : {position}')
    if position == 'moule' and th > math.pi - 1e-6:
        raise SolidError('ligne de moule indéfinie à 180°')
    if not lines:
        raise SolidError('aucun trait de pli')
    plate = region(path, tol)
    if len(plate.decompose()) != 1:
        raise SolidError("le flan doit être d'un seul tenant")
    bx0, by0, bx1, by1 = plate.bounds()
    centre, R = np.array([(bx0 + bx1) / 2, (by0 + by1) / 2]), math.hypot(bx1 - bx0, by1 - by0) + 1.0
    ba = th * (r + k * t)
    folds = []
    for a, b in lines:
        a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
        if np.linalg.norm(b - a) < 1e-9:
            raise SolidError('trait de pli de longueur nulle')
        d = (b - a) / np.linalg.norm(b - a)
        folds.append({'d': d, 'n': np.array([-d[1], d[0]]), 'a': a, 'span': sorted((a @ d, b @ d))})

    def strip(f, s0, w):
        n, d, vc = f['n'], f['d'], centre @ f['d']
        q = [s0 * n + (vc - R) * d, (s0 + w) * n + (vc - R) * d, (s0 + w) * n + (vc + R) * d, s0 * n + (vc + R) * d]
        return M.CrossSection([np.array(q)], M.FillRule.EvenOdd)

    dl = min(0.01, ba / 10)

    def zones_of(i, s0, w):
        """Morceaux du flan dans la bande [s0, s0 + w] du trait i que le trait
        traverse."""
        f, out = folds[i], []
        for c in (plate ^ strip(f, s0, w)).decompose():
            q = _cs_pts(c) @ f['d']
            if c.area() > 1e-9 and q.max() >= f['span'][0] - 1e-6 and q.min() <= f['span'][1] + 1e-6:
                out.append(c)
        if not out:
            raise SolidError(f'le trait de pli {i + 1} ne traverse pas le flan')
        return out

    def split(zs, i, mid):
        """Le flan sans les zones `zs` (du trait i) : parties à plat, et pour
        chaque zone les parties d'avant et d'après (de part et d'autre de
        `mid` le long de la normale du trait)."""
        rest = [p for p in (plate - M.CrossSection.batch_boolean(zs, M.OpType.Add)).decompose() if p.area() > 1e-9]
        sides = []
        for c, ic, m in zip(zs, i, mid):
            grow, lo, hi = c.offset(dl, M.JoinType.Miter), [], []
            for j, p in enumerate(rest):
                touch = grow ^ p
                if touch.area() > dl * dl:
                    (lo if _cs_centroid(touch) @ folds[ic]['n'] < m else hi).append(j)
            if not lo or not hi:
                raise SolidError(f'le pli {ic + 1} doit traverser le flan, de la matière des deux côtés de sa zone')
            sides.append((lo, hi))
        return rest, sides

    # 1) chaque trait seul, coupe fine : son côté le plus petit se lève (la normale du trait y pointe)
    for i, f in enumerate(folds):
        l0 = f['a'] @ f['n']
        zs = zones_of(i, l0 - dl / 2, dl)
        rest, sides = split(zs, [i] * len(zs), [l0] * len(zs))
        lo = {j for s_ in sides for j in s_[0]}
        hi = {j for s_ in sides for j in s_[1]}
        if lo & hi:
            raise SolidError(f'le trait de pli {i + 1} ne sépare pas le flan en deux')
        if sum(rest[j].area() for j in lo) < sum(rest[j].area() for j in hi):
            f['n'] = -f['n']
    # 2) zones à leur place ; reste à plat la plus grande partie du côté fixe de tous les plis
    starts = []
    for f in folds:
        l0 = f['a'] @ f['n']
        starts.append({'axe': l0 - ba / 2, 'debut': l0, 'fin': l0 - ba,
                       'moule': l0 - (r + t) * math.tan(th / 2)}[position])
    per = [zones_of(i, s0, ba) for i, s0 in enumerate(starts)]
    zones = [(i, c) for i, zs in enumerate(per) for c in zs]
    for j, (i, c) in enumerate(zones):
        for i2, c2 in zones[j + 1:]:
            if i2 != i and (c ^ c2).area() > 1e-9:
                raise SolidError('plis trop proches : leurs zones se chevauchent (dégager les coins, ou trait au '
                                 'début de la zone)')
    stays = []
    for i, zs in enumerate(per):
        rest, sides = split(zs, [i] * len(zs), [starts[i] + ba / 2] * len(zs))
        lo = {j for s_ in sides for j in s_[0]}
        if lo & {j for s_ in sides for j in s_[1]}:
            raise SolidError(f'le trait de pli {i + 1} ne sépare pas le flan en deux')
        stays.append(M.CrossSection.batch_boolean([rest[j] for j in lo], M.OpType.Add))
    panels, sides = split([c for _i, c in zones], [i for i, _c in zones], [starts[i] + ba / 2 for i, _c in zones])
    common = [j for j, p in enumerate(panels) if all((p ^ st).area() > p.area() / 2 for st in stays)]
    if not common:
        raise SolidError('plis de sens contraires : aucune partie ne reste à plat')
    fixed = max(common, key=lambda j: panels[j].area())
    nseg = max(2, int(math.ceil(th / (2 * math.acos(max(-1.0, 1 - tol / (r + t))))))) if r + t > tol else 2
    step = ba / nseg
    T, todo, built, parts = {fixed: np.eye(4)}, [fixed], set(), []
    while todo:
        j = todo.pop(0)
        for zi, (i, c) in enumerate(zones):
            if zi in built or j not in sides[zi][0]:
                continue
            if j in sides[zi][1]:
                raise SolidError('plis de sens contraires : aucune partie ne reste à plat')
            built.add(zi)
            f, s0 = folds[i], starts[i]
            n = f['n']
            d = np.array([-n[1], n[0]])                  # repère direct : la zone garde son sens
            # la zone, débordant d'un pas sur les parties voisines, maillée en bandes d'un pas le long du pli
            others = [c2 for zj, (i2, c2) in enumerate(zones) if zj != zi]
            room = plate - M.CrossSection.batch_boolean(others, M.OpType.Add) if others else plate
            wide = room ^ strip(f, s0 - step, ba + 2 * step) ^ c.offset(2 * step, M.JoinType.Miter)
            pts = _cs_pts(wide)
            vc = float((pts @ d).mean())
            # recoupée au pas en travers du pli seulement : le long du pli et dans l'épaisseur, écrasée le temps
            # du découpage, la zone garde ses arêtes entières
            sc = 1e-4 * step / max(float(np.abs(pts @ d - vc).max()), t, 1.0)
            loc = np.array([[n[0], n[1], 0.0, -s0], [sc * d[0], sc * d[1], 0.0, -sc * vc], [0.0, 0.0, sc, 0.0]])
            m = M.Manifold.extrude(wide, t).transform(loc).refine_to_length(step * (1 + 1e-6))
            Tj = T[j]

            def warp(V, n=n, d=d, s0=s0, vc=vc, sc=sc, Tj=Tj):
                flat = np.column_stack([(V[:, 0] + s0)[:, None] * n + (V[:, 1] / sc + vc)[:, None] * d, V[:, 2] / sc])
                q = _fold_map(flat, n, d, s0, ba, th, t, r, k, down)
                return q @ Tj[:3, :3].T + Tj[:3, 3]
            parts.append(m.warp_batch(warp))
            F = np.eye(4)                                # au-delà de la zone : la partie tourne d'un bloc
            probe = np.vstack([np.zeros(3), np.eye(3)])
            probe[:, :2] += (s0 + ba + 1.0) * n
            img = _fold_map(probe, n, d, s0, ba, th, t, r, k, down)
            F[:3, :3] = (img[1:] - img[0]).T
            F[:3, 3] = img[0] - F[:3, :3] @ probe[0]
            for h in sides[zi][1]:
                if h not in T:
                    T[h] = Tj @ F
                    todo.append(h)
    if len(T) != len(panels) or len(built) != len(zones):
        raise SolidError('plis de sens contraires : aucune partie ne reste à plat')
    for j, p in enumerate(panels):
        parts.append(M.Manifold.extrude(p, t).transform(T[j][:3]))
    out = M.Manifold.batch_boolean(parts, M.OpType.Add)
    if abs(z) > 1e-12:
        out = out.translate((0, 0, z))
    return _solid(out, 'Tôle pliée')
