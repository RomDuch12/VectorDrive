# Parité 3D — liste de fonctions

Liste des commandes de modélisation 3D d'un logiciel de DAO généraliste (noms des commandes
d'AutoCAD, tels que les donne son aide publique), rapprochées de ce que fait VectorDrive. Elle sert
de **liste de fonctions** seulement : rien n'est repris d'un logiciel tiers, ni code ni données ;
tout est réécrit à partir du comportement décrit publiquement. AutoCAD est une marque d'Autodesk,
citée ici pour nommer les commandes.

Moteur des volumes : [Manifold](https://github.com/elalish/manifold) (`manifold3d`, Apache-2.0) —
maillages fermés garantis, booléens robustes, extrusion, révolution, coupes, projections, somme de
Minkowski, volume et aire. Les congés et chanfreins arête par arête, l'édition de faces et l'export
STEP demanderaient un noyau B-rep (OpenCASCADE, LGPL) : prévus en option, plus tard.

Dans VectorDrive, un volume est une forme du dessin (sa silhouette vue de dessus, le maillage
rangé avec elle) : il se choisit, se range dans un calque, se déplace, s'annule et s'enregistre
comme les autres objets. Commandes : ruban **3D › Volumes**.

Légende : ✅ fait (round) · 🟡 approché · ⏸ plus tard.

## Primitives

| Commande | VectorDrive |
|---|---|
| BOX, WEDGE, CYLINDER, CONE (tronc), SPHERE, PYRAMID (tronc), TORUS | ✅ 415 — sur les marqueurs choisis, au centre des objets choisis ou de la plaque |
| POLYSOLID | ✅ 418 Mur (largeur, hauteur, à gauche / au milieu / à droite du trait) |

## Volumes depuis la 2D

| Commande | VectorDrive |
|---|---|
| EXTRUDE (hauteur, dépouille) | ✅ 413 / 415 — trous compris, vers le haut ou le bas, dépouille rentrante ou sortante |
| EXTRUDE (le long d'une trajectoire), SWEEP | ✅ 418 Balayage 3D — onglets aux coins, chemin fermé, torsion, échelle d'arrivée |
| REVOLVE | ✅ 413 / 415 — deux marqueurs, une droite, ou la verticale du point le plus à gauche ; angle et départ |
| LOFT | ✅ 418 Lissage 3D — sections de bas en haut, réglé ou arrondi |
| PRESSPULL | ✅ 421 Tirer / pousser |
| THICKEN | ⏸ (surfaces) |
| CONVTOSOLID / REGION | ✅ les contours fermés servent de régions |

## Booléens et contrôle

| Commande | VectorDrive |
|---|---|
| UNION, SUBTRACT, INTERSECT | ✅ 415 |
| INTERFERE | ✅ 417 Interférence (volume commun de chaque paire, en volume si voulu) |
| SEPARATE | ✅ 417 Séparer |
| MASSPROP | ✅ 415 Propriétés de masse (volume, aire, masse, centre de gravité, encombrement) |

## Modification des volumes

| Commande | VectorDrive |
|---|---|
| SLICE | ✅ 417 Couper (plan Z =, X =, Y = ; un côté ou les deux) |
| SHELL | ✅ 421 Coque (fermée ou ouverte par le dessus) |
| FILLETEDGE | 🟡 421 Arrondir les arêtes (toutes au même rayon) · ⏸ arête par arête |
| CHAMFEREDGE, SOLIDEDIT Faces | ⏸ (B-rep) |
| Décaler un volume | ✅ 421 Décaler le volume |
| 3DMOVE, 3DROTATE, MIRROR3D | ✅ 417 (Déplacer en Z, Rotation 3D, Symétrie en Z) ; XY : outils 2D habituels, le volume suit |
| 3DSCALE | ✅ 414 mise à l'échelle uniforme 2D (la hauteur suit) |
| 3DARRAY / ARRAY | ✅ réseaux 2D habituels (le volume suit) · ⏸ réseau en Z |
| 3DALIGN | ⏸ |

## Sorties et vues

| Commande | VectorDrive |
|---|---|
| SECTION | ✅ 417 Section (contour 2D à une hauteur) |
| FLATSHOT | ✅ 417 Vue à plat (dessus, face, côté ; silhouette) |
| VIEWBASE (mise en plan) | ⏸ |
| 3DORBIT, vues, styles visuels | ✅ plan de travail 3D (source « Volumes du dessin ») |
| STLOUT | ✅ 414 |
| Import STL | ✅ 416 Importer un volume |
| Export STEP | ⏸ (B-rep) |

## Surfaces et maillages

| Commande | VectorDrive |
|---|---|
| RULESURF, TABSURF, REVSURF, EDGESURF | 🟡 reliefs (surface bilinéaire, révolution, balayages) |
| SURFBLEND, SURFPATCH, SURFNETWORK, SURFOFFSET, SURFFILLET | ⏸ |
| MESHSMOOTH / MESHREFINE | ✅ 421 Lisser le maillage |

## Lien avec la FAO

| Fonction | VectorDrive |
|---|---|
| Volume → relief (vue de dessus) pour l'usinage 3D | ✅ 416 Volume en relief |
| Relief → volume | ✅ 416 Relief en volume |
