"""Round 685 : sélection 3D (onglet Design STEP) — « Faces tangentes » (de
proche en proche, sans arête vive : côtés et congés d'un bord arrondi, les
deux moitiés d'un trou, pas les arêtes vives ; pli mesuré par la surface
décrite ou par les facettes) et « Faces du corps » (toutes les faces des
corps choisis) ; boutons du ruban sur une pièce ouverte en 3D."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import numpy as np
from PySide6.QtWidgets import QApplication

from vectordrive.core import brep as B
from vectordrive.core import facesel as S
from vectordrive.io import model3d

app = QApplication.instance() or QApplication([])


def side_faces(m, kind, **near):
    """Faces de nature `kind` dont l'encombrement colle aux bornes données ('x0'… 'z1')."""
    keys = ('x0', 'y0', 'z0', 'x1', 'y1', 'z1')
    out = []
    for f in range(m.face_count()):
        p = S.props(m, f)
        if p['kind'] == kind and all(abs(p['bounds'][keys.index(k)] - v) < 1e-6 for k, v in near.items()):
            out.append(f)
    return out


class _Case(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.d = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def parts(self):
        """Plaque 80 × 50 × 10 à coins R6, trou Ø8, lumière 30 × 20 à coins R3 ; bloc 30 × 20 × 5 à coins vifs."""
        p = os.path.join(self.d, 'essai.step')
        plate = B.Body('plaque', [B.Slab(0, 10, [B.rounded_rect(0, 0, 80, 50, 6), B.Circle(20, 25, 4),
                                                 B.rounded_rect(40, 15, 70, 35, 3)])])
        block = B.Body('bloc', [B.Slab(0, 5, [B.rounded_rect(100, 0, 130, 20)])])
        B.write(p, [plate, block], 'essai')
        return p


class TestCore(_Case):
    def test_rounded_edge(self):
        m = model3d.from_step(self.parts())
        front = side_faces(m, 'plan', y0=0.0, y1=0.0, z0=0.0, z1=10.0)[0]   # côté avant de la plaque
        edge = S.tangent(m, [front])
        self.assertEqual(len(edge), 8)                                    # 4 côtés, 4 congés des coins
        kinds = sorted(S.props(m, f)['kind'] for f in edge)
        self.assertEqual(kinds, ['cylindre'] * 4 + ['plan'] * 4)
        self.assertTrue(all(S.props(m, f)['radius'] == 6.0 for f in edge if S.props(m, f)['kind'] == 'cylindre'))
        slot = side_faces(m, 'plan', y0=15.0, y1=15.0)                    # la lumière : son propre tour
        self.assertEqual(len(S.tangent(m, slot)), 8)
        self.assertTrue(set(S.tangent(m, slot)).isdisjoint(edge))
        hole = side_faces(m, 'cylindre', x0=16.0)
        self.assertEqual(S.tangent(m, hole[:1]), sorted(hole))            # les deux moitiés du trou
        top = side_faces(m, 'plan', z0=10.0, z1=10.0)
        self.assertEqual(S.tangent(m, top), top)                          # arêtes vives tout autour
        block = side_faces(m, 'plan', x0=100.0, x1=130.0, y0=0.0)
        self.assertEqual(S.tangent(m, block), block)                      # coins vifs : rien de plus

    def test_mesh_without_description(self):
        """Un maillage sans description (STL) : le pli des facettes, `TANGENT_MESH_DEG` de tolérance."""
        m = model3d.from_step(self.parts())
        T = np.asarray(m.triangles, float)
        stl = os.path.join(self.d, 'essai.stl')
        from vectordrive.io.stl_write import write_stl
        write_stl(stl, T.reshape(-1, 3, 3))
        s = model3d.from_mesh(stl)
        self.assertGreater(s.face_count(), 0)
        f = next(f for f in range(s.face_count()) if S.props(s, f)['kind'] == 'plan'
                 and S.props(s, f)['bounds'][2] == 10.0)
        self.assertEqual(S.tangent(s, [f]), [f])

    def test_body_faces(self):
        m = model3d.from_step(self.parts())
        self.assertEqual(m.body_count(), 2)
        hole = side_faces(m, 'cylindre', x0=16.0)
        plate = S.body_faces(m, hole[:1])
        self.assertEqual(len(plate), 20)                                  # 8 + 2 + 8 parois, dessus, dessous
        block = S.body_faces(m, side_faces(m, 'plan', x0=100.0, x1=130.0, y0=0.0))
        self.assertEqual(len(block), 6)
        self.assertEqual(sorted(plate + block), list(range(m.face_count())))
        self.assertEqual(S.body_faces(m, hole[:1] + block[:1]), list(range(m.face_count())))


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

    def test_buttons(self):
        from tests.test_round672 import full_hd, tab_index
        w = self.w
        page = w.ribbon.page(tab_index(w.ribbon, 'Design STEP'))
        self.assertEqual(page.fit(full_hd()), [])
        self.assertEqual(w.step_tangent(), [])                            # pas de vue 3D : dit
        self.assertIn('vue 3D', w.statusBar().currentMessage())
        self.assertTrue(w.open_path(self.parts()))
        w._ensure_panel3d()
        p3 = w.panel3d
        self.assertTrue(p3.refresh())
        self.assertEqual(w.step_body_faces(), [])                         # rien de choisi : dit
        self.assertIn('faces', w.statusBar().currentMessage())
        m = p3.view.model
        front = side_faces(m, 'plan', y0=0.0, y1=0.0, z0=0.0, z1=10.0)
        p3.view.set_selection(front)
        self.assertEqual(len(w.step_tangent()), 8)
        self.assertEqual(len(p3.view.sel_faces), 8)
        self.assertIn('8 face(s) tangente(s)', w.statusBar().currentMessage())
        self.assertEqual(len(w.step_body_faces()), 20)
        self.assertEqual(len(p3.view.sel_faces), 20)
        self.assertIn('20 face(s) du corps', w.statusBar().currentMessage())
        hole = side_faces(m, 'cylindre', x0=16.0)
        p3.view.set_selection(hole[:1])
        self.assertEqual(w.step_similar(), sorted(hole))                  # toujours là, par le même chemin


if __name__ == '__main__':
    unittest.main()
