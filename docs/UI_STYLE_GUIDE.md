# PriveoPDF Pixel Build Local

Ce guide est la source de verite graphique du projet. La direction artistique definitive est **PriveoPDF Pixel Build Local** : une application desktop locale, rectangulaire, lisible et privee, avec un mode sobre par defaut pour la beta publique Linux et un mode pixel conserve pour l'identite forte.

Le nom produit visible est **PriveoPDF**. Certains noms internes historiques peuvent subsister temporairement dans le code tant qu'ils ne sont pas exposes a l'utilisateur.

## Philosophie visuelle

- Application PDF locale, confidentielle, sans cloud, sans compte et sans envoi en ligne.
- Esthetique desktop assumee : outil local puissant, calme et professionnel par defaut, pixel-art disponible comme signature visuelle.
- Le mode beta Linux demarre en `dark_pro`, affiche comme `Sombre sobre`.
- Le selecteur propose six choix canoniques seulement, dont un suivi automatique du schema clair/sombre du systeme.
- La decision produit pour Windows/macOS futurs est `light_pro`, affiche comme `Clair sobre`, sans hardcode tant que ces plateformes ne sont pas qualifiees.
- Formes rectangulaires et anguleuses, construites sur une grille 4/8 px.
- Les effets de profondeur restent nets, jamais flous.
- Les modes sobres utilisent une palette neutre et une seule couleur d'accent principale.
- Les modes pixel utilisent les couches rouge, jaune, vert et bleu de facon controlee.
- Le pixel-art doit rester techno et premium, jamais enfantin ou cartoon.
- La promesse `100 % local` doit etre principalement portee par le bloc bas gauche de la sidebar.
- Ne pas multiplier les badges de confiance identiques sur une meme page.

## Presets Et Migration

Le choix persistant et la palette appliquee sont deux notions distinctes. `system`
reste enregistre comme preference et se resout au runtime vers `light_pro` ou
`dark_pro` selon le schema Qt. Si Qt ne fournit pas cette information, le repli
est `dark_pro`. Aucun polling ni acces reseau n'est utilise.

Les six choix visibles dans Paramètres sont, dans cet ordre :

- `system` : `Automatique — suivre le système` ;
- `dark_pro` : `Sombre — Sobre` ;
- `light_pro` : `Clair — Sobre` ;
- `dark_pixel` : `Sombre — Pixel` ;
- `light_pixel` : `Clair — Pixel` ;
- `dark_contrast` : `Contraste élevé`.

Compatibilite obligatoire :

- Une nouvelle installation Linux beta utilise `dark_pro`.
- Les anciens presets clairs `light_coral`, `light_ocean`, `light_sage`,
  `light_lavender` et `light_solar` migrent vers `light_pro`.
- Les anciens presets sombres `dark_midnight`, `dark_forest`, `dark_plum`
  et `dark_graphite` migrent vers `dark_pro`.
- Une ancienne preference `dark` migre vers `dark_pixel` et `light` vers
  `light_pixel`.
- Les palettes historiques restent dans les tokens pour relire les anciennes
  configurations, mais ne sont plus affichees dans le selecteur.
- La bascule de luminosite utilise des paires explicites. `dark_contrast`
  bascule vers `light_pro`, faute de palette contraste clair, et `system`
  reste `system`.

## Palette Sobre

Les modes `Sobre` sont les modes professionnels et grand public/PME/juridique/compta.

- Palette neutre, contraste eleve, lisibilite prioritaire.
- Une seule couleur d'accent principale pour l'interaction.
- Couleurs semantiques uniquement pour success, warning, danger et info.
- Aucune bordure RGB permanente sur cards, boutons, menus ou navigation.
- Accent couleur autorise sur hover, focus, actif, selection et action principale.
- Le logo et le bloc `100 % local` peuvent rester plus identitaires que le reste.

## Palette Pixel

Les modes `Pixel` conservent l'identite actuelle avec bordures et couches RGB controlees.

- Fond sombre ou clair selon `brightness`.
- Couches pixel decalees rouge/jaune/vert/bleu sur composants identitaires.
- Les bordures RGB doivent rester lisibles et ne pas generer de bruit visuel sur les textes longs.
- Les textes d'aide, descriptions longues et paragraphes restent en police UI lisible.

