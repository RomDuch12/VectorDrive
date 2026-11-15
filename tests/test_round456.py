"""Round 456 : « Outil conseillé » — le plus gros outil adapté à la stratégie qui atteint tous les
détails, parmi les outils du document et Mes outils (de la machine)."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication, QMessageBox

from vectordrive.cam import model, toolfit
from vectordrive.core import geom
from vectordrive.core.document import Document, Shape

app = QApplication.instance() or QApplication([])


def doc():
    d = Document()
    d.add(Shape(path=geom.Path([geom.rect(0, 0, 30, 20)]), tool=0))
    d.add(Shape(path=geom.Path([geom.rect(40, 0, 1.2, 20)]), tool=0))          # fente de 1,2 mm
    return d


def tools():
    out = []
    for n, (name, kind, d) in enumerate((('F3', 'fraise', 3.0), ('F1', 'fraise', 1.0), ('F0.5', 'fraise', 0.5),
                                         ('Foret 1', 'foret', 1.0)), 1):
        out.append(model.CamTool(name=name, kind=kind, diameter=d, number=n))
    return out


class TestAdvise(unittest.TestCase):
    def test_core(self):
        op = model.Operation(kind='poche', sources=[0], depth=1.0)
        t, fit_d = toolfit.advise(doc(), op, tools())
        self.assertEqual(t.name, 'F1')                                           # F3 trop gros, le foret écarté
        self.assertAlmostEqual(fit_d, 1.2, delta=0.1)
        none, _d = toolfit.advise(doc(), op, [tools()[0]])
        self.assertIsNone(none)

    def test_form(self):
        from vectordrive.ui.cam_panel import FieldsDialog
        ts = tools()
        doc_tool = ts[0]
        lib = {t.id: t for t in ts[1:]}
        op = model.Operation(kind='poche', sources=[0], depth=1.0, tool_id=doc_tool.id)
        dlg = FieldsDialog(None, 'Op', op, doc(), [doc_tool], library=list(lib.values()))
        try:
            with mock.patch.object(QMessageBox, 'information') as box:
                t = dlg.advise_tool()
                box.assert_called_once()
            self.assertEqual(t.name, 'F1')
            self.assertEqual(dlg.widgets['tool_id'].currentData(), 'lib:' + t.id)   # choisi dans la liste
        finally:
            dlg.reject()


if __name__ == '__main__':
    unittest.main()
