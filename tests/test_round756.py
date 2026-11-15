"""Round 756 : remplir ou vider la sélection ; un import rempli se vide, et inversement."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import geom
from vectordrive.core.document import Group, Shape

app = QApplication.instance() or QApplication([])


def square(x=0.0, filled=False):
    return Shape(path=geom.Path([geom.rect(x, 0, 10, 10)]), filled=filled)


def open_line():
    return Shape(path=geom.Path([geom.polyline([(0, 0), (10, 10)], closed=False)]))


class TestToggleFill(unittest.TestCase):
    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()

    def tearDown(self):
        for t in self.w.docs:
            t.modified = False
        self.w.modified = False
        self.w.close()

    def put(self, *items):
        self.w.canvas.doc.layers[0].items.extend(items)
        self.w.canvas.selection = list(items)
        return items

    def test_nothing_selected(self):
        self.w.canvas.selection = []
        self.assertEqual(self.w.toggle_fill(), 0)
        self.assertIn('Sélectionnez', self.w.statusBar().currentMessage())

    def test_toggle(self):
        a, = self.put(square())
        self.assertEqual(self.w.toggle_fill(), 1)
        self.assertTrue(a.filled)
        self.assertEqual(self.w.toggle_fill(), 1)
        self.assertFalse(a.filled)

    def test_mixed_fills_then_empties(self):
        a, b = self.put(square(), square(20, True))
        self.assertEqual(self.w.toggle_fill(), 1)
        self.assertTrue(a.filled and b.filled)
        self.assertEqual(self.w.toggle_fill(), 2)
        self.assertFalse(a.filled or b.filled)

    def test_explicit(self):
        a, b = self.put(square(), square(20, True))
        self.assertEqual(self.w.toggle_fill(False), 1)
        self.assertFalse(b.filled)
        self.assertEqual(self.w.toggle_fill(False), 0)
        self.assertEqual(self.w.toggle_fill(True), 2)

    def test_inside_groups(self):
        a, b = square(), square(20)
        self.put(Group(children=[a, Group(children=[b])]))
        self.assertEqual(self.w.toggle_fill(), 2)
        self.assertTrue(a.filled and b.filled)

    def test_open_contours_not_filled(self):
        line, = self.put(open_line())
        self.assertEqual(self.w.toggle_fill(), 0)
        self.assertFalse(line.filled)
        self.assertIn('fermé', self.w.statusBar().currentMessage())

    def test_open_with_closed(self):
        line, sq = self.put(open_line(), square())
        self.assertEqual(self.w.toggle_fill(), 1)
        self.assertFalse(line.filled)
        self.assertTrue(sq.filled)

    def test_open_filled_can_be_emptied(self):
        line, = self.put(open_line())
        line.filled = True
        self.assertEqual(self.w.toggle_fill(False), 1)
        self.assertFalse(line.filled)

    def test_solid_untouched(self):
        s, = self.put(square())
        s.extra['solide'] = {}
        self.assertEqual(self.w.toggle_fill(), 0)
        self.assertFalse(s.filled)

    def test_undo(self):
        self.put(square())
        self.w.toggle_fill()
        doc = self.w.canvas.doc
        self.assertTrue(doc.layers[0].items[-1].filled)
        self.w.undo()
        self.assertFalse(self.w.canvas.doc.layers[0].items[-1].filled)

    def test_view_mode_told(self):
        self.put(square(0, True))
        self.w.canvas.show_fill = True
        self.w.toggle_fill()
        self.assertIn('Ctrl+9', self.w.statusBar().currentMessage())
        self.w.canvas.show_fill = False

    def test_saved(self):
        from vectordrive.io import native
        a, = self.put(square())
        self.w.toggle_fill()
        again = native.from_dict(native.to_dict(self.w.canvas.doc))
        self.assertTrue(again.layers[0].items[-1].filled)

    def test_on_the_ribbon(self):
        from PySide6.QtGui import QAction
        from vectordrive.ui.icons import icon
        found = [a for a in self.w.findChildren(QAction) if a.text() == 'Remplir / vider']
        self.assertTrue(found)
        self.assertFalse(icon('fill_toggle').isNull())
        self.w.canvas.selection = list(self.put(square()))
        found[0].trigger()                                                    # la commande branchée, pas seulement écrite
        self.assertTrue(self.w.canvas.selection[0].filled)


class TestPdfImport(unittest.TestCase):
    """Un PDF rempli : la forme importée porte bien le remplissage, donc se vide."""

    def test_filled_flag(self):
        from vectordrive.io import pdf
        content = b'1 0 0 rg 10 10 100 50 re f'
        objs = [b'<< /Type /Catalog /Pages 2 0 R >>', b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
                b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] /Contents 4 0 R >>',
                b'<< /Length %d >>\nstream\n%s\nendstream' % (len(content), content)]
        out = bytearray(b'%PDF-1.4\n')
        offs = []
        for i, o in enumerate(objs, 1):
            offs.append(len(out))
            out += b'%d 0 obj\n%s\nendobj\n' % (i, o)
        xref = len(out)
        out += b'xref\n0 %d\n0000000000 65535 f \n' % (len(objs) + 1)
        for off in offs:
            out += b'%010d 00000 n \n' % off
        out += b'trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n' % (len(objs) + 1, xref)
        path = os.path.join(tempfile.mkdtemp(), 't.pdf')
        with open(path, 'wb') as f:
            f.write(out)
        doc = pdf.read(path)
        shapes = [x for L in doc.layers for x in L.items if isinstance(x, Shape)]
        self.assertTrue(shapes and all(s.filled for s in shapes))


if __name__ == '__main__':
    unittest.main()
