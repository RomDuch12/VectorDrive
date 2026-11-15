"""Round 676 : « Vis dans ce trou » (onglet Design STEP) — la paroi d'un
trou choisie, le trou reconnu dans n'importe quelle direction
(`core.screwfit` : passage, lamé, fraisé, taraudé ; débouchant ou borgne ;
côté de la tête), la vis normalisée proposée (taille, longueur) et posée
dans le trou et dans les mêmes trous ; vis seule ou avec la pièce dans un
STEP. Pièces d'essai : plaques percées du générateur, blocs à trou borgne."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import numpy as np
from PySide6.QtWidgets import QApplication

from vectordrive.core import brep as B
from vectordrive.core import screwfit as F
from vectordrive.core import stepgen as G
from vectordrive.io import step_extract as X
from vectordrive.io.neostep import step3d
from tests.test_round673 import geometry_errors, misoriented, topology

app = QApplication.instance() or QApplication([])


def part(path):
    m = step3d.lire_modele(path, axe_haut='Z')
    return np.asarray(m.triangles, float).reshape(-1, 3, 3), np.asarray(m.face_de), list(m.faces)


def _text(path):
    with open(path, encoding='latin-1') as f:
        return f.read()


def hole_face(infos, radius, tol=1e-6):
    return next(f for f, k in enumerate(infos)
                if k.get('genre') == 'cylindre' and k.get('creux') and abs(k['rayon'] - radius) < tol)


def block_with_hole(r, depth, total, at=(0, 0, 0), axis=(0, 0, 1), name='bloc'):
    """Un bloc 40 × 40 × `total`, trou borgne de rayon `r` et de profondeur `depth` ouvert en haut ; posé
    en `at`, son Z sur `axis`."""
    sq = B.rounded_rect(-20, -20, 20, 20)
    b = B.Body(name, [B.Slab(0, total - depth, [sq]), B.Slab(total - depth, total, [sq, B.Circle(0, 0, r)])])
    b.matrix = B.placement(at, axis)
    return b


class _Case(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.d = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def path(self, name):
        return os.path.join(self.d, name)

    def plate(self, hole, size='M6', thickness=12.0, flip=False):
        bodies = G.build('plaque', G.values('plaque', hole=hole, size=size, thickness=thickness))
        if flip:                                    # retournée : l'entrée du trou en dessous
            for b in bodies:
                b.matrix = B.placement((0, 0, thickness), (0, 0, -1), (1, 0, 0))
        p = self.path(f'plaque_{hole}_{size}{"_r" if flip else ""}.step')
        B.write(p, bodies, 'plaque')
        return p, bodies


class TestFit(_Case):
    def test_plate_holes(self):
        expect = {                                  # genre, famille, assise z, profondeur, longueur
            'passage': ('passage', 'chc', 12.0, 12.0, 25.0),
            'lamage': ('lamage', 'chc', 5.5, 5.5, 16.0),
            'fraisure': ('fraisure', 'fhc', 12.0, 12.0, 25.0),
            'taraude': ('taraude', 'chc', 12.0, 12.0, 12.0)}
        for hole, (kind, fam, z, depth, L) in expect.items():
            p, bodies = self.plate(hole)
            T, fo, infos = part(p)
            r = G.CLEARANCE['M6'] / 2 if hole != 'taraude' else (6 - G.PITCH['M6']) / 2
            fit = F.analyse(T, fo, infos, hole_face(infos, r))
            self.assertEqual((fit.kind, fit.through), (kind, True), hole)
            self.assertTrue(np.allclose(fit.axis, (0, 0, 1)), hole)
            self.assertAlmostEqual(float(fit.seat[2]), z, 3, hole)
            self.assertAlmostEqual(fit.depth, depth, 3, hole)
            self.assertEqual((fit.counterbore is not None), hole == 'lamage', hole)
            pr = F.propose(fit)
            self.assertEqual((pr['family'], pr['size'], pr['length'], pr['exact']), (fam, 'M6', L, True), hole)
            same = F.same_holes(T, fo, infos, fit)
            self.assertEqual(len(same), 4, hole)                         # les quatre coins
            self.assertEqual(len({(round(float(h.seat[0]), 3), round(float(h.seat[1]), 3)) for h in same}), 4)
            screws = [b for h in same for b in F.screw(h, pr['family'], pr['size'], pr['length'])]
            out = self.path(f'avec_vis_{hole}.step')
            B.write(out, bodies + screws, 'ensemble')
            self.assertEqual(len(topology(_text(out))), 5)
            self.assertEqual(geometry_errors(_text(out)), [])
            alone = self.path(f'vis_{hole}.step')                    # vis seules : la tête touche la plaque
            B.write(alone, screws, 'vis')
            self.assertEqual(misoriented(_text(alone), lambda q: any(B.contains(b, q) for b in screws)), [])
            for h, s in zip(same, screws):                               # la vis dans son trou, tête comprise
                head = B.mesh(s).reshape(-1, 3)
                self.assertLessEqual(float(head[:, 2].max()), 12.0 + 6.0 + 1e-6)
                if hole in ('lamage', 'fraisure'):
                    self.assertLessEqual(float(head[:, 2].max()), 12.0 + 1e-6, hole)     # noyée
                if hole != 'taraude':                                    # filets non représentés
                    lim = float(h.seat[2]) - (G.ISO10642['M6'][1] + 0.5 if hole == 'fraisure' else 0.5)
                    shank = head[head[:, 2] < lim]
                    self.assertLessEqual(float(np.linalg.norm(shank[:, :2] - h.seat[:2], axis=1).max()), r)

    def test_head_side_by_counterbore(self):
        p, _b = self.plate('lamage', flip=True)
        T, fo, infos = part(p)
        fit = F.analyse(T, fo, infos, hole_face(infos, G.CLEARANCE['M6'] / 2))
        self.assertEqual(fit.kind, 'lamage')
        self.assertTrue(np.allclose(fit.axis, (0, 0, -1)))              # le lamage dessous : la tête dessous
        self.assertAlmostEqual(float(fit.seat[2]), 6.5, 3)
        other = F.analyse(T, fo, infos, hole_face(infos, G.CLEARANCE['M6'] / 2), flip=True)
        self.assertTrue(np.allclose(other.axis, (0, 0, 1)))
        self.assertEqual(other.kind, 'passage')                          # de l'autre côté : pas de lamage
        self.assertAlmostEqual(float(other.seat[2]), 12.0, 3)

    def test_blind_hole_any_direction(self):
        for axis, at, seat in (((1, 0, 0), (100, 0, 0), (130, 0, 0)), ((0, -1, 0), (0, 50, 5), (0, 20, 5)),
                               ((0, 0, -1), (0, 0, 0), (0, 0, -30))):
            p = self.path('borgne.step')
            B.write(p, [block_with_hole(4.25, 25, 30, at, axis)], 'borgne')
            T, fo, infos = part(p)
            fit = F.analyse(T, fo, infos, hole_face(infos, 4.25))
            self.assertEqual((fit.kind, fit.through), ('taraude', False), axis)
            self.assertTrue(np.allclose(fit.axis, axis), axis)
            self.assertTrue(np.allclose(fit.seat, seat, atol=1e-6), (axis, fit.seat))
            self.assertAlmostEqual(fit.depth, 25.0, 3)
            pr = F.propose(fit)
            self.assertEqual((pr['family'], pr['size'], pr['length']), ('chc', 'M10', 20.0))   # ≤ 25 - 1,5
            with self.assertRaises(F.FitError):
                F.analyse(T, fo, infos, hole_face(infos, 4.25), flip=True)
            s = F.screw(fit, 'chc', 'M10', 20)[0]
            tip = B.mesh(s).reshape(-1, 3) @ np.asarray(axis, float)
            self.assertAlmostEqual(float(tip.min()), float(np.asarray(seat) @ np.asarray(axis, float)) - 20, 4)

    def test_short_blind_hole(self):
        p = self.path('court.step')
        B.write(p, [block_with_hole(4.25, 12, 20)], 'court')
        T, fo, infos = part(p)
        pr = F.propose(F.analyse(T, fo, infos, hole_face(infos, 4.25)))
        self.assertEqual((pr['size'], pr['length']), ('M10', 16.0))
        self.assertIn('trop court', pr['note'])

    def test_off_size_and_refusals(self):
        p = self.path('hors.step')
        sq = B.rounded_rect(-20, -20, 20, 20)
        B.write(p, [B.Body('b', [B.Slab(0, 10, [sq, B.Circle(0, 0, 3.8)])])], 'hors')
        T, fo, infos = part(p)
        fit = F.analyse(T, fo, infos, hole_face(infos, 3.8))
        pr = F.propose(fit)
        self.assertEqual((fit.kind, pr['size']), ('passage', 'M8'))      # Ø7,6 : au nominal M8 le plus proche
        self.assertFalse(pr['exact'])
        plane = next(f for f, k in enumerate(infos) if k.get('genre') == 'plan')
        with self.assertRaises(F.FitError):
            F.analyse(T, fo, infos, plane)
        with self.assertRaises(F.FitError):
            F.analyse(T, fo, infos, len(infos) + 3)
        p2 = self.path('lumiere.step')
        B.write(p2, [B.Body('b', [B.Slab(0, 10, [sq, B.slot(0, 0, 20, 6)])])], 'lumiere')
        T, fo, infos = part(p2)
        with self.assertRaises(F.FitError):                              # bout d'une lumière : demi-cylindre
            F.analyse(T, fo, infos, hole_face(infos, 3.0))
        p3 = self.path('axe.step')
        B.write(p3, [B.Body('axe', [B.Slab(0, 10, [B.Circle(0, 0, 3)])])], 'axe')
        T, fo, infos = part(p3)
        cyl = next(f for f, k in enumerate(infos) if k.get('genre') == 'cylindre')
        with self.assertRaises(F.FitError):                              # un bossage, pas un trou
            F.analyse(T, fo, infos, cyl)


def fit_of(test, name, bodies, r):
    """Le trou de rayon `r` (sa première paroi) de la pièce faite de `bodies`, et la vis proposée."""
    path = test.path(name)
    B.write(path, bodies, 'piece')
    T, fo, infos = part(path)
    fit = F.analyse(T, fo, infos, hole_face(infos, r))
    return fit, F.propose(fit)


SQ = B.rounded_rect(-20, -20, 20, 20)


class TestShapes(_Case):
    """Les formes qu'une première version lisait mal."""

    def test_chamfer_is_not_a_countersink(self):
        fit, pr = fit_of(self, 'taraude_chanfrein.step', [B.Body('b', [
            B.Slab(0, 9.25, [SQ, B.Circle(0, 0, 2.5)]), B.Slab(9.25, 10, [SQ, B.Circle(0, 0, 2.5, 3.25)])])], 2.5)
        self.assertEqual((fit.kind, pr['family'], pr['size']), ('taraude', 'chc', 'M6'))
        self.assertAlmostEqual(float(fit.seat[2]), 10.0, 6)                     # la tête au-dessus du chanfrein
        fit, pr = fit_of(self, 'passage_chanfrein.step', [B.Body('b', [
            B.Slab(0, 9.5, [SQ, B.Circle(0, 0, 3.3)]), B.Slab(9.5, 10, [SQ, B.Circle(0, 0, 3.3, 3.8)])])], 3.3)
        self.assertEqual((fit.kind, pr['family'], pr['size'], pr['length']), ('passage', 'chc', 'M6', 20.0))
        fit, pr = fit_of(self, 'lamage_chanfrein.step', [B.Body('b', [
            B.Slab(0, 5, [SQ, B.Circle(0, 0, 3.3)]), B.Slab(5, 5.3, [SQ, B.Circle(0, 0, 3.3, 3.6)]),
            B.Slab(5.3, 12, [SQ, B.Circle(0, 0, 5.5)])])], 3.3)
        self.assertEqual((fit.kind, pr['family']), ('lamage', 'chc'))
        self.assertAlmostEqual(float(fit.seat[2]), 5.3, 6)                      # le fond du lamage

    def test_counterbore_wall_picked(self):
        p, _b = self.plate('lamage')
        T, fo, infos = part(p)
        fit = F.analyse(T, fo, infos, hole_face(infos, G.COUNTERBORE['M6'] / 2))
        self.assertEqual((fit.kind, round(fit.radius, 6)), ('lamage', G.CLEARANCE['M6'] / 2))
        self.assertAlmostEqual(float(fit.seat[2]), 5.5, 6)

    def test_blind_holes_face_to_face(self):
        fit, pr = fit_of(self, 'entretoise.step', [B.Body('b', [
            B.Slab(0, 10, [SQ, B.Circle(0, 0, 2.5)]), B.Slab(10, 30, [SQ]),
            B.Slab(30, 40, [SQ, B.Circle(0, 0, 2.5)])])], 2.5)
        self.assertEqual((fit.kind, fit.through), ('taraude', False))           # pas un seul trou de 40
        self.assertAlmostEqual(fit.depth, 10.0, 6)

    def test_fine_series_and_spotface(self):
        for d, size in ((3.2, 'M3'), (4.3, 'M4'), (8.4, 'M8'), (10.5, 'M10')):
            fit, pr = fit_of(self, f'fine_{d}.step', [B.Body('b', [B.Slab(0, 10, [SQ, B.Circle(0, 0, d / 2)])])],
                             d / 2)
            self.assertEqual((fit.kind, pr['size'], pr['exact']), ('passage', size, True), d)
        fit, pr = fit_of(self, 'lamage_surface.step', [B.Body('b', [
            B.Slab(0, 5, [SQ]), B.Slab(5, 19, [SQ, B.Circle(0, 0, 2.5)]),
            B.Slab(19, 20, [SQ, B.Circle(0, 0, 8)])])], 2.5)
        self.assertEqual((fit.kind, pr['size']), ('taraude', 'M6'))             # lamage de surface : taraudé
        self.assertAlmostEqual(float(fit.seat[2]), 19.0, 6)

    def test_far_side_thickness(self):
        for hole in ('lamage', 'fraisure'):
            p, _b = self.plate(hole)
            T, fo, infos = part(p)
            fit = F.analyse(T, fo, infos, hole_face(infos, G.CLEARANCE['M6'] / 2), flip=True)
            self.assertEqual(fit.kind, 'passage', hole)
            self.assertAlmostEqual(fit.depth, 12.0, 6, hole)                    # toute la plaque traversée
            self.assertEqual(F.propose(fit)['length'], 25.0, hole)              # 12 + 1,5 × 6

    def test_screw_into_tapped_part_below(self):
        top = B.Body('A', [B.Slab(20, 25.5, [SQ, B.Circle(0, 0, 3.3)]), B.Slab(25.5, 32, [SQ, B.Circle(0, 0, 5.5)])])
        low = B.Body('B', [B.Slab(0, 20, [SQ, B.Circle(0, 0, 2.5)])])
        fit, pr = fit_of(self, 'empilees.step', [top, low], 3.3)
        self.assertEqual((fit.kind, fit.through), ('lamage', False))
        self.assertEqual((pr['size'], pr['length']), ('M6', 16.0))              # 5,5 + 1,5 × 6 dans B
        self.assertIn('taraudage', pr['note'])
        fit, pr = fit_of(self, 'empilees.step', [top, low], 2.5)
        self.assertEqual((fit.kind, pr['size']), ('taraude', 'M6'))             # le passage de A : pas un lamage

    def test_prepared_part(self):
        p, _b = self.plate('lamage')
        T, fo, infos = part(p)
        prep = F.Part(T, fo, infos)
        face = hole_face(infos, G.CLEARANCE['M6'] / 2)
        a, b = F.analyse(T, fo, infos, face), F.analyse(T, fo, infos, face, part=prep)
        self.assertTrue(np.allclose(a.seat, b.seat) and a.kind == b.kind and a.depth == b.depth)
        self.assertEqual(len(F.same_holes(T, fo, infos, b, part=prep)), 4)
        self.assertEqual(len(prep.holes), 8)                                    # 4 trous, 4 lamages


