"""Round 1113 (demande du 20/11) : « parcours prismatique : soit extérieur contour (relief) soit intérieur (creux) avec
respect parité englobant » — « relief = outil dehors (sur 0.968.0 c'est toujours dedans quel que soit coche case en
creux) ». En relief, l'outil reste hors des formes pair-impair : le trou d'un O en est, l'îlot dans ce trou n'en est pas."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1113.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from shapely.geometry import Point, Polygon, box  # noqa: E402

from vectordrive.cam import advanced as A  # noqa: E402
from vectordrive.cam import model as M  # noqa: E402
from vectordrive.cam import strategies as S  # noqa: E402
from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Document, Layer, Plate, Shape  # noqa: E402

TAN = math.tan(math.radians(15))
RT = 0.1                                                                  # demi-troncature du cône des essais
BEFORE = 'avant : le relief gardait l’outil dans les lettres, case « En creux » ou non'


def P(*pts):
    return geom.polyline(list(pts), closed=True)


def doc_of(*paths):
    doc = Document()
    doc.plate = Plate(width=200.0, height=100.0)
    doc.layers = [Layer(name='A', items=[Shape(path=geom.Path(list(p))) for p in paths])]
    return doc


def compute(doc, *, depth=1.0, step=0.5, previous=None, more_tools=(), **kw):
    setup = M.setup_of(doc)
    cone = M.CamTool(name='c', kind='conique', diameter=8.0, tip=0.2, angle=30.0)
    setup.tools.append(cone)
    setup.tools += list(more_tools)
    op = M.Operation(kind='prismatique', tool_id=cone.id, depth=depth, step_down=step, **kw)
    setup.operations.append(op)
    M.store(doc, setup)
    token = S._PREVIOUS.set(list(previous or []))
    try:
        return S.compute(doc, setup, op, (0.0, 0.0))
    finally:
        S._PREVIOUS.reset(token)


def cuts(tp):
    return [m for m in tp.moves if m.kind != 'rapid' and m.z < -1e-6]


O = (geom.circle((50, 50), 10), geom.circle((50, 50), 5))                # un O : l'anneau de 5 à 10
O_RING = Point(50, 50).buffer(10, quad_segs=64).difference(Point(50, 50).buffer(5, quad_segs=64))
FRAME = (P((100, 20), (160, 20), (160, 80), (100, 80)), P((120, 40), (140, 40), (140, 60), (120, 60)))
FRAME_BAND = box(100, 20, 160, 80).difference(box(120, 40, 140, 60))     # le cadre ; le carré dedans en est le trou


class Relief(unittest.TestCase):
    def check_outside(self, tp, shape):
        """Le centre de l'outil jamais dans la forme, ni plus près d'elle que le flanc à sa cote (troncature/2 + |z|·tan) :
        le cône n'entame pas le dessus."""
        cs = cuts(tp)
        self.assertTrue(cs)
        for m in cs:
            self.assertGreater(shape.distance(Point(m.x, m.y)), RT - m.z * TAN - 0.01, (m.x, m.y, m.z))
        return cs

    def test_an_o_hole_and_outside(self):
        tp = compute(doc_of(O))
        cs = self.check_outside(tp, O_RING)
        self.assertTrue(any(Point(m.x, m.y).within(Point(50, 50).buffer(5)) for m in cs), 'le trou du O')
        self.assertTrue(any(Point(50, 50).distance(Point(m.x, m.y)) > 10 for m in cs), 'le tour du O')
        self.assertTrue(any('l\'outil reste hors des formes' in w for w in tp.warnings))
        old = compute(doc_of(O), prism_rule=882)
        self.assertTrue(any(O_RING.contains(Point(m.x, m.y)) for m in cuts(old)), BEFORE)

    def test_parity_frame_and_square(self):
        tp = compute(doc_of(FRAME))
        cs = self.check_outside(tp, FRAME_BAND)
        self.assertTrue(any(Point(m.x, m.y).within(box(120, 40, 140, 60)) for m in cs), 'le carré, trou du cadre')
        self.assertTrue(any(not Point(m.x, m.y).within(box(100, 20, 160, 80)) for m in cs), 'le tour du cadre')
        self.assertFalse(any(FRAME_BAND.contains(Point(m.x, m.y)) for m in cs))
        island = compute(doc_of(FRAME + (P((126, 46), (134, 46), (134, 54), (126, 54)),)))   # un îlot dans le trou : une
        band2 = FRAME_BAND.union(box(126, 46, 134, 54))                                     # forme de plus
        self.check_outside(island, band2)

    def test_flank_offsets_and_order(self):
        tp = compute(doc_of([P((20, 20), (40, 20), (40, 40), (20, 40))]), depth=1.0, step=0.5)
        sq = box(20, 20, 40, 40)
        levels = sorted({round(m.z, 6) for m in cuts(tp)}, reverse=True)
        self.assertEqual(levels, [-0.5, -1.0])                          # de la surface vers le fond, pas de passe à Z = 0
        zs = [m.z for m in cuts(tp)]
        self.assertEqual(zs, sorted(zs, reverse=True))
        for m in cuts(tp):                                               # en onglet : à troncature/2 + |z|·tan des côtés
            self.assertAlmostEqual(max(abs(m.x - 30), abs(m.y - 30)) - 10, RT - m.z * TAN, 3)
            self.assertFalse(sq.contains(Point(m.x, m.y)))

    def test_lateral_and_overflow(self):
        sq = [P((20, 20), (40, 20), (40, 40), (20, 40))]
        plain = compute(doc_of(sq), depth=1.0, step=0.5)
        lat = compute(doc_of(sq), depth=1.0, step=0.5, prism_lateral=True)
        def offs(tp, z):
            return sorted({round(max(abs(m.x - 30), abs(m.y - 30)) - 10, 4) for m in cuts(tp) if abs(m.z - z) < 1e-6})
        self.assertEqual(offs(plain, -0.5), [round(RT + 0.5 * TAN, 4)])
        self.assertEqual(offs(lat, -0.5), [round(RT + 0.5 * TAN, 4), round(RT + TAN, 4)])   # jusqu'au flanc du fond
        ext = compute(doc_of(sq), depth=1.0, step=0.5, extension=1.0)
        bottom = offs(ext, -1.0)
        self.assertAlmostEqual(bottom[0], RT + TAN, 4)
        self.assertGreater(bottom[-1], RT + TAN + 0.5)
        self.assertLessEqual(bottom[-1], RT + TAN + 1.0 + 1e-6)
        self.assertEqual(offs(ext, -0.5), [round(RT + 0.5 * TAN, 4)])   # au fond seulement

    def test_overflow_round_at_a_sharp_corner(self):
        spike = [P((20, 20), (60, 23), (20, 26))]                        # une pointe d'environ 8,6°
        shape = Polygon([(20, 20), (60, 23), (20, 26)])
        plain = {(round(m.x, 6), round(m.y, 6)) for m in cuts(compute(doc_of(spike), depth=1.0, step=1.0))}
        ext = [m for m in cuts(compute(doc_of(spike), depth=1.0, step=1.0, extension=1.0))
               if (round(m.x, 6), round(m.y, 6)) not in plain]
        self.assertTrue(ext)
        for m in ext:                                                    # arrondi : jamais au-delà du Débordement (en
            self.assertLess(shape.distance(Point(m.x, m.y)), RT + TAN + 1.0 + 0.01)   # onglet : jusqu'à 20·d)

    def test_climb_keeps_the_letter_on_the_right(self):
        def area(climb):
            tp = compute(doc_of([P((20, 20), (40, 20), (40, 40), (20, 40))]), depth=0.5, step=0.5, climb=climb)
            pts = [(m.x, m.y) for m in cuts(tp)]
            return sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(pts, pts[1:] + pts[:1])) / 2
        self.assertLess(area(True), 0)                                   # en avalant : sens horaire, la lettre à droite
        self.assertGreater(area(False), 0)

    def test_depth_must_be_given(self):
        tp = compute(doc_of(O), depth=0.0)
        self.assertEqual(cuts(tp), [])
        self.assertTrue(any('donnez la profondeur' in w for w in tp.warnings))
        old = compute(doc_of(O), depth=0.0, prism_rule=882)              # le relief d'avant : celle de l'arête
        self.assertTrue(cuts(old))

    def test_hollow_unchanged(self):
        for shapes in ((O,), (FRAME,)):
            new = compute(doc_of(*shapes), prism_hollow=True)
            old = compute(doc_of(*shapes), prism_hollow=True, prism_rule=882)
            self.assertEqual([(m.kind, m.x, m.y, m.z) for m in new.moves], [(m.kind, m.x, m.y, m.z) for m in old.moves])

    def test_old_rule_kept(self):
        self.assertEqual(M.Operation().prism_rule, A.PRISM_OUTSIDE)
        self.assertEqual(M.Operation.from_dict({'kind': 'prismatique'}).prism_rule, 0)   # enregistrée avant 882
        d = M.Operation(kind='prismatique', prism_rule=882).to_dict()
        self.assertEqual(M.Operation.from_dict(d).prism_rule, 882)       # avant 1113 : son relief, dans les lettres


