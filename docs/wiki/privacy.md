# Confidentialité

## Traitement local

Les PDF, leurs pages, miniatures, mots de passe, noms et chemins restent sur
l’appareil. Les outils principaux ne demandent ni compte, ni cloud, ni envoi de
document.

**Reconnaître le texte (OCR)** reconnaît le texte sur l’appareil avec la bibliothèque Tesseract du
système. Le texte reconnu n’est ni journalisé ni envoyé : il est seulement
ajouté à la copie créée. Il y devient sélectionnable, copiable et repérable par
les outils de recherche de votre ordinateur.

## Réseau

La lecture et la modification des PDF ne nécessitent aucune connexion. Une
vérification de mise à jour demande une action ou un consentement distinct et
n’autorise jamais l’envoi d’un document.

## Données mémorisées

Si la restauration est activée, PriveoPDF peut conserver localement les chemins
des documents ouverts, les noms de sessions et la sélection courante. Le contenu
binaire des PDF n’est pas stocké dans la session.

L’[aide incluse](index.md) fonctionne elle aussi hors ligne.

## Protection locale

Le décodage et le rendu des PDF utilisent des processus séparés, sans accès à
la session graphique. Le confinement Linux requis est appliqué à chaque worker,
même quand l'application est déjà sans réseau. Cela réduit les conséquences
d'une éventuelle faille de moteur PDF ; cela ne garantit pas l'absence de faille.
Hors du lanceur, certains outils de pages gardent accès au dossier de sortie. L'interface
conserve les accès nécessaires pour ouvrir et enregistrer vos documents.

### Isolation des moteurs sous Linux

Dans le lanceur, les moteurs utilisent Landlock (ABI 3 minimum) et la bibliothèque
système `libseccomp2`. Une protection indisponible empêche le traitement.
Les sorties sont préparées en privé avant publication, sans écrasement des
fichiers existants. Cette voie évite les namespaces imbriqués refusés par certains
profils AppArmor. L'interface garde accès au dossier personnel ; certaines
métadonnées de fichiers peuvent rester observables malgré le refus de lecture.
