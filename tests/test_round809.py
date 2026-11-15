"""Round 809 : filtre du panneau des calques."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from vectordrive.core.document import Layer
from vectordrive.ui.layers import _plain

app = QApplication.instance() or QApplication([])


class Plain(unittest.TestCase):
    def test_case_and_accents(self):
        self.assertEqual(_plain('Plan GRAVÉ'), _plain('plan grave'))
        self.assertEqual(_plain('Œuvre'), 'œuvre')


class Panel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from vectordrive.ui.main_window import MainWindow
        cls.win = MainWindow()
        cls.panel = cls.win.layers_panel

    @classmethod
    def tearDownClass(cls):
        cls.win.modified = False
        cls.win.close()
        cls.win.deleteLater()

    def setUp(self):
        doc = self.win.canvas.doc
        doc.layers[:] = [Layer(name=n, tool=0) for n in ('Fond', 'Plan gravé', 'Découpe', 'Plan vide', 'Texte')]
        doc.active = doc.layers[0].id
        self.panel.find.clear()
        self.panel.refresh()
        self.addCleanup(self.panel.find.clear)

    def shown(self):
        tree = self.panel.tree
        return [tree.topLevelItem(i).text(1) for i in range(tree.topLevelItemCount())
                if not tree.topLevelItem(i).isHidden()]

    def test_all_shown_without_text(self):
        self.assertEqual(self.shown(), ['Fond', 'Plan gravé', 'Découpe', 'Plan vide', 'Texte'])

    def test_filter(self):
        self.panel.find.setText('plan')
        self.assertEqual(self.shown(), ['Plan gravé', 'Plan vide'])

    def test_no_accents_needed(self):
        self.panel.find.setText('DECOUPE')
        self.assertEqual(self.shown(), ['Découpe'])

    def test_blank_text_filters_nothing(self):
        self.panel.find.setText('   ')
        self.assertEqual(len(self.shown()), 5)

    def test_tool_name_counts(self):
        tool = self.panel.tree.topLevelItem(0).text(2)
        self.panel.find.setText(tool)
        self.assertEqual(len(self.shown()), 5)

    def test_nothing_found(self):
        self.panel.find.setText('zzz')
        self.assertEqual(self.shown(), [])

    def test_filter_survives_a_refresh(self):
        self.panel.find.setText('plan')
        self.panel.refresh()
        self.assertEqual(self.shown(), ['Plan gravé', 'Plan vide'])

    def test_clear_shows_all(self):
        self.panel.find.setText('plan')
        self.panel.find.clear()
        self.assertEqual(len(self.shown()), 5)

    def test_document_untouched(self):
        doc = self.win.canvas.doc
        self.panel.find.setText('plan')
        self.assertEqual(len(doc.layers), 5)
        self.assertTrue(all(L.visible for L in doc.layers))

    def test_return_activates_the_first(self):
        doc = self.win.canvas.doc
        self.panel.find.setText('vide')
        self.panel.find.returnPressed.emit()
        self.assertEqual(doc.active_layer.name, 'Plan vide')

    def test_return_with_nothing_found(self):
        doc = self.win.canvas.doc
        before = doc.active
        self.panel.find.setText('zzz')
        self.panel.activate_first()
        self.assertEqual(doc.active, before)

    def test_hidden_active_layer_stays_active(self):
        doc = self.win.canvas.doc
        before = doc.active
        self.panel.find.setText('plan')
        self.panel.refresh()
        self.assertEqual(doc.active, before)

    def test_visibility_check_on_a_filtered_row(self):
        doc = self.win.canvas.doc
        self.panel.find.setText('vide')
        tree = self.panel.tree
        row = next(tree.topLevelItem(i) for i in range(tree.topLevelItemCount()) if not tree.topLevelItem(i).isHidden())
        row.setCheckState(0, Qt.CheckState.Unchecked)
        self.assertFalse(next(L for L in doc.layers if L.name == 'Plan vide').visible)
        self.assertTrue(next(L for L in doc.layers if L.name == 'Fond').visible)


if __name__ == '__main__':
    unittest.main()
