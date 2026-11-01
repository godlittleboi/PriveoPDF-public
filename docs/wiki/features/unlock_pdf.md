# Déverrouiller un PDF

## À quoi ça sert

Retirer le chiffrement d'un PDF dont vous connaissez le mot de passe.

## Comment faire

Ouvrez **Déverrouiller un PDF** depuis l'accueil ou le menu **Outils**. Quand
vous ouvrez un PDF protégé dans le lecteur, un message et le bouton
**Déverrouiller le PDF** permettent d'accéder directement à cet outil.
Déposez le PDF protégé directement dans cet outil ; son aperçu n'est pas
nécessaire. Saisissez le mot de passe connu. Une copie `<nom>_déverrouillé.pdf` est
proposée d'office (**CHANGER…** pour une autre destination), puis cliquez sur
**DÉVERROUILLER LE PDF**. Vous pouvez annuler le traitement.
Un mot de passe incorrect est refusé : saisissez-le à nouveau pour réessayer.
Utilisez **Afficher/Masquer** pour vérifier votre saisie.

Depuis un autre outil, **DÉVERROUILLER PDF**, affiché sous un PDF protégé,
ouvre directement cet outil sur ce fichier. Un PDF qui n’est pas protégé est
signalé dès son chargement (« Ce PDF n'est pas protégé : rien à
déverrouiller. ») : aucun mot de passe n’est demandé.

Pour conserver un seul fichier, cochez **Remplacer ce PDF**, puis confirmez au
lancement. Le fichier garde son nom et devient lisible sans mot de passe ; la
version protégée précédente n'est pas conservée. Une erreur ou une annulation
avant l'enregistrement conserve le fichier précédent.

## Résultat

Le résultat s'affiche sous le bouton. **OUVRIR LE PDF** ouvre le PDF sans mot
de passe. Comparez ses pages avec
l'original. Par défaut, une copie est créée et l'original protégé reste inchangé.
Seul le choix de remplacement confirmé modifie le fichier courant. Toute personne
disposant du résultat peut en lire le contenu.

## Limites

Cet outil ne recherche ni ne récupère un mot de passe perdu. Les documents non
chiffrés, signés numériquement ou dont l'intégrité ne peut être vérifiée ne
produisent aucune sortie.
Le mot de passe reste en mémoire pendant le traitement, sans préférence,
fichier de secret ni journal. Les champs sont effacés après lancement ou sortie
de l'outil ; aucune garantie d'effacement physique de toutes les copies mémoire.
La limite est de 127 octets UTF-8, sans caractère nul ni saut de ligne.
Les métadonnées et le contenu du PDF sont conservés, sans nettoyage automatique.
