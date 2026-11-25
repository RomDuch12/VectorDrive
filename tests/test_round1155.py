"""Round 1155 (demande du 24/11) : « Click droit sur boutons_rubans aussi en mode ruban TE; ». En disposition
TypeEdit 13, le clic droit sur tout bouton du ruban donne le menu de la disposition VectorDrive : boutons Mode
(réglages de l'outil, favoris, onglets à soi par leur commande), onglet « VectorDrive » (taille et place), barre
d'accès rapide (menu du bouton, réglages de l'outil en tête) ; taille et place retenues d'une reconstruction à l'autre.
La disposition TypeEdit est fabriquée (script synthétique) : aucun fichier de TypeEdit n'est lu."""
import json
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1155.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'
os.environ.setdefault('VECTORDRIVE_KEYS_MEMORY', '1')

from PySide6.QtCore import QPoint  # noqa: E402
from PySide6.QtGui import QContextMenuEvent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])

from vectordrive.ui import typeedit_layout as TL  # noqa: E402

SCRIPT = """' script de ruban synthétique (même syntaxe que TypeEdit)
set categoryCAD = configProduct.AddCategoryFromID(307)
set panelMode = categoryCAD.AddPanelFromID(506)
cmd = "ID_COMPO_SHOWPALSHAPE"
set b1 = panelMode.AddButton(cmd,true,false)
b1.SetContextID(1001)
cmd = "ID_COMPO_SHOWPALPOINT"
set b2 = panelMode.AddButton(cmd,true,false)
b2.SetContextID(1009)
cmd = "ID_COMPO_SHOWPALDUPLICATION"
set b3 = panelMode.AddButton(cmd,true,false)
b3.SetContextID(1006)
cmd = "ID_COMPO_TEXTLIBRE"
set b4 = panelMode.AddButton(cmd,true,false)
b4.SetContextID(idContextRapido)
set panelDraw = categoryCAD.AddPanelFromID(507)
cmd = "ID_PALETTE_ETOILE"
panelDraw.AddButton cmd,true,false
cmd = "ID_ZONE_GROUP"
panelDraw.AddButton cmd,true,false
cmd = "ID_PALETTE_MESURE_COTATION"
panelDraw.AddButton cmd,false,false
set panelObj = categoryCAD.AddPanelFromID(508)
cmd = "ID_ZONE_UNGROUP"
panelObj.AddButton cmd,true,false
cmd = "ID_MANIPULER_ZONE_COMBINER"
panelObj.AddButton cmd,true,false
set c1 = configProduct.AddContextCategoryFromID(316,-1,1001)
set s1 = c1.AddPanelFromID(599)
cmd = "ID_BACKTO"
set k1 = s1.AddButton(cmd,true,false)
k1.SetTypeExitContextCategory(true)
set p1 = c1.AddPanelFromID(316)
cmd = "ID_PALETTE_RECTANGLE"
p1.AddButton cmd,true,false
set c5 = configProduct.AddContextCategoryFromID(320,-1,1009)
set s5 = c5.AddPanelFromID(599)
cmd = "ID_BACKTO"
set k5 = s5.AddButton(cmd,true,false)
k5.SetTypeExitContextCategory(true)
set p5 = c5.AddPanelFromID(320)
cmd = "ID_RETOUCHE_STARTPOINT"
p5.AddButton cmd,true,false
set c4 = configProduct.AddContextCategoryFromID(319,-1,1006)
set s4 = c4.AddPanelFromID(599)
cmd = "ID_BACKTO"
set k4 = s4.AddButton(cmd,true,false)
k4.SetTypeExitContextCategory(true)
set p4 = c4.AddPanelFromID(319)
cmd = "ID_COMPO_DUPSURCOURBE"
p4.AddButton cmd,true,false
set c6 = configProduct.AddContextCategoryFromID(321,-1,idContextRapido)
set s6 = c6.AddPanelFromID(599)
cmd = "ID_BACKTO"
set k6 = s6.AddButton(cmd,true,false)
k6.SetTypeExitContextCategory(true)
set p6 = c6.AddPanelFromID(321)
cmd = "ID_RAPIDO_CHAR_PBITALIC"
p6.AddButton cmd,true,false
"""
STRINGS = {307: 'TypeEdit', 316: 'Formes géométriques', 319: 'Duplication', 320: 'Point', 321: 'Rapido',
           506: 'Mode', 507: 'Dessin', 508: 'Objets', 599: 'Retour'}
