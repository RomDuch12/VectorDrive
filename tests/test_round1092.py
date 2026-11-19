"""Round 1092 (demande du 19/11 matin) : « Parcours Prismatique : Possibilité d'enlever la matière restant entre les
contours et le passage de l'outil précédent (en XY) ». Deux carrés à 2 mm l'un de l'autre, une fraise Ø6 d'avant qui
en a fait le tour (à 3 mm) au fond : elle a laissé l'écart entre eux et les coins rentrants."""
import math
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1092.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from shapely.geometry import Point, box  # noqa: E402
from shapely.ops import unary_union  # noqa: E402

from vectordrive.cam import advanced as A  # noqa: E402
from vectordrive.cam import model as M  # noqa: E402
from vectordrive.cam import strategies as S  # noqa: E402
from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Document, Layer, Plate, Shape  # noqa: E402
from vectordrive.ui import cam_panel  # noqa: E402

BEFORE = 'avant : pas de reste jusqu’à l’outil d’avant pour les lettres prismatiques'
TAN = math.tan(math.radians(15))
LETTERS = unary_union([box(20, 20, 30, 30), box(32, 20, 42, 30)])
FAR = unary_union([box(60, 20, 70, 30), box(72, 20, 82, 30)])          # un autre mot, loin de la fraise d'avant
H = 2.0


def P(*pts):
    return geom.polyline(list(pts), closed=True)


def square(x):
    return Shape(path=geom.Path([P((x, 20), (x + 10, 20), (x + 10, 30), (x, 30))]))


def drawing(far=False):
    doc = Document()
    doc.plate = Plate(width=100.0, height=60.0)
    doc.layers = [Layer(name='A', items=[square(x) for x in ((20, 32, 60, 72) if far else (20, 32))])]
    return doc


def previous_path(setup, offsets=(3.0,)):
    """La fraise Ø6 d'avant : des tours autour des deux carrés ensemble, au fond."""
    flat = M.CamTool(name='f6', kind='fraise', diameter=6.0)
    setup.tools.append(flat)
    tp = M.Toolpath(op_id='avant', tool_id=flat.id)
    for d in offsets:
        ring = list(LETTERS.buffer(d, quad_segs=16).exterior.coords)
        tp.moves.append(M.Move('rapid', ring[0][0], ring[0][1], 5.0))
        tp.moves.append(M.Move('plunge', ring[0][0], ring[0][1], -H))
        tp.moves += [M.Move('feed', x, y, -H) for x, y in ring[1:]]
        tp.moves.append(M.Move('rapid', ring[-1][0], ring[-1][1], 5.0))
    return tp


def prism(rest=True, previous=None, offsets=(3.0,), lateral=False, far=False, more=(), hollow=False):
    doc = drawing(far)
    setup = M.setup_of(doc)
    cone = M.CamTool(name='c', kind='conique', diameter=8.0, tip=0.2, angle=30.0)
    setup.tools.append(cone)
    op = M.Operation(kind='prismatique', tool_id=cone.id, depth=H, step_down=1.0, prism_rest=rest,
                     prism_lateral=lateral, prism_hollow=hollow)
    setup.operations.append(op)
    M.store(doc, setup)
    prev = [previous_path(setup, offsets)] if previous is None else previous
    prev = list(prev) + [m(setup) for m in more]
    token = S._PREVIOUS.set(prev)
    try:
        return S.compute(doc, setup, op, (0.0, 0.0)), setup, prev, cone
    finally:
        S._PREVIOUS.reset(token)


def facing(setup):
    """Un surfaçage d'avant, Ø40 à -0,1 : il ne va pas au fond des lettres, il ne compte pas."""
    big = M.CamTool(name='f40', kind='fraise', diameter=40.0)
    setup.tools.append(big)
    tp = M.Toolpath(op_id='surfacage', tool_id=big.id)
    tp.moves += [M.Move('rapid', 0, 0, 5.0), M.Move('plunge', 0, 0, -0.1), M.Move('feed', 100, 0, -0.1),
                 M.Move('feed', 100, 60, -0.1)]
    return tp


