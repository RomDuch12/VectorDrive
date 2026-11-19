"""Round 753 : un PDF ou un Illustrator se lit comme Inkscape le montre : ses calques (contenu optionnel), masqués
s'ils le sont dans le fichier ; le détourage coupe ; une surface peinte est fermée, en règle non nulle ; un aplat
blanc est retiré de ce qu'il recouvre et rangé à part, masqué."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import pathops as PO
from vectordrive.io import pdf
from vectordrive.io.pdf import PT_MM

app = QApplication.instance() or QApplication([])


def make_pdf(content: str, oc_props: str = '', extra_objects: dict | None = None, xobjects: str = '') -> pathlib.Path:
    """PDF d'une page de 200 × 200 pt, écrit à la main : 5 et 6 sont les calques « Vu » et « Caché »."""
    stream = content.encode('latin-1')
    objs = {
        1: b'<< /Type /Catalog /Pages 2 0 R ' + oc_props.encode() + b' >>',
        2: b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
        3: ('<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] /Contents 4 0 R /Resources << '
            '/Properties << /MC0 5 0 R /MC1 6 0 R >> ' + xobjects + ' >> >>').encode(),
        4: b'<< /Length ' + str(len(stream)).encode() + b' >>\nstream\n' + stream + b'\nendstream',
        5: b'<< /Type /OCG /Name (Vu) >>',
        6: b'<< /Type /OCG /Name (Cach\xe9) >>',
    }
    objs.update(extra_objects or {})
    out = bytearray(b'%PDF-1.5\n')
    offsets = {}
    for n in sorted(objs):
        offsets[n] = len(out)
        out += str(n).encode() + b' 0 obj\n' + objs[n] + b'\nendobj\n'
    xref = len(out)
    size = max(objs) + 1
    out += b'xref\n0 ' + str(size).encode() + b'\n0000000000 65535 f \n'
    for n in range(1, size):
        out += b'%010d 00000 n \n' % offsets[n]
    out += b'trailer\n<< /Size ' + str(size).encode() + b' /Root 1 0 R >>\nstartxref\n' + str(xref).encode() + b'\n%%EOF\n'
    p = pathlib.Path(tempfile.mkdtemp()) / 'essai.pdf'
    p.write_bytes(bytes(out))
    return p


OC = '/OCProperties << /OCGs [5 0 R 6 0 R] /D << /ON [5 0 R] /OFF [6 0 R] /Order [5 0 R 6 0 R] >> >>'


def layers(doc):
    return {L.name: L for L in doc.layers}


def mm2(pt2):
    return pt2 * PT_MM * PT_MM


class TestOptionalContent(unittest.TestCase):
    def test_layers_and_state(self):
        d = pdf.read(make_pdf('/OC /MC0 BDC 0 0 m 50 0 l 50 50 l h S EMC\n/OC /MC1 BDC 60 0 m 90 0 l 90 50 l h S EMC', OC))
        L = layers(d)
        self.assertEqual(set(L), {'Vu', 'Caché'})
        self.assertTrue(L['Vu'].visible)
        self.assertFalse(L['Caché'].visible)
        self.assertEqual((len(L['Vu'].items), len(L['Caché'].items)), (1, 1))
        self.assertEqual([x.name for x in d.layers], ['Vu', 'Caché'])          # ordre du fichier
        bb = d.bbox(visible_only=True)
        self.assertAlmostEqual(bb[2], 50 * PT_MM, places=6)
        self.assertAlmostEqual(d.bbox()[2], 90 * PT_MM, places=6)

    def test_outside_layers_keep_page(self):
        d = pdf.read(make_pdf('0 0 m 50 0 l S\n/OC /MC0 BDC 60 0 m 90 0 l S EMC', OC))
        self.assertEqual([x.name for x in d.layers], ['Page 1', 'Vu'])

    def test_no_optional_content(self):
        d = pdf.read(make_pdf('0 0 m 50 0 l S'))
        self.assertEqual([x.name for x in d.layers], ['Page 1'])
        self.assertTrue(d.layers[0].visible)

    def test_marks_without_layers(self):
        d = pdf.read(make_pdf('/Artifact BMC 0 0 m 50 0 l S EMC /Span << /X 1 >> BDC 60 0 m 90 0 l S EMC'))
        self.assertEqual([len(x.items) for x in d.layers], [2])

    def test_nested_marks(self):
        d = pdf.read(make_pdf('/OC /MC1 BDC /Artifact BMC 0 0 m 50 0 l S EMC 0 9 m 50 9 l S EMC', OC))
        self.assertEqual(len(layers(d)['Caché'].items), 2)

    def test_base_state_off(self):
        props = '/OCProperties << /OCGs [5 0 R 6 0 R] /D << /BaseState /OFF /ON [6 0 R] >> >>'
        L = layers(pdf.read(make_pdf('/OC /MC0 BDC 0 0 m 50 0 l S EMC /OC /MC1 BDC 0 9 m 50 9 l S EMC', props)))
        self.assertFalse(L['Vu'].visible)
        self.assertTrue(L['Caché'].visible)

    def test_form_on_a_layer(self):
        form = b'<< /Type /XObject /Subtype /Form /BBox [0 0 200 200] /OC 6 0 R /Length 18 >>\nstream\n0 0 m 50 0 l 50 9 l\nendstream'
        form = form.replace(b'0 0 m 50 0 l 50 9 l', b'0 0 m 50 0 l 50 9 l S').replace(b'/Length 18', b'/Length 21')
        d = pdf.read(make_pdf('/F0 Do', OC, {7: form}, '/XObject << /F0 7 0 R >>'))
        self.assertFalse(layers(d)['Caché'].visible)
        self.assertEqual(len(layers(d)['Caché'].items), 1)

    def test_several_pages_share_layer(self):
        # une seule page ici, mais deux passages dans le même calque : un seul calque
        d = pdf.read(make_pdf('/OC /MC0 BDC 0 0 m 50 0 l S EMC /OC /MC1 BDC 0 5 m 9 5 l S EMC /OC /MC0 BDC 0 9 m 50 9 l S EMC', OC))
        self.assertEqual(len(layers(d)['Vu'].items), 2)
        self.assertEqual([x.name for x in d.layers], ['Vu', 'Caché'])


