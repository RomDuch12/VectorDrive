"""Round 545 : Ouvrir — affichage Détails comme Windows (par défaut, colonnes triables), vignettes en
option ; recherche filtrée à la frappe (mots, jokers), sous-dossiers sur Entrée ; « Sous-dossiers »
lus au plus juste avec Annuler ; STEP."""
import os
import pathlib
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QApplication

from vectordrive.core import progress as P
from vectordrive.ui import file_browser as FB
from vectordrive.ui.symbols import walk_files

app = QApplication.instance() or QApplication([])


def make_tree() -> pathlib.Path:
    d = pathlib.Path(tempfile.mkdtemp())
    for rel in ('plaque A.dxf', 'Plaque_b.vnd', 'logo.svg', 'notes.txt', 'piece.step',
                'Sous/plaque c.dxf', 'Sous/Deep/éclair.dxf', '.cache/plaque cachee.dxf'):
        f = d / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text('0\nEOF\n', encoding='ascii')
    return d


class TestMatchAndWalk(unittest.TestCase):
    def test_matcher(self):
        m = FB.matcher('PLAQUE  dxf')
        self.assertTrue(m('plaque A.dxf'))
        self.assertFalse(m('Plaque_b.vnd'))
        self.assertTrue(FB.matcher('pla*b')('Plaque_b.vnd'))
        self.assertTrue(FB.matcher('*.svg')('logo.svg'))
        self.assertTrue(FB.matcher('eclair')('Éclair.dxf'))                     # sans accents ni casse
        self.assertIsNone(FB.matcher('   '))

    def test_walk(self):
        d = make_tree()
        exts = ('.dxf', '.vnd')
        names = sorted(p.name for p in walk_files(d, exts))
        self.assertEqual(names, ['Plaque_b.vnd', 'plaque A.dxf', 'plaque c.dxf', 'éclair.dxf'])   # sans .cache
        below = sorted(p.name for p in walk_files(d, exts, below_only=True))
        self.assertEqual(below, ['plaque c.dxf', 'éclair.dxf'])
        self.assertEqual(len(walk_files(d, exts, limit=2)), 2)
        self.assertEqual([p.name for p in walk_files(d, exts, FB.matcher('eclair'))], ['éclair.dxf'])

    def test_walk_cancel_keeps_found(self):
        d = make_tree()
        task = P.Task('essai')
        token = P.attach(task)
        found = []
        real = os.scandir
        calls = []

        def scandir(path):
            calls.append(path)
            if len(calls) == 2:
                task.cancel()                                                  # annulé pendant la lecture
            return real(path)
        try:
            with mock.patch('os.scandir', side_effect=scandir), self.assertRaises(P.Cancelled):
                walk_files(d, ('.dxf', '.vnd'), out=found)
        finally:
            P.detach(token)
        self.assertGreaterEqual(len(found), 1)                                 # ce qui est lu reste


