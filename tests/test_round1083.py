"""Round 1083 (demande du 18/11 soir) : « tout appli : un chemin file/folder précis est retenu pour la prochaine fois » ;
« Ruban fichier se masque sans volonté user : bouton plier/replier discret seul acteur »."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1083.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication, QFileDialog  # noqa: E402

app = QApplication.instance() or QApplication([])
BEFORE = 'avant : chaque fenêtre de fichier rouvrait là où le code le voulait, pas là où l\'on avait choisi'


class Fake:
    """La fenêtre de Qt remplacée : elle note le chemin proposé et rend celui qu'on lui donne."""

    def __init__(self):
        self.seen = []
        self.answer = None

    def __call__(self, *args, **kw):
        self.seen.append(args[2] if len(args) > 2 else kw.get('dir', ''))
        return self.answer


class PathMemory(unittest.TestCase):

    def setUp(self):
        try:
            from vectordrive.ui import pathmemory as M
        except ImportError:
            self.fail(BEFORE)
        self.M = M
        self.assertTrue(M.install())
        self.saved = {k: M.original(k) for k in M._KINDS}
        self.addCleanup(self.restore)
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.a, self.b = self.tmp / 'clients' / 'A', self.tmp / 'exports'
        for d in (self.a, self.b):
            d.mkdir(parents=True)
        from vectordrive.portable import settings
        st = settings()
        for k in st.allKeys():
            if k.startswith(M.PREFIX):
                st.remove(k)

    def restore(self):
        for k, f in self.saved.items():
            getattr(QFileDialog, self.M._KINDS[k]).vd_orig = f

    def fake(self, kind):
        f = Fake()
        getattr(QFileDialog, self.M._KINDS[kind]).vd_orig = f
        return f

    def open_drawing(self, start=''):
        return QFileDialog.getOpenFileName(None, 'Ouvrir un dessin', start, 'VND (*.vnd)')

    def export(self, start):
        return QFileDialog.getSaveFileName(None, 'Exporter', start, 'DXF (*.dxf)')

    def test_open_reopens_where_one_chose(self):
        f = self.fake('open')
        f.answer = (str(self.a / 'plaque.vnd'), 'VND (*.vnd)')
        self.assertEqual(self.open_drawing(), f.answer)
        f.answer = ('', '')
        self.open_drawing()
        self.assertEqual(pathlib.Path(f.seen[-1]), self.a, BEFORE)
        self.open_drawing(str(pathlib.Path.home()))                          # le dossier personnel, proposé faute de
        self.assertEqual(pathlib.Path(f.seen[-1]), self.a)                   # mieux : le dernier choix l'emporte

    def test_a_folder_the_code_means_is_kept(self):
        f = self.fake('save')
        f.answer = (str(self.a / 'p.simpl'), '')
        self.export('p.simpl')
        f.answer = ('', '')
        self.export(str(self.b / 'B.simpl'))                                 # le dossier du dessin B, voulu par le code
        self.assertEqual(pathlib.Path(f.seen[-1]), self.b / 'B.simpl', 'le programme de B ne part pas chez A')
        fd = self.fake('dir')
        fd.answer = str(self.a)
        QFileDialog.getExistingDirectory(None, 'Choisir un dossier', '')
        fd.answer = ''
        QFileDialog.getExistingDirectory(None, 'Choisir un dossier', str(self.b))   # la valeur du champ
        self.assertEqual(pathlib.Path(fd.seen[-1]), self.b)
        fo = self.fake('open')
        fo.answer = ('', '')
        QFileDialog.getOpenFileName(None, 'Choisir un fichier', str(self.b / 'x.txt'))   # un fichier qui n'existe pas
        self.assertEqual(pathlib.Path(fo.seen[-1]), self.b / 'x.txt')                     # dans un dossier qui existe

    def test_a_network_share_is_not_tested(self):
        from unittest import mock
        share = '\\\\serveur-absent\\partage\\Programmes'
        with mock.patch('os.path.isdir', side_effect=AssertionError('testé : l\'interface gèlerait')), \
                mock.patch('os.path.exists', side_effect=AssertionError('testé')):
            self.assertEqual(self.M.propose('k', share, 'dir'), share)
            self.assertTrue(self.M._usable(share))

    def test_cancel_keeps_the_folder(self):
        f = self.fake('open')
        f.answer = (str(self.a / 'x.vnd'), '')
        self.open_drawing()
        f.answer = ('', '')
        self.open_drawing()
        self.open_drawing()
        self.assertEqual(pathlib.Path(f.seen[-1]), self.a)

    def test_save_keeps_the_proposed_name(self):
        f = self.fake('save')
        f.answer = (str(self.b / 'premier.dxf'), '')
        self.export(str(self.tmp / 'nouveau' / 'plaque.dxf'))
        f.answer = ('', '')
        self.export('plaque 2.dxf')                                          # un nom nu : dans le dossier retenu
        self.assertEqual(pathlib.Path(f.seen[-1]), self.b / 'plaque 2.dxf')
        self.export(str(self.tmp / 'parti' / 'plaque 3.dxf'))                # un dossier qui n'existe pas : idem
        self.assertEqual(pathlib.Path(f.seen[-1]), self.b / 'plaque 3.dxf')

    def test_each_window_has_its_folder(self):
        fo, fs = self.fake('open'), self.fake('save')
        fo.answer = (str(self.a / 'p.vnd'), '')
        self.open_drawing()
        fs.answer = (str(self.b / 'e.dxf'), '')
        self.export('e.dxf')
        fo.answer = fs.answer = ('', '')
        self.open_drawing()
        self.export('f.dxf')
        self.assertEqual(pathlib.Path(fo.seen[-1]), self.a)
        self.assertEqual(pathlib.Path(fs.seen[-1]), self.b / 'f.dxf')

    def test_a_new_window_starts_at_the_last_folder(self):
        f = self.fake('open')
        f.answer = (str(self.b / 'q.vnd'), '')
        self.open_drawing()
        g = self.fake('open_many')
        g.answer = ([], '')
        QFileDialog.getOpenFileNames(None, 'Images', '', 'PNG (*.png)')
        self.assertEqual(pathlib.Path(g.seen[-1]), self.b)                   # jamais ouverte : le dernier dossier
        g.answer = ([str(self.a / '1.png'), str(self.a / '2.png')], '')
        QFileDialog.getOpenFileNames(None, 'Images', '', 'PNG (*.png)')
        g.answer = ([], '')
        QFileDialog.getOpenFileNames(None, 'Images', '', 'PNG (*.png)')
        self.assertEqual(pathlib.Path(g.seen[-1]), self.a)

    def test_folders(self):
        f = self.fake('dir')
        f.answer = str(self.b)
        QFileDialog.getExistingDirectory(None, 'Dossier des programmes', '')
        f.answer = ''
        QFileDialog.getExistingDirectory(None, 'Dossier des programmes', str(pathlib.Path.home()))
        self.assertEqual(pathlib.Path(f.seen[-1]), self.b)
        QFileDialog.getExistingDirectory(None, 'Dossier des programmes')     # deux arguments seulement
        self.assertEqual(pathlib.Path(f.seen[-1]), self.b)

    def test_a_folder_gone_is_not_proposed(self):
        import shutil
        f = self.fake('open')
        gone = self.tmp / 'usb'
        gone.mkdir()
        f.answer = (str(gone / 'a.vnd'), '')
        self.open_drawing()
        shutil.rmtree(gone)
        f.answer = ('', '')
        self.open_drawing(str(self.a))
        self.assertEqual(pathlib.Path(f.seen[-1]), self.a)

    def test_a_test_fake_does_not_stay_behind(self):
        from unittest import mock
        wrapper = QFileDialog.getOpenFileName
        real = self.M.original('open')
        with mock.patch.object(QFileDialog, 'getOpenFileName', return_value=('', '')):
            self.M.install()                                                 # posée par-dessus le faux
            self.assertTrue(getattr(QFileDialog.getOpenFileName, 'vd_pathmemory', False))
        self.assertIs(QFileDialog.getOpenFileName, wrapper)                 # remise : l'enveloppe et sa vraie fenêtre
        self.assertIs(self.M.original('open'), real)

    def test_the_window_installs_it(self):
        from vectordrive.ui.main_window import MainWindow
        self.M.uninstall()                                                   # (setUp l'a posée : la fenêtre la repose)
        self.assertFalse(self.M.installed())
        w = MainWindow()
        try:
            self.assertTrue(self.M.installed())
            self.assertTrue(getattr(QFileDialog.getSaveFileName, 'vd_pathmemory', False))
        finally:
            w.modified = False
            w.close()
            w.deleteLater()


