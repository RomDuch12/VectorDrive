"""Round 994 : la liste des polices, retour de l'atelier — « Liste polices prend la hauteur de la fenetre avec filtres et
recherche […], favories (étoile) ». La liste dépliée d'une liste de polices va jusqu'au bas de la fenêtre ; une
recherche (plusieurs mots, sans casse ni accents), des filtres, une étoile qui marque une favorite (gardée, en tête de
la liste) ; le choix, à la souris ou au clavier, fait comme un choix dans la liste d'avant."""
import os
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QMouseEvent, QPalette  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QLineEdit, QVBoxLayout, QWidget  # noqa: E402

from vectordrive import portable  # noqa: E402
from vectordrive.core import text as TX  # noqa: E402
from vectordrive.core.document import Layer, Text  # noqa: E402
from vectordrive.core.geom import Affine  # noqa: E402
from vectordrive.ui.dialogs import FontBox  # noqa: E402

app = QApplication.instance() or QApplication([])
SYSTEM = 'Essai Système 994'


def forget():
    s = portable.settings()
    for k in ('polices/favorites', 'polices/filtre'):
        s.remove(k)
    s.sync()


class Base(unittest.TestCase):

    def setUp(self):
        forget()
        self.addCleanup(forget)
        self.win = QWidget()
        self.win.resize(600, 700)                                          # l'écran hors écran : 800 × 800
        lay = QVBoxLayout(self.win)
        self.box = FontBox()
        self.box.addItem(SYSTEM)                                           # hors écran, Qt ne connaît aucune police
        lay.addWidget(self.box)
        lay.addStretch(1)
        self.win.show()
        app.processEvents()
        self.addCleanup(self.win.deleteLater)
        self.addCleanup(self.win.close)

    def opened(self):
        self.box.setCurrentFont('VD Trait')
        self.box.showPopup()
        app.processEvents()
        pop = QApplication.activePopupWidget()
        self.assertIsNotNone(pop)
        self.addCleanup(self.box.hidePopup)
        return pop

    def click_row(self, pop, name, x=None, last=False):
        rows = [r for r in range(pop.list.count()) if pop.list.item(r).data(Qt.ItemDataRole.UserRole) == name]
        self.assertTrue(rows, name)
        it = pop.list.item(rows[-1] if last else rows[0])
        pop.list.scrollToItem(it)
        app.processEvents()
        rect = pop.list.visualItemRect(it)
        pt = QPoint(rect.left() + 8 if x == 'star' else rect.center().x(), rect.center().y())
        QTest.mouseClick(pop.list.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, pt)
        app.processEvents()


class Height(Base):

    def test_down_to_the_bottom_of_the_window(self):
        pop = self.opened()
        bottom = self.win.geometry().bottom()
        top = self.box.mapToGlobal(QPoint(0, self.box.height())).y()
        self.assertGreaterEqual(pop.geometry().bottom(), bottom - 2)       # avant : une dizaine de lignes
        self.assertGreaterEqual(pop.height(), bottom - top - 2)
        self.assertGreaterEqual(pop.width(), self.box.width())

    def test_no_room_below_opens_above_never_on_the_box(self):
        lay = self.win.layout()
        lay.takeAt(lay.count() - 1)                                        # la liste déroulante en bas
        lay.insertStretch(0, 1)
        app.processEvents()
        pop = self.opened()
        g = self.win.geometry()
        self.assertLessEqual(pop.geometry().top(), g.top() + 2)            # toute la hauteur au-dessus
        self.assertLess(pop.geometry().bottom(), self.box.mapToGlobal(QPoint(0, 0)).y())   # la flèche reste libre

    def test_second_click_on_the_arrow_closes(self):
        from PySide6.QtWidgets import QStyle, QStyleOptionComboBox
        pop = self.opened()
        opt = QStyleOptionComboBox()
        self.box.initStyleOption(opt)
        arrow = self.box.style().subControlRect(QStyle.ComplexControl.CC_ComboBox, opt,
                                                QStyle.SubControl.SC_ComboBoxArrow, self.box).center()
        calls = []
        real = pop.setAttribute
        pop.setAttribute = lambda a, on=True: (calls.append((a, on)), real(a, on))   # Qt l'efface après usage
        self.addCleanup(lambda: delattr(pop, 'setAttribute'))
        QTest.mouseClick(pop, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                         pop.mapFromGlobal(self.box.mapToGlobal(arrow)))
        app.processEvents()
        self.assertFalse(pop.isVisible())
        self.assertIn((Qt.WidgetAttribute.WA_NoMouseReplay, True), calls)   # le clic n'est pas rejoué : fermée

    def test_small_window_outside_the_main_one_uses_the_screen(self):
        from vectordrive.ui import fontlist
        small = QWidget(self.win, Qt.WindowType.Dialog)
        small.resize(300, 200)
        QVBoxLayout(small).addWidget(box := FontBox())
        small.show()
        g = self.win.geometry()
        small.move(g.right() + 40, g.top())                                # à côté de la fenêtre principale
        app.processEvents()
        self.addCleanup(small.close)
        self.assertEqual(fontlist.area_for(box), fontlist.screen_of(box).availableGeometry())   # avant : la fenêtre


