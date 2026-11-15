"""Round 388 : styles de texte nommés (TypeEdit : Créer / Utiliser un style)."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core.document import Text

app = QApplication.instance() or QApplication([])


class TestStyles(unittest.TestCase):
    def test_save_apply_delete(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            a = Text(text='Titre', font='Arial', size=12.0, align='center', spacing=0.5)
            b = Text(text='Corps', font='Arial', size=3.0)
            w.canvas.doc.add(a)
            w.canvas.doc.add(b)
            w.canvas.select([a])
            self.assertEqual(w.text_style('save', 'Titre gros'), 1)
            self.assertIn('Titre gros', w.text_styles())
            w.canvas.select([b])
            self.assertEqual(w.text_style('apply', 'Titre gros'), 1)
            self.assertEqual((b.size, b.align, b.spacing), (12.0, 'center', 0.5))
            self.assertEqual(b.text, 'Corps')                              # le contenu reste
            self.assertEqual(w.text_style('apply', 'inconnu'), 0)
            self.assertEqual(w.text_style('delete', 'Titre gros'), 1)
            self.assertNotIn('Titre gros', w.text_styles())
        finally:
            w.settings.remove('texte/styles')
            w.settings.remove('texte/style_courant')
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
