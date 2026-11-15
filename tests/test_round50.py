"""Round 50 : aperçu du texte dans la boîte Texte (vraie police)."""
import os
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')


def ink(pm):
    img = pm.toImage()
    bg = img.pixelColor(0, 0)
    return sum(1 for x in range(0, img.width(), 2) for y in range(0, img.height(), 2)
               if img.pixelColor(x, y) != bg)


class TestPreview(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_render(self):
        from vectordrive.ui.dialogs import render_text_preview
        self.assertGreater(ink(render_text_preview('Gravure', 'Arial')), 50)
        self.assertGreater(ink(render_text_preview('', 'Arial')), 50)          # texte vide : exemple

    def test_dialog_updates(self):
        from vectordrive.ui.dialogs import TextDialog
        d = TextDialog(None, text='A', font='Arial', height=5)
        a = ink(d.preview.pixmap())
        d.text.setPlainText('Beaucoup plus de texte ici')
        d.update_preview()
        self.assertNotEqual(ink(d.preview.pixmap()), a)


if __name__ == '__main__':
    unittest.main()
