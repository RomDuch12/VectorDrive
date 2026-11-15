"""Round 861 : informations et comptes rendus d'un parcours (manuel de TE, pages 665 à 672 imprimées)."""
import os
import pathlib
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', os.path.join(tempfile.mkdtemp(), 'session'))
os.environ.setdefault('VECTORDRIVE_NO_TYPEEDIT', '1')

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QColor, QImage, QKeyEvent
from PySide6.QtWidgets import QApplication, QFileDialog, QLabel

from vectordrive.cam import model as M
from vectordrive.cam.model import Move, Toolpath
from vectordrive.core import geom
from vectordrive.core.document import Document, Group, Layer, Plate, Shape
from vectordrive.ui import path_report as PR

app = QApplication.instance() or QApplication([])


def path(*moves, op_id='op'):
    tp = Toolpath(op_id, 't', name='p')
    tp.moves = list(moves)
    return tp


def job():
    doc = Document()
    doc.plate = Plate(width=100.0, height=100.0)
    s = Shape(path=geom.Path([geom.rect(10, 10, 20, 20)]))
    doc.layers = [Layer(name='Vide', items=[Shape(path=geom.Path([geom.rect(50, 50, 5, 5)]), visible=False)]),
                  Layer(name='Tracé', items=[Group(children=[s])])]
    setup = M.setup_of(doc)
    tool = M.CamTool(name='Conique 30', kind='conique', diameter=6.0, tip=0.2, angle=30.0, ref='REF-1', vendor='ACME', number=3,
                     spindle=30000.0, feed=900.0, plunge=250.0)
    setup.tools.append(tool)
    op = M.Operation(kind='poche', tool_id=tool.id, depth=0.4, z_start=-0.1, name='Vidage', items=[s.id])
    setup.operations.append(op)
    M.store(doc, setup)
    return doc, setup, op


class TestNature(unittest.TestCase):

    def test_one_level(self):
        self.assertEqual(PR.nature([path(Move('rapid', 0, 0, 5), Move('feed', 0, 0, -1), Move('feed', 10, 0, -1))]), '2D')

    def test_several_levels(self):
        self.assertEqual(PR.nature([path(Move('feed', 0, 0, -1), Move('feed', 10, 0, -1), Move('feed', 10, 0, -2), Move('feed', 0, 0, -2))]), '2,5D')

    def test_slopes(self):
        self.assertEqual(PR.nature([path(Move('feed', 0, 0, 0), Move('feed', 10, 0, -1), Move('feed', 20, 0, 0))]), '3D')

    def test_a_short_ramp_does_not_count(self):
        self.assertEqual(PR.nature([path(Move('feed', 0, 0, 0), Move('feed', 3, 0, -1), Move('feed', 60, 0, -1))]), '2D')

    def test_a_circle_counts(self):
        circle = Move('arc_ccw', 10, 0, -1, 0, 0)
        self.assertEqual(PR.nature([path(Move('feed', 10, 0, -1), circle)]), '2D')
        self.assertEqual(PR.nature([path(Move('feed', 10, 0, -1), circle, Move('feed', 10, 0, -2), Move('arc_ccw', 10, 0, -2, 0, 0))]), '2,5D')


class TestFacts(unittest.TestCase):

    def setUp(self):
        self.doc, self.setup, self.op = job()
        self.tp = path(Move('rapid', 0, 0, 5), Move('rapid', 10, 0, 5), Move('feed', 10, 0, -1), Move('feed', 20, 0, -1), op_id=self.op.id)

    def test_lengths(self):
        f = PR.facts(self.doc, self.setup, self.op, [self.tp])
        self.assertAlmostEqual(f['rapid'], 10.0)
        self.assertAlmostEqual(f['feed'], 16.0)

    def test_box(self):
        self.assertEqual(PR.facts(self.doc, self.setup, self.op, [self.tp])['box'], (0, 0, -1, 20, 0, 5))

    def test_several_paths(self):
        other = path(Move('rapid', 30, -5, 5), Move('feed', 30, -5, -2))
        f = PR.facts(self.doc, self.setup, self.op, [self.tp, other])
        self.assertEqual(f['box'], (0, -5, -2, 30, 0, 5))

    def test_no_path(self):
        f = PR.facts(self.doc, self.setup, self.op, [])
        self.assertIsNone(f['box'])
        self.assertEqual((f['feed'], f['seconds']), (0.0, 0.0))

    def test_the_duration_is_positive(self):
        self.assertGreater(PR.facts(self.doc, self.setup, self.op, [self.tp])['seconds'], 0.0)

    def test_the_plan_of_a_grouped_object(self):
        self.assertEqual(PR.plan_names(self.doc, self.op), ['Tracé'])


