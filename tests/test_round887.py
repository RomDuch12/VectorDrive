"""Round 887 : Ouvrir (Ctrl+O) retient sa taille et son dossier et propose les derniers dossiers ; le
va-et-vient montre toujours 2D et 3D, l'un grisé, l'autre mis en valeur ; la FAO suit le mode."""
import os
import pathlib
import shutil
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'
_TMP = tempfile.mkdtemp(prefix='vd887_')
# round 1159 : posés par setUpModule, plus à l'import (ils valaient alors pour tous les essais du processus)
_ENV = {'VECTORDRIVE_SETTINGS': os.path.join(_TMP, 'r887.ini'),
        'VECTORDRIVE_SESSION': os.path.join(_TMP, 'session.json'),
        'VECTORDRIVE_CACHE': os.path.join(_TMP, 'cache')}
_SAVED = {}
from tests import seed_settings  # noqa: E402

from collections import Counter

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

from vectordrive.ui import recent
from vectordrive.ui import ribbon_editor as RE
from vectordrive.ui import session
from vectordrive.ui.file_browser import FULL_KEY, GEOMETRY_KEY, FileBrowser
from vectordrive.ui.main_window import MainWindow
from vectordrive.ui.ribbon import ViewSwitch

W = Qt.WindowState


def dist(a, b) -> int:
    return abs(a.red() - b.red()) + abs(a.green() - b.green()) + abs(a.blue() - b.blue())


def setUpModule():
    os.makedirs(_TMP, exist_ok=True)
    for k, v in _ENV.items():
        _SAVED[k] = os.environ.get(k)
        os.environ[k] = v
    seed_settings(os.environ['VECTORDRIVE_SETTINGS'])           # l'accrochage éteint, comme pour les autres essais


def tearDownModule():
    for k, v in _SAVED.items():                                 # les essais suivants retrouvent leurs réglages
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    shutil.rmtree(_TMP, ignore_errors=True)


class Base(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.win = MainWindow()

    @classmethod
    def tearDownClass(cls):
        cls.win.modified = False
        cls.win.close()

    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp(dir=_TMP))
        self.win.set_view_mode('2d')

    def tearDown(self):
        self.win.set_view_mode('2d')

    def folder(self, name):
        p = self.tmp / name
        p.mkdir(parents=True, exist_ok=True)
        return p


