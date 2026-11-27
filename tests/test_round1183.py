"""Round 1183 : demandes du 27/11 — « outil champs vitesse ne pas y écrire  le mm/min; » et « Tools : colonnes avances
écrire mm/min en très petit sous le label d'avance; ».

1. Formulaire d'une opération : un champ de vitesse à 0 (avance, plongée, broche, avance de finition) montre la valeur
   de l'outil en nombre seul ; l'unité reste dans le libellé du champ et dans sa bulle ; saisie, sélection, copie
   inchangées.
2. Listes d'outils (bibliothèque d'outils, « Choisir un outil », outils d'usinage du panneau FAO) : l'en-tête d'une
   colonne de vitesse montre le libellé et, dessous, l'unité en très petit et atténuée (thème clair et sombre) ; le
   titre de la colonne (tri, menu des colonnes, disposition retenue) reste entier."""
import os
import pathlib
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'rspeed.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'
os.environ.setdefault('VECTORDRIVE_KEYS_MEMORY', '1')

from PySide6.QtCore import QLocale, Qt  # noqa: E402
from PySide6.QtGui import QColor, QPalette  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QHeaderView, QTreeWidget  # noqa: E402

app = QApplication.instance() or QApplication([])

from vectordrive.cam import model  # noqa: E402
from vectordrive.i18n import tr  # noqa: E402
from vectordrive.ui import cam_panel as CP  # noqa: E402
from vectordrive.ui import tool_columns as TC  # noqa: E402

UNITS = ('mm/min', 'tr/min', tr('mm/min'), tr('tr/min'))
SPEEDS = ('feed', 'plunge', 'spindle', 'finish_feed')


class Settings(dict):
    def value(self, k, d=None):
        return self.get(k, d)

    def setValue(self, k, v):                                                # noqa: N802
        self[k] = v


def cyl():
    return model.CamTool(name='Cyl speed', diameter=2.0, feed=750.0, plunge=150.0, spindle=18000.0, step_down=0.3,
                         stepover=0.5, number=1, ref='RSP', cut_length=6.0)


def unit_header(view):
    h = view.header() if hasattr(view, 'header') else view.horizontalHeader()
    if not hasattr(TC, 'UnitHeader') or not isinstance(h, TC.UnitHeader):
        raise AssertionError('avant : en-tête ordinaire, unité dans le titre « Avance (mm/min) » sur une ligne')
    return h


def lum(c: QColor) -> float:
    return 0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue()


