"""Round 34 : largeur des outils (aperçu de gravure), sélection des
objets semblables."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from vectordrive.core import check as CK
from vectordrive.core import geom
from vectordrive.core.document import Document, Shape, Tool
from vectordrive.core.geom import Path
from vectordrive.io import raster, registry


def rect(x, y, w, h, tool=0):
    return Shape(path=Path([geom.rect(x, y, w, h)]), tool=tool)


class TestToolWidth(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_saved_in_vdz(self):
        d = Document()
        d.tools[1].width = 0.8
        d.add(rect(0, 0, 5, 5, tool=1))
        with tempfile.TemporaryDirectory() as tmp:
            f = pathlib.Path(tmp) / 'w.vdz'
            registry.save_document(d, f)
            back = registry.open_document(f)
        self.assertEqual(back.tool_width(1), 0.8)
        self.assertEqual(back.tool_width(0), 0.0)
        self.assertEqual(Tool(0, '#000').width, 0.0)

    def test_check_contour_smaller_than_tool(self):
        d = Document()
        d.tools[0].width = 1.0
        d.add(rect(0, 0, 0.6, 3))                         # plus étroit que l'outil
        d.add(rect(10, 0, 5, 5))
        issues = {i.code: i for i in CK.check(d)}
        self.assertEqual(issues['trop_petit'].count, 1)
        d.tools[0].width = 0.0
        self.assertNotIn('trop_petit', {i.code for i in CK.check(d)})

    def test_raster_uses_tool_width(self):
        d = Document()
        d.tools[0].width = 1.0
        from vectordrive.core.geom import Contour, Line
        d.add(Shape(path=Path([Contour([Line((0, 0), (10, 0))], False)])))
        img = raster.render(d, raster.RasterSpec(dpi=254, margin=2, include_plate=False))
        # trait horizontal de 1 mm = 10 px de haut au milieu de l'image
        col = [img.pixelColor(70, y).name() != '#ffffff' for y in range(img.height())]
        self.assertTrue(9 <= sum(col) <= 12, sum(col))


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

    def test_select_similar(self):
        w = self.w
        a, b, c, d = rect(0, 0, 5, 5, 0), rect(10, 0, 5, 5, 1), rect(20, 0, 5, 5.005, 0), rect(30, 0, 8, 5, 0)
        w._add_items([a, b, c, d])
        w.canvas.select([a])
        self.assertEqual({id(x) for x in w.select_similar('tool')}, {id(a), id(c), id(d)})
        w.canvas.select([a])
        self.assertEqual({id(x) for x in w.select_similar('shape')}, {id(a), id(b), id(c)})

    def test_engrave_preview_paints(self):
        w = self.w
        w.canvas.doc.tools[0].width = 0.5
        w._add_items([rect(0, 0, 5, 5)])
        w.A['engrave_preview'].setChecked(True)
        self.assertTrue(w.canvas.engrave_preview)
        w.canvas.grab()

    def test_tools_dialog_width_column(self):
        from vectordrive.ui.layers import ToolsDialog
        tools = [Tool(0, '#000000', 'Fraise', 0.3)]
        dlg = ToolsDialog(tools)
        dlg.table.item(0, 3).setText('0,45')
        self.assertEqual(dlg.tools()[0].width, 0.45)


if __name__ == '__main__':
    unittest.main()
