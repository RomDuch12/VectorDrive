"""Round 987 : une gamme est la suite de ses lignes, chacune ne reprenant que ce que les précédentes ont laissé — la reprise
à la fraise ne repasse plus à vide, sans rien laisser de plus ; vrai aussi pour une gamme TypeEdit importée, même enregistrée
avant en modèle, et ses outils ne sont plus pris pour d'autres du même nom ; la matière du tri est suivie au pas fin sur une
grande plaque ; la distance entre passes de la ligne règle la reprise."""
import copy
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', os.path.join(tempfile.mkdtemp(), 'session'))
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from vectordrive.cam import gamme  # noqa: E402
from vectordrive.cam import linkprev as LP  # noqa: E402
from vectordrive.cam import model as M  # noqa: E402
from vectordrive.cam import simulate as SI  # noqa: E402
from vectordrive.cam import strategies as S  # noqa: E402
from vectordrive.cam import templates as TPL  # noqa: E402
from vectordrive.cam import tpp  # noqa: E402
from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Document, Shape  # noqa: E402

#: une croix (angles que la grosse fraise ne prend pas) et une fente plus étroite qu'elle
CROSS = [(10, 0), (16, 0), (16, 10), (26, 10), (26, 16), (16, 16), (16, 26), (10, 26), (10, 16), (0, 16), (0, 10),
         (10, 10)]
SLOT = [(34, 0), (36.2, 0), (36.2, 22), (34, 22)]
BOX = dict(res=0.05, margin=3.0, max_cells=4_000_000)


def drawing():
    doc = Document()
    items = [doc.add(Shape(path=geom.Path([geom.polyline(pts, closed=True)]))) for pts in (CROSS, SLOT)]
    return doc, [it.id for it in items]


def run(rest_step=0.0, *, more=(), linked=None):
    """Gamme F3 puis F1 (et les outils `more`) ; `linked` : forcer le lien de la reprise."""
    doc, ids = drawing()
    big = M.CamTool(name='F3', kind='fraise', diameter=3.0, number=1)
    fine = M.CamTool(name='F1', kind='fraise', diameter=1.0, number=2)
    setup = M.CamSetup(tools=[big, fine, *more])
    steps = [gamme.Step(big.id, 'contournage'), gamme.Step(fine.id, 'contournage', stepover=rest_step)]
    steps += [gamme.Step(t.id) for t in more]
    setup.operations = gamme.build(setup, steps, 1.0, items=ids)
    if linked is not None:
        setup.operations[1].link_previous = linked
    return doc, setup, S.compute_all(doc, setup)


def air(tps, setup, i) -> tuple:
    """(longueur de coupe sans matière enlevée, remontées) du parcours `i`, sur la matière laissée par les parcours d'avant
    et par lui-même au fil de son trajet (mm)."""
    tp = tps[i]
    pieces = LP._pieces(tp, 0.005)
    out = LP.remaining_only(copy.deepcopy(tp), tps[:i], setup, setup.operations[i])

    def key(p):
        return tuple(round(c, 6) for c in p)
    kept = {(key((p.x, p.y, p.z)), key((m.x, m.y, m.z))) for p, m in zip(out.moves, out.moves[1:])}
    idle = sum(math.dist(a, b) for a, b, _k in pieces if (key(a), key(b)) not in kept)
    ups = sum(1 for p, m in zip(tp.moves, tp.moves[1:]) if m.kind == 'rapid' and m.z > p.z + 1e-6)
    return idle, ups


def cone():
    return M.CamTool(name='V30', kind='conique', diameter=6.0, tip=0.2, angle=30.0, number=3)


def cut_length(tp) -> float:
    total, prev = 0.0, None
    for m in tp.moves:
        if prev is not None and m.kind != 'rapid' and min(prev[2], m.z) < 0:
            total += math.dist(prev, (m.x, m.y, m.z))
        prev = (m.x, m.y, m.z)
    return total


