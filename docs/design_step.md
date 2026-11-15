# Design STEP — pièces STEP générées

L'onglet **Design STEP** du ruban crée des pièces STEP **en vraies faces** (plans, cylindres, cônes,
sphères), que les logiciels de CAO et de FAO ouvrent avec leurs surfaces exactes : un trou y est un
cylindre avec son axe et son rayon, pas une suite de facettes. Les filets ne sont pas représentés (comme
les modèles simplifiés des catalogues) : un trou taraudé est au diamètre de perçage, une vis au diamètre
nominal.

## 1. Générer une pièce

**Générer une pièce STEP** ouvre la fenêtre des générateurs ; **Visserie**, **Transmission**, **Brut et
profilés**, **Éléments de moule**, **Bridage** l'ouvrent sur leur catégorie.

- À gauche, les familles par catégorie ; au milieu, leurs paramètres (taille, longueur, référence…) ; à
  droite, l'aperçu ombré de la pièce — **glisser** pour la faire tourner.
- Sous les paramètres : le nom du fichier, le volume, la masse (acier, laiton ou aluminium selon la
  pièce) et l'encombrement. Des valeurs impossibles (trous qui se touchent, alésage plus grand que la
  roue…) sont dites à la place, et rien ne s'enregistre.

| Catégorie | Familles |
|---|---|
| Visserie | Vis CHC ISO 4762, H ISO 4017, FHC ISO 10642, BHC ISO 7380, STHC ISO 4026 ; écrous H ISO 4032 ; rondelles ISO 7089 et ISO 7093-1 ; goupilles ISO 2338 |
| Transmission | Roulements rigides à billes (62x, 60xx, 62xx) ; clavettes DIN 6885 A ; roues dentées droites (module, dents, largeur, alésage) |
| Brut et profilés | Barres, tubes et profilés (rond, tube, carré, plat, six pans, tube carré, cornière, U) ; plaques percées ; entretoises taraudées ; bagues lisses ; brides rondes à trous sur un cercle |
| Éléments de moule | Éjecteurs, colonnes et douilles de guidage à collerette, bagues de centrage, plaques de moule à alésages de guidage (dimensions à donner) |
| Bridage | Brides de serrage à lumière (plates ou à talon), cales étagées, mors doux à deux trous lamés (épaulement au choix), goujons de bridage, écrous pour rainure en T, vés de bridage (dimensions à donner), plateaux à rainures en T (ISO 299), cales pentées |

Les familles normalisées prennent leurs cotes dans les tables des normes (valeurs nominales). Les vis ont
le **dessous de la tête en Z = 0** et la tige vers le bas ; la vis FHC a le dessus de sa tête en Z = 0, la
vis STHC son dessus. Écrous, rondelles, bagues, barres et plaques sont posés sur Z = 0.

