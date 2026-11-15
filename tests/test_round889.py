"""Round 889 : une version portable neuve, décompressée à côté de la précédente, propose à son premier lancement d'en reprendre les
réglages et les données ; rien sans réponse, rien de changé dans l'ancien dossier, la question une seule fois."""
import os
import pathlib
import shutil
import tempfile
import time
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

from vectordrive import portable as P


def make_version(box: pathlib.Path, name: str, keys=None, files=None) -> pathlib.Path:
    """Une version portable décompressée : box/name/VectorDrive/ avec l'exe, l'ini, et des fichiers de données."""
    app_dir = box / name / 'VectorDrive'
    app_dir.mkdir(parents=True)
    (app_dir / 'VectorDrive.exe').write_bytes(b'MZ')
    (app_dir / P.INI).write_text('; VectorDrive portable : réglages enregistrés ici\n', encoding='utf-8')
    if keys:
        s = QSettings(str(app_dir / P.INI), QSettings.Format.IniFormat)
        for k, v in keys.items():
            s.setValue(k, v)
        s.sync()
    for rel, text in (files or {}).items():
        f = app_dir / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding='utf-8')
    return app_dir


def keys_of(app_dir: pathlib.Path) -> dict:
    s = QSettings(str(app_dir / P.INI), QSettings.Format.IniFormat)
    return {k: s.value(k) for k in s.allKeys()}


class Base(unittest.TestCase):

    def setUp(self):
        self.box = pathlib.Path(tempfile.mkdtemp(prefix='vd889_'))
        self.env = mock.patch.dict(os.environ, {})
        self.env.start()
        os.environ.pop('VECTORDRIVE_SETTINGS', None)

    def tearDown(self):
        self.env.stop()
        shutil.rmtree(self.box, ignore_errors=True)

    def run_new(self, new: pathlib.Path):
        os.environ['VECTORDRIVE_PORTABLE_DIR'] = str(new)


class TestFind(Base):

    def test_the_version_beside_is_found(self):
        old = make_version(self.box, 'VectorDrive-0.743.0-portable', {'dossier/ouvrir': 'D:/x'})
        new = make_version(self.box, 'VectorDrive-0.744.0-portable')
        self.assertEqual(P.previous_portable(new), old)

    def test_the_most_recently_used_wins(self):
        a = make_version(self.box, 'VectorDrive-0.740.0-portable', {'a': 1})
        b = make_version(self.box, 'VectorDrive-0.743.0-portable', {'b': 1})
        new = make_version(self.box, 'VectorDrive-0.744.0-portable')
        later = time.time() + 60
        os.utime(a / P.INI, (later, later))
        self.assertEqual(P.previous_portable(new), a)
        os.utime(b / P.INI, (later + 60, later + 60))
        self.assertEqual(P.previous_portable(new), b)

    def test_an_unused_version_or_another_folder_is_not_proposed(self):
        make_version(self.box, 'VectorDrive-0.742.0-portable')               # jamais lancée : ini vide
        (self.box / 'Documents').mkdir()
        (self.box / 'Documents' / P.INI).write_text('[x]\na=1\n', encoding='utf-8')   # pas de VectorDrive.exe
        new = make_version(self.box, 'VectorDrive-0.744.0-portable')
        self.assertIsNone(P.previous_portable(new))

    def test_a_version_unzipped_without_its_folder(self):
        flat = self.box / 'ancienne'
        flat.mkdir()
        (flat / 'VectorDrive.exe').write_bytes(b'MZ')
        s = QSettings(str(flat / P.INI), QSettings.Format.IniFormat)
        s.setValue('a', 1)
        s.sync()
        new = make_version(self.box, 'VectorDrive-0.744.0-portable')
        self.assertEqual(P.previous_portable(new), flat)


