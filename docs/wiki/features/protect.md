# Protéger un PDF

## À quoi ça sert

Ajouter un mot de passe demandé à l'ouverture du PDF.

## Comment faire

Ouvrez **Protéger un PDF** depuis l'accueil ou le menu **Outils**. Choisissez
un PDF, saisissez un nouveau mot de passe et confirmez-le. Utilisez une phrase
longue et gardez-la : PriveoPDF ne peut pas la retrouver.
Une copie `<nom>_protégé.pdf` est proposée d'office dans le dossier du PDF
(**CHANGER…** pour une autre destination), puis cliquez sur **PROTÉGER LE PDF**.
Vous pouvez annuler pendant le traitement. **Afficher/Masquer**, à côté de chaque
champ, permet de vérifier ce que vous tapez.

Pour conserver un seul fichier, cochez **Remplacer ce PDF**. La case est
décochée à chaque nouveau PDF et en quittant l'outil. Confirmez au lancement : après succès, le nom reste identique et la
version précédente n'est pas conservée. Une erreur ou une annulation avant
l'enregistrement laisse le fichier précédent intact.

## Résultat

Le PDF est chiffré en AES-256. Le résultat s'affiche sous le bouton.
**OUVRIR LE PDF** ouvre son état protégé
dans PriveoPDF, avec un bouton **Déverrouiller le PDF**. Pour lire ses pages sans
retirer la protection, ouvrez-le dans votre lecteur PDF habituel.
Par défaut, une copie est créée et l'original reste inchangé. Seule la case
**Remplacer ce PDF**, suivie de la confirmation, permet de remplacer l'original.

## Limites

Le mot de passe est masqué et effacé du formulaire après lancement ou lorsque
vous quittez l'outil. Il n'est pas mémorisé dans les préférences ou les journaux.
Il circule uniquement en mémoire pendant le traitement ; l'effacement physique
immédiat de toutes les copies mémoire n'est pas garanti.
La limite est de 127 octets UTF-8 (les caractères accentués peuvent compter pour
plusieurs octets), sans caractère nul ni saut de ligne. Aucun espace n'est retiré.
Les documents déjà chiffrés, signés numériquement ou dont l'intégrité ne peut
être vérifiée sont refusés. Déverrouillez d'abord une copie pour changer de mot
de passe. Les restrictions d'impression et de copie ne sont pas proposées ici.
Le chiffrement ne retire pas les métadonnées et ne garantit pas la conformité PDF/A.
