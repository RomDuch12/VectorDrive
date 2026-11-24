"""Round 1146 (demande du 23/11) : « tous parcours gravure : rétablir possibilité de limiter les passes d'évidement en
XY autour des logos » — le nombre de passes limité de la gravure 2,5D aussi dans la poche."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1146.ini'))

from shapely.geometry import LineString, Point, box  # noqa: E402

from vectordrive.cam import model as M, strategies as S  # noqa: E402
from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Document, Shape  # noqa: E402

BEFORE = 'avant : la poche vidait tout le cadre, sans nombre de passes limité'
LOGO = box(40, 20, 60, 40)                       # le logo au milieu du cadre de 100 × 60
FRAME = box(0, 0, 100, 60)


def run(**kw):
    d = Document()
    d.plate = None
    d.add(Shape(path=geom.Path([geom.rect(0, 0, 100, 60)]), tool=1))
    d.add(Shape(path=geom.Path([geom.rect(40, 20, 20, 20)]), tool=1))
    setup = M.setup_of(d)
    t = M.CamTool(name='F2', kind='fraise', diameter=2.0)
    setup.tools = [t]
    op = dict(kind='poche', depth=0.5, tool_id=t.id, stepover_mm=1.0)
    op.update(kw)
    return S.compute(d, setup, M.Operation(**op))


def cuts(tp):
    """Les traits en avance, à plat (x, y)."""
    out, prev = [], None
    for m in tp.moves:
        if prev is not None and m.kind != 'rapid' and (m.x, m.y) != prev:
            out.append(LineString([prev, (m.x, m.y)]))
        prev = (m.x, m.y)
    return out


def far(tp, shape):
    """La plus grande distance d'un point de coupe au bord de `shape`."""
    return max(shape.boundary.distance(Point(c)) for seg in cuts(tp) for c in seg.coords)


def laps_above(tp):
    """Les tours au-dessus du logo : les y des traits qui coupent la verticale x = 50 entre le logo et le cadre."""
    v = LineString([(50, 40.001), (50, 59.999)])
    ys = set()
    for s in cuts(tp):
        x = s.intersection(v)
        for p in getattr(x, 'geoms', [x]):
            if not p.is_empty and p.geom_type == 'Point':
                ys.add(round(p.y - 40, 2))
    return sorted(ys)


