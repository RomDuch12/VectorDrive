"""Round 22 : lecture des GVT (TypeEdit 9 et plus)."""
import pathlib
import struct
import unittest

from vectordrive.io import registry, vnd
from tests.corpus import corpus

DRAWS = pathlib.Path('C:/ProgramData/Gravotech/TypeEdit_V15-LaserType_V15/DRAWS')
DESSINS_GVT = corpus('dessins_gvt')


def sample(path):
    if not path.exists():
        raise unittest.SkipTest(f'{path.name} absent')
    return path


class TestGvt(unittest.TestCase):
    def test_header_and_parse(self):
        f = sample(DRAWS / 'RomDuch001.gvt')
        data = f.read_bytes()
        self.assertEqual(struct.unpack_from('<I', data, 0)[0], vnd.GVT_MAGIC)
        self.assertEqual(vnd.archive_start(data), struct.unpack_from('<I', data, 4)[0] - 2)
        root, _ar = vnd.parse(data)
        self.assertEqual(root.cls.name, 'CTravail')
        self.assertEqual(root.cls.schema, 11)

    def test_open_documents(self):
        for f, contours, plate in ((DRAWS / 'RomDuch001.gvt', 104, (500, 400)),
                                   (DRAWS / 'watch.gvt', 207, (30, 30)),
                                   (corpus('gvt_exemple'), 76, (400, 500))):
            with self.subTest(f.name):
                d = registry.open_document(sample(f))
                self.assertEqual(d.stats()['contours'], contours)
                self.assertAlmostEqual(d.plate.width, plate[0], places=6)
                self.assertAlmostEqual(d.plate.height, plate[1], places=6)
                self.assertEqual(len(d.tools), 10)
                self.assertEqual(d.report, [])

    def test_relief_and_metafile(self):
        d = registry.open_document(sample(DRAWS / 'pegasus.gvt'))
        im = d.layers[0].items[0]
        self.assertEqual(type(im).__name__, 'Image')
        bb = im.bbox()
        self.assertAlmostEqual(bb[2] - bb[0], 36, places=6)        # carte de 36 mm
        self.assertEqual(struct.unpack_from('<IiiHH', im.data, 0), (40, 720, 720, 1, 8))
        d = registry.open_document(sample(DRAWS / 'Cutter' / 'Cutter.gvt'))
        self.assertTrue(any('EMF' in r for r in d.report))

    def test_relief_history_message(self):
        f = DRAWS / 'poignard.gvt'
        if not f.exists():
            self.skipTest('poignard.gvt absent')
        # round 46 : lecture partielle — le dessin qui précède le relief est lu
        d = registry.open_document(f)
        self.assertTrue(any('historique' in r for r in d.report), d.report)
        self.assertGreater(d.stats()['contours'], 0)



class TestGvtToVnd(unittest.TestCase):
    def test_saved_as_vnd_from_template(self):
        import tempfile
        from vectordrive.io import vnd_write
        d = registry.open_document(sample(DRAWS / 'RomDuch001.gvt'))
        self.assertEqual(d.source_format, 'gvt')
        self.assertNotIn('vnd_source', d.extra)
        data, _rep = vnd_write.write_document(d)
        self.assertEqual(struct.unpack_from('<I', data, 0)[0], vnd.MAGIC)
        with tempfile.TemporaryDirectory() as t:
            f = pathlib.Path(t) / 'x.vnd'
            f.write_bytes(data)
            back = vnd.read(f)
        self.assertEqual(back.stats()['contours'], d.stats()['contours'])



class TestPlateWriting(unittest.TestCase):
    def test_new_document_plate_and_planes(self):
        import tempfile
        from vectordrive.core import geom
        from vectordrive.core.document import Document, Plate, Shape
        from vectordrive.io import vnd_write
        d = Document()
        d.plate = Plate(120, 80, thickness=3, x=5, y=-2)
        d.add(Shape(path=geom.Path([geom.rect(10, 10, 20, 20)])))
        data, _rep = vnd_write.write_document(d)
        root, ar = vnd.parse(data)
        ar.pos = root.fields['tail_offset']
        t = vnd.parse_tail_head(ar)
        mm = [round(v * 1000, 9) for v in t['support_bbox']]
        self.assertEqual(mm, [5, -2, -3, 125, 78, 0])
        values = [round(val * 1000, 9) for _bb, val, _axis in t['planes']]
        self.assertEqual(values, [-2, 78, 5, 125, -3, 0] * 2)
        for bb, val, axis in t['planes']:
            fixed = {0: (1, 4), 1: (0, 3), 2: (2, 5)}[axis]
            self.assertTrue(all(abs(bb[i] - val) < 1e-15 for i in fixed))
        with tempfile.TemporaryDirectory() as tmp:
            f = pathlib.Path(tmp) / 'p.vnd'
            f.write_bytes(data)
            back = vnd.read(f)
        self.assertEqual((back.plate.width, back.plate.height, back.plate.thickness), (120, 80, 3))


if __name__ == '__main__':
    unittest.main()