Les palettes decoratives historiques sont conservees uniquement pour la
compatibilite des preferences. Elles ne doivent plus etre proposees dans une
nouvelle interface.

## Palette dark existante

- `color_bg_main`: `#000000`
- `color_bg_alt`: `#030303`
- `color_bg_rail`: `#080808`
- `color_bg_surface`: `#0D0D0D`
- `color_bg_surface_hover`: `#121212`
- `color_text_main`: `#F5F5F0`
- `color_text_secondary`: `#B8B8B0`
- `color_text_muted`: `#7E7E78`
- `color_pixel_red`: `#FF2D20`
- `color_pixel_yellow`: `#FFD43B`
- `color_pixel_green`: `#7ED957`
- `color_pixel_blue`: `#2BB7E5`
- `color_pixel_orange`: `#FF8A1F`
- `color_border_default`: `#242424`
- `color_border_active`: `#2BB7E5`
- `color_focus_primary`: `#2BB7E5`
- `color_focus_secondary`: `#FFD43B`

## Palette light existante

Le mode clair reste techniquement disponible et persistant. Il adopte un rendu `papier technique retro`, pas une interface SaaS blanche dominante.

- `color_bg_main`: `#F7F3E8`
- `color_bg_alt`: `#EFE7D4`
- `color_bg_rail`: `#E7DEC8`
- `color_bg_surface`: `#FFFDF4`
- `color_bg_surface_hover`: `#F4EEDC`
- `color_text_main`: `#121212`
- `color_text_secondary`: `#353530`
- `color_text_muted`: `#5C5C56`
- Les accents pixel rouge, jaune, vert, bleu et orange restent conserves mais doivent garder un contraste suffisant sur surfaces claires.

## Typographie

- Base UI lisible par defaut.
- Windows : Segoe UI fallback.
- Linux : Inter, Noto Sans, DejaVu Sans fallback.
- macOS : system fallback.
- Police mono/pixel reservee au logo/wordmark, titres courts, boutons, badges/status pills et labels tres courts.
- Descriptions longues, textes d'aide, tooltips longs et paragraphes : police UI lisible, casse phrase acceptable.
- Ne jamais telecharger de police au runtime.
- Aucun emoji dans l'UI.

## Grille Et Formes

- Unite pixel : 4 px.
- Unite de grille : 8 px.
- Rayons : 0, 2 ou 4 px maximum.
- Bordures : 1, 2 ou 4 px, nettes.
- Pas de blur, pas de glassmorphism, pas de neumorphism, pas de pastel.
- Les surfaces importantes utilisent une bordure sombre et des couches decalees rouge/jaune/vert/bleu.

## Composants Standards

