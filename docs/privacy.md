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
- Les opérations créent de nouveaux fichiers de sortie par défaut.
- Les sources sont préservées par défaut ; tout remplacement proposé exige un choix explicite.
- Par defaut, aucun chemin de document ouvert n'est persiste. La memorisation locale est un
  consentement explicite, distinct de la reouverture automatique au demarrage.
- Si ce consentement est active, seules les sessions bornees, chemins PDF et selection
  courante sont serialises. Le desactiver ou utiliser `Effacer les donnees locales` supprime
  cet etat sans toucher aux PDF.
- Les selections visuelles, groupes de sortie, inspections et empreintes de fichiers restent
  uniquement en memoire. Les identifiants documentaires de session sont aleatoires.
- Le lecteur et les miniatures demandent le rendu QtPdf à un processus séparé. L'interface reçoit des pixels bruts et des métadonnées bornés ; les miniatures restent en mémoire dans un cache limité.
- Le dossier du dernier PDF ouvert par le sélecteur est mémorisé dans les préférences
  locales (`input/last_dir`) pour que le prochain sélecteur y reparte. Seul le chemin du
  dossier est conservé, jamais le nom ni le contenu d'un document. `Effacer les données
  locales` le supprime avec les autres préférences.
- Le fichier des préférences est réservé à votre compte (droits 0600, dossier
  0700), y compris si d'autres comptes existent sur la machine.
- Retirer un PDF des documents ouverts ne supprime jamais le fichier disque.
- Aucun compte utilisateur n'est requis.
- Aucune telemetrie n'est activee par defaut.
- Aucun document, extrait, miniature, texte OCR, metadonnee ou log sensible n'est envoye sur Internet.

## Wiki et communauté

Le bouton `Aide` lit uniquement les fichiers Markdown FR/EN livrés avec
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

Dans la copie Git officielle privée, le consentement automatique existant n'autorise
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

Pour OPT01, le worker écrit uniquement un candidat dans le répertoire privé du
superviseur. Ce dernier nettoie le répertoire même après l'arrêt forcé du worker,
puis publie seulement un candidat vérifié et strictement plus petit, via les
primitives atomiques sans remplacement. Aucun fichier n'est créé sans gain.
Un arrêt brutal de toute l'application ne garantit pas ce nettoyage.
La compression ne retire ni métadonnées ni couche OCR ; elle n'est pas une
sanitisation. Les PDF chiffrés et signatures détectées sont refusés.

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

Le confinement réseau ne suffit pas à protéger les fichiers locaux après une
compromission native. Dans le lanceur, les workers appliquent Landlock et seccomp.
Hors lanceur, ils utilisent le profil Bubblewrap complet. Le rendu et l'inspection n'ont
accès qu'aux entrées demandées, au runtime en lecture seule et à leur temporaire
privé ; ils ne reçoivent ni socket graphique, ni broker de mise à jour, ni session
utilisateur sous `/run`. La réponse de rendu n'est pas un PDF ou une image
compressée à décoder dans l'interface.

La compression et les outils de mot de passe utilisent une sortie privée publiée
par le superviseur. Dans le lanceur, cette préparation privée couvre aussi les
opérations structurelles. Hors lanceur, ces dernières conservent encore un accès
au dossier de sortie choisi : un worker compromis pourrait y altérer ses autres
fichiers. L'interface de confiance garde accès aux dossiers personnels pour
ouvrir et publier les documents, ainsi qu'au socket graphique nécessaire et au
broker à commandes limitées. Sous X11, ce socket ne constitue pas une isolation
de la session graphique. Ces limites interdisent une promesse de confinement
absolu aux seuls documents sélectionnés pour toute l'application.

Ces garanties dépendent des protections réellement disponibles sur le système ;
un démarrage réussi ne démontre pas à lui seul le confinement de chaque opération.

Si l'utilisateur ouvre ou ecrit un PDF dans un dossier synchronise par un service cloud installe sur sa machine, la synchronisation depend de ce service et du systeme de l'utilisateur, pas de PriveoPDF.

Les futures fonctions d'IA ou de rendu plus avance devront etre requalifiees avant implementation et conserver la meme promesse locale : pas d'upload de document, pas de compte obligatoire et pas de telemetrie activee par defaut.

## B4 — OCR PDF

La reconnaissance s'exécute dans le worker documentaire isolé (sans réseau,
budget mémoire de rendu, seccomp, Landlock ou bubblewrap), avec la bibliothèque
Tesseract et les modèles du système, lus en lecture seule et jamais
téléchargés. Les images de page et les couches de texte intermédiaires restent
dans le répertoire privé du superviseur, supprimé à la fin de l'échange. Le
texte reconnu n'est ni journalisé, ni renvoyé à l'interface : le résultat ne
transmet que trois compteurs de pages. La copie créée contient ce texte, désormais
extractible et indexable par les outils de recherche de l'ordinateur ; le
remplacement de la source n'est pas proposé. Un arrêt brutal de toute
l'application ne garantit pas le nettoyage des temporaires.

## Mots de passe PDF (B2)

Les mots de passe SEC01/SEC03 ne sont stockés ni dans les préférences, ni dans
les journaux, ni dans les fichiers de jobs, ni dans argv ou l'environnement.
Ils transitent par le pipe stdin privé du worker. Les champs sont vidés au
lancement et à la sortie de l'outil ; les références du job sont libérées après
traitement. Python/Qt ne garantissent pas l'effacement physique de toute copie
mémoire. Un poste compromis reste hors du périmètre. Les boutons Afficher/Masquer
rendent le secret visible uniquement à la demande et reviennent à l'état masqué
quand les champs sont vidés. Le PDF déverrouillé est lisible sans mot de passe :
copie par défaut, ou remplacement du PDF courant après choix et confirmation.
Ce dernier choix n'est pas mémorisé dans les préférences.

## B3 — contrôle avant partage

L'inspection approfondie retourne un rapport en mémoire sans cache partagé,
export ni création d'un PDF. Les valeurs sont affichées en texte brut, sans
liens actifs ni résolution XML externe. Le rapport est recalculé après traitement
et effacé à la sortie de la page. Le retrait standard cible seulement Info et
le XMP global ; commentaires, formulaires, pièces jointes et informations
visibles restent. La photocopie reconstruit l'apparence en images, sans OCR.
Elle ne promet ni anonymat, ni disparition des marques visibles ou du nom,
ni effacement physique sécurisé du disque, du swap ou des sauvegardes.

L'aperçu est un PDF reconstruit privé et temporaire, supprimé après usage ;
l'export reprend le même moteur et profil et exige une source inchangée depuis
l'aperçu. Une annulation ou erreur avant publication conserve l'original.
La photocopie utilise un scope systemd local sans description documentaire.
Dans le lanceur, un relais séparé sans réseau ni documents identifie le worker
connecté par SO_PEERPIDFD et lui impose les limites fixes. Il ne lit aucun corps
de requête. Le worker vérifie les cgroups en lecture seule, ferme le socket puis
active Landlock/seccomp avant lecture PDF et imports natifs. Le namespace du
lanceur reste conservé, sans bus utilisateur ni vue des processus hôtes.
Hors lanceur, le chemin scope puis bubblewrap reste utilisé. Ce contrôle de ressources ne constitue pas une garantie générale de
confinement de tous les composants de l'application. Le lecteur principal et
l'aperçu B3 utilisent le client de rendu isolé, sans QtPdf dans l'interface.

Correctif candidat #284 : seul le relais mémoire isolé accède au bus utilisateur.
Son socket dédié reste distinct de celui du broker de mise à jour. Les lanceurs
source et installé le préparent ; son absence refuse seulement la photocopie.
Linux 6.5+, systemd utilisateur 255+ et libsystemd0 sont requis. Le parcours réel
et le nettoyage à l'arrêt restent à qualifier sur Linux Mint.
Confinement compatible AppArmor (candidat PR276) : namespace du lanceur conservé,
Landlock ABI >= 3 et seccomp dans les workers avant import natif ; sorties privées
puis publication sans écrasement. Dépendance système `libseccomp2`. Aucune
relaxation AppArmor ni repli de production sans protection. Les métadonnées
`stat`/`readlink` ne sont pas masquées ; les limites de confinement sont décrites
dans la section « Limites » ci-dessus.
