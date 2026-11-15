"""Round 165 : texte machine (police de la commande, n° de série, date)."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.cam import instructions as I, model, strategies as S
from vectordrive.core import geom
from vectordrive.core.document import Document, Shape


def setup(params):
    s = model.CamSetup()
    t = model.CamTool(name='Con', kind='conique', diameter=3, angle=30, number=5)
    s.tools = [t]
    op = model.Operation(kind='texte_machine', tool_id=t.id, depth=0.25, params=params)
    s.operations = [op]
    return s, op


class TestStrategy(unittest.TestCase):
    def test_cycle(self):
        s, op = setup({'text': 'N°', 'variable': 'serie', 'x': 12, 'y': 8, 'depth1': 0.5})
        tp = S.compute(Document(), s, op)
        c = tp.cycles[0]
        self.assertEqual((c['kind'], c['x'], c['y'], c['text'], c['variable']), ('texte_machine', 12, 8, 'N°', 'serie'))
        self.assertEqual(c['depth1'], 0.25)                                       # jamais sous la profondeur finale
        self.assertTrue(any(m.kind == 'rapid' and (m.x, m.y) == (12, 8) for m in tp.moves))
        self.assertTrue(any('Datron' in w for w in tp.warnings))
        self.assertIn('texte_machine', model.OP_KINDS)

    def test_nothing_to_engrave(self):
        s, op = setup({'text': '  '})
        tp = S.compute(Document(), s, op)
        self.assertEqual(tp.cycles, [])
        self.assertIn('rien à graver', tp.warnings[0])

    def test_params_and_pick(self):
        self.assertIs(I.describe('texte_machine'), I.KIND_PARAMS['texte_machine'])
        self.assertEqual(I.params_of('texte_machine', {})['height'], 2.5)
        p = I.from_selection('texte_machine', {'text': 'A'}, (10, 0, 30, 10))
        self.assertEqual((p['x'], p['y'], p['text']), (20, 5, 'A'))


class TestForm(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_form_switches_params(self):
        from vectordrive.ui import cam_panel
        s, op = setup({'text': 'Lot'})
        sel = [Shape(path=geom.Path([geom.rect(0, 0, 40, 10)]))]
        d = cam_panel.FieldsDialog(None, 'Opération', op, Document(), s.tools, selection=sel)
        self.assertEqual(d.param_widgets['text'].text(), 'Lot')
        self.assertFalse(d.rows['params'][1].isHidden())
        self.assertFalse(d.rows['tool_id'][1].isHidden())
        d.pick_button.click()
        self.assertEqual((d.param_widgets['x'].value(), d.param_widgets['y'].value()), (20, 5))
        d.widgets['kind'].setCurrentIndex(d.widgets['kind'].findData('instruction'))
        self.assertIn('message', d.param_widgets)                                 # réglages de l'instruction
        d.widgets['kind'].setCurrentIndex(d.widgets['kind'].findData('gravure'))
        self.assertTrue(d.rows['params'][1].isHidden())
        d.widgets['kind'].setCurrentIndex(d.widgets['kind'].findData('texte_machine'))
        self.assertEqual(d.param_widgets['text'].text(), 'Lot')                   # valeurs gardées
        d.apply()
        self.assertEqual((op.kind, op.params['x'], op.params['text']), ('texte_machine', 20, 'Lot'))
        self.assertIn('texte_machine', cam_panel.PRESETS)


if __name__ == '__main__':
    unittest.main()
