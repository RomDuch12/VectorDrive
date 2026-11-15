"""Round 451 : 3D — trajectoires en un seul tracé, une couleur par parcours (légende), zoom vers le
curseur, vue par-dessous, clavier, grille au sol et cotes, image de la vue ; visualiseur : les
trajectoires du programme (pas le dessin)."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

from vectordrive.cam.model import Move, Toolpath
from vectordrive.ui import view3d as V

app = QApplication.instance() or QApplication([])


def tp(name, dx=0.0):
    t = Toolpath(op_id='', tool_id='', name=name)
    t.moves = [Move('rapid', dx, 0, 5), Move('plunge', dx, 0, -1), Move('feed', dx + 10, 0, -1),
               Move('rapid', dx + 10, 0, 5), Move('rapid', dx, 10, 5), Move('plunge', dx, 10, -1),
               Move('feed', dx + 10, 10, -1)]
    return t


class TestBatch(unittest.TestCase):
    def test_one_array_and_colors(self):
        arr, ranges = V.path_batch([tp('A'), tp('B', 20)], rapids=False)
        self.assertEqual(arr.shape[1], 9)
        self.assertEqual(len(ranges), 4)                                          # 2 avances par parcours
        self.assertEqual(sum(n for _f, n in ranges), len(arr))
        cols = {tuple(round(float(c), 3) for c in arr[f, 6:9]) for f, _n in ranges}
        self.assertEqual(len(cols), 2)                                            # une couleur par parcours
        mono, _r = V.path_batch([tp('A'), tp('B', 20)], colors=False)
        self.assertEqual(len({tuple(map(float, mono[i, 6:9])) for i in range(len(mono))}), 1)
        withr, r2 = V.path_batch([tp('A')], rapids=True)
        self.assertGreater(len(r2), 2)
        self.assertEqual(len(r2), 3)                                              # rapide, avance, rapide, avance (sans le point seul du départ)

    def test_grid(self):
        g, step = V.grid_lines(0, 0, 120, 60, -3)
        self.assertEqual(step, 10)
        self.assertTrue((g[:, 2] == -3).all())
        self.assertLessEqual(g[:, 0].min(), -10)
        self.assertGreaterEqual(g[:, 0].max(), 130)


class TestView(unittest.TestCase):
    def test_navigation_and_overlay(self):
        from vectordrive.cam import relief as RL
        from vectordrive.core.document import Document
        v = V.View3D()
        v.resize(400, 300)
        r = RL.from_paths(Document(), [tp('Ébauche'), tp('Finition', 20)], cut=False)
        v.set_relief(r)
        lines = [t.split('  — ')[0] for t, _c in v.overlay_lines()]
        self.assertTrue(lines[0].startswith('X '))
        self.assertIn('Ébauche', lines)
        self.assertIn('Finition', lines)
        pan0 = QPointF(v.pan.x(), v.pan.y())
        v.zoom_at(2.0, QPointF(200, 150))                                         # au centre : pas de décalage
        self.assertAlmostEqual(v.zoom, 2.0)
        self.assertAlmostEqual(v.pan.x(), pan0.x(), places=6)
        v.zoom_at(1.5, QPointF(390, 150))                                         # à droite : la vue suit
        self.assertGreater(abs(v.pan.x()) + abs(v.pan.y()), 1e-3)
        v.rotate(dpitch=-200)
        self.assertAlmostEqual(v.pitch, -89.9)                                    # par-dessous
        v.keyPressEvent(QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_7, Qt.KeyboardModifier.KeypadModifier))
        self.assertEqual((v.yaw, v.pitch), V.VIEWS['dessus'])
        v.keyPressEvent(QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_5, Qt.KeyboardModifier.KeypadModifier))
        self.assertTrue(v.ortho)
        v.keyPressEvent(QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Left, Qt.KeyboardModifier.NoModifier))
        self.assertAlmostEqual(v.yaw, (V.VIEWS['dessus'][0] + 15) % 360)
        p = pathlib.Path(tempfile.mkdtemp()) / 'v.png'
        self.assertTrue(v.save_image(str(p)))
        self.assertTrue(p.exists())
        v.deleteLater()


class TestViewer(unittest.TestCase):
    def test_program_shown_not_drawing(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            p = pathlib.Path(tempfile.mkdtemp()) / 'p.nc'
            p.write_text('G0 X0 Y0 Z5\nG1 Z-1\nG1 X150 Y80\nG0 Z5\n', encoding='ascii')
            w.view_nc_program(str(p))
            self.assertEqual(w.panel3d.source.currentData(), 'parcours')
            x0, y0, _z0, x1, y1, _z1 = w.panel3d.view.bounds()
            self.assertGreaterEqual(x1, 150)                                      # la zone couvre le programme
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
