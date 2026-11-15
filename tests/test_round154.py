"""Round 154 : laser à la TauDrive — oscillation du faisceau, passages
répétés, remplissage tourné à chaque passage, croisé, en retrait ; cadence
du scanner vérifiée, export Cielle refusé au-delà."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.cam import model, strategies as S, wobble as W
from vectordrive.core import geom
from vectordrive.core.document import Document, Shape


def doc_with(*contours):
    d = Document()
    d.plate = None
    for c in contours:
        d.add(Shape(path=geom.Path([c]), tool=0))
    return d


def laser_setup(feed=1000.0, **op):
    s = model.CamSetup()
    t = model.CamTool(name='Laser', kind='laser', diameter=0.05, power=50, frequency=20, feed=feed, cut_length=0)
    s.tools = [t]
    o = model.Operation(tool_id=t.id, **op)
    s.operations = [o]
    return s, o


def feed_length(tp):
    pos, total = None, 0.0
    for m in tp.moves:
        if m.kind == 'feed' and pos is not None:
            total += math.hypot(m.x - pos[0], m.y - pos[1])
        pos = (m.x, m.y)
    return total


class TestWobble(unittest.TestCase):
    def test_polyline(self):
        square = [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]
        out = W.apply_polyline(square, 0.1, 0.2, 'circle')
        self.assertEqual(out[0], (0, 0))
        self.assertEqual(out[-1], (0, 0))                         # contour toujours fermé
        self.assertGreater(len(out), 40 * 16 / 0.2 * 0.9)
        dist = max(min(abs(y), abs(x - 10), abs(y - 10), abs(x)) for x, y in out)
        self.assertLessEqual(dist, 0.1 + 1e-9)
        self.assertEqual(W.apply_polyline(square, 0, 0.2, 'circle'), [tuple(p) for p in square])

    def test_phase_follows_length(self):
        one = W.apply_polyline([(0, 0), (5, 0)], 0.1, 0.5, 'transverse')
        many = W.apply_polyline([(i * 0.05, 0) for i in range(101)], 0.1, 0.5, 'transverse')

        def turns(pts):
            return sum(1 for a, b in zip(pts, pts[1:]) if a[1] > 0 >= b[1])
        self.assertEqual(turns(one), turns(many))
        self.assertEqual(turns(one[:-1]), 10)                    # dix tours ; le dernier point revient sur le trait

    def test_scanner(self):
        self.assertAlmostEqual(W.scanner_hz(80000, 0.1), 13333.33, places=1)
        self.assertEqual(W.max_speed(0.1), 3000.0)
        self.assertEqual(W.check(3000, 0.1, 0.1), [])
        self.assertEqual([lv for lv, _t in W.check(4000, 0.1, 0.1)], ['attention'])
        self.assertEqual(W.check(36000, 0.1, 0.1)[0][0], 'bloquant')
        self.assertIn('festonnée', W.check(1000, 0.5, 0.1)[0][1])
        self.assertAlmostEqual(W.length_factor(0.1, 0.1), math.hypot(0.55, 0.1) / 0.1)
        self.assertEqual(W.length_factor(0.1, 0.1, 'none'), 1.0)


class TestStrategies(unittest.TestCase):
    def test_wobble_in_compute(self):
        d = doc_with(geom.rect(0, 0, 10, 5))
        s, op = laser_setup(kind='laser')
        plain = S.compute(d, s, op)
        op.wobble, op.wobble_amplitude, op.wobble_pitch = 'circle', 0.1, 0.1
        tp = S.compute(d, s, op)
        self.assertEqual(tp.warnings, [])                          # 1 m/min : 167 Hz
        self.assertGreater(len(tp.moves), 10 * len(plain.moves))
        self.assertGreater(feed_length(tp), 4 * feed_length(plain))
        op.feed = 80000
        tp = S.compute(d, s, op)
        self.assertTrue(tp.warnings[0].startswith('BLOQUANT'))


    def test_passes(self):
        d = doc_with(geom.rect(0, 0, 10, 5))
        s, op = laser_setup(kind='laser')
        one = feed_length(S.compute(d, s, op))
        op.laser_passes = 3
        self.assertAlmostEqual(feed_length(S.compute(d, s, op)), 3 * one, places=6)
        d2 = doc_with(geom.polyline([(0, 0), (10, 0)]))                          # trait ouvert : chaque passage repart du début
        s2, op2 = laser_setup(kind='laser', laser_passes=2)
        self.assertAlmostEqual(feed_length(S.compute(d2, s2, op2)), 20.0, places=6)
        s3, op3 = laser_setup(kind='laser_decoupe', side='exterieur')
        cut = feed_length(S.compute(d, s3, op3))
        op3.laser_passes = 2
        self.assertAlmostEqual(feed_length(S.compute(d, s3, op3)), 2 * cut, places=4)

    def test_fill_rotation_cross_inset(self):
        d = doc_with(geom.rect(0, 0, 10, 10))

        def directions(tp):
            out, pos = set(), None
            for m in tp.moves:
                if m.kind == 'feed' and pos is not None and math.hypot(m.x - pos[0], m.y - pos[1]) > 1:
                    out.add('h' if abs(m.y - pos[1]) < 1e-6 else 'v' if abs(m.x - pos[0]) < 1e-6 else 'o')
                pos = (m.x, m.y)
            return out
        s, op = laser_setup(kind='laser_gravure', resolution=0.5)
        self.assertEqual(directions(S.compute(d, s, op)), {'h'})
        op.laser_passes, op.hatch_step = 2, 90.0
        self.assertEqual(directions(S.compute(d, s, op)), {'h', 'v'})
        op.laser_passes, op.hatch_step, op.hatch_cross = 1, 0.0, True
        self.assertEqual(directions(S.compute(d, s, op)), {'h', 'v'})
        op.hatch_cross, op.hatch_inset = False, 1.0
        xs = [m.x for m in S.compute(d, s, op).moves if m.kind == 'feed']
        self.assertGreaterEqual(min(xs), 1.0 - 1e-6)
        self.assertLessEqual(max(xs), 9.0 + 1e-6)
        op.hatch_inset = 6.0                                      # plus large que la forme : remplissage d'origine
        xs = [m.x for m in S.compute(d, s, op).moves if m.kind == 'feed']
        self.assertLess(min(xs), 0.5)


class TestForm(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_laser_section(self):
        from vectordrive.ui import cam_panel
        s, op = laser_setup(kind='laser_gravure')
        d = cam_panel.FieldsDialog(None, 'Opération', op, Document(), s.tools)
        for n in ('hatch_step', 'hatch_cross', 'hatch_inset', 'wobble', 'laser_passes', 'finish'):
            self.assertFalse(d.rows[n][1].isHidden(), n)
        w = d.widgets['wobble']
        self.assertEqual([w.itemData(i) for i in range(w.count())], list(W.SHAPES))
        w.setCurrentIndex(w.findData('eight'))
        d.apply()
        self.assertEqual(op.wobble, 'eight')
        d.widgets['kind'].setCurrentIndex(d.widgets['kind'].findData('contour'))
        self.assertTrue(d.rows['wobble'][1].isHidden())
        self.assertTrue(d.rows['hatch_step'][1].isHidden())


if __name__ == '__main__':
    unittest.main()