class TestSwitch(Base):

    def sides(self, b):
        """De chaque moitié du bouton dessiné : le fond (sa couleur la plus présente), le nombre de
        points écrits, et la couleur écrite la plus éloignée du fond."""
        b.resize(b.sizeHint())
        img = b.grab().toImage()
        out = []
        for x0, x1 in ((5, img.width() // 2 - 5), (img.width() // 2 + 5, img.width() - 5)):    # sans le liseré (903)
            rows = [QColor(img.pixel(x, y)) for x in range(x0, x1) for y in range(5, img.height() - 5)]
            names = [c.name() for c in rows]
            ground = QColor(Counter(names).most_common(1)[0][0])
            ink = [c for c in rows if c.name() != ground.name()]
            far = max(ink, key=lambda c: dist(c, ground)) if ink else ground
            out.append({'fond': ground, 'ecrits': len(ink), 'encre': far})
        return out

    def buttons(self):
        return (self.win.ribbon.view_button,)                          # round 903 : plus dans le ruban

    def check(self, b, lit, grey):
        pal = b.palette()
        color = pal.color(QPalette.ColorRole.Highlight)
        self.assertEqual(lit['fond'].name(), color.name())             # mis en valeur
        self.assertNotEqual(grey['fond'].name(), color.name())
        self.assertGreater(lit['ecrits'], 3)                           # les deux écrits
        self.assertGreater(grey['ecrits'], 3)
        off = pal.color(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText)
        normal = pal.color(QPalette.ColorGroup.Active, QPalette.ColorRole.WindowText)
        self.assertLess(dist(grey['encre'], off), dist(grey['encre'], normal))     # l'autre grisé

    def test_both_are_written_and_one_is_lit(self):
        for b in self.buttons():
            self.assertIsInstance(b, ViewSwitch)
            left, right = self.sides(b)
            self.check(b, left, right)                                 # en 2D : 2D à gauche
            self.win.set_view_mode('3d')
            left, right = self.sides(b)
            self.check(b, right, left)
            self.win.set_view_mode('2d')

    def test_the_label_no_longer_changes(self):
        t = self.win.A['view_toggle']
        self.assertEqual(t.text(), '2D / 3D')
        t.trigger()
        self.assertEqual(t.text(), '2D / 3D')

    def test_one_click_anywhere_flips(self):
        b = self.win.ribbon.view_button
        b.resize(b.sizeHint())
        for x in (b.width() // 4, b.width() * 3 // 4):                 # d'un côté comme de l'autre
            before = self.win.view_mode()
            QTest.mouseClick(b, Qt.MouseButton.LeftButton, pos=QPoint(x, b.height() // 2))
            self.assertNotEqual(self.win.view_mode(), before)
            QTest.mouseClick(b, Qt.MouseButton.LeftButton, pos=QPoint(x, b.height() // 2))
            self.assertEqual(self.win.view_mode(), before)

    def test_the_tooltip_is_the_action_s(self):
        self.assertIn('Va-et-vient', self.win.ribbon.view_button.toolTip())

    def test_any_other_button_stays_ordinary(self):
        r = self.win.ribbon
        vue = r.page(next(i for i in range(r.count()) if r.tabText(i) == 'Vue'))
        others = [b for g in vue.groups() for b in g.buttons() if b.defaultAction() is not self.win.A['view_toggle']]
        self.assertTrue(others)
        self.assertFalse(any(isinstance(b, ViewSwitch) for b in others))


class TestFao(Base):

    def visible(self):
        r = self.win.ribbon
        return [r.tabText(i) for i in range(r.count()) if r.isTabVisible(i) and r.tabText(i).startswith('FAO')]

    def index(self, title):
        r = self.win.ribbon
        return next(i for i in range(r.count()) if r.tabText(i) == title)

    def test_one_tab_at_a_time(self):
        self.assertEqual(self.visible(), ['FAO 2D'])
        self.win.set_view_mode('3d')
        self.assertEqual(self.visible(), ['FAO 3D'])
        self.win.toggle_view_mode()
        self.assertEqual(self.visible(), ['FAO 2D'])

    def test_on_the_fao_tab_it_follows(self):
        r = self.win.ribbon
        r.setCurrentIndex(self.index('FAO 2D'))
        self.win.set_view_mode('3d')
        self.assertEqual(r.tabText(r.currentIndex()), 'FAO 3D')
        self.win.set_view_mode('2d')
        self.assertEqual(r.tabText(r.currentIndex()), 'FAO 2D')

    def test_elsewhere_the_current_tab_stays(self):
        r = self.win.ribbon
        r.setCurrentIndex(self.index('Vue'))
        self.win.set_view_mode('3d')
        self.assertEqual(r.tabText(r.currentIndex()), 'Vue')
        self.assertEqual(self.visible(), ['FAO 3D'])

    def test_a_command_of_the_3d_tab_brings_its_tab(self):
        self.win._cam3d('with_part', 'auto3d')                         # commande du ruban FAO 3D
        self.assertEqual(self.win.view_mode(), '3d')
        self.assertEqual(self.visible(), ['FAO 3D'])

    def test_rebuilding_the_ribbon_keeps_it(self):
        self.win.set_view_mode('3d')
        self.win._build_custom_tab(restyle=False)
        self.assertEqual(self.visible(), ['FAO 3D'])
        self.win.set_view_mode('2d')
        self.win._build_custom_tab(restyle=False)
        self.assertEqual(self.visible(), ['FAO 2D'])

    def test_a_tab_hidden_by_the_user_stays_hidden(self):
        RE.set_hidden(self.win.settings, ['FAO 3D'])
        try:
            self.win._build_custom_tab(restyle=False)
            self.assertEqual(self.visible(), ['FAO 2D'])
            self.win.set_view_mode('3d')
            self.assertEqual(self.visible(), [])
            self.win.set_view_mode('2d')
            self.assertEqual(self.visible(), ['FAO 2D'])
        finally:
            RE.set_hidden(self.win.settings, [])
            self.win._build_custom_tab(restyle=False)

    def test_each_drawing_keeps_its_mode_and_its_tab(self):
        w = self.win
        first = w.doc_index
        w.modified = True                                              # l'onglet vide et intact serait repris
        w.new_document()
        second = w.doc_index
        self.assertNotEqual(first, second)
        try:
            w.set_view_mode('3d')
            w.switch_tab(first)
            self.assertEqual(w.view_mode(), '2d')
            self.assertEqual(self.visible(), ['FAO 2D'])
            w.switch_tab(second)
            self.assertEqual(w.view_mode(), '3d')
            self.assertEqual(self.visible(), ['FAO 3D'])
        finally:
            w.switch_tab(second)
            w.modified = False
            w.close_tab(second)
            w.switch_tab(first)
            w.modified = False

    def test_the_session_reopens_the_tab_of_the_mode(self):
        r = self.win.ribbon
        drawing = self.tmp / 'essai.dxf'
        drawing.write_text('0\nEOF\n', encoding='ascii')
        for saved, mode, want in (('FAO 3D', '2d', 'FAO 2D'), ('FAO 2D', '2d', 'FAO 2D'), ('Vue', '2d', 'Vue')):
            r.setCurrentIndex(self.index('CAD'))
            index = {'docs': [{'path': str(drawing)}], 'ribbon': saved}
            with mock.patch.object(session, 'load_index', return_value=index), \
                    mock.patch.object(self.win, 'open_path', return_value=True), \
                    mock.patch.object(self.win, 'switch_tab'):
                self.assertEqual(session.restore(self.win, self.tmp), 1)
            self.assertEqual(r.tabText(r.currentIndex()), want, saved)


class TestTeLayout(unittest.TestCase):

    def test_the_te_layout_keeps_them_away(self):
        from tests.test_round213 import SCRIPT, STRINGS
        from vectordrive.ui import shortcuts
        from vectordrive.ui import typeedit_layout as TL
        TL._cache.clear()
        fake = TL.parse(SCRIPT, STRINGS)
        with mock.patch.object(TL, 'installed', return_value=fake):
            w = MainWindow()
            try:
                had = w.A.get('quote_essai')
                w.A['quote_essai'] = w.A['about']
                with mock.patch.dict(shortcuts.TE_ACTIONS, {'ID_FILE_COST': 'quote_essai'}):
                    w.set_theme('typeedit13')
                r = w.ribbon
                self.assertTrue(w.layout_active)
                names = [r.tabText(i) for i in range(r.count()) if r.isTabVisible(i)]
                self.assertNotIn('FAO 2D', names)
                w.set_view_mode('3d')
                names = [r.tabText(i) for i in range(r.count()) if r.isTabVisible(i)]
                self.assertNotIn('FAO 3D', names)
                w.set_view_mode('2d')
                w.set_theme('clair')
                names = [r.tabText(i) for i in range(r.count()) if r.isTabVisible(i)]
                self.assertIn('FAO 2D', names)
                self.assertNotIn('FAO 3D', names)
                if had is not None:
                    w.A['quote_essai'] = had
            finally:
                w.modified = False
                w.close()
                TL._cache.clear()


class TestWindow(Base):

    def setUp(self):
        super().setUp()
        s = self.win.settings
        for k in (GEOMETRY_KEY, FULL_KEY, 'navigateur/agrandie'):
            s.remove(k)

    def tearDown(self):
        s = self.win.settings
        for k in (GEOMETRY_KEY, FULL_KEY):
            s.remove(k)
        super().tearDown()

    def shown(self):
        d = FileBrowser(self.win, str(self.tmp))
        d.show()
        QTest.qWait(20)
        return d

    def test_first_time_full_size(self):
        d = FileBrowser(self.win, str(self.tmp))
        self.assertTrue(d.windowState() & W.WindowMaximized)
        d.reject()

    def test_a_smaller_size_comes_back(self):
        d = self.shown()
        d.setWindowState(W.WindowNoState)
        QTest.qWait(20)
        size = (d.minimumSizeHint().width() + 30, 620)
        d.resize(*size)
        QTest.qWait(20)
        d.reject()
        self.assertTrue(self.win.settings.value(GEOMETRY_KEY))
        d = self.shown()
        self.assertFalse(d.windowState() & (W.WindowMaximized | W.WindowFullScreen))
        self.assertEqual(d.height(), size[1])                          # en largeur, l'écran d'essai fait 800 px
        self.assertLessEqual(d.width(), size[0])
        d.reject()

    def test_the_longest_format_no_longer_widens_the_window(self):
        d = FileBrowser(self.win, str(self.tmp))
        longest = max(d.filter.fontMetrics().horizontalAdvance(d.filter.itemText(i)) for i in range(d.filter.count()))
        self.assertLess(d.filter.minimumSizeHint().width(), longest / 2)
        self.assertGreaterEqual(d.filter.view().minimumWidth(), d.filter.view().sizeHintForColumn(0))   # sa liste, entière
        d.reject()

    def test_maximized_comes_back(self):
        d = self.shown()
        self.assertTrue(d.windowState() & W.WindowMaximized)
        d.reject()
        d = self.shown()
        self.assertTrue(d.windowState() & W.WindowMaximized)
        d.reject()

    def test_full_screen_comes_back_and_leaves_to_the_size_before(self):
        d = self.shown()
        d.setWindowState(W.WindowNoState)
        d.resize(d.minimumSizeHint().width() + 30, 620)
        QTest.qWait(20)
        d.b_full.click()
        self.assertTrue(d.windowState() & W.WindowFullScreen)
        d.b_full.click()
        self.assertFalse(d.windowState() & (W.WindowMaximized | W.WindowFullScreen))
        d.b_full.click()
        QTest.qWait(20)
        d.reject()
        d = self.shown()
        self.assertTrue(d.windowState() & W.WindowFullScreen)
        d.reject()

    def test_a_window_never_shown_saves_no_size(self):
        d = FileBrowser(self.win, str(self.tmp))
        d.reject()
        self.assertFalse(self.win.settings.value(GEOMETRY_KEY))

    def test_a_damaged_value_falls_back_to_full_size(self):
        self.win.settings.setValue(GEOMETRY_KEY, 'abimé')
        d = FileBrowser(self.win, str(self.tmp))
        self.assertTrue(d.windowState() & W.WindowMaximized)
        d.reject()


class TestFolder(Base):

    def run_dialog(self, then, ok=0, **kw):
        def fake(dlg):
            then(dlg)
            return ok
        with mock.patch.object(FileBrowser, 'exec', fake):
            return self.win.file_browser(**kw)

    def test_a_cancelled_visit_is_remembered(self):
        a, b = self.folder('a'), self.folder('b')
        self.win.settings.setValue('dossier/ouvrir', str(a))
        self.run_dialog(lambda d: d.panel.show_folder(b))
        self.assertEqual(self.win._last_dir('ouvrir'), str(b))
        seen = []
        self.run_dialog(lambda d: seen.append(d.panel._folder))
        self.assertEqual(seen, [b])

    def test_recents_shown_do_not_change_it(self):
        a = self.folder('a')
        self.win.settings.setValue('dossier/ouvrir', str(a))
        self.run_dialog(lambda d: d.panel.show_recents())
        self.assertEqual(self.win._last_dir('ouvrir'), str(a))

    def test_a_borrowed_window_leaves_it_alone(self):
        a, b = self.folder('a'), self.folder('b')
        self.win.settings.setValue('dossier/ouvrir', str(a))
        self.run_dialog(lambda d: d.panel.show_folder(b), folder=str(b), remember=False)
        self.assertEqual(self.win._last_dir('ouvrir'), str(a))


class TestLastFolders(Base):

    def setUp(self):
        super().setUp()
        self.s = self.win.settings
        self.s.remove(recent.FOLDERS_KEY)
        self.s.remove('fichiers/recents')

    def tearDown(self):
        self.s.remove(recent.FOLDERS_KEY)
        self.s.remove('fichiers/recents')
        super().tearDown()

    def test_opening_notes_the_folder_most_recent_first(self):
        a, b = self.folder('a'), self.folder('b')
        self.win._add_recent(str(a / 'x.vnd'))
        self.win._add_recent(str(b / 'y.vnd'))
        self.win._add_recent(str(a / 'z.vnd'))
        self.assertEqual(recent.recent_folders(self.s), [str(a), str(b)])

    def test_recent_files_seed_the_list(self):
        a, b = self.folder('a'), self.folder('b')
        self.s.setValue('fichiers/recents', [str(b / 'y.vnd'), str(a / 'x.vnd'), str(b / 'z.vnd')])
        self.assertEqual(recent.recent_folders(self.s), [str(b), str(a)])

    def test_a_single_value_read_back_as_text(self):
        a = self.folder('a')
        self.s.setValue(recent.FOLDERS_KEY, str(a))
        self.assertEqual(recent.recent_folders(self.s), [str(a)])

    def test_the_list_is_bounded(self):
        for i in range(recent.FOLDERS_MAX + 5):
            self.win._add_recent(str(self.tmp / f'd{i}' / 'x.vnd'))
        got = recent.recent_folders(self.s)
        self.assertEqual(len(got), recent.FOLDERS_MAX)
        self.assertEqual(got[0], str(self.tmp / f'd{recent.FOLDERS_MAX + 4}'))

    def test_many_files_of_one_folder_do_not_push_the_others_out(self):
        a, b = self.folder('a'), self.folder('b')
        self.win._add_recent(str(b / 'y.vnd'))
        for i in range(self.win.RECENT_MAX + 3):
            self.win._add_recent(str(a / f'{i}.vnd'))
        self.assertEqual(recent.recent_folders(self.s), [str(a), str(b)])

    def test_case_is_one_folder_on_windows(self):
        a = self.folder('a')
        self.s.setValue(recent.FOLDERS_KEY, [str(a), str(a).upper()])
        want = 1 if os.name == 'nt' else 2
        self.assertEqual(len(recent.recent_folders(self.s)), want)

    def dialog(self, folder):
        return FileBrowser(self.win, str(folder))

    def test_the_folder_on_show_is_not_proposed(self):
        a, b = self.folder('a'), self.folder('b')
        self.s.setValue(recent.FOLDERS_KEY, [str(a), str(b)])
        d = self.dialog(a)
        self.assertEqual(d.folder_choices(), [b])
        d.reject()

    def test_a_vanished_folder_is_not_proposed(self):
        a, b = self.folder('a'), self.folder('b')
        self.s.setValue(recent.FOLDERS_KEY, [str(a), str(self.tmp / 'parti'), str(b)])
        d = self.dialog(a)
        self.assertEqual(d.folder_choices(), [b])
        d.reject()

    def test_a_network_folder_is_not_read(self):
        far = r'\\atelier\partage\dessins'
        d = self.dialog(self.folder('b'))
        with mock.patch.object(pathlib.Path, 'is_dir', side_effect=AssertionError('lu')) as isdir:
            with mock.patch('vectordrive.ui.symbols.is_remote', side_effect=lambda p: str(p).startswith('\\\\')):
                self.s.setValue(recent.FOLDERS_KEY, [far])
                self.assertEqual([str(p) for p in d.folder_choices()], [str(pathlib.Path(far))])
            self.assertFalse(isdir.called)
        d.reject()

    def test_the_menu_goes_there(self):
        a, b = self.folder('a'), self.folder('R&D')
        self.s.setValue(recent.FOLDERS_KEY, [str(b)])
        d = self.dialog(a)
        m = d.b_folders.menu()
        m.aboutToShow.emit()
        acts = m.actions()
        self.assertEqual(len(acts), 1)
        self.assertIn('R&&D', acts[0].text())                          # l'esperluette écrite, pas un raccourci
        self.assertEqual(acts[0].toolTip(), str(b))
        acts[0].trigger()
        self.assertEqual(d.panel._folder, b)
        self.assertTrue(d.b_back.isEnabled())                          # Précédent ramène où l'on était
        d.reject()

    def test_filled_again_each_time(self):
        a, b = self.folder('a'), self.folder('b')
        self.s.setValue(recent.FOLDERS_KEY, [str(b)])
        d = self.dialog(a)
        m = d.b_folders.menu()
        m.aboutToShow.emit()
        m.aboutToShow.emit()
        self.assertEqual(len(m.actions()), 1)
        d.reject()

    def test_nothing_to_propose_is_said(self):
        a = self.folder('a')
        d = self.dialog(a)
        m = d.b_folders.menu()
        m.aboutToShow.emit()
        self.assertEqual(len(m.actions()), 1)
        self.assertFalse(m.actions()[0].isEnabled())
        d.reject()

    def test_it_stays_discreet(self):
        d = self.dialog(self.folder('a'))
        self.assertTrue(d.b_folders.autoRaise())                       # à plat, sans liste affichée
        self.assertFalse(d.b_folders.menu().isVisible())
        d.reject()


class TestPreviewBox(Base):

    def test_the_box_with_previews_remembers_too(self):
        a, b = self.folder('a'), self.folder('b')
        s = self.win.settings
        s.setValue(recent.FOLDERS_KEY, [str(a), str(b)])
        recent.set_previews(True)
        seen, wide = [], []
        try:
            def fake(dlg):
                seen.append((list(dlg.history()), dlg.width(), bool(dlg.windowState() & W.WindowMaximized)))
                dlg.show()
                dlg.setWindowState(W.WindowNoState)
                wide.append(dlg.minimumSizeHint().width() + 60)
                dlg.resize(wide[-1], 600)
                QTest.qWait(20)
                dlg.hide()
                return 0
            with mock.patch.object(recent.QFileDialog, 'exec', fake), \
                    mock.patch('vectordrive.ui.options.value', return_value=False):
                self.win.open_dialog()
                self.win.open_dialog()
        finally:
            recent.set_previews(False)
            s.remove(recent.FOLDERS_KEY)
            s.remove(recent.DIALOG_KEY)
        self.assertEqual(seen[0][0][:2], [str(a), str(b)])             # puis le dossier affiché
        self.assertTrue(seen[0][2])                                    # la première fois : agrandie
        self.assertFalse(seen[1][2])                                   # ensuite : sa dernière taille
        self.assertEqual(seen[1][1], wide[0])


if __name__ == '__main__':
    unittest.main()
