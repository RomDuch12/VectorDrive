"""Round 271 : détourage fraisé — entrée et sortie tangentes (quarts de
cercle) dans la chute, à chaque passe, finition comprise."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.cam import model as M, strategies as S
from vectordrive.core import geom
from vectordrive.core.document import Document, Shape


def compute(**kw):
    d = Document()
    d.plate = None
    d.add(Shape(path=geom.Path([geom.rect(0, 0, 20, 10)]), tool=1))
    setup = M.setup_of(d)
    t = M.CamTool(name='F2', diameter=2)
    setup.tools = [t]
    return S.compute(d, setup, M.Operation(kind='contour', depth=1, step_down=0.5, tool_id=t.id, **kw))


def inside_part(x, y):
    return 0 < x < 20 and 0 < y < 10


class TestLeads(unittest.TestCase):
    def test_exterior(self):
        tp = compute(side='exterieur', lead_in=2, lead_out=2)
        plunges = [m for m in tp.moves if m.kind == 'plunge']
        self.assertEqual(len(plunges), 2)                                       # une entrée par passe
        for m in plunges:
            self.assertFalse(inside_part(m.x, m.y))
            self.assertGreater(min(abs(m.y - 11), abs(m.y + 1)), 1.5)          # dans la chute, loin du trajet
        cut = [m for m in tp.moves if m.kind == 'feed']
        self.assertTrue(all(not inside_part(m.x, m.y) for m in cut))

    def test_interior_and_finish(self):
        tp = compute(side='interieur', lead_in=1.5, lead_out=1.5, stock=0.2, finish=True)
        plunges = [m for m in tp.moves if m.kind == 'plunge']
        self.assertEqual(len(plunges), 3)                                       # 2 passes + finition
        for m in plunges:
            self.assertTrue(inside_part(m.x, m.y))                              # dans le trou (la chute)
        last = [m for m in tp.moves if m.kind == 'feed'][-1]
        self.assertTrue(inside_part(last.x, last.y))

    def test_without_leads_unchanged(self):
        tp = compute(side='exterieur')
        plunges = [m for m in tp.moves if m.kind == 'plunge']
        self.assertEqual(len({(round(m.x, 6), round(m.y, 6)) for m in plunges}), 1)   # une seule descente, sur le trajet
        self.assertTrue(all(abs(m.y - 11) < 1e-6 or abs(m.y + 1) < 1e-6 or abs(m.x - 21) < 1e-6 or abs(m.x + 1) < 1e-6
                            for m in plunges))


if __name__ == '__main__':
    unittest.main()
