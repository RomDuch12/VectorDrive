"""Round 1020 : demande du 14/11, 19 h 45 — « Proposer et vérifier outil en expert par défaut »."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1020.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])

from vectordrive import portable  # noqa: E402
from vectordrive.cam import model  # noqa: E402
from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Document, Shape  # noqa: E402
from vectordrive.ui import cam_panel as CP  # noqa: E402
from vectordrive.ui import modes  # noqa: E402


def shapes():
    return [Shape(path=geom.Path([geom.rect(0, 0, 30, 20)]), tool=0),
            Shape(path=geom.Path([geom.rect(40, 0, 1.2, 20)]), tool=0)]         # fente de 1,2 mm


def doc():
    d = Document()
    for sh in shapes():
        d.add(sh)
    return d


def tools(kind='fraise'):
    return [model.CamTool(name=name, kind=kind, diameter=d, number=n)
            for n, (name, d) in enumerate((('F3', 3.0), ('F1', 1.0), ('F0.5', 0.5)), 1)]


def forget():
    s = portable.settings()
    for k in (modes.KEY, 'fao/outil_propose'):
        s.remove(k)


class Proposed(unittest.TestCase):

    def setUp(self):
        forget()
        self.addCleanup(forget)

    def open(self, preset='gravure', tool_id='', lib=None, doc_tools=()):
        self.lib = tools() if lib is None else lib
        op = model.Operation(kind=CP.presets()[preset][1] if preset else 'poche', sources=[0], depth=1.0,
                             tool_id=tool_id)
        d = CP.FieldsDialog(None, 'Op', op, doc(), list(doc_tools), library=self.lib, preset=preset)
        self.addCleanup(d.deleteLater)
        return d

    def test_expert_proposes_and_checks(self):
        d = self.open()
        t = d.current_tool()
        self.assertIsNotNone(t)                                               # avant : pas d'outil
        self.assertEqual(t.name, 'F1')                                        # le plus gros qui entre dans la fente
        self.assertFalse(d.tool_note.isHidden())
        self.assertIn('F1', d.tool_note.text())
        self.assertIn('atteint tous les détails', d.tool_note.text())         # vérifié
        d.show()
        app.processEvents()
        self.assertTrue(d.tool_note.isVisible())                              # montré, rien ne le cache après coup
        d.widgets['depth'].setValue(2.0)                                      # un champ change : il ne vaut plus
        self.assertTrue(d.tool_note.isHidden())
        d.close()
        d2 = self.open()
        w = d2.widgets['tool_id']
        w.setCurrentIndex(w.findData('lib:' + self.lib[0].id))                # un autre outil : le message part
        self.assertTrue(d2.tool_note.isHidden())

    def test_tools_of_the_toolpath_kind_and_fallback(self):
        cones = [model.CamTool(name='C0.2', kind='conique', diameter=3.0, tip=0.2, angle=30.0, number=9)]
        d = self.open(lib=cones + tools())
        self.assertEqual(d.current_tool().name, 'F1')                         # une fraise, pas le cône fin
        big = tools()[:1]                                                     # F3 seule : n'entre pas dans la fente
        d = self.open(lib=big)
        self.assertEqual(d.current_tool().name, 'F3')                         # l'outil d'office d'avant, vérifié
        self.assertIn('Aucun outil ne passe partout', d.tool_note.text())
        self.assertIn('Outil proposé', d.tool_note.text())
        d = self.open(lib=cones)                                              # aucune fraise
        self.assertIsNone(d.current_tool())
        self.assertIn('Aucun outil adapté', d.tool_note.text())

    def test_nothing_when_a_tool_is_there_or_not_wanted(self):
        mine = tools()
        d = self.open(tool_id=mine[0].id, doc_tools=mine)                     # outil déjà choisi : gardé
        self.assertEqual(d.current_tool().name, 'F3')
        self.assertTrue(d.tool_note.isHidden())
        st = portable.settings()
        for key in ('percage', 'decoupe', 'trace', 'chanfrein', 'reste', 'instruction', 'laser_decoupe', 'inconnu'):
            self.assertFalse(CP.proposes_tool(st, key), key)                  # le critère n'y dit pas le bon outil
        self.assertTrue(CP.proposes_tool(st, 'gravure'))
        from vectordrive.cam import toolprefs
        with mock.patch.object(toolprefs, 'customized', return_value=True):   # Outils proposés par opération réglés
            self.assertFalse(CP.proposes_tool(st, 'gravure'))
            self.assertIsNone(self.open().current_tool())
        portable.settings().setValue(modes.KEY, 'simple')
        self.assertIsNone(self.open().current_tool())                         # mode simple : rien
        self.assertFalse(CP.proposes_tool(portable.settings(), 'decoupe'))
        portable.settings().remove(modes.KEY)
        portable.settings().setValue('fao/outil_propose', False)
        self.assertIsNone(self.open().current_tool())                         # option décochée : rien
        portable.settings().remove('fao/outil_propose')
        self.assertIsNone(self.open(preset='').current_tool())                # opération sans type de parcours

    def test_option_listed(self):
        from vectordrive.ui import options
        self.assertIn('fao/outil_propose', options.BY_KEY)                    # Options (F10), FAO
        self.assertTrue(options.default_of(options.BY_KEY['fao/outil_propose']))


class FromThePalette(unittest.TestCase):
    """Le vrai chemin : la colonne « Créer un parcours » ne met plus d'outil d'office avant le formulaire."""

    @classmethod
    def setUpClass(cls):
        from vectordrive.ui.main_window import MainWindow
        cls.w = MainWindow()

    @classmethod
    def tearDownClass(cls):
        cls.w.modified = False
        cls.w.close()

    def setUp(self):
        forget()
        self.addCleanup(forget)
        self.w.modified = False
        self.w.new_document()
        p = self.w.cam_panel
        self.w.settings.remove(p.LAST_KEY)                                    # pas de dernières valeurs retenues
        self.addCleanup(lambda: self.w.settings.remove(p.LAST_KEY))
        s = p.setup()
        s.tools = tools()                                                     # F3 d'abord : l'outil d'office d'avant
        p.save(s)
        items = shapes()
        self.w.canvas.doc.active_layer.items.extend(items)
        self.w.canvas.select(items)

    def run_form(self, accept=True):
        seen = []

        def fake_exec(dlg):
            t = dlg.current_tool()
            note = getattr(dlg, 'tool_note', None)
            seen.append((t.name if t is not None else None, note.text() if note is not None else ''))
            return 1 if accept else 0
        with mock.patch.object(CP.FieldsDialog, 'exec', fake_exec):
            op = self.w.cam_panel.new_operation('gravure')
        return op, seen[0]

    def test_palette_proposes_the_advised_tool(self):
        op, (name, note) = self.run_form()
        self.assertEqual(name, 'F1')                                          # avant : F3, le premier, sans vérifier
        self.assertIn('atteint tous les détails', note)
        self.assertEqual(self.w.cam_panel.setup().tool(op.tool_id).name, 'F1')
        op2, (name2, _n) = self.run_form()                                    # dernières valeurs : leur outil
        self.assertEqual(name2, 'F1')

    def test_cancel_adds_nothing(self):
        op, (name, _note) = self.run_form(accept=False)
        self.assertIsNone(op)
        self.assertEqual(name, 'F1')
        s = self.w.cam_panel.setup()
        self.assertEqual(len(s.tools), 3)
        self.assertEqual(s.operations, [])

    def test_simple_mode_keeps_the_first_tool(self):
        portable.settings().setValue(modes.KEY, 'simple')
        self.w.settings.setValue(modes.KEY, 'simple')
        self.addCleanup(lambda: self.w.settings.remove(modes.KEY))
        op, (name, _note) = self.run_form()
        self.assertEqual(name, 'F3')                                          # comme avant


if __name__ == '__main__':
    unittest.main()
