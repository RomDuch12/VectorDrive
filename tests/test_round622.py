"""Round 622 : guide de l'usinage 3D — « Contrôler avant la machine » (simulation : porte-outil et déplacements
rapides dans la matière ; reprise 3D ; longueur utile ; mécanismes) ; les rapides dans la matière arrivent
aussi dans la vue 3D en relief (avertissements du relief simulé)."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.cam import model, relief, simulate
from vectordrive.cam.model import Move, Toolpath
from vectordrive.core.document import Document

ROOT = pathlib.Path(__file__).resolve().parent.parent


class TestChecks(unittest.TestCase):
    def test_guide_section(self):
        text = (ROOT / 'docs' / 'usinage_3d.md').read_text(encoding='utf-8')
        self.assertIn('## 7. Contrôler avant la machine', text)
        part = text.split('## 7.')[1]
        for word in ('porte-outil', 'déplacement rapide', 'Reprise 3D', 'Longueur utile', 'Mécanismes'):
            self.assertIn(word, part)

    def test_relief_shows_rapids(self):
        doc = Document()
        st = model.setup_of(doc)
        t = model.CamTool(name='F2', kind='fraise', diameter=2)
        st.tools = [t]
        model.store(doc, st)
        tp = Toolpath(op_id='x', tool_id=t.id, name='t')
        tp.moves = [Move('rapid', 0, 0, 5), Move('rapid', 0, 0, 1), Move('plunge', 0, 0, -2), Move('feed', 5, 0, -2),
                    Move('rapid', 5, 0, -1), Move('rapid', 15, 0, -1), Move('rapid', 15, 0, 5)]
        simulate._SIM_CACHE.clear()
        r = relief.from_paths(doc, [tp], cut=True)
        self.assertTrue(any('déplacement rapide' in w for w in r.warnings), r.warnings)


if __name__ == '__main__':
    unittest.main()
