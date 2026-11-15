"""Round 955 : la famille TypeEdit s'écrit en entier — dessin LaserType (.vnl) lu et écrit, modèle (.vnm) écrit, avec
les égards du VND ; le navigateur « Ouvrir » montre tous les dessins que VectorDrive lit."""
import os
import pathlib
import struct
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r955.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

import numpy as np  # noqa: E402
from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtGui import QColor, QImage  # noqa: E402
from PySide6.QtWidgets import QApplication, QFileDialog  # noqa: E402

app = QApplication.instance() or QApplication([])

from vectordrive.core import geom  # noqa: E402
from vectordrive.core import text as T  # noqa: E402
from vectordrive.core.document import Document, Plate, Shape, Text  # noqa: E402
from vectordrive.core.geom import Affine  # noqa: E402
from vectordrive.io import companion, registry  # noqa: E402


def drawing(text=False):
    d = Document()
    d.plate = Plate(width=120, height=60)
    d.layers[0].items += [Shape(path=geom.Path([geom.rect(10, 10, 100, 40, 5.0)])),
                          Shape(path=geom.Path([geom.circle((95.0, 22.0), 6.0)]))]
    if text:
        t = Text(text='VNL', font='Arial', size=8, matrix=Affine.translation(20, 30))
        t.outline = T.layout('VNL', 'Arial', 8).transformed(t.matrix)
        d.layers[0].items.append(t)
    return d


def box(doc):
    return tuple(round(v, 3) for v in doc.bbox())


def reads_and_writes(ext: str) -> bool:
    f, g = registry.by_extension('piece' + ext), registry.writer_for('piece' + ext)
    return f is not None and f.reader is not None and g is not None and g.writer is not None


class Family(unittest.TestCase):

    def test_lasertype_drawing_is_read_and_written(self):
        self.assertTrue(reads_and_writes('.vnl'), 'le .vnl n\'est ni lu ni écrit')            # avant
        d = drawing()
        with tempfile.TemporaryDirectory() as tmp:
            f, g = os.path.join(tmp, 'plaque.vnl'), os.path.join(tmp, 'plaque.vnd')
            registry.save_document(d, f)
            registry.save_document(drawing(), g)
            data = pathlib.Path(f).read_bytes()
            self.assertEqual(struct.unpack_from('<I', data, 0)[0], 0x00211173)      # la même archive que le VND
            self.assertEqual(len(data), os.path.getsize(g))
            back = registry.open_document(f)
            self.assertEqual(sum(len(L.items) for L in back.layers), 2)
            self.assertEqual(box(back), box(d))
            self.assertEqual((back.plate.width, back.plate.height), (120.0, 60.0))
            self.assertEqual(companion.sync(d, f), (None, []))              # rien de plus à garder : pas de compagnon
        self.assertIn('vnl', [x.key for x in registry.save_formats()])

    def test_template_is_written(self):
        self.assertTrue(reads_and_writes('.vnm'), 'le modèle .vnm n\'est que lu')             # avant
        d = drawing()
        with tempfile.TemporaryDirectory() as tmp:
            f = os.path.join(tmp, 'modele.vnm')
            registry.save_document(d, f)
            back = registry.open_document(f)
            self.assertEqual(box(back), box(d))

    def test_same_companion_as_a_vnd(self):
        self.assertTrue(reads_and_writes('.vnl'), 'le .vnl n\'est ni lu ni écrit')            # avant
        d = drawing(text=True)
        with tempfile.TemporaryDirectory() as tmp:
            f = os.path.join(tmp, 'plaque.vnl')
            registry.save_document(d, f)
            cp, why = companion.sync(d, f)
            self.assertEqual(cp.name, 'plaque.vnl.vdz')                     # à côté d'un plaque.vnd : chacun le sien
            self.assertEqual(len(why), 1)                                   # le texte modifiable, rien d'autre
            self.assertIn('texte', why[0])
            self.assertNotIn('position', ' '.join(why))
            back = registry.open_document(f)
            self.assertFalse(any(isinstance(it, Text) for L in back.layers for it in L.items))   # en courbes
            companion.apply(back, f)
            self.assertTrue(any(isinstance(it, Text) for L in back.layers for it in L.items))    # le texte revient
            self.assertEqual(companion.twin_of(cp), pathlib.Path(f))


