"""Round 598 : faces et contours choisis sur une prise montrée (corps seul, retourné) — l'usinage créé
reprend cette prise, et ses contours, gardés dans le repère du dessin, retombent au même endroit."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import numpy as np
from PySide6.QtWidgets import QApplication

from tests.test_round596 import two_boxes_stl
from vectordrive.cam import mill3d, model
from vectordrive.core import solids as SO

app = QApplication.instance() or QApplication([])


@unittest.skipUnless(SO.available(), 'manifold3d absent')
class TestPosedSelection(unittest.TestCase):
    def test_contours_on_posed_body(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            w.open_path(two_boxes_stl())
            cp = w.cam_panel
            w._ensure_panel3d()
            p = w.panel3d
            p.refresh()
            s = cp.setup()
            s.operations.append(model.Operation(kind='surface3d', setup_face='-Z', body3d=1))
            cp.save(s)
            p.refresh()
            p.setup_view.setCurrentIndex(p.setup_view.findData('-Z|1'))
            self.assertEqual(p.current_setup(), ('-Z', 1))
            posed = [[42.0, -8.0, -4.0], [48.0, -8.0, -4.0], [48.0, -2.0, -4.0], [42.0, -2.0, -4.0]]
            p.view.select_mode = 'contours'
            p.view.set_selection(loops=[posed])
            o = p.machine_selection('surface3d', exec_dialog=False)
            self.assertEqual((o.setup_face, o.body3d), ('-Z', 1))
            np.testing.assert_allclose(o.contours3d[0][0], [42.0, 8.0, 4.0], atol=1e-6)   # repère du dessin
            back = mill3d.zone_op(w.canvas.doc, o)
            np.testing.assert_allclose(back.contours3d[0], posed, atol=1e-6)            # la prise : comme choisi
            p.view.select_mode = 'faces'
            f = int(p.view.model.face_ids()[0])                              # une face du corps montré
            p.view.set_selection(faces=[f])
            o2 = p.machine_selection('surface3d', exec_dialog=False)
            self.assertEqual((o2.setup_face, o2.body3d, o2.faces3d), ('-Z', 1, [f]))
            p.view.set_selection(faces=[10 ** 6])                             # face absente : profondeur 0
            self.assertEqual(p.selection_depth(), 0.0)
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