- `AppShell` / `MainWindow` : fond noir, sidebar fixe, top bar compacte, separateurs nets.
- `Sidebar` : fond `color_bg_rail`, entree `ACCUEIL`, section `DOCUMENTS OUVERTS`, bouton `AIDE` / `HELP`, puis bloc local bas gauche, bouton manuel de mise a jour encadre sans voyant decoratif et ligne `Paramètres` / `Settings` / version. Le bouton Aide reste directement au-dessus du bloc local et ouvre uniquement le wiki installe sans reseau. Le bouton de mise a jour reste directement au-dessus de la version, ne se connecte jamais avant confirmation et porte aussi l'installation lorsqu'une copie Git officielle est eligible.
- `Sidebar collapsed` : largeur compacte, acces clavier conserve, initiales ou pictos lisibles, tooltips FR/EN obligatoires. Le controle de reduction est une poignee de panneau sans libelle visible, dessinee comme un grip vertical semi-integre au separateur cote contenu, jamais un bouton texte ni un chevron `<<` / `>>` assimilable a un retour.
- `TopBar` : titre de page, bouton compact `OUTILS` / `TOOLS`, bouton texte `A PROPOS` / `ABOUT`, bouton de theme/preset. Le statut de mise a jour n'y est plus affiche.
- `PixelWordmark` : rendu Qt centralise dans `src/pdfmod/ui/branding.py`, avec variantes `wordmark_full` et `wordmark_compact`. Lorsque `PRIVEOPDF_BETA=1`, le wordmark et sa variante reduite affichent litteralement `[BETA]`; la version stable ne l'affiche jamais.
- `PixelFrame` / `SurfacePanel` : surface noire avec couches de contours decalees, sans ombre floue.
- `ToolCard` : vrai bouton Qt accessible, icone geometrique, titre et description courte, sans badge `Disponible` repetitif ni chevron textuel `>>`. Tab doit afficher le focus ; Entree, Espace et clic doivent emettre une activation unique. En mode sobre, bordure neutre permanente et accent seulement interactif. En mode pixel, couches RGB controlees. Chaque outil visible doit avoir une silhouette differente, pas seulement une couleur differente.
- `Dashboard` : sans document, grande action `Ouvrir des PDF`, dropzone, recherche et exactement neuf cartes d'outils disponibles. Les fonctions futures vivent dans une liste secondaire non actionnable alimentee par `ToolSpec`. Avec des documents, le panneau contextuel existant devient prioritaire et `Tous les outils` permet de rouvrir le catalogue.
- `PendingToolPage` : page simple pour outil non disponible, badge `EN ATTENTE` / `COMING SOON`, description courte et aucun lancement de job.
- `Tool switcher` : bouton topbar `OUTILS` / `TOOLS` et raccourci `Ctrl+K`, menu compact avec `Tous les outils` puis les outils disponibles uniquement ; il ne remplace pas la surface PDF par un menu permanent.
- `Documents ouverts` : au premier lancement, la section complete reste masquee tant que seule la session automatique vide `Session 1` existe, afin de ne pas afficher une fausse session ni `Aucun PDF ouvert`. Elle reapparait automatiquement des qu'un PDF, une session renommee ou plusieurs sessions existent, puis se remasque apres le retrait du dernier PDF si seule `Session 1` subsiste. Les cartes de sessions locales restent des `WorkspaceCard` internes, empilees sans menu deroulant lateral ; jusqu'a 5 sessions peuvent etre restaurees localement par chemins PDF, noms et selection courante. En sidebar reduite, l'entree compacte suit la meme regle de visibilite et doit rester explicite avec libelle `Doc` ou `Docs`, sans compteur ni nom de session visible, tooltip `Afficher les documents ouverts` / `Show open documents` et clic pour redeplier la sidebar.
- `Workspace document item` : ligne compacte avec nom de PDF, nombre de pages si connu, menu contextuel `Retirer des documents ouverts` et croix discrete au hover/actif ; ce retrait ne supprime jamais le fichier disque.
- `DocumentWorkspace` / route `Visualiser PDF` : sans document, le vrai mode document affiche l'unique `PdfInputPanel` commun avec sa dropzone et son bouton de selection, puis charge le PDF choisi dans le workspace ; aucune ancienne page lecteur parallele ne doit servir de preuve a ce parcours. Avec un document, le lecteur PDF local base sur QtPdf reste l'experience de lecture unique visible, avec ajustement page par defaut, preference ajustement largeur disponible et mode multipage scrollable. La zone PDF garde la priorite : la colonne droite est fermee par defaut et devient un tiroir facultatif affichant soit `Pages`, soit `Infos`, jamais les deux a la fois. Le panneau permanent `Actions` est interdit ; un bouton unique `Utiliser avec...` ouvre seulement les outils disponibles compatibles avec un PDF unique. Dans la barre de lecture, le compteur `Page n / N` est lui-meme un selecteur numerique encadre, desactive sans document et borne de 1 au nombre de pages, qui reste synchronise avec le navigateur et la miniature active ; le zoom utilise `-`, le pourcentage reel, `+` et un menu unique `Ajuster` pour page/largeur. `Plus` regroupe le mode lecture et `Ouvrir le dossier` ; ne jamais appeler cette derniere action `Exporter`. Le mode lecture masque temporairement le tiroir, la sidebar et la topbar, reste reversible par `Ctrl+Maj+R` / `Ctrl+Shift+R` et ne modifie jamais le PDF. Les miniatures locales bornees restent dans le tiroir `Pages`, via `DocumentPagesPanel` : conteneur full-width, lignes pleine largeur avec stretches gauche/droite, couple miniature + libelle centre horizontalement et scrollbar a droite du bloc. Les badges diagnostic compacts restent dans l'en-tete du document.
- `RotatePdfPage` : page dediee a la rotation, avec grande page active rendue localement sans rotation appliquee par defaut, une seule ligne de miniatures separee de la preview, combo d'angle limitee a `0/90/180/270`, barre d'action `Angle [0/90/180/270] | Rotation gauche | Rotation droite | Cible | Choisir sortie | Tourner le PDF`.
- `SplitPdfPage` : page visuelle source unique -> PDF de sortie vides au depart, deux zones de sortie par defaut dans l'ordre 1 puis 2, bouton `+ Ajouter un PDF de sortie`, vraies miniatures de pages completes dans les groupes, retrait contextuel, groupes vides ignores et mode avance par plages replie.
- `ExtractPdfPage` : page visuelle source unique -> `PDF extrait` vide au depart, clic ou drag depuis la source, vraie miniature complete dans la sortie, ordre de sortie modifiable, retrait contextuel et mode avance replie.
- `RemovePagesPage` : grille unique de miniatures, clic pour barrer/restaurer les pages a supprimer avec croix fine, suppression de toutes les pages refusee et mode avance replie.
- `PdfInputPanel` / `PdfOpenDialog` : entree PDF commune. A vide, une seule grande zone `Deposez un PDF ici ou parcourez l'appareil`; une fois charge, dropzone masquee et bouton compact `Changer PDF` ou `Ajouter PDF` ouvrant un dialogue drop/browse.
- `PdfPageThumbnailGrid` : composant commun de miniatures rendu localement avec QtPdf, page entiere sans crop, numero visible, selection clavier/souris, drag source optionnel, etats `chargement` / `apercu indisponible` / `ASSIGNEE` / `SUPPRIMEE`, cache borne et layouts `horizontal_strip`, `grid_reorder`, `selection_grid`.
- `PageOutputGroupWidget` : zone de sortie de pages ordonnees, accepte les miniatures glissees depuis la source, reutilise le provider/cache de la grille source, affiche un placeholder puis la vraie miniature locale complete, permet le reordonnancement interne, le retrait contextuel et reste lisible en mode clair.
- `ElidedLabel` : libelle technique sur une ligne, raccourci au milieu lorsque l'espace manque ; le texte complet reste disponible par infobulle et description d'accessibilite. Utiliser ce composant pour les chemins locaux longs qui ne doivent pas agrandir un panneau.
- `Status feedback` : messages transitoires non sensibles centralises via les composants feedback ; ne pas ajouter de toast ad hoc dans les pages.
- `GuidedActionCue` : une seule prochaine action peut etre signalee a la fois dans un parcours lineaire. Une vague nette traverse le bouton pendant 960 ms, puis reste absente 4 800 ms. Les presets Pixel utilisent successivement bleu, vert, jaune, orange et rouge ; les presets Sobre utilisent uniquement leur accent d'interaction. Le bouton garde un contour statique renforce et un libelle `Etape suivante` / `Next step` lorsque `reduce_motion` est actif. L'overlay ne capture jamais la souris et s'arrete si la cible est masquee, desactivee, detruite, en cours d'execution ou remplacee.
- `PdfDropZone` : grand bloc noir encadre, coins pixel colores, retour textuel sur accepte/refuse.
- `StatusPill` : badge rectangulaire uppercase, statut explicite, couleur semantique, avec variante compacte pour les diagnostics courts du visualiseur.
- `Buttons` : primary, secondary, danger, ghost, icon button, disabled state.
- `ProgressOverlay` : traitement local en cours, barre segmentee en blocs carres.
- `Dialogs` : erreurs lisibles, detail technique copiable, style sombre et net, boutons standards sans icone decorative parasite. Les fenetres de verification et d'installation des mises a jour partagent `UPDATE_DIALOG_LAYOUT` pour leur largeur minimale, leurs marges et leur espacement dans tous les presets selectionnables.
- `CommunityPage` : lecteur Markdown natif des 17 pages utilisateur FR/EN livrees avec la version. Il reutilise `SurfacePanel`, le selecteur de pages et les tokens globaux. Les liens relatifs et ancres naviguent uniquement dans la copie installee ; un changement de langue charge la page equivalente. Toute URL externe, traversal, ressource distante ou page absente reste bloquee avec un message local lisible.
- `AboutDialog` : nom, version installee separee du statut update, promesse locale et licence proprietaire ; pas de phrase passive indiquant qu'un fichier technique existe.
- `OptionsDialog` : reglages reels uniquement, langue EN/FR, preset visuel, reduction des animations, verification automatique des mises a jour, mode d'ouverture PDF, ouverture optionnelle du dernier PDF au demarrage, sortie par defaut et comportement apres traitement. En runtime Beta seulement, un panneau scrollable identifie la PR/SHA courante et propose au plus les dix versions locales precedentes validees, avec confirmation avant relance ; il est totalement absent de la version stable.
- `FirstRunDialog` : assistant de configuration initiale court limite a la langue, une promesse de traitement local et le bouton `Commencer`. Themes, animations, reseau, sortie et comportement apres traitement restent dans Paramètres.

