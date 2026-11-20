"""Round 1019 : demande du 14/11, 19 h 45 — « Form parcours : Tous les groupes sont pliables/dépliables
réarrangeables user avec mémoire du dernier choix, par défaut profondeur au dessus de particulier (renommé en Avancé) ;
Nature opération ne doit pas être dans le form mais est définie par le type de parcours choisi »."""
import json
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1019.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import QPoint, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])

from vectordrive import portable  # noqa: E402
from vectordrive.cam import model  # noqa: E402
from vectordrive.i18n import tr  # noqa: E402
from vectordrive.ui import cam_panel as CP  # noqa: E402

KEY = CP.CASES_KEYS[True]


def forget():
    s = portable.settings()
    for k in (KEY, KEY + '_pliees', 'fao/cases_outil', 'fao/cases_outil_pliees'):
        s.remove(k)


class Form(unittest.TestCase):

    def setUp(self):
        forget()
        self.addCleanup(forget)

    def open(self, op=None, **kw):
        d = CP.FieldsDialog(None, 'essai', op or model.Operation(kind='contour'), **kw)
        self.addCleanup(d.deleteLater)
        return d

    def test_click_on_title_folds_and_is_kept(self):
        d = self.open()
        d.show()
        app.processEvents()
        g = d.board.tiles['Profondeurs']
        full = g.height()
        QTest.mouseClick(g, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(30, 6))
        app.processEvents()
        self.assertTrue(g.property('vd_folded'))                              # avant : rien au clic
        self.assertIn('Profondeurs', d.board.folded)
        self.assertTrue(g.title().startswith('▸'))
        self.assertLess(g.height(), full)                                     # seul le titre reste
        self.assertEqual(json.loads(portable.settings().value(KEY + '_pliees')), ['Profondeurs'])
        d.board._focus_moved(None, d.widgets['depth'])                        # le focus y entre : dépliée
        self.assertFalse(g.property('vd_folded'))
        self.assertEqual(json.loads(portable.settings().value(KEY + '_pliees')), ['Profondeurs'])   # pour la suite
        d.close()
        d2 = self.open()                                                      # gardée pour la fois suivante
        self.assertTrue(d2.board.tiles['Profondeurs'].property('vd_folded'))
        d2.board.toggle('Profondeurs')                                        # dépliée
        self.assertEqual(d2.board.tiles['Profondeurs'].title(), tr('Profondeurs'))
        self.assertEqual(json.loads(portable.settings().value(KEY + '_pliees')), [])
        d2.board.fold_all(True)
        self.assertEqual(d2.board.folded, set(d2.board.tiles))
        d2.board.reset()                                                      # disposition d'origine : tout déplié
        self.assertFalse(d2.board.folded)
        self.assertFalse(portable.settings().contains(KEY + '_pliees'))

    def test_drag_does_not_fold(self):
        from unittest import mock
        d = self.open()
        d.show()
        app.processEvents()
        g = d.board.tiles['Vitesses']
        with mock.patch.object(type(d.board), 'drag'):
            QTest.mousePress(g, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(30, 6))
            QTest.mouseMove(g, QPoint(80, 40))
            QTest.mouseRelease(g, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(80, 40))
        self.assertFalse(d.board.folded)
        QTest.mouseClick(g, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(30, 60))
        self.assertFalse(d.board.folded)                                      # un clic dans la case : rien
        d.close()

    def test_advanced_under_depths_and_kept_layout_renamed(self):
        d = self.open()
        cols = d.board.layout_now()
        self.assertIn('Avancé', d.board.tiles)                               # avant : « Particulier »
        self.assertNotIn('Particulier', d.board.tiles)
        self.assertEqual(cols[0][:4], ['Outil', 'Opération', 'Profondeurs', 'Avancé'])
        self.assertEqual(cols[1][:2], ['Vitesses', 'Entrées et liaisons'])
        self.assertTrue(d.board.tiles['Avancé'].isAncestorOf(d.widgets['peck']))
        s = portable.settings()
        s.setValue('fao/cases_operation2_profondeurs', True)                  # déjà échangée (round 1010)
        s.setValue(KEY, json.dumps([['Particulier', 'Outil'], ['Vitesses']]))
        s.setValue(KEY + '_pliees', json.dumps(['Particulier']))
        d = self.open()
        self.assertEqual(d.board.layout_now()[0][:2], ['Avancé', 'Outil'])    # à sa place, sous son nouveau nom
        self.assertTrue(d.board.tiles['Avancé'].property('vd_folded'))
        self.assertFalse(CP.rename_kept_cases(s))                             # une fois

    def test_kind_shown_not_chosen(self):
        d = self.open(model.Operation(kind='poche'))
        self.assertTrue(d.rows['kind'][1].isHidden())                         # avant : la liste des natures
        lab = d.rows['kind_label'][1]
        self.assertTrue(lab.isHidden())                                       # 1120 : plus dans le formulaire
        self.assertEqual(lab.text(), tr(model.op_kinds()['poche']))
        d.widgets['kind'].setCurrentIndex(d.widgets['kind'].findData('contour'))
        self.assertEqual(lab.text(), tr(model.op_kinds()['contour']))
        cut = self.open(model.Operation(kind='contour'), preset='decoupe')   # parcours de la palette : son nom
        self.assertEqual(cut.rows['kind_label'][1].text(), tr(CP.presets()['decoupe'][0]))
        free = self.open(kind_choice=True)                                    # « Nouvelle opération » : la liste
        self.assertFalse(free.rows['kind'][1].isHidden())
        self.assertTrue(free.rows['kind_label'][1].isHidden())

    def test_tool_form_folds_too(self):
        d = CP.FieldsDialog(None, 'outil', model.CamTool())
        self.addCleanup(d.deleteLater)
        d.board.toggle('Coupe')
        self.assertEqual(json.loads(portable.settings().value('fao/cases_outil_pliees')), ['Coupe'])


if __name__ == '__main__':
    unittest.main()
