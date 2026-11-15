"""Round 1007 : Défaire et Refaire montrent la liste des modifications (demande du 14/11) — quelques secondes,
par-dessus le plan de travail : l'état courant en avant, les modifications défaites en grisé ; un clic sur une ligne
revient à cet état ; option F10 › Général pour s'en passer."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1007.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import QPoint, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])

NAMES = ('Un', 'Deux', 'Trois')


class Base(unittest.TestCase):

    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.addCleanup(self.close)
        self.w.settings.remove('options/annulations_liste')
        for k, name in enumerate(NAMES):
            self.step(name, k)

    def close(self):
        self.w.modified = False
        self.w.close()

    def step(self, name, k):
        from vectordrive.core import geom
        from vectordrive.core.document import Shape
        self.w.push_undo(name)
        self.w.canvas.doc.add(Shape(path=geom.Path([geom.rect(20 * k, 0, 10, 10)])))

    def count(self) -> int:
        return sum(len(L.items) for L in self.w.canvas.doc.layers)

    def texts(self, hud) -> list:
        return [t.strip() for _k, t in hud.rows()]


class Timeline(Base):

    def test_the_steps_in_order_and_where_we_are(self):
        self.assertEqual(self.w.history_timeline(), (list(NAMES), 3))
        self.w.undo()
        self.assertEqual(self.w.history_timeline(), (list(NAMES), 2))   # la défaite reste dans la suite
        self.w.undo()
        self.w.redo()
        self.assertEqual(self.w.history_timeline(), (list(NAMES), 2))
        sig = self.w.history_signature()
        self.step('Quatre', 3)                                          # une autre modification : la suite repart de là
        self.assertEqual(self.w.history_timeline(), (['Un', 'Deux', 'Quatre'], 3))
        self.assertNotEqual(self.w.history_signature(), sig)

    def test_going_to_a_step(self):
        self.assertEqual(self.w.history_go(1), 1)
        self.assertEqual(self.count(), 1)
        self.assertEqual(self.w.history_go(0), 0)                       # l'état de départ
        self.assertEqual(self.count(), 0)
        self.assertEqual(self.w.history_go(3), 3)
        self.assertEqual(self.count(), 3)
        self.assertEqual(self.w.history_go(99), 3)                      # jamais au-delà
        self.assertEqual(self.w.history_go(-5), 0)
        self.assertEqual(self.w.history_go(2), 2)
        self.assertEqual(self.count(), 2)
        self.assertEqual(self.w.history_timeline(), (list(NAMES), 2))


class Hud(Base):

    def test_undo_and_redo_show_the_list(self):
        self.assertIsNone(getattr(self.w, '_history_hud', None))
        self.w.undo()                                                   # par le code : rien ne se montre
        self.w.redo()
        self.assertIsNone(getattr(self.w, '_history_hud', None))
        self.w.A['undo'].trigger()
        hud = self.w._history_hud
        self.assertFalse(hud.isHidden())
        self.assertIs(hud.parentWidget(), self.w.stage)                 # sur le plan de travail montré, 2D ou 3D
        self.assertEqual(hud.focusPolicy(), Qt.FocusPolicy.NoFocus)     # le clavier reste au dessin
        self.assertEqual(hud.list.focusPolicy(), Qt.FocusPolicy.NoFocus)
        self.assertTrue(hud.testAttribute(Qt.WidgetAttribute.WA_NoMousePropagation))
        self.assertEqual(hud.cursor().shape(), Qt.CursorShape.ArrowCursor)
        self.assertTrue(hud.timer.isActive())
        self.assertEqual(self.count(), 2)
        self.assertEqual(self.texts(hud), ['Début de l’historique', '1. Un', '▶ 2. Deux', '3. Trois'])
        self.assertEqual(hud.current, 2)
        self.assertTrue(hud.list.item(2).font().bold())
        self.assertFalse(hud.list.item(3).font().bold())
        self.assertNotEqual(hud.list.item(3).foreground().color(), hud.list.item(1).foreground().color())
        self.w.A['undo'].trigger()
        self.assertEqual(self.texts(hud)[1], '▶ 1. Un')
        self.w.A['redo'].trigger()
        self.w.A['redo'].trigger()
        self.assertEqual(self.texts(hud)[3], '▶ 3. Trois')
        self.assertEqual(self.count(), 3)
        self.w.A['redo'].trigger()                                      # plus rien à refaire : la liste le montre
        self.assertEqual(hud.current, 3)

    def test_a_click_goes_to_the_step(self):
        hud = self.w.show_history()
        self.assertEqual(self.texts(hud)[-1], '▶ 3. Trois')
        hud.list.itemClicked.emit(hud.list.item(0))                     # « Début de l'historique »
        self.assertEqual(self.count(), 0)
        self.assertEqual(self.texts(hud), ['▶ Début de l’historique', '1. Un', '2. Deux', '3. Trois'])
        hud.list.itemClicked.emit(hud.list.item(2))
        self.assertEqual(self.count(), 2)
        self.assertEqual(hud.current, 2)
        hud.list.itemClicked.emit(hud.list.item(2))                     # déjà là : rien ne bouge
        self.assertEqual(self.count(), 2)
        self.assertEqual(self.w.history_timeline(), (list(NAMES), 2))

    def test_a_real_click_and_nothing_goes_to_the_drawing(self):
        self.w.show()
        app.processEvents()
        hud = self.w.show_history()
        app.processEvents()
        self.assertTrue(hud.isVisible())
        self.assertTrue(self.w.stage.rect().contains(hud.geometry()))   # dans le plan de travail
        with mock.patch.object(self.w.canvas, 'mousePressEvent') as press, \
                mock.patch.object(self.w.canvas, 'mouseReleaseEvent') as release:
            QTest.mouseClick(hud.list.viewport(), Qt.MouseButton.LeftButton,
                             pos=hud.list.visualItemRect(hud.list.item(1)).center())
            QTest.mouseClick(hud.title, Qt.MouseButton.LeftButton)      # sur le titre, sur le cadre : rien au dessin
            QTest.mouseClick(hud, Qt.MouseButton.LeftButton, pos=QPoint(2, 2))
        self.assertEqual(self.count(), 1)                               # la ligne « 1. Un »
        self.assertEqual(hud.current, 1)
        press.assert_not_called()
        release.assert_not_called()
        self.assertIsNot(app.focusWidget(), hud.list)

    def test_the_list_on_screen_follows_the_stacks(self):
        hud = self.w.show_history()
        self.step('Quatre', 3)                                          # une autre modification : la liste la montre
        self.assertEqual(self.texts(hud)[-1], '▶ 4. Quatre')
        self.w.undo()                                                   # un pas défait par une autre commande
        self.assertEqual(hud.current, 3)
        self.w.clear_history()
        self.assertEqual(self.texts(hud), ['▶ Début de l’historique'])
        self.step('Cinq', 4)
        self.w.new_document()                                           # un autre dessin : elle s'efface
        self.assertTrue(hud.isHidden())
        self.assertEqual(self.w.history_timeline(), ([], 0))
        self.w.switch_tab(0)
        self.w.A['undo'].trigger()                                      # … et revient avec les pas du premier
        self.assertEqual(self.texts(hud), ['▶ Début de l’historique', '1. Cinq'])

    def test_a_list_out_of_date_is_redone_not_followed(self):
        hud = self.w.show_history()
        hud.hide()                                                      # effacée : elle ne suit plus
        self.step('Quatre', 3)
        self.assertFalse(hud.go(0))                                     # périmée : refaite, rien n'est défait
        self.assertEqual(self.count(), 4)
        self.assertEqual(self.texts(hud)[-1], '▶ 4. Quatre')
        self.assertTrue(hud.go(0))
        self.assertEqual(self.count(), 0)
        # une saisie de texte en cours se termine au clic : son pas compte avant d'aller à l'étape
        self.w.history_go(4)
        hud.refresh()
        with mock.patch.object(self.w, 'finish_typing', side_effect=lambda: self.step('Texte', 5)) as done:
            self.assertFalse(hud.go(1))
        done.assert_called()
        self.assertEqual(self.count(), 5)
        self.assertEqual(self.texts(hud)[-1], '▶ 5. Texte')

    def test_a_small_work_area(self):
        from vectordrive.ui import history_hud as H
        for k in range(3, 30):
            self.step(f'Pas {k + 1}', k)
        self.w.stage.setFixedSize(170, 130)
        hud = self.w.show_history()
        self.assertEqual(hud.list.count(), H.MIN_ROWS)                  # peu de place : peu de lignes, la courante dedans
        self.assertEqual(hud.rows()[-1][0], 30)
        self.assertLessEqual(hud.width(), 170 - 2 * H.MARGIN)

    def test_it_goes_away_unless_the_mouse_is_on_it(self):
        from vectordrive.ui import history_hud as H
        hud = self.w.show_history()
        self.assertEqual(hud.timer.interval(), H.SHOWN_MS)
        self.assertTrue(hud.timer.isSingleShot())
        with mock.patch.object(hud, 'underMouse', return_value=True):
            hud.timer.stop()
            hud._timeout()
            self.assertFalse(hud.isHidden())
            self.assertTrue(hud.timer.isActive())
        hud._timeout()
        self.assertTrue(hud.isHidden())
        self.w.A['undo'].trigger()                                      # elle revient au pas suivant
        self.assertFalse(hud.isHidden())

    def test_the_option_turns_it_off(self):
        from vectordrive.ui import options as O
        self.assertTrue(O.value(self.w.settings, 'options/annulations_liste'))
        self.w.settings.setValue('options/annulations_liste', False)
        self.w.A['undo'].trigger()
        self.assertEqual(self.count(), 2)                               # défait, sans liste
        self.assertIsNone(getattr(self.w, '_history_hud', None))
        self.assertIsNone(self.w.show_history())
        self.assertIsNotNone(self.w.show_history(force=True))

    def test_a_long_history_shows_the_steps_around(self):
        from vectordrive.ui import history_hud as H
        for k in range(3, 40):
            self.step(f'Pas {k + 1}', k)
        hud = self.w.show_history()
        self.assertEqual(hud.list.count(), H.ROWS)
        self.assertEqual(hud.rows()[-1][0], 40)                         # à la fin : les dernières
        self.w.history_go(20)
        hud.refresh()
        ranks = [k for k, _t in hud.rows()]
        self.assertEqual(len(ranks), H.ROWS)
        self.assertIn(20, ranks)
        self.assertGreater(ranks.index(20), 2)                          # des pas avant, des pas après
        self.assertLess(ranks.index(20), H.ROWS - 3)
        self.w.history_go(0)
        hud.refresh()
        self.assertEqual(hud.rows()[0][0], 0)
        self.assertLessEqual(hud.width(), H.WIDTH)


if __name__ == '__main__':
    unittest.main()