class SpeedFields(unittest.TestCase):

    def form(self, op=None, tool=None):
        tool = tool or cyl()
        from shiboken6 import isValid
        dlg = CP.FieldsDialog(None, 'essai', op or model.Operation(kind='poche', tool_id=tool.id), tools=[tool])
        self.addCleanup(lambda: isValid(dlg) and dlg.deleteLater())    # validé par Entrée : supprimé par Qt ensuite
        return dlg

    def test_tool_value_is_the_number_alone(self):
        t = cyl()
        self.assertEqual(CP.tool_value_text('feed', t), '750')                # avant : « 750 mm/min »
        self.assertEqual(CP.tool_value_text('plunge', t), '150')
        self.assertEqual(CP.tool_value_text('spindle', t), '18000')           # avant : « 18000 tr/min »
        self.assertEqual(CP.tool_value_text('finish_feed', t), '750')         # pas d'avance de finition : d'ébauche
        t.finish_feed = 420.5
        self.assertEqual(CP.tool_value_text('finish_feed', t), f'420{QLocale().decimalPoint()}5')
        self.assertTrue(CP.tool_value_text('step_down', t).endswith(' mm'))  # pas une vitesse : son unité gardée
        self.assertEqual(CP.tool_value_text('feed', None), '—')
        for name in SPEEDS:
            for u in UNITS:
                self.assertNotIn(u, CP.tool_value_text(name, t), name)

    def test_form_fields_labels_and_tips(self):
        dlg = self.form()
        for name, unit in (('feed', 'mm/min'), ('plunge', 'mm/min'), ('spindle', 'tr/min'), ('finish_feed', 'mm/min')):
            w = dlg.widgets[name]
            for u in UNITS:
                self.assertNotIn(u, w.specialValueText(), name)              # rien d'écrit après le nombre
                self.assertNotIn(u, w.text(), name)
            self.assertIn(unit, CP.LABELS[name])                              # l'unité : dans le libellé…
            self.assertIn(tr(unit), w.toolTip(), name)                        # … et dans la bulle
        self.assertEqual(dlg.widgets['feed'].text(), '750')
        self.assertEqual(dlg.widgets['spindle'].text(), '18000')
        self.assertEqual(dlg.widgets['finish_feed'].text(), '750')
        dlg.widgets['feed'].setValue(700.0)                                   # l'avance d'ébauche de l'opération
        self.assertEqual(dlg.widgets['finish_feed'].specialValueText(), '700')
        self.assertIn('mm/min', dlg.widgets['finish_feed'].toolTip())

    def test_typing_selecting_copying_unchanged(self):
        dlg = self.form()
        dlg.show()
        QTest.qWait(20)
        feed = dlg.widgets['feed']
        le = feed.lineEdit()
        feed.setFocus()
        le.selectAll()
        self.assertEqual(le.selectedText(), '750')                            # toute la valeur, prête à remplacer
        le.copy()
        self.assertEqual(QApplication.clipboard().text(), '750')              # copiée : un nombre, collable ailleurs
        QTest.keyClicks(le, '820')
        QTest.keyClick(le, Qt.Key.Key_Return)
        self.assertEqual(feed.value(), 820.0)
        le.selectAll()
        QTest.keyClicks(le, '750')                                            # la valeur même de l'outil : fixée
        QTest.keyClick(le, Qt.Key.Key_Return)
        self.assertEqual(feed.value(), 750.0)
        feed.setValue(0.0)
        self.assertEqual(feed.text(), '750')                                  # à 0 : celle de l'outil, de nouveau
        self.assertEqual(feed.value(), 0.0)
        feed.interpretText()                                                  # 2e relecture : la frappe d'avant
        self.assertEqual(feed.value(), 0.0)                                   # ne compte plus
        QTest.keyClick(le, Qt.Key.Key_Return)
        self.assertEqual(feed.value(), 0.0)

    def test_saved_in_the_tool_then_validated_keeps_the_link(self):
        """2e relecture : outil à 500, « 750 » tapé, « Dans la fiche de l'outil » (outil à 750, champ remis à 0, « 750 »
        affiché), puis Tab / OK : l'opération suit l'outil, 750 n'est pas figé."""
        tool = cyl()
        tool.feed = 500.0
        op = model.Operation(kind='poche', tool_id=tool.id)
        dlg = self.form(op, tool)
        dlg.show()
        QTest.qWait(20)
        feed = dlg.widgets['feed']
        le = feed.lineEdit()
        feed.setFocus()
        le.selectAll()
        QTest.keyClicks(le, '750')
        self.assertEqual(feed.value(), 750.0)
        self.assertEqual(dlg.save_feeds_to_tool('ebauche'), ['feed'])
        self.assertEqual(tool.feed, 750.0)
        self.assertEqual((feed.value(), feed.text()), (0.0, '750'))
        feed.interpretText()
        self.assertEqual(feed.value(), 0.0)                                   # avant : 750 figé
        self.assertEqual(self.tab(feed), 0.0)
        self.assertEqual(feed.value(), 0.0)
        dlg.apply()
        self.assertEqual(op.feed, 0.0)

    def test_calculation_to_zero_then_tab(self):
        """« = » qui rend 0 après avoir tapé la valeur de l'outil : de nouveau celle de l'outil, et Tab la garde."""
        from vectordrive.ui import fields as F
        dlg, op = self.shown_form()
        feed = dlg.widgets['feed']
        le = feed.lineEdit()
        feed.setFocus()
        le.selectAll()
        QTest.keyClicks(le, '750')
        self.assertEqual(feed.value(), 750.0)
        with mock.patch('PySide6.QtWidgets.QInputDialog.getItem', return_value=('0', True)):
            F.calculate(le)
        self.assertEqual((feed.value(), feed.text()), (0.0, '750'))
        feed.interpretText()                                                  # (la perte du focus ne relit pas
        self.assertEqual(feed.value(), 0.0)                                   # une ligne non modifiée ; Entrée oui)
        self.assertEqual(self.tab(feed), 0.0)
        feed.setFocus()
        QTest.keyClick(le, Qt.Key.Key_Return)
        self.assertEqual(feed.value(), 0.0)
        dlg.apply()
        self.assertEqual(op.feed, 0.0)

    def test_undo_back_to_the_tool_value_is_not_typing(self):
        """Ctrl+Z qui ramène « 750 » (le texte de la valeur de l'outil) sur un champ hérité : pas une saisie, 0."""
        dlg, op = self.shown_form()
        feed = dlg.widgets['feed']
        le = feed.lineEdit()
        feed.setFocus()
        le.selectAll()
        QTest.keyClicks(le, '8')
        self.assertEqual(feed.value(), 8.0)
        QTest.keyClick(le, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(le.text(), '750')
        self.assertEqual(feed.value(), 0.0)
        QTest.keyClick(le, Qt.Key.Key_Return)
        self.assertEqual(feed.value(), 0.0)
        dlg.apply()
        self.assertEqual(op.feed, 0.0)

    def shown_form(self, tool=None, **kw):
        tool = tool or cyl()
        op = model.Operation(kind='poche', tool_id=tool.id, **kw)
        dlg = self.form(op, tool)
        dlg.show()
        QTest.qWait(20)
        return dlg, op

    def tab(self, w):
        """Un vrai Tab : le champ perd le focus (passé au suivant) et termine sa saisie (`editingFinished`)."""
        done = []

        def finished():
            done.append(w.value())
        w.editingFinished.connect(finished)
        try:
            if not w.hasFocus():
                w.setFocus()
                QTest.qWait(10)
            self.assertTrue(w.hasFocus())
            QTest.keyClick(w.lineEdit(), Qt.Key.Key_Tab)
            QTest.qWait(10)
            self.assertFalse(w.hasFocus() or w.lineEdit().hasFocus())          # le focus est passé au suivant
            self.assertTrue(done)                                             # la saisie terminée
        finally:
            w.editingFinished.disconnect(finished)
        return done[-1]

    def type_in(self, w, text):
        w.setFocus()
        QTest.qWait(10)
        w.lineEdit().selectAll()
        QTest.keyClicks(w.lineEdit(), text)

    def test_typed_tool_value_is_fixed(self):
        """3e relecture : héritage « 750 », taper soi-même « 750 » fixe 750 — par Entrée, par Tab, par OK."""
        d1, op1 = self.shown_form()
        feed = d1.widgets['feed']
        self.type_in(feed, '750')
        QTest.keyClick(feed.lineEdit(), Qt.Key.Key_Return)
        self.assertEqual(feed.value(), 750.0)
        self.assertNotEqual(feed.text(), '750')                               # réécrit : « 750,000 », une valeur
        d1.apply()
        self.assertEqual(op1.feed, 750.0)
        d2, op2 = self.shown_form()
        feed = d2.widgets['feed']
        self.type_in(feed, '750')
        self.assertEqual(self.tab(feed), 750.0)
        self.assertNotEqual(feed.text(), '750')                               # Tab a relu et réécrit le champ
        d2.apply()
        self.assertEqual(op2.feed, 750.0)
        d3, op3 = self.shown_form()
        self.type_in(d3.widgets['feed'], '750')
        d3.apply()                                                            # OK (le formulaire lu)
        self.assertEqual(op3.feed, 750.0)

    def test_paste(self):
        dlg, op = self.shown_form()
        feed = dlg.widgets['feed']
        le = feed.lineEdit()
        for text, want in (('640', 640.0), ('750', 750.0)):                   # collé : une saisie, même « 750 »
            feed.setValue(0.0)
            feed.setFocus()
            le.selectAll()
            QApplication.clipboard().setText(text)
            le.paste()
            QTest.keyClick(le, Qt.Key.Key_Return)
            self.assertEqual(feed.value(), want, text)
        dlg.apply()
        self.assertEqual(op.feed, 750.0)

    def test_page_down_back_to_zero(self):
        """Plongée de l'outil 5, « 5 » tapé, Page↓ jusqu'à 0 (texte identique, non réécrit) : celle de l'outil."""
        tool = cyl()
        tool.plunge = 5.0
        dlg, op = self.shown_form(tool)
        w = dlg.widgets['plunge']
        self.type_in(w, '5')
        self.assertEqual(w.value(), 5.0)
        QTest.keyClick(w.lineEdit(), Qt.Key.Key_PageDown)
        self.assertEqual((w.value(), w.text()), (0.0, '5'))
        w.interpretText()
        self.assertEqual(w.value(), 0.0)                                      # avant : 5 figé
        self.assertEqual(self.tab(w), 0.0)
        w.setFocus()
        QTest.keyClick(w.lineEdit(), Qt.Key.Key_Return)
        self.assertEqual(w.value(), 0.0)
        dlg.apply()
        self.assertEqual(op.plunge, 0.0)

    def test_emptied_field_takes_the_tool_value(self):
        dlg, op = self.shown_form()
        feed = dlg.widgets['feed']
        self.type_in(feed, '820')
        QTest.keyClick(feed.lineEdit(), Qt.Key.Key_Return)
        self.assertEqual(feed.value(), 820.0)
        feed.setFocus()
        feed.lineEdit().selectAll()
        QTest.keyClick(feed.lineEdit(), Qt.Key.Key_Delete)                     # vidé
        self.assertEqual(feed.text(), '')
        QTest.keyClick(feed.lineEdit(), Qt.Key.Key_Return)
        self.assertEqual((feed.value(), feed.text()), (0.0, '750'))           # celle de l'outil (avant : 820 gardé)
        self.assertTrue(feed.inherits_tool())
        dlg.apply()
        self.assertEqual(op.feed, 0.0)

    def test_new_tool_value_forgets_a_stale_typing(self):
        """`setSpecialValueText` à 0 : une frappe retenue égale à la nouvelle valeur de l'outil ne compte plus."""
        dlg, _op = self.shown_form()
        feed = dlg.widgets['feed']
        self.assertEqual(feed.value(), 0.0)
        feed._edited = '900'                                                  # une frappe d'avant, restée en mémoire
        feed.setSpecialValueText('900')                                       # l'outil passe à 900
        feed.interpretText()
        self.assertEqual(feed.value(), 0.0)

    def test_finish_feed_shown_is_the_one_used(self):
        """MOYEN (3e relecture) : avance de finition à 0, outil à 420,5 en finition, opération à 700 en ébauche — le
        calcul donne 700 aux passes de finition (`finish_feed_of`) : le champ montre ce que le calcul prend."""
        from types import SimpleNamespace
        tool = cyl()
        tool.finish_feed = 420.5
        dlg, op = self.shown_form(tool, feed_frame='ebauche')
        fin, feed = dlg.widgets['finish_feed'], dlg.widgets['feed']
        dp = QLocale().decimalPoint()

        def used():
            dlg.apply()
            return CP._num(model.move_feed(SimpleNamespace(fin=True), op, tool))
        self.assertEqual(fin.specialValueText(), f'420{dp}5')                 # l'opération n'a pas d'avance
        self.assertEqual(fin.specialValueText(), used())
        feed.setValue(700.0)
        self.assertEqual(fin.specialValueText(), '700')                       # avant : « 420,5 », passes à 700
        self.assertEqual(fin.specialValueText(), used())
        self.assertIn('700', fin.toolTip())
        dlg.set_feed_frame('finition')                                        # cadre Finition : celle de l'outil
        self.assertEqual(fin.specialValueText(), f'420{dp}5')
        self.assertEqual(fin.specialValueText(), used())
        dlg.set_feed_frame('ebauche')
        feed.setValue(0.0)
        self.assertEqual(fin.specialValueText(), f'420{dp}5')
        self.assertEqual(fin.specialValueText(), used())

    def test_enter_keeps_the_tool_link(self):
        """Relecture : Entrée sur « 750 » (OK par défaut) ne fige plus 750 : l'opération suit toujours l'outil."""
        dlg, op = self.shown_form()
        for name in SPEEDS:
            w = dlg.widgets[name]
            if not hasattr(CP, 'ToolValueSpin') or not isinstance(w, CP.ToolValueSpin):
                raise AssertionError('avant : champ ordinaire, son texte spécial validé comme une valeur')
            w.setFocus()
            w.lineEdit().selectAll()
            w.interpretText()
            self.assertEqual(w.value(), 0.0, name)
        feed = dlg.widgets['feed']
        feed.setFocus()
        QTest.keyClick(feed.lineEdit(), Qt.Key.Key_Return)                   # Entrée : OK du formulaire
        self.assertEqual(feed.value(), 0.0)
        self.assertEqual(feed.text(), '750')
        dlg.apply()
        self.assertEqual(op.feed, 0.0)                                        # avant : 750 enregistré
        self.assertEqual(op.spindle, 0.0)

    def test_tab_focus_out_editing_finished(self):
        dlg, _op = self.shown_form()
        feed, plunge = dlg.widgets['feed'], dlg.widgets['plunge']
        done = []
        feed.editingFinished.connect(lambda: done.append(feed.value()))
        self.assertEqual(self.tab(feed), 0.0)
        self.assertEqual(feed.value(), 0.0)
        feed.setFocus()
        QTest.qWait(10)
        plunge.setFocus()                                                     # perte du focus
        QTest.qWait(10)
        self.assertEqual(feed.value(), 0.0)
        self.assertTrue(done)
        self.assertEqual(set(done), {0.0})
        le = feed.lineEdit()                                                  # validation (fixup) du texte affiché
        self.assertEqual(feed.validate(le.text(), 0)[0], CP.QValidator.State.Acceptable)
        self.assertEqual(feed.valueFromText(le.text()), 0.0)

    def test_calculation_validated_as_is_keeps_the_link(self):
        """« = » sur une valeur héritée : le calcul part de la valeur affichée ; validé tel quel, rien n'est figé ;
        un calcul modifié s'applique."""
        from vectordrive.ui import fields as F
        dlg, op = self.shown_form()
        feed = dlg.widgets['feed']
        le = feed.lineEdit()
        proposed = []

        def same(_parent, _title, _label, items, _cur, _editable):
            proposed.append(items[0])
            return items[0], True
        before = self.calc_memory()
        with mock.patch('PySide6.QtWidgets.QInputDialog.getItem', side_effect=same):
            self.assertIsNone(F.calculate(le))
        self.assertEqual(proposed, ['750'])                                   # part de la valeur affichée
        self.assertEqual(feed.value(), 0.0)                                   # avant : 750 figé
        self.assertEqual(self.calc_memory(), before)                          # ni « ans » ni historique touchés
        with mock.patch('PySide6.QtWidgets.QInputDialog.getItem', return_value=('750*2', True)):
            F.calculate(le)
        self.assertEqual(feed.value(), 1500.0)
        feed.setValue(0.0)
        with mock.patch('PySide6.QtWidgets.QInputDialog.getItem', return_value=('750', False)):
            F.calculate(le)                                                   # annulé
        self.assertEqual(feed.value(), 0.0)
        dlg.apply()
        self.assertEqual(op.feed, 0.0)

    @staticmethod
    def calc_memory():
        from vectordrive import portable
        from vectordrive.ui import fields as F
        return F.history(portable.settings())

    def test_calculation_on_a_plain_special_field(self):
        """« = » validé tel quel sur un champ ordinaire à texte spécial (« libre ») : rien, sans erreur ; « ans » et
        l'historique inchangés ; un vrai calcul s'applique."""
        from PySide6.QtWidgets import QDoubleSpinBox
        from vectordrive.ui import fields as F
        w = QDoubleSpinBox()
        self.addCleanup(w.deleteLater)
        w.setRange(0, 1000)
        w.setSpecialValueText('libre')
        w.show()
        before = self.calc_memory()
        with mock.patch('PySide6.QtWidgets.QInputDialog.getItem', side_effect=lambda *a: (a[3][0], True)):
            self.assertIsNone(F.calculate(w.lineEdit()))
        self.assertEqual(w.value(), 0.0)
        self.assertEqual(self.calc_memory(), before)
        with mock.patch('PySide6.QtWidgets.QInputDialog.getItem', return_value=('12*2', True)):
            self.assertEqual(F.calculate(w.lineEdit()), 24.0)
        self.assertEqual(w.value(), 24.0)

    def test_inherited_value_is_dimmed(self):
        from vectordrive.ui import theme
        self.addCleanup(theme.apply_light, app)
        theme.apply_light(app)
        dlg, _op = self.shown_form()
        feed = dlg.widgets['feed']
        if not hasattr(feed, 'inherits_tool'):
            raise AssertionError('avant : la valeur héritée s’écrit comme une valeur saisie')
        text, dim = QPalette.ColorRole.Text, QPalette.ColorRole.PlaceholderText

        def colour():
            return feed.lineEdit().palette().color(QPalette.ColorGroup.Active, text)
        self.assertEqual(colour(), feed.palette().color(QPalette.ColorGroup.Active, dim))
        self.assertNotEqual(colour(), feed.palette().color(QPalette.ColorGroup.Active, text))
        feed.setValue(820.0)                                                  # une valeur à soi : couleur normale
        self.assertEqual(colour(), feed.palette().color(QPalette.ColorGroup.Active, text))
        feed.setValue(0.0)
        self.assertEqual(colour(), feed.palette().color(QPalette.ColorGroup.Active, dim))
        theme.apply_dark(app)                                                 # autre thème : ses couleurs
        QTest.qWait(10)
        self.assertEqual(colour(), feed.palette().color(QPalette.ColorGroup.Active, dim))
        own = self.form(model.Operation(kind='poche', feed=999.0))
        self.assertEqual(own.widgets['feed'].lineEdit().palette().color(QPalette.ColorGroup.Active, text),
                         own.widgets['feed'].palette().color(QPalette.ColorGroup.Active, text))

    def test_tool_form_fields_stay_plain(self):
        dlg = CP.FieldsDialog(None, 'essai', cyl())
        self.addCleanup(dlg.deleteLater)
        self.assertNotIsInstance(dlg.widgets['feed'], getattr(CP, 'ToolValueSpin', ()))
        self.assertEqual(dlg.widgets['feed'].value(), 750.0)


class Headers(unittest.TestCase):

    def tree(self, shown=TC.SHOWN):
        t = QTreeWidget()
        self.addCleanup(t.deleteLater)
        TC.install(t, None, '', shown=shown)
        return t

    def test_split(self):
        if not hasattr(TC, 'split_unit'):
            raise AssertionError('avant : pas de libellé et d’unité séparés')
        self.assertEqual(TC.split_unit('Avance (mm/min)'), ('Avance', 'mm/min'))
        self.assertEqual(TC.split_unit('Spindle (rpm)'), ('Spindle', 'rpm'))
        self.assertEqual(TC.split_unit('Ø'), ('Ø', ''))
        self.assertEqual(TC.split_unit('Passe Z'), ('Passe Z', ''))

    def test_speed_columns_show_their_unit_below(self):
        t = self.tree()
        h = unit_header(t)
        keys = ('spindle', 'feed', 'finish_feed', 'plunge', 'ramp_feed')
        for k in keys:
            c = TC.KEYS.index(k)
            full = tr(dict(TC.COLUMNS)[k])
            self.assertEqual(t.headerItem().text(c), full)                    # le titre reste entier
            self.assertEqual(h.parts(c), (full,) + TC.split_unit(full))
        self.assertIsNone(h.parts(TC.KEYS.index('diameter')))                 # les autres : une ligne
        self.assertIsNone(h.parts(0))
        self.assertLessEqual(h.unit_font().pointSizeF(), 0.7 * h.font().pointSizeF())   # très petit
        menu = TC.column_menu(t)
        self.addCleanup(menu.deleteLater)
        texts = [a.text() for a in menu.actions()]
        self.assertIn(tr('Avance (mm/min)'), texts)                           # menu des colonnes : le nom entier
        self.assertIn(tr('Broche (tr/min)'), texts)

    def test_width_from_label_height_two_lines(self):
        t = self.tree(shown=TC.KEYS)
        h = unit_header(t)
        plain = QTreeWidget()
        self.addCleanup(plain.deleteLater)
        plain.setColumnCount(len(TC.COLUMNS))
        plain.setHeaderLabels([tr(lab) for _k, lab in TC.COLUMNS])
        ph = plain.header()
        c = TC.KEYS.index('feed')
        mine, theirs = h.sectionSizeFromContents(c), ph.sectionSizeFromContents(c)
        self.assertLess(mine.width(), theirs.width())                         # « Avance », pas « Avance (mm/min) »
        label = TC.split_unit(tr('Avance (mm/min)'))[0]
        self.assertGreaterEqual(mine.width(), h.fontMetrics().horizontalAdvance(label))
        self.assertGreater(mine.height(), theirs.height())                    # deux lignes
        d = TC.KEYS.index('diameter')
        self.assertEqual(h.sectionSizeFromContents(d), ph.sectionSizeFromContents(d))
        self.assertGreaterEqual(h.sizeHint().height(), mine.height())
        hidden = unit_header(self.tree())                                     # vitesses cachées : même hauteur
        self.assertEqual(hidden.sizeHint().height(), h.sizeHint().height())

    def ink(self, img, x0, x1, y0, y1, bg):
        """Le plus fort écart de luminosité au fond `bg` dans le rectangle."""
        best = 0.0
        for y in range(y0, y1):
            for x in range(x0, x1):
                best = max(best, abs(lum(img.pixelColor(x, y)) - lum(bg)))
        return best

    def test_painted_in_light_and_dark(self):
        from vectordrive.ui import theme
        self.addCleanup(theme.apply_light, app)
        for apply in (theme.apply_light, theme.apply_dark):
            apply(app)
            t = self.tree(shown=('name', 'feed', 'diameter'))
            t.resize(700, 120)
            t.show()
            QTest.qWait(20)
            h = unit_header(t)
            img = h.grab().toImage()
            c = TC.KEYS.index('feed')
            x0, x1 = h.sectionViewportPosition(c) + 2, h.sectionViewportPosition(c) + h.sectionSize(c) - 2
            bg = img.pixelColor(x1 - 2, 1)
            fm = h.fontMetrics()
            mid = img.height() // 2
            self.assertGreater(self.ink(img, x0, x1, 1, mid, bg), 8, apply.__name__)          # le libellé en haut
            self.assertGreater(self.ink(img, x0, x1, mid + 1, img.height() - 1, bg), 8, apply.__name__)   # l'unité
            self.assertGreater(img.height(), 2 * fm.height() * 0.8)
            # la couleur réellement peinte : celle des textes d'exemple de la palette (rouge pur pour la voir),
            # l'unité seule, pas le libellé
            pal = QPalette(h.palette())
            for g in (QPalette.ColorGroup.Active, QPalette.ColorGroup.Inactive):
                pal.setColor(g, QPalette.ColorRole.PlaceholderText, QColor(255, 0, 0))
            h.setPalette(pal)
            img = h.grab().toImage()

            def red(y0, y1):
                return sum(1 for y in range(y0, y1) for x in range(x0, x1)
                           if (lambda p: p.red() - max(p.green(), p.blue()))(img.pixelColor(x, y)) > 60)
            self.assertGreater(red(mid + 1, img.height() - 1), 0, apply.__name__)
            self.assertEqual(red(1, mid), 0, apply.__name__)
            t.close()

    def test_replaced_header_keeps_sort_and_follows_font(self):
        if not hasattr(TC, 'unit_header'):
            raise AssertionError('avant : pas d’en-tête à unité')
        t = QTreeWidget()
        self.addCleanup(t.deleteLater)
        t.setColumnCount(3)
        t.setHeaderLabels(['A', 'B', 'Avance (mm/min)'])
        t.setSortingEnabled(True)
        t.header().setSortIndicatorClearable(True)
        t.sortByColumn(2, Qt.SortOrder.DescendingOrder)
        h = TC.unit_header(t, (2,))
        self.assertIs(t.header(), h)
        self.assertEqual((h.sortIndicatorSection(), h.sortIndicatorOrder()), (2, Qt.SortOrder.DescendingOrder))
        self.assertTrue(h.isSortIndicatorClearable())
        self.assertIs(TC.unit_header(t, (2,)), h)                             # une seconde fois : le même
        tall = h.sizeHint().height()
        TC.unit_header(t, ())                                                 # plus de colonne d'unité : recalculé
        self.assertIsNone(h.parts(2))
        self.assertLess(h.sizeHint().height(), tall)
        TC.unit_header(t, (2,))
        self.assertEqual(h.sizeHint().height(), tall)
        small = h.unit_font().pointSizeF()
        f = h.font()
        f.setPointSizeF(f.pointSizeF() * 2)
        h.setFont(f)                                                          # police changée : mesures refaites
        self.assertGreater(h.unit_font().pointSizeF(), small * 1.5)

    def test_picker_sort_resize_remembered(self):
        from vectordrive.ui.tool_picker import ToolPickerDialog
        st = Settings()
        t = cyl()
        dlg = ToolPickerDialog(None, [], {t.id: t}, settings=st)
        self.addCleanup(dlg.deleteLater)
        h = unit_header(dlg.tree)
        self.assertTrue(h.sectionsMovable())
        self.assertTrue(h.sectionsClickable())
        c = TC.KEYS.index('feed')
        TC.set_shown(dlg.tree, 'feed', True, st, 'outils/choix_colonnes')
        with mock.patch.object(dlg, '_lock_favorites') as lock:              # branché sur l'en-tête neuf
            h.setSortIndicator(c, Qt.SortOrder.AscendingOrder)
        lock.assert_called_with(c)
        self.assertEqual(dlg.tree.sortColumn(), c)
        h.resizeSection(c, 133)
        self.assertIn('outils/choix_colonnes/entete', st)
        again = ToolPickerDialog(None, [], {t.id: t}, settings=st)
        self.addCleanup(again.deleteLater)
        h2 = unit_header(again.tree)
        self.assertFalse(h2.isSectionHidden(c))
        self.assertEqual(h2.sectionSize(c), 133)

    def test_library_dialog(self):
        from vectordrive.ui.toollib_dialog import ToolLibraryDialog
        dlg = ToolLibraryDialog(None, None, pathlib.Path(tempfile.mkdtemp()) / 'tools.json')
        self.addCleanup(dlg.deleteLater)
        h = unit_header(dlg.tree)
        c = TC.KEYS.index('plunge')
        self.assertEqual(dlg.tree.headerItem().text(c), tr('Plongée (mm/min)'))
        self.assertEqual(h.parts(c)[2], TC.split_unit(tr('Plongée (mm/min)'))[1])
        self.assertTrue(h.isSortIndicatorShown())


class FaoTable(unittest.TestCase):

    def test_fao_tool_table(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            cp = w.cam_panel
            h = unit_header(cp.tools)
            self.assertEqual(cp.tools.horizontalHeaderItem(4).text(), tr('Avance (mm/min)'))
            self.assertEqual(h.parts(4)[1:], TC.split_unit(tr('Avance (mm/min)')))
            self.assertIsNone(h.parts(3))
            self.assertEqual(h.sectionResizeMode(1), QHeaderView.ResizeMode.Stretch)
            self.assertEqual(h.sectionResizeMode(4), QHeaderView.ResizeMode.ResizeToContents)
            self.assertTrue(h.sectionsClickable())
            s = cp.setup()
            s.tools[:] = [model.CamTool(number=1, name='A', feed=1200.0), model.CamTool(number=2, name='B', feed=90.0)]
            cp.save(s)
            cp.refresh()
            cp.tools.sortByColumn(4, Qt.SortOrder.AscendingOrder)
            self.assertEqual([cp.tools.item(r, 4).text() for r in range(2)], ['90', '1200'])   # tri en nombres
        finally:
            w.settings.remove('fao/outils_tri')
            w.modified = False
            for d in getattr(w, 'docs', []):
                d.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
