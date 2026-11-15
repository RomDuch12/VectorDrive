"""Round 410 : chaque onglet de dessin garde sa vue, sans influence des autres."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import geom
from vectordrive.core.document import Layer, Shape

app = QApplication.instance() or QApplication([])


class TestTabViews(unittest.TestCase):
    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.w.resize(1000, 700)
        c = self.w.canvas
        c.doc.add(Shape(path=geom.Path([geom.rect(0, 0, 100, 50)])))
        self.w.new_document()
        c.doc.add(Shape(path=geom.Path([geom.rect(0, 0, 10, 5)])))
        self.assertEqual(len(self.w.docs), 2)

    def tearDown(self):
        for t in self.w.docs:
            t.modified = False
        self.w.modified = False
        self.w.close()

    def test_zoom_and_history(self):
        w, c = self.w, self.w.canvas
        w.switch_tab(0)
        c.remember_view()
        c.scale, c.ox, c.oy = 7.0, 11.0, 22.0
        w.switch_tab(1)
        self.assertFalse(c.previous_view())                     # rien de l'onglet 0
        c.remember_view()
        c.scale, c.ox, c.oy = 2.0, 3.0, 4.0
        w.switch_tab(0)
        self.assertEqual((c.scale, c.ox, c.oy), (7.0, 11.0, 22.0))
        self.assertTrue(c.previous_view())                      # son propre zoom précédent
        self.assertNotEqual((c.scale, c.ox, c.oy), (2.0, 3.0, 4.0))
        w.switch_tab(1)
        self.assertEqual((c.scale, c.ox, c.oy), (2.0, 3.0, 4.0))

    def test_display_flags(self):
        w, c = self.w, self.w.canvas
        w.switch_tab(1)
        w.A['grid'].trigger()
        w.A['direction'].trigger()
        self.assertTrue(c.show_grid and c.show_direction)
        w.switch_tab(0)
        self.assertFalse(c.show_grid or c.show_direction)
        self.assertFalse(w.A['grid'].isChecked())
        w.switch_tab(1)
        self.assertTrue(c.show_grid and c.show_direction)
        self.assertTrue(w.A['grid'].isChecked())

    def test_solo_layer(self):
        w, c = self.w, self.w.canvas
        w.switch_tab(1)
        L = Layer(name='B2')
        c.doc.layers.append(L)
        c.set_solo(L.id)
        w.switch_tab(0)
        self.assertIsNone(c.solo_layer)
        w.switch_tab(1)
        self.assertEqual(c.solo_layer, L.id)

    def test_state_without_3d(self):
        st = self.w._view_state()
        self.assertEqual(st['mode'], '2d')
        self.assertIn('flags', st)


if __name__ == '__main__':
    unittest.main()
