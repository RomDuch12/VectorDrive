# Outils proposés par opération

Pour chaque type d'opération (gravure, poche, perçage, laser…), on règle quels outils proposer
et dans quel ordre. La fenêtre s'ouvre de trois endroits :
- Bibliothèque d'outils, bouton « Outils par opération… » ;
- panneau FAO, menu des outils, « Outils proposés par opération… » ;
- fenêtre « Choisir un outil », bouton « Régler les propositions… ».

## Réglage d'une opération

- **Lignes**, dans l'ordre :
  - une nature d'outil (fraise, boule, conique, foret, laser, couteau, outil spécial) ;
  - un dossier de Mes outils, sous-dossiers compris ;
  - un outil précis, retrouvé aussi dans le document, où il est copié.

  Un outil prend le rang de la première ligne qu'il remplit. Sans aucune ligne, tous les outils
  sont proposés.
- **Proposer** : soit les outils adaptés en tête puis les autres, soit seulement les outils adaptés.
- **Dans une même ligne** : ordre de la bibliothèque, Ø croissant ou Ø décroissant.
- « Appliquer aussi à… » recopie le réglage sur une autre opération. « Réglage par défaut » rend
  celui du logiciel.

Les réglages vont dans le fichier de réglages (clé `fao/outils_par_operation`) et partent avec
l'export des paramètres. Seuls ceux qui diffèrent des défauts sont écrits.

## Qui propose des outils, et sous quelle forme

| Fonction | Forme | Avec le réglage |
|---|---|---|
| Formulaire d'une opération (Nouvelle opération, Modifier, parcours de la palette) | liste « Outil » | Outils du document dans l'ordre réglé ; en mode « seulement », les autres sont cachés (l'outil déjà choisi reste). Réglage enregistré : jusqu'à 8 outils adaptés de Mes outils, puis « Choisir dans Mes outils… ». |
| Fenêtre « Choisir un outil » | arbre par dossiers, filtres | Case « Seulement les outils adaptés ». Réglage enregistré : groupe « Proposés pour … » en tête. |
| Boutons de la palette Parcours | outil pris d'office | Réglage enregistré : le premier outil proposé du document, sinon de Mes outils (copié dans le document). Sinon, comme avant : un outil de la nature du parcours. |
| Bibliothèque d'outils | filtre « Adaptés à » | Les outils proposés pour l'opération choisie, dans leur ordre. |
| Relief > Outil (dilatation au profil de l'outil) | liste | Mes outils dans l'ordre réglé pour « Relief 3D ». |

## Réglages par défaut

Ce sont ceux qu'appliquait déjà le logiciel. Par exemple :
- gravure : conique, puis fraise, boule et outil spécial ;
- perçage : foret, puis fraise ;
- reste matière : fraise et boule, Ø croissant ;
- surfaçage : fraise, Ø décroissant ;
- laser et couteau : seulement les outils de cette nature.

La liste complète est dans `vectordrive/cam/toolprefs.py` (`DEFAULTS`).
