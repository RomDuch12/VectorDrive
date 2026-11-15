"""Round 700 : Pointillés — les traits deviennent de vrais tirets d'un type
de trait (types standard d'après CADCraft, fichiers .lin, motif à soi),
courbes coupées exactement, motif ajusté aux contours fermés, points en
petits cercles."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.core import geom
from vectordrive.core import linetypes as LT


def length(c):
    return sum(s.length() for s in c.segments)


class TestPatterns(unittest.TestCase):
    def test_standard_library(self):
        lib = {t.name: t for t in LT.standard()}
        self.assertEqual(len(lib), 17)
        self.assertEqual(lib['DASHED'].pattern, [12.7, -6.35])              # pouces × 25,4
        self.assertEqual(lib['DOT'].pattern, [0.0, -6.35])

    def test_parse_pattern(self):
        self.assertEqual(LT.parse_pattern('5, -2.5, 0, -2.5'), [5.0, -2.5, 0.0, -2.5])
        self.assertEqual(LT.parse_pattern('5,-2.5'), [5.0, -2.5])
        self.assertEqual(LT.parse_pattern('5 -2,5'), [5.0, -2.5])            # virgule décimale
        self.assertEqual(LT.parse_pattern('0,5 ; -0,25'), [0.5, -0.25])
        for bad in ('', '-1, -2', 'abc', '0, 0', 'nan, -1'):
            with self.assertRaises(ValueError):
                LT.parse_pattern(bad)
        self.assertEqual(LT.format_pattern([12.7, -6.35, 0.0]), '12.7, -6.35, 0')

    def test_ranges(self):
        rs = LT.ranges(3.0, [0.5, -0.25])
        self.assertEqual(len(rs), 4)
        self.assertAlmostEqual(rs[1][0], 0.75)
        self.assertTrue(all(a == b for a, b in LT.ranges(1.0, [0.0, -0.25])))  # points
        self.assertEqual(LT.ranges(1.0, [-0.1, -0.2]), [])                     # que des espaces : rien
        self.assertIsNone(LT.ranges(1e6, [0.001, -0.001]))                   # trop de tirets : continu
        self.assertAlmostEqual(LT.ranges(10.0, [2, -1], scale=2)[1][0], 6.0)


class TestDash(unittest.TestCase):
    def test_open_line(self):
        c = geom.Contour([geom.Line((0, 0), (30, 0))], False)
        pieces, dots = LT.dash_contour(c, [5, -2.5])
        self.assertEqual([round(length(p), 6) for p in pieces], [5.0] * 4)
        self.assertEqual([p.start[0] for p in pieces], [0.0, 7.5, 15.0, 22.5])
        self.assertEqual(dots, [])
        self.assertTrue(all(not p.closed for p in pieces))

    def test_dash_turns_corner(self):
        c = geom.Contour([geom.Line((0, 0), (3, 0)), geom.Line((3, 0), (3, 10))], False)
        pieces, _dots = LT.dash_contour(c, [5, -1])
        self.assertEqual(len(pieces[0].segments), 2)                          # le premier tiret prend le coin
        self.assertAlmostEqual(length(pieces[0]), 5.0)

    def test_circle_fitted_exact(self):
        ci = geom.circle((0, 0), 10)
        pieces, _dots = LT.dash_contour(ci, [3, -1], fit=True)
        self.assertEqual(len(pieces), round(2 * math.pi * 10 / 4))
        ls = [length(p) for p in pieces]
        self.assertLess(max(ls) - min(ls), 1e-3)                              # motif tombé juste
        for p in pieces:
            for s in p.segments:
                self.assertIsInstance(s, geom.Conic)                          # arcs coupés exactement
                for t in (0.0, 0.5, 1.0):
                    self.assertAlmostEqual(math.hypot(*s.point(t)), 10.0, places=6)

    def test_closed_wrap_joined(self):
        r = geom.rect(0, 0, 20, 10)                                           # périmètre 60
        pieces, _dots = LT.dash_contour(r, [8, -3])                          # 55 → 60 puis 0 → 8 : un seul tiret
        self.assertEqual(len(pieces), 5)
        self.assertAlmostEqual(length(pieces[-1]), 13.0)
        self.assertAlmostEqual(sum(length(p) for p in pieces), 4 * 8 + 13)

    def test_dots_to_circles(self):
        c = geom.Contour([geom.Line((0, 0), (10, 0))], False)
        path = LT.dash_path(geom.Path([c]), [2, -1, 0, -1], dot=0.5)
        circles = [k for k in path.contours if k.closed]
        dashes = [k for k in path.contours if not k.closed]
        self.assertEqual((len(dashes), len(circles)), (3, 2))
        self.assertTrue(all(abs(length(k) - math.pi * 0.5) < 1e-3 for k in circles))
        self.assertEqual(len(LT.dash_path(geom.Path([c]), [2, -1, 0, -1], dot=0).contours), 3)

    def test_long_pattern_keeps_closed_contour(self):
        pieces, _dots = LT.dash_contour(geom.rect(0, 0, 2, 2), [50, -5])
        self.assertEqual(len(pieces), 1)
        self.assertTrue(pieces[0].closed)


class TestLin(unittest.TestCase):
    def test_parse(self):
        text = ('﻿;; essai\n*TIRET,Tiret __ __\nA,.5,-.25\n'
                '*GAZ,Gaz ---G---\nA,.5,-.2,["G",STANDARD,S=.1,U=0.0,X=-0.1,Y=-.05],-.25\n'
                '*TIRET,encore\nA,1,-1\n*VIDE\n*MAUVAIS\nA,x,-1\n2,-1\n')
        items, warnings = LT.parse_lin(text)
        self.assertEqual([(t.name, t.pattern) for t in items], [('TIRET', [0.5, -0.25]), ('GAZ', [0.5, -0.2, -0.25])])
        self.assertEqual(items[0].description, 'Tiret __ __')
        joined = '\n'.join(warnings)
        for part in ('texte ou forme', 'deux fois', 'VIDE sans motif', 'MAUVAIS', 'sans ligne *NOM'):
            self.assertIn(part, joined)


class TestWindow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])
        from vectordrive.ui.main_window import MainWindow
        cls.w = MainWindow()

    @classmethod
    def tearDownClass(cls):
        cls.w.modified = False
        cls.w.close()

    def square(self):
        from vectordrive.core.document import Shape
        sh = Shape(path=geom.Path([geom.rect(0, 0, 20, 10)]), tool=0, filled=True)
        self.w.canvas.doc.add(sh)
        self.w.canvas.select([sh])
        return sh

    def test_command_in_ribbon(self):
        self.assertIn('dash_convert', self.w.A)
        self.assertFalse(self.w.A['dash_convert'].icon().isNull())

    def test_dash_selection_and_undo(self):
        sh = self.square()
        n = len(list(self.w.canvas.doc.iter_leaves()))
        out = self.w.dash_selection([5, -2.5], 1.0, True, 0.0)
        self.assertEqual(len(out), 1)
        self.assertEqual(len(out[0].path.contours), 8)
        self.assertFalse(out[0].filled)
        self.assertNotEqual(out[0].id, sh.id)
        leaves = list(self.w.canvas.doc.iter_leaves())
        self.assertNotIn(sh, leaves)
        self.assertEqual(len(leaves), n)
        self.w.undo()
        self.assertEqual(len(list(self.w.canvas.doc.iter_leaves())), n)
        self.assertTrue(any(len(it.path.contours) == 1 and it.path.contours[0].closed
                            for it in self.w.canvas.doc.iter_leaves() if hasattr(it, 'path')))

    def test_keep_originals(self):
        sh = self.square()
        n = len(list(self.w.canvas.doc.iter_leaves()))
        self.w.dash_selection([5, -2.5], keep=True)
        leaves = list(self.w.canvas.doc.iter_leaves())
        self.assertIn(sh, leaves)
        self.assertEqual(len(leaves), n + 1)

    def test_dialog(self):
        from vectordrive.ui.dash_dialog import KEY, DashDialog
        s = self.w.settings
        for k in ('type', 'motif', 'echelle', 'types_lin'):
            s.remove(KEY + k)
        dlg = DashDialog(self.w, s)
        self.assertEqual(dlg.kind.currentData(), 'DASHED')
        self.assertEqual(dlg.pattern.text(), '12.7, -6.35')
        dlg.kind.setCurrentIndex(dlg.kind.findData('CENTER'))
        self.assertEqual(LT.parse_pattern(dlg.pattern.text()), next(t for t in LT.standard() if t.name == 'CENTER').pattern)
        dlg.pattern.setText('4, -1, 0, -1')
        dlg._pattern_edited()
        self.assertEqual(dlg.kind.currentIndex(), 0)                          # motif retouché : à soi
        self.assertTrue(dlg.ok.isEnabled())
        dlg.pattern.setText('-1')
        dlg._pattern_edited()
        self.assertFalse(dlg.ok.isEnabled())
        dlg.pattern.setText('4, -1, 0, -1')
        dlg._pattern_edited()
        dlg.scale.setValue(0.5)
        v = dlg.values()
        self.assertEqual((v['pattern'], v['scale']), ([4.0, -1.0, 0.0, -1.0], 0.5))
        again = DashDialog(self.w, s)
        self.assertEqual((again.kind.currentIndex(), again.pattern.text(), again.scale.value()),
                         (0, '4, -1, 0, -1', 0.5))                               # dernières valeurs
        lin = os.path.join(tempfile.mkdtemp(), 'perso.lin')
        with open(lin, 'w', encoding='cp1252') as f:
            f.write('*PERFO,Perforation é\nA,1,-0.5\n')
        self.assertEqual(again.import_lin(lin), 1)
        self.assertEqual(again.kind.currentData(), 'PERFO')
        third = DashDialog(self.w, s)
        self.assertGreaterEqual(third.kind.findData('PERFO'), 0)              # gardé pour la prochaine fois
        for k in ('type', 'motif', 'echelle', 'types_lin'):
            s.remove(KEY + k)


if __name__ == '__main__':
    unittest.main()
