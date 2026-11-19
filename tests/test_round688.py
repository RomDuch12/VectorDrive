"""Round 688 : sélection 3D « Faces coaxiales » (onglet Design STEP) — un
cylindre, un cône ou une sphère : toutes les faces de révolution du même axe
et les plans perpendiculaires bordés seulement par elles ; un trou lamé entier
(passage, lamage, fond du lamage) sans les autres trous ni le dessus de la
plaque ; un arbre tourné entier (cylindres, chanfrein, dôme, épaulement,
bouts) ; le lecteur STEP donne l'axe des cônes et des sphères ; bouton."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import numpy as np
from PySide6.QtWidgets import QApplication

from vectordrive.core import brep as B
from vectordrive.core import facesel as S
from vectordrive.core import steprevolve as RV
from vectordrive.core import stepgen as G
from vectordrive.core.geom import Contour, Line, Path, arc_conics
from vectordrive.io import model3d

app = QApplication.instance() or QApplication([])


def parts(d):
    """Plaque à 4 trous lamés M6 ; à côté, arbre tourné (Ø30 puis Ø20, chanfrein, dôme R8) d'axe Z en (150, 0)."""
    p = os.path.join(d, 'pieces.step')
    plate = G.build('plaque', G.values('plaque', hole='lamage', size='M6', thickness=12.0))
    prof = Contour([Line(a, b) for a, b in (((0, 0), (15, 0)), ((15, 0), (15, 20)), ((15, 20), (10, 20)),
                                            ((10, 20), (10, 26)), ((10, 26), (8, 28)))]
                   + arc_conics((0, 28), 8, 8, 0, 90) + [Line((0, 36), (0, 0))], True)
    shaft = RV.bodies(Path([prof]), 'arbre')[0]
    shaft.matrix = B.placement((150, 0, 0), (0, 0, 1), (1, 0, 0))
    B.write(p, plate + [shaft], 'pieces')
    return p


def kind(m, f):
    return (m.face_kinds[f] or {}).get('genre')


def body(m, f):
    return int(np.asarray(m.body_ids())[np.asarray(m.face_ids()) == f][0])


class TestCore(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.m = model3d.from_step(parts(self._tmp.name))

    def tearDown(self):
        self._tmp.cleanup()

    def test_counterbored_hole(self):
        m = self.m
        holes = [f for f in range(m.face_count()) if kind(m, f) == 'cylindre' and m.face_kinds[f].get('creux')]
        self.assertEqual(len(holes), 16)                                 # 4 passages, 4 lamages, en deux moitiés
        got = S.coaxial(m, holes[:1])
        P = S.props(m, holes[0])
        c = P['centre']
        near = [f for f in range(m.face_count()) if body(m, f) == body(m, holes[0])
                and np.linalg.norm(S.face_triangles(m, f).reshape(-1, 3)[:, :2] - c[:2], axis=1).max() < 5.6]
        self.assertEqual(got, near)                                      # le trou, tout le trou
        self.assertEqual([kind(m, f) for f in got].count('cylindre'), 4)
        planes = [f for f in got if kind(m, f) == 'plan']
        self.assertEqual(len(planes), 1)                                 # le fond du lamage, pas le dessus
        self.assertAlmostEqual(S.props(m, planes[0])['offset'], 5.5, 6)   # à mi-hauteur, tourné vers le haut
        self.assertEqual(S.coaxial(m, got), got)

    def test_turned_shaft(self):
        m = self.m
        faces = [f for f in range(m.face_count()) if body(m, f) == body(m, m.face_count() - 1)]
        cone = [f for f in faces if kind(m, f) == 'cone']
        sphere = [f for f in faces if kind(m, f) == 'sphere']
        self.assertTrue(cone and sphere)
        for f in cone + sphere:                                          # le lecteur dit l'axe
            k = m.face_kinds[f]
            self.assertAlmostEqual(abs(float(S._unit(k['axe'])[2])), 1.0, 6)
            self.assertAlmostEqual(float(np.hypot(k['centre'][0] - 150, k['centre'][1])), 0.0, 6)
        cyl = [f for f in faces if kind(m, f) == 'cylindre']
        self.assertEqual(S.coaxial(m, cyl[:1]), faces)                   # l'arbre entier
        self.assertEqual(S.coaxial(m, sphere[:1]), faces)
        plane = [f for f in faces if kind(m, f) == 'plan']
        self.assertEqual(S.coaxial(m, plane[:1]), plane[:1])             # un plan : lui seul

    def test_without_description(self):
        m = self.m
        m.face_kinds = []
        self.assertEqual(S.coaxial(m, [3, 7]), [3, 7])


class TestWindow(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()

    def tearDown(self):
        for i in range(len(self.w.docs)):
            self.w.docs[i].modified = False
        self.w.modified = False
        self.w.close()
        self._tmp.cleanup()

    def test_button(self):
        from tests.test_round672 import full_hd, tab_index
        w = self.w
        page = w.ribbon.page(tab_index(w.ribbon, 'Design STEP'))
        acts = [b.defaultAction() for g in page.groups() if g.title.text() == 'Sélection 3D' for b in g.buttons()]
        self.assertIn(w.A['step_coaxial'], acts)
        self.assertTrue(page.fit(full_hd()))                    # tient en 1920 (sans défiler, 1094)
        self.assertTrue(w.open_path(parts(self._tmp.name)))
        w._ensure_panel3d()
        p3 = w.panel3d
        self.assertTrue(p3.refresh())
        m = p3.view.model
        hole = [f for f in range(m.face_count()) if kind(m, f) == 'cylindre' and m.face_kinds[f].get('creux')][:1]
        p3.view.set_selection(hole)
        got = w.step_coaxial()
        self.assertEqual(got, S.coaxial(m, hole))
        self.assertEqual(len(got), 5)
        self.assertEqual(sorted(p3.view.sel_faces), got)
        self.assertIn('5 face(s) coaxiale(s)', w.statusBar().currentMessage())


if __name__ == '__main__':
    unittest.main()
