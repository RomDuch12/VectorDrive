"""Round 110 : modèles d'usinage — jeu d'outils et d'opérations enregistré
sous un nom et appliqué d'un clic (outils retrouvés ou ajoutés, opérations
renumérotées, couleurs choisies) ; modèles des plugins."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))
os.environ['VECTORDRIVE_CAM_TEMPLATES'] = os.path.join(tempfile.mkdtemp(), 'modeles')

from PySide6.QtWidgets import QApplication

from vectordrive import plugins
from vectordrive.cam import model, templates as TPL


def sample_setup():
    s = model.CamSetup(post='gcode')
    f2 = model.CamTool(name='Fraise 2', kind='fraise', diameter=2.0, number=1)
    v30 = model.CamTool(name='Conique 30° 0,2', kind='conique', diameter=3.0, tip=0.2, angle=30, number=2)
    s.tools = [f2, v30]
    s.operations = [model.Operation(name='Contour', kind='contour', depth=3, tool_id=f2.id, sources=[1]),
                    model.Operation(name='Finition', kind='vcarve', depth=1.5, tool_id=v30.id, ref_tool_id=f2.id,
                                    sources=[1], items=['abc'])]
    return s


class TestTemplates(unittest.TestCase):
    def setUp(self):
        for f in TPL.user_dir().glob('*.json') if TPL.user_dir().is_dir() else []:
            f.unlink()

    def test_from_setup_and_apply_to_empty(self):
        tpl = TPL.from_setup(sample_setup(), 'Gamme essai', 'deux outils')
        self.assertEqual(len(tpl['operations']), 2)
        self.assertEqual(tpl['operations'][1]['items'], [])
        s, report = TPL.apply(model.CamSetup(), tpl)
        self.assertEqual(len(s.tools), 2)
        self.assertEqual(len(s.operations), 2)
        ids = {t.id for t in s.tools}
        self.assertTrue(all(o.tool_id in ids for o in s.operations))
        self.assertIn(s.operations[1].ref_tool_id, ids)
        self.assertNotIn(s.operations[0].id, {o['id'] for o in tpl['operations']})
        self.assertIn('2 opération(s)', report[0])
        self.assertEqual(s.post, 'gcode')

    def test_existing_tools_reused_and_numbers_kept_free(self):
        tpl = TPL.from_setup(sample_setup(), 'G')
        target = model.CamSetup()
        same = model.CamTool(name='Ma fraise', kind='fraise', diameter=2.0, number=1)
        other = model.CamTool(name='Autre', kind='fraise', diameter=6.0, number=2)
        target.tools = [same, other]
        s, report = TPL.apply(target, tpl, sources=[4])
        self.assertEqual(len(s.tools), 3)                                    # la conique est ajoutée…
        added = s.tools[-1]
        self.assertEqual(added.number, 3)                                    # …au premier numéro libre
        self.assertEqual(s.operations[0].tool_id, same.id)                   # la fraise 2 existante sert
        self.assertEqual([o.sources for o in s.operations], [[4], [4]])
        self.assertTrue(any('outil ajouté' in r for r in report))
        self.assertEqual(len(target.tools), 2)                               # l'original n'est pas touché

    def test_replace(self):
        tpl = TPL.from_setup(sample_setup(), 'G')
        s0, _r = TPL.apply(model.CamSetup(), tpl)
        s1, _r = TPL.apply(s0, tpl)
        self.assertEqual(len(s1.operations), 4)
        s2, _r = TPL.apply(s1, tpl, replace=True)
        self.assertEqual(len(s2.operations), 2)

    def test_user_and_plugin_templates(self):
        TPL.save_user(TPL.from_setup(sample_setup(), 'Mon modèle / A'))
        self.assertIn('Mon modèle / A', TPL.user_templates())
        plugins.REGISTRY.templates['fao'] = {'Gamme atelier': {'operations': [], 'tools': []},
                                             'Mon modèle / A': {'operations': [], 'tools': []}}
        try:
            allt = TPL.all_templates()
            self.assertEqual(allt['Gamme atelier'][0], 'plugin')
            self.assertEqual(allt['Mon modèle / A'][0], 'utilisateur')        # le sien l'emporte
        finally:
            plugins.REGISTRY.templates.pop('fao', None)
        self.assertTrue(TPL.delete_user('Mon modèle / A'))
        self.assertNotIn('Mon modèle / A', TPL.user_templates())


class TestPanel(unittest.TestCase):
    def test_save_and_apply_from_panel(self):
        QApplication.instance() or QApplication([])
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            p = w.cam_panel
            p.save(sample_setup())
            tpl = p.save_template('Panneau', 'essai')
            self.assertEqual(tpl['name'], 'Panneau')
            p.save(model.CamSetup())
            report = p.apply_template('Panneau', exec_dialog=False)
            self.assertTrue(report)
            self.assertEqual(len(p.setup().operations), 2)
            self.assertIn('Panneau', p.info.text())
            TPL.delete_user('Panneau')
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
