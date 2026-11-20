"""Round 1121 (demande du 20/11, 15 h 46) : « prismatique option OffsetXY et si non nul alors proposition de passe de
finition ». Une surépaisseur XY laissée le long des lettres (relief : lettre grossie ; creux : forme rétrécie), la
passe de finition à OffsetXY nul, et dans le formulaire la case proposée (cochée) dès que l'OffsetXY n'est plus nul."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1121.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from shapely.geometry import Point, box  # noqa: E402

from vectordrive.cam import advanced as A  # noqa: E402
from vectordrive.cam import model as M  # noqa: E402
from vectordrive.cam import strategies as S  # noqa: E402
from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Document, Layer, Plate, Shape  # noqa: E402

TAN = math.tan(math.radians(15))
RT = 0.1                                                                  # demi-troncature du cône des essais
OFF = 0.3
BEFORE = 'avant : l’OffsetXY n’existait pas pour les lettres prismatiques'
RECT = box(20, 20, 60, 40)


def doc_of(extra=()):
    doc = Document()
    doc.plate = Plate(width=200.0, height=100.0)
    shapes = []
    for b in (RECT, *extra):
        pts = list(b.exterior.coords)[:-1]
        shapes.append(Shape(path=geom.Path([geom.polyline(pts, closed=True)])))
    doc.layers = [Layer(name='A', items=shapes)]
    return doc


def compute(extra=(), **kw):
    doc = doc_of(extra)
    setup = M.setup_of(doc)
    cone = M.CamTool(name='c', kind='conique', diameter=8.0, tip=0.2, angle=30.0)
    setup.tools.append(cone)
    kw.setdefault('depth', 1.0)
    op = M.Operation(kind='prismatique', tool_id=cone.id, step_down=0.5, **kw)
    setup.operations.append(op)
    M.store(doc, setup)
    token = S._PREVIOUS.set([])
    try:
        return S.compute(doc, setup, op, (0.0, 0.0))
    finally:
        S._PREVIOUS.reset(token)


def cuts(tp, fin=None):
    """Les mouvements sous la surface ; `fin` : ceux d'avant la passe de finition (False) ou depuis (True)."""
    ms = [m for m in tp.moves if m.kind != 'rapid' and m.z < -1e-6]
    k = next((i for i, m in enumerate(ms) if getattr(m, 'fin', False)), len(ms))
    return ms if fin is None else (ms[k:] if fin else ms[:k])


def mgap(ms):
    """Plus petite distance des trajets (segments à une même cote) au bord du rectangle, moins ce que le cône prend à
    leur cote : ≥ 0 hors de la lettre."""
    from shapely.geometry import LineString
    out = []
    for a, b in zip(ms, ms[1:]):
        if abs(a.z - b.z) < 1e-9:
            g = LineString([(a.x, a.y), (b.x, b.y)]) if (a.x, a.y) != (b.x, b.y) else Point(a.x, a.y)
            out.append(RECT.exterior.distance(g) - (RT - a.z * TAN))
    return min(out)