QAT = """[QAT]
StateOnTop=1
NbCommand=4
QAT_CMD_0=ID_FILE_NEW
QAT_CMD_1=ID_PALETTE_ETOILE
QAT_CMD_2=ID_COMPO_SHOWPALSHAPE
QAT_CMD_3=ID_COMPO_TEXTLIBRE
"""
SIZE, PLACE = 'Taille du bouton', 'Position du bouton'
FAV, UNFAV = 'Ajouter aux favoris (barre du haut)', 'Retirer des favoris (barre du haut)'
SIMPLE = ('Montrer aussi en mode simple', 'Réserver au mode expert')


def layout():
    lay = TL.parse(SCRIPT, STRINGS)
    lay.quick, lay.quick_on_top = TL.quick_access(QAT)
    return lay


def forget():
    from vectordrive import portable
    s = portable.settings()
    for k in ('ruban/boutons', 'ruban/favoris', 'vue/theme'):
        s.remove(k)
    s.sync()


def close(w):
    from shiboken6 import isValid
    if not isValid(w):
        return
    w.modified = False
    for t in getattr(w, 'docs', []):
        t.modified = False
    w.close()
    app.processEvents()


def texts(m):
    return [a.text().replace('&', '') for a in m.actions() if not a.isSeparator()]


def te_groups(w, context=False):
    """Les groupes des onglets de la disposition TypeEdit (sans, ou avec, les onglets contextuels)."""
    r = w.ribbon
    out = []
    for i in range(r.count()):
        tab = r.widget(i)
        if tab.property('te_layout') and (context or not tab.property('te_context')):
            out += r.page(i).groups()
    return out


def te_button(w, action):
    return next(b for g in te_groups(w) for b in g.buttons() if b.defaultAction() is action)


def mode_action(w, text):
    return next(a for a in w._te_actions if a.text() == text
                and str(a.property('vd_ribbon_id') or '').startswith('te_mode:'))


def vd_group(w):
    """Le groupe de l'onglet « VectorDrive » de la disposition TypeEdit (un bouton à menu par onglet de VectorDrive)."""
    return next(g for g in te_groups(w) if g.title.text() == 'Onglets de VectorDrive')


class Base(unittest.TestCase):
    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        forget()
        TL._cache.clear()
        patcher = mock.patch.object(TL, 'installed', return_value=layout())
        patcher.start()
        self.open = []                                   # les fenêtres à fermer
        self.addCleanup(self.clean, patcher)
        self.w = w = MainWindow()
        self.open.append(w)
        w.set_theme('typeedit13')
        self.assertTrue(w.layout_active)

    def clean(self, patcher):
        for w in self.open:
            w.set_theme('clair')                         # (le thème est retenu : les essais suivants)
            close(w)
        patcher.stop()
        TL._cache.clear()
        forget()

    def right_click(self, btn):
        """Le clic droit sur `btn` par le filtre de la fenêtre : le menu bâti, sans l'attendre ; None sans menu."""
        w = self.w
        menus = []
        real = type(w)._ribbon_button_menu

        def no_wait(win, *a, **k):
            k['exec_menu'] = False
            menus.append(real(win, *a, **k))
            return menus[-1]
        # (avant : hors du ruban, le clic droit ouvrait tout de suite la fenêtre de réglages d'une forme)
        with mock.patch.object(type(w), '_ribbon_button_menu', autospec=True, side_effect=no_wait), \
                mock.patch.object(type(w), 'tool_form_dialog'), mock.patch.object(type(w), '_fav_bar_menu'):
            QApplication.sendEvent(btn, QContextMenuEvent(QContextMenuEvent.Reason.Mouse, QPoint(2, 2),
                                                          btn.mapToGlobal(QPoint(2, 2))))
        for m in menus:
            self.addCleanup(m.deleteLater)
        return menus[0] if len(menus) == 1 else None


