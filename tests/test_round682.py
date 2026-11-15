"""Round 682 : « Pièce du dessin » (onglet Design STEP) — les contours
fermés choisis dans le dessin en pièce STEP à vraies faces (`core.stepdraw`) :
droites et arcs exacts, cercles en cylindres, bord le plus extérieur,
contours intérieurs en trous débouchants, en poches, ou ronds débouchants et
autres en poches ; îlots ; une pièce par bord ; refus dits."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import numpy as np
from PySide6.QtWidgets import QApplication

from vectordrive.core import brep as B
from vectordrive.core import screwfit as F
from vectordrive.core import stepdraw as D
from vectordrive.core.geom import Contour, Line, Path, circle, ellipse, rect, star
from vectordrive.io import step_extract as X
from tests.test_round673 import geometry_errors, topology
from tests.test_round676 import _text, hole_face, part

app = QApplication.instance() or QApplication([])


def volume(body):
    T = B.mesh(body).reshape(-1, 3, 3)
    return float(np.einsum('ij,ij->i', T[:, 0], np.cross(T[:, 1], T[:, 2])).sum() / 6.0)


bowtie = Contour([Line((5, 5), (15, 15)), Line((15, 15), (15, 5)), Line((15, 5), (5, 15)), Line((5, 15), (5, 5))], True)

_P = [(10 * math.cos(math.radians(90 + 144 * i)), 10 * math.sin(math.radians(90 + 144 * i))) for i in range(5)]
pentagram = Contour([Line(a, b) for a, b in zip(_P, _P[1:] + _P[:1])], True)      # étoile tracée d'un trait


def plate():
    """100 × 60, deux trous Ø6, une lumière 20 × 10."""
    return Path([rect(0, 0, 100, 60), circle((10, 10), 3), circle((90, 50), 3), rect(40, 25, 20, 10)])


class _Case(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.d = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def path(self, name):
        return os.path.join(self.d, name)

    def assertValid(self, bodies, n_shells=None):
        text = B.step_text(bodies, 'p')
        self.assertEqual(geometry_errors(text), [])
        shells = topology(text)
        self.assertEqual(len(shells), n_shells or len(bodies))
        self.assertTrue(all(not s[4] for s in shells), shells)         # arêtes bordées deux fois
        for b in bodies:
            self.assertGreater(volume(b), 0)


class TestCore(_Case):
    def test_loops(self):
        lps, left = D.loops(Path([rect(0, 0, 40, 20, 5), circle((5, 5), 2), ellipse((20, 10), 6, 3),
                                  star((30, 10), 5, 2, 5), Contour([Line((0, 30), (10, 30))], False)]))
        self.assertEqual(left, 1)                                         # le contour ouvert laissé
        r, c, e, s = lps
        self.assertIsInstance(r, B.Poly)
        self.assertEqual(sum(1 for x in r.bulges if abs(x - math.tan(math.pi / 8)) < 1e-9), 4)   # coins à 90°
        self.assertIsInstance(c, B.Circle)
        self.assertEqual((round(c.cx, 9), round(c.cy, 9), round(c.r, 9)), (5, 5, 2))
        self.assertIsInstance(e, B.Poly)                                  # ellipse : arcs tangents
        self.assertTrue(all(abs(x) > 0 for x in e.bulges))
        self.assertIsNone(s.bulges)                                       # étoile : droites
        self.assertEqual(len(s.pts), 10)
        info = D.summary(Path([rect(0, 0, 40, 20), circle((5, 5), 2)]))
        self.assertEqual((info['closed'], info['open'], info['circles']), (2, 0, 1))
        self.assertEqual(tuple(round(x, 6) for x in info['bounds']), (0, 0, 40, 20))

    def test_modes(self):
        holes, slot = 2 * math.pi * 9, 200.0
        expected = {'trous': (6000 - holes - slot) * 10, 'poches': 6000 * 10 - (holes + slot) * 3,
                    'ronds': (6000 - holes) * 10 - slot * 3}
        for mode, vol in expected.items():
            (b,) = D.bodies(plate(), 10.0, mode, 3.0, name=mode)
            self.assertValid([b])
            self.assertAlmostEqual(volume(b) / vol, 1.0, 3, mode)
            self.assertEqual(len(b.slabs), 1 if mode == 'trous' else 2, mode)
            self.assertEqual(b.name, mode)

    def test_islands_and_parts(self):
        island = Path([rect(0, 0, 60, 40), rect(10, 10, 40, 20), circle((30, 20), 4), circle((30, 20), 1.5)])
        pocket = 2400 * 8 - (800 - math.pi * 16) * 2                    # îlot rond dans la poche
        for mode, V in (('poches', pocket - math.pi * 2.25 * 2),          # le rond de l'îlot : une poche
                        ('ronds', pocket - math.pi * 2.25 * 8)):          # débouchant, îlot et fond
            (b,) = D.bodies(island, 8.0, mode, 2.0)
            self.assertValid([b])
            self.assertAlmostEqual(volume(b) / V, 1.0, 3, mode)
        with self.assertRaises(D.DrawError) as cm:                         # îlot dans un trou débouchant
            D.bodies(island, 8.0, 'trous')
        self.assertIn('détachée', str(cm.exception))
        two = Path([rect(60, 0, 40, 40), circle((80, 20), 5), rect(0, 0, 50, 30), circle((10, 10), 3)])
        bs = D.bodies(two, 6.0, name='plaque')
        self.assertEqual([b.name for b in bs], ['plaque_1', 'plaque_2'])  # de gauche à droite
        self.assertAlmostEqual(volume(bs[0]) / ((1500 - math.pi * 9) * 6), 1.0, 3)
        self.assertValid(bs)

    def test_refusals(self):
        for args, word in (((plate(), 0.0), 'épaisseur'), ((plate(), 10.0, 'poches', 10.0), 'profondeur'),
                           ((plate(), 10.0, 'poches', 0.0), 'profondeur'), ((plate(), 10.0, 'autre'), 'mode'),
                           ((Path([Contour([Line((0, 0), (10, 0))], False)]), 5.0), 'fermé'),
                           ((Path([rect(0, 0, 40, 20), rect(30, 10, 20, 20)]), 5.0), 'coupent'),
                           ((Path([rect(0, 0, 40, 20), circle((20, 10), 3), circle((22, 10), 3)]), 5.0), 'coupent'),
                           ((Path([bowtie]), 5.0), 'recoupe'), ((Path([rect(0, 0, 40, 20), bowtie]), 5.0), 'recoupe'),
                           ((Path([pentagram]), 5.0), 'recoupe')):
            with self.assertRaises(D.DrawError, msg=word) as cm:
                D.bodies(*args)
            self.assertIn(word, str(cm.exception))
        self.assertEqual(D.summary(Path([rect(0, 0, 40, 20), bowtie]))['bounds'], (0, 0, 40, 20))

    def test_tiny_segments(self):
        """Un segment ou un écart de fermeture sous le micron (DXF bruité) : laissé, la pièce s'écrit."""
        for gap in (1e-8, 1e-7, 5e-7, 1e-6):
            pts = [(0, 0), (20, 0), (20, 10), (0, 10), (gap, gap)]
            c = Contour([Line(a, b) for a, b in zip(pts, pts[1:])], True)
            bs = D.bodies(Path([c, circle((10, 5), 2)]), 4.0)
            self.assertEqual(len(bs[0].slabs[0].loops[0].pts), 4, gap)
            self.assertIsInstance(bs[0].slabs[0].loops[1], B.Circle)
            B.write(self.path('micro.step'), bs, 'micro')
            self.assertAlmostEqual(volume(bs[0]) / ((200 - math.pi * 4) * 4), 1.0, delta=1e-3)

    def test_holes_are_cylinders(self):
        """Les trous ronds écrits en vrais cylindres : « Vis dans ce trou » les reconnaît."""
        p = self.path('plaque.step')
        B.write(p, D.bodies(Path([rect(0, 0, 60, 40), circle((10, 10), 3.3), circle((50, 30), 3.3)]), 8.0), 'plaque')
        T, fo, infos = part(p)
        fit = F.analyse(T, fo, infos, hole_face(infos, 3.3))
        self.assertEqual((fit.kind, fit.through, round(fit.depth, 6)), ('passage', True, 8.0))
        self.assertEqual(len(F.same_holes(T, fo, infos, fit)), 2)