class Relief(unittest.TestCase):
    """Relief, outil hors des formes (règle 1113) : le flanc à la pente de l'outil, plus loin de OffsetXY."""

    def test_offset_leaves_material(self):
        g0 = mgap(cuts(compute()))         # sans OffsetXY : le flanc exact
        self.assertGreater(g0, -0.02)
        tp = compute(stock=OFF)
        cs = cuts(tp)
        self.assertTrue(cs)
        self.assertGreater(mgap(cs), g0 + OFF - 0.02, BEFORE)
        self.assertLess(mgap(cs), g0 + OFF + 0.02)
        self.assertTrue(any('OffsetXY de 0.3 mm' in w for w in tp.warnings))
        self.assertEqual(cuts(tp, fin=True), [], 'pas de finition sans la case')

    def test_finish_pass(self):
        g0 = mgap(cuts(compute()))
        tp = compute(stock=OFF, vcarve_finish=True)
        rough, fin = cuts(tp, fin=False), cuts(tp, fin=True)
        self.assertTrue(rough and fin, BEFORE)
        self.assertGreater(mgap(rough), g0 + OFF - 0.02)
        self.assertAlmostEqual(mgap(fin), g0, 2, 'la finition : le flanc exact, sans entamer la lettre')
        self.assertTrue(rough[-1] is not fin[0] and tp.moves.index(fin[0]) > tp.moves.index(rough[-1]), 'après')
        self.assertAlmostEqual(min(m.z for m in fin), min(m.z for m in rough), 6, 'la même profondeur')

    def test_finish_without_offset_does_nothing_more(self):
        a, b = compute(), compute(vcarve_finish=True)
        self.assertEqual(len(a.moves), len(b.moves))
        self.assertEqual(cuts(b, fin=True), [])

    def test_lateral_passes_not_repeated_in_finish(self):
        tp = compute(stock=OFF, vcarve_finish=True, prism_lateral=True)
        plain = compute(stock=OFF, vcarve_finish=True)
        self.assertEqual(len(cuts(tp, fin=True)), len(cuts(plain, fin=True)), 'la finition : un tour par niveau')


    def test_bottom_band_finished(self):
        """Au fond, l'ébauche passe à OffsetXY de la finition : la bande entre elles, plus large que la pointe,
        reprise par la finition (Débordement depuis la forme exacte) — pas d'arête laissée au pied du flanc."""
        g0 = mgap(cuts(compute()))
        fin = cuts(compute(stock=OFF, vcarve_finish=True), fin=True)
        zb = min(m.z for m in fin)
        bottom = [m for m in fin if abs(m.z - zb) < 1e-9]
        far = max(RECT.exterior.distance(Point(m.x, m.y)) - (RT - m.z * TAN) for m in bottom)
        pitch = max(0.02, 2 * (RT + A.FLAT_RIDGE * TAN))
        self.assertGreater(far, g0 + OFF - pitch - 0.02, 'avant : une arête de matière au pied du flanc')
        self.assertGreater(mgap(bottom), g0 - 0.02)

    def test_bottom_band_reaches_the_corners(self):
        """Le flanc ébauché est en onglet aux coins saillants : la bande du fond aussi, sinon une pointe y reste."""
        for rule, flank in ((1113, RT + 1.0 * TAN), (882, 0.0)):        # le flanc du fond : hors de la lettre ; TE13 : le contour
            fin = cuts(compute(stock=OFF, vcarve_finish=True, prism_rule=rule), fin=True)
            zb = min(m.z for m in fin)
            corner = max(Point(20, 20).distance(Point(m.x, m.y)) for m in fin
                         if abs(m.z - zb) < 1e-9 and m.x < 20 and m.y < 20)
            pitch = max(0.02, 2 * (RT + A.FLAT_RIDGE * TAN))
            reach = (flank + OFF - pitch) * 2 ** 0.5                      # en onglet, sur la bissectrice
            self.assertGreater(corner, reach - 0.05, f'règle {rule} : avant, des anneaux arrondis au coin')

    def test_negative_offset_no_finish(self):
        tp = compute(stock=-0.2, vcarve_finish=True)
        self.assertTrue(cuts(tp))
        self.assertFalse(any('finition' in w for w in tp.warnings), 'pas de finition annoncée')
        self.assertEqual(cuts(tp, fin=True), [], 'OffsetXY négatif : la finition ne couperait que de l’air')


