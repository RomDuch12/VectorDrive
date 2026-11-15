"""Round 230 (demandes du 20/10) : C / H / V alignent les autres objets sur
le PREMIER sélectionné (qui ne bouge pas) ; Ctrl+S refuse d'écraser un
fichier modifié par un tiers ; onglets de dessins dans la rangée des onglets
du ruban ; modèles FAO en dossiers gardent leur arborescence ; cote : Tab
change le type, clic droit quitte le mode."""
import os
import pathlib
import tempfile
import time
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QKeyEvent, QMouseEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox

from vectordrive.core import geom
from vectordrive.core.document import Shape

app = QApplication.instance() or QApplication([])


def rect(x, y, w, h):
    return Shape(path=geom.Path([geom.rect(x, y, w, h)]), tool=0)


class TestAlignToFirst(unittest.TestCase):
    def test_center_h_v_relative_to_first(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        d = w.canvas.doc
        a, b, c = rect(0, 0, 10, 10), rect(50, 30, 4, 4), rect(80, 80, 20, 2)
        for s in (a, b, c):
            d.add(s)
        box = lambda it: next(x for x in d.iter_leaves() if x.id == it.id).bbox()   # objets remplacés en bougeant
        w.canvas.select([a, b, c])
        w.align('center')                                   # C : les autres au centre du 1er
        self.assertEqual(box(a), (0, 0, 10, 10))            # la référence ne bouge pas
        self.assertEqual(box(b), (3, 3, 7, 7))
        self.assertEqual(box(c), (-5, 4, 15, 6))
        self.assertEqual(len(w.canvas.selection), 3)        # référence et objets déplacés resélectionnés
        b2 = rect(50, 30, 4, 4)
        d.add(b2)
        sel = lambda *its: w.canvas.select([next(x for x in d.iter_leaves() if x.id == it.id) for it in its])
        sel(a, b2)
        w.align('vcenter')                                  # H : même centre Y que le 1er
        self.assertEqual(box(b2), (50, 3, 54, 7))
        sel(a, b2)
        w.align('hcenter')                                  # V : même centre X que le 1er
        self.assertEqual(box(b2), (3, 3, 7, 7))
        self.assertEqual(box(a), (0, 0, 10, 10))
        self.assertEqual(len(w.canvas.selection), 2)
        w.modified = False
        w.close()


class TestSaveGuard(unittest.TestCase):
    def test_refuses_to_overwrite_a_file_changed_elsewhere(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        f = pathlib.Path(tempfile.mkdtemp()) / 'plaque.vdz'
        w.canvas.doc.add(rect(0, 0, 10, 10))
        w.path = str(f)
        self.assertTrue(w._write(str(f)))
        self.assertFalse(w.changed_on_disk(str(f)))
        time.sleep(0.02)
        f.write_bytes(f.read_bytes() + b' ')                # modifié par un autre poste
        self.assertTrue(w.changed_on_disk(str(f)))
        asked = []

        def fake_exec(box):
            asked.append(box.windowTitle())
            box.clickedButton = lambda: None                # Annuler
            return 0
        with mock.patch.object(QMessageBox, 'exec', fake_exec):
            w.save()
        self.assertEqual(len(asked), 1)
        self.assertEqual(f.stat().st_size, f.stat().st_size)    # rien écrit
        self.assertTrue(w.changed_on_disk(str(f)))
        w._write(str(f))                                     # écriture explicite : nouvel état retenu
        self.assertFalse(w.changed_on_disk(str(f)))
        w2 = MainWindow()
        self.assertTrue(w2.open_path(str(f)))
        self.assertFalse(w2.changed_on_disk(str(f)))        # lu : état retenu
        w.modified = w2.modified = False
        w.close()
        w2.close()


class TestLayout(unittest.TestCase):
    def test_doc_tabs_in_ribbon_row(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        w.resize(1400, 800)
        w.show()
        QTest.qWait(20)
        r = w.ribbon
        corner = r.cornerWidget(Qt.Corner.TopRightCorner)
        self.assertIs(w.doc_bar.parentWidget(), corner)                       # entre FAO et Options
        lay = corner.layout()
        self.assertLess(lay.indexOf(w.doc_bar), lay.indexOf(r.right_bar))
        self.assertTrue(w.doc_bar.isVisible())
        self.assertLess(w.doc_bar.mapToGlobal(w.doc_bar.rect().topLeft()).x(),
                        r.right_bar.mapToGlobal(r.right_bar.rect().topLeft()).x())
        holder = w.menuWidget()
        self.assertEqual(holder.layout().count(), 1)        # plus de rangée d'onglets au-dessus du ruban
        w.canvas.doc.add(rect(0, 0, 5, 5))                  # l'onglet n'est plus vide : le suivant s'ajoute
        w.new_document()
        self.assertEqual(w.doc_bar.tabs.count(), 2)
        w.modified = False
        w.close()


class TestTemplateTree(unittest.TestCase):
    def test_folders_kept(self):
        from vectordrive.cam import templates as TPL
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        tpl = {'format': 'vectordrive-modele-fao', 'version': 1, 'name': 'Alu / Plaques / Détour 2mm',
               'description': 'essai', 'tools': [], 'preset': 'decoupe', 'dossier': 'Alu / Plaques',
               'operations': [{'kind': 'contour', 'depth': 2.0}], 'post': '', 'machine': ''}
        with mock.patch.object(TPL, 'all_templates', return_value={tpl['name']: ('utilisateur', tpl)}):
            w.cam_palette.refresh()
        tree = w.cam_palette.tree
        top = tree.topLevelItem(1)                                           # après « Parcours type » (round 1036)
        self.assertEqual(top.text(0), 'Mes modèles')
        alu = top.child(0)
        self.assertEqual(alu.text(0), '📁 Alu')
        plaques = alu.child(0)
        self.assertEqual(plaques.text(0), '📁 Plaques')
        leaf = plaques.child(0)
        self.assertEqual(leaf.text(0), '📄 Détour 2mm')
        from vectordrive.ui.cam_palette import ROLE_KIND, ROLE_TPL
        self.assertEqual((leaf.data(0, ROLE_KIND), leaf.data(0, ROLE_TPL)), ('decoupe', tpl['name']))
        texts = []                                                           # plus sous le type de parcours

        def walk(it):
            texts.append(it.text(0))
            for i in range(it.childCount()):
                walk(it.child(i))
        walk(tree.topLevelItem(0))                                           # « Parcours type » (round 1036)
        self.assertGreater(len(texts), 5)
        self.assertFalse(any(t.startswith('📄 Détour 2mm') for t in texts))
        w.modified = False
        w.close()


class TestDimensionMode(unittest.TestCase):
    def test_tab_cycles_and_right_click_exits(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        w.resize(1000, 700)
        w.show()
        QTest.qWait(20)
        w.set_tool('dim')
        t = w.canvas.tool_obj
        self.assertEqual(t.mode, 'libre')
        tab = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Tab, Qt.KeyboardModifier.NoModifier)
        app.sendEvent(w.canvas, tab)
        self.assertEqual(t.mode, 'horizontale')
        t.pts = [(0.0, 0.0)]
        self.assertEqual(t._second((10.0, 7.0)), (10.0, 0.0))
        app.sendEvent(w.canvas, QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Tab, Qt.KeyboardModifier.NoModifier))
        self.assertEqual(t.mode, 'verticale')
        self.assertEqual(t._second((10.0, 7.0)), (0.0, 7.0))
        self.assertIs(w.canvas.tool_obj, t)                   # Tab n'a pas changé de mode d'outil
        pos = QPointF(300.0, 300.0)
        press = QMouseEvent(QEvent.Type.MouseButtonPress, pos, Qt.MouseButton.RightButton,
                            Qt.MouseButton.RightButton, Qt.KeyboardModifier.NoModifier)
        release = QMouseEvent(QEvent.Type.MouseButtonRelease, pos, Qt.MouseButton.RightButton,
                              Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier)
        app.sendEvent(w.canvas, press)
        app.sendEvent(w.canvas, release)                      # clic droit sans glisser : retour à la sélection
        self.assertEqual(w.canvas.tool, 'select')
        w.modified = False
        w.close()


if __name__ == '__main__':
    unittest.main()