class Ribbon(Base):
    def test_every_button_of_the_te_ribbon_has_size_and_place(self):
        w = self.w
        star = te_button(w, w.A['tool_star'])            # une commande ordinaire : comme en disposition VectorDrive
        m = self.right_click(star)
        t = texts(m)
        self.assertIs(m.defaultAction(), m.actions()[0])
        self.assertEqual(t[0], 'Réglages de « Étoile »…')
        for label in (SIZE, PLACE, FAV):
            self.assertIn(label, t)
        self.assertTrue(set(SIMPLE) & set(t))
        self.assertNotIn(t[0], texts(self.right_click(te_button(w, w.A['group']))), 'Grouper : pas de réglages')
        n = 0
        for g in te_groups(w, context=True):
            for b in g.buttons():
                m = w._ribbon_button_menu(b, QPoint(0, 0), exec_menu=False)
                self.addCleanup(m.deleteLater)
                name = f'{g.title.text()} › {b.defaultAction().text()}'
                self.assertIn(SIZE, texts(m), f'{name} — avant : rien pour les boutons de l’onglet « VectorDrive »')
                self.assertIn(PLACE, texts(m), name)
                n += 1
        self.assertGreater(n, 20)

    def test_mode_button_has_the_settings_of_its_tool(self):
        w = self.w
        text = te_button(w, mode_action(w, 'Texte'))
        m = self.right_click(text)
        t = texts(m)
        self.assertEqual(t[0], 'Réglages de « Texte »…', 'avant : ni réglages ni favoris pour un bouton Mode')
        self.assertIs(m.defaultAction(), m.actions()[0])
        with mock.patch.object(w, 'options_dialog') as od:
            m.defaultAction().trigger()
        od.assert_called_once_with(page='Dessin')        # ceux de l'outil Texte
        for label in (SIZE, PLACE, FAV, 'Ajouter à un nouvel onglet…'):
            self.assertIn(label, t)
        self.assertFalse(set(SIMPLE) & set(t), 'un bouton Mode est toujours montré : pas de mode simple')
        shapes = self.right_click(te_button(w, mode_action(w, 'Formes géométriques')))
        self.assertIsNone(shapes.defaultAction(), 'une famille sans réglages')
        self.assertIn(FAV, texts(shapes))
        back = next(b for g in te_groups(w, context=True) for b in g.buttons()
                    if b.defaultAction().property('vd_ribbon_id') == 'te_retour')
        t = texts(self.right_click(back))                # Retour : pas une commande, sa taille et sa place seulement
        self.assertIn(SIZE, t)
        self.assertNotIn(FAV, t)

    def test_mode_button_puts_its_command_in_the_favorites(self):
        w = self.w
        dup = te_button(w, mode_action(w, 'Duplication'))
        m = self.right_click(dup)
        act = next((a for a in m.actions() if a.text() == FAV), None)
        self.assertIsNotNone(act, 'avant : pas de favoris pour un bouton Mode')
        act.trigger()
        self.assertEqual(w.favorite_keys(), ['duplicate'])
        self.assertIn(w.A['duplicate'], w.te_quickbar.actions(), 'à la suite de la barre d’accès rapide')
        m = self.right_click(dup)
        self.assertIn(UNFAV, texts(m))
        next(a for a in m.actions() if a.text() == UNFAV).trigger()
        self.assertEqual(w.favorite_keys(), [])
        m = self.right_click(dup)
        with mock.patch.object(w, 'add_to_custom_tab') as add:
            next(a for a in m.actions() if a.text() == 'Ajouter à un nouvel onglet…').trigger()
        add.assert_called_once_with('duplicate', -1)

    def test_vd_tab_buttons_take_size_and_place(self):
        w = self.w
        g = vd_group(w)
        ids = [w._button_id(b) for b in g.buttons()]
        self.assertTrue(all(i and i.startswith('te_onglet:') for i in ids), f'avant : boutons sans identité — {ids}')
        self.assertEqual(len(ids), len(set(ids)), 'un identifiant par bouton')
        self.assertGreater(len(ids), 3)
        self.assertEqual(g.group_id, 'te:' + ids[0])
        first = g.buttons()[0]
        self.assertIsNotNone(first.defaultAction().menu(), 'toujours un bouton à menu')
        self.assertTrue(w.ribbon_button_op(first, 'small'))
        self.assertIs(g.entry_big(first), False)
        self.assertTrue(w.ribbon_button_op(first, 'last'))
        self.assertEqual([w._button_id(b) for b in g.buttons()], ids[1:] + ids[:1])
        conf = json.loads(w.settings.value('ruban/boutons'))
        self.assertEqual(conf[g.group_id][-1], [ids[0], False])
        t = texts(self.right_click(first))
        self.assertIn('Taille et place d’origine', t)
        self.assertNotIn(FAV, t, 'un menu d’onglet n’est pas une commande : pas de favoris')
        self.assertTrue(w.ribbon_button_op(first, 'reset'))
        self.assertEqual([w._button_id(b) for b in g.buttons()], ids)
        self.assertIs(g.entry_big(first), True)
        self.assertIsNone(w.settings.value('ruban/boutons'))


