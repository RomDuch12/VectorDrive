"""Round 1094 : plus aucun groupe du ruban replié en famille (un bouton dont le clic gauche déroulait une barre
flottante, prise pour un menu du clic droit) ; trop étroit, l'onglet défile de côté — la molette, la petite barre sous
lui, montrée seulement quand il déborde."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1094.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QAction, QIcon, QPixmap, QWheelEvent
from PySide6.QtWidgets import QApplication, QFrame, QMenu, QScrollBar, QWidget

app = QApplication.instance() or QApplication([])


def _icon():
    pm = QPixmap(16, 16)
    pm.fill()
    return QIcon(pm)


def ribbon_with(groups):
    from vectordrive.ui.ribbon import Ribbon
    r = Ribbon()
    page = r.add_tab('Essai')
    for title, n in groups:
        g = page.group(title)
        for i in range(n):
            g.add(QAction(_icon(), f'{title} commande {i}', r), big=i == 0)
    r.finalize()
    return r, page


def wheel(target: QWidget, dy: int) -> None:
    pos = QPointF(target.width() / 2, target.height() / 2)
    ev = QWheelEvent(pos, QPointF(target.mapToGlobal(pos.toPoint())), QPoint(0, 0), QPoint(0, dy),
                     Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase, False)
    QApplication.sendEvent(target, ev)


def popups(root: QWidget) -> list:
    """Les fenêtres flottantes d'un groupe du ruban sous `root` (pas les listes des champs déroulants, ni les menus)."""
    from vectordrive.ui.ribbon import RibbonGroup
    return [w for w in root.findChildren(QFrame) if not isinstance(w, QMenu) and isinstance(w.parent(), RibbonGroup)
            and w.windowFlags() & Qt.WindowType.Popup == Qt.WindowType.Popup]


class NoFamily(unittest.TestCase):
    def test_gone_from_the_code_and_options(self):
        from vectordrive.ui import ribbon
        from vectordrive.ui.options import BY_KEY
        self.assertFalse(hasattr(ribbon, 'FamilyPopup'))
        self.assertFalse(hasattr(ribbon.RibbonGroup, 'set_collapsed'))
        self.assertFalse(hasattr(ribbon.RibbonGroup, 'unroll'))
        self.assertNotIn('vue/ruban_familles', BY_KEY)

    def test_narrow_ribbon_keeps_every_group_open(self):
        r, page = ribbon_with([('Transformation', 9), ('Alignement', 8), ('Ordre', 6)])
        r.resize(260, 200)
        r.show()
        app.processEvents()
        r.fit_current()
        for g in page.groups():
            self.assertIs(g.body.parent(), g)
            self.assertTrue(all(b.isVisibleTo(g) for b in g.buttons()))
        self.assertEqual(popups(r), [])
        r.close()
        r.deleteLater()


