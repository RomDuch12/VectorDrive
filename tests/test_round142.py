"""Round 142 : rectangle de sélection tiré du bas vers le haut (objets
touchés), cercles complets écrits en CIRCLE dans les DXF (trous pour
NeoDrive), logiciel encastré : ni l'écran d'accueil ni une fenêtre de
passage, reprise si la fenêtre logée disparaît, message si le logiciel a
passé la main à un exemplaire déjà ouvert."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import QPointF

from vectordrive.core import geom
from vectordrive.core.document import Document, Group, Shape
from vectordrive.core.geom import Contour, Line


def app():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


class TestCrossing(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app()

    def setUp(self):
        from vectordrive.ui.canvas import Canvas
        self.c = Canvas()
        self.c.resize(800, 600)
        d = Document()
        d.plate = None
        self.frame = Shape(path=geom.Path([geom.rect(0, 0, 100, 100)]))
        self.circle = Shape(path=geom.Path([geom.circle((50, 50), 5)]))
        self.line = Shape(path=geom.Path([Contour([Line((10, 80), (90, 80))], False)]))
        self.group = Group(children=[Shape(path=geom.Path([geom.rect(20, 20, 4, 4)])),
                                     Shape(path=geom.Path([geom.rect(70, 20, 4, 4)]))])
        self.filled = Shape(path=geom.Path([geom.rect(120, 0, 30, 30)]), filled=True)
        for it in (self.frame, self.circle, self.line, self.group, self.filled):
            d.add(it)
        self.c.set_document(d)
        self.c.fit() if hasattr(self.c, 'fit') else None

    def pts(self, x0, y0, x1, y1, upward):
        """Coins à l'écran d'un rectangle du document, tiré vers le haut ou vers le bas."""
        top, bottom = self.c.to_screen(x0, y1), self.c.to_screen(x1, y0)   # y du document vers le haut
        return (bottom, top) if upward else (top, bottom)

    def ids(self, items):
        return {id(i) for i in items}

    def test_window_only_inside(self):
        s, n = self.pts(40, 40, 60, 85, upward=False)                     # vers le bas : contenus seulement
        got = self.ids(self.c.band_items(s, n))
        self.assertEqual(got, {id(self.circle)})

    def test_crossing_touched(self):
        s, n = self.pts(40, 40, 60, 85, upward=True)                      # vers le haut : touchés aussi
        got = self.ids(self.c.band_items(s, n))
        self.assertIn(id(self.circle), got)
        self.assertIn(id(self.line), got)                                 # la ligne traverse le rectangle
        self.assertNotIn(id(self.frame), got)                             # cadre vide : son trait n'est pas touché
        self.assertNotIn(id(self.group), got)

    def test_group_taken_whole(self):
        s, n = self.pts(22, 10, 30, 30, upward=True)                      # touche un seul carré du groupe
        got = self.c.band_items(s, n)
        self.assertIn(id(self.group), self.ids(got))                      # l'ensemble entier
        self.assertNotIn(id(self.group.children[0]), self.ids(got))

    def test_frame_edge_and_filled(self):
        s, n = self.pts(95, 40, 105, 60, upward=True)                     # sur le bord droit du cadre
        self.assertIn(id(self.frame), self.ids(self.c.band_items(s, n)))
        s, n = self.pts(130, 10, 140, 20, upward=True)                    # dans un objet plein
        self.assertIn(id(self.filled), self.ids(self.c.band_items(s, n)))
        s, n = self.pts(130, 10, 140, 20, upward=False)
        self.assertNotIn(id(self.filled), self.ids(self.c.band_items(s, n)))

    def test_flag(self):
        from vectordrive.ui.canvas import Canvas
        self.assertTrue(Canvas.band_is_crossing({'start': QPointF(10, 100), 'now': QPointF(50, 20)}))
        self.assertFalse(Canvas.band_is_crossing({'start': QPointF(10, 20), 'now': QPointF(50, 100)}))

    def test_touches_rect_curves(self):
        from vectordrive.ui.canvas import touches_rect
        ring = Shape(path=geom.Path([geom.circle((0, 0), 10)]))
        self.assertTrue(touches_rect(ring, (9, -1, 12, 1)))               # coupe l'arc
        self.assertFalse(touches_rect(ring, (-2, -2, 2, 2)))              # dans le trou, sans toucher
        self.assertFalse(touches_rect(ring, (7.5, 7.5, 9, 9)))            # dans l'encombrement, hors du cercle


class TestDxfCircles(unittest.TestCase):
    def test_full_circle(self):
        from vectordrive.io import dxf
        c = geom.circle((12, 7), 2.5)
        (cx, cy), r = dxf.full_circle(c)
        self.assertAlmostEqual(cx, 12, places=9)
        self.assertAlmostEqual(cy, 7, places=9)
        self.assertAlmostEqual(r, 2.5, places=9)
        self.assertIsNotNone(dxf.full_circle(c.reversed()))
        self.assertIsNone(dxf.full_circle(geom.ellipse((0, 0), 5, 3)))
        self.assertIsNone(dxf.full_circle(Contour(geom.arc_conics((0, 0), 5, 5, 0, 180), False)))
        self.assertIsNone(dxf.full_circle(geom.rect(0, 0, 4, 4)))

    def test_written_as_circle(self):
        import ezdxf
        from vectordrive.io import dxf
        d = Document()
        for x in (10, 20, 30):
            d.add(Shape(path=geom.Path([geom.circle((x, 5), 1.65)])))      # trous M4 (avant-trou 3,3)
        d.add(Shape(path=geom.Path([geom.rect(0, 0, 40, 10)])))
        f = pathlib.Path(tempfile.mkdtemp()) / 'trous.dxf'
        dxf.write(d, f)
        msp = ezdxf.readfile(str(f)).modelspace()
        circles = list(msp.query('CIRCLE'))
        self.assertEqual(len(circles), 3)
        self.assertEqual(sorted(round(e.dxf.center.x, 9) for e in circles), [10, 20, 30])
        self.assertTrue(all(abs(e.dxf.radius - 1.65) < 1e-9 for e in circles))
        self.assertEqual(len(list(msp.query('LWPOLYLINE'))), 1)
        back = dxf.read(f)
        self.assertEqual(back.stats()['contours'], 4)


class FakeProc:
    def __init__(self, pid=123, running=True):
        self.pid, self.running = pid, running

    def processId(self):
        return self.pid

    def state(self):
        from PySide6.QtCore import QProcess
        return QProcess.ProcessState.Running if self.running else QProcess.ProcessState.NotRunning


class TestEmbed(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app()

    def setUp(self):
        from vectordrive.ui import embed
        self.embed = embed
        self.saved = (embed.top_windows, embed.child_pids, embed.pids_named, embed._win32)
        embed.child_pids = lambda pid: {pid}
        self.x = embed.ExternalApp('NeoDrive.exe', [], 'NeoDrive')
        self.x.proc = FakeProc()
        self.attached = []
        self.x.attach = lambda h: self.attached.append(h)

    def tearDown(self):
        e = self.embed
        e.top_windows, e.child_pids, e.pids_named, e._win32 = self.saved

    def test_transient_window_skipped(self):
        seq = [[(1, 'NeoDrive', 100)]] + [[(2, 'NeoDrive - Génère ton SimPl', 900)]] * 8
        calls = []

        def fake(pids, hint='', framed_only=False):
            calls.append(framed_only)
            return seq[min(len(calls) - 1, len(seq) - 1)]
        self.embed.top_windows = fake
        for _ in range(9):
            self.x._poll()
        self.assertEqual(self.attached, [2])                       # pas la fenêtre de passage
        self.assertTrue(all(calls))                                # d'abord les fenêtres à barre de titre

    def test_frameless_accepted_late(self):
        flags = []
        self.embed.top_windows = lambda pids, hint='', framed_only=False: (flags.append(framed_only), [])[1]
        self.x.waited = self.embed.FRAMELESS_AFTER_MS
        self.x._poll()
        self.assertEqual(flags, [False])

    def test_vanished_window_repolls(self):
        from PySide6.QtWidgets import QWidget

        class U32:
            @staticmethod
            def IsWindow(h):
                return 0

        class Win:
            user32 = U32

        class Ct:
            windll = Win
        self.embed._win32 = lambda: (Ct, None)
        self.x.hwnd, self.x.container = 7, QWidget()
        self.x._watch()
        self.assertIsNone(self.x.container)
        self.assertEqual(self.x.hwnd, 0)
        self.assertTrue(self.x.timer.isActive())
        self.x.timer.stop()

    def test_gone_message(self):
        import sys
        if sys.platform != 'win32':
            self.skipTest('Windows')
        self.embed.pids_named = lambda exe: {4242}
        self.embed.top_windows = lambda pids, hint='', framed_only=False: []
        msg = self.x.gone_message()
        self.assertIn('4242', msg)
        self.embed.top_windows = lambda pids, hint='', framed_only=False: [(9, 'NeoDrive', 1)]
        self.assertNotIn('4242', self.x.gone_message())
        self.embed.pids_named = lambda exe: set()
        self.assertTrue(self.x.gone_message())
        self.x.hwnd = 3
        self.assertIn('NeoDrive', self.x.gone_message())


if __name__ == '__main__':
    unittest.main()