def outside_points(tp, letters=LETTERS):
    """Les points de coupe hors des lettres (le flanc est sur le contour ou dedans) : ceux du reste."""
    out = []
    for m in tp.moves:
        if m.kind != 'rapid' and m.z < 0 and letters.distance(Point(m.x, m.y)) > 1e-3:
            out.append((m.x, m.y, m.z))
    return out


class PrismRest(unittest.TestCase):

    def test_the_gap_and_the_corners_are_cleared(self):
        tp, setup, prev, cone = prism()
        pts = outside_points(tp)
        self.assertTrue(pts, BEFORE)
        gap = [p for p in pts if 30 < p[0] < 32 and 20 < p[1] < 30]
        self.assertTrue(gap, 'avant : l’écart de 2 mm entre les lettres restait')
        self.assertEqual({round(p[2], 6) for p in gap}, {-1.0, -2.0})         # à chaque niveau, jusqu'au fond
        # le fond de l'écart vraiment vidé : les anneaux au pas du fond, de l'extérieur vers les lettres
        bottom = [p for p in gap if abs(p[2] + H) < 1e-9]
        xs = sorted({round(p[0], 3) for p in bottom})
        self.assertGreaterEqual(len(xs), 2)
        pitch = 2 * (0.1 + A.FLAT_RIDGE * TAN)
        self.assertLessEqual(min(xs) - 30, pitch + 1e-3)
        # aucune arête au milieu de l'écart, là où les anneaux des deux lettres se rejoignent
        self.assertLessEqual(max(b - a for a, b in zip(xs, xs[1:])), pitch + 1e-3, xs)
        self.assertLessEqual(32 - max(xs), pitch + 1e-3)
        # jamais dans les lettres, jamais ce que la fraise a déjà creusé, jamais au-delà de son passage
        from vectordrive.cam import linkprev
        done = linkprev.cleared(prev, setup, -H + 1e-3, setup.tolerance)
        for x, y, z in pts:
            q = Point(x, y)
            self.assertFalse(LETTERS.buffer(-1e-3).contains(q))
            self.assertFalse(done.buffer(-0.01).contains(q), (x, y, z))
            # la paroi laissée à 6 mm des lettres : le cône (rayon à la surface) ne l'atteint pas
            self.assertLessEqual(LETTERS.distance(q) + 0.1 - z * TAN, 6.0 + 1e-3, (x, y, z))
        self.assertFalse(any('reste jusqu' in w for w in tp.warnings))

    def test_the_cone_never_touches_a_letter(self):
        tp, _setup, _prev, cone = prism()
        pts = outside_points(tp)
        for x, y, z in pts:
            d = LETTERS.distance(Point(x, y))
            # à toute hauteur z' : rayon du cône tip/2 + (z' - z)·tan ; lettre en retrait de (H + z')·tan
            self.assertGreaterEqual(d + (H + z) * TAN - 0.1, -1e-6, (x, y, z))

    def test_off_or_nothing_before(self):
        base, *_ = prism(rest=False)
        self.assertEqual(outside_points(base), [])
        alone, *_ = prism(rest=True, previous=[])
        self.assertEqual(alone.moves, base.moves)                         # rien d'avant : rien de plus, dit
        self.assertTrue(any('aucune opération d’avant'.replace('’', "'") in w for w in alone.warnings))
        far, *_ = prism(rest=True, offsets=(3.0, 6.0, 9.0))               # tout le tour vidé : il reste l'écart
        self.assertTrue([p for p in outside_points(far) if 30 < p[0] < 32])
        lat, *_ = prism(rest=True, lateral=True)
        self.assertTrue(outside_points(lat))

    def test_only_near_the_previous_pass(self):
        tp, *_ = prism(far=True)                                           # l'autre mot : la fraise n'y est pas allée
        pts = outside_points(tp, LETTERS.union(FAR))
        self.assertTrue([p for p in pts if p[0] < 50])
        self.assertEqual([p for p in pts if p[0] > 50], [], 'avant : l’écart d’un mot non approché, creusé')
        base, *_ = prism()
        faced, *_ = prism(more=(facing,))                                  # un surfaçage peu profond : rien de changé
        self.assertEqual(faced.moves, base.moves)
        hollow, *_ = prism(hollow=True)                                    # en creux : dit, rien de plus
        self.assertTrue(any('pour les lettres en relief' in w for w in hollow.warnings))

    def test_compute_all_gives_the_previous_toolpaths(self):
        doc = drawing()
        setup = M.setup_of(doc)
        mill = M.CamTool(name='f1', kind='fraise', diameter=1.0)
        cone = M.CamTool(name='c', kind='conique', diameter=8.0, tip=0.2, angle=30.0)
        setup.tools += [mill, cone]
        first = M.Operation(kind='gravure', tool_id=mill.id, depth=H, step_down=H)
        op = M.Operation(kind='prismatique', tool_id=cone.id, depth=H, step_down=1.0, prism_rest=True)
        setup.operations += [first, op]
        M.store(doc, setup)
        S.clear_toolpath_cache()
        seen = []
        real = A._PrismRest.of

        def spy(*a, **kw):
            seen.append([tp.op_id for tp in S.previous_toolpaths()])
            return real(*a, **kw)
        with mock.patch.object(A._PrismRest, 'of', side_effect=spy):
            out = S.compute_all(doc, setup)
            self.assertEqual(seen, [[first.id]])
            S.compute_all(doc, setup)                                      # rien de changé : la mémoire
            self.assertEqual(len(seen), 1)
            first.depth = 1.0                                              # l'opération d'avant changée : recalculée
            S.compute_all(doc, setup)
            self.assertEqual(len(seen), 2)
        self.assertEqual(len(out), 2)
        self.assertEqual(S.previous_toolpaths(), [])                       # rendu après

    def test_the_form_field(self):
        self.assertIn('prism_rest', cam_panel.KIND_FIELDS['prismatique'])
        self.assertIn('prism_rest', cam_panel.LABELS)
        op = M.Operation(kind='prismatique', prism_rest=True)
        self.assertTrue(M.Operation.from_dict(op.to_dict()).prism_rest)
        self.assertFalse(M.Operation.from_dict({'kind': 'prismatique'}).prism_rest)


