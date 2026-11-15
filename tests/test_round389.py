"""Round 389 : informations du document (TypeEdit : Fichier › Informations)."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import geom
from vectordrive.core.document import Shape, Text

app = QApplication.instance() or QApplication([])


class TestDocInfo(unittest.TestCase):
    def test_info(self):
        from vectordrive.ui.main_window import MainWindow
        from vectordrive.io import native
        w = MainWindow()
        try:
            doc = w.canvas.doc
            doc.add(Shape(path=geom.Path([geom.rect(0, 0, 5, 5)])))
            doc.add(Text(text='A', font='Arial', size=5.0))
            st = w.doc_stats()
            self.assertEqual((st['objets'], st['textes']), (2, 1))
            self.assertTrue(w.set_doc_info({'title': 'Plaque porte', 'client': 'Atelier', 'comments': 'ligne 1\nligne 2'}))
            self.assertEqual(doc.extra['info']['comments'], 'ligne 1\nligne 2')
            self.assertNotIn('author', doc.extra['info'])                  # champs vides non gardés
            self.assertFalse(w.set_doc_info(dict(doc.extra['info'])))     # inchangé
            path = os.path.join(tempfile.mkdtemp(), 'info.vnd')
            native.write(doc, path)
            self.assertEqual(native.read(path).extra['info']['title'], 'Plaque porte')
            w.undo()
            self.assertNotIn('info', w.canvas.doc.extra)
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
