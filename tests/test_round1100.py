"""Round 1100 : le relief d'un VND (CVbitmap, carte de hauteurs) réécrit tel quel au réenregistrement — il devenait une
image plate (CVnImage) et TypeEdit perdait le relief. Déplacé : la carte suit ; agrandi, retouché : image ; rendu par le .vdz, la session."""
import os
import pathlib
import struct
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1100.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from vectordrive.core.document import Document, Image, Layer  # noqa: E402
from vectordrive.core.geom import Affine  # noqa: E402
from vectordrive.io import vnd, vnd_write as W  # noqa: E402
from vectordrive.io.mfc import MfcClass, MfcObject  # noqa: E402

W_, H_ = 4, 3
HEIGHTS = [0.0, 0.1, 0.2, 0.3, 0.4, 1e30, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1]


def zmap(ox, oy):
    return {'origin': (ox, oy), 'f': 0.25, 'step': (0.004, 0.003), 'w': W_, 'h': H_,
            'data': struct.pack(f'<{W_ * H_}f', *HEIGHTS)}


def relief(schema=7, map2=False):
    o = MfcObject(MfcClass('CVbitmap', schema))
    o.fields = W._obdao_fields((0.010, 0.020, 0.0, 0.014, 0.023, 0.001))
    o.fields['map'] = zmap(0.010, 0.020)
    o.fields['histo'] = {'version': 3, 'n': 0, 'current': 0xFFFFFFFF}
    o.fields['b3c8'] = 0
    o.fields['b3c9'] = 1
    o.fields['has_map2'] = 1 if map2 else 0
    if map2:
        o.fields['map2'] = zmap(0.011, 0.021)
    if schema == 6:
        o.fields['guid6'] = bytes(range(16))
    return o


def image_of(obj):
    m = obj.fields['map']
    im = Image(data=vnd.heightmap_dib(m['w'], m['h'], m['data']), fmt='dib',
               matrix=Affine(4, 0, 0, -3, 10, 23), name='Relief')
    im.extra['vnd_obj'] = obj
    return im


def objects(data, name):
    root, _ = vnd.parse(data)
    out = []

    def walk(o):
        if o is None:
            return
        if o.cls.name == name:
            out.append(o)
        for ch in o.children or ():
            walk(ch)
    walk(root)
    return out


def doc_with(item):
    d = Document()
    d.layers = [Layer(name='Plan 1', items=[item])]
    return d


