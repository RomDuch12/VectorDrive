"""Round 543 : programmes appelés par un programme machine — chemin vu de la machine converti en chemin
du poste (F10 › FAO › Programmes appelés), valeur par défaut d'une option fournie par un plugin."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive import plugins
from vectordrive.cam import ncpaths


class TestProgramPaths(unittest.TestCase):
    def test_mappings(self):
        rules = ncpaths.mappings(r'network:T:\=\\serveur\partage\Programmes ; X:/=D:/copie;rien')
        self.assertEqual(rules, [('network:T:', r'\\serveur\partage\Programmes'), ('X:', r'D:\copie')])
        c = ncpaths.candidates(r'network:T:\\Clients\\A.SimPl', rules=rules)
        self.assertEqual(c[0], r'\\serveur\partage\Programmes\Clients\A.SimPl')
        self.assertEqual(c[1], r'network:T:\Clients\A.SimPl')
        c = ncpaths.candidates(r'NETWORK:t:\B.simpl', caller=r'C:\progs\main.simpl', rules=rules)
        self.assertEqual(c[0], r'\\serveur\partage\Programmes\B.simpl')    # casse de Windows ignorée
        self.assertIn(str(pathlib.Path(r'C:\progs') / 'B.simpl'), c)          # à côté de l'appelant (puis parents, r555)

    def test_resolve(self):
        d = pathlib.Path(tempfile.mkdtemp())
        (d / 'local').mkdir()
        (d / 'local' / 'sous.SimPl').write_text('x', encoding='utf-8')
        (d / 'voisin.SimPl').write_text('x', encoding='utf-8')
        rules = [('network:T:', str(d / 'local'))]
        self.assertEqual(ncpaths.resolve(r'network:T:\sous.SimPl', rules=rules), str(d / 'local') + r'\sous.SimPl')
        self.assertEqual(ncpaths.resolve(r'network:T:\voisin.SimPl', caller=str(d / 'main.SimPl'), rules=rules),
                         str(d / 'voisin.SimPl'))
        self.assertIsNone(ncpaths.resolve(r'network:T:\absent.SimPl', caller=str(d / 'main.SimPl'), rules=rules))

    def test_plugin_default(self):
        from PySide6.QtCore import QSettings
        from vectordrive.ui import options
        s = QSettings(os.path.join(tempfile.mkdtemp(), 'o.ini'), QSettings.Format.IniFormat)
        self.assertEqual(options.value(s, ncpaths.KEY), '')
        plugins.REGISTRY.defaults.setdefault('options', {})[ncpaths.KEY] = 'M:=L:'
        try:
            self.assertEqual(options.value(s, ncpaths.KEY), 'M:=L:')
            s.setValue(ncpaths.KEY, 'A:=B:')                              # le réglage du poste l'emporte
            self.assertEqual(options.value(s, ncpaths.KEY), 'A:=B:')
        finally:
            plugins.REGISTRY.defaults['options'].pop(ncpaths.KEY, None)


if __name__ == '__main__':
    unittest.main()