## Etats UI

- Normal : contraste fort, noir dominant.
- Hover : couche pixel decalee de 1 a 2 px, fond `color_bg_surface_hover`.
- Active : effet bouton arcade presse, leger decalage dans la grille.
- Disabled : contraste reduit mais lisible, pas de confusion avec erreur.
- Focus : contour bleu + jaune, tres visible au clavier.
- Success : vert pixel + message explicite.
- Warning : jaune pixel + message explicite.
- Error : rouge pixel + message explicite.
- Loading : texte d'action local et barre segmentee, jamais de spinner moderne dominant.
- Empty state : message court, action claire, aucun marketing.
- Pending : badge `EN ATTENTE` / `COMING SOON`, message explicite au clic, aucun lancement de job PDF.
- Documents ouverts actifs : la carte selectionnee utilise l'etat actif du style `workspaceCard`; les documents de la session active utilisent `workspaceItem` avec nom de fichier et nombre de pages si disponible. Jusqu'a 5 sessions locales peuvent exister, chacune avec sa liste de PDF et sa selection.
- Rendu PDF : ne jamais generer toutes les pages d'un gros PDF d'un coup ; les miniatures doivent etre lazy, locales, temporaires et bornees.

## Localisation Et Reglages

- L'anglais est la langue canonique par defaut.
- Le francais est disponible via selection explicite de l'utilisateur.
- La v1 ne detecte pas automatiquement la locale OS pour ne pas contredire le defaut anglais.
- Toute cle de traduction manquante doit fallback sur l'anglais.
- Les libelles de navigation, cartes outils, boutons, badges, parametres, messages pending, acces Aide, bloc local, topbar et dashboard doivent passer par `src/pdfmod/ui/i18n.py`.
- Les reglages persistants passent par `AppSettings` : preset visuel, compatibilite `theme_mode`, `language`, `reduce_motion`, `sidebar_collapsed`, assistant initial, sortie par defaut et verification automatique des mises a jour.
- Le bouton de theme reste une action claire ; les six choix canoniques restent disponibles dans Paramètres et la bascule ne remplace jamais la preference `system`.
- Les outils non disponibles restent visibles s'ils sont utiles a la comprehension produit, mais doivent etre marques pending et ne jamais demarrer un traitement.
- Le catalogue dashboard doit rester centre sur les familles iLovePDF retenues. Les pistes IA restent `roadmap_only` et hors dashboard principal tant que le local n'est pas qualifie.
- La sidebar ne liste pas le catalogue d'outils PDF ; le dashboard central reste la source principale des outils.
- Les documents ouverts de sidebar ne doivent afficher que des PDF reellement ouverts dans l'etat de session actif, avec selection visible. Ils ne stockent pas le contenu des documents et ne suppriment jamais les fichiers disque lorsqu'un PDF est retire.
- Le switcher global ne doit jamais afficher les outils `EN ATTENTE`; avec un PDF courant, l'outil choisi peut recevoir le contexte du document actif.

