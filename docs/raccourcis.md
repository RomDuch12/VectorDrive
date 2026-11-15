# Raccourcis clavier

Modifier > Raccourcis clavier : choisir le jeu, importer un
`TeTurboKey.ini`, changer une touche. Une touche n'appartient jamais qu'à
une commande (celle qu'on affecte la retire des autres) ; les conflits
s'affichent en rouge.

## Jeux

| Jeu | Origine |
|---|---|
| **TypeEdit** | le `TeTurboKey.ini` du TypeEdit **installé sur le poste** (`C:\ProgramData\Gravotech\TypeEdit_*\CONFIG\`, le plus récent), lu au démarrage, ou un fichier importé |
| **VectorDrive** | les raccourcis d'origine du programme |
| jeu d'un plugin | un atelier peut fournir le sien (`api.add_shortcut_scheme`), qui devient alors le jeu par défaut |

Par défaut : le jeu d'un plugin s'il y en a un, sinon TypeEdit s'il est
installé, sinon VectorDrive.

## Le fichier de TypeEdit

Section `[TAB_ACCELERATOR]`, triplets `CMD_nnn` (commande), `MOD_nnn`
(FCONTROL, FSHIFT, FALT), `KEY_nnn` (lettre, chiffre ou VK_F1…F12,
VK_DELETE, VK_INSERT, VK_BACK, VK_PRIOR, VK_NEXT, VK_TAB). Seules les
associations commande → touche sont reprises ; `vectordrive/ui/shortcuts.py`
(`TE_ACTIONS`) dit à quelle commande de VectorDrive répond chaque commande
TypeEdit.

## Sans équivalent (pour l'instant)

Vues 3D (Ctrl+1 … Ctrl+6), mosaïque de fenêtres, volets (F6), filtre
d'affichage (F9), ouvrir un modèle, flèche, dialogue d'alignement, aligner
sur un point, séparateur, palette de formes.

## Déplacer au clavier

Flèches : la sélection avance du pas en cours (pas des options au départ) ;
Maj+flèche : 10 fois le pas des options. **Ctrl+flèche** demande le pas :
la valeur proposée est le pas en cours, sinon la largeur (ou la hauteur)
de la sélection plus l'écart des options ; après Entrée, les flèches
avancent de cette valeur ; 0 revient au pas des options.
