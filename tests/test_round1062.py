"""Round 1062 : demande du 15/11, 19 h 35 — « click droit panneau ouvre le commun des 2 avec pour chaque element
Gauche masqué ou droite; si pas de panneau lateral F2 ouvre celui qui contient dimensions; barre d'état affiche
toujours le perimetre des fermés et longueur des ouvert de la selection »."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1062.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication, QDockWidget  # noqa: E402

app = QApplication.instance() or QApplication([])

from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Shape  # noqa: E402
from vectordrive.ui import columns as C  # noqa: E402

BEFORE = 'avant : un œil par panneau dans la fenêtre d’une colonne, rien pour les deux à la fois'


def dock(w, name):
    return w.findChild(QDockWidget, name)


def forget():
    """Les places des panneaux retenues par d'autres essais (ou par ceux-ci) : oubliées."""
    from vectordrive import portable
    s = portable.settings()
    s.remove('panneaux_colonnes')
    s.sync()


class WithWindow(unittest.TestCase):

    def setUp(self):
        self.assertTrue(hasattr(C, 'PanelRows'), BEFORE)
        from vectordrive.ui.main_window import MainWindow
        forget()
        self.w = MainWindow()
        self.w.show()
        app.processEvents()

        def close():
            self.w.modified = False
            self.w.close()
            self.w.deleteLater()
            app.processEvents()
            forget()
        self.addCleanup(close)
        self.cols = self.w.columns


class Rows(WithWindow):

    def table(self, side='droite', done=None):
        t = C.PanelRows(self.cols, side, done=done)
        self.addCleanup(t.deleteLater)
        return t

    def state(self, t, name):
        return [k for k, b in t.choices[name].items() if b.isChecked()]

    def test_every_panel_has_left_hidden_right(self):
        t = self.table()
        names = {d.objectName() for d in self.cols.docks()}
        self.assertEqual(set(t.choices), names)                              # les panneaux des deux colonnes
        self.assertGreaterEqual(len(names), 4)
        for name, row in t.choices.items():
            self.assertEqual(list(row), ['gauche', 'masque', 'droite'], name)
            d = dock(self.w, name)
            want = 'masque' if d.isHidden() else self.cols.side(d)
            if want:
                self.assertEqual(self.state(t, name), [want], name)          # un seul coché : là où il est
        self.assertEqual([b.text() for b in t.choices['dims'].values()], ['Gauche', 'Masqué', 'Droite'])

    def test_a_click_places_the_panel(self):
        calls = []
        d = dock(self.w, 'dims')
        t = self.table(done=lambda: calls.append(1))
        other = 'gauche' if self.cols.side(d) == 'droite' else 'droite'
        t.choices['dims'][other].click()
        app.processEvents()
        self.assertEqual((self.cols.side(d), d.isHidden()), (other, False))
        self.assertEqual(self.state(self.table(), 'dims'), [other])
        t = self.table(done=lambda: calls.append(1))
        t.choices['dims']['masque'].click()
        app.processEvents()
        self.assertTrue(d.isHidden())
        self.assertEqual(self.state(self.table(), 'dims'), ['masque'])
        t = self.table()
        t.choices['dims'][other].click()                                     # revenu où il était
        app.processEvents()
        self.assertFalse(d.isHidden())
        t = self.table()
        t.choices['dims'][other].click()                                     # un second clic sur sa colonne : masqué
        app.processEvents()
        self.assertTrue(d.isHidden())
        self.assertEqual(len(calls), 2)                                      # `done` après chaque choix

    def test_the_same_table_in_the_column_window_and_in_the_right_click(self):
        p = self.w.column_panel('gauche')
        self.addCleanup(p.close)
        self.assertIsInstance(p.body, C.PanelRows)
        self.assertIs(p.eyes, p.body.eyes)                                   # (l'œil d'avant : le bouton de cette colonne)
        d = dock(self.w, 'dims')
        m = self.cols.menu(d)
        self.addCleanup(m.deleteLater)
        first = m.actions()[0]
        self.assertEqual(first.objectName(), 'panneaux')                     # en tête du clic droit d'un panneau
        tables = first.defaultWidget().findChildren(C.PanelRows)
        self.assertEqual(len(tables), 1)
        self.assertEqual(set(tables[0].choices), set(p.body.choices))
        texts = [a.text() for a in m.actions()]
        self.assertIn('Plein écran translucide', texts)                      # ses propres fonctions restent


