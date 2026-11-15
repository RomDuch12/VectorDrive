"""Round 977 : au lancement, plein écran d'office tant que rien n'est retenu ; la dernière fenêtre (plein écran, ou
place et taille) est retenue pour tout nouveau lancement ; quitter le plein écran rend la fenêtre d'avant."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r977.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import QRect  # noqa: E402
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


def rect(w):
    g = w.geometry()
    return (g.x(), g.y(), g.width(), g.height())


def sized(w):
    """Place horizontale et taille (la hauteur de la barre de titre de l'écran des essais décale le haut)."""
    r = w if isinstance(w, tuple) else rect(w)
    return (r[0], r[2], r[3])


class Start(unittest.TestCase):

    def setUp(self):
        w = window()
        for k in KEYS:
            w.settings.remove(k)
        w.settings.sync()
        w.deleteLater()

    def tearDown(self):
        w = window()
        for k in KEYS:
            w.settings.remove(k)
        w.settings.setValue('fenetre/plein_ecran', False)
        w.deleteLater()

    def test_a_first_start_is_full_screen(self):
        w = window()
        self.assertTrue(w.wants_full_screen())                       # avant : la fenêtre agrandie
        self.assertEqual(w.show_at_start(), 'taskbar')               # barre des tâches visible (round 1038)
        self.assertTrue(w.is_full_screen())
        close(w)
        again = window()
        self.assertEqual(again.show_at_start(), 'taskbar')           # fermé en plein écran : rouvert en plein écran
        again.set_keep_taskbar(False)                                # … sans la barre des tâches
        close(again)
        third = window()
        self.assertEqual(third.show_at_start(), 'full')
        close(third)

    def test_the_last_window_comes_back(self):
        first = window()
        first.settings.setValue('fenetre/plein_ecran', False)
        self.assertEqual(first.show_at_start(), 'maximized')         # rien de retenu : agrandie
        close(first)
        first.settings.remove('fenetre/geometrie')
        w = window()
        w.setGeometry(QRect(60, 0, 700, 500))
        w.show()
        app.processEvents()
        w0 = rect(w)                                                 # (la fenêtre a sa hauteur minimale)
        self.assertEqual((w0[0], w0[2]), (60, 700))
        close(w)                                                     # fermée : sa place et sa taille sont retenues
        again = window()
        self.assertEqual(again.show_at_start(), 'window')            # avant : agrandie (sans session, rien de retenu)
        app.processEvents()
        self.assertEqual(sized(again), sized(w0))
        again.cycle_full_screen()                                    # plein écran…
        self.assertTrue(again.is_full_screen())
        self.assertFalse(again.remember_window())                    # … qui ne remplace pas la fenêtre retenue
        again.set_full_screen(False)
        app.processEvents()
        self.assertFalse(again.is_full_screen())
        self.assertEqual(sized(again), sized(w0))                    # quitter le plein écran : la fenêtre d'avant
        close(again)


if __name__ == '__main__':
    unittest.main()
