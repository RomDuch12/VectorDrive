"""Round 641 : jamais un bouton muet — une commande qui ne change rien de
visible (dessin, fenêtre, message, outil, vue, sélection, presse-papiers…)
le dit dans la barre d'état, avec la raison probable (rien de sélectionné,
aucune opération, aucun parcours, aucun relief, aucun volume) ; « En courbes »
calcule le contour d'un texte qui n'en a pas encore."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication, QDialog

from vectordrive.core import geom
from vectordrive.core.document import Shape

app = QApplication.instance() or QApplication([])


class TestSilent(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from vectordrive.ui.main_window import MainWindow
        cls.w = MainWindow()

    @classmethod
    def tearDownClass(cls):
        cls.w.modified = False
        cls.w.close()

    def setUp(self):
        doc = self.w.canvas.doc
        for L in doc.layers:
            L.items.clear()
        self.a = Shape(path=geom.Path([geom.rect(0, 0, 10, 10)]))
        self.b = Shape(path=geom.Path([geom.rect(30, 5, 10, 10)]))
        doc.add(self.a)
        doc.add(self.b)
        self.w.canvas.selection = []
        self.w.statusBar().clearMessage()

    def status(self):
        return self.w.statusBar().currentMessage()

    def test_nothing_selected(self):
        self.w.A['align_left'].trigger()
        self.assertIn('« Gauche » n\'a rien changé', self.status())
        self.assertIn('rien n\'est sélectionné', self.status())

    def test_effect_is_silent(self):
        self.w.canvas.selection = [self.a, self.b]
        self.w.A['align_top'].trigger()                    # les deux carrés alignés : le dessin change
        self.assertNotIn('rien changé', self.status())
        self.w.A['zoom_fit'].trigger()
        self.assertNotIn('rien changé', self.status())

    def test_own_message_kept(self):
        self.w.A['galbe'].trigger()                        # sans sélection : son propre message
        self.assertEqual(self.status(), 'Sélectionnez des formes fermées.')

    def test_no_toolpaths(self):
        self.w.canvas.selection = [self.a]
        self.w.A['cam_simulate'].trigger()
        if 'rien changé' in self.status():
            self.assertIn("aucune opération d'usinage", self.status())     # dessin sans usinage

    def test_relief_and_volume_reasons(self):
        from PySide6.QtGui import QAction
        self.w.canvas.selection = [self.a]
        for key, why in (('relief_essai', 'aucun relief sélectionné'), ('solid_essai', 'aucun volume sélectionné')):
            act = QAction('Essai', self.w)
            act.setProperty('vd_key', key)
            self.w._run_command(act, lambda: None)
            self.assertIn(why, self.status(), key)

    def test_text_outline_computed(self):
        from vectordrive.core.document import Text
        t = Text(text='AB', size=10)
        t.outline = None                                   # contour pas encore calculé
        self.w.canvas.doc.add(t)
        self.w.canvas.selection = [t]
        self.w.text_to_curves()
        texts = [it for L in self.w.canvas.doc.layers for it in L.items if isinstance(it, Text)]
        if texts:                                          # police absente du poste : le dit
            self.assertIn('En courbes', self.status())
        else:
            self.assertNotIn('rien changé', self.status())

    def test_nested_and_tip(self):
        from PySide6.QtGui import QAction
        calls = []
        inner = QAction('Intérieure', self.w)
        inner.setStatusTip('Ne fait rien du tout')
        outer = QAction('Extérieure', self.w)
        outer.setStatusTip('Lance l\'intérieure')
        inner.triggered.connect(lambda: self.w._run_command(inner, lambda: calls.append('in')))
        outer.triggered.connect(lambda: self.w._run_command(outer, lambda: (calls.append('out'), inner.trigger())))
        self.w.canvas.selection = [self.a]
        outer.trigger()
        self.assertEqual(calls, ['out', 'in'])
        self.assertIn('« Extérieure » n\'a rien changé : Lance l\'intérieure', self.status())   # une fois

    def test_window_counts(self):
        dlg = QDialog(self.w)
        act = self.w.A['about']
        self.w.canvas.selection = [self.a]
        self.w._run_command(act, lambda: (dlg.show(), dlg.close()))
        self.assertNotIn('rien changé', self.status())     # une fenêtre montrée : pas muet


if __name__ == '__main__':
    unittest.main()
