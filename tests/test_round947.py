"""Round 947 : l'IGES s'écrit — courbes exactes (droites, arcs, Bézier), un niveau par calque ; l'EMF et le WMF
s'écrivent par Inkscape. Tous trois entrent dans « Enregistrer sous » et « Exporter »."""
import math
import os
import pathlib
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r947.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Document, Layer, Shape  # noqa: E402
from vectordrive.core.geom import Contour, Cubic, Line  # noqa: E402
from vectordrive.io import companion, inkscape_import as IK, registry  # noqa: E402


class Settings:
    def value(self, key, default=None):
        return default


def drawing():
    d = Document()
    wave = Contour([Cubic((0.0, 40.0), (10.0, 55.0), (20.0, 25.0), (30.0, 40.0)), Line((30.0, 40.0), (45.5, 40.25))],
                   False)
    d.layers[0].items += [Shape(path=geom.Path([geom.rect(10, 10, 40, 20)])),
                          Shape(path=geom.Path([geom.circle((30.0, 20.0), 6.0)])),
                          Shape(path=geom.Path([wave]))]
    return d


def kinds(doc):
    return [[type(s).__name__ for c in it.path.contours for s in c.segments] for L in doc.layers for it in L.items]


class Iges(unittest.TestCase):

    def test_iges_is_written_with_exact_curves(self):
        d = drawing()
        with tempfile.TemporaryDirectory() as tmp:
            f = os.path.join(tmp, 'piece.igs')
            registry.save_document(d, f)                                    # avant : format non pris en charge en écriture
            lines = pathlib.Path(f).read_text(encoding='ascii').split('\n')[:-1]
            self.assertTrue(all(len(x) == 80 for x in lines))
            self.assertEqual((lines[0][72], lines[-1][72]), ('S', 'T'))
            back = registry.open_document(f)
            self.assertEqual(kinds(back), kinds(d))                         # arcs et Bézier restés des courbes
            self.assertIn('Conic', kinds(back)[1])
            self.assertIn('Cubic', kinds(back)[2])
            self.assertEqual(companion.differences(d, back), [])            # rendu tel quel : pas de compagnon
            self.assertEqual(companion.sync(d, f), (None, []))
            circle = back.layers[0].items[1].path.contours[0]
            for s in circle.segments:
                for t in (0.0, 0.5, 1.0):
                    x, y = s.point(t)
                    self.assertAlmostEqual(math.hypot(x - 30.0, y - 20.0), 6.0, places=6)
            # un niveau par calque
            d.layers.append(Layer(name='Découpe', items=[Shape(path=geom.Path([geom.rect(5, 5, 50, 30)]))]))
            registry.save_document(d, f)
            back = registry.open_document(f)
            self.assertEqual([len(L.items) for L in back.layers], [3, 1])
        self.assertIn('iges', [x.key for x in registry.save_formats()])


class Metafile(unittest.TestCase):

    def test_emf_goes_through_inkscape(self):
        seen = []

        def run(cmd, **k):                                                  # Inkscape, imité : il écrit le fichier demandé
            seen.append(cmd)
            out = next(a.split('=', 1)[1] for a in cmd if a.startswith('--export-filename='))
            self.assertIn('<svg', pathlib.Path(cmd[-1]).read_text(encoding='utf-8'))
            pathlib.Path(out).write_bytes(b'EMF imite')
            return subprocess.CompletedProcess(cmd, 0, b'', b'')
        with tempfile.TemporaryDirectory() as tmp:
            f = os.path.join(tmp, 'logo.emf')
            with mock.patch.object(IK, 'find', return_value='C:/x/inkscape.exe'), \
                    mock.patch.object(subprocess, 'run', side_effect=run):
                registry.save_document(drawing(), f)                        # avant : format non pris en charge en écriture
                self.assertEqual(pathlib.Path(f).read_bytes(), b'EMF imite')
                self.assertIn('--export-type=emf', seen[0])
                d = drawing()
                cp, why = companion.sync(d, f)                              # pas relu (ce serait relancer Inkscape)
                self.assertEqual((cp.name, why), ('logo.emf.vdz', ['dessin converti par Inkscape']))
                self.assertEqual(len(seen), 1)
            with mock.patch.object(IK, 'find', return_value=''), self.assertRaises(ValueError) as ctx:
                registry.save_document(drawing(), f)
            self.assertIn('Inkscape', str(ctx.exception))
        self.assertEqual(registry.by_extension('x.emf').key, 'inkscape')    # la lecture : comme avant
        self.assertIn('*.wmf', registry.filter_string(write=True))
        self.assertNotIn('*.cdr', registry.filter_string(write=True))

    @unittest.skipUnless(IK.find(Settings()), 'Inkscape absent de ce poste')
    def test_emf_for_real(self):
        tmp = tempfile.mkdtemp()
        try:
            for ext in ('.emf', '.wmf'):
                f = os.path.join(tmp, 'logo' + ext)
                registry.save_document(drawing(), f)                        # avant : format non pris en charge en écriture
                self.assertGreater(os.path.getsize(f), 100)
                back = registry.open_document(f)
                bb, want = back.bbox(), drawing().bbox()
                self.assertAlmostEqual(bb[2] - bb[0], want[2] - want[0], delta=0.5)
                self.assertAlmostEqual(bb[3] - bb[1], want[3] - want[1], delta=0.5)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    unittest.main()
