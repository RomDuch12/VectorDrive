"""Round 868 : la couleur qu'une courbe a dans TypeEdit (mesuré sur TE13 : la 3e valeur de la fin de courbe) et les propriétés
de ses contours, gardées quand VectorDrive réécrit le VND."""
import json
import os
import pathlib
import struct
import tempfile
import types
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', os.path.join(tempfile.mkdtemp(), 'session'))
os.environ.setdefault('VECTORDRIVE_NO_TYPEEDIT', '1')

from vectordrive.core import geom
from vectordrive.core.document import Document, Group, Layer, Plate, Shape, Text, Tool
from vectordrive.io import native, svg, te_clip, vnd
from vectordrive.io import vnd_write as VW


def square(x=0.0, y=0.0, side=10.0, **kw):
    return Shape(path=geom.Path([geom.polyline([(x, y), (x + side, y), (x + side, y + side), (x, y + side)], closed=True)]), **kw)


def trailer(color):
    c = vnd.hex_colorref(color)
    return struct.pack('<6I', 0, 0, c, 0, 4, c)


def leaves(items):
    for it in items:
        if isinstance(it, Group):
            yield from leaves(it.children)
        else:
            yield it


def tree_courbes(data):
    root, _ar = vnd.parse(data)
    out = []

    def walk(o):
        if o.cls.name == 'CCourbe':
            out.append(o)
        for c in o.children:
            walk(c)
    walk(root)
    return out


FILLED = {'color': 0xFFFFFF, 'fill_color': 0xFFFFFF, 'f40': 2, 'f44': 1, 'f20_2c': [5, 12, 0, 4],
          'f80_98': (0.0, 45.0, 0.0, 45.0), 'f10': struct.unpack('<Q', struct.pack('<d', 0.001))[0]}


class TEFile:
    """Un VND comme TypeEdit en écrit : la courbe de couleur 'a', la noire 'b', sur l'outil 2, et 'b' a des contours aux propriétés
    marquées. Rien d'un vrai fichier : mes propres carrés."""

    def __enter__(self):
        real = VW._courbe

        def patched(shape):
            cb = real(shape)
            marks = shape.extra if isinstance(shape.extra, dict) else {}
            if marks.get('mark_trailer'):
                cb.fields['trailer'] = marks['mark_trailer']
            if marks.get('mark_props'):
                for co in cb.children:
                    co.fields['ext_obj'].fields.update(marks['mark_props'])
            return cb
        doc = Document()
        doc.plate = Plate(width=100.0, height=50.0)
        doc.tools = [Tool(0, '#000000', 'Outil 1'), Tool(1, '#ff0000', 'Outil 2'), Tool(2, '#00ff00', 'Outil 3')]
        a = square(0, 0, extra={'mark_trailer': trailer('#ff6400')}, tool=2)
        b = square(20, 0, extra={'mark_props': FILLED, 'mark_trailer': VW.COURBE_TRAILER}, tool=2)
        white = square(40, 0, extra={'mark_trailer': trailer('#ffffff')}, tool=2)
        doc.layers = [Layer(name='A', items=[a, b, white], tool=2)]
        doc.active = doc.layers[0].id
        with mock.patch.object(VW, '_courbe', patched):
            data = VW.write_document(doc)[0]
        self.dir = tempfile.TemporaryDirectory()
        self.path = pathlib.Path(self.dir.name) / 'te.vnd'
        self.path.write_bytes(data)
        return self

    def __exit__(self, *a):
        self.dir.cleanup()

    def read(self):
        return vnd.read(str(self.path))


def changed(doc):
    """La structure a changé : l'arbre est récrit, avec la fin de la source."""
    doc.layers[0].items.append(square(60, 0, tool=doc.layers[0].tool))
    return doc


