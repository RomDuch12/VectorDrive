"""Parcellisation : un travail plus grand que la plaque ou que la table, usiné en panneaux.

Deux cas, comme dans TypeEdit : des plaques assemblées ensuite, ou une longue plaque que l'opérateur déplace entre deux
panneaux. La composition est couverte d'une grille de panneaux ; chaque panneau donne son programme, ses parcours coupés
à ses bords et rapportés à sa propre origine.

- **Panneaux** : au plus la taille voulue. Le chevauchement les fait mordre l'un sur l'autre : ce qui tombe dans la bande
  commune est usiné deux fois, pour des bords francs entre deux plaques.
- **Parcours** : chaque mouvement d'usinage est coupé au bord du panneau, Z suivant la pente. Sans chevauchement, ce qui
  est posé exactement sur une frontière n'appartient qu'à un panneau : rien n'est usiné deux fois. Un arc entièrement
  dans le panneau reste un arc ; coupé, il est aplati. À chaque coupure l'outil descend droit, à l'avance de plongée.
- **Liaisons** : refaites par le haut, en rapide, à la hauteur la plus haute du parcours d'origine : la liaison basse
  d'un parcours sur zone surfacée peut ne plus être au-dessus de la bonne zone.
- **Rapport** : à côté des programmes, en clair, l'origine et la taille de chaque panneau, le déplacement de la plaque
  depuis le panneau précédent, les parcours et leur temps.
"""
from __future__ import annotations

import copy
import math
import uuid
from dataclasses import dataclass

from .model import Move, arc_points

EPS = 1e-6
#: premier panneau et sens : bas gauche ou haut gauche, par rangées ou par colonnes
ORDERS = ('bl_rows', 'bl_cols', 'tl_rows', 'tl_cols')
#: zéro du programme d'un panneau
ORIGINS = ('bottom_left', 'top_left', 'center')
MAX_PANELS = 400
#: au-dessus du parcours, s'il n'a aucun rapide pour dire sa hauteur de sécurité (mm)
SAFE_MARGIN = 5.0


@dataclass
class Panel:
    """Un panneau, dans les coordonnées du dessin. `right` et `top` : il a un voisin de ce côté."""
    rank: int
    col: int
    row: int
    x1: float
    y1: float
    x2: float
    y2: float
    right: bool = False
    top: bool = False

    @property
    def width(self) -> float:
        return self.x2 - self.x1

    @property
    def height(self) -> float:
        return self.y2 - self.y1

    def origin(self, where: str = 'bottom_left') -> tuple[float, float]:
        if where == 'center':
            return (self.x1 + self.x2) / 2, (self.y1 + self.y2) / 2
        if where == 'top_left':
            return self.x1, self.y2
        return self.x1, self.y1


def count(extent: float, size: float, overlap: float) -> int:
    """Panneaux d'au plus `size`, mordant de `overlap`, pour couvrir `extent`."""
    if extent <= size + EPS:
        return 1
    return 1 + math.ceil((extent - size - EPS) / (size - overlap))


def plan(bounds, width: float, height: float, overlap: float = 0.0, order: str = 'bl_rows',
         fit_last: bool = True) -> list[Panel]:
    """Les panneaux qui couvrent `bounds` (x0, y0, x1, y1), dans l'ordre d'usinage. Les derniers, réduits à ce qui reste
    (`fit_last`) ou de la taille des autres. ValueError : tailles impossibles, ou trop de panneaux."""
    if bounds is None:
        return []
    if width <= 0 or height <= 0:
        raise ValueError('taille de panneau nulle')
    overlap = max(0.0, overlap)
    if overlap >= width or overlap >= height:
        raise ValueError('chevauchement plus grand que le panneau')
    x0, y0, x1, y1 = bounds
    nx, ny = count(x1 - x0, width, overlap), count(y1 - y0, height, overlap)
    if nx * ny > MAX_PANELS:
        raise ValueError(f'{nx * ny} panneaux')
    from_top = order.startswith('tl')

    def box(i: int, j: int) -> tuple[float, float, float, float]:
        a = x0 + i * (width - overlap)
        b = a + width
        if from_top:
            d = y1 - j * (height - overlap)
            c = d - height
        else:
            c = y0 + j * (height - overlap)
            d = c + height
        if fit_last:
            b, c, d = min(b, x1) if i == nx - 1 else b, max(c, y0) if from_top and j == ny - 1 else c, \
                min(d, y1) if not from_top and j == ny - 1 else d
        return a, c, b, d

    cells = [(i, j) for j in range(ny) for i in range(nx)] if order.endswith('rows') else \
        [(i, j) for i in range(nx) for j in range(ny)]
    out = []
    for rank, (i, j) in enumerate(cells, 1):
        a, c, b, d = box(i, j)
        row = j + 1 if from_top else ny - j
        out.append(Panel(rank, i + 1, row, a, c, b, d, right=i < nx - 1, top=row > 1))
    return out