class Ribbon(unittest.TestCase):

    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.w.resize(1400, 900)
        self.w.show()
        app.processEvents()
        self.r = self.w.ribbon
        self.addCleanup(self.close)

    def close(self):
        self.w.A['ribbon_collapse'].setChecked(False)
        self.w.modified = False
        self.w.close()
        self.w.deleteLater()
        app.processEvents()

    def test_double_click_no_longer_folds(self):
        r = self.r
        full = r.height()
        r.tabBarDoubleClicked.emit(r.currentIndex())
        app.processEvents()
        self.assertFalse(r.collapsed, 'avant : un double clic sur un onglet pliait le ruban')
        self.assertEqual(r.height(), full)
        r.right_bar.tabBarDoubleClicked.emit(0)
        self.assertFalse(r.collapsed)

    def test_the_button_folds_and_unfolds(self):
        r = self.r
        self.assertTrue(hasattr(r, 'fold_btn'), 'avant : pas de bouton pour plier le ruban')
        self.assertTrue(r.fold_btn.isVisible())
        full = r.height()
        r.fold_btn.click()
        self.assertTrue(r.collapsed)
        self.assertLess(r.height(), full / 2)
        self.assertEqual(r.fold_btn.text(), '˅')
        self.assertTrue(self.w.A['ribbon_collapse'].isChecked())            # la commande suit
        self.assertIn(self.w.settings.value('vue/ruban_reduit'), (True, 'true'))
        r.fold_btn.click()
        self.assertFalse(r.collapsed)
        self.assertGreater(r.height(), full * 0.9)                          # déplié (Qt recalcule sa hauteur)
        self.assertEqual(r.fold_btn.text(), '˄')

    def test_ctrl_f1_and_the_button_agree(self):
        r = self.r
        self.w.A['ribbon_collapse'].trigger()                               # Ctrl+F1
        self.assertTrue(r.collapsed)
        self.assertEqual(r.fold_btn.text(), '˅')
        self.assertFalse(r.fold_btn.autoRaise())                            # plié : un vrai bouton, visible
        self.w.A['ribbon_collapse'].trigger()
        self.assertFalse(r.collapsed)
        self.assertEqual(r.fold_btn.text(), '˄')

    def test_a_folded_ribbon_stays_folded(self):
        r = self.r
        r.fold_btn.click()
        low = r.height()
        other = next(i for i in range(r.count()) if i != r.currentIndex() and r.isTabVisible(i))
        r.tabBarClicked.emit(other)
        r.setCurrentIndex(other)
        app.processEvents()
        self.assertEqual(r.height(), low, 'avant : un clic d\'onglet l\'ouvrait, une commande le refermait')
        r._command_done()
        self.assertEqual(r.height(), low)
        self.assertTrue(r.collapsed)


if __name__ == '__main__':
    unittest.main()
