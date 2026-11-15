"""Round 897 : zéro du programme — l'origine du dessin, ou le coin supérieur gauche, le centre, le coin inférieur gauche
de la plaque (TypeEdit : positionnement de la pièce, fenêtre Usinage), quelle que soit l'origine du dessin ; dit dans la
vérification avant l'écriture et dans le message de fin, pour que l'opérateur règle l'origine de la machine au bon
endroit."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', os.path.join(tempfile.mkdtemp(), 'session'))
os.environ.setdefault('VECTORDRIVE_NO_TYPEEDIT', '1')

from vectordrive.cam import model as M
from vectordrive.cam import post
from vectordrive.cam import preflight as PF
from vectordrive.cam.model import Move, Toolpath
from vectordrive.core.document import Document, Plate


def plate():
    """Une plaque de 100 × 50 dont le centre est le zéro du dessin (point zéro au centre, comme dans TypeEdit)."""
    return Plate(width=100.0, height=50.0, x=-50.0, y=-25.0)


def path(*moves):
    tp = Toolpath('op', 'outil', name='p')
    tp.moves = list(moves)
    return tp


class Points(unittest.TestCase):

    def test_the_plate_points(self):
        pl = plate()
        self.assertEqual(post.zero_point('plaque_hg', pl), (-50.0, 25.0))
        self.assertEqual(post.zero_point('plaque_centre', pl), (0.0, 0.0))
        self.assertEqual(post.zero_point('plaque_bg', pl), (-50.0, -25.0))

    def test_the_drawing_origin(self):
        pl = plate()
        self.assertIsNone(post.zero_point('dessin', pl))
        self.assertEqual(post.zero_point('dessin', pl, (10.0, 5.0)), (10.0, 5.0))
        self.assertEqual(post.zero_point('de travers', pl, (10.0, 5.0)), (10.0, 5.0))      # choix inconnu : l'origine
        self.assertEqual(post.zero_point('plaque_hg', pl, (10.0, 5.0)), (-50.0, 25.0))     # la plaque passe avant

    def test_without_plate(self):
        self.assertEqual(post.zero_point('plaque_hg', None, (3.0, 4.0)), (3.0, 4.0))
        self.assertIsNone(post.zero_point('plaque_centre', None))
        self.assertEqual(post.zero_point('plaque_hg', Plate(width=0.0, height=50.0), (3.0, 4.0)), (3.0, 4.0))

    def test_the_texts(self):
        pl = plate()
        self.assertEqual(post.zero_text(pl, (-50.0, 25.0)), ('coin supérieur gauche de la plaque', True))
        self.assertEqual(post.zero_text(pl, None), ('centre de la plaque', True))
        self.assertEqual(post.zero_text(pl, (-50.0, -25.0)), ('coin inférieur gauche de la plaque', True))
        self.assertEqual(post.zero_text(pl, (50.0, 25.0)), ('coin supérieur droit de la plaque', True))
        self.assertEqual(post.zero_text(pl, (50.0, -25.0)), ('coin inférieur droit de la plaque', True))
        self.assertEqual(post.zero_text(pl, (-49.995, 25.004))[1], True)                  # à 0,01 mm près
        text, ok = post.zero_text(pl, (10.0, 5.0))
        self.assertFalse(ok)
        self.assertIn('X 60 ; Y 30 mm depuis le coin inférieur gauche', text)
        text, ok = post.zero_text(None, None)
        self.assertFalse(ok)
        self.assertIn('sans plaque', text)


class Setup(unittest.TestCase):

    def test_it_survives_the_file(self):
        doc = Document()
        s = M.setup_of(doc)
        self.assertEqual(s.program_zero, 'machine')                      # 0.755.0 : selon la machine par défaut
        s.program_zero = 'plaque_hg'
        M.store(doc, s)
        self.assertEqual(M.setup_of(doc).program_zero, 'plaque_hg')

    def test_an_older_drawing(self):
        d = M.CamSetup().to_dict()
        d.pop('program_zero')
        self.assertEqual(M.CamSetup.from_dict(d).program_zero, 'machine')


class Preflight(unittest.TestCase):

    def report(self, zero):
        return PF.inspect(Document(), M.CamSetup(), [path(Move('feed', 1.0, 1.0, -0.1), Move('feed', 5.0, 1.0, -0.1))],
                          zero=zero)

    def test_a_corner(self):
        r = self.report(('coin supérieur gauche de la plaque', True))
        self.assertEqual(r.zero, 'coin supérieur gauche de la plaque')
        self.assertFalse([t for _lv, t in r.notes if t.startswith('Zéro du programme')])
        html = PF.summary_html(r)
        self.assertIn('Zéro du programme (X0 Y0)', html)
        self.assertIn('coin supérieur gauche de la plaque', html)

    def test_another_point(self):
        r = self.report(('X 60 ; Y 30 mm depuis le coin inférieur gauche de la plaque, ni un coin ni le centre', False))
        got = [(lv, t) for lv, t in r.notes if t.startswith('Zéro du programme')]
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0][0], PF.ATTENTION)
        self.assertIn('X 60 ; Y 30', got[0][1])

    def test_not_asked(self):
        r = self.report(None)
        self.assertEqual(r.zero, '')
        self.assertNotIn('Zéro du programme', PF.summary_html(r))


class Panel(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])
        from vectordrive.ui.main_window import MainWindow
        cls.win = MainWindow()
        cls.p = cls.win.cam_panel

    @classmethod
    def tearDownClass(cls):
        cls.win.modified = False
        cls.win.close()

    def tearDown(self):
        self.p.zero_dialog('dessin')
        self.p.orient_dialog('normal')
        self.win.canvas.set_origin(0.0, 0.0)
        self.win.canvas.doc.plate = None

    def test_the_labels_match(self):
        self.assertEqual(set(self.p.ZERO_LABELS), set(post.ZEROS))

    def test_the_setting(self):
        self.assertTrue(self.p.zero_dialog('plaque_hg'))
        self.assertEqual(self.p.setup().program_zero, 'plaque_hg')
        self.assertFalse(self.p.zero_dialog('de travers'))
        self.assertEqual(self.p.setup().program_zero, 'plaque_hg')

    def test_the_window(self):
        from PySide6.QtWidgets import QInputDialog
        with mock.patch.object(QInputDialog, 'getItem', return_value=(self.p.ZERO_LABELS['plaque_centre'], True)):
            self.assertTrue(self.p.zero_dialog())
        self.assertEqual(self.p.setup().program_zero, 'plaque_centre')
        with mock.patch.object(QInputDialog, 'getItem', return_value=('', False)):
            self.assertFalse(self.p.zero_dialog())
        self.assertEqual(self.p.setup().program_zero, 'plaque_centre')

    def test_the_program_origin(self):
        self.win.canvas.doc.plate = plate()
        self.assertIsNone(self.p.program_origin())                      # par défaut : l'origine du dessin, ici son zéro
        self.p.zero_dialog('plaque_hg')
        self.assertEqual(self.p.program_origin(), (-50.0, 25.0))
        self.p.zero_dialog('plaque_centre')
        self.assertIsNone(self.p.program_origin())                      # le centre est le zéro du dessin
        self.p.zero_dialog('plaque_bg')
        self.assertEqual(self.p.program_origin(), (-50.0, -25.0))
        self.win.canvas.set_origin(10.0, 5.0)
        self.assertEqual(self.p.program_origin(), (-50.0, -25.0))       # la plaque passe avant l'origine du dessin
        self.p.zero_dialog('dessin')
        self.assertEqual(self.p.program_origin(), (10.0, 5.0))
        self.win.canvas.doc.plate = None
        self.p.zero_dialog('plaque_hg')
        self.assertEqual(self.p.program_origin(), (10.0, 5.0))          # sans plaque : l'origine du dessin

    def probe(self):
        """Le post-traitement avec un post-processeur d'essai qui n'écrit rien : rend ce qu'il a reçu."""
        from PySide6.QtWidgets import QMessageBox
        got = {}

        def fake(key, tps, s, **kw):
            got.update(tps=tps, **kw)
            return post.PostResult('', ['rien'], '.nc')
        tp = path(Move('feed', -40.0, 20.0, -1.0))
        with mock.patch.object(self.p, 'current_paths', lambda *a, **k: [tp]), \
                mock.patch.object(post, 'posts', lambda d='': {'x': ('x', None)}), \
                mock.patch.object(post, 'run', fake), mock.patch.object(QMessageBox, 'warning'):
            self.p.post_process()
        return got

    def test_the_post_gets_the_plate_corner(self):
        self.win.canvas.doc.plate = plate()
        self.p.zero_dialog('plaque_hg')
        self.assertEqual(self.probe()['origin'], (-50.0, 25.0))
        self.p.orient_dialog('r180')                                     # plaque tournée : toujours son coin haut gauche
        self.assertEqual(self.probe()['origin'], (-50.0, 25.0))
        self.p.orient_dialog('normal')
        self.p.zero_dialog('dessin')
        self.assertIsNone(self.probe()['origin'])

    def test_the_preflight_says_it(self):
        self.win.canvas.doc.plate = plate()
        self.p.zero_dialog('plaque_hg')
        tp = path(Move('feed', -40.0, 20.0, -1.0))
        with mock.patch('vectordrive.cam.preflight.inspect', wraps=PF.inspect) as spy:
            self.assertTrue(self.p.preflight([tp], [], exec_dialog=False))
        self.assertEqual(spy.call_args.kwargs['zero'], ('coin supérieur gauche de la plaque', True))

    def test_the_end_message_says_it(self):
        from PySide6.QtWidgets import QFileDialog
        self.win.canvas.doc.plate = plate()
        self.p.zero_dialog('plaque_hg')
        tp = path(Move('feed', -40.0, 20.0, -1.0))
        folder = tempfile.mkdtemp()

        def fake(key, part, s, *, title='', stem='', box_mm=None, out_dir='', origin=None, machine=None):
            return post.PostResult('G0', [], '.nc', 'ascii', [(stem + '.nc', 'G0\n')])
        with mock.patch.object(self.p, 'current_paths', lambda *a, **k: [tp]), \
                mock.patch.object(post, 'posts', lambda d='': {'x': ('x', None)}), \
                mock.patch.object(post, 'run', fake), mock.patch.object(self.p, 'preflight', lambda *a, **k: True), \
                mock.patch.object(QFileDialog, 'getSaveFileName', return_value=(os.path.join(folder, 'prog.nc'), '')), \
                mock.patch('vectordrive.ui.progress.run', lambda win, title, fn, *a: []), \
                mock.patch('vectordrive.ui.reveal.done_message') as done:
            self.p.post_process()
        text = done.call_args.args[2]
        self.assertIn('Zéro du programme (X0 Y0) : coin supérieur gauche de la plaque', text)


if __name__ == '__main__':
    unittest.main()
