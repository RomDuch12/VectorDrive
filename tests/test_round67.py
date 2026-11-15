"""Round 67 : marqueur, cadre englobant."""
import math
import os
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from vectordrive.core import geom
from vectordrive.core.document import Shape
from vectordrive.core.geom import Path


class TestMarker(unittest.TestCase):
    def test_geometry(self):
        cs = geom.marker((5, 5), 4)
        self.assertEqual(len(cs), 3)
        self.assertEqual((cs[0].start, cs[0].end), ((3, 5), (7, 5)))
        self.assertEqual((cs[1].start, cs[1].end), ((5, 3), (5, 7)))
        for q in cs[2].flatten(1e-4):
            self.assertAlmostEqual(math.hypot(q[0] - 5, q[1] - 5), 1.2, places=9)
        self.assertEqual(len(geom.marker((0, 0), 2, circle=False)), 2)


class _Ev:
    def modifiers(self):
        from PySide6.QtCore import Qt
        return Qt.KeyboardModifier.NoModifier


class TestWindow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_marker_tool_stays_active(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            w.marker_size.setValue(6)
            w.set_tool('marker')
            for p in ((0, 0), (20, 0)):
                w.canvas.tool_obj.press(w.canvas.to_screen(*p), p, _Ev())
            items = list(w.canvas.doc.iter_items())
            self.assertEqual(len(items), 2)
            self.assertEqual(tuple(round(v, 9) for v in items[1].bbox()), (17, -3, 23, 3))
            self.assertEqual(w.canvas.tool, 'marker')
        finally:
            w.modified = False
            w.close()

    def test_bbox_frame(self):
        from dataclasses import dataclass
        from vectordrive.ui import dialogs
        from vectordrive.ui.main_window import MainWindow

        @dataclass
        class Spec:
            margin: float = 2.0
            radius: float = 1.0
            shape: str = 'rect'

        class Fake:
            spec = Spec()

            def __init__(self, *a, **k):
                pass

            def exec(self):
                return True

            def result_params(self):
                return Fake.spec
        old = dialogs.ParamsDialog
        dialogs.ParamsDialog = Fake
        w = MainWindow()
        try:
            sq = Shape(path=Path([geom.rect(0, 0, 10, 4)]))
            w._add_items([sq])
            w.canvas.select([sq])
            w.bbox_frame()
            frame = w.canvas.selection[0]
            self.assertEqual(tuple(round(v, 9) for v in frame.bbox()), (-2, -2, 12, 6))
            self.assertAlmostEqual(frame.path.length(), 2 * (14 + 8) - 8 + 2 * math.pi, places=9)
            Fake.spec = Spec(margin=0, shape='ellipse')
            w.canvas.select([sq])
            w.bbox_frame()
            e = w.canvas.selection[0]
            for corner in ((0, 0), (10, 4)):                          # l'ellipse passe par les coins
                a, b = 5 * math.sqrt(2), 2 * math.sqrt(2)
                self.assertAlmostEqual(((corner[0] - 5) / a) ** 2 + ((corner[1] - 2) / b) ** 2, 1, places=9)
            self.assertAlmostEqual(e.bbox()[2], 5 + 5 * math.sqrt(2), places=6)
        finally:
            dialogs.ParamsDialog = old
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
