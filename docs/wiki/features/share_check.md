# Vérifier avant partage

## À quoi ça sert

Consulter les propriétés Info et XMP sans modifier le fichier, puis choisir
entre retirer les métadonnées globales et reconstruire les pages en images.
Les deux valeurs restent affichées quand Info et XMP divergent.

## Comment faire

Ouvrez **Vérifier avant partage** depuis l'accueil ou **Outils**, puis choisissez
un PDF. Une phrase résume le bilan, puis un tableau **Élément · Dans ce PDF ·
À faire** liste les métadonnées trouvées (titre, auteur, dates…) et les
éléments à relire (liens, commentaires, pièces jointes…), avec l'action
utile. **Détails techniques** (replié) montre Info, XMP et toutes les
propriétés brutes. Une analyse
incomplète affiche des minimums : zéro ne prouve alors pas une absence. Sa cause
s’affiche sur la ligne suivante (fichier illisible, limite d’analyse atteinte,
délai dépassé…).

Depuis un document déjà ouvert, **Outils → Vérifier avant partage** lance
automatiquement l'analyse. Si vous changez rapidement de document, le bilan
porte sur le dernier document sélectionné. **Annuler** ou quitter la page
interrompt l'analyse et sa reprise éventuelle ; revenir dans l'outil la relance.

**Supprimer les métadonnées** est sélectionné par défaut. Une copie
`<nom>_sans-métadonnées.pdf` est proposée d'office (**CHANGER…** pour une autre
destination) ; lancez l'action. Si aucun conteneur global n'est
présent, aucun fichier n'est créé ; la photocopie reste possible.

Pour **Photocopier le PDF — images uniquement**, lisez l'avertissement puis
préparez l'aperçu. Parcourez les pages et zoomez pour vérifier les petits textes.
L'aperçu montre le PDF reconstruit, avec les mêmes réglages que l'export.
Tant que l'aperçu n'est pas prêt, le bouton reste grisé et la raison s'affiche
dessous. Une copie `<nom>_photocopie.pdf` est proposée ; cliquez sur
**CRÉER LA PHOTOCOPIE**.
Vous pouvez annuler le rendu ou la vérification. Un document modifié exige
un nouvel aperçu. Les formulaires non rendables produisent un refus.

Une copie est créée par défaut. **Remplacer ce PDF** demande une confirmation
à chaque traitement ; pour la photocopie, elle rappelle la perte du texte et
des fonctions interactives. L'original reste intact jusqu'à publication réussie.

## Résultat

Le résultat s'affiche sous le bouton, avec les tailles avant et après. Le bilan
est recalculé sur le résultat. **OUVRIR LE PDF** ouvre le PDF, **OUVRIR LE
DOSSIER** son dossier.
Le mode standard retire Info et XMP globaux en conservant texte, annotations,
liens, formulaires et pièces jointes. La photocopie conserve seulement les
images des pages : ni texte sélectionnable, ni OCR, ni anciens objets cachés.
Le nom et les informations visibles ne sont pas anonymisés.

## Limites

Le correctif candidat #284 adapte la protection mémoire au lanceur Beta.
La photocopie reste à valider sur Linux Mint : aperçu, export, annulation et
limite mémoire. Ne cochez que les contrôles réellement effectués dans Beta.

La photocopie exige Linux 6.5+, systemd utilisateur 255+, libsystemd0, cgroups v2,
bubblewrap et les protections Landlock/seccomp du lanceur. Si la protection mémoire est indisponible ou le budget atteint,
aucune sortie n'est publiée. Windows n'est pas qualifié.
Le profil est couleur, 200 dpi, compression sans perte ; la taille peut augmenter
et la netteté diminuer au zoom. Limites : 500 pages, 20 millions de pixels par
page, 256 Mio de pixels cumulés, 1,5 Gio de mémoire du groupe, swap interdit et
120 secondes par opération. Une limite dépassée ne réduit jamais silencieusement
la qualité. Les signatures apposées interdisent les transformations ; l'inspection
reste possible. Déverrouillez les PDF chiffrés avec l'outil existant.
Aucune conformité PDF/A ou PDF/UA, sûreté générale ou anonymat n'est certifié.
Les temporaires privés sont nettoyés ; cela ne promet pas un effacement physique
sécurisé sur le disque ou dans les sauvegardes.