class F2(WithWindow):

    def test_f2_brings_back_the_column_of_the_dimensions(self):
        d = dock(self.w, 'dims')
        side = self.cols.side(d)
        with_it = [x for x in self.cols.column(side) if not x.isHidden()]    # les panneaux montrés avec lui
        self.assertGreaterEqual(len(with_it), 2)
        for s in ('gauche', 'droite'):
            self.cols.set_shown(s, False)                                    # plus aucun panneau latéral
        app.processEvents()
        self.assertTrue(all(x.isHidden() for x in with_it))
        it = Shape(path=geom.Path([geom.rect(0.0, 0.0, 10.0, 20.0)]), tool=0)   # une forme choisie : ses dimensions
        self.w.canvas.doc.add(it)
        self.w.canvas.select([it])
        self.w.f2()
        app.processEvents()
        self.assertFalse(d.isHidden())                                       # la colonne des dimensions est revenue…
        self.assertTrue(all(not x.isHidden() for x in with_it))              # …entière, pas le panneau seul
        self.assertTrue(self.cols.shown(side))
        self.assertEqual(self.cols.side(d), side)
        self.assertTrue(self.w.dims.fields['w'].hasFocus() or not self.w.isActiveWindow())

    def test_f2_reopens_dimensions_closed_alone(self):
        d = dock(self.w, 'dims')
        self.cols.close(d)                                                   # fermé seul, sa colonne restée là
        app.processEvents()
        self.assertTrue(d.isHidden())
        self.w.f2()
        app.processEvents()
        self.assertFalse(d.isHidden())


class StatusBar(WithWindow):

    def put(self, *contours):
        it = Shape(path=geom.Path(list(contours)), tool=0)
        self.w.canvas.doc.add(it)
        self.w.canvas.invalidate()
        return it

    def test_perimeter_of_the_closed_length_of_the_open(self):
        closed = self.put(geom.rect(0.0, 0.0, 10.0, 20.0))
        opened = self.put(geom.polyline([(0.0, 30.0), (10.0, 30.0), (10.0, 35.0)], closed=False))
        self.w.canvas.select([closed])
        self.assertIn('Périmètre 60.000 mm', self.w.lbl_sel.text())
        self.assertNotIn('Longueur', self.w.lbl_sel.text())
        self.w.canvas.select([opened])
        self.assertIn('Longueur 15.000 mm', self.w.lbl_sel.text())
        self.assertNotIn('Périmètre', self.w.lbl_sel.text())
        self.w.canvas.select([closed, opened])
        text = self.w.lbl_sel.text()
        self.assertIn('Périmètre 60.000 mm', text)
        self.assertIn('Longueur 15.000 mm', text)
        self.assertEqual(self.w.lbl_sel.toolTip(), text)                     # coupé dans une fenêtre étroite : la bulle
        self.assertNotIn('Périmètre', self.w.ribbon.info.text())             # le ruban garde le texte court
        self.assertEqual(self.w.ribbon.info.text(), '')                    # la barre d'état seule (18/11 soir)
        self.w.canvas.select([])
        self.assertEqual((self.w.lbl_sel.text(), self.w.ribbon.info.text()), ('', ''))
        self.assertEqual(geom.Path([geom.rect(0, 0, 3, 4), geom.polyline([(0, 0), (3, 4)], closed=False)]).lengths(),
                         (14.0, 5.0))

    def test_the_lengths_are_exact_and_follow_the_shape(self):
        from vectordrive.core.geom import Affine
        tri = geom.polyline([(0.0, 0.0), (3.0, 0.0), (3.0, 4.0)], closed=True)   # fermé sans segment de fermeture
        self.assertAlmostEqual(geom.Path([tri]).lengths()[0], 12.0, places=9)
        many = geom.Path([geom.circle((5.0 * k, 0.0), 1.0 + 0.01 * k) for k in range(300)]
                         + [geom.polyline([(0.0, 10.0 + k), (7.0, 10.0 + k)], closed=False) for k in range(50)])
        closed, opened = many.lengths()                                      # des centaines de petits contours, d'un coup
        self.assertAlmostEqual(closed, sum(c.length() for c in many.contours if c.closed), places=6)
        self.assertAlmostEqual(opened, 350.0, places=9)
        self.assertAlmostEqual(closed + opened, many.length(), places=6)
        moved = many.transformed(Affine.rotation(30.0, (1.0, 2.0)))
        self.assertIn('lengths', moved.__dict__.get('_memo', {}))            # tournée : gardées, pas recalculées
        big = many.transformed(Affine.scaling(2.0, 2.0))
        self.assertAlmostEqual(big.lengths()[1], 700.0, places=6)
        squashed = many.transformed(Affine.scaling(2.0, 1.0))                # pas une similitude : recalculées
        self.assertNotIn('lengths', squashed.__dict__.get('_memo', {}))
        self.assertAlmostEqual(squashed.lengths()[1], 700.0, places=6)

    def test_never_computed_for_a_huge_selection(self):
        from vectordrive.ui import main_window as MW
        closed = self.put(geom.rect(0.0, 0.0, 10.0, 20.0))
        old = MW.PERIMETER_LIVE_LIMIT
        MW.PERIMETER_LIVE_LIMIT = 2                                          # quatre segments : au-delà
        self.addCleanup(setattr, MW, 'PERIMETER_LIVE_LIMIT', old)
        self.w.canvas.select([closed])
        self.assertNotIn('Périmètre', self.w.lbl_sel.text())
        self.assertIsNone(self.w.selection_lengths(limit=2))
        self.assertEqual(self.w.selection_lengths(), (60.0, 0.0))            # demandé : calculé


if __name__ == '__main__':
    unittest.main()
