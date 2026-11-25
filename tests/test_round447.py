"""Round 447 : S éclate pas à pas (groupes, pièces, contours) ; bibliothèque (B) parcourue
dossier par dossier et gérée (dossiers, renommer, déplacer, corbeille, importer) ; clic droit sur
un onglet de document (nouveau, dupliquer, recharger, enregistrer, fermer)."""
import os
import pathlib
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))
LIB = tempfile.mkdtemp()                         # bibliothèque d'essai (donnée au panneau, jamais la vraie)

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox

from vectordrive.core import geom
from vectordrive.core.document import Group, Shape

app = QApplication.instance() or QApplication([])


class Base(unittest.TestCase):
    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()

    def tearDown(self):
        for t in self.w.docs:
            t.modified = False
        self.w.modified = False
        self.w.close()


class TestExplode(Base):
    def test_steps(self):
        from vectordrive.ui.shortcuts import TE_ACTIONS
        self.assertEqual(TE_ACTIONS['ID_MANIPULER_ZONE_ECLATER'], 'explode_step')
        w = self.w
        two = Shape(path=geom.Path([geom.rect(0, 0, 10, 10), geom.rect(3, 3, 4, 4),        # pièce trouée
                                    geom.rect(20, 0, 10, 10)]))                            # et une autre
        g = Group(children=[two])
        w.canvas.doc.add(Group(children=[g]))
        w.canvas.select([w.canvas.doc.layers[0].items[-1]])
        self.assertEqual(w.explode_step(), 'groupes')
        self.assertEqual(w.explode_step(), 'groupes')
        self.assertEqual(w.explode_step(), 'pieces')
        self.assertEqual(sorted(len(s.path.contours) for s in w.canvas.selection), [1, 2])
        self.assertEqual(w.explode_step(), 'contours')
        self.assertEqual([len(s.path.contours) for s in w.canvas.selection], [1, 1, 1])
        self.assertEqual(w.explode_step(), '')


class TestLibrary(Base):
    def test_navigation_and_management(self):
        lib = pathlib.Path(LIB)
        (lib / 'Plaques' / 'Laiton').mkdir(parents=True, exist_ok=True)
        (lib / 'Plaques' / 'a.dxf').write_text('0\nEOF\n', encoding='ascii')
        (lib / 'Plaques' / 'Laiton' / 'b.dxf').write_text('0\nEOF\n', encoding='ascii')
        p = self.w.symbols
        p.roots = [lib]
        p._fill_tree()
        p.deep.setChecked(False)
        p.show_folder(lib / 'Plaques')
        rows = [(p.list.item(i).text(), p.list.item(i).data(Qt.ItemDataRole.UserRole + 1))
                for i in range(p.list.count())]
        self.assertEqual(rows, [('..', 'up'), ('Laiton', 'dir'), ('a', None)])     # l'arborescence, pas tout à plat
        self.assertIn('Plaques', p.where.text())
        p._activated(p.list.item(1))                                                # entrer dans Laiton
        self.assertEqual(p._folder, lib / 'Plaques' / 'Laiton')
        p.go_up()
        self.assertEqual(p._folder, lib / 'Plaques')
        d = p.new_folder(lib / 'Plaques', 'Inox')
        self.assertTrue(d.is_dir())
        self.assertEqual(p.place_files([str(lib / 'Plaques' / 'a.dxf')], str(d)), 1)
        self.assertTrue((d / 'a.dxf').is_file())
        r = p.rename(d / 'a.dxf', 'plaque')
        self.assertEqual(r.name, 'plaque.dxf')
        outside = pathlib.Path(tempfile.mkdtemp()) / 'c.dxf'
        outside.write_text('0\nEOF\n', encoding='ascii')
        self.assertEqual(p.import_files(d, [str(outside)]), 1)
        self.assertTrue(outside.exists())                                           # copié, pas déplacé
        with mock.patch('vectordrive.ui.symbols.to_trash', side_effect=lambda q: q.unlink() or True) as tt:
            self.assertEqual(p.delete([d / 'c.dxf'], confirm=False), 1)
            tt.assert_called_once()
        self.assertEqual(p.delete([lib], confirm=False), 0)                          # la bibliothèque elle-même : non
        m = p.menu(p.list, None, exec_menu=False)
        texts = [a.text() for a in m.actions() if a.text()]
        for t in ('Nouveau dossier…', 'Importer des fichiers ici…', 'Actualiser'):
            self.assertIn(t, texts)


class TestDocTabMenu(Base):
    def test_menu(self):
        w = self.w
        w.canvas.doc.add(Shape(path=geom.Path([geom.rect(0, 0, 10, 10)])))
        m = w.doc_tab_menu(w.doc_index, exec_menu=False)
        texts = [a.text() for a in m.actions() if a.text()]
        self.assertEqual(texts, ['Nouveau', 'Dupliquer', 'Renommer…', 'Épingler', 'Recharger depuis le disque',
                                 'Ouvrir le dossier contenant', 'Enregistrer',
                                 'Enregistrer sous…', 'Fermer', 'Rouvrir un onglet fermé'])
        n = len(w.docs)
        w.duplicate_tab()
        self.assertEqual(len(w.docs), n + 1)
        self.assertEqual(len(list(w.canvas.doc.iter_leaves())), 1)
        p = pathlib.Path(tempfile.mkdtemp()) / 'r.vdz'
        from vectordrive.io import registry
        registry.save_document(w.canvas.doc, str(p))
        self.assertTrue(w.open_path(str(p)))
        w.canvas.doc.add(Shape(path=geom.Path([geom.rect(20, 0, 10, 10)])))
        w.modified = True
        with mock.patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.Yes):
            self.assertTrue(w.reload_tab())
        self.assertEqual(len(list(w.canvas.doc.iter_leaves())), 1)


if __name__ == '__main__':
    unittest.main()
