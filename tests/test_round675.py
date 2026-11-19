"""Round 675 : corps d'un STEP recopiés dans d'autres STEP en géométrie
exacte (`io.step_extract`) : extraire, séparer (un fichier par corps),
réunir des fichiers en une pièce, déplacer ; place dans l'assemblage,
noms, couleurs et unités gardés. Chaque fichier écrit est contrôlé comme
au round 673 (coques fermées, sommets et arêtes sur leurs surfaces, faces
tournées vers l'extérieur) et relu par le lecteur 3D."""
import os
import re
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import numpy as np
from PySide6.QtWidgets import QApplication

from vectordrive.core import brep as B
from vectordrive.core import stepgen as G
from vectordrive.io import model3d
from vectordrive.io import step_extract as X
from vectordrive.io.neostep import step3d
from tests.test_round672 import full_hd, tab_index
from tests.test_round673 import geometry_errors, misoriented, topology

app = QApplication.instance() or QApplication([])

AXE = B.Body('Axe', [B.Slab(0, 10, [B.Circle(0, 0, 2)])], (1.0, 0.0, 0.0))
BAGUE = B.Body('Bague', [B.Slab(0, 4, [B.Circle(30, 0, 5), B.Circle(30, 0, 2.5)])], (0.0, 0.0, 1.0))
CALE = B.Body('Cale', [B.Slab(-3, 0, [B.rounded_rect(-10, 20, 10, 30, 2)])], (0.2, 0.6, 0.2))
RX = np.array([[1.0, 0, 0], [0, 0, -1.0], [0, 1.0, 0]])         # quart de tour autour de X
RZ = np.array([[0, -1.0, 0], [1.0, 0, 0], [0, 0, 1.0]])         # quart de tour autour de Z


def _placed(body, R, t):
    m = [list(R[0]) + [t[0]], list(R[1]) + [t[1]], list(R[2]) + [t[2]], [0, 0, 0, 1]]
    return B.Body(body.name, body.slabs, body.color, m)


def _bounds(path):
    """Encombrement relu dans les coordonnées du fichier (sans redresser une pièce couchée)."""
    t = np.asarray(step3d.lire_modele(path, axe_haut='Z').triangles, float).reshape(-1, 3)
    return tuple(t.min(0)) + tuple(t.max(0))


def _text(path):
    with open(path, encoding='latin-1') as f:
        return f.read()


def assembly(part_text, places, name='asm'):
    """Un assemblage STEP : la pièce de `part_text` placée à chaque (R, t) de `places` (occurrences
    NEXT_ASSEMBLY_USAGE_OCCURRENCE et ITEM_DEFINED_TRANSFORMATION, comme les logiciels de CAO)."""
    ents = X.split_entities(part_text)

    def find(t):
        return [k for k, r in ents.items() if X._type(r) == t]
    pd = find('PRODUCT_DEFINITION')[0]
    rep = find('ADVANCED_BREP_SHAPE_REPRESENTATION')[0]
    ctx = X.refs_of(ents[rep])[-1]
    origin = [r for r in X.refs_of(ents[rep]) if X._type(ents.get(r, '')) == 'AXIS2_PLACEMENT_3D'][0]
    pdc, pc = find('PRODUCT_DEFINITION_CONTEXT')[0], find('PRODUCT_CONTEXT')[0]
    n = [max(ents)]

    def add(raw):
        n[0] += 1
        ents[n[0]] = raw
        return n[0]

    def axis(R, t):
        p = add("CARTESIAN_POINT('',(%r,%r,%r))" % tuple(float(x) for x in t))
        z = add("DIRECTION('',(%r,%r,%r))" % tuple(float(x) for x in np.asarray(R)[:, 2]))
        x = add("DIRECTION('',(%r,%r,%r))" % tuple(float(x) for x in np.asarray(R)[:, 0]))
        return add(f"AXIS2_PLACEMENT_3D('',#{p},#{z},#{x})")
    prod = add(f"PRODUCT('{name}','{name}','',(#{pc}))")
    pdf = add(f"PRODUCT_DEFINITION_FORMATION('','',#{prod})")
    pda = add(f"PRODUCT_DEFINITION('design','',#{pdf},#{pdc})")
    pdsa = add(f"PRODUCT_DEFINITION_SHAPE('','',#{pda})")
    a0 = axis(np.eye(3), (0, 0, 0))
    axes = [axis(R, t) for R, t in places]
    repa = add(f"SHAPE_REPRESENTATION('{name}',({','.join(f'#{a}' for a in [a0] + axes)}),#{ctx})")
    add(f"SHAPE_DEFINITION_REPRESENTATION(#{pdsa},#{repa})")
    for i, ax in enumerate(axes):
        nauo = add(f"NEXT_ASSEMBLY_USAGE_OCCURRENCE('{i + 1}','i{i + 1}','',#{pda},#{pd},$)")
        pdsn = add(f"PRODUCT_DEFINITION_SHAPE('','',#{nauo})")
        idt = add(f"ITEM_DEFINED_TRANSFORMATION('','',#{origin},#{ax})")
        rr = add(f"(REPRESENTATION_RELATIONSHIP('','',#{rep},#{repa})"
                 f"REPRESENTATION_RELATIONSHIP_WITH_TRANSFORMATION(#{idt})SHAPE_REPRESENTATION_RELATIONSHIP())")
        add(f"CONTEXT_DEPENDENT_SHAPE_REPRESENTATION(#{rr},#{pdsn})")
    head = part_text[:part_text.index('DATA;') + 5]
    lines = [f'#{k}={ents[k]};' for k in sorted(ents)]
    return '\n'.join([head] + lines + ['ENDSEC;', 'END-ISO-10303-21;', ''])


