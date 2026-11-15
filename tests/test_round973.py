"""Round 973 : SVG — la note de plaque et de position n'est suivie que si la page du fichier est restée celle de
l'écriture ; une page recadrée par un autre logiciel se lit comme tout SVG, sans plaque inventée."""
import os
import pathlib
import re
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r973.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])

from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Document, Plate, Shape  # noqa: E402
from vectordrive.io import registry, svg  # noqa: E402


def drawing():
    d = Document()
    d.plate = Plate(width=200.0, height=110.0, x=-100.0, y=-55.0)
    for c in (geom.rect(-90, -45, 30, 40), geom.polyline([(0, 10), (20, 40), (40, 10)])):
        d.layers[0].items.append(Shape(path=geom.Path([c])))
    return d


def box(doc):
    return [round(v, 3) for v in doc.bbox(include_plate=False)]


class Page(unittest.TestCase):

    def setUp(self):
        self.path = pathlib.Path(tempfile.mkdtemp()) / 'page.svg'
        registry.save_document(drawing(), str(self.path))
        self.text = self.path.read_text(encoding='utf-8')

    def test_the_note_holds_while_the_page_is_the_one_written(self):
        back = registry.open_document(str(self.path))
        self.assertEqual(box(back), box(drawing()))
        self.assertEqual((back.plate.x, back.plate.y, back.plate.width, back.plate.height), (-100.0, -55.0, 200.0, 110.0))
        self.assertRegex(self.text, r'data-vd-origine="-100\.0 -55\.0 200\.0 110\.0"')    # la page, pas le seul coin

    def test_a_page_changed_elsewhere_is_read_as_any_svg(self):
        # « ajuster la page au dessin » : le viewBox et la taille changent, la note reste
        cropped = re.sub(r'width="[^"]*" height="[^"]*" viewBox="[^"]*"',
                         'width="130mm" height="85mm" viewBox="-90 5 130 85"', self.text, count=1)
        self.assertNotEqual(cropped, self.text)
        self.assertIn('data-vd-plaque=', cropped)
        self.path.write_text(cropped, encoding='utf-8')
        back = registry.open_document(str(self.path))
        self.assertIsNone(back.plate)                                        # avant : la plaque d'origine, à tort
        bare = re.sub(r' data-vd-[a-z]+="[^"]*"', '', cropped)
        self.assertNotIn('data-vd-', bare)
        self.assertEqual(box(back), box(svg.read_data(bare.encode('utf-8'))))    # comme le même fichier sans note
        # une note d'une autre forme (deux nombres) : ignorée
        old = re.sub(r'data-vd-origine="[^"]*"', 'data-vd-origine="-100.0 -55.0"', self.text)
        self.path.write_text(old, encoding='utf-8')
        self.assertIsNone(registry.open_document(str(self.path)).plate)


if __name__ == '__main__':
    unittest.main()
