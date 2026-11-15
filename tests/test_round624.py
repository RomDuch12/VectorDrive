"""Round 624 : BAT de plusieurs gravures — leurs cotes unitaires, sans cotes
d'ensemble ; Maj+D distance rectangle (X, Y, XY) comme TypeEdit ; un
programme machine (.iso d'une Cielle, .nc…) ouvert d'un double-clic, glissé
ou depuis les récents s'ouvre dans le visualiseur au lieu d'un refus."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Document, Shape  # noqa: E402

CIELLE_ISO = """(INGOMBROFOGLIO:-13.625, 0.625, -8.625, 5.625)
(Programma generatore: essai)
T62 (Balayage - Profondeur 0.02mm)
S10000
G108 P100.000 I80000.00
G00X-8.625000Y0.625000
G00Z0.000000
F40000
G01X-13.625000Y0.625000
G00Z-0.001000
G00X-13.625000Y5.625000
G00Z0.000000
G01X-8.625000Y5.625000
"""


def doc_with(n):
    d = Document()
    d.plate = None
    for i in range(n):
        d.add(Shape(path=geom.Path([geom.rect(i * 30, 0, 20, 10)]), tool=0))
    return d


class TestProofDims(unittest.TestCase):
    def offsets(self, doc, **kw):
        from vectordrive.io import proof
        seen = []
        real = proof.geom.dimension

        def spy(a, b, off, **k):
            seen.append(off)
            return real(a, b, off, **k)
        proof.geom.dimension = spy
        try:
            proof.build(doc, proof.ProofInfo(**kw))
        finally:
            proof.geom.dimension = real
        return seen

    def test_several_engravings_unit_dims_only(self):
        seen = self.offsets(doc_with(2), dims=True, dims_each=True, title_block=False)
        self.assertEqual(seen.count(-7), 0)                                  # pas de cote d'ensemble
        self.assertEqual(seen.count(-3.5), 4)                                # largeur et hauteur de chacune

    def test_one_engraving_or_no_unit_dims_keeps_overall(self):
        self.assertEqual(self.offsets(doc_with(1), dims=True, dims_each=True, title_block=False,
                                      enlarge_below=0).count(-7), 2)                 # une vue
        seen = self.offsets(doc_with(2), dims=True, dims_each=False, title_block=False)
        self.assertEqual((seen.count(-7), seen.count(-3.5)), (2, 0))


class TestMeasureRect(unittest.TestCase):
    def test_text(self):
        from vectordrive.ui.tools import MeasureTool
        self.assertEqual(MeasureTool.describe_rect((1, 1), (4, -3)), 'X 3.000 mm   Y 4.000 mm   XY 5.000 mm')

    def test_shortcut_tool_and_paint(self):
        from PySide6.QtGui import QImage, QPainter
        from vectordrive.ui import shortcuts
        from vectordrive.ui.main_window import MainWindow
        from vectordrive.ui.tools import MeasureTool
        self.assertEqual(shortcuts.TE_ACTIONS['ID_PALETTE_MESUREDISTANCERECT'], 'tool_measure_rect')
        w = MainWindow()
        try:
            self.assertEqual(w.A['tool_measure_rect'].shortcut().toString(), 'Shift+D')
            w.set_tool('measure_rect')
            t = w.canvas.tool_obj
            self.assertIsInstance(t, MeasureTool)
            self.assertTrue(t.rect)
            got = []
            w.canvas.measured.connect(got.append)
            t.press(None, (0.0, 0.0), None)
            t.move(None, (30.0, 40.0), None)
            self.assertEqual(got[-1], 'X 30.000 mm   Y 40.000 mm   XY 50.000 mm')
            img = QImage(400, 300, QImage.Format.Format_ARGB32)
            p = QPainter(img)
            t.paint(p)                                                       # rectangle, côtés, diagonale
            p.end()
            w.set_tool('measure')
            self.assertFalse(w.canvas.tool_obj.rect)                         # Mesurer : inchangé
        finally:
            w.modified = False
            w.close()


class TestOpenProgram(unittest.TestCase):
    def test_iso_opens_in_viewer(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            p = pathlib.Path(tempfile.mkdtemp()) / 'Coupon_Z0001.ISO'
            p.write_text(CIELLE_ISO, encoding='ascii')
            self.assertTrue(w._program_only(p))
            self.assertFalse(w._program_only(pathlib.Path(p).with_suffix('.dxf')))
            tabs = len(w.docs)
            self.assertTrue(w.open_path(str(p)))                             # plus de « format non pris en charge »
            self.assertEqual(len(w.docs), tabs)                              # pas d'onglet de dessin
            self.assertEqual(w.view_mode(), '3d')
            tp = w.cam_panel.toolpaths[0]
            self.assertEqual(round(min(m.x for m in tp.moves), 3), -13.625)
            self.assertEqual(w.open_paths([str(p), str(p)]), 2)              # plusieurs : sans lecture de dessin
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
