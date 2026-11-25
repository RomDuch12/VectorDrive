"""Round 1152 (demande du 24/11) : F2 pendant le tracé d'une forme à la souris — le formulaire prend la position
commencée et la taille de l'instant ; tout formulaire F2 ou de réglages s'ouvre le premier champ sélectionné."""
import math
import os
import tempfile
import unittest
from dataclasses import dataclass
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1152.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import QEvent, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QMouseEvent  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from vectordrive.core import forms as F  # noqa: E402
from vectordrive.core.document import Layer, Plate  # noqa: E402
from vectordrive.ui import form_dialog as FD  # noqa: E402
from vectordrive.ui.dialogs import ParamsDialog  # noqa: E402

app = QApplication.instance() or QApplication([])
BEFORE = 'avant : F2 pendant le tracé ouvrait la forme retenue au centre de la vue, le glisser restait en cours'
UNSELECTED = 'avant : le premier champ s’ouvrait sans sélection (il fallait effacer la valeur)'
NONE, CTRL, SHIFT = (Qt.KeyboardModifier.NoModifier, Qt.KeyboardModifier.ControlModifier,
                     Qt.KeyboardModifier.ShiftModifier)
LEFT = Qt.MouseButton.LeftButton
TOL = 0.002                                 # les champs du formulaire arrondissent au millième


def mouse(kind, xy, mods=NONE):
    """Événement de souris du bouton gauche au point `xy` (pixels de la vue)."""
    button = Qt.MouseButton.NoButton if kind == QEvent.Type.MouseMove else LEFT
    buttons = Qt.MouseButton.NoButton if kind == QEvent.Type.MouseButtonRelease else LEFT
    return QMouseEvent(kind, QPointF(*xy), QPointF(*xy), button, buttons, mods)


def all_selected(field) -> bool:
    """Toute la valeur du champ est sélectionnée."""
    le = field.lineEdit() if hasattr(field, 'lineEdit') else field
    return le.hasSelectedText() and le.selectedText() == le.text()


