"""Round 634 : BAT — coloriage « logo en noir » (tous les contours fermés en
pair-impair : pleins et vides alternés pour les contours imbriqués), couleur
du cartouche au choix ; clic droit sur un onglet : « Ouvrir le dossier
contenant » (dessin, programme ouvert, fichier importé)."""
import os
import pathlib
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtGui import QImage, QPainter, QTransform
from PySide6.QtWidgets import QApplication

from vectordrive.core import geom
from vectordrive.core.document import Document, Shape
from vectordrive.io import proof

app = QApplication.instance() or QApplication([])


def logo_doc():
    """Trois carrés imbriqués (plein, vide, plein) et un trait ouvert."""
    d = Document()
    d.plate = None
    for k, s in enumerate((60, 40, 20)):
        d.add(Shape(path=geom.Path([geom.rect(-s / 2, -s / 2, s, s)]), tool=k % 2))
    d.add(Shape(path=geom.Path([geom.polyline([(-40, -40), (40, -40)])]), tool=1))
    return d


def info(**kw):
    kw.setdefault('title_block', False)
    kw.setdefault('dims', False)
    kw.setdefault('legend', False)
    return proof.ProofInfo(fill=True, **kw)


def raster(prims, PW, PH, k=2.0):
    img = QImage(int(PW * k), int(PH * k), QImage.Format.Format_RGB32)
    img.fill(0xFFFFFFFF)
    p = QPainter(img)
    from vectordrive.ui.printing import paint_prims
    paint_prims(p, prims, QTransform(k, 0, 0, -k, 0, PH * k))
    p.end()
    return img, k


class TestBlackLogo(unittest.TestCase):
    def test_one_even_odd_path(self):
        prims, PW, PH = proof.build(logo_doc(), info(fill_mode='noir'))
        filled = [pr for pr in prims if pr.fill and pr.color == (0, 0, 0)]  # (textes des cotes : en bleu)
        self.assertEqual(len(filled), 1)                                     # un seul chemin pair-impair
        self.assertEqual(len(filled[0].path.contours), 3)
        self.assertIsNone(filled[0].fill_color)
        self.assertFalse([pr for pr in prims if pr.fill_color is not None])  # pas de teinte
        opened = [pr for pr in prims if not pr.fill and pr.path.contours and not pr.path.contours[0].closed
                  and pr.color == (0, 0, 0) and abs(pr.width - 0.2) < 1e-9]
        self.assertEqual(len(opened), 1)                                     # le trait ouvert : noir

    def test_alternate_full_empty(self):
        prims, PW, PH = proof.build(logo_doc(), info(fill_mode='noir'))
        filled = [pr for pr in prims if pr.fill and pr.color == (0, 0, 0)][0]
        b = filled.path.bbox()
        cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
        s = (b[2] - b[0]) / 60.0                                             # échelle de la page
        img, k = raster(prims, PW, PH)

        def dark(x, y):
            c = img.pixelColor(int(x * k), int((PH - y) * k))
            return c.lightness() < 80
        self.assertTrue(dark(cx, cy))                                        # centre : plein
        self.assertFalse(dark(cx + 15 * s, cy))                              # 2e carré : vide
        self.assertTrue(dark(cx + 25 * s, cy))                               # anneau extérieur : plein
        self.assertFalse(dark(cx + 35 * s, cy))                              # dehors

    def test_tint_mode_unchanged(self):
        prims, PW, PH = proof.build(logo_doc(), info(fill_mode='teinte'))
        tinted = [pr for pr in prims if pr.fill and pr.fill_color is not None]
        self.assertEqual(len(tinted), 3)                                     # un objet, une teinte

    def test_pdf_even_odd(self):
        p = pathlib.Path(tempfile.mkdtemp()) / 'bat.pdf'
        captured = {}
        real = proof.pdf_bytes

        def spy(ops, *a, **kw):
            captured['ops'] = ops
            return real(ops, *a, **kw)
        with mock.patch.object(proof, 'pdf_bytes', spy):
            proof.write(logo_doc(), p, info(fill_mode='noir'))
        self.assertTrue(p.is_file())
        ops = captured['ops']
        self.assertIn('B*', ops)                                             # rempli (et bordé) en pair-impair
        self.assertFalse({'f', 'B', 'b'} & set(ops))                         # jamais la règle non nulle


