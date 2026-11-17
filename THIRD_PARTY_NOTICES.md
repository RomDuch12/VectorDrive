# Composants tiers

| Composant | Licence | Usage |
|---|---|---|
| PySide6 / Qt 6 | LGPL-3.0 | interface (liaison dynamique, bibliothèques remplaçables) |
| ezdxf | MIT | lecture / écriture DXF |
| fontTools | MIT | polices TrueType / OpenType |
| shapely / GEOS | BSD-3-Clause / LGPL-2.1 | offset, opérations booléennes |
| numpy | BSD-3-Clause | calcul |
| pypdf | BSD-3-Clause | structure des fichiers PDF |
| anthropic (SDK Python d'Anthropic) | MIT | assistant IA : Claude |
| openai (SDK Python d'OpenAI) | Apache-2.0 | assistant IA : ChatGPT |
| httpx, httpcore, idna | BSD-3-Clause | HTTP des deux SDK |
| pydantic, pydantic-core, annotated-types, typing-inspection, anyio, jiter, h11, docstring-parser | MIT | dépendances des deux SDK |
| colorama | BSD-3-Clause | dépendance de tqdm sous Windows |
| distro | Apache-2.0 | dépendance des deux SDK |
| sniffio | MIT OR Apache-2.0 | dépendance des deux SDK |
| typing-extensions | PSF-2.0 | dépendance des deux SDK |
| certifi | MPL-2.0 | certificats racine des SDK (fichier inchangé) |
| tqdm | MPL-2.0 AND MIT | dépendance du SDK openai (inchangé) |
| manifold3d (Manifold) | Apache-2.0 | volumes 3D : booléens, extrusion, révolution (licence : `licences/manifold3d-LICENSE.txt`) |

Code repris de **TauDrive** (même auteur) : encodeurs DataMatrix, QR Code,
Code 39 et EAN-13 (`vectordrive/core/barcode.py`) ; Code 128 ajouté.

Outil de test (non embarqué) : **zxing-cpp** (Apache-2.0), qui relit les
codes-barres dessinés.

Outils de fabrication (non liés au code) : **PyInstaller** (GPL-2.0 avec
exception pour les programmes empaquetés), **Inno Setup 6** (licence Inno
Setup, usage commercial permis ; le programme d'installation produit
embarque son moteur d'installation).

**Exclu** : PyMuPDF (AGPL-3.0), incompatible avec une diffusion extérieure
fermée.

## Code lié

- **vectorcraft-pathops** et **vectorcraft-geom** (storytold/vectorcraft,
  ArtCraft) — MIT OR Apache-2.0, utilisés sous **MIT**. Compilés dans
  l'extension `vectordrive/vdpathops.pyd` (sources de l'enveloppe :
  `natif/vdpathops`). Dépendances Rust : kurbo, linesweeper, pyo3 (MIT /
  Apache-2.0) ; les textes de licence des bibliothèques Rust liées dans
  l'extension : `licences/vdpathops-crates.txt`.
  **Copie modifiée** de vectorcraft-pathops 0.11.0 dans
  `natif/vendor/vectorcraft-pathops` (licences et NOTICE d'origine
  conservées) : `src/offset.rs`, le point qui sert à reconnaître un contour
  parasite du décalage est pris hors des trous du contour (et hors des îles
  d'un trou) et sur le contour aplati à 1 µm au plus ; un retrait retire
  aussi la bande des tracés ouverts. Modifications signalées par le
  commentaire « VectorDrive : ».
  **Copie** de vectorcraft-geom 0.11.0 dans `natif/vendor/vectorcraft-geom`
  (sources inchangées, licences et NOTICE d'origine conservées) : l'extension
  se construit depuis ce dépôt seul — sous macOS, `vectordrive/vdpathops.abi3.so`.
- **linesweeper 0.5.0** (jneem/linesweeper) — MIT OR Apache-2.0, utilisé
  sous **MIT**. **Copie modifiée** dans `natif/vendor/linesweeper`
  (licences d'origine conservées) : `src/topology.rs`, parcours des
  contours (`contours_for_positions`), ajout de bornes de sûreté — la
  marche d'un contour et le tour d'un point s'arrêtent par une panique au
  lieu de boucler sans fin quand les nombres d'enroulement sont localement
  incohérents (VectorDrive passe alors sur shapely). Modifications
  signalées par le commentaire « VectorDrive : bornes de sûreté ».

## Code de référence

- **storytold** (VectorCraft, CADCraft, PDFCraft, DesignCraft, FigCraft,
  craft-libs, craft-fonts) — Apache-2.0. Sources de référence dans
  hors du dépôt. Tout portage de code en Python sera
  signalé ici, fichier par fichier, avec la mention du fichier d'origine et
  des modifications, et la NOTICE Apache conservée.
- **NeoDrive, TauDrive** — code de l'auteur, réutilisé librement.

## Code porté

- **VectorCraft** (storytold/vectorcraft) — MIT OR Apache-2.0, utilisé sous **MIT**
  (texte : `licences/vectorcraft-LICENSE-MIT.txt`).
  - `vectordrive/core/liquify.py` — d'après `crates/tools/src/distort/liquify.rs` (champs
    de déplacement, rythme des touches, redécoupage, retrait des points à plat), réécrit
    en numpy ; bruit différent, segments hors du pinceau gardés tels quels.
  - `vectordrive/core/corners.py` — d'après `crates/geom/src/corners.rs` (coins, recul,
    rayon maximal, coupes), réécrit en Python ; les coupes y sont des coniques, pour
    garder de vrais arcs.
  - `vectordrive/core/varstroke.py` : les profils tout faits (`PRESETS`) — d'après
    `crates/doc/src/appearance.rs` (`WidthProfile::PRESETS`) ; ici lissés entre les points,
    avec une largeur en mm et les deux côtés réglés à part.
- **CADCraft** (storytold/cadcraft, © 2026 ArtCraft Team and the CADCraft
  contributors) — MIT OR Apache-2.0, utilisé sous **MIT** (licence :
  `licences/cadcraft-LICENSE-MIT.txt`). Portages en Python :
  - `vectordrive/core/linetypes.py` — d'après `crates/doc/src/library.rs`
    (`standard_linetypes` : valeurs en pouces, converties en mm),
    `crates/render/src/linetype.rs` (`ranges`) et
    `crates/doc/src/library/files.rs` (`parse_lin`). Modifications :
    longueurs en mm, éléments texte et formes des fichiers .lin laissés de
    côté, découpe exacte des courbes, motif ajusté aux contours fermés,
    tiret à cheval sur le départ d'un contour fermé réuni.
  - `vectordrive/core/hatch_patterns.py` — d'après `crates/doc/src/library.rs`
    (`standard_patterns` : valeurs en pouces, converties en mm ; libellés
    traduits), `crates/render/src/hatch.rs` (`Family::sweep`,
    `Family::dash`, `crossings`) et `crates/doc/src/library/files.rs`
    (`parse_pat`). Modifications : longueurs en mm, intersections en numpy,
    traits alternés, points rendus en petits cercles.
  - `vectordrive/core/strokefont.py` — table des glyphes de la police
    « CADCraft Stroke » (`crates/fonts/src/stroke.rs`, déclarée domaine
    public / CC0 par son en-tête) et décodage de sa notation. Ajouts :
    lettres accentuées composées, ligatures, guillemets, tirets, symboles,
    exposants.
  - `vectordrive/core/tancircle.py` — d'après
    `crates/engine/src/cmd/curves.rs` (`ttr`, `ttt`, `TanObj`, `solve3`).
    Modifications : objets en tuples, choix d'un segment du dessin (droit
    ou arc de cercle) au point cliqué.
  - `vectordrive/core/calc.py` (lecture des longueurs) — fractions et
    pieds-pouces d'après `crates/engine/src/units.rs` (`parse_distance`,
    `parse_mixed`). Modifications : unités métriques et points en plus,
    lecture au milieu d'un calcul, degrés minutes secondes.
  - `vectordrive/core/textmerge.py` — d'après
    `crates/engine/src/cmd/txt2mtxt.rs` (textes combinés en un seul, de
    haut en bas, au coin haut gauche). Modifications : textes tournés,
    textes à la même hauteur sur une ligne, interligne repris des écarts.
  - `vectordrive/core/compare.py` — d'après
    `crates/engine/src/cmd/file/compare.rs` (appariement par géométrie et
    propriétés puis par identifiant, zones de changements sur une grille).
    Modifications : propriétés changées sur une même géométrie, textes et
    images, zones qui se chevauchent réunies.
  - `vectordrive/ui/main_window.py` (Reproduire les propriétés) — d'après
    `crates/engine/src/cmd/props/matchprop.rs` (objet source puis objets
    destinataires, propriétés copiées au choix). Modifications : propriétés
    de VectorDrive (outil, remplissage, calque, mise en forme des textes).
  - `vectordrive/core/distort.py` (festons) — d'après
    `crates/engine/src/cmd/draw2/revcloud.rs` (`cloud_vertices` : points
    réguliers le long du contour, arcs de renflement 0,5). Modifications :
    festons calés sur les coins de tout contour, renflement réglable,
    contours ouverts, sens gardé.
  - `vectordrive/ui/tools.py` (`XLineTool`), `vectordrive/ui/canvas.py`
    (lignes de construction) — d'après `crates/engine/src/cmd/draw2/xline.rs`
    (ligne infinie par un point, plusieurs par le même point).
    Modifications : guides du plan de travail, accrochage aux croisements.
  - `vectordrive/core/cadtools.py` (`center_line`, `axis_path`),
    `vectordrive/ui/tools.py` (`CenterLineTool`) — d'après
    `crates/engine/src/cmd/draw2/centermark.rs` (`center_line` : milieu des
    débuts et des fins, traits remis dans le même sens, débord). Modifications :
    trait mixte ajusté pour finir sur des tirets longs, aperçu, outil continu.
  - `vectordrive/core/dims.py` (cote de longueur d'arc) — d'après
    `crates/render/src/dim/variants.rs` (`draw_arc_length` : arc de cote,
    lignes d'attache, symbole d'arc au-dessus du texte) et
    `crates/engine/src/cmd/annotate/angular.rs` (`ArcLenM`). Modifications :
    arc choisi par un point (plus de 180°), morceaux d'un même arc réunis,
    texte vers le centre si l'arc de cote est dedans.
  - `vectordrive/core/blend.py` (`curve_bridge`, `bridge`) — d'après
    `crates/engine/src/cmd/modify2/blend.rs` (`curve_end`, `blend_spline` :
    courbe tangente ou lisse entre deux bouts). Modifications : bouts les
    plus proches de deux traits ou d'un seul, courbe lisse en morceaux de
    Bézier, jointure en un seul tracé.
  - `vectordrive/core/gdt.py` (`parse_frame`, `compose_frame`, `layout`,
    `symbol_prims`) — d'après `crates/doc/src/gdt.rs` (chaîne, composition,
    mise en page et symboles des cadres de tolérancement). Modifications :
    cercles et arcs exacts, textes en contours, groupe qui garde sa
    définition et la suit dans les similitudes, champs du dialogue.
  - `vectordrive/core/dims.py` (`_inspected`, `space`) — d'après
    `crates/render/src/dim.rs` (DIMINSPECT : cadre, libellé et taux autour
    de la valeur) et `crates/engine/src/cmd/annotate/edit.rs` (DIMSPACE :
    cotes parallèles à intervalle régulier). Modifications : morceaux du
    texte posés un à un, base choisie parmi les cotes sélectionnées.
    De même `_jogged` et `_jog` — d'après `crates/render/src/dim/variants.rs`
    (DIMJOGGED : rayon à ressaut) et `crates/render/src/dim/linear.rs`
    (DIMJOGLINE : ressaut de ligne de cote). Modifications : ressaut placé à
    mi-chemin, plus raide s'il manque de place ; écarté sur le texte.
  - `vectordrive/io/dxf.py` (maillages 3D) — d'après
    `crates/io/src/dxf_read/entities.rs` (#2600 : un maillage polyface lu
    comme un seul objet). Modifications : polymesh, MESH et faces 3D aussi,
    en volumes ; un maillage ouvert en son contour vu de dessus.
  - `vectordrive/ui/main_window.py` (Rappeler l'effacement) — d'après
    `crates/engine/src/cmd/modify/oops.rs` et `crates/doc/src/store.rs`
    (`neighbours` : chaque objet revient entre ses voisins d'origine, seul le
    dernier effacement compte). Modifications : pile d'annulation de
    VectorDrive, calques retrouvés par identifiant ou par nom.
  - `vectordrive/core/cadtools.py` et `vectordrive/ui/main_window.py`
    (Changer par un point) — d'après `crates/engine/src/cmd/props/change.rs`
    (#2534 : le bout le plus proche de chaque ligne amené au point, un cercle
    qui passe par lui, un texte posé dessus). Modifications : bout droit d'un
    tracé ouvert, chaque cercle choisi (pas seulement seul), objets des
    groupes ; sans les questions de propriétés.
  - `vectordrive/core/calc.py` (relèvements) — d'après
    `crates/engine/src/units.rs` (#2590 : « N45dE » et les points cardinaux
    lus comme un angle depuis l'est, sens trigonométrique). Modifications :
    signe ° et virgule décimale acceptés, angle au-delà de 90° refusé.
  - `vectordrive/core/calc.py` et `vectordrive/ui/fields.py` (calculs
    précédents, « ans ») — d'après la calculatrice rapide de CADCraft (#2572 :
    historique et dernière réponse gardés d'une séance à l'autre).
    Modifications : liste du calcul des champs, 15 calculs, sans les
    variables.
  - `vectordrive/core/duplicate.py` (sur courbe par écart) — d'après
    `crates/engine/src/cmd/modify2/patharray.rs` (ARRAYPATH : autant de
    copies que la courbe en porte à l'écart donné). Modifications : pas de
    copie doublée au retour d'un contour fermé, plafond de 10 000 copies.
  - `vectordrive/core/shapes.py` et `vectordrive/ui/tools.py` (Arc centre,
    départ, fin ; Cercle 2 points) — d'après `crates/engine/src/cmd/draw2/arc.rs`
    et `crates/engine/src/cmd/draw/circle.rs` (méthodes centre-départ-fin et
    2P). Modifications : outils à clics de VectorDrive, Ctrl pour le sens
    horaire.
  - `vectordrive/core/forms.py` (Polygone par côté) — d'après
    `crates/engine/src/cmd/draw/polygon.rs` (option Côté, `polygon_from_edge`).
    Modifications : polygone paramétré de VectorDrive, Ctrl pour l'autre côté.
  - `vectordrive/core/forms.py` (Ellipse par axe) — d'après
    `crates/engine/src/cmd/draw/ellipse.rs` (bouts d'un axe, puis distance à
    l'autre axe). Modifications : ellipse paramétrée de VectorDrive.
  - `vectordrive/core/forms.py` (Rectangle 3 points) — d'après
    `crates/engine/src/cmd/draw2/rect.rs` (rectangle avec rotation).
    Modifications : un côté puis l'autre par clics, rectangle paramétré de
    VectorDrive et ses coins.
  - `vectordrive/ui/tools.py` (polygone circonscrit) — d'après
    `crates/engine/src/cmd/draw/polygon.rs` (inscrit ou circonscrit au
    cercle). Modifications : Maj pendant le tracé au lieu d'une question.
- **SolidCraft** (tangency-labs/solidcraft, © 2026 SolidCraft
  contributors) — MIT OR Apache-2.0, utilisé sous **MIT** (licence :
  `licences/solidcraft-LICENSE-MIT.txt`). Portages en Python :
  - `vectordrive/core/solids.py` (`coil`, `_helix`, `_thread_groove`,
    `ISO_COARSE`, `parse_metric`, `metric_for`, `format_metric`) — d'après
    `crates/doc/src/eval.rs` (Coil, `thread_groove`, `ISO_COARSE`,
    `parse_metric_thread`, `thread_for`, `format_thread`) et
    `crates/kernel/src/helix.rs` (`sweep_helix_mesh`). Modifications :
    ressort posé sur sa base, maillage par Manifold, tige filetée et
    taraudage d'axe vertical (perçage, pointe, chanfreins ajoutés).
    De même `hole`, `pipe` et `bounding` — d'après `crates/doc/src/eval.rs`
    (`hole_tools_and_prisms`, Pipe, BoundingSolid). Modifications : un seul
    profil tourné par perçage, lamage et fraisure par défaut, tube posé sur
    le plan, volume englobant cylindrique.
    De même `rib` et `boss` — d'après `crates/doc/src/document.rs` (Rib,
    Web) et `crates/doc/src/eval_more.rs` (`plastic_eval` : Boss).
    Modifications : nervure tracée en plan, prolongée jusqu'à l'enveloppe du
    volume ; bossage posé sur le dessus de la matière, sans congé de pied.
    De même `wrap_emboss` — d'après `crates/doc/src/eval_more.rs` (Emboss)
    et `crates/kernel/src/emboss.rs` (`emboss_cylinder_at`). Modifications :
    dessin vu de dessus enroulé sur un cylindre couché, maillage enroulé
    sommet par sommet au lieu de faces exactes.
    De même `profile_path`, `member` et `post` — d'après
    `crates/doc/src/frame.rs` (FrameMember). Modifications : sections
    centrées sur leur encombrement, profilé couché balayé avec coins en
    onglet ou poteau extrudé.
    De même `lip`, `snap_fit` et `rest` — d'après
    `crates/doc/src/eval_more.rs` (Lip, SnapFit, Rest). Modifications : bord
    pris sur le dessus du volume, clip centré sur le point, appui mesuré au
    pied avec la dépouille de l'extrusion.
    De même `sheet`, `sheet_section` et `sheet_flat` — d'après
    `crates/doc/src/sheet.rs` (SheetContour, SheetUnfold). Modifications :
    tôle debout le long d'une chaîne du plan, développé réduit au flan
    rectangulaire et à ses axes de pli.
    De même `tray` et `tray_flat` — d'après `crates/doc/src/sheet.rs`
    (SheetBase, SheetFlange, SheetUnfold). Modifications : bords tombés à
    90° sur tous les côtés d'un contour convexe, coins ouverts, développé en
    croix.
    De même `vectordrive/core/perforate.py` — d'après
    `crates/doc/src/sheet.rs` (`perforation_holes`, SheetPerforate).
    Modifications : contours fermés quelconques du dessin, traits ouverts à
    éviter, champ centré au choix.
    De même `scaling` — d'après `crates/doc/src/document.rs` (Scale).
    De même les ourlets de `sheet_section` et `sheet_flat` — d'après
    `crates/doc/src/sheet.rs` (SheetHem). Modifications : ourlets aux bouts
    de la chaîne, repliés du côté de la matière.
    De même `boundary_cells` — d'après `crates/doc/src/eval.rs`
    (BoundaryFill). Modifications : toutes les cellules d'un coup au lieu
    d'une par point, vides enfermés en plus.
    De même `sheet_fold` — d'après `crates/doc/src/sheet.rs` (SheetFold,
    `fold_side`). Modifications : plusieurs traits d'un coup, la partie qui
    reste à plat choisie pour tous les plis.
    De même `core/analysis3d.py` — d'après `crates/render/src/analysis.rs`
    (Draft, Access, leurs couleurs) et `crates/engine/src/cmd/surface_analysis.rs`
    (`inspect.draft`). Modifications : faces jugées triangle par triangle,
    accessibilité par carte de hauteurs vue depuis la direction.
    De même `line_plane` — d'après `crates/doc/src/eval.rs`
    (FeatureKind::Split, plan d'une ligne d'esquisse). Modifications : plan
    vertical passant par un segment 2D choisi dans Couper.
    De même `extent_sides`, `through_all_distance` et `extrude_between` —
    d'après `crates/doc/src/eval.rs` (`extent_sides`,
    `through_all_distance`) et `crates/doc/src/document.rs` (Extent,
    Operation). Modifications : symétrique toujours en hauteur totale,
    extrusion verticale depuis Z de départ, opération sur les volumes
    choisis avec les formes.
    De même `clearance` — d'après `crates/engine/src/cmd/clearance.rs`
    (inspect.clearance). Modifications : distances mesurées sur les
    maillages (Manifold), lieu donné par les sommets les plus proches,
    compte rendu texte.
    De même `compare`, `surface_samples`, `surface_distance` et
    `_closest_on_triangles` — d'après `crates/engine/src/cmd/compare.rs`
    (inspect.compare) et `crates/geom/src/compare.rs` (`closest_on_triangle`,
    échantillons, écarts). Modifications : régions par booléens des
    maillages au lieu d'une intégration le long de lignes, recherche par
    paquets de points voisins au lieu d'un arbre de triangles.

## Formats Gravotech

Les formats VND, VNL, GVT, SMB sont lus et écrits pour l'interopérabilité
avec des documents appartenant à l'utilisateur. Aucun code, DLL, police,
symbole ni document Gravotech n'est inclus ou redistribué. TypeEdit,
LaserType, Gravostyle et Type3 sont des marques du groupe Gravotech.
