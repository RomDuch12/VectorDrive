"""Round 99 : raccourcis TypeEdit (TeTurboKey.ini), palette FAO à gauche
(Découpe 3D, reste matière, gamme, laser), BAT de la sélection ajustée à
la feuille (PDF sans perte, images comprises), enregistrement VND avec
compagnon .vdz."""
import math
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.cam import model, strategies
from vectordrive.core import geom, nodes
from vectordrive.core.cleanup import drop_null_segments
from vectordrive.core.document import Document, Image, Plate, Shape, Text
from vectordrive.core.geom import Affine, Contour, Line
from vectordrive.io import companion, proof
from vectordrive.ui import shortcuts as SC

TURBO = """[TAB_ACCELERATOR]
CMD_000=ID_FILE_NEW
MOD_000=FCONTROL FNOINVERT FVIRTKEY
KEY_000=N
CMD_001=ID_EDIT_REDO
MOD_001=FCONTROL FNOINVERT FVIRTKEY
KEY_001=E
CMD_002=ID_PALETTE_RECTANGLE
MOD_002=FNOINVERT FVIRTKEY
KEY_002=R
CMD_003=ID_FILE_VIEWER
MOD_003=FCONTROL FNOINVERT FSHIFT FVIRTKEY
KEY_003=O
CMD_004=ID_EDIT_UNDO
MOD_004=FALT FNOINVERT FVIRTKEY
KEY_004=VK_BACK
CMD_005=ID_EDIT_OPTIONS
MOD_005=FNOINVERT FVIRTKEY
KEY_005=VK_F10
CMD_006=ID_INCONNU
MOD_006=FNOINVERT FVIRTKEY
KEY_006='Z'
"""


def app():
    return QApplication.instance() or QApplication([])


