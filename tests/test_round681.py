"""Round 681 : « Pièce dans ce trou » (onglet Design STEP) — la paroi d'un
alésage choisie, l'alésage reconnu (`core.holefit` : axe, entrée, fond,
diamètre, profondeur ; débouchant ou borgne ; entrée retournée), une pièce
des générateurs (goupille, roulement, bague, douille, colonne, éjecteur,
bague de centrage) proposée au diamètre et posée dedans, dans les mêmes
alésages au besoin ; seule ou avec la pièce dans un STEP. Pièce d'essai :
plaque de moule percée (deux Ø6, Ø16, Ø4 débouchants ; Ø22 borgne de 7)."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import numpy as np
from PySide6.QtWidgets import QApplication

from vectordrive.core import brep as B
from vectordrive.core import holefit as H
from vectordrive.core import screwfit as F
from vectordrive.io import step_extract as X
from tests.test_round673 import geometry_errors, topology
from tests.test_round676 import _text, block_with_hole, hole_face, part

app = QApplication.instance() or QApplication([])


def plate(path):
    """Plaque 120 × 60 × 20 : Ø6 en (-40, 0) et (20, 16), Ø16 en (0, 0), Ø4 en (40, 0) débouchants ; Ø22
    borgne de 7 en (-40, 16) ouvert en haut."""
    sq = B.rounded_rect(-60, -30, 60, 30)
    through = [B.Circle(-40, 0, 3.0), B.Circle(20, 16, 3.0), B.Circle(0, 0, 8.0), B.Circle(40, 0, 2.0)]
    body = B.Body('plaque', [B.Slab(0, 13, [sq] + through),
                             B.Slab(13, 20, [sq] + through + [B.Circle(-40, 16, 11.0)])])
    B.write(path, [body], 'plaque')
    return path


def extent(bodies):
    """(Z mini, Z maxi) des pièces posées."""
    P = np.concatenate([B.mesh(b).reshape(-1, 3) for b in bodies])
    return round(float(P[:, 2].min()), 6), round(float(P[:, 2].max()), 6)


class _Case(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.d = self._tmp.name
        self.p = plate(self.path('plaque.step'))
        self.T, self.fo, self.infos = part(self.p)

    def tearDown(self):
        self._tmp.cleanup()

    def path(self, name):
        return os.path.join(self.d, name)

    def bore(self, r, flip=False):
        return H.bore(self.T, self.fo, self.infos, hole_face(self.infos, r), flip)


class TestFit(_Case):
    def test_bores(self):
        b = self.bore(3.0)
        self.assertEqual((b.diameter, b.depth, b.through), (6.0, 20.0, True))
        self.assertTrue(np.allclose(b.axis, (0, 0, 1)) and np.allclose(b.entry, (-40, 0, 20)))
        self.assertTrue(np.allclose(b.bottom, (-40, 0, 0)))
        b = self.bore(3.0, flip=True)                                     # entrée par le dessous
        self.assertTrue(np.allclose(b.axis, (0, 0, -1)) and np.allclose(b.entry, (-40, 0, 0)))
        b = self.bore(11.0)
        self.assertEqual((round(b.diameter, 6), round(b.depth, 6), b.through), (22.0, 7.0, False))
        self.assertTrue(np.allclose(b.entry, (-40, 16, 20)) and np.allclose(b.bottom, (-40, 16, 13)))
        with self.assertRaises(F.FitError):
            self.bore(11.0, flip=True)                                    # borgne : une seule entrée
        plane = next(f for f, k in enumerate(self.infos) if k.get('genre') == 'plan')
        for f in (plane, -1, 10 ** 6):
            with self.assertRaises(F.FitError):
                H.bore(self.T, self.fo, self.infos, f)

    def test_proposals_placed(self):
        """Chaque pièce à sa place : au ras de l'entrée, au fond, à travers ; dans le diamètre de l'alésage."""
        expected = {
            (3.0, 'goupille'): ({'d': 6.0, 'length': 20.0}, (0, 20)),
            (3.0, 'ejecteur'): ({'d1': 6.0, 'length': 25.0, 'd2': 10.0, 'k': 5.0}, (-5, 20)),
            (3.0, 'colonne'): ({'d': 6.0, 'length': 38.0, 'D': 14.0, 'h': 6.0}, (-6, 32)),
            (8.0, 'roulement'): ({'ref': '625'}, (15, 20)),
            (8.0, 'bague'): ({'d': 10.0, 'D': 16.0, 'length': 20.0, 'chamfer': 0.5}, (0, 20)),
            (8.0, 'douille'): ({'d': 10.0, 'D': 16.0, 'length': 25.0, 'D2': 21.0, 'h': 5.0}, (0, 25)),
            (8.0, 'bague_centrage'): ({'D': 16.0, 'd': 6.0, 'h': 12.0}, (8, 20)),
            (11.0, 'roulement'): ({'ref': '608'}, (13, 20)),
            (11.0, 'bague'): ({'d': 14.0, 'D': 22.0, 'length': 7.0, 'chamfer': 0.5}, (13, 20)),
            (11.0, 'bague_centrage'): ({'D': 22.0, 'd': 8.0, 'h': 12.0}, (13, 25)),
            (2.0, 'goupille'): ({'d': 4.0, 'length': 20.0}, (0, 20)),
        }
        for (r, fam), (values, (z0, z1)) in expected.items():
            b = self.bore(r)
            v = H.propose(b, fam)
            self.assertEqual({k: v[k] for k in values}, values, (r, fam))
            bodies = H.parts(b, fam, v)
            self.assertEqual(extent(bodies), (z0, z1), (r, fam))
            P = np.concatenate([B.mesh(x).reshape(-1, 3) for x in bodies])
            inside = P[(P[:, 2] > 0.01) & (P[:, 2] < 19.99) & (P[:, 2] < b.entry[2] - 0.01)
                       & (P[:, 2] > b.bottom[2] + 0.01)]               # dans l'épaisseur percée
            if len(inside):
                rad = np.hypot(inside[:, 0] - b.entry[0], inside[:, 1] - b.entry[1])
                self.assertLessEqual(rad.max(), r + 1e-6, (r, fam))
        b = self.bore(3.0, flip=True)                                     # retourné : la tête au-dessus
        self.assertEqual(extent(H.parts(b, 'ejecteur', H.propose(b, 'ejecteur'))), (0, 25))

    def test_refusals(self):
        for r, fam, word in ((11.0, 'goupille', 'goupille'), (3.0, 'roulement', 'roulement'),
                             (11.0, 'colonne', 'borgne'), (11.0, 'ejecteur', 'borgne'),
                             (3.0, 'bague_centrage', 'Diamètre'), (3.0, 'inconnue', 'inconnue')):
            with self.assertRaises(F.FitError, msg=(r, fam)) as cm:
                H.propose(self.bore(r), fam)
            self.assertIn(word, str(cm.exception))

    def body_bore(self, slabs, r, axis=(0, 0, 1), flip=False, name='b'):
        b = B.Body(name, slabs)
        b.matrix = B.placement((0, 0, 0), axis)
        p = self.path(f'{name}.step')
        B.write(p, [b], name)
        T, fo, infos = part(p)
        return H.bore(T, fo, infos, hole_face(infos, r), flip)

    def test_series_fit(self):
        """Goupilles de toute la liste du générateur ; jamais plus grosse que l'alésage (0,05 mm), au plus 0,5 mm
        plus petite ; plus longue qu'un débouchant : elle dépasse de la sortie, c'est dit."""
        b = self.bore(8.0)
        v = H.propose(b, 'goupille')
        self.assertEqual(v, {'d': 16.0, 'length': 35.0})                  # la plus courte (dès 2 d)
        bodies = H.parts(b, 'goupille', v)
        self.assertEqual(extent(bodies), (-15, 20))
        self.assertEqual(H.outside(b, bodies), (0.0, 15.0))
        sq = B.rounded_rect(-20, -20, 20, 20)
        for D, d in ((12.0, 12.0), (6.3, 6.0), (5.6, None), (5.9, None), (5.97, 6.0), (21.7, None)):
            b = self.body_bore([B.Slab(0, 30, [sq, B.Circle(0, 0, D / 2)])], D / 2, name=f'p{D:g}')
            if d is None:
                with self.assertRaises(F.FitError, msg=D):
                    H.propose(b, 'goupille')
            else:
                self.assertEqual(H.propose(b, 'goupille')['d'], d, D)
        with self.assertRaises(F.FitError):                               # 608 (Ø22) dans Ø21,7 : trop gros
            H.propose(self.body_bore([B.Slab(0, 30, [sq, B.Circle(0, 0, 10.85)])], 10.85, name='r'), 'roulement')

    def test_short_blind(self):
        """Plus longue qu'un borgne : posée au fond, elle dépasse de l'entrée, jamais dans la matière."""
        sq = B.rounded_rect(-20, -20, 20, 20)
        b = self.body_bore([B.Slab(0, 12, [sq]), B.Slab(12, 20, [sq, B.Circle(0, 0, 3.0)])], 3.0, name='g')
        v = H.propose(b, 'goupille')
        self.assertEqual(v, {'d': 6.0, 'length': 12.0})
        bodies = H.parts(b, 'goupille', v)
        self.assertEqual(extent(bodies), (12, 24))
        self.assertEqual(H.outside(b, bodies), (4.0, 0.0))
        b = self.body_bore([B.Slab(0, 15, [sq]), B.Slab(15, 20, [sq, B.Circle(0, 0, 11.0)])], 11.0, name='r')
        bodies = H.parts(b, 'roulement', H.propose(b, 'roulement'))
        self.assertEqual(extent(bodies), (15, 22))                        # 608 : 7 de large dans 5
        b = self.body_bore([B.Slab(0, 12, [sq]), B.Slab(12, 20, [sq, B.Circle(0, 0, 8.0)])], 8.0, name='d')
        v = dict(H.propose(b, 'douille'), length=20.0)                    # corps de 15 dans 8 de profondeur
        self.assertEqual(H.outside(b, H.parts(b, 'douille', v))[1], 0.0)

    def test_tilted_noise(self):
        """Axe quelconque : le bruit de calcul de la profondeur n'ajoute pas un millimètre."""
        sq = B.rounded_rect(-20, -20, 20, 20)
        b = self.body_bore([B.Slab(0, 20, [sq, B.Circle(0, 0, 8.0)])], 8.0, axis=(0.6, 0, -0.8), name='t')
        self.assertEqual((b.diameter, b.depth), (16.0, 20.0))
        self.assertEqual(H.propose(b, 'ejecteur')['length'], 27.0)
        self.assertEqual(H.propose(b, 'colonne')['length'], 58.0)
        self.assertEqual(H.outside(b, H.parts(b, 'ejecteur', H.propose(b, 'ejecteur'))), (0.0, 7.0))

    def test_shoulder(self):
        """Un alésage prolongé par un trou à peine plus étroit : l'épaulement le ferme (borgne)."""
        sq = B.rounded_rect(-20, -20, 20, 20)
        slabs = [B.Slab(0, 10, [sq, B.Circle(0, 0, 9.5)]), B.Slab(10, 20, [sq, B.Circle(0, 0, 10.0)])]
        b = self.body_bore(slabs, 10.0, name='e')
        self.assertFalse(b.through)
        self.assertEqual(b.depth, 10.0)
        self.assertTrue(np.allclose(b.entry, (0, 0, 20)))
        with self.assertRaises(F.FitError):
            self.body_bore(slabs, 10.0, flip=True, name='e2')
        with self.assertRaises(F.FitError):
            H.propose(b, 'colonne')
        b = self.body_bore(slabs, 9.5, name='e3')                          # le trou étroit : débouchant
        self.assertTrue(b.through)
        mid = [B.Slab(0, 5, [sq, B.Circle(0, 0, 4.0)]), B.Slab(5, 15, [sq, B.Circle(0, 0, 5.0)]),
               B.Slab(15, 20, [sq, B.Circle(0, 0, 4.0)])]
        with self.assertRaises(F.FitError):                               # épaulements des deux côtés
            self.body_bore(mid, 5.0, name='m')

    def test_same_bores(self):
        part_ = F.Part(self.T, self.fo, self.infos)
        b = H.bore(self.T, self.fo, self.infos, hole_face(self.infos, 3.0), part=part_)
        same = H.same_bores(self.T, self.fo, self.infos, b, part_)
        self.assertEqual(len(same), 2)
        self.assertIs(same[0], b)
        self.assertTrue(np.allclose(same[1].entry, (20, 16, 20)))
        b = H.bore(self.T, self.fo, self.infos, hole_face(self.infos, 3.0), True, part_)
        same = H.same_bores(self.T, self.fo, self.infos, b, part_)
        self.assertEqual([round(float(c.entry[2]), 6) for c in same], [0.0, 0.0])   # entrée du même côté
        for r in (8.0, 11.0, 2.0):
            self.assertEqual(len(H.same_bores(self.T, self.fo, self.infos, self.bore(r))), 1)

    def test_any_direction(self):
        p = self.path('bloc.step')
        B.write(p, [block_with_hole(4.0, 12, 20, at=(100, 0, 0), axis=(1, 0, 0))], 'bloc')
        T, fo, infos = part(p)
        b = H.bore(T, fo, infos, hole_face(infos, 4.0))
        self.assertFalse(b.through)
        self.assertTrue(np.allclose(b.axis, (1, 0, 0)) and np.allclose(b.entry, (120, 0, 0)))
        bodies = H.parts(b, 'bague', H.propose(b, 'bague'))
        P = np.concatenate([B.mesh(x).reshape(-1, 3) for x in bodies])
        self.assertAlmostEqual(float(P[:, 0].min()), 108.0, 6)
        self.assertAlmostEqual(float(P[:, 0].max()), 120.0, 6)
        self.assertLessEqual(float(np.hypot(P[:, 1], P[:, 2]).max()), 4.0 + 1e-6)


