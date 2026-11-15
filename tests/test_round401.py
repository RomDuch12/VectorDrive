"""Round 401 : ponctuation typographique française des textes."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core.document import Text
from vectordrive.core.textops import NBSP, typographic

app = QApplication.instance() or QApplication([])


class TestTypographic(unittest.TestCase):
    def test_rules(self):
        self.assertEqual(typographic('Il dit "oui" !'), f'Il dit \u00ab{NBSP}oui{NBSP}\u00bb{NBSP}!')
        self.assertEqual(typographic("L'atelier..."), 'L\u2019atelier\u2026')
        self.assertEqual(typographic('Prix : 10 -- 20'), f'Prix{NBSP}: 10 \u2014 20')
        self.assertEqual(typographic('Ouvert 10:30'), 'Ouvert 10:30')       # heures intactes
        once = typographic('Vraiment ? "Oui"')
        self.assertEqual(typographic(once), once)                         # déjà fait : inchangé

    def test_window(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            t = Text(text="C'est ici ?", font='Arial', size=5.0)
            w.canvas.doc.add(t)
            w.canvas.select([t])
            self.assertEqual(w.text_typographic(), 1)
            texts = [x for x in w.canvas.doc.iter_leaves() if isinstance(x, Text)]
            self.assertEqual(texts[0].text, f'C\u2019est ici{NBSP}?')
            self.assertEqual(w.text_typographic(), 0)
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
