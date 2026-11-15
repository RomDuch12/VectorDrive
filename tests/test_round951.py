"""Round 951 : rubans FAO — les boutons du groupe « Machine » portent toujours le nom de leur machine (texte seul),
même quand le ruban, faute de place, réduit ses petits boutons à leur icône."""
import contextlib
import os
import tempfile
import types
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r951.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication, QToolButton  # noqa: E402

app = QApplication.instance() or QApplication([])

from tests import _posts  # noqa: E402
from vectordrive.plugins import REGISTRY  # noqa: E402


@contextlib.contextmanager
def declared():
    """Deux fraiseuses et un laser d'essai, le temps du bloc."""
    old_machines, old_posts = list(REGISTRY.machines), dict(REGISTRY.posts)
    REGISTRY.machines = [types.SimpleNamespace(key=k, label=label, kind=kind, posts=(f'poste_{k}',), doubles=(),
                                               tip='', plugin='essai')
                         for k, label, kind in (('a', 'Fraiseuse A', 'fraiseuse'), ('b', 'Fraiseuse B', 'fraiseuse'),
                                                ('c', 'Laser C', 'laser'))]
    for k in 'abc':
        REGISTRY.posts[f'poste_{k}'] = (f'Poste {k}', _posts.write)
    try:
        yield
    finally:
        REGISTRY.posts.clear()
        REGISTRY.posts.update(old_posts)
        REGISTRY.machines = old_machines


class Names(unittest.TestCase):

    def test_machine_buttons_always_show_their_name(self):
        from vectordrive.ui.main_window import MainWindow
        from vectordrive.ui.ribbon import RibbonGroup
        with declared():
            w = MainWindow()
            try:
                act = w.A['machine_a']
                buttons = [b for b in w.ribbon.findChildren(QToolButton) if b.defaultAction() is act]
                self.assertEqual(len(buttons), 2)                           # rubans FAO 2D et FAO 3D
                groups = [g for g in w.ribbon.findChildren(RibbonGroup) if buttons[0] in g.findChildren(QToolButton)]
                groups[0].set_iconic(True)                                  # la place manque : petits boutons en icônes
                for b in buttons:
                    self.assertEqual(b.toolButtonStyle(), Qt.ToolButtonStyle.ToolButtonTextOnly)   # avant : l'icône seule
                    self.assertEqual(b.text(), 'Fraiseuse A')
                buttons[0].click()                                          # le bouton choisit toujours la machine
                self.assertEqual(w.cam_panel.setup().post, 'poste_a')
                self.assertTrue(all(b.isChecked() for b in buttons))
                laser = [b for b in w.ribbon.findChildren(QToolButton) if b.defaultAction() is w.A['machine_c']]
                self.assertEqual([b.text() for b in laser], ['Laser C'])
            finally:
                w.modified = False
                w.close()


if __name__ == '__main__':
    unittest.main()
