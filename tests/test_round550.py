"""Round 550 : appel d'un programme en FAO — fichier choisi sur le poste (« … »), écrit en chemin de la
machine par les correspondances de F10 › FAO › Programmes appelés (comme NeoDrive)."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication, QLineEdit

from vectordrive.cam import ncpaths
from vectordrive.cam.instructions import INSTRUCTIONS

RULES = [('network:T:', r'\\diskstation\partage\Programme Datron')]


class TestToMachine(unittest.TestCase):
    def test_convert(self):
        self.assertEqual(ncpaths.to_machine(r'\\DiskStation\partage\Programme Datron\Clients\a.SimPl', RULES),
                         r'network:T:\Clients\a.SimPl')
        self.assertEqual(ncpaths.to_machine('//diskstation/partage/Programme Datron/b.simpl', RULES),
                         r'network:T:\b.simpl')                              # séparateurs du sélecteur
        self.assertEqual(ncpaths.to_machine(r'C:\x\c.simpl', RULES), r'C:\x\c.simpl')
        self.assertEqual(ncpaths.to_machine(r'\\diskstation\partage\Programme DatronX\d.simpl', RULES),
                         r'\\diskstation\partage\Programme DatronX\d.simpl')  # pas un autre dossier
        self.assertEqual(ncpaths.to_machine(r'network:T:\e.simpl', RULES), r'network:T:\e.simpl')

    def test_both_ways(self):
        local = r'\\diskstation\partage\Programme Datron\Clients\a.SimPl'
        machine = ncpaths.to_machine(local, RULES)
        self.assertEqual(ncpaths.candidates(machine, rules=RULES)[0], local)


class TestForm(unittest.TestCase):
    def test_file_field(self):
        ins = INSTRUCTIONS['appel_programme']
        self.assertEqual([f[2] for f in ins.fields if f[0] == 'path'], ['file'])

    def test_browse(self):
        app = QApplication.instance() or QApplication([])                  # noqa: F841
        from vectordrive.ui import cam_panel
        e = QLineEdit()
        holder = type('P', (), {})()
        with mock.patch('PySide6.QtWidgets.QFileDialog.getOpenFileName',
                        return_value=('D:/progs/sous.SimPl', '')):
            cam_panel.OperationDialog._browse_param_file(holder, e) if hasattr(cam_panel, 'OperationDialog') \
                else self._browse_any(cam_panel, holder, e)
        self.assertEqual(e.text(), r'D:\progs\sous.SimPl')

    def _browse_any(self, mod, holder, e):
        cls = next(c for c in vars(mod).values() if isinstance(c, type) and hasattr(c, '_browse_param_file'))
        cls._browse_param_file(holder, e)


if __name__ == '__main__':
    unittest.main()
