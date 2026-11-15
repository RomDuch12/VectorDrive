"""Round 428 : fenêtres FAO en plein écran translucide, molette au dessin."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])


def wheel(target, global_pos, mods=Qt.KeyboardModifier.NoModifier):
    local = target.mapFromGlobal(global_pos)
    ev = QWheelEvent(QPointF(local), QPointF(global_pos), QPoint(0, 0), QPoint(0, 120), Qt.MouseButton.NoButton,
                     mods, Qt.ScrollPhase.NoScrollPhase, False)
    QApplication.sendEvent(target, ev)


class TestOverlay(unittest.TestCase):
    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.w.resize(1200, 800)
        self.w.show()
        app.processEvents()

    def tearDown(self):
        for k in ('paths', 'palette'):
            self.w.toggle_overlay(k, False)
        self.w.settings.setValue('vue/panneau_fao', False)
        self.w.modified = False
        self.w.close()

    def test_full_and_opacity(self):
        ov = self.w.overlays['paths']
        self.assertTrue(self.w.toggle_overlay('paths'))
        d = self.w.dock_paths
        app.processEvents()
        self.assertTrue(d.isFloating())
        st = self.w.stage                                                   # tout le plan de travail
        self.assertEqual(d.geometry().topLeft(), st.mapToGlobal(st.rect().topLeft()))
        self.assertEqual(d.geometry().height(), st.height())
        self.assertGreaterEqual(d.geometry().width(), st.width())           # au moins (largeur mini du panneau)
        ov.set_opacity(0.4)
        self.assertAlmostEqual(d.windowOpacity(), 0.4, places=2)
        ov.set_opacity(0.05)
        self.assertAlmostEqual(d.windowOpacity(), 0.25, places=2)            # jamais illisible
        self.assertFalse(self.w.toggle_overlay('paths'))
        self.assertFalse(d.isFloating())
        self.assertEqual(d.windowOpacity(), 1.0)
        self.assertAlmostEqual(ov.opacity(), 0.25, places=2)                 # retenue

    def test_wheel_zooms_canvas(self):
        self.w.toggle_overlay('paths')
        app.processEvents()
        c = self.w.canvas
        s0 = c.scale
        bar = self.w.overlays['paths']._bar
        wheel(bar, bar.mapToGlobal(QPoint(5, 5)))                          # sur la barre : le dessin zoome
        self.assertNotEqual(c.scale, s0)
        s1 = c.scale
        ops = self.w.cam_panel.ops
        wheel(ops.viewport(), ops.viewport().mapToGlobal(QPoint(5, 5)))    # sur une liste : elle défile
        self.assertEqual(c.scale, s1)
        wheel(ops.viewport(), ops.viewport().mapToGlobal(QPoint(5, 5)), Qt.KeyboardModifier.ControlModifier)
        self.assertNotEqual(c.scale, s1)                                    # Ctrl : toujours le dessin

    def test_actions(self):
        self.assertIn('overlay_paths', self.w.A)
        self.w.A['overlay_palette'].trigger()
        self.assertTrue(self.w.overlays['palette'].active)
        self.assertTrue(self.w.dock_cam.isFloating())


if __name__ == '__main__':
    unittest.main()
