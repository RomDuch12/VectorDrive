"""Round 970 : PDF et EPS — un tracé tiré qui revient exactement à son point de départ est lu en contour fermé ;
un bloc de texte vide d'un PDF ne vaut plus la remarque « texte non vectorisé »."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r970.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])

from vectordrive.io import pdf, postscript  # noqa: E402

EPS = b'%!PS-Adobe-2.0 EPSF-1.2\n%%BoundingBox: 0 0 200 100\n%%EndComments\n%%EndProlog\n'


def make_pdf(content: str) -> pathlib.Path:
    """PDF d'une page de 200 × 200 pt, écrit à la main."""
    stream = content.encode('latin-1')
    objs = {
        1: b'<< /Type /Catalog /Pages 2 0 R >>',
        2: b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
        3: b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] /Contents 4 0 R /Resources << >> >>',
        4: b'<< /Length ' + str(len(stream)).encode() + b' >>\nstream\n' + stream + b'\nendstream',
    }
    out = bytearray(b'%PDF-1.5\n')
    offsets = {}
    for n in sorted(objs):
        offsets[n] = len(out)
        out += str(n).encode() + b' 0 obj\n' + objs[n] + b'\nendobj\n'
    xref = len(out)
    out += b'xref\n0 5\n0000000000 65535 f \n'
    for n in range(1, 5):
        out += b'%010d 00000 n \n' % offsets[n]
    out += b'trailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n' + str(xref).encode() + b'\n%%EOF\n'
    p = pathlib.Path(tempfile.mkdtemp()) / 'essai.pdf'
    p.write_bytes(bytes(out))
    return p


def of_pdf(content: str):
    doc = pdf.read(make_pdf(content))
    return [(len(c.segments), c.closed) for L in doc.layers for it in L.items for c in it.path.contours], doc.report


def of_eps(body: str):
    items, _report = postscript.read_bytes(EPS + body.encode('latin-1') + b'\n%%EOF\n')
    return [(len(c.segments), c.closed) for it in items for c in it.path.contours]


class Returning(unittest.TestCase):

    def test_pdf_stroke_back_to_its_start_is_closed(self):
        # le tour d'un rectangle tiré sans « h », comme l'écrit TypeEdit
        self.assertEqual(of_pdf('n 10 10 m 50 10 l 50 40 l 10 40 l 10 10 l 0 w S')[0], [(4, True)])     # avant : (4, False)
        self.assertEqual(of_pdf('10 10 m 50 10 l 50 40 l S')[0], [(2, False)])           # ne revient pas : ouvert
        self.assertEqual(of_pdf('10 10 m 50 40 l 10 10 l S')[0], [(2, False)])           # aller-retour : un trait
        self.assertEqual(of_pdf('10 10 m 30 60 70 60 90 10 c 10 10 l S')[0], [(2, True)])    # une courbe et son retour

    def test_eps_stroke_back_to_its_start_is_closed(self):
        self.assertEqual(of_eps('10 10 moveto 50 10 lineto 50 40 lineto 10 40 lineto 10 10 lineto stroke'), [(4, True)])
        self.assertEqual(of_eps('10 10 moveto 50 10 lineto 50 40 lineto stroke'), [(2, False)])

    def test_an_empty_text_block_is_not_text(self):
        told, report = of_pdf('q BT 36 805.89 Td ET Q n 10 10 m 50 10 l 50 40 l S')
        self.assertEqual(told, [(2, False)])
        self.assertNotIn(pdf.TEXT_REMARK, report)                    # avant : « texte PDF non vectorisé »
        _told, report = of_pdf('BT 10 10 Td (abc) Tj ET 10 10 m 50 10 l S')
        self.assertIn(pdf.TEXT_REMARK, report)                       # du texte montré, sans police pour le reprendre


if __name__ == '__main__':
    unittest.main()
