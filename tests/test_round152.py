"""Round 152 : instructions machine (palpage Z, origine, repère, miroir,
messages, retournement, mesure d'outil, préchauffage, table à vide, bloc
de programme) — opérations sans outil ni parcours."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.cam import instructions as I, model, strategies as S
from vectordrive.core.document import Document


class TestModel(unittest.TestCase):
    def test_params_defaults_and_types(self):
        p = I.params_of('palpage_z', {'x': '12.5', 'stock_offset': 0.1, 'inconnu': 3})
        self.assertEqual(p, {'x': 12.5, 'y': 0.0, 'origin_z_shift': 0.0, 'stock_offset': 0.1})
        self.assertEqual(I.params_of('miroir', {}), {'mirror_x': True, 'mirror_y': False})
        self.assertEqual(I.params_of('rien', {'a': 1}), {})
        self.assertIn('palpage_z', I.INSTRUCTIONS)

    def test_compute_without_tool(self):
        s = model.CamSetup()
        op = model.Operation(kind='instruction', instruction='decalage_origine', params={'x': 10, 'z': -0.5})
        s.operations = [op]
        tp = S.compute(Document(), s, op)
        self.assertEqual(tp.moves, [])
        self.assertEqual(tp.warnings, [])
        self.assertEqual(tp.cycles, [{'kind': 'instruction', 'name': 'decalage_origine',
                                      'params': {'x': 10.0, 'y': 0.0, 'z': -0.5}}])
        bad = model.Operation(kind='instruction', instruction='inconnue')
        self.assertTrue(S.compute(Document(), s, bad).warnings)

    def test_in_sequence(self):
        s = model.CamSetup()
        t = model.CamTool(diameter=2)
        s.tools = [t]
        s.operations = [model.Operation(kind='instruction', instruction='mesure_outil'),
                        model.Operation(kind='gravure', tool_id=t.id, depth=0.1),
                        model.Operation(kind='instruction', instruction='message', params={'message': 'Fin'})]
        tps = S.compute_all(Document(), s)
        self.assertEqual([tp.cycles[0]['name'] if tp.cycles else None for tp in tps],
                         ['mesure_outil', None, 'message'])


class TestForm(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_form(self):
        from vectordrive.ui.cam_panel import FieldsDialog, PRESETS
        self.assertIn('instruction', PRESETS)
        o = model.Operation(kind='instruction', instruction='palpage_z', params={'x': 5})
        d = FieldsDialog(None, 'Opération', o)
        d.show()
        self.assertTrue(d.widgets['instruction'].isVisible())
        self.assertFalse(d.widgets['tool_id'].isVisible())                   # ni outil
        self.assertFalse(d.widgets['depth'].isVisible())                     # ni profondeur
        self.assertEqual(sorted(d.param_widgets), ['origin_z_shift', 'stock_offset', 'x', 'y'])
        self.assertEqual(d.param_widgets['x'].value(), 5)
        d.param_widgets['y'].setValue(7)
        combo = d.widgets['instruction']
        combo.setCurrentIndex(combo.findData('message'))
        self.assertEqual(list(d.param_widgets), ['message'])
        d.param_widgets['message'].setText('Changer la fraise')
        d.apply()
        self.assertEqual(o.instruction, 'message')
        self.assertEqual(o.params['message'], 'Changer la fraise')
        self.assertEqual(o.params['y'], 7)                                   # gardé de l'instruction d'avant
        d.widgets['kind'].setCurrentIndex(d.widgets['kind'].findData('gravure'))
        self.assertTrue(d.widgets['tool_id'].isVisible())
        self.assertFalse(d.widgets['instruction'].isVisible())
        d.close()

    def test_text_block(self):
        from vectordrive.ui.cam_panel import FieldsDialog
        o = model.Operation(kind='instruction', instruction='bloc', params={'texte': 'Spindle Off'})
        d = FieldsDialog(None, 'Opération', o)
        w = d.param_widgets['texte']
        self.assertEqual(w.toPlainText(), 'Spindle Off')
        w.setPlainText('Spindle Off\nSleep minutes=1')
        d.apply()
        self.assertEqual(o.params['texte'], 'Spindle Off\nSleep minutes=1')
        d.close()


if __name__ == '__main__':
    unittest.main()
