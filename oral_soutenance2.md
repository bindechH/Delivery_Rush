# DELIVERY RUSH — Oral Soutenance 2 (script complet ~15 minutes)

**Équipe :** Rayane, François, Mohamed, Abdallah — EPITA  
**Tech :** Python / Pygame / PyTMX / PyScroll / UDP / JSON  
**Date :** 17 mars 2026

> Ce fichier est un **script à lire** (phrases complètes), découpé en parties, avec transitions + **cues de démo** PC1/PC2/PC3.  
> Aucun passage ne parle de “pourcentage d’avancement”.

---

## Préparation démo (NE PAS LIRE À L’ORAL)

Idéalement, vous avez 3 PC (ou 2 PC + 1 écran supplémentaire) :

- **PC Serveur** : lancer `python server.py` et le laisser tourner.
- **PC1 (écran projeté)** : lancer `python main.py`, rester sur le menu.
- **PC2 + PC3** : lancer `python main.py` et se connecter en multijoueur (deux pseudos différents).

Rappels touches utiles (à garder sous les yeux) :
- **ZQSD** : conduire
- **ESPACE** : frein à main / drift
- **TAB** : liste des joueurs
- **C** : debug collisions (tuiles + hitbox)
- **UP** : ouvrir le téléphone
- **SUPPR** : revenir / fermer le téléphone (évite **ESC** qui retourne au menu)
- **F11** : plein écran
- **ESC** : retour au menu

---

## 1) Introduction — Contexte du projet (≈ 1 min) — Rayane

Bonjour, nous allons vous présenter **Delivery Rush**, un jeu de livraison **2D en vue du dessus** développé en **Python** avec **Pygame**.

Le principe : le joueur conduit dans une ville ouverte, accepte une mission de livraison, puis doit **livrer dans un temps limité** en choisissant son trajet et en maîtrisant la conduite.

Pour cette soutenance 2, on vous présente un prototype jouable où tout s’enchaîne : conduite avec drift, missions, interface téléphone en jeu, et multijoueur.

*(DÉMO — PC1 : rester 2 secondes sur le menu pour montrer l’ambiance et l’identité visuelle.)*

Je vais maintenant vous expliquer comment on a organisé le projet et comment on s’est réparti le travail.

---

## 2) Organisation du projet & répartition des rôles (≈ 1 min) — Rayane

On a structuré le projet de façon **modulaire**, pour travailler en parallèle et garder un code lisible.

Concrètement, on a réparti les responsabilités comme suit :

Mohamed s’est occupé de la **carte** (construite avec Tiled), des **collisions**, de la **détection de surface**, et du **système de missions**.

François s’est occupé du **rendu** : l’interface en jeu, le **HUD**, le **téléphone in-game**, et tout le **menu principal** avec les écrans de paramètres et d’authentification.

De mon côté, Rayane, je me suis concentré sur le **moteur physique**, le catalogue de véhicules, le réseau client, le serveur multijoueur, et la partie son.

Et enfin Abdallah a réalisé le **site web vitrine** qui présente le jeu.

Je passe ensuite sur le planning et la vision globale des soutenances.

---

## 3) Planning prévisionnel & vision des soutenances futures (≈ 1 min) — Rayane

Notre progression suit les trois soutenances du module.

Après un socle validé en soutenance 1, cette soutenance 2 sert à montrer un **prototype jouable** : des missions complètes, une progression, et un multijoueur plus propre.

Pour la soutenance 3, on vise surtout le contenu et le polish : plus de variété, plus d’ambiance sonore, et une finition/optimisation propre.

Je laisse la parole à François pour la présentation technique générale et l’architecture.

---

## 4) Présentation technique générale du jeu (≈ 1 min) — François

Sur le plan technique, Delivery Rush repose sur une boucle Pygame claire : on lit les entrées, on met à jour la physique et les missions, puis on rend la carte, les voitures et l’interface.

L’objectif est que tout reste fluide et lisible : caméra centrée, HUD stable, et objectifs visibles en permanence.

*(DÉMO — PC1 : lancer une partie (solo ou multi) et bouger 2 secondes pour montrer la caméra et le scrolling.)*

Je continue avec l’architecture et les choix technologiques.

---

## 5) Architecture technique & choix technologiques (≈ 2 min) — François

On a une architecture modulaire avec un point d’entrée côté client, et un serveur séparé côté multijoueur.

