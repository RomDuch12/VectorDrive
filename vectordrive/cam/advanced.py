"""Stratégies 2,5D et 3D, branchées sur `strategies.compute` par leur nom.

- **vcarve** (gravure 2,5D à l'outil conique) : retraits successifs du
  contour, chacun à la profondeur où le cône a le rayon du retrait ;
  au-delà de la profondeur maximale, fond plat vidé à cette profondeur.
  Passe en Z (`vcarve_step`) : une gravure profonde en paliers, la
  dernière cote donnant la forme exacte. En « contour 2D » : pas de retraits
  ni de remontées d'angle, un seul contour au fond (le haut du cône sur le bord
  de la forme, à un décalage XY près), puis le fond vidé, lié au parcours
  précédent s'il le faut (seulement ce que les outils d'avant n'ont pas atteint).
- **relief** (3D) : carte de hauteurs tirée d'une image (blanc = surface,
  noir = profondeur maximale, ou l'inverse), compensée par la forme de
  l'outil (boule, plat, cône : dilatation), balayée en aller-retour, en
  passes de Z si la profondeur dépasse la passe de l'outil.
- **surface3d** (3D) : une pièce STEP maillée, vue de dessus (haut de la
  pièce à Z = 0), même compensation et même balayage.
"""
from __future__ import annotations

import math

from ..core.document import Image
from .model import Move
from . import strategies as S
from ..core import progress


# --- gravure 2,5D à l'outil conique ------------------------------------------------

#: fond plat : hauteur des crêtes laissées entre deux passes de la pointe (mm)
FLAT_RIDGE = 0.02
#: gravure en paliers : crêtes laissées à un palier, en part de la passe en Z
#: (le palier suivant engage au plus la passe × (1 + LAYER_RIDGE))
LAYER_RIDGE = 0.25


def _vcarve(doc, setup, op, tool, tp, em, here, z_from: float = 0.0, zone=None) -> None:
    from shapely.geometry import LineString
    if tool.kind != 'conique' or not 0 < tool.angle < 180:
        tp.warnings.append('gravure 2,5D : choisir un outil conique (angle au sommet)')
        return
    if getattr(op, 'gamme_rule', 0) >= 885:
        from .gamme import cone_step
        cone_step(doc, setup, op, tool, tp, em, here)
        return
    if getattr(op, 'finish_rule', 0) >= 877 and getattr(op, 'vcarve_edges_only', False) \
            and getattr(op, 'vcarve_mode', 'passes') == 'passes' and not getattr(op, 'link_previous', False):
        from .finish import finish_te
        finish_te(doc, setup, op, tool, tp, em, here)
        return
    geoms = [g for it in S.source_items(doc, op) if (g := S.item_geometry(it))]
    tol = setup.tolerance
    reg = S.region(geoms, tol)
    if reg.is_empty:
        tp.warnings.append('gravure 2,5D : aucun contour fermé')
        return
    stock = max(0.0, float(op.stock or 0.0))
    if stock > 0.0:                                       # la matière laissée le long des bords : ils se rapprochent
        reg = reg.buffer(-stock, join_style='mitre').buffer(0)
        if reg.is_empty:
            tp.warnings.append(f'gravure 2,5D : surépaisseur de {stock:g} mm trop grande pour ces formes')
            return
    if zone is not None:                                  # une forme à la fois (poche par poche)
        reg = zone
    tan_h = math.tan(math.radians(tool.angle) / 2)
    rt = tool.tip / 2
    r_max = _body(tool) / 2
    depth_max = abs(op.depth) if op.depth > 0 else (r_max - rt) / tan_h
    d_flat = rt + depth_max * tan_h                       # rayon du cône à la profondeur maximale
    te_rule = getattr(op, 'gravure_rule', 0) >= 878 and getattr(op, 'vcarve_mode', 'passes') == 'passes'
    if d_flat > r_max + 1e-9 and te_rule:                 # relevé dans TE13 : la profondeur demandée, le corps de l'outil reste dans la forme
        tp.warnings.append(f'gravure 2,5D : à {depth_max:g} mm, le cône de l\'outil ne va pas jusqu\'en surface ({2 * r_max:g} mm de corps) ; '
                           f'le bord reste en retrait de {d_flat - r_max:.3f} mm')
    elif d_flat > r_max + 1e-9:
        d_flat = r_max
        depth_max = (r_max - rt) / tan_h
        tp.warnings.append(f'gravure 2,5D : profondeur limitée à {depth_max:.3f} mm (diamètre de l\'outil)')
    walls = bool(getattr(op, 'vcarve_walls', True))
    vstep = max(0.0, float(getattr(op, 'vcarve_step', 0.0) or 0.0))
    if not walls and vstep > 0 and getattr(op, 'vcarve_mode', 'passes') == 'passes':
        # relevé dans TE13 : chaque passe avec le retrait de sa cote, comme une gravure à cette profondeur ;
        # ordre global : passe par passe sur tout le dessin ; poche par poche : chaque forme jusqu'au fond
        import copy
        global_order = getattr(op, 'pass_order', 'poche') == 'global' or getattr(op, 'finish_skip_frame', False)
        zones = [None] if global_order else S._nearest_first(S._solid_parts(reg), here)
        for part in zones:
            prev = 0.0
            for z in S.levels(depth_max, vstep):
                one = copy.copy(op)
                one.depth, one.vcarve_step = -z, 0.0
                _vcarve(doc, setup, one, tool, tp, em, here, z_from=prev, zone=part)
                prev = z                                  # relevé dans TE13 : le même ordre des formes à chaque passe
        tp.warnings[:] = list(dict.fromkeys(tp.warnings))
        return
    if getattr(op, 'vcarve_mode', 'passes') in ('axe', 'axe_ar'):
        keep = S.keep_exteriors(op, reg)
        if keep is True:
            _vcarve_axis(doc, setup, op, tool, tp, em, here, reg, tan_h, rt, depth_max, d_flat)
            return
        # cadre ignoré (gravure en relief) : la ligne médiane du fond toucherait le cadre — les formes
        # hors cadre en ligne médiane, le fond du cadre en passes décalées (qui sautent le cadre)
        inner = reg.difference(keep).buffer(0)
        if not inner.is_empty:
            _vcarve_axis(doc, setup, op, tool, tp, em, here, inner, tan_h, rt, depth_max, d_flat)
            if em.pos is not None:
                here = em.pos[:2]
        reg = reg.intersection(keep).buffer(0)
        tp.warnings.append('gravure 2,5D en ligne médiane : cadre ignoré — le fond du cadre est gravé en passes '
                           'décalées')
    step = max(0.01, op.resolution or 0.05)
    qs = S._quad_segs(max(d_flat, tol), tol)
    region_right = not op.climb
    contour_2d = getattr(op, 'vcarve_mode', 'passes') == 'contour'
    passes = []                                           # (retrait, z, région du retrait)
    dists = []
    d = rt + step
    while d < d_flat - 1e-9 and not contour_2d and walls:
        dists.append(d)
        d += step
    from ..core import workers
    raw = S.erosions(reg, dists, qs)                      # retraits indépendants : sur les fils de calcul
    for d, g in zip(dists, workers.pmap(lambda g: S.simplify_parts(g, tol / 2), raw)):
        passes.append((d, -min(depth_max, (d - rt) / tan_h), g))
    # fond plat : à la profondeur maximale seule la pointe coupe le fond ;
    # pas choisi pour des crêtes d'au plus FLAT_RIDGE entre deux passes
    d_ring = max(0.0, d_flat + float(getattr(op, 'vcarve_offset', 0.0) or 0.0)) if contour_2d else d_flat
    base = S.erode(reg, d_ring, qs)
    from . import linkprev
    linked = bool(getattr(op, 'link_previous', False)) and bool(linkprev.cutting(S.previous_toolpaths()))
    if contour_2d and base.is_empty:
        tp.warnings.append(f'contour 2D : formes plus étroites que le cône à {depth_max:g} mm de profondeur '
                           f'(il faut {2 * d_ring:.3f} mm) ; réduire la profondeur ou le décalage')
        return
    floor_links = not (contour_2d and linked)             # vidage partiel : pas de liaison au fond à travers la matière
    if contour_2d:
        passes.append((d_ring, -depth_max, base))         # le contour, toujours entier
        if not getattr(op, 'vcarve_edges_only', False):
            flat_step = _floor_step(op, rt, tan_h)
            inner = S.erode(base, flat_step, qs)
            if linked and not inner.is_empty:
                todo = linkprev.uncleared(reg, S.previous_toolpaths(), setup, -depth_max, tol)
                if todo is not None:
                    inner = inner.intersection(todo.buffer(rt + flat_step, quad_segs=qs)).buffer(0)
            flat = S.concentric(inner, flat_step, tol) if not inner.is_empty else []
            passes += [(d_ring + (k + 1) * flat_step, -depth_max, g) for k, g in enumerate(flat)]
        missed = reg.difference(base.buffer(d_ring, quad_segs=qs).buffer(tol)).area
        if missed > 1e-3:
            tp.warnings.append(f'contour 2D : {missed:.3f} mm² hors de portée à {depth_max:g} mm de profondeur '
                               '(angles vifs, parties étroites)')
    elif linked and not base.is_empty:
        # lié au parcours précédent : le fond est repris (même en finition « bords seuls »), mais
        # seulement là où les parcours d'avant ont laissé de la matière à la profondeur de la gravure
        todo = linkprev.uncleared(reg, S.previous_toolpaths(), setup, -depth_max, tol)
        if todo is not None:
            near = rt + 2 * (rt + FLAT_RIDGE * tan_h) + step
            base = base.intersection(todo.buffer(near, quad_segs=qs)).buffer(0)
    if contour_2d:
        pass
    elif not base.is_empty and getattr(op, 'vcarve_edges_only', False) and not linked:
        # finition (TypeEdit) : bords et tirés d'angle seulement — le fond a été
        # vidé avant (balayage) ; un tour au pied des bords, à la profondeur
        passes.append((d_flat, -depth_max, base))
    elif not base.is_empty:
        flat_step = _floor_step(op, rt, tan_h)
        rough = setup.tool(op.ref_tool_id) if op.ref_tool_id else None
        if rough is not None:
            # gamme : l'ébauche (poche laissant d_flat le long des bords) a vidé
            # `done` ; la pointe ne reprend que le fond hors de sa portée
            R = rough.radius_at(depth_max)
            done = S.erode(reg, R + d_flat, qs).buffer(R, quad_segs=qs)
            todo = base.buffer(rt, quad_segs=qs).difference(done).buffer(-0.005).buffer(0.005)
            base = base.intersection(todo.buffer(rt + 1e-3, quad_segs=qs))
        flat = S.concentric(base, flat_step, tol) if not base.is_empty else []
        if len(flat) > 400:
            tp.warnings.append(f'gravure 2,5D : fond plat en {len(flat)} passes à la pointe — '
                               'une gamme (ébauche à la fraise plate) serait plus rapide')
        for k, g in enumerate(flat):
            passes.append((d_flat + k * flat_step, -depth_max, g))
    limit = int(getattr(op, 'vcarve_max_steps', 0) or 0)
    if limit > 0 and len(passes) > limit:                # TypeEdit : nombre de pas limité, depuis le bord
        tp.warnings.append(f'gravure 2,5D : {limit} passe(s) sur {len(passes)} (nombre de passes limité)')
        passes = passes[:limit]
    # parties plus étroites que le premier retrait (passage entre deux motifs, pointe d'un angle aigu) :
    # aucune passe décalée n'y entre, la pointe suit leur ligne médiane (comme TypeEdit)
    d0 = min((d for d, _z, _g in passes), default=min(rt + step, d_flat))
    axis = [] if contour_2d else narrow_axis(reg, d0, rt, tan_h, depth_max, step, qs)   # l'axe remonte dans les angles
    if not contour_2d:
        axis += corner_axis(reg, d0, rt, tan_h, depth_max, float(getattr(op, 'corner_pull_angle', 135.0) or 0.0), S.keep_exteriors(op, reg), axis)
    if not passes and not axis:
        tp.warnings.append('gravure 2,5D : formes plus fines que la pointe de l\'outil')
        return
    reached = max([-z for _d, z, _r in passes] + [-p[2] for c in axis for p in c])
    cotes = S.levels(reached, vstep) if vstep > 0 else [-reached]
    if len(cotes) > 1:                                   # passe en Z : paliers, forme par forme
        passes = vcarve_layers(passes, cotes, rt, tan_h)
    # forme par forme, au plus proche ; liaison au fond permise dans le retrait de la passe d'avant
    keep = S.keep_exteriors(op, reg)                     # cadre englobant seul sauté (gravure en relief)
    # TE13 : du centre vers le bord, le contour en dernier (« En partant de l'extérieur » : l'inverse). En paliers : chaque palier du bord vers le centre.
    inner_first = len(cotes) == 1 and not getattr(op, 'pocket_outside_in', False)
    by_branch = te_rule and inner_first and getattr(op, 'gravure_rule', 0) >= 879
    if te_rule and keep is not True:                      # relevé dans TE13 : seule la passe le long du bord du cadre saute, le fond va jusqu'à lui
        each = [keep if d <= d_flat + 1e-9 else True for d, _z, _g in passes]
        tp.warnings.append('gravure 2,5D : cadre englobant ignoré : le fond va jusqu\'à lui, sans la passe le long de son bord')
    else:
        each = keep
    if by_branch:                                         # relevé dans TE13 : une branche finie avant la suivante
        groups = S.nested_rings(reg, [g for _d, _z, g in passes], region_right, exteriors=each, here=here)
    elif te_rule and keep is not True:
        groups = S.part_rings(reg, [g for _d, _z, g in passes], region_right, exteriors=each)
    else:
        groups = S.part_rings(reg, [g for _d, _z, g in passes], region_right, exteriors=keep)
        if keep is not True:
            tp.warnings.append('gravure 2,5D : cadre englobant ignoré (gravure en relief)')
    groups = [g for g in groups if g and g[0][1]]                 # sans passe décalée : la ligne médiane seule
    if len(groups) > 1:
        marks = [([(g[0][1][0][0][0], g[0][1][0][0][1], i)], False) for i, g in enumerate(groups)]
        groups = [groups[c[0][0][2]] for c in S.order_chains(marks, here)]
    if inner_first and not by_branch:
        groups = [[x for x in g[::-1] if x[1]] for g in groups]
        groups = [g for g in groups if g]
        if len(groups) > 1:
            marks = [([(g[0][1][0][0][0], g[0][1][0][0][1], i)], False) for i, g in enumerate(groups)]
            groups = [groups[c[0][0][2]] for c in S.order_chains(marks, here)]

    first_at_depth: dict = {}
    for i, (_d, z_i, _g) in enumerate(passes):
        first_at_depth.setdefault(round(z_i, 9), i)

    def link_pass(pi: int) -> int:                        # la passe qui borne une liaison à la cote de pi
        return first_at_depth[round(passes[pi][1], 9)] if inner_first else max(0, pi - 1)

    axis_of = _axis_by_part(reg, axis, groups)
    # retraits des liaisons, un par distance : en parallèle
    need = sorted({passes[link_pass(pi)][0] for group in groups for pi, _r in group})
    zones = dict(zip(need, workers.pmap(lambda d: S.erode(reg, d - 1e-6, qs), need)))
    tests: dict = {}
    for gi, group in enumerate(groups):
        progress.step(gi, len(groups))
        for pi, rings in group:
            dz = passes[link_pass(pi)][0]
            if dz not in tests:
                tests[dz] = S.within_test(zones[dz])
            inside, z = tests[dz], passes[pi][1]
            for pts in rings:
                pts = S._start_nearest(pts, True, em.pos)
                if floor_links and em.pos is not None and em.pos[2] < 0 and \
                        inside(LineString([em.pos[:2], pts[0][:2]])):
                    # liaison au fond, à la profondeur sûre de la zone testée
                    zl = max(em.pos[2], passes[link_pass(pi)][1])
                    if zl > em.pos[2] + 1e-9:
                        em.feed(em.pos[0], em.pos[1], zl)
                    em.feed(pts[0][0], pts[0][1], zl)
                    em.plunge(z)
                elif op.ramp:                             # entrée dans la matière (TE : plongée angulaire)
                    S.cut_chain(em, pts, True, [z], ramp=True, ramp_angle=S.ramp_angle_of(op), z_start=z_from)
                    continue
                else:
                    em.travel(*pts[0][:2])
                    em.plunge(z)
                for p in pts[1:]:
                    em.feed(p[0], p[1], z)
        _cut_axis(em, axis_of.pop(gi, []), here, cotes)  # parties étroites de la forme : avant la suivante
    _cut_axis(em, [c for cs in axis_of.values() for c in cs], here, cotes)
    _check_depth(tp, tool, cotes)


