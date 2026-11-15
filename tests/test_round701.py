"""Round 701 : hachures — motifs de DAO (familles de traits : ANSI31…,
BRICK, HONEY, EARTH, AR-CONC… d'après CADCraft) à l'échelle et à l'angle
choisis, fichiers .pat lus et gardés dans les hachures."""
import math
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import numpy as np

from vectordrive.core import geom
from vectordrive.core import hatch as HT
from vectordrive.core import hatch_patterns as HP


def square(w=40.0, h=40.0):
    return np.array(geom.rect(0, 0, w, h).flatten(0.01))


class TestPatterns(unittest.TestCase):
    def test_library(self):
        std = HP.standard()
        self.assertEqual(len(std), 22)
        self.assertAlmostEqual(std['ANSI31'].lines[0].delta[1], 0.125 * 25.4)       # ISO : pouces × 25,4
        self.assertAlmostEqual(std['AR-CONC'].lines[0].delta[0], 0.4 * 16 * 25.4)
        for p in std.values():
            self.assertTrue(p.lines and p.description)

    def test_lines_spacing_and_angle(self):
        segs, dots = HP.segments([square()], HP.standard()['LINE'].lines, scale=1.0)
        ys = sorted({round(a[1], 6) for a, b in segs})
        self.assertEqual(dots, [])
        self.assertTrue(all(abs(a[1] - b[1]) < 1e-9 for a, b in segs))              # horizontaux
        self.assertAlmostEqual(ys[1] - ys[0], 3.175)
        self.assertEqual(len(ys), 13)                                                # y = 0 (le bord) à 38,1
        segs, _d = HP.segments([square()], HP.standard()['LINE'].lines, scale=1.0, angle=90)
        self.assertTrue(all(abs(a[0] - b[0]) < 1e-9 for a, b in segs))              # tournés : verticaux

    def test_dashes_and_dots(self):
        segs, dots = HP.segments([square(20, 20)], HP.standard()['DOTS'].lines, scale=1.0)
        self.assertEqual(segs, [])
        self.assertGreater(len(dots), 100)
        self.assertTrue(all(0 <= x <= 20 and 0 <= y <= 20 for x, y in dots))
        segs, _d = HP.segments([square()], HP.standard()['DASH'].lines, scale=1.0)
        self.assertTrue(all(math.dist(a, b) <= 3.175 + 1e-6 for a, b in segs))     # tirets de 1/8 de pouce

    def test_holes_stay_empty(self):
        hole = np.array(geom.rect(10, 10, 20, 20).flatten(0.01))
        segs, _d = HP.segments([square(), hole], HP.standard()['ANSI31'].lines, scale=0.5)
        mids = [((a[0] + b[0]) / 2, (a[1] + b[1]) / 2) for a, b in segs]
        self.assertFalse(any(10.5 < x < 29.5 and 10.5 < y < 29.5 for x, y in mids))  # pair-impair

    def test_bounded(self):
        segs, dots = HP.segments([square(1000, 1000)], HP.standard()['LINE'].lines, scale=1e-4)
        self.assertEqual((segs, dots), ([], []))                                    # trop de traits : rien

    def test_parse_pat(self):
        text = ('*MINE, Mon motif ; commentaire\n45, 0,0, 0,3\n90, 0,0, 0,3, 2,-1\n'
                '*BAD\n0,0,0,0,0\n*mine,encore\n0,0,0,0,1\n*VIDE\n0,0\n')
        items, warnings = HP.parse_pat(text)
        self.assertEqual([p.name for p in items], ['MINE'])
        self.assertEqual(items[0].lines[1].dashes, [2.0, -1.0])
        joined = '\n'.join(warnings)
        for part in ('BAD', 'deux fois', 'VIDE'):
            self.assertIn(part, joined)


