"""Lier au parcours précédent (gamme TypeEdit) : l'opération ne reprend que la
matière que les parcours d'avant ont laissée — un outil conique nettoie ce
qu'il peut là où la fraise d'avant n'est pas passée.

La matière est simulée (carte des hauteurs, comme `cam.simulate`) avec les
parcours d'avant, puis les mouvements de coupe de l'opération sont rejoués
un à un, par morceaux d'au plus `PIECE` mm : un morceau qui n'enlève rien
(moins de `TOL_Z`) est retiré. Les morceaux gardés sont reliés au fond quand
la liaison ne touche aucune matière (contrôlée sur la carte), sinon par une
remontée au dégagement."""
from __future__ import annotations

import copy
import math

from .model import Move, arc_points

#: matière enlevée en dessous de laquelle un morceau ne sert à rien (mm)
TOL_Z = 0.01
#: longueur des morceaux jugés un par un (mm, au plus)
PIECE = 0.5
#: cellules de la carte au plus (au-delà, le pas grandit et le tri devient approché)
MAX_CELLS = 6_000_000
#: liaison au fond entre deux morceaux gardés : au plus cette longueur (mm), sinon remontée
LINK_MAX = 5.0
#: carte de `remaining_only` : tuiles de TILE × TILE cellules, créées seulement autour des morceaux de l'opération
TILE = 256
#: cellules de toutes les tuiles au plus (simple précision : 4 octets chacune) ; au-delà, le pas grandit
MAX_TILE_CELLS = 24_000_000
#: pas de la carte au-delà duquel le parcours est gardé en entier (mm ; au plus trois fois le pas voulu)
COARSE_MAX = 0.1


def _shifted(tp, dz: float):
    """Copie du parcours `tp` décalée de `dz` en Z."""
    out = copy.copy(tp)
    out.moves = [Move(m.kind, m.x, m.y, m.z + dz, m.cx, m.cy, fin=m.fin) for m in tp.moves]
    return out


def cutting(toolpaths) -> list:
    """Parcours qui creusent (fraises : ni laser ni parcours vide)."""
    return [tp for tp in toolpaths if tp.moves and any(m.kind != 'rapid' and m.z < 0 for m in tp.moves)]


def _pieces(tp, tol: float) -> list:
    """Morceaux de coupe [(a, b, sorte)] : avances, plongées, arcs aplatis, recoupés à `PIECE` mm ; la sorte
    finit par « + » pour une passe de finition (`Move.fin`)."""
    out = []
    prev = None
    for m in tp.moves:
        here = (m.x, m.y, m.z)
        if prev is not None and m.kind != 'rapid' and min(prev[2], m.z) < 0:
            pts = [prev] + (list(arc_points(prev, m, tol)) if m.is_arc else [here])
            for a, b in zip(pts, pts[1:]):
                L = math.hypot(b[0] - a[0], b[1] - a[1])
                kind = ('plunge' if L < 1e-9 else 'feed') + ('+' if getattr(m, 'fin', False) else '')
                n = max(1, int(math.ceil(L / PIECE)))
                for k in range(n):
                    t0, t1 = k / n, (k + 1) / n
                    out.append((tuple(a[i] + (b[i] - a[i]) * t0 for i in range(3)),
                                tuple(a[i] + (b[i] - a[i]) * t1 for i in range(3)), kind))
        prev = here
    return out


def _surface(H, a, b, tool, r: float, x0: float, y0: float, res: float):
    """(fenêtre de la carte, cote de l'outil sur cette fenêtre) pour le segment
    a → b (pointe à la cote du point le plus proche) ; None : hors de la carte
    ou au-dessus de la pièce."""
    import numpy as np
    from .advanced import tool_profile
    if a[2] >= 0 and b[2] >= 0:
        return None
    ny, nx = H.shape
    i0 = max(0, int(math.floor((min(a[0], b[0]) - r - x0) / res)))
    i1 = min(nx - 1, int(math.ceil((max(a[0], b[0]) + r - x0) / res)))
    j0 = max(0, int(math.floor((min(a[1], b[1]) - r - y0) / res)))
    j1 = min(ny - 1, int(math.ceil((max(a[1], b[1]) + r - y0) / res)))
    if i1 < i0 or j1 < j0:
        return None
    X = x0 + np.arange(i0, i1 + 1) * res
    Y = (y0 + np.arange(j0, j1 + 1) * res)[:, None]
    vx, vy = b[0] - a[0], b[1] - a[1]
    L2 = vx * vx + vy * vy
    t = np.clip(((X - a[0]) * vx + (Y - a[1]) * vy) / L2, 0.0, 1.0) if L2 > 1e-18 else np.zeros((len(Y), len(X)))
    d = np.hypot(X - (a[0] + t * vx), Y - (a[1] + t * vy))
    return H[j0:j1 + 1, i0:i1 + 1], a[2] + t * (b[2] - a[2]) + tool_profile(tool, d)