class TestHtml(unittest.TestCase):

    def setUp(self):
        self.doc, self.setup, self.op = job()
        self.tp = path(Move('rapid', 0, 0, 5), Move('feed', 0, 0, -0.5), Move('feed', 20, 0, -0.5), op_id=self.op.id)

    def report(self, **kw):
        return PR.toolpath_html(self.doc, self.setup, self.op, [self.tp], PR.ReportOptions(**kw), file_name='a.vnd')

    def test_everything_by_default(self):
        t = self.report()
        for word in ('a.vnd', 'Vidage', '-0,100 mm', '0,400 mm', 'Poche', '-0,500 mm', '2D', 'Tracé', 'Conique 30', 'REF-1', 'ACME',
                     '30°', '0,200 mm', '6,000 mm', '250 mm/min', '900 mm/min', '30000 tr/min', '25,5 mm'):
            self.assertIn(word, t)

    def test_the_tool_sections(self):
        self.assertNotIn('REF-1', self.report(tool_general=False))
        self.assertIn('6,000 mm', self.report(tool_general=False))
        self.assertNotIn('6,000 mm', self.report(tool_geometry=False))
        self.assertIn('REF-1', self.report(tool_geometry=False))

    def test_the_speed_sections(self):
        self.assertNotIn('900 mm/min', self.report(feeds=False))
        self.assertNotIn('30000 tr/min', self.report(spindle=False))

    def test_the_path_section(self):
        self.assertNotIn('Tracé', self.report(path_general=False))

    def test_the_times(self):
        self.assertNotIn('25,5 mm', self.report(length=False))
        self.assertIn('25,5 mm', self.report(duration=False))

    def test_special_characters(self):
        self.op.name = 'a<b'
        t = self.report()
        self.assertIn('a&lt;b', t)
        self.assertNotIn('a<b', t)

    def test_without_tool(self):
        self.op.tool_id = 'parti'
        t = self.report()
        self.assertNotIn('Conique 30', t)
        self.assertIn('Vidage', t)

    def final(self, **kw):
        return PR.final_html(self.doc, self.setup, [self.op], [self.tp], PR.ReportOptions(**kw), file_name='a.vnd')

    def test_final(self):
        t = self.final()
        for word in ('Compte rendu final', 'a.vnd', 'Vidage', 'Conique 30', '<td>3</td>', '25,5 mm'):
            self.assertIn(word, t)

    def test_the_final_has_the_total_of_every_operation(self):
        op2 = M.Operation(kind='gravure', tool_id=self.op.tool_id, depth=0.1, name='Deux')
        self.setup.operations.append(op2)
        tp2 = path(Move('rapid', 0, 0, 5), Move('feed', 0, 0, -0.1), Move('feed', 10, 0, -0.1), op_id=op2.id)
        t = PR.final_html(self.doc, self.setup, [self.op, op2], [self.tp, tp2], PR.ReportOptions(), file_name='')
        self.assertIn('Deux', t)
        self.assertIn('40,6 mm', t)                     # dans la matière : 5,5 + 20, puis 5,1 + 10

    def test_the_factor(self):
        o = PR.ReportOptions()
        self.assertEqual(o.duration_of(60.0), 60.0)
        o = PR.ReportOptions(use_factor=True, factor=150.0)
        self.assertEqual(o.duration_of(60.0), 90.0)
        self.assertIn('150 %', self.final(use_factor=True, factor=150.0))
        self.assertNotIn('150 %', self.final(factor=150.0))

    def test_the_factor_changes_the_total(self):
        self.tp.moves.append(Move('feed', 20000, 0, -0.5))
        plain = self.final()
        self.assertNotEqual(plain, self.final(use_factor=True, factor=300.0).replace('<p>Facteur : 300 %</p>', ''))

    def test_the_notes(self):
        self.assertNotIn('Notes', self.final())
        t = self.final(notes='ligne 1\nligne <2>')
        self.assertIn('ligne 1<br>ligne &lt;2&gt;', t)
        self.assertNotIn('ligne 1', self.report(notes='ligne 1'))


