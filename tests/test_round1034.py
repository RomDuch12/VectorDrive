"""Round 1034 : demande du 15/11 ~10 h 45 « Gravure : SurepXY : juste en dessous Passe de finition (Usine la surep avec
les avances finition) ». Gravure 2,5D à l'outil conique : case « Passe de finition » juste sous la surépaisseur XY ;
les bords repris sur la forme exacte, à l'avance de finition."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1034.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication, QCheckBox, QFormLayout  # noqa: E402

app = QApplication.instance() or QApplication([])

from vectordrive.cam import model as M  # noqa: E402
from vectordrive.cam import strategies as S  # noqa: E402
from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Document, Layer, Plate, Shape  # noqa: E402
from vectordrive.ui import cam_panel as CP  # noqa: E402

LABEL = 'Passe de finition : la surépaisseur XY usinée à l’avance de finition'
STOCK = 0.3


def carve(stock=STOCK, finish=False, angle=90.0, tip=0.2, height=10.0, setup_out=None, **kw):
    """Un rectangle de 20 × `height` mm gravé à 0,5 mm avec un outil conique ; rend (parcours, opération, outil)."""
    doc = Document()
    doc.plate = Plate(width=100.0, height=60.0)
    rect = geom.polyline([(0, 0), (20, 0), (20, height), (0, height)], closed=True)
    doc.layers = [Layer(name='A', items=[Shape(path=geom.Path([rect]))])]
    setup = M.setup_of(doc)
    t = M.CamTool(name='v', kind='conique', diameter=6.0, tip=tip, angle=angle, feed=1000.0)
    setup.tools.append(t)
    op = M.Operation(kind='vcarve', tool_id=t.id, depth=0.5, step_down=9.0, resolution=0.05, stock=stock,
                     finish_feed=300.0, **kw)
    op.vcarve_finish = finish                            # avant : le champ n'existe pas (rien n'en tient compte)
    setup.operations.append(op)
    M.store(doc, setup)
    if setup_out is not None:
        setup_out.append(setup)
    return S.compute(doc, setup, op, (0.0, 0.0)), op, t


def heights(**kw):
    """Hauteurs de la matière laissée (simulation) le long de y = 2,5, de x = 0,02 à 19,98 mm (pas de 0,02)."""
    import numpy as np
    from vectordrive.cam import simulate
    box = []
    tp, _, _ = carve(setup_out=box, height=5.0, **kw)
    sim = simulate.simulate([tp], box[0], res=0.02)
    xs = np.arange(0.02, 19.99, 0.02)
    j = np.clip(np.round((xs - sim.x0) / sim.res).astype(int), 0, sim.H.shape[1] - 1)
    i = int(round((2.5 - sim.y0) / sim.res))
    return xs, sim.H[i, j]


def cutting(tp):
    return [(i, m) for i, m in enumerate(tp.moves) if m.kind != 'rapid' and m.z < -1e-6]


class Finishing(unittest.TestCase):

    def test_the_allowance_is_machined_at_the_finishing_feed(self):
        tp, op, tool = carve(finish=True)
        fin = [(i, m) for i, m in cutting(tp) if getattr(m, 'fin', False)]
        rough = [(i, m) for i, m in cutting(tp) if not getattr(m, 'fin', False)]
        self.assertTrue(fin, 'avant : aucune passe de finition')
        self.assertTrue(rough)
        self.assertGreater(min(i for i, _ in fin), max(i for i, m in rough if m.kind == 'feed'))   # après la gravure
        # au fond, la gravure passe en retrait de la surépaisseur ; la finition, à la place qui donne la forme exacte
        # (le flanc du cône y remonte jusqu'au bord dessiné : retrait de rt + profondeur × tan(45°) = 0,6 mm)
        self.assertAlmostEqual(min(m.z for _, m in fin), -0.5, places=6)      # jusqu'au fond
        low_fin = [m for _, m in fin if m.z < -0.5 + 1e-6]
        low_rough = [m for _, m in rough if m.z < -0.5 + 1e-6]
        self.assertAlmostEqual(min(m.x for m in low_fin), 0.6, delta=0.02)
        self.assertAlmostEqual(max(m.x for m in low_fin), 20 - 0.6, delta=0.02)
        self.assertAlmostEqual(min(m.x for m in low_rough), 0.6 + STOCK, delta=0.02)
        self.assertAlmostEqual(min(m.y for m in low_fin), 0.6, delta=0.02)
        self.assertEqual({M.move_feed(m, op, tool) for _, m in fin}, {300.0})  # l'avance de finition
        self.assertEqual({M.move_feed(m, op, tool) for _, m in rough}, {1000.0})

    def test_unchecked_or_without_allowance_nothing_changes(self):
        plain, _, _ = carve()
        self.assertFalse([m for m in plain.moves if getattr(m, 'fin', False)])
        bare, _, _ = carve(stock=0.0)
        same, _, _ = carve(stock=0.0, finish=True)                           # rien à finir
        self.assertEqual([(m.kind, m.x, m.y, m.z) for m in same.moves], [(m.kind, m.x, m.y, m.z) for m in bare.moves])
        on, _, _ = carve(finish=True)
        self.assertGreater(len(on.moves), len(plain.moves))                  # avant : la case ne change rien
        self.assertEqual([(m.kind, m.x, m.y, m.z) for m in on.moves[:len(plain.moves)]],
                         [(m.kind, m.x, m.y, m.z) for m in plain.moves])     # la gravure elle-même ne change pas

    def test_the_finished_surface_is_the_exact_engraving(self):
        # cône à 30°, pointe de 0,1 : la surépaisseur (0,3) est bien plus large que la pointe — la bande de fond
        # qu'elle laisse le long des bords doit être vidée aussi (avant ce correctif : 0,36 mm de crête sur 0,5)
        import numpy as np
        xs, ref = heights(stock=0.0, angle=30.0, tip=0.1)                    # la gravure sans surépaisseur
        _, done = heights(finish=True, angle=30.0, tip=0.1)
        _, left = heights(angle=30.0, tip=0.1)                               # sans la case : la surépaisseur reste
        # flancs du trait jusqu'à rt + 0,5 × tan(15°) = 0,184 mm ; la gravure seule vide le fond à partir de
        # 0,184 + 0,3 − 0,05 = 0,434 mm : entre les deux, la bande de fond
        band = (xs > 0.2) & (xs < 0.43)
        self.assertGreater(float(np.max(left[band] + 0.5)), 0.2)
        floor = (xs > 0.2) & (xs < 19.8)
        self.assertLess(float(np.max(np.abs(done[floor] + 0.5))), 0.03)       # le fond plat, bande comprise
        walls = (xs < 0.18) | (xs > 19.82)
        self.assertLess(float(np.max(np.abs(done[walls] - ref[walls]))), 0.05)   # les flancs de la gravure exacte

    def test_a_shape_lost_to_the_allowance_is_engraved_by_the_finishing(self):
        tp, op, tool = carve(stock=2.0, finish=True, height=3.0)             # 3 mm de large, 2 mm de surépaisseur
        self.assertTrue(any('trop grande' in w for w in tp.warnings))
        fin = [m for _, m in cutting(tp) if getattr(m, 'fin', False)]
        self.assertTrue(fin)
        self.assertAlmostEqual(min(m.z for m in fin), -0.5, places=6)
        ys = [m.y for m in fin if m.z < -0.5 + 1e-6]
        self.assertAlmostEqual(min(ys), 0.6, delta=0.02)                     # le fond entier, d'un bord à l'autre
        self.assertAlmostEqual(max(ys), 3.0 - 0.6, delta=0.02)

    def test_other_engraving_modes(self):
        for mode in ('axe', 'contour'):                                      # ligne médiane, contour 2D
            tp, op, tool = carve(finish=True, vcarve_mode=mode)
            fin = [m for _, m in cutting(tp) if getattr(m, 'fin', False)]
            self.assertTrue(fin, mode)
            self.assertEqual({M.move_feed(m, op, tool) for m in fin}, {300.0}, mode)
        tp, _, _ = carve(finish=True, vcarve_walls=False, vcarve_step=0.2)    # comme TE13 : paliers en Z
        fin = [m for _, m in cutting(tp) if getattr(m, 'fin', False)]
        self.assertTrue(fin)
        self.assertAlmostEqual(min(m.z for m in fin), -0.5, places=6)         # jusqu'au fond
        self.assertEqual({round(m.z, 6) for m in fin if m.kind == 'plunge'} - {-0.2, -0.4, -0.5}, set())  # par paliers

    def test_saved_operations_keep_their_toolpath(self):
        self.assertIs(getattr(M.Operation(), 'vcarve_finish', None), False)   # avant : pas de champ
        old = M.Operation(kind='vcarve').to_dict()
        old.pop('vcarve_finish', None)
        self.assertFalse(M.Operation.from_dict(old).vcarve_finish)
        on = M.Operation(kind='vcarve')
        on.vcarve_finish = True
        self.assertTrue(M.Operation.from_dict(on.to_dict()).vcarve_finish)


class Form(unittest.TestCase):

    def open(self, kind):
        d = CP.FieldsDialog(None, 'essai', M.Operation(kind=kind))
        self.addCleanup(d.deleteLater)
        return d

    def test_the_box_sits_just_below_the_xy_allowance(self):
        d = self.open('vcarve')
        self.assertIn('vcarve_finish', d.widgets)                            # avant : pas de case
        box = d.widgets['vcarve_finish']
        self.assertIsInstance(box, QCheckBox)
        self.assertFalse(d.rows['vcarve_finish'][1].isHidden())
        lab = d.rows['vcarve_finish'][0]
        self.assertEqual(lab.text(), LABEL)
        stock, mine = d.rows['stock'][1], d.rows['vcarve_finish'][1]
        self.assertFalse(stock.isHidden())
        forms = [f for f in d.findChildren(QFormLayout) if f.getWidgetPosition(stock)[0] >= 0]
        self.assertEqual(len(forms), 1)
        row_stock, _ = forms[0].getWidgetPosition(stock)
        row_box, _ = forms[0].getWidgetPosition(mine)
        self.assertEqual(row_box, row_stock + 1)                             # juste en dessous
        box.setChecked(True)
        d.apply()
        self.assertTrue(d.obj.vcarve_finish)

    def test_detourage_and_pocket_keep_their_own_box(self):
        for kind in ('contour', 'poche'):
            d = self.open(kind)
            self.assertIn('vcarve_finish', d.rows)
            self.assertTrue(d.rows['vcarve_finish'][1].isHidden(), kind)
            self.assertFalse(d.rows['finish'][1].isHidden(), kind)           # leur « Passe de finition »


if __name__ == '__main__':
    unittest.main()
