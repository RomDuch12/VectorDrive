"""Round 925 : TypeEdit installé, le cœur ne lit pas ses polices (round 924 : seulement par un plugin) ; un symbole de
TypeEdit écrit dans une de ces polices s'ouvre, ses textes gardés, la police signalée absente."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_CACHE', tempfile.mkdtemp())

from vectordrive.core import fonts
from vectordrive.core.document import Text
from tests.corpus import corpus

FONT_DIRS = sorted(pathlib.Path('C:/ProgramData/Gravotech').glob('*/FONTS'))
EXT = ('.vnf', '.chr')


class TypeEditInstalled(unittest.TestCase):

    def setUp(self):
        if not FONT_DIRS:
            self.skipTest('TypeEdit absent du poste')
        try:
            from vectordrive.core import fontformats
        except ImportError:                      # cœur d'avant le round 924 : il les lit lui-même
            return
        if any(fontformats.of(f'x{e}') for e in EXT):
            self.skipTest('un plugin lit les polices de TypeEdit')

    def test_installed_fonts_not_read(self):
        self.assertTrue(any(f.suffix.lower() in EXT for d in FONT_DIRS for f in d.rglob('*')))
        self.assertFalse(set(FONT_DIRS) & set(fonts.FONT_DIRS))
        fonts.refresh()
        self.assertFalse([v[0] for v in fonts.families().values() if v[0].lower().endswith(EXT)])

    def test_symbol_in_a_typeedit_font_opens_with_the_font_reported(self):
        from vectordrive.io import registry
        p = corpus('smb_cote_laterale')
        if not p.exists():
            self.skipTest('symbole absent du corpus')
        d = registry.open_document(p)
        self.assertTrue([t for t in d.iter_leaves() if isinstance(t, Text)])
        self.assertTrue([r for r in d.report if 'absente du poste' in r], d.report)
        self.assertEqual([r for r in d.report if 'absente du poste' not in r], [])


if __name__ == '__main__':
    unittest.main()
