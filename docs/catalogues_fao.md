# Opérations machine, catalogues et Finition 2,5D

## Ajouter depuis un catalogue

Panneau « FAO : opérations et parcours », bouton **📖** : une fenêtre propose les opérations machine
des catalogues apportés par les plugins — commandes de la documentation de la machine, opérations d'un
autre logiciel, programmes d'exemple.

- Arbre (catalogue › famille › opération), **recherche** sur le nom, la famille et l'aide, **aperçu** du
  bloc de programme et de son aide (chapitre, page de la documentation…).
- **Ajouter** (ou double-clic, plusieurs à la fois) : les opérations se posent après celle choisie dans
  la liste.
- **Fichier…** : un fichier texte (programme machine, extrait) devient un bloc de programme.

Une opération de catalogue devient une **instruction machine** : un *bloc de programme* (texte copié tel
quel dans le programme, `{p1}` … `{p6}` remplacés par ses paramètres, qui portent un nom), ou une
instruction que VectorDrive connaît déjà (palpage, message, repère…), avec son formulaire. Seuls les
post-processeurs qui savent écrire les instructions machine les reprennent ; les autres les ignorent avec
un avertissement.

Pour les auteurs de plugins : `api.add_instruction_catalog(libellé, fournisseur)`, le fournisseur rend
une liste de `vectordrive.cam.catalog.Entry` (nom, rangement « Famille/Sous-famille », texte ou fonction
qui le lit à la demande, aide, noms et valeurs des paramètres, ou instruction et ses réglages).

## Finition 2,5D

Palette FAO › Usinage 3D › **Finition 2,5D** : la finition 3D en mode gravure 2,5D.

- La surface que laisse une gravure 2,5D des contours fermés — le cône de l'outil de gravure, choisi comme
  « Outil passé avant », jusqu'à la profondeur de l'opération — est balayée avec l'outil de l'opération
  (fraise boule, droite ou conique), selon X, Y ou croisé, au pas choisi.
- **Ébauche** : paliers en Z jusqu'à la surface, surépaisseur en Z et **décalage en XY** le long des
  flancs ; une seconde opération, en finition, reprend ensuite la surface exacte.

## Post-processeur et panneau FAO

- Le **post-processeur** (machine) se choisit dans les **Options**, onglet FAO : il vaut pour le dessin
  ouvert et pour les nouveaux dessins. Le panneau FAO affiche la machine choisie et un bouton « Options… ».
- Outils, opérations et parcours se partagent la hauteur du panneau à la souris (partage retenu) ; la
  liste des opérations prend la plus grande part. Le panneau occupe toute la hauteur de la fenêtre à
  l'ouverture.
- **Opacité** des panneaux FAO détachés et des formulaires d'outils et d'opérations : Options, onglet FAO
  (94 % par défaut).
- Le schéma d'une opération dessine la **rampe à son angle**, en zigzag quand elle est plus longue que la
  place, avec sa longueur par passe.
