"""Round 1158 (correctif d'essais) : les essais du démarrage de l'accrochage (round 986) ne dépendent plus de la graine
« accrochages non repris » laissée par les essais d'avant (round 1153)."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1158.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from tests import test_round986 as T  # noqa: E402


class SeedLost(unittest.TestCase):
    def test_start_tests_stand_alone(self):
        from vectordrive.portable import settings
        st = settings()
        st.remove('accrochage/retenir')                                     # la graine retirée par un essai d'avant
        st.setValue('accrochage/actif', True)                               # … et un état retenu, allumé
        st.sync()
        try:
            T.prefs(options__accrochage=False, options__accrochage_986='1')  # « actif au démarrage » décoché
            w = T.window()
            try:
                self.assertFalse(w.A['snap'].isChecked(),
                                 'avant : l’état retenu l’emportait, l’essai 986 échouait dans la suite entière')
            finally:
                T.close(w)
        finally:
            st = settings()
            st.setValue('accrochage/retenir', False)                        # la graine des essais, remise
            for k in ('accrochage/actif', 'accrochage/modes', 'accrochage/reperage', 'accrochage/polaire'):
                st.remove(k)
            st.sync()
            T.restore()


if __name__ == '__main__':
    unittest.main()
