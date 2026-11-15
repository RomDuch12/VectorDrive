"""Round 983 : « Exporter » la sélection écrit son fichier même quand la boîte de fichier fait tourner la boucle
d'événements (la vraie boîte de Windows) ; une fenêtre de dialogue finie reste lisible tant que le code qui a appelé
son exec() tourne, puis elle est libérée."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r983.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

import shiboken6  # noqa: E402
from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QCheckBox, QDialog, QFileDialog, QMessageBox  # noqa: E402

app = QApplication.instance() or QApplication([])


class FinishedDialogs(unittest.TestCase):

    def use(self, fit):
        """Comme une commande : une fenêtre (exec), puis une autre boîte qui fait tourner la boucle d'événements,
        puis la lecture d'un champ de la première."""
        d = QDialog()
        box = QCheckBox(d)
        box.setChecked(True)
        fit.no_hscroll(d)
        QTimer.singleShot(0, d.accept)
        d.exec()
        QTest.qWait(120)                                                     # la boîte de fichier de Windows
        try:
            read = box.isChecked()
        except RuntimeError as ex:                                           # avant : fenêtre déjà détruite
            read = str(ex)
        return read, d

    def test_a_finished_dialog_is_readable_while_its_caller_runs(self):
        from vectordrive.ui import fit
        read, d = self.use(fit)
        self.assertIs(read, True)                                            # avant : « Internal C++ object … already deleted »
        QTest.qWait(getattr(fit, 'RETRY_MS', 300) + 200)
        self.assertFalse(shiboken6.isValid(d))                               # puis libérée, le code appelant fini
        shown = QDialog()                                                    # seulement montrée (sans exec) : libérée
        fit.no_hscroll(shown)                                                # dès sa fermeture, comme avant
        shown.show()
        shown.reject()
        QTest.qWait(60)
        self.assertFalse(shiboken6.isValid(shown))


class ExportWithARealFileBox(unittest.TestCase):

    def setUp(self):
        from vectordrive.core import geom
        from vectordrive.core.document import Shape
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.a = Shape(path=geom.Path([geom.rect(10, 10, 40, 20)]))
        self.w.canvas.doc.add(self.a)
        self.w.canvas.doc.add(Shape(path=geom.Path([geom.circle((80.0, 20.0), 8.0)])))
        self.w.canvas.select([self.a])
        self.tmp = tempfile.TemporaryDirectory()
        self.saved = QFileDialog.getSaveFileName

    def tearDown(self):
        QFileDialog.getSaveFileName = self.saved
        for d in app.topLevelWidgets():
            if isinstance(d, QMessageBox):
                d.close()
        self.w.modified = False
        for t in getattr(self.w, 'docs', []):
            t.modified = False
        self.w.close()
        self.tmp.cleanup()

    def export(self, key, name):
        from vectordrive.ui import export_dialog as ED
        target = pathlib.Path(self.tmp.name) / name

        def box(*_a, **_k):
            QTest.qWait(120)                                                 # la vraie boîte : la boucle d'événements tourne
            return str(target), ''
        QFileDialog.getSaveFileName = staticmethod(box)

        def accept():
            for d in app.topLevelWidgets():
                if isinstance(d, ED.ExportDialog) and d.isVisible():
                    d.format.setCurrentIndex(d.format.findData(key))
                    self.assertTrue(d.only_sel.isChecked())
                    d.accept()
                    return
            QTimer.singleShot(50, accept)
        QTimer.singleShot(100, accept)
        try:
            got = ED.run(self.w)
        except RuntimeError as ex:                                           # avant : la fenêtre d'export déjà détruite
            got = f'erreur : {ex}'
        return target, got

    def test_selection_is_written_after_a_file_box_that_spins_the_event_loop(self):
        for key, name in (('dxf', 'selection.dxf'), ('pdf', 'selection.pdf'), ('image', 'selection.png')):
            target, got = self.export(key, name)
            self.assertEqual(got, str(target), key)                          # avant : erreur muette, aucun fichier
            self.assertGreater(target.stat().st_size, 100, key)
        from vectordrive.io import registry
        back = registry.open_document(str(pathlib.Path(self.tmp.name) / 'selection.dxf'))
        self.assertEqual(len(list(back.iter_leaves())), 1)                   # la sélection seule : le rectangle


if __name__ == '__main__':
    unittest.main()
