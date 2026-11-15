"""Round 91, revu au round 100 : Ctrl+flèche demande le pas de
déplacement (proposé : la taille de la sélection plus l'écart) ; la valeur
saisie devient le pas des flèches (copier, coller, Ctrl+flèche, Entrée,
flèche : clone accolé). Round 257 : la valeur validée déplace aussitôt la
sélection dans le sens de la flèche."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from vectordrive.core import geom
from vectordrive.core.document import Shape

CTRL, SHIFT = Qt.KeyboardModifier.ControlModifier, Qt.KeyboardModifier.ShiftModifier


class TestArrowStep(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.c = self.w.canvas
        self.c.nudge_mm, self.c.step_gap_mm = 1.0, 0.0
        self.rect = Shape(path=geom.Path([geom.rect(0, 0, 20, 8)]))
        self.c.doc.add(self.rect)
        self.c.select([self.rect])

    def tearDown(self):
        self.w.modified = False
        self.w.close()

    def x0(self):
        return self.c.selection_bbox()[0]

    def key(self, k, mods=Qt.KeyboardModifier.NoModifier):
        QTest.keyClick(self.c, k, mods)

    def answer(self, value=None, ok=True):
        """Ctrl+flèche répondu d'avance : `value` (None = la valeur proposée)."""
        from PySide6.QtWidgets import QInputDialog
        asked = []

        def fake(parent, title, label, start, lo, hi, dec):
            asked.append(start)
            return (start if value is None else value), ok
        old = QInputDialog.getDouble
        QInputDialog.getDouble = staticmethod(fake)
        self.addCleanup(lambda: setattr(QInputDialog, 'getDouble', old))
        return asked

    def test_ctrl_arrow_asks_step(self):
        steps = []
        self.c.arrowStepChanged.connect(steps.append)
        asked = self.answer(25.0)
        self.key(Qt.Key.Key_Right, CTRL)
        self.assertEqual(asked, [20.0])                             # proposé : largeur + écart
        self.assertAlmostEqual(self.x0(), 25)                       # validé : déplacé aussitôt (257)
        self.key(Qt.Key.Key_Right)
        self.assertAlmostEqual(self.x0(), 50)                       # les flèches suivent la valeur saisie
        self.key(Qt.Key.Key_Left, SHIFT)
        self.assertAlmostEqual(self.x0(), 40)                       # Maj+flèche : 10 × le pas des options
        self.c.select([])
        self.c.select(list(self.c.doc.layers[0].items))
        self.key(Qt.Key.Key_Left)
        self.assertAlmostEqual(self.x0(), 15)                       # le pas saisi reste
        asked = self.answer(0.0)
        self.key(Qt.Key.Key_Up, CTRL)
        self.assertEqual(asked, [25.0])                             # proposé : le pas en cours
        self.assertAlmostEqual(self.x0(), 15)                       # 0 : rien ne bouge
        self.key(Qt.Key.Key_Right)
        self.assertAlmostEqual(self.x0(), 16)                       # 0 : retour au pas des options
        self.assertEqual(steps, [25.0, 0.0])

    def test_gap_option_and_cancel(self):
        self.c.step_gap_mm = 2.5
        asked = self.answer(ok=False)
        self.key(Qt.Key.Key_Right, CTRL)
        self.assertEqual(asked, [22.5])
        self.assertIsNone(self.c.arrow_step)                        # annulé : rien ne change
        self.assertAlmostEqual(self.x0(), 0)
        self.key(Qt.Key.Key_Right)
        self.assertAlmostEqual(self.x0(), 1)

    def test_copy_paste_clone_side_by_side(self):
        self.answer()
        self.w.copy()
        self.w.paste()
        self.assertIsNot(self.c.selection[0], self.rect)
        self.key(Qt.Key.Key_Right, CTRL)
        self.assertAlmostEqual(self.x0(), 20)                       # clone accolé dès Ctrl+flèche validé
        self.assertAlmostEqual(self.rect.bbox()[0], 0)              # l'original reste
        self.w.paste()
        self.key(Qt.Key.Key_Right)
        self.key(Qt.Key.Key_Right)
        xs = sorted(round(it.bbox()[0], 6) for L in self.c.doc.layers for it in L.items)
        self.assertEqual(xs, [0, 20, 40])

if __name__ == '__main__':
    unittest.main()
