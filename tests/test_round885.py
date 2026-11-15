"""Round 885 : la Gamme relevée dans TE13."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', os.path.join(tempfile.mkdtemp(), 'session'))
os.environ.setdefault('VECTORDRIVE_NO_TYPEEDIT', '1')

import shapely

from vectordrive.cam import gamme
from vectordrive.cam import model as M
from vectordrive.cam import strategies as S
from vectordrive.core import geom
from vectordrive.core.document import Document, Layer, Plate, Shape

TAN = math.tan(math.radians(30))


def square(x0, y0, x1, y1):
    return geom.polyline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], closed=True)


def drawing(*paths):
    doc = Document()
    layer = Layer(name='Plan 1', items=[Shape(path=geom.Path(list(p))) for p in paths])
    doc.layers[:] = [layer]
    doc.active = layer.id
    doc.plate = Plate(width=300, height=200)
    return doc


def frame():
    """Un cadre de 50 mm, avec un trou de 30 mm : une bande de 10 mm de large."""
    return (square(10, 10, 60, 60), square(20, 20, 50, 50))


def tools():
    c3 = M.CamTool(name='c3', kind='fraise', diameter=3.0)
    c6 = M.CamTool(name='c6', kind='fraise', diameter=6.0)
    k5 = M.CamTool(name='k5', kind='conique', diameter=6.0, tip=0.5, angle=60.0)
    k2 = M.CamTool(name='k2', kind='conique', diameter=6.0, tip=0.2, angle=60.0)
    return M.CamSetup(tools=[c3, c6, k5, k2]), c3, c6, k5, k2


def run(doc, setup, steps, depth=1.0, **kw):
    ops = gamme.build(setup, steps, depth, climb=True, **kw)
    setup.operations = list(ops)
    return ops, S.compute_all(doc, setup)


def length(tp):
    total = 0.0
    prev = None
    for m in tp.moves:
        if prev is not None and m.kind != 'rapid':
            total += math.dist((prev.x, prev.y, prev.z), (m.x, m.y, m.z))
        prev = m
    return total


def cut(tp):
    return [m for m in tp.moves if m.kind != 'rapid']


def min_x(tp):
    return min(m.x for m in cut(tp))


class Lignes(unittest.TestCase):

    def test_la_fraise_reste_a_la_pente_du_cone_sans_la_pointe(self):
        s, c3, _c6, k5, _k2 = tools()
        ops = gamme.build(s, [gamme.Step(c3.id), gamme.Step(k5.id)], 1.0, stock=0.1)
        self.assertAlmostEqual(ops[0].stock, 0.1 + TAN, places=6)

    def test_en_fond_ou_sans_cone_pas_de_pente(self):
        s, c3, c6, k5, _k2 = tools()
        ops = gamme.build(s, [gamme.Step(c3.id), gamme.Step(k5.id)], 1.0, stock=0.1, contour_ref='fond')
        self.assertAlmostEqual(ops[0].stock, 0.1, places=6)
        ops = gamme.build(s, [gamme.Step(c6.id), gamme.Step(c3.id)], 1.0)
        self.assertEqual([o.stock for o in ops], [0.0, 0.0])

    def test_toutes_les_fraises_gardent_la_meme_paroi(self):
        s, c3, c6, k5, _k2 = tools()
        ops = gamme.build(s, [gamme.Step(c6.id), gamme.Step(c3.id), gamme.Step(k5.id)], 1.0)
        self.assertAlmostEqual(ops[0].stock, TAN, places=6)
        self.assertAlmostEqual(ops[1].stock, TAN, places=6)

    def test_profondeur_de_passe_par_ligne(self):
        s, c3, _c6, k5, _k2 = tools()
        ops = gamme.build(s, [gamme.Step(c3.id, step_down=0.25), gamme.Step(k5.id, step_down=0.5)], 1.0)
        self.assertEqual(ops[0].step_down, 0.25)
        self.assertEqual(ops[1].vcarve_step, 0.5)

    def test_un_cone_laisse_la_pointe_du_suivant(self):
        s, c3, _c6, k5, k2 = tools()
        ops = gamme.build(s, [gamme.Step(c3.id), gamme.Step(k5.id), gamme.Step(k2.id)], 1.0)
        self.assertAlmostEqual(ops[1].vcarve_offset, 0.1, places=6)
        self.assertEqual(ops[2].vcarve_offset, 0.0)

    def test_distance_entre_passes_du_cone(self):
        s, _c3, _c6, k5, k2 = tools()
        ops = gamme.build(s, [gamme.Step(k5.id), gamme.Step(k2.id, stepover=0.05)], 1.0)
        self.assertAlmostEqual(ops[0].stepover_mm, 0.25, places=6)   # relevé dans TE13 : 50 % de la pointe
        self.assertEqual(ops[1].stepover_mm, 0.05)

    def test_chaque_outil_part_du_precedent(self):
        s, c3, _c6, k5, k2 = tools()
        ops = gamme.build(s, [gamme.Step(c3.id), gamme.Step(k5.id), gamme.Step(k2.id)], 1.0)
        self.assertEqual(ops[1].ref_tool_id, c3.id)
        self.assertEqual(ops[2].ref_tool_id, k5.id)
        self.assertEqual([o.gamme_rule for o in ops], [0, 885, 885])

    def test_la_paroi_suit_la_profondeur_du_cone_pas_celle_de_la_fraise(self):
        s, c3, _c6, k5, _k2 = tools()
        ops = gamme.build(s, [gamme.Step(c3.id), gamme.Step(k5.id, depth=1.0)], 2.0)
        self.assertEqual((ops[0].depth, ops[1].depth), (2.0, 1.0))
        self.assertAlmostEqual(ops[0].stock, TAN, places=6)
        ops = gamme.build(s, [gamme.Step(c3.id, depth=1.0), gamme.Step(k5.id)], 2.0)
        self.assertEqual((ops[0].depth, ops[1].depth), (1.0, 2.0))
        self.assertAlmostEqual(ops[0].stock, 2 * TAN, places=6)
        self.assertEqual(ops[1].ref_tool_id, c3.id)


class Relevé(unittest.TestCase):
    """Les valeurs mesurées dans TE13 sur le même cadre (décalages, cotes)."""

    def test_fraise_puis_cone_avec_finition_3d(self):
        s, c3, _c6, k5, _k2 = tools()
        _ops, tps = run(drawing(frame()), s, [gamme.Step(c3.id, stepover=1.5, step_down=1.0), gamme.Step(k5.id)])
        self.assertAlmostEqual(min_x(tps[0]), 10 + 1.5 + TAN, places=2)
        self.assertAlmostEqual(min_x(tps[1]), 10.25, places=2)           # le sommet de l'angle, à la pointe
        zs = [m.z for m in cut(tps[1])]
        self.assertAlmostEqual(min(zs), -1.0, places=6)
        self.assertAlmostEqual(max(zs), 0.0, places=6)

    def test_cone_sans_finition_3d_a_la_cote_seulement(self):
        s, c3, _c6, k5, _k2 = tools()
        _ops, tps = run(drawing(frame()), s, [gamme.Step(c3.id), gamme.Step(k5.id, finish3d=False)])
        zs = {round(m.z, 6) for m in cut(tps[1])}
        self.assertEqual(zs, {-1.0})
        self.assertAlmostEqual(min_x(tps[1]), 10 + 0.25 + TAN, places=2)

    def test_le_premier_cone_laisse_la_pointe_du_suivant(self):
        s, c3, _c6, k5, k2 = tools()
        _ops, tps = run(drawing(frame()), s, [gamme.Step(c3.id), gamme.Step(k5.id, finish3d=False), gamme.Step(k2.id, finish3d=False)])
        self.assertAlmostEqual(min_x(tps[1]), 10 + 0.25 + TAN + 0.1, places=2)
        self.assertAlmostEqual(min_x(tps[2]), 10 + 0.1 + TAN, places=2)

    def test_en_fond_de_gravure(self):
        s, c3, _c6, k5, _k2 = tools()
        _ops, tps = run(drawing(frame()), s, [gamme.Step(c3.id), gamme.Step(k5.id)], contour_ref='fond')
        self.assertAlmostEqual(min_x(tps[0]), 11.5, places=2)
        self.assertAlmostEqual(min_x(tps[1]), 10.25, places=2)
        self.assertEqual({round(m.z, 6) for m in cut(tps[1])}, {-1.0})

    def test_surepaisseur(self):
        s, c3, _c6, k5, _k2 = tools()
        _ops, tps = run(drawing(frame()), s, [gamme.Step(c3.id), gamme.Step(k5.id)], stock=0.1)
        self.assertAlmostEqual(min_x(tps[0]), 10 + 1.5 + TAN + 0.1, places=2)
        self.assertAlmostEqual(min_x(tps[1]), 10.35, places=2)

    def test_deux_passes(self):
        s, c3, _c6, k5, _k2 = tools()
        _ops, tps = run(drawing(frame()), s, [gamme.Step(c3.id, step_down=0.5), gamme.Step(k5.id, step_down=0.5)])
        for tp in tps:
            floors = {round(m.z, 6) for m in cut(tp) if m.z <= -0.5 + 1e-6}
            self.assertEqual(floors, {-0.5, -1.0})

    def test_fraise_plus_profonde_que_le_cone(self):
        s, c3, _c6, k5, _k2 = tools()
        _ops, tps = run(drawing(frame()), s, [gamme.Step(c3.id, stepover=1.5, step_down=2.0), gamme.Step(k5.id, depth=1.0, step_down=1.0)], depth=2.0)
        self.assertAlmostEqual(min_x(tps[0]), 10 + 1.5 + TAN, places=2)
        self.assertAlmostEqual(min(m.z for m in cut(tps[0])), -2.0, places=6)
        self.assertAlmostEqual(min(m.z for m in cut(tps[1])), -1.0, places=6)
        self.assertAlmostEqual(min_x(tps[1]), 10.25, places=2)

    def test_cone_plus_profond_que_la_fraise_une_rainure_le_long_du_contour(self):
        s, c3, _c6, k5, _k2 = tools()
        _ops, tps = run(drawing(frame()), s, [gamme.Step(c3.id, depth=1.0, stepover=1.5, step_down=1.0), gamme.Step(k5.id, step_down=2.0)], depth=2.0)
        self.assertAlmostEqual(min_x(tps[0]), 10 + 1.5 + 2 * TAN, places=2)
        self.assertAlmostEqual(min(m.z for m in cut(tps[0])), -1.0, places=6)
        self.assertAlmostEqual(min(m.z for m in cut(tps[1])), -2.0, places=6)
        # relevé dans TE13 : le fond reste où la fraise l'a laissé, le cône ne le reprend pas
        self.assertLess(length(tps[1]), 450.0)

    def test_deux_cones_a_des_profondeurs_differentes(self):
        s, c3, _c6, k5, k2 = tools()
        _ops, tps = run(drawing(frame()), s, [gamme.Step(c3.id, stepover=1.5, step_down=2.0), gamme.Step(k5.id, depth=1.2), gamme.Step(k2.id, depth=0.6)], depth=2.0)
        self.assertAlmostEqual(min_x(tps[0]), 10 + 1.5 + 1.2 * TAN, places=2)      # à la profondeur du premier cône
        self.assertAlmostEqual(min_x(tps[1]), 10.35, places=2)
        self.assertAlmostEqual(min_x(tps[2]), 10.10, places=2)
        self.assertAlmostEqual(min(m.x for m in cut(tps[2]) if m.z < -0.59), 10 + 0.1 + 0.6 * TAN, places=2)
        # le flanc du premier cône a vidé le fond du second : un tour de chaque contour, pas de reprise le long des parois
        self.assertLess(length(tps[2]), 400.0)

    def test_ignorer_le_cadre(self):
        s, c3, _c6, k5, _k2 = tools()
        other = (square(70, 10, 100, 30),)
        _ops, tps = run(drawing(frame(), other), s, [gamme.Step(c3.id), gamme.Step(k5.id)], skip_frame=True)
        # relevé dans TE13 : seul le cadre, celui qui a des trous, est sauté. Sa paroi intérieure reste, et l'autre forme garde son contour
        cone = tps[1]
        band = [m for m in cut(cone) if m.x < 65]
        self.assertAlmostEqual(min(m.x for m in band), 20 - 0.25 - TAN, places=2)
        self.assertAlmostEqual(max(m.x for m in band), 50 + 0.25 + TAN, places=2)
        self.assertAlmostEqual(min(m.x for m in cut(cone) if m.x > 65), 70.25, places=2)

    def test_pas_de_passes_sur_les_flancs(self):
        s, c3, _c6, k5, _k2 = tools()
        _ops, tps = run(drawing(frame()), s, [gamme.Step(c3.id), gamme.Step(k5.id)])
        # le tour de l'extérieur et du trou, sans rien entre les deux : TE13 fait 193 + 125 mm + les montées d'angle
        self.assertLess(length(tps[1]), 400.0)


class Matière(unittest.TestCase):

    def surface(self, tps, setup):
        from vectordrive.cam import simulate as SI
        return SI.simulate(tps, setup, res=0.05, margin=4.0, max_cells=4_000_000)

    def at(self, sim, x, y):
        return float(sim.H[int(round((y - sim.y0) / sim.res)), int(round((x - sim.x0) / sim.res))])

    def test_fond_vide_partout_et_paroi_a_la_pente(self):
        s, c3, _c6, k5, _k2 = tools()
        _ops, tps = run(drawing(frame()), s, [gamme.Step(c3.id, stepover=1.5, step_down=1.0), gamme.Step(k5.id)])
        sim = self.surface(tps, s)
        self.assertAlmostEqual(self.at(sim, 15.0, 15.0), -1.0, places=3)
        self.assertAlmostEqual(self.at(sim, 15.0, 40.0), -1.0, places=3)
        self.assertAlmostEqual(self.at(sim, 10.0 + TAN + 0.05, 40.0), -1.0, delta=0.11)     # le pied de la paroi
        self.assertGreater(self.at(sim, 10.0 + TAN / 2, 40.0), -0.6)                         # la paroi, à mi-pente
        self.assertLess(self.at(sim, 10.0 + TAN / 2, 40.0), -0.4)
        self.assertGreater(self.at(sim, 9.9, 40.0), -0.02)                                   # le bord n'est pas entamé
        self.assertAlmostEqual(self.at(sim, 11.0, 11.0), -1.0, delta=0.15)                   # l'angle est vidé

    def test_bande_trop_etroite_pour_la_fraise_videe_par_le_cone(self):
        s, c3, _c6, k5, _k2 = tools()
        narrow = (square(10, 10, 40, 40), square(13, 13, 37, 37))             # 3 mm de large : la fraise n'y entre pas à cette distance de la paroi
        _ops, tps = run(drawing(narrow), s, [gamme.Step(c3.id, step_down=1.0), gamme.Step(k5.id)])
        sim = self.surface(tps, s)
        self.assertAlmostEqual(self.at(sim, 11.5, 25.0), -1.0, places=2)
        self.assertAlmostEqual(self.at(sim, 11.2, 25.0), -1.0, delta=0.05)
        self.assertAlmostEqual(self.at(sim, 11.8, 25.0), -1.0, delta=0.05)

    def test_angle_aigu_repris_par_le_cone(self):
        s, c3, _c6, k5, _k2 = tools()
        tri = (geom.polyline([(10, 10), (60, 10), (35, 50)], closed=True),)
        _ops, tps = run(drawing(tri), s, [gamme.Step(c3.id, step_down=1.0), gamme.Step(k5.id)])
        sim = self.surface(tps, s)
        # au pied de la pointe, là où la fraise ne va pas
        self.assertAlmostEqual(self.at(sim, 35.0, 46.8), -1.0, delta=0.1)
        self.assertGreaterEqual(self.at(sim, 35.0, 50.5), -1e-9)

    def test_le_cone_n_entame_pas_la_paroi(self):
        s, c3, _c6, k5, _k2 = tools()
        tri = (geom.polyline([(10, 10), (60, 10), (35, 50)], closed=True),)
        doc = drawing(tri, frame())
        _ops, tps = run(doc, s, [gamme.Step(c3.id, step_down=1.0), gamme.Step(k5.id)])
        reg = S.region([S.item_geometry(i) for i in doc.layers[0].items], s.tolerance)
        worst = -1.0
        prev = None
        for m in tps[1].moves:
            if prev is not None and m.kind != 'rapid':
                n = max(1, int(math.dist((prev.x, prev.y), (m.x, m.y)) / 0.1))
                for i in range(1, n + 1):
                    a = i / n
                    x, y, z = prev.x + a * (m.x - prev.x), prev.y + a * (m.y - prev.y), prev.z + a * (m.z - prev.z)
                    if z < -1e-6:
                        worst = max(worst, 0.25 - z * TAN - reg.boundary.distance(shapely.Point(x, y)))
            prev = m
        self.assertLess(worst, 0.02)


class Etroit(unittest.TestCase):

    def test_branche_de_la_largeur_exacte_de_la_pointe(self):
        s, c3, _c6, k5, _k2 = tools()
        stem = (geom.polyline([(70, 10), (100, 10), (100, 20), (75.25, 20), (75.25, 50), (74.75, 50), (74.75, 20), (70, 20)], closed=True),)
        _ops, tps = run(drawing(stem), s, [gamme.Step(c3.id, step_down=1.0), gamme.Step(k5.id, finish3d=False)], contour_ref='fond')
        ys = [m.y for m in cut(tps[1]) if abs(m.x - 75.0) < 0.01]
        self.assertGreater(max(ys), 49.5)


class SurépaisseurDePoche(unittest.TestCase):

    def test_une_liaison_au_fond_n_entame_pas_la_surepaisseur(self):
        s, c3, _c6, _k5, _k2 = tools()
        doc = drawing(frame())
        op = M.Operation(kind='poche', tool_id=c3.id, depth=1.0, step_down=1.0, stock=0.5, stepover_mm=1.5, climb=True)
        s.operations = [op]
        tp = S.compute(doc, s, op, (0.0, 0.0))
        reg = S.region([S.item_geometry(doc.layers[0].items[0])], s.tolerance)
        prev = None
        least = 1e9
        for m in tp.moves:
            if prev is not None and m.kind != 'rapid' and min(prev.z, m.z) < 0:
                n = max(1, int(math.dist((prev.x, prev.y), (m.x, m.y)) / 0.1))
                for i in range(n + 1):
                    a = i / n
                    least = min(least, reg.boundary.distance(shapely.Point(prev.x + a * (m.x - prev.x), prev.y + a * (m.y - prev.y))))
            prev = m
        self.assertGreater(least, 1.5 + 0.5 - 0.02)


class Reprise(unittest.TestCase):

    def test_chaque_coin_a_la_suite_l_outil_remonte(self):
        s, c3, c6, _k5, _k2 = tools()
        doc = drawing((square(10, 10, 110, 110),))
        ops, tps = run(doc, s, [gamme.Step(c6.id, step_down=1.0), gamme.Step(c3.id, stepover=1.5, step_down=1.0)])
        self.assertEqual(ops[1].kind, 'reste')
        rest = tps[1]
        # quatre coins de 3 mm : pas de longue liaison au fond entre eux
        self.assertLess(length(rest), 40.0)
        self.assertGreaterEqual(sum(1 for m in rest.moves if m.kind == 'rapid'), 4)


class Fenetre(unittest.TestCase):

    def test_la_profondeur_de_passe_de_chaque_ligne(self):
        from PySide6.QtWidgets import QApplication
        from vectordrive.ui.gamme_dialog import GammeDialog
        QApplication.instance() or QApplication([])
        s, c3, _c6, k5, _k2 = tools()
        d = GammeDialog(None, s, [gamme.Step(c3.id, stepover=1.5, depth=0.8, step_down=0.25, sweep_angle=30.0), gamme.Step(k5.id, finish3d=False)], 1.0)
        got = d.steps()
        self.assertEqual((got[0].stepover, got[0].depth, got[0].step_down, got[0].sweep_angle), (1.5, 0.8, 0.25, 30.0))
        self.assertTrue(got[0].finish3d)
        self.assertEqual((got[1].step_down, got[1].finish3d), (0.0, False))
        self.assertIn('Profondeur de passe', d.COLUMNS)


class Anciennes(unittest.TestCase):

    def test_une_operation_enregistree_garde_son_calcul(self):
        s, c3, _c6, k5, _k2 = tools()
        self.assertEqual(M.Operation.from_dict({'kind': 'vcarve'}).gamme_rule, 0)
        doc = drawing(frame())
        op = M.Operation(kind='vcarve', tool_id=k5.id, depth=1.0, ref_tool_id=c3.id, stock=0.0, climb=True)
        s.operations = [op]
        old = S.compute(doc, s, op, (0.0, 0.0))
        op2 = M.Operation.from_dict(op.to_dict())
        op2.gamme_rule = 885
        new = S.compute(doc, s, op2, (0.0, 0.0))
        self.assertGreater(length(old), length(new))
        self.assertEqual(op.to_dict()['gamme_rule'], 0)


if __name__ == '__main__':
    unittest.main()
