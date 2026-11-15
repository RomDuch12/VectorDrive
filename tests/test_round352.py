"""Round 352 : tri des contours manuel (TypeEdit) — les traits gravés dans
l'ordre et le sens du dessin au lieu du plus court."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.cam import model as M, strategies as S
from vectordrive.core import geom
from vectordrive.core.document import Document, Shape


def run(**kw):
    d = Document()
    d.plate = None
    # dessinés dans cet ordre : loin, près, milieu ; le dernier dessiné de droite à gauche
    for a, b in (((50, 0), (60, 0)), ((0, 5), (10, 5)), ((40, 10), (30, 10))):
        d.add(Shape(path=geom.Path([geom.polyline([a, b])]), tool=1))
    setup = M.setup_of(d)
    t = M.CamTool(name='V', kind='conique', diameter=3, angle=90)
    setup.tools = [t]
    return S.compute(d, setup, M.Operation(kind='gravure', depth=0.2, tool_id=t.id, **kw))


def starts(tp):
    return [(round(m.x), round(m.y)) for m in tp.moves if m.kind == 'plunge']


class TestOrder(unittest.TestCase):
    def test_modes(self):
        self.assertEqual(starts(run()), [(0, 5), (30, 10), (50, 0)])                  # au plus court
        self.assertEqual(starts(run(order_mode='dessin')), [(50, 0), (0, 5), (40, 10)])   # ordre et sens du dessin
        self.assertEqual(starts(run()), [(0, 5), (30, 10), (50, 0)])                  # remis après


if __name__ == '__main__':
    unittest.main()
