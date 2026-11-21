"""Round 1133 (demande du 20/11, 21 h 48) : Options › Assistant en mode Débutant, les réglages courants seulement ;
la recherche trouve tout."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1133.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'
os.environ['VECTORDRIVE_KEYS_MEMORY'] = '1'

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])

import tests  # noqa: E402,F401

BEFORE = 'avant : la page Assistant montre tout en mode Débutant'


class Page(unittest.TestCase):

    def setUp(self):
        from vectordrive.ui import options as O
        if not hasattr(O, 'ASSISTANT_ADVANCED'):
            self.fail(BEFORE)
        self.O = O
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.addCleanup(self.clean)

    def clean(self):
        self.w.settings.remove('assistant/mode')
        self.w.modified = False
        self.w.close()
        self.w.deleteLater()
        app.processEvents()

    def dialog(self, mode):
        self.w.settings.setValue('assistant/mode', mode)
        d = self.w.options_dialog(exec_dialog=False, page='Assistant')
        self.addCleanup(d.deleteLater)
        return d

    def shown(self, d, key):
        w = d.widgets[key]
        return w.isVisibleTo(d)

    def test_all_advanced_keys_exist(self):
        self.assertTrue(self.O.ASSISTANT_ADVANCED <= set(self.O.BY_KEY))

    def test_beginner_sees_the_essentials(self):
        d = self.dialog('debutant')
        d.show()
        app.processEvents()
        for k in ('assistant/mode', 'assistant/fournisseur', 'assistant/valider', 'assistant/plafond_session'):
            self.assertTrue(self.shown(d, k), k)
        for k in ('assistant/modele_mistral', 'assistant/outils_fao', 'assistant/couleur_vous'):
            self.assertFalse(self.shown(d, k), k)
        self.assertTrue(d.assistant_note.isVisibleTo(d))
        d.search.setText('couleur')
        self.assertTrue(self.shown(d, 'assistant/couleur_vous'), 'la recherche trouve tout')
        d.search.setText('')
        self.assertFalse(self.shown(d, 'assistant/couleur_vous'))
        mode = d.widgets['assistant/mode']
        mode.setCurrentIndex(mode.findData('avance'))
        self.assertTrue(self.shown(d, 'assistant/modele_mistral'), 'Avancé choisi dans la fenêtre : tout')
        self.assertFalse(d.assistant_note.isVisibleTo(d))
        d.hide()

    def test_advanced_sees_everything(self):
        d = self.dialog('avance')
        d.show()
        app.processEvents()
        for k in self.O.ASSISTANT_ADVANCED:
            self.assertTrue(self.shown(d, k), k)
        d.hide()


if __name__ == '__main__':
    unittest.main()