**Bridage** : la bride a sa lumière au milieu (largeur de passage de la vis) et, au choix, un talon
dessous au bout ; la cale étagée a sa plus haute marche au bord X = 0 ; le mors doux est couché, dos en
Z = 0 et face de serrage en haut, ses trous lamés côté serrage (reconnus par **Vis dans ce trou…**),
l'épaulement au bord haut de la face de serrage ; le goujon est au diamètre nominal ; l'écrou en T a sa
tête en bas, taraudé au diamètre de perçage. Le **vé de bridage** est un bloc long de Y, centré, dessous en
Z = 0, le vé ouvert en haut sur toute la longueur : angle de 90° ou 120°, ouverture donnée en haut (2 mm de
bord au moins de chaque côté), une gorge au fond pour les arêtes vives (largeur 0 : sans), 3 mm de matière
au moins dessous. Le **plateau à rainures en T** est un bloc long de Y, centré, dessous en Z = 0 : n rainures
ISO 299 ouvertes dessus sur toute la longueur, centrées en X à l'entraxe donné ; largeur a, tête b × c,
profondeur totale h (par défaut 14, 23 × 9, 23 : l'écrou en T par défaut y entre) ; 5 mm de matière au moins
dessous, entre deux têtes et au bord. La **cale pentée** est un bloc long de Y, centré, dessous en Z = 0,
le dessus en pente le long de X, de la hauteur du bout mince (X bas, 0,5 mm au moins) à celle du bout épais ;
l'angle de la pente est dans le nom du fichier.

**Plaque de moule** : longueur, largeur, épaisseur, coin à l'origine ; quatre alésages de guidage à
l'entraxe donné des bords, celui du coin X = 0, Y haut **décalé en X** (la plaque ne se monte que dans un
sens ; 0 : sans), **lamés** dessus au besoin pour les collerettes ; une **empreinte** en poche au milieu au
besoin (longueur, largeur, profondeur, rayon des coins ; longueur 0 : sans). Alésages trop près du bord ou
qui se touchent, empreinte qui touche un alésage : c'est dit. Les alésages reçoivent douilles ou colonnes
par **Pièce dans ce trou…** : les valeurs de départ (Ø20, lamage Ø26 × 5) reçoivent la douille proposée,
sa collerette Ø25 × 5 dans le lamage, au ras du dessus.

**Plaque percée** : longueur, largeur, épaisseur, rayon des coins ; trous aux quatre coins, en grille ou au
centre, avec leur marge ; trous de passage (ISO 273), lamés pour vis CHC, fraisés à 90° pour vis FHC, ou
taraudés.

**Bride ronde** : diamètre, épaisseur, alésage au centre (0 : sans) ; trous sur un cercle (nombre, Ø du
cercle, angle du premier depuis +X), de passage, lamés, fraisés ou taraudés comme la plaque percée, lamages
et fraisures dessus ; centrage en saillie dessus au besoin (Ø, hauteur). Axe Z, dessous à Z = 0. Trous sur
l'alésage ou sous le centrage, hors de la bride ou qui se touchent : c'est dit. Les trous reçoivent leurs
vis par **Vis dans ce trou…** (tous ensemble), l'alésage un roulement par **Pièce dans ce trou…**.

## 2. Enregistrer, ajouter, ouvrir

- **Enregistrer le STEP** : la pièce dans le dépôt, dans le sous-dossier de sa catégorie
  (`Visserie/Vis_CHC_ISO4762_M6x20.step`…). Un fichier du même nom est remplacé après confirmation.
- **Toute la gamme** : toutes les tailles et longueurs courantes de la famille, un fichier par pièce, dans
  un sous-dossier de la famille (`Visserie/Vis_CHC_ISO4762/`…), avec avancement et Annuler.
- **Ajouter au dessin** : la pièce comme volume du dessin, centrée sur la plaque et posée sur Z = 0 (booléens, export STL,
  usinage 3D) ; sa description (famille et paramètres) est gardée avec le volume.
- **Ouvrir le STEP** : la pièce enregistrée, ouverte dans un onglet en vue 3D, prête à placer et à usiner
  (ruban FAO 3D).

**Modifier la pièce générée…** (groupe Générateurs) : choisir dans le dessin une pièce ajoutée par les
générateurs ; la fenêtre se rouvre sur sa famille et ses valeurs, et **Remplacer dans le dessin** met la
pièce modifiée à sa place — même milieu en X et Y, même dessous, même si elle a été déplacée depuis.
Annulable ; chaque nouvel appui remplace encore la même pièce. Une pièce supprimée entre-temps est ajoutée
à neuf, au centre de la plaque.

**Pièce du dessin…** (groupe Générateurs) : choisir dans le dessin des formes fermées — le bord de la
pièce, ses trous, ses lumières, des textes (par leur contour) — puis le bouton. Elles deviennent une pièce
STEP à vraies faces, coordonnées du dessin (mm), dessous à Z = 0 :