## Iconographie Et Wordmark

- Les icones sont simples, carrees, geometriques et dessinees localement.
- Les wordmarks visibles doivent utiliser le meme renderer `PixelWordmark` : la variante full pour l'accueil, la variante compact pour la sidebar.
- Les variantes full et compact gardent la meme structure `PRIVEO` + badge `PDF`, les memes proportions visuelles et les memes offsets pixel RGB.
- En runtime beta uniquement, un cartouche rouge `[BETA]` est integre sous le badge `PDF`; l'identite stable reste strictement inchangee.
- L'icone applicative est un monogramme carre distinct du wordmark complet : grand `P` pixel blanc, fond noir/quasi noir et liseres RGB.
- Les assets d'icone Linux sont generes localement depuis `tools/generate_brand_assets.py` dans `src/pdfmod/assets/icons/`.
- Les petites tailles 16/24/32 doivent etre des variantes simplifiees, a coordonnees entieres, avec un `P` plus lisible et moins de couches RGB.
- Le wordmark ne doit pas reprendre le mot `BUILD`, ni copier une image fournie comme asset.
- Ne pas copier le logo Mistral AI, Google, iLovePDF, PDF24 ou tout asset proprietaire.
- L'inspiration Mistral reste une influence generale : modules, blocs, glyphes, techno local.

