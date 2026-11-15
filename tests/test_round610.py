"""Round 610 : plaque codée depuis un préréglage (TauDrive : préréglages de code) — la plaque type entière
(cadres, code, texte) posée d'un coup ; un préréglage relevé sur les cadres sélectionnés, enregistré."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import codeplate as CP

app = QApplication.instance() or QApplication([])


class TestPresets(unittest.TestCase):
    def test_frames_round_trip(self):
        p = CP.Preset('P', 'datamatrix', 'Arial', 15, 7, 12, 2, 0, -5.5)
        code, text = CP.preset_frames(p, 50, 30)
        self.assertEqual(code, [42.5, 26.5, 57.5, 33.5])
        self.assertEqual(text, [44.0, 23.5, 56.0, 25.5])
        back = CP.preset_from_frames('P', code, text)
        self.assertEqual((back.code_w, back.code_h, back.text_w, back.text_h, back.text_dx, back.text_dy),
                         (15.0, 7.0, 12.0, 2.0, 0.0, -5.5))

    def test_build(self):
        g = CP.build_from_preset(CP.FACTORY[0], 'B000174', 0, 0)
        bb = g.bbox()
        self.assertLessEqual(bb[2] - bb[0], 15.0 + 1e-6)
        self.assertEqual(sum(1 for c in g.children if getattr(c, 'name', '') == 'cadre'), 2)
        self.assertEqual(g.extra['codeplate']['preset'], CP.FACTORY[0].name)

    def test_window(self):
        from vectordrive.core.document import Plate
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            w.canvas.doc.plate = Plate(x=0, y=0, width=100, height=60)
            g = w.code_plate_preset(CP.FACTORY[1].name, 'ABC123', exec_dialog=False)
            bb = g.bbox()
            self.assertAlmostEqual((bb[0] + bb[2]) / 2, 50.0, 0)               # au centre de la plaque
            w.canvas.select([])
            self.assertIsNone(w.code_plate('B1'))                              # donnée sans cadres : rien
            w.save_plate_preset(CP.Preset('Mienne', 'qr', 'Arial', 12, 12, 0, 0, 0, 0))
            names = [p.name for p in w.plate_presets()]
            self.assertEqual(names[0], 'Mienne')
            self.assertIn(CP.FACTORY[0].name, names)
            g2 = w.code_plate_preset('Mienne', 'X1', at=(10, 10), exec_dialog=False)
            self.assertEqual(sum(1 for c in g2.children if getattr(c, 'name', '') == 'cadre'), 1)   # sans texte
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
