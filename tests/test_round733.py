"""Round 733 : Rappeler l'effacement (OOPS, d'après CADCraft) — ce que le
dernier Effacer a retiré revient à sa place, même après d'autres
modifications ; une seule annulation."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.core.document import Layer, Shape
from vectordrive.core.geom import Path, rect


def _sq(x, name):
    return Shape(path=Path([rect(x, 0, 5, 5)]), name=name)


class TestOops(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])
        from vectordrive.ui.main_window import MainWindow
        cls.w = MainWindow()
        cls.w.resize(1000, 700)

    @classmethod
    def tearDownClass(cls):
        cls.w.modified = False
        cls.w.close()

    def setUp(self):
        w = self.w
        w.new_document() if hasattr(w, 'new_document') else None
        doc = w.canvas.doc
        self.L = doc.active_layer
        self.L.items = [_sq(10 * i, n) for i, n in enumerate('abcde')]
        w._undo.clear()

    def names(self):
        return ''.join(it.name for it in self.w.canvas.doc.active_layer.items)   # défaire remplace les calques

    def test_back_in_place_after_other_edits(self):
        w, c = self.w, self.w.canvas
        items = {it.name: it for it in self.L.items}
        c.select([items['b'], items['c'], items['e']])
        w.delete()
        self.assertEqual(self.names(), 'ad')
        w.push_undo()                                           # d'autres modifications ensuite :
        self.L.items.insert(0, _sq(99, 'n'))                    # un objet ajouté dessous
        back = w.oops()
        self.assertEqual([it.name for it in back], ['b', 'c', 'e'])
        self.assertEqual(self.names(), 'nabcde')                 # b, c au-dessus de a ; e au-dessus de d
        self.assertEqual({it.name for it in c.selection}, {'b', 'c', 'e'})
        self.assertIn('3', w.statusBar().currentMessage())
        self.assertEqual(w.oops(), [])                          # rappelé une fois
        w.undo()                                                # une seule annulation
        self.assertEqual(self.names(), 'nad')

    def test_neighbour_above_and_layer(self):
        w, c = self.w, self.w.canvas
        items = {it.name: it for it in self.L.items}
        c.select([items['b']])
        w.delete()
        w.push_undo()
        self.L.items.remove(items['a'])                         # le voisin du dessous n'est plus là
        self.assertEqual([it.name for it in w.oops()], ['b'])
        self.assertEqual(self.names(), 'bcde')                  # sous c, qui était dessus

    def test_nothing_to_bring_back(self):
        w, c = self.w, self.w.canvas
        self.assertEqual(w.oops(), [])
        self.assertIn('Rien', w.statusBar().currentMessage())
        items = {it.name: it for it in self.L.items}
        c.select([items['a']])
        w.delete()
        w.undo()                                                # l'effacement défait : rien à rappeler
        self.assertEqual(w.oops(), [])
        self.assertEqual(self.names(), 'abcde')
        c.select([w.canvas.doc.active_layer.items[1]])
        w.delete()
        doc = w.canvas.doc
        doc.layers = [Layer(name='autre')]                      # son calque a disparu
        self.assertEqual(w.oops(), [])

    def test_ribbon_icon(self):
        from vectordrive.ui import icons
        self.assertIn('oops', icons.ICONS)
        self.assertFalse(self.w.A['oops'].icon().isNull())
        self.assertTrue(self.w.A['oops'].toolTip())


if __name__ == '__main__':
    unittest.main()
