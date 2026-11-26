"""Round 1161 (demande du 25/11) : « Parametres : ouverture en plein écran et ajouter section dossiers de travail (tous
les dossiers par défaut des imports exports sauve fichier sauve programme avec un champ par défaut ou le dernier
usé); »."""
import os
import pathlib
import shutil
import tempfile
import threading
import time
import types
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1161.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import QSettings, Qt  # noqa: E402
from PySide6.QtWidgets import QApplication, QFileDialog  # noqa: E402

app = QApplication.instance() or QApplication([])
BEFORE = 'avant : F10 s’ouvrait en petite fenêtre, sans dossiers de travail'
MAX = Qt.WindowState.WindowMaximized


def tmpdir() -> str:
    d = tempfile.mkdtemp()
    return d


def ini() -> QSettings:
    return QSettings(os.path.join(tempfile.mkdtemp(), 'essai.ini'), QSettings.Format.IniFormat)


def fix(st, usage, folder) -> None:
    st.setValue('dossiers_travail/' + usage, 'fixe')
    st.setValue('dossiers_travail/' + usage + '_chemin', str(folder))


class Logic(unittest.TestCase):
    """`workdirs.start_folder` : le dossier fixé s'il est là, sinon le dernier utilisé, sinon l'ancien défaut."""

    def setUp(self):
        from vectordrive.ui import workdirs
        self.WD = workdirs
        workdirs._DOWN.clear()
        self.addCleanup(workdirs._DOWN.clear)
        workdirs._ISSUED.clear()
        self.addCleanup(workdirs._ISSUED.clear)
        self.st = ini()

    def test_default_is_last_used(self):
        WD, st = self.WD, self.st
        self.assertEqual(WD.start_folder(st, 'exporter', 'repli'), 'repli')          # rien encore : l'ancien défaut
        last = tmpdir()
        st.setValue('dossier/exporter', last)
        self.assertEqual(WD.start_folder(st, 'exporter', 'repli'), last)              # d'office : le dernier utilisé
        self.assertEqual(WD.last_key('programmes'), 'dossier/programmes')
        self.assertEqual(WD.last_key('inconnu'), 'dossier/inconnu')                   # tout `_last_dir` y passe

    def test_fixed_wins_missing_falls_back(self):
        WD, st = self.WD, self.st
        last, fixed = tmpdir(), tmpdir()
        st.setValue('dossier/importer', last)
        fix(st, 'importer', fixed)
        self.assertEqual(WD.start_folder(st, 'importer', 'repli'), fixed)
        st.setValue('dossiers_travail/importer', 'dernier')                         # le dossier gardé, pas employé
        self.assertEqual(WD.start_folder(st, 'importer', 'repli'), last)
        fix(st, 'importer', os.path.join(fixed, 'absent'))                           # clé retirée, lecteur débranché
        self.assertEqual(WD.start_folder(st, 'importer', 'repli'), last)
        fix(st, 'importer', '')
        self.assertEqual(WD.start_folder(st, 'importer', 'repli'), last)

    def test_unreachable_share_never_freezes(self):
        WD, st = self.WD, self.st
        last = tmpdir()
        st.setValue('dossier/ouvrir', last)
        fix(st, 'ouvrir', r'\\serveur-absent\partage\dessins')
        gate, calls = threading.Event(), []

        def slow(p):                                     # un serveur qui ne répond pas
            calls.append(p)
            gate.wait(20)
            return True
        self.addCleanup(gate.set)
        with mock.patch.object(WD, '_isdir', slow), mock.patch.object(WD, 'REMOTE_WAIT', 0.3):
            t0 = time.monotonic()
            self.assertEqual(WD.start_folder(st, 'ouvrir', 'repli'), last)
            self.assertLess(time.monotonic() - t0, 2.0)                              # pas le délai du réseau
            t0 = time.monotonic()
            self.assertEqual(WD.start_folder(st, 'ouvrir', 'repli'), last)
            self.assertLess(time.monotonic() - t0, 0.2)                              # retenu absent : plus d'attente
        self.assertEqual(len(calls), 1)

    def test_reachable_share_is_used(self):
        WD, st = self.WD, self.st
        fix(st, 'exporter', r'\\serveur\partage\sorties')
        with mock.patch.object(WD, '_isdir', lambda p: True):
            self.assertEqual(WD.start_folder(st, 'exporter', 'repli'), r'\\serveur\partage\sorties')

    def test_pathmemory_keeps_a_fixed_folder(self):
        from vectordrive.ui import pathmemory
        WD, st, fixed, other = self.WD, self.st, tmpdir(), tmpdir()
        st.setValue(pathmemory.LAST, other)
        fix(st, 'exporter', fixed)
        given = os.path.join(WD.start_folder(st, 'exporter', 'repli'), 'piece.dxf')
        with mock.patch.object(pathmemory, '_generic', lambda p: True):              # Documents fixé, par exemple
            self.assertEqual(pathmemory.propose('cle', given, 'save', st), given)
            self.assertEqual(pathmemory.propose('cle', given, 'save', st), os.path.join(other, 'piece.dxf'))
            # (pas rendu par start_folder cette fois : un dossier générique, remplacé comme avant)

    def test_row_window_never_takes_other_fixed(self):
        from vectordrive.ui import pathmemory
        WD, st, common, desk = self.WD, self.st, tmpdir(), tmpdir()
        fix(st, 'autres', common)                                                    # Autres fixé sur T:\Commun
        st.setValue('dossier/exporter', desk)                                        # dernier export : le Bureau
        given = os.path.join(WD.start_folder(st, 'exporter', 'repli'), 'piece.dxf')
        with mock.patch.object(pathmemory, '_generic', lambda p: True):              # le Bureau : « générique »
            self.assertEqual(pathmemory.propose('export', given, 'save', st), given)  # repart du Bureau
            self.assertEqual(pathmemory.propose('ruban', 'ruban.json', 'save', st),   # sans ligne : Autres
                             os.path.join(common, 'ruban.json'))
            home = WD.start_folder(st, 'importer', desk)                              # l'ancien défaut (repli)
            self.assertEqual(pathmemory.propose('import', home, 'open', st), home)    # jamais Autres : tel quel

    def test_usage_without_row_takes_other(self):
        from vectordrive.ui import pathmemory
        WD, st, common, desk = self.WD, self.st, tmpdir(), tmpdir()
        fix(st, 'autres', common)
        st.setValue('dossier/fiche', desk)                                           # fiche : pas de ligne
        given = os.path.join(WD.start_folder(st, 'fiche', 'repli'), 'fiche.html')
        self.assertNotIn('fiche', WD.USAGES)
        with mock.patch.object(pathmemory, '_generic', lambda p: True):
            self.assertEqual(pathmemory.propose('fiche', given, 'save', st), os.path.join(common, 'fiche.html'))

    def test_down_share_held_by_root(self):
        WD, st = self.WD, self.st
        last = tmpdir()
        st.setValue('dossier/ouvrir', last)
        st.setValue('dossier/exporter', last)
        fix(st, 'ouvrir', r'\\serveur-absent\partage\dessins')
        fix(st, 'exporter', r'\\serveur-absent\partage\sorties')                      # même partage, autre dossier
        gate, calls = threading.Event(), []

        def slow(p):
            calls.append(p)
            gate.wait(20)
            return True
        self.addCleanup(gate.set)
        with mock.patch.object(WD, '_isdir', slow), mock.patch.object(WD, 'REMOTE_WAIT', 0.3):
            self.assertEqual(WD.start_folder(st, 'ouvrir', 'repli'), last)
            t0 = time.monotonic()
            self.assertEqual(WD.start_folder(st, 'exporter', 'repli'), last)
            self.assertLess(time.monotonic() - t0, 0.2)                              # le partage : plus d'attente
        self.assertEqual(len(calls), 1)
        self.assertEqual(WD.share_root(r'T:\Commun\x'), 't:')
        with mock.patch.object(WD, '_isdir', lambda p: False):                       # le partage répond : il manque
            fix(st, 'bat', r'\\serveur\autre\absent')                                 # un dossier, pas le partage
            self.assertEqual(WD.start_folder(st, 'bat', 'repli'), 'repli')
            self.assertNotIn(WD.share_root(r'\\serveur\autre\absent'), WD._DOWN)

    def test_is_fixed_path_one_row(self):
        WD, st, fixed = self.WD, self.st, tmpdir()
        fix(st, 'exporter', fixed)
        self.assertTrue(WD.is_fixed_path(st, os.path.join(fixed, 'a.dxf'), 'exporter'))
        self.assertTrue(WD.is_fixed_path(st, fixed, 'exporter'))
        self.assertFalse(WD.is_fixed_path(st, os.path.join(fixed, 'a.dxf'), 'importer'))   # une autre ligne

    def test_clean_path(self):
        WD = self.WD
        here = tmpdir()
        self.assertEqual(WD.clean_path(f'  "{here}" '), (os.path.normpath(here), True))   # copié de l'Explorateur
        self.assertEqual(WD.clean_path(''), ('', True))
        self.assertFalse(WD.clean_path('dessins')[1])                                   # relatif : refusé
        self.assertFalse(WD.clean_path('%VD_VARIABLE_INCONNUE%\\a')[1])                 # (relatif)
        pct = os.path.join(here, '100%')
        self.assertEqual(WD.clean_path(pct), (os.path.normpath(pct), True))             # un « % » du nom : gardé
        with mock.patch.dict(os.environ, {'VD_ESSAI_DOSSIER': here}):
            self.assertEqual(WD.clean_path('%VD_ESSAI_DOSSIER%'), (os.path.normpath(here), True))
        p, ok = WD.clean_path('~')
        self.assertTrue(ok and os.path.isabs(p))                                       # (sans regarder le disque)
        st = self.st
        fix(st, 'exporter', 'dessins')                                                 # écrit à la main : ignoré
        st.setValue('dossier/exporter', here)
        self.assertEqual(WD.start_folder(st, 'exporter', 'repli'), here)

    def test_late_answer_clears_down(self):
        WD, st = self.WD, self.st
        last, share = tmpdir(), r'\\serveur-lent\partage'
        st.setValue('dossier/ouvrir', last)
        fix(st, 'ouvrir', share)
        gate = threading.Event()

        def slow(p):                                     # répond, mais trop tard pour la première fenêtre
            gate.wait(20)
            return True
        self.addCleanup(gate.set)
        with mock.patch.object(WD, '_isdir', slow), mock.patch.object(WD, 'REMOTE_WAIT', 0.2):
            self.assertEqual(WD.start_folder(st, 'ouvrir', 'repli'), last)
            gate.set()
            end = time.monotonic() + 3
            while os.path.normcase(share) in WD._DOWN and time.monotonic() < end:
                time.sleep(0.02)
            self.assertEqual(WD.start_folder(st, 'ouvrir', 'repli'), share)            # de nouveau proposé

    def test_other_dialogs_fixed_folder(self):
        from vectordrive.ui import pathmemory
        st, fixed, other = self.st, tmpdir(), tmpdir()
        st.setValue(pathmemory.LAST, other)
        self.assertEqual(pathmemory.propose('ruban', 'ruban.json', 'save', st), os.path.join(other, 'ruban.json'))
        fix(st, 'autres', fixed)
        self.assertEqual(pathmemory.propose('ruban', 'ruban.json', 'save', st), os.path.join(fixed, 'ruban.json'))
        self.assertEqual(pathmemory.propose('ruban', '', 'dir', st), fixed)
        pathmemory.remember('ruban', os.path.join(other, 'a.json'), 'save', st)     # le dernier : toujours retenu
        self.assertEqual(st.value(pathmemory.LAST), other)

    def test_plugin_adds_a_row(self):
        from vectordrive import plugins
        from vectordrive.ui import options
        WD = self.WD

        def gone():
            WD.USAGES.pop('essai_clients', None)
            options.BY_KEY.pop('dossiers_travail/essai_clients', None)
            rows = dict(options.SPEC)[options.WORKDIRS]
            rows[:] = [o for o in rows if o.key != 'dossiers_travail/essai_clients']
        self.addCleanup(gone)
        api = plugins.Api(plugins.REGISTRY, plugins.PluginInfo('essai'))
        api.add_work_folder('essai_clients', 'Dossiers clients (essai)', last_key='essai/dernier_client')
        self.assertIn('essai_clients', WD.USAGES)
        self.assertIn('dossiers_travail/essai_clients', options.BY_KEY)
        keys = [o.key for o in dict(options.SPEC)[options.WORKDIRS]]
        self.assertEqual(keys[-1], 'dossiers_travail/essai_clients')                 # en bout de section
        last = tmpdir()
        self.st.setValue('essai/dernier_client', last)
        self.assertEqual(WD.start_folder(self.st, 'essai_clients', 'repli'), last)
        api.add_work_folder('essai_clients', 'Dossiers clients (essai)')             # pas de doublon
        keys = [o.key for o in dict(options.SPEC)[options.WORKDIRS]]
        self.assertEqual(keys.count('dossiers_travail/essai_clients'), 1)