def _check_depth(tp, tool, cotes) -> None:
    """Avertit si un palier (ou la gravure en une fois) dépasse 3 passes de
    l'outil."""
    per_pass = max(a - b for a, b in zip([0.0] + cotes, cotes))
    if per_pass > (tool.step_down or per_pass) * 3:
        tp.warnings.append(f'gravure 2,5D : {per_pass:.2f} mm de profondeur en une passe — '
                           'vérifier la tenue de l\'outil (ou régler la passe en Z de la gravure)')


def vcarve_layers(passes: list, cotes: list, rt: float, tan_h: float) -> list:
    """Gravure profonde en paliers : pour chaque cote (la dernière : le
    fond), les passes pas encore finies — celles qui s'arrêtent au-dessus de
    la cote, à leur profondeur ; les plus profondes ramenées à la cote,
    assez serrées pour que leurs cônes se rejoignent à LAYER_RIDGE × la
    passe au-dessus de la cote (crêtes reprises au palier suivant) ; à la
    dernière cote, toutes celles qui restent, à leur profondeur exacte.
    [(retrait, z, région)] palier après palier : `part_rings` les range
    ensuite forme par forme."""
    out, prev = [], 0.0
    for k, lz in enumerate(cotes):
        if k == len(cotes) - 1:
            out += [p for p in passes if p[1] < prev - 1e-9]
            break
        deeper = [i for i, p in enumerate(passes) if p[1] < lz - 1e-9]
        gap = 2 * (rt + LAYER_RIDGE * (prev - lz) * tan_h)
        keep = set(deeper[:1] + deeper[-1:])
        last = passes[deeper[0]][0] if deeper else 0.0
        for a, b in zip(deeper, deeper[1:]):
            if passes[b][0] - last > gap + 1e-9 or _vanishes(passes[a], passes[b], gap):
                keep.add(a)                               # la suivante serait trop loin, ou une partie s'arrête ici
                last = passes[a][0]
        for i, (d, z, g) in enumerate(passes):
            if z >= prev - 1e-9:
                continue                                  # finie à un palier d'avant
            if z >= lz - 1e-9:
                out.append((d, z, g))                     # finie à ce palier
            elif i in keep:
                out.append((d, lz, g))
        prev = lz
    return out


def _vanishes(pa, pb, gap: float) -> bool:
    """Une partie du retrait `pa` (branche étroite, petite forme) n'a plus
    de retrait en `pb` : la région de `pb` regonflée de l'écart des retraits
    (plus un quart de `gap`, angles vifs rendus : joints en onglet) ne
    couvre plus celle de `pa`."""
    ga, gb = pa[2], pb[2]
    if ga is None or ga.is_empty:
        return False
    if gb is None or gb.is_empty:
        return True
    return not gb.buffer(pb[0] - pa[0] + 0.25 * gap, quad_segs=8, join_style='mitre').covers(ga)


def axis_layers(pts: list, cotes: list) -> list:
    """Ligne médiane [(x, y, z)…] en paliers : pour chaque cote, les
    morceaux pas encore finis, z ramené à la cote (un point de part et
    d'autre de chaque morceau : rien ne reste aux raccords) ; à la dernière
    cote, la profondeur exacte. [[morceau…] par cote]."""
    out, prev = [], 0.0
    for lz in cotes:
        level, i, n = [], 0, len(pts)
        while i < n:
            if pts[i][2] >= prev - 1e-9:
                i += 1
                continue
            j = i
            while j < n and pts[j][2] < prev - 1e-9:
                j += 1
            run = [(x, y, max(z, lz)) for x, y, z in pts[max(0, i - 1):min(n, j + 1)]]
            if len(run) >= 2:
                level.append(run)
            i = j
        out.append(level)
        prev = lz
    return out


# --- relief 3D -----------------------------------------------------------------------------

