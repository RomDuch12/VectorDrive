# Guide des commandes — VectorDrive 0.936.0

Généré depuis le ruban (outils/guide.py) : chaque ligne est une commande réelle.

## Fichier

### Document

| Commande | Raccourci | Rôle |
|---|---|---|
| Nouveau | Ctrl+N | Nouveau dessin, dans un nouvel onglet |
| Ouvrir | Ctrl+O, Ctrl+Shift+O |  |
| Enregistrer | Ctrl+S |  |
| Enregistrer sous | Ctrl+Shift+S |  |
| Nouveau d'après un modèle… |  | Nouveau dessin à partir d'un modèle (plaque, cartouche, repères…) |
| Enregistrer comme modèle… |  | Garder ce dessin comme point de départ d'autres dessins |
| Informations |  | Titre, auteur, client et commentaires du document (gardés dans le fichier), et ses chiffres : calques, objets, temps passé |
| Aperçus des fichiers |  | Aperçu du fichier choisi dans Récents et dans Ouvrir — pour cette séance seulement (coupé par défaut : plus rapide) |
| Quitter |  | Fermer VectorDrive |

### Import / export

| Commande | Raccourci | Rôle |
|---|---|---|
| Menu de l'explorateur |  | « Convertir avec VectorDrive ▸ en DXF, SVG, PDF, EPS, Traitement par lots… » au clic droit des dessins et des dossiers dans l'explorateur Windows (votre compte seulement) |
| Vignettes dans l'explorateur |  | Vignettes des dessins (VND, DXF, SMB, SVG, AI, EPS, VDZ, PDF) et des programmes machine (G-code, SimPL…) dans l'explorateur Windows, tracées par VectorDrive (votre compte seulement) |
| Importer | Ctrl+I |  |
| Exporter | Ctrl+E |  |
| BAT PDF | Ctrl+Shift+P | Épreuve PDF (bon à tirer) |
| Imprimer | Ctrl+P | La sélection, la plaque, des calques ou tout le dessin — sur une feuille de A6 à A1, ajusté à l’échelle conseillée, à 1:1 ou au zoom choisi ; ou en PDF à la taille réelle ; ou la page BAT |
| Imprimer la sélection… |  | Imprimer les objets sélectionnés seuls : à l'échelle 1:1, ou ajustés à une feuille A4 avec des marges de 15 mm |
| Brut de l'ensemble… |  | Le morceau de matière de l'objet ou du groupe sélectionné, dessiné et coté à part sur le BAT : ni gravé, ni usiné, ni exporté. Plusieurs objets sélectionnés : ils sont groupés |
| Traitement par lots… |  | Convertir d'un coup des dessins ou des dossiers entiers (VND en DXF, PDF, SVG…), BAT au choix |
| Exporter en STL… |  | Les reliefs choisis (sur un socle) et les formes fermées choisies (extrudées) en STL : impression 3D, autre logiciel de FAO |

### Comparer

| Commande | Raccourci | Rôle |
|---|---|---|
| Comparer |  | Comparer le dessin à un autre (onglet ouvert ou fichier) : ajouté en vert, enlevé en rouge, modifié en orange |
| Différence suivante |  | Montrer la zone suivante qui porte des différences |
| Différence précédente |  | Montrer la zone précédente qui porte des différences |
| Fermer la comparaison |  | Effacer les couleurs de la comparaison |

## Edition

### Action

| Commande | Raccourci | Rôle |
|---|---|---|
| Défaire | Ctrl+Z |  |
| Refaire | Ctrl+A |  |
| Défaire plusieurs… |  | Liste des modifications : défaire jusqu'à celle choisie |
| Refaire plusieurs… |  | Liste des modifications défaites : refaire jusqu'à celle choisie |
| Vider l'historique |  | Oublier les annulations (libère la mémoire sur un gros dessin) |

### Assistant

| Commande | Raccourci | Rôle |
|---|---|---|
| Assistant IA |  | Discuter avec Claude, ChatGPT ou Mistral, qui dessinent et modifient le dessin ouvert (avec la clé d’API du fournisseur) |

### Presse-papiers

| Commande | Raccourci | Rôle |
|---|---|---|
| Coller | Ctrl+V, Shift+Ins |  |
| Couper | Ctrl+X, Shift+Del |  |
| Copier | Ctrl+C, Ctrl+Ins |  |
| Effacer | Del |  |
| Rappeler l'effacement |  | Ce que le dernier Effacer a retiré revient, chaque objet à sa place, même après d'autres modifications (une seule annulation) |
| Reproduire les propriétés |  | Les propriétés du premier objet sélectionné vont aux autres (un seul : aux objets cliqués ensuite) : outil, remplissage, calque, mise en forme des textes (choix dans F10 › Dessin) |
| Remplir / vider |  | Remplit les contours fermés de la sélection, ou les vide s'ils le sont déjà (groupes compris). Un import rempli se vide ainsi, et inversement |
| Couleur… |  | Donne une couleur aux objets sélectionnés : leur trait, et leur remplissage s'ils sont remplis. Elle ne dépend pas de l'outil ; Ctrl+8 montre ou cache les couleurs |
| Couleur de l'outil |  | Retire la couleur donnée aux objets sélectionnés : ils reprennent celle de leur outil |

### Sélection

