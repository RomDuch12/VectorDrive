"""Round 757 : copier-coller avec TypeEdit, dans les deux sens (formats TypeEditZone et TypeEditZoneVersion)."""
import os
import struct
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import QMimeData
from PySide6.QtWidgets import QApplication

from vectordrive.core import fonts as F
from vectordrive.core import geom
from vectordrive.core import text as TX
from vectordrive.core.document import Group, Shape, Text
from vectordrive.io import te_clip

app = QApplication.instance() or QApplication([])


def square(x=0.0, y=0.0, side=10.0, **k):
    return Shape(path=geom.Path([geom.rect(x, y, side, side)]), **k)


def leaves(items):
    for it in items:
        if isinstance(it, Group):
            yield from leaves(it.children)
        else:
            yield it


class TestFormat(unittest.TestCase):
    def test_version_block(self):
        self.assertEqual(te_clip.VERSION, bytes.fromhex('01000000a3020000') + bytes(24))

    def test_mime_names(self):
        self.assertEqual(te_clip.MIME, 'application/x-qt-windows-mime;value="TypeEditZone"')
        self.assertEqual(te_clip.MIME_VERSION, 'application/x-qt-windows-mime;value="TypeEditZoneVersion"')

    def test_header_like_typeedit(self):
        d = te_clip.build([square()])
        self.assertEqual(struct.unpack_from('<I', d, 0)[0], 0)                # pas de police
        self.assertEqual(struct.unpack_from('<H', d, 4)[0], 1)                # un objet
        self.assertEqual(d[6:12 + 5], bytes.fromhex('ffff01000500') + b'CZone')   # une zone, en haut

    def test_shared_class_table(self):
        d = te_clip.build([square(), square(20)])
        self.assertEqual(struct.unpack_from('<H', d, 4)[0], 2)
        self.assertEqual(d.count(b'CZone'), 1)                                # classe écrite une seule fois
        self.assertEqual(d.count(b'CCourbe'), 1)

    def test_padded_like_typeedit(self):
        d = te_clip.build([square()])
        self.assertEqual(len(d) % 4096, 0)
        self.assertEqual(len(te_clip.read(d)[0]), 1)

    def test_nothing_to_write(self):
        with self.assertRaises(te_clip.ClipError):
            te_clip.build([])
        with self.assertRaises(te_clip.ClipError):
            te_clip.build([square(visible=False)])


class TestRoundTrip(unittest.TestCase):
    def test_coordinates_in_mm(self):
        items, report = te_clip.read(te_clip.build([square(5, 7, 10)]))
        self.assertEqual(report, [])
        bb = items[0].bbox()
        for a, b in zip(bb, (5, 7, 15, 17)):
            self.assertAlmostEqual(a, b, places=6)

    def test_open_and_closed(self):
        line = Shape(path=geom.Path([geom.polyline([(0, 0), (10, 5)], closed=False)]))
        items = te_clip.read(te_clip.build([line, square()]))[0]
        self.assertFalse(items[0].path.contours[0].closed)
        self.assertTrue(items[1].path.contours[0].closed)

    def test_holes_in_order(self):
        ring = Shape(path=geom.Path([geom.rect(0, 0, 30, 30), geom.circle((15, 15), 5)]))
        items = te_clip.read(te_clip.build([ring]))[0]
        self.assertEqual(len(items[0].path.contours), 2)

    def test_nested_groups(self):
        g = Group(children=[square(), Group(children=[square(20), square(40)])])
        items = te_clip.read(te_clip.build([g]))[0]
        self.assertEqual(len(list(leaves(items))), 3)
        self.assertIsInstance(items[0], Group)

    def test_many_objects(self):
        src = [square(i * 12.0) for i in range(300)]
        self.assertEqual(len(te_clip.read(te_clip.build(src))[0]), 300)

    def test_too_many_objects_go_in_one_zone(self):
        with mock.patch.object(te_clip, 'MAX_OBJECTS', 5):
            d = te_clip.build([square(i * 12.0) for i in range(6)])
        self.assertEqual(struct.unpack_from('<H', d, 4)[0], 1)
        self.assertEqual(len(list(leaves(te_clip.read(d)[0]))), 6)

    def test_hidden_not_copied(self):
        items = te_clip.read(te_clip.build([square(), square(20, visible=False)]))[0]
        self.assertEqual(len(items), 1)

    def test_origin(self):
        items = te_clip.read(te_clip.build([square(100, 50)], origin=(100, 50)))[0]
        self.assertAlmostEqual(items[0].bbox()[0], 0, places=6)
        self.assertAlmostEqual(items[0].bbox()[1], 0, places=6)

    def test_source_untouched(self):
        src = square(5, 5)
        te_clip.build([src], origin=(1, 1))
        self.assertAlmostEqual(src.bbox()[0], 5)

    def test_tool_not_carried(self):
        items = te_clip.read(te_clip.build([square(tool=7)]))[0]
        self.assertNotEqual(getattr(items[0], 'tool', 0), 7)


