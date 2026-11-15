"""Round 952 : modes simple et expert (va-et-vient à côté du 2D / 3D, clic droit pour passer un bouton d'un mode à
l'autre) ; un bouton du ruban suit la visibilité de sa commande, un groupe ou un onglet sans rien à montrer est
caché."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r952.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import QPoint  # noqa: E402
from PySide6.QtWidgets import QApplication, QToolButton  # noqa: E402

app = QApplication.instance() or QApplication([])


class Modes(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from vectordrive.ui.main_window import MainWindow
        cls.w = MainWindow()

    @classmethod
    def tearDownClass(cls):
        cls.w.modified = False
        cls.w.close()

    def setUp(self):
        self.addCleanup(self.reset)

    def reset(self):
        """Les essais suivants retrouvent le mode expert et la répartition d'office (les réglages sont partagés)."""
        w = self.w
        for key in ('modes/simple_plus', 'modes/simple_moins'):
            w.settings.remove(key)
        if hasattr(w, 'set_ui_mode'):
            w.set_ui_mode('expert', announce=False)
        w.settings.remove('vue/mode')

    def buttons(self, key):
        act = self.w.A[key]
        return [b for b in self.w.ribbon.findChildren(QToolButton) if b.defaultAction() is act]

    def tabs(self):
        r = self.w.ribbon
        return [r.tabText(i) for i in range(r.count()) if r.isTabVisible(i)]

    def test_a_ribbon_button_follows_its_command(self):
        from vectordrive.ui.ribbon import RibbonGroup
        w = self.w
        b = self.buttons('cam_post')[0]
        w.A['cam_post'].setVisible(False)
        self.assertTrue(b.isHidden())                                       # avant : le bouton restait là
        w.A['cam_post'].setVisible(True)
        self.assertFalse(b.isHidden())
        # un groupe dont toutes les commandes sont cachées disparaît, et revient avec elles
        keys = ('compare', 'compare_next', 'compare_prev', 'compare_close')
        group = next(g for g in w.ribbon.findChildren(RibbonGroup) if self.buttons('compare')[0] in g.buttons())
        for k in keys:
            w.A[k].setVisible(False)
        self.assertTrue(group.isHidden())
        w.A['compare'].setVisible(True)
        self.assertFalse(group.isHidden())
        self.assertTrue(self.buttons('compare_next')[0].isHidden())
        for k in keys:
            w.A[k].setVisible(True)
        self.assertFalse(self.buttons('compare_next')[0].isHidden())

    def test_simple_mode_keeps_the_essentials(self):
        w = self.w
        self.assertTrue(hasattr(w, 'ui_mode'), 'pas de modes simple et expert')     # avant
        self.assertEqual(w.ui_mode(), 'expert')                             # d'office : rien ne disparaît
        self.assertIsNotNone(getattr(w.ribbon, 'mode_button', None))        # le va-et-vient, à côté du 2D / 3D
        corner = w.ribbon._corner_layout
        self.assertEqual(corner.indexOf(w.ribbon.mode_button), corner.indexOf(w.ribbon.view_button) + 1)
        before = self.tabs()
        self.assertIn('Design 3D', before)
        w.A['ui_mode'].trigger()
        self.assertEqual(w.ui_mode(), 'simple')
        self.assertTrue(all(b.isHidden() for b in self.buttons('tool_spiral')))      # réservé au mode expert
        self.assertFalse(any(b.isHidden() for b in self.buttons('tool_rect')))
        self.assertFalse(any(b.isHidden() for b in self.buttons('cam_post')))
        self.assertTrue(w.A['tool_spiral'].isVisible())                     # la commande reste : raccourcis, recherche
        self.assertNotIn('Design 3D', self.tabs())                          # un onglet sans bouton à montrer : caché
        self.assertIn('FAO 2D', self.tabs())
        w.A['ui_mode'].trigger()
        self.assertEqual(w.ui_mode(), 'expert')
        self.assertFalse(any(b.isHidden() for b in self.buttons('tool_spiral')))
        self.assertEqual(self.tabs(), before)

    def test_right_click_moves_a_button_between_modes(self):
        w = self.w

        def choose(key, text):
            menu = w._ribbon_button_menu(self.buttons(key)[0], QPoint(0, 0), exec_menu=False)
            act = next((a for a in menu.actions() if a.text() == text), None)
            self.assertIsNotNone(act, f'{key} : « {text} » absent du menu')
            act.trigger()
            menu.deleteLater()
        choose('tool_spiral', 'Montrer aussi en mode simple')
        choose('tool_rect', 'Réserver au mode expert')
        self.assertEqual(w.settings.value('modes/simple_plus'), ['tool_spiral'])
        self.assertEqual(w.settings.value('modes/simple_moins'), ['tool_rect'])
        w.set_ui_mode('simple')
        self.assertFalse(any(b.isHidden() for b in self.buttons('tool_spiral')))
        self.assertTrue(all(b.isHidden() for b in self.buttons('tool_rect')))
        choose('tool_spiral', 'Réserver au mode expert')                    # et retour : plus aucun écart gardé
        self.assertTrue(all(b.isHidden() for b in self.buttons('tool_spiral')))
        self.assertFalse(w.settings.value('modes/simple_plus'))


class Defaults(unittest.TestCase):

    def test_default_split(self):
        import importlib
        try:
            modes = importlib.import_module('vectordrive.ui.modes')
        except ImportError:
            self.fail('pas de modes simple et expert')                      # avant
        self.assertTrue(modes.default_simple('open') and modes.default_simple('machine_x'))
        self.assertFalse(modes.default_simple('solid_extrude'))
        self.assertTrue(modes.default_simple('devis', plugin_keys=('devis',)))       # les commandes des plugins


if __name__ == '__main__':
    unittest.main()
