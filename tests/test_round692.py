"""Round 692 : relecture de 688 et 690 — faces coaxiales : une sphère choisie
prend l'axe de sa voisine (l'axe que le fichier lui donne est quelconque), la
sélection reste dans le corps de la face choisie (une bague posée sur l'axe
d'un trou n'en est pas) ; répéter des corps dans les axes de la pièce
redressée (fichier « Y vers le haut »), corps choisi introuvable dit, fichier
existant remplacé au second clic seulement, la source jamais, un nom seul à
côté de la source."""
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
from vectordrive.io import step_extract as X
from tests.test_round688 import body, kind, parts

app = QApplication.instance() or QApplication([])


def boxes(path):
    """Encombrement (x0, y0, z0, x1, y1, z1) de chaque corps lu, pièce redressée comme dans la vue 3D."""
    m = model3d.from_step(path)
    T, bo = np.asarray(m.triangles, dtype=float), np.asarray(m.body_ids())
    return [np.round(np.r_[T[bo == b].reshape(-1, 3).min(0), T[bo == b].reshape(-1, 3).max(0)], 4).tolist()
            for b in sorted(set(bo.tolist()))]


class TestCoaxial(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.d = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def test_sphere_takes_its_neighbour_axis(self):
        m = model3d.from_step(parts(self.d))
        shaft = [f for f in range(m.face_count()) if body(m, f) == body(m, m.face_count() - 1)]
        sphere = [f for f in shaft if kind(m, f) == 'sphere']
        for f in sphere:                                                 # comme l'écrit une autre CAO
            m.face_kinds[f]['axe'] = np.array([0.6, 0.1, 0.79])
        self.assertEqual(S.coaxial(m, sphere[:1]), shaft)

    def test_stays_in_the_picked_body(self):
        p = os.path.join(self.d, 'plaque_bague.step')
        plate = G.build('plaque', G.values('plaque', hole='lamage', size='M6', thickness=12.0))
        bush = G.build('bague', G.values('bague'))[0]
        bush.matrix = B.placement((10, 10, 20), (0, 0, 1), (1, 0, 0))   # sur l'axe du premier trou, au-dessus
        B.write(p, plate + [bush], 'plaque_bague')
        m = model3d.from_step(p)
        hole = [f for f in range(m.face_count()) if kind(m, f) == 'cylindre' and m.face_kinds[f].get('creux')
                and body(m, f) == 0 and np.allclose(S.props(m, f)['centre'][:2], (10, 10), atol=1e-6)]
        got = S.coaxial(m, hole[:1])
        self.assertEqual(len(got), 5)                                    # passage, lamage, fond : pas la bague
        self.assertEqual({body(m, f) for f in got}, {0})
        bore = [f for f in range(m.face_count()) if body(m, f) == 1 and kind(m, f) == 'cylindre']
        self.assertEqual({body(m, f) for f in S.coaxial(m, bore[:1])}, {1})


class TestPattern(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.d = self._tmp.name
        self.src = os.path.join(self.d, 'yup.step')
        plate = G.build('plaque', G.values('plaque'))[0]
        plate.matrix = B.placement((0, 0, 0), (0, 1, 0), (1, 0, 0))     # exportée « Y vers le haut »
        B.write(self.src, [plate], 'yup')

    def tearDown(self):
        self._tmp.cleanup()

    def dialog(self, **kw):
        from vectordrive.ui.step_pattern_dialog import StepPatternDialog
        return StepPatternDialog(None, self.src, **kw)

    def test_axes_of_the_upright_part(self):
        self.assertEqual(model3d.from_step(self.src).up_axis, 'Y')
        (b0,) = boxes(self.src)
        d = self.dialog()
        self.assertEqual(d.up, 'Y')
        d.dx.setValue(0)
        d.dz.setValue(30)
        d.count.setValue(2)
        d.out.setText('monte.step')                                       # un nom seul : à côté de la source
        self.assertTrue(d.write())
        self.assertEqual(os.path.dirname(d.written), self.d)
        b = boxes(d.written)
        self.assertEqual(b[1], [b0[0], b0[1], b0[2] + 30, b0[3], b0[4], b0[5] + 30])   # monte, comme dans la vue
        d.deleteLater()
        d = self.dialog()
        d.mode.setCurrentIndex(1)
        d.count.setValue(2)
        d.angle.setValue(360)
        d.out.setText('tour.step')
        self.assertTrue(d.write())
        b = boxes(d.written)
        self.assertEqual(b[1], [-b0[3], -b0[4], b0[2], -b0[0], -b0[1], b0[5]])          # tournée, pas retournée
        d.deleteLater()

    def test_guards(self):
        d = self.dialog(picks=[5])
        self.assertIn('introuvable', d.info.text())
        self.assertIsNone(d.picks)
        d.out.setText(os.path.join(self.d, '.', 'YUP.step'))              # la source, autrement écrite
        self.assertIsNone(d.write())
        self.assertIn('source', d.info.text())
        other = os.path.join(self.d, 'deja.step')
        with open(other, 'w') as f:
            f.write('x')
        d.out.setText(other)
        self.assertIsNone(d.write())                                      # existe : dit, pas remplacé
        self.assertIn('existe déjà', d.info.text())
        self.assertEqual(os.path.getsize(other), 1)
        self.assertTrue(d.write())                                        # second clic : remplacé
        self.assertEqual(len(X.bodies(other)), 4)
        d.deleteLater()


if __name__ == '__main__':
    unittest.main()
