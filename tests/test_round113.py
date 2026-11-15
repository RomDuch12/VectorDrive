"""Round 113 : modèles de dessin (nouveau d'après un modèle, enregistrer
comme modèle), réglages exportés / importés d'un poste à l'autre, dernières
commandes TypeEdit équivalentes reliées."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))
os.environ['VECTORDRIVE_DOC_TEMPLATES'] = os.path.join(tempfile.mkdtemp(), 'modeles')

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from vectordrive import plugins
from vectordrive.core import geom
from vectordrive.core.document import Plate, Shape
from vectordrive.io import doc_templates as DT


class TestWindow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        QApplication.instance() or QApplication([])
        from vectordrive.ui.main_window import MainWindow
        cls.w = MainWindow()

    @classmethod
    def tearDownClass(cls):
        cls.w.modified = False
        cls.w.close()

    def setUp(self):
        self.w.modified = False
        self.w.new_document()

    def test_template_roundtrip(self):
        w = self.w
        d = w.canvas.doc
        d.plate = Plate(width=80, height=40)
        d.layers[0].items.append(Shape(path=geom.Path([geom.rect(5, 5, 70, 30)])))
        f = w.save_as_template('Plaque 80 × 40')
        self.assertTrue(f.is_file())
        self.assertIn('Plaque 80 × 40', DT.templates())
        w.modified = False
        w.new_document()
        self.assertTrue(w.new_from_template(str(f)))
        self.assertIsNone(w.path)
        self.assertFalse(w.modified)
        self.assertEqual(w.canvas.doc.plate.width, 80)
        self.assertEqual(len(w.canvas.doc.layers[0].items), 1)
        self.assertEqual(w.canvas.doc.source_path, '')
        self.assertTrue(DT.delete('Plaque 80 × 40'))

    def test_plugin_templates(self):
        f = os.path.join(tempfile.mkdtemp(), 'atelier.vdz')
        self.w.save_as_template('tmp')
        os.replace(DT._file('tmp'), f)
        plugins.REGISTRY.templates['dessin'] = {'Cartouche atelier': f, 'Absent': 'x:/nulle/part.vdz'}
        try:
            t = DT.templates()
            self.assertEqual(t['Cartouche atelier'], ('plugin', f))
            self.assertNotIn('Absent', t)
        finally:
            plugins.REGISTRY.templates.pop('dessin', None)

    def test_settings_export_import(self):
        w = self.w
        w.settings.setValue('options/grille', 2.5)
        w.settings.setValue('vue/theme', 'ardoise')
        w.settings.setValue('fichiers/recents', ['C:/x.vdz'])
        out = os.path.join(tempfile.mkdtemp(), 'reglages.ini')
        n = w.export_settings(out)
        self.assertGreater(n, 1)
        q = QSettings(out, QSettings.Format.IniFormat)
        self.assertEqual(q.value('vue/theme'), 'ardoise')
        self.assertIsNone(q.value('fichiers/recents'))                     # propre au poste
        w.settings.setValue('options/grille', 9.0)
        w.settings.setValue('vue/theme', 'clair')
        w.import_settings(out)
        self.assertEqual(float(w.settings.value('options/grille')), 2.5)
        self.assertAlmostEqual(w.canvas.snap.grid_step, 2.5)
        from vectordrive.ui.theme import current
        self.assertEqual(current().key, 'ardoise')
        w.set_theme('clair')

    def test_typeedit_links(self):
        from vectordrive.ui import shortcuts as S
        for cmd in ('ID_FILE_OPENMODEL', 'ID_FILE_SAVEMODEL', 'ID_COMPO_INVSENS', 'ID_APP_EXIT'):
            self.assertIn(S.TE_ACTIONS[cmd], self.w.A)


if __name__ == '__main__':
    unittest.main()
