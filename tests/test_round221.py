"""Round 221 : session sur les gros dessins — parcours sérialisés dans le
fil de fond (plus de pause de l'interface), forme binaire compacte, pas de
réécriture quand ils n'ont pas changé ; anciennes sessions relues."""
import gzip
import json
import os
import pathlib
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])


def sample_paths():
    from vectordrive.cam.model import Move, Toolpath
    a = Toolpath(op_id='op1', tool_id='t1', name='Gravure', warnings=['lent'],
                 moves=[Move('rapid', 0, 0, 5), Move('plunge', 0, 0, -0.5), Move('feed', 10.25, 0.125, -0.5),
                        Move('arc_cw', 10.25, 5, -0.5, 10.25, 2.5), Move('sonde', 1, 2, 3)])
    b = Toolpath(op_id='op2', tool_id='t2', name='Perçage', source='typeedit',
                 cycles=[{'kind': 'drill', 'x': 1.0, 'y': 2.0, 'depth': 3.0}], moves=[Move('rapid', 1, 2, 5)])
    b.shown = False
    return [a, b]


def same(tps, back):
    return [(t.op_id, t.tool_id, t.name, t.source, t.warnings, t.cycles, getattr(t, 'shown', True),
             [(m.kind, m.x, m.y, m.z, m.cx, m.cy) for m in t.moves]) for t in tps] == \
           [(t.op_id, t.tool_id, t.name, t.source, t.warnings, t.cycles, getattr(t, 'shown', True),
             [(m.kind, m.x, m.y, m.z, m.cx, m.cy) for m in t.moves]) for t in back]


class TestFormat(unittest.TestCase):
    def test_binary_roundtrip_and_legacy(self):
        from vectordrive.ui import session
        tps = sample_paths()
        data = session.paths_bytes(tps)
        self.assertTrue(gzip.decompress(data).startswith(session.PATHS_MAGIC))
        self.assertTrue(same(tps, session.paths_from_bytes(data)))             # natures inconnues comprises
        legacy = gzip.compress(json.dumps([{'op_id': 'o', 'tool_id': 't', 'name': 'ancien', 'source': 'vectordrive',
                                            'warnings': [], 'cycles': [], 'shown': True,
                                            'moves': [['rapid', 0, 0, 5, 0, 0], ['feed', 1, 1, -1, 0, 0]]}]).encode())
        old = session.paths_from_bytes(legacy)                                 # session d'avant : relue
        self.assertEqual((old[0].name, len(old[0].moves), old[0].moves[1].kind), ('ancien', 2, 'feed'))
        self.assertNotEqual(session.paths_key(tps), session.paths_key(sample_paths()))   # recalcul : autre clé
        self.assertEqual(session.paths_key(tps), session.paths_key(list(tps)))           # même liste copiée : même clé


class TestWindow(unittest.TestCase):
    def test_background_and_unchanged(self):
        from vectordrive.core import geom
        from vectordrive.core.document import Shape
        from vectordrive.ui import session
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        sh = Shape(path=geom.Path([geom.rect(0, 0, 20, 10)]), tool=0)
        w.canvas.doc.add(sh)
        w.canvas.select([sh])
        w.cam_panel.new_operation('gravure', exec_dialog=False)
        self.assertTrue(w.cam_panel.toolpaths)
        with mock.patch.object(session, 'paths_bytes', wraps=session.paths_bytes) as pb:
            snap = session.snapshot(w)                                         # fil principal : rien de sérialisé
            pb.assert_not_called()
            folder = pathlib.Path(tempfile.mkdtemp())
            session.write(snap, folder)                                        # fil de fond : sérialisé là
            pb.assert_called_once()
        index = json.loads((folder / session.INDEX).read_text(encoding='utf-8'))
        f = folder / index['docs'][0]['paths']
        self.assertTrue(f.name.startswith('parcours_') and f.suffix == '.vdp')
        stamp = (f.stat().st_mtime_ns, f.read_bytes())
        with mock.patch.object(session, 'paths_bytes', wraps=session.paths_bytes) as pb:
            session.write(session.snapshot(w), folder)                         # inchangés : pas réécrits
            pb.assert_not_called()
        self.assertEqual((f.stat().st_mtime_ns, f.read_bytes()), stamp)
        w.canvas.select([sh])
        w.cam_panel.new_operation('percage', exec_dialog=False)                # recalcul : réécrits
        with mock.patch.object(session, 'paths_bytes', wraps=session.paths_bytes) as pb:
            session.write(session.snapshot(w), folder)
            pb.assert_called_once()
        names = sorted(p.name for p in folder.iterdir() if p.suffix == '.vdp')
        self.assertEqual(len(names), 1)                                        # un fichier par onglet
        w.modified = False
        w.close()
        w2 = MainWindow()                                                      # relecture
        self.assertEqual(session.restore(w2, folder), 1)
        self.assertEqual([t.name for t in w2.cam_panel.toolpaths], ['Gravure', 'Perçage'])
        w2.modified = False
        w2.close()


if __name__ == '__main__':
    unittest.main()
