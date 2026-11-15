"""Round 865 : entrée et sortie réglées contour par contour (TE : Ponts et E/S tangentielles manuels)."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', os.path.join(tempfile.mkdtemp(), 'session'))
os.environ.setdefault('VECTORDRIVE_NO_TYPEEDIT', '1')

from PySide6.QtWidgets import QApplication

from vectordrive.cam import model as M
from vectordrive.cam import strategies as S
from vectordrive.core import geom
from vectordrive.core.document import Document, Layer, Plate, Shape
from vectordrive.core.geom import Affine

app = QApplication.instance() or QApplication([])


def square(x, y, side=20.0):
    return Shape(path=geom.Path([geom.rect(x, y, side, side)]))


def setup_doc(items, **kw):
    doc = Document()
    doc.plate = Plate(width=200.0, height=200.0)
    doc.layers = [Layer(name='A', items=list(items))]
    setup = M.setup_of(doc)
    tool = M.CamTool(name='F', diameter=2.0)
    setup.tools.append(tool)
    args = dict(kind='contour', tool_id=tool.id, depth=1.0, step_down=1.0, side='exterieur')
    args.update(kw)
    op = M.Operation(**args)
    setup.operations.append(op)
    M.store(doc, setup)
    return doc, setup, op


def cuts(tp):
    """Les parties usinées, séparées par les rapides : [(x, y)…] pour chacune."""
    out, cur, last = [], [], None
    for m in tp.moves:
        if m.kind == 'rapid':
            if cur:
                out.append(cur)
            cur, last = [], (m.x, m.y)
            continue
        if not cur and last is not None:
            cur.append(last)
        cur.append((m.x, m.y))
        last = (m.x, m.y)
    if cur:
        out.append(cur)
    return out


def length(chain):
    return sum(math.dist(a, b) for a, b in zip(chain, chain[1:]))


class TestStrategy(unittest.TestCase):

    def run_it(self, items, **kw):
        doc, setup, op = setup_doc(items, **kw)
        tp = S.compute(doc, setup, op, (0.0, 0.0))
        return [c for c in cuts(tp) if length(c) > 1.0]

    def test_only_the_marked_contour_has_a_lead(self):
        a, b = square(10, 10), square(60, 10)
        a.extra['lead_xy'] = [[30.0, 20.0, 3.0, 3.0]]       # côté droit du premier
        got = self.run_it([a, b])
        self.assertEqual(len(got), 2)
        with_lead = [c for c in got if c[0][0] < 45]
        other = [c for c in got if c[0][0] > 45]
        self.assertGreater(length(with_lead[0]), 88.0 + 3.0)     # 4 x 22 : carré décalé d'un rayon d'outil, plus les deux arcs
        self.assertLess(length(other[0]), 88.0 + 8.0)            # arrondis des coins seulement

    def test_the_mark_sets_the_start(self):
        a = square(10, 10)
        a.extra['lead_xy'] = [[30.0, 20.0, 3.0, 0.0]]
        chain = self.run_it([a])[0]
        i = next(k for k, p in enumerate(chain) if abs(p[0] - 31.0) < 1e-6)
        self.assertAlmostEqual(chain[i][1], 20.0, delta=0.2)     # le contour commence en face du repère
        self.assertGreater(i, 0)                                 # après l'entrée

    def test_a_zero_mark_takes_away_the_lead_of_the_operation(self):
        a, b = square(10, 10), square(60, 10)
        a.extra['lead_xy'] = [[30.0, 20.0, 0.0, 0.0]]
        got = self.run_it([a, b], lead_in=3.0, lead_out=3.0)
        first = [c for c in got if c[0][0] < 45][0]
        second = [c for c in got if c[0][0] > 45][0]
        self.assertLess(length(first), 96.0)
        self.assertGreater(length(second), 91.0)

    def test_without_a_mark_the_operation_decides(self):
        a = square(10, 10)
        plain = self.run_it([a])
        doc, setup, op = setup_doc([square(10, 10)], lead_in=3.0, lead_out=3.0)
        leaded = [c for c in cuts(S.compute(doc, setup, op, (0.0, 0.0))) if length(c) > 1.0]
        self.assertGreater(length(leaded[0]), length(plain[0]) + 3.0)

    def test_the_mark_goes_to_the_closest_contour(self):
        rings = [[(9.0, 9.0), (71.0, 9.0), (71.0, 71.0), (9.0, 71.0), (9.0, 9.0)],
                 [(15.0, 15.0), (65.0, 15.0), (65.0, 65.0), (15.0, 65.0), (15.0, 15.0)]]
        self.assertEqual(S.marked_leads(rings, [(40.0, 14.0, 1.0, 2.0)], 30.0), {1: (1.0, 2.0)})
        self.assertEqual(S.marked_leads(rings, [(40.0, 10.0, 1.0, 2.0)], 30.0), {0: (1.0, 2.0)})
        self.assertEqual(S.marked_leads(rings, [(400.0, 10.0, 1.0, 2.0)], 30.0), {})

    def test_the_mark_follows_the_shape(self):
        a = square(10, 10)
        a.extra['lead_xy'] = [[30.0, 20.0, 3.0, 4.0]]
        b = a.transformed(Affine.translation(5.0, 7.0))
        self.assertEqual(b.extra['lead_xy'], [[35.0, 27.0, 3.0, 4.0]])
        self.assertEqual(a.extra['lead_xy'], [[30.0, 20.0, 3.0, 4.0]])

    def test_the_pierce_check_takes_each_contour(self):
        a = square(10, 10)
        a.extra['lead_xy'] = [[30.0, 20.0, 3.0, 0.0]]
        doc, setup, op = setup_doc([a], lead_pierce=50.0)
        tp = S.compute(doc, setup, op, (0.0, 0.0))
        self.assertTrue(any('perçage' in w for w in tp.warnings))

    def test_a_mark_with_leave_uncut(self):
        a = square(10, 10)
        a.extra['lead_xy'] = [[30.0, 20.0, 3.0, 0.0]]
        doc, setup, op = setup_doc([a], leave_uncut=2.0)
        tp = S.compute(doc, setup, op, (0.0, 0.0))
        self.assertTrue(any('sortie tangente' in w for w in tp.warnings))


class TestWindow(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from vectordrive.ui.main_window import MainWindow
        cls.win = MainWindow()

    @classmethod
    def tearDownClass(cls):
        cls.win.settings.remove('cad/contour_lead')
        cls.win.modified = False
        cls.win.close()

    def setUp(self):
        w = self.win
        self.s = square(10, 10)
        layer = Layer(name='Plan 1', items=[self.s])
        doc = w.canvas.doc
        doc.layers[:] = [layer]
        doc.active = layer.id
        doc.plate = Plate(width=100.0, height=100.0)
        w._undo.clear()

    def test_a_click_puts_the_mark_on_the_contour(self):
        m = self.win.contour_lead((30.2, 20.0), params={'lead_in': 3.0, 'lead_out': 4.0})
        self.assertAlmostEqual(m[0], 30.0, places=6)
        self.assertAlmostEqual(m[1], 20.0, places=6)
        self.assertEqual(m[2:], [3.0, 4.0])
        self.assertEqual(self.s.extra['lead_xy'], [m])

    def test_far_from_any_contour(self):
        self.assertIsNone(self.win.contour_lead((80.0, 80.0), params={'lead_in': 3.0}))
        self.assertNotIn('lead_xy', self.s.extra)

    def test_a_click_on_the_mark_changes_it(self):
        self.win.contour_lead((30.0, 20.0), params={'lead_in': 3.0, 'lead_out': 4.0})
        self.win.contour_lead((30.0, 20.0), params={'lead_in': 1.0, 'lead_out': 0.0})
        self.assertEqual(self.s.extra['lead_xy'], [[30.0, 20.0, 1.0, 0.0]])

    def test_a_click_on_the_mark_removes_it(self):
        self.win.contour_lead((30.0, 20.0), params={'lead_in': 3.0, 'lead_out': 4.0})
        self.assertIsNone(self.win.contour_lead((30.0, 20.0), params={'remove': True}))
        self.assertNotIn('lead_xy', self.s.extra)

    def test_undo(self):
        self.win.contour_lead((30.0, 20.0), params={'lead_in': 3.0, 'lead_out': 4.0})
        self.win.undo()
        leaf = self.win.canvas.doc.layers[0].items[0]
        self.assertNotIn('lead_xy', leaf.extra)

    def test_negative_values_mean_none(self):
        m = self.win.contour_lead((30.0, 20.0), params={'lead_in': -3.0, 'lead_out': 4.0})
        self.assertEqual(m[2], 0.0)

    def test_the_tool(self):
        w = self.win
        w.contour_lead((30.0, 20.0), params={'lead_in': 3.0, 'lead_out': 4.0})
        w.A['tool_leads'].trigger()
        self.assertEqual(type(w.canvas.tool_obj).__name__, 'LeadTool')
        self.assertEqual(w.canvas.lead_marks(), [(30.0, 20.0)])
        w.A['tool_select'].trigger()

    def test_the_mark_reaches_the_toolpath(self):
        w = self.win
        w.contour_lead((30.0, 20.0), params={'lead_in': 3.0, 'lead_out': 3.0})
        doc = w.canvas.doc
        setup = M.setup_of(doc)
        tool = M.CamTool(name='F', diameter=2.0)
        setup.tools.append(tool)
        op = M.Operation(kind='contour', tool_id=tool.id, depth=1.0, step_down=1.0, side='exterieur')
        setup.operations.append(op)
        M.store(doc, setup)
        got = [c for c in cuts(S.compute(doc, setup, op, (0.0, 0.0))) if length(c) > 1.0]
        self.assertGreater(length(got[0]), 91.0)
        setup.operations[:] = []
        M.store(doc, setup)


if __name__ == '__main__':
    unittest.main()
