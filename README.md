# Delivery Rush

Un jeu de livraison arcade multijoueur en vue du dessus (top-down). Livrez des colis à travers la ville, maîtrisez le drift, achetez de nouvelles voitures et affrontez d'autres joueurs.

**Équipe** : Rayane (bindech), François, Mohamed (Boulanouar) — L3.1 G4 EPITA Promo 2030

## 🎮 Fonctionnalités

### Gameplay
- **Vue top-down** avec scroll fluide et zoom configurable
- **17 véhicules** différents (MICRO à SUPERCAR) avec stats uniques
- **Système de drift avancé** avec adhérence variable, handbrake, survirage haute vitesse
- **Physique réaliste** : accélération, freinage, traînée, collisions
- **Système de missions** : 3 types (standard, express, chain), 150+ emplacements nommés, timer, récompenses dynamiques
- **Missions party coop** : leader-only, défi party serveur, objectifs multi-points
- **Braqueurs IA** sur missions risquées (pression/échec si encerclement)

### Interface
- **Menu principal** avec sélection solo/multijoueur
- **Téléphone in-game** (slide-up) : applications Livraisons, GPS, Boutique, Wiki, Stats (+ Party/Top10 en multi)
- **GPS complet** affichant la carte, missions et position joueur
- **Boutique** : achat de véhicules en fonction de l'argent gagné
- **Garage** : sélection de couleur pour chaque voiture
- **Notations et HUD** : vitesse (km/h), distance parcourue, récompenses

