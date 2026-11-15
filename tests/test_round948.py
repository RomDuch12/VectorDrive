"""Round 948 : BAT — filigrane en fond du dessin ; dans le PDF, le dessin en image (son tracé n'y est plus) ; les
remarques passent à la ligne dans leur case ; le dossier du PDF ouvert après l'écriture."""
import math
import os
import pathlib
import re
import tempfile
import unittest
import zlib
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r948.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])

from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Document, Plate, Shape  # noqa: E402
from vectordrive.io import proof  # noqa: E402


def star(n=120):
    pts = [((40 + (18 if k % 2 else 9) * math.cos(2 * math.pi * k / n)),
            (25 + (18 if k % 2 else 9) * math.sin(2 * math.pi * k / n))) for k in range(n)]
    return Shape(path=geom.Path([geom.polyline(pts, closed=True)]))


def drawing():
    d = Document()
    d.plate = Plate(width=80.0, height=50.0)
    d.layers[0].items.append(star())
    return d


def info_with(**kw):
    i = proof.ProofInfo(company='ACME', client='Client', reference='R1')
    for k, v in kw.items():
        setattr(i, k, v)
    return i


def content(pdf: bytes) -> str:
    """Le contenu de la page (premier flux du fichier), décompressé."""
    m = re.search(rb'/Filter /FlateDecode >>\nstream\n(.*?)\nendstream', pdf, re.S)
    return zlib.decompress(m.group(1)).decode('ascii')


def light(pr):
    return pr.fill and pr.width == 0 and min(pr.color) > 0.7 and max(pr.color) - min(pr.color) > 0.02


class Bat(unittest.TestCase):

    def test_watermark_lies_behind_the_drawing(self):
        d = drawing()
        plain, PW, PH = proof.build(d, info_with())
        prims, PW, PH = proof.build(d, info_with(watermark=True))
        marks = [pr for pr in prims if light(pr)]
        self.assertGreaterEqual(len(marks), 6)                              # avant : aucun filigrane
        self.assertEqual(len(prims) - len(plain), len(marks))
        for pr in marks:
            b = pr.path.bbox()
            self.assertTrue(10 < b[0] and b[2] < PW - 10 and 10 + 42 < b[1] and b[3] < PH - 10)
        first_line = next(k for k, pr in enumerate(prims) if pr.width > 0 and pr.path.contours
                          and len(pr.path.contours[0].segments) >= 100)     # l'étoile
        self.assertLess(max(prims.index(pr) for pr in marks), first_line)   # en fond : avant le dessin
        other, _w, _h = proof.build(d, info_with(watermark=True, watermark_text='CONFIDENTIEL'))
        self.assertNotEqual(len([pr for pr in other if light(pr)]), len(marks))
        mono, _w, _h = proof.build(d, info_with(watermark=True, mono=True))
        grey = [pr for pr in mono if pr.fill and pr.width == 0 and 0.8 < pr.color[0] < 0.95 and len(set(pr.color)) == 1]
        self.assertEqual(len(grey), len(marks))                             # noir et blanc : gris clair, pas noir

    def test_pdf_can_hold_the_drawing_as_an_image(self):
        d = drawing()
        with tempfile.TemporaryDirectory() as tmp:
            f = pathlib.Path(tmp) / 'bat.pdf'
            proof.write(d, f, info_with(watermark=True))
            vector = f.read_bytes()
            proof.write(d, f, info_with(watermark=True, as_image=True, image_dpi=200))
            image = f.read_bytes()
        lines = lambda s: len(re.findall(r' l\n', s + '\n'))
        # l'étoile (120 droites) et le filigrane ne sont plus des tracés ; avant : ils restaient dans le PDF
        self.assertGreaterEqual(lines(content(vector)) - lines(content(image)), 120)
        self.assertEqual(vector.count(b'/Subtype /Image'), 0)
        self.assertEqual(image.count(b'/Subtype /Image'), 1)
        w, h = (int(x) for x in re.search(rb'/Width (\d+) /Height (\d+)', image).groups())
        self.assertGreater(min(w, h), 800)                                  # 200 dpi sur la zone du dessin
        self.assertIn('/Im0 Do', content(image))

    def test_notes_wrap_inside_their_cell(self):
        d = drawing()
        long = ('Graver le logo au centre de la plaque, en respectant la marge de cinq millimètres ; '
                'fond sablé, bords polis, perçage des quatre coins au diamètre trois.')
        prims, PW, PH = proof.build(d, info_with(notes=long))
        tw = PW - 20
        c2, c3 = 10 + tw * 0.62, 10 + tw * 0.80
        cell = [pr for pr in prims if pr.fill and pr.width == 0 and pr.path.contours
                and c2 < pr.path.bbox()[0] < c3 and pr.path.bbox()[1] < 10 + 42]
        self.assertGreaterEqual(len(cell), 4)                               # « Remarques » et plusieurs lignes
        self.assertLess(max(pr.path.bbox()[2] for pr in cell), c3)          # avant : une ligne, qui sortait de la case
        self.assertGreater(min(pr.path.bbox()[1] for pr in cell), 10)
        lines, size, pitch = proof.notes_lines(long * 6, c3 - c2 - 4, 32)
        self.assertLess(size, 2.6)                                          # beaucoup de texte : corps réduit
        self.assertLessEqual(len(lines), int(32 // pitch) + 1)


class Window(unittest.TestCase):

    def test_folder_is_shown_after_the_pdf(self):
        from vectordrive.ui import reveal as RV
        from vectordrive.ui.batdialog import BatDialog
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            w.canvas.doc.add(star())
            with tempfile.TemporaryDirectory() as tmp, mock.patch.object(RV, 'reveal') as shown:
                out = os.path.join(tmp, 'bat.pdf')
                self.assertEqual(w.write_proof(out, info_with()), out)
                shown.assert_not_called()
                self.assertEqual(w.write_proof(out, info_with(open_folder=True)), out)
                self.assertEqual(shown.call_count, 1)                       # avant : jamais ouvert
                self.assertEqual(str(shown.call_args[0][0]), out)
            dlg = BatDialog(w, w.canvas.doc, info_with())
            self.assertFalse(dlg.as_image.isChecked())
            dlg.watermark.setChecked(True)
            self.assertTrue(dlg.as_image.isChecked())                       # le filigrane coché : l'image aussi
            dlg.watermark_text.setText('BFM')
            dlg.image_dpi.setValue(450)
            dlg.open_folder.setChecked(True)
            i = dlg.result_info()
            self.assertEqual((i.watermark, i.watermark_text, i.as_image, i.image_dpi, i.open_folder),
                             (True, 'BFM', True, 450, True))
            dlg.close()
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
