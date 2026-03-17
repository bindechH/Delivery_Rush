"""
Fichier principal du jeu Delivery Rush - Côté client
Gère la boucle principale du jeu, les états (menu/jeu), et l'initialisation des composants.
"""

import json
from pathlib import Path
import pygame
import sys
from modules import (
    MainMenu, Player, GameMap, GameUI, NetworkClient, SoundManager, MissionSystem, PhoneUI
)

CONFIG_PATH = Path('config.json')
SOLO_SAVE_PATH = Path('solo_save.json')

# ── Config (settings only) ──────────────────────────

_CONFIG_DEFAULTS = {
    "resolution": [1920, 1080],
    "fullscreen": False,
    "fps": 60,
    "map_zoom": 2.0,
    "server_ip": "127.0.0.1",
    "server_port": 12345,
    "multi": {
        "username": "",
        "password": "",
    },
}

# ── Solo save (game state) ──────────────────────────

_SOLO_DEFAULTS = {
    "username": "player1",
    "car_model": "MICRO",
    "car_color": "White",
    "money": 0,
    "owned_cars": [{"model": "MICRO", "color": "White"}],
    "completed_missions": 0,
    "failed_missions": 0,
    "total_distance": 0.0,
    "x": 6000.0,
    "y": 6000.0,
    "angle": 0.0,
}


def _load_json(path, defaults):
    if not path.exists():
        path.write_text(json.dumps(defaults, indent=2))
        return dict(defaults)
    try:
        data = json.loads(path.read_text())
        for key in defaults:
            if key not in data:
                data[key] = defaults[key]
            elif isinstance(defaults[key], dict) and isinstance(data.get(key), dict):
                for subkey in defaults[key]:
                    if subkey not in data[key]:
                        data[key][subkey] = defaults[key][subkey]
        return data
    except Exception:
        return dict(defaults)


