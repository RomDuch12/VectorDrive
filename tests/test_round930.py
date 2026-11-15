"""Round 930 : Bibliothèque, ajouter la sélection — un bouton en haut du panneau (seul le nom est demandé, le symbole va
dans le dossier affiché, un nom pris devient « nom (2) », le fichier ajouté est choisi dans la liste) ; clic droit sur
un dossier : « Ajouter la sélection du dessin ici… »."""
import os
import pathlib
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r930.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication, QInputDialog

app = QApplication.instance() or QApplication([])


class AddSelection(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from vectordrive.ui.main_window import MainWindow
        cls.w = MainWindow()

    @classmethod
    def tearDownClass(cls):
        cls.w.modified = False
        cls.w.close()

    def setUp(self):
        from vectordrive.core import geom
        from vectordrive.core.document import Shape
        w = self.w
        w.new_document()
        self.folder = pathlib.Path(tempfile.mkdtemp())
        (self.folder / 'Logos').mkdir()
        self.sh = Shape(path=geom.Path([geom.rect(0, 0, 20, 10)]))
        w.canvas.doc.add(self.sh)
        w.canvas.select([self.sh])
        w.symbols.show_folder(self.folder)

    def files(self, folder=None):
        return sorted(p.name for p in (folder or self.folder).glob('*.smb'))

    def test_button_asks_the_name_only(self):
        p = self.w.symbols
        with mock.patch.object(QInputDialog, 'getText', return_value=('Plaque essai', True)) as ask:
            p.add_selection.click()
        ask.assert_called_once()
        self.assertEqual(self.files(), ['Plaque essai.smb'])
        cur = p.list.currentItem()
        self.assertTrue(cur is not None and cur.isSelected())
        self.assertTrue(str(cur.data(0x0100)).endswith('Plaque essai.smb'))     # le fichier ajouté, choisi
        with mock.patch.object(QInputDialog, 'getText', return_value=('Plaque essai', True)):
            p.add_selection.click()                                         # nom pris
        self.assertEqual(self.files(), ['Plaque essai (2).smb', 'Plaque essai.smb'])
        with mock.patch.object(QInputDialog, 'getText', return_value=('Autre', False)):
            p.add_selection.click()                                         # annulé : rien
        self.assertEqual(len(self.files()), 2)

    def test_folder_context_menu(self):
        p = self.w.symbols
        p.list.clearSelection()
        for i in range(p.list.count()):                                     # le dossier « Logos » dans la liste
            it = p.list.item(i)
            if str(it.data(0x0100)).endswith('Logos'):
                it.setSelected(True)
        m = p.menu(p.list, None, exec_menu=False)
        act = next(a for a in m.actions() if a.text() == 'Ajouter la sélection du dessin ici…')
        with mock.patch.object(QInputDialog, 'getText', return_value=('Dans logos', True)):
            act.trigger()
        self.assertEqual(self.files(self.folder / 'Logos'), ['Dans logos.smb'])
        self.assertTrue(any(a.text() == 'Enregistrer la sélection sous…' for a in m.actions()))

    def test_name_proposed_and_nothing_without_selection(self):
        from vectordrive.core.document import Text
        w = self.w
        t = Text(text='Bureau 12\nétage', font='VD Trait', size=5.0)
        w.canvas.doc.add(t)
        w.canvas.select([self.sh, t])
        with mock.patch.object(QInputDialog, 'getText', return_value=('', True)) as ask:
            self.assertIsNone(w.add_selection_to_library(self.folder))
        self.assertEqual(ask.call_args.kwargs.get('text'), 'Bureau 12')    # la première ligne du texte
        self.assertEqual(self.files(), [])                                  # nom vide : rien
        w.canvas.select([])
        with mock.patch.object(QInputDialog, 'getText') as ask:
            self.assertIsNone(w.add_selection_to_library(self.folder))
        ask.assert_not_called()
        self.assertIn('Sélectionnez', w.statusBar().currentMessage())

    def test_favorites_fall_back_to_save_as(self):
        w = self.w
        w.symbols.show_favorites()
        self.assertIsNone(w.symbols.target_folder())
        with mock.patch.object(w, 'save_as_symbol') as save:
            w.symbols.add_selection.click()
        save.assert_called_once()


if __name__ == '__main__':
    unittest.main()
