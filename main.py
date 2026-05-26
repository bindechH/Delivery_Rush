"""
Fichier principal du jeu Delivery Rush - Côté client
Gère la boucle principale du jeu, les états (menu/jeu), et l'initialisation des composants.
"""

import json
from pathlib import Path
import pygame
import sys
from modules.translate import normalize_language, tr
from modules.player import sanitize_car
from modules import (
    MainMenu, Player, GameMap, GameUI, NetworkClient, SoundManager, MissionSystem, PhoneUI, AIManager
)

CONFIG_PATH = Path('config.json')
SOLO_SAVE_PATH = Path('solo_save.json')
DEFAULT_SPAWN_X = 2699.0
DEFAULT_SPAWN_Y = 1341.0

# ── Config (settings only) ──────────────────────────

_CONFIG_DEFAULTS = {
    "resolution": [1280, 720],
    "fullscreen": False,
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
        "password": "",    },
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
    "reputation": 0,
    "unlock_state": {
        "tier": "rookie",
        "unlocked_types": ["standard"],
        "reputation": 0,
    },
    "mission_stats": {
        "current_streak": 0,
        "best_streak": 0,
        "bonus_earned": 0,
        "penalty_taken": 0,
    },
    "total_distance": 0.0,
    "last_vehicle_class": "compact",
    "audio_settings": {
        "music_state": "menu",
    },
    "x": DEFAULT_SPAWN_X,
    "y": DEFAULT_SPAWN_Y,
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
    if "volume" in legacy:
        cfg["volume"] = legacy["volume"]
        cfg["music_volume"] = legacy["volume"]
        cfg["effects_volume"] = legacy["volume"]
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

if "music_volume" not in _cfg:
    _cfg["music_volume"] = float(_cfg.get("volume", 0.25))
if "effects_volume" not in _cfg:
    _cfg["effects_volume"] = 0.75
if "language" not in _cfg:
    _cfg["language"] = "fr"
_cfg["language"] = normalize_language(_cfg.get("language", "fr"))
if "robber_difficulty" not in _cfg:
    _cfg["robber_difficulty"] = 4

SERVER_IP = _cfg["server_ip"]
SERVER_PORT = _cfg["server_port"]
USERNAME = _solo["username"]
CAR = sanitize_car((_solo["car_model"], _solo["car_color"]))

# États du jeu - constantes pour les modes d'affichage
MENU = 0  # Écran du menu principal
GAME = 1  # Écran de jeu actif

# Écran et performance
SCREEN_WIDTH = _cfg["resolution"][0]
SCREEN_HEIGHT = _cfg["resolution"][1]
FULLSCREEN = _cfg.get("fullscreen", False)
FPS = _cfg.get("fps", 60)
MAP_ZOOM = _cfg.get("map_zoom", 2.0)
ROBBER_DANGER_RADIUS = 320.0


def _clamp_int(value, lo, hi, fallback):
    try:
        parsed = int(value)
    except Exception:
        parsed = int(fallback)
    return max(int(lo), min(int(hi), parsed))


def _robbery_fill_rate_per_second(difficulty_rank):
    rank = _clamp_int(difficulty_rank, 1, 10, 4)
    fill_seconds = max(2.6, 8.5 - (rank - 1) * 0.58)
    return 1.0 / fill_seconds


def _pick_existing_track(*candidates):
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    return ""


