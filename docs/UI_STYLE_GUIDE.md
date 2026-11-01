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
- `PixelWordmark` : rendu Qt centralise dans `src/priveopdf/ui/branding.py`, avec variantes `wordmark_full` et `wordmark_compact`. Lorsque `PRIVEOPDF_BETA=1`, le wordmark et sa variante reduite affichent litteralement `[BETA]`; la version stable ne l'affiche jamais.
- `PixelFrame` / `SurfacePanel` : surface noire avec couches de contours decalees, sans ombre floue.
- `ToolCard` : vrai bouton Qt accessible, icone geometrique, titre et description courte, sans badge `Disponible` repetitif ni chevron textuel `>>`. Tab doit afficher le focus ; Entree, Espace et clic doivent emettre une activation unique. En mode sobre, bordure neutre permanente et accent seulement interactif. En mode pixel, couches RGB controlees. Chaque outil visible doit avoir une silhouette differente, pas seulement une couleur differente.
- `Dashboard` : sans document, dropzone compacte (`PdfDropZone(compact=True)`), recherche et cartes compactes (`ToolCard(compact=True)` : icone et titre, description en infobulle et description accessible) groupees par `ToolSpec.dashboard_group` dans l'ordre du registre. Les groupes sont empaquetes en bandes de quatre colonnes egales : un groupe court partage sa bande avec le suivant s'il y tient. Les outils disponibles restent visibles sans defilement a 1366 x 768 (test `test_dashboard_shows_all_tools_without_scrolling_at_1366_by_768`). Avec des documents, un bandeau de contexte (nombre de PDF, document selectionne, `Ajouter PDF`) remplace la dropzone ; le catalogue reste visible. Une action recommandee n'apparait que si les documents l'appellent (PDF selectionne protege : Deverrouiller ; sinon deux PDF ou plus : Fusionner), jamais par defaut. Un document protege porte le suffixe traduit `[protégé]` / `[protected]` dans la sidebar, distinct de `[!]` (PDF illisible). La liste des documents reste dans la sidebar seulement. Les fonctions futures vivent dans une liste secondaire non actionnable alimentee par `ToolSpec`, repliee sous la grille.
- Raccourcis des pages outils : `Ctrl+Entrée` declenche l'action par `ToolActionBar.request_action` (rien si l'action est bloquee) et `Échap` revient en arriere. Ils sont attaches a la pile centrale (`WidgetWithChildrenShortcut`) pour laisser `Échap` au renommage inline de la sidebar. L'infobulle du bouton d'action les rappelle (`tool.action.shortcut`). Entree seule reste au widget qui a le focus.
- `Tool switcher` : bouton topbar `OUTILS` / `TOOLS` et raccourci `Ctrl+K`, menu compact avec `Tous les outils` puis les outils disponibles uniquement ; il ne remplace pas la surface PDF par un menu permanent.
- `Documents ouverts` : au premier lancement, la section complete reste masquee tant que seule la session automatique vide `Session 1` existe, afin de ne pas afficher une fausse session ni `Aucun PDF ouvert`. Elle reapparait automatiquement des qu'un PDF, une session renommee ou plusieurs sessions existent, puis se remasque apres le retrait du dernier PDF si seule `Session 1` subsiste. Les cartes de sessions locales restent des `WorkspaceCard` internes, empilees sans menu deroulant lateral, dans une zone `WorkspaceScroll` qui defile verticalement des que la place manque (contrat UX, L3 : aucune ligne compressee ni superposee, pas de defilement horizontal) ; l'infobulle de chaque carte explique son role et le renommage par double-clic ; jusqu'a 5 sessions peuvent etre restaurees localement par chemins PDF, noms et selection courante. En sidebar reduite, l'entree compacte suit la meme regle de visibilite et doit rester explicite avec libelle `Doc` ou `Docs`, sans compteur ni nom de session visible, tooltip `Afficher les documents ouverts` / `Show open documents` et clic pour redeplier la sidebar.
- `Workspace document item` : ligne compacte de hauteur fixe avec nom de PDF raccourci par `elide_file_name` (debut et extension gardes, fin du nom favorisee), nom complet en infobulle, nombre de pages si connu, menu contextuel `Retirer des documents ouverts` et croix discrete au hover/actif ; ce retrait ne supprime jamais le fichier disque.
- `DocumentWorkspace` / route `Visualiser PDF` : sans document, le vrai mode document affiche l'unique `PdfInputPanel` commun avec sa dropzone et son bouton de selection, puis charge le PDF choisi dans le workspace ; aucune ancienne page lecteur parallele ne doit servir de preuve a ce parcours. Avec un document, le lecteur PDF local base sur QtPdf reste l'experience de lecture unique visible, avec ajustement largeur par defaut pour une nouvelle installation (contrat UX, L7 et E11), preference ajustement page disponible et mode multipage scrollable. Dans `MainWindow`, le nom du fichier n'apparait qu'une fois, dans la topbar ; l'en-tete du document ne le reprend qu'en mode lecture, qui masque la topbar. La zone PDF garde la priorite : la colonne droite est fermee par defaut et devient un tiroir facultatif affichant soit `Pages`, soit `Infos`, jamais les deux a la fois. Le panneau permanent `Actions` est interdit ; un bouton unique `Utiliser avec...` ouvre seulement les outils disponibles compatibles avec un PDF unique. Dans la barre de lecture, le compteur `Page n / N` est lui-meme un selecteur numerique encadre, desactive sans document et borne de 1 au nombre de pages, qui reste synchronise avec le navigateur et la miniature active ; le zoom utilise `-`, le pourcentage reel, `+` et un menu unique `Ajuster` pour page/largeur. `Plus` regroupe le mode lecture et `Ouvrir le dossier` ; ne jamais appeler cette derniere action `Exporter`. Le mode lecture masque temporairement le tiroir, la sidebar et la topbar, reste reversible par `Ctrl+Maj+R` / `Ctrl+Shift+R` et ne modifie jamais le PDF. Les miniatures locales bornees restent dans le tiroir `Pages`, via `DocumentPagesPanel` : conteneur full-width, lignes pleine largeur avec stretches gauche/droite, couple miniature + libelle centre horizontalement et scrollbar a droite du bloc. Les badges diagnostic compacts restent dans l'en-tete du document. Socle 6A : `IsolatedPdfView` porte la seule conversion page/ecran (`page_at`, `page_rect`, `to_page`, `to_view`), les calques dessines au-dessus de la page (`PageOverlay`, `add_overlay`) et l'outil actif qui recoit la souris (`ViewerTool`, `set_active_tool`) ; sans outil actif, l'ecran reste un lecteur simple. `DocumentWorkspace` expose `set_edit_bar(widget)` : la barre contextuelle `ViewerEditBar`, sous la barre de lecture, n'apparait qu'avec un outil actif et jamais en mode lecture. Le zoom (Ctrl+molette, `+`, `-`) est centre sur le pointeur ou le centre de la vue et conserve les pixels precedents jusqu'au nouveau rendu : aucune page blanche entre deux pas.
- `RotatePdfPage` : page dediee a la rotation, avec grande page active rendue localement sans rotation appliquee par defaut, une seule ligne de miniatures separee de la preview ; l'angle (`0/90/180/270`) se regle par `À gauche` et `À droite` seuls et s'affiche en clair (`RotationAngleValue`), sans liste d'angles (contrat UX, L5 et E6). Mise en page d'edition de pages (adaptation de la regle 1 du contrat UX) : aperçu et miniatures a gauche ; a droite, une colonne de largeur `SIZES["tool_side_column"]` empile Réglages (`Angle` et sa valeur, `À gauche`, `À droite`, `Cible` avec `Toutes les pages` par defaut), la sortie (`OutputTargetField`) et l'action unique (`ToolActionBar`). Aucune barre de réglages en haut. Tout reste visible sans defilement a 1366 x 768. L'angle 0° bloque l'action avec sa raison (`rotation.required.angle`).
- `install_page_tool_layout` (`components/tool_flow.py`) : mise en page commune des outils d'edition de pages (Tourner, Diviser, Extraire, Supprimer, Reorganiser). Retour seul sur la premiere ligne, description et entree PDF, puis les pages a gauche et une colonne `PageToolSideColumn` de largeur `SIZES["tool_side_column"]` a droite qui empile Reglages, Sortie et Action. Le contenu ne defile que si la fenetre est trop petite. Test : `test_page_editing_tools_fit_beside_the_sidebar_at_1366_by_768`. Ne pas recreer cette structure localement.
- Diviser : une seule liste `DECOUPER` (`Toutes les N pages` par defaut avec N = 2, `Une page par fichier`, `Par groupes (glisser-deposer)`, `Par plages`) en tete de la colonne de droite, sans bouton `Mode avance` (contrat UX, L5) ; les zones de sortie par glisser n'apparaissent qu'avec `Par groupes`, le champ de plages qu'avec `Par plages`. L'annonce des fichiers (`split.announce.*`) se place sous la destination, avant le bouton.
- Outils de pages (`VisualPageOperationPage`, `PageOperationPage`, `InsertPdfPagesPage`, `InsertBlankPage`) : sortie proposée par `OutputTargetField` (dossier pour Diviser), action et résultat par `ToolActionBar` ; la raison du blocage (aucune page placée, toutes les pages supprimées, document d'une page pour Réorganiser) s'affiche sous le bouton.
- `SplitPdfPage` : page visuelle source unique ; avec `Par groupes`, PDF de sortie vides au depart, deux zones de sortie dans l'ordre 1 puis 2, bouton `+ Ajouter un PDF de sortie`, vraies miniatures de pages completes dans les groupes, retrait contextuel et groupes vides ignores ; les plages sont un choix de la liste `DECOUPER`.
- `ExtractPdfPage` : page visuelle source unique -> `PDF extrait` vide au depart, clic ou drag depuis la source, vraie miniature complete dans la sortie, ordre de sortie modifiable, retrait contextuel et mode avance replie.
- `RemovePagesPage` : grille unique de miniatures, clic pour barrer/restaurer les pages a supprimer avec croix fine, suppression de toutes les pages refusee et mode avance replie.
- `PdfPageThumbnailGrid` : la page courante ou selectionnee est signalee par son seul cadre d'accent (`QListView#ThumbnailList`), jamais grisee comme une page marquee (contrat UX, L5). Les marques gardent leur dessin propre : croix rouge pour une page supprimee, cadre de 3 px couleur succes (`color_success`) pour une page placee, distinct du cadre d'accent de 2 px de la page courante. `select_all_pages()` selectionne toutes les pages sans reduire la selection au chargement (Inserer des pages).
- `PdfInputPanel` : entree PDF commune. A vide, une seule grande zone `Deposez un PDF ici ou parcourez l'appareil`; une fois charge, dropzone masquee et bouton compact `Changer PDF` ou `Ajouter PDF` ouvrant directement le selecteur du systeme, sans fenetre intermediaire. Un PDF depose n'importe ou sur la fenetre rejoint la source de l'outil courant (ou les Documents ouverts hors outil). Le selecteur part de `PRIVEOPDF_OPEN_DIR` ou du `dev_corpus` en dev et Beta, sinon du dernier dossier utilise, sinon de Documents.
- `PdfPageThumbnailGrid` : composant commun de miniatures rendu localement avec QtPdf dans un worker isolé, page entiere sans crop, numero visible, selection clavier/souris, drag source optionnel, etats `chargement` / `apercu indisponible` / `ASSIGNEE` / `SUPPRIMEE`, cache borne et layouts `horizontal_strip`, `grid_reorder`, `selection_grid`.
- `IsolatedPdfView` : viewport commun du lecteur ; ne charge jamais le PDF dans l'interface. Consomme les pixels RGBA validés du worker, rend les pages visibles à la demande, conserve navigation multipage, ajustement page/largeur, zoom et copie de sélection. Cache mémoire borné de 48 Mio et deux rendus simultanés. Couleurs d'interface issues de la palette ; papier blanc indépendant du thème. Les limites et preuves système sont décrites dans `docs/security/PDF_COMPARTMENTS.md`.
- `PageOutputGroupWidget` : zone de sortie de pages ordonnees, accepte les miniatures glissees depuis la source, reutilise le provider/cache de la grille source, affiche un placeholder puis la vraie miniature locale complete, permet le reordonnancement interne, le retrait contextuel et reste lisible en mode clair.
- `ElidedLabel` : libelle technique sur une ligne, raccourci au milieu lorsque l'espace manque ; le texte complet reste disponible par infobulle et description d'accessibilite. Utiliser ce composant pour les chemins locaux longs qui ne doivent pas agrandir un panneau.
- `Status feedback` : messages transitoires non sensibles centralises via les composants feedback ; ne pas ajouter de toast ad hoc dans les pages.
- `GuidedActionCue` : une seule prochaine action peut etre signalee a la fois dans un parcours lineaire. `ToolActionBar` porte le sien et le pointe sur son bouton d'action des que rien ne le bloque et tant qu'aucun resultat n'est affiche ; une page outil n'en cree pas un second. `ToolActionBar` porte le sien et le pointe sur son bouton d'action des que rien ne le bloque et tant qu'aucun resultat n'est affiche ; une page outil n'en cree pas un second. Une vague nette traverse le bouton pendant 960 ms, puis reste absente 4 800 ms. Les presets Pixel utilisent successivement bleu, vert, jaune, orange et rouge ; les presets Sobre utilisent uniquement leur accent d'interaction. Le bouton garde un contour statique renforce et un libelle `Etape suivante` / `Next step` lorsque `reduce_motion` est actif. L'overlay ne capture jamais la souris et s'arrete si la cible est masquee, desactivee, detruite, en cours d'execution ou remplacee.
- `PdfDropZone` : grand bloc noir encadre, coins pixel colores, retour textuel sur accepte/refuse.
- `StatusPill` : badge rectangulaire uppercase, statut explicite, couleur semantique, avec variante compacte pour les diagnostics courts du visualiseur.
- `Buttons` : primary, secondary, danger, ghost, icon button, disabled state.
- `ProgressOverlay` : traitement local en cours, barre segmentee en blocs carres.
- `OutputTargetField` : zone Sortie commune des outils (`docs/ux/UX_CONTRACT.md`, regle 4). Des qu'une source existe, propose `<dossier>/<source><suffixe>.pdf` sans dialogue : dossier de sortie par defaut des Parametres, sinon dossier de la source ; suffixe traduit (`output.suffix.<outil>`). Un nom deja pris devient `-2`, `-3`… ; le bouton `CHANGER…` ouvre le dialogue sans confirmation d'ecrasement et un choix manuel est conserve jusqu'a la prochaine source. Le chemin s'affiche dans un `ElidedLabel` avec infobulle complete.
- `SourceCheck` : vérification de la source au chargement (logique L4 du contrat UX). Placé sous la source de chaque page outil ; compte les pages dans le worker isolé (`QtPageCountRunner`, un fichier à la fois) ou reçoit le résultat d'un comptage déjà fait par la page (`record`). Un PDF protégé affiche `Ce PDF est protégé par mot de passe.` (`ErrorText`) et le bouton secondaire `DÉVERROUILLER PDF`, qui ouvre Déverrouiller sur ce fichier ; un PDF vide, tronqué ou non PDF affiche `Ce PDF est illisible ou endommagé.`, et `Changer PDF` reste le bouton compact de `PdfInputPanel`. Dans Déverrouiller, un PDF non protégé affiche `Ce PDF n'est pas protégé : rien à déverrouiller.`. Protéger et Déverrouiller masquent les champs de mot de passe, et les vident, tant que la source pose problème. Fusionner et Insérer nomment chaque fichier en cause, une ligne par fichier. La même phrase bloque le bouton d'action ; pendant la vérification, `Vérification du PDF…` le bloque aussi. Une source déjà vérifiée l'est de nouveau quand son fichier change (PDF déverrouillé en place). Un fichier introuvable ou inaccessible n'est pas signalé ici : le traitement donne sa propre raison. Masqué sans problème ; une panne du worker sans lien avec le PDF n'affiche rien ici et reste signalée par le traitement. Avec `unsigned_copy=True` (Reconnaître le texte, Caviarder, Filigraner), un PDF signé numériquement affiche `Ce PDF porte une signature numérique…` (`WarningText`, bord avertissement) et la case `Produire une copie sans signature`, décochée à chaque fichier ; `Cochez « Produire une copie sans signature » pour continuer.` bloque le bouton tant qu'elle ne l'est pas.
- Paramètres (`OptionsDialog`) : 760 px de large à l'ouverture, sans barre de défilement horizontale à 1366 × 768 ; le dossier de sortie par défaut occupe sa propre ligne, ses boutons dessous (contrat UX, L7, B33).
- Accueil : la recherche d'outils replace familles et cartes à chaque saisie, sans case vide (contrat UX, L7, B34).
- Erreurs : la ligne d'erreur de `ToolActionBar` se sélectionne pour être copiée ; pour les échecs de protection mémoire (OCR, photocopie), le message principal ne nomme aucun composant système et une ligne `Détail technique : <code>` le suit (`error_detail`, contrat UX, L7).
- `ToolActionBar` : zones Action et Resultat communes (regles 6 a 9). Un seul `PrimaryButton` en capitales, la raison du blocage en une ligne sous le bouton, `ProgressOverlay` + `Annuler` pendant le traitement, puis `Fichier cree : nom` (`ResultText`, bord succes) avec `OUVRIR LE PDF` et `OUVRIR LE DOSSIER`, ou une erreur traduite par code (`ErrorText`, bord danger). Aucune boite modale pour un succes ou une erreur d'execution.
- `Dialogs` : erreurs lisibles, detail technique copiable, style sombre et net, boutons standards sans icone decorative parasite. Les fenetres de verification et d'installation des mises a jour partagent `UPDATE_DIALOG_LAYOUT` pour leur largeur minimale, leurs marges et leur espacement dans tous les presets selectionnables.
- `CommunityPage` : lecteur Markdown natif des 18 pages utilisateur FR/EN livrees avec la version. Il reutilise `SurfacePanel`, le selecteur de pages et les tokens globaux. Les liens relatifs et ancres naviguent uniquement dans la copie installee ; un changement de langue charge la page equivalente. Toute URL externe, traversal, ressource distante ou page absente reste bloquee avec un message local lisible.
- `OcrLanguageDialog` (Reconnaître le texte, `AJOUTER UNE LANGUE…`) : liste filtrable des langues connues (nom + code, installées marquées), `INSTALLER` qui remet le paquet `tesseract-ocr-<code>` au programme d'installation du système (lien `apt://`, mot de passe demandé par le système, aucun téléchargement par PriveoPDF), repli `COPIER LA COMMANDE` ; le dossier des modèles est surveillé et la langue est cochée dès que son fichier existe.
- `AboutDialog` : nom, version installee separee du statut update, promesse locale et licence Apache 2.0 ; pas de phrase passive indiquant qu'un fichier technique existe.
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
- Les libelles de navigation, cartes outils, boutons, badges, parametres, messages pending, acces Aide, bloc local, topbar et dashboard doivent passer par `src/priveopdf/ui/i18n.py`.
- Les reglages persistants passent par `AppSettings` : preset visuel, compatibilite `theme_mode`, `language`, `reduce_motion`, `sidebar_collapsed`, assistant initial, sortie par defaut et verification automatique des mises a jour.
- Le bouton de theme reste une action claire ; les six choix canoniques restent disponibles dans Paramètres et la bascule ne remplace jamais la preference `system`.
- Les outils non disponibles restent visibles s'ils sont utiles a la comprehension produit, mais doivent etre marques pending et ne jamais demarrer un traitement.
- Le catalogue dashboard doit rester centre sur les familles iLovePDF retenues. Les pistes IA restent `roadmap_only` et hors dashboard principal tant que le local n'est pas qualifie.
- La sidebar ne liste pas le catalogue d'outils PDF ; le dashboard central reste la source principale des outils.
- Les documents ouverts de sidebar ne doivent afficher que des PDF reellement ouverts dans l'etat de session actif, avec selection visible. Ils ne stockent pas le contenu des documents et ne suppriment jamais les fichiers disque lorsqu'un PDF est retire.
- Le switcher global ne doit jamais afficher les outils `EN ATTENTE`; avec un PDF courant, l'outil choisi peut recevoir le contexte du document actif.

## Iconographie Et Wordmark

- En sidebar repliee, conserver l'icone applicative officielle via `build_app_icon`,
  y compris son marqueur DEV/BETA. Ce bouton reutilise `GhostButton`, les tailles
  des tokens et un tooltip FR/EN ; clic ou activation clavier redeplie la sidebar
  pour retrouver le wordmark complet et le bloc de confidentialite.

- Les icones sont simples, carrees, geometriques et dessinees localement.
- Les wordmarks visibles doivent utiliser le meme renderer `PixelWordmark` : la variante full pour l'accueil, la variante compact pour la sidebar.
- Les variantes full et compact gardent la meme structure `PRIVEO` + badge `PDF`, les memes proportions visuelles et les memes offsets pixel RGB.
- En runtime beta uniquement, un cartouche rouge `[BETA]` est integre sous le badge `PDF`; l'identite stable reste strictement inchangee.
- L'icone applicative est un monogramme carre distinct du wordmark complet : grand `P` pixel blanc, fond noir/quasi noir et liseres RGB.
- Les assets d'icone Linux sont generes localement depuis `tools/generate_brand_assets.py` dans `src/priveopdf/assets/icons/`.
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

### Compression simple

`CompressPdfPage` réutilise la dropzone, les boutons, panneaux et tokens communs.
Le document reste entier : aucun sélecteur de pages. Deux réglages seulement,
un avertissement avant la réduction renforcée, puis `OutputTargetField` et
`ToolActionBar`. Le résultat conserve les mesures à l'écran (tailles en
octets/Ko/Mo selon la langue) ; l'absence de gain n'offre aucune ouverture de
fichier. Vérifier FR/EN dans les six presets.

