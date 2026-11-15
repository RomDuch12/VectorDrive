"""Round 240 : calques en onglets — l'onglet regardé est le calque actif et
le seul visible ; « Voir tous » ; liste des calques à cocher, case tout
cocher / décocher."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])


class TestLayerTabs(unittest.TestCase):
    def setUp(self):
        from vectordrive.core import geom
        from vectordrive.core.document import Layer, Shape
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        d = self.d = self.w.canvas.doc
        d.layers[0].items.append(Shape(path=geom.Path([geom.rect(0, 0, 20, 10)])))
        for name in ('B', 'C'):
            L = Layer(name=name, tool=2)
            L.items.append(Shape(path=geom.Path([geom.circle((10, 5), 3)]), tool=2))
            d.layers.append(L)
        self.w.layers_panel.refresh()
        self.w.layer_all.setChecked(False)
        self.w.A['layer_tabs'].setChecked(True)

    def tearDown(self):
        self.w.A['layer_tabs'].setChecked(False)
        self.w.layer_all.setChecked(False)
        self.w.modified = False
        self.w.close()

    def test_tab_is_active_and_alone(self):
        w, d = self.w, self.d
        self.assertEqual(w.layer_tabs.count(), 3)
        self.assertEqual(w.layer_tabs.tabData(w.layer_tabs.currentIndex()), d.active_layer.id)
        w.layer_tabs.setCurrentIndex(2)
        self.assertEqual(d.active, d.layers[2].id)
        self.assertEqual(list(w.canvas.shown_items()), d.layers[2].items)
        # le calque actif changé ailleurs (panneau) : l'onglet suit
        d.active = d.layers[1].id
        w.layers_panel.refresh()
        self.assertEqual(w.layer_tabs.currentIndex(), 1)
        self.assertEqual(w.canvas.solo_layer, d.layers[1].id)

    def test_show_all_and_list(self):
        w, d = self.w, self.d
        w.layer_all.setChecked(True)
        self.assertIsNone(w.canvas.solo_layer)
        self.assertEqual(len(list(w.canvas.shown_items())), 3)
        w._fill_layer_list()
        lst = w.layer_list
        self.assertEqual([lst.item(i).text() for i in range(lst.count())], ['Plan 1', 'B', 'C'])
        lst.item(2).setCheckState(Qt.CheckState.Unchecked)                  # C masqué
        QApplication.processEvents()
        self.assertFalse(d.layers[2].visible)
        self.assertEqual(len(list(w.canvas.shown_items())), 2)
        self.assertEqual(w.layer_check_all.checkState(), Qt.CheckState.PartiallyChecked)
        w._layer_list_all()                                                 # tout cocher
        self.assertTrue(all(L.visible for L in d.layers))
        self.assertEqual(w.layer_check_all.checkState(), Qt.CheckState.Checked)
        w._layer_list_all()                                                 # tout décocher : l'actif reste
        self.assertEqual([L.visible for L in d.layers], [True, False, False])
        w._fill_layer_list()
        w._layer_list_clicked(lst.item(1))                                  # clic sur un nom : actif
        self.assertEqual(d.active, d.layers[1].id)
        self.assertTrue(d.layers[1].visible)
        self.assertIn(w.settings.value('vue/calques_tous'), (True, 'true'))


if __name__ == '__main__':
    unittest.main()
