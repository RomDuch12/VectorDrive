"""Round 112 : texte vertical, tangentes à deux cercles et enveloppe,
alignements extérieurs, liste des annulations nommées."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import geom, shapes as SH
from vectordrive.core.document import Shape, Text


class TestTangents(unittest.TestCase):
    def test_external_and_internal(self):
        ext = SH.circle_tangents((0, 0), 2, (10, 0), 1, 'externes')
        self.assertEqual(len(ext), 2)
        for c in ext:
            a, b = c.start, c.end
            self.assertAlmostEqual(math.hypot(*a), 2, places=6)
            self.assertAlmostEqual(math.hypot(b[0] - 10, b[1]), 1, places=6)
            # perpendiculaire au rayon au point de contact
            d = (b[0] - a[0], b[1] - a[1])
            self.assertAlmostEqual(a[0] * d[0] + a[1] * d[1], 0, places=6)
        self.assertEqual(len(SH.circle_tangents((0, 0), 2, (10, 0), 1, 'toutes')), 4)
        self.assertEqual(SH.circle_tangents((0, 0), 5, (1, 0), 1), [])           # l'un dans l'autre
        self.assertEqual(len(SH.circle_tangents((0, 0), 2, (3, 0), 2, 'internes')), 0)   # sécants

    def test_belt(self):
        b = SH.belt((0, 0), 2, (10, 0), 2)
        self.assertTrue(b.closed)
        bb = b.bbox()
        self.assertAlmostEqual(bb[0], -2, places=3)
        self.assertAlmostEqual(bb[2], 12, places=3)
        self.assertAlmostEqual(bb[3] - bb[1], 4, places=3)
        self.assertAlmostEqual(b.signed_area(), 4 * 10 + math.pi * 4, delta=0.02)   # oblong, sens trigonométrique
        self.assertIsNone(SH.belt((0, 0), 5, (1, 0), 1))


class TestWindow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        QApplication.instance() or QApplication([])
        from vectordrive.ui.main_window import MainWindow
        cls.w = MainWindow()

    @classmethod
    def tearDownClass(cls):
        cls.w.modified = False
        cls.w.close()

    def setUp(self):
        self.w.modified = False
        self.w.new_document()
        self.w._undo.clear()
        self.w._redo.clear()

    def test_vertical_text(self):
        w = self.w
        t = Text(text='ABC', font='Arial', size=5)
        w.canvas.doc.layers[0].items.append(t)
        w.canvas.select([t])
        w.toggle_vertical_text()
        self.assertEqual(t.text, 'A\nB\nC')
        bb = t.bbox()
        self.assertGreater(bb[3] - bb[1], bb[2] - bb[0])
        w.toggle_vertical_text()
        self.assertEqual(t.text, 'ABC')
        self.assertNotIn('vertical', t.extra)

    def test_tangents_in_window(self):
        w = self.w
        a = Shape(path=geom.Path([geom.circle((0, 0), 3)]))
        b = Shape(path=geom.Path([geom.circle((20, 0), 1)]))
        w.canvas.doc.layers[0].items += [a, b]
        w.canvas.select([a, b])
        new = w.tangents('enveloppe')
        self.assertEqual(len(new), 1)
        self.assertTrue(new[0].path.contours[0].closed)
        w.canvas.select([a, b])
        self.assertEqual(len(w.tangents('externes')), 2)

    def test_align_outside(self):
        w = self.w
        ref = Shape(path=geom.Path([geom.rect(50, 50, 10, 10)]))
        o = Shape(path=geom.Path([geom.rect(0, 0, 4, 4)]))
        w.canvas.doc.layers[0].items += [ref, o]
        w.canvas.select([ref, o])
        w.align('left_out')
        moved = next(x for x in w.canvas.doc.layers[0].items if x.id == o.id)
        self.assertAlmostEqual(moved.bbox()[2], 50)
        w.canvas.select([ref, moved])
        w.align('top_out')
        moved = next(x for x in w.canvas.doc.layers[0].items if x.id == o.id)
        self.assertAlmostEqual(moved.bbox()[1], 60)
        self.assertEqual(next(x for x in w.canvas.doc.layers[0].items if x.id == ref.id).bbox()[0], 50)

    def test_named_undo_steps(self):
        w = self.w
        s = Shape(path=geom.Path([geom.rect(0, 0, 10, 10)]))
        w.canvas.doc.layers[0].items.append(s)
        w.canvas.select([s])
        w.A['mirror_h'].trigger()
        w.A['rot90'].trigger()
        labels = w.undo_labels()
        self.assertEqual(labels[0], w.A['rot90'].text())
        self.assertEqual(labels[1], w.A['mirror_h'].text())
        w.undo_steps(2)
        self.assertEqual(len(w._undo), 0)
        self.assertEqual(w.redo_labels()[0], w.A['mirror_h'].text())
        w.redo_steps(1)
        self.assertEqual(w.undo_labels()[0], w.A['mirror_h'].text())
        w.push_undo('Essai')
        self.assertEqual(w.undo_labels()[0], 'Essai')


if __name__ == '__main__':
    unittest.main()