class TestDialog(_Case):
    def test_pins_written(self):
        from vectordrive.ui.part_hole_dialog import PartHoleDialog
        d = PartHoleDialog(None, self.p, hole_face(self.infos, 3.0))
        self.assertIn('Ø6', d.hole.text())
        self.assertIn('débouchant', d.hole.text())
        self.assertEqual(d.family.currentData(), 'goupille')
        self.assertEqual(d.current_values(), {'d': 6.0, 'length': 20.0})
        self.assertTrue(d.b_save.isEnabled() and d.flip.isEnabled())
        self.assertTrue(d.all.isEnabled())
        self.assertIn('2', d.all.text())
        self.assertEqual(len(d.bodies()), 1)
        self.assertIsNotNone(d.preview.tris)
        d.all.setChecked(True)
        self.assertEqual(len(d.bodies()), 2)
        out = d.save(self.path('goupilles.step'))
        names = [b.name for b in X.bodies(out)]
        self.assertEqual(names, ['Goupille ISO 2338 6x20 (1)', 'Goupille ISO 2338 6x20 (2)'])
        both = d.save_with_part(self.path('plaque_et_goupilles.step'))
        bs = X.bodies(both)
        self.assertEqual([b.name for b in bs][0], 'plaque')
        self.assertEqual(len(bs), 3)
        text = _text(both)
        self.assertEqual(geometry_errors(text), [])
        self.assertEqual(len(topology(text)), 3)
        d.set_value('length', 16.0)                                       # cote changée à la main
        self.assertEqual(d.current_values()['length'], 16.0)
        self.assertEqual(extent(d.bodies()), (4, 20))
        d.b_propose.click()
        self.assertEqual(d.current_values()['length'], 20.0)
        d.family.setCurrentIndex(d.family.findData('ejecteur'))
        self.assertEqual(d.current_values()['d1'], 6.0)
        self.assertIn('tête', d.note.text())
        d.flip.setChecked(True)                                           # entrée par le dessous
        self.assertTrue(np.allclose(d.bore.axis, (0, 0, -1)))
        d.all.setChecked(False)
        self.assertEqual(extent(d.bodies()), (0, 25))
        self.assertIn('dépasse de 5 mm de la sortie', d.info.text())     # la tête sous la sortie
        d.deleteLater()

    def test_not_fitting(self):
        from vectordrive.ui.part_hole_dialog import PartHoleDialog
        d = PartHoleDialog(None, self.p, hole_face(self.infos, 11.0))
        self.assertIn('borgne', d.hole.text())
        self.assertFalse(d.flip.isEnabled() or d.all.isEnabled())
        self.assertIn('Ne va pas', d.note.text())                         # pas de goupille Ø22
        self.assertFalse(d.b_save.isEnabled() or d.b_both.isEnabled())
        self.assertEqual(d.bodies(), [])
        self.assertIsNone(d.save(self.path('rien.step')))
        self.assertFalse(os.path.exists(self.path('rien.step')))
        d.family.setCurrentIndex(d.family.findData('roulement'))
        self.assertTrue(d.b_save.isEnabled())
        self.assertEqual(d.current_values(), {'ref': '608'})
        out = d.save(self.path('roulement.step'))
        self.assertEqual([b.name for b in X.bodies(out)], ['Roulement 608'])
        d.family.setCurrentIndex(d.family.findData('colonne'))
        self.assertFalse(d.b_save.isEnabled())
        self.assertIn('borgne', d.note.text())
        d.deleteLater()

    def test_not_a_bore(self):
        from vectordrive.ui.part_hole_dialog import PartHoleDialog
        plane = next(f for f, k in enumerate(self.infos) if k.get('genre') == 'plan')
        d = PartHoleDialog(None, self.p, [plane])
        self.assertIsNone(d.bore)
        self.assertIn('trou', d.hole.text())
        self.assertFalse(d.b_save.isEnabled() or d.b_both.isEnabled() or d.family.isEnabled())
        self.assertFalse(d.flip.isEnabled() or d.all.isEnabled())
        self.assertIsNone(d.save_with_part(self.path('rien.step')))
        d.deleteLater()
        d = PartHoleDialog(None, self.p, [plane, hole_face(self.infos, 8.0)])   # la paroi retenue
        self.assertEqual(round(d.bore.diameter, 6), 16.0)
        d.deleteLater()

    def test_part_in_centimetres(self):
        from vectordrive.ui.part_hole_dialog import PartHoleDialog
        blk = B.Body('cm', [B.Slab(0, 2, [B.rounded_rect(-4, -4, 4, 4), B.Circle(0, 0, 0.3)])])
        p = self.path('cm.step')
        with open(p, 'w', encoding='ascii') as f:
            f.write(B.step_text([blk], 'cm').replace('SI_UNIT(.MILLI.,.METRE.)', 'SI_UNIT(.CENTI.,.METRE.)'))
        T, fo, infos = part(p)
        d = PartHoleDialog(None, p, hole_face(infos, 3.0))               # lu en mm : Ø6 × 20
        self.assertEqual(d.current_values(), {'d': 6.0, 'length': 20.0})
        self.assertIsNotNone(d.save(self.path('goupille_cm.step')))
        self.assertIsNone(d.save_with_part(self.path('cm_et_goupille.step')))   # unités différentes : dit
        self.assertIn('millimètres', d.hole.text())
        self.assertFalse(os.path.exists(self.path('cm_et_goupille.step')))
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
        acts = [b.defaultAction() for g in page.groups() if g.title.text() == 'Modifier un STEP'
                for b in g.buttons()]
        self.assertIn(self.w.A['step_screw'], acts)
        self.assertIn(self.w.A['step_part_hole'], acts)
        self.assertTrue(page.fit(full_hd()))                    # tient en 1920 (sans défiler, 1094)

    def test_faces_of_drawing(self):
        w = self.w
        self.assertIsNone(w.step_part_hole(exec_dialog=False))            # pas de pièce STEP : dit
        self.assertIn('trou', w.statusBar().currentMessage())
        self.assertTrue(w.open_path(self.p))
        w._ensure_panel3d()
        p3 = w.panel3d
        self.assertTrue(p3.refresh())
        self.assertIsNone(w.step_part_hole(exec_dialog=False))            # rien de choisi
        self.assertIsNone(w.step_screw(exec_dialog=False))
        hole = hole_face(self.infos, 8.0)
        plane = next(f for f, k in enumerate(self.infos) if k.get('genre') == 'plan')
        p3.view.set_selection([plane, hole])
        d = w.step_part_hole(exec_dialog=False)
        self.assertEqual(os.path.normcase(d.path), os.path.normcase(self.p))
        self.assertEqual(d.face, hole)
        d.family.setCurrentIndex(d.family.findData('douille'))
        out = d.save(self.path('douille.step'))
        self.assertEqual([b.name for b in X.bodies(out)], ['Douille de guidage 10x25'])
        d.deleteLater()
        s = w.step_screw(exec_dialog=False)                               # même sélection, vis
        self.assertEqual(s.face, hole)
        s.deleteLater()


if __name__ == '__main__':
    unittest.main()
