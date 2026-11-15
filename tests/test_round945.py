"""Round 945 : poche, seulement le reste — la passe de finition ne prend plus au fond d'un coup de la matière jamais
ouverte plus épaisse que ce qu'un coin droit garde : rainure derrière une cloison mince, col court, passage entre
une île et le bord. Une surépaisseur seule reste finie au fond."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r945.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

import shapely  # noqa: E402

from vectordrive.cam import model, strategies  # noqa: E402
from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Document, Shape  # noqa: E402

DEPTH = 3.0


def doc_of(*contours):
    d = Document()
    d.layers[0].items.append(Shape(path=geom.Path(list(contours))))
    return d


def poly(pts):
    return geom.polyline([(float(x), float(y)) for x, y in pts], closed=True)


def plan(d_small, stock, stock_a=0.0, d_big=4.0):
    big = model.CamTool(name='ébauche', diameter=d_big, step_down=0.5)
    small = model.CamTool(name='finition', diameter=d_small, step_down=0.5)
    s = model.CamSetup(tools=[big, small])
    a = model.Operation(name='ébauche', kind='poche', tool_id=big.id, depth=DEPTH, stock=stock_a)
    b = model.Operation(name='finition', kind='poche', tool_id=small.id, depth=DEPTH, rest_previous=True,
                        stock=stock, finish=True)
    s.operations = [a, b]
    return s, a, b


def feeds(tp):
    """Avances dans la matière : [(z haut, z bas, segment)]."""
    out, prev = [], None
    for m in tp.moves:
        if prev is not None and m.kind != 'rapid' and min(prev.z, m.z) < -1e-6 and \
                math.dist((prev.x, prev.y), (m.x, m.y)) > 1e-9:
            out.append((max(prev.z, m.z), min(prev.z, m.z), shapely.LineString([(prev.x, prev.y), (m.x, m.y)])))
        prev = m
    return out


def levels_in(tp, zone):
    return sorted({round(lo, 3) for _hi, lo, seg in feeds(tp) if seg.intersects(zone)})


def inscribed(g):
    """Diamètre du plus grand disque inscrit dans g (bissection sur le retrait)."""
    lo, hi = 0.0, 10.0
    for _k in range(16):
        mid = (lo + hi) / 2
        if g.buffer(-mid / 2, quad_segs=8).is_empty:
            hi = mid
        else:
            lo = mid
    return lo


def taken_at_once(tp, d, s, a, b, zone):
    """Épaisseur (disque inscrit, mm) du plus gros morceau de matière que personne n'a ouverte aux cotes du dessus
    et que les avances au fond enlèvent d'un coup, dans `zone`."""
    tool = s.tool(b.tool_id)
    r = strategies.cut_radius(b, tool)
    zb = strategies.op_levels(b, tool)[-1]
    geoms = [g for it in strategies.source_items(d, b) if (g := strategies.item_geometry(it))]
    reg = strategies.region(geoms, s.tolerance)
    opened = [strategies.cleared_by(d, a, s.tool(a.tool_id), s.tolerance)]
    opened += [seg.buffer(r, quad_segs=16) for hi, _lo, seg in feeds(tp) if hi > zb + 1e-6]
    opened = shapely.union_all([g for g in opened if g is not None])
    bottom = [seg.buffer(r, quad_segs=16) for hi, lo, seg in feeds(tp) if abs(hi - zb) < 1e-6 and abs(lo - zb) < 1e-6]
    if not bottom:
        return 0.0
    solid = shapely.union_all(bottom).intersection(reg).difference(opened).intersection(zone)
    solid = solid.buffer(-0.01).buffer(0.01)
    return max((inscribed(p) for p in shapely.get_parts(solid) if p.area > 0.01), default=0.0)


def corner(r, stock):
    """Ce qu'un coin droit garde (disque inscrit) : la référence de ce qu'une finition prend au fond d'un coup."""
    return 0.343 * r + 1.172 * stock + 0.05


