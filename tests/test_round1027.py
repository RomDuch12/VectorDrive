"""Round 1027 : demande du 14/11 — « système d'automatisation de programmes (liste opés appliquée à un pattern dessin
gravure + brut) » : programmes en série — un modèle d'usinage appliqué à chaque dessin d'un lot, son programme
écrit comme par le post-traitement ; les dessins ne sont jamais réécrits."""
import os
import pathlib
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1027.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication, QMenu  # noqa: E402

app = QApplication.instance() or QApplication([])

from tests import _posts  # noqa: E402
from vectordrive.cam import model  # noqa: E402
from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Document, Plate, Shape  # noqa: E402


def write_drawing(path: pathlib.Path, tool=0, setup=None) -> pathlib.Path:
    """Un dessin d'essai : une plaque 100 × 50 et un rectangle de l'outil (couleur) `tool`."""
    from vectordrive.io import registry
    doc = Document()
    doc.plate = Plate(width=100.0, height=50.0, thickness=3.0)
    doc.add(Shape(path=geom.Path([geom.rect(20.0, 10.0, 30.0, 20.0)]), tool=tool))
    if setup is not None:
        model.store(doc, setup)
    registry.save_document(doc, path)
    return path


def engraving_setup(name='G 1027', depth=0.2):
    s = model.CamSetup()
    t = model.CamTool(name='Cyl 1027', diameter=1.0, number=1, cut_length=5, step_down=0.5)
    s.tools = [t]
    s.operations = [model.Operation(name=name, kind='gravure', tool_id=t.id, sources=[0], depth=depth)]
    return s


def template():
    from vectordrive.cam import templates as TPL
    return TPL.from_setup(engraving_setup(), 'M 1027')


class Series(unittest.TestCase):

    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.posts = _posts.registered('essai')
        self.posts.__enter__()
        self.addCleanup(self.posts.__exit__, None, None, None)

    def test_template_applied_to_each_drawing(self):
        from vectordrive.cam import series
        a = write_drawing(self.tmp / 'a.vdz')
        b = write_drawing(self.tmp / 'b.vdz')
        other = write_drawing(self.tmp / 'autre couleur.vdz', tool=5)
        bad = self.tmp / 'abime.vdz'
        bad.write_bytes(b'pas un dessin')
        before = {p: p.read_bytes() for p in (a, b, other)}
        out = self.tmp / 'programmes'
        res = series.programs([a, b, other, bad], out, template(), 'essai')
        self.assertEqual([pathlib.Path(s).name for s, _f in res.done], ['a.vdz', 'b.vdz'])
        text = (out / 'a.nc').read_text(encoding='ascii')
        self.assertIn('(ESSAI a)', text)                                     # le titre : le nom du dessin
        self.assertIn('G1 ', text)
        self.assertEqual(res.done[0][1], [str(out / 'a.nc')])
        self.assertEqual([pathlib.Path(s).name for s, _m in res.skipped], ['autre couleur.vdz'])
        self.assertIn('aucun parcours', res.skipped[0][1])                    # la couleur du modèle n'y est pas
        self.assertEqual([pathlib.Path(s).name for s, _m in res.errors], ['abime.vdz'])
        self.assertEqual({p: p.read_bytes() for p in before}, before)         # les dessins jamais réécrits
        again = series.programs([a], out, template(), 'essai')
        self.assertEqual((len(again.done), again.skipped[0][1]), (0, 'a.nc existe déjà'))
        self.assertEqual(len(series.programs([a], out, template(), 'essai', overwrite=True).done), 1)
        beside = series.programs([b], '', template(), 'essai')               # sans dossier : à côté du dessin
        self.assertEqual(beside.done[0][1], [str(self.tmp / 'b.nc')])

    def test_drawing_operations_kept_or_replaced(self):
        from vectordrive.cam import series
        own = write_drawing(self.tmp / 'propre.vdz', setup=engraving_setup('Mienne 1027', depth=0.7))
        bare = write_drawing(self.tmp / 'nu.vdz')
        res = series.programs([own, bare], self.tmp / 'o', None, 'essai')    # sans modèle : ses opérations
        self.assertEqual([pathlib.Path(s).name for s, _f in res.done], ['propre.vdz'])
        self.assertIn('aucune opération', res.skipped[0][1])
        self.assertIn('Z-0.700', (self.tmp / 'o' / 'propre.nc').read_text(encoding='ascii'))
        from vectordrive.io import registry
        doc = registry.open_document(own)
        names = [o.name for o in series.setup_for(doc, template(), replace=True).operations]
        self.assertEqual(names, ['G 1027'])
        names = [o.name for o in series.setup_for(doc, template(), replace=False).operations]
        self.assertEqual(names, ['Mienne 1027', 'G 1027'])

    def test_tree_kept_and_same_program_once(self):
        from vectordrive.cam import series
        (self.tmp / 'src' / 'client').mkdir(parents=True)
        a = write_drawing(self.tmp / 'src' / 'client' / 'x.vdz')
        b = write_drawing(self.tmp / 'src' / 'client' / 'x.svg')
        res = series.programs([a, b], self.tmp / 'out', template(), 'essai', keep_tree_from=self.tmp / 'src')
        self.assertTrue((self.tmp / 'out' / 'client' / 'x.nc').exists())
        self.assertEqual(len(res.done), 1)
        self.assertIn('même programme', res.skipped[0][1])
        none = series.programs([a], self.tmp / 'z', template(), 'absent')
        self.assertEqual(len(none.errors), 1)                                 # post-processeur inconnu : dit


