"""
Initialisation du package modules pour Delivery Rush
Exporte toutes les classes et fonctions principales du jeu pour un accès facile.
"""

# === IMPORTS DES MODULES PRINCIPAUX ===
from .map import GameMap              # Gestionnaire de carte Tiled
from .missions import MissionSystem    # Système de missions de livraison
from .phone import PhoneUI             # Interface téléphone in-game
from .player import Player, VEHICLE_CATALOG, VEHICLE_COLORS  # Classe joueur + catalogue véhicules
from .rendering import MainMenu, GameUI, draw_text  # Interfaces utilisateur et rendu
from .sounds import SoundManager       # Gestionnaire de sons et musique
from .network import NetworkClient, InterpolatedPlayer  # Client réseau pour le multijoueur