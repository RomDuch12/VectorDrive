"""Round 1068 : demande du 17/11, 0 h 05 (atelier SimPL), troisième étape — « utiliser les parcours calculés … les
combiner avec des opérations internes Datron (ND et manuel SimPL) avec génération SimPL ». Le cœur donne le dessin au
post-processeur qui le demande : il y ajoute les opérations propres à la machine que le dessin porte (NeoDrive sur le
Datron, plugin) ; avec elles, un programme s'écrit même sans parcours."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1068.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication  # noqa: E402

from tests import _posts  # noqa: E402

app = QApplication.instance() or QApplication([])
BEFORE = 'avant : le post-processeur ne reçoit pas le dessin'
SEEN = []
PREVIEW = []


def with_doc(toolpaths, setup, *, title: str = '', machine=None, stem: str = 'programme', box_mm=None, doc=None,
             origin=None, preview=False):
    """Post d'essai : il écrit une ligne par parcours, puis les « opérations de la machine » du dessin."""
    from vectordrive.cam.post import PostResult
    SEEN.append((doc, origin, len(toolpaths)))
    PREVIEW.append(preview)
    lines = ['%'] + [f'(parcours {tp.name})' for tp in toolpaths]
    plain = '%\nM30\n'
    ops = list((getattr(doc, 'extra', None) or {}).get('essai1068') or [])
    lines += [f'(machine {o})' for o in ops] + ['M30']
    res = PostResult('\n'.join(lines) + '\n', [], '.nc', 'utf-8')
    res.check_files = [(stem + '.nc', plain)]                     # le programme sans elles : la relecture
    return res


with_doc.doc_operations = lambda doc: len((getattr(doc, 'extra', None) or {}).get('essai1068') or [])


def without_doc(toolpaths, setup, *, title: str = '', machine=None, stem: str = 'programme', box_mm=None):
    from vectordrive.cam.post import PostResult
    SEEN.append(('sans', None, len(toolpaths)))
    return PostResult('%\nM30\n', [], '.nc', 'utf-8')


def broken(toolpaths, setup, **_k):
    raise AssertionError('jamais appelé')


broken.doc_operations = lambda doc: 1 / 0


def spin(n=4):
    for _ in range(n):
        app.processEvents()


class Run(unittest.TestCase):

    def setUp(self):
        from vectordrive.cam import post
        self.assertTrue(hasattr(post, 'doc_operations'), BEFORE)
        SEEN.clear()
        for key, fn in (('essai1068', with_doc), ('essai1068b', without_doc), ('essai1068c', broken)):
            cm = _posts.registered(key, fn)
            cm.__enter__()
            self.addCleanup(cm.__exit__, None, None, None)

    def test_the_post_that_asks_gets_the_drawing_and_its_origin(self):
        from vectordrive.cam import model, post
        from vectordrive.core.document import Document
        doc = Document()
        doc.extra['essai1068'] = ['Surfaçage', 'Perçage']
        res = post.run('essai1068', [], model.CamSetup(), doc=doc, origin=(5.0, 6.0))
        self.assertEqual(SEEN, [(doc, (5.0, 6.0), 0)])
        self.assertIn('(machine Perçage)', res.text)
        SEEN.clear()
        post.run('essai1068', [], model.CamSetup())                 # sans dessin : comme avant
        self.assertEqual(SEEN, [(None, None, 0)])
        SEEN.clear()
        post.run('essai1068b', [], model.CamSetup(), doc=doc)       # un post qui ne le demande pas : rien de changé
        self.assertEqual(SEEN, [('sans', None, 0)])
        PREVIEW.clear()
        post.run('essai1068', [], model.CamSetup(), doc=doc, preview=True)
        self.assertEqual(PREVIEW, [True])

    def test_how_many_operations_of_its_own(self):
        from vectordrive.cam import post
        from vectordrive.core.document import Document
        doc = Document()
        self.assertEqual(post.doc_operations('essai1068', doc), 0)
        doc.extra['essai1068'] = ['Surfaçage']
        self.assertEqual(post.doc_operations('essai1068', doc), 1)
        self.assertEqual(post.doc_operations('essai1068b', doc), 0)            # le post n'en écrit pas
        self.assertEqual(post.doc_operations('essai1068c', doc), 0)            # le plugin en défaut : rien
        self.assertEqual(post.doc_operations('inconnu1068', doc), 0)
        self.assertEqual(post.doc_operations('essai1068', None), 0)
        self.assertEqual(post.doc_operations('', doc), 0)