### Protection et déverrouillage

`PasswordPdfPage` partage les deux parcours SEC01/SEC03 : entrée PDF commune,
champ Qt natif masqué avec libellé et confirmation seulement pour protéger,
bouton standard Afficher/Masquer à côté de chaque champ, aide courte, puis
`OutputTargetField` avec la case **Remplacer ce PDF** (`allow_replace`) et
`ToolActionBar`. La case est décochée à chaque nouvelle source et en quittant la
page ; elle cache le choix de sortie et exige une confirmation à chaque
lancement. Les résultats restent visibles. **OUVRIR LE PDF** ouvre le PDF dans
PriveoPDF. Le lecteur affiche un état
protégé avec une action de déverrouillage, sans dropzone ni zone grise vide. Aucun aperçu préalable n'est exigé pour un PDF chiffré.
Les champs sont effacés au lancement et à la sortie de la page. Vérifier FR/EN dans
les six presets, y compris erreurs, progression et résultat.

### Caviarder un PDF

`RedactPdfPage` suit la mise en page d'édition de pages (`install_page_tool_layout`) : à gauche, le lecteur `IsolatedPdfView` (socle 6A) avec `RedactionTool` actif et `RedactionOverlay` (zones en couleur `color_danger` translucide, rectangle en cours en pointillé) ; à droite, Réglages (titre `Zones à noircir`, compteur, aide, `Retirer la dernière zone`, `Tout effacer`, boutons secondaires), `OutputTargetField` puis `ToolActionBar`. Le statut sous le lecteur annonce que le PDF produit est une photocopie ; le résultat (L1) ajoute la ligne de vérification (zones, pages). Les textes visibles ne parlent ni d'objet, ni de flux, ni de pixel ; les annotations à apparence (tampons, champs remplis) sont rendues dans le lecteur de cette page comme dans la photocopie produite (`set_render_annotations`).

