"""Round 90 : mode sombre réel (au choix, appliqué tout de suite) et calques
en onglets (un calque montré seul)."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import geom
from vectordrive.core.document import Layer, Shape
from vectordrive.ui import theme


class TestTheme(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        theme.apply_light(self.app)                  # quel que soit le thème laissé par un essai précédent

    def tearDown(self):
        theme.apply_light(self.app)

    def test_modes(self):
        self.assertTrue(theme.apply_theme(self.app, 'sombre'))
        self.assertLess(self.app.palette().window().color().lightness(), 80)
        self.assertEqual(theme.canvas_colors(), theme.CANVAS_DARK)
        self.assertFalse(theme.apply_theme(self.app, 'clair'))
        self.assertGreater(self.app.palette().window().color().lightness(), 200)
        self.assertEqual(theme.canvas_colors(), theme.CANVAS_LIGHT)

    def test_ink_readable_on_dark(self):
        from PySide6.QtGui import QColor
        self.assertEqual(theme.ink('#0000ff'), '#0000ff')                  # clair : couleur d'outil telle quelle
        theme.apply_dark(self.app)
        self.assertEqual(theme.ink('#000000'), '#e6e6e6')
        self.assertGreater(QColor(theme.ink('#0000ff')).lightness(), 160)
        self.assertEqual(theme.ink('#ffff00'), '#ffff00')


class TestWindow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        d = self.w.canvas.doc
        d.layers[0].items.append(Shape(path=geom.Path([geom.rect(0, 0, 20, 10)])))
        d.layers.append(Layer(name='Fine', tool=2))
        d.layers[1].items.append(Shape(path=geom.Path([geom.circle((10, 5), 3)]), tool=2))
        self.w.layers_panel.refresh()

    def tearDown(self):
        self.w.A['layer_tabs'].setChecked(False)
        self.w.set_dark(False)
        self.w.modified = False
        self.w.close()

    def test_layer_tabs_show_one_layer(self):
        w, d = self.w, self.w.canvas.doc
        w.layer_all.setChecked(False)
        w.A['layer_tabs'].setChecked(True)
        self.assertEqual([w.layer_tabs.tabText(i) for i in range(w.layer_tabs.count())],
                         ['Plan 1', 'Fine'])                                 # round 240 : plus d'onglet « Tous »
        w.layer_tabs.setCurrentIndex(1)
        self.assertEqual(w.canvas.solo_layer, d.layers[1].id)
        self.assertIs(d.active_layer, d.layers[1])                          # nouveaux objets dans ce calque
        w.canvas.select_all()
        self.assertEqual(w.canvas.selection, d.layers[1].items)
        self.assertEqual(list(w.canvas.shown_items()), d.layers[1].items)
        edge = w.canvas.to_screen(0, 5)                                       # bord du rectangle de « Plan 1 »
        self.assertIsNone(w.canvas.pick(edge))
        w.layer_all.setChecked(True)                                         # « Voir tous »
        self.assertIs(w.canvas.pick(edge), d.layers[0].items[0])
        self.assertIsNone(w.canvas.solo_layer)
        self.assertIs(d.active_layer, d.layers[1])
        w.canvas.select_all()
        self.assertEqual(len(w.canvas.selection), 2)
        w.layer_all.setChecked(False)

    def test_solo_follows_current_layer_and_off(self):
        w, d = self.w, self.w.canvas.doc
        w.layer_all.setChecked(False)
        w.A['layer_tabs'].setChecked(True)
        w._cycle_layer_tab(1)                                                # « Fine »
        self.assertEqual(w.canvas.solo_layer, d.layers[1].id)
        d.active = d.layers[0].id
        w.layers_panel.refresh()
        self.assertEqual(w.canvas.solo_layer, d.layers[0].id)
        w.A['layer_tabs'].setChecked(False)
        self.assertIsNone(w.canvas.solo_layer)
        self.assertFalse(w.layer_bar.isVisibleTo(w))
        self.assertIn(w.settings.value('vue/onglets_calques'), (False, 'false'))

    def test_dark_mode_live(self):
        w = self.w
        w.A['theme_dark'].setChecked(True)
        self.assertEqual(w.settings.value('vue/theme'), 'sombre')
        self.assertLess(self.app.palette().window().color().lightness(), 80)
        from vectordrive.ui.icons import icon
        self.assertEqual(w.A['grid'].icon().cacheKey(), icon('grid').cacheKey())   # icônes refaites
        w.A['theme_dark'].setChecked(False)
        self.assertEqual(w.settings.value('vue/theme'), 'clair')


if __name__ == '__main__':
    unittest.main()