class TestTurboKey(unittest.TestCase):
    def test_parse(self):
        e = SC.parse_turbokey(TURBO)
        self.assertEqual(e[:6], [('ID_FILE_NEW', 'Ctrl+N'), ('ID_EDIT_REDO', 'Ctrl+E'), ('ID_PALETTE_RECTANGLE', 'R'),
                                 ('ID_FILE_VIEWER', 'Ctrl+Shift+O'), ('ID_EDIT_UNDO', 'Alt+Backspace'),
                                 ('ID_EDIT_OPTIONS', 'F10')])
        self.assertEqual(e[6], ('ID_INCONNU', 'Z'))                        # touche entre apostrophes
        self.assertEqual(SC.unmapped(e), [('ID_INCONNU', 'Z')])

    def test_merge_newer_wins(self):
        new = [('ID_EDIT_REDO', 'Ctrl+E'), ('ID_COMPO_TEXTLIBRE', 'Alt+T')]
        old = [('ID_EDIT_REDO', 'Ctrl+A'), ('ID_COMPO_TEXTLIBRE', 'X'), ('ID_EDIT_SELECTALL', 'Ctrl+A'),
               ('ID_SNAP_PLUS', 'Ctrl+E')]
        self.assertEqual(SC.merge(new, old), new + [('ID_EDIT_SELECTALL', 'Ctrl+A')])

    #: jeu de type TypeEdit pour les essais (comme un TeTurboKey.ini importé ou un jeu de plugin)
    ESSAI = [('ID_EDIT_REDO', 'Ctrl+E'), ('ID_EDIT_SELECTALL', 'Ctrl+A'), ('ID_FICHIER_EXPORTER', 'Shift+E'),
             ('ID_PALETTE_DIGITDROITESINGLE', 'Ctrl+L'), ('ID_FILE_PRINT', 'Ctrl+P'), ('ID_PALETTE_RECTANGLE', 'R')]

    def test_effective_one_owner_per_key(self):
        app()
        defaults = {'redo': ['Ctrl+A'], 'select_all': ['Ctrl+L'], 'export': ['Ctrl+E'], 'tool_line': [],
                    'proof': ['Ctrl+P'], 'print': ['Ctrl+Shift+P']}
        m = SC.effective(defaults, 'typeedit', self.ESSAI)
        self.assertEqual(m['redo'], ['Ctrl+E'])
        self.assertEqual(m['select_all'], ['Ctrl+A'])
        self.assertEqual(m['export'], ['Shift+E'])
        self.assertEqual(m['tool_line'], ['Ctrl+L'])
        self.assertEqual(m['proof'], [])                                     # Ctrl+P : impression (TypeEdit)
        self.assertEqual(SC.conflicts(m), {})
        self.assertEqual(SC.effective(defaults, 'vectordrive'), defaults)
        mine = SC.effective(defaults, 'typeedit', self.ESSAI, custom={'proof': ['Ctrl+P']})
        self.assertEqual((mine['proof'], mine['print']), (['Ctrl+P'], []))

    def test_plugin_scheme_in_window(self):
        """Un jeu apporté par un plugin devient le jeu par défaut, sans conflit."""
        app()
        from vectordrive import plugins
        from vectordrive.ui.main_window import MainWindow
        plugins.reset()
        api = plugins.Api(plugins.REGISTRY, plugins.PluginInfo('essai', name='Essai'))
        api.add_shortcut_scheme('essai', 'Essai', self.ESSAI, default=True)
        w = MainWindow()
        try:
            self.assertEqual(SC.load(w.settings)[0], 'essai')
            self.assertEqual(SC.conflicts(SC.effective(w._default_shortcuts, 'essai')), {})
            self.assertEqual(w.A['tool_rect'].shortcuts()[0].toString(), 'R')
            self.assertEqual(w.A['redo'].shortcuts()[0].toString(), 'Ctrl+E')
            dlg = w.shortcuts_dialog(exec_dialog=False)
            self.assertGreaterEqual(dlg.combo.findData('essai'), 0)
            with tempfile.TemporaryDirectory() as tmp:
                f = os.path.join(tmp, 'TeTurboKey.ini')
                pathlib.Path(f).write_text(TURBO, encoding='cp1252')
                self.assertEqual(dlg.import_file(f), 7)
            self.assertEqual(dlg.scheme, 'typeedit')
            self.assertEqual(dlg.mapping()['undo'], ['Alt+Backspace'])
            dlg.combo.setCurrentIndex(dlg.combo.findData('vectordrive'))
            self.assertEqual(dlg.mapping()['redo'], w._default_shortcuts['redo'])
        finally:
            w.modified = False
            w.close()
            plugins.reset()

    def test_user_palette(self):
        txt = "[GLOBAL]\nNbCategories=2\n[TypeEdit_User]\nNameCmd_0=ID_PALETTE_RECTANGLE\n" \
              "NameCmd_1=ID_FAO_FABRICERESTEMATIERE\nNameCmd_2=ID_CMD_TP_CUTTING_3D\n[LaserType_User]\n" \
              "NameCmd_0=ID_CMD_TP_LASER\n"
        with tempfile.TemporaryDirectory() as tmp:
            f = os.path.join(tmp, 'T3PALUSER3D.INI')
            pathlib.Path(f).write_bytes(txt.encode('utf-16'))
            self.assertEqual(SC.user_palette(f), ['tool_rect', 'cam_new_reste', 'cam_new_decoupe3d', 'cam_new_laser'])


def rect_doc(w=30, h=15):
    d = Document()
    d.layers[0].items.append(Shape(path=geom.Path([geom.rect(0, 0, w, h)])))
    return d


