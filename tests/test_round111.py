"""Round 111 : ruban personnalisé (« Mon onglet », onglets masqués), zoom
fenêtre, déplacer par valeurs."""
import json
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QApplication

from vectordrive.core import geom
from vectordrive.core.document import Shape
from vectordrive.ui import ribbon_editor as RE


class TestRibbon(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        QApplication.instance() or QApplication([])
        from vectordrive.ui.main_window import MainWindow
        cls.w = MainWindow()
        cls.w.resize(1200, 800)

    @classmethod
    def tearDownClass(cls):
        for k in (RE.KEY, RE.HIDDEN):
            cls.w.settings.remove(k)
        cls.w.modified = False
        cls.w.close()

    def setUp(self):
        self.w.modified = False
        self.w.new_document()

    def test_load_defaults_and_garbage(self):
        s = self.w.settings
        s.setValue(RE.KEY, 'pas du json')
        self.assertEqual(RE.load(s)['groupes'], [])
        s.setValue(RE.KEY, json.dumps({'titre': 'Atelier', 'position': 'fin',
                                       'groupes': [{'titre': 'G', 'commandes': [{'key': 'open'}, 'x']}]}))
        conf = RE.load(s)
        self.assertEqual((conf['titre'], conf['position']), ('Atelier', 'fin'))
        self.assertEqual(conf['groupes'][0]['commandes'], [{'key': 'open'}])
        s.remove(RE.KEY)

    def test_custom_tab_and_hidden_tabs(self):
        w = self.w
        r = w.ribbon
        n = r.count()
        RE.save(w.settings, {'titre': 'Mon onglet', 'position': 'debut', 'groupes': [
            {'titre': 'Fichiers', 'commandes': [{'key': 'open', 'big': True}, {'key': 'proof', 'big': False},
                                               {'key': 'inconnue', 'big': True}]}]})
        RE.set_hidden(w.settings, ['Aide'])
        w._build_custom_tab()
        self.assertEqual(r.count(), n + 1)
        self.assertEqual(r.tabText(0), 'Mon onglet')
        self.assertEqual(r.custom_title, 'Mon onglet')
        aide = next(i for i in range(r.count()) if r.tabText(i) == 'Aide')
        self.assertFalse(r.isTabVisible(aide))
        # refait sans doublon ; vidé : l'onglet disparaît
        w._build_custom_tab()
        self.assertEqual(r.count(), n + 1)
        RE.save(w.settings, {'titre': 'Mon onglet', 'groupes': []})
        RE.set_hidden(w.settings, [])
        w._build_custom_tab()
        self.assertEqual(r.count(), n)
        self.assertTrue(all(r.isTabVisible(i) for i in range(r.count())     # onglet contextuel : selon la sélection ;
                            if r.tabText(i) not in (w.text_tab_title, 'FAO 3D')   # FAO 3D : en 3D seulement
                            and not (r.page(i) is not None and r.page(i).property('vd_cad') == '3d')))   # CAD 3D : de même

    def test_editor(self):
        w = self.w
        dlg = w.ribbon_editor(exec_dialog=False)
        dlg.new_group('Gravure')
        dlg.add('tool_text')
        dlg.add('barcode')
        dlg.move(-1)
        dlg.toggle_big()
        conf = dlg.result_conf()
        self.assertEqual([c['key'] for c in conf['groupes'][0]['commandes']], ['barcode', 'tool_text'])
        self.assertFalse(conf['groupes'][0]['commandes'][0]['big'])
        dlg.filter.setText('rectangle')
        self.assertGreaterEqual(dlg.commands.count(), 1)
        dlg.tab_checks['Aide'].setChecked(False)
        dlg.accept()
        w._build_custom_tab()
        self.assertEqual(w.ribbon.custom_title, 'Mon onglet')
        RE.save(w.settings, {'titre': 'Mon onglet', 'groupes': []})
        RE.set_hidden(w.settings, [])
        w._build_custom_tab()

    def test_zoom_window_tool(self):
        w = self.w
        c = w.canvas
        c.fit((0, 0, 200, 100))
        s0 = c.scale
        w.set_tool('zoom')
        t = c.tool_obj
        a, b = c.to_screen(10, 10), c.to_screen(30, 20)
        t.press(a, None, None)
        t.move(b, None, None)
        t.release(b, None, None)
        self.assertGreater(c.scale, s0 * 4)
        s1 = c.scale
        t.press(QPointF(50, 50), None, None)
        t.release(QPointF(51, 50), None, None)                            # un clic : rapprocher
        self.assertGreater(c.scale, s1)
        w.set_tool('select')

    def test_move_by(self):
        w = self.w
        s = Shape(path=geom.Path([geom.rect(0, 0, 10, 10)]))
        w.canvas.doc.layers[0].items.append(s)
        w.canvas.select([s])
        w.move_by(5, -2)
        bb = w.canvas.selection_bbox()
        self.assertAlmostEqual(bb[0], 5)
        self.assertAlmostEqual(bb[1], -2)
        new = w.move_by(20, 0, copy_=True)
        self.assertEqual(len(new), 1)
        self.assertEqual(len(w.canvas.doc.layers[0].items), 2)
        self.assertAlmostEqual(new[0].bbox()[0], 25)


if __name__ == '__main__':
    unittest.main()
