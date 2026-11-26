"""Round 1178 (demande du 26/11 : « Electroerosion : fonction de calcul angle fil (avec u et v) qui détecte les chutes
matiere qui se detachent du brut et coupent le fil » ; Fanuc Robocut ; chute à risque : la signaler, proposer
d'incliner le fil et une attache ; dépouille constante ou contours haut et bas). Le cœur : opération « fil_edm »,
chutes, angle minimal, U/V, attaches, post-processeur Fanuc Robocut."""
import math
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1178.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from shapely.geometry import box  # noqa: E402

from vectordrive.cam import model, strategies  # noqa: E402
from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Document, Plate, Shape  # noqa: E402

BEFORE = 'avant : pas d\'électroérosion à fil'


def edm():
    try:
        from vectordrive.cam import wire_edm
    except ImportError:
        raise AssertionError(BEFORE)
    return wire_edm


def robocut():
    try:
        from vectordrive.cam.post import robocut as R
    except ImportError:
        raise AssertionError(BEFORE)
    return R


def drawing(*contours, thickness=10.0):
    """Un dessin : plaque 100 × 50 de `thickness`, un objet par contour (points, fermé)."""
    d = Document()
    d.plate = Plate(width=100.0, height=50.0, thickness=thickness)
    for pts, closed in contours:
        d.layers[0].items.append(Shape(path=geom.Path([geom.polyline(pts, closed=closed)])))
    return d


def square(x, y, w, h):
    return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)], True


def run(doc, side='interieur', order='auto', **params):
    edm()
    op = model.Operation(name='Fil', kind='fil_edm', side=side, order_mode=order, params=params)
    s = model.CamSetup(operations=[op])
    return strategies.compute(doc, s, op), op, s


def cycle(tp):
    return next(c for c in tp.cycles if c.get('kind') == 'fil_edm')


def chutes(tp):
    return cycle(tp)['chutes']


def blocking(warnings):
    return [w for w in warnings if w.startswith('BLOQUANT')]


def part_with_hole():
    """Une pièce 40 × 30 percée d'un trou Ø 10 (un seul objet, deux contours)."""
    d = Document()
    d.plate = Plate(width=100.0, height=50.0, thickness=10.0)
    d.layers[0].items.append(Shape(path=geom.Path([geom.polyline(square(30, 10, 40, 30)[0], True),
                                                     geom.circle((50, 25), 5)])))
    return d


class Pieces(unittest.TestCase):

    def test_square_in_a_square_the_slug_falls_at_the_end_of_its_contour(self):
        tp, _op, _s = run(drawing(square(40, 15, 20, 20)))
        ch = chutes(tp)
        self.assertEqual(len(ch), 1)
        c = ch[0]
        self.assertEqual((c['genre'], c['contour'], c['risque']), ('chute', 1, 'moyen'))
        self.assertAlmostEqual(c['aire'], (20 - 4 * 0.145) ** 2, delta=1.0)       # le carré moins la saignée
        #                                                                           (et l'approche qui y entre)
        self.assertAlmostEqual(c['masse'], 7.85 * c['aire'] * 10 / 1000, places=6)
        self.assertEqual((round(c['x'], 3), round(c['y'], 3)), (40.145, 15.145))   # fin du contour : son départ
        self.assertEqual(c['cote'], 'gauche')                                     # trigo, fil dedans : à gauche
        self.assertTrue(any('chute 1' in w and 'risque moyen' in w for w in tp.warnings), tp.warnings)
        self.assertEqual([z['kind'] for z in tp.zones], ['chute'])

    def test_the_part_itself_falls_when_cut_outside(self):
        tp, _op, _s = run(drawing(square(40, 15, 20, 20)), side='exterieur')
        self.assertEqual([c['genre'] for c in chutes(tp)], ['pièce'])

    def test_part_with_a_hole_the_hole_first_then_the_part(self):
        d = Document()
        d.plate = Plate(width=100.0, height=50.0, thickness=10.0)
        d.layers[0].items.append(Shape(path=geom.Path([geom.polyline(square(30, 10, 40, 30)[0], True),
                                                         geom.circle((50, 25), 5)])))
        tp, _op, _s = run(d, side='exterieur')
        cy = cycle(tp)
        self.assertEqual([c['cote'] for c in cy['contours']], ['interieur', 'exterieur'])   # le trou d'abord
        self.assertEqual([(c['genre'], c['contour']) for c in cy['chutes']], [('chute', 1), ('pièce', 2)])
        self.assertFalse(any('déjà détaché' in w for w in tp.warnings))
        tp2, _op, s2 = run(d, side='exterieur', order='dessin')                   # le tour d'abord : mauvais ordre
        self.assertTrue(any(w.startswith('BLOQUANT') and 'déjà détaché' in w for w in tp2.warnings), tp2.warnings)
        res = robocut().write([tp2], s2)                                          # rien d'écrit
        self.assertEqual((res.text, res.files), ('', []))
        self.assertTrue(any('déjà détaché' in w for w in blocking(res.warnings)), res.warnings)

    def test_a_cut_from_edge_to_edge_parts_the_stock(self):
        d = drawing(([(-5, 20), (105, 20)], False))
        tp, _op, _s = run(d)
        ch = chutes(tp)
        self.assertEqual(len(ch), 1)                                              # le plus grand morceau reste
        self.assertLess(ch[0]['pts'][0][1], 21)                                   # le bas, 100 × 20, tombe
        self.assertEqual(ch[0]['risque'], 'fort')
        self.assertTrue(any('lourde' in w for w in tp.warnings), tp.warnings)
        self.assertIsNone(ch[0]['attache_proposee'])                              # coupe ouverte : pas d'attache
        tp2, _op, _s = run(d, bride=[50, 5])                                      # bridé en bas : le haut tombe
        self.assertGreater(min(y for _x, y in chutes(tp2)[0]['pts']), 19)

    def test_an_open_cut_that_parts_nothing(self):
        tp, _op, _s = run(drawing(([(10, 10), (30, 10)], False)))
        self.assertEqual(chutes(tp), [])
        self.assertEqual(tp.zones, [])
        self.assertFalse(any('chute' in w for w in tp.warnings))

    def test_find_pieces_on_its_own(self):
        W = edm()
        ring = [(2, 2), (8, 2), (8, 8), (2, 8), (2, 2)]
        pieces, problems, held = W.find_pieces(box(0, 0, 10, 10), [{'lines': [ring]}], 0.3)
        self.assertEqual(len(pieces), 1)
        self.assertEqual(problems, [])
        self.assertGreater(held.area, pieces[0]['poly'].area)

    def test_small_and_slender_slugs(self):
        tp, _op, _s = run(drawing(square(40, 15, 2, 2), thickness=1.0))           # petite et plate : elle tombe
        #                                                                           (1,42 mm de côté, 1 d'épaisseur)
        self.assertEqual(chutes(tp)[0]['risque'], 'faible', chutes(tp)[0])
        self.assertEqual(tp.zones, [])
        tp, _op, _s = run(drawing(square(40, 15, 30, 6)))                         # plus haute que large
        self.assertEqual(chutes(tp)[0]['risque'], 'fort')
        tp, _op, _s = run(drawing(square(40, 15, 1.5, 1.5)))                      # petite (0,85 mm²) même haute :
        self.assertEqual(chutes(tp)[0]['risque'], 'faible')                       # pas de fenêtre à chaque calcul
        self.assertEqual(tp.zones, [])
        tp, _op, _s = run(drawing(square(40, 15, 3, 3)))                          # 2,42 mm, 5,9 mm² : plus haute
        self.assertEqual(chutes(tp)[0]['risque'], 'fort')                         # que large, elle peut basculer
        self.assertIn('plus haute que large', chutes(tp)[0]['raisons'][0])

    def test_held_piece_is_the_one_at_the_stock_edge(self):
        d = drawing(square(1, 1, 98, 48))                                         # brut à peine plus grand
        tp, _op, _s = run(d, side='exterieur')
        ch = chutes(tp)
        self.assertEqual([c['genre'] for c in ch], ['pièce'])                     # la pièce tombe, le cadre reste
        self.assertGreater(ch[0]['aire'], 4000)
        tp2, _op, _s = run(d, side='exterieur', bride=[50, 25])                   # bridée dans la pièce : le cadre
        self.assertLess(chutes(tp2)[0]['aire'], 400)                              # tombe (le point bridé d'abord)

    def test_open_contour_inside_a_closed_one_is_cut_first(self):
        d = drawing(square(30, 10, 40, 30), ([(45, 25), (55, 25)], False))        # le carré d'abord dans le dessin
        tp, _op, _s = run(d, side='exterieur')
        self.assertEqual([c['ferme'] for c in cycle(tp)['contours']], [False, True])   # le trait dedans d'abord


