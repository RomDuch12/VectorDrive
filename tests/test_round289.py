"""Round 289 : multicopie d'un parcours (TypeEdit) — colonnes × rangées,
pas donné ou calculé (taille + écart), serpentin, remontée entre copies,
cycles décalés."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.cam import model as M, strategies as S
from vectordrive.core import geom
from vectordrive.core.document import Document, Shape


def setup_of(path):
    d = Document()
    d.plate = None
    d.add(Shape(path=geom.Path([path]), tool=1))
    setup = M.setup_of(d)
    t = M.CamTool(name='F1', diameter=1)
    setup.tools = [t]
    return d, setup, t


class TestMulticopy(unittest.TestCase):
    def test_grid(self):
        d, setup, t = setup_of(geom.rect(0, 0, 10, 5))
        one = S.compute(d, setup, M.Operation(kind='gravure', depth=0.2, tool_id=t.id))
        many = S.compute(d, setup, M.Operation(kind='gravure', depth=0.2, tool_id=t.id, copies_x=3, copies_y=2,
                                               copies_gap=5))
        f1 = [m for m in one.moves if m.kind == 'feed']
        fm = [m for m in many.moves if m.kind == 'feed']
        self.assertEqual(len(fm), 6 * len(f1))
        xs = sorted({round(m.x, 6) for m in fm})
        self.assertEqual((min(xs), max(xs)), (0.0, 40.0))                       # pas 10 + 5
        self.assertEqual(max(m.y for m in fm), 15.0)                              # pas 5 + 5
        self.assertTrue(any('3 × 2' in w for w in many.warnings))
        # entre deux copies, l'outil remonte au dégagement
        for a, b in zip(many.moves, many.moves[1:]):
            if b.kind == 'rapid' and (abs(b.x - a.x) > 1 or abs(b.y - a.y) > 1):
                self.assertGreaterEqual(a.z, 0.0 - 1e-9)

    def test_given_pitch_and_cycles(self):
        d, setup, t = setup_of(geom.circle((0, 0), 1.5))
        t.kind, t.diameter = 'foret', 3.0
        tp = S.compute(d, setup, M.Operation(kind='percage', depth=1, tool_id=t.id, copies_x=2, copies_dx=20,
                                             copies_dy=30))
        self.assertEqual(sorted(round(m.x, 6) for m in tp.moves if m.kind == 'plunge'), [0.0, 20.0])
        if tp.cycles:                                                              # cycles machine décalés aussi
            self.assertEqual(sorted(round(c['x'], 6) for c in tp.cycles), [0.0, 20.0])


if __name__ == '__main__':
    unittest.main()
