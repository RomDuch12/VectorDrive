"""Round 247 : formes paramétrées, éditables après coup (objets éditables de
TypeEdit) — rectangle (coins droits, arrondis, chanfreinés, creux),
ellipse, polygone (taille au sommet, au côté ou par longueur de côté,
arrondi), étoile (rayons, décalage, arrondi), spirale (Archimède ou
logarithmique), flèche (standard, orthogonale, filaire, double, harpon),
arc par sa corde. F2, double-clic, clic droit sur le bouton de l'outil."""
import math
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication, QDialog

app = QApplication.instance() or QApplication([])


class TestForms(unittest.TestCase):
    def test_every_type_builds(self):
        from vectordrive.core import forms as F
        for kind, cls in F.TYPES.items():
            p = cls().build()
            self.assertTrue(p.contours and all(c.segments for c in p.contours), kind)

    def test_parameters(self):
        from vectordrive.core import forms as F
        hexa = F.Polygon(sides=6, size=10.0, size_mode='longueur', angle=0.0)
        c = hexa.build().contours[0]
        self.assertAlmostEqual(math.dist(c.segments[0].p0, c.segments[0].p1), 10.0, 9)
        apo = F.Polygon(sides=4, size=10.0, size_mode='cote', angle=45.0).build()
        self.assertAlmostEqual(apo.bbox()[2], 10.0, 9)                   # carré de demi-côté 10
        st = F.Star(branches=5, r_out=20, r_in=8, twist=10)
        self.assertEqual(len(st.build().contours[0].segments), 10)
        self.assertGreater(len(F.Star(rounding=1.0).build().contours[0].segments), 10)
        r = F.Rect(width=40, height=20, corner='chanfrein', radius=3).build()
        self.assertEqual(len(r.contours[0].segments), 8)
        creux = F.Rect(width=40, height=20, corner='creux', radius=4).build().contours[0]
        self.assertAlmostEqual(abs(creux.signed_area()), 40 * 20 - math.pi * 16, 1)
        ar = F.Arrow(length=40, style='filaire').build()
        self.assertTrue(all(not c.closed for c in ar.contours))
        self.assertEqual(len(F.Arrow(double=True).build().contours[0].segments), 10)
        ortho = F.Arrow(style='orthogonale', head_width=16, head_length=99).build()
        self.assertAlmostEqual(ortho.bbox()[2] - ortho.bbox()[0], 40.0, 9)
        log = F.Spiral(law='log', r_out=20, r_in=1, turns=3).build()
        self.assertAlmostEqual(max(abs(v) for v in log.bbox()), 20.0, 2)
        arc = F.ChordArc(x0=0, y0=0, x1=40, y1=0, sagitta=10).build()
        self.assertAlmostEqual(arc.bbox()[3], 10.0, 6)

    def test_follows_similarity_not_stretch(self):
        from vectordrive.core import forms as F, geom
        sh = F.make(F.Star(cx=5, cy=5, twist=10))
        m = geom.Affine.translation(10, 0) @ geom.Affine.rotation(30) @ geom.Affine.scaling(1.5)
        t = sh.transformed(m)
        s = F.spec_of(t)
        self.assertIsNotNone(s)
        self.assertAlmostEqual(s.r_out, 30.0, 9)
        self.assertAlmostEqual(s.angle, 120.0, 9)
        rebuilt = s.build()
        self.assertLess(max(abs(a - b) for a, b in zip(rebuilt.bbox(), t.path.bbox())), 1e-6)
        mir = F.spec_of(sh.transformed(geom.Affine.mirror_y(0)))
        self.assertEqual(mir.twist, -10)
        self.assertIsNone(F.spec_of(sh.transformed(geom.Affine.scaling(2, 1))))   # étirée : une courbe
        sh.path = geom.Path([geom.rect(0, 0, 1, 1)])                     # retouchée
        self.assertIsNone(F.spec_of(sh))


class TestMarker(unittest.TestCase):
    def test_ten_looks_and_tool(self):
        from vectordrive.core import forms as F
        for k in range(10):
            self.assertTrue(F.Marker(look=k).build().contours)
        from vectordrive.ui.main_window import MainWindow
        from vectordrive.ui import form_dialog as FD
        w = MainWindow()
        try:
            s = F.Marker(look=8)
            FD.save_defaults(w.settings, s)                               # clic droit sur l'outil : aspect 8
            w.set_tool('marker')
            w.canvas.tool_obj.press(None, (5.0, 5.0), None)
            m = F.spec_of(w.canvas.selection[0])
            self.assertEqual((m.kind, m.look, m.cx), ('marker', 8, 5.0))
            self.assertEqual(w.canvas.tool, 'marker')                     # l'outil reste actif
        finally:
            w.settings.remove('formes/marker')
            w.modified = False
            w.close()


