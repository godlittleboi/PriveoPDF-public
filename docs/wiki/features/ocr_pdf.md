# Reconnaître le texte (OCR)

## À quoi ça sert

Rendre un PDF scanné recherchable : le texte des pages scannées est reconnu sur
cet ordinateur, puis ajouté de façon invisible. Vous pouvez ensuite chercher,
sélectionner et copier ce texte dans un lecteur PDF.

## Comment faire

Ouvrez **Reconnaître le texte (OCR)** depuis l'accueil, famille **OPTIMISER
PDF**, ou depuis un PDF ouvert avec **Outils**. Déposez un seul PDF.

Cochez la ou les langues du document, trois au plus. **Anglais**, **Français**
et **Espagnol** sont toujours affichés ; toute autre langue dont le modèle est
installé s'ajoute à la liste. La langue de l'interface est cochée d'office si
son modèle est installé. Une langue grisée n'est pas installée ; son infobulle
donne la commande à saisir dans un terminal, par exemple :

```bash
sudo apt install tesseract-ocr tesseract-ocr-fra
```

Pour ajouter une langue, cliquez sur **AJOUTER UNE LANGUE…**, choisissez-la
dans la liste (recherche par nom) et cliquez sur **INSTALLER** : le programme
d'installation du système demande votre mot de passe et installe le modèle ;
PriveoPDF ne télécharge rien lui-même. La langue est cochée dès que le modèle
est présent. Sans programme d'installation graphique, **COPIER LA COMMANDE**
donne la commande à coller dans un terminal (`sudo apt install
tesseract-ocr-<code>`). Codes des langues courantes : `deu` allemand, `ita` italien,
`por` portugais, `nld` néerlandais, `pol` polonais, `ron` roumain, `rus` russe,
`ara` arabe, `tur` turc, `ell` grec, `swe` suédois, `dan` danois, `nor`
norvégien, `fin` finnois, `ces` tchèque, `hun` hongrois, `ukr` ukrainien, `heb`
hébreu, `jpn` japonais, `kor` coréen, `chi_sim` chinois simplifié, `chi_tra`
chinois traditionnel, `hin` hindi, `vie` vietnamien, `cat` catalan, `eus`
basque, `bre` breton, `lat` latin. La liste complète : `apt search
tesseract-ocr-`. Une langue inconnue de PriveoPDF s'affiche par son code.

Si aucun modèle n'est installé, le bouton reste désactivé et la même commande
s'affiche dessous. Un fichier de destination est proposé d'office dans le
dossier du PDF, par exemple `facture_recherchable.pdf` ; **CHANGER…** permet
d'en choisir un autre. Cliquez sur **RECONNAÎTRE LE TEXTE**. La progression
s'affiche page par page et vous pouvez annuler.

Pour ne traiter que certaines pages (une photo ou une page manuscrite à laisser
de côté, ou un document de plus de 50 pages scannées), ouvrez
**OPTIONS AVANCÉES** et saisissez les pages à reconnaître, par exemple
`1-50, 52`. Vide, le champ traite toutes les pages scannées. Les autres pages
restent telles quelles ; un long document se traite en plusieurs passes, en
relançant l'outil sur le fichier produit avec les pages suivantes.

## Résultat

Le résultat s'affiche sous le bouton : fichier créé, puis le nombre de pages
rendues recherchables, de pages laissées intactes (déjà textuelles, ou non
choisies) et de pages sans texte détecté. **OUVRIR LE PDF** et **OUVRIR LE
DOSSIER** sont proposés.

L'aspect des pages ne change pas. Les pages qui contiennent déjà du texte ne
sont pas modifiées. Un scan posé de travers ou à l'envers est lu dans le bon
sens, mais la page n'est pas pivotée : utilisez [Faire pivoter des
pages](rotate.md) pour la redresser. L'original reste inchangé et un fichier
existant n'est jamais remplacé.

Aucun fichier n'est créé si toutes les pages (ou toutes les pages choisies)
contiennent déjà du texte ou si aucun texte n'est reconnu. Vérifiez alors la
langue cochée et la netteté du scan.

## Limites

La reconnaissance peut se tromper, surtout sur un scan flou, une écriture
manuscrite, un tableau complexe ou une petite police : relisez le texte
important. Une page qui mélange déjà du texte et une image scannée est
laissée telle quelle. Trois langues au plus par passe.

Un document est limité à 500 pages, dont 50 pages scannées au format A4 au plus
(25 en A3 ; format maximal A2) par passe, et à trente minutes de traitement.
Au-delà, choisissez les pages dans **OPTIONS AVANCÉES** et procédez en plusieurs
passes, ou divisez le document avec [Diviser un PDF](split.md). Les PDF
chiffrés ou endommagés sont refusés, comme une page scannée qui porte
une annotation, un champ de formulaire ou un recadrage. Il n'y a ni traitement
par lot ni conversion PDF/A.

Un PDF qui porte une signature numérique est signalé dès son chargement :
l'OCR la rendrait invalide. Cochez **Produire une copie sans signature** pour
continuer ; la copie ne contient plus la signature numérique, l'original n'est
pas modifié et une signature visible reste une simple image. La case est
décochée à chaque nouveau fichier. Si la signature est posée sur une page
scannée, cette page reste refusée comme toute annotation.

Les modèles Tesseract viennent des paquets du système (Linux Mint 22, Ubuntu
24.04) ; PriveoPDF ne les télécharge jamais.