def _gain(surf) -> float:
    """Plus grande épaisseur de matière que l'outil enlève (mm)."""
    return 0.0 if surf is None else max(0.0, float((surf[0] - surf[1]).max()))


class _Tiles:
    """Carte des hauteurs en tuiles, créées seulement là où passent les morceaux de l'opération (fenêtre de l'outil
    comprise) : sur une grande pièce, la matière reste suivie au pas fin autour de l'outil (une seule carte pour toute
    la pièce devenait grossière : des morceaux qui enlevaient encore un peu de matière auraient été retirés)."""

    def __init__(self, pieces, tool, res: float):
        import numpy as np
        deepest = -min(min(a[2], b[2]) for a, b, _k in pieces)
        box = np.array([(min(a[0], b[0]), max(a[0], b[0]), min(a[1], b[1]), max(a[1], b[1])) for a, b, _k in pieces])
        self.coarse = False
        while True:
            r = tool.radius_at(deepest) + 2 * res
            x0, y0 = float(box[:, 0].min()) - r, float(box[:, 2].min()) - r
            keys = self._keys(box, r, x0, y0, res)
            n = len(keys) * TILE * TILE
            if n <= MAX_TILE_CELLS or len(keys) <= 1:
                break
            res *= max(1.05, math.sqrt(n / MAX_TILE_CELLS))
            self.coarse = True
        self.x0, self.y0, self.res = x0, y0, res
        self.tiles = {k: np.zeros((TILE, TILE), dtype=np.float32) for k in keys}

    @staticmethod
    def _keys(box, r: float, x0: float, y0: float, res: float) -> set:
        import numpy as np
        side = TILE * res
        i0 = np.floor((box[:, 0] - r - x0) / side).astype(int)
        i1 = np.floor((box[:, 1] + r - x0) / side).astype(int)
        j0 = np.floor((box[:, 2] - r - y0) / side).astype(int)
        j1 = np.floor((box[:, 3] + r - y0) / side).astype(int)
        one = (i0 == i1) & (j0 == j1)
        keys = set(zip(i0[one].tolist(), j0[one].tolist()))
        for a, b, c, d in zip(i0[~one].tolist(), i1[~one].tolist(), j0[~one].tolist(), j1[~one].tolist()):
            keys.update((i, j) for i in range(a, b + 1) for j in range(c, d + 1))
        return keys

    def parts(self, a, b, r: float) -> tuple:
        """([(tuile, x0, y0)] que recouvre la fenêtre du segment a → b au rayon r, une tuile manque-t-elle ?)"""
        side = TILE * self.res
        i0 = int(math.floor((min(a[0], b[0]) - r - self.x0) / side))
        i1 = int(math.floor((max(a[0], b[0]) + r - self.x0) / side))
        j0 = int(math.floor((min(a[1], b[1]) - r - self.y0) / side))
        j1 = int(math.floor((max(a[1], b[1]) + r - self.y0) / side))
        out, missing = [], False
        for i in range(i0, i1 + 1):
            for j in range(j0, j1 + 1):
                t = self.tiles.get((i, j))
                if t is None:
                    missing = True
                else:
                    out.append((t, self.x0 + i * side, self.y0 + j * side))
        return out, missing

    def stamp(self, a, b, tool, r: float) -> None:
        from . import simulate as SIM
        for t, tx, ty in self.parts(a, b, r)[0]:
            SIM._stamp_segment(t, a, b, tool, r, tx, ty, self.res)

    def surfaces(self, a, b, tool, r: float) -> list:
        return [s for t, tx, ty in self.parts(a, b, r)[0] if (s := _surface(t, a, b, tool, r, tx, ty, self.res)) is not None]


def _gain_on(H, a, b, tool, r: float, x0: float, y0: float, res: float) -> float:
    """Plus grande épaisseur enlevée sur le segment a → b, sur la carte `H` (tableau ou `_Tiles` : une tuile absente
    compte comme de la matière)."""
    if isinstance(H, _Tiles):
        parts, missing = H.parts(a, b, r)
        if missing:
            return math.inf
        return max((_gain(_surface(t, a, b, tool, r, tx, ty, H.res)) for t, tx, ty in parts), default=0.0)
    return _gain(_surface(H, a, b, tool, r, x0, y0, res))