class SearchAndFilters(Base):

    def test_search_several_words_no_case_no_accents(self):
        pop = self.opened()
        pop.search.setText('geo VD')
        self.assertEqual(pop.shown(), ['VD Géo'])
        pop.search.setText('vd GÉO')
        self.assertEqual(pop.shown(), ['VD Géo'])
        pop.search.setText('vd')
        self.assertLessEqual({'VD Trait', 'VD Géo'}, set(pop.shown()))
        self.assertTrue(all('vd' in n.lower() for n in pop.shown()))
        pop.search.setText('aucune police ne porte ce nom 994')
        self.assertEqual(pop.shown(), [])

    def test_filter_builtin(self):
        pop = self.opened()
        pop.filter_buttons['integree'].click()
        self.assertEqual(pop.shown(), ['VD Trait', 'VD Géo'])
        self.assertEqual(str(portable.settings().value('polices/filtre')), 'integree')   # repris à la prochaine fois
        self.box.hidePopup()
        pop = self.opened()
        self.assertTrue(pop.filter_buttons['integree'].isChecked())
        system = [e[0] for e in pop.entries() if e[1] == 'systeme']       # suite complète : Qt en connaît peut-être d'autres
        self.assertIn(SYSTEM, system)
        pop.filter_buttons['systeme'].click()
        self.assertEqual(pop.shown(), system)
        self.assertNotIn('VD Trait', system)
        pop.filter_buttons['toutes'].click()
        self.assertEqual(pop.shown(), [e[0] for e in pop.entries()])
        self.assertEqual(pop.shown()[:2], ['VD Trait', 'VD Géo'])

    def test_kept_filter_without_the_current_font_or_empty(self):
        portable.settings().setValue('polices/filtre', 'systeme')
        pop = self.opened()                                                # police : VD Trait, intégrée
        self.assertTrue(pop.filter_buttons['toutes'].isChecked())          # avant : la liste sans VD Trait
        self.assertIn('VD Trait', pop.shown())
        self.box.hidePopup()
        portable.settings().setValue('polices/filtre', 'svg')
        pop = self.opened()
        self.assertTrue(pop.filter_buttons['toutes'].isChecked())          # avant : « Aucune police ne correspond »
        self.assertFalse(pop.filter_buttons['svg'].isEnabled())            # pas de police SVG : grisé

    def test_system_fonts_marked(self):
        pop = self.opened()
        kinds = {pop.list.item(r).data(Qt.ItemDataRole.UserRole + 1) for r in pop.font_rows()}
        self.assertEqual(kinds, {'integree', 'systeme'})
        n = sum(1 for i in range(self.box.count()) if self.box.itemText(i))
        self.assertEqual(len(pop.shown()), n)                               # toutes, une fois chacune


class Favorites(Base):

    def test_star_marks_a_favorite_kept_and_listed_first(self):
        pop = self.opened()
        self.click_row(pop, 'VD Géo', 'star')
        self.assertTrue(pop.isVisible())                                    # l'étoile ne ferme pas la liste
        self.assertEqual(self.box.currentText(), 'VD Trait')                # ni ne choisit la police
        from vectordrive.ui import fontlist
        self.assertEqual(fontlist.favorites(), ['VD Géo'])
        self.box.hidePopup()
        pop = self.opened()
        self.assertEqual(pop.list.item(0).data(Qt.ItemDataRole.UserRole), None)       # titre « Favorites »
        self.assertEqual(pop.shown()[0], 'VD Géo')
        pop.filter_buttons['favorites'].click()
        self.assertEqual(pop.shown(), ['VD Géo'])
        self.click_row(pop, 'VD Géo', 'star')                               # plus favorite
        self.assertEqual(fontlist.favorites(), [])

    def test_double_click_on_the_star_and_another_process(self):
        from vectordrive.ui import fontlist
        pop = self.opened()
        fontlist.set_favorites(['VD Trait'])                               # marquée ailleurs, liste ouverte
        rows = [r for r in pop.font_rows() if pop.list.item(r).data(Qt.ItemDataRole.UserRole) == 'VD Géo']
        rect = pop.list.visualItemRect(pop.list.item(rows[0]))
        pt = QPointF(rect.left() + 8, rect.center().y())
        vp = pop.list.viewport()
        for t in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonRelease, QEvent.Type.MouseButtonDblClick,
                  QEvent.Type.MouseButtonRelease):                         # un double-clic sur l'étoile
            QApplication.sendEvent(vp, QMouseEvent(t, pt, vp.mapToGlobal(pt), Qt.MouseButton.LeftButton,
                                                   Qt.MouseButton.LeftButton if t != QEvent.Type.MouseButtonRelease
                                                   else Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier))
        self.assertEqual(fontlist.favorites(), ['VD Trait', 'VD Géo'])     # avant : basculée deux fois, l'autre perdue
        self.assertTrue(pop.isVisible())

    def test_favorites_filter_without_favorite(self):
        portable.settings().setValue('polices/filtre', 'favorites')
        pop = self.opened()
        self.assertTrue(pop.filter_buttons['toutes'].isChecked())          # aucune favorite : toutes
        pop.filter_buttons['favorites'].click()
        self.assertEqual(pop.shown(), [])
        self.assertIn('étoile', pop.info.text())


