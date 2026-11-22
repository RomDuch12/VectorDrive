"""Round 1138 (demande du 22/11, 10 h 45) : VD-convert, le convertisseur seul au menu contextuel (comme TauConvert) —
il s'installe sous le compte, retire proprement les autres versions (autre VD-convert, menu de VectorDrive, copie
déplacée) pour les remplacer, se désinstalle, convertit. Registre en mémoire : jamais le vrai registre ni le vrai
dossier des programmes."""
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1138.ini'))
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])

import tests  # noqa: E402,F401
from vectordrive import shellmenu as SM  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
BEFORE = 'avant : pas de VD-convert'
SVG = ('<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="60mm" viewBox="0 0 100 60">'
       '<rect x="10" y="10" width="80" height="40" fill="none"/></svg>')


def VC():
    try:
        from vectordrive import vdconvert
    except ImportError:
        raise AssertionError(BEFORE)
    return vdconvert


def commands(reg):
    """Toutes les commandes inscrites sous les clés de la famille."""
    return [v[1].get('') for k, v in reg.keys.items() if k.endswith('\\command') and v[1].get('')]


class Base(unittest.TestCase):

    def setUp(self):
        self.VC = VC()
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        env = mock.patch.dict(os.environ, {'VECTORDRIVE_VDCONVERT_DIR': str(self.tmp / 'installe')})
        env.start()
        self.addCleanup(env.stop)
        self.reg = self.VC.MemoryReg()

    def folder(self, name, mark=None):
        f = self.tmp / name
        f.mkdir(parents=True)
        (f / self.VC.EXE).write_bytes(b'MZ')
        (f / '_internal').mkdir()
        (f / '_internal' / 'lib.dll').write_bytes(b'x' * 100)
        if mark:
            (f / self.VC.MARK).write_text(mark, encoding='utf-8')
        return f

    def old_install(self, name='ancien', version='0.990.0', key='VD-convert'):
        f = self.folder(name, mark=version)
        self.reg.write(self.VC.UNINSTALL_ROOT + '\\' + key,
                       {'DisplayName': 'VD-convert', 'DisplayVersion': version, 'InstallLocation': str(f)})
        SM.install(write=self.reg.write, program=(str(f / self.VC.EXE), []), lots=False)
        return f


class Menu(Base):

    def test_plan_without_lots(self):
        full = dict(SM.plan(('C:/A/VectorDrive.exe', [])))
        conv = dict(SM.plan(('C:/A/VD-convert.exe', []), lots=False))
        self.assertTrue(any(k.endswith('90lots') for k in full))
        self.assertTrue(any(SM.DIR_KEY in k for k in full))
        self.assertFalse(any(k.endswith('90lots') or SM.DIR_KEY in k for k in conv))
        self.assertTrue(any('--convert' in v.get('', '') for v in conv.values()))
        SM.install(write=self.reg.write, program=('C:/A/VD-convert.exe', []), lots=False)
        self.assertTrue(SM.check(read=self.reg.read, program=('C:/A/VD-convert.exe', []), lots=False)[0])
        self.assertFalse(SM.check(read=self.reg.read, program=('C:/B/VD-convert.exe', []), lots=False)[0])

    def test_program_of(self):
        VC = self.VC
        self.assertEqual(VC.program_of('"C:\\P\\VD-convert.exe" --convert "%1" --to dxf'), 'C:\\P\\VD-convert.exe')
        self.assertEqual(VC.program_of('"C:\\Py\\pythonw.exe" "D:\\src\\VectorDrive.py" --lots "%1"'),
                         'D:\\src\\VectorDrive.py')
        self.assertTrue(VC.is_ours('C:/x/whatever.exe', 'VectorDrive.Convertir'))
        self.assertTrue(VC.is_ours('', 'Ancien', 'VectorDrive.Convertir.dxf'))
        self.assertFalse(VC.is_ours('C:/Tools/foo.exe', 'Foo.Open'))
        self.assertFalse(VC.is_ours('C:/x/VectorDrive.exe', 'Ouvrir avec VectorDrive'))   # un verbe fait à la main