def path_bounds(toolpaths) -> tuple[float, float, float, float] | None:
    """Cadre de ce qui est usiné : les mouvements hors rapides, cycles de trous compris."""
    xs, ys = [], []
    for tp in toolpaths:
        prev = None
        for m in tp.moves:
            if m.kind != 'rapid' and prev is not None:
                pts = arc_points(prev, m, 0.05) if m.is_arc else [(m.x, m.y, m.z)]
                for p in [prev, *pts]:
                    xs.append(p[0])
                    ys.append(p[1])
            prev = (m.x, m.y, m.z)
        for c in tp.cycles or []:
            if isinstance(c, dict) and c.get('kind') != 'instruction' and 'x' in c and 'y' in c:
                xs.append(float(c['x']))
                ys.append(float(c['y']))
    return (min(xs), min(ys), max(xs), max(ys)) if xs else None


def _clip(a, b, p: Panel):
    """Segment 3D coupé au panneau (bords compris), Z suivant ; None s'il n'y entre pas."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    t0, t1 = 0.0, 1.0
    for pk, qk in ((-dx, a[0] - p.x1), (dx, p.x2 - a[0]), (-dy, a[1] - p.y1), (dy, p.y2 - a[1])):
        if pk == 0.0:
            if qk < -EPS:
                return None
            continue
        r = qk / pk
        if pk < 0.0:
            t0 = max(t0, r)
        else:
            t1 = min(t1, r)
    if t0 > t1:
        return None

    def at(t: float):
        if t <= 0.0:
            return a
        if t >= 1.0:
            return b
        return a[0] + t * dx, a[1] + t * dy, a[2] + t * (b[2] - a[2])
    return at(t0), at(t1)


def _neighbour_owns(a, b, p: Panel) -> bool:
    """Posé sur la frontière de droite ou du haut : au voisin."""
    if p.right and abs(a[0] - p.x2) < EPS and abs(b[0] - p.x2) < EPS:
        return True
    return p.top and abs(a[1] - p.y2) < EPS and abs(b[1] - p.y2) < EPS


def _inside(q, p: Panel) -> bool:
    return p.x1 - EPS <= q[0] <= p.x2 + EPS and p.y1 - EPS <= q[1] <= p.y2 + EPS


def chains(moves, p: Panel, shared: bool = True, tol: float = 0.01) -> list[tuple[tuple, list]]:
    """Ce qui est usiné dans le panneau : [(point de départ, mouvements qui se suivent)]. `shared` : sans chevauchement,
    une frontière n'appartient qu'à un panneau."""
    out: list = []
    start, cur = None, []

    def close() -> None:
        nonlocal start, cur
        if cur:
            out.append((start, cur))
        start, cur = None, []

    def add(a, b, move: Move) -> None:
        nonlocal start
        last = (cur[-1].x, cur[-1].y, cur[-1].z) if cur else None
        if last is None or math.dist(last, a) > EPS:
            close()
            start = a
        cur.append(move)

    prev = None
    for m in moves:
        end = (m.x, m.y, m.z)
        if prev is None or m.kind == 'rapid':
            close()
            prev = end
            continue
        pieces = [(prev, end)]
        if m.is_arc:
            pts = arc_points(prev, m, tol)
            if all(_inside(q, p) for q in pts) and _inside(prev, p) and not (shared and _neighbour_owns(prev, end, p)):
                add(prev, end, m)
                prev = end
                continue
            pieces = list(zip([prev, *pts], pts))
        kind = 'plunge' if m.kind == 'plunge' else 'feed'
        for a, b in pieces:
            got = _clip(a, b, p)
            if got is None or math.dist(*got) < EPS or (shared and _neighbour_owns(*got, p)):
                close()
                continue
            add(got[0], got[1], Move(kind, *got[1], fin=m.fin))
        prev = end
    close()
    return out


def safe_height(tp) -> float:
    """La hauteur la plus haute du parcours d'origine, avant ses liaisons basses éventuelles."""
    moves = tp.unfaced or tp.moves
    top = max(m.z for m in moves)
    rapids = [m.z for m in moves if m.kind == 'rapid']
    return top if rapids and max(rapids) >= top - EPS else top + SAFE_MARGIN


