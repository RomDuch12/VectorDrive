"""Round 449 : outils propres à chaque machine (post-processeur) — sauf « tous » ; outils reconnus
d'un coup d'œil : silhouette en icône, libellé avec les cotes, fiche complète."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from vectordrive.cam import model, toollib

app = QApplication.instance() or QApplication([])


class Settings(dict):
    def value(self, k, d=None):
        return self.get(k, d)

    def setValue(self, k, v):                                         # noqa: N802
        self[k] = v


def tools():
    a = model.CamTool(name='Datron 2', kind='fraise', diameter=2.0, cut_length=4, flutes=2, vendor='Datron',
                      ref='0068432A', machines=['datron'])
    b = model.CamTool(name='V30', kind='conique', diameter=3.0, angle=30, tip=0.2, machines=['gcode'])
    c = model.CamTool(name='Foret 3', kind='foret', diameter=3.0)                 # toutes machines
    for t, n in zip((a, b, c), (1, 2, 3)):
        t.number = n
    return [a, b, c]


class TestCore(unittest.TestCase):
    def test_machine_and_labels(self):
        a, b, c = tools()
        self.assertTrue(toollib.for_machine(a, 'datron'))
        self.assertFalse(toollib.for_machine(b, 'datron'))
        self.assertTrue(toollib.for_machine(c, 'datron'))                         # sans machine : partout
        self.assertTrue(toollib.for_machine(b, ''))                               # pas de machine : tous
        self.assertEqual(toollib.specs(b), 'Ø3 30° pointe 0.2 L3')
        self.assertEqual(toollib.short_label(a), 'T1 Datron 2 — Ø2 L4 Z2')
        s = toollib.summary(a, {'datron': 'DATRON Next'})
        self.assertIn('Datron 0068432A', s)
        self.assertIn('Machines : DATRON Next', s)
        self.assertIn('Machines : toutes', toollib.summary(c))
        back = model.CamTool.from_dict(a.to_dict())
        self.assertEqual(back.machines, ['datron'])
        self.assertEqual(model.CamTool.from_dict({'name': 'x'}).machines, [])     # anciens fichiers


class TestPicker(unittest.TestCase):
    def test_machine_filter(self):
        from vectordrive.ui.tool_picker import ToolPickerDialog
        lib = {t.id: t for t in tools()}
        st = Settings()
        dlg = ToolPickerDialog(None, [], lib, settings=st, machine=('datron', 'DATRON Next'))
        try:
            self.assertFalse(dlg.filters.mach.isHidden())
            self.assertIn('DATRON Next', dlg.filters.mach.text())
            shown = lambda: sorted(it.text(0).split(' — ')[0] for it in dlg._items()      # noqa: E731
                                   if it.data(0, Qt.ItemDataRole.UserRole) and not it.isHidden())
            self.assertEqual(shown(), ['Datron 2', 'Foret 3'])                    # 1016 : sans le n° T
            dlg.filters.mach.setChecked(False)                                    # tous les outils
            self.assertEqual(shown(), ['Datron 2', 'Foret 3', 'V30'])
            self.assertFalse(st['outils/machine_seule'])
            it = next(i for i in dlg._items() if i.data(0, Qt.ItemDataRole.UserRole))
            self.assertFalse(it.icon(0).isNull())                                 # silhouette en icône
            self.assertIn('Machines', it.toolTip(0))
            dlg.tree.setCurrentItem(it)
            self.assertIn('T', dlg.info.text())                                   # fiche à côté
        finally:
            dlg.deleteLater()
        plain = ToolPickerDialog(None, [], {t.id: t for t in tools()[2:]}, settings=Settings(),
                                 machine=('datron', 'DATRON Next'))
        self.assertTrue(plain.filters.mach.isHidden())                            # aucun outil réservé : pas de case
        plain.deleteLater()


class TestManager(unittest.TestCase):
    def test_set_machines(self):
        from vectordrive.ui.toollib_dialog import ToolLibraryDialog
        p = pathlib.Path(tempfile.mkdtemp()) / 'tools.json'
        ts = tools()
        for t in ts:
            t.machines = []
        toollib.save(ts, p)
        dlg = ToolLibraryDialog(None, None, p)
        try:
            dlg.select(dlg.tools[1])
            self.assertEqual(dlg.set_machines(['datron', 'cielle']), 1)
            self.assertEqual(toollib.load(p)[1].machines, ['datron', 'cielle'])
            dlg.select(dlg.tools[1])
            self.assertEqual(dlg.set_machines([]), 1)                              # aucune : toutes
            self.assertEqual(toollib.load(p)[1].machines, [])
            m = dlg.context_menu(exec_menu=False)
            self.assertIn('Machines…', [a.text() for a in m.actions()])
        finally:
            dlg.close()


if __name__ == '__main__':
    unittest.main()