LETTERS = box(20, 20, 30, 30).union(box(32, 20, 42, 30))               # deux carrés à 2 mm l'un de l'autre


def previous(setup_tools, depth=2.0):
    """La fraise Ø6 d'avant : un tour autour des deux carrés, à 3 mm, au fond."""
    flat = M.CamTool(name='f6', kind='fraise', diameter=6.0)
    setup_tools.append(flat)
    tp = M.Toolpath(op_id='avant', tool_id=flat.id)
    ring = list(LETTERS.buffer(3.0, quad_segs=16).exterior.coords)
    tp.moves.append(M.Move('rapid', ring[0][0], ring[0][1], 5.0))
    tp.moves.append(M.Move('plunge', ring[0][0], ring[0][1], -depth))
    tp.moves += [M.Move('feed', x, y, -depth) for x, y in ring[1:]]
    tp.moves.append(M.Move('rapid', ring[-1][0], ring[-1][1], 5.0))
    return tp, flat


class Rest(unittest.TestCase):
    def doc(self):
        return doc_of([P((20, 20), (30, 20), (30, 30), (20, 30))], [P((32, 20), (42, 20), (42, 30), (32, 30))])

    def test_the_gap_is_cleared_outside_the_flanks(self):
        tools = []
        prev, flat = previous(tools)
        base = compute(self.doc(), depth=2.0, step=1.0, more_tools=[flat])
        rest = compute(self.doc(), depth=2.0, step=1.0, previous=[prev], more_tools=[flat], prism_rest=True)
        gap = box(30.6, 20.0, 31.4, 30.0)                                 # le milieu de l’écart, hors des flancs
        self.assertFalse(any(gap.contains(Point(m.x, m.y)) for m in cuts(base)))
        self.assertTrue(any(gap.contains(Point(m.x, m.y)) for m in cuts(rest)))
        for m in cuts(rest):
            self.assertGreater(LETTERS.distance(Point(m.x, m.y)), RT - m.z * TAN - 0.01, (m.x, m.y, m.z))
        self.assertFalse(any('pour les lettres en relief' in w for w in rest.warnings))

    def test_nothing_before(self):
        base = compute(self.doc(), depth=2.0, step=1.0)
        rest = compute(self.doc(), depth=2.0, step=1.0, prism_rest=True)
        self.assertEqual([(m.kind, m.x, m.y, m.z) for m in rest.moves], [(m.kind, m.x, m.y, m.z) for m in base.moves])
        self.assertTrue(any('rien à reprendre' in w for w in rest.warnings))