class Angles(unittest.TestCase):

    def test_minimal_taper(self):
        W = edm()
        self.assertAlmostEqual(W.min_taper(0.29, 10, 'coincee', 0.5), math.degrees(math.asin(0.29 / 5)))   # exact :
        self.assertAlmostEqual(W.min_taper(0.29, 10, 'libre'), math.degrees(math.asin(0.029)))   # h × sin(a) = k
        self.assertGreater(W.min_taper(0.29, 10, 'coincee', 0.5), math.degrees(math.atan(0.29 / 5)))
        self.assertEqual(W.min_taper(0.29, 0), 0.0)
        self.assertEqual(W.min_taper(20, 10), 90.0)                               # impossible : 90°

    def test_proposal_side_and_uv(self):
        tp, _op, _s = run(drawing(square(40, 15, 20, 20)))
        t = chutes(tp)[0]['inclinaison']
        a = math.degrees(math.asin(0.29 / 5))
        self.assertAlmostEqual(t['minimal'], a)
        self.assertEqual(t['angle'], -math.ceil(a * 100) / 100)                  # chute à gauche : fil à droite
        self.assertEqual((t['code'], t['cote'], t['retenue']), ('G52', 'droite', 'coincee'))
        self.assertAlmostEqual(t['uv'], 30 * math.tan(math.radians(abs(t['angle']))))   # guides : épaisseur + 20
        tp, _op, _s = run(drawing(square(40, 15, 20, 20)), retenue='libre')
        t = chutes(tp)[0]['inclinaison']
        self.assertEqual(t['code'], 'G51')
        self.assertAlmostEqual(t['minimal'], math.degrees(math.asin(0.029)))

    def test_applied_taper_holds_the_slug(self):
        W = edm()
        tp, op, s = run(drawing(square(40, 15, 20, 20)))
        W.apply_taper(op, chutes(tp)[0]['inclinaison'])
        self.assertEqual(W.params_of(op)['inclinaison'], 'constante')
        self.assertEqual(op.params['inclinaison'], W.CHOICE_LABELS['inclinaison']['constante'])   # comme le formulaire
        tp2 = strategies.compute(drawing(square(40, 15, 20, 20)), s, op)
        self.assertEqual(chutes(tp2)[0]['risque'], 'faible')
        self.assertIn('coincée', chutes(tp2)[0]['raisons'][0])
        self.assertEqual(tp2.zones, [])
        self.assertAlmostEqual(cycle(tp2)['reglages']['uv'], chutes(tp)[0]['inclinaison']['uv'])

    def test_settings_read_from_the_form_labels_and_bounded(self):
        W = edm()
        L = W.CHOICE_LABELS
        op = model.Operation(kind='fil_edm', params={'compensation': L['compensation']['calcul'], 'passes': 40,
                                                     'inclinaison': 'inconnue', 'angle': -120, 'fil': -1})
        p = W.params_of(op)
        self.assertEqual((p['compensation'], p['passes'], p['inclinaison']), ('calcul', 9, 'aucune'))
        self.assertEqual((p['angle'], p['fil']), (-89.0, 0.0))
        self.assertEqual([f[0] for f in W.FORM_FIELDS if f[2] == 'choice'], list(W.CHOICES))

    def test_constant_taper_uv(self):
        W = edm()
        self.assertAlmostEqual(W.uv_constant(1.0, 30.0), 30 * math.tan(math.radians(1.0)))
        pts = [(0, 0), (10, 0), (20, 0), (20, 20), (0, 20), (0, 0)]
        uv = W.taper_uv(pts, 1.0, 30.0)
        m = 30 * math.tan(math.radians(1.0))
        self.assertAlmostEqual(uv[1][0], 0.0)                                     # vers +x : la gauche est +y
        self.assertAlmostEqual(uv[1][1], m)
        self.assertAlmostEqual(W.taper_uv(pts, -1.0, 30.0)[1][1], -m)

    def test_upper_and_lower_contours_uv(self):
        W = edm()
        pair = W.pair_contours(square(0, 0, 20, 20)[0] + [(0, 0)], square(1, 1, 18, 18)[0] + [(1, 1)], True)
        self.assertEqual(pair[0], (0.0, 0.0, 1.0, 1.0))
        self.assertEqual(len(pair), 5)
        self.assertEqual(W.prog_points(pair, 10.0, 30.0, 0.0)[0], (0.0, 0.0, 3.0, 3.0))
        x, y, u, v = W.prog_points(pair, 10.0, 30.0, 5.0)[0]                    # plan de programmation à mi-hauteur
        self.assertEqual((x, y, u, v), (0.5, 0.5, 3.0, 3.0))
        tri = W.pair_contours([(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)],
                              [(0, 0), (10, 0), (5, 10), (0, 0)], True)          # 4 et 3 sommets : à la même fraction
        self.assertEqual(len(tri), 7)                                             # 0, 1/4, …, 1 : le premier répété
        self.assertEqual(tri[0], tri[-1])

    def test_upper_and_lower_contours_in_the_operation(self):
        d = drawing(square(40, 15, 20, 20), square(41, 16, 18, 18))
        bas, haut = d.layers[0].items
        tp, _op, _s = run(d, inclinaison='haut_bas', bas=bas.id, haut=haut.id, guides=30)
        uv = [tuple(round(v, 6) for v in q[2:]) for b in cycle(tp)['blocs'] if b['op'] == 'coupe' for q in b['pts']]
        self.assertIn((3.0, 3.0), uv)                                             # le coin bas-gauche
        self.assertIn((-3.0, -3.0), uv)
        self.assertTrue(any('G40' in w for w in tp.warnings))                     # décalage calculé
        self.assertEqual(len(chutes(tp)), 1)
        self.assertFalse(any(w.startswith('BLOQUANT') for w in tp.warnings), tp.warnings)
        self.assertAlmostEqual(cycle(tp)['reglages']['angle_haut_bas'], math.degrees(math.atan(math.sqrt(2) / 10)),
                               places=2)                                          # le coin : 1 mm en X et en Y