def _save_json(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def _migrate_old_config():
    """Migrate legacy player_config.json → config.json + solo_save.json."""
    old = Path('player_config.json')
    if not old.exists():
        return
    try:
        legacy = json.loads(old.read_text())
    except Exception:
        return
    # Build config.json
    cfg = dict(_CONFIG_DEFAULTS)
    for k in ("resolution", "fullscreen", "fps", "server_ip", "server_port"):
        if k in legacy:
            cfg[k] = legacy[k]
    if "multi" in legacy:
        cfg["multi"] = legacy["multi"]
    _save_json(CONFIG_PATH, cfg)
    # Build solo_save.json
    solo = dict(_SOLO_DEFAULTS)
    if "solo" in legacy:
        for k in _SOLO_DEFAULTS:
            if k in legacy["solo"]:
                solo[k] = legacy["solo"][k]
    _save_json(SOLO_SAVE_PATH, solo)
    old.rename('player_config_old.json')


# Run migration if needed, then load
_migrate_old_config()
_cfg = _load_json(CONFIG_PATH, _CONFIG_DEFAULTS)
_solo = _load_json(SOLO_SAVE_PATH, _SOLO_DEFAULTS)

SERVER_IP = _cfg["server_ip"]
SERVER_PORT = _cfg["server_port"]
USERNAME = _solo["username"]
CAR = (_solo["car_model"], _solo["car_color"])

# États du jeu - constantes pour les modes d'affichage
MENU = 0  # Écran du menu principal
GAME = 1  # Écran de jeu actif

# Écran et performance
SCREEN_WIDTH = _cfg["resolution"][0]
SCREEN_HEIGHT = _cfg["resolution"][1]
FULLSCREEN = _cfg.get("fullscreen", False)
FPS = _cfg.get("fps", 60)
MAP_ZOOM = _cfg.get("map_zoom", 2.0)
MENU_MUSIC = "assets/sounds/ambiance.mp3"



def _init_networking(auth_username=None, auth_password=None, ip=None, port=None):
    """
    Initialise la connexion réseau au serveur pour le mode multijoueur.
    Utilise les identifiants fournis par l'écran d'authentification.
    """
    host = ip or SERVER_IP
    srv_port = port or SERVER_PORT
    user = auth_username or _cfg.get("multi", {}).get("username", "") or USERNAME
    password = auth_password or _cfg.get("multi", {}).get("password", "") or None
    print(f"Connexion à {host}:{srv_port} en tant que {user}")
    client = NetworkClient(host, srv_port)
    ok, reason = client.connect(user, CAR, password=password)
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
    # Local copies of mutable config values (may be updated by settings screen)
    server_ip = SERVER_IP
    server_port = SERVER_PORT
    fps = FPS
    flags = pygame.FULLSCREEN if FULLSCREEN else pygame.RESIZABLE
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), flags)
    pygame.display.set_caption("Delivery Rush")
    clock = pygame.time.Clock()
    current_w, current_h = SCREEN_WIDTH, SCREEN_HEIGHT
    is_fullscreen = FULLSCREEN

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
    map_zoom = _cfg.get("map_zoom", 2.0)
    menu = MainMenu(screen, font, small_font, current_w, current_h, server_ip, USERNAME, CAR, sound_manager, fullscreen=is_fullscreen, map_zoom=map_zoom)
    game_map = GameMap(
        "assets/map/maps/deliveryrush_map.tmx",
        (current_w, current_h),
        zoom=map_zoom
    )

    game_ui = None  # Interface de jeu (initialisée seulement en mode jeu)
    mission_system = None  # Système de missions
    phone_ui = None  # Interface téléphone

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
        dt = clock.tick(fps) / 1000.0  # Delta time en secondes (pour animations fluides)
        events = pygame.event.get()  # Récupération des événements Pygame

        # Gestion des événements globaux (quitter le jeu, fullscreen)
        for event in events:
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_F11:
                is_fullscreen = not is_fullscreen
                if is_fullscreen:
                    screen = pygame.display.set_mode((current_w, current_h), pygame.FULLSCREEN)
                else:
                    screen = pygame.display.set_mode((current_w, current_h), pygame.RESIZABLE)
            elif event.type == pygame.VIDEORESIZE and not is_fullscreen:
                current_w, current_h = event.w, event.h
                screen = pygame.display.set_mode((current_w, current_h), pygame.RESIZABLE)
                menu.resize(current_w, current_h)

        # === ÉTAT MENU ===
        if state == MENU:
            # Affichage du menu et récupération des rectangles de boutons
            solo_rect, multi_rect, quit_rect, settings_rect = menu.display_menu(dt)

            # Gestion des clics sur les boutons du menu
            for event in events:
                new_state, new_multiplayer = menu.handle_menu_input(event, solo_rect, multi_rect, quit_rect, settings_rect)
                if new_state == 'QUIT':
                    running = False
                    if network_client:
                        network_client.send_disconnect('menu_quit')
                        network_client.close()
                        network_client = None
                    sound_manager.stop_music()
                    break
                if new_state == 'APPLY_SETTINGS':
                    # Appliquer les réglages depuis le menu settings
                    sd = menu.get_settings_dict()
                    server_ip = sd.get("server_ip", server_ip)
                    server_port = sd.get("server_port", server_port)
                    fps = sd.get("fps", fps)
                    new_res = sd.get("resolution", (current_w, current_h))
                    new_fs = sd.get("fullscreen", is_fullscreen)
                    # Persist to config
                    _cfg["server_ip"] = server_ip
                    _cfg["server_port"] = server_port
                    _cfg["fps"] = fps
                    new_zoom = sd.get("map_zoom", map_zoom)
                    _cfg["map_zoom"] = new_zoom
                    _cfg["resolution"] = list(new_res)
                    _cfg["fullscreen"] = new_fs
                    _save_json(CONFIG_PATH, _cfg)
                    # Apply map zoom
                    if new_zoom != map_zoom:
                        map_zoom = new_zoom
                        game_map.set_zoom(map_zoom)
                    # Apply resolution/fullscreen changes
                    if new_fs != is_fullscreen or (new_res[0] != current_w or new_res[1] != current_h):
                        current_w, current_h = new_res
                        is_fullscreen = new_fs
                        flags = pygame.FULLSCREEN if is_fullscreen else pygame.RESIZABLE
                        screen = pygame.display.set_mode((current_w, current_h), flags)
                        menu.resize(current_w, current_h)
                    continue
                if new_state == 'AUTH_CONNECT':
                    multiplayer = True
                    auth_user = getattr(menu, 'auth_username', '')
                    auth_pass = getattr(menu, 'auth_password', '')
                    # Save multi credentials to config (not solo save)
                    _cfg["multi"]["username"] = auth_user
                    _cfg["multi"]["password"] = auth_pass
                    _save_json(CONFIG_PATH, _cfg)
                    network_client, reason = _init_networking(auth_user, auth_pass, server_ip, server_port)
                    if network_client:
                        state = GAME
                    else:
                        menu.auth_open = True
                        menu.auth_error = f"Échec : {reason}"
                        multiplayer = False
                        network_client = None
                    continue
                if new_state is not None:
                    if new_multiplayer is not None:
                        multiplayer = new_multiplayer
                        if not multiplayer:
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
                sound_manager.stop_music()
                player_world = (getattr(game_map, 'width_px', 12000), getattr(game_map, 'height_px', 12000))

                if multiplayer and network_client and network_client.server_player_data:
                    # ── MULTI: use server data ──
                    spd = network_client.server_player_data
                    multi_car = (spd.get('car_model', 'MICRO'), spd.get('car_color', 'White'))
                    mission_system = MissionSystem(
                        money=spd.get('money', 0),
                        owned_cars=spd.get('owned_cars', [{"model": "MICRO", "color": "White"}]),
                        completed_count=spd.get('completed_missions', 0),
                        failed_count=spd.get('failed_missions', 0),
                    )
                    phone_ui = PhoneUI(current_w, current_h, mission_system)
                    player_obj = Player(multi_car, player_world)
                    player_obj.x = spd.get('last_x', 6000.0)
                    player_obj.y = spd.get('last_y', 6000.0)
                    player_obj.angle = spd.get('last_angle', 0.0)
                    player_obj.distance_traveled = spd.get('total_distance', 0.0)
                    mp_username = getattr(menu, 'auth_username', '') or _cfg.get("multi", {}).get("username", USERNAME)
                    game_ui = GameUI(screen, font, small_font, player_obj, game_map, other_players, current_w, current_h, mp_username, name_font, mission_system=mission_system, phone_ui=phone_ui)
                else:
                    # ── SOLO: use local solo_save ──
                    solo = _solo
                    mission_system = MissionSystem(
                        money=solo.get("money", 0),
                        owned_cars=solo.get("owned_cars", [{"model": "MICRO", "color": "White"}]),
                        completed_count=solo.get("completed_missions", 0),
                        failed_count=solo.get("failed_missions", 0),
                    )
                    phone_ui = PhoneUI(current_w, current_h, mission_system)
                    solo_car = (solo.get("car_model", "MICRO"), solo.get("car_color", "White"))
                    player_obj = Player(solo_car, player_world)
                    player_obj.x = solo.get("x", 6000.0)
                    player_obj.y = solo.get("y", 6000.0)
                    player_obj.angle = solo.get("angle", 0.0)
                    player_obj.distance_traveled = solo.get("total_distance", 0.0)
                    game_ui = GameUI(screen, font, small_font, player_obj, game_map, other_players, current_w, current_h, USERNAME, name_font, mission_system=mission_system, phone_ui=phone_ui)

            if game_ui:
                game_ui.handle_events(events)  # Gestion des événements de jeu
                # Vérifier la touche ESC pour revenir au menu
                for event in events:
                    if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                        if phone_ui and phone_ui.visible:
                            pass  # Phone handles ESC internally
                        else:
                            print("ESC pressé, retour au menu")
                            if mission_system and game_ui:
                                if multiplayer and network_client:
                                    # ── MULTI: save progress to server ──
                                    progress = {
                                        'money': mission_system.money,
                                        'owned_cars': mission_system.owned_cars,
                                        'car_model': game_ui.player.car[0],
                                        'car_color': game_ui.player.car[1],
                                        'completed_missions': mission_system.completed_count,
                                        'failed_missions': mission_system.failed_count,
                                    }
                                    network_client.send_save_progress(progress)
                                else:
                                    # ── SOLO: save to solo_save.json ──
                                    _solo["money"] = mission_system.money
                                    _solo["owned_cars"] = mission_system.owned_cars
                                    _solo["completed_missions"] = mission_system.completed_count
                                    _solo["failed_missions"] = mission_system.failed_count
                                    if game_ui.player:
                                        _solo["car_model"] = game_ui.player.car[0]
                                        _solo["car_color"] = game_ui.player.car[1]
                                        _solo["total_distance"] = game_ui.player.distance_traveled
                                        _solo["x"] = game_ui.player.x
                                        _solo["y"] = game_ui.player.y
                                        _solo["angle"] = game_ui.player.angle
                                    _save_json(SOLO_SAVE_PATH, _solo)
                            state = MENU
                            game_ui = None
                            mission_system = None
                            phone_ui = None
                            multiplayer = False
                            other_players.clear()
                            if network_client:
                                network_client.send_disconnect('esc_menu')
                                network_client.close()
                                network_client = None
                            sound_manager.play_music(MENU_MUSIC, volume=0.5)
                            break
                    elif event.type == pygame.KEYDOWN and event.key == pygame.K_UP:
                        if phone_ui and not phone_ui.visible:
                            phone_ui.toggle()  # Only open, not close
                    elif event.type == pygame.KEYDOWN and event.key == pygame.K_c:
                        game_map.show_collisions = not game_map.show_collisions

                # Gérer les événements du téléphone
                if phone_ui and phone_ui.visible:
                    phone_ui.handle_events(events)
                
                if state == GAME:  # Mettre à jour uniquement si toujours en jeu
                    # Mise à jour animation téléphone
                    if phone_ui:
                        phone_ui.update(dt)
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

                    # Mise à jour du système de missions
                    if mission_system and game_ui:
                        player_cx = game_ui.player.x + game_ui.player.size / 2
                        player_cy = game_ui.player.y + game_ui.player.size / 2
                        mission_system.update(player_cx, player_cy, dt)

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
                                mission_system = None
                                phone_ui = None
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
                        # Rendu du téléphone par-dessus (peek strip + slide-up)
                        if phone_ui:
                            phone_ui.render(screen, player=game_ui.player, game_map=game_map)

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