def _gray(image: Image, nx: int, ny: int):
    """Niveaux de gris (0 noir … 1 blanc) de l'image ré-échantillonnée en
    nx × ny ; None si l'image ne se lit pas."""
    import numpy as np
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor, QImage, QPainter
    from ..io.raster import _app
    _app()
    if image.fmt == 'dib':
        from ..ui.canvas import dib_to_qimage
        q = dib_to_qimage(image.data)
    else:
        q = QImage.fromData(image.data)
    if q is None or q.isNull():
        return None
    if q.format() == QImage.Format.Format_Grayscale16:
        # carte de hauteurs 16 bits (galbe, TypeArt) : ré-échantillonnée sans
        # repasser par 8 bits (bilinéaire)
        import numpy as np
        from ..core.galbe import gray_array
        G = gray_array(q)
        h, w = G.shape
        fx = np.clip((np.arange(nx) + 0.5) * w / nx - 0.5, 0, w - 1)
        fy = np.clip((np.arange(ny) + 0.5) * h / ny - 0.5, 0, h - 1)
        x0 = np.floor(fx).astype(int)
        y0 = np.floor(fy).astype(int)
        x1 = np.minimum(x0 + 1, w - 1)
        y1 = np.minimum(y0 + 1, h - 1)
        tx = (fx - x0)[None, :]
        ty = (fy - y0)[:, None]
        top = G[np.ix_(y0, x0)] * (1 - tx) + G[np.ix_(y0, x1)] * tx
        bot = G[np.ix_(y1, x0)] * (1 - tx) + G[np.ix_(y1, x1)] * tx
        return top * (1 - ty) + bot * ty
    q = q.scaled(nx, ny, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
    flat = QImage(q.size(), QImage.Format.Format_RGB32)
    flat.fill(QColor('white'))
    p = QPainter(flat)
    p.drawImage(0, 0, q)
    p.end()
    g = flat.convertToFormat(QImage.Format.Format_Grayscale8)
    arr = np.frombuffer(g.constBits(), np.uint8, g.sizeInBytes()).reshape(g.height(), g.bytesPerLine())
    return arr[:, :g.width()].astype(float) / 255.0


def _body(tool) -> float:
    """Plus grand diamètre qui coupe (cône : jusqu'à la queue, `CamTool.body_diameter`)."""
    f = getattr(tool, 'body_diameter', None)
    return f() if callable(f) else tool.diameter


def tool_profile(tool, d):
    """Hauteur de la surface de l'outil au-dessus de sa pointe, à la
    distance d de l'axe (numpy) ; inf au-delà du rayon."""
    import numpy as np
    r = _body(tool) / 2
    out = np.full(np.shape(d), np.inf)
    inside = d <= r + 1e-12
    if tool.kind == 'boule':
        out[inside] = r - np.sqrt(np.maximum(0.0, r * r - d[inside] ** 2))
    elif tool.kind == 'conique' and 0 < tool.angle < 180:
        t = math.tan(math.radians(tool.angle) / 2)
        out[inside] = np.maximum(0.0, d[inside] - tool.tip / 2) / t
    elif tool.kind == 'profil' and getattr(tool, 'profile', None):
        # outil spécial : la plus basse hauteur où le profil atteint la distance d
        P = sorted((float(b), float(a)) for a, b in tool.profile)
        hs = np.array([h for h, _r in P])
        rs = np.maximum.accumulate(np.array([r for _h, r in P]))
        H = np.linspace(hs[0], hs[-1], 400)
        R = np.maximum.accumulate(np.interp(H, hs, rs))
        k = np.searchsorted(R, d[inside], side='left')
        ok = k < len(H)
        vals = np.full(k.shape, np.inf)
        vals[ok] = H[k[ok]]
        out[inside] = vals
    else:
        out[inside] = 0.0
    return out


def _flat_compensate(P, k: int, ny: int, nx: int, res: float, r: float):
    """Fraise plate : dilatation par le disque, ligne par ligne — pour chaque
    décalage vertical, le maximum sur la demi-largeur du disque à cette
    hauteur, lu dans une table de maxima glissants par puissances de deux
    (deux lectures par fenêtre) : O(k log k) passes au lieu de O(k²)."""
    import numpy as np
    levels = [P]                                         # levels[p][:, x] = max(P[:, x : x + 2^p])
    while (1 << len(levels)) <= 2 * k + 1:
        prev, s = levels[-1], 1 << (len(levels) - 1)
        nxt = prev.copy()
        np.maximum(nxt[:, :-s], prev[:, s:], out=nxt[:, :-s])
        levels.append(nxt)
    T = np.full((ny, nx), -np.inf)
    for dy in range(-k, k + 1):
        progress.step(dy + k, 2 * k + 1, "Compensation de l'outil : ligne {0} sur {1}")
        # demi-largeur w : les dx tels que hypot(dx, dy)·res ≤ r (même test que la boucle)
        w = -1
        while w + 1 <= k and math.hypot(w + 1, dy) * res <= r + 1e-12:
            w += 1
        if w < 0:
            continue
        n = 2 * w + 1
        p = n.bit_length() - 1
        L = levels[p]
        rows = slice(k + dy, k + dy + ny)
        a = L[rows, k - w:k - w + nx]
        b = L[rows, k + w - (1 << p) + 1:k + w - (1 << p) + 1 + nx]
        np.maximum(T, np.maximum(a, b), out=T)
    return T


def compensate(H, res: float, tool, pad: float = 0.0):
    """Cote de la pointe de l'outil en chaque point de la grille : la plus
    haute qui ne fait pas entrer l'outil dans la surface H (dilatation par
    le profil de l'outil). Hors de la carte, la matière est à Z = 0."""
    import numpy as np
    r = tool.diameter / 2
    if tool.kind == 'conique' and 0 < getattr(tool, 'angle', 0) < 180 and H.size:
        # cône : jusqu'à sa queue, mais plus haut que le relief son flanc ne touche rien
        span = max(float(np.max(H)), float(pad)) - float(np.min(H))
        r = max(r, min(_body(tool) / 2, tool.tip / 2 + span * math.tan(math.radians(tool.angle) / 2) + res))
    k = max(0, int(math.ceil(r / res)))
    ny, nx = H.shape
    P = np.full((ny + 2 * k, nx + 2 * k), float(pad))    # hors de la carte : `pad` (0 : matière au ras du dessus)
    P[k:k + ny, k:k + nx] = H
    if tool.kind not in ('boule', 'conique', 'profil'):  # bout plat : profil nul dans le disque
        return _flat_compensate(P, k, ny, nx, res, r)
    T = np.full(H.shape, -np.inf)
    for dy in range(-k, k + 1):
        progress.step(dy + k, 2 * k + 1, "Compensation de l'outil : ligne {0} sur {1}")
        for dx in range(-k, k + 1):
            d = math.hypot(dx, dy) * res
            prof = tool_profile(tool, np.array([d]))[0]
            if not math.isfinite(prof):
                continue
            np.maximum(T, P[k + dy:k + dy + ny, k + dx:k + dx + nx] - prof, out=T)
    return T


def envelope(T, res: float, tool):
    """Surface que laisse un outil dont la pointe a suivi les cotes T : en
    chaque point, le plus bas qu'a atteint sa surface (érosion par le profil
    de l'outil). La matière restante est entre cette surface et la pièce."""
    import numpy as np
    return -compensate(-np.asarray(T, dtype=np.float64), res, tool, pad=-np.inf)


def _relief(doc, setup, op, tool, tp, em, here) -> None:
    import numpy as np
    images = [it for it in S.source_items(doc, op) if isinstance(it, Image)]
    if not images:
        tp.warnings.append('relief : aucune image parmi les objets choisis (blanc = surface, noir = fond)')
        return
    res = max(0.02, op.resolution or 0.1)
    for img in images:
        depth = abs(op.depth)
        if depth <= 0 and 'galbe' in img.extra:
            # relief TypeArt : sa propre profondeur (sommet affleurant)
            depth = float(img.extra['galbe'].get('relief_depth') or 0.0)
            tp.warnings.append(f'relief : profondeur du relief TypeArt, {depth:.3f} mm')
        if depth <= 0:
            tp.warnings.append('relief : profondeur nulle')
            continue
        m = img.matrix
        if abs(m.b) > 1e-9 or abs(m.c) > 1e-9:
            tp.warnings.append('relief : image tournée — usinée selon sa boîte englobante')
        x0, y0, x1, y1 = img.bbox()
        nx, ny = max(2, int(round((x1 - x0) / res)) + 1), max(2, int(round((y1 - y0) / res)) + 1)
        if nx * ny > 6_000_000:
            tp.warnings.append(f'relief : carte de {nx} × {ny} points, trop grande — augmenter le pas')
            continue
        gray = _gray(img, nx, ny)
        if gray is None:
            tp.warnings.append('relief : image illisible')
            continue
        gray = gray[::-1]                                  # lignes de bas en haut : y croissant
        H = -(gray if op.invert else (1.0 - gray)) * depth
        T = with_stock(H, res, tool, op.stock)
        if ((getattr(op, 'scan_mode', 'passes') or 'passes') == 'passes' and getattr(op, 'follow_profile', True)
                and not getattr(op, 'parallel_slices', 0)):
            _raster(em, setup, op, tool, T, x0, y0, res, depth)
        else:
            from . import mill3d
            levels = mill3d.useful_levels(S.levels(depth, op.step_down or tool.step_down), T)
            mill3d.finish(em, setup, op, tool, T, mill3d.Grid(x0, y0, nx, ny, res), levels, None, tp)
    if depth > (tool.cut_length or depth):
        tp.warnings.append('relief : profondeur supérieure à la longueur utile')


#: triangles couvrant au plus SMALL × SMALL nœuds : traités en bloc ; par paquets de CHUNK
SMALL = 8
CHUNK = 20000


def _small_triangles(H, T, x0: float, y0: float, res: float) -> None:
    """Petits triangles (boîte de SMALL × SMALL nœuds au plus) rastérisés
    ensemble : mêmes nœuds, même test d'appartenance que la boucle."""
    import numpy as np
    ny, nx = H.shape
    xs, ys, zs = T[:, :, 0], T[:, :, 1], T[:, :, 2]
    i0 = np.maximum(0, np.floor((xs.min(axis=1) - x0) / res).astype(int))
    j0 = np.maximum(0, np.floor((ys.min(axis=1) - y0) / res).astype(int))
    i1 = np.minimum(nx - 1, np.ceil((xs.max(axis=1) - x0) / res).astype(int))
    j1 = np.minimum(ny - 1, np.ceil((ys.max(axis=1) - y0) / res).astype(int))
    den = (ys[:, 1] - ys[:, 2]) * (xs[:, 0] - xs[:, 2]) + (xs[:, 2] - xs[:, 1]) * (ys[:, 0] - ys[:, 2])
    keep = (i1 >= i0) & (j1 >= j0) & (np.abs(den) >= 1e-12)
    if not keep.any():
        return
    xs, ys, zs, i0, j0, i1, j1, den = (a[keep] for a in (xs, ys, zs, i0, j0, i1, j1, den))
    d = np.arange(SMALL)
    shape = (len(i0), SMALL, SMALL)
    II = np.broadcast_to(i0[:, None, None] + d[None, None, :], shape)
    JJ = np.broadcast_to(j0[:, None, None] + d[None, :, None], shape)
    valid = (II <= i1[:, None, None]) & (JJ <= j1[:, None, None])
    X = x0 + II * res
    Y = y0 + JJ * res
    a1, b1 = (ys[:, 1] - ys[:, 2])[:, None, None], (xs[:, 2] - xs[:, 1])[:, None, None]
    a2, b2 = (ys[:, 2] - ys[:, 0])[:, None, None], (xs[:, 0] - xs[:, 2])[:, None, None]
    dx, dy = X - xs[:, 2][:, None, None], Y - ys[:, 2][:, None, None]
    dn = den[:, None, None]
    l1 = (a1 * dx + b1 * dy) / dn
    l2 = (a2 * dx + b2 * dy) / dn
    l3 = 1.0 - l1 - l2
    inside = valid & (l1 >= -1e-9) & (l2 >= -1e-9) & (l3 >= -1e-9)
    if not inside.any():
        return
    Z = l1 * zs[:, 0][:, None, None] + l2 * zs[:, 1][:, None, None] + l3 * zs[:, 2][:, None, None]
    np.maximum.at(H, (JJ[inside], II[inside]), Z[inside])


def heightmap_from_triangles(tris, x0: float, y0: float, nx: int, ny: int, res: float):
    """Carte de hauteurs vue de dessus d'un maillage (N × 3 × 3, mm) : la
    plus haute face en chaque nœud de la grille ; -inf hors de la pièce.
    Les petits triangles (la plupart dans un maillage fin) sont traités en
    bloc par numpy ; les autres un à un."""
    import numpy as np
    H = np.full((ny, nx), -np.inf)
    tris = np.asarray(tris, dtype=float).reshape(-1, 3, 3)
    if len(tris):
        span_i = np.ceil((tris[:, :, 0].max(axis=1) - x0) / res) - np.floor((tris[:, :, 0].min(axis=1) - x0) / res)
        span_j = np.ceil((tris[:, :, 1].max(axis=1) - y0) / res) - np.floor((tris[:, :, 1].min(axis=1) - y0) / res)
        small = (span_i < SMALL) & (span_j < SMALL)
        S = tris[small]
        for k in range(0, len(S), CHUNK):
            progress.check()
            _small_triangles(H, S[k:k + CHUNK], x0, y0, res)
        tris = tris[~small]
    for t in tris:
        xs, ys, zs = t[:, 0], t[:, 1], t[:, 2]
        i0 = max(0, int(math.floor((xs.min() - x0) / res)))
        i1 = min(nx - 1, int(math.ceil((xs.max() - x0) / res)))
        j0 = max(0, int(math.floor((ys.min() - y0) / res)))
        j1 = min(ny - 1, int(math.ceil((ys.max() - y0) / res)))
        if i1 < i0 or j1 < j0:
            continue
        den = (ys[1] - ys[2]) * (xs[0] - xs[2]) + (xs[2] - xs[1]) * (ys[0] - ys[2])
        if abs(den) < 1e-12:
            continue                                       # face verticale : vue de dessus, sans aire
        X, Y = np.meshgrid(x0 + np.arange(i0, i1 + 1) * res, y0 + np.arange(j0, j1 + 1) * res)
        l1 = ((ys[1] - ys[2]) * (X - xs[2]) + (xs[2] - xs[1]) * (Y - ys[2])) / den
        l2 = ((ys[2] - ys[0]) * (X - xs[2]) + (xs[0] - xs[2]) * (Y - ys[2])) / den
        l3 = 1.0 - l1 - l2
        inside = (l1 >= -1e-9) & (l2 >= -1e-9) & (l3 >= -1e-9)
        if not inside.any():
            continue
        Z = l1 * zs[0] + l2 * zs[1] + l3 * zs[2]
        sub = H[j0:j1 + 1, i0:i1 + 1]
        np.maximum(sub, np.where(inside, Z, -np.inf), out=sub)
    return H


class _SwapXY:
    """Émetteur qui échange X et Y (passes selon Y sur la carte transposée)."""

    def __init__(self, em):
        self.em = em

    def travel(self, x, y):
        self.em.travel(y, x)

    def plunge(self, z):
        self.em.plunge(z)

    def feed(self, x, y, z):
        self.em.feed(y, x, z)

    def retract(self):
        self.em.retract()


def _raster(em, setup, op, tool, T, x0: float, y0: float, res: float, depth: float) -> None:
    """Balayage en aller-retour de la carte compensée T (cotes de pointe),
    en passes de Z jusqu'à −depth — selon X, selon Y, ou croisé (toutes les
    passes selon X, puis la dernière cote reprise selon Y : finition qui
    efface les crêtes du premier sens)."""
    mode = getattr(op, 'raster_dir', 'x') or 'x'
    levels = S.levels(depth, op.step_down or tool.step_down)
    if mode == 'y':
        _raster_rows(_SwapXY(em), setup, tool, T.T, y0, x0, res, levels)
        return
    _raster_rows(em, setup, tool, T, x0, y0, res, levels)
    if mode == 'xy' and levels:
        _raster_rows(_SwapXY(em), setup, tool, T.T, y0, x0, res, levels[-1:])


def _raster_rows(em, setup, tool, T, x0: float, y0: float, res: float, levels) -> None:
    import numpy as np
    ny, nx = T.shape
    step_over = max(res, (tool.stepover or 0.2) * tool.diameter)
    xs = x0 + np.arange(nx) * res
    rows = np.arange(0, ny, max(1, int(round(step_over / res))))
    if rows[-1] != ny - 1:
        rows = np.append(rows, ny - 1)
    for zl in levels:
        em.retract()
        forward = True
        for j, row in enumerate(rows):
            if j % 8 == 0:
                progress.check()
            y = float(y0 + row * res)
            zrow = np.maximum(T[row], zl)
            idx = range(nx) if forward else range(nx - 1, -1, -1)
            pts = _simplify([(float(xs[i]), y, float(zrow[i])) for i in idx], setup.tolerance)
            if j == 0:
                em.travel(pts[0][0], pts[0][1])
                em.plunge(pts[0][2])
            else:
                prev_row = rows[j - 1]
                col = 0 if forward else nx - 1
                seg = np.maximum(T[prev_row:row + 1, col], zl)
                for r_i, z in zip(range(prev_row + 1, row + 1), seg[1:]):
                    em.feed(float(xs[col]), float(y0 + r_i * res), float(z))
            for p in pts[1:]:
                em.feed(*p)
            forward = not forward


def _surface3d(doc, setup, op, tool, tp, em, here) -> None:
    """Pièce 3D (STEP, STL, 3D XML) : vue de dessus maillée, haut de la
    pièce à Z = 0, balayée jusqu'à −depth (au-delà, la pièce n'est pas
    suivie) ; faces ou contours choisis dans la vue 3D : seulement là."""
    import numpy as np
    from . import mill3d
    op = mill3d.zone_op(doc, op)
    res = max(0.02, op.resolution or 0.1)
    got = mill3d.piece_heights(doc, op, tool, tp, res, 'surface 3D')
    if got is None:
        return
    model, g, H, depth = got
    H[~np.isfinite(H)] = -depth                            # autour de la pièce : jusqu'à la profondeur
    H = np.maximum(H, -depth)
    T = with_stock(H, res, tool, op.stock, pad=-depth)        # autour de la carte : le bas
    mask = mill3d.zone_mask(op, model, g, T, op.stock, tp.warnings, tool=tool)
    if mask is not None and not mask.any():
        if not tp.warnings:
            tp.warnings.append('surface 3D : la zone choisie est vide')
        return
    mask = mill3d.combine(mask, mill3d.slope_mask(T, res, op.slope_min, op.slope_max))
    if mask is not None and not mask.any():
        tp.warnings.append('surface 3D : aucune pente dans les limites choisies')
        return
    levels = mill3d.useful_levels(S.levels(depth, op.step_down or tool.step_down), T, mask)
    try:
        mill3d.finish(em, setup, op, tool, T, g, levels, mask, tp)
    except mill3d.TooBig as ex:
        tp.warnings.append(f'surface 3D : {ex}')


def _rest3d(doc, setup, op, tool, tp, em, here) -> None:
    """Reprise 3D : la matière que l'outil d'avant (`ref_tool_id`, plus
    gros) a laissée dans les creux et les angles, enlevée par l'outil de
    l'opération — balayage par paliers là seulement."""
    import numpy as np
    from . import mill3d
    prev = setup.tool(op.ref_tool_id) if op.ref_tool_id else None
    if prev is None:
        tp.warnings.append('reprise 3D : choisir l\'outil passé avant (« Outil passé avant »)')
        return
    op = mill3d.zone_op(doc, op)
    res = max(0.02, op.resolution or 0.1)
    got = mill3d.piece_heights(doc, op, tool, tp, res, 'reprise 3D', margin_tool=prev)
    if got is None:
        return
    model, g, H, depth = got
    H[~np.isfinite(H)] = -depth
    H = np.maximum(H, -depth)
    T = with_stock(H, res, tool, op.stock, pad=-depth)
    Tprev = with_stock(H, res, prev, op.stock, pad=-depth)   # même bord : pas de faux reste
    mask = mill3d.zone_mask(op, model, g, None, op.stock, tp.warnings)
    step = op.step_down or tool.step_down or tool.diameter / 2
    # matière vraiment laissée : surfaces atteintes par les deux outils (pas leurs cotes de pointe, qui font
    # passer pour du reste toute une bande au pied des parois, que l'outil d'avant ne pouvait pas approcher)
    if not mill3d.rest_raster(em, setup, op, tool, T, Tprev, g, step, mask,
                              direction=getattr(op, 'raster_dir', 'x') or 'x',
                              Eprev=envelope(Tprev, res, prev), Ecur=envelope(T, res, tool)):
        tp.warnings.append('reprise 3D : rien à reprendre (l\'outil d\'avant passe partout où celui-ci passe)')


def _waterline3d(doc, setup, op, tool, tp, em, here) -> None:
    """Niveaux constants 3D : l'outil fait le tour de la pièce à chaque
    cote (passe `step_down`), sur les pentes d'au moins `slope_min` degrés
    — finition des parois raides, que le balayage marque."""
    import numpy as np
    from . import mill3d
    op = mill3d.zone_op(doc, op)
    res = max(0.02, op.resolution or 0.05)
    got = mill3d.piece_heights(doc, op, tool, tp, res, 'niveaux constants')
    if got is None:
        return
    model, g, H, depth = got
    H[~np.isfinite(H)] = -depth
    H = np.maximum(H, -depth)
    T = with_stock(H, res, tool, op.stock, pad=-depth)
    zone = mill3d.zone_mask(op, model, g, None, op.stock, tp.warnings)
    if zone is not None:
        zone = mill3d.dilate(zone, int(math.ceil(tool.diameter / 2 / res)))
    mask = mill3d.combine(zone, mill3d.slope_mask(T, res, op.slope_min, op.slope_max))
    step = op.step_down or (mill3d.scallop_step(tool.diameter / 2, 0.01) if tool.kind == 'boule'
                            else tool.step_down)
    levels = [z for z in S.levels(depth, step) if z > float(T.min()) - 1e-9]
    if not mill3d.waterline(em, setup, op, tool, T, g, levels, mask):
        tp.warnings.append('niveaux constants : aucune paroi dans la zone')


def _rough3d(doc, setup, op, tool, tp, em, here) -> None:
    """Ébauche 3D par paliers en Z d'une pièce (STEP, STL, 3D XML) : à
    chaque palier, tout ce que l'outil peut enlever sans entamer la pièce
    ni sa surépaisseur, vidé en anneaux depuis le bord ; faces ou contours
    choisis dans la vue 3D : au-dessus d'eux seulement. Brut donné
    (`core.stock3d`, première prise) : paliers depuis son haut, tout le brut
    vidé autour de la pièce, rien hors de lui."""
    import numpy as np
    from . import mill3d
    from ..core import stock3d
    op = mill3d.zone_op(doc, op)
    res = max(0.05, op.resolution or 0.2)
    from ..core import workspace as WS
    sb = part = None
    if stock3d.of_setup(setup).active() and not WS.op_setup(op, doc)[0]:     # '+Z' écrit = la face du dessin
        part = mill3d.op_model(doc, op)
        sb = stock3d.box_for(doc, setup, part)
    got = mill3d.piece_heights(doc, op, tool, tp, res, 'ébauche 3D', cover=sb, model=part)
    if got is None:
        return
    model, g, H, depth = got
    H[~np.isfinite(H)] = -depth                            # autour de la pièce : la matière jusqu'à la profondeur
    H = np.maximum(H, -depth)
    T = with_stock(H, res, tool, op.stock + res / 2, pad=-depth)       # un demi-pas de plus : la carte échantillonne les bords
    mask = mill3d.zone_mask(op, model, g, None, op.stock, tp.warnings)
    if mask is not None:                                   # au-dessus des faces choisies : l'outil y entre en entier
        mask = mill3d.dilate(mask, int(math.ceil(tool.diameter / 2 / res)))
    top = 0.0
    if sb is not None:                                     # brut : l'outil ne sort pas de lui (bord compris)
        tp.warnings.extend(stock3d.check(sb, model.bounds()))
        inside = sb.inside(g.xs[None, :], g.ys[:, None], 0.9 * tool.diameter / 2)
        mask = inside if mask is None else (mask & inside)
        top = max(0.0, sb.top)
        em.clear = max(em.clear, top + op.clear_z)         # approche au-dessus du brut, pas dedans
        em.safe = max(em.safe, em.clear)
    levels = mill3d.useful_levels(mill3d.rough_levels(op, tool, depth, H, res), T, mask)
    if top > 1e-6:                                         # le brut au-dessus de la pièce : paliers depuis son haut
        above = mill3d.levels_above(top, op.step_down or tool.step_down or tool.diameter / 2)
        lift = max(0.0, float(op.stock or 0.0)) + res / 2  # juste au-dessus du haut de la pièce (surépaisseur)
        if 0.01 < lift < top - 0.01:
            above = sorted(set(above) | {lift}, reverse=True)
        levels = above + levels
    if not mill3d.zlevel_rough(em, setup, op, tool, tp, T, g, levels, mask, here, start=top):
        tp.warnings.append('ébauche 3D : rien à enlever')


def with_stock(H, res: float, tool, stock: float = 0.0, pad: float = 0.0):
    """Cotes de pointe de l'outil sur la carte H, avec une surépaisseur
    `stock` tout autour de la surface (ébauche : de la matière reste pour la
    finition) : la surface décalée de `stock` est suivie — comme l'outil
    élargi de 2 × stock, remonté de `stock` (exact pour une fraise boule,
    très proche pour une fraise droite)."""
    stock = max(0.0, float(stock or 0.0))
    if stock <= 0:
        return compensate(H, res, tool, pad)
    import dataclasses
    grown = dataclasses.replace(tool, diameter=tool.diameter + 2 * stock,
                                tip=(tool.tip + 2 * stock) if getattr(tool, 'tip', 0) else tool.tip)
    return compensate(H, res, grown, pad) + stock


def _simplify(pts: list, tol: float) -> list:
    """Points alignés (à tol près, en 3D) retirés."""
    if len(pts) <= 2:
        return pts
    out = [pts[0]]
    for k in range(1, len(pts) - 1):
        a, b, c = out[-1], pts[k], pts[k + 1]
        # écart de b à la droite ac
        ac = [c[i] - a[i] for i in range(3)]
        ab = [b[i] - a[i] for i in range(3)]
        L2 = sum(v * v for v in ac)
        if L2 <= 0:
            continue
        t = sum(ab[i] * ac[i] for i in range(3)) / L2
        dev = math.sqrt(sum((ab[i] - t * ac[i]) ** 2 for i in range(3)))
        if dev > tol:
            out.append(b)
    out.append(pts[-1])
    return out


def prismatic_heights(reg, tool, te: bool = False) -> tuple[float, float]:
    """Lettres prismatiques : (profondeur pour laquelle l'arête de la partie la
    plus large affleure à Z = 0, idem pour la plus étroite) — rayon inscrit
    moins la demi-troncature, divisé par tan(demi-angle). `te` : comme le bouton
    Calculer de TE13, sans la troncature (son centre suit le contour)."""
    import shapely
    tan_h = math.tan(math.radians(tool.angle) / 2)
    rt = 0.0 if te else tool.tip / 2
    radii = []
    for p in getattr(reg, 'geoms', [reg]):
        if p.geom_type != 'Polygon' or p.is_empty:
            continue
        radii.append(shapely.maximum_inscribed_circle(p, 0.01).length)
    if not radii:
        return 0.0, 0.0
    return max(0.0, (max(radii) - rt) / tan_h), max(0.0, (min(radii) - rt) / tan_h)


def _prism_parts(reg, geoms, tol) -> tuple:
    """Les formes de la région dans l'ordre de TE13 : celui du dessin, ce qui est à l'intérieur d'une forme avant elle. Et les points de départ
    des contours du dessin."""
    import numpy as np
    import shapely
    parts = shapely.get_parts(reg)
    parts = parts[(shapely.get_type_id(parts) == 3) & ~shapely.is_empty(parts)]
    firsts = [pts[0] for pts, closed in S.polylines(geoms, tol) if closed]
    n = len(parts)
    rank = np.full(n, len(firsts), dtype=int)
    if firsts and n:
        src, dst = shapely.STRtree(parts).query(shapely.points(firsts), predicate='dwithin', distance=1e-6)
        for f, p in sorted(zip(src.tolist(), dst.tolist()), reverse=True):
            rank[p] = f
    filled = shapely.polygons(shapely.get_exterior_ring(parts))
    area = shapely.area(filled)
    q, t = shapely.STRtree(filled).query(shapely.point_on_surface(parts), predicate='within')
    depth = np.zeros(n, dtype=int)
    top = np.arange(n)
    for i, j in zip(q.tolist(), t.tolist()):
        if i != j:
            depth[i] += 1
            if area[j] > area[top[i]]:
                top[i] = j
    order = sorted(range(n), key=lambda i: (int(rank[top[i]]), -int(depth[i]), int(rank[i])))
    return parts[order], firsts


PRISM_MIN_TURN = 22.5                                     # relevé dans TE13 : pas d'arête pour un tournant de 20°, une pour 25°, saillant ou rentrant


def _prismatic_te(setup, op, tool, tp, em, here, geoms, reg, tan_h) -> None:
    """Lettres prismatiques, relevées dans TE13 sur mes dessins. Le centre de l'outil suit, à chaque niveau z, le contour décalé vers
    l'intérieur en onglet : de (H + z)·tan en relief, le contour exact au fond ; de |z|·tan en creux. En relief les niveaux partent du fond, en creux
    de la surface. Passes latérales : à chaque niveau, tous les décalages entre le flanc et le bord (en relief), ou entre le flanc et le centre
    de la forme (en creux). Puis les arêtes du toit (le squelette droit) sont reprises, jusqu'au plat. Différence voulue : pas de passe à Z = 0, qui
    n'enlèverait rien."""
    import numpy as np
    import shapely
    from shapely.geometry import Point
    from . import skeleton as SK
    h_max, h_min = prismatic_heights(reg, tool, te=True)
    H = abs(op.depth) if op.depth else h_max
    tp.warnings.append(f'lettres prismatiques : arêtes à Z = 0 pour {h_max:.3f} mm de profondeur '
                       f'(lettre la plus étroite : {h_min:.3f} mm) ; ici {H:.3f} mm'
                       + (' — sommets plats là où la lettre est plus large' if H < h_max - 1e-6 else ''))
    if H <= 0:
        return
    h_tool = (_body(tool) / 2 - tool.tip / 2) / tan_h
    if H > h_tool + 1e-9:
        if op.depth:                                      # demandée : comme dans TE13, on la fait, en prévenant
            tp.warnings.append(f'lettres prismatiques : le cône de l\'outil ne fait que {h_tool:.3f} mm de haut pour {H:.3f} mm de profondeur : son corps touchera la matière')
        else:                                             # calculée, sans que personne ne l'ait choisie : pas au-delà de ce que l'outil peut faire
            tp.warnings.append(f'lettres prismatiques : profondeur limitée à {h_tool:.3f} mm (le cône de l\'outil) ; demandez-la pour aller plus bas')
            H = h_tool
    step = abs(op.step_down or tool.step_down or 0.0)
    if step <= 0 or step > H:
        step = H
    hollow = bool(op.prism_hollow)
    lateral = bool(op.prism_lateral)
    parts, firsts = _prism_parts(reg, geoms, setup.tolerance)
    if not len(parts):
        return
    first_tree = shapely.STRtree(shapely.points(firsts)) if firsts else None
    region_right = not op.climb                           # relevé : en avalant, le sens direct autour d'un extérieur, en relief comme en creux
    cache: dict = {}
    sources = shapely.geometrycollections(parts)

    def inset(d: float):
        key = round(d, 6)
        if key not in cache:
            if d <= 1e-9:
                cache[key] = parts
            else:
                raw = shapely.buffer(parts, -d, join_style='mitre', mitre_limit=20.0)
                whole = shapely.geometrycollections(shapely.get_parts(raw))
                if S.drop_splinters(whole, sources, -d) is not whole:      # un seul contrôle pour toutes les formes, et forme par forme s'il y a quelque chose à retirer
                    raw = np.array([S.drop_splinters(g, parts[k], -d) for k, g in enumerate(raw)], dtype=object)
                cache[key] = raw
        return cache[key]

    def rings(i: int, d: float, forward: bool) -> list:
        out = []
        for pts in S.rings_of(inset(d)[i], region_right):
            if first_tree is not None:
                pts = S._start_nearest(pts, True, firsts[int(first_tree.nearest(Point(pts[0][:2])))])
            out.append(pts)
        return out[::-1] if forward else out

    def cut_level(z: float, d: float, forward: bool) -> bool:
        any_ring = False
        for i in (range(len(parts)) if forward else range(len(parts) - 1, -1, -1)):
            for pts in rings(i, d, forward):
                S.cut_chain(em, pts, True, [z])
                any_ring = True
        return any_ring

    if hollow:
        zs = [-k * step for k in range(1, int(H / step + 1e-9) + 1) if k * step < H - 1e-9] + [-H]
        for z in zs:
            d = -z * tan_h
            if not lateral:
                cut_level(z, d, True)
                continue
            while cut_level(z, d, True):                  # jusqu'au centre de chaque forme
                d += step * tan_h
    else:
        zs = []
        z = -H
        while z < -1e-9:
            zs.append(z)
            z += step
        zs.reverse()
        ext = max(0.0, getattr(op, 'extension', 0.0) or 0.0)
        for z in zs:
            for z2 in (zs[zs.index(z):] if lateral else [z]):
                d = (H + z2) * tan_h
                if d <= 1e-9 and ext > 0:                 # « Débordement » : le fond autour des lettres, de l'extérieur vers elles
                    qs = S._quad_segs(max(setup.tolerance, 1e-3), setup.tolerance)
                    pitch = max(0.02, 2 * (tool.tip / 2 + FLAT_RIDGE * tan_h))
                    k = int(ext / pitch + 1e-9)
                    while k >= 1:
                        ring_list = [(pts, True) for pts in S.rings_of(S.buffer_checked(reg, k * pitch, qs), region_right)]
                        for pts, closed in S.order_chains(ring_list, em.pos or here):
                            S.cut_chain(em, pts, closed, [z])
                        k -= 1
                cut_level(z, d, d <= 1e-9)

    def z_of(t: float) -> float:
        return -t / tan_h if hollow else -H + t / tan_h

    top = H * tan_h
    failed = 0
    for i in range(len(parts)):
        progress.step(i, len(parts))
        arcs = SK.checked_arcs(parts[i])
        if arcs is None:
            failed += 1
            continue
        corners = {(round(a[0], 3), round(a[1], 3)) for a in arcs if a[7] >= 0 and a[6] >= PRISM_MIN_TURN}
        crest = [p for pts in rings(i, top, True) for p in pts[:-1]]
        chains = []
        for pts in rings(i, 0.0, True):                   # la couture d'un contour courbe : de son départ au plat (les coins ont leur arête)
            s0 = pts[0]
            if crest and (round(s0[0], 3), round(s0[1], 3)) not in corners:
                near = min(crest, key=lambda p: math.dist(p[:2], s0[:2]))
                chains.append([(s0[0], s0[1], 0.0), (near[0], near[1], top)])
        chains += SK.roof_tours(arcs, top, PRISM_MIN_TURN)
        for chain in chains:
            em.travel(chain[0][0], chain[0][1])
            em.plunge(z_of(chain[0][2]))
            for x, y, t in chain[1:]:
                em.feed(x, y, z_of(t))
    if failed:
        tp.warnings.append(f'lettres prismatiques : arêtes non reprises sur {failed} forme(s) (squelette impossible à calculer)')


def _prismatic(doc, setup, op, tool, tp, em, here) -> None:
    """Lettres prismatiques (TypeEdit) : lettres en relief au profil
    triangulaire, arête au milieu. La pointe de l'outil conique suit le
    tour des lettres (décalé de la demi-troncature) à la profondeur H : le
    cône taille chaque flanc à la pente de l'outil, et l'arête affleure là
    où H = (rayon inscrit − demi-troncature) / tan(demi-angle). Profondeur 0 :
    celle de la lettre la plus large. « Débordement » : passes latérales qui
    dégagent le fond autour des lettres, de l'extérieur vers les lettres."""
    if tool.kind != 'conique' or not 0 < tool.angle < 180:
        tp.warnings.append('lettres prismatiques : choisir un outil conique (angle au sommet)')
        return
    geoms = [g for it in S.source_items(doc, op) if (g := S.item_geometry(it))]
    tol = setup.tolerance
    reg = S.region(geoms, tol)
    if reg.is_empty:
        tp.warnings.append('lettres prismatiques : aucun contour fermé')
        return
    tan_h = math.tan(math.radians(tool.angle) / 2)
    if getattr(op, 'prism_rule', 0) >= 882:
        _prismatic_te(setup, op, tool, tp, em, here, geoms, reg, tan_h)
        return
    rt = tool.tip / 2
    h_top, h_low = prismatic_heights(reg, tool)
    H = abs(op.depth) if op.depth else h_top
    h_tool = (_body(tool) / 2 - rt) / tan_h
    if H > h_tool + 1e-9:
        tp.warnings.append(f'lettres prismatiques : profondeur limitée à {h_tool:.3f} mm (diamètre de l\'outil)')
        H = h_tool
    tp.warnings.append(f'lettres prismatiques : arêtes à Z = 0 pour {h_top:.3f} mm de profondeur '
                       f'(lettre la plus étroite : {h_low:.3f} mm) ; ici {H:.3f} mm'
                       + (' — sommets plats là où la lettre est plus large' if H < h_top - 1e-6 else ''))
    if H <= 0:
        return
    qs = S._quad_segs(max(rt, tol), tol)
    region_right = op.climb                               # matière (les lettres) à droite en avalant
    ext = max(0.0, getattr(op, 'extension', 0.0) or 0.0)
    flat_step = max(0.02, 2 * (rt + FLAT_RIDGE * tan_h))
    offsets = []
    k = 1
    while ext > 0 and k * flat_step <= ext + 1e-9:
        offsets.append(rt + k * flat_step)
        k += 1
    offsets = list(reversed(offsets)) + [rt]              # de l'extérieur vers les lettres, le flanc en dernier
    zs = S.levels(H, op.step_down or tool.step_down)
    for z in zs:
        for off in offsets:
            g = S.buffer_checked(reg, off, qs) if off > 0 else reg
            rings = [(pts, True) for pts in S.rings_of(g, region_right)]
            for pts, closed in S.order_chains(rings, em.pos or here):
                S.cut_chain(em, pts, closed, [z])


def engraving_surface(reg, cone, depth: float, x0: float, y0: float, nx: int, ny: int, res: float):
    """Carte des cotes (≤ 0) laissées par une gravure 2,5D de la région `reg`
    à l'outil conique `cone`, au plus `depth` de profondeur : en chaque point
    intérieur, −min(depth, (distance au bord − rayon de pointe) / tan(½ angle)) ;
    dehors, 0."""
    import numpy as np
    import shapely
    tan_h = math.tan(math.radians(cone.angle) / 2)
    rt = cone.tip / 2
    xs = x0 + np.arange(nx) * res
    ys = y0 + np.arange(ny) * res
    X, Y = np.meshgrid(xs, ys)
    H = np.zeros((ny, nx))
    inside = shapely.contains_xy(reg, X, Y)
    if not inside.any():
        return H
    band = rt + depth * tan_h                              # au-delà du bord de cette distance : le fond
    core = reg.buffer(-band)
    deep = shapely.contains_xy(core, X, Y) if not core.is_empty else np.zeros_like(inside)
    H[inside] = -depth
    todo = inside & ~deep
    if todo.any():
        segs = []
        rings = [r for part in shapely.get_parts(reg) for r in shapely.get_rings(part)]
        for ring in rings:                               # bords (extérieurs et trous) de chaque morceau
            c = np.asarray(ring.coords)
            segs.extend(shapely.linestrings(np.stack([c[:-1], c[1:]], axis=1)))
        tree = shapely.STRtree(segs)
        pts = shapely.points(X[todo], Y[todo])
        _idx, dist = tree.query_nearest(pts, return_distance=True, all_matches=False)
        H[todo] = -np.minimum(depth, np.maximum(0.0, dist - rt) / tan_h)
    return H


def _finish25d(doc, setup, op, tool, tp, em, here) -> None:
    """Finition 2,5D : la surface d'une gravure 2,5D (cône de l'outil passé
    avant, sinon de l'outil de l'opération s'il est conique ; profondeur de
    l'opération, sinon celle du cône) balayée avec l'outil de l'opération ;
    ébauche : paliers en Z, surépaisseur tout autour de la surface (`stock`, en XY et en Z) et décalage en XY le long
    des flancs (`stock_xy`) qui s'y ajoute."""
    import dataclasses
    cone = setup.tool(op.ref_tool_id) if op.ref_tool_id else None
    if cone is None or cone.kind != 'conique':
        cone = tool if tool.kind == 'conique' else None
    if cone is None or not 0 < cone.angle < 180:
        tp.warnings.append('finition 2,5D : choisir l\'outil conique de la gravure 2,5D (« Outil passé avant »)')
        return
    geoms = [g for it in S.source_items(doc, op) if (g := S.item_geometry(it))]
    reg = S.region(geoms, setup.tolerance)
    if reg.is_empty:
        tp.warnings.append('finition 2,5D : aucun contour fermé')
        return
    tan_h = math.tan(math.radians(cone.angle) / 2)
    full = (_body(cone) / 2 - cone.tip / 2) / tan_h
    depth = min(abs(op.depth), full) if op.depth > 0 else full
    res = max(0.02, op.resolution or 0.05)
    grow = max(0.0, float(getattr(op, 'stock_xy', 0.0) or 0.0)) if getattr(op, 'rough_mode', False) else 0.0
    margin = tool.diameter / 2 + grow + 2 * res
    bx0, by0, bx1, by1 = reg.bounds
    x0, y0 = bx0 - margin, by0 - margin
    nx = int(math.ceil((bx1 - bx0 + 2 * margin) / res)) + 1
    ny = int(math.ceil((by1 - by0 + 2 * margin) / res)) + 1
    if nx * ny > 6_000_000:
        tp.warnings.append(f'finition 2,5D : carte de {nx} × {ny} points, trop grande — augmenter le pas')
        return
    H = engraving_surface(reg, cone, depth, x0, y0, nx, ny, res)
    cutter = tool
    if grow > 0:                                          # ébauche : l'outil élargi reste à `grow` des flancs
        cutter = dataclasses.replace(tool, diameter=tool.diameter + 2 * grow,
                                     tip=(tool.tip + 2 * grow) if getattr(tool, 'tip', 0) else tool.tip)
    T = with_stock(H, res, cutter, op.stock if getattr(op, 'rough_mode', False) else 0.0)
    air = T > -1e-4                                      # rien à enlever : l'outil passe au-dessus,
    T[air] = max(0.05, float(getattr(op, 'clear_z', 0.5) or 0.5))   # sans frotter la pièce
    if getattr(op, 'rough_mode', False):
        _raster(em, setup, op, tool, T, x0, y0, res, depth)
        return
    levels = S.levels(depth, depth)[-1:]                 # finition : la surface seule, d'une passe
    mode = getattr(op, 'raster_dir', 'x') or 'x'
    if mode == 'y':
        _raster_rows(_SwapXY(em), setup, tool, T.T, y0, x0, res, levels)
        return
    _raster_rows(em, setup, tool, T, x0, y0, res, levels)
    if mode == 'xy':
        _raster_rows(_SwapXY(em), setup, tool, T.T, y0, x0, res, levels)


STRATEGIES = {
    'fer_dorer': lambda *a: _emboss(*a),
    'finition25d': _finish25d,
    'vcarve': _vcarve,
    'prismatique': _prismatic,
    'relief': _relief,
    'surface3d': _surface3d,
    'ebauche3d': _rough3d,
    'reprise3d': _rest3d,
    'niveaux3d': _waterline3d,
}

__all__ = ['STRATEGIES', 'compensate', 'heightmap_from_triangles', 'tool_profile', 'Move']


# --- gravure 2,5D en ligne médiane (intaille optimisée) ---------------------------------------
def medial_axis(reg, step: float, min_dist: float | None = None) -> list[list[tuple[float, float]]]:
    """Axe médian approché d'une région (polylignes) : arêtes du diagramme de
    Voronoï des points du bord (rééchantillonné tous les `step` mm) qui
    restent dans la région et à plus de `min_dist` du bord (sinon ce sont des
    bissectrices entre points voisins d'un même côté), chaînées."""
    import shapely
    import numpy as np
    min_dist = step if min_dist is None else min_dist
    pts = []                                               # points du bord, en tableaux (sans objets Python)
    for poly in getattr(reg, 'geoms', [reg]):
        if poly.geom_type != 'Polygon' or poly.is_empty:
            continue
        for ring in [poly.exterior] + list(poly.interiors):
            pts.append(shapely.get_coordinates(shapely.segmentize(ring, step))[:-1])
    pts = np.unique(np.round(np.concatenate(pts), 9), axis=0) if pts else np.empty((0, 2))
    if len(pts) < 3:                                       # (sans doublons : GEOS refuse sinon le Voronoï)
        return []
    edges = shapely.get_parts(shapely.voronoi_polygons(shapely.multipoints(pts), only_edges=True))
    edges = edges[shapely.get_num_points(edges) >= 2]
    if len(edges) == 0:
        return []
    # tests sur tableaux (shapely vectorisé) : extrémités dans la région et loin du bord —
    # distance au bord par un arbre de ses segments (au lieu du bord entier, point par point)
    a_xy = shapely.get_coordinates(shapely.get_point(edges, 0))
    b_xy = shapely.get_coordinates(shapely.get_point(edges, -1))
    shapely.prepare(reg)
    ok = shapely.contains_xy(reg, a_xy[:, 0], a_xy[:, 1]) & shapely.contains_xy(reg, b_xy[:, 0], b_xy[:, 1])
    segs = []
    for poly in getattr(reg, 'geoms', [reg]):
        if poly.geom_type != 'Polygon' or poly.is_empty:
            continue
        for ring in [poly.exterior] + list(poly.interiors):
            c = np.asarray(ring.coords)[:, :2]
            segs.append(np.stack([c[:-1], c[1:]], axis=1))
    tree = shapely.STRtree(shapely.linestrings(np.concatenate(segs)))
    for xy in (a_xy, b_xy):
        idx = np.nonzero(ok)[0]
        if len(idx) == 0:
            break
        near, _t = tree.query(shapely.points(xy[idx]), predicate='dwithin', distance=min_dist)
        close = np.zeros(len(idx), dtype=bool)
        close[np.unique(near)] = True
        # dwithin : distance ≤ min_dist ; l'ancien test écartait distance < min_dist (égalité négligeable)
        ok[idx[close]] = False
    keep = []
    for i in np.nonzero(ok)[0].tolist():
        ka = tuple(round(float(v), 5) for v in a_xy[i])
        kb = tuple(round(float(v), 5) for v in b_xy[i])
        if ka != kb:                                       # arêtes nulles (points du bord alignés)
            keep.append((ka, kb))
    # chaînage : on suit les sommets de degré 2
    adj: dict = {}
    for a, b in keep:
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)
    used = set()
    chains = []

    def walk(start, nxt):
        line = [start, nxt]
        used.add(frozenset((start, nxt)))
        prev, cur = start, nxt
        while len(adj[cur]) == 2:
            n2 = adj[cur][0] if adj[cur][1] == prev else adj[cur][1]
            key = frozenset((cur, n2))
            if key in used:
                break
            used.add(key)
            line.append(n2)
            prev, cur = cur, n2
        return line
    for v, nb in adj.items():
        if len(nb) != 2:
            for n in nb:
                if frozenset((v, n)) not in used:
                    chains.append(walk(v, n))
    for v, nb in adj.items():                              # boucles sans extrémité
        for n in nb:
            if frozenset((v, n)) not in used:
                chains.append(walk(v, n))
    return chains


