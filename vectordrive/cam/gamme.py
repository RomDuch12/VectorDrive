"""Gamme à plusieurs outils (manuel de TE, pages 619 à 621) : une ligne par outil, classées du plus gros au plus fin, qui donnent
autant d'opérations liées. Ébauche à la poche, reprises des restes, puis gravure à l'outil conique : avec ses tirés d'angle
(« Finition 3D » du manuel), ou contour 2D sans remontées d'angle.

Relevé dans TE13 sur 65 fichiers de parcours de mes dessins :
- une fraise reste à son rayon + la pente du cône à la profondeur + la surépaisseur, sans compter la pointe, s'il y a un cône dans la liste et que le
  contour est respecté en surface ; sinon à son rayon + la surépaisseur ;
- un cône ne fait pas de passes sur les flancs. Forme par forme et à chaque passe : le fond à sa cote, là où l'outil d'avant n'a pas pu aller, puis le
  contour à cette cote, à la pointe + la pente + la surépaisseur + la pointe du cône suivant. En Finition 3D, ce contour a ses tirés d'angle ; sinon les
  trous viennent avant l'extérieur. En fond de gravure : pas de pente, pas de tirés d'angle. La Finition 2D n'a rien changé sur mes dessins.
Différence voulue : TE reprend en carrés tout l'angle laissé par l'outil d'avant, même quand le contour l'a déjà enlevé (16 mm par angle droit, à vide).
VD ne reprend que ce qui reste : une reprise à la fraise est liée au parcours précédent (`link_previous`, `linkprev.remaining_only`), les morceaux
de son parcours qui n'enlèvent plus rien après ceux des lignes d'avant sont retirés ; le cône ne reprend déjà que ce que l'outil d'avant a laissé
(`cone_step`) : lié, il ne gagnerait presque rien et remonterait plus souvent."""
from __future__ import annotations

import math
from dataclasses import dataclass

from .model import Operation

#: écart toléré entre les angles des outils coniques (°)
ANGLE_TOL = 1e-3


@dataclass
class Step:
    """Une ligne de la gamme."""
    tool_id: str
    mode: str = 'balayage'          # poche : 'balayage' ou 'contournage'
    stepover: float = 0.0           # distance entre passes (mm, 0 : selon l'outil)
    depth: float = 0.0              # profondeur de cette ligne, si elle est moindre que celle de la gamme (mm, 0 : celle de la gamme)
    finish3d: bool = True           # outil conique : tirés d'angle ; sinon contour 2D, sans remontées
    sweep_angle: float = 0.0        # balayage : angle de départ (°)
    step_down: float = 0.0          # profondeur de passe (mm, 0 : fraise, selon l'outil ; cône, en une fois)


def is_cone(tool) -> bool:
    return tool.kind == 'conique' and 0 < tool.angle < 180


def ranked(setup, steps: list, depth: float) -> list:
    """[(ligne, outil)], du plus gros au plus fin, à leur taille et à leur forme : les fraises, puis les outils coniques (rayon
    à la profondeur de la gamme). Les lignes sans outil connu sont laissées de côté. À égalité, l'ordre donné."""
    pairs = [(s, setup.tool(s.tool_id)) for s in steps]
    pairs = [(s, t) for s, t in pairs if t is not None]
    return sorted(pairs, key=lambda p: (is_cone(p[1]), -(p[1].radius_at(depth) if is_cone(p[1]) else p[1].diameter / 2)))


def problem(setup, steps: list, depth: float) -> str:
    """Ce qui empêche la gamme ('' : rien). Le texte est en français : à traduire là où il est montré."""
    pairs = ranked(setup, steps, depth)
    if not pairs:
        return 'Choisissez au moins un outil.'
    if depth <= 0:
        return 'La profondeur de la gamme doit être positive.'
    angles = [t.angle for _s, t in pairs if is_cone(t)]
    if angles and max(angles) - min(angles) > ANGLE_TOL:
        return 'Les outils coniques d\'une gamme doivent avoir le même angle.'
    return ''


