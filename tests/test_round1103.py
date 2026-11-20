"""Round 1103 : des fenêtres ouvertes par `exec()` (espace de travail, bridage, brut, préférences d'outils, lettres,
scripts…) restaient en mémoire après leur fermeture ; elles sont libérées comme les formulaires (`fit.release`).
Mesuré avec un vrai `exec()` : un `exec` remplacé n'émet pas `finished` et ne dit rien de la libération."""
import inspect
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1103.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])

CLASSES = (
    ('toolprefs_dialog', 'ToolPrefsDialog'), ('stock_dialog', 'StockDialog'), ('stock2d_dialog', 'Stock2DDialog'),
    ('fixture_dialog', 'FixtureDialog'), ('workspace_dialog', 'WorkspaceDialog'), ('letters_dialog', 'LettersDialog'),
    ('script_dialog', 'ScriptDialog'), ('dash_dialog', 'DashDialog'), ('stamp_dialog', 'StampDialog'),
    ('multicopy_dialog', 'MulticopyDialog'), ('copy_nest_dialog', 'CopyNestDialog'), ('edges3d_dialog', 'EdgesDialog'),
    ('guides_dialog', 'GuidesDialog'), ('instruction_catalog', 'CatalogDialog'), ('font_editor', 'CloneBox'),
    ('text_columns_dialog', 'TextColumnsDialog'), ('rest_preview_dialog', 'RestPreviewDialog'),
)


class TestReleased(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from vectordrive.ui.main_window import MainWindow
        cls.w = MainWindow()
        cls.w.show()
        app.processEvents()
        cls.timer = QTimer()
        cls.timer.timeout.connect(cls._close_modal)
        cls.timer.start(30)

    @classmethod
    def tearDownClass(cls):
        cls.timer.stop()
        cls.w.modified = False
        for t in getattr(cls.w, 'docs', []):
            t.modified = False
        cls.w.close()
        cls.w.deleteLater()

    @staticmethod
    def _close_modal():
        m = app.activeModalWidget()
        if m is not None:
            m.reject()

    def counts(self, fn, n=4):
        out = []
        for _ in range(n):
            fn()
            for _ in range(6):
                app.processEvents()
            out.append(len(app.allWidgets()))
        return out

    def test_classes_release(self):
        import importlib
        for mod, cls in CLASSES:
            c = getattr(importlib.import_module(f'vectordrive.ui.{mod}'), cls)
            self.assertIn('release(self)', inspect.getsource(c.__init__), cls)
        from vectordrive.ui import cam_panel, main_window
        for fn in (main_window.MainWindow._confirm_machine_export,
                   main_window.MainWindow.cad_massprop):
            if fn is not None:
                self.assertIn('release(box)', inspect.getsource(fn))
        self.assertEqual(inspect.getsource(main_window).count('release(box)'), 3)    # boîtes de message construites
        self.assertEqual(inspect.getsource(cam_panel).count('release(box)'), 1)

    def test_doc_window_outlives_catalog(self):
        # le PDF ouvert depuis le catalogue reste ouvert quand le catalogue (libéré) est détruit ; réemployé ensuite
        from shiboken6 import isValid
        from PySide6.QtCore import QEvent, QSettings
        from PySide6.QtWidgets import QWidget
        from vectordrive.cam import catalog as C
        from vectordrive.ui import instruction_catalog as IC
        from tests.test_round488 import make_pdf
        pdf = make_pdf(3)
        e = C.Entry(name='Commande', text='Commande', doc=pdf, page=2, catalog='Essai')
        st = QSettings(os.path.join(tempfile.mkdtemp(), 'd.ini'), QSettings.Format.IniFormat)
        host = QWidget()
        dlg = IC.CatalogDialog(host, catalogs=[('Essai', [e], '')], settings=st)
        dlg.tree.setCurrentItem(dlg.entries()[0][0])
        win = dlg.open_doc()
        self.assertIs(win.parentWidget(), dlg)         # catalogue ouvert (modal) : son enfant, pas figée par lui
        dlg.done(0)                                    # fermé : passée à la fenêtre principale, toujours ouverte
        self.assertIs(win.parentWidget(), host)
        self.assertTrue(win.isVisible())
        dlg.deleteLater()
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.assertFalse(isValid(dlg))
        self.assertTrue(isValid(win) and win.isVisible())
        again = IC.CatalogDialog(host, catalogs=[('Essai', [e], '')], settings=st)
        again.tree.setCurrentItem(again.entries()[0][0])
        self.assertIs(again.open_doc(), win)
        self.assertIs(win.parentWidget(), again)
        win.close()
        again.deleteLater()
        host.deleteLater()

    def test_no_growth_real_exec(self):
        cp = self.w.cam_panel
        for name, fn in (('scripts', self.w.shape_script), ('brut', cp.stock_dialog), ('brut 2D', cp.stock2d_dialog),
                         ('espace de travail', cp.workspace_dialog), ('préférences d\'outils', cp.tool_prefs),
                         ('tableau de texte', self.w.text_table),
                         ('options (déjà libérées)', self.w.options_dialog),
                         ('opération (déjà libérée)', lambda: cp.new_operation('gravure'))):
            with self.subTest(name):
                c = self.counts(fn)
                self.assertEqual(c[-1], c[0], (name, c))


if __name__ == '__main__':
    unittest.main()
