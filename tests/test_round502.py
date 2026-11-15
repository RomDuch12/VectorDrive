"""Round 502 : fils de calcul (core.workers) pour les retraits de régions (poches, gravure 2,5D), retraits
bornés par le cercle inscrit de chaque partie ; onglet F10 « Performances » (fils, priorité basse, carte
graphique, anticrénelage de la vue 3D)."""
import os
import sys
import tempfile
import threading
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication
from shapely.geometry import MultiPolygon, Point, box

from vectordrive.cam import strategies as S
from vectordrive.core import progress as P
from vectordrive.core import workers

app = QApplication.instance() or QApplication([])


class TestWorkers(unittest.TestCase):
    def tearDown(self):
        workers.set_count(0)

    def test_pmap_order_threads_and_cancel(self):
        workers.set_count(4)
        names = []
        self.assertEqual(workers.pmap(lambda x: (names.append(threading.current_thread().name), x * x)[1],
                                      range(20)), [x * x for x in range(20)])
        self.assertTrue(any(n.startswith('vd-geometrie') for n in names))
        task = P.Task('essai')
        token = P.attach(task)
        try:
            task.cancel()
            with self.assertRaises(P.Cancelled):                     # l'annulation du calcul suit dans les fils
                workers.pmap(lambda x: P.check(), range(8))
        finally:
            P.detach(token)
        workers.set_count(1)
        self.assertEqual(workers.pmap(lambda x: threading.current_thread().name, [1, 2]),
                         [threading.current_thread().name] * 2)        # un fil : à la suite
        self.assertGreaterEqual(workers.auto_count(), 1)

    def test_erosions_same_as_sequential(self):
        workers.set_count(4)
        big = box(0, 0, 40, 30).difference(MultiPolygon([box(5 + 6 * i, 5, 8 + 6 * i, 9) for i in range(5)]))
        small = [Point(60 + 3 * i, 5).buffer(1.0, 16) for i in range(40)]
        reg = MultiPolygon([big] + small)
        qs = 8
        dists = [0.0] + [0.4 * k for k in range(1, 200)]
        got = S.erosions(reg, dists, qs)
        seq = []
        for d in dists:
            g = reg if d <= 0 else S.erode(reg, d, qs)
            if g.is_empty:
                break
            seq.append(g)
        self.assertEqual(len(got), len(seq))
        for a, b in zip(got, seq):
            self.assertLess(a.symmetric_difference(b).area, 1e-6)
        self.assertLess(S.inscribed_radius(reg), 15.1)
        self.assertGreater(S.inscribed_radius(reg), 9.9)
        self.assertEqual(len(S.concentric(reg, 0.5, 0.01)), len(S.erosions(reg, [0.5 * k for k in range(1000)], 8)))


class TestPerformancesPage(unittest.TestCase):
    def test_page_and_apply(self):
        from vectordrive.ui import options as O, progress
        from vectordrive.ui.main_window import MainWindow
        self.assertIn('Performances', O.PAGES)
        keys = [o.key for o in dict(O.SPEC)['Performances']]
        self.assertEqual(keys[:4], ['perf/fils', 'perf/processus', 'perf/priorite_basse', 'affichage/gpu'])
        w = MainWindow()
        try:
            w.settings.setValue('perf/fils', 3)
            w.settings.setValue('perf/priorite_basse', True)
            w.apply_options()
            self.assertEqual(workers.count(), 3)
            self.assertTrue(progress.LOW_PRIORITY)
            self.assertIn('Performances', [w.options_dialog(exec_dialog=False).tabs.tabText(i)
                                           for i in range(len(O.SPEC))])
        finally:
            w.settings.setValue('perf/fils', 0)
            w.settings.setValue('perf/priorite_basse', False)
            w.apply_options()
            w.modified = False
            w.close()
        self.assertFalse(progress.LOW_PRIORITY)

    @unittest.skipUnless(sys.platform == 'win32', 'priorité de processus Windows')
    def test_low_priority_restored(self):
        from vectordrive.ui import progress
        k = progress._kernel32()
        progress._set_low_priority(True)
        self.assertEqual(k.GetPriorityClass(k.GetCurrentProcess()), 0x4000)
        progress._set_low_priority(True)                              # imbriqué
        progress._set_low_priority(False)
        self.assertEqual(k.GetPriorityClass(k.GetCurrentProcess()), 0x4000)
        progress._set_low_priority(False)
        self.assertEqual(k.GetPriorityClass(k.GetCurrentProcess()), 0x20)

    def test_samples(self):
        from vectordrive import portable
        from vectordrive.ui import view3d
        st = portable.settings()
        st.setValue('vue3d/anticrenelage', '8')
        self.assertEqual(view3d.samples(), 8)
        st.setValue('vue3d/anticrenelage', '3')
        self.assertEqual(view3d.samples(), 4)
        st.setValue('affichage/gpu', 'logiciel')                       # rendu logiciel : aucun (round 530)
        self.assertEqual(view3d.samples(), 0)
        st.remove('affichage/gpu')
        st.remove('vue3d/anticrenelage')


if __name__ == '__main__':
    unittest.main()
