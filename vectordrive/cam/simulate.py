"""Simulation d'enlèvement de matière (2,5D) : la pièce est une carte de
hauteurs (dessus à Z = 0) ; l'outil (plat, boule, cône) y est imprimé le
long des mouvements en avance. Sert à voir ce que les parcours — calculés
ou importés de TypeEdit — vont graver, avant d'aller à la machine. Contrôles :
porte-outil dans la matière, déplacement rapide dans la matière. Brut 3D
donné plus haut que la pièce (`core.stock3d`) : la matière part de son haut
dans son emprise."""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from .advanced import tool_profile
from .model import CamTool, arc_points
from ..core import progress


#: diamètre d'outil au-delà duquel l'en-tête est jugé faux (mm) ; les
#: séquences multi-outils de TypeEdit annoncent 1 m
MAX_TOOL = 100.0


@dataclass
class SimResult:
    H: object                       # numpy (ny, nx), mm ; 0 = surface
    x0: float
    y0: float
    res: float
    removed: float = 0.0            # volume enlevé (mm³)
    deepest: float = 0.0            # cote la plus basse (mm)
    warnings: list = field(default_factory=list)
    #: contacts du porte-outil avec la matière : {'tool', 'x', 'y', 'z', 'depth', 'points'}
    collisions: list = field(default_factory=list)
    #: déplacements rapides dans la matière : {'tool', 'x', 'y', 'z', 'depth'}
    rapid_hits: list = field(default_factory=list)
    #: brut (`core.stock3d.StockBox`) : matière jusqu'à son haut dans son emprise ; None : jusqu'à Z 0
    stock: object = None


def stock_top(stock) -> float:
    """Haut de la matière intacte : celui du brut s'il dépasse au-dessus
    de la pièce, sinon Z 0."""
    return max(0.0, float(getattr(stock, 'top', 0.0) or 0.0)) if stock is not None else 0.0


def initial_heights(stock, x0: float, y0: float, res: float, shape):
    """Matière intacte sur la grille : Z 0, et le haut du brut dans son
    emprise quand il dépasse au-dessus de la pièce."""
    import numpy as np
    H = np.zeros(shape)
    top = stock_top(stock)
    if top > 0:
        ny, nx = shape
        xs = x0 + np.arange(nx) * res
        ys = y0 + np.arange(ny) * res
        H[stock.inside(xs[None, :], ys[:, None])] = top
    return H


def stock_of(doc, setup, toolpaths=()):
    """Brut du réglage FAO placé autour de la pièce 3D du dessin, pour des
    parcours de la prise du dessin ; None sans brut, sans pièce 3D, ou si
    un parcours est d'une autre prise (pièce retournée, corps seul : autre
    repère). Sans pièce 3D (ou sans son brut), le brut du dessin 2D (`core.stock2d`, réponse 20 du 14/11) : plaque ou
    contour dessiné, marges, surépaisseur au-dessus de la plaque."""
    from ..core import stock2d, stock3d
    if doc is None:
        return None
    s3, s2 = stock3d.of_setup(setup).active(), stock2d.of_setup(setup).active()
    if not (s3 or s2):
        return None
    from ..core import workspace as WS
    ops = {op.id: op for op in getattr(setup, 'operations', [])}
    for tp in toolpaths:
        op = ops.get(tp.op_id)
        if op is not None and WS.op_setup(op, doc) != ('', -1):   # '+Z' écrit = la face du dessin
            return None
    if s3:
        from . import mill3d
        from .model import Operation
        box = stock3d.box_for(doc, setup, mill3d.op_model(doc, Operation(kind='surface3d')))
        if box is not None:
            return box
    if s2 and any(getattr(tp, 'stock', None) for tp in toolpaths):   # programme relu avec son brut : le sien
        return None
    return stock2d.box_for(doc, setup) if s2 else None


#: tolérance de contact du porte-outil (mm)
HOLDER_TOL = 0.01
#: pénétration tolérée d'un déplacement rapide dans la matière (mm)
RAPID_TOL = 0.02


