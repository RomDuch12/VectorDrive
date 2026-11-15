"""Round 684 : pièce tournée du dessin (onglet Design STEP) — un demi-profil
fermé du dessin tourné autour du trait droit choisi avec lui, sinon de son
bord gauche (`core.steprevolve`) : droites en cylindres, cônes et plans, arcs
centrés sur l'axe en sphères, autres arcs en cônes ; pointes et arêtes vives
du haut et du bas arrêtées d'un petit plat ; volumes (Pappus), faces,
encombrements, refus ; fenêtre « Pièce du dessin » en forme tournée ; ruban."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import brep as B
from vectordrive.core import stepdraw as D
from vectordrive.core import steprevolve as RV
from vectordrive.core.geom import Contour, Line, Path, arc_conics, circle
from vectordrive.io import step_extract as X
from tests.test_round673 import geometry_errors, misoriented, topology
from tests.test_round676 import _text, part
from tests.test_round677 import placed_bounds

app = QApplication.instance() or QApplication([])


def poly(pts, closed=True):
    return Contour([Line(a, b) for a, b in zip(pts, pts[1:] + (pts[:1] if closed else []))], closed)


def pappus(pts, x_axis=0.0):
    """Volume du profil polygonal tourné autour de la verticale x = x_axis."""
    a = sum((x0 - x_axis) * y1 - (x1 - x_axis) * y0 for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1])) / 2
    cx = sum(((x0 - x_axis) + (x1 - x_axis)) * ((x0 - x_axis) * y1 - (x1 - x_axis) * y0)
             for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1])) / (6 * a)
    return 2 * math.pi * abs(a) * cx


def surfaces(infos, genre):
    """Surfaces d'un genre : le noyau écrit chaque surface de révolution en deux moitiés."""
    n = sum(i['genre'] == genre for i in infos)
    assert n % 2 == 0, (genre, n)
    return n // 2


SHAFT = [(10, 0), (25, 0), (25, 30), (20, 30), (20, 48), (18, 50), (10, 50)]       # axe : le bord gauche, x = 10
AXIS = poly([(0, -5), (0, 60)], False)


