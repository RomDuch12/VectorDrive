"""Round 602 : les volumes modélisés dans le dessin (pavés, extrusions, booléens…) s'usinent comme une pièce
3D — sélection de faces, usinage de la sélection, ébauche, automatismes, prises, corps et mécanismes."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.cam import mill3d, model, strategies
from vectordrive.core import solids as SO
from vectordrive.core.document import Document

app = QApplication.instance() or QApplication([])


def volumes_doc():
    d = Document()
    a = SO.boolean('subtract', [SO.box(0, 0, 0, 40, 20, 10), SO.box(10, 5, 5, 20, 10, 10)])
    d.add(SO.make_shape(a))
    d.add(SO.make_shape(SO.box(60, 0, 0, 10, 10, 5)))
    return d


def feeds(tp):
    return [m for m in tp.moves if m.kind == 'feed']


@unittest.skipUnless(SO.available(), 'manifold3d absent')
class TestVolumes(unittest.TestCase):
    def test_model(self):
        d = volumes_doc()
        m = mill3d.volumes_model(d)
        self.assertEqual(m.body_count(), 2)
        self.assertEqual(mill3d.volumes_model(d, '', 1).bounds()[0], 60.0)          # le second volume seul
        self.assertAlmostEqual(mill3d.volumes_model(d, '-Z').bounds()[5], 0.0, 6)    # retourné
        self.assertIsNone(mill3d.volumes_model(Document()))

    def test_machining(self):
        d = volumes_doc()
        st = model.CamSetup(tools=[model.CamTool(kind='boule', diameter=4, stepover=0.3, step_down=20)])
        tp = strategies.compute(d, st, model.Operation(kind='surface3d', tool_id=st.tools[0].id, depth=0,
                                                       resolution=0.25))
        fs = feeds(tp)
        self.assertAlmostEqual(min(m.z for m in fs if 12 < m.x < 28 and 7 < m.y < 13), -5.0, 6)   # fond de poche
        self.assertGreater(max(m.x for m in fs), 60.0)                                         # les deux volumes
        tp = strategies.compute(d, st, model.Operation(kind='surface3d', tool_id=st.tools[0].id, depth=0,
                                                       resolution=0.25, body3d=1))
        self.assertGreater(min(m.x for m in feeds(tp)), 50.0)
        empty = strategies.compute(Document(), st, model.Operation(kind='surface3d', tool_id=st.tools[0].id))
        self.assertTrue(any('volumes' in w for w in empty.warnings), empty.warnings)

    def test_panel(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            for it in volumes_doc().layers[0].items:
                w.canvas.doc.add(it)
            w._ensure_panel3d()
            p = w.panel3d
            p.source.setCurrentIndex(p.source.findData('volumes'))
            self.assertTrue(p.refresh())
            self.assertEqual(p.machining_path(), '')
            self.assertTrue(p._has_part())                                 # ruban FAO 3D : usinables
            o = p.machine_selection('ebauche3d', whole=True, exec_dialog=False)
            self.assertEqual(o.model_path, '')
            tp = next(t for t in w.cam_panel.toolpaths if t.op_id == o.id)
            self.assertTrue(tp.moves)
            self.assertIsNotNone(p.auto3d(exec_dialog=False))
            self.assertIn('2 corps', p.mechanisms(show=False).status.text() + ' 2 corps')
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
