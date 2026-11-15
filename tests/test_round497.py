"""Round 497 : navigateur Ouvrir — Précédent, Parent, Suivant (historique des lieux vus) ; programmes
machine (G-code, Heidenhain, langages des plugins) en vignette, en fiche, ouverts dans le visualiseur."""
import os
import pathlib
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import geom
from vectordrive.core.document import Document, Shape
from vectordrive.io import registry
from vectordrive.ui import nc_preview as NP

app = QApplication.instance() or QApplication([])
GCODE = '''%
G21 G90
G0 Z5
G0 X0 Y0
G1 Z-0.5 F300
G1 X40 Y0 F1200
G2 X40 Y20 I0 J10
G1 X0 Y20
G1 X0 Y0
G0 Z5
M30
'''


class TestProgramsAndHistory(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = pathlib.Path(tempfile.mkdtemp())
        doc = Document()
        doc.add(Shape(path=geom.Path([geom.circle((0, 0), 10)])))
        registry.save_document(doc, cls.dir / 'rond.dxf')
        (cls.dir / 'cadre.nc').write_text(GCODE)
        (cls.dir / 'Sous dossier').mkdir()
        (cls.dir / 'Sous dossier' / 'poche.gcode').write_text(GCODE)

    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.w._remember_dir('ouvrir', str(self.dir / 'rond.dxf'))
        self.w.settings.setValue('navigateur/filtre', 0)
        self.dlg = self.w.file_browser(exec_dialog=False)
        self.p = self.dlg.panel

    def tearDown(self):
        self.dlg.reject()
        self.w.modified = False
        self.w.close()

    def names(self):
        return [self.p.list.item(i).text() for i in range(self.p.list.count())]

    def test_program_listed_and_drawn(self):
        self.assertEqual(self.names(), ['..', 'Sous dossier', 'cadre.nc', 'rond.dxf'])
        img = NP.preview_image(self.dir / 'cadre.nc', 120)
        self.assertEqual((img.width(), img.height()), (120, 120))
        self.assertTrue(any(img.pixelColor(60, y).name() != '#ffffff' for y in range(30, 36)))   # trait Y20
        from vectordrive.ui.symbols import describe_file, preview_image
        self.assertIsNotNone(preview_image(self.dir / 'cadre.nc', 64))         # même voie que les dessins
        info = describe_file(self.dir / 'cadre.nc')
        self.assertIn('Programme ISO', info)
        self.assertIn('40,00 × 20,00 mm', info)
        (self.dir / 'vide.nc').write_text('% rien\n')
        self.assertIsNone(NP.preview_image(self.dir / 'vide.nc', 64))

    def test_plugin_extension_in_filters(self):
        from vectordrive.plugins import REGISTRY
        from vectordrive.ui import file_browser as FB
        REGISTRY.nc_readers.append(('Essai', ('.essai',), lambda text, name: None, None))
        try:
            self.assertIn('.essai', NP.program_exts())
            self.assertIn('.essai', FB.filters()[0][1])                         # dessins et programmes
            self.assertNotIn('.essai', dict(FB.filters())['DXF'])
        finally:
            REGISTRY.nc_readers.pop()

    def test_back_up_forward(self):
        p, d = self.p, self.dlg
        self.assertFalse(d.b_back.isEnabled())
        self.assertTrue(d.b_up.isEnabled())
        p.show_folder(self.dir / 'Sous dossier')
        self.assertEqual(self.names(), ['..', 'poche.gcode'])
        self.assertTrue(d.b_back.isEnabled())
        d.b_up.click()                                                          # parent
        self.assertEqual(p._folder, self.dir)
        d.b_back.click()
        self.assertEqual(p._folder, self.dir / 'Sous dossier')
        d.b_back.click()
        self.assertEqual(p._folder, self.dir)
        self.assertTrue(d.b_forward.isEnabled())
        d.b_forward.click()
        self.assertEqual(p._folder, self.dir / 'Sous dossier')
        p.show_recents()                                                        # un nouveau lieu efface la suite
        self.assertFalse(d.b_forward.isEnabled())
        self.assertFalse(d.b_up.isEnabled())
        d.b_back.click()
        self.assertEqual(p._folder, self.dir / 'Sous dossier')
        p.refresh()                                                             # même lieu : pas noté deux fois
        self.assertTrue(d.b_forward.isEnabled())

    def test_open_program(self):
        self.dlg.choose([self.dir / 'cadre.nc'])
        self.assertEqual(self.dlg.paths, [str(self.dir / 'cadre.nc')])
        from vectordrive.ui import file_browser as FB

        class Fake:
            def __init__(self, win, folder=''):
                self.paths, self.insert = [str(TestProgramsAndHistory.dir / 'cadre.nc')], False

            def exec(self):
                return 1

            def deleteLater(self):
                pass
        with mock.patch.object(FB, 'FileBrowser', Fake), \
                mock.patch.object(type(self.w), 'view_nc_program') as view, \
                mock.patch.object(type(self.w), 'open_path') as op:
            self.w.file_browser()
        view.assert_called_once_with(str(self.dir / 'cadre.nc'))
        op.assert_not_called()
        tp = self.w.open_nc_program(str(self.dir / 'cadre.nc'), add=False)    # le visualiseur le lit
        self.assertGreater(len(tp.moves), 5)


if __name__ == '__main__':
    unittest.main()
