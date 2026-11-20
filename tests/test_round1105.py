"""Round 1105 : une page PDF avec du texte (chaînes, tableaux de `TJ`) était découpée par pypdf, vingt fois plus lent ;
chaînes et tableaux découpés par VectorDrive, mêmes opérations que pypdf (opérateurs, nombres, noms)."""
import io
import os
import tempfile
import time
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1105.ini'))

from vectordrive.io import pdf  # noqa: E402

TEXT_PAGE = (b'q 0.5 0 0 0.5 10 20 cm 1 0 0 rg\n'
             b'BT /F1 12 Tf 1 0 0 1 72 700 Tm (Bonjour \\(le\\) monde) Tj\n'
             b'[(A) -120 (V) 30.5 <48656C6C6F> -.5 (x (imbriqu\\351e) y)] TJ\n'
             b'(ligne\\\\) \' 2 1 (suite) " ET\n'
             b'% commentaire (pas une cha\\356ne\n'
             b'/OC /MC0 BDC 0 0 m 100 0 l 100 50 l h f EMC [3 2] 0 d 1 w 10 10 50 20 re S Q\n'
             b'/Im1 Do\n')


def pypdf_ops(data: bytes) -> list:
    from pypdf.generic import ContentStream, DecodedStreamObject
    s = DecodedStreamObject()
    s.set_data(data)
    return ContentStream(s, None).operations


def simple(v):
    """Valeur comparable : nombres, noms ; chaînes et tableaux par leur forme."""
    from pypdf.generic import NameObject
    if isinstance(v, (list, tuple)):
        return [simple(x) for x in v]
    if isinstance(v, NameObject) or (isinstance(v, str) and v[:1] == '/'):
        return str(v)
    if isinstance(v, (bytes, str)):
        return 'chaîne'
    return float(v)


class TestScan(unittest.TestCase):
    def test_text_page_fast_same_as_pypdf(self):
        got = pdf.fast_operations(TEXT_PAGE)
        self.assertIsNotNone(got)                                          # avant : None (laissé à pypdf)
        ref = pypdf_ops(TEXT_PAGE)
        self.assertEqual([o if isinstance(o, str) else o.decode('latin-1') for _a, o in ref], [o for _a, o in got])
        for (ra, ro), (ga, go) in zip(ref, got):
            self.assertEqual(simple(list(ra)), simple(ga), go)

    def test_strings(self):
        ops = pdf.fast_operations(b'BT (a\\)b(c)d) Tj <4142 43> Tj ET')
        self.assertEqual(ops, [([], 'BT'), ([b'a\\)b(c)d'], 'Tj'), ([b'4142 43'], 'Tj'), ([], 'ET')])
        self.assertEqual(pdf.fast_operations(b'[1 [2 3] (x)] 0 d'), [([[1.0, [2.0, 3.0], b'x'], 0.0], 'd')])

    def test_names_and_nul_like_pypdf(self):
        # relecture : « #xx » dans un nom décodé (calque d'un BDC, forme d'un Do) ; l'octet nul est un blanc
        for data in (b'/OC /MC#30 BDC (a) Tj EMC /Im#31 Do', b'BT (a)\x00Tj ET', b'0 0 m 10 0 l S /G#53 gs'):
            with self.subTest(data=data):
                got = pdf.fast_operations(data)
                self.assertIsNotNone(got)
                ref = pypdf_ops(data)
                self.assertEqual([o if isinstance(o, str) else o.decode('latin-1') for _a, o in ref], [o for _a, o in got])
                for (ra, _ro), (ga, _go) in zip(ref, got):
                    self.assertEqual(simple(list(ra)), simple(ga))
        self.assertEqual(pdf.fast_operations(b'/OC /MC#30 BDC (a) Tj EMC')[0][0], ['/OC', '/MC0'])
        # l'octet nul sépare (norme PDF ; pypdf le colle à l'opérateur qui précède : « m\x0010 »)
        self.assertEqual(pdf.fast_operations(b'0 0 m\x0010 0 l S'), [([0.0, 0.0], 'm'), ([10.0, 0.0], 'l'), ([], 'S')])

    def test_left_to_pypdf(self):
        for data in (b'/Span << /ActualText (x) >> BDC EMC',              # dictionnaire
                     b'BI /W 1 /H 1 /BPC 8 /CS /G ID \x00 EI',            # image en ligne
                     b'(pas ferm\xe9e Tj', b'[1 2 0 d', b'1 2] 0 d', b'[1 m] 0 d', b'(a) true Tj', b'> 1 w'):
            with self.subTest(data=data):
                self.assertIsNone(pdf.fast_operations(data))

    def test_plain_paths_unchanged(self):
        data = b'0 0 m 10 0 l 10 10 l h f'
        self.assertEqual(pdf.fast_operations(data),
                         [([0.0, 0.0], 'm'), ([10.0, 0.0], 'l'), ([10.0, 10.0], 'l'), ([], 'h'), ([], 'f')])

    def test_faster_than_pypdf(self):
        data = TEXT_PAGE * 400

        def best(fn):
            out = []
            for _ in range(3):
                t = time.perf_counter()
                got = fn(data)
                out.append(time.perf_counter() - t)
            return min(out), got
        t_fast, fast = best(pdf.fast_operations)
        t_ref, ref = best(pypdf_ops)
        self.assertEqual(len(fast), len(ref))
        self.assertLess(t_fast * 1.5, t_ref, (t_fast, t_ref))

    def test_text_still_read(self):
        # un PDF avec texte : formes et textes vivants comme avant
        from reportlab.pdfgen import canvas
        path = os.path.join(tempfile.mkdtemp(), 't.pdf')
        c = canvas.Canvas(path)
        c.setFont('Helvetica', 14)
        c.drawString(72, 700, 'Plaque (gravée)')
        c.rect(50, 650, 200, 100)
        c.save()
        doc = pdf.read(path)
        texts = [it for L in doc.layers for it in L.items if hasattr(it, 'font')]
        shapes = [it for L in doc.layers for it in L.items if hasattr(it, 'path') and not hasattr(it, 'font')]
        self.assertEqual([t.text for t in texts], ['Plaque (gravée)'])
        self.assertEqual(len(shapes), 1)


if __name__ == '__main__':
    unittest.main()
