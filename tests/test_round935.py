"""Round 935 : Poche, seulement le reste — corrections de relecture du round 931 : recalculée quand une poche d'avant
change (et à l'écriture quand l'ordre change), Z de départ compté, poches d'avant qui ne vident pas tout non comptées,
outil boule (pied des parois), contour au fond (poche entière), finition sans le cadre ni les parois déjà faites."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r935.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])

from vectordrive.cam import model, strategies  # noqa: E402
from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Document, Shape  # noqa: E402

W, H = 30.0, 15.0


def doc_of(*contours):
    d = Document()
    d.layers[0].items.append(Shape(path=geom.Path(list(contours))))
    return d


def rect_doc():
    return doc_of(geom.rect(0, 0, W, H))


def cuts(tp):
    return [(m.x, m.y) for m in tp.moves if m.z < -1e-6 and m.kind != 'rapid']


def length(tp):
    out, prev = 0.0, None
    for m in tp.moves:
        if prev is not None and m.kind != 'rapid' and min(prev.z, m.z) < -1e-6:
            out += math.dist((prev.x, prev.y), (m.x, m.y))
        prev = m
    return out


def plan(big=None, small=None, depth=0.5, **rough):
    big = big or model.CamTool(name='ébauche', diameter=4.0, step_down=1.0)
    small = small or model.CamTool(name='finition', diameter=1.0, step_down=1.0)
    s = model.CamSetup(tools=[big, small])
    a = model.Operation(name='ébauche', kind='poche', tool_id=big.id, depth=depth, **rough)
    b = model.Operation(name='finition', kind='poche', tool_id=small.id, depth=depth, rest_previous=True)
    s.operations = [a, b]
    return s, a, b


def full_length(d, s, b):
    return length(strategies.compute(d, s, model.Operation(kind='poche', tool_id=b.tool_id, depth=b.depth)))


class Strategy(unittest.TestCase):

    def test_z_start_of_the_previous_counts(self):
        d = rect_doc()
        s, a, b = plan(depth=1.5, z_start=1.0)                 # fond de l'ébauche à -0,5
        b.depth = 1.0                                           # fond de la finition à -1 : plus bas
        tp = strategies.compute(d, s, b)
        self.assertTrue(any('aucune poche active avant' in w for w in tp.warnings))
        self.assertAlmostEqual(length(tp), full_length(d, s, b), delta=1e-6)
        a.z_start = 0.0                                         # fond à -1,5 : elle compte
        self.assertLess(length(strategies.compute(d, s, b)), full_length(d, s, b) / 10)

    def test_previous_that_does_not_clear_everything_is_not_counted(self):
        d = rect_doc()
        for rough in ({'pocket_mode': 'balayage', 'sweep_contour': 'sans'},
                      {'pocket_mode': 'balayage', 'sweep_texture': True},
                      {'stepover_mm': 5.0}):                     # passes plus écartées que la fraise de 4
            s, a, b = plan(**rough)
            tp = strategies.compute(d, s, b)
            self.assertTrue(any('non comptée' in w for w in tp.warnings), rough)
            self.assertAlmostEqual(length(tp), full_length(d, s, b), delta=1e-6)
        s, a, b = plan(pocket_mode='balayage', sweep_contour='apres')    # avec le tour du contour : comptée
        tp = strategies.compute(d, s, b)
        self.assertFalse(any('non comptée' in w for w in tp.warnings))
        self.assertLess(length(tp), full_length(d, s, b) / 5)

    def test_ball_previous_leaves_the_wall_foot(self):
        d = rect_doc()
        ball = model.CamTool(name='boule', kind='boule', diameter=4.0, step_down=1.0)
        s, a, b = plan(big=ball)
        done = length(strategies.compute(d, s, b))
        self.assertGreater(done, 2 * 2 * (W + H))                # des tours le long des parois, pas seulement les coins
        self.assertLess(done, full_length(d, s, b) / 2)          # le milieu, vidé par la boule, n'est pas refait

    def test_v_bit_with_contour_at_the_bottom_is_the_whole_pocket(self):
        d = rect_doc()
        v = model.CamTool(name='V', kind='conique', diameter=3.0, angle=60.0, tip=0.1, step_down=1.0)
        s, a, b = plan(big=model.CamTool(name='F2', diameter=2.0, step_down=1.0), small=v, depth=0.3)
        b.contour_ref = 'fond'
        tp = strategies.compute(d, s, b)
        self.assertTrue(any('contour respecté au fond' in w for w in tp.warnings))
        full = strategies.compute(d, s, model.Operation(kind='poche', tool_id=v.id, depth=0.3, contour_ref='fond'))
        self.assertAlmostEqual(length(tp), length(full), delta=1e-6)

    def test_finish_skips_the_frame(self):
        import shapely
        d = doc_of(geom.rect(0, 0, W, H), geom.rect(10, 5, 10, 5))        # cadre et une forme dedans : relief
        s, a, b = plan()
        b.finish, b.stock, b.finish_skip_frame = True, 0.1, True
        outer = shapely.box(0, 0, W, H).exterior
        pts = cuts(strategies.compute(d, s, b))
        self.assertTrue(pts)
        self.assertFalse([p for p in pts if abs(outer.distance(shapely.Point(p)) - 0.5) < 0.02])

    def test_finish_does_not_redo_curved_walls(self):
        import shapely
        arc = [(20 + 10 * math.cos(math.radians(a)), 10 + 10 * math.sin(math.radians(a))) for a in range(-90, 91, 6)]
        d = doc_of(geom.polyline([(0, 20), (0, 0)] + arc, closed=True))   # deux coins vifs, puis un arc
        s, a, b = plan()
        b.finish, b.stock = True, 0.1
        pts = cuts(strategies.compute(d, s, b))
        self.assertTrue(pts)
        self.assertFalse([p for p in pts if math.dist(p, (30, 10)) < 2])  # l'arc, fait par la fraise de 4
        self.assertTrue(any(shapely.Point(p).distance(shapely.Point(0, 0)) < 3 for p in pts))   # les coins, oui


class Panel(unittest.TestCase):

    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.cp = self.w.cam_panel
        sh = Shape(path=geom.Path([geom.rect(0, 0, W, H)]))
        self.w.canvas.doc.active_layer.items.append(sh)
        s = self.cp.setup()
        big = model.CamTool(name='ébauche 935', diameter=4.0, step_down=1.0)
        small = model.CamTool(name='finition 935', diameter=1.0, step_down=1.0)
        s.tools = [big, small]
        s.operations = [model.Operation(name='A', kind='poche', tool_id=big.id, items=[sh.id], depth=0.5),
                        model.Operation(name='B', kind='poche', tool_id=small.id, items=[sh.id], depth=0.5,
                                        rest_previous=True),
                        model.Operation(name='C', kind='contour', tool_id=small.id, items=[sh.id], depth=0.5)]
        self.cp.save(s)

    def tearDown(self):
        self.w.modified = False
        self.w.close()

    def test_the_rest_digest_follows_the_previous_operations(self):
        s = self.cp.setup()
        a, b, c = s.operations
        before = self.cp._inputs_state()[2]
        a.stock = 0.2
        self.cp.save(s)
        after = self.cp._inputs_state()[2]
        self.assertNotEqual(before[b.id], after[b.id])                     # A retouchée : B à refaire
        self.assertEqual(before[c.id], after[c.id])                        # C ne dépend pas de A
        s = self.cp.setup()
        s.operations = [s.operations[1], s.operations[0], s.operations[2]]   # B avant A : à refaire aussi
        self.cp.save(s)
        self.assertNotEqual(self.cp._inputs_state()[2][b.id], after[b.id])

    def test_validating_the_previous_recomputes_the_rest(self):
        s = self.cp.setup()
        for op in s.operations:
            self.cp.compute_op(op)
        b_id = s.operations[1].id
        first = length(next(t for t in self.cp.toolpaths if t.op_id == b_id))
        s = self.cp.setup()
        s.operations[0].stock = 0.2                                         # l'ébauche laisse 0,2 le long des bords
        self.cp.save(s)
        self.cp.compute_op(s.operations[0])
        second = length(next(t for t in self.cp.toolpaths if t.op_id == b_id))
        self.assertGreater(second, first + 10)
        self.assertTrue(self.cp.inputs_current())                           # rien d'autre à refaire


if __name__ == '__main__':
    unittest.main()
