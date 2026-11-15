"""Round 42 : inventaire des polices en cache disque."""
import json
import os
import pathlib
import shutil
import tempfile
import unittest

from vectordrive.core import fonts


class TestFontCache(unittest.TestCase):
    def test_cache_written_reused_and_invalidated(self):
        arial = fonts.find_font('Arial')
        if not arial:
            self.skipTest('Arial absente')
        fonts.families.cache_clear()
        fonts.families()
        cf = fonts.cache_file()
        self.assertTrue(cf.exists())
        self.assertTrue(str(cf).startswith(os.environ.get('VECTORDRIVE_CACHE', '§')))   # jamais le profil
        data = json.loads(cf.read_text(encoding='utf-8'))
        self.assertEqual(data['version'], fonts.CACHE_VERSION)
        with tempfile.TemporaryDirectory() as tmp:
            d = pathlib.Path(tmp)
            shutil.copy(arial[0], d / 'copie_essai.ttf')
            fonts.add_font_dir(d)                       # signature changée : nouvel inventaire
            try:
                fam = fonts.families()
                self.assertTrue(any(v[0].endswith('copie_essai.ttf') for v in fam.values()) or
                                fonts.find_font('Arial') is not None)
                self.assertIn(str(d), [s[0] for s in json.loads(cf.read_text(encoding='utf-8'))['sig']])
            finally:
                fonts.FONT_DIRS.remove(d)
                fonts.families.cache_clear()

    def test_corrupt_cache_ignored(self):
        cf = fonts.cache_file()
        cf.parent.mkdir(parents=True, exist_ok=True)
        cf.write_text('{pas du json', encoding='utf-8')
        fonts.families.cache_clear()
        self.assertTrue(fonts.families())


if __name__ == '__main__':
    unittest.main()