class TestDialog(_Case):
    def test_screws_written(self):
        from vectordrive.ui.screw_dialog import ScrewDialog
        p, bodies = self.plate('lamage')
        T, fo, infos = part(p)
        d = ScrewDialog(None, p, hole_face(infos, G.CLEARANCE['M6'] / 2))
        self.assertEqual(d.fit.kind, 'lamage')
        self.assertEqual(d.screw_values(), ('chc', 'M6', 16.0))
        self.assertTrue(d.all.isEnabled())
        self.assertIn('4', d.all.text())
        self.assertIn('lamé', d.hole.text())
        self.assertEqual(len(d.bodies()), 1)
        self.assertIsNotNone(d.preview.tris)
        d.all.setChecked(True)
        self.assertEqual(len(d.bodies()), 4)
        out = d.save(self.path('vis.step'))
        names = [b.name for b in X.bodies(out)]
        self.assertEqual(len(names), 4)
        self.assertTrue(all(n.startswith('Vis CHC ISO 4762 M6x16') for n in names))
        both = d.save_with_part(self.path('plaque_et_vis.step'))
        bs = X.bodies(both)
        self.assertEqual(len(bs), 5)
        self.assertEqual(bs[0].name, bodies[0].name)
        text = _text(both)
        self.assertEqual(geometry_errors(text), [])
        self.assertEqual(len(topology(text)), 5)
        d.set_screw('chc', 'M6', 20)
        self.assertEqual(d.screw_values(), ('chc', 'M6', 20.0))
        d.family.setCurrentIndex(d.family.findData('bhc'))
        self.assertEqual(d.screw_values()[:2], ('bhc', 'M6'))            # taille gardée
        self.assertIn(d.screw_values()[2], F.lengths('bhc', 'M6'))
        d.flip.setChecked(True)                                           # la tête de l'autre côté
        self.assertTrue(np.allclose(d.fit.axis, (0, 0, -1)))
        self.assertEqual(d.fit.kind, 'passage')
        self.assertEqual(d.screw_values(), ('chc', 'M6', 25.0))           # la vis proposée de nouveau
        self.assertIn('de passage', d.note.text())
        d.deleteLater()

    def test_not_a_hole(self):
        from vectordrive.ui.screw_dialog import ScrewDialog
        p, _b = self.plate('passage')
        T, fo, infos = part(p)
        plane = next(f for f, k in enumerate(infos) if k.get('genre') == 'plan')
        d = ScrewDialog(None, p, plane)
        self.assertIsNone(d.fit)
        self.assertIn('trou', d.hole.text())
        self.assertFalse(d.b_save.isEnabled() or d.b_both.isEnabled())
        self.assertIsNone(d.save(self.path('rien.step')))
        self.assertFalse(os.path.exists(self.path('rien.step')))
        self.assertFalse(d.flip.isEnabled() or d.all.isEnabled())
        d.deleteLater()

    def test_part_in_centimetres(self):
        from vectordrive.ui.screw_dialog import ScrewDialog
        blk = B.Body('cm', [B.Slab(0, 0.55, [B.rounded_rect(-2, -2, 2, 2), B.Circle(0, 0, 0.33)]),
                            B.Slab(0.55, 1.2, [B.rounded_rect(-2, -2, 2, 2), B.Circle(0, 0, 0.55)])])
        p = self.path('cm.step')
        with open(p, 'w', encoding='ascii') as f:
            f.write(B.step_text([blk], 'cm').replace('SI_UNIT(.MILLI.,.METRE.)', 'SI_UNIT(.CENTI.,.METRE.)'))
        T, fo, infos = part(p)
        d = ScrewDialog(None, p, hole_face(infos, 3.3))
        self.assertEqual((d.fit.kind, d.screw_values()), ('lamage', ('chc', 'M6', 16.0)))   # lu en mm
        self.assertIsNotNone(d.save(self.path('vis_cm.step')))
        self.assertIsNone(d.save_with_part(self.path('cm_et_vis.step')))   # unités différentes : dit
        self.assertIn('millimètres', d.hole.text())
        self.assertFalse(os.path.exists(self.path('cm_et_vis.step')))
        d.deleteLater()

    def test_blind_flip_disabled(self):
        from vectordrive.ui.screw_dialog import ScrewDialog
        p = self.path('borgne.step')
        B.write(p, [block_with_hole(2.5, 15, 20)], 'borgne')
        T, fo, infos = part(p)
        d = ScrewDialog(None, p, hole_face(infos, 2.5))
        self.assertEqual(d.fit.kind, 'taraude')
        self.assertFalse(d.flip.isEnabled())
        self.assertEqual(d.screw_values(), ('chc', 'M6', 12.0))           # ≤ 15 - 1
        self.assertFalse(d.all.isEnabled())
        d.deleteLater()