class _Case(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.d = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def path(self, name):
        return os.path.join(self.d, name)

    def solid(self, path, name='piece'):
        """Les pièces, écrites : solides fermés, bien tournés, géométrie juste ; (pièces, infos des faces)."""
        bs = RV.bodies(path, name)
        p = self.path(f'{name}.step')
        B.write(p, bs, name)
        text = _text(p)
        self.assertEqual(geometry_errors(text), [], name)
        top = topology(text)
        self.assertEqual(len(top), len(bs), name)
        self.assertFalse(any(t[-1] for t in top), name)                   # chaque arête bordée deux fois
        self.assertEqual(misoriented(text, lambda q: any(B.contains(b, q) for b in bs)), [], name)
        return bs, part(p)[2]


class TestCore(_Case):
    def test_stepped_shaft(self):
        (b,), infos = self.solid(Path([poly(SHAFT)]), 'arbre')
        self.assertAlmostEqual(B.volume(b) / pappus(SHAFT, 10), 1.0, delta=1e-9)
        self.assertEqual(placed_bounds(b), [-15, -15, 0, 15, 15, 50])     # axe Z, bas du profil à Z = 0
        self.assertEqual(surfaces(infos, 'cylindre'), 2)                  # Ø30 et Ø20
        self.assertEqual(surfaces(infos, 'cone'), 1)                      # le chanfrein
        self.assertEqual(sorted({round(i["rayon"], 6) for i in infos if i["genre"] == "cylindre"}), [10.0, 15.0])
        s = RV.summary(Path([poly(SHAFT)]))
        self.assertEqual((s['profiles'], s['axis'], s['diameter'], s['height']), (1, 'gauche', 30.0, 50.0))

    def test_axis_line(self):
        ring = [(8, 0), (15, 0), (15, 12), (8, 12)]                        # bague, l'axe tracé à x = 0
        (b,), infos = self.solid(Path([poly(ring), AXIS]), 'bague')
        self.assertAlmostEqual(B.volume(b) / pappus(ring), 1.0, delta=1e-9)
        self.assertFalse(B.contains(b, (0, 0, 6)) or B.contains(b, (7.9, 0, 6)))
        self.assertTrue(B.contains(b, (0, 8.1, 6)))
        self.assertEqual(RV.summary(Path([poly(ring), AXIS]))['axis'], 'trait')
        prof = [(0, 5), (40, 5), (40, 15), (25, 15), (25, 21), (0, 21)]   # axe horizontal tracé vers la gauche
        (b,), _i = self.solid(Path([poly(prof), poly([(60, 5), (-10, 5)], False)]), 'horizontal')
        self.assertEqual(placed_bounds(b), [-16, -16, 0, 16, 16, 40])     # Z le long de +X du dessin
        self.assertTrue(B.contains(b, (15, 0, 10)) and not B.contains(b, (15, 0, 30)))
        left = [(-10, 0), (0, 0), (0, 10), (-10, 10)]                     # à gauche de l'axe : retourné
        (b,), _i = self.solid(Path([poly(left), poly([(0, -1), (0, 11)], False)]), 'gauche')
        self.assertAlmostEqual(B.volume(b) / (math.pi * 1000), 1.0, delta=1e-9)

    def test_sphere_and_tip(self):
        half = Contour(arc_conics((0, 0), 10, 10, -90, 180) + [Line((0, 10), (0, -10))], True)
        (b,), infos = self.solid(Path([half]), 'boule')
        self.assertAlmostEqual(B.volume(b) / (4 / 3 * math.pi * 1000), 1.0, delta=1e-6)   # pôles arrêtés à TIP
        self.assertEqual(surfaces(infos, 'sphere'), 2)                    # coupée à l'équateur
        cone = [(0, 0), (6, 0), (6, 20), (0, 30)]                          # pointe de centre
        (b,), infos = self.solid(Path([poly(cone)]), 'pointe')
        top = 20 + 10 * (1 - RV.TIP / 6)
        self.assertAlmostEqual(placed_bounds(b)[5], top, 5)
        self.assertAlmostEqual(B.volume(b) / pappus(cone), 1.0, delta=1e-6)
        self.assertEqual(surfaces(infos, 'cone'), 1)
        dome = Contour([Line((0, 0), (10, 0)), Line((10, 0), (10, 5))] + arc_conics((0, 5), 10, 10, 0, 90)
                       + [Line((0, 15), (0, 0))], True)
        (b,), _i = self.solid(Path([dome]), 'dome')
        self.assertAlmostEqual(B.volume(b) / (math.pi * 500 + 2 / 3 * math.pi * 1000), 1.0, delta=1e-6)

    def test_torus_groove_and_edges(self):
        (b,), _i = self.solid(Path([circle((20, 0), 4), AXIS]), 'tore')   # arcs hors de l'axe : des cônes
        self.assertAlmostEqual(B.volume(b) / (2 * math.pi ** 2 * 20 * 16), 1.0, delta=0.005)
        pulley = [(5, 0), (30, 0), (30, 4), (24, 10), (30, 16), (30, 20), (5, 20)]   # poulie à gorge en V
        (b,), infos = self.solid(Path([poly(pulley), AXIS]), 'poulie')
        self.assertAlmostEqual(B.volume(b) / pappus(pulley), 1.0, delta=1e-9)
        self.assertEqual(surfaces(infos, 'cone'), 2)                      # les deux flancs de la gorge
        knife = [(0, 0), (5, 0), (5, 10)]                                  # couteau en haut, creux conique
        (b,), _i = self.solid(Path([poly(knife), AXIS]), 'couteau')
        self.assertAlmostEqual(B.volume(b) / pappus(knife), 1.0, delta=0.002)

    def test_two_parts(self):
        lo, hi = [(0, 10), (8, 10), (8, 12), (0, 12)], [(0, 0), (5, 0), (5, 5), (0, 5)]
        bs, _i = self.solid(Path([poly(lo), poly(hi)]), 'deux')
        self.assertEqual([b.name for b in bs], ['deux_1', 'deux_2'])      # de bas en haut
        self.assertAlmostEqual(B.volume(bs[0]) / pappus(hi), 1.0, delta=1e-9)
        self.assertEqual(placed_bounds(bs[1])[2::3], [10, 12])

    def test_refusals(self):
        sq = poly([(5, 0), (15, 0), (15, 10), (5, 10)])
        for path, word in ((Path([poly([(-5, 0), (5, 0), (5, 10), (-5, 10)]), AXIS]), 'deux côtés'),
                           (Path([poly([(0, 0), (20, 0), (20, 20), (0, 20)]), poly([(5, 5), (10, 5), (10, 10), (5, 10)])]),
                            'vide'),
                           (Path([sq, poly([(15, 0), (20, 0), (20, 10), (15, 10)]), AXIS]), 'touchent'),
                           (Path([sq, AXIS, poly([(30, 0), (30, 10)], False)]), 'un seul'),
                           (Path([poly([(5, 0), (15, 10), (15, 0), (5, 10)]), AXIS]), 'recoupe'),
                           (Path([AXIS]), 'fermé'),
                           (Path([poly([(5, 0), (0, 10), (5, 20)]), AXIS]), 'pincé')):
            with self.assertRaises(D.DrawError, msg=word) as cm:
                RV.bodies(path)
            self.assertIn(word, str(cm.exception))


    def test_review(self):
        """Relecture : petit plat des extrêmes à la largeur TIP, coin fin, sommets quasi sur l'axe, vide fermé
        dans un même profil, arc tangent à l'axe."""
        rhomb = [(5, 0), (15, 0), (15, 9), (10, 10), (5, 9)]              # parois presque à plat au sommet
        (b,), _i = self.solid(Path([poly(rhomb), AXIS]), 'losange')
        self.assertAlmostEqual(placed_bounds(b)[5], 10 - RV.TIP / 5, 5)    # raccourcie de TIP / 5, pas de TIP
        self.assertAlmostEqual(B.volume(b) / pappus(rhomb), 1.0, delta=1e-4)
        wedge = [(4, 0), (5, 0), (10, 10)]                                  # parois presque parallèles
        (b,), _i = self.solid(Path([poly(wedge), AXIS]), 'coin')
        self.assertAlmostEqual(B.volume(b) / pappus(wedge), 1.0, delta=0.01)
        near = [(0.004, 0), (10, 0), (10, 10), (0.004, 10)]                 # à 4 µm de l'axe : sur l'axe
        (b,), _i = self.solid(Path([poly(near), AXIS]), 'plein')
        self.assertAlmostEqual(B.volume(b) / (math.pi * 1000), 1.0, delta=1e-9)
        self.assertTrue(B.contains(b, (0, 0, 5)))
        hollow = [(0, 0), (10, 0), (10, 20), (0, 20), (0, 15), (5, 15), (5, 5), (0, 5)]
        for path, word in ((Path([poly(hollow), AXIS]), 'vide fermé'),
                           (Path([circle((4, 0), 4), AXIS]), 'tangent'),
                           (Path([circle((4.005, 0), 4), AXIS]), 'tangent')):
            with self.assertRaises(D.DrawError, msg=word) as cm:
                RV.bodies(path)
            self.assertIn(word, str(cm.exception))


class TestDialog(_Case):
    def test_turned(self):
        from vectordrive.ui.drawing_step_dialog import DrawingStepDialog
        d = DrawingStepDialog(None, Path([poly(SHAFT)]), folder=self.d, name='arbre', shape='tournee')
        self.assertFalse(d.thickness.isEnabled() or d.mode.isEnabled() or d.pocket.isEnabled())
        self.assertIn('1 profil(s), autour du bord gauche du profil', d.summary.text())
        self.assertIn('Ø 30 × 50 mm', d.summary.text())
        self.assertEqual(len(d.bodies), 1)
        self.assertIn('tournée', d.info.text())
        out = d.save(self.path('arbre.step'))
        self.assertEqual([b.name for b in X.bodies(out)], ['arbre'])
        d.set_values(shape='extrudee', thickness=5.0)                       # la même pièce extrudée
        self.assertTrue(d.thickness.isEnabled())
        self.assertEqual(d.bodies[0].slabs[0].z1, 5.0)
        self.assertIn('contours fermés', d.summary.text())
        d.set_values(shape='tournee')
        self.assertAlmostEqual(B.volume(d.bodies[0]) / pappus(SHAFT, 10), 1.0, delta=1e-9)
        d.deleteLater()
        d = DrawingStepDialog(None, Path([poly([(-5, 0), (5, 0), (5, 10), (-5, 10)]), AXIS]), folder=self.d,
                              shape='tournee')
        self.assertEqual(d.bodies, [])
        self.assertIn('deux côtés', d.info.text())
        self.assertFalse(d.b_save.isEnabled())
        d.deleteLater()


class TestWindow(_Case):
    def setUp(self):
        super().setUp()
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.w.step_depot_folder(self.d)

    def tearDown(self):
        for i in range(len(self.w.docs)):
            self.w.docs[i].modified = False
        self.w.modified = False
        self.w.close()
        super().tearDown()

    def test_tab_and_selection(self):
        from tests.test_round672 import full_hd, tab_index
        from vectordrive.core.document import Shape
        w = self.w
        page = w.ribbon.page(tab_index(w.ribbon, 'Design STEP'))
        acts = [b.defaultAction() for g in page.groups() if g.title.text() == 'Générateurs' for b in g.buttons()]
        self.assertIn(w.A['stepgen_turned'], acts)
        self.assertEqual(page.fit(full_hd()), [])
        prof = Shape(path=Path([poly([(8, 0), (15, 0), (15, 12), (8, 12)])]))
        axis = Shape(path=Path([AXIS]))
        w._add_items([prof, axis])
        w.canvas.select([prof, axis])
        d = w.stepgen_drawing(exec_dialog=False, shape='tournee')
        self.assertEqual(d.shape.currentData(), 'tournee')
        self.assertIn('autour du trait droit choisi', d.summary.text())
        self.assertEqual(len(d.bodies), 1)
        out = d.open_step(confirm=False)
        self.assertTrue(out.startswith(os.path.join(self.d, 'Dessin')))
        self.assertEqual(len(X.bodies(out)), 1)
        d.deleteLater()


if __name__ == '__main__':
    unittest.main()
