"""Round 896 : simulation — une plongée verticale (perçage, débourrage, entrée droite) creuse jusqu'à son point le plus bas : le
trou apparaît, et le retour en rapide dans le trou percé n'est plus signalé comme déplacement rapide dans la matière. Le reste de
la simulation ne change pas (l'impression d'avant est recopiée ici pour comparer).
Relecture des programmes ISO : sans aucun arc tranché (petits arcs loin de l'origine), les centres I J absolus sont reconnus
quand ils suivent bien mieux l'ensemble des arcs — le contrôle du programme écrit ne signale plus d'écart à tort."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', os.path.join(tempfile.mkdtemp(), 'session'))
os.environ.setdefault('VECTORDRIVE_NO_TYPEEDIT', '1')

import numpy as np

from vectordrive.cam import arcfit, ncread, postcheck
from vectordrive.cam import model as M
from vectordrive.cam import simulate as SIM
from vectordrive.cam import strategies as S
from vectordrive.cam.advanced import tool_profile
from vectordrive.core import geom
from vectordrive.core.document import Document, Layer, Plate, Shape


def old_stamp_segment(H, a, b, tool, r, x0, y0, res, top=0.0):
    """L'impression d'avant (round 895) : segment vertical à la cote de son départ."""
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
    else:
        t = np.zeros((len(Y), len(X)))
    d = np.hypot(X - (a[0] + t * vx), Y - (a[1] + t * vy))
    z = a[2] + t * (b[2] - a[2])
    sub = H[j0:j1 + 1, i0:i1 + 1]
    np.minimum(sub, z + tool_profile(tool, d), out=sub)


def fraise(d=2.0, **kw):
    return M.CamTool(name='f', kind='fraise', diameter=d, **kw)


def run(moves, tool, res=0.05):
    setup = M.CamSetup(tools=[tool])
    tp = M.Toolpath(op_id='', tool_id=tool.id, moves=[M.Move(*m) for m in moves])
    return SIM._simulate([tp], setup, res=res, margin=3.0)


def at(sim, x, y):
    i = int(round((x - sim.x0) / sim.res))
    j = int(round((y - sim.y0) / sim.res))
    return float(sim.H[j, i])


class Plongee(unittest.TestCase):

    def test_hole_is_dug(self):
        sim = run([('rapid', 10, 10, 2), ('rapid', 10, 10, 0.5), ('feed', 10, 10, -1.0), ('rapid', 10, 10, 2)], fraise())
        self.assertAlmostEqual(at(sim, 10, 10), -1.0, places=6)                 # avant : 0, rien de creusé
        self.assertAlmostEqual(sim.deepest, -1.0, places=6)
        self.assertAlmostEqual(at(sim, 12.5, 10), 0.0, places=6)               # hors du Ø de l'outil : intact
        self.assertGreater(sim.removed, 0.9 * math.pi * 1.0 * 1.0)             # environ π r² × 1 mm

    def test_peck_return_is_not_a_collision(self):
        moves = [('rapid', 10, 10, 2), ('rapid', 10, 10, 0.5), ('feed', 10, 10, -1.0), ('rapid', 10, 10, 0.5),
                 ('rapid', 10, 10, -0.9), ('feed', 10, 10, -2.0), ('rapid', 10, 10, 2)]
        sim = run(moves, fraise())
        self.assertEqual(sim.rapid_hits, [])                                    # avant : 0,9 mm « dans la matière »
        self.assertAlmostEqual(sim.deepest, -2.0, places=6)

    def test_rapid_into_material_still_found(self):
        sim = run([('rapid', 10, 10, 2), ('rapid', 10, 10, -0.5), ('rapid', 10, 10, 2)], fraise())
        self.assertEqual(len(sim.rapid_hits), 1)
        self.assertAlmostEqual(sim.rapid_hits[0]['depth'], 0.5, places=6)
        moves = [('rapid', 10, 10, 2), ('feed', 10, 10, -1.0), ('rapid', 10, 10, 2), ('rapid', 10, 10, -1.5)]
        sim = run(moves, fraise())                                               # plus bas que le trou percé
        self.assertEqual(len(sim.rapid_hits), 1)
        self.assertAlmostEqual(sim.rapid_hits[0]['depth'], 0.5, places=6)

    def test_drilling_strategy(self):
        doc = Document()
        layer = Layer(name='Plan 1', items=[Shape(path=geom.Path([geom.circle((20 + 15 * k, 20), 1.0)])) for k in range(3)])
        doc.layers[:] = [layer]
        doc.active = layer.id
        doc.plate = Plate(width=80, height=40, thickness=5)
        foret = M.CamTool(name='d', kind='foret', diameter=2.0, number=1)
        setup = M.CamSetup(tools=[foret])
        op = M.Operation(kind='percage', tool_id=foret.id, depth=3.0, peck=1.0)
        setup.operations = [op]
        tp = S.compute(doc, setup, op, (0.0, 0.0))
        self.assertTrue(any(m.kind == 'rapid' and m.z < 0 for m in tp.moves))   # débourrage : retour rapide dans le trou
        sim = SIM._simulate([tp], setup, res=0.05, margin=3.0)
        self.assertEqual(sim.rapid_hits, [])
        for k in range(3):
            self.assertAlmostEqual(at(sim, 20 + 15 * k, 20), -3.0, places=6)

    def test_cone_plunge(self):
        k = M.CamTool(name='k', kind='conique', diameter=3.0, tip=0.0, angle=90.0)
        sim = run([('rapid', 10, 10, 1), ('feed', 10, 10, -0.5), ('rapid', 10, 10, 1)], k)
        self.assertAlmostEqual(at(sim, 10, 10), -0.5, places=6)
        self.assertAlmostEqual(at(sim, 10.25, 10), -0.25, places=6)              # flanc à 45° : 0,25 mm plus haut


class RienDAutre(unittest.TestCase):

    def segments(self):
        rng = np.random.default_rng(896)
        out = []
        for _ in range(60):
            a = (float(rng.uniform(2, 8)), float(rng.uniform(2, 8)), float(rng.uniform(-1.5, 0.3)))
            b = (a[0] + float(rng.uniform(-2, 2)), a[1] + float(rng.uniform(-2, 2)), float(rng.uniform(-1.5, 0.3)))
            out.append((a, b))
        out.append(((5.0, 5.0, -1.0), (5.0, 5.0, 0.2)))                          # vertical, en montant : comme avant
        return out

    def test_same_as_before_except_downward_plunges(self):
        for tool in (fraise(1.0), M.CamTool(name='b', kind='boule', diameter=1.0),
                     M.CamTool(name='k', kind='conique', diameter=2.0, tip=0.1, angle=60.0)):
            r = tool.body_diameter() / 2
            for a, b in self.segments():
                H1 = np.zeros((220, 220))
                H2 = np.zeros((220, 220))
                old_stamp_segment(H1, a, b, tool, r, 0.0, 0.0, 0.05)
                SIM._stamp_segment(H2, a, b, tool, r, 0.0, 0.0, 0.05)
                self.assertTrue(np.array_equal(H1, H2))

    def test_batch_same_as_segment(self):
        tool = fraise(1.0)
        segs = self.segments() + [((4.0, 4.0, 0.5), (4.0, 4.0, -1.2)), ((6.0, 3.0, 0.0), (6.0, 3.0, -0.4))]
        H1 = np.zeros((220, 220))
        H2 = np.zeros((220, 220))
        for a, b in segs:
            SIM._stamp_segment(H1, a, b, tool, 0.5, 0.0, 0.0, 0.05)
        SIM._stamp_batch(H2, [a + b for a, b in segs], tool, 0.5, 0.0, 0.0, 0.05)
        self.assertTrue(np.array_equal(H1, H2))
        H3 = np.zeros((220, 220))
        SIM._stamp_batch(H3, [(4.0, 4.0, 0.5, 4.0, 4.0, -1.2)], tool, 0.5, 0.0, 0.0, 0.05)
        self.assertAlmostEqual(float(H3[80, 80]), -1.2, places=6)                # au bas de la plongée


def small_arcs(cx, cy, r, loops=2):
    """Parcours : plongée puis `loops` tours d'un petit cercle en segments (comme le fond d'une hélice)."""
    n = 16                                                                       # arcs de 15 segments, 2 droites au bout
    pts = [(cx + r * math.cos(math.radians(90 + 360.0 / n * k)), cy + r * math.sin(math.radians(90 + 360.0 / n * k)))
           for k in range(n * loops + 1)]
    moves = [M.Move('rapid', pts[0][0], pts[0][1], 2.0), M.Move('plunge', pts[0][0], pts[0][1], -0.5)]
    moves += [M.Move('feed', x, y, -0.5) for x, y in pts[1:]]
    tp = M.Toolpath(op_id='o', tool_id='t', name='essai')
    tp.moves = moves
    return tp


def program(toolpaths, ij_abs):
    """Programme ISO des parcours ajustés en arcs, centres I J absolus (fiche Ijki=0) ou relatifs, cotes à 3 décimales."""
    out = []
    for tp in toolpaths:
        prev = None
        for m in arcfit.fit_moves(tp.moves, 0.01):
            if m.kind == 'rapid':
                out.append(f'G0 X{m.x:.3f} Y{m.y:.3f} Z{m.z:.3f}')
            elif m.is_arc:
                i, j = (m.cx, m.cy) if ij_abs else (m.cx - prev[0], m.cy - prev[1])
                out.append(f'{"G2" if m.kind == "arc_cw" else "G3"} X{m.x:.3f} Y{m.y:.3f} I{i:.3f} J{j:.3f}')
            else:
                out.append(f'G1 X{m.x:.3f} Y{m.y:.3f} Z{m.z:.3f} F500')
            prev = (m.x, m.y)
        out.append('G0 Z2.')
    return '\n'.join(out + ['M30']) + '\n'


class PetitsArcs(unittest.TestCase):
    CENTRES = ((-480.0, -95.0, 0.45), (-480.0, -75.0, 0.09), (-440.0, -95.0, 0.3))   # flèche < 0,01 mm

    def toolpaths(self):
        return [small_arcs(cx, cy, r) for cx, cy, r in self.CENTRES]

    def test_absolute_centres_far_from_origin(self):
        tp = ncread.read(program(self.toolpaths(), True), 'essai.iso')
        arcs = [m for m in tp.moves if m.is_arc]
        self.assertGreaterEqual(len(arcs), 6)
        for m in arcs:                                                           # avant : cercles de ~490 mm de rayon
            self.assertLess(min(math.hypot(m.cx - cx, m.cy - cy) for cx, cy, _r in self.CENTRES), 0.002)
        self.assertTrue(any('absolues' in w for w in tp.warnings))

    def test_relative_centres_unchanged(self):
        tp = ncread.read(program(self.toolpaths(), False), 'essai.nc')
        arcs = [m for m in tp.moves if m.is_arc]
        self.assertGreaterEqual(len(arcs), 6)
        for m in arcs:
            self.assertLess(min(math.hypot(m.cx - cx, m.cy - cy) for cx, cy, _r in self.CENTRES), 0.002)
        self.assertFalse(any('absolues' in w for w in tp.warnings))

    def test_full_circles_only_unchanged(self):
        text = 'G0 X-479. Y-95. Z1.\nG1 X-479. Y-95. Z-0.5 F100\nG3 X-479. Y-95. I-480. J-95.\nM30\n'
        arc = next(m for m in ncread.read(text, 'c.iso').moves if m.is_arc)
        self.assertEqual((arc.cx, arc.cy), (-959.0, -190.0))                     # indécidable : relatifs, comme avant

    def test_written_program_check(self):
        tps = self.toolpaths()
        self.assertEqual(postcheck.verify([('essai.iso', program(tps, True))], tps, M.CamSetup()), [])
        self.assertEqual(postcheck.verify([('essai.nc', program(tps, False))], tps, M.CamSetup()), [])


if __name__ == '__main__':
    unittest.main()
