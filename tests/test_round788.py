"""Round 788 : permutation des plans d'un volume."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

import numpy as np

from vectordrive.core import solids as SO


def rb(b):
    return [round(float(v), 4) for v in b]


@unittest.skipUnless(SO.available(), 'volumes indisponibles')
class TestMatrix(unittest.TestCase):
    def test_axes_turn(self):
        s = SO.box(10, 20, 5, 30, 40, 10)                # 30 × 40 × 10
        got = s.transformed(SO.permutation(s.bounds())).bounds()
        # X prend l'ancien Z (10), Y l'ancien X (30), Z l'ancien Y (40)
        self.assertAlmostEqual(got[3] - got[0], 10)
        self.assertAlmostEqual(got[4] - got[1], 30)
        self.assertAlmostEqual(got[5] - got[2], 40)

    def test_stays_on_the_spot(self):
        s = SO.box(10, 20, 5, 30, 40, 10)
        got = s.transformed(SO.permutation(s.bounds())).bounds()
        self.assertAlmostEqual((got[0] + got[3]) / 2, 25)
        self.assertAlmostEqual((got[1] + got[4]) / 2, 40)
        self.assertAlmostEqual(got[2], 5)                # même dessous

    def test_three_times_gives_the_original(self):
        s = SO.box(10, 20, 5, 30, 40, 10)
        t = s
        for _ in range(3):
            t = t.transformed(SO.permutation(t.bounds()))
        self.assertEqual(rb(t.bounds()), rb(s.bounds()))
        self.assertAlmostEqual(t.volume(), s.volume(), places=4)

    def test_is_a_real_rotation(self):
        m = SO.permutation((0, 0, 0, 1, 1, 1))
        self.assertAlmostEqual(float(np.linalg.det(m[:3, :3])), 1.0)     # pas de pièce retournée en miroir

    def test_volume_kept_and_not_inside_out(self):
        s = SO.box(0, 0, 0, 30, 20, 10)
        got = s.transformed(SO.permutation(s.bounds()))
        self.assertAlmostEqual(got.volume(), 6000.0, places=3)

    def test_shift(self):
        s = SO.box(0, 0, 0, 30, 20, 10)
        a = s.transformed(SO.permutation(s.bounds())).bounds()
        b = s.transformed(SO.permutation(s.bounds(), 7.0)).bounds()
        self.assertAlmostEqual(b[0] - a[0], 7.0)
        self.assertAlmostEqual(b[1], a[1])


@unittest.skipUnless(SO.available(), 'volumes indisponibles')
class TestWindow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = mock.patch.dict(os.environ, {
            'VECTORDRIVE_SETTINGS': self.tmp.name + '/r.ini', 'VECTORDRIVE_SESSION': self.tmp.name + '/session',
            'VECTORDRIVE_CACHE': self.tmp.name + '/cache'})
        self.env.start()
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.item = SO.make_shape(SO.box(0, 0, 0, 30, 20, 10))
        self.w.canvas.doc.add(self.item)
        self.w.canvas.select([self.item])

    def tearDown(self):
        self.w.canvas.doc.modified = False
        self.w.close()
        self.w.deleteLater()
        self.env.stop()
        self.tmp.cleanup()

    def items(self):
        return list(self.w.canvas.doc.iter_items())

    def test_action_and_te_links(self):
        from vectordrive.ui.shortcuts import TE_ACTIONS
        self.assertIn('solid_permute', self.w.A)
        self.assertEqual(TE_ACTIONS['ID_COMPO_FLIPPLAN'], 'solid_permute')
        self.assertEqual(TE_ACTIONS['ID_ROTATION_OBJET3D'], 'solid_rotate3d')

    def test_action_found_in_the_ribbon(self):
        found = False
        for i in range(self.w.ribbon.count()):
            for g in self.w.ribbon.page(i).groups():
                found = found or any(b.defaultAction() is self.w.A['solid_permute'] for b in g.buttons())
        self.assertTrue(found)

    def test_permute_in_place_same_object_with_undo(self):
        new = self.w.solid_permute(keep=False)
        self.assertEqual(len(new), 1)
        self.assertEqual(new[0].id, self.item.id)
        b = SO.of_item(new[0]).bounds()
        self.assertAlmostEqual(b[3] - b[0], 10, places=4)
        self.assertAlmostEqual(b[5] - b[2], 20, places=4)
        self.assertEqual(len(self.items()), 1)
        self.w.undo()
        b = SO.of_item(self.items()[0]).bounds()
        self.assertAlmostEqual(b[3] - b[0], 30, places=4)

    def test_three_clicks_come_back(self):
        for _ in range(3):
            self.w.solid_permute(keep=False)
            self.w.canvas.select(self.items())
        b = SO.of_item(self.items()[0]).bounds()
        self.assertEqual(rb(b), rb((0, 0, 0, 30, 20, 10)))

    def test_keep_puts_the_result_beside(self):
        new = self.w.solid_permute(keep=True)
        self.assertEqual(len(new), 2)
        self.assertEqual(len(self.items()), 2)
        original = SO.of_item(new[0]).bounds()
        result = SO.of_item(new[1]).bounds()
        self.assertEqual(rb(original), rb((0, 0, 0, 30, 20, 10)))
        self.assertGreater(result[0], original[3])       # à côté, sans le toucher
        self.assertAlmostEqual(result[0] - original[3], 5.0, places=4)

    def test_shift_key_keeps_the_original(self):
        from PySide6.QtCore import Qt
        with mock.patch('PySide6.QtWidgets.QApplication.keyboardModifiers', return_value=Qt.KeyboardModifier.ShiftModifier):
            self.assertEqual(len(self.w.solid_permute()), 2)

    def test_without_shift_replaces(self):
        from PySide6.QtCore import Qt
        with mock.patch('PySide6.QtWidgets.QApplication.keyboardModifiers', return_value=Qt.KeyboardModifier.NoModifier):
            self.assertEqual(len(self.w.solid_permute()), 1)

    def test_nothing_selected_does_nothing(self):
        self.w.canvas.select([])
        self.assertEqual(self.w.solid_permute(keep=False), [])
        self.assertEqual(len(self.items()), 1)


if __name__ == '__main__':
    unittest.main()
