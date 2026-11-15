"""Round 232 : Maj+E exporte la sélection (ou tout) avec des modèles
d'export (format + réglages enregistrés)."""
import os
import pathlib
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication, QFileDialog, QInputDialog

from vectordrive.core import geom
from vectordrive.core.document import Shape

app = QApplication.instance() or QApplication([])


def rect(x, y, w, h):
    return Shape(path=geom.Path([geom.rect(x, y, w, h)]), tool=0)


class TestExportSelection(unittest.TestCase):
    def test_templates_and_selection(self):
        from vectordrive.io import registry
        from vectordrive.ui import export_dialog as ED
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        a, b = rect(0, 0, 10, 10), rect(50, 50, 5, 5)
        w.canvas.doc.add(a)
        w.canvas.doc.add(b)
        w.canvas.select([b])
        dlg = ED.ExportDialog(w, selection=True)
        self.assertTrue(dlg.only_sel.isChecked())
        i = dlg.format.findData('dxf')
        self.assertGreaterEqual(i, 0)
        dlg.format.setCurrentIndex(i)
        dlg.fields['dpi'].setValue(600.0)
        with mock.patch.object(QInputDialog, 'getText', return_value=('Client DXF', True)):
            dlg._save_template()
        self.assertEqual([t['nom'] for t in ED.load_templates(w.settings)], ['Client DXF'])
        self.assertEqual(ED.load_templates(w.settings)[0]['options']['dpi'], 600.0)
        dlg2 = ED.ExportDialog(w, selection=True)                    # modèle proposé et appliqué
        self.assertEqual(dlg2.list.count(), 1)
        dlg2.fields['dpi'].setValue(72.0)
        dlg2._pick(dlg2.list.item(0))
        self.assertEqual((dlg2.format.currentData(), dlg2.fields['dpi'].value()), ('dxf', 600.0))
        dlg2.list.setCurrentRow(0)
        dlg2._delete_template()
        self.assertEqual(ED.load_templates(w.settings), [])
        out = pathlib.Path(tempfile.mkdtemp()) / 'sel.dxf'
        with mock.patch.object(ED.ExportDialog, 'exec', return_value=1), \
                mock.patch.object(QFileDialog, 'getSaveFileName', return_value=(str(out), '')), \
                mock.patch.object(ED.ExportDialog, 'current', return_value={'format': 'dxf', 'options': {}}):
            self.assertEqual(ED.run(w), str(out))
        back = registry.open_document(out)
        leaves = list(back.iter_leaves())
        self.assertEqual(len(leaves), 1)                               # la sélection seule
        self.assertEqual(leaves[0].bbox(), (50, 50, 55, 55))           # à sa place
        png = out.with_suffix('.png')
        ED.export_items(w, [a, b], str(png), {'dpi': 100.0, 'plaque': False})
        self.assertGreater(png.stat().st_size, 100)
        w.canvas.select([])
        out2 = out.with_name('tout.svg')
        with mock.patch.object(ED.ExportDialog, 'exec', return_value=1), \
                mock.patch.object(QFileDialog, 'getSaveFileName', return_value=(str(out2), '')), \
                mock.patch.object(ED.ExportDialog, 'current', return_value={'format': 'svg', 'options': {}}):
            ED.run(w)                                                  # sans sélection : tout le dessin
        self.assertEqual(len(list(registry.open_document(out2).iter_leaves())), 2)
        w.modified = False
        w.close()


if __name__ == '__main__':
    unittest.main()