class TestTitleColor(unittest.TestCase):
    def test_colored_title_block(self):
        prims, _w, _h = proof.build(logo_doc(), info(title_block=True, title_color='#b22222'))
        red = proof._rgb('#b22222')
        bg = [pr for pr in prims if pr.fill and pr.fill_color == proof.tint(red, 0.12)]
        self.assertEqual(len(bg), 1)                                         # fond clair du cartouche
        self.assertTrue(any(pr.color == red and pr.width == 0.5 for pr in prims))

    def test_black_default_and_mono(self):
        for kw in ({}, {'title_color': '#b22222', 'mono': True}):
            prims, _w, _h = proof.build(logo_doc(), info(title_block=True, **kw))
            red = proof._rgb('#b22222')
            self.assertFalse([pr for pr in prims if pr.color == red or pr.fill_color == proof.tint(red, 0.12)])

    def test_fields_and_options(self):
        self.assertIn('fill_mode', proof.LAYOUT_FIELDS)
        self.assertIn('title_color', proof.LAYOUT_FIELDS)
        from vectordrive.ui.options import BY_KEY, default_of
        self.assertEqual(default_of(BY_KEY['bat/fill_mode']), 'contour')
        self.assertEqual(default_of(BY_KEY['bat/title_color']), '')


class TestDialog(unittest.TestCase):
    def test_result_info(self):
        from vectordrive.ui.batdialog import BatDialog
        dlg = BatDialog(None, logo_doc(), proof.ProofInfo(client='BFM', fill=True, title_color='#123456'))
        try:
            self.assertEqual(dlg.result_info().title_color, '#123456')       # couleur choisie gardée
            dlg.fill_mode.setCurrentIndex(dlg.fill_mode.findData('teinte'))
            dlg.title_color.setCurrentIndex(dlg.title_color.findData('#2e7d32'))
            i = dlg.result_info()
            self.assertEqual((i.fill_mode, i.title_color), ('teinte', '#2e7d32'))
            dlg.checks['fill'].setChecked(False)
            dlg.refresh()
            self.assertFalse(dlg.fill_mode.isEnabled())
        finally:
            dlg.close()


class TestRevealTab(unittest.TestCase):
    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()

    def tearDown(self):
        for t in self.w.docs:
            t.modified = False
        self.w.modified = False
        self.w.close()

    def action(self):
        m = self.w.doc_tab_menu(self.w.doc_index, exec_menu=False)
        return next(a for a in m.actions() if a.text() == 'Ouvrir le dossier contenant')

    def test_menu_entry(self):
        w = self.w
        self.assertFalse(self.action().isEnabled())                          # dessin jamais enregistré
        f = pathlib.Path(tempfile.mkdtemp()) / 'prog.nc'
        f.write_text('G0 X0\n', encoding='utf-8')
        w.canvas.doc.source_path = str(f)                                    # programme ouvert en dessin
        a = self.action()
        self.assertTrue(a.isEnabled())
        with mock.patch('vectordrive.ui.reveal.reveal', return_value=True) as rv:
            a.trigger()
        rv.assert_called_once_with(str(f))

    def test_missing_file(self):
        with mock.patch('vectordrive.ui.reveal.reveal', return_value=False):
            self.assertFalse(self.w.reveal_file(''))
            self.assertFalse(self.w.reveal_file('Z:/nulle/part.nc'))
        self.assertIn('introuvable', self.w.statusBar().currentMessage())


if __name__ == '__main__':
    unittest.main()
