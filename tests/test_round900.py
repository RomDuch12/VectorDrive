"""Round 900 : contours superposés. Décaler suit la règle pair-impair : une forme dont chaque contour est tracé deux
fois ne laisse pas de matière, ses contours comptent comme des traits (comme le calcul exact) au lieu d'être remplis.
« Superposés » a le raccourci à et agit tout de suite avec les derniers réglages (Ctrl+clic ou premier usage : la
fenêtre)."""
import math
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r900.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication

from vectordrive.core import geom, parallel, pathops
from vectordrive.core.geom import Contour, Line, Path

app = QApplication.instance() or QApplication([])

RING = (12 * 12 - (4 - math.pi)) - 8 * 8          # carré de 10 agrandi de 1 (coins ronds), moins le carré de 8


def doubled(*contours):
    return Path([c for c in contours for _ in range(2)])


class Offset(unittest.TestCase):

    def test_a_doubled_square_grows_into_a_ring(self):
        res = pathops.offset(doubled(geom.rect(0, 0, 10, 10)), 1.0)
        self.assertEqual(len(res.contours), 2)
        self.assertAlmostEqual(pathops.area(res), RING, delta=0.05)
        b = res.bbox()
        self.assertAlmostEqual(b[0], -1.0, places=2)
        self.assertAlmostEqual(b[2], 11.0, places=2)

    def test_a_doubled_square_shrinks_to_nothing(self):
        self.assertAlmostEqual(pathops.area(pathops.offset(doubled(geom.rect(0, 0, 10, 10)), -1.0)), 0.0, places=6)

    def test_like_the_exact_offset(self):
        src = doubled(geom.rect(0, 0, 10, 10), geom.rect(20, 0, 6, 4))
        res, exact = parallel.offset_checked(src, 0.5)
        self.assertTrue(exact)
        self.assertAlmostEqual(pathops.area(res), pathops.area(parallel.offset_region(src, 0.5)), delta=0.02)
        # un contour tracé une fois : la forme pleine, comme avant
        self.assertAlmostEqual(pathops.area(pathops.offset(Path([geom.rect(0, 0, 10, 10)]), 1.0)),
                               144 - (4 - math.pi), delta=0.05)

    def test_open_contours_and_a_zero_area_spike(self):
        spike = Contour([Line((0, 0), (10, 0)), Line((10, 0), (0, 0))], closed=True)
        line = Contour([Line((0, 20), (10, 20))], closed=False)
        res = pathops.offset(Path([spike, line]), 0.5)
        self.assertAlmostEqual(pathops.area(res), 2 * (10 + math.pi * 0.25), delta=0.05)
        res = pathops.offset(Path(doubled(geom.rect(0, 0, 10, 10)).contours + [line]), 1.0)
        self.assertAlmostEqual(pathops.area(res), RING + 2 * 10 + math.pi, delta=0.1)


class Window(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from vectordrive.ui.main_window import MainWindow
        cls.w = MainWindow()

    @classmethod
    def tearDownClass(cls):
        cls.w.modified = False
        cls.w.close()

    def setUp(self):
        self.w.modified = False
        self.w.new_document()
        for k in ('nettoyage/entre_calques', 'nettoyage/tolerance'):
            self.w.settings.remove(k)

    def add(self, path):
        from vectordrive.core.document import Shape
        sh = Shape(path=path, tool=0)
        self.w.canvas.doc.active_layer.items.append(sh)
        return sh

    def test_the_shortcut(self):
        from PySide6.QtGui import QKeySequence
        a = self.w.A['dedupe']
        self.assertEqual(a.shortcut(), QKeySequence('à'))
        self.assertIn('Ctrl', a.toolTip())

    def test_first_use_opens_the_window_then_it_acts_at_once(self):
        from vectordrive.ui import main_window as MW
        self.add(doubled(geom.rect(0, 0, 10, 10)))
        seen = []

        def fake_exec(dlg):
            seen.append(dlg.windowTitle())
            w_tol, w_across = self.w.last_dedupe_dialog
            w_tol.setValue(0.05)
            return 1
        with mock.patch.object(MW.QDialog, 'exec', fake_exec):
            self.w.A['dedupe'].trigger()
        self.assertEqual(len(seen), 1)
        self.assertEqual(len(self.w.canvas.doc.active_layer.items[0].path.contours), 1)
        self.assertAlmostEqual(float(self.w.settings.value('nettoyage/tolerance')), 0.05)
        self.add(doubled(geom.rect(30, 0, 10, 10)))
        with mock.patch.object(MW.QDialog, 'exec', fake_exec), \
                mock.patch.object(MW.MainWindow, '_ctrl_held', staticmethod(lambda: False)):
            self.w.A['dedupe'].trigger()                                 # les derniers réglages, sans fenêtre
        self.assertEqual(len(seen), 1)
        self.assertEqual(len(self.w.canvas.doc.active_layer.items[1].path.contours), 1)
        self.assertIn('1', self.w.statusBar().currentMessage())
        self.add(doubled(geom.rect(60, 0, 10, 10)))
        with mock.patch.object(MW.QDialog, 'exec', fake_exec), \
                mock.patch.object(MW.MainWindow, '_ctrl_held', staticmethod(lambda: True)):
            self.w.A['dedupe'].trigger()                                 # Ctrl+clic : la fenêtre
        self.assertEqual(len(seen), 2)

    def test_offset_says_the_doubled_contours(self):
        sh = self.add(doubled(geom.rect(0, 0, 10, 10)))
        self.w.canvas.select([sh])
        self.w.offset_selection({'distance': 1.0, 'join': 'round', 'count': 1, 'keep': False, 'last_only': False})
        msg = self.w.statusBar().currentMessage()
        self.assertIn('pair-impair', msg)
        self.assertIn('(à)', msg)
        items = self.w.canvas.doc.active_layer.items
        self.assertEqual(len(items), 1)
        self.assertAlmostEqual(pathops.area(items[0].path), RING, delta=0.05)


if __name__ == '__main__':
    unittest.main()
