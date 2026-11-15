"""Round 904 : intaille standard (TypeEdit 13 « Standard », SPECIALINTAILLE/Prismatic = 0). L'outil suit un flanc à l'aller,
l'autre au retour ; chaque branche est parcourue deux fois. L'intaille optimisée (« Optimisé » : les deux flancs en une passe)
reste la ligne médiane. L'import des modèles TE suit la clé Prismatic et reprend la surépaisseur."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r904.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

import shapely
from shapely.geometry import box

from vectordrive.cam import model as M
from vectordrive.cam import strategies as S
from vectordrive.cam import tpp
from vectordrive.core import geom
from vectordrive.core.document import Document, Layer, Plate, Shape

TAN = math.tan(math.radians(15.0))
RT = 0.1


def bar(x0, y0, x1, y1):
    return geom.polyline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], closed=True)


def carve(contour, mode, depth=1.0):
    doc = Document()
    doc.plate = Plate(width=300.0, height=100.0)
    doc.layers = [Layer(name='A', items=[Shape(path=geom.Path([contour]))])]
    setup = M.setup_of(doc)
    t = M.CamTool(name='c', kind='conique', diameter=6.0, tip=2 * RT, angle=30.0)
    setup.tools.append(t)
    op = M.Operation(kind='vcarve', tool_id=t.id, depth=depth, step_down=9.0, resolution=0.05, vcarve_mode=mode)
    setup.operations.append(op)
    M.store(doc, setup)
    return S.compute(doc, setup, op, (0.0, 0.0))


def cuts(tp):
    return [(m.x, m.y, m.z) for m in tp.moves if m.kind != 'rapid' and m.z < -1e-6]


def length(tp):
    out, prev = 0.0, None
    for m in tp.moves:
        if prev is not None and m.kind != 'rapid' and m.z < -1e-6 and prev[2] < -1e-6:
            out += math.dist(prev[:2], (m.x, m.y))
        prev = (m.x, m.y, m.z)
    return out


WIDE = (0.0, 0.0, 30.0, 4.0)          # 4 mm de large : à 1 mm, l'outil ne touche pas les deux flancs
NARROW = (0.0, 0.0, 30.0, 0.5)        # 0,5 mm : il les touche


class Strategy(unittest.TestCase):

    def test_wide_branch_one_flank_then_the_other(self):
        reach = RT + 1.0 * TAN
        side = 2.0 - reach                                                # écart de l'axe de l'outil à la ligne médiane
        mid = [p for p in cuts(carve(bar(*WIDE), 'axe_ar')) if 8 < p[0] < 22]
        self.assertTrue(any(abs(p[1] - (2.0 + side)) < 0.05 for p in mid))
        self.assertTrue(any(abs(p[1] - (2.0 - side)) < 0.05 for p in mid))
        opt = [p for p in cuts(carve(bar(*WIDE), 'axe')) if 8 < p[0] < 22]
        self.assertTrue(opt)
        self.assertTrue(all(abs(p[1] - 2.0) < 0.05 for p in opt))         # optimisée : la ligne médiane, comme avant
        region = box(*WIDE)
        for p in cuts(carve(bar(*WIDE), 'axe_ar')):                        # l'outil ne mord jamais un flanc
            self.assertGreater(region.exterior.distance(shapely.Point(p[0], p[1])), RT + abs(p[2]) * TAN - 0.01)

    def test_narrow_branch_twice(self):
        std, opt = carve(bar(*NARROW), 'axe_ar'), carve(bar(*NARROW), 'axe')
        mid = [p for p in cuts(std) if 1 < p[0] < 29]                     # hors des petites branches des coins
        self.assertTrue(mid)
        self.assertTrue(all(abs(p[1] - 0.25) < 0.05 for p in mid))        # l'outil touche les deux flancs : sur l'axe
        self.assertGreater(length(opt), 10.0)
        self.assertAlmostEqual(length(std) / length(opt), 2.0, delta=0.2)  # aller et retour

    def test_flank_trip_alone(self):
        from vectordrive.cam import advanced as A
        pts = [(x, 2.0, -1.0) for x in (5.0, 10.0, 15.0)]
        out = A.flank_trip(pts, [2.0, 2.0, 2.0], box(*WIDE), RT, TAN)
        self.assertEqual(len(out), 6)
        self.assertEqual([round(p[0], 6) for p in out], [5.0, 10.0, 15.0, 15.0, 10.0, 5.0])
        ys = sorted({round(p[1], 4) for p in out})
        self.assertEqual(len(ys), 2)
        self.assertAlmostEqual(ys[1] - ys[0], 2 * (2.0 - RT - TAN), places=3)


class TypeEdit(unittest.TestCase):

    def op(self, sections):
        return tpp.to_template(tpp.Preset(name='I', kind='CP_Intaglio', sections=sections))['operations'][0]

    def test_prismatic_key(self):
        self.assertEqual(self.op({'SPECIALINTAILLE': {'Prismatic': '0', 'Allowance': '1.e-004'}})['vcarve_mode'], 'axe_ar')
        self.assertEqual(self.op({'SPECIALINTAILLE': {'Prismatic': '1'}})['vcarve_mode'], 'axe')
        self.assertEqual(self.op({})['vcarve_mode'], 'axe')                # sans la clé : comme avant
        self.assertAlmostEqual(self.op({'SPECIALINTAILLE': {'Prismatic': '0', 'Allowance': '1.e-004'}})['stock'], 0.1)

    def test_the_choice_in_the_form(self):
        from vectordrive.ui import cam_panel
        ch = cam_panel.FIELD_CHOICES['vcarve_mode']
        self.assertIn('axe_ar', ch)
        self.assertIn('aller-retour', ch['axe_ar'])
        self.assertEqual(list(ch).index('axe_ar'), list(ch).index('axe') + 1)


if __name__ == '__main__':
    unittest.main()
