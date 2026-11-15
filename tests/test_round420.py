"""Round 420 : dossier de fiches machine livré par un plugin, quand aucun n'est choisi."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.cam import post
from vectordrive.plugins import REGISTRY

app = QApplication.instance() or QApplication([])


class Fake:
    def __init__(self, d):
        self.d = d
        self.asked = []

    def posts(self, machines_dir):
        self.asked.append(machines_dir)
        return {'mah:' + os.path.join(machines_dir, 'M.MAH'): 'Machine test'}

    def default_machines(self):
        return self.d


class Broken:
    def posts(self, machines_dir):
        return {}

    def default_machines(self):
        raise RuntimeError('en défaut')


class TestDefaultMachines(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.fake = Fake(self.tmp)
        self.saved = list(REGISTRY.post_providers)
        REGISTRY.post_providers[:] = [Broken(), self.fake]

    def tearDown(self):
        REGISTRY.post_providers[:] = self.saved

    def test_core(self):
        self.assertEqual(post.default_machines_dir(), self.tmp)            # le plugin en défaut est passé
        self.fake.d = os.path.join(self.tmp, 'absent')
        self.assertEqual(post.default_machines_dir(), '')                  # dossier inexistant : rien

    def test_panel(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            w.settings.setValue('fao/machines', '')
            cp = w.cam_panel
            self.assertEqual(cp.machines_dir(), self.tmp)
            cp._fill_posts()
            self.assertIn('Machine test — ' + os.path.basename(self.tmp),
                          [cp.post.itemText(i) for i in range(cp.post.count())])
            other = tempfile.mkdtemp()
            w.settings.setValue('fao/machines', other)                     # le choix de l'utilisateur prime
            self.assertEqual(cp.machines_dir(), other)
        finally:
            w.settings.setValue('fao/machines', '')
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
