"""Round 1004 : le formulaire d'un parcours rangé comme demandé le 14/11 — en haut l'outil et les vitesses, dessous
l'opération et les entrées et liaisons, puis le particulier, puis le reste ; Multicopie, Enroulement et Autres en bas
et en mode expert seulement."""
import json
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1004.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])

from vectordrive import portable  # noqa: E402
from vectordrive.cam import model  # noqa: E402
from vectordrive.ui import cam_panel as CP  # noqa: E402
from vectordrive.ui import modes  # noqa: E402
from vectordrive.ui.tiles import TileBoard  # noqa: E402

KEYS = ('fao/cases_operation', 'fao/cases_operation2', 'fao/cases_outil', modes.KEY)


def forget():
    s = portable.settings()
    for k in KEYS:
        s.remove(k)
    s.sync()


def dialog(op=None):
    return CP.FieldsDialog(None, 'essai', op or model.Operation(kind='contour'))


class Order(unittest.TestCase):

    def setUp(self):
        forget()
        self.addCleanup(forget)

    def open(self, op=None):
        d = dialog(op)
        self.addCleanup(d.deleteLater)
        return d

    def test_tool_and_speeds_on_top(self):
        cols = self.open().board.layout_now()
        self.assertEqual(len(cols), 2)
        self.assertEqual([cols[0][0], cols[1][0]], ['Outil', 'Vitesses'])                    # en haut
        self.assertEqual([cols[0][1], cols[1][1]], ['Opération', 'Entrées et liaisons'])     # dessous (1019)
        self.assertEqual(cols[0][2:4], ['Profondeurs', 'Avancé'])                            # dessous encore
        rest = cols[0][4:] + cols[1][2:]
        self.assertTrue({'Où usiner', 'Évidage', 'Laser', 'Angles', 'Boucles'} <= set(rest))
        low = [[k for k in c if k != 'Autres'][-1] for c in cols]
        self.assertEqual(low, ['Multicopie', 'Enroulement'])                                 # tout en bas
        if 'Autres' in cols[0] + cols[1]:
            self.assertEqual(cols[0][-1], 'Autres')                                          # et « Autres » après eux

    def test_a_tool_section(self):
        d = self.open()
        sections = dict(CP.OP_SECTIONS)
        self.assertEqual(sections['Outil'], ('tool_id', 'ref_tool_id', 'ramp'))
        self.assertNotIn('tool_id', sections['Opération'])
        tile = d.board.tiles['Outil']
        self.assertTrue(tile.isAncestorOf(d.widgets['tool_id']))
        self.assertTrue(tile.isAncestorOf(d.widgets['ramp']))           # la plongée angulaire reste sous l'outil
        self.assertTrue(d.board.tiles['Opération'].isAncestorOf(d.widgets['name']))

    def test_expert_only_sections(self):
        d = self.open()                                                 # d'office : mode expert, tout est là
        self.assertFalse(d.board.tiles['Multicopie'].isHidden() or d.board.tiles['Enroulement'].isHidden())
        portable.settings().setValue(modes.KEY, 'simple')
        d = self.open()
        self.assertTrue(d.board.tiles['Multicopie'].isHidden())
        self.assertTrue(d.board.tiles['Enroulement'].isHidden())
        self.assertFalse(d.board.tiles['Outil'].isHidden() or d.board.tiles['Vitesses'].isHidden())
        op = model.Operation(kind='contour', copies_x=3)                # une opération qui s'en sert : montrée
        d = self.open(op)
        self.assertFalse(d.board.tiles['Multicopie'].isHidden())
        self.assertTrue(d.board.tiles['Enroulement'].isHidden())
        d.widgets['copies_x'].setValue(2)                               # et ses champs s'appliquent toujours
        d.apply()
        self.assertEqual(op.copies_x, 2)

    def test_the_layout_kept_before_is_not_taken(self):
        s = portable.settings()
        s.setValue('fao/cases_operation', json.dumps([['Vitesses'], ['Opération']]))   # celle d'avant cette version
        cols = self.open().board.layout_now()
        self.assertEqual(cols[0][0], 'Outil')
        d = self.open()
        d.board.move_case('Vitesses', 0, 0)                             # la nouvelle se garde sous le réglage neuf
        self.assertEqual(json.loads(s.value('fao/cases_operation2'))[0][0], 'Vitesses')
        self.assertEqual(self.open().board.layout_now()[0][0], 'Vitesses')

    def test_board_default_given_by_the_form(self):
        from PySide6.QtWidgets import QGroupBox
        tiles = {k: QGroupBox(k) for k in ('a', 'b', 'c', 'd', 'e')}
        b = TileBoard(tiles, None, '', 2, default=[['c', 'a', 'absente'], ['b']])
        self.assertEqual(b.layout_now(), [['c', 'a', 'e'], ['b', 'd']])        # les cases non nommées : colonne courte
        self.assertEqual(b.default_layout(3), [['a', 'b'], ['c', 'd'], ['e']])  # un autre nombre de colonnes : réparties
        b.deleteLater()

    def test_tool_form_unchanged(self):
        d = CP.FieldsDialog(None, 'outil', model.CamTool(name='Cyl 2', diameter=2.0))
        self.addCleanup(d.deleteLater)
        order = [k for c in d.board.layout_now() for k in c]
        self.assertEqual(order[:3], ['Outil', 'Géométrie', 'Coupe'])
        self.assertEqual(CP.CASES_KEYS, {True: 'fao/cases_operation2', False: 'fao/cases_outil'})


if __name__ == '__main__':
    unittest.main()
