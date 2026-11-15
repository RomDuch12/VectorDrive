"""Round 902 : détourage intérieur aux angles arrondis. Une île plus petite que l'arrondi, que l'arrondi boucherait, est
gardée telle quelle : l'outil en fait le tour sans l'arrondir. Le parcours la signale (avertissement, zone orange avec
le parcours, fenêtre d'information une fois par calcul) ; la session garde les zones."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r902.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

import shapely
from shapely.geometry import Polygon, box

from vectordrive.cam import model as M
from vectordrive.cam import strategies as S
from vectordrive.core import geom
from vectordrive.core.document import Document, Layer, Plate, Shape


def square(x0, y0, x1, y1):
    return geom.polyline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], closed=True)


def drawing(*contours):
    doc = Document()
    layer = Layer(name='Plan 1', items=[Shape(path=geom.Path(list(contours)))])
    doc.layers[:] = [layer]
    doc.active = layer.id
    doc.plate = Plate(width=300, height=200)
    return doc


TOOL = M.CamTool(name='F1', diameter=1.0, step_down=1.0)
SMALL = (18.3, 18.3, 21.7, 21.7)                   # île de 3,4 mm
BIG = (5.0, 5.0, 12.0, 12.0)                       # île de 7 mm


def contour(doc, ra=2.0, side='interieur'):
    setup = M.CamSetup(tools=[TOOL])
    op = M.Operation(kind='contour', tool_id=TOOL.id, side=side, depth=0.5, corner_round=ra)
    setup.operations = [op]
    return S.compute(doc, setup, op, (0.0, 0.0))


def cuts(tp):
    return [shapely.Point(m.x, m.y) for m in tp.moves if m.kind != 'rapid' and m.z < -1e-6]


class Strategy(unittest.TestCase):

    def test_a_small_island_is_kept_and_said(self):
        tp = contour(drawing(square(0, 0, 40, 40), square(*SMALL)))
        island = box(*SMALL)
        pts = cuts(tp)
        self.assertTrue(pts)
        self.assertGreater(min(island.distance(p) for p in pts), 0.5 - 0.02)      # l'outil fait le tour, à son rayon
        self.assertLess(min(island.distance(p) for p in pts), 0.5 + 0.02)
        self.assertEqual(len(tp.zones), 1)
        self.assertEqual(tp.zones[0]['kind'], 'ile')
        self.assertTrue(Polygon(tp.zones[0]['pts']).equals_exact(island, 1e-3) or
                        abs(Polygon(tp.zones[0]['pts']).symmetric_difference(island).area) < 1e-3)
        self.assertTrue(any('île' in w and 'arrondi' in w for w in tp.warnings))

    def test_a_big_island_is_rounded_not_said(self):
        tp = contour(drawing(square(0, 0, 40, 40), square(*BIG)))
        self.assertEqual(tp.zones, [])
        self.assertFalse(any('île' in w for w in tp.warnings))
        corner = shapely.Point(BIG[0], BIG[1])                           # coin de l'île arrondi : l'outil s'en approche
        self.assertLess(min(corner.distance(p) for p in cuts(tp)), 2.0 + 0.5 + 0.05)

    def test_only_the_small_one_of_two(self):
        tp = contour(drawing(square(0, 0, 40, 40), square(*SMALL), square(*BIG)))
        self.assertEqual(len(tp.zones), 1)
        self.assertIn('1 île(s)', ' '.join(tp.warnings))

    def test_without_rounding_or_outside_nothing_said(self):
        doc = drawing(square(0, 0, 40, 40), square(*SMALL))
        self.assertEqual(contour(doc, ra=0.0).zones, [])
        self.assertEqual(contour(doc, side='exterieur').zones, [])
        self.assertEqual(S.keep_small_islands(M.Toolpath('', ''), box(0, 0, 9, 9), box(0, 0, 9, 9), 2.0), box(0, 0, 9, 9))


class Window(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])
        from vectordrive.ui.main_window import MainWindow
        cls.w = MainWindow()

    @classmethod
    def tearDownClass(cls):
        cls.w.modified = False
        cls.w.close()

    def test_highlighted_and_told_once(self):
        cp = self.w.cam_panel
        tp = contour(drawing(square(0, 0, 40, 40), square(*SMALL)))
        tp.name = 'Découpe'
        cp.display([tp])
        lines = cp.announce_zones()
        self.assertEqual(len(lines), 1)
        self.assertIn('Découpe', lines[0])
        self.assertTrue(cp.zones_box.isVisible())
        self.assertFalse(cp.zones_box.isModal())
        cp.zones_box.close()
        self.assertEqual(cp.announce_zones(), [])                        # une fois par calcul
        canvas = self.w.canvas
        self.assertTrue(any(getattr(t, 'zones', None) for t, _c in canvas.toolpaths))
        self.assertFalse(canvas.grab().isNull())                         # dessin de la zone
        cp.display([])

    def test_the_session_keeps_the_zones(self):
        from vectordrive.ui import session
        tp = contour(drawing(square(0, 0, 40, 40), square(*SMALL)))
        back = session.paths_from_bytes(session.paths_bytes([tp]))[0]
        self.assertEqual(back.zones, tp.zones)
        self.assertTrue(back.zones)


if __name__ == '__main__':
    unittest.main()