class Solid(unittest.TestCase):

    def test_dimensions_are_not_part_of_the_solid(self):
        from vectordrive.core import dims
        from vectordrive.io import write3d
        d = Document()
        d.layers[0].items += [Shape(path=geom.Path([geom.rect(10, 10, 40, 20)])),
                              dims.group(dims.Dim(kind='libre', points=[(10.0, 10.0), (50.0, 10.0)], offset=-8.0))]
        self.assertGreater(sum(len(c.path.contours) for c in d.layers[0].items[1].children), 2)   # flèches, chiffres
        with tempfile.TemporaryDirectory() as tmp:
            f = os.path.join(tmp, 'cotee.step')
            registry.save_document(d, f)
            text = pathlib.Path(f).read_text(encoding='ascii')
            self.assertEqual(text.count('MANIFOLD_SOLID_BREP'), 1)          # avant : les flèches et les chiffres aussi
        self.assertEqual(len(write3d.flat_paths(d)), 1)

    def test_a_shape_laid_twice_counts_once(self):
        from vectordrive.core.geom import Contour, Line
        from vectordrive.io import mesh3d, write3d
        d = Document()
        again = geom.rect(10, 10, 40, 20)
        again = Contour(again.segments[2:] + again.segments[:2], True)      # le même, parti d'un autre coin
        ends_meet = Contour([Line((60.0, 10.0), (80.0, 10.0)), Line((80.0, 10.0), (80.0, 30.0)),
                             Line((80.0, 30.0), (60.0, 10.0))], False)       # pas marqué fermé : ses bouts se rejoignent
        flat = Contour([Line((0.0, 50.0), (30.0, 50.0)), Line((30.0, 50.0), (0.0, 50.0))], True)     # sans aire
        d.layers[0].items += [Shape(path=geom.Path([geom.rect(10, 10, 40, 20)])), Shape(path=geom.Path([again])),
                              Shape(path=geom.Path([ends_meet])), Shape(path=geom.Path([flat]))]
        self.assertEqual(len(write3d.loops_of(d)), 2)                       # avant : 3 — doublon et plat comptés, triangle non
        with tempfile.TemporaryDirectory() as tmp:
            f, g = os.path.join(tmp, 'double.step'), os.path.join(tmp, 'double.stl')
            registry.save_document(d, f)                                    # avant : le doublon s'effaçait (pair-impair)
            text = pathlib.Path(f).read_text(encoding='ascii')
            self.assertEqual(text.count('MANIFOLD_SOLID_BREP'), 2)          # le rectangle, le triangle
            self.assertEqual(text.count("PLANE('"), (4 + 2) + (3 + 2))      # flancs exacts : pas de repli en polygones
            registry.save_document(d, g)
            T = np.asarray(mesh3d.read_stl(g), np.float64)
            vol = abs(float(np.einsum('ij,ij->i', T[:, 0], np.cross(T[:, 1], T[:, 2])).sum()) / 6)
            self.assertAlmostEqual(vol, (800 + 200) * 3.0, delta=0.5)