class TestHatchSpec(unittest.TestCase):
    def test_cad_pattern_hatch(self):
        src = geom.Path([geom.rect(0, 0, 40, 40)])
        p = HT.hatch_path(src, HT.HatchSpec(pattern='pat:ANSI37', scale=0.5, angle=0.0))
        self.assertGreater(len(p.contours), 20)
        user = HT.HatchSpec(pattern='pat:MINE', pat=[[0, 0, 0, 0, 2]], angle=0.0)
        lines = HT.hatch_path(src, user)
        self.assertEqual(len(lines.contours), 20)                                    # gardé dans les réglages
        again = HT.HatchSpec.from_dict(user.to_dict())
        self.assertEqual(again.pat, [[0, 0, 0, 0, 2]])
        dots = HT.hatch_path(src, HT.HatchSpec(pattern='pat:DOTS', dot=0.3, angle=0.0))
        self.assertTrue(all(c.closed for c in dots.contours))                       # points en cercles
        self.assertEqual(len(HT.hatch_path(src, HT.HatchSpec(pattern='pat:DOTS', dot=0, angle=0.0)).contours), 0)

    def test_old_settings_still_read(self):
        spec = HT.HatchSpec.from_dict({'spacing': 1.0, 'angle': 30.0, 'pattern': 'briques'})
        self.assertEqual((spec.scale, spec.pat), (1.0, []))
        self.assertTrue(HT.hatch_path(geom.Path([geom.rect(0, 0, 10, 10)]), spec).contours)


class TestWindow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])
        from vectordrive.ui.main_window import MainWindow
        cls.w = MainWindow()

    @classmethod
    def tearDownClass(cls):
        cls.w.settings.remove(cls.w.HATCH_PAT_KEY)
        cls.w.modified = False
        cls.w.close()

    def test_import_and_dialog(self):
        from vectordrive.ui import dialogs
        w = self.w
        w.settings.remove(w.HATCH_PAT_KEY)
        pat = os.path.join(tempfile.mkdtemp(), 'perso.pat')
        with open(pat, 'w', encoding='cp1252') as f:
            f.write('*RAYURES,Rayures é\n0, 0,0, 0,2\n*ANSI31,doublon du standard\n45,0,0,0,1\n')
        new = w.import_hatch_patterns(pat)
        self.assertEqual([p.name for p in new], ['RAYURES'])                        # le standard n'est pas remplacé
        self.assertEqual([p.name for p in w.hatch_user_patterns()], ['RAYURES'])
        seen = {}

        def fake_exec(dlg):
            box = dlg.fields['pattern']
            seen['values'] = [box.itemData(i) for i in range(box.count())]
            box.setCurrentIndex(box.findData('pat:RAYURES'))
            seen['angle'] = dlg.fields['angle'].value()                             # motif de DAO : angle 0
            return 1
        with mock.patch.object(dialogs.ParamsDialog, 'exec', fake_exec):
            spec = w._hatch_dialog(HT.HatchSpec())
        self.assertIn('pat:ANSI31', seen['values'])
        self.assertIn('lignes', seen['values'])
        self.assertEqual(seen['angle'], 0.0)
        self.assertEqual((spec.pattern, spec.pat), ('pat:RAYURES', [[0.0, 0.0, 0.0, 0.0, 2.0]]))

        def keep_exec(dlg):
            seen['kept'] = dlg.fields['pattern'].currentData()
            return 1
        w.settings.remove(w.HATCH_PAT_KEY)                                         # fichier oublié : le groupe garde
        with mock.patch.object(dialogs.ParamsDialog, 'exec', keep_exec):        # son motif
            again = w._hatch_dialog(spec)
        self.assertEqual(seen['kept'], 'pat:RAYURES')
        self.assertEqual(again.pat, [[0.0, 0.0, 0.0, 0.0, 2.0]])

        def std_exec(dlg):
            dlg.fields['pattern'].setCurrentIndex(dlg.fields['pattern'].findData('pat:BRICK'))
            return 1
        with mock.patch.object(dialogs.ParamsDialog, 'exec', std_exec):
            std = w._hatch_dialog(again)
        self.assertEqual((std.pattern, std.pat), ('pat:BRICK', []))


if __name__ == '__main__':
    unittest.main()
