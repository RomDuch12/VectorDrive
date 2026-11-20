"""Round 1109 : gravure laser (remplissage) d'une forme plus petite que le pas des lignes — avec le contour en finition,
TypeError (`em.pos` None dans `order_chains`) ; sans, un parcours vide sans un mot."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1109.ini'))

from vectordrive.cam import model, strategies  # noqa: E402
from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Document, Shape  # noqa: E402


def compute(size, finish, kind='laser', **kw):
    d = Document()
    d.add(Shape(path=geom.Path([geom.rect(3.0, 4.0, size, size)])))
    t = model.CamTool(kind=kind, diameter=0.05)
    s = model.CamSetup(tools=[t])
    op = model.Operation(kind='laser_gravure', tool_id=t.id, finish=finish, **kw)
    return strategies.compute(d, s, op)


class TestTinyLaserFill(unittest.TestCase):
    def test_finish_only_outline(self):
        tp = compute(0.03, True, resolution=0.1)                                 # avant : TypeError 'NoneType' object is not subscriptable
        cuts = [m for m in tp.moves if m.kind == 'feed']
        self.assertTrue(cuts)                                     # le contour de finition est gravé
        xs = [m.x for m in tp.moves if m.kind != 'rapid']
        self.assertGreaterEqual(min(xs), 3.0 - 1e-6)
        self.assertLessEqual(max(xs), 3.03 + 1e-6)
        self.assertTrue(any('rien de rempli (contour seul)' in w for w in tp.warnings), tp.warnings)

    def test_no_finish_says_why(self):
        tp = compute(0.03, False, resolution=0.1)
        self.assertFalse([m for m in tp.moves if m.kind == 'feed'])
        self.assertTrue(any('rien de rempli' in w and 'contour seul' not in w for w in tp.warnings), tp.warnings)

    def test_normal_fill_unchanged(self):
        tp = compute(2.0, True)
        self.assertFalse(any('rien de rempli' in w for w in tp.warnings), tp.warnings)
        self.assertGreater(len([m for m in tp.moves if m.kind == 'feed']), 20)

    def test_order_chains_without_position(self):
        ring = [(5.0, 5.0, 0.0), (6.0, 5.0, 0.0), (6.0, 6.0, 0.0), (5.0, 6.0, 0.0), (5.0, 5.0, 0.0)]
        out = strategies.order_chains([(ring, True), ([(1.0, 1.0, 0.0), (2.0, 1.0, 0.0)], False)], None)
        self.assertEqual(out[0][0][0][:2], (1.0, 1.0))           # depuis l'origine : la chaîne la plus proche d'abord


if __name__ == '__main__':
    unittest.main()
