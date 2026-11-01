# Visualiser un PDF

## À quoi ça sert

Lire un PDF, parcourir ses pages et vérifier son contenu sans le modifier.

## Comment faire

Déposez un PDF ou cliquez sur **Parcourir**. La molette et le pavé tactile font
défiler le document en continu. Les flèches haut/bas défilent ; Page haut/bas
avance ou recule d'un écran. Utilisez les boutons de page ou le tiroir de
miniatures pour changer directement de page. **Ctrl + molette** règle le zoom,
centré sur le pointeur : l'endroit visé reste sous la souris. La page garde son
affichage pendant que le nouveau rendu arrive, sans passer par une page blanche ;
**Ajuster** adapte la page ou sa largeur à la fenêtre. Sur une nouvelle
installation, un PDF s'ouvre ajusté à la largeur ; une installation mise à jour
garde son réglage (**Paramètres → Lecture PDF**).
Le nom du fichier figure en haut de la fenêtre.
Les boutons **+** et **−** changent le zoom de 5 points de pourcentage par clic.
Le zoom manuel va de 1 % à 400 % ; **Ajuster** peut choisir une valeur différente
pour afficher une page de taille inhabituelle en entier.
Le mode lecture (**Plus**, ou **Ctrl+Maj+R** ; **Échap** pour en sortir) ajuste la largeur ; à sa sortie,
le zoom choisi auparavant revient.

Pour copier du texte, glissez la souris sur les lignes voulues, comme dans un
lecteur PDF habituel : le glisser peut partir de la marge ou y finir, et le
surlignage suit le texte. **Ctrl+C** copie la sélection ; un clic ailleurs
l'efface. Au-dessus du texte, le curseur prend la forme d'une barre verticale.

Pour trouver un mot, appuyez sur **Ctrl+F** ou cliquez sur la loupe, puis
tapez le texte : la recherche porte sur tout le document. Les résultats sont
surlignés ; **Entrée** passe au suivant, **Maj+Entrée** au précédent, et le
compteur indique la position, par exemple `2 / 5`. **Échap** ferme la recherche.

## Résultat

Le PDF reste ouvert dans l’application et apparaît dans **Documents ouverts**.
Aucun nouveau fichier n’est créé.

## Limites

Un PDF protégé, endommagé ou inhabituel peut refuser de s’ouvrir ou s’afficher
partiellement. La lecture ne lance jamais automatiquement une reconnaissance de
texte : un PDF scanné, fait d'images, n'a pas de texte à sélectionner ni à
rechercher. [Reconnaître le texte (OCR)](ocr_pdf.md) en crée une copie dont le texte se sélectionne
et se recherche. La sélection reste sur une seule page. La recherche ignore les
majuscules mais pas les accents (« réunion » ne trouve pas « reunion ») et
s'arrête à 1 000 résultats (le compteur affiche alors « 1000+ »). Sur un
document très long ou endommagé, elle peut échouer : le message « Recherche
impossible dans ce document » s'affiche alors.
