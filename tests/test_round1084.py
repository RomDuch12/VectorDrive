"""Round 1084 (demandes du 18/11 soir) : « emporte-pièce on définit un coutour qui devient pointeur souris (mémoire du
dernier) et un click retire ce qui s'y trouve à l'intérieur (opé soustraction) fonctionne contours ouverts et fermés
(conserve respectivement des contours ouverts et fermés) » ; « outils poincons et couteaux : la 1 ere forme
sélectionnée devient le pointeur souri et le reste tant que click gauche puis click droit retire l'outil »."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1084.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication  # noqa: E402

from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Shape  # noqa: E402
from vectordrive.core.geom import Path  # noqa: E402

app = QApplication.instance() or QApplication([])
BEFORE = 'avant : l\'emporte-pièce ne prenait qu\'un segment, un rectangle ou un cercle'


def length(cs):
    return sum(float(s.length()) for c in cs for s in (c.close() if c.closed else c).segments)


class Core(unittest.TestCase):

    def setUp(self):
        from vectordrive.core import punchtool as PT
        self.PT = PT
        self.assertTrue(hasattr(PT, 'stamp_of'), BEFORE)

    def test_the_stamp_is_centred(self):
        PT = self.PT
        st = PT.stamp_of(Path([geom.rect(10, 20, 6, 4)]))
        self.assertEqual(tuple(round(v, 9) for v in st.bbox()), (-3.0, -2.0, 3.0, 2.0))
        b = PT.place(st, (50, 50)).bbox()
        self.assertEqual(tuple(round(v, 9) for v in b), (47.0, 48.0, 53.0, 52.0))
        b = PT.place(st, (0, 0), 90.0).bbox()
        self.assertAlmostEqual(b[2] - b[0], 4.0, places=6)                  # tournée
        self.assertIsNone(PT.stamp_of(Path([geom.polyline([(0, 0), (5, 0)])])))   # un trait : pas d'emporte-pièce
        self.assertIsNotNone(PT.stamp_of(Path([geom.polyline([(0, 0), (5, 0)])]), closed_only=False))  # couteau : si
        self.assertIn('forme', PT.KINDS)

    def test_open_stays_open_closed_stays_closed(self):
        PT = self.PT
        cutter = PT.place(PT.stamp_of(Path([geom.rect(0, 0, 10, 10)])), (20, 0))       # carré 15..25 × -5..5
        line = Path([geom.polyline([(0, 0), (40, 0)])])
        got = PT.punch_region(line, cutter, False)
        self.assertEqual(len(got.contours), 2)
        self.assertTrue(all(not c.closed for c in got.contours))
        self.assertAlmostEqual(length(got.contours), 30.0, places=5)
        frame = Path([geom.rect(0, -20, 40, 20)])                            # le bord du haut passe sous le carré
        got = PT.punch_region(frame, cutter, False)
        self.assertIsNotNone(got)
        self.assertTrue(all(c.closed for c in got.contours), 'avant : le cadre s\'ouvrait en traits')
        self.assertEqual(len(got.contours), 1)
        self.assertAlmostEqual(length(got.contours), 120.0 - 10.0 + 20.0, places=4)  # une encoche de 10 × 5
        inside = Path([geom.rect(-50, -50, 120, 100)])                      # le carré au milieu, loin du tracé
        self.assertIsNone(PT.punch_region(inside, cutter, False))
        small = Path([geom.rect(18, -2, 4, 4)])                             # tout dessous : parti
        self.assertEqual(PT.punch_region(small, cutter, False).contours, [])

    def test_a_ring_loses_a_band(self):
        PT = self.PT
        ring = Path([geom.rect(-20, -20, 40, 40), geom.rect(-10, -10, 20, 20)])  # un anneau carré
        cutter = PT.place(PT.stamp_of(Path([geom.rect(0, 0, 10, 10)])), (15, 0))  # en travers de la bande de droite
        got = PT.punch_region(ring, cutter, False)
        self.assertEqual(len(got.contours), 1, 'avant : le bord du poinçon tracé aussi dans le trou')
        self.assertAlmostEqual(length(got.contours), 160 - 10 + 80 - 10 + 2 * 10, places=4)


class Window(unittest.TestCase):

    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.w.resize(1200, 800)
        self.w.show()
        app.processEvents()
        self.addCleanup(self.close)
        for k in ('cad/emporte_piece', 'cad/emporte_piece_forme'):
            self.w.settings.remove(k)
            self.addCleanup(self.w.settings.remove, k)
        self.info = mock.patch('vectordrive.ui.main_window.QMessageBox.information')
        self.said = self.info.start()
        self.addCleanup(self.info.stop)

    def close(self):
        self.w.modified = False
        self.w.close()
        self.w.deleteLater()
        app.processEvents()

    def add(self, c, filled=False):
        s = Shape(path=Path([c]), tool=0, filled=filled)
        self.w.canvas.doc.add(s)
        return s

    def test_the_first_selected_shape_is_the_punch(self):
        w = self.w
        stamp = self.add(geom.rect(100, 100, 10, 10))
        line = self.add(geom.polyline([(0, 0), (60, 0)]))
        frame = self.add(geom.rect(0, 20, 60, 20))
        w.canvas.selection = [stamp]
        self.assertTrue(hasattr(w, 'punch_command'), BEFORE)
        w.punch_command()
        self.assertEqual(w.canvas.tool, 'punchout')
        tool = w.canvas.tool_obj
        self.assertEqual(tool.spec['kind'], 'forme')
        shape, _ = w.canvas.punch_preview((30, 0), tool.spec)                # le pointeur : la forme, sous la souris
        self.assertEqual(tuple(round(v, 9) for v in shape.bbox()), (25.0, -5.0, 35.0, 5.0))
        tool.press(None, (30, 0), None)
        self.assertAlmostEqual(length(line.path.contours), 50.0, places=5)
        self.assertTrue(all(not c.closed for c in line.path.contours))
        tool.press(None, (10, 20), None)                                     # le bord du bas du cadre
        self.assertTrue(all(c.closed for c in frame.path.contours))
        self.assertEqual(len(frame.path.contours), 1)
        self.assertEqual(w.canvas.tool, 'punchout')                          # l'outil reste
        tool.press(None, (105, 105), None)                                   # sur la forme pointeur : épargnée
        self.assertAlmostEqual(length(stamp.path.contours), 40.0, places=6)
        w.canvas.toolExitRequested.emit()                                    # clic droit : quitter
        self.assertEqual(w.canvas.tool, 'select')
        w.set_tool('punchout')                                               # sans sélection : la dernière forme
        self.assertEqual(w.canvas.tool_obj.spec['kind'], 'forme')
        b = w.canvas.tool_obj.spec['stamp'].bbox()
        self.assertAlmostEqual(b[2] - b[0], 10.0, places=6)
        self.assertIsNotNone(w.last_stamp())

    def test_the_other_selected_objects_only(self):
        w = self.w
        stamp = self.add(geom.circle((100, 100), 3))
        a = self.add(geom.polyline([(0, 0), (60, 0)]))
        b = self.add(geom.polyline([(0, 1), (60, 1)]))
        w.canvas.selection = [stamp, b]
        w.punch_command()
        w.canvas.tool_obj.press(None, (30, 0.5), None)
        self.assertAlmostEqual(length(a.path.contours), 60.0, places=6)     # pas sélectionné : intact
        self.assertLess(length(b.path.contours), 60.0)

    def shapes(self):
        return [s for L in self.w.canvas.doc.layers for s in L.items if isinstance(s, Shape)]

    def test_after_undo_the_punch_is_still_spared(self):
        w = self.w
        stamp = self.add(geom.rect(0, -5, 10, 10))                           # la forme pointeur
        self.add(geom.polyline([(30, 0), (90, 0)]))
        w.canvas.selection = [stamp]
        w.punch_command()
        tool = w.canvas.tool_obj
        tool.press(None, (60, 0), None)
        w.undo()                                                             # des copies reviennent dans le dessin
        tool.press(None, (5, 0), None)                                       # sur la forme pointeur
        back = [s for s in self.shapes() if s.bbox()[0] == 0.0]
        self.assertEqual(len(back), 1, 'avant : la forme pointeur était trouée après Ctrl+Z')
        self.assertAlmostEqual(length(back[0].path.contours), 40.0, places=6)

    def test_the_knife_cuts_its_targets_again(self):
        w = self.w
        blade = self.add(geom.polyline([(0, 100), (0, 140)]))
        plate = self.add(geom.rect(0, 0, 60, 20))
        self.add(geom.rect(0, 22, 60, 6))                                    # traversée, pas sélectionnée : intacte
        w.canvas.selection = [blade, plate]
        w.knife_command()
        tool = w.canvas.tool_obj
        tool.press(None, (20, 10), None)
        tool.press(None, (40, 10), None)                                     # dans un morceau du 1er clic
        low = [s for s in self.shapes() if s is not blade and s.bbox()[3] <= 20.0 + 1e-9]
        self.assertEqual(len(low), 3, 'avant : le second clic ne coupait plus rien')
        self.assertEqual(len([s for s in self.shapes() if s.bbox()[1] >= 22.0 - 1e-9 and s is not blade]), 1)

    def test_without_a_closed_shape_it_says_so(self):
        w = self.w
        w.canvas.selection = [self.add(geom.polyline([(0, 0), (60, 0)]))]
        w.punch_command()
        self.assertFalse(self.said.called)                       # demande du 19/11 : plus de fenêtre, la barre d'état
        self.assertIn('Poinçonner', w.statusBar().currentMessage())
        self.assertNotEqual(w.canvas.tool, 'punchout')

    def test_shift_keeps_the_old_punch(self):
        w = self.w
        frame = self.add(geom.rect(10, -5, 10, 10))
        line = self.add(geom.polyline([(0, 0), (60, 0)]))
        w.canvas.selection = [frame, line]
        with mock.patch.object(type(w), '_shift_held', staticmethod(lambda: True)):
            w.punch_command()
        self.assertNotEqual(w.canvas.tool, 'punchout')
        rest = [s for L in w.canvas.doc.layers for s in L.items if isinstance(s, Shape) and s is not frame]
        self.assertAlmostEqual(sum(length(s.path.contours) for s in rest), 50.0, places=5)   # trouée d'un coup

    def test_the_knife_follows_the_mouse(self):
        from vectordrive.ui import tools as T
        w = self.w
        blade = self.add(geom.polyline([(100, 100), (100, 140)]))         # un trait vertical de 40
        box = self.add(geom.rect(0, 0, 40, 20))
        line = self.add(geom.polyline([(0, 50), (60, 50)]))
        w.canvas.selection = [blade]
        self.assertTrue(hasattr(w, 'knife_command'), 'avant : le Couteau coupait d\'un coup, sans pointeur')
        w.knife_command()
        tool = w.canvas.tool_obj
        self.assertIsInstance(tool, T.KnifeStampTool)
        self.assertEqual(tool.placed((20, 10)).bbox()[1], -10.0)             # centré sur la souris
        tool.press(None, (20, 10), None)
        pieces = [s for L in w.canvas.doc.layers for s in L.items if isinstance(s, Shape) and s is not blade
                  and s is not line]
        self.assertEqual(len(pieces), 2, 'la boîte en deux morceaux fermés')
        self.assertTrue(all(c.closed for s in pieces for c in s.path.contours))
        tool.press(None, (30, 50), None)                                     # un trait ouvert : coupé, ouvert
        self.assertEqual(len(line.path.contours), 2)
        self.assertEqual(w.canvas.tool, 'knife_line')                        # l'outil reste
        self.assertAlmostEqual(length(blade.path.contours), 40.0, places=6)  # la lame, intacte
        w.undo()
        back = [s for L in w.canvas.doc.layers for s in L.items if isinstance(s, Shape) and s.bbox()[1] == 50.0]
        self.assertEqual([len(s.path.contours) for s in back], [1])          # chaque clic s'annule à part
        shapes = [s for L in w.canvas.doc.layers for s in L.items if isinstance(s, Shape)]
        self.assertEqual(len(shapes), 4, 'la boîte reste en deux morceaux (le 1er clic)')
        w.canvas.toolExitRequested.emit()
        self.assertEqual(w.canvas.tool, 'select')
        w.set_tool('knife_line')                                             # l'outil d'avant, sans lame
        self.assertIsInstance(w.canvas.tool_obj, T.KnifeLineTool)

    def test_the_options_offer_the_last_shape(self):
        w = self.w
        stamp = self.add(geom.rect(100, 100, 8, 8))
        w.canvas.selection = [stamp]
        w.set_tool('punchout')
        w.set_tool('select')
        got = w.punchout_options({'kind': 'cercle', 'diameter': 4.0})       # la forme choisie ici, pas la sélection
        self.assertEqual(w.canvas.tool_obj.spec['kind'], 'cercle')
        self.assertEqual(got['kind'], 'cercle')
        w.set_tool('select')
        got = w.punchout_options({'kind': 'forme'})
        self.assertEqual(w.canvas.tool_obj.spec['kind'], 'forme')
        self.assertIsNotNone(w.canvas.tool_obj.spec.get('stamp'))


if __name__ == '__main__':
    unittest.main()