class TestFiles(unittest.TestCase):

    def test_the_first_free_number(self):
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, 'Pièce.vnd')
            a, b = PR.report_names(src)
            self.assertEqual(os.path.basename(a), 'Pièce_000_ReportByToolpath.pdf')
            self.assertEqual(os.path.basename(b), 'Pièce_000_FinalReport.pdf')
            pathlib.Path(b).write_bytes(b'x')
            a, b = PR.report_names(src)
            self.assertEqual(os.path.basename(a), 'Pièce_001_ReportByToolpath.pdf')
            self.assertEqual(os.path.basename(b), 'Pièce_001_FinalReport.pdf')

    def test_without_a_file(self):
        with tempfile.TemporaryDirectory() as d:
            a, _b = PR.report_names('', d)
            self.assertEqual(os.path.dirname(a), d)
            self.assertEqual(os.path.basename(a), 'Parcours_000_ReportByToolpath.pdf')

    def test_the_pdf(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 'a.pdf')
            PR.write_pdf(p, '<html><body><p>Bonjour</p></body></html>', 'Titre')
            self.assertTrue(pathlib.Path(p).read_bytes().startswith(b'%PDF'))

    def test_the_pdf_with_an_image(self):
        with tempfile.TemporaryDirectory() as d:
            im = QImage(40, 40, QImage.Format.Format_RGB32)
            im.fill(QColor('red'))
            pic = os.path.join(d, 'i.png')
            im.save(pic)
            a, b = os.path.join(d, 'a.pdf'), os.path.join(d, 'b.pdf')
            PR.write_pdf(a, '<html><body><p>x</p></body></html>', 'T')
            PR.write_pdf(b, '<html><body><p>x</p><p><img src="image" width="500"></p></body></html>', 'T', pic)
            self.assertGreater(os.path.getsize(b), os.path.getsize(a))

    def test_a_folder_that_does_not_exist(self):
        with self.assertRaises(OSError):
            PR.write_pdf(os.path.join(tempfile.gettempdir(), 'pas_de_dossier_861', 'a.pdf'), '<html></html>', 'T')


