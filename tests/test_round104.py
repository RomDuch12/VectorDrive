"""Round 104 : options F10 par onglets (toutes appliquées), case
« respecter les proportions » par défaut, BAT à 1:1 coté avec
agrandissement (petite pièce) ou réduction (trop grande)."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import geom
from vectordrive.core.document import Document, Plate, Shape
from vectordrive.io import proof
from vectordrive.ui import options


def app():
    return QApplication.instance() or QApplication([])


def doc(w, h, plate=False):
    d = Document()
    d.plate = Plate(w + 2, h + 2) if plate else None
    d.add(Shape(path=geom.Path([geom.rect(0, 0, w, h)])))
    return d


class TestBatViews(unittest.TestCase):
    def views(self, d, **kw):
        return [(v['k'], v['label']) for v in proof._geometry(d, proof.ProofInfo(**kw))['views']]

    def test_small_piece_gets_enlargement(self):
        v = self.views(doc(20, 10))
        self.assertEqual(v[0], (1.0, 'Taille réelle'))
        self.assertEqual(v[1][1], 'Agrandissement')
        self.assertIn(v[1][0], proof.ENLARGEMENTS)

    def test_normal_and_big(self):
        self.assertEqual(self.views(doc(150, 80)), [(1.0, 'Taille réelle')])
        self.assertEqual(self.views(doc(400, 300)), [(0.4, 'Réduction')])                 # 1:2,5
        self.assertEqual(len(self.views(doc(60, 35), enlarge=True)), 2)                     # demandé
        self.assertEqual(len(self.views(doc(150, 80), enlarge=True)), 1)                    # ne tiendrait pas
        self.assertEqual(len(self.views(doc(20, 10), enlarge_below=10)), 1)                 # seuil réglé

    def test_page_has_two_dimensioned_views(self):
        d = doc(20, 10, plate=True)
        prims, PW, PH = proof.build(d, proof.ProofInfo())
        plates = [pr for pr in prims if pr.color == (0.45, 0.45, 0.45)]
        self.assertEqual(len(plates), 2)                                                    # une plaque par vue
        blue = [pr for pr in prims if pr.color == (0.1, 0.25, 0.55) and pr.width > 0]
        self.assertEqual(len(blue), 4)                                                      # 2 cotes × 2 vues
        widths = sorted(pr.path.bbox()[2] - pr.path.bbox()[0] for pr in plates)
        self.assertAlmostEqual(widths[0], 22, places=6)                                     # vraie grandeur
        self.assertGreater(widths[1], 22 * 2)

    def test_old_modes_still_there(self):
        self.assertAlmostEqual(proof.page_scale(doc(20, 10), proof.ProofInfo(scale_mode='normalisee')), 10)
        self.assertEqual(len(proof._geometry(doc(20, 10), proof.ProofInfo(scale_mode='reelle'))['views']), 1)


class TestOptions(unittest.TestCase):
    def setUp(self):
        app()
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()

    def tearDown(self):
        for key in list(options.BY_KEY):
            self.w.settings.remove(key)
        self.w.settings.setValue('accrochage/retenir', False)     # la graine des essais (round 1153)
        self.w.settings.setValue('options/accrochage', False)     # … accrochage éteint, rien de retenu (round 1159)
        from tests import SNAP_STATE
        for key in SNAP_STATE:
            self.w.settings.remove(key)
        self.w.modified = False
        self.w.close()

    def test_every_option_has_a_widget_and_roundtrips(self):
        dlg = self.w.options_dialog(exec_dialog=False)
        self.assertEqual(set(dlg.widgets), set(options.BY_KEY))
        self.assertGreaterEqual(len(options.BY_KEY), 45)
        self.assertGreaterEqual(dlg.tabs.count(), 8)
        dlg.restore_defaults()
        dlg.accept()
        for key, o in options.BY_KEY.items():
            if o.kind != 'font':                                     # police selon le poste
                self.assertEqual(options.value(self.w.settings, key), o.default, key)

    def test_options_take_effect(self):
        st = self.w.settings
        st.setValue('options/proportions', False)
        st.setValue('vue/zoom_pas', 2.0)
        st.setValue('vue/poignees', 11)
        st.setValue('options/decimales', 1)
        st.setValue('plaque/largeur', 210.0)
        st.setValue('plaque/hauteur', 297.0)
        st.setValue('plaque/epaisseur', 3.0)
        st.setValue('fao/z_degagement', 7.5)
        self.w.apply_options()
        self.assertFalse(self.w.dims.keep.isChecked())
        self.assertEqual((self.w.zoom_step, self.w.canvas.handle_px), (2.0, 11))
        self.assertEqual(self.w.dims.fields['x'].decimals(), 1)
        self.w.new_document()
        p = self.w.canvas.doc.plate
        self.assertEqual((p.width, p.height, p.thickness), (210.0, 297.0, 3.0))
        self.w.canvas.doc.add(Shape(path=geom.Path([geom.rect(0, 0, 10, 5)])))
        self.w.cam_panel.ops_from_colors()
        self.assertEqual(self.w.cam_panel.setup().operations[0].safe_z, 7.5)
        st.setValue('options/proportions', True)
        self.w.apply_options()
        self.assertTrue(self.w.dims.keep.isChecked())

    def test_companion_mode(self):
        from vectordrive.io import companion
        d = doc(10, 5)
        with tempfile.TemporaryDirectory() as tmp:
            f = os.path.join(tmp, 'p.vnd')
            from vectordrive.io.vnd_write import write
            write(d, f)
            self.assertEqual(companion.sync(d, f, mode='besoin'), (None, []))
            cp, why = companion.sync(d, f, mode='toujours')
            self.assertTrue(cp.exists() and why)
            self.assertEqual(companion.sync(d, f, mode='jamais'), (None, []))
            self.assertFalse(cp.exists())


if __name__ == '__main__':
    unittest.main()
