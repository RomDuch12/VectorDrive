"""Round 102 : bibliothèque d'outils (tools.json), dessins DXF / STEP des
outils, catalogues en ligne, échanges (NeoDrive, TypeEdit .Dbt en mode de
compatibilité, CSV, données fabricant ISO 13399), gestionnaire."""
import json
import os
import pathlib
import tempfile
import unittest
import zipfile

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))
os.environ['VECTORDRIVE_TOOLS'] = os.path.join(tempfile.mkdtemp(), 'tools.json')

from PySide6.QtWidgets import QApplication

from vectordrive.cam import catalogs, model, toollib, tooldraw

NEO = {'version': '3.1', 'tools': {
    'datron_cyl3': {'name': 'Cyl 3 z2', 'reference': '0068493F / 1', 'rpm': 30000, 'feed_finishing': 1200,
                    'feed_plunge': 300, 'feed_ramp': 400, 'diameter': 3.0, 'vendor': 'DATRON', 'max_depth': 6,
                    'geometry': {'Diameter': 3.0, 'TipAngle': 0.0, 'TipDiameter': 3.0, 'NumberOfFlutes': 2,
                                 'FluteLength': 9.0},
                    'dessins': {'cotes': {'D1': 3.0, 'D2': 6.0, 'L1': 50.0, 'L2': 9.0}, 'famille': 'fraise'}},
    'con30': {'name': 'Con 30° 0.2', 'rpm': 25000, 'feed_finishing': 500, 'feed_plunge': 200, 'diameter': 3.0,
              'vendor': 'DATRON', 'geometry': {'Diameter': 3.0, 'TipAngle': 30.0, 'TipDiameter': 0.2}}}}


def app():
    return QApplication.instance() or QApplication([])


class TestDrawings(unittest.TestCase):
    def test_profiles_and_files(self):
        from vectordrive.io import registry
        tools = [model.CamTool(name='V', kind='conique', diameter=6, angle=30, tip=0.2),
                 model.CamTool(name='F', diameter=2, cut_length=6, geometry={'D2': 3, 'L1': 38, 'L3': 10, 'D3': 1.9}),
                 model.CamTool(name='B', kind='boule', diameter=1),
                 model.CamTool(name='T', diameter=4, geometry={'R': 0.5}),
                 model.CamTool(name='D', kind='foret', diameter=3, angle=118)]
        fams = []
        with tempfile.TemporaryDirectory() as tmp:
            for t in tools:
                p = tooldraw.profile_of(t)
                pts = p['points']
                self.assertTrue(all(b[1] >= a[1] for a, b in zip(pts, pts[1:])))     # z jamais décroissant
                fams.append(p['cotes']['famille'])
                out = tooldraw.write_drawings(t, tmp, t.name)
                self.assertGreaterEqual(registry.open_document(out['step']).stats()['objets'], 1)
                self.assertGreater(registry.open_document(out['dxf']).stats()['contours'], 1)
        self.assertEqual(fams, ['conique', 'fraise', 'boule', 'torique', 'foret'])
        v = tooldraw.profile_of(tools[0])['points']
        self.assertAlmostEqual(v[0][0], 0.1)                                          # la pointe de 0,2
        f = tooldraw.profile_of(tools[1])
        self.assertAlmostEqual(max(z for _r, z in f['points']), 38)                  # L1
        self.assertAlmostEqual(f['z_coupe'], 6)                                       # L2


