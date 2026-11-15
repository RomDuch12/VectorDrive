"""Round 478 : catalogues d'opérations machine (plugins), fichier pris comme bloc, paramètres nommés."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.cam import catalog as C, instructions as INS

app = QApplication.instance() or QApplication([])


def provider():
    return [C.Entry(name='Poche rectangle', path='Cycles/Poches', text='RectangleCavity widthX={p1} widthY={p2}',
                    names=['Largeur X', 'Largeur Y'], values=[20, 10], note='Manuel 5.2.3.1'),
            {'name': 'Message', 'path': 'Dialogues', 'instruction': 'message', 'params': {'message': 'Bonjour'}}]


def broken():
    raise RuntimeError('catalogue abîmé')


class TestCatalog(unittest.TestCase):
    def setUp(self):
        from vectordrive.plugins import REGISTRY
        self.reg = REGISTRY
        REGISTRY.instruction_catalogs[:] = [('Essai 478', provider), ('Abîmé', broken)]

    def tearDown(self):
        self.reg.instruction_catalogs.clear()

    def test_catalogs_and_operation(self):
        cats = C.catalogs()
        self.assertEqual([c[0] for c in cats], ['Essai 478', 'Abîmé'])
        self.assertIn('catalogue abîmé', cats[1][2])
        e = cats[0][1][0]
        op = C.operation_of(e)
        self.assertEqual((op.kind, op.instruction, op.name), ('instruction', 'bloc', 'Poche rectangle'))
        self.assertEqual(INS.bloc_lines(op.params), ['RectangleCavity widthX=20 widthY=10'])
        self.assertEqual(INS.bloc_names(op.params)[:3], ['Largeur X', 'Largeur Y', ''])
        op2 = C.operation_of(cats[0][1][1])
        self.assertEqual((op2.instruction, op2.params), ('message', {'message': 'Bonjour'}))

    def test_file_entry(self):
        f = pathlib.Path(tempfile.mkdtemp()) / 'extrait.simpl'
        f.write_bytes('Rapid Z=5\r\nLine X=10 # é\r\n'.encode('cp1252'))
        e = C.file_entry(f)
        self.assertEqual(e.lines(), 'Rapid Z=5\nLine X=10 # é\n')
        self.assertEqual(C.operation_of(e).name, 'extrait')

    def test_dialog_and_panel(self):
        from vectordrive.ui.instruction_catalog import CatalogDialog
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            dlg = CatalogDialog(w.cam_panel)
            self.assertEqual(len(dlg.entries()), 2)
            self.assertEqual(dlg._filter('rectangle'), 1)
            it = next(it for it, e in dlg.entries() if not it.isHidden())
            dlg.tree.setCurrentItem(it)
            self.assertIn('RectangleCavity', dlg.preview.toPlainText())
            self.assertIn('Largeur X', dlg.note.text())
            dlg.accept()
            self.assertEqual([e.name for e in dlg.chosen], ['Poche rectangle'])
            ops = w.cam_panel.add_from_catalog(dlg.chosen)
            s = w.cam_panel.setup()
            self.assertEqual(s.operations[-1].name, 'Poche rectangle')
            self.assertEqual(len(ops), 1)
            w.cam_panel.refresh()
            w.cam_panel.ops.selectRow(len(s.operations) - 1)
            fd = w.cam_panel.edit_op(exec_dialog=False)
            labels = [fd.widgets['params'].layout().itemAt(r, fd.widgets['params'].layout().ItemRole.LabelRole)
                      for r in range(fd.widgets['params'].layout().rowCount())]
            texts = [lab.widget().text() for lab in labels if lab is not None and lab.widget() is not None]
            self.assertIn('Largeur X {p1}', texts)
            fd.reject()
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