class TestSurfaces(unittest.TestCase):
    def test_painted_surface_is_closed(self):
        d = pdf.read(make_pdf('0 0 m 50 0 l 50 50 l 0 50 l f'))
        c = d.layers[0].items[0].path.contours[0]
        self.assertTrue(c.closed)
        self.assertEqual(c.closing_gap(), 0.0)
        self.assertTrue(d.layers[0].items[0].filled)

    def test_stroke_stays_open(self):
        c = pdf.read(make_pdf('0 0 m 50 0 l 50 50 l S')).layers[0].items[0].path.contours[0]
        self.assertFalse(c.closed)

    def test_nonzero_overlap_united(self):
        d = pdf.read(make_pdf('0 0 m 50 0 l 50 50 l 0 50 l h 25 25 m 75 25 l 75 75 l 25 75 l h f'))
        s = d.layers[0].items[0]
        self.assertAlmostEqual(PO.area(s.path), mm2(50 * 50 * 2 - 25 * 25), places=3)
        self.assertEqual(len(s.path.contours), 1)                              # réunis

    def test_evenodd_kept(self):
        d = pdf.read(make_pdf('0 0 m 50 0 l 50 50 l 0 50 l h 25 25 m 75 25 l 75 75 l 25 75 l h f*'))
        self.assertEqual(len(d.layers[0].items[0].path.contours), 2)

    def test_opposite_windings_keep_their_curves(self):
        ring = '0 0 m 100 0 l 100 100 l 0 100 l h 25 25 m 25 75 l 75 75 l 75 25 l h f'
        s = pdf.read(make_pdf(ring)).layers[0].items[0]
        self.assertEqual(len(s.path.contours), 2)
        self.assertAlmostEqual(PO.area(s.path), mm2(100 * 100 - 50 * 50), places=3)


class TestWhite(unittest.TestCase):
    def test_white_under_goes_apart(self):
        d = pdf.read(make_pdf('1 1 1 rg 0 0 50 50 re f 0 0 0 rg 60 0 30 30 re f'))
        L = layers(d)
        self.assertEqual(len(L['Page 1'].items), 1)
        self.assertTrue(L['Page 1'].visible)
        self.assertEqual(len(L['Page 1 (blanc)'].items), 1)
        self.assertFalse(L['Page 1 (blanc)'].visible)
        self.assertNotIn('pdf_blanc', L['Page 1'].items[0].extra)
        self.assertNotIn('pdf_blanc', L['Page 1 (blanc)'].items[0].extra)

    def test_white_over_cuts(self):
        d = pdf.read(make_pdf('0 0 0 rg 0 0 100 100 re f 1 1 1 rg 25 25 50 50 re f'))
        L = layers(d)
        self.assertEqual(len(L['Page 1'].items), 1)
        self.assertAlmostEqual(PO.area(L['Page 1'].items[0].path), mm2(100 * 100 - 50 * 50), places=3)
        self.assertTrue(any('aplats blancs' in r for r in d.report))

    def test_white_covers_all(self):
        d = pdf.read(make_pdf('0 0 0 rg 10 10 20 20 re f 1 1 1 rg 0 0 100 100 re f'))
        self.assertEqual(layers(d)['Page 1'].items, [])

    def test_white_fill_with_stroke_stays_outline(self):
        d = pdf.read(make_pdf('0 G 1 1 1 rg 0 0 50 50 re B'))
        s = d.layers[0].items[0]
        self.assertFalse(s.filled)
        self.assertEqual(len(d.layers), 1)

    def test_white_stroke_shape_cuts_below(self):
        d = pdf.read(make_pdf('0 0 0 rg 0 0 100 100 re f 0 G 1 1 1 rg 25 25 50 50 re B'))
        self.assertAlmostEqual(PO.area(d.layers[0].items[0].path), mm2(100 * 100 - 50 * 50), places=3)
        self.assertEqual(len(d.layers[0].items), 2)

    def test_cmyk_white(self):
        d = pdf.read(make_pdf('0 0 0 0 k 0 0 50 50 re f'))
        self.assertEqual(layers(d)['Page 1'].items, [])


