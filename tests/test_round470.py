"""Round 470 : bibliothèque — vignettes de ce qui est à l'écran d'abord (file courte, reprise au
défilement)."""
import os
import pathlib
import tempfile
import time
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

DXF = "0\nSECTION\n2\nENTITIES\n0\nLINE\n8\n0\n10\n0\n20\n0\n11\n10\n21\n5\n0\nENDSEC\n0\nEOF\n"


class TestVisibleFirst(unittest.TestCase):
    def test_order(self):
        from vectordrive.ui import symbols as S
        root = pathlib.Path(tempfile.mkdtemp())
        for i in range(120):
            (root / f'f{i:03d}.dxf').write_text(DXF, encoding='ascii')
        st = QSettings(os.path.join(tempfile.mkdtemp(), 'r.ini'), QSettings.Format.IniFormat)
        p = S.SymbolPanel(st)
        p.roots = [root]
        p._fill_tree()
        p.resize(500, 600)
        p.show()
        p.size.setValue(160)
        p._timer.stop()
        p.show_folder(root)
        p._timer.stop()
        app.processEvents()
        bar = p.list.verticalScrollBar()
        bar.setValue(bar.maximum())                                               # tout en bas
        p._timer.stop()
        p._visible_first()
        vp = p.list.viewport().rect()
        first = p._pending[0]
        self.assertTrue(p.list.visualItemRect(first).intersects(vp))             # une ligne visible d'abord
        self.assertGreater(p.list.row(first), 60)
        p._load_some()
        self.assertLessEqual(len(p._jobs), S.SymbolPanel.QUEUE)                  # file courte
        t = time.time()
        while (p._pending or p._jobs) and time.time() - t < 30:
            p._load_some()
            time.sleep(0.005)
        self.assertFalse(p._pending)
        p.deleteLater()


if __name__ == '__main__':
    unittest.main()
