"""Round 899 : réglages des nouvelles opérations dans les options (F10, onglet FAO). Départ des contours fermés au choix
de l'utilisateur ; entrée en rampe des nouveaux détourages, poches et tracés, active par défaut comme dans la plupart des
réglages TypeEdit ; Gravure 3D sans passes sur les flancs, fond à 50 % de la pointe, comme TypeEdit. Les dernières
valeurs d'un parcours retenues avant ne remettent pas les anciens réglages d'origine ; celles retenues depuis restent un
choix."""
import json
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r899.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

KEYS = ('fao/depart', 'fao/rampe', 'fao/gravure3d_flancs', 'fao/gravure3d_fond')


class Options(unittest.TestCase):

    def test_the_options_and_their_defaults(self):
        from vectordrive.ui import options as O
        got = {k: O.BY_KEY[k].default for k in KEYS}
        self.assertEqual(got, {'fao/depart': 'proche', 'fao/rampe': True, 'fao/gravure3d_flancs': False,
                               'fao/gravure3d_fond': 'pointe'})
        self.assertEqual([v for v, _ in O.BY_KEY['fao/depart'].choices], ['proche', 'dessin'])
        self.assertEqual([v for v, _ in O.BY_KEY['fao/gravure3d_fond'].choices], ['pointe', 'crete'])
        fao = dict(O.SPEC)['FAO']
        self.assertTrue(set(KEYS) <= {o.key for o in fao})


