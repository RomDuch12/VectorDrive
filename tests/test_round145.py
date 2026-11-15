"""Round 145 : calcul des parcours en mode sélection (seulement les objets
sélectionnés, chaque opération gardant ses couleurs) ou en mode couleur."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.core import geom
from vectordrive.core.document import Document, Group, Shape


def doc3():
    d = Document()
    a = Shape(path=geom.Path([geom.rect(0, 0, 10, 10)]), tool=0)
    b = Shape(path=geom.Path([geom.rect(20, 0, 10, 10)]), tool=0)
    c = Shape(path=geom.Path([geom.rect(40, 0, 10, 10)]), tool=1)
    g = Group(children=[Shape(path=geom.Path([geom.rect(60, 0, 5, 5)]), tool=0),
                        Shape(path=geom.Path([geom.rect(70, 0, 5, 5)]), tool=1)])
    for it in (a, b, c, g):
        d.add(it)
    return d, a, b, c, g


class TestSourceItems(unittest.TestCase):
    def test_colour_mode_unchanged(self):
        from vectordrive.cam import strategies as S
        from vectordrive.cam.model import Operation
        d, a, b, c, g = doc3()
        got = S.source_items(d, Operation(sources=[0]))
        self.assertEqual([x.id for x in got], [a.id, b.id, g.children[0].id])
        self.assertEqual(len(S.source_items(d, Operation())), 5)
        got = S.source_items(d, Operation(items=[g.id]))                       # objets choisis : le groupe
        self.assertEqual([x.id for x in got], [ch.id for ch in g.children])

    def test_selection_restricts_and_keeps_colours(self):
        from vectordrive.cam import strategies as S
        from vectordrive.cam.model import Operation
        d, a, b, c, g = doc3()
        sel = [a.id, c.id, g.id]
        self.assertEqual([x.id for x in S.source_items(d, Operation(sources=[0]), only=sel)],
                         [a.id, g.children[0].id])                             # b non sélectionné, c d'une autre couleur
        self.assertEqual([x.id for x in S.source_items(d, Operation(sources=[1]), only=sel)],
                         [c.id, g.children[1].id])
        self.assertEqual(S.source_items(d, Operation(sources=[0]), only=[]), [])
        self.assertEqual([x.id for x in S.source_items(d, Operation(items=[a.id, b.id]), only=[b.id])], [b.id])

    def test_compute_all_scope(self):
        from vectordrive.cam import model, strategies as S
        d, a, b, c, g = doc3()
        s = model.CamSetup()
        t = model.CamTool(name='F1', diameter=1, feed=600, number=1)
        s.tools = [t]
        s.operations = [model.Operation(kind='gravure', tool_id=t.id, sources=[0], depth=0.1)]
        full = S.compute_all(d, s)
        part = S.compute_all(d, s, only=[a.id])
        self.assertGreater(full[0].lengths()[0], part[0].lengths()[0] * 2.5)    # 3 contours de couleur 0, contre 1
        self.assertIsNone(S._ONLY.get())                                        # pas de reste après le calcul
        self.assertEqual(len(S.source_items(d, s.operations[0])), 3)


class TestPanel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_mode_switch_and_compute(self):
        from vectordrive.cam import model
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            d, a, b, c, g = doc3()
            w.canvas.set_document(d)
            s = model.CamSetup()
            t = model.CamTool(name='F1', diameter=1, feed=600, number=1)
            s.tools = [t]
            s.operations = [model.Operation(kind='gravure', tool_id=t.id, sources=[0], depth=0.1)]
            model.store(w.canvas.doc, s)
            panel = w.cam_panel
            panel.refresh()
            panel.set_selection_mode(False)
            full = panel.compute()[0].lengths()[0]
            panel.set_selection_mode(True)
            self.assertEqual(w.settings.value('fao/mode_calcul'), 'selection')
            w.canvas.selection = []
            self.assertEqual(panel.compute(), [])                                # rien de sélectionné
            self.assertIn('sélection', panel.info.text().lower())
            w.canvas.selection = [b]
            part = panel.compute()[0].lengths()[0]
            self.assertLess(part, full / 2)
            panel.set_selection_mode(False)
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
