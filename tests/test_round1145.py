"""Round 1145 (demande du 23/11) : clic droit sur les boutons du ruban → les réglages de la fonction, suite : Gomme et
Pinceau à aplat, Raccord et Chanfrein entre deux traits, Ligne de coupure, Cercle tangent, Simplifier, Symétrie
cyclique."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1145.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'
os.environ.setdefault('VECTORDRIVE_KEYS_MEMORY', '1')

from PySide6.QtWidgets import QApplication, QToolButton  # noqa: E402

app = QApplication.instance() or QApplication([])
BEFORE = 'avant : pas de réglages au clic droit sur cet outil'
KEYS = ('cad/gomme', 'cad/ligne_coupure', 'coins/fillet', 'coins/chamfer', 'dessin/cercle_tangent',
        'simplifier/precision', 'approximation/angle', 'cad/simplifier_reglages', 'cad/simplifier', 'symetrie/copies')


class Settings(unittest.TestCase):
    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        for k in KEYS:
            self.w.settings.remove(k)
            self.addCleanup(self.w.settings.remove, k)

    def tearDown(self):
        self.w.canvas.doc.modified = False
        self.w.modified = False
        self.w.close()
        self.w.deleteLater()
        app.processEvents()

    def test_every_new_tool_has_settings(self):
        w = self.w
        for k in ('tool_eraser', 'tool_blob', 'tool_fillet2', 'tool_chamfer2', 'tool_breakline', 'tool_tan_circle',
                  'node_simplify', 'sym_cyclic'):
            self.assertIn(k, w.A, k)
            self.assertIsNotNone(w._tool_settings(w.A[k]), f'{k} : {BEFORE}')

    def test_brush_radius(self):
        w = self.w
        got = w.brush_settings(params={'radius': 3.5})
        self.assertEqual(got, {'radius': 3.5})
        self.assertEqual(w.canvas.eraser_radius, 3.5)
        self.assertEqual(w._cad_value('gomme', 'radius', 1.0), 3.5)
        self.assertEqual(w.brush_settings(params={'radius': 0.0})['radius'], 0.05)   # jamais nul
        w.brush_settings(params={'radius': 2.0})
        from vectordrive.ui.main_window import MainWindow
        w2 = MainWindow()                                                   # retenu d'une session à l'autre
        try:
            self.assertEqual(w2.canvas.eraser_radius, 2.0)
        finally:
            w2.modified = False
            w2.close()
            w2.deleteLater()

    def test_brush_proposes_the_current_radius(self):
        w = self.w
        w.canvas.eraser_radius = 4.25                                       # changé par [ et ] pendant l'outil
        seen = {}
        real = w._ask

        def spy(key, title, spec, choices=None, params=None):
            seen['last'] = w.settings.value(f'cad/{key}')
            return real(key, title, spec, choices=choices, params=params)
        with mock.patch.object(w, '_ask', side_effect=spy):
            w.brush_settings(params={})
        self.assertEqual(seen['last'], {'radius': 4.25})
        self.assertEqual(w.canvas.eraser_radius, 4.25)

    def test_corner_sizes(self):
        w = self.w
        self.assertEqual(w.corner_settings('fillet', -3.0), -3.0)          # creusé : retenu tel quel
        self.assertEqual(float(w.settings.value('coins/fillet')), -3.0)
        self.assertEqual(w.canvas.fillet_radius, 3.0)                       # le raccord prend le rayon
        self.assertEqual(w.corner_settings('chamfer', 1.5), 1.5)
        self.assertEqual(w.canvas.chamfer_size, 1.5)
        self.assertIsNone(w.corner_settings('chamfer', 0.0))                # rien : rien de changé
        self.assertEqual(w.canvas.chamfer_size, 1.5)
        from vectordrive.ui import dialogs
        with mock.patch.object(dialogs.CornerDialog, 'exec', return_value=0):
            self.assertIsNone(w.corner_settings('fillet'))                  # Annuler
        self.assertEqual(float(w.settings.value('coins/fillet')), -3.0)

    def test_breakline(self):
        from vectordrive.ui import tools as T
        w = self.w
        got = w.breakline_settings(params={'size': 4.0, 'extension': 2.0})
        self.assertEqual(got, {'size': 4.0, 'extension': 2.0})
        self.assertEqual((w.canvas.breakline_size, w.canvas.breakline_ext), (4.0, 2.0))
        c = T.BreakLineTool(w.canvas)._contour((0.0, 0.0), (30.0, 0.0))
        b = c.bbox()
        self.assertAlmostEqual(b[0], -2.0, 6)                              # débord des deux côtés
        self.assertAlmostEqual(b[2], 32.0, 6)
        self.assertAlmostEqual(b[3] - b[1], 4.0, 6)                         # hauteur du zigzag
        self.assertEqual(w.breakline_settings(params={'size': -1.0, 'extension': -1.0}),
                         {'size': 0.0, 'extension': 0.0})
        w.breakline_settings(params={'size': 5.0, 'extension': 1.0})
        from vectordrive.ui.main_window import MainWindow
        w2 = MainWindow()
        try:
            self.assertEqual((w2.canvas.breakline_size, w2.canvas.breakline_ext), (5.0, 1.0))
        finally:
            w2.modified = False
            w2.close()
            w2.deleteLater()

    def test_tan_circle_radius_without_taking_the_tool(self):
        w = self.w
        self.assertEqual(w.tan_circle_settings(7.5), 7.5)
        self.assertEqual(float(w.settings.value('dessin/cercle_tangent')), 7.5)
        self.assertEqual(w.canvas.tan_circle_radius, 7.5)
        self.assertNotEqual(w.canvas.tool, 'tan_circle')
        from PySide6.QtWidgets import QInputDialog
        with mock.patch.object(QInputDialog, 'getDouble', return_value=(0.0, False)):
            self.assertIsNone(w.tan_circle_settings())
        with mock.patch.object(QInputDialog, 'getDouble', return_value=(2.0, True)) as g:
            self.assertEqual(w.tan_circle_settings(), 2.0)
        self.assertEqual(g.call_args.args[3], 7.5)                         # le dernier rayon proposé

    def test_simplify_settings(self):
        w = self.w
        got = w.simplify_settings(params={'precision': 0.2, 'corner': 50.0})
        self.assertEqual(got, {'precision': 0.2, 'corner': 50.0})
        self.assertEqual(float(w.settings.value('simplifier/precision')), 0.2)
        self.assertEqual(float(w.settings.value('approximation/angle')), 50.0)
        self.assertEqual(w.simplify_settings(params={'precision': 0.0, 'corner': 400.0}),
                         {'precision': 1e-4, 'corner': 180.0})

    def test_cyclic_copies_without_switching_on(self):
        w = self.w
        self.assertEqual(w.cyclic_settings(12), 12)
        self.assertEqual(w.cyclic_n.value(), 12)
        self.assertEqual(int(w.settings.value('symetrie/copies')), 12)
        self.assertFalse(w.A['sym_cyclic'].isChecked())
        self.assertEqual(w.cyclic_settings(500), 72)                        # dans les bornes du compteur
        from PySide6.QtWidgets import QInputDialog
        with mock.patch.object(QInputDialog, 'getInt', return_value=(8, True)) as g:
            self.assertEqual(w.cyclic_settings(), 8)
        self.assertEqual(g.call_args.args[3], 72)

    def test_right_click_menu_has_them_first(self):
        w = self.w
        seen = 0
        for k in ('tool_eraser', 'tool_fillet2', 'tool_chamfer2', 'tool_breakline', 'node_simplify'):
            btn = next((b for b in w.ribbon.findChildren(QToolButton) if b.defaultAction() is w.A[k]), None)
            if btn is None:
                continue                                                    # pas dans le ruban de ce mode
            seen += 1
            m = w._ribbon_button_menu(btn, btn.mapToGlobal(btn.rect().center()), exec_menu=False,
                                      settings=w._tool_settings(w.A[k]))
            self.assertIsNotNone(m.defaultAction(), k)
        self.assertGreater(seen, 0)                                         # au moins un bouton essayé

    def test_negative_fillet_kept_after_restart(self):
        self.w.corner_settings('fillet', -3.0)
        from vectordrive.ui.main_window import MainWindow
        w2 = MainWindow()                                                   # relancé : toujours un congé de 3
        try:
            self.assertEqual(w2.canvas.fillet_radius, 3.0)
        finally:
            w2.modified = False
            w2.close()
            w2.deleteLater()

    def test_simplify_dialog_proposes_the_same_precision(self):
        w = self.w
        w.simplify_settings(params={'precision': 0.3, 'corner': 40.0})
        self.assertEqual(w._cad_value('simplifier', 'precision', 0.0), 0.3)


if __name__ == '__main__':
    unittest.main()