class Panel(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._env = os.environ.get('VECTORDRIVE_TOOLS')
        os.environ['VECTORDRIVE_TOOLS'] = os.path.join(tempfile.mkdtemp(), 'tools.json')   # Mes outils : vide
        from vectordrive.ui.main_window import MainWindow
        cls.w = MainWindow()

    @classmethod
    def tearDownClass(cls):
        cls.w.modified = False
        cls.w.close()
        if cls._env is None:
            os.environ.pop('VECTORDRIVE_TOOLS', None)
        else:
            os.environ['VECTORDRIVE_TOOLS'] = cls._env

    def setUp(self):
        self.w.modified = False
        self.w.new_document()
        self.cp = self.w.cam_panel
        st = self.w.settings
        for k in KEYS + (self.cp.LAST_KEY,):
            st.remove(k)
        from vectordrive.core import geom
        from vectordrive.core.document import Shape
        sh = Shape(path=geom.Path([geom.rect(0, 0, 10, 10)]), tool=0)
        self.w.canvas.doc.active_layer.items.append(sh)
        self.w.canvas.select([sh])

    def tearDown(self):
        for k in KEYS + (self.cp.LAST_KEY,):
            self.w.settings.remove(k)
        self.w.modified = False

    def tool(self, op):
        return self.cp.setup().tool(op.tool_id)

    def with_form(self, key):
        from vectordrive.ui import cam_panel as CP
        s = self.cp.setup()                              # 1016 : le formulaire ne crée plus d'outil d'office
        for kind in ('fraise', 'conique'):
            self.cp._tool_for(s, kind)
        self.cp.save(s)
        with mock.patch.object(CP.FieldsDialog, 'exec', lambda dlg: 1):
            return self.cp.new_operation(key)

    def test_ramp_by_default_on_cuts_pockets_and_traces(self):
        for key in ('decoupe', 'gravure', 'trace'):
            with self.subTest(key):
                self.assertTrue(self.cp.new_operation(key, exec_dialog=False).ramp)
        self.assertFalse(self.cp.new_operation('percage', exec_dialog=False).ramp)
        self.assertFalse(self.cp.new_operation('gravure3d', exec_dialog=False).ramp)

    def test_ramp_off_in_the_options(self):
        self.w.settings.setValue('fao/rampe', False)
        self.assertFalse(self.cp.new_operation('decoupe', exec_dialog=False).ramp)
        self.assertEqual(self.cp._op_defaults('poche')['ramp'], False)

    def test_start_point_in_the_options(self):
        self.assertEqual(self.cp.new_operation('decoupe', exec_dialog=False).start_policy, 'proche')
        self.w.settings.setValue('fao/depart', 'dessin')
        self.assertEqual(self.cp.new_operation('decoupe', exec_dialog=False).start_policy, 'dessin')
        self.assertEqual(self.cp.new_operation('trace', exec_dialog=False).start_policy, 'dessin')
        self.w.settings.setValue('fao/depart', 'inconnu')
        self.assertEqual(self.cp._op_defaults()['start_policy'], 'proche')

    def test_engraving_3d_like_typeedit(self):
        op = self.cp.new_operation('gravure3d', exec_dialog=False)
        t = self.tool(op)
        self.assertGreater(t.tip, 0)
        self.assertFalse(op.vcarve_walls)
        self.assertAlmostEqual(op.stepover_mm, round(t.tip / 2, 3), places=6)
        from vectordrive.cam import advanced
        self.assertAlmostEqual(advanced._floor_step(op, t.tip / 2, 0.27), op.stepover_mm, places=6)

    def test_engraving_3d_as_before_in_the_options(self):
        self.w.settings.setValue('fao/gravure3d_flancs', True)
        self.w.settings.setValue('fao/gravure3d_fond', 'crete')
        self.assertTrue(self.cp._op_defaults('vcarve')['vcarve_walls'])
        op = self.cp.new_operation('gravure3d', exec_dialog=False)
        self.assertTrue(op.vcarve_walls)
        self.assertEqual(op.stepover_mm, 0.0)

    def test_values_kept_before_do_not_bring_back_the_old_defaults(self):
        from vectordrive.cam import model
        from vectordrive.cam import templates as TPL
        old = {}
        for key, kind in (('decoupe', 'contour'), ('gravure3d', 'vcarve')):
            o = model.Operation(kind=kind, depth=0.77, ramp=False, start_policy='proche', vcarve_walls=True,
                                stepover_mm=0.0)
            old[key] = TPL.single(o, None, '', key)                 # retenues avant ce round : sans 'defaults'
        self.w.settings.setValue(self.cp.LAST_KEY, json.dumps(old))
        self.w.settings.setValue('fao/depart', 'dessin')
        op = self.with_form('decoupe')
        self.assertEqual(op.depth, 0.77)                            # le reste des dernières valeurs : repris
        self.assertTrue(op.ramp)
        self.assertEqual(op.start_policy, 'dessin')
        op = self.with_form('gravure3d')
        self.assertEqual(op.depth, 0.77)
        self.assertFalse(op.vcarve_walls)
        self.assertAlmostEqual(op.stepover_mm, round(self.tool(op).tip / 2, 3), places=6)

    def test_values_kept_since_are_a_choice(self):
        op = self.with_form('decoupe')                              # retenues avec ce round
        self.assertTrue(op.ramp)
        self.assertEqual(self.cp.last_values('decoupe')['defaults'], self.cp.DEFAULTS_ROUND)
        g = self.with_form('gravure3d')
        self.assertAlmostEqual(g.stepover_mm, round(self.tool(g).tip / 2, 3), places=6)
        last = json.loads(self.w.settings.value(self.cp.LAST_KEY))
        last['decoupe']['operations'][0]['ramp'] = False            # choix de l'utilisateur au formulaire
        last['gravure3d']['operations'][0].update(stepover_mm=0.0, vcarve_walls=True)
        self.w.settings.setValue(self.cp.LAST_KEY, json.dumps(last))
        self.assertFalse(self.with_form('decoupe').ramp)
        g = self.with_form('gravure3d')
        self.assertEqual(g.stepover_mm, 0.0)
        self.assertTrue(g.vcarve_walls)

    def test_pocket_chosen_in_3d_and_add(self):
        from vectordrive.ui import cam_panel as CP
        sh = self.w.canvas.selection[0]
        self.assertTrue(self.cp.add_pocket([sh], 0.5, exec_dialog=False).ramp)
        self.assertTrue(self.cp._op_defaults(CP.model.Operation.kind)['ramp'])     # « Ajouter » : un tracé


if __name__ == '__main__':
    unittest.main()