class TestRelief(unittest.TestCase):
    def test_written_as_read(self):
        for schema, map2 in ((7, False), (7, True), (6, True), (5, False), (2, False), (1, False)):
            with self.subTest(schema=schema, map2=map2):
                src = relief(schema, map2)
                data, _report = W.write_document(doc_with(image_of(src)), allow_foreign=True)
                got = objects(data, 'CVbitmap')
                self.assertEqual(len(got), 1)
                self.assertEqual(objects(data, 'CVnImage'), [])
                f, g = src.fields, got[0].fields
                self.assertEqual(g['map'], f['map'])
                need = {'histo': 2, 'b3c8': 3, 'b3c9': 4, 'has_map2': 5, 'map2': 5, 'guid6': 6}
                for k, v in need.items():
                    if schema >= v and (k != 'map2' or map2) and (k != 'guid6' or schema == 6):
                        self.assertEqual(g.get(k), f[k], k)
                    elif k != 'histo' or schema < 2:
                        self.assertNotIn(k, g, k)

    def test_reopened_and_rewritten(self):
        data, _ = W.write_document(doc_with(image_of(relief(map2=True))), allow_foreign=True)
        with tempfile.TemporaryDirectory() as tmp:
            p = pathlib.Path(tmp) / 'relief.vnd'
            p.write_bytes(data)
            d = vnd.read(p)
            ims = [it for L in d.layers for it in L.items if isinstance(it, Image)]
            self.assertEqual(len(ims), 1)
            self.assertEqual(ims[0].extra['vnd_obj'].cls.name, 'CVbitmap')
            again, _ = W.write_document(d)
            self.assertEqual(len(objects(again, 'CVbitmap')), 1)
            self.assertEqual(objects(again, 'CVbitmap')[0].fields['map'], zmap(0.010, 0.020))
            self.assertEqual(objects(again, 'CVnImage'), [])

    def test_moved_map_follows(self):
        im = image_of(relief(map2=True)).transformed(Affine.translation(5, -2))
        t = W.source_object(im)
        self.assertIsNotNone(t)
        self.assertAlmostEqual(t.fields['map']['origin'][0], 0.015)
        self.assertAlmostEqual(t.fields['map']['origin'][1], 0.018)
        self.assertAlmostEqual(t.fields['map2']['origin'][0], 0.016)
        self.assertAlmostEqual(t.fields['map2']['origin'][1], 0.019)
        self.assertAlmostEqual(t.fields['bbox'][0], 0.015)
        self.assertEqual(t.fields['map']['data'], zmap(0, 0)['data'])
        src = im.extra['vnd_obj']
        self.assertEqual(src.fields['map']['origin'], (0.010, 0.020))     # l'objet lu n'est pas touché

    def test_scaled_becomes_image(self):
        im = image_of(relief()).transformed(Affine.scaling(2, 2))
        self.assertIsNone(W.source_object(im))
        data, report = W.write_document(doc_with(im), allow_foreign=True)
        self.assertEqual(objects(data, 'CVbitmap'), [])
        self.assertEqual(len(objects(data, 'CVnImage')), 1)
        self.assertTrue(any('mis à l\'échelle' in r for r in report), report)

    def test_foreign_relief_kept(self):
        # relief venu d'un autre fichier (pas de vnd_source) : rien qui renvoie aux tables du fichier, gardé
        data, report = W.write_document(doc_with(image_of(relief())))
        self.assertEqual(len(objects(data, 'CVbitmap')), 1)
        self.assertEqual(objects(data, 'CVnImage'), [])
        self.assertFalse(any('texte(s) ou cote(s)' in r for r in report), report)

    def reread(self, data, tmp, name='r.vnd'):
        p = pathlib.Path(tmp) / name
        p.write_bytes(data)
        return vnd.read(p)

    def test_moved_in_own_vnd(self):
        # réécriture de son propre VND (même structure : `_patch`) : la carte et la boîte suivent
        data, _ = W.write_document(doc_with(image_of(relief(map2=True))), allow_foreign=True)
        with tempfile.TemporaryDirectory() as tmp:
            d = self.reread(data, tmp)
            L = d.layers[0]
            L.items[0] = L.items[0].transformed(Affine.translation(5, -2))
            again, _ = W.write_document(d)
        g = objects(again, 'CVbitmap')
        self.assertEqual(len(g), 1)
        self.assertAlmostEqual(g[0].fields['map']['origin'][0], 0.015)
        self.assertAlmostEqual(g[0].fields['map']['origin'][1], 0.018)
        self.assertAlmostEqual(g[0].fields['map2']['origin'][0], 0.016)
        self.assertAlmostEqual(g[0].fields['bbox'][0], 0.015)
        self.assertAlmostEqual(g[0].fields['bbox'][1], 0.018)
        self.assertEqual(g[0].fields['map']['data'], zmap(0, 0)['data'])

    def test_unmoved_rewritten_to_the_byte(self):
        data, _ = W.write_document(doc_with(image_of(relief(map2=True))), allow_foreign=True)
        with tempfile.TemporaryDirectory() as tmp:
            d = self.reread(data, tmp)
            again, _ = W.write_document(d)
        self.assertEqual(objects(again, 'CVbitmap')[0].fields['map'], objects(data, 'CVbitmap')[0].fields['map'])

    def test_through_vdz(self):
        # .vdz (et session, récupération : même `attach_source`) : le relief retrouve son objet par GUID
        from vectordrive.io import native
        data, _ = W.write_document(doc_with(image_of(relief())), allow_foreign=True)
        with tempfile.TemporaryDirectory() as tmp:
            d = self.reread(data, tmp)
            z = pathlib.Path(tmp) / 'r.vdz'
            native.write(d, str(z))
            d2 = native.read(str(z))
        im = d2.layers[0].items[0]
        self.assertIsInstance(im, Image)
        self.assertIsNotNone(im.extra.get('vnd_obj'))
        self.assertEqual(im.extra['vnd_obj'].cls.name, 'CVbitmap')
        again, _ = W.write_document(d2)
        self.assertEqual(len(objects(again, 'CVbitmap')), 1)
        self.assertEqual(objects(again, 'CVnImage'), [])

    def test_swapped_reliefs(self):
        # deux reliefs intervertis (même structure : `_patch`) : chacun garde ses hauteurs
        a, b = relief(), relief()
        b.fields['map'] = dict(zmap(0.050, 0.050), data=struct.pack(f'<{W_ * H_}f', *([5.0] * (W_ * H_))))
        b.fields['bbox'] = (0.050, 0.050, 0.0, 0.054, 0.053, 0.001)
        ia, ib = image_of(a), image_of(b)
        ib.matrix = Affine(4, 0, 0, -3, 50, 53)
        d = Document()
        d.layers = [Layer(name='Plan 1', items=[ia, ib])]
        data, _ = W.write_document(d, allow_foreign=True)
        with tempfile.TemporaryDirectory() as tmp:
            d2 = self.reread(data, tmp)
        L = d2.layers[0]
        L.items.reverse()
        again, _ = W.write_document(d2)
        got = {g.fields['map']['origin']: g.fields['map']['data'] for g in objects(again, 'CVbitmap')}
        self.assertEqual(got[(0.010, 0.020)], zmap(0, 0)['data'])
        self.assertEqual(got[(0.050, 0.050)], b.fields['map']['data'])
        guids = {g.fields['map']['origin']: g.fields['guid'] for g in objects(again, 'CVbitmap')}
        self.assertEqual(guids[(0.050, 0.050)], b.fields['guid'])

    def test_swapped_images(self):
        # même chose pour deux images (CVnImage) : les pixels suivent
        from vectordrive.io.raster import to_dib
        from PySide6.QtGui import QColor, QImage
        from PySide6.QtCore import QBuffer, QByteArray, QIODevice

        def png(color):
            q = QImage(4, 4, QImage.Format_RGB32)
            q.fill(QColor(color))
            ba = QByteArray()
            buf = QBuffer(ba)
            buf.open(QIODevice.WriteOnly)
            q.save(buf, 'PNG')
            return to_dib(bytes(ba), 'png')
        i1 = Image(data=png('red'), fmt='dib', matrix=Affine(4, 0, 0, 4, 0, 0))
        i2 = Image(data=png('blue'), fmt='dib', matrix=Affine(4, 0, 0, 4, 20, 0))
        d = Document()
        d.layers = [Layer(name='Plan 1', items=[i1, i2])]
        data, _ = W.write_document(d)
        with tempfile.TemporaryDirectory() as tmp:
            d2 = self.reread(data, tmp)
        L = d2.layers[0]
        first = L.items[0]
        L.items.reverse()
        again, _ = W.write_document(d2)
        imgs = objects(again, 'CVnImage')
        self.assertEqual(len(imgs), 2)
        self.assertIsNot(L.items[0], first)
        self.assertEqual([o.fields['bitmap'] for o in imgs], [it.data for it in L.items])

    def test_newer_relief_not_kept_for_typeedit13(self):
        # relief d'un fichier TypeEdit 14 / 15 (schéma inconnu de la V13) venu d'ailleurs : écrit en image
        data, report = W.write_document(doc_with(image_of(relief(schema=8))))
        self.assertEqual(objects(data, 'CVbitmap'), [])
        self.assertEqual(len(objects(data, 'CVnImage')), 1)

    def test_mixed_relief_schemas(self):
        # MFC déclare la classe une fois avec son schéma : un seul schéma de relief par VND, les autres en image
        for other in (6, 2, 5):
            with self.subTest(other=other):
                a, b = relief(7), relief(other, map2=other >= 5)
                ia, ib = image_of(a), image_of(b)
                ib.matrix = Affine(4, 0, 0, -3, 50, 53)
                d = Document()
                d.layers = [Layer(name='Plan 1', items=[ia, ib])]
                data, report = W.write_document(d, allow_foreign=True)
                vnd.parse(data)                                 # lecture complète : pas d'exception
                self.assertEqual([o.cls.schema for o in objects(data, 'CVbitmap')], [7])
                self.assertEqual(len(objects(data, 'CVnImage')), 1)
                self.assertTrue(any('autre version de TypeEdit' in r for r in report), report)
                self.assertIn('vnd_obj', ib.extra)                      # le dessin de l'utilisateur n'est pas touché

    def test_mixed_schemas_keep_the_source_one(self):
        # VND relu qui a un relief de schéma 6 ; un relief de schéma 7 importé : celui de la source est gardé
        data, _ = W.write_document(doc_with(image_of(relief(6, map2=True))), allow_foreign=True)
        with tempfile.TemporaryDirectory() as tmp:
            d = self.reread(data, tmp)
        imp = image_of(relief(7))
        imp.matrix = Affine(4, 0, 0, -3, 50, 53)
        d.layers[0].items.insert(0, imp)
        again, report = W.write_document(d)
        vnd.parse(again)
        self.assertEqual([o.cls.schema for o in objects(again, 'CVbitmap')], [6])
        self.assertEqual(len(objects(again, 'CVnImage')), 1)

    def test_reader_marks_object(self):
        data, _ = W.write_document(doc_with(image_of(relief())), allow_foreign=True)
        with tempfile.TemporaryDirectory() as tmp:
            p = pathlib.Path(tmp) / 'r.vnd'
            p.write_bytes(data)
            d = vnd.read(p)
        im = d.layers[0].items[0]
        self.assertIsInstance(im, Image)
        self.assertEqual(im.name, 'Relief')
        self.assertIn('vnd_obj', im.extra)

    def test_external_edit_drops_relief(self):
        from types import SimpleNamespace
        from vectordrive.ui import main_window
        im = image_of(relief())
        d = doc_with(im)
        with tempfile.TemporaryDirectory() as tmp:
            png = pathlib.Path(tmp) / 'retouche.png'
            png.write_bytes(b'PNG retouchee')
            watched = []
            fake = SimpleNamespace(
                _image_files={str(png): im.id},
                _image_watch=SimpleNamespace(files=lambda: watched, addPath=watched.append),
                canvas=SimpleNamespace(doc=d, selection=[im], invalidate=lambda: None),
                push_undo=lambda: None, _on_doc_changed=lambda: None,
                statusBar=lambda: SimpleNamespace(showMessage=lambda *a: None))
            main_window.MainWindow._image_changed(fake, str(png))
        new = d.layers[0].items[0]
        self.assertIsNot(new, im)
        self.assertEqual(new.fmt, 'png')
        self.assertNotIn('vnd_obj', new.extra)
        self.assertIn('vnd_obj', im.extra)                       # l'image d'avant (annulation) le garde


if __name__ == '__main__':
    unittest.main()
