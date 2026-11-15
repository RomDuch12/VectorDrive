"""Round 1009 : les modèles d'un parcours en liste à colonnes (demande du 14/11) — la liste déroulante « Modèle » du
formulaire se déroule en tableau : dossier, outil, diamètre, profondeur, passe, avance, origine, description ; filtre à
la frappe, tri par colonne (les nombres comme des nombres), colonnes au choix, le tout retenu."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1009.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication, QComboBox  # noqa: E402

app = QApplication.instance() or QApplication([])

from vectordrive import portable  # noqa: E402
from vectordrive.cam import model  # noqa: E402
from vectordrive.cam import templates as TPL  # noqa: E402
from vectordrive.ui import cam_panel as CP  # noqa: E402

#: nom, dossier, profondeur, passe, outil, Ø de l'outil, avance, description
MODELS = (('Laiton fin', 'Laiton', 0.3, 0.1, 'Pointe 0.5', 0.5, 300.0, 'Gravure de plaque'),
          ('Laiton profond', 'Laiton', 10.0, 0.5, 'Cyl 2', 2.0, 600.0, ''),
          ('Alu ébauche', '', 2.0, 1.0, 'Cyl 6', 6.0, 1500.0, 'Évidage rapide'),
          ('Inox', '', 1.5, 0.25, 'Boule 3', 3.0, 200.0, ''))


def full(name, folder) -> str:
    return f'{folder} / {name}' if folder else name


class Base(unittest.TestCase):

    def setUp(self):
        from vectordrive.ui import template_picker as TP
        self.TP = TP
        s = portable.settings()
        for k in (TP.STATE_KEY, TP.SIZE_KEY, TP.STATE_COLUMNS_KEY):
            s.remove(k)
        self.names = []
        for name, folder, depth, step, tool_name, dia, feed, desc in MODELS:
            op = model.Operation(kind='poche', depth=depth, step_down=step)
            tool = model.CamTool(name=tool_name, diameter=dia, number=1, feed=feed)
            tpl = TPL.single(op, tool, full(name, folder), 'poche', desc)
            if folder:
                tpl['dossier'] = folder
            TPL.save_user(tpl)
            self.names.append(tpl['name'])
        self.addCleanup(lambda: [TPL.delete_user(n) for n in self.names])

    def form(self, **kw):
        d = CP.FieldsDialog(None, 'essai', model.Operation(kind='poche'), templates=list(self.names), preset='poche',
                            **kw)
        self.addCleanup(d.deleteLater)
        return d

    def column(self, key) -> int:
        return self.TP.KEYS.index(key)


class Rows(Base):

    def test_what_a_row_shows(self):
        origin, tpl = TPL.all_templates()['Laiton / Laiton profond']
        row = self.TP.row_of('Laiton / Laiton profond', origin, tpl)
        self.assertEqual((row['name'], row['folder'], row['tool']), ('Laiton profond', 'Laiton', 'Cyl 2'))
        self.assertEqual((row['diameter'], row['depth'], row['step_down'], row['feed']), (2.0, 10.0, 0.5, 600.0))
        self.assertEqual((row['origin'], row['operations']), ('À moi', 1))
        bare = self.TP.row_of('Vide', 'plugin', {'name': 'Vide'})                # modèle sans rien : pas d'erreur
        self.assertEqual((bare['name'], bare['tool'], bare['depth'], bare['origin']), ('Vide', '', None, 'Fourni'))
        # l'outil montré est celui que le formulaire chargera : le premier du modèle
        two = {'name': 'Deux', 'operations': [{'kind': 'poche', 'tool_id': 'b', 'power': 40.0}],
               'tools': [{'id': 'a', 'name': 'A', 'diameter': 1.0}, {'id': 'b', 'name': 'B', 'diameter': 2.0}]}
        row = self.TP.row_of('Deux', 'utilisateur', two)
        self.assertEqual((row['tool'], row['diameter'], row['power']), ('A', 1.0, 40.0))


class Picker(Base):

    def test_the_form_drops_down_a_table(self):
        d = self.form()
        box = d.template_box
        self.assertIsInstance(box, self.TP.TemplateCombo)
        self.assertIsInstance(box, QComboBox)                                   # la liste ordinaire reste dessous
        self.assertEqual(box.count(), 1 + len(MODELS))
        self.assertEqual(box.names(), self.names)
        p = box.popup()
        self.assertEqual(p.tree.columnCount(), len(self.TP.COLUMNS))
        self.assertEqual(p.tree.topLevelItemCount(), len(MODELS))
        self.assertEqual(p.visible_names(),                                    # par nom, sans casse ni accents
                         ['Alu ébauche', 'Inox', 'Laiton / Laiton fin', 'Laiton / Laiton profond'])
        it = next(r for r in p.rows() if r.data(0, self.TP.ROLE + 1) == 'Laiton / Laiton fin')
        texts = {k: it.text(self.column(k)) for k in self.TP.KEYS}
        self.assertEqual(texts, {'name': 'Laiton fin', 'folder': 'Laiton', 'tool': 'Pointe 0.5', 'diameter': '0,5',
                                 'depth': '0,3', 'step_down': '0,1', 'feed': '300', 'power': '', 'origin': 'À moi',
                                 'description': 'Gravure de plaque'})
        self.assertIn('4', p.status.text())

    def test_filter(self):
        p = self.form().template_box.popup()
        p.filter.setText('LAITON')
        self.assertEqual(p.visible_names(), ['Laiton / Laiton fin', 'Laiton / Laiton profond'])
        self.assertIn('2', p.status.text())
        p.filter.setText('laiton plaque')                                       # tous les mots, toutes les colonnes
        self.assertEqual(p.visible_names(), ['Laiton / Laiton fin'])
        p.filter.setText('evidage')                                             # sans accents
        self.assertEqual(p.visible_names(), ['Alu ébauche'])
        p.filter.setText('boule')                                               # par l'outil
        self.assertEqual(p.visible_names(), ['Inox'])
        p.filter.setText('cyl')
        self.assertEqual(p.visible_names(), ['Alu ébauche', 'Laiton / Laiton profond'])
        p.filter.setText('zzz')
        self.assertEqual(p.visible_names(), [])
        p.filter.setText('')
        self.assertEqual(len(p.visible_names()), 4)

    def test_sorting_numbers_as_numbers(self):
        p = self.form().template_box.popup()
        p.tree.sortByColumn(self.column('depth'), Qt.SortOrder.AscendingOrder)
        self.assertEqual(p.visible_names(), ['Laiton / Laiton fin', 'Inox', 'Alu ébauche', 'Laiton / Laiton profond'])
        p.tree.sortByColumn(self.column('depth'), Qt.SortOrder.DescendingOrder)
        self.assertEqual(p.visible_names()[0], 'Laiton / Laiton profond')       # 10 après 2, pas « 10 » avant « 2 »
        p.tree.sortByColumn(self.column('feed'), Qt.SortOrder.AscendingOrder)
        self.assertEqual(p.visible_names(), ['Inox', 'Laiton / Laiton fin', 'Laiton / Laiton profond', 'Alu ébauche'])
        p.tree.sortByColumn(self.column('folder'), Qt.SortOrder.DescendingOrder)
        self.assertEqual(set(p.visible_names()[:2]), {'Laiton / Laiton fin', 'Laiton / Laiton profond'})

    def test_choosing_loads_the_template(self):
        d = self.form()
        box = d.template_box
        with mock.patch.object(d, 'load_template') as load:
            p = box.popup()
            p.choose('Inox')
            self.assertEqual(box.currentData(), 'Inox')
            load.assert_called_once_with('Inox')
            p = box.popup()                                                     # déroulée de nouveau : il est choisi
            self.assertEqual(p.tree.currentItem().data(0, self.TP.ROLE + 1), 'Inox')
            p.choose('Inox')                                                    # le même : ses réglages reviennent
            self.assertEqual(load.call_count, 2)
            p = box.popup()
            p.filter.setText('alu')
            p.tree.setCurrentItem(None)
            p._enter()                                                          # Entrée : le premier montré
            self.assertEqual(box.currentData(), 'Alu ébauche')
            p.choose('inconnu')                                                 # pas dans la liste : rien
            self.assertEqual(box.currentData(), 'Alu ébauche')

    def test_columns_and_sort_are_kept(self):
        box = self.form().template_box
        p = box.popup()
        m = p.columns_menu()
        self.addCleanup(m.deleteLater)
        boxes = [a for a in m.actions() if a.isCheckable()]
        self.assertEqual(len(boxes), len(self.TP.COLUMNS) - 1)                  # le nom ne se cache pas
        self.assertEqual([a.isChecked() for a in boxes],                        # la puissance laser : cachée d'office
                         [k not in self.TP.HIDDEN for k in self.TP.KEYS[1:]])
        p.set_column_shown(self.column('description'), False)
        p.set_column_shown(0, False)
        self.assertFalse(p.tree.header().isSectionHidden(0))
        p.tree.sortByColumn(self.column('diameter'), Qt.SortOrder.DescendingOrder)
        box.showPopup()
        p.resize(700, 300)                                                      # tirée à la poignée
        box.hidePopup()
        again = self.form().template_box.popup()                                # une autre fois
        h = again.tree.header()
        self.assertTrue(h.isSectionHidden(self.column('description')))
        self.assertFalse(h.isSectionHidden(self.column('tool')))
        self.assertEqual((h.sortIndicatorSection(), h.sortIndicatorOrder()),
                         (self.column('diameter'), Qt.SortOrder.DescendingOrder))
        self.assertEqual(again.visible_names()[0], 'Alu ébauche')               # Ø 6 d'abord
        self.assertEqual(again.wanted_size(200), (700, 300))
        self.assertEqual(again.wanted_size(1200)[0], 1200)                      # jamais plus étroite que la liste

    def test_a_saved_template_joins_the_table(self):
        d = self.form()
        d.save_template('Nouveau modèle')
        self.names.append('Nouveau modèle')
        self.assertIn('Nouveau modèle', d.template_box.popup().visible_names())


class Review(Base):
    """Constats de la relecture indépendante."""

    def test_filter_by_column_decimal_point_and_shown_text(self):
        p = self.form().template_box.popup()
        p.filter.setText('0.3')                                                 # le point vaut la virgule
        self.assertEqual(p.visible_names(), ['Laiton / Laiton fin'])
        p.filter.setText('outil:cyl')                                           # une seule colonne
        self.assertEqual(p.visible_names(), ['Alu ébauche', 'Laiton / Laiton profond'])
        p.filter.setText('dossier:laiton prof:10')
        self.assertEqual(p.visible_names(), ['Laiton / Laiton profond'])
        p.filter.setText('desc:laiton')                                         # « laiton » n'est pas dans la description
        self.assertEqual(p.visible_names(), [])
        p.filter.setText('Ø:6')
        self.assertEqual(p.visible_names(), ['Alu ébauche'])
        p.filter.setText('inconnue:laiton')                                     # pas une colonne : un mot ordinaire
        self.assertEqual(p.visible_names(), [])
        from vectordrive import i18n
        try:
            i18n.set_language('en')
            if all(i18n.tr(t) != t for t in self.TP.ORIGINS.values()):         # traductions versées (après la chaîne)
                p = self.form().template_box.popup()
                p.filter.setText('mine')                                        # l'origine telle qu'elle est montrée
                self.assertEqual(len(p.visible_names()), 4)
                p.filter.setText('tool:cyl')                                    # le titre montré de la colonne
                self.assertEqual(len(p.visible_names()), 2)
        finally:
            i18n.set_language('fr')

    def test_empty_cells_stay_last(self):
        p = self.form().template_box.popup()
        last = {'Alu ébauche', 'Inox'}                                          # sans dossier
        for order in (Qt.SortOrder.AscendingOrder, Qt.SortOrder.DescendingOrder):
            p.tree.sortByColumn(self.column('folder'), order)
            self.assertEqual(set(p.visible_names()[2:]), last, order)
            p.tree.sortByColumn(self.column('description'), order)
            self.assertEqual(set(p.visible_names()[2:]), {'Laiton / Laiton profond', 'Inox'}, order)

    def test_dropping_down_and_the_size_kept(self):
        TP = self.TP
        box = self.form().template_box
        p = box.popup()
        self.assertTrue(p.testAttribute(Qt.WidgetAttribute.WA_NoMouseReplay))  # un clic sur le combo : fermée
        box.setCurrentIndex(box.findData('Inox'))
        box.showPopup()
        self.assertTrue(p.isVisible())
        self.assertEqual(p.tree.currentItem().data(0, TP.ROLE + 1), 'Inox')
        self.assertIsNotNone(box._screen())
        p.filter.setText('alu')
        box.hidePopup()
        self.assertFalse(p.isVisible())
        self.assertIsNone(portable.settings().value(TP.SIZE_KEY))               # taille imposée : pas retenue
        self.assertIsNotNone(portable.settings().value(TP.STATE_KEY))           # colonnes : retenues
        box.showPopup()
        self.assertEqual(p.filter.text(), '')                                   # rouverte : filtre vidé
        self.assertEqual(len(p.visible_names()), 4)
        p.hide()

    def test_enter_on_opening_keeps_the_form(self):
        d = self.form()
        box = d.template_box
        with mock.patch.object(d, 'load_template') as load:
            box.popup().choose('Inox')
            self.assertEqual(load.call_count, 1)
            box.showPopup()
            p = box.popup()
            p._enter()                                                          # rien tapé, rien bougé : fermée
            self.assertEqual(load.call_count, 1)                                # les réglages changés restent
            self.assertFalse(p.isVisible())
            self.assertEqual(box.currentData(), 'Inox')

    def test_keyboard_between_filter_and_list(self):
        from PySide6.QtTest import QTest
        box = self.form().template_box
        box.showPopup()
        p = box.popup()
        self.addCleanup(p.hide)
        QTest.keyClick(p.filter, Qt.Key.Key_Down)                               # ↓ : dans la liste
        first = p.tree.currentItem()
        self.assertIsNotNone(first)
        QTest.keyClick(p.tree, 'l')                                             # la frappe va au filtre
        QTest.keyClick(p.tree, 'a')
        self.assertEqual(p.filter.text(), 'la')
        QTest.keyClick(p.tree, Qt.Key.Key_Backspace)
        self.assertEqual(p.filter.text(), 'l')
        p.filter.clear()
        p.tree.setCurrentItem(next(it for it in p.rows() if not it.isHidden()))
        with mock.patch.object(p.filter, 'setFocus') as focus:
            QTest.keyClick(p.tree, Qt.Key.Key_Up)                               # ↑ sur la première ligne : au filtre
        focus.assert_called()

    def test_no_template_from_the_drop_down(self):
        d = self.form()
        box = d.template_box
        box.popup().choose('Inox')
        box.showPopup()
        p = box.popup()
        self.assertTrue(p.none_button.isVisibleTo(p))
        self.assertEqual(p.none_button.text(), box.itemText(0))                 # « (réglages ci-dessous) »
        p.none_button.click()
        self.assertEqual(box.currentIndex(), 0)
        self.assertFalse(p.isVisible())

    def test_second_click_of_a_double_click(self):
        from PySide6.QtCore import QPointF, QRect
        from PySide6.QtGui import QMouseEvent
        from PySide6.QtWidgets import QWidget

        class Target(QWidget):
            pressed = 0

            def mousePressEvent(self, ev):                                      # noqa: N802
                Target.pressed += 1

        t = Target()
        self.addCleanup(t.deleteLater)

        def press(x, kind=QMouseEvent.Type.MouseButtonPress):
            ev = QMouseEvent(kind, QPointF(1, 1), QPointF(x, 10), Qt.MouseButton.LeftButton,
                             Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
            QApplication.sendEvent(t, ev)

        sw = self.TP._SwallowClicks(QRect(0, 0, 100, 100))
        press(500)                                                              # ailleurs : passe
        self.assertEqual(Target.pressed, 1)
        press(50)                                                               # là où était la liste : retenu
        self.assertEqual(Target.pressed, 1)
        press(50, QMouseEvent.Type.MouseButtonRelease)                          # le double clic fini : plus rien
        press(50)
        self.assertEqual(Target.pressed, 2)
        del sw
        box = self.form().template_box                                          # par un clic sur une ligne
        p = box.popup()
        with mock.patch.object(self.TP, '_SwallowClicks') as swallow:
            p.show()
            p._clicked(p.rows()[0])
        swallow.assert_called_once()

    def test_default_columns_and_state_of_another_version(self):
        TP = self.TP
        p = self.form().template_box.popup()
        h = p.tree.header()
        self.assertTrue(h.isSectionHidden(self.column('power')))                # la puissance laser : au choix
        self.assertFalse(h.isSectionHidden(self.column('description')))
        m = p.columns_menu()
        self.addCleanup(m.deleteLater)
        self.assertIn('Colonnes par défaut', [a.text() for a in m.actions()])
        p.set_column_shown(self.column('power'), True)
        p.set_column_shown(self.column('description'), False)
        p.tree.sortByColumn(self.column('feed'), Qt.SortOrder.DescendingOrder)
        p.reset_columns()
        self.assertTrue(h.isSectionHidden(self.column('power')))
        self.assertFalse(h.isSectionHidden(self.column('description')))
        self.assertEqual(h.sortIndicatorSection(), 0)
        self.assertEqual(p.visible_names()[0], 'Alu ébauche')
        s = portable.settings()                                                 # état d'une autre version : laissé
        p.set_column_shown(self.column('description'), False)
        s.setValue(TP.STATE_COLUMNS_KEY, len(TP.COLUMNS) - 1)
        again = self.form().template_box.popup()
        self.assertFalse(again.tree.header().isSectionHidden(self.column('description')))


if __name__ == '__main__':
    unittest.main()
