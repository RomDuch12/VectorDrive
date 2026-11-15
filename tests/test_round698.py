"""Round 698 : un parcours de la palette par stratégie — son formulaire n'a
plus la liste des stratégies et s'ouvre prérempli avec les dernières valeurs
validées pour ce parcours (outil compris ; hauteurs de F10 et nom d'origine) ;
dernières valeurs enregistrées en modèle ou oubliées depuis la palette."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])


def square(win, x=0.0):
    from vectordrive.core import geom
    from vectordrive.core.document import Shape
    sh = Shape(path=geom.Path([geom.rect(x, 0, 20, 10)]), tool=0)
    win.canvas.doc.add(sh)
    win.canvas.select([sh])
    return sh


class TestLastValues(unittest.TestCase):
    def setUp(self):
        from vectordrive.ui.cam_panel import CamPanel
        from vectordrive.ui.main_window import MainWindow
        self._tpl = os.environ.get('VECTORDRIVE_CAM_TEMPLATES')
        os.environ['VECTORDRIVE_CAM_TEMPLATES'] = tempfile.mkdtemp()
        self.w = MainWindow()
        self.w.settings.remove(CamPanel.LAST_KEY)         # aucun reste d'un autre essai du même processus
        self.p = self.w.cam_panel
        square(self.w)

    def tearDown(self):
        from vectordrive.ui.cam_panel import CamPanel
        self.w.settings.remove(CamPanel.LAST_KEY)
        if self._tpl is not None:
            os.environ['VECTORDRIVE_CAM_TEMPLATES'] = self._tpl
        self.w.modified = False
        self.w.close()

    def add_tool(self, name, diameter, number):
        from vectordrive.cam import model
        t = model.CamTool(name=name, diameter=diameter, number=number)
        s = self.p.setup()
        s.tools.append(t)
        self.p.save(s)
        return t

    def run_form(self, key, edit=None, ok=True, **kw):
        """Nouveau parcours `key` par son formulaire : `edit(dlg)` le remplit, OK ou Annuler."""
        from vectordrive.ui import cam_panel as CP
        seen = {}

        def fake_exec(dlg):
            seen['dlg'] = dlg
            seen['depth'] = dlg.widgets['depth'].value()
            seen['tool'] = dlg.widgets['tool_id'].currentData()
            seen['kind_hidden'] = dlg.rows['kind'][1].isHidden()
            if edit is not None:
                edit(dlg)
            return 1 if ok else 0
        with mock.patch.object(CP.FieldsDialog, 'exec', fake_exec):
            op = self.p.new_operation(key, **kw)
        return op, seen

    def test_form_without_kind_list(self):
        from vectordrive.cam import model
        from vectordrive.ui.cam_panel import FieldsDialog
        op, seen = self.run_form('decoupe')
        self.assertTrue(seen['kind_hidden'])                             # nouveau parcours : pas de liste
        self.assertEqual(op.kind, 'contour')
        s = self.p.setup()
        dlg = FieldsDialog(self.p, 'essai', model.Operation.from_dict(op.to_dict()), self.w.canvas.doc, s.tools)
        self.assertTrue(dlg.rows['kind'][1].isHidden())                  # round 1019 : jamais de liste
        self.assertFalse(dlg.rows['kind_label'][1].isHidden())           # le type de parcours, montré
        dlg.close()

    def test_prefilled_with_last_values(self):
        from vectordrive.ui.options import value
        big = self.add_tool('Fraise Ø6', 6.0, 7)

        def edit(dlg):
            dlg.widgets['depth'].setValue(2.7)
            dlg.widgets['safe_z'].setValue(33.0)
            dlg.widgets['name'].setText('Découpe du cadre')
            dlg.widgets['tool_id'].setCurrentIndex(dlg.widgets['tool_id'].findData(big.id))
        first, seen = self.run_form('decoupe', edit)
        self.assertEqual(seen['depth'], 1.0)                             # premier emploi : réglages d'origine
        self.assertEqual((first.depth, first.tool_id), (2.7, big.id))
        tip = self.w.cam_palette.tip('decoupe')
        self.assertIn('dernières valeurs', tip)
        second, seen = self.run_form('decoupe')
        self.assertEqual((seen['depth'], seen['tool']), (2.7, big.id))   # prérempli : profondeur, outil
        self.assertEqual(second.safe_z, value(self.w.settings, 'fao/z_degagement'))   # hauteurs de F10
        self.assertEqual(second.name, 'Découpe')                         # nom d'origine du parcours
        self.assertEqual(second.items, first.items)
        other = self.p.new_operation('decoupe', exec_dialog=False)     # sans formulaire : réglages d'origine
        self.assertEqual(other.depth, 1.0)
        third, seen = self.run_form('trace')
        self.assertNotEqual(seen['depth'], 2.7)                          # chaque parcours a les siennes

    def test_tool_added_when_missing(self):
        big = self.add_tool('Fraise Ø6', 6.0, 7)
        self.run_form('decoupe', lambda dlg: dlg.widgets['tool_id'].setCurrentIndex(
            dlg.widgets['tool_id'].findData(big.id)))
        s = self.p.setup()
        s.operations.clear()
        s.tools = [t for t in s.tools if t.id != big.id]                 # autre dessin : l'outil n'y est pas
        n = len(s.tools)
        self.p.save(s)
        op, _seen = self.run_form('decoupe')
        s = self.p.setup()
        tool = s.tool(op.tool_id)
        self.assertEqual((tool.name, tool.diameter), ('Fraise Ø6', 6.0))
        self.assertEqual(len(s.tools), n + 1)                            # seul l'outil retenu est ajouté

    def test_cancel_adds_nothing(self):
        tools = [t.id for t in self.p.setup().tools]
        op, _seen = self.run_form('decoupe', lambda dlg: dlg.widgets['depth'].setValue(4.0), ok=False)
        self.assertIsNone(op)
        self.assertEqual([t.id for t in self.p.setup().tools], tools)    # aucun outil laissé par le formulaire
        self.assertIsNone(self.p.last_values('decoupe'))                 # annulé : rien de retenu

    def test_template_wins_and_is_remembered(self):
        from vectordrive.cam import model
        from vectordrive.cam import templates as TPL
        self.run_form('decoupe', lambda dlg: dlg.widgets['depth'].setValue(2.7))
        op = model.Operation(name='Découpe fine', kind='contour', depth=0.4)
        TPL.save_user(TPL.single(op, None, 'Fine', 'decoupe'))
        got, seen = self.run_form('decoupe', template='Fine')
        self.assertEqual(seen['depth'], 0.4)                             # le modèle choisi, pas les dernières
        self.assertEqual(got.name, 'Découpe fine')
        _again, seen = self.run_form('decoupe')
        self.assertEqual(seen['depth'], 0.4)                             # le modèle employé : dernières valeurs

    def test_reste_reference_tool(self):
        small = self.add_tool('Fraise Ø1', 1.0, 8)
        big = self.add_tool('Fraise Ø6', 6.0, 9)
        first, _seen = self.run_form('reste')
        self.assertEqual((first.tool_id, first.ref_tool_id), (small.id, big.id))
        second, seen = self.run_form('reste')
        self.assertEqual(seen['tool'], small.id)
        self.assertEqual(second.ref_tool_id, big.id)                     # outil de référence : le plus gros

    def test_palette_save_and_forget(self):
        from vectordrive.cam import templates as TPL
        self.run_form('decoupe', lambda dlg: dlg.widgets['depth'].setValue(2.7))
        pal = self.w.cam_palette
        self.assertEqual(pal.save_last('decoupe', 'Mes réglages de découpe'), 'Mes réglages de découpe')
        tpl = TPL.user_templates()['Mes réglages de découpe']
        self.assertEqual((tpl['preset'], tpl['operations'][0]['depth']), ('decoupe', 2.7))
        self.assertIn('Mes réglages de découpe', self.p.templates_for('decoupe'))
        self.assertTrue(pal.forget_last('decoupe'))
        self.assertIsNone(self.p.last_values('decoupe'))
        self.assertNotIn('dernières valeurs', pal.tip('decoupe'))
        self.assertIsNone(pal.save_last('decoupe', 'Rien'))              # plus rien à enregistrer
        _op, seen = self.run_form('decoupe')
        self.assertEqual(seen['depth'], 1.0)                             # réglages d'origine


if __name__ == '__main__':
    unittest.main()