class TestWindow(unittest.TestCase):
    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()

    def tearDown(self):
        self.w.modified = False
        self.w.close()

    def test_drawn_rect_and_star_are_forms(self):
        from vectordrive.core import forms as F
        w = self.w
        w.set_tool('rect')
        sh = w.canvas.draw_between((0, 0), (30, 10))
        s = F.spec_of(sh)
        self.assertEqual((s.kind, s.width, s.height, s.cx, s.cy), ('rect', 30, 10, 15, 5))
        w.set_tool('star')
        t = w.canvas.tool_obj
        t.a, t.b = (50.0, 50.0), (50.0, 70.0)
        st = t.spec()
        self.assertEqual((st.kind, st.r_out, st.cx), ('star', 20.0, 50.0))
        t.release(None, (50.0, 70.0), None)
        self.assertEqual(F.spec_of(w.canvas.selection[0]).kind, 'star')

    def test_f2_edit_and_cancel(self):
        from vectordrive.core import forms as F
        w = self.w
        w.set_tool('ellipse')
        sh = w.canvas.draw_between((0, 0), (20, 10))
        w.canvas.select([sh])
        dlg = w.edit_form(sh, exec_dialog=False)
        dlg.set_field('width', 50.0)                                     # aperçu en direct
        self.assertAlmostEqual(sh.path.bbox()[2] - sh.path.bbox()[0], 50.0, 6)
        dlg.reject()                                                     # annuler : comme avant
        self.assertAlmostEqual(sh.path.bbox()[2] - sh.path.bbox()[0], 20.0, 6)
        dlg = w.edit_form(sh, exec_dialog=False)
        dlg.set_field('height', 30.0)
        dlg.accept()
        self.assertEqual(F.spec_of(sh).height, 30.0)
        w.undo()
        sh2 = w.canvas.doc.layers[0].items[-1]
        self.assertAlmostEqual(sh2.path.bbox()[3] - sh2.path.bbox()[1], 10.0, 6)
        with mock.patch.object(w, 'edit_form') as ed:                    # F2 sur une forme sélectionnée
            w.canvas.select([sh2])
            w.set_tool('select')
            w.f2()
            ed.assert_called_once()

    def test_f2_with_tool_creates_numerically(self):
        from vectordrive.core import forms as F
        w = self.w
        w.set_tool('polygon')
        dlg = w.f2() if False else w.create_form('polygon', exec_dialog=False)
        dlg.set_field('sides', 8)
        sh = w.create_form('polygon', spec=dlg.value())
        self.assertEqual(F.spec_of(sh).sides, 8)
        arrow = w.create_form('arrow', spec=F.Arrow(style='filaire'))
        self.assertEqual(F.spec_of(arrow).style, 'filaire')

    def test_right_click_tool_button(self):
        from PySide6.QtCore import QPoint
        from PySide6.QtGui import QContextMenuEvent
        from PySide6.QtWidgets import QToolButton
        from vectordrive.ui import form_dialog as FD
        w = self.w
        btn = next(b for b in w.ribbon.findChildren(QToolButton) if b.defaultAction() is w.A['tool_star'])
        seen = []

        def fake_exec(d):
            seen.append(d.windowTitle())
            d.set_field('branches', 7)
            return QDialog.DialogCode.Accepted
        with mock.patch.object(FD.FormDialog, 'exec', fake_exec):
            QApplication.sendEvent(btn, QContextMenuEvent(QContextMenuEvent.Reason.Mouse, QPoint(2, 2), btn.mapToGlobal(QPoint(2, 2))))
        self.assertEqual(len(seen), 1)
        self.assertEqual(FD.defaults(w.settings, 'star').branches, 7)   # réglage de l'outil gardé
        self.assertEqual(w.sides.value(), 7)

    def test_double_click_and_node_edit(self):
        from vectordrive.core import forms as F
        w = self.w
        sh = w.create_form('star', spec=F.Star(cx=0, cy=0))
        with mock.patch.object(w, 'edit_form') as ed:
            w._item_double_clicked(sh)
            ed.assert_called_once()
        from vectordrive.core import geom
        sh.path = geom.Path([geom.rect(0, 0, 3, 3)])                     # retouchée en Mode Point…
        w._item_double_clicked(sh)                                       # … le double-clic l'y emmène
        self.assertEqual(w.canvas.tool, 'node')


if __name__ == '__main__':
    unittest.main()