## Animations

- Duree standard : 80 a 160 ms.
- Aucun rebond, aucune animation molle.
- Hover : deplacement visuel tres court des couches colorees.
- Active : bouton presse, translation/padding de 2 a 4 px maximum.
- Drag-over : bordure multicolore active ou scanline sobre.
- Prevoir `reduce_motion` si une animation devient plus ambitieuse.
- Le guidage sequentiel est l'exception longue explicitement cadree : traversee de 960 ms, pause de 4 800 ms, une seule cible, aucun timer de frame actif pendant la pause et aucune variation de geometrie du bouton.

## Accessibilite

- Contraste texte/fond eleve en permanence.
- Focus clavier visible.
- Les informations critiques ne doivent jamais etre transmises uniquement par la couleur.
- Les textes longs restent lisibles et ne doivent pas chevaucher les composants.
- Les couleurs saturees ne doivent pas servir de fond direct a de longs textes.

## Interdictions

- Interface blanche dominante ou palette Google-like.
- Coins arrondis modernes type 12, 16 ou 24 px.
- Gradients flous, ombres realistes, glow massif, glassmorphism, neumorphism.
- Styles inline massifs et QSS duplique hors couche theme.
- Composants ad hoc alors qu'un composant commun existe.
- Copie de logos, assets, icones proprietaires ou wording exacts.
- Logique metier PDF deplacee dans l'UI.
- Promesses cloud, compte ou telemetrie non decidees.
- Badges `100 % local` ou panneaux de confiance repetes dans la meme page.

## Exemple De Page Outil Conforme

Une page outil doit :

1. S'inscrire dans `MainWindow`/`AppShell`.
2. Utiliser `PixelFrame`, `SurfacePanel`, boutons standards, `PdfDropZone` et `StatusPill`.
3. Construire un `JobRequest` valide sans appeler directement le moteur PDF.
4. Afficher erreurs et succes avec message humain, couleur semantique et detail technique copiable si disponible.
5. Ajouter tout nouveau pattern visuel au design system avant usage large.

## Checklist Avant Validation UI

- Le nom visible est PriveoPDF.
- L'interface beta Linux demarre en `Sombre sobre`; les modes pixel restent disponibles.
- Les couleurs, rayons, espacements et animations viennent des tokens.
- Aucun style important n'est code en dur dans une page.
- Le focus clavier est visible.
- Les erreurs et succes ont un texte explicite.
- La promesse locale n'est pas dupliquee partout.
- Le bouton encadre de mise a jour se trouve directement au-dessus de la version, sans voyant decoratif ; sa confirmation, la liste des changements et le helper d'installation separe utilisent le theme global. La topbar ne duplique aucun statut update.
- La version installee reste separee du statut update.
- `tools/check_ui_style.py` a ete lance si disponible.
- Les tests ou smoke tests UI pertinents ont ete reportes.

## Garde-fou Diagnostic

`tools/check_ui_style.py` est un outil d'aide. Il signale les couleurs hex hors tokens, les appels `setStyleSheet` hors couche theme, les gros blocs QSS inline et les anciens noms visibles. Il peut produire des faux positifs ; les resultats doivent etre interpretes, pas appliques aveuglement.