class TestAdopt(Base):

    def setUp(self):
        super().setUp()
        self.old = make_version(self.box, 'VectorDrive-0.743.0-portable',
                                {'dossier/ouvrir': 'D:/dessins', 'fichiers/dossiers': ['D:/a', 'D:/b'], 'vue/theme': 'sombre'},
                                {'donnees/outils/tools.json': '{"outils": 1}', 'donnees/modeles_fao/m.json': '{}',
                                 'donnees/recuperation/r.vdz': 'ancien', 'donnees/session/index.json': '{}',
                                 'bibliotheque/logo.svg': '<svg/>'})
        self.new = make_version(self.box, 'VectorDrive-0.744.0-portable')
        self.before = {f: f.read_bytes() for f in self.old.rglob('*') if f.is_file()}

    def test_accepted_settings_and_data_come_over(self):
        self.run_new(self.new)
        asked = []
        got = P.offer_previous(lambda name: asked.append(name) or True)
        self.assertEqual(got, self.old)
        self.assertEqual(asked, ['VectorDrive-0.743.0-portable'])
        k = keys_of(self.new)
        self.assertEqual(k['dossier/ouvrir'], 'D:/dessins')
        self.assertEqual(k['fichiers/dossiers'], ['D:/a', 'D:/b'])
        self.assertEqual(k['vue/theme'], 'sombre')
        self.assertEqual(k[P.ADOPTED_KEY], 'VectorDrive-0.743.0-portable')
        self.assertTrue((self.new / 'donnees/outils/tools.json').is_file())
        self.assertTrue((self.new / 'donnees/modeles_fao/m.json').is_file())
        self.assertTrue((self.new / 'donnees/session/index.json').is_file())
        self.assertTrue((self.new / 'bibliotheque/logo.svg').is_file())
        self.assertFalse((self.new / 'donnees/recuperation').exists())          # la récupération reste à l'ancienne

    def test_the_old_folder_is_untouched(self):
        self.run_new(self.new)
        P.offer_previous(lambda name: True)
        after = {f: f.read_bytes() for f in self.old.rglob('*') if f.is_file()}
        self.assertEqual(after, self.before)

    def test_refused_nothing_comes_and_it_is_not_asked_again(self):
        self.run_new(self.new)
        self.assertIsNone(P.offer_previous(lambda name: False))
        self.assertEqual(keys_of(self.new), {P.ADOPTED_KEY: 'non'})
        self.assertFalse((self.new / 'donnees').exists())
        asked = []
        self.assertIsNone(P.offer_previous(lambda name: asked.append(name) or True))
        self.assertEqual(asked, [])

    def test_accepted_it_is_not_asked_again(self):
        self.run_new(self.new)
        P.offer_previous(lambda name: True)
        asked = []
        P.offer_previous(lambda name: asked.append(name) or True)
        self.assertEqual(asked, [])

    def test_a_file_already_there_is_never_replaced(self):
        mine = self.new / 'donnees/outils/tools.json'
        mine.parent.mkdir(parents=True)
        mine.write_text('{"les miens": 1}', encoding='utf-8')
        n = P.adopt(self.old, self.new)
        self.assertEqual(mine.read_text(encoding='utf-8'), '{"les miens": 1}')
        self.assertEqual(n, 3)                                                  # modèles, session, bibliothèque

    def test_a_used_version_is_never_asked(self):
        s = QSettings(str(self.new / P.INI), QSettings.Format.IniFormat)
        s.setValue('vue/theme', 'clair')
        s.sync()
        self.run_new(self.new)
        self.assertIsNone(P.offer_previous(lambda name: self.fail('demandé')))
        self.assertEqual(keys_of(self.new), {'vue/theme': 'clair'})

    def test_never_for_tests_or_an_installed_version(self):
        self.run_new(self.new)
        os.environ['VECTORDRIVE_SETTINGS'] = str(self.box / 'essai.ini')
        self.assertIsNone(P.offer_previous(lambda name: self.fail('demandé')))
        os.environ.pop('VECTORDRIVE_SETTINGS')
        os.environ.pop('VECTORDRIVE_PORTABLE_DIR')
        self.assertIsNone(P.offer_previous(lambda name: self.fail('demandé')))

    def test_alone_nothing_is_asked(self):
        shutil.rmtree(self.old.parent)
        self.run_new(self.new)
        self.assertIsNone(P.offer_previous(lambda name: self.fail('demandé')))
        self.assertEqual(keys_of(self.new), {})

    def test_the_question_names_the_folder_and_its_two_choices(self):
        from PySide6.QtWidgets import QMessageBox
        seen = {}

        def fake_exec(box):
            seen['text'] = box.text()
            seen['buttons'] = [b.text() for b in box.buttons()]
            seen['default'] = box.defaultButton().text()
            return 0
        with mock.patch.object(QMessageBox, 'exec', fake_exec):
            self.assertFalse(P._ask_adopt('VectorDrive-0.743.0-portable'))
        self.assertIn('VectorDrive-0.743.0-portable', seen['text'])
        self.assertEqual(sorted(seen['buttons']), ['Partir de zéro', 'Reprendre ses réglages'])
        self.assertEqual(seen['default'], 'Reprendre ses réglages')


class TestStart(unittest.TestCase):

    def test_the_program_asks_before_reading_its_settings(self):
        src = (pathlib.Path(__file__).resolve().parents[1] / 'VectorDrive.py').read_text(encoding='utf-8')
        at = src.index('portable.offer_previous()')
        self.assertLess(at, src.index('st = portable.settings()\n    apply_theme'))
        self.assertGreater(at, src.index('instance.forward(args.fichier'))   # une fenêtre déjà lancée : rien demandé


if __name__ == '__main__':
    unittest.main()
