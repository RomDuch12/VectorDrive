"""Round 858 : fer à dorer gaufrant : choix des passes, galbe dans les formes (manuel de TE, page 618)."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from shapely.geometry import Point, Polygon

from vectordrive.cam import advanced as A
from vectordrive.cam import model as M
from vectordrive.cam import strategies as S
from vectordrive.core import geom
from vectordrive.core.document import Document, Layer, Plate, Shape

BOX = (10.0, 10.0, 40.0, 20.0)
POLY = Polygon([(10, 10), (50, 10), (50, 30), (10, 30)])


def path_of(tool=None, **params):
    doc = Document()
    doc.plate = Plate(width=100.0, height=100.0)
    doc.layers = [Layer(name='A', items=[Shape(path=geom.Path([geom.rect(*BOX)]))])]
    setup = M.setup_of(doc)
    tool = tool or M.CamTool(name='F', diameter=1.0)
    setup.tools.append(tool)
    op = M.Operation(kind='fer_dorer', tool_id=tool.id, depth=1.0, emboss_edge=0.5, emboss_width=2.0, resolution=0.25)
    for k, v in params.items():
        setattr(op, k, v)
    setup.operations.append(op)
    M.store(doc, setup)
    return S.compute(doc, setup, op, (0.0, 0.0))


def cone():
    t = M.CamTool(name='C', diameter=6.0)
    t.kind, t.angle, t.tip = 'conique', 60.0, 0.1
    return t


def cuts(tp):
    return [m for m in tp.moves if m.kind != 'rapid' and m.z < -1e-9]


class TestDefault(unittest.TestCase):

    def test_around_still_stays_out_of_the_forms(self):
        a = path_of(emboss_side='autour', emboss_passes='standard')
        self.assertTrue(cuts(a))
        self.assertTrue(all(not POLY.buffer(-1e-6).contains(Point(m.x, m.y)) for m in cuts(a)))


class TestInside(unittest.TestCase):

    def test_everything_stays_in_the_form(self):
        tp = path_of(emboss_side='dedans')
        self.assertTrue(cuts(tp))
        for m in cuts(tp):
            self.assertTrue(POLY.contains(Point(m.x, m.y)), (m.x, m.y))

    def test_the_tool_does_not_touch_the_margin(self):
        tp = path_of(emboss_side='dedans')
        margin = POLY.boundary
        for m in cuts(tp):
            self.assertGreaterEqual(Point(m.x, m.y).distance(margin), 0.5 + 0.5 - 1e-6)       # largeur au bord + rayon de l'outil

    def test_deepest_in_the_middle(self):
        tp = path_of(emboss_side='dedans')
        low = min(cuts(tp), key=lambda m: m.z)
        self.assertAlmostEqual(low.z, -1.0, places=6)
        self.assertGreaterEqual(Point(low.x, low.y).distance(POLY.boundary), 2.5 + 0.5 - 0.3)

    def test_the_depth_follows_the_profile(self):
        tp = path_of(emboss_side='dedans', step_down=5.0)
        for m in cuts(tp):
            d = Point(m.x, m.y).distance(POLY.boundary) - 0.5                                 # moins le rayon de l'outil
            self.assertGreaterEqual(-m.z + 1e-6, 0.0)
            self.assertLessEqual(-m.z, A.emboss_depth(M.Operation(depth=1.0, emboss_edge=0.5, emboss_width=2.0), d + 0.26) + 1e-6)

    def test_the_floor_is_emptied(self):
        tp = path_of(emboss_side='dedans')
        centre = [m for m in cuts(tp) if abs(m.y - 20.0) < 0.5]    # les passes vont jusqu'à la ligne du milieu
        self.assertTrue(centre)
        self.assertAlmostEqual(min(m.z for m in centre), -1.0, places=6)

    def test_a_form_too_small_gives_no_crash(self):
        doc = Document()
        doc.plate = Plate(width=100.0, height=100.0)
        doc.layers = [Layer(name='A', items=[Shape(path=geom.Path([geom.rect(10, 10, 0.4, 0.4)]))])]
        setup = M.setup_of(doc)
        t = M.CamTool(name='F', diameter=1.0)
        setup.tools.append(t)
        op = M.Operation(kind='fer_dorer', tool_id=t.id, depth=1.0, emboss_side='dedans')
        setup.operations.append(op)
        M.store(doc, setup)
        self.assertEqual(cuts(S.compute(doc, setup, op, (0.0, 0.0))), [])


class TestPasses(unittest.TestCase):

    def test_intaglio_alone(self):
        tp = path_of(cone(), emboss_passes='intaille', emboss_side='dedans')
        self.assertTrue(cuts(tp))
        self.assertFalse([w for w in tp.warnings if 'passes, de' in w])
        for m in cuts(tp):
            self.assertTrue(POLY.contains(Point(m.x, m.y)))
        self.assertGreater(min(m.z for m in cuts(tp)), -1.0 - 1e-6)

    def test_standard_and_intaglio(self):
        std = path_of(cone(), emboss_side='dedans')
        ax = path_of(cone(), emboss_side='dedans', emboss_passes='intaille')
        both = path_of(cone(), emboss_side='dedans', emboss_passes='les_deux')
        self.assertGreater(len(cuts(both)), len(cuts(std)))
        self.assertGreater(len(cuts(both)), len(cuts(ax)))

    def test_the_intaglio_needs_a_cone(self):
        tp = path_of(emboss_passes='les_deux', emboss_side='dedans')
        self.assertTrue([w for w in tp.warnings if 'outil conique' in w], tp.warnings)
        self.assertTrue(cuts(tp))

    def test_the_form_offers_them(self):
        from vectordrive.ui import cam_panel as P
        for n in ('emboss_side', 'emboss_passes'):
            self.assertIn(n, P.KIND_FIELDS['fer_dorer'])
            self.assertIn(n, P.LABELS)
        self.assertEqual(set(P.FIELD_CHOICES['emboss_side']), {'autour', 'dedans'})
        self.assertEqual(set(P.FIELD_CHOICES['emboss_passes']), {'standard', 'intaille', 'les_deux'})


if __name__ == '__main__':
    unittest.main()
