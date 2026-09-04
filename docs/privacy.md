# Confidentialite

PriveoPDF traite les fichiers sur la machine de l'utilisateur.

Les PDF et leur contenu sont traités localement et ne sont pas téléversés.
Aucune télémétrie n'est activée par défaut. Les vérifications de mise à jour
facultatives peuvent contacter GitHub après une action ou un consentement
explicite. Elles n'envoient ni document, ni contenu de document, ni chemin de
document. L'inventaire détaillé et ses limites figurent dans
`docs/compliance/NETWORK_ACTIVITY.md`.

## Traitement local

- Les PDF selectionnes sont lus localement.
- Les operations du MVP creent de nouveaux fichiers de sortie.
- Les fichiers source ne sont pas modifies.
- Par defaut, aucun chemin de document ouvert n'est persiste. La memorisation locale est un
  consentement explicite, distinct de la reouverture automatique au demarrage.
- Si ce consentement est active, seules les sessions bornees, chemins PDF et selection
  courante sont serialises. Le desactiver ou utiliser `Effacer les donnees locales` supprime
  cet etat sans toucher aux PDF.
- Les selections visuelles, groupes de sortie, inspections et empreintes de fichiers restent
  uniquement en memoire. Les identifiants documentaires de session sont aleatoires.
- Le lecteur et les miniatures rendent les pages localement via QtPdf ; les miniatures sont temporaires et cachees avec une limite de taille.
- Retirer un PDF des documents ouverts ne supprime jamais le fichier disque.
- Aucun compte utilisateur n'est requis.
- Aucune telemetrie n'est activee par defaut.
- Aucun document, extrait, miniature, texte OCR, metadonnee ou log sensible n'est envoye sur Internet.

## Wiki et communauté

Le bouton `Communauté` lit uniquement les fichiers Markdown FR/EN livrés avec
la version et les rend dans un composant Qt natif. Il ne résout aucune URL,
n'exécute aucun JavaScript et n'ouvre aucune connexion.

Le futur portail public sera un complément distinct. Son ouverture dans le
navigateur nécessitera une action explicite et ne transmettra jamais le PDF
courant, son chemin, ses miniatures, son contenu, ses métadonnées ou les
préférences de l'application. Consulter le portail et installer un addon resteront
deux consentements séparés.

## Verification de mises a jour

La verification automatique des mises a jour est desactivee par defaut. Le
premier lancement presente une case non cochee et une annulation n'ouvre aucune
connexion. Ce consentement persistant couvre uniquement le manifeste public
configure. Une verification manuelle reste disponible sans donner un
consentement permanent. Si elle est confirmee pendant un controle automatique,
elle attend la fin de celui-ci puis lance sa propre verification ; le resultat
automatique n'est pas reutilise comme resultat manuel.

Dans une installation distribuee, la verification contacte uniquement une URL
HTTPS configuree sur un hote exact autorise. Le manifeste est borne, strict et
signe Ed25519 ; les cles inconnues, les downgrades et URLs non autorisees sont
refuses. Le canal production reste non configure tant qu'une vraie cle publique
mainteneur n'est pas provisionnee. Aucun artefact distant n'est auto-installe.

Dans la copie Git officielle, le consentement automatique existant n'autorise
pas Git. Seule la confirmation manuelle affichee pour chaque clic permet la
recuperation de `origin/main` dans un stockage Git temporaire prive, apres
controle local de la branche, de la proprete et du remote. Le clone ouvert
reste en lecture seule et le stockage isole est supprime apres la verification.
Les resultats de cette verification Git ne sont jamais stockes ni relus comme
cache du manifeste public.
Git peut transmettre au serveur les donnees techniques normales de sa connexion.
Le broker n'herite ni proxy, ni credential, ni askpass, ni configuration Git/SSH
utilisateur ; PriveoPDF n'ajoute
aucun document, chemin PDF, preference ni journal a cet echange. L'installation
est executee dans un helper separe sans log persistant. Un marqueur d'etat vide
peut rester dans le repertoire Git uniquement apres une interruption
dangereuse afin de bloquer le redemarrage ; il ne contient aucun document,
chemin, preference, identifiant ni sortie de processus.

Cette fonction n'envoie aucun PDF, chemin de fichier, nom de fichier,
metadonnee de document, contenu extrait, miniature, mot de passe ni log
sensible. Hors copie Git officielle, si aucun manifest public n'est configure,
PriveoPDF affiche simplement que la verification des mises a jour n'est pas
configuree et reste utilisable.

## Fichiers temporaires

Le moteur ecrit dans un temporaire aleatoire en mode `0600`, dans le dossier de sortie, force
les donnees sur disque puis publie par une operation atomique sans remplacement. Le temporaire
est nettoye dans un bloc `finally`. Le processus PDF dispose en outre d'un repertoire temporaire
prive et de limites de ressources.

## Logs

L'application et le lanceur n'ecrivent aucun journal persistant par defaut : stdout/stderr sont
herites. Un journal de diagnostic est cree uniquement avec `--debug-log` ou
`PRIVEOPDF_DEBUG_LOG=1`, sous `${XDG_STATE_HOME:-$HOME/.local/state}/priveopdf`, avec dossier
`0700`, fichiers `0600`, rotation 512 Kio et cinq fichiers au maximum. Une redaction centrale
retire chemins complets, noms documentaires et secrets connus ; un log de debug doit malgre
tout etre traite comme sensible et partage seulement apres revue.

Dans le runtime Beta uniquement, `Options > Diagnostic Beta` peut redemarrer explicitement
le meme PR/SHA sous un superviseur local. Cette session opt-in conserve au maximum 512 Kio de
sortie nettoyee, 100 evenements techniques sans chemin documentaire et cinq sessions dans le
profil XDG isole de l'artefact. L'export ZIP est local, prive (`0600`), refuse d'ecraser un
fichier existant et applique une seconde redaction. Il contient uniquement provenance de
l'artefact, versions techniques, controles locaux, statut de sortie, journaux nettoyes et
empreintes des membres. Aucun PDF, miniature, texte extrait, preference, mot de passe, nom ou
chemin documentaire n'est volontairement inclus. L'utilisateur doit relire l'archive avant de
la partager, car une redaction automatique ne peut pas garantir qu'un texte technique
inattendu est sans sensibilite.

## Telemeterie et crash reporting

Aucune telemetrie ni transmission de crash n'est activee. Le rapport de diagnostic Beta reste
sur l'appareil jusqu'a un export manuel et n'est envoye ni a GitHub, ni a PriveoPDF, ni a un
tiers. Toute collecte distante future devra etre optionnelle, documentee et sans document joint.

## Limites

Si l'utilisateur ouvre ou ecrit un PDF dans un dossier synchronise par un service cloud installe sur sa machine, la synchronisation depend de ce service et du systeme de l'utilisateur, pas de PriveoPDF.

Les futures fonctions d'OCR, d'IA ou de rendu plus avance devront etre requalifiees avant implementation et conserver la meme promesse locale : pas d'upload de document, pas de compte obligatoire et pas de telemetrie activee par defaut.
