"""Round 1038 : demande du 15/11 ~17 h 20 « queue démarrage initial en plein ecran avec taskbar visible; »."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1038.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])

KEYS = ('fenetre/plein_ecran', 'fenetre/plein_ecran_barre', 'fenetre/geometrie')


def window():
    from vectordrive.ui.main_window import MainWindow
    return MainWindow()


def close(w):
    w.modified = False
    for t in getattr(w, 'docs', []):
        t.modified = False
    w.close()
    app.processEvents()


class FirstStart(unittest.TestCase):

    def setUp(self):
        w = window()
        for k in KEYS:
            w.settings.remove(k)
        w.settings.sync()
        w.deleteLater()

    tearDown = setUp

    def test_full_screen_with_the_taskbar(self):
        w = window()
        self.assertEqual(w.show_at_start(), 'taskbar')                       # avant : 'full', la barre cachée
        self.assertTrue(w.is_full_screen())
        self.assertTrue(w.keeps_taskbar())
        self.assertEqual(w.geometry(), w.screen().availableGeometry())       # la zone de travail de l'écran
        self.assertTrue(w.A['full_screen_taskbar'].isChecked())              # la case du menu le dit
        close(w)
        again = window()
        self.assertEqual(again.show_at_start(), 'taskbar')                   # retenu
        close(again)

    def test_a_choice_already_made_stays(self):
        w = window()
        self.assertEqual(w.show_at_start(), 'taskbar')                       # (avant : 'full')
        close(w)
        w.settings.setValue('fenetre/plein_ecran_barre', False)              # la barre cachée, choisie
        again = window()
        self.assertEqual(again.show_at_start(), 'full')
        close(again)
        for k in KEYS:
            again.settings.remove(k)
        again.settings.setValue('fenetre/plein_ecran', True)                 # déjà lancé (version d'avant) :
        third = window()                                                     # son plein écran ne change pas
        self.assertEqual(third.show_at_start(), 'full')
        close(third)


if __name__ == '__main__':
    unittest.main()