class Window(unittest.TestCase):

    def setUp(self):
        from vectordrive.cam import post
        from vectordrive.ui.main_window import MainWindow
        self.assertTrue(hasattr(post, 'doc_operations'), BEFORE)
        SEEN.clear()
        cm = _posts.registered('essai1068', with_doc)
        cm.__enter__()
        self.addCleanup(cm.__exit__, None, None, None)
        self.w = MainWindow()
        self.w.resize(1400, 900)
        self.addCleanup(self.close)
        self.p = self.w.cam_panel
        s = self.p.setup()
        s.post = 'essai1068'
        self.p._fill_posts()
        self.p.save(s)

    def close(self):
        self.w.modified = False
        self.w.close()
        self.w.deleteLater()

    def test_preview_without_toolpaths_but_with_operations_of_the_machine(self):
        data = self.p.program_preview()
        self.assertEqual(data['files'], [])                          # rien : la note de toujours
        self.assertIn('Aucun parcours', data['note'])
        self.w.canvas.doc.extra['essai1068'] = ['Surfaçage']
        data = self.p.program_preview()
        self.assertEqual(len(data['files']), 1, data['note'])
        self.assertIn('(machine Surfaçage)', data['files'][0][1])
        self.assertIs(SEEN[-1][0], self.w.canvas.doc)              # le dessin affiché
        self.assertTrue(PREVIEW[-1])                                # un aperçu
        self.assertIn('opérations propres à la machine', data['note'])
        self.assertEqual(self.p.machine_ops(), 1)

    def test_once_in_a_grouped_program_and_never_turned(self):
        from unittest import mock
        from vectordrive.cam import post
        self.w.canvas.doc.extra['essai1068'] = ['Surfaçage']
        with mock.patch.object(post, 'program_groups', lambda *a, **k: [('a', []), ('b', []), ('c', [])]):
            SEEN.clear()
            data = self.p.program_preview()
        self.assertEqual([d for d, _o, _n in SEEN], [None, None, self.w.canvas.doc])   # le dernier fichier seul
        self.assertEqual(sum('(machine Surfaçage)' in t for _n, t in data['files']), 1)
        s = self.p.setup()
        s.output_orient = 'miroir_y'
        self.p.save(s)
        with mock.patch.object(self.p, '_stock_box', lambda: (0.0, 0.0, -2.0, 100.0, 50.0, 0.0)):
            SEEN.clear()
            data = self.p.program_preview()
        self.assertEqual([d for d, _o, _n in SEEN], [None])
        self.assertTrue(any('Orientation de sortie' in w for w in data['warnings']), data['warnings'])

    def test_written_without_toolpaths_and_read_back_without_them(self):
        from unittest import mock
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        from vectordrive.cam import postcheck
        self.w.canvas.doc.extra['essai1068'] = ['Perçage']
        read = []
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, 'p.nc')
            old = QFileDialog.getSaveFileName, QMessageBox.information, QMessageBox.warning
            QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: (out, ''))
            QMessageBox.information = QMessageBox.warning = staticmethod(lambda *a, **k: None)
            try:
                with mock.patch.object(postcheck, 'verify', lambda files, *a, **k: read.append(files) or []):
                    self.p.post_process()
            finally:
                QFileDialog.getSaveFileName, QMessageBox.information, QMessageBox.warning = old
            self.assertTrue(pathlib.Path(out).exists(), 'avant : rien écrit sans parcours')
            self.assertIn('(machine Perçage)', pathlib.Path(out).read_text(encoding='utf-8'))
        self.assertEqual(read, [[('p.nc', '%\nM30\n')]])               # relu : le programme sans elles
        box = getattr(self.p, 'done_box', None)
        self.assertIsNotNone(box)
        box.close()


if __name__ == '__main__':
    unittest.main()
