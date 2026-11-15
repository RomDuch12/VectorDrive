"""Round 163 : production des états (textes variables)."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import geom, variables as V
from vectordrive.core.document import Group, Plate, Shape, Text


def badge():
    frame = Shape(path=geom.Path([geom.rect(0, 0, 30, 10)]))
    t = Text(text='|Nom|', font='Police absente', matrix=geom.Affine.translation(2, 2))
    t.extra['template'] = '|Nom|'
    return [frame, t]


TABLE = V.VarTable(['Nom'], [['Ana'], ['Bob'], ['Cléo'], ['Dan'], ['Eve']])


class TestProduce(unittest.TestCase):
    def test_grid_and_values(self):
        items = badge()
        groups, lay = V.produce(items, TABLE, (0, 0, 90, 40), gap=2, margin=3)
        self.assertEqual((lay['cols'], lay['rows'], lay['plates']), (2, 2, 2))
        self.assertEqual([g.name for g in groups], ['État 1', 'État 2', 'État 3', 'État 4', 'État 5'])
        texts = [g.children[1] for g in groups]
        self.assertEqual([t.text for t in texts], ['Ana', 'Bob', 'Cléo', 'Dan', 'Eve'])
        self.assertTrue(all('template' not in t.extra for t in texts))
        self.assertEqual(items[1].text, '|Nom|')                                  # originaux intacts
        b = [g.bbox() for g in groups]
        self.assertLess(b[0][0], b[1][0])                                         # de gauche à droite
        self.assertGreater(b[0][1], b[2][1])                                      # puis vers le bas
        self.assertGreater(b[4][0], 90)                                           # 2e plaque à droite
        ids = {it.id for g in groups for it in g.children}
        self.assertFalse(ids & {it.id for it in items})                           # nouveaux objets

    def test_range_and_no_plate(self):
        groups, lay = V.produce(badge(), TABLE, None, first=1, last=2)
        self.assertEqual([g.children[1].text for g in groups], ['Bob', 'Cléo'])
        self.assertEqual(lay['rows'], 1)
        self.assertGreater(groups[0].bbox()[0], 30)                               # à droite des originaux
        self.assertEqual(V.produce(badge(), V.VarTable(['Nom'], []), None), ([], {}))

    def test_dates_and_groups(self):
        g = Group(children=[Text(text='Le |Date yyyy| — |Nom|', font='Police absente')])
        groups, _lay = V.produce([g], V.VarTable(['Nom'], [['Ana']]), None)
        inner = groups[0].children[0].children[0]
        self.assertRegex(inner.text, r'^Le 20\d\d — Ana$')


class TestCommand(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_command(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            doc = w.canvas.doc
            doc.plate = Plate(90, 40)
            items = [doc.add(x) for x in badge()]
            V.store(doc, TABLE)
            w.canvas.select(items)
            n_layers = len(doc.layers)
            groups = w.produce_states(exec_dialog=False, first=2, last=4)
            self.assertEqual(len(groups), 3)
            self.assertEqual(len(doc.layers), n_layers + 1)
            self.assertEqual(doc.layers[-1].name, 'États 2 à 4')
            self.assertFalse(any(it.visible for it in items))                     # originaux masqués
            w.undo()
            self.assertEqual(len(w.canvas.doc.layers), n_layers)
            self.assertTrue(all(it.visible for L in w.canvas.doc.layers for it in L.items))
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
