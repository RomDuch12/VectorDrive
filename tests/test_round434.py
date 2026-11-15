"""Round 434 : gestionnaire d'outils agrandi / plein écran, barre allégée, filtres ; outils proposés
par opération (réglages et fenêtre)."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from vectordrive.cam import model, toollib, toolprefs

app = QApplication.instance() or QApplication([])


class Settings(dict):
    def value(self, k, d=None):
        return self.get(k, d)

    def setValue(self, k, v):                                         # noqa: N802
        self[k] = v


def tools():
    out = []
    for name, kind, d, vendor, folder in (('F2', 'fraise', 2.0, 'Datron', 'Datron/Fraises'),
                                          ('F6', 'fraise', 6.0, 'Datron', 'Datron/Fraises'),
                                          ('V30', 'conique', 3.0, 'Gravotech', 'Gravure'),
                                          ('B1', 'boule', 1.0, 'Datron', 'Datron/Boules'),
                                          ('Foret 3', 'foret', 3.0, '', 'Perçage')):
        t = model.CamTool(name=name, kind=kind, diameter=d, vendor=vendor)
        t.folder = folder
        out.append(t)
    return out


class TestPrefsCore(unittest.TestCase):
    def test_defaults_and_rules(self):
        ts = tools()
        self.assertEqual([t.name for t in toolprefs.ordered(ts, 'gravure')][:3], ['V30', 'F2', 'F6'])
        self.assertEqual(toolprefs.best(ts, 'percage').name, 'Foret 3')
        self.assertEqual([t.name for t in toolprefs.ordered(ts, 'reste', only=True)], ['F2', 'F6', 'B1'])
        self.assertEqual(toolprefs.ordered(ts, 'laser'), [])                     # « seulement » : aucun laser
        prefs = {'poche': {'rules': [toolprefs.tool_rule(ts[1]), {'type': 'dossier', 'value': 'Datron'}],
                           'mode': 'seuls', 'sort': 'd_asc'}}
        self.assertEqual([t.name for t in toolprefs.ordered(ts, 'poche', prefs)], ['F6', 'B1', 'F2'])
        copy = model.CamTool.from_dict(ts[1].to_dict())                         # copie dans le document
        copy.id, copy.folder = model.new_id(), ''
        self.assertTrue(toolprefs.suits(copy, 'poche', prefs))
        s = Settings()
        toolprefs.save(s, {'poche': prefs['poche'], 'gravure': toolprefs.default_for('gravure')})
        back = toolprefs.load(s)
        self.assertEqual(list(back), ['poche'])                                  # les défauts ne sont pas écrits
        self.assertTrue(toolprefs.customized('poche', back))
        self.assertFalse(toolprefs.customized('gravure', back))

    def test_filters(self):
        ts = tools()
        self.assertEqual([t.name for t in ts if toollib.matches(t, kind='fraise', dmin=3)], ['F6'])
        self.assertEqual([t.name for t in ts if toollib.matches(t, 'datron', dmax=2)], ['F2', 'B1'])
        self.assertEqual([t.name for t in ts if toollib.matches(t, vendor='gravotech')], ['V30'])
        self.assertEqual(toollib.vendors(ts), ['Datron', 'Gravotech'])


class TestManager(unittest.TestCase):
    def setUp(self):
        from vectordrive.ui.toollib_dialog import ToolLibraryDialog
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        p = self.tmp / 'tools.json'
        toollib.save(tools(), p)
        self.dlg = ToolLibraryDialog(None, None, p)

    def tearDown(self):
        self.dlg.close()

    def names(self):
        return [it.text(0).split(' — ')[0] for it in self.dlg._items() if it.data(0, Qt.ItemDataRole.UserRole)]

    def test_bar_and_window(self):
        d = self.dlg
        self.assertTrue(d.windowState() & Qt.WindowState.WindowFullScreen)          # 1016 : plein écran d'office
        self.assertFalse(d.toggle_full_screen())
        self.assertTrue(d.windowState() & Qt.WindowState.WindowMaximized)
        self.assertTrue(d.toggle_full_screen())
        for gone in ('deldir', 'cat', 'draw', 'impdir', 'dup', 'merge', 'keep', 'add', 'del', 'ren'):
            self.assertNotIn(gone, d.buttons)                                        # dans « Plus » / clic droit
        self.assertEqual(d.buttons['take'].defaultAction(), d.acts['keep'])          # sans document : copier
        self.assertFalse(d.acts['keep'].isEnabled())                                 # … déjà dans Mes outils
        texts = [a.text() for a in d.context_menu(exec_menu=False).actions() if a.text()]
        self.assertIn(d.acts['ren'].text(), texts)
        self.assertNotIn(d.acts['keep'].text(), texts)                               # grisée : absente du menu

    def test_filters(self):
        d = self.dlg
        d.filters.kind.setCurrentIndex(d.filters.kind.findData('fraise'))
        self.assertEqual(self.names(), ['F2', 'F6'])
        self.assertIn('2 outil(s) sur 5', d.info.text())
        d.filters.reset()
        d.filters.vendor.setCurrentIndex(d.filters.vendor.findData('Gravotech'))
        self.assertEqual(self.names(), ['V30'])
        d.filters.reset()
        d.filters.op.setCurrentIndex(d.filters.op.findData('percage'))              # adaptés, dans l'ordre
        self.assertEqual(self.names(), ['Foret 3', 'F2', 'F6'])
        top = d.tree.topLevelItem(0).text(0)
        self.assertIn('Proposés pour', top)

    def test_delete_folder_row(self):
        d = self.dlg
        d.select_folder('Datron/Boules')
        d.tree.currentItem().setSelected(True)
        self.assertEqual(d.delete(confirm=False), 1)
        self.assertNotIn('B1', [t.name for t in toollib.load(d.path)])
        self.assertNotIn('Datron/Boules', toollib.folders(toollib.load(d.path)))


class TestPrefsDialog(unittest.TestCase):
    def test_edit_and_save(self):
        from vectordrive.ui.toolprefs_dialog import ToolPrefsDialog
        s = Settings()
        ts = tools()
        dlg = ToolPrefsDialog(None, s, ts, kind='poche')
        self.assertEqual(dlg.kind(), 'poche')
        self.assertEqual(dlg.rules.count(), 2)                                      # fraise, boule
        dlg.add_rule({'type': 'nature', 'value': 'foret'})
        dlg.add_rule({'type': 'nature', 'value': 'foret'})                          # pas deux fois
        self.assertEqual(dlg.rules.count(), 3)
        self.assertTrue(dlg.move_rule(-1))                                          # foret avant boule
        self.assertTrue(dlg.add_folder('Gravure'))
        dlg.mode.setCurrentIndex(dlg.mode.findData('seuls'))
        first = dlg.preview.item(0).text()
        self.assertIn('F2', first)
        self.assertEqual(dlg.preview.count(), 5)
        self.assertTrue(dlg.ops.currentItem().text().startswith('●'))
        self.assertEqual(dlg.copy_to(['contour']), 1)
        dlg.accept()
        back = toolprefs.load(s)
        self.assertEqual(set(back), {'poche', 'contour'})
        self.assertEqual([r['value'] for r in back['poche']['rules']], ['fraise', 'foret', 'boule', 'Gravure'])
        self.assertEqual(back['poche']['mode'], 'seuls')
        dlg2 = ToolPrefsDialog(None, s, ts, kind='poche')
        dlg2.reset_kind()
        dlg2.accept()
        self.assertEqual(set(toolprefs.load(s)), {'contour'})


if __name__ == '__main__':
    unittest.main()