class TestBrowser(unittest.TestCase):
    def setUp(self):
        self.d = make_tree()
        self.s = QSettings(os.path.join(tempfile.mkdtemp(), 's.ini'), QSettings.Format.IniFormat)
        self.p = FB.FileBrowserPanel(self.s)
        self.p.EXTS = FB.BROWSER_EXT

    def tearDown(self):
        self.p.deleteLater()

    def rows(self):
        return [self.p.list.item(i) for i in range(self.p.list.count())]

    def visible(self):
        return [it.text() for it in self.rows() if not it.isHidden()]

    def test_details_default(self):
        self.assertEqual(self.p._view, 'details')
        self.p.show_folder(self.d)
        self.assertTrue(self.p.columns.isVisibleTo(self.p))
        self.assertIn('piece.step', self.visible())                            # STEP montré
        self.assertNotIn('notes.txt', self.visible())
        files = [it for it in self.rows() if it.data(FB.ROLE_KIND) is None]
        mtime, size, kind = files[0].data(FB.ROLE_DETAILS)[:3]
        self.assertGreater(mtime, 0)
        self.assertEqual(size, pathlib.Path(files[0].data(Qt.ItemDataRole.UserRole)).stat().st_size)
        self.assertTrue(kind)
        self.assertEqual(self.p._pending, [])                                 # aucune vignette à tracer
        dirs = [it for it in self.rows() if it.data(FB.ROLE_KIND) == 'dir']
        self.assertEqual(dirs[0].data(FB.ROLE_DETAILS)[1], None)

    def test_columns_sort(self):
        self.p.show_folder(self.d)
        got = []
        self.p.sortChanged.connect(got.append)
        self.p._column_clicked(3)                                             # Taille
        self.assertEqual(got, ['taille'])
        self.assertEqual(self.s.value(FB.SORT_KEY), 'taille')
        self.assertEqual(self.p.columns.sortIndicatorSection(), 3)
        self.assertEqual(self.p.columns.sortIndicatorOrder(), Qt.SortOrder.DescendingOrder)

    def test_filter_while_typing(self):
        self.p.show_folder(self.d)
        self.p.search.setText('plaque')
        self.p._filter_list()
        self.assertEqual(sorted(t for t in self.visible() if t != '..' and '.' in t),
                         ['Plaque_b.vnd', 'plaque A.dxf'])
        self.assertIn('Entrée', self.p.where.text())
        self.p._search()                                                      # Entrée : sous-dossiers
        self.assertEqual(sorted(self.visible()), ['Plaque_b.vnd', 'Sous/plaque c.dxf', 'plaque A.dxf'])
        self.p.search.setText('')
        self.p._filter_list()                                                 # effacée : le dossier revient
        self.assertIn('logo.svg', self.visible())
        self.p.search.setText('logo')
        self.p.show_folder(self.d / 'Sous')                                   # naviguer efface la recherche
        self.assertEqual(self.p.search.text(), '')

    def test_vignettes(self):
        self.p.set_view('vignettes')
        self.assertEqual(self.s.value(FB.VIEW_KEY), 'vignettes')
        self.p.show_folder(self.d)
        self.assertFalse(self.p.columns.isVisibleTo(self.p))
        self.assertTrue(self.p.size.isEnabled())
        self.assertGreater(len(self.p._pending) + len(self.p._jobs or []), 0)   # vignettes à tracer
        self.p.set_view('details')
        self.assertFalse(self.p.size.isEnabled())

    def test_deep_cancel(self):
        from vectordrive.ui import symbols as S

        def stopped(base, exts, match, limit, below, out, *_rest):
            out.append(base / 'Sous' / 'plaque c.dxf')
            raise P.Cancelled()                                                # Annuler pendant la lecture
        self.p.deep.setChecked(False)
        self.p.show_folder(self.d)
        with mock.patch.object(S, 'walk_files', side_effect=stopped):
            self.p.deep.setChecked(True)
        self.assertIn('arrêtée', self.p.where.text())
        self.assertIn('Sous/plaque c.dxf', self.visible())                    # ce qui est lu reste
        self.p.deep.setChecked(False)

    def test_deep(self):
        self.p.deep.setChecked(True)
        try:
            self.p.show_folder(self.d)
            self.assertIn('Sous/Deep/éclair.dxf', self.visible())
            self.assertNotIn('.cache/plaque cachee.dxf', self.visible())
        finally:
            self.p.deep.setChecked(False)

    def test_dialog_view_combo(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            dlg = w.file_browser(exec_dialog=False)
            self.assertEqual(dlg.view.currentData(), 'details')
            dlg.panel._column_clicked(1)
            self.assertEqual(dlg.sort.currentData(), 'date')
            dlg.view.setCurrentIndex(dlg.view.findData('vignettes'))
            self.assertEqual(dlg.panel._view, 'vignettes')
            dlg.view.setCurrentIndex(dlg.view.findData('details'))
            dlg.reject()
        finally:
            w.settings.setValue(FB.SORT_KEY, 'nom')                           # pas de fuite vers les autres essais
            w.settings.setValue(FB.VIEW_KEY, 'details')
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
