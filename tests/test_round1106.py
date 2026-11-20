"""Round 1106 : des fenêtres construites sur place (`QDialog(self)`) restaient en mémoire après leur fermeture ; la case
« Limiter aux données » de la multicopie, sans variable, restait sans parent. Mesuré avec un vrai `exec()`."""
import inspect
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1106.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import QEvent, QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])

SITES = (
    ('main_window', 'MainWindow', ('point_by_coordinates', '_params_choice', 'doc_info_dialog', 'chain_dialog',
                                   'dedupe_dialog', 'code_plate_preset', '_text_box_numeric', 'replace_font_dialog',
                                   'point_dialog', 'origin_dialog')),
    ('cam_panel', 'CamPanel', ('apply_template', '_relief_gamme_dialog')),
    ('toollib_dialog', 'ToolLibraryDialog', ('set_machines',)),
    ('assistant_panel', 'AssistantPanel', ('edit_memory',)),
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
            app.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)
            out.append(len(app.allWidgets()))
        return out

    def test_sites_release(self):
        import importlib
        for mod, cls, names in SITES:
            m = importlib.import_module(f'vectordrive.ui.{mod}')
            c = next((v for k, v in vars(m).items() if inspect.isclass(v) and hasattr(v, names[0])), None)
            self.assertIsNotNone(c, (mod, names[0]))
            for name in names:
                src = inspect.getsource(getattr(c, name))
                self.assertRegex(src, r'release\((dlg|d)\)', (mod, name))

    def test_no_growth_real_exec(self):
        w = self.w
        w.canvas.selection = []
        for name, fn in (('plaque codée (préréglage)', w.code_plate_preset), ('infos du document', w.doc_info_dialog),
                         ('doublons', w.dedupe_dialog), ('chaîner', w.chain_dialog),
                         ('origine', w.origin_dialog)):
            with self.subTest(name):
                c = self.counts(fn)
                self.assertEqual(c[-1], c[1], (name, c))

    def test_multicopy_limit_not_orphan(self):
        from vectordrive.ui.multicopy_dialog import MulticopyDialog
        from vectordrive.core import multicopy as MC
        before = {id(x) for x in app.topLevelWidgets()}
        dlg = MulticopyDialog(self.w, (0.0, 0.0, 10.0, 10.0), (0.0, 0.0, 100.0, 100.0), MC.MultiSpec(), [], 0)
        from PySide6.QtWidgets import QCheckBox
        orphans = [x for x in app.topLevelWidgets() if id(x) not in before and isinstance(x, QCheckBox)]
        self.assertEqual(orphans, [])
        self.assertIs(dlg.limit.parentWidget(), dlg)
        dlg.show()
        app.processEvents()
        self.assertFalse(dlg.limit.isVisible())                   # pas posée : cachée
        self.assertEqual(dlg.result_spec().limit_to_rows, MC.MultiSpec().limit_to_rows)   # valeur gardée, comme avant
        dlg.close()
        dlg.deleteLater()


if __name__ == '__main__':
    unittest.main()