class TestStrategies(unittest.TestCase):
    def test_decoupe3d_bevel(self):
        d = rect_doc()
        v = model.CamTool(kind='conique', diameter=6, angle=90, tip=0.2, step_down=0.25)
        s = model.CamSetup(tools=[v])
        op = model.Operation(kind='decoupe3d', tool_id=v.id, depth=1.0, side='exterieur')
        tp = strategies.compute(d, s, op)
        reg = strategies.region([d.layers[0].items[0].path], 0.01)
        offs = {}
        for m in tp.moves:
            if m.z < 0 and m.kind == 'feed':
                off = reg.exterior.distance(geom_point(m))
                self.assertGreaterEqual(off, v.radius_at(-m.z) - 0.02)       # jamais dans la pièce
                offs.setdefault(round(m.z, 6), []).append(off)
        for z, lst in offs.items():                                          # chaque passe : rayon du cône à z
            self.assertAlmostEqual(min(lst), v.radius_at(-z), delta=0.02)
        self.assertEqual(sorted(offs), [-1.0, -0.75, -0.5, -0.25])

    def test_items_scope(self):
        d = rect_doc()
        other = Shape(path=geom.Path([geom.rect(100, 100, 5, 5)]))
        d.layers[0].items.append(other)
        t = model.CamTool(diameter=1)
        s = model.CamSetup(tools=[t])
        op = model.Operation(kind='gravure', tool_id=t.id, items=[other.id])
        tp = strategies.compute(d, s, op)
        self.assertTrue(all(m.x >= 99 for m in tp.moves if m.z < 0))

    def test_rest_corners_only(self):
        d = rect_doc()
        big, small = model.CamTool(diameter=4), model.CamTool(diameter=1)
        s = model.CamSetup(tools=[big, small])
        op = model.Operation(kind='reste', tool_id=small.id, ref_tool_id=big.id, depth=0.5)
        tp = strategies.compute(d, s, op)
        cut = [(m.x, m.y) for m in tp.moves if m.z < 0]
        self.assertTrue(cut)
        for x, y in cut:                                                     # près d'un coin seulement
            self.assertLess(min(math.dist((x, y), c) for c in ((0, 0), (30, 0), (0, 15), (30, 15))), 3.5)
        self.assertTrue(any('coins' in w for w in tp.warnings))             # 4 × 0,5²(1 − π/4) hors de portée

    def test_rest_needs_bigger_tool(self):
        d = rect_doc()
        a = model.CamTool(diameter=1)
        s = model.CamSetup(tools=[a])
        tp = strategies.compute(d, s, model.Operation(kind='reste', tool_id=a.id, ref_tool_id=a.id))
        self.assertEqual(tp.moves, [])

    def test_laser_fill(self):
        d = rect_doc(10, 5)
        las = model.CamTool(kind='laser', diameter=0.05)
        s = model.CamSetup(tools=[las])
        op = model.Operation(kind='laser_gravure', tool_id=las.id, resolution=0.5)
        tp = strategies.compute(d, s, op)
        ys = sorted({round(m.y, 6) for m in tp.moves if m.kind == 'feed'})
        self.assertEqual(len(ys), 10)                                         # 5 mm / 0,5
        self.assertFalse(tp.warnings)
        op.hatch_angle = 90
        tp = strategies.compute(d, s, op)
        xs = sorted({round(m.x, 6) for m in tp.moves if m.kind == 'feed'})
        self.assertEqual(len(xs), 20)

    def test_laser_cut_kerf(self):
        d = rect_doc(10, 5)
        las = model.CamTool(kind='laser', diameter=0.2)
        s = model.CamSetup(tools=[las])
        tp = strategies.compute(d, s, model.Operation(kind='laser_decoupe', tool_id=las.id, side='exterieur'))
        xs = [m.x for m in tp.moves if m.kind == 'feed']
        self.assertAlmostEqual(min(xs), -0.1, places=6)
        self.assertEqual({m.z for m in tp.moves if m.kind == 'feed'}, {0.0})

    def test_vcarve_flat_floor_no_ridges(self):
        d = rect_doc(20, 12)
        v = model.CamTool(kind='conique', diameter=6, angle=60, tip=0.2, step_down=1, cut_length=10)
        s = model.CamSetup(tools=[v])
        op = model.Operation(kind='vcarve', tool_id=v.id, depth=0.8, resolution=0.05)
        tp = strategies.compute(d, s, op)
        reg = strategies.region([d.layers[0].items[0].path], 0.01)
        floor = sorted({round(reg.exterior.distance(geom_point(m)), 3) for m in tp.moves
                        if abs(m.z + 0.8) < 1e-9 and m.kind == 'feed'})
        gaps = [b - a for a, b in zip(floor, floor[1:])]
        self.assertGreater(len(gaps), 10)
        t = math.tan(math.radians(30))
        self.assertLessEqual(max(gaps), 2 * (0.1 + 0.02 * t) + 2e-3)        # crêtes ≤ 0,02 mm

    def test_gamme_rough_then_rest_of_floor(self):
        d = rect_doc(20, 12)
        v = model.CamTool(kind='conique', diameter=6, angle=60, tip=0.2, step_down=1, cut_length=10)
        f = model.CamTool(diameter=2)
        s = model.CamSetup(tools=[v, f])
        alone = strategies.compute(d, s, model.Operation(kind='vcarve', tool_id=v.id, depth=0.8))
        after = strategies.compute(d, s, model.Operation(kind='vcarve', tool_id=v.id, depth=0.8, ref_tool_id=f.id))
        self.assertLess(after.lengths()[0], alone.lengths()[0] / 2)          # le fond est fait par l'ébauche