class InstallReplace(Base):

    def test_replace_others(self):
        VC = self.VC
        SM.install(write=self.reg.write, program=('C:/Prog/VectorDrive/VectorDrive.exe', []))   # l'application
        old = self.old_install()
        self.reg.write(rf'{SM.CLASSES}\SystemFileAssociations\.dxf\shell\Autre.Ouvrir\command',
                       {'': '"C:\\Outils\\autre.exe" "%1"'})
        others = VC.find_others(self.reg, str(self.tmp / 'installe' / VC.EXE))
        kinds = sorted(o.kind for o in others)
        self.assertEqual(kinds, ['install', 'menu', 'menu'])
        self.assertTrue(any('VectorDrive' in o.text() and 'reste installée' in o.text() for o in others))
        self.assertTrue(any(o.version == '0.990.0' for o in others))
        src = self.folder('telechargements', mark=None)
        got = VC.install(self.reg, src, self.tmp / 'installe')
        exe = self.tmp / 'installe' / VC.EXE
        self.assertEqual(got['exe'], str(exe))
        self.assertTrue(got['copied'])
        self.assertTrue((self.tmp / 'installe' / '_internal' / 'lib.dll').is_file())
        self.assertEqual((self.tmp / 'installe' / VC.MARK).read_text(encoding='utf-8').strip(), VC.version())
        self.assertFalse(old.exists())                                             # l'ancienne installation : supprimée
        self.assertTrue(any('dossier supprimé' in r for r in got['removed']))
        cmds = [c for c in commands(self.reg) if 'autre.exe' not in c]
        self.assertTrue(cmds and all(str(exe) in c for c in cmds), cmds)           # tout appelle la nouvelle
        self.assertFalse(any('--lots' in c for c in cmds))                          # plus de traitement par lots
        self.assertIsNone(self.reg.read(rf'{SM.CLASSES}\{SM.DIR_KEY}', 'MUIVerb'))
        self.assertIn('autre.exe', self.reg.read(rf'{SM.CLASSES}\SystemFileAssociations\.dxf\shell\Autre.Ouvrir'
                                                 r'\command', ''))
        self.assertEqual(self.reg.read(VC.UNINSTALL_KEY, 'DisplayVersion'), VC.version())
        self.assertEqual(self.reg.read(VC.UNINSTALL_KEY, 'InstallLocation'), str(self.tmp / 'installe'))
        self.assertIn('--desinstaller', self.reg.read(VC.UNINSTALL_KEY, 'UninstallString'))
        self.assertEqual(VC.find_others(self.reg, str(exe)), [])                  # propre

    def test_unmarked_folder_kept(self):
        VC = self.VC
        mine = self.folder('mes_dessins', mark=None)                               # pas de marque : jamais supprimé
        (mine / 'plan.dxf').write_text('x', encoding='utf-8')
        self.reg.write(VC.UNINSTALL_ROOT + '\\VD-convert-vieux', {'DisplayName': 'VD-convert vieux',
                                                                  'InstallLocation': str(mine)})
        src = self.folder('src')
        got = VC.install(self.reg, src, self.tmp / 'installe')
        self.assertTrue((mine / 'plan.dxf').is_file())
        self.assertTrue(any('dossier laissé' in r for r in got['removed']))
        busy = self.tmp / 'occupe'
        busy.mkdir()
        (busy / 'note.txt').write_text('à moi', encoding='utf-8')
        before = dict(self.reg.keys)
        with self.assertRaises(OSError):
            VC.install(self.reg, src, busy)                                        # un dossier qui n'est pas à nous
        self.assertEqual(self.reg.keys, before)
        self.assertTrue((busy / 'note.txt').is_file())

    def test_reinstall_in_place_and_uninstall(self):
        VC = self.VC
        src = self.folder('src')
        VC.install(self.reg, src, self.tmp / 'installe')
        target = self.tmp / 'installe'
        got = VC.install(self.reg, target, target)                                 # relancé depuis l'installation
        self.assertFalse(got['copied'])
        self.assertTrue((target / VC.EXE).is_file())
        later = []
        with mock.patch.object(VC, 'running_dir', return_value=target):
            done = VC.uninstall(self.reg, target, later=later.append)
        self.assertEqual(later, [target])                                          # l'exe qui tourne : après la sortie
        self.assertTrue(any('Applications' in d for d in done))
        self.assertEqual(VC.registrations(self.reg), [])
        self.assertIsNone(self.reg.read(VC.UNINSTALL_KEY, 'DisplayName'))
        VC.install(self.reg, src, target)
        SM.install(write=self.reg.write, program=('C:/Prog/VectorDrive/VectorDrive.exe', []))  # l'appli reprend le menu
        done = VC.uninstall(self.reg, target)
        self.assertFalse(target.exists())                                          # pas l'exe qui tourne : tout de suite
        self.assertTrue(VC.registrations(self.reg))                                # le menu de VectorDrive : laissé


