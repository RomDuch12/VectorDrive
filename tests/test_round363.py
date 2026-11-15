"""Round 363 : poche — entrée en hélice : la descente tourne sur un cercle
du rayon demandé, dans la poche ; sinon rampe le long de l'anneau."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.cam import model as M, strategies as S
from vectordrive.core import geom
from vectordrive.core.document import Document, Shape


def run(size=20, **kw):
    d = Document()
    d.plate = None
    d.add(Shape(path=geom.Path([geom.rect(0, 0, size, size)]), tool=1))
    setup = M.setup_of(d)
    t = M.CamTool(name='F', kind='droite', diameter=2)
    setup.tools = [t]
    return S.compute(d, setup, M.Operation(kind='poche', depth=2, step_down=1, tool_id=t.id, ramp=True, **kw))


def descent(tp):
    """Mouvements de travail qui descendent, jusqu'au premier fond."""
    out, prev = [], None
    for m in tp.moves:
        if m.kind == 'feed' and prev is not None and m.z < prev - 1e-9:
            out.append((m.x, m.y, m.z))
        prev = m.z
    return out


class TestHelix(unittest.TestCase):
    def test_helix(self):
        tp = run(ramp_helix=1.5, ramp_angle=10)
        D = descent(tp)
        self.assertGreater(len(D), 20)
        # les points de la descente sont sur un cercle de rayon 1,5
        D = [p for p in D if p[2] >= -1 - 1e-9]                     # première passe
        (ax, ay, _), (bx, by, _), (qx, qy, _) = D[0], D[len(D) // 3], D[2 * len(D) // 3]
        d = 2 * (ax * (by - qy) + bx * (qy - ay) + qx * (ay - by))     # centre du cercle par trois points
        A, B, Q = ax * ax + ay * ay, bx * bx + by * by, qx * qx + qy * qy
        cx = (A * (by - qy) + B * (qy - ay) + Q * (ay - by)) / d
        cy = (A * (qx - bx) + B * (ax - qx) + Q * (bx - ax)) / d
        for x, y, _z in D:
            self.assertAlmostEqual(math.hypot(x - cx, y - cy), 1.5, 1)
        for m in tp.moves:                                          # jamais hors de la poche (rayon 1)
            if m.kind == 'feed':
                self.assertTrue(0.99 <= m.x <= 19.01 and 0.99 <= m.y <= 19.01, (m.x, m.y))

    def test_fallback(self):
        a = run(size=3.5, ramp_helix=5.0)                           # cercle trop grand : rampe le long de l'anneau
        b = run(size=3.5)
        self.assertEqual([(round(m.x, 6), round(m.y, 6), round(m.z, 6)) for m in a.moves],
                         [(round(m.x, 6), round(m.y, 6), round(m.z, 6)) for m in b.moves])

    def test_spiral(self):
        tp = run(ramp_helix=1.0, pocket_spiral=True)
        self.assertGreater(len(descent(tp)), 20)
        self.assertEqual(sum(1 for m in tp.moves if m.kind == 'plunge' and m.z < -1.5), 0)    # plongée jusqu'au fond déjà fait


if __name__ == '__main__':
    unittest.main()
