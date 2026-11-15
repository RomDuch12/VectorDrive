"""Round 972 : la plaque écrite dans le DXF, l'IGES et le SVG eux-mêmes (et, en SVG, la place du dessin), et relue :
un dessin simple enregistré dans ces formats n'a plus besoin d'un compagnon « pour la plaque »."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r972.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])

from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Document, Plate, Shape  # noqa: E402
from vectordrive.io import companion, registry, svg  # noqa: E402

PLATE = dict(width=200.0, height=110.0, corner_radius=4.0, material='Laiton poli « été »', x=-100.0, y=-55.0,
             thickness=3.0, margins=[2.0, 2.0, 5.0, 5.0])


def drawing(plate=True):
    d = Document()
    if plate:
        d.plate = Plate(**PLATE)
    for c in (geom.rect(-90, -45, 30, 40), geom.polyline([(0, 10), (20, 40), (40, 10)])):
        d.layers[0].items.append(Shape(path=geom.Path([c])))
    return d


def saved(ext, plate=True):
    d = drawing(plate)
    path = pathlib.Path(tempfile.mkdtemp()) / f'plaque{ext}'
    registry.save_document(d, str(path))
    return d, path, registry.open_document(str(path))


class PlateInTheFile(unittest.TestCase):

    def check(self, ext):
        d, path, back = saved(ext)
        self.assertEqual(companion.foreign_reasons(d, str(path)), [])       # avant : ['plaque'] (et la position, en SVG)
        self.assertEqual(back.plate.__dict__, d.plate.__dict__)
        self.assertEqual([round(v, 3) for v in back.bbox(include_plate=False)],
                         [round(v, 3) for v in d.bbox(include_plate=False)])
        _d, _path, bare = saved(ext, plate=False)
        self.assertIsNone(bare.plate)                                        # sans plaque : rien d'inventé
        return path

    def test_dxf(self):
        import ezdxf
        path = self.check('.dxf')
        head = ezdxf.readfile(str(path)).header
        self.assertEqual((tuple(head['$LIMMIN'])[:2], tuple(head['$LIMMAX'])[:2]), ((-100.0, -55.0), (100.0, 55.0)))

    def test_iges(self):
        path = self.check('.igs')
        rows = path.read_text(encoding='ascii').splitlines()
        self.assertEqual({len(r) for r in rows}, {80})                       # la note tient dans les lignes de 80 colonnes
        self.assertGreater(sum(r[72] == 'S' for r in rows), 1)
        self.assertEqual(int(rows[-1][1:8]), sum(r[72] == 'S' for r in rows))

    def test_svg(self):
        path = self.check('.svg')
        self.assertIn('data-vd-plaque=', path.read_text(encoding='utf-8'))
        self.assertNotIn('data-vd-', svg.to_string(drawing()))               # presse-papiers, aperçus : inchangés

    def test_a_damaged_note_is_no_plate(self):
        from vectordrive.io import plate_note
        ok = plate_note.to_text(Plate(**PLATE))
        self.assertTrue(ok.isascii())
        self.assertEqual(plate_note.from_text(ok).__dict__, Plate(**PLATE).__dict__)
        self.assertEqual(plate_note.find_in(f'en-tête   {plate_note.TAG} : {ok}   suite').__dict__, Plate(**PLATE).__dict__)
        for bad in ('', 'null', '[]', '{', '{"width":"x","height":5}', '{"width":0,"height":5}',
                    '{"width":10,"height":5,"margins":[1,2]}', '{"width":10,"height":5,"visible":"oui"}'):
            self.assertIsNone(plate_note.from_text(bad), bad)
        self.assertEqual(plate_note.from_text('{"width":10,"height":5,"plus_tard":1}').width, 10.0)   # champ inconnu ignoré
        self.assertEqual(plate_note.to_text(Plate(width=10, height=5, material='x' * 300)), '')     # trop longue : pas écrite
        self.assertEqual(plate_note.to_text(None), '')


if __name__ == '__main__':
    unittest.main()