class GammeWithoutAirCuts(unittest.TestCase):

    def test_rest_line_is_linked(self):
        """La reprise à la fraise est liée au parcours précédent ; la poche et le cône (qui ne reprend déjà que le reste)
        non."""
        _doc, setup, tps = run(more=[cone()])
        self.assertEqual([o.kind for o in setup.operations], ['poche', 'reste', 'vcarve'])
        self.assertEqual([o.link_previous for o in setup.operations], [False, True, False])
        self.assertTrue(any('lier au parcours précédent' in w for w in tps[1].warnings))

    def test_rest_pass_cuts_less_air_and_leaves_nothing(self):
        """La reprise à la fraise Ø1 après la Ø3 : bien moins de coupe à vide et de remontées (avant : le premier tour de
        chaque angle frôlait le reste depuis le côté déjà vidé, remontée d'un angle à l'autre) ; la gamme enlève ce
        qu'enlève la fraise fine seule : rien de laissé en plus par la reprise raccourcie."""
        doc, setup, tps = run()
        _d, setup0, tps0 = run(linked=False)
        self.assertTrue(tps[1].moves)
        idle, ups = air(tps, setup, 1)
        idle0, ups0 = air(tps0, setup0, 1)
        self.assertLess(idle, 0.7 * idle0)
        self.assertLessEqual(ups, ups0 // 3)
        alone = M.CamSetup(tools=[setup.tools[1]])
        alone.operations = [M.Operation(kind='poche', tool_id=setup.tools[1].id, depth=1.0,
                                        items=list(setup.operations[0].items))]
        ref = S.compute_all(doc, alone)
        a = SI.simulate(tps, setup, **BOX)
        b = SI.simulate(ref, alone, **BOX)
        self.assertAlmostEqual(a.removed, b.removed, delta=0.005 * b.removed)
        c = SI.simulate(tps0, setup0, **BOX)                  # la même gamme non liée : la même pièce, au plus près
        self.assertAlmostEqual(a.removed, c.removed, delta=0.0005 * c.removed)

    def test_line_stepover_is_used(self):
        """La distance entre passes de la ligne (Stepover_i de TE) règle la reprise ; négative : celle de l'outil ; au plus
        90 % du diamètre (sans crêtes entre les passes)."""
        tight = cut_length(run(0.15)[2][1])
        wide = cut_length(run(0.45)[2][1])
        self.assertGreater(tight, 1.3 * wide)
        self.assertAlmostEqual(cut_length(run(-1.0)[2][1]), cut_length(run(0.0)[2][1]), places=6)
        self.assertAlmostEqual(cut_length(run(2.5)[2][1]), cut_length(run(0.9)[2][1]), places=6)

    def test_start_above_zero(self):
        """Z de départ à 1 mm (dessus de la matière) : la reprise liée garde ses passes du haut et ne descend jamais en rapide
        sous le dessus + l'approche (avant : passes au-dessus de 0 retirées, d'où 1,25 mm d'un coup ; approche à la cote
        d'un dessus à 0, plongée rapide dans la matière)."""
        doc, ids = drawing()
        big = M.CamTool(name='F3', kind='fraise', diameter=3.0, number=1)
        fine = M.CamTool(name='F1', kind='fraise', diameter=1.0, number=2)
        levels = []
        for linked in (False, True):
            setup = M.CamSetup(tools=[big, fine])
            steps = [gamme.Step(big.id, 'contournage', step_down=0.25), gamme.Step(fine.id, 'contournage', step_down=0.25)]
            setup.operations = gamme.build(setup, steps, 1.5, items=ids, z_start=1.0)
            setup.operations[1].link_previous = linked
            tp = S.compute_all(doc, setup)[1]
            levels.append({round(m.z, 3) for m in tp.moves if m.kind == 'feed' and m.z < 1.0})
        op = setup.operations[1]
        self.assertIn(0.75, levels[1])
        self.assertLessEqual(levels[1], levels[0])
        low = min(m.z for m in tp.moves if m.kind == 'rapid')
        self.assertGreaterEqual(low, 1.0 + min(op.clear_z, op.safe_z) - 1e-6)

    def test_too_large_keeps_whole_path(self):
        """Une carte qui devrait être trop grossière : la reprise liée est gardée en entier, avec un avertissement (avant :
        tri approché, des morceaux qui enlevaient encore un peu de matière étaient retirés)."""
        saved = LP.MAX_CELLS, getattr(LP, 'MAX_TILE_CELLS', None)
        LP.MAX_CELLS = LP.MAX_TILE_CELLS = 2 * 256 * 256
        try:
            _doc, _setup, tps = run(linked=True)
            _d, _s, tps0 = run(linked=False)
        finally:
            LP.MAX_CELLS, LP.MAX_TILE_CELLS = saved
        self.assertTrue(any('gardé en entier' in w for w in tps[1].warnings), tps[1].warnings)
        self.assertEqual(len(tps[1].moves), len(tps0[1].moves))

    def test_rest_form_shows_stepover(self):
        """La fiche d'une reprise montre la distance entre passes."""
        from vectordrive.ui import cam_panel
        self.assertIn('stepover_mm', cam_panel.KIND_FIELDS['reste'])


class LargePlate(unittest.TestCase):

    def cone_line(self, far: bool):
        """Gamme F3 puis cône sur une croix, et une autre croix au coin opposé d'une plaque de 300 × 200 si `far`."""
        doc = Document()
        shapes = [CROSS] + ([[(x + 280, y + 180) for x, y in CROSS]] if far else [])
        ids = [doc.add(Shape(path=geom.Path([geom.polyline(pts, closed=True)]))).id for pts in shapes]
        big, v = M.CamTool(name='F3', kind='fraise', diameter=3.0, number=1), cone()
        setup = M.CamSetup(tools=[big, v])
        setup.operations = gamme.build(setup, [gamme.Step(big.id, 'contournage'), gamme.Step(v.id)], 1.0, items=ids)
        setup.operations[1].link_previous = True         # lié, quoi que fasse `build`
        return S.compute_all(doc, setup)[1]

    def test_fine_map_on_a_large_plate(self):
        """Deux formes loin l'une de l'autre : la matière reste suivie au pas fin autour de l'outil (avant : une carte pour
        toute la plaque, au pas de 0,1 mm, tri approché), chaque forme triée comme si elle était seule."""
        one, two = self.cone_line(False), self.cone_line(True)
        self.assertFalse([w for w in two.warnings if 'approché' in w])
        self.assertAlmostEqual(cut_length(two), 2 * cut_length(one), delta=0.01 * cut_length(two))


class TypeEditGamme(unittest.TestCase):

    def preset(self):
        keys = {'ZBottom': '1.e-003', 'SkipExternal': '0', 'ModeOnBottom': '1', 'Allowance': '0.', 'Zup': '0.'}
        p = tpp.Preset(name='Essai', kind='CP_Sequence_MultiTool', sections={'SPECIALGAMME_NEW': keys, 'FAO_NEWPARAMGLOB': {}})
        p.tools = [M.CamTool(name='F3', kind='fraise', diameter=3.0), M.CamTool(name='F1', kind='fraise', diameter=1.0),
                   cone()]
        return p

    def test_imported_gamme_is_linked(self):
        """Une gamme TypeEdit importée : la reprise liée au parcours précédent."""
        setup, _r = TPL.apply(M.CamSetup(), tpp.to_template(self.preset()), replace=True)
        self.assertEqual([o.kind for o in setup.operations], ['poche', 'reste', 'vcarve'])
        self.assertEqual([o.link_previous for o in setup.operations], [False, True, False])

    def test_template_saved_before_is_linked(self):
        """Un modèle enregistré avant (version 1, reprise non liée) : liée à son application ; un modèle enregistré
        maintenant garde le choix de l'utilisateur (reprise déliée : déliée)."""
        tpl = tpp.to_template(self.preset())
        tpl['version'] = 1
        for d in tpl['operations']:
            d['link_previous'] = False
        setup, _r = TPL.apply(M.CamSetup(), tpl, replace=True)
        self.assertEqual([o.link_previous for o in setup.operations], [False, True, False])
        setup.operations[1].link_previous = False
        mine = TPL.from_setup(setup, 'Ma gamme')
        again, _r = TPL.apply(M.CamSetup(), mine, replace=True)
        self.assertEqual([o.link_previous for o in again.operations], [False, False, False])

    def test_same_name_other_tool_is_not_taken(self):
        """Appliquée à un document qui a déjà une fraise du même nom mais d'un autre diamètre : la gamme garde ses outils
        (avant : la reprise prenait cette fraise, parfois celle de l'ébauche, et ne reprenait rien)."""
        doc, ids = drawing()
        twin = M.CamTool(name='F1', kind='fraise', diameter=3.0, number=7)
        # le même cône, sans son corps (diamètre de 1 mm d'office d'une fiche) : retrouvé, pas ajouté en double
        v = M.CamTool(name='V30', kind='conique', diameter=1.0, tip=0.2, angle=30.0, number=3)
        setup, _r = TPL.apply(M.CamSetup(tools=[twin, v]), tpp.to_template(self.preset()), replace=True, items=ids)
        rest = setup.operations[1]
        self.assertAlmostEqual(setup.tool(rest.tool_id).diameter, 1.0)
        self.assertNotEqual(rest.tool_id, twin.id)
        self.assertEqual(setup.operations[2].tool_id, v.id)
        self.assertEqual([t.name for t in setup.tools].count('V30'), 1)
        tps = S.compute_all(doc, setup)
        self.assertTrue(tps[1].moves)


if __name__ == '__main__':
    unittest.main()