class DraftF2(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from vectordrive.ui.main_window import MainWindow
        cls.w = MainWindow()
        if not cls.w.docs:
            cls.w.new_document()

    @classmethod
    def tearDownClass(cls):
        for t in cls.w.docs:
            t.modified = False
        cls.w.modified = False
        cls.w.close()
        cls.w.deleteLater()
        app.processEvents()

    def setUp(self):
        w = self.w
        self.c = c = w.canvas
        self.layer = Layer(name='Plan 1')
        c.doc.layers[:] = [self.layer]
        c.doc.active = self.layer.id
        c.doc.plate = Plate(width=200.0, height=100.0)
        w._undo.clear()
        w.set_tool('select')
        c.select([])
        c._drag = None
        self.addCleanup(self.clean)

    def clean(self):
        self.c._drag = None
        self.w.set_tool('select')
        for kind in ('rect', 'ellipse', 'circle', 'polygon', 'star', 'spiral'):
            self.w.settings.remove(f'formes/{kind}')            # réglages retenus par l'essai : retirés

    def drag(self, tool, a=(30, 40), b=(110, 90), mods=NONE):
        """Glisser de l'outil commencé en `a`, le pointeur en `b`, le bouton toujours tenu."""
        self.w.set_tool(tool)
        self.c.mousePressEvent(mouse(QEvent.Type.MouseButtonPress, a))
        if b is not None:
            self.c.mouseMoveEvent(mouse(QEvent.Type.MouseMove, b, mods))

    def release(self, at=(110, 90)):
        self.c.mouseReleaseEvent(mouse(QEvent.Type.MouseButtonRelease, at))

    def f2(self, accept: bool):
        """F2, le formulaire de la forme validé ou annulé sans s'ouvrir : rend la forme qu'il montrait."""
        seen = {}

        def fake(dlg):
            seen['spec'] = dlg.value()
            return 1 if accept else 0
        with mock.patch.object(FD.FormDialog, 'exec', fake):
            seen['got'] = self.w.f2()
        return seen.get('spec'), seen['got']

    def test_rect_form_takes_place_and_size_of_the_drag(self):
        w, c = self.w, self.c
        FD.save_defaults(w.settings, F.Rect(width=7.0, height=9.0, corner='arrondi', radius=2.5, angle=30.0))
        self.drag('rect')
        (ax, ay), (bx, by) = c._drag['a'], c._drag['b']
        self.assertGreater(abs(bx - ax), 1e-3)
        spec, got = self.f2(accept=False)
        self.assertEqual(spec.kind, 'rect')
        self.assertAlmostEqual(spec.cx, (ax + bx) / 2, msg=BEFORE, delta=TOL)  # la position commencée à la souris
        self.assertAlmostEqual(spec.cy, (ay + by) / 2, delta=TOL)
        self.assertAlmostEqual(spec.width, abs(bx - ax), delta=TOL)  # la taille au moment de F2
        self.assertAlmostEqual(spec.height, abs(by - ay), delta=TOL)
        self.assertEqual((spec.corner, spec.radius), ('arrondi', 2.5))      # le reste : retenu
        self.assertEqual(spec.angle, 0.0)                                   # droit, comme posé à la souris
        self.assertIsNone(got)                                              # annulé : rien de posé
        self.assertEqual(len(self.layer.items), 0)

    def test_clicked_corner_stays_when_the_size_is_typed(self):
        w, c = self.w, self.c
        FD.save_defaults(w.settings, F.Rect(width=7.0, height=9.0, corner='arrondi', radius=2.5, angle=30.0))
        self.drag('rect')
        (ax, ay), (bx, by) = c._drag['a'], c._drag['b']
        sx, sy = (1 if bx >= ax else -1), (1 if by >= ay else -1)
        seen = {}

        def fake(dlg):
            seen['first'] = dlg.first                                       # la taille d'abord
            dlg.widgets['width'].setValue(80.0)                             # F2, la valeur, Entrée
            return 1
        with mock.patch.object(FD.FormDialog, 'exec', fake):
            sh = w.f2()
        self.assertEqual(seen['first'], 'width')
        got = F.spec_of(sh)
        self.assertAlmostEqual(got.width, 80.0)
        self.assertAlmostEqual(got.cx - sx * got.width / 2, ax, delta=TOL)  # le coin cliqué n'a pas bougé
        self.assertAlmostEqual(got.cy - sy * got.height / 2, ay, delta=TOL)
        kept = FD.defaults(w.settings, 'rect')                              # retenus : le champ tapé seulement
        self.assertEqual((kept.width, kept.height, kept.angle), (80.0, 9.0, 30.0))

    def test_cancel_leaves_no_ghost_drag(self):
        c = self.c
        self.drag('rect')
        self.f2(accept=False)
        self.assertIsNone(c._drag, BEFORE)                                  # le glisser est pris
        self.release()                                                      # relâcher après : rien de créé
        self.assertEqual(len(self.layer.items), 0, BEFORE)
        self.assertEqual(c.tool, 'rect')                                    # l'outil reste, prêt pour un autre tracé
        self.assertIsNone(c.take_draft())                                   # plus rien à prendre
        self.w.set_tool('line')                                             # un trait n'a pas de formulaire : laissé
        c.mousePressEvent(mouse(QEvent.Type.MouseButtonPress, (30, 40)))
        c.mouseMoveEvent(mouse(QEvent.Type.MouseMove, (110, 90)))
        with mock.patch.object(type(self.w), 'focus_dimensions'):
            self.w.f2()
        self.assertEqual(c._drag['kind'], 'draw')
        self.release()
        self.assertEqual(len(self.layer.items), 1)

    def test_ok_places_the_form_once(self):
        w, c = self.w, self.c
        self.drag('rect')
        (ax, ay), (bx, by) = c._drag['a'], c._drag['b']
        spec, sh = self.f2(accept=True)
        self.assertEqual(len(self.layer.items), 1)
        got = F.spec_of(sh)
        self.assertAlmostEqual(got.cx, (ax + bx) / 2, msg=BEFORE, delta=TOL)
        self.assertAlmostEqual(got.width, abs(bx - ax), delta=TOL)
        self.assertAlmostEqual(got.height, abs(by - ay), delta=TOL)
        self.release()                                                      # le bouton relâché ensuite : rien de plus
        self.assertEqual(len(c.doc.layers[0].items), 1, BEFORE)
        w.undo()                                                            # un seul pas d'annulation
        self.assertEqual(len(c.doc.layers[0].items), 0)

    def test_circle_centre_and_diameter(self):
        c = self.c
        self.drag('circle')
        (ax, ay), (bx, by) = c._drag['a'], c._drag['b']
        spec, _got = self.f2(accept=False)
        self.assertEqual(spec.kind, 'circle')
        self.assertAlmostEqual(spec.cx, ax, msg=BEFORE, delta=TOL)  # le centre au premier point
        self.assertAlmostEqual(spec.cy, ay, delta=TOL)
        self.assertAlmostEqual(spec.diameter, 2 * math.hypot(bx - ax, by - ay), delta=TOL)
        self.release()
        self.assertEqual(len(self.layer.items), 0)

    def test_ellipse_with_ctrl_and_shift_like_the_drawing(self):
        c = self.c
        self.drag('ellipse', mods=CTRL)                                     # Ctrl : un cercle
        (ax, ay), (bx, by) = c._drag['a'], c._drag['b']
        side = max(abs(bx - ax), abs(by - ay))
        spec, _got = self.f2(accept=False)
        self.assertEqual(spec.kind, 'ellipse')
        self.assertAlmostEqual(spec.width, side, msg=BEFORE, delta=TOL)
        self.assertAlmostEqual(spec.height, side, delta=TOL)
        self.release()
        self.drag('rect', mods=SHIFT)                                       # Maj : depuis le centre
        (ax, ay), (bx, by) = c._drag['a'], c._drag['b']
        spec, _got = self.f2(accept=False)
        self.assertAlmostEqual(spec.cx, ax, msg=BEFORE, delta=TOL)
        self.assertAlmostEqual(spec.cy, ay, delta=TOL)
        self.assertAlmostEqual(spec.width, 2 * abs(bx - ax), delta=TOL)
        self.assertAlmostEqual(spec.height, 2 * abs(by - ay), delta=TOL)

    def test_drag_without_size_keeps_the_kept_form_at_the_click(self):
        w, c = self.w, self.c
        FD.save_defaults(w.settings, F.Rect(width=7.0, height=9.0))
        self.drag('rect', b=None)                                           # le bouton pressé, sans bouger
        ax, ay = c._drag['a']
        spec, _got = self.f2(accept=False)
        self.assertAlmostEqual(spec.cx, ax, msg=BEFORE, delta=TOL)  # à la position du clic
        self.assertAlmostEqual(spec.cy, ay, delta=TOL)
        self.assertEqual((spec.width, spec.height), (7.0, 9.0))             # la taille retenue
        self.assertIsNone(c._drag)

    def test_polygon_drag(self):
        w, c = self.w, self.c
        FD.save_defaults(w.settings, F.Polygon(angle=15.0, rounding=1.5))
        self.drag('polygon')
        t = c.tool_obj
        a, b = t.a, t.b
        self.assertGreater(math.dist(a, b), 1e-3)
        drawn = t.spec().angle                                              # vers le pointeur, comme le tracé
        spec, _got = self.f2(accept=False)
        self.assertEqual(spec.kind, 'polygon')
        self.assertAlmostEqual(spec.cx, a[0], msg=BEFORE, delta=TOL)  # du centre…
        self.assertAlmostEqual(spec.cy, a[1], delta=TOL)
        self.assertAlmostEqual(spec.size, math.dist(a, b), delta=TOL)  # … au sommet
        self.assertEqual(spec.sides, max(3, int(c.poly_sides)))
        self.assertEqual(spec.rounding, 1.5)                                # le reste : retenu
        self.assertAlmostEqual(spec.angle, drawn, delta=TOL)
        self.assertIsNone(t.a)                                              # le glisser est pris
        self.release()
        self.assertEqual(len(self.layer.items), 0, BEFORE)
        self.drag('star')                                                   # validé : l'étoile posée une fois
        t = c.tool_obj
        a, b = t.a, t.b
        _spec, sh = self.f2(accept=True)
        self.release()
        self.assertEqual(len(c.doc.layers[0].items), 1)
        got = F.spec_of(sh)
        self.assertEqual(got.kind, 'star')
        self.assertAlmostEqual(got.r_out, math.dist(a, b), delta=TOL)
        self.assertAlmostEqual(got.cx, a[0], delta=TOL)


class FirstField(unittest.TestCase):
    def shown(self, dlg):
        self.addCleanup(dlg.deleteLater)
        self.addCleanup(dlg.close)
        dlg.show()
        app.processEvents()
        return dlg

    def test_form_dialog_first_field_selected(self):
        dlg = self.shown(FD.FormDialog(None, F.Rect(cx=12.5, cy=3.0)))
        first = dlg.widgets['cx']
        self.assertIs(dlg.focusWidget(), first)
        self.assertTrue(all_selected(first), UNSELECTED)
        QTest.keyClicks(first, '42')                                        # F2, la valeur : elle remplace l'ancienne
        self.assertEqual(first.value(), 42.0)
        self.assertEqual(dlg.value().cx, 42.0)
        tool = self.shown(FD.FormDialog(None, F.Rect(), placement=False))   # réglages de l'outil : la largeur
        self.assertIs(tool.focusWidget(), tool.widgets['width'])
        self.assertTrue(all_selected(tool.widgets['width']))

    def test_params_dialog_first_field_selected(self):
        @dataclass
        class P:
            dist: float = 2.5
            name: str = 'abc'
            on: bool = True
            mode: str = 'a'
        labels = {'dist': 'Distance', 'name': 'Nom', 'on': 'Actif', 'mode': 'Mode'}
        dlg = self.shown(ParamsDialog(None, 'Essai', P(), labels, choices={'mode': [('a', 'A'), ('b', 'B')]}))
        first = dlg.fields['dist']
        self.assertIs(dlg.focusWidget(), first)
        self.assertTrue(all_selected(first), UNSELECTED)
        QTest.keyClicks(first, '7')
        self.assertEqual(dlg.result_params().dist, 7.0)
        text = self.shown(ParamsDialog(None, 'Essai', P(), {'name': 'Nom', 'dist': 'Distance'}))
        self.assertIs(text.focusWidget(), text.fields['name'])              # un texte : tout sélectionné aussi
        self.assertEqual(text.fields['name'].selectedText(), 'abc', UNSELECTED)
        off = ParamsDialog(None, 'Essai', P(), labels)
        off.fields['dist'].setEnabled(False)                                # premier champ grisé : le suivant
        self.shown(off)
        self.assertIs(off.focusWidget(), off.fields['name'])
        self.assertEqual(off.fields['name'].selectedText(), 'abc', UNSELECTED)
        for key in ('on', 'mode'):                                          # case, liste : le focus, sans sélection
            d = self.shown(ParamsDialog(None, 'Essai', P(), {key: labels[key], 'dist': 'Distance'},
                                        choices={'mode': [('a', 'A'), ('b', 'B')]}))
            self.assertIs(d.focusWidget(), d.fields[key])
            self.assertFalse(d.fields['dist'].lineEdit().hasSelectedText())


if __name__ == '__main__':
    unittest.main()
