"""Round 458 : 3D — la légende donne pour chaque parcours son temps estimé et sa longueur en
avance, et le total."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.cam import model
from vectordrive.cam.model import Move, Toolpath
from vectordrive.ui import view3d as V

app = QApplication.instance() or QApplication([])


def tp(name, op_id, tool_id, n=10):
    t = Toolpath(op_id=op_id, tool_id=tool_id, name=name)
    t.moves = [Move('rapid', 0, 0, 5), Move('plunge', 0, 0, -1)] + \
        [Move('feed', 100.0 * (i % 2 == 0), 10.0 * i, -1) for i in range(1, n)]
    return t


class TestLegend(unittest.TestCase):
    def test_times(self):
        from vectordrive.cam import relief as RL
        from vectordrive.core.document import Document
        s = model.CamSetup()
        t1 = model.CamTool(name='F', kind='fraise', diameter=2, feed=600)
        s.tools = [t1]
        o1 = model.Operation(kind='poche', tool_id=t1.id, feed=1200)
        o2 = model.Operation(kind='poche', tool_id=t1.id, feed=300)
        s.operations = [o1, o2]
        a, b = tp('Rapide', o1.id, t1.id), tp('Lente', o2.id, t1.id)
        v = V.View3D()
        v.setup = s
        v.set_relief(RL.from_paths(Document(), [a, b], cut=False))
        lines = [t for t, c in v.overlay_lines() if c is not None]
        self.assertTrue(lines[0].startswith('Rapide  — '))
        self.assertIn(' m', lines[0])
        fast, slow = v._stat(a)[0], v._stat(b)[0]
        self.assertGreater(slow, fast * 2)                                        # avance de l'opération
        total = [t for t, c in v.overlay_lines() if t.startswith('Total')]
        self.assertEqual(len(total), 1)
        self.assertIn('en avance', total[0])
        v.deleteLater()


if __name__ == '__main__':
    unittest.main()
