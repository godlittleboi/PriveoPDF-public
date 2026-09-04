# Conséquences d'un hébergement source public

Réévaluation : 3 septembre 2026.

Un dépôt GitHub public rend accessibles l'arbre courant, les branches, les
commits et leurs métadonnées. La licence peut limiter les usages accordés mais
n'empêche pas matériellement les clones, copies, captures ou forks. Un retour
ultérieur au privé ne supprime pas les copies déjà obtenues.

Pour PriveoPDF, une publication directe du dépôt canonique rendrait notamment
visibles :

- l'historique de développement et les anciennes branches conservées ;
- les anciennes versions de fichiers aujourd'hui supprimés ;
- les noms et adresses de commit enregistrés dans Git ;
- les Issues, Pull Requests, journaux et artefacts futurs rendus publics selon
  les réglages GitHub.

L'audit du 3 septembre 2026 n'a trouvé aucun secret réel dans les contenus
texte et diffs accessibles. Il a toutefois confirmé un ancien chemin
`/home/<redacted-user>/...` et une adresse Gmail dans des métadonnées de
commits. Une PR ordinaire ne peut pas modifier ces objets historiques.

La décision retenue est un nouveau dépôt public sans historique, produit par
l'export allowlisté depuis un SHA complet de `main`. Le dépôt canonique ne sera
ni réécrit, ni purgé, ni rendu public. Un dépôt neuf n'hérite pas de ses branches,
commits, PR, Issues ou exécutions Actions. Son premier commit doit utiliser une
identité générique contrôlée afin de ne pas recopier une adresse privée.

La plateforme affichera néanmoins le compte qui possède le dépôt ou effectue la
publication. Cette identité de plateforme doit être acceptée explicitement ; la
procédure ne peut pas promettre l'anonymat d'un dépôt GitHub public.
