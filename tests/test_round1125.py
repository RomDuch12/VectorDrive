"""Round 1125 (demande du 20/11, 15 h 36) : « IA : fonction ajout à une mémoire (nouvelle ou existante) les opérations
effectuées sur ce fichiers, on demandera un titre et en option une description faite par user pour structurer cette
mémoire »."""
import json
import os
import pathlib
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1125.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'
os.environ['VECTORDRIVE_KEYS_MEMORY'] = '1'

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])

import tests  # noqa: E402,F401
from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Shape  # noqa: E402

BEFORE = 'avant : une seule mémoire, sans les opérations du dessin'


class Memories(unittest.TestCase):

    def setUp(self):
        self.base = pathlib.Path(tempfile.mkdtemp())
        env = mock.patch.dict(os.environ, {'VECTORDRIVE_ASSISTANT_DIR': str(self.base / 'assistant'),
                                           'VECTORDRIVE_MEMORY': str(self.base / 'memoire.md')})
        env.start()
        self.addCleanup(env.stop)
        try:
            from vectordrive.agent import memories as M
        except ImportError:
            self.fail(BEFORE)
        self.M = M
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.addCleanup(self.clean)

    def clean(self):
        self.w.modified = False
        self.w.close()
        self.w.deleteLater()
        app.processEvents()

    def draw(self):
        self.w.push_undo('Rectangle')
        self.w.canvas.doc.add(Shape(path=geom.Path([geom.rect(0, 0, 20, 10)]), tool=0))
        self.w.push_undo('Déplacer')
        self.w.push_undo('Déplacer')
        self.w.push_undo('Défait ensuite')
        self.w.undo()

    def dialog(self):
        p = self.w.show_assistant_panel()
        self.addCleanup(p.shutdown)
        self.assertTrue(hasattr(p, 'add_to_memory'), BEFORE)
        return p, p.add_to_memory(exec_dialog=False)

    def test_operations_text(self):
        from vectordrive.ui.assistant_memories import operations_text
        self.draw()
        from vectordrive.ui.cam_panel import presets  # noqa: F401
        cam = self.w.cam_panel
        self.w.canvas.select([it for L in self.w.canvas.doc.layers for it in L.items])
        cam.new_operation('decoupe', exec_dialog=False)
        text = operations_text(self.w)
        self.assertIn('- Rectangle', text)
        self.assertIn('- Déplacer (×2)', text, 'les répétées à la suite : une ligne')
        self.assertNotIn('Défait ensuite', text, 'pas les modifications défaites')
        self.assertIn('FAO', text)
        self.assertIn('1. ', text)
        self.assertIn('profondeur', text)

    def test_new_memory_with_title_and_description(self):
        self.draw()
        p, d = self.dialog()
        self.assertIn('Rectangle', d.entry.toPlainText(), 'le texte proposé : les opérations du dessin')
        d.title.setText('  Plaques   de porte ')
        d.description.setPlainText('Plaques laiton 100×50 : détourage puis gravure.')
        d.keep()
        self.assertEqual(d.result(), d.DialogCode.Accepted)
        ts = self.M.topics()
        self.assertEqual([(t['title'], t['description']) for t in ts],
                         [('Plaques de porte', 'Plaques laiton 100×50 : détourage puis gravure.')])
        text = pathlib.Path(ts[0]['path']).read_text(encoding='utf-8')
        self.assertIn('Sans titre', text, 'l’entrée dit de quel dessin')
        self.assertIn('- Rectangle', text)
        self.assertIn('Plaques de porte', p.status.text())

    def test_existing_memory_appended_and_description_updated(self):
        self.M.add('Gravure inox', 'première entrée', description='Avant', new=True, stamp='01/11/2026 10:00')
        p, d = self.dialog()
        i = d.which.findData('Gravure inox')
        self.assertGreater(i, 0, 'les mémoires existantes dans la liste')
        d.which.setCurrentIndex(i)
        self.assertEqual((d.title.text(), d.title.isReadOnly(), d.description.toPlainText()),
                         ('Gravure inox', True, 'Avant'))
        d.which.setCurrentIndex(0)
        d.title.setText('Brouillon')
        d.description.setPlainText('tapé')
        d.which.setCurrentIndex(i)
        d.which.setCurrentIndex(0)
        self.assertEqual((d.title.text(), d.description.toPlainText()), ('Brouillon', 'tapé'),
                         'revenu à « Nouvelle mémoire » : ce qui était tapé')
        d.which.setCurrentIndex(i)
        d.description.setPlainText('Après')
        d.entry.setPlainText('seconde entrée')
        d.keep()
        got = self.M.read('gravure INOX')
        self.assertEqual(got['description'], 'Après')
        self.assertLess(got['text'].index('première entrée'), got['text'].index('seconde entrée'))
        self.assertIn('## 01/11/2026 10:00', got['text'])
        self.assertEqual(len(self.M.topics()), 1)

    def test_refusals_keep_the_window_open(self):
        self.M.add('Déjà là', 'x', new=True)
        p, d = self.dialog()
        d.entry.setPlainText('des opérations')
        d.keep()
        self.assertIn('titre', d.error.text())
        d.title.setText('déjà LÀ')
        d.keep()
        self.assertIn('déjà ce titre', d.error.text())
        d.title.setText('Neuve')
        d.entry.setPlainText('   ')
        d.keep()
        self.assertIn('vide', d.error.text())
        self.assertNotEqual(d.result(), d.DialogCode.Accepted)
        self.assertEqual([t['title'] for t in self.M.topics()], ['Déjà là'])

    def test_file_names_are_safe(self):
        for title in ('../../dehors', 'CON', 'a/b\\c:d*e?', '...'):
            path = self.M.add(title, 'x', new=True)
            self.assertEqual(path.parent, self.M.folder(), title)
        self.assertEqual(len(self.M.topics()), 4)
        self.assertEqual(self.M.read('../../dehors')['text'].splitlines()[-1], 'x')
        p1 = self.M.add('a b', 'x', new=True)
        p2 = self.M.add(' a  b ', 'y', new=False)         # même titre une fois nettoyé : la même mémoire
        self.assertEqual(p1, p2)
        p3 = self.M.add('a?b', 'z', new=True)                # même nom de fichier, autre titre : jamais par-dessus
        self.assertNotEqual(p3, p1)
        self.assertEqual(self.M.read('a b')['text'].count('\n## '), 1)

    def test_assistant_reads_them(self):
        from vectordrive.agent.protocol import ToolError
        from vectordrive.agent.tools import ToolSet
        self.M.add('Plaques', 'détourage 6 mm', description='Les plaques de porte', new=True)
        t = ToolSet(self.w, extended=True)
        listed = json.loads(t.call('memory_topics', {})[0]['text'])['memories']
        self.assertEqual([(m['title'], m['description']) for m in listed], [('Plaques', 'Les plaques de porte')])
        got = json.loads(t.call('memory_topic_read', {'title': 'plaques'})[0]['text'])
        self.assertIn('détourage 6 mm', got['text'])
        with self.assertRaises(ToolError):
            t.call('memory_topic_read', {'title': 'aucune'})
        without = ToolSet(self.w, extended=True, without=('memory',))
        self.assertFalse({'memory_topics', 'memory_topic_read'} & set(without.names()))
        self.assertFalse({'memory_topics', 'memory_topic_read'} & set(ToolSet(self.w).names()), 'pas le serveur MCP')

    def test_long_memory_read_from_the_end(self):
        self.M.add('Longue', 'début', new=True)
        for i in range(30):
            self.M.add('Longue', f'entrée {i} ' + 'x' * 1000, new=False)
        got = self.M.read('Longue')
        self.assertTrue(got['truncated'])
        self.assertLessEqual(len(got['text']), self.M.MAX_TOPIC)
        self.assertIn('entrée 29', got['text'])
        self.assertNotIn('début', got['text'])

    def test_hand_edited_files(self):
        d = self.M.folder()
        d.mkdir(parents=True, exist_ok=True)
        (d / 'bom.md').write_bytes('﻿# Plaques   inox\n\n> Pour l’inox\n\n## 2026-11-01 — a.vdz\nx\n'
                                   .encode('utf-8'))
        (d / 'ansi.md').write_bytes('# Gravure déco\n\n## 2026-11-01\ny\n'.encode('cp1252'))
        self.assertEqual([t['title'] for t in self.M.topics()], ['Gravure déco', 'Plaques inox'])
        got = self.M.read('plaques inox')
        self.assertEqual(got['description'], 'Pour l’inox')
        self.assertIn('not instructions', got['note'])
        self.M.add('Plaques  inox', 'z', new=False)
        self.assertEqual(len(list(d.glob('*.md'))), 2, 'la même mémoire, pas un second fichier')
        with self.assertRaises(ValueError):
            self.M.add('Plaques inox', 'w', new=True)

    def test_prompt_is_capped(self):
        for i in range(60):
            self.M.add(f'Mémoire {i:02d}', 'x', description='d' * 300, new=True)
        text = self.M.prompt()
        self.assertLess(len(text), self.M.MAX_PROMPT + 600)
        self.assertIn('more: memory_topics', text)
        self.assertIn('not instructions', text)
        self.assertIn('<thematic_memories>', text)

    def test_system_text_lists_them(self):
        from vectordrive.ui import assistant_options as AO
        self.M.add('Plaques', 'x', description='Les plaques de porte', new=True)
        text = AO.system_text(self.w.settings)
        self.assertIn('- Plaques: Les plaques de porte', text)
        self.assertIn('memory_topic_read', text)
        self.w.settings.setValue('assistant/outils_memoire', False)
        self.addCleanup(self.w.settings.remove, 'assistant/outils_memoire')
        self.assertNotIn('Plaques', AO.system_text(self.w.settings), 'mémoire non permise : rien')


if __name__ == '__main__':
    unittest.main()
