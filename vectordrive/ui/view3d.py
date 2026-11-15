"""Plan de travail en mode 3D : le modèle 3D du fichier ouvert (STEP,
STL, 3D XML : toute la pièce ou tout l'assemblage, faces, arêtes, couleurs),
ou la pièce telle que l'usinage la laissera (relief du dessin ou simulation
des parcours FAO), en OpenGL — tourner
(glisser), déplacer (clic droit ou molette enfoncée), zoomer (molette),
vues de dessus, de face, de côté, en perspective ; relief exagérable,
parcours d'outil affichés.

Rendu par QOpenGLWidget (pas de dépendance hors de Qt). Sans OpenGL (bureau
à distance…), une vue de dessus ombrée le remplace.
"""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QColor, QMatrix4x4, QPainter, QVector3D
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QHBoxLayout, QLabel, QPushButton,
                               QToolButton, QVBoxLayout, QWidget)

from ..i18n import tr

GL_TRIANGLES, GL_TRIANGLE_STRIP, GL_LINE_STRIP, GL_LINES = 0x0004, 0x0005, 0x0003, 0x0001
GL_FLOAT, GL_DEPTH_TEST, GL_COLOR_BUFFER_BIT, GL_DEPTH_BUFFER_BIT = 0x1406, 0x0B71, 0x4000, 0x0100
GL_POLYGON_OFFSET_FILL = 0x8037

#: couleurs de la matière (comme une plaque bicouche : dessus, cœur, fond)
SURFACE = (0.80, 0.64, 0.47)
CORE = (0.60, 0.82, 0.64)
DEEP = (0.42, 0.52, 0.80)
SIDE = (0.66, 0.52, 0.38)
#: côté le plus long de la grille affichée (cellules)
MAX_SIDE = 420
#: finesse de la 3D : clé → (libellé, points de la grille calculée, côté le plus long de la surface affichée)
FINESSE = {'normale': ('Normale', 1_000_000, MAX_SIDE), 'fine': ('Fine', 4_000_000, 900),
           'tres_fine': ('Très fine', 16_000_000, 1800)}
FINESSE_KEY = '3d/finesse'
#: vues prédéfinies : (lacet, tangage) en degrés
VIEWS = {'dessus': (0.0, 89.9), 'face': (0.0, 12.0), 'cote': (90.0, 12.0), 'iso': (-35.0, 40.0),
         # vue 3D « graveur » de TypeEdit : la plaque vue de devant, d'en haut, comme à la machine
         'graveur': (0.0, 55.0),
         # vues 2D de TypeEdit : plans YZ (de côté) et ZX (de face), sans inclinaison
         'yz': (90.0, 0.0), 'zx': (0.0, 0.0)}

VS = """
attribute highp vec3 pos;
attribute highp vec3 nrm;
attribute highp vec3 col;
uniform highp mat4 mvp;
uniform highp vec3 light;
uniform highp float lit;
uniform highp float twosided;
varying highp vec3 vcol;
varying highp float vz;
varying highp float vi;
void main() {
    vi = nrm.y;
    vcol = col;
    if (lit > 0.0) {   // traits (normale nulle) : couleur telle quelle, normalize(0) donnerait NaN (noir)
        float c = dot(normalize(nrm), normalize(light));
        float d = mix(max(c, 0.0), abs(c), twosided);
        vcol = mix(col, col * (0.38 + 0.62 * d), lit);
    }
    vz = pos.z;
    gl_Position = mvp * vec4(pos, 1.0);
}
"""
FS = """
varying highp vec3 vcol;
varying highp float vz;
varying highp float vi;
uniform highp float alpha;
uniform highp float clipz;
uniform highp float playhead;
uniform highp float useidx;
void main() {
    if (vz > clipz) discard;
    if (useidx > 0.5 && vi > playhead) {
        gl_FragColor = vec4(mix(vcol, vec3(0.62, 0.64, 0.68), 0.75), alpha);
        return;
    }
    gl_FragColor = vec4(vcol, alpha);
}
"""
#: modes d'affichage (modèle 3D et relief)
DISPLAY = {'aretes': 'Ombré et arêtes', 'ombre': 'Ombré', 'filaire': 'Filaire (arêtes, parcours)'}
#: clic sur le modèle 3D : rien (tourner seulement), choisir des faces, choisir des contours fermés
SELECT_MODES = {'off': 'Clic : points et cotes', 'faces': 'Clic : choisir des faces',
                'contours': 'Clic : choisir des contours fermés'}
#: trou débouchant : le perçage descend de ceci sous la pièce (mm)
THROUGH_EXTRA = 0.5
#: faces choisies (orange), contours choisis (magenta)
PICKED_FACE = (1.0, 0.55, 0.10)
PICKED_LOOP = (0.93, 0.10, 0.62)
#: couleurs des corps (« Couleur par corps »)
BODY_COLORS = ((0.55, 0.70, 0.90), (0.95, 0.70, 0.45), (0.60, 0.85, 0.60), (0.85, 0.60, 0.85),
               (0.90, 0.85, 0.50), (0.55, 0.85, 0.85), (0.90, 0.55, 0.55), (0.70, 0.70, 0.70))
GL_BLEND, GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA = 0x0BE2, 0x0302, 0x0303


