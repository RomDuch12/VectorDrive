# VectorDrive

Logiciel de dessin pour la gravure, en Python/PySide6 : réécriture de la
partie **dessin** de TypeEdit / LaserType V15, avec son ergonomie et ses
raccourcis, et la lecture de ses fichiers.

**Logiciel libre**, sous double licence **MIT ou Apache-2.0** (au choix :
[LICENSE-MIT](LICENSE-MIT), [LICENSE-APACHE](LICENSE-APACHE)). Le cœur ne
contient aucune donnée d'atelier ; ce qui est propre à un atelier
(bibliothèque d'outils, stratégies maison, gabarits, devis, raccourcis,
**post-processeurs, fiches machine et programmes machine** — le cœur n'en
contient aucun : les parcours s'y calculent, se voient et se simulent, le
programme s'écrit par le plugin de l'atelier) s'ajoute par **plugin** :
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Démarrer

```bash
python VectorDrive.py                          # interface
python VectorDrive.py dessin.vnd               # ouvrir un fichier
python VectorDrive.py --autotest               # contrôle de l'installation
python VectorDrive.py --convert dessin.vnd --to dxf
python -m unittest discover -s tests -t .      # tests (QT_QPA_PLATFORM=offscreen)
python outils/bench.py gros.smb --copies 10    # mesures sur un gros dessin
```

Dépendances : `pip install -r requirements.txt` (PySide6, ezdxf, fontTools,
shapely, numpy, pypdf) ; développement et tests : `requirements-dev.txt`.

## Installer, publier, mettre à jour

