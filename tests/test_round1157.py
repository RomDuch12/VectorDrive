"""Round 1157 : « Toutes les icones : redessiner en plus détaillé et utilisant plusieurs couleurs éventuellement
attention aux thèmes); » — icônes en aplats de couleur, palette tirée du thème."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1157.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import QSize  # noqa: E402
from PySide6.QtGui import QIcon  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from vectordrive.ui import icons  # noqa: E402
from vectordrive.ui import theme as TH  # noqa: E402
from vectordrive.ui import themes as T  # noqa: E402

app = QApplication.instance() or QApplication([])
BEFORE = 'avant : deux encres seulement (encre et accent), pas de palette'
#: icônes les plus vues : chacune doit porter au moins trois couleurs franches
CLES = ('new', 'open', 'save', 'import', 'export', 'print', 'pdf', 'copy', 'paste', 'cut', 'duplicate', 'zoom_in',
        'grid', 'rect', 'group', 'align_left', 'node', 'cam', 'options', 'assistant_ia')


def image(name, mode=QIcon.Mode.Normal):
    return icons.icon(name).pixmap(QSize(64, 64), mode).toImage()


def pleins(img):
    """Les pixels bien opaques d'une image, en (r, v, b)."""
    out = []
    for y in range(img.height()):
        for x in range(img.width()):
            c = img.pixelColor(x, y)
            if c.alpha() > 200:
                out.append((c.red(), c.green(), c.blue()))
    return out


def teintes(img):
    """Nombre de couleurs franches : les pixels opaques, par paquets de 32 niveaux, qui couvrent au moins 12 px."""
    n = {}
    for r, g, b in pleins(img):
        k = (r >> 5, g >> 5, b >> 5)
        n[k] = n.get(k, 0) + 1
    return sum(1 for v in n.values() if v >= 12)


def a_la_couleur(img, color):
    """L'image a-t-elle un aplat de cette couleur (au moins 12 px exacts) ?"""
    want = (color.red(), color.green(), color.blue())
    return sum(1 for c in pleins(img) if c == want) >= 12


