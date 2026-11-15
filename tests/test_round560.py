"""Round 560 : copier-coller entre deux dessins (onglets) — les objets gardent leurs couleurs ; SVG collé
d'un autre logiciel : ses couleurs aussi."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import geom
from vectordrive.core.document import Document, Shape, Tool

app = QApplication.instance() or QApplication([])


class TestPasteColors(unittest.TestCase):
    def test_copy_between_documents(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            w.canvas.doc.tools = [Tool(0, '#000000'), Tool(2, '#ff0000')]
            s = Shape(path=geom.Path([geom.rect(0, 0, 5, 5)]), tool=2)
            w.canvas.doc.add(s)
            w.canvas.select([s])
            w.copy()
            other = Document()
            other.tools = [Tool(0, '#000000'), Tool(2, '#0000ff')]
            other.add(Shape(path=geom.Path([geom.rect(9, 9, 1, 1)]), tool=2))
            w.canvas.doc = other                                             # un autre dessin (onglet)
            w.paste()
            pasted = w.canvas.selection[0]
            self.assertEqual(other.tool_color(pasted.tool), '#ff0000')        # rouge gardé
            self.assertEqual(other.tool_color(2), '#0000ff')                  # le bleu du dessin aussi
        finally:
            w.modified = False
            w.close()

    def test_paste_svg_colors(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            w.paste_svg(b'<svg xmlns="http://www.w3.org/2000/svg" width="10mm" height="10mm" viewBox="0 0 10 10">'
                        b'<rect width="2" height="2" stroke="#00a000" fill="none"/></svg>')
            g = w.canvas.selection[0] if w.canvas.selection else list(w.canvas.doc.iter_items())[-1]
            leaf = g.children[0]
            self.assertEqual(w.canvas.doc.tool_color(leaf.tool), '#00a000')
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
