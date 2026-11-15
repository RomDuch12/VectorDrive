"""Round 901 : panneau des calques, une case dans l'en-tête de la colonne des cases, qui coche ou décoche tous les
calques ; partielle si certains seulement sont affichés ; le calque actif reste affiché."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r901.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])


class Header(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from vectordrive.ui.main_window import MainWindow
        cls.w = MainWindow()
        cls.w.resize(1400, 900)
        cls.w.show()

    @classmethod
    def tearDownClass(cls):
        cls.w.modified = False
        cls.w.close()

    def setUp(self):
        from vectordrive.core.document import Layer
        self.w.modified = False
        self.w.new_document()
        doc = self.w.canvas.doc
        doc.layers += [Layer(name='B', tool=1), Layer(name='C', tool=2)]
        self.p = self.w.layers_panel
        self.p.refresh()
        self.h = self.p.tree.header()

    def visible(self):
        return [L.visible for L in self.w.canvas.doc.layers]

    def test_the_header_has_the_box(self):
        from vectordrive.ui.layers import CheckHeader
        self.assertIsInstance(self.h, CheckHeader)
        self.assertEqual(self.h.state, Qt.CheckState.Checked)
        self.assertIn('tous les calques', self.h.toolTip())
        self.assertFalse(self.h.grab().isNull())                         # dessin de la case

    def test_unchecks_then_checks_all_layers(self):
        doc = self.w.canvas.doc
        self.p.toggle_all()
        self.assertEqual(self.visible(), [L is doc.active_layer for L in doc.layers])   # l'actif reste affiché
        self.assertEqual(self.h.state, Qt.CheckState.PartiallyChecked)
        self.p.toggle_all()
        self.assertEqual(self.visible(), [True, True, True])
        self.assertEqual(self.h.state, Qt.CheckState.Checked)

    def test_a_row_unchecked_makes_it_partial(self):
        it = self.p.tree.topLevelItem(2)
        it.setCheckState(self.p.COL_VIS, Qt.CheckState.Unchecked)
        self.assertEqual(self.visible(), [True, True, False])
        self.assertEqual(self.h.state, Qt.CheckState.PartiallyChecked)
        self.p.toggle_all()                                                # partielle : tout affiché
        self.assertEqual(self.visible(), [True, True, True])

    def test_a_click_on_the_box(self):
        x = self.h.sectionViewportPosition(self.p.COL_VIS) + self.h.sectionSize(self.p.COL_VIS) // 2
        pos = self.h.viewport().rect().center()
        pos.setX(x)
        QTest.mouseClick(self.h.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, pos)
        self.assertEqual(sum(self.visible()), 1)
        x = self.h.sectionViewportPosition(self.p.COL_NAME) + 10
        pos.setX(x)
        QTest.mouseClick(self.h.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, pos)
        self.assertEqual(sum(self.visible()), 1)                         # un clic ailleurs dans l'en-tête : rien

    def test_the_list_of_layers_follows(self):
        self.w.set_all_layers_visible(False)
        self.assertEqual(self.h.state, Qt.CheckState.PartiallyChecked)
        self.p.invert_visibility()
        self.assertEqual(sum(self.visible()), 2)
        self.assertEqual(self.h.state, Qt.CheckState.PartiallyChecked)
        self.w.set_all_layers_visible(True)
        self.assertEqual(self.h.state, Qt.CheckState.Checked)


if __name__ == '__main__':
    unittest.main()
