"""Round 706 : Réunir les textes (comme TXT2MTXT en DAO, d'après CADCraft) —
textes d'une ligne réunis en un texte de plusieurs lignes, de haut en bas,
à la même hauteur dans une ligne, interligne repris des écarts."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.core import text as TX
from vectordrive.core import textmerge as TM
from vectordrive.core.document import Shape, Text
from vectordrive.core.geom import Affine, Path


def txt(s, x, y, size=5.0, font='VD Trait', **kw):
    return Text(text=s, font=font, size=size, matrix=Affine.translation(x, y), **kw)


class TestMerge(unittest.TestCase):
    def test_top_down_and_same_line(self):
        parts = [txt('ligne 3', 10, 0), txt('ligne 1', 12, 20), txt('B', 40, 10.4), txt('ligne 2 A', 10, 10)]
        out = TM.merge(parts)
        self.assertEqual(out.text, 'ligne 1\nligne 2 A B\nligne 3')
        self.assertEqual((out.matrix.e, out.matrix.f), (10.0, 20.0))             # le plus à gauche, en haut
        em = TX.em_for_height(('<vectordrive:trait>', 0), 5.0)
        self.assertAlmostEqual(out.line_spacing * em, 10.0, places=3)            # interligne repris
        self.assertNotIn(out.id, {p.id for p in parts})
        self.assertIsNone(out.outline)

    def test_rotated_and_refused(self):
        rot = Affine.rotation(90)
        a = txt('haut', 0, 0)
        a.matrix = Affine.translation(0, 0) @ rot
        b = txt('bas', 0, 0)
        b.matrix = Affine.translation(8, 0) @ rot                                 # tourné de 90° : « plus bas » = à droite
        self.assertEqual(TM.merge([b, a]).text, 'haut\nbas')
        self.assertIsNone(TM.merge([txt('seul', 0, 0)]))
        on_arc = txt('arc', 0, 0)
        on_arc.extra['arc'] = {'center': [0, 0], 'radius': 10}
        self.assertFalse(TM.mergeable(on_arc))
        self.assertFalse(TM.mergeable(txt('  ', 0, 0)))
        self.assertFalse(TM.mergeable(Shape(path=Path())))


class TestCommand(unittest.TestCase):
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

    def test_merge_command_and_undo(self):
        c = self.w.canvas
        keep = Shape(path=Path())
        parts = [txt('Plaque', 0, 30), txt('N° 12', 0, 22), txt('2026', 0, 14)]
        for it in parts + [keep]:
            c.doc.add(it)
        n = len(list(c.doc.iter_leaves()))
        c.select(parts + [keep])
        out = self.w.merge_texts()
        self.assertEqual(out.text, 'Plaque\nN° 12\n2026')
        self.assertTrue(out.outline and out.outline.contours)
        leaves = list(c.doc.iter_leaves())
        self.assertEqual(len(leaves), n - 2)
        self.assertIn(keep, leaves)                                              # le reste de la sélection demeure
        self.assertEqual(c.selection, [out])
        self.w.undo()
        self.assertEqual(len(list(c.doc.iter_leaves())), n)

    def test_action(self):
        from vectordrive.ui import icons
        self.assertIn('text_merge', icons.ICONS)
        self.assertFalse(self.w.A['text_merge'].icon().isNull())


if __name__ == '__main__':
    unittest.main()