def _rapid_hit(H, a, b, tool: CamTool, r: float, x0: float, y0: float, res: float, top: float = 0.0):
    """Plus forte pénétration (mm) de l'outil (profil compris) dans la
    matière H le long du déplacement rapide a → b, et le point ; (0, None)
    si l'outil reste dans le vide (au-dessus de `top`, haut de la matière)."""
    import numpy as np
    ny, nx = H.shape
    n = max(2, int(math.ceil(math.dist(a, b) / res)) + 1)
    worst, at = 0.0, None
    for t in np.linspace(0.0, 1.0, n):
        x, y, z = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t)
        if z >= top:
            continue                                     # au-dessus de la matière
        i0, i1 = max(0, int(math.floor((x - r - x0) / res))), min(nx - 1, int(math.ceil((x + r - x0) / res)))
        j0, j1 = max(0, int(math.floor((y - r - y0) / res))), min(ny - 1, int(math.ceil((y + r - y0) / res)))
        if i1 < i0 or j1 < j0:
            continue
        X, Y = np.meshgrid(x0 + np.arange(i0, i1 + 1) * res - x, y0 + np.arange(j0, j1 + 1) * res - y)
        d = np.hypot(X, Y)
        disk = d <= r + 1e-9
        if not disk.any():
            continue
        prof = tool_profile(tool, d[disk])
        prof = np.where(np.isfinite(prof), prof, 0.0)
        pen = float((H[j0:j1 + 1, i0:i1 + 1][disk] - (z + prof)).max())
        if pen > worst:
            worst, at = pen, (float(x), float(y), float(z))
    return worst, at


def _holder_hit(H, x: float, y: float, z_holder: float, radius: float, x0: float, y0: float, res: float) -> float:
    """Pénétration (mm, 0 si aucune) du disque du porte-outil, de rayon
    `radius` à la cote `z_holder`, dans la matière restante H."""
    import numpy as np
    ny, nx = H.shape
    i0 = max(0, int(math.floor((x - radius - x0) / res)))
    i1 = min(nx - 1, int(math.ceil((x + radius - x0) / res)))
    j0 = max(0, int(math.floor((y - radius - y0) / res)))
    j1 = min(ny - 1, int(math.ceil((y + radius - y0) / res)))
    if i1 < i0 or j1 < j0:
        return 0.0
    X, Y = np.meshgrid(x0 + np.arange(i0, i1 + 1) * res - x, y0 + np.arange(j0, j1 + 1) * res - y)
    disk = X * X + Y * Y <= radius * radius
    if not disk.any():
        return 0.0
    top = float(H[j0:j1 + 1, i0:i1 + 1][disk].max())
    return max(0.0, top - z_holder - HOLDER_TOL)


def _stamp_segment(H, a, b, tool: CamTool, r: float, x0: float, y0: float, res: float, top: float = 0.0) -> None:
    """Creuse dans H la trace de l'outil sur le segment a → b (pointe à la
    cote du point le plus proche de chaque nœud de la grille ; segment
    vertical, plongée : à sa cote la plus basse)."""
    import numpy as np
    if a[2] >= top and b[2] >= top:
        return
    ny, nx = H.shape
    i0 = max(0, int(math.floor((min(a[0], b[0]) - r - x0) / res)))
    i1 = min(nx - 1, int(math.ceil((max(a[0], b[0]) + r - x0) / res)))
    j0 = max(0, int(math.floor((min(a[1], b[1]) - r - y0) / res)))
    j1 = min(ny - 1, int(math.ceil((max(a[1], b[1]) + r - y0) / res)))
    if i1 < i0 or j1 < j0:
        return
    X = x0 + np.arange(i0, i1 + 1) * res
    Y = (y0 + np.arange(j0, j1 + 1) * res)[:, None]
    vx, vy = b[0] - a[0], b[1] - a[1]
    L2 = vx * vx + vy * vy
    if L2 > 1e-18:
        t = np.clip(((X - a[0]) * vx + (Y - a[1]) * vy) / L2, 0.0, 1.0)
    else:                                                # plongée verticale : l'outil descend jusqu'au bas du segment
        t = np.full((len(Y), len(X)), 1.0 if b[2] < a[2] else 0.0)
    d = np.hypot(X - (a[0] + t * vx), Y - (a[1] + t * vy))
    z = a[2] + t * (b[2] - a[2])
    sub = H[j0:j1 + 1, i0:i1 + 1]
    np.minimum(sub, z + tool_profile(tool, d), out=sub)


#: segments traités d'un coup (fenêtres empilées) ; au-delà de cette largeur de
#: fenêtre (cellules), un segment est imprimé seul (long déplacement en avance)
BATCH = 2048
MAX_WINDOW = 24


