"""Round 125 : thème « TypeEdit 13 » — couleurs du script de ruban de la
V13 et de son écran (relevées sur TypeEdit V13 lancé au poste) ; remplace
l'ancien « TypeEdit classique (bleu) »."""
import os
import pathlib
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))
os.environ.setdefault('VECTORDRIVE_THEMES', os.path.join(tempfile.mkdtemp(), 'themes'))

from vectordrive.ui import themes as T

V13_SCRIPT = """' script de ruban (extrait synthétique, mêmes instructions que la V13)
visualManager.SetColorRibbonBarBackgroundFromRGB 188,199,216
visualManager.SetColorRibbonPanelCaptionTopHighlightFromRGB 90,131,183
visualManager.SetColorRibbonPanelCaptionTopNoHighlightFromRGB 241,182,42
visualManager.SetColorRibbonPanelCaptionBottomNoHighlightFromRGB 246,229,189
visualManager.SetColorRulerTopFromRGB 226,232,240
visualManager.SetColorRulerTextFromRGB 0,0,0
visualManager.SetFontName "Segoe UI"
"""


class FakeSettings:
    def __init__(self, **kw):
        self.d = kw

    def value(self, k, default=None):
        return self.d.get(k, default)


class TestTypeEdit13(unittest.TestCase):
    def test_builtin_counts_unchanged(self):
        self.assertEqual((len(T.BUILTIN), len(T.LIGHT_KEYS), len(T.DARK_KEYS)), (30, 5, 25))
        self.assertIn('typeedit13', T.LIGHT_KEYS)
        self.assertNotIn('typeedit_classique', T.BUILTIN)

    def test_colours_as_on_screen(self):
        t = T.BUILTIN['typeedit13']
        self.assertEqual(t.name, 'TypeEdit 13')
        self.assertEqual(t.colors['ribbon'], '#bcc7d8')
        self.assertEqual(t.colors['main'], '#bcc7d8')
        self.assertEqual(t.colors['caption'], '#5a83b7')            # bandeaux bleus, pas orangés
        self.assertEqual(t.colors['caption_text'], '#ffffff')
        self.assertEqual(t.colors['tab_selected'], '#5a83b7')
        self.assertEqual(t.colors['panel_title'], '#5a83b7')
        self.assertEqual(t.colors['highlight'], '#669731')
        self.assertEqual((t.canvas['ruler'], t.canvas['ruler_text']), ('#e2e8f0', '#000000'))
        self.assertEqual((t.canvas['plate'], t.canvas['plate_edge']), ('#ffffff', '#000000'))
        self.assertEqual(t.canvas['page'], '#ffffff')
        self.assertEqual(t.font, 'Segoe UI')
        self.assertFalse(t.dark)
        self.assertGreaterEqual(T.contrast(t.colors['caption_text'], t.colors['caption']), 3)

    def test_from_a_v13_script(self):
        vals = T.parse_ribbon_script(V13_SCRIPT)
        self.assertEqual(vals['RibbonPanelCaptionTopNoHighlight'], '#f1b62a')
        t = T.typeedit13_theme(vals)
        self.assertEqual(t.colors['caption'], '#5a83b7')
        self.assertEqual(t.colors['ribbon'], '#bcc7d8')

    def test_version_of_install(self):
        self.assertEqual(T.typeedit_version('C:/TypeEdit_V13-LaserType_V13/res/RIBBON/x.txt'), 13)
        self.assertEqual(T.typeedit_version(r'C:\ProgramData\Gravotech\TypeEdit_V15-LaserType_V15\res'), 15)
        self.assertEqual(T.typeedit_version('ailleurs'), 0)

    def test_scripts_sorted_by_version(self):
        pd = pathlib.Path(tempfile.mkdtemp())
        for v in (13, 15):
            d = pd / 'Gravotech' / f'TypeEdit_V{v}-LaserType_V{v}' / 'res' / 'RIBBON'
            d.mkdir(parents=True)
            (d / 'ScriptRibbonUI_TE.txt').write_text(V13_SCRIPT, encoding='utf-16')
        with mock.patch.dict(os.environ, {'PROGRAMDATA': str(pd)}):
            files = T.ribbon_script_files()
            versions = [T.typeedit_version(f) for f in files]
            self.assertEqual(versions, sorted(versions, reverse=True))
            self.assertTrue(all(T.typeedit_version(f) == 13 for f in T.ribbon_script_files(13)))
            self.assertTrue(T.ribbon_script_files(13))

    def test_old_setting_still_works(self):
        self.assertEqual(T.get('typeedit_classique').key, 'typeedit13')
        self.assertEqual(T.chosen_key(FakeSettings(**{'vue/theme': 'typeedit_classique'})), 'typeedit13')


if __name__ == '__main__':
    unittest.main()
