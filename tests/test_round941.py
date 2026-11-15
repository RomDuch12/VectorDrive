"""Round 941 : Exporter — la sélection seule dans une image ou un PDF est cadrée sur elle, sans la plaque ; le format,
et les réglages du dernier export sont proposés la fois suivante."""
import os
import pathlib
import re
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r941.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication, QFileDialog

app = QApplication.instance() or QApplication([])

from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Shape  # noqa: E402
from vectordrive.ui import export_dialog as ED  # noqa: E402


class Export(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from vectordrive.ui.main_window import MainWindow
        cls.w = MainWindow()

    @classmethod
    def tearDownClass(cls):
        cls.w.modified = False
        cls.w.close()

    def setUp(self):
        w = self.w
        w.new_document()
        w.settings.remove('export/dernier_choix')
        self.a = Shape(path=geom.Path([geom.rect(0, 0, 40, 20)]))
        self.b = Shape(path=geom.Path([geom.circle((70.0, 10.0), 8.0)]))
        for it in (self.a, self.b):
            w.canvas.doc.add(it)
        w.canvas.select([self.b])                               # la sélection : le cercle de 16 mm
        self.dir = pathlib.Path(tempfile.mkdtemp())

    def run_export(self, name, key, only_selection=True, **options):
        out = self.dir / name

        def fake_exec(dlg):
            dlg.format.setCurrentIndex(dlg.format.findData(key))
            dlg.only_sel.setChecked(only_selection)
            for k, v in options.items():
                dlg.fields[k].setValue(v) if hasattr(dlg.fields[k], 'setValue') else dlg.fields[k].setChecked(v)
            return 1
        with mock.patch.object(ED.ExportDialog, 'exec', fake_exec), \
                mock.patch.object(QFileDialog, 'getSaveFileName', return_value=(str(out), '')):
            self.assertEqual(ED.run(self.w), str(out))
        self.w._export_report.close()
        return out

    def image_key(self):
        return next(f.key for f in ED.formats() if ED.kind_of(f) == 'image')

    def test_the_selection_in_an_image_is_framed_on_itself(self):
        out = self.run_export('sel.png', self.image_key(), dpi=300.0)
        img = QImage(str(out))
        self.assertLess(img.width(), 400)                       # 16 mm + les marges, à 300 dpi ; avant : la plaque, 5 953 px
        self.assertLess(img.height(), 400)
        self.assertGreater(img.width(), 180)
        out = self.run_export('tout.png', self.image_key(), only_selection=False, dpi=300.0)
        self.assertGreater(QImage(str(out)).width(), 3000)      # tout le dessin : avec la plaque, comme avant

    def test_the_selection_in_a_pdf_is_framed_on_itself(self):
        out = self.run_export('sel.pdf', 'pdf')
        box = re.search(rb'/MediaBox\s*\[\s*0\s+0\s+([\d.]+)\s+([\d.]+)', out.read_bytes())
        self.assertIsNotNone(box)
        self.assertLess(float(box.group(1)), 100.0)             # 26 mm = 74 points ; avant : la plaque, 1 446 points
        self.assertLess(float(box.group(2)), 100.0)

    def test_the_last_export_is_offered_again(self):
        self.run_export('sel.png', self.image_key(), dpi=150.0, marge=7.0)
        dlg = ED.ExportDialog(self.w, selection=True)
        self.assertEqual(dlg.format.currentData(), self.image_key())      # avant : le premier format de la liste
        self.assertAlmostEqual(dlg.fields['dpi'].value(), 150.0)
        self.assertAlmostEqual(dlg.fields['marge'].value(), 7.0)
        self.assertTrue(dlg.only_sel.isChecked())
        self.assertFalse(dlg.fields['plaque'].isEnabled())      # la sélection seule : sans la plaque
        dlg.only_sel.setChecked(False)
        self.assertTrue(dlg.fields['plaque'].isEnabled())
        self.run_export('tout.svg', 'svg', only_selection=False)
        dlg = ED.ExportDialog(self.w, selection=True)
        self.assertEqual(dlg.format.currentData(), 'svg')
        self.assertTrue(dlg.only_sel.isChecked())               # une sélection : proposée, comme avant


if __name__ == '__main__':
    unittest.main()
