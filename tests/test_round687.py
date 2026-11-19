"""Round 687 : sélection 3D « Faces parallèles » (onglet Design STEP) — un
plan : tous les plans de même normale à toute cote (les fonds tournés vers
l'outil, pas ceux tournés vers le bas) ; un cylindre : ceux d'axe parallèle,
creux ou non comme lui (les trous percés dans ce sens, pas un alésage
couché) ; sur plusieurs corps ; bouton du ruban."""
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


def parts(d):
    """Cale à 3 marches, plaque à 4 trous lamés M6 à côté, bague couchée le long de X."""
    p = os.path.join(d, 'pieces.step')
    steps = G.build('cale_etagee', G.values('cale_etagee', steps=3, step_height=8, step_depth=12, width=30))
    plate = G.build('plaque', G.values('plaque', hole='lamage', size='M6', thickness=12.0))
    plate[0].matrix = B.placement((0, 50, 0), (0, 0, 1), (1, 0, 0))
    bush = G.build('bague', G.values('bague'))[0]
    bush.matrix = B.placement((-30, 0, 10), (1, 0, 0), (0, 1, 0))
    B.write(p, steps + plate + [bush], 'pieces')
    return p


def faces(m, kind, test=lambda p: True):
    return [f for f in range(m.face_count()) if S.props(m, f)['kind'] == kind and test(S.props(m, f))]


class TestCore(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.m = model3d.from_step(parts(self._tmp.name))

    def tearDown(self):
        self._tmp.cleanup()

    def test_planes(self):
        m = self.m
        up = faces(m, 'plan', lambda p: p['normal'][2] > 0.999)
        self.assertEqual(sorted({round(S.props(m, f)['offset'], 6) for f in up}), [5.5, 8, 12, 16, 24])
        self.assertEqual(S.parallel(m, up[:1]), up)                      # toutes cotes, tous corps
        down = faces(m, 'plan', lambda p: p['normal'][2] < -0.999)
        self.assertEqual(S.parallel(m, down[:1]), down)                  # même sens seulement
        self.assertTrue(set(up).isdisjoint(down))
        self.assertEqual(S.parallel(m, up[:1] + down[:1]), sorted(up + down))

    def test_cylinders(self):
        m = self.m
        vertical = faces(m, 'cylindre', lambda p: p['hollow'] and abs(p['axis'][2]) > 0.999)
        self.assertEqual(len(vertical), 16)                               # 4 trous et 4 lamages, en deux moitiés
        self.assertEqual(S.parallel(m, vertical[:1]), vertical)
        bore = faces(m, 'cylindre', lambda p: p['hollow'] and abs(p['axis'][0]) > 0.999)
        self.assertEqual(len(bore), 2)
        self.assertEqual(S.parallel(m, bore[:1]), bore)                  # l'alésage couché, seul
        outside = faces(m, 'cylindre', lambda p: not p['hollow'])
        self.assertTrue(outside and set(S.parallel(m, outside[:1])).isdisjoint(bore))   # pas les creux


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
        self.assertIn(w.A['step_parallel'], acts)
        self.assertTrue(page.fit(full_hd()))                    # tient en 1920 (sans défiler, 1094)
        self.assertTrue(w.open_path(parts(self._tmp.name)))
        w._ensure_panel3d()
        p3 = w.panel3d
        self.assertTrue(p3.refresh())
        m = p3.view.model
        up = faces(m, 'plan', lambda p: p['normal'][2] > 0.999)
        p3.view.set_selection(up[:1])
        self.assertEqual(w.step_parallel(), up)
        self.assertEqual(sorted(p3.view.sel_faces), up)
        self.assertIn(f'{len(up)} face(s) parallèle(s)', w.statusBar().currentMessage())


if __name__ == '__main__':
    unittest.main()
