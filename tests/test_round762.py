"""Round 762 : VND : les cas que la batterie a fait tomber. Nom de plan Unicode relisible, coordonnées invalides et outils
impossibles écartés et signalés ; le document de l'utilisateur n'est jamais touché."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.core import geom
from vectordrive.core.document import Document, Group, Image, Layer, Plate, Shape, Text
from vectordrive.core.geom import Affine, Line
from vectordrive.io import mfc, te_clip, vnd, vnd_write

NAN = float('nan')
INF = float('inf')


def square(x=10.0, tool=0):
    return Shape(path=geom.Path([geom.rect(x, 10, 20, 20)]), tool=tool)


def broken(v):
    """Contour fermé dont un point vaut `v`."""
    return geom.Contour([Line((0.0, 0.0), (v, 5.0)), Line((v, 5.0), (10.0, 10.0)), Line((10.0, 10.0), (0.0, 0.0))], closed=True)


def doc_of(*items, name='A', tool=0):
    d = Document()
    d.plate = Plate(100, 80)
    d.layers = [Layer(name=name, items=list(items), tool=tool)]
    return d


def read_bytes(data):
    with tempfile.TemporaryDirectory() as t:
        path = os.path.join(t, 'x.vnd')
        with open(path, 'wb') as f:
            f.write(data)
        return vnd.read(path)


def written_points(data):
    (root, _ar) = vnd.parse(data)
    out = []

    def walk(o):
        if o.cls.name == 'CContour':
            out.append(o.fields)
        for ch in o.children:
            if ch is not None:
                walk(ch)
    walk(root)
    return out


class TestCString(unittest.TestCase):
    def round_trip(self, s):
        w = vnd_write.MfcWriter()
        w.cstring(s)
        w.u32(0x12345678)                                 # ce qui suit doit se relire à sa place
        ar = mfc.Archive(bytes(w.buf))
        got = ar.cstring()
        self.assertEqual(ar.u32(), 0x12345678)
        return got

    def test_ansi(self):
        self.assertEqual(self.round_trip('Plan é è'), 'Plan é è')

    def test_bmp(self):
        self.assertEqual(self.round_trip('日本語 ✓'), '日本語 ✓')

    def test_emoji_counts_two_units(self):
        self.assertEqual(self.round_trip('😀'), '😀')
        self.assertEqual(self.round_trip('a😀b😀c'), 'a😀b😀c')

    def test_long_with_emoji(self):
        s = '😀' * 200                                     # 400 unités : la longueur passe sur 16 bits
        self.assertEqual(self.round_trip(s), s)

    def test_length_around_the_limit(self):
        for n in (126, 127, 128, 254, 255):
            s = '😀' * n
            self.assertEqual(self.round_trip(s), s, n)

    def test_lone_surrogate_does_not_crash(self):
        self.assertEqual(len(self.round_trip('a\ud83dz')), 3)


class TestLayerName(unittest.TestCase):
    def test_unicode_plan_is_fully_read(self):
        name = '日本語 ✓ éè 😀 "guillemets"'
        d = doc_of(square(), name=name)
        data, _r = vnd_write.write_document(d)
        self.assertEqual(vnd_write.check_written(d, data), [])
        (root, _ar) = vnd.parse(data)
        calque = next(c for c in root.children if c.cls.name == 'CCalque')
        self.assertEqual(calque.fields['layer_name'], name)
        self.assertEqual(sum(1 for L in read_bytes(data).layers for _ in L.items), 1)

    def test_name_not_a_string(self):
        d = doc_of(square(), name=None)
        data, _r = vnd_write.write_document(d)
        self.assertEqual(sum(1 for L in read_bytes(data).layers for _ in L.items), 1)


class TestCoordinates(unittest.TestCase):
    def assert_all_finite(self, data):
        points = written_points(data)
        self.assertTrue(points)
        for f in points:
            self.assertTrue(vnd.points_finite(f))
            for p in f['points']:
                for v in p[:4]:
                    self.assertTrue(math.isfinite(v))

    def test_bad_contour_dropped_good_kept(self):
        for bad in (NAN, INF, -INF, 1e300):
            s = Shape(path=geom.Path([broken(bad), geom.rect(10, 10, 20, 20)]))
            data, report = vnd_write.write_document(doc_of(s))
            self.assert_all_finite(data)
            self.assertEqual(len(written_points(data)), 1, bad)
            self.assertTrue(any('1 contour' in r for r in report), (bad, report))

    def test_object_with_only_bad_contours_goes(self):
        data, report = vnd_write.write_document(doc_of(Shape(path=geom.Path([broken(INF)])), square()))
        self.assertEqual(len(written_points(data)), 1)
        self.assertTrue(any('contour' in r for r in report))

    def test_in_a_group(self):
        data, report = vnd_write.write_document(doc_of(Group(children=[Shape(path=geom.Path([broken(NAN)])), square()]),
                                                       Group(children=[Shape(path=geom.Path([broken(INF)]))])))
        self.assertEqual(len(written_points(data)), 1)
        self.assertTrue(report)

    def test_cubic_and_conic(self):
        bad = geom.Contour([geom.Cubic((0.0, 0.0), (NAN, 1.0), (2.0, 2.0), (3.0, 0.0))])
        badw = geom.Contour([geom.Conic((0.0, 0.0), (1.0, 1.0), (2.0, 0.0), NAN)])
        zero = geom.Contour([geom.Conic((0.0, 0.0), (1.0, 1.0), (2.0, 0.0), 0.0)])
        good = geom.Contour([geom.Conic((0.0, 0.0), (1.0, 1.0), (2.0, 0.0), 0.7)])
        self.assertFalse(vnd_write._contour_ok(bad))
        self.assertFalse(vnd_write._contour_ok(badw))
        self.assertFalse(vnd_write._contour_ok(zero))
        self.assertTrue(vnd_write._contour_ok(good))

    def test_image_and_text_with_bad_matrix(self):
        img = Image(data=b'x', fmt='png', matrix=Affine(NAN, 0, 0, 1, 0, 0))
        txt = Text(text='A', matrix=Affine(1, 0, 0, 1, INF, 0))
        data, report = vnd_write.write_document(doc_of(img, txt, square()))
        self.assertEqual(len(written_points(data)), 1)
        self.assertTrue(any('2 objet' in r for r in report), report)

    def test_big_but_valid_is_kept(self):
        s = Shape(path=geom.Path([geom.rect(5e6, -5e6, 1000, 1000)]))
        data, report = vnd_write.write_document(doc_of(s))
        self.assertEqual(len(written_points(data)), 1)
        self.assertFalse(any('invalide' in r for r in report))

    def test_only_bad_objects_gives_an_empty_valid_file(self):
        d = doc_of(Shape(path=geom.Path([broken(INF)])))
        data, _r = vnd_write.write_document(d)
        self.assertEqual(vnd_write.check_written(d, data), [])       # pas un « fichier vide par erreur »

    def test_write_tells_the_user(self):
        d = doc_of(Shape(path=geom.Path([broken(NAN), geom.rect(1, 1, 2, 2)])))
        with tempfile.TemporaryDirectory() as t:
            vnd_write.write(d, os.path.join(t, 'x.vnd'))
        self.assertTrue(any('contour' in r for r in d.report))

    def test_users_document_untouched(self):
        s = Shape(path=geom.Path([broken(INF), geom.rect(1, 1, 2, 2)]), tool=-1)
        d = doc_of(s, Shape(path=geom.Path([broken(NAN)])))
        vnd_write.write_document(d)
        self.assertEqual(len(d.layers[0].items), 2)
        self.assertEqual(len(s.path.contours), 2)
        self.assertEqual(s.tool, -1)

    def test_healthy_document_is_passed_as_is(self):
        d = doc_of(square(), Group(children=[square(40)]))
        self.assertIs(vnd_write.clean_document(d)[0], d)
        self.assertEqual(vnd_write.clean_document(d)[1], [])

    def test_bad_plate_and_origin(self):
        d = doc_of(square())
        d.plate = Plate(NAN, 80)
        d.extra['origine'] = (INF, 0.0)
        data, report = vnd_write.write_document(d)
        self.assertEqual(len(written_points(data)), 1)
        self.assertTrue(any('plaque' in r for r in report))
        self.assertTrue(any('origine' in r for r in report))
        back = read_bytes(data)
        bb = back.bbox()
        self.assertAlmostEqual(bb[0], 10.0, places=6)                # pas de décalage venu de l'origine écartée


class TestCheckStillWatches(unittest.TestCase):
    def test_nan_that_got_through_is_told(self):
        """Dernier filet : si un point invalide passait quand même, la relecture le dirait."""
        d = doc_of(Shape(path=geom.Path([broken(NAN), geom.rect(1, 1, 2, 2)])))
        data, _r = vnd_write._write_document(d)                      # sans le tri
        self.assertTrue(any('invalides' in n for n in vnd_write.check_written(d, data)))


class TestTool(unittest.TestCase):
    def test_negative_tool(self):
        data, report = vnd_write.write_document(doc_of(square(tool=-1)))
        back = read_bytes(data)
        self.assertEqual(back.layers[0].items[0].tool, 0)
        self.assertTrue(any('outil' in r for r in report))

    def test_layer_tool(self):
        data, report = vnd_write.write_document(doc_of(name='A', tool=-3))
        self.assertTrue(data)
        self.assertTrue(any('outil' in r for r in report))

    def test_tool_nan_and_huge(self):
        for t in (NAN, 2 ** 40):
            data, report = vnd_write.write_document(doc_of(square(tool=t)))
            self.assertEqual(read_bytes(data).layers[0].items[0].tool, 0, t)
            self.assertTrue(any('outil' in r for r in report), t)

    def test_good_tool_kept(self):
        data, report = vnd_write.write_document(doc_of(square(tool=7)))
        self.assertEqual(read_bytes(data).layers[0].items[0].tool, 7)
        self.assertFalse(any('outil' in r for r in report))


class TestClipboard(unittest.TestCase):
    def test_bad_objects_do_not_reach_typeedit(self):
        data = te_clip.build([Shape(path=geom.Path([broken(NAN)])), square()])
        items, _r = te_clip.read(data)
        self.assertEqual(len(items), 1)

    def test_nothing_left(self):
        with self.assertRaises(te_clip.ClipError):
            te_clip.build([Shape(path=geom.Path([broken(INF)]))])

    def test_unicode_stays_readable(self):
        s = square()
        s.name = 'Objet 😀'
        self.assertEqual(len(te_clip.read(te_clip.build([s]))[0]), 1)


if __name__ == '__main__':
    unittest.main()
