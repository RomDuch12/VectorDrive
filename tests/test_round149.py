"""Round 149 : formulaire d'opération et d'outil en sections et en
colonnes, illustration, champs propres à une stratégie masqués pour les
autres, taille ajustée à l'écran."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))


class TestForms(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_operation_sections_and_visibility(self):
        from PySide6.QtWidgets import QGroupBox
        from vectordrive.cam import model
        from vectordrive.ui.cam_panel import FieldsDialog, OpIllustration
        o = model.Operation(kind='poche', depth=0.6, finish=True, stock=0.1)
        d = FieldsDialog(None, 'Opération', o)
        d.show()
        titles = [g.title() for g in d.findChildren(QGroupBox)]
        for t in ('Opération', 'Où usiner', 'Profondeurs', 'Entrées et liaisons', 'Vitesses', 'Avancé'):
            self.assertIn(t, titles)
        self.assertIsInstance(d.illustration, OpIllustration)
        self.assertFalse(d.widgets['peck'].isVisible())                    # perçage seulement
        self.assertTrue(d.widgets['finish_skip_frame'].isVisible())
        d.widgets['kind'].setCurrentIndex(d.widgets['kind'].findData('percage'))
        self.assertTrue(d.widgets['peck'].isVisible())
        self.assertFalse(d.widgets['finish'].isVisible())
        self.assertFalse(d.widgets['tabs'].isVisible())
        d.widgets['kind'].setCurrentIndex(d.widgets['kind'].findData('contour'))
        self.assertTrue(d.widgets['tabs'].isVisible())
        self.assertTrue(d.widgets['side'].isVisible())
        d.widgets['depth'].setValue(1.5)
        d.illustration.grab()                                              # le schéma se dessine
        d.apply()
        self.assertEqual((o.kind, o.depth), ('contour', 1.5))
        d.close()

    def test_unknown_kind_shows_all(self):
        from vectordrive.cam import model
        from vectordrive.ui.cam_panel import FieldsDialog
        o = model.Operation(kind='strategie_de_plugin')
        d = FieldsDialog(None, 'Opération', o)
        d.show()
        self.assertTrue(d.widgets['peck'].isVisible())
        self.assertTrue(d.widgets['tabs'].isVisible())
        d.close()

    def test_tool_form_with_silhouette(self):
        from PySide6.QtWidgets import QGroupBox
        from vectordrive.cam import model
        from vectordrive.ui.cam_panel import FieldsDialog
        t = model.CamTool(name='Conique', kind='conique', diameter=3.175, angle=30, tip=0.2)
        d = FieldsDialog(None, 'Outil', t)
        titles = [g.title() for g in d.findChildren(QGroupBox)]
        for x in ('Outil', 'Géométrie', 'Coupe'):
            self.assertIn(x, titles)
        self.assertFalse(d.illustration.pixmap().isNull())
        d.widgets['diameter'].setValue(6)
        d.apply()
        self.assertEqual(t.diameter, 6)
        d.close()

    def test_fits_screen(self):
        from vectordrive.cam import model
        from vectordrive.ui.cam_panel import FieldsDialog
        d = FieldsDialog(None, 'Opération', model.Operation())
        avail = d.screen().availableGeometry()
        self.assertLessEqual(d.width(), avail.width())
        self.assertLessEqual(d.height(), avail.height())
        d.close()


if __name__ == '__main__':
    unittest.main()
