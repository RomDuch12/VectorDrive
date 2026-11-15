"""Round 867 : les textes vivants que TypeEdit 13 ne reconnaîtrait pas partent en courbes."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', os.path.join(tempfile.mkdtemp(), 'session'))
os.environ.setdefault('VECTORDRIVE_NO_TYPEEDIT', '1')

from vectordrive.core import fonts as F
from vectordrive.core.document import Text
from vectordrive.io.vnd_write import _LiveTexts


class FakeFont(dict):
    pass


def allowed(name, variable=False, known=True):
    font = FakeFont({'fvar': 1} if variable else {})
    with mock.patch.object(F, 'is_available', return_value=known), \
            mock.patch.object(F, 'find_font', return_value=('x.ttf', 0)), \
            mock.patch.object(F, 'installed', return_value=known), \
            mock.patch.object(F, 'load', return_value=font):     # round 988 : installée dans Windows
        return _LiveTexts.allowed(Text(text='A', font=name, size=10.0))


class TestLiveTexts(unittest.TestCase):

    def test_a_display_name_stays_alive(self):
        self.assertTrue(allowed('Arial Narrow'))

    def test_a_one_word_display_name_stays_alive(self):
        self.assertTrue(allowed('Arial'))

    def test_a_missing_font_is_written_in_curves(self):
        self.assertFalse(allowed('Arial', known=False))

    def test_a_variable_font_is_written_in_curves(self):
        self.assertFalse(allowed('Bahnschrift', variable=True))

    def test_an_internal_key_is_written_in_curves(self):
        self.assertFalse(allowed('arialnarrow'))

    def test_an_engraving_font_with_such_a_name_stays_alive(self):
        with mock.patch.dict(F.PLUGIN_FONTS, {'trait1': 'x.essai'}):
            self.assertTrue(allowed('trait1'))


class TestVariable(unittest.TestCase):

    def test_a_font_without_axes(self):
        with mock.patch.object(F, 'find_font', return_value=('x.ttf', 0)), mock.patch.object(F, 'load', return_value=FakeFont()):
            self.assertFalse(F.is_variable('X'))

    def test_a_font_with_axes(self):
        with mock.patch.object(F, 'find_font', return_value=('x.ttf', 0)), mock.patch.object(F, 'load', return_value=FakeFont(fvar=1)):
            self.assertTrue(F.is_variable('X'))

    def test_no_font(self):
        with mock.patch.object(F, 'find_font', return_value=None):
            self.assertFalse(F.is_variable('X'))

    def test_an_unreadable_font(self):
        with mock.patch.object(F, 'find_font', return_value=('x.ttf', 0)), mock.patch.object(F, 'load', side_effect=OSError):
            self.assertFalse(F.is_variable('X'))


if __name__ == '__main__':
    unittest.main()