class Hollow(unittest.TestCase):
    """En creux : le centre de l'outil dans la forme, à |z|·tan du bord ; plus loin de OffsetXY."""

    def inner(self, m):
        return RECT.exterior.distance(Point(m.x, m.y)) - (-m.z * TAN)

    def test_offset_shrinks_the_hollow(self):
        exact = cuts(compute(prism_hollow=True))
        self.assertLess(min(self.inner(m) for m in exact), 0.02)
        cs = cuts(compute(prism_hollow=True, stock=OFF))
        self.assertTrue(all(RECT.contains(Point(m.x, m.y)) for m in cs))
        self.assertGreater(min(self.inner(m) for m in cs), OFF - 0.02, BEFORE)

    def test_hollow_finish(self):
        tp = compute(prism_hollow=True, stock=OFF, vcarve_finish=True)
        fin = cuts(tp, fin=True)
        self.assertTrue(fin, BEFORE)
        self.assertLess(min(self.inner(m) for m in fin), 0.02)
        zb = min(m.z for m in fin)
        bottom = [self.inner(m) for m in fin if abs(m.z - zb) < 1e-9]
        pitch = max(0.02, 2 * (RT + A.FLAT_RIDGE * TAN))
        self.assertGreater(max(bottom), OFF - pitch - 0.02, 'la bande du fond reprise')
        self.assertLess(max(bottom), OFF, 'sans repasser l’ébauche')

    def test_narrow_shape_said(self):
        thin = box(80, 20, 80.4, 40)                     # 0,4 mm de large : disparaît à 0,3 mm de chaque côté
        tp = compute(extra=(thin,), prism_hollow=True, stock=OFF)
        self.assertTrue(any('1 forme(s) trop étroite(s)' in w and 'pas usinée' in w for w in tp.warnings))
        tp = compute(extra=(thin,), prism_hollow=True, stock=OFF, vcarve_finish=True)
        self.assertTrue(any('par la finition seulement' in w for w in tp.warnings))
        self.assertTrue(any(thin.contains(Point(m.x, m.y)) for m in cuts(tp, fin=True)))


class TeRule(unittest.TestCase):
    """Le trajet relevé dans TE13 (règle 882), profondeur déduite des lettres : la même avec ou sans OffsetXY."""

    def test_depth_from_the_exact_letters(self):
        a = compute(prism_rule=882, depth=0.0)
        b = compute(prism_rule=882, depth=0.0, stock=OFF, vcarve_finish=True)
        self.assertAlmostEqual(min(m.z for m in cuts(a)), min(m.z for m in cuts(b, fin=False)), 6)
        self.assertAlmostEqual(min(m.z for m in cuts(a)), min(m.z for m in cuts(b, fin=True)), 6)

    def test_too_big_an_offset(self):
        tp = compute(prism_hollow=True, stock=15.0)
        self.assertEqual(cuts(tp), [])
        self.assertTrue(any('trop grand' in w for w in tp.warnings))


class Form(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def open(self, op):
        from vectordrive.ui import cam_panel as CP
        d = CP.FieldsDialog(None, 'essai', op)
        self.addCleanup(d.deleteLater)
        d.show()
        self.app.processEvents()
        return d

    def test_offset_field_and_proposed_finish(self):
        d = self.open(M.Operation(kind='prismatique', name='P'))
        lab, sw = d.rows['stock']
        self.assertTrue(sw.isVisible(), BEFORE)
        self.assertTrue(lab.text().startswith('OffsetXY'))
        fw = d.widgets['vcarve_finish']
        self.assertFalse(fw.isVisible(), 'OffsetXY nul : pas de finition proposée')
        sw.setValue(0.2)
        self.assertTrue(fw.isVisible())
        self.assertTrue(fw.isChecked(), 'non nul : la passe de finition proposée')
        fw.setChecked(False)
        sw.setValue(0.3)
        self.assertFalse(fw.isChecked(), 'décochée : le reste')
        sw.setValue(0.0)
        self.assertFalse(fw.isVisible())
        sw.setValue(0.1)
        self.assertTrue(fw.isChecked(), 'de nouveau non nul : proposée de nouveau')
        sw.setValue(-0.2)
        self.assertFalse(fw.isVisible(), 'négatif : rien à finir')
        d.close()

    def test_saved_choice_kept_on_open(self):
        op = M.Operation(kind='prismatique', name='P', stock=0.2, vcarve_finish=False)
        d = self.open(op)
        fw = d.widgets['vcarve_finish']
        self.assertTrue(fw.isVisible())
        self.assertFalse(fw.isChecked(), 'à l’ouverture, le choix enregistré')
        d.apply()
        self.assertEqual((op.stock, op.vcarve_finish), (0.2, False))
        d.close()

    def test_other_kinds_unchanged(self):
        d = self.open(M.Operation(kind='contour', name='C'))
        self.assertFalse(d.rows['stock'][0].text().startswith('OffsetXY'))
        d.close()


if __name__ == '__main__':
    unittest.main()