def _stamp_batch(H, segs, tool: CamTool, r: float, x0: float, y0: float, res: float) -> None:
    """Même calcul que `_stamp_segment`, pour une pile de segments courts :
    les fenêtres (toutes de la taille de la plus grande) sont empilées en
    un tableau (K, w, w) traité d'un coup — mille fois moins d'appels numpy,
    résultat identique au bit près (mêmes opérations, cellule par cellule)."""
    import numpy as np
    S = np.asarray(segs, dtype=float)                           # (K, 6) : ax ay az bx by bz [r]
    if S.shape[1] == 7:                                         # rayon de coupe propre à chaque segment
        r = S[:, 6]
        S = S[:, :6]
    ny, nx = H.shape
    A, B = S[:, :3], S[:, 3:]
    i0 = np.maximum(0, np.floor((np.minimum(A[:, 0], B[:, 0]) - r - x0) / res).astype(int))
    i1 = np.minimum(nx - 1, np.ceil((np.maximum(A[:, 0], B[:, 0]) + r - x0) / res).astype(int))
    j0 = np.maximum(0, np.floor((np.minimum(A[:, 1], B[:, 1]) - r - y0) / res).astype(int))
    j1 = np.minimum(ny - 1, np.ceil((np.maximum(A[:, 1], B[:, 1]) + r - y0) / res).astype(int))
    keep = (i1 >= i0) & (j1 >= j0)
    if not keep.any():
        return
    A, B, i0, i1, j0, j1 = A[keep], B[keep], i0[keep], i1[keep], j0[keep], j1[keep]
    w = int(max((i1 - i0).max(), (j1 - j0).max())) + 1
    k = np.arange(w)
    I = np.minimum(i0[:, None] + k[None, :], nx - 1)                       # (K, w)
    J = np.minimum(j0[:, None] + k[None, :], ny - 1)
    X = (x0 + I * res)[:, None, :]                                          # (K, 1, w)
    Y = (y0 + J * res)[:, :, None]                                          # (K, w, 1)
    ax, ay, az = A[:, 0, None, None], A[:, 1, None, None], A[:, 2, None, None]
    vx, vy, vz = (B - A)[:, 0, None, None], (B - A)[:, 1, None, None], (B - A)[:, 2, None, None]
    L2 = vx * vx + vy * vy
    with np.errstate(divide='ignore', invalid='ignore'):           # plongée verticale : jusqu'au bas du segment
        t = np.where(L2 > 1e-18, np.clip(((X - ax) * vx + (Y - ay) * vy) / L2, 0.0, 1.0), np.where(vz < 0, 1.0, 0.0))
    d = np.hypot(X - (ax + t * vx), Y - (ay + t * vy))
    z = az + t * vz + tool_profile(tool, d)
    valid = (k[None, :, None] <= (j1 - j0)[:, None, None]) & (k[None, None, :] <= (i1 - i0)[:, None, None])
    z = np.where(valid, z, np.inf)
    JJ = np.broadcast_to(J[:, :, None], z.shape)
    II = np.broadcast_to(I[:, None, :], z.shape)
    m = np.isfinite(z)
    np.minimum.at(H, (JJ[m], II[m]), z[m])


#: classes de largeur de fenêtre (cellules) : un lot n'empile que des fenêtres voisines
WINDOWS = (6, 10, 16, MAX_WINDOW)


def cut_radius_of(tool: CamTool, r: float, res: float):
    """Rayon où l'outil touche encore la matière à une profondeur donnée :
    fonction profondeur (≥ 0) → rayon (≤ r). Au-delà, la surface de l'outil
    est au-dessus de la pièce (cote ≥ 0) : une fraise conique de 6 mm qui
    grave à 0,2 mm ne creuse que dans 0,17 mm — la fenêtre de calcul suit
    ce rayon, pas celui de l'outil (même résultat, bien moins de cellules)."""
    import numpy as np
    from .advanced import tool_profile
    ds = np.linspace(0.0, r, 1025)
    prof = np.maximum.accumulate(tool_profile(tool, ds))
    step = ds[1] - ds[0] if len(ds) > 1 else r

    def at(depth: float) -> float:
        k = int(np.searchsorted(prof, depth, side='left'))
        return r if k >= len(ds) else min(r, ds[k] + step + res)
    return at


def _flush(H, batches: dict, tool: CamTool, r: float, x0: float, y0: float, res: float) -> None:
    for batch in batches.values():
        if batch:
            _stamp_batch(H, batch, tool, r, x0, y0, res)
            batch.clear()