- les courbes sont ramenées à des droites et des arcs de cercle (à 0,01 mm) : un arc reste un arc, sa
  paroi un cylindre ; un contour rond est un vrai cercle (trou reconnu par **Vis dans ce trou…**) ;
- le contour le plus extérieur est le bord ; un dessin à plusieurs bords donne une pièce par bord, dans le
  même fichier (`nom_1`, `nom_2`… de gauche à droite) ;
- **Contours intérieurs** : **Trous débouchants**, **Poches** (de la profondeur donnée, depuis le dessus),
  ou **Ronds débouchants, autres en poche** (plaque gravée : trous de fixation et lumières) ;
- un contour dans une poche est un îlot, un contour dans un îlot de nouveau un trou ou une poche (un trou
  rond débouchant traverse l'îlot et le fond) ; un îlot dans un trou débouchant serait une pièce détachée :
  c'est dit, comme des contours qui se coupent, un contour qui se recoupe (en huit, étoile tracée d'un
  trait) ou une poche plus profonde que la pièce ;
- les contours ouverts sont laissés (comptés) ;
- **Enregistrer…** : dans le dépôt (dossier `Dessin`, nom de la pièce) ou ailleurs ; **Ouvrir en 3D** :
  enregistrée dans le dépôt puis ouverte dans un onglet, vue 3D.

**Pièce tournée du dessin…** (même groupe ; ou **Forme : Tournée** dans la fenêtre) : une pièce de
révolution (arbre, bague, axe, poulie, pointe) depuis son demi-profil fermé dessiné d'un côté de l'axe :

- l'axe est un **trait droit** choisi avec le profil (vertical, horizontal pour un dessin de tournage, ou
  incliné ; il n'a pas à toucher le profil : une bague) ; sans trait, la verticale par le point le plus à
  gauche du profil ;
- dans la pièce, l'axe est Z (vers le haut du trait, ou vers sa droite s'il est horizontal), au centre ; le
  bas du profil est à Z = 0 ;
- une droite du profil donne un cylindre, un cône (chanfrein, fraisure, pointe) ou un plan ; un arc centré
  sur l'axe donne une sphère (boule, calotte) ; les autres arcs (congés, gorges rondes) et les courbes sont
  ramenés à des cônes à 0,01 mm près ;
- une pointe sur l'axe est arrêtée d'un petit plat de 0,05 mm de rayon ; une arête vive tout en haut ou
  tout en bas (deux parois qui partent du même cercle) d'un plat de 0,05 mm, là où les parois s'écartent
  d'autant ; un sommet à moins de 0,01 mm de l'axe est mis dessus ;
- chaque contour fermé est une pièce (`nom_1`, `nom_2`… de bas en haut) ; un profil des deux côtés de
  l'axe, qui se recoupe, qui touche l'axe en plusieurs traits, deux profils qui se touchent ou l'un dans
  l'autre (un vide fermé), un arc tangent à l'axe, deux traits droits : c'est dit ;
- le résumé donne le nombre de profils, d'où vient l'axe, le Ø maxi et la hauteur.

## 3. Sélection 3D

**Faces** (le même bouton qu'au ruban FAO 3D) : un clic dans la vue 3D d'une pièce (STEP, STL, volumes du
dessin) choisit une face, Ctrl ou Maj : plusieurs, un second clic la retire ; **Effacer la sélection** la vide.
La ligne sous la vue dit ce qu'est la face choisie (« trou Ø6,6 sur 5,5 mm, axe +Z », « plan, normale +Z,
à 12 mm ») ou, pour deux faces, leur mesure.

- **Faces semblables** : toutes les faces comme celles choisies — un cylindre : les cylindres de même rayon,
  creux ou non comme lui (tous les trous de ce diamètre) ; un plan : les plans de même normale à la même
  cote (faces coplanaires, fonds de lamages) ; une autre face (cône, congé) : celles de même nature et de
  même aire. Puis **Vis dans ce trou…** prend la première paroi de trou choisie.
