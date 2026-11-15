"""Round 980 : fiche d'outil (Mes outils) — les dessins DXF et STEP de l'outil s'ouvrent dans un nouvel onglet ou se
posent à la souris sur le dessin en cours."""
import json
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r980.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'
os.environ['VECTORDRIVE_TOOLS'] = os.path.join(tempfile.mkdtemp(), 'tools.json')

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])

NEO = {'version': '3.1', 'tools': {
    'cyl3': {'name': 'Cyl 3 z2', 'reference': 'ESSAI-3', 'rpm': 30000, 'feed_finishing': 1200, 'feed_plunge': 300,
             'diameter': 3.0, 'vendor': 'ESSAI', 'max_depth': 6,
             'geometry': {'Diameter': 3.0, 'TipAngle': 0.0, 'TipDiameter': 3.0, 'NumberOfFlutes': 2, 'FluteLength': 9.0},
             'dessins': {'cotes': {'D1': 3.0, 'D2': 6.0, 'L1': 50.0, 'L2': 9.0}, 'famille': 'fraise'}},
    'con30': {'name': 'Con 30', 'rpm': 25000, 'feed_finishing': 500, 'feed_plunge': 200, 'diameter': 3.0,
              'vendor': 'ESSAI', 'geometry': {'Diameter': 3.0, 'TipAngle': 30.0, 'TipDiameter': 0.2}}}}
KEYS = [('dxf', 'open'), ('dxf', 'place'), ('step', 'open'), ('step', 'place')]


class ToolDrawings(unittest.TestCase):

    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        pathlib.Path(os.environ['VECTORDRIVE_TOOLS']).unlink(missing_ok=True)
        self.d = self.library()

    def tearDown(self):
        self.w.modified = False
        for t in getattr(self.w, 'docs', []):
            t.modified = False
        self.w.close()

    def library(self):
        d = self.w.cam_panel.tool_library(exec_dialog=False)
        if not d.tools:
            with tempfile.TemporaryDirectory() as tmp:
                f = pathlib.Path(tmp) / 'neo.json'
                f.write_text(json.dumps(NEO), encoding='utf-8')
                d.import_file(f)
        d.select(self.tool(d, 'Cyl'))
        return d

    @staticmethod
    def tool(d, start):
        return next(t for t in d.tools if t.name.startswith(start))

    def buttons(self, d=None) -> dict:
        """Les boutons des dessins de la fiche : « Ouvrir » et « Poser », pour le DXF et pour le STEP."""
        found = getattr(d or self.d, 'drawing_buttons', {})
        self.assertEqual(sorted(found), KEYS)                                # avant : la fiche ne montrait que les chemins
        return found

    def enabled(self, d=None) -> list:
        b = self.buttons(d)
        return [b[k].isEnabled() for k in KEYS]

    def test_buttons_follow_the_drawings_of_the_tool(self):
        d = self.d
        self.assertEqual(self.enabled(), [False] * 4)                        # pas encore de dessins : rien à ouvrir
        out = d.draw()
        self.assertEqual(self.enabled(), [True] * 4)
        self.assertEqual(pathlib.Path(d.drawing_path('dxf')), pathlib.Path(out['dxf']))
        self.assertEqual([self.buttons()[k].text() for k in KEYS], ['Ouvrir', 'Poser au clic'] * 2)
        d.select(self.tool(d, 'Con'))                                        # un outil sans dessins
        self.assertEqual(self.enabled(), [False] * 4)
        self.assertFalse(d.use_drawing('dxf', 'open'))
        pathlib.Path(out['step']).unlink()                                   # un dessin effacé du disque
        d.select(self.tool(d, 'Cyl'))
        self.assertEqual(self.enabled(), [True, True, False, False])
        d.tree.setCurrentItem(None)                                          # plus d'outil choisi
        self.assertEqual(self.enabled(), [False] * 4)

    def test_open_in_a_new_tab(self):
        from vectordrive.core import geom
        from vectordrive.core.document import Shape
        d, w = self.d, self.w
        b = self.buttons()
        out = d.draw()
        w.canvas.doc.add(Shape(path=geom.Path([geom.rect(40, 20, 10, 10)])))  # le dessin en cours n'est pas vide
        w.modified = True
        tabs = len(w.docs)
        closed = []
        d.finished.connect(closed.append)
        b[('dxf', 'open')].click()
        app.processEvents()
        self.assertEqual(len(w.docs), tabs + 1)                              # un nouvel onglet, le dessin en cours gardé
        self.assertEqual(w.docs[w.doc_index].name(), pathlib.Path(out['dxf']).name)
        self.assertGreater(w.canvas.doc.stats()['contours'], 1)
        self.assertEqual(closed, [1])                                        # la fenêtre des outils laisse la place
        w.switch_tab(0)
        self.assertEqual(sum(len(L.items) for L in w.canvas.doc.layers), 1)

    def test_place_with_the_mouse_on_the_current_drawing(self):
        d, w = self.d, self.w
        b = self.buttons()
        d.draw()
        tabs = len(w.docs)
        before = sum(len(L.items) for L in w.canvas.doc.layers)
        closed = []
        d.finished.connect(closed.append)
        b[('step', 'place')].click()
        app.processEvents()
        self.assertEqual(w.canvas.tool, 'place_symbol')                      # le dessin suit le pointeur…
        self.assertEqual(closed, [1])
        w.canvas.tool_obj.callback((25.0, 10.0))                             # … un clic le pose
        app.processEvents()
        self.assertEqual(len(w.docs), tabs)                                  # sur le dessin en cours : pas d'onglet neuf
        self.assertEqual(sum(len(L.items) for L in w.canvas.doc.layers), before + 1)
        bb = [it for L in w.canvas.doc.layers for it in L.items][-1].bbox()   # centré sur le clic
        self.assertAlmostEqual((bb[0] + bb[2]) / 2, 25.0, places=6)
        self.assertAlmostEqual((bb[1] + bb[3]) / 2, 10.0, places=6)


if __name__ == '__main__':
    unittest.main()
