"""Round 151 : opérations de NeoDrive, 2e partie — surfaçage ; cercles et
rectangles reconnus dans les poches et les détourages (cycles des machines)."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.cam import model, strategies as S
from vectordrive.core import geom
from vectordrive.core.document import Document, Plate, Shape
from vectordrive.core.geom import Affine


def doc_of(*contours, plate=None):
    d = Document()
    d.plate = plate
    for c in contours:
        d.add(Shape(path=geom.Path([c]), tool=0))
    return d


def run(doc, kind, **kw):
    s = model.CamSetup()
    t = model.CamTool(name='F2', diameter=2, number=1, step_down=0.5, stepover=0.4, cut_length=10)
    s.tools = [t]
    op = model.Operation(kind=kind, tool_id=t.id, **kw)
    s.operations = [op]
    return S.compute(doc, s, op)


class TestRectOf(unittest.TestCase):
    def test_shapes(self):
        from vectordrive.core.holes import rect_of
        sh = Shape(path=geom.Path([geom.rect(10, 20, 40, 30)]))
        self.assertEqual(rect_of(sh), (30.0, 35.0, 40.0, 30.0, 0.0))
        x, y, w, h, r = rect_of(Shape(path=geom.Path([geom.rect(0, 0, 40, 30, 5)])))
        self.assertEqual((x, y, w, h), (20.0, 15.0, 40.0, 30.0))
        self.assertAlmostEqual(r, 5.0, places=4)
        slanted = geom.rect(0, 0, 40, 30).transformed(Affine.rotation(10, (0, 0)))
        self.assertIsNone(rect_of(Shape(path=geom.Path([slanted]))))
        tri = geom.Contour([geom.Line((0, 0), (10, 0)), geom.Line((10, 0), (10, 10)), geom.Line((10, 10), (0, 0))],
                           True)
        self.assertIsNone(rect_of(Shape(path=geom.Path([tri]))))


class TestCycles(unittest.TestCase):
    def test_pocket_circle_and_rect(self):
        tp = run(doc_of(geom.circle((10, 10), 4), geom.rect(30, 0, 20, 10, 2)), 'poche', depth=1.0, stock=0.1)
        kinds = [c['kind'] for c in tp.cycles]
        self.assertEqual(sorted(kinds), ['poche_cercle', 'poche_rectangle'])
        circ = next(c for c in tp.cycles if c['kind'] == 'poche_cercle')
        self.assertEqual((circ['x'], circ['y'], circ['diameter'], circ['depth'], circ['stepover']),
                         (10.0, 10.0, 8.0, 1.0, 40))
        self.assertTrue(tp.moves)                                          # les mouvements restent calculés

    def test_nested_or_free_shapes_no_cycles(self):
        frame_and_letter = doc_of(geom.rect(0, 0, 60, 30), geom.rect(20, 10, 10, 10))
        self.assertEqual(run(frame_and_letter, 'poche', depth=0.5).cycles, [])
        star = geom.polygon((0, 0), 10, 5)
        self.assertEqual(run(doc_of(star), 'poche', depth=0.5).cycles, [])

    def test_contour_sides_and_tabs(self):
        tp = run(doc_of(geom.rect(0, 0, 40, 20)), 'contour', depth=2, side='interieur')
        self.assertEqual(tp.cycles[0]['kind'], 'decoupe_rectangle')
        self.assertEqual(tp.cycles[0]['side'], 'Inside')
        tp = run(doc_of(geom.circle((0, 0), 5)), 'contour', depth=2, side='exterieur')
        self.assertEqual((tp.cycles[0]['kind'], tp.cycles[0]['side']), ('decoupe_cercle', 'Outside'))
        self.assertEqual(run(doc_of(geom.rect(0, 0, 40, 20)), 'contour', depth=2, tabs=2).cycles, [])


class TestFacing(unittest.TestCase):
    def test_plate_facing(self):
        d = doc_of(plate=Plate(100, 50))
        tp = run(d, 'surfacage', depth=0.4, extension=1.0)
        feeds = [m for m in tp.moves if m.kind == 'feed']
        xs, ys = [m.x for m in feeds], [m.y for m in feeds]
        self.assertAlmostEqual(min(xs), -2.0)                              # débordement 1 + rayon 1
        self.assertAlmostEqual(max(xs), 102.0)
        self.assertAlmostEqual(min(ys), -2.0)
        self.assertAlmostEqual(max(ys), 52.0)
        self.assertTrue(all(abs(m.z + 0.4) < 1e-9 for m in feeds))
        c = tp.cycles[0]
        self.assertEqual((c['kind'], c['width'], c['height'], c['x'], c['y']), ('surfacage_rectangle', 100, 50, 50, 25))
        # passes espacées du recouvrement (0,4 × Ø2), en aller-retour
        rows = sorted({round(m.y, 6) for m in feeds})
        gaps = [b - a for a, b in zip(rows, rows[1:])]
        self.assertLessEqual(max(gaps), 0.8 + 1e-9)

    def test_angle(self):
        d = doc_of(plate=Plate(40, 40))
        tp = run(d, 'surfacage', depth=0.2, face_angle=90)
        feeds = [m for m in tp.moves if m.kind == 'feed']
        moves = [(b.x - a.x, b.y - a.y) for a, b in zip(feeds, feeds[1:]) if math.dist((a.x, a.y), (b.x, b.y)) > 5]
        self.assertTrue(all(abs(dx) < 1e-6 for dx, _dy in moves))         # passes verticales

    def test_circle_facing(self):
        tp = run(doc_of(geom.circle((5, 5), 10)), 'surfacage', depth=0.2, extension=0.5)
        self.assertEqual(tp.cycles[0]['kind'], 'surfacage_cercle')
        self.assertEqual(tp.cycles[0]['diameter'], 20)


if __name__ == '__main__':
    unittest.main()
