"""Round 1172 : deux essais anciens remis à jour — test_round993 quel que soit l'essai d'avant (réglage
`impression/couleurs` laissé), test_round644 avec les trajectoires montrées par l'œil."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1172.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])

BEFORE = 'avant : test_round993 échouait après un essai qui laissait impression/couleurs ; test_round644 échouait'


def run(name):
    suite = unittest.defaultTestLoader.loadTestsFromName(name)
    res = unittest.TestResult()
    suite.run(res)
    return res


class OldTests(unittest.TestCase):

    def test_993_after_a_test_that_left_the_colour_setting(self):
        from vectordrive import portable
        portable.settings().setValue('impression/couleurs', False)
        res = run('tests.test_round993.Window.test_first_time_from_f10')
        self.assertEqual(res.testsRun, 1)
        self.assertEqual((res.failures, res.errors), ([], []))

    def test_644_paths_shown_by_the_eye(self):
        res = run('tests.test_round644.TestView.test_all_setups')
        self.assertEqual(res.testsRun, 1)
        self.assertEqual((res.failures, res.errors), ([], []))


if __name__ == '__main__':
    unittest.main()