#: simulations gardées pour la séance, en octets de cartes au plus (les plus anciennes partent d'abord)
SIM_CACHE_BYTES = 512 * 1024 * 1024
_SIM_CACHE: dict = {}


def _sim_key(toolpaths, setup, res, margin, max_cells, stock=None):
    """Empreinte de ce que lit la simulation : mouvements (contenu, pas
    l'identité : une retouche garde l'identifiant du parcours), outils et
    machine du réglage, grille."""
    import hashlib
    import numpy as np
    from .strategies import _setup_signature
    sig = _setup_signature(setup)
    if sig is None:
        return None
    h = hashlib.blake2b(digest_size=20)
    h.update(sig.encode())
    h.update(repr((res, margin, max_cells, stock)).encode())
    for tp in toolpaths:
        if not tp.moves:
            continue
        h.update(str(tp.tool_id).encode())
        h.update(''.join(m.kind[0] + m.kind[-1] for m in tp.moves).encode())
        h.update(np.array([(m.x, m.y, m.z, m.cx, m.cy) for m in tp.moves], dtype=float).tobytes())
    return h.hexdigest()


def _sim_copy(sim: SimResult) -> SimResult:
    import copy
    out = copy.copy(sim)
    out.H = sim.H.copy()
    out.warnings = list(sim.warnings)
    out.collisions = [dict(e) for e in sim.collisions]
    out.rapid_hits = [dict(e) for e in sim.rapid_hits]
    return out


def simulate(toolpaths, setup, *, res: float | None = None, margin: float = 2.0,
             max_cells: int = 2_000_000, stock=None) -> SimResult:
    """Matière laissée par les parcours (carte des hauteurs) ; `stock` :
    brut placé (`stock_of`), la matière part de son haut. La même
    simulation demandée à nouveau (vue 3D rouverte, source rechoisie) est
    reprise de la mémoire."""
    key = _sim_key(toolpaths, setup, res, margin, max_cells, stock)
    if key is not None and key in _SIM_CACHE:
        hit = _SIM_CACHE.pop(key)
        _SIM_CACHE[key] = hit                             # le plus récent en dernier
        return _sim_copy(hit)
    sim = _simulate(toolpaths, setup, res=res, margin=margin, max_cells=max_cells, stock=stock)
    if key is not None and sim.H.nbytes <= SIM_CACHE_BYTES:
        _SIM_CACHE[key] = _sim_copy(sim)
        while sum(x.H.nbytes for x in _SIM_CACHE.values()) > SIM_CACHE_BYTES:
            _SIM_CACHE.pop(next(iter(_SIM_CACHE)))
    return sim