class TestDialog(_Case):
    def test_dialog(self):
        from vectordrive.ui.drawing_step_dialog import DrawingStepDialog
        d = DrawingStepDialog(None, plate(), folder=self.d, name='plaque test')
        self.assertIn('4 contours fermés, dont 2 ronds', d.summary.text())
        self.assertIn('100 × 60', d.summary.text())
        self.assertEqual(d.mode.currentData(), 'trous')
        self.assertFalse(d.pocket.isEnabled())
        self.assertEqual(len(d.bodies), 1)
        self.assertIsNotNone(d.preview.tris)
        self.assertEqual(d.target(), __import__('pathlib').Path(self.d) / 'Dessin' / 'plaque_test.step')
        d.set_values(mode='ronds', pocket=3.0, thickness=12.0)
        self.assertTrue(d.pocket.isEnabled())
        self.assertEqual(len(d.bodies[0].slabs), 2)
        out = d.save(self.path('plaque.step'))
        self.assertEqual([b.name for b in X.bodies(out)], ['plaque test'])
        self.assertEqual(geometry_errors(_text(out)), [])
        d.set_values(pocket=20.0)                                         # plus profonde que la pièce : dit
        self.assertEqual(d.bodies, [])
        self.assertFalse(d.b_save.isEnabled() or d.b_open.isEnabled())
        self.assertIn('profondeur', d.info.text())
        self.assertIsNone(d.save(self.path('rien.step')))
        self.assertFalse(os.path.exists(self.path('rien.step')))
        d.deleteLater()

    def test_dialog_guards(self):
        from unittest import mock
        from vectordrive.ui import drawing_step_dialog as M
        d = M.DrawingStepDialog(None, Path([rect(0, 0, 40, 20), bowtie]), folder=self.d)   # se recoupe : dit
        self.assertEqual(d.bodies, [])
        self.assertIn('recoupe', d.info.text())
        self.assertFalse(any(b.autoDefault() or b.isDefault() for b in (d.b_save, d.b_open)))   # Entrée : rien
        d.deleteLater()
        blocked = self.path('depot_fichier')                              # dépôt inutilisable : un fichier
        open(blocked, 'w').close()
        d = M.DrawingStepDialog(None, plate(), folder=blocked, name='p')
        with mock.patch.object(M.QFileDialog, 'getSaveFileName', return_value=('', '')) as ask:
            self.assertIsNone(d.save())
        self.assertEqual(ask.call_args[0][2], 'p.step')                   # proposé sans dossier
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

    def test_tab(self):
        from tests.test_round672 import full_hd, tab_index
        r = self.w.ribbon
        page = r.page(tab_index(r, 'Design STEP'))
        acts = [b.defaultAction() for g in page.groups() if g.title.text() == 'Générateurs' for b in g.buttons()]
        self.assertIn(self.w.A['stepgen_drawing'], acts)
        self.assertEqual(page.fit(full_hd()), [])

    def test_from_selection(self):
        from vectordrive.core.document import Shape
        w = self.w
        self.assertIsNone(w.stepgen_drawing(exec_dialog=False))           # rien de choisi : dit
        self.assertIn('fermées', w.statusBar().currentMessage())
        edge = Shape(path=Path([rect(0, 0, 80, 50, 4)]))
        holes = Shape(path=Path([circle((10, 10), 3.3), circle((70, 40), 3.3)]))
        line = Shape(path=Path([Contour([Line((0, 60), (80, 60))], False)]))
        w._add_items([edge, holes, line])
        w.canvas.select([line])
        self.assertIsNone(w.stepgen_drawing(exec_dialog=False))           # rien de fermé
        w.canvas.select([edge, holes, line])
        d = w.stepgen_drawing(exec_dialog=False)
        self.assertIn('3 contours fermés, dont 2 ronds ; 1 ouverts laissés', d.summary.text())
        self.assertEqual(len(d.bodies), 1)
        out = d.open_step(confirm=False)                                  # enregistrée au dépôt, ouverte en 3D
        self.assertTrue(os.path.exists(out))
        self.assertTrue(out.startswith(os.path.join(self.d, 'Dessin')))
        self.assertEqual(len(X.bodies(out)), 1)
        self.assertEqual(os.path.normcase(w.canvas.doc.source_path), os.path.normcase(out))
        d.deleteLater()


if __name__ == '__main__':
    unittest.main()