def _axis_by_part(reg, axis, groups) -> dict:
    """Lignes médianes rangées par forme : {n° de groupe de passes : lignes}
    (la partie de la région qui contient le premier point de la ligne) ;
    -1 pour celles d'une forme sans passe décalée."""
    if not axis:
        return {}
    import shapely
    parts = list(getattr(reg, 'geoms', [reg]))
    tree = shapely.STRtree(parts)
    owner = {}
    for gi, group in enumerate(groups):
        x, y = group[0][1][0][0][0], group[0][1][0][0][1]
        hit = tree.query(shapely.points(x, y), predicate='intersects')
        if len(hit):
            owner.setdefault(int(hit[0]), gi)
    out: dict = {}
    for c in axis:
        hit = tree.query(shapely.points(c[0][0], c[0][1]), predicate='intersects')
        gi = owner.get(int(hit[0]), -1) if len(hit) else -1
        out.setdefault(gi, []).append(c)
    return out


def _cut_axis(em, chains, here, cotes=None) -> None:
    """Lignes médianes au plus proche : la pointe descend selon la largeur ;
    `cotes` (passe en Z) : chaque ligne palier après palier."""
    for pts, _closed in S.order_chains([(c, False) for c in chains], em.pos[:2] if em.pos is not None else here):
        levels = axis_layers(pts, cotes) if cotes and len(cotes) > 1 else [[pts]]
        for level in levels:
            for run, _c in S.order_chains([(r, False) for r in level], em.pos[:2] if em.pos is not None else here):
                em.travel(run[0][0], run[0][1])
                em.plunge(run[0][2])
                for x, y, z in run[1:]:
                    em.feed(x, y, z)