class Tabs(unittest.TestCase):

    def test_tab_spot_on_a_straight_segment_far_from_the_entry(self):
        W = edm()
        spot = W.tab_spot(square(0, 0, 20, 20)[0] + [(0, 0)], 1.0)
        self.assertIn((spot['x'], spot['y']), [(20.0, 10.0), (10.0, 20.0)])
        self.assertTrue(spot['droit'])

    def test_applied_tab_holds_the_slug_until_the_stop(self):
        W = edm()
        d = drawing(square(40, 15, 20, 20))
        tp, op, s = run(d)
        prop = chutes(tp)[0]['attache_proposee']
        W.apply_tab(op, prop)
        tp2 = strategies.compute(d, s, op)
        ch = chutes(tp2)
        self.assertEqual(len(ch), 1)
        self.assertTrue(ch[0]['attache'])
        self.assertEqual(ch[0]['risque'], 'faible')
        cy = cycle(tp2)
        self.assertTrue(cy['contours'][0]['attache'])
        self.assertEqual([b['op'] for b in cy['attaches']][:3], ['rapide', 'enfiler', 'arret'])
        start = next(b for b in cy['attaches'] if b.get('role') == 'approche')['pts'][-1]   # le départ du contour
        end = next(b for b in cy['attaches'] if b.get('role') == 'attache')['pts'][-1]
        self.assertAlmostEqual(math.dist(start[:2], end[:2]), 1.0 + 2 * 0.145, places=6)   # matière + 2 rayons
        mid = ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)
        self.assertAlmostEqual(math.dist(mid, (prop['x'], prop['y'])), 0.0, places=6)
        text = robocut().write([tp2], s, title='attache').text
        after = text[text.index('M00'):]                                          # l'attache après l'arrêt, en
        self.assertIn('G01 G42 D1', after)                                        # sens inverse (fil à droite)
        self.assertNotIn('G41', after)


EXPECTED = """%
O0001 (ESSAI)
(VECTORDRIVE - ELECTROEROSION A FIL - A SIMULER AVANT USINAGE)
(PROGRAMME NON ESSAYE SUR LA MACHINE : CODES A VERIFIER)
(FIL 0.250 ETINCELAGE 0.020 SAIGNEE 0.290)
(EPAISSEUR 10.000 PLAN DE PROGRAMMATION 0.000 DISTANCE ENTRE GUIDES 30.000)
(DECALAGES D1 0.1450)
G90
G92 X42.121 Y17.121
(FIL ENFILE AU TROU DE DEPART)
G01 G41 D1 X40.000 Y15.000
G01 X60.000 Y15.000
G01 X60.000 Y35.000
G01 X40.000 Y35.000
G01 X40.000 Y15.000
G01 G40 X42.121 Y17.121
M50
G40 G50
M02
%
"""


class Post(unittest.TestCase):

    def test_simple_program(self):
        tp, _op, s = run(drawing(square(40, 15, 20, 20)))
        res = robocut().write([tp], s, title='Essai')
        self.assertEqual(res.text, EXPECTED)
        self.assertTrue(any('à vérifier sur la machine' in w for w in res.warnings))

    def test_through_post_run_with_the_drawing_origin(self):
        from vectordrive.cam import post
        from vectordrive.plugins import REGISTRY
        R = robocut()
        tp, _op, s = run(drawing(square(40, 15, 20, 20)))
        with mock.patch.dict(REGISTRY.posts, {R.KEY: (R.LABEL, R.write)}):
            res = post.run(R.KEY, [tp], s, title='Essai', origin=(40, 15))
        self.assertIn('G92 X2.121 Y2.121', res.text)
        self.assertIn('G01 G41 D1 X0.000 Y0.000', res.text)
        self.assertIn('G01 X20.000 Y20.000', res.text)

    def test_a_milling_post_leaves_wire_paths_aside(self):
        from tests import _posts
        from vectordrive.cam import post
        tp, _op, s = run(drawing(square(40, 15, 20, 20)))
        with _posts.registered('essai_fraisage'):
            res = post.run('essai_fraisage', [tp], s, title='Essai')
        self.assertNotIn('G1 X60', res.text)
        self.assertTrue(any('pas écrite par ce post-processeur' in w for w in res.warnings), res.warnings)

    def test_constant_taper_codes(self):
        tp, _op, s = run(drawing(square(40, 15, 20, 20)), inclinaison='constante', angle=-1.5)
        text = robocut().write([tp], s).text
        self.assertIn('G01 G41 D1 G52 A1.500 X40.000 Y15.000', text)
        self.assertIn('G01 G40 G50 X42.121 Y17.121', text)
        self.assertIn('(DEPOUILLE 1.500 DEG A DROITE DU SENS DE COUPE, U/V 0.786)', text)
        self.assertNotIn(' U', text.split('G90', 1)[1])                          # la commande calcule U/V

    def test_upper_and_lower_program_writes_u_and_v(self):
        d = drawing(square(40, 15, 20, 20), square(41, 16, 18, 18))
        bas, haut = d.layers[0].items
        tp, _op, s = run(d, inclinaison='haut_bas', bas=bas.id, haut=haut.id, guides=30)
        text = robocut().write([tp], s).text
        self.assertIn('U0.000 V0.000', text.split('G92', 1)[1].splitlines()[0])
        self.assertTrue(any(' U3.000 V3.000' in ln for ln in text.splitlines()), text)
        self.assertNotIn('G41', text)

    def test_skim_passes_and_registers(self):
        tp, _op, s = run(drawing(square(40, 15, 20, 20)), passes=2)
        text = robocut().write([tp], s).text
        self.assertIn('(DECALAGES D1 0.1750 D2 0.1450)', text)
        self.assertEqual(text.count('G01 G41 D2 X60.000 Y15.000'), 1)

    def test_options_and_other_paths(self):
        tp, _op, s = run(drawing(square(40, 15, 20, 20)))
        s.post_options = {'robocut': {'fin': 'M30', 'absolu': False, 'numeroter': True}}
        other = model.Toolpath('x', 't', moves=[model.Move('rapid', 0, 0, 2)], name='Fraisage')
        res = robocut().write([tp, other], s)
        self.assertIn('M30', res.text)
        self.assertIn('G91', res.text)
        self.assertIn('N10 ', res.text)
        self.assertTrue(any('pas écrits' in w for w in res.warnings))

    def test_tabs_in_a_separate_program(self):
        W = edm()
        d = drawing(square(40, 15, 20, 20))
        tp, op, s = run(d, attache_coupe='apart')
        W.apply_tab(op, chutes(tp)[0]['attache_proposee'])
        res = robocut().write([strategies.compute(d, s, op)], s, stem='piece')
        self.assertEqual([f for f, _t in res.files], ['piece.nc', 'piece_attaches.nc'])
        self.assertNotIn('M00', res.files[0][1])
        self.assertIn('M00', res.files[1][1])

    def test_registered_by_a_plugin(self):
        R = robocut()
        api = mock.Mock()
        R.register(api)
        api.add_post.assert_called_once_with('robocut', R.LABEL, R.write)
        self.assertTrue(R.write.wire_edm)


