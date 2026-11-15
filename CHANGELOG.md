# Nouveautés de VectorDrive

Ce qui change pour l'utilisateur, version par version (les plus récentes en bas).

### v0.2.0 — interface à ruban, formats DXF, SVG, PDF, VND, texte

### v0.3.0 — symboles, plaque, calques = outils

### v0.4.0 — codes-barres, DataMatrix, QR Code, BAT PDF

### v0.5.0 — texte en arc et en largeur imposée, duplication sur courbe

### v0.6.0 — gros fichiers

### v0.7.0 — création de symboles

### v0.8.0 — combiner, répartir, texte dans un cadre

### v0.9.0 — braille, photo

### v0.10.0 — contrôle sur un corpus de fichiers réels, cadrans, multicopie

### v0.11.0 — arcs et segments

### v0.12.0 — rogner

### v0.13.0 — confort de production

### v0.14.0 — poignées

### v0.15.0 — ordre, gel, masquage

### v0.16.0 — échanges et impression

### v0.17.0 — GVT

### v0.18.0 — bibliothèque Gravotech et trous de perçage

### v0.19.0 — textes et cotes TypeEdit déplacés

### v0.20.0 — fichiers abîmés et vérification avant gravure

### v0.21.0 — polices des textes et prudence à l'écriture

### v0.22.0 — imbrication

### v0.23.0 — vectorisation d'images

### v0.24.0 — trait central

### v0.25.0 — accrochage aux intersections

### v0.26.0 — raccord des contours

### v0.27.0 — règles et guides

### v0.28.0 — images bitmap

### v0.29.0 — aperçu de gravure, sélection des semblables

### v0.30.0 — DXF raccordés à l'ouverture, tests isolés

### v0.31.0 — crénage OpenType

### v0.32.0 — polices Gravotech

### v0.33.0 — textes TypeEdit modifiables sur place

### v0.34.0 — textes TypeEdit sur plusieurs lignes

### v0.35.0 — sûreté des polices

### v0.36.0 — boîte Plaque

### v0.37.0 — polices en cache

### v0.38.0 — scénarios complets

### v0.39.0 — alignement lu, textes vivants dans les symboles

### v0.40.0 — recherche dans les textes des symboles

### v0.41.0 — lecture partielle

### v0.42.0 — SVG mal formés

### v0.43.0 — SimPl à séquences intégrées, documentation

### v0.44.0 — fiche de validation TypeEdit

### v0.45.0 — aperçu du texte

### v0.46.0 — temps de démarrage

### v0.47.0 — analyse statique

### v0.48.0 — hachures

### v0.49.0 — ombrage

### v0.50.0 — spirale

### v0.51.0 — approximation, segmentation

### v0.52.0 — enveloppe

### v0.53.0 — tampon

### v0.54.0 — tronquer, prolonger

### v0.55.0 — poinçonner, rogner à une forme

### v0.56.0 — trait double, gomme à boucles, courbes parallèles exactes

### v0.57.0 — espacer, même taille, README

### v0.58.0 — Décaler exact

### v0.59.0 — Mode Point complété

### v0.60.0 — fuzz géométrique, moteur natif sous délai, colonnes, miroir sur axe

### v0.61.0 — raccordement

### v0.62.0 — marqueur, cadre englobant

### v0.63.0 — boucles du moteur natif corrigées à la source

### v0.64.0 — dessin symétrique

### v0.65.0 — fiche de validation, README

### v0.66.0 — ruban compact

### v0.67.0 — icônes en thème sombre

### v0.68.0 — feuille de style en thème sombre

### v0.69.0 — décomposer, supprimer des contours

### v0.70.0 — Aide > Nouveautés

### v0.71.0 — boutons « Annuler » en français

### v0.72.0 — Vérifier signale les petites boucles

### v0.73.0 — contour du trait exact

### v0.74.0 — décalages exacts partout

### v0.75.0 — objets masqués jamais exportés en VND

### v0.76.0 — chercher une commande (Ctrl+K)

### v0.77.0 — gros dessins

### v0.78.0 — délai du moteur natif proportionnel

### v0.79.0 — ombrage pleine plus rapide

### v0.80.0 — mode portable

### v0.81.0 — copier-coller-déplacer, glisser avec maintien

### v0.82.0 — BAT réglable avec aperçu

### v0.83.0 — VND : polices et en-tête

### v0.84.0 — VND relus en entier et réécrits à l'identique (solides 3D, cotes radiales)

### v0.85.0 — mode sombre, calques en onglets

### v0.86.0 — Ctrl+flèche fixe le pas des flèches

### v0.87.0 — FAO — outils, opérations, parcours, TypeEdit

### v0.88.0 — post-processeurs (G-code, ISO d'après fiche .MAH, Cielle, DXF)

### v0.89.0 — parcours 2,5D et 3D

### v0.90.0 — devis des gravures (passé dans un plugin en 0.95)

### v0.91.0 — bases d'outils TypeEdit (.Dbt)

### v0.92.0 — simulation de l'usinage

### v0.93.0 — avances et régimes des parcours TypeEdit

### v0.94.0 — raccourcis TypeEdit, palette FAO à gauche, BAT de la sélection, VND + compagnon

### v0.95.0 — logiciel libre (MIT ou Apache-2.0), plugins

- VectorDrive devient un logiciel libre, sous double licence MIT ou Apache-2.0.
- Plugins : un atelier ajoute ses outils, ses stratégies, ses gabarits, ses post-processeurs
  et ses raccourcis sans toucher au programme (voir docs/ARCHITECTURE.md).
- Raccourcis : ceux du TypeEdit installé sur le poste sont repris d'office.
- Ctrl+flèche demande le pas de déplacement des flèches.
### v0.96.0 — prêt à publier

- Licence : MIT ou Apache-2.0, copyright RomDuch, with Claude.
- Nouveautés (ce journal) séparées du journal de développement.
- Tests sur fichiers réels : corpus désigné par des clés, hors dépôt (`tests/corpus.py`).
- Dépôt public tiré du dépôt de travail par `outils/exporter_public.py`.

### v0.97.0 — bibliothèque d'outils, options F10, BAT 1:1 coté, logiciels encastrés

- **Bibliothèque d'outils** (FAO > Bibliothèque d'outils) : vos outils dans un `tools.json`, fiche complète
  (avances, régimes, cotes du fabricant D1…L3, catalogue, prix), silhouette, **dessins DXF et STEP**
  générés depuis les cotes, recherche.
- **Catalogues en ligne** : 25 fabricants, revendeurs et plateformes (DATRON, Sandvik Coromant,
  Kennametal, Walter, ISCAR, Seco, Mitsubishi, Gühring, EMUGE-FRANKEN, OSG, YG-1, Dormer Pramet, MAPAL,
  CERATIZIT, FRAISA, KYOCERA SGS, Harvey Tool, ZECHA, Mikron, Magafor, Gravotech, Onsrud, Amana,
  Hoffmann, ToolsUnited, MachiningCloud) : site et recherche d'une référence.
- **Import / export** : tools.json de NeoDrive, bases TypeEdit `.Dbt` en mode de compatibilité (ce qui
  se perd est signalé), CSV, données fabricant ISO 13399 / GTC (expérimental).
- **Options (F10)** en 8 onglets, une cinquantaine d'options toutes appliquées, dont « Respecter les
  proportions » cochée ou non par défaut.
- **BAT** : la pièce à **1:1 cotée** ; si elle fait moins de 30 mm (réglable) ou sur demande, une vue
  **agrandie** à côté ; si elle ne tient pas, une **réduction** normalisée.
- **Onglets d'espace de travail** : un plugin peut encastrer un autre logiciel dans un onglet à côté du
  dessin (fenêtre rattachée, détachable).

### v0.98.0 — barre de progression et Annuler

- Tout calcul qui dure (parcours FAO, simulation, ouverture et import, décaler, booléens, rogner,
  arcs et segments, approximation, vectorisation, photo en points, imbrication, vérification du
  dessin, recherche de symboles, téléchargement d'une mise à jour) affiche une **barre de progression
  avec un bouton Annuler** ; l'interface reste vivante, le dessin n'est pas modifié tant que le calcul
  n'est pas fini, et Annuler le laisse tel quel.

### v0.99.0 — 30 thèmes, interface personnalisable

- **30 thèmes** (Vue > Affichage > Thème) : 5 clairs, 25 sombres. **TypeEdit** reprend l'interface de
  TypeEdit (ruban gris-bleu, légendes des groupes en bandeau, titres des panneaux bleu foncé, plan de
  travail blanc) avec les couleurs lues dans le TypeEdit installé sur le poste ; aussi TypeEdit
  classique (bleu) et TypeEdit sombre. Mode sombre : passe du thème clair préféré au thème sombre préféré ;
  « Suivre le système » suit Windows en direct.
- **Personnaliser l'interface** : choix sur aperçu, duplication d'un thème pour en régler chaque couleur
  (interface et plan de travail), import / export de fichiers de thème ; les plugins peuvent en ajouter.
- **F10 > Apparence** : couleur d'accent, couleurs du plan de travail (fond, page, plaque, grille,
  sélection, aperçu, accrochage), police et taille du texte de l'interface, densité, arrondi des boutons,
  taille des icônes du ruban, libellés, légendes des groupes, ruban réduit aux onglets (Ctrl+F1 ou
  double-clic sur un onglet).
- **Miroirs** : M = miroir vertical de TypeEdit (gauche-droite), Maj+M = miroir horizontal (haut-bas).

### v0.100.0 — plan de travail en 2D ou en 3D

- **Vue > Mode : 2D ou 3D.** En 3D, la pièce telle que l'usinage la laissera : d'après les **parcours FAO
  simulés** s'il y a des opérations actives, sinon d'après le **dessin** (chaque trait creusé à la largeur
  de son outil et à la profondeur de son opération, 0,3 mm à défaut ; objets remplis évidés, contours
  fermés aussi au choix). Plaque en volume, couleurs de matière (surface, gravure, poches profondes).
- Tourner (glisser), déplacer (clic droit), zoomer (molette), vues **Dessus, Face, Côté, Perspective**
  (double-clic : perspective), **relief exagéré** jusqu'à ×50, parcours d'outil affichés. Recalcul
  automatique quand le dessin change, avec barre de progression et Annuler.
- Sans OpenGL (bureau à distance…), une vue de dessus ombrée la remplace.

### v0.101.0 — CATIA, 3D XML, STL

- **3D XML** (export ouvert de CATIA et des logiciels Dassault) et **STL** s'ouvrent en **vue de dessus** :
  un calque par hauteur des faces tournées vers le haut (la plus haute d'abord) et la silhouette de la pièce,
  assemblages placés.
- **CATIA** (.CATPart, .CATProduct, .cgr) : format fermé que nul lecteur libre n'ouvre. VectorDrive l'ouvre
  par un **convertisseur en STEP** désigné dans F10 > Fichiers (celui de CATIA en mode batch, un
  convertisseur du commerce…) ; sans convertisseur, il indique quoi exporter depuis CATIA (STEP, 3D XML,
  STL ; DXF pour un .CATDrawing).

### v0.102.0 — encore plus proche de TypeEdit

- **Raccourcis** : une centaine de commandes de plus du ruban de TypeEdit reliées à leur équivalent
  (aligner à gauche / droite / haut / bas, même taille, tampon, braille, codes-barres, surface, décomposer,
  rogner, poinçonner, texte sur courbe…) : leurs raccourcis TypeEdit marchent dans VectorDrive.
- **Règle graduée et vernier** (CAD > Métiers) : pas, grands et moyens traits, numérotation, vernier de
  n divisions ; modifiable par double-clic.
- **Textes** : rechercher / remplacer (sélection ou tout le dessin), MAJUSCULES, minuscules, Majuscule Aux
  Mots.
- **Contours** : supprimer les points alignés ; contours presque ronds remplacés par des cercles exacts.
- **Dessin** : cercle par 3 points, flèche simple ou double.
- **Plaque** : coller la sélection au bord gauche, droit, haut ou bas de la plaque.
- **Vue** : zoom précédent, zoom plaque. **Edition** : vider l'historique.

### v0.103.0 — modèles d'usinage

- **Modèles d'usinage** (panneau FAO > réglage) : enregistrer les outils et opérations d'un dessin sous un
  nom, puis les appliquer d'un clic à un autre — sur les couleurs prévues, celles de la sélection, du calque
  actif ou toutes ; outils retrouvés dans le réglage du dessin ou ajoutés. Les plugins peuvent en fournir.
- Édition de l'atelier : ses gammes de gravure et ébavurages, ses recettes laser en modèles ;
  CAD > Atelier > **Montage** (DataMatrix et référence à chaque poste d'un montage).

### v0.104.0 — ruban personnalisé

- **Personnaliser le ruban** (Vue > Affichage) : « Mon onglet » réunit les commandes de votre choix, en
  groupes titrés, en grands ou petits boutons, en premier ou en dernier ; les onglets inutiles se masquent.
- **Zoom fenêtre** : glisser un rectangle pour le cadrer (un clic rapproche).
- **Déplacer…** : déplacer la sélection d'une distance donnée, ou en poser une copie.

### v0.105.0 — annulations nommées, tangentes, texte vertical

- **Défaire plusieurs… / Refaire plusieurs…** (Edition) : la liste des modifications, chacune nommée
  d'après sa commande ; on revient d'un coup jusqu'à celle choisie.
- **Tangentes** (CAD) : droites tangentes à deux cercles (externes, internes, toutes) ou leur
  **enveloppe** (courroie, trou oblong).
- **Texte vertical** : lettres les unes sous les autres, et retour.
- **Alignements extérieurs** : placer les objets contre le premier sélectionné, à gauche, à droite, dessus
  ou dessous.

### v0.106.0 — modèles de dessin, réglages d'un poste à l'autre

- **Nouveau d'après un modèle… / Enregistrer comme modèle…** (Fichier) : un dessin de départ (plaque,
  cartouche, repères, textes à compléter) gardé sous un nom ; les plugins peuvent en fournir.
- **Exporter / importer les réglages** (Modifier > Configuration) : options, thème, raccourcis, ruban
  personnalisé… dans un fichier, pour retrouver sa configuration sur un autre poste.
- Encore des commandes TypeEdit reliées à leur équivalent (inverser le sens, homothétie, couper un contour,
  zoom fenêtre, quitter…).

### v0.107.0 — mise en forme des textes

- Onglet **Mise en forme**, qui paraît quand des textes sont sélectionnés (comme la barre de mise en forme
  de TypeEdit) : police, hauteur, largeur des lettres, interlettrage, interligne, alignement gauche /
  centré / droite, casse, texte vertical, rechercher / remplacer — appliqués à tous les textes sélectionnés
  d'un coup, remis en page à la même place.
- Ruban : les légendes des groupes ne sont plus coupées par la barre de défilement.

### v0.108.0 — traitement par lots

- **Traitement par lots…** (Fichier > Import / export) : convertir d'un coup des dessins ou des dossiers
  entiers (VND en DXF, PDF, SVG…), arborescence gardée, BAT PDF de chacun au choix ; barre de progression,
  Annuler, compte rendu (fichiers abîmés signalés sans arrêter le lot).
- Ruban : « Récents » en petit bouton, aligné sur ses voisins.

### v0.109.0 — rosaces et notes

- **Symétrie cyclique** (CAD > Création) : chaque forme dessinée est répétée en rosace autour du centre de
  la plaque (nombre de copies réglable) ; **symétrie centrale** (demi-tour).
- **Notes** (post-it) : une consigne pour l'atelier posée sur le dessin, jamais usinée ni exportée ;
  double-clic pour la modifier (vide : la supprimer) ; affichage au choix (Vue > Repères) ; gardées dans
  le VDZ et le compagnon d'un VND.

### v0.110.0 — temps d'usinage estimé

- **Temps d'usinage** (panneau FAO) estimé d'après les mouvements réels : avances de coupe et de plongée,
  rapides à la vitesse de la machine, accélérations (sans arrêt entre deux segments presque alignés),
  changements d'outil ; vitesse des rapides, accélération et durée d'un changement d'outil réglables
  (F10 > FAO). Durées affichées en heures, minutes, secondes.
- **Notes** : se déplacent à la souris (annulable).

### v0.111.0 — vérifier des dessins

- **Vérifier seulement** (Traitement par lots) : chaque dessin est lu sans rien écrire — format, objets,
  contours, remarques du lecteur, erreurs — avec un rapport CSV ; aussi en ligne de commande :
  `VectorDrive --verifier DOSSIER --out rapport.csv`. Pour contrôler d'un coup des fichiers venus d'un
  autre poste ou d'un client.
- Édition de l'atelier : devis possible d'après le temps d'usinage des parcours calculés.

### v0.112.0 — points par coordonnées

- **Point par coordonnées…** (CAD > Création) : donner le point suivant de l'outil de dessin par ses
  coordonnées, absolues ou relatives au point précédent ; deux points pour un rectangle, une ellipse ou un
  trait.
- Correctif : rectangles, ellipses et traits dessinés à la souris reçoivent eux aussi leur reflet en dessin
  symétrique, et leur rosace en symétrie cyclique.

### v0.113.0 — couteau

- **Couteau** (Opérations > Contours) : les formes fermées sélectionnées sont coupées en morceaux le long du
  trait sélectionné en dernier (droite, polyligne, courbe ou bord d'une autre forme), comme le couteau de
  TypeEdit ; les trous sont respectés, le trait reste.

### v0.114.0 — modèles et codes-barres TypeEdit

- Les **modèles TypeEdit** (.vnm) s'ouvrent, et ceux du TypeEdit installé sur le poste sont proposés dans
  « Nouveau d'après un modèle ».
- Les **codes-barres TypeEdit** d'un VND sont lus (la lecture s'y arrêtait) : affichés tels que TypeEdit les
  a dessinés, avec leurs données, et réécrits à l'identique.

### v0.115.0 — cadrans TypeEdit

- Les **cadrans et règles graduées TypeEdit** d'un VND ou d'un modèle sont lus (la lecture s'y arrêtait) :
  affichés tels que TypeEdit les a dessinés, réécrits à l'identique et déplacés comme le fait TypeEdit
  (dessin, courbe de base et centre suivent). Le modèle TypeEdit « front-panel-1 » s'ouvre en entier.

### v0.116.0 — codes-barres TypeEdit V15

- Les **codes-barres 1D et 2D de TypeEdit V15** (DataMatrix, QR…) d'un VND sont lus : affichés tels que
  TypeEdit les a dessinés, avec leurs données, et réécrits à l'identique ; un code déplacé est réécrit comme
  dessin. À confirmer sur des fichiers de l'atelier.
- Commandes TypeEdit « Décalage multiple » et « Effet ombrage » reliées (raccourcis TypeEdit, Mon onglet).

### v0.117.0 — braille TypeEdit

- Les **textes braille TypeEdit** d'un VND sont lus : points affichés tels que TypeEdit les a dessinés, texte
  conservé, réécrits à l'identique et déplacés comme le fait TypeEdit. À confirmer sur des fichiers de
  l'atelier.

### v0.118.0 — thème TypeEdit 13

- Nouveau thème **TypeEdit 13** : les couleurs de TypeEdit V13 (ruban bleu-gris, bandeaux des groupes et
  onglet courant bleus, règles claires, plaque blanche bordée de noir), lues dans son script de ruban et
  vérifiées sur son écran ; si TypeEdit V13 est installé, ses couleurs sont prises sur le poste. Il remplace
  « TypeEdit classique (bleu) » (un réglage qui le désignait passe à TypeEdit 13).

### v0.119.0 — compatibilité TypeEdit 13

- Les VND enregistrés par VectorDrive sont au format de **TypeEdit 13** (version de l'atelier), y compris
  ceux qui viennent d'un GVT de TypeEdit 14 ou 15 : versions de classes et en-têtes d'objets de la V13 ; un
  VND plus récent que la V13 est réécrit au format V13 depuis le modèle. Un contrôle signale ce qui ne serait
  pas lisible par la V13.
- Vérification de dessins (`--verifier`) : nouvelle colonne **TypeEdit 13** (le fichier s'ouvre-t-il tel quel
  dans la V13 ; un GVT est signalé, à enregistrer en VND).
- Messages d'enregistrement plus justes : un objet TypeEdit simplement déplacé mais non corrigible sans
  risque (code-barres…) n'est plus annoncé « tourné ou mis à l'échelle ».

### v0.120.0 — variables TypeEdit, validé dans TypeEdit 13

- Les **variables** d'un document TypeEdit (séries, noms…) sont lues : les réglages du document (plaque,
  outils, machine) sont gardés quand on modifie un dessin qui en contient ; auparavant ils étaient remplacés
  par ceux du modèle.
- Validation dans **TypeEdit 13** : 17 VND écrits par VectorDrive sur 17 s'ouvrent et s'affichent comme
  prévu.

### v0.121.0 — ouvrir le dossier du programme

- Après **Post-traiter…**, le message de fin a un bouton **Ouvrir le dossier** : l'explorateur s'ouvre sur
  le dossier du programme machine, le fichier sélectionné. Le bouton **📂** du panneau FAO y ramène à tout
  moment (dernier programme ou parcours TypeEdit écrit ; son chemin en info-bulle).
- Traitement par lots : bouton **Ouvrir le dossier de sortie**.

### v0.122.0 — textes TypeEdit modifiables dans les VND (expérimental)

- Option **Enregistrement en VND : textes TypeEdit modifiables** (F10 > Fichiers, désactivée par défaut) :
  les textes d'une ligne en police TrueType sont écrits comme des textes TypeEdit, modifiables dans TypeEdit
  13 ; les autres (plusieurs lignes, polices Gravotech) restent en courbes. Vérifié dans TypeEdit 13 :
  TypeEdit refait la mise en page (texte environ 5 % plus étroit en Arial).
- Correction des textes vivants des **symboles** (même défaut : TypeEdit n'en chargeait pas le dessin).

### v0.123.0 — vrai mode 3D

- En **mode 3D**, un dessin ouvert depuis un **STEP** montre la pièce entière (ou tout l'assemblage) : toutes
  les faces ombrées, les arêtes, les couleurs du fichier, comme NeoDrive — et non plus seulement les calques de
  sa vue de dessus. Aussi pour les **STL** et **3D XML** (arêtes vives calculées). Le mode 2D garde la vue de
  dessus pour graver.
- Source du relief : « Modèle 3D du fichier » (choisi d'office en Automatique), « Dessin », « Parcours FAO ».
- Modèle lu une fois par fichier (barre de progression, Annuler) ; faces et arêtes envoyées en un seul bloc à
  la carte graphique ; sans OpenGL, les arêtes sont dessinées en perspective.

### v0.124.0 — performances

- **Ouverture** des VND plus rapide (fichiers de l'atelier : environ un quart de temps en moins), résultat
  identique (vérifié sur 359 795 contours et 4 600 textes).
- **Premier affichage** d'un gros dessin 3 à 4 fois plus rapide (arcs convertis pour l'écran sans recherche,
  au µm près).
- **Zoom à la molette** instantané sur les gros dessins : l'image se met à l'échelle tout de suite, le rendu
  net suit dès qu'on s'arrête.

### v0.125.0 — disposition du ruban de TypeEdit 13

- Le thème **TypeEdit 13** est maintenant un « mod » : en plus des couleurs, le ruban prend la **disposition de
  TypeEdit 13** — onglets Fichier, Edition, Vue, Modifier, TypeEdit, FAO, mêmes groupes, commandes dans le même
  ordre ; les boutons **Mode** (Formes géométriques, Texte, Mode Point) et **Opérations** (Manipulation,
  Alignement, Transformation, Effets spéciaux, Duplication, Outils métier, Mesures…) ouvrent leur onglet
  contextuel, avec **Retour**. La disposition est lue dans le TypeEdit 13 du poste (rien de Gravotech n'est
  copié). Les onglets de VectorDrive restent accessibles dans l'onglet **VectorDrive**.
- F10 > Apparence > **Disposition du ruban** : selon le thème, VectorDrive ou TypeEdit 13.

### v0.126.0 — barre d'accès rapide de TypeEdit 13

- Disposition TypeEdit 13 du ruban : la **barre d'accès rapide** de l'utilisateur (celle de son TypeEdit 13 :
  Nouveau, Ouvrir, Enregistrer, Annuler, zooms, sélection, Mode Point, Usinage, Logo, Combiner, Éclater, mesures,
  Décaler, Accrochage, Aligner, Miroir, Rectangle, Cercle…) au-dessus du ruban, comme dans TypeEdit.

### v0.127.0 — textes TypeEdit modifiables de plusieurs lignes

- Option « textes TypeEdit modifiables » (expérimental) : les textes de **plusieurs lignes** sont maintenant
  écrits en textes TypeEdit — TypeEdit 13 n'en affichait que la première ligne ; vérifié identique à un texte
  de TypeEdit. Seules les polices Gravotech restent en courbes.
- Correction : TypeEdit 13 rend ces textes à **la même largeur** que VectorDrive (les « 5 % plus étroit » de la
  0.122.0 étaient une erreur de mesure).

### v0.128.0 — textes TypeEdit modifiables : polices Gravotech

- Option « textes TypeEdit modifiables » : les textes en **polices Gravotech** (Vn Futura, MECA, polices GII…)
  sont aussi écrits en textes TypeEdit, vérifiés dans TypeEdit 13 à la même taille que dans VectorDrive. Un
  texte dont la police n'existe pas sur le poste reste en courbes (il partait en Arial sous un nom inconnu).

### v0.129.0 — enregistrement plus rapide

- **Enregistrement des VND** 2 à 8 fois plus rapide sur les gros dessins de l'atelier (s8 : 11,7 → 4,9 s sans
  changement de structure, 28,4 → 3,6 s après un ajout), fichiers écrits identiques à l'octet.

### v0.130.0 — vérification plus rapide, sauvegarde sans à-coups

- **Vérifier le dessin** (et `--verifier`) 2,3 fois plus rapide sur les gros dessins (6,3 → 2,7 s sur un VND de
  2 400 objets), mêmes remarques ; l'enregistrement des VND en profite aussi (−25 %).
- **Sauvegarde de récupération** en tâche de fond : l'interface ne se fige plus toutes les 3 minutes sur les gros
  dessins (2 s → moins de 25 ms).
- Gros dessins : les pauses du ramasse-miettes Python disparaissent après l'ouverture.

### v0.131.0 — Mode Point et vues de TypeEdit 13

- **Affiner** : un nouveau point au milieu de chaque segment, tracé inchangé (« Affiner la courbe » de TypeEdit).
- **En segment** / **En angle** (Mode Point, deux points d'un contour) : la portion entre eux devient une seule
  droite, ou un angle à l'intersection des tangentes ; Maj : l'autre portion d'un contour fermé.
- **Vues YZ et ZX** : la pièce en 3D vue strictement de côté ou de face.
- Disposition TypeEdit 13 : 10 boutons de plus reliés (271 sur 438), dont la base d'outils, les couleurs
  d'usinage et les réglages de vectorisation.

### v0.132.0 — redresser suivant un axe

- **Axe vertical / Axe horizontal** (onglet Modifier, Transformation ; « Aligner suivant un axe » de TypeEdit) :
  clic sur un point de pivot, puis sur un autre point ; la sélection tourne autour du pivot, de la plus petite
  rotation, pour que le second point soit à sa verticale (horizontale). Aperçu en pointillés, accrochage F3.
  Pratique pour redresser un dessin scanné ou importé de travers.

### v0.133.0 — déplacer un contour, aligner et centrer

- **Déplacer un contour** (Mode Point) : glisser un contour d'un objet sans le décombiner ; les autres contours
  ne bougent pas (Ctrl : à 45°).
- **Aligner et centrer** (Centres) : les centres alignés dans les deux sens d'un seul clic.

### v0.134.0 — projections de points

- **Projection verticale / horizontale / orthogonale** (Mode Point) : les points sélectionnés vont sur un repère
  cliqué ensuite — un guide ou un contour (le croisement le plus proche, ou le point le plus proche), comme dans
  TypeEdit. Les anciens boutons « projection » de la disposition TypeEdit alignaient les points entre eux.

### v0.135.0 — sélection par contact, NeoDrive dans son onglet

- **Rectangle de sélection tiré du bas vers le haut** : il sélectionne aussi les objets qu'il touche (un trait y entre
  ou le traverse ; un groupe est pris en entier). Tiré du haut vers le bas, il ne prend que ce qu'il contient, comme
  avant. Le rectangle « par contact » est vert, en tirets-points.
- **NeoDrive dans son onglet** : le bouton NeoDrive logeait l'écran d'accueil de NeoDrive au lieu de sa fenêtre — l'onglet
  restait vide et NeoDrive s'ouvrait derrière. La fenêtre logée est maintenant la vraie fenêtre principale ; si elle
  disparaît, l'onglet attend la suivante ; si NeoDrive est déjà ouvert ailleurs, l'onglet le dit.
- **DXF** : les cercles complets sont écrits en vrais cercles (CIRCLE) : centre et rayon exacts pour NeoDrive (trous à
  percer ou tarauder) et les autres logiciels.

### v0.136.0 — Mode Point en bascule, Devis à côté du BAT

- **P** (ou le bouton Mode Point) entre en Mode Point, puis en sort vers la sélection, comme la palette Point de
  TypeEdit.
- Un plugin peut placer un bouton juste après un bouton du ruban : le **Devis** de l'édition de l'atelier se range à
  côté du **BAT PDF** (Fichier > Import / export) ; dans la disposition TypeEdit 13, le bouton « Coût » de TypeEdit
  ouvre ce devis.

### v0.137.0 — boutons qui ne faisaient rien

- **Options (F10)**, **Raccourcis clavier**, **Centrer plaque**, **Simuler…** (panneau FAO), **Catalogues en ligne…**
  (bibliothèque d'outils), **Ajouter →** et **Nouveau groupe…** (ruban personnalisé) : ces commandes ne faisaient
  rien. Le bouton (ou la commande) transmettait un « faux » que la commande prenait pour un de ses réglages. Corrigé
  pour toutes les commandes, avec un contrôle automatique qui empêche ce défaut de revenir.
- **À propos** : plus de chemin de dossier ; « RomDuch with Claude — romduch@gmail.com ».

### v0.138.0 — parcours sur la sélection

- **FAO : Calculer sur** les couleurs (tout le dessin) ou **la sélection seulement** : en mode sélection, seuls les
  objets sélectionnés sont usinés (un groupe sélectionné vaut pour son contenu), chaque opération gardant ses
  couleurs. Le choix est gardé ; Simuler et Post-traiter suivent le même mode.
- Édition de l'atelier (plugin 1.4.0) : outils de gravure du devis cochables (oui / non / auto) avec leur taux horaire,
  outils et modèles de devis enregistrés, fenêtre du devis en trois colonnes.

### v0.139.0 — Mes outils en dossiers, dans le panneau FAO

- **Mes outils** (bibliothèque d'outils) : rangés en **dossiers** — chaque import (TypeEdit .Dbt, NeoDrive, CSV,
  fabricants…) devient un dossier distinct ; **Déplacer vers…**, **Renommer…**, **Fusionner…**, **Supprimer le
  dossier**. Un outil copié d'une autre bibliothèque va dans un dossier à son nom.
- **Panneau FAO** : les outils de Mes outils sont proposés dans le formulaire d'opération (par dossier) et par le
  bouton 📚 (Mes outils ▸ dossier ▸ outil) ; l'outil choisi est copié dans les outils du document. Une opération
  peut se créer sans outil dans le document.

### v0.140.0 — formulaires de parcours enregistrés, modèles TypeEdit, rampes, relief, formulaire en colonnes

- **Modèles d'opération** : « Enregistrer l'opération choisie comme modèle… » garde le formulaire rempli (et son
  outil) ; « Appliquer un modèle d'usinage » le réutilise sur d'autres formes — couleurs, ou **objets sélectionnés
  seulement**.
- **Modèles de parcours TypeEdit (.ttpl)** : import, export de l'opération choisie, et « Reprendre les modèles
  TypeEdit du poste » (dossiers PRESET de TypeEdit 13 et 15).
- **Rampes** : l'entrée en rampe sert aussi aux traits ouverts (descente en zigzag le long du trait) et aux anneaux
  des poches (plus de plongée verticale dans la matière) ; **angle de rampe** réglable par opération.
- **Finition sans le cadre** (gravure en relief) : « Finition : pas de passe sur le cadre » — la passe de finition
  ne fait que le tour des formes, pas le contour extérieur.
- **Formulaire d'opération et d'outil** : sections en colonnes (Opération, Où usiner, Profondeurs, Entrées et
  liaisons, Vitesses, Particulier), **schéma** de l'opération (vue de dessus du parcours, coupe avec passes et rampe)
  et silhouette de l'outil, champs propres à une autre stratégie masqués, taille ajustée à l'écran ; bibliothèque
  d'outils ajustée à l'écran.

### v0.141.0 — opérations de NeoDrive : trous, formes simples, surfaçage, instructions machine

- **Taraudage** (fraise à fileter) : au centre de chaque cercle, hélice du filetage M2 à M12 (pas ISO ou choisi,
  filet à droite ou à gauche, avalant du fond vers le haut ou en opposition).
- **Perçage à la fraise** : hélice descendante au Ø du trou (celui du cercle ou un Ø choisi), un tour au fond.
- **Ébavurage des trous** : l'outil conique plonge juste ce qu'il faut pour chanfreiner le bord (largeur réglable).
- Palette FAO : boutons Taraudage, Perçage fraise, Ébavurage trous ; formulaire : choix du filetage (pas et
  avant-trou affichés).
- **Surfaçage** : passes parallèles en aller-retour sur l'encombrement des objets choisis ou sur la plaque
  (débordement, angle des passes).
- **Instruction machine** (opération sans outil, dans l'ordre des opérations) : palpage Z, décalage d'origine,
  rotation et miroir du repère, message, retournement de la pièce, mesure de longueur d'outil, préchauffage de la
  broche, table à vide, bloc de programme tel quel ; formulaire selon l'instruction choisie.
- Formulaire d'opération : une stratégie n'affiche plus les champs propres aux autres (gravure : plus de pontets ni
  de débourrage).
- Édition de l'atelier (plugin 1.7.0) : le post Datron écrit ces opérations comme NeoDrive — trous en **cycles
  SimPl natifs** (Thread, DrillMilling, Drill), poches et détourages de cercles et de rectangles (CircleCavity,
  RectangleCavity, CircleFromMid, RectFromMid), surfaçage (RectangleFace, CircleFace), instructions
  (SurfaceMeasure, ShiftWcsInc, RotateWcs, MirrorWcs, StatusMessage, Dialog, MeasureToolLength, SpindleWarmup,
  Vacuum).

### v0.142.0 — palpages de NeoDrive, mesure d'orientation, repère local, compteur de pièces

- Nouvelles **instructions machine** : palpage d'un **coin**, d'une **arête**, d'un **rectangle** (brut), d'un
  **axe de symétrie**, d'une **forme en U** ; **mesure d'orientation** sur deux repères ronds (angle contrôlé,
  confirmation de l'opérateur au-delà d'un maximum) ; **repère local** (décalage, rotation, remise à zéro) ;
  **compteur de pièces** gardé par la machine (numéro de série avec préfixe et zéros).
- Formulaire : **Prendre sur la sélection** remplit la position du palpage depuis les objets sélectionnés (coin
  choisi, milieu, cotes du rectangle, largeur, centres et Ø de deux cercles) ; les réglages rarement changés sont
  rangés dans **Réglages avancés**, replié.
- Édition de l'atelier (plugin 1.8.0) : le post Datron écrit ces instructions comme NeoDrive (CornerMeasure,
  EdgeMeasureV2, RectangleMeasure, SymmetryAxisMeasure, UShapeMeasure, CircleMeasure, Shift/Rotate/ResetLcs,
  loadvalueof / savevalueof). À simuler avant tout usage sur la machine.

### v0.143.0 — laser : oscillation du faisceau, passages, remplissage tourné et croisé

- **Oscillation du faisceau** (marquage, découpe et gravure laser) : cercle, huit ou transverse, amplitude et pas ;
  la phase suit la longueur parcourue, les contours restent fermés. Un trait large et régulier en un seul passage.
- **Cadence du scanner** vérifiée : avertissement au-delà de 500 Hz, export Cielle **refusé** au-delà de 1 000 Hz
  (le miroir ne suivrait pas), avec la vitesse à ne pas dépasser.
- **Passages** répétés pour les opérations laser.
- Gravure laser : lignes **tournées à chaque passage**, **croisées** (+90° au même passage), remplissage **en
  retrait** du contour ; la passe de finition (contour) est proposée dans le formulaire.
- Formulaire d'opération : section **Laser**.

### v0.144.0 — coupon d'essai laser

- **Coupon d'essai laser** (FAO ▸ Réglage) : une grille de cases où un paramètre varie en X et un autre en Y
  (puissance, vitesse, fréquence, pas du remplissage, passages), les autres fixés ; valeurs gravées en tête des
  colonnes et des rangées (vitesse en m/min), titre ; valeurs arrondies pour être recopiées telles quelles.
- Chaque case a son opération (sur ses seuls objets) et, si la puissance ou la fréquence changent, sa copie de
  l'outil laser ; les étiquettes sont marquées à puissance réduite (25 % au plus), en un passage, remplies ou non.
- Les cases peuvent porter **le dessin sélectionné** au lieu d'un carré plein, pour juger le rendu réel.

### v0.145.0 — question à l'opérateur, appel d'un programme de la machine

- Instruction **Question à l'opérateur** (Oui / Non) : sur Non, les opérations qui suivent sont sautées, jusqu'à la
  question suivante ; parking facultatif avant la question.
- Instruction **Appel d'un programme de la machine** : un programme existant appelé tel quel à cet endroit
  (avertissement si le fichier n'est pas indiqué).
- Édition de l'atelier (plugin 1.9.0) : le post Datron écrit la question comme NeoDrive (programme qui rend la
  réponse, opérations suivantes dans un `if`), l'appel en `usermodule`, et importe `DialogUtilities` dès qu'un
  dialogue est écrit.

### v0.146.0 — filtre de sélection (F9)

- **Filtre de sélection** (Édition ▸ Sélection, **F9**, comme TypeEdit) : un bouton par nature d'objet — courbes
  fermées, courbes ouvertes, textes, textes en colonnes, images, codes à barres, cotations, cadrans et règles —
  avec leur nombre dans le dessin. Tant que la fenêtre est ouverte, seules les natures enfoncées se sélectionnent
  (clic, rectangle, Tout, Inverser) ; Tout / Aucun / Inverser les boutons, **Sélectionner** prend d'un coup tout ce
  qui passe le filtre. À l'ouverture rien n'est choisi ; à la fermeture le filtre s'arrête.
- Un groupe ordinaire passe le filtre si tout son contenu le passe ; un code, une cotation, un cadran ont leur
  propre nature. Commande TypeEdit reliée : `ID_DRAW_FILTER`.

### v0.147.0 — marqueterie

- **Marqueterie** (CAO ▸ Duplication, comme TypeEdit) : de courbes fermées ou de textes (sans les vectoriser), les
  formes **femelles** (logement) et **mâles** (pièce rapportée), chacune sur un plan neuf — le plan d'origine ne change
  pas. Angles arrondis (rentrants et saillants, pour l'emboîtement), décalage de chaque forme, miroir autour de
  l'axe X, couleur de chaque forme, imbrication des formes mâles sur la plaque.
- **Prédéfinis d'usinage** : trou conique ou cylindrique, borgne (femelle en poche) ou débouchant (femelle
  détourée par l'intérieur) ; la forme mâle est détourée par l'extérieur. Annuler retire les plans et les opérations.

### v0.148.0 — duplication homothétique sur une courbe

- **Duplication homothétique** (CAO ▸ Duplication, comme TypeEdit) : sélectionner l'objet de départ, l'objet de fin
  (même forme, autre taille), puis la courbe ; les copies passent de la taille de l'un à celle de l'autre le long
  de la courbe, la première centrée sur son départ. Orientées selon la courbe ou non ; **copies équidistantes** :
  l'écart entre deux copies est constant au lieu de la distance entre leurs centres.

### v0.149.0 — vérification avant l'écriture du programme

- Avant d'écrire le programme machine, un **récapitulatif** (comme TauDrive) : parcours, opérations, longueurs en
  avance et en rapide, durée estimée, changements d'outil, encombrement, outils employés — et ce qui mérite un
  regard, du plus grave au plus anodin : rien à usiner, opération sans parcours, parcours qui sort de la plaque
  (au-delà du rayon de l'outil), objets masqués, textes sans police, un même numéro d'outil pour des outils
  différents, laser à 0 %, avertissements du calcul et du post-processeur, opérations désactivées, travail long.
- Rien n'est bloqué : la décision reste à l'opérateur. Désactivable dans la fenêtre ou dans FAO ▸ Réglage.

### v0.150.0 — arc tangent à deux cercles

- **Arc tangent** (comme TypeEdit) : un arc du rayon choisi, tangent aux deux cercles sélectionnés — raccord à
  l'extérieur des deux (congé) ou englobant les deux ; les deux solutions sont tracées, d'un point de contact à
  l'autre par le plus court.

### v0.151.0 — textes variables

- **Textes variables** (comme TypeEdit) : dans un texte, `|Nom|` prend la valeur de la variable ; `|Date|` et
  `|Heure|`, suivies au besoin d'un format (`|Date dd/MM/yyyy|`, `|Heure HH:mm|`, codes de TypeEdit), la date et
  l'heure du moment.
- **Variables** (CAO ▸ Texte) : un tableau, une colonne par variable et une ligne par état ; ajouter, renommer,
  supprimer ; **séries** (départ, pas, nombre ou valeur finale ; numérique, alphabétique, alphanumérique ; chiffres
  constants ; texte avant et après ; aperçu) ; **import** d'un fichier de données (point-virgule ou tabulation,
  noms en première ligne ou non) ; **état affiché** sur le dessin.
- **Texte variable** : ajoute `|Nom|` au texte sélectionné, ou crée un texte variable au centre de la vue ; le
  modèle du texte est gardé, les valeurs changent avec l'état.

### v0.152.0 — production des états

- **Produire les états** (CAO ▸ Texte) : un exemplaire de la sélection (ou de tout le dessin) par ligne du tableau
  des variables — lignes choisies —, chacun groupé (« État n ») avec ses textes remplis, rangé sur la plaque de
  gauche à droite puis de haut en bas (plaques suivantes à droite), sur un plan neuf ; les originaux sont masqués
  (Tout afficher les remet). Badges, plaques numérotées, étiquettes en série.

### v0.153.0 — journal des exports

- **Journal des exports** (FAO ▸ Réglage, comme TauDrive) : à chaque écriture d'un programme, une entrée s'ajoute à
  `<programme>-journal.txt`, à côté — heure, fichiers, post-processeur, opérations avec leurs réglages (outil,
  profondeur, avance, puissance…), et **ce qui a changé depuis l'écriture précédente**. Texte ASCII, lisible
  partout ; un journal impossible à écrire ne fait jamais échouer le programme.

### v0.154.0 — texte machine (n° de série, date)

- Stratégie **Texte machine** (palette FAO) : un texte gravé par la commande numérique avec sa propre police, composé
  au moment de l'usinage — texte fixe, **variable** ajoutée (le compteur de pièces : un numéro de série par pièce),
  **date du jour** ; centre (repris de la sélection), hauteur, rotation, profondeur, double passe.
- Édition de l'atelier (plugin 1.10.0) : écrit par le post Datron comme NeoDrive (`Engrave::StandardTextEngrave`,
  modules `Engrave` et `DateTimeModule` importés au besoin) ; les autres post-processeurs l'ignorent, avec un
  avertissement.

### v0.155.0 — saisie de l'opérateur au lancement

- Instruction **Saisie de l'opérateur** : au lancement du programme, une fenêtre demande à l'opérateur des valeurs
  (position, avance, angle, nombre, quantité, texte, oui / non), une ligne par champ — libellé, type, défaut, unité,
  variable ; les valeurs vont dans des variables que reprend le **texte machine** (n° de commande gravé, par
  exemple). Type inconnu ou aucun champ : avertissement au calcul.
- Édition de l'atelier (plugin 1.11.0) : écrite comme les « Paramètres opérateur » de NeoDrive (`InputDialog`,
  variables déclarées en tête du module).

### v0.156.0 — épaisseur de trait au laser

- Marquage laser : **épaisseur du trait** par passages parallèles (comme TauDrive) — de part et d'autre du tracé, à
  l'écart choisi (80 % du faisceau par défaut), jusqu'à l'épaisseur voulue ; là où deux tracés sont plus proches que
  l'épaisseur, les passages qui se superposeraient sont retirés (pas deux fois l'énergie au même endroit).

### v0.157.0 — modes de sélection

- **Modes de sélection** (Édition ▸ Sélection, comme TypeEdit) : opérateur appliqué aux clics et au rectangle de
  sélection — standard (Ctrl : ajouter ou retirer), par zone (remplace), **ajout**, **désélection**, **garder**
  (intersection avec la sélection en cours) ; à la fermeture, retour à la sélection standard.
- **Classement de la sélection** : en rangées ou en colonnes, dans un sens ou en zig-zag, depuis le coin haut gauche,
  ou ordre inversé — l'ordre du dessin, donc celui de l'usinage (gravure de séries, plaques).

### v0.158.0 — sélection au lasso

- **Lasso** (Édition ▸ Sélection et fenêtre des modes de sélection, comme TypeEdit) : clics = lasso polygonal,
  glisser = lasso à main levée ; double-clic, Entrée ou fin du glissé : les objets que le lasso touche sont pris,
  selon l'opérateur de sélection (ajout, désélection, garder…) et le filtre F9 ; un objet sans tracé (image) l'est
  par son encombrement.

### v0.159.0 — textes sur arcs multiples

- **Textes sur arcs multiples** (CAO ▸ Texte, comme TypeEdit) : les textes sélectionnés, chacun sur un arc de même
  centre — rayon, angle (milieu du texte, 90° = en haut), sens horaire ou non, rotation d'ensemble, mêmes réglages
  pour toutes les lignes ; déformation **simple** (lettres entières tournées), **radiale** (le haut et le bas des
  lettres suivent l'arc) ou **inclinée** (les côtés vont vers le centre). Les textes restent modifiables.

### v0.160.0 — entrée et sortie tangentes de la découpe laser

- Découpe laser : **entrée et sortie tangentes** en quart de cercle (rayon au choix), comme l'amorçage de la découpe
  jet d'eau de TypeEdit : le faisceau perce dans la chute — dehors pour un détourage extérieur, dedans pour un
  intérieur — et rejoint le contour dans son sens ; chaque passage repart de l'entrée.

### v0.161.0 — ordre des contours

- L'affichage du **sens des contours** (Ctrl+7 ; TypeEdit : Ctrl+T) montre aussi le **rang** de chaque objet à son
  point de départ : celui de la sélection dans son ordre, sinon celui du dessin — l'ordre d'usinage, à vérifier après
  un classement de la sélection.

### v0.162.0 — palpage Z mémorisé

- Instruction **Palpage Z mémorisé** (série de pièces, comme NeoDrive) : la première pièce est palpée et la mesure
  gardée par la machine d'un lancement à l'autre ; sur les suivantes, elle est reprise sans repalper — sur question à
  l'opérateur, toujours, ou jamais ; « oublier en fin de programme » fait repalper la pièce suivante.
- Édition de l'atelier (plugin 1.12.0) : écrit comme NeoDrive (`MeasuringCommonValues`, `hassavedvalue`,
  `loadvalueof` / `savevalueof`, `SetWcs Z=…`, `deletesavedvalueof`).

### v0.163.0 — liste des caractères

- **Liste des caractères** (CAO ▸ Texte, comme le Rapido de TypeEdit) : les caractères d'une police — polices du
  système et polices Gravotech —, par blocs (Latin-1, ponctuation et monnaies, ™ № ½, flèches, mathématiques, ⌀…,
  usage privé des polices de symboles) ; double-clic ou Insérer : le caractère s'ajoute au texte sélectionné (à son
  modèle s'il est variable), sinon il est copié dans le presse-papiers.
- Le miroir du texte du Rapido de TypeEdit est relié au miroir gauche-droite (le texte reste un texte).

### v0.164.0 — texte déplacé sur sa courbe, courbe de révolution

- **Déplacer sur la courbe** (CAO ▸ Texte, comme TypeEdit) : un texte sur courbe ou en arc est placé à une distance
  du départ de sa courbe, ou décalé depuis sa position actuelle ; il reste un texte modifiable.
- **Courbe de révolution** (comme TypeEdit) : une courbe ouverte répétée N fois autour du centre de la plaque, dans le
  sens horaire ou non, mise bout à bout en une seule courbe fermée (rosaces, engrenages, festons).

### v0.165.0 — texture (courbes qui remplissent l'espace)

- **Texture** (comme TypeEdit, Effets spéciaux) : les contours fermés ou les textes sélectionnés remplis d'une courbe
  de **Hilbert**, **Peano**, **Moore**, **Sierpinski** ou **Lebesgue**, plus ou moins fine (itérations) ; les
  contours intérieurs (trous des lettres) restent vides ; « avec les bords » garde les contours. Un décor de gravure
  sur le trait, à usiner comme un tracé.

### v0.166.0 — stratégies de découpe

- **Stratégies de découpe** (FAO ▸ Découpe, comme TypeEdit) : géométries de découpe d'une plaque en pièces —
  **cercles en quinconce**, **octogones** jointifs, **parts de gâteau** (cercle extérieur découpé ou non),
  **rectangles** (contour avant, après ou sans), **triangles** (diagonales montantes ou descendantes), **rondelle** ;
  les traits entre pièces voisines sont communs (une seule passe), le contour à part, dans l'ordre d'usinage voulu.

### v0.167.0 — LED (enseignes lumineuses)

- **LED** (CAO ▸ Duplication, comme TypeEdit) : perçages des diodes d'une enseigne pour les contours ou les textes
  sélectionnés — **sur les contours** (écart entre axes compris entre un minimum et un maximum, ou un nombre par
  contour ; une diode à chaque angle ; décalage au début et à la fin des contours ouverts) ou **à l'intérieur** en
  grille (pas, angle ; seulement les diodes entières) ; les diodes qui se touchent sont écartées.

### v0.168.0 — espacement des textes

- **Espacement** des textes sélectionnés (CAO ▸ Texte, comme le Rapido de TypeEdit) : **chasse fixe** (chaque
  caractère au milieu d'une case de la largeur du plus large : des numéros de série qui s'alignent d'une plaque à
  l'autre), **proportionnel** (sans crénage), **typographique** (avec crénage, comme jusqu'ici).

### v0.169.0 — italique et souligné

- **Italique** et **souligné** des textes sélectionnés (CAO ▸ Texte, comme le Rapido de TypeEdit), en bascule :
  lettres penchées de 12° ; une barre sous chaque ligne, gravée comme les lettres. Le texte reste modifiable.

### v0.170.0 — aperçu des manipulations (F4)

- **Aperçu** (Édition ▸ Sélection, **F4**, comme TypeEdit) : pendant un déplacement, un redimensionnement ou une
  rotation, les objets sont dessinés entiers (par défaut) ou, aperçu coupé, réduits à leur rectangle englobant en
  pointillés — plus fluide sur les très gros dessins.

### v0.171.0 — calcul des parcours plus rapide sur les gros dessins

- L'enchaînement des contours au plus proche voisin passe par une grille (comme TauDrive) : même ordre, mais calculé
  en une fraction de seconde au lieu de plusieurs secondes pour des milliers de contours (longs textes, motifs).

### v0.172.0 — poches et détourages rapides sur les gros dessins

- La région usinée (règle pair-impair des contours fermés) se calcule par groupes de contours qui se touchent : même
  résultat, mais 3 000 petits contours passent de plus d'une minute et demie à environ une seconde (poches,
  détourages, gravure laser, V-carving).

### v0.173.0 — gravure laser rapide sur les gros dessins

- Les lignes du remplissage laser se calculent d'un seul balayage de tous les contours : mêmes lignes, mais
  3 000 petits contours passent de près d'une minute à environ deux secondes.

### v0.174.0 — poches et V-carving rapides sur les gros dessins

- Sur un dessin de nombreuses formes séparées, les retraits successifs (poches, V-carving, fonds plats, reste
  matière, remplissage laser rentré) se calculent forme par forme : mêmes parcours, nettement plus vite.

### v0.175.0 — enroulement sur cylindre et cône (3 axes)

- **Enroulement cylindrique** et **Enroulement conique** (FAO ▸ Parcours, comme TypeEdit) : le parcours d'une
  opération s'enroule sur une pièce couchée (axe selon X ou Y) — le dessin suit la circonférence, la profondeur est
  reprise à la verticale de la surface, l'outil restant vertical. Nouvelle section **Enroulement** dans la fiche de
  l'opération : rayon de la pièce, génératrice du dessus (Z = 0 sur le dessus), second rayon et longueur pour un cône.
- Prudence : les cycles machine sont remplacés par les mouvements enroulés ; au-delà de 60° depuis le dessus un
  avertissement, au-delà de 85°, au laser, avec un texte machine ou un réglage incomplet, rien n'est écrit. Parcours
  à simuler avant usinage.

### v0.176.0 — textes justifiés, petites majuscules, ligne de base

- **Justifié** (Mise en forme ▸ Alignement, et dans les fenêtres de texte) : chaque ligne s'étire à la largeur de la
  plus longue, l'écart réparti entre les lettres — comme « aligner en blocs » de TypeEdit.
- **Petites majuscules** (Casse) : les minuscules deviennent des capitales réduites, le texte restant modifiable.
- **Sur / Sous la ligne de base** : un texte peut pendre sous sa ligne de base (le haut des capitales sur la ligne).
- VND : un texte ainsi mis en forme (ou en italique, souligné, déformé en arc, en chasse fixe ou proportionnelle) est
  écrit en courbes, même avec l'option des textes TypeEdit modifiables — le paragraphe TypeEdit perdrait le style.

### v0.177.0 — longueur maximale des textes

- **Longueur max.** (Mise en forme ▸ Longueur, comme TypeEdit) : un texte plus long que la longueur donnée se
  resserre ; plus court, il reste tel quel. **Compression ligne** : chaque ligne trop longue resserrée seule ;
  **Compression paragraphe** : toutes du même facteur. La compression appliquée s'affiche. Pratique pour les
  plaques nominatives et les textes variables : chaque nom tient dans la place prévue.

### v0.178.0 — poches forme par forme

- Les poches d'un dessin de plusieurs formes (lettres d'un texte, découpes…) s'usinent forme par forme : toutes les
  passes d'une lettre, du centre vers le bord et sur toute la profondeur, avant la suivante, prise au plus près —
  comme NeoDrive et TypeEdit. Fini les allers-retours d'une lettre à l'autre à chaque anneau.

### v0.179.0 — V-carving forme par forme

- La gravure 2,5D à l'outil conique (V-carving) s'usine elle aussi forme par forme : toutes les passes d'une lettre
  (retraits et fond plat) avant la suivante, prise au plus près — beaucoup moins de remontées et de rapides.

### v0.180.0 — découpe 3D rapide sur les gros dessins

- La découpe 3D (chanfrein au cône) choisit la forme suivante au plus près sans les comparer toutes : même ordre,
  mais 3 000 petites formes passent de plus de deux minutes à quelques secondes.

### v0.181.0 — laser : graver plus grand que le champ, en morceaux

- Post-processeur **Cielle** : le champ de marquage (110 mm par défaut) se règle dans le panneau FAO, et chaque export
  prévient si le dessin en sort. **En morceaux** : un dessin plus grand se découpe en morceaux égaux (marge de 2 mm
  au bord du champ), un travail .CLJOB par morceau recentré, et un fichier de **consignes** dit à l'opérateur où
  poser la pièce puis de combien la pousser entre deux morceaux (serpentin, rien n'est gravé deux fois). **Raccords**
  : petits traits au milieu des frontières pour contrôler le recalage — comme TauDrive.

### v0.182.0 — la date du jour à l'usinage

- Les textes datés (**|Date|**, **|Heure|**, avec leur format) prennent la date du moment à chaque calcul des
  parcours et avant d'écrire le programme : une plaque préparée lundi et gravée mercredi porte la date de mercredi —
  comme TauDrive. Un pas d'annulation ; réglable dans le menu du panneau FAO (« Dates des textes mises au jour du
  calcul »). Les états déjà produits gardent la leur.

### v0.183.0 — fichiers récents et machines en commandes

- **Fichier récent 1 à 4** et **Machines…** deviennent des commandes (raccourcis, ruban personnel, disposition
  TypeEdit 13 : les boutons des fichiers récents et du réglage des machines de TypeEdit fonctionnent).

### v0.184.0 — fusionner les parcours du même outil

- **Fusionner les parcours** (FAO ▸ Parcours, et menu du panneau FAO, comme TypeEdit) : les opérations qui utilisent
  le même outil que celle choisie viennent à sa suite, dans leur ordre ; **Regrouper toutes les opérations par
  outil** fait de même pour chaque outil. Moins de changements d'outil (le nombre évité s'affiche) ; l'ordre
  d'usinage change : à vérifier (ébauche avant finition). Annulable.

### v0.185.0 — plaque codée

- **Plaque codée** (CAO ▸ Métiers) : sur les cadres d'une plaque type, le code (DataMatrix carré ou rectangulaire
  au plus grand, QR, Code 128…) remplit le plus grand, son texte lisible le suivant ; on part de la place disponible
  et le contenu s'y ajuste — comme TauDrive. Un double clic change la donnée : code et texte sont refaits ensemble,
  jamais en désaccord, là où la plaque a été déplacée.

### v0.186.0 — galbe (relief bombé)

- **Galbe** (CAO ▸ Métiers, comme le Galbe de TypeArt) : les formes fermées sélectionnées deviennent un relief bombé
  — hauteur selon la distance au bord : Z min. au bord, montée à l'angle de départ, Z max. à la distance max., angle
  d'arrivée au sommet (0° : plat) ; une forme plus étroite n'atteint pas Z max. Le galbe est posé en image de
  hauteurs (blanc au plus haut) : l'opération **Relief** l'usine, profondeur = Z max. (bas-relief), ou en creux avec
  « blanc en creux » (moule). Les lettres gardent leurs trous.

### v0.187.0 — convertir depuis l'explorateur Windows

- **Menu de l'explorateur** (Fichier ▸ Import / export) : ajoute « Convertir avec VectorDrive ▸ en DXF, en SVG, en
  PDF, en EPS » au clic droit des dessins (VND, DXF, SVG, PDF, AI, EPS, symboles…) dans l'explorateur Windows —
  conversion sans ouvrir l'application, à côté du fichier, sans jamais écraser un fichier existant (« nom (2).dxf »).
  Posé pour votre compte seulement (aucun droit d'administrateur), retiré d'un clic. Sous Windows 11 : « Afficher
  plus d'options ». Comme TauDrive.
- Ligne de commande : `--keep` garde un fichier existant lors d'une conversion.

### v0.188.0 — galbes combinés et lissage

- **Galbe** sur un galbe existant (sélectionné avec les nouvelles formes) : combinaison comme dans TypeArt —
  remplacer, ajouter, soustraire (creux sous le fond possibles), maximum, minimum, moyenne — dans la zone du nouveau
  galbe, ou seulement sur le galbe existant. La profondeur à usiner en Relief suit le résultat.
- **Lissage** (Métiers) : adoucit un galbe, en entier ou dans la zone des formes sélectionnées avec lui (nombre de
  passes).

### v0.189.0 — sécurité : enroulement et axe rotatif

- Un parcours enroulé sur cylindre ou cône pour une machine 3 axes n'est plus écrit avec une fiche machine TypeEdit
  qui enroule déjà par l'axe rotatif (Mset40) : il le serait deux fois. L'export est refusé, avec la raison.

### v0.190.0 — création de texture

- **Création de texture** (CAO ▸ Métiers, comme TypeEdit) : un motif — chevrons, vagues, écailles, briques,
  croisillons, zigzag, ou vos propres traits ouverts — répété par symétrie (translation, miroirs, demi-tour,
  quinconce), tourné au besoin, remplit les contours fermés ou les textes sélectionnés ; les trous restent vides.

### v0.191.0 — bloc de programme paramétré

- L'instruction **Bloc de programme** prend jusqu'à six paramètres : `{p1}` … `{p6}` dans ses lignes sont remplacés
  par leurs valeurs à l'écriture du programme — une fonction personnalisée réutilisable, comme dans NeoDrive.

### v0.192.0 — ajuster dans le cadre

- **Ajuster dans le cadre** (à côté de Rogner) : les objets sélectionnés sont mis à l'échelle et centrés dans le
  cadre sélectionné en dernier (marge au choix), proportions gardées, ou étirés pour le remplir — un logo dans
  la zone réservée d'une plaque, en un geste (TypeEdit : Découpe ▸ Redimensionner). Annulable.

### v0.193.0 — palettes de TypeEdit

- Les palettes de TypeEdit — **Formes géométriques**, **Effets spéciaux**, **Alignement**, **Transformation**,
  **TypeArt**, **Métiers** — s'ouvrent en menus sous la souris avec les commandes équivalentes de VectorDrive : les boutons
  de palette de la disposition TypeEdit 13 fonctionnent, et chaque palette peut aller dans un raccourci ou dans
  Mon onglet.

### v0.194.0 — reproduire la mise en forme

- **Reproduire la mise en forme** (Mise en forme ▸ Casse, comme TypeEdit) : police, hauteur, largeur, espacements,
  alignement et styles (italique, souligné, petites majuscules, ligne de base, longueur maximale) passent du
  premier texte sélectionné aux autres — ou, un seul texte choisi, aux textes cliqués ensuite. Annulable.

### v0.195.0 — projection parallèle sur une pièce STEP

- **Projection parallèle** (FAO ▸ Parcours, comme TypeEdit) : le parcours d'une opération est posé verticalement sur
  la surface d'une pièce STEP (« Pièce STEP » dans la section Enroulement) — gravure d'un bouton bombé, d'une pièce
  galbée, l'outil restant vertical, le dessus de la pièce à Z = 0. Rien n'est écrit si le parcours sort de la pièce
  ou si le STEP ne se lit pas. À simuler.

### v0.196.0 — enrouler le dessin (aperçu)

- **Enroulement cylindrique / conique du dessin** (palette Effets spéciaux, comme l'onglet CAO de TypeEdit) : une
  copie du dessin telle qu'on la verra de dessus sur la pièce couchée — pour juger de la lisibilité avant de graver
  avec l'enroulement des parcours. Les originaux restent.

### v0.197.0 — liste de validation sur machine

- `docs/validation_machine.md` : pour chaque fonction récente qui change ce que la machine reçoit (enroulement,
  projection, poches forme par forme, galbe, laser en morceaux, champ de marquage…), ce qu'il faut vérifier et
  comment — simulation, passage en l'air, pièce d'essai — avant la production.

### v0.198.0 — collisions du porte-outil

- Fiche d'outil : **dépassement hors pince** et **Ø de l'écrou de pince / porte-outil**. Renseignés, la
  **simulation** compare à chaque point le porte-outil (au-dessus de la pointe de ce dépassement) à la matière qui
  reste à ce moment — un écrou qui descend dans une poche étroite touche ses parois — et signale chaque collision
  (position, profondeur), comme NeoDrive. La **vérification avant écriture** prévient déjà quand un parcours
  descend plus bas que le dépassement de son outil.

### v0.199.0 — pince et écrou de la broche

- **Broche : pince et écrou…** (menu du panneau FAO) : longueur d'outil serrée dans la pince et Ø de l'écrou. Le
  dépassement d'un outil sans valeur propre s'en déduit, comme dans NeoDrive (longueur totale du catalogue moins
  la longueur serrée, jamais moins que la longueur utile + 1 mm), et l'écrou sert de porte-outil : les collisions
  se vérifient sans renseigner chaque outil.

### v0.200.0 — Mes outils en lot, outils de la bibliothèque dans les parcours

- **Bibliothèque d'outils** : **Importer…** prend plusieurs fichiers d'un coup (un dossier de Mes outils chacun) et
  **Importer un dossier…** lit un dossier et tous ses sous-dossiers (JSON VectorDrive ou NeoDrive, bases TypeEdit,
  CSV, données de fabricants) : Mes outils reprend l'arborescence du disque (« Datron/fraises »), les dossiers d'une
  base TypeEdit en sous-dossiers. Un dossier déjà présent est remplacé ou doublé, au choix ; un fichier illisible
  est signalé sans arrêter le lot. Le chemin du `tools.json` est affiché, et il peut être choisi (F10 > FAO).
- Les dossiers de Mes outils s'emboîtent (arbre de la bibliothèque, menu 📚 du panneau FAO) ; renommer ou
  supprimer un dossier suit ses sous-dossiers.
- **Créer un parcours** (palette FAO) : le formulaire propose Mes outils, et sans outil de la bonne nature dans le
  document, c'est celui de Mes outils qui est pris (copié dans le document) avant tout outil par défaut.
- Programmes machine et parcours TypeEdit : le dossier proposé est celui du dessin, sinon le dernier utilisé,
  sinon Documents — jamais le dossier de VectorDrive.

### v0.201.0 — ruban en familles, sans défilement

- Le ruban ne défile plus horizontalement : quand un onglet ne tient pas dans la largeur, ses groupes se replient
  en **familles** (de la droite vers la gauche, comme le ruban de TypeEdit 13) — un bouton par famille, avec
  l'icône de sa première commande ; **un clic sur la famille déroule sa barre** sous le bouton, refermée après la
  commande. Les petites familles reprennent leur place dès qu'il y en a. Vaut aussi pour la disposition TypeEdit 13.
- F10 > Apparence > **Groupes du ruban** : repliés quand la place manque (par défaut) ou toujours repliés.

### v0.202.0 — onglet Options, Options et Aide à droite

- L'onglet **Modifier** devient **Options** : un bouton par onglet de la fenêtre des options (Général, Apparence,
  Dessin, Affichage, Fichiers, FAO, BAT, Mises à jour, Plugins), qui l'ouvre sur cet onglet, à côté de la
  configuration (Options F10, raccourcis, réglages, plaque, outils). La fenêtre des options s'ouvre plus grande.
- **Options** et **Aide** se placent tout à droite de la fenêtre ; les autres onglets restent à gauche, **FAO** en
  dernier (les onglets ajoutés par un plugin, « Mon onglet » en fin et l'onglet de mise en forme des textes se
  placent avant lui).
- Disposition TypeEdit 13 : même ordre (l'onglet Modifier de TypeEdit devient Options, avec les mêmes boutons ;
  l'onglet VectorDrive avant FAO) ; le **BAT** se place à côté du **Coût** (devis) dans Fichier > Information.

### v0.203.0 — fenêtres sans défilement horizontal

- À l'ouverture, une fenêtre s'élargit (sans dépasser l'écran) tant qu'une de ses colonnes, listes ou tableaux
  devrait défiler horizontalement ; dans une fenêtre à volets, la place est d'abord prise aux volets voisins qui
  en ont de trop. Vaut pour toutes les fenêtres de VectorDrive, et pour celles des plugins qui le demandent.
- Panneaux **Calques** et **FAO** : colonnes à la largeur du panneau (noms raccourcis plutôt que défilement).
- **Bibliothèque d'outils** : colonnes ajustées, boutons sur deux lignes ; **Personnaliser le ruban** : cases des
  onglets sur plusieurs lignes (la fenêtre faisait plus de 2 600 pixels en disposition TypeEdit 13) et taille
  d'ouverture limitée à l'écran.

### v0.204.0 — onglets de dessins, session silencieuse

- **Plusieurs dessins à la fois**, dans des onglets en haut de la fenêtre, comme dans un navigateur : chacun garde
  son historique d'annulation, sa vue et ses parcours FAO. **Nouveau** (Ctrl+N, ou « + ») et **Ouvrir** (plusieurs
  fichiers d'un coup) ouvrent un onglet — l'onglet vide du démarrage est réutilisé ; Ctrl+F4 ferme l'onglet
  (un dessin modifié est proposé à l'enregistrement), Ctrl+F6 / Ctrl+Maj+F6 passent d'un onglet à l'autre, clic du
  milieu pour fermer, onglets déplaçables. Un dessin déjà ouvert est relu dans son onglet ; modifié, une copie
  fraîche s'ouvre à côté.
- **Une seule fenêtre** : un double-clic sur un dessin (ou un nouveau lancement) l'ouvre dans un onglet de la
  fenêtre déjà ouverte, qui passe devant. `--nouvelle-fenetre` : une fenêtre à part.
- **Session silencieuse** (F10 > Général, active par défaut) : VectorDrive se ferme **sans question** et rouvre tout
  au démarrage — onglets, dessins modifiés non enregistrés (ils reviennent « modifiés », à enregistrer quand vous
  le décidez : vos fichiers ne sont jamais écrits sans vous), vue, parcours FAO, onglet du ruban, place des
  panneaux et de la fenêtre. Gardée aussi toutes les quelques minutes : après un arrêt brutal, tout revient.

### v0.205.0 — FAO à la manière de TypeEdit : colonne des parcours, modèles

- **Colonne de gauche** (panneau FAO) : le bouton **Outils** (Mes outils, le tools.json en dossiers), « Usiner : la
  sélection / les couleurs » (**la sélection par défaut**), et les **parcours disponibles** rangés comme dans
  TypeEdit (usinage 2D, 2D-3D, 3D, laser, machine, favoris de la palette TypeEdit). Un clic sur un parcours ouvre
  son formulaire pour les **contours sélectionnés** (outil, profondeur, passes, Z de départ, et les réglages propres
  au parcours) ; sa validation **calcule ce seul parcours**, les autres restent affichés. Rien de sélectionné :
  VectorDrive le dit, au lieu d'usiner une couleur entière.
- **Modèles** : sous chaque parcours, ses modèles ; un clic ouvre le formulaire déjà rempli. Dans le formulaire :
  choisir un modèle, ou **Enregistrer comme modèle…** (réglages et outil). **Modèles TypeEdit…** importe les
  paramètres de parcours enregistrés dans le TypeEdit du poste (avec leurs dossiers : profondeur, passes, Z de
  départ, surépaisseur, côté, avalant, pontets) et ses .ttpl.
- Formulaire : **Z de départ** (dessus de la matière : tout le parcours en suit) et **un pontet tous les … mm**
  (écart entre pontets, comme TypeEdit).
- **Opérations et parcours calculés** dans le panneau de droite, ou dans une **fenêtre détachée** (⧉), au choix.

### v0.206.0 — voir et simuler les parcours en 2D et en 3D

- Parcours calculés : **Voir 2D** (sur le dessin) ou **3D** (les trajectoires au-dessus de la matière : plongées,
  rapides, profondeurs), **Simuler 2D** (image ombrée) ou **3D** (la matière enlevée) — boutons du panneau et
  groupe « Voir et simuler » de l'onglet FAO. La vue 3D et sa simulation reprennent les parcours du panneau (ceux
  qui sont cochés), sans tout recalculer ; puis Post-traiter écrit le programme.
- Disposition TypeEdit 13 : la simulation volumique ouvre la simulation 3D.

### v0.207.0 — post-processeurs et fichiers machine dans les plugins

- Le cœur ne contient plus **aucun post-processeur ni fichier machine** : G-code, ISO paramétré par une fiche
  machine, laser, DXF des parcours, et les programmes machine du dessin, en lecture comme en écriture, viennent
  des plugins. Sans plugin, les parcours se calculent, se voient et se simulent ; le panneau FAO dit qu'aucun
  post-processeur n'est là au lieu d'écrire un programme.
- API des plugins : `add_post_provider` (post-processeurs tirés des fichiers machine d'un dossier) et `add_format`
  (format de fichier, avec sa fenêtre de réglages à l'export et la vérification du dessin pour un programme
  machine). La conversion en ligne de commande et le contrôle de dossiers chargent les plugins.

### v0.208.0 — la fenêtre tient dans l'écran avec le panneau FAO

- Panneau FAO ouvert, la fenêtre principale dépassait la hauteur d'un écran de 1080 px (la liste des opérations et
  parcours imposait la sienne). Cette liste défile désormais en hauteur, et seulement pour ce qui dépasse : avec
  de la place, elle garde son aspect habituel ; rien n'y défile ni n'y est coupé en largeur. Idem en fenêtre
  détachée.

### v0.209.0 — fenêtres de dialogue libérées

- Chaque fenêtre de dialogue (formulaire de parcours, bibliothèque d'outils, options, BAT…) restait en mémoire
  après sa fermeture, avec tous ses éléments : une journée de travail en accumulait des milliers, et chaque
  changement de thème ou de disposition devenait plus lent. Elles sont désormais détruites une fois fermées.

### v0.210.0 — session rapide sur les gros dessins

- La sauvegarde silencieuse de la session (toutes les 3 minutes et à la fermeture) figeait l'interface plus
  d'une seconde sur un gros dessin dont les parcours étaient calculés (2 millions de mouvements : 1,6 s, puis
  4,5 s d'écriture ; 6 s à la fermeture). Les parcours sont désormais mis en forme en arrière-plan, sous une
  forme compacte (3,4 Mo au lieu de 12,4), et ne sont réécrits que s'ils ont été recalculés : plus de pause,
  fermeture en 1,5 s. Les sessions enregistrées par les versions précédentes sont relues.

### v0.211.0 — parcours affichés sans ralentir, même énormes

- Sur un gros dessin dont les parcours étaient affichés (2 millions de mouvements), chaque rafraîchissement du
  plan de travail prenait 24 s (2,7 s zoomé ×4) : déplacer ou zoomer devenait impossible. Au-delà de 200 000
  segments, les parcours sont tracés au trait fin : 0,3 s pour la vue entière, 0,07 s zoomé — le dessin seul
  en prend 0,1. Les parcours habituels gardent leur trait de 1,2 px.

### v0.212.0 — simulation d'usinage 5 × plus rapide

- La simulation d'enlèvement de matière imprime l'outil par lots de segments (même résultat au bit près) :
  536 000 mouvements simulés en 5,6 s au lieu de 27,6 ; 131 000 en 1,1 s au lieu de 4,9.
- Plugin BFM 1.15.2 : le post-processeur Datron écrit ses nombres deux fois plus vite (268 000 mouvements :
  5 s au lieu de 11), toujours au même octet que le script TypeEdit d'origine.

### v0.213.0 — grandes images

- Une image de plus de 8 200 px de côté (photo ou illustration en haute définition) était refusée : « image
  illisible ». Qt limite par défaut le décodage à 256 Mo ; la limite est levée, et au-delà de 50 millions de
  pixels l'image est réduite à l'ouverture (sa taille en mm reste celle de l'original ; une remarque le dit).
  Même chose pour les images des reliefs, demi-teintes et de la vectorisation. Quand une image ne se lit
  vraiment pas, le message donne la raison.

### v0.214.0 — textes des DXF

- Les textes d'un DXF (TEXT, MTEXT, attributs de blocs, textes des cotes) deviennent des **textes vivants** :
  police du style (celle du poste si elle existe, sinon Arial, et la substitution est dite), hauteur,
  rotation, alignement (les neuf points d'ancrage), facteur de largeur, inclinaison, textes ajustés entre
  deux points, paragraphes multilignes. Ils étaient jusqu'ici laissés de côté avec une remarque « texte à
  convertir » — un DXF d'atelier sur trois en contient.

### v0.215.0 — photos de téléphone redressées

- Une photo prise en portrait avec un téléphone arrivait couchée : l'orientation enregistrée dans la photo
  (EXIF) est désormais appliquée à l'ouverture — comme image du dessin, source d'un relief, d'une demi-teinte
  ou d'une vectorisation. Taille en mm et réduction des très grandes images suivent l'image redressée.

### v0.216.0 — textes des SVG

- Les textes d'un SVG (`<text>`, lignes en `<tspan>`) deviennent des **textes vivants** : position, corps
  (ramené en hauteur de capitales), police du poste ou Arial (la substitution est dite), ancrage début /
  milieu / fin, italique. Comme pour les DXF, ils étaient laissés de côté avec une remarque.

### v0.217.0 — textes des PDF

- Les textes d'un PDF (et d'un Illustrator compatible PDF) deviennent des **textes vivants** : chaîne, position,
  corps, rotation ; la police de base est remplacée par celle du poste (Helvetica → Arial, Times → Times New
  Roman…, gras et italique suivis), et la substitution est dite. Jusqu'ici une remarque signalait seulement
  « texte PDF non vectorisé ».

### v0.218.0 — textes gardés à l'export

- Un texte vivant qui n'avait encore jamais été affiché (dessin importé puis exporté aussitôt, conversion
  `--convert`, traitement par lots) disparaissait des fichiers DXF, SVG, PDF, EPS et VND écrits. Ses contours
  sont désormais calculés avant d'écrire.

### v0.219.0 — demandes de l'atelier du 20/10 (1)

- **C, H, V** : avec plusieurs objets sélectionnés, le premier est la référence et ne bouge pas ; C centre les
  autres sur lui, H aligne leurs centres sur sa ligne (même Y), V sur sa colonne (même X). La plaque ne sert de
  référence que pour un objet seul.
- **Ctrl+S** : si le fichier a été modifié sur le disque par un autre poste ou un autre logiciel depuis votre
  dernière lecture ou sauvegarde, VectorDrive le dit et propose Écraser, Enregistrer sous… ou Annuler — plus de
  modifications perdues à l'atelier.
- **Onglets de dessins** dans la rangée des onglets du ruban, à gauche de Fichier : la fenêtre retrouve la
  hauteur que prenait la rangée d'onglets.
- **Modèles de parcours** rangés en dossiers (les vôtres, ceux importés de TypeEdit) : la palette FAO garde
  leur arborescence dans un groupe « Modèles (dossiers) » au lieu de les répartir par type de parcours.
- **Cotes** : pendant la cotation, Tab change le type (alignée, horizontale, verticale), comme TypeEdit.
- **Clic droit** (sans glisser) dans un mode (cote, tracé, points…) : retour au mode sélection.

### v0.220.0 — champs de valeur

- Dans tous les champs de valeur (dimensions, formulaires FAO, options…), un **double-clic sélectionne toute la
  valeur** (et non la partie entière ou les décimales seules), et la **virgule, le point et le point du pavé
  numérique** sont tous acceptés comme séparateur décimal.

### v0.221.0 — Maj+E : exporter la sélection, avec des modèles

- **Exporter** (Maj+E dans la disposition TypeEdit, Ctrl+E sinon) ouvre une fenêtre : la sélection seule (ou
  tout le dessin), le format, ses réglages (textes vivants du VND, résolution, fond, marge et trait des
  images), et des **modèles d'export** à enregistrer et rappeler d'un clic (double-clic : exporter aussitôt).
  Les formats des plugins (programmes machine) y sont aussi. Les objets exportés gardent leur place.

### v0.222.0 — B : la bibliothèque de l'atelier

- Le panneau des symboles (touche **B** dans la disposition TypeEdit) s'ouvre sur la **bibliothèque** : le dossier
  `bibliotheque` à côté du programme (créé au premier lancement), où l'on range symboles TypeEdit (.smb) et
  dessins DXF ou VectorDrive (.vdz) ; un double-clic les pose au centre de la vue, le glisser-déposer les pose
  où l'on veut. Les DXF ont leur vignette (contours tracés).

### v0.223.0 — 3D avec transparence

- Vue 3D (dessin en relief, parcours calculés, simulation, modèle STEP) : un curseur **Transparence** rend la
  matière et le modèle translucides, les parcours et le dessin se voient au travers.

### v0.224.0 — onglets de dessins entre FAO et Options

- Les onglets de dessins se placent dans la rangée des onglets du ruban **entre FAO et Options**, pas avant
  Fichier.

### v0.225.0 — traductions et vérification des polices

- Traductions anglaises des nouveautés (export, bibliothèque, cotes, 3D).
- Vérification avant usinage : un texte dont la police manque est signalé (usiné avec la police de
  remplacement), même si son contour a été calculé.

### v0.226.0 — modèles de parcours TypeEdit avec leurs outils

- Import des modèles de parcours de TypeEdit : chaque fichier va dans son propre dossier
  (« TypeEdit 13 — Meca3 »), ses dossiers dessous, sans se mêler aux autres modèles.
- L'outil de chaque modèle est importé (numéro, nom, référence, fournisseur, géométrie) et affiché
  à côté du modèle ; une gamme garde ses outils d'ébauche et de finition.
- Modèles de TypeEdit 15 (chaînes Unicode) lus.
- Dossiers de modèles : ranger un modèle, renommer ou déplacer un dossier, le supprimer
  (clic droit dans la palette des parcours).

### v0.227.0 — import d'outils avec aperçu

- Importer des outils (fichiers ou dossier) montre d'abord ce qui sera importé : arborescence du
  fichier, silhouette et fiche de chaque outil.
- Doublons repérés et décochés d'office : outils déjà dans Mes outils, et outils répétés dans
  l'import même.
- Sélection multiple (un dossier coche tout son contenu), recherche, puis choix du dossier de
  rangement ; l'arborescence du fichier peut être gardée ou non.
- Une base d'outils TypeEdit importée seule garde ses dossiers.

### v0.228.0 — choix de l'outil par dossiers

- Le formulaire d'un parcours ne liste plus des centaines d'outils : seulement ceux du document,
  et une ligne « Choisir dans Mes outils (par dossiers)… ».
- Cette ligne ouvre l'arborescence des dossiers de Mes outils (nombre d'outils par dossier),
  avec recherche par nom, référence, fabricant, Ø ou numéro, et la silhouette de l'outil.
- Le dernier dossier utilisé s'ouvre de lui-même ; l'outil choisi est copié dans le document.

### v0.229.0 — calques en onglets : le calque regardé est le calque actif

- Mode onglets : un onglet par calque ; l'onglet choisi est le calque actif, et le seul visible.
- Case « Voir tous » : les autres calques restent visibles, le calque actif suit toujours l'onglet.
- Bouton « Calques » : liste des calques à cocher (visibles), une case pour tout cocher ou tout
  décocher ; un clic sur un nom rend ce calque actif.

### v0.230.0 — F3 : fenêtre des accrochages

- F3 ouvre (ou referme) la fenêtre des accrochages, comme dans TypeEdit : accrochage actif,
  points accrochés, choix rapides (tous, aucun), rayon d'attraction en pixels (gardé).
- Maj+F3 active ou coupe l'accrochage.
- Nouvel accrochage aux quadrants des cercles et des arcs (0°, 90°, 180°, 270°).

### v0.231.0 — Ctrl+1 à Ctrl+9 de TypeEdit, onglets 2.5D et 3D

- Ctrl+1 vue 2D, Ctrl+2 vue YZ, Ctrl+3 vue ZX, Ctrl+4 vue graveur, Ctrl+5 vue isométrique,
  Ctrl+6 3D dynamique, Ctrl+7 sens, Ctrl+8 aperçu gravure, Ctrl+9 remplissage — aussi dans le jeu
  de raccourcis de VectorDrive.
- Ruban de TypeEdit : l'onglet « TypeEdit » devient « 2.5D », l'onglet « TypeArt » devient « 3D »
  et apparaît, avec les vues 3D et l'usinage 3D de VectorDrive.

### v0.232.0 — B ouvre la bibliothèque

- B (jeu de raccourcis TypeEdit) ouvre la bibliothèque sur le dossier de l'atelier, déplié sur
  ses sous-dossiers, son contenu en vignettes ; ensuite, elle rouvre là où on en était.
- La bibliothèque de l'atelier reste en tête de l'arbre même quand d'autres dossiers ont été
  ajoutés. Le panneau s'appelle désormais « Bibliothèque ».

### v0.233.0 — Mode Point : sélection au rectangle, barre entière

- Mode Point : glisser depuis le vide (ou sur la forme) trace un rectangle qui sélectionne les
  points de la forme active (Maj : ajoute) ; « Tout sélectionner » prend tous ses points ;
  K arrondit les points choisis.
- Ruban : un long groupe (comme la barre Mode Point de TypeEdit, 30 commandes) passe en petits
  boutons sur trois rangées au lieu de se replier en un seul bouton.
- Ruban de TypeEdit : l'onglet TypeArt n'est plus pris pour un second onglet 2.5D.

### v0.234.0 — calque Trajectoires, en 2.5D et en 3D

- Les trajectoires calculées ont leur ligne « Trajectoires » dans le panneau des calques : sa case
  les montre ou les cache, sur le plan de travail comme dans la vue 3D. Ce n'est pas un calque du
  dessin : rien n'y est usiné ni exporté.
- En 2.5D, chaque trajectoire est teintée selon la profondeur : claire en surface, foncée au fond.
- En 3D, les trajectoires se dessinent aussi par-dessus une pièce STEP ouverte (le haut de la pièce
  est le Z = 0 de la FAO) ; la vue 3D se met à jour après chaque calcul.

### v0.235.0 — points d'intersection et leur suppression

- I (TypeEdit) ou « Intersections » : les points d'intersection de la sélection (sinon de tout le
  dessin) sont repérés sur le plan de travail, par nature — boucle d'un contour qui se recoupe,
  croisement entre contours d'un objet, entre objets, contours dessinés en double.
- La fenêtre les liste (un clic y amène la vue) et propose la méthode pour les supprimer :
  retirer les petites boucles (longueur choisie), normaliser, surface remplie, réunir les objets,
  garder le contour extérieur, couper aux intersections, supprimer les contours en double.
  Chaque méthode ne touche que les objets qu'elle concerne ; tout s'annule.
- Les simples contacts (sommets communs, traits qui se rejoignent bout à bout) ne sont pas comptés.

### v0.236.0 — formes paramétrées, éditables après coup

- Rectangles, ellipses, polygones, étoiles, spirales et flèches gardent leurs paramètres de
  construction : on les rouvre pour changer un paramètre, l'aperçu suit en direct.
- F2 avec un outil de forme : la forme par ses paramètres (au centre de la vue). F2 ou double-clic
  sur une forme posée : ses paramètres. Clic droit sur le bouton de l'outil : les paramètres de la
  forme sélectionnée, ou les réglages des prochaines formes de cet outil.
- Nouveaux paramètres : coins droits, arrondis, chanfreinés ou creux ; polygone par rayon aux
  sommets, aux côtés ou longueur de côté, sommets arrondis ; étoile à rayons libres, creux décalés,
  pointes arrondies ; spirale d'Archimède ou logarithmique ; flèche standard, orthogonale ou
  filaire, double, en harpon, ancrée à la base, au milieu ou à la pointe ; arc par sa corde.
- Déplacer, tourner, mettre à l'échelle ou retourner une forme garde ses paramètres ; l'étirer ou
  la retoucher en Mode Point en fait une courbe ordinaire.

### v0.237.0 — cotes : options de cotation, cotes angulaires et radiales

- L'outil Cote passe par Tab de la cote alignée à l'horizontale, la verticale, l'angulaire (premier
  point, sommet, second point, puis le rayon de l'arc) et la radiale (clic sur un cercle ou un arc,
  puis la position du texte ; rayon ou diamètre).
- Options de cotation : symbole de chaque extrémité (flèche pleine, ouverte, trait oblique,
  point, aucun) et sa taille ; ligne de cote entre les lignes d'attache, à l'extérieur ou absente ;
  lignes d'attache, leur débord et leur écart à l'objet ; police, hauteur, écart du texte (0 : dans
  la ligne, coupée), orientation, préfixe, suffixe, unité (mm, cm, m, pouces), décimales.
- Une cote se rouvre par double-clic pour en changer une option (aperçu en direct) ; clic droit
  sur le bouton Cote : les options des prochaines cotes. Déplacée ou tournée, elle reste une cote.

### v0.238.0 — marqueurs à dix aspects

- Le marqueur a dix aspects, comme dans TypeEdit (croix droite ou oblique, croix et cercle, cercle,
  cercle et point, carré, losange, croix et carré, cible, triangle) : clic droit sur l'outil
  Marqueur pour choisir celui des prochains ; un marqueur posé se rouvre par double-clic ou F2.

### v0.239.0 — vue 3D revue

- Barre de la vue 3D sur deux rangées : elle tient dans une fenêtre étroite.
- Projection orthogonale (sans perspective) ou perspective (O) ; vue « Graveur » ; « Tout voir » (F).
- Affichage ombré, ombré avec arêtes, ou filaire (arêtes et parcours seuls).
- Trièdre des axes X, Y, Z dans le coin de la vue.
- Plan de coupe horizontal : rien n'est montré au-dessus, pour voir l'intérieur d'une pièce STEP ou
  le fond d'une poche ; rapides des parcours affichables.
- Corrigé : décocher le calque Trajectoires, ou un calque dans la liste du mode onglets, pouvait
  fermer le programme.

### v0.240.0 — lecture de l'usinage pas à pas en 3D

- Sous la vue 3D, une barre de lecture suit l'usinage mouvement par mouvement : curseur, lecture
  et pause (Espace), pas à pas, début, fin, vitesse de ×1 à ×256.
- L'outil est dessiné à sa place (fraise ou cône), la suite des parcours est estompée, et le
  mouvement en cours s'affiche (avance ou rapide, X, Y, Z, opération).
- En simulation, la matière est enlevée au fur et à mesure (pendant la lecture, et à chaque arrêt
  du curseur).

### v0.241.0 — pièce STEP placée comme sur la machine

- « Placer la pièce 3D » (ruban, et bouton « Placer… » de la vue 3D) : face tournée vers l'outil
  (dessus, dessous — pièce retournée —, l'un des quatre côtés), rotation autour de Z, position
  (coordonnées du fichier, centrée sur la plaque, dans le coin de la plaque, centrée sur l'origine,
  ou décalage libre).
- Le même placement sert partout : la vue de dessus en 2D est relue pour la face choisie, le modèle
  3D, l'usinage de surface 3D et les trajectoires montrées sur la pièce suivent ; le reste du dessin
  (textes, gravures ajoutés) ne bouge pas. Le placement s'annule et se garde avec le dessin.

### v0.242.0 — traductions

- Traductions anglaises des nouveautés : formes paramétrées, cotes, intersections, accrochages,
  calques, import et choix d'outils, vue 3D, lecture de l'usinage, placement des pièces 3D.

### v0.243.0 — corrections

- Le panneau des calques n'est plus refait à chaque affichage des parcours quand il n'y en a pas
  (mise en page relancée pour rien).

### v0.244.0 — bibliothèque en sous-dossiers

- La bibliothèque montre aussi les symboles et dessins des sous-dossiers : une bibliothèque rangée
  en dossiers n'affiche plus une liste vide à la racine ; le sous-dossier est écrit au-dessus du nom.
- Les vignettes des dessins (DXF…) sont tracées en arrière-plan : la bibliothèque ne fige plus le
  programme sur de gros dessins.

### v0.245.0 — BAT : coloriage, nom libre

- Le BAT tient compte du coloriage : avec « Remplissage » coché à l'écran (Ctrl+9), les formes
  fermées sont remplies d'une teinte claire de leur outil (gris clair en noir et blanc) ; la case
  « Coloriage » de la fenêtre du BAT le règle.
- Le nom proposé pour le BAT ne remplace plus un BAT existant (« (2) », « (3) »…) ; si le fichier
  ne peut pas être remplacé (ouvert dans le lecteur PDF), le BAT est proposé sous un autre nom.

### v0.246.0 — origine du dessin, paramètres, lots depuis l'explorateur

- Point du pavé numérique accepté dans tous les champs de valeur, y compris quand le champ lui-même
  a la main (fenêtre de Ctrl+flèche, champs de la fenêtre F2…).
- Ctrl+flèche : la valeur validée déplace aussitôt la sélection dans le sens de la flèche, puis
  reste le pas des flèches suivantes (0 : retour au pas des options, sans déplacer).
- Origine du dessin : repère X / Y sur le plan de travail (Vue > Repères > Origine) ; un glisser
  depuis le coin des règles la place, un double-clic sur le coin la remet au zéro ; « Placer
  l'origine… » (valeurs, coin ou centre de la plaque, sélection). Les règles, la position F2, la
  saisie de coordonnées et la barre d'état se lisent depuis l'origine ; les fichiers écrits gardent
  le zéro du dessin. L'origine est gardée avec le dessin.
- Paramètres exportés / importés dans un seul fichier (.vdparam) : réglages, Mes outils, modèles
  d'usinage, modèles de dessin, thèmes, au choix. À l'import, les outils sont ajoutés sans doublon
  et tout ce qui est remplacé est d'abord sauvegardé ; les anciens exports .ini s'importent encore.
- Menu de l'explorateur : « Traitement par lots… » au clic droit des dessins (sous « Convertir avec
  VectorDrive ») et des dossiers ; les fichiers choisis arrivent dans la fenêtre du traitement par
  lots (déjà ouverte ou lancée). Le menu posé se remet à jour seul au lancement d'une nouvelle
  version.

### v0.247.0 — Mode Point : points en courbe et hors courbe

- Correction : en Mode Point, les points ne s'affichaient plus (depuis la v0.233.0), sauf pendant un
  rectangle de sélection.
- Mode Point : les points en courbe et les points hors courbe (points de contrôle) sont tous montrés,
  comme dans les logiciels de gravure : départ en gros carré, arrivée d'un contour ouvert en petit
  carré, point continu en rond, angle en carré, point hors courbe en petit rond relié à son point.
- Les points hors courbe se sélectionnent comme les autres (clic, Maj+clic, rectangle, Tout
  sélectionner) et se déplacent avec eux (glisser, flèches) ; Suppr les retire (le segment
  devient plus simple).
- « En courbe » / « Hors courbe » : un point hors courbe devient un point par où passe le tracé, et
  inversement. « En droite » s'applique aussi aux segments des points hors courbe sélectionnés.
- Double-clic sur un point : ses attributs — X, Y (depuis l'origine du dessin), en courbe / hors
  courbe, poids W du point de contrôle d'une conique.

### v0.248.0 — reliefs : dôme, extrudé, révolution, facette

- Cartes de hauteurs des reliefs en 16 bits : 65 536 niveaux au lieu de 256 (un relief de 10 mm
  n'a plus de marches de 0,04 mm à l'usinage). Les reliefs déjà enregistrés se relisent.
- Nouvel onglet Relief : création, mode de combinaison, retouches, usinage.
- Dôme sur des marqueurs : gaussien (cloche), sphérique ou Bézier quadratique (cloche de verre),
  diamètre et hauteur.
- Relief extrudé : l'intérieur des formes fermées décalé en Z (marche à flancs droits, en creux si
  le décalage est négatif).
- Relief de révolution : une courbe tournée autour d'un axe (deux marqueurs, ou une droite choisie
  avec elle).
- Facette : plan incliné passant par trois marqueurs de cotes données, dans les formes fermées.
- Mode de combinaison commun aux reliefs (remplacer, ajouter, soustraire, maximum, minimum,
  moyenne, limiter au relief existant), gardé d'une fois sur l'autre.

### v0.249.0 — reliefs : balayage

- Balayage d'un profil le long d'un chemin (onglet Relief) : choisir le chemin, puis le profil.
  - Balayage simple (cadres, moulures) : le profil part du chemin fermé, vers l'intérieur si le
    chemin tourne dans le sens trigonométrique, vers l'extérieur dans le sens horaire (ou côté
    imposé) ; coins aigus, chanfreinés ou arrondis.
  - Tube : le profil, centré sur le chemin (ouvert ou fermé), le suit des deux côtés.
  - Hauteur du profil réglable (compression).

### v0.250.0 — reliefs : retouches

- Retouches d'un relief (onglet Relief), sur tout le relief ou seulement dans les formes fermées
  sélectionnées avec lui :
  - recalage en Z (haut, milieu, bas ou cote donnée amenés à une hauteur) ;
  - ajustement dynamique (nouveau Z max., courbure du profil) ; ajuster au volume (Z min. / max.) ;
  - inverser le relief (bosses en creux) ; trancher entre deux cotes ;
  - rehausser les détails ; bas-relief (faible profondeur, détails gardés) ; remplir les trous ;
  - matrice / poinçon : la matrice (empreinte retournée, en creux, élargie d'un jeu) posée à côté
    du poinçon ;
  - adapter à un outil : ce que la fraise choisie peut réellement usiner (parois dépouillées par une
    fraise conique, détails trop fins comblés).

### v0.251.0 — reliefs : vue 3D, multicopies, perlage

- La vue 3D montre les reliefs du dessin (galbes, dômes, balayages…) tels que l'usinage Relief les
  laissera : sommet affleurant, fond à la profondeur du relief.
- Multicopie linéaire (lignes et colonnes), multicopie circulaire (autour d'un marqueur ou du
  centre) et perlage (le long d'une courbe, tourné selon elle) du relief d'une zone, à l'intérieur
  du relief, avec le mode de combinaison en cours.

### v0.252.0 — dessin technique

- Diviser une courbe en parts égales, ou la mesurer (un repère tous les n mm, depuis le début ou la
  fin) : des repères le long du tracé, au choix tournés selon la courbe.
- Allonger ou raccourcir un contour ouvert : de Δ, jusqu'à une longueur totale ou en pourcentage, au
  début, à la fin ou des deux côtés (prolongé dans la tangente, raccourci dans la courbe).
- Repères de centre des cercles et arcs : croix au centre, avec ou sans traits débordants.
- Propriétés de masse des formes fermées : aire, périmètre, centre de gravité (depuis l'origine du
  dessin), moments d'inertie, moment polaire, rayons de giration ; trous retranchés.

### v0.253.0 — déformations

- Déformations des formes (onglet Opérations) : zigzag (pointes ou vagues arrondies, amplitude et
  longueur d'onde ; les bouts d'un trait ouvert restent en place), rugosité (bord irrégulier, même
  résultat à chaque fois pour un même tirage), contracter / dilater, torsion.

### v0.254.0 — FAO : découpe sur ligne commune

- Détourage extérieur : option « Découpe sur ligne commune ». Des pièces voisines écartées d'un
  diamètre d'outil sont chacune détourées, et leur bord commun n'est coupé qu'une fois.
- Sans l'option, des pièces trop proches pour passer entre elles sont signalées : elles sont
  détourées ensemble, sans coupe entre elles.

### v0.255.0 — FAO : lettres prismatiques

- Nouvelle stratégie « Lettres prismatiques » (enseignes) : lettres en relief au profil triangulaire,
  arête au milieu, flancs à la pente de l'outil conique. Profondeur laissée à 0 : celle qui fait
  affleurer l'arête de la lettre la plus large ; la profondeur pour la plus étroite est indiquée.
  « Débordement » : passes latérales qui dégagent le fond autour des lettres.
- Les modèles TypeEdit « gravure prismatique » importés utilisent cette stratégie.

### v0.256.0 — export STL

- Exporter en STL (Fichier, onglet Relief) : les reliefs choisis, posés sur un socle, et les formes
  fermées choisies, extrudées d'une hauteur donnée (trous compris), en un maillage fermé pour
  l'impression 3D ou un autre logiciel de FAO ; les grands reliefs sont allégés au besoin.
- Les groupes Déformations et Dessin technique passent dans l'onglet CAD (l'onglet Opérations
  débordait sur un écran de 1 600 px).

### v0.257.0 — reliefs : textures

- Relief d'une image (photo, logo) : chaque gris devient une hauteur, du noir au blanc, entre deux
  cotes choisies, courbe des gris et lissage réglables.
- Texturing algorithmique : texture fractale (standard, focale, rayures, concentrique) sur le
  relief ou dans les formes fermées choisies.
- Tissage : fils entrelacés de deux nappes croisées (écart, largeur des fils, hauteur, angle).

### v0.258.0 — galbe : compression, profil dessiné

- Galbe : compression du profil, comme TypeEdit. Sans compression, le sommet est plat une fois le
  Z max. atteint. Sur la longueur, Z max. est atteint tout le long de l'arête, même dans les parties
  étroites. Proportionnelle : la hauteur suit la largeur locale.
- Galbe asymétrique : une courbe ouverte choisie avec les formes fermées sert de profil (abscisse :
  distance au bord, ordonnée : hauteur).
- Correction : une forme qui touche le bord de la carte (fond autour à 0 mm) n'était pas galbée
  de ce côté.

### v0.259.0 — FAO : passes variables, modèles TypeEdit plus fidèles

- Profondeurs des passes au choix (par exemple « 0,8 0,6 0,4 » : passes de plus en plus fines, la
  dernière répétée jusqu'au fond) ; vide : passes égales, comme avant.
- Modèles d'usinage TypeEdit importés : passes de profondeurs différentes, plongée angulaire (entrée
  en rampe et son angle) et finition (surépaisseur, sans le cadre) repris.

### v0.260.0 — FAO : entrées tangentes en détourage

- Détourage fraisé : entrée et sortie tangentes en quart de cercle, dans la chute (à l'extérieur
  pour un détourage extérieur, dans le trou pour un intérieur), à chaque passe et pour la passe de
  finition ; l'outil n'attaque plus le bord de la pièce en plongée.

### v0.261.0 — FAO : poche en balayage

- Poche : évidage au choix en passes concentriques ou en balayage (passes parallèles, comme le
  Balayage de TypeEdit). Angle de départ, optimisé (le long de la forme, moins de remontées) ou X
  et Y (passes croisées) ; aller-retour sans remonter, ou passes dans un seul sens (en opposition,
  en avalant) ; tour du contour avant ou après le balayage. Distance entre passes réglable en mm.
- Les modèles TypeEdit de balayage importés donnent ce balayage au lieu de passes concentriques.

### v0.262.0 — FAO : ordre de détourage sûr

- Détourage : les trous d'une pièce sont coupés avant son tour (avant, le tour pouvait passer
  d'abord et libérer la pièce avant ses trous). Option « Petites pièces d'abord », comme TypeEdit,
  pour usiner les petites pièces avant qu'elles ne bougent.

### v0.263.0 — FAO : outil conique en poche et en détourage

- Poche et détourage avec un outil conique (ou boule) : l'outil est décalé du rayon qui coupe
  vraiment à la profondeur demandée, et non plus de la moitié du diamètre de sa queue. Une gravure
  peu profonde à la fraise en V n'est plus refusée (« outil trop gros ») ni décalée de plusieurs
  millimètres.
- Contour respecté au choix en surface (bord du dessin en haut, par défaut) ou au fond (pointe
  sur le contour), comme TypeEdit ; repris des modèles TypeEdit importés.
- Poche à l'outil conique : passes assez serrées pour que le fond soit plat, milieu compris.

### v0.264.0 — FAO : mode de tracé

- Gravure sur le trait, traits ouverts en plusieurs passes : aller-retour (comme avant), aller
  simple (toujours dans le même sens) ou aller simple puis un retour à la dernière passe, comme
  TypeEdit ; repris des modèles TypeEdit de tracé (le plus souvent en aller simple).

### v0.265.0 — FAO : découpe au couteau

- Nouvelle stratégie « Découpe au couteau » (vinyle, carton…), comme le Vinyle de TypeEdit :
  - tracé : le couteau suit le contour ;
  - couteau asservi : il remonte et se réoriente à chaque angle vif ;
  - couteau flottant : le déport de la lame est compensé et l'outil pivote autour des angles.
- Nouveau type d'outil Couteau (déport de la lame = pointe). Les modèles TypeEdit Vinyle et Cutter
  importés utilisent cette stratégie.

### v0.266.0 — FAO : chanfrein des bords

- Nouvelle stratégie « Chanfrein des bords » : l'outil conique longe les bords des pièces (et de
  leurs trous) à la profondeur qui donne la largeur de chanfrein voulue sur le dessus. Les modèles
  TypeEdit « gamme chanfrein » importés l'utilisent.

### v0.267.0 — reliefs : SculptArt

- SculptArt (onglet Relief) : retoucher un relief au pinceau, à la souris — ajouter, creuser,
  lisser, aplanir, bruit ; rayon et force réglables (Pinceau…). Chaque coup de pinceau s'annule
  d'un coup.

### v0.268.0 — FAO : gammes TypeEdit

- Modèles d'usinage TypeEdit « gamme » (multi-outils) : ils donnaient une opération inconnue,
  sans parcours. Ils donnent maintenant une étape par outil : ébauche à la poche (balayage, angle,
  surépaisseur repris), reprise des restes pour un outil intermédiaire, finition 2,5D à l'outil
  conique — chacune avec ses passes, son recouvrement et sa profondeur.
- Une opération « gamme » d'un modèle importé avant cette version est calculée en finition, avec
  un avertissement (réimporter le modèle pour avoir l'ébauche).

### v0.269.0 — FAO : finition de gravure

- Gravure 2,5D : option « Finition : bords et tirés d'angle seulement », passe finale qui suit les
  bords et remonte dans les angles sans revider le fond, comme la Finition de TypeEdit. Cadre
  englobant ignoré au choix (gravure en relief).
- Les modèles TypeEdit « Finition » importés donnent cette finition, et non plus une finition de
  surface 3D sur pièce STEP.

### v0.270.0 — FAO : reliefs TypeArt à leur profondeur

- Usinage Relief d'un relief TypeArt (galbe, dôme, balayage…) : profondeur laissée à 0, le relief est
  usiné à sa propre profondeur (sommet affleurant).
- Les modèles TypeEdit d'usinage TypeArt sont importés (stratégie Relief).

### v0.271.0 — FAO : intaille en ligne médiane

- Gravure 2,5D en ligne médiane (intaille optimisée de TypeEdit) : la pointe de l'outil conique
  suit en une seule passe le milieu de chaque forme, en touchant les deux flancs. Sa profondeur suit
  la largeur locale (pleins et déliés) et il remonte dans les angles. Les zones trop larges pour
  l'outil sont signalées.
- Les modèles TypeEdit « Intaille » importés utilisent ce mode.

### v0.272.0 — modèles TypeEdit : sens d'usinage

- Modèles d'usinage TypeEdit importés : le sens d'usinage (en avalant / en opposition) est repris
  correctement. Les découpes « en opposition » étaient importées en avalant.
- Gravure 3D TypeEdit : pas entre les passes, sens et cadre ignoré repris.

### v0.273.0 — FAO : balayage texturé

- Poche en balayage : option Texturing, comme TypeEdit. Le fond est fait de coups de gouge de
  longueur, profondeur et chevauchement tirés entre des bornes (aspect sculpté à la main) ; un même
  tirage redonne la même texture. Repris des modèles TypeEdit de balayage texturé.

### v0.274.0 — Pathfinder

- Opérations > Booléens : diviser (toutes les pièces de formes qui se chevauchent, chacune à l'outil de
  la forme visible au-dessus), détourer (parties cachées supprimées), fusionner (puis pièces du
  même outil réunies), recadrer (la forme du dessus sert de cadre), soustraire l'arrière. L'ordre
  de superposition est celui du dessin, quel que soit l'ordre de sélection.

### v0.275.0 — gribouillis

- Gribouillis (CAD > Métiers) : remplir les formes fermées d'un zigzag continu, gravé d'un seul trait
  tant que la forme le permet (l'outil ne remonte pas d'une ligne à l'autre). Réglages : angle, écart,
  débord des pointes, variation au hasard (aspect fait main).

### v0.276.0 — aligner par points

- Aligner par points (Opérations > Transformation), comme la commande ALIGNER des logiciels de
  DAO : deux points source et leurs destinations déplacent et tournent la sélection (accrochage
  F3) ; Maj au dernier clic : mise à l'échelle aussi ; Entrée après la première paire : déplacement
  seul. Pratique pour caler un dessin sur un gabarit ou un montage.

### v0.277.0 — Mode Point sur plusieurs formes

- Mode Point (P) avec plusieurs formes choisies ou un groupe : les points de toutes les formes sont
  montrés, la première est active ; un clic sur un point d'une autre la rend active (avant, aucun
  point n'apparaissait).

### v0.278.0 — FAO : multicopie d'un parcours

- Multicopie d'un parcours, comme TypeEdit : colonnes × rangées, pas donné ou calculé (taille des
  objets + écart), en serpentin, l'outil remontant entre deux copies ; les cycles machine sont
  décalés aussi. Pour usiner plusieurs plaques identiques d'un coup sur un montage.

### v0.279.0 — thème TypeEdit : barre de texte

- Thème TypeEdit : les boutons de la barre de texte (italique, souligné, casse, sur ou sous la ligne
  de base, justification, interlignage, compression, table des caractères, reproduire la mise en
  forme, insérer une variable, miroir) font la commande correspondante de VectorDrive.

### v0.280.0 — SculptArt : pousser, attirer

- SculptArt : deux nouveaux pinceaux, « pousser » (la matière entraînée dans le sens du geste) et
  « attirer » (resserrée vers le centre du pinceau).

### v0.281.0 — reliefs : remplissage par texture

- Remplissage par texture (Relief > Textures), comme TypeEdit : un petit relief, le motif, est répété
  en pavage dans les formes fermées choisies, sur le relief choisi ou en nouveau relief.

### v0.282.0 — reliefs : texture raccordable

- Texture raccordable (Relief > Textures), comme TypeEdit : le relief est rendu raccordable, ses
  bords opposés se rejoignent sans couture une fois répété en pavage.

### v0.283.0 — FAO : fer à dorer gaufrant

- Nouvelle stratégie « Fer à dorer gaufrant », comme TypeEdit : les formes restent en relief et,
  autour, la matière descend suivant un demi-profil de galbe (largeur laissée au bord, angles de
  départ et d'arrivée, largeur maxi, profondeur) en passes 2D concentriques. Les modèles TypeEdit
  correspondants l'utilisent.

### v0.284.0 — Repérage d'accrochage

- Repérage d'accrochage (F11, onglet Accrochage), comme le repérage objet des logiciels de DAO :
  les points accrochés que l'on survole sont retenus (petites croix), puis le curseur s'accroche
  sur leurs verticales et horizontales, et à leurs croisements, avec des lignes de repérage en
  pointillé. Changer de mode oublie les points retenus.

### v0.285.0 — Couteau flottant à boucles

- Découpe au couteau : nouveau type « Couteau flottant à boucles », comme TypeEdit : à chaque
  angle vif l'outil dépasse le sommet, fait une boucle tangente hors de la matière et revient
  sur le côté suivant. Réglages de l'onglet Avancé de TypeEdit : angles latéraux minimum et
  maximum (aussi pour le couteau asservi), longueur minimale des côtés, distance d'entrée/sortie
  et rayon de la boucle, vérification des intersections (une boucle qui entrerait dans la
  matière ou toucherait le dessin est omise).

### v0.286.0 — Découpe : boucles aux angles, angles arrondis, décalage

- Détourage et découpe laser, nouvelle section « Boucles » comme l'onglet Boucles de TypeEdit :
  aux angles extérieurs de la pièce, l'outil prolonge l'arête, fait une boucle hors de la pièce
  et revient sur l'arête suivante — angles vifs et vitesse tenue. Angles minimum et maximum
  (orientés), longueur minimale des côtés, rayon et longueur de boucle ; « Vérifier les
  intersections » réduit ou omet les boucles qui toucheraient une pièce.
- Angles arrondis en plus de l'outil, et décalage supplémentaire du parcours (onglet FAO de la
  découpe TypeEdit). Les réglages de découpe TypeEdit sont repris.

### v0.287.0 — Balayage : surépaisseur du cassé d'angle

- Poche en balayage : surépaisseur propre au tour du contour (cassé d'angle), entre 0 et celle
  des hachures, comme le paramètre AllowanceSweep de TypeEdit (repris des réglages TypeEdit).

### v0.288.0 — Découpe en chaîne

- Détourage : option « Découpe en chaîne », comme TypeEdit : à chaque passe l'outil va d'une
  pièce à la suivante sans remonter — il longe la pièce faite jusqu'au point le plus proche de
  la suivante et la rejoint par un brin coupé dans la chute. Il remonte seulement si ce brin
  toucherait une pièce. Reprise des réglages de découpe TypeEdit.

### v0.289.0 — Accrochage au centre de gravité

- Nouveau mode d'accrochage « Centres de gravité » (F3), comme TypeEdit : le centre de gravité
  de la surface des contours fermés d'un objet, trous retranchés. Dans la fenêtre des
  accrochages, le ruban, les choix rapides et le repérage.

### v0.290.0 — Poche en spirale

- Poche concentrique : options « En spirale » (les passes successives d'une même forme
  deviennent une spirale continue, sans plongée entre elles ; les retraits à îlots restent en
  anneaux) et « En partant de l'extérieur », comme la gravure 2D de TypeEdit (reprises de ses
  réglages).

### v0.291.0 — Étirer

- Nouvel outil « Étirer » (Dessin > Transformation), comme ÉTIRER des logiciels de DAO : une
  fenêtre de capture, puis un point de base et sa destination ; les nœuds pris dans la fenêtre
  bougent (avec leurs poignées), les segments vers les autres s'allongent. Formes de la
  sélection, sinon toutes. Annulable ; accrochage F3 et repérage F11 utilisables.

### v0.292.0 — Contour de zone

- Nouvel outil « Contour de zone » (Dessin > Tronquer), comme CONTOUR des logiciels de DAO :
  un clic dans une zone fermée par des traits — ouverts ou fermés, de formes différentes, qui se
  croisent — crée la forme fermée de cette zone, ses îlots en trous (Maj : sans les îlots).
  Pratique pour préparer une poche ou un remplissage à partir de traits de construction.

### v0.293.0 — Concepteur de formes

- Nouvel outil « Concepteur de formes » (Opérations > Booléens), comme dans les logiciels de
  dessin vectoriel : sur des formes choisies qui se recouvrent, glisser à travers leurs pièces
  les réunit en une forme ; un clic isole une pièce ; avec Alt, les pièces touchées sont
  supprimées. Annulable.

### v0.294.0 — Balayage entre deux chemins

- Relief (TypeArt) : nouveau balayage « Entre deux chemins », comme TypeEdit : le profil est
  tendu, à chaque station, du premier chemin au second (chemins ouverts ou fermés, sens accordé
  automatiquement) ; avec un second profil, la section passe peu à peu de l'un à l'autre
  (morphing) ; hauteur gardée ou proportionnelle à l'écart des chemins.
- Les commandes Balayage simple / tube gardent leur type même si le dernier balayage était
  d'un autre type.

### v0.295.0 — Relief d'un modèle 3D

- Relief (TypeArt) : « Relief d'un modèle 3D », comme la transformation d'une surface en objet
  TypeArt de TypeEdit : une pièce STL, STEP ou 3D XML, vue de dessus, de dessous, de face, de
  dos ou de côté, devient un relief (bas de la pièce à Z = 0), en taille réelle ou ramenée à
  une dimension, à sa hauteur ou en bas-relief d'une hauteur donnée ; combinable avec le relief
  choisi selon le mode de combinaison.

### v0.296.0 — SculptArt : miroir

- SculptArt : réglage « Miroir » du pinceau, comme TypeEdit : chaque touche est reproduite
  autour du centre du relief par un axe horizontal, un axe vertical, deux axes perpendiculaires
  ou plusieurs axes (2 à 10, n secteurs tournés et reflétés ; un nombre impair n'a pas d'axe
  vertical).

### v0.297.0 — SculptArt : masque

- SculptArt : réglage « Masque » du pinceau, comme les masques de couleur de TypeEdit : les
  formes fermées sélectionnées avec le relief servent de pochoir — le pinceau ne touche que
  dedans (ou que dehors), le reste est protégé.

### v0.298.0 — Perçage : points percés et modes

- Perçage, comme le filtre de sélection et les modes de TypeEdit : points percés au choix
  (centres des cercles et marqueurs, marqueurs seuls, départ et/ou arrivée des traits, centre
  des contours fermés pour le braille) ; perçage en passes avec remontée au dégagement, avec un
  petit recul (brise-copeau) ou en une seule passe ; remontée en vitesse de travail ou rapide.
  Les marqueurs sont maintenant percés.

### v0.299.0 — Taraudage et filetage

- Taraudage à la fraise, comme le taraudage / filetage de TypeEdit : filetage extérieur (la
  fraise tourne autour d'une vis), angle de départ, entrée et sortie tout droit ou en arc de
  cercle tangent (distance d'entrée / sortie pour le filetage extérieur).

### v0.300.0 — Tri des petites pièces

- Détourage, « Petites pièces d'abord » : critère au choix comme TypeEdit — aire, périmètre ou
  cercle inscrit (les pièces étroites passent d'abord, même longues).

### v0.301.0 — Largeur variable

- Dessin > Contours : « Largeur variable », comme les profils de largeur des logiciels de dessin
  vectoriel : un trait devient une bande dont la largeur va de celle du départ à celle de
  l'arrivée, s'effile aux deux bouts ou ondule — pleins et déliés, feuilles, pointes à graver.

### v0.302.0 — Cotes en ordonnée et repères

- Outil Cote (Tab : type suivant), deux nouveaux types comme dans les logiciels de DAO :
  « Cote en ordonnée » — l'abscisse (trait vertical) ou l'ordonnée (trait horizontal) d'un point
  depuis l'origine du dessin, trait coudé si besoin ; « Repère » — flèche sur le point, trait
  jusqu'au coude, palier et texte demandé au dernier clic.

### v0.303.0 — Cotation en chaîne et depuis une ligne de base

- Outil Cote (Tab), comme dans les logiciels de DAO : « Cotation en chaîne » — chaque clic pose
  une cote qui part de l'arrivée de la précédente, sur la même ligne ; « Cotation depuis une
  ligne de base » — toutes partent du même point, sur des lignes décalées. On enchaîne sur la
  dernière cote posée ou sur la cote sélectionnée.

### v0.304.0 — Mesure de volume

- FAO > Parcours : « Mesure de volume », comme TypeEdit — volume des reliefs choisis (au-dessus
  de Z = 0, et creux), sinon volume de matière enlevé par les parcours cochés (simulation) et
  profondeur atteinte.
- Commandes TypeEdit 13 reliées en plus : balayage avancé (entre deux chemins), surface en
  TypeArt (relief d'un modèle 3D), barre d'enroulement, mesure de volume.

### v0.305.0 — Outil spécial

- FAO > Parcours : « Outil spécial », comme TypeEdit — un outil de forme créé à partir d'un
  profil dessiné (trait ouvert, de la pointe vers la queue) et de deux marqueurs sur son axe ;
  ajouté aux outils du réglage FAO (dossier Outils spéciaux). Son rayon de coupe suit le profil,
  et sa forme exacte sert à la compensation des reliefs et à la simulation.

### v0.306.0 — Plaque : marges et ajustement de la composition

- Plaque, comme la Surface active de TypeEdit : marges gauche, droite, bas et haut — la zone
  gravable est tracée en pointillé et la vérification avant gravure signale les objets posés
  dans les marges ; « Ajuster la composition à la nouvelle taille » (proportions gardées ou non)
  quand on change les dimensions de la plaque. Les marges sont enregistrées avec le dessin.

### v0.307.0 — Mise en page du texte

- Options > Configuration : « Mise en page du texte », comme l'assistant de la Surface active de
  TypeEdit — n lignes de texte centrées, réparties sur la plaque : volume du texte, marges du
  haut et du bas en interlignes, décalage vers le haut, marges gauche et droite ; hauteurs
  égales ou relatives. Chaque ligne garde la largeur disponible pour longueur maximale (elle se
  resserre si le texte saisi est trop long).

### v0.308.0 — Point zéro de la plaque

- Fenêtre Plaque : « Point zéro », comme la Surface active de TypeEdit — l'origine des
  coordonnées affichées (règles, position, saisie de points) placée à un coin de la plaque ou à
  son centre.

### v0.309.0 — Enveloppes : dix formes de plus

- Enveloppe (textes compris, re-modifiable) : arc inférieur, coquille vers le bas ou vers le
  haut, drapeau, poisson, montée, œil de poisson, gonfler, compresser et torsion, comme les
  déformations des logiciels de dessin vectoriel.

### v0.310.0 — Tableau

- Options > Configuration : « Tableau », comme TABLE des logiciels de DAO — grille de cellules et
  leurs textes pour les plaques signalétiques (une ligne par rangée, « ; » entre les cellules),
  largeurs de colonnes égales ou données, hauteur des rangées, cadre et traits intérieurs,
  alignement ; les textes trop longs se resserrent dans leur cellule. Posé au coin haut-gauche
  de la plaque, en un groupe.

### v0.311.0 — Projection locale

- FAO : « Projection locale », comme TypeEdit — le parcours de l'opération choisie est posé sur
  une pièce 3D (STEP, STL, 3D XML) le long d'une courbe guide tracée sur sa vue de dessus : le
  dessin suit la courbe, les longueurs sont mesurées sur la surface (pas d'étirement dans les
  pentes), l'écart à la courbe est pris sur la surface, la profondeur à la verticale (machine
  3 axes). Refus clair si le dessin dépasse la courbe ou la pièce.
- Traduction anglaise du libellé du contenu des tableaux corrigée.

### v0.312.0 — Gomme à boucles : séparer, encombrement

- Gomme à boucles, comme TypeEdit : les boucles peuvent être séparées du contour (gardées à part,
  refermées) au lieu d'être supprimées, et leur taille mesurée par leur longueur ou par leur
  encombrement (diagonale de leur boîte).

### v0.313.0 — Souris (F5)

- Utilisation de la souris (F5), comme TypeEdit : la molette zoome ou fait défiler la vue (Ctrl :
  zoom, Maj : défilement horizontal) ; le clic droit sans glisser peut zoomer, défaire la
  dernière action, poser l'outil courant ou geler la sélection (glisser reste un déplacement de
  la vue) ; un double-clic sur la molette montre tout le dessin.

### v0.314.0 — Combiner les reliefs

- Relief > Combinaison : « Combiner les reliefs », comme TypeEdit — les reliefs choisis sont
  collés dans le premier (le relief courant) selon le mode de combinaison (ajouter, soustraire,
  maximum…), là où ils ont du relief ; la carte s'agrandit au besoin.
- Bouton « Souris » (F5) dans Options > Configuration.

### v0.315.0 — Parcours en dessin

- FAO > Parcours : « Parcours en dessin », comme l'édition de la géométrie du parcours de
  TypeEdit — les trajectoires cochées (centre de l'outil, arcs aplatis, passes de profondeur en
  un seul tracé) deviennent des traits dans un calque « Parcours », pour les retoucher, les
  mesurer ou les exporter.

### v0.316.0 — Éditer l'image

- « Éditer l'image », comme l'éditeur de bitmap de TypeEdit : l'image choisie s'ouvre dans
  l'éditeur d'images du poste ; à chaque enregistrement, elle est reprise dans le dessin à sa
  place (annulable).

### v0.317.0 — Échelle par référence

- Dessin > Transformation : « Échelle par référence », comme dans les logiciels de DAO — un point
  de base et la fin d'une longueur connue, puis la nouvelle longueur (cliquée depuis le point de
  base, ou saisie avec Entrée) : la sélection est mise à l'échelle autour du point de base.

### v0.318.0 — Raccord entre deux traits

- Dessin > Tronquer : « Raccord entre deux traits », comme le raccord des logiciels de DAO —
  deux traits droits cliqués du côté à garder sont prolongés ou coupés jusqu'à se rejoindre et
  raccordés par un arc tangent (rayon des congés), ou en coin vif (rayon 0, ou Maj).

### v0.319.0 — Chanfrein entre deux traits

- Dessin > Tronquer : « Chanfrein entre deux traits », comme dans les logiciels de DAO — deux
  traits droits prolongés ou coupés et reliés par un chanfrein de la taille réglée (Maj : coin
  vif).

### v0.320.0 — Repérage polaire

- Accrochage : « Repérage polaire » (F12), comme dans les logiciels de DAO — depuis le dernier
  point cliqué, le curseur s'accroche aux angles multiples du pas (15° par défaut, clic droit sur
  le bouton pour le changer), avec une ligne de repérage en pointillé.

### v0.321.0 — Rotation par référence

- Dessin > Transformation : « Rotation par référence », comme dans les logiciels de DAO — un
  centre, la direction d'un bord de l'objet, puis la direction voulue (cliquée, ou un angle
  saisi avec Entrée) : pour redresser un objet sur un bord quelconque.
- Icônes manquantes de quelques boutons (étirer, échelle par référence, courbe de révolution,
  diviser, mesurer, symétrie centrale) remplacées par des icônes existantes ; un essai vérifie
  désormais que chaque bouton a son icône.

### v0.322.0 — Gravure 2,5D : nombre de passes limité

- Gravure 2,5D : « Nombre de passes limité », comme TypeEdit — seules les n passes les plus proches
  du bord sont faites (reprise des bords, gravure en relief) ; repris des réglages TypeEdit.

### v0.323.0 — Nettoyer les superpositions

- Dessin > Contours : « Nettoyer les superpositions », comme dans les logiciels de DAO — les traits
  droits qui se recouvrent (un bord dessiné deux fois, des formes accolées) sont fusionnés pour
  n'être gravés qu'une fois ; les traits qui se prolongent sont joints, par outil.

### v0.324.0 — Cotation rapide

- Mesure : « Cotation rapide », comme dans les logiciels de DAO — les objets choisis sont cotés
  d'un coup : positions en X sous la sélection et en Y à sa gauche (centres des cercles, coins des
  autres objets), en chaîne ou depuis une ligne de base. Pratique pour les plans de perçage.

### v0.325.0 — Purger

- Mesure : « Purger », comme dans les logiciels de DAO — retire ce qui ne grave rien : formes et
  textes vides, groupes vides, calques vides (le calque actif reste). Annulable.

### v0.326.0 — Sonde de relief

- Relief > Combinaison : « Sonde de relief », comme les outils de mesure TypeArt — un clic sur un
  relief donne sa cote Z en ce point ; un second clic, le profil entre les deux points (cotes
  mini et maxi, pente la plus forte).

### v0.327.0 — Pièces 3D maillées plus rapides

- Les pièces 3D maillées (relief d'un modèle 3D, surface 3D d'une pièce STEP, projection
  parallèle et locale) se mettent en carte de hauteurs environ 14 fois plus vite (une demi-sphère
  de 160 000 facettes au pas de 0,1 mm : 10 s → 0,7 s), au résultat identique.

### v0.328.0 — Reliefs à la fraise plate plus rapides

- Usinage des reliefs et des surfaces 3D avec une fraise à bout plat : la compensation de l'outil
  est jusqu'à 40 fois plus rapide (même résultat).

### v0.329.0 — Copier avec point de base, coller au point

- « Copier avec point de base » (Ctrl+Maj+C) puis « Coller au point » (Ctrl+Maj+V), comme dans les
  logiciels de DAO : la copie se pose par son point de base au point cliqué — avec l'accrochage,
  pour placer exactement (sans point de base : son coin bas-gauche).

### v0.330.0 — Crayon : formes reconnues

- CAD > Création : « Crayon », comme l'outil Shaper des logiciels de dessin vectoriel — on dessine
  à main levée et le tracé devient le trait, le rectangle (droit ou à 45°), le cercle, l'ellipse
  ou le triangle esquissé ; sinon une courbe lissée (Maj au lâcher : courbe lissée seulement).

### v0.331.0 — Gomme

- Dessin > Tronquer : « Gomme », comme dans les logiciels de dessin vectoriel — glisser efface ce
  que couvre la gomme ronde : les formes fermées sont entamées (ou coupées en morceaux), les
  traits ouverts coupés ; [ et ] changent sa taille. Un passage = une annulation.

### v0.332.0 — Pinceau à aplat

- CAD > Création : « Pinceau à aplat », comme dans les logiciels de dessin vectoriel — glisser
  peint une surface pleine qui se fond avec les formes fermées de l'outil courant qu'elle touche
  (aplats à graver au laser ou à vider) ; [ et ] changent sa taille.

### v0.333.0 — Isoler

- « Isoler », comme dans les logiciels de DAO — seule la sélection reste visible, les autres
  objets sont masqués le temps du travail ; « Fin d'isolement » les réaffiche (les objets masqués
  avant restent masqués).

### v0.334.0 — Fiche de réglage

- FAO > Parcours : « Fiche de réglage » — une feuille d'atelier à imprimer (page web) : plaque et
  matière, encombrement du dessin, outils utilisés (numéro, type, diamètre, angle, broche),
  opérations dans l'ordre (stratégie, outil, profondeur, passe, surépaisseur, avance, temps
  estimé), temps total et changements d'outil, avertissements des parcours, vue de dessus des
  trajectoires.

### v0.335.0 — Motifs de hachures

- Hachures : motifs au choix comme dans les logiciels de DAO — traits parallèles, briques, traits
  pointillés, traits ondulés, nid d'abeille ; le pas donne l'échelle, l'angle les tourne, les
  trous restent vides.

### v0.336.0 — Oblong, anneau, secteur

- CAD > Création : trois formes paramétrées de plus, éditables ensuite comme les autres
  (double-clic) — oblong (boutonnière : longueur hors tout, largeur, angle), anneau (rayons
  extérieur et intérieur), secteur de couronne ou part de disque (rayons, angle de départ,
  ouverture). Elles suivent déplacements, rotations et miroirs.

### v0.337.0 — Engrenage

- CAD > Création : « Engrenage », forme paramétrée éditable — denture en développante de cercle
  (module, nombre de dents, angle de pression), alésage central au choix.

### v0.338.0 — Poche : optimisation des angles

- Poche concentrique : « Optimisation des angles », comme TypeEdit — avec un pas large, l'outil
  va chercher la matière restée dans les angles aigus (aller-retour sur la bissectrice, sans
  sortir de la zone permise). Repris des réglages TypeEdit.

### v0.339.0 — Découpe 3D : tirés d'angle

- Découpe 3D à l'outil conique : « Tirés d'angle », comme TypeEdit — dans les angles rentrants
  (côté chute), l'outil remonte le long de la bissectrice jusqu'à ce que le cône touche l'angle à
  la surface : l'arête du dessus reste vive. Les modèles TypeEdit « Découpe 3D » sont repris
  (option 3D, angle maximum).

### v0.340.0 — Découpe 3D : tiré d'angle au pied

- Découpe 3D : « Tiré d'angle au pied », comme TypeEdit — au pied des angles saillants de la pièce
  (dans la fourchette d'angles réglée), l'outil conique va jusqu'à l'angle vif : utile pour les
  poinçons, dont le pied donne l'angle du dessus de la pièce finale. Repris des réglages TypeEdit.

### v0.341.0 — Tri des contours manuel

- Opérations FAO : « Tri des contours », comme TypeEdit — automatique (le trajet le plus court,
  par défaut) ou manuel : les traits sont usinés dans l'ordre et le sens où ils ont été dessinés.

### v0.342.0 — Modèles TypeEdit : entrées tangentielles

- Import des modèles d'usinage TypeEdit : l'entrée et la sortie tangentielles des découpes sont
  reprises (avec le rayon de raccordement réglé dans TypeEdit).

### v0.343.0 — Modèles TypeEdit : surépaisseur supprimée à la dernière passe

- Import des modèles d'usinage TypeEdit : l'option « Supprimer sur la dernière passe » de la
  découpe devient une passe de finition qui enlève la surépaisseur.

### v0.344.0 — Modèles TypeEdit : gamme chanfrein

- Import des modèles d'usinage TypeEdit : la gamme « Chanfrein » donne ses trois étapes — chanfrein
  des bords à l'outil conique (largeur tirée de la hauteur et de la longueur du chanfrein), puis
  les découpes avec les outils suivants (profondeur, nombre de passes, côté, sens, pontets) — au
  lieu d'une seule opération.

### v0.345.0 — Reliefs : sens des passes

- Usinage des reliefs et des surfaces 3D : passes selon X, selon Y, ou croisées (toutes les
  passes selon X puis une finition selon Y à la dernière profondeur, qui efface les crêtes).

### v0.346.0 — Accrochages perpendiculaire et tangente

- Accrochage (F3) : modes « Perpendiculaire » et « Tangente », comme dans les logiciels de DAO —
  depuis le dernier point cliqué, le pied de la perpendiculaire sur un trait ou un cercle, et le
  point de tangence sur un cercle ou un arc.

### v0.347.0 — Courbe par points

- CAD > Création : « Courbe par points », comme la SPLINE par points de lissage des logiciels de
  DAO — chaque clic est un point par lequel passe une courbe lisse (sans angle) ; double-clic ou
  Entrée pour finir, clic sur le premier point pour la fermer.

### v0.348.0 — Accrochage prolongement

- Accrochage (F3) : mode « Prolongement », comme dans les logiciels de DAO — survoler le bout d'un
  trait droit le retient, puis le curseur s'accroche sur son prolongement (ligne de repérage en
  pointillé).

### v0.349.0 — Accrochage parallèle

- Accrochage (F3) : mode « Parallèle », comme dans les logiciels de DAO — survoler un trait droit
  retient sa direction, puis depuis le dernier point cliqué le curseur s'accroche sur la
  parallèle (ligne de repérage).

### v0.350.0 — Milieu de deux points, depuis un point

- Ruban Dessin › Accrochage : « Milieu de deux points » — pendant un outil, le prochain point
  est le milieu de deux points cliqués (accrochés) ; « Depuis un point » — un point de base
  cliqué puis un décalage X ; Y saisi, comme dans les logiciels de DAO.

### v0.351.0 — Détourage trochoïdal

- Détourage : option « Trochoïdal » — l'outil avance en boucles le long du contour (rainure plus
  large que l'outil, engagement réduit pour les matières dures et les petites fraises) ; largeur
  de rainure et avance par boucle réglables ; le contour reste respecté.

### v0.352.0 — Poche : entrée en hélice

- Poche (concentrique ou en spirale) : avec « Entrée en rampe », un rayon d'hélice fait descendre
  l'outil en hélice à l'angle de rampe, sur un cercle qui reste dans la poche (puis un tour à plat) ;
  si aucun cercle ne tient, rampe le long du contour comme avant.

### v0.353.0 — Ligne double

- Ruban CAD › Création : « Ligne double » (comme Ligne simple/double de TypeEdit) — deux traits
  parallèles cliqués comme une polyligne ; écartement, calage au centre, à gauche ou à droite,
  bouts ouverts, fermés ou arrondis ; polyligne fermée : deux contours fermés.

### v0.354.0 — Primitives 3D en relief

- Ruban TypeArt › Textures : « Primitive 3D » (comme les surfaces Sphère, Ellipsoïde, Cône,
  Cylindre, Tore, Cube de TypeEdit) — la moitié haute du solide en relief, sur les marqueurs
  choisis ou au centre des objets choisis ; combinable avec le relief choisi.

### v0.355.0 — Dôme par profil

- Ruban TypeArt › Textures : « Dôme par profil » — un profil dessiné (trait ouvert : X = distance
  à l'axe, Y = hauteur) tourné autour d'un axe vertical au marqueur choisi, sur un tour complet ou
  de l'angle de départ à l'angle d'arrivée (bouton, coupe, dôme à profil libre) ; hauteur ramenée
  au choix ; combinable.

### v0.356.0 — Surface bilinéaire

- Ruban TypeArt › Textures : « Surface bilinéaire » (comme dans TypeEdit) — une surface réglée
  par les hauteurs de ses quatre coins, sur l'encombrement des formes fermées choisies (dans leur
  intérieur), du relief choisi ou de la plaque ; combinable (pente, plan incliné, gauchi).

### v0.357.0 — Gravure laser : ordre du remplissage

- Gravure laser (remplissage) : « Ordre du remplissage » (comme l'Optimisation de zone de
  TypeEdit) — global, forme par forme (au plus proche) ou par zones (carreaux de largeur et
  hauteur réglables, en serpentin) ; les lignes restent alignées d'une zone à l'autre.

### v0.358.0 — Gravure laser : orientation automatique

- Gravure laser (remplissage) : « Orientation automatique » (comme dans TypeEdit) — les lignes de
  chaque morceau (forme, zone) dans le sens de sa longueur : moins de lignes, plus longues, moins
  d'allumages ; l'angle des lignes s'y ajoute.

### v0.359.0 — Détourage : matière restante

- Détourage : « Matière restante en fin de contour » (comme With remaining material de TypeEdit)
  — l'outil s'arrête avant la fin du contour et la pièce reste tenue par ce pont ; à chaque passe,
  avec l'entrée tangente si elle est demandée.

### v0.360.0 — Dôme par profil : nom

- « Surface de révolution » (v0.355.0) s'appelle « Dôme par profil » : son axe est vertical ; la
  révolution autour d'un axe couché reste « TypeArt de révolution ».

### v0.361.0 — Ombrage : parties éclairées

- Ombrage : type « Parties éclairées » (comme l'Effet ombrage de TypeEdit) — le liseré de l'objet
  du côté de la lumière (opposé à la direction de l'ombre), à graver dans une couleur plus claire
  sur les matières multicouches ; l'écart le rentre dans l'objet. Groupe re-modifiable.

### v0.362.0 — Compteur de temps

- Ruban Vue › Repères : « Compteur » (comme dans TypeEdit) — le temps passé sur le document dans
  la barre d'état, gardé dans le fichier (il reprend à l'ouverture) ; il ne compte que pendant le
  travail : rien au-delà de 5 minutes sans action. Pour chiffrer un devis.

### v0.363.0 — Relief : bordure

- Ruban TypeArt › Retouches : « Bordure » (comme dans TypeEdit) — le relief choisi prolongé autour
  des formes fermées choisies, sur une largeur : dans la continuité de son bord, ou à plat à un Z
  donné ; sans sortir du relief.

### v0.364.0 — Relief : effacer, extraire une partie

- Ruban TypeArt › Retouches : « Effacer une partie » (comme dans TypeEdit) — seul le relief dans
  les formes fermées choisies est gardé (Ctrl : il y est effacé) ; « Extraire une partie » — ce
  relief devient un relief à part, recadré, ôté de l'original (Ctrl : laissé).

### v0.365.0 — Relief : tranches

- Ruban TypeArt › Retouches : « Tranches » (comme dans TypeEdit) — les contours du relief choisi à
  des cotes successives (courbes de niveau), du haut vers le bas ou du bas vers le haut : épaisseur
  de la première tranche, des suivantes, nombre ; une forme par cote. Pour retrouver le contour
  d'un objet palpé.

### v0.366.0 — Relief : poser

- Ruban TypeArt › Retouches : « Poser » (comme dans TypeEdit) — le second relief choisi posé sur le
  premier : son point le plus bas, ou son plan de base, au niveau du point le plus haut du dessous ;
  ou son plan de base qui suit la surface. Les deux reliefs sont remplacés par le résultat.

### v0.367.0 — Texte : ressorts

- Fenêtre Texte : « Insérer un ressort ◆ » (comme la fonction Ressort de TypeEdit) — l'espace libre
  d'une ligne, jusqu'à la largeur imposée (sinon la plus longue ligne), est partagé entre ses
  ressorts : mots poussés à droite, centrés, répartis, sans calcul. Le ressort ne se grave pas.

### v0.368.0 — Code-barres en négatif

- Code-barres : « Inverser couleur » (comme dans TypeEdit) — c'est le fond qui se grave : un cadre
  autour du code (marge réglable, en modules) moins les modules ou les barres, qui restent en
  relief ; pour les codes 1D et 2D.

### v0.369.0 — Ligne de coupure

- Ruban CAD › Création : « Ligne de coupure » (comme le symbole de rupture des logiciels de DAO) —
  deux clics, un trait avec le zigzag de rupture au milieu (hauteur : un sixième de la longueur).

### v0.370.0 — Couper avec point de base

- « Couper avec point de base » (Ctrl+Maj+X, comme dans les logiciels de DAO) : la sélection est
  copiée, puis effacée une fois son point de base cliqué ; « Coller au point » la repose par ce point.

### v0.371.0 — Contour de zone : écart toléré

- Contour de zone : écart toléré entre les traits (clic droit sur le bouton, comme HPGAPTOL en DAO)
  — une zone presque fermée, dont les traits ne se touchent pas tout à fait, donne quand même sa
  forme, angles vifs gardés.

### v0.372.0 — Sélection cyclique

- Sélection : Alt+clic choisit tour à tour les objets superposés sous le curseur (comme la sélection
  cyclique des logiciels de DAO) — du plus haut au plus bas, puis on reboucle ; la barre d'état dit
  lequel sur combien.
- Les messages du canevas « Milieu : second point » et celui-ci passent par les traductions.

### v0.373.0 — Calcul dans les champs

- Champs de valeur : la touche = ouvre un calcul (comme la calculatrice rapide des logiciels de DAO)
  — « 25,4*3 », « (120-10)/7 », « sqrt(2)*10 », « 50*tan(30) » (angles en degrés), pi ; le
  résultat remplace la valeur. Rien n'est exécuté : seuls les nombres et ces opérations sont lus.

### v0.374.0 — Traits de coupe

- Ruban CAD › Dessin technique : « Traits de coupe » (comme les hirondelles de repérage de TypeEdit,
  les Crop Marks des logiciels de dessin) — traits aux coins dans le prolongement des bords et/ou
  cibles au milieu des côtés, autour de la sélection (sinon de la plaque) ; longueur, écart,
  diamètre des cibles, fond perdu. Dessin original, en groupe.

### v0.375.0 — Imbriquer : remplir la plaque

- Imbriquer : 0 exemplaire = remplir la plaque (comme la copie imbriquée de TypeEdit) — les objets
  choisis, tour à tour, autant de fois qu'ils tiennent sur une plaque (quart de tour permis, écart
  et marge respectés).

### v0.376.0 — Mode Point : moyenne

- Mode Point : « Moyenne » (comme Average des logiciels de dessin) — les points sélectionnés réunis
  en leur point moyen ; puis Joindre soude deux bouts ouverts.

### v0.377.0 — Styles de texte

- Ruban CAD › Texte : « Styles de texte » (comme Créer / Utiliser un style de TypeEdit) — la mise
  en forme du texte choisi (police, hauteur, largeur, espacements, alignement, styles) enregistrée
  sous un nom, appliquée ensuite aux textes choisis ; le dernier style utilisé reste proposé.

### v0.378.0 — Informations du document

- Ruban Fichier › Document : « Informations » (comme dans TypeEdit) — titre, auteur, client,
  référence et commentaires (sur plusieurs lignes) gardés dans le fichier ; avec les chiffres du
  document : calques, objets, textes, images, temps passé. Annulable.

### v0.379.0 — Calques : inverser la visibilité

- Panneau des calques : bouton ◐ « Inverser la visibilité » (comme dans TypeEdit) — les calques
  affichés sont masqués et les masqués affichés ; la sélection perd ce qui disparaît.

### v0.380.0 — Aperçu du reste de matière

- Ruban FAO › Voir et simuler : « Reste de matière » (comme l'Aperçu du reste de matière de
  TypeEdit) — pour les formes fermées choisies et un outil du réglage, les zones qu'il ne peut pas
  vider (angles rentrants, passages trop étroits ; outil conique : à la profondeur donnée) posées
  en surfaces sur un calque « Reste de matière », avec leur aire. Pour choisir l'outil.

### v0.381.0 — Pontets incurvés

- Détourage : « Forme des pontets » incurvée (comme les ponts incurvés de TypeEdit) — l'outil monte
  et redescend en douceur sur le premier et le dernier tiers du pontet au lieu de flancs verticaux :
  moins de chocs, pontet plus facile à casser proprement.

### v0.382.0 — Pontets à la main

- Outil « Pontets à la main » (ruban FAO, comme l'ajout manuel de ponts de TypeEdit) : un clic près
  du contour d'une forme fermée y pose un pontet, un clic sur un pontet l'ôte ; le détourage les
  prend à leur place (largeur et hauteur de l'opération), à l'extérieur comme à l'intérieur ; ils
  suivent la forme quand on la déplace, la tourne ou la met à l'échelle.

### v0.383.0 — Mode Point : en arc

- Mode Point : « En arc » (comme Transformer en arc de TypeEdit) — deux points d'un contour
  sélectionnés, la portion entre eux devient l'arc de cercle qui passe par ses bouts et son milieu
  (Maj : l'autre portion d'un contour fermé), à côté de « En segment » et « En angle ».

### v0.384.0 — Relief : surépaisseur

- Relief et surface 3D : la « Surépaisseur » est prise — l'outil suit la surface décalée tout
  autour (ébauche qui laisse de la matière pour une finition avec un outil plus fin, comme les
  gammes TypeArt de TypeEdit).

### v0.385.0 — Relief : aligner un plan à zéro

- Ruban TypeArt › Retouches : « Aligner un plan à zéro » (comme dans TypeEdit) — un relief palpé
  de travers est redressé : le plan qui passe par le relief sous trois marqueurs choisis est ramené
  à Z 0, le reste suit.

### v0.386.0 — Couleurs pour daltoniens

- Ruban Vue › Affichage : « Couleurs pour daltoniens » (comme le mode ColourBlind de TypeEdit) — les
  parcours FAO et les repères d'intersection prennent des couleurs qui se distinguent sans le rouge
  et le vert (palette d'Okabe et Ito) ; gardé dans les réglages.

### v0.387.0 — Points de départ, points de contrôle

- Ruban Vue › Contours : « Points de départ » et « Points de contrôle » (comme les options
  d'affichage de TypeEdit) — le départ de chaque contour (carré plein), et les points de tous les
  contours (carré : angle, rond : point lisse), sans passer en Mode Point ; gardés dans les réglages.

### v0.388.0 — Accrochage intuitif

- Ruban Dessin › Accrochage : « Accrochage intuitif » (comme dans TypeEdit) — avec l'outil Cote, le
  curseur s'accroche aux points, milieux, centres et intersections même si l'accrochage (F3) est
  coupé ; les autres outils ne changent pas.

### v0.389.0 — Congés creusés

- Congés : un rayon négatif (comme l'angle arrondi de TypeEdit) creuse le coin — l'arc est centré
  sur le coin et entre dans la forme ; sur toute la forme ou, en Mode Point, sur les points choisis.

### v0.390.0 — Ponctuation typographique

- Textes : « Ponctuation typographique » (comme la ponctuation intelligente des logiciels de
  dessin, à la française) — guillemets « », apostrophe ’, points de suspension …, tiret —, espaces
  insécables avant ; : ! ? ; les heures (10:30) restent intactes.

### v0.391.0 — Graduations : chiffres inclinés

- Graduations linéaires : chiffres inclinés d'un angle (90° : perpendiculaires aux traits, comme
  les labels de TypeEdit), et chiffres sous la règle au lieu d'au-dessus des grands traits.

### v0.392.0 — Lire un programme ISO

- Ruban FAO › Voir et simuler : « Lire un programme ISO… » (comme les simulations NC de TypeEdit) —
  un programme G-code d'une autre machine ou d'un autre logiciel s'affiche parmi les parcours, pour
  le voir et le simuler avant de le lancer : G0/G1/G2/G3 (arcs par I J ou R), absolu/relatif,
  pouces/mm ; les cycles de perçage et les arcs hors du plan XY sont signalés.

### v0.393.0 — Vectoriser en arcs et segments

- Vectoriser : option « En arcs et segments » (comme dans TypeEdit) — le tracé n'est fait que de
  droites et d'arcs de cercle (à 0,02 mm près), que la machine suit mieux que des courbes de Bézier.

### v0.394.0 — Couteau au trait

- Ruban CAD › Création : « Couteau au trait » (comme Couper un contour de TypeEdit) — glisser un
  segment à travers des formes fermées (celles choisies, sinon toutes celles qu'il touche) : elles
  sont coupées et chaque morceau est refermé ; Ctrl : segment à 45°. Annulable.

### v0.395.0 — Étendre en arc

- Ruban Opérations › Tronquer : « Étendre en arc » (comme dans TypeEdit) — un clic près du bout d'un
  arc de cercle le prolonge sur son cercle, dans son sens, jusqu'au premier trait rencontré.

### v0.396.0 — Duplication libre

- Ruban Opérations › Duplication : « Duplication libre » (comme dans TypeEdit) — la sélection suit
  le pointeur en pointillés, chaque clic pose une copie (son centre au point cliqué, accrochage F3
  compris) ; Échap pour finir. Chaque copie s'annule.

### v0.397.0 — Ctrl+flèche en mode point

- Mode point : Ctrl+flèche se comporte comme hors mode point — « pas de déplacement ? » (proposé :
  le pas en cours, sinon l'étendue des points choisis plus l'écart des options), puis les points
  choisis avancent d'un pas dans ce sens ; les flèches suivantes avancent de ce pas, Maj + ↑ / ↓ de
  dix pas ; 0 revient au pas des options. Chaque déplacement s'annule.

### v0.398.0 — Fichiers récents en grand menu

- Fichier › Récents devient un grand menu : chaque fichier avec son dossier, son format, sa taille
  et sa date de modification (les fichiers disparus sont grisés, « introuvable ») ; boutons Ouvrir,
  Ouvrir dans l'explorateur, Retirer de la liste, Vider la liste ; double-clic : ouvrir.
- Aperçus des fichiers (Récents et Ouvrir) : coupés par défaut pour la rapidité, ils s'allument pour
  la séance par le bouton « Aperçus » du menu ou « Aperçus des fichiers » (Fichier › Document).
  Allumés, la boîte Ouvrir montre l'aperçu du fichier pointé (et peut les couper).

### v0.399.0 — Une vue par onglet

- Chaque onglet de dessin garde sa propre vue, sans influence des autres : zoom et position, zooms
  précédents (« Zoom précédent » ne ramène plus la vue d'un autre dessin), calque affiché seul,
  plan de travail 2D ou 3D, caméra 3D, et affichages (Grille, Sens, Remplissage, Aperçu gravure,
  Points de départ, Points de contrôle). Un nouvel onglet part des affichages en cours.

### v0.400.0 — Ruban TypeEdit : menu Fichier

- Disposition TypeEdit 13 : bouton « Fichier » à gauche des onglets, avec le menu principal de
  TypeEdit lu sur le poste — Nouveau, Ouvrir, Enregistrer, Enregistrer sous, Importer, Exporter,
  Imprimer, BAT, les quatre derniers fichiers par leur nom (&1 à &4), « Fichiers récents… » (le grand
  menu) et Quitter.
- Onglet contextuel Surfaces : Sphère, Cylindre, Cône, Tore, Ellipsoïde, Pavé (chacun ouvre la
  primitive en relief avec ce solide), surface de révolution, surface bilinéaire, balayages,
  projections parallèle et locale ; Mode Point : Aligner par points.

### v0.401.0 — L'onglet Relief devient 3D

- Le ruban Relief (l'ancien TypeArt) s'appelle désormais « 3D » et commence par un groupe Vues 3D
  (pièce en 3D, vue graveur, iso, YZ, ZX, modèle 3D, parcours et simulation 3D) ; les commandes de
  relief suivent, inchangées. La palette TypeArt s'appelle « 3D ».
- « TypeArt extrudé » devient « Relief extrudé », « TypeArt de révolution » « Relief de révolution ».

### v0.402.0 — Volumes 3D : le moteur

- Nouveau moteur de volumes (maillages fermés, sur Manifold, Apache-2.0) : pavé, coin, cylindre,
  cône et tronc, sphère, pyramide (et tronc), tore ; extrusion des contours fermés (trous compris)
  vers le haut ou le bas, avec angle de dépouille rentrant ou sortant ; révolution autour d'un axe
  du dessin, complète ou partielle (sens direct) ; union, soustraction, intersection ; volume, aire,
  centre de gravité, encombrement et masse. Les commandes du ruban 3D suivent.
- docs/parite_3d.md : la liste des fonctions 3D visées et leur état.
- Nouvelle dépendance : manifold3d (Apache-2.0), licence jointe.

### v0.403.0 — Les volumes dans le dessin

- Un volume 3D est une forme du dessin : en 2D, sa silhouette vue de dessus, qu'on choisit,
  déplace, tourne, retourne ou met à l'échelle comme toute forme — le volume suit (une mise à
  l'échelle uniforme agrandit aussi la hauteur ; un étirement ne touche pas Z). Copier, calques,
  annuler, enregistrer (VDZ) : comme pour les autres objets.
- Plan de travail 3D : nouvelle source « Volumes du dessin » ; en Automatique, les volumes sont
  montrés quand le dessin en a (la caméra ne se recadre pas à chaque changement).
- Exporter en STL : les volumes choisis partent tels quels.

### v0.404.0 — Ruban 3D : volumes

- Ruban 3D › Volumes : Extrusion (formes fermées choisies, hauteur, dépouille, Z de départ ; elles
  sont remplacées ou gardées), Révolution (autour de deux marqueurs, d'une droite choisie avec elles,
  sinon de la verticale de leur point le plus à gauche ; angle et départ), Pavé, Coin, Cylindre,
  Cône, Sphère, Pyramide, Tore (sur les marqueurs choisis, au centre des objets choisis ou de la
  plaque), Union, Soustraction (le premier choisi moins les suivants), Intersection, Propriétés de
  masse (volume, aire, masse selon la masse volumique, centre de gravité, encombrement). Tout
  s'annule ; le plan de travail 3D suit.
- Plan de travail 3D : les faces cachées ne passent plus devant après la première image (le test de
  profondeur se perdait) — modèles STEP / STL compris.

### v0.405.0 — Volume ↔ relief

- Ruban 3D › Volumes : « Volume en relief » — les volumes choisis vus de dessus deviennent un relief
  (le dessus de la matière à chaque pas), à usiner avec les parcours 3D (Relief, Finition) ;
  « Relief en volume » — un relief devient un volume (socle dessous), pour les booléens et le STL ;
  « Importer un volume » — un STL fermé entre dans le dessin comme volume.

### v0.406.0 — Modifier les volumes

- Ruban 3D › Volumes : Déplacer en Z ; Rotation 3D (axe X, Y ou Z par le centre de chaque volume ou
  de l'ensemble) ; Symétrie en Z (plan horizontal, copie possible) ; Couper (plan horizontal Z = ou
  vertical X = / Y =, garder un côté ou les deux) ; Section (contour 2D à une hauteur) ; Vue à plat
  (contour 2D vu de dessus, de face ou de côté, posé à droite des volumes) ; Interférence (volume
  commun de chaque paire, ajouté en volume si voulu) ; Séparer (corps disjoints en volumes à part).
  Tout s'annule ; les volumes gardent leur place, leur nom et leur outil.

### v0.407.0 — Balayage, lissage, mur

- Ruban 3D › Volumes : Balayage 3D (le chemin choisi d'abord, puis les profils fermés, trous
  compris : tube, moulure, rampe ; coins en onglet, chemin fermé possible ; torsion et échelle
  d'arrivée) ; Lissage 3D (contours fermés posés de bas en haut, à écart régulier ou aux hauteurs
  données ; passage réglé ou arrondi) ; Mur (largeur, hauteur, à gauche, au milieu ou à droite des
  traits choisis).

### v0.408.0 — [E] Cadre englobant direct

- Cadre englobant (touche E, et la commande TypeEdit qui y mène) : le rectangle de l'encombrement de
  la sélection — ou de tout le dessin — est tracé tout de suite, sans marge et sans fenêtre.
  « Cadre englobant… » garde la fenêtre (marge, coins arrondis, ellipse).

### v0.409.0 — Fiches machine livrées par un plugin

- FAO : sans dossier de fiches machine choisi, VectorDrive prend celui qu'un plugin livre (s'il en
  livre un) ; le dossier choisi par l'utilisateur prime toujours. Pour les plugins :
  `default_machines()` du fournisseur de fiches.

### v0.410.0 — Coque, arrondis, tirer / pousser

- Ruban 3D › Volumes : Coque (parois d'épaisseur donnée, fermée ou ouverte par le dessus) ; Arrondir
  les arêtes (toutes les arêtes vives au même rayon, rentrantes comprises si voulu) ; Décaler le
  volume (grossi, arêtes arrondies, ou aminci) ; Tirer / pousser (formes fermées posées sur le
  dessus d'un volume : bossage ajouté ou poche creusée) ; Lisser le maillage (facettes subdivisées,
  arêtes vives gardées au-delà d'un angle).

### v0.411.0 — Maj+C : coter

- Maj+C (Coter) : une cote choisie → ses réglages ; un cadre (ou d'autres objets) choisi → ses cotes
  automatiques — largeur dessous ou dessus, hauteur à gauche ou à droite, écart, chaque objet ou
  l'ensemble, diamètre des cercles — avec des modèles de réglages (« Enregistrer ces réglages comme
  modèle », puis le choisir dans la liste) ; rien de choisi → l'outil Cote, entre deux points, Tab
  changeant le type de cote en cours de pose. Avec le clavier TypeEdit, Maj+C mène aussi à Coter.

### v0.412.0 — Parité 3D : l'état

- docs/parite_3d.md à jour : ce que font les volumes de VectorDrive (rounds 413 à 421) en regard de
  la liste des fonctions 3D visées, et ce qui reste (congés arête par arête, édition de faces,
  STEP, mise en plan, surfaces).

### v0.413.0 — Volumes hachurés en 2D

- Plan de travail 2D : la silhouette d'un volume 3D est hachurée (couleur de son outil), pour le
  distinguer d'une forme plate.

### v0.414.0 — Réseau en Z

- Ruban 3D › Volumes : Réseau en Z — copies des volumes choisis empilées en hauteur (nombre, pas,
  rotation de l'une à l'autre autour de l'axe vertical : escalier tournant, colonne torsadée…).

### v0.415.0 — Décaler au clavier

- Décaler (touche A) : la distance arrive sélectionnée — « A 5 Entrée » décale de 5 mm ; la
  jonction (arrondie, angle vif, chanfreinée) et « Conserver l'original » reprennent la dernière
  valeur utilisée.

### v0.416.0 — Opérations : clic droit

- FAO › Opérations, clic droit : « Mettre à jour avec le dessin sélectionné » (mêmes réglages, sur
  les objets sélectionnés, parcours recalculé) ; Modifier… (Ctrl+M : le formulaire, les objets
  sélectionnés devenant ce qu'elle usine ; parcours recalculé) ; Dupliquer ; Supprimer (Suppr, son
  parcours part avec elle) ; Simuler en 2D, Simuler en 3D (cette opération seule).

### v0.417.0 — Fenêtres FAO en plein écran translucide

- FAO : « Opérations en plein écran » (outils, opérations et parcours ; bouton ⛶ du panneau) et
  « Créer un parcours en plein écran » — la fenêtre couvre tout le plan de travail et le suit quand
  il change de taille ; son opacité se règle dans sa barre de titre pour voir le dessin dessous
  (retenue) ; la molette zoome toujours le dessin, sauf au-dessus d'une liste ou d'un champ, qui
  défilent (Ctrl + molette : le dessin quand même).

### v0.418.0 — Usinage par couleur sur demande

- Créer un parcours : le choix « Usiner : la sélection / les couleurs » est caché par défaut — un
  nouveau parcours usine la sélection. La case « Usinage par couleur » le fait paraître (retenu).

### v0.419.0 — Plein écran

- Vue › Affichage : Plein écran (Maj+F11) — VectorDrive sur tout l'écran, sans barre de titre ni
  barre des tâches ; Maj+F11 pour revenir ; retenu au lancement suivant. (F11 reste le repérage,
  comme dans TypeEdit.)

### v0.420.0 — Bibliothèque d'outils : rangement

- Mes outils (tools.json) : sélection multiple (Ctrl, Maj) pour déplacer ou supprimer (Suppr) ;
  glisser des outils sur un dossier les y range, sur un outil les place juste avant lui ; ↑ / ↓
  réordonnent dans le dossier ; « Nouveau dossier… » crée un sous-dossier du dossier choisi (les
  outils choisis y vont ; vide, il est gardé) ; « Renommer… » (F2) renomme l'outil ou le dossier
  choisi.

### v0.421.0 — Volumes hachurés, même en Remplissage

- Plan de travail 2D : un volume reste hachuré quand l'affichage Remplissage est allumé (il passait
  en aplat et ne se distinguait plus).

### v0.422.0 — Passes multiples : ordre et liaison

- Poche et détourage en plusieurs passes : « Passes multiples » — poche par poche (chaque poche ou
  contour jusqu'au fond, comme avant) ou global (chaque profondeur sur toutes les poches avant la
  suivante) ; « Connecter les passes » — d'une passe à la suivante, l'outil reste dans la matière
  et descend en rampe, à l'angle de rampe de l'opération.

### v0.423.0 — Bibliothèque d'outils : plein écran, filtres, outils par opération

- La bibliothèque d'outils s'ouvre agrandie (⛶ ou F11 : plein écran) ; une seule barre de commandes :
  Importer (fichiers ou dossier), Exporter, ↑ / ↓, Déplacer vers…, Ajouter au document ou Copier dans mes
  outils selon la bibliothèque montrée ; les commandes rares dans « Plus » et toutes au clic droit.
  Supprimer (Suppr) retire aussi un dossier choisi avec ses outils (plus de bouton à part).
- Filtres : texte, nature, plage de Ø, fabricant, « Adaptés à » une opération (dans l'ordre réglé).
- Outils proposés par opération : pour chaque stratégie, les natures, dossiers ou outils précis à proposer,
  dans l'ordre, en tête ou seuls, tri par Ø ; aperçu de l'ordre obtenu ; recopie sur d'autres stratégies.
  Accès : bibliothèque d'outils, menu des outils du panneau FAO.

### v0.424.0 — Outils proposés par opération, partout

- Formulaire d'une opération : la liste « Outil » suit le réglage de la stratégie (outils du document dans
  l'ordre ; mode « seulement » : les autres cachés, l'outil choisi reste) ; réglage enregistré : les premiers
  outils adaptés de Mes outils sont proposés directement.
- Choisir un outil : filtres (nature, Ø, fabricant), case « Seulement les outils adaptés », groupe « Proposés
  pour … », bouton « Régler les propositions… », fenêtre agrandie (⛶ / F11 : plein écran).
- Boutons de la palette Parcours : stratégie réglée, le premier outil proposé est pris d'office.
- Relief > Outil : Mes outils dans l'ordre réglé pour le relief 3D.
- Qui propose des outils et sous quelle forme : docs/outils_par_operation.md et la fenêtre du réglage.

### v0.425.0 — Formulaire d'opération : outils de la stratégie choisie

- Changer la stratégie dans le formulaire refait la liste « Outil » selon les outils proposés pour elle
  (l'outil choisi reste choisi).
- Filtres de la bibliothèque plus compacts : la recherche prend la place, la fenêtre tient sur un écran de
  1 366 px ; infobulles des stratégies dans « Outils proposés par opération ».
- Raccourci TypeEdit de TypeArt « préparer pour l'usinage » : une seule correspondance (Outil du relief).

### v0.426.0 — Fichiers endommagés : messages clairs

- Ouvrir un fichier abîmé (VDZ, PDF, AI, DXF…) affiche « Fichier endommagé ou illisible », avec le détail
  technique en dessous, au lieu d'une erreur interne de la bibliothèque de lecture.
- Import d'outils : un CSV dont une ligne a plus de colonnes que l'en-tête est lu (le surplus est ignoré) ;
  une archive .zip abîmée donne un message au lieu d'une erreur non rattrapée.

### v0.427.0 — Fenêtres rouvertes après fermeture, interface plus légère

- Liste des caractères, filtre de sélection, modes de sélection et aimantation : fermées par la croix,
  elles se rouvrent de nouveau (elles étaient détruites à la fermeture et ne revenaient plus).
- Le filtre d'événements de la fenêtre principale ne regarde plus que les clics droits : moins de travail
  à chaque mouvement de souris ; le changement de thème passe de 1,2 s à 0,7 s.

### v0.428.0 — Mémoire : menus ponctuels libérés

- Menus du clic droit (panneau FAO, calques, bibliothèque d'outils), « Défaire / Refaire plusieurs… »,
  palettes et boîte des propriétés de masse : libérés après usage (chacun restait en mémoire jusqu'à la
  fermeture du logiciel, un par ouverture).

### v0.429.0 — Détourage plus rapide sur les dessins chargés

- Ordre des pièces au plus proche (détourage, remplissage laser forme par forme) calculé d'un coup : un
  détourage de 400 pièces passe de 4,2 s à 0,9 s, avec exactement le même parcours.

### v0.430.0 — Bandeau Fichier complet en disposition TypeEdit, formulaire de parcours agrandissable

- Disposition TypeEdit 13 : l'onglet Fichier de VectorDrive (Document, Récents, modèles, Import / export,
  BAT, impression, lot…) reste affiché, en premier, à la place du menu Fichier réduit ; Quitter y est ajouté.
- Formulaire d'un parcours : bouton ⛶ et F11 pour le plein écran, bouton d'agrandissement de la fenêtre,
  état agrandi retenu ; l'usinage par couleur (couleurs, objets choisis) est replié en fin de formulaire,
  son résumé sur le bouton.

### v0.431.0 — Modèles de parcours : rangement à la souris, import TypeEdit fidèle

- Import des paramètres de parcours de TypeEdit : l'arborescence est refaite telle quelle (dossiers dans les
  dossiers, séparateurs pris en compte, groupes de la palette), dans l'ordre de TypeEdit, et les noms des
  modèles ne sont plus tronqués ; un nouvel import remplace le précédent au lieu de le doubler.
- Palette des parcours : vos modèles et dossiers se rangent par glisser-déposer (sur un dossier, ou sur
  « Modèles (dossiers) » pour les sortir de tout dossier), sélection multiple, Nouveau dossier (gardé même
  vide), Nouveau sous-dossier, Renommer (F2), Supprimer (Suppr).

### v0.432.0 — Cadre englobant et entrées tangentes corrigés

- « Pas de passe sur le cadre » ne saute plus que le contour fermé qui englobe tout (ou chaque contour
  englobant non englobé) : les formes à l'intérieur (personnage, brouette, soleil…) sont de nouveau
  gravées.
- Détourage avec entrée / sortie tangentes : l'arc est réduit pour rester dans la chute (jour étroit
  entre deux formes, intérieur d'une lettre), ou supprimé s'il ne tient pas — il n'entame plus la pièce.

### v0.433.0 — Affichages Ctrl+7, Ctrl+8, Ctrl+9 ; 3D filaire

- Ctrl+7 (Sens) : contours fermés en vert (anti-horaire) ou en bleu (horaire), contours ouverts en noir,
  avec la flèche de départ et le rang.
- Ctrl+8 (Couleurs des outils) : traits à la couleur de leur outil, ou tous à l'encre ; l'aperçu de gravure
  reste dans le menu, sans raccourci.
- Ctrl+9 (Remplissage) : contours fermés remplis de la couleur de leur outil.
- L'export en image reprend ces affichages (sens, couleurs, remplissage), réglables dans sa fenêtre.
- Vue 3D filaire par défaut.

### v0.434.0 — Images blanches sans fond, vectorisation lissée

- Une image claire sur fond transparent (logo blanc en PNG) est reconnue : affichée sur un fond sombre au
  lieu d'être invisible, et vectorisée d'après sa forme.
- Vectorisation : longueur des segments réglable (mm), et option « Courbure continue » (lissage C∞, force
  réglable) pour les images de basse qualité ; les coins restent vifs au-delà de l'angle des coins.

### v0.435.0 — Origine dans le VND, BAT coté par gravure

- VND : l'origine du dessin (au centre de la plaque, par exemple) devient le zéro du fichier : TypeEdit
  rouvre la même plaque avec la même origine.
- BAT : une cote (largeur, hauteur) pour chaque gravure — chaque objet ou groupe de premier niveau —, et
  le prix du devis au-dessus de chacune quand un devis a été réglé (fourni par un plugin).

### v0.436.0 — Bibliothèque en dossiers, S pas à pas, menu des onglets

- Bibliothèque (B) : chaque dossier montre son dossier parent, ses sous-dossiers puis ses fichiers, comme
  l'explorateur (double-clic pour entrer, Retour arrière pour remonter, chemin affiché ; « Sous-dossiers »
  pour tout voir à plat). Gestion complète au clic droit : nouveau dossier, renommer (F2), déplacer
  (aussi par glisser-déposer sur l'arbre), corbeille (Suppr), importer des fichiers, enregistrer la
  sélection du dessin ici, ouvrir dans l'explorateur.
- S (Éclater pas à pas) : à chaque appui, un niveau de moins — groupes dégroupés, puis formes séparées en
  pièces (extérieur et ses trous), puis chaque contour seul.
- Clic droit sur un onglet de document : nouveau, dupliquer, recharger depuis le disque, enregistrer,
  enregistrer sous, fermer.

### v0.437.0 — Visualiseur de programmes en 3D

- « Visualiser un programme en 3D » : un programme machine lu et montré seul en 3D filaire, cadré.
- Langages lus : ISO (arcs dans les plans XY, XZ et YZ), Heidenhain en dialogue texte clair (L, CC, C,
  CR, FMAX, cotes incrémentales), et ceux qu'ajoutent les plugins (SimPL…), reconnus au contenu ou à
  l'extension.

### v0.438.0 — Outils par machine, outils reconnus d'un coup d'œil

- Chaque outil peut être réservé à des machines (post-processeurs) : gestionnaire d'outils › Plus ou clic
  droit › Machines… (outils choisis, ou tout un dossier) ; aucune machine : l'outil sert partout.
- Choix d'un outil, gestionnaire et propositions des formulaires : seulement les outils de la machine du
  réglage FAO (case « Outils de : … », décochée pour tous les voir) ; le choix automatique d'un nouveau
  parcours prend d'abord un outil de la machine.
- Les outils se reconnaissent : silhouette en icône, cotes dans le libellé (« T12 Fraise 2 — Ø2 L4 Z2 »),
  fiche complète en infobulle et à côté de la silhouette (nature, cotes, référence, vitesses, dossier,
  machines).

### v0.439.0 — Bibliothèque : grandes vignettes, aperçu, grande fenêtre

- Taille des vignettes réglable (curseur, ou Ctrl + molette sur la liste) : au-delà de la petite vignette
  enregistrée dans les symboles, chaque dessin est retracé net à la taille voulue (formes teintées,
  couleurs des outils).
- Aperçu grand format du fichier choisi et sa fiche : taille en mm, objets, contours, poids, date.
- « Grande fenêtre » : la bibliothèque dans une fenêtre agrandie (dossiers, grandes vignettes, aperçu),
  F11 pour le plein écran ; double-clic pour poser dans le dessin.

### v0.440.0 — 3D : navigation, couleurs par parcours, grille et cotes

- Molette : le zoom se fait vers le curseur ; la pièce se regarde aussi par-dessous.
- Clavier dans la vue 3D : flèches pour tourner, + / − (ou Page haut / bas) pour zoomer, pavé numérique
  1 face, 3 côté, 7 dessus, 0 perspective, 5 orthogonale / perspective, F ou Origine : tout voir.
- Une couleur par parcours, avec sa légende ; grille au sol sous la pièce et cotes X × Y × Z en
  surimpression (cases Grille, Cotes, Couleur par parcours).
- « Image… » : la vue 3D enregistrée en PNG ou JPEG.
- Gros programmes (150 000 mouvements) : trajectoires envoyées d'un seul bloc à la carte graphique.
- Visualiseur de programmes : la 3D montre bien les trajectoires du programme (et non le dessin), sur une
  zone qui le couvre en entier.

### v0.441.0 — Vérifier l'outil ; 3D : plaque en filaire, couleur par profondeur

- Formulaire d'une opération : « Vérifier l'outil » — l'outil choisi atteint-il tous les détails des
  formes fermées à usiner ? Part de surface hors d'atteinte et plus gros diamètre qui passe partout.
- 3D filaire : les arêtes de la plaque autour des trajectoires ; trajectoires colorées par parcours, par
  profondeur (de la surface au fond) ou d'une seule couleur.

### v0.442.0 — Programmes machine : un parcours par outil

- Le visualiseur découpe un programme par outil — ISO (T…, le commentaire de la ligne sert de nom),
  Heidenhain (TOOL CALL), et les langages des plugins — : chaque outil est un parcours nommé, dans sa
  couleur en 3D, avec la légende.

### v0.443.0 — Panneau FAO : outils reconnus, machine vérifiée

- Tableaux des outils et des opérations : silhouette de l'outil, cotes dans le libellé, fiche en
  infobulle ; un outil réservé à d'autres machines que celle choisie est signalé (orange).
- Lecteurs de programmes éprouvés sur 30 000 programmes aléatoires ou abîmés : aucune erreur.

### v0.444.0 — 3D : coordonnées et distances au clic

- Un clic sur une trajectoire dans la vue 3D donne les coordonnées du point le plus proche (profondeur
  vraie, même relief exagéré) ; un second clic, la distance entre les deux points (et ΔX, ΔY, ΔZ) ;
  Échap pour effacer.

### v0.445.0 — Outil conseillé

- Formulaire d'une opération : « Outil conseillé » choisit le plus gros outil adapté à la stratégie qui
  atteint tous les détails des formes, parmi les outils du document et ceux de Mes outils de la machine.

### v0.446.0 — Bibliothèque : récents

- « ★ Récents » en tête de l'arbre de la bibliothèque : les 30 derniers fichiers posés dans un dessin, le
  plus récent d'abord (panneau et grande fenêtre).

### v0.447.0 — 3D : temps et longueurs dans la légende

- La légende de la vue 3D donne pour chaque parcours son temps d'usinage estimé et sa longueur en avance,
  et le total (avances du réglage FAO ; programme lu sans avance connue : 600 mm/min).

### v0.448.0 — Programmes lus : temps selon les avances programmées

- Visualiseur : les avances écrites dans le programme (F, en ISO et en Heidenhain) servent au temps
  estimé de chaque parcours, au lieu d'une avance par défaut.

### v0.449.0 — Favoris de la bibliothèque, échelle des profondeurs en 3D

- Bibliothèque : « ☆ Favoris » sous « Récents » — fichiers et dossiers retenus au clic droit (Ajouter aux
  favoris / Retirer des favoris).
- 3D, couleur par profondeur : l'échelle (surface, fond en mm) dans la légende.

### v0.450.0 — Bibliothèque : VND et SVG ; outils importés et machine

- La bibliothèque accepte aussi les dessins VND et SVG (vignettes, aperçu, pose dans le dessin).
- Outils importés : l'indication pour les réserver à la machine du réglage FAO (Plus › Machines…, le dossier
  importé restant choisi) ; rien n'est changé sans le demander.

### v0.451.0 — Programmes lus : outils reconnus

- Visualiseur : l'outil de chaque parcours est reconnu — un outil de Mes outils dont la référence (ou le
  nom) figure dans le programme, sinon les cotes lues (Ø, D, angle) — et la lecture pas à pas en 3D le
  dessine à sa taille.

### v0.452.0 — Outils du document reconnus dans Mes outils

- Panneau FAO : chaque outil du document dit s'il est dans Mes outils (et dans quel dossier) — même
  référence, ou même nom et mêmes cotes ; « Outils › Copier les outils absents dans Mes outils » les y
  range (dossier « Copiés des dessins »).

### v0.453.0 — Lecture 3D : temps écoulé, vue qui suit l'outil

- Lecture des parcours en 3D : le temps écoulé sur le temps total à côté du mouvement en cours ; « Suivre
  l'outil » garde la vue centrée sur lui.

### v0.454.0 — Bibliothèque : glisser-déposer à l'endroit voulu

- Un dessin glissé de la bibliothèque (DXF, VDZ, VND, SVG) est posé là où on le lâche, comme un symbole ;
  un dessin venu d'ailleurs reste importé tel quel.

### v0.455.0 — Documentation

- Trois pages : `docs/vue_3d.md` (vue 3D, visualiseur de programmes, navigation, mesures, lecture),
  `docs/bibliotheque.md` (dossiers, vignettes, récents, favoris, gestion), `docs/outils_par_machine.md`
  (outils par machine, reconnus, vérifiés, conseillés), citées dans le README.

### v0.456.0 — 3D : mesures sur les modèles

- La mesure au clic vise aussi les sommets des arêtes d'un modèle 3D (STEP, STL…) : coordonnées d'un point,
  distance entre deux.

### v0.457.0 — Grande fenêtre de la bibliothèque : fermer après avoir posé

- Case « Fermer après avoir posé » (retenue) : la grande fenêtre se ferme dès qu'un fichier est posé dans
  le dessin.

### v0.458.0 — 3D anticrénelée

- Vue 3D : anticrénelage (MSAA ×4) — traits, trajectoires et arêtes lissés (sans effet sur les cartes qui ne
  le permettent pas).

### v0.459.0 — Bibliothèque : vignettes de l'écran d'abord

- Grandes vignettes d'un dossier fourni (2 000 fichiers et plus) : celles qui sont à l'écran sont faites
  d'abord, et de nouveau après un défilement — en moins d'une demi-seconde au lieu de suivre l'ordre du
  dossier.
### v0.460.0 — 3D : gros programmes affichés, plaque masquable

- Vue 3D : la barre passe à la ligne et le texte d'information est tronqué (en entier dans la bulle). Un
  gros programme (900 000 mouvements) élargissait la fenêtre hors de l'écran et la vue OpenGL ne
  s'affichait pas.
- Case « Plaque » : masque la plaque de travail (bloc et arêtes en filaire).
- Visualiseur : le programme est lu une seule fois et la vue calculée une seule fois (deux fois plus
  rapide) ; le brut déclaré par le programme (BLK FORM Heidenhain, ou donné par un plugin) remplace la
  plaque du dessin ; la durée calculée par la machine, quand un plugin la fournit, s'ajoute à la légende.
- Lecteurs de programmes des plugins : ils reçoivent le chemin du fichier (fichiers joints par la machine).
### v0.461.0 — B : la bibliothèque dans sa fenêtre, à tout l'écran

- B (jeu de raccourcis TypeEdit) ouvre la bibliothèque dans sa fenêtre séparée, agrandie à tout l'écran
  (F11 : plein écran) ; de nouveau B la referme. Le panneau latéral reste disponible (Ctrl+Maj+Y, ruban).
### v0.462.0 — Alt+W : centrer la sélection sur l'origine

- Alt+W (et la commande TypeEdit Manipuler › Centrer) : le centre de la sélection est posé sur l'origine
  (celle de « Placer l'origine », sinon le zéro du dessin). « Centrer plaque » reste dans le ruban.
### v0.463.0 — Panneau FAO : la liste des opérations en grand

- Panneau « FAO : opérations et parcours » : outils, opérations (avec leurs commandes) et parcours dans un
  partage réglable à la souris, retenu d'une séance à l'autre ; la liste des opérations prend la plus
  grande part (six lignes au moins).
- À l'ouverture, le panneau prend toute la hauteur de la fenêtre.
### v0.464.0 — Post-processeur dans les Options, panneaux FAO translucides

- Le post-processeur (machine) se choisit dans les Options, onglet FAO : il vaut pour le dessin ouvert et
  pour les nouveaux dessins. Le panneau FAO affiche seulement la machine choisie et un bouton « Options… ».
- Panneaux FAO détachés et formulaires des outils et opérations légèrement translucides : opacité réglable
  dans les Options (94 % par défaut, 100 % : opaques). Le plein écran translucide garde son propre réglage.
### v0.465.0 — Schéma de l'opération : la rampe à son angle

- Formulaire d'une opération, schéma en coupe : la rampe est tracée à son vrai angle (même échelle en
  largeur et en profondeur), en zigzag quand elle est plus longue que la place, comme à l'usinage ; l'angle
  et la longueur de rampe par passe sont indiqués (0 = 5°, comme le calcul).
- Le schéma suit chaque changement du formulaire (angle, profondeur, passes…).
### v0.466.0 — Parcours « Finition 2,5D »

- Nouveau parcours « Finition 2,5D » (palette FAO, Usinage 3D) : la finition 3D en mode gravure 2,5D. La
  surface que laisse une gravure 2,5D des contours fermés (cône de l'outil de gravure, choisi comme « Outil
  passé avant », profondeur de l'opération) est balayée avec l'outil de l'opération (fraise boule, droite ou
  conique), selon X, Y ou croisé.
- Option « Ébauche » : paliers en Z jusqu'à la surface, surépaisseur en Z et décalage en XY le long des
  flancs (la finition reprend ensuite la surface exacte).
### v0.467.0 — FAO : opérations machine depuis un catalogue

- Panneau FAO, bouton 📖 « Ajouter depuis un catalogue » : une fenêtre (arbre, recherche, aperçu du bloc)
  propose les opérations machine des catalogues apportés par les plugins — commandes de la documentation de
  la machine, opérations d'un autre logiciel, programmes d'exemple — et les pose dans la liste des
  opérations, après celle choisie. « Fichier… » prend un fichier texte comme bloc de programme.
- Bloc de programme : les paramètres {p1} … {p6} peuvent porter un nom, affiché dans le formulaire.
- API des plugins : `add_instruction_catalog(libellé, fournisseur)`.
### v0.468.0 — 3D : finesse réglable

- Vue 3D, liste « Finesse » (normale, fine, très fine) : la simulation et le relief sont calculés sur une
  grille de 1, 4 ou 16 millions de points, et la surface affichée est plus détaillée (420, 900 ou 1 800
  points de côté) — pour voir des gravures fines sur une grande pièce. Le choix est retenu.
- Mesure sur un programme réel de 900 000 mouvements (pièce de 520 × 200 mm) : simulation en 7,6 s
  (pas de 0,32 mm), 9 s (0,16 mm), 10,8 s (0,08 mm).
### v0.469.0 — Visualiseur plus rapide

- Ouverture d'un gros programme dans le visualiseur : la vue 3D n'est plus calculée deux fois, et les
  calculs d'arcs (longueurs, temps, tracé) sont plus rapides. Sur un programme réel de 900 000 mouvements :
  6,8 s, contre 34 s en v0.459.
### v0.469.1 — Documentation

- `docs/catalogues_fao.md` : opérations machine depuis un catalogue, Finition 2,5D, post-processeur dans les
  Options, panneau FAO ; `docs/vue_3d.md` : plaque, finesse, brut et durée de la machine d'un programme lu.
### v0.470.0 — 3D d'un programme ouvert comme dessin

- Un programme machine ouvert par Fichier › Ouvrir (SimPL avec le plugin, ISO, Heidenhain…) montre en 3D
  ses trajectoires — un parcours par outil, sur le brut du programme — et non plus le relief plat du
  dessin ; la simulation part de ces trajectoires. Le programme est lu une fois (relu s'il change).
### v0.471.0 — Catalogue d'opérations : récents

- Fenêtre « Ajouter depuis un catalogue » : rubrique « ★ Récents » en tête, avec les 15 dernières opérations
  ajoutées (retenues d'une séance à l'autre).
### v0.472.0 — 3D : seuls les parcours cochés

- Cocher ou décocher un parcours dans la liste FAO met la vue 3D à jour : seuls les parcours cochés y
  restent (par exemple une opération d'un programme lu dans le visualiseur), sans changer la vue.
### v0.473.0 — Lecture pas à pas à la durée de la machine

- Quand le programme lu donne la durée calculée par la machine (plugin), la lecture pas à pas affiche le
  temps écoulé calé sur elle (« durée machine ») : l'estimation donne les proportions, la machine le total.
### v0.474.0 — Panneau FAO sur toute la hauteur

- À l'ouverture du panneau FAO, le panneau Dimensions passe en onglet à côté de « FAO : opérations et
  parcours » : les opérations ont toute la hauteur de la fenêtre (F2 montre l'onglet Dimensions). La
  disposition d'avant revient quand on ferme le panneau FAO.
### v0.474.1 — Finition 2,5D : plusieurs formes, sans frotter

- Finition 2,5D sur plusieurs formes séparées : le calcul échouait, il passe.
- Là où il n'y a rien à enlever (entre les formes, autour), l'outil passe à la hauteur d'approche au lieu
  de frotter le dessus de la pièce.
### v0.475.0 — Catalogue : documentation à la page

- Fenêtre « Ajouter depuis un catalogue » : bouton « Documentation, p. N » quand le catalogue indique le
  document du poste qui décrit l'opération (manuel de la machine en PDF) — ouvert dans VectorDrive, à la
  bonne page, sans autre logiciel.
- API des plugins : `Entry.doc` (chemin du PDF) et `Entry.page`.
### v0.475.1 — Schéma de rampe lisible

- Schéma de l'opération : l'angle de rampe s'écrit sous la surface (il chevauchait le titre) et « Rampe a°
  sur L mm par passe » a sa propre ligne en bas de la coupe (le titre était tronqué).
### v0.475.2 — Nettoyage

- Panneau FAO et traductions : restes des changements du jour retirés (aucun effet visible).
### v0.475.3 — Export de la sélection

- Exporter (Ctrl+E), « La sélection seulement » : chaque objet garde son calque et l'outil de ce calque (le VND
  mettait toute la sélection au calque actif, à son outil) ; l'origine du dessin est appliquée comme à
  l'enregistrement (même place dans TypeEdit) ; variables et informations du dessin suivent.
### v0.476.0 — Ouvrir : navigateur à vignettes

- Fichier › Ouvrir (Ctrl+O) : navigateur à vignettes — dossiers du poste (Bureau, Documents, lecteurs, dossiers
  ajoutés avec +), vignettes des dessins VND, DXF, SMB, SVG, AI, EPS, PDF, VDZ tracées à la taille choisie
  (48 à 512 px, Ctrl + molette), grand aperçu et fiche du fichier pointé, filtre par format, recherche par nom
  (sous-dossiers compris, sans accents), récents et favoris ; Ouvrir (plusieurs fichiers), Insérer dans le
  dessin, ou « Boîte de Windows… ». Option Fichiers › « Ouvrir : navigateur à vignettes » pour revenir à la
  boîte du système.
### v0.476.1 — Traductions

- Navigateur Ouvrir : libellés traduits en anglais.
### v0.477.0 — Ouvrir : accès rapides de Windows

- Navigateur Ouvrir (Ctrl+O) : les accès rapides de l'explorateur Windows (dossiers épinglés et fréquents,
  partages réseau compris) en tête de l'arbre ; un clic sur « Accès rapide » les montre en grand.
- Vignettes : les images du dessin (logo scanné, photo…) apparaissent (elles restaient blanches).
### v0.478.0 — Vignettes dans l'explorateur Windows

- Fichier › Import / export › « Vignettes dans l'explorateur » : les dessins VND, DXF, SMB, SVG, AI, EPS, VDZ
  (et PDF si aucun autre logiciel n'en fournit déjà) ont leur vignette dans l'explorateur Windows, tracée par
  VectorDrive (lancé sans fenêtre à la demande, arrêté seul après deux minutes). Votre compte seulement, sans
  droit d'administrateur ; décocher pour retirer.
### v0.478.1 — Vignettes de l'explorateur : chemin avec espaces

- Contrôle de la pose des vignettes juste quand VectorDrive est dans un dossier dont le nom contient des
  espaces ou des accents.
### v0.479.0 — Ouvrir : Précédent, Parent, Suivant ; programmes CN

- Boîte Ouvrir (Ctrl+O) : boutons Précédent, Dossier parent et Suivant, comme dans l'explorateur
  (Alt + Gauche, Alt + Haut, Alt + Droite) ; l'historique couvre aussi Récents, Favoris et Accès rapide.
- Les programmes machine y sont aussi : G-code ISO (.nc, .iso, .tap, .ngc, .gcode, .gc, .cnc, .mpf, .spf,
  .eia, .din, .ptp), Heidenhain (.h) et les langages apportés par les plugins. Vignette = parcours vu de dessus
  (un trait de couleur par outil, rapides en pointillé), fiche : langage, emprise, Z, outils, longueurs.
  Ouvrir les montre dans le visualiseur 3D ; « Insérer dans le dessin » les ajoute aux parcours affichés.
- Filtres : « Dessins et programmes » (par défaut), « Programmes CN », « Tous les dessins ».
### v0.479.1 — Vignettes tronquées au défilement

- Bibliothèque et boîte Ouvrir : une vignette arrivée pendant le défilement n'est plus tronquée (la case
  du fichier a sa taille de vignette dès l'affichage du dossier).
### v0.480.0 — Carte graphique de la vue 3D

- F10 › Affichage › « Carte graphique de la vue 3D » : choix de Windows, économie d'énergie (carte intégrée),
  hautes performances (carte dédiée) ou rendu logiciel — pour les postes à deux cartes. Les cartes du poste
  et celle qui rend la vue 3D sont affichées sous l'option. Au prochain démarrage.
### v0.481.0 — Exporter : réglages selon le format, fichier vérifié

- Exporter (Maj+E) : seuls les réglages du format choisi sont montrés (VND : textes modifiables ; images :
  résolution, fond, plaque, marge, trait, remplissage ; autres formats : aucun).
- Le fichier écrit est relu et vérifié (objets retrouvés pour un dessin, dimensions pour une image) ; le
  résultat s'affiche avec un bouton « Ouvrir le dossier ».
- Bouton « Dossier du dernier export » dans la fenêtre Exporter.
### v0.481.1 — Régions des grands dessins beaucoup plus rapides

- Région des contours fermés (remplissage, poches, finesse du devis, reste de matière…) : un dessin de
  milliers de contours imbriqués ou croisés se calcule en une fraction de seconde au lieu de plusieurs
  minutes (DXF de 7 400 contours : devis en 4 s au lieu de plus de 5 min). Calcul interruptible.
### v0.482.0 — Calculs sur plusieurs cœurs, onglet Performances

- Poches et gravure 2,5D : les retraits de la région se calculent en même temps sur les cœurs du poste
  (Hibou : poche 3,4 s → 1,7 s, gravure 2,5D 10,8 s → 6,4 s, mêmes trajectoires).
- F10 › Performances (nouvel onglet) : nombre de fils de calcul (automatique : cœurs moins un), calculs
  longs en priorité basse pour garder les autres logiciels fluides, carte graphique de la vue 3D (déplacée
  ici), anticrénelage de la vue 3D (aucun à 8 ×). Les cœurs et les cartes du poste y sont affichés.
### v0.482.1 — DXF plus rapides, mémoire des vignettes bornée

- DXF : les anciennes polylignes 2D (POLYLINE) sont lues comme les LWPOLYLINE, arcs exacts — ouverture
  environ 30 % plus rapide sur les dessins qui en sont faits.
- Vignettes (bibliothèque, Ouvrir, récents) gardées dans une mémoire bornée, réglable dans F10 ›
  Performances (256 Mo par défaut) : les moins récemment vues partent d'abord.
### v0.483.0 — Traitement par lots sur plusieurs cœurs, plugin 1.22.1

- Traitement par lots (conversion et vérification) : quand le reste du lot s'annonce long, il est réparti
  sur plusieurs processus (lot de 9 DXF lourds : 17,6 s → 9,3 s) ; un lot de petits fichiers reste à la
  suite, sans surcoût. Deux sources pour un même fichier de sortie (x.vnd et x.gvt) : la seconde est
  signalée et ignorée au lieu d'écraser la première.
- Devis (plugin BFM 1.22.1) : finesse du dessin calculée sur plusieurs cœurs (Hibou 5,4 s → 3,4 s).
### v0.483.1 — Gravure 2,5D en ligne médiane plus rapide

- Gravure 2,5D en ligne médiane : l'axe médian se calcule 2 à 3 fois plus vite (Bateau : 43 s → 14 s),
  trajectoires identiques.
### v0.483.2 — Simulation d'usinage 3 à 5 fois plus rapide

- Simulation des parcours (vue 3D) et lecture pas à pas : chaque mouvement ne calcule que la zone où l'outil
  touche vraiment la matière (une fraise conique de 6 mm qui grave à 0,2 mm ne creuse que dans 0,17 mm de
  rayon) : 3 à 5 fois plus rapide (Hibou, 4 millions de points : 53 s → 10 s), matière identique.
### v0.484.0 — Réunion et décalage des grands dessins

- Réunion (Union) de nombreux objets : par groupes d'objets qui se touchent, deux à deux — 1 900 objets en
  7 s au lieu de plusieurs minutes, même résultat.
- Décaler : un long décalage (des milliers d'objets) passe sur plusieurs cœurs — 1 900 objets en 5,7 s au
  lieu de 20 s, même résultat.
### v0.484.1 — Vignettes des gros dessins sur plusieurs cœurs

- Bibliothèque et boîte Ouvrir : quand les vignettes sont lentes (gros DXF, dossier réseau), les suivantes
  se tracent sur plusieurs processus — dossier de 27 gros DXF : 48 s → 18,5 s. Les dossiers ordinaires
  restent comme avant.
### v0.484.2 — BAT plus rapide

- BAT (PDF) des dessins aux nombreuses gravures : 40 % plus rapide (3 800 cotes : 19 s → 11 s) — les
  caractères des polices sont gardés pour la séance, le PDF est compressé un peu moins fort (2 % plus gros).
### v0.484.3 — Vignettes des programmes dans l'explorateur

- « Vignettes dans l'explorateur » couvre aussi les programmes machine (.nc, .tap, .ngc, .gcode, .cnc, .mpf…
  et SimPL avec le plugin) : leur parcours vu de dessus, comme dans la boîte Ouvrir. Si la commande est
  déjà cochée, la décocher puis la recocher pour ajouter ces formats.
- Enregistrer : un gros dessin s'écrit sans figer la fenêtre (barre de progression au-delà d'un tiers de
  seconde).
### v0.485.0 — Parcours FAO : seules les opérations changées sont recalculées

- Calcul des parcours : une opération dont rien n'a changé (ni elle, ni les outils et le réglage, ni le
  dessin, ni son point de départ) reprend son parcours d'avant — retoucher une opération sur trois ne
  recalcule qu'elle (Hibou : 8 s → 0,5 s ; rien de changé : 0,15 s). Le texte machine, les instructions
  et la surface 3D (fichier STEP) sont toujours recalculés.
### v0.485.1 — Simulation 3D mémorisée

- Vue 3D : la même simulation redemandée (vue rouverte, source rechoisie, parcours inchangés) revient
  aussitôt au lieu d'être recalculée ; une retouche des parcours la recalcule. Mémoire réglable dans F10 › Performances (512 Mo par défaut, 0 : jamais gardée).
- Panneau FAO : la barre d'état dit combien de parcours ont été repris tels quels et combien recalculés.
### v0.485.2 — Vignettes de l'explorateur en parallèle, pas de processus orphelins

- Vignettes de l'explorateur : plusieurs vignettes se tracent en même temps (dossier de 9 gros DXF : 17 s →
  6,6 s) — les dernières d'un gros dossier ne manquent plus (l'explorateur abandonnait une demande après
  25 s d'attente).
- Les processus de calcul (lots, vignettes, décalages) s'arrêtent avec VectorDrive, même après une
  fermeture brutale : plus aucun processus orphelin en mémoire.
### v0.485.3 — Mémoires de la séance visibles et vidables

- F10 › Performances : la mémoire utilisée par VectorDrive, celle des vignettes et des simulations 3D (sur
  leur plafond), le nombre de parcours gardés ; bouton « Vider les mémoires » (tout se recalcule au besoin).
### v0.485.4 — Import PDF plus rapide

- Import PDF (et Illustrator compatible PDF) : les pages faites de tracés se lisent 2,5 fois plus vite (BAT
  de 10 000 gravures : 13 s → 5 s) ; les pages à textes restent lues comme avant.
### v0.486.0 — Ouvrir : tri des fichiers

- Boîte Ouvrir : tri par nom, par date (les plus récents d'abord), par taille ou par type, retenu d'une
  fois sur l'autre — le dernier fichier d'un dossier client se retrouve en tête.
### v0.486.1 — F10 : chercher un réglage

- Options (F10) : un champ de recherche en haut — taper « fils », « vignettes », « VND », « outil »… ne garde
  que les réglages concernés (libellés et info-bulles, sans accents ni majuscules) et ouvre leur onglet.
### v0.486.2 — Plan de travail plus fluide sur les gros dessins

- Plan de travail : repeint 3 à 6 fois plus rapide sur les dessins de milliers d'objets (sélectionner,
  désélectionner : 0,5 s → 0,1 s pour 10 000 objets), surtout en thème sombre.
### v0.486.3 — Symboles posés plusieurs fois plus vite

- Bibliothèque : un symbole (ou un gros DXF) posé plusieurs fois n'est lu qu'une fois par séance ; un fichier
  modifié entre-temps est relu.
### v0.486.4 — SimPL écrits à la main lisibles, durée machine ; plugin 1.23.0

- Programmes SimPL écrits à la main (plugin BFM 1.23.0) : le visualiseur et les vignettes suivent Main et
  ses sous-programmes ; les textes gravés par la machine (StandardTextEngrave) et ses rectangles
  (RectFromMid) sont tracés de façon approchée — police monotrait de TypeEdit, date du jour — et signalés.
- Fiche d'un programme (boîte Ouvrir) : la durée calculée par la machine quand elle est connue.
### v0.486.5 — Programmes ISO : cycles de perçage tracés

- Programmes ISO (G-code) : les cycles de perçage G81 à G89 sont maintenant tracés dans le visualiseur et
  les vignettes (descente au fond à chaque trou, retour au plan R ou à la cote de départ) au lieu d'être
  seulement signalés.
### v0.486.6 — Vue 3D : mémoire graphique rendue quand elle est masquée

- Vue 3D masquée (retour au plan 2D, panneau fermé) : sa mémoire graphique est rendue aux autres programmes
  et rechargée à l'affichage suivant — utile sur les cartes intégrées.
### v0.486.7 — Essais en parallèle

- Pour les développeurs : `python outils/tests_paralleles.py` passe la suite des essais sur plusieurs
  processus (2 min 30 au lieu de 7 min) ; la fin de round s'en sert.
### v0.486.8 — Essais sans fichiers temporaires laissés

- Pour les développeurs : `outils/tests_paralleles.py` fait travailler les essais dans un dossier temporaire
  à part, supprimé à la fin — plus de dossiers accumulés dans le Temp de Windows.
### v0.486.9 — Nombre de processus réglable

- F10 › Performances : « Processus des longs travaux » (traitement par lots, Décaler, vignettes lentes,
  vignettes de l'explorateur) — automatique par défaut (8 au plus), à réduire sur un poste chargé (environ
  150 Mo chacun).
### v0.487.0 — Ouvrir plusieurs dessins d'un coup, plus vite

- Ouvrir plusieurs dessins à la fois (boîte Ouvrir, sélection multiple) : ils sont lus ensemble, sur
  plusieurs cœurs quand la lecture s'annonce longue (9 gros DXF : 18,7 s → 11,3 s), puis un onglet chacun ;
  un fichier illisible est signalé sans arrêter les autres.
### v0.487.1 — Mesurer le poste

- F10 › Performances : « Mesurer le poste » — quelques secondes pour voir ce que les fils de calcul et les
  processus apportent sur ce poste, avec un conseil de réglage si les valeurs automatiques ne conviennent pas.
### v0.487.2 — Programmes Heidenhain : perçages et arcs tangents

- Programmes Heidenhain : les cycles de perçage 200 à 205 (appelés par CYCL CALL ou M99) et les arcs
  tangents CT sont maintenant tracés dans le visualiseur et les vignettes.
### v0.487.3 — Vérification par lots des programmes machine

- Traitement par lots › Vérifier, et `VectorDrive --verifier dossier` : les programmes machine (G-code,
  Heidenhain, SimPL…) sont lus aussi — nombre de mouvements et d'outils, remarques du lecteur, programmes
  vides ou illisibles signalés. Pratique avant d'envoyer un dossier aux machines.
### v0.487.4 — Rendu logiciel sans anticrénelage

- Vue 3D en rendu logiciel (F10 › Performances › Carte graphique) : l'anticrénelage est coupé — sans carte
  graphique, chaque échantillon coûte au processeur.
### v0.487.5 — Poche du fond d'une plaque autour de lettres : quelques secondes

- Poches et gravure 2,5D sur une pièce percée de centaines de trous (fond d'une plaque autour des lettres,
  gravure en relief) : le calcul passe de plusieurs minutes à quelques secondes (plaque de 705 lettres :
  plus de 6 min → 4,8 s), même trajectoire à la précision près.
### v0.487.6 — Correctif

- Retraits de régions : une petite région sans pièce percée de nombreux trous garde exactement le calcul
  d'avant le 0.487.5.
### v0.487.7 — Intersections : « Réunir » et « Contour extérieur » sur les gros dessins

- Points d'intersection › Réunir les objets qui se croisent / Contour extérieur seulement : le regroupement
  des objets qui se touchent est quasi immédiat (plaque de 10 000 objets : 2 min 20 → 4 s), mêmes résultats.
### v0.487.8 — Intersections : « Couper aux intersections » 4 fois plus rapide

- Points d'intersection › Couper aux intersections : 4 fois plus rapide sur les dessins chargés (281 objets,
  11 800 segments : 19 s → 5 s), mêmes morceaux.
### v0.487.9 — Processus des vignettes rendus quand ils ne servent plus

- Bibliothèque et Ouvrir : les processus qui tracent les vignettes des gros dessins sont arrêtés une minute
  après la dernière vignette (et par « Vider les mémoires ») — jusqu'à 900 Mo rendus au poste.
### v0.487.10 — F10 s'ouvre aussitôt

- Options (F10) : la première ouverture ne marque plus de temps d'arrêt (les cartes graphiques du poste sont
  lues en arrière-plan au démarrage ; avant : 2,7 s).
### v0.487.11 — Bibliothèque et Ouvrir : plus de gel sur les gros fichiers

- Choisir un gros dessin dans la bibliothèque ou la boîte Ouvrir ne fige plus la fenêtre : le grand aperçu
  et la fiche se calculent en arrière-plan (la vignette s'affiche en attendant) et sont gardés pour la
  séance (avant : environ 6 s de gel par clic sur un gros DXF).
- Changer la taille des vignettes : celles déjà tracées plus grandes sont réduites aussitôt, sans être
  retracées ; en agrandissant, l'ancienne s'affiche agrandie le temps que la nouvelle arrive.
### v0.487.12 — Récents, symboles, BAT et export sans gel

- Fichiers récents (avec aperçus) : l'aperçu d'un gros dessin se calcule en arrière-plan ; la liste reste
  utilisable.
- Poser un gros dessin de la bibliothèque : lu dans le fil de calcul (barre de progression s'il est long),
  la fenêtre ne gèle plus.
- BAT et Exporter : écrits dans le fil de calcul (barre de progression sur un gros dessin), la fenêtre ne gèle plus.
### v0.487.13 — Fenêtre BAT sans gel sur les gros dessins

- Fenêtre BAT : sur un dessin de milliers d'objets, l'aperçu de la page se calcule en arrière-plan ; changer
  un réglage ne fige plus la fenêtre.
### v0.487.14 — Programmes et vérification d'export sans gel

- Lire ou visualiser un gros programme machine, et la vérification qui suit un export : faits dans le fil
  de calcul (barre de progression si c'est long), la fenêtre ne gèle plus.
### v0.487.15 — Programme Datron 2 fois plus vite (plugin 1.23.1)

- Programme DATRON (SimPL, plugin BFM 1.23.1) : un gros programme s'écrit 2 fois plus vite (844 000
  mouvements : 9,9 s → 5,3 s), même programme.
- Plan de travail sans couleurs d'outils : repeint plus léger sur les gros dessins.
### v0.487.16 — Mémoire des parcours plafonnée

- FAO : les parcours gardés en mémoire pour éviter les recalculs sont plafonnés (environ 400 Mo) ;
  un très gros parcours n'est plus gardé, la mémoire ne gonfle plus au fil des calculs.
### v0.488.0 — Programmes appelés suivis (plugin 1.24.0)

- Programme SimPL (plugin BFM 1.24.0) : les programmes appelés (usermodule) sont lus et leurs mouvements
  tracés à leur place dans le visualiseur ; un programme appelé introuvable est signalé.
- F10 › FAO › « Programmes appelés : chemin machine = chemin du poste » : le chemin écrit pour la machine
  (lecteur réseau de la commande) est converti en chemin du poste ; plusieurs correspondances séparées
  par ; ; à défaut, le fichier est cherché tel quel puis à côté du programme appelant.
- Plugins : un plugin peut fournir la valeur par défaut d'une option de F10.
### v0.488.1 — Bibliothèque : double-clic, puis un clic pour poser

- Grande fenêtre de la bibliothèque : un double-clic sur un dessin ferme la fenêtre ; le dessin suit le
  pointeur dans le plan de travail et un clic le pose (centré, accrochage compris) ; Échap : rien n'est
  posé. Case « Double-clic : fermer la fenêtre et poser le dessin d'un clic » (cochée par défaut) ;
  décochée, le dessin est posé au centre de la vue comme avant.
- Option F10 › FAO « Programmes appelés » traduite en anglais.
### v0.489.0 — Ouvrir comme l'explorateur de Windows

- Fichier › Ouvrir : affichage « Détails (comme Windows) » par défaut — nom, date de modification, type
  et taille en colonnes (clic sur une colonne : tri ; largeurs réglables), icônes du système, aucun tracé
  de vignette (le grand aperçu du fichier pointé reste). « Affichage › Vignettes » en option, avec la
  taille des vignettes et le tri.
- Recherche : filtre le dossier affiché dès la frappe (plusieurs mots, jokers * et ?, sans casse ni
  accents) ; Entrée cherche aussi dans tous les sous-dossiers (avancement, Annuler garde ce qui est
  trouvé) ; changer de dossier efface la recherche, comme dans l'explorateur.
- « Sous-dossiers » : lecture au plus juste (dossiers cachés et système ignorés), barre d'avancement et
  Annuler sur les gros dossiers ou le réseau (ce qui est lu reste affiché). Aussi dans la bibliothèque.
- STEP (.stp, .step) dans Ouvrir, avec son filtre.
### v0.489.1 — BAT et impression réglables

- F10 › BAT : orientation (portrait par défaut, paysage, selon le dessin), échelle imposée (1:1, 2:1,
  1:2…), cartouche, cotes d'encombrement, légende des outils ; la fenêtre BAT part de ces réglages
  (puis retient les derniers choix).
- F10 › Impression (nouvel onglet) : ce que Ctrl+Maj+P imprime (demander, le dessin, la page BAT),
  format de la feuille (A4 par défaut), orientation (portrait par défaut), échelle (1:1 par défaut,
  2:1, 5:1, 1:2, 1:5, ajustée à la feuille), réduction si le dessin dépasse, position (centré ou en
  bas à gauche à la marge), marge, plaque, seulement la sélection. La boîte d'impression s'ouvre sur
  ce format et cette orientation ; la dernière imprimante choisie est retenue.
### v0.489.2 — Couleurs gardées : symboles, VND, pose et import

- Symboles (.smb) : les couleurs (outils) des objets sont gardées. Un symbole TypeEdit n'a pas de couleur ;
  VectorDrive ajoute après les données de TypeEdit un petit bloc de couleurs que TypeEdit ne lit pas (le
  symbole reste identique pour TypeEdit). Un symbole sans couleur prend toujours celle du calque où on
  le pose.
- VND : un calque dont les objets sont de plusieurs couleurs est écrit en un calque TypeEdit par outil
  (dans TypeEdit, un calque = un outil = une couleur) : chaque objet garde son outil.
- Poser un symbole ou un dessin de la bibliothèque, importer, glisser un fichier : les objets gardent
  leurs couleurs dans le dessin (outil de même couleur repris, sinon outil ajouté ; les outils du
  dessin ne changent pas).
### v0.489.3 — Couleurs des DXF et SVG gardées

- DXF lu : chaque couleur devient un outil du dessin (dans l'ordre où elle apparaît ; couleur vraie,
  couleur indexée, « du calque », « du bloc » ; le blanc des DAO compte pour le noir). DXF écrit : la
  couleur de chaque outil (couleur indexée la plus proche et couleur vraie) au lieu de « du calque ».
- SVG lu : couleur du trait (sinon du fond) de chaque objet, héritée des groupes, en outils ; le SVG
  écrit gardait déjà les couleurs.
- F10 › Fichiers « Couleurs des DXF et SVG lus gardées » (coché) ; décoché : tout à l'outil 1 comme avant.
### v0.489.4 — Couleurs des PDF, EPS et AI gardées

- PDF, EPS et Illustrator (AI) lus : la couleur de chaque tracé (trait, sinon fond ; gris, RVB ou CMJN)
  devient un outil du dessin, comme pour les DXF et SVG ; ces formats écrits par VectorDrive gardaient
  déjà la couleur de chaque outil : l'aller-retour garde maintenant les couleurs.
- F10 › Fichiers : « Couleurs des fichiers lus gardées (DXF, SVG, PDF, EPS, AI) ».
### v0.489.5 — Programme appelé choisi sur le poste (plugin 1.24.1)

- FAO › instruction « Appel d'un programme de la machine » : bouton « … » pour choisir le fichier sur le
  poste ; à l'écriture du programme (SimPL, plugin BFM 1.24.1), le chemin du poste devient celui de la
  machine par les correspondances de F10 › FAO › Programmes appelés (comme NeoDrive) ; un chemin déjà
  écrit pour la machine reste tel quel.
### v0.489.6 — Ouvrir : réglages par défaut, colonnes retenues

- F10 › Fichiers : affichage d'Ouvrir (Détails ou Vignettes), tri et taille des vignettes par défaut.
- Ouvrir : largeurs des colonnes de l'affichage Détails retenues d'une fois sur l'autre ; Ctrl+F place le
  curseur dans la recherche ; Échap efface la recherche (puis, recherche vide, ferme la fenêtre).
### v0.489.7 — Panneau Bibliothèque : double-clic, puis un clic pour poser

- Panneau Bibliothèque (ancré) : comme la grande fenêtre, un double-clic sur un dessin le fait suivre le
  pointeur, un clic le pose (Échap : rien). F10 › Fichiers « Bibliothèque : double-clic, puis un clic
  pour poser le dessin » (coché ; décoché : au centre de la vue), même réglage que la case de la grande
  fenêtre.
### v0.489.8 — BAT : logo et entreprise en en-tête

- F10 › BAT « En-tête : entreprise » et « En-tête : logo » (image PNG, JPEG…) : imprimés en haut à gauche
  de chaque BAT (logo de 10 mm de haut, proportions gardées), dans l'aperçu, le PDF et l'impression.
  Un logo introuvable est simplement omis.
### v0.489.9 — Correctif : sous-dossiers et recherche d'Ouvrir

- Ouvrir et Bibliothèque : « Sous-dossiers » et la recherche (Entrée) échouaient sur un dossier d'au moins
  25 sous-dossiers (v0.489.1 à v0.489.8) ; corrigé : l'avancement affiche « n dossiers lus, n fichiers
  trouvés ». Mesuré : 2 235 symboles en sous-dossiers listés en 0,5 s.
### v0.489.10 — Programmes appelés : copie locale, réseau absent sans attente

- Programme SimPL qui en appelle un autre : hors de l'atelier, la copie locale du programme appelé est
  trouvée dans un dossier parent du programme ouvert avec la fin du chemin de la machine (par exemple
  « T:\…\Tranch\Date.simpl » → « …\Tranch\Date.simpl ») ; essayé sur un programme de l'atelier : le
  programme appelé est tracé (1 954 mouvements au lieu de 1 256).
- Un partage réseau injoignable (atelier hors d'atteinte) n'est plus réessayé pendant une minute : les
  aperçus et vignettes de programmes ne restent pas en attente du réseau.
### v0.489.11 — Couleurs lues : teintes voisines regroupées

- Fichiers lus (DXF, SVG, PDF, EPS, AI) : les teintes voisines (PDF d'impression : noirs à peine
  différents, gris proches…) font un seul outil, et 16 outils au plus sont créés (au-delà : la couleur la
  plus proche). Un catalogue PDF de l'atelier passe de plus de 8 outils à 4.
### v0.489.12 — Symboles : couleurs gardées, réglable

- F10 › Fichiers « Symboles créés : couleurs gardées » (coché) : décoché, un symbole est écrit exactement
  comme par TypeEdit, sans le bloc de couleurs de VectorDrive.
### v0.489.13 — Ouvrir : chercher dans les textes des dessins

- Ouvrir : case « Dans les textes » à côté de « Sous-dossiers » : la recherche (Entrée) trouve aussi les
  VND et SMB dont un texte TypeEdit répond (client, référence…), le texte trouvé dans l'infobulle. Chaque
  fichier n'est lu qu'une fois (index gardé, comme la recherche de la bibliothèque) : sur tout un disque,
  la première recherche est longue (avancement et Annuler), les suivantes rapides (D:\Documents : 142 s
  puis 3,8 s).
### v0.489.14 — Recherche dans les textes 4 fois plus rapide

- Ouvrir › « Dans les textes » : les fichiers pas encore lus le sont d'avance, sur plusieurs processus
  quand ils sont nombreux ; première recherche sur tout un disque de dessins : 142 s → 33 s (suivantes :
  3 s, index gardé).
### v0.489.15 — Copier-coller : couleurs gardées

- Copier dans un dessin, coller dans un autre (onglets), ou « Coller au point » : les objets gardent leurs
  couleurs (outil de même couleur repris, sinon ajouté ; les outils du dessin ne changent pas).
- SVG copié dans un autre logiciel puis collé : ses couleurs sont gardées (F10 › Fichiers).
### v0.489.16 — Ouvrir encore plus proche de l'explorateur

- Ouvrir et Bibliothèque : les dossiers et fichiers cachés ou système de Windows (AppData, Cookies…) ne sont
  plus montrés, ni lus par « Sous-dossiers » et la recherche, comme dans l'explorateur.
- Affichage Détails : en-tête des colonnes à la hauteur d'une ligne ; le curseur de taille des vignettes
  n'apparaît qu'en affichage Vignettes.
### v0.489.17 — Impression : aperçu avant d'imprimer

- Imprimer (Ctrl+Maj+P) : aperçu de la feuille telle qu'elle sortira (format, orientation, échelle,
  position), dessin à l'échelle ou page BAT ; le bouton de l'aperçu imprime, l'imprimante choisie est
  retenue. F10 › Impression « Aperçu avant d'imprimer » (coché ; décoché : directement la boîte
  d'impression).
### v0.489.18 — Ouvrir : dossiers réseau plus rapides

- Ouvrir (Détails, tri par date ou taille, sous-dossiers) : la date et la taille de chaque fichier sont
  reprises de la lecture du dossier (Windows les donne avec la liste) au lieu d'un accès disque par fichier
  — sensible sur un partage réseau de milliers de fichiers.
### v0.489.19 — Impression en mosaïque à 1:1

- F10 › Impression « Plus grand que la feuille : à l'échelle sur plusieurs feuilles (mosaïque) » : au lieu
  d'être réduit, le dessin sort à l'échelle choisie (1:1…) sur plusieurs feuilles repérées A1, B1… (n/N),
  avec 6 mm de recouvrement et le cadre de la zone imprimée pour les assembler.
### v0.489.20 — Pose au clic : R pour tourner

- Poser un dessin de la bibliothèque d'un clic : R le tourne de 90° (Maj+R dans l'autre sens) avant de le
  poser ; le contour qui suit le pointeur montre la rotation.
### v0.489.21 — Ouvrir › Insérer : posé d'un clic

- Ouvrir › « Insérer dans le dessin » d'un seul dessin : il suit le pointeur et un clic le pose (R : tourner),
  comme depuis la bibliothèque (même réglage de F10 › Fichiers) ; plusieurs fichiers : au centre de la vue
  comme avant.
### v0.489.22 — Export DXF : un calque par outil

- Exporter › DXF : case « un calque par outil » (Outil 1, Outil 2…, chacun de la couleur de son outil) pour
  les logiciels de FAO qui travaillent par calque ; décochée, les calques du dessin comme avant.
### v0.489.23 — Éléments masqués : réglable

- F10 › Fichiers « Ouvrir et Bibliothèque : montrer les éléments masqués » (décoché, comme l'explorateur de
  Windows) : coché, les fichiers et dossiers cachés ou système sont montrés et lus.
### v0.489.24 — Ouvrir : chemin tapé, F5

- Ouvrir : un chemin tapé ou collé dans la recherche puis Entrée affiche ce dossier (ou ouvre ce fichier),
  comme la barre d'adresse de l'explorateur ; F5 actualise la liste.
### v0.489.25 — Ouvrir : colonne Emplacement

- Ouvrir (Détails) : dans Récents, Favoris et Accès rapide, une colonne « Emplacement » donne le dossier de
  chaque fichier (deux fichiers de même nom se distinguent) ; masquée quand on parcourt un dossier.
### v0.489.26 — Bibliothèque : recherche dans tous ses formats

- Recherche de la bibliothèque : les DXF, VDZ, VND et SVG sont trouvés par leur nom, les SMB et les VND
  aussi par leurs textes TypeEdit ; les fichiers pas encore lus le sont en une fois, sur plusieurs
  processus s'ils sont nombreux.
### v0.489.27 — BAT : bouton Imprimer

- Fenêtre du BAT : bouton « Imprimer… » qui envoie ce BAT à l'imprimante (aperçu avant impression selon
  F10 › Impression, imprimante retenue) au lieu d'écrire le PDF.
### v0.489.28 — VND : couleurs des outils dans TypeEdit

- VND écrit : les couleurs des outils du dessin sont reportées dans la table des outils de TypeEdit (fin de
  document) — TypeEdit doit montrer les mêmes couleurs que VectorDrive, sans fichier compagnon. Seule la
  couleur de chaque outil existant change ; un VND déjà à ces couleurs reste identique.
### v0.489.29 — Ouvrir : dernières recherches

- Ouvrir : les 20 dernières recherches lancées (Entrée) sont retenues et proposées dès la frappe.
### v0.489.30 — Fiche d'un dessin : ses couleurs

- Ouvrir et Bibliothèque : la fiche d'un dessin à plusieurs couleurs indique combien d'outils il emploie
  (« 3 couleurs (outils 1, 2, 4) »).
### v0.489.31 — Programmes appelés : la conversion de NeoDrive reprise (plugin 1.24.2)

- Plugin BFM 1.24.2 : la valeur par défaut de F10 › FAO › Programmes appelés reprend la conversion réglée
  dans NeoDrive sur le poste (lecteur P: de l'atelier), puis le partage réseau en secours.
- Plusieurs correspondances pour le même chemin machine : essayées dans l'ordre à la lecture ; chacune
  redonne le chemin machine à l'écriture.
### v0.489.32 — Symboles : aperçu en couleurs

- Symbole créé : son aperçu intégré (petites vignettes de la bibliothèque, navigateur de symboles de
  TypeEdit) est tracé aux couleurs des outils, sur la palette standard du fichier ; sans couleur, en noir
  comme avant.
### v0.489.33 — Couleurs : 10 outils comme TypeEdit

- Couleurs des fichiers lus : regroupées en 10 outils au plus, comme la table des outils d'un document
  TypeEdit.
- VND : un dessin qui emploie un outil au-delà du 10e garde ses couleurs dans le compagnon .vdz.
### v0.489.34 — Ouvrir : dossiers réseau sans gel

- Ouvrir et Bibliothèque : un dossier réseau (partage, lecteur réseau de l'atelier, accès rapide) est lu
  en arrière-plan, liste et dépliage de l'arbre : un partage hors d'atteinte ne fige plus la fenêtre
  (barre d'avancement et Annuler s'il tarde).
### v0.489.35 — Ouvrir : récents réseau sans attente

- Ouvrir › Récents : un fichier d'un partage réseau n'est plus vérifié dans le fil de l'interface (ni son
  existence, ni sa date, ni son icône) : un partage hors d'atteinte ne fige pas la liste.
### v0.489.36 — Bibliothèque : récents et favoris réseau sans attente

- Bibliothèque (et Ouvrir) : les récents et favoris situés sur un partage réseau sont gardés sans être
  vérifiés à l'ouverture : un partage hors d'atteinte ne fige plus la fenêtre.
### v0.489.37 — Menu Récents : réseau sans attente

- Fichier › Récents : un fichier d'un partage réseau n'est plus interrogé à l'ouverture du menu (taille et
  date laissées vides) : le menu s'ouvre aussitôt, même hors d'atteinte du lecteur réseau de l'atelier.
### v0.489.38 — Couleurs lues : le noir à l'outil 1

- DXF, SVG, PDF, EPS, AI lus : le noir (ou le blanc des logiciels de DAO), s'il est employé, prend l'outil 1
  — celui que les modèles de FAO usinent d'office — même s'il n'apparaît pas en premier dans le fichier ;
  un fichier d'une seule couleur reste tout à l'outil 1.
### v0.489.39 — Ouvrir : imprimer sans ouvrir

- Ouvrir › clic droit sur un dessin › « Imprimer… » : le dessin est imprimé à l'échelle selon F10 ›
  Impression (aperçu d'abord) sans être ouvert dans un onglet.
### v0.489.40 — Bibliothèque : imprimer sans ouvrir

- Bibliothèque (grande fenêtre et panneau) : clic droit sur un dessin › « Imprimer… », comme dans Ouvrir.
### v0.489.41 — Impression d'un dessin vide

- Imprimer un dessin vide : « Rien à imprimer » au lieu d'une feuille blanche.
- Bibliothèque : l'indication de la recherche dit ce qu'elle trouve (noms des fichiers, textes des
  symboles et des VND).
### v0.489.42 — Ouvrir : colonne Type parlante

- Ouvrir (Détails) : la colonne Type donne le nom du format (« AutoCAD DXF », « Symbole TypeEdit »,
  « TypeEdit / Gravostyle », « STEP (vue de dessus) »…) et « Programme … » pour un programme machine.
### v0.489.43 — F10 › BAT : choisir le logo

- F10 › BAT › logo : le bouton « … » ouvre une boîte « Ouvrir » filtrée sur les images (PNG, JPEG…) au lieu
  de celle du fichier d'outils.
### v0.489.44 — Essais : Temp nettoyé

- Les essais et l'autotest suppriment leurs fichiers temporaires en fin de passage, y compris lancés par
  « python -m unittest » : plus de dossiers tmp* qui s'accumulent dans le Temp de Windows.
### v0.490.0 — Vue 3D : choisir des faces et des contours fermés

- Vue 3D d'une pièce STEP, STL ou 3D XML : nouvelle liste « Clic : choisir des faces » / « Clic : choisir des
  contours fermés ». Un clic choisit la face visée (en orange) ou le contour fermé de cette face le plus proche
  du clic (en magenta) ; Ctrl ou Maj en ajoute, un second clic en retire, un clic dans le vide ou Échap efface.
- La sélection est résumée sous la barre : nombre, aire, hauteurs (horizontale, verticale).
- Faces d'un STEP : celles du fichier. STL, 3D XML et volumes : triangles regroupés jusqu'aux arêtes vives.
- En affichage filaire, les faces choisies sont dessinées pleines.
### v0.490.1 — Vue 3D : usiner les faces et les contours choisis

- Vue 3D, bouton « Usiner la sélection » :
  - « Balayage 3D de la sélection » : une opération Surface 3D limitée aux faces choisies (ou à l'intérieur
    des contours choisis), à la profondeur de la sélection. L'outil évite toujours toute la pièce : il ne
    balaie que là où il touche les faces choisies, pas là où une paroi voisine le tient au-dessus ;
  - « Contours dans le dessin » : les contours fermés de la sélection deviennent des formes du dessin,
    à usiner avec les parcours 2D ;
  - « Poche jusqu'à ce fond » (fond plat choisi) : ses contours dans le dessin et une poche à sa profondeur ;
  - « Remplacer la zone de » une opération 3D par la sélection, « Montrer la zone de » une opération.
- Formulaire de la Surface 3D : zone (faces ou contours, décocher pour toute la pièce), débordement autour
  de la zone, distance entre passes.
- La Surface 3D lit aussi les pièces STL et 3D XML ; pièce relue une seule fois tant qu'elle ne change pas ;
  les paliers inutiles sous le point le plus bas sont sautés.
### v0.490.2 — Ébauche 3D par paliers en Z

- Nouvelle stratégie « Ébauche 3D (paliers en Z) » pour les pièces STEP, STL et 3D XML. À chaque palier,
  l'outil enlève tout ce qu'il peut sans entamer la pièce ni la surépaisseur laissée, en anneaux depuis le
  bord, avec une entrée en rampe depuis le palier précédent. Un palier est ajouté juste au-dessus de chaque
  fond plat, pour qu'il ne garde pas plus que la surépaisseur.
- Zone : toute la pièce, ou au-dessus des faces et contours choisis dans la vue 3D.
- Vue 3D : le bouton devient « Usinage 3D », avec l'ébauche et le balayage de la sélection ou de toute la
  pièce.
- Surface 3D : l'outil descend aussi tout autour de la pièce, jusqu'en bas.
### v0.491.0 — Automatismes d'usinage 3D

- Vue 3D › Usinage 3D › « Automatisme d'usinage 3D… » : une suite d'étapes appliquée d'un coup à la pièce,
  ou aux faces et contours choisis. Suites livrées : Ébauche et finition ; Ébauche, demi-finition,
  finition ; Ébauche seule ; Finition seule.
- Les outils sont proposés d'après la pièce et les outils disponibles (ceux du document, puis Mes outils) :
  - ébauche : la plus grosse fraise qui tient dans la pièce et descend assez profond ;
  - demi-finition : une boule d'environ la moitié de l'outil précédent ;
  - finition : une boule de rayon au plus égal au plus petit rayon creux de la pièce (STEP).
  S'il manque un outil, il est créé.
- Les réglages en découlent : passe en Z de l'outil, distance entre passes de la boule pour une crête de
  0,01 mm, pas de la carte. La finition qui suit une ébauche suit la surface en une passe.
- Tout se modifie dans la fenêtre :
  - les étapes : ajouter, retirer, monter, descendre, désactiver ;
  - pour chaque étape : la stratégie, l'outil (proposé ou choisi), la surépaisseur, la passe, la distance
    entre passes et le sens.
- « Enregistrer sous… » garde la suite sous un nom pour d'autres pièces. Les plugins peuvent en ajouter.
- « Créer les usinages » ajoute les outils et les opérations au panneau FAO, en une seule annulation, et
  calcule les parcours.
### v0.491.1 — Reprise 3D, niveaux constants, pentes

- Nouvelle stratégie « Reprise 3D » : la matière que l'outil d'avant, plus gros, a laissée dans les creux et
  les angles, enlevée par paliers avec un outil plus petit, là seulement.
- Nouvelle stratégie « Niveaux constants 3D » : l'outil fait le tour des parois à chaque cote, pour finir les
  parois raides que le balayage marque. La passe d'une boule est calculée pour une crête de 0,01 mm.
- Balayage 3D et niveaux constants : limites de pente (« pentes d'au moins / d'au plus », en degrés).
- Nouvel automatisme « Ébauche, reprise, finition des pentes et des parois » :
  - ébauche ;
  - reprise avec une fraise moitié plus petite ;
  - balayage des pentes jusqu'à 50° ;
  - niveaux constants sur les parois à partir de 40°.
- Vue 3D › Usinage 3D : « Niveaux constants de la sélection ».
### v0.492.0 — Vue 3D : corps et mécanismes

- Pièces à plusieurs corps (solides d'un STEP, morceaux séparés d'un STL, volumes du dessin) : bouton « Corps »
  de la vue 3D. Chaque corps se montre ou se masque ; une couleur par corps en option.
- « Mécanismes et animation… » repère les contacts entre corps :
  - plans en vis-à-vis, au jeu près (0,3 mm par défaut) ;
  - cylindres coaxiaux (STEP).
- Il en déduit la liaison :
  - appui plan, le corps peut s'écarter ;
  - glissière, avec le sens donné par une butée ;
  - pivot, pivot glissant ;
  - encastrement.
- Le mouvement libre de chaque corps se lit à partir du corps fixe : le plus gros, ou celui choisi.
- Tout est réglable : écart des contacts, des directions, recouvrement mini, jeu des cylindres, corps fixe,
  course, rotation.
- Animation dans la vue 3D : curseur de « Fermé » à « Ouvert », lecture en va-et-vient. Pour chaque
  mouvement : animé ou non, course, sens inversé. La vue se tourne pendant l'animation.
- Exemple : un moule en trois parties assemblées en queue d'aronde → deux glissières, les parties latérales
  coulissent le long de la partie centrale.
### v0.492.1 — Usinage 3D sur toutes les faces

- Opérations 3D : « Face vers l'outil » (dessus, dessous, côtés) pour une seconde prise. La pièce est
  retournée avec la même rotation et la même position (centrée sur la plaque, dans le coin…) ; les contours
  choisis suivent.
- « Corps usiné » : un seul corps d'une pièce à plusieurs corps, posé comme une pièce à part.
- Automatisme d'usinage 3D, deux nouveaux choix :
  - « Corps » : toute la pièce, chaque corps séparément, ou un corps ;
  - « Prises : toutes les faces ».
  Les prises qui atteignent toute la surface sont proposées : chaque fois celle qui en atteint le plus, en
  privilégiant les surfaces vues de dessus. Ce qui reste hors d'atteinte en 3 axes est signalé.
- L'automatisme est répété pour chaque prise de chaque corps, chaque prise précédée d'un message à
  l'opérateur « Poser … : … vers l'outil ». Les outils sont créés une seule fois pour toutes les prises.
### v0.492.2 — Vue 3D par prise

- Vue 3D : liste « Prise ». Elle montre la pièce, ou le corps, posée comme pour les usinages d'une prise
  (face vers l'outil, corps seul), avec leurs seules trajectoires ; on vérifie ainsi chaque retournement.
- Panneau FAO › réglage : « Automatisme d'usinage 3D… » quand le dessin vient d'une pièce 3D.
### v0.492.3 — Sélection sur une prise montrée

- Vue 3D, prise montrée (corps seul, retourné) : les faces et les contours choisis là créent un usinage
  de cette prise ; les contours retombent au même endroit de la pièce.
### v0.493.0 — Les fonctions de la machine choisie

- Plugins : une machine fait apparaître ses fonctions quand on la choisit (F10 › FAO, autre dessin, modèle
  d'usinage) :
  - boutons du ruban et panneaux ancrés réservés à certaines machines ;
  - plugins prévenus quand la machine change ;
  - « Post-traitement » propre à une machine (nom du travail, dossier, quantité…) à la place de la boîte
    « Enregistrer » ordinaire.
- Post-traitement : le post-processeur reçoit le dossier d'écriture tel que la machine le voit
  (correspondances de F10 › FAO › chemins des programmes). Une fiche machine compte pour la machine qu'elle
  désigne.
### v0.493.1 — Réglages propres à une machine

- Les réglages propres à un post-processeur (par exemple la touche de fonction du pupitre d'une machine)
  sont gardés avec le dessin.
### v0.493.2 — Documentation : fonctions propres à une machine

- docs/ARCHITECTURE.md : comment un plugin fait apparaître les fonctions d'une machine quand on la choisit
  (commandes et panneaux réservés, machine changée, post-traitement propre, réglages gardés avec le dessin,
  dossier vu par la machine).
### v0.494.0 — Usiner les volumes du dessin

- Les volumes modélisés dans VectorDrive (pavés, extrusions, booléens, pousser-tirer…) s'usinent comme une
  pièce 3D : faces et contours choisis, ébauche, reprise, balayage, niveaux constants, automatismes, prises
  (face vers l'outil, volume seul), corps et mécanismes. On modifie la pièce en volumes, puis on l'usine.
- Vue 3D, « Volumes du dessin » : leurs trajectoires calculées s'y affichent.
### v0.494.1 — Pièce 3D convertie en volumes du dessin

- Vue 3D › Usinage 3D (ou Corps) › « Convertir en volumes du dessin » : chaque corps de la pièce (STEP,
  STL, 3D XML) devient un volume du dessin, à modifier avec les outils 3D (booléens, pousser-tirer…) puis à
  usiner.
- Le maillage est réparé : jonctions en T coupées, petits trous bouchés, triangles réorientés. Un corps qui
  ne se ferme pas est signalé, avec la raison.
- Lecteur STEP : les sommets du bord d'une face reprennent exactement les points de ses arêtes, partagés avec
  la face voisine. Le maillage a beaucoup moins de fentes.
### v0.494.2 — STEP : triangles plats retirés

- Lecteur STEP : les triangles plats (aire nulle) sont retirés à la lecture, avec leur couleur et leur face.
  Le maillage est plus léger et plus propre pour l'affichage, l'usinage et la conversion en volumes.
### v0.494.3 — Guide de l'usinage 3D

- docs/usinage_3d.md : sélection de faces et de contours, commandes « Usinage 3D », stratégies, automatismes
  (outils proposés, toutes les faces, chaque corps), prises, corps, mécanismes et animation, modification
  de la pièce en volumes.
### v0.495.0 — Trous d'une pièce 3D → perçages

- Vue 3D › Usinage 3D › « Trous de la pièce → perçages » (pièce STEP) : les trous cylindriques verticaux
  sont repérés. Les faces d'un même trou sont réunies, et les congés et rainures (cercle incomplet) sont
  écartés. Chaque trou donne un cercle dans le dessin (calque actif) et chaque diamètre un perçage, à la
  profondeur du trou ; un trou débouchant descend de 0,5 mm de plus.
- Perçage au foret du bon diamètre s'il y en a un (dessin, puis Mes outils), sinon perçage à la fraise en
  hélice.
### v0.495.1 — Automatisme 3D : un outil créé une fois

- Automatisme d'usinage 3D : quand deux étapes demandent le même outil à créer (deux finitions à la même
  boule), il n'est proposé et créé qu'une fois.
- Fenêtre de l'automatisme : plus de reste de l'ancien tableau en haut à gauche quand on change de suite,
  de corps ou de prises.
### v0.495.2 — Automatisme 3D : pas plus bas que l'outil

- Automatisme d'usinage 3D : une étape ne descend pas plus bas que la longueur utile de son outil, au-delà de
  laquelle le porte-outil toucherait la pièce. La fenêtre indique les outils concernés : prendre des outils
  plus longs, ou usiner le reste depuis d'autres prises.
### v0.495.3 — Usinage 3D : corrections

- Trous d'une pièce 3D : un trou ouvert par-dessous n'est plus percé du dessus. Les trous de même diamètre
  mais de profondeurs différentes ont chacun leur perçage. Un trou dont le centre tombe sur un demi-pas
  n'est plus perdu.
- Balayage des faces choisies : les faces en pente sont balayées entièrement (avant, presque rien).
- Niveaux constants sur des parois choisies : les parois verticales sont prises en compte.
- Ébauche 3D : un plan incliné ne compte plus comme des centaines de fonds plats (des centaines de paliers
  inutiles).
- Reprise 3D : plus de faux reste au bord de la zone.
- Corps usiné inconnu : toute la pièce, à sa place sur la plaque.
- Mécanismes :
  - sens du dégagement juste quand un corps en enveloppe un autre (noyau dans une empreinte) ;
  - un corps encastré suit le mouvement de son parent ;
  - un corps pris entre deux plans glisse dans le plan ;
  - le sens des normales d'un maillage est vérifié par son volume.
- Automatisme 3D :
  - quand aucune fraise ne tient dans la pièce, la plus petite est proposée ;
  - les contours choisis sur une prise montrée sont ramenés au dessin ;
  - les prises proposées viennent de la pièce telle que lue.
- Conversion en volumes : chaque coque d'un maillage est orientée (une cavité reste une cavité).
### v0.496.0 — Plaque codée depuis un préréglage

- « Plaque codée » sans cadre sélectionné : la plaque type entière (cadres, code, texte) est posée d'un coup
  depuis un préréglage, au centre de la plaque. Préréglages livrés : DataMatrix 15 × 7, code carré 10 × 10,
  QR 20 × 20.
- « Enregistrer les cadres sélectionnés comme préréglage… » garde une plaque type dessinée (fenêtres du code
  et du texte, symbologie, police) pour la réutiliser.
### v0.497.0 — Mécanismes : réglages gardés avec le dessin

- Fenêtre « Mécanismes » : les réglages du repérage (écarts, recouvrement, jeu, corps fixe, course, rotation)
  et ceux de chaque mouvement (animé ou non, course, sens inversé) sont enregistrés avec le dessin et
  retrouvés à la réouverture. Ouvrir la fenêtre ne modifie pas le dessin ; les réglages d'une autre pièce
  (autre nombre de corps) sont ignorés.
### v0.497.1 — Pièce 3D : corps fermés en volumes

- « Convertir en volumes du dessin » ferme désormais les corps dont deux faces voisines posent la même
  languette dos à dos, ou dont deux petits trous se touchent en un sommet ; les débris sans volume laissés par
  les bouchages sont écartés. Les corps d'un moule de plusieurs pièces deviennent des volumes du dessin, à
  percer, couper ou compléter puis à usiner.
### v0.497.2 — STEP : surfaces extrudées maillées sur toute leur hauteur

- Lecture STEP : une surface extrudée (SURFACE_OF_LINEAR_EXTRUSION) est maillée sur toute la hauteur de sa
  face — le vecteur d'extrusion n'en donne que l'unité. Avant, une face plus haute que trois fois ce vecteur
  restait vide (ou déformée) : un trou dans la pièce, que l'usinage 3D prenait pour un creux.
### v0.498.0 — Mécanismes : contrôle des collisions

- Fenêtre « Mécanismes » : « Contrôler les collisions » déplace les corps, fermés en volumes, pas à pas sur
  la course réglée. Deux corps qui prennent un volume commun s'interpénètrent : au repos, ou dès la position
  trouvée (affinée), avec la course parcourue et le volume en cause ; la vue se met à cette position. Deux
  faces en contact ne comptent pas. Les corps impossibles à fermer sont signalés.
### v0.498.1 — Mécanismes : course jusqu'à la butée

- Fenêtre « Mécanismes » : « Course jusqu'à la butée » mesure, pour chaque mouvement animé pris seul, ce que
  le corps parcourt avant de heurter un autre corps, et règle sa course dessus (gardée avec le dessin) ; un
  corps libre sur toute sa course la garde.
- Contrôle des collisions : avec moins de deux corps fermés en volumes, la fenêtre dit qu'il n'y a rien à
  contrôler (au lieu de « aucune collision »). Volume commun toléré abaissé (1e-7 du plus petit corps).
### v0.499.0 — Trous d'un maillage ; mécanismes : corrections

- « Trous de la pièce → perçages » marche aussi sur un maillage (STL) et sur les volumes du dessin percés ou
  modifiés : une face aux parois verticales posée sur un cercle (8 sommets au moins) est un cylindre, un trou
  si elle regarde l'axe. Un perçage fait dans un corps converti en volume redevient un perçage.
- Mécanismes, corrections :
  - « Course » et « Rotation des pivots » s'appliquent de nouveau après un premier repérage ; une course réglée
    à la main est gardée tant que la course repérée ne change pas ;
  - les facettes de deux cylindres ajustés ne sont plus prises pour une collision (épaisseur tolérée
    0,05 mm), la position de la butée restant précise ;
  - deux corps qui s'interpénètrent au repos restent contrôlés pendant le mouvement ;
  - « Course jusqu'à la butée » règle une course du côté libre ; un corps bloqué dès le départ garde sa
    course (sens à inverser) ;
  - un corps non animé suit encore son parent ; le message donne la course du corps qui bouge ;
  - une surface ouverte n'est pas un volume contrôlé ;
  - les réglages gardés ne s'appliquent qu'à la même pièce (mêmes corps), et jamais à un autre dessin.
### v0.500.0 — Reprise 3D sur la matière vraiment laissée

- Reprise 3D : la matière à reprendre est celle que l'outil d'avant a vraiment laissée (comparaison des
  surfaces atteintes par les deux outils). Avant, toute une bande au pied des parois, que l'outil d'avant ne
  pouvait pas approcher, passait pour du reste et était balayée palier après palier. Un point n'est repris
  qu'une fois à sa cote ; les fentes où l'outil entre tout juste sont reprises ; chaque zone est faite sur
  toute sa profondeur avant la suivante, les segments enchaînés au plus proche, avec des sauts et des descentes
  au ras de la matière connue au lieu de remonter au dégagement. Sur une pièce de moule (prise du dessus,
  40 mm) : reprise fraise Ø4 après Ø8, de 2 h 05 à 4 min 39 ; boule Ø3 après Ø12, de 12 h 23 à 31 min.
- Nouvelle suite d'automatisme « Ébauche, finition, reprise des angles » : grosse boule à passes larges, puis
  petite boule seulement là où la grosse n'atteint pas (distance entre passes d'après la crête).
### v0.500.1 — Reprise 3D : le tour des parois

- Reprise 3D : à chaque palier, après le balayage d'une zone, l'outil fait le tour de ses parois. Les lignes de
  balayage, posées sur une grille, ne passaient pas au ras des parois qui leur sont parallèles : un coin
  gardait une bande de matière d'un pas. Au fond, le tour se fait 5 µm au-dessus.
### v0.500.2 — Reprise 3D : déplacements rapides sûrs

- Reprise 3D : les déplacements rapides redeviennent ceux de toujours (remontée au dégagement, descente rapide
  jusqu'à la hauteur d'approche, plongée). Depuis la v0.500.0, l'outil descendait et sautait en rapide « au
  ras » de la matière que l'outil d'avant était censé avoir laissée — or une ébauche par paliers laisse des
  marches sur les pentes (et une autre surépaisseur, une autre zone ou une autre profondeur en laissent
  davantage) : des rapides pouvaient y entrer. Le reste réel, l'ordre des zones et des segments et le tour des
  parois sont gardés. Pièce de moule (prise du dessus, 40 mm) : reprise fraise Ø4 après Ø8 en 11 min 46
  (2 h 05 avant la v0.500.0), boule Ø3 après Ø12 en 1 h 10 (12 h 23).
- Reprise 3D : chaque zone est calculée sur son seul cadre (plus rapide sur une pièce à nombreux creux) ; le
  centre de l'outil reste dans la zone choisie.
- Fenêtre « Mécanismes » : le tableau des mouvements, rempli de nouveau, ne laisse plus d'anciennes cases
  visibles par-dessus les nouvelles.
### v0.501.0 — Simulation : déplacements rapides dans la matière

- La simulation contrôle maintenant les déplacements rapides : un rapide qui passe dans la matière (outil et
  profil de son bout comptés, matière telle que les parcours d'avant l'ont laissée) est signalé avec sa
  position et sa profondeur, en rouge dans la fenêtre de simulation comme les collisions du porte-outil.
  Une remontée verticale depuis le point d'usinage n'est pas contrôlée. Aucune alerte sur les suites
  d'usinage 3D livrées ; sur les reprises des v0.500.0 et v0.500.1, ce contrôle signale les rapides fautifs.
### v0.501.1 — Reprise 3D : zones repérées plus vite

- Reprise 3D : les zones d'un seul tenant sont repérées par segments de ligne plutôt que point par point —
  mêmes zones, une quarantaine de fois plus vite sur des creux compacts.
### v0.501.2 — Guide : contrôler avant la machine

- Guide de l'usinage 3D (docs/usinage_3d.md) : nouvelle partie « Contrôler avant la machine » — simulation
  (porte-outil et déplacements rapides dans la matière, aussi dans la vue 3D en relief), reprise 3D, longueur
  utile des outils, collisions des mécanismes.

### v0.502.0 — Origine du dessin : zéro des programmes machine

- Comme le point zéro de TypeEdit, l'origine du dessin (Vue ▸ Repères ▸ Placer l'origine…, ou point zéro de
  la plaque : centre, coin…) devient le zéro X, Y des programmes machine : parcours, arcs, cycles de trous
  et brut sont décalés au post-traitement. Origine au zéro du dessin : programmes inchangés.

### v0.503.0 — Maj+D distance rectangle ; BAT de plusieurs gravures ; programmes ISO ouverts

- Maj+D : distance rectangle (comme TypeEdit) — clic au départ, clic à l'arrivée : le rectangle des deux
  points, ses côtés X et Y et la diagonale XY ; aussi dans le ruban (Mesure), à côté de « Mesurer ».
- BAT de plusieurs gravures cotées une à une : leurs cotes suffisent, celles d'encombrement de l'ensemble ne
  sont plus écrites (une seule gravure : inchangé).
- Un programme machine (.iso, .nc…) ouvert d'un double-clic, glissé sur la fenêtre ou repris des récents
  s'ouvre dans le visualiseur au lieu d'un refus « format non pris en charge ».

### v0.504.0 — Gravure 2,5D : passages étroits et pointes des angles

- Gravure 2,5D à l'outil conique (et sa finition « bords seulement ») : les parties plus étroites que le
  premier retrait — passage entre deux motifs (0,341 mm avec un outil 30° pointe 0,2 et un pas de 0,1 mm),
  traits fins, pointes des angles aigus — sont suivies par leur ligne médiane, la pointe descendant selon la
  demi-largeur locale, comme TypeEdit ; elles n'étaient pas gravées.

### v0.504.1 — STEP : tores maillés sans débordement

- Maillage des pièces STEP : une face torique dont le bord passe par le côté intérieur de l'anneau (l'angle
  ±180° du tube) ne déborde plus de l'autre côté du tube — elle recouvrait la face voisine et empêchait la
  conversion en volume.

### v0.504.2 — Programmes ISO : centres d'arcs absolus

- Lecture des programmes ISO : les centres d'arcs I J écrits en cotes absolues (comme la Cielle) sont
  reconnus — G90.1 / G91.1 s'ils sont écrits, sinon arc par arc, la lecture qui met le départ et l'arrivée
  à la même distance du centre. Les arcs de ces programmes n'étaient plus que des cercles énormes reliant
  les passes.

### v0.505.0 — Arcs G2 / G3 dans les programmes

- Les suites de segments d'un parcours (avances à Z constant) qui suivent un cercle à 0,01 mm près sont écrites
  en arcs par les post-processeurs qui savent en écrire : programmes deux à trois fois plus courts,
  mouvements plus doux. Écart garanti (sommets et flèches) sous la tolérance ; plongées, rampes, rapides et
  arcs déjà présents inchangés ; jamais sur une machine à axe rotatif. Réglage : FAO ▸ Arcs dans les
  programmes (0 = segments seuls). L'affichage et la simulation gardent les segments.

### v0.505.1 — Maillage STEP plus robuste

- Conversion des pièces STEP en volumes : un sommet ajouté sur le bord d'une face courbe (découpe de la
  triangulation) est posé sur la corde de la face voisine, et les trous dont le bord passe plusieurs fois par
  un même sommet sont retrouvés et bouchés même près d'arêtes partagées par trois triangles.

### v0.505.2 — Corrections : palpages et origine, tores, gravure 2,5D

- Origine du dessin = zéro du programme (0.502) : les positions des palpages (prises sur la sélection) suivent
  désormais l'origine comme les parcours — elles restaient au zéro du dessin, et un palpage de surface pouvait
  se faire à côté de la pièce. À vérifier sur tout programme écrit avec une origine déplacée depuis 0.502.
- STEP : une face torique qui fait le tour de l'axe (bourrelet, bord arrondi) est maillée du bon côté du tube
  (régression de 0.504.1).
- Gravure 2,5D : la liaison au fond entre deux anneaux se fait à la profondeur sûre (jusqu'à un pas de gravure
  de trop dans les canaux étroits).
- Programmes ISO : centres d'arcs absolus aussi dans les plans XZ / YZ.

### v0.505.3 — Moteur natif : plus de blocage sans fin

- Booléens et ombres portées : sur certaines formes (deux traits presque confondus), le moteur natif
  bouclait sans fin — VectorDrive attendait 20 s, passait au moteur de secours et laissait un calcul tourner
  jusqu'à la fermeture. Le moteur s'arrête maintenant de lui-même et le secours prend le relais aussitôt.

### v0.506.0 — Contrôle du programme écrit

- Chaque programme écrit est relu et comparé aux parcours dont il vient : un écart de plus de 0,05 mm (arc
  dans le mauvais sens, mouvement perdu, cote mal écrite…) est signalé avec sa position, en tête du message
  du post-traitement. Contrôle sauté (et dit) quand la relecture ne peut pas être exacte : cycles exécutés par
  la machine, axe rotatif, laser en morceaux.
### v0.507.0 — Gamme : lier au parcours précédent

- Nouvelle option d'opération « Lier au parcours précédent » (comme une gamme) : l'outil ne reprend que la
  matière laissée par les opérations d'avant — par exemple un cône fin qui nettoie les passages trop étroits
  pour la fraise d'ébauche, sans regraver l'air. Les liaisons au fond ne passent que là où la matière est déjà
  enlevée ; sinon l'outil remonte. Un avertissement dit quelle part du parcours est gardée, et prévient quand
  un outil plus gros est placé après (ordre conseillé : du plus gros au plus fin).
- Gravure en V : un cône descend jusqu'à sa queue (D2 de la fiche outil) ; une fiche sans diamètre ne limite
  plus la profondeur à 1 mm de large.
### v0.508.0 — BAT : logo en noir, cartouche en couleur

- BAT : coloriage « Logo en noir » (par défaut) — tous les contours fermés du dessin remplis en noir en
  pair-impair : un contour fermé dans un autre est vide, le suivant plein, comme un logo imprimé. L'ancien
  coloriage (teinte claire de la couleur de l'outil) reste au choix.
- BAT : couleur du cartouche au choix (noir, bleu, rouge, vert, orange, gris ou autre couleur) : traits,
  intitulés et fond clair ; toujours noir en impression noir et blanc.
- Clic droit sur un onglet : « Ouvrir le dossier contenant » — le dossier du dessin, du programme ouvert ou
  du fichier importé, le fichier sélectionné.
### v0.509.0 — Brut de la pièce 3D

- Pièce 3D (STEP, STL, 3D XML) : le brut se donne (FAO ▸ menu ▸ Brut de la pièce 3D…, vue 3D, automatisme
  3D) — bloc, barre ronde, plaque du dessin, ou boîte de la pièce agrandie de marges ; surépaisseur au-dessus
  de la pièce, décalage, matière ; « Ajuster à la pièce ».
- Ébauche 3D avec un brut : paliers depuis le haut du brut (au-dessus de la pièce), tout le brut vidé autour
  de la pièce et rien hors de lui ; approche au-dessus du brut. Avertissement si la pièce dépasse du brut ou
  si le brut est trop mince.
- Automatisme 3D : la longueur utile des outils est comptée depuis le haut du brut ; le brut est rappelé
  dans la fenêtre. Vue 3D : arêtes du brut autour de la pièce (case Plaque).
### v0.510.0 — Pièce 3D posée sur n'importe quelle face

- Pièce 3D : elle peut être posée sur n'importe quelle face plane, plus seulement sur les six faces des axes,
  pour usiner le dessus. Vue 3D, une face choisie : « Poser la pièce sur cette face (usiner le dessus) » ou
  « Tourner cette face vers l'outil » ; la pièce est alignée sur les axes (plus petit rectangle englobant).
- Placer la pièce 3D : les faces d'appui stables (planes, toute la pièce d'un même côté) sont proposées avec
  leur aire.
### v0.511.0 — Espace de travail : étaux, mandrins, collisions

- Espace de travail (nouveau module) : la table de la machine et le matériel de serrage autour de la pièce
  — étau (mors, cales parallèles), mandrin (mors radiaux), bride, cale, bloc, cylindre, table, ou modèle
  STEP / STL importé — gardés avec le dessin, ou sous un nom pour les reprendre (dossier
  `espaces_de_travail` ; les plugins peuvent en livrer).
- Serrage : l'étau (ou le mandrin) se place sur le brut de la pièce 3D, mors sur ses grands côtés,
  ouverture à sa largeur, la prise voulue dans les mors ; prise proposée d'après les parcours : le plus de
  serrage possible sans que les mors montent à moins d'1 mm sous les coupes les plus basses près d'eux,
  avertissement sous 3 mm de prise.
- Collisions : avant l'écriture du programme, un parcours dont l'outil ou le porte-outil touche le
  matériel est bloquant (premier point, élément touché). Le corps d'un cône s'élargit avec la hauteur :
  graver près d'un mors ne donne pas de fausse alerte.
### v0.512.0 — Fenêtre « Espace de travail »

- FAO ▸ menu (et menu de la vue 3D) ▸ « Espace de travail (étau, mandrin, brides)… » : liste des
  éléments, dimensions et position de chacun, « Serrer le brut », « Prise proposée », « Vérifier les
  parcours », espaces gardés (charger, enregistrer sous, supprimer). Un espace chargé se recale sur le
  brut : l'étau le serre et la table, les cales, les brides le suivent.
- Vue 3D : le matériel est dessiné autour de la pièce (avec « Plaque »), pour la première prise.
### v0.513.0 — Automatisme 3D : au-dessus des mors de l'étau

- Automatisme d'usinage 3D : avec un étau (ou un mandrin) dans l'espace de travail, la première prise
  s'arrête à 1 mm au-dessus du haut des mors (« Rester au-dessus des mors », coché par défaut) ; le
  dessous se fait dans une autre prise. Ligne « Espace de travail » et bouton « Espace de travail… »
  dans la fenêtre.
- Espace de travail : « Ajouter ▸ Modèle 3D importé » demande le fichier STEP ou STL (étau du fabricant,
  montage, machine) et le pose sous le brut.
### v0.514.0 — Rubans : tout tient en Full HD

- Rubans : les libellés des grands boutons passent sur deux lignes ; quand la place manque, les petits
  boutons gardent leur icône seule (le nom en infobulle), du groupe le plus large au plus étroit, avant
  tout repli en famille ; leurs libellés reviennent dès que la place le permet (écrans plus larges).
  En 1920 pixels, Fichier, Édition, Vue, Opérations, 3D, FAO et Options tiennent sans repli.
- Commandes en double retirées du ruban : chacune à une seule place (export STL dans Fichier, galbe et
  lissage dans 3D, placer la pièce 3D dans 3D, trajectoires et simulation 3D dans FAO, dimensions dans
  Édition, casse et ligne de base des textes dans l'onglet Mise en forme).
- Homonymes renommés : « Portion en arc », « Point sur courbe » (Mode Point), « Diviser (repères) »,
  « Mesurer (repères) » (Dessin technique). Icône pour « Quitter ».
### v0.515.0 — Plus aucun bouton muet

- Toute commande qui ne change rien de visible (dessin, sélection, outil, vue, fenêtre, message,
  presse-papiers, parcours, panneau 3D…) le dit dans la barre d'état : « « Commande » n'a rien changé : … »
  avec la raison probable — rien n'est sélectionné, aucune opération d'usinage, aucun parcours calculé,
  aucun relief ou aucun volume sélectionné — sinon ce que fait la commande. Les commandes qui affichent
  déjà leur propre message, ouvrent une fenêtre ou un menu ne sont pas concernées.
- « En courbes » convertit aussi un texte dont le contour n'avait pas encore été calculé (il ne
  faisait rien) ; sans texte ou sans police, il le dit.
### v0.516.0 — Vue 3D lisible en mode sombre, couleurs au choix

- Vue 3D : les arêtes de la pièce, la grille, les arêtes du brut, de la plaque et du matériel de
  serrage sortaient en noir sur certaines cartes graphiques (calcul d'éclairage appliqué aux traits) :
  elles prennent enfin leur couleur. Sur fond sombre, arêtes claires et grille discrète ; sur fond
  clair, arêtes foncées.
- Menu « Couleurs » de la vue 3D : couleur de la pièce, couleur des arêtes, couleurs d'origine (celles
  du fichier). Le choix est retenu d'une session à l'autre ; « Couleur par corps » reste prioritaire.
### v0.517.0 — Machines, broches et exemples STEP d'espaces de travail

- Espace de travail : deux nouveaux éléments — **Machine** (table rainurée et portique, passage sous la
  traverse réglable ; le portique est montré, pas vérifié) et **Broche** (écrou de pince, nez, corps) :
  la broche suit l'outil, son nez et son corps sont vérifiés contre le matériel au-dessus du
  porte-outil (« la broche touche… »). La table peut avoir des rainures en T.
- Mandrin à quatre mors : chaque paire serre son côté d'un brut rectangulaire.
- Table, machine et broche restent alignées sur les axes de la machine quand l'étau tourne pour serrer
  le brut (seuls l'étau et ses accessoires tournent).
- Exemples livrés, à charger, modifier et enregistrer sous son propre nom : machine à portique avec
  étau et broche, étau de 80 mm sur table rainurée, mandrin 4 mors Ø 125, table rainurée et brides (posées
  par rapport au brut), en plus de l'étau de 125 mm et du mandrin 3 mors.
- Bouton « STEP » de la fenêtre : exporter l'espace en STEP (pavés et cylindres en vraies faces, un
  solide coloré par volume) ou écrire tous les exemples en STEP — espaces complets et chaque matériel
  seul, centré — à retoucher dans un logiciel de CAO puis à réimporter comme « Modèle 3D importé ».
### v0.518.0 — Trajectoires 3D recomposées sur la pièce

- Vue 3D, liste des prises : « Prises : toutes (trajectoires recomposées) » — la pièce posée comme le
  dessin, avec les trajectoires de chaque prise (pièce retournée, face vers l'outil) et de chaque corps
  usiné seul ramenées sur elle : on voit d'un coup que chaque face de chaque pièce est usinée, et d'où
  vient l'outil. Les arcs sont aplatis ; une prise dont la pièce est illisible n'est pas montrée.
### v0.519.0 — Chaque prise tenue à sa façon

- Espace de travail par prise : la pièce retournée (ou un corps posé seul) peut avoir son propre
  matériel — un autre étau, un mandrin, des mors doux, des brides… Choisir la prise dans la vue 3D puis
  « Espace de travail… » : la fenêtre règle celui de cette prise (titre « prise : dessous »…), avec le
  brut et les parcours de cette prise seulement.
- La vue 3D montre le matériel de la prise affichée ; le contrôle avant écriture vérifie les parcours
  de chaque prise contre son propre espace ; l'usinage auto 3D reste au-dessus des mors de l'étau de
  chaque prise (une pièce retournée sans espace à elle : sans limite, comme avant).
- Sûreté (relecture) : la prise « dessus » de l'usinage auto 3D (pièce posée comme le dessin) est
  vérifiée contre l'étau du dessin et limitée par ses mors — elle ne l'était pas ; un corps usiné seul
  voit l'étau du dessin dans son propre repère (son haut à Z 0) ; l'écrou de pince de la broche est
  vérifié ; mandrin 4 mors tourné : chaque paire de mors sur le bon côté du brut ; les prises qui ne
  peuvent pas être vérifiées (sans matériel, broche sans dépassement d'outil connu) sont signalées.
- La fenêtre d'une prise vérifie exactement les parcours que vérifie le contrôle avant écriture ; une
  prise ouverte puis validée sans changement garde l'espace du dessin (pas de copie figée).
- Exports STEP (espaces de travail, outils) plus stricts : VECTOR en entité à part.
- En courbes : un texte dont la police manque n'est plus converti en Arial.
### v0.520.0 — Gravure en V profonde en paliers

- Gravure 2,5D à l'outil conique : réglage « Passe en Z de la gravure ». Une gravure profonde se fait en
  paliers, forme par forme : à chaque palier, tout ce qui doit être plus bas est creusé jusqu'à la cote
  (crêtes d'au plus un quart de passe, reprises au palier suivant) ; la dernière cote donne la forme exacte,
  la pièce finie est la même qu'en une fois. Aussi en ligne médiane (intaille). 0 : en une fois, comme avant.
- L'avertissement « … mm de profondeur en une passe » propose ce réglage.
### v0.521.0 — Simulation depuis le haut du brut

- Brut 3D plus haut que la pièce : la simulation (fenêtre, vue 3D, lecture pas à pas, mesure de volume)
  part du haut du brut dans son emprise. Le surfaçage se voit, et un déplacement rapide ou un porte-outil
  qui passerait dans cette matière (entre le haut de la pièce et le haut du brut) est signalé ; avant, la
  matière commençait au haut de la pièce.
- Parcours d'une autre prise (pièce retournée, corps seul) : simulés comme avant (autre repère).
### v0.522.0 — Plus de contrôles dans l'automatisme d'usinage 3D

- Prises : « Faces choisies » — cases dessus, dessous, côtés (cochées d'abord comme les prises proposées),
  part de la surface hors d'atteinte des faces cochées.
- « Réglages de l'étape… » : le formulaire complet de l'opération que crée l'étape (rampe, pentes, vitesses,
  hauteurs…) ; les champs changés sont gardés avec l'étape, pour toutes ses prises et à l'enregistrement.
- Colonne « Crête (mm) » pour les étapes à la fraise boule ; réglages propres de l'étape en info-bulle.
- « Aperçu des usinages » : les opérations qui seront créées, prise par prise (outil, profondeur, remarques).
### v0.523.0 — Surface 3D posée en 2D, et corrections de sûreté

- Vue 3D › « Poser sur une surface 2D (sous-onglet) » : la face choisie (ou des faces tournées du même côté),
  tournée vers l'outil — une des six faces, ou la pièce posée pour une face inclinée —, devient un calque du
  dessin avec son contour en guide. Ce qu'on y dessine s'usine dans cette prise, à partir de la hauteur de la
  face (dégagement gardé au-dessus de la pièce) ; les autres prises n'usinent jamais ces objets, et le contour
  n'est jamais usiné.
- Sûreté : une opération dont la prise est écrite « dessus » alors que c'est la face du dessin gardait mal le
  brut 3D — l'ébauche partait du haut de la pièce (premier palier trop chargé) et la simulation ne contrôlait
  pas la matière du brut. Corrigé.
- Gravure en V par paliers : une branche étroite garde son dernier anneau (crêtes bornées) ; les lignes
  médianes des parties étroites sont gravées en paliers aussi.
- Automatisme 3D : une seule prise sur une autre face que celle du dessin a sa consigne « poser la pièce ».
- « Poser la pièce sur cette face » : face d'une pièce à plusieurs corps bien orientée.
### v0.524.0 — Ctrl+chiffres sur clavier AZERTY

- Ctrl + une touche de la rangée des chiffres fait la commande de Ctrl+chiffre quelle que soit la disposition
  du clavier : en AZERTY, Ctrl+& … Ctrl+à font Ctrl+1 … Ctrl+0 (vues 2D/3D, sens, couleurs des outils,
  remplissage, tout voir…), comme dans TypeEdit — y compris la touche 6, où Ctrl+- ne fait plus que Ctrl+6.
### v0.525.0 — Corps positionné à part pour l'usinage

- Vue 3D, menu « Utiliser » : « Positionner ce corps à part pour l'usinage… » — pour une pièce à plusieurs
  corps (moule, assemblage), le corps des faces choisies reçoit sa propre pose : face tournée vers l'outil
  (six faces ou face d'appui plane du corps seul), rotation, position (centré, coin, origine, libre).
  « Comme l'ensemble » remet la pose commune. Annulable.
- Les usinages de ce corps (prise « corps seul ») se font dans sa pose ; une autre face du corps garde sa
  rotation et sa position. Les trajectoires reviennent sur l'ensemble (prise « toutes »).
- Le corps positionné apparaît dans la liste des prises de la vue 3D, même sans usinage ; il ne reprend pas
  l'espace de travail du dessin (il est tenu ailleurs) mais peut avoir le sien.
- Une surface choisie sur ce corps, posée sur un sous-onglet 2D, s'usine dans la pose du corps.
### v0.525.1 — Vue 3D et automatisme : brut compté, calculs gardés

- Vue 3D : quand le brut est montré et dépasse la pièce, la grille passe sous le brut et la coupe horizontale
  parcourt toute sa hauteur.
- Automatisme 3D : en « faces choisies », les zones atteintes de chaque face reprennent celles déjà calculées
  pour les prises proposées (ouverture plus rapide sur une grosse pièce).
### v0.526.0 — Relecture : surfaces 2D, arrêt entre deux prises

- Sûreté — automatisme 3D sur plusieurs prises (depuis la v0.492.1) : la consigne « Poser la pièce » entre deux
  prises était un simple message, que la machine affiche sans s'arrêter. Elle est maintenant une instruction
  « Retournement de la pièce » : remontée, broche coupée, attente de l'opérateur. **Un programme écrit avec
  l'automatisme 3D sur plusieurs prises, en v0.492.1 à v0.525.1, enchaîne les prises sans arrêt : le réécrire.**
- Vérification avant écriture : un passage à une autre prise sans arrêt entre les deux est signalé (bloquant
  quand la pièce doit être retournée).
- Surfaces posées en 2D (v0.523.0) :
  - poser une face tournée vers le haut (fond de poche, marche) ne retire plus au dessin ses calques ;
  - deux surfaces de la même prise gardent chacune leur cote — une opération n'usine que le calque de surface
    auquel elle est rattachée (une gravure aurait pu descendre de la différence de hauteur entre les deux) ;
  - objets ramenés sur un calque ordinaire, ou calque supprimé : la prise, la cote de départ et le dégagement
    reviennent comme avant ; une cote retouchée à la main n'est plus remise ;
  - un modèle de parcours ne garde plus la prise et la cote d'une surface ;
  - pièce placée autrement (rotation, position, plaque, corps posé à part) : le contenu des surfaces la suit ;
    tant qu'il ne l'a pas suivie, il n'est pas usiné ; « Ajuster la composition » ne les déplace plus ;
  - une face mal orientée dans le fichier est posée du bon côté (ou refusée).
- Corps positionné à part : l'espace de travail de sa prise est le bon, et la vue 3D suit sa nouvelle pose.
- Ctrl + rangée des chiffres : seulement sous Windows (autres systèmes : touches différentes), pas dans une
  fenêtre ouverte par-dessus.
- Plugin BFM 1.35.0 : le post G-code écrit l'arrêt (M0) ; le post ISO des fiches le signale.
### v0.526.1 — Vue 3D : trajectoires sur leur prise

- Vue 3D, une prise montrée : les trajectoires d'une surface posée en 2D n'apparaissent que sur sa prise, et
  sa prise est proposée dans la liste ; celles du dessin ne sont plus dessinées sur la pièce tournée
  autrement.
### v0.527.0 — Arrêts entre les prises en un clic

- Vérification avant l'écriture : quand des opérations usinent la pièce tournée autrement sans arrêt entre
  les deux, un bouton « Ajouter les arrêts » place une instruction « Retournement de la pièce » (broche
  coupée, parking, attente de l'opérateur) avant chacune ; le programme est à relancer ensuite.
- Vérification coupée : cet arrêt qui manque est quand même signalé avant l'écriture (ajouter les arrêts,
  écrire quand même ou renoncer).
- Vérification avant l'écriture : les points bloquants en tête de la liste, et l'en-tête dit combien il y en a
  (il disait toujours « Rien n'est bloqué »).
- Message de l'arrêt au retour à la prise du dessin : « Poser la pièce comme le dessin ».
### v0.527.1 — Relecture : surfaces posées gardées à l'enregistrement

- Surface posée en 2D : le sous-onglet garde sa surface à l'enregistrement et à la reprise de session. Avant,
  elle était perdue : à la réouverture, ses opérations retombaient sur la prise du dessin, à Z 0 (0.523.0 à
  0.527.0 — refaire les parcours des documents concernés).
- Document enregistré par ces versions : un calque qui a gardé le contour d'une surface mais perdu sa pose est
  signalé (bloquant) par la vérification avant l'écriture — refaire la pose et y remettre le contenu.
- Annuler après que le contenu d'une surface a suivi la pièce (placée, plaque changée) ne décale plus ce
  contenu au calcul suivant.
- Usinage par couleur d'une surface supprimée : il n'usine plus tout le dessin ; il n'usine rien et la
  vérification le signale (annuler la suppression le rétablit).
- Arrêt entre deux prises vérifié dans l'ordre des parcours écrits (parcours décoché, déplacé, arrêt retiré).
- Parcours déjà calculés refaits avant d'écrire, simuler ou faire la fiche quand une surface a suivi la pièce.
- Vue 3D : modèle rechargé quand la plaque change ; une prise « dessus » écrite n'apparaît plus en double.
- Automatisme 3D : la colonne « Outil » montre l'outil (elle était réduite à quelques pixels) ; la fenêtre
  s'élargit à l'ouverture.
### v0.527.2 — Relecture : programme écrit tel que vérifié

- Une opération désactivée (ou supprimée) après le calcul n'est plus écrite dans le programme. Avant, son
  parcours resté coché partait à la machine alors que la vérification l'ignorait.
- « Ajouter les arrêts » place l'arrêt juste après la dernière opération de la prise d'avant : un palpage ou un
  message prévu pour la prise suivante vient donc après le retournement.
- Un dessin enregistré en .vdz garde le lien vers sa pièce 3D. Rouvert, il retrouve ses prises, son placement et
  ses surfaces posées (sinon une surface « dessus » d'une pièce retournée pouvait passer pour la prise du dessin).
  L'onglet dupliqué et le compagnon d'un VND les gardent aussi.
- Les parcours calculés avant qu'une surface suive la pièce (placement, plaque, corps posé à part) sont
  recalculés avant d'écrire ; les parcours décochés restent décochés.
- Vérification coupée : tout ce qui rendrait le programme faux est quand même montré avant l'écriture (arrêt qui
  manque entre deux prises, surface qui a perdu sa pose, arrêt que le post ne sait pas écrire).
- Points bloquants : la touche Entrée ne fait plus « Écrire quand même ».
### v0.527.3 — Relecture : arrêts à leur place, pièce 3D sûre

- « Ajouter les arrêts » place l'arrêt après toute la prise d'avant, opérations décochées ou désactivées
  comprises. Avant, une opération de la prise d'avant décochée au moment de l'ajout, puis recochée, se
  retrouvait derrière l'arrêt : usinée sur la pièce retournée, sans avertissement.
- Un arrêt ajouté sait quelle prise il annonce : suivi d'une opération d'une autre prise, il est bloquant à la
  vérification (et montré même vérification coupée).
- Pièce 3D d'un dessin rouvert : celle du même nom à côté du dessin passe d'abord (dossier de travail copié avec
  une nouvelle révision). Si l'ancienne existe encore, la vérification le signale avec les deux chemins.
- Surfaces posées et opérations 3D d'un dossier déplacé (ou d'un lecteur réseau vu sous un autre nom)
  retrouvent la pièce du dessin : leur contenu suit de nouveau la pièce placée autrement.
- Un modèle de dessin ne garde plus la pièce 3D : un nouveau dessin n'y est pas lié en douce.
- Compagnon d'un VND : le contour d'une surface posée retrouve sa marque (sans elle il aurait été usiné).
- Parcours recalculés avant l'écriture : par document (changer d'onglet ne fait plus tout recalculer), aussi
  après la suppression de la dernière surface posée ; la liste reste comme on l'avait laissée (ordre, parcours
  inversés, parcours TypeEdit) ; un parcours retiré revient décoché, une opération nouvelle cochée. Simuler ou
  mettre sur la fiche ne remet plus les dates du jour.
- Vérification : une opération active sans parcours calculé (absente du programme) est signalée, un parcours
  décoché aussi. Écrire avec seulement des parcours d'opérations désactivées le dit au lieu de ne rien faire ;
  les parcours TypeEdit exportés suivent la même règle.
### v0.527.4 — Relecture : pièce 3D reliée, parcours TypeEdit et arrêts

- Pièce 3D du même nom à côté du dessin (dossier de travail copié), prise puis enregistrée : à la réouverture,
  les surfaces posées sur une face de côté gardaient l'ancien chemin et leur contenu pouvait se décaler sans
  avertissement (v0.527.3). Une surface posée est maintenant toujours rapportée à la pièce du dessin.
- Une surface dont la pièce n'est plus celle du dessin ne bouge plus (avant, elle suivait un placement par
  défaut).
- Une opération posée sur un autre fichier 3D du même nom, même absent, n'est plus remise sur la pièce du dessin.
- Un modèle de dessin ne garde pas non plus les surfaces posées : leur contenu y est signalé, pas usiné à côté.
- Compagnon d'un VND : un seul objet remarqué comme contour par contour de surface (un détourage tracé sur le
  bord reste usiné).
- Arrêts entre prises : un parcours TypeEdit (sans opération) compte comme usinage de la prise du dessin ; un
  arrêt ajouté ne passe plus devant lui ; un arrêt fait à la main après un arrêt ajouté est respecté ; un autre
  corps seul après un arrêt est à regarder, pas bloquant.
- Le message « rien à écrire » n'accuse plus des opérations désactivées quand le calcul a été annulé.
### v0.527.5 — Ajuster la composition et pièce 3D ; relecture

- Fenêtre « Plaque » : avec une pièce 3D, cocher « Ajuster la composition » dit ce que l'ajustement fera au
  dessin posé sur la pièce. La pièce ne change pas de taille et, sauf centrée sur la plaque, elle ne suit pas :
  le dessin se décalera d'elle. La barre d'état le redit une fois la plaque changée.
- Arrêts entre prises : une « Question à l'opérateur » ajoutée après un arrêt ajouté ne cache plus une prise
  différente derrière (v0.527.4). Seul un « Retournement » fait à la main change la pose annoncée.
- Un parcours recalculé seul (formulaire validé) reprend sa place : un parcours TypeEdit qui le suivait le suit
  toujours (v0.527.4 pouvait le faire passer devant : découpe avant gravure).
- Parcours TypeEdit sur la mauvaise prise : le message dit de le remettre à sa place ; « Ajouter les arrêts »
  n'est plus proposé quand il n'y pourrait rien.
- Surface posée rapportée à la pièce du dessin alors que celle sur laquelle elle a été posée existe encore avec
  un autre contenu (révision du même nom) : signalée. Surface qui n'est plus rapportée à sa pièce du tout :
  signalée aussi (son contenu reste où il était).
- Compagnon d'un VND : le contour d'une surface est reconnu au même outil d'abord.
### v0.527.6 — Pièce 3D qui suit la plaque ; relecture

- Pièce 3D centrée sur la plaque ou calée dans son coin : quand la plaque change, elle la suit aussi pour la prise
  du dessin (v0.527.5 ne la déplaçait qu'à l'écran). La barre d'état le dit ; une seule annulation remet plaque et
  pièce. Le dessin, lui, ne bouge qu'avec « Ajuster la composition ».
- Arrêts entre prises : une « Question à l'opérateur » seule entre deux prises différentes est signalée (elle ne
  dit pas de retourner la pièce) ; « Ajouter les arrêts » n'en ajoute pas par-dessus.
- Parcours TypeEdit placé après une prise retournée : le message dit de le remettre dans la liste avant le
  retournement. Message des arrêts manquants : rappelle de remettre dans l'ordre des opérations les parcours
  déplacés à la main.
- Un parcours recalculé seul (formulaire validé) garde l'ordre de la liste, même changé à la main ; un nouveau
  (arrêt ajouté) va juste avant le parcours de l'opération suivante.
- Pièce 3D du dessin introuvable : une seule note pour toutes les surfaces posées. Surface posée sur une copie de
  la pièce désarchivée avec une autre date : plus signalée comme « autre contenu » (seule la taille compte).
- Compagnon d'un VND : à outil égal, le contour au même rang passe devant.
### v0.527.7 — Pièce 3D qui suit la plaque sans relecture ; relecture

- Pièce 3D centrée sur la plaque ou calée dans son coin : quand la plaque change, sa vue (lecture du STEP) est
  déplacée, plus relue. Les objets restent les mêmes : une opération qui les désigne (détourage de la pièce…) les
  garde, ainsi que leurs retouches (v0.527.6 les recréait : l'opération ne trouvait plus rien). Plaque élargie
  sans que la pièce bouge (calée dans le coin) : rien n'est refait. Pièce devenue illisible : laissée où elle
  était, avec un message.
- « Ajuster la composition à la nouvelle taille » ne met plus à l'échelle la vue de la pièce 3D : elle suit la
  pièce, comme les surfaces posées.
- Barre d'état : le message « la pièce 3D a suivi la plaque » n'apparaît que si elle a bougé ; il donne le
  décalage, et ne conseille l'ajustement de la composition que si la plaque garde sa taille.
- Monter ou descendre une opération emmène ses parcours dans la liste (v0.527.6 gardait l'ancien ordre au
  recalcul d'une seule opération).
- Parcours TypeEdit avant une opération d'une autre prise : le message dit de le remettre avant le retournement,
  ou d'ajouter un arrêt (bouton s'il est proposé, sinon à la main).
- Surface posée dont la pièce du dessin n'a pas pu être lue : dit comme tel (plus « autre pièce »).
- Compagnon d'un VND : le contour d'une surface est de nouveau reconnu au même outil d'abord (v0.527.6 pouvait
  marquer un détourage à sa place).
### v0.527.8 — Parcours refaits quand la pièce 3D a bougé ; relecture

- Pièce 3D placée autrement depuis le calcul des parcours (elle a suivi la plaque, a été replacée, ou un corps
  posé à part, centré sur la plaque ou calé dans son coin, a suivi la plaque) : les parcours sont refaits avant
  l'écriture, et la barre d'état le dit. Avant, une opération 3D ou une gravure sur les contours de la vue de la
  pièce gardait ses anciens parcours, à côté de la pièce. Vaut aussi quand seule une opération avait été
  calculée, et pour l'export des parcours TypeEdit.
- Mode sélection : ce recalcul reprend les objets du dernier calcul (pas la sélection du moment, vide ou autre),
  et une opération refaite seule depuis son formulaire reprend tous ses objets.
- Contours de la vue de la pièce groupés (seuls ou avec du dessin) : ils suivent la pièce comme les autres, et
  disparaissent avec elle quand on la replace (plus de vue en double).
- « Ajuster la composition à la nouvelle taille » : la vue de la pièce n'y échappe que si la pièce suit la plaque
  (centrée ou calée dans son coin) ; sinon elle est ajustée avec le dessin, comme avant la v0.527.7 (vue du STEP
  utilisée comme dessin).
- Lecture de la pièce annulée pendant un changement de plaque : un message le dit (la pièce reste à sa place
  d'avant, à replacer). La sélection est vidée quand la pièce suit la plaque.
- « Fusionner les parcours » (regroupés par outil) : les parcours des opérations déplacées suivent le nouvel
  ordre, ceux des autres restent où on les a mis ; annuler la fusion remet aussi les parcours. Avant, le programme
  gardait l'ancien ordre jusqu'au prochain calcul complet.
- Interface en anglais : le message cite le vrai nom de la case « Ajuster la composition à la nouvelle taille ».
### v0.527.9 — Recalcul avant l'écriture fidèle au dernier calcul ; relecture

- Le recalcul fait avant l'écriture (pièce 3D placée autrement, surface posée, date du jour) rejoue le dernier
  calcul, quel que soit le mode du moment : en mode sélection, les mêmes objets ; en mode couleur, tous. Avant, un
  mode changé entre-temps pouvait ajouter au programme des objets absents de la liste, ou en retirer.
- Liste faite entièrement depuis les formulaires des opérations : seules ces opérations sont refaites ; sinon tout
  est refait.
- Parcours repris d'une session : refaits avant la première écriture (avant, un placement changé depuis n'était
  pas vu). En mode sélection, un message demande de sélectionner les objets puis de calculer.
- Objets du dernier calcul remplacés ou supprimés (pièce replacée, groupe défait…) : rien n'est écrit, un message
  demande de les resélectionner puis de calculer. Recalcul annulé : rien n'est écrit, la liste d'avant reste et le
  recalcul sera refait à la prochaine écriture.
- Un formulaire validé qui met à jour des textes datés (date, heure) fait refaire les autres parcours avant
  l'écriture : ils ne gardent plus la date d'avant.
- Parcours retiré de la liste, liste faite depuis les formulaires : il ne revient plus coché au recalcul.
  Parcours TypeEdit relus seuls : gardés et écrits même quand aucune opération n'est à refaire.
- Le message « Parcours recalculés » n'apparaît que si une liste existante a vraiment été refaite.
- « Fusionner les parcours » et son annulation : seules les opérations qui ont changé de place (parmi celles qui
  ont des parcours) emmènent leurs parcours ; un ordre réglé à la main entre les autres reste.
### v0.527.10 — Session reprise : parcours tels qu'on les avait laissés ; relecture

- La session garde, avec les parcours, ce que le panneau FAO savait de leur calcul (mode, objets du mode
  sélection, parcours retirés de la liste) et leur sens (parcours retournés). À la reprise, rien n'est refait si
  le dessin n'a pas bougé ; s'il a bougé, le recalcul rejoue le calcul d'alors (v0.527.9 refaisait tout : sens
  perdu, parcours retirés revenus, objets du mode sélection oubliés).
- Dessin rouvert depuis son fichier et retouché sur le disque depuis la session (VND repris dans TypeEdit…), ou
  session enregistrée par une version d'avant : « Calculer » est demandé avant la première écriture, quel que soit
  le mode. Un parcours inversé ou décoché après une sauvegarde de la session est bien gardé ainsi.
- Sans calcul connu, le recalcul suit le mode du moment (en mode sélection : la sélection).
- « Calcul des parcours » annulé pendant le recalcul fait avant l'écriture : rien n'est écrit (v0.527.9 pouvait
  écrire les seuls parcours TypeEdit).
- Liste vidée : un recalcul passe par le calcul normal, affiché. Opérations toutes désactivées : les parcours
  TypeEdit relus s'écrivent aussi en mode sélection.
### v0.527.11 — Simulation 3D, « Parcours en dessin » et volume : les parcours du programme ; relecture

- La simulation 3D (source « Parcours » ou « Simulation » de la vue 3D), « Parcours en dessin » et la mesure de
  volume prennent les parcours que le programme écrirait, sans ceux des opérations désactivées ou supprimées
  depuis le calcul. Avant, ils montraient les parcours d'avant un changement du dessin.
- « Parcours en dessin » et la mesure de volume recalculent les parcours si le dessin a changé depuis leur calcul
  (pièce 3D placée autrement, plaque, surface posée), comme l'écriture du programme.
- La vue 3D ne recalcule pas d'elle-même : des parcours d'avant un changement du dessin (ou d'une session reprise)
  n'y sont pas montrés, elle demande « Calculer » ; elle dit aussi quand les parcours cochés sont ceux
  d'opérations désactivées.
- « Calculer » avec la vue 3D ouverte : un seul calcul, et la vue montre aussitôt les nouveaux parcours. Un calcul
  annulé n'en relance plus un second par la vue 3D.
- Sans parcours coché, la vue 3D montre toujours tous les parcours de la liste ; sans parcours du tout, le calcul
  qu'elle lance ne met plus la date du jour dans le dessin.
- Session : les parcours repris ne sont gardés tels quels que si le fichier du dessin n'a pas changé depuis qu'il
  a été ouvert (autre poste sur le même dessin avant l'enregistrement de la session).
### v0.527.12 — Trajectoires sur la pièce 3D : celles du programme ; relecture

- Correction : un parcours refait depuis son formulaire après un changement du dessin (plaque, pièce 3D placée
  autrement), puis le dessin remis comme au calcul, pouvait être écrit tel quel, calculé pour l'état
  intermédiaire (par exemple décalé de la différence de plaque). Désormais, valider un formulaire après un
  changement du dessin fait tout recalculer avant l'écriture, même si le dessin revient ensuite comme il était.
- Liste faite seulement depuis les formulaires, avec une surface posée : plus de faux « Parcours recalculés » ni
  de trajectoires cachées.
- Les trajectoires posées sur la pièce 3D (vue « Modèle 3D », une prise ou toutes recomposées) et sur les volumes
  du dessin suivent la même règle que la simulation : les parcours cochés que le programme écrirait, sans ceux
  des opérations désactivées. Calculées avant un changement du dessin (pièce placée autrement, surface posée,
  session reprise), elles ne sont plus montrées à leur ancienne place : la ligne d'information le dit (aussi
  après « Positionner un corps »), et « Calculer » les remet. Un programme relu ou un parcours TypeEdit reste
  montré.
### v0.528.0 — Usinage 3D en plusieurs prises : relecture

- Correction : un corps de la pièce positionné à part dans une autre pose (par exemple dessous vers l'outil)
  n'était pas vu comme retourné quand l'usinage passait de l'ensemble à ce corps : la vérification ne bloquait
  pas et « Ajouter les arrêts » n'en mettait aucun. Désormais, c'est bloquant et l'arrêt est ajouté.
- L'arrêt avant un corps positionné à part dit sa vraie pose (« Poser le corps 2 : dessous vers l'outil ») au
  lieu de « comme le dessin », dans la vérification comme dans l'automatisme 3D, et garde la pose annoncée : si
  la pose du corps change ensuite, ou si l'arrêt est suivi d'un usinage d'une autre pose, c'est bloquant.
- Deux usinages avec la même face réelle vers l'outil (par exemple l'ensemble et un corps posé à part, dessus
  tous les deux) ne sont plus bloquants : à regarder seulement, comme deux corps tenus côte à côte. L'arrêt
  ajouté se place après les usinages de la même pose (même décochés).
- Correction : les contours de zone choisis dans la vue 3D restaient à leur place quand la pièce était replacée ou
  suivait la plaque (pièce centrée) : l'usinage pouvait tomber à côté de la zone, sur une autre partie de la
  pièce. Ils suivent maintenant la pièce (pour les contours choisis à partir de cette version).
- « Montrer la zone » dans une autre prise que celle du dessin montre les contours sur la pièce telle qu'elle est
  posée ; « Remplacer la zone » ne les retourne plus.
- Vue 3D : trajectoires recomposées aussi sur les volumes du dessin (prise retournée, corps seul) ; parcours sans
  opération (TypeEdit, programme relu) montrés dans la prise du dessin seulement.
### v0.528.1 — Volumes du dessin usinés un par un : le bon volume

- Correction : une opération qui usine un seul des volumes du dessin (« Corps usiné » n°…) visait son rang parmi
  les volumes visibles. Cacher un calque, ou ajouter un volume avant lui, lui faisait usiner un autre volume sans
  rien dire. L'opération garde maintenant le volume visé ; caché ou supprimé, il n'est pas usiné et le parcours
  le dit. Un numéro au-delà des volumes ne fait plus usiner tous les volumes.
- Changer le numéro dans le formulaire de l'opération vise le volume de ce numéro.
- Vue 3D : les trajectoires d'un volume caché ne sont plus recomposées sur un autre.
- Le formulaire de l'opération montre le numéro d'aujourd'hui du volume visé ; l'espace de travail, le contrôle
  des collisions et les arrêts de changement de prise suivent ce volume.
- Un booléen garde le volume du premier choisi : les opérations qui l'usinaient le suivent.
- Modèles d'usinage et réglage importé : le numéro du corps seul, pas le volume d'un autre dessin.
- Déplacer avec copie pose de nouveaux objets (ils partageaient l'identifiant de l'original).
### v0.528.2 — Parcours refaits après une retouche du dessin ou d'un outil

- Correction : un objet déplacé ou retouché après « Calculer », un outil modifié (diamètre…), ou une opération
  modifiée hors de son formulaire ne refaisait pas les parcours : le programme, la simulation, la fiche et
  « Parcours en dessin » prenaient ceux d'avant (un objet déplacé de 50 mm était usiné à son ancienne place).
  Ils sont maintenant refaits avant, comme après un placement de la pièce 3D, et la barre d'état le dit. Une
  opération seule retouchée : elle seule est refaite. Une opération ajoutée ou réactivée depuis le calcul est
  calculée avant l'écriture. Changer de post-processeur, renommer ou désactiver une opération, ajouter un outil
  qui ne sert pas ne refait rien.
- Les traits posés par « Parcours en dessin » ne sont plus usinés par couleur (une opération sur toutes les
  couleurs gravait les trajectoires reprises) : seulement choisis comme objets de l'opération ou en mode
  sélection. Les poser ne rend pas les parcours périmés.
- Vue 3D : les trajectoires d'avant une retouche ne sont pas montrées (« Calculer »).
- Session reprise : les parcours gardés sont refaits si le dessin avait été retouché depuis leur calcul.
- Empreinte du dessin plus rapide (mémoire des parcours) ; guides et notes n'en font plus partie.
### v0.529.0 — Vue 3D : onglets Pièce et Prise

- Vue 3D d'une pièce à plusieurs corps : onglets **« Pièce »** — « Ensemble », puis un onglet par corps (un
  moule en trois parties en a quatre). Un clic montre le corps seul, cadré, à poser, brider et usiner à part ;
  plus besoin de cliquer une face dans un mode de clic particulier puis de chercher dans le menu « Usinage 3D ».
- Sous la pièce choisie, onglets **« Prise »** : une par position ou bridage (les reprises) — « Comme le
  dessin » pour l'ensemble, « Comme l'ensemble » ou « Posé à part » pour un corps, puis les faces retournées ;
  « Toutes (recomposées) » sur l'ensemble. Le nombre d'usinages de la prise suit son nom, son bridage est
  rappelé à côté. La liste déroulante des prises disparaît.
- **« + Prise »** : une autre face vers l'outil (dessous, côtés) pour la pièce choisie, gardée avec le dessin
  même sans usinage ; clic droit sur l'onglet : « Retirer cette prise » (sans usinage ; son bridage avec elle),
  double clic : son bridage. Annulables.
- Boutons **Placer…** (l'ensemble, ou le corps posé à part), **Bridage…** (le matériel de la prise montrée),
  **Brut…** et **Automatisme…** à côté des onglets ; « Placer… » quitte la barre du haut.
- L'automatisme d'usinage 3D lancé depuis un corps seul ou une pièce retournée crée ses usinages dans cette
  prise (avec l'arrêt « poser la pièce » d'une face retournée), mesurés sur ce corps, faces et contours choisis
  compris ; il les créait jusqu'ici dans la prise du dessin, mesurés sur la pièce montrée.
- Une prise ajoutée ou bridée ne rend pas les parcours périmés.
### v0.530.0 — Rubans FAO 2D et FAO 3D

- Le ruban « FAO » devient **« FAO 2D »** (mêmes groupes) ; nouveau ruban **« FAO 3D »** avec toutes les
  fonctions qui étaient dans les menus déroulants de la vue 3D, en boutons :
  - **Pièce 3D** : Placer la pièce 3D (venu de l'onglet 3D), Brut…, Bridage… (de la prise montrée), En
    volumes ;
  - **Clic dans la vue** : Faces, Contours fermés, Points et cotes (boutons cochés comme la vue), Effacer la
    sélection ;
  - **Usinage 3D** : Automatisme…, Ébauche 3D et Balayage 3D (faces et contours choisis, sinon toute la pièce
    ou le corps de la prise montrée), Niveaux constants, Poche jusqu'au fond, Trous → perçages, Contours dans
    le dessin, Zone d'un usinage (« Remplacer la zone de « … » » avec des faces choisies, « Montrer la zone
    de « … » ») ;
  - **Poser** : sur cette face, face vers l'outil, corps posé à part (celui de l'onglet), surface 2D ;
  - **Corps et couleurs** : corps montrés ou masqués, Tout montrer, Couleur par corps, Mécanismes…, couleurs
    de la pièce et des arêtes, couleurs d'origine ;
  - **Calculer et voir** : Calculer les parcours (aussi dans FAO 2D, seule commande des deux), Trajectoires 3D
    et Simulation 3D (venues de FAO 2D).
- La barre de la vue 3D ne garde que l'affichage (source, vues, rendu, recalcul) : les listes « Clic : … »,
  « Usinage 3D », « Couleurs » et « Corps » disparaissent.
- Passer en 3D depuis le ruban FAO 2D montre FAO 3D, revenir en 2D depuis FAO 3D montre FAO 2D.
- Une commande du ruban FAO 3D sans pièce 3D, ou qui demande des faces choisies, le dit sous la barre de la
  vue et dans la barre d'état, sans rien faire. Après Trajectoires 3D ou Simulation 3D, elle remontre la pièce
  pour la viser ; « En volumes » refuse les volumes du dessin (déjà là) ; les menus Zone et Corps suivent le
  dessin montré.
- Les deux rubans tiennent en Full HD avec tous leurs libellés, sans replier de groupe. Le bouton 3D reste dans
  l'onglet Vue (les commandes du ruban FAO 3D passent d'elles-mêmes en 3D).
- Les actions de plugins prévues pour l'onglet « FAO » vont dans « FAO 2D » ; les onglets ajoutés par un plugin
  se placent avant FAO 2D, les deux rubans FAO restant côte à côte.
### v0.531.0 — Pièces STEP en vraies faces et générateurs

- Nouveau noyau **`core.brep`** : des pièces décrites en tranches empilées le long de Z (cercles, cônes,
  sphères, polygones avec arcs, troncs de pyramide), écrites en **STEP AP214 en vraies faces** (plans,
  cylindres, cônes, sphères ; arêtes et sommets partagés ; un solide nommé et coloré par corps). Les fichiers
  s'ouvrent dans les logiciels de CAO avec leurs surfaces exactes (trous reconnus comme cylindres, axes, rayons),
  pas en facettes.
- Nouveau module **`core.stepgen`** : 20 familles de pièces paramétrées, filets non représentés (comme les
  modèles simplifiés des catalogues) :
  - **Visserie** : vis CHC ISO 4762, H ISO 4017, FHC ISO 10642, BHC ISO 7380, STHC ISO 4026 ; écrous H
    ISO 4032 ; rondelles ISO 7089 et ISO 7093-1 ; goupilles cylindriques ISO 2338 ;
  - **Transmission** : roulements rigides à billes (séries 62x, 60xx, 62xx), clavettes DIN 6885 A, roues
    dentées droites (développante 20°, module et nombre de dents) ;
  - **Brut** : barres, tubes et profilés (rond, tube, carré, plat, six pans, tube carré, cornière, U), plaques
    percées (trous de passage, lamés pour CHC, fraisés pour FHC, taraudés ; aux coins, en grille ou au centre),
    entretoises taraudées, bagues lisses ;
  - **Moule** : éjecteurs, colonnes et douilles de guidage, bagues de centrage (dimensions à donner).
- Dimensions des familles normalisées prises dans les tables des normes (valeurs nominales) ; les vis ont
  le dessous de la tête en Z = 0 et la tige vers le bas (FHC : dessus de la tête en Z = 0). Une famille avec
  gamme s'écrit d'un coup, une pièce par fichier, aux longueurs préférentielles des normes (743 pièces au total).
- Une description impossible est refusée avec sa raison (boucles qui se coupent ou se touchent, trou qui mord
  sur un coin arrondi, trous qui se touchent, vis trop courte pour sa tête…), jamais écrite fausse.
- Chaque fichier écrit est contrôlé : chaque arête bordée par deux faces en sens opposés, nombre d'Euler juste,
  sommets et arêtes sur leurs surfaces, toutes les faces tournées vers l'extérieur.
### v0.532.0 — Onglet Design STEP : générateurs de pièces

- Nouvel onglet de ruban **« Design STEP »** :
  - **Générateurs** : *Générer une pièce STEP* (grand bouton), et *Visserie*, *Transmission*, *Brut et
    profilés*, *Éléments de moule* qui ouvrent la fenêtre sur leur catégorie ;
  - **Dépôt STEP** : *Parcourir le dépôt* (le dossier du dépôt dans le navigateur à vignettes) et *Dossier du
    dépôt…*.
- Fenêtre des générateurs : familles par catégorie, paramètres de la famille (listes des tailles normalisées,
  longueurs, références), aperçu ombré qui tourne d'un glisser, nom du fichier, volume, masse (acier, laiton
  ou aluminium) et encombrement ; une valeur impossible est dite et rien ne s'enregistre.
  - **Enregistrer le STEP** : dans le dépôt, sous-dossier de la catégorie ; remplacement confirmé.
  - **Toute la gamme** : toutes les tailles et longueurs courantes de la famille, un fichier par pièce, dans un
    sous-dossier de la famille, avec avancement et Annuler.
  - **Ajouter au dessin** : la pièce en volume du dessin, centrée sur la plaque et posée sur Z = 0, sa
    description gardée.
  - **Ouvrir le STEP** : enregistrée puis ouverte dans un onglet, en vue 3D.
- Dans la disposition TypeEdit, ces commandes vont dans l'onglet « VectorDrive » comme les autres commandes
  propres à VectorDrive.
- Guide : docs/design_step.md.
- Le dépôt s'ouvre dans le navigateur avec le filtre STEP, sans changer le filtre ni le dossier d'ouverture
  retenus.
- Pièces STEP (noyau du round précédent) : aperçu des grandes grilles de trous bien plus rapide ; une bague
  au chanfrein trop grand garde une couronne ; deux boucles confondues dans une tranche sont refusées ;
  l'écriture d'un STEP qui échoue ne vide plus un fichier existant ; plaques : 625 trous en grille au plus.
### v0.533.0 — Corps d'un STEP : extraire, séparer, réunir

- Onglet **Design STEP**, nouveau groupe **Modifier un STEP** :
  - **Corps d'un STEP…** : les corps (solides) d'un fichier STEP — celui de la pièce 3D du dessin, avec le
    corps des faces choisies coché seul, sinon un fichier à choisir — listés avec leur nombre de faces et
    montrés dans un aperçu qu'on fait tourner ; **Extraire les corps cochés…** (un fichier),
    **Un fichier par corps…** (un moule en trois parties : trois STEP, nommés d'après les corps ; fichiers
    existants remplacés après confirmation), **Voir les fichiers** dans le navigateur à vignettes ;
  - **Déplacer les corps cochés** : translation X, Y, Z et rotation autour de X, Y ou Z, suivie dans
    l'aperçu, appliquée aux fichiers écrits ;
  - **Réunir des STEP…** : plusieurs fichiers STEP en une seule pièce, chaque corps à sa place.
- La géométrie est recopiée **exacte** (faces, arêtes, surfaces du fichier d'origine, rien n'est remaillé),
  avec les noms et les couleurs des corps, les unités du fichier et la place de chaque pièce dans
  l'assemblage. Les coordonnées restent celles du fichier d'origine : des pièces séparées puis réunies
  reviennent à leur place. Des fichiers en unités différentes ne se réunissent pas d'un coup (refus dit).
- Sûreté : un fichier changé sur le disque depuis sa lecture est relu et rien n'est écrit ; un déplacement
  en miroir ou déformé est refusé ; des unités d'angle différentes ne se réunissent pas ; un fichier
  illisible est dit ; avancement et annulation pour les gros fichiers (200 corps séparés en 3 s) ; noms de
  fichiers réservés de Windows (NUL, COM1…) évités.
- Lecture des STEP : un « DATA; » dans une chaîne de l'en-tête ou « ENDSEC » dans un nom ne coupent plus la
  lecture ; la forme `DATA('nom',(…));` est lue.
- Guide : `docs/design_step.md`, nouvelle section « Modifier un STEP ».
### v0.534.0 — Vis dans ce trou

- Onglet **Design STEP**, groupe **Modifier un STEP** : **Vis dans ce trou…**. Choisir dans la vue 3D d'une
  pièce STEP la paroi d'un trou : le trou est reconnu dans n'importe quelle direction — lamé, fraisé, de
  passage ou taraudé ; débouchant ou borgne — et la vis normalisée est proposée et posée :
  - lamé : CHC ISO 4762, le dessous de la tête sur le fond du lamage ; fraisé : FHC ISO 10642, la tête au
    ras ; passage ou taraudé : CHC, la tête sur l'ouverture ;
  - taille d'après le diamètre (la plus proche s'il est hors norme, c'est dit), longueur parmi celles de la
    norme (trou débouchant et 1,5 d de filet en prise, trou borgne sous la profondeur moins un pas,
    taraudé débouchant traversé) ;
  - vis (CHC, H, FHC, BHC), taille et longueur modifiables, **Tête de l'autre côté**, **Tous les trous
    identiques (n)** ; aperçu de la pièce autour du trou avec la vis.
  - un chanfrein d'entrée n'est pas une fraisure, un lamage de surface laisse le trou taraudé, la paroi du
    lamage choisie donne le trou dessous, deux trous face à face restent deux trous ; passage ISO 273 en
    séries fine, moyenne et large ; trou de passage posé sur un taraudage (trou étagé, deux pièces) : la
    vis s'y visse ; l'épaisseur traversée compte le côté opposé ;
  - rapide sur une grande pièce (625 trous lamés reconnus en quelques secondes).
- **Enregistrer la vis…** (la ou les vis seules, aux coordonnées de la pièce) ou **Pièce et vis…** (un seul
  STEP, géométrie de la pièce recopiée exacte ; pièce en millimètres).
- Guide : `docs/design_step.md`, section « Modifier un STEP ».
### v0.535.0 — Générateurs de bridage

- Onglet **Design STEP**, groupe **Générateurs** : nouvelle catégorie **Bridage** (bouton et fenêtre des
  générateurs), pour préparer les prises et les reprises d'usinage :
  - **Bride de serrage** plate, lumière oblongue au milieu pour la vis (M6 à M16) ;
  - **Cale étagée** : nombre, hauteur et profondeur des marches, largeur ;
  - **Mors doux** : longueur, hauteur, épaisseur, deux trous lamés côté serrage (vis, entraxe, hauteur des
    trous) ; les trous sont reconnus par **Vis dans ce trou…** ;
  - **Goujon de bridage** : M6 à M20, longueur.
- Dimensions à donner (pas de norme) ; chaque pièce est un solide fermé, enregistrée dans le sous-dossier
  `Bridage` du dépôt, ajoutée au dessin ou ouverte comme les autres.
### v0.536.0 — Modifier une pièce générée

- Onglet **Design STEP**, groupe **Générateurs** : **Modifier la pièce générée…**. Une pièce ajoutée au
  dessin par les générateurs (choisie dans le dessin) rouvre leur fenêtre avec sa famille et ses valeurs ;
  **Remplacer dans le dessin** met la pièce modifiée à sa place : même milieu en X et Y, même dessous, même
  si elle a été déplacée ou posée sur une autre depuis. Annulable ; chaque nouvel appui remplace encore la
  même pièce. Une pièce supprimée entre-temps est ajoutée à neuf, au centre de la plaque.
- Guide : `docs/design_step.md`, section « Enregistrer, ajouter, ouvrir ».
### v0.537.0 — Parois alignées : bride à talon, mors à épaulement, écrou en T

- Pièces STEP générées : deux étages d'une pièce peuvent désormais avoir des **parois alignées** (le talon
  d'une bride au ras du bout, l'épaulement d'un mors, le tenon d'un écrou en T, une marche, une équerre,
  une poche ouverte sur le bord). Les faces restent exactes et partagent leurs arêtes ; les pièces
  d'avant sont écrites à l'identique.
- Catégorie **Bridage** : **Bride de serrage** avec talon dessous au bout (hauteur et longueur ; 0 : bride
  plate) ; **Mors doux** avec épaulement au bord haut de la face de serrage (profondeur et hauteur) ;
  nouvel **Écrou pour rainure en T** (largeur de rainure, tête, hauteurs, longueur, taraudage).
- Toujours refusés, avec un message : étages qui se croisent, qui ne se touchent qu'en un point ou bord à
  bord (deux solides, même un bouchon exactement dans un trou), presque alignés (écart sous le
  micromètre : arrondir les cotes), arc tangent à un côté. Des cotes au bruit de calcul près (pièce
  tournée, 0,1 + 0,2) restent justes, maillage compris ; un sommet posé sur un côté de l'étage voisin à
  un millionième de millimètre près est vu comme posé (accepté juste ou refusé, plus de maillage ouvert).
### v0.538.0 — Sélection 3D : faces semblables, mesures

- Onglet **Design STEP**, nouveau groupe **Sélection 3D** : **Faces** (un clic dans la vue 3D choisit une
  face, comme au ruban FAO 3D), **Faces semblables**, **Mesurer la sélection**, **Effacer la sélection**.
- **Faces semblables** : tous les trous du diamètre de celui choisi, les faces coplanaires à une face plane
  (fonds de lamages), les fraisures ou congés identiques ; puis **Vis dans ce trou…** sur ces trous.
- **Mesurer la sélection** : chaque face décrite (trou ou cylindre Ø et axe, plan avec sa normale et sa
  cote, aire) ; pour deux faces, distance de deux plans parallèles, angle de deux plans, entraxe de deux
  trous, distance d'un axe à un plan, sinon la plus courte distance ; plusieurs faces : aire et
  encombrement ; texte à copier.
- La ligne sous la vue 3D dit ce qu'est la face choisie, ou la mesure entre deux faces.
- STEP (surfaces exactes du fichier) comme STL (faces planes reconnues à leurs facettes).
### v0.539.0 — Pièce dans ce trou

- Onglet **Design STEP**, groupe **Modifier un STEP** : **Pièce dans ce trou…** — la paroi d'un alésage
  choisie dans la vue 3D d'une pièce STEP, une pièce des générateurs proposée à son diamètre et posée
  dedans : **goupille cylindrique** (la plus longue de la série dans la profondeur), **roulement** (la
  référence de diamètre extérieur), **bague lisse**, **douille de guidage** (collerette sur l'entrée),
  **colonne de guidage** et **éjecteur** (alésage débouchant), **bague de centrage**.
- L'alésage est reconnu dans n'importe quelle direction, débouchant ou borgne ; **Entrer par l'autre
  côté** pour un débouchant ; toutes les cotes se changent (**Proposer de nouveau** : celles de l'alésage) ;
  une pièce qui ne va pas est dite.
- **Tous les alésages identiques (n)** : la même pièce dans chacun ; **Enregistrer seule…** ou **Avec la
  pièce percée…** dans un fichier STEP (géométrie exacte, coordonnées de la pièce).
### v0.540.0 — Pièce STEP du dessin

- Onglet **Design STEP**, groupe **Générateurs** : **Pièce du dessin…** — les formes fermées choisies dans
  le dessin (bord, trous, lumières, textes par leur contour) deviennent une pièce STEP **à vraies faces** :
  les arcs restent des arcs (parois cylindriques), un contour rond est un vrai cercle (trou reconnu par
  **Vis dans ce trou…**).
- Épaisseur ; **Contours intérieurs** en **Trous débouchants**, en **Poches** (profondeur donnée) ou
  **Ronds débouchants, autres en poche** ; îlots dans les poches ; une pièce par bord dans le même fichier.
- Contours qui se coupent, contour qui se recoupe (en huit), îlot dans un trou débouchant (pièce
  détachée), poche plus profonde que la pièce : c'est dit. Aperçu ; **Enregistrer…** (dépôt, dossier
  Dessin) ; **Ouvrir en 3D**.
### v0.541.0 — Vé de bridage et plaque de moule

- Générateurs STEP, **Bridage** : **Vé de bridage** — bloc long de Y, vé ouvert en haut sur toute la
  longueur (90° ou 120°, ouverture donnée), gorge au fond pour les arêtes vives ; les flancs sont de vrais
  plans inclinés.
- **Éléments de moule** : **Plaque de moule** — quatre alésages de guidage aux coins, l'un décalé en X (un
  seul sens de montage), lamés au besoin pour les collerettes ; empreinte en poche au milieu au besoin (coins
  arrondis). Alésages trop près du bord ou qui se touchent, empreinte qui touche un alésage : c'est dit.
- Les alésages de la plaque sont reconnus par **Pièce dans ce trou…** : la douille proposée se pose dans les
  quatre, sa collerette dans le lamage, au ras du dessus.
### v0.542.0 — Pièce tournée du dessin

- Onglet **Design STEP**, groupe **Générateurs** : **Pièce tournée du dessin…** — un demi-profil fermé
  dessiné d'un côté de l'axe devient une pièce STEP de révolution **à vraies faces** (arbre, bague, axe,
  poulie, pointe) : les droites donnent des cylindres, des cônes et des plans, un arc centré sur l'axe une
  sphère, les autres arcs des cônes à 0,01 mm près.
- L'axe : un trait droit choisi avec le profil (vertical, horizontal pour un dessin de tournage, ou
  incliné ; il peut être à l'écart du profil : une bague), sinon le bord gauche du profil. Axe en Z, bas
  du profil à Z = 0 ; une pièce par contour fermé.
- Pointes sur l'axe et arêtes vives du haut ou du bas arrêtées d'un petit plat ; profil des deux côtés de
  l'axe, qui se recoupe, qui touche l'axe en plusieurs traits, profils qui se touchent ou l'un dans
  l'autre, arc tangent à l'axe : c'est dit.
- La fenêtre **Pièce du dessin** gagne **Forme** : **Extrudée** ou **Tournée**.
### v0.543.0 — Faces tangentes, faces du corps

- Onglet **Design STEP**, groupe **Sélection 3D** : **Faces tangentes** — de proche en proche, les faces qui
  suivent celles choisies sans arête vive : un bord arrondi (côtés et congés des coins), une chaîne de
  congés, les deux moitiés d'un trou ; une arête vive arrête la sélection.
- **Faces du corps** : toutes les faces des corps des faces choisies (une partie d'un moule en plusieurs
  corps).
### v0.544.0 — Bride ronde

- Générateurs STEP, **Brut et profilés** : **Bride ronde** — disque à trous sur un cercle (nombre, Ø du
  cercle, angle du premier), de passage, lamés, fraisés ou taraudés ; alésage au centre et centrage en
  saillie au besoin. Trous sur l'alésage, hors de la bride ou qui se touchent : c'est dit.
- Les trous reçoivent leurs vis par **Vis dans ce trou…** (tous ensemble), l'alésage un roulement par
  **Pièce dans ce trou…**.
### v0.545.0 — Faces parallèles

- Onglet **Design STEP**, groupe **Sélection 3D** : **Faces parallèles** — un plan choisi : tous les plans de
  même normale à toute cote (les fonds tournés vers l'outil d'une prise, sur tous les corps) ; un cylindre :
  tous ceux d'axe parallèle, creux ou non comme lui (les trous percés dans ce sens).
### v0.546.0 — Faces coaxiales

- Onglet **Design STEP**, groupe **Sélection 3D** : **Faces coaxiales** — un cylindre, un cône ou une sphère
  choisi : toutes les faces du même axe et les fonds plats entre elles. Un trou lamé entier d'un clic
  (passage, lamage, fond du lamage), sans les autres trous ni le dessus de la pièce ; un arbre tourné entier
  (cylindres, chanfreins, dôme, épaulements, bouts) ; les alésages alignés de plaques empilées.
- Le lecteur STEP donne aussi l'axe des cônes, des sphères et des tores.
### v0.547.0 — Plateau à rainures en T

- Onglet **Design STEP**, générateurs **Bridage** : **Plateau à rainures en T** — bloc de longueur, largeur
  et hauteur données, n rainures ISO 299 ouvertes dessus sur toute la longueur, centrées à l'entraxe donné
  (largeur, tête, profondeur ; par défaut 14 mm : l'écrou en T par défaut y entre) ; cotes impossibles
  refusées (rainure trop profonde, têtes qui se touchent, plateau trop étroit).
### v0.548.0 — Répéter des corps

- Onglet **Design STEP**, groupe **Modifier un STEP** : **Répéter des corps…** — les corps d'un STEP (la
  pièce 3D du dessin, le corps des faces choisies seul, sinon un fichier à choisir) copiés dans un nouveau
  STEP à géométrie exacte, l'original compris : **en ligne** au pas donné en X, Y et Z, ou **en rond** autour
  de la verticale (360° : répartis sur le tour, sinon du premier au dernier sur l'angle). Le fichier source
  n'est jamais écrasé.
### v0.549.0 — Cale pentée

- Onglet **Design STEP**, générateurs **Bridage** : **Cale pentée** — bloc de longueur et largeur données, le
  dessus en pente du bout mince au bout épais ; l'angle de la pente est dans le nom du fichier.
### v0.549.1 — Faces coaxiales et Répéter des corps : corrections

- **Faces coaxiales** : la sélection reste dans le corps de la face choisie (une bague posée sur l'axe d'un
  trou, ou une autre partie du moule, n'en est plus) ; une sphère choisie prend l'axe de la face voisine qui
  passe par son centre (les fichiers d'autres CAO lui donnent un axe quelconque : le cylindre qu'elle
  termine manquait).
- **Répéter des corps** : pas, verticale et centre dans les axes de la pièce redressée, comme dans la vue 3D
  (un fichier « Y vers le haut » montait de côté ou se retournait) ; un corps choisi introuvable est dit ;
  un fichier qui existe n'est remplacé qu'au second clic ; la source n'est jamais écrasée, même écrite
  autrement ; un nom seul est écrit à côté de la source ; avancement et Annuler pendant l'écriture.
### v0.550.0 — Inverser dans le corps

- Onglet **Design STEP**, groupe **Sélection 3D** : **Inverser dans le corps** — les faces des corps choisis
  qui ne sont pas choisies : le reste d'une pièce (tout sauf un trou, sauf les fonds déjà usinés) ; les
  autres corps restent hors de la sélection.
### v0.551.0 — Usinages 3D modifiables dans la vue 3D

- Vue 3D : liste **« Usinages »** à droite de la vue — les usinages de la prise montrée, leur outil et
  l'état de leur parcours. Double clic : le formulaire de l'usinage (parcours recalculé) ; **Outil de
  l'usinage…** (les parcours des usinages qui s'en servent sont recalculés) ; recalculer, dupliquer, monter,
  descendre ; **Supprimer le parcours** (l'usinage reste) ; **Supprimer l'usinage** (Suppr, annulable) ; case :
  actif ou non. Elle s'ouvre après l'automatisme, le premier usinage créé choisi.
- Ruban FAO 3D, groupe **« Usinages »** : Liste des usinages, Modifier l'usinage…, Outil de l'usinage…,
  Supprimer l'usinage. Groupe « Corps et couleurs » : les couleurs sous un bouton **« Couleurs »**.
- Automatisme d'usinage 3D : **Outil de l'étape…** — l'outil proposé ou choisi, modifié dans son
  formulaire, devient (en copie) l'outil de l'étape ; l'outil d'origine ne change pas.
- Correction : modifier un usinage 3D de toute la pièce ne le réduit plus au premier corps (« Corps usiné »
  accepte « toute la pièce ») ; la courbe guide d'une projection locale n'est plus changée en texte.
### v0.552.0 — Thème Crépuscule par défaut

- Un poste qui n'a pas choisi de thème prend **Crépuscule** (avant : Clair) — au lancement, dans les options,
  le menu Thème et Personnaliser l'interface ; un thème choisi est gardé. Un thème personnel supprimé ramène à
  Crépuscule.
### v0.553.0 — Onglets de ruban à soi

- **Personnaliser le ruban** gère maintenant autant d'onglets à soi qu'on veut, et plus seulement « Mon onglet ».
  Chacun a son nom et sa place : en premier, en dernier ou après un onglet donné. Il réunit les commandes de
  son choix, rangées en groupes, en grands ou petits boutons ; chaque bouton peut recevoir son propre libellé
  (« Libellé du bouton… »), tout en gardant l'icône, la commande et l'état d'origine.
- **Exporter… / Importer…** : les onglets à soi et les onglets masqués dans un fichier JSON, pour les retrouver
  sur un autre poste.
- **Clic droit sur une commande du ruban** : l'ajouter à un onglet à soi existant ou à un nouvel onglet, ou la
  retirer de l'onglet à soi où elle est.
- **Clic droit sur un onglet** : renommer ou supprimer un onglet à soi, créer un nouvel onglet, personnaliser
  le ruban.
- Un onglet à soi ne prend jamais le titre d'un autre onglet : il est numéroté (« Aide (2) »). Une commande
  d'un plugin absent reste dans les réglages.
### v0.554.0 — Gravure 2,5D en ligne médiane : le cadre est bien ignoré

- **Gravure 2,5D en « Ligne médiane »** avec « Finition : pas de passe sur le cadre (gravure en relief) » : le
  cadre englobant n'est plus repassé, que la gravure soit seule ou liée au parcours précédent. Le fond du cadre
  est gravé en passes décalées, qui sautent le cadre, et les formes hors du cadre restent en ligne médiane. Un
  avertissement le signale dans le parcours.
- **Modèles d'usinage TypeEdit de gravure 3D** : l'option « pas de passe sur le cadre » de la gravure n'est plus
  écrasée par celle de la finition à l'import.
### v0.555.0 — Parcours préremplis avec leurs dernières valeurs

- **Colonne des parcours de la FAO** : chaque parcours correspond à une stratégie et reste toujours proposé. Son
  formulaire s'ouvre prérempli avec les dernières valeurs validées pour ce parcours : profondeurs, passes,
  options et outil. L'outil est repris dans le dessin, ou ajouté s'il n'y est pas. Les hauteurs de dégagement
  et d'approche restent celles des Options (F10), et le nom reste celui du parcours. Un modèle choisi sous le
  parcours passe avant les dernières valeurs, et devient à son tour les dernières valeurs une fois validé.
- **Formulaire d'un nouveau parcours** : plus de liste des stratégies, puisque c'est celle du parcours cliqué.
  Le formulaire d'une opération existante la garde.
- **Clic droit sur un parcours** : « Enregistrer les dernières valeurs comme modèle… » range ces réglages, avec
  leur outil, en modèle sous ce parcours. « Revenir aux réglages d'origine » oublie les dernières valeurs. La
  bulle du parcours indique s'il est prérempli.
- Un formulaire annulé ne retient rien. Un parcours créé sans formulaire, par un script, garde les réglages
  d'origine.
### v0.556.0 — Opérations liées dans la liste

- **Lier au parcours précédent** : l'opération liée reste attachée à celle qui la précède dans la liste des
  opérations de la FAO.
  - Elle est marquée « ↳ » dans la liste des opérations et dans celle des parcours. Sa bulle nomme l'opération
    à laquelle elle est liée.
  - Monter ou descendre une opération emmène ses opérations liées, d'un bloc. Une opération liée déplacée seule
    change de place dans la chaîne. Une copie se range après les opérations liées.
  - Clic droit sur une opération : « Lier au parcours précédent », pour lier ou délier sans ouvrir le
    formulaire.
- **Calcul d'une opération liée** (formulaire validé, liaison cochée) : il part maintenant des parcours des
  opérations d'avant, comme « Calculer ». Ces parcours sont calculés s'il en manque. Auparavant, seul le calcul
  de toutes les opérations appliquait la liaison.
- Une opération recalculée refait aussi les opérations liées qui la suivent et qui étaient déjà calculées.
### v0.557.0 — Pointillés

- **Pointillés** (Dessin › Contours, palette des effets spéciaux) : les traits sélectionnés deviennent de vrais
  tirets, pour la découpe en pointillés, le pliage ou la perforation au laser, au couteau ou à la fraise.
  - Types de traits standard, d'après CADCraft : DASHED, CENTER, PHANTOM, DOT, DASHDOT, HIDDEN, BORDER,
    DIVIDE et leurs variantes. Les valeurs ISO sont en mm.
  - Fichiers **.lin** lus et retenus pour la fois suivante. Les éléments texte ou forme sont laissés de côté.
  - **Motif à soi** en mm : un tiret (positif), un espace (négatif), un point (0), par exemple « 5, -2.5 ».
  - **Échelle** du motif. Sur les contours fermés, le motif peut être ajusté pour tomber juste : pas de tiret
    raccourci au départ.
  - Les points deviennent de petits cercles du diamètre choisi, ou rien.
  - Les traits d'origine peuvent être gardés. Un aperçu du motif est affiché.
- Les tirets suivent les courbes elles-mêmes : droites, Bézier et arcs sont coupés exactement, sans
  approximation en segments. Un tiret à cheval sur le départ d'un contour fermé reste d'un seul morceau.
  Annulable.
### v0.558.0 — Hachures : motifs de DAO et fichiers .pat

- **Hachures › Motif** : en plus des traits, briques, pointillés, ondulés et nid d'abeille, 22 motifs de DAO
  d'après CADCraft.
  - Matériaux ANSI31 à ANSI38 (fonte, acier, bronze, plastique, brique réfractaire, marbre, plomb,
    aluminium).
  - LINE, NET, NET3, DOTS, DASH, BRICK, SQUARE, CROSS, EARTH, GRASS, HONEY, ZIGZAG, AR-CONC et AR-SAND.
  - Chaque motif est un ensemble de familles de traits, avec tirets et points, aux valeurs ISO en mm.
- **Échelle** et **angle** du motif. Les points deviennent de petits cercles du diamètre choisi, ou rien. Les
  trous restent vides. En passant à un motif de DAO, l'angle revient à 0.
- **Fichier .pat…** : les motifs d'un fichier .pat sont lus et retenus pour la fois suivante. Un motif
  importé est gardé dans les hachures elles-mêmes : elles restent modifiables sans le fichier.
### v0.559.0 — Police monotrait intégrée « VD Trait »

- **VD Trait** est en tête de la liste des polices. C'est une police monotrait toujours disponible, même sans
  police installée sur le poste : des traits ouverts, gravés en un passage. Elle convient aux plaques, aux cotes
  et au marquage.
  - Lettres, chiffres et ponctuation d'après la police « CADCraft Stroke ».
  - Lettres accentuées composées à la volée (à â ä ç é è ê ë î ï ô ö ù û ü ÿ, capitales comprises, et le latin
    étendu : ñ å ł š ž č ř ę ő…), œ æ ß, guillemets « », tirets, €, £, ©, ®, ×, ÷, ², ³, ¿ et ¡.
  - Hauteur du texte = hauteur des capitales, comme pour les polices Gravotech. Pas de crénage.
### v0.560.0 — Cercle tangent

- **Cercle tangent** (CAD › Création, palette des formes) : un cercle tangent à des traits droits, des cercles ou
  des arcs, d'après CADCraft.
  - Au départ, l'outil demande un rayon. Avec un rayon, deux clics suffisent : le cercle de ce rayon est tangent
    aux deux objets cliqués.
  - Avec un rayon 0, il faut trois clics : le cercle est tangent aux trois objets (cercle inscrit dans un
    triangle, cercle entre trois trous…).
  - On clique près des points de contact voulus. Parmi les solutions possibles, l'outil garde celle qui touche
    les objets au plus près des clics. Le cercle s'affiche en aperçu au survol de l'objet qui termine la
    construction.
- **Déplacer sur la courbe** a maintenant son icône (des lettres posées sur une courbe).
### v0.561.0 — Mesurer un rayon, mesurer un angle

- **Mesurer un rayon** (CAD › Mesure) : clic sur un cercle, un arc ou une courbe.
  - Cercle : rayon, diamètre et centre.
  - Arc : rayon, diamètre, angle et longueur de l'arc entier, même s'il est fait de plusieurs morceaux (coins
    arrondis, arcs importés).
  - Courbe : rayon de courbure au point cliqué, avec le cercle osculateur en tirets.
  - Trait droit : longueur et angle.
  - Les objets d'un groupe et les textes se mesurent aussi.
- **Mesurer un angle** (CAD › Mesure) :
  - entre deux traits droits : on clique chacun du côté de l'angle voulu, et les droites sont prolongées jusqu'à
    leur rencontre. Si les traits sont parallèles, l'outil donne leur écart ;
  - en trois points : le sommet, puis un point de chaque côté (accrochage F3 conseillé).
  - L'angle est dessiné sur le plan avec sa valeur. La barre d'état donne aussi le supplément et l'angle rentrant.
### v0.562.0 — Unités et fractions dans les calculs

- **Calcul d'un champ** (touche = dans un champ de valeur) : les longueurs peuvent porter leur unité. Le résultat
  est en mm.
  - mm, cm, dm, m, in ou ", ft ou ', pt : « 2,5cm », « 1in », « 10pt », « 1m-20cm ».
  - Fractions et pieds-pouces comme en DAO, d'après CADCraft : « 3/4" », « 6 1/2in », « 1'6" », « 1'-6 1/2" ».
    Elles servent à reprendre une cote en pouces d'un plan américain.
  - Avec « ° », degrés, minutes et secondes : « 30°15'36" » donne 30,26.
### v0.563.0 — Réunir les textes

- **Réunir les textes** (Texte, à côté de Rechercher / remplacer) : les textes choisis deviennent un seul texte de
  plusieurs lignes, d'après le TXT2MTXT de CADCraft. Un plan DXF ou PDF importé arrive souvent avec un objet par
  ligne de texte : après la réunion, le paragraphe se modifie d'un bloc.
  - Les lignes sont rangées de haut en bas, y compris pour des textes tournés. Des textes à la même hauteur
    forment une seule ligne, de gauche à droite.
  - Le texte réuni garde la police, la hauteur et les réglages du texte le plus haut. Son interligne reprend
    l'écart entre les lignes.
  - Les textes sur courbe, en arc ou dans un cadre ne sont pas touchés, ni les autres objets de la sélection.
    La commande s'annule.
- **Sur courbe** (texte) prend l'icône des lettres posées sur une courbe.
### v0.564.0 — Comparer deux dessins

- **Comparer** (Fichier › Comparer) : le dessin affiché est comparé à un autre onglet ouvert ou à un fichier
  lu du disque, d'après le COMPARE de CADCraft. Il sert par exemple à voir ce qui change entre deux versions d'un
  plan envoyé par un client.
  - Ce qui n'est qu'ici est surligné en vert. Ce qui n'est que dans l'autre dessin est tracé en rouge pointillé.
    Un objet modifié est en orange, l'ancienne forme en pointillé.
  - Un objet est modifié quand il garde son identifiant (même .vdz réenregistré) ou sa forme, et change de forme,
    de texte, d'outil, de remplissage ou de calque. Les coordonnées sont comparées au micron près.
  - Différence suivante et précédente : les zones qui portent des différences sont cadrées l'une après l'autre,
    de haut en bas puis de gauche à droite.
  - Une légende en bas à gauche compte les objets de chaque couleur. Fermer la comparaison efface les couleurs.
    Le dessin n'est pas modifié.
- Hachures : le bouton « Fichier .pat… » ne reçoit plus l'état du clic.
### v0.565.0 — Reproduire les propriétés

- **Reproduire les propriétés** (Edition › Presse-papiers, pinceau) : les propriétés d'un objet vont à d'autres
  objets, d'après le MATCHPROP de CADCraft.
  - Plusieurs objets sélectionnés : les propriétés du premier vont aux autres.
  - Un seul objet sélectionné : ses propriétés sont prises, puis les objets cliqués ensuite les reçoivent.
  - Propriétés reproduites : l'outil, le remplissage, le calque (l'objet y passe), et entre textes la police,
    la hauteur, la largeur, les espacements, l'alignement et les styles. Chacune se coche ou se décoche dans
    F10 › Dessin.
  - Dans un groupe, tous les objets prennent l'outil et le remplissage. La commande s'annule.
### v0.566.0 — Festons

- **Festons** (Déformations) : le tracé des formes choisies devient une suite d'arcs réguliers, d'après le nuage
  de révision (REVCLOUD) de CADCraft. Il sert pour un cadre de plaque festonné, un bord de timbre ou une frise.
  - Largeur d'un feston en mm. Les festons sont égaux entre deux coins et se rejoignent sur les coins. Un contour
    lisse (cercle, coins arrondis) est festonné d'un seul tenant.
  - Bombé : 0,5 donne le nuage des DAO (arcs de 106°), 1 donne des demi-cercles. Les festons peuvent aussi aller
    vers l'intérieur.
  - Un trait ouvert reçoit ses festons à droite de son sens de parcours. Les arcs sont exacts et le sens des
    contours est gardé.
### v0.567.0 — Lignes de construction

- **Ligne de construction** (CAD › Création) : un guide oblique infini, d'après le XLINE de CADCraft.
  - Un premier clic pose le point de passage, puis chaque clic pose une ligne par ce point (Maj : angle par pas de
    15°). Échap termine. Une ligne horizontale ou verticale devient un guide ordinaire.
  - Avec F3, le curseur s'accroche sur les lignes et à leurs croisements, entre elles et avec les guides.
  - Une ligne se glisse parallèlement à elle-même. Ramenée sur une règle, elle est supprimée. Un double-clic règle
    son point de passage et son angle, ou la supprime.
  - « Effacer les guides » les efface aussi. Les lignes sont enregistrées avec le dessin et s'annulent.
### v0.568.0 — Ligne d'axe

- **Ligne d'axe** (CAD › Dessin technique) : un trait sur l'axe de deux traits droits, d'après le CENTERLINE de
  CADCraft.
  - Un clic sur chaque trait. La ligne va du milieu de leurs débuts au milieu de leurs fins (les traits sont remis
    dans le même sens) et déborde un peu à chaque bout. Deux traits en V donnent leur bissectrice.
  - L'aperçu suit le curseur après le premier clic. L'outil reste actif pour la paire suivante ; Échap termine.
  - Dans F10 › Dessin : le débord (2 mm par défaut) et, au choix, un trait mixte (motif CENTER) dont l'échelle est
    ajustée pour finir sur un tiret long aux deux bouts.
### v0.569.0 — Cote de longueur d'arc

- **Cote de longueur d'arc** (CAD › Mesure, ou Tab dans l'outil Cote) : la longueur développée d'un arc, d'après le
  DIMARC de CADCraft.
  - Un clic sur l'arc, un clic pour placer l'arc de cote. Les morceaux d'un même arc sont réunis, et les arcs de
    plus de 180° sont cotés en entier. Un cercle entier est refusé.
  - Lignes d'attache radiales, arc de cote concentrique, flèches et texte le long de l'arc (ou à plat selon les
    options de cotation). Le symbole d'arc est dessiné au-dessus du nombre, en traits, quelle que soit la police.
  - Si l'arc de cote est placé à l'intérieur, le texte va vers le centre. Comme les autres cotes, elle se rouvre
    par un double-clic et suit les déplacements, rotations et symétries.
### v0.570.0 — Raccord en courbe

- **Raccord en courbe** (Contours, à côté du Raccordement) : relie deux traits ouverts par une courbe qui les
  prolonge, d'après le BLEND de CADCraft. Les traits restent entiers, contrairement au Raccordement qui les coupe
  sur un arc.
  - Les bouts les plus proches des deux traits choisis sont reliés. Avec un seul trait, ses deux bouts sont reliés
    et le tracé se ferme.
  - Tangent : une courbe de Bézier qui part dans le prolongement de chaque trait. Lisse : la courbure est nulle aux
    deux bouts, pour un raccord sans à-coup sur des traits droits.
  - Joindre en un seul tracé (par défaut) ou garder la courbe à part.
### v0.571.0 — DXF : multilignes, repères et droites infinies

- **Lecture DXF** : des entités de DAO qui étaient laissées de côté sont reprises (liste d'après le lecteur DXF de
  CADCraft).
  - Multilignes (MLINE), repères multiples (MULTILEADER) et cotes de longueur d'arc (ARC_DIMENSION) : leurs traits,
    flèches et textes, comme les cotes et repères simples. Les tableaux (ACAD_TABLE) sont éclatés de même quand le
    fichier le permet.
  - Les droites infinies (XLINE) et les demi-droites (RAY) deviennent des lignes de construction : un guide
    ordinaire si elles sont horizontales ou verticales, un guide oblique sinon. Elles suivent l'unité du fichier et
    celles des calques cachés sont écartées.
### v0.572.0 — Cadres de tolérancement

- **Cadre de tolérancement** (Mesure, sous la cote de longueur d'arc) : le cadre des tolérances géométriques
  (ISO 1101, ASME Y14.5), d'après CADCraft.
  - Les 14 caractéristiques (rectitude, planéité, localisation, battement…), la tolérance avec sa zone cylindrique
    (Ø) et sa condition de matière (M, L, S), jusqu'à trois références et l'identificateur de référence sous le
    cadre.
  - Les symboles sont dessinés en traits : aucune police spéciale n'est nécessaire, et le cadre se grave comme une
    cote.
  - Un double-clic rouvre le cadre pour le modifier ; il garde sa place. Déplacé, tourné ou mis à l'échelle, il
    reste modifiable.
- **Lecture DXF** : les cadres de tolérancement (TOLERANCE) sont repris en cadres modifiables, à la hauteur de
  texte du style de cote du fichier. Un cadre de plusieurs lignes se modifie par sa chaîne.
### v0.573.0 — Cotes d'inspection, Espacer les cotes

- **Cote d'inspection** (Mesure) : la valeur des cotes sélectionnées passe dans un cadre à bouts ronds ou pointus,
  avec un libellé à gauche et le taux d'inspection à droite (100 % par défaut), séparés par des traits, d'après le
  DIMINSPECT de CADCraft. « Sans cadre » garde le libellé et le taux ; « Aucune » retire l'inspection.
  - Cotes linéaires, angulaires et radiales. Le texte dans la ligne coupe la ligne de cote autour du cadre.
  - Le double-clic sur une cote propose aussi l'inspection (groupe Inspection). Elle reste propre à la cote : les
    prochaines cotes ne la reprennent pas.
- **Espacer les cotes** (Mesure) : les cotes linéaires parallèles sélectionnées sont mises à intervalle régulier
  à partir de la plus proche de l'objet, d'après le DIMSPACE de CADCraft. Un intervalle de 0 les aligne sur elle.
  Les cotes d'une autre direction restent où elles sont.
### v0.574.0 — Cote radiale à ressaut, Ressaut de cote

- **Cote radiale à ressaut** (Mesure) : pour un grand rayon dont le centre sort de la feuille, d'après le
  DIMJOGGED de CADCraft. Clic sur le cercle ou l'arc, clic pour placer le texte, puis clic pour le départ de la
  ligne : elle part de là, parallèle au rayon, et le rejoint par un ressaut à 45° à mi-chemin. La valeur reste le
  vrai rayon. Aussi dans l'outil Cote (Tab, après la cotation depuis une ligne de base).
- **Ressaut de cote** (Mesure) : un zigzag sur la ligne des cotes linéaires sélectionnées, pour une longueur qui
  n'est pas à l'échelle du dessin, d'après le DIMJOGLINE de CADCraft. Sa position se donne en pourcentage de la
  longueur ; 0 le retire. Il n'est pas tracé s'il tomberait sur un texte qui coupe la ligne.
### v0.575.0 — Ressort, Filetage (tige filetée, taraudage)

- **Ressort** (3D › Volumes) : une section ronde ou carrée enroulée en hélice, d'après le Coil de SolidCraft.
  - Réglages : diamètre, pas, nombre de tours, taille de la section, angle de départ, sens d'enroulement (à droite
    ou à gauche).
  - Le diamètre se prend au milieu de la section, hors tout ou à l'intérieur. Un cercle choisi donne le sien.
  - Le ressort se pose sur les marqueurs ou les cercles choisis, sinon au centre de la plaque.
  - Il est refusé si ses spires se touchent (pas plus petit que la section) ou si la section atteint l'axe.
- **Filetage** (3D › Volumes) : un filetage ISO modélisé (profil de base ISO 68-1, pas gros ISO 261 ou pas donné :
  M8, M8x1), d'après le filetage modélisé de SolidCraft.
  - **Tige filetée** sur les marqueurs ou les cercles choisis, bouts chanfreinés jusqu'au fond de filet.
  - **Taraudage du volume choisi** à ces endroits : perçage au diamètre nominal moins le pas, puis le filet sur la
    profondeur donnée. Un trou borgne est percé deux pas plus bas, avec une pointe à 118°. Le trou peut aussi être
    débouchant.
  - Sans désignation, la taille vient du cercle choisi : son diamètre est celui de la tige, ou celui du perçage pour
    un taraudage (6,8 mm donne M8).
  - Filet à droite ou à gauche. Annulable.
### v0.576.0 — Perçage 3D, Tube, Volume englobant

- **Perçage 3D** (3D › Volumes) : des trous dans le volume choisi, depuis son dessus, sur les marqueurs ou les cercles
  choisis (un cercle donne son diamètre), d'après les perçages de SolidCraft.
  - Simple, lamé ou fraisé. Lamage et fraisure à 0 prennent 1,8 × le trou (profond du diamètre) et 2 × le trou.
  - Borgne, avec une pointe de foret (118° par défaut) en option, ou débouchant.
  - Annulable.
- **Tube** (3D › Volumes) : un tube plein ou creux (diamètre extérieur, paroi) le long des traits choisis, ouverts ou
  fermés, d'après le Pipe de SolidCraft. Il est posé sur le plan ou son axe est mis à la hauteur donnée. Les coins
  vifs sont pris en onglet.
- **Volume englobant** (3D › Volumes) : un pavé, ou un cylindre d'axe vertical, autour des volumes choisis, grossi
  d'une marge, d'après le Bounding solid de SolidCraft. Il sert de brut de la pièce.
### v0.577.0 — Nervure, Bossage

- **Nervure** (3D › Volumes) : un mur d'épaisseur donnée le long des traits choisis, réuni au volume choisi, d'après
  le Rib et le Web de SolidCraft.
  - Il monte du dessous du volume jusqu'à son dessus, ou jusqu'à une hauteur donnée.
  - Un trait ouvert est prolongé jusqu'aux parois (l'enveloppe du volume) : un trait tracé au milieu d'un bac va
    d'une paroi à l'autre. Plusieurs traits font plusieurs nervures, qui peuvent se croiser.
  - Les traits sont retirés (en option).
- **Bossage** (3D › Volumes) : un bossage de pièce plastique posé sur le volume choisi, aux marqueurs ou aux cercles
  choisis (un cercle donne son diamètre), d'après le Boss de SolidCraft.
  - Il part du dessus de la matière sous chaque point : le fond d'un bac, pas le haut de ses parois.
  - Fût en dépouille et trou (diamètre, profondeur depuis le haut).
  - Nervures rayonnantes en option : nombre, épaisseur, portée, retrait sous le haut.
  - Annulable.
### v0.578.0 — Relief sur cylindre

- **Relief sur cylindre** (3D › Volumes) : les formes fermées et les textes choisis, dessinés au-dessus d'un volume
  cylindrique couché (axe X ou Y), sont enroulés sur lui, en relief ou gravés, d'après l'Emboss sur cylindre de
  SolidCraft.
  - Le long de l'axe, le dessin ne change pas. L'écart à la ligne de dessus devient l'arc parcouru sur le pourtour :
    un texte tracé sur la ligne de dessus se lit, vu d'en haut, comme sur le dessin.
  - L'axe et le rayon viennent de l'encombrement du volume, ou se donnent.
  - Le dessin peut aller jusqu'à presque un demi-tour de chaque côté de la ligne de dessus.
  - Les formes et les textes peuvent être retirés. Annulable.
### v0.579.0 — Profilé

- **Profilé** (3D › Volumes) : des profilés posés le long des traits choisis, ou debout sur les marqueurs choisis,
  d'après les profilés de SolidCraft.
  - Sections : plat, rond plein, tube rectangulaire, tube rond, cornière, U et I. On donne la largeur (ou le
    diamètre), la hauteur, l'épaisseur de paroi, d'ailes ou de semelles, et l'âme du U ou du I.
  - Le long d'un trait ouvert ou fermé, les coins sont coupés en onglet. Le profilé est posé sur le plan à Z, ou
    centré à Z. La section se place à gauche du sens de tracé : inverser le trait retourne une cornière ou un U.
  - Sur un marqueur, on obtient un poteau vertical de la longueur donnée, sa section tournée de l'angle choisi.
  - Les traits peuvent être remplacés. Annulable.
### v0.580.0 — Lèvre, rainure, clip, appui

- **Lèvre ou rainure**, **Clip** et **Appui** (3D › Volumes) : les pièces plastiques de SolidCraft.
  - **Lèvre ou rainure** : une bande levée ou creusée le long du bord d'un volume coqué ouvert, sur son dessus,
    contre l'arête intérieure (autour de l'ouverture) ou extérieure. La rainure est élargie et creusée du jeu : la
    lèvre du bac entre dans la rainure du couvercle. Refus si la bande est plus large que le bord, ou si le dessus a
    plusieurs ouvertures semblables.
  - **Clip** : un bras vertical en porte-à-faux sur chaque marqueur choisi, avec au bout un crochet à face d'arrêt
    plate et rampe. On donne la longueur, l'épaisseur et la largeur du bras, la saillie, la hauteur et la direction
    du crochet, et un pied sous le dessus.
  - **Appui** : un plot rond ou rectangulaire sur chaque marqueur choisi, plein ou creux, en dépouille, mesuré au
    pied.
  - Clips et appuis se posent sur le dessus de la matière du volume choisi et lui sont réunis, ou restent des
    volumes à part. Sans volume choisi, ils se posent à Z. Annulable.
### v0.581.0 — Tôle pliée

- **Tôle pliée** (3D › Volumes) : une tôle debout le long d'une chaîne ouverte de traits droits, d'après la tôle
  pliée de SolidCraft.
  - La chaîne est une face de la tôle. La matière est à gauche ou à droite du sens de tracé. Chaque sommet devient
    un pli au rayon intérieur donné.
  - Le **développé** se pose sous les traits : un flan rectangulaire de la longueur développée, avec les axes de pli.
    Chaque zone de pli vaut angle × (rayon intérieur + K × épaisseur), facteur K réglable (0,44 par défaut). La
    barre d'état donne la longueur.
  - Refus : trait trop court pour ses plis, pli rabattu à 180°, arcs dans la chaîne.
  - Les traits peuvent être remplacés. Annulable.
### v0.582.0 — Bac en tôle

- **Bac en tôle** (3D › Volumes) : un bac dans un contour convexe de traits droits, d'après la tôlerie de SolidCraft
  (tôle de base et bords tombés).
  - Fond plat, et sur chaque côté un bord relevé à 90° au rayon intérieur donné. Le contour donne l'extérieur des
    bords, la hauteur se mesure sous tout. Les coins restent ouverts.
  - Le **développé** se pose à droite des contours : un flan en croix (le fond, prolongé sur chaque côté de la zone
    de pli puis du bord droit) avec les axes de pli. Facteur K réglable (0,44 par défaut).
  - Refus : contour concave, trop petit pour ses bords, bords moins hauts que rayon + épaisseur.
  - Les contours peuvent être remplacés. Annulable.
### v0.583.0 — Perforer

- **Perforer** (Opérations › Duplication) : des trous ronds dans la matière des contours fermés choisis, d'après la
  perforation de tôle de SolidCraft.
  - Disposition en quinconce (rangées à 60°, une sur deux décalée d'un demi-pas) ou en grille carrée. On donne le
    diamètre, le pas entre axes et la marge (par défaut le diamètre).
  - Les contours choisis sont réunis : une découpe, même dans une autre forme, reste libre. Les trous gardent la
    marge aux bords, aux découpes et aux traits ouverts choisis, comme les axes de pli d'un développé de tôle.
  - Rangées centrées dans l'encombrement (marges égales), ou depuis le coin bas gauche ou bas droit.
  - La barre d'état donne le nombre de trous et la part ajourée. Annulable.
### v0.584.0 — Échelle 3D

- **Échelle 3D** (3D › Volumes) : les volumes choisis mis à l'échelle, d'après l'échelle de SolidCraft.
  - Un même facteur pour les trois axes, ou un facteur par axe : compensation de retrait d'un moulage, pièce
    étirée en hauteur…
  - Le point fixe est le centre du dessous (la pièce reste posée), le centre ou l'origine du dessin. Il se prend
    pour chaque volume ou pour l'ensemble.
  - Facteurs strictement positifs : une symétrie passe par Symétrie en Z. Annulable.
### v0.585.0 — Ourlets de la tôle pliée

- **Tôle pliée** : des ourlets au début et à la fin de la chaîne, d'après les ourlets de SolidCraft.
  - Un retour replié à 180° du côté de la matière, de la longueur donnée, avec un jeu réglable (0 : ourlet
    écrasé).
  - Le développé compte chaque ourlet, π × (jeu / 2 + K × épaisseur) puis son retour, avec son axe de pli à 180°.
  - Refus si un retour est plus long que le plat de son trait.
### v0.586.0 — Cellules

- **Cellules** (3D › Volumes) : des volumes à part tirés des volumes choisis, d'après le remplissage de cellules de
  SolidCraft.
  - **Morceaux** : chaque partie d'un seul tenant qui est dans certains volumes et hors des autres. Deux volumes qui
    se recouvrent donnent trois morceaux.
  - **Vides enfermés** : chaque vide que les volumes enferment entièrement. Une boîte et son couvercle donnent leur
    intérieur ; un moule fermé donne son empreinte.
  - Les volumes choisis restent, ou sont remplacés. La barre d'état donne le nombre de cellules et leur volume.
    Annulable.
### v0.587.0 — Plier la tôle

- **Plier la tôle** (3D › Volumes) : le flan dessiné à plat, plié le long de traits, d'après le pliage de SolidCraft.
  - Le flan est fait des contours fermés choisis (les trous restent des trous), les plis des traits ouverts choisis.
  - Chaque trait lève le côté le plus petit du flan, vers le haut ou vers le bas, de l'angle donné (jusqu'à 180°) au
    rayon intérieur donné. La plus grande partie reste à plat.
  - La zone de pli est large de angle × (rayon + K × épaisseur). Le trait est au milieu de la zone, à son début, à sa
    fin ou sur la ligne de moule.
  - Un trait plie les morceaux du flan qu'il traverse : une patte, ou les deux côtés d'un cadre.
  - Un flan en croix donne une boîte, le trait au début de la zone (coins ouverts).
  - Refus si un trait ne traverse pas le flan ou si deux zones de pli se chevauchent.
### v0.588.0 — Analyse de surface

- **Analyse de surface** (3D › Volumes) : la pièce 3D en couleurs dans la vue 3D, d'après les analyses de SolidCraft.
  Elle porte sur les volumes du dessin ou sur un fichier STEP ouvert.
  - **Dépouille** vers une direction de démoulage (Z+, Z−, X±, Y±) : vert, dépouille d'au moins l'angle donné ;
    jaune, moins (parois droites) ; rouge, au moins l'angle à l'opposé (l'autre moitié du moule).
  - **Accessibilité** le long d'une direction : vert, face atteinte (tournée vers elle ou parallèle, et rien
    au-dessus) ; rouge, face cachée (contre-dépouilles, dessous). Pour juger un usinage à outil vertical ou un
    démoulage.
  - La barre d'état donne la part de la surface de chaque couleur. « Aucune » rend les couleurs de la pièce.
  - L'affichage filaire passe en ombré. Le choix des faces reste possible pendant l'analyse.
### v0.589.0 — DXF : maillages 3D en volumes

- **DXF** : les maillages 3D sont repris au lieu d'être écartés, d'après CADCraft.
  - Maillages polyface et polymesh (POLYLINE), MESH et faces 3D (3DFACE) deviennent des volumes, un objet chacun ;
    les faces 3D d'un même calque et d'une même couleur font un seul volume.
  - Un maillage ouvert (une surface) est repris en son contour vu de dessus.
  - Blocs, unités du fichier et calques éteints sont suivis comme pour le reste du dessin.
### v0.590.0 — Rappeler l'effacement

- **Rappeler l'effacement** (Edition › Presse-papiers) : ce que le dernier Effacer a retiré revient, d'après OOPS
  de CADCraft.
  - Ça marche même après d'autres modifications, ce que Défaire ne permet pas sans les perdre.
  - Chaque objet revient juste au-dessus de celui qui était dessous, ou sous celui qui était dessus s'il n'est plus
    là. Les objets rappelés sont sélectionnés.
  - Seul le dernier effacement compte. Rien ne revient s'il a été défait ; un objet déjà dans le dessin, ou dont le
    calque n'existe plus, reste dehors. Une seule annulation.
### v0.591.0 — Changer par un point

- **Changer par un point** (Dessin technique) : un point cliqué change les objets choisis, d'après CHANGE de
  CADCraft.
  - Le bout le plus proche de chaque trait droit vient au point, le reste du tracé ne bouge pas. Un tracé ouvert
    compte aussi si son dernier morceau est droit.
  - Chaque cercle passe par le point et garde son centre et son sens.
  - Un texte choisi seul est posé par son origine sur le point.
  - Le reste (rectangles, bouts courbes, volumes, objets verrouillés) est laissé tel quel ; les objets dans les
    groupes sont suivis. Les objets changés restent sélectionnés. Une seule annulation.
### v0.592.0 — Relèvements dans les calculs

- **Calculs dans les champs** : un relèvement de géomètre donne sa direction, d'après CADCraft.
  - « N45°E », « S30d15'W », « N12,5W » : l'angle compté depuis le nord ou le sud, vers l'est ou l'ouest.
  - Un point cardinal seul vaut aussi : « N », « E », « S », « W ».
  - Le résultat est en degrés depuis l'est, dans le sens trigonométrique, comme les autres angles : N vaut 90,
    N45°E vaut 45, S30°W vaut 240. Un angle au-delà de 90° est refusé.
### v0.593.0 — Calculs précédents et dernier résultat

- **Calculs dans les champs** (touche =) : les calculs précédents et le dernier résultat sont gardés, d'après la
  calculatrice rapide de CADCraft.
  - La liste du calcul propose la valeur du champ, puis les 15 derniers calculs, le plus récent d'abord. Un simple
    nombre n'y entre pas.
  - « ans » vaut le dernier résultat : « ans/2 », « ans+3 ».
  - Les deux restent d'une séance à l'autre. Un calcul refusé ne change rien.
### v0.594.0 — Dupliquer sur courbe par écart

- **Dupliquer › Sur courbe** : un écart en mm pose un exemplaire tous les tant de mm depuis le départ de la
  courbe, autant qu'elle en porte, d'après CADCraft.
  - Sur une courbe ouverte, le bout est occupé si l'écart tombe juste ; sur un contour fermé, pas de copie doublée
    au retour.
  - 0 garde le nombre d'exemplaires. L'écart est retenu d'une fois sur l'autre ; un écart trop petit pour la
    courbe (plus de 10 000 copies) est refusé.
- **FAO** : monter, descendre ou dupliquer une opération ne choisit plus qu'elle, même avec Ctrl ou Maj enfoncé ;
  la liste pouvait garder plusieurs lignes choisies et l'action suivante partir de la mauvaise.
### v0.595.0 — Arc centre, départ, fin ; Cercle 2 points

- **Arc centre, départ, fin** (CAD › Création) : un clic au centre, un au départ, qui donne le rayon, un pour la
  fin, d'après CADCraft. L'arc tourne dans le sens trigonométrique ; avec Ctrl, dans le sens horaire. L'aperçu
  suit le pointeur.
- **Cercle 2 points** (CAD › Création) : deux clics, les bouts d'un diamètre.
### v0.596.0 — Polygone par côté

- **Polygone par côté** (CAD › Création) : deux clics donnent les bouts d'un côté, d'après CADCraft.
  - Le polygone, avec le nombre de côtés du ruban, se pose à gauche du côté tracé ; avec Ctrl, à droite.
  - Il reste un polygone paramétré, réglé par la longueur de son côté : on le retouche comme les autres.
### v0.597.0 — Ellipse par axe

- **Ellipse par axe** (CAD › Création) : deux clics aux bouts d'un axe, puis un clic à la distance voulue du
  centre pour l'autre demi-axe, d'après CADCraft.
  - L'ellipse suit l'inclinaison de l'axe : une ellipse penchée se trace d'un seul geste.
  - Elle reste une ellipse paramétrée, retouchable comme celle tracée en cadre.
### v0.598.0 — Rectangle 3 points

- **Rectangle 3 points** (CAD › Création) : deux clics pour un côté, qui donne l'inclinaison, un troisième pour
  l'autre côté, d'après CADCraft.
  - Le rectangle se pose du côté du troisième clic, avec les coins du rectangle par défaut (droits, arrondis,
    chanfreins ou creux).
  - Il reste un rectangle paramétré, retouchable comme les autres.
### v0.599.0 — Polygone circonscrit

- **Polygone** (CAD › Création) : avec Maj, le pointeur donne le milieu d'un côté au lieu d'un sommet, d'après
  CADCraft. Le polygone est alors circonscrit au cercle tracé. Ctrl + Maj met un côté en haut. L'outil a
  maintenant une infobulle.
### v0.600.0 — Ouvrir en plein écran, plaque par défaut 500 × 400

- **Ouvrir** (Ctrl+O) : la fenêtre s'ouvre toujours agrandie, même si elle avait été réduite la dernière fois.
  Le bouton ⛶ ou F11 la met en plein écran, et elle se rouvre ainsi la fois suivante. La boîte Ouvrir avec
  aperçus s'ouvre aussi agrandie.
- **Plaque des nouveaux dessins** : 500 × 400 mm, épaisseur 50 mm, coins de rayon 10 mm. Le zéro du dessin est au
  centre de la plaque. Deux réglages s'ajoutent dans les options (F10) :
  - le rayon des coins ;
  - l'origine, au centre ou au coin bas-gauche.
### v0.601.0 — Onglet Design 3D

- **Design 3D** : nouvel onglet du ruban pour les volumes, rangé comme SolidCraft. Les volumes quittent l'onglet 3D,
  qui garde les reliefs et les vues. Groupes :
  - Créer ;
  - Modifier ;
  - Combiner ;
  - Tôlerie ;
  - Plasturgie ;
  - Inspecter ;
  - Échanges (import, volume en relief et l'inverse).
### v0.602.0 — Couper un volume par un trait

- **Couper** (Design 3D › Modifier) : nouveau plan « Vertical, par le trait choisi », d'après SolidCraft. Le plan
  passe par le premier segment de la forme 2D choisie avec les volumes, il peut donc être en biais. Le côté + est à
  droite du trait, dans son sens de tracé. Le trait reste dans le dessin.
### v0.603.0 — Extrusion symétrique, deux côtés, à travers tout

- **Extrusion** (Design 3D › Créer), d'après SolidCraft :
  - **Côtés** : un côté (le signe de la hauteur), symétrique (la hauteur en tout, moitié de chaque côté) ou deux
    côtés (une hauteur de chaque côté du plan du dessin) ;
  - **À travers tout** : la hauteur traverse les volumes choisis avec les formes ;
  - **Opération** : nouveaux volumes, ou réunis aux volumes choisis, soustraits ou en commun avec eux. Un trou
    débouchant se fait en une commande.
  La dépouille reste d'un seul côté.
### v0.604.0 — Jeu entre volumes

- **Jeu entre volumes** (Design 3D › Inspecter), d'après SolidCraft. Pour les volumes choisis, il relève :
  - les chevauchements, avec leur volume commun ;
  - les contacts ;
  - les paires plus proches qu'un jeu minimal, avec leur distance et leur lieu ;
  - le plus proche voisin de chaque volume.

  Les paires éloignées sont écartées sur leur encombrement.
- Infobulles de Couper et d'Extrusion mises à jour (trait choisi, côtés, opération).
### v0.605.0 — Comparer deux volumes

- **Comparer deux volumes** (Design 3D › Inspecter), d'après SolidCraft : deux versions d'une pièce posées l'une
  sur l'autre. Le premier volume choisi est A, le second B. Le compte rendu donne :
  - les volumes, les aires et la différence de volume ;
  - l'écart de chaque surface à l'autre : le plus grand, son lieu et l'écart moyen ;
  - les régions de matière de A seulement ou de B seulement, avec leur volume et leur écart.

  « Identiques » s'affiche si aucune région ne dépasse la tolérance. Les régions peuvent être ajoutées au dessin
  (rouge : A seul, vert : B seul).
### v0.606.0 — Aligner des volumes

- **Aligner** (Design 3D › Modifier) : les volumes choisis sont alignés sur le premier choisi, qui ne bouge pas.
  Chaque axe se règle à part : côtés ou centres alignés, contre la référence, posés dessus ou dessous, avec un jeu
  au choix. Par défaut, centrés et posés sur la référence : un couvercle sur sa boîte en une commande.
### v0.607.0 — Coque ouverte de plusieurs côtés

- **Coque** (Design 3D › Modifier), d'après SolidCraft :
  - les parois se prennent dedans (comme avant), dehors (le volume devient le vide) ou des deux côtés ;
  - la coque peut s'ouvrir par un ou plusieurs côtés : dessus, dessous, X−, X+, Y−, Y+. Un tube se fait en
    ouvrant les deux bouts, un bac en ouvrant le dessus.
### v0.608.0 — Un VND s'ouvre toujours sur son dessin dans TypeEdit

- **VND vide dans TypeEdit 13** : TypeEdit n'affiche à l'ouverture que son premier plan. Un dessin dont le premier
  calque est vide ou masqué s'ouvrait donc sur une page blanche, alors que l'aperçu de l'explorateur et VectorDrive
  montraient tout. Le premier calque qui a quelque chose à montrer est désormais écrit en premier (les autres gardent
  leur ordre), et le rapport d'export le dit.
- Un calque masqué ou verrouillé dans VectorDrive l'est aussi dans le VND.
### v0.609.0 — Rouvrir un onglet fermé

- **Clic droit sur la barre d'onglets › Rouvrir un onglet fermé** : les 25 derniers onglets fermés, du plus récent au
  plus ancien, gardés d'une séance à l'autre. **Ctrl+Maj+T** rouvre le dernier. Un dessin sans fichier est gardé pour
  la séance (les cinq derniers) ; un fichier disparu est signalé.
- **Ctrl+Maj+1 … 9** (le chiffre lui-même sur un clavier AZERTY) fait comme **Ctrl+& … ç**, sauf si un raccourci
  Ctrl+Maj+chiffre a été défini.
### v0.610.0 — PDF et Illustrator lus comme Inkscape les montre

- **Calques du fichier** : les calques d'un PDF ou d'un Illustrator (contenu optionnel) deviennent des calques de
  VectorDrive, masqués s'ils le sont dans le fichier. Un .ai qui contient plusieurs variantes d'un logo n'empile plus
  toutes les variantes : seule la variante visible s'affiche, les autres sont à un clic dans le panneau des calques.
- **Détourage** : un masque d'écrêtage coupe maintenant les surfaces qu'il contient, et ce qui est tout dehors n'est
  plus importé.
- **Surfaces fermées** : une surface peinte est un contour fermé, même sans fermeture explicite dans le fichier. Les
  recouvrements d'un même tracé sont réunis (règle non nulle du PDF) : plus d'encoches aux coins des traits vectorisés.
- **Aplats blancs** : un aplat blanc est retiré de ce qu'il recouvre, et n'est plus un contour à graver. Il est rangé
  dans un calque masqué « … (blanc) ». Un fond blanc avec un trait reste un contour.
- « Tout voir » cadre ce qui se voit, pas les calques masqués.
### v0.611.0 — Dégagement bas sur la zone surfacée, remontées en rapide

- **Après un surfaçage**, les liaisons qui restent au-dessus de la zone surfacée se font à un dégagement bas
  (*Dégagement sur une zone déjà surfacée*, 0,2 mm par défaut) ; ce qui traverse une partie non surfacée garde le
  *Dégagement* de l'opération. Les deux se règlent par opération, et par F10 › FAO pour les nouvelles. 0 : sans.
  L'outil entier doit rester dans la zone, du départ à l'arrivée de la liaison.
- **Toute remontée verticale vers le dégagement se fait en rapide**, sauf le perçage réglé en remontée à vitesse de
  travail.
- PDF : un texte dans la page ne fait plus échouer la lecture (depuis la v0.610.0).
### v0.612.0 — Gravure 2,5D en contour 2D, sans remontées d'angle

- **Gravure 2,5D › Contour 2D sans remontées d'angle, puis vidage** : à l'outil conique, un seul contour au fond, le
  haut du cône sur le bord de la forme, à un **décalage XY** réglable (+ vers l'intérieur). Le fond est ensuite vidé.
- Avec **Lier au parcours précédent**, seul ce que les outils d'avant n'ont pas atteint est vidé ; le contour reste
  entier. Avec *Bords seulement*, le contour seul.
- Ce qui reste hors de portée à cette profondeur (angles vifs, parties étroites) est chiffré dans les avertissements.
### v0.613.0 — Remplir ou vider la sélection

- **Remplir / vider** (Accueil › Presse-papiers) : les contours fermés de la sélection, groupes compris. Tout ce qui est
  rempli se vide, sinon tout se remplit. Un import rempli (PDF, Illustrator…) se vide ainsi, et inversement.
- Les traits ouverts ne se remplissent pas. Si l'affichage Remplissage (Ctrl+9) est actif, le message le rappelle : il
  montre tout rempli quoi qu'il en soit.
### v0.614.0 — Copier-coller avec TypeEdit, dans les deux sens

- **Coller dans VectorDrive ce qu'on a copié dans TypeEdit** : courbes, groupes, textes modifiables, à leur place, sur
  l'outil courant.
- **Copier dans VectorDrive, coller dans TypeEdit** : mêmes objets, mêmes coordonnées (l'origine du dessin devient le zéro
  de TypeEdit), textes modifiables quand TypeEdit sait les relire, en courbes sinon. Essayé pour de bon avec TypeEdit 13.
- Une copie faite ailleurs ne colle plus l'ancienne copie de VectorDrive ; une copie illisible ne colle rien et le dit.
- Une copie venue d'une autre fenêtre de VectorDrive se colle aussi.
- Un objet TypeEdit ne porte pas d'outil : collé, il prend celui du plan courant, dans les deux sens.
### v0.615.0 — BAT : logos coloriés dans la couleur de leurs contours, précision des cotes, thème

- **Coloriage « Couleur des contours »**, nouveau réglage par défaut : contours fermés seulement, pleins et vides alternés
  d'un contour à l'autre (pair-impair), à travers les objets et les outils, chaque plein dans la couleur de son contour. Les
  traits ouverts restent des traits. « Logo en noir » et « Teinte claire » restent au choix.
- **Précision des cotes** réglable (0 à 4 décimales), avec ou sans les zéros de la fin, partout sur la page.
- **Thème de couleur** : la couleur du cartouche peut aussi aller au cadre, à l'en-tête et aux cotes, et peut être prise sur
  le logo. Jamais en noir et blanc.
- **Logos** : image ou dessin (SVG, PDF, Illustrator, DXF, VND…), un dessin restant en tracés exacts ; **second logo** à droite
  (celui du client…) ; choix dans le BAT, parmi les logos déjà employés. L'entreprise se règle aussi dans le BAT.
### v0.616.0 — BAT : bruts des ensembles, cotés à part

- **Fichier › Brut de l'ensemble…** : le morceau de matière d'un objet ou d'un groupe (largeur, hauteur, décalage, épaisseur,
  nom). Plusieurs objets sélectionnés : ils sont groupés en un ensemble.
- Sur le BAT, chaque brut est dessiné et **coté à part** : brut et ensemble, l'un ou l'autre, ou rien, au choix pour chacun.
  La page se cadre sur les bruts ; un seul brut donne les dimensions du cartouche.
- À l'écran : un cadre pointillé, qui suit l'ensemble quand il bouge, tourne ou change d'échelle. Le brut n'est ni gravé, ni
  usiné, ni exporté.
### v0.617.0 — BAT : cotes de brut lisibles

- Les cotes verticales d'un brut se lisent de bas en haut, comme toutes les autres cotes de la page (depuis la v0.616.0).
### v0.618.0 — VND : relu avant d'aller sur le disque

- Chaque VND est relu avant d'être posé sur le disque. Illisible, ou vide alors que le dessin ne l'est pas : rien n'est écrit, l'erreur est dite, et le fichier déjà là reste intact.
- Écriture d'un seul coup : une panne en cours d'enregistrement ne laisse ni fichier vide ni fichier coupé. Un fichier tenu ouvert par un autre logiciel donne une erreur, pas un fichier à moitié écrit.
- Remarques au rapport : relecture incomplète, premier plan vide (TypeEdit s'ouvre sur ce plan), coordonnées invalides.
### v0.619.0 — VND : un dessin abîmé n'empêche plus d'enregistrer

- Noms de plan avec un emoji ou un caractère hors plan de base : la longueur était comptée en caractères et non en unités UTF-16. Le fichier en devenait illisible à partir de là. Corrigé, le nom se relit à l'identique.
- Coordonnée infinie : l'enregistrement plantait. NaN, infini ou valeur absurde (plus de mille kilomètres) : le contour est écarté du fichier, les autres restent, et le rapport en donne le compte. Le dessin ouvert n'est pas modifié.
- Numéro d'outil négatif ou impossible : l'enregistrement plantait. L'objet est écrit sur l'outil 1 et le rapport le dit.
- Plaque ou origine aux valeurs invalides : écartées, et dites au rapport.
- Copier vers TypeEdit : mêmes règles, rien d'invalide n'arrive dans le presse-papiers.
### v0.620.0 — Point de référence, répéter, transformer chaque objet

- **F2 : point de référence à 9 positions.** Les coins, milieux et centre du cadre : X et Y donnent la position de ce point, et largeur, hauteur, rotation et échelle se font autour de lui. Pour poser un coin à une cote : cliquer le coin, taper X et Y. Le choix est gardé ; le centre reste le réglage d'usine.
- **Répéter la transformation** (Ctrl+Alt+T) : refait le dernier déplacement, la dernière rotation ou mise à l'échelle, à la souris ou au clavier.
- **Répéter et copier** (Ctrl+Alt+Maj+T) : la même chose sur une copie. Déplacer un objet, puis répéter autant de fois que de copies voulues ; une rotation répétée tourne autour du même point.
- **Transformer chaque objet** : déplacement, échelle et rotation de chaque objet autour de lui-même, et non de la sélection entière.
### v0.621.0 — Fichiers de clients : CorelDRAW, EMF, WMF, Visio, HPGL

- **Ouvrir CorelDRAW (.cdr, .cmx), EMF, WMF, Visio (.vsd, .vsdx) et WordPerfect (.wpg)** par Inkscape, s'il est installé sur le poste : VectorDrive lui fait écrire un SVG, puis le lit. Sans Inkscape, le message dit quoi faire. Le chemin se règle dans F10 › Fichiers s'il n'est pas à sa place habituelle.
- **HPGL (.plt, .hpgl, .hpg), en lecture et en écriture** : traits, cercles, arcs, rectangles, absolu et relatif. Une plume = un outil. Les textes du traceur ne sont pas lus, le rapport en donne le compte ; les images ne sont pas écrites.
### v0.622.0 — Vectoriser un logo en couleurs

- **Vectoriser** cherche maintenant plusieurs couleurs : une forme remplie par couleur, sur l'outil de cette couleur (repris s'il existe, ajouté sinon), le tout en un groupe. Le fond est laissé de côté, transparent ou non, sauf si on demande de le tracer. Le nombre donné est un plafond : les couleurs presque égales, les pixels isolés et les liserés adoucis entre deux couleurs ne font pas une couleur.
- En couleurs, les coins restent vifs et à leur vraie place, et un contour se réajuste en peu de courbes.
- La **courbure continue** en noir et blanc garde elle aussi ses coins à leur vraie place.
- **Correction — Approximer** : une courbe presque droite perdait son point d'arrivée. Un contour fait de telles courbes pouvait s'écarter du dessin de plusieurs unités.
### v0.623.0 — Orthographe

- **Orthographe** relit les textes de la sélection, sinon de tout le dessin, avec le correcteur de Windows : les mots ajoutés dans Windows sont connus, aucun dictionnaire à installer.
- Un mot à la fois, dans son texte, avec des propositions : **Remplacer**, **Ignorer**, **Ignorer partout**. Un mot répété se retire avec son espace. Chaque correction s'annule et refait le contour du texte.
- Les textes en majuscules sont relus aussi, comme on grave souvent ; un mot en majuscules sans ses accents n'est pas compté comme faute. Les variables et ce qui porte un chiffre ne sont pas touchés.
- La langue est celle du poste, ou celle choisie dans **F10 › Texte**. Sans correcteur pour cette langue, la commande le dit.
### v0.624.0 — Lettres : régler chaque lettre, exposant, indice, crénage manuel

- **Lettres…** (groupe Texte) règle les lettres choisies d'un texte droit : **crénage** (décale aussi ce qui suit), **décalage** en X et en Y, **hauteur**, **largeur**, **rotation** autour de la lettre.
- Boutons **Exposant**, **Indice** et **Normal** : m², H₂O en deux clics.
- **Alt+flèches** : crénage et décalage en Y au clavier, plus vite avec Maj. Sans lettre choisie, c'est la lettre qui suit le curseur.
- L'effet est immédiat sur le dessin, tout s'annule en une fois, et **Annuler** revient à l'état d'avant.
- Les distances sont en % de la hauteur : elles suivent le corps du texte. Corriger le texte ensuite ne perd pas les réglages des lettres restantes.
- Dans un VND ou une copie vers TypeEdit, un tel texte part en courbes, à sa vraie forme : TypeEdit ne garde pas ces réglages dans un paragraphe.
### v0.625.0 — BAT : le nom d'un brut laisse la place à ses voisins

- Le nom d'un brut (« Brut … × ép. … ») ne chevauche plus les cotes ou le cadre d'un brut voisin : il passe au-dessus de son brut si la place est libre, sinon dessous, à droite ou à gauche.
### v0.626.0 — Italique et souligné réglables

- **Italique et souligné…** (groupe Texte) : angle de l'italique, de -75° à 75° ; distance et épaisseur de la barre du souligné, en % de la hauteur. Une distance négative passe la barre dans les lettres.
- Les boutons **Italique** et **Souligné** reprennent ces derniers réglages.
### v0.627.0 — Courbe par équation et guilloché

- **Courbe par équation** (Métiers) : x(t) et y(t), y = f(x) ou polaire r = f(a), à 0,01 mm près, en peu de courbes. Rose, cardioïde, lemniscate, spirales, cœur, Lissajous et sinusoïde sont tout prêts. Aperçu pendant la frappe.
- La courbe s'arrête au bord de ce qui se calcule et se coupe à un saut : pas de trait entre deux branches de 1/x.
- **Guilloché** (Métiers) : traits entrelacés, comme sur un billet ou un cadran. **Rosette** autour d'un centre, **bande** droite, **spirographe**, avec une seconde vague pour faire onduler le motif.
- Rien n'est exécuté : une formule ne peut contenir que des calculs.
### v0.628.0 — Imbriquer selon la vraie forme

- **Imbriquer** peut ranger les objets **selon leur vraie forme** : ils s'emboîtent, un L dans un autre, une étoile dans un creux. Sur un essai, 23 objets au lieu de 15 sur la même plaque.
- Rotation par pas réglable, ou aucune. Une pièce peut aller **dans le trou** d'une autre, si on le demande.
- L'écart demandé est toujours tenu ; une **précision** plus grossière va plus vite et perd un peu de place. Le message donne l'occupation de la plaque.
- **Exemplaires 0** remplit la plaque, de la même façon. Ce qui ne tient pas passe sur des plaques suivantes.
- Les rectangles restent le réglage par défaut : ils serrent au dixième près les pièces rectangulaires, là où la forme laisse une demi-case de jeu.
### v0.629.0 — Courber le long d’un tracé

- **Courber le long d’un tracé** (Opérations, Contours) : les objets, textes compris, suivent une courbe et se déforment avec elle, à 0,005 mm près, là où la duplication le long d’une courbe ne fait que placer des copies raides. Quatre poses : étiré sur toute la longueur, à sa taille, répété à la suite, répété sur toute la longueur. Réglages : ce qui se pose sur le tracé (milieu, bas, haut), hauteur, écart au tracé, départ, écart entre copies, miroir, sens. Sur un tracé fermé, on tourne ; au-delà d’un tracé ouvert, on continue tout droit. Coins vifs : le dessin reste d’un seul tenant. Si le tracé tourne plus serré que la hauteur du dessin, la barre d’état prévient qu’il se replie.
- Le résultat est un groupe re-modifiable au double-clic ; on peut garder le tracé dans le dessin.
- **Boîte d’un groupe** : les objets masqués (originaux d’une enveloppe, d’un tampon…) ne comptent plus dans sa taille.
### v0.630.0 — Copie imbriquée

- **Copie imbriquée** (Métiers, Duplication) : un tableau donne le nombre d’exemplaires de chaque objet (ou le même pour tous) et son nom, modifiable. Rangement par rectangles ou selon la vraie forme, depuis l’un des quatre coins, en rangées ou en colonnes, avec un plan par plaque (ou les plaques suivantes à droite). Textes et groupes restent intacts, un objet à 0 exemplaire ne bouge pas.
- **Ruban de TypeEdit** : orthographe, plan de référence d’un relief et réglages par lettre du mode texte reliés à ce qui existe (Orthographe, Aligner un plan à zéro, Lettres).
### v0.631.0 — Tampon : formats de support et découpe

- **Support imposé** : rectangle, cercle ou ellipse, à un format courant (38 × 14, 47 × 18, ø 40…) ou sur mesure, et vos propres formats enregistrés sous un nom. Le dessin est centré et, au choix, mis à l’échelle pour tenir, marge comprise : dans un cercle ou une ellipse, on juge sur le tracé lui-même, pas sur sa boîte. S’il dépasse, la barre d’état prévient.
- **Forme de la découpe** : le support, optimisée (autour de la forme des objets), rectangle, ou boîtes fusionnées (par ligne), avec un décalage.
- Un tampon déjà fait change de format au double-clic ; l’original reste à sa taille.
### v0.632.0 — Copier dans une forme

- **Copier dans une forme** (Métiers, Duplication) : des exemplaires des objets remplissent une forme choisie, selon leur vraie forme. Autant qu’il en tient ou un nombre donné, marge au bord, écart, rotation. Les trous de la forme restent vides, les originaux ne bougent pas, et la barre d’état dit combien sont placés, le taux d’occupation et ce qui n’a pas trouvé place.
### v0.633.0 — Polices SVG

- **Polices SVG** : les polices au format SVG, dont les polices monotrait libres (Hershey, EMS), sont lues comme les autres polices : traits ouverts gravés en un passage, approche et crénage du fichier. **Ajouter une police SVG…** (à côté de Changer la police) copie le fichier dans le dossier des polices de l’utilisateur ; un SVG sans police est refusé.
### v0.634.0 — Import IGES

- **IGES** (`.igs`, `.iges`) : les courbes (ligne, arc, conique, polyligne, spline, NURBS, composite, sous-figures) arrivent par niveau, en courbes exactes quand c’est possible, et raccordées. Les surfaces NURBS, détourées ou faces de solide, donnent la silhouette et un calque par hauteur de face plate ; la pièce s’ouvre aussi en 3D. Les unités du fichier sont suivies, sauf si la pièce devient démesurée : elle est alors lue en millimètres. Ce qui n’est pas lu (surfaces de révolution, cylindres tabulés, nuages de points) est dit dans le compte rendu.
### v0.635.0 — Texte dans une forme

- **Dans une forme** (Texte) : le texte coule dans une forme fermée, ligne après ligne, de part et d’autre de ses trous et de ses creux ; aucune lettre ne dépasse. Taille choisie ou plus grande taille qui fait tout tenir, alignement, justification, interligne, marge, bloc centré dans la hauteur. Les lignes restent du texte vivant et un double-clic reprend le tout ; ce qui n’a pas trouvé place est signalé.
### v0.636.0 — Relief : mode prismatique, facettes au bord ; éclairage de la vue 3D

- **Mode prismatique** (TypeArt, Création) : des lettres ou des objets à Z constant, avec le profil choisi sur leur bord et un plateau au centre. Le texte n’a pas besoin d’être converti.
- **Facettes au bord** (TypeArt, Retouches) : autour du relief, une pente descend de son bord jusqu’à zéro.
- **Éclairage** (TypeArt, Vues 3D) : la direction de la lumière de la vue 3D, gardée d’une session à l’autre.
- **Inverser l’ordre dans les groupes** : les objets de chaque groupe, sous-groupes compris, passent dans l’ordre inverse.
- Effacer une partie, Extraire une partie, Poser et Bordure répondent aussi à leur nom de commande TypeEdit.
### v0.637.0 — Repères : la liste, la répartition, un objet en repères

- **Repères…** : la liste des repères du dessin, horizontaux, verticaux et obliques, à modifier, ajouter ou supprimer ; des colonnes et des rangées réparties sur la plaque, avec une marge.
- **Objet en repères** : chaque côté droit des objets sélectionnés devient un repère, et les côtés de la boîte pour une courbe ou un texte. Les objets restent, un repère déjà là n’est pas doublé.
### v0.638.0 — Copies liées

- **Copie liée** (Alt+D) : une copie qui suit la forme de son original. Modifier les nœuds, le texte ou la taille de l’original modifie toutes ses copies ; chacune garde sa place, sa rotation et son échelle, et déplacer l’original ne les déplace pas. Elle suit aussi son outil, sauf si elle en a reçu un autre.
- **Délier la copie** rend une copie indépendante, **Sélectionner l’original** retrouve son original. Modifier les nœuds d’une copie, ou supprimer l’original, la délie aussi.
- Le lien est conservé dans le format natif ; dans les autres formats, une copie est un objet ordinaire.
### v0.639.0 — Enveloppe par courbes, grille de déformation du relief

- **Enveloppe par courbes** : les objets sélectionnés, textes compris, se déforment entre quatre courbes qui se touchent, dans n’importe quel ordre et n’importe quel sens, ou dans un contour fermé coupé à ses quatre coins. Le résultat reste modifiable au double-clic. Le rangement des côtés tourne le dessin d’un quart de tour dans l’enveloppe.
- **Grille de déformation** (TypeArt) : la même enveloppe pour un relief, Z inchangé, pour un décor en bandeau ou en arc. Le pas du relief déformé se règle.
- La commande TE « Texture sur niveaux de gris » ouvre le relief d’une image.
### v0.640.0 — Usinage d’un relief : ébauche, reprise, angle, spirale, tranches parallèles

- Un relief s’usine maintenant avec les stratégies 3D : **ébauche 3D**, **reprise 3D** derrière un plus gros outil, **niveaux constants** et **surface 3D**. Sélectionnez le relief dans l’opération ; l’outil reste dans son rectangle, sommet affleurant. Une pièce 3D donnée à l’opération passe avant.
- **Balayage** du relief et de la surface 3D : passes selon X ou Y, **suivant un angle** avec une passe croisée au choix, ou **en spirale**, vers l’intérieur ou l’extérieur, en avalant ou en opposition.
- **Tranches parallèles au profil** : autant de passes qu’il faut, chacune décalée de la profondeur de passe au-dessus de la surface, sans jamais remonter.
- **Suivre le profil 3D** : décoché, l’outil ne repasse plus sur ce qui est déjà à sa cote, il remonte et saute ces zones.
### v0.641.0 — Gamme relief

- **Gamme relief** (Usinage 3D, onglet TypeArt) : sur le relief sélectionné, cochez les outils d’ébauche et une finition. Le plus gros outil ébauche, chaque suivant reprend seulement ce que le précédent a laissé, une surépaisseur reste pour la finition. Les parcours créés restent des parcours ordinaires, à régler un par un.
- **Correction :** un nouveau parcours Relief ou Finition 3D sur un relief prenait la profondeur du préréglage, 1 mm, et l’opération Relief écrasait alors tout le relief à cette hauteur. Il prend maintenant la hauteur du relief.
### v0.642.0 — Enrouler un relief sur un autre

- **Enrouler sur un relief** (TypeArt) : un relief posé sur un autre en gardant ses dimensions le long de la surface. Projection parallèle, enroulement sphérique, cylindrique autour de X ou de Y. Départ à un coin, au centre ou sur deux marqueurs. Répétition en X et en Y dans le galbe du support. Résultat ajouté, soustrait, ou seul.
### v0.643.0 — Scripts de forme

- **Script** (TypeEdit) : dessiner avec un script en VBScript. Les fonctions sont celles du manuel de TypeEdit : NewCurve, MoveTo, LineTo, ArcHTo, ArcTTo, ClosePath, InputScriptBox, ShowValue, DbApi, WndScriptApi, GetAppParameter, VbScriptInclude. La fenêtre liste vos scripts et ceux de TypeEdit s'il est installé (en lecture seule), et permet de les modifier, de les essayer et de lancer le dessin.
- Un script qui crée un objet à paramètres (CreatUnicReeditableObject) se rouvre d'un double-clic sur son dessin, avec ses valeurs, là où il a été déplacé.
- Un script ne peut ni lire ni écrire de fichier, ni lancer de programme, et une boucle sans fin s'arrête d'elle-même. Une erreur donne sa ligne et la sélectionne dans le texte.
- Les boîtes HTML ne sont pas ouvertes : le script tourne alors avec ses valeurs gardées, et la fenêtre le dit. Les fonctions qui agissent sur le document de TypeEdit sont refusées, avec leur nom.
### v0.644.0 — Boutons de script et ligne de commande

- **Script 1 à Script 10** : dix commandes qui lancent chacune un script choisi dans la fenêtre des scripts (Placer sur un bouton). Elles portent le nom du script, s'ajoutent au ruban par Personnaliser le ruban et acceptent un raccourci.
- **Ligne de commande** : `VectorDrive -SCRIPT fichier -SCPARAM a b c` ouvre une fenêtre et y lance le script, avec les mêmes options que TypeEdit. Le script est cherché tel quel, puis dans vos scripts, puis dans ceux de TypeEdit.
### v0.645.0 — Permuter les plans d'un volume

- **Permuter les plans** (Volumes) : X Y Z devient Z X Y à chaque clic, sur place, le dessous restant à sa hauteur. Trois clics rendent la pièce d'origine. Avec Maj, l'original reste et le résultat se pose à côté.
### v0.646.0 — Imbrication au plus juste

- **Imbriquer selon la vraie forme** : à la fin du rangement, chaque objet glisse vers le coin de départ jusqu'à l'écart demandé, mesuré sur la géométrie exacte. La grille laissait jusqu'à deux ou trois cases de jeu entre les objets ; ce jeu disparaît sans changer le rangement, ni passer sous l'écart.
### v0.647.0 — Réglages par lettre sur une courbe

- **Lettres** : le crénage, la hauteur, la largeur, la rotation et les décalages d'une lettre valent maintenant aussi pour un texte en arc, sur une courbe ou déformé sur un arc. Sur une courbe, le décalage en X suit la courbe et le décalage en Y s'en écarte.
### v0.648.0 — Plusieurs polices dans un texte

- **Lettres** : les lettres choisies peuvent avoir leur propre police, à la hauteur du texte, sur un texte droit, en arc ou sur une courbe. Choisir la police du texte retire ce réglage ; Remplacer la police change tout le texte, lettres comprises, sans toucher à leurs autres réglages.
### v0.649.0 — Éditeur de polices

- **Polices** : un éditeur de polices, sur le modèle de celui de TypeEdit. La sélection devient un caractère, posé sur la ligne de base ou à sa place depuis l'origine du dessin (pour un g, une virgule). Un caractère s'insère dans le dessin pour être repris, s'efface, change de chasse ; les paires de crénage se règlent, un texte d'essai montre le résultat. Une police se crée de zéro, s'ouvre, ou repart d'une police TrueType, OpenType ou SVG. Les traits ouverts restent ouverts : on peut dessiner une police monotrait. Le format écrit est le SVG, pas le VNF. Enregistrée, la police rejoint la liste et les textes du dessin qui s'en servent suivent.
- **Polices SVG** : un nom de police contenant une apostrophe ou une esperluette était mal lu dans la liste.
- **Disposition TypeEdit** : la commande Coût reste libre pour un plugin.
### v0.650.0 — Polycourbe

- **Dessin** : un outil Polycourbe, sur le modèle de TypeEdit : segments et arcs qui se suivent sans cassure. Tab passe des segments libres aux arcs tangents, puis aux segments tangents ; Retour arrière retire le dernier morceau ; Entrée ou un double-clic termine ; un clic sur le premier point ferme le contour ; Ctrl contraint à 45°.
- **Disposition TypeEdit** : la polycourbe, le Bézier, la ligne double, la mesure d'angle et la duplication libre répondent à leurs commandes.
### v0.651.0 — Espacements du texte

- **Texte** : deux modes de crénage de plus, sur le modèle de TypeEdit : serré avec crénage et serré, sans les espaces de part et d'autre des lettres. Un bouton passe au mode suivant.
- **Texte** : trois interlignes, fixe en mm, proportionnel et typographique en pourcentage ; les deux derniers suivent la hauteur du texte.
- **Texte** : la casse initiale remet le texte comme il était avant les changements de casse.
- **Disposition TypeEdit** : les boutons d'interligne étaient reliés aux modes de chasse, ils changeaient l'espacement des lettres. Ils règlent maintenant l'interligne.
### v0.652.0 — Texte de droite à gauche

- **Texte** : de droite à gauche, sur le modèle de TypeEdit. L'arabe prend ses quatre formes (isolée, initiale, médiane, finale) et la ligature lam-alef si la police les porte ; l'hébreu se pose à l'envers de la frappe ; chiffres et mots latins restent dans leur sens, parenthèses retournées. Le texte reste gardé dans l'ordre de la frappe. Il s'enregistre en courbes dans un VND.
### v0.653.0 — Parcellisation

- **FAO** : un travail plus grand que la plaque ou que la table s'usine en panneaux, sur le modèle de TypeEdit. Taille des panneaux, chevauchement, premier panneau et sens, zone couverte (ce qui est à usiner, ou la plaque), zéro de chaque programme ; les panneaux vides sont retirés, les autres se réordonnent ou se retirent à la main. Un programme par panneau, coupé à ses bords et rapporté à son zéro, avec un rapport : taille et origine de chaque panneau, déplacement de la plaque depuis le précédent, parcours et temps.
- **FAO** : sans chevauchement, un trait ou un trou posé exactement sur une frontière n'appartient qu'à un panneau : rien n'est usiné deux fois. À chaque coupure l'outil descend droit, à l'avance de plongée, et remonte en rapide à la hauteur la plus haute du parcours.
### v0.654.0 — Esquisse contrainte

- **Dessin** : une esquisse contrainte, d'après SolidCraft. Traits, rectangles, cercles et arcs, tenus par des contraintes (coïncident, horizontal, vertical, parallèle, perpendiculaire, dans l'axe, tangent, égal, concentrique, milieu, symétrique, fixe) et des cotes (longueur, distance, en X, en Y, rayon, diamètre, angle). Changez une cote, la figure se recalcule ; tirez un point, il suit tant que les contraintes le permettent.
- **Dessin** : ce qui reste libre est en bleu, et le nombre de degrés de liberté est affiché. Une contrainte qui en contredirait d'autres est refusée, et la fenêtre dit lesquelles. La géométrie de construction guide sans aller au tracé.
- **Dessin** : une esquisse peut partir des traits et des arcs sélectionnés. L'objet garde son esquisse dans le fichier natif : un double-clic la reprend.
### v0.655.0 — Historique des volumes

- **Design 3D** : Historique, d'après la frise des opérations de SolidCraft. Chaque commande de volumes note ses réglages et ce qu'elle a pris dans la sélection ; la fenêtre liste les étapes dans l'ordre. Reprenez un réglage : le volume se recalcule, à sa place, avec tout ce qui vient après. Un double-clic sur un volume ouvre son historique.
- **Design 3D** : le lien entre esquisse et volume. Une extrusion, ou toute autre commande, partie d'une esquisse contrainte la garde : changez une cote, le volume suit.
- **Design 3D** : une étape se suspend et se reprend. L'historique s'enregistre avec le fichier natif et revient avec Annuler. Un volume changé hors de ses commandes, ou importé, compte pour un volume figé : la suite garde son histoire à partir de là.
### v0.656.0 — Coins réglables

- **Dessin** : Coins réglables, d'après VectorCraft. Une poignée dans chaque angle des formes choisies : la tirer arrondit tous les coins de la forme, ou seulement ceux qu'on a choisis d'un clic (Ctrl pour en ajouter). Alt+clic passe de l'arrondi à l'arrondi inversé et au chanfrein, un double-clic demande le rayon, Suppr rend le coin vif.
- **Dessin** : les côtés peuvent être courbes, ils sont alors recoupés. Les arrondis sont de vrais arcs. Le rayon reste réglable après coup, avec les déplacements, rotations, miroirs et mises à l'échelle : la forme garde son tracé d'avant dans le fichier natif. Un étirement ou une retouche des points en fait une forme ordinaire.
### v0.657.0 — Liquéfier

- **Dessin** : Liquéfier, d'après VectorCraft. Un pinceau qui déforme les formes choisies, sinon toutes celles qu'il rencontre : Déformer pousse le contour dans le sens du geste, Tordre, Contracter et Dilater agissent tant qu'on tient le pinceau, Festonner, Cristalliser et Froisser ajoutent du relief au contour.
- **Dessin** : taille, angle et force du pinceau dans Réglages du pinceau, crochets `[` `]` pour changer de taille en cours de travail. Le pinceau n'ajoute des points que là où il passe : le reste d'un long trait reste un trait, un arc reste un arc. Échap abandonne le geste, et un passage s'annule d'un seul coup.
### v0.658.0 — HPGL lu en entier

- **Import** : les échelles du HPGL sont suivies (IP, SC, y compris isotrope et à facteur), ainsi que la rotation (RO). Une échelle sans fenêtre, dont la taille dépendait du papier du traceur, est signalée à l'ouverture.
- **Import** : les textes (LB) ne sont plus perdus : ils arrivent à leur place, à leur taille et dans leur largeur, en texte modifiable, avec direction, origine, pente et lignes (SI, SR, DI, DR, LO, SL, CP, ES, SD). Le dessin des lettres n'est pas celui du traceur, que le fichier ne porte pas : c'est signalé.
- **Import** : HP-GL/2 : polylignes codées (PE), courbes (BZ, BR), arcs par trois points (AT, RT), secteurs (EW, WG), polygones fermés (PM), et fichiers dans l'enveloppe PCL des pilotes, qui étaient refusés.
- **Import** : un arc et les traits qui le prolongent forment un seul contour, fermé s'il revient à son départ. Un fichier qui changeait le caractère de fin de texte (DT) ne perd plus tout ce qui suit le premier texte.
### v0.659.0 — Congés et chanfreins sur les arêtes choisies

- **Design 3D** : Congés et chanfreins, dans Modifier. Les arêtes se cliquent sur le volume, en 3D ; un second clic en retire une, et des boutons prennent toutes les arêtes, les saillantes ou les rentrantes. « Arrondir les arêtes » les traitait toutes d'un coup, et reste là pour ça.
- **Design 3D** : une arête rentrante reçoit de la matière, une saillante en perd. Le rayon peut varier d'un bout à l'autre de l'arête. Une arête arrêtée par une paroi laisse la paroi intacte, et trois congés de même rayon qui se rejoignent à un coin s'y raccordent par une portion de sphère.
- **Design 3D** : un rayon trop grand pour les faces de l'arête est refusé, avec le rayon qui tient ; la fenêtre reste ouverte et les arêtes choisies ne sont pas perdues. L'opération entre dans l'historique du volume : son rayon et ses arêtes restent modifiables.
### v0.660.0 — Dépouille d’un volume déjà fait

- **Design 3D** : Dépouille, dans Modifier. Les faces se cliquent sur le volume, en 3D, et un bouton prend toutes les parois. On règle l'angle, le sens de démoulage (Z, Y ou X, dans un sens ou l'autre) et le plan neutre, la hauteur où les faces ne bougent pas. L'analyse de dépouille disait déjà ce qui ne se démoulait pas, sans pouvoir le corriger.
- **Design 3D** : une paroi plate reste plate, un cylindre devient un cône, et le bord d'une poche s'évase vers l'ouverture. Les faces voisines restent dans leur plan. Un angle négatif donne une contre-dépouille.
- **Design 3D** : un angle qui ferait se croiser des faces est refusé, la fenêtre reste ouverte et les faces choisies ne sont pas perdues. L'opération entre dans l'historique du volume : son angle et ses faces restent modifiables.
### v0.661.0 — Déplacer des faces d’un volume déjà fait

- **Design 3D** : Déplacer des faces, dans Modifier. On clique les faces sur le volume, puis on les fait avancer le long de leur normale : un trou se resserre ou s'ouvre, une poche devient moins profonde, une paroi s'éloigne, un bossage grandit, sans refaire la pièce.
- **Design 3D** : par un vecteur, les faces se déplacent en bloc : un perçage ou un bossage change de place sur sa plaque. Les faces voisines restent dans leur plan, elles s'allongent ou raccourcissent, et le dessus de la plaque se redécoupe autour du perçage.
- **Design 3D** : un déplacement qui ferait se croiser ou se toucher des faces est refusé, la fenêtre reste ouverte et les faces choisies ne sont pas perdues. L'opération entre dans l'historique du volume : sa distance et ses faces restent modifiables.
### v0.662.0 — Supprimer des faces d’un volume déjà fait

- **Design 3D** : Supprimer des faces, dans Modifier. On clique les faces sur le volume : un perçage se bouche, une poche, un bossage, une rainure, une entaille de coin ou un chanfrein s'efface, et les plans autour se prolongent sur la place laissée. De quoi simplifier une pièce reçue avant de l'usiner.
- **Design 3D** : ce qui ne peut pas se refermer est refusé et dit pourquoi : une paroi extérieure, une voisine courbe, un plot resté au fond d'une entaille. La fenêtre reste ouverte et les faces choisies ne sont pas perdues. L'opération entre dans l'historique du volume.
### v0.663.0 — Lettres à la souris

- **Texte** : Lettres à la souris. Un clic sur une lettre du texte la choisit (Ctrl pour en ajouter ou en retirer), et on la décale en la glissant sur le dessin, même si le texte est tourné, penché ou étiré. Les autres lettres ne bougent pas.
- **Texte** : au clavier, les flèches la décalent (cinq fois plus avec Maj), Alt+flèches règle le crénage et pousse ce qui suit, + et − sa taille, Page préc. et Page suiv. sa rotation, Suppr la remet à la normale. Un double-clic ouvre la fenêtre Lettres sur elle : ce sont les mêmes réglages.
### v0.664.0 — Texte autour des formes

- **Texte** : Dans une forme sait contourner. Sélectionnez la forme et d'autres formes fermées, plus petites : le texte coule dans la plus grande, à la distance voulue des autres, qui peuvent être dedans, déborder de son bord ou la couper en deux. Elles restent sur le dessin.
### v0.665.0 — IGES : plans, surfaces réglées, de révolution et cylindres tabulés

- **Import IGES** : les surfaces planes (108), réglées (118), de révolution (120) et les cylindres tabulés (122) sont lues, entières, détourées ou faces de solide. Elles étaient seulement signalées au compte rendu : une pièce faite de ces surfaces arrivait vide. Elles donnent maintenant les calques de hauteur et la silhouette, comme les surfaces NURBS.
### v0.666.0 — Filtre des calques

- **Calques** : un champ en tête du panneau ne montre que les calques dont le nom ou l'outil contient le texte, sans tenir compte des majuscules ni des accents. Entrée active le premier. Pratique sur un dessin de plusieurs centaines de plans. Le dessin ne change pas : les calques écartés restent visibles et usinés.
### v0.667.0 — Restant de plaque

- **Restant de plaque** (Métiers, Duplication) : la partie de la plaque que les objets laissent libre devient une forme, sur son propre plan. Trois façons : le plus grand rectangle libre, autour des rectangles des objets, ou autour de leur vraie forme. Un écart autour des objets, une surface et une largeur minimales : les fentes entre deux pièces ne comptent pas. La forme reste sélectionnée : Copier dans une forme y range aussitôt d'autres objets. Elle peut aussi être gardée dans la bibliothèque, dans Restants de plaque.
### v0.668.0 — Optimiseur d'imbrication

- **Imbriquer** et **Copie imbriquée** : un optimiseur essaie plusieurs rangements, dans plusieurs ordres et, si vous le demandez, dans les deux directions, puis garde le meilleur : d'abord ce qui tient, puis le moins de plaques, puis le moins de place prise sur la dernière. Nombre d'essais, durée maximale, arrêt à un gain de remplissage. La barre d'état dit combien d'essais ont été faits et la direction retenue. Avec 1 essai, sans les deux directions, rien ne change.
### v0.669.0 — Rapport d'imbrication

- **Rapport d'imbrication** (Métiers, Duplication) : un PDF avec les réglages de la dernière imbrication, puis une page par plan rempli : plaque, nombre de pièces, surface des pièces, surface et dimensions de découpe, remplissage, et le dessin du plan. Commentaires et image en option. Les réglages restent dans le dessin : le rapport peut se faire plus tard, après réouverture.
### v0.670.0 — Imbrication : miroir et contour englobant

- **Imbriquer** et **Copie imbriquée** : nouveau réglage **Retournement permis (miroir)**, selon la forme des objets. Un objet symétrique ne change rien ; un objet qui ne l'est pas gagne les poses retournées. Le rapport d'imbrication le mentionne.
- **Imbriquer dans un contour** (Métiers, Duplication) : sélectionnez d'abord le contour fermé, puis les objets. Ils s'y rangent en se déplaçant, sans copie. Les trous du contour restent libres. Dans un groupe ou une combinaison, le contour suivant ne sert que lorsque le précédent est plein. Ce qui ne tient nulle part reste où il était.
- **Copier dans une forme** : le retournement est aussi proposé.
### v0.671.0 — Multicopie complète

- **Multicopie** devient un assistant avec aperçu numéroté, qui se met à jour à chaque réglage :
  - **Quantité** : nombre total, original compris, ou nombre de plans. Ce qui ne tient pas sur la plaque passe sur de nouveaux plans.
  - **Variables** : un exemplaire par ligne du tableau, ou des exemplaires vides au-delà si l'on enlève la limite.
  - **Position** : départ de la duplication (les quatre coins), position du bloc sur la plaque (neuf places), ou premier exemplaire à la place de la sélection.
  - **Optimisé** : rangées en aller-retour, pour moins de déplacements ; les rangées du retour peuvent être tournées d'un demi-tour.
  - **Lignes de découpe**, dans la couleur choisie : découpe totale (bords des cellules) ou partielle (traits aux croisements). Une cellule vide n'a pas de ligne.
  - **Ignorer le premier objet** : il donne la taille de la cellule sans être copié. **Conserver la sélection** : les exemplaires vont sur de nouveaux plans.
  - Sans sélection, tous les objets visibles et non verrouillés du plan actif sont pris.
### v0.672.0 — Découper la matière restante, liste d'angles

- **Découper la matière restante** (Métiers, Duplication) : une grille de lignes sur ce qui reste de la plaque, espacement réglable en X et en Y, dans la couleur choisie. Les lignes s'arrêtent à l'écart demandé autour des objets et au bord de la plaque.
- **Imbrication selon la forme** : on peut donner la liste des angles permis (par exemple `0;90;180`), à la place d'un pas de rotation.
### v0.673.0 — Outil largeur

- **Outil largeur** (Dessin) : sur un trait, un clic pose un point de largeur et le glisser règle cette largeur, avec l'aperçu en direct. Alt règle un seul côté, Ctrl déplace le point le long du trait, Suppr le retire. Entrée ou un double-clic valide : le trait devient une bande pleine, annulable d'un coup.
- **Largeur variable** : cinq profils de plus (pointe au départ, pointe à l'arrivée, pincé au milieu, goutte, vague).
- Une bande ne perd plus de morceau quand un virage est plus serré que la largeur, ou quand le trait se croise.
### v0.674.0 — Plume calligraphique

- **Plume calligraphique** (Dessin) : les traits choisis deviennent ce que tracerait une plume qui ne tourne pas : pleins en travers de la plume, déliés dans son sens. Largeur, angle et épaisseur de la plume réglables, de la plume plate à la plume ronde. Le résultat est une forme pleine, avec ses trous.
### v0.675.0 — Import de variables complet

- **Variables, Importer** : une fenêtre règle l'extraction, avec l'aperçu de ce qu'elle donne : ligne de départ, première ligne pour les noms, séparateur de colonnes et de lignes, ou colonnes de largeur constante, et regroupement des lignes identiques qui se suivent.
- **Correction** : un fichier Unicode, comme l'écrit le Bloc-notes, sortait illisible. Il est maintenant lu correctement, avec ou sans marque de début. Un fichier contenant un octet illisible pouvait aussi faire échouer l'import : ce n'est plus le cas.
- Un séparateur d'un seul caractère respecte les guillemets, comme à la sortie d'un tableur.
### v0.676.0 — Rechercher / remplacer complet

- **Rechercher / remplacer** : en plus du texte, la fenêtre change une taille pour une autre ou toutes les tailles, une police pour une autre ou toutes les polices, et donne à tous les textes la même compression.
- Le tout s'applique à la sélection, au plan actif ou à tous les plans, et s'annule d'un seul coup. Les listes proposent ce qui se trouve réellement dans cette portée.
- Les polices posées sur quelques lettres suivent le remplacement.
### v0.677.0 — Alignement : marges, objet par objet, premier sélectionné

- **Aligner contre la plaque** : chaque objet va contre la marge, le bord s'il n'y a pas de marge, au lieu de déplacer la sélection d'un bloc. Pour garder un ensemble, le grouper d'abord. Une variable s'aligne sur sa ligne de base.
- **Même largeur, hauteur, taille** : la référence est l'objet sélectionné en premier, comme les alignements.
- **Mode Point, Aligner** : la valeur vient du premier point cliqué, et Ctrl ajoute des points à la sélection comme Maj.
- **Commandes Espacement de TypeEdit** : elles répartissent entre les objets extrêmes, sans fenêtre. L'écart imposé reste dans Espacer H et V.
- **Correction** : un alignement perdait l'ordre de la sélection, donc la référence de l'alignement suivant.
### v0.678.0 — Maj garde l'original, Raccorder avec liaison

- **Maj sur une commande** : la commande s'applique à une copie, l'original reste en place : alignements, combiner, décomposer, poinçonner, congés, chanfreins, approximation, commandes du Mode Point et d'autres. Un seul Ctrl+Z revient à l'état de départ. Si la commande ne fait rien, ou si sa fenêtre est annulée, aucune copie ne reste.
- **Raccorder** : à la distance de fusion s'ajoute la distance de liaison, entre les deux, un segment relie les points sans bouger la forme. L'option Séparément ferme chaque contour sur lui-même.
- **Raccorder** reprend ses derniers réglages sans fenêtre. Ctrl+clic ouvre la fenêtre, le premier usage aussi.
- **Correction** : un contour dont l'autre bout est plus près qu'un contour voisin se ferme au lieu de partir vers ce voisin.
### v0.679.0 — Texte en arc complet

- **Texte en arc** s'applique au texte sélectionné, et plus seulement à un nouveau texte. Le double-clic rouvre les réglages de l'arc.
- **Distance cordale** : l'arc se déduit de sa flèche et de la longueur du texte, qui reste à sa place.
- **Angles de départ et d'arrivée** (Ctrl+clic) : avec le centre et le rayon, le texte remplit l'arc entre les deux angles, en sens horaire.
- **Directions** : à droite, à gauche et en bas renversé s'ajoutent au haut et au bas lisible. Le texte se pose sur la ligne de base ou dessous.
### v0.680.0 — Texte dans un rectangle à la souris

- **Texte dans un cadre** : sans forme sélectionnée, on glisse le rectangle à la souris. **F2** donne sa largeur, sa hauteur, un de ses 9 points et les coordonnées de ce point.
- **Comprimer les lettres** devient le réglage proposé : le texte garde la hauteur du cadre et se comprime si la largeur manque. Réduire et Étirer restent au choix.
- Le texte se centre aussi en hauteur dans le cadre.
- **Tab** pose un ressort, qui se répartit sur la largeur du cadre.
### v0.681.0 — Texte en rangées et colonnes

- **Rangées et colonnes** : une nouvelle fenêtre pose du texte en tableau, par sa première ligne de base (point à gauche, au milieu ou à droite) ou par le tableau lui-même (un de ses 9 points, largeur et hauteur totales).
- Chaque colonne a sa largeur, son alignement, sa marge gauche, sa largeur de texte et sa marge inférieure, ou toutes suivent la première.
- **Bordures** : tout, cadre, lignes horizontales, lignes verticales ou aucune, dans une couleur à part.
- Le contenu se saisit dans une grille, et **Ctrl+V** colle un tableau copié, qui agrandit la grille au besoin. Un texte trop long se comprime pour tenir dans sa cellule.
- Le texte sélectionné remplit la première colonne. Le **double-clic** rouvre la fenêtre sans perdre le texte, même après un déplacement.
- La commande Texte en colonnes de TypeEdit mène ici ; **En colonnes**, qui répartit les lignes d'un texte, reste à sa place.
### v0.682.0 — Courbes symétriques

- Quatre nouveaux outils dans l'onglet CAO : **Courbe symétrique (axe OX)**, **(axe OY)**, **Courbe cyclique** (les deux axes) et **Courbe symétrique (origine)**.
- On dessine une partie : la courbe se complète en un seul contour, lisse, retouchable en Mode Point. Un point cliqué sur un axe ou tout près s'y pose.
- **Fermée par défaut**, **F** l'ouvre ou la ferme pendant le tracé. **Ctrl** maintenue en déplaçant pose un point d'angle, **Maj** un point tangent. Double-clic ou Entrée pour finir, Retour arrière retire le dernier point.
- Les commandes correspondantes de TypeEdit mènent à ces outils. **Dessin symétrique**, **Symétrie cyclique** et **Symétrie centrale** restent pour dessiner librement avec les autres outils.
### v0.683.0 — Ligne double complète

- **Type de coins** : aigu, chanfreiné ou arrondi, sur les lignes ouvertes comme sur les lignes refermées.
- **Espacement de chaque côté de l'axe** : à la place de l'écartement et du calage, chaque trait a sa distance à l'axe cliqué. Une distance nulle pose un trait sur l'axe. Les anciens réglages se reprennent.
- **Départ et fin de ligne** : ouvert, plat ou arrondi, aussi avec deux espacements différents.
- Les bouts et les coins arrondis sont plus fins : 32 points par quart de tour au lieu de 8.
- L'outil reprend les derniers réglages, gardés d'une séance à l'autre. La fenêtre s'ouvre à la première utilisation et par **Ctrl+clic** sur l'outil.
### v0.684.0 — Étendre en arc : le point à atteindre se choisit

- **Étendre en arc** se fait en deux clics : le bout de l'arc, puis le point à atteindre. Tous les points que le cercle rencontre sont marqués, et l'aperçu suit le plus proche du pointeur : le premier, le deuxième ou un suivant.
- Les arcs des fichiers importés, en courbes de Bézier, sont reconnus.
- Un arc fait de plusieurs morceaux du même cercle ne s'arrête plus sur lui-même.
- Un contour qui n'est pas un arc donne un message clair.
- La commande Étendre en arc de TypeEdit mène à cet outil et non plus à Prolonger.
### v0.685.0 — Texte sur courbe : poser l'existant, déplacer à la souris

- **Sur courbe** pose le texte sélectionné sur la courbe sélectionnée, dans son alignement. La courbe disparaît, **Maj** la garde. Une courbe seule ouvre toujours la fenêtre d'un nouveau texte.
- **Déplacer sur la courbe** se fait à la souris : le texte suit le pointeur le long de sa courbe, un clic le pose. **F2** donne la position en chiffres, depuis le départ de la courbe ou depuis la position actuelle, dans une seule fenêtre.
- Sur une courbe fermée, le texte passe le point de départ sans s'y entasser.
### v0.686.0 — La flèche à la souris

- **Flèche** demande son type, standard, orthogonale ou filaire, puis se dessine en quatre clics : la base de la queue, la pointe, la taille de la pointe, l'épaisseur de la queue et la forme de la pointe. La filaire s'arrête au troisième clic.
- **Ctrl** cale la pointe à 45°, **Retour arrière** revient au clic précédent.
- **F2** pendant le tracé ou **Ctrl+clic** sur le bouton ouvrent les dimensions en chiffres.
- La flèche reste éditable par double-clic, et le type choisi est proposé la fois suivante.
### v0.687.0 — Décaler sans rien perdre, dictionnaire, compression globale

- **Décaler** : une forme qu'on ne peut pas décaler, décalage intérieur trop grand par exemple, ne disparaît plus. Si rien n'est créé, un message le dit et le dessin ne change pas. Si une partie seulement échoue, ces formes restent et la barre d'état les compte.
- **Seulement le plus éloigné** : avec plusieurs décalages, ne garde que le dernier.
- **Orthographe** : le bouton **Ajouter** met le mot dans un dictionnaire propre à VectorDrive. Il n'est plus signalé, ni ici ni les fois suivantes.
- **Compression globale** : un pourcentage de la longueur de la plus longue ligne, toutes les lignes resserrées du même facteur.
### v0.688.0 — F2 pendant le geste

- **Pendant un tracé** (polyligne, courbe par points, plume, ligne double, courbes symétriques), **F2** ouvre la liste des points : on corrige, on ajoute, on retire, et **Terminer le tracé** pose la forme.
- **En tirant un repère depuis une règle**, F2 sans relâcher le bouton donne sa position en chiffres.
- **En déplaçant un objet**, F2 sans relâcher le bouton donne la position du point saisi : on amène un point précis de l'objet à des coordonnées précises. Maj en fait une copie.
- **En tournant ou en redimensionnant à la souris**, F2 donne l'angle, ou la largeur et la hauteur en %, depuis la poignée opposée.
### v0.689.0 — Textes sur arcs multiples : réglages commun par commun

- **Quatre cases** : Même rayon, Angle de départ identique, Même direction, Même type. Chacune impose la valeur de la première ligne aux suivantes, sans toucher au reste.
- **Réouverture** : un texte déjà posé sur un arc revient avec son rayon, son angle, son sens, sa déformation et le centre commun.
- **Aperçu** : les réglages se voient sur le dessin avant de valider. Annuler remet tout comme avant, sans rien ajouter à l'historique.
- **Corrigé** : un cercle sélectionné avec les textes sert maintenant de centre. La fenêtre ne le voyait jamais.
### v0.690.0 — Le centre de rotation se déplace

- **Centre de rotation** : en mode rotation (second clic sur la sélection), le centre se déplace à la souris et s'accroche aux points avec F3. Il reste à sa place tant que la sélection ne change pas, pour plusieurs rotations de suite. **Maj+clic** le remet au milieu.
- **F2** : pendant qu'on déplace le centre, sa position. En mode rotation, l'angle et le centre.
- **Garder l'original** : **Maj** en tournant, **Alt** en tournant ou en redimensionnant, à la souris.
- **Échelle** : un centre déplacé sert aussi de point fixe pour le redimensionnement.
### v0.691.0 — Arc 3 points fidèle à l'aperçu, F2 sur les arcs et les cercles

- **Corrigé — Arc 3 points** : l'aperçu montrait un arc et le clic en posait un autre, sur le même cercle. Le dessin suit maintenant l'aperçu : départ, passage, arrivée.
- **Maj sur le troisième clic** : départ, arrivée, puis la courbure.
- **F2** pendant Arc 3 points, Cercle 3 points, Cercle 2 points, Ligne de coupure et Polygone par côté : les coordonnées des points. Le dernier point attendu pose la forme.
- **F2 sur Arc centre, départ, fin** : le centre, le rayon, les deux angles et le sens. Les valeurs sont gardées pour la fois suivante.
- **Outil Bézier** : Retour arrière reprend à l'avant-dernier point, plusieurs fois de suite.
### v0.692.0 — Geler devient étanche

- **Corrigé** : un objet gelé pouvait être pris au rectangle ou par Inverser, puis déplacé ou supprimé. Il n'entre plus dans la sélection, d'où que vienne la demande.
- **Corrigé** : Inverser la sélection prenait aussi les objets masqués, qu'on pouvait alors supprimer sans les voir.
- **Dégeler un seul objet** : un clic désigne un objet gelé. Il s'affiche en magenta, sans poignées, et rien ne le modifie. Le bouton **Geler** le dégèle. Ctrl+clic en désigne plusieurs.
- Un glisser qui part d'un objet gelé trace un rectangle de sélection et ne déplace rien.
### v0.693.0 — Rogner, Poinçonner, Ajuster : le cadre d'abord

- **Ordre de sélection** : le cadre se sélectionne maintenant **en premier**, comme dans TypeEdit, pour Rogner, Poinçonner et Ajuster dans le cadre. Si le premier objet n'est pas fermé, le dernier sert de cadre, comme avant.
- **Changement à connaître** : avec deux objets fermés sélectionnés, c'est le premier qui coupe. Une ancienne habitude « le cadre en dernier » donne donc l'inverse. Annuler rétablit tout.
- **Ctrl sur Rogner ou Poinçonner** : le type standard, supprimer les éléments qui touchent le cadre, ou les garder entiers ; et garder le cadre ou non.
- **Groupe** : un groupe de contours fermés peut servir de cadre.
- **Corrigé** : avec plusieurs objets sélectionnés et aucun fermé, Rogner coupait à la plaque sans le dire. La barre d'état l'indique.
### v0.694.0 — Modeler un contour à deux clics

- **Couper-supprimer** : deux clics sur un contour, n'importe où et pas seulement sur des nœuds ; la portion entre eux part. Sur un contour fermé, c'est le sens horaire du premier au second, et Tab prend l'autre portion. Un cercle rouge marque chaque point, la portion visée s'affiche en rouge avant de valider.
- **Transformer en segment, en arc, en courbe, en angle** : deux clics, puis la souris règle la forme et un dernier clic valide (le segment n'a pas ce dernier temps). L'arc passe par le point cliqué, la courbe y a son milieu, l'angle y a son sommet. Le reste du contour ne bouge pas.
- **Effacer un contour** : un clic retire ce contour, sans décombiner l'objet.
- **Déconnecter** : accepte plusieurs points à la fois, le contour s'ouvre à chacun.
- **Maj** sur le dernier clic garde l'original, Retour arrière revient d'un pas. Les outils restent actifs pour le contour suivant.
- Les commandes TypeEdit Effacer un contour, Couper-supprimer et Transformer en segment, arc, courbe et angle mènent maintenant à ces outils. Les commandes de Mode Point sur deux points sélectionnés restent disponibles.
### v0.695.0 — Couper un contour comme TypeEdit

- **Couper un contour** (l'ancien Couteau au trait) : le trait coupe maintenant les contours **ouverts ou fermés** à chaque intersection, sans rien déplacer ; les morceaux restent dans le même objet, comme le fait TypeEdit. Les points de découpe s'affichent en doubles carrés pendant le geste.
- **Tab ou Maj** : les contours fermés sont refermés le long du trait, comme le faisait toujours l'ancien outil. **Changement à connaître** : sans Tab ni Maj, l'outil ne referme plus.
- **Les courbes restent des courbes** : couper un cercle en deux donne 3 segments par morceau au lieu de 257, ce qui allège d'autant l'usinage. Vaut aussi pour la commande Couteau, avec un trait courbe ou le bord d'un cercle. Si la coupe est trop tordue pour ce calcul (contours qui se croisent), l'ancien résultat aplati à 2 µm reste en secours.
- **Corrigé** : Couteau perdait sans le dire les traits ouverts d'un objet qui contenait aussi des contours fermés, et ne coupait pas les objets à l'intérieur d'un groupe tout en annonçant des morceaux.
### v0.696.0 — Contour du trait complet

- **Contour du trait** (les Couteaux de TypeEdit) : du filaire devient un contour fermé. Le **rayon** remplace l'épaisseur, comme dans TypeEdit : c'est la moitié de l'épaisseur.
- **Coins** aigus, chanfreinés ou arrondis, **début et fin** plats ou arrondis. Avec tout en arrondi, les courbes restent de vrais arcs ; sinon elles sont suivies à 2 µm près.
- **Conserver les courbes d'origine**.
- **Créer une enveloppe** pour préparer une gravure ou un balayage : rectangulaire, circulaire, convexe ou concave, avec une marge. La concave colle au dessin et économise la matière et le temps d'usinage.
- La commande Couteaux de TypeEdit mène maintenant ici et non plus à Couteau.
### v0.697.0 — Duplication à la souris

- **Duplication linéaire** : le nombre de colonnes et de rangées, puis glisser ; les copies suivent en pointillés, relâcher les pose. Le geste donne le pas entre deux copies ; **Tab** envoie la dernière copie au pointeur ; Ctrl : à 45°.
- **Duplication circulaire** : le nombre d'exemplaires et la rotation, puis glisser jusqu'au centre du cercle, avec l'accrochage F3 pour viser exactement le centre d'un cercle déjà tracé.
- **F2** pendant ces outils : les chiffres. En linéaire, colonnes, rangées, Delta et Offset ; en circulaire, exemplaires, angle total, centre et rotation.
- **Duplication libre** : glisser fait suivre le point saisi plutôt que le centre, et F2 sans relâcher donne sa position en chiffres. Ctrl, ou Ctrl en lançant l'outil : seulement à l'horizontale ou à la verticale.
- La fenêtre Dupliquer reste disponible. Les commandes de réseau de TypeEdit mènent maintenant à ces outils.
### v0.698.0 — Alt+clic sur une poignée

- **Corrigé** : depuis la 0.690, Alt+clic sur une poignée ne faisait plus défiler les objets superposés. Sans geste, Alt+clic les fait défiler de nouveau ; avec un geste, Alt garde l'original.
### v0.699.0 — Plusieurs points d'accrochage au même endroit

- **Alt** pendant un tracé : quand plusieurs points d'accrochage tombent sous le pointeur, passe au suivant ; la barre d'état indique lequel et combien il y en a. Sans bouger la souris, le choix reste.
### v0.700.0 — Convertir des courbes, classement, contours ouverts

- **Convertir des courbes** : chaque contour devient le cercle, l'ellipse ou le rectangle le plus proche. Un vrai cercle, une vraie ellipse ou un vrai rectangle se retrouvent exactement. Maj garde l'original. La commande de TypeEdit mène ici.
- **Classement depuis un coin** : sans sélection, la commande de classement attend le rectangle de sélection et son premier point donne le coin de départ.
- **Inverser l’ordre** vaut aussi pour les contours d'un objet combiné, ce qui change leur ordre d'usinage.
- **Ctrl sur la recherche d'intersections** : marque les extrémités des contours ouverts.
### v0.701.0 — Duplication sur courbe complète, Interpoler

- **Duplication sur courbe** : la courbe peut être formée de plusieurs courbes combinées ; avant, seule la première servait, sans le dire.
- **En gardant leur écart à la courbe** : les objets suivent la courbe à la même distance d'elle ; un marqueur parmi eux donne le point qui suit la courbe.
- **Par déformation du premier objet au second** : les exemplaires passent progressivement d'une forme à l'autre le long de la courbe.
- **Interpoler entre deux objets** : les formes de passage entre deux formes sélectionnées, à leurs places. Les droites restent des droites et les courbes de vraies courbes quand les deux formes ont la même suite de segments.
### v0.702.0 — Enveloppes rétablies

- **Corrigé avant publication** : la préparation de la 0.696 remplaçait par erreur le module des enveloppes de déformation (arc, arche, vague, Courber le long d'un tracé) par celui du contour du trait. Aucune version publiée n'a été touchée. Les deux ont maintenant chacun leur module.
### v0.703.0 — Détourage : ce qui tient la pièce, ce qui manque au programme

- **Corrigé : la finition coupait les pontets.** Avec une surépaisseur et une passe de finition, celle-ci passait à pleine profondeur à travers les pontets : la pièce n'était plus tenue. La finition lève maintenant l'outil en face des pontets de l'ébauche.
- **Corrigé : les pontets disparaissaient sans le dire** avec une entrée et une sortie tangentes, et en détourage intérieur, alors que le formulaire les proposait. Ils sont maintenant usinés dans tous ces cas. Avec une matière restante, ils restent ignorés, et un message le dit.
- **Corrigé : l'angle de rampe était dépassé** sur un contour fermé court. L'outil fait maintenant autant de tours qu'il faut pour le tenir. **Le temps d'usinage de ces petits contours augmente.**
- **Corrigé : le tri manuel ne valait pas pour tout le dessin.** Pièces et trous suivent maintenant l'ordre du dessin en détourage et en poche, les trous restant avant le tour de leur pièce.
- **Nouveau message** : un contour ou une zone trop étroits pour l'outil, un trou trop petit ou un col infranchissable sont signalés, comme dans TypeEdit, quand le nombre de trajectoires diffère du nombre de contours. Ils disparaissaient sans message, sauf si tout le dessin était concerné.
- **Contours intérieurs** : élément par élément, ou tous les intérieurs puis tous les extérieurs, en détourage et en découpe laser.
### v0.704.0 — Commande Ouvrir rétablie

- **Corrigé avant publication** : la préparation de la 0.700 faisait marquer les contours ouverts à la commande Ouvrir, au lieu d'ouvrir les contours fermés. Aucune version publiée n'a été touchée.
### v0.705.0 — Reprise d'usinage

- **Reprise d'usinage** (clic droit sur une opération) : n'usiner qu'une partie d'un parcours, après une casse d'outil ou un arrêt par exemple. La table donne chaque point du parcours, avec ses entrées dans la matière et ses changements de direction ; on choisit le point de reprise et le dernier point usiné. L'outil arrive au-dessus du point de reprise et y descend en plongée.
- **Sûreté** : la reprise vaut pour le parcours au moment de son choix. S'il a changé depuis (outil, profondeur, dessin), elle est ignorée, un message le dit et le parcours est usiné en entier. Une opération en reprise porte la mention « (reprise) » dans la liste.
- Le reste du calcul (liaisons basses, gamme d'outils) continue de compter le parcours complet.
- Les libellés de l'ordre des contours intérieurs (0.703) sont traduits en anglais.
### v0.706.0 — Pontets : le défaut de la pente, pointillés et micro-attaches, balayage par zone

- **Corrigé, à lire si vous usinez des pontets droits : le pontet montait en pente depuis le sommet précédent.** Le contour ne restait pas à pleine profondeur jusqu'au pontet. Sur un rectangle de 100 × 50, outil de 6 mm, profondeur 10 et 2 pontets, **200 mm du contour n'étaient pas à pleine profondeur au lieu de 20 mm**. La pièce pouvait rester tenue par bien plus de matière que prévu. Ce défaut existe dans toutes les versions publiées depuis longtemps. Le pontet droit monte et redescend maintenant sur place.
- **Type de pontets** : ponts (une hauteur reste), pointillés (parties non usinées, les micro-attaches) ou nettoyer les ponts. Le laser utilise toujours les pointillés.
- **Pontets au plus, par contour**, en détourage, gravure, découpe laser et poche.
- **Balayage par zone** : en évidage par balayage, finir une zone avant de passer à la suivante, au lieu de sauter d'un îlot à l'autre.
- Les pontets valent aussi en gravure, et en aller simple et dernier aller-retour.
### v0.707.0 — Mode Point, Ctrl et Maj sur quelques commandes

- **Ajouter un point** en Mode Point : un clic sur le contour pose un point rouge, puis le bouton ou la touche **+** l'ajoute. La touche **-** supprime les points sélectionnés.
- **Simplifier** : moins de points, à la précision retenue. En Mode Point, l'objet en cours ; sinon la sélection. **Ctrl ou Maj** demande la précision.
- **Ctrl sur Combiner** : grouper. **Ctrl sur Décombiner** : dégrouper.
- **Maj sur le rectangle de sélection** : aussi les objets dont la boîte englobante le touche.
### v0.708.0 — Touches du manuel sur les transformations

**Changements de comportement, pour suivre TypeEdit :**

- **Poignées d'échelle : Maj garde l'original** (elle redimensionnait depuis le centre). **Tab enfoncée : depuis le centre.** **Ctrl : par pas de 100 %, depuis le centre** (1, 2, 3 fois, ou 1/2, 1/3). Un coin sans proportions passe de Ctrl à **Ctrl+Alt**. Alt garde toujours l'original.
- **Miroir sur axe : les objets se retournent**, et Ctrl ou Maj garde les originaux (il faisait toujours des copies). L'axe peut aussi être **deux marqueurs**.
- **Polygone : Maj prend deux points opposés.** Le polygone circonscrit passe de Maj à **Alt**. Étoile : Maj prend deux points opposés sur le cercle.
- **Gomme à boucles : les derniers réglages, sans fenêtre.** Ctrl ou le premier usage ouvre la fenêtre.

**Nouveau :**

- **Miroirs** : Maj garde l'original ; Ctrl met l'axe sur le côté droit ou à la base. Ctrl+Maj fait les deux.
- **Booléens et Décaler** : Ctrl ou Maj garde les originaux. **Rogner, quarts de tour** : Maj garde l'original.
- **Rectangle** : Maj part du centre. **Ellipse** : Maj la centre sur le premier point.
- **Marqueur** : Ctrl ou Maj choisit d'abord son aspect.
- **Maj+Page précédente : arrière-plan ; Maj+Page suivante : premier plan ; Ctrl+Maj+O : ouvrir.**
### v0.709.0 — 2D et 3D par un seul bouton, bouton Animation, un import garde sa 3D

- **Un seul bouton pour passer de la 2D à la 3D et revenir.** Il reste visible dans la rangée des onglets, quel que soit l'onglet choisi, et montre où il mène. Les boutons 2D, 3D et « Retour en 2D » disparaissent. Ctrl+1 et Ctrl+6 restent.
- **Bouton Animation**, dans l'onglet Vue et sur la vue 3D : il passe en 3D, ouvre la fenêtre des mécanismes et lance le mouvement des corps de la pièce quand un mouvement est repéré. Il était jusqu'ici dans le menu Corps.
- **Corrigé : un fichier 3D importé dans un dessin perdait sa 3D.** STEP, IGES, STL ou 3D XML importé ou glissé dans un dessin : seule sa vue de dessus était gardée, et la vue 3D n'en montrait rien. Le dessin le retient maintenant comme sa pièce 3D, comme s'il avait été ouvert : vue 3D, FAO 3D, Placer la pièce 3D, et après enregistrement. Annuler l'import l'enlève.
- **Limite** : un dessin n'a qu'une pièce 3D. S'il en a déjà une, il la garde, le fichier suivant n'est importé qu'en vue de dessus, et un message le dit.
### v0.710.0 — Surépaisseur en Gravure 3D, Finition et Intaille

- **Surépaisseur** dans le formulaire de la gravure à l'outil conique : elle laisse la matière le long des bords, pour une passe de finition ensuite. Le champ existait mais la gravure l'ignorait.
- En Gravure 3D et Finition, le tracé s'écarte des bords de la valeur demandée, la profondeur ne change pas. En Intaille, la pointe reste sur l'axe et la profondeur diminue. Une surépaisseur trop grande pour les formes est signalée.
### v0.711.0 — Le point de départ commande le départ de l'usinage

- **Point de départ** (Mode Point) : l'usinage commence maintenant au point choisi, en tracé, détourage, finition, laser et découpe laser. La commande changeait le dessin, mais le calcul repartait du point le plus proche.
- **Départ des contours fermés**, dans le formulaire : au plus près (par défaut) ou au point de départ du dessin, pour tous les contours.
- L'entrée et la sortie tangentes partent de ce point quand il a été choisi ; sinon, du milieu du plus long côté, comme avant.
### v0.712.0 — Entrée et sortie : linéaire, goutte et contrôle de perçage

- **Forme de l'entrée et de la sortie** : circulaire (le quart de cercle), linéaire avec son angle d'entrée et son angle de sortie, ou perçage en goutte.
- **Perçage en goutte** : le perçage est à la distance demandée du contour. Plus loin que le diamètre de perçage : une goutte, avec une entrée et une sortie tangentes. Égal : un cercle. Plus près : une demi-volte.
- **Rayon de perçage** : un point d'entrée ou de sortie trop près d'un contour du dessin est signalé.
### v0.713.0 — Rampe à distance maxi, limite en Z des tirés d'angle

- **Distance maxi de la rampe** : la descente se fait en allers-retours sur les premiers millimètres du contour, à l'angle demandé, sans passer sur un pontet.
- **Limite en Z du tiré** en découpe 3D : l'outil continue de monter dans la même pente, au-dessus de la matière, pour évacuer les copeaux.
### v0.714.0 — Gamme à plusieurs outils

- **Gamme multi-outils** : autant d'outils qu'il faut, classés seuls du plus gros au plus fin : fraises d'abord, puis outils coniques. La fenêtre donnait une ébauche et une finition.
- **Une ligne par outil** : balayage ou contournage et son angle, distance entre passes, profondeur plus faible si besoin, et pour un cône sa finition 3D (tirés d'angle) ou non (contour 2D sans remontées).
- **Pour toute la gamme** : Z de départ, profondeur totale, respect du contour en surface ou en fond, surépaisseur, cadre englobant ignoré.
- Les opérations portent le nom de leur outil et se reprennent : chacune n'usine que ce que les précédentes ont laissé. Les outils coniques d'une gamme doivent avoir le même angle.
### v0.715.0 — Fer à dorer : choix des passes, galbe dans les formes

- **Choix des passes** : standard, intaille (la ligne centrale des formes et ses tirés d'angle, à l'outil conique), ou les deux.
- **Côté du galbe** : autour des formes, comme jusqu'ici, ou dans les formes, avec le fond vidé jusqu'au centre.
### v0.716.0 — Orientation de sortie

- **Orientation de sortie** (menu des réglages FAO) : la plaque, et donc les parcours, en miroir ou tournés dans le programme écrit : les huit positions du manuel. Le réglage est gardé avec le dessin.
- La plaque garde son coin inférieur gauche et le zéro du programme garde sa place sur elle (centre, coin…). Les arcs, les trous et les palpages suivent.
- En miroir, la fenêtre de fin rappelle que le sens d'usinage s'inverse : avalant et opposition sont échangés.
### v0.717.0 — Simulation 2D : profondeur, contour théorique, fond, hors matière, zoom

- **Profondeur de la vue** : un curseur et un champ. À une cote donnée, ce qui est enlevé apparaît en bleu ; à 0, le relief ombré. Sans refaire la simulation.
- **Théorique** : le contour du dessin en rouge, pour comparer l'usinage au dessin.
- **En fond** : le fond de gravure ressort en orange.
- **Hors matière** : les déplacements de l'outil, même hors de la matière, en pointillés bleus.
- **Zoom** : clic droit pour agrandir, Maj + clic droit pour réduire, jusqu'à 8 fois. L'image enregistrée garde les tracés.
### v0.718.0 — Informations et comptes rendus d'un parcours

- **Informations…** (clic droit sur une opération, ou Ctrl+I quand la liste a la main) : type, distance d'usinage, distance en rapide, durée, cotes mini et maxi, profondeur.
- **Compte rendu parcours outil…** (clic droit, ou Ctrl+T) : le contenu se choisit (outil, vitesses, parcours, durée et longueur, notes, image), puis deux PDF : le compte rendu du parcours et le compte rendu final.
- **Compte rendu final** : tous les parcours à usiner, leur outil et son numéro, la durée et la longueur totales. Un **facteur** en pourcentage multiplie la durée, selon le réglage de la machine ; les notes y figurent.
- Les fichiers proposés sont numérotés à côté du dessin (NOM_000_ReportByToolpath.pdf, NOM_000_FinalReport.pdf) et rien n'est écrasé sans le demander. Ctrl+I reste Importer ailleurs que sur la liste.
### v0.719.0 — Aperçu du reste de matière : une fenêtre et un bon à tirer

- **Reste de matière** ouvre une fenêtre : les outils par type, la surépaisseur, la profondeur, et les zones où l'outil ne passe pas en rouge. Tout se met à jour en changeant d'outil ou de réglage.
- **Au curseur** : le cercle de l'outil, et un second pour la surépaisseur, avec les coordonnées. La molette agrandit autour du curseur.
- **Épaisseur ignorée** : une zone plus mince compte pour usinée.
- **Imprimer le bon à tirer** : un PDF avec la date, le fichier, l'outil, la surépaisseur, la profondeur, et l'image.
- **Aperçu du reste** : le même aperçu depuis le formulaire d'une opération, avec son outil, sa profondeur et sa surépaisseur.
- **Poser sur le dessin** garde le calque « Reste de matière » d'avant.
### v0.720.0 — Grouper les programmes

- **Grouper les programmes** (menu des réglages FAO) : tout dans un seul fichier, comme jusqu'ici, un fichier par plan, ou un fichier par parcours. Le réglage est gardé avec le dessin.
- Les fichiers portent le nom choisi suivi du plan, ou du numéro et du nom du parcours. Si certains existent déjà, la question est posée avant d'écrire.
- Chaque fichier est relu et comparé à ses parcours, et la fenêtre de fin donne tous les fichiers et toutes les remarques.
### v0.721.0 — La simulation en relief sur le dessin

- **Poser en relief sur le dessin** (simulation 2D) : la matière simulée devient un objet relief du plan actif, à sa place sur le dessin. Il se regarde, se combine et s'usine comme les autres reliefs.
### v0.722.0 — Entrée et sortie contour par contour

- **Entrée et sortie d'un contour** (FAO 2D, à côté des pontets à la main) : un clic près d'un contour fermé y met le départ et demande son entrée et sa sortie, à la place de celles de l'opération. 0 : sans. Un clic sur le repère les change ou les retire. Le repère suit la forme.
### v0.723.0 — Les modes de tracé comme dans TypeEdit 13

- **Aller-retour** : à chaque passe, l'outil suit le trait puis revient dessus à la même profondeur, sur les contours fermés comme sur les traits ouverts.
- **Aller-retour sur la dernière tranche** : ce retour à la dernière passe, contours fermés compris.
- **Aller simple** : ce que faisait l'ancien « Aller-retour » : un sens par passe sur un trait ouvert, sans relever. Les opérations déjà enregistrées gardent exactement leur parcours.
- **Toujours dans le même sens** : l'ancien « Aller simple », sous ce nom.
### v0.724.0 — Textes vivants : polices que TypeEdit 13 ne reconnaît pas

- Avec l'option « textes modifiables », un texte en police variable (Bahnschrift…) part en courbes : TypeEdit 13 ne reconnaît pas ces polices, même installées.
- De même pour un nom de police réduit à sa forme interne, en minuscules et sans espace : TypeEdit 13 l'aurait remplacée.
### v0.725.0 — Les couleurs des courbes, comme dans TypeEdit 13

- **Un VND réécrit garde ses couleurs.** TypeEdit garde une couleur par courbe, en plus de celle de l'outil ; VectorDrive la perdait dès que la structure du dessin changeait : les courbes colorées repartaient noires. Elles gardent maintenant leur couleur, et leurs contours toutes leurs propriétés.
- **VectorDrive montre ces couleurs**, à l'écran et dans les exports (images, PDF, SVG, PostScript, BAT). Une courbe mise sur un autre outil prend la couleur de cet outil. Une courbe blanche, que TypeEdit ne montre plus sur fond blanc, reste visible dans VectorDrive.
- **Un dessin de VectorDrive s'ouvre en couleurs dans TypeEdit** : chaque courbe y a la couleur de son outil, y compris par le presse-papiers. Elles y étaient toutes noires.
- **Les noms** des courbes et des zones sont gardés à la réécriture.
### v0.726.0 — Le point de départ du dessin, comme dans TypeEdit 13

- En **Point de départ du dessin**, un détourage extérieur commence maintenant là où TypeEdit 13 le fait commencer : au début du côté par lequel l'outil quitte le sommet, après l'arrondi de l'angle, et non au milieu de cet arrondi. L'entrée en goutte y est tangente : mêmes demi-cercles que l'entrée automatique de TypeEdit 13.
- Un point de départ posé à la main et le départ « au plus près » ne changent pas.
### v0.727.0 — Fer à dorer : le galbe de TypeEdit 13

- **Le profil était à l'envers** : il partait plat du bord des formes et finissait raide au fond. Il part maintenant raide et finit plat, comme dans TypeEdit 13 : mêmes cotes à moins de 0,003 mm sur le dessin d'essai.
- **Les angles se comptent comme dans TypeEdit** : départ depuis la verticale, arrivée depuis l'horizontale. L'angle de départ est ramené au demi-angle de l'outil et à la droite du bord au fond.
- **Dans les formes par défaut**, comme TypeEdit. Autour des formes reste au choix, et les dessins déjà réglés le gardent.
- **Les passes partent du bord**, s'enchaînent sans remonter, et une forme est finie avant la suivante.
- **La passe centrale** suit le même profil, jusque dans les angles.
### v0.728.0 — Gravure 3D : tirés d'angle et ordre de TypeEdit 13

- **Tirés d'angle** : dans les angles plus fermés que l'angle réglé (135° par défaut), la pointe remonte le long de la bissectrice jusqu'à toucher les deux bords en surface. Avec une pointe assez large par rapport à la distance entre passes, VectorDrive n'en faisait aucun et laissait les angles ronds. 0 : aucun. Le mode « contour 2D » n'en fait toujours pas.
- **Du centre vers le bord par défaut**, comme TypeEdit 13, le contour en dernier : « En partant de l'extérieur » donne l'ordre d'avant. Les mêmes surfaces sont usinées, dans un autre ordre. En paliers, chaque palier reste du bord vers le centre.
- **Distance entre passes au fond**, au choix (mêmes passes et même longueur que TypeEdit 13 à 0,1 mm). 0 : comme avant. Reprise de TypeEdit à l'import de ses réglages.
- **Entrée en rampe** au choix en gravure 3D.
- **L'outil reste au fond** entre deux bras d'une forme, là où le fond sera de toute façon usiné.
### v0.729.0 — Passes connectées en descente angulaire

- **Connecter les passes** : d'une passe à la suivante, l'outil reste dans la matière et descend en rampe le long du contour, sans remonter. TypeEdit 13 ignore ce réglage en plongée angulaire et remonte à chaque passe. VectorDrive le respecte, en détourage, en poche et maintenant en tracé.
- **À l'import d'un réglage de TypeEdit**, `ConnectToolpath` coche cette option quand la plongée angulaire est active.
- **Un seul tour par passe en rampe** : VectorDrive faisait deux tours complets à chaque passe. Il fait maintenant un tour et reprend la partie en pente à la cote, comme TypeEdit 13 : 512 mm au lieu de 998 mm sur le dessin d'essai.
- **L'angle de rampe est exact**, même sur un long côté, où la pente s'étalait jusqu'au sommet suivant.
- **Rampe sans connexion**, pour les nouvelles opérations : à chaque passe, l'outil remonte et repart en pente comme dans TypeEdit 13, de la surface en détourage, de la passe d'avant en tracé. Les opérations déjà enregistrées restent dans la matière : l'option y est cochée à l'ouverture.
- **Poche** : la rampe suit l'anneau. Une fois la pente finie, l'outil pouvait repartir tout droit vers le début de l'anneau, à travers une forme non convexe.
### v0.730.0 — La distance entre ponts de TypeEdit 13

- **Distance entre ponts** : nouveau réglage, avec le même nombre de ponts que TypeEdit 13 aux mêmes distances. Elle compte de la fin d'un pont au début du suivant, là où « Un pontet tous les » compte d'un pont au suivant.
- **À l'import d'un réglage de TypeEdit**, sa distance va dans ce réglage. Avant, elle allait dans « Un pontet tous les » et donnait trop de ponts : 5 au lieu de 4 à 30 mm sur un contour de 156 mm.
- Les opérations déjà enregistrées gardent leurs ponts. Pour un modèle déjà importé, réimportez-le pour avoir le nombre de TypeEdit 13.
### v0.731.0 — Entrées et sorties : l'import de TypeEdit et la goutte

- **Import de TypeEdit corrigé** : VectorDrive ajoutait une entrée et une sortie de 6 mm à chaque Découpe importée, alors que TypeEdit 13 n'en fait aucune avec ces réglages. Réimportez vos modèles de Découpe : ceux qui sont déjà importés gardent ces arcs.
- **Rayon de transition** : nouveau réglage de l'entrée en goutte, le R de TypeEdit 13. Mêmes points que TypeEdit 13 pour les 5 couples rayon et distance essayés, y compris la demi-volte, quand la distance est plus petite que le diamètre du cercle.
- Le rayon de perçage de TypeEdit ne change pas le parcours : il ne sert qu'au contrôle des contours voisins. À l'import, il va dans le contrôle.
### v0.732.0 — Import de TypeEdit : passes, ordre et départ comme TypeEdit 13

Comparaison, sur un même dessin, des parcours de TypeEdit 13 et de VectorDrive pour 9 réglages enregistrés. Découpes, Tracés et Gravure 3D ont maintenant les mêmes passes et la même longueur, à 0,5 % près.

- **Une passe de trop** : 2 mm en 6 passes en donnaient 7, à cause d'un pas arrondi. Corrigé, y compris pour les modèles déjà importés.
- **Ordre des passes** : le choix Global ou Poche par poche de TypeEdit est repris à l'import. Il était ignoré.
- **Départ** : les contours importés partent du premier point du dessin, comme dans TypeEdit 13.
- **Gravure 3D en plusieurs passes** : le nombre de passes est repris. Chaque passe grave tout le fond avec le retrait de sa cote, sans passes sur les flancs, comme TypeEdit 13. Nouvelle case « Passes sur les flancs avant le fond » : cochée par défaut, décochée à l'import. **Réimportez vos modèles de Gravure 3D** pour en profiter.
- **Parcours `.000` de TypeEdit** : l'outil de l'en-tête est lu correctement. Il était refusé comme invraisemblable.
### v0.733.0 — Balayage : le parcours de TypeEdit 13

Sur 18 essais comparés, le Balayage a maintenant la même longueur que dans TypeEdit 13, à 0,03 % près, et les mêmes points d'entrée sur 15 d'entre eux.

- **L'outil reste en bas** : les rangées s'enchaînent en suivant le bord de la zone. Il ne remonte plus entre deux rangées d'une même partie.
- **Forme par forme** : en « Par zone » comme en « Avec saut d'îlots », une forme est finie avant la suivante. L'ordre Global ou Poche par poche est respecté.
- **Rangées** : posées à partir du bas de la zone, tous les « Distance entre passes ». **Sans cassé d'angle, comme dans TypeEdit, le bas de la zone n'est pas usiné.**
- **Plongée angulaire** : l'outil descend en aller et retour sur le début de la rangée ou du cassé d'angle, depuis la passe d'avant.
- **Angle « Optimisé »** : le long des côtés qui font le plus de longueur.
- **« X et Y »** : l'angle tourne d'une passe à la suivante, avec une nouvelle valeur de rotation.
- **Cassé d'angle** : il suit le sens et le départ de TypeEdit, les trous avant le bord extérieur.
- **Vos opérations enregistrées ne changent pas.** Réimportez vos modèles de Balayage pour en profiter.
### v0.734.0 — Finition : le parcours de TypeEdit 13

La Finition fait maintenant le trajet de TypeEdit 13 : sur 12 essais comparés, chaque contour a la même longueur à quelques centièmes de millimètre près, hors la descente depuis la hauteur d'approche.

- **Un seul trajet par contour** : l'outil suit le bord à la distance où le cône touche la surface. Il ne remonte plus entre le contour et les tirés d'angle.
- **Tirés d'angle dans le contour** : dans chaque angle plus fermé que l'angle réglé, l'outil monte au sommet le long de la bissectrice et redescend, sans quitter le contour.
- **Parties étroites** : là où le contour n'a plus la place, l'outil passe sur l'axe de la forme, à la profondeur que la largeur permet, va au bout et revient. Un goulot relie les deux parties en un seul trajet.
- **À chaque passe** : le tout, à sa cote. Une forme fine qui n'a rien de plus bas à usiner n'est pas refaite.
- **Plongée angulaire** : aller et retour sur le début du trajet, tirés d'angle compris. Sans plongée, le tiré d'angle s'arrête à la surface.
- **« Ignorer le cadre englobant »** : comme dans TypeEdit, tous les contours extérieurs sont ignorés, même ceux qui n'entourent rien. Sur des formes sans trou, il ne reste donc rien à usiner, et VectorDrive le dit.
- **« Finition 3D uniquement »** : nouvelle case, et importée : les tirés d'angle et les parties étroites, sans le contour.
- **Surépaisseur** : les arrondis restent centrés sur les sommets du dessin.
- **Profondeur** : elle n'est plus limitée par le diamètre de l'outil. Si le cône ne va pas jusqu'en surface, un avertissement donne le retrait laissé sur le bord.
- **Vos opérations enregistrées ne changent pas.** Réimportez vos modèles de Finition pour en profiter.
### v0.735.0 — Gravure 3D : le cadre et la profondeur comme TypeEdit 13 ; Finition plus rapide sur un gros dessin

- **« Ignorer le cadre englobant » en Gravure 3D** : le fond va jusqu'au cadre, seule la passe le long de son bord saute. Jusqu'ici, VectorDrive laissait non gravée la moitié de la bande contre le cadre.
- **Gravure 3D profonde** : la profondeur demandée est tenue, même au-delà de la hauteur du cône. Un avertissement donne le retrait laissé sur le bord. Jusqu'ici, la profondeur était limitée.
- **Finition sur un très gros dessin** : le calcul se fait forme par forme. Une géométrie que le calcul refusait ne l'arrête plus.
- **Vos opérations enregistrées ne changent pas.** Réimportez vos modèles de Gravure 3D pour en profiter.
### v0.736.0 — Gravure 3D : le fond dans l'ordre de TypeEdit 13

Le fond se grave maintenant branche par branche, comme dans TypeEdit 13 : une partie est finie avant de passer à la suivante, du centre vers le bord. L'outil ne fait plus l'aller-retour entre les quatre coins d'un cadre à chaque passe.

Sur un dessin d'essai, la longueur tombe de 41 264 à 39 793 mm, pour 39 715 mm dans TypeEdit 13.

Les nouvelles opérations et les modèles réimportés en profitent. Vos opérations enregistrées ne changent pas.
### v0.737.0 — Usinage : un dessin touffu ne bloque plus le calcul

Sur certains dessins aux nombreux contours qui se croisent, le calcul d'un parcours s'arrêtait sur une erreur de géométrie. C'est corrigé, pour tous les parcours fondés sur des contours fermés.

- Les zones qui se chevauchent de quelques microns sont réunies autrement, au lieu d'arrêter le calcul.
- Les contours non valides sont réparés.
- Les contours d'aire nulle, comme un trait repassé sur lui-même, ne comptent plus comme des formes. Aucun outil ne pouvait y entrer.
### v0.738.0 — Usinage : l'Intaille ne fait plus d'étoile sur les courbes

La gravure en ligne médiane (Intaille) suit maintenant l'axe des formes sans branches parasites. Les valeurs ci-dessous viennent de dessins mesurés dans TypeEdit 13.

- **Un cercle ne donne rien**, avec un avertissement, comme dans TypeEdit. Il donnait une étoile.
- **Un anneau donne son cercle moyen, un oblong son axe, une ellipse le segment entre ses centres de courbure.**
- **Les angles restent gravés jusqu'à 135°** : un angle de 120° garde sa branche, un angle de 150° n'en a pas.
- **L'outil reste au fond d'une branche à la suivante** au lieu de remonter.
- **La Finition profite du même nettoyage** dans ses passages d'axe.

Ce changement vaut pour les nouvelles opérations et les modèles réimportés. Une opération existante garde son calcul.
### v0.739.0 — Usinage : les Lettres prismatiques comme dans TypeEdit

Le parcours Lettres prismatiques a été refait d'après des mesures dans TypeEdit 13, sur des dessins d'essai.

- **En relief ou en creux** : la case « En creux » est nouvelle.
- **Passes latérales** : la nouvelle case enlève la matière par passes successives, à chaque niveau.
- **Un contour par niveau** : le centre de l'outil suit le contour décalé qui correspond à la pente de l'outil. Le contour exact est atteint au fond.
- **Les arêtes sont reprises** : celles des coins, saillants ou rentrants, et celles des parties étroites, jusqu'au plat du dessus.
- **Profondeur demandée** : elle est faite, avec un avertissement si le corps de l'outil doit toucher la matière. Une profondeur calculée (valeur 0) reste limitée au cône de l'outil.

Ce changement vaut pour les nouvelles opérations. Une opération existante garde son calcul.
### v0.740.0 — Usinage : plus de descente dans la paroi sur un décalage faux

Sur certains dessins, un parcours descendait à pleine profondeur à un endroit où l'outil n'avait pas sa place, et entamait la paroi. Le défaut touchait tout ce qui décale un contour : la découpe, la poche, la gravure, la finition, les lettres prismatiques.

- Les parcours déjà calculés restent faux tant qu'ils ne sont pas recalculés : recalculez ceux qui ont été faits sur des dessins à petits détails.
- Une entrée en plongée angulaire sur un chemin de quelques microns ne fait plus des centaines d'allers-retours : l'outil y descend droit.
### v0.741.0 — Finition : un tiré d'angle s'arrête avant la paroi

Un tiré d'angle pouvait passer contre une paroi courte et l'entamer. Il s'arrête maintenant avant elle, et le reste de la forme est repris par l'axe médian, comme dans une partie étroite.

- Les parcours déjà calculés restent tels quels tant qu'ils ne sont pas recalculés.
### v0.742.0 — Gamme : le parcours de TypeEdit 13

Avec un outil conique après une fraise, la Gamme fait maintenant le trajet de TypeEdit 13 : sur mon dessin d'essai, le cône coupe 1 072 mm là où VectorDrive en coupait 5 405, pour 1 350 mm dans TypeEdit 13. Sur 12 essais, la pièce simulée est la même à 0,11 mm près, sauf quelques cellules le long des parois et les endroits où TypeEdit laisse de la matière.

- **Le cône ne repasse plus sur les flancs.** Forme par forme et à chaque passe : le fond là où l'outil d'avant n'a pas pu aller, puis le contour à la cote, avec ses tirés d'angle en Finition 3D.
- **Profondeur de passe par ligne** : nouvelle colonne de la Gamme.
- **La fraise reste à son rayon + la pente du cône**, sans compter la pointe, à la profondeur du cône. Elle usine donc un peu plus près de la paroi.
- **Plusieurs cônes** : chacun laisse à la paroi la pointe du suivant.
- **Distance entre passes du cône** : 50 % de la pointe par défaut.
- **En fond de gravure** : pas de pente et pas de tirés d'angle, comme TypeEdit 13.
- **Ignorer le cadre** : seul le cadre est sauté, les formes sans trou gardent leur contour, comme TypeEdit 13.
- **Reprise à la fraise** : un coin après l'autre, l'outil remonte entre deux.
- **Les gammes déjà dans vos dessins ne changent pas.** Refaites une gamme pour en profiter.

Corrigé aussi pour toutes les poches : une liaison au fond entre deux anneaux pouvait entamer la surépaisseur.
### v0.743.0 — Import des gammes de TypeEdit 13

Une gamme enregistrée dans TypeEdit 13 est maintenant importée avec les règles de la gamme de VectorDrive. Sur 9 gammes enregistrées, calculées par TypeEdit 13 sur mon dessin d'essai, les 25 parcours ont les mêmes bornes à 0,001 mm près, et les pièces simulées le même volume à 0,03 % près.

- **Profondeur** : une ligne sans profondeur propre va à celle de la gamme. L'ancien import prenait une valeur rangée dans la ligne que TypeEdit ignore : 3 gammes sur 30 usinaient trop ou pas assez profond.
- **Repris aussi** : Ignorer le cadre, la Finition 3D, le sens de chaque ligne, la surépaisseur et la pente du cône sur la paroi de la fraise.
- **Plongée angulaire** sur toutes les lignes. Dans une reprise ou un fond de cône, la rampe suit le fond, à l'aller et au retour, comme TypeEdit 13.
- **Passes en mode Global** : le cône et les reprises font chaque passe sur tout le dessin avant la suivante.
- **Cône profond à plusieurs passes** : les passes hautes ne longent plus les murs une seconde fois. Il reste les angles, comme TypeEdit 13 : 4 186 mm au lieu de 8 073 sur mon essai, pour 4 528 dans TypeEdit 13.
- **Cadre ignoré** : ses angles ne sont plus repris à la fraise ni au cône.

Les modèles déjà importés gardent leur calcul : réimportez-les pour en profiter.
### v0.744.0 — Ouvrir retient sa taille et ses dossiers ; va-et-vient 2D / 3D

**Ouvrir (Ctrl+O)**
- La fenêtre s'ouvre agrandie la première fois, puis comme vous l'avez laissée : à sa taille, agrandie ou en plein écran (⛶, F11). En quittant le plein écran, elle reprend sa taille d'avant.
- Elle s'ouvre dans le dernier dossier regardé, même si vous l'avez fermée sans rien ouvrir.
- **Derniers dossiers** : un petit bouton à côté des flèches déroule les 10 derniers dossiers où un dessin a été ouvert ou enregistré. Le dossier affiché n'y est pas, ni un dossier disparu d'un disque du poste. Un dossier réseau n'est lu que si vous le choisissez.
- La liste des formats imposait 1 480 px de large à la fenêtre. Elle peut maintenant descendre à environ 990 px.
- La boîte Ouvrir avec aperçus retient aussi sa taille et propose les derniers dossiers dans « Regarder dans ».

**Va-et-vient 2D / 3D**
- Le bouton montre toujours 2D et 3D : le mode en cours en couleur, l'autre grisé. Un clic n'importe où sur le bouton bascule.
- **La FAO suit le mode** : un seul onglet FAO paraît, « FAO 2D » en 2D et « FAO 3D » en 3D. Si l'onglet FAO était affiché, il passe de l'un à l'autre. Une session rouverte affiche l'onglet FAO du mode.

**Note de la 0.743 corrigée** : les 25 parcours importés ont les mêmes bornes en x et la même profondeur que TypeEdit 13, à 0,001 mm près. Les bornes en y n'ont pas été comparées.
### v0.745.0 — Finition et cône de gamme plus rapides

- Le cône d'une gamme (Finition 3D) et la Finition à passes se calculent plus vite, avec exactement le même parcours.
- Mesuré sur trois vrais dessins (cône de 0,4 mm à 30°, trois passes) : le cône de la gamme passe de 23 à 17 s, de 206 à 146 s et de 331 à 113 s ; la Finition seule, de 12 à 9 s, de 83 à 78 s et de 64 à 61 s.
### v0.746.0 — Un portable neuf reprend les réglages du précédent

- Une nouvelle version portable, décompressée à côté de la précédente (par exemple dans le même dossier), pose une question à son premier lancement : **Reprendre ses réglages** ou **Partir de zéro**.
- **Reprendre ses réglages** copie les options, les derniers dossiers, la taille d'Ouvrir, les outils, les modèles FAO, les thèmes, les scripts, les polices ajoutées et la bibliothèque. Les fichiers de récupération restent avec l'ancienne version.
- Rien n'est changé dans l'ancien dossier. Un fichier déjà présent dans le nouveau dossier n'est jamais remplacé.
- La question n'est posée qu'une fois, et seulement si le nouveau dossier n'a encore aucun réglage. S'il y a plusieurs versions à côté, celle utilisée en dernier est proposée.
- La mise à jour intégrée, qui garde déjà tout, ne pose pas la question. La version installée non plus.
### v0.747.0 — Un VND modifié reste complet après un redémarrage

- **Corrigé** : un dessin ouvert depuis un VND et modifié perdait son lien avec le fichier d'origine dans deux cas : rouvert par la session après un redémarrage de VectorDrive (mise à jour, arrêt brutal), ou enregistré en .vdz puis rouvert. Réenregistré en VND, ses textes TypeEdit devenaient des courbes et ses cotes des groupes, un solide 3D disparaissait, et les outils, la machine et les parcours TypeEdit repartaient du modèle.
- Le lien est maintenant gardé : le VND écrit est le même que si VectorDrive n'avait pas été fermé.
- Un .vdz enregistré depuis un VND contient aussi ce VND. Il est donc plus gros : sur un VND de 61 Mo, 32 Mo au lieu de 9,5. La session en garde une seule copie par fichier, écrite une fois.
- La réouverture prend un peu plus longtemps : 0,7 s de plus pour un VND de 18 Mo, 1,8 s pour 61 Mo.
- Un modèle de dessin n'emporte pas le VND d'où il vient.
### v0.748.0 — Décaler et Trait double : les courbes serrées gardent leurs deux côtés

- **Corrigé** : quand la pointe d'une courbe est plus serrée que la distance demandée, le calcul exact pouvait jeter tout un côté de la parallèle. Décaler gardait alors un morceau de la forme collé au tracé (un retrait de 1 mm laissait jusqu'à 1,9 mm² de matière sur le trait), et Trait double ne traçait qu'un des deux côtés.
- Relevé sur 39 dessins réels (150 courbes par dessin, 4 distances, 22 804 décalages) : 684 contours calculés exactement avaient un sommet trop près du tracé. Après correction : aucun.
- Décaler contrôle aussi chaque résultat exact : si l'un de ses sommets est plus près du tracé que la distance demandée, il prend le calcul natif. Ce contrôle coûte 5 % du temps de calcul.
### v0.749.0 — Décalage : une lettre à trou ne disparaît plus

- **Corrigé** : un petit retrait (de 0,1 à 0,5 mm environ) pouvait faire disparaître entièrement une lettre à trou, comme un D ou un O, quand son trou passe près du centre de la lettre. À l'inverse, un agrandissement pouvait boucher le trou d'un cadre qui contient une petite île.
- Le défaut était dans le calcul natif. Il touchait Décaler avec des raccords en pointe ou en biseau, les très grands tracés, et le contrôle du calcul exact avec raccords ronds, qui rendait alors le résultat faux.
- Sur 39 dessins réels (22 748 décalages comparés au calcul exact), 55 résultats natifs perdaient de la matière, jusqu'à 2 929 mm². Il en reste 30, jusqu'à 76 mm², dus à une autre cause, à examiner.
### v0.750.0 — Décalage : un anneau mince ne disparaît plus

- **Corrigé** : un petit retrait pouvait faire disparaître une forme mince en entier, avec tout ce qu'elle contient : par exemple un anneau de 24 mm et 0,6 mm d'épaisseur, retiré de 0,15 à 0,25 mm, ou un cadre fin entourant un texte.
- **Corrigé** : une forme traversée par un trait ouvert pouvait disparaître dans un retrait. Le trait creuse maintenant la forme, comme dans le calcul exact. Ses bouts restent en pointe dans le calcul natif, alors qu'ils sont ronds dans le calcul exact.
- Comme au round précédent, le défaut était dans le calcul natif : Décaler avec des raccords en pointe ou en biseau, les très grands tracés, et le contrôle du calcul exact.
- Sur 39 dessins réels, les résultats natifs qui perdent de la matière alors que le calcul exact est juste passent de 30 à 26, et la plus grosse perte de 76 à 61 mm². Les 7 plus grosses pertes restantes viennent d'une même forme faite de contours doublés, que les deux calculs ne lisent pas de la même façon.
### v0.751.0 — Usinage : plus de passe dans la paroi des petites formes

- **Corrigé** : une forme ou un trou trop petits pour l'outil pouvaient recevoir une passe fantôme qui entrait dans la paroi, jusqu'à 0,4 mm sur l'essai. C'était le cas de la passe de finition d'un détourage avec surépaisseur, du chanfrein d'arête, de la découpe 3D, de la découpe sur ligne commune et du tour des lettres prismatiques (ancien trajet). La première passe du détourage et la poche étaient déjà protégées depuis la v0.740.0. Ces passes sont maintenant contrôlées de la même façon.
- Le chanfrein d'arête prévient quand la forme est trop petite pour la pointe de l'outil, au lieu de ne rien faire sans message.
- Les zones de collision de la découpe en chaîne et des boucles aux angles passent par le même contrôle.
- Les parcours déjà calculés ne changent pas tant qu'ils ne sont pas recalculés.
- Mesuré sur 39 dessins réels, pour des rayons d'outil de 0,25 à 1,5 mm : sans ce contrôle, un décalage vers l'extérieur gardait 44 faux trous (19 dessins), et un décalage vers l'intérieur 16 fausses parties (7 dessins), jusqu'à 1,13 mm plus près de la paroi que l'outil.
### v0.752.0 — Finition et cône de gamme encore plus rapides

- Le cône d'une gamme (Finition 3D) et la Finition à passes se calculent plus vite, avec exactement le même parcours.
- Mesuré sur six vrais dessins (cône de 0,4 mm à 30°, trois passes), les deux versions lancées en même temps : le cône de la gamme prend 8 à 18 % de temps en moins, par exemple de 130 à 108 s ; la Finition seule, de 2 à 15 % en moins.
- Sur le dessin qui prenait 13 minutes avec ce réglage avant la v0.745.0, le cône de la gamme prend maintenant moins de 2 minutes.
### v0.753.0 — Contrôle des programmes : trous percés simulés, petits arcs bien relus

- Une plongée verticale creuse maintenant jusqu'à son point le plus bas : perçage, débourrage, entrée droite d'un outil. Avant, elle restait à la cote de son départ : les trous percés n'apparaissaient pas dans la simulation.
- Au débourrage, le retour en rapide dans le trou déjà percé n'est plus signalé à tort comme « déplacement rapide dans la matière ». Une vraie descente rapide dans la matière, ou plus bas que le trou, l'est toujours.
- Le reste de la simulation ne change pas.
- Relecture des programmes ISO : quand aucun arc ne permet de dire si les centres I J sont absolus ou relatifs (petits arcs loin de l'origine), VectorDrive retient la lecture qui suit le mieux l'ensemble des arcs. Avant, de tels programmes à centres absolus étaient relus en relatifs : le contrôle du programme écrit signalait à tort un écart de plus de 1 mm, et l'aperçu du programme montrait des arcs énormes.
### v0.754.0 — Zéro du programme : coin ou centre de la plaque, comme TypeEdit

- Nouveau réglage FAO « Zéro du programme » (menu des réglages du panneau FAO, à côté de l'orientation de sortie) : le point X0 Y0 des programmes machine. Au choix : l'origine du dessin (réglage par défaut, comme avant), le coin supérieur gauche, le centre ou le coin inférieur gauche de la plaque. Comme le positionnement de la pièce de la fenêtre Usinage de TypeEdit, un point de la plaque ne dépend pas de l'origine du dessin. Le réglage est gardé avec le dessin ; avec une orientation de sortie, le zéro garde sa place sur la plaque.
- Le zéro du programme est dit avant et après l'écriture : en tête du récapitulatif de la vérification, et dans le message de fin (« Zéro du programme (X0 Y0) : coin supérieur gauche de la plaque — l'origine de la machine se règle sur ce point »).
- S'il ne tombe ni sur un coin ni sur le centre de la plaque, ou s'il n'y a pas de plaque, la vérification le signale : l'opérateur ne pourrait pas régler l'origine de la machine sur un repère de la plaque.
- Pourquoi : sur une machine où l'opérateur règle l'origine au lancement de l'usinage, un programme dont le zéro n'est pas au point attendu est usiné décalé, par exemple d'une demi-plaque, et l'outil peut sortir de la plaque vers l'étau ou les brides.
### v0.755.0 — Zéro du programme selon la machine

- Le réglage FAO « Zéro du programme » propose en premier « Selon la machine », qui devient le réglage par défaut : le zéro est celui qu'attend la machine choisie, quand son post-processeur ou sa fiche machine le disent (par exemple le coin supérieur gauche de la plaque, sur une machine où l'opérateur règle l'origine sur ce coin au lancement de l'usinage). Sinon, c'est l'origine du dessin, comme avant.
- La fenêtre du réglage dit ce que donne ce choix pour la machine du dessin : « Selon la machine (ici : coin supérieur gauche de la plaque) ».
- Un choix fait dans le dessin (origine du dessin, coin ou centre de la plaque) passe avant celui de la machine. Il reste dit dans la vérification avant l'écriture et dans le message de fin, comme en 0.754.0.
- Plugins : une fonction d'écriture de post-processeur dit le zéro de sa machine par son attribut `program_zero`, un fournisseur de fiches machine par `default_zero(clé)`.
### v0.756.0 — Réglages des nouvelles opérations comme TypeEdit

- Options (F10), onglet FAO : quatre réglages des nouvelles opérations.
  - « Départ des contours fermés » : au plus près (comme avant) ou au point de départ du dessin, comme TypeEdit. Les points de départ choisis à la main restent respectés.
  - « Entrée en rampe des nouveaux détourages, poches et tracés » (TypeEdit : plongée angulaire), cochée par défaut, comme dans la plupart des réglages TypeEdit. Les passes connectées vont avec la rampe ; TypeEdit, lui, demande de couper la plongée angulaire pour les connecter.
  - Gravure 3D : sans passes sur les flancs avant le fond, et le fond à 50 % de la pointe de l'outil, comme TypeEdit. L'ancien fond (sans crête de plus de 0,02 mm) demande deux fois moins de passes ; il reste au choix.
- Les dernières valeurs d'un parcours retenues avant cette version ne remettent pas les anciens réglages d'origine sur ces points. Celles retenues depuis restent le choix fait au formulaire.
- Les opérations existantes et les modèles ne changent pas.
### v0.757.0 — Contours superposés : raccourci à, Décaler en pair-impair

- « Superposés » (supprimer les contours superposés) a le raccourci **à**. Il agit tout de suite, sur la sélection ou sur tout le dessin, avec les derniers réglages ; la première fois, et sur Ctrl+clic, la fenêtre des réglages s'ouvre. Le nombre de contours supprimés s'affiche dans la barre d'état.
- Décaler suit la règle pair-impair : une forme dont chaque contour est tracé deux fois ne laisse pas de matière. Agrandie, elle donne un anneau autour de chaque trait ; en retrait, rien. Jusqu'ici elle était remplie, puis décalée. Le message de fin compte ces contours et rappelle le raccourci à, qui supprime les doublons avant de décaler.
### v0.758.0 — Calques : une case pour tous

- Panneau des calques : une case dans l'en-tête de la colonne des cases coche ou décoche tous les calques d'un clic. Elle est partielle quand certains calques seulement sont affichés ; un clic sur elle les affiche alors tous. Le calque actif reste affiché, comme avec la case « Tous » de la liste des calques.
### v0.759.0 — Détourage intérieur arrondi : les petites îles gardées

- Détourage intérieur avec « Arrondi des angles » : une île plus petite que l'arrondi n'est plus avalée. Elle est gardée telle quelle, et l'outil en fait le tour sans l'arrondir. Les îles plus grandes ont leurs angles arrondis, comme avant.
- Le parcours le signale : un avertissement, l'île en surbrillance orange sur le dessin tant que le parcours est affiché, et une fenêtre d'information après le calcul. La fenêtre ne bloque pas le travail et ne revient pas tant que le parcours n'est pas recalculé. La surbrillance est gardée avec la session.
### v0.760.0 — Ruban : un seul onglet CAD, le va-et-vient près des onglets, F12 plein écran

- Le va-et-vient 2D / 3D n'est plus que dans la rangée des onglets, à droite. Les boutons 2D / 3D des rubans (Vue, Vues 3D, ancien onglet 3D) sont retirés. La moitié inactive du va-et-vient a un fin liseré de la couleur de la moitié active, pour qu'on la voie.
- Les onglets « 2.5D » et « 3D » deviennent un seul onglet **CAD**, à la même place. Son contenu suit le mode : outils de dessin en 2D, création 3D (pavés, extrusions, booléens…) en 3D. Si l'onglet CAD est ouvert, il le reste au changement de mode ; sinon, l'onglet ouvert ne change pas.
- **F12** : plein écran (Maj+F11 marche toujours). Le repérage polaire passe sur **Maj+F12**.
### v0.761.0 — Intaille standard, comme TypeEdit 13

- Gravure 3D, mode **« Ligne médiane en aller-retour (intaille standard) »** : l'outil suit un flanc à l'aller et l'autre au retour, comme le mode « Standard » de l'intaille de TypeEdit 13. Là où la forme est plus large que l'outil à la profondeur demandée, chaque flanc est quand même gravé. Là où l'outil touche les deux flancs, il passe deux fois sur la branche.
- Le mode « Ligne médiane (intaille optimisée) » ne change pas : les deux flancs en une seule passe, comme « Optimisé » dans TypeEdit 13.
- Import des modèles d'intaille de TypeEdit : le mode Standard ou Optimisé du modèle est repris, ainsi que sa surépaisseur. Un modèle qui ne précise pas le mode reste en intaille optimisée, comme avant.
### v0.762.0 — Calque Trajectoires : une ligne par parcours, son formulaire, et les programmes lus

- Le calque **Trajectoires** du panneau des calques se déplie d'un clic : une ligne par parcours, avec sa case (montré ou caché, comme dans la liste des parcours du panneau FAO), sa couleur, son outil et son nombre de mouvements.
- **Double-clic sur un parcours** : le formulaire complet de son opération. Validé, le parcours est recalculé.
- **Programme lu** (« Lire un programme ISO… », ou un programme glissé : ISO, Heidenhain, et SimPL avec l'édition qui le lit) : il arrive dans le calque Trajectoires, déplié, avec un parcours par outil. Le double-clic sur un de ces parcours en fait une opération de tracé. Son trajet est repris dans un calque « Programme : … » du dessin, une seule fois même s'il a plusieurs passes. L'outil est reconnu à son libellé. La profondeur et le nombre de passes sont ceux du programme. Une fois le formulaire validé, le parcours calculé remplace celui du programme, à sa place. Annulé, rien ne change.
### v0.763.0 — Programmes lus : l'outil du programme, le même

- **Parcours lu d'un programme** (SimPL, ISO, Heidenhain), double-clic dans le calque Trajectoires : le formulaire prend **l'outil du programme**, jamais un autre. Un outil du document de même référence (ou de même nom) est repris tel quel. Sinon l'outil est cherché dans Mes outils, puis dans les bibliothèques des plugins (le tools.json de l'atelier), d'abord par sa référence (« 0068443G » est trouvé dans « 0068443G / 114206 »), puis par son nom ; reconnu, il est copié dans le document avec ses cotes, sa broche et ses avances, au numéro du programme.
- **Outil inconnu** : une fenêtre propose de le créer d'après le programme. Le formulaire de l'outil s'ouvre avec sa référence (ou son numéro, pour un programme ISO de Cielle), son fabricant, sa vitesse de broche et ses avances (coupe, plongée, rampe) déjà remplies, et ses cotes lues dans son nom (« Fr2 » : Ø 2 ; « 30__0_6 » : cône 30°, pointe 0,6 ; « Z2 » : 2 dents ; « Lg6 » : longueur utile 6). Validé, il rejoint Mes outils (dossier « Outils des programmes ») et le document. On peut aussi continuer sans l'enregistrer, ou annuler.
- Dans le calque Trajectoires, un outil inconnu est marqué « ? » ; l'infobulle dit dans quelle bibliothèque un outil a été reconnu.
- Programme ISO : le numéro de l'outil (T), son commentaire et la vitesse de broche (S) sont lus ; les avances de coupe et de plongée viennent des mouvements.
### v0.764.0 — Colonnes des calques réglables ; Texte et Texte vertical au lieu de « Rapido »

- **Panneau des calques** : les colonnes Calque et Outil se règlent en glissant le bord de leur titre ; un double-clic sur un titre met la colonne à la largeur de son contenu (le double-clic sur un bord aussi). Les largeurs sont retenues d'un lancement à l'autre ; la colonne Objets va jusqu'au bord du panneau. À la première ouverture, Calque prend 60 % de la place et Outil le reste.
- **Disposition TypeEdit 13** : dans l'onglet Texte, les deux boutons qui s'appelaient « Rapido » s'appellent **Texte** et **Texte vertical**, chacun avec son icône (lettres sur une ligne, lettres l'une sous l'autre). L'onglet qu'ils ouvrent, « Rapido » dans TypeEdit, s'appelle **Mise en forme**, comme l'onglet de VectorDrive.
- Le bouton Texte vertical a sa propre icône partout.
### v0.765.0 — Préréglages de texte, mise en forme complète des polices

- **Onglet Mise en forme** (textes sélectionnés) : en plus de la police, de la hauteur, de la largeur, de l'interlettrage et de l'interligne, il a maintenant l'**inclinaison** (en degrés, négative : penchée à gauche), l'**espacement des lettres** (typographique avec crénage, proportionnel, serré avec crénage, serré, chasse fixe), comme la barre Rapido de TypeEdit 13 (Italique, Souligné, Petites majuscules, Italique et souligné…, Lettres… restent dans CAD › Texte).
- **Préréglages de texte** : un groupe Préréglages dans l'onglet Mise en forme. Choisir un préréglage dans la liste le pose sur les textes sélectionnés et le donne aux nouveaux textes ; **Enregistrer le préréglage…** garde sous un nom la mise en forme du texte sélectionné (sans sélection : celle des nouveaux textes) ; la liste montre le préréglage du texte sélectionné.
- **Gestionnaire des préréglages** (Préréglages de texte…, aussi dans l'onglet CAD) : la liste des préréglages, et tous les réglages de celui qui est choisi — police, hauteur, largeur, interlettrage, interligne, inclinaison, alignement, espacement, souligné, petites majuscules, de droite à gauche — enregistrés à chaque changement ; Nouveau…, Dupliquer, Renommer…, Supprimer, Importer…, Exporter… (fichier JSON), Appliquer à la sélection, Pour les nouveaux textes. Les styles de texte d'avant y sont.
- **Nouveaux textes** : ils prennent le préréglage choisi (police, hauteur, largeur, espacements, inclinaison, styles) ; ce qu'on change dans la fenêtre du texte est repris pour le suivant.
- **Disposition TypeEdit 13** : l'onglet Mise en forme ouvert par les boutons Texte et Texte vertical a les mêmes champs (police, hauteur, largeur, inclinaison, interlettrage, interligne, espacement) et les préréglages ; sans texte sélectionné, ces champs règlent le texte qu'on va écrire, comme dans TypeEdit.
### v0.766.0 — Police monotrait intégrée « VD Géo »

- **VD Géo** : une seconde police monotrait intégrée, à côté de VD Trait, toujours là sans police installée. Linéale géométrique dans l'esprit des années 1920 : O et o ronds, a et g à un seul étage, sommets pointus, S de deux cercles, chiffres de même largeur (numéros alignés). Dessin original, à la règle et au compas : cercles, arcs d'ellipse et droites ; les courbes sont des arcs exacts, jamais des polylignes.
- **Gravée en un passage** : des traits ouverts sur la ligne médiane, peu de levées d'outil (a, b, d, g, p, q, O, S, chiffres… d'un seul trait), et aucun trait repassé (n, m, r, u : le fût, puis l'arche), pour qu'un laser ne marque pas deux fois.
- **Caractères** : ASCII, Latin-1, Latin étendu A (338 caractères : lettres accentuées composées, Œ, Æ, ß, Ł, Đ, ŋ…), guillemets, tirets, €, ‰, ™, ©, ®, ⌀, fractions, espaces fines.
- Dans toutes les listes de polices, juste après VD Trait ; hauteur des capitales 1, comme les polices Gravotech ; sans crénage.
### v0.767.0 — Plein écran sans clignotement, barre des tâches gardée

- **Plein écran sans clignotement** (F12) : sous Windows, la fenêtre en plein écran a maintenant un liseré d'un pixel. Sans lui, une fenêtre qui couvre tout l'écran avec une vue OpenGL (la vue 3D) passait en plein écran exclusif : l'image clignotait, menus, listes et bulles paraissaient mal.
- **Garder la barre des tâches** (Options › Affichage, à côté de Plein écran) : en plein écran, VectorDrive occupe l'écran sans cadre ni barre de titre, mais la barre des tâches de Windows reste visible et utilisable. Retenu d'un lancement à l'autre ; coché ou décoché en plein écran, il s'applique aussitôt.
### v0.768.0 — Outils : tri par colonne et filtres

- **Outils d'usinage** (panneau FAO) : un clic sur un titre de colonne trie la liste (T, Nom, Nature, Ø, Avance) ; un deuxième clic inverse, un troisième rend l'ordre du document. T, Ø et avance se trient en nombres (2 avant 10). Le tri est retenu d'un lancement à l'autre.
- **Filtres** au-dessus de la liste : une recherche (nom, référence, fabricant, Ø, n° T, dossier) et la nature de l'outil ; les autres outils sont cachés, rien n'est retiré. L'outil choisi dans une liste triée ou filtrée est bien celui qu'on modifie ou supprime.
- **Bibliothèque d'outils** et **Choisir un outil** : tri par colonne aussi (Ø en nombres) ; les dossiers et les groupes (Outils du document, Proposés pour…) restent en tête, dans leur ordre, les outils se trient dans chacun. Dans la bibliothèque, Monter et Descendre ne servent que dans l'ordre rangé.
### v0.769.0 — Police VD Géo enrichie : grec, flèches, signes techniques

- **Grec** : l'alphabet complet, capitales et minuscules (ς final compris), dans le même dessin géométrique ; les capitales communes avec le latin (Α, Β, Ε, Η, Ο…) sont les mêmes. Accents monotoniques composés (ά έ ή ί ό ύ ώ, ϊ ϋ ΐ ΰ) ; sur les capitales, le tonos se place à gauche de la lettre (Ά Έ Ώ…).
- **Flèches** ← ↑ → ↓ ↔ ↕ ↖ ↗ ↘ ↙ ⇐ ⇒ et **signes techniques** ≤ ≥ ≠ ≈ ∞ √ ∠ ⊥ ∥ ′ ″ № ℃ ℉ ✓ ✗ ; Ω de l'ohm, ∆, ∑, ∅ ; μ grec.
- **Exposants et indices** ⁰ à ⁹, ₀ à ₉ (H₂O, m³), **fractions** ⅓ ⅔ ⅛ ⅜ ⅝ ⅞, barre de fraction, tirets.
- **Virgule et point souscrits** : roumain Ș ș Ț ț (virgule, pas cédille), ạ ẹ… ; les lettres latines accentuées du Latin étendu B et additionnel que la composition sait faire (Ǎ ǎ Ǒ ǒ Ȧ ȧ Ḃ…), et les équivalents canoniques (Å de l'angström, point-virgule grec).
- 671 caractères (338 avant), tous d'un trait continu, sans droite repassée ; un caractère dont les accents empilés sortiraient de la boîte des caractères n'est pas proposé dans la table.
### v0.770.0 — Le zoom reste quand le plan de travail change de taille caché

- **Zoom gardé** : quand le plan de travail change de taille pendant qu'il est caché, Qt lui rejoue sa taille au retour. Avant, cela refaisait « Tout voir » et le zoom ou le déplacement choisi était perdu. Maintenant « Tout voir » ne se fait qu'à la première taille, ou si la vue n'a pas bougé depuis le dernier cadrage ; une vue zoomée ou déplacée reste telle quelle.
- Le zoom d'un gros dessin repasse par l'aperçu mis à l'échelle puis le rendu net, comme avant la v0.764.0 : les colonnes réglables du panneau des calques changeaient sa largeur demandée, et ce redimensionnement rejoué remettait la vue au cadre.
### v0.771.0 — Police VD Géo : crénage

- **Crénage** : la police VD Géo a maintenant sa table de crénage, comme les polices TrueType : AV, To, Ty, LT, P., F, ou Vé se rapprochent ; en 10 mm de haut, « AVATAR » raccourcit de 6 mm. Elle s'applique dans les modes d'espacement « Typographique » et « Serré avec crénage », comme pour les autres polices ; « Proportionnel », « Serré » et « Chasse fixe » ne crènent pas.
- La table est calculée sur le dessin des lettres. Deux traits n'y sont jamais rapprochés à moins de 0,15 fois la hauteur des capitales, pour que la gravure ne soude pas deux lettres. Rien n'est créné après un chiffre ni après une apostrophe (« 7.5 », « l’été » restent lisibles). Les lettres accentuées par-dessus (À, Ÿ, ý) se crènent comme leur lettre de base.
- La police VD Trait reste sans crénage.
### v0.772.0 — Programmes lus : même nom, autre référence, autre outil

- **Outil d'un programme lu** (SimPL, ISO, Heidenhain) : un outil de même nom mais d'une autre référence n'est plus pris pour l'outil du programme, ni dans le document, ni dans Mes outils, ni dans les bibliothèques des plugins. Le programme le propose alors à la création, comme un outil inconnu. Un outil sans référence se reconnaît toujours à son nom.
- Les références multiples (« 0068443G / 114206 ») se comparent une à une, des deux côtés : un programme qui en donne plusieurs reconnaît l'outil qui en a une.
### v0.773.0 — Préréglages de texte sûrs

- **Import de préréglages** : un fichier aux valeurs illisibles (hauteur vide, « 5 mm » écrit en texte…) ne bloque plus le gestionnaire ni le démarrage de VectorDrive. Les valeurs illisibles sont écartées, et celles par défaut les remplacent. Un préréglage ne garde que la mise en forme : il ne change jamais le contenu ni la place d'un texte.
- **Interligne** : une valeur donnée dans le gestionnaire, dans le ruban sans sélection ou dans la fenêtre Texte remplace le mode d'interligne (fixe, proportionnel, typographique) enregistré avec le préréglage, comme sur un texte sélectionné.
- **Nouveau texte** : il garde les valeurs du préréglage que la fenêtre Texte ne sait pas montrer (interligne au-delà de 5, par exemple) ; seuls les champs changés dans la fenêtre remplacent ceux du préréglage, qui reste choisi sinon.
- Un préréglage qui ne change rien aux textes choisis ne fait plus d'étape d'annulation et ne marque plus le dessin modifié.
- Importer un préréglage du même nom que celui des nouveaux textes met ceux-ci à jour ; exporter dans un dossier où l'on ne peut pas écrire le dit, au lieu d'une erreur.
### v0.774.0 — Programmes lus : l'outil exact, la broche de chaque passage

- **Outil d'un programme lu** : un outil dont le nom est seulement contenu dans celui que donne le programme (« Fraise D2 » pour « FRAISE D2 L10 ») n'est plus pris pour lui, et le nom du fichier n'entre plus en compte (un outil de référence « 12345 » n'est plus reconnu dans « Commande_123456.nc »). Le programme propose alors l'outil à la création. Le même nom, une référence de l'outil donnée en commentaire (« (0068443G) »), ou écrite en mot entier dans le commentaire, le font toujours reconnaître.
- **Broche** : celle de chaque passage d'outil, modale comme sur la machine : un outil repris plus loin à une autre vitesse a sa vitesse, un outil sans S garde celle en cours.
- **Cône à pointe entière** dans le nom d'un outil d'atelier (« 2_Fr_90__1 ») : un cône à 90°, pointe 1, et non plus une fraise de Ø 90.
- Un outil proposé sans nom dans le programme s'appelle « T4 » (son numéro), et non plus comme le fichier ; il ne prend plus de cotes dans le nom du fichier.
- **Liste des outils triée** (panneau FAO) : après une modification, le même outil reste choisi, et non la même ligne. « − » ne supprime plus un autre outil que celui qu'on avait choisi.
### v0.775.0 — Programmes lus et préréglages : corrections de relecture

- **Outil d'un programme lu sans nom** : un outil proposé sous son seul numéro (« T3 ») et gardé dans le document n'est plus repris en silence par un autre programme qui appelle aussi T3, à une autre vitesse. Un outil du document nommé « T1 », d'une autre référence, n'est plus pris non plus. Le programme propose l'outil à la création. Un outil du document sans référence se reconnaît toujours au nom que donne le programme, et un outil d'une bibliothèque déjà copié dans le document est toujours repris.
- **Référence dans le commentaire** : une référence d'outil collée au reste par « _ » ou « - » (« FR2_0068443G », « FR2-0068443G »), suivie d'un point, ou qui contient une espace (« ABC 12345 »), est reconnue. Ni lettre ni chiffre collés devant ou derrière, et jamais la partie entière d'un nombre décimal (« 12345,6 »).
- **Cotes lues dans le nom d'un outil** : la pointe d'un cône suivie d'un mot ou d'une unité (« 30__0_6 Balay », « 30__0_6mm ») vaut 0,6 et non plus 0. Le Ø et la longueur utile ne sont plus tronqués non plus (« Fr2_5 Balay » : Ø 2,5), et « Fr2.5 » ne donne plus Ø 2.
- **Préréglage de texte mal formé** (alignement, espacement ou mode d'interligne donnés en liste dans un fichier importé) : la valeur est écartée au lieu de bloquer le gestionnaire ou le démarrage.
### v0.776.0 — VD Géo : florin, signe estimé et accents isolés

- **Police VD Géo** : ƒ (florin, le f descendu sous la ligne, d'un seul trait), ℮ (signe « estimé » des préemballages : un e rond, plus grand) et les accents isolés ˆ ˜ ˘ ˙ ˚ ˝ ˇ ˛, dessinés comme ´ ¨ ¯ ¸. Tout le jeu Windows-1252 est maintenant dessiné ; la police compte 681 caractères.
### v0.777.0 — Programmes lus : cotes et références, suite de la relecture

- **Cotes lues dans le nom d'un outil** : une référence collée par « _ » n'est plus prise pour la décimale d'une cote (« FR2_0068443G » : Ø 2, et non 2,0068443 ; un cône « 30__0_2_0068443G » reste un cône de pointe 0,2). Le Ø écrit à la mode atelier « 3__2_5 » vaut 2,5. Une pointe à trois décimales (« 30__0_125 ») est lue en entier.
- **Référence dans le commentaire** : reconnue aussi après « chiffre, » (« D3,0068443G »). Suivie de « -2 » ou « _2 », c'est une variante : l'outil de la référence courte n'est plus pris. Quand plusieurs références figurent, la plus longue l'emporte (« ABC 12345 » plutôt que « 12345 »).
- **Outil proposé au nom long** : un outil créé d'après un commentaire de plus de 60 caractères (nom tronqué) est retrouvé dans le document au programme suivant, au lieu d'être redemandé et créé en double.
- **Préréglage de texte** : un nombre démesuré dans un fichier importé est écarté au lieu de faire planter.
### v0.778.0 — Programmes lus : nom entier de l'outil proposé, règle des variantes

- **Outil proposé d'après un programme** : il garde le nom entier que donne le programme, même long. Deux outils dont les noms ne différaient qu'après le 60e caractère étaient pris l'un pour l'autre sans rien demander ; et un outil créé au nom long n'était pas retrouvé dans Mes outils au document suivant (redemandé, puis créé en double). Les deux sont réglés.
- **Référence dans le commentaire** : la règle des variantes (« 114917-2 », « 114917_2 » : un autre outil que « 114917 ») ne vaut plus que pour une référence qui finit par un chiffre, suivie d'un ou deux chiffres en fin de mot. « 0068443G_3 », « FR2-0068443G-2D », « 114917_30__0_2 » (référence puis cotes d'atelier) sont de nouveau reconnus.
### v0.779.0 — Le texte s'écrit dans le dessin ; la fenêtre Texte passe dans le ruban

- **Texte** : un clic avec l'outil Texte pose le départ, et la frappe écrit le texte directement dans le dessin, lettre après lettre, avec un curseur clignotant. Entrée : nouvelle ligne ; Tab : un ressort ; flèches, Origine, Fin : le curseur ; Ctrl+V : coller ; Échap, Ctrl+Entrée ou un clic ailleurs : le texte est fini (Échap une deuxième fois : l'outil Sélection). Toute la saisie d'un texte est un seul pas d'annulation ; un texte vidé s'en va.
- **Reprendre un texte** : un double-clic sur un texte droit, ou un clic dessus avec l'outil Texte, le reprend dans le dessin, le curseur à l'endroit cliqué. Les textes en arc, sur courbe, de droite à gauche ou dans un cadre gardent leur fenêtre.
- **Onglet Mise en forme** : c'est maintenant le formulaire du texte, sur deux rangées comme l'onglet Rapido de TypeEdit 13 — Retour et Texte ; Général (police, caractères, interlettrage, interligne, hauteur, largeur, inclinaison, espacement des lettres) ; Position du texte (alignements, ressort, vertical, droite à gauche, casse) ; Ligne de base (position, mode d'interligne, longueur maximale et compression) ; Largeur imposée (largeur et ajustement, venus de l'ancienne fenêtre Texte) ; Outils ; Préréglages. Il paraît avec l'outil Texte et passe devant ; Retour, ou un autre outil, ramène l'onglet d'avant. Un champ changé pendant la frappe s'applique au texte qui s'écrit, puis la frappe reprend.
- **Ressort** : un petit bouton dans Mise en forme, et la touche Tab pendant la frappe. Le grand bouton « Insérer un ressort » de la fenêtre Texte (texte sur courbe) devient un bouton à sa taille.
### v0.780.0 — F12 en trois temps

- **Plein écran** : F12 (ou Maj+F11), appuis successifs : plein écran, puis plein écran avec la barre des tâches de Windows visible et utilisable, puis la fenêtre. « Garder la barre des tâches » montre le deuxième temps.
### v0.781.0 — Polices de TypeEdit : lues par un plugin, plus par le cœur

- **Polices** : le cœur ne lit plus les polices installées par TypeEdit (Vision `.vnf`, Gravograph `.chr`), sans doute protégées : leur lecteur passe dans un plugin, qui les lit sur le poste sans jamais les redistribuer. Sans ce plugin, un texte dans une de ces polices est dessiné dans la police de remplacement et signalé « police absente », comme toute police manquante.
- **Plugins** : `Api.add_font_format` — un format de polices propriétaire : extensions, dossiers, infobulle dans les listes de polices, lecteur (nom, glyphes, métriques, crénage, caractères dessinés). Ses polices entrent dans l'inventaire en cache (refait quand un format arrive ou s'en va), la mise en page, le crénage, la table des caractères et les textes vivants des VND ; l'éditeur de polices ne part d'elles que si le format le permet ; un lecteur en défaut laisse le nom du fichier.
- Les polices SVG sont lues directement.
### v0.782.0 — Polices de TypeEdit absentes sans leur plugin : signalées

- **Polices** : TypeEdit installé, le cœur ne lit toujours pas ses polices ; un symbole ou un dessin de TypeEdit écrit dans une de ces polices s'ouvre avec tous ses textes, dessinés dans la police de remplacement, et la police est signalée absente du poste.
### v0.783.0 — Mise en forme : tout l’onglet à l’écran, une icône par commande

- **Ruban** : l'onglet Mise en forme tient en entier sur un écran de 1 920 px, et encore à 1 600 px, sans groupe replié. Les petits boutons du formulaire (alignements, casse, ligne de base, compression) suivent le mode « icônes seules » du ruban quand la place manque, et retrouvent leurs libellés dès qu'il y en a.
- **Icônes** : chaque commande de l'onglet a sa propre icône (casse en majuscules, minuscules, mots, petites capitales, initiale ; écriture de droite à gauche ; texte sur ou sous la ligne de base ; interligne fixe, proportionnel ou typographique ; compression de la ligne, du paragraphe ou globale ; rechercher / remplacer ; reproduire la mise en forme ; préréglages et leur enregistrement). Les lettres des icônes sont tracées avec la police filaire VD Géo : elles restent nettes à 16 px.
### v0.784.0 — Outil Texte et polices des plugins : corrections de relecture

- **Outil Texte** : bouger la souris sur le dessin pendant la saisie ne provoque plus d'erreur interne, et le repère d'accrochage suit de nouveau le curseur.
- **Outil Texte** : le curseur de saisie reste dans le texte quand celui-ci change sans la frappe (Rechercher / remplacer, casse) ; les espaces insécables (Alt+0160, AltGr+Espace) s'écrivent ; Maj+Tab écrit un ressort, comme Tab, au lieu d'emmener la frappe dans un autre champ.
- **Outil Texte** : changer d'onglet de dessin, en ouvrir ou en fermer un, ou quitter pendant la saisie finit le texte dans son dessin (un texte vidé ne reste plus, invisible, dans le dessin) ; un nouveau texte écrit puis effacé ne laisse plus de pas d'annulation qui ne fait rien.
- **Mise en forme** : un champ validé en cliquant dans un autre champ laisse la main à ce champ (avant, la frappe repartait dans le dessin) ; Entrée ramène toujours la frappe au dessin.
- **Mise en forme** : Largeur imposée remise à « libre » rend la police telle quelle (une lettre seule n'est plus étirée) et garde l'interlettrage choisi quand le texte a des ressorts ; quand Mise en forme s'en va, l'onglet d'où on l'avait ouverte revient, même ouverte à la main.
- **Polices des plugins** : une police abîmée ne fait plus échouer la mise en page (glyphes vides, mesures par défaut, crénage nul), et la liste des polices est relue quand le plugin qui les lit est mis à jour.
### v0.785.0 — Outil d'un programme lu : le créer ou choisir un outil existant ; les bibliothèques des plugins au formulaire

- **Programmes lus (SimPL, ISO…)** : un outil inconnu des bibliothèques peut être créé d'après le programme, comme avant, ou remplacé par un outil existant (document, Mes outils, bibliothèques des plugins). La case « Retenir ce choix pour les prochaines fois », cochée d'office, le fait reconnaître aux lectures suivantes.
- **Programmes lus** : à la lecture, une fenêtre propose les outils inconnus du programme (Créer l'outil… / Choisir un outil existant… / Plus tard). Elle se coupe dans les options FAO.
- **Calque Trajectoires** : un double-clic sur l'outil d'un parcours lu en choisit un autre, retenu ou pour cette fois seulement (décochée, l'association d'avant est oubliée). Le double-clic ailleurs sur la ligne ouvre toujours son formulaire.
- **Formulaire d'une opération** : « Choisir un outil » cherche aussi dans les bibliothèques des plugins, comme les outils DATRON de l'atelier, et les dossiers de la racine s'ouvrent sur leur premier niveau.
### v0.786.0 — Dimensions (F2) en pourcentage, F2 suivant pour les proportions, maintien de 0,25 s

- **Dimensions (F2)** : Largeur et Hauteur acceptent un pourcentage de la cote affichée : « 120% » agrandit, « 80% » réduit, « +20% » et « -20% » ajoutent ou retirent. Un champ « % » à côté de chacune agrandit ou réduit de même ; avec « Conserver les proportions », l'autre cote suit.
- **Dimensions (F2)** : le premier F2 ouvre les dimensions sans toucher à la case « Conserver les proportions » ; chaque F2 suivant, le curseur dans les dimensions, la coche ou la décoche.
- **Souris** : le maintien du bouton sur une forme avant qu'un glisser la déplace passe à 0,25 s par défaut (au lieu de 0,6 s), toujours réglable dans les options (Dessin › Maintien avant déplacement à la souris).
### v0.787.0 — Bibliothèque : ajouter la sélection

- **Bibliothèque** : un bouton « Ajouter la sélection » en haut du panneau et de la grande fenêtre enregistre la sélection du dessin en symbole dans le dossier affiché. Seul le nom est demandé (la première ligne d'un texte de la sélection est proposée) ; un nom déjà pris devient « nom (2) ». Le symbole ajouté est choisi dans la liste.
- **Bibliothèque** : clic droit sur un dossier, « Ajouter la sélection du dessin ici… » l'y enregistre. « Enregistrer la sélection sous… » garde la fenêtre Enregistrer sous ; elle sert aussi quand les favoris ou les récents sont affichés.
### v0.788.0 — Poche : seulement le reste (ébauche puis finition)

- **Poche** : nouvelle case « Seulement le reste », pour l'ébauche puis la finition d'une gravure. L'opération ne passe que là où les poches d'avant ont laissé de la matière : les coins plus fins que leur outil et la surépaisseur XY qu'elles ont laissée le long des bords. Ce qu'un outil au moins aussi gros a déjà vidé n'est pas repassé : leur outil et leur surépaisseur XY sont comptés (une passe de finition enlève cette surépaisseur).
- Les passes sont celles de la poche entière, gardées seulement là où l'outil enlève ce reste. La passe du bord compte le flanc d'un outil conique ; les autres comptent sa pointe. Sans poche active avant, la poche entière est faite (avec un message). La surface laissée et ce qui reste hors de portée de l'outil sont signalés.
### v0.789.0 — Corrections de relecture (outil d'un programme lu, F2, bibliothèque)

- **Outil d'un programme lu** : le double-clic sur un outil inconnu (« ? ») propose aussi « Créer l'outil d'après le programme… », en plus des outils existants. Avant, une fois la fenêtre des outils inconnus fermée, on ne pouvait plus le créer.
- **Outil d'un programme lu** : un outil créé depuis le formulaire (double-clic sur le nom du parcours) est reconnu sur les parcours lus ; le « ? » disparaît.
- **Outil d'un programme lu** : plusieurs programmes lus à la suite, la fenêtre des outils inconnus les garde tous (avant, seuls ceux du dernier).
- **Outil d'un programme lu** : un programme qui ne nomme pas son outil n'a rien à retenir. L'outil n'est plus copié dans Mes outils et le message dit « cette fois ».
- **Outil d'un programme lu** : un échec de l'enregistrement dans Mes outils n'est plus caché par le message « retenu ».
- **Associations des outils** : un fichier abîmé est mis de côté (`associations_programmes.abime.json`) au lieu d'être écrasé. Un fichier inaccessible (partage absent) n'est pas réécrit. Le fichier est lu avec ou sans BOM, et le fichier temporaire a un nom unique.
- **Fenêtres** : les fenêtres des outils inconnus, du choix d'un outil, de sa création et la question sont libérées une fois fermées.
- **F2** pendant le glisser d'un repère depuis la règle : la position en chiffres, même si le focus est dans les dimensions. Avant, il cochait ou décochait les proportions.
- **Ouvrir** (navigateur de fichiers) : ni bouton ni menu d'ajout de la sélection, qui n'y faisaient rien.
- **Bibliothèque en grande fenêtre** sur les favoris ou les récents : « Ajouter la sélection » ouvre Enregistrer sous. Avant, la sélection partait dans le dossier du panneau ancré. Un dossier illisible n'est plus visé.
- Traductions anglaises de l'option des outils inconnus et de l'aide du délai de maintien.
### v0.790.0 — Outils des programmes lus, en liste

- **Bibliothèque d'outils**, « Plus » ou clic droit, **Outils des programmes lus…** : les outils retenus à la place de ceux des programmes lus (case « Retenir ce choix pour les prochaines fois »). Pour chacun, l'outil du programme (nom, référence, numéro T…) et l'outil retenu (nom, référence, Ø).
- **Oublier** les associations choisies : à la prochaine lecture, l'outil du programme est proposé de nouveau. Pour en changer, double-clic sur l'outil d'un parcours lu (calque Trajectoires), comme avant.
- Un fichier des associations abîmé ou inaccessible est signalé. Le regarder ne le réécrit pas et ne le met pas de côté.
- Un outil de programme dont la référence n'a rien de lisible (« / ») est retrouvé, remplacé et oublié comme les autres.
### v0.791.0 — Glisser la sélection dans la Bibliothèque

- Déplacer la sélection **hors de la vue jusque sur une Bibliothèque** montrée (panneau ou grande fenêtre) la fait partir en glisser-déposer :
  - lâchée sur la **liste**, elle est ajoutée au dossier affiché (le nom est demandé, comme avec « Ajouter la sélection ») ;
  - lâchée sur un **dossier de l'arbre**, elle est ajoutée à ce dossier (pas sur Récents ni Favoris) ;
  - lâchée sur la liste des favoris ou des récents, Enregistrer sous s'ouvre ;
  - revenue dans la vue, elle est **déplacée là** (Maj : copiée, Ctrl : sur un axe, comme un déplacement) ;
  - lâchée ailleurs, rien ne change.
- Hors de la vue ailleurs que sur une Bibliothèque (règles, hors de la fenêtre), le déplacement continue comme avant.
### v0.792.0 — Poche, seulement le reste : corrections

- **Recalculée** quand une poche d'avant change : son formulaire validé refait aussi les poches « seulement le reste » qui la suivent. À l'écriture du programme, elles sont refaites si une opération d'avant a changé ou si l'ordre a changé. Avant, l'ancien parcours restait, par exemple sans la surépaisseur ajoutée à l'ébauche.
- Le **fond réel** des poches d'avant est comparé, **Z de départ** compris : une ébauche moins profonde ne compte plus.
- Une poche d'avant qui **ne vide pas tout** ce que son outil atteint n'est plus comptée, et un avertissement le dit :
  - balayage sans tour du contour, ou texturé ;
  - passes plus écartées que l'outil ;
  - outil conique dont le pas imposé est plus large que la pointe.
- Avant un **outil boule**, le pied des parois (arrondi) reste à faire.
- **Outil conique ou boule au contour respecté au fond** : la poche entière, car le flanc taille hors du contour.
- **Passe de finition** :
  - « pas de passe sur le cadre » est respecté ;
  - les parois déjà faites par un outil plus gros (arcs compris) ne sont plus repassées.
### v0.793.0 — Poche : plus de matière laissée (spirale, pas large) ; seulement le reste : liaisons et corrections

**Poche**

- **En spirale** : le premier tour est fait en entier. Avant, la spirale partait aussitôt vers l'anneau suivant et laissait de la matière : au centre en partant du centre (15 mm² sur un rectangle de 40 × 30 mm, fraise de 6, au pas d'origine de 40 %), le long des parois en partant du bord (plus de 100 mm² sur un cercle de 40 mm).
- **En spirale**, dans une forme à bras (un L, un T) : là où un anneau intérieur ne longe pas tout l'anneau suivant, le tour qui glisse de l'un à l'autre n'y passait pas et laissait une bande. Elle est reprise par un tour le long de son bord, après la spirale.
- **Pas plus large que le rayon de la fraise** (plus de 50 %) : la poche ne laisse plus rien entre ses passes.
  - L'îlot qui restait au centre, ou là où la forme se resserre, est repris par un tour de plus, juste après la passe qui l'entoure. Avant : 3,6 mm² au milieu d'un carré de 23,9 mm (fraise de 6, pas de 5 mm), sans rien dire.
  - Les lamelles des coins vifs sont enlevées par une reprise d'angle, d'office, aux seuls coins qui en laisseraient une (aucune à 90° tant que le pas ne dépasse pas 85 %). « Optimisation des angles » garde son réglage quand elle est cochée.
  - « En spirale » passe en anneaux, avec un message : à ce pas, une spirale laisserait de la matière entre ses tours. Les anneaux restent liés au fond, sans plongée entre eux.
- Rien ne change au pas d'origine (40 %) en anneaux, ni au pas plus large que la fraise.

**Poche, seulement le reste**

- **Liaisons** : d'un reste au suivant, l'outil remonte et se déplace en rapide quand c'est plus court que d'y aller au fond. Avant, toute liaison qui restait dans la poche se faisait au fond, à l'avance de coupe : d'un coin à l'autre d'un cadre, des dizaines de millimètres à vitesse lente. Sur un cadre de 48 × 46 mm avec une étoile en relief, le parcours dans la matière passe de 195 à 34 mm.
  - La limite se calcule avec les avances : la liaison au fond à l'avance de coupe, contre une plongée depuis la hauteur d'approche (ou la descente en hélice, si elle est réglée). Elle ne descend jamais sous le diamètre de l'outil : les petits sauts dans un même coin restent au fond.
  - En plusieurs passes, l'outil qui a fini un reste remonte avant le suivant. Avant, il y allait en biais depuis le fond, plus bas que la première passe, à travers ce qui n'était pas encore nettoyé.
- **Passe de finition** : elle est faite même quand il ne reste rien d'autre à nettoyer, et dans toutes les formes. Avant, avec la même fraise que l'ébauche et une surépaisseur, la poche ne faisait rien et disait « rien à nettoyer » ; une forme sans coin à reprendre (un cercle) n'avait pas sa passe de finition.
- **Ébauche à l'outil boule** : elle n'est comptée que si son pas ne dépasse pas la moitié de sa largeur. Au-delà, ses crêtes sont trop hautes, et un avertissement dit qu'elle n'est pas comptée.
- **Recalcul annulé** : après la validation d'une poche d'avant, si le recalcul d'une poche « seulement le reste » est annulé, elle n'est plus donnée pour à jour. Elle est refaite avant l'écriture du programme.
### v0.794.0 — Glisser la sélection dans la Bibliothèque : corrections

- **La sélection lâchée sur la liste de la Bibliothèque est ajoutée.** Depuis la 0.791.0, seul l'arbre des dossiers la prenait : sur la liste, le curseur d'interdiction s'affichait et rien n'était ajouté.
- Le glisser part aussi quand la Bibliothèque **recouvre la vue** (grande fenêtre, panneau flottant). Avant, il fallait que le pointeur sorte du rectangle de la vue ; sinon la sélection se déplaçait sous la fenêtre.
- **Curseurs** : sur la Bibliothèque, celui de la copie (la sélection reste dans le dessin). De retour dans la vue, celui du déplacement, ou de la copie avec Maj. Avant, c'était l'inverse dans la vue.
- Le glisser venu d'**une autre fenêtre VectorDrive** est refusé. Avant, la Bibliothèque enregistrait la sélection de sa propre fenêtre.
- Le repère d'accrochage ne reste plus affiché quand le glisser part vers la Bibliothèque.
- **Dossier illisible** affiché dans la Bibliothèque : « Ajouter la sélection » ouvre Enregistrer sous. Avant, la sélection partait dans le dossier choisi dans l'arbre, ou dans la première bibliothèque.
- **Outils des programmes lus** : un fichier des associations enregistré dans un autre codage (ANSI avec un accent, UTF-16) n'empêche plus de lire un programme. Il est traité comme un fichier abîmé : ignoré à la lecture, mis de côté à la prochaine écriture.
### v0.795.0 — Poche : corrections de relecture (finition en pleine matière, pas de 100 %, forme en T)

**Poche, seulement le reste**

- **Passe de finition dans une forme que personne n'a ouverte** : elle se fait à toutes les cotes, comme un contour, et un message le dit. Avant (0.793.0 et 0.794.0), dans une rainure où l'outil n'entre qu'à la finition (surépaisseur retirée), il plongeait d'un coup jusqu'au fond et faisait le tour en une seule passe, en pleine matière : 3 mm de profondeur avec une fraise de 1 mm dans l'exemple relevé. Le long d'une simple surépaisseur, la finition reste au fond seulement.
- **Liaisons au fond** : la limite est celle de la première passe, la même à toutes les cotes. Avant, elle grandissait avec la profondeur : une liaison refusée en haut passait au fond plus bas.
- **En plusieurs passes** : dans un même reste (un coin), l'outil descend à la passe suivante sans remonter au dégagement. Avant : deux remontées par coin pour trois passes. Pas si une descente en rampe est réglée.

**Poche au pas plus large que le rayon de la fraise** (plus de 50 %)

- **Ce qui reste entre les passes est mesuré sur le parcours lui-même**, anneaux et reprises d'angle compris, puis repris par un tour à la fin de chaque cote. Avant (0.793.0 et 0.794.0), il était prévu par un calcul à part, qui se trompait dans de rares formes : 20,8 mm² laissés dans le pied d'un T (barre de 60 × 14 mm, pied de 14 × 36 mm, fraise de 6, pas de 4,08 mm), sans avertissement.
- **Pas de 100 % exactement** : plus de reprises d'angle de quelques microns sur chaque sommet des arcs (256 sur un cercle de 40 mm), et le calcul ne s'emballe plus. Sur un cadre avec 20 lettres en relief, il prenait 38 s en 0.794.0 ; il reste sous la seconde.
### v0.796.0 — Poche, seulement le reste : passe de finition, corrections

- **Finition dans une forme que personne n'a ouverte, avec une surépaisseur de plus d'un demi-rayon de l'outil** : elle se fait à toutes les cotes. En 0.795.0, le cas était manqué : une fraise de 1 avec 0,3 mm de surépaisseur plongeait encore d'un coup au fond d'une rainure de 1,02 à 1,14 mm de large, ou d'un trou de 1,1 mm, et en faisait le tour en une seule passe.
- **Un coin aigu ne fait plus passer tout le tour de finition à toutes les cotes** : seul le tronçon qui longe de la matière jamais ouverte y passe, le reste du tour se fait au fond. Avant, sur un triangle à pointe de 30°, les 83 mm du tour étaient refaits à chacune des trois cotes.
- Un morceau fait à toutes les cotes en aller-retour **finit dans le sens réglé** (en avalant ou en opposition), que le nombre de passes soit pair ou impair.
- **Outil conique ou boule** : la finition reste au fond seulement, comme avant la 0.795.0. Le flanc de l'outil ouvre la matière à chaque passe ; le message « à toutes les cotes » sortait à tort.
### v0.797.0 — Poche : les tours ajoutés entre les passes, au plus proche

- **Poche au pas plus large que le rayon de la fraise, ou en spirale** : les tours ajoutés pour reprendre ce qui resterait entre les passes sont visités au plus proche. Avant, ils l'étaient dans l'ordre du calcul, avec de longues liaisons au fond de l'un à l'autre.
  - Sur une plaque de 100 îles carrées (fraise de 3, pas de 75 %) : 11 387 mm dans la matière au lieu de 12 951, 93 plongées au lieu de 97.
  - Au pas de 90 à 100 %, le parcours raccourcit aussi (5 533 → 4 658 mm sur 36 îles), avec quelques plongées de plus (89 → 103).
  - Rien de changé à ce qui est usiné.
### v0.798.0 — Exporter la sélection : cadrée sur elle ; le dernier export retenu

- **Exporter, « La sélection seulement »**, en image (PNG, JPG…), PDF, SVG, AI, EPS ou HPGL : le fichier est cadré sur la sélection, sans la plaque. Avant, la plaque suivait toujours : deux petits objets donnaient un PNG de 5 953 × 4 772 points ou un PDF de 510 × 410 mm, avec la sélection minuscule au milieu.
- En VND, VDZ, SMB et DXF, rien ne change : la sélection reste à sa place.
- Exporter tout le dessin en image garde le choix « avec la plaque ».
- **Le dernier export est retenu** : la fenêtre s'ouvre sur le format et les réglages du dernier export (le dossier l'était déjà).
### v0.799.0 — Dimensions (F2) : ordre de tabulation, référence plus visible, Ctrl + pavé numérique

- **Tab** passe par les cotes d'abord, puis par leurs pourcentages : X, Y, Largeur, Hauteur, Épaisseur Z, puis % largeur, % hauteur, % Z, Rotation, Échelle. Avant, chaque « % » suivait sa cote.
- **Épaisseur Z** et son « % » sont ajoutés, grisés : le dessin est en 2D, aucun objet n'a encore d'épaisseur.
- **Référence** : les neuf cases sont à droite de X et Y, plus nettes. Celle qui est choisie est pleine et bleue, et le cadre est tracé derrière elles. Le panneau est un peu moins haut.
- **Ctrl + 1 à 9 du pavé numérique** choisit le point de référence, disposé comme le pavé : 7 en haut à gauche, 5 au centre, 3 en bas à droite. Cela marche depuis le dessin. Ctrl+7, 8 et 9 du clavier gardent le sens, les couleurs et le remplissage.
### v0.800.0 — Une couleur par objet ; Ctrl + chiffre sans Maj ; surbrillance réglable

- **Couleur d'un objet** : Édition › **Couleur…** donne une couleur aux objets sélectionnés. Le trait la prend, et le remplissage aussi quand l'objet est rempli. Elle ne dépend pas de l'outil : l'objet la garde s'il change d'outil.
  - Sans couleur propre, l'objet garde celle de son outil, comme avant (noir pour l'outil 1).
  - Édition › **Couleur de l'outil** retire la couleur propre.
  - La couleur suit dans le VDZ, le VND (TypeEdit la montre comme couleur de la courbe), le SVG, le PDF, les images et le DXF.
- **Ctrl+8** (« Couleurs », auparavant « Couleurs des outils ») montre ou cache toutes les couleurs.
- **Ctrl + chiffre sans Maj sur un clavier français** : Ctrl+8 répond aussi à Ctrl+_ (la même touche), Ctrl+7 à Ctrl+è, Ctrl+9 à Ctrl+ç, et de même pour les vues Ctrl+1 à Ctrl+6. Avant, il fallait ajouter Maj, parce que les chiffres du haut d'un clavier AZERTY la demandent. Une touche déjà prise par une autre commande (Ctrl+- : zoom) n'est pas reprise.
- **Options › Épaisseur de la surbrillance de la sélection** : le trait des objets sélectionnés, 2 px par défaut, de 1 à 12.
### v0.801.0 — Imprimer la sélection : à l'échelle 1:1 ou ajustée à une feuille A4

- **Fichier › Imprimer la sélection…** imprime les objets sélectionnés seuls, sans la plaque, centrés sur la feuille. Deux choix :
  - **à l'échelle 1:1** (taille réelle) ;
  - **ajustée à la feuille A4**, avec des marges de 15 mm.
- Le dernier choix est proposé la fois suivante. L'aperçu avant impression et l'imprimante retenue restent ceux de F10 › Impression.
- Avant, il fallait cocher « Seulement la sélection » et changer l'échelle dans F10 › Impression, puis les remettre.
### v0.802.0 — Poche « Seulement le reste » : la finition ne prend plus de matière épaisse au fond d'un coup

- **Passe de finition** : elle se fait toujours au fond seulement là où il ne reste que la surépaisseur, et à toutes les cotes là où l'outil rencontre de la matière que personne n'a ouverte. Ce qui compte comme « jamais ouvert » est maintenant mesuré sur ce que l'outil rencontre vraiment : tout ce qui est plus épais que ce que les passes laissent dans un coin droit.
  - **Rainure derrière une cloison mince** : une rainure où seule la finition entre, à 0,05 – 0,4 mm d'une poche déjà vidée, passait pour ouverte et était prise au fond d'un coup, sur toute la largeur de l'outil. Elle est faite à toutes les cotes.
  - **Col court** entre deux poches, **passage entre une île et le bord** : même défaut sur les passages de 0,6 à 2,6 mm de long, corrigé.
  - Une surépaisseur seule, un coin droit ou arrondi : au fond seulement, comme avant. Un coin aigu, où il reste plus de matière : à toutes les cotes, sur la pointe seulement.
### v0.803.0 — Ouvrir, importer, enregistrer, exporter : les mêmes formats

- **Enregistrer sous** propose tous les formats que VectorDrive sait écrire — DXF, SVG, PDF, AI, EPS, HPGL, symbole SMB, images, et ceux des plugins — plus seulement VDZ et VND. Le fichier demandé reçoit tout ce que son format garde.
- **Compagnon pour tous les formats** : quand le format ne garde pas tout (réglage FAO, guides, textes modifiables, objets réglables, plaque, calques…), un fichier `.vdz` est écrit à côté, comme pour le VND : `piece.dxf` → `piece.dxf.vdz`. Le VND garde `piece.vdz`.
  - Il n'est écrit que s'il le faut : VectorDrive relit le fichier qu'il vient d'écrire et le compare au dessin. La barre d'état dit pourquoi il a été écrit.
  - À l'ouverture, il est relu. Si le fichier n'a pas changé, le dessin revient entier. S'il a été retouché dans un autre logiciel, c'est lui qui fait foi : seuls le réglage FAO, les guides et l'état des calques sont repris.
  - Ouvrir le compagnon ouvre le fichier qu'il accompagne.
- **Ctrl+S** réenregistre un fichier de travail dans son format, avec son compagnon. Un fichier reçu (sans compagnon) n'est jamais écrasé : Ctrl+S demande où enregistrer.
- **Importer** (et un fichier lâché sur le dessin) relit aussi le compagnon : les textes reviennent modifiables.
- **Exporter** ne change pas : la sélection (ou tout le dessin), sans compagnon.
- Le réglage « fichier .vdz compagnon » de F10 (si besoin, toujours, jamais) vaut pour tous les formats.
### v0.804.0 — IGES, EMF et WMF : écrits aussi

- **IGES** : VectorDrive ne faisait que le lire ; il l'écrit. Les courbes sont exactes — droites, arcs de cercle, courbes de Bézier —, en millimètres, un niveau IGES par calque. Relu, le dessin revient tel quel.
- **EMF et WMF** (dessins de Windows : Word, Excel, vieux logiciels de gravure) : écrits par Inkscape quand il est installé sur le poste, comme ils sont déjà lus. Sans Inkscape, le message dit quoi faire.
- Ces trois formats sont dans **Enregistrer sous** et dans **Exporter**.
- Restent lus seulement : STEP, STL, 3D XML, CATIA, GVT et modèles TypeEdit, CorelDRAW, Visio.
### v0.805.0 — BAT : filigrane, dessin en image, remarques à la ligne, dossier ouvert

- **Filigrane** : un texte répété en biais, clair, derrière le dessin — le nom de l'entreprise d'office, ou le texte de votre choix, dans la couleur du cartouche ou une autre. Il est à l'aperçu, à l'impression et dans le PDF.
- **PDF : dessin en image** : coché, les vues, les cotes et le filigrane sont écrits dans une image (300 dpi d'office, réglable). Le client voit le dessin, mais son tracé n'est plus dans le fichier : il ne peut pas le récupérer. Le cartouche, l'en-tête et la légende restent nets. Cocher le filigrane coche aussi cette case ; elle se décoche si vous voulez un PDF en tracés.
- **Remarques** : le texte passe à la ligne tout seul dans sa case du cartouche. Avant, une longue ligne en sortait, et seules six lignes étaient écrites. S'il y en a beaucoup, le corps diminue pour que tout tienne.
- **Dossier ouvert** : coché, le dossier du PDF s'ouvre une fois le BAT écrit, le fichier montré.
- Ces réglages sont dans le cadre « Filigrane et PDF », sous l'aperçu ; ils sont retenus d'un BAT au suivant.
### v0.806.0 — BAT : carnet de clients, préréglages, logo de tout format

- **Carnet de clients** : « Garder ce client » retient le nom du cartouche et le second logo. Le logo est **copié dans le carnet**, quel que soit son format : image (PNG, JPEG, BMP, TIFF, GIF, WebP…) ou dessin (SVG, PDF, AI, EPS, DXF, VND, symbole, HPGL, IGES, et CorelDRAW, EMF, WMF par Inkscape). Au BAT suivant, choisir le client dans la liste écrit son nom et pose son logo.
  - Le carnet est un dossier (F10 › BAT › « Carnet de clients : dossier ») : un dossier partagé sert à tous les postes. Vide, il est dans les données de VectorDrive.
- **Préréglages** : la mise en page, les couleurs, l'entreprise et son logo, le filigrane, le PDF en image… se gardent sous un nom (« Enregistrer… ») et se reprennent d'un clic. Le client et son logo n'en font pas partie : ils viennent du carnet.
- **Logo de tout format** : tout dessin que VectorDrive sait lire peut servir de logo, en tracés exacts. Avant, seuls neuf formats étaient acceptés.
### v0.807.0 — FAO : un ruban par machine

- **Machines** : un plugin déclare les machines de l'atelier — fraiseuses et lasers — et, pour chacune, le post-processeur qui lui convient le mieux. Le cœur de VectorDrive n'en connaît aucune : sans plugin, rien ne change.
- **Rubans FAO 2D et FAO 3D** : un groupe « Machine », avec un bouton par fraiseuse. Celui de la machine du dessin est enfoncé ; un clic en change. Les boutons et les panneaux propres à une machine n'apparaissent que pour elle.
- **Ruban « FAO laser »** : les lasers ont leur propre ruban, avec leurs machines, le panneau, le calcul, le post-traitement et le coupon d'essai. Il n'existe que si une machine laser est déclarée.
- **Palette de la FAO** : pour une fraiseuse, les parcours laser ne sont plus proposés ; pour un laser, seuls les siens le sont.
- **Post-processeurs en double** : une machine n'est proposée qu'une fois, sous son nom, dans le panneau FAO et dans F10 › FAO ; les fiches et les post-processeurs qui font double emploi ne sont plus listés. Un dessin réglé sur l'un d'eux reste lisible : il est reconnu comme étant de cette machine. Le choix de F10 reste celui des nouveaux dessins.
- Une machine qui n'a pas encore de post-processeur reste dans le ruban : un clic dit qu'elle est à configurer, le dessin garde la sienne.
### v0.808.0 — FAO : le nom des machines sur leurs boutons

- **Rubans FAO, groupe « Machine »** : chaque bouton porte le nom de sa machine, en texte. Avant, quand la place manquait, le ruban réduisait ces boutons à leur icône — la même pour toutes les machines : on ne savait plus laquelle choisir.
- Les boutons restent rangés par trois ; celui de la machine du dessin est enfoncé.
### v0.809.0 — Modes simple et expert

- **Simple | Expert** : un va-et-vient à côté de celui du 2D / 3D, en haut du ruban. Le **mode simple** ne garde que l'essentiel — ouvrir, enregistrer, imprimer, BAT, dessiner les formes courantes, écrire, aligner, les opérations de base, calculer et post-traiter en FAO, choisir la machine, les commandes des plugins. Le **mode expert** montre tout, comme avant ; c'est le mode d'office.
  - En mode simple, un groupe qui n'a plus de bouton disparaît, un onglet qui n'a plus de groupe aussi (Design 3D, Design STEP).
  - Les raccourcis, les menus du dessin et la recherche de commande donnent toujours toutes les commandes.
- **Clic droit sur un bouton du ruban** : « Montrer aussi en mode simple » ou « Réserver au mode expert ». Votre répartition est retenue. Pour un outil dont le clic droit ouvre déjà les réglages (formes, cote…), c'est Maj + clic droit.
- **Corrigé** : un bouton du ruban suit la visibilité de sa commande. Les boutons propres à une machine restaient affichés pour les autres machines.
### v0.810.0 — Disposition TypeEdit 13 : les machines dans l'onglet FAO

- **Ruban à la disposition de TypeEdit 13** : l'onglet FAO de TypeEdit commence par le groupe « Machine » — les fraiseuses, puis les lasers (cette disposition n'a qu'un onglet FAO). Avant, les machines n'y étaient que dans les menus de l'onglet « VectorDrive ».
- Les commandes qu'un plugin réserve à une machine y ont leurs groupes, montrés pour cette machine seulement, comme dans les rubans FAO de VectorDrive.
### v0.811.0 — STEP, STL et 3D XML : écrits aussi

- **Enregistrer sous** et **Exporter** proposent le STEP, le STL et le 3D XML : le dessin part **en volume**. Les formes fermées sont tirées de l'épaisseur de la plaque (3 mm quand elle n'en a pas), le dessus à Z 0 comme sur la machine ; un contour dans un autre est un trou, un contour dans ce trou une île. Les volumes de l'onglet 3D partent tels quels, les reliefs sur leur socle (STL et 3D XML).
- **STEP** : de vrais solides, que tout logiciel de CAO ouvre et modifie — un plan par segment droit, un **cylindre par arc de cercle** (un trou rond reste un trou rond), une surface exacte par courbe de Bézier ou arc d'ellipse. Des contours qui se croisent sont d'abord réunis.
- Le dessin lui-même (calques, outils, textes, réglages FAO) reste dans le compagnon `.vdz` écrit à côté par « Enregistrer sous » : rouvert dans VectorDrive, le fichier rend le dessin, pas seulement la vue de dessus de la pièce.
- La barre d'état dit ce qui est parti (« en volume : 2 volume(s), formes fermées tirées de 5 mm ») ; « Exporter » relit la pièce et en donne le nombre de triangles.
- Dans la liste des formats d'écriture, l'IGES ne s'appelle plus « IGES (vue de dessus) » : il s'écrit en courbes à plat.
- Le STEP a été ouvert dans un autre logiciel de CAO (solides fermés, volumes justes). Le 3D XML, écrit d'après le schéma publié par Dassault, n'a été relu que par VectorDrive : à essayer dans votre lecteur avant de compter dessus.
- Restent lus seulement : CATIA, GVT et modèles TypeEdit, CorelDRAW, Visio.
### v0.812.0 — Dessins LaserType et modèles TypeEdit écrits ; « Ouvrir » montre tous les formats

- **Dessin LaserType (.vnl)** : lu et écrit. C'est la même archive que le VND : VectorDrive le relit et le réécrit sans en changer un octet, et TypeEdit 13 ouvre ceux qu'il écrit. Ctrl+S le réenregistre à sa place, comme un VND, avec la même copie `.bak` avant la première écriture.
- **Modèle TypeEdit (.vnm)** : écrit aussi (« Enregistrer sous », « Exporter »). Un modèle ouvert ne s'écrase pas d'un Ctrl+S : « Enregistrer sous ».
- Comme pour le VND, le compagnon `.vdz` n'est écrit que pour ce que TypeEdit ne garde pas (textes modifiables, réglage FAO…), et un fichier lu en partie n'est jamais écrasé.
- **Ouvrir (Ctrl+O)** : le navigateur de VectorDrive montre maintenant **tous les dessins que VectorDrive lit**. Il n'en montrait que dix sortes : ni IGES, ni HPGL, ni images, ni STL, ni 3D XML, ni GVT, ni modèles, ni EMF n'y paraissaient — il fallait passer par la boîte du système. Quatre filtres en plus : TypeEdit et LaserType, Images, Pièces 3D, Autres dessins.
- Les fichiers qu'un autre logiciel lit pour VectorDrive (CorelDRAW, EMF, WMF, Visio par Inkscape ; CATIA par son convertisseur) sont listés sans vignette : ce logiciel n'est lancé qu'à l'ouverture.
- **STEP, STL, 3D XML** : les cotes du dessin ne partent plus en volume (leurs flèches et leurs chiffres étaient tirés comme des formes de la pièce) ; une forme posée deux fois au même endroit ne s'efface plus (elle compte une fois) ; un contour dont les bouts se rejoignent sans être marqué fermé — fréquent dans les dessins importés — fait partie de la pièce.
- Restent lus seulement : GVT (TypeEdit 14 et plus), CATIA, CorelDRAW, Visio.
### v0.813.0 — Plein écran : F12 boucle vraiment, boutons Réduire, Fenêtre et Fermer

- **F12** (ou Maj+F11), appuis successifs : la fenêtre → le plein écran → le plein écran avec la barre des tâches de Windows → la fenêtre. La boucle était écrite depuis la 0.780 mais **ne tournait pas sur un vrai poste** : après le premier appui, VectorDrive ne se savait plus en plein écran — chaque F12 refaisait le premier pas, et la fenêtre restait sans barre de titre, donc sans boutons.
- **Réduire, Fenêtre, Fermer** : en plein écran la barre de titre n'est plus là ; ses trois boutons paraissent tout à droite de la rangée des onglets, après Options et Aide, dans les deux pleins écrans. « Fenêtre » quitte le plein écran.
- La fenêtre reste active après chaque pas : l'appui suivant sur F12 lui arrive.
- Le plein écran suit l'écran s'il change de taille (résolution, barre des tâches déplacée).
### v0.814.0 — La fenêtre du BAT tient dans l'écran

- **BAT** : sur un écran 1920 × 1080, la fenêtre était plus haute que l'écran — **OK, Imprimer et Annuler étaient sous le bas de l'écran**, cachés. Ses réglages (cartouche, mise en page) sont maintenant dans un volet qui défile quand l'écran est plus petit qu'eux ; les boutons restent toujours visibles, sous le volet.
- Sur un écran plus haut, rien ne change : tous les réglages sont montrés, sans défilement.
### v0.815.0 — Plein écran : le liseré d'un pixel, pour la vue 3D

- En plein écran sur tout l'écran, la fenêtre retrouve le **liseré d'un pixel** qu'elle avait avant la 0.813 : sa surface fait un pixel de moins que l'écran de chaque côté, ce qui évite à la vue 3D de passer en plein écran exclusif (image qui clignote, menus et bulles mal affichés). La 0.813 le remplaçait par un débord d'un pixel en bas de l'écran, dont rien ne garantissait le même effet.
- Rien ne change pour F12 ni pour les boutons Réduire, Fenêtre et Fermer ; le plein écran avec la barre des tâches n'a pas de liseré (sa surface ne couvre pas l'écran).
### v0.816.0 — STEP, STL, 3D XML : les gros dessins s'écrivent vite

- Un dessin de 23 000 contours (motifs de points, textes serrés) mettait près de **quatre minutes** à s'écrire en STEP ; il en met **quatorze secondes**, pour le même fichier. La recherche des formes posées en double comparait chaque contour à tous ses voisins de même aire — dans un motif de points identiques, des dizaines de comparaisons par point.
- Les contours du dessin ne sont plus relevés deux fois quand il faut d'abord les réunir.
### v0.817.0 — BAT d'un dessin fait de milliers d'objets

- **Une cote par gravure** s'arrête à 40 gravures. Au-delà — un motif de points, un fond de hachures, un dessin non groupé — le dessin est coté comme un tout (cotes d'encombrement) et n'est plus chiffré objet par objet. Avant, chaque objet recevait ses deux cotes : 64 000 cotes sur un dessin de 32 000 objets, une page illisible.
- Le BAT de ce dessin s'écrit en **2 secondes** au lieu de 42.
### v0.818.0 — HPGL : plus d'escalier sur les tracés très serrés

- Un tracé dont les points sont plus rapprochés que le pas du traceur (0,025 mm) — dessin vectorisé, courbe importée en petits traits — partait **en escalier** : chaque point arrondi au pas, un tracé jusqu'à un tiers plus long que le vrai, et bien plus lourd. Les points inutiles sont retirés avant l'arrondi : une droite de 2 000 petits traits repart en une droite.
- Les tracés ordinaires (droites, arcs, courbes de Bézier, textes) s'écrivent comme avant, au point près.
### v0.819.0 — HPGL : les contours minuscules restent

- L'allégement des tracés serrés (0.818) ne fait pas disparaître les contours plus petits qu'un demi-pas du traceur (un point de quelques microns) : ils restent écrits, d'un trait d'un pas, comme toujours.
### v0.820.0 — Pièces maillées : vue de dessus plus rapide

- L'ouverture d'une pièce 3D maillée (STL, 3D XML, IGES ou STEP en surfaces) calcule sa vue de dessus environ un tiers plus vite : une pièce IGES de 100 000 triangles s'ouvre en 8 secondes au lieu de 11. Le dessin obtenu est le même.
### v0.821.0 — Export en image d'un grand dessin : plus de fausse alerte

- Exporter en image un dessin de grande taille (à partir de 70 cm de côté environ à 300 points par pouce) écrivait un fichier correct, mais VectorDrive annonçait ensuite « À vérifier : Image illisible ». La vérification lit maintenant la taille de l'image sans la décoder ; un fichier vraiment abîmé reste signalé.
### v0.822.0 — Impression à l'échelle : la feuille se tourne, et une réduction se dit

- **Imprimer la sélection à l'échelle 1** : la feuille se tourne selon la sélection. Une sélection en largeur (250 × 150 mm) tient sur un A4 couché ; avant, la feuille restait en hauteur et la sélection était réduite pour rien.
- Quand un dessin demandé à une échelle est plus grand que la feuille, il est réduit pour tenir (réglage d'office de F10 › Impression). Le message le dit maintenant — « réduit à 63 % pour tenir sur la feuille : ce n'est pas l'échelle demandée » — au lieu d'un simple « Envoyé à l'imprimante ». Pour garder l'échelle : l'impression sur plusieurs feuilles, dans F10 › Impression.
### v0.823.0 — Compagnon : la raison dite pour des contours colorés

- Enregistrer un dessin dont des contours ont leur couleur écrit un compagnon `.vdz` (la couleur y suit l'objet, quel que soit son outil). La barre d'état en donnait une raison fausse — « 3 objet(s) paramétrique(s) ou groupe(s) avec textes » ; elle dit maintenant « 3 contour(s) de couleur propre ».
### v0.824.0 — IGES : la couleur des contours

- **Écriture** : chaque contour part avec sa couleur — celle de son outil, ou la sienne (Édition › Presse-papiers › Couleur). Le rouge, le vert, le bleu, le jaune, le magenta, le cyan et le blanc prennent le numéro que l'IGES leur donne ; toute autre couleur a sa définition (entité 314). Le noir reste « sans couleur » : un dessin noir s'écrit comme avant.
- **Lecture** : les couleurs d'un IGES — les nôtres comme celles d'un fichier reçu — deviennent des outils, comme en DXF (une couleur = un outil ; F10 › Fichiers pour ne pas les reprendre). Une courbe composite sans couleur prend celle de ses morceaux, une sous-figure celle de son instance. Avant, tout revenait en noir.
- Quand un fichier porte à la fois des courbes de couleur et une pièce en surfaces, les hauteurs de la vue de dessus prennent les outils qui suivent ceux des couleurs.
- Vérifié dans TypeEdit 13 : il importe ces fichiers sans un message (lui-même n'en reprend pas les couleurs).
### v0.825.0 — DXF : les contours noirs visibles dans TypeEdit

- **Le défaut** : importé dans TypeEdit 13, un DXF de VectorDrive perdait ses contours noirs. Ils étaient là — sélectionnés, on les voyait — mais dessinés en blanc sur la page blanche. Le noir d'un DXF porte le numéro 7, « blanc ou noir selon le fond », et le filtre DXF que prend la visionneuse de TypeEdit le rend en blanc (il le fait aussi pour les DXF que TypeEdit exporte lui-même).
- **Corrigé** : le noir est écrit avec sa couleur vraie en plus du numéro 7. Vérifié dans TypeEdit 13 avec ses deux filtres DXF : noir visible, couleurs justes.
- **F10 › Fichiers › « DXF écrits : le noir aussi en couleur vraie »**, coché d'office. À décocher pour un logiciel à fond noir (AutoCAD…), où un noir vrai ne se verrait pas alors que le numéro 7 s'y adapte.
### v0.826.0 — EPS : les surfaces relues en contours fermés

- **Le défaut** : un EPS fait de surfaces remplies — ceux que TypeEdit exporte, les logos en Illustrator ancien — s'ouvrait sans un seul contour fermé. Chaque forme revenait « ouverte » : pas de poche ni de remplissage sans la raccorder d'abord. Les deux EPS d'exemple livrés avec TypeEdit 13 : 0 contour fermé sur 38, et 0 sur 64.
- **Corrigé** : un tracé rempli (f, F, b, B, fill, eofill) est une surface, ses contours sont fermés — c'est ce que fait le remplissage lui-même, et ce que le lecteur PDF faisait déjà. Les deux exemples : 38 sur 38 et 64 sur 64. Un tracé seulement tiré garde ses bouts ; un trait droit seul reste un trait.
### v0.827.0 — PDF et EPS : le tour d'une forme tiré jusqu'à son départ est fermé

- **Le défaut** : un PDF exporté par TypeEdit s'ouvrait avec toutes ses formes « ouvertes ». TypeEdit trace le tour de chaque forme jusqu'à son point de départ sans écrire la fermeture ; VectorDrive attendait cette fermeture.
- **Corrigé**, en PDF comme en EPS : un tracé tiré qui revient exactement à son point de départ est un contour fermé. Une ligne qui ne revient pas reste ouverte ; un simple aller-retour reste un trait.
- Un PDF qui ne contient qu'un bloc de texte vide (TypeEdit en écrit un) ne vaut plus la remarque « texte PDF non vectorisé ».
### v0.828.0 — STEP : les courbes d'un « fil de fer » sont lues

- **Le défaut** : un STEP qui ne porte que des courbes — ce que TypeEdit exporte pour un dessin, un jeu de B-splines sans une seule face — s'ouvrait vide. VectorDrive ne lisait d'un STEP que ses faces.
- **Corrigé** : les courbes libres d'un STEP (jeux de courbes « GEOMETRIC_CURVE_SET » et « GEOMETRIC_SET ») arrivent dans un calque « STEP courbes », en courbes exactes : B-splines, rationnelles ou non (un cercle reste fait d'arcs), polylignes, droites bornées, cercles entiers ou bornés, courbes composites. Les unités du fichier sont respectées, le placement de la pièce (autre face en haut, rotation, décalage) aussi. Une courbe d'un type non lu (ellipse…) est comptée dans le compte rendu.
- Une pièce en solides se lit comme avant ; si elle porte aussi un fil de fer, il s'ajoute dans son calque.
### v0.829.0 — DXF, SVG, IGES : la plaque dans le fichier, plus de compagnon pour elle

- Enregistrer un dessin en **DXF**, en **SVG** ou en **IGES** écrit maintenant sa plaque dans le fichier lui-même (taille, position, rayon des coins, épaisseur, marges, matière) ; le SVG garde en plus la place du dessin. À l'ouverture, le dessin revient avec sa plaque, à sa place.
- Conséquence : pour un dessin simple, **plus de fichier compagnon `.vdz`** à côté du DXF, du SVG ou de l'IGES — il n'y était écrit que pour la plaque (et, en SVG, pour la position). Le compagnon reste écrit quand il garde autre chose : réglage FAO, textes modifiables, objets réglables, couleurs propres.
- Où c'est écrit : une propriété du dessin en DXF (avec ses limites, que les logiciels de DAO connaissent), la section de départ en IGES, deux attributs de la racine en SVG. Les autres logiciels n'en sont pas gênés : vérifié dans TypeEdit 13 pour le DXF et l'IGES.
- PDF, EPS et HPGL gardent leur compagnon : ils ne rendent pas non plus les courbes telles quelles.
### v0.830.0 — SVG : la plaque notée ne vaut que pour la page d'origine

- Un SVG enregistré par VectorDrive porte sa plaque et la place du dessin (0.829.0). Inkscape garde cette note quand il réenregistre le fichier : la plaque et la position reviennent. Mais si la page y est recadrée (« ajuster la page au dessin »), la note devient fausse — VectorDrive posait alors la plaque d'origine sous un dessin déplacé.
- La note dit maintenant quelle page elle décrit, et n'est suivie que si le fichier a gardé cette page. Sinon le fichier se lit comme tout SVG, sans plaque inventée.
- Vérifié avec Inkscape 1.3 : il lit le SVG de VectorDrive à la bonne taille et à la bonne place, objet par objet.
### v0.831.0 — PDF : Inkscape ouvre les PDF de VectorDrive

- **Le défaut** : Inkscape 1.3 s'arrêtait en erreur (« Emergency save ») en ouvrant un PDF ou un fichier Illustrator écrit par VectorDrive sans image. Il manquait à la page son entrée « /Resources », que la norme PDF exige même vide. TypeEdit, les navigateurs et notre propre lecteur la toléraient, pas Inkscape.
- **Corrigé** : la page la porte toujours — dessins enregistrés en PDF ou en AI, et BAT. Vérifié avec Inkscape 1.3 : il ouvre le PDF, à la bonne taille et à la bonne place, et en rend les mêmes contours que VectorDrive.
### v0.832.0 — DXF : les courbes en arcs, pour les logiciels qui lisent mal les SPLINE

- **Le constat** : une courbe de Bézier part dans un DXF en SPLINE, exacte — AutoCAD et TypeEdit la relisent à 0,01 mm. LibreCAD, lui, ignore les nœuds des SPLINE : une courbe à plusieurs morceaux y sort déformée (sur le dessin d'essai, une vague haute de 23,7 mm y fait 32,5 mm ; jusqu'à 9 mm d'écart).
- **F10 › Fichiers › « DXF écrits : courbes »** : « En courbes exactes (SPLINE) », comme avant et d'office, ou « En arcs raccordés à 0,005 mm ». En arcs, le DXF ne contient que des droites et des arcs de cercle, un contour par entité : lu à 0,005 mm par LibreCAD comme par TypeEdit (ses deux filtres), 10 contours sur 10.
- En arcs, VectorDrive écrit le compagnon `.vdz` dès que le dessin a des courbes de Bézier : c'est lui qui les garde exactes à la réouverture.
### v0.833.0 — Listes déroulantes : la molette sans effet au survol

- Faire défiler un panneau de réglages changeait au passage la liste déroulante qui se trouvait sous le pointeur. La molette n'agit plus sur une liste déroulante qu'une fois celle-ci dépliée par un clic ; au survol, elle continue de faire défiler le panneau. Les champs de nombres gardent la molette.
### v0.834.0 — Lancement en plein écran, dernière fenêtre retenue

- **Au premier lancement, VectorDrive s'ouvre en plein écran** (F12 fait le tour : plein écran, plein écran avec la barre des tâches, fenêtre).
- **La dernière fenêtre est retenue**, pour tout nouveau lancement, y compris une fenêtre à part : plein écran, plein écran avec la barre des tâches, ou fenêtre à sa place et à sa taille (agrandie si elle l'était). Avant, la place d'une fenêtre n'était retrouvée qu'avec la session.
- **Quitter le plein écran rend la fenêtre d'avant**, à sa place et à sa taille, au lieu de toujours l'agrandir.
### v0.835.0 — Le plein écran tient

- **Le défaut** : après avoir choisi une machine, déplacé des panneaux ou changé de ruban, le plein écran — surtout celui qui garde la barre des tâches — « se cassait » : la fenêtre débordait de l'écran et F12 ne la remettait plus en place. La cause : les panneaux empilés à droite imposaient à la fenêtre une hauteur minimale plus grande que l'écran (874 px au départ, plus de 1 600 avec le panneau d'une machine sous Dimensions et Calques), et la fenêtre était agrandie de force.
- **Corrigé** : la fenêtre a sa propre taille minimale, petite — elle ne peut plus être agrandie de force au-delà de l'écran. Le panneau d'une machine se range en onglet à côté des Calques au lieu de s'empiler dessous, et prend la colonne quand sa machine est choisie (Dimensions passe en onglet à côté). Un plein écran qu'une mise en page déplace reprend sa place de lui-même.
### v0.836.0 — Plus d'échec silencieux : journal des erreurs, export qui dit quand rien n'est écrit

- **Journal des erreurs** : une erreur inattendue dans une commande ne laissait aucune trace dans la version installée (sans console) — la commande semblait ne rien faire. Elle est maintenant écrite, avec son détail, dans `erreurs.txt` (dossier des données de VectorDrive) et annoncée dans la barre d'état.
- **Exporter** : si l'écriture ne laisse aucun fichier, un message le dit (avant : rien). Un export en erreur garde son détail dans le journal.
### v0.837.0 — Fiche d'outil : ouvrir ou poser ses dessins DXF et STEP

- **Mes outils › fiche de l'outil** : sous la silhouette, les deux dessins de l'outil (DXF et STEP) ont chacun deux boutons. « Ouvrir » : le dessin s'ouvre dans un nouvel onglet, le dessin en cours reste dans le sien. « Poser au clic » : la fenêtre des outils se ferme, le dessin suit le pointeur sur le dessin en cours, un clic le pose (R : tourner de 90°, Échap : annuler).
- Les boutons sont grisés tant que l'outil n'a pas de dessin (« Dessins DXF + STEP » les fait) ou si le fichier n'est plus sur le disque. Pour un outil d'une bibliothèque en lecture seule, les dessins tout juste faits s'ouvrent et se posent aussi.
- **Interface en anglais** : les messages du journal des erreurs et de l'export sans fichier (0.836.0), et les deux réglages « DXF écrits » de F10 › Fichiers (0.825.0, 0.832.0), restaient en français ; ils sont traduits.
### v0.838.0 — FAO : opérations et parcours dans un seul tableau, outils repliés en bas

- **Un seul tableau** : chaque opération porte en tête de ligne l'**œil** de son parcours — ouvert (à la couleur du tracé) : parcours dessiné, simulé, écrit ; barré : caché ; rien : pas encore calculé. Un clic sur l'œil le montre ou le cache. La case à cocher de la ligne reste l'activation de l'opération.
- **La liste « Parcours »** ne paraît plus que si un parcours n'a pas d'opération (programme relu, parcours TypeEdit) : elle donne alors l'ordre d'écriture de tous les parcours, comme avant. Sinon elle laisse sa hauteur aux opérations.
- **Clic droit sur une opération** : « Afficher ou cacher le parcours », « Inverser le sens du parcours », « Retirer le parcours calculé ». « Enregistrer les parcours cochés au format TypeEdit » est aussi dans « Réglage… ».
- **Outils d'usinage** : la liste est tout en bas du panneau, repliée sous son bouton (« Outils d'usinage (3) ») ; un clic la déplie sur un tiers de la hauteur, et le choix est retenu.
- **Interface en anglais** : dix libellés et bulles de F10 (surbrillance de la sélection, délai avant déplacement, fichier compagnon, outils inconnus d'un programme lu, carnet de clients) restaient en français ; ils sont traduits.
### v0.839.0 — Un panneau dans sa propre fenêtre : réduire, agrandir, fermer, plein écran

- **Le constat** : un panneau détaché de la fenêtre principale n'a ni bouton « réduire » ni bouton « agrandir », et ne passe pas en plein écran — gênant pour un panneau qui demande de la place.
- **Une vraie fenêtre** : un panneau peut aller dans sa propre fenêtre, avec la barre de titre du système (réduire, agrandir, fermer) et sa place dans la barre des tâches. « ⛶ » (ou F11) la met en plein écran ; sa barre montre alors ses propres boutons réduire, agrandir et fermer, et Échap en sort.
- « ⚓ » remet le panneau dans la fenêtre principale. Fermer la fenêtre ferme le panneau : il rouvre la fois suivante là où il était — fenêtre ou panneau, plein écran, place. La fenêtre principale fermée, la fenêtre du panneau ne lui survit pas.
- Pour les plugins : `MainWindow.dock_as_window(panneau, clé)` rend le `DockAsWindow` du panneau (`ui/panel_window`) — `to_window`, `to_dock`, `toggle`, `open`.
### v0.840.0 — Exporter la sélection : le fichier est écrit

- **Le défaut** : « Exporter » avec une sélection n'écrivait aucun fichier, sans rien dire. Sans sélection, l'export du dessin entier marchait.
- **La cause** : une fenêtre de dialogue était libérée dès sa fermeture, à la première occasion. La boîte de fichier de Windows, ouverte juste après la fenêtre « Exporter », donnait cette occasion ; l'export relisait ensuite la case « La sélection seulement » d'une fenêtre qui n'existait plus. L'erreur était muette dans la version installée (depuis la 0.836.0 elle s'écrit dans le journal des erreurs).
- **Corrigé à deux endroits** : l'export lit ses choix avant d'ouvrir la boîte de fichier ; et, pour toutes les fenêtres, une fenêtre finie n'est plus libérée tant que le code qui l'a ouverte n'a pas rendu la main. D'autres commandes bâties de même — une fenêtre, puis une boîte de fichier, un message ou une progression, puis la lecture de la fenêtre — étaient exposées au même défaut.
- Vérifié avec la vraie boîte de fichier de Windows, en plein écran avec la barre des tâches : DXF, PDF et PNG de la sélection écrits et relus.
### v0.841.0 — Relecture des versions 0.833.0 à 0.840.0

Ces versions avaient été publiées sans relecture indépendante. Cette relecture a trouvé les défauts ci-dessous ; chacun a été vérifié par un essai qui échoue sur l'ancien code.

- **Panneau dans sa fenêtre** : un F12 ou une réduction de la fenêtre principale refermait la fenêtre du panneau et le rendait à un panneau ancré caché. Seule la fermeture de VectorDrive la referme maintenant (et elle rouvrira dans sa fenêtre).
- **Lancement en plein écran** : les panneaux reprennent la place qu'ils avaient dans la session (seul un lancement en fenêtre la leur rendait).
- **FAO, l'œil des opérations** : le réglage FAO était relu une fois par ligne à chaque rafraîchissement ; avec 60 opérations, un clic sur un œil prenait une demi-seconde. Il n'est plus relu qu'une fois.
- **FAO, ordre des parcours** : la liste des parcours reparaît quand leur ordre d'écriture, réglé à la main, n'est pas celui des opérations. Sinon cet ordre ne se voyait plus et ne se changeait plus.
- **Molette** : une liste déroulante survolée par la molette prenait encore le clavier ; la flèche suivante l'aurait changée. Un clic ou Tab le lui donnent.
- **Journal des erreurs** : une même erreur répétée, dans un dessin ou un geste de souris, n'est écrite qu'une fois de suite ; le journal raccourci ne coupe plus un caractère ; les erreurs des fils de calcul s'écrivent encore sur la sortie d'erreur quand il y en a une.
- **Fenêtres finies** : une fenêtre préparée deux fois pour sa libération n'est plus libérée trop tôt.
### v0.842.0 — Molette inversable, rectangle de sélection, pointeur, onglets et noms de calques

- **Molette** : « Inverser le zoom de la molette » (Options › Souris, F5) — la molette vers soi rapproche.
- **Rectangle de sélection** : bouton gauche tenu, zoomer à la molette (plusieurs fois, depuis plusieurs endroits) ne déplace plus son coin de départ : il reste au même point du dessin, et la sélection est celle du rectangle tiré dans le dessin.
- **Pointeur** : la double flèche montrée sur le coin d'une forme choisie ne reste plus après Suppr (ni après Échap, Ctrl+A ou toute sélection changée) ; sans sélection, le survol rend le pointeur de l'outil.
- **Calques en onglets** : un bouton « × » au bout de la barre des onglets la ferme ; l'option d'Options › Affichage (F10) les ouvre ou les ferme tout de suite ; Ctrl+Tab ne rouvre plus la barre (onglets fermés, il rend actif le calque suivant, en passant les calques cachés ou verrouillés).
- **Calques** : un double-clic sur le nom d'un calque le renomme, même s'il n'était pas encore actif ou s'il est verrouillé (le cadenas n'entre pas dans le nom). Seul le nom s'édite.
### v0.843.0 — Un cadre par objet choisi, accrochage actif d'office

- **Sélection de plusieurs objets** : chacun a son cadre en pointillé, en plus du cadre à poignées (un groupe a le sien, ses objets non ; au-delà de 400 objets, le cadre commun seul).
- **Accrochage actif d'office**, sur les nœuds et les intersections (et les guides) : plus la grille, qui aimantait chaque clic, ni les milieux et les centres (F3 pour les reprendre). Il est allumé une fois même si vous l'aviez laissé éteint ; éteint de nouveau dans Options › Général (« Accrochage actif au démarrage »), il le reste. Options › OK ne le rallume plus en cours de travail. « Nœuds et intersections » est le premier choix rapide (F3, Ctrl+D / Ctrl+F).
- **Au survol**, un petit cercle entoure le point accroché et un fil le relie au pointeur, aussi avec la flèche de sélection (le point qu'un glisser prendra) ; rien sur une poignée de la sélection, ni sur un très gros dessin (plus de 5 000 objets) avec la flèche.
- **Guides** : un guide tiré ne s'accroche plus à lui-même (il avançait par sauts quand l'accrochage aux guides était actif).
### v0.844.0 — Gamme : la reprise ne repasse plus à vide

- **Gamme à plusieurs outils** (faite dans VD ou importée de TypeEdit) : la reprise à la fraise est maintenant liée au parcours précédent. Elle ne garde que les morceaux de son parcours qui enlèvent encore de la matière après les lignes d'avant ; les autres sont retirés, et les remontées d'un angle à l'autre deviennent de courtes liaisons au fond quand rien ne gêne. Sur les gammes TypeEdit de mon poste, la coupe à vide de la reprise passe de 34 à 50 % de son parcours à 5 à 12 % (TypeEdit : 34 à 49 %), son parcours est 14 à 32 % plus court, pour la même pièce. Le cône de gamme ne reprenait déjà que ce que la fraise avait laissé : il reste tel quel (lié, il remontait plus souvent pour presque rien).
- **Modèles déjà importés de TypeEdit** : la reprise est liée aussi quand vous les appliquez, sans refaire l'import. Les modèles enregistrés à partir de cette version gardent votre choix (reprise déliée : déliée).
- **Distance entre passes** de chaque ligne de la gamme (celle de TypeEdit) : la reprise la suit, elle l'ignorait. Elle est dans la fiche de l'opération ; au plus 90 % du diamètre de l'outil (au-delà, des crêtes resteraient), négative : celle de l'outil.
- **Modèle appliqué à un document** qui a déjà un outil du même nom : l'outil n'est repris que s'il a aussi la même sorte et la même taille (le diamètre ; pour un cône, l'angle et la pointe). Avant, deux fiches TypeEdit du même nom pouvaient se confondre : la reprise prenait alors l'outil de l'ébauche et ne faisait rien.
- **Lier au parcours précédent** :
  - avec un **Z de départ** au-dessus de 0, les passes du haut ne sont plus retirées (l'outil prenait toute la hauteur d'un coup) et l'approche suit le dessus de la matière (l'outil descendait en rapide jusqu'à l'approche d'un dessus à 0, dans la matière) ;
  - sur une **grande plaque**, la matière est suivie au pas fin autour de l'outil (par tuiles), au lieu d'une seule carte pour toute la plaque qui devenait grossière (« tri approché ») ; si la plaque est trop grande même ainsi, le parcours est gardé en entier, avec un avertissement, plutôt que de laisser de la matière.
### v0.845.0 — VND : les textes restent modifiables dans TypeEdit

- **Enregistrer en VND** écrit maintenant les textes en textes TypeEdit modifiables, sans option à cocher : rouvert dans TypeEdit, un texte se modifie comme les siens (avant, l'option était décochée d'office et le texte arrivait en courbes). L'option est cochée une fois même si vous l'aviez laissée décochée ; décochée de nouveau (Options › Fichiers), elle le reste. L'**export** (Maj+E) aussi : la case est cochée d'office, dans le dernier choix et dans les modèles d'export enregistrés avant ; ceux enregistrés à partir de cette version gardent votre choix.
- **Police que TypeEdit ne trouverait pas** : le texte reste en courbes — police intégrée à VectorDrive (VD Géo, VD Trait…), police SVG, police ajoutée dans les dossiers de VectorDrive mais pas installée dans Windows. TypeEdit n'ouvre un fichier qu'une fois toutes ses polices installées : un seul texte de ce genre l'aurait bloqué. Les polices de TypeEdit (lues par un plugin) et celles installées dans Windows restent modifiables.
- **Compte rendu de l'enregistrement** (barre d'état) : combien de textes sont modifiables, combien sont en courbes et pourquoi (police, mise en forme que TypeEdit ne garde pas comme le justifié ou l'italique, texte sur courbe, étiré ou en miroir).
- **Symboles** (option des textes modifiables, toujours à cocher) : mêmes règles, la mise en forme que TypeEdit ne garde pas et les polices qu'il ne trouve pas partent en courbes (le texte gardait ses lettres mais perdait sa mise en forme).
- **VND rouvert, texte changé, enregistré par-dessus** : TypeEdit montre le nouveau texte. Quand le dessin gardait la même structure, seule la position du texte était reportée et TypeEdit montrait l'ancien texte (l'ancienne taille, l'ancien angle) ; caché jusqu'ici, ce défaut serait devenu courant avec les textes modifiables d'office. Un VND inchangé est toujours réécrit à l'octet près.
- **Traitement par lots** vers le VND : il suit le même réglage (il écrivait les textes en courbes).
- Vérifié dans TypeEdit 13 : un VND écrit avec les réglages d'office s'ouvre sans question ; « Arial modifiable » et un texte Times centré sur deux lignes y sont des objets texte, le texte en VD Géo un objet courbe à son dessin. Écrit en texte modifiable comme avant cette version, ce texte VD Géo faisait demander à TypeEdit de remplacer la police inconnue par Arial : la gravure aurait changé de police. Un VND rouvert, texte changé puis réenregistré, montre le nouveau texte.
### v0.846.0 — Police absente à l'ouverture, polices installées sans redémarrer

- **Dessin TypeEdit ouvert dont une police manque sur le poste** : ses textes passent en **VD Géo** dans une **copie de leur calque**, placée juste devant lui et active ; le calque d'origine est caché et reste tel quel (ses textes gardent leur police). TypeEdit, lui, fait fermer, installer la police et relancer. Les lettres en VD Géo sont posées dans les boîtes de caractères de TypeEdit (même place, même longueur de ligne) et l'interlettrage est recalé sur VD Géo : un texte modifié ensuite garde sa largeur. La barre d'état dit combien de textes et quelles polices ; une lettre dans une police absente (réglage par lettre) passe aussi en VD Géo. La copie est faite d'objets neufs : réécrit en VND, le calque d'origine garde ses textes TypeEdit tels quels, rien n'est en double ; les opérations FAO qui usinaient le calque usinent sa copie (un calque caché ne s'usine pas). Réenregistré et rouvert, avec ou sans son compagnon, le dessin garde ses deux calques, sans nouvelle copie, et un seul des deux est montré : la copie tant que la police manque, l'original quand elle est installée (rien n'est usiné deux fois). Un texte relu avec son tracé (VDZ, compagnon) se montre tel qu'il a été écrit : il reste dans son calque ; un calque de surface (FAO sur une face) garde aussi ses textes, en police de remplacement. Réglage : Options › Fichiers, « Dessin ouvert dont une police manque sur le poste » (ou la police de remplacement dans le calque, comme avant).
- **Police installée VectorDrive ouvert** : plus besoin de redémarrer. Au retour dans la fenêtre (après l'installation dans Windows) et à l'ouverture d'une liste de polices, VectorDrive regarde si des polices sont arrivées (un simple coup d'œil aux dossiers de polices de Windows et aux polices ajoutées : rien de lent, même avec des dossiers de polices sur le réseau) ; les textes qui les attendaient (leur police ou celle d'une de leurs lettres) se redessinent dans leur police, dans tous les onglets (calques cachés compris : le calque d'origine se montre alors juste, la copie peut être retirée) ; un texte TypeEdit se redessine dans ses boîtes de caractères, à sa place. Annuler (Ctrl+Z) ne ramène pas l'ancien tracé. La barre d'état les nomme. Les polices des dossiers ajoutés dans les Options ne sont pas annoncées comme installées au lancement.
- **Listes de polices** : elles montrent aussi les polices TrueType / OpenType installées depuis le lancement de VectorDrive, et celles d'un dossier de polices ajouté (Options).
- **VND et son compagnon** : un dessin dont le premier calque est caché ou vide, enregistré en VND puis rouvert, retrouve chaque calque avec son état (caché, verrouillé) et ses objets VectorDrive, même quand deux calques portent le même nom. L'écriture du VND passe devant le premier calque qui a quelque chose à montrer (TypeEdit n'affiche que celui-là à l'ouverture) et le compagnon était relu rang pour rang : l'état et les objets d'un calque pouvaient passer à son voisin.
### v0.847.0 — Décaler : les décalages qui se croisent sont réunis

- **Décaler** (A) : les contours décalés qui se chevauchent — lettres voisines, formes proches — sont **réunis d'office** en un seul, à chaque distance (plusieurs décalages : chaque rang à part) et pour un même outil (deux outils, deux usinages). Plus de matière enlevée deux fois ni de contours qui se croisent à reprendre à la main. La réunion se fait morceau par morceau : seules les lettres d'un texte qui croisent une autre forme sont réunies avec elle, les autres restent telles quelles. L'un dans l'autre — une lettre dans son cadre, une forme dans le trou d'une autre —, ils restent séparés ; ceux qui se touchent seulement aussi. Case « Réunir les décalages qui se croisent » dans la fenêtre, cochée d'office et retenue. La barre d'état dit combien de contours ont été réunis ; le fil de calcul montre l'avancement.
### v0.848.0 — Plusieurs textes sélectionnés : un formulaire commun

- **Double-clic sur un des textes sélectionnés** (deux au moins) : un **formulaire commun** — police, hauteur des capitales, largeur des lettres, inclinaison, interlettrage, interligne, espacement des lettres, alignement, largeur imposée et ajustement. Chaque champ montre la valeur commune ; quand elle diffère d'un texte à l'autre, celle du premier, **en gris**. Seuls les champs modifiés s'appliquent, **à tous** les textes (comme depuis l'onglet Mise en forme), les autres restent ceux de chaque texte — chacun garde son contenu. Un seul pas d'annulation. Un texte seul se modifie comme avant ; pour taper dans un des textes d'une sélection, cliquez-le seul d'abord.
### v0.849.0 — BAT : filigrane réglable, logo possible

- **Filigrane du BAT** (cadre « Filigrane et PDF ») : son **motif** — le texte, ou **un logo** (celui de l'en-tête, ou un autre fichier : image ou dessin, tout entier dans la couleur du filigrane ; le blanc d'une image disparaît, l'image reste transparente dans le PDF) ; sa **taille** (hauteur du texte, le logo le double), son **angle**, l'**écart** entre deux motifs, son **intensité** (de très clair à la couleur même) ; **répété en quinconce** ou **un seul au milieu** (réduit s'il ne tient pas). Les réglages d'office donnent le filigrane d'avant ; ils sont gardés comme les autres, préréglages compris. Un logo image est écrit une seule fois dans le PDF, réduit à une taille suffisante : le PDF reste léger. Un logo dessiné passe tout entier dans la couleur du filigrane, ses parties blanches comprises.
### v0.850.0 — Ctrl+P : la fenêtre Imprimer

- **Ctrl+P ouvre la fenêtre Imprimer** (le BAT PDF passe à **Ctrl+Maj+P**) : **quoi** — la sélection, la plaque et ce qu'elle contient (le dessin coupé au bord de la plaque), des calques (cochés dans la liste), tout le dessin, ou la page BAT ; **vers** l'imprimante ou un **fichier PDF** ; la **feuille** — A6, A5, A4, A3, A2, A1, Letter, ou en PDF la **taille réelle** du dessin (la feuille à sa mesure, marges comprises, à 1:1) ; l'**échelle** — ajustée à la feuille à l'**échelle conseillée** (la plus grande échelle normalisée qui tient : 1:1, 1:2, 1:5, 2:1…), ajustée tout juste, 1:1, ou un **zoom au choix** ; orientation, marge, plaque en pointillés. L'échelle obtenue et la feuille sont montrées avant d'imprimer — c'est celle qui sort (la mosaïque des Options ne s'en mêle pas) ; les choix sont retenus, et la première fois la fenêtre reprend ce que vous aviez réglé dans Options › Impression (feuille, orientation, marge, échelle ; « Imprimer (Ctrl+P), la première fois » : la sélection sinon la plaque, tout le dessin ou la page BAT). L'imprimante passe par l'aperçu, comme avant. Un PDF déjà ouvert dans un lecteur est écrit à côté (« nom (2).pdf »), et un PDF qui n'a pas pu être écrit est signalé. Options › Impression propose aussi A6, A2 et A1.
### v0.851.0 — La liste des polices : haute comme la fenêtre, recherche, filtres, favorites

- **La liste des polices** (onglet Mise en forme, fenêtres de texte, table des caractères…) s'ouvre **jusqu'au bas de la fenêtre** (au-dessus de la liste déroulante, jusqu'en haut, si la place manque en dessous — jamais sur elle : un second clic sur la flèche la referme ; une petite fenêtre de réglages posée sur la fenêtre principale en prend la hauteur). En tête, une **recherche** : un ou plusieurs mots, sans casse ni accents (« geo vd » trouve VD Géo) ; **↑ ↓ Page** parcourent la liste, **Entrée** choisit, **Échap** ferme ; la ligne sous la souris est surlignée. Des **filtres** : toutes, favorites, intégrées, lues par un plugin, SVG, système (le dernier choisi est repris, sauf s'il ne montre pas la police en cours ; ceux sans police sont grisés). Un clic sur l'**étoile** d'une police en fait une **favorite** : gardée, elle vient en tête de la liste ; un autre clic la retire. Les polices sont rangées par catégorie, chacune du système montrée dans son propre dessin. Choisir une police fait comme avant, et pendant la saisie d'un texte la frappe continue dans le dessin.
### v0.852.0 — Reconnaissance de police : les polices les plus proches des lettres en courbes

- **Liste des polices › « Reconnaître la sélection »** : sélectionnez dans le dessin des lettres mises en courbes (un texte converti, un DXF, un logo…), ouvrez la liste des polices et cliquez le bouton : les polices du poste **les plus proches** viennent en tête de la liste, la plus proche d'abord, chacune avec sa **proximité** en pour cent ; un clic (ou Entrée) en choisit une. **5 propositions** d'office, nombre réglable à côté du bouton (gardé ; aussi dans Options › Dessin). La recherche se fait parmi les polices du **filtre choisi** (toutes, favorites, système…). Les lettres sont comparées une à une, trous, points et accents compris, à celles de chaque police (traits ouverts d'une police monotrait compris) ; elles sont attendues sur une ligne à peu près horizontale, détachées les unes des autres ; un cadre autour du texte, un soulignement ou un trait qui barre plusieurs lettres sont laissés de côté. La première fois, la forme des lettres de chaque police est relevée (moins d'une demi-minute pour 300 polices, la liste reste utilisable, l'avancement est montré, le bouton devient « Arrêter ») puis gardée : ensuite, c'est immédiat. Deux polices au dessin identique (Verdana et MS Reference Sans Serif, par exemple) ne prennent qu'une place.
- Pas encore : seule la graisse de la liste est comparée (pas le gras ni l'italique d'une même famille), et des lettres inclinées ou élargies dans VectorDrive ne sont pas redressées avant la comparaison.
### v0.853.0 — FAO : la plongée angulaire en haut du formulaire

- **Formulaire d'opération** : sous l'outil, un **bouton « Plongée angulaire »** à icône — enfoncé, l'outil entre dans la matière en rampe (l'icône montre la descente en biais) ; relâché, il plonge droit — et l'**angle** de la rampe à côté (actif bouton enfoncé, ou quand les passes sont connectées : elles descendent en rampe à cet angle ; 0 : 5°). La distance maxi de la rampe reste dans « Entrées et liaisons ».
- **Corrigé** : depuis la v0.728 (round 871), « Entrée en rampe » et son angle n'étaient plus montrés que pour la gravure en V : on ne pouvait plus les changer pour un contour, une poche, une gravure… (le réglage d'office de F10 s'appliquait toujours). Ils sont de nouveau montrés pour les stratégies dont le parcours entre en rampe : gravure, contour, poche, reprise, découpe 3D, chanfrein d'arête, gravure 2,5D, ébauche 3D, gamme (pas pour le perçage, le chanfrein de trou, le surfaçage, le laser, le vinyle ni les instructions, qui plongent droit).
### v0.854.0 — FAO : les sections du formulaire en cases, rangées à votre guise

- **Formulaires d'opération et d'outil** : chaque section (Opération, Profondeurs, Vitesses, Évidage…) est une **case** que l'on **glisse par son titre** vers une autre place ou une autre colonne (un trait montre où elle ira ; la colonne défile près de ses bords). **Clic droit sur un titre** : de 1 à 4 colonnes (les cases réparties sans colonne vide ; à 3 ou 4 colonnes, un champ trop large défile), ou la disposition d'origine. La disposition est **gardée** (une pour les opérations, une pour les outils) et reprise à la prochaine ouverture ; une section nouvelle vient en bas de la colonne la plus courte, une section absente cette fois (celle d'un plugin) garde sa place. Les sections sans champ pour la stratégie choisie restent masquées.
### v0.855.0 — FAO : la matière qui reste entre les opérations

- **Simulation** : « **Matière après** » une opération choisie dans la liste (dans l'ordre d'usinage ; « Toutes les opérations » : la simulation complète, comme avant). L'image montre la matière laissée aux opérations suivantes, et **en vert ce que l'opération choisie enlève** — seulement ce que les opérations d'avant n'avaient pas déjà enlevé : une finition qui repasse là où l'ébauche est déjà descendue n'enlève rien. Une opération coupée en deux endroits de la liste compte en entier. Le volume enlevé jusque-là et la part de cette opération sont affichés ; « Cette opération » montre ou cache le vert ; « Hors matière » montre le chemin de l'outil jusqu'à cette opération ; « Poser en relief » pose la matière de cet état (une fois par état). Passer d'une opération à la suivante ne simule que celle-ci. Les alertes (porte-outil, rapides dans la matière) restent celles de tout le programme. Le brut de la pièce 3D, s'il est défini, est le point de départ.
- **Clic droit sur une opération** : « **Matière restante après cette opération…** » ouvre la simulation du programme — les parcours cochés des opérations actives de la même prise, et ceux de cette opération même décochés —, arrêtée après elle.
### v0.856.0 — Texte : la sélection dans la saisie

- **Double clic : le mot ; triple clic : la ligne ; quadruple clic : tout le texte**, dans un texte qui s'écrit dans le dessin (outil Texte, ou double clic sur un texte avec l'outil Sélection : le mot double-cliqué est sélectionné d'emblée). Le double clic prend le mot du caractère cliqué ; sur une espace ou une ponctuation, elle seule.
- **Étendre** : glisser la souris, Maj+clic, Maj+flèches, Maj+Origine, Maj+Fin. Les flèches sans Maj posent le curseur au début ou à la fin de la sélection.
- **La frappe, Coller, Suppr et Retour arrière** remplacent ou retirent la sélection ; **Ctrl+C** (Ctrl+Inser) la copie, **Ctrl+X** (Maj+Suppr) la coupe, comme Copier et Couper du menu. Pendant la saisie, ces touches ne copient ni ne coupent jamais l'objet texte lui-même.
- La sélection se voit ligne par ligne, saut de ligne compris. Un clic dans la boîte du texte (creux d'une lettre, espace, bout de ligne) reste dans ce texte au lieu de le finir. Un texte changé sans la frappe (Rechercher / remplacer) perd sa sélection plutôt que de la décaler.
### v0.857.0 — Trois réponses : symboles en texte modifiable, police absente, ordre d'impression

- **Symboles créés : textes TypeEdit modifiables d'office** (« Créer un symbole », « Ajouter la sélection » de la Bibliothèque, export en SMB). Le réglage (F10 › Fichiers) est coché une fois, même s'il avait été laissé décoché ; décoché de nouveau, il le reste. Il n'est plus « expérimental ». Mêmes règles que pour un VND : un texte dans une police que TypeEdit n'a pas reste en courbes.
- **Police absente, VND réenregistré** : la copie en VD Géo est maintenant écrite derrière son calque d'origine, cachée, et l'original visible. TypeEdit, qui n'ouvre que le premier plan, ouvre donc sur le calque d'origine et propose d'installer ou de remplacer la police. Vérifié dans TypeEdit 13 : « Police de caractères inconnue… Remplacée par Arial », puis le plan d'origine. VectorDrive, lui, remontre la copie tant que la police manque, et l'original dès qu'elle est installée, avec ou sans le fichier compagnon.
- **Imprimer** : la liste propose dans l'ordre la sélection, la page BAT, la plaque, tout le dessin, puis des calques ; le réglage de F10 suit le même ordre.
### v0.858.0 — Panneaux : deux colonnes, mêmes boutons partout

- **Chaque panneau a la même barre** : son nom, puis **plein écran translucide** (⛶), **détacher** (⧉) et **fermer** (✕). Le plein écran translucide, réservé jusqu'ici au panneau FAO, vaut pour tous les panneaux (Calques, Bibliothèque, Dimensions, ceux des plugins).
- **Clic droit sur la barre ou sur l'onglet d'un panneau** : les mêmes fonctions, plus **Colonne de gauche** et **Colonne de droite**. Un panneau envoyé dans une colonne s'y range en onglet avec ceux qui y sont ; sa colonne est retenue. La palette des parcours peut aller à droite, les opérations à gauche.
- **Deux boutons en haut à droite, après Simple / Expert** : montrer ou cacher la colonne de gauche, la colonne de droite. Les panneaux cachés ainsi reviennent ensemble, les mêmes onglets devant.
- **Un clic sur l'onglet CAD range les panneaux FAO ; un clic sur un onglet FAO les rétablit** (F10 › FAO pour s'en passer). Seuls les clics comptent : un onglet qui change de lui-même (outil Texte, bascule 2D / 3D) ne range rien.
- Un panneau détaché se déplace par sa barre et se redimensionne par la poignée de son coin bas droit. Un panneau détaché mis en plein écran revient détaché, à sa place.
### v0.859.0 — Panneau FAO épuré : un bouton « Parcours 3D »

- **Un seul bouton, « Parcours 3D »** : il calcule les parcours (ou les refait si le dessin a changé) et montre en 3D, dans le calque Trajectoires, à part du dessin, ceux des **opérations choisies dans la liste** — aucune ligne choisie : toutes les opérations actives. Les autres sont cachés (leur œil est fermé), donc hors du programme.
- **Un programme partiel ne s'écrit pas sans qu'on le sache** : le panneau affiche « N opération(s) active(s) cachée(s) : hors du programme », et le compte rendu d'écriture du programme le redit avec leurs noms.
- **Partis du panneau** : la liste « toutes les opérations / seulement les objets sélectionnés », les boutons Calculer, Simuler, 2D et 3D, « Ne plus afficher les parcours », « Parcours TypeEdit… », détacher et plein écran. Tout reste dans le ruban FAO ; détacher et plein écran translucide sont dans la barre du panneau.
- Les lignes choisies ne valent que pour leur dessin : changer d'onglet de dessin les oublie.
### v0.860.0 — Le programme machine dans sa fenêtre

- **Le bouton « Post-traiter… » du panneau FAO devient le bouton « Programme »**, à l'icône de machine colorée. Il ouvre la fenêtre **Programme machine** : le programme que la machine du dessin recevrait pour les parcours montrés, **coloré** (mots G et M, outils, axes, avances, nombres, commentaires ; HPGL et SimPL compris).
- **En direct ou à la demande** : coché, le programme suit le panneau FAO et le dessin (opérations, parcours montrés ou cachés, machine) ; décoché, il attend « Mettre à jour », qui refait aussi les parcours si le dessin a changé. Un très long programme attend toujours « Mettre à jour ».
- **La machine se choisit dans la fenêtre** ; **l'opération choisie dans le panneau FAO est retrouvée** dans le programme, surlignée et amenée à l'écran, dans son fichier s'il y en a plusieurs.
- **Ce qui est montré est ce qui sera écrit** : les mêmes fichiers, le même encodage. Des opérations actives cachées sont signalées, avec un bouton « Tout montrer ». « Copier », et « Enregistrer… » pour écrire le fichier (le post-traitement de toujours, avec ses contrôles).
- **Une fenêtre comme les autres panneaux** : détachée d'office ; par sa barre, elle se range dans une colonne ou couvre le dessin en **plein écran translucide** — à sa place quand l'opacité est au plus haut.
### v0.861.0 — Formulaire de parcours : l'outil et les vitesses en haut

- **L'ordre demandé** : en haut **Outil** (l'outil, l'outil de référence, la plongée angulaire) et **Vitesses** ; dessous **Opération** et **Entrées et liaisons** ; puis **Particulier** et **Profondeurs** ; puis le reste.
- **Multicopie, Enroulement et Autres** sont tout en bas, et **seulement en mode expert** ; en mode simple ils ne paraissent que si l'opération s'en sert déjà.
- Les cases se rangent toujours à la souris. La disposition gardée avant cette version n'est pas reprise : le nouvel ordre s'applique une fois, puis vos changements sont retenus.
### v0.862.0 — Bibliothèque : les couleurs gardées, le format au choix

- **Un symbole écrit par VectorDrive garde ses couleurs** : l'outil de chaque objet (déjà), et maintenant **sa couleur propre et son remplissage**, qui étaient perdus en le reposant. Ses courbes sont écrites **à la couleur de leur outil** (elles étaient toutes écrites en noir).
- **Format des symboles créés** (F10 › Fichiers) : **SMB** (TypeEdit), **DXF**, **SMB et DXF**, ou **VDZ** (VectorDrive : tout est gardé). Il vaut pour « Créer un symbole » et pour « Ajouter la sélection » de la Bibliothèque, qui lit ces formats. En « SMB et DXF », les deux fichiers portent le même nom.
- Les symboles déjà écrits se lisent comme avant ; un symbole écrit par cette version se lit aussi avec les précédentes (sans la couleur propre ni le remplissage).
### v0.863.0 — Reconnaître une police depuis une capture d'écran

- **Reconnaître une police…** (ruban du texte, à côté de la police et de « Caractères » ; aussi CAD › Texte ; présent en mode simple) : une fenêtre compare des lettres aux polices de la liste des polices et montre les plus proches, avec leur pourcentage. Les lettres viennent **de la dernière capture d'écran** (d'office : le dossier des captures de Windows), **de l'image du presse-papiers**, **d'un fichier image** au choix, ou des **lettres en courbes sélectionnées** dans le dessin (groupes compris ; un texte sélectionné n'en est pas : sa police est connue).
- L'image doit montrer un texte net, sur fond uni, cadré au plus près : l'écriture claire sur fond sombre et les images sans fond sont lues aussi, les poussières sont écartées ; d'une capture très chargée, seules les plus grandes formes sont gardées. Une image illisible ou trop détaillée (photo) est dite.
- **Double clic** sur une police (ou « Appliquer ») : elle va aux textes sélectionnés (un pas d'annulation) ; sans texte sélectionné, elle devient celle des prochains textes et la barre de texte la montre.
- **La première fois est expliquée** : VectorDrive dessine les lettres de chaque police installée pour les comparer aux vôtres, ce qui prend de quelques secondes à une minute ; ce dessin est gardé, les fois suivantes sont presque immédiates. L'avancement est affiché, « Arrêter » interrompt.
### v0.864.0 — Défaire et Refaire montrent la liste des modifications

- **Défaire** et **Refaire** (Ctrl+Z, Ctrl+Y — Ctrl+E ou Ctrl+A selon le jeu de raccourcis) montrent quelques secondes, en haut à gauche du plan de travail, **la suite des modifications** : celle où l'on est en gras, précédée de ▶, les modifications défaites en grisé.
- **Un clic sur une ligne revient à cette étape** — en arrière comme en avant ; « Début de l'historique » revient avant la plus ancienne modification gardée. La liste ne prend ni le clavier ni les clics du dessin : on continue à défaire et refaire, elle suit ; elle suit aussi une nouvelle modification, et s'efface quand on change de dessin.
- Elle s'efface seule après trois secondes, et reste tant que la souris est dessus. Une longue suite montre douze lignes autour de l'étape courante (moins quand la place manque). En vue 3D elle se montre aussi.
- **F10 › Général › « Défaire et Refaire montrent la liste des modifications »** : à décocher pour s'en passer. « Défaire plusieurs… » et « Refaire plusieurs… » restent.
### v0.865.0 — La surépaisseur dit ce qu'elle est : XY ou 3D

- Le champ « Surépaisseur » du formulaire d'un parcours n'a pas le même sens partout ; son libellé le dit maintenant, d'après le parcours choisi :
  - **Surépaisseur XY : le long des flancs** — contour, poche, reprise, découpe 3D, gravure en V. Le fond est usiné à la profondeur demandée : rien n'est laissé en Z.
  - **Surépaisseur 3D : en XY et en Z** — relief, surface 3D, ébauche 3D, reprise 3D, niveaux 3D, finition 2,5D en ébauche : la matière est laissée tout autour de la surface.
  - **Largeur du chanfrein** — ébavurage des trous, où ce champ règle la largeur du chanfrein.
  - En **finition 2,5D** (ébauche), la surépaisseur 3D est laissée tout autour de la surface et le « décalage en XY le long des flancs » s'y ajoute.
- La fenêtre de la **gamme multi-outils** parle de « Surépaisseur XY laissée pour la finition », celle de la **gamme relief** de « Surépaisseur 3D laissée pour la finition : en XY et en Z » ; le tableau de l'**usinage 3D automatique** d'une colonne « Surépaisseur 3D ».
- Aucun calcul ne change : les parcours sont les mêmes.
### v0.866.0 — Modèles de parcours : une liste à colonnes

- La liste déroulante **Modèle** du formulaire d'un parcours se déroule en **tableau** : nom, dossier, outil, diamètre, profondeur, passe en Z, avance, puissance du laser (colonne à montrer), origine (fourni, à moi), description.
- **Filtre** à la frappe, en haut de la liste : tous les mots tapés, sans casse ni accents, dans toutes les colonnes (« laiton plaque », le nom d'un outil…) ; le point vaut la virgule (« 0.5 » trouve « 0,5 ») ; **« colonne:valeur »** cherche dans une seule colonne (« outil:cyl », « prof:10 »). Entrée prend le premier modèle montré ; les flèches vont dans la liste, la frappe revient au filtre, ↑ sur la première ligne aussi.
- **Tri** d'un clic sur un en-tête, les nombres comme des nombres, les cases vides toujours en bas. Les **colonnes** se déplacent à la souris et se montrent ou se cachent par le clic droit sur l'en-tête, qui propose aussi « Colonnes par défaut » ; la liste se redimensionne par son coin.
- « (réglages ci-dessous) » reste au bas de la liste : sans modèle, les réglages du formulaire.
- Tri, ordre et largeur des colonnes, colonnes montrées et taille donnée à la liste sont retenus.
### v0.867.0 — La valeur de l'outil dans le champ ; profondeurs avant entrées et liaisons

- Dans le formulaire d'un parcours, un champ laissé à 0 prend la valeur de l'outil : **il la montre maintenant**, avec son unité — « 600 mm/min (outil) » pour l'avance et la plongée, « 18000 tr/min (outil) » pour la broche, « 0,3 mm (outil) » pour la passe en Z, « ≈ 1 mm (50 % du Ø de l'outil) » pour la distance entre passes d'une fraise droite — au lieu de « celle de l'outil ». Pour un outil conique ou boule, la distance entre passes dit « d'après l'outil et le parcours » : chaque stratégie la calcule à sa façon. Une valeur que l'outil n'a pas est dite « non réglée dans l'outil ». Un autre outil choisi : les valeurs suivent. Une valeur tapée reste celle du parcours ; une distance entre passes négative venue d'une gamme est gardée.
- La case **Profondeurs** passe au-dessus d'**Entrées et liaisons** dans la disposition d'origine du formulaire ; une disposition déjà réglée les échange aussi, une fois (ensuite, elle reste comme on la range).
### v0.868.0 — Poche entière : la finition à toutes les cotes là où l'ébauche n'est pas passée (option)

- Nouvelle case dans le formulaire de la **poche**, sous « Passe de finition » : **« Finition à toutes les cotes là où l'ébauche n'a pas ouvert la matière »**. Une poche entière avec surépaisseur laisse des endroits où seule la passe de finition entre : une rainure plus étroite que l'outil et deux surépaisseurs, la pointe d'un coin aigu. D'office, la finition y descend au fond d'un coup, sur toute la profondeur. Case cochée, elle y passe **à chaque cote**, comme un contour, sur ce tronçon seulement ; le reste du tour reste au fond. C'est la règle que « Seulement le reste » applique déjà.
- Vaut pour la poche concentrique et le balayage. Outil conique ou boule : au fond seulement (son flanc ouvre la matière à chaque passe).
- Case décochée (d'office) : les parcours ne changent pas.
### v0.869.0 — Les parcours sans opération dans le tableau des opérations

- Un parcours qui n'a pas d'opération — **programme relu** (SimPL, ISO…), **parcours TypeEdit** importé, parcours d'une opération retirée — est maintenant **une ligne du tableau des opérations**, après elles : en italique, avec son nom, sa nature, l'outil s'il est connu et sa profondeur. **Son œil** le montre ou le cache (caché : hors du programme), comme une opération.
- **Double clic** (ou Ctrl+M) : le formulaire qui en fait une opération, comme avant depuis le calque Trajectoires. **Suppr** : il est retiré, après confirmation (Annuler ne le rend pas : un programme se relit). **↑ / ↓** : il change de place dans l'ordre d'écriture, avant une opération par exemple — il passe d'un coup toutes les passes de l'opération voisine, jamais entre deux. **Clic droit** : en faire une opération, afficher ou cacher, inverser le sens, retirer.
- La liste « Parcours » à part ne se montre plus pour eux ; elle reparaît seulement quand des parcours sont écrits dans un autre ordre que le tableau (réglé à la main, ou un parcours sans opération placé entre deux opérations).
### v0.870.0 — Deux panneaux d'une colonne dans le même onglet

- **Clic droit** sur la barre d'un panneau ancré (ou sur son onglet) : **En onglet avec ›** propose les autres panneaux montrés de sa colonne — **Dimensions (F2)** et **Calques** peuvent ainsi partager un onglet, comme tout autre couple de panneaux. **Sortir des onglets** remet le panneau seul, sous les autres panneaux de sa colonne.
- Retenu : au lancement suivant, les panneaux se retrouvent ensemble, ou séparés, comme on les a laissés.
### v0.871.0 — Brut d'un dessin 2D : plaque ou contour dessiné, marges, surépaisseur

- **FAO ▸ menu du réglage ▸ Brut du dessin 2D…** : la matière d'où une gravure ou un fraisage sur plaque est usiné, quand ce n'est pas une plaque plate à Z 0. Au choix : **la plaque du dessin** ou **un contour dessiné** (une forme fermée choisie sur le dessin, « Prendre l'objet choisi comme contour »), avec une **marge** autour, une **surépaisseur au-dessus de la plaque** (Z 0 reste le dessus de la plaque finie ; un surfaçage la retire) et l'épaisseur (0 : celle de la plaque).
- Gardé avec le dessin. **La simulation part du haut de ce brut**, dans son emprise (contour compris) : la surépaisseur traversée compte dans la matière enlevée.
- Le brut d'une pièce 3D reste à part et passe devant quand une pièce 3D est là. Le calcul des opérations depuis le haut du brut suit dans une prochaine version.
### v0.872.0 — Les opérations partent du haut du brut du dessin 2D

- Avec un **brut du dessin 2D plus haut que la plaque** (surépaisseur, FAO ▸ Brut du dessin 2D…), la **première passe** d'un surfaçage, d'une gravure sur le trait, d'un détourage, d'une poche, d'un perçage ou d'un reste matière **part du haut du brut** ; le fond ne change pas, les dégagements passent au-dessus du brut.
- Un **surfaçage** sans objet ni couleur choisis travaille **toute l'emprise du brut** (plaque et marges, ou contour dessiné), de son haut jusqu'à Z 0. Les opérations placées **après ce surfaçage** (actif) repartent de Z 0 : le dessus est fait. Un surfaçage limité à des objets ou des couleurs laisse le brut ailleurs : les opérations d'après partent toujours de son haut.
- La gravure 2,5D, les chanfreins et le taraudage gardent Z 0 (leur profondeur se lit sur le dessus de la plaque), avec leurs **dégagements relevés** au-dessus du brut. Les cycles machine d'une opération qui traverse la surépaisseur sont remplacés par ses mouvements, comme avec un Z de départ.
- Les opérations **liées au parcours précédent** reprennent aussi la matière laissée dans la surépaisseur ; une poche « seulement le reste » voit les poches d'avant à leur vrai fond.
- Sans changement : le laser, les opérations enroulées ou projetées, celles d'une autre prise (pièce retournée, face d'une pièce 3D), celles qui ont un Z de départ, et tout le réglage s'il a un brut 3D.
### v0.873.0 — Outils : listes en colonnes, plein écran, pas d'outil mis d'office

- **Choisir un outil** et la **bibliothèque d'outils** montrent les caractéristiques des outils **en colonnes**, l'arborescence des dossiers gardée : nom, Ø, longueur de coupe, fabricant et référence d'office ; au **clic droit sur les titres**, montrer ou cacher le n° T, la nature, le dépassement, les dents, l'angle, la broche, les vitesses d'avance, de plongée et de rampe, la passe, le recouvrement, le dossier, les machines et les dessins (DXF, STEP). Les colonnes se déplacent en glissant leur titre ; la disposition est retenue. « Colonnes par défaut » revient à celle d'origine.
- Le **n° T** n'est plus écrit devant le nom : il n'apparaît que si sa colonne est montrée.
- Les deux fenêtres s'ouvrent **en plein écran** d'office ; F11 (ou ⛶) les ramène agrandies, et c'est retenu.
- Formulaire d'une opération sans outil : **« — Choisir un outil — »** au lieu du premier outil de la liste, qui s'y mettait d'office. Un **nouveau parcours** sans outil adapté (dans le document ou Mes outils) ne crée plus de « Fraise Ø1 » (ou de conique, de foret) d'office : l'outil est à choisir dans le formulaire. De même pour « Nouvelle opération », la poche et le perçage d'une pièce 3D et l'usinage 3D d'une sélection. **OK sans outil** : refusé, la liste « Outil » est signalée en rouge.
- Choisi au formulaire, l'outil règle ce qui dépend de lui : le pas du fond de la gravure 3D, l'outil de référence du reste matière.
### v0.874.0 — Choisir un outil : la fiche modifiable à droite, avec ses dessins DXF et STEP

- La colonne de droite de **Choisir un outil** montre la **fiche de l'outil choisi** : sa silhouette, ses **dessins DXF et STEP** (Ouvrir dans un nouvel onglet, Poser au clic sur le dessin) et **toutes ses caractéristiques, modifiables** : nom, nature, n° T, Ø, pointe, angle, longueur de coupe, dépassement, Ø du porte-outil, dents, broche, avances de coupe, de plongée et de rampe, passe en Z, recouvrement, puissance et fréquence laser, fabricant, référence, notes.
- Les caractéristiques qui ont une colonne ont leur case **« en colonne »** : cochée, elle s'affiche aussi en colonne de la liste (comme au clic droit sur les titres, dont elle suit les choix).
- **Enregistrer la fiche** : un outil de **Mes outils** est réécrit dans la bibliothèque (seulement les champs changés) ; un outil **du document** est modifié dans le document (gardé avec le formulaire de l'opération ; les parcours affichés des autres opérations qui s'en servent sont recalculés) ; un outil d'une bibliothèque de plugin reste en **lecture seule**. La ligne de l'outil et la liste « Outil » du formulaire suivent.
- Une fiche **modifiée** est enregistrée d'elle-même quand on choisit l'outil (OK, double-clic, Entrée) ou qu'on en montre un autre.
- Les dessins s'ouvrent ou se posent depuis une fenêtre ouverte directement sur VectorDrive (bibliothèque d'outils) ; depuis le formulaire d'une opération, il faut d'abord le fermer.
- « Outil du programme » : les outils du document y sont en lecture seule.
### v0.875.0 — Vitesses d'une opération : cadres Ébauche et Finition, avance de finition des outils, historique

- Les outils ont une **avance de finition** (mm/min ; 0 : celle de coupe), dans la fiche de **Choisir un outil**, la **bibliothèque d'outils**, le formulaire d'un outil et une colonne **Finition (mm/min)**.
- Dans le formulaire d'une opération, la section **Vitesses** montre deux cadres côte à côte : **Ébauche** (avance, plongée, broche) et **Finition** (avance de finition). **Un clic dans un cadre ou dans un de ses champs, ou la saisie dans un de ses champs, l'active, en surbrillance** (pas le passage d'un champ à l'autre par Tab) : l'opération prend l'avance de ce cadre, pour son calcul, sa durée, la fiche de réglage et le rapport de parcours. En Finition sans valeur propre : l'avance de finition de l'outil, sinon celle d'ébauche (le champ la montre).
- **Dans la fiche de l'outil**, sous chaque cadre, écrit ses valeurs dans la fiche de l'outil du document choisi (gardée à l'OK du formulaire) ; l'opération suit alors l'outil. Pour un outil de Mes outils, le bouton est grisé : sa fiche se modifie dans Choisir un outil.
- Chaque changement des vitesses d'un outil (broche, avances de coupe, de finition, de plongée, de rampe), depuis le formulaire d'une opération ou d'un outil, la fiche de Choisir un outil ou la bibliothèque, entre dans son **historique** (date, avant, après, d'où ; les 50 derniers) : **Historique des vitesses de l'outil…** dans le formulaire, **Historique…** dans la fiche. Les modèles de parcours ne l'emportent pas.
- Les programmes machine prendront l'avance du cadre actif, et l'avance de finition des seules passes de finition, avec une prochaine version des post-processeurs.
### v0.876.0 — Formulaire de parcours : cases pliables, « Avancé », la nature donnée par le parcours

- **Un clic sur le titre d'une case la plie** (seul son titre reste, précédé de « ▸ ») **ou la déplie** ; les cases pliées sont retenues pour la fois suivante, dans le formulaire d'une opération comme dans celui d'un outil. Clic droit sur un titre : **Tout plier**, **Tout déplier** ; « Disposition d'origine » déplie tout. Les cases se glissent toujours par leur titre.
- La case **« Particulier » s'appelle « Avancé »** ; une disposition déjà gardée la garde à sa place.
- Disposition d'origine : à gauche **Outil, Opération, Profondeurs, puis Avancé** ; à droite **Vitesses, puis Entrées et liaisons** ; puis le reste.
- Une case pliée se déplie d'elle-même quand le focus y entre (Tab, champ à remplir avant OK) ; elle reste pliée la fois suivante.
- **La nature de l'opération n'est plus une liste du formulaire** : elle est donnée par le type de parcours, montré sur la ligne **« Type de parcours »** (le nom du parcours de la colonne « Créer un parcours »). Seules « Nouvelle opération », sans type de parcours choisi, et l'opération faite d'après un programme relu (nature devinée) gardent la liste.
### v0.877.0 — Mode expert : l'outil conseillé proposé et vérifié d'office

- En **mode expert**, une nouvelle **poche** (« Gravure » de la colonne « Créer un parcours ») **propose l'outil conseillé** (la plus grosse fraise qui atteint tous les détails, parmi les outils du document et Mes outils de la machine, comme le bouton « Outil conseillé ») **et le vérifie** : le message s'écrit sous l'outil, sans fenêtre à fermer. Il disparaît dès qu'un champ change (la vérification ne vaut plus ; « Vérifier l'outil » la refait). Jusqu'ici, la première fraise venue était mise d'office, sans vérification. Quand aucune ne passe partout, la première est mise comme avant, et la vérification dit ce qu'elle n'atteint pas.
- Les autres parcours gardent l'outil d'office d'avant : ce critère n'y désigne pas le bon outil (un perçage veut le foret du trou, un détourage extérieur dépend des creux du bord, un tracé suit le trait). Les dernières valeurs retenues gardent leur outil ; un modèle choisi donne le sien ; des « Outils proposés par opération » réglés pour la poche passent avant.
- Option (F10, FAO) : « Mode expert : un nouveau parcours propose et vérifie l'outil conseillé », cochée d'office. En mode simple, rien n'est proposé (le premier outil de la nature voulue, comme avant) ; les boutons « Vérifier l'outil », « Outil conseillé » et « Aperçu du reste » restent.
### v0.878.0 — Passes de finition à l'avance de finition

- **Les passes de finition** (le tour qui enlève la surépaisseur laissée, d'un détourage ou d'une poche, case « Passe de finition ») **se font à l'avance de finition** de l'opération (cadre Finition du formulaire) ou, sinon, de l'outil (« Finition (mm/min) » de sa fiche), quand il y en a une ; une opération qui impose sa propre avance garde celle-ci si elle n'a pas d'avance de finition (l'avance de l'outil, plus vive, ne la dépasse pas). Sans avance de finition, à l'avance d'ébauche comme avant. Le reste du parcours garde l'avance du cadre actif.
- Le temps estimé compte les passes de finition à leur avance. Le marquage suit le parcours : arcs ajustés, parcours inversé ou déplacé, lié au parcours précédent, découpé en panneaux, origine et orientation du programme, enroulement et projection, session rouverte (les parcours d'une session d'avant : à recalculer).
- Les post-processeurs écrivent cette avance avec le plugin des machines 1.49.0.
### v0.879.0 — Dimensions (F2) et Calques en onglets d’office ; « Réglage… » de la FAO en mode expert

- **Dimensions (F2) et Calques partagent d'office le même groupe d'onglets** de leur colonne, Dimensions devant (jusqu'ici, Dimensions était au-dessus, à mettre en onglet au clic droit). Ce rangement ne s'applique pas si vous les avez séparés (« Sortir des onglets » sur l'un ou l'autre), si Dimensions est en onglet avec un autre panneau, ou si vous les avez rangés dans deux colonnes.
- Panneau FAO : le bouton **« Réglage… »** (importer, exporter le réglage FAO) n'est montré qu'en **mode expert**.
### v0.880.0 — Formulaires de parcours et d’outil : les flèches des champs répondent de nouveau au clic

- Dans le formulaire d'une opération (et celui d'un outil), **un clic sur les flèches d'un champ n'avait souvent aucun effet** (la touche ↑ marchait), et des champs de la colonne de gauche (Nom, Z de départ, Profondeur…) n'étaient même pas visibles : une case plus large que sa colonne (un long libellé, les cadres Ébauche et Finition côte à côte, un champ qui montre « 800 mm/min ») était coupée à droite, et les flèches de ses champs se trouvaient sous la colonne voisine ou sous le schéma de l'opération.
- Chaque colonne de cases prend maintenant la largeur de ses cases, sans dépasser sa part de l'écran ; sur un petit écran, une barre de défilement horizontale apparaît au lieu de couper. Elle suit une case qui change (champ montré ou caché, case pliée ou dépliée). Le panneau des opérations FAO et la colonne des réglages du BAT suivent aussi un contenu qui s'élargit.
### v0.881.0 — Mode simple : le ruban rangé d’après ce qu’il montre

- En **mode simple**, chaque groupe du ruban est rangé à partir de la disposition expert (même ordre, mêmes grands boutons) d'après ce qu'il montre : les petits boutons qui restent s'empilent par trois **sans trou** (jusqu'ici, les boutons réservés au mode expert laissaient des places vides, voire des colonnes vides).
- Un groupe qui ne montre plus qu'**un ou deux petits boutons** les montre en **grands boutons**.
- De retour en mode expert, la disposition expert revient telle quelle (vos changements du ruban compris : le mode simple part d'elle).
### v0.882.0 — Plaques de reprise : les bruts percés et taraudés aux trous de la plaque

- FAO › menu du réglage › **Plaque de reprise : trous de fixation des bruts…** : les bruts posés sur le dessin d'une plaque de reprise (un symbole de la bibliothèque, un DXF…) y sont vissés par-dessous. Sous chaque brut, les trous de la plaque qu'il couvre en entier, à une marge de son bord, sont les places de ses vis ; les plus écartés sont gardés (4 d'office, ou tous).
- Un calque **Fixation des bruts** reçoit des trous TypeEdit au foret du taraudage, avec une opération de **perçage** et une de **taraudage** sur ces trous. Déplacez ou effacez ensuite les trous comme tout objet : les opérations les suivent. Annuler retire le tout.
- Le filetage se déduit des trous de la plaque (Ø 3,2 : M3 ; Ø 4,3 : M4 ; Ø 6,4 : M6…) ou se choisit. Réglables aussi : les diamètres des trous de la plaque retenus, la marge, la profondeur taraudée, le perçage plus profond, et le brut retourné (gauche-droite ou haut-bas) pour son taraudage. Le compte des trous suit chaque réglage ; le dernier réglage est retenu.
### v0.883.0 — Plaques de reprise : la plaque posée depuis ses dossiers, jamais usinée

- La fenêtre **Plaque de reprise : trous de fixation des bruts** propose les plaques du dernier dossier de plaques choisi (et de ceux des modules) : **Poser** met la plaque choisie (symbole, DXF, SVG, VDZ) sur un calque à elle, verrouillé, sous le dessin, centrée sur la plaque du dessin (sans plaque : son coin bas-gauche à l'origine). **Autre fichier…** en prend une ailleurs et retient son dossier.
- La plaque posée devient d'office celle des trous de fixation ; c'est un repère : aucune opération ne l'usine, même par couleur, ni « une gravure par couleur » ; ni l'HPGL ni le relief tiré du dessin ne la reprennent. Annuler la retire.
### v0.884.0 — Programmes en série : un modèle d'usinage appliqué à chaque dessin d'une liste

- Fichier › **Traitement par lots** › **Programmes machine en série** : choisissez un modèle d'usinage (ou gardez les opérations de chaque dessin) et un post-processeur (ou celui de chaque dessin), puis **Écrire les programmes**. Chaque dessin de la liste reçoit le modèle, ses parcours sont calculés et son programme est écrit comme par le post-traitement (zéro du programme, orientation de sortie, un programme par plan ou par opération si le réglage le dit), dans le dossier de sortie (arborescence gardée), ou à côté du dessin sans dossier de sortie.
- Le modèle remplace d'office les opérations du dessin ; décoché, il s'y ajoute. Les dessins ne sont jamais réécrits ; un programme qui existe déjà n'est remplacé que si « Remplacer les fichiers existants » est coché.
- Comme le post-traitement d'un dessin : un défaut bloquant (arrêt manquant entre deux prises, surface qui a perdu sa pose…) n'écrit rien pour ce dessin, et chaque programme écrit est relu. Aucun programme du lot n'en remplace un autre, ni un dessin. Une machine à l'export propre (travail, dossier) passe par le panneau FAO.
- Le compte rendu dit les dessins sans opération, ceux dont les couleurs ne sont pas celles du modèle, les erreurs et les avertissements des post-processeurs. FAO › menu du réglage › **Programmes en série (modèle d'usinage)…** ouvre la même fenêtre.
### v0.885.0 — Colonnes partagées en hauteur ; la fenêtre d'une colonne

- Clic droit sur la barre ou l'onglet d'un panneau › **Au-dessus de ›** ou **Au-dessous de ›** un autre panneau : la colonne (de gauche comme de droite) se partage en hauteur, les deux panneaux montrés à la fois — Dimensions (F2) au-dessus de Calques, par exemple. Le choix est retenu pour les lancements suivants ; « En onglet avec › » les remet en onglets.
- **Clic droit sur un bouton de colonne** (en haut à droite) : la fenêtre de la colonne, sous le bouton. Elle liste tout ce que les colonnes peuvent accueillir (ceux de cette colonne d'abord, les autres avec leur place) ; **un œil par panneau** l'y montre (la FAO s'ouvre pour ses panneaux) ou l'en retire. **✕**, ou un clic droit dans la fenêtre, la ferme.
### v0.886.0 — Les favoris, tout en haut

- **Clic droit sur un bouton du ruban › Ajouter aux favoris (barre du haut)** : la commande rejoint la barre des favoris, tout en haut de la fenêtre, au-dessus du ruban (la première rangée en plein écran). Avec la disposition TypeEdit 13, ils suivent sa barre d'accès rapide (pas de deuxième barre, rien en double). Retenus pour les lancements suivants ; sans favoris, pas de barre.
- Clic droit sur un bouton des favoris : **Retirer des favoris**, et le reste du menu du ruban. Les outils de forme gardent leurs réglages au clic droit : Maj + clic droit donne ce menu.
- Les boutons des groupes repliés du ruban (dans leur menu déroulant) ont maintenant aussi ce menu au clic droit.
### v0.887.0 — Reconnaître une police : un bouton à part, un panneau de colonne

- **Reconnaître une police…** a son bouton à part dans le ruban du texte (groupe « Police », disposition TypeEdit 13 comprise), en grand aussi dans CAD › Texte.
- Sa fenêtre est maintenant un **panneau de colonne** : à droite d'office (en onglet avec les panneaux de la colonne), à gauche si vous l'y mettez (clic droit sur sa barre › Colonne de gauche, ou l'œil de la fenêtre de la colonne) ; le choix est retenu, il revient avec sa colonne, et le panneau peut aussi être détaché. À chaque clic sur le bouton, l'image pointe de nouveau sur la dernière capture d'écran. « Fermer » ferme le panneau et arrête la reconnaissance ; Échap l'arrête seulement. L'aperçu de l'image suit la largeur de la colonne.
### v0.888.0 — Champs sans flèches, un clic prend toute la valeur

- **Plus jamais de flèches ▲▼ dans les champs de valeur**, dans toute l'application : les touches ↑ ↓ et la molette changent toujours la valeur, la touche = ouvre toujours le calcul.
- **Un clic dans un champ sélectionne toute sa valeur**, prête à être remplacée (un deuxième clic place le curseur ; une partie choisie en glissant est gardée).
- Formulaires de parcours : un champ à 0 qui prend la valeur de l'outil n'affiche plus que **la valeur et son unité** (« 750 mm/min », « ≈ 1 mm », « — » si l'outil ne la donne pas, « auto » quand le parcours la calcule) ; d'où elle vient est dit dans sa bulle.
- **Aide** : la mention « Développé par RomDuch with Claude » et l'adresse de l'auteur, dans l'onglet Aide du ruban et dans À propos.
### v0.889.0 — Version macOS (essai)

- **macOS (essai)** : `VectorDrive.app` pour Apple Silicon (arm64) et Intel (x86_64), macOS 14 ou plus récent, construite par GitHub Actions (`.github/workflows/macos.yml`, recette `outils/macos/VectorDrive-macos.spec`) et jointe à chaque version publiée sur GitHub. L'autotest y réussit en entier (104 sur 104), depuis les sources comme dans l'application. Application non signée : macOS refuse le premier lancement ; Réglages Système › Confidentialité et sécurité › « Ouvrir quand même » (une seule fois).
- **Polices** : sous macOS, celles du système (`/System/Library/Fonts`, dont Arial) sont trouvées ; sous macOS et Linux, celles de l'utilisateur passent avant celles du système, comme dans le système.
- Le **moteur natif** des tracés (booléens, décalages) se construit depuis le dépôt seul : vectorcraft-geom 0.11.0 (MIT OR Apache-2.0) est copié dans `natif/vendor/vectorcraft-geom`, avec ses licences. L'extension Windows est recompilée (mêmes sources) sans aucun chemin du poste ; les licences des bibliothèques Rust qu'elle contient sont dans `licences/vdpathops-crates.txt`.
- L'export public ne contient plus les données de couverture des essais (`.coverage`) ni le profil d'exécution (`prof.out`).
### v0.890.0 — Ajouter un plugin, sous Windows et macOS

- **F10 › Plugins › « Ajouter un plugin… »** : choisir l'archive `.zip` d'un plugin ; elle est décompressée dans le dossier des plugins de VectorDrive et le plugin est chargé au démarrage suivant. Une nouvelle version remplace l'ancienne ; si le remplacement échoue (fichier en service…), l'ancienne reste entière, bibliothèques comprises. Une archive abîmée ne change rien et n'empêche jamais le démarrage. Si le plugin remplacé tourne déjà, le compte rendu conseille de redémarrer. Le compte rendu s'affiche sous le bouton ; « Ouvrir le dossier des plugins » à côté.
- Un plugin peut apporter ses **bibliothèques Python** (dossier `_lib` de son archive) : la version portable n'a pas besoin de les contenir. Chacune remplace sa version précédente.
- **macOS** : les données de VectorDrive (plugins compris) et le rapport des essais vont dans `~/Library/Application Support/VectorDrive` ; celles d'une première version macOS, dans `~/VectorDrive`, restent utilisées là où elles sont.
- Les versions empaquetées (Windows, macOS) contiennent les modules Python courants dont les bibliothèques d'un plugin ont besoin.
### v0.891.0 — Gravure 2,5D : la passe de finition

- **Gravure 2,5D à l'outil conique** : nouvelle case **« Passe de finition »**, juste sous la surépaisseur XY du formulaire. Avec une surépaisseur, la gravure laisse cette matière le long des bords, puis la passe de finition la retire, à l'**avance de finition** (celle du cadre Finition de l'opération, sinon celle de l'outil) : les flancs repris sur la forme exacte, le fond là où la gravure ne l'a pas vidé (la bande le long des bords), les tirés d'angle jusqu'aux vrais coins. La surface finie est celle de la gravure sans surépaisseur. Une forme trop étroite pour la surépaisseur est gravée en entier par la finition. En ligne médiane, c'est la ligne médiane de la forme exacte qui est reprise.
- Sans surépaisseur, ou case décochée, rien ne change ; les dessins enregistrés gardent leur parcours.
### v0.892.0 — L'archive ajoutable d'un plugin

- **Fabriquer l'archive d'un plugin** : nouvelle commande `python outils/plugin_zip.py DOSSIER_DU_PAQUET --lib openpyxl -o mon_plugin.zip` (et `plugins.build_archive`). Elle écrit l'archive que l'on ajoute ensuite par F10 › Plugins › « Ajouter un plugin… », sous Windows comme sous macOS : le paquet du plugin à la racine, sans caches (`__pycache__`, `.pyc`) ni fichiers cachés ; dans `_lib`, chaque bibliothèque nommée par `--lib`, avec ses `.dist-info`.
- Ce qui ne marcherait pas partout est refusé, avec la raison : une bibliothèque compilée (`.pyd`, `.so`…, propre à un système), la bibliothèque standard (déjà dans VectorDrive), une bibliothèque introuvable, un paquet qui ne définit pas `register`, un nom de fichier que Windows ne peut pas écrire (`aux.py`, `:` ou `?` dans le nom) ou deux noms qui ne diffèrent que par la casse. L'archive est relue avant de prendre la place de l'ancienne ; en cas de refus, rien n'est écrit.
- Le paquet garde le nom de son dossier sur le disque, même tapé avec une autre casse ou atteint par un lien.