def _floor_step(op, rt: float, tan_h: float) -> float:
    """Distance entre les passes du fond plat : celle de l'opération (TE : « Distance entre passes »), sinon celle qui ne laisse
    pas de crêtes de plus de FLAT_RIDGE."""
    step = float(getattr(op, 'stepover_mm', 0.0) or 0.0)
    return max(0.01, step) if step > 0 else max(0.02, 2 * (rt + FLAT_RIDGE * tan_h))


def corner_axis(reg, d0, rt, tan_h, depth_max, max_angle, keep=True, known=()) -> list:
    """Tirés d'angle (relevés dans TE13) : dans chaque angle saillant de la forme plus fermé que `max_angle`, la pointe remonte de
    la passe la plus proche du bord, le long de la bissectrice, jusqu'à toucher les deux bords en surface. Lignes [(x, y, z)…] comme
    celles de `narrow_axis`, sauf là où l'une d'elles passe déjà, là où il n'y a pas la place, et sur le cadre sauté (`keep`)."""
    if d0 <= rt + 1e-6 or max_angle <= 0:
        return []
    from shapely.geometry import LineString, MultiLineString, Point
    z0 = -min(depth_max, (d0 - rt) / tan_h)
    seen = MultiLineString([[p[:2] for p in c] for c in known if len(c) >= 2]) if known else None
    out = []
    for poly in getattr(reg, 'geoms', [reg]):
        if poly.geom_type != 'Polygon' or poly.is_empty:
            continue
        skip_outer = keep is not True and keep.covers(poly.representative_point())
        edge = poly.boundary
        for v, b, ang in S.corner_pulls(poly, False, max_angle):
            s = math.sin(ang / 2)
            if s < 1e-6 or (skip_outer and poly.exterior.distance(Point(v)) < 1e-9):
                continue
            tip = (v[0] + b[0] * rt / s, v[1] + b[1] * rt / s)
            end = (v[0] + b[0] * d0 / s, v[1] + b[1] * d0 / s)
            if abs(edge.distance(Point(tip)) - rt) > 1e-3 or abs(edge.distance(Point(end)) - d0) > 1e-3:
                continue
            if seen is not None and seen.distance(LineString([tip, end])) < (d0 - rt) / 4:
                continue
            out.append([(end[0], end[1], z0), (tip[0], tip[1], 0.0)])
    return out