def relinked(found, safe: float) -> list[Move]:
    """Les morceaux reliés par le haut : rapide au-dessus, descente droite, remontée en rapide."""
    out: list[Move] = []
    for (x, y, z), moves in found:
        out.append(Move('rapid', x, y, safe))
        if z < safe - EPS:
            out.append(Move('plunge', x, y, z))
        out.extend(moves)
        end = moves[-1]
        if end.z < safe - EPS:
            out.append(Move('rapid', end.x, end.y, safe))
    return out


def _is_real_cycle(c) -> bool:
    return isinstance(c, dict) and c.get('kind') != 'instruction' and 'x' in c and 'y' in c


def _keeps_cycle(c, p: Panel, shared: bool) -> bool:
    q = (float(c['x']), float(c['y']))
    return _inside(q, p) and not (shared and _neighbour_owns(q, q, p))


def cut_path(tp, p: Panel, shared: bool = True, tol: float = 0.01):
    """Copie du parcours réduite au panneau, None si rien n'y tombe. Les trous en cycle suivent les mouvements :
    un post-processeur écrit l'un ou l'autre."""
    found = chains(tp.moves, p, shared, tol) if tp.moves else []
    cycles = [c for c in tp.cycles or [] if not _is_real_cycle(c) or _keeps_cycle(c, p, shared)]
    if not found and not any(_is_real_cycle(c) for c in cycles):
        return None
    c = copy.copy(tp)
    c.moves = relinked(found, safe_height(tp)) if found else []
    c.cycles = cycles
    c.uid = uuid.uuid4().hex[:12]
    c.unfaced = None
    c.uncut = None
    if getattr(c, 'feeds', None):                      # programme relu : ses avances allaient mouvement par mouvement
        c.feeds = None
    return c


def _is_real(tp) -> bool:
    return bool(tp.moves) or any(_is_real_cycle(c) for c in tp.cycles or [])


def split(toolpaths, panels: list[Panel], overlap: float = 0.0, tol: float = 0.01) -> dict[int, list]:
    """{rang : parcours du panneau} ; liste vide pour un panneau où rien ne tombe. Ce qui n'usine rien (arrêts, consignes)
    reste à sa place dans chaque programme."""
    shared = overlap <= EPS
    out = {}
    for p in panels:
        got, any_cut = [], False
        for tp in toolpaths:
            if not _is_real(tp):
                got.append(tp)
                continue
            c = cut_path(tp, p, shared, tol)
            if c is not None:
                got.append(c)
                any_cut = True
        out[p.rank] = got if any_cut else []
    return out


def segments(toolpaths, tol: float = 0.05):
    """Cadres de ce qui est usiné, pour voir vite quels panneaux restent vides : tableau N × 4 (x min, y min, x max, y max)."""
    import numpy as np
    rows = []
    for tp in toolpaths:
        prev = None
        for m in tp.moves:
            if m.kind != 'rapid' and prev is not None:
                pts = arc_points(prev, m, tol) if m.is_arc else [(m.x, m.y, m.z)]
                for a, b in zip([prev, *pts], pts):
                    rows.append((min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1])))
            prev = (m.x, m.y, m.z)
        rows.extend((float(c['x']), float(c['y']), float(c['x']), float(c['y'])) for c in tp.cycles or [] if _is_real_cycle(c))
    return np.array(rows, dtype=float).reshape(-1, 4)


def occupied(panels: list[Panel], boxes) -> list[Panel]:
    """Les panneaux où tombe au moins un de ces cadres. Un trait en biais peut frôler un coin sans y entrer :
    `filled`, après la découpe, a le dernier mot."""
    return [p for p in panels if len(boxes) and bool(((boxes[:, 2] >= p.x1) & (boxes[:, 0] <= p.x2) &
                                                      (boxes[:, 3] >= p.y1) & (boxes[:, 1] <= p.y2)).any())]


