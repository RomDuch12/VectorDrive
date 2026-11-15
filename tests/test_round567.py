"""Round 567 : export DXF — « un calque par outil » (Outil 1, Outil 2…, de la couleur de l'outil) dans le
formulaire propre au DXF ; sinon les calques du dessin."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import ezdxf
from PySide6.QtWidgets import QApplication

from vectordrive.core import geom
from vectordrive.core.document import Shape, Tool

app = QApplication.instance() or QApplication([])


class TestDxfLayers(unittest.TestCase):
    def test_per_tool(self):
        from vectordrive.ui import export_dialog as ED
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            w.canvas.doc.tools = [Tool(0, '#000000'), Tool(2, '#ff0000')]
            items = [Shape(path=geom.Path([geom.rect(0, 0, 5, 5)]), tool=0),
                     Shape(path=geom.Path([geom.rect(9, 0, 5, 5)]), tool=2)]
            for it in items:
                w.canvas.doc.add(it)
            d = pathlib.Path(tempfile.mkdtemp())
            ED.export_items(w, items, str(d / 'a.dxf'), {'dxf_calques_outils': True})
            ED.export_items(w, items, str(d / 'b.dxf'), {})
            la = {e.dxf.layer for e in ezdxf.readfile(d / 'a.dxf').modelspace()}
            lb = {e.dxf.layer for e in ezdxf.readfile(d / 'b.dxf').modelspace()}
            self.assertEqual(la, {'Outil 1', 'Outil 3'})
            self.assertEqual(lb, {w.canvas.doc.layers[0].name})
            self.assertEqual(ezdxf.readfile(d / 'a.dxf').layers.get('Outil 3').dxf.color, 1)   # rouge
            dlg = ED.ExportDialog(w, selection=False)
            dxf = next(k for k, f in dlg._formats.items() if ED.kind_of(f) == 'dxf')
            dlg.format.setCurrentIndex(dlg.format.findData(dxf))
            self.assertTrue(dlg.right.isRowVisible(dlg.fields['dxf_calques_outils']))
            self.assertFalse(dlg.right.isRowVisible(dlg.fields['dpi']))
            dlg.reject()
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
