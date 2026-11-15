"""Round 992 : BAT, filigrane — retour de l'atelier « Filigrane : + de paramètres de réglage, logo possible ». Taille,
angle, écart, intensité, disposition (répété ou un seul au milieu) ; motif : le texte ou un logo (dessin ou image, celui de
l'en-tête ou un autre), dans la couleur du filigrane. Les réglages d'office donnent le filigrane d'avant."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtGui import QColor, QImage, QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from vectordrive.core.document import Document, Plate  # noqa: E402
from vectordrive.io import proof  # noqa: E402
from vectordrive.io.raster import qimage_of  # noqa: E402

app = QApplication.instance() or QApplication([])
BOX = (10.0, 52.0, 200.0, 287.0)


def info_with(**kw):
    i = proof.ProofInfo(company='ACME', client='Client', reference='R1', watermark=True)
    for k, v in kw.items():
        setattr(i, k, v)
    return i


def box_of(prims):
    return proof._prims_box(prims)


def motifs(prims, info):
    return len(prims) // max(1, len(proof.watermark_motif(info)))


class Settings(unittest.TestCase):

    def test_size_angle_gap_strength(self):
        base = proof.watermark_prims(info_with(), BOX)
        self.assertGreater(len(base), 6)
        big = proof.watermark_prims(info_with(watermark_size=20.0), BOX)
        self.assertLess(len(big), len(base))
        flat = info_with(watermark_angle=0.0)
        one = proof.watermark_motif(flat)
        b = box_of(proof.watermark_prims(flat, BOX)[:len(one)])
        self.assertAlmostEqual(b[3] - b[1], box_of(one)[3] - box_of(one)[1], places=6)      # à plat : pas incliné
        wide = proof.watermark_prims(info_with(watermark_gap=40.0), BOX)
        self.assertLess(len(wide), len(base))
        blue = (0.12, 0.31, 0.61)
        self.assertEqual(proof.watermark_color(info_with(watermark_strength=50)), proof.tint(blue, 0.5))
        self.assertEqual(proof.watermark_color(info_with()), proof.tint(blue, 0.2))           # d'office : comme avant
        self.assertEqual(proof.watermark_color(info_with(watermark_strength='x')), proof.tint(blue, 0.2))   # illisible
        for k in ('watermark_kind', 'watermark_logo', 'watermark_size', 'watermark_angle', 'watermark_gap',
                  'watermark_strength', 'watermark_layout'):
            self.assertIn(k, proof.LAYOUT_FIELDS)
            self.assertIn(k, proof.preset_of(info_with()))

    def test_one_in_the_middle(self):
        info = info_with(watermark_layout='centre', watermark_size=12.0)
        got = proof.watermark_prims(info, BOX)
        self.assertEqual(motifs(got, info), 1)
        b = box_of(got)
        self.assertAlmostEqual((b[0] + b[2]) / 2, (BOX[0] + BOX[2]) / 2, places=6)
        self.assertAlmostEqual((b[1] + b[3]) / 2, (BOX[1] + BOX[3]) / 2, places=6)
        huge = proof.watermark_prims(info_with(watermark_layout='centre', watermark_size=200.0,
                                               watermark_text='TRES GRAND FILIGRANE'), BOX)
        b = box_of(huge)
        self.assertTrue(b[0] >= BOX[0] - 1e-6 and b[2] <= BOX[2] + 1e-6 and b[1] >= BOX[1] - 1e-6 and b[3] <= BOX[3] + 1e-6)


class Logo(unittest.TestCase):

    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix='vd992_'))

    def test_drawn_logo_in_the_watermark_colour(self):
        svg = self.tmp / 'logo.svg'
        svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="40mm" height="20mm" viewBox="0 0 40 20">'
                       '<rect x="0" y="0" width="40" height="20" fill="#ff0000"/>'
                       '<rect x="10" y="5" width="20" height="10" fill="#00ff00"/></svg>', encoding='utf-8')
        info = info_with(watermark_kind='logo', watermark_logo=str(svg), watermark_angle=0.0, watermark_size=10.0)
        one = proof.watermark_motif(info)
        self.assertTrue(one and all(pr.fill and pr.color == proof.watermark_color(info) for pr in one))
        b = box_of(one)
        self.assertAlmostEqual(b[3] - b[1], 20.0, places=3)                      # le double de la hauteur du texte
        self.assertAlmostEqual(b[2] - b[0], 40.0, places=3)
        header = info_with(watermark_kind='logo', logo=str(svg), watermark_angle=0.0, watermark_size=10.0)
        self.assertAlmostEqual(box_of(proof.watermark_motif(header))[3] - box_of(proof.watermark_motif(header))[1], 20.0,
                               places=3)                                        # sans logo du filigrane : celui de l'en-tête
        self.assertGreater(len(proof.watermark_prims(info, BOX)), 3)

    def test_image_logo_white_disappears(self):
        png = self.tmp / 'logo.png'
        img = QImage(40, 20, QImage.Format.Format_RGB32)
        img.fill(QColor('white'))
        p = QPainter(img)
        p.fillRect(0, 0, 20, 20, QColor('black'))
        p.end()
        img.save(str(png))
        info = info_with(watermark_kind='logo', watermark_logo=str(png), watermark_size=10.0)
        one = proof.watermark_motif(info)
        self.assertEqual(len(one), 1)
        self.assertIsNotNone(one[0].image)
        q = qimage_of(one[0].image).convertToFormat(QImage.Format.Format_ARGB32)
        self.assertEqual(q.pixelColor(5, 10).alpha(), 255)                      # le noir : plein…
        col = proof.watermark_color(info)
        self.assertEqual((q.pixelColor(5, 10).red(), q.pixelColor(5, 10).blue()), (round(col[0] * 255), round(col[2] * 255)))
        self.assertEqual(q.pixelColor(35, 10).alpha(), 0)                       # … le blanc : rien
        corners = [one[0].matrix.apply(c) for c in ((0, 0), (1, 1))]
        self.assertAlmostEqual(abs(corners[0][1] - corners[1][1]), 20.0, places=6)
        self.assertAlmostEqual(abs(corners[0][0] - corners[1][0]), 40.0, places=6)
        with tempfile.TemporaryDirectory() as tmp:
            d = Document()
            d.plate = Plate(width=80.0, height=50.0)
            f = pathlib.Path(tmp) / 'bat.pdf'
            proof.write(d, f, info_with(watermark_kind='logo', watermark_logo=str(png)))
            self.assertEqual(f.read_bytes().count(b'/SMask'), 1)                # transparente, écrite une fois
            self.assertGreater(len(proof.watermark_prims(info, BOX)), 3)        # pour tous les motifs

    def test_big_image_logo_reduced(self):
        png = self.tmp / 'grand.png'
        img = QImage(2400, 1200, QImage.Format.Format_RGB32)
        img.fill(QColor('black'))
        img.save(str(png))
        one = proof.watermark_motif(info_with(watermark_kind='logo', watermark_logo=str(png)))
        q = qimage_of(one[0].image)
        self.assertEqual((q.width(), q.height()), (1000, 500))               # quelques cm : assez fin, léger

    def test_several_logos_kept(self):
        paths = []
        for k in range(3):
            p = self.tmp / f'l{k}.png'
            img = QImage(8, 8, QImage.Format.Format_RGB32)
            img.fill(QColor('black'))
            img.save(str(p))
            paths.append(str(p))
        got = [proof.logo_image(p) for p in paths]
        self.assertTrue(all(proof.logo_image(p) is g for p, g in zip(paths, got)))   # pas relus tour à tour

    def test_no_logo_falls_back_to_the_text(self):
        info = info_with(watermark_kind='logo', logo='', watermark_logo='')
        self.assertEqual(len(proof.watermark_motif(info)), 1)
        self.assertIsNone(proof.watermark_motif(info)[0].image)


class Dialog(unittest.TestCase):

    def test_fields_kept_and_enabled(self):
        from vectordrive.ui.batdialog import BatDialog
        d = Document()
        d.plate = Plate(width=80.0, height=50.0)
        dlg = BatDialog(None, d, info_with(watermark=False))
        try:
            self.assertFalse(dlg.watermark_size.isEnabled())
            dlg.watermark.setChecked(True)
            dlg.refresh()
            self.assertTrue(dlg.watermark_size.isEnabled())
            self.assertFalse(dlg.watermark_logo.isEnabled())                    # motif : le texte
            dlg.watermark_kind.setCurrentIndex(dlg.watermark_kind.findData('logo'))
            dlg.watermark_layout.setCurrentIndex(dlg.watermark_layout.findData('centre'))
            dlg.watermark_size.setValue(15.0)
            dlg.watermark_angle.setValue(-20.0)
            dlg.watermark_strength.setValue(45)
            dlg.refresh()
            self.assertTrue(dlg.watermark_logo.isEnabled())
            self.assertTrue(dlg.watermark_text.isEnabled())                     # le motif si le logo manque
            self.assertFalse(dlg.watermark_gap.isEnabled())                     # un seul : pas d'écart
            i = dlg.result_info()
            self.assertEqual((i.watermark_kind, i.watermark_layout, i.watermark_size, i.watermark_angle,
                              i.watermark_strength, i.watermark_logo), ('logo', 'centre', 15.0, -20.0, 45, ''))
            dlg.load_layout({'watermark_kind': 'texte', 'watermark_gap': 25.0, 'watermark_layout': 'trame'})
            i = dlg.result_info()
            self.assertEqual((i.watermark_kind, i.watermark_gap, i.watermark_layout), ('texte', 25.0, 'trame'))
        finally:
            dlg.close()


if __name__ == '__main__':
    unittest.main()
