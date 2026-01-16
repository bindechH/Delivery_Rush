"""
Fichier principal du jeu Delivery Rush - Côté client
Gère la boucle principale du jeu, les états (menu/jeu), et l'initialisation des composants.
"""

import json
from pathlib import Path
import pygame
import sys
from modules import (
    MainMenu, Player, GameMap, GameUI, NetworkClient, SoundManager
)

CONFIG_PATH = Path('player_config.json')


def load_player_config():
    """
    Charge la configuration du joueur depuis player_config.json
    Crée le fichier avec des valeurs par défaut s'il n'existe pas
    """
    defaults = {
        "username": "player1",
        "server_ip": "127.0.0.1",
        "server_port": 12345,
        "car_model": "SUV",
        "car_color": "Black",
    }
    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(json.dumps(defaults, indent=2))
        return defaults
    try:
        data = json.loads(CONFIG_PATH.read_text())
        return {**defaults, **data}
    except Exception:
        return defaults


# Configuration chargée depuis le fichier
_cfg = load_player_config()
SERVER_IP = _cfg["server_ip"]
SERVER_PORT = _cfg["server_port"]
USERNAME = _cfg["username"]
CAR = (_cfg["car_model"], _cfg["car_color"])

# États du jeu - constantes pour les modes d'affichage
MENU = 0  # Écran du menu principal
GAME = 1  # Écran de jeu actif

# Constantes d'écran et performance
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
FPS = 60  # Images par seconde cibles
MENU_MUSIC = "assets/sounds/ambiance.mp3"  # Musique du menu



def _init_networking():
    """
    Initialise la connexion réseau au serveur pour le mode multijoueur
    Retourne le client réseau et la raison en cas d'échec
    """
    print(f"Connexion à {SERVER_IP}:{SERVER_PORT} en tant que {USERNAME}")
    client = NetworkClient(SERVER_IP, SERVER_PORT)
    ok, reason = client.connect(USERNAME, CAR)
    if not ok:
        print(f"Échec de la connexion : {reason}")
        return None, reason
    print("Connexion au serveur réalisée, mode multijoueur activé")
    return client, 'ok'


def _send_player_position(network_client, player, username):
    """Envoie la position et l'état du joueur au serveur"""
    network_client.send_state(player)


def _receive_player_positions(network_client, other_players_dict, username):
    """
    Reçoit et met à jour les positions des autres joueurs depuis le serveur
    Retourne True si succès, False sinon
    """
    success, positions = network_client.receive_states()
    if success is False:
        return False
    if success is True:
        other_players_dict.clear()
        other_players_dict.update(positions)
    return True


