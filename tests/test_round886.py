"""Round 886 : les Gammes enregistrées dans TypeEdit, importées par `gamme.build` ; passes globales, cadre ignoré et rampes relevés dans TE13."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', os.path.join(tempfile.mkdtemp(), 'session'))
os.environ.setdefault('VECTORDRIVE_NO_TYPEEDIT', '1')

from vectordrive.cam import gamme
from vectordrive.cam import model as M
from vectordrive.cam import strategies as S
from vectordrive.cam import templates as TPL
from vectordrive.cam import tpp
from vectordrive.core import geom
from vectordrive.core.document import Document, Layer, Plate, Shape

TAN15 = math.tan(math.radians(15))


def fraise(d):
    return M.CamTool(name=f'c{d}', kind='fraise', diameter=d)


def cone(tip, angle=30.0):
    return M.CamTool(name=f'k{tip}', kind='conique', diameter=6.0, tip=tip, angle=angle)


def preset(tools, glob=None, **gamme_keys):
    keys = {'ZBottom': '3.e-003', 'SkipExternal': '0', 'ModeOnBottom': '1', 'Allowance': '0.', 'Zup': '0.'}
    keys.update(gamme_keys)
    p = tpp.Preset(name='Essai', kind='CP_Sequence_MultiTool', sections={'SPECIALGAMME_NEW': keys, 'FAO_NEWPARAMGLOB': glob or {}})
    p.tools = tools
    return p


def ops_of(p):
    return tpp.to_template(p)['operations']


def square(x0, y0, x1, y1):
    return geom.polyline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], closed=True)


def drawing(*paths):
    doc = Document()
    layer = Layer(name='Plan 1', items=[Shape(path=geom.Path(list(p) if isinstance(p, tuple) else [p])) for p in paths])
    doc.layers[:] = [layer]
    doc.active = layer.id
    doc.plate = Plate(width=300, height=200)
    return doc


def run_template(doc, p):
    setup, _r = TPL.apply(M.CamSetup(), tpp.to_template(p), replace=True)
    return setup, S.compute_all(doc, setup)


def cuts(tp):
    return [m for m in tp.moves if m.kind != 'rapid']


class Lignes(unittest.TestCase):
    """Les clés de SPECIALGAMME_NEW, relevées sur les fichiers de TE."""

    def test_une_ligne_sans_profondeur_propre_va_a_celle_de_la_gamme(self):
        ops = ops_of(preset([fraise(3.0), cone(0.4)], ZBottom='1.5e-003', ZBottom_0='3.e-003', independant_depth_0='0', ZBottom_1='3.e-003',
                            independant_depth_1='0'))
        self.assertEqual([o['depth'] for o in ops], [1.5, 1.5])

    def test_une_ligne_a_profondeur_propre(self):
        ops = ops_of(preset([fraise(3.0), cone(0.4)], ZBottom_0='3.e-003', independant_depth_0='0', ZBottom_1='1.5e-003', independant_depth_1='1'))
        self.assertEqual([o['depth'] for o in ops], [3.0, 1.5])

    def test_la_paroi_de_la_fraise_suit_la_profondeur_du_cone(self):
        ops = ops_of(preset([fraise(3.0), cone(0.4)], Allowance='1.e-004', ZBottom_1='1.5e-003', independant_depth_1='1'))
        self.assertAlmostEqual(ops[0]['stock'], 0.1 + 1.5 * TAN15, places=6)
        self.assertAlmostEqual(ops[1]['stock'], 0.1)

    def test_passes_de_chaque_ligne(self):
        ops = ops_of(preset([fraise(3.0), cone(0.4)], NbSlices_0='2', NbSlices_1='5'))
        self.assertEqual(ops[0]['step_down'], 1.5)
        self.assertEqual(ops[1]['vcarve_step'], 0.6)

    def test_finition_3d_et_cadre(self):
        ops = ops_of(preset([fraise(3.0), cone(0.4)], Mode3DOnly_1='1', SkipExternal='1'))
        self.assertEqual(ops[1]['vcarve_mode'], 'passes')
        self.assertTrue(all(o['finish_skip_frame'] for o in ops))
        ops = ops_of(preset([fraise(3.0), cone(0.4)], Mode3DOnly_1='0'))
        self.assertEqual(ops[1]['vcarve_mode'], 'contour')
        self.assertFalse(ops[1]['finish_skip_frame'])

    def test_balayage_et_contournage_de_la_premiere_ligne(self):
        ops = ops_of(preset([fraise(3.0), cone(0.4)], Sweeping_0='1', AngleDecal_0=str(math.pi / 2), Stepover_0='1.5e-003'))
        self.assertEqual((ops[0]['pocket_mode'], ops[0]['sweep_angle'], ops[0]['stepover_mm']), ('balayage', 90.0, 1.5))
        self.assertEqual(ops_of(preset([fraise(3.0), cone(0.4)], Sweeping_0='0'))[0]['pocket_mode'], 'concentrique')

    def test_sens_de_chaque_ligne(self):
        ops = ops_of(preset([fraise(3.0), cone(0.4)], climbMilling_0='1', climbMilling_1='2'))
        self.assertEqual([o['climb'] for o in ops], [False, True])

    def test_trois_outils_et_outil_d_avant(self):
        ops = ops_of(preset([fraise(3.0), fraise(2.0), cone(0.4)]))
        self.assertEqual([o['kind'] for o in ops], ['poche', 'reste', 'vcarve'])
        self.assertEqual(ops[1]['ref_tool_id'], ops[0]['tool_id'])
        self.assertEqual(ops[2]['ref_tool_id'], ops[1]['tool_id'])
        self.assertTrue(all(o['gamme_rule'] >= 885 for o in ops[1:]))

    def test_deux_cones_le_premier_laisse_la_pointe_du_second(self):
        ops = ops_of(preset([fraise(3.0), cone(0.4), cone(0.2)]))
        self.assertAlmostEqual(ops[1]['vcarve_offset'], 0.1)
        self.assertEqual(ops[2]['vcarve_offset'], 0.0)

    def test_plongee_et_ordre_des_passes_pour_toutes_les_lignes(self):
        ops = ops_of(preset([fraise(3.0), fraise(2.0), cone(0.4)], glob={'PLONGEEANGULAIRE_ATIVE': '1', 'PLONGEEANGULAIRE_ANGLE': str(math.radians(10)),
                                                                          'MODE_MULTIPASSE': '0'}))
        for o in ops:
            self.assertTrue(o['ramp'])
            self.assertAlmostEqual(o['ramp_angle'], 10.0)
            self.assertEqual(o['pass_order'], 'global')
        ops = ops_of(preset([fraise(3.0), cone(0.4)], glob={'PLONGEEANGULAIRE_ATIVE': '0', 'MODE_MULTIPASSE': '1'}))
        self.assertFalse(any(o['ramp'] for o in ops))
        self.assertEqual({o['pass_order'] for o in ops}, {'poche'})

    def test_en_surface_et_en_fond(self):
        self.assertEqual(ops_of(preset([fraise(3.0), cone(0.4)], ModeOnBottom='1'))[0]['contour_ref'], 'surface')
        ops = ops_of(preset([fraise(3.0), cone(0.4)], ModeOnBottom='2'))
        self.assertEqual(ops[0]['contour_ref'], 'fond')
        self.assertEqual(ops[0]['stock'], 0.0)

    def test_le_plan_de_depart(self):
        ops = ops_of(preset([fraise(3.0), cone(0.4)], Zup='5.e-004'))
        self.assertEqual({o['z_start'] for o in ops}, {0.5})

    def test_les_operations_passent_par_le_modele(self):
        setup, _r = TPL.apply(M.CamSetup(), tpp.to_template(preset([fraise(3.0), cone(0.4)])), replace=True)
        self.assertEqual([o.kind for o in setup.operations], ['poche', 'vcarve'])
        self.assertEqual(setup.operations[1].ref_tool_id, setup.operations[0].tool_id)
        self.assertEqual(setup.operations[1].gamme_rule, 885)


class Calcul(unittest.TestCase):
    """Une gamme importée, calculée, aux décalages relevés dans TE13."""

    def test_decalages_de_la_fraise_et_du_cone(self):
        doc = drawing(square(10, 10, 40, 40))
        p = preset([fraise(3.0), cone(0.6)], ZBottom='2.e-003', Allowance='1.e-004', ZBottom_1='1.5e-003', independant_depth_1='1', Mode3DOnly_1='0')
        _s, (a, b) = run_template(doc, p)
        self.assertAlmostEqual(min(m.x for m in a.moves), 10 + 1.5 + 0.1 + 1.5 * TAN15, places=3)
        self.assertAlmostEqual(min(m.z for m in cuts(a)), -2.0)
        self.assertAlmostEqual(min(m.x for m in b.moves), 10 + 0.3 + 0.1 + 1.5 * TAN15, places=3)
        self.assertAlmostEqual(min(m.z for m in cuts(b)), -1.5)

    def test_avec_rampe_les_sommets_du_cone_restent_en_z_0(self):
        doc = drawing(square(10, 10, 40, 40))
        p = preset([fraise(3.0), cone(0.6)], glob={'PLONGEEANGULAIRE_ATIVE': '1', 'PLONGEEANGULAIRE_ANGLE': str(math.radians(10))}, Mode3DOnly_1='1',
                   ZBottom='1.e-003')
        _s, (_a, b) = run_template(doc, p)
        self.assertLessEqual(max(m.z for m in cuts(b)), 1e-9)


class Passes(unittest.TestCase):
    """MODE_MULTIPASSE : Global, chaque passe sur tout le dessin ; sinon, chaque forme jusqu'au fond."""

    def order(self, pass_order, finish3d):
        doc = drawing(square(10, 10, 30, 30), square(60, 10, 80, 30))
        c, k = fraise(3.0), cone(0.4)
        setup = M.CamSetup(tools=[c, k])
        ops = gamme.build(setup, [gamme.Step(c.id, 'contournage'), gamme.Step(k.id, finish3d=finish3d, step_down=0.5)], 1.0, climb=True, pass_order=pass_order)
        setup.operations = list(ops)
        tp = S.compute(doc, setup, ops[1], (0.0, 0.0))
        seen = []
        for m in tp.moves:
            if m.kind != 'rapid' and m.z <= -0.5 + 1e-6:
                key = (m.x > 45, round(m.z, 3) < -0.5 - 1e-6)
                if not seen or seen[-1] != key:
                    seen.append(key)
        return seen

    def test_global_une_passe_sur_tout_le_dessin_puis_la_suivante(self):
        for finish3d in (True, False):
            seen = self.order('global', finish3d)
            first_deep = next(i for i, s in enumerate(seen) if s[1])
            self.assertEqual({s[0] for s in seen[:first_deep]}, {False, True})

    def test_poche_par_poche_chaque_forme_jusqu_au_fond(self):
        for finish3d in (True, False):
            seen = self.order('poche', finish3d)
            turn = next(i for i, s in enumerate(seen) if s[0] != seen[0][0])
            self.assertTrue(any(s[1] for s in seen[:turn]))


