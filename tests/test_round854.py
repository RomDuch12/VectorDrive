"""Round 854 : le point de départ d'un contour commande le départ de l'usinage (manuel de TE, page 693)."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', os.path.join(tempfile.mkdtemp(), 'session'))
os.environ.setdefault('VECTORDRIVE_NO_TYPEEDIT', '1')

from vectordrive.cam import model as M
from vectordrive.cam import strategies as S
from vectordrive.core import geom
from vectordrive.core import nodes as N
from vectordrive.core.document import Document, Layer, Plate, Shape
from vectordrive.core.geom import Affine


def rectangle(k=None, x=10.0, y=10.0):
    c = geom.rect(x, y, 40, 20)
    return c if k is None else N.set_start(c, k)


def first_cut(tp):
    m = next(m for m in tp.moves if m.kind != 'rapid')
    return m.x, m.y


class Base(unittest.TestCase):

    def path_of(self, shapes, kind='contour', **params):
        doc = Document()
        doc.plate = Plate(width=200.0, height=200.0)
        doc.layers = [Layer(name='A', items=list(shapes))]
        setup = M.setup_of(doc)
        tool = M.CamTool(name='F', diameter=6.0)
        setup.tools.append(tool)
        op = M.Operation(kind=kind, tool_id=tool.id)
        op.depth = 1.0
        for k, v in params.items():
            setattr(op, k, v)
        setup.operations.append(op)
        M.store(doc, setup)
        return S.compute(doc, setup, op, (0.0, 0.0))

    @staticmethod
    def chosen(contour):
        s = Shape(path=geom.Path([contour]))
        s.extra = {'start_xy': [list(contour.segments[0].start[:2])]}
        return s


class TestHelpers(unittest.TestCase):
    RING = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0), (0.0, 0.0)]

    def test_on_a_corner(self):
        r = S.begin_at(self.RING, (10.0, 10.0))
        self.assertEqual(r[0], (10.0, 10.0))
        self.assertEqual(r[-1], (10.0, 10.0))
        self.assertEqual(len(r), len(self.RING))

    def test_on_a_side_the_point_is_added(self):
        r = S.begin_at(self.RING, (5.0, -1.0))
        self.assertEqual(r[0], (5.0, 0.0))
        self.assertEqual(r[1], (10.0, 0.0))
        self.assertEqual(r[-2], (0.0, 0.0))
        self.assertEqual(len(r), len(self.RING) + 1)

    def test_same_shape_same_direction(self):
        r = S.begin_at(self.RING, (5.0, -1.0))
        area = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(r, r[1:])) / 2
        self.assertAlmostEqual(area, 100.0, places=6)
        self.assertAlmostEqual(sum(math.dist(a, b) for a, b in zip(r, r[1:])), 40.0, places=6)

    def test_each_mark_goes_to_the_nearest_ring(self):
        other = [(p[0] + 30.0, p[1]) for p in self.RING]
        chains, fixed = S.apply_starts([(self.RING, True), (other, True)], [(30.0, 10.0)], 5.0)
        self.assertEqual(chains[0][0], self.RING)
        self.assertEqual(chains[1][0][0], (30.0, 10.0))
        self.assertEqual(fixed, {(30.0, 10.0)})

    def test_too_far_nothing_moves(self):
        chains, fixed = S.apply_starts([(self.RING, True)], [(50.0, 50.0)], 5.0)
        self.assertEqual(chains[0][0], self.RING)
        self.assertFalse(fixed)

    def test_open_chains_stay(self):
        line = [(0.0, 0.0), (10.0, 0.0)]
        chains, fixed = S.apply_starts([(line, False)], [(10.0, 0.0)], 5.0)
        self.assertEqual(chains[0][0], line)
        self.assertFalse(fixed)

    def test_the_first_mark_wins(self):
        chains, _ = S.apply_starts([(self.RING, True)], [(10.0, 10.0), (0.0, 10.0)], 5.0)
        self.assertEqual(chains[0][0][0], (10.0, 10.0))


class TestEngraving(Base):

    def test_default_stays_at_the_nearest_point(self):
        tp = self.path_of([Shape(path=geom.Path([rectangle(1)]))], side='sur')
        self.assertEqual(first_cut(tp), (10.0, 10.0))

    def test_the_chosen_point_is_respected(self):
        c = rectangle(1)
        tp = self.path_of([self.chosen(c)], side='sur')
        self.assertEqual(first_cut(tp), tuple(c.segments[0].start[:2]))
        self.assertNotEqual(first_cut(tp), (10.0, 10.0))

    def test_drawing_start_policy(self):
        c = rectangle(1)
        tp = self.path_of([Shape(path=geom.Path([c]))], side='sur', start_policy='dessin')
        self.assertEqual(first_cut(tp), tuple(c.segments[0].start[:2]))

    def test_laser_too(self):
        c = rectangle(1)
        tp = self.path_of([self.chosen(c)], kind='laser')
        self.assertEqual(first_cut(tp), tuple(c.segments[0].start[:2]))


class TestContour(Base):
    """Un détourage extérieur de Ø 6 : l'anneau décalé est à 3 mm du dessin."""

    def near_start(self, tp, c, delta=3.05):
        self.assertLessEqual(math.dist(first_cut(tp), c.segments[0].start[:2]), delta, first_cut(tp))

    def test_default_nearest(self):
        tp = self.path_of([Shape(path=geom.Path([rectangle(1)]))], side='exterieur')
        self.assertLess(math.dist(first_cut(tp), (10.0, 10.0)), 3.05)

    def test_chosen_point_outside(self):
        c = rectangle(1)
        self.near_start(self.path_of([self.chosen(c)], side='exterieur'), c)

    def test_chosen_point_inside(self):
        c = rectangle(1)
        tp = self.path_of([self.chosen(c)], side='interieur')
        self.assertLess(math.dist(first_cut(tp), c.segments[0].start[:2]), 3 * math.sqrt(2) + 0.05)

    def test_drawing_policy(self):
        c = rectangle(1)
        self.near_start(self.path_of([Shape(path=geom.Path([c]))], side='exterieur', start_policy='dessin'), c)

    def test_several_pieces_each_at_its_point(self):
        a, b = rectangle(1), rectangle(2, y=60.0)
        tp = self.path_of([self.chosen(a), self.chosen(b)], side='exterieur')
        plunges = [m for prev, m in zip(tp.moves, tp.moves[1:]) if prev.kind == 'rapid' and m.kind != 'rapid']
        for c in (a, b):
            self.assertTrue(any(math.dist((m.x, m.y), c.segments[0].start[:2]) < 3.05 for m in plunges), plunges[:6])

    def test_the_ring_is_complete(self):
        ref = self.path_of([Shape(path=geom.Path([rectangle()]))], side='exterieur')
        tp = self.path_of([self.chosen(rectangle(1))], side='exterieur')

        def length(t):
            cuts = [m for m in t.moves if m.kind != 'rapid']
            return sum(math.dist((a.x, a.y), (b.x, b.y)) for a, b in zip(cuts, cuts[1:]))
        self.assertAlmostEqual(length(ref), length(tp), delta=0.5)

    def test_lead_in_starts_there(self):
        c = rectangle(1)
        tp = self.path_of([self.chosen(c)], side='exterieur', lead_in=2.0, ramp=False)
        self.assertLess(math.dist(first_cut(tp), c.segments[0].start[:2]), 3.05 + 2.0 * math.sqrt(2) + 0.05)

    def test_lead_in_without_choice_stays_on_the_long_side(self):
        tp = self.path_of([Shape(path=geom.Path([rectangle()]))], side='exterieur', lead_in=2.0, ramp=False)
        self.assertLess(abs(first_cut(tp)[0] - 28.0), 0.2, first_cut(tp))

    def test_finish_pass_too(self):
        c = rectangle(1)
        tp = self.path_of([self.chosen(c)], side='exterieur', stock=0.5, finish=True)
        plunges = [m for prev, m in zip(tp.moves, tp.moves[1:]) if prev.kind == 'rapid' and m.kind != 'rapid']
        self.assertGreaterEqual(len(plunges), 2)
        self.assertLess(math.dist((plunges[-1].x, plunges[-1].y), c.segments[0].start[:2]), 3.05)