class QuickBar(Base):
    def button(self, action):
        b = self.w.te_quickbar.widgetForAction(action)
        self.assertIsNotNone(b)
        return b

    def test_quick_bar_button_opens_the_button_menu(self):
        w = self.w
        m = self.right_click(self.button(w.A['tool_star']))
        self.assertIsNotNone(m, 'avant : la fenêtre de réglages tout de suite, sans menu')
        t = texts(m)
        self.assertEqual(t[0], 'Réglages de « Étoile »…')
        self.assertIs(m.defaultAction(), m.actions()[0])
        self.assertIn(FAV, t)
        self.assertNotIn(SIZE, t, 'la barre d’accès rapide n’est pas le ruban : ni taille ni place')
        self.assertNotIn(PLACE, t)
        with mock.patch.object(type(w), 'tool_form_dialog') as dlg:
            m.defaultAction().trigger()
        dlg.assert_called_once_with('star')
        m = self.right_click(self.button(w.A['new']))    # une commande sans réglages : avant, rien du tout
        self.assertIsNotNone(m)
        self.assertIsNone(m.defaultAction())
        self.assertIn(FAV, texts(m))
        m = self.right_click(self.button(mode_action(w, 'Texte')))        # un bouton Mode : comme dans le ruban
        self.assertEqual(texts(m)[0], 'Réglages de « Texte »…')
        self.assertIn(FAV, texts(m))
        self.assertNotIn(SIZE, texts(m))

    def test_favorite_of_the_quick_bar_keeps_its_settings(self):
        w = self.w
        self.assertTrue(w.add_favorite('tool_rect'))     # disposition TypeEdit : à la suite de la barre d'accès rapide
        b = self.button(w.A['tool_rect'])
        self.assertTrue(w._is_favorite_button(b))
        m = self.right_click(b)
        t = texts(m)
        self.assertEqual(t[0], 'Réglages de « Rectangle »…', 'avant : le menu des favoris sans les réglages')
        for label in (UNFAV, 'Afficher les libellés', 'Agencer les favoris à la souris'):
            self.assertIn(label, t)
        self.assertNotIn(SIZE, t)


class Rebuild(Base):
    def state(self, w):
        g = vd_group(w)
        mode = next(x for x in te_groups(w) if x.title.text() == 'Mode')
        draw = next(x for x in te_groups(w) if x.title.text() == 'Dessin')
        return ([w._button_id(b) for b in g.buttons()], g.entry_big(g.buttons()[-1]),
                [b.defaultAction().text() for b in mode.buttons()], draw.entry_big(te_button(w, w.A['tool_star'])))

    def test_size_and_place_kept_when_the_te_ribbon_is_rebuilt(self):
        from vectordrive.ui.main_window import MainWindow
        w = self.w
        g = vd_group(w)
        ids = [w._button_id(b) for b in g.buttons()]
        self.assertTrue(all(ids), 'avant : les boutons de l’onglet « VectorDrive » n’avaient ni taille ni place')
        first = g.buttons()[0]
        self.assertTrue(w.ribbon_button_op(first, 'small'))
        self.assertTrue(w.ribbon_button_op(first, 'last'))
        self.assertTrue(w.ribbon_button_op(te_button(w, mode_action(w, 'Formes géométriques')), 'right'))
        self.assertTrue(w.ribbon_button_op(te_button(w, w.A['tool_star']), 'small'))
        want = (ids[1:] + ids[:1], False, ['Point', 'Formes géométriques', 'Duplication', 'Texte'], False)
        self.assertEqual(self.state(w), want)
        saved = w.settings.value('ruban/boutons')
        w.set_theme('clair')                             # disposition VectorDrive : le ruban TypeEdit défait…
        self.assertFalse(w.layout_active)
        self.assertEqual(w.settings.value('ruban/boutons'), saved, 'les réglages de TypeEdit 13 gardés pour lui')
        w.set_theme('typeedit13')                        # … et refait : des boutons neufs, rangés comme choisi
        self.assertTrue(w.layout_active)
        self.assertEqual(self.state(w), want)
        close(w)                                         # au lancement suivant
        self.open.remove(w)
        w2 = MainWindow()
        self.open.append(w2)
        self.assertTrue(w2.layout_active)
        self.assertEqual(self.state(w2), want)
        m = w2._ribbon_button_menu(vd_group(w2).buttons()[-1], QPoint(0, 0), exec_menu=False)
        self.addCleanup(m.deleteLater)
        next(a for a in m.actions() if a.text() == 'Taille et place d’origine').trigger()
        self.assertEqual([w2._button_id(b) for b in vd_group(w2).buttons()], ids)


if __name__ == '__main__':
    unittest.main()
