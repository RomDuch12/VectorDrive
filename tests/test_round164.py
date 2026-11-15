"""Round 164 : journal des exports (TauDrive)."""
import datetime
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.cam import journal as JR, model


def setup():
    s = model.CamSetup()
    t = model.CamTool(name='Fraise Ø2', diameter=2, number=3)
    s.tools = [t]
    s.operations = [model.Operation(name='Détourage', kind='contour', tool_id=t.id, depth=1.0, feed=800)]
    return s


class TestJournal(unittest.TestCase):
    def test_state_and_differences(self):
        s = setup()
        a = JR.state(s, (), 'datron')
        self.assertEqual(a['operations']['1. Détourage']['outil'], 'T3')
        self.assertEqual(a['operations']['1. Détourage']['avance'], '800')
        self.assertEqual(JR.differences(None, a), [])
        s.operations[0].feed = 1000
        s.tools[0].number = 4
        s.operations.append(model.Operation(name='Gravure', kind='gravure', tool_id=s.tools[0].id))
        b = JR.state(s, (), 'gcode')
        diff = JR.differences(a, b)
        self.assertIn('post-processeur : datron -> gcode', diff)
        self.assertIn('operation ajoutee : 2. Gravure', diff)
        self.assertIn('1. Détourage - avance : 800 -> 1000', diff)
        self.assertIn('1. Détourage - outil : T3 -> T4', diff)

    def test_render_ascii(self):
        st = JR.state(setup(), (), 'datron')
        text = JR.render(st, ['1. Détourage - avance : 800 -> 1000'], rank=2, folder='C:\\Pièces',
                         files=['programme.simpl'], when=datetime.datetime(2026, 10, 18, 15, 0, 0))
        text.encode('ascii')                                                    # ASCII seulement
        self.assertIn('Export n2   2026-10-18 15:00:00', text)
        self.assertIn('MODIFICATIONS', text)
        self.assertIn('Detourage', text)
        self.assertIn('aucun reglage modifie', JR.render(st, [], rank=3, folder='x', files=[]))

    def test_append_and_rank(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(JR.next_rank(tmp, 'prog'), 1)
            st = JR.state(setup(), (), 'datron')
            p = JR.append(tmp, 'prog', JR.render(st, [], rank=1, folder=tmp, files=['prog.simpl']))
            JR.append(tmp, 'prog', JR.render(st, [], rank=2, folder=tmp, files=['prog.simpl']))
            self.assertEqual(p.name, 'prog-journal.txt')
            self.assertEqual(JR.next_rank(tmp, 'prog'), 3)
            self.assertIn(b'\r\n', p.read_bytes())
            self.assertIsNone(JR.append(os.path.join(tmp, 'absent', 'dossier'), 'prog', 'x'))   # sans lever


class TestPanel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_write_journal(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            panel = w.cam_panel
            model.store(w.canvas.doc, setup())
            with tempfile.TemporaryDirectory() as tmp:
                out = pathlib.Path(tmp) / 'piece.simpl'
                w.settings.setValue('fao/journal', False)
                self.assertIsNone(panel.write_journal(out, 'datron', [], ['piece.simpl']))
                w.settings.setValue('fao/journal', True)
                p1 = panel.write_journal(out, 'datron', [], ['piece.simpl'])
                s = panel.setup()
                s.operations[0].depth = 1.5
                model.store(w.canvas.doc, s)
                panel.write_journal(out, 'datron', [], ['piece.simpl'])
                text = p1.read_text(encoding='ascii')
                self.assertIn('Export n2', text)
                self.assertIn('1. Detourage - profondeur : 1 -> 1.5', text)
            w.settings.setValue('fao/journal', False)
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