class Form(unittest.TestCase):
    def test_ok_in_the_form_takes_the_new_rule(self):
        from PySide6.QtWidgets import QApplication
        from vectordrive.ui import cam_panel as CP
        QApplication.instance() or QApplication([])
        op = M.Operation(kind='prismatique', prism_rule=882)
        d = CP.FieldsDialog(None, 'essai', op)
        self.addCleanup(d.deleteLater)
        self.assertEqual(op.prism_rule, 882)                            # ouverte : rien de changé
        d.apply()
        self.assertEqual(op.prism_rule, A.PRISM_OUTSIDE)
        other = M.Operation(kind='contour', prism_rule=882)
        d2 = CP.FieldsDialog(None, 'essai', other)
        self.addCleanup(d2.deleteLater)
        d2.apply()
        self.assertEqual(other.prism_rule, 882)                         # une autre opération : rien

    def test_a_template_from_before_gives_the_new_rule(self):
        from vectordrive.cam import templates as TPL
        cone = M.CamTool(name='c', kind='conique', diameter=8.0, tip=0.2, angle=30.0)
        old = M.Operation(kind='prismatique', tool_id=cone.id, prism_rule=882)
        tpl = TPL.single(old, cone, 'lettres 1113')
        self.assertEqual(tpl['operations'][0]['prism_rule'], 882)       # enregistré avant 1113
        s, _r = TPL.apply(M.CamSetup(), tpl)
        self.assertEqual([o.prism_rule for o in s.operations], [A.PRISM_OUTSIDE])
        other = TPL.single(M.Operation(kind='contour', prism_rule=882), cone, 'contour 1113')
        s, _r = TPL.apply(M.CamSetup(), other)
        self.assertEqual(s.operations[0].prism_rule, 882)               # une autre opération : rien


if __name__ == '__main__':
    unittest.main()
