"""Round 744 : onglet « Design 3D » rangé comme SolidCraft — Créer,
Modifier, Combiner, Tôlerie, Plasturgie, Inspecter, Échanges ; les volumes
ne sont plus dans l'onglet 3D (reliefs)."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))


def tab_index(r, title):
    return next(i for i in range(r.count()) if r.tabText(i) == title)


class TestDesign3D(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])
        from vectordrive.ui.main_window import MainWindow
        cls.w = MainWindow()

    @classmethod
    def tearDownClass(cls):
        cls.w.modified = False
        cls.w.close()

    def actions(self, title):
        from PySide6.QtWidgets import QToolButton
        r = self.w.ribbon
        if title == 'CAD 3D':                                            # round 903 : la page CAD du mode 3D
            page = r.widget(next(i for i in range(r.count()) if r.page(i) is not None and r.page(i).property('vd_cad') == '3d'
                                 and not r.widget(i).property('te_layout')))
        else:
            page = r.widget(tab_index(r, title))
        return {b.defaultAction() for b in page.findChildren(QToolButton) if b.defaultAction()}

    def test_tab(self):
        r = self.w.ribbon
        titles = [r.tabText(i) for i in range(r.count())]
        cad3d = next(i for i in range(r.count()) if r.page(i) is not None and r.page(i).property('vd_cad') == '3d'
                     and not r.widget(i).property('te_layout'))
        self.assertEqual(titles[cad3d], 'CAD')                           # round 903 : l'ancien onglet « 3D »
        self.assertLess(cad3d, titles.index('Design 3D'))
        self.assertLess(titles.index('Design 3D'), titles.index('Design STEP'))
        page = r.page(tab_index(r, 'Design 3D'))
        self.assertEqual([g.title.text() for g in page.groups()],
                         ['Créer', 'Modifier', 'Combiner', 'Tôlerie', 'Plasturgie', 'Inspecter', 'Échanges'])
        got = self.actions('Design 3D')
        A = self.w.A
        every = {k for _t, big, small in self.w.DESIGN3D_GROUPS for k in big + small}
        self.assertEqual({A[k] for k in every}, got)
        solids = {k for k in A if k.startswith('solid_')} | {'relief_to_solid'}
        ribbon = {A[k] for k in solids if A[k] in got}
        self.assertEqual(len(ribbon), len(every))                       # chacun une fois
        self.assertFalse({A[k] for k in solids} & self.actions('CAD 3D'))   # l'onglet CAD en 3D : les reliefs
        self.assertIn(A['galbe'], self.actions('CAD 3D'))


if __name__ == '__main__':
    unittest.main()
