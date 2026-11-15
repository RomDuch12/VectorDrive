"""Round 964 : une grande image exportée n'est plus déclarée « illisible » — la vérification lit sa taille sans la
décoder (Qt refuse par défaut de décoder plus de 256 Mo)."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r964.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtGui import QColor, QImage, QImageReader  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])

from vectordrive.ui import export_dialog as E  # noqa: E402


class BigImage(unittest.TestCase):

    def test_an_image_qt_will_not_decode_is_still_checked(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = os.path.join(tmp, 'grande.png')
            img = QImage(1200, 900, QImage.Format.Format_RGB32)
            img.fill(QColor('white'))
            self.assertTrue(img.save(f))
            limit = QImageReader.allocationLimit()
            QImageReader.setAllocationLimit(1)           # comme une image de plus de 256 Mo avec la limite d'office
            try:
                self.assertTrue(QImage(f).isNull())      # Qt refuse de la décoder…
                ok, report = E.verify_export(f)
            finally:
                QImageReader.setAllocationLimit(limit)
            self.assertTrue(ok, report)                  # … elle n'en est pas moins bonne (avant : « Image illisible »)
            self.assertIn('1200 × 900', report)
            broken = os.path.join(tmp, 'abimee.png')
            with open(broken, 'wb') as fh:
                fh.write(b'pas une image')
            ok, report = E.verify_export(broken)
            self.assertFalse(ok)                         # un fichier abîmé reste signalé
            self.assertIn('illisible', report)


if __name__ == '__main__':
    unittest.main()
