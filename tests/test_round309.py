"""Round 309 : perçage (TypeEdit : filtre de sélection et modes) — points
percés : cercles et marqueurs, marqueurs, départ / arrivée des traits,
centres des contours fermés ; débourrage, brise-copeau, une passe ;
remontée en vitesse de travail."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.cam import model as M, strategies as S
from vectordrive.core import forms as F, geom
from vectordrive.core.document import Document, Shape
from vectordrive.ui import cam_panel as CP


def doc_of():
    d = Document()
    d.plate = None
    d.add(Shape(path=geom.Path([geom.circle((10, 10), 1)]), tool=1))
    d.add(Shape(path=geom.Path([geom.polyline([(0, 0), (5, 0)])]), tool=1))
    d.add(Shape(path=geom.Path([geom.rect(20, 0, 4, 2)]), tool=1))
    d.add(F.make(F.Marker(cx=30, cy=30), tool=1))
    return d, True


def run(**kw):
    d, has_marker = doc_of()
    setup = M.setup_of(d)
    t = M.CamTool(name='Foret', kind='foret', diameter=2)
    setup.tools = [t]
    return S.compute(d, setup, M.Operation(kind='percage', depth=3, tool_id=t.id, **kw)), has_marker


def holes(tp):
    return sorted({(round(m.x, 6), round(m.y, 6)) for m in tp.moves if m.kind == 'plunge'})


class TestDrill(unittest.TestCase):
    def test_points(self):
        tp, mk = run()
        self.assertIn((10, 10), holes(tp))
        if mk:
            self.assertIn((30, 30), holes(tp))
        self.assertEqual(holes(run(drill_points='depart')[0]), [(0, 0)])
        self.assertEqual(holes(run(drill_points='arrivee')[0]), [(5, 0)])
        self.assertEqual(set(holes(run(drill_points='depart_arrivee')[0])) >= {(0, 0), (5, 0), (20, 0)}, True)
        self.assertIn((22, 1), holes(run(drill_points='centres')[0]))
        tp, _ = run(drill_points='marqueurs')
        self.assertEqual(holes(tp), [(30, 30)] if mk else [])

    def test_modes(self):
        tp, _ = run(peck=1)
        zs = [m.z for m in tp.moves if m.kind == 'rapid' and (round(m.x, 6), round(m.y, 6)) == (10, 10)]
        self.assertEqual(zs.count(M.Operation().clear_z), 4)             # approche + 2 débourrages + fin ; débourrage : remonte au dégagement
        tp, _ = run(peck=1, drill_mode='brise_copeau')
        ups = [m for m in tp.moves if m.kind == 'rapid' and (round(m.x, 6), round(m.y, 6)) == (10, 10)
               and m.z < 0]
        self.assertEqual([round(m.z, 3) for m in ups], [-0.7, -1.7])        # petit recul de 0,3
        tp, _ = run(peck=1, drill_mode='simple')
        self.assertEqual(sum(1 for m in tp.moves if m.kind == 'plunge' and (round(m.x, 6), round(m.y, 6)) == (10, 10)), 1)
        tp, _ = run(drill_feed_retract=True)
        self.assertTrue(any(m.kind == 'feed' and m.z > 0 for m in tp.moves))

    def test_form(self):
        self.assertIn('drill_points', CP.FIELD_CHOICES)
        self.assertIn('drill_mode', CP.KIND_FIELDS['percage'])


if __name__ == '__main__':
    unittest.main()