- **Faces parallèles** : un plan choisi, tous les plans de même normale (même sens) à toute cote — les
  fonds et dessus tournés vers l'outil d'une prise, sur tous les corps ; un cylindre, tous ceux d'axe
  parallèle, creux ou non comme lui — les trous percés dans ce sens (pas un alésage couché).
- **Faces coaxiales** : un cylindre, un cône, une sphère ou un tore choisi, dans son corps, toutes les faces
  de révolution du même axe (sphères centrées dessus) et les plans perpendiculaires à l'axe bordés seulement
  par elles — un trou entier d'un clic (passage, lamage et son fond, fraisure, fond plat), un arbre tourné
  entier (cylindres, chanfreins, dôme, épaulements, bouts) ; une bague ou une autre partie du moule sur le
  même axe n'en est pas ; une sphère choisie prend l'axe de la face voisine qui passe par son centre ; un
  plan reste seul.
- **Faces tangentes** : de proche en proche, les faces qui suivent celles choisies **sans arête vive** — un
  bord arrondi (les côtés et les congés des coins), une chaîne de congés, les deux moitiés d'un trou ; une
  arête vive (un dessus, un chanfrein, des coins vifs) arrête la sélection. Le pli est mesuré le long des
  arêtes communes : par la surface que le lecteur STEP décrit (plan, cylindre : 3° au plus), sinon par les
  facettes (20° au plus : cônes, sphères, tores, STL).
- **Faces du corps** : toutes les faces des corps des faces choisies — une partie d'un moule en plusieurs
  corps, pour la mesurer, la montrer ou l'usiner seule.
- **Inverser dans le corps** : les faces des corps choisis qui ne sont pas choisies — le reste d'une pièce
  (tout sauf un trou, sauf les fonds déjà usinés) ; deux fois : la sélection de départ.
- **Mesurer la sélection** : chaque face décrite (nature, diamètre et axe, normale et cote, aire) et, pour
  deux faces :

| Faces | Mesure |
|---|---|
| deux plans parallèles | leur distance |
| deux plans | l'angle entre leurs normales |
| deux cylindres d'axes parallèles | l'entraxe |
| deux cylindres | l'angle des axes et leur plus courte distance |
| un cylindre et un plan parallèle à son axe | la distance de l'axe au plan |
| autres | la plus courte distance entre les deux faces |

  Plusieurs faces : leur aire et leur encombrement. **Copier** met le texte dans le presse-papiers.

Une face d'un STEP est décrite par ce que le lecteur en dit (surface exacte) ; un maillage sans
description (STL) : une face plate est reconnue à ses facettes, les autres restent « face ».

## 4. Modifier un STEP

**Corps d'un STEP…** ouvre les corps (solides) d'un fichier STEP : celui de la pièce 3D du dessin, avec le
corps des faces choisies dans la vue 3D coché seul, sinon un fichier à choisir (**Ouvrir…** en change).

- La liste donne chaque corps avec son nombre de faces ; les corps cochés sont montrés dans l'aperçu
  (glisser pour tourner). **Tout cocher**, **Tout décocher**.
