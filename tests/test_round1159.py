"""Round 1159 (consolidation des essais) : l'état de départ des essais ne dépend plus de leur ordre — graine des
réglages remise entre deux classes, essai des options qui rend l'accrochage éteint, variables d'environnement des
essais 887, 1117 et 1118 posées par setUpModule et plus à l'import."""
import io
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1159.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

import tests  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])
STATE = ('accrochage/actif', 'accrochage/modes', 'accrochage/reperage', 'accrochage/polaire')


def settings():
    from vectordrive.portable import settings as st
    return st()


def spoil():
    """Ce qu'un essai peut laisser : plus de graine, un état d'accrochage retenu, l'option d'accrochage retirée."""
    st = settings()
    st.remove('accrochage/retenir')
    st.remove('options/accrochage')
    st.setValue('accrochage/actif', True)
    st.setValue('accrochage/modes', 'nearest')
    st.sync()


def text(v) -> str:
    """QSettings rend un booléen dans le processus qui l'a écrit, un texte une fois relu du fichier."""
    return str(v).lower()


def seeded(st) -> dict:
    return {'retenir': text(st.value('accrochage/retenir')), 'accrochage': text(st.value('options/accrochage')),
            'etat': [k for k in STATE if st.contains(k)]}


GOOD = {'retenir': 'false', 'accrochage': 'false', 'etat': []}


class Reseed(unittest.TestCase):
    def tearDown(self):
        tests.seed_settings(os.environ['VECTORDRIVE_SETTINGS'])
        st = settings()
        st.setValue('accrochage/retenir', False)
        st.setValue('options/accrochage', False)
        for k in STATE:
            st.remove(k)
        st.sync()

    def test_reseed_puts_the_seed_back(self):
        spoil()
        tests.reseed()
        self.assertEqual(seeded(settings()), GOOD)

    def test_reseed_turns_a_left_snap_option_off(self):
        st = settings()
        st.setValue('options/accrochage', True)                              # laissé allumé par une classe d'avant
        st.sync()
        tests.reseed()
        self.assertEqual(text(settings().value('options/accrochage')), 'false')

    def test_reseed_does_not_rewrite_a_clean_file(self):
        tests.reseed()
        path = os.environ['VECTORDRIVE_SETTINGS']
        before = os.stat(path).st_mtime_ns
        os.utime(path, ns=(before - 10 ** 9, before - 10 ** 9))             # une seconde plus tôt : réécrit = vu
        tests.reseed()
        self.assertEqual(os.stat(path).st_mtime_ns, before - 10 ** 9, 'fichier déjà conforme : pas réécrit')

    def test_between_two_classes(self):
        seen = {}

        class First(unittest.TestCase):
            def test_spoils(self):
                spoil()

        class Second(unittest.TestCase):
            def test_starts_clean(self):
                seen.update(seeded(settings()))

        suite = unittest.TestSuite([First('test_spoils'), Second('test_starts_clean')])
        result = unittest.TextTestRunner(stream=io.StringIO()).run(suite)
        self.assertTrue(result.wasSuccessful())
        self.assertEqual(seen, GOOD, 'la seconde classe part de la graine, quoi qu’ait laissé la première')

    def test_no_reseed_inside_a_class(self):
        seen = {}

        class Same(unittest.TestCase):
            def test_a_sets(self):
                st = settings()
                st.setValue('accrochage/actif', True)
                st.sync()

            def test_b_reads(self):
                seen['etat'] = settings().contains('accrochage/actif')

        suite = unittest.TestSuite([Same('test_a_sets'), Same('test_b_reads')])
        unittest.TextTestRunner(stream=io.StringIO()).run(suite)
        self.assertTrue(seen['etat'], 'dans une même classe, rien n’est touché entre deux essais')


class OptionsTest(unittest.TestCase):
    def test_104_leaves_the_snap_off(self):
        from tests import test_round104 as T
        st = settings()
        st.setValue('accrochage/actif', True)
        st.sync()
        t = T.TestOptions('test_every_option_has_a_widget_and_roundtrips')
        t.setUp()
        t.tearDown()
        st = settings()
        self.assertEqual(text(st.value('options/accrochage')), 'false')
        self.assertFalse(st.contains('accrochage/actif'))


class ModuleEnvironment(unittest.TestCase):
    KEYS = ('VECTORDRIVE_SETTINGS', 'VECTORDRIVE_SESSION', 'VECTORDRIVE_CACHE')

    def check(self, name):
        import importlib
        before = {k: os.environ.get(k) for k in self.KEYS}
        T = importlib.import_module('tests.' + name)
        self.assertEqual({k: os.environ.get(k) for k in self.KEYS}, before, 'l’import ne change pas l’environnement')
        self.assertTrue(hasattr(T, '_ENV'), 'variables posées par setUpModule')
        T.setUpModule()
        try:
            self.assertEqual({k: os.environ.get(k) for k in self.KEYS}, T._ENV)
            self.assertTrue(os.path.isdir(T._TMP))
        finally:
            T.tearDownModule()
        self.assertEqual({k: os.environ.get(k) for k in self.KEYS}, before, 'tearDownModule rend l’environnement')

    def test_887(self):
        self.check('test_round887')

    def test_1117(self):
        self.check('test_round1117')

    def test_1118(self):
        self.check('test_round1118')


if __name__ == '__main__':
    unittest.main()
