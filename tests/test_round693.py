"""Round 693 : sélection 3D « Inverser dans le corps » (onglet Design STEP) —
les faces des corps des faces choisies qui ne sont pas choisies : le reste
d'une pièce, les autres corps laissés ; rien de choisi, rien ; bouton."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import facesel as S
from vectordrive.io import model3d
from tests.test_round688 import body, kind, parts

app = QApplication.instance() or QApplication([])


class TestCore(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.m = model3d.from_step(parts(self._tmp.name))

    def tearDown(self):
        self._tmp.cleanup()

    def test_invert(self):
        m = self.m
        plate = [f for f in range(m.face_count()) if body(m, f) == 0]
        hole = S.coaxial(m, [f for f in plate if kind(m, f) == 'cylindre' and m.face_kinds[f].get('creux')][:1])
        rest = S.invert(m, hole)
        self.assertEqual(sorted(rest + hole), plate)                    # la plaque sauf le trou
        self.assertTrue(set(rest).isdisjoint(hole))
        self.assertEqual(S.invert(m, rest), hole)                        # deux fois : le trou
        self.assertEqual(S.invert(m, []), [])
        self.assertEqual(S.invert(m, plate), [])


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
        self.assertIn(w.A['step_invert'], acts)
        self.assertEqual(page.fit(full_hd()), [])
        self.assertTrue(w.open_path(parts(self._tmp.name)))
        w._ensure_panel3d()
        p3 = w.panel3d
        self.assertTrue(p3.refresh())
        m = p3.view.model
        p3.view.set_selection([0])
        got = w.step_invert()
        self.assertEqual(got, S.invert(m, [0]))
        self.assertEqual(sorted(p3.view.sel_faces), got)
        self.assertIn(f'{len(got)} face(s) choisie(s) : le reste du corps', w.statusBar().currentMessage())


if __name__ == '__main__':
    unittest.main()