def _simulate(toolpaths, setup, *, res: float | None = None, margin: float = 2.0,
              max_cells: int = 2_000_000, stock=None) -> SimResult:
    import numpy as np
    feeds = [tp for tp in toolpaths if tp.moves]
    boxes = [tp.bbox() for tp in feeds]
    if not boxes:
        return SimResult(np.zeros((1, 1)), 0.0, 0.0, 1.0, warnings=['aucun parcours'])
    x0 = min(b[0] for b in boxes) - margin
    y0 = min(b[1] for b in boxes) - margin
    x1 = max(b[3] for b in boxes) + margin
    y1 = max(b[4] for b in boxes) + margin
    if res is None:
        res = max(math.sqrt((x1 - x0) * (y1 - y0) / max_cells), 0.01)
    nx, ny = int(math.ceil((x1 - x0) / res)) + 1, int(math.ceil((y1 - y0) / res)) + 1
    top = stock_top(stock)                                 # haut de la matière (brut au-dessus de la pièce)
    H = initial_heights(stock, x0, y0, res, (ny, nx))
    H0 = H.copy() if top > 0 else None
    out = SimResult(H, x0, y0, res, stock=stock)
    total = sum(len(tp.moves) for tp in feeds) or 1
    done = 0
    for tp in feeds:
        tool = setup.tool(tp.tool_id) or CamTool(diameter=0.2)
        if tool.kind == 'laser':
            tool = CamTool(diameter=max(tool.diameter, res))
        if tool.kind not in ('boule', 'conique'):
            tool = CamTool(kind='fraise', diameter=max(tool.diameter, res))
        if tool.diameter > MAX_TOOL:
            w = f'outil de {tool.diameter:g} mm invraisemblable (en-tête faux) : simulé avec 1 mm'
            if w not in out.warnings:
                out.warnings.append(w)
            tool = CamTool(kind='fraise', diameter=1.0)
        r = max(tool.body_diameter() / 2, res / 2)           # cône : jusqu'à sa queue
        real = setup.tool(tp.tool_id)
        from .model import holder_of
        so, hd = holder_of(real, setup)
        rh = hd / 2
        check = so > 0 and rh > 0
        event = None
        prev = None
        batches: dict = {w: [] for w in WINDOWS}       # segments courts en attente, par largeur de fenêtre
        reach = cut_radius_of(tool, r, res)             # rayon de coupe selon la profondeur
        for m in tp.moves:
            done += 1
            if done % 200 == 0:
                progress.step(done, total, 'Simulation : mouvement {0} sur {1}')
            here = (m.x, m.y, m.z)
            if prev is not None and m.kind != 'rapid' and min(prev[2], m.z) < top:
                pts = [prev] + (arc_points(prev, m, res / 2) if m.is_arc else [here])
                for a, b in zip(pts, pts[1:]):
                    if a[2] >= top and b[2] >= top:
                        continue                        # au-dessus de la matière : rien à creuser
                    rc = reach(top - min(a[2], b[2]))
                    span = max(abs(b[0] - a[0]), abs(b[1] - a[1])) + 2 * rc
                    if span > MAX_WINDOW * res:
                        _stamp_segment(H, a, b, tool, rc, x0, y0, res, top)
                    else:
                        batch = batches[next(w for w in WINDOWS if span <= w * res)]
                        batch.append((a[0], a[1], a[2], b[0], b[1], b[2], rc))
                        if len(batch) >= BATCH:
                            _stamp_batch(H, batch, tool, r, x0, y0, res)
                            batch.clear()
            elif prev is not None and m.kind == 'rapid' and min(prev[2], m.z) < top \
                    and not (m.z >= prev[2] and math.hypot(m.x - prev[0], m.y - prev[1]) < 1e-9):
                _flush(H, batches, tool, r, x0, y0, res)  # remontée verticale : sûre ; le reste est contrôlé
                hit, at = _rapid_hit(H, prev, here, tool, r, x0, y0, res, top)
                if hit > RAPID_TOL:
                    out.rapid_hits.append({'tool': real.name if real is not None else '', 'x': at[0], 'y': at[1],
                                           'z': at[2], 'depth': hit})
            if check:
                _flush(H, batches, tool, r, x0, y0, res)  # la matière doit être à jour sous le porte-outil
                z_h = m.z + so                          # bas du porte-outil
                hit = _holder_hit(H, m.x, m.y, z_h, rh, x0, y0, res) if z_h < top else 0.0
                if hit > 0:
                    if event is None:
                        event = {'tool': real.name, 'x': m.x, 'y': m.y, 'z': m.z, 'depth': hit, 'points': 0}
                        out.collisions.append(event)
                    event['points'] += 1
                    if hit > event['depth']:
                        event.update(x=m.x, y=m.y, z=m.z, depth=hit)
                else:
                    event = None
            prev = here
        _flush(H, batches, tool, r, x0, y0, res)
    for e in out.collisions[:5]:
        out.warnings.append(f'collision : porte-outil de « {e["tool"]} » dans la matière à X {e["x"]:.2f} '
                            f'Y {e["y"]:.2f} Z {e["z"]:.2f} ({e["depth"]:.2f} mm)')
    if len(out.collisions) > 5:
        out.warnings.append(f'… et {len(out.collisions) - 5} autre(s) collision(s) du porte-outil')
    for e in out.rapid_hits[:5]:
        out.warnings.append(f'collision : déplacement rapide de « {e["tool"]} » dans la matière à X {e["x"]:.2f} '
                            f'Y {e["y"]:.2f} Z {e["z"]:.2f} ({e["depth"]:.2f} mm)')
    if len(out.rapid_hits) > 5:
        out.warnings.append(f'… et {len(out.rapid_hits) - 5} autre(s) déplacement(s) rapide(s) dans la matière')
    out.removed = float(((H0 if H0 is not None else 0.0) - H).sum() * res * res)
    out.deepest = float(H.min())
    return out


