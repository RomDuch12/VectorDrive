"""Round 1059 : réponse du 15/11 à la question 28 — « Surép Z distincte » : un contour, une poche ou une reprise
laisse, en plus de sa surépaisseur sur les flancs, une surépaisseur Z au fond pour une finition."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1059.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])

from vectordrive.cam import model, strategies  # noqa: E402
from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Document, Shape  # noqa: E402

BEFORE = 'avant : la surépaisseur ne se règle que sur les flancs, le fond va toujours à la profondeur'


def doc_of(w=20.0, h=20.0):
    d = Document()
    d.layers[0].items.append(Shape(path=geom.Path([geom.rect(0.0, 0.0, w, h)]), tool=0))
    return d


def setup(*ops, tools=None):
    s = model.CamSetup()
    s.tools = tools or [model.CamTool(name='F2', diameter=2.0, step_down=0.5, number=1)]
    for o in ops:
        o.tool_id = o.tool_id or s.tools[0].id
        s.operations.append(o)
    return s


def cuts(tp):
    return [(m.x, m.y, m.z) for m in tp.moves if m.kind != 'rapid']


def floor(tp) -> float:
    return round(min(z for _x, _y, z in cuts(tp)), 6)


def run(kind, **kw):
    op = model.Operation(kind=kind, **kw)
    return strategies.compute(doc_of(), setup(op), op), op


class Floor(unittest.TestCase):

    def setUp(self):
        self.assertTrue(hasattr(strategies, 'left_on_floor'), BEFORE)

    def test_a_pocket_leaves_its_floor(self):
        tp, op = run('poche', depth=2.0, stock_z=0.5)
        self.assertEqual(floor(tp), -1.5)                                    # 0,5 mm laissés au fond
        self.assertEqual(sorted({round(z, 3) for _x, _y, z in cuts(tp) if z < 0}), [-1.5, -1.0, -0.5])
        self.assertEqual(op.depth, 2.0)                                      # l'opération garde sa profondeur
        self.assertEqual(floor(run('poche', depth=2.0)[0]), -2.0)
        self.assertFalse(tp.warnings)

    def test_a_contour_and_a_rest_too_the_others_not(self):
        self.assertEqual(floor(run('contour', depth=3.0, stock_z=1.0)[0]), -2.0)
        self.assertEqual(floor(run('gravure', depth=1.0, stock_z=0.4)[0]), -1.0)   # un tracé : pas de fond à laisser
        self.assertEqual([strategies.left_on_floor(model.Operation(kind=k, stock_z=0.4))
                          for k in ('contour', 'poche', 'reste', 'gravure', 'percage', 'vcarve')],
                         [0.4, 0.4, 0.4, 0.0, 0.0, 0.0])
        self.assertEqual(strategies.left_on_floor(model.Operation(kind='poche', stock_z=-1.0)), 0.0)

    def test_the_walls_keep_their_own_allowance(self):
        with_z, _ = run('poche', depth=2.0, stock=0.3, stock_z=0.5)
        without, _ = run('poche', depth=2.0, stock=0.3)
        reach = lambda tp: round(max(x for x, _y, _z in cuts(tp)), 4)        # noqa: E731
        self.assertEqual(reach(with_z), reach(without))                      # les flancs : la même surépaisseur XY
        self.assertEqual(reach(with_z), 20.0 - 1.0 - 0.3)
        self.assertEqual((floor(with_z), floor(without)), (-1.5, -2.0))

    def test_nothing_left_to_cut_is_said(self):
        for leave in (2.0, 3.0):
            tp, _ = run('poche', depth=2.0, stock_z=leave)
            self.assertEqual(cuts(tp), [])
            self.assertTrue(any('surépaisseur Z' in w for w in tp.warnings), tp.warnings)

    def test_a_pocket_that_leaves_its_floor_has_not_emptied_it(self):
        big = model.CamTool(name='F6', diameter=6.0, step_down=1.0, number=1)
        small = model.CamTool(name='F2', diameter=2.0, step_down=1.0, number=2)
        rough = model.Operation(name='E', kind='poche', tool_id=big.id, depth=2.0, stock_z=0.5)
        fine = model.Operation(name='F', kind='poche', tool_id=small.id, depth=2.0, rest_previous=True)
        s = model.CamSetup(tools=[big, small])
        s.operations = [rough, fine]
        self.assertEqual((strategies.pocket_bottom(rough), strategies.pocket_bottom(fine)), (-1.5, -2.0))
        self.assertEqual(strategies.previous_pockets(s, fine), [])           # le fond reste à faire partout
        tp = strategies.compute(doc_of(), s, fine)
        self.assertTrue(any(abs(x - 10) < 2 and abs(y - 10) < 2 and z < -1.9 for x, y, z in cuts(tp)))   # au milieu aussi
        self.assertTrue(any('surépaisseur Z' in w and '0.5' in w for w in tp.warnings), tp.warnings)   # et c'est dit
        rough.stock_z = 0.0                                                  # sans surépaisseur Z : vidé, pas repassé
        self.assertEqual(strategies.previous_pockets(s, fine), [rough])
        self.assertEqual(strategies.floor_left_before(s, fine), [])
        rough.stock_z = 5.0                                                  # plus que sa profondeur : rien d'usiné
        self.assertEqual(strategies.pocket_bottom(rough), 0.0)

    def test_the_floor_of_an_operation_is_counted_once(self):
        # l'ébauche s'arrête à −1,4 ; la poche d'après, « seulement le reste », à −1,5 (1,7 moins 0,2 laissés) : l'ébauche
        # n'a pas vidé jusque-là — vrai aussi pendant le calcul, où la profondeur est déjà réduite
        big = model.CamTool(name='F6', diameter=6.0, step_down=1.0, number=1)
        small = model.CamTool(name='F2', diameter=2.0, step_down=1.0, number=2)
        rough = model.Operation(name='E', kind='poche', tool_id=big.id, depth=1.9, stock_z=0.5)
        semi = model.Operation(name='D', kind='poche', tool_id=small.id, depth=1.7, stock_z=0.2, rest_previous=True)
        s = model.CamSetup(tools=[big, small])
        s.operations = [rough, semi]
        self.assertEqual(round(strategies.pocket_bottom(semi), 6), -1.5)
        tp = strategies.compute(doc_of(), s, semi)
        self.assertEqual(floor(tp), -1.5)
        self.assertTrue(any(abs(x - 10) < 2 and abs(y - 10) < 2 and z < -1.45 for x, y, z in cuts(tp)))   # le milieu aussi

    def test_cycles_start_and_rest_follow(self):
        tp, _ = run('poche', depth=2.0, stock_z=0.5)
        self.assertTrue(tp.cycles)
        self.assertEqual({round(c['depth'], 6) for c in tp.cycles}, {1.5})   # le cycle de la machine : au-dessus du fond
        tp, _ = run('poche', depth=2.0, stock_z=0.5, z_start=-1.0)
        self.assertEqual(floor(tp), -2.5)                                    # depuis le Z de départ
        big = model.CamTool(name='F6', diameter=6.0, step_down=1.0, number=1)
        small = model.CamTool(name='F2', diameter=2.0, step_down=1.0, number=2)
        rest = model.Operation(kind='reste', tool_id=small.id, ref_tool_id=big.id, depth=2.0, stock_z=0.5)
        s = model.CamSetup(tools=[big, small])
        s.operations = [rest]
        self.assertEqual(floor(strategies.compute(doc_of(), s, rest)), -1.5)

    def test_the_relief_drawn_from_the_drawing_counts_what_is_cut(self):
        from vectordrive.cam import relief
        d = doc_of()
        s = model.setup_of(d)
        s.operations = [model.Operation(kind='poche', depth=2.0, stock_z=0.5, sources=[0]),
                        model.Operation(kind='gravure', depth=1.0, stock_z=0.5, sources=[1])]
        d.extra['fao'] = s.to_dict()
        depths = relief.tool_depths(d)
        self.assertEqual((depths[0], depths[1]), (1.5, 1.0))

    def test_kept_with_the_operation(self):
        op = model.Operation(kind='poche', depth=2.0, stock_z=0.25)
        self.assertEqual(model.Operation.from_dict(op.to_dict()).stock_z, 0.25)
        old = op.to_dict()
        del old['stock_z']
        self.assertEqual(model.Operation.from_dict(old).stock_z, 0.0)        # un réglage d'avant : rien de laissé


class Form(unittest.TestCase):

    def setUp(self):
        self.assertTrue(hasattr(strategies, 'left_on_floor'), BEFORE)

    def test_the_field_is_shown_where_it_counts(self):
        from vectordrive.ui import cam_panel as CP
        for kind, shown in (('contour', True), ('poche', True), ('reste', True), ('gravure', False),
                            ('percage', False), ('vcarve', False)):
            d = CP.FieldsDialog(None, 'essai', model.Operation(kind=kind))
            self.addCleanup(d.deleteLater)
            self.assertEqual(not d.rows['stock_z'][0].isHidden(), shown, kind)
        self.assertIn('Z', CP.field_label('stock_z', 'poche'))
        d = CP.FieldsDialog(None, 'essai', model.Operation(kind='poche', stock_z=0.3))
        self.addCleanup(d.deleteLater)
        self.assertAlmostEqual(d.widgets['stock_z'].value(), 0.3)
        d.widgets['stock_z'].setValue(0.6)
        d.apply()
        self.assertAlmostEqual(d.obj.stock_z, 0.6)
        self.assertIn('stock_z', CP.CamPanel.LAST_SKIP)                      # pas repris par l'opération suivante


if __name__ == '__main__':
    unittest.main()
