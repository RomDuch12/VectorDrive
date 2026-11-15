"""Round 903 : ruban. Le va-et-vient 2D / 3D n'est plus que dans la rangée des onglets ; sa moitié inactive a un fin
liseré de la couleur du mode en cours. Un seul onglet « CAD », dont le contenu suit le mode (dessin 2D, création 3D).
Plein écran sur F12 (Maj+F11 reste), repérage polaire sur Maj+F12."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r903.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtGui import QColor, QKeySequence, QPalette
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])


class Base(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from vectordrive.ui.main_window import MainWindow
        cls.w = MainWindow()
        cls.w.resize(1500, 900)
        cls.w.show()

    @classmethod
    def tearDownClass(cls):
        cls.w.modified = False
        cls.w.close()

    def setUp(self):
        self.w.set_view_mode('2d')

    def tearDown(self):
        self.w.set_view_mode('2d')

    def cad(self):
        r = self.w.ribbon
        out = {}
        for i in range(r.count()):
            p = r.page(i)
            if p is not None and p.property('vd_cad') and not r.widget(i).property('te_layout'):
                out[p.property('vd_cad')] = i
        return out

    def actions(self, i):
        return {id(b.defaultAction()) for g in self.w.ribbon.page(i).groups() for b in g.buttons()}


class Keys(Base):

    def test_f12_is_the_full_screen(self):
        A = self.w.A
        self.assertEqual([k.toString() for k in A['full_screen'].shortcuts()], ['F12', 'Shift+F11'])
        self.assertEqual(A['snap_polar'].shortcut(), QKeySequence('Shift+F12'))
        on_f12 = [k for k, a in A.items() if any(s == QKeySequence('F12') for s in a.shortcuts())]
        self.assertEqual(on_f12, ['full_screen'])
        self.assertIn('F12', A['full_screen'].toolTip())


class Switch(Base):

    def test_no_switch_in_the_ribbons(self):
        A, r = self.w.A, self.w.ribbon
        for i in range(r.count()):
            p = r.page(i)
            if p is None:
                continue
            acts = {id(b.defaultAction()) for g in p.groups() for b in g.buttons()}
            for k in ('view_toggle', 'view_2d', 'view_3d'):
                self.assertNotIn(id(A[k]), acts, (r.tabText(i), k))
        self.assertIs(r.view_button.defaultAction(), A['view_toggle'])
        self.assertTrue(r.view_button.isVisible())

    def test_a_thin_line_around_the_other_side(self):
        b = self.w.ribbon.view_button
        b.resize(b.sizeHint())
        hl = b.palette().color(QPalette.ColorRole.Highlight)

        def lit(x0, x1):
            img = b.grab().toImage()
            n = 0
            for x in range(x0, x1):
                for y in (2, 3, img.height() - 3, img.height() - 4):
                    c = QColor(img.pixel(x, y))
                    n += abs(c.red() - hl.red()) + abs(c.green() - hl.green()) + abs(c.blue() - hl.blue()) < 90
            return n
        half = b.width() // 2
        self.assertGreater(lit(half + 6, b.width() - 6), 10)           # en 2D : le liseré autour de « 3D »
        self.w.set_view_mode('3d')
        self.assertGreater(lit(6, half - 6), 10)                       # en 3D : autour de « 2D »


class Cad(Base):

    def test_one_cad_tab_following_the_mode(self):
        r = self.w.ribbon
        titles = [r.tabText(i) for i in range(r.count())]
        self.assertNotIn('3D', titles)
        self.assertNotIn('2.5D', titles)
        c = self.cad()
        self.assertEqual(set(c), {'2d', '3d'})
        self.assertEqual(c['3d'], c['2d'] + 1)                           # côte à côte : l'onglet ne saute pas
        self.assertEqual((r.tabText(c['2d']), r.tabText(c['3d'])), ('CAD', 'CAD'))
        self.assertTrue(r.isTabVisible(c['2d']))
        self.assertFalse(r.isTabVisible(c['3d']))
        A = self.w.A
        self.assertIn(id(A['tool_rect']), self.actions(c['2d']))
        self.assertIn(id(A['galbe']), self.actions(c['3d']))
        r.setCurrentIndex(c['2d'])
        self.w.set_view_mode('3d')
        self.assertFalse(r.isTabVisible(c['2d']))
        self.assertTrue(r.isTabVisible(c['3d']))
        self.assertEqual(r.currentIndex(), c['3d'])                      # CAD choisi : il le reste
        self.w.set_view_mode('2d')
        self.assertEqual(r.currentIndex(), c['2d'])
        self.assertFalse(r.isTabVisible(c['3d']))

    def test_another_tab_stays_chosen(self):
        r = self.w.ribbon
        vue = next(i for i in range(r.count()) if r.tabText(i) == 'Vue')
        r.setCurrentIndex(vue)
        self.w.set_view_mode('3d')
        self.assertEqual(r.currentIndex(), vue)
        self.assertTrue(r.isTabVisible(self.cad()['3d']))                # le CAD a changé de contenu sans être choisi
        self.w.set_view_mode('2d')
        self.assertEqual(r.currentIndex(), vue)
        self.assertTrue(r.isTabVisible(self.cad()['2d']))


if __name__ == '__main__':
    unittest.main()
