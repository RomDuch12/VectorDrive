"""Round 325 : combiner des reliefs (TypeEdit : coller un objet TypeArt dans
le courant, selon le mode de combinaison) ; bouton Souris au ruban."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import numpy as np
from PySide6.QtWidgets import QApplication

from vectordrive.core import galbe as GB, relief_ops as R
from vectordrive.ui import shortcuts as SC

app = QApplication.instance() or QApplication([])


def at(img, x, y):
    H, x0, y1, res = GB.decode(img)
    return float(H[int((y1 - y) / res), int((x - x0) / res)])


def reliefs():
    a = GB.encode(np.full((100, 100), 1.0), 0.0, 10.0, 0.1, GB.GalbeSpec())        # 10 × 10 à 1 mm
    h = np.zeros((50, 50))
    h[10:40, 10:40] = 2.0
    b = GB.encode(h, 8.0, 5.0, 0.1, GB.GalbeSpec())                                  # 5 × 5 posé de 8 à 13 en x
    return a, b


class TestMerge(unittest.TestCase):
    def test_modes(self):
        a, b = reliefs()
        m = R.merge_reliefs([a, b], 'ajouter')
        self.assertAlmostEqual(at(m, 9.5, 2.5), 3.0, 6)            # 1 + 2
        self.assertAlmostEqual(at(m, 2, 2), 1.0, 6)
        self.assertAlmostEqual(at(m, 11.5, 2.5), 2.0, 6)            # hors du premier : agrandi
        self.assertAlmostEqual(at(m, 8.5, 0.5), 1.0, 6)             # bord nul du second : pas touché
        m = R.merge_reliefs([a, b], 'maximum')
        self.assertAlmostEqual(at(m, 9.5, 2.5), 2.0, 6)
        self.assertIsNone(R.merge_reliefs([a], 'ajouter'))

    def test_command(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            a, b = reliefs()
            w.canvas.doc.add(a)
            w.canvas.doc.add(b)
            w.canvas.select([a, b])
            img = w.relief_merge()
            self.assertIsNotNone(img)
            self.assertEqual(w.canvas.doc.layers[0].items, [img])
            w.undo()
            self.assertEqual(len(w.canvas.doc.layers[0].items), 2)
            self.assertEqual(SC.TE_ACTIONS['ID_OPEN_COMBI'], 'relief_merge')
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
