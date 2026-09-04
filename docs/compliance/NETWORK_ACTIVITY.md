# Inventaire des activités réseau

État audité : préparation du 3 septembre 2026. Cet inventaire décrit les chemins
présents ou préparés ; il ne prétend pas qu'un service public est déjà configuré.

Les PDF et leur contenu sont traités localement et ne sont pas téléversés.
Aucune télémétrie n'est activée par défaut. Les vérifications de mise à jour
facultatives peuvent contacter GitHub après une action ou un consentement
explicite. Elles n'envoient ni document, ni contenu de document, ni chemin de
document.

## Flux applicatifs

| Flux | Déclencheur | Destination | Données nécessaires | Données exclues | État |
| --- | --- | --- | --- | --- | --- |
| Manifeste de mise à jour distribué | clic manuel ou consentement persistant séparé, désactivé par défaut | URL HTTPS et hôte exact explicitement configurés | requête HTTPS, version applicative utile au contrôle et métadonnées techniques normales de connexion | PDF, contenu, miniature, métadonnée PDF, nom ou chemin du document, préférence sans rapport, journal | canal production non configuré |
| Vérification Git d'une copie source officielle | confirmation à chaque clic ; le consentement au manifeste ne l'autorise pas | URL HTTPS canonique GitHub ; le remote local n'est qu'une preuve d'identité | références Git nécessaires et métadonnées normales du protocole HTTPS | document, chemin PDF, contenu PDF, miniature, préférence, journal, proxy, credential, askpass, configuration Git utilisateur et SSH | privé, manuel, broker séparé et stockage Git temporaire supprimé |
| Ouverture d'un futur portail communautaire | action explicite ouvrant le navigateur système | URL publique que le propriétaire devra décider | requête normale du navigateur | aucun état du PDF courant transmis par PriveoPDF | URL non décidée ; aucun navigateur embarqué |
| Rapport de diagnostic bêta | redémarrage diagnostique puis export ZIP explicitement demandés dans Options | aucune : création locale seulement | provenance de l'artefact, versions logicielles, état de fin, journal et événements expurgés | PDF, contenu, miniature, mot de passe, préférence, nom et chemin documentaire | disponible uniquement dans le runtime bêta ; partage ultérieur sous contrôle de l'utilisateur |

Une annulation ou l'absence de configuration n'ouvre aucune connexion. Aucun
artefact distant n'est installé automatiquement. Le wiki embarqué est lu depuis
les fichiers locaux, sans JavaScript ni résolution d'URL. Le rapport de
diagnostic n'est jamais envoyé par PriveoPDF : joindre le ZIP à une Issue ou à
un canal privé est une action séparée effectuée par l'utilisateur.

## Flux d'installation et de maintenance

L'installation des dépendances n'est pas hors ligne. `uv` peut contacter les
index de paquets configurés par l'utilisateur ou l'installateur afin de
télécharger les dépendances verrouillées. Git, le système d'exploitation et le
navigateur peuvent aussi effectuer leurs propres connexions. Ces flux ne sont
pas des uploads de PDF par PriveoPDF et restent soumis à leurs configurations.

### Publication DEV du miroir source public

Uniquement dans l'installation canonique privée marquée `DEV`, une action
mainteneur explicite peut préparer puis publier ponctuellement un snapshot source
allowlisté vers GitHub. Le clic dans Paramètres ne réalise aucune connexion depuis
le processus documentaire : il dépose une requête locale privée, ferme
PriveoPDF, puis le wrapper hôte utilise la session `gh` déjà authentifiée du
mainteneur.

Ce flux peut contacter `github.com` et `api.github.com` pour créer ou mettre à
jour `godlittleboi/PriveoPDF-public`, pousser l'arbre source propre et configurer
sa visibilité, Discussions et ses protections. Les données envoyées se limitent
au snapshot source explicitement destiné à devenir public, à sa provenance Git,
aux métadonnées normales des commits de publication et aux requêtes de
configuration GitHub. Sont exclus : PDF utilisateur, contenu ou miniature de
PDF, nom ou chemin documentaire, préférences utilisateur, historique Git privé,
branches/PR/Issues privées, journaux Actions privés et secrets stockés dans
PriveoPDF.

Le jeton obtenu depuis l'authentification locale GitHub CLI est projeté uniquement
dans des fichiers temporaires privés `0600` et supprimé à la fin. Le mode
`VÉRIFIER LA PUBLICATION` construit et contrôle le snapshot sans modifier de
dépôt distant. La première publication crée d'abord le miroir en privé et ne le
rend public qu'après confirmation distincte et configuration des protections ;
un échec ne doit jamais être présenté comme une publication réussie.

Les mainteneurs peuvent aussi utiliser GitHub Actions, GitHub Pages, les registres
de paquets, les sources officielles Qt et la future plateforme réglementaire pour
construire, publier la documentation, auditer ou signaler. Ces flux CI n'existent
pas dans l'application installée. Aucun secret de signature, rapport de
vulnérabilité privé ou document utilisateur ne doit apparaître dans leurs
journaux publics.

## Absences de collecte

- aucune télémétrie ni analytics applicatif ;
- aucun crash reporting automatique ;
- aucun compte PriveoPDF ;
- aucun service cloud PriveoPDF ;
- aucun upload automatique de journal ou de rapport de sécurité.

Tout nouveau flux exige une qualification sécurité/confidentialité, une
documentation de sa destination, des données, du déclencheur et de la durée de
conservation, ainsi qu'un consentement lorsque nécessaire.