def fixed_name(toolpaths, setup, *, title='', machine=None, stem='programme', box_mm=None):
    """Un post qui nomme lui-même son fichier (comme un nom nettoyé) : deux dessins, un même fichier."""
    r = _posts.write(toolpaths, setup, title=title, stem=stem)
    r.files = [('commun.nc', r.text)]
    return r


def blocking(toolpaths, setup, *, title='', machine=None, stem='programme', box_mm=None):
    r = _posts.write(toolpaths, setup, title=title, stem=stem)
    r.warnings = ['BLOQUANT : arrêt non écrit (essai)']
    return r


def as_dxf(toolpaths, setup, *, title='', machine=None, stem='programme', box_mm=None):
    r = _posts.write(toolpaths, setup, title=title, stem=stem)
    r.extension = '.dxf'
    return r


class Guards(unittest.TestCase):

    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())

    def test_no_program_overwrites_another_or_a_drawing(self):
        from vectordrive.cam import series
        a = write_drawing(self.tmp / 'a.vdz')
        b = write_drawing(self.tmp / 'b.vdz')
        with _posts.registered('fixe', fixed_name):
            res = series.programs([a, b], self.tmp / 'o', template(), 'fixe', overwrite=True)
        self.assertEqual(len(res.done), 1)
        self.assertIn('même fichier que le programme de a.vdz', res.errors[0][1])   # jamais écrasé en silence
        drawing = self.tmp / 'a.dxf'
        drawing.write_bytes(b'0\nEOF\n')
        with _posts.registered('dxf_essai', as_dxf):
            res = series.programs([a], '', template(), 'dxf_essai', overwrite=True)
        self.assertIn('remplacerait un dessin', res.errors[0][1])
        self.assertEqual(drawing.read_bytes(), b'0\nEOF\n')

    def test_blocking_warning_and_machine_export_write_nothing(self):
        from vectordrive.cam import series
        from vectordrive.plugins import REGISTRY
        a = write_drawing(self.tmp / 'a.vdz')
        with _posts.registered('bloque', blocking):
            res = series.programs([a], self.tmp / 'o', template(), 'bloque')
        self.assertIn('BLOQUANT', res.errors[0][1])                          # comme le post-traitement : rien d'écrit
        self.assertFalse((self.tmp / 'o' / 'a.nc').exists())
        with _posts.registered('essai'), mock.patch.dict(REGISTRY.post_exports, {'essai': lambda *a: True}):
            res = series.programs([a], self.tmp / 'o', template(), 'essai')
        self.assertIn('panneau FAO', res.errors[0][1])                       # export propre à la machine

    def test_options_post_for_drawings_without_setup(self):
        from vectordrive.cam import series
        from vectordrive.io import registry
        tpl = dict(template(), post='')
        bare = registry.open_document(write_drawing(self.tmp / 'nu.vdz'))
        self.assertEqual(series.setup_for(bare, tpl, default_post='essai_options').post, 'essai_options')
        own = engraving_setup()
        own.post = 'le_sien'
        mine = registry.open_document(write_drawing(self.tmp / 'propre.vdz', setup=own))
        self.assertEqual(series.setup_for(mine, tpl, default_post='essai_options').post, 'le_sien')


class Window(unittest.TestCase):

    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.posts = _posts.registered('essai')
        self.posts.__enter__()
        self.addCleanup(self.posts.__exit__, None, None, None)

        def close():
            self.w.modified = False
            for k in ('lots/modele', 'lots/post', 'lots/remplacer', 'lots/dossier'):
                self.w.settings.remove(k)
            self.w.close()
            app.processEvents()
        self.addCleanup(close)

    def test_batch_window_writes_the_programs(self):
        (self.tmp / 'dessins').mkdir()
        write_drawing(self.tmp / 'dessins' / 'a.vdz')
        write_drawing(self.tmp / 'dessins' / 'b.vdz')
        with mock.patch('vectordrive.cam.templates.all_templates', lambda: {'M 1027': ('utilisateur', template())}):
            dlg = self.w.batch_dialog(exec_dialog=False)
        self.addCleanup(dlg.deleteLater)
        self.assertFalse(dlg.replace.isEnabled())                             # sans modèle : rien à remplacer
        dlg.template.setCurrentIndex(dlg.template.findData('M 1027'))
        self.assertTrue(dlg.replace.isEnabled())
        dlg.post.setCurrentIndex(dlg.post.findData('essai'))
        dlg.add_paths([str(self.tmp / 'dessins')])
        dlg.out.setText(str(self.tmp / 'sortie'))
        res = dlg.programs()
        self.assertEqual(len(res.done), 2)
        self.assertTrue((self.tmp / 'sortie' / 'b.nc').exists())
        self.assertIn('2 programme(s) écrit(s)', dlg.report.toPlainText())
        self.assertEqual(self.w.settings.value('lots/modele'), 'M 1027')
        self.assertEqual(self.w.settings.value('lots/post'), 'essai')

    def test_in_the_setup_menu(self):
        seen = []

        class Menu(QMenu):                                                    # le menu montré : ses commandes lues
            def exec(self, *_a):
                seen.extend(x.text() for x in self.actions())
        with mock.patch('PySide6.QtWidgets.QMenu', Menu):
            self.w.cam_panel.setup_menu()
        self.assertIn("Programmes en série (modèle d'usinage)…", seen)


if __name__ == '__main__':
    unittest.main()
