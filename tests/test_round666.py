"""Round 666 : simulation 3D, « Parcours en dessin » et mesure de volume
prennent les parcours que le programme écrirait, sans ceux d'opérations
désactivées. « Parcours en dessin » et le volume les recalculent si le
dessin a changé depuis leur calcul ; la vue 3D ne recalcule pas d'elle-même
(elle se rafraîchit aussi au milieu d'un calcul lancé ailleurs) : elle dit
« Calculer ». Un calcul lancé ailleurs, réussi ou annulé, n'en relance pas
un autre par la vue 3D. Session : empreinte du fichier tel qu'il a été lu."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))
os.environ.setdefault('VECTORDRIVE_CAM_TEMPLATES', os.path.join(tempfile.mkdtemp(), 'modeles_fao'))

from PySide6.QtWidgets import QApplication

from tests import test_round657 as R657
from tests import test_round664 as R664
from vectordrive.cam import model, strategies
from vectordrive.ui import session

app = QApplication.instance() or QApplication([])


@unittest.skipUnless(__import__('vectordrive.core.solids', fromlist=['x']).available(), 'manifold3d absent')
class TestWindow(unittest.TestCase):
    setUp, names = R657.TestWindow.setUp, R657.TestWindow.names
    tearDown, move_part = R664.TestWindow.tearDown, R664.TestWindow.move_part

    def fresh(self):
        return self.cp._memo('_placement_states') == self.cp._placement_state()

    def counted(self):
        calls = []
        real = strategies.compute_all

        def counting(*a, **k):
            calls.append(1)
            return real(*a, **k)
        return calls, mock.patch.object(strategies, 'compute_all', counting)

    def in_3d(self):
        """Vue 3D visible sur la simulation (dessin sans modèle 3D)."""
        p = self.p
        p.source.blockSignals(True)
        p.source.setCurrentIndex(p.source.findData('simulation'))
        p.source.blockSignals(False)
        return (mock.patch.object(p, '_model_source', lambda: None),
                mock.patch.object(self.w, 'view_mode', lambda: '3d'))

    def show_simulation(self):
        a, b = self.in_3d()
        with a, b:
            return self.p.refresh()

    def test_view_does_not_recompute(self):
        cp, p = self.cp, self.p
        before = list(cp.toolpaths)
        self.assertEqual(self.names(p._computed_paths()), ['Un', 'Deux'])
        self.move_part()
        calls, patch = self.counted()
        with patch:
            self.assertEqual(p._computed_paths(), [])                             # d'avant : rien, pas de calcul
        self.assertEqual(calls, [])
        self.assertEqual(cp.toolpaths, before)
        self.assertFalse(self.show_simulation())
        self.assertIn('Calculer', p.info.text())
        cp.compute()
        self.assertEqual(self.names(p._computed_paths()), ['Un', 'Deux'])

    def test_compute_elsewhere_once(self):
        p = self.p
        self.move_part()
        a, b = self.in_3d()
        calls, patch = self.counted()
        with a, b, patch:
            self.p.stale = True
            self.cp.compute()                                                     # « Calculer » : la vue suit
        self.assertEqual(calls, [1])
        self.assertFalse(p.stale)
        self.assertEqual(self.names(p.relief.toolpaths), ['Un', 'Deux'])

    def test_cancel_elsewhere_once(self):
        from vectordrive.ui import progress
        p = self.p
        real = progress.run
        calls = []

        def run(win, title, *a, **k):
            if title == 'Calcul des parcours':
                calls.append(1)
                raise progress.Cancelled()
            return real(win, title, *a, **k)
        self.move_part()
        a, b = self.in_3d()
        with a, b, mock.patch('vectordrive.ui.progress.run', run):
            self.assertEqual(self.w.cam_to_drawing(), [])                         # annulé : pas un 2e calcul
        self.assertEqual(calls, [1])
        self.assertIn('Calculer', p.info.text())

    def test_selection_redone_then_compute(self):
        cp, p = self.cp, self.p
        cp.set_selection_mode(True)
        self.w.canvas.selection = [self.m1]
        cp.compute()
        was, self.m1.id = self.m1.id, 'remplace'                                  # objets du calcul remplacés
        self.move_part()
        self.assertEqual(cp.current_paths(dates=False), [])
        self.assertIn('remplacés', cp.info.text())
        self.m1.id = was                                                          # remis, resélectionné
        a, b = self.in_3d()
        with a, b:
            cp.compute()                                                          # « Calculer »
        self.assertNotIn('remplacés', cp.info.text())
        self.assertEqual(self.names(p.relief.toolpaths), ['Un'])

    def test_view_not_redone_while_computing(self):
        cp, p = self.cp, self.p
        cp.display([])
        seen = []
        real = p.refresh

        def spy():
            r = real()
            seen.append((p._taking, r))
            return r
        with mock.patch.object(p, 'refresh', spy), mock.patch.object(self.w, 'view_mode', lambda: '3d'):
            tps = p._computed_paths()                                             # rien de calculé : calcul
        self.assertEqual(self.names(tps), ['Un', 'Deux'])
        self.assertTrue(seen)
        self.assertEqual(set(seen), {(True, False)})                              # vue faite par l'appel en cours
        self.assertFalse(p._taking)
        cp.display([])
        cp._computing = True                                                      # calcul en cours ailleurs
        try:
            self.assertEqual(p._computed_paths(), [])
        finally:
            cp._computing = False

    def test_program_paths_as_they_are(self):
        cp, p = self.cp, self.p
        prog = model.Toolpath('', '', [model.Move('feed', 0, 0, 0), model.Move('feed', 5, 0, 0)], name='prog.nc')
        prog.shown = True
        for tp in cp.toolpaths:
            tp.on = False                                                         # arrêtés (round 1163)
        cp.display([prog] + list(cp.toolpaths))
        self.move_part()
        calls, patch = self.counted()
        with patch:
            self.assertEqual(p._computed_paths(), [prog])                         # pas de calcul du dessin
        self.assertEqual(calls, [])

    def test_disabled_not_simulated(self):
        cp = self.cp
        s = cp.setup()
        s.operations[1].enabled = False
        cp.save(s)
        self.assertEqual(self.names(self.p._computed_paths()), ['Un'])
        for o in s.operations:
            o.enabled = False
        cp.save(s)
        self.assertFalse(self.show_simulation())
        self.assertIn('désactivées', self.p.info.text())
        self.assertFalse(self.p.stale)

    def test_nothing_checked_shows_all(self):
        cp = self.cp
        for tp in cp.toolpaths:
            tp.shown = False
        self.assertEqual(self.p._computed_paths(), list(cp.toolpaths))           # comme avant : tous

    def test_session_resumed_asks(self):
        self.cp.from_session()
        self.assertFalse(self.show_simulation())
        self.assertIn('Calculer', self.p.info.text())

    def test_cam_to_drawing_follows(self):
        self.move_part()
        shapes = self.w.cam_to_drawing()
        self.assertEqual(len(shapes), 2)
        self.assertTrue(self.fresh())

    def test_volume_follows(self):
        self.w.canvas.selection = []
        self.move_part()
        out = self.w.measure_volume(show=False)
        self.assertIsNotNone(out)
        self.assertTrue(self.fresh())


@unittest.skipUnless(__import__('vectordrive.core.solids', fromlist=['x']).available(), 'manifold3d absent')
class TestFileChanged(unittest.TestCase):
    def test_changed_before_session_saved(self):
        from vectordrive.io import native
        from vectordrive.ui.main_window import MainWindow
        R = R657.TestWindow()
        R.setUp()
        with tempfile.TemporaryDirectory() as tmp:
            path, folder = os.path.join(tmp, 'plaque.vdz'), os.path.join(tmp, 'session')
            native.write_atomic(native.snapshot(R.doc), path)
            R.tearDown()
            w = MainWindow()
            try:
                w.open_path(path)
                w.cam_panel.compute()
                t = os.path.getmtime(path) + 60
                os.utime(path, (t, t))                                            # autre poste, avant la sauvegarde
                w.modified = False
                session.save(w, folder)
            finally:
                w.close()
            w2 = MainWindow()
            try:
                session.restore(w2, folder)
                last = w2.cam_panel._memo('_only')
            finally:
                w2.modified = False
                w2.close()
            self.assertEqual(tuple(last or ()), ('session', None))


if __name__ == '__main__':
    unittest.main()