class TestFollows(unittest.TestCase):

    def test_it_follows_the_shape(self):
        s = Shape(path=geom.Path([rectangle()]))
        s.extra = {'start_xy': [[10.0, 10.0]]}
        t = s.transformed(Affine.translation(5.0, 7.0))
        self.assertEqual(t.extra['start_xy'], [[15.0, 17.0]])
        self.assertEqual(s.extra['start_xy'], [[10.0, 10.0]])

    def test_the_form_offers_it(self):
        from vectordrive.ui import cam_panel as P
        for kind in ('contour', 'gravure', 'laser', 'laser_decoupe'):
            self.assertIn('start_policy', P.KIND_FIELDS[kind])
        self.assertIn('start_policy', P.LABELS)
        self.assertEqual(set(P.FIELD_CHOICES['start_policy']), {'proche', 'dessin'})

    def test_it_survives_the_file(self):
        doc = Document()
        setup = M.setup_of(doc)
        op = M.Operation(kind='contour')
        op.start_policy = 'dessin'
        setup.operations.append(op)
        M.store(doc, setup)
        self.assertEqual(M.setup_of(doc).operations[0].start_policy, 'dessin')


class TestCommand(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])
        from vectordrive.ui.main_window import MainWindow
        cls.win = MainWindow()

    @classmethod
    def tearDownClass(cls):
        cls.win.modified = False
        cls.win.close()

    def test_node_start_records_the_point(self):
        win = self.win
        doc = win.canvas.doc
        s = Shape(path=geom.Path([rectangle()]))
        layer = Layer(name='Plan 1', items=[s])
        doc.layers[:] = [layer]
        doc.active = layer.id
        win.canvas.select([s])
        win.A['tool_node'].trigger()
        tool = win.canvas.tool_obj
        tool.sel.clear()
        tool.sel.add((0, 1))
        win.node_start()
        c = s.path.contours[0]
        self.assertEqual(s.extra['start_xy'], [list(c.segments[0].start[:2])])
        tool.sel.clear()
        tool.sel.add((0, 2))
        win.node_start()
        c = s.path.contours[0]
        self.assertEqual(s.extra['start_xy'], [list(c.segments[0].start[:2])])     # le dernier, pas les deux


if __name__ == '__main__':
    unittest.main()