### Filigraner un PDF

`WatermarkPdfPage` suit la même mise en page que Caviarder : à gauche, le lecteur `IsolatedPdfView` (socle 6A) sans outil de souris, avec `WatermarkOverlay` qui dessine l'aperçu du texte (gris d'impression, opacité de l'intensité choisie, disposition calculée par `domain/watermark_layout.py`, police système étirée à la largeur Helvetica-Bold) ; à droite, Réglages (titre `Filigrane`, `QLineEdit` Texte limité à 120 caractères, listes Disposition et Intensité dans un `QFormLayout`, aide), `OutputTargetField` puis `ToolActionBar`. Le statut sous le lecteur dit que le texte est écrit dans la page et qu'une réédition volontaire peut le retirer ; le résultat (L1) ajoute la ligne de vérification (pages). Un texte vide ou hors Latin-1 bloque l'action avec sa raison et vide l'aperçu ; le panneau de réglages est inactif pendant le job.

### Vérifier avant partage

`SharePdfPage` réutilise PdfInputPanel, SurfacePanel, les boutons et
ProgressOverlay (analyse et aperçu), puis `OutputTargetField` avec
`allow_replace` et `ToolActionBar` pour le traitement final. Le bilan
(contrat UX, L7) : une phrase de synthèse (`ShareSynthesis`, texte brut), un
tableau en lecture seule `ShareReportTable` (Élément · Dans ce PDF · À faire),
puis `Détails techniques` replié (QPlainTextEdit en lecture seule : Info, XMP,
propriétés brutes) et `Recalculer le bilan` après le bilan. Les valeurs
documentaires restent du texte brut. Deux modes dans la
même page, copie par défaut, remplacement confirmé ; en mode photocopie,
l'action reste désactivée avec sa raison tant que l'aperçu n'est pas prêt.
ReaderPdfView affiche seulement le candidat de photocopie vérifié, avec page
et zoom ; aucune capture du lecteur source. La progression numérique provient
du worker. Vérifier FR/EN dans les six presets, aperçu, refus et bilan compris.
