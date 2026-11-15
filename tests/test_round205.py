"""Round 205 : reproduire la mise en forme des textes."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import fonts, text as TX
from vectordrive.core.document import Text
from vectordrive.core.geom import Affine

FONT = 'Arial'


def model_text():
    t = Text(text='Modèle', font=FONT, size=7.5, align='center', spacing=0.4, width_ratio=0.8)
    t.extra.update(italic=12.0, small_caps=True, max_length={'length': 40.0, 'by': 'line'})
    return t


@unittest.skipUnless(fonts.find_font(FONT), 'police Arial absente')
class TestFormat(unittest.TestCase):
    def test_apply_keeps_content_and_place(self):
        src = model_text()
        dst = Text(text='Autre texte', font=FONT, size=3.0, matrix=Affine(1, 0, 0, 1, 20, 30))
        dst.extra['underline'] = True
        self.assertTrue(TX.apply_format(dst, TX.text_format(src)))
        self.assertEqual((dst.text, dst.matrix.e, dst.matrix.f), ('Autre texte', 20, 30))
        self.assertEqual((dst.size, dst.align, dst.width_ratio), (7.5, 'center', 0.8))
        self.assertEqual(dst.extra['italic'], 12.0)
        self.assertNotIn('underline', dst.extra)                                  # styles du modèle seulement
        self.assertIsNotNone(dst.outline)
        self.assertFalse(TX.apply_format(dst, TX.text_format(src)))               # déjà identique
        src.extra['max_length']['length'] = 10.0
        self.assertEqual(dst.extra['max_length']['length'], 40.0)                  # copie, pas un partage

    def test_box_text_keeps_its_height(self):
        boxed = Text(text='Cadre', font=FONT, size=2.0)
        boxed.extra['box'] = {'x0': 0, 'y0': 0, 'x1': 20, 'y1': 5}
        TX.apply_format(boxed, TX.text_format(model_text()))
        self.assertNotEqual(boxed.size, 7.5)


@unittest.skipUnless(fonts.find_font(FONT), 'police Arial absente')
class TestUi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_two_ways(self):
        from vectordrive.ui.main_window import MainWindow
        from vectordrive.ui.shortcuts import TE_ACTIONS
        self.assertEqual(TE_ACTIONS['ID_RAPIDO_TEXT_REPRODMISEENFORME_DLL'], 'text_copy_format')
        w = MainWindow()
        try:
            src, a, b = model_text(), Text(text='A', font=FONT, size=3.0), Text(text='B', font=FONT, size=3.0)
            for t in (src, a, b):
                t.outline = TX.outline_for(t)
                w.canvas.doc.add(t)
            w.canvas.selection = [src, a]
            self.assertEqual(w.copy_text_format(), 1)
            self.assertEqual(a.size, 7.5)
            w.canvas.selection = [src]
            self.assertEqual(w.copy_text_format(), 0)                                  # pinceau chargé
            w.canvas.selection = [b]
            w._on_selection()
            self.assertEqual(b.size, 7.5)
            self.assertIsNone(w._format_brush)                                         # une seule fois
            w.undo()
            self.assertTrue(any(isinstance(t, Text) and t.text == 'B' and t.size == 3.0
                                for t in w.canvas.doc.iter_leaves()))
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
