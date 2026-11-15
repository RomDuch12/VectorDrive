# Usinage 3D — guide

VectorDrive usine en 3 axes une pièce 3D : un fichier **STEP, STL ou 3D XML** ouvert comme dessin, ou les
**volumes modélisés dans le dessin** (onglet CAD en mode 3D : pavés, extrusions, booléens, pousser-tirer…). Tout part de
la **vue 3D** (va-et-vient 2D / 3D, ou panneau FAO) et du ruban **« FAO 3D »**. L'onglet FAO suit le mode :
« FAO 2D » en 2D, « FAO 3D » en 3D.

## 1. Choisir des faces ou des contours

Ruban FAO 3D, groupe « Clic dans la vue » :

- **Faces** : un clic choisit la face visée (en orange) ;
- **Contours fermés** : un clic choisit le contour de la face visée le plus proche du clic (en magenta) ;
- **Points et cotes** : un clic montre le point visé et ses cotes ; **Effacer la sélection** ;
- Ctrl ou Maj : plusieurs ; un second clic retire ; un clic dans le vide ou Échap efface tout.

La sélection est résumée sous la barre (nombre, aire, hauteurs). Faces d'un STEP : celles du fichier ;
STL et volumes : triangles regroupés jusqu'aux arêtes vives.

## 2. Usiner — ruban FAO 3D, groupe « Usinage 3D »

Les usinages se font dans la prise montrée (onglets Pièce et Prise de la vue 3D, § 3), sur les faces et
contours choisis, sinon sur toute la pièce (ou le corps). Une commande qui demande une sélection, ou sans
pièce 3D, le dit sous la barre de la vue.

| Commande | Ce qu'elle fait |
|---|---|
| Ébauche 3D (sélection, sinon toute la pièce) | paliers en Z ; à chaque palier, tout ce que l'outil peut enlever sans entamer la pièce ni la surépaisseur, en anneaux, entrée en rampe ; un palier juste au-dessus de chaque fond plat |
| Balayage 3D | passes parallèles qui suivent la surface (sens X, Y ou croisé), limitées aux pentes voulues |
| Niveaux constants | le tour des parois à chaque cote (finition des parois raides) |
| Contours dans le dessin | les contours fermés deviennent des formes du dessin, pour les parcours 2D |
| Poche jusqu'au fond | fond plat choisi : ses contours et une poche à sa profondeur |
| Trous → perçages | trous verticaux complets — cylindres creux du STEP ; pour un maillage ou des volumes du dessin percés, faces aux parois verticales posées sur un cercle : un cercle par trou dans le dessin, un perçage par diamètre et profondeur |
| Zone d'un usinage : Remplacer la zone de « … », Montrer la zone de « … » | la sélection devient la zone d'un usinage 3D, ou l'inverse |
| Automatisme… | voir § 3 |
| En volumes (groupe « Pièce 3D ») | voir § 6 |

L'outil évite toujours **toute** la pièce : la zone (faces ou contours choisis) dit seulement où il
travaille — sur des faces choisies, là où il les touche, pas là où une paroi voisine le tient au-dessus.

Stratégies FAO correspondantes (formulaire d'opération) : Ébauche 3D, Reprise 3D (la matière que l'outil
d'avant a vraiment laissée — creux, angles, fentes —, zone par zone, balayage puis tour des parois à chaque
palier ; l'outil d'avant est supposé être passé sur toute la zone),
Surface 3D (balayage), Niveaux constants 3D. Réglages propres : zone, débordement autour de la zone, pentes
d'au moins / d'au plus, face vers l'outil (prise), corps usiné.

## 3. Automatismes d'usinage 3D

Une suite d'étapes appliquée d'un coup, sur la sélection ou toute la pièce :

- **suites livrées** : Ébauche et finition ; Ébauche, demi-finition, finition ; Ébauche, reprise, finition
  des pentes et des parois ; Ébauche, finition, reprise des angles (grosse boule à passes larges, puis petite
  boule seulement là où la grosse n'atteint pas) ; Ébauche seule ; Finition seule ;
- **outils proposés** d'après la pièce, parmi ceux du dessin puis Mes outils (créés s'il en manque) :
  ébauche : la plus grosse fraise qui tient ; demi-finition : environ la moitié de l'outil d'avant ;
  finition : une boule de rayon au plus égal au plus petit rayon creux (STEP) ;
