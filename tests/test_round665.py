"""Round 665 : relecture des derniers ajouts de 664. La session garde ce
que le panneau sait du calcul des parcours (mode, objets, parcours
retirés, empreintes) et leur sens : rien n'est refait à la reprise si rien
n'a bougé, et un recalcul rejoue le bon calcul. Session d'avant (sans ces
données) : « Calculer » demandé, quel que soit le mode. Sans calcul connu,
le mode du moment compte. Calcul complet annulé pendant le recalcul : rien
d'écrit. Opérations désactivées : ne bloquent pas l'écriture des parcours
TypeEdit."""
import json
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
from vectordrive.cam import model
from vectordrive.cam.edit import reversed_toolpath
from vectordrive.ui import session

app = QApplication.instance() or QApplication([])


@unittest.skipUnless(__import__('vectordrive.core.solids', fromlist=['x']).available(), 'manifold3d absent')
class TestWindow(unittest.TestCase):
    setUp, names = R657.TestWindow.setUp, R657.TestWindow.names
    tearDown, move_part, written = R664.TestWindow.tearDown, R664.TestWindow.move_part, R664.TestWindow.written

    def resume(self, memo):
        cp = self.cp                                                              # aller-retour de la session
        tps = session.paths_from_bytes(session.paths_bytes(cp.toolpaths))
        for name in cp.MEMOS:
            cp._remember(name, None)
        cp.display(tps)
        cp.restore_memo(json.loads(json.dumps(memo)) if memo is not None else None)
        return tps

    def test_session_keeps_what_was_known(self):
        cp = self.cp
        un = next(tp for tp in cp.toolpaths if tp.moves)
        back = reversed_toolpath(un)
        back.reversed = True
        cp.display([back])                                                        # « Un » retourné, « Deux » retiré
        self.resume(cp.memo_of(self.doc))
        calls = []
        with mock.patch.object(cp, '_recompute', lambda dates=True: calls.append(1) or []):
            tps = cp.current_paths(dates=False)
        self.assertEqual(calls, [])                                               # rien n'a bougé : rien refait
        self.assertTrue(tps[0].reversed)
        self.move_part()
        tps = cp.current_paths(dates=False)                                       # refait comme il était
        self.assertEqual(self.names([tp for tp in tps if tp.moves]), ['Un'])
        self.assertTrue(getattr(tps[0], 'reversed', False))

    def test_old_session_asks(self):
        cp = self.cp
        self.resume(None)                                                         # session d'avant
        self.assertEqual(cp.current_paths(dates=False), [])
        self.assertIn('session reprise', cp.info.text())
        cp.compute()                                                              # « Calculer » : tout repart
        self.assertEqual(self.written(), ['Un', 'Deux'])

    def test_unknown_calc_uses_current_mode(self):
        cp = self.cp
        for name in ('_only', '_computed'):
            cp._remember(name, None)
        cp._remember('_whole', set())
        cp.display([])
        cp.set_selection_mode(True)
        self.w.canvas.selection = [self.m1]
        self.move_part()
        self.assertEqual(self.written(), ['Un'])

    def test_full_compute_cancelled(self):
        from vectordrive.ui import progress
        cp = self.cp
        before = list(cp.toolpaths)
        real = progress.run

        def run(win, title, *a, **k):
            if title == 'Calcul des parcours':
                raise progress.Cancelled()
            return real(win, title, *a, **k)
        self.move_part()
        with mock.patch('vectordrive.ui.progress.run', run):
            self.assertEqual(cp.current_paths(dates=False), [])
        self.assertEqual(cp.toolpaths, before)
        self.assertEqual(self.written(), ['Un', 'Deux'])                          # retenté ensuite

    def test_disabled_ops_do_not_block(self):
        cp = self.cp
        s = cp.setup()
        for o in s.operations:
            o.enabled = False
        cp.save(s)
        te = model.Toolpath('', '', [model.Move('feed', 0, 0, 0)], name='TE')
        te.shown = True
        cp.display(list(cp.toolpaths) + [te])
        cp.from_session()
        cp.set_selection_mode(True)
        self.assertEqual(cp.current_paths(dates=False), [te])

    def test_session_entry_has_memo(self):
        snap = session.snapshot(self.w)
        entry = next(e for e, _d, paths in snap['docs'] if paths)
        memo = json.loads(json.dumps(entry['cam']))                              # écrit en JSON dans l'index
        self.assertEqual(memo['_only'], ['couleur', None])
        self.assertEqual(sorted(memo['_computed']), sorted(o.id for o in self.cp.setup().operations))

    def test_key_follows_direction_and_check(self):
        tps = list(self.cp.toolpaths)
        key = session.paths_key(tps)
        tps[0] = reversed_toolpath(tps[0])                                        # même uid (copie)
        tps[0].reversed = True
        self.assertNotEqual(session.paths_key(tps), key)                          # fichier réécrit
        k2 = session.paths_key(tps)
        tps[1].shown = False
        self.assertNotEqual(session.paths_key(tps), k2)

    def test_nothing_known_stays_unknown(self):
        cp = self.cp
        for name in cp.MEMOS:
            cp._remember(name, None)
        cp.restore_memo({})                                                       # onglet jamais calculé
        self.assertIsNone(cp._memo('_only'))

    def test_session_then_all_forms(self):
        cp = self.cp
        cp.from_session()
        for o in cp.setup().operations:
            cp.compute_op(o)                                                      # chacune refaite
        self.move_part()
        self.assertEqual(self.written(), ['Un', 'Deux'])


@unittest.skipUnless(__import__('vectordrive.core.solids', fromlist=['x']).available(), 'manifold3d absent')
class TestFileChanged(unittest.TestCase):
    def test_file_changed_since_session(self):
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
                w.modified = False
                session.save(w, folder)
            finally:
                w.close()
            for changed in (False, True):
                if changed:
                    t = os.path.getmtime(path) + 60
                    os.utime(path, (t, t))                                        # retouché depuis
                w2 = MainWindow()
                try:
                    session.restore(w2, folder)
                    last = w2.cam_panel._memo('_only')
                finally:
                    w2.modified = False
                    w2.close()
                self.assertEqual(tuple(last or ()), ('session', None) if changed else ('couleur', None))


if __name__ == '__main__':
    unittest.main()
