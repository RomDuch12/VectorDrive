"""Round 500 : Exporter — réglages selon la nature du format, fichier écrit relu et vérifié, message avec
« Ouvrir le dossier », bouton « Dossier du dernier export »."""
import os
import pathlib
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication, QFileDialog

from vectordrive.core import geom
from vectordrive.core.document import Shape
from vectordrive.ui import export_dialog as ED

app = QApplication.instance() or QApplication([])


class TestExport(unittest.TestCase):
    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        for x in (0, 20):
            self.w.canvas.doc.add(Shape(path=geom.Path([geom.rect(x, 0, 10, 10)])))
        self.dir = pathlib.Path(tempfile.mkdtemp())

    def tearDown(self):
        self.w.modified = False
        self.w.close()

    def visible(self, dlg):
        return {k for k, w in dlg.fields.items() if dlg.right.isRowVisible(w)}

    def test_form_follows_format(self):
        dlg = ED.ExportDialog(self.w, selection=False)
        dlg.format.setCurrentIndex(dlg.format.findData('svg'))                 # DXF a son réglage (r567)
        self.assertEqual(self.visible(dlg), set())
        self.assertFalse(dlg.no_option.isHidden())
        png = next(k for k, f in dlg._formats.items() if ED.kind_of(f) == 'image')
        dlg.format.setCurrentIndex(dlg.format.findData(png))
        self.assertEqual(self.visible(dlg), {'dpi', 'transparent', 'plaque', 'marge', 'trait', 'rempli'})
        self.assertTrue(dlg.no_option.isHidden())
        dlg.format.setCurrentIndex(dlg.format.findData('vnd'))
        self.assertEqual(self.visible(dlg), {'vnd_textes_vivants'})

    def test_verify(self):
        out = self.dir / 'a.dxf'
        ED.export_items(self.w, [it for L in self.w.canvas.doc.layers for it in L.items], str(out), {})
        ok, msg = ED.verify_export(str(out), 2)
        self.assertTrue(ok, msg)
        self.assertIn('2', msg)
        self.assertFalse(ED.verify_export(str(out), 5)[0])                   # objets perdus
        self.assertFalse(ED.verify_export(str(self.dir / 'absent.dxf'))[0])
        (self.dir / 'vide.svg').write_bytes(b'')
        self.assertFalse(ED.verify_export(str(self.dir / 'vide.svg'))[0])
        (self.dir / 'faux.png').write_bytes(b'pas une image')
        self.assertFalse(ED.verify_export(str(self.dir / 'faux.png'))[0])

    def test_run_reports_and_remembers(self):
        out = self.dir / 'tout.svg'
        with mock.patch.object(ED.ExportDialog, 'exec', return_value=1), \
                mock.patch.object(QFileDialog, 'getSaveFileName', return_value=(str(out), '')), \
                mock.patch.object(ED.ExportDialog, 'current', return_value={'format': 'svg', 'options': {}}):
            self.assertEqual(ED.run(self.w), str(out))
        box = self.w._export_report
        self.assertIn('Vérifié', box.text())
        self.assertTrue(any(b.text() == 'Ouvrir le dossier' for b in box.buttons()))
        box.close()
        self.assertEqual(self.w.settings.value(ED.LAST_KEY), str(out))
        dlg = ED.ExportDialog(self.w, selection=False)
        self.assertTrue(dlg.last_btn.isEnabled())
        with mock.patch('vectordrive.ui.reveal.reveal', return_value=True) as rv:
            self.assertTrue(dlg.reveal_last())
        rv.assert_called_once_with(str(out))


if __name__ == '__main__':
    unittest.main()