MENU_MUSIC = _pick_existing_track(
    "assets/music/menu_music.mp3",
    "assets/sounds/menu_music.mp3",
    "assets/sounds/ambiance.mp3",
)
MISSION_MUSIC = _pick_existing_track(
    "assets/music/mission_music.mp3",
    "assets/sounds/mission_music.mp3",
    "assets/sounds/ambiance.mp3",
)
CITY_AMBIENCE = _pick_existing_track(
    "assets/music/city_ambiant.mp3",
    "assets/sounds/city_ambience.mp3",
    "assets/sounds/city_ambience.ogg",
    "assets/sounds/city_ambience.wav",
    "assets/sounds/ambiance.mp3",
)



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
    Reçoit et met à jour les positions des autres joueurs depuis le serveur.
    Utilise l'interpolation pour lisser les positions entre les ticks serveur.
    Retourne True si succès, False sinon.
    """
    success, positions = network_client.receive_states()
    if success is False:
        return False
    # Toujours mettre à jour avec les positions interpolées (lissage entre ticks serveur)
    interpolated = network_client.get_interpolated_players()
    other_players_dict.clear()
    other_players_dict.update(interpolated)
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
    language = normalize_language(_cfg.get("language", "fr"))
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
    sound_manager.set_music_volume(_cfg.get("music_volume", _cfg.get("volume", 0.25)))
    if hasattr(sound_manager, "set_effects_volume"):
        sound_manager.set_effects_volume(_cfg.get("effects_volume", 0.75))
    sound_manager.set_music_state("menu")
    if MENU_MUSIC:
        sound_manager.play_music(MENU_MUSIC, volume=1.0)
    else:
        sound_manager.stop_music()

    # Initialisation des composants principaux du jeu
    map_zoom = _cfg.get("map_zoom", 2.0)
    menu = MainMenu(
        screen,
        font,
        small_font,
        current_w,
        current_h,
        server_ip,
        USERNAME,
        CAR,
        sound_manager,
        fullscreen=is_fullscreen,
        map_zoom=map_zoom,
        music_volume=_cfg.get("music_volume", _cfg.get("volume", 0.25)),
        effects_volume=_cfg.get("effects_volume", 0.75),
        language=language,
    )
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
    other_players = {}  # Vue fusionnée pour rendu/collisions (joueurs distants + IA)
    remote_players = {}  # Joueurs distants uniquement (réseau)
    ai_manager = None  # IA locale (solo)
    ai_tick_rate = 6.0
    ai_tick_interval = 1.0 / ai_tick_rate
    ai_tick_accumulator = 0.0
    ai_world_cache = {}
    game_music_track = MENU_MUSIC
    connection_errors = 0  # Compteur d'erreurs de connexion consécutives
    MAX_CONNECTION_ERRORS = 3  # Nombre max d'erreurs avant déconnexion automatique
    drift_sound_active = False
    handbrake_sound_latch = False
    last_collision_count = 0
    collision_sound_cooldown = 0.0
    robber_difficulty = _clamp_int(_cfg.get("robber_difficulty", 4), 1, 10, 4)
    robbery_fill_rate = _robbery_fill_rate_per_second(robber_difficulty)
    robber_target_count = robber_difficulty
    robbery_pressure = 0.0
    robbery_close_count = 0

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
                    language = normalize_language(sd.get("language", language))
                    _cfg["language"] = language
                    menu.language = language
                    new_music_vol = float(sd.get("music_volume", _cfg.get("music_volume", 0.25)))
                    new_effects_vol = float(sd.get("effects_volume", _cfg.get("effects_volume", 0.75)))
                    _cfg["music_volume"] = new_music_vol
                    _cfg["effects_volume"] = new_effects_vol
                    _cfg["volume"] = new_music_vol
                    sound_manager.set_music_volume(new_music_vol)
                    if hasattr(sound_manager, "set_effects_volume"):
                        sound_manager.set_effects_volume(new_effects_vol)
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
                        menu.auth_error = tr(language, "menu.net_error", reason=reason)
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
                if not multiplayer:
                    # simple loading screen: gray background (80, 80, 80), dark gray text (40, 40, 40)
                    loading_bg = (80, 80, 80)
                    loading_text_color = (40, 40, 40)
                    font_to_use = getattr(menu, 'title_font', None) or pygame.font.Font("assets/fonts/ari-w9500-bold.ttf", 38)
                    for step in range(5):
                        pygame.event.pump()
                        for event in pygame.event.get():
                            if event.type == pygame.QUIT:
                                pygame.quit()
                                sys.exit()
                        screen.fill(loading_bg)
                        dots = "." * (step % 4)
                        label_text = tr(language, "menu.loading", default="loading").lower()
                        msg = f"{label_text}{dots}"
                        txt_surf = font_to_use.render(msg, True, loading_text_color)
                        text_rect = txt_surf.get_rect(center=(current_w // 2, current_h // 2))
                        screen.blit(txt_surf, text_rect)
                        pygame.display.flip()
                        pygame.time.wait(250)

                sound_manager.stop_music()
                if hasattr(sound_manager, 'set_music_state'):
                    sound_manager.set_music_state('gameplay')
                if hasattr(sound_manager, 'start_city_ambience'):
                    sound_manager.start_city_ambience(CITY_AMBIENCE, gain=0.6)
                game_music_track = None
                player_world = (getattr(game_map, 'width_px', 12000), getattr(game_map, 'height_px', 12000))
                other_players.clear()
                remote_players.clear()

                if multiplayer and network_client and network_client.server_player_data:
                    # ── MULTI: use server data ──
                    spd = network_client.server_player_data
                    multi_car = (spd.get('car_model', 'MICRO'), spd.get('car_color', 'White'))
                    player_obj = Player(multi_car, player_world)
                    player_obj.x = spd.get('last_x', DEFAULT_SPAWN_X)
                    player_obj.y = spd.get('last_y', DEFAULT_SPAWN_Y)
                    player_obj.angle = spd.get('last_angle', 0.0)
                    player_obj.distance_traveled = spd.get('total_distance', 0.0)

                    mission_system = MissionSystem(
                        money=spd.get('money', 0),
                        owned_cars=spd.get('owned_cars', [{"model": "MICRO", "color": "White"}]),
                        completed_count=spd.get('completed_missions', 0),
                        failed_count=spd.get('failed_missions', 0),
                        current_car=multi_car,
                        reputation=spd.get('reputation', 0),
                        unlock_state=spd.get('unlock_state', {}),
                        mission_stats=spd.get('mission_stats', {}),
                        language=language,
                    )
                    mission_system.refresh_available_missions_for_vehicle(player_obj.car)
                    if network_client.server_missions:
                        mission_system.load_server_missions(network_client.server_missions, equipped_car=player_obj.car)

                    def _mission_event_sender(event_type, payload, equipped_car):
                        if network_client:
                            network_client.send_mission_event(event_type, payload, equipped_car=equipped_car)

                    phone_ui = PhoneUI(
                        current_w,
                        current_h,
                        mission_system,
                        mission_event_sender=_mission_event_sender,
                        sound_event_sender=sound_manager.play_event,
                        language=language,
                        multiplayer=True,
                        network_client=network_client,
                    )
                    mp_username = getattr(menu, 'auth_username', '') or getattr(menu, 'username', '') or USERNAME
                    game_ui = GameUI(
                        screen,
                        font,
                        small_font,
                        player_obj,
                        game_map,
                        other_players,
                        current_w,
                        current_h,
                        mp_username,
                        name_font,
                        mission_system=mission_system,
                        phone_ui=phone_ui,
                        language=language,
                    )
                else:
                    # ── SOLO: use local solo_save ──
                    solo = _solo
                    solo_car = (solo.get("car_model", "MICRO"), solo.get("car_color", "White"))
                    player_obj = Player(solo_car, player_world)
                    player_obj.x = solo.get("x", DEFAULT_SPAWN_X)
                    player_obj.y = solo.get("y", DEFAULT_SPAWN_Y)
                    player_obj.angle = solo.get("angle", 0.0)
                    player_obj.distance_traveled = solo.get("total_distance", 0.0)

                    mission_system = MissionSystem(
                        money=solo.get("money", 0),
                        owned_cars=solo.get("owned_cars", [{"model": "MICRO", "color": "White"}]),
                        completed_count=solo.get("completed_missions", 0),
                        failed_count=solo.get("failed_missions", 0),
                        current_car=solo_car,
                        reputation=solo.get("reputation", 0),
                        unlock_state=solo.get("unlock_state", {}),
                        mission_stats=solo.get("mission_stats", {}),
                        language=language,
                    )
                    mission_system.refresh_available_missions_for_vehicle(player_obj.car)
                    phone_ui = PhoneUI(
                        current_w,
                        current_h,
                        mission_system,
                        sound_event_sender=sound_manager.play_event,
                        language=language,
                        multiplayer=False,
                        network_client=None,
                    )
                    solo_username = getattr(menu, 'username', USERNAME) or USERNAME
                    if solo_username != _solo.get("username"):
                        _solo["username"] = solo_username
                        _save_json(SOLO_SAVE_PATH, _solo)
                    game_ui = GameUI(
                        screen,
                        font,
                        small_font,
                        player_obj,
                        game_map,
                        other_players,
                        current_w,
                        current_h,
                        solo_username,
                        name_font,
                        mission_system=mission_system,
                        phone_ui=phone_ui,
                        language=language,
                    )

                # IA locale: trafic en solo, braqueurs en solo/multi.
                ai_manager = AIManager()
                ai_tick_accumulator = 0.0
                ai_world_cache = {}
                drift_sound_active = False
                handbrake_sound_latch = False
                last_collision_count = int(getattr(player_obj, 'collision_count', 0) or 0)
                collision_sound_cooldown = 0.0
                robber_target_count = robber_difficulty * (2 if multiplayer else 1)
                robbery_pressure = 0.0
                robbery_close_count = 0
                if not multiplayer:
                    ai_manager.configure_performance(
                        active_update_radius=880.0,
                        obstacle_neighbor_radius=240.0,
                        use_dynamic_obstacles=True,
                    )
                    ai_manager.configure_dynamic_traffic(
                        enabled=True,
                        target_count=44,
                        spawn_min_distance=260.0,
                        spawn_radius=1850.0,
                        despawn_radius=3100.0,
                        center_bias=0.48,
                        rebalance_interval=0.16,
                        spawn_batch=3,
                        edge_despawn_margin=36.0,
                    )
                    player_center = (
                        player_obj.x + player_obj.size * 0.5,
                        player_obj.y + player_obj.size * 0.5,
                    )
                    ai_manager.spawn_traffic(game_map, count=16, focus_points=[player_center])
                else:
                    ai_manager.configure_performance(
                        active_update_radius=1200.0,
                        obstacle_neighbor_radius=0.0,
                        use_dynamic_obstacles=False,
                    )
                    ai_manager.configure_dynamic_traffic(
                        enabled=False,
                        target_count=0,
                        spawn_batch=1,
                        rebalance_interval=1.0,
                    )

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
                                    vehicle_profile = game_ui.player.get_vehicle_profile() if hasattr(game_ui.player, 'get_vehicle_profile') else {}
                                    progress = {
                                        'money': mission_system.money,
                                        'owned_cars': mission_system.owned_cars,
                                        'car_model': game_ui.player.car[0],
                                        'car_color': game_ui.player.car[1],
                                        'completed_missions': mission_system.completed_count,
                                        'failed_missions': mission_system.failed_count,
                                        'total_distance': game_ui.player.distance_traveled,
                                        'reputation': getattr(mission_system, 'reputation', 0),
                                        'unlock_state': mission_system.get_unlock_state() if hasattr(mission_system, 'get_unlock_state') else {},
                                        'mission_stats': dict(getattr(mission_system, 'mission_stats', {})),
                                        'last_vehicle_class': vehicle_profile.get('vehicle_class', 'compact'),
                                        'audio_settings': {
                                            'music_state': getattr(sound_manager, 'current_music_state', 'menu'),
                                            'music_volume': _cfg.get('music_volume', 0.25),
                                            'effects_volume': _cfg.get('effects_volume', 0.75),
                                        },
                                    }
                                    network_client.send_save_progress(progress)
                                else:
                                    # ── SOLO: save to solo_save.json ──
                                    _solo["money"] = mission_system.money
                                    _solo["owned_cars"] = mission_system.owned_cars
                                    _solo["completed_missions"] = mission_system.completed_count
                                    _solo["failed_missions"] = mission_system.failed_count
                                    _solo["reputation"] = getattr(mission_system, "reputation", 0)
                                    _solo["unlock_state"] = mission_system.get_unlock_state() if hasattr(mission_system, "get_unlock_state") else {}
                                    _solo["mission_stats"] = dict(getattr(mission_system, "mission_stats", {}))
                                    _solo["audio_settings"] = {
                                        "music_state": getattr(sound_manager, "current_music_state", "menu"),
                                        "music_volume": _cfg.get("music_volume", 0.25),
                                        "effects_volume": _cfg.get("effects_volume", 0.75),
                                    }
                                    if game_ui.player:
                                        _solo["car_model"] = game_ui.player.car[0]
                                        _solo["car_color"] = game_ui.player.car[1]
                                        _solo["total_distance"] = game_ui.player.distance_traveled
                                        _solo["x"] = game_ui.player.x
                                        _solo["y"] = game_ui.player.y
                                        _solo["angle"] = game_ui.player.angle
                                        profile = game_ui.player.get_vehicle_profile() if hasattr(game_ui.player, "get_vehicle_profile") else {}
                                        _solo["last_vehicle_class"] = profile.get("vehicle_class", "compact")
                                    _save_json(SOLO_SAVE_PATH, _solo)
                            state = MENU
                            menu.language = language
                            current_menu_car = game_ui.player.car if (game_ui and getattr(game_ui, 'player', None)) else (_solo.get('car_model', 'MICRO'), _solo.get('car_color', 'White'))
                            menu.refresh_vehicle(current_menu_car)
                            game_ui = None
                            mission_system = None
                            phone_ui = None
                            ai_manager = None
                            ai_tick_accumulator = 0.0
                            ai_world_cache = {}
                            robbery_pressure = 0.0
                            robbery_close_count = 0
                            multiplayer = False
                            other_players.clear()
                            remote_players.clear()
                            if network_client:
                                network_client.send_disconnect('esc_menu')
                                network_client.close()
                                network_client = None
                            if hasattr(sound_manager, 'stop_vehicle_engine'):
                                sound_manager.stop_vehicle_engine()
                            if hasattr(sound_manager, 'stop_city_ambience'):
                                sound_manager.stop_city_ambience()
                            if MENU_MUSIC:
                                sound_manager.play_music(MENU_MUSIC, volume=1.0)
                            else:
                                sound_manager.stop_music()
                            if hasattr(sound_manager, 'set_music_state'):
                                sound_manager.set_music_state('menu')
                            game_music_track = MENU_MUSIC
                            break
                    elif event.type == pygame.KEYDOWN and event.key == pygame.K_UP:
                        if phone_ui and not phone_ui.visible:
                            phone_ui.toggle()  # Only open, not close
                            if hasattr(sound_manager, 'play_event'):
                                sound_manager.play_event('ui_open')
                    elif event.type == pygame.KEYDOWN and event.key == pygame.K_c:
                        show_collisions = getattr(game_map, 'show_collisions', False)
                        show_ai_debug = getattr(game_map, 'show_ai_debug', False)
                        debug_on = bool(show_collisions or show_ai_debug)
                        game_map.show_collisions = not debug_on
                        game_map.show_ai_debug = not debug_on

                # Gérer les événements du téléphone
                if phone_ui and phone_ui.visible:
                    phone_ui.handle_events(events)
                
                if state == GAME:  # Mettre à jour uniquement si toujours en jeu
                    # Mise à jour animation téléphone
                    if phone_ui:
                        phone_ui.update(dt)

                    # Rectangles des joueurs distants (réseau) pour l'évitement IA
                    remote_rects = []
                    hitbox_scale = getattr(game_ui.player, 'hitbox_scale', 1.0)
                    hit_size = max(2, int(game_ui.player.size * hitbox_scale))
                    hit_offset = (game_ui.player.size - hit_size) / 2
                    for player_data in remote_players.values():
                        if isinstance(player_data, dict):
                            ox, oy = player_data.get('x', 0), player_data.get('y', 0)
                        else:
                            ox, oy = player_data
                        remote_rects.append(pygame.Rect(int(ox + hit_offset), int(oy + hit_offset), hit_size, hit_size))

                    # Mise à jour IA puis fusion dans la vue de rendu
                    ai_render_players = {}
                    risky_mission_active = bool(
                        mission_system
                        and mission_system.active_mission
                        and str(getattr(mission_system.active_mission, 'risk_level', 'chill')).lower() == 'risky'
                    )

                    if ai_manager and not multiplayer:
                        if risky_mission_active:
                            player_center = (
                                game_ui.player.x + game_ui.player.size * 0.5,
                                game_ui.player.y + game_ui.player.size * 0.5,
                            )
                            ai_manager.ensure_robbers(
                                game_map,
                                target_count=robber_target_count,
                                focus_points=[player_center],
                                enabled=True,
                            )
                        else:
                            ai_manager.ensure_robbers(game_map, target_count=0, enabled=False)

                        ai_tick_accumulator += dt
                        update_steps = 0
                        while ai_tick_accumulator >= ai_tick_interval and update_steps < 3:
                            ai_world_cache = ai_manager.update_all(
                                ai_tick_interval,
                                game_map,
                                player=game_ui.player,
                                extra_obstacles=remote_rects,
                            )
                            ai_tick_accumulator -= ai_tick_interval
                            update_steps += 1

                        if not ai_world_cache:
                            ai_world_cache = ai_manager.get_world_entities()

                        ai_render_players = AIManager.entities_to_other_players(ai_world_cache, prefix="AI")

                    combined_players = dict(remote_players)
                    combined_players.update(ai_render_players)
                    other_players.clear()
                    other_players.update(combined_players)

                    robber_entities = [
                        pdata
                        for pdata in other_players.values()
                        if isinstance(pdata, dict)
                        and bool(pdata.get('ai', False))
                        and str(pdata.get('ai_kind', '')).lower() == 'robber'
                    ]

                    if risky_mission_active and mission_system and mission_system.active_mission:
                        player_cx = game_ui.player.x + game_ui.player.size * 0.5
                        player_cy = game_ui.player.y + game_ui.player.size * 0.5
                        close_count = 0
                        for robber in robber_entities:
                            rcx = float(robber.get('x', 0.0) or 0.0) + game_ui.player.size * 0.5
                            rcy = float(robber.get('y', 0.0) or 0.0) + game_ui.player.size * 0.5
                            if ((rcx - player_cx) ** 2 + (rcy - player_cy) ** 2) <= (ROBBER_DANGER_RADIUS ** 2):
                                close_count += 1

                        robbery_close_count = close_count
                        if close_count > 0:
                            robbery_pressure = min(1.0, robbery_pressure + dt * robbery_fill_rate * close_count)
                        else:
                            robbery_pressure = max(0.0, robbery_pressure - dt * 0.35)

                        if robbery_pressure >= 1.0:
                            telemetry = (
                                game_ui.player.get_mission_telemetry_snapshot()
                                if hasattr(game_ui.player, 'get_mission_telemetry_snapshot')
                                else None
                            )
                            if mission_system.fail_active_mission(reason='robbed', player_stats=telemetry):
                                robbery_pressure = 0.0
                                robbery_close_count = 0
                                if ai_manager and not multiplayer:
                                    ai_manager.ensure_robbers(game_map, target_count=0, enabled=False)
                    else:
                        robbery_pressure = max(0.0, robbery_pressure - dt * 0.45)
                        robbery_close_count = 0

                    if hasattr(game_ui, 'set_robbery_status'):
                        game_ui.set_robbery_status(
                            active=risky_mission_active,
                            pressure=robbery_pressure,
                            robber_count=len(robber_entities),
                            close_count=robbery_close_count,
                        )

                    # Construction des rectangles de collision (joueurs distants + IA)
                    other_rects = []
                    for player_data in other_players.values():
                        if isinstance(player_data, dict):
                            ox, oy = player_data.get('x', 0), player_data.get('y', 0)
                        else:
                            ox, oy = player_data
                        other_rects.append(pygame.Rect(int(ox + hit_offset), int(oy + hit_offset), hit_size, hit_size))

                    # Mise à jour de l'état du jeu (mouvement, collisions, etc.)
                    game_ui.update(pygame.key.get_pressed(), dt, other_rects)

                    # Déclencher les SFX véhicule à partir de la télémétrie joueur.
                    if collision_sound_cooldown > 0.0:
                        collision_sound_cooldown = max(0.0, collision_sound_cooldown - dt)

                    player = game_ui.player
                    speed_kmh = float(getattr(player, 'speed_kmh', 0.0) or 0.0)
                    lateral_speed = float(getattr(player, 'lateral_speed', 0.0) or 0.0)
                    drift_angle = abs(float(getattr(player, 'drift_angle', 0.0) or 0.0))
                    handbrake_now = bool(getattr(player, 'handbrake', False))

                    # Make drift audio easier to trigger while preserving hysteresis.
                    drift_start_threshold = 82.0
                    drift_hold_threshold = 62.0
                    lateral_trigger = lateral_speed >= (drift_hold_threshold if drift_sound_active else drift_start_threshold)
                    handbrake_trigger = handbrake_now and speed_kmh >= 30.0 and drift_angle >= 6.0
                    is_drifting_now = lateral_trigger or handbrake_trigger

                    if is_drifting_now and not drift_sound_active and hasattr(sound_manager, 'play_drift_start'):
                        sound_manager.play_drift_start()
                    elif not is_drifting_now and drift_sound_active and hasattr(sound_manager, 'play_drift_stop'):
                        sound_manager.play_drift_stop()
                    drift_sound_active = is_drifting_now

                    if handbrake_now and not handbrake_sound_latch and speed_kmh >= 20.0 and hasattr(sound_manager, 'play_brake'):
                        sound_manager.play_brake()
                    handbrake_sound_latch = handbrake_now

                    current_collision_count = int(getattr(player, 'collision_count', 0) or 0)
                    if current_collision_count < last_collision_count:
                        # Le compteur peut être réinitialisé après une mission.
                        last_collision_count = current_collision_count

                    new_collisions = max(0, current_collision_count - last_collision_count)
                    if new_collisions > 0 and collision_sound_cooldown <= 0.0 and hasattr(sound_manager, 'play_collision'):
                        impact_intensity = min(1.0, max(0.25, speed_kmh / 110.0))
                        sound_manager.play_collision(impact_intensity)
                        collision_sound_cooldown = 0.14
                    last_collision_count = current_collision_count

                    # Mise à jour du système de missions
                    if mission_system and game_ui:
                        if multiplayer and network_client and getattr(network_client, 'coop_notifications', None):
                            local_user = str(getattr(network_client, 'username', '') or getattr(game_ui, 'username', '') or '')
                            for notice in list(network_client.coop_notifications):
                                if not isinstance(notice, dict):
                                    continue
                                mission_payload = notice.get('mission')
                                participants = [str(p) for p in (notice.get('participants', []) or []) if str(p)]
                                if participants and local_user and local_user not in participants:
                                    continue

                                activated = False
                                if hasattr(mission_system, 'activate_network_mission'):
                                    activated = bool(mission_system.activate_network_mission(mission_payload, equipped_car=game_ui.player.car))
                                if activated:
                                    if hasattr(game_ui.player, 'reset_mission_telemetry'):
                                        game_ui.player.reset_mission_telemetry()
                                    if hasattr(sound_manager, 'play_event'):
                                        sound_manager.play_event('mission_accept')

                            network_client.coop_notifications.clear()

                        player_cx = game_ui.player.x + game_ui.player.size / 2
                        player_cy = game_ui.player.y + game_ui.player.size / 2
                        telemetry = (
                            game_ui.player.get_mission_telemetry_snapshot()
                            if hasattr(game_ui.player, 'get_mission_telemetry_snapshot')
                            else None
                        )
                        mission_system.update(player_cx, player_cy, dt, player_stats=telemetry)

                        if hasattr(mission_system, 'get_and_clear_mission_events'):
                            for event in mission_system.get_and_clear_mission_events():
                                event_name = str(event.get('type', ''))
                                if hasattr(sound_manager, 'play_event') and event_name:
                                    sound_manager.play_event(event_name)

                        # Résultat mission one-shot: popup local + synchro réseau (multi).
                        mission_result = mission_system.consume_last_result() if hasattr(mission_system, 'consume_last_result') else None
                        if mission_result:
                            if hasattr(game_ui, 'push_mission_result'):
                                game_ui.push_mission_result(mission_result)

                            if hasattr(game_ui.player, 'reset_mission_telemetry'):
                                game_ui.player.reset_mission_telemetry()

                            if hasattr(sound_manager, 'play_event'):
                                sound_manager.play_event('mission_complete' if mission_result.get('success', False) else 'mission_fail')

                            if multiplayer and network_client:
                                mission_payload = mission_result.get('mission', {}) if isinstance(mission_result.get('mission', {}), dict) else {}
                                mission_id = mission_payload.get('id')
                                if mission_id is not None:
                                    if mission_result.get('success', False):
                                        reward_value = int(mission_result.get('money_delta', mission_payload.get('reward', 0)) or 0)
                                        rep_delta = int(mission_result.get('reputation_delta', 0) or 0)
                                        network_client.send_mission_event(
                                            'mission_complete',
                                            {'id': mission_id, 'reward': reward_value, 'reputation_delta': rep_delta},
                                            equipped_car=game_ui.player.car,
                                        )
                                    else:
                                        network_client.send_mission_event(
                                            'mission_fail',
                                            {
                                                'id': mission_id,
                                                'reason': str(mission_result.get('reason', 'failed')),
                                            },
                                            equipped_car=game_ui.player.car,
                                        )

                        # Multi: synchroniser la liste serveur et traiter les refus d'acceptation.
                        if multiplayer and network_client:
                            if mission_system.active_mission is None and network_client.server_missions:
                                mission_system.load_server_missions(network_client.server_missions, equipped_car=game_ui.player.car)

                            if getattr(network_client, 'mission_denials', None):
                                for denial in network_client.mission_denials:
                                    denied_id = denial.get('mission_id')
                                    reason = denial.get('reason', 'incompatible')
                                    if denied_id is not None:
                                        mission_system.handle_server_mission_denied(denied_id, reason=reason)
                                        if hasattr(sound_manager, 'play_event'):
                                            sound_manager.play_event('mission_denied')
                                network_client.mission_denials.clear()

                    if game_ui and hasattr(sound_manager, 'update_vehicle_engine'):
                        sound_manager.update_vehicle_engine(player=game_ui.player)
                        if hasattr(sound_manager, 'update_other_engines'):
                            sound_manager.update_other_engines(player=game_ui.player, other_players=other_players)
                        desired_music = None
                        if hasattr(sound_manager, 'set_music_state'):
                            if mission_system and mission_system.active_mission:
                                desired_music = MISSION_MUSIC
                                state_name = 'high_intensity' if mission_system.active_mission.time_remaining <= 25 else 'mission'
                            else:
                                state_name = 'gameplay'
                            sound_manager.set_music_state(state_name)
                        if desired_music != game_music_track:
                            if desired_music:
                                sound_manager.play_music(desired_music, volume=1.0)
                            else:
                                sound_manager.stop_music()
                            game_music_track = desired_music

                    # Gestion du réseau en mode multijoueur
                    if multiplayer and network_client:
                        _send_player_position(network_client, game_ui.player, USERNAME)  # Envoi position
                        if _receive_player_positions(network_client, remote_players, USERNAME):  # Réception positions
                            connection_errors = 0  # Réinitialiser le compteur d'erreurs

                            # Rafraîchir immédiatement la vue de rendu après réception réseau
                            combined_players = dict(remote_players)
                            combined_players.update(ai_render_players)
                            other_players.clear()
                            other_players.update(combined_players)
                        else:
                            connection_errors += 1  # Incrémenter les erreurs
                            if connection_errors >= MAX_CONNECTION_ERRORS:
                                # Trop d'erreurs consécutives - déconnexion automatique
                                print("Trop d'erreurs de réception, retour au menu")
                                state = MENU
                                menu.language = language
                                current_menu_car = game_ui.player.car if (game_ui and getattr(game_ui, 'player', None)) else (_solo.get('car_model', 'MICRO'), _solo.get('car_color', 'White'))
                                menu.refresh_vehicle(current_menu_car)
                                game_ui = None
                                mission_system = None
                                phone_ui = None
                                ai_manager = None
                                ai_tick_accumulator = 0.0
                                ai_world_cache = {}
                                robbery_pressure = 0.0
                                robbery_close_count = 0
                                multiplayer = False
                                other_players.clear()
                                remote_players.clear()
                                if network_client:
                                    network_client.send_disconnect('net_error')
                                    network_client.close()
                                    network_client = None
                                menu.show_error = True
                                menu.error_message = tr(language, "menu.disconnected")
                                if hasattr(sound_manager, 'stop_vehicle_engine'):
                                    sound_manager.stop_vehicle_engine()
                                if hasattr(sound_manager, 'stop_city_ambience'):
                                    sound_manager.stop_city_ambience()
                                if MENU_MUSIC:
                                    sound_manager.play_music(MENU_MUSIC, volume=1.0)
                                else:
                                    sound_manager.stop_music()
                                if hasattr(sound_manager, 'set_music_state'):
                                    sound_manager.set_music_state('menu')
                                game_music_track = MENU_MUSIC
                    if multiplayer and network_client and hasattr(game_ui, 'set_party_snapshot'):
                        game_ui.set_party_snapshot(getattr(network_client, 'party_state', {}))
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
    if hasattr(sound_manager, 'stop_vehicle_engine'):
        sound_manager.stop_vehicle_engine()
    if hasattr(sound_manager, 'stop_city_ambience'):
        sound_manager.stop_city_ambience()
    pygame.quit()  # Quitter Pygame
    sys.exit()  # Terminer le programme

# Point d'entrée du programme
if __name__ == "__main__":
    main()

