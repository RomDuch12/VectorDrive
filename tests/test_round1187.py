"""Round 1187 — correctif du round 1185 : la fin de l'application ne plante plus. Des fenêtres principales fermées mais
pas détruites (l'autotest en laisse une dizaine) sont détruites par l'interpréteur à sa fin ; Qt masque alors leurs
panneaux, et le filtre des panneaux masqués du round 1185 armait une minuterie sur un rangement de colonnes en pleine
destruction : violation d'accès (code de sortie 139, une fois sur trois ou plus)."""
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.abspath(__file__)
ROOT = os.path.dirname(os.path.dirname(HERE))


def child(n=8):
    """Dans un processus à part : n fenêtres faites, montrées, fermées sans être détruites, puis la fin."""
    tmp = tempfile.mkdtemp(prefix='vd_r1187_')
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'
    os.environ['VECTORDRIVE_NO_PLUGINS'] = '1'
    os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'
    for k, v in (('VECTORDRIVE_SETTINGS', 'reglages.ini'), ('VECTORDRIVE_CACHE', ''),
                 ('VECTORDRIVE_SESSION', 'session'), ('VECTORDRIVE_TOOLS', 'outils/tools.json'),
                 ('VECTORDRIVE_SESSION_TEMP', 'sessions'), ('VECTORDRIVE_CAM_TEMPLATES', 'modeles_fao'),
                 ('VECTORDRIVE_BIBLIOTHEQUE', 'bibliotheque')):
        os.environ[k] = os.path.join(tmp, v) if v else tmp
    sys.path.insert(0, ROOT)
    import tests  # noqa: F401  (dossiers du poste redirigés)
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from vectordrive.ui.main_window import MainWindow
    keep = []
    for _ in range(n):
        w = MainWindow()
        w.show()
        app.processEvents()
        w.modified = False
        w.close()
        app.processEvents()
        keep.append(w)
    print('fenêtres', len(keep), flush=True)


class EndOfApplication(unittest.TestCase):

    def test_windows_left_closed_end_cleanly(self):
        env = dict(os.environ)
        env['LOCALAPPDATA'] = tempfile.mkdtemp(prefix='vd_r1187_lad_')
        for i in range(4):                                     # le plantage n'était pas systématique
            r = subprocess.run([sys.executable, HERE, 'enfant'], cwd=ROOT, env=env, capture_output=True,
                               text=True, encoding='utf-8', errors='replace', timeout=600)
            self.assertIn('fenêtres 8', r.stdout, r.stderr[-2000:])
            self.assertEqual(r.returncode, 0, f'passage {i + 1} : avant, violation d’accès à la fin\n'
                             + r.stderr[-2000:])

    def test_the_filter_rests_while_the_window_is_closed(self):
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        import tests  # noqa: F401
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            w.show()
            app.processEvents()
            self.assertTrue(getattr(w.columns, '_win_shown', None), 'avant : aucun repère de la fenêtre montrée')
            w.close()
            app.processEvents()
            self.assertFalse(w.columns._win_shown)
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__' and sys.argv[1:] == ['enfant']:
    child()
elif __name__ == '__main__':
    unittest.main()
