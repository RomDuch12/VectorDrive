"""Round 530 : vue 3D en rendu logiciel — pas d'anticrénelage (chaque échantillon coûte au processeur)."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive import portable
from vectordrive.ui import view3d


class TestSoftwareSamples(unittest.TestCase):
    def test_software_no_msaa(self):
        st = portable.settings()
        try:
            st.setValue('vue3d/anticrenelage', '8')
            st.setValue('affichage/gpu', 'performance')
            self.assertEqual(view3d.samples(), 8)
            st.setValue('affichage/gpu', 'logiciel')
            self.assertEqual(view3d.samples(), 0)
        finally:
            st.remove('affichage/gpu')
            st.remove('vue3d/anticrenelage')


if __name__ == '__main__':
    unittest.main()
