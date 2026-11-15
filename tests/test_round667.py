"""Round 667 : trajectoires posées sur la pièce 3D (ou les volumes du
dessin) : les cochées que le programme écrirait — pas celles d'opérations
désactivées —, aucune si elles datent d'avant un changement du dessin ; la
vue le dit, « Calculer » les remet."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))
os.environ.setdefault('VECTORDRIVE_CAM_TEMPLATES', os.path.join(tempfile.mkdtemp(), 'modeles_fao'))

from PySide6.QtWidgets import QApplication

from tests import test_round657 as R657
from tests import test_round664 as R664

app = QApplication.instance() or QApplication([])


@unittest.skipUnless(__import__('vectordrive.core.solids', fromlist=['x']).available(), 'manifold3d absent')
class TestModelPaths(unittest.TestCase):
    setUp, names = R657.TestWindow.setUp, R657.TestWindow.names
    tearDown, move_part = R664.TestWindow.tearDown, R664.TestWindow.move_part

    def shown(self):
        self.assertTrue(self.p.refresh())
        return self.names(self.p.view.model_paths)

    def test_current_paths_on_part(self):
        cp, p = self.cp, self.p
        self.assertEqual(self.shown(), ['Un', 'Deux'])
        self.assertNotIn('Calculer', p.info.text())
        self.move_part()
        self.assertEqual(self.shown(), [])                                        # d'avant le déplacement
        self.assertIn('Calculer', p.info.text())
        with mock.patch.object(self.w, 'view_mode', lambda: '3d'):
            cp.compute()                                                          # la vue suit
        self.assertEqual(self.names(p.view.model_paths), ['Un', 'Deux'])
        self.assertNotIn('Calculer', p.info.text())

    def test_disabled_not_on_part(self):
        cp, p = self.cp, self.p
        s = cp.setup()
        s.operations[1].enabled = False
        cp.save(s)
        self.assertEqual(self.shown(), ['Un'])
        s.operations[0].enabled = False
        cp.save(s)
        self.assertEqual(self.shown(), [])
        self.assertIn('désactivées', p.info.text())

    def test_unchecked_not_noted(self):
        for tp in self.cp.toolpaths:
            tp.shown = False
        self.assertEqual(self.shown(), [])
        self.assertNotIn('Calculer', self.p.info.text())
        self.assertEqual(self.p._outdated_note(self.cp), '')

    def test_form_after_change_keeps_old_marked(self):
        from vectordrive.core import placement3d as P3
        cp = self.cp
        self.move_part()
        cp.compute_op(cp.setup().operations[1])                                   # « Deux » pour la pièce déplacée
        self.assertEqual(cp._memo('_placement_states'), '')                       # « Un » reste d'avant
        self.doc.extra.pop(P3.KEY_BODIES, None)                                   # remise comme au calcul
        self.assertTrue(cp.outdated())
        before = list(cp.toolpaths)
        tps = cp.current_paths(dates=False)                                       # tout refait
        self.assertEqual(self.names(tps), ['Un', 'Deux'])
        self.assertFalse(set(map(id, tps)) & set(map(id, before)))
        self.assertFalse(cp.outdated())

    def test_forms_only_reference(self):
        from vectordrive.core import surface2d
        cp = self.cp
        for name in cp.MEMOS:
            cp._remember(name, None)
        cp.display([])
        for o in cp.setup().operations:
            cp.compute_op(o)                                                      # liste faite par les formulaires
        self.assertEqual(cp._memo('_surface_states'), surface2d.state(self.doc))
        self.assertFalse(cp.outdated())

    def test_program_still_on_part(self):
        from vectordrive.cam import model
        cp, p = self.cp, self.p
        prog = model.Toolpath('', '', [model.Move('feed', 0, 0, 0), model.Move('feed', 5, 0, 0)], name='prog.nc')
        cp.display([prog] + list(cp.toolpaths))
        self.move_part()
        self.assertEqual(self.shown(), ['—'])                                     # le programme relu, pas les autres
        self.assertIn('Calculer', p.info.text())
        self.assertEqual(p._computed_paths(), [])                                 # simulation : rien de partiel

    def test_typeedit_with_ops_disabled(self):
        from vectordrive.cam import model
        cp = self.cp
        te = model.Toolpath('', '', [model.Move('feed', 0, 0, 0), model.Move('feed', 5, 0, 0)], name='TE')
        cp.display(list(cp.toolpaths) + [te])
        s = cp.setup()
        for o in s.operations:
            o.enabled = False
        cp.save(s)
        self.move_part()
        self.assertEqual(self.shown(), ['—'])                                     # écrit par le programme : montré
        self.assertNotIn('Calculer', self.p.info.text())


if __name__ == '__main__':
    unittest.main()
