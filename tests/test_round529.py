"""Round 529 : vérification par lots — les programmes machine sont lus aussi (mouvements, outils,
remarques du lecteur) ; la conversion par lots reste aux seuls dessins."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from vectordrive.core import geom
from vectordrive.core.document import Document, Shape
from vectordrive.io import batch, registry

GCODE = 'G21 G90\nT1\nG0 Z5\nG0 X0 Y0\nG1 Z-0.5 F300\nG1 X30\nT2\nG0 Z5\nG0 X5 Y5\nG1 Z-1\nG1 Y20\nM30\n'


class TestCheckPrograms(unittest.TestCase):
    def test_programs_in_check(self):
        d = pathlib.Path(tempfile.mkdtemp())
        (d / 'a.nc').write_text(GCODE)
        (d / 'vide.tap').write_text('% rien\n')
        doc = Document()
        doc.add(Shape(path=geom.Path([geom.circle((0, 0), 3)])))
        registry.save_document(doc, d / 'rond.dxf')
        self.assertEqual([f.name for f in batch.collect([d])], ['rond.dxf'])            # conversion : dessins
        files = batch.collect([d], programs=True)
        self.assertEqual(sorted(f.name for f in files), ['a.nc', 'rond.dxf', 'vide.tap'])
        rows = {pathlib.Path(r['fichier']).name: r for r in batch.check(files)}
        a = rows['a.nc']
        self.assertTrue(a['lu'])
        self.assertEqual(a['format'], 'programme iso')
        self.assertEqual(a['contours'], 2)                                             # deux outils
        self.assertGreater(a['objets'], 6)
        self.assertFalse(rows['vide.tap']['lu'])
        self.assertIn('aucun mouvement', rows['vide.tap']['erreur'])
        self.assertTrue(rows['rond.dxf']['lu'])


if __name__ == '__main__':
    unittest.main()
