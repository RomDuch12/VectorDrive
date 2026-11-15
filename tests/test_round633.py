"""Round 633 : gamme — « Lier au parcours précédent » (cam.linkprev) : le cône
ne reprend que la matière laissée par la fraise d'avant (passage trop étroit
pour elle), la pièce finie est la même qu'avec la gravure entière ; les
liaisons au fond ne touchent jamais la matière du moment. Cônes jusqu'à leur
queue (CamTool.body_diameter : fiche NeoDrive sans diamètre → 1 mm)."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import numpy as np

from vectordrive.cam import linkprev, model, simulate, strategies
from vectordrive.cam.model import CamTool
from vectordrive.core import geom
from vectordrive.core.document import Document, Shape

GAP = 1.0                                            # passage entre les deux « lettres » : trop étroit pour Ø 2


def setup_doc(linked=True, edges_only=True, cone_first=False):
    d = Document()
    d.plate = None
    shapes = [Shape(path=geom.Path([geom.rect(-10, -7, 20, 14)]), tool=0),          # cadre de la poche
              Shape(path=geom.Path([geom.rect(-4 - GAP / 2, -3, 4, 6)]), tool=0),   # deux lettres en relief
              Shape(path=geom.Path([geom.rect(GAP / 2, -3, 4, 6)]), tool=0)]
    for sh in shapes:
        d.add(sh)
    ids = [sh.id for sh in shapes]
    s = model.CamSetup()
    cyl = CamTool(name='Cyl 2', diameter=2.0, number=1, cut_length=7, step_down=1.0)
    cone = CamTool(name='Con 30 0.2', kind='conique', diameter=1.0, tip=0.2, angle=30.0, number=2, cut_length=15,
                   geometry={'D1': 0.2, 'D2': 6.0, 'L1': 50.0, 'angle': 30.0})      # comme une fiche NeoDrive
    s.tools = [cyl, cone]
    pocket = model.Operation(name='Ébauche', kind='poche', tool_id=cyl.id, items=list(ids), depth=2.0,
                             step_down=1.0)
    carve = model.Operation(name='Gravure', kind='vcarve', tool_id=cone.id, items=list(ids), depth=2.0,
                            vcarve_edges_only=edges_only, finish_skip_frame=True, link_previous=linked, gravure_rule=0)
    s.operations = [carve, pocket] if cone_first else [pocket, carve]
    return d, s


def heights(tps, s):
    sim = simulate.simulate([tp for tp in tps if tp.moves], s, res=0.02, margin=1.0)
    x0, y0 = -12.0, -9.0
    i0, j0 = int(round((y0 - sim.y0) / sim.res)), int(round((x0 - sim.x0) / sim.res))
    return sim.H[i0:i0 + 900, j0:j0 + 1200]


class TestBody(unittest.TestCase):
    def test_cone_to_shank(self):
        cone = CamTool(kind='conique', diameter=1.0, tip=0.2, angle=30.0, geometry={'D2': 6.0})
        self.assertEqual(cone.body_diameter(), 6.0)
        self.assertAlmostEqual(cone.radius_at(2.0), 0.1 + 2 * math.tan(math.radians(15)), places=9)
        self.assertEqual(cone.radius_at(50.0), 3.0)
        self.assertEqual(CamTool(kind='conique', diameter=1.0, tip=0.2, angle=30.0).radius_at(50.0), 0.5)
        self.assertEqual(CamTool(diameter=3.0, geometry={'D2': 6.0}).body_diameter(), 3.0)   # fraise : son Ø

    def test_vcarve_not_limited(self):
        d, s = setup_doc(linked=False, edges_only=False)
        s.operations = s.operations[1:]
        tp = strategies.compute_all(d, s)[0]
        self.assertFalse([w for w in tp.warnings if 'limitée' in w])
        self.assertAlmostEqual(min(m.z for m in tp.moves), -2.0, places=6)


class TestLinkPrevious(unittest.TestCase):
    def test_same_part_less_path(self):
        d, s = setup_doc(linked=True)
        linked = strategies.compute_all(d, s)
        d2, s2 = setup_doc(linked=False, edges_only=False)
        full = strategies.compute_all(d2, s2)
        self.assertTrue(any('lier au parcours précédent' in w for w in linked[1].warnings))
        n_link = len(linkprev._pieces(linked[1], 0.005))
        n_full = len(linkprev._pieces(full[1], 0.005))
        self.assertLess(n_link, n_full / 2)                                   # l'air n'est plus usiné
        diff = np.abs(heights(linked, s) - heights(full, s2))
        self.assertLess(float(diff.max()), 0.05)                             # même pièce finie
        gap = [(m.x, m.y) for m in linked[1].moves if m.kind != 'rapid' and m.z < -0.5]
        self.assertTrue(any(abs(x) < GAP / 2 and abs(y) < 2.5 for x, y in gap))   # le cône dans le passage

    def test_links_never_cut(self):
        d, s = setup_doc(linked=True)
        tps = strategies.compute_all(d, s)
        token = strategies._PREVIOUS.set([tps[0]])                            # le parcours avant le tri
        try:
            raw = strategies.compute(d, s, s.operations[1])
        finally:
            strategies._PREVIOUS.reset(token)
        src = linkprev._pieces(raw, 0.005)
        tool = s.tool(tps[1].tool_id)
        pieces = linkprev._pieces(tps[1], 0.005)
        H, x0, y0, res, _c = linkprev._grid(src, tool, 0.03)
        rough = simulate.sim_tool(s, tps[0], res)
        for a, b, _k in linkprev._pieces(tps[0], 0.005):                      # matière laissée par l'ébauche
            simulate._stamp_segment(H, a, b, rough, 1.0 + res, x0, y0, res)
        cone = simulate.sim_tool(s, tps[1], res)
        reach = simulate.cut_radius_of(cone, cone.body_diameter() / 2, res)
        A = np.array([a for a, _b, _k in src])
        B = np.array([b for _a, b, _k in src])

        def own(p):                                                          # sur un morceau du parcours d'avant tri
            v = B - A
            L2 = np.maximum((v * v).sum(axis=1), 1e-18)
            t = np.clip(((p - A) * v).sum(axis=1) / L2, 0.0, 1.0)
            return float(np.min(np.linalg.norm(A + t[:, None] * v - p, axis=1))) < 1e-7
        links = 0
        for a, b, kind in pieces:
            surf = linkprev._surface(H, a, b, cone, reach(-min(a[2], b[2])), x0, y0, res)
            if kind == 'feed' and min(a[2], b[2]) < 0 and not own((np.array(a) + np.array(b)) / 2):
                links += 1                                                   # liaison au fond ajoutée
                self.assertLessEqual(linkprev._gain(surf), linkprev.TOL_Z + 1e-9)
            if surf is not None:
                np.minimum(surf[0], surf[1], out=surf[0])

    def test_join(self):
        op = model.Operation(safe_z=2.0, clear_z=0.5)
        cone = CamTool(kind='conique', diameter=1.0, tip=0.2, angle=30.0, geometry={'D2': 6.0})
        res = 0.02
        H = np.zeros((101, 301))                                             # X -1..5, Y -1..1
        H[30:71, 40:261] = -1.0                                              # tranchée creusée (Y ±0,4, X -0,2..4,2)
        reach = simulate.cut_radius_of(cone, 3.0, res)
        moves = []
        linkprev._join(moves, (0.0, 0.0, -0.4), (4.0, 0.0, -0.6), op, cone, H, -1.0, -1.0, res, reach)
        self.assertEqual([m.kind for m in moves], ['feed', 'plunge'])        # au fond, puis plongée
        self.assertEqual((moves[0].x, moves[0].z), (4.0, -0.4))
        H[30:71, 145:156] = 0.0                                              # matière au milieu : remontée
        moves = []
        linkprev._join(moves, (0.0, 0.0, -0.4), (4.0, 0.0, -0.6), op, cone, H, -1.0, -1.0, res, reach)
        self.assertEqual([m.kind for m in moves], ['rapid', 'rapid', 'rapid', 'plunge'])
        self.assertEqual(moves[0].z, 2.0)

    def test_without_previous_and_order(self):
        d, s = setup_doc(linked=True)
        s.operations = s.operations[1:]
        tp = strategies.compute_all(d, s)[0]
        self.assertTrue(tp.moves and any('aucun parcours avant' in w for w in tp.warnings))
        d, s = setup_doc(linked=True, cone_first=True)
        tp = strategies.compute_all(d, s)[0]
        self.assertTrue(any('est usiné après' in w for w in tp.warnings))   # gros outil après le cône

    def test_cache_follows_previous(self):
        d, s = setup_doc(linked=True)
        a = strategies.compute_all(d, s)
        strategies.compute_all(d, s)
        self.assertEqual(strategies.LAST_RUN['reused'], 2)
        s.operations[0].depth = 1.0                                          # l'ébauche change : la gravure aussi
        b = strategies.compute_all(d, s)
        self.assertEqual(strategies.LAST_RUN['computed'], 2)
        self.assertNotEqual(len(a[1].moves), len(b[1].moves))

    def test_form_field(self):
        from vectordrive.ui import cam_panel
        self.assertIn('link_previous', cam_panel.LABELS if hasattr(cam_panel, 'LABELS') else
                      next(v for k, v in vars(cam_panel).items() if isinstance(v, dict) and 'link_passes' in v))
        for kind in ('vcarve', 'contour', 'poche', 'reste', 'decoupe3d'):
            self.assertIn('link_previous', cam_panel.KIND_FIELDS[kind])
        self.assertIn('link_previous', model.Operation.from_dict({'link_previous': True}).__dict__)
        self.assertTrue(model.Operation.from_dict({'link_previous': True}).link_previous)


if __name__ == '__main__':
    unittest.main()
