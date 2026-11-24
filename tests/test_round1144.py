"""Round 1144 (demande du 23/11) : clic droit sur les boutons du ruban → les réglages de la fonction ; Poinçonner :
« sur contour fermé ouvrir le contour » ; l'outil Cercle juste avant Ellipse."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1144.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'
os.environ.setdefault('VECTORDRIVE_KEYS_MEMORY', '1')

from PySide6.QtWidgets import QApplication, QDialog, QToolButton  # noqa: E402

from vectordrive.core import forms as F  # noqa: E402
from vectordrive.core import geom  # noqa: E402
from vectordrive.core import punchtool as PT  # noqa: E402
from vectordrive.core.geom import Path  # noqa: E402

app = QApplication.instance() or QApplication([])
BEFORE = 'avant : pas d’outil Cercle, ni de réglage « ouvrir le contour fermé »'


def square(x0=0.0, y0=0.0, s=20.0):
    return Path([geom.polyline([(x0, y0), (x0 + s, y0), (x0 + s, y0 + s), (x0, y0 + s)], closed=True)])


class Core(unittest.TestCase):
    def test_circle_form(self):
        self.assertIn('circle', F.TYPES, BEFORE)
        c = F.TYPES['circle'](cx=5.0, cy=-2.0, diameter=30.0)
        b = c.build().bbox()
        self.assertAlmostEqual(b[2] - b[0], 30.0, 6)
        self.assertAlmostEqual((b[0] + b[2]) / 2, 5.0, 6)
        sh = F.make(c)
        self.assertEqual(F.spec_of(sh).diameter, 30.0)
        m = geom.Affine.scaling(2.0)
        d = F.transformed(sh.extra[F.KEY], m, sh.path.transformed(m))      # agrandi : le diamètre suit
        self.assertAlmostEqual(d['diameter'], 60.0, 9)
        rot = geom.Affine.rotation(30.0) if hasattr(geom.Affine, 'rotation') else None
        if rot is not None:                                                 # tourné : pas d'angle, pas d'erreur
            self.assertIsNotNone(F.transformed(sh.extra[F.KEY], rot, sh.path.transformed(rot)))
        mirror = geom.Affine(-1, 0, 0, 1, 0, 0)
        self.assertIsNotNone(F.transformed(sh.extra[F.KEY], mirror, sh.path.transformed(mirror)))

    def test_punch_opens_a_closed_contour(self):
        cut = PT.region('cercle', (20.0, 20.0), 10.0)                      # sur un coin du carré
        kept = PT.punch_region(square(), cut, False)
        self.assertTrue(kept is not None and all(c.closed for c in kept.contours))   # d'office : reste fermé
        opened = PT.punch_region(square(), cut, False, open_closed=True)
        self.assertIsNotNone(opened, BEFORE)
        self.assertTrue(opened.contours and not any(c.closed for c in opened.contours))
        length = sum(float(s.length()) for c in opened.contours for s in c.segments)
        self.assertLess(length, 80.0)                                       # le coin couvert est parti
        self.assertGreater(length, 65.0)
        self.assertIsNone(PT.punch_region(square(), PT.region('cercle', (100.0, 100.0), 10.0), False,
                                          open_closed=True))                # rien sous la forme : rien de changé
        filled = PT.punch_region(square(), cut, True, open_closed=True)     # une surface : évidée, toujours fermée
        self.assertTrue(filled is not None and all(c.closed for c in filled.contours))


class Window(unittest.TestCase):
    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        for k in ('cad/emporte_piece', 'formes/circle', 'cad/text_style', 'ligne_double/reglages'):
            self.w.settings.remove(k)
            self.addCleanup(self.w.settings.remove, k)

    def tearDown(self):
        self.w.canvas.doc.modified = False
        self.w.modified = False
        self.w.close()
        self.w.deleteLater()
        app.processEvents()

    def test_circle_tool_right_before_ellipse(self):
        w = self.w
        self.assertIn('tool_circle', w.A, BEFORE)
        group = next(g for g in w.ribbon.findChildren(QToolButton) if g.defaultAction() is w.A['tool_ellipse']).parent()
        acts = [b.defaultAction() for b in group.findChildren(QToolButton)
                if b.defaultAction() is not None and b.parent() is group]
        i = acts.index(w.A['tool_circle'])
        self.assertIs(acts[i + 1], w.A['tool_ellipse'])
        from vectordrive.ui import modes
        self.assertTrue(modes.in_simple('tool_circle', w.settings))         # aussi en mode simple

    def test_circle_tool_draws_a_circle(self):
        w = self.w
        w.A['tool_circle'].trigger()
        self.assertEqual(w.canvas.tool, 'circle')
        sh = w.canvas.draw_between((10.0, 10.0), (13.0, 14.0))              # centre, puis à 5 mm
        spec = F.spec_of(sh)
        self.assertEqual(spec.kind, 'circle')
        self.assertAlmostEqual(spec.diameter, 10.0, 9)
        self.assertEqual((spec.cx, spec.cy), (10.0, 10.0))
        w.A['tool_circle'].trigger()
        w.canvas.select([])                                                 # rien de sélectionné : l'outil
        self.assertEqual(w._form_kind_of_tool(), 'circle')
        with mock.patch.object(type(w), 'edit_form', side_effect=AssertionError('fenêtre de la forme')), \
                mock.patch.object(type(w), 'create_form', return_value=None) as cf:
            w.f2()                                                          # F2 : le cercle en chiffres
        self.assertEqual(cf.call_args.args[0], 'circle')
        self.assertIsNotNone(w.create_form('circle', exec_dialog=False))

    def test_circle_right_click_default_diameter(self):
        from vectordrive.ui import form_dialog as FD
        w = self.w
        settings = w._tool_settings(w.A['tool_circle'])
        self.assertIsNotNone(settings)

        def fake(d):
            d.set_field('diameter', 42.0)
            return QDialog.DialogCode.Accepted
        with mock.patch.object(FD.FormDialog, 'exec', fake):
            settings()
        self.assertEqual(FD.defaults(w.settings, 'circle').diameter, 42.0)
        sh = w.create_form('circle', spec=FD.defaults(w.settings, 'circle'))
        self.assertAlmostEqual(F.spec_of(sh).diameter, 42.0, 9)

    def test_punch_setting_and_right_click(self):
        w = self.w
        for k in ('punch', 'tool_punchout'):
            self.assertIsNotNone(w._tool_settings(w.A[k]), k)
        got = w.punch_settings(params={'open_closed': True, 'kind': 'cercle', 'diameter': 10.0})
        self.assertTrue(got['open_closed'])
        self.assertTrue(w.punchout_spec()['open_closed'])
        self.assertNotEqual(w.canvas.tool, 'punchout')                     # le clic droit ne prend pas l'outil
        w.settings.setValue('cad/emporte_piece', {'kind': 'cercle', 'open_closed': 'false'})
        self.assertFalse(w.punchout_spec()['open_closed'])                  # relu d'un .ini
        w.settings.setValue('cad/emporte_piece', {'kind': 'cercle', 'open_closed': 'true'})
        self.assertTrue(w.punchout_spec()['open_closed'])
        names = [n for n, *_ in self._punch_fields()]
        self.assertIn('open_closed', names)

    def _punch_fields(self):
        seen = []
        real = self.w._ask

        def spy(key, title, spec, choices=None, params=None):
            seen.extend(spec)
            return real(key, title, spec, choices=choices, params=params)
        with mock.patch.object(self.w, '_ask', side_effect=spy):
            self.w.punch_settings(params={})
        return seen

    def test_punch_at_opens_the_contour(self):
        from vectordrive.core.document import Shape
        w = self.w
        sh = Shape(path=square())
        w.canvas.doc.layers[0].items.append(sh)
        spec = dict(w.punchout_spec(), kind='cercle', diameter=10.0, open_closed=True)
        n = w.canvas.punch_at((20.0, 20.0), spec)
        self.assertEqual(n, 1)
        self.assertFalse(any(c.closed for c in sh.path.contours))

    def test_existing_settings_on_right_click(self):
        w = self.w
        for k in ('tool_dim_arc', 'tool_dim_jogged', 'tool_rect3', 'tool_polygon_edge', 'tool_dline', 'text_italic',
                  'text_underline', 'tool_text', 'tool_center_line'):
            self.assertIn(k, w.A, k)
            self.assertIsNotNone(w._tool_settings(w.A[k]), k)
        with mock.patch.object(type(w), 'tool_form_dialog') as fd:
            w._tool_settings(w.A['tool_rect3'])()
            w._tool_settings(w.A['tool_polygon_edge'])()
        self.assertEqual([c.args[0] for c in fd.call_args_list], ['rect', 'polygon'])
        with mock.patch.object(type(w), 'options_dialog') as od:
            w._tool_settings(w.A['tool_center_line'])()
        self.assertEqual(od.call_args.kwargs.get('page'), 'Dessin')
        self.assertIsNone(w._tool_settings(w.A['tool_line']))              # rien à régler : pas de réglages

    def test_double_line_settings(self):
        import json
        w = self.w
        o = {'left': 2.0, 'right': 1.0, 'corners': 'vif', 'ends': 'ouvert'}
        self.assertEqual(w.dline_settings(dict(o)), o)
        self.assertEqual(json.loads(w.settings.value('ligne_double/reglages')), o)
        self.assertEqual(w.canvas.dline, o)
        with mock.patch.object(type(w), 'dline_dialog', return_value=None):
            self.assertIsNone(w.dline_settings())                           # Annuler : rien de changé
        self.assertEqual(json.loads(w.settings.value('ligne_double/reglages')), o)

    def test_italic_underline_defaults(self):
        w = self.w
        got = w.text_style_defaults(params={'italic': 20.0, 'pos': 30.0, 'thick': 10.0})
        self.assertEqual(got, {'italic': 20.0, 'pos': 30.0, 'thick': 10.0})
        self.assertEqual(w._text_style_default('italic'), 20.0)
        self.assertEqual(w._text_style_default('underline'), {'pos': 30.0, 'thick': 10.0})

    def test_ribbon_menu_has_the_settings(self):
        w = self.w
        btn = next((b for b in w.ribbon.findChildren(QToolButton) if b.defaultAction() is w.A['tool_circle']), None)
        self.assertIsNotNone(btn)
        m = w._ribbon_button_menu(btn, btn.mapToGlobal(btn.rect().center()), exec_menu=False,
                                  settings=w._tool_settings(w.A['tool_circle']))
        self.assertIsNotNone(m.defaultAction())                             # réglages en tête


if __name__ == '__main__':
    unittest.main()