class TestDialogs(unittest.TestCase):

    def test_the_default_options(self):
        d = PR.PathReportDialog(None, 'Titre')
        o = d.options()
        self.assertEqual(o, PR.ReportOptions())
        d.done(0)

    def test_the_factor_field_follows(self):
        d = PR.PathReportDialog(None)
        self.assertFalse(d.factor.isEnabled())
        d.use_factor.setChecked(True)
        self.assertTrue(d.factor.isEnabled())
        d.factor.setValue(120.0)
        o = d.options()
        self.assertTrue(o.use_factor)
        self.assertEqual(o.factor, 120.0)
        d.done(0)

    def test_the_notes_need_the_box(self):
        d = PR.PathReportDialog(None)
        d.notes.setPlainText('note')
        self.assertEqual(d.options().notes, '')
        d.use_notes.setChecked(True)
        self.assertEqual(d.options().notes, 'note')
        d.done(0)

    def test_sections(self):
        d = PR.PathReportDialog(None)
        for box, key in ((d.tool_general, 'tool_general'), (d.tool_geometry, 'tool_geometry'), (d.feeds, 'feeds'), (d.spindle, 'spindle'),
                         (d.path_general, 'path_general'), (d.duration, 'duration'), (d.length, 'length')):
            box.setChecked(False)
            self.assertFalse(getattr(d.options(), key), key)
        d.show_pdf.setChecked(False)
        self.assertFalse(d.options().show_pdf)
        d.done(0)

    def test_the_image_asks_for_a_file(self):
        with tempfile.TemporaryDirectory() as td:
            im = QImage(40, 20, QImage.Format.Format_RGB32)
            im.fill(QColor('blue'))
            pic = os.path.join(td, 'i.png')
            im.save(pic)
            d = PR.PathReportDialog(None)
            with mock.patch.object(QFileDialog, 'getOpenFileName', return_value=(pic, '')):
                d.use_image.setChecked(True)
            self.assertEqual(d.options().image, pic)
            self.assertIsNotNone(d.preview.pixmap())
            d.use_image.setChecked(False)
            self.assertEqual(d.options().image, '')
            d.done(0)

    def test_no_image_chosen_unchecks(self):
        d = PR.PathReportDialog(None)
        with mock.patch.object(QFileDialog, 'getOpenFileName', return_value=('', '')):
            d.use_image.setChecked(True)
        self.assertFalse(d.use_image.isChecked())
        self.assertEqual(d.options().image, '')
        d.done(0)

    def test_a_bad_image_is_refused(self):
        with tempfile.TemporaryDirectory() as td:
            bad = os.path.join(td, 'i.png')
            pathlib.Path(bad).write_bytes(b'rien')
            d = PR.PathReportDialog(None)
            self.assertFalse(d.set_image(bad))
            self.assertEqual(d.image_path, '')
            d.done(0)

    def test_the_information_window(self):
        f = {'kind': 'Poche (vidage)', 'feed': 16.0, 'rapid': 10.0, 'seconds': 75.0, 'box': (0, 0, -1, 20, 0, 5), 'depth': 0.4}
        d = PR.PathInfoDialog(None, 'C:/a.vnd', f)
        self.assertEqual(d.rows['Chemin d\'accès'].text(), 'C:/a.vnd')
        self.assertEqual(d.rows['Distance d\'usinage'].text(), '16,0 mm')
        self.assertEqual(d.rows['Distance d\'usinage rapide'].text(), '10,0 mm')
        self.assertEqual(d.rows['Durée d\'usinage'].text(), '1 min 15 s')
        self.assertEqual(d.rows['Z mini'].text(), '-1,000 mm')
        self.assertEqual(d.rows['X maxi'].text(), '20,000 mm')
        self.assertEqual(d.rows['Profondeur'].text(), '0,400 mm')
        d.done(0)

    def test_without_path(self):
        f = {'kind': 'Poche (vidage)', 'feed': 0.0, 'rapid': 0.0, 'seconds': 0.0, 'box': None, 'depth': 0.4}
        d = PR.PathInfoDialog(None, '', f)
        self.assertNotIn('X mini', d.rows)
        self.assertTrue(d.rows['Chemin d\'accès'].text())
        d.done(0)