@unittest.skipUnless(F.is_available('Arial'), 'police Arial absente')
class TestTexts(unittest.TestCase):
    def text(self, s='Abc'):
        t = Text(text=s, font='Arial', size=5.0)
        t.outline = TX.outline_for(t)
        return t

    def test_stays_a_text(self):
        d = te_clip.build([self.text()])
        self.assertEqual(struct.unpack_from('<I', d, 0)[0], 1)
        self.assertEqual(d[4:9], b'Arial')
        items = te_clip.read(d)[0]
        self.assertIsInstance(items[0], Text)
        self.assertEqual((items[0].text, items[0].font), ('Abc', 'Arial'))

    def test_read_drops_table_dependency(self):
        d = te_clip.build([self.text()])
        t = te_clip.read(d)[0][0]
        self.assertNotIn('vnd_obj', t.extra)                                  # sa table n'est pas celle du dessin


class TestBadData(unittest.TestCase):
    def test_short(self):
        for d in (b'', b'\0' * 5):
            with self.assertRaises(te_clip.ClipError):
                te_clip.read(d)

    def test_font_table_too_long(self):
        with self.assertRaises(te_clip.ClipError):
            te_clip.read(struct.pack('<I', 0x7FFFFFFF) + bytes(64))
        with self.assertRaises(te_clip.ClipError):
            te_clip.read(struct.pack('<I', 3) + bytes(70))

    def test_no_object(self):
        self.assertEqual(te_clip.read(bytes(10))[0], [])

    def test_truncated_never_crashes(self):
        d = te_clip.build([square(), Group(children=[square(20)])])
        end = len(d.rstrip(b'\0'))
        for cut in range(0, end, 17):
            try:
                te_clip.read(d[:cut])
            except te_clip.ClipError:
                pass

    def test_noise_never_crashes(self):
        import random
        rnd = random.Random(757)
        for _ in range(40):
            blob = struct.pack('<IH', 0, rnd.randint(1, 5)) + bytes(rnd.randrange(256) for _ in range(rnd.randint(0, 300)))
            try:
                te_clip.read(blob)
            except te_clip.ClipError:
                pass


