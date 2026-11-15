"""Round 547 : couleurs gardées — symboles SMB (bloc VDSMBCOL ignoré par TypeEdit), VND (un calque
TypeEdit par outil), pose d'un symbole et import d'un dessin (couleurs reprises par le dessin)."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.core import geom
from vectordrive.core.document import Document, Group, Shape, Tool
from vectordrive.io import registry, smb


def colored() -> Document:
    d = Document()
    d.tools = [Tool(0, '#000000'), Tool(3, '#ff0000'), Tool(5, '#00a000')]
    d.layers[0].items = [Shape(path=geom.Path([geom.rect(0, 0, 10, 10)]), tool=3),
                         Shape(path=geom.Path([geom.circle((20, 5), 4)]), tool=5),
                         Group(children=[Shape(path=geom.Path([geom.rect(30, 0, 2, 2)]), tool=3),
                                         Shape(path=geom.Path([geom.rect(40, 0, 2, 2)]), tool=0)])]
    return d


class TestColors(unittest.TestCase):
    def setUp(self):
        self.t = pathlib.Path(tempfile.mkdtemp())

    def test_smb_block(self):
        d = colored()
        items = d.layers[0].items
        f = self.t / 's.smb'
        smb.write(items, f, tools=d.tool_colors(items))
        data = f.read_bytes()
        self.assertIn(smb.COLORS_MAGIC, data)
        self.assertEqual(smb.rewrite(data), data)                         # archive TypeEdit intacte
        g = smb.as_group(f)
        self.assertEqual([c.tool for c in g.children[:2]], [3, 5])
        self.assertEqual([c.tool for c in g.children[2].children], [3, 0])
        self.assertEqual(g.extra['tool_colors'][3], '#ff0000')
        doc = smb.read(f)
        self.assertEqual(doc.tool_color(5), '#00a000')

    def test_smb_without_block(self):
        f = self.t / 'n.smb'
        smb.write([Shape(path=geom.Path([geom.rect(0, 0, 5, 5)]))], f)
        self.assertNotIn(smb.COLORS_MAGIC, f.read_bytes())               # rien d'ajouté sans couleur
        self.assertNotIn('tool_colors', smb.as_group(f).extra)            # couleur du calque où on le pose

    def test_export_smb(self):
        f = self.t / 'e.smb'
        registry.save_document(colored(), f)
        r = registry.open_document(f)
        items = [it for L in r.layers for it in L.items]
        self.assertEqual(sorted(set(r.tool_colors(items).values())), ['#000000', '#00a000', '#ff0000'])

    def test_vnd_one_layer_per_tool(self):
        f = self.t / 'x.vnd'
        registry.save_document(colored(), f)
        r = registry.open_document(f)
        tools = sorted({lf.tool for L in r.layers for it in L.items
                        for lf in (it.children if isinstance(it, Group) else [it])})
        self.assertIn(3, tools)
        self.assertIn(5, tools)
        self.assertEqual(r.layers[0].name, 'Plan 1')

    def test_adopt(self):
        target = Document()
        target.tools = [Tool(0, '#000000'), Tool(1, '#ff0000'), Tool(3, '#123456')]
        target.layers[0].items = [Shape(path=geom.Path([geom.rect(0, 0, 1, 1)]), tool=3)]
        a = Shape(path=geom.Path([geom.rect(0, 0, 1, 1)]), tool=3)            # rouge là-bas
        b = Shape(path=geom.Path([geom.rect(0, 0, 1, 1)]), tool=5)            # vert, outil 5 libre ici
        c = Shape(path=geom.Path([geom.rect(0, 0, 1, 1)]), tool=0)            # noir : déjà pareil
        remap = target.adopt_tool_colors([a, b, c], {3: '#ff0000', 5: '#00a000', 0: '#000000'})
        self.assertEqual(remap, {3: 1})
        self.assertEqual((a.tool, b.tool, c.tool), (1, 5, 0))
        self.assertEqual(target.tool_color(5), '#00a000')
        self.assertEqual(target.tool_color(3), '#123456')                     # l'outil du dessin n'a pas bougé
        d = Shape(path=geom.Path([geom.rect(0, 0, 1, 1)]), tool=3)            # couleur nouvelle, outil 3 pris
        target.adopt_tool_colors([d], {3: '#abcdef'})
        self.assertNotEqual(d.tool, 3)
        self.assertEqual(target.tool_color(d.tool), '#abcdef')

    def test_place_symbol_keeps_colors(self):
        from PySide6.QtWidgets import QApplication
        QApplication.instance() or QApplication([])
        from vectordrive.ui.main_window import MainWindow
        d = colored()
        f = self.t / 'c.smb'
        smb.write(d.layers[0].items, f, tools=d.tool_colors(d.layers[0].items))
        w = MainWindow()
        try:
            w.canvas.doc.tools = [Tool(0, '#000000'), Tool(3, '#0000ff')]
            w.canvas.doc.add(Shape(path=geom.Path([geom.rect(0, 0, 1, 1)]), tool=3))
            w.insert_symbol(str(f), (0.0, 0.0))
            g = w.canvas.selection[0]
            first = g.children[0]
            self.assertEqual(w.canvas.doc.tool_color(first.tool), '#ff0000')   # rouge gardé
            self.assertEqual(w.canvas.doc.tool_color(3), '#0000ff')             # le bleu du dessin aussi
            self.assertNotIn('tool_colors', g.extra)
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
