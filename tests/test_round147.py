"""Round 147 : formulaires d'opération enregistrés et réappliqués sur
d'autres formes (couleurs ou objets sélectionnés) ; modèles de parcours
TypeEdit (.ttpl) : lecture, écriture, ceux du poste."""
import math
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))
os.environ['VECTORDRIVE_CAM_TEMPLATES'] = tempfile.mkdtemp()

CONICAL = ('<?xml version="1.0" encoding="ISO-8859-1" ?>\n'
           '<gangdrill.BdOTool type="0" num="7" diameter="3.175" angle="0.2617993877991494" truncation="0.2" '
           'radius="0" maxDepth="0.15" passDepth="0.05" snominal="24000" fnominal="0.8" fplg="0.3" nbdent="1" '
           'supplier="Datron" reference="0068302" toolName="Conique 30° 0,2 gravure">\n'
           '\t<mapparam.CMapParam MODE_GRAVURE="1">\n'
           '\t\t<entry key="NB_PASSES" value="3"/>\n'
           '\t</mapparam.CMapParam>\n</gangdrill.BdOTool>\n')


class TestTtpl(unittest.TestCase):
    def test_conical_template(self):
        from vectordrive.cam import ttpl
        tpl = ttpl.parse(CONICAL.split('?>', 1)[1].strip(), 'Gravure fine')
        t, o = tpl['tools'][0], tpl['operations'][0]
        self.assertEqual((t['kind'], t['number'], t['diameter'], t['tip']), ('conique', 7, 3.175, 0.2))
        self.assertAlmostEqual(t['angle'], 30.0, places=6)                    # demi-angle 15° (rad) → 30°
        self.assertEqual((t['feed'], t['plunge'], t['spindle']), (800.0, 300.0, 24000.0))
        self.assertEqual((o['kind'], o['depth'], o['step_down'], o['tool_id']), ('gravure', 0.15, 0.05, t['id']))
        self.assertEqual(tpl['typeedit']['params'], {'MODE_GRAVURE': '1', 'NB_PASSES': '3'})
        back = ttpl.parse(ttpl.to_xml(tpl).split('?>', 1)[1].strip(), 'retour')
        bt, bo = back['tools'][0], back['operations'][0]
        self.assertEqual((bt['kind'], bt['diameter'], bt['tip'], bt['number']), ('conique', 3.175, 0.2, 7))
        self.assertAlmostEqual(bt['angle'], 30.0, places=6)
        self.assertEqual((bo['depth'], bo['step_down']), (0.15, 0.05))
        self.assertEqual(back['typeedit']['params']['MODE_GRAVURE'], '1')

    def test_installed_presets(self):
        from vectordrive.cam import ttpl
        files = ttpl.installed()
        if not files:
            self.skipTest('pas de TypeEdit sur ce poste')
        for f in files:
            tpl = ttpl.read(f)
            self.assertEqual(len(tpl['tools']), 1)
            self.assertGreater(tpl['tools'][0]['diameter'], 0)
            out = pathlib.Path(tempfile.mkdtemp()) / f.name
            ttpl.write(tpl, out)
            again = ttpl.read(out)
            self.assertEqual(again['tools'][0]['diameter'], tpl['tools'][0]['diameter'])
            self.assertEqual(again['operations'][0]['depth'], tpl['operations'][0]['depth'])


class TestOperationTemplates(unittest.TestCase):
    def setup3(self):
        from vectordrive.cam import model
        s = model.CamSetup()
        a = model.CamTool(name='Conique', kind='conique', diameter=3.175, angle=30, tip=0.2, number=1)
        b = model.CamTool(name='Fraise 2', diameter=2, number=2)
        s.tools = [a, b]
        s.operations = [model.Operation(name='Gravure fine', kind='gravure', tool_id=a.id, depth=0.12),
                        model.Operation(name='Découpe', kind='detourage', tool_id=b.id, depth=3)]
        return s

    def test_from_operation_and_apply_on_items(self):
        from vectordrive.cam import model, templates as T
        s = self.setup3()
        tpl = T.from_operation(s, s.operations[0], 'Gravure fine 0,12')
        self.assertEqual(len(tpl['tools']), 1)
        self.assertEqual(len(tpl['operations']), 1)
        other = model.CamSetup()
        out, report = T.apply(other, tpl, items=['obj1', 'obj2'])
        self.assertEqual(out.operations[0].items, ['obj1', 'obj2'])
        self.assertEqual(out.operations[0].depth, 0.12)
        self.assertEqual(out.tools[0].name, 'Conique')
        out2, _r = T.apply(other, tpl, sources=[3])
        self.assertEqual((out2.operations[0].items, out2.operations[0].sources), ([], [3]))


class TestPanel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()

    def tearDown(self):
        self.w.modified = False
        self.w.close()

    def test_save_apply_ttpl(self):
        from vectordrive.cam import model, templates as T
        from vectordrive.core import geom
        from vectordrive.core.document import Shape
        w = self.w
        panel = w.cam_panel
        s = TestOperationTemplates().setup3()
        model.store(w.canvas.doc, s)
        panel.refresh()
        panel.ops.selectRow(0)
        tpl = panel.save_op_template('Gravure fine (form)')
        self.assertIn('Gravure fine (form)', T.user_templates())
        a = Shape(path=geom.Path([geom.rect(0, 0, 10, 10)]))
        w.canvas.doc.add(a)
        n_before = len(panel.setup().operations)
        panel.apply_template('Gravure fine (form)', exec_dialog=False, items=[a.id], sources=[])
        ops = panel.setup().operations
        self.assertEqual(len(ops), n_before + 1)
        self.assertEqual(ops[-1].items, [a.id])
        self.assertEqual(ops[-1].depth, tpl['operations'][0]['depth'])
        # .ttpl
        f = pathlib.Path(tempfile.mkdtemp()) / 'Gravure fine.ttpl'
        f.write_bytes(CONICAL.encode('latin-1'))
        got = panel.import_ttpl(str(f))
        self.assertEqual(got['name'], 'TypeEdit : Gravure fine')
        self.assertIn('TypeEdit : Gravure fine', T.user_templates())
        panel.ops.selectRow(0)
        out = panel.export_ttpl(str(pathlib.Path(tempfile.mkdtemp()) / 'export.ttpl'))
        from vectordrive.cam import ttpl
        back = ttpl.read(out)
        self.assertEqual(back['tools'][0]['kind'], 'conique')
        self.assertTrue(math.isclose(back['operations'][0]['depth'], 0.12))


if __name__ == '__main__':
    unittest.main()
