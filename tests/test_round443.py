"""Round 443 : « pas de passe sur le cadre » ne saute que le contour englobant (non englobé) ;
entrées / sorties tangentes réduites pour rester dans la chute (jour étroit entre deux formes)."""
import unittest

import shapely
from shapely.geometry import LineString

from vectordrive.cam import model, strategies as S
from vectordrive.core import geom
from vectordrive.core.document import Document, Shape


def doc_with(*rects):
    d = Document()
    for x, y, w, h in rects:
        d.add(Shape(path=geom.Path([geom.rect(x, y, w, h)]), tool=0))
    return d


class TestFrame(unittest.TestCase):
    def test_only_enclosing_contour_skipped(self):
        # cadre 0..100, une forme dedans (île) 30..70, une forme seule dehors 120..140
        d = doc_with((0, 0, 100, 100), (10, 10, 80, 80), (30, 30, 40, 40), (120, 0, 20, 20))
        reg = S.region([S.item_geometry(it) for it in d.iter_leaves()], 0.01)
        frames = S.frames_of(reg)
        self.assertAlmostEqual(frames.area, 100 * 100 - 80 * 80, places=3)    # le cadre seul
        rings = S.rings_of(reg, True, exteriors=frames)
        boxes = sorted(tuple(round(v) for v in shapely.LinearRing(r).bounds) for r in rings)
        self.assertEqual(boxes, [(10, 10, 90, 90), (30, 30, 70, 70), (120, 0, 140, 20)])
        op = model.Operation(kind='vcarve', finish_skip_frame=True)
        self.assertIs(S.keep_exteriors(model.Operation(kind='vcarve'), reg), True)
        self.assertIsNot(S.keep_exteriors(op, reg), True)
        self.assertIs(S.keep_exteriors(op, S.region([S.item_geometry(it) for it in
                                                     doc_with((0, 0, 10, 10)).iter_leaves()], 0.01)), True)

    def test_vcarve_keeps_inner_shapes(self):
        d = doc_with((0, 0, 100, 100), (10, 10, 80, 80), (40, 40, 20, 20))
        s = model.CamSetup()
        s.tools = [model.CamTool(name='V', kind='conique', diameter=6.0, angle=30, tip=0.1, number=1)]
        out = {}
        for skip in (False, True):
            op = model.Operation(kind='vcarve', depth=1.0, step_down=1.0, tool_id=s.tools[0].id, sources=[0],
                                 finish_skip_frame=skip, gravure_rule=0)
            tp = S.compute(d, s, op)
            out[skip] = [m for m in tp.moves if m.z < 0]
        xs = [m.x for m in out[True]]
        self.assertGreater(min(xs), 1.0)                                       # rien sur le bord du cadre
        self.assertTrue(any(40 <= m.x <= 60 and 40 <= m.y <= 60 for m in out[True]))   # l'île gravée


class TestLeads(unittest.TestCase):
    def test_lead_stays_in_scrap(self):
        # deux pièces séparées d'un jour de 4 mm : détourage extérieur, fraise Ø3, entrées de 5 mm
        d = doc_with((0, 0, 40, 20), (0, 24, 40, 20))
        s = model.CamSetup()
        s.tools = [model.CamTool(name='F3', kind='fraise', diameter=3.0, number=1)]
        op = model.Operation(kind='contour', depth=1.0, step_down=1.0, tool_id=s.tools[0].id, sources=[0],
                             side='exterieur', lead_in=5.0, lead_out=5.0)
        tp = S.compute(d, s, op)
        reg = S.region([S.item_geometry(it) for it in d.iter_leaves()], 0.01)
        segs, prev = [], None
        for m in tp.moves:
            if prev is not None and m.kind != 'rapid' and m.z < 0 and prev.z < 0:
                segs.append(LineString([(prev.x, prev.y), (m.x, m.y)]))
            prev = m
        cut = shapely.union_all(segs).buffer(1.5 - 0.02)
        self.assertLess(cut.intersection(reg).area, 1e-3)                       # la pièce n'est pas entamée


if __name__ == '__main__':
    unittest.main()
