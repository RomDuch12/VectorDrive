"""Round 148 : liaisons en rampe (traits ouverts en zigzag, anneaux de
poche, angle réglable) ; finitions sans passe sur le cadre (gravure en
relief)."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.cam import model, strategies as S
from vectordrive.core import geom
from vectordrive.core.document import Document, Shape
from vectordrive.core.geom import Contour


def emitter():
    return S.Emitter(model.Operation(), model.CamTool())


def steepest(moves, start=None) -> float:
    """Plus forte descente (|dz| / déplacement horizontal) des avances."""
    worst = 0.0
    prev = start
    for m in moves:
        if prev is not None and m.kind == 'feed' and m.z < prev[2] - 1e-12:
            h = math.dist(prev[:2], (m.x, m.y))
            worst = max(worst, math.inf if h < 1e-12 else (prev[2] - m.z) / h)
        prev = (m.x, m.y, m.z)
    return worst


class TestRamps(unittest.TestCase):
    def test_open_ramp_long_stroke(self):
        em = emitter()
        pts = [(0, 0), (10, 0)]
        S.cut_chain(em, pts, False, [-0.5], ramp=True, ramp_angle=5)
        self.assertLessEqual(steepest(em.moves), math.tan(math.radians(5)) + 1e-9)
        self.assertFalse([m for m in em.moves if m.kind == 'plunge' and m.z < -1e-9])   # pas de plongée dans la matière
        self.assertEqual((em.moves[-1].x, em.moves[-1].y, em.moves[-1].z), (10, 0, -0.5))
        at_depth = [m for m in em.moves if m.kind == 'feed' and abs(m.z + 0.5) < 1e-12]
        self.assertTrue(any(abs(m.x) < 1e-12 for m in at_depth))                  # revenu au départ à la cote

    def test_open_ramp_zigzag_short_stroke(self):
        em = emitter()
        pts = [(0, 0), (2, 0)]
        S.cut_chain(em, pts, False, [-0.5], ramp=True, ramp_angle=5)              # rampe de 5,7 mm sur 2 mm
        self.assertLessEqual(steepest(em.moves), math.tan(math.radians(5)) + 1e-9)
        self.assertTrue(all(-1e-9 <= m.x <= 2 + 1e-9 for m in em.moves if m.kind == 'feed'))
        self.assertGreaterEqual(sum(1 for m in em.moves if m.kind == 'feed'), 4)
        self.assertAlmostEqual(min(m.z for m in em.moves), -0.5)

    def test_levels_and_angle(self):
        em = emitter()
        S.cut_chain(em, [(0, 0), (20, 0)], False, [-0.2, -0.4], ramp=True, ramp_angle=10)
        self.assertLessEqual(steepest(em.moves), math.tan(math.radians(10)) + 1e-9)
        self.assertAlmostEqual(min(m.z for m in em.moves), -0.4)
        self.assertEqual(S.ramp_angle_of(model.Operation()), S.RAMP_ANGLE)
        self.assertEqual(S.ramp_angle_of(model.Operation(ramp_angle=12)), 12)
        self.assertEqual(S.ramp_angle_of(model.Operation(ramp_angle=80)), 80)          # 0.921.0 : 89° au plus
        self.assertEqual(S.ramp_angle_of(model.Operation(ramp_angle=120)), 89)

    def test_no_ramp_unchanged(self):
        em = emitter()
        S.cut_chain(em, [(0, 0), (10, 0)], False, [-0.5])
        plunges = [m for m in em.moves if m.kind == 'plunge']
        self.assertEqual([m.z for m in plunges], [-0.5])                           # plongée verticale, comme avant


def doc_frame_letter():
    d = Document()
    d.plate = None
    frame = Contour(geom.rect(0, 0, 60, 30).segments, True)
    letter = geom.rect(20, 10, 10, 10)
    d.add(Shape(path=geom.Path([frame, letter]), tool=0))
    return d


def pocket(**kw):
    s = model.CamSetup()
    t = model.CamTool(name='F1', diameter=1, feed=600, number=1, step_down=0.2, stepover=0.4)
    s.tools = [t]
    op = model.Operation(kind='poche', tool_id=t.id, depth=0.4, **kw)
    s.operations = [op]
    return s, op


class TestPocket(unittest.TestCase):
    def test_pocket_ramp_no_plunge_into_material(self):
        d = doc_frame_letter()
        s, op = pocket(ramp=True, ramp_angle=8)
        tp = S.compute(d, s, op)
        self.assertTrue(tp.moves)
        prev_level = 0.0
        for m in tp.moves:
            if m.kind == 'plunge':
                self.assertGreaterEqual(m.z, -0.2 - 1e-9)                         # au plus jusqu'au niveau d'avant
        self.assertLessEqual(steepest(tp.moves), math.tan(math.radians(8)) + 1e-6)
        del prev_level

    def test_finish_skip_frame(self):
        d = doc_frame_letter()
        s, op = pocket(stock=0.1, finish=True)
        s2, op2 = pocket(stock=0.1, finish=True, finish_skip_frame=True)
        full = S.compute(d, s, op).lengths()[0]
        skip = S.compute(d, s2, op2).lengths()[0]
        frame_ring = 2 * (60 - 1 + 30 - 1)                                        # anneau de finition du cadre
        self.assertAlmostEqual(full - skip, frame_ring, delta=frame_ring * 0.15)
        reg = S.region([d.layers[0].items[0].path], 0.01).buffer(-0.5)
        self.assertEqual(len(S.rings_of(reg, True, exteriors=False)), 1)          # la lettre seulement
        self.assertEqual(len(S.rings_of(reg, True)), 2)


if __name__ == '__main__':
    unittest.main()
