"""Round 680 : sélection 3D (onglet Design STEP, groupe « Sélection 3D ») — nature et mesures d'une face
(`core.facesel`), faces semblables (trous de même diamètre, faces coplanaires), mesures entre deux faces
(plans parallèles, entraxe, axe et plan) ; maillage sans description (STL) ; la ligne d'état de la vue 3D, les
boutons du ruban sur la pièce du dessin."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import numpy as np
from PySide6.QtWidgets import QApplication

from vectordrive.core import brep as B
from vectordrive.core import facesel as S
from vectordrive.core import stepgen as G
from vectordrive.io import model3d

app = QApplication.instance() or QApplication([])


class _Case(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.d = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def plate(self):
        p = os.path.join(self.d, 'plaque.step')
        B.write(p, G.build('plaque', G.values('plaque', hole='lamage', size='M6', thickness=12.0)), 'plaque')
        return p


def faces_of(m, kind, **want):
    out = []
    for f in range(m.face_count()):
        p = S.props(m, f)
        if p['kind'] == kind and all(abs(p[k] - v) < 1e-6 if isinstance(v, float) else p[k] == v
                                     for k, v in want.items() if k in p):
            out.append(f)
    return out


class TestCore(_Case):
    def test_props_and_similar(self):
        m = model3d.from_step(self.plate())
        holes = faces_of(m, 'cylindre', radius=G.CLEARANCE['M6'] / 2)
        self.assertEqual(len(holes), 8)                                  # 4 trous, deux demi-faces chacun
        p = S.props(m, holes[0])
        self.assertTrue(p['hollow'])
        self.assertTrue(np.allclose(np.abs(p['axis']), (0, 0, 1)))
        self.assertAlmostEqual(p['length'], 5.5, 6)
        self.assertEqual(S.similar(m, holes[:1]), holes)                 # tous les trous de ce diamètre
        cbs = faces_of(m, 'cylindre', radius=G.COUNTERBORE['M6'] / 2)
        self.assertEqual(S.similar(m, cbs[:1]), cbs)
        floors = [f for f in faces_of(m, 'plan') if abs(S.props(m, f)['offset'] - 5.5) < 1e-6]
        self.assertEqual(len(floors), 4)                                 # fonds des lamages, coplanaires
        self.assertEqual(S.similar(m, floors[:1]), floors)
        top = next(f for f in faces_of(m, 'plan') if S.props(m, f)['normal'][2] > 0.99
                   and abs(S.props(m, f)['offset'] - 12) < 1e-6)
        self.assertEqual(S.similar(m, [top]), [top])
        self.assertEqual(S.similar(m, [10 ** 6]), [])

    def test_between(self):
        m = model3d.from_step(self.plate())
        planes = faces_of(m, 'plan')
        top = next(f for f in planes if S.props(m, f)['normal'][2] > 0.99 and S.props(m, f)['offset'] > 11)
        bottom = next(f for f in planes if S.props(m, f)['normal'][2] < -0.99)
        b = S.measure(m, [top, bottom])['between']
        self.assertEqual(b['what'], 'parallel_planes')
        self.assertAlmostEqual(b['distance'], 12.0, 6)
        side = next(f for f in planes if S.props(m, f)['normal'][0] > 0.99)
        self.assertEqual(S.measure(m, [top, side])['between']['what'], 'planes')
        self.assertAlmostEqual(S.measure(m, [top, side])['between']['angle'], 90.0, 6)
        holes = faces_of(m, 'cylindre', radius=G.CLEARANCE['M6'] / 2)
        cx = {f: S.props(m, f)['centre'] for f in holes}
        a = holes[0]
        other = next(f for f in holes if abs(cx[f][0] - cx[a][0]) > 1 and abs(cx[f][1] - cx[a][1]) < 1e-6)
        b = S.measure(m, [a, other])['between']
        self.assertEqual(b['what'], 'parallel_axes')
        self.assertAlmostEqual(b['distance'], abs(cx[other][0] - cx[a][0]), 6)   # entraxe
        b = S.measure(m, [a, side])['between']
        self.assertEqual(b['what'], 'axis_plane')
        self.assertAlmostEqual(b['distance'], 100 - cx[a][0], 6)
        self.assertEqual(S.measure(m, [a, top])['between']['what'], 'axis_normal_to_plane')
        res = S.measure(m, [top, bottom, side])
        self.assertNotIn('between', res)
        self.assertTrue(np.allclose(res['bounds'], (0, 0, 0, 100, 60, 12)))

    def test_mesh_without_description(self):
        T = B.mesh(B.Body('bloc', [B.Slab(0, 10, [B.rounded_rect(0, 0, 40, 20)])])).astype(np.float32)
        m = model3d.Model3D(T, np.ones((len(T), 3), np.float32), np.zeros((0, 2, 3), np.float32), 'bloc.stl')
        tops = [f for f in range(m.face_count()) if S.props(m, f)['kind'] == 'plan'
                and S.props(m, f)['normal'][2] > 0.99]
        self.assertEqual(len(tops), 1)
        self.assertAlmostEqual(S.props(m, tops[0])['offset'], 10.0, 5)
        bottom = next(f for f in range(m.face_count()) if S.props(m, f).get('normal', (0, 0, 0))[2] < -0.99)
        self.assertAlmostEqual(S.measure(m, [tops[0], bottom])['between']['distance'], 10.0, 5)

    def test_text(self):
        from vectordrive.ui import step_select as U
        m = model3d.from_step(self.plate())
        hole = faces_of(m, 'cylindre', radius=G.CLEARANCE['M6'] / 2)[0]
        self.assertIn('trou Ø6,6', U.short_text(m, [hole]))
        self.assertIn('axe ', U.short_text(m, [hole]))
        lines = U.measure_lines(S.measure(m, list(range(m.face_count()))))
        self.assertIn('autres faces', '\n'.join(lines))
        self.assertIn('encombrement 100 × 60 × 12 mm', lines[-1])


class TestWindow(_Case):
    def setUp(self):
        super().setUp()
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()

    def tearDown(self):
        for i in range(len(self.w.docs)):
            self.w.docs[i].modified = False
        self.w.modified = False
        self.w.close()
        super().tearDown()

    def test_ribbon(self):
        from tests.test_round672 import full_hd, tab_index
        r = self.w.ribbon
        page = r.page(tab_index(r, 'Design STEP'))
        acts = [b.defaultAction() for g in page.groups() if g.title.text() == 'Sélection 3D' for b in g.buttons()]
        self.assertEqual(acts, [self.w.A[k] for k in ('cam3d_pick_faces', 'step_similar', 'step_parallel',
                                                     'step_coaxial', 'step_tangent', 'step_body_faces', 'step_invert',
                                                     'step_measure', 'cam3d_clear')])
        self.assertTrue(page.fit(full_hd()))                    # tient en 1920 (sans défiler, 1094)

    def test_similar_and_measure(self):
        w = self.w
        self.assertEqual(w.step_similar(), [])                            # pas de vue 3D : dit
        self.assertIn('vue 3D', w.statusBar().currentMessage())
        p = self.plate()
        self.assertTrue(w.open_path(p))
        w._ensure_panel3d()
        p3 = w.panel3d
        self.assertTrue(p3.refresh())
        self.assertEqual(w.step_measure(exec_dialog=False), [])           # rien de choisi : dit
        self.assertIn('faces', w.statusBar().currentMessage())
        w.A['cam3d_pick_faces'].trigger()                                  # clic : choisir des faces
        self.assertEqual(p3.view.select_mode, 'faces')
        m = p3.view.model
        holes = faces_of(m, 'cylindre', radius=G.CLEARANCE['M6'] / 2)
        p3.view.set_selection(holes[:1])
        self.assertIn('trou Ø6,6', p3.info.text())                         # la ligne d'état de la vue 3D
        self.assertEqual(w.step_similar(), holes)
        self.assertEqual(sorted(p3.view.sel_faces), holes)
        lines = w.step_measure(exec_dialog=False)
        self.assertEqual(len(lines), 8 + 1)
        self.assertIn('8 faces', lines[-1])
        p3.view.set_selection(holes[:1] + [f for f in holes if abs(S.props(m, f)['centre'][0]
                                                                      - S.props(m, holes[0])['centre'][0]) > 1][:1])
        self.assertIn('entraxe', p3.info.text())
        d = w.step_screw(exec_dialog=False)                               # vis dans les trous choisis
        self.assertEqual(d.fit.kind, 'lamage')
        d.deleteLater()


if __name__ == '__main__':
    unittest.main()