def geom_point(m):
    from shapely.geometry import Point
    return Point(m.x, m.y)


class TestNodes(unittest.TestCase):
    def test_set_start_and_null_segments(self):
        c = geom.rect(0, 0, 10, 5)
        n = nodes.node_count(c)
        c2 = nodes.set_start(c, 1)
        self.assertEqual(c2.start, nodes.node_point(c, 1))
        self.assertEqual(nodes.node_count(c2), n)
        p = geom.Path([Contour([Line((0, 0), (5, 0)), Line((5, 0), (5, 0)), Line((5, 0), (5, 5))], False)])
        q, k = drop_null_segments(p)
        self.assertEqual((k, len(q.contours[0].segments)), (1, 2))


class TestProof(unittest.TestCase):
    def doc(self):
        app()
        d = Document()
        d.plate = Plate(x=0, y=0, width=600, height=400)
        a = Shape(path=geom.Path([geom.rect(10, 10, 20, 8)]))
        b = Shape(path=geom.Path([geom.circle((500, 300), 40)]))
        from PySide6.QtCore import QBuffer, QIODevice
        from PySide6.QtGui import QColor, QImage
        img = QImage(4, 2, QImage.Format.Format_ARGB32)
        img.fill(QColor(255, 0, 0, 128))
        buf = QBuffer()
        buf.open(QIODevice.OpenModeFlag.WriteOnly)
        img.save(buf, 'PNG')
        im = Image(data=bytes(buf.data()), fmt='png', matrix=Affine(20, 0, 0, -10, 12, 30))
        for it in (a, b, im):
            d.layers[0].items.append(it)
        return d, a, b, im

    def test_selection_fills_page(self):
        d, a, b, im = self.doc()
        info = proof.ProofInfo()
        self.assertAlmostEqual(proof.page_scale(d, info), 0.2)              # tout : 1:5
        self.assertAlmostEqual(proof.page_scale(d, proof.ProofInfo(fit_selection=True), [a, im]), 6.0)  # ajustée
        self.assertAlmostEqual(proof.page_scale(d, proof.ProofInfo(content='tout'), [a]), 0.2)
        self.assertAlmostEqual(proof.page_scale(d, proof.ProofInfo(fit_selection=False), [a, im]), 1.0)
        prims, _w, _h = proof.build(d, info, [a])
        self.assertFalse(any(pr.image is not None for pr in prims))
        self.assertEqual(sum(1 for pr in prims if pr.color == (0.45, 0.45, 0.45)), 0)   # pas de plaque

    def test_pdf_lossless_image(self):
        d, a, b, im = self.doc()
        with tempfile.TemporaryDirectory() as tmp:
            f = os.path.join(tmp, 'bat.pdf')
            proof.write(d, f, proof.ProofInfo(), items=[a, im])
            data = pathlib.Path(f).read_bytes()
            self.assertIn(b'/Subtype /Image /Width 4 /Height 2 /ColorSpace /DeviceRGB', data)
            self.assertIn(b'/SMask', data)                                    # transparence gardée
            self.assertNotIn(b'DCTDecode', data)                              # pas de JPEG
            from PySide6.QtCore import QBuffer, QByteArray, QIODevice
            from PySide6.QtPdf import QPdfDocument
            buf = QBuffer()
            buf.setData(QByteArray(data))
            buf.open(QIODevice.OpenModeFlag.ReadOnly)
            pd = QPdfDocument()
            pd.load(buf)                                                      # lu par Qt PDF (pdfium)
            self.assertEqual(pd.pageCount(), 1)
            pd.close()
            from vectordrive.io import pdf
            f2 = os.path.join(tmp, 'tout.pdf')
            pdf.write(d, f2)
            self.assertIn(b'/XObject', pathlib.Path(f2).read_bytes())


