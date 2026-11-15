"""Round 997 : FAO, cases du formulaire, retour de l'atelier — « groupes de form agencés sous forme de cases que user
peut agencer à sa guise avec mémoire disposition ». Les sections des formulaires d'opération et d'outil se glissent par
leur titre (autre place, autre colonne) ; clic droit : nombre de colonnes, disposition d'origine ; gardé."""
import json
import os
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import QMimeData, QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QDropEvent  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from vectordrive import portable  # noqa: E402
from vectordrive.cam import model  # noqa: E402
from vectordrive.ui import cam_panel as CP  # noqa: E402

app = QApplication.instance() or QApplication([])
KEY = 'fao/cases_operation2'                                    # round 1004 : disposition d'origine neuve, réglage neuf


def forget():
    s = portable.settings()
    for k in (KEY, 'fao/cases_outil'):
        s.remove(k)
    s.sync()


def dialog(kind='contour'):
    return CP.FieldsDialog(None, 'essai', model.Operation(kind=kind))


class Cases(unittest.TestCase):

    def setUp(self):
        forget()
        self.addCleanup(forget)

    def open(self, kind='contour'):
        d = dialog(kind)
        self.addCleanup(d.deleteLater)
        return d

    def test_default_two_columns_as_before(self):
        d = self.open()
        cols = d.board.layout_now()                                       # avant : pas de cases
        self.assertEqual(len(cols), 2)
        order = [k for c in cols for k in c]
        self.assertEqual(order[:3], ['Outil', 'Opération', 'Profondeurs'])       # round 1019 : l'ordre demandé
        self.assertEqual(len(order), len(d.board.tiles))                  # (les colonnes : celles du formulaire)

    def test_moved_case_kept_for_next_time(self):
        d = self.open()
        d.board.move_case('Vitesses', 0, 0)
        self.assertEqual(d.board.layout_now()[0][0], 'Vitesses')
        saved = json.loads(portable.settings().value(KEY))
        self.assertEqual(saved[0][0], 'Vitesses')
        d2 = self.open('poche')                                           # une autre opération : même disposition
        self.assertEqual(d2.board.layout_now()[0][0], 'Vitesses')
        self.assertIs(d2.board.tiles['Vitesses'].parentWidget(), d2.board.columns[0])

    def test_dropped_on_another_column(self):
        d = self.open()
        d.resize(1000, 700)
        d.show()
        app.processEvents()
        col = d.board.columns[1]
        md = QMimeData()
        md.setData('application/x-vectordrive-case', 'Opération'.encode('utf-8'))
        ev = QDropEvent(QPointF(10, 1), Qt.DropAction.MoveAction, md, Qt.MouseButton.LeftButton,
                        Qt.KeyboardModifier.NoModifier)
        col.dropEvent(ev)
        cols = d.board.layout_now()
        shown = [k for k in cols[1] if not d.board.tiles[k].isHidden()]  # une section masquée peut rester devant
        self.assertEqual(shown[0], 'Opération')
        self.assertNotIn('Opération', cols[0])
        d.close()

    def test_columns_and_reset(self):
        d = self.open()
        d.board.set_columns(3)
        self.assertEqual(len(d.board.layout_now()), 3)
        self.assertEqual(len(self.open().board.layout_now()), 3)          # gardé
        d.board.reset()
        self.assertEqual(len(d.board.layout_now()), 2)
        self.assertFalse(portable.settings().contains(KEY))

    def test_hidden_section_stays_hidden_after_a_move(self):
        d = self.open('contour')
        d.show()
        app.processEvents()
        laser = d.board.tiles['Laser']
        self.assertTrue(laser.isHidden())                                 # pas de champ laser pour un contour
        d.board.move_case('Laser', 0, 0)
        self.assertTrue(laser.isHidden())
        self.assertFalse(d.board.tiles['Opération'].isHidden())
        d.close()

    def test_damaged_or_old_layout(self):
        s = portable.settings()
        s.setValue(KEY, 'pas du json')
        self.assertEqual(len(self.open().board.layout_now()), 2)
        s.setValue(KEY, json.dumps([['Vitesses', 'Section disparue'], ['Opération', 'Vitesses']]))
        cols = self.open().board.layout_now()
        self.assertEqual(cols[0][0], 'Vitesses')                          # une seule fois, à sa première place
        self.assertEqual([k for c in cols for k in c].count('Vitesses'), 1)
        self.assertNotIn('Section disparue', [k for c in cols for k in c])
        self.assertIn('Profondeurs', [k for c in cols for k in c])        # oubliée de la disposition : ajoutée

    def test_title_drag_starts(self):
        d = self.open()
        d.show()
        app.processEvents()
        g = d.board.tiles['Vitesses']
        with mock.patch.object(type(d.board), 'drag') as drag:
            QTest.mousePress(g, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(30, 6))
            QTest.mouseMove(g, QPoint(80, 40))
            QTest.mouseRelease(g, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(80, 40))
        drag.assert_called_once()
        d.close()

    def test_tool_form_has_its_own(self):
        d = CP.FieldsDialog(None, 'outil', model.CamTool())
        self.addCleanup(d.deleteLater)
        d.board.move_case('Coupe', 0, 0)
        self.assertEqual(json.loads(portable.settings().value('fao/cases_outil'))[0][0], 'Coupe')
        self.assertFalse(portable.settings().contains(KEY))

    def test_down_in_the_same_column(self):
        d = self.open()
        d.board.move_case('Outil', 0, 2)                                  # lâchée entre la 2e et la 3e
        self.assertEqual(d.board.layout_now()[0][:2], ['Opération', 'Outil'])
        d.board.move(QPoint(0, 0))                                         # QWidget.move n'est plus masqué

    def test_no_empty_column(self):
        d = CP.FieldsDialog(None, 'outil', model.CamTool())
        self.addCleanup(d.deleteLater)
        n = len(d.board.tiles)
        for cols in (3, 4):
            d.board.set_columns(cols)
            sizes = [len(c) for c in d.board.layout_now()]
            self.assertEqual(sum(sizes), n)
            if n >= cols:
                self.assertNotIn(0, sizes, sizes)                          # avant : 5 cases en 4 → [2, 2, 1, 0]
            self.assertLessEqual(max(sizes) - min(sizes), 1)

    def test_hint_on_the_title_only(self):
        from PySide6.QtCore import QEvent
        from PySide6.QtGui import QHelpEvent
        from PySide6.QtWidgets import QToolTip
        d = self.open()
        d.show()
        app.processEvents()
        g = d.board.tiles['Vitesses']
        self.assertEqual(g.toolTip(), '')                                  # avant : sur tous les champs de la case
        QApplication.sendEvent(g, QHelpEvent(QEvent.Type.ToolTip, QPoint(30, 4), g.mapToGlobal(QPoint(30, 4))))
        self.assertIn('Glissez', QToolTip.text())
        QToolTip.hideText()
        d.close()

    def test_sections_absent_this_time_keep_their_place(self):
        portable.settings().setValue(KEY, json.dumps([['Section de plugin', 'Opération'], ['Vitesses']]))
        d = self.open()
        d.board.move_case('Vitesses', 0, 1)
        saved = json.loads(portable.settings().value(KEY))
        self.assertEqual(saved[0][0], 'Section de plugin')                 # avant : oubliée au premier geste
        self.assertIn('Vitesses', saved[0])


if __name__ == '__main__':
    unittest.main()