class TestLibrary(unittest.TestCase):
    def test_neodrive_and_round_trips(self):
        tools = toollib.from_json(json.dumps(NEO))
        self.assertEqual([(t.name, t.kind) for t in tools], [('Cyl 3 z2', 'fraise'), ('Con 30° 0.2', 'conique')])
        c, v = tools
        self.assertEqual((c.spindle, c.feed, c.plunge, c.ref, c.flutes), (30000, 1200, 300, '0068493F', 2))
        self.assertEqual(c.geometry['L1'], 50.0)
        self.assertEqual((v.angle, v.tip), (30.0, 0.2))
        with tempfile.TemporaryDirectory() as tmp:
            for name in ('a.json', 'b.csv', 'c.neodrive.json', 'd.Dbt'):
                f = os.path.join(tmp, name)
                notes = toollib.export_file(tools, f)
                back, _n = toollib.import_file(f)
                self.assertEqual([t.name for t in back], [t.name for t in tools], name)
                self.assertEqual(back[1].kind, 'conique', name)
                self.assertAlmostEqual(back[0].feed, 1200, msg=name)
                if name.endswith('.Dbt'):
                    self.assertTrue(any('cotes du fabricant' in n for n in notes))     # mode de compatibilité
            self.assertEqual(toollib.load(os.path.join(tmp, 'a.json'))[0].geometry['D2'], 6.0)

    def test_csv_iso_symbols(self):
        text = 'name;DC;DCON;OAL;APMX;NOF;RE;vendor;ref\nBoule 2;2;4;50;4;2;1;ACME;B2-50\n'
        t = toollib.from_csv(text)[0]
        self.assertEqual((t.kind, t.diameter, t.cut_length, t.flutes), ('boule', 2.0, 4.0, 2))
        self.assertEqual(t.geometry['D2'], 4.0)
        self.assertEqual(t.catalog['reference'], 'B2-50')

    def test_manufacturer_files(self):
        xml = '<tool><property symbol="DC"><value>6</value></property><property symbol="OAL">57</property>' \
              '<NOF>3</NOF><property symbol="APMX"><value>13</value></property></tool>'
        p21 = "#10=PROPERTY('DC','cutting diameter',LENGTH_MEASURE(8.));\n#11=PROPERTY('NOF',$,COUNT_MEASURE(4.));"
        with tempfile.TemporaryDirectory() as tmp:
            z = pathlib.Path(tmp) / 'gtc.zip'
            with zipfile.ZipFile(z, 'w') as f:
                f.writestr('A/fraise6.xml', xml)
                f.writestr('B/fraise8.p21', p21)
                f.writestr('C/readme.txt', 'rien')
            tools, notes = toollib.import_file(z)
        self.assertEqual(sorted((t.diameter, t.flutes) for t in tools), [(6.0, 3), (8.0, 4)])
        six = next(t for t in tools if t.diameter == 6)
        self.assertEqual((six.cut_length, six.geometry['L1']), (13.0, 57.0))

    def test_catalogs(self):
        others = [v for v in catalogs.VENDORS if v.key != 'datron' and v.kind != 'plateforme']
        self.assertGreaterEqual(len(others), 20)
        self.assertEqual(catalogs.search_url(catalogs.vendor('DATRON'), '0068493F'),
                         'https://webshop.datron.de/search?search=0068493F')
        u = catalogs.search_url(catalogs.vendor('yg1'), 'EMB 52')
        self.assertTrue(u.startswith('https://duckduckgo.com/?q=YG-1+EMB+52'))
        self.assertIn('site%3Awalter-tools.com', catalogs.search_url(catalogs.vendor('walter'), 'X1'))


class TestDialog(unittest.TestCase):
    def setUp(self):
        app()
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        pathlib.Path(os.environ['VECTORDRIVE_TOOLS']).unlink(missing_ok=True)

    def tearDown(self):
        self.w.modified = False
        self.w.close()

    def test_manager(self):
        d = self.w.cam_panel.tool_library(exec_dialog=False)
        self.assertEqual(d.path, pathlib.Path(os.environ['VECTORDRIVE_TOOLS']))
        with tempfile.TemporaryDirectory() as tmp:
            f = pathlib.Path(tmp) / 'neo.json'
            f.write_text(json.dumps(NEO), encoding='utf-8')
            self.assertEqual(d.import_file(f), 2)
        self.assertEqual(len(toollib.load(d.path)), 2)                    # enregistré tout de suite
        d.select(d.tools[1])
        d.w['g_L1'].setValue(40)
        d.w['c_prix'].setValue(31.5)
        d.apply()
        t = toollib.load(d.path)[1]
        self.assertEqual((t.geometry['L1'], t.catalog['prix']), (40.0, 31.5))
        out = d.draw()
        self.assertTrue(pathlib.Path(out['step']).exists())
        self.assertEqual(d.add_to_document(), 1)
        self.assertEqual(self.w.cam_panel.setup().tools[-1].name, 'Con 30° 0.2')
        c = d.open_catalogs(exec_dialog=False)
        c.dry_run = True
        c.table.selectRow(0)
        c.ref.setText('0068493F')
        self.assertIn('webshop.datron.de/search?search=0068493F', c.search())
        self.assertEqual(c.open_site(), 'https://www.datron.com')

    def test_plugin_library_is_read_only(self):
        from vectordrive import plugins
        plugins.reset()
        try:
            api = plugins.Api(plugins.REGISTRY, plugins.PluginInfo('essai', name='Essai'))
            api.add_tool_library('Outils essai', lambda: toollib.from_json(json.dumps(NEO)))
            d = self.w.cam_panel.tool_library(exec_dialog=False)
            d.source.setCurrentIndex(d.source.findData('Outils essai'))
            self.assertEqual(len(d.tools), 2)
            self.assertFalse(d.buttons['new'].isEnabled())
            d.select(d.tools[0])
            self.assertEqual(d.copy_to_mine(), 1)
            self.assertEqual(len(toollib.load(d.path)), 1)
        finally:
            plugins.reset()


if __name__ == '__main__':
    unittest.main()