class TestReading(unittest.TestCase):

    def test_the_color_of_each_curve(self):
        with TEFile() as f:
            doc = f.read()
        a, b, white = list(leaves(doc.layers[0].items))
        self.assertEqual(a.extra['te_color'], ['#ff6400', 2])
        self.assertEqual(b.extra['te_color'], ['#000000', 2])
        self.assertEqual(white.extra['te_color'], ['#ffffff', 2])

    def test_it_is_shown_as_in_typeedit(self):
        with TEFile() as f:
            doc = f.read()
        a, b, white = list(leaves(doc.layers[0].items))
        self.assertEqual(doc.item_color(a), '#ff6400')

    def test_without_its_own_color_the_tool_gives_it(self):
        with TEFile() as f:
            doc = f.read()
        _a, b, _white = list(leaves(doc.layers[0].items))
        self.assertEqual(doc.item_color(b), '#00ff00')

    def test_a_white_curve_stays_visible(self):
        with TEFile() as f:
            doc = f.read()
        white = list(leaves(doc.layers[0].items))[2]
        self.assertEqual(doc.item_color(white), '#00ff00')

    def test_another_tool_takes_over(self):
        with TEFile() as f:
            doc = f.read()
        a = list(leaves(doc.layers[0].items))[0]
        a.tool = 1
        self.assertEqual(doc.item_color(a), '#ff0000')

    def test_a_plain_item_has_the_color_of_its_tool(self):
        doc = Document()
        doc.tools = [Tool(0, '#123456', 'Outil 1')]
        self.assertEqual(doc.item_color(square()), '#123456')

    def test_the_properties_are_shared_on_a_big_file(self):
        with TEFile() as f:
            doc = f.read()
        a, b, white = list(leaves(doc.layers[0].items))
        self.assertIs(a.extra['vnd']['props'].rows[0], white.extra['vnd']['props'].rows[0])
        self.assertIsNot(a.extra['vnd']['props'].rows[0], b.extra['vnd']['props'].rows[0])


class TestRewriting(unittest.TestCase):

    def rewritten(self):
        with TEFile() as f:
            doc = changed(f.read())
            data = VW.write_document(doc)[0]
        return tree_courbes(data)

    def test_the_end_of_the_curve_comes_back(self):
        got = self.rewritten()
        self.assertEqual(got[0].fields['trailer'], trailer('#ff6400'))
        self.assertEqual(got[1].fields['trailer'], VW.COURBE_TRAILER)
        self.assertEqual(got[2].fields['trailer'], trailer('#ffffff'))

    def test_the_properties_of_the_contours_come_back(self):
        fields = self.rewritten()[1].children[0].fields['ext']
        for k, v in FILLED.items():
            self.assertEqual(fields[k] if k != 'f80_98' else tuple(fields[k]), v, k)

    def test_the_other_contours_keep_the_defaults(self):
        fields = self.rewritten()[0].children[0].fields['ext']
        self.assertEqual(fields['f40'], 4)
        self.assertEqual(fields['color'], 0)

    def test_a_new_curve_takes_the_color_of_its_tool(self):
        self.assertEqual(self.rewritten()[3].fields['trailer'], trailer('#00ff00'))

    def test_a_curve_moved_to_another_tool(self):
        with TEFile() as f:
            doc = f.read()
            a = doc.layers[0].items[0]
            for leaf in leaves([a]):
                leaf.tool = 1
            doc.extra.pop('vnd_signature', None)
            got = tree_courbes(VW.write_document(doc)[0])
        self.assertIn(trailer('#ff0000'), [c.fields['trailer'] for c in got])
        self.assertNotIn(trailer('#ff6400'), [c.fields['trailer'] for c in got])

    def test_a_moved_curve_keeps_its_color(self):
        with TEFile() as f:
            doc = changed(f.read())
            doc.layers[0].items[0] = doc.layers[0].items[0].transformed(geom.Affine.translation(1.0, 1.0))
            got = tree_courbes(VW.write_document(doc)[0])
        self.assertEqual(got[0].fields['trailer'], trailer('#ff6400'))

    def test_another_number_of_contours_falls_back_on_the_defaults(self):
        with TEFile() as f:
            doc = changed(f.read())
            b = list(leaves(doc.layers[0].items))[1]
            b.path = geom.Path(list(b.path.contours) + [geom.polyline([(0, 30), (5, 30), (5, 35)], closed=True)])
            got = tree_courbes(VW.write_document(doc)[0])
        self.assertEqual(got[1].children[0].fields['ext']['f40'], 4)
        self.assertEqual(len(got[1].children), 2)

    def test_a_clone_keeps_its_color(self):
        with TEFile() as f:
            doc = f.read()
        a = list(leaves(doc.layers[0].items))[0]
        self.assertEqual(doc.item_color(a.clone()), '#ff6400')

    def test_an_untouched_file_is_given_back_as_it_was(self):
        with TEFile() as f:
            self.assertEqual(VW.write_document(f.read())[0], f.path.read_bytes())

    def test_the_file_is_read_again_with_its_colors(self):
        with TEFile() as f:
            doc = changed(f.read())
            data = VW.write_document(doc)[0]
            again = pathlib.Path(f.dir.name) / 'b.vnd'
            again.write_bytes(data)
            doc2 = vnd.read(str(again))
        self.assertEqual(list(leaves(doc2.layers[0].items))[0].extra['te_color'], ['#ff6400', 2])


