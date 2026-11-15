"""Round 571 : recherche de la bibliothèque — tous ses formats par le nom (DXF, VDZ, VND, SVG), SMB et VND
par leurs textes TypeEdit, lecture préparée en une fois."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.core import text as TX
from vectordrive.core.document import Text
from vectordrive.io import smb


class TestLibrarySearch(unittest.TestCase):
    def test_all_formats(self):
        d = pathlib.Path(tempfile.mkdtemp())
        (d / 'logo client.dxf').write_text('0\nEOF\n', encoding='ascii')
        (d / 'logo.svg').write_text('<svg/>', encoding='ascii')
        t = Text(text='CLIENT MARTIN', font='Arial', size=5.0)
        t.outline = TX.outline_for(t)
        smb.write([t], d / 'plaque.smb', live_texts=True)
        idx = smb.TextIndex(d / 'i.json')
        exts = ('.smb', '.dxf', '.vdz', '.vnd', '.svg')
        found = smb.search([d], 'logo', idx, exts=exts)
        self.assertEqual(sorted(f.name for f, _t in found), ['logo client.dxf', 'logo.svg'])
        found = smb.search([d], 'martin', idx, exts=exts)
        self.assertEqual([(f.name, h) for f, h in found], [('plaque.smb', 'CLIENT MARTIN')])
        self.assertEqual(smb.search([d], 'logo', idx), [])                    # symboles seuls par défaut


if __name__ == '__main__':
    unittest.main()