def _grid(pieces, tool, res: float):
    import numpy as np
    deepest = -min(min(a[2], b[2]) for a, b, _k in pieces)
    r = tool.radius_at(deepest) + 2 * res
    x0 = min(min(a[0], b[0]) for a, b, _k in pieces) - r
    y0 = min(min(a[1], b[1]) for a, b, _k in pieces) - r
    x1 = max(max(a[0], b[0]) for a, b, _k in pieces) + r
    y1 = max(max(a[1], b[1]) for a, b, _k in pieces) + r
    coarse = (x1 - x0) * (y1 - y0) / (res * res) > MAX_CELLS
    if coarse:
        res = math.sqrt((x1 - x0) * (y1 - y0) / MAX_CELLS)
    nx, ny = int(math.ceil((x1 - x0) / res)) + 1, int(math.ceil((y1 - y0) / res)) + 1
    return np.zeros((ny, nx)), x0, y0, res, coarse


def remaining_only(tp, previous, setup, op):
    """Le parcours `tp` réduit à ce qui enlève encore de la matière après les
    parcours `previous` (dans l'ordre d'usinage)."""
    from . import simulate as SIM
    z0 = float(getattr(op, 'z_start', 0.0) or 0.0)
    if z0:
        # Z de départ : le dessus de la matière est à z0 (`compute` y décale tout le parcours) ; trié dans le repère du
        # dessus (les parcours d'avant d'une gamme ont le même), dégagements compris, puis rendu à sa cote
        flat = copy.copy(op)
        flat.z_start = 0.0
        out = remaining_only(_shifted(tp, -z0), [_shifted(p, -z0) for p in previous], setup, flat)
        out.moves = _shifted(out, z0).moves
        return out
    from ..core import progress
    prev = cutting(previous)
    if not prev:
        tp.warnings.append('lier au parcours précédent : aucun parcours avant celui-ci — usiné en entier')
        return tp
    tool0 = setup.tool(tp.tool_id)
    if tool0 is None:
        return tp
    tol = max(1e-3, setup.tolerance / 2)
    pieces = _pieces(tp, tol)
    if not pieces:
        return tp
    r_tip = tool0.radius_at(0.0) if tool0.kind == 'conique' else tool0.diameter / 2
    res = min(0.05, max(0.01, r_tip / 3))
    H = _Tiles(pieces, tool0, res)
    if H.coarse and H.res > min(COARSE_MAX, 3 * res):
        # trop grand pour suivre la matière assez finement : des morceaux qui enlèvent encore un peu seraient retirés
        tp.warnings.append(f'lier au parcours précédent : surface trop grande pour suivre la matière finement (pas de '
                           f'{H.res:.3f} mm) — parcours gardé en entier')
        return tp
    x0, y0, res, coarse = H.x0, H.y0, H.res, H.coarse
    # matière laissée par les parcours d'avant (même impression que la simulation)
    for tp_prev in prev:
        tool = SIM.sim_tool(setup, tp_prev, res)
        r = max(tool.body_diameter() / 2, res / 2)
        reach = SIM.cut_radius_of(tool, r, res)
        p0 = None
        for m in tp_prev.moves:
            here = (m.x, m.y, m.z)
            if p0 is not None and m.kind != 'rapid' and min(p0[2], m.z) < 0:
                pts = [p0] + (list(arc_points(p0, m, res / 2)) if m.is_arc else [here])
                for a, b in zip(pts, pts[1:]):
                    if a[2] < 0 or b[2] < 0:
                        H.stamp(a, b, tool, reach(-min(a[2], b[2])))
            p0 = here
    tool = SIM.sim_tool(setup, tp, res)
    r = max(tool.body_diameter() / 2, res / 2)
    reach = SIM.cut_radius_of(tool, r, res)
    # morceaux rejoués dans l'ordre : chacun jugé (et sa liaison contrôlée) sur la matière de ce moment
    import numpy as np
    moves: list = []
    pos = None
    n = 0
    for k, (a, b, kind) in enumerate(pieces):
        if k % 500 == 0:
            progress.step(k, len(pieces), 'Lier au parcours précédent : morceau {0} sur {1}')
        surfs = H.surfaces(a, b, tool, reach(-min(a[2], b[2])))
        if max((_gain(s) for s in surfs), default=0.0) <= TOL_Z:
            continue
        if pos is None or math.dist(pos, a) > 1e-6:
            _join(moves, pos, a, op, tool, H, x0, y0, res, reach)
        for surf in surfs:                                   # la carte suit l'outil
            np.minimum(surf[0], surf[1], out=surf[0])
        moves.append(Move('plunge' if kind.startswith('plunge') else 'feed', *b, fin=kind.endswith('+')))
        pos = b
        n += 1
    if pos is not None and pos[2] < op.safe_z:
        moves.append(Move('rapid', pos[0], pos[1], op.safe_z))
    out = copy.copy(tp)
    out.warnings = list(tp.warnings)
    out.moves = moves
    if not n:
        out.warnings.append('lier au parcours précédent : rien à reprendre, les parcours d\'avant ont tout enlevé')
    else:
        out.warnings.append(f'lier au parcours précédent : {100.0 * n / len(pieces):.0f} % du parcours gardé '
                            '(là où les parcours d\'avant ont laissé de la matière)')
    if coarse:
        out.warnings.append(f'lier au parcours précédent : grande surface, matière suivie au pas de {res:.3f} mm '
                            '(tri approché)')
    return out


