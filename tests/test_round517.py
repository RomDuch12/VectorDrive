"""Round 517 : F10 — champ de recherche des réglages (libellés, info-bulles, clés ; sans accents ni casse)."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])


class TestOptionsSearch(unittest.TestCase):
    def test_filter(self):
        from vectordrive.ui.main_window import MainWindow
        from vectordrive.ui.options import SPEC
        w = MainWindow()
        try:
            dlg = w.options_dialog(exec_dialog=False)
            titles = [t for t, _o in SPEC]
            n = dlg.filter_options('FILS DE CALCUL')
            self.assertEqual(n, 1)
            self.assertEqual(dlg.tabs.currentIndex(), titles.index('Performances'))
            self.assertFalse(dlg.tabs.isTabEnabled(titles.index('BAT')))
            fils = dlg.widgets['perf/fils']
            form = dlg._rows[[r[2] for r in dlg._rows].index(fils)][1]
            self.assertTrue(form.isRowVisible(fils))
            self.assertGreater(dlg.filter_options('memoire'), 1)        # « Mémoire … » sans accent
            self.assertGreater(dlg.filter_options('vnd/compagnon'), 0)  # par la clé
            self.assertEqual(dlg.filter_options('zzzz introuvable'), 0)
            total = dlg.filter_options('')
            self.assertEqual(total, len(dlg._rows))
            self.assertTrue(all(dlg.tabs.isTabEnabled(i) for i in range(dlg.tabs.count())))
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
