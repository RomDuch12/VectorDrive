"""Round 873 : la distance entre ponts de TE13. Les nombres et positions attendus sont ceux que TE13 a calculés sur le même dessin
(un T de 156,27 mm et un triangle de 92,70 mm de tour au Ø6, en Découpe extérieure, 2 passes de 1 mm)."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.cam import model as M
from vectordrive.cam import strategies as S
from vectordrive.cam import tpp
from vectordrive.core import geom
from vectordrive.core.document import Document, Layer, Plate, Shape

T_SHAPE = [(10, 10), (50, 10), (50, 20), (35, 20), (35, 40), (25, 40), (25, 20), (10, 20)]
TRIANGLE = [(70, 15), (90, 15), (80, 40)]
L_T = 156.27
L_TRI = 92.70


def of_length(L):
    return [(0.0, 0.0), (L, 0.0)]


def path_of(shapes=(T_SHAPE, TRIANGLE), **kw):
    doc = Document()
    doc.plate = Plate(width=120.0, height=60.0)
    doc.layers = [Layer(name='A', items=[Shape(path=geom.Path([geom.polyline(s, closed=True)])) for s in shapes])]
    setup = M.setup_of(doc)
    t = M.CamTool(name='F', diameter=6.0)
    setup.tools.append(t)
    base = dict(kind='contour', side='exterieur', tool_id=t.id, depth=2.0, step_down=1.0)
    base.update(kw)
    op = M.Operation(**base)
    setup.operations.append(op)
    M.store(doc, setup)
    return S.compute(doc, setup, op, (0.0, 0.0))


def bridges(tp, top):
    """Les ponts du parcours à la cote `top` : (nombre, longueur de chacun)."""
    ms = tp.moves
    out, cur = [], None
    for a, b in zip(ms, ms[1:]):
        if b.kind == 'rapid':
            cur = None
            continue
        if abs(b.z - top) < 1e-9 and abs(a.z - top) < 1e-9:
            d = math.hypot(b.x - a.x, b.y - a.y)
            if cur is None:
                cur = [0.0]
                out.append(cur)
            cur[0] += d
        else:
            cur = None
    return [round(c[0], 2) for c in out]


class TestCount(unittest.TestCase):
    # (distance, longueur du pont avec l'outil, nombre sur le T, nombre sur le triangle) : relevés dans TE13
    MEASURED = [(10, 8, 9, 5), (20, 11, 5, 3), (30, 11, 4, 2), (45, 11, 3, 2), (50, 11, 3, 2), (50, 8, 3, 2), (60, 11, 2, 1),
                (80, 11, 2, 1), (100, 11, 1, 1), (200, 11, 1, 1), (30, 36, 2, 1)]

    def test_the_numbers_of_te(self):
        for gap, width, n_t, n_tri in self.MEASURED:
            op = M.Operation(tab_gap=float(gap))
            self.assertEqual(S.tab_count(op, of_length(L_T), width), n_t, (gap, width))
            self.assertEqual(S.tab_count(op, of_length(L_TRI), width), n_tri, (gap, width))

    def test_at_least_one(self):
        self.assertEqual(S.tab_count(M.Operation(tab_gap=1000.0), of_length(10.0), 2.0), 1)

    def test_the_maximum_still_holds(self):
        self.assertEqual(S.tab_count(M.Operation(tab_gap=10.0, tab_max=3), of_length(L_T), 8.0), 3)

    def test_every_pont_is_asked_by_a_distance(self):
        self.assertTrue(S.has_tabs(M.Operation(tab_gap=30.0)))
        self.assertFalse(S.has_tabs(M.Operation()))

    def test_the_other_rule_does_not_move(self):
        self.assertEqual(S.tab_count(M.Operation(tab_spacing=30.0), of_length(L_T), 11.0), 5)


class TestPath(unittest.TestCase):
    KW = dict(tab_gap=30.0, tab_width=5.0, tab_height=0.5)

    def test_the_number_on_each_contour(self):
        self.assertEqual(bridges(path_of(**self.KW), -1.5), [11.0] * 6)              # 4 sur le T, 2 sur le triangle

    def test_each_one_in_the_middle_of_its_share(self):
        # TE13, à 45 : 3 ponts sur le T, le premier à 20,54 mm du départ, puis tous les 52,09 mm
        got = S.tab_intervals(of_length(L_T), 3, 11.0)
        self.assertAlmostEqual(got[0][0], 20.54, delta=0.01)
        self.assertAlmostEqual(got[1][0] - got[0][0], 52.09, delta=0.01)

    def test_they_only_touch_the_passes_below_them(self):
        # 0,5 de haut : pas sur la passe à 1 mm ; 1,5 de haut : aussi sur celle-là
        self.assertEqual(bridges(path_of([T_SHAPE], **self.KW), -0.5), [])
        tall = path_of([T_SHAPE], tab_gap=30.0, tab_width=5.0, tab_height=1.5)
        self.assertEqual(bridges(tall, -0.5), [11.0] * 8)


class TestPresets(unittest.TestCase):

    def op(self, sections):
        return tpp.to_template(tpp.Preset(name='essai', kind='CP_Cutting_3D', sections=sections))['operations'][0]

    def test_a_distance_is_read_as_a_distance(self):
        o = self.op({'PROFONDEUR': {'ZBOTTOM': '2.e-003'},
                     'SPECIALDECOUPE': {'AddLinks': '1', 'HeightOfBridge': '5.e-004', 'LengthOfBridge': '5.e-003',
                                        'DistanceUnderBridge': '3.e-002'}})
        self.assertAlmostEqual(o['tab_gap'], 30.0)
        self.assertEqual(o['tab_spacing'], 0.0)
        self.assertEqual(o['tabs'], 0)


class TestForm(unittest.TestCase):

    def test_the_form_offers_it(self):
        from vectordrive.ui import cam_panel as P
        for kind in ('contour', 'gravure', 'laser_decoupe'):
            self.assertIn('tab_gap', P.KIND_FIELDS[kind])
        self.assertIn('tab_gap', P.LABELS)


if __name__ == '__main__':
    unittest.main()
