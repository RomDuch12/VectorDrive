"""Round 677 : catégorie « Bridage » des générateurs STEP (onglet Design STEP) — bride de serrage plate à
lumière, cale étagée (profil extrudé, posé par sa matrice), mors doux à trous lamés, goujon de bridage ;
volumes, encombrements, solides fermés et bien tournés, refus dits ; trous du mors reconnus par « Vis dans ce
trou » ; fenêtre et ruban."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import numpy as np
from PySide6.QtWidgets import QApplication

from vectordrive.core import brep as B
from vectordrive.core import stepgen as G
from tests.test_round673 import geometry_errors, misoriented, topology

app = QApplication.instance() or QApplication([])

KEYS = ('bride', 'cale_etagee', 'mors_doux', 'goujon')


def _text(path):
    with open(path, encoding='latin-1') as f:
        return f.read()


def mesh_volume(b):
    from vectordrive.core import solids as SO
    return SO.from_triangles(B.mesh(b, n_arc=256), b.name).volume()


def placed_bounds(b):
    P = B.mesh(b).reshape(-1, 3)
    return [round(float(x), 6) + 0.0 for x in list(P.min(axis=0)) + list(P.max(axis=0))]


def slot_area(length, width):
    return (length - width) * width + math.pi * (width / 2) ** 2


class _Case(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.d = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def path(self, name):
        return os.path.join(self.d, name)

    def assertSolid(self, key, v):
        bodies = G.build(key, v)
        self.assertEqual(len(bodies), 1, key)
        p = self.path(f'{G.file_name(key, v)}.step')
        G.write(key, v, p)
        text = _text(p)
        self.assertEqual(geometry_errors(text), [], key)
        top = topology(text)
        self.assertEqual(len(top), 1, key)
        self.assertFalse(top[0][-1], key)                                    # chaque arête bordée deux fois
        self.assertEqual(misoriented(text, lambda q: B.contains(bodies[0], q)), [], key)
        return bodies[0], p


class TestBuild(_Case):
    def test_strap_clamp(self):
        v = G.values('bride')
        b, _p = self.assertSolid('bride', v)
        self.assertEqual(b.name, 'Bride 100x30x15 M10')
        self.assertEqual(placed_bounds(b), [0, -15, 0, 100, 15, 15])
        expect = (100 * 30 - slot_area(40, G.CLEARANCE['M10'])) * 15
        self.assertAlmostEqual(mesh_volume(b) / expect, 1.0, delta=0.002)
        for over in ({'slot': 96.0}, {'slot': 5.0}, {'width': 12.0}):
            with self.assertRaises(G.GenError, msg=over):
                G.build('bride', G.values('bride', **over))

    def test_step_block(self):
        v = G.values('cale_etagee', steps=4, step_height=8, step_depth=12, width=30)
        b, p = self.assertSolid('cale_etagee', v)
        self.assertEqual(placed_bounds(b), [0, 0, 0, 48, 30, 32])
        expect = sum(12 * 30 * 8 * i for i in range(1, 5))                 # colonne i : i marches de haut
        self.assertAlmostEqual(mesh_volume(b) / expect, 1.0, delta=0.001)
        T = B.mesh(b).reshape(-1, 3)
        self.assertLessEqual(float(T[np.isclose(T[:, 2], 32), 0].max()), 12 + 1e-6)   # la plus haute en X = 0
        self.assertGreaterEqual(float(T[np.isclose(T[:, 2], 8), 0].max()), 48 - 1e-6)  # la plus basse en X = 48
        from vectordrive.io import step_extract as X
        bs = X.bodies(p)
        self.assertEqual([x.name for x in bs], [b.name])
        from vectordrive.io.neostep import step3d
        m = step3d.lire_modele(p, axe_haut='Z')                           # le fichier aux mêmes coordonnées
        P = np.asarray(m.triangles, float).reshape(-1, 3)
        self.assertEqual([round(float(x), 6) + 0.0 for x in list(P.min(axis=0)) + list(P.max(axis=0))],
                         [0, 0, 0, 48, 30, 32])
        self.assertSolid('cale_etagee', G.values('cale_etagee', steps=1))

    def test_soft_jaw(self):
        v = G.values('mors_doux')
        b, _p = self.assertSolid('mors_doux', v)
        self.assertEqual(placed_bounds(b), [0, 0, 0, 150, 40, 20])
        prof = G._hole_profile('lamage', 'M8', 20.0)
        holes = 2 * sum(math.pi * c.r ** 2 * (z1 - z0) for z0, z1, c in prof)
        self.assertAlmostEqual(mesh_volume(b) / (150 * 40 * 20 - holes), 1.0, delta=0.002)
        for over in ({'hole_y': 37.0}, {'spacing': 145.0}, {'spacing': 10.0}):
            with self.assertRaises(G.GenError, msg=over):
                G.build('mors_doux', G.values('mors_doux', **over))

    def test_soft_jaw_holes_take_screws(self):
        from vectordrive.core import screwfit as F
        from vectordrive.io.neostep import step3d
        p = self.path('mors.step')
        G.write('mors_doux', G.values('mors_doux'), p)
        m = step3d.lire_modele(p, axe_haut='Z')
        T, fo, infos = np.asarray(m.triangles, float).reshape(-1, 3, 3), np.asarray(m.face_de), list(m.faces)
        face = next(f for f, k in enumerate(infos) if k.get('genre') == 'cylindre' and k.get('creux')
                    and abs(k['rayon'] - G.CLEARANCE['M8'] / 2) < 1e-6)
        fit = F.analyse(T, fo, infos, face)
        self.assertEqual((fit.kind, fit.through), ('lamage', True))
        self.assertTrue(np.allclose(fit.axis, (0, 0, 1)))                # la tête côté serrage
        pr = F.propose(fit)
        self.assertEqual((pr['family'], pr['size']), ('chc', 'M8'))
        self.assertEqual(len(F.same_holes(T, fo, infos, fit)), 2)

    def test_stud(self):
        b, _p = self.assertSolid('goujon', G.values('goujon'))
        self.assertEqual(b.name, 'Goujon M12x80')
        self.assertEqual(placed_bounds(b)[2::3], [0, 80])
        self.assertAlmostEqual(placed_bounds(b)[3], 6.0, 2)
        with self.assertRaises(G.GenError):
            G.build('goujon', G.values('goujon', size='M20', length=30.0))

    def test_names_and_category(self):
        self.assertEqual(G.CATEGORIES[-1], 'Bridage')
        self.assertEqual([k for k, f in G.FAMILIES.items() if f.category == 'Bridage'][:4], list(KEYS))
        names = set()
        for k in KEYS:
            n = G.file_name(k, G.values(k))
            self.assertRegex(n, r'^[A-Za-z0-9_.-]+$', k)
            self.assertIsNone(G.FAMILIES[k].series, k)
            names.add(n)
        self.assertNotEqual(G.file_name('mors_doux', G.values('mors_doux')),
                            G.file_name('mors_doux', G.values('mors_doux', hole_y=15.0)))   # tout dans le nom


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

    def test_tab_and_dialog(self):
        from tests.test_round672 import full_hd, tab_index
        w = self.w
        r = w.ribbon
        page = r.page(tab_index(r, 'Design STEP'))
        gen = next(g for g in page.groups() if g.title.text() == 'Générateurs')
        self.assertIn(w.A['stepgen_bridage'], [b.defaultAction() for b in gen.buttons()])
        self.assertEqual(page.fit(full_hd()), [])
        d = w.stepgen_dialog('Bridage', exec_dialog=False)
        self.assertEqual(G.FAMILIES[d.key].category, 'Bridage')
        for k in KEYS:
            d.select_family(k)
            self.assertEqual(d.key, k)
            self.assertFalse(d.error, k)
        d.select_family('cale_etagee')
        d.set_value('steps', 4)
        path = d.save(confirm=False)
        self.assertTrue(path.endswith('.step'))
        self.assertEqual(os.path.basename(os.path.dirname(path)), 'Bridage')
        new = d.add_to_drawing()
        self.assertEqual(len(new), 1)
        from vectordrive.core import solids as SO
        x0, y0, z0, x1, y1, z1 = SO.of_item(new[0]).bounds()
        self.assertAlmostEqual(z0, 0.0, 3)                                 # posée sur Z = 0, marches en Z
        self.assertAlmostEqual(z1 - z0, 40.0, 3)
        self.assertAlmostEqual(x1 - x0, 60.0, 3)
        w.undo()
        d.deleteLater()


if __name__ == '__main__':
    unittest.main()