def sim_tool(setup, tp, res: float) -> CamTool:
    """Outil tel que la simulation l'imprime (laser : fin trait ; plat par défaut)."""
    tool = setup.tool(tp.tool_id) or CamTool(diameter=0.2)
    if tool.kind == 'laser':
        tool = CamTool(diameter=max(tool.diameter, res))
    if tool.kind not in ('boule', 'conique'):
        tool = CamTool(kind='fraise', diameter=max(tool.diameter, res))
    if tool.diameter > MAX_TOOL:
        tool = CamTool(kind='fraise', diameter=1.0)
    return tool


def simulate_range(toolpaths, setup, sim: SimResult, start: int, end: int) -> SimResult:
    """La matière de `sim` (copiée) après les mouvements d'indice global
    [start, end) des parcours (comptés à la suite, rapides compris) — pour
    voir l'usinage avancer pas à pas : chaque étape repart de la précédente.
    Sans contrôle du porte-outil (la simulation complète s'en charge)."""
    import numpy as np
    H = np.array(sim.H, copy=True)
    x0, y0, res = sim.x0, sim.y0, sim.res
    top = stock_top(sim.stock)
    k = 0
    for tp in toolpaths:
        n = len(tp.moves)
        if k + n <= start:
            k += n
            continue
        if k >= end:
            break
        tool = sim_tool(setup, tp, res)
        r = max(tool.body_diameter() / 2, res / 2)
        prev = None
        if k < start:                                   # mouvement d'avant : point de départ
            m0 = tp.moves[start - k - 1]
            prev = (m0.x, m0.y, m0.z)
        reach = cut_radius_of(tool, r, res)             # fenêtres au rayon de coupe (même résultat)
        batches: dict = {w: [] for w in WINDOWS}
        for i in range(max(0, start - k), min(n, end - k)):
            if not i % 256:
                progress.check()                        # Annuler (dans un calcul suivi) : sans attendre la fin du bloc
            m = tp.moves[i]
            here = (m.x, m.y, m.z)
            if prev is not None and m.kind != 'rapid' and min(prev[2], m.z) < top:
                pts = [prev] + (arc_points(prev, m, res / 2) if m.is_arc else [here])
                for a, b in zip(pts, pts[1:]):
                    if a[2] >= top and b[2] >= top:
                        continue
                    rc = reach(top - min(a[2], b[2]))
                    span = max(abs(b[0] - a[0]), abs(b[1] - a[1])) + 2 * rc
                    if span > MAX_WINDOW * res:
                        _stamp_segment(H, a, b, tool, rc, x0, y0, res, top)
                    else:
                        batch = batches[next(w for w in WINDOWS if span <= w * res)]
                        batch.append((a[0], a[1], a[2], b[0], b[1], b[2], rc))
                        if len(batch) >= BATCH:
                            _stamp_batch(H, batch, tool, r, x0, y0, res)
                            batch.clear()
            prev = here
        _flush(H, batches, tool, r, x0, y0, res)
        k += n
    out = SimResult(H, x0, y0, res, stock=sim.stock)
    H0 = initial_heights(sim.stock, x0, y0, res, H.shape) if top > 0 else 0.0
    out.removed = float((H0 - H).sum() * res * res)
    out.deepest = float(H.min())
    return out


#: mouvements simulés d'un bloc entre deux points d'avancement (`advance`)
CHUNK = 5000


def op_spans(toolpaths) -> list:
    """Les opérations dans l'ordre d'usinage : [(op_id, i, j, début, fin)] — les parcours toolpaths[i:j], les mouvements
    [début, fin) comptés à la suite comme dans `simulate_range`. Des parcours qui se suivent d'une même opération n'en font
    qu'une ; un parcours sans opération (TypeEdit, programme relu) est seul (op_id None) ; un parcours vide n'en est pas."""
    out, k = [], 0
    for i, tp in enumerate(toolpaths):
        n = len(tp.moves)
        if not n:
            continue
        op = getattr(tp, 'op_id', None) or None
        if out and op is not None and out[-1][0] == op:
            out[-1] = (op, out[-1][1], i + 1, out[-1][3], k + n)
        else:
            out.append((op, i, i + 1, k, k + n))
        k += n
    return out


def blank(sim: SimResult) -> SimResult:
    """La matière intacte (le brut, sinon Z 0) sur la grille de `sim`."""
    import numpy as np
    H = initial_heights(sim.stock, sim.x0, sim.y0, sim.res, np.shape(sim.H))
    return SimResult(H, sim.x0, sim.y0, sim.res, deepest=float(H.min()), stock=sim.stock)


