"""Round 674 : onglet de ruban « Design STEP » — fenêtre des générateurs
(familles par catégorie, paramètres, aperçu ombré, volume et masse ;
enregistrer la pièce ou toute la gamme dans le dépôt STEP, ajouter au dessin
comme volume, ouvrir le STEP), dépôt dans le navigateur à vignettes ;
maillage fermé des pièces (`brep.mesh`)."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import brep as B
from vectordrive.core import stepgen as G
from tests.test_round672 import full_hd, tab_index

app = QApplication.instance() or QApplication([])


class TestMesh(unittest.TestCase):
    def test_closed_meshes(self):
        from vectordrive.core import solids as SO
        for key in G.FAMILIES:
            for b in G.build(key, G.values(key)):
                s = SO.from_triangles(B.mesh(b), key)                     # fermé, orienté : sinon SolidError
                self.assertAlmostEqual(s.volume() / B.volume(b), 1.0, delta=0.005, msg=key)

    def test_outward_and_placed(self):
        import numpy as np
        b = B.Body('bague', [B.Slab(0, 8, [B.Circle(0, 0, 10), B.Circle(0, 0, 4)])])
        T = B.mesh(b)
        vol = float(np.einsum('ij,ij->i', T[:, 0], np.cross(T[:, 1], T[:, 2])).sum() / 6.0)
        self.assertGreater(vol, 0)                                         # normales vers l'extérieur
        b.matrix = B.translation(100, 50, -8)
        lo = B.mesh(b).reshape(-1, 3).min(axis=0)
        self.assertEqual([round(float(x), 6) for x in lo], [90, 40, -8])

    def test_folder_names(self):
        names = {k: G.folder_name(k) for k, f in G.FAMILIES.items() if f.series is not None}
        self.assertEqual(names['chc'], 'Vis_CHC_ISO4762')
        self.assertEqual(len(set(names.values())), len(names))              # une gamme par dossier
        for n in names.values():
            self.assertRegex(n, r'^[A-Za-z0-9_.-]+$')


class TestDialogAlone(unittest.TestCase):
    def setUp(self):
        from vectordrive.ui.stepgen_dialog import StepGenDialog
        self.dir = tempfile.mkdtemp()
        self.d = StepGenDialog(None, folder=self.dir)

    def tearDown(self):
        self.d.deleteLater()

    def test_every_family_previews(self):
        d = self.d
        for key in G.FAMILIES:
            d.select_family(key)
            self.assertEqual(d.error, '', key)
            self.assertIsNotNone(d.preview.tris, key)
            self.assertIn('cm³', d.info.text(), key)
            d.preview.resize(300, 300)
            d.preview.grab()                                              # rendu sans erreur

    def test_save_and_error(self):
        d = self.d
        d.select_family('chc')
        d.set_value('size', 'M4')
        d.set_value('length', 12.0)
        self.assertIn('Vis_CHC_ISO4762_M4x12.step', d.info.text())
        p = d.save()
        self.assertEqual(pathlib.Path(p), pathlib.Path(self.dir) / 'Visserie' / 'Vis_CHC_ISO4762_M4x12.step')
        self.assertTrue(os.path.getsize(p) > 1000)
        self.assertEqual(d.save(confirm=False), p)                        # remplacé sans demander
        d.select_family('plaque')
        d.set_value('pattern', 'grille')
        d.set_value('nx', 30)
        self.assertIn('trous qui se touchent', d.error)
        self.assertFalse(d.b_save.isEnabled())
        self.assertIsNone(d.save())
        self.assertIsNone(d.preview.tris)
        self.assertFalse(d.b_add.isEnabled())                             # sans fenêtre principale

    def test_series(self):
        d = self.d
        d.select_family('ecrou')
        files = d.save_series(ask=False)
        self.assertEqual(len(files), len(G.ISO4032))
        self.assertTrue(all(pathlib.Path(f).parent.name == 'Ecrou_H_ISO4032' for f in files))
        d.select_family('clavette')
        self.assertFalse(d.b_series.isEnabled())
        self.assertEqual(d.save_series(ask=False), [])

    def test_category_preset(self):
        from vectordrive.ui.stepgen_dialog import StepGenDialog
        d = StepGenDialog(None, 'Moule', folder=self.dir)
        self.assertEqual(G.FAMILIES[d.key].category, 'Moule')
        d.deleteLater()


class TestRibbonAndDrawing(unittest.TestCase):
    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.dir = tempfile.mkdtemp()
        self.w.step_depot_folder(self.dir)

    def tearDown(self):
        for i in range(len(self.w.docs)):
            self.w.docs[i].modified = False
        self.w.modified = False
        self.w.close()

    def test_tab(self):
        r = self.w.ribbon
        titles = [r.tabText(i) for i in range(r.count())]
        self.assertLess(titles.index('Design STEP'), titles.index('FAO 2D'))
        page = r.page(tab_index(r, 'Design STEP'))
        self.assertEqual([g.title.text() for g in page.groups()], ['Générateurs', 'Sélection 3D', 'Modifier un STEP',
                                                                'Dépôt STEP'])
        acts = [b.defaultAction() for g in page.groups() for b in g.buttons()]
        A = self.w.A
        for k in ('stepgen', 'stepgen_visserie', 'stepgen_transmission', 'stepgen_brut', 'stepgen_moule',
                  'step_depot', 'step_depot_folder'):
            self.assertIn(A[k], acts, k)
        self.assertTrue(page.fit(full_hd()))                    # tient en 1920 (sans défiler, 1094)

    def test_dialog_from_window(self):
        w = self.w
        d = w.stepgen_dialog('Transmission', exec_dialog=False)
        self.assertEqual(d.folder, self.dir)
        self.assertEqual(G.FAMILIES[d.key].category, 'Transmission')
        d.select_family('roulement')
        new = d.add_to_drawing()
        self.assertEqual(len(new), 1)
        self.assertEqual(new[0].extra['stepgen']['key'], 'roulement')
        from vectordrive.core import solids as SO
        s = SO.of_item(new[0])
        x0, y0, z0, x1, y1, z1 = s.bounds()
        plate = w.canvas.doc.plate
        cx = plate.x + plate.width / 2 if plate is not None else 0.0
        self.assertAlmostEqual((x0 + x1) / 2, cx, 3)                       # au centre de la plaque
        self.assertAlmostEqual(z1 - z0, 7.0, 3)
        w.undo()
        self.assertEqual(SO.doc_solids(w.canvas.doc), [])
        n = len(w.docs)
        p = d.open_step()
        self.assertTrue(os.path.exists(p))
        self.assertEqual(len(w.docs), n + 1)
        self.assertEqual(w.view_mode(), '3d')
        from vectordrive.io import model3d
        self.assertEqual(model3d.source_of(w.canvas.doc), p)
        d.deleteLater()

    def test_depot_browser(self):
        w = self.w
        dlg = w.step_depot(exec_dialog=False)
        self.assertEqual(pathlib.Path(dlg.panel._folder), pathlib.Path(self.dir))         # le dépôt montré
        dlg.deleteLater()



class TestReview(unittest.TestCase):
    """Relecture : bague à grand chanfrein, boucles confondues, écriture sûre, grandes grilles, Entrée, valeurs
    en attente, placement dans le dessin, aperçu vide, filtre du dépôt."""

    def test_bush_chamfer_and_same_loops(self):
        from vectordrive.core import solids as SO
        for c in (1.0, 1.5, 2.0, 5.0):
            b = G.build('bague', G.values('bague', d=10, D=16, chamfer=c))[0]
            s = SO.from_triangles(B.mesh(b), 'bague')                    # fermé : sinon SolidError
            self.assertAlmostEqual(s.volume() / B.volume(b), 1.0, delta=0.005)
        same = B.Body('x', [B.Slab(0, 5, [B.Circle(0, 0, 5), B.Circle(0, 0, 5)])])
        with self.assertRaises(B.BrepError):
            B.check(same)

    def test_write_keeps_file_on_error(self):
        d = tempfile.mkdtemp()
        p = os.path.join(d, 'a.step')
        B.write(p, [B.Body('ok', [B.Slab(0, 5, [B.Circle(0, 0, 5)])])])
        before = pathlib.Path(p).read_text(encoding='ascii')
        bad = B.Body('pointe', [B.Slab(0, 5, [B.Poly([(0, 0), (10, 0), (10, 10), (0, 10)], scale_top=0.0,
                                                      center=(5, 5))])])
        with self.assertRaises(ValueError):
            B.write(p, [bad])
        self.assertEqual(pathlib.Path(p).read_text(encoding='ascii'), before)
        self.assertEqual(sorted(os.listdir(d)), ['a.step'])

    def test_big_grid(self):
        import time
        t = time.time()
        b = G.build('plaque', G.values('plaque', length=1000, width=1000, pattern='grille', nx=25, ny=25,
                                       hole='passage', size='M3'))[0]
        T = B.mesh(b)
        self.assertLess(time.time() - t, 8.0)                             # 208 s avant la relecture
        from vectordrive.core import solids as SO
        SO.from_triangles(T, 'grille')
        with self.assertRaises(G.GenError):
            G.build('plaque', G.values('plaque', pattern='grille', nx=26, ny=25, length=1000, width=1000))

    def test_preview_empty_and_culled(self):
        import numpy as np
        from vectordrive.ui.stepgen_dialog import Preview
        pv = Preview()
        pv.resize(200, 200)
        pv.set_bodies([(np.zeros((0, 3, 3)), (1.0, 0.0, 0.0))])
        self.assertIsNone(pv.tris)
        pv.grab()
        pv.set_bodies([(np.array([[[0, 0, 0], [0, 1, 0], [1, 0, 0]]], float), (1.0, 0.0, 0.0))])
        pv.yaw, pv.pitch = 0.0, 1.5708                                    # le seul triangle vu de dos
        pv.grab()
        pv.yaw, pv.pitch = 0.0, -1.5708
        pv.grab()

    def test_enter_and_pending_values(self):
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QPushButton
        from vectordrive.ui.stepgen_dialog import StepGenDialog
        d = StepGenDialog(None, None, 'barre', tempfile.mkdtemp())
        self.assertFalse(any(b.autoDefault() or b.isDefault() for b in d.findChildren(QPushButton)))
        w = d.widgets['length']
        self.assertFalse(w.keyboardTracking())
        QTest.keyClick(w, Qt.Key.Key_Return)                              # pas de choix de dossier
        w.setValue(123.0)                                                 # minuterie en attente
        self.assertTrue(d._timer.isActive())
        path = d.save(confirm=False)
        self.assertIn('123', os.path.basename(path))                      # la pièce à jour, pas l'ancienne
        d.deleteLater()


class TestReviewDrawing(unittest.TestCase):
    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.dir = tempfile.mkdtemp()
        self.w.step_depot_folder(self.dir)

    def tearDown(self):
        for i in range(len(self.w.docs)):
            self.w.docs[i].modified = False
        self.w.modified = False
        self.w.close()

    def test_centered_on_plate_and_pending(self):
        from vectordrive.core import solids as SO
        w = self.w
        plate = w.canvas.doc.plate
        cx, cy = (plate.x + plate.width / 2, plate.y + plate.height / 2) if plate is not None else (0.0, 0.0)
        for fam, over in (('plaque', {}), ('fhc', {}), ('barre', {'shape': 'corniere'})):
            d = w.stepgen_dialog(None, exec_dialog=False)
            d.select_family(fam)
            for k, v in over.items():
                d.set_value(k, v)
            if fam == 'plaque':
                d.widgets['length'].setValue(140.0)                       # en attente à l'appui du bouton
            new = d.add_to_drawing()
            self.assertEqual(len(new), 1, fam)
            x0, y0, z0, x1, y1, z1 = SO.of_item(new[0]).bounds()
            self.assertAlmostEqual((x0 + x1) / 2, cx, 3, fam)
            self.assertAlmostEqual((y0 + y1) / 2, cy, 3, fam)
            self.assertAlmostEqual(z0, 0.0, 3, fam)                       # posée sur Z = 0
            if fam == 'plaque':
                self.assertAlmostEqual(x1 - x0, 140.0, 3)
                self.assertEqual(new[0].extra['stepgen']['values']['length'], 140.0)
            w.undo()
            d.deleteLater()

    def test_depot_filter_not_saved(self):
        from vectordrive.ui.file_browser import FILTER_KEY
        w = self.w
        w.settings.setValue(FILTER_KEY, 2)                                # DXF retenu
        before = w._last_dir('ouvrir')
        dlg = w.step_depot(exec_dialog=False)
        self.assertIn('.step', [e.lower() for e in dlg.panel.EXTS])
        self.assertEqual(int(w.settings.value(FILTER_KEY)), 2)
        self.assertEqual(w._last_dir('ouvrir'), before)
        dlg.deleteLater()


if __name__ == '__main__':
    unittest.main()