class Reprise(unittest.TestCase):

    def run_rest(self, **kw):
        doc = drawing((square(10, 10, 60, 60), square(20, 20, 50, 50)), square(100, 10, 130, 40))
        big, small = fraise(6.0), fraise(3.0)
        setup = M.CamSetup(tools=[big, small])
        ops = gamme.build(setup, [gamme.Step(big.id, 'contournage'), gamme.Step(small.id, step_down=kw.pop('step_down', 0.0))], 1.0, climb=True, **kw)
        setup.operations = list(ops)
        return S.compute(doc, setup, ops[1], (0.0, 0.0))

    def test_cadre_ignore_ses_angles_ne_sont_pas_repris(self):
        full = self.run_rest()
        self.assertLess(min(m.x for m in cuts(full)), 20)
        skip = self.run_rest(skip_frame=True)
        self.assertGreater(min(m.x for m in cuts(skip)), 90)                # seule la forme sans trou garde les siens

    def test_global_chaque_passe_sur_tous_les_coins(self):
        tp = self.run_rest(step_down=0.5, pass_order='global')
        zs = [round(m.z, 3) for m in cuts(tp)]
        first_deep = next(i for i, z in enumerate(zs) if z < -0.5)
        self.assertEqual(len({(m.x > 90) for m in cuts(tp)[:first_deep]}), 2)

    def test_chaque_coin_jusqu_au_fond_sinon(self):
        tp = self.run_rest(step_down=0.5)
        seq = cuts(tp)
        first_deep = next(i for i, m in enumerate(seq) if m.z < -0.5)
        self.assertEqual(len({(m.x > 90) for m in seq[:first_deep]}), 1)