- **Installateur Windows** : `dist/installeur/VectorDrive-x.y.z-setup.exe`
  (Inno Setup 6). Installation par utilisateur sans droits administrateur
  (ou pour tous depuis l'assistant), raccourci bureau et association `.vdz`
  au choix ; les `.vnd` restent associés à TypeEdit.
- **Publier une version** : augmenter `__version__` dans
  `vectordrive/__init__.py`, puis
  `python outils/publier.py --build --dest <dossier des mises à jour> --notes "…"`
  (PyInstaller, autotest de l'exe, installateur, manifeste
  `vectordrive-latest.json` avec empreinte SHA-256).
- **Mises à jour automatiques** : options (F10) → « Source des mises à
  jour » = ce dossier (partage réseau, dossier synchronisé) ou une
  adresse https ; « Rechercher au démarrage » ou Aide → Mises à jour.
  L'empreinte est vérifiée, l'installation est silencieuse et VectorDrive
  redémarre ; rien ne s'installe sans accord.
- **Langue** : français ou anglais (F10, au prochain démarrage) ;
  `python VectorDrive.py --lang en`. Traductions :
  `vectordrive/ressources/i18n/en.json` ; `python outils/i18n_wrap.py --extract`
  liste les libellés non traduits.

## État (v0.65.0, 16/10/2026)

| Format | Lecture | Écriture | Validation |
|---|---|---|---|
| VND (TypeEdit) | calques, zones, courbes, arcs exacts, plaque, outils, images, textes, cotes, trous | ✓ dessin inchangé réécrit à l'octet ; textes, cotes et trous déplacés restent des objets TypeEdit ; FAO conservée si structure inchangée | dessin de référence = son DXF exporté par TypeEdit ; à valider dans TypeEdit |
| GVT (TypeEdit 9+) | ✓ 16/19 exemples (relief en image, EMF en cadre, trous, polices des textes) | — (enregistrer en VND) | exemples TypeEdit et dessins réels, conformes aux aperçus |
| SMB (symboles) | ✓ 6 307 symboles réels, textes et cotations compris | ✓ réécriture à l'octet ; création (textes en courbes) | toutes les bibliothèques ; création à valider dans TypeEdit |
| DXF | ✓ arcs/bulges exacts, splines, blocs ; contours raccordés à l'ouverture (option) | ✓ LWPOLYLINE à bulges, SPLINE | aller-retour ; 117 DXF réels raccordés |
| SVG | ✓ arcs exacts, calques Inkscape | ✓ | aller-retour |
| PDF / AI ≥ 9 | ✓ tracés, XObjects | ✓ (BAT) | SVG et PDF concordent à 0,001 % |
| VDZ (natif) | ✓ | ✓ | aller-retour exact |
| EPS / PS / AI ≤ 8 | ✓ Bézier exactes | ✓ EPS | plan réel = son PDF |
| Programmes machine (SimPl, CLJOB…) | par plugin (`Api.add_format`) | par plugin | — |
| STEP | ✓ vue de dessus, trous | — | pièces « Fix on wall » |
| Polices propriétaires | par plugin (`Api.add_font_format`) : lues sur le poste, jamais redistribuées | — | — |
| Images (PNG, JPEG, BMP, TIFF, GIF) | ✓ à la taille réelle (résolution) | ✓ PNG/JPEG/BMP (dpi, transparence, largeur des outils) | taille au pixel près |
| VNL | à venir (échantillons TypeEdit) | | |

Interface : ruban Fichier / Edition / Vue / Modifier / CAD, raccourcis
TypeEdit (Ctrl+A refaire, Ctrl+L tout sélectionner, F2 dimensions…),
sélection, déplacement, rectangle / ellipse / trait, miroirs, rotations,
alignements, centrage sur plaque, périmètre exact, ouvrir / fermer les
contours, groupes, annuler / refaire, plaque.

Ruban à soi (Vue › Personnaliser le ruban) : autant d'onglets qu'on veut, nommés, placés en premier, en
dernier ou après un onglet donné, avec les commandes choisies en groupes et un libellé propre à chaque bouton ;
onglets inutiles masqués ; export / import JSON pour un autre poste. Un clic droit sur une commande du ruban
l'ajoute à un onglet à soi ; un clic droit sur un onglet le renomme ou le supprime.

Calques façon TypeEdit (calque = outil = couleur ; calque actif,
verrouillage, envoi de la sélection, table des outils), accrochage F3
(nœuds, milieux, centres, grille ; Ctrl+D / Ctrl+F), duplication linéaire,
en grille et circulaire, surface, options F10, BAT PDF (Ctrl+P).

Codes-barres DataMatrix, QR Code, Code 128, Code 39 et EAN-13 dessinés en
vectoriel (rangées, carrés, contour fusionné ou points), re-éditables par
double-clic ; suppression des contours superposés, inversion du sens,
mesure de distance et d'angle. Textes à largeur imposée (interlettrage ou
étirement), texte en arc (haut/bas, extérieur/intérieur), duplication le
long d'une courbe. Création de symboles TypeEdit (`.smb`) depuis la
sélection, rangés dans la bibliothèque ; export `.smb` du dessin.
Combiner / décombiner, englobants-englobés (trous rattachés, sens
normalisé), répartition régulière, texte ajusté dans un cadre.
Braille français (braille intégral, cotes réglables, transcription
affichée pour relecture) et photo tramée (points ou lignes). Cadrans
(graduations et chiffres) et multicopie (remplir la plaque). Aide →
Commandes (F1) : toutes les commandes et leurs raccourcis. Arcs et
segments : courbes de Bézier remplacées par des arcs tangents et des
droites à la tolérance voulue (utilisé par l'export SimPl : `Arc CW/CCW`). Rogner à la plaque ou à
un cadre (traits coupés sans ajout de bord, surfaces intersectées). Rotation libre
et échelle (F2), fichiers récents, récupération après un arrêt anormal.
Poignées à la souris : coins proportionnels (Ctrl : libre, Maj : depuis le
centre), côtés sur un axe ; second clic sur la sélection : rotation
(Ctrl : pas de 15°). Ordre des objets ; geler, masquer. Copier-coller
SVG avec les autres logiciels (Inkscape, Illustrator…) ; impression
directe à l'échelle 1:1 ou de la page BAT.

Depuis le round 23 : trous de perçage (objet Trou de TypeEdit) ;
**Vérifier** avant gravure (hors plaque, contours presque fermés,
doublons, poussières, contours plus étroits que l'outil, textes sans
glyphes…) avec corrections, et alerte avant un export machine ;
**Imbriquer** sur la plaque ; **Vectoriser** une image (contours ou
trait central pour graver en un passage) ; accrochage aux
**intersections**, sur le contour et aux **guides** ; **règles
graduées** et guides ; **Raccorder** les contours ouverts ; largeur des
outils et **aperçu de gravure** ; sélection des objets semblables.
Lecteurs éprouvés sur 5 100 fichiers volontairement abîmés
(`outils/fuzz.py`). Crénage
OpenType identique à HarfBuzz ; textes TypeEdit modifiables sur place
(position, alignement, interligne, rapport de largeur retrouvés) ;
changement de police en lot ; recherche de symboles par leurs textes ;
plaques enregistrées ; lecture partielle des VND/GVT à objet inconnu ;
réparation des SVG d'Illustrator mal formés ; textes vivants dans les
symboles créés (expérimental, à valider dans TypeEdit). Les tests et l'autotest n'écrivent jamais dans le
profil de l'utilisateur (`VECTORDRIVE_SETTINGS`).

Depuis le round 50 : aperçu du texte avec la vraie police (celles des
plugins comprises) ; démarrage en 0,5 s ; outils et opérations de TypeEdit qui
manquaient — **hachures** (aplats, croisées, retrait), **ombrage** (ombre
pleine exacte ou portée), **enveloppe** (arc, arche, bombé, pincé, vague,
trapèze), **tampon** encreur (cadre, bordure, épaulement, miroir, fond en
négatif), tous re-modifiables au double-clic ; **spirale** ;
**approximation** des polylignes en courbes lisses et **segmentation** ;
**tronquer** et **prolonger** à la souris ; **poinçonner** et rogner à la
forme exacte d'un cadre (traits monotrait coupés au bord) ; **trait
double** et **gomme à boucles** sur des courbes parallèles exactes (arcs
concentriques, Bézier à 0,1 µm) ; **espacer** à écart imposé et
**même largeur / hauteur / taille** ; **Décaler exact** (arcs
concentriques exacts au lieu de 9 µm d'écart, trous plus jamais bouchés) ;
**Mode Point** complet (droite ↔ courbe, lisse, symétrique, aligner) ;
**texte en colonnes** ; **miroir sur axe** et **dessin symétrique** ;
**raccordement** de deux traits ; **marqueur** et **cadre englobant**.
Chaque opération est éprouvée sur des DXF réels et par un fuzz
géométrique (`outils/fuzz_geom.py`, 9 000 formes aléatoires) qui a mis au
jour deux boucles sans fin du moteur booléen natif, corrigées dans une
copie modifiée de linesweeper (`natif/vendor`) ; le moteur natif est en
outre appelé sous délai avec repli shapely. Nouveautés : [CHANGELOG.md](CHANGELOG.md).

## Arborescence

| Dossier | Contenu |
|---|---|
| `vectordrive/core` | géométrie exacte (droites, Bézier, coniques), document — sans Qt |
| `vectordrive/io` | un module par format, `registry.py`, `mfc.py` (archives MFC) |
| `vectordrive/ui` | fenêtre, ruban, plan de travail |
| `docs/ARCHITECTURE.md` | cœur libre et plugins |
| `docs/typeedit_ui.md` | ergonomie TypeEdit de référence |
| `docs/vue_3d.md` | vue 3D, visualiseur de programmes, mesures, lecture |
| `docs/bibliotheque.md` | bibliothèque (B) : dossiers, vignettes, récents, favoris, gestion |
| `docs/outils_par_machine.md` | outils par machine, reconnus, vérifiés, conseillés |
| `docs/usinage_3d.md` | usinage 3D : pièce, prises, ébauche, balayage, automatismes, liste des usinages (modifier, outil, supprimer), corps, mécanismes |
| `docs/catalogues_fao.md` | opérations machine depuis un catalogue, Finition 2,5D, post-processeur, panneau FAO |
| `docs/design_step.md` | onglet Design STEP : générateurs de pièces STEP (visserie, transmission, profilés, moule, bridage), pièce STEP du dessin (extrudée ou tournée), sélection 3D (faces semblables, parallèles, coaxiales, tangentes, du corps, inverser, mesures), corps d'un STEP (extraire, séparer, réunir, répéter), vis ou pièce dans un trou, dépôt STEP |
| `tests` | tests unitaires ; corpus de fichiers réels hors dépôt (`tests/corpus.py`) |

## Validation sur machine

Avant d'usiner avec une fonction nouvelle qui change ce que la machine reçoit (enroulement, projection, laser en
morceaux…), suivre [docs/validation_machine.md](docs/validation_machine.md) : simulation, passage en l'air, pièce
d'essai.
