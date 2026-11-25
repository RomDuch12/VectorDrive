"""Round 1153 (demande du 24/11) : « Conserver les accrochages à la fermeture et ses réglages BaT (coloriages et
autres); »."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1153.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])
BEFORE = 'avant : les accrochages repartaient de leur état d’office à chaque lancement'
STATE = ('accrochage/actif', 'accrochage/modes', 'accrochage/reperage', 'accrochage/polaire')
KEPT = STATE + ('accrochage/retenir', 'accrochage/rayon', 'options/tolerance', 'options/accrochage',
                'options/accrochage_986')
DEFAULT = {'node', 'intersection', 'guide'}


def settings():
    from vectordrive.portable import settings as st
    return st()


def window():
    from vectordrive.ui.main_window import MainWindow
    return MainWindow()


def close(w):
    if getattr(w, "_closed_1153", False):                                   # déjà fermée par l’essai
        return
    w._closed_1153 = True
    for t in getattr(w, 'docs', []):
        t.modified = False
    w.modified = False
    w.close()
    w.deleteLater()
    app.processEvents()


def put_back(before):
    """Les réglages touchés par un essai remis comme avant lui (retirés s'ils n'existaient pas)."""
    st = settings()
    for k, v in before.items():
        if v is None:
            st.remove(k)
        else:
            st.setValue(k, v)
    st.sync()


class Snaps(unittest.TestCase):
    def setUp(self):
        st = settings()
        self.addCleanup(put_back, {k: st.value(k) for k in KEPT})
        for k in STATE:                                                      # rien de retenu : un premier lancement
            st.remove(k)
        st.setValue('accrochage/retenir', True)                              # (éteint dans la graine des essais)
        st.setValue('options/accrochage', False)                             # éteint au démarrage, comme dans la graine
        st.setValue('options/accrochage_986', '1')
        st.sync()

    def open(self):
        w = window()
        self.addCleanup(close, w)
        return w

    def state(self, w):
        sn = w.canvas.snap
        return bool(sn.enabled), set(sn.modes), bool(sn.tracking), bool(sn.polar)

    def test_first_time_defaults_and_nothing_written(self):
        from vectordrive.ui import options
        self.assertTrue('accrochage/retenir' in options.BY_KEY, BEFORE)
        self.assertTrue(options.BY_KEY['accrochage/retenir'].default)        # d'office : repris
        w = self.open()
        first = options.value(w.settings, 'options/accrochage')              # « Accrochage actif au démarrage »
        self.assertEqual(self.state(w), (first, DEFAULT, False, False))
        self.assertEqual(w.A['snap'].isChecked(), first)
        for k in STATE:
            self.assertFalse(w.settings.contains(k), k)                      # rien n'a changé : rien n'est écrit

    def test_state_survives_closing(self):
        w = self.open()
        self.assertFalse(w.canvas.snap.enabled)                              # « Accrochage actif au démarrage » décoché
        w.A['snap'].setChecked(True)
        w.A['snap_node'].setChecked(False)
        w.A['snap_middle'].setChecked(True)
        w.A['snap_grid'].setChecked(True)
        w.A['snap_tracking'].setChecked(True)
        w.A['snap_polar'].setChecked(True)
        want = (True, {'intersection', 'guide', 'middle', 'grid'}, True, True)
        self.assertEqual(self.state(w), want)
        close(w)
        w = self.open()                                                      # « relancée »
        self.assertEqual(self.state(w), want, BEFORE)
        for name, on in (('snap', True), ('snap_node', False), ('snap_intersection', True), ('snap_guide', True),
                         ('snap_middle', True), ('snap_grid', True), ('snap_center', False),
                         ('snap_tracking', True), ('snap_polar', True)):
            self.assertEqual(w.A[name].isChecked(), on, name)                # les commandes cochées de même
        sw = w.snap_window(show=False)                                       # le panneau F3 aussi
        self.assertTrue(sw.enabled.isChecked())
        self.assertTrue(sw.boxes['middle'].isChecked())
        self.assertFalse(sw.boxes['node'].isChecked())
        self.assertIn('polaire', w.lbl_snap.text())                          # la barre d'état le dit
        sw.set_modes(set())                                                  # « Aucun », accrochage éteint,
        w.A['snap_polar'].setChecked(False)                                  # le repérage laissé coché
        w.A['snap'].setChecked(False)
        close(w)
        w = self.open()
        self.assertEqual(self.state(w), (False, set(), True, False))         # le repérage ne l'a pas rallumé
        self.assertFalse(w.A['snap'].isChecked())
        self.assertTrue(w.A['snap_tracking'].isChecked())

    def test_option_off_starts_from_defaults(self):
        from vectordrive.ui import options
        self.assertTrue('accrochage/retenir' in options.BY_KEY, BEFORE)
        st = settings()
        st.setValue('accrochage/retenir', False)
        st.sync()
        w = self.open()
        w.A['snap'].setChecked(True)
        w.A['snap_middle'].setChecked(True)
        w.A['snap_tracking'].setChecked(True)
        for k in STATE:
            self.assertFalse(w.settings.contains(k), k)                      # décoché : rien n'est retenu
        close(w)
        w = self.open()
        self.assertEqual(self.state(w), (False, DEFAULT, False, False))      # comme avant le round
        st.setValue('accrochage/retenir', True)                              # recoché dans F10, sans relancer :
        st.sync()
        w.A['snap_center'].setChecked(True)                                  # tout l'état du moment est retenu
        close(w)
        w = self.open()
        self.assertEqual(self.state(w), (False, DEFAULT | {'center'}, False, False))

    def test_radius_survives_closing(self):
        w = self.open()
        sw = w.snap_window(show=False)
        sw.radius.setValue(17)
        self.assertEqual(w.canvas.snap_px, 17)
        close(w)
        w = self.open()
        self.assertEqual(w.canvas.snap_px, 17, 'avant : le rayon de la fenêtre F3 revenait à la tolérance de F10')
        from vectordrive.ui import options
        self.assertEqual(options.value(w.settings, 'options/tolerance'), 17)  # un seul réglage, celui de F10


class BatFill(unittest.TestCase):
    def setUp(self):
        st = settings()
        self.addCleanup(self.put_back, {k: st.value(k) for k in st.allKeys() if k.startswith('bat/')})
        st.remove('bat/fill')                                                # aucun BAT validé encore
        st.sync()
        self.w = window()
        self.addCleanup(close, self.w)

    @staticmethod
    def put_back(before):
        st = settings()
        for k in st.allKeys():
            if k.startswith('bat/') and k not in before:                     # écrits par les BAT validés ici
                st.remove(k)
        put_back(before)

    def bat(self, fill=None, notes=None):
        """La fenêtre du BAT ouverte par `_proof_info` : rend (coloriage proposé, remarques proposées) ; `fill`
        donné : la case mise ainsi et le BAT validé, sinon abandonné."""
        from vectordrive.ui import batdialog
        seen = []

        def fake_exec(dlg):
            seen.append((dlg.checks['fill'].isChecked(), dlg.notes.toPlainText()))
            if fill is None:
                return 0
            dlg.checks['fill'].setChecked(fill)
            if notes is not None:
                dlg.notes.setPlainText(notes)
            return 1
        with mock.patch.object(batdialog.BatDialog, 'exec', fake_exec):
            info = self.w._proof_info()
        if fill is not None:
            self.assertEqual(info.fill, fill)
        return seen[0]

    def test_fill_keeps_the_last_choice(self):
        w = self.w
        screen = bool(w.canvas.show_fill)
        self.addCleanup(setattr, w.canvas, 'show_fill', screen)
        w.canvas.show_fill = True
        self.assertTrue(self.bat()[0])                                       # aucun BAT validé : comme à l'écran
        w.canvas.show_fill = False
        self.assertFalse(self.bat()[0])                                      # (abandonné : rien n'est retenu)
        self.bat(fill=True, notes='à livrer jeudi')                          # validé à l'inverse de l'écran
        got = self.bat()
        self.assertTrue(got[0], 'avant : la case Coloriage du BAT suivait l’écran à chaque ouverture')
        self.assertEqual(got[1], '')                                         # les remarques : propres à chaque BAT
        self.assertFalse(w.settings.contains('bat/notes'))
        self.assertFalse(w.settings.contains('bat/date'))
        w.canvas.show_fill = True
        self.bat(fill=False)                                                 # … et dans l'autre sens
        self.assertFalse(self.bat()[0])
        self.assertTrue(w.canvas.show_fill)                                  # l'écran, lui, n'a pas bougé


if __name__ == '__main__':
    unittest.main()
