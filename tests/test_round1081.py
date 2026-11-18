"""Round 1081 : le panneau FAO ne nomme plus de logiciel de machine dans ses avis (demande du 17/11 soir : « on ne
mentionne plus ND, c'est invisible pour user »)."""
import ast
import json
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1081.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])
ROOT = pathlib.Path(__file__).resolve().parents[1]
PANEL = ROOT / 'vectordrive' / 'ui' / 'cam_panel.py'
BEFORE = 'avant : « opérations propres à la machine (NeoDrive…) » dans les avis du panneau FAO'


def tr_strings(path: pathlib.Path) -> list:
    """Les textes passés à tr() dans le module (montrés à l'utilisateur)."""
    out = []
    for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
        if (isinstance(node, ast.Call) and getattr(node.func, 'id', '') == 'tr' and node.args
                and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)):
            out.append(node.args[0].value)
    return out


class NoMachineSoftwareName(unittest.TestCase):

    def test_cam_panel_messages(self):
        shown = tr_strings(PANEL)
        self.assertFalse([t for t in shown if 'NeoDrive' in t and 'propres à la machine' in t], BEFORE)
        self.assertIn('Orientation de sortie : les opérations propres à la machine (celles de son plugin) ne sont pas '
                      'écrites, elles ne suivent pas l\'orientation', shown)
        self.assertIn('Opérations propres à la machine (celles de son plugin) : non écrites dans les programmes par '
                      'panneau', shown)

    def test_old_translations_do_not_come_back(self):
        """Les traductions des nouveaux avis arrivent à la fin du round ; la langue anglaise ne nomme pas le logiciel
        pour eux."""
        en = json.loads((ROOT / 'vectordrive' / 'ressources' / 'i18n' / 'en.json').read_text(encoding='utf-8'))
        for key in ('Orientation de sortie : les opérations propres à la machine (celles de son plugin) ne sont pas '
                    'écrites, elles ne suivent pas l\'orientation',
                    'Opérations propres à la machine (celles de son plugin) : non écrites dans les programmes par '
                    'panneau'):
            self.assertNotIn('NeoDrive', en.get(key, ''))

    def test_the_note_of_the_panel(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            note = w.cam_panel._orient_note()
            self.assertNotIn('NeoDrive', note, BEFORE)
            self.assertIn('propres à la machine', note)
        finally:
            w.modified = False
            w.close()
            app.processEvents()


if __name__ == '__main__':
    unittest.main()