| Commande | Raccourci | Rôle |
|---|---|---|
| Sélection | Esc |  |
| Tout | Ctrl+L | Sélectionner tout |
| Inverser |  | Inverser la sélection |
| Filtre | F9 | Filtre de sélection : seules les natures d'objets choisies se sélectionnent |
| Aperçu | F4 | Aperçu pendant les déplacements, redimensionnements et rotations : les objets entiers (sinon leur seul rectangle, plus rapide) |
| Modes |  | Modes de sélection : ajout, désélection, garder ; classement de la sélection (ordre d'usinage) |
| Lasso |  | Sélection au lasso : clics = lasso polygonal, glisser = à main levée ; double-clic ou Entrée pour prendre les objets touchés (opérateur et filtre de sélection compris) |
| Même outil |  | Sélectionner tous les objets du même outil que la sélection |
| Même forme |  | Sélectionner tous les objets de même nature et de même taille que la sélection |
| Geler |  | Geler la sélection : elle reste visible mais ne se modifie plus. Un clic désigne un objet gelé, ce bouton le dégèle |
| Tout dégeler |  | Déverrouiller tous les objets |
| Masquer |  | Masquer la sélection |
| Tout afficher |  | Réafficher les objets masqués |
| Isoler |  | Ne montrer que la sélection (les autres objets masqués) ; « Fin d'isolement » les réaffiche |
| Fin d'isolement |  | Réafficher les objets masqués par « Isoler » |

### Ordre

| Commande | Raccourci | Rôle |
|---|---|---|
| Premier plan | Shift+PgDown | Placer la sélection au-dessus (et en dernier à l'usinage) |
| Arrière-plan | Shift+PgUp | Placer la sélection au-dessous (et en premier à l'usinage) |
| Avancer |  | Avancer d'un rang |
| Reculer |  | Reculer d'un rang |

### Groupes

| Commande | Raccourci | Rôle |
|---|---|---|
| Grouper |  |  |
| Dégrouper |  |  |
| Inverser l’ordre |  | Les objets de chaque groupe et les contours de chaque objet combiné passent dans l’ordre inverse (l’ordre d’usinage aussi) |
| Combiner |  | Réunir les objets sélectionnés en une seule forme |
| Décombiner |  | Séparer chaque contour en une forme |
| Englobants |  | Combiner englobants et englobés : chaque contour extérieur reçoit ses trous (sens normalisé pour l'usinage) |

### Modes

| Commande | Raccourci | Rôle |
|---|---|---|
| Dimensions | F2 | Dimensions et positionnement ; avec un outil de forme (rectangle, polygone, étoile, spirale…) : la forme par ses paramètres ; une forme sélectionnée : ses paramètres |
| Accrochage | Shift+F3 | Accrochage aux nœuds, milieux, centres et à la grille (F3 : fenêtre des accrochages) |

### Accrochage

| Commande | Raccourci | Rôle |
|---|---|---|
| Fenêtre des accrochages | F3 | Accrochages (TypeEdit : F3) : activer, choisir les points accrochés, rayon d'attraction |
| Nœuds |  | Accrocher : nœuds |
| Intersections |  | Accrocher : intersections |
| Milieux |  | Accrocher : milieux |
| Centres |  | Accrocher : centres |
| Centres de gravité |  | Accrocher : centres de gravité |
| Quadrants |  | Accrocher : quadrants |
| Perpendiculaire |  | Accrocher : perpendiculaire |
| Tangente |  | Accrocher : tangente |
| Prolongement |  | Accrocher : prolongement |
| Parallèle |  | Accrocher : parallèle |
| Guides |  | Accrocher : guides |
| Milieu de deux points |  | Pendant un outil : le prochain point est le milieu de deux points cliqués (accrochés) |
| Depuis un point |  | Pendant un outil : cliquer un point de base, puis saisir le décalage (X, Y) du point voulu |
| Accrochage intuitif |  | Cotation : le curseur s'accroche aux points, milieux, centres et intersections même sans l'accrochage (F3) |
| Sur le contour |  | Accrocher : sur le contour |
| Grille |  | Accrocher : grille |
| Repérage | F11 | Repérage d'accrochage (F11) : survoler des points accrochés les retient ; le curseur s'accroche ensuite sur leurs verticales et horizontales, et à leurs croisements |
| Repérage polaire | Shift+F12 | Repérage polaire (Maj+F12) : depuis le dernier point cliqué, le curseur s'accroche aux angles multiples du pas (15° par défaut ; clic droit sur le bouton : changer le pas) |

## Vue

### Mode

| Commande | Raccourci | Rôle |
|---|---|---|
| Animation |  | Les corps de la pièce 3D en mouvement ; liaisons, course, sens et collisions dans sa fenêtre |

### Zoom

| Commande | Raccourci | Rôle |
|---|---|---|
| Tout voir | Ctrl+0, Home, Ctrl+À |  |
| Sélection |  | Zoom sur la sélection |
| Rapprocher | Ctrl+PgUp |  |
| Éloigner | Ctrl+PgDown |  |
| Actualiser | Ctrl+W, Ctrl+R |  |
| Zoom précédent |  | Revenir à la vue précédente (zoom, cadrage) |
| Zoom plaque |  | Cadrer la plaque |
| Zoom fenêtre |  |  |

### Contours

| Commande | Raccourci | Rôle |
|---|---|---|
| Sens | Ctrl+7, Ctrl+È | Sens des contours : fermés en vert (anti-horaire) ou en bleu (horaire), ouverts en noir ; flèche au départ et rang de chaque objet |
| Remplissage | Ctrl+9, Ctrl+Ç | Contours fermés remplis de la couleur de leur outil |
| Aperçu gravure |  | Traits à la largeur réelle de leur outil (table des outils) : repère les détails trop fins pour la fraise ou le laser |
| Grille | Ctrl+G |  |
| Points de départ |  | Le point de départ de chaque contour affiché (carré plein) |
| Points de contrôle |  | Les points de tous les contours affichés : carré pour un angle, rond pour un point lisse |

### Repères

| Commande | Raccourci | Rôle |
|---|---|---|
| Règles | Ctrl+Shift+R | Règles graduées ; glisser depuis une règle pose un guide |
| Effacer les guides |  | Supprimer tous les guides (un guide seul : le ramener sur une règle) |
| Repères… |  | La liste des repères du dessin, à modifier ; des repères répartis sur la plaque |
| Objet en repères |  | Chaque côté droit des objets sélectionnés devient un repère ; pour une courbe, les côtés de sa boîte |
| Origine |  | Repère de l'origine du dessin (X, Y) ; glisser depuis le coin des règles pour la déplacer |
| Placer l'origine… |  | Origine des coordonnées (règles, position F2, barre d'état) : coin ou centre de la plaque, centre de la sélection, valeurs saisies |
| Notes |  | Afficher les notes du dessin |
| Compteur |  | Temps passé sur le document (gardé dans le fichier) dans la barre d'état — pour un devis ; ne compte que pendant le travail (rien après 5 minutes sans action) |

### Affichage

| Commande | Raccourci | Rôle |
|---|---|---|
| Calques en onglets |  | Un onglet par calque au-dessus du plan de travail : choisir un calque le montre seul |
| Thème |  | 30 thèmes (5 clairs, 25 sombres, dont TypeEdit), les vôtres et ceux des plugins |
| Mode sombre |  | Passer du thème clair préféré au thème sombre préféré (F10 > Apparence) |
| Personnaliser |  | Personnaliser l'interface : thèmes sur aperçu, couleurs de l'interface et du plan de travail, import et export |
| Personnaliser le ruban |  | Onglets à soi, nommés et placés où l'on veut : vos commandes en groupes, au libellé choisi ; onglets affichés. Clic droit sur une commande du ruban : l'ajouter à un onglet à soi |
| Réduire le ruban | Ctrl+F1 | Ruban réduit aux onglets (un clic sur un onglet le déplie le temps d'une commande ; double-clic sur un onglet : réduire ou déplier) |
| Couleurs pour daltoniens |  | Parcours FAO et repères d'intersection dans des couleurs qui se distinguent sans le rouge et le vert (palette d'Okabe et Ito) |
| Plein écran | F12, Shift+F11 | VectorDrive sur tout l'écran, sans barre de titre ; F12 une 2e fois : la barre des tâches de Windows reste visible et utilisable ; une 3e fois : la fenêtre ; retenu au lancement suivant |
| Garder la barre des tâches |  | Plein écran : la barre des tâches de Windows reste visible et utilisable (VectorDrive sans cadre sur le reste de l'écran) |

## CAD

### Création

| Commande | Raccourci | Rôle |
|---|---|---|
| Sélection | Esc |  |
| Rectangle |  | Rectangle : glisser d'un coin à l'autre ; Ctrl : carré ; Maj : à partir du centre |
| Ellipse |  | Ellipse : glisser d'un coin à l'autre de sa boîte ; Ctrl : cercle ; Maj : centrée sur le premier point |
| Rectangle 3 points |  | Rectangle 3 points : deux clics pour un côté (il donne l'inclinaison), un troisième pour l'autre côté ; coins du rectangle par défaut |
| Trait |  |  |
| Polyligne |  |  |
| Polycourbe |  | Polycourbe : segments et arcs qui se suivent sans cassure. Tab : segments libres, arcs tangents, segments tangents ; Retour arrière : retire le dernier ; Entrée pour finir, clic sur le premier point pour la fermer |
| Bézier |  |  |
| Courbe par points |  | Courbe par points : chaque clic est un point de passage d'une courbe lisse ; double-clic ou Entrée pour finir, clic sur le premier point pour la fermer |
| Ligne double |  | Ligne double : deux traits parallèles, clics comme pour une polyligne ; Ctrl+clic sur l'outil : type de coins, espacement de chaque côté de l'axe, départ et fin de ligne |
| Ligne de coupure |  | Ligne de coupure : deux clics, le symbole de rupture (zigzag) au milieu du trait |
| Polygone |  | Polygone : glisser du centre vers un sommet (Ctrl : sommet en haut) ; Maj : deux points opposés ; Alt : vers le milieu d'un côté (polygone circonscrit) |
| Polygone par côté |  | Polygone par côté : deux clics, les bouts d'un côté ; le polygone (nombre de côtés du ruban) se pose à gauche du côté tracé, Ctrl : à droite |
| Étoile |  | Étoile : glisser du centre vers une pointe (Ctrl : pointe en haut) ; Maj : deux points opposés sur le cercle |
| Spirale |  |  |
| Arc 3 points |  | Arc 3 points : départ, passage, arrivée ; Maj sur le troisième clic : départ, arrivée, puis la courbure ; F2 : les points en chiffres |
| Couper un contour |  | Couper un contour : glisser un trait à travers des contours ouverts ou fermés (choisis, sinon tous ceux qu'il touche) ; ils sont coupés à chaque intersection, sans rien déplacer. Tab ou Maj : les contours fermés sont refermés le long du trait ; Ctrl : à 45° |
| Cercle 3 points |  |  |
| Arc centre, départ, fin |  | Arc centre, départ, fin : un clic au centre, un au départ (il donne le rayon), un pour la fin ; sens trigonométrique, Ctrl : sens horaire ; F2 : en chiffres |
| Cercle 2 points |  | Cercle 2 points : deux clics, les bouts d'un diamètre |
| Ellipse par axe |  | Ellipse par axe : deux clics, les bouts d'un axe (il donne l'inclinaison), puis un clic à la distance voulue du centre pour l'autre demi-axe |
| Cercle tangent |  | Cercle tangent : clic sur deux traits droits, cercles ou arcs, près des points de contact — cercle du rayon demandé tangent aux deux ; rayon 0 : un 3e clic, cercle tangent aux trois |
| Ligne de construction |  | Ligne de construction : un clic pour le point, un clic par ligne qui y passe (Maj : par 15°) — guide oblique infini, accrochage dessus et aux croisements (F3) ; double-clic pour la régler, ramenée sur une règle : supprimée |
| Marqueur |  |  |
| Crayon (formes reconnues) |  | Crayon : dessiner à main levée — le tracé devient le trait, le rectangle, l'ellipse ou le triangle esquissé, sinon une courbe lissée (Maj au lâcher : courbe lissée seulement) |
| Pinceau à aplat |  | Pinceau à aplat : glisser peint une surface pleine qui se fond avec les formes fermées de l'outil courant qu'elle touche ; [ et ] : taille |
| Oblong |  | Oblong (boutonnière) : longueur hors tout, largeur, angle — éditable ensuite |
| Anneau |  | Anneau : rayons extérieur et intérieur — éditable ensuite |
| Secteur |  | Secteur de couronne ou part de disque : rayons, angle de départ, ouverture — éditable ensuite |
| Engrenage |  | Engrenage à denture en développante : module, nombre de dents, angle de pression, alésage — éditable ensuite |
| Courbe symétrique (axe OX) |  | Courbe d'un seul tenant, symétrique par rapport à l'axe horizontal du centre de la plaque ; fermée par défaut, F pour l'ouvrir ; Ctrl ou Maj en déplaçant : un point en angle ou tangent |
| Courbe symétrique (axe OY) |  | Courbe d'un seul tenant, symétrique par rapport à l'axe vertical du centre de la plaque ; fermée par défaut, F pour l'ouvrir ; Ctrl ou Maj en déplaçant : un point en angle ou tangent |
| Courbe cyclique |  | Courbe d'un seul tenant, centrée sur la plaque et symétrique par rapport aux deux axes ; fermée par défaut, F pour l'ouvrir |
| Courbe symétrique (origine) |  | Courbe d'un seul tenant, symétrique par rapport au centre de la plaque ; fermée par défaut, F pour l'ouvrir |
| Dessin symétrique |  | Chaque forme dessinée reçoit son reflet par rapport à l'axe vertical du milieu de la plaque ; un trait qui touche l'axe est raccordé à son reflet |
| Symétrie cyclique |  | Chaque forme dessinée est répétée en rosace autour du centre de la plaque (nombre de copies réglable) |
| Flèche |  | Flèche en quatre clics : la base de la queue, la pointe, la taille de la pointe, l'épaisseur de la queue ; F2 ou Ctrl+clic : ses dimensions en chiffres |
| Tangentes |  | Droites tangentes à deux cercles sélectionnés, ou leur enveloppe (courroie, oblong) |
| Note |  | Note (post-it) sur le dessin : consigne pour l'atelier, jamais usinée ni exportée |
| Point par coordonnées… |  | Donner le point suivant de l'outil de dessin par ses coordonnées (absolues ou relatives) |

### Texte

| Commande | Raccourci | Rôle |
|---|---|---|
| Texte |  |  |
| Sur courbe |  | Poser le texte sélectionné sur la courbe sélectionnée, qui disparaît (Maj la garde) ; une courbe seule : un nouveau texte |
| En arc |  | Mettre en arc le texte sélectionné, ou un nouveau texte (sur le cercle sélectionné ou au centre de la vue) ; Ctrl+clic : par les angles |
| Dans un cadre |  | Texte ajusté dans un rectangle (rectangle sélectionné ou dimensions) |
| Dans une forme |  | Le texte coule dans une forme fermée, ligne après ligne, en évitant ses trous. Sélectionnez la forme, et le texte à y mettre s’il existe déjà. D’autres formes sélectionnées, plus petites : il les contourne |
| Déplacer sur la courbe |  | Déplacer un texte le long de sa courbe, à la souris ; F2 : depuis le départ de la courbe ou depuis sa position actuelle |
| Caractères |  | Liste des caractères d'une police : insérer un symbole (Ø, ±, °, ©…) dans le texte sélectionné |
| Reconnaître une police… |  | Trouver les polices du poste les plus proches de lettres en courbes sélectionnées, ou d'une image : la dernière capture d'écran, le presse-papiers, un fichier |
| Chasse fixe |  | Espacement fixe : chaque caractère dans une case de même largeur (numéros alignés) |
| Proportionnel |  | Espacement proportionnel, sans crénage |
| Typographique |  | Espacement typographique, avec crénage |
| Serré avec crénage |  | Crénage automatique, sans les espaces de part et d’autre des lettres |
| Serré |  | Sans crénage, ni les espaces de part et d’autre des lettres |
| Italique |  | Texte penché (12°) ou droit |
| Souligné |  | Texte souligné (une barre sous chaque ligne) ou non |
| Italique et souligné… |  | Angle de l'italique, position et épaisseur du souligné |
| Lettres… |  | Régler chaque lettre : crénage, décalage, hauteur, largeur, rotation, exposant et indice |
| Lettres à la souris |  | Clic : choisir une lettre du texte, glisser : la décaler. Flèches : décaler ; Alt+flèches : crénage ; + et − : taille ; Page préc. et suiv. : rotation ; Suppr : remettre à la normale ; double-clic : la fenêtre Lettres |
| Sur arcs multiples |  | Lignes de texte sur des arcs de même centre : rayon, angle, sens, déformation simple, radiale ou inclinée |
| En colonnes |  | Répartir les lignes du texte sélectionné en colonnes côte à côte |
| Rangées et colonnes |  | Texte en rangées et colonnes : largeur, alignement et marges par colonne, bordures ; le double-clic le rouvre |
| Texte variable |  | Ajoute |Nom| (variable, date ou heure) au texte sélectionné, ou un nouveau texte variable |
| Variables |  | Tableau des variables (une ligne par état), séries, import de données, état affiché |
| Produire les états |  | Un exemplaire de la sélection par ligne du tableau des variables, rangé sur la plaque ; les originaux sont masqués |
| Changer la police |  | Changer la police des textes sélectionnés (ou de tous les textes) |
| Ajouter une police SVG… |  | Une police au format SVG (les polices monotrait libres, Hershey par exemple) rejoint la liste des polices |
| Éditeur de polices |  | Dessiner une police, monotrait ou non, caractère par caractère, ou en modifier une : la sélection devient le caractère |
| Préréglages de texte… |  | Gestionnaire des préréglages de texte : créer, modifier chaque réglage, renommer, dupliquer, supprimer, importer, exporter |
| En courbes |  | Transformer les textes en courbes |
| Orthographe… |  | Relit les textes de la sélection, sinon de tout le dessin, avec le correcteur de Windows |
| Rechercher / remplacer |  | Rechercher et remplacer dans les textes (sélection, sinon tout le dessin) |
| Ponctuation typographique |  | Textes choisis (sinon tous) : guillemets « », apostrophe ’, points de suspension …, espaces insécables avant ; : ! ? |
| Réunir les textes |  | Réunir les textes choisis en un seul texte de plusieurs lignes, de haut en bas (textes d'une ligne d'un plan importé) : police, hauteur et interligne gardés |

### Mesure

| Commande | Raccourci | Rôle |
|---|---|---|
| Cote |  |  |
| Cote de longueur d'arc |  | Cote de longueur d'arc : clic sur un arc (ses morceaux réunis), clic pour placer l'arc de cote — longueur développée, symbole d'arc au-dessus du nombre ; Tab : autre type de cote |
| Cote radiale à ressaut |  | Cote radiale à ressaut : clic sur un cercle ou un arc, clic pour placer le texte, clic pour le départ de la ligne (centre hors de la feuille : grand rayon) — la ligne rejoint le rayon par un ressaut |
| Ressaut de cote |  | Ressaut (zigzag) sur la ligne des cotes linéaires sélectionnées : cote d'une longueur qui n'est pas à l'échelle du dessin ; position 0 : retiré |
| Cadre de tolérancement |  | Cadre de tolérance géométrique (planéité, localisation, battement…) avec sa valeur, la condition de matière et les références ; double-clic pour le modifier |
| Cote d'inspection |  | Cotes sélectionnées en cotes d'inspection : cadre autour de la valeur, libellé et taux d'inspection (aucune : retire l'inspection) |
| Espacer les cotes |  | Cotes linéaires parallèles sélectionnées à intervalle régulier à partir de la plus proche de l'objet (intervalle 0 : alignées sur elle) |
| Mesurer |  |  |
| Distance rectangle (X, Y, XY) | Shift+D | Distance rectangle (TypeEdit) : clic au départ, clic à l'arrivée — le rectangle des deux points, ses côtés X et Y et la diagonale XY (accrochage F3 conseillé) |
| Mesurer un rayon |  | Mesurer un rayon : clic sur un cercle, un arc ou une courbe — rayon et diamètre, angle et longueur d'un arc, rayon de courbure d'une courbe au point cliqué |
| Mesurer un angle |  | Mesurer un angle : clic sur deux traits droits, du côté de l'angle voulu ; ailleurs, trois clics — le sommet puis un point de chaque côté (F3 : accrochage aux points) |
| Cadre englobant | E | Rectangle juste autour de la sélection (ou de tout le dessin), sans marge, tout de suite |
| Cadre englobant… |  | Rectangle (ou ellipse) autour de la sélection, avec marge et coins arrondis |

### Mode Point

| Commande | Raccourci | Rôle |
|---|---|---|
| Mode Point |  |  |
| Supprimer point |  |  |
| Couper |  | Couper le contour au point sélectionné |
| Joindre |  | Joindre deux contours ouverts |
| En droite |  | Segments entre les points sélectionnés → droites |
| En courbe |  | Segments entre les points sélectionnés → courbes modifiables |
| Point sur courbe |  | Points hors courbe sélectionnés → en courbe : le tracé passe par eux |
| Hors courbe |  | Points en courbe sélectionnés → hors courbe : ils tirent la courbe sans qu'elle y passe |
| Lisser |  | Points sélectionnés lisses (poignées alignées) |
| Symétrique |  | Points sélectionnés symétriques (poignées alignées, même longueur) |
| Aligner H |  | Points sélectionnés à la même hauteur |
| Aligner V |  | Points sélectionnés à la même abscisse |
| Moyenne |  | Points sélectionnés réunis en un seul endroit : leur point moyen (puis Joindre pour souder deux bouts ouverts) |
| Point de départ |  | Mode Point : le point sélectionné devient le départ de son contour fermé, et l'usinage commencera là |
| Affiner |  | Un nouveau point au milieu de chaque segment (tracé inchangé) |
| Ajouter un point |  | Mode Point : cliquez sur le contour, un point rouge apparaît, puis ce bouton ou la touche + |
| Simplifier |  | Moins de points, à la précision choisie : celle-ci se règle avec Ctrl ou Maj |
| En segment |  | Mode Point, deux points d'un contour : la portion entre eux devient une seule droite (Maj : l'autre portion d'un contour fermé) |
| Portion en arc |  | Mode Point, deux points d'un contour : la portion entre eux devient l'arc de cercle qui passe par son milieu (Maj : l'autre portion d'un contour fermé) |
| En angle |  | Mode Point, deux points d'un contour : la portion entre eux devient un angle, à l'intersection des tangentes (Maj : l'autre portion d'un contour fermé) |
| Déplacer un contour |  | Glisser un contour d'un objet sans le décombiner (Ctrl : à 45°) |
| Projection verticale |  | Points sélectionnés projetés verticalement sur un repère (guide ou contour) : cliquez ensuite sur le repère |
| Projection horizontale |  | Points sélectionnés projetés horizontalement sur un repère (guide ou contour) : cliquez ensuite sur le repère |
| Projection orthogonale |  | Points sélectionnés amenés au point le plus proche d'un repère (guide ou contour) : cliquez ensuite sur le repère |

### Modeler

| Commande | Raccourci | Rôle |
|---|---|---|
| Couper-supprimer |  | Deux clics sur un contour : la portion entre eux est retirée. Fermé : de l'un à l'autre dans le sens horaire, Tab : l'autre portion |
| Effacer un contour |  | Un clic sur un contour le retire, sans décombiner l'objet ; Maj : l'original reste |
| Transformer en segment |  | Deux clics sur un contour : la portion entre eux devient une droite ; Tab : l'autre portion |
| Transformer en arc |  | Deux clics sur un contour, puis régler l'arc à la souris et cliquer ; Tab : l'autre portion |
| Transformer en courbe |  | Deux clics sur un contour, puis régler la courbe à la souris et cliquer ; Tab : l'autre portion |
| Transformer en angle |  | Deux clics sur un contour, puis placer le sommet de l'angle et cliquer ; Tab : l'autre portion |

### Tronquer

| Commande | Raccourci | Rôle |
|---|---|---|
| Tronquer |  |  |
| Prolonger |  |  |
| Étendre en arc |  | Étendre en arc : un clic près du bout d'un arc de cercle, puis un clic vers le point à atteindre, le premier que le cercle rencontre ou un suivant |
| Contour de zone |  | Contour de zone : cliquer dans une zone fermée par des traits (ouverts ou fermés, qui se croisent) crée sa forme, îlots en trous (Maj : sans les îlots) ; clic droit sur le bouton : écart toléré entre les traits |
| Raccord entre deux traits |  | Raccord entre deux traits : cliquer le 1er trait puis le 2e, du côté à garder — prolongés ou coupés et raccordés par un arc (rayon des congés ; Maj : coin vif) |
| Gomme |  | Gomme : glisser efface ce qu'elle couvre (formes de la sélection, sinon toutes) ; [ et ] : plus petite, plus grande |
| Emporte-pièce |  | Emporte-pièce : un clic retire d'un contour une longueur donnée (centrée sur le clic), ou ce que couvre un rectangle ou un cercle ; Tab : la forme ; [ et ] : la taille (formes seulement : un texte est à convertir en courbes d'abord) |
| Réglages de l'emporte-pièce… |  | Emporte-pièce : sa forme (segment, rectangle, cercle) et ses tailles |
| Chanfrein entre deux traits |  | Chanfrein entre deux traits : cliquer le 1er trait puis le 2e, du côté à garder — prolongés ou coupés et reliés par un chanfrein (taille des chanfreins ; Maj : coin vif) |

### Déformations

| Commande | Raccourci | Rôle |
|---|---|---|
| Zigzag |  | Faire onduler le tracé de part et d'autre de lui-même : pointes ou vagues arrondies |
| Rugosité |  | Écarter au hasard les points du tracé : bord irrégulier, effet tracé à la main |
| Contracter / dilater |  | Dilater : côtés bombés ; contracter : pointes vers l'extérieur |
| Torsion |  | Tourner le dessin, d'autant plus qu'on est près de son centre |
| Festons |  | Bord en festons : arcs réguliers bombés vers l'extérieur, qui se rejoignent aux coins (cadre de plaque, nuage de révision) |

### Dessin technique

| Commande | Raccourci | Rôle |
|---|---|---|
| Diviser (repères) |  | Repères en parts égales le long de la courbe choisie |
| Mesurer (repères) |  | Un repère tous les n mm le long de la courbe choisie |
| Allonger |  | Allonger ou raccourcir un contour ouvert : de Δ, jusqu'à une longueur, ou en pourcentage |
| Changer par un point |  | Cliquer un point : le bout le plus proche de chaque trait droit choisi y vient, chaque cercle choisi passe par lui (même centre), un texte choisi seul y est posé |
| Repères de centre |  | Une croix au centre de chaque cercle ou arc choisi (avec traits débordants au choix) |
| Ligne d'axe |  | Ligne d'axe : clic sur deux traits droits — un trait sur leur axe, du milieu des débuts au milieu des fins, qui déborde un peu ; continu ou en trait mixte (F10 › Dessin) |
| Traits de coupe |  | Traits de coupe aux coins et cibles de repérage (hirondelles) autour de la sélection, sinon de la plaque — pour recaler une découpe sur une impression |

### Symboles

| Commande | Raccourci | Rôle |
|---|---|---|
| Bibliothèque | Ctrl+Shift+Y | Panneau de la bibliothèque : symboles, DXF et dessins de l'atelier, rangés en dossiers |
| Bibliothèque (fenêtre) |  | Bibliothèque (TypeEdit : B) dans sa fenêtre, à tout l'écran : dossiers, grandes vignettes, aperçu ; de nouveau B pour la fermer |
| Créer un symbole |  | Enregistrer la sélection comme symbole TypeEdit (.smb) dans la bibliothèque |

### Métiers

| Commande | Raccourci | Rôle |
|---|---|---|
| Code-barres |  | DataMatrix, QR Code, Code 128, Code 39, EAN-13 |
| Plaque codée |  | Sur deux cadres sélectionnés : le code dans le plus grand, son texte lisible dans l'autre, chacun ajusté à son cadre ; le texte suit toujours le code |
| Création de texture |  | Un motif (chevrons, vagues, écailles… ou vos traits) répété par symétrie dans les contours fermés |
| Vectoriser |  | Contours d'une image noir et blanc (logo, tampon) : image sélectionnée ou fichier |
| Éditer l'image |  | Ouvrir l'image choisie dans l'éditeur d'images du poste ; à chaque enregistrement, elle est reprise dans le dessin, à sa place |
| Hachures |  | Remplir les contours fermés sélectionnés de traits parallèles (aplats au laser ou à la fraise) |
| Gribouillis |  | Remplir les formes fermées choisies d'un zigzag continu (gravure en un trait, sans remonter) |
| Braille |  | Texte en braille français (points à graver ou à percer) |
| Photo |  | Photo tramée : points ou lignes selon la densité |
| Cadran |  | Graduations et chiffres autour d'un centre (cercle sélectionné ou centre de la vue) |
| Règle graduée |  | Règle graduée numérotée, avec vernier au choix |
| Trous |  | Trous de perçage (objet Trou de TypeEdit) : cercles sélectionnés changés en trous, ou trou au centre de la vue |
| Tampon |  | Préparer un tampon encreur : cadre, bordure, épaulement, miroir, fond à graver (négatif) |
| Courbe par équation |  | Une courbe tirée de formules : x(t) et y(t), y = f(x) ou polaire ; rose, cœur, spirale… tout prêts |
| Guilloché |  | Motif de traits entrelacés, comme sur un billet ou un cadran : rosette, bande, spirographe |

## CAD

### Vues 3D

| Commande | Raccourci | Rôle |
|---|---|---|
| Vue graveur | Ctrl+4, Ctrl+' | Pièce en 3D vue de devant et d'en haut, comme depuis la machine |
| Vue isométrique | Ctrl+5, Ctrl+( | Pièce en 3D en vue isométrique |
| Vue YZ | Ctrl+2, Ctrl+É | Pièce en 3D vue de côté (plan YZ), sans perspective inclinée |
| Vue ZX | Ctrl+3, Ctrl+" | Pièce en 3D vue de face (plan ZX), sans perspective inclinée |
| Éclairage |  | Régler la direction de la lumière dans la vue 3D |

### Création

| Commande | Raccourci | Rôle |
|---|---|---|
| Galbe |  | Relief bombé des formes fermées sélectionnées (le galbe de TypeArt) : carte de hauteurs à usiner en Relief |
| Balayage |  | Balayer un profil le long d'un chemin (sélectionnez le chemin, puis le profil) : cadre, moulure, tube |
| Dôme |  | Dôme sur les marqueurs sélectionnés : gaussien, sphérique ou cloche de verre |
| Relief extrudé |  | L'intérieur des formes fermées sélectionnées décalé en Z (marche à flancs droits) |
| Relief de révolution |  | Une courbe tournée autour d'un axe : deux marqueurs, ou une droite, sélectionnés avec elle |
| Facette |  | Plan incliné par trois marqueurs (cotes données) dans les formes fermées sélectionnées |
| Balayage entre deux chemins |  | Profil tendu entre deux chemins (premier chemin, second, profil ; un second profil : passage de l'un à l'autre) |
| Mode prismatique |  | Des lettres ou des objets à Z constant, le profil sur leur bord. Sélectionnez le texte ou l’objet, puis le profil (une courbe ouverte) |
| Grille de déformation |  | Le relief déformé entre quatre courbes qui se touchent, ou dans un contour fermé, pour un décor en bandeau ou en arc. Sélectionnez le relief et les courbes |

### Combinaison

| Commande | Raccourci | Rôle |
|---|---|---|
| Remplacer |  | Mode de combinaison des reliefs : remplacer |
| Ajouter |  | Mode de combinaison des reliefs : ajouter |
| Soustraire |  | Mode de combinaison des reliefs : soustraire |
| Maximum |  | Mode de combinaison des reliefs : maximum |
| Minimum |  | Mode de combinaison des reliefs : minimum |
| Moyenne |  | Mode de combinaison des reliefs : moyenne |
| Limiter la modification |  | Les nouveaux reliefs ne se posent que sur le relief existant |
| Combiner les reliefs |  | Coller les reliefs choisis dans le premier (le relief courant), selon le mode de combinaison |
| Sonde de relief |  | Sonde de relief : clic = cote Z du relief en ce point ; second clic = profil (cotes mini et maxi, pente la plus forte) |

### Retouches

| Commande | Raccourci | Rôle |
|---|---|---|
| Lissage |  | Lisser un galbe : tout le galbe, ou la zone des formes sélectionnées avec lui |
| Recalage en Z |  | Amener le haut, le milieu ou le bas du relief à une cote (dans les formes fermées choisies avec lui, sinon partout) |
| Ajustement dynamique |  | Nouveau Z max. du relief et courbure de son profil (dans les formes fermées choisies avec lui, sinon partout) |
| Ajuster au volume |  | Étirer les hauteurs du relief entre un Z min. et un Z max. (dans les formes fermées choisies avec lui, sinon partout) |
| Inverser le relief |  | Miroir en Z : les bosses en creux, les creux en bosses (dans les formes fermées choisies avec lui, sinon partout) |
| Trancher |  | Garder le relief entre deux cotes (dans les formes fermées choisies avec lui, sinon partout) |
| Rehausser les détails |  | Accentuer les petits reliefs (masque flou) (dans les formes fermées choisies avec lui, sinon partout) |
| Bas-relief |  | Ramener le relief à une faible profondeur en gardant ses détails (dans les formes fermées choisies avec lui, sinon partout) |
| Remplir les trous |  | Combler les cuvettes fermées jusqu'à leur bord (dans les formes fermées choisies avec lui, sinon partout) |
| Bordure |  | Le relief choisi prolongé autour des formes fermées choisies, sur une largeur : dans la continuité de son bord, ou à plat à un Z donné (sans sortir du relief) |
| Facettes au bord |  | Autour du relief, une pente descend de son bord jusqu’à zéro : le bord à pic s’adoucit |
| Effacer une partie |  | Garder seulement le relief dans les formes fermées choisies (Ctrl : effacer celui de ces formes) |
| Extraire une partie |  | Le relief dans les formes fermées choisies devient un relief à part, recadré ; ôté de l'original (Ctrl : laissé dans l'original) |
| Tranches |  | Les contours du relief choisi à des cotes successives (courbes de niveau) — pour retrouver le contour d'un objet palpé |
| Poser |  | Poser le relief choisi en second sur le premier : point le plus bas ou plan de base au niveau du point le plus haut du dessous, ou plan de base qui suit la surface |
| Enrouler sur un relief |  | Le second relief choisi, enroulé sur le premier en gardant ses dimensions le long de la surface : parallèle, sphérique ou cylindrique, en une ou plusieurs copies |
| Aligner un plan à zéro |  | Relief palpé de travers : le plan passant par le relief sous trois marqueurs choisis est ramené à Z 0 (relief redressé) |
| Matrice/Poinçon |  | Poinçon et matrice (empreinte retournée, en creux) d'un relief, avec un jeu (dans les formes fermées choisies avec lui, sinon partout) |
| Adapter à un outil |  | Ce que l'outil choisi peut usiner : parois dépouillées, détails trop fins comblés (dans les formes fermées choisies avec lui, sinon partout) |
| Texture raccordable |  | Rendre le relief raccordable : ses bords opposés se raccordent en pavage |

### SculptArt

| Commande | Raccourci | Rôle |
|---|---|---|
| SculptArt |  | SculptArt : peindre sur un relief (ajouter, creuser, lisser, aplanir, bruit) ; réglages du pinceau : 3D > SculptArt > Pinceau |
| Pinceau… |  | Pinceau de SculptArt : type (ajouter, creuser, lisser, aplanir, bruit), rayon, force |

### Textures

| Commande | Raccourci | Rôle |
|---|---|---|
| Relief d'une image |  | Une image (photo, logo) en relief : du noir au blanc, des cotes choisies (PhotoArt) |
| Relief d'un modèle 3D |  | Une pièce 3D (STL, STEP, 3D XML) vue d'un côté devient un relief, combinable avec le relief choisi |
| Primitive 3D |  | Sphère, ellipsoïde, cône, cylindre couché, tore ou pavé en relief — sur les marqueurs choisis, au centre des objets choisis ou du relief choisi ; combinable avec le relief choisi |
| Dôme par profil |  | Le profil choisi (trait ouvert : X = distance à l'axe, Y = hauteur) tourné autour d'un axe vertical, au marqueur choisi (sinon à son point le plus à gauche), sur un tour ou une partie |
| Surface bilinéaire |  | Surface réglée par les hauteurs de ses quatre coins — sur l'encombrement des formes fermées choisies (dans leur intérieur), du relief choisi ou de la plaque |
| Texturing algorithmique |  | Texture fractale (standard, focale, rayures, concentrique) sur le relief ou dans les formes fermées choisies |
| Tissage |  | Fils entrelacés (deux nappes croisées) sur le relief ou dans les formes fermées choisies |
| Remplissage par texture |  | Répéter un petit relief (le motif) en pavage dans les formes fermées choisies, sur le relief choisi ou en nouveau relief |

### Duplication

| Commande | Raccourci | Rôle |
|---|---|---|
| Multicopie linéaire |  | Recopier le relief d'une zone (forme fermée choisie avec lui) en lignes et colonnes, dans le relief |
| Multicopie circulaire |  | Recopier le relief d'une zone autour d'un centre (marqueur, sinon le centre de la zone) |
| Perlage |  | Recopier le relief d'une zone le long d'une courbe choisie avec lui |

### Usinage

| Commande | Raccourci | Rôle |
|---|---|---|
| Relief |  | Nouveau parcours : relief (sur la sélection, sinon sur la couleur du calque actif) |
| Gamme relief |  | Nouveau parcours : gamme relief (sur la sélection, sinon sur la couleur du calque actif) |
| Finition 3D |  | Nouveau parcours : finition 3d (sur la sélection, sinon sur la couleur du calque actif) |

## Opérations

### Booléens

| Commande | Raccourci | Rôle |
|---|---|---|
| Union |  | Opération booléenne : union (référence : 1er objet sélectionné) ; Ctrl ou Maj : garder les originaux |
| Intersection |  | Opération booléenne : intersection (référence : 1er objet sélectionné) ; Ctrl ou Maj : garder les originaux |
| Différence |  | Opération booléenne : différence (référence : 1er objet sélectionné) ; Ctrl ou Maj : garder les originaux |
| Exclusion |  | Opération booléenne : exclusion (référence : 1er objet sélectionné) ; Ctrl ou Maj : garder les originaux |
| Diviser |  | Toutes les pièces délimitées par les contours qui se croisent (chacune à l'outil de la forme visible au-dessus) |
| Détourer |  | Supprimer les parties cachées par les formes du dessus |
| Fusionner |  | Détourer, puis réunir les pièces voisines du même outil |
| Recadrer |  | La forme du dessus sert de cadre aux autres, puis disparaît |
| Soustraire l'arrière |  | La forme du dessus moins toutes les autres |
| Concepteur de formes |  | Concepteur de formes : choisir des formes qui se recouvrent, puis glisser à travers leurs pièces pour les réunir (clic : une pièce à part ; Alt : supprimer les pièces touchées) |

### Contours

| Commande | Raccourci | Rôle |
|---|---|---|
| Décaler |  | Décalage des contours |
| Rogner |  | Couper ce qui dépasse du cadre fermé sélectionné en premier, ou sinon de la plaque ; Ctrl : le type de rognage |
| Ajuster dans le cadre |  | Mettre les objets sélectionnés à l'échelle, centrés dans le cadre sélectionné en premier |
| Poinçonner |  | La forme fermée sélectionnée en premier troue les autres objets (traits coupés à son bord, surfaces évidées) ; Ctrl : le type de perforage |
| Couteau |  | Couper les formes fermées sélectionnées le long du trait sélectionné en dernier (droite, polyligne, courbe ou bord d'une forme) |
| Ombrage |  | Ombre pleine (extrusion) ou portée des contours fermés sélectionnés, re-modifiable au double-clic |
| Enveloppe |  | Déformer la sélection (textes compris) en arc, arche, bombé, pincé, vague ou trapèze, re-modifiable au double-clic |
| Enveloppe par courbes |  | Déformer les objets entre quatre courbes qui se touchent, ou dans un contour fermé. Sélectionnez les objets, puis les courbes en dernier ; re-modifiable au double-clic |
| Courber le long d’un tracé |  | Le dessin suit une courbe et se déforme avec elle : étiré, à sa taille ou répété. Sélectionnez les objets puis, en dernier, le tracé. Re-modifiable au double-clic |
| Trait double |  | Remplacer chaque trait par deux traits parallèles (courbes parallèles exactes) |
| Pointillés |  | Changer les traits en vrais tirets d'un type de trait (découpe en pointillés, pliage, perforation) : types standard, fichier .lin ou motif à soi |
| Congés |  | Arrondir les coins (en Mode Point : les nœuds sélectionnés) |
| Chanfreins |  | Chanfreiner les coins (en Mode Point : les nœuds sélectionnés) |
| Coins réglables |  | Une poignée dans chaque angle des formes choisies : la tirer arrondit. Clic : choisir un coin ; Alt+clic : arrondi, inversé, chanfrein ; double-clic : le rayon au clavier ; Suppr : coin vif |
| Liquéfier |  | Un pinceau qui déforme les formes choisies, sinon toutes celles qu’il rencontre. Crochets : la taille du pinceau |
| Réglages du pinceau… |  | Liquéfier : ce que fait le pinceau, sa taille, sa force et le détail qu’il ajoute |
| Raccordement |  | Relier deux traits ouverts par un arc tangent (ou un coin vif si le rayon est nul), en les prolongeant ou en les coupant |
| Raccord en courbe |  | Relier les bouts les plus proches de deux traits ouverts (ou les deux bouts d'un trait) par une courbe dans leur prolongement, tangente ou lisse ; les traits restent entiers |
| Contour du trait |  | Remplacer un trait par le contour de son épaisseur |
| Largeur variable |  | Remplacer un trait par une bande de largeur variable : de la largeur de départ à celle d'arrivée, effilée aux deux bouts ou ondulée (pleins et déliés, feuilles, pointes) |
| Outil largeur |  | Sur un trait : clic, un point de largeur ; glisser, sa largeur (Alt : un seul côté ; Ctrl : le déplacer le long du trait) ; Suppr : le retirer ; Entrée ou double-clic : valider, le trait devient une bande pleine |
| Plume calligraphique |  | Les traits choisis, comme tracés par une plume plate : larges en travers de la plume, fins dans son sens |
| Intersections |  | Détecter les points d'intersection (sélection, sinon tout le dessin) et les supprimer : petites boucles, normalisation, réunion, contour extérieur, coupe aux intersections |
| Gomme à boucles |  | Supprimer les petites boucles où un contour se recoupe lui-même |
| Nettoyer les superpositions |  | Traits droits qui se recouvrent (bords dessinés deux fois, formes accolées) : fusionnés pour n'être gravés qu'une fois, par outil |
| Arcs et segments |  | Remplacer les courbes de Bézier par des arcs de cercle tangents et des droites |
| Approximation |  | Remplacer les suites de petits segments par des courbes lisses (DXF, vectorisation) |
| Courbe lisse… |  | Remplacer les contours choisis par une courbe lisse qui les approche, sans coin et à courbure continue : les détails au tracé plus court que la longueur de lissage s’effacent ; Maj : l’original reste |
| Segmentation |  | Remplacer les courbes par des segments de droite |

### Transformation

| Commande | Raccourci | Rôle |
|---|---|---|
| Miroir H |  | Symétrie gauche-droite (axe vertical ; « miroir vertical » de TypeEdit, M) ; Maj : garder l'original ; Ctrl : l'axe sur le côté droit |
| Miroir V |  | Symétrie haut-bas (axe horizontal ; « miroir horizontal » de TypeEdit, Maj+M) ; Maj sur le bouton : garder l'original ; Ctrl : l'axe à la base |
| Rotation 90° |  |  |
| Miroir sur axe |  | Symétrie des objets par rapport au trait droit, ou aux deux marqueurs, sélectionnés en dernier ; Ctrl ou Maj : garder les originaux |
| Rotation −90° |  |  |
| Rotation… | Shift+R | Tourner la sélection d'un angle quelconque |
| Déplacer… |  | Déplacer la sélection d'une distance donnée, ou en poser une copie |
| Répéter la transformation | Ctrl+Alt+T | Refait sur la sélection le dernier déplacement, la dernière rotation ou mise à l'échelle, à la souris ou au clavier |
| Répéter et copier | Ctrl+Alt+Shift+T | Comme Répéter la transformation, sur une copie : déplacer un objet, puis répéter autant de fois que de copies voulues |
| Transformer chaque objet… |  | Déplace, met à l'échelle ou tourne chaque objet sélectionné autour de lui-même |
| Axe vertical |  | Redresser : faire tourner la sélection autour d'un point (1er clic) pour qu'un autre point (2e clic) soit à sa verticale ; F3 : accrochage aux points |
| Axe horizontal |  | Redresser : faire tourner la sélection autour d'un point (1er clic) pour qu'un autre point (2e clic) soit à son horizontale ; F3 : accrochage aux points |
| Aligner par points |  | Aligner par points : 1er point source, sa destination, 2e point source, sa destination (Maj au dernier clic : à l'échelle ; Entrée après deux clics : déplacement seul) |
| Étirer |  | Étirer : deux coins d'une fenêtre de capture, puis un point de base et sa destination ; les nœuds dans la fenêtre bougent, les segments vers les autres s'étirent (formes de la sélection, sinon toutes) |
| Échelle par référence |  | Échelle par référence : point de base, fin de la longueur de référence, puis la nouvelle longueur (3e clic depuis le point de base, ou Entrée pour la saisir) |
| Rotation par référence |  | Rotation par référence : centre, direction de référence (un bord de l'objet), puis la direction voulue (3e clic, ou Entrée pour saisir l'angle) |

### Alignement

| Commande | Raccourci | Rôle |
|---|---|---|
| Gauche |  | Aligner : gauche |
| Centre H |  | Aligner : centre h |
| Droite |  | Aligner : droite |
| Haut |  | Aligner : haut |
| Centre V |  | Aligner : centre v |
| Bas |  | Aligner : bas |
| Centres |  | Aligner : centres |
| Gauche extérieur |  | Placer à gauche du premier objet sélectionné |
| Droite extérieur |  | Placer à droite du premier objet sélectionné |
| Haut extérieur |  | Placer au-dessus du premier objet sélectionné |
| Bas extérieur |  | Placer au-dessous du premier objet sélectionné |
| Centrer plaque |  | Centrer la sélection sur la plaque |
| Centrer sur l'origine | Alt+W | Centrer la sélection sur l'origine (TypeEdit : Alt+W) |
| Centrer plaque H |  | Centrer horizontalement la sélection sur la plaque |
| Centrer plaque V |  | Centrer verticalement la sélection sur la plaque |
| Plaque gauche |  | Chaque objet contre la marge gauche de la plaque |
| Plaque droite |  | Chaque objet contre la marge droite de la plaque |
| Plaque haut |  | Chaque objet contre la marge haute de la plaque |
| Plaque bas |  | Chaque objet contre la marge basse de la plaque |
| Répartir H |  | Espacements égaux (le premier et le dernier objet restent en place) |
| Répartir V |  | Espacements égaux (le premier et le dernier objet restent en place) |
| Centres H |  | Espacements égaux (le premier et le dernier objet restent en place) |
| Centres V |  | Espacements égaux (le premier et le dernier objet restent en place) |
| Espacer H |  | Objets placés de gauche à droite avec un écart imposé |
| Espacer V |  | Objets placés de bas en haut avec un écart imposé |
| Même largeur |  | Mettre les objets aux dimensions de l'objet sélectionné en premier |
| Même hauteur |  | Mettre les objets aux dimensions de l'objet sélectionné en premier |
| Même taille |  | Mettre les objets aux dimensions de l'objet sélectionné en premier |

### Contours

| Commande | Raccourci | Rôle |
|---|---|---|
| Fermer |  | Fermer les contours ouverts |
| Ouvrir |  | Ouvrir les contours fermés |
| Inverser le sens |  | Inverser le sens de parcours des contours sélectionnés |
| Superposés | À | Supprimer les contours superposés (doublons), tout de suite avec les derniers réglages ; Ctrl+clic : la fenêtre |
| Points doubles |  | Supprimer les points confondus des contours sélectionnés (segments de longueur nulle) |
| Points alignés |  | Supprimer les points alignés : droites consécutives fusionnées (DXF, contours vectorisés) |
| En cercles |  | Contours fermés presque ronds (polygones d'un DXF…) remplacés par des cercles exacts |
| Convertir des courbes |  | Remplacer chaque contour sélectionné par le cercle, l'ellipse ou le rectangle le plus proche ; Maj : l'original reste |
| Raccorder |  | Raccorder les contours ouverts dont les extrémités se touchent (import DXF…) et fermer les boucles ; Ctrl+clic : les distances |
| Décomposer |  | Chaque segment des objets sélectionnés devient un trait séparé |
| Supprimer des contours |  | Retirer les trous, les contours extérieurs ou les contours plus petits qu'une taille |

### Duplication

| Commande | Raccourci | Rôle |
|---|---|---|
| Dupliquer | Ctrl+Shift+D | Duplication linéaire, en grille ou circulaire |
| Copie liée | Alt+D | Une copie qui suit la forme de son original : modifier l’original modifie ses copies ; chacune garde sa place |
| Délier la copie | Alt+Shift+D | La copie liée redevient un objet indépendant |
| Sélectionner l’original |  | Sélectionne l’original de la copie liée |
| Duplication homothétique |  | Copies le long d'une courbe, de la taille d'un objet à celle d'un autre (sélection : objet de départ, objet de fin, puis la courbe) |
| Duplication libre |  | Duplication libre : la sélection suit le pointeur ; chaque clic pose une copie (son centre au point cliqué) ; Échap pour finir |
| Duplication linéaire |  | Le nombre de colonnes et de rangées, puis glisser : les copies suivent en pointillés ; Tab : la dernière au pointeur ; F2 : en chiffres |
| Duplication circulaire |  | Le nombre d'exemplaires, puis glisser jusqu'au centre du cercle (accrochage F3 compris) ; F2 : en chiffres |
| Interpoler entre deux objets |  | Les formes de passage entre deux formes sélectionnées, dans l'ordre de sélection, à leurs places |
| Multicopie |  | Remplir la plaque avec le plus grand nombre d'exemplaires de la sélection |
| Imbriquer |  | Ranger les objets sélectionnés sur la plaque au plus serré (plaques suivantes à droite si besoin) |
| Copie imbriquée |  | Autant d’exemplaires qu’il faut de chaque objet, rangés sur autant de plaques ou de plans qu’il en faut : nombre par objet, point de départ, direction |
| Imbriquer dans un contour |  | Les objets se rangent dans un contour fermé, selon leur vraie forme. Sélectionnez d’abord le contour, puis les objets. Dans un groupe ou une combinaison : contour après contour |
| Copier dans une forme |  | Des exemplaires des objets remplissent une forme choisie, selon leur vraie forme. Sélectionnez les objets puis, en dernier, la forme à remplir |
| Restant de plaque |  | La partie de la plaque que les objets laissent libre devient une forme, sur son plan : prête pour une autre imbrication ou à garder dans la bibliothèque |
| Découper la matière restante |  | Une grille de lignes de découpe sur ce qui reste de la plaque, pour la faire tomber en petits morceaux : autour de la sélection, sinon du plan actif |
| Rapport d’imbrication |  | Un PDF : les réglages de la dernière imbrication, puis chaque plan rempli, avec ses surfaces et son dessin |
| Marqueterie |  | Formes mâles et femelles pour la marqueterie ou l'incrustation, chacune sur son plan |
| LED |  | Positions des diodes d'une enseigne : sur les contours sélectionnés (écart entre axes ou nombre par contour, angles) ou en grille à l'intérieur |
| Script |  | Dessiner avec un script en VBScript : les mêmes fonctions que les scripts de forme de TypeEdit (NewCurve, MoveTo, LineTo, ArcHTo, ArcTTo, ClosePath, DbApi, WndScriptApi) |
| Esquisse contrainte… |  | Dessiner avec des contraintes et des cotes : horizontal, tangent, égal, 40 mm… La figure se recalcule. Double-clic pour la reprendre |
| Perforer |  | Trous ronds en quinconce ou en grille carrée dans les contours fermés choisis (les découpes restent libres), à une marge des bords et des traits ouverts choisis, comme des axes de pli |

### Mesure

| Commande | Raccourci | Rôle |
|---|---|---|
| Vérifier |  | Vérifier le dessin avant gravure : hors plaque, contours presque fermés, doublons, poussières… |
| Purger |  | Retirer ce qui ne grave rien : formes et textes vides, groupes vides, calques vides |
| Périmètre |  | Mesurer le périmètre |
| Surface |  | Surface des contours fermés |
| Propriétés de masse |  | Aire, périmètre, centre de gravité, moments d'inertie des formes fermées choisies |
| Coter | Shift+C | Maj+C : une cote choisie → ses réglages ; des objets choisis (un cadre…) → leurs cotes automatiques (réglages et modèles) ; rien de choisi → cote entre deux points (Tab : autre type de cote) |
| Cotation rapide |  | Coter d'un coup les objets choisis : positions en X dessous et en Y à gauche (centres des cercles, coins des autres), en chaîne ou depuis une ligne de base |

## Design 3D

### Créer

| Commande | Raccourci | Rôle |
|---|---|---|
| Extrusion |  | Les formes fermées choisies tirées en volumes (hauteur, angle de dépouille, hauteur de départ) ; les trous restent des trous. D'un côté, symétrique, des deux côtés ou à travers les volumes choisis ; nouveaux volumes, ou réunis aux volumes choisis, soustraits ou en commun avec eux |
| Révolution |  | Les formes fermées choisies tournées autour d'un axe (deux marqueurs, ou une droite choisie avec elles ; sinon la verticale de leur point le plus à gauche) |
| Balayage 3D |  | Profils fermés tirés le long d'un chemin (choisir le chemin d'abord, puis les profils) : tube, moulure, rampe ; torsion et échelle d'arrivée en option |
| Lissage 3D |  | Volume passant par les contours fermés choisis, posés l'un au-dessus de l'autre dans l'ordre du choix (bas d'abord) ; réglé ou arrondi |
| Pavé |  | Volume : pavé (longueur, largeur, hauteur) — sur les marqueurs choisis, au centre des objets choisis, sinon au centre de la plaque |
| Coin |  | Volume : coin — pavé coupé en biais, pleine hauteur d'un côté — sur les marqueurs choisis, au centre des objets choisis, sinon au centre de la plaque |
| Cylindre |  | Volume : cylindre d'axe vertical — sur les marqueurs choisis, au centre des objets choisis, sinon au centre de la plaque |
| Cône |  | Volume : cône ou tronc de cône (rayon du dessus) — sur les marqueurs choisis, au centre des objets choisis, sinon au centre de la plaque |
| Sphère |  | Volume : sphère — sur les marqueurs choisis, au centre des objets choisis, sinon au centre de la plaque |
| Pyramide |  | Volume : pyramide ou tronc, nombre de côtés au choix — sur les marqueurs choisis, au centre des objets choisis, sinon au centre de la plaque |
| Tore |  | Volume : tore (anneau) — sur les marqueurs choisis, au centre des objets choisis, sinon au centre de la plaque |
| Mur |  | Mur de largeur et de hauteur données le long des traits choisis (à gauche, au milieu ou à droite du trait) |
| Tube |  | Tube plein ou creux (diamètre, paroi) le long des traits choisis, posé sur le plan ou à une hauteur donnée |
| Profilé |  | Profilés (plat, rond, tubes, cornière, U, I) couchés le long des traits choisis, coins en onglet, ou en poteaux sur les marqueurs choisis |
| Ressort |  | Ressort d'axe vertical : section ronde ou carrée enroulée en hélice (diamètre, pas, tours), sur les marqueurs ou les cercles choisis (leur diamètre), sinon au centre de la plaque |
| Filetage |  | Filetage ISO modélisé : tige filetée sur les marqueurs ou les cercles choisis, ou taraudage du volume choisi à ces endroits (M8, M8x1… ; vide : d'après le diamètre du cercle) |
| Perçage 3D |  | Perçages dans le volume choisi, depuis son dessus, sur les marqueurs ou les cercles choisis (leur diamètre) : simple, lamé ou fraisé ; borgne (pointe de foret en option) ou débouchant |
| Nervure |  | Mur d'épaisseur donnée le long des traits choisis, réuni au volume choisi : du dessous jusqu'à son dessus (ou une hauteur), prolongé d'une paroi à l'autre |
| Relief sur cylindre |  | Les formes fermées et les textes choisis, dessinés au-dessus d'un volume cylindrique couché (axe X ou Y), enroulés sur lui : en relief ou gravés |

### Modifier

| Commande | Raccourci | Rôle |
|---|---|---|
| Tirer / pousser |  | Les formes fermées choisies avec un volume, posées sur son dessus : tirées vers le haut (ajoutées) ou poussées dans la matière (creusées) |
| Historique… |  | Les étapes du volume choisi : reprendre un réglage ou une esquisse, suspendre une étape. Le volume se recalcule, à sa place |
| Coque |  | Les volumes choisis évidés : parois d'épaisseur donnée, prises dedans, dehors ou des deux côtés ; fermés ou ouverts d'un ou de plusieurs côtés (dessus, dessous, X, Y) |
| Arrondir les arêtes |  | Toutes les arêtes vives des volumes choisis arrondies au rayon donné (saillantes, et rentrantes si voulu) |
| Congés et chanfreins… |  | Arrondir ou chanfreiner les seules arêtes qu’on clique sur le volume |
| Dépouille… |  | Pencher les faces qu’on clique sur le volume, pour qu’il sorte du moule |
| Déplacer des faces… |  | Changer un diamètre, une profondeur, ou déplacer un perçage, en cliquant ses faces sur le volume |
| Supprimer des faces… |  | Boucher un perçage, effacer une poche ou un bossage, en cliquant ses faces sur le volume |
| Décaler le volume |  | Les volumes choisis grossis (arêtes arrondies) ou amincis d'une distance donnée |
| Lisser le maillage |  | Les volumes choisis lissés : facettes subdivisées, arêtes vives gardées au-delà d'un angle |
| Couper |  | Les volumes choisis coupés par un plan horizontal (Z), vertical (X, Y) ou vertical par un trait choisi avec eux ; garder un côté ou les deux |
| Séparer |  | Les corps disjoints d'un volume en volumes à part |
| Déplacer en Z |  | Monter ou descendre les volumes choisis |
| Aligner |  | Les volumes choisis alignés sur le premier choisi, qui ne bouge pas : côtés ou centres alignés, contre lui, posés dessus ou dessous, axe par axe |
| Rotation 3D |  | Les volumes choisis tournés autour d'un axe X, Y ou Z passant par leur centre |
| Permuter les plans |  | X Y Z devient Z X Y à chaque clic, sur place : trois clics rendent la pièce d'origine. Avec Maj, l'original reste et le résultat se pose à côté |
| Échelle 3D |  | Les volumes choisis mis à l'échelle, d'un même facteur ou par axe (compensation de retrait…), autour du centre de leur dessous, de leur centre ou de l'origine |
| Symétrie en Z |  | Les volumes choisis retournés par un plan horizontal (copie possible) |
| Réseau en Z |  | Copies des volumes choisis empilées en hauteur (nombre, pas, rotation de l'une à l'autre : escalier tournant…) |

### Combiner

| Commande | Raccourci | Rôle |
|---|---|---|
| Union |  | Les volumes choisis réunis en un seul |
| Soustraction |  | Le premier volume choisi, moins les suivants |
| Intersection |  | La partie commune aux volumes choisis |
| Cellules |  | Les morceaux délimités par les volumes choisis (dans certains, hors des autres) et les vides qu'ils enferment (empreinte d'un moule fermé), en volumes à part |

### Tôlerie

| Commande | Raccourci | Rôle |
|---|---|---|
| Tôle pliée |  | Tôle pliée debout le long des chaînes de traits droits choisies, plis au rayon intérieur, et son développé à plat (facteur K) avec les axes de pli |
| Bac en tôle |  | Bac en tôle dans les contours convexes choisis : fond plat, bord tombé relevé à 90° sur chaque côté, coins ouverts, et son développé en croix (facteur K) avec les axes de pli |
| Plier la tôle |  | Le flan dessiné à plat (contours fermés choisis, trous compris) plié le long des traits choisis, au rayon intérieur, du côté le plus petit de chaque trait ; la zone de pli suit le facteur K |

### Plasturgie

| Commande | Raccourci | Rôle |
|---|---|---|
| Bossage |  | Bossage plastique sur le volume choisi, posé sur le dessus de la matière aux marqueurs ou aux cercles choisis : fût en dépouille, trou, nervures rayonnantes |
| Lèvre ou rainure |  | Lèvre en relief ou rainure creusée le long du bord des volumes coqués ouverts choisis, contre l'arête intérieure ou extérieure : la lèvre d'une moitié entre dans la rainure de l'autre |
| Clip |  | Clips à crochet aux marqueurs choisis : bras vertical en porte-à-faux posé sur le dessus du volume choisi et réuni à lui, ou volume à part |
| Appui |  | Appuis aux marqueurs choisis : plots ronds ou rectangulaires, pleins ou creux, en dépouille, posés sur le dessus du volume choisi et réunis à lui, ou volumes à part |

### Inspecter

| Commande | Raccourci | Rôle |
|---|---|---|
| Propriétés de masse |  | Volume, aire, centre de gravité, encombrement et masse des volumes choisis |
| Volume englobant |  | Pavé ou cylindre autour des volumes choisis, grossi d'une marge : brut de la pièce |
| Section |  | Contour 2D des volumes choisis à une hauteur donnée |
| Vue à plat |  | Contour 2D des volumes choisis vus de dessus, de face ou de côté, posé à droite d'eux |
| Interférence |  | Les volumes choisis qui se chevauchent : volume commun de chaque paire (et en volumes) |
| Jeu entre volumes |  | Les volumes choisis qui se chevauchent, se touchent ou sont plus proches qu'un jeu donné (distance et lieu), et le plus proche voisin de chacun |
| Comparer deux volumes |  | Deux versions d'une pièce posées l'une sur l'autre : écart des surfaces (plus grand, moyen, lieu) et régions de matière du premier seulement ou du second seulement |
| Analyse de surface |  | La pièce 3D en couleurs : dépouille de ses faces vers une direction de démoulage (vert, jaune, rouge), ou faces atteintes le long d'une direction, outil vertical ou démoulage (vert, rouge) |

### Échanges

| Commande | Raccourci | Rôle |
|---|---|---|
| Importer un volume |  | Un fichier STL (maillage fermé) ajouté au dessin comme volume |
| Volume en relief |  | Les volumes choisis vus de dessus en relief (carte de hauteurs) — à usiner avec les parcours 3D (Relief, Finition) |
| Relief en volume |  | Les reliefs choisis en volumes (avec un socle) — pour les booléens et l'export STL |

## Design STEP

### Générateurs

| Commande | Raccourci | Rôle |
|---|---|---|
| Générer une pièce STEP |  | Vis, écrous, rondelles, goupilles, roulements, clavettes, roues dentées, barres, plaques percées, éléments de moule : une pièce STEP en vraies faces, d'après les normes |
| Visserie |  | Vis CHC, H, FHC, BHC, STHC, écrous, rondelles, goupilles (normes ISO) |
| Transmission |  | Roulements rigides à billes, clavettes, roues dentées droites |
| Brut et profilés |  | Barres, tubes, profilés, plaques percées, entretoises, bagues |
| Éléments de moule |  | Éjecteurs, colonnes et douilles de guidage, bagues de centrage |
| Bridage |  | Brides de serrage, cales étagées, mors doux, goujons, écrous pour rainure en T |
| Modifier la pièce générée… |  | La pièce du dessin choisie, ajoutée par les générateurs, rouverte avec ses valeurs : la modifier puis la remplacer à sa place |
| Pièce du dessin… |  | Les formes fermées choisies dans le dessin (et les textes) en pièce STEP à vraies faces : épaisseur, contours intérieurs en trous débouchants ou en poches ; une pièce par bord |
| Pièce tournée du dessin… |  | Un demi-profil fermé choisi dans le dessin, tourné autour du trait droit choisi avec lui (sinon de son bord gauche) : pièce STEP de révolution à vraies faces |

### Sélection 3D

| Commande | Raccourci | Rôle |
|---|---|---|
| Faces |  | Un clic dans la vue 3D choisit une face (Ctrl ou Maj : plusieurs, un second clic retire) |
| Faces semblables |  | Dans la vue 3D, toutes les faces comme celles choisies : trous de même diamètre, faces coplanaires, fraisures ou congés identiques |
| Faces parallèles |  | Un plan : tous les plans de même normale, à toute cote (les fonds tournés vers l'outil) ; un cylindre : tous ceux d'axe parallèle (les trous percés dans ce sens) |
| Faces coaxiales |  | Un cylindre, un cône ou une sphère : toutes les faces du même axe et les fonds plats entre elles (un trou entier : passage, lamage, fraisure, fond ; un arbre entier) |
| Faces tangentes |  | De proche en proche, les faces qui suivent celles choisies sans arête vive : un bord arrondi (côtés et congés des coins), une chaîne de congés |
| Faces du corps |  | Toutes les faces des corps des faces choisies (une partie d'un moule) |
| Inverser dans le corps |  | Les faces des corps choisis qui ne sont pas choisies : le reste d'une pièce (tout sauf les fonds déjà usinés, sauf un trou) |
| Mesurer la sélection |  | Les faces choisies dans la vue 3D décrites (diamètre, axe, normale, aire) ; pour deux faces, leur distance ou leur angle |
| Effacer la sélection |  | Plus aucune face ni aucun contour choisis (Échap dans la vue 3D) |

### Modifier un STEP

| Commande | Raccourci | Rôle |
|---|---|---|
| Corps d'un STEP… |  | Les corps d'un fichier STEP (la pièce 3D du dessin, sinon un fichier à choisir) : extraire, un fichier par corps (un moule en trois parties : trois STEP), déplacer ; géométrie exacte |
| Réunir des STEP… |  | Plusieurs fichiers STEP réunis en une seule pièce, chaque corps à sa place |
| Répéter des corps… |  | Les corps d'un STEP (la pièce 3D du dessin, le corps choisi seul) copiés en ligne au pas donné, ou en rond autour de la verticale, dans un nouveau STEP ; géométrie exacte |
| Vis dans ce trou… |  | La paroi d'un trou choisie dans la vue 3D d'une pièce STEP : le trou reconnu (passage, lamé, fraisé, taraudé), la vis normalisée proposée et posée, enregistrée seule ou avec la pièce |
| Pièce dans ce trou… |  | La paroi d'un alésage choisie dans la vue 3D d'une pièce STEP : goupille, roulement, bague, douille, colonne, éjecteur ou bague de centrage proposé à son diamètre et posé, enregistré seul ou avec la pièce |

### Dépôt STEP

| Commande | Raccourci | Rôle |
|---|---|---|
| Parcourir le dépôt |  | Le dépôt STEP dans le navigateur à vignettes : ouvrir une pièce ou la poser dans le dessin |
| Dossier du dépôt… |  | Choisir le dossier où les pièces STEP sont enregistrées et rangées |

## Mise en forme

### Texte

| Commande | Raccourci | Rôle |
|---|---|---|
| Retour |  | Fin du texte : l'outil Sélection, et l'onglet d'avant |
| Texte |  |  |

### Général

| Commande | Raccourci | Rôle |
|---|---|---|
| Caractères |  | Liste des caractères d'une police : insérer un symbole (Ø, ±, °, ©…) dans le texte sélectionné |

### Police

| Commande | Raccourci | Rôle |
|---|---|---|
| Reconnaître une police… |  | Trouver les polices du poste les plus proches de lettres en courbes sélectionnées, ou d'une image : la dernière capture d'écran, le presse-papiers, un fichier |

### Position du texte

| Commande | Raccourci | Rôle |
|---|---|---|
| Gauche |  | Alignement des lignes des textes sélectionnés |
| Centré |  | Alignement des lignes des textes sélectionnés |
| Droite |  | Alignement des lignes des textes sélectionnés |
| Justifié |  | Lignes justifiées : chacune étirée à la largeur de la plus longue (écart réparti entre les lettres) |
| Ressort |  | Ressort (touche Tab pendant la frappe) : l'espace libre de la ligne — jusqu'à la largeur imposée, sinon la plus longue ligne — est partagé entre ses ressorts, pour aligner, centrer, répartir |
| Texte vertical |  | Lettres les unes sous les autres (ou retour à l'horizontale) |
| De droite à gauche |  | Texte de droite à gauche, ou retour : ordre d’affichage et formes liées de l’arabe, si la police les porte |
| MAJUSCULES |  | Textes en majuscules |
| minuscules |  | Textes en minuscules |
| Majuscule Aux Mots |  | Première lettre de chaque mot en majuscule |
| Petites majuscules |  | Minuscules en capitales réduites (ou retour aux minuscules), le texte restant modifiable |
| Casse initiale |  | Remettre le texte dans la casse qu’il avait avant les changements de casse |

### Ligne de base

| Commande | Raccourci | Rôle |
|---|---|---|
| Sur la ligne de base |  | Texte posé sur sa ligne de base (comme d'habitude) |
| Sous la ligne de base |  | Texte sous sa ligne de base : le haut des capitales vient sur la ligne |
| Interligne fixe |  | En mm d’une ligne de base à l’autre, quelle que soit la hauteur du texte |
| Interligne proportionnel |  | Un pourcentage de la hauteur du texte, ajouté à elle ; il suit la hauteur |
| Interligne typographique |  | Un pourcentage de la hauteur complète de la police, jambages compris ; il suit la hauteur |
| Compression ligne |  | Longueur maximale : chaque ligne trop longue est resserrée seule |
| Compression paragraphe |  | Longueur maximale : toutes les lignes resserrées du même facteur, celui de la plus longue |
| Compression globale |  | Toutes les lignes resserrées du même facteur, pour tenir dans un pourcentage de la longueur de la plus longue |

### Outils

| Commande | Raccourci | Rôle |
|---|---|---|
| Rechercher / remplacer |  | Rechercher et remplacer dans les textes (sélection, sinon tout le dessin) |
| Changer la police |  | Changer la police des textes sélectionnés (ou de tous les textes) |
| Reproduire la mise en forme |  | La mise en forme du premier texte sélectionné va aux autres (un seul : aux textes cliqués ensuite) |

### Préréglages

| Commande | Raccourci | Rôle |
|---|---|---|
| Enregistrer le préréglage… |  | La mise en forme du texte sélectionné (sans sélection : celle des nouveaux textes) enregistrée sous un nom |
| Préréglages de texte… |  | Gestionnaire des préréglages de texte : créer, modifier chaque réglage, renommer, dupliquer, supprimer, importer, exporter |

## FAO 2D

### Usinage

| Commande | Raccourci | Rôle |
|---|---|---|
| Panneau FAO |  | Outils d'usinage, opérations, parcours, post-traitement |
| Bibliothèque d'outils |  | Outils : bibliothèque, cotes, catalogues en ligne, dessins DXF et STEP, import et export (TypeEdit, NeoDrive, CSV, ISO 13399) |
| Calculer les parcours |  | Calculer les parcours des opérations actives |
| Post-traiter… |  | Écrire le programme machine (à simuler avant usinage) |
| Parcellisation… |  | Travail plus grand que la plaque ou que la table : le découper en panneaux, un programme par panneau |
| Pontets à la main |  | Pontets à la main : un clic près du contour d'une forme fermée pose un pontet (pris par le détourage, largeur et hauteur de l'opération) ; un clic sur un pontet l'ôte |
| Entrée et sortie d'un contour |  | Entrée et sortie d'un contour : un clic près d'un contour fermé y met le départ et demande son entrée et sa sortie, à la place de celles de l'opération (0 : sans) ; un clic sur un repère les change ou les retire |
| Opérations en plein écran |  | La fenêtre des outils, opérations et parcours sur tout le plan de travail, opacité réglable pour voir le dessin dessous ; la molette zoome toujours le dessin |
| Créer un parcours en plein écran |  | La fenêtre « Créer un parcours » sur tout le plan de travail, opacité réglable ; la molette zoome toujours le dessin |

### Voir et simuler

| Commande | Raccourci | Rôle |
|---|---|---|
| Trajectoires 2D |  | Parcours calculés sur le dessin |
| Simuler l'usinage |  | Simulation d'enlèvement de matière des parcours cochés |
| Mesure de volume |  | Volume des reliefs choisis, sinon volume de matière enlevé par les parcours cochés (simulation) |
| Outil spécial |  | Créer un outil de forme : sélectionner son profil (trait ouvert, de la pointe vers la queue), puis deux marqueurs l'un au-dessus de l'autre sur l'axe de l'outil |
| Projection locale |  | Poser le parcours de l'opération choisie sur une pièce 3D le long d'une courbe guide : sélectionner la courbe (sur la vue de dessus de la pièce), puis cette commande |
| Parcours en dessin |  | Les trajectoires cochées (centre de l'outil) deviennent des traits du dessin, dans un calque « Parcours », pour les retoucher ou les exporter |
| Fiche de réglage |  | Feuille d'atelier à imprimer : plaque, outils, opérations dans l'ordre, temps estimés, avertissements et vue des trajectoires (HTML) |
| Reste de matière |  | Aperçu : les zones des formes fermées choisies que l'outil ne peut pas vider (angles, passages étroits), posées en surfaces sur un calque à part |
| Lire un programme ISO… |  | Un programme ISO (G-code) d'une autre machine ou d'un autre logiciel affiché parmi les parcours, pour le voir et le simuler avant de le lancer |
| Visualiser un programme en 3D… |  | Programme machine (ISO, Heidenhain, et les langages des plugins : SimPL…) lu et montré en 3D filaire, seul, pour le vérifier avant de le lancer |

### Parcours

| Commande | Raccourci | Rôle |
|---|---|---|
| Parcours TypeEdit… |  | Afficher les parcours TypeEdit (.000, .001…) d'un VND |
| Effacer les parcours |  |  |
| Enroulement cylindrique |  | Enrouler le parcours de l'opération choisie sur une pièce cylindrique couchée (machine 3 axes : Z suit la surface) |
| Enroulement conique |  | Enrouler le parcours de l'opération choisie sur une pièce conique couchée (machine 3 axes : Z suit la surface) |
| Projection parallèle |  | Projeter le parcours de l'opération choisie sur la surface d'une pièce STEP (machine 3 axes : Z suit la surface) |
| Fusionner les parcours |  | Les opérations du même outil que celle choisie viennent à sa suite : moins de changements d'outil |

### Découpe

| Commande | Raccourci | Rôle |
|---|---|---|
| Cercles en quinconce |  | Stratégie de découpe : géométrie de découpe d'une plaque en pièces (traits communs entre pièces voisines) |
| Octogones |  | Stratégie de découpe : géométrie de découpe d'une plaque en pièces (traits communs entre pièces voisines) |
| Parts de gâteau |  | Stratégie de découpe : géométrie de découpe d'une plaque en pièces (traits communs entre pièces voisines) |
| Rectangles |  | Stratégie de découpe : géométrie de découpe d'une plaque en pièces (traits communs entre pièces voisines) |
| Triangles |  | Stratégie de découpe : géométrie de découpe d'une plaque en pièces (traits communs entre pièces voisines) |
| Rondelle |  | Stratégie de découpe : géométrie de découpe d'une plaque en pièces (traits communs entre pièces voisines) |

## FAO 3D

### Pièce 3D

| Commande | Raccourci | Rôle |
|---|---|---|
| Placer la pièce 3D |  | Pièce STEP, STL ou 3D XML : face tournée vers l'outil, rotation, position sur la plaque — pour la vue de dessus, la vue 3D et l'usinage 3D |
| Brut… |  | Bloc, barre ronde ou plaque d'où la pièce 3D est usinée |
| Bridage… |  | Étau, mandrin, brides, cales de la prise montrée dans la vue 3D |
| En volumes |  | Chaque corps de la pièce devient un volume du dessin (maillage réparé), à modifier avec les outils 3D puis à usiner |

### Clic dans la vue

| Commande | Raccourci | Rôle |
|---|---|---|
| Faces |  | Un clic dans la vue 3D choisit une face (Ctrl ou Maj : plusieurs, un second clic retire) |
| Contours fermés |  | Un clic dans la vue 3D choisit le contour fermé le plus proche (Ctrl ou Maj : plusieurs) |
| Points et cotes |  | Un clic dans la vue 3D montre le point visé et ses cotes |
| Effacer la sélection |  | Plus aucune face ni aucun contour choisis (Échap dans la vue 3D) |

### Usinage 3D

| Commande | Raccourci | Rôle |
|---|---|---|
| Automatisme… |  | Ébauche, demi-finition, finition… d'un coup, outils proposés d'après la pièce — dans la prise montrée, sur la sélection, sinon toute la pièce (ou le corps) |
| Ébauche 3D |  | Paliers en Z sur les faces et contours choisis, sinon sur toute la pièce (ou le corps) de la prise montrée |
| Balayage 3D |  | Passes qui suivent la surface, sur les faces et contours choisis, sinon sur toute la pièce |
| Niveaux constants |  | Le tour des parois choisies à chaque cote (finition des parois raides) |
| Poche jusqu'au fond |  | Fond plat choisi : ses contours dans le dessin et une poche jusqu'à sa profondeur |
| Trous → perçages |  | Trous cylindriques verticaux de la pièce : un cercle par trou dans le dessin et un perçage par diamètre, à la profondeur du trou |
| Contours dans le dessin |  | Les contours fermés de la sélection deviennent des formes du dessin, à usiner en 2D |
| Zone d'un usinage |  | La sélection devient la zone d'un usinage 3D, ou la zone d'un usinage devient la sélection |

### Usinages

| Commande | Raccourci | Rôle |
|---|---|---|
| Liste des usinages |  | À droite de la vue 3D : les usinages de la prise montrée, leur outil, leur parcours — double clic pour modifier, Suppr pour supprimer |
| Modifier l'usinage… |  | Le formulaire de l'usinage choisi dans la liste : stratégie, outil, passes, surépaisseur, pentes, zone… ; son parcours est recalculé |
| Outil de l'usinage… |  | Diamètre, longueur utile, avance, vitesse… de l'outil de l'usinage choisi ; les parcours des usinages qui s'en servent sont recalculés |
| Supprimer l'usinage |  | L'usinage choisi et son parcours supprimés (Annuler le rend) |

### Poser

| Commande | Raccourci | Rôle |
|---|---|---|
| Poser sur cette face |  | La face plane choisie en bas, sur la table : le dessus vers l'outil, pièce alignée sur les axes |
| Face vers l'outil |  | La face plane choisie tournée vers l'outil |
| Corps posé à part… |  | Le corps de l'onglet (ou des faces choisies) posé seul pour son usinage : face vers l'outil, rotation, position ; ses trajectoires reviennent sur l'ensemble |
| Surface 2D |  | La face choisie, tournée vers l'outil, devient un sous-onglet du dessin avec son contour en guide : ce qu'on y dessine s'usine dans cette prise |

### Corps et couleurs

| Commande | Raccourci | Rôle |
|---|---|---|
| Corps |  | Corps de la pièce : les montrer ou les masquer |
| Tout montrer |  | Tous les corps de la pièce montrés |
| Couleur par corps |  | Une couleur par corps de la pièce |
| Mécanismes… |  | Contacts et liaisons entre les corps (glissière, pivot, appui…), mouvement libre, animation, collisions |
| Couleurs |  | Couleur de la pièce, des arêtes (retenues), couleurs d'origine |

### Calculer et voir

| Commande | Raccourci | Rôle |
|---|---|---|
| Calculer les parcours |  | Calculer les parcours des opérations actives |
| Trajectoires 3D |  | Parcours calculés en 3D, au-dessus de la matière (plongées, rapides, profondeurs) |
| Simulation 3D |  | Enlèvement de matière des parcours calculés, en 3D |

## Options

### Options

| Commande | Raccourci | Rôle |
|---|---|---|
| Général |  | Options (F10), onglet « Général » |
| Apparence |  | Options (F10), onglet « Apparence » |
| Dessin |  | Options (F10), onglet « Dessin » |
| Affichage |  | Options (F10), onglet « Affichage » |
| Fichiers |  | Options (F10), onglet « Fichiers » |
| FAO |  | Options (F10), onglet « FAO » |
| BAT |  | Options (F10), onglet « BAT » |
| Impression |  | Options (F10), onglet « Impression » |
| Mises à jour |  | Options (F10), onglet « Mises à jour » |
| Plugins |  | Options (F10), onglet « Plugins » |
| Performances |  | Options (F10), onglet « Performances » |

### Configuration

| Commande | Raccourci | Rôle |
|---|---|---|
| Options | F10 |  |
| Raccourcis clavier |  | Jeu de raccourcis (TypeEdit ou VectorDrive), import d'un TeTurboKey.ini, réglage par commande |
| Exporter les paramètres… |  | Réglages (options, thème, raccourcis, ruban…), outils, modèles et thèmes dans un fichier, pour un autre poste ou une sauvegarde |
| Importer des paramètres… |  | Reprendre les paramètres exportés d'un autre poste (ce qui est remplacé est d'abord sauvegardé) |
| Souris | F5 | Utilisation de la souris (F5) : molette pour zoomer ou faire défiler, rôle du clic droit |
| Plaque |  |  |
| Mise en page du texte |  | Lignes de texte réparties sur la plaque : nombre de lignes, volume du texte, marges automatiques (chaque ligne garde la largeur de la plaque pour longueur maximale) |
| Tableau |  | Tableau de cellules et de textes (plaques signalétiques) : une ligne par rangée, cellules séparées par « ; » |
| Outils |  | Table des outils (couleurs) |

## Aide

### VectorDrive

| Commande | Raccourci | Rôle |
|---|---|---|
| Commandes | F1 | Guide des commandes et raccourcis |
| À propos |  | Version, licences et composants tiers |
| Mises à jour |  | Rechercher une nouvelle version |
| Nouveautés |  | Ce qui a changé dans les dernières versions (journal de développement) |
| Chercher une commande | Ctrl+K | Trouver une commande en tapant quelques lettres de son nom, puis Entrée |

## Raccourcis sans bouton

| Commande | Raccourci |
|---|---|
| Fermer l'onglet | Ctrl+F4 |
| Onglet de dessin suivant | Ctrl+F6 |
| Onglet de dessin précédent | Ctrl+Shift+F6 |
| Copier avec point de base | Ctrl+Shift+C |
| Couper avec point de base | Ctrl+Shift+X |
| Coller au point | Ctrl+Shift+V |
| Couleurs | Ctrl+8, Ctrl+_ |
| Référence : Haut gauche | Ctrl+Num+7 |
| Référence : Haut centre | Ctrl+Num+8 |
| Référence : Haut droite | Ctrl+Num+9 |
| Référence : Milieu gauche | Ctrl+Num+4 |
| Référence : Centre | Ctrl+Num+5 |
| Référence : Milieu droite | Ctrl+Num+6 |
| Référence : Bas gauche | Ctrl+Num+1 |
| Référence : Bas centre | Ctrl+Num+2 |
| Référence : Bas droite | Ctrl+Num+3 |
| 2D | Ctrl+1, Ctrl+& |
| 3D | Ctrl+6, Ctrl+- |
| Onglet de calque suivant | Ctrl+Tab |
| Onglet de calque précédent | Ctrl+Shift+Tab |
| Rouvrir le dernier onglet fermé | Ctrl+Shift+T |
| Mode précédent | Ctrl+D |
| Mode suivant | Ctrl+F |