class Panel(unittest.TestCase):
    """Le formulaire (OK : `compute_op`) donne les parcours d'avant ; une opération d'avant retouchée la refait."""

    def setUp(self):
        from PySide6.QtWidgets import QApplication
        self.app = QApplication.instance() or QApplication([])
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.cp = self.w.cam_panel
        frame = Shape(path=geom.Path([P((10, 10), (52, 10), (52, 40), (10, 40))]))
        a, b = square(20), square(32)
        self.w.canvas.doc.active_layer.items.extend([frame, a, b])
        s = self.cp.setup()
        f6 = M.CamTool(name='f6 1092', kind='fraise', diameter=6.0, step_down=2.0)
        cone = M.CamTool(name='c 1092', kind='conique', diameter=8.0, tip=0.2, angle=30.0, step_down=1.0)
        s.tools = [f6, cone]
        s.operations = [M.Operation(name='poche', kind='poche', tool_id=f6.id, items=[frame.id, a.id, b.id], depth=H),
                        M.Operation(name='lettres', kind='prismatique', tool_id=cone.id, items=[a.id, b.id],
                                    depth=H, step_down=1.0, prism_rest=True)]
        self.cp.save(s)

    def tearDown(self):
        self.w.modified = False
        self.w.close()

    def prism_tp(self, s):
        return next(t for t in self.cp.toolpaths if t.op_id == s.operations[1].id)

    def test_the_form_gives_the_previous_and_follows_it(self):
        s = self.cp.setup()
        for op in s.operations:
            self.cp.compute_op(op)
        tp = self.prism_tp(s)
        self.assertTrue([p for p in outside_points(tp) if 30 < p[0] < 32], 'avant : OK du formulaire, sans le reste')
        before = self.cp._inputs_state()[2][s.operations[1].id]
        s = self.cp.setup()
        s.operations[0].depth = 1.0                                         # la poche ne va plus au fond des lettres
        self.cp.save(s)
        self.assertNotEqual(self.cp._inputs_state()[2][s.operations[1].id], before)
        self.cp.compute_op(s.operations[0])
        tp = self.prism_tp(s)                                               # refaite avec elle
        self.assertEqual(outside_points(tp), [])
        self.assertTrue(any('rien à reprendre' in w for w in tp.warnings))
        self.assertTrue(self.cp.inputs_current())


if __name__ == '__main__':
    unittest.main()