class Rampe(unittest.TestCase):

    def corner_rest(self, ramp=True, angle=10.0):
        doc = drawing(square(10, 10, 60, 60))
        big, small = fraise(6.0), fraise(2.0)
        setup = M.CamSetup(tools=[big, small])
        ops = gamme.build(setup, [gamme.Step(big.id, 'contournage'), gamme.Step(small.id, step_down=1.0)], 1.0, climb=True, ramp=ramp, ramp_angle=angle)
        setup.operations = list(ops)
        return S.compute(doc, setup, ops[1], (0.0, 0.0))

    def test_une_reprise_descend_en_rampe(self):
        tp = self.corner_rest()
        zs = sorted({round(m.z, 3) for m in cuts(tp)})
        self.assertGreater(len(zs), 5)
        q = None
        for m in tp.moves:
            if q is not None and m.kind == 'feed' and q.kind != 'rapid' and -1 < min(m.z, q.z) and m.z != q.z:
                run = math.hypot(m.x - q.x, m.y - q.y)
                if run > 1e-6:
                    self.assertLessEqual(abs(m.z - q.z) / run, math.tan(math.radians(10.0)) + 1e-6)
            q = m

    def test_sans_rampe_elle_plonge(self):
        tp = self.corner_rest(ramp=False)
        self.assertEqual(sorted({round(m.z, 3) for m in cuts(tp)}), [-1.0])

    def test_sur_un_tout_petit_anneau_l_outil_plonge(self):
        c = fraise(2.0)
        em = S.Emitter(M.Operation(kind='poche', depth=1.0), c)
        em.travel(0.0, 0.0)
        ring = [(0.0, 0.0), (0.005, 0.0), (0.005, 0.005), (0.0, 0.005), (0.0, 0.0)]
        allowed = geom_box(-1, -1, 1, 1)
        n = len(em.moves)
        S.ramp_floor(em, [ring], allowed, 0.0, -1.0, 10.0)
        self.assertEqual(len(em.moves), n)                                  # rien : mill_rings plongera

    def test_aller_et_retour_le_long_du_fond(self):
        c = fraise(2.0)
        em = S.Emitter(M.Operation(kind='poche', depth=1.0), c)
        ring = [(0.0, 0.0), (20.0, 0.0), (20.0, 2.0), (0.0, 2.0), (0.0, 0.0)]
        allowed = geom_box(-1, -1, 21, 3)
        S.ramp_floor(em, [ring], allowed, 0.0, -1.0, 10.0)
        self.assertAlmostEqual(em.pos[2], -1.0)
        self.assertAlmostEqual(em.pos[0], 0.0)
        self.assertAlmostEqual(em.pos[1], 0.0)


