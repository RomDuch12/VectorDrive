"""Round 1005 : la bibliothèque garde les couleurs (réponse 9 du 14/11) — un symbole écrit par VectorDrive garde la
couleur propre et le remplissage de ses objets, ses courbes sont écrites à la couleur de leur outil (TypeEdit les
montrait noires) ; les symboles créés s'écrivent en SMB, en DXF, dans les deux, ou en VDZ, au choix."""
import os
import pathlib
import struct
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1005.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication, QFileDialog  # noqa: E402

from vectordrive.core import geom  # noqa: E402
from vectordrive.core import text as TX  # noqa: E402
from vectordrive.core.document import OWN_COLOR, Document, Group, Shape, Text, own_color  # noqa: E402
from vectordrive.core.geom import Affine  # noqa: E402
from vectordrive.io import smb  # noqa: E402

app = QApplication.instance() or QApplication([])
TOOLS = {0: '#000000', 1: '#ff0000', 2: '#00a000'}


def shape(k, tool=0, **kw):
    return Shape(path=geom.Path([geom.rect(30 * k, 0, 20, 14)]), tool=tool, **kw)


def leaves(items):
    for it in items:
        if isinstance(it, Group):
            yield from leaves(it.children)
        else:
            yield it


def back(items, tools=TOOLS, **kw):
    """Le symbole écrit puis relu : (ses objets, le document relu)."""
    tmp = pathlib.Path(tempfile.mkdtemp(prefix='vd1005_')) / 'essai.smb'
    smb.write(items, tmp, tools=tools, **kw)
    doc = smb.read(tmp)
    return list(leaves(doc.layers[0].items)), doc, tmp.read_bytes()


class Colours(unittest.TestCase):

    def test_own_colour_and_fill_come_back(self):
        a, b, c = shape(0), shape(1, tool=1), shape(2, tool=2, filled=True)
        b.extra[OWN_COLOR] = '#3366cc'
        got, doc, _data = back([a, b, c])
        self.assertEqual([it.tool for it in got], [0, 1, 2])
        self.assertEqual([own_color(it) for it in got], [None, '#3366cc', None])    # la couleur propre
        self.assertEqual([it.filled for it in got], [False, False, True])           # le remplissage
        self.assertEqual({t.index: t.color for t in doc.tools if t.index in TOOLS}, TOOLS)

    def test_curves_written_in_their_colour(self):
        a, b, c = shape(0), shape(1, tool=1), shape(2, tool=2)
        c.extra[OWN_COLOR] = '#3366cc'
        got, _doc, _data = back([a, b, c])
        seen = [it.extra['te_color'][0].lower() for it in got]      # la couleur que TypeEdit montre
        self.assertEqual(seen, ['#000000', '#ff0000', '#3366cc'])   # avant : tout en noir

    def test_block_stays_readable_by_older_versions(self):
        _got, _doc, data = back([shape(0), shape(1, tool=1)])
        root, _fonts, ar = smb.parse(data)
        block = smb.read_colors(data, ar.pos)
        self.assertEqual(block['v'], 1)                             # rien de plus à dire : le bloc d'avant
        self.assertNotIn('objets', block)
        filled = shape(1, tool=1, filled=True)
        _got, _doc, data = back([shape(0), filled])
        root, _fonts, ar = smb.parse(data)
        block = smb.read_colors(data, ar.pos)
        self.assertEqual((block['v'], block['zones'], block['objets']), (2, [0, 1], [[{}], [{'f': 1}]]))
        _got, _doc, data = back([shape(0, filled=True)], tools={})  # outil 0 seul, mais rempli : le bloc est écrit
        root, _fonts, ar = smb.parse(data)
        self.assertEqual(smb.read_colors(data, ar.pos)['objets'], [[{'f': 1}]])
        self.assertEqual(struct.unpack_from('<I', data, 0)[0], smb.MAGIC)

    def test_a_group_and_a_text_in_curves(self):
        g = Group(children=[shape(0, tool=1, filled=True), shape(1, tool=2)])
        g.children[1].extra[OWN_COLOR] = '#aa5500'
        t = Text(text='AB', font='VD Trait', size=8, matrix=Affine.translation(0, 40), tool=1)
        t.outline = TX.outline_for(t)
        t.extra[OWN_COLOR] = '#112233'
        got, _doc, _data = back([g, t], live_texts=False)
        self.assertEqual([it.filled for it in got[:2]], [True, False])
        self.assertEqual(own_color(got[1]), '#aa5500')
        self.assertGreaterEqual(len(got), 3)
        self.assertTrue(all(own_color(it) == '#112233' for it in got[2:]))   # chaque courbe du texte : sa couleur

    def test_option_off_writes_no_block(self):
        was = smb.KEEP_COLORS
        self.addCleanup(setattr, smb, 'KEEP_COLORS', was)
        smb.KEEP_COLORS = False
        got, _doc, data = back([shape(0, tool=1, filled=True)])
        self.assertNotIn(smb.COLORS_MAGIC, data)
        self.assertEqual(got[0].extra['te_color'][0].lower(), '#ff0000')    # la couleur des courbes, elle, y est


