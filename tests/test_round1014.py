"""Round 1014 : réponse 20 du 14/11 — brut d'un dessin 2D : plaque ou contour dessiné, marges, surépaisseur au-dessus
de la plaque ; gardé avec le réglage FAO ; la simulation part de son haut."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1014.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])

from vectordrive.cam import model  # noqa: E402
from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Document, Plate, Shape  # noqa: E402


def drawing(plate=True):
    doc = Document()
    doc.plate = Plate(width=100.0, height=50.0, thickness=3.0) if plate else None
    disc = Shape(path=geom.Path([geom.circle((50.0, 25.0), 10.0)]), tool=0)
    doc.add(disc)
    doc.add(Shape(path=geom.Path([geom.rect(70.0, 5.0, 4.0, 4.0)]), tool=0))
    return doc, disc


def engraving(doc, item):
    s = model.CamSetup()
    t = model.CamTool(name='Cyl 1', diameter=1.0, number=1, cut_length=5, step_down=0.5)
    s.tools = [t]
    s.operations = [model.Operation(name='G', kind='gravure', tool_id=t.id, items=[item.id], depth=0.2)]
    return s


class Stock2DModel(unittest.TestCase):

    def test_plate_and_margins(self):
        from vectordrive.core import stock2d
        doc, _disc = drawing()
        st = stock2d.Stock2D(kind='plaque', top=1.0, side=2.0)
        box = stock2d.resolve(st, doc)
        self.assertEqual((box.x0, box.y0, box.x1, box.y1), (-2.0, -2.0, 102.0, 52.0))
        self.assertEqual((box.top, box.bottom), (1.0, -3.0))                 # épaisseur : celle de la plaque
        self.assertEqual(stock2d.resolve(stock2d.Stock2D(kind='plaque', thickness=8.0), doc).bottom, -8.0)
        doc.plate = None
        self.assertIsNone(stock2d.resolve(st, doc))
        self.assertIsNone(stock2d.resolve(stock2d.Stock2D(), doc))

    def test_drawn_contour(self):
        from vectordrive.core import stock2d
        doc, disc = drawing()
        box = stock2d.resolve(stock2d.Stock2D(kind='contour', item=disc.id, top=0.5, side=1.0), doc)
        self.assertAlmostEqual(box.x1 - box.x0, 22.0, places=1)              # Ø 20 et 1 mm de marge
        inside = box.inside([50.0, 60.5, 41.0, 41.5], [25.0, 25.0, 34.0, 25.0])
        self.assertEqual(list(inside), [True, True, False, True])            # coin de la boîte : hors du disque
        self.assertAlmostEqual(box.footprint().area, 3.1416 * 11 * 11, delta=2.0)
        self.assertIsNone(stock2d.resolve(stock2d.Stock2D(kind='contour', item='absent'), doc))
        square = Shape(path=geom.Path([geom.rect(40.0, 15.0, 20.0, 20.0)]), tool=0)   # même boîte que le disque
        doc.add(square)
        a = stock2d.resolve(stock2d.Stock2D(kind='contour', item=disc.id), doc)
        b = stock2d.resolve(stock2d.Stock2D(kind='contour', item=square.id), doc)
        self.assertEqual((a.x0, a.y0, a.x1, a.y1), (b.x0, b.y0, b.x1, b.y1))
        self.assertNotEqual(repr(a), repr(b))                                # le cache des simulations les distingue

    def test_kept_with_the_cam_setup(self):
        from vectordrive.core import stock2d
        s = model.CamSetup()
        s.stock2d = stock2d.to_dict(stock2d.Stock2D(kind='contour', item='abc', top=1.5, side=2.0))
        back = model.CamSetup.from_dict(s.to_dict())
        st = stock2d.of_setup(back)
        self.assertEqual((st.kind, st.item, st.top, st.side, st.thickness), ('contour', 'abc', 1.5, 2.0, 0.0))
        self.assertEqual(stock2d.of_setup(model.CamSetup.from_dict({})).kind, '')
        self.assertEqual(stock2d.from_dict({'kind': 'nimporte', 'top': 'x'}).kind, '')


class Simulation(unittest.TestCase):

    def test_starts_from_the_top_of_the_stock(self):
        from vectordrive.cam import simulate as SIM
        from vectordrive.cam import strategies
        from vectordrive.core import stock2d
        doc, disc = drawing()
        s = engraving(doc, disc)
        paths = [tp for tp in strategies.compute_all(doc, s) if tp.moves]
        self.assertTrue(paths)
        self.assertIsNone(SIM.stock_of(doc, s, paths))                        # sans brut : comme avant
        flat = SIM.simulate(paths, s, res=0.25)
        self.assertAlmostEqual(float(flat.H.max()), 0.0)
        s.stock2d = stock2d.to_dict(stock2d.Stock2D(kind='plaque', top=1.0))
        box = SIM.stock_of(doc, s, paths)                                     # avant : None sans pièce 3D
        self.assertIsNotNone(box)
        sim = SIM.simulate(paths, s, res=0.25, stock=box)
        self.assertAlmostEqual(float(sim.H.max()), 1.0)                       # le haut du brut
        self.assertGreater(sim.removed, flat.removed * 3)                     # 1,2 mm traversé au lieu de 0,2
        square = Shape(path=geom.Path([geom.rect(45.0, 20.0, 10.0, 10.0)]), tool=0)   # brut : un carré dessiné
        doc.add(square)
        s.stock2d = stock2d.to_dict(stock2d.Stock2D(kind='contour', item=square.id, top=1.0))
        box = SIM.stock_of(doc, s, paths)
        self.assertIsNotNone(box.poly)
        sim = SIM.simulate(paths, s, res=0.25, stock=box)
        def at(x, y):
            return float(sim.H[int(round((y - sim.y0) / sim.res)), int(round((x - sim.x0) / sim.res))])
        self.assertAlmostEqual(at(50.0, 25.0), 1.0)                           # dans le carré (centre du disque)
        self.assertAlmostEqual(at(58.0, 25.0), 0.0)                           # hors du carré : la plaque
        step = SIM.simulate_range(paths, s, SIM.blank(sim), 0, 10 ** 9)       # pas à pas : le même brut
        self.assertAlmostEqual(float(step.H.max()), 1.0)
        paths[0].stock = object()                                             # programme relu avec son brut
        self.assertIsNone(SIM.stock_of(doc, s, paths))


class Window(unittest.TestCase):

    def test_dialog_and_panel(self):
        from vectordrive.core import stock2d
        from vectordrive.ui.stock2d_dialog import Stock2DDialog
        doc, disc = drawing(plate=False)
        dlg = Stock2DDialog(None, stock2d.Stock2D(kind='plaque'), doc, disc)
        self.assertFalse(dlg.ok.isEnabled())                                  # pas de plaque
        self.assertTrue(dlg.take_picked())
        dlg.spins['top'].setValue(1.0)
        v = dlg.value()
        self.assertEqual((v.kind, v.item, v.top), ('contour', disc.id, 1.0))
        self.assertTrue(dlg.ok.isEnabled())
        self.assertIn('au-dessus', dlg.info.text())
        dlg.spins['top'].setValue(0.0)
        self.assertIn('plaque plate', dlg.info.text())                       # sans surépaisseur : rien ne change
        dlg.deleteLater()
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            p = w.cam_panel
            self.assertIsNotNone(p.stock2d_dialog(exec_dialog=False))
            p.set_stock2d(stock2d.Stock2D(kind='plaque', top=0.5))
            self.assertEqual(stock2d.of_setup(p.setup()).top, 0.5)
            p.set_stock2d(stock2d.Stock2D())
            self.assertEqual(p.setup().stock2d, {})
        finally:
            w.modified = False
            for t in getattr(w, 'docs', []):
                t.modified = False
            w.close()
            app.processEvents()


if __name__ == '__main__':
    unittest.main()