class TestCompanion(unittest.TestCase):
    def test_round_trip(self):
        app()
        from vectordrive.core import text as T
        from vectordrive.io import vnd
        from vectordrive.io.vnd_write import write
        d = rect_doc()
        t = Text(text='BFM', font='Arial', size=8, matrix=Affine.translation(5, 5))
        t.outline = T.layout('BFM', 'Arial', 8).transformed(t.matrix)
        d.layers[0].items.append(t)
        s = model.CamSetup(tools=[model.CamTool()])
        s.operations = [model.Operation(tool_id=s.tools[0].id, items=[d.layers[0].items[0].id])]
        model.store(d, s)
        self.assertEqual(companion.reasons(rect_doc()), [])
        with tempfile.TemporaryDirectory() as tmp:
            f = os.path.join(tmp, 'p.vnd')
            write(d, f)
            cp, why = companion.sync(d, f)
            self.assertEqual(cp.name, 'p.vdz')
            self.assertTrue(companion.is_companion(cp))
            back = vnd.read(f)
            msgs = companion.apply(back, f)
            self.assertIn('relu', msgs[0])
            self.assertIsInstance(back.layers[0].items[1], Text)
            self.assertEqual(model.setup_of(back).operations[0].items, [back.layers[0].items[0].id])
            data = bytearray(pathlib.Path(f).read_bytes())
            data[200] ^= 1
            pathlib.Path(f).write_bytes(bytes(data))
            back = vnd.read(f)
            msgs = companion.apply(back, f)
            self.assertIn('a changé', msgs[0])
            self.assertNotIsInstance(back.layers[0].items[1], Text)
            self.assertTrue(any('disparus' in m for m in msgs))
            # plus rien à garder : compagnon supprimé ; un .vdz indépendant n'est jamais touché
            plain = rect_doc()
            write(plain, f)
            self.assertEqual(companion.sync(plain, f), (None, []))
            self.assertFalse(cp.exists())
            from vectordrive.io import native
            native.write(plain, cp)
            with self.assertRaises(FileExistsError):
                companion.sync(d, f)


class TestPanel(unittest.TestCase):
    def test_palette_and_gamme(self):
        app()
        from vectordrive.ui.main_window import MainWindow
        from PySide6.QtCore import Qt
        w = MainWindow()
        try:
            self.assertEqual(w.dockWidgetArea(w.dock_cam), Qt.DockWidgetArea.LeftDockWidgetArea)
            sh = Shape(path=geom.Path([geom.rect(0, 0, 30, 15)]))
            w.canvas.doc.add(sh)
            w.canvas.select([sh])
            o = w.cam_panel.new_operation('decoupe3d', exec_dialog=False)
            self.assertEqual((o.kind, o.items), ('decoupe3d', [sh.id]))
            self.assertEqual(w.cam_panel.setup().tool(o.tool_id).kind, 'conique')
            ops = w.cam_panel.new_gamme(exec_dialog=False)
            self.assertEqual([x.kind for x in ops], ['poche', 'vcarve'])
            self.assertEqual(ops[1].ref_tool_id, ops[0].tool_id)
            self.assertGreater(ops[0].stock, 0)
            self.assertTrue(w.cam_panel.toolpaths)
            for key in ('cam_new_trace', 'cam_simulate', 'node_start', 'center_plate_h', 'remove_dup_points'):
                self.assertIn(key, w.A)
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
