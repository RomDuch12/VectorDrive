# Ergonomie TypeEdit à reproduire

Notes de travail établies à partir du manuel utilisateur TypeEdit/LaserType
V14 (FR) installé avec le logiciel. Résumé factuel (noms de commandes,
touches) écrit par nous ; le manuel lui-même n'est ni copié ni redistribué.

## Fenêtre

- Barre de titre : document courant.
- **Barre d'onglets** sous le titre ; chaque onglet affiche un **ruban** de
  groupes d'icônes : Fichier, Edition, Vue, Modifier, puis l'interface de
  travail (TYPE CAD / LASER CAD ; ART et CAM hors périmètre).
- **Informations sur la sélection en fin de ruban** : type et nombre
  d'objets, taille du cadre englobant, coordonnées de l'origine.
  Format observé dans la barre d'état : `1 Courbe(s) (L 99.858 mm, H
  59.296 mm, P 0.000 mm) [ Cx 67.245 mm Cy 108.354 mm Cz 0.000 mm ]`, puis
  `X: … Y: … Z: … mm` et la vue (`XY View`).
- Filigrane de l'interface active en bas à droite.

## Onglets (correspondance VectorDrive)

| Onglet | Groupes |
|---|---|
| Fichier | Nouveau, Ouvrir, Enregistrer, Modèles, Informations, Importer/Exporter, Imprimer |
| Edition | Action (Défaire/Refaire, listes), Presse-papiers (Couper, Copier, Coller, Effacer), Sélection (outil, tout, inverser, geler), Modes (F2 position souris, F3 accrochage, F4 aperçu, F9 filtre), Groupes (Combiner, Décombiner, Grouper, Dégrouper, Combiner englobants/englobés) |
| Vue | Zoom, Rafraîchir, Orienter la vue, Contours (ordre, direction et couleur, couleurs, mode graphique) |
| Modifier | Options (F10), souris (F5), propriétés de l'objet, usinage couleur |
| CAD | Modes : symboles, création d'objets (marqueur, rectangle, polygone, étoile, Bézier, trait simple/double, cercle/ellipse, arc, polycourbe, axe, raccordements, spirale, courbes symétriques), texte (outils texte, texte dans un rectangle, sur courbe, en arc, en colonnes, transformer en courbes), **Mode Point** (ajout/suppression, transformation, connecter/déconnecter, modeler, alignements, décomposer), placer objets, vectorisation. Opérations : manipulation (étendre, tronquer, gomme pour boucles, décomposer, supprimer contours, **booléens**, rogner, poinçonner, **décaler**, décalage multiple, ombrage, enveloppe), positionnement (**alignements** intérieur/extérieur/vertical/horizontal, **centrer**, espacement et redimensionnement automatiques, ordre), transformation (rotation, **miroir**), mesure (distance, taille, angle, cadre englobant, cotation, **périmètre**, surface), duplication (linéaire, circulaire, sur courbe), effets (convertir, segmentation, arcs et segments, inverser le sens, **détection des intersections**, approximation, supprimer superposés), outils métiers (perçage, cadrans, variables, multicopie, braille, codes-barres 1D/2D, tampon, script) |

## Raccourcis clavier TypeEdit (à reprendre tels quels)

| Touche | Action |
|---|---|
| F1 | aide contextuelle |
| **F2** | dimensions et positionnement de la sélection |
| F3 | fenêtre Mode d'accrochage |
| F4 | aperçu de la transformation (maintenu) |
| F5 | paramètres de la souris |
| F7 | bascule sens / couleur / remplissage des contours |
| F9 | filtre de sélection |
| F10 | options |
| flèches | déplacement fin de la sélection (pas réglable) |
| Maj + →/← | point suivant / précédent (Mode Point) |
| Ctrl+1…6 | vues (XY, YZ, XZ, 3D graveur, 3D iso, dynamique) |
| Ctrl+7 / 8 / 9 | sens du contour / couleur / remplissage |
| Ctrl+Z | défaire |
| **Ctrl+A** | **refaire** (et non « tout sélectionner ») |
| **Ctrl+L** | **sélectionner tout** |
| Ctrl+C, Ctrl+Inser | copier |
| Ctrl+X, Maj+Suppr | couper |
| Ctrl+V, Maj+Inser | coller |
| Ctrl+N / O / S / P | nouveau / ouvrir / enregistrer / imprimer |
| Ctrl+I / Ctrl+E | importer / exporter |
| Ctrl+M | ouvrir un modèle |
| Ctrl+G | grille |
| Ctrl+D / Ctrl+F | mode d'accrochage précédent / suivant |
| Ctrl+W / Ctrl+R | actualiser / actualiser rapidement |
| Ctrl+Maj+O | visionneuse de fichiers |
| Ctrl+Page↑ / Page↓ | rapprocher / éloigner |

Modificateurs pendant un outil : Ctrl + Rectangle = carré, Ctrl + Ellipse =
cercle, Ctrl+Maj + forme = depuis le centre, Ctrl + rotation = pas de 15°,
Ctrl + échelle = pas de 100 %, Ctrl + déplacement = contraint en X ou Y,
Ctrl + clic = sélection multiple / désélection.
