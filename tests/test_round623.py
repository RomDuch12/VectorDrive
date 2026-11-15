"""Round 623 : l'origine du dessin devient le zéro des programmes machine
(comme le point zéro de TypeEdit : centre de la plaque, coin…) — parcours,
arcs, cycles de trous et brut décalés au post-traitement."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.cam import model, post
from vectordrive.cam.model import Move, Toolpath


def path():
    tp = Toolpath(op_id='o', tool_id='t', name='p')
    tp.moves = [Move('rapid', 10, 20, 5), Move('plunge', 10, 20, -1), Move('feed', 30, 20, -1),
                Move('arc_cw', 40, 10, -1, 30, 10)]
    tp.cycles = [{'kind': 'taraudage', 'x': 10.0, 'y': 20.0, 'depth': 6},
                 {'kind': 'instruction', 'name': 'palpage_z', 'params': {'x': 5, 'y': 5}}]
    tp.stock = 'gardé'
    return tp


class TestOrigin(unittest.TestCase):
    def test_shifted(self):
        tp = path()
        out = post.shifted([tp], (25.0, 10.0))[0]
        self.assertEqual([(m.x, m.y, m.z) for m in out.moves], [(-15, 10, 5), (-15, 10, -1), (5, 10, -1), (15, 0, -1)])
        self.assertEqual((out.moves[3].cx, out.moves[3].cy), (5, 0))          # centre de l'arc décalé
        self.assertEqual((out.cycles[0]['x'], out.cycles[0]['y']), (-15, 10))
        self.assertEqual(out.cycles[1]['params'], {'x': -20.0, 'y': -5.0})   # palpage : suit l'origine (round 630)
        self.assertEqual(out.stock, 'gardé')                                  # attributs ajoutés gardés
        self.assertEqual((tp.moves[0].x, tp.cycles[0]['x']), (10, 10.0))      # l'original intact
        self.assertIs(post.shifted([tp], (0, 0))[0], tp)
        self.assertIs(post.shifted([tp], None)[0], tp)

    def test_run_passes_shifted_paths_and_box(self):
        from vectordrive.plugins import REGISTRY
        seen = {}

        def write(toolpaths, setup, *, title='', machine=None, stem='', box_mm=None):
            seen['x'] = toolpaths[0].moves[0].x
            seen['box'] = box_mm
            return post.PostResult('G0', [], '.nc')
        REGISTRY.posts['essai623'] = ('Essai', write)
        try:
            s = model.CamSetup()
            post.run('essai623', [path()], s, box_mm=(0, 0, -3, 50, 20, 0), origin=(25, 10))
            self.assertEqual(seen['x'], -15)
            self.assertEqual(seen['box'], (-25, -10, -3, 25, 10, 0))
            post.run('essai623', [path()], s, box_mm=(0, 0, -3, 50, 20, 0))
            self.assertEqual((seen['x'], seen['box']), (10, (0, 0, -3, 50, 20, 0)))   # sans origine : inchangé
        finally:
            REGISTRY.posts.pop('essai623', None)

    def test_panel_origin(self):
        from PySide6.QtWidgets import QApplication
        QApplication.instance() or QApplication([])
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            doc = w.canvas.doc
            self.assertIsNone(w.cam_panel.program_origin())
            w.canvas.set_origin(25.0, 10.0)
            self.assertEqual(w.cam_panel.program_origin(), (25.0, 10.0))
            w.canvas.set_origin(0.0, 0.0)
            self.assertIsNone(w.cam_panel.program_origin())
            self.assertIs(w.canvas.doc, doc)
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
