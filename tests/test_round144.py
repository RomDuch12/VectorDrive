"""Round 144 : boutons et commandes qui ne faisaient rien — le signal
« clicked » / « triggered » de Qt passe un booléen (False) que la méthode
branchée recevait dans son premier paramètre (exec_dialog, path, key…) :
Options (F10), Raccourcis, Centrer plaque, Simuler, Catalogues en ligne,
Ajouter / Nouveau groupe du ruban personnalisé. À propos sans chemin de
dossier."""
import ast
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

ROOT = pathlib.Path(__file__).resolve().parents[1] / 'vectordrive'
BOOL_SIGNALS = {'clicked', 'triggered'}
#: premiers paramètres faits pour recevoir le booléen
OK_NAMES = {'checked', 'on', '_checked', '_', '_on', 'state', 'enabled', 'visible'}


def risky_connections() -> list[str]:
    """Signal à booléen branché sur une méthode (directement, ou par une
    variable de boucle) dont le premier paramètre n'attend pas ce booléen."""
    out = []
    for f in sorted(ROOT.rglob('*.py')):
        tree = ast.parse(f.read_text(encoding='utf-8'))
        for cls in [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]:
            methods = {m.name: m for m in cls.body if isinstance(m, ast.FunctionDef)}

            def bad(name):
                m = methods.get(name)
                params = m.args.args[1:] if m else []
                return bool(params) and params[0].arg not in OK_NAMES
            for node in ast.walk(cls):
                if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                        and node.func.attr == 'connect' and isinstance(node.func.value, ast.Attribute)
                        and node.func.value.attr in BOOL_SIGNALS and node.args):
                    continue
                t = node.args[0]
                if isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name) and t.value.id == 'self' \
                        and bad(t.attr):
                    out.append(f'{f.name}:{node.lineno} {t.attr}')
                elif isinstance(t, ast.Name):
                    out.append(f'{f.name}:{node.lineno} variable « {t.id} » : envelopper dans une lambda')
    return out


class TestStatic(unittest.TestCase):
    def test_no_bool_into_parameters(self):
        self.assertEqual(risky_connections(), [])


class TestClicks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from PySide6.QtWidgets import QDialog
        from vectordrive.ui.main_window import MainWindow
        self.shown = []
        self._exec = QDialog.exec
        QDialog.exec = lambda d: (self.shown.append(type(d).__name__), 0)[1]
        self.w = MainWindow()

    def tearDown(self):
        from PySide6.QtWidgets import QDialog
        QDialog.exec = self._exec
        self.w.modified = False
        self.w.close()

    def test_options_and_shortcuts_open(self):
        self.w.A['options'].trigger()
        self.w.A['shortcuts'].trigger()
        self.assertGreaterEqual(len(self.shown), 2, self.shown)

    def test_center_on_plate(self):
        from vectordrive.core import geom
        from vectordrive.core.document import Plate, Shape
        w = self.w
        w.canvas.doc.plate = Plate(100, 50)
        sh = Shape(path=geom.Path([geom.rect(0, 0, 10, 10)]))
        w.canvas.doc.add(sh)
        w.canvas.selection = [sh]
        w.A['center_plate'].trigger()                      # recevait False comme axe
        bb = w.canvas.selection[0].bbox()
        self.assertAlmostEqual((bb[0] + bb[2]) / 2, 50, places=6)
        self.assertAlmostEqual((bb[1] + bb[3]) / 2, 25, places=6)

    def test_catalogs_button(self):
        from vectordrive.ui.toollib_dialog import ToolLibraryDialog
        dlg = ToolLibraryDialog(self.w, self.w.cam_panel)
        dlg.acts['cat'].trigger()                          # recevait False comme exec_dialog
        self.assertIn('CatalogsDialog', self.shown)

    def test_about_has_no_path(self):
        from PySide6.QtWidgets import QMessageBox
        got = []
        orig = QMessageBox.about
        QMessageBox.about = staticmethod(lambda parent, title, text: got.append(text))
        try:
            self.w.about()
        finally:
            QMessageBox.about = orig
        self.assertIn('RomDuch with Claude', got[0])
        self.assertIn('romduch@gmail.com', got[0])
        self.assertNotIn(':\\', got[0])
        self.assertNotIn('.ini', got[0].lower())


if __name__ == '__main__':
    unittest.main()
