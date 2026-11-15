"""Round 321 : tableau (comme TABLE en DAO) — grille, textes des cellules,
largeurs de colonnes, alignement, longueur maximale des textes."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import table as TB
from vectordrive.core.document import Group, Plate, Text

app = QApplication.instance() or QApplication([])


class TestTable(unittest.TestCase):
    def test_rows(self):
        self.assertEqual(TB.rows_of('a;b\nc;;d'), [['a', 'b'], ['c', '', 'd']])
        self.assertEqual(TB.rows_of('a\tb\n\nc'), [['a', 'b'], ['c']])

    def test_build(self):
        spec = TB.TableSpec(content='A;B;C\n1;2;3', widths='10 30', width=60, row_height=10, align='center')
        lines, texts = TB.build(spec, (0, 20))
        self.assertEqual(TB.column_widths(spec, 3), [10, 30, 20])
        self.assertEqual(lines.bbox(), (0, 0, 60, 20))
        self.assertEqual(len(lines.contours), 1 + 1 + 2)               # cadre, 1 rangée, 2 colonnes
        self.assertEqual([t[0] for t in texts], ['A', 'B', 'C', '1', '2', '3'])
        self.assertEqual(texts[1][1], 25)                              # centre de la 2e colonne
        self.assertAlmostEqual(texts[0][2], 20 - 5 - spec.text_height / 2)
        self.assertEqual(texts[0][4], 7)                               # 10 − 2 × 1,5

    def test_command(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            w.canvas.doc.plate = Plate(100, 50)
            g = w.new_table({'content': 'Tension;230 V\nPuissance;1,5 kW', 'widths': '', 'width': 60.0,
                             'row_height': 8.0, 'text_height': 3.5, 'padding': 1.5, 'align': 'left', 'frame': True,
                             'inner': True, 'font': 'Arial'})
            self.assertIsInstance(g, Group)
            texts = [c for c in g.children if isinstance(c, Text)]
            self.assertEqual(len(texts), 4)
            b = g.bbox()
            self.assertAlmostEqual(b[0], 2.0)                              # au coin haut-gauche de la plaque
            self.assertAlmostEqual(b[3], 48.0)
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
