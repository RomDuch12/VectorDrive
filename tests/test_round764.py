"""Round 764 : ouvrir CorelDRAW, EMF, WMF et Visio par Inkscape ; lire et écrire le HPGL."""
import math
import os
import pathlib
import struct
import subprocess
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.core import geom
from vectordrive.core.document import Document, Group, Image, Layer, Shape
from vectordrive.io import hpgl, inkscape_import as IK, registry

SVG = ('<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="50mm" viewBox="0 0 100 50">'
       '<rect x="10" y="10" width="30" height="20" fill="none" stroke="#ff0000"/></svg>')


class Settings:
    def __init__(self, value=''):
        self.v = value

    def value(self, _k, default=''):
        return self.v or default


def wmf() -> bytes:
    """Petit WMF à part entière, écrit ici : un carré."""
    pts = [(100, 100), (900, 100), (900, 900), (100, 900), (100, 100)]
    poly = struct.pack('<IHH', 4 + len(pts) * 2, 0x0325, len(pts)) + b''.join(struct.pack('<hh', *p) for p in pts)
    eof = struct.pack('<IH', 3, 0)
    words = 9 + (len(poly) + len(eof)) // 2
    head = struct.pack('<HHHIHIH', 1, 9, 0x0300, words, 0, len(poly) // 2, 0)
    place = struct.pack('<IHhhhhHI', 0x9AC6CDD7, 0, 0, 0, 1000, 1000, 1440, 0)
    check = 0
    for w in struct.unpack('<10H', place):
        check ^= w
    return place + struct.pack('<H', check) + head + poly + eof


class TestFind(unittest.TestCase):
    def test_setting_first(self):
        with tempfile.TemporaryDirectory() as t:
            p = os.path.join(t, 'ink.exe')
            pathlib.Path(p).write_bytes(b'')
            self.assertEqual(IK.find(Settings(f'"{p}"')), p)

    def test_bad_setting_falls_through(self):
        with mock.patch('shutil.which', return_value='C:/ailleurs/inkscape.exe'):
            self.assertEqual(IK.find(Settings('C:/nulle/part.exe')), 'C:/ailleurs/inkscape.exe')

    def test_not_there(self):
        with mock.patch('shutil.which', return_value=None), mock.patch.object(IK, '_usual_places', return_value=[]):
            self.assertEqual(IK.find(Settings()), '')

    def test_usual_place(self):
        with tempfile.TemporaryDirectory() as t:
            p = os.path.join(t, 'inkscape.exe')
            pathlib.Path(p).write_bytes(b'')
            with mock.patch('shutil.which', return_value=None), mock.patch.object(IK, '_usual_places', return_value=[p]):
                self.assertEqual(IK.find(Settings()), p)


class TestRead(unittest.TestCase):
    def setUp(self):
        self.dir = pathlib.Path(tempfile.mkdtemp())
        self.src = self.dir / 'logo client é.cdr'
        self.src.write_bytes(b'RIFF')

    def fake_run(self, code=0, svg=SVG):
        def run(cmd, **k):
            dst = next(a.split('=', 1)[1] for a in cmd if a.startswith('--export-filename='))
            self.cmd = cmd
            if svg is not None:
                pathlib.Path(dst).write_text(svg, encoding='utf-8')
            return subprocess.CompletedProcess(cmd, code, b'', b'avertissement\nmauvais fichier\n')
        return run

    def read(self, run):
        with mock.patch.object(IK, 'find', return_value='ink.exe'), mock.patch('subprocess.run', run):
            return IK.read(self.src)

    def test_converted_and_read(self):
        d = self.read(self.fake_run())
        self.assertEqual(self.cmd[0], 'ink.exe')
        self.assertEqual(self.cmd[-1], str(self.src))
        self.assertIn('--export-plain-svg', self.cmd)
        bb = d.bbox()
        self.assertAlmostEqual(bb[2] - bb[0], 30.0, places=3)
        self.assertAlmostEqual(bb[3] - bb[1], 20.0, places=3)
        self.assertTrue(any('Inkscape' in r for r in d.report))

    def test_without_inkscape_says_what_to_do(self):
        with mock.patch.object(IK, 'find', return_value=''):
            with self.assertRaises(ValueError) as ctx:
                IK.read(self.src)
        self.assertIn('Inkscape', str(ctx.exception))
        self.assertIn('PDF', str(ctx.exception))
        self.assertIn(self.src.name, str(ctx.exception))

    def test_failure_said(self):
        with self.assertRaises(ValueError) as ctx:
            self.read(self.fake_run(code=1, svg=None))
        self.assertIn('mauvais fichier', str(ctx.exception))

    def test_no_output_said(self):
        with self.assertRaises(ValueError):
            self.read(self.fake_run(code=0, svg=None))

    def test_empty_output_said(self):
        with self.assertRaises(ValueError):
            self.read(self.fake_run(code=0, svg=''))

    def test_timeout_said(self):
        def run(cmd, **k):
            raise subprocess.TimeoutExpired(cmd, 1)
        with self.assertRaises(ValueError) as ctx:
            self.read(run)
        self.assertIn('ne répond pas', str(ctx.exception))

    def test_cannot_start_said(self):
        def run(cmd, **k):
            raise OSError('accès refusé')
        with self.assertRaises(ValueError) as ctx:
            self.read(run)
        self.assertIn('démarrer', str(ctx.exception))

    def test_temp_dir_cleaned(self):
        seen = []
        real = self.fake_run()

        def run(cmd, **k):
            r = real(cmd, **k)
            seen.append(next(a.split('=', 1)[1] for a in cmd if a.startswith('--export-filename=')))
            return r
        self.read(run)
        self.assertFalse(os.path.exists(os.path.dirname(seen[0])))

    def test_in_the_registry(self):
        for ext in ('x.cdr', 'x.CMX', 'x.emf', 'x.wmf', 'x.vsd', 'x.vsdx', 'x.wpg'):
            f = registry.by_extension(ext)
            self.assertEqual(f.key, 'inkscape', ext)
            self.assertIsNone(f.writer)
        self.assertIn('*.cdr', registry.filter_string())
        self.assertNotIn('*.cdr', registry.filter_string(write=True))

    @unittest.skipUnless(IK.find(Settings()), 'Inkscape absent de ce poste')
    def test_for_real(self):
        p = self.dir / 'carré.wmf'
        p.write_bytes(wmf())
        d = registry.open_document(p)
        self.assertGreaterEqual(d.stats()['contours'], 1)
        bb = d.bbox()
        self.assertGreater(bb[2] - bb[0], 1.0)


class TestHpglRead(unittest.TestCase):
    def only(self, text):
        by_pen, _labels = hpgl.read_text(text)
        return by_pen

    def box(self, contours):
        p = geom.Path(list(contours))
        return p.bbox()

    def test_square_is_closed(self):
        c = self.only('IN;SP1;PU0,0;PD400,0,400,400,0,400,0,0;PU;')[1]
        self.assertEqual(len(c), 1)
        self.assertTrue(c[0].closed)
        self.assertEqual(self.box(c), (0.0, 0.0, 10.0, 10.0))           # 40 unités par mm

    def test_open_line(self):
        c = self.only('PU0,0;PD400,0;PU;')[1]
        self.assertFalse(c[0].closed)
        self.assertEqual(len(c[0].segments), 1)

    def test_relative(self):
        c = self.only('PA400,400;PR;PD400,0,0,400;PU;')[1]
        self.assertEqual(self.box(c), (10.0, 10.0, 20.0, 20.0))

    def test_pen_up_moves(self):
        c = self.only('PU0,0;PD40,0;PU400,0;PD440,0;PU;')[1]
        self.assertEqual(len(c), 2)
        self.assertEqual(c[1].segments[0].start, (10.0, 0.0))

    def test_pens_are_separate(self):
        by = self.only('SP1;PU0,0;PD40,0;PU;SP3;PU0,40;PD40,40;PU;')
        self.assertEqual(sorted(by), [1, 3])

    def test_circle(self):
        c = self.only('PA400,400;CI200;')[1]
        bb = self.box(c)
        self.assertAlmostEqual(bb[0], 5.0)
        self.assertAlmostEqual(bb[2], 15.0)
        self.assertTrue(c[0].closed)

    def test_arc(self):
        c = self.only('PU400,0;PD;AA0,0,90;PU;')[1]
        self.assertEqual(len(c), 1)
        bb = self.box(c)
        self.assertAlmostEqual(bb[2], 10.0)
        self.assertAlmostEqual(bb[3], 10.0)

    def test_after_an_arc_the_pen_is_at_its_end(self):
        c = self.only('PU400,0;PD;AA0,0,90;PR;PD40,0;PU;')[1]
        self.assertEqual(len(c), 1)
        self.assertAlmostEqual(c[0].segments[-1].start[0], 0.0, places=6)
        self.assertAlmostEqual(c[0].segments[-1].start[1], 10.0, places=6)

    def test_edge_rectangle(self):
        c = self.only('PA40,40;EA440,240;')[1]
        self.assertEqual(self.box(c), (1.0, 1.0, 11.0, 6.0))
        self.assertTrue(c[0].closed)

    def test_no_semicolons(self):
        c = self.only('PU0 0 PD400 0 400 400 PU')[1]
        self.assertEqual(self.box(c), (0.0, 0.0, 10.0, 10.0))

    def test_decimal_and_spaces(self):
        c = self.only('PU 0.5 , 0 ; PD 400.5 , 0 ;')[1]
        self.assertEqual(len(c[0].segments), 1)
        self.assertAlmostEqual(c[0].segments[0].end[0], 400.5 / 40)

    def test_label_counted_and_its_letters_not_read_as_commands(self):
        by, labels = hpgl.read_text('PU0,0;LBPD400,400\x03;PU0,0;PD40,0;PU;')
        self.assertEqual(labels, 1)
        self.assertEqual(self.box(by[1]), (0.0, 0.0, 1.0, 0.0))

    def test_garbage_does_not_crash(self):
        self.assertEqual(self.only(''), {})
        self.assertEqual(self.only('PD'), {})
        self.assertEqual(self.only('SP;CI;AA1;EA1;;;'), {})


class TestHpglFile(unittest.TestCase):
    def setUp(self):
        self.dir = pathlib.Path(tempfile.mkdtemp())

    def test_open(self):
        p = self.dir / 'x.plt'
        p.write_text('IN;SP2;PU0,0;PD400,0,400,400,0,400,0,0;PU;', encoding='ascii')
        d = registry.open_document(p)
        self.assertEqual(len(d.layers), 1)
        self.assertEqual(d.layers[0].tool, 1)
        self.assertEqual(d.layers[0].items[0].tool, 1)
        self.assertEqual(d.bbox(), (0.0, 0.0, 10.0, 10.0))

    def test_empty_refused(self):
        p = self.dir / 'x.plt'
        p.write_text('IN;SP1;PU;', encoding='ascii')
        with self.assertRaises(ValueError):
            hpgl.read(p)

    def test_pcl_refused(self):
        p = self.dir / 'x.plt'
        p.write_bytes(b'\x1b%-12345X@PJL')
        with self.assertRaises(ValueError) as ctx:
            hpgl.read(p)
        self.assertIn('pas du HPGL', str(ctx.exception))

    def test_labels_told(self):
        p = self.dir / 'x.plt'
        p.write_text('PU0,0;PD40,0;LBtexte\x03', encoding='ascii')
        self.assertTrue(any('texte' in r for r in hpgl.read(p).report))


class TestHpglWrite(unittest.TestCase):
    def doc(self, *items):
        d = Document()
        d.plate = None
        d.layers = [Layer(name='A', items=list(items))]
        return d

    def test_simple(self):
        t, images = hpgl.write_text(self.doc(Shape(path=geom.Path([geom.rect(0, 0, 10, 5)]))))
        self.assertEqual(images, 0)
        self.assertIn('SP1;', t)
        self.assertIn('PU0,0;', t)
        self.assertIn('400,0', t)
        self.assertIn('400,200', t)
        self.assertTrue(t.startswith('IN;'))
        self.assertTrue(t.rstrip().endswith('SP0;'))

    def test_moved_to_zero(self):
        t, _i = hpgl.write_text(self.doc(Shape(path=geom.Path([geom.rect(-5, -7, 10, 5)]))))
        self.assertNotIn('-', t)
        self.assertIn('PU0,0;', t)

    def test_tools_become_pens(self):
        t, _i = hpgl.write_text(self.doc(Shape(path=geom.Path([geom.rect(0, 0, 1, 1)]), tool=4),
                                         Shape(path=geom.Path([geom.rect(2, 0, 1, 1)]), tool=0)))
        self.assertLess(t.index('SP1;'), t.index('SP5;'))

    def test_round_trip(self):
        d = self.doc(Shape(path=geom.Path([geom.rect(0, 0, 25, 12.5), geom.circle((60, 20), 10)])))
        with tempfile.TemporaryDirectory() as t:
            p = os.path.join(t, 'a.plt')
            registry.save_document(d, p)
            back = registry.open_document(p)
        self.assertEqual(back.stats()['contours'], 2)
        bb = back.bbox()
        self.assertAlmostEqual(bb[2], 70.0, places=1)
        self.assertAlmostEqual(bb[3], 30.0, places=1)
        L = sum(c.length() for it in back.iter_leaves() for c in it.path.contours)
        self.assertAlmostEqual(L, 2 * (25 + 12.5) + 2 * math.pi * 10, delta=0.2)

    def test_curves_within_tolerance(self):
        t, _i = hpgl.write_text(self.doc(Shape(path=geom.Path([geom.circle((10, 10), 10)]))))
        by, _l = hpgl.read_text(t)
        for s in by[1][0].segments:
            for x, y in (s.start, s.end):
                self.assertAlmostEqual(math.hypot(x - 10, y - 10), 10, delta=0.05)

    def test_hidden_not_written(self):
        s = Shape(path=geom.Path([geom.rect(0, 0, 1, 1)]))
        s.visible = False
        t, _i = hpgl.write_text(self.doc(s, Shape(path=geom.Path([geom.rect(50, 0, 1, 1)]))))
        self.assertEqual(t.count('PD'), 1)

    def test_group(self):
        t, _i = hpgl.write_text(self.doc(Group(children=[Shape(path=geom.Path([geom.rect(0, 0, 1, 1)]))])))
        self.assertEqual(t.count('PD'), 1)

    def test_image_told(self):
        d = self.doc(Image(data=b'x', fmt='png'), Shape(path=geom.Path([geom.rect(0, 0, 1, 1)])))
        with tempfile.TemporaryDirectory() as t:
            hpgl.write(d, os.path.join(t, 'a.plt'))
        self.assertTrue(any('image' in r for r in d.report))

    def test_empty_drawing(self):
        t, _i = hpgl.write_text(self.doc())
        self.assertEqual(t.count('PD'), 0)

    def test_tiny_contour_skipped(self):
        t, _i = hpgl.write_text(self.doc(Shape(path=geom.Path([geom.rect(0, 0, 0.001, 0.001)]))))
        self.assertEqual(t.count('PD'), 0)


if __name__ == '__main__':
    unittest.main()
