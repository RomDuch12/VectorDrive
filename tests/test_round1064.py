"""Round 1064 : demande du 16/11, 23 h 25 — « lorsque click droit sur colonne d ou g, c'est le même menu donc pas besoin
du titre qui mentionne d ou g. Un click ailleurs ferme ce menu: Fenetre parcours_form titre fenetre : "parcours
[type_parcours] - [commentaire si préenregistré]"; plongée angulaire limite à 89°; »."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1064.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QKeyEvent, QMouseEvent  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel  # noqa: E402

app = QApplication.instance() or QApplication([])

from vectordrive.cam import model  # noqa: E402
from vectordrive.cam import strategies as S  # noqa: E402
from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Shape  # noqa: E402
from vectordrive.i18n import tr  # noqa: E402
from vectordrive.ui import cam_panel as CP  # noqa: E402


def forget():
    from vectordrive import portable
    s = portable.settings()
    s.remove('panneaux_colonnes')
    s.sync()


class Window(unittest.TestCase):

    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        forget()
        self.addCleanup(forget)
        self.w = MainWindow()
        self.w.show()
        app.processEvents()
        self.addCleanup(self.clean)

    def clean(self):
        p = self.w.cam_panel
        self.w.settings.remove(p.LAST_KEY)
        self.w.modified = False
        self.w.close()
        self.w.deleteLater()
        app.processEvents()


class ColumnWindow(Window):

    def press(self, target, at: QPoint):
        ev = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(2, 2), QPointF(at), Qt.MouseButton.LeftButton,
                         Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(target, ev)

    def test_same_window_for_both_columns_without_a_title(self):
        for side in ('gauche', 'droite'):
            p = self.w.column_panel(side)
            texts = ' '.join(lab.text() for lab in p.findChildren(QLabel))
            self.assertNotIn(tr('Colonne de gauche'), texts, side)
            self.assertNotIn(tr('Colonne de droite'), texts, side)
            self.assertTrue(p.choices)                                        # le tableau des panneaux, lui, y est
            p.close()

    def test_a_click_elsewhere_closes_it(self):
        p = self.w.column_panel('droite')
        g = p.frameGeometry()
        self.press(p.body, g.center())                                       # dans la fenêtre : elle reste
        self.assertIsNotNone(self.w.columns.panel('droite'))
        self.press(self.w.statusBar(), QPoint(g.left() - 30, g.top() + 5))  # ailleurs dans VectorDrive : fermée
        self.assertIsNone(self.w.columns.panel('droite'))

    def test_another_application_or_escape_closes_it(self):
        p = self.w.column_panel('gauche')
        QApplication.sendEvent(app, QEvent(QEvent.Type.ApplicationDeactivate))   # un clic dans une autre application
        self.assertIsNone(self.w.columns.panel('gauche'))
        p = self.w.column_panel('gauche')
        over = QKeyEvent(QEvent.Type.ShortcutOverride, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
        over.ignore()
        QApplication.sendEvent(self.w.canvas, over)                         # Échap n'est pas un raccourci de la fenêtre
        self.assertTrue(over.isAccepted())
        esc = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(self.w.canvas, esc)                          # le clavier va au dessin : fermée quand même
        self.assertIsNone(self.w.columns.panel('gauche'))
        # fermée : elle ne regarde plus les clics (une fenêtre rouverte ensuite ne se ferme pas pour rien)
        p2 = self.w.column_panel('gauche')
        self.press(p2.body, p2.frameGeometry().center())
        self.assertIsNotNone(self.w.columns.panel('gauche'))

    def test_a_second_right_click_on_its_button_closes_it(self):
        b = self.w.ribbon.column_buttons[1]
        self.w.column_panel('droite', b)
        at = b.mapToGlobal(b.rect().center())
        self.press(b, at)                                                    # l'appui sur le bouton : fermée
        self.assertIsNone(self.w.columns.panel('droite'))
        self.assertIsNone(self.w.column_panel('droite', b))                  # le menu qui suit ne la rouvre pas
        self.assertIsNotNone(self.w.column_panel('droite', b))               # un clic droit de plus : rouverte


class ToolpathForm(Window):

    def select_circle(self):
        it = Shape(path=geom.Path([geom.circle((10.0, 10.0), 2.0)]), tool=0)
        self.w.canvas.doc.add(it)
        self.w.canvas.invalidate()
        self.w.canvas.select([it])

    def titles(self, key, **kw):
        seen = []

        def fake(dlg):
            seen.append(dlg.windowTitle())
            box = dlg.template_box
            if box is not None and box.currentData():
                box.setCurrentIndex(0)                                       # « réglages ci-dessous »
                seen.append(dlg.windowTitle())
            return 0
        self.select_circle()
        with mock.patch.object(CP.FieldsDialog, 'exec', fake):
            self.w.cam_panel.new_operation(key, **kw)
        return seen

    def test_title_names_the_toolpath_type(self):
        self.assertEqual(self.titles('decoupe'), [tr('Parcours {0}').format(tr('Découpe'))])

    def test_title_carries_the_comment_of_a_saved_toolpath(self):
        from vectordrive.cam import templates as TPL
        op = model.Operation(kind='contour', name='Détourage', side='exterieur', depth=1.0)
        tpl = TPL.single(op, None, 'Détourage alu', 'decoupe', description='Alu 3 mm, deux passes\nsuite')
        with mock.patch.object(TPL, 'all_templates', return_value={'Détourage alu': ('utilisateur', tpl)}):
            seen = self.titles('decoupe', template='Détourage alu')
        base = tr('Parcours {0}').format(tr('Découpe'))
        self.assertEqual(seen, [base + ' - Alu 3 mm, deux passes', base])  # modèle quitté : sans commentaire

    def test_the_title_follows_the_strategy_chosen_in_the_list(self):
        self.assertTrue(hasattr(CP, 'toolpath_title'), 'avant : « Nouvelle opération »')
        seen = []

        def fake(dlg):
            box = dlg.widgets['kind']
            seen.append(dlg.windowTitle())
            box.setCurrentIndex(box.findData('poche'))
            seen.append(dlg.windowTitle())
            return 0
        tool = model.CamTool(name='F2', kind='fraise', diameter=2.0)
        panel = self.w.cam_panel
        with mock.patch.object(CP.FieldsDialog, 'exec', fake),                 mock.patch.object(type(panel), 'pick_library', lambda _self: [tool]):   # un outil dans Mes outils
            panel.add_op()
        kinds = model.op_kinds()
        self.assertEqual(seen[1], tr('Parcours {0}').format(tr(kinds['poche'])))
        self.assertTrue(seen[0].startswith(tr('Parcours {0}').format('')))

    def test_typeedit_descriptions_are_not_comments(self):
        self.assertTrue(hasattr(CP, 'template_note'), 'avant : sans commentaire')
        from vectordrive.cam import templates as TPL
        tpl = TPL.single(model.Operation(kind='poche'), None, 'TE / Gravure V30', 'gravure',
                         description='TypeEdit : Gravure V30 (CP_Engraving, TE)')
        tpl['dossier'] = 'TE'
        with mock.patch.object(TPL, 'all_templates', return_value={'TE / Gravure V30': ('plugin', tpl)}):
            self.assertEqual(CP.template_note('TE / Gravure V30'), 'Gravure V30')

    def test_without_description_the_template_name_is_the_comment(self):
        self.assertTrue(hasattr(CP, 'toolpath_title'), 'avant : « Nouveau parcours : … », sans le modèle')
        self.assertEqual(CP.toolpath_title('contour', 'decoupe', CP.template_note('')),
                         tr('Parcours {0}').format(tr('Découpe')))
        from vectordrive.cam import templates as TPL
        tpl = TPL.single(model.Operation(kind='contour'), None, 'Atelier / Inox 2', 'decoupe')
        tpl['dossier'] = 'Atelier'
        with mock.patch.object(TPL, 'all_templates', return_value={'Atelier / Inox 2': ('utilisateur', tpl)}):
            self.assertEqual(CP.template_note('Atelier / Inox 2'), 'Inox 2')


class RampAngle(unittest.TestCase):

    def test_up_to_89_degrees(self):
        self.assertEqual(S.ramp_angle_of(model.Operation(ramp_angle=80)), 80)   # n'est plus ramené à 45
        self.assertEqual(S.ramp_angle_of(model.Operation(ramp_angle=89)), 89)
        self.assertEqual(S.ramp_angle_of(model.Operation(ramp_angle=150)), 89)
        self.assertEqual(S.ramp_angle_of(model.Operation()), S.RAMP_ANGLE)

    def test_the_field_stops_at_89(self):
        op = model.Operation(kind='contour', ramp=True, ramp_angle=150.0)
        dlg = CP.FieldsDialog(None, 'essai', op, None, [])
        self.addCleanup(dlg.deleteLater)
        spin = dlg.widgets['ramp_angle']
        self.assertEqual(spin.maximum(), 89.0)
        self.assertEqual(spin.value(), 89.0)
        spin.setValue(60.0)
        dlg.apply()
        self.assertEqual(op.ramp_angle, 60.0)

    def test_a_steep_ramp_still_reaches_the_depth(self):
        em = S.Emitter(model.Operation(), model.CamTool())
        S.cut_chain(em, [(0, 0), (20, 0), (20, 10), (0, 10)], True, [-1.0], ramp=True,
                    ramp_angle=S.ramp_angle_of(model.Operation(ramp_angle=89)))
        self.assertAlmostEqual(min(m.z for m in em.moves), -1.0)


if __name__ == '__main__':
    unittest.main()
