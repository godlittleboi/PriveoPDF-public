# Caviarder un PDF

## À quoi ça sert

Noircir des zones d'un PDF (un nom, un numéro, une adresse, une photo) et
supprimer réellement ce qui se trouvait dessous, avant de partager le fichier.
Un simple rectangle dessiné par-dessus ne suffit pas : le texte masqué reste
dans le fichier et se retrouve en le copiant. Ici, le PDF produit est une
photocopie de chaque page avec les zones noircies, puis il est vérifié.

## Comment faire

Ouvrez **Caviarder un PDF** depuis l'accueil, famille **SÉCURISER PDF**, ou
depuis un PDF ouvert avec **Outils**. Déposez un seul PDF.

Les pages s'affichent à gauche. Tracez un rectangle avec la souris sur chaque
zone à noircir : elle apparaît en couleur sur la page et le compteur de zones
augmente à droite. **Retirer la dernière zone** annule le dernier rectangle,
**Tout effacer** les retire tous. Ctrl + molette règle le zoom.

Un fichier de destination est proposé d'office dans le dossier du PDF, par
exemple `contrat_caviardé.pdf` ; **CHANGER…** permet d'en choisir un autre.
Cliquez sur **CAVIARDER LE PDF**. La progression s'affiche page par page.

## Résultat

Le résultat s'affiche sous le bouton : fichier créé, nombre de zones noircies
et de pages concernées, puis ce que la vérification a établi après l'écriture :
chaque page est une image, aucun texte ni objet caché ne subsiste. **OUVRIR LE
PDF** et **OUVRIR LE DOSSIER** sont proposés. L'original reste inchangé et un
fichier existant n'est jamais remplacé.

Dans le PDF produit, chaque page est une image de la page d'origine, zones
noircies comprises, à 200 points par pouce. Le texte n'est donc plus
sélectionnable ni recherchable : pour le rendre recherchable, utilisez
[Reconnaître le texte (OCR)](ocr_pdf.md) sur le fichier produit ; rien ne
sera reconnu sous les zones noires. Les métadonnées, liens, formulaires,
pièces jointes et calques de l'original ne sont pas repris ; un tampon ou un
champ rempli reste visible, comme sur une photocopie, et se noircit comme le
reste de la page.

## Limites

Le PDF produit est plus lourd qu'un PDF textuel et son texte n'est plus
sélectionnable. Les zones sont des rectangles ; tracez-en plusieurs pour une
forme complexe. Le caviardage refuse un PDF protégé ou endommagé, un
formulaire interactif et un document au-delà de 500 pages ou d'environ
20 millions de pixels par page. Au plus 500 zones par document.

Un PDF qui porte une signature numérique est signalé dès son chargement : le
caviardage la rendrait invalide. Cochez **Produire une copie sans signature**
pour continuer ; la copie ne contient plus la signature numérique, l'original
n'est pas modifié et une signature visible reste une simple image. La case est
décochée à chaque nouveau fichier.

Vérifiez vous-même le fichier produit avant de le partager : la vérification
contrôle que les zones tracées sont noires et qu'aucun texte ne subsiste, pas
que vous avez tracé toutes les zones utiles.