def build(setup, steps: list, depth: float, *, stock: float = 0.0, contour_ref: str = 'surface', skip_frame: bool = False,
          z_start: float = 0.0, label: str = 'Gamme', **common) -> list:
    """Les opérations de la gamme, dans l'ordre d'usinage. Elles portent le nom de leur outil (TE, page 619). `common` : ce qui
    va à toutes (objets usinés, hauteurs de dégagement). Sans `problem` : à contrôler avant."""
    pairs = ranked(setup, steps, depth)
    cones = [t for _s, t in pairs if is_cone(t)]
    slope = math.tan(math.radians(cones[0].angle) / 2) if cones and contour_ref != 'fond' else 0.0
    ops: list = []

    def depth_of(step) -> float:
        return step.depth if 0 < step.depth < depth else depth

    cone_depth = next((depth_of(s) for s, t in pairs if is_cone(t)), depth)
    for i, (step, tool) in enumerate(pairs):
        d = depth_of(step)
        kw = dict(common, name=f'{label} : {tool.name}', tool_id=tool.id, depth=d, z_start=z_start, contour_ref=contour_ref,
                  finish_skip_frame=skip_frame)
        if is_cone(tool):
            later = next((t for _s, t in pairs[i + 1:] if is_cone(t)), None)
            op = Operation(kind='vcarve', stock=stock, ref_tool_id=pairs[i - 1][1].id if i else '', gamme_rule=885,
                           vcarve_mode='passes' if step.finish3d else 'contour', vcarve_offset=later.tip / 2 if later is not None else 0.0,
                           vcarve_step=step.step_down, stepover_mm=step.stepover if step.stepover > 0 else tool.tip / 2, **kw)
        else:
            # le cône prend le bord à partir de cette distance : voir `cone_step`. Relevé dans TE13 : à la profondeur du cône, pas à celle de la fraise
            wall = cone_depth * slope
            if i == 0:
                op = Operation(kind='poche', stock=stock + wall, stepover_mm=step.stepover, step_down=step.step_down,
                               pocket_mode='balayage' if step.mode == 'balayage' else 'concentrique', **kw)
                if step.mode == 'balayage':
                    op.sweep_angle = math.fmod(step.sweep_angle, 360.0)
            else:
                op = Operation(kind='reste', stock=stock + wall, stepover_mm=step.stepover, step_down=step.step_down,
                               ref_tool_id=pairs[i - 1][1].id, gamme_rule=885, **kw)
                op.link_previous = True                   # seulement ce que les lignes d'avant ont laissé, sans passe à vide
        ops.append(op)
    return ops


def _polygons(geom) -> list:
    return [p for p in getattr(geom, 'geoms', [geom]) if p.geom_type == 'Polygon' and not p.is_empty]