Le **client** est lancé via `main.py`. Il initialise Pygame, charge la config, puis orchestre tous les modules : la carte, le joueur, les missions, l’interface, et le réseau si on est en multijoueur.

Le **serveur** est lancé via `server.py`. Il tourne indépendamment et gère les connexions, l’authentification, la diffusion des états, et la persistance des données.

Pour la carte, on utilise **Tiled** pour construire la ville en couches. Ensuite on charge cette carte avec **PyTMX**, et on l’affiche avec **PyScroll**, ce qui nous donne une caméra et un rendu optimisé.

Pour le multijoueur, on utilise **UDP** : pour un jeu de conduite, on privilégie la réactivité. Si un paquet est perdu, le suivant corrige très vite.

Les messages sont en **JSON**, ce qui est pratique pour le debug et la persistance.

Enfin, on a séparé la configuration : `config.json` pour les réglages machine, et `solo_save.json` pour la progression solo.

Je passe la parole à Mohamed pour la partie carte et environnement.

---

## 6) Carte & environnement (≈ 1 min) — Mohamed

La ville est pensée comme un environnement ouvert en vue du dessus. On l’a construite avec **Tiled** en séparant les éléments en couches : le sol, les routes, les bâtiments et les zones de collision.

La nouveauté importante de cette soutenance, c’est que la carte n’est plus seulement “jolie”. Elle influence le gameplay.

D’abord, on a des **collisions** : le véhicule ne traverse plus les bâtiments.
Ensuite, on a une **détection de surface** : route ou hors-route. Cette information est utilisée par la physique pour modifier l’adhérence et la vitesse, ce qui rend la conduite plus intéressante.

*(DÉMO — PC1 : rouler doucement contre un bâtiment pour montrer que ça bloque ; puis appuyer sur **C** pour afficher le debug des collisions/hitbox.)*

Je passe maintenant à la partie interface et affichage en jeu.

---

## 7) Interface utilisateur (HUD + affichage en jeu) (≈ 1 min) — François

Pendant la conduite, on a un HUD volontairement clair : l’objectif est de donner au joueur toutes les infos utiles sans casser l’immersion.

On affiche notamment la **vitesse**, l’état de la mission — avec le temps restant et la récompense —, et des aides de navigation : une flèche GPS et une minimap.

On a aussi un mode pratique pour le multijoueur : en maintenant **TAB**, on affiche la liste des joueurs connectés.

*(DÉMO — PC1 : lancer une mission et montrer la barre de mission + la flèche GPS ; puis maintenir **TAB**.)*

Je passe ensuite au menu principal, qui sert à configurer et démarrer correctement la partie.

---

## 8) Menu principal (≈ 1 min) — François

Le menu principal n’est pas juste un écran de départ.
Il permet de lancer le solo ou le multijoueur, mais aussi de gérer les paramètres techniques du jeu.

On a donc un écran de paramètres pour ajuster l’IP/port serveur, les FPS, la résolution, le zoom de la carte, le volume, et le fullscreen.
Et quand on choisit le multijoueur, on passe par un écran d’authentification où on saisit le mot de passe.

*(DÉMO — PC1 : cliquer sur l’icône paramètres ; changer le volume ; appliquer ; puis montrer **F11** plein écran.)*

Je laisse maintenant Rayane présenter la partie son et ambiance.

---

## 9) Sons & ambiance (≈ 45 s) — Rayane

La partie son est gérée par un SoundManager.
Pour cette soutenance, on a une musique d’ambiance qui se lance dès le menu et qui continue à accompagner l’expérience.

L’intérêt, c’était aussi de valider une gestion robuste : on peut changer le volume à la volée depuis les paramètres, et la structure est prête pour brancher des effets plus “gameplay”, comme le moteur, le drift, ou les sons de validation de mission.

*(DÉMO — PC1 : monter/descendre le volume dans les paramètres et montrer que ça s’applique immédiatement.)*

Je passe ensuite à la partie centrale du jeu : les missions.

---

## 10) Missions / livraisons (≈ 2 min) — Mohamed

Les missions sont le cœur de Delivery Rush.

On a défini une liste de points d’intérêt sur la ville — par exemple des lieux publics, des commerces, des zones logistiques — et le système génère des missions **procéduralement** en choisissant un point de ramassage et un point de livraison.

On a trois types de missions :

Les missions **standard**, qui laissent un temps confortable.