def narrow_axis(reg, d0, rt, tan_h, depth_max, step, qs) -> list:
    """Lignes médianes [(x, y, z)…] des parties de la région que les passes
    décalées (premier retrait `d0`) n'atteignent pas : là où la région moins
    son ouverture au rayon d0 laisse de la place à la pointe (rayon `rt`).
    La pointe y descend selon la demi-largeur locale (d − rt) / tan."""
    import numpy as np
    import shapely
    if d0 <= rt + 1e-6:
        return []
    fit = S.erode(reg, rt + 1e-3, qs)                    # la pointe y tient
    if fit.is_empty:
        return []
    opened = S.erode(reg, d0, qs).buffer(d0, quad_segs=qs)
    # zone de la pointe moins l'ouverture (et pas la région moins l'ouverture : leurs bords se
    # confondent presque partout, la différence en devenait très lente)
    uncut = fit.difference(opened).buffer(-1e-4).buffer(1e-4)
    if uncut.is_empty or uncut.area < 1e-8:
        return []
    zone = reg.intersection(uncut.buffer(d0 + step, quad_segs=qs))       # l'axe calculé près d'elles seulement
    ax_step = max(0.02, min(step, d0 / 2))
    chains = medial_axis(zone, ax_step, min_dist=max(ax_step / 2, rt))
    if not chains:
        return []
    segs = []
    for poly in getattr(reg, 'geoms', [reg]):
        if poly.geom_type != 'Polygon' or poly.is_empty:
            continue
        for ring in [poly.exterior] + list(poly.interiors):
            c = np.asarray(ring.coords)[:, :2]
            segs.append(np.stack([c[:-1], c[1:]], axis=1))
    tree = shapely.STRtree(shapely.linestrings(np.concatenate(segs)))      # demi-largeur : distance au vrai bord
    near = uncut.buffer(1e-3)                            # là où rien d'autre ne passe
    shapely.prepare(near)
    dense = [shapely.get_coordinates(shapely.segmentize(shapely.LineString(c), ax_step)) for c in chains]
    allp = np.concatenate(dense)                         # demi-largeurs de tous les points d'un coup
    _i, dist = tree.query_nearest(shapely.points(allp), return_distance=True, all_matches=False)
    ok = (dist > rt + 1e-4) & (dist <= d0 + 1e-6) & shapely.contains_xy(near, allp[:, 0], allp[:, 1])
    z = -np.minimum(depth_max, (dist - rt) / tan_h)
    out, k = [], 0
    for c in dense:
        cur = []
        for j in range(k, k + len(c)):
            if ok[j]:
                cur.append((float(allp[j, 0]), float(allp[j, 1]), float(z[j])))
            elif cur:
                out.append(cur)
                cur = []
        if cur:
            out.append(cur)
        k += len(c)
    return [p for p in out if len(p) >= 2 and min(q[2] for q in p) < -0.005]


