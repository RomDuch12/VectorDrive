"""Round 327 : éditeur de bitmap (TypeEdit) — l'image écrite en PNG pour
l'éditeur du poste, reprise à l'enregistrement (même place)."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import QBuffer, QIODevice
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

from vectordrive.core.document import Image
from vectordrive.core.geom import Affine
from vectordrive.ui import shortcuts as SC

app = QApplication.instance() or QApplication([])


def png(color) -> bytes:
    q = QImage(8, 4, QImage.Format.Format_RGB32)
    q.fill(QColor(color))
    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    q.save(buf, 'PNG')
    return bytes(buf.data())


class TestBitmap(unittest.TestCase):
    def test_round_trip(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            im = Image(data=png('white'), fmt='png', matrix=Affine(40, 0, 0, -20, 5, 25))
            w.canvas.doc.add(im)
            w.canvas.select([im])
            path = w.image_edit(launch=False)
            self.assertTrue(os.path.exists(path))
            self.assertFalse(QImage(path).isNull())
            with open(path, 'wb') as f:                              # « enregistré dans l'éditeur »
                f.write(png('black'))
            w._image_changed(path)
            new = w.canvas.doc.layers[0].items[0]
            self.assertEqual(new.data, png('black'))
            self.assertEqual(new.matrix, im.matrix)                   # même place
            self.assertEqual(new.id, im.id)
            w.undo()
            self.assertEqual(w.canvas.doc.layers[0].items[0].data, png('white'))
            self.assertEqual(SC.TE_ACTIONS['ID_BITMAPEDITOR'], 'image_edit')
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