class Safety(Base):

    def test_foreign_and_orphans(self):
        VC = self.VC
        hand = rf'{SM.CLASSES}\SystemFileAssociations\.dxf\shell\Ouvrir avec VectorDrive'
        self.reg.write(hand + r'\command', {'': r'"C:\Prog\VectorDrive.exe" "%1"'})   # fait à la main : intouché
        orphan = rf'{SM.CLASSES}\{SM.VERB}.svg'
        self.reg.write(orphan + r'\shell\01dxf\command', {'': r'"C:\Vieux\VD-convert.exe" --convert "%1"'})
        others = VC.find_others(self.reg, str(self.tmp / 'installe' / VC.EXE))
        self.assertEqual([o.keys for o in others], [[orphan]])
        VC.install(self.reg, self.folder('src'), self.tmp / 'installe')
        self.assertIn('VectorDrive.exe', self.reg.read(hand + r'\command', ''))
        self.assertNotIn('Vieux', ' '.join(commands(self.reg)))

    def test_locked_target_changes_nothing(self):
        VC = self.VC
        SM.install(write=self.reg.write, program=('C:/Prog/VectorDrive/VectorDrive.exe', []))
        target = self.tmp / 'installe'
        VC.install(self.reg, self.folder('v1'), target)
        SM.install(write=self.reg.write, program=('C:/Prog/VectorDrive/VectorDrive.exe', []))   # l'appli reprend
        before = {k: dict(v[1]) for k, v in self.reg.keys.items()}
        real = pathlib.Path.rename

        def locked(self_, dest):
            if self_ == target:
                raise PermissionError('utilisé')
            return real(self_, dest)
        with mock.patch.object(pathlib.Path, 'rename', locked):
            with self.assertRaises(OSError):
                VC.install(self.reg, self.folder('v2'), target)
        self.assertEqual({k: dict(v[1]) for k, v in self.reg.keys.items()}, before)   # menu de VectorDrive gardé
        self.assertTrue(VC.safe_folder(target))
        self.assertFalse(target.with_name('installe.nouveau').exists())

    def test_payload_only_and_source_kept(self):
        VC = self.VC
        src = self.folder('telechargements', mark='0.990.0')        # le zip décompressé à plat, déjà marqué
        (src / 'photo_vacances.jpg').write_bytes(b'x')
        self.reg.write(VC.UNINSTALL_ROOT + '\\VD-convert', {'DisplayName': 'VD-convert',
                                                            'InstallLocation': str(src)})
        VC.install(self.reg, src, self.tmp / 'installe')
        self.assertFalse((self.tmp / 'installe' / 'photo_vacances.jpg').exists())    # seulement l'exe et _internal
        self.assertTrue((src / 'photo_vacances.jpg').is_file())                      # la source jamais supprimée
        self.assertTrue((self.tmp / 'installe' / '_internal' / 'lib.dll').is_file())

    def test_dev_uninstall(self):
        VC = self.VC
        got = VC.install(self.reg)                                                   # développement
        self.assertTrue(VC.registrations(self.reg))
        VC.uninstall(self.reg, self.tmp / 'installe', program=got['exe'])
        self.assertEqual(VC.registrations(self.reg), [])