- **Déplacer les corps cochés** : translation X, Y, Z en mm et rotation autour de X, Y ou Z (autour de
  l'origine du fichier, puis la translation) ; l'aperçu suit. Sans valeur, les corps gardent leur place.
- **Extraire les corps cochés…** : les corps cochés dans un seul fichier STEP.
- **Un fichier par corps…** : chaque corps coché dans son fichier, nommé d'après le corps, dans le dossier
  choisi (un moule en trois parties : trois STEP) ; des fichiers existants sont remplacés après
  confirmation. **Voir les fichiers** ouvre le dossier dans le navigateur à vignettes.

**Réunir des STEP…** fait une seule pièce de plusieurs fichiers STEP, chaque corps à sa place.

**Répéter des corps…** (même groupe) : les corps d'un STEP — la pièce 3D du dessin, le corps des faces
choisies seul, sinon un fichier à choisir — copiés dans un nouveau STEP à géométrie exacte, l'original
compris : **en ligne** au pas donné en X, Y et Z, ou **en rond** autour de la verticale par le centre donné
(360° : répartis sur le tour, sinon du premier au dernier sur l'angle). Les axes sont ceux de la pièce
redressée, comme dans la vue 3D (un fichier exporté « Y vers le haut » compris). Une série de mors, de vés,
de pièces à usiner sur un plateau. Un nom seul est écrit à côté de la source ; un fichier qui existe n'est
remplacé qu'au second clic sur **Écrire** ; le fichier source ne l'est jamais.

La géométrie est recopiée **exacte** (faces, arêtes, surfaces du fichier d'origine), avec les noms et les
couleurs des corps, les unités du fichier et sa place dans l'assemblage ; rien n'est remaillé. Les
coordonnées restent celles du fichier d'origine : des pièces séparées puis réunies reviennent à leur place.
À l'ouverture, une pièce exportée couchée est redressée comme tout STEP (ses grandes faces planes à plat).
Des fichiers en unités différentes (mm et pouces) ne se réunissent pas d'un coup.

**Vis dans ce trou…** : choisir dans la vue 3D de la pièce du dessin (une pièce STEP) la paroi d'un trou,
puis le bouton. Le trou est reconnu dans n'importe quelle direction, débouchant ou borgne :

| Trou | Vis proposée | Posée |
|---|---|---|
| lamé (un cylindre au moins 1,4 fois plus large à l'ouverture) | CHC ISO 4762 | dessous de la tête sur le fond du lamage |
| fraisé (un cône qui s'ouvre à 1,5 fois le Ø du trou au moins) | FHC ISO 10642 | tête au ras de la surface |
| de passage (Ø ISO 273 série fine, moyenne ou large, ou nominal) | CHC | tête sur l'ouverture |
| taraudé (Ø de perçage) | CHC | tête sur l'ouverture |

Un cône plus petit à l'ouverture est un chanfrein d'entrée : la tête se pose au-dessus. Un lamage moins
profond que la moitié du diamètre de la vis est un lamage de surface : le trou garde le genre de son
diamètre (un taraudage lamé reste taraudé). La paroi du lamage choisie à la place de celle du trou : le trou
dessous. Deux trous sur le même axe séparés par de la matière (une entretoise taraudée aux deux bouts) sont
deux trous.

- La taille vient du diamètre du trou (la plus proche s'il est hors norme, c'est dit) ; la longueur, parmi
  celles de la norme : un trou débouchant de passage, lamé ou fraisé et 1,5 d de filet en prise dessous ;
  un trou borgne, la plus longue sous la profondeur moins un pas ; un taraudé débouchant, la plus courte
  qui le traverse. L'épaisseur traversée compte un lamage, une fraisure ou un chanfrein du côté opposé.
  Un trou de passage fermé au fond par un taraudage de sa taille (trou étagé, pièce posée sur une pièce
  taraudée, dans le même fichier) : la vis s'y visse.
- Vis (CHC, H, FHC, BHC), taille et longueur se changent ; **Tête de l'autre côté** pour un trou
  débouchant ; **Tous les trous identiques (n)** pose la même vis dans chaque trou de même diamètre, même
  genre, même longueur et même sens.
- **Enregistrer la vis…** : la ou les vis seules dans un fichier STEP, aux coordonnées de la pièce ;
  **Pièce et vis…** : la pièce et ses vis dans un seul fichier (pièce en millimètres ; sinon, c'est dit :
  la vis seule).
- Une grande pièce aux nombreux trous est préparée une fois : la reconnaissance des trous identiques
  reste rapide (625 trous lamés en quelques secondes).

**Pièce dans ce trou…** : la paroi d'un alésage choisie dans la vue 3D (comme pour la vis), puis le
bouton. L'alésage est la paroi elle-même (sans passer au trou plus étroit d'un lamage) : son axe, son
entrée (le bout ouvert ; d'un débouchant, le haut, **Entrer par l'autre côté** pour l'autre bout), son
fond, son diamètre et sa profondeur. Un bout prolongé par un trou plus étroit est un épaulement : l'alésage
y est fermé (borgne). La pièce choisie est proposée à son diamètre et posée :

| Pièce | Proposée | Posée |
|---|---|---|
| goupille cylindrique ISO 2338 | Ø de la série qui va (pas plus gros que l'alésage, au plus 0,5 mm plus petit), la plus longue dans la profondeur | au ras de l'entrée |
| roulement rigide à billes | la référence de Ø extérieur qui va (même règle ; à Ø égal, celle qui tient dans la profondeur) | au ras de l'entrée |
| bague lisse | Ø extérieur de l'alésage, toute la profondeur | au ras de l'entrée |
| douille de guidage à collerette | Ø extérieur de l'alésage, corps dans toute la profondeur | collerette sur l'entrée |
| colonne de guidage à collerette (débouchant) | Ø guidé de l'alésage | collerette contre la sortie, colonne qui dépasse de l'entrée |
| éjecteur (débouchant) | Ø de tige de l'alésage, longueur jusqu'à la tête | bout au ras de l'entrée, tête sous la sortie |
| bague de centrage | Ø extérieur de l'alésage, 12 mm de haut (au plus l'épaisseur d'un débouchant) | au fond d'un borgne (elle dépasse pour centrer), au ras de l'entrée d'un débouchant |

Une pièce plus longue qu'un alésage borgne est posée au fond et dépasse de l'entrée, jamais dans la
matière ; sous l'aperçu, ce qui dépasse de l'entrée ou de la sortie est dit. Sous un lamage, l'entrée est
le fond du lamage : une collerette s'y loge (elle « dépasse » de l'entrée, dans le lamage).

- Les cotes « à donner » (alésage d'une bague, collerette, tête) sont proposées en proportion ; toutes se
  changent dans la fenêtre (**Proposer de nouveau** : celles de l'alésage). Une pièce qui ne va pas (pas de
  goupille de la série à ce diamètre, colonne dans un borgne, diamètre hors des cotes du générateur) : c'est
  dit, rien à enregistrer.
- **Tous les alésages identiques (n)** : la même pièce dans chaque alésage de même diamètre, même
  profondeur, débouchant ou non pareil, entrée du même côté.
- **Enregistrer seule…** : la ou les pièces posées dans un fichier STEP, aux coordonnées de la pièce
  percée ; **Avec la pièce percée…** : les deux dans un seul fichier (pièce en millimètres ; sinon, c'est
  dit).

## 5. Dépôt STEP

- **Dossier du dépôt…** choisit le dossier où les pièces sont enregistrées (par défaut
  `Documents/VectorDrive/STEP`) ; le bouton **Dossier…** de la fenêtre fait de même.
- **Parcourir le dépôt** l'ouvre dans le navigateur à vignettes : vue de dessus de chaque STEP, recherche,
  favoris ; ouvrir une pièce ou la poser dans le dessin.

## 6. Contrôle des fichiers

Chaque fichier écrit est un solide fermé : chaque arête est bordée par deux faces en sens opposés, le
nombre d'Euler est juste, toutes les faces sont tournées vers l'extérieur. Deux étages d'une pièce peuvent
avoir des parois alignées (talon, épaulement, tenon) : les arêtes y sont coupées aux sommets de l'autre
étage ; des étages qui se croisent, se touchent en un point, bord à bord (même un bouchon dans un trou),
presque alignés (écart sous le micromètre) ou dont un arc touche un côté de l'autre sont refusés, avec
un message. Un fichier contient un solide
nommé et coloré par pièce.