def prune_hairs(chains: list, reg, max_angle: float = 135.0, walls=None, tiny: float = 0.0) -> list:
    """L'axe médian sans ses branches parasites. Une branche sans issue qui part vers un sommet plus ouvert que `max_angle` n'apporte rien :
    sur une courbe en petits segments, il y en a une par sommet (un cercle donne une étoile). Le long d'une branche vers un sommet d'angle a,
    la distance au bord baisse de sin(a/2) par mm : c'est ce qui les reconnaît. Relevé dans TE13 : un cercle ne donne rien, une ellipse son
    segment entre les centres de courbure, un oblong son axe, un anneau son cercle moyen, et le 120° garde sa branche, le 150° non.
    `tiny` : ce qui reste isolé et fait moins que cela au total disparaît aussi (le petit amas au centre d'un cercle)."""
    if not chains:
        return chains
    import numpy as np
    import shapely
    if walls is None:
        from .finish import _walls_index
        walls = _walls_index(reg)
    if walls is None:
        return chains
    limit = math.sin(math.radians(max_angle) / 2)
    n = len(chains)
    ends = np.array([[chains[i][0][:2], chains[i][-1][:2]] for i in range(n)], dtype=float).reshape(-1, 2)
    _i, dist = walls.query_nearest(shapely.points(ends), return_distance=True, all_matches=False)
    key = [(round(float(p[0]), 4), round(float(p[1]), 4)) for p in ends]
    at: dict = {}
    for i in range(n):
        at.setdefault(key[2 * i], set()).add(i)
        at.setdefault(key[2 * i + 1], set()).add(i)
    alive = set(range(n))
    todo = list(range(n))
    while todo:
        i = todo.pop()
        if i not in alive:
            continue
        a, b = 2 * i, 2 * i + 1
        free_a = len(at[key[a]]) == 1
        free_b = len(at[key[b]]) == 1 or key[a] == key[b]
        if not free_a and not free_b:
            continue
        if free_a and free_b:
            free, joint = (a, b) if dist[a] <= dist[b] else (b, a)
        else:
            free, joint = (a, b) if free_a else (b, a)
        chord = math.dist(ends[free], ends[joint])
        drop = dist[joint] - dist[free]
        hair = chord < 1e-9 or drop / chord > limit
        lone = free_a and free_b and chord < tiny
        if hair or lone:
            alive.discard(i)
            for k in (a, b):
                at[key[k]].discard(i)
                todo.extend(at[key[k]])                   # ses voisines deviennent peut-être des bouts
    if tiny > 0:                                          # au centre d'un cercle, il reste un petit amas de morceaux
        seen: set = set()
        for i in sorted(alive):
            if i in seen:
                continue
            seen.add(i)
            comp, stack = [], [i]
            while stack:
                c = stack.pop()
                comp.append(c)
                for k in (2 * c, 2 * c + 1):
                    for o in at[key[k]]:
                        if o not in seen:
                            seen.add(o)
                            stack.append(o)
            if sum(math.dist(ends[2 * c], ends[2 * c + 1]) for c in comp) < tiny:
                alive.difference_update(comp)
    return [chains[i] for i in range(n) if i in alive]


def flank_trip(pts: list, dist, reg, rt: float, tan_h: float) -> list:
    """Intaille standard (TypeEdit 13 « Standard ») : l'outil suit un flanc à l'aller, l'autre au retour. `pts` : la ligne médiane
    [(x, y, z)] ; `dist` : la demi-largeur locale en chaque point. Là où la forme est plus large que l'outil à sa cote (profondeur
    bornée), l'axe de l'outil s'écarte de la ligne médiane de d − R(z) de chaque côté, R(z) = demi-pointe + |z| × tan(demi-angle) :
    l'outil touche le flanc. Ailleurs, aller et retour suivent la ligne médiane : la branche est parcourue deux fois. L'écart est
    réduit là où l'outil mordrait un flanc (branche courbe, jonction)."""
    import numpy as np
    import shapely
    if len(pts) < 2:
        return list(pts)
    xy = np.array([(p[0], p[1]) for p in pts], dtype=float)
    z = np.array([p[2] for p in pts], dtype=float)
    tg = np.empty_like(xy)
    tg[1:-1] = xy[2:] - xy[:-2]
    tg[0], tg[-1] = xy[1] - xy[0], xy[-1] - xy[-2]
    norm = np.hypot(tg[:, 0], tg[:, 1])
    norm[norm < 1e-12] = 1.0
    nrm = np.stack([-tg[:, 1] / norm, tg[:, 0] / norm], axis=1)
    reach = rt + np.abs(z) * tan_h
    want = np.maximum(0.0, np.asarray(dist, dtype=float) - reach)
    bound = reg.boundary
    sides = []
    for s in (1.0, -1.0):
        off = want.copy()
        for _ in range(8):
            q = xy + s * nrm * off[:, None]
            bad = ((shapely.distance(shapely.points(q), bound) < reach - 1e-3)
                   | ~shapely.contains_xy(reg, q[:, 0], q[:, 1])) & (off > 0)
            if not bad.any():
                break
            off[bad] *= 0.5
        else:
            off[bad] = 0.0
        q = xy + s * nrm * off[:, None]
        sides.append([(float(x), float(y), float(zz)) for (x, y), zz in zip(q, z)])
    return sides[0] + sides[1][::-1]