class Robust(Base):

    def test_stage_rename_fails_rolls_back(self):
        VC = self.VC
        target = self.tmp / 'installe'
        VC.install(self.reg, self.folder('v1'), target)
        before = {k: dict(v[1]) for k, v in self.reg.keys.items()}
        real = pathlib.Path.rename

        def scanned(self_, dest):
            if self_.name.endswith('.nouveau'):
                raise PermissionError('analysé par l’antivirus')
            return real(self_, dest)
        with mock.patch.object(pathlib.Path, 'rename', scanned), mock.patch('time.sleep'):
            with self.assertRaises(OSError) as cm:
                VC.install(self.reg, self.folder('v2'), target)
        self.assertIn('rien n', str(cm.exception))
        self.assertTrue(VC.safe_folder(target))                                       # l’ancienne remise en place
        self.assertFalse(target.with_name('installe.nouveau').exists())
        self.assertFalse(target.with_name('installe.ancien').exists())
        self.assertEqual({k: dict(v[1]) for k, v in self.reg.keys.items()}, before)

    def test_wipe_keeps_folder_recognised(self):
        VC = self.VC
        f = self.folder('installe', mark='0.994.0')
        held = open(f / '_internal' / 'lib.dll', 'rb')                                # une conversion qui tourne
        try:
            VC.wipe(f)
            if (f / '_internal' / 'lib.dll').exists():                                # Windows : fichier ouvert
                self.assertTrue(VC.safe_folder(f))
        finally:
            held.close()
        VC.wipe(f)
        self.assertFalse(f.exists())
        self.assertTrue(self.tmp.exists())

    def test_leftovers_checked(self):
        VC = self.VC
        target = self.tmp / 'installe'
        stage = target.with_name('installe.nouveau')
        stage.mkdir()
        (stage / 'mes_notes.txt').write_text('à garder', encoding='utf-8')
        with self.assertRaises(OSError):
            VC.install(self.reg, self.folder('v1'), target)
        self.assertTrue((stage / 'mes_notes.txt').is_file())
        self.assertEqual(self.reg.keys, {})
        (stage / 'mes_notes.txt').unlink()
        (stage / VC.EXE).write_bytes(b'MZ')                                           # un vrai reste : repris
        VC.install(self.reg, self.tmp / 'v1', target)
        self.assertFalse(stage.exists())
        self.assertTrue(VC.safe_folder(target))
        src = self.folder('installe.ancien', mark='0.990.0')                           # lancé depuis un reste
        with self.assertRaises(OSError):
            VC.install(self.reg, src, target)
        self.assertTrue((src / VC.EXE).is_file())

    def test_busy_target_refused(self):
        VC = self.VC
        target = self.tmp / 'installe'
        VC.install(self.reg, self.folder('v1'), target)
        with mock.patch.object(VC, 'in_use', lambda _f: True):
            with self.assertRaises(OSError) as cm:
                VC.install(self.reg, self.folder('v2'), target)
        self.assertIn('utilisé', str(cm.exception))
        self.assertFalse(target.with_name('installe.nouveau').exists())
        self.assertFalse(VC.in_use(target))                                           # rien ne tourne ici

    def test_read_only_source(self):
        import stat
        VC = self.VC
        src = self.folder('partage')
        for f in (src / VC.EXE, src / '_internal' / 'lib.dll'):
            os.chmod(f, stat.S_IREAD)                                                 # copié d’un partage réseau
        target = self.tmp / 'installe'
        VC.install(self.reg, src, target)
        self.assertFalse(VC.in_use(target))                                           # lecture seule ≠ en cours
        VC.install(self.reg, src, target)                                             # réinstallation acceptée
        VC.uninstall(self.reg, target)
        self.assertFalse(target.exists())
        for f in (src / VC.EXE, src / '_internal' / 'lib.dll'):
            os.chmod(f, stat.S_IREAD | stat.S_IWRITE)

    def test_other_install_wiped_in_order(self):
        VC = self.VC
        other = self.old_install('ailleurs')
        held = open(other / '_internal' / 'lib.dll', 'rb')                            # une conversion y tourne
        try:
            VC.install(self.reg, self.folder('v2'), self.tmp / 'installe')
            if (other / '_internal' / 'lib.dll').exists():                            # Windows : fichier ouvert
                self.assertTrue(VC.safe_folder(other))                                # encore reconnu
        finally:
            held.close()
        self.assertNotIn(str(other), ' '.join(commands(self.reg)))

    def test_log_released(self):
        VC = self.VC
        logs = self.tmp / 'local' / VC.NAME
        logs.mkdir(parents=True)
        log = logs / 'VD-convert.log'
        out = open(log, 'a', encoding='utf-8')                                        # l’exe fenêtré
        old = sys.stdout, sys.stderr
        sys.stdout = sys.stderr = out
        try:
            with mock.patch.object(VC, 'log_dir', lambda: logs):
                VC.uninstall(self.reg, self.tmp / 'installe')
        finally:
            if sys.stdout is not old[0]:
                sys.stdout.close()
            sys.stdout, sys.stderr = old
        self.assertTrue(out.closed)
        self.assertFalse(logs.exists())


