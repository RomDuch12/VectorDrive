"""Round 1024 : demande du 14/11, 19 h 45 — « Boutons rubans : le mode simple réarrange les boutons depuis la
disposition expert en fonction de ce qu'il contient »."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1024.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QAction  # noqa: E402
from PySide6.QtWidgets import QApplication, QToolButton, QWidget  # noqa: E402

app = QApplication.instance() or QApplication([])

from vectordrive.ui import ribbon as R  # noqa: E402


def columns(g):
    """Les colonnes de petits éléments du groupe : nombre d'éléments montrés de chacune (dans l'ordre)."""
    out = []
    for i in range(g._row.count()):
        w = g._row.itemAt(i).widget()
        if w is None or isinstance(w, QToolButton):
            continue
        lay = w.layout()
        out.append(sum(1 for k in range(lay.count())
                       if lay.itemAt(k).widget() is not None and not lay.itemAt(k).widget().isHidden()))
    return out


def bigs(g):
    return [w.defaultAction().text() for w in (g._row.itemAt(i).widget() for i in range(g._row.count()))
            if isinstance(w, QToolButton) and not w.isHidden()]


class Group(unittest.TestCase):

    def make(self, n_small, n_big=0):
        self.owner = QWidget()
        self.addCleanup(self.owner.deleteLater)
        g = R.RibbonGroup('Essai', self.owner)
        self.acts = []
        for k in range(n_big):
            a = QAction(f'G{k}', self.owner)
            g.add(a, big=True)
            self.acts.append(a)
        for k in range(n_small):
            a = QAction(f'P{k}', self.owner)
            g.add(a, big=False)
            self.acts.append(a)
        return g

    def test_small_buttons_restacked_without_holes(self):
        g = self.make(6)
        self.assertEqual(columns(g), [3, 3])
        keep = {'P0', 'P2', 'P4', 'P5'}
        g.refresh_visibility(lambda a: a.text() in keep)                     # mode simple : 4 sur 6
        self.assertEqual(columns(g), [3, 1])                                  # avant : [2, 2], des trous
        order = [b.defaultAction().text() for b in g.buttons() if not b.isHidden()]
        self.assertEqual(order, ['P0', 'P2', 'P4', 'P5'])                     # l'ordre de la disposition expert
        g.refresh_visibility(None)                                            # mode expert : comme avant
        self.assertEqual(columns(g), [3, 3])
        self.assertTrue(all(not b.isHidden() for b in g.buttons()))

    def test_one_or_two_small_buttons_shown_big(self):
        g = self.make(5)
        g.refresh_visibility(lambda a: a.text() in ('P1', 'P3'))
        self.assertEqual(bigs(g), ['P1', 'P3'])                               # avant : deux petits dans une colonne
        b = next(b for b in g.buttons() if b.defaultAction().text() == 'P1')
        self.assertTrue(b.property('ribbon_big'))
        self.assertEqual(b.toolButtonStyle(), Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        g.set_iconic(True)                                                    # la place manque : les petits seuls
        self.assertEqual(b.toolButtonStyle(), Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        g.set_iconic(False)
        g.refresh_visibility(None)
        self.assertEqual(bigs(g), [])
        self.assertFalse(b.property('ribbon_big'))
        self.assertEqual(columns(g), [3, 2])

    def test_big_buttons_stay_big_small_ones_stay_small_with_a_big_one(self):
        g = self.make(4, n_big=1)
        g.refresh_visibility(lambda a: a.text() in ('G0', 'P3'))
        self.assertEqual(bigs(g), ['G0'])
        self.assertEqual(columns(g), [1])                                     # avant : deux colonnes, la 1re vide

    def test_expert_layout_order_and_looks_come_back(self):
        self.owner = QWidget()
        self.addCleanup(self.owner.deleteLater)
        g = R.RibbonGroup('Essai', self.owner)
        acts = {}
        for name, big in (('P0', False), ('G0', True), ('P1', False), ('P2', False), ('P3', False)):
            acts[name] = QAction(name, self.owner)
            g.add(acts[name], big=big)
        m = QToolButton(g.body)                                               # bouton de machine : texte seul
        acts['M'] = QAction('M', self.owner)
        m.setDefaultAction(acts['M'])
        m.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        g.add_widget(m)
        acts['S'] = QAction('S', self.owner)
        s = g.insert_after(acts['G0'], acts['S'], big=False)                  # petit bouton à sa place
        expert = [g._row.itemAt(i).widget() for i in range(g._row.count())]
        self.assertIs(expert[2], s)
        g.refresh_visibility(lambda a: a.text() != 'P1')
        self.assertEqual(columns(g), [1, 3])                                  # avant : [1, 2, 1]
        g.refresh_visibility(None)
        self.assertEqual(columns(g), [1, 3, 1])
        self.assertIs(g._row.itemAt(2).widget(), s)
        self.assertEqual([b.defaultAction().text() for b in g.buttons()], ['P0', 'G0', 'S', 'P1', 'P2', 'P3', 'M'])
        self.assertEqual(m.toolButtonStyle(), Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.assertIsNone(m.property('ribbon_big'))

    def test_small_inserted_button_keeps_its_place_after_compact(self):
        g = self.make(0, n_big=3)
        s = g.insert_after(self.acts[0], QAction('S', self.owner), big=False)
        self.assertIs(g._row.itemAt(1).widget(), s)
        g.set_compact(True)
        g.set_compact(False)
        self.assertIs(g._row.itemAt(1).widget(), s)                          # avant : empilé avec G1 et G2
        self.assertEqual(bigs(g), ['G0', 'S', 'G1', 'G2'])                   # chacun à sa place dans la rangée
        self.assertFalse(s.property('ribbon_big'))
        self.assertTrue(all(g._row.itemAt(i).widget().property('ribbon_big') for i in (0, 2, 3)))

    def test_machine_hidden_command_in_simple_mode(self):
        g = self.make(4)
        self.acts[1].setVisible(False)                                        # commande d'une autre machine
        g.refresh_visibility(lambda a: True)
        self.assertEqual(columns(g), [3])
        self.acts[1].setVisible(True)
        g.refresh_visibility(lambda a: True)
        self.assertEqual(columns(g), [3, 1])


class MainRibbon(unittest.TestCase):

    def test_simple_mode_has_no_empty_column(self):
        from vectordrive import portable
        from vectordrive.ui import modes
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        self.addCleanup(lambda: (setattr(w, 'modified', False), w.close()))
        self.addCleanup(lambda: portable.settings().remove(modes.KEY))
        w.set_ui_mode('simple', announce=False)
        holes = []
        for g in w.ribbon.findChildren(R.RibbonGroup):
            if g.vacant:
                continue
            items = [g._row.itemAt(i).widget() for i in range(g._row.count())]
            for k, it in enumerate(items):
                if it is None or isinstance(it, QToolButton):
                    continue
                lay = it.layout()
                n = sum(1 for j in range(lay.count())
                        if lay.itemAt(j).widget() is not None and not lay.itemAt(j).widget().isHidden())
                nxt = items[k + 1] if k + 1 < len(items) else None
                if n == 0 or (n < g.rows and nxt is not None and not isinstance(nxt, QToolButton)):
                    holes.append((g.title.text(), k, n))                     # vide, ou trouée avant une autre colonne
        self.assertEqual(holes, [])                                           # avant : des colonnes vides ou trouées


if __name__ == '__main__':
    unittest.main()
