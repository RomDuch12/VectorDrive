"""Round 1124 (demande du 20/11, 16 h 08) : « Assistant IA peut enregistrer des copies de fichier (sans pouvoir écraser
ce qui n'est pas de lui, mais peut ecraser ce qu'il a fait lui) »."""
import json
import os
import pathlib
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1124.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])

import tests  # noqa: E402,F401
from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Shape  # noqa: E402

BEFORE = 'avant : l’assistant n’enregistrait rien'


class Copies(unittest.TestCase):

    def setUp(self):
        from vectordrive.agent import tools as T
        from vectordrive.ui.main_window import MainWindow
        self.T = T
        self.base = pathlib.Path(tempfile.mkdtemp())
        env = mock.patch.dict(os.environ, {'VECTORDRIVE_ASSISTANT_DIR': str(self.base / 'assistant')})
        env.start()
        self.addCleanup(env.stop)
        self.w = MainWindow()
        self.addCleanup(self.clean)
        self.tools = T.ToolSet(self.w, extended=True)
        for name in ('save_copy', 'list_copies'):
            self.assertIn(name, self.tools.names(), BEFORE)
        self.sh = Shape(path=geom.Path([geom.rect(0, 0, 20, 10)]), tool=0)
        self.w.canvas.doc.add(self.sh)
        self.folder = self.base / 'assistant' / 'copies'

    def clean(self):
        self.w.modified = False
        self.w.close()
        self.w.deleteLater()
        app.processEvents()

    def call(self, tool, **args):
        return json.loads(self.tools.call(tool, args)[0]['text'])

    def refused(self, tool, **args):
        from vectordrive.agent.protocol import ToolError
        with self.assertRaises(ToolError) as cm:
            self.tools.call(tool, args)
        return str(cm.exception)

    def shapes_in(self, path):
        from vectordrive.io import registry
        doc = registry.open_document(str(path))
        return sum(len(L.items) for L in doc.layers)

    def leftovers(self):
        return [p.name for p in self.folder.iterdir() if p.name.startswith('.~')] if self.folder.exists() else []

    def test_copy_written_drawing_untouched(self):
        self.w.path, self.w.modified = None, True
        got = self.call('save_copy', name='Essai copie')
        p = pathlib.Path(got['saved'])
        self.assertEqual(p, self.folder / 'Essai copie.vdz')
        self.assertTrue(p.is_file())
        self.assertEqual((got['format'], got['replaced']), ('vdz', False))
        self.assertEqual(self.shapes_in(p), 1)
        self.assertEqual((self.w.path, self.w.modified), (None, True), 'le dessin ouvert reste tel quel')
        reg = self.T.copies_registry()
        self.assertTrue(self.T.own_copy(p, reg), 'retenue comme sienne')
        self.assertEqual(self.leftovers(), [], 'pas de fichier provisoire laissé')

    def test_never_over_a_foreign_file(self):
        self.folder.mkdir(parents=True)
        foreign = self.folder / 'Plaque.vdz'
        foreign.write_bytes(b'le fichier de l utilisateur')
        for over in (False, True):
            self.assertIn('not one of your copies', self.refused('save_copy', name='Plaque', overwrite=over))
        self.assertEqual(foreign.read_bytes(), b'le fichier de l utilisateur')
        self.assertEqual(self.leftovers(), [])

    def test_own_copy_replaced_on_demand(self):
        p = pathlib.Path(self.call('save_copy', name='Mienne')['saved'])
        self.assertIn('"overwrite": true', self.refused('save_copy', name='Mienne'))
        self.w.canvas.doc.add(Shape(path=geom.Path([geom.rect(30, 0, 5, 5)]), tool=0))
        got = self.call('save_copy', name='Mienne', overwrite=True)
        self.assertTrue(got['replaced'])
        self.assertEqual(self.shapes_in(p), 2, 'remplacée par le dessin d’aujourd’hui')
        self.assertTrue(self.T.own_copy(p), 'toujours sienne (nouvelle empreinte)')

    def test_own_copy_changed_by_the_user_is_no_longer_his(self):
        p = pathlib.Path(self.call('save_copy', name='Changée')['saved'])
        with open(p, 'ab') as f:
            f.write(b'\0')
        before = p.read_bytes()
        self.assertIn('not one of your copies', self.refused('save_copy', name='Changée', overwrite=True))
        self.assertEqual(p.read_bytes(), before)
        self.assertFalse(self.call('list_copies')['copies'][0]['yours'])

    def test_formats(self):
        got = self.call('save_copy', name='Plan', format='dxf')
        self.assertTrue(got['saved'].endswith('Plan.dxf'))
        self.assertEqual(got['format'], 'dxf')
        got = self.call('save_copy', name='Plan', format='.svg')
        self.assertTrue(got['saved'].endswith('Plan.svg'))
        self.assertTrue(self.call('save_copy', name='Plan', format='step')['saved'].endswith('Plan.step'))
        self.assertTrue(self.call('save_copy', name='Plan2', format='stp')['saved'].endswith('Plan2.stp'))
        self.assertIn('no format', self.refused('save_copy', name='Plan', format='nc'))
        self.assertIn('no format', self.refused('save_copy', name='Plan', format='exe'))
        self.assertNotIn('.vdz', [p.suffix for p in self.folder.iterdir()], 'pas de compagnon .vdz écrit à côté')

    def test_names_checked(self):
        for bad in ('../dehors', 'a/b', 'C:x', '', '   ', 'CON', 'nul', 'x' * 61, 'a.vdz', 'COM1', 'lpt¹', 'COM0'):
            self.assertIn('"name"', self.refused('save_copy', name=bad), bad)
        self.assertIn('"overwrite"', self.refused('save_copy', name='ok', overwrite='oui'))
        self.assertFalse(self.folder.exists() and any(self.folder.iterdir()))

    def test_folder_option(self):
        other = self.base / 'mes copies'
        self.w.settings.setValue('assistant/dossier_copies', str(other))
        self.addCleanup(self.w.settings.remove, 'assistant/dossier_copies')
        got = self.call('save_copy', name='Ailleurs')
        self.assertEqual(pathlib.Path(got['saved']), other / 'Ailleurs.vdz')
        listed = self.call('list_copies')
        self.assertEqual(pathlib.Path(listed['folder']), other)
        self.assertEqual([(c['name'], c['yours'], c['in_folder']) for c in listed['copies']],
                         [('Ailleurs.vdz', True, True)])

    def test_write_failure_leaves_nothing(self):
        from vectordrive.io import registry
        with mock.patch.object(registry, 'save_document', side_effect=OSError('disque plein')):
            self.assertIn('disque plein', self.refused('save_copy', name='Ratée'))
        self.assertFalse((self.folder / 'Ratée.vdz').exists())
        self.assertEqual(self.leftovers(), [])
        self.assertEqual(self.T.copies_registry(), {})

    def test_file_appearing_meanwhile_is_kept(self):
        from vectordrive.io import registry
        real = registry.save_document
        target = self.folder / 'Course.vdz'

        def write(doc, path):
            real(doc, path)
            target.write_bytes(b'venu entre-temps')
        with mock.patch.object(registry, 'save_document', side_effect=write):
            self.assertIn('meanwhile', self.refused('save_copy', name='Course'))
        self.assertEqual(target.read_bytes(), b'venu entre-temps')
        self.assertEqual(self.leftovers(), [])

    def test_own_copy_changed_meanwhile_is_kept(self):
        from vectordrive.io import registry
        p = pathlib.Path(self.call('save_copy', name='Pendant')['saved'])
        real = registry.save_document

        def write(doc, path):
            real(doc, path)
            p.write_bytes(b'change par l utilisateur')
        with mock.patch.object(registry, 'save_document', side_effect=write):
            self.assertIn('meanwhile', self.refused('save_copy', name='Pendant', overwrite=True))
        self.assertEqual(p.read_bytes(), b'change par l utilisateur')
        self.assertEqual(self.leftovers(), [])

    def test_other_formats_say_what_they_lose_and_the_drawing_is_untouched(self):
        extra = dict(self.w.canvas.doc.extra)
        report = list(self.w.canvas.doc.report)
        got = self.call('save_copy', name='Pour TE', format='vnd')
        self.assertTrue(any('only the vdz format' in n for n in got['notes']))
        self.assertEqual(self.w.canvas.doc.extra, extra, 'le dessin ouvert pas touché (réglages VND)')
        self.assertEqual(list(self.w.canvas.doc.report), report)
        self.assertNotIn('notes', self.call('save_copy', name='Complète'))

    def test_written_but_not_recorded(self):
        with mock.patch.object(self.T, 'record_copy', side_effect=OSError('registre verrouillé')):
            msg = self.refused('save_copy', name='Hors registre')
        self.assertIn('was written but could not be recorded', msg)
        self.assertTrue((self.folder / 'Hors registre.vdz').is_file())
        self.assertIn('not one of your copies', self.refused('save_copy', name='Hors registre', overwrite=True))

    def test_without_hard_links(self):
        with mock.patch.object(os, 'link', side_effect=OSError('pas de liens ici')):
            p = pathlib.Path(self.call('save_copy', name='Sans lien')['saved'])
            self.assertTrue(self.T.own_copy(p))
            from vectordrive.io import registry
            real = registry.save_document
            target = self.folder / 'Venue.vdz'

            def write(doc, path):
                real(doc, path)
                target.write_bytes(b'venu entre-temps')
            with mock.patch.object(registry, 'save_document', side_effect=write):
                self.assertIn('meanwhile', self.refused('save_copy', name='Venue'))
            self.assertEqual(target.read_bytes(), b'venu entre-temps')
        self.assertEqual(self.leftovers(), [])

    def test_same_bytes_put_back_later_are_not_his(self):
        p = pathlib.Path(self.call('save_copy', name='Remise')['saved'])
        data = p.read_bytes()
        p.unlink()
        p.write_bytes(data)                              # un fichier de l'utilisateur, mêmes octets, plus tard
        os.utime(p, ns=(1, 1))
        self.assertFalse(self.T.own_copy(p))

    def test_the_file_has_its_real_name_while_written(self):
        from vectordrive.io import registry
        seen = []
        real = registry.save_document

        def write(doc, path):
            seen.append(pathlib.Path(path).name)
            real(doc, path)
        with mock.patch.object(registry, 'save_document', side_effect=write):
            self.call('save_copy', name='Plan', format='pdf')
        self.assertEqual(seen, ['Plan.pdf'], 'le titre d’un PDF, le nom d’un STEP : jamais un nom provisoire')
        self.assertEqual(self.leftovers(), [])

    def test_the_model_is_told(self):
        from vectordrive.agent import chat
        self.assertIn('save_copy', chat.SYSTEM)
        self.assertNotIn('nothing you do can overwrite a file', chat.SYSTEM)

    def test_option_and_mcp(self):
        t = self.T.ToolSet(self.w, extended=True, without=('copies',))
        self.assertFalse({'save_copy', 'list_copies'} & set(t.names()))
        self.assertFalse({'save_copy', 'list_copies'} & set(self.T.ToolSet(self.w).names()), 'pas le serveur MCP')
        from vectordrive.ui.assistant_options import TOOL_GROUPS
        self.assertEqual(TOOL_GROUPS['assistant/outils_copies'], 'copies')
        from vectordrive.ui.options import value
        self.assertTrue(value(self.w.settings, 'assistant/outils_copies'), 'permis d’office')

    def test_tests_never_write_in_the_user_data(self):
        self.assertTrue(os.environ.get('VECTORDRIVE_ASSISTANT_DIR'))
        from vectordrive.portable import data_dir
        self.assertNotEqual(self.T.assistant_dir(), data_dir() / 'assistant')


if __name__ == '__main__':
    unittest.main()
