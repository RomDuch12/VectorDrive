"""Round 942 : Dimensions (F2) — Tab passe par les cotes puis par leurs « % » ; champs Z grisés ; référence plus
grande ; Ctrl + pavé numérique choisit le point de référence, sans gêner Ctrl+7, 8, 9 du clavier."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r942.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Shape  # noqa: E402

CTRL = Qt.KeyboardModifier.ControlModifier
PAD = Qt.KeyboardModifier.KeypadModifier


class F2(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from vectordrive.ui.main_window import MainWindow
        cls.w = MainWindow()
        cls.w.resize(1600, 950)
        cls.w.show()
        cls.w.activateWindow()
        app.processEvents()

    @classmethod
    def tearDownClass(cls):
        cls.w.modified = False
        cls.w.close()

    def setUp(self):
        w = self.w
        w.new_document()
        self.sh = Shape(path=geom.Path([geom.rect(10, 20, 40, 25)]))
        w.canvas.doc.add(self.sh)
        w.canvas.select([self.sh])
        w.dims.set_reference_key(5) if hasattr(w.dims, 'set_reference_key') else None
        w.focus_dimensions()
        app.processEvents()

    def test_tab_goes_through_the_sizes_then_the_percents(self):
        d = self.w.dims
        self.assertTrue(d.fields['w'].hasFocus())
        seen = []
        for _k in range(5):
            QTest.keyClick(QApplication.focusWidget(), Qt.Key.Key_Tab)
            app.processEvents()
            seen.append(QApplication.focusWidget())
        self.assertEqual(seen, [d.fields['h'], d.pct['w'], d.pct['h'], d.rot, d.scale])   # avant : L, % L, H, % H
        self.assertFalse(d.z_size.isEnabled() or d.z_pct.isEnabled())       # Z : grisé, le dessin est en 2D
        i = d.tab_order.index
        self.assertLess(i(d.fields['h']), i(d.z_size))
        self.assertLess(i(d.z_size), i(d.pct['w']))
        self.assertLess(i(d.pct['h']), i(d.z_pct))

    def test_ctrl_numpad_picks_the_reference(self):
        w, d = self.w, self.w.dims
        w.canvas.setFocus()
        app.processEvents()
        sens = w.A['direction'].isChecked()
        QTest.keyClick(w.canvas, Qt.Key.Key_7, CTRL | PAD)                  # Ctrl + 7 du pavé : haut gauche
        app.processEvents()
        self.assertEqual(d.anchor.point(), (0.0, 1.0))
        self.assertEqual(w.A['direction'].isChecked(), sens)                # pas l'affichage du sens (Ctrl+7 du clavier)
        self.assertAlmostEqual(d.fields['x'].value(), 10.0)
        self.assertAlmostEqual(d.fields['y'].value(), 45.0)
        QTest.keyClick(w.canvas, Qt.Key.Key_3, CTRL | PAD)                  # bas droite
        app.processEvents()
        self.assertEqual(d.anchor.point(), (1.0, 0.0))
        self.assertAlmostEqual(d.fields['x'].value(), 50.0)
        self.assertEqual(str(w.settings.value('f2/reference')), '1.0,0.0')
        QTest.keyClick(w.canvas, Qt.Key.Key_7, CTRL)                        # le 7 du clavier : toujours le sens
        app.processEvents()
        self.assertEqual(d.anchor.point(), (1.0, 0.0))
        self.assertNotEqual(w.A['direction'].isChecked(), sens)
        w.A['direction'].setChecked(sens)

    def test_the_reference_grid_is_easier_to_see(self):
        d = self.w.dims
        b = d.anchor.buttons[(0.5, 0.5)]
        self.assertGreaterEqual(b.width(), 15)                              # avant : 14 px, et pâles
        self.assertLessEqual(d.minimumSizeHint().height(), 250)             # à droite de X et Y : le panneau ne grandit pas
        self.assertIn('pavé numérique', b.toolTip())
        self.assertIn('#1971c2', b.styleSheet())                            # la case choisie : pleine, à la couleur d'accent


if __name__ == '__main__':
    unittest.main()