class TestWindow(unittest.TestCase):
    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.cb = QApplication.clipboard()
        self.cb.clear()

    def tearDown(self):
        for t in self.w.docs:
            t.modified = False
        self.w.modified = False
        self.w.close()
        self.cb.clear()

    def te_copy(self, *items, data=None):
        md = QMimeData()
        md.setData(te_clip.MIME, data if data is not None else te_clip.build(list(items)))
        md.setData(te_clip.MIME_VERSION, te_clip.VERSION)
        self.cb.setMimeData(md)

    def top(self):
        return self.w.canvas.doc.layers[0].items

    def test_copy_offers_the_te_formats(self):
        s = square(5, 5)
        self.top().append(s)
        self.w.canvas.selection = [s]
        self.w.copy()
        md = self.cb.mimeData()
        self.assertTrue(md.hasFormat(te_clip.MIME))
        self.assertEqual(bytes(md.data(te_clip.MIME_VERSION)), te_clip.VERSION)
        self.assertAlmostEqual(te_clip.read(bytes(md.data(te_clip.MIME)))[0][0].bbox()[0], 5, places=6)
        self.assertTrue(md.hasFormat('image/svg+xml'))                        # Inkscape et les autres : comme avant

    def test_copy_keeps_origin_as_te_zero(self):
        s = square(105, 55)
        self.top().append(s)
        self.w.canvas.doc.extra['origine'] = (100.0, 50.0)
        self.w.canvas.selection = [s]
        self.w.copy()
        got = te_clip.read(bytes(self.cb.mimeData().data(te_clip.MIME)))[0][0]
        self.assertAlmostEqual(got.bbox()[0], 5, places=6)

    def test_own_copy_stays_internal(self):
        s = square(5, 5, name='Moi', filled=True, tool=3)
        self.top().append(s)
        self.w.canvas.selection = [s]
        self.w.copy()
        n = len(self.top())
        self.w.paste()
        self.assertEqual(len(self.top()), n + 1)
        self.assertTrue(self.top()[-1].filled)                                # pas repassé par le format TypeEdit
        self.assertEqual(self.top()[-1].tool, 3)

    def test_paste_te_copy(self):
        self.te_copy(square(5, 7))
        self.w.canvas.current_tool_index = 2
        self.w.paste()
        got = self.top()[-1]
        self.assertAlmostEqual(got.bbox()[0], 5, places=6)                    # à sa place
        self.assertEqual(got.tool, 2)                                         # outil courant
        self.assertEqual(self.w.canvas.selection, [got])
        self.assertIn('TypeEdit', self.w.statusBar().currentMessage())

    def test_paste_te_copy_undo(self):
        self.te_copy(square(5, 7))
        n = len(self.top())
        self.w.paste()
        self.assertEqual(len(self.top()), n + 1)
        self.w.undo()
        self.assertEqual(len(self.w.canvas.doc.layers[0].items), n)

    def test_te_copy_replaces_an_older_one(self):
        old = square(100, 100)
        self.top().append(old)
        self.w.canvas.selection = [old]
        self.w.copy()
        self.te_copy(square(1, 1))
        self.w.paste()
        self.assertAlmostEqual(self.top()[-1].bbox()[0], 1, places=6)

    def test_paste_twice(self):
        self.te_copy(square(1, 1))
        n = len(self.top())
        self.w.paste()
        self.w.paste()
        self.assertEqual(len(self.top()), n + 2)
        self.assertIsNot(self.top()[-1], self.top()[-2])

    def test_origin_on_paste(self):
        self.w.canvas.doc.extra['origine'] = (100.0, 50.0)
        self.te_copy(square(5, 5))
        self.w.paste()
        self.assertAlmostEqual(self.top()[-1].bbox()[0], 105, places=6)
        self.assertAlmostEqual(self.top()[-1].bbox()[1], 55, places=6)

    def test_unreadable_pastes_nothing(self):
        old = square(100, 100)
        self.top().append(old)
        self.w.canvas.selection = [old]
        self.w.copy()
        self.te_copy(data=struct.pack('<I', 0x7FFFFFFF) + bytes(64))
        n = len(self.top())
        self.w.paste()
        self.assertEqual(len(self.top()), n)                                  # surtout pas l'ancienne copie
        self.assertIn('illisible', self.w.statusBar().currentMessage())

    def test_paste_at(self):
        self.te_copy(square(5, 5))
        got = self.w.paste_at((50.0, 60.0))
        self.assertEqual(len(got), 1)
        self.assertAlmostEqual(got[0].bbox()[0], 50, places=6)
        self.assertAlmostEqual(got[0].bbox()[1], 60, places=6)

    def test_other_vectordrive_is_not_ours(self):
        s = square(5, 5)
        self.top().append(s)
        self.w.canvas.selection = [s]
        self.w.copy()
        md = QMimeData()
        md.setData(self.w.CLIP_MARK, b'1:2')                                  # marque d'une autre fenêtre
        md.setData(te_clip.MIME, te_clip.build([square(33, 33)]))
        self.cb.setMimeData(md)
        self.w.paste()
        self.assertAlmostEqual(self.top()[-1].bbox()[0], 33, places=6)

    def test_svg_from_elsewhere_still_works(self):
        md = QMimeData()
        md.setData('image/svg+xml', b'<svg xmlns="http://www.w3.org/2000/svg" width="10mm" height="10mm" viewBox="0 0 10 10">'
                                    b'<rect width="5" height="5"/></svg>')
        self.cb.setMimeData(md)
        n = len(self.top())
        self.w.paste()
        self.assertEqual(len(self.top()), n + 1)


if __name__ == '__main__':
    unittest.main()