class TestIcons(unittest.TestCase):
    def setUp(self):
        TH.apply_theme(app, 'clair')
        self.addCleanup(TH.apply_theme, app, 'clair')

    def palette(self):
        """La palette posée pour le thème appliqué : nom → QColor."""
        self.assertTrue(hasattr(icons, '_palette'), BEFORE)
        icons._charge(icons._palette())
        return dict(icons._PAL)

    def test_palette_from_theme(self):
        self.assertTrue(hasattr(icons, '_palette'), BEFORE)
        clair = icons._palette()
        self.assertEqual(len(clair), 3 + len(icons.TEINTES))
        self.assertEqual(clair[:2], icons._inks())                       # encre et accent du thème, comme avant
        self.assertEqual(len(icons._inks()), 2)                          # (ui/cam_panel s'en sert)
        pal = self.palette()
        for k in ('ink', 'accent', 'paper', 'blue', 'green', 'gold', 'red', 'grey', 'blue_f', 'gold_f', 'shade'):
            self.assertIn(k, pal)
        self.assertGreater(T.luminance(pal['paper'].name()), T.luminance(pal['ink'].name()))   # papier clair
        TH.apply_theme(app, 'sombre')
        sombre = icons._palette()
        self.assertNotEqual(clair[3:], sombre[3:])                       # d'autres teintes sur fond sombre
        pal = self.palette()
        self.assertLess(T.luminance(pal['paper'].name()), T.luminance(pal['ink'].name()))      # papier sous l'encre
        bg = sombre[2]
        for k in ('blue', 'green', 'gold', 'red', 'grey'):               # chaque teinte se détache du fond
            self.assertGreater(T.contrast(pal[k].name(), bg), 3.0, k)
        TH.apply_theme(app, 'clair')
        bg = clair[2]
        pal = self.palette()
        for k in ('blue', 'green', 'red', 'grey'):
            self.assertGreater(T.contrast(pal[k].name(), bg), 3.0, k)

    def test_every_icon_draws_in_light_and_dark(self):
        self.assertTrue(hasattr(icons, '_palette'), BEFORE)
        self.assertGreaterEqual(len(icons.ICONS), 286)
        for key in ('clair', 'sombre'):
            TH.apply_theme(app, key)
            for name in icons.ICONS:
                ic = icons.icon(name)
                self.assertFalse(ic.isNull(), (key, name))
                pm = ic.pixmap(QSize(64, 64))
                self.assertEqual((pm.width(), pm.height()), (64, 64), (key, name))
                self.assertGreater(len(pleins(pm.toImage())), 60, (key, name))        # non vide
        for key in ('contraste_clair', 'contraste_sombre', 'typeedit13', 'terminal'):  # tout thème : sans erreur
            TH.apply_theme(app, key)
            for name in icons.ICONS:
                self.assertFalse(icons.icon(name).isNull(), (key, name))
        TH.apply_theme(app, 'clair')
        for name in CLES:                                                # encore là une fois grisée (désactivé)
            gris = image(name, QIcon.Mode.Disabled)
            self.assertGreater(sum(1 for y in range(64) for x in range(64) if gris.pixelColor(x, y).alpha() > 40),
                               200, name)

    def test_key_icons_have_several_colours(self):
        for key in ('clair', 'sombre'):
            TH.apply_theme(app, key)
            for name in CLES:
                self.assertGreaterEqual(teintes(image(name)), 3, (key, name, BEFORE))
            pal = self.palette()
            self.assertTrue(a_la_couleur(image('save'), pal['blue_f']), key)        # disquette bleue
            self.assertTrue(a_la_couleur(image('save'), pal['paper']), key)         # et son étiquette de papier
            self.assertTrue(a_la_couleur(image('open'), pal['gold_f']), key)        # dossier or
            self.assertTrue(a_la_couleur(image('new'), pal['paper']), key)          # feuille
            self.assertTrue(a_la_couleur(image('new'), pal['green']), key)          # pastille + verte
            self.assertTrue(a_la_couleur(image('delete'), pal['red']), key)         # croix rouge
            self.assertTrue(a_la_couleur(image('rect'), pal['blue_f']), key)        # l'objet dessiné : bleu
            self.assertTrue(a_la_couleur(image('export'), pal['accent']), key)      # l'action : accent du thème

    def test_cache_follows_theme_palette(self):
        self.assertTrue(hasattr(icons, '_palette'), BEFORE)
        a = icons.icon('save')
        self.assertEqual(icons.icon('save').cacheKey(), a.cacheKey())    # gardée tant que le thème ne change pas
        TH.apply_theme(app, 'sombre')
        b = icons.icon('save')
        self.assertNotEqual(a.pixmap(64, 64).toImage(), b.pixmap(64, 64).toImage())
        TH.apply_theme(app, 'clair')
        self.assertEqual(icons.icon('save').cacheKey(), a.cacheKey())    # la même, reprise du cache
        # un thème qui ne change qu'une teinte (clé facultative icon_blue) : l'icône est refaite, à cette teinte
        clair = T.BUILTIN['clair']
        t = clair.copy(key='essai1157', colors={**clair.colors, 'icon_blue': '#aa00aa'})
        TH.apply(app, t)
        try:
            self.assertEqual(icons._palette()[:2], icons._inks())        # même encre, même accent
            c = icons.icon('save')
            self.assertNotEqual(c.cacheKey(), a.cacheKey())
            self.assertNotEqual(c.pixmap(64, 64).toImage(), a.pixmap(64, 64).toImage())
            pal = self.palette()
            self.assertEqual(pal['blue'].name(), '#aa00aa')
            self.assertTrue(a_la_couleur(c.pixmap(64, 64).toImage(), pal['blue_f']))
        finally:
            TH.apply_theme(app, 'clair')

    def test_unknown_name_gives_default_icon(self):
        pal = self.palette()
        inconnu = image('icone_qui_n_existe_pas_1157')
        self.assertEqual(inconnu, image('new'))                          # la feuille blanche, comme avant
        self.assertTrue(a_la_couleur(inconnu, pal['paper']))
        self.assertNotIn('icone_qui_n_existe_pas_1157', icons.ICONS)

    def test_names_kept_and_distinct(self):
        self.assertTrue(hasattr(icons, '_palette'), BEFORE)
        for name in ('select', 'undo', 'redo', 'zoom_fit', 'union', 'xor', 'snap_grid', 'node_align_v', 'view_zx',
                     'order_backward', 'unfreeze', 'show_all', 'distribute_vc', 'tab_assistant', 'text_preset_save',
                     'wrap_cone', 'origin', 'shape_script', 'clock', 'cam_post', 'library'):
            self.assertIn(name, icons.ICONS)
        # des commandes voisines ne partagent pas le même dessin
        for a, b in (('undo', 'redo'), ('import', 'export'), ('zoom_in', 'zoom_out'), ('distribute_h', 'distribute_hc'),
                     ('distribute_v', 'distribute_vc'), ('union', 'xor'), ('freeze', 'unfreeze'), ('hide', 'show_all'),
                     ('order_front', 'order_forward'), ('library', 'group'), ('text_horizontal', 'text_vertical')):
            self.assertNotEqual(image(a), image(b), (a, b))


if __name__ == '__main__':
    unittest.main()