class Review(unittest.TestCase):
    """Relecture : ce qui peut casser le fil ou la pièce bloque l'écriture (« BLOQUANT », reconnu par
    `preflight.safety`, rien d'écrit) ; fin de programme et de cycle propres ; attaches dans le bon ordre."""

    def assertBlocked(self, res, word, s):
        from vectordrive.cam import preflight
        self.assertEqual((res.text, res.files), ('', []))
        self.assertTrue(any(word in w for w in blocking(res.warnings)), res.warnings)
        self.assertTrue(any(word in w for w in preflight.safety(Document(), s, [], res.warnings)))

    # 1. orientation de sortie, mouvements qui ne sont plus ceux du cycle
    def test_output_orientation_blocks(self):
        tp, _op, s = run(drawing(square(40, 15, 20, 20)))
        s.output_orient = 'miroir_y'
        self.assertBlocked(robocut().write([tp], s), 'orientation de sortie', s)

    def test_mirrored_moves_of_a_single_contour_block(self):
        from vectordrive.cam import post
        tp, _op, s = run(drawing(square(40, 15, 20, 20)))
        mirrored = post.oriented([tp], 'miroir_y', (0, 0, 100, 50))[0]          # le carré reste en place, pas
        self.assertBlocked(robocut().write(mirrored, s), 'ne sont plus ceux du calcul', s)   # le trou

    # 2. fin de programme et de cycle : G40 G50, guide haut droit ; contour ouvert incliné enfilé droit
    def test_program_and_tab_cut_end_with_cancelled_compensation(self):
        W = edm()
        d = drawing(square(40, 15, 20, 20))
        tp, op, s = run(d)
        W.apply_tab(op, chutes(tp)[0]['attache_proposee'])
        text = robocut().write([strategies.compute(d, s, op)], s).text
        self.assertTrue(text.endswith('M50\nG40 G50\nM02\n%\n'), text)            # l'attache coupée en G42 D1
        self.assertEqual(text.count('M50\nG40 G50\n'), 2)                         # arrêté devant l'attache, puis
        self.assertNotIn('G40 G50\nG40 G50', text)                                # après elle ; pas deux fois

    def test_upper_and_lower_guide_back_upright_after_each_cut(self):
        W = edm()
        d = drawing(square(40, 15, 20, 20), square(41, 16, 18, 18))
        bas, haut = d.layers[0].items
        tp, op, s = run(d, inclinaison='haut_bas', bas=bas.id, haut=haut.id, guides=30)
        W.apply_tab(op, chutes(tp)[0]['attache_proposee'])
        text = robocut().write([strategies.compute(d, s, op)], s).text
        self.assertEqual(text.count('M50\nG00 U0.000 V0.000\n'), 2, text)         # fil coupé guide penché : redressé
        self.assertTrue(text.endswith('M50\nG00 U0.000 V0.000\nG40 G50\nM02\n%\n'), text)

    def test_open_contour_tilted_is_threaded_upright_before_its_start(self):
        d = drawing(([(0, 10), (30, 10)], False), ([(0, 11), (30, 11)], False))   # depuis le bord de la plaque
        bas, haut = d.layers[0].items
        tp, _op, s = run(d, inclinaison='haut_bas', bas=bas.id, haut=haut.id, guides=30)
        b = cycle(tp)['blocs']
        self.assertEqual([x['op'] for x in b[:2]], ['rapide', 'enfiler'])
        self.assertEqual([round(v, 6) for v in b[0]['pt']], [-3.0, 10.0, 0.0, 0.0])  # 3 mm en amont, fil droit
        approach = next(x for x in b if x.get('role') == 'approche')['pts'][0]
        self.assertEqual([round(v, 6) for v in approach], [0.0, 10.0, 0.0, 3.0])    # il s'incline sur l'approche
        self.assertEqual(blocking(tp.warnings), [])                               # l'approche est hors matière
        text = robocut().write([tp], s).text
        self.assertIn('G92 X-3.000 Y10.000 U0.000 V0.000', text)
        self.assertTrue(text.endswith('M50\nG00 U0.000 V0.000\nG40 G50\nM02\n%\n'), text)

    def test_open_contour_tilted_threaded_in_the_material_blocks(self):
        d = drawing(([(40, 25), (60, 25)], False), ([(40, 26), (60, 26)], False))  # commence dans la plaque
        bas, haut = d.layers[0].items
        tp, _op, s = run(d, inclinaison='haut_bas', bas=bas.id, haut=haut.id, guides=30)
        self.assertTrue(any('traverse de la matière' in w and 'X 37.00 Y 25.00' in w for w in blocking(tp.warnings)),
                        tp.warnings)
        self.assertBlocked(robocut().write([tp], s), 'traverse de la matière', s)
        tp, _op, s = run(drawing(([(40, 25), (60, 25)], False)))                  # fil droit : enfilé au point même
        self.assertEqual(blocking(tp.warnings), [])
        self.assertTrue(any('enfilage en X 40.00 Y 25.00, dans la matière' in w for w in tp.warnings), tp.warnings)
        tp, _op, s = run(drawing(([(0, 25), (60, 25)], False)))                   # depuis le bord : rien à dire
        self.assertFalse(any('enfilage' in w for w in tp.warnings), tp.warnings)

    # 3. contours haut et bas : distance entre guides exigée, inclinaison contrôlée
    def test_upper_and_lower_without_guide_distance_blocks(self):
        d = drawing(square(40, 15, 20, 20), square(41, 16, 18, 18))
        bas, haut = d.layers[0].items
        tp, _op, s = run(d, inclinaison='haut_bas', bas=bas.id, haut=haut.id)
        self.assertTrue(any('distance entre les guides' in w for w in blocking(tp.warnings)), tp.warnings)
        self.assertBlocked(robocut().write([tp], s), 'distance entre les guides', s)

    def test_upper_and_lower_too_steep_blocks(self):
        d = drawing(square(40, 15, 20, 20), square(48, 23, 4, 4))                 # 8 mm sur 10 : 38,7° (coins
        bas, haut = d.layers[0].items                                             # 48,5°)
        tp, _op, s = run(d, inclinaison='haut_bas', bas=bas.id, haut=haut.id, guides=30)
        self.assertTrue(any('penche jusqu' in w for w in blocking(tp.warnings)), tp.warnings)
        self.assertBlocked(robocut().write([tp], s), 'inclinaison la plus forte', s)
        tp, _op, s = run(d, inclinaison='haut_bas', bas=bas.id, haut=haut.id, guides=30, angle_max=60)
        self.assertEqual(blocking(tp.warnings), [])
        self.assertTrue(robocut().write([tp], s).text)

    # 4. attache d'un trou dans une pièce sans attache : coupée avant le tour de la pièce
    def test_tab_of_a_hole_cut_before_the_surrounding_contour(self):
        W = edm()
        d = part_with_hole()
        tp, op, s = run(d, side='exterieur')
        self.assertEqual(chutes(tp)[0]['contour'], 1)                             # la chute du trou
        W.apply_tab(op, chutes(tp)[0]['attache_proposee'])
        tp2 = strategies.compute(d, s, op)
        cy = cycle(tp2)
        self.assertEqual([(c['attache'], c['attache_avant']) for c in cy['contours']], [(True, 2), (False, 0)])
        self.assertEqual(cy['attaches'], [])                                      # pas à la fin
        self.assertEqual(blocking(tp2.warnings), [])
        self.assertEqual([(c['genre'], c['attache'], c['risque']) for c in cy['chutes']][0], ('chute', True, 'faible'))
        text = robocut().write([tp2], s).text
        self.assertLess(text.index('M00'), text.index('X70.000'))                 # l'arrêt avant le tour
        self.assertIn('AVANT LE CONTOUR 2', text)
        s.post_options = {}
        op.params = dict(op.params, attache_coupe='apart')                        # « à part » : impossible ici
        tp3 = strategies.compute(d, s, op)
        self.assertEqual(cycle(tp3)['attaches'], [])
        self.assertTrue(any('programme principal' in w for w in tp3.warnings), tp3.warnings)

    # 6. attache qui déplace le départ du Mode Point
    def test_tab_moving_an_imposed_start_is_said(self):
        W = edm()
        d = drawing(square(40, 15, 20, 20))
        d.layers[0].items[0].extra = {'start_xy': [[40.0, 25.0]]}
        tp, op, s = run(d)
        first = next(b for b in cycle(tp)['blocs'] if b.get('role') == 'approche')['pts'][0]
        self.assertEqual([round(v, 3) for v in first[:2]], [40.0, 25.0])          # départ au repère
        W.apply_tab(op, {'x': 60.0, 'y': 25.0, 'longueur': 1.0})
        tp2 = strategies.compute(d, s, op)
        note = next((w for w in tp2.warnings if 'départ imposé' in w), '')
        self.assertIn('(X 40.00 Y 25.00)', note)
        self.assertIn('en X 60.00', note)
        self.assertFalse(note.startswith('BLOQUANT'))

    # 7. registres D numérotés sur tout le programme
    def test_registers_over_the_whole_program(self):
        tpa, _op, s = run(drawing(square(40, 15, 20, 20)), passes=2)              # D 0,175 puis 0,145
        tpb, _op, _s = run(drawing(square(5, 5, 10, 10)), fil=0.3)                # 0,170 : un autre registre
        tpc, _op, _s = run(drawing(square(5, 30, 10, 10)))                        # 0,145 : le même que tpa
        text = robocut().write([tpa, tpb, tpc], s).text
        self.assertIn('(DECALAGES D1 0.1750 D2 0.1450 D3 0.1700)', text)
        self.assertNotIn('D4', text)
        self.assertEqual(text.count('G41 D3'), 1)
        self.assertEqual(text.count('G41 D2'), 2)                                 # reprise de tpa, et tpc

    # 9. dépouille au-delà de la limite : une seule limite, bloquante
    def test_constant_taper_beyond_the_limit_blocks(self):
        tp, _op, s = run(drawing(square(40, 15, 20, 20)), inclinaison='constante', angle=35)
        self.assertTrue(any('35' in w for w in blocking(tp.warnings)), tp.warnings)
        self.assertBlocked(robocut().write([tp], s), 'inclinaison la plus forte', s)
        tp, _op, s = run(drawing(square(40, 15, 20, 20)), inclinaison='constante', angle=35, angle_max=40)
        self.assertIn('G51 A35.000', robocut().write([tp], s).text)
        self.assertNotIn('angle_max', robocut().OPTIONS)


