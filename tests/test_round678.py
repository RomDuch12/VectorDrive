"""Round 678 : « Modifier la pièce générée… » (onglet Design STEP) — une pièce ajoutée au dessin par les
générateurs rouverte avec sa famille et ses valeurs, remplacée à sa place (même milieu en X et Y, même dessous,
même après un déplacement), annulable, remplacée encore ; refus dits (rien de choisi, plusieurs objets, pas une
pièce générée, famille inconnue) ; pièce supprimée entre-temps : ajoutée à neuf."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import solids as SO
from vectordrive.core import stepgen as G

app = QApplication.instance() or QApplication([])


class TestEdit(unittest.TestCase):
    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self._tmp = tempfile.TemporaryDirectory()
        self.w = MainWindow()
        self.w.step_depot_folder(self._tmp.name)

    def tearDown(self):
        for i in range(len(self.w.docs)):
            self.w.docs[i].modified = False
        self.w.modified = False
        self.w.close()
        self._tmp.cleanup()

    def solids(self):
        return [it for L in self.w.canvas.doc.layers for it in L.items if SO.is_solid(it)]

    def add_plate(self, **over):
        d = self.w.stepgen_dialog(None, exec_dialog=False)
        d.select_family('plaque')
        for k, v in over.items():
            d.set_value(k, v)
        new = d.add_to_drawing()
        d.deleteLater()
        self.assertEqual(len(new), 1)
        return new[0]

    def test_tab(self):
        from tests.test_round672 import full_hd, tab_index
        w = self.w
        page = w.ribbon.page(tab_index(w.ribbon, 'Design STEP'))
        gen = next(g for g in page.groups() if g.title.text() == 'Générateurs')
        self.assertIn(w.A['stepgen_edit'], [b.defaultAction() for b in gen.buttons()])
        self.assertEqual(page.fit(full_hd()), [])

    def test_replace_in_place(self):
        w = self.w
        self.add_plate(length=140.0, thickness=8.0)
        w.canvas.select(self.solids())
        w.move_by(30.0, -20.0)                                           # déplacée après l'ajout
        moved = self.solids()[0]
        self.assertEqual(moved.extra['stepgen']['values']['length'], 140.0)
        x0, y0, z0, x1, y1, z1 = SO.of_item(moved).bounds()
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        d = w.stepgen_edit(exec_dialog=False)
        self.assertEqual(d.key, 'plaque')
        self.assertEqual(d.current_values()['length'], 140.0)
        self.assertEqual(d.current_values()['thickness'], 8.0)
        self.assertEqual(d.b_add.text(), 'Remplacer dans le dessin')
        d.set_value('length', 200.0)
        new = d.add_to_drawing()
        self.assertEqual(len(new), 1)
        self.assertEqual(self.solids(), new)                              # l'ancienne remplacée, pas doublée
        a0, b0, c0, a1, b1, c1 = SO.of_item(new[0]).bounds()
        self.assertAlmostEqual((a0 + a1) / 2, cx, 3)
        self.assertAlmostEqual((b0 + b1) / 2, cy, 3)
        self.assertAlmostEqual(c0, z0, 3)
        self.assertAlmostEqual(a1 - a0, 200.0, 3)
        self.assertEqual(new[0].extra['stepgen']['values']['length'], 200.0)
        d.set_value('thickness', 12.0)                                    # remplacée encore
        again = d.add_to_drawing()
        self.assertEqual(self.solids(), again)
        self.assertAlmostEqual(SO.of_item(again[0]).bounds()[5] - c0, 12.0, 3)
        d.deleteLater()
        w.undo()
        w.undo()
        back = self.solids()
        self.assertEqual(len(back), 1)
        self.assertEqual(back[0].extra['stepgen']['values']['length'], 140.0)   # annulé : celle d'avant
        self.assertAlmostEqual(SO.of_item(back[0]).bounds()[0], x0, 3)

    def test_raised_part_keeps_its_bottom(self):
        w = self.w
        it = self.add_plate()
        st = dict(it.extra['stepgen'])
        sol = SO.of_item(it)
        import numpy as np
        m = np.eye(4)
        m[2, 3] = 25.0
        raised = SO.make_shape(sol.transformed(m), w.canvas.current_tool_index)   # posée sur une autre, Z = 25
        raised.extra['stepgen'] = st
        w.canvas.selection = [it]
        w._replace_selection([raised])
        d = w.stepgen_edit(raised, exec_dialog=False)
        d.set_value('width', 80.0)
        new = d.add_to_drawing()
        self.assertAlmostEqual(SO.of_item(new[0]).bounds()[2], 25.0, 3)
        d.deleteLater()

    def test_refusals(self):
        w = self.w
        self.assertIsNone(w.stepgen_edit(exec_dialog=False))             # rien de choisi
        self.assertIn('pièce ajoutée par les générateurs', w.statusBar().currentMessage())
        a = self.add_plate()
        b = self.add_plate(length=50.0)
        w.canvas.select([a, b])
        self.assertIsNone(w.stepgen_edit(exec_dialog=False))             # deux objets
        w.canvas.select([a])
        a.extra['stepgen'] = {'key': 'inconnue', 'values': {}}
        self.assertIsNone(w.stepgen_edit(exec_dialog=False))             # famille inconnue
        del a.extra['stepgen']
        self.assertIsNone(w.stepgen_edit(exec_dialog=False))             # pas une pièce générée
        d = w.stepgen_dialog(None, exec_dialog=False)
        self.assertFalse(d.edit_item(None))
        d.deleteLater()

    def test_deleted_meanwhile(self):
        w = self.w
        it = self.add_plate()
        w.canvas.select([it])
        d = w.stepgen_edit(exec_dialog=False)
        w.delete()
        self.assertEqual(self.solids(), [])
        new = d.add_to_drawing()                                          # ajoutée à neuf, au centre de la plaque
        self.assertEqual(len(new), 1)
        self.assertEqual(d.b_add.text(), 'Ajouter au dessin')
        plate = w.canvas.doc.plate
        if plate is not None:
            x0, y0, _z0, x1, y1, _z1 = SO.of_item(new[0]).bounds()
            self.assertAlmostEqual((x0 + x1) / 2, plate.x + plate.width / 2, 3)
        d.deleteLater()

    def test_every_family_reopens(self):
        w = self.w
        for key in ('chc', 'cale_etagee', 'roulement', 'barre'):
            d = w.stepgen_dialog(None, exec_dialog=False)
            d.select_family(key)
            new = d.add_to_drawing()
            d.deleteLater()
            e = w.stepgen_edit(new[0], exec_dialog=False)
            self.assertEqual(e.key, key)
            self.assertEqual(e.current_values(), G.values(key))
            e.deleteLater()


if __name__ == '__main__':
    unittest.main()