class _Case(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.d = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def path(self, name):
        return os.path.join(self.d, name)

    def assertSolidFile(self, path, bodies):
        """Le fichier écrit : une coque fermée par corps, géométrie juste, faces vers l'extérieur."""
        text = _text(path)
        shells = topology(text)
        self.assertEqual(len(shells), len(bodies))
        for (f, ed, v, h, bad) in shells:
            self.assertEqual(bad, [])
            self.assertEqual((v - ed + f - h) % 2, 0)
        self.assertEqual(geometry_errors(text), [])
        self.assertEqual(misoriented(text, lambda p: any(B.contains(b, p) for b in bodies)), [])
        return text

    def assertBounds(self, path, expected, delta=0.02):
        """Encombrement relu (les cercles relus en facettes : à 0,02 mm près)."""
        got = _bounds(path)
        for a, b in zip(got, expected):
            self.assertAlmostEqual(a, b, delta=delta)


class TestEntities(unittest.TestCase):
    def test_split_respects_strings_and_comments(self):
        text = ("ISO-10303-21;\nHEADER;\nENDSEC;\nDATA;\n#1=PRODUCT('a;b','it''s; ok','',(#2));\n"
                "/* #9=FAUX(); */\n#2=PRODUCT_CONTEXT('',\n  #3,'mechanical');\n#3=X('#7');\nENDSEC;\n")
        e = X.split_entities(text)
        self.assertEqual(sorted(e), [1, 2, 3])
        self.assertEqual(e[1], "PRODUCT('a;b','it''s; ok','',(#2))")
        self.assertEqual(X.refs_of(e[2]), [3])
        self.assertEqual(X.refs_of(e[3]), [])                    # « #7 » dans une chaîne : pas une référence
        self.assertEqual(X.renumber(e[1], {2: 5}), "PRODUCT('a;b','it''s; ok','',(#5))")
        self.assertEqual(X.renumber('F(#1,#2)', {1: 4}), 'F(#4,$)')
        self.assertEqual(X.closure(e, [1]), [1, 2, 3])
        with self.assertRaises(X.ExtractError):
            X.split_entities('HEADER;')

    def test_move_points(self):
        self.assertEqual(X._move_points("CARTESIAN_POINT('',(1.,2.,3.))", RZ, np.array([10.0, 0, 0]), 1.0,
                                        'CARTESIAN_POINT'), "CARTESIAN_POINT('',(8.,1.,3.))")
        self.assertEqual(X._move_points("DIRECTION('',(1.,0.,0.))", RZ, np.array([10.0, 0, 0]), 1.0,
                                        'DIRECTION'), "DIRECTION('',(0.,1.,0.))")
        self.assertEqual(X._move_points("CARTESIAN_POINT('',(1.,0.,0.))", np.eye(3), np.array([10.0, 0, 0]),
                                        10.0, 'CARTESIAN_POINT'), "CARTESIAN_POINT('',(2.,0.,0.))")
        p2 = "CARTESIAN_POINT('',(0.5,0.25))"                    # point d'une courbe de paramètres
        self.assertEqual(X._move_points(p2, RX, np.array([1.0, 2, 3]), 1.0, 'CARTESIAN_POINT'), p2)


class TestExtract(_Case):
    def setUp(self):
        super().setUp()
        self.src = self.path('piece.step')
        B.write(self.src, [AXE, BAGUE, CALE], 'piece')

    def test_bodies_like_reader(self):
        bs = X.bodies(self.src)
        self.assertEqual([b.name for b in bs], model3d.from_step(self.src).body_names)
        self.assertEqual([b.name for b in bs], ['Axe', 'Bague', 'Cale'])
        for b in bs:
            self.assertTrue(np.allclose(b.R, np.eye(3)) and np.allclose(b.t, 0))
            self.assertGreater(b.faces, 2)

    def test_extract_one(self):
        out = X.extract(self.src, [1], self.path('bague.step'))
        text = self.assertSolidFile(out, [BAGUE])
        m = model3d.from_step(out)
        self.assertEqual(m.body_names, ['Bague'])
        self.assertBounds(out, (25, -5, 0, 35, 5, 4))
        self.assertEqual(text.count("STYLED_ITEM('color'"), 6)          # une couleur par face, gardée
        self.assertEqual(set(re.findall(r"COLOUR_RGB\('',([^)]*)\)", text)), {'0.,0.,1.'})
        self.assertIn('ADVANCED_BREP_SHAPE_REPRESENTATION', text)
        self.assertIn("SI_UNIT(.MILLI.,.METRE.)", text)
        for kind in ('CYLINDRICAL_SURFACE', 'PLANE(', 'CIRCLE(', 'EDGE_CURVE'):     # surfaces exactes, pas de facettes
            self.assertEqual(text.count(kind), B.step_text([BAGUE], 'b').count(kind))

    def test_extract_several_and_errors(self):
        out = X.extract(self.src, [2, 0], self.path('deux.step'), name='Deux corps')
        self.assertSolidFile(out, [AXE, CALE])
        self.assertEqual(model3d.from_step(out).body_names, ['Axe', 'Cale'])
        self.assertIn("PRODUCT('Deux corps'", _text(out))
        for bad in ([], [3], [-1]):
            with self.assertRaises(X.ExtractError):
                X.extract(self.src, bad, self.path('x.step'))

    def test_extract_moved(self):
        out = X.extract(self.src, [1, 2], self.path('tournee.step'), moves={1: (RX, (5, 6, 7))})
        moved = _placed(BAGUE, RX, (5, 6, 7))
        self.assertSolidFile(out, [moved, CALE])
        m = model3d.from_step(out)
        self.assertEqual(m.body_names, ['Bague', 'Cale'])
        self.assertBounds(out, (-10, 2, -3, 40, 30, 12))
        alone = X.extract(self.src, [1], self.path('seule.step'), moves={1: (RX, (5, 6, 7))})
        self.assertBounds(alone, (30, 2, 2, 40, 6, 12))                # y : -z ; z : y

    def test_split(self):
        files = X.split(self.src, self.path('parts'))
        self.assertEqual([os.path.basename(f) for f in files], ['Axe.step', 'Bague.step', 'Cale.step'])
        for f, body, box in zip(files, (AXE, BAGUE, CALE),
                                ((-2, -2, 0, 2, 2, 10), (25, -5, 0, 35, 5, 4), (-10, 20, -3, 10, 30, 0))):
            self.assertSolidFile(f, [body])
            self.assertEqual(model3d.from_step(f).body_names, [body.name])
            self.assertBounds(f, box)
        some = X.split(self.src, self.path('some'), picks=[2])
        self.assertEqual([os.path.basename(f) for f in some], ['Cale.step'])

    def test_split_same_names(self):
        src = self.path('meme.step')
        B.write(src, [AXE, B.Body('Axe', [B.Slab(0, 5, [B.Circle(20, 0, 1)])]), B.Body('Été / 2', CALE.slabs)])
        files = X.split(src, self.path('p'))
        self.assertEqual([os.path.basename(f) for f in files], ['Axe.step', 'Axe_2.step', 'Ete_2.step'])

    def test_combine_with_generated_part(self):
        vis = G.write('chc', G.values('chc', size='M6', length=20), self.path('vis.step'))
        out = X.combine([(self.src, [1], None), (vis, None, (np.eye(3), (30, 0, 4)))], self.path('tout.step'),
                        name='Bague et vis')
        m = model3d.from_step(out)
        self.assertEqual(m.body_names, ['Bague', 'Vis CHC ISO 4762 M6x20'])
        x0, y0, z0, x1, y1, z1 = _bounds(out)
        self.assertAlmostEqual(z0, -16, delta=0.02)                       # tige de 20 sous la tête posée à z = 4
        self.assertAlmostEqual(z1, 10, delta=0.02)                        # tête de 6 au-dessus
        self.assertAlmostEqual(x0, 25, delta=0.02)
        n_vis = len(model3d.from_step(vis).face_kinds)
        n_bague = len(model3d.from_step(X.extract(self.src, [1], self.path('b.step'))).face_kinds)
        self.assertEqual(len(m.face_kinds), n_vis + n_bague)
        self.assertEqual(len(topology(_text(out))), 2)
        self.assertEqual(geometry_errors(_text(out)), [])

    def test_units(self):
        cm = self.path('cm.step')
        with open(cm, 'w', encoding='latin-1', newline='\n') as f:
            f.write(B.step_text([BAGUE], 'cm').replace('SI_UNIT(.MILLI.,.METRE.)', 'SI_UNIT(.CENTI.,.METRE.)'))
        bs = X.bodies(cm)
        self.assertAlmostEqual(bs[0].extra['unit_mm'], 10.0)
        self.assertBounds(cm, (250, -50, 0, 350, 50, 40))
        out = X.extract(cm, [0], self.path('cm_moved.step'), moves={0: (np.eye(3), (10, 0, 0))})
        self.assertIn('SI_UNIT(.CENTI.,.METRE.)', _text(out))           # unités du fichier gardées
        self.assertBounds(out, (260, -50, 0, 360, 50, 40))              # déplacement donné en mm
        with self.assertRaises(X.ExtractError):
            X.combine([(self.src, [0], None), (cm, None, None)], self.path('mix.step'))


class TestAssembly(_Case):
    def test_instances_placed(self):
        part = B.step_text([BAGUE], 'bague')
        places = [(np.eye(3), (0, 0, 0)), (RZ, (0, 0, 50)), (RX, (100, 0, 0))]
        src = self.path('asm.step')
        with open(src, 'w', encoding='latin-1', newline='\n') as f:
            f.write(assembly(part, places))
        bs = X.bodies(src)
        self.assertEqual(len(bs), 3)
        self.assertEqual(len({b.item for b in bs}), 1)                  # une seule pièce, trois fois placée
        self.assertEqual([b.name for b in bs], model3d.from_step(src).body_names)
        for b, (R, t) in zip(bs, places):
            self.assertTrue(np.allclose(b.R, R) and np.allclose(b.t, t))
        files = X.split(src, self.path('parts'))
        self.assertEqual(len(files), 3)
        self.assertEqual(len({os.path.basename(f).lower() for f in files}), 3)
        boxes = ((25, -5, 0, 35, 5, 4), (-5, 25, 50, 5, 35, 54), (125, -4, -5, 135, 0, 5))
        for f, (R, t), box in zip(files, places, boxes):
            self.assertSolidFile(f, [_placed(BAGUE, R, t)])
            self.assertBounds(f, box)
        both = X.extract(src, [1, 2], self.path('deux.step'), moves={2: (np.eye(3), (0, 0, 10))})
        self.assertSolidFile(both, [_placed(BAGUE, RZ, (0, 0, 50)), _placed(BAGUE, RX, (100, 0, 10))])
        self.assertEqual(len(topology(_text(both))), 2)



class TestDialog(_Case):
    def setUp(self):
        super().setUp()
        self.src = self.path('piece.step')
        B.write(self.src, [AXE, BAGUE, CALE], 'piece')

    def test_rotation(self):
        from vectordrive.ui.step_edit_dialog import rotation
        self.assertEqual(rotation('X', 90), RX.tolist())
        self.assertEqual(rotation('Z', 90), RZ.tolist())
        R = np.asarray(rotation('Y', 30))
        self.assertTrue(np.allclose(R.T @ R, np.eye(3)) and abs(np.linalg.det(R) - 1) < 1e-12)

    def test_checked_moved_written(self):
        from vectordrive.ui.step_edit_dialog import StepBodiesDialog
        d = StepBodiesDialog(None, self.src, picks=[1])
        self.assertEqual(d.list.count(), 3)
        self.assertEqual(d.checked(), [1])
        self.assertEqual(len(d.meshes), 3)
        self.assertIsNone(d.move())
        lo = d.preview.tris.reshape(-1, 3).min(0)
        self.assertAlmostEqual(float(lo[0]), 25, delta=0.02)               # aperçu : le corps coché seul
        d.set_move(5, 6, 7, 'X', 90)
        lo, hi = d.preview.tris.reshape(-1, 3).min(0), d.preview.tris.reshape(-1, 3).max(0)
        for a, b in zip(list(lo) + list(hi), (30, 2, 2, 40, 6, 12)):
            self.assertAlmostEqual(float(a), b, delta=0.02)               # aperçu déplacé
        out = d.extract(self.path('seule.step'))
        self.assertBounds(out, (30, 2, 2, 40, 6, 12))
        self.assertSolidFile(out, [_placed(BAGUE, RX, (5, 6, 7))])
        d.check_all(True)
        d.set_move()
        files = d.split(self.path('parts'), ask=False)
        self.assertEqual([os.path.basename(f) for f in files], ['Axe.step', 'Bague.step', 'Cale.step'])
        self.assertBounds(files[1], (25, -5, 0, 35, 5, 4))
        self.assertEqual(d.split(self.path('parts'), ask=False), files)    # remplacés
        self.assertIn('3', d.info.text())
        d.check_all(False)
        self.assertFalse(d.b_extract.isEnabled() or d.b_split.isEnabled())
        self.assertIsNone(d.extract(self.path('rien.step')))
        self.assertEqual(d.split(self.path('rien'), ask=False), [])
        self.assertFalse(os.path.exists(self.path('rien.step')))
        d.deleteLater()

    def test_bad_file(self):
        from vectordrive.ui.step_edit_dialog import StepBodiesDialog
        bad = self.path('bad.step')
        with open(bad, 'w', encoding='latin-1') as f:
            f.write('pas un STEP')
        d = StepBodiesDialog(None)
        self.assertFalse(d.load(bad))
        self.assertEqual((d.path, d.list.count()), ('', 0))
        self.assertTrue(d.info.text())
        self.assertFalse(d.b_extract.isEnabled())
        d.deleteLater()


class TestWindow(_Case):
    def setUp(self):
        super().setUp()
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.w.step_depot_folder(self.d)
        self.src = self.path('piece.step')
        B.write(self.src, [AXE, BAGUE, CALE], 'piece')

    def tearDown(self):
        for i in range(len(self.w.docs)):
            self.w.docs[i].modified = False
        self.w.modified = False
        self.w.close()
        super().tearDown()

    def test_tab(self):
        r = self.w.ribbon
        page = r.page(tab_index(r, 'Design STEP'))
        self.assertEqual([g.title.text() for g in page.groups()], ['Générateurs', 'Sélection 3D', 'Modifier un STEP',
                                                                'Dépôt STEP'])
        acts = [b.defaultAction() for g in page.groups() for b in g.buttons()]
        for k in ('step_bodies', 'step_combine', 'step_screw'):
            self.assertIn(self.w.A[k], acts, k)
        self.assertTrue(page.fit(full_hd()))                    # tient en 1920 (sans défiler, 1094)

    def test_split_then_combine(self):
        w = self.w
        d = w.step_bodies(self.src, exec_dialog=False)
        self.assertEqual(d.checked(), [0, 1, 2])
        files = d.split(self.path('parts'), ask=False)
        d.deleteLater()
        out = w.step_combine(files, self.path('tout.step'))
        self.assertEqual([b.name for b in X.bodies(out)], ['Axe', 'Bague', 'Cale'])
        self.assertSolidFile(out, [AXE, BAGUE, CALE])                       # chaque corps revenu à sa place
        self.assertBounds(out, _bounds(self.src))
        self.assertIn("PRODUCT('tout'", _text(out))
        cm = self.path('cm.step')
        with open(cm, 'w', encoding='latin-1', newline='\n') as f:
            f.write(B.step_text([BAGUE], 'cm').replace('SI_UNIT(.MILLI.,.METRE.)', 'SI_UNIT(.CENTI.,.METRE.)'))
        self.assertIsNone(w.step_combine([files[0], cm], self.path('mix.step')))
        self.assertIn('Réunion impossible', w.statusBar().currentMessage())
        self.assertFalse(os.path.exists(self.path('mix.step')))

    def test_body_of_drawing(self):
        w = self.w
        self.assertTrue(w.open_path(self.src))
        w._ensure_panel3d()
        p = w.panel3d
        self.assertTrue(p.refresh())
        m = p.view.model
        face = int(np.asarray(m.face_of)[np.where(np.asarray(m.body_ids()) == 2)[0][0]])
        p.view.set_selection([face])
        self.assertEqual(p.selected_body(), 2)
        d = w.step_bodies(exec_dialog=False)                               # la pièce du dessin, le corps choisi
        self.assertEqual(os.path.normcase(d.path), os.path.normcase(self.src))
        self.assertEqual(d.checked(), [2])
        out = d.extract(self.path('cale.step'))
        self.assertEqual([b.name for b in X.bodies(out)], ['Cale'])
        d.deleteLater()



def _rebuild(text, ents):
    head = text[:text.index('DATA;') + 5]
    return '\n'.join([head] + [f'#{k}={ents[k]};' for k in sorted(ents)] + ['ENDSEC;', 'END-ISO-10303-21;', ''])


class TestReview(_Case):
    """Relecture : axes omis, contexte d'une représentation complexe, corps maillés, unités d'angle, miroir,
    lecture de la section DATA, surcharge de couleur, styles écrits une fois, noms réservés."""

    def save(self, name, text):
        path = self.path(name)
        with open(path, 'w', encoding='latin-1', newline='\n') as f:
            f.write(text)
        return path

    def test_default_axes_rotated(self):
        t = B.step_text([BAGUE], 'dflt')
        ents = X.split_entities(t)
        z_dirs = {k for k, r in ents.items() if X._type(r) == 'DIRECTION' and re.search(r"\(0\.,0\.,1\.\)", r)}
        x_dirs = {k for k, r in ents.items() if X._type(r) == 'DIRECTION' and re.search(r"\(1\.,0\.,0\.\)", r)}
        n = 0
        for k, r in list(ents.items()):
            if X._type(r) == 'AXIS2_PLACEMENT_3D':
                pt, zz, xx = X.refs_of(r)
                if zz in z_dirs and xx in x_dirs:              # les valeurs par défaut : « $ » (ISO 10303-42)
                    ents[k] = f"AXIS2_PLACEMENT_3D('',#{pt},$,$)"
                    n += 1
        self.assertGreater(n, 5)
        src = self.save('dflt.step', _rebuild(t, ents))
        self.assertBounds(src, (25, -5, 0, 35, 5, 4))
        out = X.extract(src, [0], self.path('dflt_rx.step'), moves={0: (RX, (0, 0, 0))})
        self.assertBounds(out, (25, -4, -5, 35, 0, 5))
        text = _text(out)
        self.assertNotIn(',$', ''.join(ln for ln in text.splitlines() if 'AXIS2_PLACEMENT_3D' in ln))
        self.assertAlmostEqual(step3d.lire_modele(out, axe_haut='Z').aire(),
                               step3d.lire_modele(src, axe_haut='Z').aire(), 3)
        same = X.extract(src, [0], self.path('dflt_id.step'))            # sans déplacement : recopié tel quel
        self.assertIn(',$,$)', _text(same))

    def test_complex_representation_context(self):
        t = B.step_text([BAGUE], 'cx').replace('SI_UNIT(.MILLI.,.METRE.)', 'SI_UNIT(.CENTI.,.METRE.)')
        ents = X.split_entities(t)
        rep = next(k for k, r in ents.items() if X._type(r) == 'ADVANCED_BREP_SHAPE_REPRESENTATION')
        args = ents[rep][len('ADVANCED_BREP_SHAPE_REPRESENTATION('):-1]
        ents[rep] = f'(ADVANCED_BREP_SHAPE_REPRESENTATION()REPRESENTATION({args})SHAPE_REPRESENTATION())'
        src = self.save('cx.step', _rebuild(t, ents))
        bs = X.bodies(src)
        self.assertIsNotNone(bs[0].context)
        out = X.extract(src, [0], self.path('cx_out.step'))
        self.assertBounds(out, (250, -50, 0, 350, 50, 40))               # pas 10 fois trop petite
        self.assertIn('SI_UNIT(.CENTI.,.METRE.)', _text(out))
        b0 = bs[0]
        b0.context = None                                                 # contexte introuvable : refus, pas des mm
        with self.assertRaises(X.ExtractError):
            X.write_bodies([(X.split_entities(_text(src)), b0, None)], self.path('x.step'))

    def test_tessellated_moved(self):
        t = B.step_text([BAGUE], 'tess')
        ents = X.split_entities(t)
        rep = next(k for k, r in ents.items() if X._type(r) == 'ADVANCED_BREP_SHAPE_REPRESENTATION')
        refs = X.refs_of(ents[rep])
        axis = next(r for r in refs if X._type(ents[r]) == 'AXIS2_PLACEMENT_3D')
        n = max(ents)
        ents[n + 1] = "COORDINATES_LIST('',4,((0.,0.,0.),(10.,0.,0.),(0.,10.,0.),(0.,0.,10.)))"
        ents[n + 2] = (f"TRIANGULATED_FACE('',#{n + 1},4,((0.,0.,1.)),$,(),"
                       f"((1,3,2),(1,2,4),(2,3,4),(1,4,3)))")
        ents[n + 3] = f"TESSELLATED_SOLID('tetra',(#{n + 2}),$)"
        ents[rep] = f"TESSELLATED_SHAPE_REPRESENTATION('tess',(#{n + 3},#{axis}),#{refs[-1]})"
        src = self.save('tess.step', _rebuild(t, ents))
        out = X.extract(src, [0], self.path('tess_moved.step'), moves={0: (RZ, (100, 0, 0))})
        self.assertBounds(out, (90, 0, 0, 100, 10, 10))
        self.assertIn('((0.,0.,1.))', _text(out))                         # normale autour de Z : inchangée
        out2 = X.extract(src, [0], self.path('tess_rx.step'), moves={0: (RX, (0, 0, 0))})
        self.assertIn('((0.,-1.,0.))', _text(out2))                       # normale tournée

    def test_angle_units_and_mirror(self):
        cone = B.Body('Cone', [B.Slab(0, 10, [B.Circle(0, 0, 5, 2)])], (0.8, 0.2, 0.2))
        rad = B.step_text([cone], 'rad')
        src_rad = self.save('rad.step', rad)
        ents = X.split_entities(rad)
        k_an = next(k for k, r in ents.items() if 'PLANE_ANGLE_UNIT' in r)
        n = max(ents)
        ents[n + 1] = "(NAMED_UNIT(*)PLANE_ANGLE_UNIT()SI_UNIT($,.RADIAN.))"
        ents[n + 2] = "DIMENSIONAL_EXPONENTS(0.,0.,0.,0.,0.,0.,0.)"
        ents[n + 3] = f"PLANE_ANGLE_MEASURE_WITH_UNIT(PLANE_ANGLE_MEASURE(0.01745329252),#{n + 1})"
        ents[k_an] = f"(CONVERSION_BASED_UNIT('DEGREE',#{n + 3})NAMED_UNIT(#{n + 2})PLANE_ANGLE_UNIT())"
        src_deg = self.save('deg.step', _rebuild(rad, ents))
        with self.assertRaises(X.ExtractError):
            X.combine([(src_deg, None, None), (src_rad, None, None)], self.path('mix.step'))
        X.combine([(src_rad, None, None), (src_rad, None, (np.eye(3), (20, 0, 0)))], self.path('ok.step'))
        mirror = np.diag([1.0, 1.0, -1.0])
        for R in (mirror, 2.0 * np.eye(3)):                               # miroir, mise à l'échelle : refusés
            with self.assertRaises(X.ExtractError):
                X.extract(src_rad, [0], self.path('m.step'), moves={0: (R, (0, 0, 0))})
        self.assertFalse(os.path.exists(self.path('m.step')))

    def test_data_section_and_items(self):
        base = B.step_text([BAGUE], 'p')
        cases = {
            'espace': base.replace('\nDATA;\n', '\nDATA ;\n'),
            'entete': base.replace("FILE_DESCRIPTION(('VectorDrive')", "FILE_DESCRIPTION(('DATA; #14=X(); x')"),
            'dollar': re.sub(r"(ADVANCED_BREP_SHAPE_REPRESENTATION\('p',\()", r"\1$,", base),
            'endsec': base.replace("PRODUCT('p','p',''", "PRODUCT('p','p','ENDSEC; fin'"),
            'nommee': base.replace('\nDATA;\n', "\nDATA('donnees',('AUTOMOTIVE_DESIGN'));\n")}
        for label, text in cases.items():
            self.assertNotEqual(text, base, label)
            src = self.save(f'{label}.step', text)
            out = X.extract(src, [0], self.path(f'{label}_out.step'))
            self.assertEqual([b.name for b in X.bodies(out)], ['Bague'], label)
            self.assertBounds(out, (25, -5, 0, 35, 5, 4))

    def test_override_colour_and_styles_once(self):
        t = B.step_text([BAGUE], 'p')
        ents = X.split_entities(t)
        face = next(k for k, r in ents.items() if X._type(r) == 'ADVANCED_FACE')
        styled = next(k for k, r in ents.items() if X._type(r) == 'STYLED_ITEM')
        n = max(ents)
        ents[n + 1] = "COLOUR_RGB('',1.,0.,0.)"
        ents[n + 2] = f"FILL_AREA_STYLE_COLOUR('',#{n + 1})"
        ents[n + 3] = f"FILL_AREA_STYLE('',(#{n + 2}))"
        ents[n + 4] = f"SURFACE_STYLE_FILL_AREA(#{n + 3})"
        ents[n + 5] = f"SURFACE_SIDE_STYLE('',(#{n + 4}))"
        ents[n + 6] = f"SURFACE_STYLE_USAGE(.BOTH.,#{n + 5})"
        ents[n + 7] = f"PRESENTATION_STYLE_ASSIGNMENT((#{n + 6}))"
        ents[n + 8] = f"OVER_RIDING_STYLED_ITEM('rouge',(#{n + 7}),#{face},#{styled})"
        src = self.save('over.step', _rebuild(t, ents))
        out = _text(X.extract(src, [0], self.path('over_out.step')))
        self.assertIn("COLOUR_RGB('',1.,0.,0.)", out)
        self.assertNotIn('OVER_RIDING_STYLED_ITEM', out)                 # gardée comme style simple
        three = self.path('trois.step')
        B.write(three, [B.Body(f'b{i}', [B.Slab(0, 2, [B.Circle(20 * i, 0, 3)])], (0.0, 0.0, 1.0))
                        for i in range(3)])
        text = _text(X.extract(three, [0, 1, 2], self.path('trois_out.step')))
        self.assertEqual(text.count('COLOUR_RGB('), 1)                    # la chaîne du style écrite une fois
        self.assertEqual(text.count("STYLED_ITEM('color'"), _text(three).count("STYLED_ITEM('color'"))

    def test_reserved_names(self):
        self.assertEqual(X.safe_name('NUL'), '_NUL')
        self.assertEqual(X.safe_name('con.part'), '_con.part')
        self.assertEqual(X.safe_name('Console'), 'Console')
        src = self.path('res.step')
        B.write(src, [B.Body('COM1', [B.Slab(0, 2, [B.Circle(0, 0, 3)])])])
        self.assertEqual([os.path.basename(f) for f in X.split(src, self.path('r'))], ['_COM1.step'])


class TestReviewUi(_Case):
    def setUp(self):
        super().setUp()
        self.src = self.path('piece.step')
        B.write(self.src, [AXE, BAGUE, CALE], 'piece')

    def test_file_changed_on_disk(self):
        from vectordrive.ui.step_edit_dialog import StepBodiesDialog
        d = StepBodiesDialog(None, self.src)
        B.write(self.src, [CALE, AXE], 'piece')                          # réécrit : deux corps, autre ordre
        os.utime(self.src, (d.mtime + 10, d.mtime + 10))
        self.assertIsNone(d.extract(self.path('a.step')))
        self.assertIn('changé', d.info.text())
        self.assertEqual([b.name for b in d.bodies], ['Cale', 'Axe'])    # relu
        self.assertFalse(os.path.exists(self.path('a.step')))
        out = d.extract(self.path('a.step'))
        self.assertEqual([b.name for b in X.bodies(out)], ['Cale', 'Axe'])
        d.deleteLater()

    def test_unreadable_file_said(self):
        from unittest import mock
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            junk = self.path('junk.step')
            with open(junk, 'w', encoding='latin-1') as f:
                f.write('rien')
            with mock.patch('vectordrive.ui.main_window.QMessageBox.warning') as warn:
                self.assertIsNone(w.step_bodies(junk))
            warn.assert_called_once()
            self.assertIn('Lecture impossible', warn.call_args[0][2])
        finally:
            w.modified = False
            w.close()

if __name__ == '__main__':
    unittest.main()