# --- géométrie (numpy, sans OpenGL : essais) -------------------------------------------------
def pool_min(H, k: int):
    """Carte réduite d'un facteur k en gardant le point le plus bas de chaque
    bloc (les traits fins restent visibles)."""
    import numpy as np
    if k <= 1:
        return H
    ny, nx = H.shape
    py, px = (-ny) % k, (-nx) % k
    P = np.pad(H, ((0, py), (0, px)), mode='edge')
    return P.reshape(P.shape[0] // k, k, P.shape[1] // k, k).min(axis=(1, 3))


def depth_colors(H, deepest: float):
    """Couleur selon la profondeur (mm) : surface intacte, gravure (cœur de
    la matière, jusqu'à 0,5 mm), puis de plus en plus bleu vers le fond des
    poches profondes."""
    import numpy as np
    d = np.clip(-H, 0.0, None)
    s, c, f = (np.array(v) for v in (SURFACE, CORE, DEEP))
    cut = (d > 0.01)[..., None]
    t = np.clip((d - 0.5) / max(1.5, deepest - 0.5), 0.0, 1.0)[..., None]
    return np.where(cut, c * (1 - t) + f * t, s)


def mesh(sim, *, exag: float = 1.0, max_side: int = MAX_SIDE):
    """Bandes de triangles de la carte : (lignes, 2·nx, 9) float32 —
    position, normale, couleur — et nombre de sommets par bande."""
    import numpy as np
    H, res = sim.H, sim.res
    k = max(1, int(math.ceil(max(H.shape) / max_side)))
    if k > 1:
        H, res = pool_min(H, k), res * k
    ny, nx = H.shape
    if ny < 2 or nx < 2:
        H = np.zeros((2, 2))
        ny = nx = 2
    X = sim.x0 + np.arange(nx) * res
    Y = sim.y0 + np.arange(ny) * res
    Z = H * exag
    gy, gx = np.gradient(Z, res)
    N = np.dstack([-gx, -gy, np.ones_like(Z)])
    N /= np.linalg.norm(N, axis=2, keepdims=True)
    C = depth_colors(H, -min(float(H.min()), 0.0))
    P = np.dstack([np.broadcast_to(X, (ny, nx)), np.broadcast_to(Y[:, None], (ny, nx)), Z])
    V = np.concatenate([P, N, C], axis=2).astype(np.float32)
    S = np.stack([V[:-1], V[1:]], axis=2).reshape(ny - 1, 2 * nx, 9)
    return np.ascontiguousarray(S), 2 * nx


def box(x0, y0, x1, y1, z0, z1):
    """Côtés et dessous d'un pavé (triangles : n×9 float32)."""
    import numpy as np
    col = SIDE
    faces = [((x0, y0), (x1, y0), (0, -1)), ((x1, y0), (x1, y1), (1, 0)),
             ((x1, y1), (x0, y1), (0, 1)), ((x0, y1), (x0, y0), (-1, 0))]
    tris = []
    for (ax, ay), (bx, by), (nx_, ny_) in faces:
        a, b, c, d = (ax, ay, z1), (bx, by, z1), (bx, by, z0), (ax, ay, z0)
        for q in (a, b, c, a, c, d):
            tris.append(q + (nx_, ny_, 0.0) + col)
    for q in ((x0, y0, z0), (x1, y1, z0), (x1, y0, z0), (x0, y0, z0), (x0, y1, z0), (x1, y1, z0)):
        tris.append(q + (0.0, 0.0, -1.0) + col)
    return np.array(tris, dtype=np.float32)


def box_edges(tris, color=(0.45, 0.40, 0.33)):
    """Arêtes (traits n×9) du pavé dont `box` donne les faces : les 12
    arêtes de sa boîte."""
    import numpy as np
    if not len(tris):
        return np.zeros((0, 9), np.float32)
    x0, y0, z0 = tris[:, 0].min(), tris[:, 1].min(), tris[:, 2].min()
    x1, y1, z1 = tris[:, 0].max(), tris[:, 1].max(), tris[:, 2].max()
    c = [(x, y, z) for z in (z0, z1) for y in (y0, y1) for x in (x0, x1)]
    pairs = [(0, 1), (2, 3), (0, 2), (1, 3), (4, 5), (6, 7), (4, 6), (5, 7), (0, 4), (1, 5), (2, 6), (3, 7)]
    a = np.zeros((24, 9), np.float32)
    for i, (p, q) in enumerate(pairs):
        a[2 * i, :3], a[2 * i + 1, :3] = c[p], c[q]
    a[:, 6:9] = color
    return a


#: couleur des arêtes du modèle 3D (fond clair), et sur fond sombre
EDGE = (0.12, 0.14, 0.20)
EDGE_DARK_BG = (0.80, 0.84, 0.90)
#: réglages : couleur de la pièce et des arêtes choisies (« #rrggbb », vide : d'origine / selon le fond)
PART_COLOR_KEY = 'vue3d/couleur_piece'
EDGE_COLOR_KEY = 'vue3d/couleur_aretes'


def edge_for(bg, light=EDGE, dark=EDGE_DARK_BG) -> tuple:
    """Couleur de trait lisible sur le fond `bg` (QColor) : foncée sur fond
    clair, claire sur fond sombre."""
    return light if bg.lightness() >= 128 else dark


def rgb_of(text) -> tuple | None:
    """« #rrggbb » (réglages) → (r, g, b) entre 0 et 1 ; None : vide ou illisible."""
    c = QColor(str(text or ''))
    return (c.redF(), c.greenF(), c.blueF()) if text and c.isValid() else None


def hex_of(rgb) -> str:
    """(r, g, b) entre 0 et 1 → « #rrggbb » ; '' : aucune."""
    if rgb is None:
        return ''
    return QColor.fromRgbF(*[min(1.0, max(0.0, float(v))) for v in rgb]).name()
#: couleur des arêtes du brut (core.stock3d)
STOCK = (0.85, 0.50, 0.10)


#: couleurs du matériel de serrage (core.workspace) : table, étau et mandrin, le reste
FIXTURE = {'table': (0.36, 0.38, 0.42), 'etau': (0.52, 0.60, 0.70), 'mandrin': (0.52, 0.60, 0.70)}
FIXTURE_OTHER = (0.62, 0.62, 0.56)
FIXTURE_EDGE = (0.20, 0.22, 0.26)
FIXTURE_EDGE_DARK_BG = (0.62, 0.66, 0.72)


def fixture_arrays(ws, dz: float = 0.0):
    """Matériel de l'espace de travail `ws` (éléments montrés) → (triangles
    n·3×9, arêtes m·2×9) float32, décalés de `dz` en Z ; None, None : rien."""
    import numpy as np
    from ..core import workspace as WS
    tris, segs = [], []
    for e in ws.elements:
        if not e.visible:
            continue
        t = WS.triangles(e).astype(np.float32)
        if len(t):
            n = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
            ln = np.linalg.norm(n, axis=1)
            n = n / np.where(ln > 0, ln, 1.0)[:, None]
            rows = np.zeros((len(t), 3, 9), np.float32)
            rows[:, :, :3] = t
            rows[:, :, 2] += dz
            rows[:, :, 3:6] = n[:, None, :]
            rows[:, :, 6:9] = FIXTURE.get(e.kind, FIXTURE_OTHER)
            tris.append(rows.reshape(-1, 9))
        s = WS.edges(e).astype(np.float32).reshape(-1, 3)
        if len(s):
            rows = np.zeros((len(s), 9), np.float32)
            rows[:, :3] = s
            rows[:, 2] += dz
            rows[:, 6:9] = FIXTURE_EDGE
            segs.append(rows)
    if not tris and not segs:
        return None, None
    tri = np.ascontiguousarray(np.concatenate(tris)) if tris else np.zeros((0, 9), np.float32)
    edge = np.ascontiguousarray(np.concatenate(segs)) if segs else np.zeros((0, 9), np.float32)
    return tri, edge


def stock_edges(sb, dz: float = 0.0, color=STOCK):
    """Arêtes (traits n×9) du brut `sb` (core.stock3d.StockBox), décalé de
    `dz` en Z (haut de la pièce à Z = 0 pour la FAO, en haut du modèle) :
    pavé, ou cylindre (deux cercles et quatre génératrices)."""
    import numpy as np
    z0, z1 = sb.bottom + dz, sb.top + dz
    if sb.round:
        cx, cy = sb.center
        r = (sb.x1 - sb.x0) / 2
        ring = [(cx + r * math.cos(2 * math.pi * k / 64), cy + r * math.sin(2 * math.pi * k / 64)) for k in range(65)]
        segs = [((a[0], a[1], z), (b[0], b[1], z)) for z in (z0, z1) for a, b in zip(ring, ring[1:])]
        segs += [((ring[k][0], ring[k][1], z0), (ring[k][0], ring[k][1], z1)) for k in (0, 16, 32, 48)]
    else:
        c = [(sb.x0, sb.y0), (sb.x1, sb.y0), (sb.x1, sb.y1), (sb.x0, sb.y1)]
        segs = [((a[0], a[1], z), (b[0], b[1], z)) for z in (z0, z1) for a, b in zip(c, c[1:] + c[:1])]
        segs += [((x, y, z0), (x, y, z1)) for x, y in c]
    a = np.zeros((2 * len(segs), 9), np.float32)
    for i, (p, q) in enumerate(segs):
        a[2 * i, :3], a[2 * i + 1, :3] = p, q
    a[:, 6:9] = color
    return a


def model_arrays(model, picked=None, face_color=None, edge_color=EDGE):
    """Modèle 3D → (triangles n·3×9, arêtes m·2×9) float32 : position,
    normale de la face, couleur — tout d'un bloc (un seul tracé chacun).
    `picked` : indices des triangles des faces choisies (en orange) ;
    `face_color` : une couleur pour toute la pièce (None : celles du modèle) ;
    `edge_color` : celle des arêtes."""
    import numpy as np
    t = np.asarray(model.triangles, dtype=np.float32).reshape(-1, 3, 3)
    n = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
    ln = np.linalg.norm(n, axis=1)
    n = n / np.where(ln > 0, ln, 1.0)[:, None]
    N = np.repeat(n[:, None, :], 3, axis=1)
    cols = np.asarray(model.colors, dtype=np.float32).reshape(-1, 3)
    if face_color is not None:
        cols = np.tile(np.asarray(face_color, np.float32), (len(t), 1))
    if picked is not None and len(picked):
        cols = cols.copy()
        cols[np.asarray(picked, dtype=np.int64)] = PICKED_FACE
    C = np.repeat(cols.reshape(-1, 1, 3), 3, axis=1)
    tri = np.concatenate([t, N, C], axis=2).reshape(-1, 9).astype(np.float32)
    seg = np.asarray(model.segments, dtype=np.float32).reshape(-1, 3)
    edge = np.concatenate([seg, np.zeros_like(seg), np.tile(np.array(edge_color, np.float32), (len(seg), 1))],
                          axis=1)
    return np.ascontiguousarray(tri), np.ascontiguousarray(edge.astype(np.float32))


def loop_lines(loops, color=PICKED_LOOP):
    """Contours (polylignes (k, 3)) → (sommets ·×9 float32, [(premier, nombre)])
    pour un tracé GL_LINE_STRIP par contour."""
    import numpy as np
    parts, ranges, k = [], [], 0
    for L in loops:
        L = np.asarray(L, dtype=np.float32).reshape(-1, 3)
        if len(L) < 2:
            continue
        rows = np.zeros((len(L), 9), np.float32)
        rows[:, :3] = L
        rows[:, 6:] = color
        parts.append(rows)
        ranges.append((k, len(L)))
        k += len(L)
    arr = np.concatenate(parts) if parts else np.zeros((0, 9), np.float32)
    return np.ascontiguousarray(arr), ranges


def path_lines(toolpaths, *, exag: float = 1.0, rapids: bool = False):
    """Parcours : [(sommets n×9, couleur)] à tracer en lignes brisées."""
    import numpy as np
    from ..cam.model import arc_points
    out = []
    feed, rapid = (0.06, 0.38, 0.82), (0.88, 0.38, 0.0)
    g = 0                                               # numéro global du mouvement (tête de lecture)
    for tp in toolpaths:
        run, kind, prev = [], None, None
        for m in tp.moves:
            here = (m.x, m.y, m.z)
            k = 'rapid' if m.kind == 'rapid' else 'feed'
            if prev is not None:
                if k != kind and run:
                    out.append((run, kind))
                    run = [prev + (g - 1,)]
                pts = arc_points(prev, m, 0.05) if getattr(m, 'is_arc', False) else [here]
                run.extend(p + (g,) for p in pts)
            else:
                run = [here + (g,)]
            kind, prev = k, here
            g += 1
        if len(run) > 1:
            out.append((run, kind))
    lines = []
    for pts, kind in out:
        if kind == 'rapid' and not rapids:
            continue
        col = rapid if kind == 'rapid' else feed
        a = np.array([(x, y, z * exag if z < 0 else z, 0.0, float(i), 1.0) + col for x, y, z, i in pts],
                     dtype=np.float32)
        lines.append(a)
    return lines


#: couleurs des parcours (une par parcours, dans l'ordre) : avances ; les rapides restent orange
PATH_COLORS = [(0.06, 0.38, 0.82), (0.17, 0.58, 0.28), (0.70, 0.16, 0.55), (0.10, 0.60, 0.65),
               (0.55, 0.36, 0.10), (0.38, 0.30, 0.78), (0.78, 0.22, 0.20), (0.35, 0.45, 0.10)]
RAPID_COLOR = (0.88, 0.38, 0.0)
#: couleur par profondeur : surface, fond
DEPTH_TOP, DEPTH_BOTTOM = (0.55, 0.85, 0.35), (0.55, 0.05, 0.45)


def path_batch(toolpaths, *, exag: float = 1.0, rapids: bool = False, dz: float = 0.0, colors=True):
    """Toutes les trajectoires en un seul tableau (n×9) et ses morceaux
    [(début, nombre)] à tracer en lignes brisées : un seul tampon OpenGL
    même pour un programme de 150 000 mouvements. Avances : une couleur par
    parcours (`colors` vrai ou 'parcours'), dégradé de la surface au fond
    ('profondeur'), sinon bleu ; rapides en orange."""
    import numpy as np
    from ..cam.model import arc_points
    mode = 'parcours' if colors is True else ('unie' if not colors else str(colors))
    deep = min((m.z for tp in toolpaths for m in tp.moves if m.kind != 'rapid'), default=0.0)
    deep = deep if deep < -1e-9 else -1.0
    chunks, ranges = [], []
    first = 0
    g = 0
    for ti, tp in enumerate(toolpaths):
        feed = PATH_COLORS[ti % len(PATH_COLORS)] if mode == 'parcours' else PATH_COLORS[0]
        run, kind, prev = [], None, None

        def flush():
            nonlocal first
            if len(run) > 1 and (kind != 'rapid' or rapids):
                col = RAPID_COLOR if kind == 'rapid' else feed
                a = np.empty((len(run), 9), dtype=np.float32)
                p = np.asarray(run, dtype=np.float64)
                a[:, 0], a[:, 1] = p[:, 0], p[:, 1]
                a[:, 2] = np.where(p[:, 2] < 0, p[:, 2] * exag, p[:, 2]) + dz
                a[:, 3], a[:, 4], a[:, 5] = 0.0, p[:, 3], 1.0
                a[:, 6:9] = col
                if mode == 'profondeur' and kind != 'rapid':        # clair en surface, foncé au fond
                    t = np.clip(p[:, 2] / deep, 0.0, 1.0)[:, None]
                    a[:, 6:9] = (1 - t) * np.array(DEPTH_TOP) + t * np.array(DEPTH_BOTTOM)
                chunks.append(a)
                ranges.append((first, len(run)))
                first += len(run)
        for m in tp.moves:
            here = (m.x, m.y, m.z)
            k = 'rapid' if m.kind == 'rapid' else 'feed'
            if prev is not None:
                if k != kind and run:
                    flush()
                    run = [prev + (g - 1,)]
                pts = arc_points(prev, m, 0.05) if getattr(m, 'is_arc', False) else [here]
                run.extend(p + (g,) for p in pts)
            else:
                run = [here + (g,)]
            kind, prev = k, here
            g += 1
        flush()
    arr = np.concatenate(chunks) if chunks else np.zeros((0, 9), np.float32)
    return np.ascontiguousarray(arr), ranges


#: grille au sol (fond clair), et sur fond sombre
GRID = (0.55, 0.58, 0.64)
GRID_DARK_BG = (0.30, 0.32, 0.36)


def grid_lines(x0, y0, x1, y1, z: float, color=GRID):
    """Grille au sol (traits n×9) sous la pièce : pas de 1, 2 ou 5 × 10ⁿ mm,
    une quinzaine de traits sur le grand côté, débordant un peu."""
    import numpy as np
    span = max(x1 - x0, y1 - y0, 1e-3)
    raw = span / 15
    mag = 10 ** math.floor(math.log10(raw))
    step = next(k * mag for k in (1, 2, 5, 10) if k * mag >= raw)
    m = step
    gx0, gy0 = math.floor((x0 - m) / step) * step, math.floor((y0 - m) / step) * step
    gx1, gy1 = math.ceil((x1 + m) / step) * step, math.ceil((y1 + m) / step) * step
    segs = []
    x = gx0
    while x <= gx1 + 1e-9:
        segs += [(x, gy0, z), (x, gy1, z)]
        x += step
    y = gy0
    while y <= gy1 + 1e-9:
        segs += [(gx0, y, z), (gx1, y, z)]
        y += step
    a = np.zeros((len(segs), 9), dtype=np.float32)
    a[:, :3] = segs
    a[:, 6:9] = color
    return a, step


def tool_lines(pos, diameter: float, kind: str = 'fraise', angle: float = 0.0, length: float = 12.0,
               exag: float = 1.0):
    """Silhouette de l'outil (traits n×9) à sa position : cylindre (fraise),
    cône (outil conique), avec sa pointe en `pos`."""
    import numpy as np
    x, y, z = pos
    z = z * exag if z < 0 else z
    r = max(diameter / 2, 0.05)
    col = (0.98, 0.78, 0.18)
    n = 24
    ring = [(math.cos(2 * math.pi * i / n), math.sin(2 * math.pi * i / n)) for i in range(n)]
    cone = 0.0
    if kind == 'conique' and 0 < angle < 179:
        cone = r / math.tan(math.radians(angle / 2))    # hauteur du cône jusqu'au plein diamètre
    top = z + cone + length
    segs = []
    for (a, b), (c, d) in zip(ring, ring[1:] + ring[:1]):
        segs.append(((x + r * a, y + r * b, top), (x + r * c, y + r * d, top)))
        segs.append(((x + r * a, y + r * b, z + cone), (x + r * c, y + r * d, z + cone)))
    for a, b in ring[::6]:
        segs.append(((x + r * a, y + r * b, z + cone), (x + r * a, y + r * b, top)))
        if cone > 0:
            segs.append(((x, y, z), (x + r * a, y + r * b, z + cone)))
    arr = [p + (0.0, 0.0, 1.0) + col for s in segs for p in s]
    return np.array(arr, dtype=np.float32)


# --- vue OpenGL -----------------------------------------------------------------------------
def samples() -> int:
    """Anticrénelage de la vue 3D (F10 › Performances) : 0, 2, 4 ou 8 échantillons ;
    aucun en rendu logiciel (sans carte graphique, chaque échantillon coûte au processeur)."""
    try:
        from .. import portable
        st = portable.settings()
        if str(st.value('affichage/gpu', 'auto') or 'auto') == 'logiciel':
            return 0
        n = int(st.value('vue3d/anticrenelage', 4))
    except (TypeError, ValueError, ImportError):
        n = 4
    return n if n in (0, 2, 4, 8) else 4


#: direction de la lumière par rapport à la vue (commande Éclairage) : azimut et hauteur, en degrés
LIGHT_DEFAULT = {'azimuth': 30.0, 'elevation': math.degrees(math.atan(1.4))}
LIGHT = dict(LIGHT_DEFAULT)


def light_vector(yaw: float) -> tuple[float, float, float]:
    a = math.radians(yaw - LIGHT['azimuth'])
    return math.sin(a), -math.cos(a), math.tan(math.radians(min(85.0, max(0.0, LIGHT['elevation']))))


class View3D(QOpenGLWidget):
    """Vue OpenGL du relief."""

    #: faces ou contours choisis au clic (modèle 3D)
    selectionChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.relief = None
        self.model = None                   # modèle 3D du fichier (prioritaire sur le relief)
        self.exag = 1.0
        self.show_paths = True
        self.max_side = MAX_SIDE            # finesse de la surface affichée (FINESSE)
        self.show_plate = True              # plaque de travail (bloc, arêtes en filaire)
        self.show_rapids = False
        self.alpha = 1.0                    # opacité de la matière et des modèles (set_alpha)
        #: trajectoires tracées sur un modèle 3D, et leur décalage en Z (le haut de
        #: la pièce est Z = 0 pour la FAO, en haut du modèle dans le fichier)
        self.model_paths: list = []
        self.model_dz = 0.0
        self.stock_lines = None             # arêtes du brut autour du modèle (stock_edges), sous « Plaque »
        self.fixture = (None, None)         # matériel de serrage (fixture_arrays), sous « Plaque »
        self.yaw, self.pitch = VIEWS['iso']
        self.zoom = 1.0
        self.pan = QVector3D(0, 0, 0)
        self.ortho = False                  # projection orthogonale (sans perspective)
        self.display = 'filaire'            # DISPLAY (filaire par défaut)
        self.clip = None                    # coupe : rien au-dessus de ce Z (None : pas de coupe)
        self.triad = True                   # trièdre des axes dans le coin
        self.grid = True                    # grille au sol sous la pièce
        self.overlay = True                 # cotes de la pièce et légende des parcours
        self.path_colors = True             # 'parcours' (ou vrai), 'profondeur', 'unie' (ou faux)
        self.picks: list = []               # points choisis au clic (au plus deux) : (x, y, z) vrais
        self.select_mode = 'off'            # SELECT_MODES : ce que choisit un clic sur le modèle 3D
        self.sel_faces: set = set()         # faces choisies (numéros de `model.face_ids()`)
        self.sel_loops: list = []           # contours fermés choisis : polylignes (k, 3), repère du modèle
        self.edge_chains: list = []         # arêtes qu'un clic peut choisir (mode 'aretes') : polylignes (k, 3)
        self.sel_edges: set = set()         # leurs rangs
        self.hidden_bodies: set = set()     # corps masqués (numéros de `model.body_ids()`)
        self.body_moves: dict = {}          # corps déplacés (animation) : numéro → (R 3×3, t 3)
        self.body_colors = False            # une couleur par corps
        self.analysis = None                # ('depouille', direction, angle) ou ('acces', direction) : couleurs
        self._analysis_cache = None         # (clé, (triangles, couleurs, origines, parts)) de la dernière analyse
        self.part_color = None              # couleur choisie pour la pièce (r, g, b) ; None : celles du modèle
        self.edge_color = None              # couleur choisie des arêtes ; None : selon le fond (edge_for)
        self._dark_bg = None                # fond sombre au dernier chargement (thème changé : rechargé)
        self.setup = None                   # réglage FAO (avances) pour les temps de la légende
        self._stats: dict = {}              # parcours → (durée s, longueur en avance mm)
        self._pick_pts = None               # sommets des trajectoires montrées (pour le clic)
        self._press = None
        self.playhead = 1e12                # lecture : mouvements après ce numéro estompés
        self._tool_arr = None               # silhouette de l'outil (lecture)
        self.ok = None                      # OpenGL utilisable (après initializeGL)
        self._dirty = True
        self._last = None
        self._bufs = []
        self.setMinimumSize(200, 150)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        from PySide6.QtGui import QSurfaceFormat
        fmt = QSurfaceFormat(self.format())
        fmt.setSamples(samples())                       # anticrénelage : traits et arêtes lissés (repli si absent)
        self.setFormat(fmt)

    # --- données ----------------------------------------------------------------------
    def set_relief(self, relief) -> None:
        self.relief = relief
        self.model = None
        self.picks, self._pick_pts = [], None
        self._dirty = True
        self.update()

    def set_model(self, model) -> None:
        """Affiche un modèle 3D (`io.model3d.Model3D`) : faces ombrées des
        deux côtés, arêtes. Un autre modèle : la sélection est effacée."""
        if model is not self.model and (self.sel_faces or self.sel_loops):
            self.sel_faces, self.sel_loops = set(), []
            self.selectionChanged.emit()
        if model is not self.model:
            self.hidden_bodies, self.body_moves = set(), {}
        self.model = model
        self.relief = None
        self.zoom, self.pan = 1.0, QVector3D(0, 0, 0)
        self.picks, self._pick_pts = [], None
        self._dirty = True
        self.update()

    def bounds(self) -> tuple:
        """(x0, y0, z0, x1, y1, z1) de ce qui est affiché."""
        if self.model is not None:
            return self.model.bounds()
        r = self.relief
        x0, y0, x1, y1 = r.area if r is not None else (0, 0, 100, 50)
        return (x0, y0, 0.0, x1, y1, 0.0)

    def set_exag(self, k: float) -> None:
        self.exag = max(0.1, float(k))
        self._dirty = True
        self.update()

    def set_view(self, name: str) -> None:
        self.yaw, self.pitch = VIEWS.get(name, VIEWS['iso'])
        self.zoom, self.pan = 1.0, QVector3D(0, 0, 0)
        self.update()

    def set_playhead(self, k: float, tool=None) -> None:
        """Lecture : mouvements jusqu'au numéro k en couleur, la suite
        estompée ; `tool` : (position, diamètre, nature, angle) de l'outil."""
        self.playhead = float(k)
        if tool is None:
            self._tool_arr = None
        else:
            pos, dia, kind, ang = tool
            dz = self.model_dz if self.model is not None else 0.0
            self._tool_arr = tool_lines((pos[0], pos[1], pos[2] + dz), dia, kind, ang,
                                        exag=self.exag if self.model is None else 1.0)
        self.update()

    def fit(self) -> None:
        """Tout voir : zoom et décalage remis, orientation gardée."""
        self.zoom, self.pan = 1.0, QVector3D(0, 0, 0)
        self.update()

    def set_ortho(self, on: bool) -> None:
        self.ortho = bool(on)
        self.update()

    def set_display(self, mode: str) -> None:
        self.display = mode if mode in DISPLAY else 'aretes'
        self._dirty = True
        self.update()

    def z_range(self) -> tuple[float, float]:
        """(Z bas, Z haut) de ce qui est affiché (relief : jusqu'au fond de la
        plaque ; pièce : avec son brut s'il est montré — grille dessous, coupe
        sur toute sa hauteur)."""
        if self.model is not None:
            b = self.model.bounds()
            s = self.stock_lines if self.show_plate else None
            if s is not None and len(s):
                return min(b[2], float(s[:, 2].min())), max(b[5], float(s[:, 2].max()))
            return b[2], b[5]
        r = self.relief
        if r is None:
            return -1.0, 0.0
        th = r.plate[4] if r.plate else max(2.0, 3 * -min(r.sim.deepest, 0.0))
        return -max(th, -min(r.sim.deepest, 0.0) * self.exag), 0.0

    def set_clip(self, frac: float | None) -> None:
        """Coupe horizontale : `frac` de 0 (fond) à 1 (haut) ; None ou ≥ 1 : aucune."""
        if frac is None or frac >= 0.999:
            self.clip = None
        else:
            z0, z1 = self.z_range()
            self.clip = z0 + (z1 - z0) * max(0.0, float(frac))
        self.update()

    def _geometry(self):
        import numpy as np
        r = self.relief
        strips, per = mesh(r.sim, exag=self.exag, max_side=getattr(self, 'max_side', MAX_SIDE))
        x0, y0, x1, y1 = r.area
        if r.plate:
            px, py, pw, ph, th = r.plate
            bx = box(px, py, px + pw, py + ph, -th, 0.0)
        else:
            th = max(2.0, 3 * -min(r.sim.deepest, 0.0))
            bx = box(x0, y0, x1, y1, -th, 0.0)
        lines = path_batch(r.toolpaths, exag=self.exag, rapids=self.show_rapids, colors=self.path_colors) \
            if self.show_paths else (np.zeros((0, 9), np.float32), [])
        return strips, per, np.ascontiguousarray(bx), lines

    # --- OpenGL -------------------------------------------------------------------------
    def initializeGL(self) -> None:
        from PySide6.QtOpenGL import QOpenGLShader, QOpenGLShaderProgram
        try:
            self.prog = QOpenGLShaderProgram(self)
            self.ok = bool(self.prog.addShaderFromSourceCode(QOpenGLShader.ShaderTypeBit.Vertex, VS)
                           and self.prog.addShaderFromSourceCode(QOpenGLShader.ShaderTypeBit.Fragment, FS)
                           and self.prog.link())
        except Exception:
            self.ok = False
        if self.ok:
            f = self.context().functions()
            f.glEnable(GL_DEPTH_TEST)
            try:
                from .. import gpu
                gpu.note_renderer(f.glGetString(0x1F01))          # GL_RENDERER : la carte utilisée
            except Exception:                                     # fiche seulement : sans elle
                pass

    def _buffer(self, arr):
        from PySide6.QtOpenGL import QOpenGLBuffer
        b = QOpenGLBuffer(QOpenGLBuffer.Type.VertexBuffer)
        b.create()
        b.bind()
        data = arr.tobytes()
        b.allocate(data, len(data))
        b.release()
        return b

    def _upload(self) -> None:
        import numpy as np
        for b in self._bufs:
            b.destroy()
        self._bufs = []
        self._draws = []
        if self.model is not None:
            shown, keep = self.shown_model()
            picked = self.selected_triangles()
            if keep is not None and len(picked):                  # numéros dans le modèle montré
                picked = np.flatnonzero(np.isin(keep, picked))      # triangle recoupé : tous ses morceaux
            dark = self._background().lightness() < 128
            self._dark_bg = dark
            tri, edge = model_arrays(shown, picked, None if self.body_colors or self.analysis else self.part_color,
                                     self.edge_rgb())
            if len(tri) and self.display == 'filaire' and len(picked):   # filaire : les faces choisies seules
                tri = np.ascontiguousarray(tri.reshape(-1, 3, 9)[picked].reshape(-1, 9))
            if len(tri) and (self.display != 'filaire' or len(picked)):
                self._bufs.append(self._buffer(tri))
                self._draws.append((self._bufs[-1], GL_TRIANGLES, [(0, len(tri))], 1.0, 1.0))
            if len(edge) and self.display != 'ombre':
                self._bufs.append(self._buffer(edge))
                self._draws.append((self._bufs[-1], GL_LINES, [(0, len(edge))], 0.0, 0.0))
            if self.show_plate and self.stock_lines is not None and len(self.stock_lines):
                self._bufs.append(self._buffer(self.stock_lines))
                self._draws.append((self._bufs[-1], GL_LINES, [(0, len(self.stock_lines))], 0.0, 0.0))
            ftri, fedge = self.fixture if self.show_plate else (None, None)
            if ftri is not None and len(ftri) and self.display != 'filaire':
                self._bufs.append(self._buffer(ftri))
                self._draws.append((self._bufs[-1], GL_TRIANGLES, [(0, len(ftri))], 1.0, 1.0))
            if fedge is not None and len(fedge):
                if dark:                                   # fond sombre : arêtes du matériel éclaircies
                    fedge = fedge.copy()
                    fedge[:, 6:9] = FIXTURE_EDGE_DARK_BG
                self._bufs.append(self._buffer(fedge))
                self._draws.append((self._bufs[-1], GL_LINES, [(0, len(fedge))], 0.0, 0.0))
            if self.sel_loops:
                arr, ranges = loop_lines(self.sel_loops)
                if ranges:
                    self._bufs.append(self._buffer(arr))
                    self._draws.append((self._bufs[-1], GL_LINE_STRIP, ranges, 0.0, 0.0))
            self._pick_pts = self._model_points(None)
            if self.show_paths and self.model_paths:
                arr, ranges = path_batch(self.model_paths, rapids=self.show_rapids, dz=self.model_dz,
                                         colors=self.path_colors)
                self._pick_pts = self._model_points(arr)
                if ranges:
                    self._bufs.append(self._buffer(arr))
                    self._draws.append((self._bufs[-1], GL_LINE_STRIP, ranges, 0.0, 0.0))
            self._add_grid()
            return
        if self.relief is None:
            return
        strips, per, bx, lines = self._geometry()
        if self.display == 'filaire' and self.show_plate:   # filaire : les parcours, et les arêtes de la plaque
            edges = box_edges(bx)
            if len(edges):
                self._bufs.append(self._buffer(edges))
                self._draws.append((self._bufs[-1], GL_LINES, [(0, len(edges))], 0.0, 0.0))
        if self.display != 'filaire':                  # filaire : les parcours seuls
            self._bufs.append(self._buffer(strips))
            self._draws.append((self._bufs[-1], GL_TRIANGLE_STRIP,
                                [(j * per, per) for j in range(strips.shape[0])], 1.0, 0.0))
            if self.show_plate:
                self._bufs.append(self._buffer(bx))
                self._draws.append((self._bufs[-1], GL_TRIANGLES, [(0, len(bx))], 1.0, 0.0))
        arr, ranges = lines
        self._pick_pts = arr[:, :3] if len(arr) else None
        if ranges:
            self._bufs.append(self._buffer(arr))
            self._draws.append((self._bufs[-1], GL_LINE_STRIP, ranges, 0.0, 0.0))
        self._add_grid()

    def _add_grid(self) -> None:
        """Grille au sol, sous le bas de ce qui est affiché."""
        if not self.grid:
            return
        x0, y0, _z0, x1, y1, _z1 = self.bounds()
        z = self.z_range()[0] - 0.01
        dark = self._background().lightness() < 128      # fond sombre : grille discrète sous les arêtes claires
        g, self.grid_step = grid_lines(x0, y0, x1, y1, z, color=GRID_DARK_BG if dark else GRID)
        if len(g):
            self._bufs.append(self._buffer(g))
            self._draws.append((self._bufs[-1], GL_LINES, [(0, len(g))], 0.0, 0.0))

    def camera(self) -> QMatrix4x4:
        x0, y0, z0, x1, y1, z1 = self.bounds()
        size = max(x1 - x0, y1 - y0, z1 - z0, 1e-3 if self.model is not None else 1.0)
        c = QVector3D((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2) + self.pan
        dist = size * 1.5 / self.zoom
        yaw, pitch = math.radians(self.yaw), math.radians(self.pitch)
        eye = c + QVector3D(dist * math.cos(pitch) * math.sin(yaw), -dist * math.cos(pitch) * math.cos(yaw),
                            dist * math.sin(pitch))
        m = QMatrix4x4()
        aspect = self.width() / max(1, self.height())
        if self.ortho:                                 # même cadrage que la perspective à la distance de visée
            h = dist * math.tan(math.radians(17.5))
            m.ortho(-h * aspect, h * aspect, -h, h, -dist * 10 - size, dist * 10 + size)
        else:
            m.perspective(35.0, aspect, max(dist * 0.01, 0.01), dist * 10 + size)
        up = QVector3D(0, 1, 0) if abs(self.pitch) > 89 else QVector3D(0, 0, 1)
        m.lookAt(eye, c, up)
        return m

    def _background(self) -> QColor:
        from .theme import canvas_colors
        return QColor(canvas_colors()['bg'].split(';')[0])

    def edge_rgb(self) -> tuple:
        """Couleur des arêtes du modèle : celle choisie, sinon lisible sur le fond."""
        return tuple(self.edge_color) if self.edge_color else edge_for(self._background())

    def release_gpu(self) -> int:
        """Tampons de la carte graphique rendus (vue masquée) ; rechargés au
        prochain affichage. Rend le nombre de tampons libérés."""
        bufs = list(self._bufs)
        if not bufs or self.context() is None:
            return 0
        self.makeCurrent()
        try:
            for b in bufs:
                b.destroy()
        finally:
            self.doneCurrent()
        self._bufs = []
        self._draws = []
        self._dirty = True
        return len(bufs)

    def hideEvent(self, ev) -> None:                    # noqa: N802 (API Qt)
        # vue masquée (panneau fermé, onglet 2D) : la mémoire graphique revient aux autres programmes
        self.release_gpu()
        super().hideEvent(ev)

    def paintGL(self) -> None:
        if not self.ok:
            self._paint_fallback()
            return
        f = self.context().functions()
        bg = self._background()
        f.glClearColor(bg.redF(), bg.greenF(), bg.blueF(), 1.0)
        f.glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        f.glEnable(GL_DEPTH_TEST)                      # à chaque image : le trièdre (QPainter) remet l'état à zéro
        if self.relief is None and self.model is None:
            return
        if self.model is not None and self._dark_bg is not None and self._dark_bg != (bg.lightness() < 128):
            self._dirty = True                         # thème clair ↔ sombre : arêtes recolorées
        if self._dirty:
            self._upload()
            self._dirty = False
        self.prog.bind()
        self.prog.setUniformValue('mvp', self.camera())
        self.prog.setUniformValue1f('clipz', float(self.clip) if self.clip is not None else 1e9)
        self.prog.setUniformValue1f('playhead', float(self.playhead))
        self.prog.setUniformValue('light', QVector3D(*light_vector(self.yaw)))
        stride = 9 * 4
        locs = [(self.prog.attributeLocation(n), off) for n, off in (('pos', 0), ('nrm', 12), ('col', 24))]
        see_through = self.alpha < 0.999
        if see_through:                                # matière translucide : les parcours se voient au travers
            f.glEnable(GL_BLEND)
            f.glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        for buf, mode, ranges, lit, two in self._draws:
            surface = mode in (GL_TRIANGLES, GL_TRIANGLE_STRIP)
            self.prog.setUniformValue1f('lit', float(lit))
            self.prog.setUniformValue1f('twosided', float(two))
            self.prog.setUniformValue1f('alpha', float(self.alpha) if surface else 1.0)
            self.prog.setUniformValue1f('useidx', 1.0 if mode == GL_LINE_STRIP else 0.0)
            if see_through:
                f.glDepthMask(not surface)             # les faces translucides ne masquent pas ce qui est derrière
            buf.bind()
            for loc, off in locs:
                self.prog.enableAttributeArray(loc)
                self.prog.setAttributeBuffer(loc, GL_FLOAT, off, 3, stride)
            offset = mode in (GL_TRIANGLES, GL_TRIANGLE_STRIP) and self.model is not None
            if offset:                                 # faces un peu en retrait : arêtes nettes par-dessus
                f.glEnable(GL_POLYGON_OFFSET_FILL)
                f.glPolygonOffset(1.0, 1.0)
            for first, count in ranges:
                f.glDrawArrays(mode, first, count)
            if offset:
                f.glDisable(GL_POLYGON_OFFSET_FILL)
            buf.release()
        if see_through:
            f.glDepthMask(True)
            f.glDisable(GL_BLEND)
        if self._tool_arr is not None and len(self._tool_arr):       # l'outil, par-dessus
            buf = self._buffer(self._tool_arr)
            self.prog.setUniformValue1f('lit', 0.0)
            self.prog.setUniformValue1f('useidx', 0.0)
            self.prog.setUniformValue1f('alpha', 1.0)
            buf.bind()
            for loc, off in locs:
                self.prog.enableAttributeArray(loc)
                self.prog.setAttributeBuffer(loc, GL_FLOAT, off, 3, stride)
            f.glDrawArrays(GL_LINES, 0, len(self._tool_arr))
            buf.release()
            buf.destroy()
        self.prog.release()
        if self.triad or self.overlay:
            p = QPainter(self)
            if self.triad:
                self.paint_triad(p)
            if self.overlay:
                self.paint_overlay(p)
            p.end()

    def triad_axes(self) -> list:
        """[(nom, dx, dy)] : axes X, Y, Z vus de la caméra (vecteurs écran unitaires,
        y vers le bas), du plus loin au plus proche."""
        yaw, pitch = math.radians(self.yaw), math.radians(self.pitch)
        # repère caméra : droite, haut (même convention que camera())
        right = (math.cos(yaw), math.sin(yaw), 0.0)
        fwd = (-math.cos(pitch) * math.sin(yaw), math.cos(pitch) * math.cos(yaw), -math.sin(pitch))
        up = (right[1] * fwd[2] - right[2] * fwd[1], right[2] * fwd[0] - right[0] * fwd[2],
              right[0] * fwd[1] - right[1] * fwd[0])
        out = []
        for name, v in (('X', (1, 0, 0)), ('Y', (0, 1, 0)), ('Z', (0, 0, 1))):
            dx = sum(a * b for a, b in zip(v, right))
            dy = -sum(a * b for a, b in zip(v, up))
            depth = sum(a * b for a, b in zip(v, fwd))
            out.append((depth, name, dx, dy))
        return [(n, dx, dy) for _d, n, dx, dy in sorted(out, reverse=True)]

    def paint_triad(self, p: QPainter) -> None:
        """Trièdre des axes en bas à gauche (X rouge, Y vert, Z bleu)."""
        from PySide6.QtGui import QPen
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        o = QPointF(38.0, self.height() - 38.0)
        cols = {'X': QColor('#e03131'), 'Y': QColor('#2f9e44'), 'Z': QColor('#1971c2')}
        for name, dx, dy in self.triad_axes():
            e = QPointF(o.x() + dx * 26, o.y() + dy * 26)
            p.setPen(QPen(cols[name], 2.2))
            p.drawLine(o, e)
            p.drawText(QPointF(e.x() + dx * 7 - 4, e.y() + dy * 7 + 4), name)

    def overlay_lines(self) -> list:
        """Textes de la surimpression : cotes de la pièce, pas de la grille,
        projection, et la légende des parcours [(texte, couleur ou None)]."""
        x0, y0, z0, x1, y1, z1 = self.bounds()
        if self.relief is not None and self.model is None:
            z0, z1 = self.z_range()
        f = lambda v: f'{v:.2f}'.rstrip('0').rstrip('.').replace('.', ',')       # noqa: E731
        out = [(f'X {f(x1 - x0)} × Y {f(y1 - y0)} × Z {f(z1 - z0)} mm', None)]
        extra = [tr('orthogonale') if self.ortho else tr('perspective')]
        if self.grid and getattr(self, 'grid_step', 0):
            extra.append(tr('grille {0} mm').format(f(self.grid_step)))
        out.append(('  —  '.join(extra), None))
        tps = (self.model_paths if self.model is not None else
               (self.relief.toolpaths if self.relief is not None else [])) if self.show_paths else []
        if self.path_colors in (True, 'parcours') and len(tps) > 1:
            for i, tp in enumerate(tps[:12]):
                out.append((str(getattr(tp, 'name', '') or tr('Parcours {0}').format(i + 1)) + self._stat_text(tp),
                            PATH_COLORS[i % len(PATH_COLORS)]))
        if tps and self.path_colors == 'profondeur':          # échelle des couleurs de profondeur
            deep = min((m.z for tp in tps for m in tp.moves if m.kind != 'rapid'), default=0.0)
            out.append((tr('Surface : 0 mm'), DEPTH_TOP))
            out.append((tr('Fond : {0} mm').format(f(deep)), DEPTH_BOTTOM))
        if tps:
            tot = sum(self._stat(tp)[0] for tp in tps)
            feed = sum(self._stat(tp)[1] for tp in tps)
            from ..cam.timing import format_duration
            out.append((tr('Total : {0} estimées, {1} m en avance').format(
                format_duration(tot), f'{feed / 1000:.2f}'.replace('.', ',')), None))
            mach = next((s for tp in tps if (s := getattr(tp, 'machine_seconds', None))), None)
            if mach:                                          # durée calculée par la machine (fichier joint)
                out.append((tr('Durée prévue par la machine : {0}').format(format_duration(mach)), None))
        out += [(t, None) for t in self.pick_lines()]        # points mesurés, en dernier
        return out

    def _stat(self, tp) -> tuple:
        """(durée estimée s, longueur en avance mm) d'un parcours, en cache."""
        key = (id(tp), len(tp.moves))
        v = self._stats.get(key)
        if v is None:
            from ..cam import model as M, timing
            try:
                sec = timing.path_seconds(tp, self.setup or M.CamSetup())
            except Exception:                            # parcours incomplet : pas de temps
                sec = 0.0
            v = self._stats[key] = (sec, tp.lengths()[0])
            if len(self._stats) > 500:
                self._stats = {key: v}
        return v

    def _stat_text(self, tp) -> str:
        from ..cam.timing import format_duration
        sec, feed = self._stat(tp)
        return f'  — {format_duration(sec)}, {feed / 1000:.2f} m'.replace('.', ',')

    def paint_overlay(self, p: QPainter) -> None:
        from PySide6.QtGui import QFont
        dark = self._background().lightness() < 128
        ink = QColor('#e9ecef') if dark else QColor('#343a40')
        fnt = QFont(p.font())
        fnt.setPointSizeF(max(7.5, fnt.pointSizeF()))
        p.setFont(fnt)
        y = 18
        for text, col in self.overlay_lines():
            if col is not None:
                p.fillRect(8, y - 9, 14, 9, QColor.fromRgbF(*col))
                p.setPen(ink)
                p.drawText(28, y, text)
            else:
                p.setPen(ink)
                p.drawText(8, y, text)
            y += 16

    def save_image(self, path: str) -> bool:
        """Image de la vue (PNG, JPEG) à la taille de l'écran."""
        img = self.grabFramebuffer() if self.ok else self.grab().toImage()
        return bool(img.save(str(path)))

    def set_alpha(self, a: float) -> None:
        """Opacité de la matière et des modèles (0 = invisible, 1 = opaque) :
        les parcours et le dessin restent dessinés en plein."""
        self.alpha = max(0.0, min(1.0, float(a)))
        self.update()

    def _paint_fallback(self) -> None:
        p = QPainter(self)
        p.fillRect(self.rect(), self._background())
        if self.model is not None:
            self._paint_wireframe(p)
        elif self.relief is not None:
            from ..cam.simulate import render
            img = render(self.relief.sim, width=max(200, self.width()))
            img = img.scaled(self.width(), self.height() - 24, Qt.AspectRatioMode.KeepAspectRatio,
                             Qt.TransformationMode.SmoothTransformation)
            p.drawImage(QPointF((self.width() - img.width()) / 2, 24), img)
        p.setPen(QColor('#ffffff'))
        p.drawText(8, 16, tr('OpenGL indisponible : vue de dessus ombrée'))
        p.end()

    def _paint_wireframe(self, p: QPainter) -> None:
        """Sans OpenGL : arêtes du modèle projetées (même caméra)."""
        import numpy as np
        seg = np.asarray(self.model.segments, dtype=np.float64).reshape(-1, 3)
        if not len(seg):
            return
        m = np.array(self.camera().data(), dtype=np.float64).reshape(4, 4)   # colonne par colonne
        h = np.c_[seg, np.ones(len(seg))] @ m
        w = np.where(np.abs(h[:, 3]) > 1e-9, h[:, 3], 1e-9)
        x = (h[:, 0] / w + 1) * 0.5 * self.width()
        y = (1 - h[:, 1] / w) * 0.5 * self.height()
        from PySide6.QtCore import QLineF
        p.setPen(QColor('#d8dde6') if self._background().lightness() < 128 else QColor('#1e2433'))
        p.drawLines([QLineF(x[i], y[i], x[i + 1], y[i + 1]) for i in range(0, len(x) - 1, 2)])

    # --- souris -------------------------------------------------------------------------
    def mousePressEvent(self, ev) -> None:
        self._last = ev.position()
        self._press = ev.position()

    def mouseMoveEvent(self, ev) -> None:
        if self._last is None:
            return
        d = ev.position() - self._last
        self._last = ev.position()
        if ev.buttons() & Qt.MouseButton.LeftButton:
            self.yaw = (self.yaw - d.x() * 0.4) % 360
            self.pitch = max(-89.9, min(89.9, self.pitch + d.y() * 0.3))     # par-dessous aussi
        elif ev.buttons() & (Qt.MouseButton.RightButton | Qt.MouseButton.MiddleButton):
            x0, y0, z0, x1, y1, z1 = self.bounds()
            k = max(x1 - x0, y1 - y0, z1 - z0, 1e-3) / max(1, self.height()) / self.zoom * 1.2
            yaw = math.radians(self.yaw)
            right = QVector3D(math.cos(yaw), math.sin(yaw), 0)
            fwd = QVector3D(-math.sin(yaw), math.cos(yaw), 0)
            self.pan += right * (-d.x() * k) + fwd * (d.y() * k)
        self.update()

    def mouseReleaseEvent(self, ev) -> None:
        self._last = None
        p0, self._press = self._press, None
        if p0 is not None and ev.button() == Qt.MouseButton.LeftButton \
                and (ev.position() - p0).manhattanLength() < 4:
            if self.select_mode != 'off' and self.model is not None:
                mods = ev.modifiers()
                add = bool(mods & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier))
                self.select_at(ev.position(), add=add)
            else:
                self.pick_at(ev.position())

    # --- sélection de faces et de contours (modèle 3D) -----------------------------------
    def ray_at(self, pos):
        """Rayon de la caméra sous le point `pos` de l'écran : (origine,
        direction unitaire), repère du modèle ; None si la vue est vide."""
        import numpy as np
        if self.width() <= 0 or self.height() <= 0:
            return None
        m = np.array(self.camera().data(), dtype=np.float64).reshape(4, 4)
        try:
            inv = np.linalg.inv(m)
        except np.linalg.LinAlgError:
            return None
        x = 2.0 * pos.x() / self.width() - 1.0
        y = 1.0 - 2.0 * pos.y() / self.height()
        a = np.array([x, y, -1.0, 1.0]) @ inv
        b = np.array([x, y, 1.0, 1.0]) @ inv
        if abs(a[3]) < 1e-12 or abs(b[3]) < 1e-12:
            return None
        a, b = a[:3] / a[3], b[:3] / b[3]
        d = b - a
        n = np.linalg.norm(d)
        return (a, d / n) if n > 0 else None

    def shown_model(self):
        """(modèle montré, triangle d'origine de chacun ou None) : corps
        masqués retirés, corps déplacés (animation), couleur par corps,
        couleurs d'une analyse de surface (triangles recoupés pour
        l'accessibilité) — le modèle lui-même s'il n'y a rien de tout cela."""
        import numpy as np
        m = self.model
        if m is None or not (self.hidden_bodies or self.body_moves or self.body_colors or self.analysis):
            return m, None
        from ..io.model3d import Model3D
        bodies = m.body_ids()
        tris = np.asarray(m.triangles, dtype=np.float32)
        cols = np.asarray(m.colors, dtype=np.float32)
        segs = np.asarray(m.segments, dtype=np.float32)
        sb = m.segment_bodies() if (self.hidden_bodies or self.body_moves) and len(segs) else None
        if self.body_moves:
            tris = tris.copy()
            segs = segs.copy()
            for b, (R, t) in self.body_moves.items():
                sel = bodies == b
                R, t = np.asarray(R, dtype=np.float32), np.asarray(t, dtype=np.float32)
                tris[sel] = tris[sel] @ R.T + t
                if sb is not None:
                    ss = sb == b
                    segs[ss] = segs[ss] @ R.T + t
        if self.body_colors:
            pal = np.asarray(BODY_COLORS, dtype=np.float32)
            cols = pal[bodies % len(pal)]
        keep = None
        if self.hidden_bodies:
            keep = np.flatnonzero(~np.isin(bodies, list(self.hidden_bodies)))
            tris, cols = tris[keep], cols[keep]
            if sb is not None:
                segs = segs[~np.isin(sb, list(self.hidden_bodies))]
        if self.analysis:
            tris, cols, keep, _shares = self._analysed(tris, keep)
        return Model3D(tris, cols, segs, m.name), keep

    def _analysed(self, tris, keep):
        """Analyse de surface (core.analysis3d, d'après SolidCraft) des
        triangles montrés : (triangles, couleurs, triangle d'origine de
        chacun, parts de la surface par couleur) ; gardée tant que le modèle,
        l'analyse, les corps masqués ou déplacés ne changent pas."""
        import numpy as np
        from ..core import analysis3d as AN
        key = (id(self.model), self.analysis, tuple(sorted(self.hidden_bodies)),
               tuple((b, np.asarray(R).tobytes(), np.asarray(t).tobytes()) for b, (R, t) in sorted(self.body_moves.items())))
        if self._analysis_cache is not None and self._analysis_cache[0] == key:
            return self._analysis_cache[1]
        if self.analysis[0] == 'depouille':
            cls, pal = AN.draft_classes(tris, self.analysis[1], self.analysis[2]), AN.DRAFT_COLORS
        else:                                           # accessibilité : grands triangles recoupés, jugés morceau par morceau
            span = float(np.ptp(np.asarray(tris).reshape(-1, 3), axis=0).max()) if len(tris) else 1.0
            tris, parent = AN.subdivide(tris, max(span / 50, 1e-3), max(150_000, len(tris)))
            keep = parent if keep is None else np.asarray(keep)[parent]
            cls, pal = AN.access_classes(tris, self.analysis[1]), AN.ACCESS_COLORS
        out = (np.asarray(tris, dtype=np.float32), np.asarray(pal, dtype=np.float32)[cls], keep,
               AN.area_shares(tris, cls, len(pal)))
        self._analysis_cache = (key, out)
        return out

    def set_body_hidden(self, b: int, hidden: bool) -> None:
        (self.hidden_bodies.add if hidden else self.hidden_bodies.discard)(int(b))
        self._dirty = True
        self.update()

    def set_body_moves(self, moves: dict) -> None:
        """Corps déplacés : {numéro: (R 3×3, t 3)} ; {} : tous à leur place."""
        self.body_moves = dict(moves or {})
        self._dirty = True
        self.update()

    def face_at(self, pos):
        """(face, triangle, point touché) sous le clic, ou None (plan de
        coupe : ce qui est au-dessus ne compte pas ; corps masqués ou
        déplacés : tels qu'à l'écran)."""
        import numpy as np
        from ..core import faces3d
        if self.model is None or not len(self.model.triangles):
            return None
        ray = self.ray_at(pos)
        if ray is None:
            return None
        shown, keep = self.shown_model()
        tris = np.asarray(shown.triangles)
        idx = keep
        if self.clip is not None:
            low = np.flatnonzero(tris[:, :, 2].min(axis=1) <= self.clip)
            tris = tris[low]
            idx = low if idx is None else idx[low]
        i, t = faces3d.ray_hit(tris, *ray)
        if i < 0:
            return None
        if idx is not None:
            i = int(idx[i])
        hit = ray[0] + t * ray[1]
        return int(self.model.face_ids()[i]), i, hit

    def set_edge_chains(self, chains) -> None:
        """Les arêtes qu'un clic peut choisir (mode 'aretes')."""
        import numpy as np
        self.edge_chains = [np.asarray(c, dtype=np.float64) for c in chains]
        self.set_edge_selection(())

    def set_edge_selection(self, ranks) -> None:
        self.sel_edges = {int(k) for k in ranks if 0 <= int(k) < len(self.edge_chains)}
        self.set_selection(loops=[self.edge_chains[k] for k in sorted(self.sel_edges)])

    def edge_at(self, pos, radius: float = 12.0):
        """Le rang de l'arête sous le clic, à moins de `radius` pixels ; une arête vue passe avant
        une arête cachée. None : aucune."""
        import numpy as np
        from PySide6.QtCore import QPointF
        from ..core import faces3d
        if not self.edge_chains or self.width() <= 0 or self.height() <= 0:
            return None
        m = np.array(self.camera().data(), dtype=np.float64).reshape(4, 4)
        here = np.array([pos.x(), pos.y()], dtype=np.float64)
        found = []
        for k, chain in enumerate(self.edge_chains):
            h = np.c_[chain, np.ones(len(chain))] @ m
            front = h[:, 3] > 1e-9
            w = np.where(front, h[:, 3], 1.0)
            xy = np.c_[(h[:, 0] / w + 1.0) * 0.5 * self.width(), (1.0 - h[:, 1] / w) * 0.5 * self.height()]
            a, b = xy[:-1], xy[1:]
            ab = b - a
            t = np.clip(((here - a) * ab).sum(axis=1) / np.maximum((ab * ab).sum(axis=1), 1e-9), 0.0, 1.0)
            d = np.linalg.norm(here - (a + ab * t[:, None]), axis=1)
            d[~(front[:-1] & front[1:])] = np.inf
            j = int(np.argmin(d))
            if d[j] <= radius:
                found.append((float(d[j]), k, chain[j] + (chain[j + 1] - chain[j]) * t[j], a[j] + ab[j] * t[j]))
        if not found:
            return None
        found.sort(key=lambda f: f[0])
        tris = None if self.model is None else np.asarray(self.model.triangles)
        if tris is not None and len(tris):
            tol = max(self.bounds()[3] - self.bounds()[0], self.bounds()[4] - self.bounds()[1], 1e-3) * 0.01
            for _d, k, point, xy in found[:6]:
                ray = self.ray_at(QPointF(float(xy[0]), float(xy[1])))
                if ray is None:
                    continue
                i, t = faces3d.ray_hit(tris, *ray)
                if i < 0 or t >= float((point - ray[0]) @ ray[1]) - tol:
                    return k
        return found[0][1]

    def select_at(self, pos, add: bool = False):
        """Clic de sélection : la face visée (mode 'faces') ou le contour
        fermé de cette face le plus proche du point visé (mode 'contours') ;
        `add` (Ctrl ou Maj) : ajoutée à la sélection, ou retirée si elle y
        est déjà. Un clic dans le vide sans `add` efface tout. Rend la face
        ou le contour, ou None."""
        import numpy as np
        from ..core import faces3d
        if self.select_mode == 'aretes':                 # un clic ajoute ou retire ; dans le vide, rien ne change
            k = self.edge_at(pos)
            if k is not None:
                self.set_edge_selection(self.sel_edges ^ {k})
            return k
        hit = self.face_at(pos)
        if hit is None:
            if not add and (self.sel_faces or self.sel_loops):
                self.clear_selection()
            return None
        face, _tri, point = hit
        if self.select_mode == 'contours':
            loops = faces3d.boundary_loops(self.model.triangles,
                                           faces3d.face_triangles(self.model.face_ids(), [face]))
            if not loops:
                return None
            loop = min(loops, key=lambda L: _dist_to_polyline(point, L))
            same = [k for k, L in enumerate(self.sel_loops) if len(L) == len(loop) and np.allclose(L, loop)]
            if not add:
                self.sel_loops = [] if same and len(self.sel_loops) == 1 else [loop]
                self.sel_faces = set()
            elif same:
                del self.sel_loops[same[0]]
            else:
                self.sel_loops.append(loop)
            result = loop
        else:
            if not add:
                self.sel_faces = set() if self.sel_faces == {face} else {face}
                self.sel_loops = []
            elif face in self.sel_faces:
                self.sel_faces.discard(face)
            else:
                self.sel_faces.add(face)
            result = face
        self._dirty = True
        self.update()
        self.selectionChanged.emit()
        return result

    def set_selection(self, faces=(), loops=()) -> None:
        import numpy as np
        self.sel_faces = {int(f) for f in faces}
        self.sel_loops = [np.asarray(L, dtype=float) for L in loops] if loops else []
        self._dirty = True
        self.update()
        self.selectionChanged.emit()

    def clear_selection(self) -> None:
        self.set_selection()

    def selected_triangles(self):
        """Indices des triangles des faces choisies."""
        import numpy as np
        from ..core import faces3d
        if self.model is None or not self.sel_faces:
            return np.zeros(0, dtype=np.int64)
        return faces3d.face_triangles(self.model.face_ids(), self.sel_faces)

    def selection_text(self) -> str:
        """Résumé de la sélection (nombre, aire, hauteurs), ou ''."""
        from ..core import faces3d
        f = lambda v: f'{v:.2f}'.rstrip('0').rstrip('.').replace('.', ',')       # noqa: E731
        if self.sel_faces and self.model is not None:
            d = faces3d.describe(self.model.triangles[self.selected_triangles()])
            kind = tr(', horizontale') if d['plat'] else (tr(', verticale') if d['vertical'] else '')
            text = tr('{0} face(s) choisie(s) : {1} mm², Z {2} à {3}{4}').format(
                len(self.sel_faces), f(d['aire']), f(d['z_min']), f(d['z_max']),
                kind if len(self.sel_faces) == 1 else '')
            if len(self.sel_faces) <= 2:                 # ce qu'est la face, ou la mesure entre les deux
                from .step_select import short_text
                try:
                    more = short_text(self.model, self.sel_faces)
                except (ValueError, IndexError, KeyError, TypeError):
                    more = ''
                if more:
                    text += ' — ' + more
            return text
        if self.sel_loops:
            import numpy as np
            z = np.concatenate([np.asarray(L)[:, 2] for L in self.sel_loops])
            return tr('{0} contour(s) fermé(s) choisi(s), Z {1} à {2}').format(
                len(self.sel_loops), f(float(z.min())), f(float(z.max())))
        return ''

    def _points(self):
        """Sommets des trajectoires montrées (repère affiché : profondeurs exagérées)."""
        if (self._dirty or self._pick_pts is None) and (self.relief is not None or self.model is not None):
            import numpy as np
            if self.model is not None:
                arr, _r = path_batch(self.model_paths, rapids=self.show_rapids, dz=self.model_dz) \
                    if self.show_paths else (np.zeros((0, 9), np.float32), [])
                self._pick_pts = self._model_points(arr)
                return self._pick_pts
            elif self.relief is not None and self.show_paths:
                arr, _r = path_batch(self.relief.toolpaths, exag=self.exag, rapids=self.show_rapids)
            else:
                arr = np.zeros((0, 9), np.float32)
            self._pick_pts = arr[:, :3] if len(arr) else None
        return self._pick_pts

    def _model_points(self, paths):
        """Points à viser sur un modèle 3D : sommets de ses arêtes, et ceux
        des trajectoires tracées dessus."""
        import numpy as np
        parts = []
        seg = getattr(self.model, 'segments', None)
        if seg is not None and len(seg):
            parts.append(np.asarray(seg, dtype=np.float32).reshape(-1, 3))
        if paths is not None and len(paths):
            parts.append(np.asarray(paths[:, :3], dtype=np.float32))
        return np.concatenate(parts) if parts else None

    def pick_at(self, pos, radius: float = 10.0):
        """Le sommet de trajectoire le plus proche du clic (à `radius` pixels
        près) devient un point choisi ; le troisième recommence. Rend le
        point (x, y, z vrais) ou None."""
        import numpy as np
        pts = self._points()
        if pts is None or not len(pts) or self.width() <= 0:
            return None
        m = np.array(self.camera().data(), dtype=np.float64).reshape(4, 4)
        h = np.c_[pts.astype(np.float64), np.ones(len(pts))] @ m
        ok = h[:, 3] > 1e-9
        if not ok.any():
            return None
        x = (h[:, 0] / np.where(ok, h[:, 3], 1) + 1) * 0.5 * self.width()
        y = (1 - h[:, 1] / np.where(ok, h[:, 3], 1)) * 0.5 * self.height()
        d = np.hypot(x - pos.x(), y - pos.y())
        d[~ok] = np.inf
        if self.clip is not None:
            d[pts[:, 2] > self.clip] = np.inf
        i = int(np.argmin(d))
        if not np.isfinite(d[i]) or d[i] > radius:
            return None
        px, py, pz = (float(v) for v in pts[i])
        if self.model is None and pz < 0 and self.exag > 0:
            pz /= self.exag                                # profondeur vraie
        elif self.model is not None:
            pz -= self.model_dz
        if len(self.picks) >= 2:
            self.picks = []
        self.picks.append((px, py, pz))
        self.update()
        return self.picks[-1]

    def pick_lines(self) -> list:
        """Textes des points choisis (et de leur distance)."""
        f = lambda v: f'{v:.3f}'.rstrip('0').rstrip('.').replace('.', ',')       # noqa: E731
        out = [tr('Point {0} : X {1}  Y {2}  Z {3}').format(i + 1, f(p[0]), f(p[1]), f(p[2]))
               for i, p in enumerate(self.picks)]
        if len(self.picks) == 2:
            a, b = self.picks
            d = math.dist(a, b)
            out.append(tr('Distance {0} mm (ΔX {1}, ΔY {2}, ΔZ {3})').format(
                f(d), f(b[0] - a[0]), f(b[1] - a[1]), f(b[2] - a[2])))
        return out

    def mouseDoubleClickEvent(self, ev) -> None:
        self.set_view('iso')

    def keyPressEvent(self, ev) -> None:
        k = ev.key()
        keypad = bool(ev.modifiers() & Qt.KeyboardModifier.KeypadModifier)
        views = {Qt.Key.Key_1: 'face', Qt.Key.Key_3: 'cote', Qt.Key.Key_7: 'dessus', Qt.Key.Key_0: 'iso'}
        if k in (Qt.Key.Key_F, Qt.Key.Key_Home):        # tout voir
            self.fit()
        elif k in views and (keypad or not ev.modifiers()):
            self.set_view(views[k])                      # pavé numérique : 1 face, 3 côté, 7 dessus, 0 perspective
        elif k == Qt.Key.Key_5:
            self.set_ortho(not self.ortho)
        elif k in (Qt.Key.Key_Left, Qt.Key.Key_Right):
            self.rotate(dyaw=15.0 if k == Qt.Key.Key_Left else -15.0)
        elif k in (Qt.Key.Key_Up, Qt.Key.Key_Down):
            self.rotate(dpitch=10.0 if k == Qt.Key.Key_Up else -10.0)
        elif k in (Qt.Key.Key_Plus, Qt.Key.Key_PageUp):
            self.zoom_at(1.25)
        elif k in (Qt.Key.Key_Minus, Qt.Key.Key_PageDown):
            self.zoom_at(1 / 1.25)
        elif k == Qt.Key.Key_Escape and (self.sel_faces or self.sel_loops):   # sélection effacée
            self.clear_selection()
        elif k == Qt.Key.Key_Escape and self.picks:      # points choisis effacés
            self.picks = []
            self.update()
        elif k == Qt.Key.Key_O:                        # orthogonale / perspective
            self.set_ortho(not self.ortho)
        elif k == Qt.Key.Key_Space and getattr(self.parent(), 'player', None) is not None                 and self.parent().player.isVisible():  # lecture / pause
            self.parent().player.command('lecture')
        else:
            super().keyPressEvent(ev)

    def wheelEvent(self, ev) -> None:
        steps = ev.angleDelta().y() / 120
        self.zoom_at(1.15 ** steps, ev.position())

    def zoom_at(self, factor: float, at=None) -> None:
        """Zoom de `factor` ; `at` (position à l'écran) : le point visé reste
        sous le curseur (approché dans le plan du centre de visée)."""
        old = self.zoom
        self.zoom = max(0.2, min(80.0, self.zoom * factor))
        if at is not None and self.width() > 0 and self.height() > 0 and abs(self.zoom - old) > 1e-12:
            x0, y0, z0, x1, y1, z1 = self.bounds()
            size = max(x1 - x0, y1 - y0, z1 - z0, 1e-3)
            dist = size * 1.5 / old
            h = dist * math.tan(math.radians(17.5))
            u = (at.x() / self.width() - 0.5) * 2 * h * self.width() / self.height()
            v = (0.5 - at.y() / self.height()) * 2 * h
            yaw, pitch = math.radians(self.yaw), math.radians(self.pitch)
            right = QVector3D(math.cos(yaw), math.sin(yaw), 0.0)
            fwd = QVector3D(-math.cos(pitch) * math.sin(yaw), math.cos(pitch) * math.cos(yaw), -math.sin(pitch))
            up = QVector3D.crossProduct(right, fwd)
            self.pan += (right * u + up * v) * (1.0 - old / self.zoom)
        self.update()

    def center_on(self, x: float, y: float, z: float) -> None:
        """La vue centrée sur le point (repère affiché : profondeur exagérée)."""
        x0, y0, z0, x1, y1, z1 = self.bounds()
        if self.model is None and z < 0:
            z *= self.exag
        elif self.model is not None:
            z += self.model_dz
        self.pan = QVector3D(x - (x0 + x1) / 2, y - (y0 + y1) / 2, z - (z0 + z1) / 2)
        self.update()

    def rotate(self, dyaw: float = 0.0, dpitch: float = 0.0) -> None:
        self.yaw = (self.yaw + dyaw) % 360
        self.pitch = max(-89.9, min(89.9, self.pitch + dpitch))
        self.update()


def _dist_to_polyline(p, L) -> float:
    """Distance du point p (3D) à la polyligne L (k, 3)."""
    import numpy as np
    L = np.asarray(L, dtype=np.float64)
    a, b = L[:-1], L[1:]
    ab = b - a
    den = np.einsum('ij,ij->i', ab, ab)
    t = np.clip(np.einsum('ij,ij->i', np.asarray(p) - a, ab) / np.where(den > 0, den, 1.0), 0.0, 1.0)
    q = a + ab * t[:, None]
    return float(np.linalg.norm(q - np.asarray(p), axis=1).min()) if len(q) else float('inf')


class Player(QWidget):
    """Lecture des parcours (comme la simulation de NeoDrive) : curseur sur
    les mouvements, lecture, pas à pas, vitesse ; l'outil est dessiné à sa
    place, la suite des parcours estompée et — en simulation — la matière
    enlevée jusque-là (étapes calculées à la suite, mises en cache)."""
    SPEEDS = (('×1', 1), ('×4', 4), ('×16', 16), ('×64', 64), ('×256', 256))

    def __init__(self, panel):
        super().__init__(panel)
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QSlider
        self.panel = panel
        row = QHBoxLayout(self)
        row.setContentsMargins(6, 0, 6, 3)
        self.buttons = {}
        for key, text, tip in (('debut', '⏮', 'Début'), ('arriere', '◀', 'Mouvement précédent'),
                               ('lecture', '▶', 'Lecture / pause (Espace)'), ('avant', '▶|', 'Mouvement suivant'),
                               ('fin', '⏭', 'Fin : tout l\'usinage')):
            b = QToolButton()
            b.setText(text)
            b.setToolTip(tr(tip))
            b.setAutoRaise(True)
            b.clicked.connect(lambda _=False, k=key: self.command(k))
            row.addWidget(b)
            self.buttons[key] = b
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 0)
        self.slider.valueChanged.connect(self._moved)
        row.addWidget(self.slider, 1)
        self.speed = QComboBox()
        for label, v in self.SPEEDS:
            self.speed.addItem(label, v)
        self.speed.setCurrentIndex(2)
        self.speed.setToolTip(tr('Vitesse de lecture (mouvements par image)'))
        row.addWidget(self.speed)
        self.follow = QCheckBox(tr('Suivre l\'outil'))
        self.follow.setToolTip(tr('La vue reste centrée sur l\'outil pendant la lecture'))
        row.addWidget(self.follow)
        from .flow import ElideLabel
        self.label = ElideLabel('')
        self.label.setMinimumWidth(120)
        row.addWidget(self.label, 1)
        self.times: list = []                           # temps écoulé à la fin de chaque mouvement (s)
        self.timer = QTimer(self)
        self.timer.setInterval(40)
        self.timer.timeout.connect(self._tick)
        self.cut = QTimer(self)                          # matière : recalculée quand le curseur s'arrête
        self.cut.setSingleShot(True)
        self.cut.setInterval(150)
        self.cut.timeout.connect(self._material)
        self.moves: list = []                           # [(parcours, mouvement)] à la suite
        self.toolpaths: list = []
        self.base = None                                # relief de départ (matière intacte) et grille
        self.full = None                                # relief complet (fin)
        self.stages: dict = {}                          # numéro → SimResult
        self.setVisible(False)

    def load(self, toolpaths, relief=None) -> None:
        """Parcours à lire ; `relief` : relief de simulation complet (matière enlevée)."""
        self.timer.stop()
        self.toolpaths = [tp for tp in toolpaths if tp.moves]
        self.moves = [(tp, m) for tp in self.toolpaths for m in tp.moves]
        try:
            from ..cam import model as _M, timing
            setup = getattr(self.panel.view, 'setup', None) or _M.CamSetup()
            self.times = timing.cumulative(self.toolpaths, setup)
            mach = next((s for tp in self.toolpaths if (s := getattr(tp, 'machine_seconds', None))), None)
            self.machine_timed = bool(mach and self.times and self.times[-1] > 0)
            if self.machine_timed:                       # durée de la machine : l'estimation donne les proportions
                k = mach / self.times[-1]
                self.times = [t * k for t in self.times]
        except Exception:                                # temps impossible : la lecture reste
            self.times = []
        self.full = relief if relief is not None and relief.source == 'simulation' else None
        self.base = None
        self.stages = {}
        if self.full is not None:
            from ..cam.simulate import SimResult, initial_heights
            s = self.full.sim
            st = getattr(s, 'stock', None)                # brut : la matière intacte part de son haut
            self.base = SimResult(initial_heights(st, s.x0, s.y0, s.res, s.H.shape), s.x0, s.y0, s.res, stock=st)
            self.stages[0] = self.base
        n = len(self.moves)
        self.slider.blockSignals(True)
        self.slider.setRange(0, n)
        self.slider.setValue(n)
        self.slider.blockSignals(False)
        self.setVisible(n > 0)
        self.panel.view.set_playhead(1e12)
        self.label.setText(tr('{0} mouvements — curseur ou lecture pour suivre l\'usinage').format(n) if n else '')

    def command(self, key: str) -> None:
        n = len(self.moves)
        k = self.slider.value()
        if key == 'lecture':
            if self.timer.isActive():
                self.timer.stop()
                self.buttons['lecture'].setText('▶')
            else:
                if k >= n:
                    self.slider.setValue(0)
                self.timer.start()
                self.buttons['lecture'].setText('⏸')
            return
        self.timer.stop()
        self.buttons['lecture'].setText('▶')
        self.slider.setValue({'debut': 0, 'arriere': max(0, k - 1), 'avant': min(n, k + 1), 'fin': n}[key])

    def _tick(self) -> None:
        n = len(self.moves)
        k = self.slider.value() + int(self.speed.currentData() or 1)
        if k >= n:
            k = n
            self.timer.stop()
            self.buttons['lecture'].setText('▶')
        self.slider.setValue(k)
        import time
        if self.full is not None and time.monotonic() - getattr(self, '_last_cut', 0.0) > 0.5:
            self._last_cut = time.monotonic()               # pendant la lecture : la matière suit
            self.cut.stop()
            self._material()

    def tool_at(self, k: int):
        """(position, diamètre, nature, angle) de l'outil après k mouvements."""
        if not self.moves or k <= 0:
            return None
        tp, m = self.moves[min(k, len(self.moves)) - 1]
        setup = self.panel.win.cam_panel.setup() if hasattr(self.panel.win, 'cam_panel') else None
        t = setup.tool(tp.tool_id) if setup is not None else None
        if t is None:
            t = getattr(tp, 'tool_guess', None)            # programme lu : outil reconnu d'après son libellé
        dia = t.diameter if t is not None else 1.0
        return (m.x, m.y, m.z), dia, (t.kind if t is not None else 'fraise'), (t.angle if t is not None else 0.0)

    def _moved(self, k: int) -> None:
        n = len(self.moves)
        view = self.panel.view
        if k >= n:
            view.set_playhead(1e12)
        else:
            view.set_playhead(k - 0.5, self.tool_at(k))
        if 0 < k <= n:
            tp, m = self.moves[k - 1]
            kind = tr('rapide') if m.kind == 'rapid' else tr('avance')
            text = tr('Mouvement {0} / {1} — {2} — X {3:.3f}  Y {4:.3f}  Z {5:.3f} — {6}').format(
                k, n, kind, m.x, m.y, m.z, tp.name or '')
            if len(self.times) == n and n:
                from ..cam.timing import format_duration
                text += f' — {format_duration(self.times[k - 1])} / {format_duration(self.times[-1])}'
                if getattr(self, 'machine_timed', False):
                    text += ' ' + tr('(durée machine)')
            self.label.setText(text)
            if self.follow.isChecked():
                view.center_on(m.x, m.y, m.z)
        else:
            self.label.setText(tr('Début — {0} mouvements').format(n))
        if self.full is not None:
            self.cut.start()

    def stage(self, k: int):
        """Matière après k mouvements (depuis l'étape en cache la plus proche)."""
        from ..cam.simulate import simulate_range
        if k in self.stages:
            return self.stages[k]
        j = max(i for i in self.stages if i <= k)
        setup = self.panel.win.cam_panel.setup()
        s = simulate_range(self.toolpaths, setup, self.stages[j], j, k)
        if len(self.stages) > 40:                        # mémoire : on garde le départ et les plus récentes
            for old in sorted(self.stages)[1:-20]:
                self.stages.pop(old, None)
        self.stages[k] = s
        return s

    def _material(self) -> None:
        if self.full is None:
            return
        from ..cam.relief import Relief
        k = self.slider.value()
        r = self.full if k >= len(self.moves) else Relief(self.stage(k), self.full.plate, self.full.toolpaths,
                                                          'simulation', [])
        view = self.panel.view
        keep = (view.yaw, view.pitch, view.zoom, view.pan)
        view.relief = r
        view._dirty = True
        view.yaw, view.pitch, view.zoom, view.pan = keep
        view.update()


