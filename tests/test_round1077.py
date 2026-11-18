"""Round 1077 : demande du 17/11 soir — Datron, « image exportée (vue 2D 3D ou les 2) ». Un post-processeur joint des
fichiers binaires à son programme (`PostResult.attachments`), seulement à l'écriture (`attach`) ; le post-traitement
les écrit à côté du programme."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1077.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication  # noqa: E402

from tests import _posts  # noqa: E402

app = QApplication.instance() or QApplication([])
BEFORE = 'avant : un post-processeur ne joint que des fichiers texte'
ATTACH = []
PNG = b'\x89PNG\r\n\x1a\n' + bytes(range(256))


def joining(toolpaths, setup, *, title: str = '', machine=None, stem: str = 'programme', box_mm=None, doc=None,
            origin=None, preview=False, attach=False):
    """Post d'essai : son programme, et ses fichiers joints quand on l'écrit."""
    from vectordrive.cam.post import PostResult
    ATTACH.append(attach)
    ops = list((getattr(doc, 'extra', None) or {}).get('essai1077') or [])
    res = PostResult('%\n' + ''.join(f'(machine {o})\n' for o in ops) + 'M30\n', [], '.nc', 'utf-8')
    if attach:
        res.attachments = [(stem + '.png', PNG), ('../dehors.bin', b'xy'), ('texte.txt', 'pas des octets')]
    return res


joining.doc_operations = lambda doc: len((getattr(doc, 'extra', None) or {}).get('essai1077') or [])


def plain(toolpaths, setup, *, title: str = '', machine=None, stem: str = 'programme', box_mm=None):
    from vectordrive.cam.post import PostResult
    ATTACH.append('sans')
    return PostResult('%\nM30\n', [], '.nc', 'utf-8')


class Run(unittest.TestCase):

    def setUp(self):
        from vectordrive.cam import post
        self.assertTrue(hasattr(post, 'write_attachments'), BEFORE)
        ATTACH.clear()
        for key, fn in (('essai1077', joining), ('essai1077b', plain)):
            cm = _posts.registered(key, fn)
            cm.__enter__()
            self.addCleanup(cm.__exit__, None, None, None)

    def test_attach_only_when_writing(self):
        from vectordrive.cam import model, post
        res = post.run('essai1077', [], model.CamSetup())
        self.assertEqual((ATTACH, res.attachments), ([False], []))           # l'aperçu, le programme d'essai : rien
        res = post.run('essai1077', [], model.CamSetup(), attach=True, stem='p')
        self.assertEqual(ATTACH[-1], True)
        self.assertEqual(res.attachments[0], ('p.png', PNG))
        post.run('essai1077', [], model.CamSetup(), attach=True, preview=True)
        self.assertEqual(ATTACH[-1], False)                                  # jamais pendant un aperçu
        res = post.run('essai1077b', [], model.CamSetup(), attach=True)      # un post qui ne le demande pas
        self.assertEqual((ATTACH[-1], res.attachments), ('sans', []))

    def test_written_by_name_only_and_bytes_only(self):
        from vectordrive.cam import post
        res = post.PostResult('x', attachments=[('a.png', PNG), ('../b.bin', b'xy'), ('c.txt', 'texte'), ('', b'z')])
        with tempfile.TemporaryDirectory() as tmp:
            sub = pathlib.Path(tmp) / 'prog'
            sub.mkdir()
            got = post.write_attachments(res, sub)
            self.assertEqual([f.name for f in got], ['a.png', 'b.bin'])
            self.assertEqual((sub / 'a.png').read_bytes(), PNG)
            self.assertTrue((sub / 'b.bin').exists())                        # dans le dossier du programme
            self.assertFalse((pathlib.Path(tmp) / 'b.bin').exists())
            self.assertFalse((sub / 'c.txt').exists())
            self.assertEqual(post.write_attachments(post.PostResult('x'), sub), [])


class Window(unittest.TestCase):

    def setUp(self):
        from vectordrive.cam import post
        from vectordrive.ui.main_window import MainWindow
        self.assertTrue(hasattr(post, 'write_attachments'), BEFORE)
        ATTACH.clear()
        cm = _posts.registered('essai1077', joining)
        cm.__enter__()
        self.addCleanup(cm.__exit__, None, None, None)
        self.w = MainWindow()
        self.w.resize(1400, 900)
        self.addCleanup(self.close)
        self.p = self.w.cam_panel
        s = self.p.setup()
        s.post = 'essai1077'
        self.p._fill_posts()
        self.p.save(s)

    def close(self):
        self.w.modified = False
        self.w.close()
        self.w.deleteLater()
        app.processEvents()

    def test_post_process_writes_them_next_to_the_program(self):
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        self.w.canvas.doc.extra['essai1077'] = ['Perçage']
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, 'p.nc')
            old = QFileDialog.getSaveFileName, QMessageBox.information, QMessageBox.warning
            QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: (out, ''))
            QMessageBox.information = QMessageBox.warning = staticmethod(lambda *a, **k: None)
            try:
                self.p.post_process()
            finally:
                QFileDialog.getSaveFileName, QMessageBox.information, QMessageBox.warning = old
            self.assertTrue(pathlib.Path(out).exists())
            self.assertEqual((pathlib.Path(tmp) / 'p.png').read_bytes(), PNG, BEFORE)
            self.assertTrue((pathlib.Path(tmp) / 'dehors.bin').exists())
            self.assertFalse((pathlib.Path(tmp) / 'texte.txt').exists())
            self.assertFalse((pathlib.Path(tmp).parent / 'dehors.bin').exists())
            self.assertIn(True, ATTACH)                                       # l'écriture
            self.assertEqual(ATTACH[0], False)                                # le programme d'essai : sans
        box = getattr(self.p, 'done_box', None)
        if box is not None:
            box.close()

    def test_an_existing_attachment_is_asked_first(self):
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        self.w.canvas.doc.extra['essai1077'] = ['Perçage']
        asked = []
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, 'p.nc')
            (pathlib.Path(tmp) / 'p.png').write_bytes(b'photo')               # une image à soi, du même nom
            old = QFileDialog.getSaveFileName, QMessageBox.information, QMessageBox.warning, QMessageBox.question
            QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: (out, ''))
            QMessageBox.information = QMessageBox.warning = staticmethod(lambda *a, **k: None)
            QMessageBox.question = staticmethod(lambda *a, **k: asked.append(a[2]) or QMessageBox.StandardButton.No)
            try:
                self.p.post_process()
            finally:
                (QFileDialog.getSaveFileName, QMessageBox.information, QMessageBox.warning,
                 QMessageBox.question) = old
            self.assertTrue(asked and 'p.png' in asked[0], 'un fichier joint existant : demandé')
            self.assertEqual((pathlib.Path(tmp) / 'p.png').read_bytes(), b'photo')     # Non : rien d'écrasé
            self.assertFalse(pathlib.Path(out).exists())
        box = getattr(self.p, 'done_box', None)
        if box is not None:
            box.close()

    def test_a_locked_attachment_is_noted_not_fatal(self):
        from vectordrive.cam import post
        res = post.PostResult('x', attachments=[('a.png', PNG), ('b.png', PNG)])
        with tempfile.TemporaryDirectory() as tmp:
            (pathlib.Path(tmp) / 'a.png').mkdir()                              # « a.png » ne peut pas s'écrire
            got = post.write_attachments(res, tmp)
            self.assertEqual([f.name for f in got], ['b.png'])
            self.assertTrue(any('a.png' in w for w in res.warnings))
            self.assertEqual(post.write_attachments(res, tmp, skip=[pathlib.Path(tmp) / 'b.png']), [])


if __name__ == '__main__':
    unittest.main()