def cone_step(doc, setup, op, tool, tp, em, here) -> None:
    """Un cône de la gamme, relevé dans TE13 : voir l'en-tête du module. `vcarve_offset` : ce qu'il laisse au cône suivant. `ref_tool_id` : l'outil d'avant,
    dont on déduit ce qu'il a vidé."""
    import copy

    import shapely
    from . import strategies as S
    from .advanced import _body, _check_depth, _floor_step
    from .finish import _overlay, finish_order, finish_te
    tol = setup.tolerance
    lines = S.polylines([g for it in S.source_items(doc, op) if (g := S.item_geometry(it))], tol)
    reg = S.region_from_lines(lines)                     # aplatis une fois : la Finition s'en sert aussi
    if reg.is_empty:
        tp.warnings.append('gravure 2,5D : aucun contour fermé')
        return
    tan_h = math.tan(math.radians(tool.angle) / 2)
    rt = tool.tip / 2
    depth = abs(op.depth) if op.depth > 0 else (_body(tool) / 2 - rt) / tan_h
    fond = getattr(op, 'contour_ref', 'surface') == 'fond'
    slope = 0.0 if fond else tan_h
    stock = max(0.0, float(op.stock or 0.0))
    leave = max(0.0, float(op.vcarve_offset or 0.0))
    step = _floor_step(op, rt, tan_h)
    vstep = max(0.0, float(op.vcarve_step or 0.0))
    cotes = S.levels(depth, vstep) if vstep > 0 else [-depth]
    qs = S._quad_segs(max(rt + depth * tan_h, tol), tol)
    region_right = not op.climb
    prev = setup.tool(op.ref_tool_id) if op.ref_tool_id else None
    prev_is_cone = prev is not None and is_cone(prev)
    prev_r = 0.0 if prev is None else prev.tip / 2 if prev_is_cone else prev.diameter / 2
    # l'opération de l'outil d'avant : sa profondeur et ce qu'elle a laissé. À défaut, celles d'une gamme uniforme
    known = next((o for o in setup.operations[::-1] if prev is not None and o.tool_id == prev.id and o.id != op.id), None)
    prev_depth = abs(known.depth) if known is not None and known.depth else depth
    prev_stock = float(known.stock or 0.0) if known is not None else depth * slope + stock
    prev_leave = float(known.vcarve_offset or 0.0) if known is not None else rt
    parts = _polygons(reg)
    tree = shapely.STRtree(parts)
    frames = S.frames_of(reg) if getattr(op, 'finish_skip_frame', False) else None
    is_frame = [frames is not None and frames.covers(p.representative_point()) for p in parts]
    ramp = bool(op.ramp)
    angle = S.ramp_angle_of(op) if ramp else None
    marks = S.start_marks(doc, op, tol)

    def done_at(z: float):
        """Ce que l'outil d'avant a vidé à la cote z. None : rien de connu."""
        if prev is None:
            return None
        if prev_is_cone:                                  # son contour au fond, et son flanc à cette cote
            ring = S.erode(reg, prev_r + prev_depth * slope + stock + prev_leave, qs)
            return ring.buffer(prev_r + max(0.0, prev_depth + z) * slope, quad_segs=qs)
        # relevé dans TE13 : un cône plus profond que la fraise ne reprend pas le fond entre les deux
        return S.erode(reg, prev_r + prev_stock, qs).buffer(prev_r, quad_segs=qs)

    def plan(z: float) -> tuple:
        """Pour la cote z : ({forme : [(morceau du fond, anneaux)]}, {forme : anneaux du contour})."""
        off = rt - z * slope + stock + leave
        base = S.erode(reg, off - 1e-4, qs)               # une branche de la largeur exacte de la pointe garde son axe
        floors: dict = {}
        rings: dict = {}
        if base.is_empty:
            return floors, rings, off, base
        keep = True if frames is None else frames      # S.keep_exteriors(op, reg), sans rechercher les cadres à chaque passe
        for poly in _polygons(base):
            who = int(tree.nearest(poly.representative_point()))
            rings.setdefault(who, []).extend(S.rings_of(poly, region_right, exteriors=keep)[::-1])
        inner = S.erode(base, rt, qs)                     # le reste : ce que le passage du contour n'enlève pas
        done = done_at(z)
        if done is not None and not prev_is_cone:
            # relevé dans TE13, cône profond à plusieurs passes : à une passe haute, la bande entre le contour et la paroi de la fraise n'est pas vidée,
            # les passes suivantes l'enlèvent. Restent les angles
            arm = prev_stock - (off + rt)
            if arm > 0:
                done = done.buffer(arm, quad_segs=qs)
        todo = inner if done is None or inner.is_empty else _overlay('difference', inner, done)
        todo = todo.buffer(-0.005).buffer(0.005)
        if todo.is_empty:
            return floors, rings, off, base
        centers = _overlay('intersection', base, todo.buffer(rt / 2, quad_segs=qs))
        for piece, group in S.rings_by_piece(centers, S.concentric(centers, step, tol), region_right):
            group = group[::-1]                           # du centre vers le bord, comme TE
            who = int(tree.nearest(piece.representative_point()))
            # cadre ignoré : ses angles ne sont pas repris
            if group and not (is_frame[who] and prev is not None and parts[who].exterior.buffer(max(off, prev_stock) + prev_r).covers(piece)):
                floors.setdefault(who, []).append((piece, group))
        return floors, rings, off, base

    plans = [plan(z) for z in cotes]

    def floor(who: int, k: int) -> None:
        pieces = list(plans[k][0].get(who, ()))
        z_from = cotes[k - 1] if k else 0.0
        while pieces:
            at = em.pos[:2] if em.pos is not None else here
            one = min(range(len(pieces)), key=lambda i: pieces[i][0].distance(shapely.Point(at[0], at[1])))
            piece, group = pieces.pop(one)
            if angle:
                S.ramp_floor(em, group, piece.buffer(1e-6), z_from, cotes[k], angle)
            S.mill_rings(em, group, [z_from, cotes[k]], piece.buffer(1e-6), only={1})

    outers = [list(p.exterior.coords) for p in parts]
    order, _tops = finish_order(outers, [shapely.Polygon(c) for c in outers], getattr(op, 'order_mode', 'auto') == 'dessin')
    if op.vcarve_mode == 'passes' and not fond:
        one = copy.copy(op)
        one.stock = stock + leave
        one.ramp = False                                  # relevé dans TE13 : plongée active ou non, les sommets restent en Z 0 ; seuls les fonds sont en rampe

        def by_shape(closed: list, polys: list) -> list:
            who = tree.nearest(shapely.points([tuple(c[0][:2]) for c in closed])).tolist()
            contours: dict = {}
            for c, w in enumerate(who):
                outer = polys[c].covers(parts[w].representative_point())
                if not (outer and is_frame[w]):           # relevé dans TE13 : le cadre seul, pas les formes sans trou
                    contours.setdefault(w, []).append((not outer, c))
            return [([c for _o, c in sorted(contours.get(w, []))], lambda k, w=w: floor(w, k)) for w in order]
        finish_te(doc, setup, one, tool, tp, em, here, by_shape=by_shape, lines=lines, reg=reg)
    else:
        visits = [(w, k) for k in range(len(cotes)) for w in order] if getattr(op, 'pass_order', 'poche') == 'global' else             [(w, k) for w in order for k in range(len(cotes))]
        for w, k in visits:
            floor(w, k)
            off = plans[k][2]
            chains = [(pts, True) for pts in plans[k][1].get(w, ())]
            chains, fixed = S.apply_starts(chains, marks, off + 1.0, off)
            for pts, _c in chains:
                if pts[0] not in fixed:
                    pts = S._start_nearest(pts, True, em.pos)
                S.cut_chain(em, pts, True, [cotes[k]], ramp=ramp, ramp_angle=S.ramp_angle_of(op), z_start=cotes[k - 1] if k else 0.0)
        off, base = plans[-1][2], plans[-1][3]
        if base.is_empty:
            tp.warnings.append(f'contour 2D : formes plus étroites que le cône à {depth:g} mm de profondeur (il faut {2 * off:.3f} mm) ; '
                               'réduire la profondeur ou le décalage')
    _check_depth(tp, tool, cotes)
