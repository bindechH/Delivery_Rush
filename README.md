# Delivery Rush

Un jeu de livraison multijoueur construit avec Python et Pygame.

## Structure du Projet

- `main.py` : Application cliente principale
- `server.py` : Serveur UDP pour le multijoueur
- `player_config.json` : Configuration du joueur
- `modules/` : Modules du jeu
  - `player.py` : Classe joueur et gestion réseau
  - `map.py` : Rendu de la carte du jeu
  - `missions.py` : Système de missions (espace réservé)
  - `network.py` : Gestion réseau
  - `rendering.py` : Rendu et interface utilisateur
  - `sounds.py` : Gestionnaire de sons (espace réservé)
- `assets/` : Ressources du jeu (images, sons)

## Démarrage

1. Installez les dépendances : `pip install -r requirements.txt`
2. Lancez le serveur : `python server.py`
3. Lancez le client : `python main.py`

## Fonctionnalités

- Gameplay de livraison vue du dessus
- Support multijoueur (UDP)
- Génération dynamique de missions (planifié)
- Améliorations de véhicules (planifié)
- IA ennemie (planifié)