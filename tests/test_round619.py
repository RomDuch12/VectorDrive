"""Round 619 : reprise 3D — les déplacements rapides redeviennent ceux de toujours (dégagement, hauteur
d'approche, plongée) : descendre ou sauter « au ras » de la matière laissée par l'outil d'avant entrait dans les
marches d'une ébauche par paliers (relecture). Zones calculées sur leur cadre ; le centre de l'outil reste dans
la zone choisie. Fenêtre « Mécanismes » : le tableau des mouvements rempli de nouveau ne laisse plus d'anciennes
cases visibles par-dessus les nouvelles."""
import math
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication, QCheckBox, QDoubleSpinBox

from tests.test_round591 import feeds
from tests.test_round595 import box_tris, model_of
from vectordrive.cam import auto3d as A
from vectordrive.cam import model, strategies
from vectordrive.core import solids as SO
from vectordrive.core.document import Document

app = QApplication.instance() or QApplication([])


class TestMovesTable(unittest.TestCase):
    def test_no_stale_cells(self):
        from vectordrive.ui.main_window import MainWindow
        from vectordrive.ui.view3d import Panel3D
        w = MainWindow()
        try:
            p = Panel3D(w)
            m = model_of(box_tris(0, 0, 0, 10, 10, 5), box_tris(0, 0, 5, 10, 10, 10), box_tris(20, 0, 0, 30, 10, 5),
                         box_tris(20, 0, 5, 30, 10, 10))
            p.model = m
            p.view.set_model(m)
            dlg = p.mechanisms(show=False)
            rows = dlg.moves_table.rowCount()
            for _k in range(3):
                dlg._fill_moves()                                       # sans boucle d'évènements entre deux
            vp = dlg.moves_table.viewport()
            shown = [x for x in vp.findChildren(QCheckBox) + vp.findChildren(QDoubleSpinBox) if not x.isHidden()]
            self.assertEqual(len(shown), 3 * rows)
            dlg.done(0)
        finally:
            w.modified = False
            w.close()


def sloped_pocket():
    """Bloc 60 × 40 × 20, poche 30 × 10 dont le fond monte en pente (biseau) : une ébauche par paliers y laisse
    des marches."""
    from vectordrive.io import stl_write
    s = SO.boolean('union', [SO.boolean('subtract', [SO.box(0, 0, 0, 60, 40, 20), SO.box(10, 10, 5, 40, 20, 20)]),
                             SO.wedge(50, 10, 5, -40, 20, 10)])
    f = pathlib.Path(tempfile.mkdtemp()) / 'poche_en_pente.stl'
    stl_write.write_stl(str(f), s.triangles())
    return str(f)


@unittest.skipUnless(SO.available(), 'manifold3d absent')
class TestRestRapids(unittest.TestCase):
    def test_rapids_above_clear_after_roughing(self):
        f = sloped_pocket()
        seq = A.builtin()['Ébauche, reprise, finition des pentes et des parois']
        tools = [model.CamTool(kind='fraise', diameter=12, cut_length=60, step_down=4.0),
                 model.CamTool(kind='fraise', diameter=6, cut_length=60, step_down=2.0),
                 model.CamTool(kind='boule', diameter=4, cut_length=60)]
        out = A.plan(seq, tools, [], A.PartInfo(60, 40, 15, 2.0, 48), model_path=f, depth=0)
        rest = out[1].op
        self.assertEqual(rest.kind, 'reprise3d')
        st = model.CamSetup(tools=[p.tool for p in out[:2]])
        tp = strategies.compute(Document(), st, rest)
        self.assertTrue(feeds(tp))
        prev = None
        for mv in tp.moves:                                             # rapide : au-dessus, ou à la verticale
            if mv.kind == 'rapid' and prev is not None and mv.z < rest.clear_z - 1e-9:
                self.assertAlmostEqual(math.hypot(mv.x - prev.x, mv.y - prev.y), 0.0, 9, (prev, mv))
                self.assertGreater(mv.z, prev.z, (prev, mv))            # seulement en remontant
            prev = mv

    def test_tool_centre_in_the_zone(self):
        from tests.test_round591 import pocket_stl
        f = pocket_stl()                                                # poche 20 × 10 (x 10..30)
        big = model.CamTool(kind='fraise', diameter=6, stepover=0.4, step_down=1.0)
        small = model.CamTool(kind='fraise', diameter=2, stepover=0.4, step_down=1.0)
        st = model.CamSetup(tools=[big, small])
        zone = [[[9.0, 4.0, 5.0], [16.0, 4.0, 5.0], [16.0, 16.0, 5.0], [9.0, 16.0, 5.0]]]   # moitié gauche de la poche
        op = model.Operation(kind='reprise3d', tool_id=small.id, ref_tool_id=big.id, depth=0, model_path=f,
                             resolution=0.1, contours3d=zone)
        fs = feeds(strategies.compute(Document(), st, op))
        self.assertTrue(fs)
        self.assertLess(max(mv.x for mv in fs), 16.0 + 1.0 + 0.2)      # au plus un rayon au-delà de la zone
        self.assertLess(max(mv.x for mv in fs), 20.0)                   # pas les coins de droite


if __name__ == '__main__':
    unittest.main()
