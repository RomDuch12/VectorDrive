"""Round 476 : schéma de l'opération — rampe à son vrai angle, zigzag si elle est plus longue que la place."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.cam import model

app = QApplication.instance() or QApplication([])


class TestRampPreview(unittest.TestCase):
    def dialog(self, w, angle):
        from vectordrive.ui.cam_panel import FieldsDialog
        op = model.Operation(kind='contour', ramp=True, ramp_angle=angle, depth=1.0, step_down=0.5)
        return FieldsDialog(w.cam_panel, 'Essai', op, doc=w.canvas.doc, tools=[])

    def test_true_angle(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            d = self.dialog(w, 30.0)
            ill = d.illustration
            self.assertEqual(ill.ramp_angle(), 30.0)
            segs = ill.ramp_segments(0.0, 1000.0, 0.0, 100.0, 0.5)              # 0,5 mm à 100 px/mm
            self.assertEqual(len(segs), 1)
            xa, ya, xb, yb = segs[0]
            self.assertAlmostEqual(math.degrees(math.atan2(yb - ya, xb - xa)), 30.0, places=6)
            d.widgets['ramp_angle'].setValue(0.0)                                # 0 : 5° comme le calcul
            self.assertEqual(ill.ramp_angle(), 5.0)
            segs = ill.ramp_segments(0.0, 100.0, 0.0, 100.0, 0.5)               # 571 px de long : zigzag
            self.assertGreater(len(segs), 5)
            self.assertAlmostEqual(segs[-1][3], 50.0)                            # au fond de la passe
            self.assertTrue(all(0.0 - 1e-6 <= x <= 100.0 + 1e-6 for s in segs for x in (s[0], s[2])))
            ill.resize(300, 400)
            ill.grab()                                                           # se dessine sans erreur
            d.reject()
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