class Formats(unittest.TestCase):

    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix='vd1005_'))
        self.w = MainWindow()
        self.w.settings.remove('symboles/format')
        self.addCleanup(self.close)
        doc = self.w.canvas.doc
        self.items = [shape(0), shape(1, tool=1, filled=True)]
        self.items[0].extra[OWN_COLOR] = '#3366cc'
        for it in self.items:
            doc.add(it)
        self.w.canvas.select(self.items)

    def close(self):
        self.w.settings.remove('symboles/format')
        self.w.modified = False
        self.w.close()

    def names(self):
        return sorted(p.name for p in self.tmp.iterdir())

    def test_default_smb_and_the_choice(self):
        from vectordrive.ui import options as O
        o = O.BY_KEY['symboles/format']
        self.assertEqual((o.default, [k for k, _l in o.choices]), ('smb', ['smb', 'dxf', 'smb+dxf', 'vdz']))
        self.assertEqual(self.w.symbol_formats(), ['.smb'])
        got = self.w.add_selection_to_library(str(self.tmp), 'essai', fallback=False)
        self.assertEqual((pathlib.Path(got).name, self.names()), ('essai.smb', ['essai.smb']))

    def test_both_formats_under_one_free_name(self):
        self.w.settings.setValue('symboles/format', 'smb+dxf')
        (self.tmp / 'essai.dxf').write_text('déjà là', encoding='utf-8')     # le nom est pris en DXF seulement
        got = self.w.add_selection_to_library(str(self.tmp), 'essai', fallback=False)
        self.assertEqual(pathlib.Path(got).name, 'essai (2).smb')
        self.assertEqual(self.names(), ['essai (2).dxf', 'essai (2).smb', 'essai.dxf'])
        self.assertIn('essai (2).dxf', self.w.statusBar().currentMessage())
        from vectordrive.ui.symbols import file_as_group
        g = file_as_group(str(self.tmp / 'essai (2).dxf'))          # la Bibliothèque le lit
        self.assertEqual(len(list(leaves([g]))), 2)

    def test_dxf_alone_and_vdz(self):
        self.w.settings.setValue('symboles/format', 'dxf')
        got = self.w.add_selection_to_library(str(self.tmp), 'trait', fallback=False)
        self.assertEqual((pathlib.Path(got).name, self.names()), ('trait.dxf', ['trait.dxf']))
        self.w.settings.setValue('symboles/format', 'vdz')
        self.w.add_selection_to_library(str(self.tmp), 'tout', fallback=False)
        self.assertIn('tout.vdz', self.names())
        from vectordrive.ui.symbols import file_as_group
        got = list(leaves([file_as_group(str(self.tmp / 'tout.vdz'))]))
        self.assertEqual(sorted(own_color(it) or '' for it in got), ['', '#3366cc'])   # tout est gardé
        self.assertEqual(sorted(it.filled for it in got), [False, True])

    def test_create_a_symbol_follows_the_format(self):
        self.w.settings.setValue('symboles/format', 'smb+dxf')
        out = self.tmp / 'logo.smb'
        with mock.patch.object(QFileDialog, 'getSaveFileName', return_value=(str(out), '')) as ask:
            self.w.save_as_symbol()
        self.assertIn('*.smb', ask.call_args[0][3])
        self.assertEqual(self.names(), ['logo.dxf', 'logo.smb'])
        self.w.settings.setValue('symboles/format', 'dxf')
        with mock.patch.object(QFileDialog, 'getSaveFileName', return_value=(str(self.tmp / 'seul'), '')) as ask:
            self.w.save_as_symbol()
        self.assertIn('*.dxf', ask.call_args[0][3])
        self.assertIn('seul.dxf', self.names())                     # l'extension du format, ajoutée

    def test_the_note_about_texts(self):
        t = Text(text='Plaque', font='VD Trait', size=8, matrix=Affine.translation(0, 40))
        t.outline = TX.outline_for(t)
        self.w.canvas.doc.add(t)
        self.w.canvas.select([t])
        self.w.settings.setValue('symboles/textes_vivants', False)
        self.addCleanup(self.w.settings.remove, 'symboles/textes_vivants')
        self.w.add_selection_to_library(str(self.tmp), 'a', fallback=False)
        self.assertIn('courbes', self.w.statusBar().currentMessage())
        self.w.settings.setValue('symboles/format', 'dxf')          # en DXF : pas de note sur les textes TypeEdit
        self.w.add_selection_to_library(str(self.tmp), 'b', fallback=False)
        self.assertNotIn('courbes', self.w.statusBar().currentMessage())


if __name__ == '__main__':
    unittest.main()
