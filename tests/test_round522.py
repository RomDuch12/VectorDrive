"""Round 522 : vue 3D — tampons de la carte graphique rendus quand la vue est masquée, rechargés à
l'affichage suivant."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])


class FakeBuf:
    def __init__(self):
        self.destroyed = False

    def destroy(self):
        self.destroyed = True


class TestReleaseGpu(unittest.TestCase):
    def test_release_on_hide(self):
        from vectordrive.ui.view3d import View3D
        v = View3D()
        self.assertEqual(v.release_gpu(), 0)                     # rien à rendre
        bufs = [FakeBuf(), FakeBuf()]
        v._bufs = list(bufs)
        v._draws = [object()]
        v._dirty = False
        v.makeCurrent = lambda: None
        v.doneCurrent = lambda: None
        v.context = lambda: object()
        v.hideEvent(__import__('PySide6.QtGui', fromlist=['QHideEvent']).QHideEvent())
        self.assertTrue(all(b.destroyed for b in bufs))
        self.assertEqual((v._bufs, v._draws, v._dirty), ([], [], True))   # rechargés au prochain affichage


if __name__ == '__main__':
    unittest.main()
