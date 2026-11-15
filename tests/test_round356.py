"""Round 356 : reliefs — passes selon X, selon Y, ou croisées (finition selon
Y à la dernière cote)."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import numpy as np
from PySide6.QtWidgets import QApplication

from vectordrive.cam import model as M, strategies as S
from vectordrive.core import galbe as GB
from vectordrive.core.document import Document

app = QApplication.instance() or QApplication([])


def run(**kw):
    d = Document()
    d.plate = None
    H = np.zeros((60, 100))
    H[20:40, 30:70] = -1.0
    img = GB.encode(H + 1.0, 0.0, 6.0, 0.1, GB.GalbeSpec())
    img.tool = 1
    d.add(img)
    setup = M.setup_of(d)
    t = M.CamTool(name='B2', kind='boule', diameter=2, stepover=0.5)
    setup.tools = [t]
    return S.compute(d, setup, M.Operation(kind='relief', depth=1, step_down=1, tool_id=t.id, resolution=0.1, **kw))


def direction(tp):
    """Longueurs avancées le long de X (dy ≈ 0) et le long de Y."""
    xs = ys = 0.0
    prev = None
    for m in tp.moves:
        if prev is not None and m.kind == 'feed':
            dx, dy = abs(m.x - prev.x), abs(m.y - prev.y)
            if dx > 1e-6 and dy < 1e-9:
                xs += dx
            elif dy > 1e-6 and dx < 1e-9:
                ys += dy
        prev = m
    return xs, ys


class TestRasterDir(unittest.TestCase):
    def test_dirs(self):
        x = direction(run())
        y = direction(run(raster_dir='y'))
        xy = direction(run(raster_dir='xy'))
        self.assertGreater(x[0], x[1])
        self.assertGreater(y[1], y[0])
        self.assertGreater(xy[1], x[1])                 # la finition croisée ajoute des passes selon Y
        self.assertGreater(xy[0], y[0])


if __name__ == '__main__':
    unittest.main()
