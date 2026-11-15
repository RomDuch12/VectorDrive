"""Round 23 : bibliothèque Gravotech (chaînes UTF-16), trous de perçage
(CTrou), réécriture à l'octet des VND inchangés."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from vectordrive.core import geom, holes
from vectordrive.core.document import Document, Shape
from vectordrive.core.geom import Affine, Path
from vectordrive.io import registry, smb, vnd, vnd_write
from vectordrive.io.mfc import Archive, WideStr
from tests.corpus import corpus

GANG = pathlib.Path('C:/ProgramData/Gravotech/TypeEdit_V15-LaserType_V15/GANGDRILL')
SYMB = pathlib.Path('C:/ProgramData/Gravotech/TypeEdit_V15-LaserType_V15/Symbols')
PERLIM = corpus('vnd_verite')


def sample(path):
    if not path.exists():
        raise unittest.SkipTest(f'{path.name} absent')
    return path


class TestWideStrings(unittest.TestCase):
    def test_utf16_string_round_trip(self):
        w = vnd_write.MfcWriter()
        w.cstring(WideStr('OBJETINFOS'))
        w.cstring('OBJETINFOS')
        data = bytes(w.buf)
        self.assertEqual(data[:4], b'\xff\xfe\xff\x0a')
        ar = Archive(data, 0, {})
        a, b = ar.cstring(), ar.cstring()
        self.assertIsInstance(a, WideStr)
        self.assertNotIsInstance(b, WideStr)
        w2 = vnd_write.MfcWriter()
        w2.cstring(a)
        w2.cstring(b)
        self.assertEqual(bytes(w2.buf), data)

    def test_gravotech_envelope_symbol_identical(self):
        f = sample(SYMB / 'TE15' / 'ENVELOPES' / 'arc.smb')
        d = f.read_bytes()
        self.assertEqual(smb.rewrite(d), d)


class TestHoles(unittest.TestCase):
    def test_read_gangdrill(self):
        for name in ('gangdrill_32mm.vnd', 'gangdrill_32mm.gvt'):
            with self.subTest(name):
                d = registry.open_document(sample(GANG / name))
                items = d.layers[0].items
                self.assertEqual(len(items), 23)
                self.assertTrue(all(holes.is_hole(it) for it in items))
                s = holes.spec_of(items[0])
                self.assertAlmostEqual(s.diameter, 4, places=9)
                self.assertAlmostEqual(s.depth, 10, places=9)
                self.assertEqual(holes.table(items), [(4.0, 10.0, 23)])
                self.assertEqual(d.report, [])

    def test_gangdrill_rewritten_identically_then_moved(self):
        f = sample(GANG / 'gangdrill_32mm.vnd')
        src = f.read_bytes()
        d = registry.open_document(f)
        data, _ = vnd_write.write_document(d)
        a = vnd.archive_start(src)
        self.assertEqual(data[a:], src[a:])
        d.layers[0].items[0] = d.layers[0].items[0].transformed(Affine.translation(10, 5))
        root, _ = vnd.parse(vnd_write.write_document(d)[0])
        zone = root.children[0].children[0]
        t = zone.children[0]
        self.assertEqual(t.cls.name, 'CTrou')
        self.assertEqual([round(v * 1000, 9) for v in t.fields['pos']], [17, 12, 0])
        self.assertEqual([round(v * 1000, 9) for v in zone.fields['bbox']], [15, 10, -10, 19, 14, 0])

    def test_new_holes_written_and_read_back(self):
        d = Document()
        d.add(holes.make((20, 30), holes.HoleSpec(diameter=6, depth=2.5)))
        d.add(Shape(path=Path([geom.rect(0, 0, 10, 10)])))
        data, _ = vnd_write.write_document(d)
        root, _ = vnd.parse(data)
        names = vnd.structure_signature(root)
        self.assertIn('CTrou', names)
        with tempfile.TemporaryDirectory() as tmp:
            f = pathlib.Path(tmp) / 't.vnd'
            f.write_bytes(data)
            back = registry.open_document(f)
        hs = [it for L in back.layers for it in L.items if holes.is_hole(it)]
        self.assertEqual(len(hs), 1)
        self.assertEqual(holes.circle_of(hs[0]), (20.0, 30.0, 3.0))
        self.assertAlmostEqual(holes.spec_of(hs[0]).depth, 2.5, places=9)

    def test_scaled_hole_and_square(self):
        h = holes.make((0, 0), holes.HoleSpec(4, 1)).transformed(Affine(2, 0, 0, 2, 0, 0))
        self.assertEqual(holes.circle_of(h), (0.0, 0.0, 4.0))
        sq = Shape(path=Path([geom.rect(0, 0, 4, 4)]))
        self.assertIsNone(holes.circle_of(sq))
        oval = holes.make((0, 0), holes.HoleSpec(4, 1)).transformed(Affine(2, 0, 0, 1, 0, 0))
        self.assertIsNone(vnd_write._trou(oval))         # ovale : écrit comme courbe

    def test_convert_circles(self):
        c = Shape(path=Path([geom.circle((5, 5), 1.5)]))
        sq = Shape(path=Path([geom.rect(0, 0, 4, 4)]))
        out = holes.convert([c, sq], holes.HoleSpec(8, 3), keep_diameter=True)
        self.assertEqual(list(out), [id(c)])
        self.assertAlmostEqual(holes.spec_of(out[id(c)]).diameter, 3, places=9)
        out = holes.convert([c], holes.HoleSpec(8, 3), keep_diameter=False)
        self.assertAlmostEqual(holes.spec_of(out[id(c)]).diameter, 8, places=9)


class TestUntouchedVnd(unittest.TestCase):
    def test_reference_identical(self):
        f = sample(PERLIM)
        src = f.read_bytes()
        data, _ = vnd_write.write_document(registry.open_document(f))
        a = vnd.archive_start(src)
        self.assertEqual(data[a:], src[a:])

    def test_moved_curve_still_patched(self):
        f = sample(PERLIM)
        d = registry.open_document(f)
        L = next(L for L in d.layers if any(isinstance(it, Shape) for it in L.items))
        i = next(k for k, it in enumerate(L.items) if isinstance(it, Shape))
        before = L.items[i].bbox()
        L.items[i] = L.items[i].transformed(Affine.translation(10, 0))
        data, _ = vnd_write.write_document(d)
        with tempfile.TemporaryDirectory() as tmp:
            g = pathlib.Path(tmp) / 'm.vnd'
            g.write_bytes(data)
            back = registry.open_document(g)
        L2 = next(x for x in back.layers if x.name == L.name)
        after = L2.items[i].bbox()
        self.assertAlmostEqual(after[0] - before[0], 10, places=6)


class TestWindow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()

    def tearDown(self):
        self.w.modified = False
        self.w.close()

    def test_circles_to_holes_and_edit(self):
        w = self.w
        c = Shape(path=Path([geom.circle((10, 10), 2)]))
        w._add_items([c])
        w._hole_dialog = lambda spec, title, keep=None: (holes.HoleSpec(6, 3), keep)
        w.new_holes()
        h = w.canvas.selection[0]
        self.assertTrue(holes.is_hole(h))
        self.assertAlmostEqual(holes.spec_of(h).diameter, 4, places=9)     # diamètre gardé
        self.assertAlmostEqual(holes.spec_of(h).depth, 3, places=9)
        w._hole_dialog = lambda spec, title, keep=None: (holes.HoleSpec(5, 1), False)
        w._item_double_clicked(h)
        h2 = w.canvas.selection[0]
        self.assertEqual(holes.circle_of(h2), (10.0, 10.0, 2.5))
        self.assertAlmostEqual(holes.spec_of(h2).depth, 1, places=9)
        w.canvas.select([])
        w.new_holes()                                     # sans cercle : un trou au centre
        self.assertTrue(holes.is_hole(w.canvas.selection[0]))
        w.canvas.grab()                                   # dessin de la croix


if __name__ == '__main__':
    unittest.main()
