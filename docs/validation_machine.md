# Validation sur machine

Ce qui, dans les dernières versions, change ce que la machine reçoit, et ce
qu'il faut vérifier **avant tout usage en production**. Ordre conseillé pour
chaque point : simulation dans VectorDrive (FAO ▸ Simuler l'usinage), puis
simulation dans le logiciel de la machine, puis passage **en l'air** (Z
relevé), puis une pièce d'essai. Les programmes portent déjà la mention
« à simuler ».

## Fraisage (posts ISO, G-code, Datron)

| Version | Fonction | À vérifier |
|---|---|---|
| 0.509 | Brut de la pièce 3D | Avec un brut donné (bloc, barre ronde, plaque, marges), l'ébauche 3D commence au haut du brut (paliers au-dessus du haut de la pièce, approche au-dessus du brut) et vide tout le brut autour de la pièce, sans sortir de lui (première prise seulement). Vérifier le zéro Z : il reste le haut de la pièce, le brut le dépasse de sa surépaisseur. La simulation part encore de Z 0 : contrôler les premières passes sur la machine. |
| 0.507 | Gamme : lier au parcours précédent | Une opération liée ne reprend que la matière laissée par les opérations d'avant (simulées) : les morceaux qui n'enlèvent rien sont retirés, les liaisons au fond ne passent que dans la matière déjà enlevée (sinon remontée au plan de dégagement). Ordre conseillé : du plus gros outil au plus fin. Le cône descend jusqu'à sa queue (D2 de la fiche). Vérifier en simulation sur la machine les liaisons au fond et la profondeur des cônes avant le premier usinage. |
| 0.506 | Contrôle du programme écrit | Chaque programme écrit est relu et comparé aux parcours (écart toléré 0,05 mm) : un avertissement « CONTRÔLE » avec la position signale un arc mal écrit, un mouvement perdu, une cote mal formatée. Contrôle sauté (et dit) quand la relecture ne peut pas être exacte : cycles exécutés par la machine (trous, poches, texte Datron), axe rotatif, laser en morceaux. Il vérifie le programme écrit, pas la machine : la simulation sur la machine reste nécessaire. |
| 0.505 | Arcs G2 / G3 dans les programmes | Les suites de segments qui suivent un cercle à 0,01 mm près (FAO ▸ Arcs dans les programmes ; 0 = segments seuls) sont écrites en arcs par les post-processeurs G-code, ISO des fiches et Datron ; écart garanti ≤ la tolérance, rayon ≤ 500 mm, moins d'un tour par arc, arcs plans seulement (Z constante). Vérifier sur la machine : sens G2 / G3, centres I J (relatifs ou absolus selon la fiche), alarme de rayon éventuelle. |
| 0.502 | Origine du dessin = zéro du programme | Comme le point zéro de TypeEdit : l'origine du dessin (Vue ▸ Repères ▸ Placer l'origine…, ou point zéro de la plaque : centre, coin…) devient le zéro X, Y des programmes machine — parcours, cycles de trous et brut décalés. Les positions des palpages (X, Y, comme « Prendre sur la sélection » les remplit) suivent l'origine comme les parcours (depuis 0.505.2) ; les décalages (incréments) ne bougent pas. Origine au zéro du dessin : programme inchangé. Vérifier le zéro pièce de la machine avant usinage. |
| 0.175 | Enroulement sur cylindre / cône (3 axes) | Origine : Z = 0 sur la génératrice du dessus, X (ou Y) = 0 sur cette génératrice. Profondeur mesurée à la verticale : sur les flancs (au-delà de 30 à 40°), la gravure est plus large et moins profonde normalement à la surface. Avertissement au-delà de 60°, refus au-delà de 85°. Cône : rayon 1 à la cote 0 de l'axe, rayon 2 à la cote « longueur ». |
| 0.189 | Refus avec une fiche à axe rotatif | Avec une fiche .MAH qui enroule par l'axe A (Mset40), un parcours enroulé pour 3 axes doit être refusé (message), jamais écrit. |
| 0.195 | Projection parallèle sur une pièce STEP | Le STEP doit être vu de dessus dans la même orientation et la même origine que le dessin ; dessus de la pièce à Z = 0. Refus si le parcours sort de la pièce. |
| 0.178 / 0.179 | Poches et V-carving forme par forme | Ordre des formes et liaisons au fond dans la simulation (les liaisons restent dans la poche, sinon remontée). |
| 0.184 | Fusionner les parcours du même outil | L'ordre d'usinage change : vérifier qu'aucune finition ne passe avant son ébauche. |
| 0.186 / 0.188 | Galbe usiné en Relief | Profondeur de l'opération Relief = profondeur indiquée par le galbe (message à la pose) ; outil boule ; simulation. |
| 0.198 | Collisions du porte-outil | Dépassement hors pince et Ø de l'écrou mesurés sur la machine (pas ceux du catalogue) ; une collision annoncée par la simulation se retrouve sur la pièce d'essai ; sans ces deux cotes, rien n'est vérifié. |
| 0.182 | Date du jour au calcul | La date gravée est celle du jour du calcul des parcours (pas celle de la préparation). |

## Laser (post Cielle)

| Version | Fonction | À vérifier |
|---|---|---|
| 0.181 | Champ de marquage | Le côté du champ (110 mm par défaut) correspond à la lentille ; un dessin hors du champ centré sur l'origine est signalé. |
| 0.181 | Gravure en morceaux | Sens des déplacements de la pièce dans les consignes (X+ à droite, Y+ en haut du plan de travail) comparé à la table réelle ; traits de raccord continus après le dernier morceau ; aucun trait gravé deux fois. |

## Hors machine

| Version | Fonction | À vérifier |
|---|---|---|
| 0.187 | Menu « Convertir avec VectorDrive » de l'explorateur | Posé seulement sur demande (Fichier ▸ Menu de l'explorateur), sous le compte de l'utilisateur ; une conversion n'écrase jamais un fichier existant. |
| 0.176 / 0.177 | Textes stylés dans les VND | Avec l'option des textes TypeEdit modifiables, un texte justifié, en italique, souligné, en petites majuscules, sous la ligne de base ou à longueur maximale est écrit en courbes : vérifier dans TypeEdit qu'il paraît comme dans VectorDrive. |
