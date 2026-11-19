"""Round 1088 (demande du 18/11 soir) : « Assistant : permettre copier coller du texte, colorer différemment les
provenances texte et valeurs de textes, un assistant séparé par onglet ». Aucun appel réel : un client simulé."""
import os
import tempfile
import unittest
import weakref
from types import SimpleNamespace as NS

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1088.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'
os.environ['VECTORDRIVE_KEYS_MEMORY'] = '1'

from PySide6.QtCore import QEvent, Qt  # noqa: E402
from PySide6.QtGui import QKeyEvent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])


class FakeStream:
    def __init__(self, msg, chunks):
        self.msg, self.chunks = msg, chunks

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def __iter__(self):
        for c in self.chunks:
            yield NS(type='text', text=c)

    def get_final_message(self):
        return self.msg


class FakeAnthropic:
    def __init__(self, turns):
        self.turns = list(turns)
        self.messages = self

    def stream(self, **kw):
        content, stop = self.turns.pop(0)
        return FakeStream(NS(content=content, stop_reason=stop), [b.text for b in content if b.type == 'text'])


def override(widget, key, mods=Qt.KeyboardModifier.ControlModifier) -> bool:
    ev = QKeyEvent(QEvent.Type.ShortcutOverride, key, mods)
    ev.ignore()
    QApplication.sendEvent(widget, ev)
    return ev.isAccepted()


class Assistant(unittest.TestCase):

    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.w.resize(1200, 800)
        self.w.show()
        app.processEvents()
        self.addCleanup(self.close)
        self.p = self.w.show_assistant_panel()

    def close(self):
        self.p.shutdown()
        for t in self.w.docs:
            t.modified = False
        self.w.modified = False
        self.w.close()
        self.w.deleteLater()
        app.processEvents()

    def mark(self):
        """Le premier onglet n'est plus vierge : un nouveau dessin ouvre un autre onglet."""
        from vectordrive.core import geom
        from vectordrive.core.document import Shape
        self.w.canvas.doc.add(Shape(path=geom.Path([geom.rect(0, 0, 10, 10)]), tool=0))
        self.w.modified = True

    def test_copy_and_paste_go_to_the_text(self):
        p = self.p
        for widget in (p.view, p.input):
            self.assertTrue(override(widget, Qt.Key.Key_C), 'avant : Ctrl+C allait au dessin')
            self.assertTrue(override(widget, Qt.Key.Key_A))
            self.assertFalse(override(widget, Qt.Key.Key_N))                # les autres : à la fenêtre
        self.assertTrue(override(p.input, Qt.Key.Key_V))
        self.assertFalse(override(p.view, Qt.Key.Key_V))                   # rien à coller dans la discussion
        self.assertFalse(override(p.view, Qt.Key.Key_Z))                   # la discussion : Ctrl+Z reste au dessin
        self.assertTrue(override(p.input, Qt.Key.Key_Z))                   # la demande : à son texte

    def test_values_stand_out(self):
        from vectordrive.ui import assistant_panel as AP
        got = AP.highlight('Plaque de 120 × 40 mm, texte « BUREAU », angle 15°, remplissage 50 %.')
        for part in ('120', '40 mm', '« BUREAU »', '15°', '50 %'):
            self.assertIn('<span style="color:{0}">{1}</span>'.format(AP.C_VALUE, part.replace('«', '«')), got)
        self.assertNotIn('color:', AP.highlight('Rien à signaler'))

    def test_the_colours_of_a_conversation(self):
        from vectordrive.ui import assistant_panel as AP
        p = self.p
        p.provider.setCurrentIndex(p.provider.findData('anthropic'))
        fake = FakeAnthropic([([NS(type='text', text='Rectangle de 40 × 20 mm.')], 'end_turn')])
        p.client_for = lambda _p: fake
        self.assertTrue(p.send('Un rectangle'))
        self.assertTrue(p.wait(20))
        doc = p.view.toHtml().lower()
        for colour in (AP.C_USER, AP.C_BOT, AP.C_VALUE):
            self.assertIn(colour, doc, 'avant : tout de la même couleur')
        text = p.view.toPlainText()
        self.assertIn('Un rectangle', text)
        self.assertIn('Rectangle de 40 × 20 mm.', text.replace('\xa0', ' '))

    def test_one_assistant_per_tab(self):
        w, p = self.w, self.p
        self.mark()
        first = w.docs[w.doc_index]
        p._line('dans le premier onglet')
        v1 = p.view
        w.new_document()
        app.processEvents()
        self.assertIsNot(w.docs[w.doc_index], first)
        self.assertIsNot(p.view, v1, 'avant : la même discussion pour tous les onglets')
        self.assertEqual(p.view.toPlainText(), '')
        w.switch_tab(w.docs.index(first))
        app.processEvents()
        self.assertIs(p.view, v1)
        self.assertIn('dans le premier onglet', p.view.toPlainText())

    def test_a_replaced_start_tab_keeps_its_conversation(self):
        w, p = self.w, self.p
        p._line('dans l’onglet de départ')
        v, holder = p.view, p._tab
        w.new_document()                                                     # l'onglet vierge, remplacé sur place
        app.processEvents()
        self.assertIs(p.view, v)
        self.assertIn('dans l’onglet de départ', p.view.toPlainText())
        self.assertEqual(p._runner(holder)(lambda: 'fait'), 'fait')         # ses outils agissent sur le nouveau

    def test_tools_stay_on_their_tab(self):
        from vectordrive.agent.protocol import ToolError
        w, p = self.w, self.p
        self.mark()
        first = w.docs[w.doc_index]
        run = p._runner([weakref.ref(first)])
        self.assertEqual(run(lambda: 'fait'), 'fait')
        w.new_document()
        app.processEvents()
        with self.assertRaises(ToolError):
            run(lambda: 'fait')
        w.switch_tab(w.docs.index(first))
        self.assertEqual(run(lambda: 'fait'), 'fait')


if __name__ == '__main__':
    unittest.main()