class Pocket(unittest.TestCase):
    def test_limited_around_the_logo(self):
        full = run(finish_skip_frame=True)
        lim = run(finish_skip_frame=True, vcarve_max_steps=3)
        self.assertGreater(far(full, LOGO), 15.0)                         # tout le cadre vidé
        self.assertLess(far(lim, LOGO), 1.0 + 3 * 1.0 + 0.05, BEFORE)      # rayon + 3 pas (n impair : un tour de plus)
        self.assertTrue(any('nombre de passes limité' in w for w in lim.warnings))
        self.assertLess(len(lim.moves), len(full.moves))
        self.assertTrue(all(FRAME.boundary.distance(Point(c)) > 15.0 for s in cuts(lim) for c in s.coords))
        self.assertIsNone(S._FRAME_SRC.get())                               # rien ne reste pour l'opération suivante

    def test_laps(self):
        self.assertEqual(laps_above(run(finish_skip_frame=True, vcarve_max_steps=2)), [1.0, 2.0])
        self.assertEqual(laps_above(run(finish_skip_frame=True, vcarve_max_steps=4)), [1.0, 2.0, 3.0, 4.0])
        self.assertEqual(laps_above(run(finish_skip_frame=True, vcarve_max_steps=1)), [1.0, 2.0])   # pair : 2 tours

    def test_nothing_left_in_the_band(self):
        from shapely.ops import unary_union
        for n, wide in ((3, 1.0), (2, 1.8)):                               # pas plus large que le rayon aussi
            lim = run(finish_skip_frame=True, vcarve_max_steps=n, stepover_mm=wide)
            cut = unary_union([s.buffer(1.0, quad_segs=16) for s in cuts(lim)])
            band = LOGO.buffer(1.0 + (n - 1) * wide, quad_segs=32).difference(LOGO)   # à moins de D du logo
            self.assertLess(band.difference(cut.buffer(0.02)).area, 0.05, n)

    def test_counted_from_the_frame_too_when_it_is_cut(self):
        lim = run(vcarve_max_steps=2)                                       # le cadre repassé : un bord aussi
        pts = [Point(c) for s in cuts(lim) for c in s.coords]
        self.assertTrue(any(FRAME.boundary.distance(p) < 2.0 for p in pts))
        near = [min(FRAME.boundary.distance(p), LOGO.boundary.distance(p)) for p in pts]
        self.assertLess(max(near), 2 * 1.0 + 1.0)                           # dans la bande (arcs aux coins du cadre)
        mid = [p for p, d in zip(pts, near) if d > 2.05]                    # au-delà de 2 tours : les coins du cadre
        self.assertTrue(all(min(p.x, 100 - p.x) < 4 and min(p.y, 60 - p.y) < 4 for p in mid))

    def test_sweep_limited_too(self):
        full = run(pocket_mode='balayage', finish_skip_frame=True)
        lim = run(pocket_mode='balayage', finish_skip_frame=True, vcarve_max_steps=2)
        self.assertGreater(far(full, LOGO), 15.0)
        self.assertLess(far(lim, LOGO), 1.0 + 1.0 + 0.05, BEFORE)

    def test_spiral_limited_too(self):
        lim = run(pocket_spiral=True, finish_skip_frame=True, vcarve_max_steps=3)
        self.assertLess(far(lim, LOGO), 1.0 + 3.0 + 0.05, BEFORE)

    def test_zero_changes_nothing(self):
        a = run(finish_skip_frame=True)
        b = run(finish_skip_frame=True, vcarve_max_steps=0)
        self.assertEqual([(m.kind, m.x, m.y, m.z) for m in a.moves], [(m.kind, m.x, m.y, m.z) for m in b.moves])

    def test_finish_keeps_the_real_wall(self):
        d = Document()                                                      # une poche sans cadre, « pas de passe
        d.plate = None                                                      # sur le cadre » cochée (gamme, modèle)
        d.add(Shape(path=geom.Path([geom.rect(0, 0, 30, 30)]), tool=1))
        setup = M.setup_of(d)
        t = M.CamTool(name='F2', kind='fraise', diameter=2.0)
        setup.tools = [t]
        tp = S.compute(d, setup, M.Operation(kind='poche', depth=0.5, tool_id=t.id, stepover_mm=1.0, finish=True,
                                             stock=0.2, finish_skip_frame=True, vcarve_max_steps=2))
        wall = box(0, 0, 30, 30).boundary
        self.assertAlmostEqual(min(wall.distance(Point(c)) for s in cuts(tp) for c in s.coords), 1.0, 2)
        self.assertEqual(tp.cycles, [])                                     # pas de cycle de poche entière

    def test_rest_after_a_limited_pocket(self):
        d = Document()
        d.plate = None
        d.add(Shape(path=geom.Path([geom.rect(0, 0, 100, 60)]), tool=1))
        d.add(Shape(path=geom.Path([geom.rect(40, 20, 20, 20)]), tool=1))
        setup = M.setup_of(d)
        t = M.CamTool(name='F2', kind='fraise', diameter=2.0)
        setup.tools = [t]
        a = M.Operation(kind='poche', depth=0.5, tool_id=t.id, stepover_mm=1.0, finish_skip_frame=True,
                        vcarve_max_steps=2)
        b = M.Operation(kind='poche', depth=0.5, tool_id=t.id, stepover_mm=1.0, rest_previous=True)
        setup.operations = [a, b]
        tp = S.compute(d, setup, b)                                         # le milieu reste à vider : la reprise le fait
        self.assertGreater(far(tp, LOGO), 10.0)

    def test_band_helper(self):
        op = M.Operation(kind='poche', vcarve_max_steps=2, finish_skip_frame=True)
        reg = FRAME.difference(LOGO)
        band = S.limit_band(op, reg, 1.0, 1.0, 8, record=False)
        self.assertAlmostEqual(band.bounds[0], 40 - 3.0, 2)                # 2 × 1 + 1 pas
        op.vcarve_max_steps = 0
        self.assertIs(S.limit_band(op, reg, 1.0, 1.0, 8), reg)
        plain = box(0, 0, 10, 10)                                           # sans cadre : depuis son bord
        op.vcarve_max_steps = 1
        b = S.limit_band(op, plain, 1.0, 1.0, 8, record=False)
        self.assertTrue(b.contains(Point(1, 1)) and not b.contains(Point(5, 5)))
        op.vcarve_max_steps = 50                                            # tout couvert : la région telle quelle
        self.assertIs(S.limit_band(op, plain, 1.0, 1.0, 8, record=False), plain)



class Form(unittest.TestCase):
    def test_field_in_the_pocket_form(self):
        from vectordrive.ui import cam_panel as CP
        self.assertIn('vcarve_max_steps', CP.KIND_FIELDS['poche'], BEFORE)
        self.assertIn('vcarve_max_steps', CP.KIND_FIELDS['vcarve'])
        self.assertIn('logos', CP.LABELS['vcarve_max_steps'])


if __name__ == '__main__':
    unittest.main()
