"""Round 483 : catalogue d'opérations machine — rubrique « Récents »."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from vectordrive.cam import catalog as C

app = QApplication.instance() or QApplication([])


def cats():
    return [('Essai', [C.Entry(name=f'Op {i}', path='Famille', text=f'Ligne {i}', catalog='Essai')
                       for i in range(3)], '')]


class TestRecents(unittest.TestCase):
    def test_recents(self):
        from vectordrive.ui import instruction_catalog as IC
        st = QSettings(os.path.join(tempfile.mkdtemp(), 'r.ini'), QSettings.Format.IniFormat)
        dlg = IC.CatalogDialog(None, catalogs=cats(), settings=st)
        self.assertEqual(dlg.tree.topLevelItemCount(), 1)                   # rien de récent
        it = next(it for it, e in dlg.entries() if e.name == 'Op 2')
        dlg.tree.setCurrentItem(it)
        dlg.accept()
        dlg2 = IC.CatalogDialog(None, catalogs=cats(), settings=st)
        top = dlg2.tree.topLevelItem(0)
        self.assertIn('Récents', top.text(0))
        self.assertEqual(top.child(0).text(0), 'Op 2')
        for k in range(20):
            IC.remember(st, [C.Entry(name=f'X{k}', catalog='Essai')])
        self.assertEqual(len(st.value(IC.RECENT_KEY)), IC.RECENT_MAX)
        self.assertEqual(st.value(IC.RECENT_KEY)[0], 'Essai||X19')


if __name__ == '__main__':
    unittest.main()