class Window(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from vectordrive.ui.main_window import MainWindow
        cls.w = MainWindow()

    @classmethod
    def tearDownClass(cls):
        cls.w.modified = False
        cls.w.close()

    def test_ctrl_s_saves_a_lasertype_drawing_in_place(self):
        from vectordrive.io import vnd_write
        w = self.w
        with tempfile.TemporaryDirectory() as tmp:
            f, m = os.path.join(tmp, 'plaque.vnl'), os.path.join(tmp, 'modele.vnm')
            vnd_write.write(drawing(), f)
            vnd_write.write(drawing(), m)
            self.assertTrue(w.open_path(f), 'un .vnl ne s\'ouvre pas')                          # avant
            self.assertEqual(pathlib.Path(w.path), pathlib.Path(f))        # Ctrl+S : ce fichier, comme un VND
            w.canvas.doc.add(Shape(path=geom.Path([geom.rect(40, 20, 10, 10)])))
            w.modified = True
            w.save()
            self.assertEqual(sum(len(L.items) for L in registry.open_document(f).layers), 3)
            self.assertFalse(w.modified)
            with mock.patch.object(QFileDialog, 'getSaveFileName', return_value=('', '')) as ask:
                self.assertTrue(w.open_path(m))
                self.assertFalse(w.path)                                    # un modèle reçu : « Enregistrer sous »
                w.save_as()
            offered = ask.call_args[0][3]
            self.assertIn('Dessin LaserType (*.vnl)', offered)
            self.assertIn('Modèle TypeEdit (*.vnm)', offered)
            w.modified = False


class Browser(unittest.TestCase):

    def test_open_browser_lists_every_readable_format(self):
        from vectordrive.ui import file_browser as FB
        every = {e for f in registry.FORMATS if f.reader is not None for e in f.extensions}
        self.assertEqual(set(FB.BROWSER_EXT), every)                        # avant : dix extensions
        self.assertEqual(FB.BROWSER_EXT[:3], ('.vnd', '.dxf', '.smb'))
        labels = [label for label, _e in FB.filters()]
        self.assertEqual(labels[:2], ['Dessins et programmes', 'TypeEdit VND'])     # rangs gardés (filtre retenu)
        table = dict(FB.filters())
        self.assertTrue(every <= set(table['Dessins et programmes']))
        self.assertIn('.vnl', table['TypeEdit et LaserType (VND, VNL, modèles, GVT)'])
        self.assertIn('.png', table['Images'])
        self.assertIn('.stl', table['Pièces 3D (STEP, IGES, STL, 3D XML, CATIA)'])
        self.assertIn('.plt', table['Autres dessins (HPGL, EMF, WMF, CorelDRAW, Visio…)'])
        d = pathlib.Path(tempfile.mkdtemp())
        registry.save_document(drawing(), str(d / 'a.igs'))
        registry.save_document(drawing(), str(d / 'b.plt'))
        img = QImage(8, 8, QImage.Format.Format_RGB32)
        img.fill(QColor('white'))
        img.save(str(d / 'c.png'))
        (d / 'notes.txt').write_text('rien', encoding='ascii')
        p = FB.FileBrowserPanel(QSettings(os.path.join(tempfile.mkdtemp(), 's.ini'), QSettings.Format.IniFormat))
        try:
            p.EXTS = FB.BROWSER_EXT
            p.show_folder(d)
            rows = [p.list.item(i) for i in range(p.list.count())]
            names = [it.text() for it in rows if it.data(FB.ROLE_KIND) is None]     # les fichiers, pas le dossier parent
            self.assertEqual(sorted(names), ['a.igs', 'b.plt', 'c.png'])
        finally:
            p.deleteLater()

    def test_no_preview_through_another_program(self):
        from vectordrive.ui import symbols
        d = pathlib.Path(tempfile.mkdtemp())
        f = d / 'logo.emf'
        f.write_bytes(b'\x01\x00\x00\x00')
        with mock.patch('vectordrive.io.inkscape_import.read', return_value=drawing()) as read:
            self.assertIsNone(symbols.preview_image(f, 64))
            self.assertIn('logo.emf', symbols.describe_file(f))
            read.assert_not_called()                                        # avant : Inkscape lancé pour la vignette
            self.assertEqual(box(registry.open_document(str(f))), box(drawing()))   # ouvert : lu comme les autres
            read.assert_called_once()


if __name__ == '__main__':
    unittest.main()