class AnglesDansLaPasseHaute(unittest.TestCase):
    """Relevé dans TE13 : à une passe haute d'un cône profond, la bande entre le contour et la paroi de la fraise n'est pas vidée."""

    def run_cone(self, n):
        doc = drawing(square(10, 10, 60, 60))
        c, k = fraise(2.0), cone(0.4)
        setup = M.CamSetup(tools=[c, k])
        ops = gamme.build(setup, [gamme.Step(c.id, 'contournage'), gamme.Step(k.id, finish3d=False, step_down=3.0 / n)], 3.0, climb=True)
        setup.operations = list(ops)
        return S.compute(doc, setup, ops[1], (0.0, 0.0))

    def test_pas_de_bande_le_long_des_murs(self):
        tp = self.run_cone(5)
        wall = 3.0 * TAN15
        off = 0.2 + 0.6 * TAN15
        self.assertLess(off + 0.2, wall)                                    # il y a bien une bande
        at = 0.0
        q = None
        for m in tp.moves:
            if q is not None and m.kind != 'rapid' and abs(m.z + 0.6) < 1e-6 and abs(q.z + 0.6) < 1e-6:
                at += math.hypot(m.x - q.x, m.y - q.y)
            q = m
        ring = 4 * (50 - 2 * off)
        self.assertGreater(at, ring - 1e-3)                                 # le contour, les angles, pas un tour de plus le long des murs
        self.assertLess(at, ring + 40.0)

    def test_la_derniere_passe_finit_le_mur(self):
        tp = self.run_cone(5)
        self.assertAlmostEqual(min(m.x for m in cuts(tp) if abs(m.z + 3.0) < 1e-6), 10 + 0.2 + 3.0 * TAN15, places=3)


def geom_box(x0, y0, x1, y1):
    from shapely.geometry import box
    return box(x0, y0, x1, y1)


if __name__ == '__main__':
    unittest.main()
