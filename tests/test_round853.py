"""Round 853 : surépaisseur en Gravure 3D, Finition et Intaille (manuel de TE, pages 609, 613 et 614)."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.cam import model as M
from vectordrive.cam import strategies as S
from vectordrive.core import geom
from vectordrive.core.document import Document, Layer, Plate, Shape


class Base(unittest.TestCase):

    def path_of(self, box=(10, 10, 40, 20), **params):
        doc = Document()
        doc.plate = Plate(width=100.0, height=100.0)
        doc.layers = [Layer(name='A', items=[Shape(path=geom.Path([geom.rect(*box)]))])]
        setup = M.setup_of(doc)
        tool = M.CamTool(name='Conique 30', diameter=6.0)
        tool.kind, tool.angle, tool.tip = 'conique', 30.0, 0.2
        setup.tools.append(tool)
        op = M.Operation(kind='vcarve', tool_id=tool.id)
        op.depth = 0.3
        for k, v in params.items():
            setattr(op, k, v)
        setup.operations.append(op)
        M.store(doc, setup)
        return S.compute(doc, setup, op, (0.0, 0.0))

    @staticmethod
    def cuts(tp):
        return [m for m in tp.moves if m.kind != 'rapid' and m.z < -1e-9]

    def extent(self, tp):
        pts = self.cuts(tp)
        return min(m.x for m in pts), min(m.y for m in pts), max(m.x for m in pts), max(m.y for m in pts)


class TestEngraving(Base):

    def test_without_stock_nothing_changes(self):
        self.assertEqual(len(self.path_of().moves), len(self.path_of(stock=0.0).moves))

    def test_the_outline_stays_further_from_the_wall(self):
        a = self.extent(self.path_of())
        b = self.extent(self.path_of(stock=0.2))
        self.assertAlmostEqual(b[0] - a[0], 0.2, places=2)
        self.assertAlmostEqual(a[2] - b[2], 0.2, places=2)
        self.assertAlmostEqual(b[1] - a[1], 0.2, places=2)
        self.assertAlmostEqual(a[3] - b[3], 0.2, places=2)

    def test_edges_only_too(self):
        a = self.extent(self.path_of(vcarve_edges_only=True))
        b = self.extent(self.path_of(vcarve_edges_only=True, stock=0.2))
        self.assertAlmostEqual(b[0] - a[0], 0.2, places=2)

    def test_two_d_contour_too(self):
        a = self.extent(self.path_of(vcarve_mode='contour'))
        b = self.extent(self.path_of(vcarve_mode='contour', stock=0.1))
        self.assertAlmostEqual(b[0] - a[0], 0.1, places=2)

    def test_the_depth_does_not_change(self):
        a = min(m.z for m in self.path_of().moves)
        b = min(m.z for m in self.path_of(stock=0.2).moves)
        self.assertAlmostEqual(a, b, places=6)

    def test_too_much_stock_says_so(self):
        tp = self.path_of(stock=50.0)
        self.assertEqual(self.cuts(tp), [])
        self.assertTrue(any('surépaisseur' in w for w in tp.warnings), tp.warnings)

    def test_negative_stock_is_ignored(self):
        a = self.extent(self.path_of())
        b = self.extent(self.path_of(stock=-1.0))
        self.assertAlmostEqual(a[0], b[0], places=6)

    def test_the_form_offers_it(self):
        from vectordrive.ui.cam_panel import KIND_FIELDS
        self.assertIn('stock', KIND_FIELDS['vcarve'])


class TestIntaglio(Base):
    """Intaille : la pointe suit l'axe médian ; la largeur laissée aux flancs réduit la profondeur. Une forme étroite : la
    profondeur y dépend de sa largeur, pas du diamètre de l'outil."""
    BOX = (10, 10, 40, 2)

    def deepest(self, tp):
        return -min(m.z for m in tp.moves)

    def test_the_stock_reduces_the_depth(self):
        a = self.path_of(self.BOX, vcarve_mode='axe', depth=0.0)
        b = self.path_of(self.BOX, vcarve_mode='axe', depth=0.0, stock=0.1)
        drop = 0.1 / math.tan(math.radians(15.0))
        self.assertAlmostEqual(self.deepest(a) - self.deepest(b), drop, places=2)

    def test_it_stays_on_the_axis(self):
        a = self.path_of(self.BOX, vcarve_mode='axe', depth=0.0)
        b = self.path_of(self.BOX, vcarve_mode='axe', depth=0.0, stock=0.1)
        for tp in (a, b):                                 # le plus profond, au milieu de la forme (les coins ont leurs branches)
            self.assertAlmostEqual(min(tp.moves, key=lambda m: m.z).y, 11.0, delta=0.05)


if __name__ == '__main__':
    unittest.main()
