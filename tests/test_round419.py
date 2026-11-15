"""Round 419 : [E] cadre englobant sans fenêtre, marge 0."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import geom
from vectordrive.core.document import Shape

app = QApplication.instance() or QApplication([])


class TestQuickFrame(unittest.TestCase):
    def test_e(self):
        from vectordrive.ui import dialogs
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        old = dialogs.ParamsDialog
        dialogs.ParamsDialog = None                          # aucune fenêtre ne doit s'ouvrir
        try:
            self.assertEqual(w.A['bbox_frame'].shortcut().toString(), 'E')
            sq = Shape(path=geom.Path([geom.rect(0, 0, 10, 4), geom.circle((20, 2), 3)]))
            w._add_items([sq])
            w.canvas.select([sq])
            w.A['bbox_frame'].trigger()
            frame = w.canvas.selection[0]
            self.assertIsNot(frame, sq)
            self.assertEqual(tuple(round(v, 9) for v in frame.bbox()), (0, -1, 23, 5))
            self.assertEqual(len(frame.path.contours[0].segments), 4)       # rectangle, coins vifs
            w.undo()
            self.assertEqual(len(w.canvas.doc.layers[0].items), 1)
            self.assertIn('bbox_frame_options', w.A)
            from vectordrive.ui.shortcuts import TE_ACTIONS
            self.assertEqual(TE_ACTIONS['ID_ZONE_ENCOMPASS'], 'bbox_frame')
        finally:
            dialogs.ParamsDialog = old
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