def hole_and_outline():
    """Une pièce 40 × 30 et son trou Ø 10, deux objets (pour deux opérations)."""
    d = Document()
    d.plate = Plate(width=100.0, height=50.0, thickness=10.0)
    outer = Shape(path=geom.Path([geom.polyline(square(30, 10, 40, 30)[0], True)]))
    hole = Shape(path=geom.Path([geom.circle((50, 25), 5)]))
    d.layers[0].items += [outer, hole]
    return d, outer, hole


def compute_all(doc, *ops):
    s = model.CamSetup(operations=list(ops))
    return [strategies.compute(doc, s, op) for op in ops], s


class SecondReview(unittest.TestCase):
    """2e relecture : plusieurs opérations d'électroérosion, export propre à un plugin, parcellisation, doublons."""

    def assertBlocked(self, res, word, s):
        Review.assertBlocked(self, res, word, s)

    def ops(self, first, second):
        edm()
        d, outer, hole = hole_and_outline()
        trous = model.Operation(name='Trous', kind='fil_edm', side='interieur', items=[hole.id])
        tours = model.Operation(name='Tours', kind='fil_edm', side='exterieur', items=[outer.id])
        return d, (trous, tours) if first == 'trous' else (tours, trous)

    # 1. attaches de chaque opération juste après ses contours ; contrôle entre opérations
    def test_tab_of_a_first_operation_cut_before_the_next_operation(self):
        W = edm()
        d, (trous, tours) = self.ops('trous', 'tours')
        tps, s = compute_all(d, trous, tours)
        self.assertEqual(chutes(tps[0])[0]['contour'], 1)
        W.apply_tab(trous, chutes(tps[0])[0]['attache_proposee'])
        tps, s = compute_all(d, trous, tours)
        self.assertTrue(cycle(tps[0])['attaches'])                                # attache « en fin » d'opération
        res = robocut().write(tps, s)
        self.assertEqual(blocking(res.warnings), [])
        self.assertLess(res.text.index('M00'), res.text.index('X70.000'))         # avant le tour (2e opération)

    def test_holes_of_a_later_operation_in_a_part_already_cut_block(self):
        d, (tours, trous) = self.ops('tours', 'trous')
        tps, s = compute_all(d, tours, trous)
        self.assertEqual([blocking(tp.warnings) for tp in tps], [[], []])          # chacune seule est juste
        self.assertBlocked(robocut().write(tps, s), 'tombé à la fin du contour 1 de « Tours »', s)

    def test_part_held_by_a_separate_tab_program_does_not_block(self):
        W = edm()
        d, (tours, trous) = self.ops('tours', 'trous')
        tps, s = compute_all(d, tours, trous)
        W.apply_tab(tours, chutes(tps[0])[0]['attache_proposee'])
        tours.params = dict(tours.params, attache_coupe='apart')                  # tenue pendant le programme
        tps, s = compute_all(d, tours, trous)
        res = robocut().write(tps, s, stem='piece')
        self.assertEqual(blocking(res.warnings), [])
        self.assertEqual(len(res.files), 2)

    def test_same_contour_recut_by_a_second_operation_does_not_block(self):
        edm()
        d, outer, _hole = hole_and_outline()
        a = model.Operation(name='Ebauche', kind='fil_edm', side='interieur', items=[outer.id])
        b = model.Operation(name='Finition', kind='fil_edm', side='interieur', items=[outer.id])
        tps, s = compute_all(d, a, b)
        self.assertEqual(blocking(robocut().write(tps, s).warnings), [])

    # 3e relecture : un seul calcul des chutes sur tout le programme
    def two_ops(self, first, second, **params):
        """Deux opérations sur deux objets : (contours, côté) chacune ; rend (parcours, réglages, opérations)."""
        edm()
        d = Document()
        d.plate = Plate(width=100.0, height=50.0, thickness=10.0)
        ops = []
        for k, ((pts, closed), side) in enumerate((first, second)):
            it = Shape(path=geom.Path([geom.polyline(pts, closed=closed)]))
            d.layers[0].items.append(it)
            ops.append(model.Operation(name=f'Op{k + 1}', kind='fil_edm', side=side, items=[it.id],
                                       params=dict(params) if k == 0 else {}))
        tps, s = compute_all(d, *ops)
        return d, tps, s, ops

    def test_exterior_part_recut_after_it_fell_blocks(self):
        d, tps, s, _ops = self.two_ops((square(40, 15, 20, 20), 'exterieur'), (square(40, 15, 20, 20), 'exterieur'))
        self.assertBlocked(robocut().write(tps, s), 'tombé à la fin du contour 1 de « Op1 »', s)
        d, tps, s, _ops = self.two_ops((square(40, 15, 20, 20), 'interieur'), (square(40, 15, 20, 20), 'interieur'))
        self.assertEqual(blocking(robocut().write(tps, s).warnings), [])          # un trou recoupé : la matière
        #                                                                           tenue est autour

    def test_outer_cut_dropping_parts_held_by_separate_tabs_blocks(self):
        W = edm()
        d, tps, s, ops = self.two_ops((square(40, 15, 20, 20), 'exterieur'), (square(20, 8, 60, 34), 'exterieur'),
                                      attache_coupe='apart')
        W.apply_tab(ops[0], chutes(tps[0])[0]['attache_proposee'])
        tps, s = compute_all(d, *ops)
        self.assertEqual([blocking(tp.warnings) for tp in tps], [[], []])
        self.assertBlocked(robocut().write(tps, s), 'l\'attache du contour 1 est coupé dans un morceau déjà détaché', s)

    def test_parts_cut_in_a_piece_parted_by_an_earlier_open_cut_block(self):
        d, tps, s, _ops = self.two_ops((([(-5, 20), (105, 20)], False), 'interieur'),
                                       (square(40, 5, 10, 10), 'exterieur'))
        self.assertBlocked(robocut().write(tps, s), 'tombé à la fin du contour 1 de « Op1 »', s)

    def test_wire_edm_split_over_several_programs_blocks(self):
        from vectordrive.cam import post
        d, (trous, tours) = self.ops('trous', 'tours')
        tps, s = compute_all(d, trous, tours)
        s.program_group = 'parcours'
        groups = post.program_groups(tps, 'parcours')                             # un programme par opération
        self.assertEqual(len(groups), 2)
        self.assertBlocked(robocut().write(groups[0][1], s), 'plusieurs programmes', s)
        self.assertFalse(any('plusieurs programmes' in w for tp in tps for w in tp.warnings))   # des copies

    # 4e relecture : programmes répartis seulement s'ils le sont vraiment
    def test_one_plan_or_paths_off_do_not_block(self):
        from vectordrive.cam import post
        d, (trous, tours) = self.ops('trous', 'tours')
        tps, s = compute_all(d, trous, tours)
        mill = model.Toolpath('x', 't', moves=[model.Move('feed', 0, 0, 0), model.Move('feed', 1, 0, 0)], name='M')
        s.program_group = 'plan'                                                  # l'électroérosion sur un plan,
        groups = post.program_groups(tps + [mill], 'plan', lambda tp: 'P2' if tp is mill else 'P1')   # un fraisage
        self.assertEqual([len(part) for _sfx, part in groups], [2, 1])            # sur un autre
        self.assertEqual(blocking(robocut().write(groups[0][1], s).warnings), [])
        s.program_group = 'parcours'                                              # « Tours » à l'arrêt : la liste
        groups = post.program_groups(tps[:1], 'parcours')                         # écrite n'a que « Trous »
        self.assertEqual(blocking(robocut().write(groups[0][1], s).warnings), [])

    def test_blocking_warnings_first(self):
        from vectordrive.cam import post
        from vectordrive.plugins import REGISTRY
        R = robocut()
        tp, _op, s = run(drawing(square(40, 15, 20, 20), thickness=0.0), inclinaison='constante', angle=35)
        self.assertTrue(any('épaisseur non donnée' in w for w in tp.warnings))    # un avertissement ordinaire, que
        with mock.patch.dict(REGISTRY.posts, {R.KEY: (R.LABEL, R.write)}):       # `check` met d'abord
            res = post.run(R.KEY, [tp], s)
        self.assertTrue(any('épaisseur non donnée' in w for w in res.warnings), res.warnings)
        self.assertTrue(res.warnings[0].startswith('BLOQUANT'), res.warnings)

    # 2. export propre à un plugin : sans les parcours d'électroérosion
    def test_plugin_export_gets_no_wire_paths(self):
        from PySide6.QtWidgets import QApplication
        from vectordrive import plugins
        from vectordrive.cam.post import PostResult
        QApplication.instance() or QApplication([])
        tp, _op, _s = run(drawing(square(40, 15, 20, 20)))
        mill = model.Toolpath('x', 't', moves=[model.Move('feed', 0, 0, 0), model.Move('feed', 1, 0, 0)], name='M')
        r = plugins.REGISTRY
        saved = dict(r.posts), dict(r.post_exports)
        done = []
        api = plugins.Api(r, plugins.PluginInfo('essai', 'essai'))
        api.add_post('essai_fil', 'Essai', lambda tps, setup, **k: PostResult('G1\n', [], '.nc'))
        api.add_post_export('essai_fil', lambda cp, tps, s: done.append([t.name for t in tps]) or True)
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            cp = w.cam_panel
            cp.set_post('essai_fil')
            with mock.patch.object(cp, 'current_paths', lambda: [mill, tp]), \
                    mock.patch.object(cp, 'checked_paths', lambda: [mill, tp]), \
                    mock.patch.object(cp, 'refresh_dates', lambda: 0), \
                    mock.patch.object(cp, 'preflight', lambda *a, **k: True), \
                    mock.patch('PySide6.QtWidgets.QFileDialog.getSaveFileName',
                               side_effect=AssertionError('pas de boîte ordinaire')):
                cp.post_process()
            self.assertEqual(done, [['M']])
        finally:
            r.posts, r.post_exports = saved
            w.modified = False
            w.close()

    # remarques : parcellisation refusée, pas de doublon des bloquants
    def test_no_panelling_with_wire_edm(self):
        from PySide6.QtWidgets import QApplication
        QApplication.instance() or QApplication([])
        tp, _op, _s = run(drawing(square(40, 15, 20, 20)))
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            cp = w.cam_panel
            told = []
            with mock.patch.object(cp, 'current_paths', lambda: [tp]), \
                    mock.patch('vectordrive.ui.panels_dialog.PanelsDialog', side_effect=AssertionError('panneaux')), \
                    mock.patch('PySide6.QtWidgets.QMessageBox.information', lambda *a: told.append(a[2])):
                cp.post_panels()
            self.assertTrue(told and 'électroérosion à fil' in told[0], told)
        finally:
            w.modified = False
            w.close()

    def test_blocking_warning_not_repeated_by_the_common_checks(self):
        from vectordrive.cam import post
        from vectordrive.plugins import REGISTRY
        R = robocut()
        tp, _op, s = run(drawing(square(40, 15, 20, 20)), inclinaison='constante', angle=35)
        with mock.patch.dict(REGISTRY.posts, {R.KEY: (R.LABEL, R.write)}):
            res = post.run(R.KEY, [tp], s)
        self.assertEqual(res.text, '')
        self.assertEqual(sum('35' in w and 'BLOQUANT' in w for w in res.warnings), 1, res.warnings)
        self.assertTrue(any(w.startswith('BLOQUANT : « Fil »') for w in res.warnings), res.warnings)


