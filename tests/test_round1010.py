"""Round 1010 : demande du 14/11 — un champ à 0 qui prend la valeur de l'outil la montre, avec son unité (« 600
mm/min (outil) »), plus de « celle de l'outil » ; « Profondeurs » au-dessus d'« Entrées et liaisons »."""
import json
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1010.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import QLocale  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])

from vectordrive import portable  # noqa: E402
from vectordrive.cam import model  # noqa: E402
from vectordrive.i18n import tr  # noqa: E402
from vectordrive.ui import cam_panel as CP  # noqa: E402


def forget():
    s = portable.settings()
    for k in (CP.CASES_KEYS[True], 'fao/cases_operation2_profondeurs'):
        s.remove(k)
    s.sync()


class ToolValues(unittest.TestCase):

    def setUp(self):
        self.big = model.CamTool(name='Cyl 2', diameter=2.0, feed=750.0, plunge=150.0, spindle=18000.0,
                                 step_down=0.3, stepover=0.5, number=1)
        self.small = model.CamTool(name='Cyl 1', diameter=1.0, feed=420.5, plunge=90.0, spindle=24000.0,
                                   step_down=0.15, stepover=0.4, number=2)

    def open(self, **kw):
        op = model.Operation(kind='poche', tool_id=self.big.id, **kw)
        d = CP.FieldsDialog(None, 'essai', op, tools=[self.big, self.small])
        self.addCleanup(d.deleteLater)
        return d

    def shown(self, d, name) -> str:
        return d.widgets[name].specialValueText()

    def test_the_value_of_the_tool_with_its_unit(self):
        d = self.open()
        dp = QLocale().decimalPoint()                                           # le séparateur des champs
        self.assertIs(d.current_tool(), self.big)
        self.assertEqual(self.shown(d, 'feed'), '750 mm/min')                  # round 1031 : la valeur seule
        self.assertEqual(self.shown(d, 'plunge'), '150 mm/min')
        self.assertEqual(self.shown(d, 'spindle'), '18000 ' + tr('tr/min'))
        self.assertEqual(self.shown(d, 'step_down'), f'0{dp}3 mm')
        self.assertIn('1 mm', self.shown(d, 'stepover_mm'))                     # 50 % de 2 mm
        self.assertIn('50 %', d.widgets['stepover_mm'].toolTip())             # round 1031 : dans la bulle
        self.assertEqual(d.widgets['feed'].text(), self.shown(d, 'feed'))      # à 0 : c'est ce qui se lit
        tools = d.widgets['tool_id']
        tools.setCurrentIndex(tools.findData(self.small.id))                   # un autre outil : elles suivent
        self.assertIs(d.current_tool(), self.small)
        self.assertIn(f'420{dp}5 mm/min', self.shown(d, 'feed'))
        self.assertIn('24000 ' + tr('tr/min'), self.shown(d, 'spindle'))
        self.assertIn(f'0{dp}4 mm', self.shown(d, 'stepover_mm'))
        self.check_typing(d)
        self.assertEqual(d.widgets['stepover_mm'].minimum(), 0.0)
        own = self.open(feed=999.0)                                             # une valeur à lui : gardée
        self.assertEqual(own.widgets['feed'].value(), 999.0)
        self.assertNotIn('outil', own.widgets['feed'].text())
        own.apply()
        self.assertEqual(own.obj.feed, 999.0)

    def test_no_more_celle_de_l_outil(self):
        d = self.open()
        for name, w in d.widgets.items():
            if hasattr(w, 'specialValueText'):
                self.assertNotIn('celle de l', w.specialValueText(), name)
        self.assertFalse([k for k, v in CP.LABELS.items() if 'celle de l\'outil' in v])
        self.assertEqual(CP.tool_value_tip('feed', None), tr('d’après l’outil, à choisir'))

    def check_typing(self, d):
        """Relecture : le texte de l'outil n'est pas réécrit à chaque frappe (Qt réécrirait le champ)."""
        dp = QLocale().decimalPoint()
        for name, keys, want in (('step_down', f'0{dp}15', 0.15), ('feed', '1234', 1234.0),
                                 ('stepover_mm', f'1{dp}25', 1.25)):
            w = d.widgets[name]
            w.lineEdit().selectAll()
            QTest.keyClicks(w, keys)
            self.assertAlmostEqual(w.value(), want, msg=name)

    def test_what_the_tool_does_not_give(self):
        """Relecture : outil conique ou boule, la distance entre passes n'est pas chiffrée (chaque stratégie la
        calcule) ; une valeur absente de l'outil est dite ; une distance négative d'une gamme reste."""
        vee = model.CamTool(name='V 30', kind='conique', diameter=3.175, angle=30.0, stepover=0.4, feed=0.0,
                            number=3)
        self.assertEqual(CP.tool_value_tip('stepover_mm', vee), tr('d’après l’outil et le parcours'))
        self.assertEqual(CP.tool_value_tip('feed', vee), tr('non réglée dans l’outil'))
        flat = model.CamTool(name='Cyl 3', diameter=3.0, stepover=0.0, number=4)
        self.assertEqual(CP.tool_value_tip('stepover_mm', flat), tr('d’après l’outil et le parcours'))
        d = self.open(stepover_mm=-1.0)
        self.assertEqual(d.widgets['stepover_mm'].value(), -1.0)
        d.apply()
        self.assertEqual(d.obj.stepover_mm, -1.0)


class Layout(unittest.TestCase):

    def setUp(self):
        forget()
        self.addCleanup(forget)

    def open(self):
        d = CP.FieldsDialog(None, 'essai', model.Operation(kind='contour'))
        self.addCleanup(d.deleteLater)
        return d

    def test_depths_above_leads_and_links(self):
        self.assertLess(CP.OP_LAYOUT[0].index('Profondeurs'), CP.OP_LAYOUT[0].index('Avancé'))   # round 1019
        cols = self.open().board.layout_now()
        self.assertEqual(cols[0][:4], ['Outil', 'Opération', 'Profondeurs', 'Avancé'])
        self.assertEqual(cols[1][:2], ['Vitesses', 'Entrées et liaisons'])

    def test_a_kept_layout_is_swapped_once(self):
        s = portable.settings()
        mine = [['Outil', 'Entrées et liaisons', 'Opération'], ['Vitesses', 'Laser', 'Profondeurs']]
        s.setValue(CP.CASES_KEYS[True], json.dumps(mine))
        cols = self.open().board.layout_now()
        self.assertEqual(cols[0][:3], ['Outil', 'Profondeurs', 'Opération'])   # leurs places échangées
        self.assertEqual(cols[1][:3], ['Vitesses', 'Laser', 'Entrées et liaisons'])
        d = self.open()                                                         # une fois : l'utilisateur décide
        d.board.move_case('Entrées et liaisons', 0, 0)
        self.assertEqual(self.open().board.layout_now()[0][0], 'Entrées et liaisons')
        forget()                                                                # déjà dans l'ordre : rien
        right = [['Outil', 'Profondeurs'], ['Vitesses', 'Entrées et liaisons']]
        s.setValue(CP.CASES_KEYS[True], json.dumps(right))
        self.assertFalse(CP.swap_kept_cases(s))
        self.assertEqual(json.loads(s.value(CP.CASES_KEYS[True])), right)
        s.setValue(CP.CASES_KEYS[True], 'pas du json')                          # illisible : pas d'erreur
        s.remove('fao/cases_operation2_profondeurs')
        self.assertFalse(CP.swap_kept_cases(s))


if __name__ == '__main__':
    unittest.main()
