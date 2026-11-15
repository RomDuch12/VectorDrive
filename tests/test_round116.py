"""Round 116 : symétrie cyclique (rosace) et centrale, notes (post-it)."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import geom
from vectordrive.core.document import Plate
from vectordrive.io import registry


class TestWindow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        QApplication.instance() or QApplication([])
        from vectordrive.ui.main_window import MainWindow
        cls.w = MainWindow()
        cls.w.resize(1000, 700)

    @classmethod
    def tearDownClass(cls):
        cls.w.A['sym_cyclic'].setChecked(False)
        cls.w.modified = False
        cls.w.close()

    def setUp(self):
        self.w.modified = False
        self.w.new_document()
        self.w.canvas.doc.plate = Plate(width=100, height=100)

    def test_cyclic(self):
        w = self.w
        w.cyclic_n.setValue(6)
        w.A['sym_cyclic'].setChecked(True)
        self.assertEqual(w.canvas.cyclic, 6)
        sh = w.canvas.commit_shape(geom.Path([geom.rect(70, 48, 10, 4)]))
        self.assertEqual(len(sh.path.contours), 6)
        bb = sh.bbox()
        self.assertAlmostEqual((bb[0] + bb[2]) / 2, 50, places=3)                # rosace centrée sur la plaque
        self.assertAlmostEqual((bb[1] + bb[3]) / 2, 50, places=3)
        w.A['sym_draw'].setChecked(True)                                        # l'axe remplace la rosace
        self.assertFalse(w.A['sym_cyclic'].isChecked())
        self.assertEqual(w.canvas.cyclic, 0)
        w.A['sym_draw'].setChecked(False)

    def test_point_symmetry(self):
        w = self.w
        w.A['sym_point'].trigger()
        self.assertEqual(w.canvas.cyclic, 2)
        sh = w.canvas.commit_shape(geom.Path([geom.circle((60, 70), 2)]))
        centers = sorted(round((c.bbox()[0] + c.bbox()[2]) / 2, 3) for c in sh.path.contours)
        self.assertEqual(centers, [40.0, 60.0])
        w.A['sym_cyclic'].setChecked(False)

    def test_notes(self):
        w = self.w
        i = w.add_note('Graver à 0,2 mm\nlaiton', at=(10, 20))
        self.assertEqual(i, 0)
        self.assertEqual(w.canvas.notes()[0]['text'], 'Graver à 0,2 mm\nlaiton')
        r = w.canvas._note_rect(w.canvas.notes()[0])
        self.assertEqual(w.canvas.note_at(r.center()), 0)
        w.edit_note(0, 'Laiton 2 mm')
        self.assertEqual(w.canvas.notes()[0]['text'], 'Laiton 2 mm')
        self.assertEqual(w.undo_labels()[0], 'Note')
        # gardées dans le VDZ, jamais dans un DXF
        d = tempfile.mkdtemp()
        registry.save_document(w.canvas.doc, os.path.join(d, 'n.vdz'))
        back = registry.open_document(os.path.join(d, 'n.vdz'))
        self.assertEqual(back.extra['notes'][0]['text'], 'Laiton 2 mm')
        registry.save_document(w.canvas.doc, os.path.join(d, 'n.dxf'))
        self.assertNotIn('Laiton', pathlib.Path(d, 'n.dxf').read_text(encoding='utf-8', errors='replace'))
        w.A['notes_visible'].setChecked(False)
        self.assertIsNone(w.canvas.note_at(r.center()))
        w.A['notes_visible'].setChecked(True)
        w.edit_note(0, '')
        self.assertEqual(w.canvas.notes(), [])
        self.assertNotIn('notes', w.canvas.doc.extra)
        w.undo()
        self.assertEqual(len(w.canvas.notes()), 1)

    def test_typeedit_links(self):
        from vectordrive.ui import shortcuts as S
        self.assertEqual(S.TE_ACTIONS['ID_SYMMETRICAL_CURVES_CYCLIC'], 'tool_sym_both')
        self.assertEqual(S.TE_ACTIONS['ID_POST_IT'], 'note')


if __name__ == '__main__':
    unittest.main()