class Scrolls(unittest.TestCase):
    def setUp(self):
        self.r, self.page = ribbon_with([('Un', 12), ('Deux', 12), ('Trois', 12), ('Quatre', 12)])
        self.r.show()

    def tearDown(self):
        self.r.close()
        self.r.deleteLater()

    def settle(self, width):
        self.r.resize(width, 200)
        for _ in range(3):
            app.processEvents()
        self.r.fit_current()
        app.processEvents()

    def test_wheel_scrolls_sideways_and_bar_takes_its_room(self):
        self.settle(5000)
        sc = self.r.widget(0)
        wide_h = self.r.height()
        self.assertEqual(sc.horizontalScrollBarPolicy(), Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.settle(300)
        bar = sc.horizontalScrollBar()
        self.assertGreater(bar.maximum(), 0)
        self.assertEqual(sc.horizontalScrollBarPolicy(), Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.assertEqual(self.r.height(), wide_h + bar.sizeHint().height())   # sa place prise : légendes visibles
        self.assertGreaterEqual(sc.viewport().height(), self.page.height())
        self.assertEqual(bar.value(), 0)
        # la molette sur la page (une vraie, sur un bouton, remonte jusqu'à elle ; une simulée ne remonte pas)
        wheel(sc.viewport(), -120)
        self.assertGreater(bar.value(), 0)
        v = bar.value()
        wheel(sc.viewport(), 120)
        self.assertLess(bar.value(), v)
        self.settle(5000)                                                 # place revenue : plus de barre
        self.assertEqual(self.r.height(), wide_h)
        self.assertEqual(sc.horizontalScrollBarPolicy(), Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def test_wheel_does_nothing_when_it_fits(self):
        self.settle(5000)
        sc = self.r.widget(0)
        self.assertEqual(sc.horizontalScrollBar().maximum(), 0)
        wheel(sc.viewport(), -120)
        self.assertEqual(sc.horizontalScrollBar().value(), 0)


class MainWindowNarrow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from vectordrive.ui.main_window import MainWindow
        cls.w = MainWindow()
        cls.w.resize(900, 700)
        cls.w.show()
        app.processEvents()

    @classmethod
    def tearDownClass(cls):
        cls.w.modified = False
        cls.w.close()

    def test_every_tab_open_or_scrolling(self):
        """Sur un portable étroit : chaque onglet, chaque groupe ouvert (CAD › Transformation, Alignement…) ; un
        onglet qui ne tient pas défile, jamais de barre flottante."""
        r = self.w.ribbon
        seen = 0
        for i in range(r.count()):
            if not r.isTabVisible(i) or r.page(i) is None:
                continue
            r.setCurrentIndex(i)
            r.fit_current()
            app.processEvents()
            with self.subTest(onglet=r.tabText(i)):
                for g in r.page(i).groups():
                    self.assertIs(g.body.parent(), g)
                sc = r.widget(i)
                if r.page(i).sizeHint().width() > sc.width():
                    self.assertGreater(sc.horizontalScrollBar().maximum(), 0)
                    self.assertIsInstance(sc.horizontalScrollBar(), QScrollBar)
                seen += 1
        self.assertGreater(seen, 3)
        self.assertEqual(popups(r), [])

    def test_old_setting_ignored(self):
        self.w.settings.setValue('vue/ruban_familles', 'toujours')        # réglage d'une version d'avant
        self.w._apply_ribbon_options()
        r = self.w.ribbon
        r.fit_current()
        self.assertTrue(all(g.body.parent() is g for g in r.page(r.currentIndex()).groups()))
        self.w.settings.remove('vue/ruban_familles')



class WheelOnFields(unittest.TestCase):
    def test_spinbox_without_focus_lets_the_tab_scroll(self):
        from PySide6.QtWidgets import QSpinBox
        from vectordrive.ui.ribbon import Ribbon
        r = Ribbon()
        page = r.add_tab('Essai')
        for t in ('Un', 'Deux', 'Trois', 'Quatre'):
            g = page.group(t)
            for i in range(12):
                g.add(QAction(_icon(), f'{t} {i}', r), big=i == 0)
        spin = QSpinBox()
        spin.setRange(0, 100)
        spin.setValue(50)
        page.groups()[0].add_widget(spin)
        r.finalize()
        r.resize(300, 200)
        r.show()
        for _ in range(3):
            app.processEvents()
        r.fit_current()
        app.processEvents()
        bar = r.widget(0).horizontalScrollBar()
        self.assertGreater(bar.maximum(), 0)
        self.assertEqual(spin.focusPolicy(), Qt.FocusPolicy.StrongFocus)
        wheel(spin, -120)                                                 # sans le focus : l'onglet défile
        self.assertEqual(spin.value(), 50)
        self.assertGreater(bar.value(), 0)
        r.close()
        r.deleteLater()


class TypeEditPalettes(unittest.TestCase):
    """Disposition TypeEdit 13 : CAD › Manipulation, Alignement… étaient des boutons de palette, qui ouvraient un menu
    à la souris au clic gauche (le « menu du clic droit » de la demande)."""

    @classmethod
    def setUpClass(cls):
        from vectordrive.ui.main_window import MainWindow
        cls.w = MainWindow()

    @classmethod
    def tearDownClass(cls):
        cls.w.modified = False
        cls.w.close()

    def test_palette_commands_in_the_group(self):
        from PySide6.QtWidgets import QToolButton
        from vectordrive.ui.typeedit_layout import TELayout, TETab, TEPanel
        w = self.w
        lay = TELayout(tabs=[TETab('CAD', [TEPanel('Manipulation', [('ID_COMPO_SHOWPALTRANSFORMATION', True)]),
                                           TEPanel('Alignement', [('ID_COMPO_SHOWPALALIGN', True)])])])
        w.layout_active, w._te_layout = True, lay
        w._build_te_tabs(lay)
        try:
            r = w.ribbon
            i = next(k for k in range(r.count()) if r.tabText(k) == 'CAD')
            groups = {g.title.text(): g for g in r.page(i).groups()}
            for title, key in (('Manipulation', 'palette_transform'), ('Alignement', 'palette_align')):
                acts = [b.defaultAction() for b in groups[title].findChildren(QToolButton)]
                self.assertNotIn(w.A[key], acts)                          # plus le bouton qui ouvre un menu
                want = [w.A[k] for k in w.PALETTES[key][1] if k in w.A]
                self.assertTrue(all(a in acts for a in want), title)      # ses commandes, dans le groupe
            self.assertIsNone(QApplication.activePopupWidget())
        finally:
            w._clear_te_tabs()
            w.layout_active = False

    def test_shortcut_opens_a_floating_palette_not_a_menu(self):
        w = self.w
        w.A['palette_align'].trigger()
        pal = w._last_palette
        self.assertNotIsInstance(pal, QMenu)
        self.assertEqual(pal.windowType(), Qt.WindowType.Tool)                # une fenêtre d'outils
        self.assertTrue(pal.isVisible())
        self.assertIsNone(QApplication.activePopupWidget())
        self.assertIn(w.A['align_left'], pal.actions())
        app.processEvents()
        self.assertTrue(pal.isVisible())                                  # reste ouverte (pas un menu qui se ferme)
        pal.close()


if __name__ == '__main__':
    unittest.main()
