"""Round 315 : mesure de volume (TypeEdit : FAO ▸ Mesure de volume) — volume
des reliefs choisis, sinon matière enlevée par les parcours ; commandes
TypeEdit 13 reliées (balayage avancé, surface en TypeArt, enroulement)."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import numpy as np
from PySide6.QtWidgets import QApplication

from vectordrive.core import galbe as GB
from vectordrive.ui import shortcuts as SC

app = QApplication.instance() or QApplication([])


class TestVolume(unittest.TestCase):
    def test_relief(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            H = np.zeros((100, 100))
            H[:50] = 2.0                                               # 10 × 5 mm à 2 mm
            H[50:60] = -1.0                                            # 10 × 1 mm en creux de 1 mm
            img = GB.encode(H, 0.0, 10.0, 0.1, GB.GalbeSpec())
            w.canvas.doc.add(img)
            w.canvas.select([img])
            v = w.measure_volume(show=False)
            self.assertAlmostEqual(v['relief'], 100.0, 6)
            self.assertAlmostEqual(v['creux'], 10.0, 6)
            w.canvas.select([])
            self.assertIsNone(w.measure_volume(show=False))            # ni relief ni parcours
        finally:
            w.modified = False
            w.close()

    def test_links(self):
        for k in ('ID_TART_ADVANCED_SWEEPING', 'ID_MAPPING_SURF', 'ID_PALETTE_MESUREVOLUME', 'ID_BarEnroule'):
            self.assertIn(k, SC.TE_ACTIONS)


if __name__ == '__main__':
    unittest.main()
