"""Round 898 : zéro du programme « Selon la machine », réglage par défaut — le post-processeur (attribut `program_zero`
de sa fonction) ou la fiche machine (`default_zero(clé)` de son fournisseur) disent le zéro qu'attend la machine, par
exemple le coin supérieur gauche de la plaque là où l'opérateur règle l'origine sur ce coin au lancement de l'usinage ;
sinon l'origine du dessin, comme avant. Un choix fait dans le dessin passe avant."""
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
from vectordrive.cam.model import Move, Toolpath
from vectordrive.core.document import Document, Plate
from vectordrive.plugins import REGISTRY


def plate():
    """Une plaque de 100 × 50 dont le centre est le zéro du dessin."""
    return Plate(width=100.0, height=50.0, x=-50.0, y=-25.0)


def writer(zero=None):
    """Une fonction d'écriture de post-processeur d'essai, qui dit (ou non) le zéro de sa machine."""
    def write(tps, s, **kw):
        return post.PostResult('', ['rien'], '.nc')
    if zero is not None:
        write.program_zero = zero
    return write


class Sheets:
    """Un fournisseur de fiches d'essai : la fiche « mah:coin » attend le coin supérieur gauche de la plaque."""

    def posts(self, folder):
        return {'mah:coin': 'Coin', 'mah:rien': 'Rien'}

    def resolve(self, key):
        return None

    def default_zero(self, key):
        if key == 'mah:panne':
            raise OSError('fiche illisible')
        return {'mah:coin': 'plaque_hg', 'mah:bizarre': 'ailleurs'}.get(key, '')


def with_posts(**zeros):
    """Les post-processeurs d'essai (clé → zéro dit, ou None) et le fournisseur de fiches, le temps d'un essai."""
    return (mock.patch.dict(REGISTRY.posts, {k: (k, writer(z)) for k, z in zeros.items()}),
            mock.patch.object(REGISTRY, 'post_providers', [Sheets()]))


class Machine(unittest.TestCase):

    def setUp(self):
        for p in with_posts(coin='plaque_hg', centre='plaque_centre', muet=None, faux='nulle part'):
            p.start()
            self.addCleanup(p.stop)

    def test_the_choices(self):
        self.assertEqual(post.ZEROS[0], 'machine')
        self.assertEqual(post.PLATE_ZEROS, ('plaque_hg', 'plaque_centre', 'plaque_bg'))
        self.assertIsNone(post.zero_point('machine', plate()))                            # pas un point de la plaque

    def test_a_post_says_its_zero(self):
        self.assertEqual(post.default_zero('coin'), 'plaque_hg')
        self.assertEqual(post.default_zero('centre'), 'plaque_centre')
        self.assertEqual(post.default_zero('muet'), 'dessin')                             # rien dit : l'origine du dessin
        self.assertEqual(post.default_zero('faux'), 'dessin')                             # réponse inconnue
        self.assertEqual(post.default_zero(''), 'dessin')
        self.assertEqual(post.default_zero('absent'), 'dessin')

    def test_a_machine_sheet_says_its_zero(self):
        self.assertEqual(post.default_zero('mah:coin'), 'plaque_hg')
        self.assertEqual(post.default_zero('mah:rien'), 'dessin')
        self.assertEqual(post.default_zero('mah:bizarre'), 'dessin')
        self.assertEqual(post.default_zero('mah:panne'), 'dessin')                       # fiche illisible : rien

    def test_the_drawing_choice_wins(self):
        self.assertEqual(post.effective_zero('machine', 'coin'), 'plaque_hg')
        self.assertEqual(post.effective_zero('machine', 'muet'), 'dessin')
        self.assertEqual(post.effective_zero('dessin', 'coin'), 'dessin')
        self.assertEqual(post.effective_zero('plaque_centre', 'mah:coin'), 'plaque_centre')
        self.assertEqual(post.effective_zero('de travers', 'mah:coin'), 'plaque_hg')     # réglage inconnu : la machine