class Choosing(Base):

    def test_click_chooses_like_the_qt_list(self):
        got = []
        self.box.activated.connect(got.append)
        texts = []
        self.box.currentTextChanged.connect(texts.append)
        pop = self.opened()
        self.click_row(pop, 'VD Géo')
        self.assertFalse(pop.isVisible())
        self.assertEqual(self.box.currentText(), 'VD Géo')
        self.assertEqual(got, [self.box.findText('VD Géo')])
        self.assertIn('VD Géo', texts)

    def test_focus_left_where_the_choice_put_it(self):
        edit = QLineEdit()                                                 # le dessin, pendant une saisie de texte
        self.win.layout().addWidget(edit)
        app.processEvents()
        self.box.activated.connect(lambda _i: edit.setFocus())
        pop = self.opened()
        self.click_row(pop, 'VD Géo')
        self.assertEqual(self.box.currentText(), 'VD Géo')
        self.assertIs(self.win.focusWidget(), edit)                         # avant : repris par la liste de polices

    def test_hover_and_drag_from_the_box(self):
        pop = self.opened()
        vp = pop.list.viewport()
        rows = [r for r in pop.font_rows() if pop.list.item(r).data(Qt.ItemDataRole.UserRole) == 'VD Géo']
        rect = pop.list.visualItemRect(pop.list.item(rows[0]))
        pt = QPointF(rect.center())
        QApplication.sendEvent(vp, QMouseEvent(QEvent.Type.MouseMove, pt, vp.mapToGlobal(pt), Qt.MouseButton.NoButton,
                                               Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier))
        self.assertEqual(pop.list.currentItem().data(Qt.ItemDataRole.UserRole), 'VD Géo')   # surlignée au survol
        QApplication.sendEvent(vp, QMouseEvent(QEvent.Type.MouseButtonRelease, pt, vp.mapToGlobal(pt),
                                               Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton,
                                               Qt.KeyboardModifier.NoModifier))   # enfoncé sur la flèche, relâché ici
        self.assertFalse(pop.isVisible())
        self.assertEqual(self.box.currentText(), 'VD Géo')

    def test_style_of_the_box_not_in_the_list(self):
        self.box.setStyleSheet('color: gray;')                             # « valeurs différentes » d'un formulaire
        pop = self.opened()
        self.assertIs(pop.parentWidget(), self.win)
        self.assertNotEqual(pop.list.palette().color(QPalette.ColorRole.Text).name(), '#808080')

    def test_keyboard(self):
        pop = self.opened()
        self.assertTrue(pop.search.hasFocus() or not pop.isActiveWindow())
        QTest.keyClicks(pop.search, 'geo')                  # (QTest.keyClicks ne sait pas taper « é » hors écran)
        QTest.keyClick(pop.search, Qt.Key.Key_Return)
        app.processEvents()
        self.assertEqual(self.box.currentText(), 'VD Géo')
        pop = self.opened()
        pop.filter_buttons['integree'].click()
        self.assertEqual(pop.list.currentItem().data(Qt.ItemDataRole.UserRole), 'VD Trait')
        QTest.keyClick(pop.search, Qt.Key.Key_Down)
        self.assertEqual(pop.list.currentItem().data(Qt.ItemDataRole.UserRole), 'VD Géo')
        QTest.keyClick(pop.search, Qt.Key.Key_Escape)
        app.processEvents()
        self.assertFalse(pop.isVisible())
        self.assertEqual(self.box.currentText(), 'VD Trait')                # inchangée


class InTheWindow(unittest.TestCase):

    def test_text_format_font_from_the_list(self):
        from vectordrive.ui.main_window import MainWindow
        forget()
        w = MainWindow()
        try:
            doc = w.canvas.doc
            layer = Layer(name='Plan 1')
            doc.layers[:] = [layer]
            doc.active = layer.id
            t = Text(text='Abc', font='VD Trait', size=5.0, matrix=Affine.translation(10, 10))
            t.outline = TX.outline_for(t)
            layer.items[:] = [t]
            w.canvas.select([t])
            box = w.textbar.font
            box.showPopup()
            app.processEvents()
            pop = box._popup
            pop.search.setText('VD Géo')
            QTest.keyClick(pop.search, Qt.Key.Key_Return)
            app.processEvents()
            self.assertEqual(layer.items[0].font, 'VD Géo')
        finally:
            w.modified = False
            w.close()
            w.deleteLater()


if __name__ == '__main__':
    unittest.main()
