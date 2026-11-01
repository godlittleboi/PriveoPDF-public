# Diviser un PDF

## À quoi ça sert

Créer plusieurs PDF à partir d’un seul document.

## Comment faire

Ajoutez le PDF, puis choisissez comment **DÉCOUPER** dans la colonne de
droite :

- **Toutes les N pages** (choix par défaut, 2 pages par fichier) : indiquez le
  nombre de pages par fichier ; le dernier fichier garde les pages restantes ;
- **Une page par fichier** ;
- **Par groupes (glisser-déposer)** : répartissez visuellement les pages dans
  les groupes de sortie ;
- **Par plages** : saisissez une plage par fichier, par exemple `1-3,4-6`.

Le dossier du PDF est proposé d’office ; **CHANGER…** permet d’en choisir un
autre. Les noms des fichiers à créer s’affichent avant l’action, par exemple
`Rapport_part-1.pdf`. Tant que le découpage n’est pas possible, le bouton reste
grisé et la raison s’affiche dessous.

## Résultat

Chaque groupe non vide devient un nouveau PDF local. Le nombre de fichiers créés
s’affiche sous le bouton, avec **OUVRIR LE DOSSIER**. Le document source reste
inchangé.

## Limites

Les groupes vides sont ignorés. Un document d’une page ne peut pas être divisé,
et un découpage qui recopierait tout le document dans un seul fichier est
refusé. Si un fichier portant un nom prévu existe déjà dans le dossier, le
bouton reste grisé : choisissez un autre dossier.