def _join(moves: list, pos, a, op, tool, H, x0, y0, res, reach) -> None:
    """Rejoindre le départ `a` d'un morceau gardé : au fond si la liaison ne
    touche aucune matière (carte de ce moment), sinon par le dégagement."""
    if pos is not None and pos[2] < 0 and math.hypot(a[0] - pos[0], a[1] - pos[1]) <= LINK_MAX:
        zl = max(pos[2], a[2])
        p1, p2 = (pos[0], pos[1], zl), (a[0], a[1], zl)
        if _gain_on(H, p1, p2, tool, reach(-zl), x0, y0, res) <= TOL_Z:
            if zl > pos[2] + 1e-9:
                moves.append(Move('feed', *p1))              # remontée : sûre
            moves.append(Move('feed', *p2))
            if a[2] < zl - 1e-9:
                moves.append(Move('plunge', *a))
            return
    safe, clear = op.safe_z, op.clear_z
    if pos is not None and pos[2] < safe:
        moves.append(Move('rapid', pos[0], pos[1], safe))
    moves.append(Move('rapid', a[0], a[1], safe))
    moves.append(Move('rapid', a[0], a[1], clear))
    if a[2] < clear - 1e-9:
        moves.append(Move('plunge', *a))


def cleared(previous, setup, z: float, tol: float):
    """Surface (XY) que les parcours d'avant ont creusée jusqu'à la cote `z`
    ou plus bas (fraises : rayon de l'outil ; cônes : rayon à cette hauteur
    au-dessus de la pointe) ; None : rien."""
    from shapely import union_all
    from shapely.geometry import LineString, MultiPoint
    parts = []
    for tp in cutting(previous):
        tool = setup.tool(tp.tool_id)
        if tool is None or tool.kind == 'laser':
            continue
        lines: dict = {}
        dots: dict = {}
        prev = None
        for m in tp.moves:
            here = (m.x, m.y, m.z)
            if prev is not None and m.kind != 'rapid':
                pts = [prev] + (list(arc_points(prev, m, tol)) if m.is_arc else [here])
                for a, b in zip(pts, pts[1:]):
                    zm = max(a[2], b[2])
                    if zm > z + 1e-6:
                        continue
                    r = round(tool.radius_at(z - zm), 3)
                    if r <= 0:
                        continue
                    if math.hypot(b[0] - a[0], b[1] - a[1]) < 1e-9:
                        dots.setdefault(r, []).append(a[:2])
                        continue
                    runs = lines.setdefault(r, [])
                    if runs and runs[-1][-1] == a[:2]:
                        runs[-1].append(b[:2])
                    else:
                        runs.append([a[:2], b[:2]])
            prev = here
        for r, runs in lines.items():
            parts += [LineString(run).buffer(r, quad_segs=8) for run in runs]
        for r, pts in dots.items():
            parts.append(MultiPoint(pts).buffer(r, quad_segs=8))
    return union_all(parts) if parts else None


def uncleared(reg, previous, setup, z: float, tol: float):
    """La région `reg` sans ce que les parcours d'avant ont creusé jusqu'à `z` ; None : pas de parcours avant."""
    if not cutting(previous or []):
        return None
    done = cleared(previous, setup, z, tol)
    if done is None or done.is_empty:
        return reg
    return reg.difference(done.buffer(-1e-4)).buffer(-1e-3).buffer(1e-3)


def later_bigger(setup, op) -> str:
    """Nom d'une opération active placée APRÈS `op`, sur les mêmes objets, avec
    une fraise plus grosse (la gamme va du plus gros au plus fin) ; '' : aucune."""
    ops = [o for o in setup.operations if o.enabled]
    if op not in ops:
        return ''
    tool = setup.tool(op.tool_id)
    if tool is None:
        return ''
    mine = tool.radius_at(abs(op.depth) or 1.0)
    for o in ops[ops.index(op) + 1:]:
        t = setup.tool(o.tool_id)
        if t is None or t.kind == 'laser' or o.kind in ('instruction', 'texte_machine', 'percage', 'surfacage'):
            continue
        if t.kind != 'conique' and t.diameter / 2 > mine + 1e-9 and _same_place(op, o):
            return o.name or o.kind
    return ''


def _same_place(a, b) -> bool:
    """Les deux opérations usinent-elles (peut-être) les mêmes objets ?"""
    if a.items and b.items:
        return bool(set(a.items) & set(b.items))
    if a.items or b.items:
        return True                                      # objets d'un côté, couleurs de l'autre : prudence
    return not a.sources or not b.sources or bool(set(a.sources) & set(b.sources))
