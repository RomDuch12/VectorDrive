# Vue 3D et visualiseur de programmes

## Ouvrir

- **Ctrl+6** (ou Vue › 3D) : la pièce en 3D — le modèle 3D du fichier, les volumes du dessin, les parcours
  FAO (trajectoires ou simulation) ou le relief du dessin (liste « Relief »).
- **FAO › Visualiser un programme en 3D…** : un programme machine lu et montré seul, en filaire, cadré.
  Langages lus : ISO / G-code (arcs dans les plans XY, XZ et YZ), Heidenhain en dialogue texte clair
  (L, CC, C, CR, FMAX, cotes incrémentales), et ceux qu'ajoutent les plugins (par exemple SimPL).
  Le programme est découpé **par outil** (changements T…, TOOL CALL…) : un parcours par outil, nommé
  d'après lui, chacun dans sa couleur. L'outil de chaque parcours est reconnu (un outil de Mes outils dont
  la référence figure dans le programme, sinon les cotes lues : Ø, D, angle).

## Naviguer

| Geste ou touche | Effet |
|---|---|
| glisser (bouton gauche) | tourner (la pièce se voit aussi par-dessous) |
| glisser (bouton droit ou molette enfoncée) | déplacer |
| molette | zoomer vers le curseur |
| flèches | tourner de 15° (gauche, droite) ou 10° (haut, bas) |
| + / − (Page haut / bas) | zoomer |
| pavé numérique 1, 3, 7, 0 | face, côté, dessus, perspective |
| 5 ou O | orthogonale / perspective |
| F ou Origine | tout voir |
| double-clic | perspective |
| Échap | effacer les points mesurés |

## Lire et mesurer

- **Grille** au sol (pas affiché en haut à gauche), **Cotes** de la pièce (X × Y × Z) et légende.
- **Couleur par parcours** (légende avec le temps estimé et la longueur en avance de chacun, et le
  total), **par profondeur** (échelle surface → fond) ou **unie**.
- **Clic sur une trajectoire** : coordonnées du point le plus proche (profondeur vraie, même relief
  exagéré) ; second clic : distance et ΔX, ΔY, ΔZ.
- **Lecture** pas à pas sous la vue : curseur, vitesse, outil dessiné à sa taille, temps écoulé sur le temps
  total, « Suivre l'outil » pour garder la vue centrée sur lui.
- **Image…** : la vue enregistrée en PNG ou JPEG.
- Filaire : les trajectoires et les arêtes de la plaque ; **Plaque** décochée : la plaque est masquée.
- **Finesse** (normale, fine, très fine) : la simulation et le relief sont calculés sur 1, 4 ou 16 millions
  de points et la surface affichée est plus détaillée — pour les gravures fines d'une grande pièce. Sur un
  programme de 900 000 mouvements (pièce de 520 × 200 mm) : 7,6 s, 9 s, 10,8 s.
- La barre passe à la ligne quand la fenêtre est étroite ; le texte d'information est tronqué (en entier
  dans sa bulle).

## Programme lu : brut et durée de la machine

- Le **brut** déclaré par le programme (BLK FORM d'un programme Heidenhain, ou donné par le lecteur d'un
  plugin) remplace la plaque du dessin : la simulation part de ce bloc.
- La **durée calculée par la machine**, quand un plugin la lit (fichiers que la machine joint au
  programme), s'ajoute à la légende sous le temps estimé.

Les temps sont estimés d'après les avances : celles du réglage FAO pour les parcours calculés, celles
écrites dans le programme (F…) pour un programme lu.
