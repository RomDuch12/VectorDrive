"""Round 697 : gravure 2,5D « pas de passe sur le cadre » (gravure en relief)
aussi en ligne médiane — seule ou liée au parcours précédent ; modèle
TypeEdit de gravure 3D : la finition n'écrase plus le cadre ignoré de la
gravure."""
import os
import tempfile
import unittest

os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.cam import model, strategies, tpp
from vectordrive.cam.model import CamTool
from vectordrive.core import geom
from vectordrive.core.document import Document, Shape


def setup(skip=True, linked=True, outside=False):
    d = Document()
    d.plate = None
    rects = [(-10, -7, 20, 14), (-6, -3, 4, 6), (2, -3, 4, 6)]          # cadre, deux « lettres » en relief
    if outside:
        rects.append((14, -2, 3, 4))                                    # une forme hors du cadre
    shapes = [Shape(path=geom.Path([geom.rect(*r)]), tool=0) for r in rects]
    for sh in shapes:
        d.add(sh)
    ids = [sh.id for sh in shapes]
    s = model.CamSetup()
    cyl = CamTool(name='Cyl 2', diameter=2.0, number=1, cut_length=7, step_down=1.0)
    cone = CamTool(name='V', kind='conique', diameter=6.0, tip=0.2, angle=60.0, number=2, cut_length=15)
    s.tools = [cyl, cone]
    pocket = model.Operation(name='Ébauche', kind='poche', tool_id=cyl.id, items=list(ids), depth=1.0, step_down=1.0)
    carve = model.Operation(name='Gravure', kind='vcarve', tool_id=cone.id, items=list(ids), depth=2.0,
                            vcarve_mode='axe', finish_skip_frame=skip, link_previous=linked)
    s.operations = [pocket, carve] if linked else [carve]
    return d, s


def on_frame(tp, margin=1.0) -> int:
    """Mouvements dans la matière le long du cadre."""
    return sum(1 for m in tp.moves if m.kind != 'rapid' and m.z < -0.05 and -10.5 < m.x < 10.5 and
               (abs(abs(m.x) - 10) < margin or abs(abs(m.y) - 7) < margin))


class TestMedianFrame(unittest.TestCase):
    def test_linked_skips_frame(self):
        d, s = setup()
        tp = strategies.compute_all(d, s)[1]
        self.assertTrue(tp.moves)
        self.assertEqual(on_frame(tp), 0)
        self.assertTrue(any('cadre ignoré' in w for w in tp.warnings))

    def test_alone_skips_frame(self):
        d, s = setup(linked=False)
        tp = strategies.compute_all(d, s)[0]
        self.assertTrue(tp.moves)
        self.assertEqual(on_frame(tp), 0)
        # autour des lettres : la gravure est bien là
        self.assertTrue(any(m.kind != 'rapid' and m.z < -0.05 and abs(m.x) < 8 and abs(m.y) < 5 for m in tp.moves))

    def test_frame_kept_without_option(self):
        d, s = setup(skip=False, linked=False)
        tp = strategies.compute_all(d, s)[0]
        self.assertGreater(on_frame(tp), 0)                            # ligne médiane : le cadre est touché
        self.assertFalse(any('cadre ignoré' in w for w in tp.warnings))

    def test_shape_outside_frame_on_median(self):
        d, s = setup(linked=False, outside=True)
        tp = strategies.compute_all(d, s)[0]
        self.assertEqual(on_frame(tp), 0)
        out = [m for m in tp.moves if m.kind != 'rapid' and m.z < -0.05 and 14 <= m.x <= 17]
        self.assertTrue(out)                                            # la forme hors cadre, en ligne médiane
        self.assertTrue(all(-2 <= m.y <= 2 for m in out))


class TestTypeEditTemplate(unittest.TestCase):
    def op(self, sections, kind='CP_Engraving_3D'):
        return tpp.to_template(tpp.Preset(name='essai', kind=kind, sections=sections))['operations'][0]

    def test_engraving_skip_kept(self):
        o = self.op({'SPECIALGRAVURE': {'SkipExternal': '1', 'Stepover': '1.e-004'},
                     'SPECIALFINITION': {'Allowance': '1.e-004'}})
        self.assertEqual(o['kind'], 'vcarve')
        self.assertTrue(o['finish_skip_frame'])                         # la finition ne l'efface plus
        o = self.op({'SPECIALGRAVURE': {'SkipExternal': '0'}, 'SPECIALFINITION': {'SkipExternal': '1'}})
        self.assertFalse(o['finish_skip_frame'])                        # gravure 3D : la valeur de la gravure

    def test_finishing_unchanged(self):
        o = self.op({'SPECIALFINITION': {'Allowance': '1.e-004', 'SkipExternal': '1'}}, 'CP_Finishing')
        self.assertTrue(o['finish_skip_frame'])
        o = self.op({'SPECIALGRAVURE': {'SkipExternal': '1'}, 'SPECIALFINITION': {'SkipExternal': '0'}},
                    'CP_Intaglio')
        self.assertTrue(o['finish_skip_frame'])
        self.assertEqual(o['vcarve_mode'], 'axe')


if __name__ == '__main__':
    unittest.main()
