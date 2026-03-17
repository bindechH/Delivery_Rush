# Oral — Delivery Rush (Soutenance 2) — Version 15 minutes

**Date :** 17 mars 2026  
**Format :** script + chrono + cues de démo 3 PC  

> Objectif : tenir **15 minutes** (±30 s) avec une démo fluide.  
> Aucune mention de pourcentages d’avancement.

---

## Avant de commencer (hors chrono)

- **PC Serveur** : `python server.py` (laisser tourner).
- **PC1 (projeté)** : `python main.py` (prêt au menu).
- **PC2 + PC3** : `python main.py` (prêts à se connecter en multi).

**Touches utiles en démo**
- **ZQSD** : conduire
- **ESPACE** : frein à main / drift
- **TAB** : liste des joueurs
- **C** : debug collisions (tuiles + hitbox)
- **UP** : ouvrir le téléphone
- **SUPPR** : revenir / fermer le téléphone (évite **ESC** qui retourne au menu)
- **F11** : plein écran
- **ESC** : retour menu

---

## Chrono (15:00)

- **0:00 → 1:10** : Intro / concept / objectif de la soutenance 2
- **1:10 → 2:10** : Organisation / rôles / méthode de travail
- **2:10 → 4:00** : Architecture & choix technos (modules, Tiled, PyTMX/PyScroll, UDP/JSON, config/saves)
- **4:00 → 5:30** : Carte + collisions + surfaces (**démo mur + C**)
- **5:30 → 7:30** : Physique & drift + impact des surfaces (**démo drift**)
- **7:30 → 10:20** : Missions + HUD/GPS/minimap (**démo mission complète**)
- **10:20 → 11:40** : Téléphone in-game (livraisons / GPS / boutique / garage / stats)
- **11:40 → 14:10** : Multijoueur (auth, interpolation, sauvegarde) (**démo 3 PC**)
- **14:10 → 15:00** : Menu/paramètres + son + site web + conclusion

---

## Script (à lire)

### 0:00 — Intro (≈ 1 min 10) — Rayane

Bonjour, nous allons vous présenter **Delivery Rush**, un jeu de livraison **2D top-down** développé en **Python avec Pygame**.

Le principe : on conduit un véhicule dans une ville ouverte, on accepte une mission de livraison, puis on doit optimiser son trajet pour livrer **dans le temps**.

Pour cette soutenance 2, l’objectif est de montrer un **prototype jouable** : des missions complètes, une conduite plus “nerveuse” avec drift, des collisions, une UI téléphone en jeu, et un multijoueur plus robuste.

*(DÉMO PC1 : rester 2–3 s sur le menu pour l’ambiance.)*

---

### 1:10 — Organisation & rôles (≈ 1 min) — Rayane

On a organisé le projet de façon **modulaire** : chaque grosse fonctionnalité est isolée dans un module, ce qui nous permet de travailler en parallèle.

- Mohamed : carte (Tiled), collisions/surfaces, missions
- François : rendu, HUD, téléphone in-game, menu
- Rayane : moteur physique/voitures, réseau UDP + serveur, son
- Abdallah : site web de présentation

---

### 2:10 — Architecture & choix techniques (≈ 1 min 50) — François

Le point d’entrée client est **main.py**, qui orchestre la boucle de jeu : inputs → update physique → update missions → réseau (si multi) → rendu.

On s’appuie sur :
- **Tiled** pour construire la ville en couches (routes, bâtiments/collisions…)
- **PyTMX + PyScroll** pour charger et afficher la carte avec une caméra fluide
- **UDP + JSON** pour synchroniser rapidement les états (position/angle/voiture)

On a aussi séparé la configuration :
- **config.json** : paramètres techniques + identifiants multi
- **solo_save.json** : progression solo (argent, voitures, stats)

---

### 4:00 — Carte, collisions, surfaces (≈ 1 min 30) — Mohamed

La ville n’est pas juste un décor : on a ajouté des **collisions** avec l’environnement.
Concrètement, le joueur ne traverse plus les bâtiments, et on exploite aussi une info de **surface** (route vs hors-route) qui influence le comportement de la voiture.

*(DÉMO PC1 : rouler dans un mur ; puis appuyer sur **C** pour montrer les collisions.)*

---

### 5:30 — Physique & drift (≈ 2 min) — Rayane

L’objectif du moteur physique est le “feeling” : une voiture qui a du poids.

- **Inertie / drag** : on décélère progressivement
- **Direction dépendante de la vitesse** : plus on va vite, plus il faut anticiper
- **Frein à main** : **ESPACE** réduit l’adhérence et permet le drift
- **Surfaces** : hors-route = moins d’adhérence, moins de vitesse

*(DÉMO PC1 : accélérer puis relâcher ; faire un drift en virage avec **ESPACE** ; passer hors-route pour sentir la différence.)*

---

### 7:30 — Missions + HUD/GPS (≈ 2 min 50) — Mohamed (missions) / François (HUD)

Les missions sont le cœur du gameplay :
- on génère des missions à partir de points d’intérêt de la carte
- une mission a un **ramassage**, une **livraison**, une **récompense** et un **timer**
- la validation se fait automatiquement par proximité (ramassage puis livraison)

Pour guider le joueur sans casser le rythme, on a un HUD :
- barre de mission (objectif / temps / récompense)
- flèche GPS directionnelle + distance
- minimap et notifications

*(DÉMO PC1 : **UP** → app Livraisons → accepter ; suivre flèche GPS ; ramasser puis livrer. Montrer le timer et les notifications.)*

---

### 10:20 — Téléphone in-game (≈ 1 min 20) — François

Plutôt que des menus qui mettent le jeu en pause, on a un **téléphone intégré**.
Il centralise :
- Livraisons (choix/abandon)
- GPS (vue globale)
- Boutique (acheter un véhicule avec stats)
- Garage (équiper)
- Stats (argent, missions, distance)

*(DÉMO PC1 : GPS → Boutique → équiper un véhicule ; revenir accueil puis **SUPPR** pour fermer.)*

---

### 11:40 — Multijoueur (≈ 2 min 30) — Rayane

Le multijoueur suit un modèle **client–serveur** :
- chaque client calcule sa propre physique
- il envoie son état en UDP
- le serveur redistribue les états à tous

Pour que l’affichage soit fluide, on **interpole** les positions reçues : les autres voitures ne “sautent” pas.

On a ajouté deux points importants :
- **authentification** (mot de passe haché + sel côté serveur)
- **sauvegarde serveur** (argent, voitures, stats), récupérée à la reconnexion

*(DÉMO 3 PC : PC2/PC3 se connectent ; tout le monde roule en même temps ; PC2 fait des virages rapides → PC1 montre la fluidité. Puis PC3 ferme brutalement → disparition après timeout.)*

---

### 14:10 — Menu/paramètres, son, site, conclusion (≈ 50 s) — François (menu/son) / Abdallah (site) / Tous (conclusion)

Le menu permet de lancer solo/multi et de régler les paramètres utiles (IP/port, FPS, résolution, volume, plein écran **F11**).
La musique d’ambiance est gérée proprement et le volume est réglable.

On a aussi un **site web vitrine** qui présente le projet et comment jouer.

Pour conclure : Delivery Rush est maintenant un prototype complet et cohérent : conduite + missions + UI téléphone + multijoueur fluide.  
Merci, et on est prêts pour vos questions.
