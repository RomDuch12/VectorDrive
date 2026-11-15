"""Round 58 : tampon."""
import math
import os
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from vectordrive.core import geom, pathops
from vectordrive.core import stamp as S
from vectordrive.core.document import Shape, Text
from vectordrive.core.geom import Affine, Path


def square():
    return Shape(path=Path([geom.rect(0, 0, 10, 10)]))


class TestStamp(unittest.TestCase):
    def test_areas(self):
        sq = square().path
        self.assertAlmostEqual(pathops.area(S.region(sq, S.StampSpec(margin=2, radius=0, border=1))), 44, places=6)
        self.assertAlmostEqual(pathops.area(S.region(sq, S.StampSpec(margin=2, radius=0, border=1, negative=False))),
                               152, places=6)
        a = pathops.area(S.region(sq, S.StampSpec(margin=2, radius=0, border=1, shoulder=0.5)))
        self.assertAlmostEqual(a, 144 - (121 - (4 - math.pi) * 0.25), places=3)     # coins arrondis de l'épaulement
        a = pathops.area(S.region(sq, S.StampSpec(margin=3, radius=8, border=0)))
        self.assertAlmostEqual(a, math.pi * 64 - 100, places=6)                       # cadre devenu disque

    def test_mirror_and_parts(self):
        t = Text(text='F', font='Arial', size=10)
        g = S.build([t], S.StampSpec(margin=1, border=0.5, hatch=0.5))
        names = [c.name for c in g.children]
        self.assertEqual(names, ['Objets', 'Zone à graver', 'Découpe', 'Hachures'])
        src, zone, cut = (c.path for c in g.children[:3])
        self.assertFalse(g.children[0].visible)
        x0, _, x1, _ = cut.bbox()
        m = Affine.mirror_y((x0 + x1) / 2)
        # le F retourné : la zone à graver ne recouvre pas l'image miroir des lettres
        inter = pathops.boolean(zone, src.transformed(m), 'intersect')
        self.assertLess(pathops.area(inter), 1e-6)
        self.assertGreater(pathops.area(pathops.boolean(zone, src, 'intersect')), 1)  # non retourné : recouvre
        g2 = S.build([t], S.StampSpec(margin=1, border=0.5, mirror=False))
        self.assertEqual(len(g2.children), 3)

    def test_rebuild_follows_move(self):
        g = S.build([square()], S.StampSpec())
        g2 = S.rebuild(g.transformed(Affine.translation(30, 0)), S.StampSpec(margin=5))
        self.assertAlmostEqual(g2.children[2].path.bbox()[0], 25)


class TestWindow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_new_and_edit(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            w._add_items([square()])
            w._stamp_dialog = lambda spec: S.StampSpec(margin=3)
            w.new_stamp()
            g = w.canvas.selection[0]
            self.assertEqual(g.extra['stamp']['margin'], 3)
            w._stamp_dialog = lambda spec: S.StampSpec(margin=4, hatch=1)
            w._item_double_clicked(g)
            self.assertEqual(w.canvas.selection[0].extra['stamp']['margin'], 4)
            w.undo()
            gs = [it for it in w.canvas.doc.iter_items() if 'stamp' in it.extra]
            self.assertEqual([x.extra['stamp']['margin'] for x in gs], [3])
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
