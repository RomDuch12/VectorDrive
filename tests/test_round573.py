"""Round 573 : VND — couleurs des outils du dessin reportées dans la table des outils de TypeEdit (fin de
document) ; une fin de document déjà à ces couleurs reste identique."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.core import geom
from vectordrive.core.document import Document, Shape, Tool
from vectordrive.io import vnd, vnd_write


def write_read(doc) -> Document:
    data, _rep = vnd_write.write_document(doc)
    f = pathlib.Path(tempfile.mkdtemp()) / 'x.vnd'
    f.write_bytes(data)
    return vnd.read(f)


class TestToolColors(unittest.TestCase):
    def test_written_and_read(self):
        d = Document()
        d.tools = [Tool(0, '#000000'), Tool(3, '#ff8000'), Tool(5, '#00a000')]
        d.layers[0].items = [Shape(path=geom.Path([geom.rect(0, 0, 10, 10)]), tool=3),
                             Shape(path=geom.Path([geom.circle((20, 5), 4)]), tool=5)]
        r = write_read(d)
        self.assertEqual(r.tool_color(3), '#ff8000')                         # dans le VND lui-même
        self.assertEqual(r.tool_color(5), '#00a000')
        self.assertEqual(write_read(r).tool_color(3), '#ff8000')             # relu puis réécrit

    def test_colorref(self):
        self.assertEqual(vnd.hex_colorref('#ff8000'), 0x0080FF)
        self.assertEqual(vnd.colorref_hex(vnd.hex_colorref('#123456')), '#123456')

    def test_unchanged_tail(self):
        base = vnd_write.default_template()
        root, _ar = vnd.parse(base)
        tail = base[root.fields['tail_offset']:]
        doc = Document()
        doc.tools = []                                                       # aucun outil : rien ne change
        self.assertIs(vnd_write.set_tool_colors(tail, doc), tail)
        f = pathlib.Path(tempfile.mkdtemp()) / 't.vnd'
        f.write_bytes(base)
        same = vnd.read(f)                                                   # ses propres couleurs : identique
        self.assertIs(vnd_write.set_tool_colors(tail, same), tail)


if __name__ == '__main__':
    unittest.main()