Les missions **express**, qui sont plus tendues mais mieux payées.

Et les missions **chaîne**, qui proposent un compromis entre les deux.

La récompense et le temps ne sont pas figés : ils sont modulés par la distance entre le ramassage et la livraison, ce qui évite que toutes les missions se ressemblent.

En jeu, le cycle est très simple : on accepte une mission, on va au point de ramassage, la prise se fait automatiquement quand on arrive à proximité, puis on livre de la même façon à destination.

*(DÉMO — PC1 : ouvrir le téléphone avec **UP**, aller dans l’app Livraisons, accepter une mission. Montrer que les marqueurs et le HUD se mettent à jour.)*

Je laisse ensuite Rayane vous présenter le moteur de conduite et le drift, qui donnent la sensation de jeu.

---

## 11) Moteur physique — Sensations de conduite (≈ 2 min) — Rayane

Le moteur physique de Delivery Rush ne cherche pas la simulation parfaite : on cherche un compromis entre réalisme et plaisir.
Notre objectif, c’est une voiture qui a du “poids”.

Premièrement, on a de l’**inertie** : quand on relâche l’accélération, la voiture glisse et ralentit progressivement.

Deuxièmement, la **direction dépend de la vitesse** : à l’arrêt, on ne pivote pas sur place comme un tank, et à haute vitesse on doit anticiper ses virages.

Troisièmement, on a un vrai **drift** au frein à main : en maintenant **ESPACE**, on réduit l’adhérence latérale et la voiture se met à glisser. Le joueur doit contre-braquer pour garder le contrôle, et ça donne une sensation très arcade, mais cohérente.

Enfin, la carte influence la conduite : hors-route, on perd de l’adhérence et on ralentit, ce qui encourage à rester sur les routes.

*(DÉMO — PC1 : accélérer puis relâcher pour montrer l’inertie ; enchaîner un virage avec **ESPACE** pour montrer le drift et les traces.)*

Je termine en parlant du multijoueur, où cette physique est synchronisée entre plusieurs machines.

---

## 12) Multijoueur (≈ 2 min) — Rayane

Le multijoueur repose sur un modèle **client–serveur**.
L’idée est simple : chaque client calcule sa physique localement, puis envoie régulièrement son état — position, angle, voiture — au serveur en UDP.

Le serveur récupère ces états et les rediffuse à tous les clients.

Pour que le mouvement des autres joueurs soit fluide, on n’affiche pas les positions “brutes” dès qu’elles arrivent. On applique une **interpolation** : on lisse le mouvement entre deux états reçus. Résultat : même si le réseau est irrégulier, l’affichage reste propre.

On a aussi ajouté une authentification : quand on se connecte, on envoie un mot de passe. Côté serveur, il n’est jamais stocké en clair : on le stocke sous forme **hachée avec un sel**, ce qui évite qu’un fichier de données révèle des mots de passe.

Et surtout, le serveur persiste la progression : argent, véhicules possédés, statistiques. Si on se reconnecte avec le même compte, on récupère l’état.

*(DÉMO — PC1/PC2/PC3 : faire rouler tout le monde en même temps ; PC2 fait des virages rapides pour montrer la fluidité chez PC1 ; puis fermer PC3 et attendre quelques secondes pour montrer la disparition après timeout.)*

Je laisse enfin Abdallah présenter rapidement le site web.

---

## 13) Site web (≈ 45 s) — Abdallah

On a réalisé un site vitrine pour présenter Delivery Rush.
L’objectif est d’avoir une page claire qui explique le concept, les fonctionnalités, comment jouer, et qui donne un accès au projet.

Ça nous sert aussi pour communiquer proprement sur le jeu en dehors de l’exécutable.

*(DÉMO — PC1 : ouvrir le site (GitHub Pages ou la version locale dans `docs/index.html`) et scroller quelques secondes.)*

---

## 14) Conclusion (≈ 45 s) — Tous

Pour conclure, cette soutenance 2 montre un prototype complet et cohérent :

On a une ville avec collisions et surfaces, une conduite avec inertie et drift, un système de missions jouable avec économie, une interface téléphone intégrée, et un multijoueur fluide avec authentification et sauvegarde.

La suite, pour la dernière phase, va surtout consister à enrichir le contenu et à polir l’expérience : plus de variété dans les missions, plus de sons et d’effets, et une finition propre.

Merci, et on est prêts pour vos questions.
