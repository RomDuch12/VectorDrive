"""Round 32 : règles graduées, guides et accrochage aux guides."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from vectordrive.core import snap as S


class TestTicks(unittest.TestCase):
    def test_steps(self):
        from vectordrive.ui.rulers import tick_steps
        self.assertEqual(tick_steps(3.0), (2, 20))            # 3 px/mm : chiffres tous les 20 mm
        self.assertEqual(tick_steps(30.0), (0.2, 2))
        minor, major = tick_steps(0.05)
        self.assertGreaterEqual(major * 0.05, 60)
        self.assertGreaterEqual(minor * 0.05, 6)


class TestGuideSnap(unittest.TestCase):
    def test_guides(self):
        sn = S.Snap(enabled=True, modes={'guide'})
        sn.guides = [['v', 10.0], ['h', 20.0]]
        self.assertEqual((sn.query(10.3, 50, 1.0, []).x, sn.query(10.3, 50, 1.0, []).kind), (10.0, 'guide'))
        h = sn.query(10.4, 19.7, 1.0, [])
        self.assertEqual((h.x, h.y), (10.0, 20.0))             # croisement de deux guides
        self.assertIsNone(sn.query(15, 25, 1.0, []))

    def test_object_snap_first(self):
        from vectordrive.core import geom
        from vectordrive.core.document import Shape
        from vectordrive.core.geom import Path
        sn = S.Snap(enabled=True)
        sn.guides = [['v', 10.2]]
        r = Shape(path=Path([geom.rect(10, 0, 5, 5)]))
        self.assertEqual(sn.query(10.1, 0.1, 1.0, [r]).kind, 'node')


class TestWindow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.w.resize(1000, 700)
        self.w.show()
        self.app.processEvents()

    def tearDown(self):
        self.w.modified = False
        self.w.close()

    def test_drag_move_delete_and_save(self):
        from PySide6.QtCore import QPoint, QPointF
        from PySide6.QtTest import QTest
        from PySide6.QtCore import Qt
        c = self.w.canvas
        c.snap.enabled = False
        c.add_guide('v', 50.0)
        self.assertTrue(self.w.modified)
        sx = int(round(c.to_screen(50, 0).x()))
        self.assertEqual(c.guide_at(QPointF(sx + 2, 100)), 0)
        # déplacer le guide
        QTest.mousePress(c, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(sx, 200))
        QTest.mouseMove(c, QPoint(sx + 30, 210))
        QTest.mouseRelease(c, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(sx + 30, 210))
        self.assertAlmostEqual(c.guides[0][1], c.to_doc(QPointF(sx + 30, 210))[0], places=6)   # suit le curseur
        # enregistré dans le VDZ et relu
        from vectordrive.io import registry
        with tempfile.TemporaryDirectory() as tmp:
            f = pathlib.Path(tmp) / 'g.vdz'
            registry.save_document(c.doc, f)
            back = registry.open_document(f)
        self.assertEqual(back.extra.get('guides'), [['v', c.guides[0][1]]])
        # ramené hors du canevas : supprimé
        sx = int(round(c.to_screen(c.guides[0][1], 0).x()))
        QTest.mousePress(c, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(sx, 200))
        QTest.mouseMove(c, QPoint(-5, 200))
        QTest.mouseRelease(c, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(-5, 200))
        self.assertEqual(c.guides, [])

    def test_drag_from_ruler(self):
        from PySide6.QtCore import QPoint, QPointF, Qt
        from PySide6.QtTest import QTest
        w, c = self.w, self.w.canvas
        c.snap.enabled = False
        r = w.ruler_v                                          # règle de gauche : guide vertical
        target = r.mapFromGlobal(c.mapToGlobal(QPoint(300, 200)))
        QTest.mousePress(r, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(10, 200))
        QTest.mouseMove(r, target)
        self.assertIsNotNone(c.guide_preview)
        QTest.mouseRelease(r, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, target)
        self.assertEqual(len(c.guides), 1)
        self.assertEqual(c.guides[0][0], 'v')
        self.assertAlmostEqual(c.guides[0][1], c.to_doc(QPointF(300, 200))[0], places=6)
        self.assertIsNone(c.guide_preview)

    def test_rulers_toggle_and_clear(self):
        w = self.w
        w.A['rulers'].setChecked(False)
        self.assertFalse(w.ruler_h.isVisible())
        w.A['rulers'].setChecked(True)
        self.assertTrue(w.ruler_h.isVisible())
        w.canvas.add_guide('h', 3.0)
        w.canvas.add_guide('v', 4.0)
        w.clear_guides()
        self.assertEqual(w.canvas.guides, [])
        w.ruler_h.grab()                                       # dessin des graduations
        w.ruler_v.grab()


if __name__ == '__main__':
    unittest.main()