def main():
    """
    Fonction principale du jeu - Boucle de jeu principale
    Gère l'initialisation, les états du jeu (menu/jeu), et la logique réseau
    """

    # Initialisation de Pygame et de la fenêtre
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Delivery Rush")
    clock = pygame.time.Clock()

    # Chargement des polices
    font = pygame.font.SysFont(None, 48)  # Police système pour le titre
    small_font = pygame.font.Font("assets/fonts/ari-w9500-bold.ttf", 28)  # Police pour le menu
    name_font = pygame.font.Font("assets/fonts/ari-w9500-bold.ttf", 24)   # Police pour les noms
    for fnt in (font, small_font, name_font):
        fnt.set_bold(True)  # Toutes les polices en gras

    # Initialisation du gestionnaire de sons et musique du menu
    sound_manager = SoundManager()
    sound_manager.play_music(MENU_MUSIC, volume=0.1)  # Volume réduit pour le menu

    # Initialisation des composants principaux du jeu
    menu = MainMenu(screen, font, small_font, SCREEN_WIDTH, SCREEN_HEIGHT, SERVER_IP, USERNAME, CAR, sound_manager)
    game_map = GameMap(
        "assets/map/maps/deliveryrush_map.tmx",  # Fichier de carte Tiled
        (SCREEN_WIDTH, SCREEN_HEIGHT)  # Dimensions de l'écran pour le rendu
    )

    game_ui = None  # Interface de jeu (initialisée seulement en mode jeu)

    # Variables d'état du jeu
    state = MENU  # État actuel (MENU ou GAME)
    multiplayer = False  # Mode multijoueur activé/désactivé
    running = True  # Boucle principale active

    # Variables de réseau pour le multijoueur
    network_client = None  # Client réseau (None si pas connecté)
    other_players = {}  # Dictionnaire des autres joueurs {username: {x, y, angle, car}}
    connection_errors = 0  # Compteur d'erreurs de connexion consécutives
    MAX_CONNECTION_ERRORS = 3  # Nombre max d'erreurs avant déconnexion automatique

    # === BOUCLE PRINCIPALE DU JEU ===
    while running:
        dt = clock.tick(FPS) / 1000.0  # Delta time en secondes (pour animations fluides)
        events = pygame.event.get()  # Récupération des événements Pygame

        # Gestion des événements globaux (quitter le jeu)
        for event in events:
            if event.type == pygame.QUIT:
                running = False

        # === ÉTAT MENU ===
        if state == MENU:
            # Affichage du menu et récupération des rectangles de boutons
            solo_rect, multi_rect, quit_rect, vol_rect = menu.display_menu()

            # Gestion des clics sur les boutons du menu
            for event in events:
                new_state, new_multiplayer = menu.handle_menu_input(event, solo_rect, multi_rect, quit_rect, vol_rect)
                if new_state == 'QUIT':
                    running = False
                    if network_client:
                        network_client.send_disconnect('menu_quit')  # Informer le serveur
                        network_client.close()
                        network_client = None
                    sound_manager.stop_music()
                    break
                if new_state is not None:
                    if new_multiplayer is not None:
                        multiplayer = new_multiplayer
                        if multiplayer:
                            if network_client is None:
                                network_client, reason = _init_networking()
                            if network_client:
                                state = new_state
                            else:
                                menu.show_error = True
                                menu.error_message = f"Connect failed: {reason}"
                                multiplayer = False
                                network_client = None
                        else:
                            state = new_state
                        print("Jeu solo en cours")
                    else:
                        state = new_state
                        print("Jeu solo en cours")
        # === ÉTAT JEU ===
        elif state == GAME:
            # Initialisation de l'interface de jeu si nécessaire
            if game_ui is None:
                print(f"Entrée en mode jeu, multijoueur={multiplayer}")
                sound_manager.stop_music()  # Arrêter la musique du menu
                # Dimensions du monde de jeu (basées sur la carte)
                player_world = (getattr(game_map, 'width_px', 12000), getattr(game_map, 'height_px', 12000))
                # Création de l'interface de jeu avec tous les composants
                game_ui = GameUI(screen, font, small_font, Player(CAR, player_world), game_map, other_players, SCREEN_WIDTH, SCREEN_HEIGHT, USERNAME, name_font)

            if game_ui:
                game_ui.handle_events(events)  # Gestion des événements de jeu
                # Vérifier la touche ESC pour revenir au menu
                for event in events:
                    if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                        print("ESC pressé, retour au menu")
                        state = MENU
                        game_ui = None
                        multiplayer = False
                        other_players.clear()
                        if network_client:
                            network_client.send_disconnect('esc_menu')
                            network_client.close()
                            network_client = None
                        sound_manager.play_music(MENU_MUSIC, volume=0.5)
                        break
                
                if state == GAME:  # Mettre à jour uniquement si toujours en jeu
                    # Construction des rectangles de collision pour les autres joueurs
                    other_rects = []
                    hitbox_scale = getattr(game_ui.player, 'hitbox_scale', 1.0)
                    hit_size = max(2, int(game_ui.player.size * hitbox_scale))
                    hit_offset = (game_ui.player.size - hit_size) / 2
                    for player_data in other_players.values():
                        if isinstance(player_data, dict):
                            ox, oy = player_data.get('x', 0), player_data.get('y', 0)
                        else:
                            ox, oy = player_data
                        other_rects.append(pygame.Rect(int(ox + hit_offset), int(oy + hit_offset), hit_size, hit_size))

                    # Mise à jour de l'état du jeu (mouvement, collisions, etc.)
                    game_ui.update(pygame.key.get_pressed(), dt, other_rects)

                    # Gestion du réseau en mode multijoueur
                    if multiplayer and network_client:
                        _send_player_position(network_client, game_ui.player, USERNAME)  # Envoi position
                        if _receive_player_positions(network_client, other_players, USERNAME):  # Réception positions
                            connection_errors = 0  # Réinitialiser le compteur d'erreurs
                        else:
                            connection_errors += 1  # Incrémenter les erreurs
                            if connection_errors >= MAX_CONNECTION_ERRORS:
                                # Trop d'erreurs consécutives - déconnexion automatique
                                print("Trop d'erreurs de réception, retour au menu")
                                state = MENU
                                game_ui = None
                                multiplayer = False
                                other_players.clear()
                                if network_client:
                                    network_client.send_disconnect('net_error')
                                    network_client.close()
                                    network_client = None
                                menu.show_error = True
                                menu.error_message = "Déconnecté du serveur !"
                                sound_manager.play_music(MENU_MUSIC, volume=1)
                    if game_ui:
                        game_ui.render()  # Rendu graphique du jeu

        pygame.display.flip()  # Mise à jour de l'écran

    # === NETTOYAGE FINAL ===
    if network_client:
        network_client.send_disconnect('shutdown')  # Informer le serveur de l'arrêt
        network_client.close()  # Fermer proprement la connexion
    pygame.quit()  # Quitter Pygame
    sys.exit()  # Terminer le programme

# Point d'entrée du programme
if __name__ == "__main__":
    main()

