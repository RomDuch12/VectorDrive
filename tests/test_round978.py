"""Round 978 : le plein écran tient — la fenêtre a sa propre taille minimale (des panneaux empilés ne l'agrandissent
plus de force au-delà de l'écran), un panneau de machine se range en onglet à côté des Calques et prend la colonne
quand sa machine est choisie, et un plein écran déplacé reprend sa place."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r978.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import QRect, Qt  # noqa: E402
from PySide6.QtWidgets import QApplication, QDockWidget, QLabel, QVBoxLayout, QWidget  # noqa: E402

from vectordrive import plugins  # noqa: E402
from vectordrive.cam import post  # noqa: E402

app = QApplication.instance() or QApplication([])


def tall(win):
    """Un panneau de machine bien plus haut qu'un écran."""
    w = QWidget()
    lay = QVBoxLayout(w)
    lab = QLabel('machine')
    lab.setMinimumHeight(1500)
    lay.addWidget(lab)
    return w


def writer(toolpaths, setup, *, title='', machine=None, stem='p', box_mm=None, machine_dir=''):
    return post.PostResult('', [], '.txt')


def close(w):
    w.settings.setValue('fenetre/plein_ecran', False)
    w.settings.remove('fenetre/plein_ecran_barre')
    w.modified = False
    for t in getattr(w, 'docs', []):
        t.modified = False
    st = w.settings
    w.close()
    app.processEvents()                                  # après la fermeture (qui les écrit) : la fenêtre d'un essai
    st.remove('panneaux_colonnes/place')                 # suivant (1003) ne retrouve ni ses panneaux rangés à droite,
    st.remove('fenetre/geometrie')                       # ni sa taille de 900 × 600, ni le panneau FAO ouvert (il ne
    st.setValue('vue/panneau_fao', False)                # restait que 190 px au dessin)


class Holds(unittest.TestCase):

    def setUp(self):
        r = plugins.REGISTRY
        self.saved = (dict(r.posts), list(r.post_providers), list(r.actions), list(r.panels), list(r.post_hooks),
                      dict(r.post_exports))
        api = plugins.Api(r, plugins.PluginInfo('essai', 'essai'))
        api.add_post('essai_haut', 'Machine d’essai', writer)
        api.add_panel('essai_haut', 'Panneau très haut', tall, posts=('essai_haut',))
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.addCleanup(close, self.w)

    def tearDown(self):
        r = plugins.REGISTRY
        r.posts, r.post_providers, r.actions, r.panels, r.post_hooks, r.post_exports = self.saved

    def test_stacked_panels_no_longer_force_the_window_taller(self):
        w = self.w
        self.assertEqual((w.minimumSize().width(), w.minimumSize().height()), (640, 480))
        w.resize(900, 600)
        w.show()
        for d in w.findChildren(QDockWidget):                        # tous les panneaux, empilés à droite
            d.setFloating(False)
            w.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, d)
            d.setVisible(True)
        app.processEvents()
        self.assertEqual((w.width(), w.height()), (900, 600))       # avant : agrandie de force (plus de 1 500 px)
        self.assertEqual((w.minimumSize().width(), w.minimumSize().height()), w.MIN_WINDOW)

    def test_a_machine_panel_is_a_tab_and_takes_the_column(self):
        w = self.w
        w.show()
        dock = w.plugin_docks['essai_haut']
        layers, dims = w.findChild(QDockWidget, 'layers'), w.findChild(QDockWidget, 'dims')
        self.assertTrue(dock.isHidden())                             # sa machine n'est pas choisie
        w.cam_panel.set_post('essai_haut')
        app.processEvents()
        self.assertFalse(dock.isHidden())
        tabs = w.tabifiedDockWidgets(dock)
        self.assertIn(layers, tabs)                                  # avant : empilé sous les autres panneaux
        self.assertIn(dims, tabs)                                    # Dimensions en onglet : la colonne est à lui
        self.assertTrue(dock.isVisible())                            # et il est devant

    def test_a_moved_full_screen_goes_back(self):
        w = self.w
        w.show()
        w.cycle_full_screen()
        w.cycle_full_screen()
        self.assertEqual(w.full_screen_mode(), 'taskbar')
        app.processEvents()
        want = w._full_screen_rect()
        self.assertEqual(w.geometry(), want)
        w.setGeometry(QRect(want.x() + 30, want.y() + 20, want.width() - 60, want.height() + 80))   # quelque chose la déplace
        for _ in range(5):
            app.processEvents()
        self.assertEqual(w.geometry(), want)                         # avant : restait déplacée
        self.assertTrue(w.full_screen_holds())
        w.set_full_screen(False)
        app.processEvents()
        w.setGeometry(QRect(40, 0, 700, 600))                        # en fenêtre : on la déplace comme on veut
        for _ in range(3):
            app.processEvents()
        self.assertEqual((w.geometry().x(), w.geometry().width()), (40, 700))


if __name__ == '__main__':
    unittest.main()
