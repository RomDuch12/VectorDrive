"""Round 155 : coupon d'essai laser (repris de TauDrive) — grille où un
paramètre varie en X et un autre en Y, valeurs gravées, une opération par
case, étiquettes à puissance réduite."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.cam import coupon as CP, model, strategies as S
from vectordrive.core import geom
from vectordrive.core.document import Document, Shape, Text


def laser(**kw):
    d = dict(name='Laser', kind='laser', diameter=0.05, power=60.0, frequency=30.0, feed=2000.0, cut_length=0)
    d.update(kw)
    return model.CamTool(**d)


class TestValues(unittest.TestCase):
    def test_steps_and_format(self):
        self.assertEqual(CP.steps(20, 100, 5, 'power'), [20, 40, 60, 80, 100])
        self.assertEqual(CP.steps(1000, 2000, 4, 'feed'), [1000, 1500, 2000])          # arrondi à 500, sans doublon
        self.assertEqual(CP.steps(1, 4, 6, 'laser_passes'), [1, 2, 3, 4])
        self.assertEqual(CP.steps(0.01, 0.08, 3, 'resolution'), [0.01, 0.045, 0.08])
        self.assertEqual(CP.steps(50, 90, 1, 'power'), [50])
        self.assertEqual(CP.fmt(2500, 'feed'), '2.5')                                 # m/min
        self.assertEqual(CP.fmt(3, 'laser_passes'), '3')
        self.assertEqual(CP.fmt(62.5, 'power'), '62.5')


class TestBuild(unittest.TestCase):
    def test_grid(self):
        t = laser()
        c = CP.build(CP.Spec(x_field='power', x_from=20, x_to=60, x_count=3,
                             y_field='laser_passes', y_from=1, y_to=2, y_count=2,
                             fixed={'feed': 3000, 'frequency': 50}), t)
        self.assertEqual(c.cells, 6)
        cells = [ch for ch in c.group.children if isinstance(ch, Shape)]
        texts = [ch for ch in c.group.children if isinstance(ch, Text)]
        self.assertEqual(len(cells), 6)
        self.assertEqual(len(texts), 3 + 2 + 1)                                      # colonnes, rangées, titre
        self.assertEqual(sorted(x.power for x in c.tools), [20, 25, 40, 60])          # 3 cases + étiquettes (25 %)
        self.assertTrue(all(x.frequency == 50 for x in c.tools))
        cell_ops = c.operations[:-1]
        self.assertEqual([o.laser_passes for o in cell_ops], [1, 1, 1, 2, 2, 2])
        self.assertTrue(all(o.feed == 3000 and o.kind == 'laser_gravure' for o in cell_ops))
        self.assertEqual([o.items for o in cell_ops], [[x.id] for x in cells])
        tools = {x.id: x for x in c.tools}
        self.assertEqual([tools[o.tool_id].power for o in cell_ops], [20, 40, 60] * 2)
        lab = c.operations[-1]
        self.assertEqual((lab.kind, lab.laser_passes, sorted(lab.items)), ('laser', 1, sorted(x.id for x in texts)))
        self.assertEqual(tools[lab.tool_id].power, 25)
        # colonnes de gauche à droite, rangées de haut en bas
        xs = [x.bbox()[0] for x in cells[:3]]
        self.assertEqual(xs, sorted(xs))
        self.assertGreater(cells[0].bbox()[1], cells[3].bbox()[1])
        self.assertIn('20', [x.text for x in texts])

    def test_single_row_motif_center(self):
        motif = [geom.circle((50, 50), 5), geom.rect(40, 40, 3, 3)]
        c = CP.build(CP.Spec(x_count=2, y_field='', title=False, filled=False, center=(100, 50), cell=10), laser(),
                     motif=motif)
        cells = [ch for ch in c.group.children if isinstance(ch, Shape)]
        self.assertEqual(len(cells), 2)
        self.assertEqual(len(cells[0].path.contours), 2)
        bb = cells[0].bbox()
        self.assertAlmostEqual(max(bb[2] - bb[0], bb[3] - bb[1]), 9.0, places=6)    # 90 % de la case
        self.assertTrue(all(o.kind == 'laser' for o in c.operations))
        gb = c.group.bbox()
        self.assertLess(abs((gb[0] + gb[2]) / 2 - 100), 6)

    def test_compute(self):
        c = CP.build(CP.Spec(x_count=2, y_count=2), laser())
        d = Document()
        d.plate = None
        d.add(c.group)
        s = model.CamSetup()
        s.tools, s.operations = c.tools, c.operations
        tps = S.compute_all(d, s)
        self.assertEqual(len(tps), 5)
        for tp in tps[:4]:
            self.assertTrue(tp.moves)
            xs = [m.x for m in tp.moves if m.kind == 'feed']
            self.assertLess(max(xs) - min(xs), 8.0 + 1e-6)                           # une case, pas toute la grille


class TestPanel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_dialog(self):
        from vectordrive.ui.coupon_dialog import CouponDialog
        d = CouponDialog(None, [laser(power=40)])
        self.assertEqual(d.fixed['power'].value(), 40)
        self.assertFalse(d.fixed['power'].isEnabled())                               # porté par l'axe X
        self.assertTrue(d.fixed['frequency'].isEnabled())
        d.y.field.setCurrentIndex(d.y.field.findData('power'))
        self.assertIn('même paramètre', d.note.text())
        d.y.field.setCurrentIndex(d.y.field.findData('frequency'))
        self.assertEqual((d.y.lo.value(), d.y.hi.value()), (15, 45))                 # autour de 30 kHz
        s = d.spec()
        self.assertEqual((s.x_field, s.y_field, s.fixed['feed']), ('power', 'frequency', 2000))

    def test_panel_adds_items_and_ops(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            w.canvas.doc.plate = None
            panel = w.cam_panel
            n_ops = len(panel.setup().operations)
            c = panel.laser_coupon(exec_dialog=False, spec=CP.Spec(x_count=2, y_count=2), tool=laser())
            self.assertTrue(any(it is c.group for L in w.canvas.doc.layers for it in L.items))
            self.assertEqual(len(panel.setup().operations), n_ops + 5)
            w.undo()
            self.assertEqual(len(panel.setup().operations), n_ops)
            self.assertFalse(any(it is c.group or it.id == c.group.id for L in w.canvas.doc.layers for it in L.items))
            w.redo()
            self.assertEqual(len(panel.setup().operations), n_ops + 5)
            self.assertEqual(panel.ops.rowCount(), n_ops + 5)
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
