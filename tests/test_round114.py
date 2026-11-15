"""Round 114 : mise en forme des textes (barre « Rapido » de TypeEdit) —
onglet contextuel, police, hauteur, largeur, espacements, alignement."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import geom
from vectordrive.core.document import Group, Shape, Text


class TestTextFormat(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        QApplication.instance() or QApplication([])
        from vectordrive.ui.main_window import MainWindow
        cls.w = MainWindow()

    @classmethod
    def tearDownClass(cls):
        cls.w.modified = False
        cls.w.close()

    def setUp(self):
        self.w.modified = False
        self.w.new_document()
        self.w._undo.clear()

    def tab_visible(self):
        r = self.w.ribbon
        i = next(i for i in range(r.count()) if r.tabText(i) == self.w.text_tab_title)
        return r.isTabVisible(i)

    def test_context_tab(self):
        w = self.w
        t = Text(text='ABC', font='Arial', size=5)
        s = Shape(path=geom.Path([geom.rect(0, 0, 5, 5)]))
        w.canvas.doc.layers[0].items += [t, s]
        self.assertFalse(self.tab_visible())
        w.canvas.select([s])
        w._on_selection()
        self.assertFalse(self.tab_visible())
        w.canvas.select([t])
        w._on_selection()
        self.assertTrue(self.tab_visible())
        self.assertAlmostEqual(w.textbar.size.value(), 5)
        w.canvas.select([])
        w._on_selection()
        self.assertFalse(self.tab_visible())

    def test_apply_fields(self):
        w = self.w
        a = Text(text='ABC', font='Arial', size=5)
        b = Text(text='XYZ', font='Arial', size=5, extra={'fit': {'width': 30, 'mode': 'spacing'}})
        g = Group(children=[b])
        w.canvas.doc.layers[0].items += [a, g]
        w.canvas.select([a, g])
        w._on_selection()
        w0 = a.bbox()[2] - a.bbox()[0]
        w.textbar.size.setValue(10)
        self.assertEqual((a.size, b.size), (10, 10))
        self.assertAlmostEqual((a.bbox()[3] - a.bbox()[1]) / 2, (a.bbox()[3] - a.bbox()[1]) / 2)
        self.assertGreater(a.bbox()[2] - a.bbox()[0], w0 * 1.5)
        w.textbar.width.setValue(50)
        self.assertAlmostEqual(a.width_ratio, 0.5)
        self.assertNotIn('fit', b.extra)                               # la largeur imposée cède
        w.textbar.spacing.setValue(1.0)
        self.assertEqual(a.spacing, 1.0)
        self.assertEqual(w.set_text_align('center'), 2)
        self.assertEqual(a.align, 'center')
        self.assertEqual(w.undo_labels()[0], 'Mise en forme du texte')
        self.assertEqual(len(w._undo), 4)
        w.undo()
        self.assertEqual(w.canvas.doc.layers[0].items[0].align, 'left')

    def test_font_change(self):
        w = self.w
        t = Text(text='Abc', font='Arial', size=5)
        w.canvas.doc.layers[0].items.append(t)
        w.canvas.select([t])
        w._on_selection()
        self.assertEqual(w.textbar.apply('font', 'Times New Roman'), 1)
        self.assertEqual(t.font, 'Times New Roman')
        self.assertEqual(w.textbar.apply('font', 'Times New Roman'), 0)  # rien à changer : pas de pas d'annulation


if __name__ == '__main__':
    unittest.main()
