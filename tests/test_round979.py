"""Round 979 : plus d'échec silencieux — journal des erreurs inattendues (fichier `erreurs.txt`, barre d'état) ;
« Exporter » dit quand aucun fichier n'a été écrit et garde au journal le détail d'un export en erreur."""
import os
import pathlib
import sys
import tempfile
import threading
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r979.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox  # noqa: E402

app = QApplication.instance() or QApplication([])

from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Shape  # noqa: E402
from vectordrive.ui import export_dialog as ED  # noqa: E402


class Silent(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.hook, cls.thread_hook = sys.excepthook, threading.excepthook
        from vectordrive.ui.main_window import MainWindow
        cls.w = MainWindow()
        cls.a = Shape(path=geom.Path([geom.rect(10, 10, 40, 20)]))
        cls.w.canvas.doc.add(cls.a)

    @classmethod
    def tearDownClass(cls):
        cls.w.modified = False
        cls.w.close()
        sys.excepthook, threading.excepthook = cls.hook, cls.thread_hook

    def export(self, target):
        """Ctrl+E sur la sélection, la boîte de fichier remplacée par `target`, la fenêtre validée en DXF."""
        w = self.w
        w.canvas.select([self.a])

        def accept():
            for d in app.topLevelWidgets():
                if isinstance(d, ED.ExportDialog) and d.isVisible():
                    d.format.setCurrentIndex(d.format.findData('dxf'))
                    d.accept()
                    return
            QTimer.singleShot(50, accept)
        QTimer.singleShot(50, accept)
        with mock.patch.object(QFileDialog, 'getSaveFileName', return_value=(str(target), '')), \
                mock.patch.object(QMessageBox, 'warning') as warning, \
                mock.patch.object(QMessageBox, 'critical') as critical:
            got = ED.run(w)
        for d in app.topLevelWidgets():
            if isinstance(d, QMessageBox):
                d.close()
        return got, warning, critical

    def test_an_export_that_writes_nothing_says_so(self):
        target = pathlib.Path(tempfile.mkdtemp()) / 'rien.dxf'
        with mock.patch.object(ED, 'export_items', lambda *a, **k: None):       # une écriture qui ne laisse rien
            got, warning, critical = self.export(target)
        self.assertIsNone(got)
        self.assertFalse(target.exists())
        self.assertEqual(warning.call_count, 1)                                 # avant : aucun message
        self.assertIn(str(target), warning.call_args[0][2])
        good = target.with_name('bon.dxf')
        got, warning, critical = self.export(good)                              # l'export normal : rien de changé
        self.assertEqual((got, good.exists(), warning.call_count, critical.call_count), (str(good), True, 0, 0))

    def test_unexpected_errors_go_to_the_journal_and_the_status_bar(self):
        from vectordrive import journal
        self.assertIs(sys.excepthook, journal._hook)                            # posé par la fenêtre
        log = journal.path()
        if log.exists():
            log.unlink()
        try:
            raise ValueError('boum')
        except ValueError:
            with mock.patch.object(sys, 'stderr', None):                        # comme l'exécutable sans console
                sys.excepthook(*sys.exc_info())
        text = log.read_text(encoding='utf-8')
        self.assertIn('ValueError: boum', text)
        self.assertIn('test_round979.py', text)                                 # avec le chemin de l'erreur
        app.processEvents()
        self.assertIn('boum', self.w.statusBar().currentMessage())
        self.assertIn(journal.NAME, self.w.statusBar().currentMessage())

        def broken(*a, **k):
            raise RuntimeError('écriture en panne')
        with mock.patch.object(ED, 'export_items', broken):
            got, warning, critical = self.export(pathlib.Path(tempfile.mkdtemp()) / 'panne.dxf')
        self.assertEqual((got, critical.call_count), (None, 1))
        text = log.read_text(encoding='utf-8')
        self.assertIn('écriture en panne', text)                                # le détail d'un export en erreur
        self.assertIn('export .dxf', text)


if __name__ == '__main__':
    unittest.main()
