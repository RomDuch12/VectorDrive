"""Round 939 : Poche, seulement le reste — la passe de finition le long de matière jamais ouverte se fait à toutes les
cotes quelle que soit la surépaisseur ; le tronçon seulement pour un tour fermé ; dernière cote dans le sens demandé ;
outil conique : au fond seulement."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r939.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from vectordrive.cam import model, strategies  # noqa: E402
from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Document, Shape  # noqa: E402


def doc_of(*contours):
    d = Document()
    d.layers[0].items.append(Shape(path=geom.Path(list(contours))))
    return d


def plan(big_d, small_d, depth, step, rough_stock=0.0, stock=0.2, small=None):
    big = model.CamTool(name='ébauche', diameter=big_d, step_down=step)
    small = small or model.CamTool(name='finition', diameter=small_d, step_down=step)
    s = model.CamSetup(tools=[big, small])
    a = model.Operation(name='ébauche', kind='poche', tool_id=big.id, depth=depth, stock=rough_stock)
    b = model.Operation(name='finition', kind='poche', tool_id=small.id, depth=depth, rest_previous=True,
                        stock=stock, finish=True)
    s.operations = [a, b]
    return s, a, b


def cut_steps(tp):
    out, prev = [], None
    for m in tp.moves:
        if prev is not None and m.kind != 'rapid' and min(prev.z, m.z) < -1e-6:
            out.append((prev, m))
        prev = m
    return out


def levels_cut(tp):
    return sorted({round(m.z, 3) for p, m in cut_steps(tp) if math.dist((p.x, p.y), (m.x, m.y)) > 1e-9})


def deepest_plunge(tp):
    """Plus grande descente d'un coup sous la surface."""
    return max(max(0.0, -m.z) - max(0.0, -p.z) for p, m in zip(tp.moves, tp.moves[1:]) if m.kind == 'plunge')


def length_at(tp, z):
    return sum(math.dist((p.x, p.y), (m.x, m.y)) for p, m in cut_steps(tp)
               if abs(m.z - z) < 1e-6 and abs(p.z - z) < 1e-6)


class Finish(unittest.TestCase):

    def test_a_thick_stock_in_a_narrow_slot_still_goes_level_by_level(self):
        for shape, stock in ((geom.rect(0, 0, 20.0, 1.06), 0.3),            # la fraise de 1 n'y entre qu'à la finition
                             (geom.rect(0, 0, 20.0, 1.3), 0.5),
                             (geom.circle((0.0, 0.0), 0.56), 0.3)):
            s, a, b = plan(4.0, 1.0, 3.0, 0.5, stock=stock)
            tp = strategies.compute(doc_of(shape), s, b)
            self.assertEqual(levels_cut(tp), [-3.0, -2.5, -2.0, -1.5, -1.0, -0.5], stock)   # avant : −3 seulement
            self.assertLessEqual(deepest_plunge(tp), 0.5 + 1e-9, stock)                     # avant : 3 mm d'un coup
            self.assertTrue(any('à toutes les cotes' in w for w in tp.warnings))

    def test_a_sharp_corner_no_longer_sends_the_whole_ring_to_every_level(self):
        tri = geom.polyline([(0, 0), (60, 0), (0, 34.64)], closed=True)      # 90°, 30° et 60°
        s, a, b = plan(4.0, 4.0, 1.5, 0.5, rough_stock=0.2)
        b.tool_id = a.tool_id                                               # la même fraise : la finition seule
        tp = strategies.compute(doc_of(tri), s, b)
        bottom, upper = length_at(tp, -1.5), length_at(tp, -0.5)
        self.assertGreater(bottom, 60.0)                                    # le tour entier, au fond
        self.assertLess(upper, bottom / 3)                                  # avant : le tour entier à chaque cote
        s, a, b = plan(4.0, 1.0, 1.5, 0.5, rough_stock=0.2)                 # une fraise fine : la pointe à 30° seule
        tp = strategies.compute(doc_of(tri), s, b)                          # est jamais ouverte, sur un tronçon
        self.assertLess(length_at(tp, -0.5), length_at(tp, -1.5) / 2)       # avant : 144 mm à chaque cote

    def test_the_last_level_of_an_open_stretch_runs_the_asked_way(self):
        pts = [(0, 0), (30, 0), (30, 15), (15.6, 15), (15.6, 35), (14.4, 35), (14.4, 15), (0, 15)]   # poche et rainure

        def way(step):
            s, a, b = plan(4.0, 1.0, 3.0, step)
            tp = strategies.compute(doc_of(geom.polyline(pts, closed=True)), s, b)
            dy = [m.y - p.y for p, m in cut_steps(tp) if abs(m.z + 3.0) < 1e-6 and abs(p.z + 3.0) < 1e-6
                  and abs(m.x - 14.9) < 0.02 and abs(p.x - 14.9) < 0.02 and abs(m.y - p.y) > 10]   # le long de la rainure
            self.assertTrue(dy, step)
            return dy[-1] > 0
        self.assertEqual(way(0.5), way(0.6))                                # 6 cotes ou 5 : le même sens au fond

    def test_a_v_bit_finishes_at_the_bottom_only(self):
        v = model.CamTool(name='V', kind='conique', diameter=3.0, angle=60.0, tip=0.2, step_down=0.25)
        s, a, b = plan(3.0, 1.0, 1.0, 0.25, rough_stock=0.1, stock=0.1, small=v)
        tp = strategies.compute(doc_of(geom.rect(0, 0, 30, 15)), s, b)
        self.assertFalse(any('à toutes les cotes' in w for w in tp.warnings))             # avant : annoncé, et fait
        self.assertGreater(length_at(tp, -1.0), 60.0)
        self.assertLess(length_at(tp, -0.5), 30.0)                          # (les restes des coins, pas la finition)


if __name__ == '__main__':
    unittest.main()
