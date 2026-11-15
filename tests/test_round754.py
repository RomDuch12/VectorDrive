"""Round 754 : toute remontée verticale vers le dégagement en rapide ; après un surfaçage, dégagement bas sur la zone
surfacée et l'autre dégagement pour traverser ce qui n'est pas surfacé, tous deux réglables."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.cam import strategies as S
from vectordrive.cam.model import CamSetup, CamTool, Move, Operation
from vectordrive.core import geom
from vectordrive.core.document import Document, Layer, Plate, Shape

app = QApplication.instance() or QApplication([])


def square(x, y, w=5.0, tool=0):
    return Shape(path=geom.Path([geom.rect(x, y, w, w)]), tool=tool)


def mv(*specs):
    return [Move(k, x, y, z) for k, x, y, z in specs]


class TestRapidRetracts(unittest.TestCase):
    def test_chain_to_safe(self):
        m = mv(('plunge', 0, 0, -1), ('feed', 0, 0, 0.5), ('rapid', 0, 0, 2))
        self.assertEqual(S.rapid_retracts(m, 2.0), 1)
        self.assertEqual([x.kind for x in m], ['plunge', 'rapid', 'rapid'])

    def test_feed_to_safe(self):
        m = mv(('rapid', 0, 0, 2), ('plunge', 0, 0, -1), ('feed', 5, 0, -1), ('feed', 5, 0, 3))
        self.assertEqual(S.rapid_retracts(m, 2.0), 1)
        self.assertEqual(m[-1].kind, 'rapid')

    def test_plunge_kind_going_up(self):
        m = mv(('rapid', 0, 0, 2), ('plunge', 0, 0, -1), ('plunge', 0, 0, 2))
        S.rapid_retracts(m, 2.0)
        self.assertEqual(m[-1].kind, 'rapid')

    def test_partial_rise_stays(self):
        m = mv(('rapid', 0, 0, 2), ('plunge', 0, 0, -1), ('feed', 0, 0, -0.5), ('feed', 5, 0, -0.5))
        self.assertEqual(S.rapid_retracts(m, 2.0), 0)
        self.assertEqual(m[2].kind, 'feed')

    def test_slanted_exit_stays(self):
        m = mv(('rapid', 0, 0, 2), ('plunge', 0, 0, -1), ('feed', 1, 0, 3))
        self.assertEqual(S.rapid_retracts(m, 2.0), 0)

    def test_descent_untouched(self):
        m = mv(('rapid', 0, 0, 2), ('rapid', 0, 0, 0.5), ('plunge', 0, 0, -1))
        self.assertEqual(S.rapid_retracts(m, 2.0), 0)
        self.assertEqual(m[-1].kind, 'plunge')

    def test_every_strategy_rises_in_rapid(self):
        doc = Document()
        doc.plate = Plate(100, 100)
        doc.layers = [Layer(name='A', items=[square(10, 10, 20), Shape(path=geom.Path([geom.circle((60, 60), 8)]))])]
        endmill = CamTool(id='f', name='F', kind='fraise', diameter=2.0)
        vbit = CamTool(id='c', name='C', kind='conique', diameter=6.0, angle=30.0, tip=0.6)
        drill = CamTool(id='d', name='D', kind='foret', diameter=2.0)
        setup = CamSetup(tools=[endmill, vbit, drill])
        for kind, tool in (('contour', 'f'), ('poche', 'f'), ('gravure', 'f'), ('surfacage', 'f'), ('percage', 'd'),
                           ('vcarve', 'c'), ('percage_fraise', 'f'), ('chanfrein', 'c'), ('chanfrein_bord', 'c')):
            op = Operation(name=kind, kind=kind, tool_id=tool, depth=1.0, hole_diameter=5.0)
            tp = S.compute(doc, setup, op)
            self.assertTrue(tp.moves or tp.warnings, kind)
            prev = None
            for m in tp.moves:
                if prev is not None and m.kind != 'rapid' and not m.is_arc and m.x == prev.x and m.y == prev.y \
                        and m.z >= op.safe_z - 1e-9 and m.z > prev.z:
                    self.fail(f'{kind} : remontée au dégagement en {m.kind}')
                prev = m

    def test_feed_retract_option_kept(self):
        doc = Document()
        doc.layers = [Layer(name='A', items=[Shape(path=geom.Path([geom.circle((10, 10), 2)]))])]
        setup = CamSetup(tools=[CamTool(id='d', name='D', kind='foret', diameter=4.0)])
        op = Operation(name='alésage', kind='percage', tool_id='d', depth=3.0, drill_feed_retract=True)
        tp = S.compute(doc, setup, op)
        ups = [m for p, m in zip(tp.moves, tp.moves[1:]) if m.z > p.z and m.x == p.x and m.y == p.y]
        self.assertTrue(any(m.kind != 'rapid' for m in ups))


class TestFaced(unittest.TestCase):
    """Plaque 100 × 100, surfaçage de la zone 0-60 en X par objet, gravures dedans et dehors."""

    def setUp(self):
        self.face_item = square(0, 0, 60)
        self.face_item.tool = 5
        self.a, self.b, self.c = square(10, 10), square(40, 40), square(85, 85)
        doc = Document()
        doc.plate = Plate(100, 100)
        doc.layers = [Layer(name='A', items=[self.face_item, self.a, self.b, self.c])]
        self.doc = doc
        self.setup = CamSetup(tools=[CamTool(id='s', name='S', kind='fraise', diameter=10.0),
                                     CamTool(id='g', name='G', kind='fraise', diameter=2.0)])
        self.face = Operation(name='surf', kind='surfacage', tool_id='s', depth=0.3, items=[self.face_item.id])

    def laterals(self, tp):
        out = []
        prev = None
        for m in tp.moves:
            if prev is not None and m.kind == 'rapid' and (abs(m.x - prev.x) > 1e-9 or abs(m.y - prev.y) > 1e-9):
                out.append((round(prev.x, 3), round(prev.y, 3), round(m.x, 3), round(m.y, 3), m.z))
            prev = m
        return out

    def engrave(self, items, **k):
        return Operation(name='g', kind='gravure', tool_id='g', depth=0.2, items=[i.id for i in items], **k)

    def test_inside_low_outside_high(self):
        self.setup.operations = [self.face, self.engrave([self.a, self.b, self.c], safe_z=3.0, safe_z_faced=0.2)]
        _f, tp = S.compute_all(self.doc, self.setup)
        lat = self.laterals(tp)
        self.assertEqual((tp.moves[0].kind, tp.moves[0].z), ('rapid', 3.0))    # l'arrivée dans le parcours : haute
        heights = [z for *_p, z in lat]
        self.assertIn(0.2, heights)                                            # a → b : dans la zone
        self.assertIn(3.0, heights)                                            # vers c : hors de la zone
        for x0, y0, x1, y1, z in lat:
            if z == 0.2:
                self.assertLess(max(x0, x1), 60)
            if max(x0, x1) > 60:
                self.assertEqual(z, 3.0)
        self.assertTrue(any('zone surfacée' in w for w in tp.warnings))

    def test_no_move_below_low_between_shapes(self):
        self.setup.operations = [self.face, self.engrave([self.a, self.b])]
        _f, tp = S.compute_all(self.doc, self.setup)
        self.assertTrue(all(m.z >= 0.2 - 1e-9 for m in tp.moves if m.kind == 'rapid'))
        self.assertEqual(tp.moves[-1].z, 2.0)                                  # sortie du parcours au dégagement

    def test_approach_above_low_not_climbed(self):
        self.setup.operations = [self.face, self.engrave([self.a, self.b], clear_z=0.5, safe_z_faced=0.2)]
        _f, tp = S.compute_all(self.doc, self.setup)
        lat = [x for x in self.laterals(tp) if x[4] == 0.2]
        self.assertTrue(lat)
        i = next(k for k, m in enumerate(tp.moves) if m.kind == 'rapid' and m.z == 0.2
                 and abs(m.x - lat[0][2]) < 1e-3 and abs(m.y - lat[0][3]) < 1e-3)
        self.assertEqual(tp.moves[i + 1].kind, 'plunge')                       # on plonge de là : pas de remontée à 0,5

    def test_settable_and_off(self):
        self.setup.operations = [self.face, self.engrave([self.a, self.b], safe_z_faced=0.7, safe_z=5.0)]
        _f, tp = S.compute_all(self.doc, self.setup)
        self.assertIn(0.7, [x[4] for x in self.laterals(tp)])
        self.setup.operations = [self.face, self.engrave([self.a, self.b], safe_z_faced=0.0, safe_z=5.0)]
        _f, tp = S.compute_all(self.doc, self.setup)
        self.assertEqual({x[4] for x in self.laterals(tp)}, {5.0})

    def test_without_facing_nothing_changes(self):
        self.setup.operations = [self.engrave([self.a, self.b], safe_z=4.0)]
        tp, = S.compute_all(self.doc, self.setup)
        self.assertEqual({x[4] for x in self.laterals(tp)}, {4.0})
        self.assertIsNone(tp.unfaced)

    def test_facing_after_does_not_count(self):
        self.setup.operations = [self.engrave([self.a, self.b], safe_z=4.0), self.face]
        tp, _f = S.compute_all(self.doc, self.setup)
        self.assertEqual({x[4] for x in self.laterals(tp)}, {4.0})

    def test_tool_must_fit_inside_zone(self):
        # zone jusqu'à X = 65 : à 64,5 un outil de Ø 2 déborderait de la zone, il reste haut
        near = square(64.5, 10, 5)
        far = square(64.5, 40, 5)
        self.doc.layers[0].items += [near, far]
        self.setup.operations = [Operation(name='s', kind='surfacage', tool_id='s', depth=0.3, items=[self.face_item.id],
                                           extension=-5.0), self.engrave([near, far], safe_z=4.0)]
        _f, tp = S.compute_all(self.doc, self.setup)
        self.assertEqual({x[4] for x in self.laterals(tp)}, {4.0})

    def test_redo_after_facing_changed(self):
        self.setup.operations = [self.face, self.engrave([self.a, self.b], safe_z=4.0)]
        tps = S.compute_all(self.doc, self.setup)
        self.assertIn(0.2, [x[4] for x in self.laterals(tps[1])])
        small = square(0, 0, 25)
        self.doc.layers[0].items.append(small)
        self.face.items = [small.id]
        tps[0] = S.compute(self.doc, self.setup, self.face)                    # le surfaçage refait seul, plus petit
        S.apply_faced_all(self.setup, tps)
        self.assertEqual({x[4] for x in self.laterals(tps[1])}, {4.0})         # plus de liaison basse hors de la zone
        self.assertIsNone(tps[1].unfaced)

    def test_cached_result_not_doubled(self):
        self.setup.operations = [self.face, self.engrave([self.a, self.b])]
        first = S.compute_all(self.doc, self.setup)[1]
        again = S.compute_all(self.doc, self.setup)[1]
        self.assertEqual([(m.kind, m.x, m.y, m.z) for m in first.moves], [(m.kind, m.x, m.y, m.z) for m in again.moves])
        self.assertEqual(sum('zone surfacée' in w for w in again.warnings), 1)

    def test_simulation_finds_no_rapid_hit(self):
        from vectordrive.cam import simulate as SIM
        self.setup.operations = [self.face, self.engrave([self.a, self.b], safe_z_faced=0.2)]
        tps = S.compute_all(self.doc, self.setup)
        res = SIM.simulate(tps, self.setup, res=0.2, stock=None)
        self.assertFalse(getattr(res, 'rapid_hits', []))

    def test_default_values(self):
        self.assertEqual(Operation(name='x').safe_z_faced, 0.2)
        from vectordrive.ui.options import value
        from PySide6.QtCore import QSettings
        s = QSettings(os.environ['VECTORDRIVE_SETTINGS'], QSettings.Format.IniFormat)
        self.assertEqual(float(value(s, 'fao/z_surface')), 0.2)


class TestPdfTexts(unittest.TestCase):
    def test_text_in_a_page(self):
        from vectordrive.core.document import Text
        from vectordrive.io import pdf
        t = Text(text='x')
        items = [t, Shape(path=geom.Path([geom.rect(0, 0, 5, 5)]), filled=True)]
        self.assertEqual(pdf._knock_out(items, []), [])
        self.assertEqual(len(items), 2)


if __name__ == '__main__':
    unittest.main()
