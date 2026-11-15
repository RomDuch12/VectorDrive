"""Round 442 : modèles de parcours importés de TypeEdit — arborescence refaite d'après le nombre
d'éléments de chaque dossier (séparateurs compris), noms entiers ; palette : glisser-déposer,
nouveau dossier (gardé vide), renommer, Suppr, réimport sans doublon."""
import os
import pathlib
import struct
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication, QMessageBox

from vectordrive.cam import tpp

app = QApplication.instance() or QApplication([])


def cs(s: str) -> bytes:
    b = s.encode('cp1252')
    return bytes([len(b)]) + b


def folder(name: str, count: int) -> bytes:
    return b'\0' * 4 + b'\xff' * 8 + struct.pack('<i', count) + cs(name)


def preset(name: str) -> bytes:
    sec = cs('PARAMPCR') + struct.pack('<I', 1) + cs('MODE') + cs('CREATION')
    sec += cs('PROFONDEUR') + struct.pack('<I', 1) + cs('ZBOTTOM') + cs('0.003')
    return (b'\0' * 4 + b'\xff' * 4 + cs(name) + struct.pack('<3i', 7, 17, 7) + cs('CP_Cutting_3D')
            + b'\x01\x01\x00\x00\x00' + cs('TEMP') + b'\x01' + struct.pack('<I', 2) + sec)


def sample() -> bytes:
    # nom piège : « ext Ø3 … » (32 caractères) précédé d'une espace (0x20 = 32)
    tricky = '7-3  --  Déc ext Ø3 avant ébav -3Pz2/4p a0.05'
    return (b'\x0b\xcf\x00\x00' + folder('Datron', 2)
            + folder('2501 Process', 4) + preset('Trou Pz3.5') + folder('-' * 30, 0) + preset(tricky)
            + preset('Finit 30')
            + folder('Old', 2) + preset('Ancien') + folder('Sous', 1) + preset('Profond')
            + folder('Disponible', 1) + preset('Découpe'))


class TestTree(unittest.TestCase):
    def test_folders_and_names(self):
        ps = tpp.parse(sample())
        got = [(p.folder, p.name) for p in ps]
        self.assertEqual(got, [('Datron/2501 Process', 'Trou Pz3.5'),
                               ('Datron/2501 Process', '7-3  --  Déc ext Ø3 avant ébav -3Pz2/4p a0.05'),
                               ('Datron/2501 Process', 'Finit 30'),       # après le séparateur : même dossier
                               ('Datron/Old', 'Ancien'), ('Datron/Old/Sous', 'Profond'),
                               ('Disponible', 'Découpe')])


class TestPalette(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.env = mock.patch.dict(os.environ, {'VECTORDRIVE_CAM_TEMPLATES': self.tmp})
        self.env.start()
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.pal = self.w.cam_palette

    def tearDown(self):
        self.w.modified = False
        self.w.close()
        self.env.stop()

    def test_import_move_delete(self):
        from vectordrive.cam import templates as TPL
        f = pathlib.Path(self.tmp).parent / 'TypeEdit_V13' / 'CONFIG' / 'PathParam_Essai.TPP'
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(sample())
        with mock.patch.object(QMessageBox, 'information'):
            self.assertEqual(self.pal.import_typeedit([str(f)]), 6)
            self.assertEqual(self.pal.import_typeedit([str(f)]), 6)        # réimport : remplacé, pas doublé
        root = tpp.source_name(f)
        names = TPL.user_templates()
        self.assertEqual(len(names), 6)
        self.assertIn(f'{root}/Datron/Old/Sous', TPL.user_folders())
        # nouveau dossier, gardé vide
        self.assertEqual(self.pal.new_folder('', 'Atelier'), 'Atelier')
        self.assertIn('Atelier', TPL.user_folders())
        # glisser-déposer : un modèle et un dossier dans « Atelier »
        trou = f'{root}/Datron/2501 Process / Trou Pz3.5'
        self.pal.move_objects([('modele', trou), ('dossier', f'{root}/Datron/Old')], 'Atelier')
        after = TPL.user_templates()
        self.assertIn('Atelier / Trou Pz3.5', after)
        self.assertIn('Atelier/Old/Sous / Profond', after)
        self.assertEqual(self.pal.move_objects([('dossier', 'Atelier')], 'Atelier/Old'), 0)   # pas dans lui-même
        # dépôt sur le groupe « Modèles (dossiers) » : hors dossier
        g = next(self.pal.tree.topLevelItem(i) for i in range(self.pal.tree.topLevelItemCount())
                 if self.pal.tree.topLevelItem(i).data(0, 0x0100 + 4))
        self.assertEqual(self.pal.tree.target_folder(g), '')
        # renommer (F2), puis Suppr sur la sélection
        self.assertEqual(self.pal.rename_template('Atelier / Trou Pz3.5', 'Trou M4'), 'Atelier / Trou M4')
        self.pal._open_folders = {'Atelier'}
        self.pal.refresh()
        from PySide6.QtWidgets import QTreeWidgetItemIterator
        it = QTreeWidgetItemIterator(self.pal.tree)
        while it.value() is not None:
            v = it.value()
            if v.data(0, 0x0100 + 3) == 'Atelier':
                v.setSelected(True)
            it += 1
        self.assertEqual(self.pal.tree.moving(), [('dossier', 'Atelier')])
        n = self.pal.delete_selected(confirm=False)
        self.assertEqual(n, 3)                                                       # Trou M4, Ancien, Profond
        self.assertNotIn('Atelier', TPL.user_folders())


if __name__ == '__main__':
    unittest.main()
