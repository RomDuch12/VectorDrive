"""Round 281 : relief TypeArt usiné à sa propre profondeur quand la
profondeur de l'opération est 0 ; modèles TypeEdit TypeArt repris en
Relief."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.cam import model as M, strategies as S, tpp
from vectordrive.core import typeart as TA
from vectordrive.core.document import Document

app = QApplication.instance() or QApplication([])


class TestReliefDepth(unittest.TestCase):
    def test_own_depth(self):
        d = Document()
        d.plate = None
        img = TA.dome([(5, 5)], TA.DomeSpec(diameter=8, height=1.5, resolution=0.2, margin=0.5))
        d.add(img)
        setup = M.setup_of(d)
        b = M.CamTool(name='B1', kind='boule', diameter=1.0, step_down=1.0)
        setup.tools = [b]
        tp = S.compute(d, setup, M.Operation(kind='relief', depth=0.0, tool_id=b.id, resolution=0.2,
                                             items=[img.id]))
        self.assertTrue(any('TypeArt' in w for w in tp.warnings))
        self.assertAlmostEqual(min(m.z for m in tp.moves), -img.extra['galbe']['relief_depth'], 1)

    def test_typeedit(self):
        self.assertEqual(tpp.TYPES['CP_TypeArt'][1], 'relief')
        t = tpp.to_template(tpp.Preset(name='TA', kind='CP_TypeArt'))
        self.assertEqual(t['operations'][0]['kind'], 'relief')


if __name__ == '__main__':
    unittest.main()
