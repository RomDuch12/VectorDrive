"""Round 1030 : demande du 15/11, 9 h 50 — « Reconnaître une police… » est un bouton à part du ruban du texte ; sa
fenêtre est un panneau de colonne, à droite ou à gauche selon le choix de l'utilisateur (retenu)."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1030.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import QEvent, Qt  # noqa: E402
from PySide6.QtGui import QKeyEvent  # noqa: E402
from PySide6.QtWidgets import QApplication, QDialog, QDockWidget  # noqa: E402

app = QApplication.instance() or QApplication([])

PREFIX = 'panneaux_colonnes'


def forget():
    from vectordrive import portable
    s = portable.settings()
    s.remove(PREFIX)
    s.remove('vue/mode')
    s.remove('vue/panneau_fao')
    s.sync()


def window():
    from vectordrive.ui.main_window import MainWindow
    w = MainWindow()
    w.settings.setValue('fenetre/plein_ecran', False)
    w.show()
    app.processEvents()
    return w


def close(w):
    from shiboken6 import isValid
    if not isValid(w):
        return
    w.modified = False
    for t in getattr(w, 'docks', []):
        t.modified = False
    w.close()
    app.processEvents()


class FontPanel(unittest.TestCase):

    def setUp(self):
        forget()
        self.addCleanup(forget)

    def test_the_button_opens_a_column_panel(self):
        w = window()
        self.addCleanup(close, w)
        d = w.findChild(QDockWidget, 'polices')
        self.assertIsNotNone(d)
        self.assertTrue(d.isHidden())                                         # pas montré d'office
        self.assertIsNone(d.widget())                                         # ni fait (rien à lire au lancement)
        w.A['font_recognize'].trigger()                                       # le bouton du ruban
        app.processEvents()
        self.assertFalse(d.isHidden())
        self.assertFalse(d.isFloating())
        self.assertEqual(w.columns.side(d), 'droite')                         # à droite d'office
        p = d.widget()
        self.assertEqual(p.objectName(), 'fontRecognize')
        self.assertFalse(p.isWindow())                                        # dans le panneau, pas à part
        self.assertIn(d, w.columns.docks())                                   # la fenêtre des colonnes le liste

    def test_left_column_kept_at_relaunch(self):
        w = window()
        self.addCleanup(close, w)
        w.show_font_panel()
        d = w.findChild(QDockWidget, 'polices')
        w.columns.move(d, 'gauche')                                           # le choix de l'utilisateur
        self.assertEqual(w.columns.side(d), 'gauche')
        w.settings.sync()
        close(w)
        w = window()
        self.addCleanup(close, w)
        w.A['font_recognize'].trigger()
        app.processEvents()
        d = w.findChild(QDockWidget, 'polices')
        self.assertEqual(w.columns.side(d), 'gauche')
        self.assertFalse(d.isHidden())

    def test_close_hides_the_panel_escape_does_not(self):
        w = window()
        self.addCleanup(close, w)
        p = w.show_font_panel()
        d = w.findChild(QDockWidget, 'polices')
        over = QKeyEvent(QEvent.Type.ShortcutOverride, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
        over.ignore()
        p.event(over)
        self.assertTrue(over.isAccepted())                                    # Échap pour lui, pas pour l'outil Sélection
        p.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier))
        self.assertFalse(d.isHidden())                                        # Échap : la reconnaissance s'arrête
        self.assertTrue(p.isVisible())
        p.reject()                                                            # « Fermer »
        self.assertTrue(d.isHidden())
        self.assertIs(d.widget(), p)                                          # gardé pour la prochaine fois
        p2 = w.show_font_panel()
        self.assertIs(p2, p)
        self.assertTrue(p.isVisible())                                        # pas caché lui-même

    def test_not_shown_with_its_column(self):
        w = window()
        self.addCleanup(close, w)
        d = w.findChild(QDockWidget, 'polices')
        for x in w.columns.column('droite'):                                  # colonne vide : ce qui revient d'office
            w.columns.close(x)
        w.columns.set_shown('droite', True)
        self.assertTrue(d.isHidden())                                         # pas lui, comme le programme machine
        self.assertTrue(w.columns.shown('droite'))

    def test_back_with_its_column(self):
        w = window()
        self.addCleanup(close, w)
        w.show_font_panel()
        d = w.findChild(QDockWidget, 'polices')
        w.columns.set_shown('droite', False)
        self.assertTrue(d.isHidden())
        w.columns.set_shown('droite', True)                                   # il y était : il revient
        self.assertFalse(d.isHidden())

    def test_restored_by_the_session_with_its_content(self):
        w = window()
        self.addCleanup(close, w)
        w.show_font_panel()
        state = w.saveState()
        w2 = window()
        self.addCleanup(close, w2)
        d2 = w2.findChild(QDockWidget, 'polices')
        self.assertIsNone(d2.widget())
        w2.restoreState(state)                                                # la session le remontre
        app.processEvents()
        self.assertFalse(d2.isHidden())
        self.assertEqual(d2.widget().objectName(), 'fontRecognize')           # pas un panneau vide

    def test_a_separate_button_in_the_text_ribbon(self):
        w = window()
        self.addCleanup(close, w)
        from vectordrive.ui.ribbon import RibbonGroup
        a = w.A['font_recognize']
        alone = [g for g in w.ribbon.findChildren(RibbonGroup) if [b.defaultAction() for b in g.buttons()] == [a]]
        self.assertEqual(len(alone), 1)                                       # son groupe à lui (Mise en forme)

    def test_still_a_dialog_on_its_own(self):
        w = window()
        self.addCleanup(close, w)
        dlg = w.font_recognize_dialog(exec_dialog=False)
        self.addCleanup(dlg.deleteLater)
        self.assertIsInstance(dlg, QDialog)
        self.assertTrue(dlg.isWindow())
        self.assertIsNone(dlg.docked)


if __name__ == '__main__':
    unittest.main()
