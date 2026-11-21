"""Round 1130 (demande du 20/11, 21 h 48) : des boutons IA tout prêts (modèles), à relire puis garder."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1130.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'
os.environ['VECTORDRIVE_KEYS_MEMORY'] = '1'

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])

import tests  # noqa: E402,F401

BEFORE = 'avant : pas de modèles de boutons IA'


class Templates(unittest.TestCase):

    def setUp(self):
        from vectordrive.agent import ai_buttons as AB
        if not hasattr(AB, 'TEMPLATES'):
            self.fail(BEFORE)
        self.AB = AB
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.w.settings.remove(AB.KEY)
        self.w.settings.remove(self.w.FAV_KEY)
        self.addCleanup(self.clean)
        self.p = self.w.show_assistant_panel()

    def clean(self):
        self.p.shutdown()
        self.w.settings.remove(self.AB.KEY)
        self.w.settings.remove(self.w.FAV_KEY)
        self.w.modified = False
        self.w.close()
        self.w.deleteLater()
        app.processEvents()

    def test_templates_are_valid(self):
        AB = self.AB
        self.assertGreaterEqual(len(AB.TEMPLATES), 4)
        ids = set()
        for i in range(len(AB.TEMPLATES)):
            b = AB.template(i)
            self.assertTrue(b.label and b.task, i)
            self.assertIn(b.scope, AB.SCOPES)
            self.assertIn(b.control, AB.CONTROLS)
            self.assertTrue(set(b.tools) <= set(AB.GROUPS))
            ids.add(b.id)
        self.assertEqual(len(ids), len(AB.TEMPLATES), 'un identifiant neuf chacun')

    def test_the_plus_menu(self):
        texts = [a.text() for a in self.p.ai_add.menu().actions() if a.text()]
        self.assertEqual(texts[0], 'Nouveau bouton IA…')
        self.assertIn('Depuis un modèle', texts)
        for t in self.AB.TEMPLATES:
            self.assertIn(t[0], texts)

    def test_create_from_a_template(self):
        i = [t[0] for t in self.AB.TEMPLATES].index('Vérifier avant la FAO')
        d = self.p.new_ai_button(exec_dialog=False, template=i)
        self.assertEqual(d.windowTitle(), 'Nouveau bouton IA')
        self.assertEqual(d.label.text(), 'Vérifier avant la FAO')
        self.assertEqual(d.scope.currentData(), 'tous')
        self.assertEqual(d.control.currentData(), 'verification')
        self.assertIn('Ne modifie rien', d.rules.toPlainText())
        d.label.setText('Contrôle')
        d.keep()
        got = self.AB.load(self.w.settings)
        self.assertEqual([b.label for b in got], ['Contrôle'])
        self.assertIn(got[0].key, self.w.favorite_keys())
        d2 = self.p.new_ai_button(exec_dialog=False, template=i)
        d2.keep()
        got = self.AB.load(self.w.settings)
        self.assertEqual(len({b.id for b in got}), 2, 'deux boutons distincts depuis le même modèle')


if __name__ == '__main__':
    unittest.main()
