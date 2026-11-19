"""Round 1090 (demande du 19/11 matin) : « poincon et couteau : quelle difference ? supprimer popup info ; Assistant,
le texte affiché (console assistant-user) doit pouvoir etre copié, car si je colle j'ai du code pas le texte que je
souhaite copier »."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1090.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'
os.environ['VECTORDRIVE_KEYS_MEMORY'] = '1'

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])


class Popups(unittest.TestCase):

    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.addCleanup(self.close)
        self.info = mock.patch('vectordrive.ui.main_window.QMessageBox.information')
        self.said = self.info.start()
        self.addCleanup(self.info.stop)

    def close(self):
        self.w.modified = False
        self.w.close()
        self.w.deleteLater()
        app.processEvents()

    def line(self):
        from vectordrive.core import geom
        from vectordrive.core.document import Shape
        s = Shape(path=geom.Path([geom.polyline([(0, 0), (60, 0)])]), tool=0)
        self.w.canvas.doc.add(s)
        return s

    def test_no_window_but_the_status_bar(self):
        w = self.w
        cases = (('punch_command', 'Poinçonner', []), ('knife_command', 'Couteau', []),
                 ('punch_items', 'Poinçonner', [self.line()]), ('knife', 'Couteau', []))
        for name, title, sel in cases:
            w.canvas.select(sel)
            w.statusBar().clearMessage()
            getattr(w, name)()
            self.assertFalse(self.said.called, f'avant : une fenêtre d’information ({name})')
            self.assertTrue(w.statusBar().currentMessage().startswith(title + ' : '), name)

    def test_the_message_survives_the_ribbon_status_tip(self):
        w = self.w
        w.canvas.select([])
        w.punch_command()
        said = w.statusBar().currentMessage()
        w.statusBar().clearMessage()                     # la souris quitte le bouton du ruban : info-bulle d'état vide
        app.processEvents()
        self.assertEqual(w.statusBar().currentMessage(), said, 'avant : effacé aussitôt')


class ChatCopy(unittest.TestCase):

    def test_the_conversation_is_copied_as_plain_text(self):
        from PySide6.QtTest import QTest
        from vectordrive.ui.assistant_panel import AssistantPanel, ChatView
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            p = w.show_assistant_panel()
            self.assertIsInstance(p, AssistantPanel)
            self.assertIsInstance(p.view, ChatView)
            p._line('Une plaque de 120 × 40 mm, texte "BUREAU".')
            p._line('Deuxième ligne.')
            p._line('<b>Vous :</b> trois<br>lignes ici', raw=True)            # un saut de ligne, une insécable
            p.view.setFocus()
            p.view.selectAll()
            QApplication.clipboard().clear()
            QTest.keyClick(p.view, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
            md = QApplication.clipboard().mimeData()
            self.assertEqual(md.formats(), ['text/plain'], 'avant : du HTML, du Markdown et de l’OpenDocument en plus')
            got = md.text()
            self.assertIn('Une plaque de 120 × 40 mm, texte "BUREAU".', got)
            self.assertIn('\nDeuxième ligne.', got)
            self.assertIn('Vous : trois\nlignes ici', got)
            for bad in ('\u2029', '\u2028', '\u00a0', '<'):
                self.assertNotIn(bad, got)
            p.input.setPlainText('Ma demande')                                   # la demande aussi
            p.input.selectAll()
            p.input.setFocus()
            QApplication.clipboard().clear()
            QTest.keyClick(p.input, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
            md = QApplication.clipboard().mimeData()
            self.assertEqual((md.formats(), md.text()), (['text/plain'], 'Ma demande'))
            p.shutdown()
        finally:
            w.modified = False
            w.close()
            w.deleteLater()
            app.processEvents()


if __name__ == '__main__':
    unittest.main()
