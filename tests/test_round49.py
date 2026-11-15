"""Round 49 : guides annulables."""
import os
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')


class TestGuidesUndo(unittest.TestCase):
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

    def test_add_clear_undo_redo(self):
        w, c = self.w, self.w.canvas
        c.add_guide('v', 10.0)
        c.add_guide('h', 20.0)
        self.assertEqual(len(c.guides), 2)
        w.undo()
        self.assertEqual(c.guides, [['v', 10.0]])
        w.redo()
        self.assertEqual(len(c.guides), 2)
        w.clear_guides()
        self.assertEqual(c.guides, [])
        w.undo()
        self.assertEqual(len(c.guides), 2)

    def test_old_snapshot_format(self):
        w = self.w
        d = w.canvas.doc
        w._restore((list(d.layers), d.plate, list(d.tools), d.active))     # instantané à 4 éléments
        self.assertIsNotNone(w.canvas.doc)


if __name__ == '__main__':
    unittest.main()