#: donnée de la prise « toutes » (trajectoires recomposées) dans la liste des prises
ALL_SETUPS = '*'


class Panel3D(QWidget):
    """Plan de travail en mode 3D : barre (source, vues, relief ×, parcours)
    et vue OpenGL."""
    _anim_dlg = None                                     # la fenêtre ouverte par le bouton Animation

    def __init__(self, win, parent=None):
        super().__init__(parent)
        self.win = win
        from .flow import ElideLabel, FlowLayout
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        # une barre qui passe à la ligne : elle tient dans une fenêtre étroite (et ne l'élargit pas)
        self.bar = QWidget(self)
        bar = FlowLayout(self.bar)
        bar.setContentsMargins(6, 3, 6, 3)
        bar2 = bar
        bar.addWidget(QLabel(tr('Relief')))
        self.source = QComboBox()
        for key, label in (('auto', 'Automatique'), ('modele', 'Modèle 3D du fichier (STEP, STL, 3D XML)'),
                           ('volumes', 'Volumes du dessin'),
                           ('dessin', 'Dessin (profondeurs des outils)'), ('fao', 'Parcours FAO simulés'),
                           ('parcours', 'Trajectoires FAO calculées'),
                           ('simulation', 'Simulation des parcours FAO calculés')):
            self.source.addItem(tr(label), key)
        self.source.setToolTip(tr('Automatique : le modèle 3D si le dessin vient d\'un fichier 3D (STEP…), sinon '
                                  'ses volumes s\'il en a, sinon les parcours FAO s\'il y a des opérations actives, '
                                  'sinon le dessin (traits à la largeur de leur outil, profondeur de leur opération '
                                  'ou {0} mm)').format(0.3))
        self.source.currentIndexChanged.connect(lambda _i: self.refresh())
        bar.addWidget(self.source)
        for key, label in (('dessus', 'Dessus'), ('face', 'Face'), ('cote', 'Côté'), ('graveur', 'Graveur'),
                           ('iso', 'Perspective')):
            b = QToolButton()
            b.setText(tr(label))
            b.setAutoRaise(True)
            b.clicked.connect(lambda _=False, k=key: self.view.set_view(k))
            bar.addWidget(b)
        b = QToolButton()
        b.setText(tr('Tout voir'))
        b.setAutoRaise(True)
        b.setToolTip(tr('Cadrer toute la pièce (F)'))
        b.clicked.connect(lambda _=False: self.view.fit())
        bar.addWidget(b)
        self.ortho = QCheckBox(tr('Orthogonale'))
        self.ortho.setToolTip(tr('Projection sans perspective : les cotes se lisent à l\'écran (O)'))
        self.ortho.toggled.connect(lambda on: self.view.set_ortho(on))
        bar.addWidget(self.ortho)
        self.display = QComboBox()
        for key, label in DISPLAY.items():
            self.display.addItem(tr(label), key)
        self.display.setToolTip(tr('Affichage du modèle 3D ou de la matière'))
        self.display.setCurrentIndex(self.display.findData('filaire'))   # comme la vue : filaire par défaut
        self.display.currentIndexChanged.connect(lambda _i: self.view.set_display(self.display.currentData()))
        bar.addWidget(self.display)
        self.select = QComboBox()
        for key, label in SELECT_MODES.items():
            self.select.addItem(tr(label), key)
        self.select.setToolTip(tr('Modèle 3D : un clic choisit une face ou un contour fermé (Ctrl ou Maj : '
                                  'plusieurs, un second clic retire) pour l\'usiner ou modifier un usinage ; '
                                  'Échap efface la sélection'))
        self.select.currentIndexChanged.connect(lambda _i: self._select_mode())
        for w in (self.select,):                        # mode de clic : ruban FAO 3D (« Clic dans la vue »)
            w.setParent(self)
            w.setVisible(False)
        from PySide6.QtWidgets import QMenu
        self.use = QToolButton()
        self.use.setText(tr('Usinage 3D'))
        self.use.setToolTip(tr('Ébaucher ou balayer toute la pièce ou les faces et contours choisis, les mettre '
                               'dans le dessin, remplacer la zone d\'un usinage 3D'))
        self.use.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.use_menu = QMenu(self.use)
        self.use_menu.aboutToShow.connect(self._fill_use_menu)
        self.use.setMenu(self.use_menu)
        self.use.setParent(self)                         # ses commandes : ruban FAO 3D
        self.use.setVisible(False)
        self.color_btn = QToolButton()
        self.color_btn.setText(tr('Couleurs'))
        self.color_btn.setToolTip(tr('Couleur de la pièce et de ses arêtes (retenues) ; d\'origine : celles du '
                                     'fichier, arêtes claires sur fond sombre'))
        self.color_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        cm = QMenu(self.color_btn)
        cm.addAction(tr('Couleur de la pièce…'), lambda: self.choose_color('part'))
        cm.addAction(tr('Couleur des arêtes…'), lambda: self.choose_color('edge'))
        cm.addSeparator()
        cm.addAction(tr('Couleurs d\'origine'), self.reset_colors)
        self.color_btn.setMenu(cm)
        self.color_btn.setParent(self)
        self.color_btn.setVisible(False)
        self.bodies = QToolButton()
        self.bodies.setText(tr('Corps'))
        self.bodies.setToolTip(tr('Corps (solides) de la pièce : les montrer ou les masquer, une couleur par corps'))
        self.bodies.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.bodies_menu = QMenu(self.bodies)
        self.bodies_menu.aboutToShow.connect(self._fill_bodies_menu)
        self.bodies.setMenu(self.bodies_menu)
        self.bodies.setParent(self)
        self.bodies.setVisible(False)
        self.setup_view = QComboBox(self)                # prise montrée : choisie par les onglets (pas montrée)
        self.setup_view.setVisible(False)
        self.setup_view.currentIndexChanged.connect(lambda _i: self._setup_view_changed())
        b = QPushButton(tr('Recalculer'))
        b.clicked.connect(self.refresh)
        bar.addWidget(b)
        b = QPushButton(tr('Animation'))
        b.setToolTip(tr('Les corps de la pièce 3D en mouvement ; liaisons, course, sens et collisions dans sa fenêtre'))
        b.clicked.connect(lambda: self.animate())
        bar.addWidget(b)
        bar2.addWidget(QLabel(tr('Relief ×')))
        self.exag = QDoubleSpinBox()
        self.exag.setRange(0.5, 50.0)
        self.exag.setDecimals(1)
        self.exag.setValue(1.0)
        self.exag.setToolTip(tr('Exagération des profondeurs (1 = vraie grandeur)'))
        self.exag.valueChanged.connect(lambda v: self.view.set_exag(v))
        bar2.addWidget(self.exag)
        self.paths = QCheckBox(tr('Parcours'))
        self.paths.setChecked(True)
        self.paths.toggled.connect(self._paths)
        bar2.addWidget(self.paths)
        self.rapids = QCheckBox(tr('Rapides'))
        self.rapids.setToolTip(tr('Déplacements rapides des parcours (en orange)'))
        self.rapids.toggled.connect(self._rapids)
        bar2.addWidget(self.rapids)
        self.fill = QCheckBox(tr('Contours fermés évidés'))
        self.fill.setToolTip(tr('Relief du dessin : creuser l\'intérieur des contours fermés (sinon seulement le trait)'))
        self.fill.toggled.connect(lambda _on: self.refresh())
        bar2.addWidget(self.fill)
        from PySide6.QtWidgets import QSlider
        bar2.addWidget(QLabel(tr('Transparence')))
        self.alpha = QSlider(Qt.Orientation.Horizontal)
        self.alpha.setRange(0, 90)
        self.alpha.setValue(0)
        self.alpha.setFixedWidth(90)
        self.alpha.setToolTip(tr('Matière et modèle 3D translucides : les parcours (et le dessin) se voient au '
                                 'travers — 0 : opaque'))
        self.alpha.valueChanged.connect(lambda v: self.view.set_alpha(1.0 - v / 100.0))
        bar2.addWidget(self.alpha)
        bar2.addWidget(QLabel(tr('Coupe')))
        self.clip = QSlider(Qt.Orientation.Horizontal)
        self.clip.setRange(0, 100)
        self.clip.setValue(100)
        self.clip.setFixedWidth(90)
        self.clip.setToolTip(tr('Plan de coupe horizontal : rien n\'est montré au-dessus (100 : pas de coupe) — '
                                'pour voir l\'intérieur d\'une pièce ou le fond d\'une poche'))
        self.clip.valueChanged.connect(lambda v: self.view.set_clip(v / 100.0))
        bar2.addWidget(self.clip)
        self.finesse = QComboBox()
        for key, (label, _cells, _side) in FINESSE.items():
            self.finesse.addItem(tr(label), key)
        self.finesse.setToolTip(tr('Finesse de la simulation et du relief : grille de 1, 4 ou 16 millions de '
                                   'points, surface affichée plus détaillée (gravures fines) — plus lent'))
        st = getattr(win, 'settings', None)
        cur = str(st.value(FINESSE_KEY, 'normale') or 'normale') if st is not None else 'normale'
        self.finesse.setCurrentIndex(max(0, self.finesse.findData(cur)))
        self.finesse.currentIndexChanged.connect(lambda _i: self._finesse_changed())
        bar2.addWidget(QLabel(tr('Finesse')))
        bar2.addWidget(self.finesse)
        self.plate = QCheckBox(tr('Plaque'))
        self.plate.setChecked(True)
        self.plate.setToolTip(tr('Plaque de travail (bloc de matière, ses arêtes en filaire) : décocher pour ne '
                                 'voir que les trajectoires et la surface usinée'))
        self.plate.toggled.connect(lambda on: self._set_view_flag('show_plate', on))
        bar2.addWidget(self.plate)
        self.grid = QCheckBox(tr('Grille'))
        self.grid.setChecked(True)
        self.grid.setToolTip(tr('Grille au sol sous la pièce (pas affiché en haut à gauche)'))
        self.grid.toggled.connect(lambda on: self._set_view_flag('grid', on))
        bar2.addWidget(self.grid)
        self.overlay = QCheckBox(tr('Cotes'))
        self.overlay.setChecked(True)
        self.overlay.setToolTip(tr('Cotes de la pièce (X × Y × Z) et légende des parcours, en surimpression'))
        self.overlay.toggled.connect(lambda on: self._set_view_flag('overlay', on, upload=False))
        bar2.addWidget(self.overlay)
        self.colors = QComboBox()
        for key, label in (('parcours', 'Couleur par parcours'), ('profondeur', 'Couleur par profondeur'),
                           ('unie', 'Couleur unie')):
            self.colors.addItem(tr(label), key)
        self.colors.setToolTip(tr('Trajectoires : une couleur par parcours (légende en haut à gauche), un dégradé '
                                  'de la surface (clair) au fond (foncé), ou toutes en bleu'))
        self.colors.currentIndexChanged.connect(
            lambda _i: self._set_view_flag('path_colors', self.colors.currentData(), as_bool=False))
        bar2.addWidget(self.colors)
        b = QToolButton()
        b.setText(tr('Image…'))
        b.setAutoRaise(True)
        b.setToolTip(tr('Enregistrer la vue 3D en image (PNG, JPEG)'))
        b.clicked.connect(lambda _=False: self.export_image())
        bar2.addWidget(b)
        self.info = ElideLabel('')
        self.info.setContentsMargins(6, 0, 6, 2)
        lay.addWidget(self.bar)
        lay.addWidget(self.info)
        self.parts = self._parts_bar()
        lay.addWidget(self.parts)
        self.player = Player(self)
        lay.addWidget(self.player)
        self.view = View3D(self)
        if st is not None:                                 # couleurs choisies une fois pour toutes
            self.view.part_color = rgb_of(st.value(PART_COLOR_KEY, ''))
            self.view.edge_color = rgb_of(st.value(EDGE_COLOR_KEY, ''))
        self.view.selectionChanged.connect(self._selection_changed)
        from PySide6.QtWidgets import QSplitter
        from .ops3d_list import Ops3DList
        self.split = QSplitter(Qt.Orientation.Horizontal)  # la vue, et la liste des usinages à sa droite
        self.split.addWidget(self.view)
        self.ops_list = Ops3DList(self)
        self.split.addWidget(self.ops_list)
        self.split.setStretchFactor(0, 1)
        self.split.setStretchFactor(1, 0)
        self.split.setCollapsible(0, False)
        self.split.setSizes([900, 300])
        lay.addWidget(self.split, 1)
        self.relief = None
        self.model = None
        self._model_key = None
        self.stale = True
        self._sync_actions()

    def _sync_actions(self) -> None:
        """Boutons cochables du ruban FAO 3D comme la vue : mode de clic,
        couleur par corps."""
        A = getattr(self.win, 'A', None) or {}
        mode = self.select.currentData() or 'off'
        for key, on in (('cam3d_pick_faces', mode == 'faces'), ('cam3d_pick_contours', mode == 'contours'),
                        ('cam3d_pick_off', mode == 'off'),
                        ('cam3d_body_colors', bool(getattr(self.view, 'body_colors', False)))):
            a = A.get(key)
            if a is not None and a.isChecked() != on:
                a.blockSignals(True)
                a.setChecked(on)
                a.blockSignals(False)
                if on and a.actionGroup() is not None:  # signaux bloqués : le groupe ne l'a pas vu cocher
                    a.actionGroup().addAction(a)

    def set_pick(self, mode: str) -> None:
        """Clic dans la vue : 'faces', 'contours' ou 'off' (points et cotes)."""
        i = self.select.findData(mode)
        if i >= 0:
            self.select.setCurrentIndex(i)
        self._sync_actions()

    def clear_pick(self) -> None:
        self.view.clear_selection()

    def set_body_colors(self, on: bool) -> None:
        self._set_view_flag('body_colors', on)
        self._sync_actions()

    def set_analysis(self, kind: str | None, direction: str = 'z+', angle: float = 1.0) -> list:
        """Analyse de surface de la pièce montrée (d'après SolidCraft) :
        'depouille' (faces par dépouille vers `direction`, angle minimal
        `angle`), 'acces' (faces atteintes le long de `direction`) ou None ;
        l'affichage filaire passe en ombré. Rend les parts de la surface par
        couleur ([] sans analyse ou sans pièce)."""
        v = self.view
        v.analysis = None if not kind else (kind, direction, float(angle)) if kind == 'depouille' else (kind, direction)
        v._analysis_cache = None
        if kind and v.display == 'filaire':
            self.display.setCurrentIndex(self.display.findData('aretes'))
        v._dirty = True
        v.update()
        if not kind or v.model is None:
            return []
        v.shown_model()
        return list(v._analysis_cache[1][3])

    def _say(self, text: str) -> None:
        self.info.setText(text)
        self.win.statusBar().showMessage(text, 8000)

    def _has_part(self) -> bool:
        """Une pièce 3D à usiner est montrée ; sinon, le dire."""
        if self.view.model is None or self.machining_path() is None:
            self._say(tr('Pas de pièce 3D à usiner : ouvrir un STEP, un STL, un 3D XML, ou modéliser des volumes '
                         '(ruban 3D)'))
            return False
        return True

    def show_part(self) -> None:
        """La pièce 3D (fichier ou volumes du dessin) montrée au lieu des
        trajectoires, de la simulation ou du relief du dessin : les commandes
        du ruban FAO 3D la visent."""
        from ..core import solids as SO
        from ..io import model3d
        if (self.source.currentData() or 'auto') in ('auto', 'modele', 'volumes'):
            return
        doc = self.win.canvas.doc
        if model3d.source_of(doc) is not None or (SO.available() and SO.doc_solids(doc)):
            self.set_source('auto')

    def with_part(self, what: str, *args):
        """Commande du ruban qui vise la pièce : rien sans pièce (dit)."""
        return getattr(self, what)(*args) if self._has_part() else None

    def _has_selection(self) -> bool:
        if self.view.sel_faces or self.view.sel_loops:
            return True
        self._say(tr('Choisir d\'abord des faces ou des contours (ruban FAO 3D : « Faces », « Contours fermés »)'))
        return False

    def machine3d(self, kind: str, need_selection: bool = False, exec_dialog: bool = True):
        """Ruban FAO 3D : `kind` sur les faces et contours choisis, sinon sur
        toute la pièce (le corps, la pièce retournée de la prise montrée) ;
        `need_selection` : jamais toute la pièce."""
        if not self._has_part():
            return None
        has = bool(self.view.sel_faces or self.view.sel_loops)
        if need_selection and not self._has_selection():
            return None
        return self.machine_selection(kind, exec_dialog=exec_dialog, whole=not has)

    def pocket_to_floor(self):
        """Ruban FAO 3D : poche jusqu'au fond plat choisi."""
        if not (self._has_part() and self._has_selection()):
            return None
        if not self.flat_selection():
            self._say(tr('Choisir un fond plat (faces à une seule hauteur)'))
            return None
        return self.contours_to_drawing(pocket=True)

    def selection_to_drawing(self):
        """Ruban FAO 3D : contours de la sélection dans le dessin."""
        if not (self._has_part() and self._has_selection()):
            return None
        return self.contours_to_drawing()

    def holes3d(self):
        """Ruban FAO 3D : trous de la pièce en perçages (prise du dessin)."""
        if not self._has_part():
            return None
        if self.current_setup() != ('', -1):             # « Toutes » : la pièce comme le dessin
            self._say(tr('Trous → perçages : dans la prise « Comme le dessin » de l\'ensemble'))
            return None
        return self.holes_to_drilling()

    def place_selected_body(self):
        """Ruban FAO 3D : le corps de l'onglet, sinon celui des faces choisies, posé à part."""
        part = self.current_part()
        return self.place_body(part if part >= 0 else None)

    def fill_zone_menu(self, m) -> None:
        """Menu « Zone d'un usinage » du ruban FAO 3D, sans sous-menus (rien
        ne reste d'une ouverture à l'autre)."""
        m.clear()
        cp = getattr(self.win, 'cam_panel', None)
        ops = cp.ops_3d() if cp is not None else []
        if not ops:
            m.addAction(tr('Aucun usinage 3D')).setEnabled(False)
            return
        has = bool(self.view.sel_faces or self.view.sel_loops)
        for o in ops:                                    # la sélection devient sa zone
            act = m.addAction(tr('Remplacer la zone de « {0} »').format(o.name or o.kind),
                              lambda _=False, oid=o.id: self.win._cam3d('replace_zone', oid))
            act.setEnabled(has)
        m.addSeparator()
        for o in ops:                                    # sa zone devient la sélection
            act = m.addAction(tr('Montrer la zone de « {0} »').format(o.name or o.kind),
                              lambda _=False, op=o: self.win._cam3d('show_zone', op))
            act.setEnabled(bool(o.faces3d or o.contours3d))

    def fill_bodies_list(self, m) -> None:
        """Menu « Corps » du ruban FAO 3D : chaque corps montré ou masqué."""
        self._fill_bodies_menu(m)

    def _select_mode(self) -> None:
        self._sync_actions()
        self.view.select_mode = self.select.currentData() or 'off'
        if self.view.select_mode == 'off':
            self.view.clear_selection()
        elif self.view.select_mode == 'faces' and self.view.sel_loops:
            self.view.set_selection(faces=self.view.sel_faces)
        elif self.view.select_mode == 'contours' and self.view.sel_faces:
            self.view.set_selection(loops=self.view.sel_loops)

    def _selection_changed(self) -> None:
        text = self.view.selection_text()
        self.info.setText(text or (tr('Modèle 3D : {0}').format(self.model.summary()) if self.model is not None
                                   else ''))

    # --- usinage de la sélection ----------------------------------------------------------
    def selection_loops(self) -> list:
        """Contours fermés de la sélection : ceux choisis, sinon ceux qui
        bordent les faces choisies (repère du modèle)."""
        from ..core import faces3d
        v = self.view
        if v.sel_loops:
            return [L.copy() for L in v.sel_loops]
        if v.sel_faces and v.model is not None:
            return faces3d.boundary_loops(v.model.triangles, v.selected_triangles())
        return []

    def selection_depth(self) -> float:
        """Profondeur sous le haut de la pièce du point le plus bas de la
        sélection (mm, ≥ 0)."""
        import numpy as np
        v = self.view
        if v.model is None:
            return 0.0
        top = float(v.model.bounds()[5])
        sel = v.selected_triangles() if v.sel_faces else []
        if len(sel):
            low = float(np.asarray(v.model.triangles)[sel][:, :, 2].min())
        elif v.sel_loops:
            low = min(float(np.asarray(L)[:, 2].min()) for L in v.sel_loops)
        else:
            return 0.0
        return max(0.0, top - low)

    def _fill_use_menu(self) -> None:
        m = self.use_menu
        m.clear()
        v = self.view
        cp = getattr(self.win, 'cam_panel', None)
        has = bool(v.sel_faces or v.sel_loops)
        a = m.addAction(tr('Ébauche 3D de la sélection (paliers en Z)…'), lambda: self.machine_selection('ebauche3d'))
        a.setEnabled(has and cp is not None)
        a = m.addAction(tr('Balayage 3D de la sélection (surface 3D)…'), lambda: self.machine_selection('surface3d'))
        a.setEnabled(has and cp is not None)
        a = m.addAction(tr('Niveaux constants de la sélection (parois)…'),
                        lambda: self.machine_selection('niveaux3d'))
        a.setEnabled(has and cp is not None)
        m.addSeparator()
        a = m.addAction(tr('Automatisme d\'usinage 3D…'), lambda: self.auto3d())
        a.setToolTip(tr('Ébauche, demi-finition, finition… d\'un coup, outils proposés d\'après la pièce, tout '
                        'modifiable et enregistrable — sur la sélection, sinon toute la pièce'))
        a.setEnabled(cp is not None)
        a = m.addAction(tr('Brut de la pièce 3D…'), lambda: cp.stock_dialog(model=self.model))
        a.setEnabled(cp is not None)
        a = m.addAction(tr('Espace de travail (étau, mandrin, brides)…'),
                        lambda: cp.workspace_dialog(model=self.model, setup=self.current_setup()))
        a.setEnabled(cp is not None)
        one = len(v.sel_faces) == 1 and self._model_source() is not None
        a = m.addAction(tr('Poser la pièce sur cette face (usiner le dessus)'), lambda: self.rest_on_selection())
        a.setToolTip(tr('La face plane choisie en bas, sur la table : le dessus vers l\'outil, pièce alignée sur les axes'))
        a.setEnabled(one)
        a = m.addAction(tr('Tourner cette face vers l\'outil'), lambda: self.rest_on_selection(up=True))
        a.setEnabled(one)
        a = m.addAction(tr('Positionner ce corps à part pour l\'usinage…'), lambda: self.place_body())
        a.setToolTip(tr('Pièce à plusieurs corps (moule…) : le corps choisi posé seul, sur la face voulue, tourné '
                        'et placé à part ; ses usinages se font dans cette pose, leurs trajectoires reviennent sur '
                        'l\'ensemble'))
        a.setEnabled(self.selected_body() is not None)
        m.addSeparator()
        a = m.addAction(tr('Ébauche 3D de toute la pièce…'), lambda: self.machine_selection('ebauche3d', whole=True))
        a.setEnabled(cp is not None)
        a = m.addAction(tr('Balayage 3D de toute la pièce…'), lambda: self.machine_selection('surface3d', whole=True))
        a.setEnabled(cp is not None)
        m.addSeparator()
        a = m.addAction(tr('Contours dans le dessin'), lambda: self.contours_to_drawing())
        a.setToolTip(tr('Les contours fermés de la sélection deviennent des formes du dessin (vue de dessus), '
                        'à usiner avec les parcours 2D'))
        a.setEnabled(has)
        a = m.addAction(tr('Poser sur une surface 2D (sous-onglet)'), lambda: self.surface_to_layer())
        a.setToolTip(tr('La face choisie, tournée vers l\'outil, devient un calque du dessin (sous-onglet) avec son '
                        'contour en guide : ce qu\'on y dessine s\'usine dans cette prise, à partir de la face'))
        a.setEnabled(bool(v.sel_faces) and self.machining_path() is not None)
        a = m.addAction(tr('Trous de la pièce → perçages'), lambda: self.holes_to_drilling())
        a.setToolTip(tr('Trous cylindriques verticaux de la pièce (STEP, maillage, volumes du dessin) : un cercle par '
                        'trou dans le dessin et un perçage par diamètre, à la profondeur du trou'))
        a.setEnabled(cp is not None and self.machining_path() is not None and (self.current_setup() == ('', -1)))
        a = m.addAction(tr('Poche jusqu\'à ce fond…'), lambda: self.contours_to_drawing(pocket=True))
        a.setToolTip(tr('Fond plat choisi : ses contours dans le dessin et une poche jusqu\'à sa profondeur'))
        a.setEnabled(has and cp is not None and self.flat_selection())
        ops = cp.ops_3d() if cp is not None else []
        if ops:
            sub = m.addMenu(tr('Remplacer la zone de'))
            sub.setEnabled(has)
            for o in ops:
                sub.addAction(o.name or o.kind, lambda _=False, oid=o.id: self.replace_zone(oid))
            sub2 = m.addMenu(tr('Montrer la zone de'))
            for o in ops:
                act = sub2.addAction(o.name or o.kind, lambda _=False, op=o: self.show_zone(op))
                act.setEnabled(bool(o.faces3d or o.contours3d))
        m.addSeparator()
        a = m.addAction(tr('Convertir la pièce en volumes du dessin (pour la modifier)'), lambda: self.to_volumes())
        a.setToolTip(tr('Chaque corps devient un volume du dessin (maillage réparé : jonctions, petits trous), à '
                        'modifier avec les outils 3D puis à usiner'))
        a.setEnabled(self._model_source() is not None)
        m.addSeparator()
        m.addAction(tr('Effacer la sélection (Échap)'), self.view.clear_selection)

    def flat_selection(self) -> bool:
        """La sélection est-elle à une seule hauteur (fond plat) ?"""
        import numpy as np
        v = self.view
        if v.model is None:
            return False
        if v.sel_faces:
            z = np.asarray(v.model.triangles)[v.selected_triangles()][:, :, 2]
        elif v.sel_loops:
            z = np.concatenate([np.asarray(L)[:, 2] for L in v.sel_loops])
        else:
            return False
        return bool(len(z)) and float(np.ptp(z)) < 1e-3

    def machine_selection(self, kind: str, exec_dialog: bool = True, whole: bool = False):
        """Nouvelle opération 3D sur la sélection, ou sur toute la pièce
        (`whole`) — panneau FAO. Ébauche : fraise, 0,3 mm de surépaisseur,
        entrée en rampe."""
        cp = getattr(self.win, 'cam_panel', None)
        src = self.machining_path()
        if cp is None or src is None:
            return None
        v = self.view
        kw = {'tool_kind': 'fraise', 'stock': 0.3, 'ramp': True} if kind == 'ebauche3d' else {}
        face, body = self.current_setup()                  # prise montrée : l'usinage la reprend
        if (face, body) != ('', -1):
            kw.update(setup_face=face, body3d=body)
        if whole:
            return cp.add_3d_operation(kind, model_path=src, depth=0.0, exec_dialog=exec_dialog, **kw)
        return cp.add_3d_operation(kind, faces=sorted(v.sel_faces), loops=self.loops_in_drawing(),
                                   model_path=src, depth=self.selection_depth(), exec_dialog=exec_dialog, **kw)

    def loops_in_drawing(self) -> list:
        """Contours choisis, ramenés de la prise montrée au repère de la pièce
        posée comme le dessin (celui des zones des usinages)."""
        loops = [L.tolist() for L in self.view.sel_loops]
        face, body = self.current_setup()
        src = self._model_source()
        if not loops or (face, body) == ('', -1) or src is None:
            return loops
        import numpy as np
        from ..cam import mill3d
        from ..core import placement3d as P3
        doc = self.win.canvas.doc
        shown = mill3d.side_placement(doc, src, face, body) or P3.Placement()
        view = mill3d.side_placement(doc, src, '') or P3.Placement()
        out = []
        for L in loops:
            a = np.asarray(L, dtype=np.float64).reshape(-1, 3).copy()
            a[:, 0] -= shown.dx
            a[:, 1] -= shown.dy
            out.append(view.apply(a @ shown.rotation()).tolist())
        return out

    def selected_body(self) -> int | None:
        """Corps des faces choisies (un seul, pièce du dessin à plusieurs
        corps ; celui de la prise montrée s'il est montré seul), sinon None."""
        import numpy as np
        v = self.view
        if v.model is None or not v.sel_faces or self._model_source() is None:
            return None
        shown = self.current_setup()[1]
        if shown >= 0:
            return shown
        if v.model.body_count() < 2:
            return None
        b = np.unique(np.asarray(v.model.body_ids())[v.selected_triangles()])
        return int(b[0]) if len(b) == 1 else None

    def place_body(self, body: int | None = None, *, exec_dialog: bool = True, placement=None, reset: bool = False):
        """Corps `body` (celui des faces choisies) positionné à part pour son
        usinage : face vers l'outil, rotation, position (fenêtre, ou
        `placement`) ; `reset` : de nouveau comme l'ensemble. Rend le
        placement gardé (None : rien de changé, ou remis comme l'ensemble) —
        ou la fenêtre, sans l'ouvrir."""
        from dataclasses import dataclass
        from ..cam import mill3d
        from ..core import placement3d as P3
        body = self.selected_body() if body is None else int(body)
        src = self._model_source()
        if body is None or src is None:
            self.info.setText(tr('Choisir une face d\'un des corps de la pièce'))
            return None
        doc = self.win.canvas.doc
        cur = P3.body_of(doc, body)
        if placement is None and not reset:
            from .dialogs import ParamsDialog
            base = cur or P3.of(doc)

            @dataclass
            class P:
                face: str = base.face
                rot: float = base.rot
                mode: str = base.mode if cur is not None else 'centre'
                dx: float = base.dx
                dy: float = base.dy
            labels = {'face': tr('Face tournée vers l\'outil'), 'rot': tr('Rotation autour de Z (°)'),
                      'mode': tr('Position'), 'dx': tr('Décalage X (mm, position libre)'),
                      'dy': tr('Décalage Y (mm, position libre)')}
            faces = [('', tr('Comme l\'ensemble (pas de pose à part)'))] + \
                [(k, tr(v)) for k, v in P3.FACE_LABELS.items()]
            try:                                           # faces d'appui stables du corps seul
                for key, area, _f in P3.rest_faces(mill3d.submodel(mill3d.raw_model(src), body)):
                    if key not in P3.FACES:
                        faces.append((key, tr('Posée sur une face plane de {0} mm²').format(f'{area:.0f}')))
            except Exception:                              # noqa: BLE001 — pièce illisible : les six faces
                pass
            if cur is not None and cur.face not in [k for k, _t in faces]:
                faces.append((cur.face, tr(P3.face_label(cur.face))))
            choices = {'face': faces, 'mode': [(k, tr(v)) for k, v in P3.MODES.items()]}
            names = self._body_names(src)
            name = names[body] if body < len(names) else f'Corps {body + 1}'
            dlg = ParamsDialog(self, tr('Positionner « {0} » pour l\'usinage').format(name), P(), labels,
                               choices=choices)
            if not exec_dialog:
                return dlg
            if not dlg.exec():
                return None
            r = dlg.result_params()
            reset = not r.face
            placement = None if reset else P3.Placement(r.face, float(r.rot), r.mode, float(r.dx), float(r.dy))
        self.win.push_undo(tr('Positionner un corps'), keys=(P3.KEY_BODIES,))
        P3.set_body(doc, body, None if reset else placement)
        from ..core import surface2d
        if surface2d.follow(doc):                          # ses surfaces posées le suivent
            self.win.canvas.invalidate()
        self.win.modified = True
        self._fill_setups(src)
        key = f'|{body}'
        i = self.setup_view.findData(key)
        if i >= 0 and not reset:
            self.setup_view.setCurrentIndex(i)            # le corps montré dans sa pose
        self.refresh()
        self.info.setText((tr('Corps remis comme l\'ensemble') if reset else
                           tr('Corps positionné à part : {0}, rotation {1}°').format(
                               tr(P3.face_label(placement.face)), f'{placement.rot:g}'.replace('.', ',')))
                          + self._outdated_note(getattr(self.win, 'cam_panel', None)))
        return None if reset else placement

    def rest_on_selection(self, up: bool = False):
        """La pièce posée sur la face plane choisie (usiner le dessus) — ou,
        `up`, cette face tournée vers l'outil —, alignée sur les axes ; rend
        le placement appliqué (None : pas une seule face plane)."""
        import numpy as np
        from ..cam import mill3d
        from ..core import placement3d as P3
        v = self.view
        src = self._model_source()
        if v.model is None or len(v.sel_faces) != 1 or src is None:
            self.info.setText(tr('Choisir une seule face plane de la pièce'))
            return None
        t = np.asarray(v.model.triangles, dtype=np.float64)[v.selected_triangles()]
        cr = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
        area, s = 0.5 * float(np.linalg.norm(cr, axis=1).sum()), 0.5 * cr.sum(axis=0)
        if area <= 0 or np.linalg.norm(s) < area * math.cos(math.radians(1.0)):
            self.info.setText(tr('Face non plane : choisir une face plane'))
            return None
        from ..core import surface2d
        n = surface2d.outward_normal(v.model, v.selected_triangles())    # maillage retourné : vers le dehors
        doc = self.win.canvas.doc
        face, body = self.current_setup()
        shown = (mill3d.side_placement(doc, src, face, body) if (face, body) != ('', -1) else P3.of(doc)) \
            or P3.Placement()
        R = shown.rotation()
        key = P3.face_for_rest(-(R.T @ n) if up else R.T @ n)          # repère de la pièce redressée
        raw = (t.reshape(-1, 3) - np.array([shown.dx, shown.dy, 0.0])) @ R
        rot = P3.align_rot(raw @ P3.face_matrix(key).T)
        cur = P3.of(doc)
        return self.win.place_model3d(placement=P3.Placement(key, rot, cur.mode, cur.dx, cur.dy))

    def _stock_lines(self, m):
        """Arêtes du brut du réglage FAO autour de la pièce montrée, ou None."""
        cp = getattr(self.win, 'cam_panel', None)
        if cp is None or m is None or not len(getattr(m, 'triangles', ())):
            return None
        from ..core import stock3d
        box = stock3d.box_for(self.win.canvas.doc, cp.setup(), m)
        return stock_edges(box, float(m.bounds()[5])) if box is not None else None

    def show_stock(self) -> None:
        """Brut changé : ses arêtes redessinées autour de la pièce montrée."""
        self.view.stock_lines = self._stock_lines(self.view.model)
        self.view._dirty = True
        self.view.update()

    def _fixture(self, m):
        """Matériel de l'espace de travail de la prise montrée autour de la
        pièce (une pièce retournée a le sien, ou aucun)."""
        if m is None or not len(getattr(m, 'triangles', ())):
            return None, None
        from ..core import workspace as WS
        ws = WS.of(self.win.canvas.doc, *self.current_setup())
        return fixture_arrays(ws, float(m.bounds()[5])) if ws.elements else (None, None)

    def show_workspace(self) -> None:
        """Espace de travail changé : matériel redessiné."""
        self.view.fixture = self._fixture(self.view.model)
        self.view._dirty = True
        self.view.update()

    def auto3d(self, exec_dialog: bool = True, sequence: str = ''):
        """Automatisme d'usinage 3D sur la sélection (sinon toute la pièce) :
        sa fenêtre, puis les opérations créées ; rend la fenêtre (sans
        l'ouvrir si `exec_dialog` est faux) ou les opérations."""
        from .auto3d_dialog import Auto3DDialog
        cp = getattr(self.win, 'cam_panel', None)
        src = self.machining_path()
        if cp is None or src is None or self.view.model is None:
            return None
        v = self.view
        whole = not (v.sel_faces or v.sel_loops)
        from ..cam import mill3d
        raw = mill3d.raw_model(src) if src else None      # prises (faces vers l'outil) : de la pièce telle que lue
        face, body = self.current_setup()                 # prise de l'onglet (corps seul, pièce retournée) : elle seule
        setup = None if self.all_setups() or (face, body) == ('', -1) else (face, body)
        dlg = Auto3DDialog(self, cp, v.model, model_path='', faces=sorted(v.sel_faces),     # '' : la pièce du dessin
                           loops=self.loops_in_drawing(), depth=0.0 if whole else self.selection_depth(),
                           sides_model=raw, setup=setup, view_loops=[L.tolist() for L in v.sel_loops])
        if sequence:
            i = dlg.choice.findData(sequence)
            if i >= 0:
                dlg.choice.setCurrentIndex(i)
        if not exec_dialog:
            return dlg
        ok = dlg.exec()
        if ok:
            dlg._replan()
        planned = dlg.planned if ok else []
        dlg.deleteLater()                                # fenêtre libérée (les étapes planifiées gardées)
        if not ok:
            return None
        ops = cp.apply_auto3d(planned)
        self._fill_setups(self._model_source())          # les prises créées se choisissent tout de suite
        self.ops_list.show_ops(ops)                      # à modifier, supprimer : la liste des usinages
        return ops

    # --- liste « Usinages » (ruban FAO 3D, groupe « Usinages ») ----------------------------
    def ops_toggle(self, on: bool) -> None:
        self.ops_list.toggle(on)

    def ops_command(self, what: str, *args):
        return getattr(self.ops_list, what)(*args)

    def surface_to_layer(self):
        """Faces choisies → sous-onglet « surface 2D » : la prise qui les tourne
        vers l'outil, leur contour dans un nouveau calque (actif) ; rend le
        calque (None : rien de posé)."""
        from ..core import surface2d
        v = self.view
        path = self.machining_path()
        if path is None or not v.sel_faces:
            self.info.setText(tr('Choisir une ou plusieurs faces de la pièce'))
            return None
        from ..core import placement3d as P3
        doc = self.win.canvas.doc
        body = self.selected_body() if path else None    # corps montré seul, ou positionné à part : sa prise
        if body is None or (self.current_setup()[1] < 0 and P3.body_of(doc, body) is None):
            body = -1
        info = surface2d.pose(doc, path, sorted(v.sel_faces), body)
        if info is None:
            self.info.setText(tr('Faces d\'orientations trop différentes : choisir une face, ou des faces tournées '
                                 'du même côté'))
            return None
        if info.get('down'):
            self.info.setText(tr('Cette face ne se tourne pas vers l\'outil : le maillage du fichier est '
                                 'incohérent à cet endroit (faces ouvertes ou retournées)'))
            return None
        self.win.push_undo(tr('Surface posée en 2D'))
        L = surface2d.add_layer(doc, info)
        self.win._on_doc_changed()
        msg = tr('Surface posée sur le calque « {0} » : prise {1}, face à Z {2} mm').format(
            L.name, surface2d.label(doc, info), f'{info["z"]:g}'.replace('.', ','))
        if info['flat'] > surface2d.FLAT_TOL:
            msg += ' — ' + tr('surface non plane (écart {0} mm) : le dessin y est vu à plat').format(
                f'{info["flat"]:g}'.replace('.', ','))
        self.info.setText(msg)
        self.win.statusBar().showMessage(msg, 10000)
        return L

    def contours_to_drawing(self, pocket: bool = False, exec_dialog: bool = True) -> list:
        """Contours fermés de la sélection → formes du dessin (vue de
        dessus) ; `pocket` : et une poche jusqu'à la profondeur du fond."""
        from ..core import geom
        from ..core.document import Shape
        loops = self.selection_loops()
        if not loops:
            return []
        doc = self.win.canvas.doc
        tool = doc.active_layer.tool if getattr(doc, 'active_layer', None) is not None else 0
        shapes = []
        for L in loops:
            pts = [(float(p[0]), float(p[1])) for p in L[:-1]]
            if len(pts) >= 3:
                sh = Shape(path=geom.Path([geom.polyline(pts, closed=True)]), tool=tool)
                sh.extra['contour3d'] = True
                shapes.append(sh)
        if not shapes:
            return []
        depth = self.selection_depth()
        self.win._add_items(shapes)
        if pocket:
            cp = getattr(self.win, 'cam_panel', None)
            if cp is not None:
                cp.add_pocket(shapes, depth, tr('Poche jusqu\'au fond (Z −{0})').format(
                    f'{depth:.2f}'.rstrip('0').rstrip('.')), exec_dialog=exec_dialog)
        self.win.statusBar().showMessage(tr('{0} contour(s) ajouté(s) au dessin').format(len(shapes)), 5000)
        return shapes

    def holes_to_drilling(self, exec_dialog: bool = False) -> tuple[list, list]:
        """Trous verticaux de la pièce (posée comme le dessin) : un cercle par
        trou dans un calque « Trous 3D », un perçage par diamètre (à la
        profondeur du plus profond) ; rend (cercles, opérations)."""
        from ..core import geom, holes3d
        from ..core.document import Shape
        cp = getattr(self.win, 'cam_panel', None)
        model = self.view.model
        if cp is None or model is None:
            return [], []
        holes = holes3d.find(model)
        if not holes:
            self.win.statusBar().showMessage(tr('Aucun trou vertical complet dans cette pièce'), 6000)
            return [], []
        tool = getattr(self.win.canvas, 'current_tool_index', 0)
        circles, by_d = [], {}
        for h in holes:
            sh = Shape(path=geom.Path([geom.circle((h.x, h.y), h.radius)]), tool=tool,
                       name=tr('Trou Ø{0}').format(f'{h.diameter:g}'.replace('.', ',')))
            sh.extra['trou3d'] = {'diametre': h.diameter, 'profondeur': h.depth, 'debouchant': h.through}
            circles.append(sh)
            by_d.setdefault((round(h.diameter, 3), round(h.depth, 2), h.through), []).append((sh, h))
        self.win._add_items(circles)
        ops = []
        for (d, _depth, _thr), pairs in sorted(by_d.items(), reverse=True):
            depth = max(h.depth + (THROUGH_EXTRA if h.through else 0.0) for _s, h in pairs)   # débouchant : un peu plus
            label = tr('Perçage Ø{0} ({1} trou(s), {2} mm)').format(f'{d:g}'.replace('.', ','), len(pairs),
                                                                     f'{depth:g}'.replace('.', ','))
            o = cp.add_drilling([s for s, _h in pairs], depth, d, label, exec_dialog=exec_dialog)
            if o is not None:
                ops.append(o)
        self.win.statusBar().showMessage(tr('{0} trou(s), {1} perçage(s)').format(len(holes), len(ops)), 6000)
        return circles, ops

    def replace_zone(self, op_id: str) -> bool:
        if not self._has_selection():                     # jamais une zone vidée sans le dire
            return False
        cp = getattr(self.win, 'cam_panel', None)
        v = self.view
        return bool(cp) and cp.set_op_zone(op_id, sorted(v.sel_faces), self.loops_in_drawing())

    def show_zone(self, op) -> None:
        """La zone d'une opération 3D devient la sélection de la vue."""
        mode = 'contours' if op.contours3d and not op.faces3d else 'faces'
        i = self.select.findData(mode)
        self.select.blockSignals(True)
        self.select.setCurrentIndex(i)
        self.select.blockSignals(False)
        self._sync_actions()
        self.view.select_mode = mode
        self.view.set_selection(faces=op.faces3d, loops=self._zone_loops_shown(op))

    def _zone_loops_shown(self, op) -> list:
        """Contours de la zone de `op` dans la prise montrée (gardés dans le
        repère de la pièce posée comme le dessin quand ils ont été choisis) :
        « Remplacer la zone » les ramène ensuite tels quels."""
        loops = list(op.contours3d or [])
        if not loops or self._model_source() is None:
            return loops
        import copy
        from ..cam import mill3d
        c = copy.copy(op)
        c.setup_face, c.body3d = self.current_setup()
        return [list(L) for L in mill3d.zone_op(self.win.canvas.doc, c).contours3d]

    def _finesse_changed(self) -> None:
        st = getattr(self.win, 'settings', None)
        if st is not None:
            st.setValue(FINESSE_KEY, self.finesse.currentData())
        if self.model is None:                           # relief ou simulation : recalculés à la finesse choisie
            self.refresh()

    def set_colors(self, part=..., edge=...) -> None:
        """Couleur de la pièce et/ou des arêtes ((r, g, b) entre 0 et 1, None :
        d'origine), retenues dans les réglages ; vue redessinée."""
        st = getattr(self.win, 'settings', None)
        for name, key, rgb in (('part_color', PART_COLOR_KEY, part), ('edge_color', EDGE_COLOR_KEY, edge)):
            if rgb is ...:
                continue
            setattr(self.view, name, tuple(rgb) if rgb is not None else None)
            if st is not None:
                st.setValue(key, hex_of(rgb))
        self.view._dirty = True
        self.view.update()

    def choose_color(self, which: str) -> None:
        """Couleur de la pièce ('part') ou des arêtes ('edge') choisie au nuancier."""
        from PySide6.QtWidgets import QColorDialog
        v = self.view
        cur = v.part_color if which == 'part' else (v.edge_color or edge_for(v._background()))
        if cur is None and v.model is not None and len(v.model.colors):
            import numpy as np
            cur = tuple(np.asarray(v.model.colors, np.float32).reshape(-1, 3)[0])
        start = QColor.fromRgbF(*cur) if cur is not None else QColor('#b3bdcc')
        c = QColorDialog.getColor(start, self, tr('Couleur de la pièce') if which == 'part'
                                  else tr('Couleur des arêtes'))
        if c.isValid():
            rgb = (c.redF(), c.greenF(), c.blueF())
            self.set_colors(**({'part': rgb} if which == 'part' else {'edge': rgb}))

    def reset_colors(self) -> None:
        """Couleurs du fichier, arêtes selon le fond."""
        self.set_colors(part=None, edge=None)

    def _set_view_flag(self, name: str, on, upload: bool = True, as_bool: bool = True) -> None:
        setattr(self.view, name, bool(on) if as_bool else on)
        if upload:
            self.view._dirty = True
        self.view.update()

    def export_image(self, path: str | None = None) -> str | None:
        """La vue 3D en image ; rend le chemin écrit."""
        if path is None:
            from PySide6.QtWidgets import QFileDialog
            path, _ = QFileDialog.getSaveFileName(self, tr('Image de la vue 3D'), 'vue3d.png',
                                                  tr('Images (*.png *.jpg)'))
            if not path:
                return None
        return path if self.view.save_image(path) else None

    def set_source(self, key: str) -> None:
        """Source du relief choisie (relief recalculé) : 'parcours', 'simulation'…"""
        i = self.source.findData(key)
        if i >= 0:
            self.source.blockSignals(True)
            self.source.setCurrentIndex(i)
            self.source.blockSignals(False)
        if key in ('parcours', 'simulation') and not self.paths.isChecked():
            self.paths.setChecked(True)
        self.refresh()

    def _computed_paths(self) -> list:
        """Parcours du panneau FAO : les cochés, ceux que le programme
        écrirait — aucun s'ils datent d'avant un changement du dessin (la vue
        ne recalcule pas : « Calculer ») —, sinon tous ; calculés au besoin."""
        cp = getattr(self.win, 'cam_panel', None)
        if cp is None:
            return []
        if cp.checked_paths():
            return self._checked_paths(cp)
        tps = list(cp.toolpaths)
        if not tps and not self._active_ops():          # programme ouvert comme dessin : ses trajectoires
            tps = self._program_paths()
        if not tps and not getattr(cp, '_computing', False):
            self._taking = True                         # parcours affichés pendant le calcul : vue faite après
            try:
                tps = cp.compute(dates=False) or []
            finally:
                self._taking = False
        return tps

    def _checked_paths(self, cp, partial: bool = False) -> list:
        """Parcours cochés que le programme écrirait (programme relu, parcours
        TypeEdit : tels quels) ; ceux des opérations ne sont pas montrés s'ils
        datent d'avant un changement du dessin — la vue ne recalcule pas,
        `_outdated_note` le dit — : aucun parcours (simulation), ou seulement
        ceux sans opération (`partial` : trajectoires posées sur la pièce)."""
        mine = cp.checked_paths() if cp is not None else []
        live = cp._writable(mine) if mine else []
        if any(tp.op_id for tp in live) and cp.outdated():
            return [tp for tp in live if not tp.op_id] if partial else []
        return live

    def _outdated_note(self, cp) -> str:
        """Suffixe du texte d'information quand des trajectoires cochées ne
        sont pas montrées (d'avant un changement du dessin, opérations
        désactivées)."""
        mine = cp.checked_paths() if cp is not None else []
        if not mine:
            return ''
        live = cp._writable(mine)
        if not live:
            return ' — ' + tr('trajectoires d\'opérations désactivées : pas montrées')
        if any(tp.op_id for tp in live) and cp.outdated():
            return ' — ' + tr('trajectoires calculées avant un changement du dessin : pas montrées (« Calculer » '
                              'du ruban FAO, ou « Parcours 3D »)')
        return ''

    #: extensions des programmes machine lus par le cœur (les plugins ajoutent les leurs)
    PROGRAM_EXTS = ('.nc', '.iso', '.tap', '.ngc', '.gcode', '.cnc', '.h')

    def _active_ops(self) -> bool:
        from ..cam import model as _M
        return any(o.enabled for o in _M.setup_of(self.win.canvas.doc).operations)

    def _program_paths(self) -> list:
        """Trajectoires du programme machine d'où vient le dessin (un parcours
        par outil), lues une fois par fichier et par date ; [] sinon."""
        import os
        src = getattr(self.win.canvas.doc, 'source_path', None)
        if not src or not os.path.isfile(src):
            return []
        from ..plugins import REGISTRY
        ext = os.path.splitext(src)[1].lower()
        exts = set(self.PROGRAM_EXTS) | {e.lower() for _l, es, _r, _s in REGISTRY.nc_readers for e in es}
        if ext not in exts:
            return []
        key = (src, os.path.getmtime(src))
        cache = getattr(self, '_program_cache', None)
        if cache is None or cache[0] != key:
            from ..cam import ncread
            try:
                with open(src, encoding='utf-8', errors='replace') as f:
                    tp = ncread.read(f.read(), os.path.basename(src), path=src)
            except (OSError, ValueError):
                return []
            parts = list(getattr(tp, 'parts', None) or []) or [tp]
            for p in parts:
                for k in ('stock', 'machine_seconds'):
                    if getattr(tp, k, None) and not getattr(p, k, None):
                        setattr(p, k, getattr(tp, k))
            cache = self._program_cache = (key, [p for p in parts if p.moves])
        return list(cache[1])

    def _rapids(self, on: bool) -> None:
        self.view.show_rapids = on
        self.view._dirty = True
        self.view.update()

    def _paths(self, on: bool) -> None:
        self.view.show_paths = on
        self.view._dirty = True
        self.view.update()

    def machining_path(self) -> str | None:
        """Pièce que les usinages 3D de la vue visent : le fichier 3D du
        dessin, '' pour les volumes du dessin, None s'il n'y en a pas."""
        src = self._model_source()
        if src is not None:
            return src
        return '' if getattr(self, 'volumes_shown', False) and self.view.model is not None else None

    def _model_source(self) -> str | None:
        from ..io import model3d
        key = self.source.currentData() or 'auto'
        if key not in ('auto', 'modele'):
            return None
        return model3d.source_of(self.win.canvas.doc)

    def refresh(self) -> bool:
        """Modèle 3D du fichier, ou relief du dessin courant (barre de
        progression)."""
        from ..cam import relief as RL
        from .progress import Cancelled, run
        if getattr(self, '_taking', False):              # parcours calculés pour cette vue : elle se fait ensuite
            self.stale = True
            return False
        doc = self.win.canvas.doc
        src = self._model_source()
        for w in (self.exag, self.fill):
            w.setEnabled(src is None)
        self.place.setVisible(src is not None)
        self._fill_setups(src)
        if src is not None:
            return self._show_model(src)
        key = self.source.currentData() or 'auto'
        if key in ('auto', 'volumes'):
            from ..core import solids as SO
            vols = SO.doc_solids(doc) if SO.available() else []
            if vols or key == 'volumes':
                return self._show_solids([s for _it, s in vols])
        if (self.source.currentData() or 'auto') == 'modele':
            self.view.set_model(None)
            self.model = None
            self.stale = False
            self.info.setText(tr('Ce dessin ne vient pas d\'un fichier 3D (STEP, STL, 3D XML)'))
            return False
        key = self.source.currentData() or 'auto'
        if key == 'auto' and not self._active_ops() and self._program_paths():
            key = 'parcours'                             # programme ouvert comme dessin : ses trajectoires
        if key in ('parcours', 'simulation'):
            extra = {'toolpaths': self._computed_paths()}
            cp = getattr(self.win, 'cam_panel', None)
            if not extra['toolpaths'] and cp is not None and cp.checked_paths():
                self.info.setText(tr('Aucun parcours à montrer : les parcours cochés sont ceux d\'opérations '
                                     'désactivées ou supprimées depuis le calcul')
                                  if not cp._writable(cp.checked_paths()) else
                                  tr('Aucun parcours à montrer : parcours calculés avant un changement du dessin '
                                     '(pièce 3D placée autrement, surface posée, session reprise) ; « Calculer » '
                                     'dans le ruban FAO'))
                self.view.set_relief(None)
                self.player.load([])
                self.relief, self.model, self.stale = None, None, False
                return False
        else:
            extra = {'fill_closed': self.fill.isChecked()}
        _label, cells, side = FINESSE.get(self.finesse.currentData(), FINESSE['normale'])
        extra['max_cells'] = cells
        self.view.max_side = side
        try:
            r = run(self.win, tr('Vue 3D'), RL.build, doc, key, **extra)
        except Cancelled:
            self.info.setText(tr('Calcul annulé'))
            return False
        self.relief = r
        self.model = None
        self.stale = False
        from ..cam import model as _M
        self.view.setup = _M.setup_of(doc)              # avances du réglage : temps de la légende
        self.view.set_relief(r)
        self.player.load(r.toolpaths or [], r)          # lecture pas à pas des parcours
        src = {'fao': tr('parcours FAO simulés'), 'simulation': tr('parcours FAO calculés, simulés'),
               'parcours': tr('trajectoires FAO calculées')}.get(r.source, tr('dessin'))
        self.info.setText(tr('{0} — profondeur maxi {1:.3f} mm — volume enlevé {2:.1f} mm³ — pas {3:.3f} mm')
                          .format(src, -r.sim.deepest if r.sim.deepest < 0 else 0.0, r.sim.removed, r.sim.res)
                          + (' — ' + '; '.join(tr(w) for w in r.warnings) if r.warnings else ''))
        return True

    def _show_solids(self, solids: list) -> bool:
        """Les volumes du dessin ; la caméra reste où elle est quand ils
        changent (elle ne se recadre qu'à leur première apparition)."""
        from ..core import solids as SO
        for w in (self.exag, self.fill):
            w.setEnabled(False)
        self.place.setVisible(False)
        m = SO.to_model(solids) if solids else None
        self.stale = False
        self.relief = None
        self._model_key = None
        self.volumes_shown = m is not None              # les volumes se choisissent et s'usinent comme une pièce
        if m is None:
            self.model = None
            self.view.set_model(None)
            self.info.setText(tr('Aucun volume dans ce dessin (ruban 3D : Pavé, Extrusion…)'))
            return False
        first = self.view.model is None
        self.model = m
        if first:
            self.view.set_model(m)
        else:
            self.view.model, self.view.relief = m, None
        cp = getattr(self.win, 'cam_panel', None)             # trajectoires calculées, sur les volumes
        paths = self._checked_paths(cp, partial=True)
        if cp is not None:                                     # volumes : une seule vue, prises recomposées
            paths = self._reassembled(paths)
        self.view.model_paths = paths
        self.view.model_dz = float(m.bounds()[5])
        self.view.stock_lines = self._stock_lines(m)
        self.view.fixture = self._fixture(m)
        self.player.load(self.view.model_paths)
        self.view._dirty = True
        self.view.update()
        vol = sum(s.volume() for s in solids)
        self.info.setText(tr('{0} volume(s) — {1} triangles — {2:.1f} mm³').format(len(solids), len(m.triangles), vol)
                          + self._outdated_note(cp))
        return True

    def setup_groups(self) -> list:
        """Prises des usinages du réglage (3D, et 2D d'une surface posée) :
        [(face, corps)] dans l'ordre des opérations ; ('', -1) : la pièce comme
        le dessin."""
        from ..core import workspace as WS
        cp = getattr(self.win, 'cam_panel', None)
        doc = self.win.canvas.doc
        out = []
        for o in (cp.setup().operations if cp is not None else []):
            if o.kind == 'instruction':
                continue
            g = WS.op_setup(o, doc)                        # face du dessin écrite : ramenée à ''
            if g != ('', -1) and g not in out:
                out.append(g)
        from ..core import placement3d as P3
        for k in sorted((doc.extra.get(P3.KEY_BODIES) or {}), key=lambda s: int(s) if s.lstrip('-').isdigit() else 0):
            g = ('', int(k)) if k.lstrip('-').isdigit() else None
            if g is not None and g not in out and not any(b == g[1] for _f, b in out):
                out.append(g)                              # corps positionné à part : sa prise, même sans usinage
        for g in WS.extra_setups(doc):                     # ajoutées à la main, bridées : même sans usinage
            if g not in out:
                out.append(g)
        return out

    def _fill_setups(self, src) -> None:
        from ..cam.auto3d import SIDE_LABELS
        cur = self.setup_view.currentData()
        groups = self.setup_groups() if src is not None else []
        names = self._body_names(src)
        if len(names) > 1:                               # chaque corps a son onglet, même sans usinage
            groups += [('', b) for b in range(len(names)) if ('', b) not in groups]
        self.setup_view.blockSignals(True)
        self.setup_view.clear()
        self.setup_view.addItem(tr('Prise : comme le dessin'), '|-1')
        for face, body in groups:
            name = (names[body] if body < len(names) else f'Corps {body + 1}') if body >= 0 else ''
            side = tr(SIDE_LABELS.get(face, face)) if face else tr(SIDE_LABELS[''])   # '' : face du dessin
            bits = [b for b in (name, side) if b]
            self.setup_view.addItem(tr('Prise : {0}').format(', '.join(bits)), f'{face}|{body}')   # clé texte
        if groups:
            self.setup_view.addItem(tr('Prises : toutes (trajectoires recomposées)'), ALL_SETUPS)
        i = self.setup_view.findData(cur) if cur is not None else 0
        if i < 0 and cur not in (None, ALL_SETUPS):       # prise disparue (annulée…) : la première de sa pièce
            i = self.setup_view.findData('|' + str(cur).partition('|')[2])
        self.setup_view.setCurrentIndex(max(0, i))
        self.setup_view.blockSignals(False)
        if src is not None and self.setup_view.currentData() != cur:
            self._setup_memory()[self.current_part()] = self.setup_view.currentData()
        self._sync_tabs(src)
        self.ops_list.fill()                             # usinages de la prise montrée

    def _body_names(self, src) -> list:
        """Noms des corps de la pièce du fichier `src`, déjà lue (rien n'est lu
        ici, sans barre de progression) ; [] : pas encore lue, ou pas de pièce."""
        import os
        from ..cam import mill3d
        if not src:
            return []
        try:
            fk = (os.path.normcase(os.path.abspath(src)), os.path.getmtime(src))
        except OSError:
            return []
        known = getattr(self, '_names', {})
        if fk in known:                                    # retenus quand la pièce a été lue
            return known[fk]
        m = mill3d.cached_raw_model(src)
        key = self._model_key
        if m is None and self.model is not None and key and tuple(key[:2]) == fk and key[4] < 0:
            m = self.model                                 # la pièce entière montrée : les mêmes corps
        if m is None:
            return []
        self._names = {fk: [m.body_name(b) for b in range(m.body_count())]}   # la pièce montrée seule
        return self._names[fk]

    def _setup_memory(self) -> dict:
        """Dernière prise montrée de chaque pièce, pour le document courant."""
        import weakref
        doc = self.win.canvas.doc
        ref = getattr(self, '_memory_doc', None)
        if ref is None or ref() is not doc:
            self._memory_doc = weakref.ref(doc)
            self._last_setup = {}
        return self._last_setup

    # --- onglets « Pièce » et « Prise » ------------------------------------------------------
    def _parts_bar(self) -> QWidget:
        """Onglets « Pièce » (l'ensemble, chaque corps d'une pièce à plusieurs
        corps) et « Prise » de la pièce choisie (une par position, par
        bridage : les reprises), avec ce qui se règle pour elle."""
        from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QMenu, QTabBar
        from .flow import ElideLabel
        w = QWidget(self)
        g = QGridLayout(w)
        g.setContentsMargins(6, 0, 6, 2)
        g.setHorizontalSpacing(6)
        g.setVerticalSpacing(0)
        self._syncing = False
        self._tab_keys = {'part': [], 'setup': []}
        self._last_setup: dict = {}

        def tabs():
            t = QTabBar(w)
            t.setExpanding(False)
            t.setUsesScrollButtons(True)
            t.setDrawBase(False)
            t.setElideMode(Qt.TextElideMode.ElideNone)
            return t
        self.part_label = QLabel(tr('Pièce'))
        self.part_tabs = tabs()
        self.part_tabs.setToolTip(tr('L\'ensemble, ou un corps de la pièce : posé, bridé et usiné à part'))
        self.part_tabs.currentChanged.connect(lambda _i: self._part_tab_changed())
        g.addWidget(self.part_label, 0, 0)
        g.addWidget(self.part_tabs, 0, 1, 1, 3, Qt.AlignmentFlag.AlignLeft)
        self.setup_tabs = tabs()
        self.setup_tabs.setToolTip(tr('Prises (reprises) de la pièce choisie : posée et bridée autrement pour usiner '
                                      'd\'autres faces ; double clic : bridage ; clic droit : bridage, retirer'))
        self.setup_tabs.currentChanged.connect(lambda _i: self._setup_tab_changed())
        self.setup_tabs.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.setup_tabs.customContextMenuRequested.connect(self._setup_tab_menu)
        self.setup_tabs.tabBarDoubleClicked.connect(lambda i: self.clamping() if i >= 0 else None)
        g.addWidget(QLabel(tr('Prise')), 1, 0)
        g.addWidget(self.setup_tabs, 1, 1)
        self.add_btn = QToolButton(w)
        self.add_btn.setText(tr('+ Prise'))
        self.add_btn.setToolTip(tr('Nouvelle prise de la pièce choisie : une autre face vers l\'outil (pièce '
                                   'retournée, sur le côté), à brider et usiner'))
        self.add_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.add_menu = QMenu(self.add_btn)
        self.add_menu.aboutToShow.connect(self._fill_add_menu)
        self.add_btn.setMenu(self.add_menu)
        g.addWidget(self.add_btn, 1, 2)
        self.setup_note = ElideLabel('')
        g.addWidget(self.setup_note, 1, 3)
        g.setColumnStretch(3, 1)
        row = QHBoxLayout()
        row.setSpacing(4)
        self.place = QPushButton(tr('Placer…'))
        self.place.clicked.connect(lambda _=False: self.place_part())
        row.addWidget(self.place)
        self.clamp_btn = QPushButton(tr('Bridage…'))
        self.clamp_btn.setToolTip(tr('Étau, mandrin, brides, cales de la prise montrée (la sienne : une pièce '
                                     'retournée, un corps posé à part sont tenus autrement)'))
        self.clamp_btn.clicked.connect(lambda _=False: self.clamping())
        row.addWidget(self.clamp_btn)
        b = QPushButton(tr('Brut…'))
        b.setToolTip(tr('Bloc, barre ronde ou plaque d\'où la pièce est usinée'))
        b.clicked.connect(lambda _=False: self.stock())
        row.addWidget(b)
        self.auto_btn = QPushButton(tr('Automatisme…'))
        self.auto_btn.setToolTip(tr('Automatisme d\'usinage 3D dans la prise montrée : toute la pièce (ou le corps), '
                                    'ou les faces et contours choisis'))
        self.auto_btn.clicked.connect(lambda _=False: self.auto3d())
        row.addWidget(self.auto_btn)
        g.addLayout(row, 1, 4)
        w.setVisible(False)
        return w

    def current_part(self) -> int:
        """Pièce de l'onglet choisi : -1 l'ensemble, sinon le corps."""
        return -1 if self.all_setups() else self.current_setup()[1]

    def _side_text(self, face: str) -> str:
        from ..cam.auto3d import SIDE_LABELS
        from ..core import placement3d as P3
        t = tr(SIDE_LABELS[face]) if face in SIDE_LABELS else tr(P3.face_label(face))
        return t[:1].upper() + t[1:]

    def _setup_tab_text(self, key, doc, count: dict) -> str:
        from ..core import placement3d as P3
        if key == ALL_SETUPS:
            return tr('Toutes (recomposées)')
        face, _s, body = str(key).partition('|')
        body = int(body or -1)
        text = self._side_text(face) if face else tr('Comme le dessin') if body < 0 else \
            tr('Posé à part') if P3.body_of(doc, body) is not None else tr('Comme l\'ensemble')
        c = count.get((face, body), 0)
        return text + (f' ({c})' if c else '')

    def _set_tabs(self, bar, kind: str, keys: list, labels: list, current, tips=()) -> None:
        if self._tab_keys[kind] != keys or [bar.tabText(i) for i in range(bar.count())] != labels:
            while bar.count():
                bar.removeTab(0)
            for text in labels:
                bar.addTab(text)
            self._tab_keys[kind] = list(keys)
        for i, tip in enumerate(tips):
            bar.setTabToolTip(i, tip)
        i = keys.index(current) if current in keys else 0
        if bar.currentIndex() != i:
            bar.setCurrentIndex(i)

    def _sync_tabs(self, src) -> None:
        """Onglets d'après la liste des prises : la pièce et la prise montrées
        choisies ; la ligne de la prise (usinages, bridage)."""
        from ..core import workspace as WS
        if src is None:
            self.parts.setVisible(False)
            return
        doc = self.win.canvas.doc
        names = self._body_names(src)
        keys = [self.setup_view.itemData(i) for i in range(self.setup_view.count())]
        bodies = set(range(len(names))) if len(names) > 1 else set()
        bodies |= {int(str(k).partition('|')[2] or -1) for k in keys if k != ALL_SETUPS}   # et ceux des prises
        parts = [(-1, tr('Ensemble'))] + [(b, names[b] if b < len(names) else f'Corps {b + 1}')
                                          for b in sorted(bodies - {-1})]
        part = self.current_part()
        cp = getattr(self.win, 'cam_panel', None)
        count: dict = {}
        for o in (cp.setup().operations if cp is not None else []):
            if o.kind != 'instruction':
                g = WS.op_setup(o, doc)
                count[g] = count.get(g, 0) + 1
        mine = [k for k in keys if (part < 0 if k == ALL_SETUPS else int(str(k).partition('|')[2] or -1) == part)]
        mine.sort(key=lambda k: (k == ALL_SETUPS, k != ALL_SETUPS and bool(str(k).partition('|')[0])))
        labels, tips = [], []
        for n, k in enumerate(mine, 1):
            text = self._setup_tab_text(k, doc, count)
            labels.append(text if k == ALL_SETUPS else f'{n}. {text}')
            if k == ALL_SETUPS:
                tips.append(tr('La pièce comme le dessin, les trajectoires de chaque prise et de chaque corps '
                               'recomposées sur elle'))
            else:
                face, _s, body = str(k).partition('|')
                tips.append(tr('{0} usinage(s) dans cette prise').format(count.get((face, int(body or -1)), 0)))
        self._syncing = True
        try:
            self._set_tabs(self.part_tabs, 'part', [b for b, _n in parts], [t for _b, t in parts], part)
            self._set_tabs(self.setup_tabs, 'setup', mine, labels, self.setup_view.currentData(), tips)
        finally:
            self._syncing = False
        self.part_label.setVisible(len(parts) > 1)
        self.part_tabs.setVisible(len(parts) > 1)
        self.parts.setVisible(True)
        self.place.setToolTip(tr('Pièce 3D : face tournée vers l\'outil, rotation, position sur la plaque')
                              if part < 0 else tr('Ce corps posé à part pour son usinage : face vers l\'outil, '
                                                  'rotation, position'))
        if self.all_setups():
            self.setup_note.setText('')
            return
        ws = WS.of(doc, *self.current_setup())
        k = WS.clamping(ws) if ws.elements else -1
        self.setup_note.setText(tr('Bridage : aucun') if not ws.elements else
                                tr('Bridage : « {0} »').format(ws.elements[k].label()) if k >= 0 else
                                tr('Bridage : {0} élément(s)').format(len(ws.elements)))

    def _part_tab_changed(self) -> None:
        if self._syncing:
            return
        i, keys = self.part_tabs.currentIndex(), self._tab_keys['part']
        if not 0 <= i < len(keys):
            return
        part = keys[i]
        want = self._setup_memory().get(part)             # la prise montrée la dernière fois pour cette pièce
        j = self.setup_view.findData(want) if want is not None else -1
        if j < 0:
            j = self.setup_view.findData(f'|{part}')
        if j >= 0 and j != self.setup_view.currentIndex():
            self.setup_view.setCurrentIndex(j)
            if self.view.model is not None:
                self.view.fit()                            # l'autre pièce (un corps seul, l'ensemble) cadrée
        else:
            self._sync_tabs(self._model_source())

    def _setup_tab_changed(self) -> None:
        if self._syncing:
            return
        i, keys = self.setup_tabs.currentIndex(), self._tab_keys['setup']
        j = self.setup_view.findData(keys[i]) if 0 <= i < len(keys) else -1
        if j >= 0:
            self.setup_view.setCurrentIndex(j)

    def _used_setups(self) -> set:
        from ..core import workspace as WS
        cp = getattr(self.win, 'cam_panel', None)
        doc = self.win.canvas.doc
        return {WS.op_setup(o, doc) for o in (cp.setup().operations if cp is not None else [])
                if o.kind != 'instruction'}

    def removable(self, face: str, body: int) -> bool:
        """Prise ajoutée à la main (ou bridée), sans usinage : elle se retire."""
        from ..core import workspace as WS
        g = (face or '', int(body))
        return bool(g[0]) and g in WS.extra_setups(self.win.canvas.doc) and g not in self._used_setups()

    def _setup_tab_menu(self, pos) -> None:
        from PySide6.QtWidgets import QMenu
        i = self.setup_tabs.tabAt(pos)
        keys = self._tab_keys['setup']
        if not 0 <= i < len(keys):
            return
        if i != self.setup_tabs.currentIndex():
            self.setup_tabs.setCurrentIndex(i)            # la prise montrée
        key = keys[i]
        face, _s, body = str(key).partition('|')
        m = QMenu(self)
        m.addAction(tr('Bridage…'), lambda: self.clamping())
        m.addAction(tr('Automatisme d\'usinage 3D…'), lambda: self.auto3d())
        m.addSeparator()
        a = m.addAction(tr('Retirer cette prise'), lambda: self.remove_setup(face, int(body or -1)))
        a.setEnabled(key != ALL_SETUPS and self.removable(face, int(body or -1)))
        m.exec(self.setup_tabs.mapToGlobal(pos))
        m.deleteLater()

    def _fill_add_menu(self) -> None:
        from ..core import access3d
        from ..core import workspace as WS
        m = self.add_menu
        m.clear()
        src = self._model_source()
        if src is None:
            return
        doc, part = self.win.canvas.doc, self.current_part()
        for s in access3d.SIDES:
            key = WS.setup_key(WS.norm_face(doc, s, src, part), part)
            a = m.addAction(self._side_text(s) + (tr(' (déjà là)') if self.setup_view.findData(key) >= 0 else ''),
                            lambda s=s: self.add_setup(s))
            a.setEnabled(self.setup_view.findData(key) < 0)

    def add_setup(self, face: str):
        """Nouvelle prise de la pièce choisie : `face` vers l'outil, gardée
        avec le dessin et montrée tout de suite (son onglet), à brider et
        usiner ; rend (face, corps) — face du dessin : ''."""
        from ..core import workspace as WS
        src = self._model_source()
        if src is None:
            return None
        doc, part = self.win.canvas.doc, self.current_part()
        face = WS.norm_face(doc, face or '', src, part)
        key = WS.setup_key(face, part)
        if self.setup_view.findData(key) < 0:
            self.win.push_undo(tr('Ajouter une prise'), keys=(WS.SETUPS_KEY,))
            WS.declare(doc, face, part)
            self.win.modified = True
            self._fill_setups(src)
        i = self.setup_view.findData(key)
        if i >= 0:
            self.setup_view.setCurrentIndex(i)
        return face, part

    def remove_setup(self, face: str, body: int) -> bool:
        """Prise ajoutée à la main retirée, avec son bridage (pas celle d'un
        usinage, ni la première de la pièce) ; False : rien de retiré."""
        from ..core import workspace as WS
        src = self._model_source()
        if src is None or not self.removable(face, body):
            return False
        doc = self.win.canvas.doc
        self.win.push_undo(tr('Retirer une prise'), keys=(WS.SETUPS_KEY, WS.KEY_SETUPS))
        WS.undeclare(doc, face, body)
        self.win.modified = True
        shown = self.setup_view.currentData() == WS.setup_key(face, body)
        self._fill_setups(src)
        if shown:
            i = self.setup_view.findData(f'|{int(body)}')
            if i >= 0 and i != self.setup_view.currentIndex():
                self.setup_view.setCurrentIndex(i)        # la première prise de la même pièce
            else:
                self._setup_view_changed()
        return True

    def place_part(self):
        """« Placer… » de la pièce choisie : l'ensemble comme sur la machine,
        un corps posé à part."""
        part = self.current_part()
        return self.win.place_model3d() if part < 0 else self.place_body(part)

    def clamping(self, exec_dialog: bool = True):
        """Bridage (espace de travail) de la prise montrée ; rend la fenêtre."""
        cp = getattr(self.win, 'cam_panel', None)
        if cp is None:
            return None
        model = self.model if self._model_source() is not None else None
        dlg = cp.workspace_dialog(exec_dialog=exec_dialog, model=model, setup=self.current_setup())
        if exec_dialog:
            self._fill_setups(self._model_source())        # bridée : la prise existe, sa ligne
        return dlg

    def stock(self, exec_dialog: bool = True):
        """Brut de la pièce 3D (pièce montrée : le contrôle autour d'elle) ; rend la fenêtre."""
        cp = getattr(self.win, 'cam_panel', None)
        if cp is None:
            return None
        return cp.stock_dialog(exec_dialog=exec_dialog, model=self.model if self._model_source() is not None
                               else None)

    def current_setup(self) -> tuple:
        """(face vers l'outil, corps) de la prise montrée ; « toutes » : la
        pièce comme le dessin ('', -1)."""
        g = self.setup_view.currentData() or '|-1'
        if g == ALL_SETUPS:
            return '', -1
        face, _s, body = str(g).partition('|')
        return face, int(body or -1)

    def all_setups(self) -> bool:
        """Prise « toutes » : trajectoires de chaque prise recomposées."""
        return self.setup_view.currentData() == ALL_SETUPS

    def _reassembled(self, paths) -> list:
        """Trajectoires de toutes les prises ramenées sur la pièce comme le dessin."""
        from ..cam import reassemble
        cp = getattr(self.win, 'cam_panel', None)
        return reassemble.reassemble(self.win.canvas.doc, paths, cp.setup().operations) if cp is not None else paths

    def _setup_view_changed(self) -> None:
        src = self._model_source()
        self._setup_memory()[self.current_part()] = self.setup_view.currentData()
        if src is not None:
            self.view.clear_selection()
            self._show_model(src)
        self._sync_tabs(src)
        self.ops_list.fill()

    def _show_model(self, path: str) -> bool:
        self.volumes_shown = False
        return self._show_file_model(path)

    def _show_file_model(self, path: str) -> bool:
        """Charge (une fois par fichier et par date) et affiche le modèle 3D —
        posé comme le dessin, ou comme la prise choisie (face vers l'outil,
        corps seul)."""
        import os
        from ..io import model3d
        from .progress import Cancelled, run
        from ..core import placement3d as P3
        doc = self.win.canvas.doc
        pl = P3.of(doc)
        face, body = self.current_setup()
        own = P3.body_of(doc, body)                            # corps posé à part : sa pose, la plaque
        plate = getattr(doc, 'plate', None)
        key = (os.path.normcase(os.path.abspath(path)), os.path.getmtime(path), tuple(P3.to_dict(pl).values()),
               face, body, tuple(P3.to_dict(own).values()) if own is not None else None,
               (plate.x, plate.y, plate.width, plate.height) if plate is not None else None)   # centrée, au coin…
        if self.model is None or self._model_key != key:
            try:
                if (face, body) != ('', -1):
                    from ..cam import mill3d
                    m = run(self.win, tr('Vue 3D'), mill3d.load_model, self.win.canvas.doc, path, face, body)
                else:
                    m = run(self.win, tr('Vue 3D'), model3d.load, path, pl)
            except Cancelled:
                self.info.setText(tr('Chargement annulé'))
                return False
            except Exception as ex:
                self.info.setText(tr('Modèle 3D illisible : {0}').format(ex))
                return False
            self.model, self._model_key = m, key
            self._body_names(path)                         # noms des corps retenus (pièce lue à l'instant)
            self.view.set_model(m)
        elif self.view.model is not self.model:
            self.view.set_model(self.model)
        cp = getattr(self.win, 'cam_panel', None)              # trajectoires calculées, sur la pièce
        paths = self._checked_paths(cp, partial=True)
        if cp is not None and self.all_setups():              # toutes, recomposées sur la pièce
            paths = self._reassembled(paths)
        elif cp is not None and self.setup_view.count() > 1:   # celles de la prise montrée seulement
            from ..core import workspace as WS                 # (2D comprises : surfaces posées, dessin)
            doc = self.win.canvas.doc
            ops = {o.id: o for o in cp.setup().operations}
            face, body = self.current_setup()
            want = (WS.norm_face(doc, face, path, body), body)
            paths = [t for t in paths if WS.op_setup(ops.get(t.op_id), doc) == want]   # sans opération : dessin
        self.view.model_paths = paths
        self.player.load(self.view.model_paths)
        self.view.model_dz = float(self.model.bounds()[5])
        self.view.stock_lines = self._stock_lines(self.model)
        self.view.fixture = self._fixture(self.model)
        self.view._dirty = True
        self.view.update()
        self.stale = False
        self._fill_setups(path)                            # noms des corps, une fois le modèle lu
        if (key[3], key[4]) != self.current_setup() and not getattr(self, '_reshowing', False):
            self._reshowing = True                         # prise disparue de la liste : celle qui la remplace
            try:
                return self._show_file_model(path)
            finally:
                self._reshowing = False
        self.info.setText(tr('Modèle 3D : {0}').format(self.model.summary())
                          + (' — ' + '; '.join(self.model.notes[:2]) if self.model.notes else '')
                          + self._outdated_note(cp))
        return True

    def _fill_bodies_menu(self, m=None) -> None:
        import numpy as np
        m = self.bodies_menu if m is None else m
        m.clear()
        model = self.view.model
        if model is None:
            m.addAction(tr('Aucun corps : pas de pièce 3D')).setEnabled(False)
            return
        counts = np.bincount(model.body_ids(), minlength=model.body_count())
        for b in range(model.body_count()):
            a = m.addAction(tr('{0} ({1} triangles)').format(model.body_name(b), int(counts[b])))
            a.setCheckable(True)
            a.setChecked(b not in self.view.hidden_bodies)
            a.toggled.connect(lambda on, k=b: self.view.set_body_hidden(k, not on))
        m.addSeparator()
        m.addAction(tr('Tout montrer'), self.show_all_bodies)
        m.addAction(tr('Convertir en volumes du dessin'), lambda: self.to_volumes())
        a = m.addAction(tr('Mécanismes et animation…'), lambda: self.mechanisms())
        a.setToolTip(tr('Contacts et liaisons entre les corps (glissière, pivot, appui…), mouvement libre de chacun, '
                        'animation'))
        a = m.addAction(tr('Couleur par corps'))
        a.setCheckable(True)
        a.setChecked(self.view.body_colors)
        a.toggled.connect(lambda on: self.set_body_colors(on))

    def to_volumes(self, show_report: bool = True) -> tuple[list, list]:
        """Corps montrés du modèle 3D → volumes du dessin (maillage réparé) ;
        rend (formes ajoutées, [(corps, raison)] des échecs)."""
        import numpy as np
        from ..core import solids as SO
        from ..core import watertight as WT
        if getattr(self, 'volumes_shown', False):        # volumes du dessin montrés : ils y sont déjà
            self._say(tr('En volumes : la pièce d\'un fichier 3D (STEP, STL, 3D XML) ; les volumes du dessin y sont '
                         'déjà'))
            return [], []
        model = self.view.model
        if model is None or not SO.available():
            return [], []
        bodies = model.body_ids()
        shapes, failed = [], []
        tool = getattr(self.win.canvas, 'current_tool_index', 0)
        for b in range(model.body_count()):
            if b in self.view.hidden_bodies:
                continue
            try:
                s = WT.to_solid(np.asarray(model.triangles)[bodies == b].astype(float), model.body_name(b))
            except SO.SolidError as ex:
                failed.append((model.body_name(b), str(ex)))
                continue
            shapes.append(SO.make_shape(s, tool))
        if shapes:
            self.win._add_items(shapes)
        if show_report:
            msg = tr('{0} corps converti(s) en volumes du dessin').format(len(shapes))
            if failed:
                msg += '\n\n' + tr('Non convertis (maillage du fichier impossible à fermer) :') + '\n' + \
                    '\n'.join(f'• {n} — {r}' for n, r in failed)
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(self, tr('Convertir en volumes'), msg)
        return shapes, failed

    def mechanisms(self, show: bool = True):
        """Fenêtre « Mécanismes » (non modale) ; rend la fenêtre."""
        from .mechanics_dialog import MechanicsDialog
        if self.view.model is None or self.view.model.body_count() < 2:
            self.info.setText(tr('Un seul corps : pas de mécanisme à repérer'))
            return None
        dlg = MechanicsDialog(self)
        if show:
            dlg.show()
        return dlg

    def animate(self):
        """Le bouton Animation : la fenêtre des mécanismes, l'animation lancée s'il y a un mouvement. Rend la fenêtre, None s'il
        n'y a pas plusieurs corps."""
        dlg = self._anim_dlg
        if dlg is None or not dlg.isVisible() or dlg.model is not self.view.model:
            if dlg is not None:
                dlg.close()                              # la pièce revient fermée
            dlg = self._anim_dlg = self.mechanisms()
        if dlg is None:
            return None
        dlg.raise_()
        if dlg.active():
            dlg.play.setChecked(True)
        return dlg

    def show_all_bodies(self) -> None:
        self.view.hidden_bodies = set()
        self.view._dirty = True
        self.view.update()
