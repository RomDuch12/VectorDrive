"""Round 368 : gravure laser — remplissage global, forme par forme ou par
zones (TypeEdit : Optimisation de zone) ; lignes alignées d'une zone à
l'autre."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.cam import model as M, strategies as S
from vectordrive.core import geom
from vectordrive.core.document import Document, Shape


def run(contours, **kw):
    d = Document()
    d.plate = None
    for c in contours:
        d.add(Shape(path=geom.Path([c]), tool=1))
    setup = M.setup_of(d)
    t = M.CamTool(name='L', kind='laser', diameter=0.05)
    setup.tools = [t]
    return S.compute(d, setup, M.Operation(kind='laser_gravure', tool_id=t.id, resolution=0.5, **kw))


def segments(tp):
    """Segments gravés (de point en point, en travail)."""
    out, prev = [], None
    for m in tp.moves:
        if m.kind == 'feed' and prev is not None:
            out.append((round(prev[0], 6), round(prev[1], 6), round(m.x, 6), round(m.y, 6)))
        prev = (m.x, m.y)
    return out


class TestFillOrder(unittest.TestCase):
    def test_by_shape(self):
        a, b = geom.rect(0, 0, 4, 4), geom.rect(10, 0, 4, 4)
        g = run([a, b])                                   # global : chaque ligne passe d'une forme à l'autre
        f = run([a, b], fill_order='forme')
        xs = [m.x for m in f.moves if m.kind == 'feed']
        first_b = next(i for i, x in enumerate(xs) if x > 5)
        self.assertTrue(all(x > 5 for x in xs[first_b:]))  # la 1re forme finie avant la 2de
        gx = [m.x for m in g.moves if m.kind == 'feed']
        self.assertTrue(any(x > 5 for x in gx[:len(gx) // 4]))
        self.assertEqual(len(segments(f)), len(segments(g)))

    def test_zones_aligned(self):
        sq = geom.rect(0, 0, 20, 7.3)
        g = run([sq])
        z = run([sq], fill_order='zones', fill_dx=5, fill_dy=5)
        ys_g = sorted({round(m.y, 6) for m in g.moves if m.kind == 'feed'})
        ys_z = sorted({round(m.y, 6) for m in z.moves if m.kind == 'feed'})
        self.assertEqual(ys_g, ys_z)                      # mêmes rangées : pas de décalage aux raccords
        parts = S.fill_parts(S.region([geom.Path([sq])], 0.01), 'zones', 5, 5)
        self.assertEqual(len(parts), 8)                   # 4 × 2 carreaux
        self.assertAlmostEqual(sum(p.area for p in parts), 20 * 7.3, 6)


if __name__ == '__main__':
    unittest.main()