class Setup(unittest.TestCase):

    def test_the_default(self):
        self.assertEqual(M.CamSetup().program_zero, 'machine')
        d = M.CamSetup().to_dict()
        d.pop('program_zero')
        self.assertEqual(M.CamSetup.from_dict(d).program_zero, 'machine')               # dessin d'avant 0.754.0
        d['program_zero'] = 'dessin'
        self.assertEqual(M.CamSetup.from_dict(d).program_zero, 'dessin')                # choix gardé


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

    def setUp(self):
        for p in with_posts(coin='plaque_hg', muet=None):
            p.start()
            self.addCleanup(p.stop)
        self.win.canvas.doc.plate = plate()

    def tearDown(self):
        self.p.zero_dialog('machine')
        self.use('')
        self.win.canvas.set_origin(0.0, 0.0)
        self.win.canvas.doc.plate = None

    def use(self, key):
        s = self.p.setup()
        s.post = key
        self.p.save(s)

    def test_the_labels_match(self):
        self.assertEqual(list(self.p.ZERO_LABELS)[0], 'machine')
        self.assertEqual(set(self.p.ZERO_LABELS), set(post.ZEROS))

    def test_the_post_key(self):
        self.use('coin')
        self.assertEqual(self.p.post_key(), 'coin')
        self.use('mah:coin')
        self.assertEqual(self.p.post_key(), 'mah:coin')
        self.use('disparu')                                              # absent : le premier disponible
        self.assertEqual(self.p.post_key(), next(iter(post.posts(self.p.machines_dir())), ''))

    def test_the_machine_zero_by_default(self):
        self.assertEqual(self.p.setup().program_zero, 'machine')
        self.use('coin')
        self.assertEqual(self.p.program_origin(), (-50.0, 25.0))         # coin supérieur gauche de la plaque
        self.use('mah:coin')
        self.assertEqual(self.p.program_origin(), (-50.0, 25.0))
        self.use('muet')
        self.win.canvas.set_origin(10.0, 5.0)
        self.assertEqual(self.p.program_origin(), (10.0, 5.0))           # rien dit : l'origine du dessin
        self.use('coin')
        self.win.canvas.doc.plate = None
        self.assertEqual(self.p.program_origin(), (10.0, 5.0))           # sans plaque : l'origine du dessin

    def test_the_drawing_choice_wins(self):
        self.use('coin')
        self.assertEqual(self.p.program_origin(), (-50.0, 25.0))         # la machine
        self.p.zero_dialog('dessin')                                     # puis le choix du dessin
        self.assertIsNone(self.p.program_origin())
        self.p.zero_dialog('plaque_bg')
        self.assertEqual(self.p.program_origin(), (-50.0, -25.0))

    def test_the_window_says_what_the_machine_wants(self):
        from PySide6.QtWidgets import QInputDialog
        self.use('coin')
        self.p.zero_dialog('dessin')
        got = {}

        def pick(parent, title, label, items, current, editable):
            got.update(items=items, current=current)
            return items[0], True
        with mock.patch.object(QInputDialog, 'getItem', pick):
            self.assertTrue(self.p.zero_dialog())
        self.assertEqual(got['items'][0], 'Selon la machine (ici : coin supérieur gauche de la plaque)')
        self.assertEqual(got['current'], 1)                              # le choix d'avant : l'origine du dessin
        self.assertEqual(self.p.setup().program_zero, 'machine')
        self.use('muet')
        with mock.patch.object(QInputDialog, 'getItem', pick):
            self.p.zero_dialog()
        self.assertEqual(got['items'][0], 'Selon la machine (ici : origine du dessin)')
        self.assertEqual(got['current'], 0)

    def test_the_post_and_the_checks_get_it(self):
        from PySide6.QtWidgets import QMessageBox
        self.use('coin')
        seen = {}

        def fake(key, tps, s, **kw):
            seen.update(key=key, **kw)
            return post.PostResult('', ['rien'], '.nc')
        tp = Toolpath('op', 'outil', name='p')
        tp.moves = [Move('feed', -40.0, 20.0, -1.0)]
        with mock.patch.object(self.p, 'current_paths', lambda *a, **k: [tp]), \
                mock.patch.object(post, 'run', fake), mock.patch.object(QMessageBox, 'warning'):
            self.p.post_process()
        self.assertEqual(seen['key'], 'coin')
        self.assertEqual(seen['origin'], (-50.0, 25.0))
        from vectordrive.cam import preflight as PF
        with mock.patch('vectordrive.cam.preflight.inspect', wraps=PF.inspect) as spy:
            self.assertTrue(self.p.preflight([tp], [], exec_dialog=False))
        self.assertEqual(spy.call_args.kwargs['zero'], ('coin supérieur gauche de la plaque', True))


if __name__ == '__main__':
    unittest.main()