def filled(panels: list[Panel], paths: dict) -> tuple[list[Panel], dict]:
    """Sans les panneaux restés vides à la découpe, rangs refaits."""
    kept = [p for p in panels if paths.get(p.rank)]
    fresh = renumbered(kept)
    return fresh, {n.rank: paths[p.rank] for n, p in zip(fresh, kept)}


def renumbered(panels: list[Panel]) -> list[Panel]:
    """Mêmes panneaux, rangs refaits dans l'ordre de la liste."""
    return [Panel(k, p.col, p.row, p.x1, p.y1, p.x2, p.y2, p.right, p.top) for k, p in enumerate(panels, 1)]


def plate_move(prev: Panel, p: Panel, where: str = 'bottom_left') -> tuple[float, float]:
    """Déplacement de la plaque depuis le panneau précédent, pour amener ce panneau au même zéro machine."""
    a, b = prev.origin(where), p.origin(where)
    return a[0] - b[0], a[1] - b[1]


def _v(x: float) -> str:
    return f'{x:.2f}'.replace('.', ',')


def _duration(seconds: float) -> str:
    s = int(round(seconds))
    return f'{s // 3600} h {s // 60 % 60:02d} min {s % 60:02d} s' if s >= 3600 else f'{s // 60} min {s % 60:02d} s'


def report(panels: list[Panel], paths: dict, setup, bounds, stem: str, *, names: dict | None = None, overlap: float = 0.0,
           where: str = 'bottom_left', when: str = '', spec=None) -> str:
    """Le rapport des panneaux, en clair (ASCII), écrit à côté des programmes."""
    from . import timing as TM
    n = len(panels)
    labels = {'bottom_left': 'coin bas gauche', 'top_left': 'coin haut gauche', 'center': 'centre'}
    lines = [f'PARCELLISATION - {n} PANNEAU{"X" if n > 1 else ""}',
             f'Travail : {stem}' + (f'    Ecrit le {when} par VectorDrive' if when else ''),
             f'Zone : X {_v(bounds[0])} a {_v(bounds[2])}, Y {_v(bounds[1])} a {_v(bounds[3])} '
             f'({_v(bounds[2] - bounds[0])} x {_v(bounds[3] - bounds[1])} mm)',
             f'Chevauchement : {_v(overlap)} mm    Zero de chaque programme : {labels.get(where, where)} du panneau', '',
             'Repere : X+ vers la droite, Y+ vers le haut, tels qu\'affiches a l\'ecran.',
             'Longue plaque : meme zero machine pour tous les panneaux ; entre deux panneaux, la plaque se deplace de la '
             'valeur indiquee.',
             'Plaques separees : chaque plaque se pose a son zero, sans deplacement.',
             'A chaque coupure l\'outil descend droit, a l\'avance de plongee : a simuler avant usinage.', '']
    total = 0.0
    previous = None
    for p in panels:
        name = (names or {}).get(p.rank, f'{stem}_P{p.rank:02d}')
        ox, oy = p.origin(where)
        lines.append(f'Panneau {p.rank}/{n}  (rangee {p.row}, colonne {p.col}) - programme {name}')
        lines.append(f'  Taille : {_v(p.width)} x {_v(p.height)} mm')
        lines.append(f'  Couvre le dessin de X {_v(p.x1)} a {_v(p.x2)} et de Y {_v(p.y1)} a {_v(p.y2)}')
        lines.append(f'  Zero du programme : point X {_v(ox)} / Y {_v(oy)} du dessin')
        if previous is not None:
            dx, dy = plate_move(previous, p, where)
            lines.append(f'  Deplacement de la plaque depuis le panneau {previous.rank} : X {_v(dx)} / Y {_v(dy)} mm')
        seconds = 0.0
        for tp in paths.get(p.rank, []):
            if not _is_real(tp):
                continue
            t = TM.path_seconds(tp, setup, spec)
            seconds += t
            feed, _rapid = tp.lengths()
            label = tp.name or tp.op_id or 'parcours'
            lines.append(f'  Parcours {label} : {_v(feed)} mm en avance, {_duration(t)}')
        lines.append(f'  Temps estime du panneau : {_duration(seconds)}')
        lines.append('')
        total += seconds
        previous = p
    lines.append(f'Temps estime total, hors mises en place : {_duration(total)}')
    return '\n'.join(lines) + '\n'