class TestPanel(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from vectordrive.ui.main_window import MainWindow
        cls.win = MainWindow()
        cls.panel = cls.win.cam_panel

    @classmethod
    def tearDownClass(cls):
        cls.win.modified = False
        cls.win.close()

    def setUp(self):
        w = self.win
        doc = w.canvas.doc
        s = Shape(path=geom.Path([geom.rect(10, 10, 20, 20)]))
        layer = Layer(name='Plan 1', items=[s])
        doc.layers[:] = [layer]
        doc.active = layer.id
        doc.plate = Plate(width=60.0, height=60.0)
        w.canvas.select([s])
        setup = self.panel.setup()
        setup.operations[:] = []
        self.panel.save(setup)
        self.op = self.panel.new_operation('gravure', exec_dialog=False)
        self.panel.refresh()
        self.panel._select_row(self.panel.ops, 0)

    def key(self, kind, key, mods=Qt.KeyboardModifier.ControlModifier):
        ev = QKeyEvent(kind, key, mods)
        ev.ignore()
        QApplication.sendEvent(self.panel.ops, ev)
        return ev

    def test_the_menu_offers_them(self):
        m = self.panel.op_menu(exec_menu=False)
        texts = [a.text() for a in m.actions()]
        self.assertIn('Informations…', texts)
        self.assertIn('Compte rendu parcours outil…', texts)
        m.deleteLater()

    def test_the_information_of_the_operation(self):
        d = self.panel.path_info(exec_dialog=False)
        self.assertGreater(float(d.rows['Distance d\'usinage'].text().split()[0].replace(',', '.')), 80.0)
        self.assertTrue(any(isinstance(w, QLabel) for w in d.rows.values()))
        d.done(0)

    def test_no_operation(self):
        s = self.panel.setup()
        s.operations[:] = []
        self.panel.save(s)
        self.panel.refresh()
        self.assertIsNone(self.panel.path_info(exec_dialog=False))
        self.assertEqual(self.panel.path_report(PR.ReportOptions(show_pdf=False), ('a', 'b')), [])

    def test_the_two_reports(self):
        with tempfile.TemporaryDirectory() as d, mock.patch('PySide6.QtGui.QDesktopServices.openUrl') as opened:
            a, b = os.path.join(d, 'a.pdf'), os.path.join(d, 'b.pdf')
            done = self.panel.path_report(PR.ReportOptions(show_pdf=False), (a, b))
            self.assertEqual(done, [a, b])
            self.assertTrue(pathlib.Path(a).read_bytes().startswith(b'%PDF'))
            self.assertTrue(pathlib.Path(b).read_bytes().startswith(b'%PDF'))
            opened.assert_not_called()

    def test_they_are_shown(self):
        with tempfile.TemporaryDirectory() as d, mock.patch('PySide6.QtGui.QDesktopServices.openUrl') as opened:
            self.panel.path_report(PR.ReportOptions(), (os.path.join(d, 'a.pdf'), os.path.join(d, 'b.pdf')))
            self.assertEqual(opened.call_count, 2)

    def test_cancelling_the_dialog(self):
        with mock.patch.object(PR.PathReportDialog, 'exec', return_value=0):
            self.assertEqual(self.panel.path_report(), [])

    def test_cancelling_the_files(self):
        with mock.patch.object(QFileDialog, 'getSaveFileName', return_value=('', '')):
            self.assertEqual(self.panel.path_report(PR.ReportOptions(show_pdf=False)), [])

    def test_the_proposed_names(self):
        self.win.canvas.doc.source_path = os.path.join(tempfile.gettempdir(), 'piece_861.vnd')
        seen = []

        def ask(_parent, _title, start, _filter):
            seen.append(os.path.basename(start))
            return '', ''
        try:
            with mock.patch.object(QFileDialog, 'getSaveFileName', ask):
                self.panel.path_report(PR.ReportOptions(show_pdf=False))
        finally:
            self.win.canvas.doc.source_path = None
        self.assertEqual(seen, ['piece_861_000_ReportByToolpath.pdf'])

    def test_a_writing_error_is_told(self):
        from PySide6.QtWidgets import QMessageBox
        bad = os.path.join(tempfile.gettempdir(), 'pas_de_dossier_861', 'a.pdf')
        with mock.patch.object(QMessageBox, 'warning') as warn:
            self.assertEqual(self.panel.path_report(PR.ReportOptions(show_pdf=False), (bad, bad)), [])
        warn.assert_called_once()

    def test_ctrl_i_on_the_list(self):
        over = self.key(QEvent.Type.ShortcutOverride, Qt.Key.Key_I)
        self.assertTrue(over.isAccepted())
        with mock.patch.object(self.panel, 'path_info') as info:
            self.key(QEvent.Type.KeyPress, Qt.Key.Key_I)
        info.assert_called_once()

    def test_ctrl_t_on_the_list(self):
        with mock.patch.object(self.panel, 'path_report') as report:
            self.key(QEvent.Type.KeyPress, Qt.Key.Key_T)
        report.assert_called_once()

    def test_other_keys_pass(self):
        over = self.key(QEvent.Type.ShortcutOverride, Qt.Key.Key_I, Qt.KeyboardModifier.NoModifier)
        self.assertFalse(over.isAccepted())
        with mock.patch.object(self.panel, 'path_info') as info:
            self.key(QEvent.Type.KeyPress, Qt.Key.Key_U)
        info.assert_not_called()

    def test_ctrl_i_stays_import_elsewhere(self):
        self.assertEqual(self.win.A['import'].shortcut().toString(), 'Ctrl+I')


if __name__ == '__main__':
    unittest.main()
