"""Round 168 : modes de sélection de TypeEdit — opérateurs et classement."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import geom, selsort as SS
from vectordrive.core.document import Document, Shape


def sq(x, y, s=4):
    return Shape(path=geom.Path([geom.rect(x, y, s, s)]), name=f'{x},{y}')


def grid():
    # 3 colonnes × 2 rangées, données en désordre ; rangée du haut à y = 20
    return [sq(20, 0), sq(0, 20), sq(10, 0), sq(20, 20), sq(0, 0), sq(10, 20)]


class TestCore(unittest.TestCase):
    def test_combine(self):
        a, b, c = sq(0, 0), sq(10, 0), sq(20, 0)
        self.assertEqual(SS.combine([a, b], [c], 'standard'), [c])
        self.assertEqual(SS.combine([a, b], [b, c], 'standard', ctrl=True), [a, c])
        self.assertEqual(SS.combine([a, b], [c], 'zone', ctrl=True), [c])
        self.assertEqual(SS.combine([a, b], [b, c], 'ajout'), [a, b, c])
        self.assertEqual(SS.combine([a, b], [b, c], 'retrait'), [a])
        self.assertEqual(SS.combine([a, b], [b, c], 'garder'), [b])

    def test_sorts(self):
        names = lambda items: [it.name for it in items]
        g = grid()
        self.assertEqual(names(SS.sort(g, 'h')), ['0,20', '10,20', '20,20', '0,0', '10,0', '20,0'])
        self.assertEqual(names(SS.sort(g, 'hz')), ['0,20', '10,20', '20,20', '20,0', '10,0', '0,0'])
        self.assertEqual(names(SS.sort(g, 'v')), ['0,20', '0,0', '10,20', '10,0', '20,20', '20,0'])
        self.assertEqual(names(SS.sort(g, 'vz')), ['0,20', '0,0', '10,0', '10,20', '20,20', '20,0'])
        self.assertEqual(names(SS.sort(g, 'inverse')), names(g)[::-1])

    def test_slight_misalignment_same_row(self):
        items = [sq(10, 0.8), sq(0, 0), sq(20, -0.5)]
        self.assertEqual([it.name for it in SS.sort(items, 'h')], ['0,0', '10,0.8', '20,-0.5'])

    def test_apply_order(self):
        d = Document()
        other = d.add(sq(100, 100))
        g = [d.add(x) for x in grid()]
        moved = SS.apply_order(d, SS.sort(g, 'h'))
        items = d.layers[0].items
        self.assertIs(items[0], other)                                            # non choisi : à sa place
        self.assertEqual([it.name for it in items[1:]], ['0,20', '10,20', '20,20', '0,0', '10,0', '20,0'])
        self.assertGreater(moved, 0)


class TestWindow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_operators_and_sort(self):
        from vectordrive.ui.main_window import MainWindow
        from vectordrive.ui.shortcuts import TE_ACTIONS
        self.assertEqual(TE_ACTIONS['ID_COMPO_SELECTIONMODES_OPERATEURS'], 'selection_modes')
        w = MainWindow()
        try:
            c = w.canvas
            g = [c.doc.add(x) for x in grid()]
            dlg = w.selection_modes(True)
            self.assertTrue(w.A['selection_modes'].isChecked())
            c.select(g[:2])
            dlg.radios['ajout'].setChecked(True)
            self.assertEqual(c.select_op, 'ajout')
            c.apply_pick([g[2]])
            self.assertEqual(c.selection, g[:3])
            dlg.radios['retrait'].setChecked(True)
            c.apply_pick([g[0], g[5]])
            self.assertEqual(c.selection, g[1:3])
            dlg.radios['garder'].setChecked(True)
            c.apply_pick([g[2], g[4]])
            self.assertEqual(c.selection, [g[2]])
            c.select(g)
            self.assertGreater(w.sort_selection('hz'), 0)
            self.assertEqual([it.name for it in c.doc.layers[0].items],
                             ['0,20', '10,20', '20,20', '20,0', '10,0', '0,0'])
            w.undo()
            self.assertEqual([it.name for it in w.canvas.doc.layers[0].items], [it.name for it in g])
            w.selection_modes(False)
            self.assertEqual(c.select_op, 'standard')                             # fermée : standard
            self.assertFalse(w.A['selection_modes'].isChecked())
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
