"""Round 43 : scénarios complets sur fichiers réels, par la fenêtre
(ouvrir, modifier, enregistrer, rouvrir)."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from vectordrive.core.document import Image, Shape, Text
from vectordrive.core.geom import Affine
from vectordrive.io import registry, vnd
from tests.corpus import corpus

PERLIM = corpus('vnd_verite')
GANG = pathlib.Path('C:/ProgramData/Gravotech/TypeEdit_V15-LaserType_V15/GANGDRILL/gangdrill_32mm.gvt')
SYMBOLS = corpus('symboles_perso')
DXFS = corpus('dossier_corpus')


def need(p):
    if p is None or not pathlib.Path(p).exists():
        raise unittest.SkipTest(f'{p} absent')
    return str(p)


class Scenarios(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = pathlib.Path(self.tmp.name)

    def tearDown(self):
        self.w.modified = False
        self.w.close()
        self.tmp.cleanup()

    def test_vnd_move_all_and_back(self):
        w = self.w
        self.assertTrue(w.open_path(need(PERLIM)))
        st = w.canvas.doc.stats()
        bb = w.canvas.doc.bbox()
        w.canvas.select_all()
        w.canvas.transform_selection(Affine.translation(12.5, -4))
        out = self.dir / 'p.vnd'
        registry.save_document(w.canvas.doc, out)
        back = registry.open_document(out)
        self.assertEqual(back.stats(), st)
        bb2 = back.bbox()
        self.assertAlmostEqual(bb2[0] - bb[0], 12.5, places=4)
        self.assertAlmostEqual(bb2[1] - bb[1], -4, places=4)
        self.assertEqual(sum(isinstance(i, Image) for i in back.iter_leaves()), 1)

    def test_vdz_keeps_today_settings(self):
        w = self.w
        self.assertTrue(w.open_path(need(PERLIM)))
        w.canvas.add_guide('v', 42.0)
        w.canvas.doc.tools[0].width = 0.4
        out = self.dir / 'p.vdz'
        registry.save_document(w.canvas.doc, out)
        self.assertTrue(w.open_path(str(out)))
        self.assertEqual(w.canvas.guides, [['v', 42.0]])
        self.assertEqual(w.canvas.doc.tool_width(0), 0.4)

    def test_symbol_texts_font_change_and_svg(self):
        f = corpus('smb_textes') if corpus('smb_textes').exists() else None
        w = self.w
        self.assertTrue(w.open_path(need(f)))
        texts = [t for t in w.canvas.doc.iter_leaves() if isinstance(t, Text)]
        before = [t.outline.bbox() for t in texts]
        w.replace_font(texts, 'Arial')
        for t, a in zip(texts, before):
            b = t.outline.bbox()
            # reste en place : point d'ancrage de son alignement
            k = {'left': lambda q: q[0], 'right': lambda q: q[2],
                 'center': lambda q: (q[0] + q[2]) / 2}[t.align]
            self.assertLess(abs(k(a) - k(b)), 0.6 * t.size, t.text)
        out = self.dir / 's.svg'
        registry.save_document(w.canvas.doc, out)
        back = registry.open_document(out)
        self.assertGreater(back.stats()['contours'], 0)

    def test_gvt_holes_to_vnd(self):
        w = self.w
        self.assertTrue(w.open_path(need(GANG)))
        holes = [s for s in w.canvas.doc.iter_leaves() if isinstance(s, Shape) and 'trou' in s.extra]
        self.assertEqual(len(holes), 23)
        w.canvas.select([w.canvas.doc.layers[0].items[0]])
        w.canvas.transform_selection(Affine.translation(3, 3))
        out = self.dir / 'g.vnd'
        registry.save_document(w.canvas.doc, out)
        root, _ = vnd.parse(out.read_bytes())
        self.assertEqual(vnd.structure_signature(root).count('CTrou'), 23)

    def test_dxf_open_chain_check_nest(self):
        from vectordrive.core import check as CK
        from vectordrive.core import nesting as N
        from vectordrive.core.document import Plate
        f = corpus('dxf_reel_1') if corpus('dxf_reel_1').exists() else None
        w = self.w
        self.assertTrue(w.open_path(need(f)))
        self.assertTrue(any('raccord' in r for r in w.canvas.doc.report))
        CK.check(w.canvas.doc)
        w.canvas.doc.plate = Plate(400, 300)
        items = [it for it in w.canvas.doc.iter_items()][:20]
        r = w.apply_nesting(items, N.NestSpec(margin=5, gap=2))
        self.assertGreater(len(r.placed), 0)
        w._confirm_machine_export = lambda: True
        out = self.dir / 'e.png'
        from vectordrive.io import raster
        raster.write(w.canvas.doc, out, raster.RasterSpec(dpi=30))
        self.assertTrue(out.exists())


if __name__ == '__main__':
    unittest.main()
