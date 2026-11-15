"""Round 931 : Poche, seulement le reste (ébauche puis finition de gravure) — les passes de la poche entière, gardées là
seulement où l'outil enlève ce que les poches d'avant ont laissé (coins, surépaisseur XY) ; ce qu'un outil au moins aussi
gros a vidé n'est pas repassé."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r931.ini'))

from vectordrive.cam import model, strategies
from vectordrive.core import geom
from vectordrive.core.document import Document, Shape

W, H = 30.0, 15.0
CORNERS = ((0, 0), (W, 0), (0, H), (W, H))


def rect_doc():
    d = Document()
    d.layers[0].items.append(Shape(path=geom.Path([geom.rect(0, 0, W, H)])))
    return d


def wall_dist(x, y):
    return min(x, y, W - x, H - y)


def cuts(tp):
    return [(m.x, m.y) for m in tp.moves if m.z < -1e-6 and m.kind != 'rapid']


def length(tp):
    out, prev = 0.0, None
    for m in tp.moves:
        if prev is not None and m.kind != 'rapid' and min(prev.z, m.z) < -1e-6:
            out += math.dist((prev.x, prev.y), (m.x, m.y))
        prev = m
    return out


def swept(tp, radius):
    """Ce que le fond de l'outil a balayé à la dernière cote (shapely)."""
    import shapely
    zmin = min(m.z for m in tp.moves)
    lines, prev = [], None
    for m in tp.moves:
        if prev is not None and m.kind != 'rapid' and abs(prev.z - zmin) < 1e-6 and abs(m.z - zmin) < 1e-6:
            lines.append(shapely.LineString([(prev.x, prev.y), (m.x, m.y)]) if
                         math.dist((prev.x, prev.y), (m.x, m.y)) > 1e-9 else shapely.Point(m.x, m.y))
        prev = m
    return shapely.union_all(lines).buffer(radius)


def plan(rough_d=4.0, rough_stock=0.0, rough_finish=False, fin=None, depth=0.5):
    big = model.CamTool(name='ébauche', diameter=rough_d, step_down=1.0)
    small = fin or model.CamTool(name='finition', diameter=1.0, step_down=1.0)
    s = model.CamSetup(tools=[big, small])
    a = model.Operation(name='ébauche', kind='poche', tool_id=big.id, depth=depth, stock=rough_stock,
                        finish=rough_finish)
    b = model.Operation(name='finition', kind='poche', tool_id=small.id, depth=depth, rest_previous=True)
    s.operations = [a, b]
    return s, a, b, small


class RestOnly(unittest.TestCase):

    def test_corners_only_and_all_of_them(self):
        import shapely
        d = rect_doc()
        s, a, b, small = plan()
        tp = strategies.compute(d, s, b)
        pts = cuts(tp)
        self.assertTrue(pts)
        for x, y in pts:                                                     # près d'un coin seulement
            self.assertLess(min(math.dist((x, y), c) for c in CORNERS), 3.5)
        full = strategies.compute(d, s, model.Operation(kind='poche', tool_id=small.id, depth=0.5))
        self.assertLess(length(tp), length(full) / 10)
        reg = shapely.box(0, 0, W, H)
        done = reg.buffer(-2.0).buffer(2.0)                                  # vidé par la fraise de 4
        reach = reg.buffer(-0.5).buffer(0.5)                                 # ce que la fraise de 1 atteint
        rest = reg.difference(done).intersection(reach)
        self.assertGreater(rest.area, 1.0)
        self.assertLess(rest.difference(swept(tp, 0.5)).area, 0.02)          # rien d'oublié
        self.assertTrue(any('mm² laissés' in w for w in tp.warnings))

    def test_stock_xy_of_the_previous_is_counted(self):
        d = rect_doc()
        s, a, b, _small = plan(rough_stock=0.2)
        import shapely
        tp = strategies.compute(d, s, b)
        pts = cuts(tp)
        reg = shapely.box(0, 0, W, H)
        band = reg.difference(reg.buffer(-0.2, join_style='mitre'))          # laissée le long des bords
        band = band.intersection(reg.buffer(-0.5).buffer(0.5))               # (l'angle vif : hors de portée)
        self.assertGreater(band.area, 15)
        self.assertLess(band.difference(swept(tp, 0.5)).area, 0.02)         # passée, tout du long
        for x, y in pts:                                    # pas plus loin que la surépaisseur laissée (et les coins)
            near = min(math.dist((x, y), c) for c in CORNERS) < 3.5
            self.assertTrue(near or wall_dist(x, y) < 0.5 + 0.2 + 0.5, (x, y))
        a.finish = True                                      # une passe de finition l'a enlevée : les coins seuls
        tp = strategies.compute(d, s, b)
        self.assertFalse(any(abs(x - W / 2) < 1 for x, y in cuts(tp)))
        self.assertTrue(cuts(tp))

    def test_nothing_left_or_no_previous(self):
        d = rect_doc()
        s, a, b, _small = plan()
        b.tool_id = a.tool_id                                # le même outil que l'ébauche : rien à nettoyer
        tp = strategies.compute(d, s, b)
        self.assertEqual(cuts(tp), [])
        self.assertTrue(any('seulement le reste' in w for w in tp.warnings))
        s, a, b, small = plan()
        a.enabled = False                                    # aucune poche avant : la poche entière
        tp = strategies.compute(d, s, b)
        full = strategies.compute(d, s, model.Operation(kind='poche', tool_id=small.id, depth=0.5))
        self.assertAlmostEqual(length(tp), length(full), delta=1e-6)
        self.assertTrue(any('aucune poche active avant' in w for w in tp.warnings))

    def test_engraving_rough_then_v_bit(self):
        d = rect_doc()
        v = model.CamTool(name='V', kind='conique', diameter=3.0, angle=60.0, tip=0.1, step_down=1.0)
        s, a, b, _v = plan(rough_d=2.0, fin=v, depth=0.3)
        tp = strategies.compute(d, s, b)
        pts = cuts(tp)
        self.assertTrue(pts)
        full = strategies.compute(d, s, model.Operation(kind='poche', tool_id=v.id, depth=0.3))
        self.assertLess(length(tp), length(full) / 5)
        r = v.radius_at(0.3)
        for x, y in pts:                                     # le bord (flanc) et les coins, rien au milieu
            near = min(math.dist((x, y), c) for c in CORNERS) < 2.5
            self.assertTrue(near or wall_dist(x, y) < r + 0.05, (x, y))

    def test_form_and_file(self):
        from vectordrive.ui import cam_panel
        self.assertIn('rest_previous', cam_panel.KIND_FIELDS['poche'])
        self.assertIn('rest_previous', dict(cam_panel.OP_SECTIONS)['Opération'])
        self.assertIn('Seulement le reste', cam_panel.LABELS['rest_previous'])
        op = model.Operation(kind='poche', rest_previous=True)
        self.assertTrue(model.Operation.from_dict(op.to_dict()).rest_previous)
        self.assertFalse(model.Operation.from_dict({'kind': 'poche'}).rest_previous)

    def test_recomputed_when_the_previous_changes(self):
        d = rect_doc()
        s, a, b, _small = plan()
        strategies.clear_toolpath_cache()
        first = strategies.compute_all(d, s)[1]
        a.stock = 0.2                                        # l'ébauche laisse une surépaisseur : la finition change
        second = strategies.compute_all(d, s)[1]
        self.assertGreater(length(second), length(first) + 10)


if __name__ == '__main__':
    unittest.main()
