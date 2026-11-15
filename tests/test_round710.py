"""Round 710 : Lignes de construction (comme XLINE en DAO, d'après CADCraft) —
guides obliques gardés à part, accrochage dessus et aux croisements, outil à
clics, glisser, suppression sur une règle, double-clic, effacer, annuler."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.core.snap import Snap


class TestSnap(unittest.TestCase):
    def test_on_line_and_crossings(self):
        s = Snap(enabled=True, modes={'guide'})
        s.obliques = [(0.0, 0.0, 45.0)]
        h = s.query(5.0, 5.3, 0.5, [])
        self.assertEqual(h.kind, 'guide')
        self.assertAlmostEqual(h.x, 5.15, places=6)                     # pied de la perpendiculaire
        self.assertAlmostEqual(h.y, 5.15, places=6)
        s.guides = [('h', 4.0)]
        h = s.query(4.1, 4.2, 0.5, [])
        self.assertAlmostEqual((h.x, h.y), (4.0, 4.0))                  # croisement oblique × horizontal
        s.guides = []
        s.obliques = [(0.0, 0.0, 45.0), (10.0, 0.0, 135.0)]
        h = s.query(5.2, 4.9, 0.5, [])
        self.assertAlmostEqual(h.x, 5.0, places=6)                      # croisement de deux obliques
        self.assertAlmostEqual(h.y, 5.0, places=6)
        self.assertIsNone(s.query(20.0, 0.0, 0.5, []))
        s.obliques, s.guides = [], [('v', 3.0), ('h', 2.0)]
        h = s.query(3.2, 2.1, 0.5, [])
        self.assertEqual((h.x, h.y), (3.0, 2.0))                        # guides droits seuls : comme avant


class TestCanvas(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])
        from vectordrive.ui.main_window import MainWindow
        cls.w = MainWindow()
        cls.w.resize(1000, 700)

    @classmethod
    def tearDownClass(cls):
        cls.w.modified = False
        cls.w.close()

    def setUp(self):
        c = self.w.canvas
        c.doc.extra.pop(c.OBLIQUES, None)
        c.guides.clear()

    def test_add_undo_clear(self):
        w, c = self.w, self.w.canvas
        self.assertEqual(c.add_oblique_guide(1, 2, 30), 'o')
        self.assertEqual(c.add_oblique_guide(5, 6, 180), 'h')            # horizontale : guide ordinaire
        self.assertEqual(c.add_oblique_guide(5, 6, -90), 'v')
        self.assertEqual(c.oblique_guides, [[1.0, 2.0, 30.0]])
        self.assertEqual(c.guides, [['h', 6.0], ['v', 5.0]])
        c.grab()                                                          # se dessine
        w.undo()
        w.undo()
        w.undo()
        self.assertEqual(c.oblique_guides, [])
        self.assertNotIn(c.OBLIQUES, c.doc.extra)
        w.redo()
        self.assertEqual(c.oblique_guides, [[1.0, 2.0, 30.0]])
        w.clear_guides()
        self.assertEqual(c.oblique_guides, [])
        w.undo()
        self.assertEqual(c.oblique_guides, [[1.0, 2.0, 30.0]])

    def test_edit_pick_and_remove(self):
        w, c = self.w, self.w.canvas
        c.add_oblique_guide(0, 0, 45)
        c.fit((-50, -50, 50, 50))
        self.assertEqual(c.oblique_at(c.to_screen(10, 10)), 0)
        self.assertIsNone(c.oblique_at(c.to_screen(10, -10)))
        self.assertTrue(w.edit_oblique_guide(0, {'x': 1.0, 'y': 2.0, 'angle': 225.0}))
        self.assertEqual(c.oblique_guides, [[1.0, 2.0, 45.0]])
        self.assertTrue(w.edit_oblique_guide(0, {'x': 1.0, 'y': 2.0, 'angle': 90.0}))
        self.assertEqual((c.oblique_guides, c.guides), ([], [['v', 1.0]]))   # verticale : guide ordinaire
        w.undo()
        self.assertTrue(w.edit_oblique_guide(0, {'delete': True}))
        self.assertEqual(c.oblique_guides, [])
        from vectordrive.io import native
        c.add_oblique_guide(0, 0, 60)
        snap = native.snapshot(c.doc)
        self.assertIsNot(snap.extra[c.OBLIQUES], c.doc.extra[c.OBLIQUES])  # copie pour l'enregistrement de fond

    def test_tool(self):
        from vectordrive.ui import icons
        from vectordrive.ui.tools import XLineTool
        c = self.w.canvas
        t = XLineTool(c)
        t.press(None, (0.0, 0.0), None)
        t.move(None, (10.0, 10.0), None)
        self.assertAlmostEqual(c.oblique_preview[2], 45.0)
        t.press(None, (10.0, 10.0), None)
        t.press(None, (10.0, -17.32), None)                               # deuxième ligne par le même point
        self.assertEqual(len(c.oblique_guides), 2)
        self.assertAlmostEqual(c.oblique_guides[1][2], 180.0 - 60.0, places=2)
        t.cancel()
        self.assertIsNone(c.oblique_preview)
        self.assertIn('xline', icons.ICONS)
        self.assertFalse(self.w.A['tool_xline'].icon().isNull())
        self.w.set_tool('xline')
        self.assertIsInstance(c.tool_obj, XLineTool)
        self.w.set_tool('select')


if __name__ == '__main__':
    unittest.main()