def advance(toolpaths, setup, state: SimResult, start: int, end: int) -> SimResult:
    """La matière `state` (celle d'avant le mouvement `start`) après les mouvements [start, end), par blocs de `CHUNK`
    mouvements avec avancement et Annuler (`simulate_range`) ; `state` n'est pas modifiée (rendue telle quelle s'il n'y a
    rien à faire). Sans contrôle du porte-outil (la simulation complète s'en charge)."""
    cur, i = state, start
    while i < end:
        j = min(end, i + CHUNK)
        cur = simulate_range(toolpaths, setup, cur, i, j)
        i = j
        progress.step(i - 1, end, 'Simulation : mouvement {0} sur {1}')
    return cur


def remaining(toolpaths, setup, sim: SimResult, start: int, end: int):
    """La matière avant et après les mouvements [start, end) — une opération (`op_spans`) —, en partant du brut, sur la
    grille de `sim` (la simulation complète) : (avant, après). Après la dernière opération : la matière de la simulation
    complète ; `après.removed - avant.removed` : ce que l'opération enlève, sans ce que celles d'avant ont déjà enlevé."""
    before = advance(toolpaths, setup, blank(sim), 0, start)
    return before, advance(toolpaths, setup, before, start, end)


def to_relief(sim: SimResult, tool: int = 0, name: str = 'Simulation'):
    """La matière simulée en objet relief (`core.galbe`) : à sa place sur le dessin, la surface en blanc, le fond en noir. Les
    valeurs de `sim.H` sont aux nœuds de la grille, une image a les siennes au centre de ses pixels. None s'il n'y a rien de creusé."""
    import numpy as np
    from ..core import galbe as GB
    H = np.asarray(sim.H, dtype=float)
    if H.size == 0 or float(H.min()) >= -1e-9:
        return None
    ny = H.shape[0]
    spec = GB.GalbeSpec(z_max=float(H.max()), z_min=float(H.min()), resolution=sim.res, margin=0.0)
    return GB.encode(H[::-1], sim.x0 - sim.res / 2, sim.y0 + (ny - 0.5) * sim.res, sim.res, spec, tool, name)


def render(sim: SimResult, width: int = 900, *, level: float | None = None, bottom: bool = False, mark=None):
    """Image ombrée (QImage) : relief éclairé, couleur selon la profondeur
    (surface claire, fond bleu foncé), Y vers le haut.
    `level` (cote négative) : la vue à cette altitude, ce qui est enlevé à cette cote en bleu, le reste clair (TE : Profondeur
    de la vue). `bottom` : le fond de gravure ressort en orange (TE : En fond). `mark` (booléens de la forme de `sim.H`) : ces
    points en vert — ce qu'une opération enlève."""
    import numpy as np
    from PySide6.QtGui import QImage
    H = sim.H
    gy, gx = np.gradient(H, sim.res)
    nz = 1.0 / np.sqrt(gx * gx + gy * gy + 1.0)
    light = np.clip((-gx * 0.5 + gy * 0.5 + 1.0) * nz, 0, 1.4) / 1.4
    depth = -H / max(1e-9, -sim.deepest) if sim.deepest < 0 else np.zeros_like(H)
    base = np.stack([0.93 - 0.75 * depth, 0.90 - 0.55 * depth, 0.82 - 0.15 * depth], axis=-1)
    if level is not None and level < 0:
        base = np.where((H <= level + 1e-9)[..., None], np.array([0.18, 0.35, 0.67]), np.array([0.93, 0.90, 0.82]))
    if bottom and sim.deepest < 0:
        base = np.where((H <= sim.deepest + max(1e-3, 0.02 * -sim.deepest))[..., None], np.array([0.95, 0.55, 0.10]), base)
    if mark is not None and np.shape(mark) == np.shape(H):
        base = np.where(np.asarray(mark, dtype=bool)[..., None], np.array([0.30, 0.72, 0.36]), base)
    rgb = np.clip(base * (0.55 + 0.45 * light)[..., None], 0, 1)
    img = (rgb[::-1] * 255).astype(np.uint8)
    h, w = img.shape[:2]
    data = np.ascontiguousarray(img)
    q = QImage(data.data, w, h, 3 * w, QImage.Format.Format_RGB888).copy()
    if w > width:
        from PySide6.QtCore import Qt
        q = q.scaledToWidth(width, Qt.TransformationMode.SmoothTransformation)
    return q
