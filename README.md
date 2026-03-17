# Delivery Rush

Un jeu de livraison arcade multijoueur en vue du dessus (top-down). Livrez des colis à travers la ville, maîtrisez le drift, achetez de nouvelles voitures et affrontez d'autres joueurs.

**Équipe** : Rayane (bindech), François, Mohamed (Boulanouar), Abdallah — L3.1 G4 EPITA Promo 2026

## 🎮 Fonctionnalités

### Gameplay
- **Vue top-down** avec scroll fluide et zoom configurable
- **17 véhicules** différents (MICRO à SUPERCAR) avec stats uniques
- **Système de drift avancé** avec adhérence variable, handbrake, survirage haute vitesse
- **Physique réaliste** : accélération, freinage, traînée, collisions
- **2 types de surface** : route et hors-route (friction différente)
- **Système de missions** : 3 types (standard, express, chain), 40+ emplacements, timer, récompenses

### Interface
- **Menu principal** avec sélection solo/multijoueur
- **Téléphone in-game** (slide-up) : applications Livraisons, GPS, Boutique, Garage, Stats
- **GPS complet** affichant la carte, missions et position joueur
- **Boutique** : achat de véhicules en fonction de l'argent gagné
- **Garage** : sélection de couleur pour chaque voiture
- **Notations et HUD** : vitesse (km/h), distance parcourue, récompenses

### Multijoueur
- **Mode UDP*** : jusqu'à 8 joueurs simultanés
- **Synchronisation réseau** en temps réel
- **Liste des joueurs** (touche TAB)
- **Sauvegarde serveur** du progrès (argent, véhicules, stats)

### Paramètres
- **Résolution configurable** (1920×1080 par défaut)
- **Fullscreen** (F11)
- **Zoom de carte** ajustable en paramètres
- **Volume de musique** réglable

### Debug
- **Touche C** : Affiche les rectangles de collision (rouge) et hitbox (vert)
- **Touche TAB** : Liste des joueurs en ligne

## 📋 Configuration

Modifiez `config.json` :
```json
{
  "resolution": [1920, 1080],
  "fullscreen": false,
  "fps": 60,
  "map_zoom": 2.0,
  "server_ip": "127.0.0.1",
  "server_port": 12345,
  "multi": {
    "username": "YourUsername",
    "password": "YourPassword"
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
| **C** | Toggle debug collision |
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
│   ├── player.py          # Classe joueur + physique + drift
│   ├── map.py             # Rendu Tiled + collisions
│   ├── missions.py        # Système de missions
│   ├── network.py         # Client/serveur UDP
│   ├── rendering.py       # Rendu UI + game loop
│   ├── phone.py           # Interface smartphone
│   └── sounds.py          # Gestionnaire audio
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
└── siteweb/               # Site de présentation du projet
```

## 🎨 Véhicules

**Budget-friendly** : MICRO, HATCHBACK, SEDAN, WAGON, VAN, MEDIUM TRUCK

**Sportif** : CIVIC, COUPE, SPORT, SUPERCAR

**Utilitaire** : PICKUP, BOX TRUCK, JEEP, SUV

**Luxe** : LUXURY

Chaque véhicule possède 8 coloris uniques et des stats différentes (vitesse max, accélération, adhérence, etc.).

## 🗺️ Carte

- **Taille** : 12000×12000 pixels
- **Format** : Tiled TMX
- **Couches** : roads_base (surface), collision_8 (obstacles)
- **Collisions** : Grid-based avec rect collision pour les véhicules
- **Zoom** : Configurable (par défaut 2.0)

## 🤖 Multijoueur

### Architecture
- **UDP** : Communication légère et rapide
- **Sync** : Position, rotation, voiture, états mission
- **Limitation** : ~8 joueurs généralement (montée en charge non testée)

### Flux
1. Authentification avec identifiant/mot de passe
2. Envoi régulier de position au serveur
3. Réception des positions autres joueurs (30 fps)
4. Synchronisation mission et données (si joueur maître)

## 📊 Stats & Progression

- **Argent gagné** : +30/+75/+150$ par mission (standard/express/chain)
- **Distance parcourue** : Tracée en pixels (30px ≈ 1m réel)
- **Temps jeu** : Visible en session
- **Sauvegarde** : Auto-save en solo, sync serveur en multijoueur

## 🐛 Débogage

### Afficher collision boxes
Appuyez sur **C** pendant le jeu pour activer le debug collision display.

### Logs
Vérifiez la console pour les traces réseau, chargement assets, erreurs.

### Réinitialiser sauvegarde
Supprimez `solo_save.json` pour recommencer en solo.

## 📝 Licence

Projet étudiant - EPITA 2026

## 🔗 Ressources

- **PyScroll** : https://github.com/bitcraft/pyscroll
- **PyTMX** : https://github.com/bitcraft/pytmx
- **Pygame** : https://pygame.org