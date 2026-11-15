"""Round 1008 : la surépaisseur dit ce qu'elle est (réponse 19 du 14/11) — le libellé du champ suit le parcours
choisi : XY le long des flancs (contour, poche, reprise, découpe 3D, gravure en V), 3D en XY et en Z (parcours 3D),
largeur du chanfrein (ébavurage des trous)."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1008.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])

from vectordrive.cam import model  # noqa: E402
from vectordrive.i18n import tr  # noqa: E402
from vectordrive.ui import cam_panel as CP  # noqa: E402


class StockLabel(unittest.TestCase):

    def open(self, kind):
        d = CP.FieldsDialog(None, 'essai', model.Operation(kind=kind))
        self.addCleanup(d.deleteLater)
        return d

    def label(self, d) -> str:
        return d.rows['stock'][0].text()

    def test_xy_3d_or_chamfer(self):
        self.assertEqual(CP.field_label('stock', 'poche'), CP.STOCK_XY)
        self.assertEqual(CP.field_label('stock', 'surface3d'), CP.STOCK_3D)
        self.assertIn('XY', CP.STOCK_XY)
        self.assertIn('Z', CP.STOCK_3D)
        self.assertNotIn('Z', CP.STOCK_XY)
        self.assertEqual(CP.field_label('stock'), CP.LABELS['stock'])           # sans parcours : le libellé général
        self.assertEqual(CP.field_label('depth', 'poche'), CP.LABELS['depth'])  # les autres champs : inchangés
        # chaque parcours qui montre le champ a son libellé précis
        self.assertEqual({k for k, fields in CP.KIND_FIELDS.items() if 'stock' in fields}, set(CP.STOCK_LABELS))

    def test_the_form_follows_the_toolpath(self):
        for kind in ('contour', 'poche', 'reste', 'decoupe3d', 'vcarve'):
            self.assertEqual(self.label(self.open(kind)), tr(CP.STOCK_XY), kind)
        for kind in ('relief', 'surface3d', 'ebauche3d', 'reprise3d', 'niveaux3d'):
            self.assertEqual(self.label(self.open(kind)), tr(CP.STOCK_3D), kind)
        self.assertIn('chanfrein', self.label(self.open('chanfrein')))
        d = self.open('contour')                                                # changé dans le formulaire : il suit
        kinds = d.widgets['kind']
        kinds.setCurrentIndex(kinds.findData('surface3d'))
        self.assertEqual(self.label(d), tr(CP.STOCK_3D))
        kinds.setCurrentIndex(kinds.findData('poche'))
        self.assertEqual(self.label(d), tr(CP.STOCK_XY))
        self.assertFalse(d.rows['stock'][0].isHidden())

    def test_a_new_toolpath_of_the_palette(self):
        # parcours de la palette : la stratégie est fixée, la liste masquée ; le libellé est celui du parcours
        d = CP.FieldsDialog(None, 'essai', model.Operation(kind='surface3d'), preset='surface3d')
        self.addCleanup(d.deleteLater)
        self.assertTrue(d.fixed_kind)
        self.assertEqual(self.label(d), tr(CP.STOCK_3D))
        self.assertIn('XY', CP.field_label('stock', 'finition25d'))         # le décalage XY s'ajoute à la 3D

    def test_the_gammes_and_the_automatic_3d(self):
        from PySide6.QtWidgets import QLabel
        from vectordrive.core.document import Document
        from vectordrive.ui import auto3d_dialog as A3
        from vectordrive.ui.gamme_dialog import GammeDialog
        s = model.setup_of(Document())
        t = model.CamTool(name='F2', diameter=2.0)
        s.tools[:] = [t]
        g = GammeDialog(None, s, [], 0.4)                                       # gravure en V, poche, reprise : XY
        self.addCleanup(g.deleteLater)
        texts = [lab.text() for lab in g.findChildren(QLabel)]
        self.assertIn(tr('Surépaisseur XY laissée pour la finition'), texts)
        self.assertNotIn(tr('Surépaisseur'), texts)
        self.assertIn('Surépaisseur 3D (mm)', A3.COLUMNS)                      # l'usinage 3D automatique : 3D
        self.assertNotIn('Surépaisseur (mm)', A3.COLUMNS)
        self.assertIn(tr(CP.STOCK_3D), A3._params_text({'stock': 0.2}))
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        self.addCleanup(w.close)
        panel = w.cam_panel
        setup = panel.setup()
        setup.tools.append(model.CamTool(name='F6', kind='fraise', diameter=6.0))
        panel._relief_gamme_dialog(setup, 0.15, 0.0, run=False)                 # la gamme relief : 3D
        texts = [lab.text() for lab in panel._gamme_dlg.findChildren(QLabel)]
        self.assertTrue(any('3D' in x and 'Surépaisseur' in x for x in texts), texts)
        self.assertFalse(any('XY laissée' in x for x in texts))


if __name__ == '__main__':
    unittest.main()
