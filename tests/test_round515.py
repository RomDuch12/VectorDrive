"""Round 515 : import PDF — flux de tracés simples découpés sans pypdf (BAT de 10 000 gravures : 13 s →
5 s), mêmes opérations que pypdf ; flux à chaînes, tableaux, dictionnaires ou images en ligne : pypdf."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from pypdf import PdfReader
from pypdf.generic import ContentStream

from vectordrive.core import geom
from vectordrive.core.document import Document, Shape
from vectordrive.io import pdf, proof as P, registry


def norm(ops):
    return [([float(x) if not isinstance(x, str) else str(x) for x in o],
             op.decode('latin-1') if isinstance(op, bytes) else op) for o, op in ops]


class TestFastContent(unittest.TestCase):
    def test_same_as_pypdf(self):
        doc = Document()
        for i in range(40):
            doc.add(Shape(path=geom.Path([geom.circle((6 * (i % 8), 6 * (i // 8)), 2)])))
        out = os.path.join(tempfile.mkdtemp(), 'bat.pdf')
        P.write(doc, out, P.ProofInfo(reference='essai'))
        r = PdfReader(out, strict=False)
        c = r.pages[0].get_contents()
        fast = pdf.fast_operations(pdf.stream_bytes(c))
        self.assertIsNotNone(fast)
        self.assertEqual(norm(fast), norm(ContentStream(c, r).operations))
        back = registry.open_document(out)
        self.assertGreaterEqual(sum(1 for _ in back.iter_leaves()), 40)

    def test_tokens_and_fallback(self):
        ops = pdf.fast_operations(b'q 1 0 0 1 10 -2.5 cm % note\n0 0 m .5 1 l h /GS0 gs S Q')
        self.assertEqual(ops, [([], 'q'), ([1.0, 0.0, 0.0, 1.0, 10.0, -2.5], 'cm'), ([0.0, 0.0], 'm'),
                               ([0.5, 1.0], 'l'), ([], 'h'), (['/GS0'], 'gs'), ([], 'S'), ([], 'Q')])
        for data in (b'BI /W 1 /H 1 ID x EI', b'true 0 0 m'):
            self.assertIsNone(pdf.fast_operations(data), data)
        for data in (b'BT (Bonjour) Tj ET', b'[3 2] 0 d 0 0 m 1 1 l S', b'<00150016> Tj'):   # round 1105 : ici
            self.assertIsNotNone(pdf.fast_operations(data), data)
        self.assertIsNone(pdf.fast_operations(None))
        self.assertIsNotNone(pdf.fast_operations(b'0 0 m 10 0 l S BIG 1 0 0 RG'))   # BI dans un mot : pas une image


if __name__ == '__main__':
    unittest.main()