class TestClip(unittest.TestCase):
    def test_clip_cuts_surface(self):
        d = pdf.read(make_pdf('q 0 0 50 50 re W n 0 0 100 100 re f Q 60 60 10 10 re f'))
        items = d.layers[0].items
        self.assertEqual(len(items), 2)
        self.assertAlmostEqual(PO.area(items[0].path), mm2(50 * 50), places=3)
        self.assertAlmostEqual(PO.area(items[1].path), mm2(10 * 10), places=3)  # Q : détourage levé

    def test_clip_outside_dropped(self):
        d = pdf.read(make_pdf('q 0 0 50 50 re W n 60 60 10 10 re f 60 60 m 90 90 l S Q'))
        self.assertEqual(d.layers[0].items, [])

    def test_inside_keeps_its_curves(self):
        curve = '10 10 m 40 10 40 40 10 40 c h f'
        d = pdf.read(make_pdf('q 0 0 50 50 re W n ' + curve + ' Q'))
        p = d.layers[0].items[0].path
        self.assertEqual(p, pdf.read(make_pdf(curve)).layers[0].items[0].path)

    def test_open_stroke_over_edge_kept(self):
        d = pdf.read(make_pdf('q 0 0 50 50 re W n 10 10 m 90 90 l S Q'))
        self.assertEqual(len(d.layers[0].items), 1)

    def test_nested_clips(self):
        d = pdf.read(make_pdf('q 0 0 50 50 re W n 25 25 50 50 re W n 0 0 100 100 re f Q'))
        self.assertAlmostEqual(PO.area(d.layers[0].items[0].path), mm2(25 * 25), places=3)

    def test_clip_path_not_drawn(self):
        self.assertEqual(pdf.read(make_pdf('0 0 50 50 re W n')).layers[0].items, [])

    def test_paint_then_clip(self):
        d = pdf.read(make_pdf('0 0 50 50 re W f 0 0 100 100 re f'))
        self.assertEqual(len(d.layers[0].items), 2)
        self.assertAlmostEqual(PO.area(d.layers[0].items[1].path), mm2(50 * 50), places=3)


class TestWindow(unittest.TestCase):
    def test_hidden_layers_and_fit(self):
        from vectordrive.ui.main_window import MainWindow
        path = make_pdf('/OC /MC0 BDC 0 0 m 50 0 l 50 50 l h S EMC\n/OC /MC1 BDC 180 180 m 190 180 l 190 190 l h S EMC', OC)
        w = MainWindow()
        try:
            self.assertTrue(w.open_path(str(path)))
            L = layers(w.canvas.doc)
            self.assertFalse(L['Caché'].visible)
            w.canvas.doc.plate = None
            w.canvas.fit()                                                     # le cadrage suit ce qui se voit
            self.assertGreater(w.canvas.scale, min(max(w.canvas.width(), 100), max(w.canvas.height(), 100)) / (60 * PT_MM) * 0.5)
        finally:
            w.modified = False
            w.close()

    def test_vnd_export_opens_on_visible_layer(self):
        import struct
        from vectordrive.io import vnd, vnd_write
        d = pdf.read(make_pdf('/OC /MC1 BDC 60 0 m 90 0 l 90 50 l h S EMC\n/OC /MC0 BDC 0 0 m 50 0 l 50 50 l h S EMC', OC))
        self.assertEqual(d.layers[0].name, 'Caché')
        d.extra['vnd_premier_plan'] = True               # round 1099 : réglage « premier calque montré en tête »
        data, _r = vnd_write.write_document(d)
        root, _ar = vnd.parse(data)
        self.assertEqual(root.children[0].fields['layer_name'], 'Vu')
        self.assertEqual(struct.unpack_from('<IIII', root.children[1].fields['attrs'])[3], 0)


if __name__ == '__main__':
    unittest.main()
