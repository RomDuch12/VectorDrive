"""Round 520 : fiche d'un programme (boîte Ouvrir) — durée calculée par la machine quand le lecteur la
connaît (SimPL : dossier MetaData de la DATRON)."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from vectordrive.plugins import REGISTRY
from vectordrive.ui import nc_preview as NP


def reader(text, name, path=None):
    from vectordrive.cam.model import Move, Toolpath
    tp = Toolpath(op_id='', tool_id='', name=name, source='nc')
    tp.moves = [Move('rapid', 0, 0, 5), Move('plunge', 0, 0, -0.2), Move('feed', 10, 0, -0.2)]
    tp.machine_seconds = 754.0
    return tp


class TestMachineDuration(unittest.TestCase):
    def test_duration_line(self):
        f = pathlib.Path(tempfile.mkdtemp()) / 'prog.essai520'
        f.write_text('programme')
        REGISTRY.nc_readers.append(('Essai 520', ('.essai520',), reader, None))
        try:
            info = NP.describe(f)
        finally:
            REGISTRY.nc_readers.pop()
        self.assertIn('Durée machine', info)
        self.assertIn('12', info)                                   # 754 s : 12 min 34 s


if __name__ == '__main__':
    unittest.main()