### Multijoueur
- **Mode UDP** : synchronisation temps réel des joueurs et des IA serveur
- **Synchronisation réseau** en temps réel
- **Liste des joueurs** (touche TAB)
- **Sauvegarde serveur** du progrès (argent, véhicules, stats)
- **Système de party** (jusqu'à 3 joueurs)
- **Missions partagées** : seul le leader lance, tous les membres reçoivent la mission
- **Braqueurs synchronisés** visibles sur la route pour tous les joueurs

### Paramètres
- **Résolution configurable** (1280×720 par défaut)
- **Fullscreen** (F11)
- **Zoom de carte** ajustable en paramètres
- **Volumes musique + effets** réglables
- **Difficulté des braqueurs** configurable (1 à 10)
- **Langue FR/EN** configurable

### Debug
- **Touche C** : active/désactive le mode debug (collisions + debug IA)
- **Touche TAB** : Liste des joueurs en ligne

## 📋 Configuration

Modifiez `config.json` :
```json
{
  "resolution": [1280, 720],
  "fullscreen": false,
  "fps": 60,
  "map_zoom": 2.0,
  "volume": 0.25,
  "music_volume": 0.25,
  "effects_volume": 0.75,
  "robber_difficulty": 4,
  "language": "fr",
  "server_ip": "play.deliveryrush.lol",
  "server_port": 12345,
  "multi": {
    "username": "",
    "password": ""
  }
}
```

## 🚀 Démarrage

### Prérequis
- Python 3.8+
- Pygame 2.5.2+
- PyTMX 3.32+
- PyScroll 2.31+

### Installation

```bash
pip install -r requirements.txt
```

### Lancer Solo
```bash
python main.py
```
Sélectionnez "SOLO" au menu.

### Lancer Multijoueur
1. Lancez le serveur :
   ```bash
   python server.py
   ```
2. Lancez le client :
   ```bash
   python main.py
   ```
3. Sélectionnez "MULTI" et entrez vos identifiants.

## ⌨️ Contrôles

| Touche | Action |
|--------|--------|
| **Z** | Accélération |
| **S** | Freinage / Marche arrière |
| **Q** | Tourner à gauche |
| **D** | Tourner à droite |
| **ESPACE** | Frein à main (handbrake) |
| **UP** | Ouvrir/fermer le téléphone |
| **TAB** | Liste des joueurs |
| **C** | Toggle debug (collision + IA) |
| **F11** | Toggle fullscreen |
| **ESC** | Retour au menu |

## 📁 Structure du Projet

```
.
├── main.py                 # Application cliente
├── server.py               # Serveur multijoueur UDP
├── config.json             # Configuration
├── solo_save.json          # Sauvegarde solo
├── requirements.txt        # Dépendances
├── modules/
│   ├── __init__.py        # Export des classes/modules
│   ├── ia.py              # IA trafic + braqueurs + navigation
│   ├── player.py          # Classe joueur + physique + drift
│   ├── map.py             # Rendu Tiled + collisions
│   ├── missions.py        # Système de missions
│   ├── network.py         # Client/serveur UDP
│   ├── rendering.py       # Rendu UI + game loop
│   ├── phone.py           # Interface smartphone
│   ├── sounds.py          # Gestionnaire audio
│   └── translate.py       # Traductions FR/EN
├── assets/
│   ├── images/
│   │   ├── cars/          # Sprites 17 véhicules × 8 couleurs
│   │   ├── HUD/           # Boutons, logo, background
│   │   └── map/           # Tileset, textures
│   ├── fonts/             # Polices TTF
│   ├── sounds/            # Musique et effets
│   └── map/
│       └── maps/
│           └── deliveryrush_map.tmx  # Carte Tiled
├── server_data/           # Données persistées côté serveur
└── __pycache__/           # Cache Python local
```

## 🎨 Véhicules

**Budget-friendly** : MICRO, HATCHBACK, SEDAN, WAGON, VAN, MEDIUM TRUCK

**Sportif** : CIVIC, COUPE, SPORT, SUPERCAR

**Utilitaire** : PICKUP, BOX TRUCK, JEEP, SUV

**Luxe** : LUXURY

Chaque véhicule possède 8 coloris uniques et des stats différentes (vitesse max, accélération, adhérence, etc.).

## 🗺️ Carte

- **Taille** : 8192×8192 pixels (512×512 tuiles de 16 px)
- **Format** : Tiled TMX
- **Couches** : roads_base (surface), collision_8 (obstacles)
- **Collisions** : Grid-based avec rect collision pour les véhicules
- **Zoom** : Configurable (par défaut 2.0)

## 🤖 Multijoueur

### Architecture
- **UDP** : Communication légère et rapide
- **Sync** : Position, rotation, voiture, états mission
- **Cadences serveur** : broadcast 30 Hz, heartbeat timeout 5 s
- **IA serveur autoritaire** : 8 bots (tick IA 8 Hz)

### Flux
1. Authentification avec identifiant/mot de passe
2. Envoi régulier de position au serveur
3. Réception des positions autres joueurs (30 fps)
4. Synchronisation missions/données de progression
5. IA serveur autoritaire (trafic + braqueurs) diffusée aux clients
6. Interpolation client (delay 0.1 s) pour lisser les mouvements distants

### Party coop
- **Création/join de party** (max 3 joueurs)
- **Leader-only start** : seul le leader peut démarrer une mission partagée
- **Objectifs multi-drop** : plusieurs livraisons apparaissent, les joueurs choisissent la destination qu'ils veulent prendre
- **Défi party serveur** : objectifs et timer adaptés à la taille du groupe

## 📊 Stats & Progression

- **Argent gagné** : calcul dynamique selon type, distance, risque et performance
- **Plages de base** : standard 100-250, express 200-500, chain 150-350
- **Distance parcourue** : Tracée et stockée en pixels
- **Temps jeu** : Visible en session
- **Sauvegarde** : Auto-save en solo, sync serveur en multijoueur

## 🐛 Débogage

### Afficher collision boxes
Appuyez sur **C** pendant le jeu pour activer le debug collision display.

### Logs
Vérifiez la console pour les traces réseau, chargement assets, erreurs.

### Erreur WinError 10040 (UDP datagram trop gros)
Si le client affiche une erreur de réception UDP trop grande :
- vérifiez que vous lancez bien le serveur avec la version à jour du repo
- redémarrez serveur + client
- évitez d'avoir plusieurs serveurs simultanés sur le même port

### Erreur WinError 10048 (port déjà utilisé)
Le port UDP `12345` est déjà occupé par un autre processus.
- fermez l'ancien serveur
- ou changez `server_port` dans `config.json` et relancez serveur + client avec le même port

### Réinitialiser sauvegarde
Supprimez `solo_save.json` pour recommencer en solo.

## 📝 Licence

Projet étudiant - EPITA 2026

## 🔗 Ressources

- **PyScroll** : https://github.com/bitcraft/pyscroll
- **PyTMX** : https://github.com/bitcraft/pytmx
- **Pygame** : https://pygame.org
