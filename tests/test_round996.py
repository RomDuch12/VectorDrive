"""Round 996 : FAO, plongée angulaire, retour de l'atelier — « FAO plongée angulaire : icone-bouton push on/off avec champ
angle visible haut de formulaire après choix outil intégré ». Sous l'outil, un bouton poussoir à icône (enfoncé : en
rampe) et l'angle à côté ; montrés pour les contours, poches, gravures… (depuis le round 871, seulement pour la gravure en
V)."""
import os
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QCheckBox, QFormLayout, QGroupBox  # noqa: E402

from vectordrive.cam import model  # noqa: E402
from vectordrive.ui import cam_panel as CP  # noqa: E402

app = QApplication.instance() or QApplication([])


def dialog(kind='contour', **kw):
    d = CP.FieldsDialog(None, 'essai', model.Operation(kind=kind, **kw))
    return d


def group_of(w):
    p = w.parentWidget()
    while p is not None and not isinstance(p, QGroupBox):
        p = p.parentWidget()
    return p


def form_row(form: QFormLayout, w) -> int:
    for r in range(form.rowCount()):
        it = form.itemAt(r, QFormLayout.ItemRole.FieldRole)
        if it is not None and it.widget() is not None and (it.widget() is w or it.widget().isAncestorOf(w)):
            return r
    return -1


class Visible(unittest.TestCase):

    def test_shown_for_milling_strategies(self):
        for kind in ('contour', 'poche', 'gravure', 'reste', 'vcarve', 'gamme', 'chanfrein_bord', 'decoupe3d'):
            d = dialog(kind)
            try:
                for n in ('ramp', 'ramp_angle', 'ramp_max'):
                    self.assertTrue(d.widgets[n].isVisibleTo(d), (kind, n))   # avant : masqués sauf gravure en V
            finally:
                d.deleteLater()

    def test_hidden_where_it_means_nothing(self):
        for kind in ('percage', 'laser', 'laser_gravure', 'vinyle', 'taraudage',
                     'chanfrein', 'surfacage'):                         # leur parcours plonge droit, rampe ou pas
            d = dialog(kind)
            try:
                for n in ('ramp', 'ramp_angle', 'ramp_max'):
                    self.assertFalse(d.widgets[n].isVisibleTo(d), (kind, n))   # le bouton : sa ligne masquée
            finally:
                d.deleteLater()


    def test_strategy_changed_in_the_form(self):
        d = dialog('contour', ramp=True)
        try:
            combo = d.widgets['kind']
            combo.setCurrentIndex(combo.findData('percage'))
            self.assertFalse(d.widgets['ramp'].isVisibleTo(d))
            combo.setCurrentIndex(combo.findData('contour'))
            self.assertTrue(d.widgets['ramp'].isVisibleTo(d))
            self.assertTrue(d.widgets['ramp_angle'].isEnabled())
        finally:
            d.deleteLater()


class AtTheTop(unittest.TestCase):

    def test_angle_also_for_connected_passes(self):
        d = dialog('contour', ramp=False, link_passes=False)
        try:
            self.assertFalse(d.widgets['ramp_angle'].isEnabled())
            d.widgets['link_passes'].setChecked(True)                       # les passes descendent en rampe à l'angle
            self.assertTrue(d.widgets['ramp_angle'].isEnabled())            # avant : grisé
            d.widgets['link_passes'].setChecked(False)
            self.assertFalse(d.widgets['ramp_angle'].isEnabled())
        finally:
            d.deleteLater()

    def test_under_the_tool_in_the_first_section(self):
        d = dialog('contour')
        try:
            g = group_of(d.widgets['tool_id'])
            self.assertIs(group_of(d.widgets['ramp']), g)                   # avant : « Entrées et liaisons »
            self.assertIs(group_of(d.widgets['ramp_angle']), g)
            form = g.layout()
            # round 1020 : la ligne de l'outil proposé (cachée) sous l'outil
            self.assertEqual(form_row(form, d.widgets['ramp']), form_row(form, d.widgets['tool_id']) + 3)
            self.assertEqual(form_row(form, d.widgets['ramp']), form_row(form, d.widgets['ramp_angle']))   # côte à côte
        finally:
            d.deleteLater()

    def test_a_push_button_with_an_icon(self):
        d = dialog('contour', ramp=False, ramp_angle=12.0)
        try:
            b = d.widgets['ramp']
            self.assertIsInstance(b, QCheckBox)                             # lu comme avant par le formulaire
            self.assertIsInstance(b, CP.ToggleBox)
            self.assertFalse(b.icon().isNull())
            off = b.icon().pixmap(32, 32).toImage()
            self.assertFalse(d.widgets['ramp_angle'].isEnabled())           # angle actif bouton enfoncé
            d.show()
            app.processEvents()
            QTest.mouseClick(b, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, b.rect().center())
            self.assertTrue(b.isChecked())
            self.assertTrue(d.widgets['ramp_angle'].isEnabled())
            self.assertNotEqual(b.icon().pixmap(32, 32).toImage(), off)    # l'icône suit : en biais
            d.widgets['ramp_angle'].setValue(20.0)
            d.apply()
            self.assertTrue(d.obj.ramp)
            self.assertEqual(d.obj.ramp_angle, 20.0)
            self.assertEqual(d.illustration.ramp_angle(), 20.0)             # le schéma la montre
        finally:
            d.close()
            d.deleteLater()

    def test_template_sets_the_button(self):
        d = dialog('poche', ramp=False)
        try:
            self.assertFalse(d.widgets['ramp_angle'].isEnabled())
            d._set_widget('ramp', True)                                     # un modèle d'usinage chargé
            self.assertTrue(d.widgets['ramp'].isChecked())
            self.assertTrue(d.widgets['ramp_angle'].isEnabled())
        finally:
            d.deleteLater()
        d = CP.FieldsDialog(None, 'outil', model.CamTool())                 # le formulaire d'outil : rien de changé
        try:
            self.assertNotIn('ramp', d.widgets)
        finally:
            d.deleteLater()


if __name__ == '__main__':
    unittest.main()