class TestNames(unittest.TestCase):

    def round_trip(self, *items, keep=False):
        doc = Document()
        doc.plate = Plate(width=100.0, height=50.0)
        doc.layers = [Layer(name='A', items=list(items))]
        doc.active = doc.layers[0].id
        with tempfile.TemporaryDirectory() as d:
            path = pathlib.Path(d) / 'a.vnd'
            path.write_bytes(VW.write_document(doc)[0])
            first = vnd.read(str(path))
            if keep:
                first.extra.pop('vnd_signature', None)
                path.write_bytes(VW.write_document(first)[0])
                return vnd.read(str(path))
            return first

    def test_a_curve(self):
        got = self.round_trip(square(name='Trait'), square(20, 0))
        self.assertEqual(got.layers[0].items[0].name, 'Trait')

    def test_a_group(self):
        got = self.round_trip(Group(children=[square(), square(20, 0)], name='Ensemble'))
        self.assertEqual(got.layers[0].items[0].name, 'Ensemble')

    def test_a_zone_around_a_single_object(self):
        s = square(extra={'vnd': {'wraps': 2, 'zone_names': {2: 'Logo'}}})
        got = self.round_trip(s, keep=True)
        vx = got.layers[0].items[0].extra['vnd']
        self.assertEqual(vx['wraps'], 2)
        self.assertEqual(vx['zone_names'], {2: 'Logo'})

    def test_after_a_native_file_the_key_is_text(self):
        s = square(extra={'vnd': {'wraps': 1, 'zone_names': {'1': 'Logo'}}})
        got = self.round_trip(s)
        self.assertEqual(got.layers[0].items[0].extra['vnd']['zone_names'], {1: 'Logo'})

    def test_no_name_writes_no_name(self):
        got = self.round_trip(square())
        self.assertEqual(got.layers[0].items[0].name, '')
        self.assertNotIn('zone_names', got.layers[0].items[0].extra['vnd'])