def _vcarve_axis(doc, setup, op, tool, tp, em, here, reg, tan_h, rt, depth_max, d_flat, depth_of=None) -> None:
    """Intaille optimisée (TypeEdit) : la pointe suit l'axe médian de chaque
    forme en touchant les deux flancs, sa profondeur suivant la demi-largeur
    locale (d − demi-pointe) / tan(demi-angle), au plus `depth_max` ; les
    zones plus larges que l'outil ne sont pas vidées (fond à évider à part).
    Intaille standard (vcarve_mode 'axe_ar') : chaque branche en aller-retour,
    un flanc à l'aller, l'autre au retour (`flank_trip`).
    `depth_of(d)` : une autre profondeur, à la demi-largeur locale d (fer à dorer)."""
    import shapely
    step = max(0.02, min(0.2, (op.resolution or 0.1)))
    chains = medial_axis(reg, step)
    if not chains:
        tp.warnings.append('gravure 2,5D en ligne médiane : formes trop fines')
        return
    te_rule = getattr(op, 'gravure_rule', 0) >= 881 and not depth_of
    if te_rule:
        chains = prune_hairs(chains, reg, float(getattr(op, 'corner_pull_angle', 135.0) or 135.0), tiny=4 * step)
        if not chains:
            tp.warnings.append('gravure 2,5D en ligne médiane : pas d\'axe à suivre dans ces formes (un cercle, par exemple) ; comme dans TypeEdit, rien n\'est gravé')
            return
    bound = reg.boundary
    trip = getattr(op, 'vcarve_mode', '') == 'axe_ar' and not depth_of
    out = []
    for c in chains:
        dense = list(shapely.segmentize(shapely.LineString(c), step).coords)
        d = shapely.distance(shapely.points(dense), bound)
        pts = [(x, y, -depth_of(float(di)) if depth_of else -min(depth_max, max(0.0, (float(di) - rt) / tan_h)))
               for (x, y), di in zip(dense, d)]
        if any(p[2] < 0 for p in pts):
            out.append(flank_trip(pts, d, reg, rt, tan_h) if trip else pts)
    vstep = max(0.0, float(getattr(op, 'vcarve_step', 0.0) or 0.0))
    deepest = max((-p[2] for c in out for p in c), default=0.0)
    for pts, _closed in S.order_chains([(c, False) for c in out], here):
        deep = -min(p[2] for p in pts)
        for level in axis_layers(pts, S.levels(deep, vstep) if vstep > 0 else [-deep]):
            for run, _c in S.order_chains([(r, False) for r in level], em.pos[:2] if em.pos is not None else here):
                if te_rule and em.pos is not None and em.pos[2] < 0 and math.dist(em.pos[:2], run[0][:2]) < 1e-3:
                    em.feed(run[0][0], run[0][1], run[0][2])  # la suite part d'où l'on est : on reste au fond, comme TE13
                else:
                    em.travel(run[0][0], run[0][1])
                    em.plunge(run[0][2])
                for x, y, z in run[1:]:
                    em.feed(x, y, z)
    _check_depth(tp, tool, S.levels(deepest, vstep) if vstep > 0 else [-deepest])
    wide = (2 if trip else 1) * d_flat                    # aller-retour : un flanc puis l'autre, deux largeurs d'outil
    if not depth_of and not S.erode(reg, wide, S._quad_segs(wide, setup.tolerance)).is_empty:
        tp.warnings.append('gravure 2,5D en ligne médiane : des zones sont plus larges que l\'outil à cette '
                           'profondeur — leur fond reste à évider (balayage, ou gravure en passes)')


# --- fer à dorer gaufrant (galbe en passes 2D concentriques) -----------------------------------
def _emboss_curve(op, tool=None) -> tuple:
    """Le demi-profil relevé dans TE13 : une courbe de Bézier du second degré, du bord (0, 0) au fond (largeur, -profondeur). Son point
    de contrôle, le point rouge de la fenêtre de TE, est à la rencontre des deux tangentes. L'angle de départ se compte depuis la
    verticale : TE le ramène entre le demi-angle de l'outil (0,573° s'il n'en a pas) et la droite qui va du bord au fond, et le profil
    est alors cette droite. L'angle d'arrivée se compte depuis l'horizontale. Rend (largeur, profondeur, x et z du point de contrôle)."""
    W = max(1e-6, getattr(op, 'emboss_width', 2.0) or 2.0)
    P = abs(op.depth)
    start = float(getattr(op, 'emboss_start_angle', 0.0) or 0.0)
    if start >= 89.9:                                     # 90 : l'ancienne valeur par défaut, comptée autrement
        start = 0.0
    half = tool.angle / 2 if tool is not None and tool.kind == 'conique' else 0.0
    chord = math.degrees(math.atan2(W, P)) if P > 0 else 89.0
    start = min(max(start, half, 0.573), chord)
    slope_in = 1.0 / math.tan(math.radians(start))
    slope_out = math.tan(math.radians(min(max(0.0, float(getattr(op, 'emboss_end_angle', 0.0) or 0.0)), 89.0)))
    if slope_in <= P / W + 1e-9 or slope_out >= P / W - 1e-9:
        return W, P, W / 2, -P / 2
    xc = (P - slope_out * W) / (slope_in - slope_out)
    return W, P, xc, -slope_in * xc


def emboss_depth(op, d: float, tool=None) -> float:
    """Profondeur du fer à dorer à la distance d du bord des formes : 0 sur la largeur laissée au bord, puis le demi-profil
    jusqu'à la profondeur totale à la largeur maxi (`tool` : pour la limite de l'angle de départ)."""
    edge = max(0.0, getattr(op, 'emboss_edge', 0.0) or 0.0)
    x = d - edge
    if x <= 0:
        return 0.0
    W, P, xc, zc = _emboss_curve(op, tool)
    if x >= W:
        return P
    a, b = W - 2 * xc, 2 * xc
    t = x / b if abs(a) < 1e-12 else (-b + math.sqrt(max(0.0, b * b + 4 * a * x))) / (2 * a)
    return -(2 * t * (1 - t) * zc - t * t * P)


def _emboss_cut(em, ring: list, z: float, op_levels: list, can_link) -> None:
    """Une passe fermée à la cote z, depuis le point du contour le plus près de l'outil. On la rejoint en avance, sans remonter, si
    `can_link(de, vers, cote)` (comme TE, qui enchaîne ses passes), sinon par un dégagement. Si l'opération limite la prise de passe
    (`op_levels`) : d'abord les cotes au-dessus de z."""
    pos = em.pos
    pts = S.begin_at(ring, pos[:2]) if pos is not None else ring
    start = pts[0]
    if pos is not None and pos[2] < 0 and can_link(pos[:2], start[:2], pos[2]):
        em.feed(start[0], start[1], pos[2])
    else:
        em.travel(start[0], start[1])
    for lz in [v for v in op_levels if v > z + 1e-9] + [z]:
        x, y, here_z = em.pos
        if lz < here_z:
            em.plunge(lz)
        elif lz > here_z:
            em.feed(x, y, lz)
        for p in pts[1:]:
            em.feed(p[0], p[1], lz)


def _emboss_inside(reg, op, tool, em, here, edge, r, step, qs, region_right, op_levels) -> int:
    """Le galbe dans les formes (TE13) : passes concentriques depuis le bord, l'axe de l'outil à bord + k × la distance entre passes,
    la cote donnée par le profil en retirant le rayon de l'outil ; le fond est vidé jusqu'au centre. Quand une forme se sépare en
    plusieurs parties, chacune est finie avant la suivante. Un trajet de liaison reste là où le galbe descendra de toute façon au moins
    à la cote de l'outil : il ne marque rien. Rend le nombre de retraits usinés."""
    import shapely
    from shapely.geometry import LineString
    plan, a = [], edge + step
    while len(plan) < 4000:
        g = S.erode(reg, a, qs)
        if g.is_empty:
            break
        plan.append((-emboss_depth(op, a - r, tool), g, [p for p in getattr(g, 'geoms', [g]) if p.geom_type == 'Polygon' and not p.is_empty]))
        a += step
    if not plan:
        return 0
    for _z, g, _parts in plan:
        shapely.prepare(g)

    def can_link(p, q, z) -> bool:
        n = math.dist(p, q)
        if n < 1e-6:
            return True
        safe = next(g for lz, g, _parts in plan if lz <= z + 1e-9)
        k = min(1e-5, n * 1e-3) / n                       # les deux bouts sont sur des contours : on regarde entre les deux
        return safe.covers(LineString([(p[0] + (q[0] - p[0]) * k, p[1] + (q[1] - p[1]) * k),
                                       (q[0] + (p[0] - q[0]) * k, q[1] + (p[1] - q[1]) * k)]))

    kids = []                                             # kids[k][i] : les parties du retrait k + 1 dans la partie i du retrait k
    for k in range(len(plan) - 1):
        now, nxt = plan[k][2], plan[k + 1][2]
        out = [[] for _ in now]
        if nxt:
            pts = [p.representative_point() for p in nxt]
            child, parent = shapely.STRtree(now).query(pts, predicate='intersects')
            for c, f in zip(child.tolist(), parent.tolist()):
                out[f].append(c)
        kids.append(out)
    kids.append([[] for _ in plan[-1][2]])
    done = set()
    stack = [[(0, i) for i in range(len(plan[0][2]))]]
    while stack:
        todo = stack[-1]
        if not todo:
            stack.pop()
            continue
        pos = em.pos[:2] if em.pos is not None else here
        from shapely.geometry import Point
        here_pt = Point(pos)
        k, i = min(todo, key=lambda n: plan[n[0]][2][n[1]].exterior.distance(here_pt))
        todo.remove((k, i))
        z = plan[k][0]
        if z < -1e-9:
            rings = [(pts, True) for pts in S.rings_of(plan[k][2][i], region_right)]
            for pts, _closed in S.order_chains(rings, em.pos[:2] if em.pos is not None else here):
                _emboss_cut(em, pts, z, op_levels, can_link)
            done.add(k)
        if kids[k][i]:
            stack.append([(k + 1, c) for c in kids[k][i]])
    return len(done)


def _emboss_around(reg, op, tool, em, here, edge, r, step, qs, region_right, op_levels) -> int:
    """Le galbe autour des formes, qui restent en relief : même profil, mêmes passes depuis le bord, jusqu'à la largeur maxi."""
    W = max(1e-6, getattr(op, 'emboss_width', 2.0) or 2.0)
    axes, a = [], edge + step
    while a - edge - r < W - 1e-9 and len(axes) < 4000:
        axes.append(a)
        a += step
    axes.append(edge + r + W)

    def can_link(p, q, _z) -> bool:                       # vers la passe voisine : le galbe y est plus profond
        return math.dist(p, q) <= 3 * step

    n_rings = 0
    for a in axes:
        z = -emboss_depth(op, a - r, tool)
        if z >= -1e-9:
            continue
        rings = [(pts, True) for pts in S.rings_of(S.buffer_checked(reg, a, qs), not region_right)]
        for pts, _closed in S.order_chains(rings, em.pos[:2] if em.pos is not None else here):
            _emboss_cut(em, pts, z, op_levels, can_link)
        n_rings += 1
    return n_rings


def _emboss(doc, setup, op, tool, tp, em, here) -> None:
    """Fer à dorer gaufrant, relevé dans TE13. `emboss_side` 'dedans' (TE) : le galbe descend vers l'intérieur des formes, le fond est
    vidé jusqu'au centre ; 'autour' : les formes restent en relief. `emboss_passes` : passes concentriques, passe sur la ligne centrale
    et les angles à la cote du profil (outil conique), ou les deux."""
    geoms = [g for it in S.source_items(doc, op) if (g := S.item_geometry(it))]
    tol = setup.tolerance
    reg = S.region(geoms, tol)
    if reg.is_empty:
        tp.warnings.append('fer à dorer : aucun contour fermé')
        return
    r = tool.tip / 2 if tool.kind == 'conique' else S.cut_radius(op, tool)
    W = max(1e-6, getattr(op, 'emboss_width', 2.0) or 2.0)
    edge = max(0.0, getattr(op, 'emboss_edge', 0.0) or 0.0)
    step = max(0.01, op.resolution or 0.1)
    qs = S._quad_segs(max(r, tol, edge + W + r), tol)     # les arcs des retraits suivent le profil
    which = getattr(op, 'emboss_passes', 'standard')
    n_rings = 0
    if which != 'intaille':
        passes = _emboss_inside if getattr(op, 'emboss_side', 'dedans') == 'dedans' else _emboss_around
        n_rings = passes(reg, op, tool, em, here, edge, r, step, qs, op.climb, S.op_levels(op, tool))
    if which != 'standard':
        if tool.kind == 'conique' and 0 < tool.angle < 180:
            tan_h = math.tan(math.radians(tool.angle) / 2)
            depth_max = abs(op.depth)
            _vcarve_axis(doc, setup, op, tool, tp, em, here, reg, tan_h, tool.tip / 2, depth_max,
                         tool.tip / 2 + depth_max * tan_h, depth_of=lambda d: emboss_depth(op, d - tool.tip / 2, tool))
        else:
            tp.warnings.append('fer à dorer : la passe sur la ligne centrale demande un outil conique')
    if which != 'intaille':
        tp.warnings.append(f'fer à dorer : {n_rings} passes, de {edge:g} à {edge + W:g} mm du bord')
