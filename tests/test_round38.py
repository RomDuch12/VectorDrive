"""Round 38 : textes TypeEdit modifiables sur place, changement de
police en lot, dossiers de polices supplémentaires."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from vectordrive.core import fonts
from vectordrive.core import text as TX
from vectordrive.core.document import Text
from vectordrive.core.geom import Affine
from tests.corpus import corpus

SYMBOLS = corpus('symboles_perso')


def symbol_texts(key):
    from vectordrive.io import smb
    f = corpus(key)
    if not f.exists():
        raise unittest.SkipTest(f'{key} absent')
    return [t for t in smb.read(f).iter_leaves() if isinstance(t, Text)]


class TestTypeEditTextRelayout(unittest.TestCase):
    def test_edit_keeps_place(self):
        for t in symbol_texts('smb_textes'):
            with self.subTest(t.text):
                a, b = t.outline.bbox(), TX.outline_for(t).bbox()
                self.assertLess(max(abs(x - y) for x, y in zip(a, b)), 0.01 * t.size)

    def test_width_ratio_and_spacing(self):
        for t in symbol_texts('smb_textes_2'):
            if t.text.startswith('OT0550'):
                self.assertAlmostEqual(t.width_ratio, 0.72, places=3)
                a, b = t.outline.bbox(), TX.outline_for(t).bbox()
                self.assertLess(max(abs(x - y) for x, y in zip(a, b)), 0.01 * t.size)
                return
        self.skipTest('texte OT0550 absent')

    def test_rotated_text(self):
        from vectordrive.io import smb
        for f in list(SYMBOLS.rglob('*.smb'))[:400] if SYMBOLS.exists() else []:
            d = f.read_bytes()
            if b'CParagraphe' not in d:
                continue
            try:
                doc = smb.read(f)
            except Exception:
                continue
            for t in doc.iter_leaves():
                if isinstance(t, Text) and abs(t.matrix.b) > 0.5 and t.outline and '\n' not in t.text:
                    a, b = t.outline.bbox(), TX.outline_for(t).bbox()
                    self.assertLess(max(abs(x - y) for x, y in zip(a, b)), 0.02 * t.size)
                    return
        self.skipTest('pas de texte tourné')


class TestWindow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()

    def tearDown(self):
        self.w.modified = False
        self.w.close()

    def test_replace_font(self):
        w = self.w
        t = Text(text='Gravure', font='Arial', size=5, matrix=Affine.translation(20, 30))
        t.outline = TX.outline_for(t)
        w._add_items([t])
        target = 'Times New Roman'
        before = t.outline.bbox()
        self.assertEqual(w.replace_font([t], target), 1)
        self.assertEqual(t.font, target)
        after = t.outline.bbox()
        self.assertNotEqual(before, after)
        self.assertAlmostEqual(after[1], before[1], delta=2.5)            # même ligne de base, à peu près
        self.assertAlmostEqual(after[0], before[0], delta=1.0)
        w.undo()
        self.assertEqual(next(x for x in w.canvas.doc.iter_leaves()).font, 'Arial')

    def test_font_dirs_option(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.w.settings.setValue('polices/dossiers', tmp + ';C:/nexistepas')
            self.w.apply_options()
            self.assertIn(pathlib.Path(tmp), fonts.FONT_DIRS)
            fonts.FONT_DIRS.remove(pathlib.Path(tmp))
            fonts.families.cache_clear()


if __name__ == '__main__':
    unittest.main()
