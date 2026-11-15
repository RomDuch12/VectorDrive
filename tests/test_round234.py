"""Round 234 : vue 3D avec transparence — matière et modèle translucides,
parcours (et dessin) visibles au travers."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])


class TestTransparency(unittest.TestCase):
    def test_slider_drives_alpha(self):
        from vectordrive.ui import view3d as V3
        from vectordrive.ui.main_window import MainWindow
        self.assertIn('alpha', V3.FS)                                  # le nuanceur a l'opacité
        w = MainWindow()
        from vectordrive.core import geom
        from vectordrive.core.document import Shape
        sh = Shape(path=geom.Path([geom.rect(0, 0, 20, 10)]), tool=0)
        w.canvas.doc.add(sh)
        w.canvas.select([sh])
        w.cam_panel.new_operation('gravure', exec_dialog=False)
        w.show_toolpaths('3d')
        p = w.panel3d
        self.assertEqual(p.view.alpha, 1.0)
        p.alpha.setValue(60)                                           # 60 % de transparence
        self.assertAlmostEqual(p.view.alpha, 0.4, 6)
        p.view.set_alpha(2.0)
        self.assertEqual(p.view.alpha, 1.0)                            # bornée
        p.view.set_alpha(-1.0)
        self.assertEqual(p.view.alpha, 0.0)
        p.alpha.setValue(0)
        self.assertEqual(p.view.alpha, 1.0)                            # opaque à nouveau
        p.view.set_alpha(0.5)
        p.view.repaint()                                               # rendu (OpenGL ou repli) sans erreur
        w.show_toolpaths('2d')
        w.modified = False
        w.close()


if __name__ == '__main__':
    unittest.main()