- **réglages déduits** : passe de l'outil, distance entre passes d'une boule pour une crête de 0,01 mm, pas
  de la carte ; une finition qui suit une ébauche suit la surface en une passe ;
- **tout se modifie** : étapes (ajouter, retirer, monter, descendre, désactiver), stratégie, outil (proposé
  ou choisi), surépaisseur, passe, distance entre passes, sens ; « Enregistrer sous… » garde la suite ;
- **Outil de l'étape…** : l'outil proposé ou choisi, dans son formulaire (diamètre, longueur utile, avance,
  vitesse…) ; la copie modifiée (nommée « … (modifié) ») devient l'outil de l'étape et entre dans le dessin
  avec les usinages — l'outil d'origine, du dessin ou de Mes outils, ne change pas ;
- « Créer les usinages » : outils et opérations ajoutés au panneau FAO, en une seule annulation ; la liste
  « Usinages » s'ouvre à droite de la vue 3D, le premier usinage créé choisi.

### Modifier ou supprimer les usinages créés

Liste **« Usinages »** à droite de la vue 3D (séparateur réglable) : les usinages de la prise montrée —
tous avec la prise « Toutes » —, leur outil et l'état de leur parcours (calculé, à calculer, désactivé).
Elle se montre dès que le dessin a des usinages ; ruban FAO 3D, groupe **« Usinages »** : « Liste des
usinages » la montre ou la cache (retenu).

| Commande | Ce qu'elle fait |
|---|---|
| double clic, Ctrl+M, Modifier l'usinage… | le formulaire de l'usinage : stratégie, outil, passes, surépaisseur, pentes, zone, prise… ; son parcours est recalculé — la sélection du dessin 2D n'y est pas prise |
| Outil de l'usinage… | le formulaire de son outil ; les parcours des usinages qui s'en servent sont recalculés (une annulation) |
| Recalculer l'usinage | son parcours calculé de nouveau |
| Dupliquer l'usinage | une copie juste après lui, à modifier (autre outil, autre zone) |
| Monter, Descendre l'usinage | sa place parmi les usinages de la liste ; ses parcours le suivent |
| Supprimer le parcours | le parcours calculé retiré, l'usinage gardé |
| Suppr, Supprimer l'usinage | l'usinage et son parcours supprimés ; Annuler le rend |
| case de la ligne | usinage actif ou désactivé |

Les boutons sous la liste et son clic droit donnent les mêmes commandes ; l'usinage choisi l'est aussi dans le
tableau du panneau FAO. Un usinage de toute la pièce le reste quand on le modifie (« Corps usiné » : toute la
pièce).

### Toutes les faces, chaque corps

- **Corps** : toute la pièce, chaque corps séparément (pièce à plusieurs corps), ou un corps ;
- **Prises : toutes les faces** : les prises (dessus, dessous, côtés) qui atteignent toute la surface sont
  proposées — chaque fois celle qui en atteint le plus, les surfaces vues de dessus d'abord — et ce qui
  reste hors d'atteinte en 3 axes est signalé. La suite est répétée pour chaque prise, précédée d'un message
  à l'opérateur « Poser … : … vers l'outil ».

Vue 3D, onglets **« Pièce »** et **« Prise »** :

- **Pièce** (pièce à plusieurs corps) : « Ensemble », puis un onglet par corps — un moule en trois parties
  a quatre onglets ; chaque corps se pose, se bride et s'usine à part ;
