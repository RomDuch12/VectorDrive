"""Round 690 : « Répéter des corps » (onglet Design STEP, groupe « Modifier
un STEP ») — les corps d'un STEP copiés en ligne au pas donné ou en rond
autour de la verticale (sur le tour, ou du premier au dernier sur un angle),
le corps choisi seul ; solides fermés et bien placés ; refus dits ; fenêtre
(modes, écriture, pas sur la source) ; ruban."""
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
from vectordrive.io import model3d
from vectordrive.io import step_extract as X
from tests.test_round673 import geometry_errors, topology
from tests.test_round676 import _text

app = QApplication.instance() or QApplication([])


def source(d):
    """Une bague Ø posée en (40, 0) et une plaque à côté, en (200, 0)."""
    p = os.path.join(d, 'source.step')
    bush = G.build('bague', G.values('bague'))[0]
    bush.matrix = B.placement((40, 0, 0), (0, 0, 1), (1, 0, 0))
    plate = G.build('plaque', G.values('plaque'))[0]
    plate.matrix = B.placement((200, 0, 0), (0, 0, 1), (1, 0, 0))
    B.write(p, [bush, plate], 'source')
    return p


def centres(path):
    """Par corps lu, dans l'ordre du fichier : (x, y) de l'axe de son premier cylindre (exact, du STEP) et le Z
    de son dessous."""
    m = model3d.from_step(path)
    T = np.asarray(m.triangles, dtype=float).reshape(-1, 3, 3)
    fo, bo = np.asarray(m.face_ids()), np.asarray(m.body_ids())
    out = []
    for b in sorted(set(bo.tolist())):
        cyl = [f for f in sorted(set(fo[bo == b].tolist())) if (m.face_kinds[f] or {}).get('genre') == 'cylindre']
        c = np.asarray(m.face_kinds[cyl[0]]['centre'], dtype=float)
        out.append(np.array([c[0], c[1], T[bo == b][:, :, 2].min()]))
    return out


class TestCore(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.d = self._tmp.name
        self.src = source(self.d)
        self.c0 = centres(self.src)[0]

    def tearDown(self):
        self._tmp.cleanup()

    def check(self, path, n):
        text = _text(path)
        self.assertEqual(geometry_errors(text), [])
        top = topology(text)
        self.assertEqual(len(top), n)
        self.assertFalse(any(t[-1] for t in top))                        # chaque arête bordée deux fois

    def test_line(self):
        out = X.pattern(self.src, [0], os.path.join(self.d, 'ligne.step'), X.pattern_moves(3, step=(0, 30, 5)))
        self.check(out, 3)
        cs = centres(out)
        for k, c in enumerate(cs):
            self.assertTrue(np.allclose(c, self.c0 + np.array([0, 30, 5]) * k, atol=1e-6), (k, c))
        self.assertEqual(len(X.bodies(out)), 3)
        both = X.pattern(self.src, None, os.path.join(self.d, 'tous.step'), X.pattern_moves(2, step=(0, 100, 0)))
        self.check(both, 4)                                               # les deux corps, deux fois

    def test_round(self):
        out = X.pattern(self.src, [0], os.path.join(self.d, 'rond.step'), X.pattern_moves(6, angle=360))
        self.check(out, 6)
        angles = sorted(round(math.degrees(math.atan2(c[1], c[0])) % 360, 6) for c in centres(out))
        self.assertEqual(angles, [0, 60, 120, 180, 240, 300])
        self.assertTrue(all(abs(math.hypot(c[0], c[1]) - 40) < 1e-6 for c in centres(out)))
        out = X.pattern(self.src, [0], os.path.join(self.d, 'quart.step'), X.pattern_moves(4, angle=90, centre=(40, -40)))
        r = [math.hypot(c[0] - 40, c[1] + 40) for c in centres(out)]
        self.assertTrue(np.allclose(r, 40, atol=1e-6))
        a = [round(math.degrees(math.atan2(c[1] + 40, c[0] - 40)), 6) for c in centres(out)]
        self.assertEqual(a, [90, 120, 150, 180])                          # du premier au dernier, sur 90°

    def test_refusals(self):
        for kw, word in (({'count': 0, 'step': (1, 0, 0)}, 'au moins'), ({'count': 3, 'step': (0, 0, 0)}, 'pas nul'),
                         ({'count': 3, 'angle': 0.0}, 'angle nul')):
            with self.assertRaises(X.ExtractError) as cm:
                X.pattern_moves(**kw)
            self.assertIn(word, str(cm.exception))
        with self.assertRaises(X.ExtractError):
            X.pattern(self.src, [5], os.path.join(self.d, 'x.step'), X.pattern_moves(2, step=(1, 0, 0)))


class TestWindow(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.src = source(self._tmp.name)

    def tearDown(self):
        for i in range(len(self.w.docs)):
            self.w.docs[i].modified = False
        self.w.modified = False
        self.w.close()
        self._tmp.cleanup()

    def test_dialog_and_ribbon(self):
        from tests.test_round672 import full_hd, tab_index
        w = self.w
        page = w.ribbon.page(tab_index(w.ribbon, 'Design STEP'))
        acts = [b.defaultAction() for g in page.groups() if g.title.text() == 'Modifier un STEP' for b in g.buttons()]
        self.assertIn(w.A['step_pattern'], acts)
        self.assertEqual(page.fit(full_hd()), [])
        d = w.step_pattern(self.src, exec_dialog=False, picks=[0])
        self.assertTrue(d.dx.isEnabled() and not d.angle.isEnabled())
        d.mode.setCurrentIndex(1)
        self.assertTrue(d.angle.isEnabled() and not d.dx.isEnabled())
        d.out.setText(self.src)                                           # pas sur la source
        self.assertIsNone(d.write())
        self.assertIn('source', d.info.text())
        d.count.setValue(3)
        d.out.setText(os.path.join(self._tmp.name, 'trois.step'))
        self.assertTrue(d.write() and os.path.isfile(d.written))
        self.assertEqual(len(X.bodies(d.written)), 3)
        d.deleteLater()


if __name__ == '__main__':
    unittest.main()
