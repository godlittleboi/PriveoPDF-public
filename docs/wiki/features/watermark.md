# Filigraner un PDF

## À quoi ça sert

Écrire un texte visible sur chaque page d'un PDF avant de le remettre : une
mention (« Confidentiel », « Copie non contractuelle »), le nom du
destinataire, une référence. Si le fichier circule, la copie dit d'où elle
vient. Le texte est écrit dans le contenu de chaque page, pas ajouté comme une
annotation qu'un lecteur retire d'un clic.

## Comment faire

Ouvrez **Filigraner un PDF** depuis l'accueil, famille **SÉCURISER PDF**, ou
depuis un PDF ouvert avec **Outils**. Déposez un seul PDF.

Les pages s'affichent à gauche. À droite, saisissez le **Texte** (jusqu'à
120 caractères : lettres latines avec accents, chiffres, ponctuation
courante), choisissez la **Disposition** — en diagonale au centre, ou répété
sur toute la page — et l'**Intensité** (légère, moyenne, forte). L'aperçu se
met à jour sur les pages à chaque changement. Ctrl + molette règle le zoom.

Un fichier de destination est proposé d'office dans le dossier du PDF, par
exemple `contrat_filigrané.pdf` ; **CHANGER…** permet d'en choisir un autre.
Cliquez sur **FILIGRANER LE PDF**.

## Résultat

Le résultat s'affiche sous le bouton : fichier créé, puis ce que la
vérification a établi après l'écriture : le texte est présent et visible sur
chaque page. **OUVRIR LE PDF** et **OUVRIR LE DOSSIER** sont proposés.
L'original reste inchangé et un fichier existant n'est jamais remplacé.

Dans le PDF produit, le texte d'origine reste sélectionnable et recherchable ;
le filigrane aussi. Les liens, formulaires, annotations et métadonnées de
l'original sont conservés tels quels. La vérification rouvre le fichier
produit, compte ses pages, contrôle qu'aucune annotation n'a été ajoutée,
retrouve le texte sur chaque page et compare chaque page rendue à la page
d'origine.

## Limites

Aucun filigrane visible n'est indélébile : quelqu'un qui réédite le PDF ou le
transforme en images peut le retirer. La promesse est la résistance à une
suppression triviale, pas une protection contre la copie. Le filigrane refuse
un PDF protégé ou endommagé et un document au-delà de 500 pages. Le
texte utilise une police standard (Helvetica-Bold) : les caractères hors
alphabet latin sont refusés avant l'action.

Un PDF qui porte une signature numérique est signalé dès son chargement : le
filigrane la rendrait invalide. Cochez **Produire une copie sans signature**
pour continuer ; la copie ne contient plus la signature numérique, l'original
n'est pas modifié et une signature visible reste une simple image. La case est
décochée à chaque nouveau fichier.
