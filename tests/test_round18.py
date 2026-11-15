"""Round 18 : rotation libre et échelle (F2), fichiers récents, récupération."""
import math
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from vectordrive.core import geom
from vectordrive.core.document import Shape
from vectordrive.core.geom import Path


class TestWindow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        from PySide6.QtCore import QSettings
        self.tmp = tempfile.TemporaryDirectory()
        self.w = MainWindow()
        # réglages d'essai : jamais ceux de l'utilisateur
        self.w.settings = QSettings(str(pathlib.Path(self.tmp.name) / 'essai.ini'), QSettings.Format.IniFormat)

    def tearDown(self):
        self.w.modified = False
        self.w.close()
        self.tmp.cleanup()

    def test_rotate_and_scale_fields(self):
        w = self.w
        sh = w.canvas.doc.add(Shape(path=Path([geom.rect(0, 0, 20, 10)])))
        w.canvas.select([sh])
        w.dims.rot.setValue(90)
        w.dims._rotate()
        bb = w.canvas.selection_bbox()
        self.assertAlmostEqual(bb[2] - bb[0], 10, places=9)
        self.assertAlmostEqual(bb[3] - bb[1], 20, places=9)
        self.assertAlmostEqual((bb[0] + bb[2]) / 2, 10, places=9)       # autour du centre
        self.assertEqual(w.dims.rot.value(), 0)
        w.dims.scale.setValue(50)
        w.dims._scale()
        bb = w.canvas.selection_bbox()
        self.assertAlmostEqual(bb[3] - bb[1], 10, places=9)
        self.assertEqual(w.dims.scale.value(), 100)
        w.undo()
        w.undo()
        self.assertAlmostEqual(w.canvas.doc.layers[0].items[0].bbox()[2], 20, places=9)

    def test_recent(self):
        w = self.w
        for k in range(15):
            w._add_recent(f'C:/x/{k}.vdz')
        w._add_recent('C:/x/3.vdz')
        lst = w._recent()
        self.assertEqual(len(lst), w.RECENT_MAX)
        self.assertEqual(pathlib.Path(lst[0]), pathlib.Path('C:/x/3.vdz'))
        self.assertEqual(sum(1 for p in lst if pathlib.Path(p) == pathlib.Path('C:/x/3.vdz')), 1)

    def test_autosave_cycle(self):
        w = self.w
        d = pathlib.Path(self.tmp.name)
        w._recovery_dir = lambda: d
        w.session_dir = None                           # récupération sans session (avec elle : la session, round 215)
        w.start_autosave()
        w.canvas.doc.add(Shape(path=Path([geom.circle((0, 0), 5)])))
        w.modified = True
        w._autosave(wait=True)
        f = d / f'{w._pid}.vdz'
        self.assertTrue(f.exists())
        from vectordrive.io import registry
        self.assertEqual(registry.open_document(f).stats()['contours'], 1)
        w._clear_autosave()
        self.assertFalse(f.exists())


if __name__ == '__main__':
    unittest.main()