class Finish(unittest.TestCase):

    def test_slot_behind_a_thin_wall_is_cut_level_by_level(self):
        # rainure de 1,1 jamais ouverte, à 0,2 mm de deux poches ébauchées : la cloison ne la rend pas « ouverte »
        w, t = 1.1, 0.2
        y1 = 10 + t
        d = doc_of(geom.rect(0, 0, 20, 10), geom.rect(2, y1, 16, w), geom.rect(0, y1 + w + t, 20, 10))
        s, a, b = plan(1.0, 0.5)
        tp = strategies.compute(d, s, b)
        slot = shapely.box(2, y1, 18, y1 + w)
        self.assertEqual(len(levels_in(tp, slot)), 6)                       # avant : au fond seulement
        self.assertLess(taken_at_once(tp, d, s, a, b, slot), corner(0.5, 0.5))        # avant : 1,10 mm, tout l'outil
        self.assertTrue(any('toutes les cotes' in x for x in tp.warnings))
        # ébauche à la même surépaisseur : le long d'un bord droit des poches, la surépaisseur seule — au fond seulement
        s, a, b = plan(1.0, 0.5, stock_a=0.5)
        tp = strategies.compute(d, s, b)
        self.assertEqual(levels_in(tp, shapely.box(8, 0.2, 12, 0.8)), [-DEPTH])
        self.assertEqual(len(levels_in(tp, slot)), 6)

    def test_short_neck_is_cut_level_by_level(self):
        # col de 1,1 x 1,0 entre deux poches (fraise de 1, surépaisseur 0,3) ; puis 2,06 x 2,0 (fraise de 2, 0,05)
        for d_small, stock, w, ln in ((1.0, 0.3, 1.1, 1.0), (2.0, 0.05, 2.06, 2.0)):
            with self.subTest(d=d_small, w=w, ln=ln):
                a0 = 12.0
                d = doc_of(poly([(0, 0), (a0, 0), (a0, a0 / 2 - w / 2), (a0 + ln, a0 / 2 - w / 2), (a0 + ln, 0),
                                 (2 * a0 + ln, 0), (2 * a0 + ln, a0), (a0 + ln, a0), (a0 + ln, a0 / 2 + w / 2),
                                 (a0, a0 / 2 + w / 2), (a0, a0), (0, a0)]))
                s, a, b = plan(d_small, stock)
                tp = strategies.compute(d, s, b)
                zone = shapely.box(a0, a0 / 2 - w / 2, a0 + ln, a0 / 2 + w / 2).buffer(d_small / 2)
                self.assertLess(taken_at_once(tp, d, s, a, b, zone), corner(d_small / 2, stock))
                self.assertGreater(len(levels_in(tp, shapely.box(a0 + ln / 2 - 0.05, a0 / 2 - w / 2, a0 + ln / 2 + 0.05,
                                                                 a0 / 2 + w / 2))), 1)     # avant : le fond seulement

    def test_passage_between_an_island_and_the_wall(self):
        # île de 0,6 à 2,2 du bord d'un cadre ébauché : le passage, où seule la finition entre (fraise de 2)
        w, c = 2.2, 0.6
        d = doc_of(geom.rect(0, 0, 30, 20), geom.rect(12, w, c, c))
        s, a, b = plan(2.0, 0.3, stock_a=0.3)
        tp = strategies.compute(d, s, b)
        zone = shapely.box(12.0 - 1.0, 0.0, 12.0 + c + 1.0, w)
        self.assertLess(taken_at_once(tp, d, s, a, b, zone), corner(1.0, 0.3))       # avant : 0,96 mm d'un coup
        self.assertEqual(levels_in(tp, shapely.box(22, 0.7, 26, 1.3)), [-DEPTH])     # plus loin, le bord : au fond


if __name__ == '__main__':
    unittest.main()
