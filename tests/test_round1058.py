"""Round 1058 : plaques de reprise, réponses du 15/11 (question 33) et du 16/11 — une CHC M4 passe dans un trou de
4,05 ; les M6 fraisés tous les 100 mm fixent la plaque sur la table, ce ne sont pas des places de vis ; « drillmill si
>= M6 sinon percage-taraudage en une seule opé » ; profondeur 3,5 mm pour 7 mm, 6 mm pour 10 mm."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1058.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])

from vectordrive.cam import fixture as FX  # noqa: E402
from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Document, Layer, Plate, Shape  # noqa: E402

BEFORE = 'avant : un trou de 4,05 donne M3, et toujours un perçage au foret plus un taraudage'


def circle(x, y, d):
    return Shape(path=geom.Path([geom.circle((x, y), d / 2)]), tool=0)


def drawing(screw=4.05, table=6.4):
    """Une plaque percée Ø `screw` tous les 25 mm (8 × 4) et Ø `table` tous les 100 mm (2 × 2, entre les autres) ; un
    brut de 60 × 60 qui couvre neuf trous de vis et un trou de table."""
    plate = Layer(name='Plaque')
    plate.items = [circle(25.0 * i, 25.0 * j, screw) for i in range(8) for j in range(4)]
    plate.items += [circle(37.5 + 100.0 * i, 12.5 + 50.0 * j, table) for i in range(2) for j in range(2)]
    blanks = Layer(name='Bruts')
    a = Shape(path=geom.Path([geom.rect(-10.0, -10.0, 70.0, 70.0)]), tool=1)
    blanks.items = [a]
    return Document(layers=[plate, blanks]), plate, blanks, a


def at(holes):
    return sorted((round(h.x, 3), round(h.y, 3)) for h in holes)


class Model(unittest.TestCase):

    def setUp(self):
        self.assertTrue(hasattr(FX, 'depth_for'), BEFORE)

    def test_an_m4_screw_goes_through_a_4_05_hole(self):
        got = [FX.thread_for(d) for d in (4.05, 4.0, 3.2, 3.0, 5.2, 6.05, 6.4, 13.99, 1.5)]
        self.assertEqual(got, ['M4', 'M4', 'M3', 'M3', 'M5', 'M6', 'M6', 'M12', ''])

    def test_the_most_frequent_holes_are_the_screw_holes(self):
        doc, plate, blanks, a = drawing()
        pl = FX.layout([a], plate.items, FX.Spec(per_blank=0))
        self.assertEqual(pl.thread, 'M4')
        self.assertEqual(len(pl.blanks[0][1]), 9)
        self.assertNotIn((37.5, 12.5), at(pl.blanks[0][1]))                  # le trou de la table : pas une vis
        every = FX.layout([a], plate.items, FX.Spec(per_blank=0, common_only=False))
        self.assertIn((37.5, 12.5), at(every.blanks[0][1]))
        self.assertEqual(len(every.blanks[0][1]), 10)
        holes = [FX.Hole(0, 0, 4.0), FX.Hole(1, 0, 4.05), FX.Hole(2, 0, 4.05), FX.Hole(3, 0, 6.4), FX.Hole(4, 0, 6.4)]
        self.assertEqual([h.x for h in FX.common(holes)], [0, 1, 2])         # 4 et 4,05 : le même trou
        self.assertEqual([h.x for h in FX.common(holes[1:])], [1, 2])        # à égalité : le plus petit
        self.assertEqual(FX.common([]), [])

    def test_depth_from_the_thickness(self):
        self.assertEqual([FX.depth_for(t) for t in (7, 10, 12, 8, 4, 0)], [3.5, 6.0, 6.0, 4.5, 0.0, 0.0])
        self.assertEqual(FX.depth_for(10, machined=5), 4.5)
        s = FX.Spec(depth=5.0)
        self.assertEqual((s.depth_on(7), s.depth_on(0), s.depth_on(None)), (3.5, 5.0, 5.0))   # inconnue : la réglée
        self.assertEqual(s.depth_on(4), 0.0)                                 # connue, trop mince : rien à tarauder
        self.assertEqual(FX.Spec(depth=5.0, auto_depth=False).depth_on(4), 5.0)
        # le perçage (à partir de M6) : 2 mm sous le taraudage, sans entrer dans ce qui sera usiné en face
        self.assertEqual([FX.Spec().drill_on(t) for t in (10, 12, 7, 0, 4)], [6.5, 8.0, 3.5, 8.0, 0.0])
        self.assertEqual(FX.Spec(auto_depth=False).drill_on(10), 8.0)
        back = FX.Spec.from_dict(FX.Spec(common_only=False, auto_depth=False, machined=2.0).to_dict())
        self.assertEqual((back.common_only, back.auto_depth, back.machined), (False, False, 2.0))
        odd = FX.Spec.from_dict({'common_only': 'false', 'auto_depth': 'True'})
        self.assertEqual((odd.common_only, odd.auto_depth), (False, True))
        old = FX.Spec.from_dict({'depth': 4.0, 'common_only': None})         # un réglage d'avant : les cases cochées
        self.assertEqual((old.common_only, old.auto_depth, old.machined, old.depth), (True, True, 3.0, 4.0))

    def test_predrilled_from_m6(self):
        self.assertEqual([FX.predrilled(t) for t in ('M3', 'M4', 'M5', 'M6', 'M8', '', 'M7')],
                         [False, False, False, True, True, False, False])


class Panel(unittest.TestCase):

    def setUp(self):
        self.assertTrue(hasattr(FX, 'depth_for'), BEFORE)
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()

        def close():
            self.w.modified = False
            for t in getattr(self.w, 'docs', []):
                t.modified = False
            self.w.settings.remove('fao/plaque_reprise')
            self.w.close()
            app.processEvents()
        self.addCleanup(close)

    def put(self, screw=4.05, table=6.4, thickness=7.0):
        p = self.w.cam_panel
        doc, plate, blanks, a = drawing(screw, table)
        p.doc.layers.extend([plate, blanks])
        if p.doc.plate is None:
            p.doc.plate = Plate()
        p.doc.plate.thickness = thickness
        return p, plate, a

    def test_under_m6_one_operation_the_thread_mill_drills(self):
        from vectordrive.cam import model
        from vectordrive.core import holes
        p, plate, a = self.put()
        before = len(p.setup().operations)
        pl = p.fixture_holes(exec_dialog=False, spec=FX.Spec(depth=5.0), plate_layer=plate, blanks=[a])
        self.assertEqual((pl.thread, pl.count()), ('M4', 4))
        ops = p.setup().operations[before:]
        self.assertEqual([o.kind for o in ops], ['taraudage'])               # ni foret, ni perçage à part
        self.assertEqual(ops[0].name, 'Perçage-taraudage M4 des bruts')
        self.assertEqual((ops[0].thread, ops[0].depth), ('M4', 3.5))         # plaque de 7 mm : 3,5 mm
        layer = p.doc.layers[-1]
        self.assertEqual(layer.name, 'Fixation des bruts M4')
        self.assertEqual(sorted(ops[0].items), sorted(it.id for it in layer.items))
        self.assertAlmostEqual(holes.circle_of(layer.items[0])[2] * 2, model.THREADS['M4'][2], places=3)
        self.assertEqual(holes.spec_of(layer.items[0]).depth, 3.5)           # le trou dessiné : à la profondeur taraudée
        self.assertTrue('3,5' in p.info.text() or '3.5' in p.info.text(), p.info.text())
        tp = next(x for x in p.toolpaths if x.op_id == ops[0].id)
        self.assertEqual(len(tp.cycles), 4)                                  # quatre cycles de taraudage, au centre
        self.assertEqual({(c['kind'], c['depth'], c['thread']) for c in tp.cycles}, {('taraudage', 3.5, 'M4')})
        tool = next(t for t in p.setup().tools if t.id == ops[0].tool_id)
        self.assertEqual((tool.kind, tool.diameter), ('fraise', 3.3))        # elle perce l'avant-trou : faite à son Ø
        self.assertIn(tool.name, p.info.text())                              # dite, à vérifier

    def test_the_mill_that_drills_is_never_a_thin_one(self):
        from vectordrive.cam import model
        p, plate, a = self.put()
        s = p.setup()
        s.tools += [model.CamTool(name='Fine', kind='fraise', diameter=1.0),      # laisserait un noyau
                    model.CamTool(name='Filet M4', kind='fraise', diameter=3.2),
                    model.CamTool(name='Grosse', kind='fraise', diameter=3.5)]    # plus grosse que l'avant-trou
        p.save(s)
        before = len(p.setup().operations)
        p.fixture_holes(exec_dialog=False, spec=FX.Spec(), plate_layer=plate, blanks=[a])
        op = p.setup().operations[before]
        self.assertEqual(next(t.name for t in p.setup().tools if t.id == op.tool_id), 'Filet M4')

    def test_a_blank_too_thin_gets_nothing(self):
        p, plate, a = self.put(thickness=4.0)
        layers, ops, steps = len(p.doc.layers), len(p.setup().operations), len(self.w._undo)
        self.assertIsNone(p.fixture_holes(exec_dialog=False, spec=FX.Spec(), plate_layer=plate, blanks=[a]))
        self.assertEqual((len(p.doc.layers), len(p.setup().operations), len(self.w._undo)), (layers, ops, steps))
        self.assertIn('trop mince', p.info.text())
        pl = p.fixture_holes(exec_dialog=False, spec=FX.Spec(depth=2.0, auto_depth=False), plate_layer=plate,
                             blanks=[a])
        self.assertEqual(p.setup().operations[-1].depth, 2.0)                # à la main : comme demandé
        self.assertEqual(pl.count(), 4)

    def test_the_thickness_of_the_2d_stock_comes_first(self):
        from vectordrive.core import stock2d
        p, plate, a = self.put(thickness=7.0)
        self.assertEqual(p.blank_thickness(), 7.0)
        s = p.setup()
        s.stock2d = stock2d.to_dict(stock2d.Stock2D(kind='plaque', thickness=10.0))
        p.save(s)
        self.assertEqual(p.blank_thickness(), 10.0)
        p.fixture_holes(exec_dialog=False, spec=FX.Spec(), plate_layer=plate, blanks=[a])
        self.assertEqual(p.setup().operations[-1].depth, 6.0)

    def test_from_m6_helical_drilling_then_the_thread(self):
        from vectordrive.cam import model
        p, plate, a = self.put(screw=6.4, table=9.0, thickness=10.0)
        s = p.setup()
        s.tools.append(model.CamTool(name='Foret 5', kind='foret', diameter=5.0))   # un foret conviendrait : pas pris
        p.save(s)
        before = len(p.setup().operations)
        pl = p.fixture_holes(exec_dialog=False, spec=FX.Spec(max_diameter=9.5), plate_layer=plate, blanks=[a])
        self.assertEqual(pl.thread, 'M6')
        ops = p.setup().operations[before:]
        self.assertEqual([o.kind for o in ops], ['percage_fraise', 'taraudage'])
        self.assertEqual((ops[0].name, ops[1].name), ('Perçage à la fraise M6 des bruts', 'Taraudage M6 des bruts'))
        self.assertEqual((ops[0].hole_diameter, ops[0].depth), (5.0, 6.5))   # plus bas, sans entrer dans la face usinée
        self.assertEqual((ops[1].thread, ops[1].depth), ('M6', 6.0))         # plaque de 10 mm : 6 mm
        self.assertEqual(sorted(ops[0].items), sorted(ops[1].items))

    def test_the_dialog_shows_what_will_be_made(self):
        from vectordrive.ui.fixture_dialog import FixtureDialog
        doc, plate, blanks, a = drawing()
        doc.plate = Plate()
        doc.plate.thickness = 7.0
        dlg = FixtureDialog(None, doc, FX.Spec(per_blank=0, depth=5.0), selection=[a])
        self.addCleanup(dlg.deleteLater)
        self.assertTrue(dlg.common.isChecked())
        self.assertEqual(dlg.placement.count(), 9)
        self.assertIn('M4', dlg.info.text())
        self.assertIn('une seule opération', dlg.info.text())
        self.assertFalse(dlg.extra.isEnabled())                              # pas de perçage à part sous M6
        self.assertEqual((dlg.depth.value(), dlg.depth.isEnabled()), (3.5, False))   # d'après les 7 mm
        self.assertEqual(dlg.spec().depth, 5.0)                              # la profondeur réglée reste retenue
        dlg.machined.setValue(6.0)                                           # il ne resterait que 0,5 mm
        self.assertTrue(dlg.too_thin)
        self.assertIn('trop mince', dlg.info.text())
        self.assertFalse(dlg.ok.isEnabled())
        dlg.machined.setValue(2.0)
        self.assertEqual(dlg.depth.value(), 4.5)
        self.assertTrue(dlg.ok.isEnabled())
        dlg.auto_depth.setChecked(False)
        self.assertEqual((dlg.depth.value(), dlg.depth.isEnabled()), (5.0, True))
        dlg.depth.setValue(4.2)                                              # réglée à la main, puis la case recochée
        dlg.auto_depth.setChecked(True)
        self.assertEqual((dlg.depth.value(), dlg.spec().depth), (4.5, 4.2))
        dlg.auto_depth.setChecked(False)
        self.assertEqual(dlg.depth.value(), 4.2)                             # jamais perdue
        dlg.common.setChecked(False)                                         # tous les trous : celui de la table aussi
        self.assertEqual(dlg.placement.count(), 10)
        s = dlg.spec()
        self.assertEqual((s.common_only, s.auto_depth, s.machined), (False, False, 2.0))
        dlg.thread.setCurrentIndex(dlg.thread.findData('M6'))
        self.assertIn('puis taraudage', dlg.info.text())
        self.assertTrue(dlg.extra.isEnabled())
        unknown = FixtureDialog(None, doc, FX.Spec(depth=5.0), selection=[a], thickness=0.0)   # épaisseur inconnue
        self.addCleanup(unknown.deleteLater)
        self.assertEqual((unknown.depth.value(), unknown.depth.isEnabled(), unknown.too_thin), (5.0, True, False))
        self.assertFalse(unknown.machined.isEnabled())
        given = FixtureDialog(None, doc, FX.Spec(), selection=[a], thickness=10.0)   # celle du réglage FAO d'abord
        self.addCleanup(given.deleteLater)
        self.assertEqual(given.depth.value(), 6.0)
        few = Shape(path=geom.Path([geom.rect(30.5, 5.5, 14.0, 14.0)]), tool=1)   # sur le seul trou de la table
        none = FixtureDialog(None, doc, FX.Spec(), selection=[few])
        self.addCleanup(none.deleteLater)
        self.assertEqual(none.placement.count(), 0)
        self.assertIn('décochez', none.info.text())                          # la case qui les écarte est dite


if __name__ == '__main__':
    unittest.main()
