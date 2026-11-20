"""Round 1120 : le formulaire d'une opération — le nom en tête, sur la ligne du modèle (le nom de la liste des
parcours calculés) ; « Type de parcours » et la case Active n'y sont plus (demande du 20/11, 16 h 08)."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1120.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication, QComboBox  # noqa: E402

app = QApplication.instance() or QApplication([])

from vectordrive.cam import model  # noqa: E402
from vectordrive.ui import cam_panel as CP  # noqa: E402


class Form(unittest.TestCase):

    def open(self, op=None, **kw):
        d = CP.FieldsDialog(None, 'essai', op or model.Operation(kind='contour', name='Contour 1'), **kw)
        self.addCleanup(d.deleteLater)
        return d

    def head_widgets(self, d):
        lay = d.head
        return [lay.itemAt(i).widget() for i in range(lay.count()) if lay.itemAt(i).widget() is not None]

    def test_name_first_on_the_template_line(self):
        d = self.open(preset='decoupe')
        ws = self.head_widgets(d)
        self.assertIs(ws[1], d.widgets['name'], 'en tête : « Nom » puis son champ')
        self.assertEqual(ws[0].text(), 'Nom')
        self.assertIn(d.template_box, ws, 'sur la même ligne que le modèle')
        self.assertLess(ws.index(d.widgets['name']), ws.index(d.template_box))
        self.assertFalse(d.board.tiles['Opération'].isAncestorOf(d.widgets['name']))
        self.assertIn('liste des parcours calculés', d.widgets['name'].toolTip())

    def test_name_first_without_template(self):
        d = self.open()                                  # une opération ouverte de la liste : pas de modèle
        self.assertIsNone(d.template_box)
        self.assertIs(self.head_widgets(d)[1], d.widgets['name'])

    def test_name_goes_to_the_operation_and_its_toolpaths(self):
        op = model.Operation(kind='contour', name='Contour 1')
        d = self.open(op)
        d.widgets['name'].setText('Détourage plaque')
        d.apply()
        self.assertEqual(op.name, 'Détourage plaque')

    def test_kind_and_active_gone(self):
        d = self.open(preset='decoupe')
        d.show()
        app.processEvents()
        self.assertFalse(d.rows['kind_label'][1].isVisible(), '« Type de parcours » : plus dans le formulaire')
        self.assertFalse(d.rows['kind'][1].isVisible())
        self.assertNotIn('enabled', d.rows)
        self.assertFalse(d.widgets['enabled'].isVisible(), 'la case Active : dans la liste des opérations')
        d.close()

    def test_active_kept_on_apply(self):
        for state in (True, False):
            op = model.Operation(kind='contour', enabled=state)
            d = self.open(op)
            d.apply()
            self.assertIs(op.enabled, state, 'la valeur ne change pas en passant par le formulaire')

    def test_free_kind_choice_keeps_its_list(self):
        d = self.open(kind_choice=True)                  # « Nouvelle opération » : le type reste à choisir
        d.show()
        app.processEvents()
        self.assertIsInstance(d.rows['kind'][1], QComboBox)
        self.assertTrue(d.rows['kind'][1].isVisible())
        d.close()

    def test_instruction_keeps_name_in_head(self):
        d = self.open(model.Operation(kind='instruction', name='Pause'))
        d.show()
        app.processEvents()
        self.assertTrue(d.widgets['name'].isVisible())
        d.close()

    def test_tool_form_unchanged(self):
        d = CP.FieldsDialog(None, 'outil', model.CamTool())
        self.addCleanup(d.deleteLater)
        self.assertIsNone(d.head)


if __name__ == '__main__':
    unittest.main()
