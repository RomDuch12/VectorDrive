"""Round 422 : Maj+C — cotes automatiques d'un cadre, cote entre deux points, édition d'une cote."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import dims as D
from vectordrive.core import geom
from vectordrive.core.document import Shape

app = QApplication.instance() or QApplication([])

P = {'template': '', 'width': True, 'height': True, 'h_side': 'dessous', 'v_side': 'gauche', 'gap': 8.0,
     'each': True, 'circles': False, 'save_as': ''}


class TestCore(unittest.TestCase):
    def test_frame_dims(self):
        ds = D.frame_dims((0, 0, 40, 20))
        self.assertEqual([(d.kind, round(d.value(), 6)) for d in ds], [('horizontale', 40), ('verticale', 20)])
        lines = D.build(ds[0])[0]
        self.assertAlmostEqual(lines.bbox()[1], -8 - D.DimStyle().symbol / 2, delta=3)   # sous le cadre
        up = D.frame_dims((0, 0, 40, 20), D.FrameDims(h_side='dessus', v_side='droite', height=True))
        self.assertGreater(D.build(up[0])[0].bbox()[3], 20)
        self.assertGreater(D.build(up[1])[0].bbox()[2], 40)
        self.assertEqual(len(D.frame_dims((0, 0, 40, 20), D.FrameDims(height=False))), 1)


class TestShiftC(unittest.TestCase):
    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.c = self.w.canvas
        self.w.settings.setValue(self.w.FRAME_DIMS_TEMPLATES, {})

    def tearDown(self):
        self.w.set_tool('select')
        self.w.modified = False
        self.w.close()

    def test_frame(self):
        self.assertEqual(self.w.A['smart_dims'].shortcut().toString(), 'Shift+C')
        from vectordrive.ui import shortcuts as SC
        self.assertEqual(SC.te_mapping([('ID_PALETTE_MESURE_COTATION', 'Shift+C')]), {'smart_dims': ['Shift+C']})
        fr = Shape(path=geom.Path([geom.rect(0, 0, 40, 20)]))
        circ = Shape(path=geom.Path([geom.circle((10, 10), 3)]))
        self.c.doc.add(fr)
        self.c.doc.add(circ)
        self.c.select([fr])
        got = self.w.smart_dims(params=dict(P))
        self.assertEqual(sorted(round(D.dim_of(g).value(), 6) for g in got), [20, 40])
        self.c.select([fr, circ])
        got = self.w.smart_dims(params=dict(P, each=False, circles=True, save_as='Plaque'))
        kinds = sorted(D.dim_of(g).kind for g in got)
        self.assertEqual(kinds, ['horizontale', 'radiale', 'verticale'])
        rad = next(D.dim_of(g) for g in got if D.dim_of(g).kind == 'radiale')
        self.assertAlmostEqual(rad.value(), 6, places=3)                      # Ø
        self.assertIn('Plaque', self.w.frame_dims_templates())
        self.c.select([fr])
        got = self.w.smart_dims(params=dict(P, template='Plaque', width=False, height=False))
        self.assertEqual(len(got), 2)                                          # le modèle impose ses réglages

    def test_edit_and_tool(self):
        fr = Shape(path=geom.Path([geom.rect(0, 0, 40, 20)]))
        self.c.doc.add(fr)
        self.c.select([fr])
        g = self.w.smart_dims(params=dict(P, height=False))[0]
        self.c.select([g])
        dlg = self.w.smart_dims(exec_dialog=False)                             # une cote choisie : ses réglages
        self.assertIsNotNone(dlg)
        self.assertTrue(hasattr(dlg, 'value'))
        dlg.reject()
        self.c.select([])
        self.assertIsNone(self.w.smart_dims())
        self.assertEqual(self.c.tool, 'dim')                                   # rien : cote entre deux points


if __name__ == '__main__':
    unittest.main()