class TestWindow(_Case):
    """Le bouton du ruban sur la pièce du dessin : les faces choisies dans la vue 3D (une face plane puis la
    paroi d'un trou : la paroi retenue), rien de choisi : dit."""

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
        acts = [b.defaultAction() for g in page.groups() if g.title.text() == 'Modifier un STEP'
                for b in g.buttons()]
        self.assertIn(self.w.A['step_screw'], acts)
        self.assertEqual(page.fit(full_hd()), [])

    def test_faces_of_drawing(self):
        w = self.w
        p, _b = self.plate('lamage')
        self.assertIsNone(w.step_screw(exec_dialog=False))                # pas de pièce STEP : dit
        self.assertIn('trou', w.statusBar().currentMessage())
        self.assertTrue(w.open_path(p))
        w._ensure_panel3d()
        p3 = w.panel3d
        self.assertTrue(p3.refresh())
        self.assertIsNone(w.step_screw(exec_dialog=False))                # rien de choisi
        T, fo, infos = part(p)
        hole = hole_face(infos, G.CLEARANCE['M6'] / 2)
        plane = next(f for f, k in enumerate(infos) if k.get('genre') == 'plan')
        self.assertIn(hole, set(int(f) for f in p3.view.model.face_ids()))  # mêmes numéros que le lecteur
        p3.view.set_selection([plane, hole])
        d = w.step_screw(exec_dialog=False)
        self.assertEqual(os.path.normcase(d.path), os.path.normcase(p))
        self.assertEqual(d.face, hole)
        self.assertEqual(d.fit.kind, 'lamage')
        self.assertEqual(d.screw_values(), ('chc', 'M6', 16.0))
        out = d.save(self.path('vis.step'))
        self.assertEqual(len(X.bodies(out)), 1)
        d.deleteLater()
        p3.view.set_selection([plane])                                     # pas une paroi de trou : dit
        d = w.step_screw(exec_dialog=False)
        self.assertIsNone(d.fit)
        self.assertFalse(d.b_save.isEnabled())
        d.deleteLater()
        d = w.step_screw(p, 10 ** 6, exec_dialog=False)                   # numéro hors de la pièce
        self.assertIsNone(d.fit)
        d.deleteLater()


if __name__ == '__main__':
    unittest.main()
