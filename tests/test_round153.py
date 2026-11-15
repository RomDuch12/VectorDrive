"""Round 153 : palpages de NeoDrive (coin, arête, rectangle, symétrie, U),
mesure d'orientation, repère local, compteur de pièces ; réglages avancés
repliés et « Prendre sur la sélection » dans le formulaire."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.cam import instructions as I, model, strategies as S
from vectordrive.core import geom
from vectordrive.core.document import Document, Shape

BOX = (10.0, 20.0, 120.0, 90.0)


class TestDescriptions(unittest.TestCase):
    def test_new_instructions(self):
        for k in ('palpage_coin', 'palpage_arete', 'palpage_rectangle', 'palpage_symetrie', 'palpage_u',
                  'mesure_orientation', 'repere_local', 'compteur_pieces'):
            ins = I.INSTRUCTIONS[k]
            names = [f[0] for f in ins.fields]
            self.assertEqual(len(names), len(set(names)), k)
            self.assertTrue(set(ins.advanced) <= set(names), k)
            for f in ins.fields:
                if f[2] == 'choice':
                    self.assertIn(f[3], f[4], (k, f[0]))

    def test_choice_out_of_list(self):
        p = I.params_of('palpage_coin', {'corner': 'Nulle part', 'view': 'Intérieur'})
        self.assertEqual((p['corner'], p['view']), ('Avant gauche', 'Intérieur'))
        self.assertEqual(p['retract'], 15.0)

    def test_compute(self):
        s = model.CamSetup()
        op = model.Operation(kind='instruction', instruction='palpage_rectangle', params={'width_x': 50})
        s.operations = [op]
        tp = S.compute(Document(), s, op)
        self.assertEqual(tp.moves, [])
        self.assertEqual(tp.cycles[0]['params']['width_x'], 50.0)
        self.assertEqual(tp.cycles[0]['params']['origin'], 'Centre')


class TestFromSelection(unittest.TestCase):
    def test_corners(self):
        want = {'Avant gauche': (10, 20), 'Avant droit': (120, 20), 'Arrière gauche': (10, 90),
                'Arrière droit': (120, 90)}
        for corner, xy in want.items():
            p = I.from_selection('palpage_coin', {'corner': corner}, BOX)
            self.assertEqual((p['x'], p['y']), xy)

    def test_rectangle_and_axis(self):
        p = I.from_selection('palpage_rectangle', {}, BOX)
        self.assertEqual((p['x'], p['y'], p['width_x'], p['width_y']), (65, 55, 110, 70))
        p = I.from_selection('palpage_rectangle', {'origin': 'Avant droit'}, BOX)
        self.assertEqual((p['x'], p['y']), (120, 20))
        self.assertEqual(I.from_selection('palpage_symetrie', {}, BOX)['width'], 110)
        self.assertEqual(I.from_selection('palpage_symetrie', {'axis': 'Y (+ Z)'}, BOX)['width'], 70)
        self.assertEqual(I.from_selection('palpage_u', {}, BOX)['width'], 70)       # côtés parallèles à X
        self.assertEqual(I.from_selection('palpage_u', {'direction': 'Y+ (arête derrière)'}, BOX)['width'], 110)

    def test_edge_inside_material(self):
        p = I.from_selection('palpage_arete', {}, BOX)                    # X+ : à droite
        self.assertEqual((p['x'], p['y']), (110, 55))
        p = I.from_selection('palpage_arete', {'direction': 'Y− (arête devant)', 'z_edge_offset': 50}, BOX)
        self.assertEqual((p['x'], p['y']), (65, 55))                    # pas au-delà du milieu

    def test_two_circles(self):
        p = I.from_selection('mesure_orientation', {}, None, [(0, 0, 3), (2, 80, 4)])
        self.assertEqual((p['x1'], p['y1'], p['d1'], p['x2'], p['y2'], p['d2']), (0, 0, 6, 2, 80, 8))
        self.assertEqual(p['axis'], 'Y (+ Z)')
        self.assertEqual(I.from_selection('mesure_orientation', {'x1': 5}, None, [(0, 0, 3)])['x1'], 5)
        self.assertEqual(I.from_selection('repere_local', {'shift_x': 2}, BOX)['shift_x'], 2)   # sans reprise


class TestForm(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def dialog(self, key, selection):
        from vectordrive.ui import cam_panel
        op = model.Operation(kind='instruction', instruction=key)
        return op, cam_panel.FieldsDialog(None, 'Opération', op, Document(), [], selection=selection)

    def test_advanced_and_pick(self):
        sel = [Shape(path=geom.Path([geom.rect(10, 20, 110, 70)]), tool=0)]
        op, d = self.dialog('palpage_coin', sel)
        self.assertTrue(d.advanced_box.isHidden())
        self.assertIn('retract', d.param_widgets)
        d.advanced_toggle.setChecked(True)
        self.assertFalse(d.advanced_box.isHidden())
        d.param_widgets['corner'].setCurrentIndex(d.param_widgets['corner'].findData('Arrière droit'))
        self.assertTrue(d.pick_button.isEnabled())
        d.pick_button.click()
        self.assertEqual((d.param_widgets['x'].value(), d.param_widgets['y'].value()), (120, 90))
        self.assertEqual(d.param_widgets['corner'].currentData(), 'Arrière droit')
        self.assertFalse(d.advanced_box.isHidden())                       # reste ouvert
        d.apply()
        self.assertEqual((op.params['x'], op.params['corner']), (120, 'Arrière droit'))

    def test_pick_needs_selection(self):
        _op, d = self.dialog('palpage_rectangle', [])
        self.assertFalse(d.pick_button.isEnabled())
        c = Shape(path=geom.Path([geom.circle((0, 0), 3)]), tool=0)
        _op, d = self.dialog('mesure_orientation', [c])
        self.assertFalse(d.pick_button.isEnabled())                      # deux cercles
        c2 = Shape(path=geom.Path([geom.circle((60, 1), 4)]), tool=0)
        _op, d = self.dialog('mesure_orientation', [c, c2])
        d.pick_button.click()
        self.assertEqual((d.param_widgets['x2'].value(), d.param_widgets['d2'].value()), (60, 8))


if __name__ == '__main__':
    unittest.main()
