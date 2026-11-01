# Dépannage

## Un PDF ne s’ouvre pas

Vérifiez qu’il existe toujours, qu’il se termine par `.pdf` et qu’une autre
application peut le lire. Un document protégé ou endommagé peut être refusé.

Dans un outil, un PDF inutilisable est signalé dès son chargement, sous la
source, et le bouton d’action reste inactif :

- « Ce PDF est protégé par mot de passe. » : **DÉVERROUILLER PDF** ouvre
  Déverrouiller un PDF sur ce fichier. Un PDF qui s'ouvre sans mot de passe
  mais porte des restrictions d'usage est traité normalement ; la copie
  produite n'a plus ces restrictions ;
- « Ce PDF est illisible ou endommagé. » : choisissez un autre fichier avec
  **CHANGER PDF**.

Dans Fusionner et Insérer, le message nomme chaque fichier en cause.

## Une opération ne démarre pas

Vérifiez la sélection de pages, les champs signalés et la destination. La sortie
doit être différente de la source et ne doit pas déjà exister. La raison du
blocage s’affiche sous le bouton.

Les plages de pages saisies au clavier n’acceptent que les chiffres 0 à 9, des
tirets et des virgules (par exemple `1-3,5`). Un numéro de page ne peut pas
dépasser 100 000, ni une expression compter plus de 100 000 pages au total.

## « La structure de ce PDF est trop volumineuse pour cet outil »

Fusionner, Diviser, Extraire, Supprimer, Réorganiser, Insérer et Ajouter une
page blanche lisent les ressources des pages copiées pour conserver l’état des
calques. Un document aux ressources exceptionnellement nombreuses (plusieurs
centaines de milliers d’objets pour une seule opération) est refusé avant toute
écriture, sans fichier créé. Traitez moins de pages à la fois : extrayez ou
divisez le document en parties plus petites, puis recommencez sur chaque partie.
L’original n’est jamais modifié.

## Le résultat ne correspond pas à l’attente

Conservez l’original, notez l’action et réessayez avec une copie non sensible.
Consultez ensuite la [fiche de l’outil](features/README.md) pour vérifier ses
limites.

## Reconnaître le texte (OCR) ne reconnaît rien ou reste désactivé

Le bouton reste désactivé tant qu'aucun modèle de langue n'est installé. Dans un
terminal : `sudo apt install tesseract-ocr tesseract-ocr-fra` (`-eng` pour
l'anglais, `-spa` pour l'espagnol), puis rouvrez l'outil. Si aucun texte n'est
reconnu, cochez la bonne langue et utilisez un scan plus net. Voir
[Reconnaître le texte (OCR)](features/ocr_pdf.md).

## L’OCR ou la photocopie n’a pas pu fonctionner sous sa protection mémoire

Le message se termine par un **Détail technique** que vous pouvez copier.
Ces traitements limitent leur mémoire sur l’ordinateur : ils demandent une
session systemd utilisateur, cgroups v2 et bubblewrap. Si ces éléments sont
présents, le document a peut-être dépassé la limite de traitement : essayez
avec un document plus court. Aucun fichier n’est créé dans ce cas.

## L’affichage est difficile à lire

Choisissez un autre thème dans **Paramètres → Thème** et consultez
[Apparence](features/appearance.md).

Aucun rapport ou document n’est envoyé automatiquement.

## Les sources publiques ne démarrent pas

Installez les dépendances verrouillées, puis utilisez
`bash tools/launch_priveopdf.sh` depuis la racine du projet. Un lancement Python
direct ne prépare pas le confinement. `network_isolation_unavailable` indique
que l'isolation Linux obligatoire est indisponible : conservez le diagnostic et
vérifiez les prérequis du guide d'installation source inclus. Ne désactivez pas
le confinement pour traiter un PDF.

La mise à jour Git privée et l'historique des bêtas internes sont désactivés dans
les snapshots publics. Les checklists de bêta privée et leurs lanceurs relèvent
du workflow de développement séparé du mainteneur.
