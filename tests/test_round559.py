"""Round 559 : recherche dans les textes — fichiers pas encore lus préparés d'avance, sur plusieurs
processus quand ils sont nombreux (premier passage sur tout un disque : 142 s → 33 s)."""
import os
import pathlib
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.core import text as TX
from vectordrive.core.document import Text
from vectordrive.io import smb
from vectordrive.ui import file_browser as FB


class TestFill(unittest.TestCase):
    def test_fill_and_search(self):
        d = pathlib.Path(tempfile.mkdtemp())
        for i in range(5):
            t = Text(text=f'REF {i} CLIENT', font='Arial', size=5.0)
            t.outline = TX.outline_for(t)
            smb.write([t], d / f's{i}.smb', live_texts=True)
        idx = smb.TextIndex(d / 'i.json')
        files = sorted(d.glob('*.smb'))
        self.assertEqual(len(idx.missing(files)), 5)
        from vectordrive.core import workers
        with mock.patch.object(workers, 'adaptive_map', wraps=workers.adaptive_map) as am:
            self.assertEqual(idx.fill(files), 5)
            self.assertEqual(am.call_count, 1)                                 # en une fois
        self.assertEqual(idx.missing(files), [])
        self.assertEqual(idx.fill(files), 0)
        found, hits = [], {}
        FB.search_texts(d, ('.smb',), FB.matcher('ref 3'), idx, 100, found, hits)
        self.assertEqual([f.name for f in found], ['s3.smb'])
        self.assertEqual(hits[str(d / 's3.smb')], 'REF 3 CLIENT')

    def test_file_texts_bad(self):
        f = pathlib.Path(tempfile.mkdtemp()) / 'x.vnd'
        f.write_bytes(b'pas un vnd')
        self.assertEqual(smb.file_texts(str(f)), [])


if __name__ == '__main__':
    unittest.main()
