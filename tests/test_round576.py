"""Round 576 : programmes appelés — plusieurs correspondances pour le même chemin machine (lecteur P: puis
partage réseau) : essayées dans l'ordre ; à l'écriture, chacune redonne le chemin machine."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.cam import ncpaths


class TestSeveral(unittest.TestCase):
    def test_order(self):
        a, b = pathlib.Path(tempfile.mkdtemp()), pathlib.Path(tempfile.mkdtemp())
        (b / 'Tranch').mkdir()
        (b / 'Tranch' / 'Date.simpl').write_text('x', encoding='utf-8')
        rules = ncpaths.mappings(f'network:T:\={a};network:T:\={b}')
        self.assertEqual(len(rules), 2)
        got = ncpaths.resolve(r'network:T:\Tranch\Date.simpl', rules=rules)
        self.assertEqual(pathlib.Path(got), b / 'Tranch' / 'Date.simpl')        # la seconde, la première absente
        self.assertEqual(ncpaths.to_machine(str(a / 'x.simpl'), rules), r'network:T:\x.simpl')
        self.assertEqual(ncpaths.to_machine(str(b / 'y.simpl'), rules), r'network:T:\y.simpl')


if __name__ == '__main__':
    unittest.main()
