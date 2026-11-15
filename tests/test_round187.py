"""Round 187 : textes justifiés, petites majuscules, sur / sous la ligne de base."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import fonts, text as TX
from vectordrive.core.document import Text

FONT = 'Arial'


@unittest.skipUnless(fonts.find_font(FONT), 'police Arial absente')
class TestLayout(unittest.TestCase):
    def test_plain_unchanged(self):
        a = TX._placed('Abc\nDéfg', FONT, 5.0, 'center', 0.2, 1.2, 0.9, True)
        b = TX._placed('Abc\nDéfg', FONT, 5.0, 'center', 0.2, 1.2, 0.9, True, False, False)
        self.assertEqual([m.to_tuple() for _g, m in a], [m.to_tuple() for _g, m in b])

    def test_justify(self):
        txt = 'IIIIIIIIIIII\nII II'
        placed = TX._placed(txt, FONT, 5.0, 'justify', 0.0, 1.2, 1.0, True)
        ys = sorted({round(m.f, 6) for _g, m in placed}, reverse=True)
        second = [m for _g, m in placed if round(m.f, 6) == ys[1]]
        first = [m for _g, m in placed if round(m.f, 6) == ys[0]]
        self.assertAlmostEqual(first[0].e, second[0].e)                          # même départ
        w1 = TX.layout(txt.split('\n')[0], FONT, 5.0).bbox()
        p = TX.layout(txt, FONT, 5.0, align='justify')
        lo = [c.bbox() for c in p.contours if c.bbox()[1] < -1.0]                # seconde ligne
        self.assertAlmostEqual(max(b[2] for b in lo), w1[2], delta=0.05)         # même largeur que la 1re
        one = TX.layout('Seul', FONT, 5.0, align='justify').bbox()
        self.assertEqual(one, TX.layout('Seul', FONT, 5.0).bbox())               # une ligne : inchangée

    def test_small_caps(self):
        full = TX.layout('AB', FONT, 10.0).bbox()
        sc = TX.layout('Ab', FONT, 10.0, small_caps=True)
        a_right = TX.layout('A', FONT, 10.0).bbox()[2]
        tops_a = [c.bbox()[3] for c in sc.contours if c.bbox()[2] <= a_right + 1e-9]
        tops_b = [c.bbox()[3] for c in sc.contours if c.bbox()[0] > a_right - 1e-9]
        self.assertAlmostEqual(max(tops_a), full[3], delta=0.05)                 # A : pleine hauteur
        self.assertAlmostEqual(max(tops_b), full[3] * TX.SMALL_CAPS, delta=0.08)  # b : capitale réduite
        self.assertLess(sc.bbox()[2], full[2])
        self.assertEqual(TX.layout('12-AB', FONT, 10.0, small_caps=True).bbox(),
                         TX.layout('12-AB', FONT, 10.0).bbox())                  # rien à réduire

    def test_baseline_and_vnd_styled(self):
        from vectordrive.io.vnd_write import styled
        t = Text(text='HE', font=FONT, size=8.0)
        t.outline = TX.outline_for(t)
        top = t.outline.bbox()[3]
        self.assertFalse(styled(t))
        t.extra['baseline'] = {'side': 'under', 'offset': 25.0}
        b = TX.outline_for(t).bbox()
        self.assertAlmostEqual(b[3], top - 8.0 - 2.0, delta=1e-6)               # haut 2 mm sous la ligne
        self.assertTrue(styled(t))
        for k, v in (('italic', 12.0), ('underline', True), ('small_caps', True), ('arc_warp', {'radius': 9}),
                     ('spacing_mode', 'fixed')):
            u = Text(text='HE', font=FONT, size=8.0)
            u.extra[k] = v
            self.assertTrue(styled(u), k)
        u = Text(text='HE', font=FONT, size=8.0, align='justify')
        self.assertTrue(styled(u))


@unittest.skipUnless(fonts.find_font(FONT), 'police Arial absente')
class TestUi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_actions(self):
        from vectordrive.core.geom import Affine
        from vectordrive.ui.main_window import MainWindow
        from vectordrive.ui.shortcuts import TE_ACTIONS
        for tid, key in (('ID_RAPIDO_LINE_BTNJUSTIF_DLL', 'text_align_justify'),
                         ('ID_RAPIDO_CHAR_PBSMAJ_DLL', 'case_small'),
                         ('ID_RAPIDO_LINE_BTNONLB_DLL', 'text_on_baseline'),
                         ('ID_RAPIDO_LINE_BTNUNDERLB_DLL', 'text_under_baseline')):
            self.assertEqual(TE_ACTIONS[tid], key)
        w = MainWindow()
        try:
            t = Text(text='Ab\nCdef', font=FONT, size=5.0, matrix=Affine(1, 0, 0, 1, 10, 50))
            t.outline = TX.outline_for(t)
            w.canvas.doc.add(t)
            w.canvas.selection = [t]
            w._on_selection()
            self.assertEqual(w.set_text_align('justify'), 1)
            self.assertEqual(t.align, 'justify')
            w.toggle_text_style('small_caps')
            self.assertTrue(t.extra['small_caps'])
            w.set_text_baseline('under')
            self.assertEqual(t.extra['baseline']['side'], 'under')
            w.set_text_baseline('on')
            self.assertNotIn('baseline', t.extra)
            w.undo()
            self.assertEqual(w.canvas.doc.iter_leaves().__next__().extra['baseline']['side'], 'under')
        finally:
            w.modified = False
            w.close()

    def test_dialog_combo(self):
        from vectordrive.ui.dialogs import TextDialog
        d = TextDialog(None, text='x', align='justify')
        self.assertEqual(d.align.currentData(), 'justify')


if __name__ == '__main__':
    unittest.main()
