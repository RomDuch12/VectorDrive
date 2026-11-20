"""Round 894 : les décalages de l'usinage qui deviennent un parcours ne gardent plus l'anneau retourné d'une forme trop petite pour l'outil
(finition du détourage, chanfrein d'arête, découpe 3D, ligne commune, lettres prismatiques) : `buffer_checked`."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import shapely
from shapely.geometry import Polygon, box

from vectordrive.cam import model as M
from vectordrive.cam import strategies as S
from vectordrive.core import geom
from vectordrive.core.document import Document, Layer, Plate, Shape

ROOT = pathlib.Path(__file__).resolve().parents[1]

#: la forme inventée du round 883 (12 sommets, rayon inscrit 1,70) : à 2 mm, GEOS rend un anneau retourné
STAR = [(2.048, 0.0), (1.469, 0.848), (0.992, 1.717), (0.0, 2.048), (-0.848, 1.469), (-1.717, 0.992),
        (-2.048, 0.0), (-1.469, -0.848), (-0.992, -1.717), (0.0, -2.048), (0.848, -1.469), (1.717, -0.992)]


def star(dx, dy):
    return geom.polyline([(x + dx, y + dy) for x, y in STAR], closed=True)


def square(x0, y0, x1, y1):
    return geom.polyline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], closed=True)


def drawing(*paths):
    doc = Document()
    layer = Layer(name='Plan 1', items=[Shape(path=geom.Path([p])) for p in paths])
    doc.layers[:] = [layer]
    doc.active = layer.id
    doc.plate = Plate(width=300, height=200)
    return doc


def run(doc, tool, **kw):
    """(passes en matière [(x, y, z, distance à la paroi)], avertissements)."""
    setup = M.CamSetup(tools=[tool])
    op = M.Operation(tool_id=tool.id, **kw)
    setup.operations = [op]
    tp = S.compute(doc, setup, op, (0.0, 0.0))
    reg = S.region([S.item_geometry(it) for it in doc.layers[0].items], setup.tolerance)
    walls = shapely.get_rings(shapely.get_parts(reg))
    cuts = [(m.x, m.y, m.z, min(w.distance(shapely.Point(m.x, m.y)) for w in walls))
            for m in tp.moves if m.kind != 'rapid' and m.z < -1e-6]
    return cuts, tp.warnings


class Controle(unittest.TestCase):

    def setUp(self):
        self.reg = Polygon([(-30, -30), (30, -30), (30, 30), (-30, 30)], [STAR])
        if len(self.reg.buffer(2.0, quad_segs=8).interiors) != 1:
            self.skipTest('GEOS ne rend plus l\'anneau retourné')

    def test_le_trou_retourne_part(self):
        self.assertEqual(len(S.buffer_checked(self.reg, 2.0, 8).interiors), 0)
        self.assertTrue(S.buffer_checked(Polygon(STAR), -2.0, 8).is_empty)

    def test_un_vrai_decalage_ne_change_pas(self):
        for d in (-1.0, 0.5, 1.5):
            self.assertTrue(S.buffer_checked(self.reg, d, 8).equals(self.reg.buffer(d, quad_segs=8)))
            self.assertTrue(S.buffer_checked(box(0, 0, 9, 9), d, 4).equals(box(0, 0, 9, 9).buffer(d, quad_segs=4)))

    def test_la_ligne_commune(self):
        chains, _shared = S.common_line_chains(self.reg, 2.0, True, 0.01)
        self.assertEqual(len(chains), 1)                                    # avant : 2, la seconde dans le trou


class Parcours(unittest.TestCase):

    def test_la_finition_du_detourage(self):
        fr = M.CamTool(name='f', kind='fraise', diameter=4.0)
        cuts, _w = run(drawing(star(30, 30), square(60, 10, 100, 50)), fr, kind='contour', depth=1.0, step_down=1.0, side='interieur',
                       finish=True, stock=0.2)
        self.assertTrue(cuts)
        self.assertGreater(min(c[3] for c in cuts), 2.0 - 0.02)            # avant : 1,615, dans la paroi de l'étoile

    def test_le_chanfrein_d_arete(self):
        ch = M.CamTool(name='c', kind='conique', diameter=12.0, tip=4.0, angle=90.0)
        cuts, warn = run(drawing(star(30, 30)), ch, kind='chanfrein_bord', depth=1.0, side='interieur', chamfer_width=0.3)
        self.assertEqual(cuts, [])                                          # avant : un tour à 1,615 de la paroi
        self.assertTrue(any('trop petite' in w for w in warn))
        cuts, _w = run(drawing(square(10, 10, 50, 50), star(30, 30)), ch, kind='chanfrein_bord', depth=1.0, side='exterieur',
                       chamfer_width=0.3)
        self.assertTrue(cuts)
        self.assertGreater(min(c[3] for c in cuts), 2.0 - 0.02)

    def test_la_decoupe_3d(self):
        cone = M.CamTool(name='v', kind='conique', diameter=10.0, tip=3.769, angle=60.0)  # rayon 2,0 à 0,2 mm de profondeur
        cuts, _w = run(drawing(star(30, 30), square(60, 10, 100, 50)), cone, kind='decoupe3d', depth=0.6, step_down=0.2,
                       side='interieur')
        self.assertTrue(cuts)
        self.assertGreater(min(c[3] - cone.radius_at(-c[2]) for c in cuts), -0.02)

    def test_les_lettres_prismatiques(self):
        cone = M.CamTool(name='v', kind='conique', diameter=10.0, tip=4.0, angle=60.0)
        cuts, _w = run(drawing(square(10, 10, 50, 50), star(30, 30)), cone, kind='prismatique', depth=0.5, step_down=0.5, climb=True,
                       prism_rule=0)
        self.assertTrue(cuts)
        self.assertGreater(min(c[3] for c in cuts), 2.0 - 0.02)            # avant : un tour dans le creux en étoile


class Sources(unittest.TestCase):

    def test_plus_de_decalage_de_parcours_sans_controle(self):
        src = (ROOT / 'vectordrive' / 'cam' / 'strategies.py').read_text(encoding='utf-8')
        for old in ('fin = reg.buffer(', 'g = comp.buffer(', 'g = p.buffer(d', "g = reg.buffer(rt if side"):
            self.assertNotIn(old, src)
        adv = (ROOT / 'vectordrive' / 'cam' / 'advanced.py').read_text(encoding='utf-8')
        self.assertEqual(adv.count('S.buffer_checked(reg,'), 6)                # 1092 : les anneaux du reste ; 1113 : les flancs hors des formes ; 1121 : l'OffsetXY


if __name__ == '__main__':
    unittest.main()
