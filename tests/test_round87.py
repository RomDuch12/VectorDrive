"""Round 87 : BAT réglable (format, orientation, échelle, éléments) avec aperçu."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from vectordrive.core import geom
from vectordrive.core.document import Document, Plate, Shape
from vectordrive.io import proof


def doc(w=40, h=12):
    d = Document()
    d.plate = Plate(width=w, height=h)
    d.layers[0].items.append(Shape(path=geom.Path([geom.rect(2, 2, w - 4, h - 4)])))
    return d


class TestLayout(unittest.TestCase):
    def test_scales(self):
        small = doc(40, 12)
        self.assertEqual(proof.page_scale(small, proof.ProofInfo()), 1)                   # taille réelle
        self.assertEqual(proof.page_scale(small, proof.ProofInfo(scale_mode='normalisee')), 5)   # 5:1
        k = proof.page_scale(small, proof.ProofInfo(scale_mode='ajuster'))
        self.assertGreater(k, 5)
        self.assertEqual(proof.page_scale(small, proof.ProofInfo(scale_mode='imposee', scale=2)), 2)
        big = doc(600, 300)
        self.assertEqual(proof.page_scale(big, proof.ProofInfo()), 1 / 2.5)               # réduction normalisée 1:2,5

    def test_fit_fills_area(self):
        d = doc(40, 12)
        g = proof._geometry(d, proof.ProofInfo(scale_mode='ajuster'))
        self.assertAlmostEqual(min(g['aw'] / (g['FW'] * g['k']), g['ah'] / (g['FH'] * g['k'])), 1, places=9)

    def test_page_and_orientation(self):
        _p, PW, PH = proof.build(doc(), proof.ProofInfo(page='A3', orientation='portrait'))
        self.assertEqual((PW, PH), (297.0, 420.0))
        _p, PW, PH = proof.build(doc(10, 50), proof.ProofInfo(page='A5'))
        self.assertEqual((PW, PH), (148.0, 210.0))                                       # dessin en hauteur

    def test_elements_and_mono(self):
        full, _, _ = proof.build(doc(), proof.ProofInfo())
        bare, _, _ = proof.build(doc(), proof.ProofInfo(title_block=False, dims=False, legend=False))
        self.assertLess(len(bare), len(full) / 3)
        mono, _, _ = proof.build(doc(), proof.ProofInfo(mono=True))
        self.assertTrue(all(abs(p.color[0] - p.color[1]) < 1e-9 and abs(p.color[1] - p.color[2]) < 1e-9
                            for p in mono))

    def test_labels_and_pdf(self):
        self.assertEqual([proof.scale_label(k) for k in (1, 5, 0.2)], ['1:1', '5:1', '1:5'])
        with tempfile.TemporaryDirectory() as tmp:
            f = os.path.join(tmp, 'bat.pdf')
            proof.write(doc(), f, proof.ProofInfo(page='A3', scale_mode='ajuster'))
            with open(f, 'rb') as fh:
                data = fh.read()
            self.assertIn(b'/MediaBox [0 0 1190.5512 841.8898]', data)                   # A3 paysage (1/10 000 pt)


class TestDialog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_dialog_roundtrip_and_settings(self):
        from vectordrive.ui.batdialog import BatDialog
        from vectordrive.ui.main_window import MainWindow
        dlg = BatDialog(None, doc(), proof.ProofInfo(client='BFM'))
        dlg.mode.setCurrentIndex(dlg.mode.findData('ajuster'))
        dlg.page.setCurrentIndex(dlg.page.findData('A3'))
        dlg.checks['legend'].setChecked(False)
        dlg.refresh()
        info = dlg.result_info()
        self.assertEqual((info.client, info.scale_mode, info.page, info.legend), ('BFM', 'ajuster', 'A3', False))
        self.assertIn(':1', dlg.scale_info.text())
        self.assertFalse(dlg.preview.pixmap().isNull())
        w = MainWindow()
        try:
            import vectordrive.ui.batdialog as bd
            old = bd.BatDialog.exec
            bd.BatDialog.exec = lambda self: True
            try:
                first = w._proof_info()
                first.page, first.mono, first.margin = 'A5', True, 4.5
                for k in ('page', 'mono', 'margin'):
                    w.settings.setValue(f'bat/{k}', getattr(first, k))
                again = w._proof_info()
            finally:
                bd.BatDialog.exec = old
            self.assertEqual((again.page, again.mono, again.margin), ('A5', True, 4.5))
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