- **Prise**, sous la pièce choisie : une par position ou bridage (les reprises) — « Comme le dessin »
  (l'ensemble), « Comme l'ensemble » ou « Posé à part » (un corps), puis les faces retournées (dessous,
  côtés) ; « Toutes (recomposées) » : la pièce comme le dessin et les trajectoires de chaque prise et de
  chaque corps recomposées sur elle. Le nombre d'usinages de la prise suit son nom ;
- **+ Prise** : une autre face vers l'outil, gardée avec le dessin même sans usinage ; clic droit sur
  l'onglet : « Retirer cette prise » (sans usinage) ; double clic : son bridage ;
- **Placer…** (l'ensemble, ou le corps posé à part), **Bridage…** (étau, mandrin, brides de la prise
  montrée), **Brut…**, **Automatisme…** : l'automatisme crée les usinages de la prise montrée — le corps
  seul, la pièce retournée —, sur toute la pièce ou les faces et contours choisis là.

Chaque prise montre la pièce (ou le corps) posée comme pour ses usinages, avec leurs seules trajectoires et
son bridage ; les faces et contours choisis là créent des usinages de cette prise.

## 4. Corps

Ruban FAO 3D, groupe **« Corps et couleurs »** (pièce à plusieurs corps : solides d'un STEP, morceaux
séparés d'un STL, volumes du dessin) : « Corps » montre ou masque chaque corps ; Tout montrer, Couleur par
corps, Mécanismes… ; « Couleurs » : couleur de la pièce, des arêtes (retenues), couleurs d'origine. Groupe
« Poser » :
poser la pièce sur la face choisie, tourner cette face vers l'outil, corps posé à part, surface 2D.

## 5. Mécanismes et animation

Ruban FAO 3D, « Mécanismes… » :

- **contacts** entre corps : faces planes en vis-à-vis au jeu près, cylindres coaxiaux (STEP) ;
- **liaisons** : appui plan (le corps peut s'écarter), glissière (sens donné par une butée), pivot, pivot
  glissant, encastrement ;
- **mouvement libre** de chaque corps, depuis le corps fixe (le plus gros, ou celui choisi) ;
- **réglages** : écart des contacts, écart des directions, recouvrement mini, jeu des cylindres, corps fixe,
  course, rotation ;
- **animation** : curseur de « Fermé » à « Ouvert », lecture en va-et-vient ; pour chaque mouvement : animé
  ou non, course, sens inversé. La vue se tourne pendant l'animation.

- **collisions** : « Contrôler les collisions » déplace les corps, fermés en volumes, pas à pas sur la course ;
  deux corps qui prennent un volume commun s'interpénètrent (au repos, ou à partir de la position trouvée,
  montrée dans la vue). Deux faces en contact ne comptent pas ;
- **course jusqu'à la butée** : chaque mouvement pris seul est mesuré jusqu'à sa première collision, et sa
  course est réglée dessus.

Les réglages et ceux de chaque mouvement sont enregistrés avec le dessin et retrouvés à la réouverture.

## 6. Modifier la pièce

- Les **usinages** se modifient (zones, faces, prises, outils, réglages) sans toucher la pièce.
- La **géométrie** se modifie en volumes : « En volumes » (ruban FAO 3D ; « Convertir en volumes du dessin »
  dans le menu Corps) fait de chaque corps un volume du dessin (maillage réparé : languettes en double,
  jonctions en T, petits trous, orientation, débris), à modifier avec l'onglet CAD en mode 3D (booléens : percer, ajouter,
  couper) puis à usiner comme ci-dessus. Un corps dont le maillage ne se ferme pas est signalé, avec la raison.

## 7. Contrôler avant la machine

- **Simulation** (panneau FAO, ou vue 3D en relief) : la matière enlevée par les parcours, dans l'ordre, et
  deux contrôles signalés en rouge — le **porte-outil** qui touche la matière, et un **déplacement rapide**
  qui passe dans la matière (outil et profil de son bout comptés, matière telle que les parcours d'avant
  l'ont laissée). Une remontée verticale depuis le point d'usinage n'est pas contrôlée.
- **Reprise 3D** : elle suppose que l'outil d'avant est passé sur toute la zone ; ses déplacements rapides
  restent au-dessus de la pièce (dégagement, hauteur d'approche) et l'outil plonge depuis là.
- **Longueur utile** : un outil plus court que la profondeur à usiner limite l'usinage à sa longueur (signalé
  dans l'automatisme) — choisir un outil long dans « Mes outils ».
- **Mécanismes** : contrôle des collisions des corps sur la course (§ 5).