class Convert(Base):

    def test_convert(self):
        VC = self.VC
        src = self.tmp / 'cote.svg'
        src.write_text(SVG, encoding='utf-8')
        from vectordrive.io import registry
        for k, _lab in SM.TARGETS:
            dest, _n = VC.convert(src, k, self.tmp / 'neuf' / 'sortie')
            self.assertTrue(dest.is_file() and dest.suffix == '.' + k)
            bb = registry.open_document(str(dest)).bbox()
            self.assertAlmostEqual(bb[2] - bb[0], 80.0, delta=0.05)
        again, _n = VC.convert(src, 'dxf', self.tmp / 'neuf' / 'sortie')
        self.assertEqual(again.name, 'cote (2).dxf')                              # jamais d'écrasement
        with self.assertRaises(ValueError):
            VC.convert(src, 'vnd')

    def test_launcher(self):
        VC()
        sys.path.insert(0, str(ROOT))
        import VDConvert
        src = self.tmp / 'a.svg'
        src.write_text(SVG, encoding='utf-8')
        import contextlib
        import io
        quiet = io.StringIO()                                   # la chaîne lit la fin de la sortie des essais
        with contextlib.redirect_stdout(quiet), contextlib.redirect_stderr(quiet):
            self.assertEqual(VDConvert.main(['--convert', str(src), '--to', 'pdf', '--keep']), 0)
        self.assertIn('a.pdf', quiet.getvalue())
        self.assertTrue((self.tmp / 'a.pdf').is_file())
        bad = self.tmp / 'b.dxf'
        bad.write_text('pas un dxf', encoding='utf-8')
        with contextlib.redirect_stdout(quiet), contextlib.redirect_stderr(quiet):
            self.assertEqual(VDConvert.main(['--convert', str(bad), '--to', 'svg', '--silencieux']), 1)
        spec = (ROOT / 'VDConvert.spec').read_text(encoding='utf-8')
        for word in ("name='VD-convert'", "'anthropic'", "'openai'", "'opengl32sw'", "console=False"):
            self.assertIn(word, spec)

    def test_autotest(self):
        VC()
        env = {k: v for k, v in os.environ.items() if k not in ('VECTORDRIVE_SETTINGS',)}
        env['QT_QPA_PLATFORM'] = 'offscreen'
        env['PYTHONIOENCODING'] = 'utf-8'
        r = subprocess.run([sys.executable, 'VDConvert.py', '--autotest'], cwd=ROOT, capture_output=True, text=True,
                           encoding='utf-8', errors='replace', timeout=600, env=env)
        self.assertEqual(r.returncode, 0, r.stdout[-2000:] + r.stderr[-2000:])
        self.assertIn('5 OK, 0 échec', r.stdout)


class Window(Base):

    def test_window(self):
        VC = self.VC
        from vectordrive.ui.vdconvert_window import ConvertWindow
        SM.install(write=self.reg.write, program=('C:/Prog/VectorDrive/VectorDrive.exe', []))
        w = ConvertWindow(reg=self.reg)
        try:
            self.assertEqual(w.others.count(), 1)
            self.assertIn('Remplacer', w.install_btn.text())
            got = w.do_install(confirm=False)                                     # développement : ce script
            self.assertTrue(got['exe'].endswith('VDConvert.py'))
            self.assertEqual(w.others.count(), 0)
            self.assertEqual(w.install_btn.text(), 'Réinstaller')
            self.assertTrue(all('VDConvert.py' in c for c in commands(self.reg)))
            src = self.tmp / 'c.svg'
            src.write_text(SVG, encoding='utf-8')
            bad = self.tmp / 'd.dxf'
            bad.write_text('rien', encoding='utf-8')
            w.fmt.setCurrentIndex(w.fmt.findData('eps'))
            out = w.convert_files([str(src), str(bad)])
            self.assertEqual([p.name for p in out], ['c.eps'])
            log = w.log.toPlainText()
            self.assertIn('✓ c.svg → c.eps', log)
            self.assertIn('✗ d.dxf', log)
            self.assertGreater(len(w.guide_text()), 200)
        finally:
            w.close()
            w.deleteLater()


if __name__ == '__main__':
    unittest.main()
