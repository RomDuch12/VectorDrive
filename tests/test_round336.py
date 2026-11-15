"""Round 336 : purger (comme PURGE en DAO) — formes et textes vides, groupes
vides, calques vides (l'actif reste), annulable."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import geom, purge as PG
from vectordrive.core.document import Document, Group, Layer, Shape, Text

app = QApplication.instance() or QApplication([])


def doc():
    d = Document()
    d.add(Shape(path=geom.Path([geom.rect(0, 0, 5, 5)])))
    d.add(Shape(path=geom.Path()))                                        # vide
    d.add(Text(text='  '))                                                # texte vide
    d.add(Group(children=[Shape(path=geom.Path())]))                      # groupe vide une fois purgé
    d.layers.append(Layer(name='Vide'))
    return d


class TestPurge(unittest.TestCase):
    def test_core(self):
        d = doc()
        counts = PG.purge(d)
        self.assertEqual(counts, {'objets': 3, 'groupes': 1, 'calques': 1})
        self.assertEqual(len(d.layers), 1)
        self.assertEqual(len(d.layers[0].items), 1)
        self.assertEqual(PG.purge(d), {'objets': 0, 'groupes': 0, 'calques': 0})

    def test_command(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            d = w.canvas.doc
            d.add(Shape(path=geom.Path([geom.rect(0, 0, 5, 5)])))
            d.add(Shape(path=geom.Path()))
            d.layers.append(Layer(name='Vide'))
            counts = w.purge()
            self.assertEqual((counts['objets'], counts['calques']), (1, 1))
            w.undo()
            self.assertEqual(len(w.canvas.doc.layers), 2)
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
