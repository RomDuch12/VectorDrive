"""Round 435 : outils proposés par opération appliqués — liste du formulaire, Choisir un outil,
boutons de la palette, Relief > Outil."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication, QWidget

from vectordrive.cam import model, toolprefs

app = QApplication.instance() or QApplication([])


class Settings(dict):
    def value(self, k, d=None):
        return self.get(k, d)

    def setValue(self, k, v):                                         # noqa: N802
        self[k] = v


class Parent(QWidget):
    def __init__(self, settings):
        super().__init__()
        self.settings = settings


def library():
    out = []
    for name, kind, d, folder in (('Lib F3', 'fraise', 3.0, 'Datron/Fraises'), ('Lib B1', 'boule', 1.0, 'Datron/Boules'),
                                  ('Lib B2', 'boule', 2.0, 'Datron/Boules'), ('Lib V60', 'conique', 4.0, 'Gravure')):
        t = model.CamTool(name=name, kind=kind, diameter=d)
        t.folder = folder
        out.append(t)
    return out


class TestForm(unittest.TestCase):
    def setUp(self):
        self.s = Settings()
        self.parent = Parent(self.s)
        self.f2 = model.CamTool(name='F2', kind='fraise', diameter=2.0, number=1)
        self.v30 = model.CamTool(name='V30', kind='conique', diameter=3.0, number=2)
        self.lib = library()

    def form(self, kind, tool):
        from vectordrive.ui.cam_panel import FieldsDialog
        op = model.Operation(kind=kind, tool_id=tool.id)
        return FieldsDialog(self.parent, 'essai', op, None, [self.f2, self.v30], library=self.lib)

    def datas(self, dlg):
        c = dlg.widgets['tool_id']
        return [c.itemData(i) for i in range(c.count()) if c.itemData(i)]

    def test_default_order(self):
        self.assertEqual(self.datas(self.form('gravure', self.f2))[:2], [self.v30.id, self.f2.id])   # conique d'abord
        self.assertEqual(self.datas(self.form('poche', self.f2)), [self.f2.id, self.v30.id, '__choisir__'])

    def test_customized(self):
        toolprefs.save(self.s, {'poche': {'rules': [{'type': 'dossier', 'value': 'Datron/Boules'},
                                                    {'type': 'nature', 'value': 'fraise'}],
                                          'mode': 'seuls', 'sort': 'd_desc'}})
        d = self.form('poche', self.f2)
        lib = {t.name: t.id for t in self.lib}
        self.assertEqual(self.datas(d), [self.f2.id, 'lib:' + lib['Lib B2'], 'lib:' + lib['Lib B1'],
                                         'lib:' + lib['Lib F3'], '__choisir__'])   # V30 caché : pas adapté
        d2 = self.form('poche', self.v30)                                    # l'outil choisi reste dans la liste
        self.assertIn(self.v30.id, self.datas(d2))

    def test_picker(self):
        toolprefs.save(self.s, {'poche': {'rules': [{'type': 'nature', 'value': 'boule'}], 'mode': 'seuls'}})
        d = self.form('poche', self.f2)
        pick = d.widgets['tool_id'].choose(exec_dialog=False)
        top = pick.tree.topLevelItem(0)
        self.assertIn('Proposés pour', top.text(0))
        self.assertEqual([top.child(i).text(0).split(' — ')[0] for i in range(top.childCount())], ['Lib B1', 'Lib B2'])
        self.assertTrue(pick.only.isChecked())
        visible = {it.text(0).split(' — ')[0] for it in pick._items() if it.data(0, 0x0100) and not it.isHidden()}
        self.assertEqual(visible, {'Lib B1', 'Lib B2'})
        pick.only.setChecked(False)
        visible = {it.text(0).split(' — ')[0] for it in pick._items() if it.data(0, 0x0100) and not it.isHidden()}
        self.assertIn('F2', visible)
        pick.filters.dmin.setValue(1.5)                                      # filtre de Ø
        visible = {it.text(0).split(' — ')[0] for it in pick._items() if it.data(0, 0x0100) and not it.isHidden()}
        self.assertNotIn('Lib B1', visible)
        dlg = pick.tool_prefs(exec_dialog=False)
        self.assertEqual(dlg.kind(), 'poche')
        pick.deleteLater()


class TestPalette(unittest.TestCase):
    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.cp = self.w.cam_panel

    def tearDown(self):
        self.w.settings.setValue(toolprefs.KEY, '')
        self.w.modified = False
        self.w.close()

    def test_tool_for(self):
        s = model.CamSetup()
        f6 = model.CamTool(name='F6', kind='fraise', diameter=6.0)
        f1 = model.CamTool(name='F1', kind='fraise', diameter=1.0)
        s.tools = [f6, f1]
        self.assertIs(self.cp._tool_for(s, 'fraise', op_kind='poche'), f6)               # non réglé : comme avant
        toolprefs.save(self.w.settings, {'poche': {'rules': [{'type': 'nature', 'value': 'fraise'}], 'sort': 'd_asc'}})
        self.assertIs(self.cp._tool_for(s, 'fraise', op_kind='poche'), f1)
        toolprefs.save(self.w.settings, {'poche': {'rules': [{'type': 'nature', 'value': 'boule'}]}})
        with mock.patch.object(self.cp, 'library_tools', return_value=library()):
            t = self.cp._tool_for(s, 'fraise', op_kind='poche')                        # pris dans Mes outils
        self.assertEqual((t.name, t.folder), ('Lib B1', ''))
        self.assertIn(t, s.tools)


if __name__ == '__main__':
    unittest.main()