class TestNewDrawings(unittest.TestCase):

    def doc(self, *items):
        d = Document()
        d.plate = Plate(width=100.0, height=50.0)
        d.tools = [Tool(0, '#000000', 'Outil 1'), Tool(1, '#ff0000', 'Outil 2')]
        d.layers = [Layer(name='A', items=list(items))]
        d.active = d.layers[0].id
        return d

    def test_black_writes_no_color(self):
        self.assertEqual(tree_courbes(VW.write_document(self.doc(square()))[0])[0].fields['trailer'], VW.COURBE_TRAILER)

    def test_a_colored_tool_shows_in_typeedit(self):
        self.assertEqual(tree_courbes(VW.write_document(self.doc(square(tool=1)))[0])[0].fields['trailer'], trailer('#ff0000'))

    def test_a_tool_without_a_table_entry_takes_the_default(self):
        got = tree_courbes(VW.write_document(self.doc(square(tool=3)))[0])[0].fields['trailer']
        self.assertEqual(got, trailer(Document().tool_color(3)) if Document().tool_color(3) != '#000000' else VW.COURBE_TRAILER)

    def test_a_text_in_curves_takes_it_too(self):
        path = square().path
        t = Text(text='A', font='Inconnue', size=10.0, outline=path, tool=1)
        self.assertEqual(tree_courbes(VW.write_document(self.doc(t))[0])[0].fields['trailer'], trailer('#ff0000'))

    def test_a_strange_color_writes_no_color(self):
        d = self.doc(square(tool=1))
        d.tools[1].color = 'rouge'
        self.assertEqual(tree_courbes(VW.write_document(d)[0])[0].fields['trailer'], VW.COURBE_TRAILER)

    def test_the_context_is_given_back(self):
        VW.write_document(self.doc(square(tool=1)))
        self.assertIsNone(VW._TOOL_COLOR)


class TestClipboard(unittest.TestCase):

    def test_with_the_drawing(self):
        d = Document()
        d.tools = [Tool(0, '#000000', 'Outil 1'), Tool(1, '#ff0000', 'Outil 2')]
        self.assertIn(trailer('#ff0000'), te_clip.build([square(tool=1)], doc=d))

    def test_without_the_drawing(self):
        self.assertNotIn(trailer('#ff0000'), te_clip.build([square(tool=1)]))

    def test_a_copy_from_typeedit_keeps_its_color_on_the_current_tool(self):
        s = square(extra={'te_color': ['#ff6400', 0]})
        data = te_clip.build([s])
        items, _rep = te_clip.read(data)
        vnd._set_tool(items, 1)
        d = Document()
        d.tools = [Tool(0, '#000000', 'Outil 1'), Tool(1, '#ff0000', 'Outil 2')]
        self.assertEqual(d.item_color(list(leaves(items))[0]), '#ff6400')


class TestNativeFile(unittest.TestCase):

    def test_the_color_is_saved_but_not_the_properties(self):
        with TEFile() as f:
            doc = f.read()
        a = list(leaves(doc.layers[0].items))[0]
        out = native._item_out(a)
        self.assertEqual(out['extra']['te_color'], ['#ff6400', 2])
        self.assertIsNone(out['extra']['vnd'].get('props'))
        self.assertNotIn('trailer', out['extra']['vnd'])
        json.dumps(out['extra'])

    def test_it_comes_back_in_the_next_vnd(self):
        s = square(extra={'te_color': ['#ff6400', 1]}, tool=1)
        d = Document()
        d.tools = [Tool(0, '#000000', 'Outil 1'), Tool(1, '#ff0000', 'Outil 2')]
        d.plate = Plate(width=100.0, height=50.0)
        d.layers = [Layer(name='A', items=[s], tool=1)]
        d.active = d.layers[0].id
        self.assertEqual(tree_courbes(VW.write_document(d)[0])[0].fields['trailer'], trailer('#ff6400'))


class TestShownEverywhere(unittest.TestCase):

    def doc(self):
        d = Document()
        d.tools = [Tool(0, '#000000', 'Outil 1')]
        d.plate = Plate(width=100.0, height=50.0)
        d.layers = [Layer(name='A', items=[square(extra={'te_color': ['#ff6400', 0]})])]
        return d

    def test_on_the_canvas(self):
        from vectordrive.ui.canvas import Canvas
        d = self.doc()
        got = Canvas._color(types.SimpleNamespace(doc=d), d.layers[0].items[0])
        self.assertEqual(got, '#ff6400')

    def test_in_an_svg(self):
        path = pathlib.Path(tempfile.mkdtemp()) / 'x.svg'
        svg.write(self.doc(), path)
        self.assertIn('#ff6400', path.read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