def naive_pieces(stock, steps, kerf_w, held_point=None):
    """Le calcul d'avant (la matière refaite à chaque étape depuis le brut) : la référence du calcul incrémental."""
    from shapely.geometry import LineString, Point
    from shapely.ops import unary_union
    r, min_area = kerf_w / 2, kerf_w * kerf_w
    held, removed, out = stock, None, []
    hp = Point(*held_point) if held_point else None
    for k, st in enumerate(steps):
        cut = unary_union([LineString(ln).buffer(r, quad_segs=4) for ln in st['lines']])
        removed = cut if removed is None else removed.union(cut)
        rest = stock.difference(removed)
        comps = [c for c in getattr(rest, 'geoms', [rest]) if c.area >= min_area and not held.is_empty and
                 c.intersection(held).area > 0.5 * c.area]
        if not comps:
            held = stock.difference(stock)
            continue
        new = next((c for c in comps if hp is not None and c.distance(hp) <= r), None)
        if new is None:
            at_edge = [c for c in comps if c.distance(stock.boundary) <= 1e-6]
            new = max(at_edge or comps, key=lambda c: c.area)
        out += [(k, c.area) for c in comps if c is not new]
        held = new
    return sorted(out), held.area


def ring(x, y, w, h):
    return [(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)]


def holes_plate(n, cols=20):
    """Une plaque de `n` trous Ø 4 (un objet) dans une pièce (un autre objet) : deux opérations, trous puis tour."""
    rows = (n + cols - 1) // cols
    d = Document()
    d.plate = Plate(width=20 + cols * 15.0, height=20 + rows * 15.0, thickness=10.0)
    holes = Shape(path=geom.Path([geom.circle((17.5 + 15 * (i % cols), 17.5 + 15 * (i // cols)), 2.0)
                                  for i in range(n)]))
    outer = Shape(path=geom.Path([geom.polyline(ring(5, 5, 10 + cols * 15, 10 + rows * 15)[:-1], closed=True)]))
    d.layers[0].items += [holes, outer]
    return d, [model.Operation(name='Trous', kind='fil_edm', side='interieur', items=[holes.id]),
               model.Operation(name='Tour', kind='fil_edm', side='exterieur', items=[outer.id])]


class FourthReview(unittest.TestCase):
    """4e relecture : chutes en temps linéaire, attache courte, programmes vraiment répartis, brut de tout le
    programme."""

    def test_incremental_pieces_match_the_full_computation(self):
        W = edm()
        stock = box(0, 0, 120, 60)
        steps = [{'lines': [ring(8 + 12 * i, 8 + 12 * j, 4, 4)]} for i in range(9) for j in range(3)]   # 0-26
        steps += [{'lines': [ring(5, 30, 26, 10)]},                                 # 27 : un cadre autour de trous
                  {'lines': [ring(14, 37, 2, 2)]},                                  # 28 : un trou dans le cadre tombé
                  {'lines': [[(60, 25), (60, 40)]]},                                # 29 : un trait qui ne sépare rien
                  {'lines': [[(-5, 50), (125, 50)]]},                               # 30 : de bord à bord
                  {'lines': [ring(70, 30, 6, 6)]}, {'lines': [ring(70, 52, 3, 3)]},   # 31 en bas, 32 en haut
                  {'lines': [[(100, -5), (100, 65)]]}]                              # 33 : encore de bord à bord
        # point bridé : aucun (le bas reste, puis la gauche), à droite en bas, dans la bande du haut (le bas tombe)
        for hp, bad in ((None, [28, 32]), ((110, 30), [28, 32]), ((50, 55), [28, 31, 33])):
            pieces, problems, held = W.find_pieces(stock, steps, 0.3, hp)
            ref, ref_held = naive_pieces(stock, steps, 0.3, hp)
            got = sorted((pc['step'], pc['poly'].area) for pc in pieces)
            self.assertEqual([k for k, _a in got], [k for k, _a in ref], hp)
            for (_k, a), (_k2, b) in zip(got, ref):
                self.assertAlmostEqual(a, b, delta=1e-6)
            self.assertAlmostEqual(held.area, ref_held, delta=1e-6)
            self.assertEqual([p[0] for p in problems], bad, hp)                     # coupes dans un morceau tombé

    def test_hundreds_of_holes_in_reasonable_time(self):
        import time
        edm()
        d, ops = holes_plate(300)
        t0 = time.perf_counter()
        tps, s = compute_all(d, *ops)
        res = robocut().write(tps, s)
        again = robocut().write(tps, s)                                           # aperçu, essai, écriture
        took = time.perf_counter() - t0
        self.assertEqual(blocking(res.warnings), [])
        self.assertEqual(len(chutes(tps[0])), 300)
        self.assertEqual([c['genre'] for c in chutes(tps[1])], ['pièce'])
        self.assertEqual(again.text, res.text)
        self.assertLess(took, 20.0)                                               # ≈ 2 s seul, avant ≈ 40 s

    def test_whole_program_check_done_once_per_computation(self):
        W = edm()
        d, ops = holes_plate(10)
        tps, s = compute_all(d, *ops)
        with mock.patch.object(W, 'find_pieces', wraps=W.find_pieces) as fp:
            robocut().write(tps, s)
            robocut().write(tps, s)
            self.assertEqual(fp.call_count, 1)
            tps, s = compute_all(d, *ops)                                          # recalcul : refait
            robocut().write(tps, s)
            self.assertEqual(fp.call_count, 1 + 2 + 1)                            # (et les deux calculs)

    def test_short_tab_on_a_part_carried_away_by_an_outer_cut_blocks(self):
        W = edm()
        d, tps, s, ops = SecondReview.two_ops(self, (square(40, 15, 20, 20), 'exterieur'),
                                              (square(20, 8, 60, 34), 'exterieur'), attache_coupe='apart')
        W.apply_tab(ops[0], dict(chutes(tps[0])[0]['attache_proposee'], longueur=0.05))   # plus courte qu'une
        tps, s = compute_all(d, *ops)                                                       # saignée (0,29)
        self.assertTrue(cycle(tps[0])['attaches'])
        self.assertBlocked(robocut().write(tps, s), 'l\'attache du contour 1 est coupé dans un morceau déjà détaché', s)

    def assertBlocked(self, res, word, s):
        Review.assertBlocked(self, res, word, s)

    def test_whole_program_stock_is_the_union_of_the_operations_stocks(self):
        W = edm()
        d = Document()
        d.plate = Plate(width=0.0, height=0.0, thickness=10.0)                    # pas de plaque : la boîte des
        items = [Shape(path=geom.Path([geom.polyline(square(x, 10, 20, 20)[0], closed=True)])) for x in (10, 60)]
        d.layers[0].items += items                                                # contours de chaque opération
        ops = [model.Operation(name=f'Op{k}', kind='fil_edm', side='exterieur', items=[it.id])
               for k, it in enumerate(items, 1)]
        tps, s = compute_all(d, *ops)
        with mock.patch.object(W, 'find_pieces', wraps=W.find_pieces) as fp:
            robocut()._WHOLE.clear()
            res = robocut().write(tps, s)
        self.assertAlmostEqual(fp.call_args_list[0][0][0].area, 2 * 30 * 30)
        self.assertEqual(blocking(res.warnings), [])                              # deux bruts séparés : chacun
        #                                                                           tenu à part

    # 5e relecture : bruts qui ne se touchent pas
    def test_separate_stocks_of_different_sizes_do_not_block(self):
        d = Document()
        d.plate = Plate(width=0.0, height=0.0, thickness=10.0)                    # boîtes : 60 × 60 et 20 × 20
        big = Shape(path=geom.Path([geom.polyline(square(0, 0, 50, 50)[0], True), geom.circle((25, 25), 8)]))
        small = Shape(path=geom.Path([geom.polyline(square(200, 20, 10, 10)[0], True)]))
        d.layers[0].items += [big, small]
        for order in ((big, small), (small, big)):
            ops = [model.Operation(name=f'Op{k}', kind='fil_edm', side='exterieur', items=[it.id])
                   for k, it in enumerate(order, 1)]
            tps, s = compute_all(d, *ops)
            self.assertEqual([blocking(tp.warnings) for tp in tps], [[], []])
            cy = cycle(tps[0] if order[0] is big else tps[1])
            self.assertEqual([c['cote'] for c in cy['contours']], ['interieur', 'exterieur'])   # trou puis tour
            res = robocut().write(tps, s)
            self.assertEqual(blocking(res.warnings), [], order)
            self.assertTrue(res.text)

    def test_find_pieces_on_separate_stocks(self):
        from shapely.geometry import MultiPolygon
        W = edm()
        stock = MultiPolygon([box(0, 0, 60, 60), box(195, 15, 215, 35)])
        steps = [{'lines': [ring(17, 17, 16, 16)]}, {'lines': [ring(5, 5, 50, 50)]},   # trou puis tour dans la
                 {'lines': [ring(200, 20, 10, 10)]}, {'lines': [ring(20, 20, 4, 4)]}]   # 1re, tour dans la 2de,
        history = []                                                                    # puis recoupe du trou
        pieces, problems, held = W.find_pieces(stock, steps, 0.3, history=history)
        self.assertEqual([pc['step'] for pc in pieces], [0, 1, 2])
        self.assertEqual(problems, [(3, 0)])                                       # dans la chute du trou
        self.assertEqual(len(history), 4)
        self.assertAlmostEqual(held.area, 60 * 60 - 50.3 * 50.3 + 20 * 20 - 10.3 * 10.3, delta=0.5)


class Window(unittest.TestCase):

    def test_operation_computed_in_the_panel_and_warning_shown(self):
        edm()
        from PySide6.QtWidgets import QApplication
        QApplication.instance() or QApplication([])
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            doc = w.canvas.doc
            doc.plate = Plate(width=100.0, height=50.0, thickness=10.0)
            pts, closed = square(40, 15, 20, 20)
            doc.layers[0].items.append(Shape(path=geom.Path([geom.polyline(pts, closed=closed)])))
            op = model.Operation(name='Fil', kind='fil_edm', side='interieur')
            model.store(doc, model.CamSetup(operations=[op]))
            tps = w.cam_panel.compute()
            self.assertEqual(len(tps), 1)
            self.assertTrue(any('chute 1' in x for x in tps[0].warnings), tps[0].warnings)
            self.assertTrue(any(z.get('kind') == 'chute' for t, _c in w.canvas.toolpaths for z in t.zones))
            self.assertIsNone(getattr(w.cam_panel, 'zones_box', None))            # pas « Îles gardées »
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