class Window(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from vectordrive.ui.main_window import MainWindow
        cls.w = MainWindow()
        if not cls.w.docs:
            cls.w.new_document()

    @classmethod
    def tearDownClass(cls):
        cls.w.modified = False
        cls.w.close()
        cls.w.deleteLater()
        app.processEvents()

    def setUp(self):
        from vectordrive.ui.options import BY_KEY
        st = self.w.settings
        every = list(BY_KEY) + [f'dossier/{k}' for k in ('ouvrir', 'enregistrer', 'importer', 'exporter',
                                                          'programmes', 'import_outils')]
        saved = {k: st.value(k) for k in every if st.contains(k)}

        def back():
            for k in every + [k for k in st.allKeys() if k.startswith('dossiers_travail/')]:
                st.remove(k)
            for k, v in saved.items():
                st.setValue(k, v)
        self.addCleanup(back)
        try:
            from vectordrive.ui import workdirs
        except ImportError:                              # l'arbre d'avant : les essais échouent sur leur propre vérif
            return
        workdirs._DOWN.clear()
        workdirs._ISSUED.clear()
        self.addCleanup(workdirs._ISSUED.clear)

    def test_options_open_maximized_close_and_reopen(self):
        from vectordrive.ui.options import SPEC, OptionsDialog
        w = self.w
        dlg = w.options_dialog(exec_dialog=False)
        self.assertTrue(dlg.windowState() & MAX, BEFORE)
        self.assertEqual(dlg.tabs.count(), len(SPEC))
        dlg.show()
        app.processEvents()
        self.assertTrue(dlg.isMaximized())
        avail = dlg.screen().availableGeometry()
        self.assertGreaterEqual(dlg.frameGeometry().width(), avail.width() - 2)        # tout l'écran
        dlg.reject()
        app.processEvents()
        self.assertFalse(dlg.isVisible())                                              # fermée
        again = w.options_dialog(exec_dialog=False, page='FAO')
        again.show()
        app.processEvents()
        self.assertTrue(again.isMaximized())                                           # rouverte, encore maximisée
        self.assertEqual(again.tabs.tabText(again.tabs.currentIndex()), 'FAO')
        again.reject()
        app.processEvents()
        seen = []

        def fake_exec(self_):
            seen.append(bool(self_.windowState() & MAX))
            return 0
        with mock.patch.object(OptionsDialog, 'exec', fake_exec):
            third = w.options_dialog()                                                 # F10 (sans vraie fenêtre)
        self.assertEqual(seen, [True])
        third.deleteLater()                                       # (les deux fermées sont libérées : fit.release)
        app.processEvents()

    def test_workdirs_page(self):
        from vectordrive.ui import options, workdirs as WD
        w = self.w
        self.assertIn('Dossiers de travail', options.PAGES, BEFORE)
        self.assertIn('options_dossiers', w.A)                                          # bouton de l'onglet Options
        dlg = w.options_dialog(exec_dialog=False, page='Dossiers de travail')
        self.addCleanup(dlg.deleteLater)
        self.assertEqual(dlg.tabs.tabText(dlg.tabs.currentIndex()), 'Dossiers de travail')
        for usage in ('ouvrir', 'enregistrer', 'importer', 'exporter', 'programmes', 'bat', 'autres'):
            r = dlg.widgets[WD.mode_key(usage)]
            self.assertEqual(r.mode.currentData(), WD.LAST, usage)                       # d'office : comme avant
            self.assertEqual(r.edit.text(), '')
            self.assertTrue(r.browse.text() and r.reset.text())
        self.assertGreater(dlg.filter_options('programme'), 0)                           # la recherche les trouve

    def test_row_choose_accept_reopen_reset(self):
        from vectordrive.ui import workdirs as WD
        w, st = self.w, self.w.settings
        fixed, last = tmpdir(), tmpdir()
        st.setValue('dossier/exporter', last)
        dlg = w.options_dialog(exec_dialog=False, page='Dossiers de travail')
        r = dlg.widgets[WD.mode_key('exporter')]
        self.assertIn(last, r.edit.placeholderText())                                    # le dernier utilisé, montré
        with mock.patch.object(QFileDialog, 'getExistingDirectory', return_value=fixed) as ask:
            r.browse.click()
        self.assertEqual(ask.call_args[0][2], last)                                       # la boîte part du dernier
        self.assertEqual((r.edit.text(), r.mode.currentData()), (fixed, WD.FIXED))
        dlg.accept()
        self.assertEqual(st.value('dossiers_travail/exporter'), 'fixe')
        self.assertEqual(st.value('dossiers_travail/exporter_chemin'), fixed)
        self.assertFalse(st.contains('dossiers_travail/importer_chemin'))                # rien d'écrit pour les autres
        self.assertEqual(w._last_dir('exporter'), fixed)
        dlg2 = w.options_dialog(exec_dialog=False, page='Dossiers de travail')
        r2 = dlg2.widgets[WD.mode_key('exporter')]
        self.assertEqual((r2.edit.text(), r2.mode.currentData()), (fixed, WD.FIXED))     # rouverte : retrouvé
        r2.reset.click()
        self.assertEqual((r2.edit.text(), r2.mode.currentData()), ('', WD.LAST))         # revenu à l'origine
        r3 = dlg2.widgets[WD.mode_key('importer')]
        r3.edit.textEdited.emit('D:/ailleurs')
        self.assertEqual(r3.mode.currentData(), WD.FIXED)                                 # un dossier écrit : fixé
        r3.edit.setText('')
        dlg2.accept()
        self.assertFalse(st.contains('dossiers_travail/exporter_chemin'))
        self.assertEqual(w._last_dir('exporter'), last)

    def test_file_dialogs_start_in_fixed_folder(self):
        w, st = self.w, self.w.settings
        imp, enr, exp, last = tmpdir(), tmpdir(), tmpdir(), tmpdir()
        fix(st, 'importer', imp)
        fix(st, 'enregistrer', enr)
        fix(st, 'exporter', exp)
        got = {}

        def ask(name):
            def f(*args, **kw):
                got[name] = str(args[2])
                return '', ''
            return f
        with mock.patch.object(QFileDialog, 'getOpenFileName', ask('open')), \
                mock.patch.object(QFileDialog, 'getSaveFileName', ask('save')):
            w.import_dialog()
            self.assertEqual(got['open'], imp, BEFORE)
            w.save_as()
            self.assertIn(pathlib.Path(enr), (pathlib.Path(got['save']), pathlib.Path(got['save']).parent))
            w.export_whole_dialog()
            self.assertEqual(got['save'], exp)
            shutil.rmtree(imp)                                                           # dossier fixé disparu
            st.setValue('dossier/importer', last)
            w.import_dialog()
            self.assertEqual(got['open'], last)                                          # le dernier utilisé

    def test_last_used_still_remembered(self):
        w, st = self.w, self.w.settings
        fixed, other = tmpdir(), tmpdir()
        fix(st, 'exporter', fixed)
        w._remember_dir('exporter', os.path.join(other, 'piece.dxf'))
        self.assertEqual(st.value('dossier/exporter'), other)
        self.assertEqual(w._last_dir('exporter'), fixed)
        st.setValue('dossiers_travail/exporter', 'dernier')
        self.assertEqual(w._last_dir('exporter'), other)

    def test_program_folder(self):
        w, st = self.w, self.w.settings
        p = w.cam_panel
        drawing, prog = tmpdir(), tmpdir()
        w.path = os.path.join(drawing, 'plaque.vnd')
        self.addCleanup(setattr, w, 'path', None)
        self.assertEqual(p.program_dir(), pathlib.Path(drawing))                           # d'office : comme avant
        fix(st, 'programmes', prog)
        self.assertEqual(p.program_dir(), pathlib.Path(prog), BEFORE)                      # toujours ce dossier
        fix(st, 'programmes', os.path.join(prog, 'absent'))
        self.assertEqual(p.program_dir(), pathlib.Path(drawing))                           # absent : comme avant

    def test_tool_import_start(self):
        from vectordrive.ui.toollib_dialog import ToolLibraryDialog
        w, st = self.w, self.w.settings
        fake = types.SimpleNamespace(parent=lambda: w)
        last, fixed = tmpdir(), tmpdir()
        st.setValue('dossier/import_outils', last)
        self.assertEqual(ToolLibraryDialog._import_start(fake), last)
        fix(st, 'import_outils', fixed)
        self.assertEqual(ToolLibraryDialog._import_start(fake), fixed)

    def test_program_folder_not_taken_by_other(self):
        from vectordrive.ui import pathmemory
        w, st = self.w, self.w.settings
        common, last = tmpdir(), tmpdir()
        fix(st, 'autres', common)
        st.setValue('dossier/programmes', last)
        w.path = None
        given = str(w.cam_panel.program_dir() / 'piece.simpl')
        with mock.patch.object(pathmemory, '_generic', lambda p: True):
            self.assertEqual(pathmemory.propose('programme', given, 'save', st), given)   # pas « Autres »
            self.assertEqual(pathmemory.propose('fiche', 'a.json', 'save', st),            # sans ligne : Autres
                             os.path.join(common, 'a.json'), BEFORE)

    def test_row_paths_cleaned_and_checked(self):
        from PySide6.QtWidgets import QDialog
        from vectordrive.ui import workdirs as WD
        w, st = self.w, self.w.settings
        good, other = tmpdir(), tmpdir()
        dlg = w.options_dialog(exec_dialog=False, page='Dossiers de travail')
        exp, imp, bat = (dlg.widgets[WD.mode_key(u)] for u in ('exporter', 'importer', 'bat'))
        exp.edit.textEdited.emit(f'"{good}"')                                          # collé de l'Explorateur
        exp.edit.setText(f'"{good}"')
        imp.edit.setText('dessins')                                                    # pas un chemin complet
        imp.mode.setCurrentIndex(imp.mode.findData(WD.FIXED))
        dlg.search.setText('zzzz introuvable')                                          # une recherche en cours
        dlg.accept()
        self.assertNotEqual(dlg.result(), QDialog.DialogCode.Accepted)                  # OK refusé
        self.assertEqual(dlg.search.text(), '')                                         # recherche vidée :
        self.assertEqual(dlg.tabs.tabText(dlg.tabs.currentIndex()), 'Dossiers de travail')
        form = dlg._rows[[r[2] for r in dlg._rows].index(imp)][1]
        self.assertTrue(form.isRowVisible(imp))                                         # la ligne se voit
        self.assertFalse(imp.warn.isHidden())                                           # dit en rouge sur la ligne
        self.assertTrue(exp.warn.isHidden())
        self.assertFalse(st.contains('dossiers_travail/exporter_chemin'))              # rien d'écrit
        with mock.patch.dict(os.environ, {'VD_ESSAI_DOSSIER': other}):
            imp.edit.setText('%VD_ESSAI_DOSSIER%')
            bat.edit.setText(os.path.join(good, 'absent'))                              # lecteur débranché
            bat.mode.setCurrentIndex(bat.mode.findData(WD.FIXED))
            dlg.accept()
            self.assertNotEqual(dlg.result(), QDialog.DialogCode.Accepted)              # absent : signalé d'abord
            self.assertFalse(bat.warn.isHidden())
            self.assertTrue(imp.warn.isHidden())
            dlg.accept()                                                                # OK de nouveau : gardé
        self.assertEqual(dlg.result(), QDialog.DialogCode.Accepted)
        self.assertEqual(st.value('dossiers_travail/exporter_chemin'), os.path.normpath(good))   # sans guillemets
        self.assertEqual(st.value('dossiers_travail/importer_chemin'), os.path.normpath(other))  # développé
        self.assertEqual(st.value('dossiers_travail/bat_chemin'), os.path.join(good, 'absent'))
        dlg2 = w.options_dialog(exec_dialog=False, page='Dossiers de travail')
        self.addCleanup(dlg2.deleteLater)
        r = dlg2.widgets[WD.mode_key('exporter')]
        self.assertEqual(r.mode.currentData(), WD.FIXED)
        r.edit.clear()
        r.edit.textEdited.emit('')                                                      # vidé au clavier
        self.assertEqual(r.mode.currentData(), WD.LAST)

    def test_restore_defaults_skips_only_late_rows(self):
        from vectordrive.ui import options
        dlg = self.w.options_dialog(exec_dialog=False)
        self.addCleanup(dlg.deleteLater)
        late = options.Opt('dossiers_travail/essai_tard', 'Tard', 'workdir', 'dernier', extra={'usage': 'essai_tard'})
        with mock.patch.dict(options.BY_KEY, {late.key: late}):
            dlg.restore_defaults()                                                      # ligne venue après : sautée
        other = options.B('essai/tard', 'Tard', False)
        with mock.patch.dict(options.BY_KEY, {other.key: other}):
            with self.assertRaises(KeyError):                                           # le reste : pas caché
                dlg.restore_defaults()

    def test_restored_window_widens_again(self):
        from vectordrive.ui import fit
        dlg = self.w.options_dialog(exec_dialog=False)
        dlg.show()
        for _ in range(3):
            app.processEvents()
        self.assertTrue(dlg.isMaximized())
        with mock.patch.object(fit, 'widen', return_value=0) as widen:
            dlg.setWindowState(Qt.WindowState.WindowNoState)                            # « Restaurer »
            for _ in range(3):
                app.processEvents()
        self.assertFalse(dlg.isMaximized())
        self.assertTrue(any(c.args and c.args[0] is dlg for c in widen.call_args_list))
        dlg.reject()
        app.processEvents()


if __name__ == '__main__':
    unittest.main()
