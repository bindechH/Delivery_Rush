"""
Server UDP pour Delivery Rush - Gestion du multijoueur
Gère les connexions clients, la synchronisation des positions et la logique réseau.
"""

import json
import hashlib
import secrets
import logging
import math
import random
import socket
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pytmx

from modules.ia import AIManager

# Configuration du serveur
SERVER_HOST = '0.0.0.0'  # Écoute sur toutes les interfaces
SERVER_PORT = 12345
HEARTBEAT_TIMEOUT = 5  # secondes avant de considérer un client mort
BROADCAST_RATE = 30    # paquets par seconde pour pousser l'état du monde
TICK_SLEEP = 0.003     # petit sleep pour garder la charge raisonnable
# 64 KiB socket read buffer for UDP payloads.
BUFFER_SIZE = 65535
ROOT_DIR = Path(__file__).resolve().parent
DATA_DIR = ROOT_DIR / "server_data"
DATA_DIR.mkdir(exist_ok=True)
MISSION_GEN_INTERVAL = 40.0
MAX_SERVER_MISSIONS = 6
PARTY_MAX_MEMBERS = 3
PARTY_CHALLENGE_BASE_DELIVERIES = 3
PARTY_CHALLENGE_DELIVERIES_PER_MEMBER = 2
PARTY_CHALLENGE_BASE_TIME = 360
PARTY_CHALLENGE_TIME_PER_MEMBER = 90
PARTY_CHALLENGE_RETENTION = 12.0
AI_TICK_RATE = 8.0
AI_MAX_STEPS_PER_LOOP = 3
SERVER_BOT_COUNT = 8
SERVER_BOT_PREFIX = "BOT"
SERVER_MAP_PATH = ROOT_DIR / "assets" / "map" / "maps" / "deliveryrush_map.tmx"
PLAYER_SIZE = 134.0
PLAYER_HITBOX_SCALE = 0.175
DEFAULT_SPAWN_X = 2699.0
DEFAULT_SPAWN_Y = 1341.0
SERVER_HEAVY_MODELS = ("PICKUP", "VAN", "BOX TRUCK", "MEDIUM TRUCK")
SERVER_EXPRESS_MODELS = ("COUPE", "MUSCLECAR", "SPORT", "SUPERCAR", "LUXURY")
SERVER_RISKY_TYPE_BASE_CHANCE = {
    'standard': 0.28,
    'express': 0.52,
    'chain': 0.62,
}

SERVER_CARGO_POOL = {
    'standard': [
        {'type': 'colis', 'icon': 'PKG', 'weight': (20, 85)},
        {'type': 'alimentaire', 'icon': 'FOOD', 'weight': (25, 100)},
        {'type': 'documents', 'icon': 'DOC', 'weight': (5, 30)},
    ],
    'express': [
        {'type': 'medical', 'icon': 'MED', 'weight': (8, 45)},
        {'type': 'vip', 'icon': 'VIP', 'weight': (5, 25)},
        {'type': 'urgent', 'icon': 'NOW', 'weight': (10, 40)},
    ],
    'chain': [
        {'type': 'materiel', 'icon': 'BOX', 'weight': (60, 170)},
        {'type': 'lourd', 'icon': 'HVY', 'weight': (110, 260)},
        {'type': 'industriel', 'icon': 'IND', 'weight': (120, 300)},
    ],
}

SERVER_COOP_ROLE_BY_CLASS = {
    'compact': 'runner',
    'family': 'support',
    'sport': 'sprinter',
    'super': 'sprinter',
    'utility': 'hauler',
    'truck': 'hauler',
}

SERVER_VEHICLE_PROFILES = {
    "MICRO": {"vehicle_class": "compact", "max_speed": 800.0, "cargo_capacity": 70.0},
    "HATCHBACK": {"vehicle_class": "compact", "max_speed": 950.0, "cargo_capacity": 70.0},
    "SEDAN": {"vehicle_class": "family", "max_speed": 1050.0, "cargo_capacity": 120.0},
    "CIVIC": {"vehicle_class": "compact", "max_speed": 1100.0, "cargo_capacity": 80.0},
    "COUPE": {"vehicle_class": "sport", "max_speed": 1200.0, "cargo_capacity": 80.0},
    "WAGON": {"vehicle_class": "family", "max_speed": 1000.0, "cargo_capacity": 120.0},
    "MINIVAN": {"vehicle_class": "family", "max_speed": 900.0, "cargo_capacity": 140.0},
    "SUV": {"vehicle_class": "family", "max_speed": 1050.0, "cargo_capacity": 130.0},
    "JEEP": {"vehicle_class": "family", "max_speed": 950.0, "cargo_capacity": 130.0},
    "PICKUP": {"vehicle_class": "utility", "max_speed": 1000.0, "cargo_capacity": 210.0},
    "MUSCLECAR": {"vehicle_class": "sport", "max_speed": 1350.0, "cargo_capacity": 85.0},
    "SPORT": {"vehicle_class": "sport", "max_speed": 1400.0, "cargo_capacity": 80.0},
    "LUXURY": {"vehicle_class": "family", "max_speed": 1300.0, "cargo_capacity": 110.0},
    "SUPERCAR": {"vehicle_class": "super", "max_speed": 1500.0, "cargo_capacity": 65.0},
    "VAN": {"vehicle_class": "utility", "max_speed": 850.0, "cargo_capacity": 220.0},
    "BOX TRUCK": {"vehicle_class": "utility", "max_speed": 750.0, "cargo_capacity": 260.0},
    "MEDIUM TRUCK": {"vehicle_class": "truck", "max_speed": 700.0, "cargo_capacity": 320.0},
}

# Lieux de mission (copie serveur — doit correspondre à missions.py)
SERVER_LOCATIONS = [
    {"name": "Bibliothèque", "x": 75, "y": 105},
    {"name": "École de cinéma", "x": 98, "y": 132},
    {"name": "Campus Epita", "x": 135, "y": 132},
    {"name": "Université", "x": 167, "y": 105},
    {"name": "Restaurant italien", "x": 234, "y": 105},
    {"name": "Restaurant chinois", "x": 243, "y": 85},
    {"name": "Épicerie", "x": 279, "y": 85},
    {"name": "Pharmacie", "x": 219, "y": 85},
    {"name": "Centre commercial", "x": 261, "y": 132},
    {"name": "Agence de voyage", "x": 266, "y": 161},
    {"name": "Commissariat de police", "x": 285, "y": 183},
    {"name": "News Industry", "x": 286, "y": 203},
    {"name": "Tribunal", "x": 331, "y": 203},
    {"name": "Laboratoire", "x": 327, "y": 183},
    {"name": "Musée", "x": 359, "y": 181},
    {"name": "Fast food", "x": 373, "y": 181},
    {"name": "Hôpital 1", "x": 464, "y": 180},
    {"name": "Hôpital 2", "x": 256, "y": 250},
    {"name": "Hôtel", "x": 214, "y": 227},
    {"name": "Siège Vision Industry", "x": 219, "y": 185},
    {"name": "Siège Corp Industry", "x": 361, "y": 236},
    {"name": "Banque 1", "x": 417, "y": 342},
    {"name": "Banque 2", "x": 333, "y": 250},
    {"name": "Quartier d'affaires 1", "x": 403, "y": 236},
    {"name": "Quartier d'affaires 2", "x": 436, "y": 272},
    {"name": "Quartier d'affaires 3", "x": 412, "y": 307},
    {"name": "Stade", "x": 488, "y": 31},
    {"name": "Parc", "x": 488, "y": 131},
    {"name": "Quartier résidentiel 1", "x": 463, "y": 61},
    {"name": "Quartier résidentiel 2", "x": 475, "y": 28},
    {"name": "Quartier résidentiel 3", "x": 474, "y": 12},
    {"name": "Quartier résidentiel 4", "x": 427, "y": 61},
    {"name": "Quartier résidentiel 5", "x": 407, "y": 46},
    {"name": "Quartier résidentiel 6", "x": 358, "y": 22},
    {"name": "Siège Delivery Rush", "x": 397, "y": 412},
    {"name": "Delivery Dispatch", "x": 472, "y": 379},
    {"name": "Delivery Rush Logistics", "x": 411, "y": 446},
    {"name": "Entrepôt Delivery Rush", "x": 330, "y": 463},
]

# Mission points are authored on the 512x512 tile grid.
SERVER_MISSION_COORD_SCALE = 16.0


def _scale_server_locations_to_world(locations: List[Dict[str, Any]]) -> None:
    for loc in locations:
        try:
            x = float(loc.get('x', 0.0) or 0.0)
            y = float(loc.get('y', 0.0) or 0.0)
        except Exception:
            continue
        if x <= 600.0 and y <= 600.0:
            loc['x'] = x * SERVER_MISSION_COORD_SCALE
            loc['y'] = y * SERVER_MISSION_COORD_SCALE


_scale_server_locations_to_world(SERVER_LOCATIONS)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class ServerWorldMap:
    """Lightweight map data for server-side AI simulation (no rendering)."""

    def __init__(self, tmx_path: Path):
        self.tmx_path = Path(tmx_path)
        self.tmx_data = pytmx.TiledMap(str(self.tmx_path))

        self.tile_width = int(getattr(self.tmx_data, "tilewidth", 32) or 32)
        self.tile_height = int(getattr(self.tmx_data, "tileheight", 32) or 32)
        self.map_width_tiles = int(getattr(self.tmx_data, "width", 0) or 0)
        self.map_height_tiles = int(getattr(self.tmx_data, "height", 0) or 0)
        self.width_px = self.map_width_tiles * self.tile_width
        self.height_px = self.map_height_tiles * self.tile_height

        self._road_grid = [[False] * self.map_width_tiles for _ in range(self.map_height_tiles)]
        self._collision_grid = [[False] * self.map_width_tiles for _ in range(self.map_height_tiles)]

        for layer in self.tmx_data.layers:
            if not isinstance(layer, pytmx.TiledTileLayer):
                continue
            layer_name = (layer.name or "").lower()
            if "roads_base" in layer_name:
                self._mark_grid_from_layer(layer, self._road_grid)
            if layer_name == "collision_8":
                self._mark_grid_from_layer(layer, self._collision_grid)

        if not any(any(row) for row in self._road_grid):
            for y in range(self.map_height_tiles):
                for x in range(self.map_width_tiles):
                    self._road_grid[y][x] = not self._collision_grid[y][x]

        self.collision_rects: List[Tuple[float, float, float, float]] = []
        for y in range(self.map_height_tiles):
            for x in range(self.map_width_tiles):
                if self._collision_grid[y][x]:
                    self.collision_rects.append((
                        x * self.tile_width,
                        y * self.tile_height,
                        self.tile_width,
                        self.tile_height,
                    ))

    def _mark_grid_from_layer(self, layer: pytmx.TiledTileLayer, grid: List[List[bool]]) -> None:
        for y in range(self.map_height_tiles):
            for x in range(self.map_width_tiles):
                try:
                    gid = layer.data[y][x]
                except (IndexError, TypeError):
                    gid = 0
                if gid and gid > 0:
                    grid[y][x] = True

    def _rect_tile_bounds(self, rect: Any) -> Tuple[int, int, int, int]:
        """Convertit un rect monde (tuple/dict/obj) en bornes tuiles clamped."""
        x = y = w = h = 0.0

        if hasattr(rect, "x") and hasattr(rect, "y") and hasattr(rect, "width") and hasattr(rect, "height"):
            x = float(rect.x)
            y = float(rect.y)
            w = float(rect.width)
            h = float(rect.height)
        elif isinstance(rect, dict):
            if all(k in rect for k in ("x", "y", "w", "h")):
                x = float(rect["x"])
                y = float(rect["y"])
                w = float(rect["w"])
                h = float(rect["h"])
            elif all(k in rect for k in ("x", "y", "width", "height")):
                x = float(rect["x"])
                y = float(rect["y"])
                w = float(rect["width"])
                h = float(rect["height"])
        elif isinstance(rect, (tuple, list)) and len(rect) == 4:
            x = float(rect[0])
            y = float(rect[1])
            w = float(rect[2])
            h = float(rect[3])

        if self.map_width_tiles <= 0 or self.map_height_tiles <= 0:
            return 0, -1, 0, -1

        right = max(x, x + w - 1.0)
        bottom = max(y, y + h - 1.0)

        tx0 = max(0, int(x // self.tile_width))
        ty0 = max(0, int(y // self.tile_height))
        tx1 = min(self.map_width_tiles - 1, int(right // self.tile_width))
        ty1 = min(self.map_height_tiles - 1, int(bottom // self.tile_height))
        return tx0, tx1, ty0, ty1

    def check_collision(self, rect: Any) -> bool:
        tx0, tx1, ty0, ty1 = self._rect_tile_bounds(rect)
        if tx1 < tx0 or ty1 < ty0:
            return False

        for ty in range(ty0, ty1 + 1):
            row = self._collision_grid[ty]
            for tx in range(tx0, tx1 + 1):
                if row[tx]:
                    return True
        return False

    def check_rect_collision(self, rect: Any) -> List[Tuple[float, float, float, float]]:
        collisions: List[Tuple[float, float, float, float]] = []
        tx0, tx1, ty0, ty1 = self._rect_tile_bounds(rect)
        if tx1 < tx0 or ty1 < ty0:
            return collisions

        for ty in range(ty0, ty1 + 1):
            row = self._collision_grid[ty]
            for tx in range(tx0, tx1 + 1):
                if row[tx]:
                    collisions.append((
                        tx * self.tile_width,
                        ty * self.tile_height,
                        self.tile_width,
                        self.tile_height,
                    ))

        return collisions

    def is_road_at(self, world_x: float, world_y: float) -> bool:
        tx = int(world_x / self.tile_width)
        ty = int(world_y / self.tile_height)
        if 0 <= tx < self.map_width_tiles and 0 <= ty < self.map_height_tiles:
            return bool(self._road_grid[ty][tx])
        return False

    def is_collision_at(self, world_x: float, world_y: float) -> bool:
        tx = int(world_x / self.tile_width)
        ty = int(world_y / self.tile_height)
        if 0 <= tx < self.map_width_tiles and 0 <= ty < self.map_height_tiles:
            return bool(self._collision_grid[ty][tx])
        return True


class DeliveryRushServer:
    """
    Serveur principal pour Delivery Rush - Gestion du multijoueur UDP
    Gère les connexions clients, les positions et la synchronisation en temps réel
    """

    def __init__(self):
        """Initialisation du serveur UDP"""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.server_socket.bind((SERVER_HOST, SERVER_PORT))
        self.server_socket.setblocking(False)

        self.clients = {}       # username -> {addr, x, y, angle, car, last_seen}
        self.addr_to_name = {}  # addr -> username

        self.last_broadcast = time.time()

        # Données persistantes (auth + progression)
        self.player_data = self._load_data()

        # Missions générées par le serveur
        self.server_missions = []
        self._mission_counter = 0
        self._last_mission_gen = time.time()

        # Missions coop en attente
        self.coop_waiting = {}  # mission_id -> [usernames qui ont join]

        # Parties multijoueur (leader + membres, max 3)
        self.parties: Dict[str, Dict[str, Any]] = {}
        self.player_party: Dict[str, str] = {}
        self._party_counter = 0
        self.party_challenges: Dict[str, Dict[str, Any]] = {}
        self._challenge_counter = 0

        # IA serveur (autoritaire)
        self.server_map: Optional[ServerWorldMap] = None
        self.ai_manager: Optional[AIManager] = None
        self.bot_entities: Dict[str, Dict[str, Any]] = {}
        self._ai_tick_interval = 1.0 / max(1.0, AI_TICK_RATE)
        self._ai_accumulator = 0.0
        self._last_ai_time = time.time()

        # Générer les premières missions
        self._generate_missions(MAX_SERVER_MISSIONS)
        self._init_server_ai()

        logging.info(f"Serveur démarré sur {SERVER_HOST}:{SERVER_PORT}")

    @staticmethod
    def _default_player_fields(car: Optional[Any] = None) -> Dict[str, Any]:
        model = 'MICRO'
        color = 'White'
        if isinstance(car, (list, tuple)) and len(car) >= 2:
            model, color = str(car[0]), str(car[1])
        return {
            'money': 0,
            'owned_cars': [{'model': 'MICRO', 'color': 'White'}],
            'car_model': model,
            'car_color': color,
            'completed_missions': 0,
            'failed_missions': 0,
            'reputation': 0,
            'unlock_state': {
                'tier': 'rookie',
                'unlocked_types': ['standard'],
                'reputation': 0,
            },
            'mission_stats': {
                'current_streak': 0,
                'best_streak': 0,
                'bonus_earned': 0,
                'penalty_taken': 0,
            },
            'last_vehicle_class': 'compact',
            'audio_settings': {'music_state': 'menu'},
            'total_distance': 0.0,
            'last_x': DEFAULT_SPAWN_X,
            'last_y': DEFAULT_SPAWN_Y,
            'last_angle': 0.0,
        }

    def _merge_player_defaults(self, pdata: Dict[str, Any], car: Optional[Any] = None) -> Dict[str, Any]:
        defaults = self._default_player_fields(car=car)
        out = dict(pdata or {})
        for key, value in defaults.items():
            if key not in out:
                out[key] = value
            elif isinstance(value, dict) and isinstance(out.get(key), dict):
                merged = dict(value)
                merged.update(out[key])
                out[key] = merged
        return out

    @staticmethod
    def _unlock_state_from_reputation(reputation: int) -> Dict[str, Any]:
        rep = max(0, int(reputation))
        if rep >= 32:
            tier = 'elite'
            unlocked = ['standard', 'express', 'chain']
        elif rep >= 16:
            tier = 'pro'
            unlocked = ['standard', 'express', 'chain']
        elif rep >= 6:
            tier = 'trusted'
            unlocked = ['standard', 'express']
        else:
            tier = 'rookie'
            unlocked = ['standard']
        return {
            'tier': tier,
            'unlocked_types': unlocked,
            'reputation': rep,
        }

    def _init_server_ai(self):
        """Initialise la simulation des bots côté serveur."""
        if not SERVER_MAP_PATH.exists():
            logging.warning(f"Carte introuvable pour l'IA serveur: {SERVER_MAP_PATH}")
            return

        try:
            self.server_map = ServerWorldMap(SERVER_MAP_PATH)
            self.ai_manager = AIManager(use_proximity_culling=False)
            self.ai_manager.configure_performance(
                active_update_radius=1400.0,
                obstacle_neighbor_radius=0.0,
                use_dynamic_obstacles=False,
            )
            self.ai_manager.configure_dynamic_traffic(
                enabled=True,
                target_count=SERVER_BOT_COUNT,
                spawn_min_distance=580.0,
                spawn_radius=1700.0,
                despawn_radius=2800.0,
                center_bias=0.66,
                rebalance_interval=0.42,
                spawn_batch=1,
                edge_despawn_margin=56.0,
            )
            self.ai_manager.spawn_traffic(self.server_map, count=SERVER_BOT_COUNT, prefix="traffic")
            self.bot_entities = self._collect_bot_entities()
            logging.info(
                f"IA serveur initialisée: {len(self.bot_entities)} bots, tickrate={AI_TICK_RATE:.1f} Hz"
            )
        except Exception as e:
            logging.error(f"Échec d'initialisation de l'IA serveur: {e}")
            self.server_map = None
            self.ai_manager = None
            self.bot_entities = {}

    def _collect_bot_entities(self) -> Dict[str, Dict[str, Any]]:
        """Construit un snapshot des bots actuels sans avancer la simulation."""
        if not self.ai_manager:
            return {}

        entities: Dict[str, Dict[str, Any]] = {}
        all_agents = list(self.ai_manager.traffic_agents.values()) + list(self.ai_manager.pursuit_agents.values())
        for agent in all_agents:
            entities[agent.ai_id] = agent.to_world_entity()
        return entities

    def _build_player_obstacle_rects(self) -> List[Tuple[float, float, float, float]]:
        """Retourne des hitbox des joueurs réels pour l'évitement des bots."""
        hit_size = max(2.0, PLAYER_SIZE * PLAYER_HITBOX_SCALE)
        hit_offset = (PLAYER_SIZE - hit_size) * 0.5

        rects: List[Tuple[float, float, float, float]] = []
        for pdata in self.clients.values():
            px = float(pdata.get('x', 0.0)) + hit_offset
            py = float(pdata.get('y', 0.0)) + hit_offset
            rects.append((px, py, hit_size, hit_size))
        return rects

    def _build_player_focus_points(self) -> List[Tuple[float, float]]:
        """Centres monde des joueurs réels pour spawn/despawn dynamique des bots."""
        points: List[Tuple[float, float]] = []
        center_offset = PLAYER_SIZE * 0.5
        for pdata in self.clients.values():
            px = float(pdata.get('x', 0.0)) + center_offset
            py = float(pdata.get('y', 0.0)) + center_offset
            points.append((px, py))
        return points

    def _active_robber_focus_points(self) -> List[Tuple[float, float]]:
        """Joueurs à cibler par les braqueurs IA (missions risquées/party actives)."""
        center_offset = PLAYER_SIZE * 0.5
        targeted_users: List[str] = []

        for mission in self.server_missions:
            if str(mission.get('status', '')) != 'active':
                continue

            risk_level = str(mission.get('risk_level', 'chill') or 'chill').lower()
            party_mode = bool(mission.get('party_mission', False))
            if risk_level != 'risky' and not party_mode:
                continue

            participants = [str(p) for p in (mission.get('participants', []) or []) if str(p)]
            if not participants:
                accepted_by = str(mission.get('accepted_by', '') or '').strip()
                if accepted_by:
                    participants = [accepted_by]

            for username in participants:
                if username in self.clients and username not in targeted_users:
                    targeted_users.append(username)

        focus_points: List[Tuple[float, float]] = []
        for username in targeted_users:
            pdata = self.clients.get(username)
            if not pdata:
                continue
            px = float(pdata.get('x', 0.0) or 0.0) + center_offset
            py = float(pdata.get('y', 0.0) or 0.0) + center_offset
            focus_points.append((px, py))

        return focus_points

    def _tick_server_ai(self):
        """Fait avancer l'IA serveur à fréquence fixe pour limiter la charge CPU."""
        if not self.ai_manager or not self.server_map:
            return

        now = time.time()
        elapsed = max(0.0, now - self._last_ai_time)
        self._last_ai_time = now

        max_accu = self._ai_tick_interval * (AI_MAX_STEPS_PER_LOOP + 1)
        self._ai_accumulator = min(max_accu, self._ai_accumulator + elapsed)

        steps = 0
        player_obstacles = self._build_player_obstacle_rects()
        player_focus_points = self._build_player_focus_points()
        robber_focus_points = self._active_robber_focus_points()
        robber_target_count = min(12, max(0, len(robber_focus_points) * 2))
        self.ai_manager.ensure_robbers(
            self.server_map,
            target_count=robber_target_count,
            focus_points=robber_focus_points,
            enabled=robber_target_count > 0,
        )

        while self._ai_accumulator >= self._ai_tick_interval and steps < AI_MAX_STEPS_PER_LOOP:
            self.bot_entities = self.ai_manager.update_all(
                self._ai_tick_interval,
                self.server_map,
                player=None,
                extra_obstacles=player_obstacles,
                focus_points=player_focus_points,
            )
            self._ai_accumulator -= self._ai_tick_interval
            steps += 1

        if steps >= AI_MAX_STEPS_PER_LOOP:
            self._ai_accumulator = min(self._ai_accumulator, self._ai_tick_interval)

        if not self.bot_entities:
            self.bot_entities = self._collect_bot_entities()

    def handle_incoming_data(self):
        """
        Traite les données entrantes des clients
        Gère les messages hello, state, disconnect, login et coop
        """
        addr = None
        try:
            data, addr = self.server_socket.recvfrom(BUFFER_SIZE)
            msg = json.loads(data.decode())
            msg_type = msg.get('type')

            if msg_type == 'hello':
                self.handle_hello(addr, msg)
                return

            if msg_type == 'state':
                self.handle_state(addr, msg)
                return

            if msg_type == 'disconnect':
                self.handle_disconnect(addr, msg)
                return

            if msg_type == 'chat':
                self.handle_chat(addr, msg)
                return

            if msg_type == 'mission_event':
                self.handle_mission_event(addr, msg)
                return

            if msg_type == 'coop_join':
                self.handle_coop_join(addr, msg)
                return

            if msg_type == 'leaderboard_request':
                self.handle_leaderboard_request(addr, msg)
                return

            if msg_type == 'party_create':
                self.handle_party_create(addr, msg)
                return

            if msg_type == 'party_join':
                self.handle_party_join(addr, msg)
                return

            if msg_type == 'party_leave':
                self.handle_party_leave(addr, msg)
                return

            if msg_type == 'party_state_request':
                self.handle_party_state_request(addr, msg)
                return

            if msg_type == 'save_progress':
                self.handle_save_progress(addr, msg)
                return

        except BlockingIOError:
            return  # Pas de données disponibles
        except ConnectionResetError as e:
            logging.warning(f"Connexion réinitialisée depuis {addr or '<unknown>'}: {e}")
        except json.JSONDecodeError as e:
            logging.warning(f"JSON invalide reçu de {addr or '<unknown>'}: {e}")
        except Exception as e:
            logging.error(f"Erreur lors du traitement des données de {addr or '<unknown>'}: {e}")

    def handle_hello(self, addr, msg):
        """
        Gère la connexion d'un client avec authentification optionnelle.
        Si password fourni → mode multi (auth requise).
        Sinon → mode casual (pas d'auth).
        """
        username = msg.get('username')
        car = msg.get('car', ('SUPERCAR', 'Black'))
        password = msg.get('password')

        if not username:
            self._send_hello_response(addr, status='denied', reason='invalid_username')
            return

        # Mode authentifié (multi)
        if password is not None:
            if username in self.player_data:
                # Compte existant → vérifier le mot de passe
                stored = self._merge_player_defaults(self.player_data[username], car=car)
                self.player_data[username] = stored
                if not self._verify_password(password, stored.get('salt', ''), stored.get('password_hash', '')):
                    self._send_hello_response(addr, status='denied', reason='wrong_password')
                    return
            else:
                # Nouveau compte → enregistrer
                salt = secrets.token_hex(16)
                pw_hash = hashlib.sha256((salt + password).encode()).hexdigest()
                account_data = self._merge_player_defaults({}, car=car)
                account_data['salt'] = salt
                account_data['password_hash'] = pw_hash
                self.player_data[username] = account_data
                self._save_data()
                logging.info(f"Nouveau compte créé : {username}")

        # Vérifier collision de nom si déjà connecté
        if username in self.clients and self.clients[username]['addr'] != addr:
            logging.info(f"Nom '{username}' déjà connecté, rejet de {addr}")
            self._send_hello_response(addr, status='denied', reason='username_taken')
            return

        # Accepter la connexion
        saved_x = DEFAULT_SPAWN_X
        saved_y = DEFAULT_SPAWN_Y
        saved_angle = 0.0
        saved_car = car
        if username in self.player_data:
            pd = self._merge_player_defaults(self.player_data[username], car=car)
            pd['unlock_state'] = self._unlock_state_from_reputation(pd.get('reputation', 0))
            self.player_data[username] = pd
            saved_x = pd.get('last_x', DEFAULT_SPAWN_X)
            saved_y = pd.get('last_y', DEFAULT_SPAWN_Y)
            saved_angle = pd.get('last_angle', 0.0)
            saved_car_m = pd.get('car_model')
            saved_car_c = pd.get('car_color')
            if saved_car_m and saved_car_c:
                saved_car = (saved_car_m, saved_car_c)

        self.clients[username] = {
            'addr': addr,
            'x': saved_x,
            'y': saved_y,
            'angle': saved_angle,
            'car': saved_car,
            'on_road': True,
            'last_seen': time.time()
        }
        self.addr_to_name[addr] = username

        # Préparer les données joueur pour la réponse
        player_info = None
        if username in self.player_data:
            pd = self._merge_player_defaults(self.player_data[username], car=saved_car)
            pd['unlock_state'] = self._unlock_state_from_reputation(pd.get('reputation', 0))
            self.player_data[username] = pd
            player_info = {
                'money': pd.get('money', 0),
                'owned_cars': pd.get('owned_cars', []),
                'car_model': pd.get('car_model', 'MICRO'),
                'car_color': pd.get('car_color', 'White'),
                'completed_missions': pd.get('completed_missions', 0),
                'failed_missions': pd.get('failed_missions', 0),
                'reputation': pd.get('reputation', 0),
                'unlock_state': pd.get('unlock_state', {}),
                'mission_stats': pd.get('mission_stats', {}),
                'last_vehicle_class': pd.get('last_vehicle_class', 'compact'),
                'audio_settings': pd.get('audio_settings', {'music_state': 'menu'}),
                'last_x': pd.get('last_x', DEFAULT_SPAWN_X),
                'last_y': pd.get('last_y', DEFAULT_SPAWN_Y),
                'last_angle': pd.get('last_angle', 0.0),
                'total_distance': pd.get('total_distance', 0.0),
            }

        logging.info(f"Connexion : {username} @ {addr}" + (" (authentifié)" if password else ""))
        self._send_hello_response(addr, status='ok', player_data=player_info)

    def _send_hello_response(self, addr, status='ok', reason=None, player_data=None):
        """Envoie la réponse au handshake hello d'un client"""
        payload = {'type': 'hello_response', 'status': status}
        if reason:
            payload['reason'] = reason
        if player_data:
            payload['player_data'] = player_data
        # Envoyer aussi la liste des missions serveur
        if status == 'ok':
            payload['missions'] = [m for m in self.server_missions if m.get('status') == 'available']
        try:
            self.server_socket.sendto(json.dumps(payload).encode(), addr)
        except Exception as e:
            logging.error(f"Échec d'envoi de hello_response à {addr}: {e}")

    def handle_state(self, addr, msg):
        """
        Met à jour l'état d'un client (position, angle, voiture)
        Gère aussi les changements d'adresse IP/port (NAT traversal)
        """
        username = msg.get('username')
        if not username or username not in self.clients:
            # Client non enregistré ou état perdu : demander un re-hello
            self._send_control(addr, 'need_hello')
            return

        client = self.clients[username]
        if client['addr'] != addr:
            # Mise à jour de l'adresse si NAT/port changé (reconnexion rapide)
            old_addr = client['addr']
            self.addr_to_name.pop(old_addr, None)
            client['addr'] = addr
            self.addr_to_name[addr] = username
            logging.info(f"Adresse mise à jour pour {username}: {old_addr} -> {addr}")

        # Mise à jour des données du client
        client['x'] = msg.get('x', client['x'])
        client['y'] = msg.get('y', client['y'])
        client['angle'] = msg.get('angle', client.get('angle', 0.0))
        client['on_road'] = msg.get('on_road', True)
        client['vehicle_class'] = msg.get('vehicle_class', client.get('vehicle_class', ''))
        client['cargo_capacity'] = msg.get('cargo_capacity', client.get('cargo_capacity', 0))
        new_car = msg.get('car', client['car'])
        client['car'] = new_car
        client['last_seen'] = time.time()  # Timestamp de dernière activité

        # Persist car change to player data
        if username in self.player_data:
            car_m = new_car[0] if isinstance(new_car, (list, tuple)) else new_car
            car_c = new_car[1] if isinstance(new_car, (list, tuple)) and len(new_car) > 1 else 'White'
            if self.player_data[username].get('car_model') != car_m or self.player_data[username].get('car_color') != car_c:
                self.player_data[username]['car_model'] = car_m
                self.player_data[username]['car_color'] = car_c
            if client.get('vehicle_class'):
                self.player_data[username]['last_vehicle_class'] = client.get('vehicle_class')

    def handle_disconnect(self, addr, msg):
        """Gère la déconnexion propre d'un client, sauvegarde la position."""
        username = msg.get('username') or self.addr_to_name.get(addr)
        if not username or username not in self.clients:
            return
        client_data = self.clients[username]
        client_addr = client_data['addr']
        # Sauvegarder la dernière position et voiture
        if username in self.player_data:
            self.player_data[username]["last_x"] = client_data.get("x", 0)
            self.player_data[username]["last_y"] = client_data.get("y", 0)
            self.player_data[username]["last_angle"] = client_data.get("angle", 0)
            car = client_data.get("car")
            if car:
                self.player_data[username]["car_model"] = car[0] if isinstance(car, (list, tuple)) else car
                self.player_data[username]["car_color"] = car[1] if isinstance(car, (list, tuple)) and len(car) > 1 else 'White'
            if client_data.get('vehicle_class'):
                self.player_data[username]['last_vehicle_class'] = client_data.get('vehicle_class')
            self._save_player(username)
        logging.info(f"Déconnexion : {username} ({client_addr})")
        self.addr_to_name.pop(client_addr, None)
        self.clients.pop(username, None)
        self._remove_player_from_party(username)
        self._broadcast_party_state(reason='party_leave')

    def _send_control(self, addr, code):
        """Envoie un message de contrôle à un client (ex: need_hello)"""
        payload = {'type': 'control', 'code': code}
        try:
            self.server_socket.sendto(json.dumps(payload).encode(), addr)
        except Exception as e:
            logging.error(f"Échec d'envoi du contrôle '{code}' à {addr}: {e}")

    def check_disconnections(self):
        """
        Vérifie les clients inactifs et les déconnecte automatiquement
        Utilise HEARTBEAT_TIMEOUT pour déterminer l'inactivité
        """
        now = time.time()
        to_drop = []
        for username, data in list(self.clients.items()):
            if now - data['last_seen'] > HEARTBEAT_TIMEOUT:
                to_drop.append(username)

        for username in to_drop:
            client_data = self.clients[username]
            addr = client_data['addr']
            # Sauvegarder position et voiture avant suppression
            if username in self.player_data:
                self.player_data[username]["last_x"] = client_data.get("x", 0)
                self.player_data[username]["last_y"] = client_data.get("y", 0)
                self.player_data[username]["last_angle"] = client_data.get("angle", 0)
                car = client_data.get("car")
                if car:
                    self.player_data[username]["car_model"] = car[0] if isinstance(car, (list, tuple)) else car
                    self.player_data[username]["car_color"] = car[1] if isinstance(car, (list, tuple)) and len(car) > 1 else 'White'
                if client_data.get('vehicle_class'):
                    self.player_data[username]['last_vehicle_class'] = client_data.get('vehicle_class')
                self._save_player(username)
            logging.info(f"Suppression de {username} ({addr}) - timeout")
            self.addr_to_name.pop(addr, None)
            self.clients.pop(username, None)
            self._remove_player_from_party(username)

        if to_drop:
            self._broadcast_party_state(reason='party_leave')

    def broadcast_positions(self):
        """
        Diffuse les positions de tous les joueurs à tous les clients connectés
        Respecte le taux BROADCAST_RATE pour éviter la surcharge réseau
        """
        if time.time() - self.last_broadcast < 1.0 / BROADCAST_RATE:
            return  # Pas encore temps de broadcaster

        if not self.clients:
            return  # Aucun client connecté

        # Construction du paquet avec toutes les positions
        players = {
            username: {
                'x': data['x'],
                'y': data['y'],
                'angle': data.get('angle', 0.0),
                'car': data['car'],
                'on_road': data.get('on_road', True),
                'vehicle_class': data.get('vehicle_class', ''),
            }
            for username, data in self.clients.items()
        }

        # Ajouter les bots autoritaires du serveur.
        if self.bot_entities:
            bot_players = AIManager.entities_to_other_players(self.bot_entities, prefix=SERVER_BOT_PREFIX)
            compact_bots = {}
            for bot_name, payload in bot_players.items():
                if not isinstance(payload, dict):
                    continue
                compact_bots[bot_name] = {
                    'x': float(payload.get('x', 0.0) or 0.0),
                    'y': float(payload.get('y', 0.0) or 0.0),
                    'angle': float(payload.get('angle', 0.0) or 0.0),
                    'car': payload.get('car', ('MICRO', 'White')),
                    'on_road': bool(payload.get('on_road', True)),
                    'ai': True,
                    'ai_kind': str(payload.get('ai_kind', 'traffic') or 'traffic'),
                    'ai_state': str(payload.get('ai_state', 'driving') or 'driving'),
                    'vehicle_class': str(payload.get('vehicle_class', '') or ''),
                }
            players.update(compact_bots)

        packet_payload = {'type': 'state_broadcast', 'players': players}
        packet = json.dumps(packet_payload).encode()

        # Hard guard: if packet is still huge, drop AI entries for this tick.
        if len(packet) > 60000:
            players = {
                username: pdata
                for username, pdata in players.items()
                if not (isinstance(pdata, dict) and bool(pdata.get('ai', False)))
            }
            packet = json.dumps({'type': 'state_broadcast', 'players': players}).encode()

        # Envoi à tous les clients
        for username, data in list(self.clients.items()):
            addr = data['addr']
            try:
                self.server_socket.sendto(packet, addr)
            except Exception as e:
                logging.error(f"Échec d'envoi du broadcast à {username} ({addr}): {e}")

        self.last_broadcast = time.time()

    def handle_chat(self, addr, msg):
        """Relaye un message de chat à tous les autres clients."""
        username = msg.get('username') or self.addr_to_name.get(addr)
        if not username or username not in self.clients:
            return
        message = msg.get('message', '')[:200]
        logging.info(f"Chat [{username}]: {message}")
        packet = json.dumps({
            'type': 'chat_broadcast',
            'username': username,
            'message': message
        }).encode()
        for uname, data in list(self.clients.items()):
            if uname != username:
                try:
                    self.server_socket.sendto(packet, data['addr'])
                except Exception:
                    pass

    def _build_leaderboard_top10(self) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for username, pdata in self.player_data.items():
            pd = self._merge_player_defaults(pdata)
            rows.append({
                'username': username,
                'completed_missions': int(pd.get('completed_missions', 0) or 0),
                'money': int(pd.get('money', 0) or 0),
                'reputation': int(pd.get('reputation', 0) or 0),
                'failed_missions': int(pd.get('failed_missions', 0) or 0),
            })

        rows.sort(key=lambda r: (r['completed_missions'], r['money'], r['reputation']), reverse=True)
        top10 = rows[:10]
        for i, row in enumerate(top10, start=1):
            row['rank'] = i
        return top10

    def handle_leaderboard_request(self, addr, msg):
        username = msg.get('username') or self.addr_to_name.get(addr)
        packet = {
            'type': 'leaderboard_data',
            'top10': self._build_leaderboard_top10(),
            'requested_by': username,
        }
        try:
            self.server_socket.sendto(json.dumps(packet).encode(), addr)
        except Exception:
            pass

    def _party_public_view(self, party_id: str, party: Dict[str, Any]) -> Dict[str, Any]:
        members = [m for m in party.get('members', []) if m in self.clients]
        if not members:
            members = list(party.get('members', []))

        challenge_payload = None
        challenge = self.party_challenges.get(party_id)
        if challenge:
            challenge_payload = self._party_challenge_view(challenge)

        return {
            'id': str(party_id),
            'leader': str(party.get('leader', '')),
            'members': members[:PARTY_MAX_MEMBERS],
            'size': min(PARTY_MAX_MEMBERS, len(members)),
            'max_size': PARTY_MAX_MEMBERS,
            'challenge': challenge_payload,
        }

    def _party_challenge_view(self, challenge: Dict[str, Any]) -> Dict[str, Any]:
        now = time.time()
        status = str(challenge.get('status', 'active'))
        if status == 'active':
            remaining_time = max(0, int(float(challenge.get('end_time', now) or now) - now))
        else:
            remaining_time = max(0, int(challenge.get('time_remaining', 0) or 0))

        return {
            'id': str(challenge.get('id', '')),
            'status': status,
            'leader': str(challenge.get('leader', '')),
            'participants': [p for p in challenge.get('participants', []) if p in self.clients],
            'target_deliveries': int(challenge.get('target_deliveries', 0) or 0),
            'completed_deliveries': int(challenge.get('completed_deliveries', 0) or 0),
            'time_limit': int(challenge.get('time_limit', 0) or 0),
            'time_remaining': remaining_time,
        }

    def _active_party_challenge(self, party_id: Optional[str]) -> Optional[Dict[str, Any]]:
        if not party_id:
            return None
        challenge = self.party_challenges.get(party_id)
        if not challenge:
            return None
        if str(challenge.get('status', 'active')) != 'active':
            return None
        return challenge

    def _send_party_event(self, party_id: str, event: str, payload: Optional[Dict[str, Any]] = None) -> None:
        party = self.parties.get(party_id)
        if not party:
            return

        message = {
            'type': 'party_event',
            'event': str(event),
            'party_id': str(party_id),
        }
        if payload:
            message.update(payload)

        packet = json.dumps(message).encode()
        for member in party.get('members', []):
            cdata = self.clients.get(member)
            if not cdata:
                continue
            try:
                self.server_socket.sendto(packet, cdata['addr'])
            except Exception:
                pass

    def _start_party_challenge(self, party_id: str, leader: str, participants: List[str]) -> Dict[str, Any]:
        current = self._active_party_challenge(party_id)
        if current:
            return current

        self._challenge_counter += 1
        target = max(
            PARTY_CHALLENGE_BASE_DELIVERIES,
            PARTY_CHALLENGE_BASE_DELIVERIES + (len(participants) - 1) * PARTY_CHALLENGE_DELIVERIES_PER_MEMBER,
        )
        time_limit = int(PARTY_CHALLENGE_BASE_TIME + len(participants) * PARTY_CHALLENGE_TIME_PER_MEMBER)
        start_t = time.time()

        challenge = {
            'id': f'C{self._challenge_counter:04d}',
            'party_id': party_id,
            'leader': leader,
            'participants': list(participants),
            'target_deliveries': int(target),
            'completed_deliveries': 0,
            'time_limit': int(time_limit),
            'time_remaining': int(time_limit),
            'start_time': start_t,
            'end_time': start_t + float(time_limit),
            'status': 'active',
            'counted_mission_ids': set(),
        }
        self.party_challenges[party_id] = challenge

        self._send_party_event(
            party_id,
            'challenge_started',
            {'challenge': self._party_challenge_view(challenge)},
        )
        self._broadcast_party_state(reason='challenge_started')
        return challenge

    def _finish_party_challenge(self, party_id: str, status: str) -> None:
        challenge = self.party_challenges.get(party_id)
        if not challenge:
            return
        if str(challenge.get('status', 'active')) != 'active':
            return

        now = time.time()
        challenge['status'] = str(status)
        challenge['time_remaining'] = max(0, int(float(challenge.get('end_time', now) or now) - now))
        challenge['finished_time'] = now
        self.party_challenges[party_id] = challenge

        self._send_party_event(
            party_id,
            'challenge_completed' if status == 'completed' else 'challenge_failed',
            {'challenge': self._party_challenge_view(challenge)},
        )
        self._broadcast_party_state(reason='challenge_update')

    def _progress_party_challenge(self, username: str, mission_id: Any) -> None:
        party_id = self.player_party.get(username)
        challenge = self._active_party_challenge(party_id)
        if not challenge:
            return
        if username not in challenge.get('participants', []):
            return

        mission_key = str(mission_id) if mission_id is not None else None
        counted = challenge.get('counted_mission_ids', set())
        if mission_key and mission_key in counted:
            return
        if mission_key:
            counted.add(mission_key)
            challenge['counted_mission_ids'] = counted

        challenge['completed_deliveries'] = int(challenge.get('completed_deliveries', 0) or 0) + 1
        target = int(challenge.get('target_deliveries', 0) or 0)

        self.party_challenges[party_id] = challenge

        self._send_party_event(
            party_id,
            'challenge_progress',
            {
                'challenge': self._party_challenge_view(challenge),
                'username': username,
            },
        )

        if target > 0 and int(challenge.get('completed_deliveries', 0) or 0) >= target:
            self._finish_party_challenge(party_id, 'completed')
        else:
            self._broadcast_party_state(reason='challenge_update')

    def _tick_party_challenges(self) -> None:
        now = time.time()
        changed = False
        to_delete: List[str] = []
        to_fail: List[str] = []

        for party_id, challenge in list(self.party_challenges.items()):
            status = str(challenge.get('status', 'active'))
            if status == 'active':
                remaining = max(0, int(float(challenge.get('end_time', now) or now) - now))
                challenge['time_remaining'] = remaining
                self.party_challenges[party_id] = challenge
                if remaining <= 0:
                    to_fail.append(party_id)
                    continue

                party = self.parties.get(party_id)
                if not party or not party.get('members'):
                    to_fail.append(party_id)
                    continue

                participants = [p for p in challenge.get('participants', []) if p in party.get('members', []) and p in self.clients]
                if participants != challenge.get('participants', []):
                    challenge['participants'] = participants
                    if challenge.get('leader') not in participants and participants:
                        challenge['leader'] = participants[0]
                    self.party_challenges[party_id] = challenge
                    changed = True
                if not participants:
                    to_fail.append(party_id)
            else:
                finished_t = float(challenge.get('finished_time', now) or now)
                if now - finished_t >= PARTY_CHALLENGE_RETENTION:
                    to_delete.append(party_id)

        for party_id in to_fail:
            self._finish_party_challenge(party_id, 'failed')
            changed = True

        for party_id in to_delete:
            self.party_challenges.pop(party_id, None)
            changed = True

        if changed:
            self._broadcast_party_state(reason='challenge_update')

    def _broadcast_party_state(self, reason: str = 'update') -> None:
        parties_payload = {
            pid: self._party_public_view(pid, pdata)
            for pid, pdata in self.parties.items()
            if pdata.get('members')
        }
        for username, cdata in list(self.clients.items()):
            my_party_id = self.player_party.get(username)
            my_party = parties_payload.get(my_party_id) if my_party_id else None
            packet = {
                'type': 'party_data',
                'reason': reason,
                'my_party': my_party,
                'parties': parties_payload,
            }
            try:
                self.server_socket.sendto(json.dumps(packet).encode(), cdata['addr'])
            except Exception:
                pass

    def _remove_player_from_party(self, username: str) -> None:
        party_id = self.player_party.pop(username, None)
        if not party_id:
            return
        party = self.parties.get(party_id)
        if not party:
            return

        members = [m for m in party.get('members', []) if m != username]
        if not members:
            self.parties.pop(party_id, None)
            self.party_challenges.pop(party_id, None)
            return

        party['members'] = members[:PARTY_MAX_MEMBERS]
        if party.get('leader') == username:
            party['leader'] = party['members'][0]
        self.parties[party_id] = party

        challenge = self._active_party_challenge(party_id)
        if challenge:
            participants = [p for p in challenge.get('participants', []) if p != username and p in party.get('members', [])]
            challenge['participants'] = participants
            if challenge.get('leader') == username and participants:
                challenge['leader'] = participants[0]
            self.party_challenges[party_id] = challenge
            if not participants:
                self._finish_party_challenge(party_id, 'failed')

    def handle_party_create(self, addr, msg):
        username = msg.get('username') or self.addr_to_name.get(addr)
        if not username or username not in self.clients:
            return

        self._remove_player_from_party(username)
        self._party_counter += 1
        party_id = f"P{self._party_counter:04d}"
        self.parties[party_id] = {
            'id': party_id,
            'leader': username,
            'members': [username],
        }
        self.player_party[username] = party_id
        self._broadcast_party_state(reason='party_created')

    def handle_party_join(self, addr, msg):
        username = msg.get('username') or self.addr_to_name.get(addr)
        if not username or username not in self.clients:
            return

        target_id = str(msg.get('party_id', '') or '').strip()
        leader_name = str(msg.get('leader', '') or '').strip()

        party_id = None
        if target_id and target_id in self.parties:
            party_id = target_id
        elif leader_name:
            for pid, pdata in self.parties.items():
                if str(pdata.get('leader', '')) == leader_name:
                    party_id = pid
                    break

        if not party_id:
            deny = {'type': 'party_event', 'event': 'join_denied', 'reason': 'party_not_found'}
            try:
                self.server_socket.sendto(json.dumps(deny).encode(), self.clients[username]['addr'])
            except Exception:
                pass
            return

        party = self.parties.get(party_id, {})
        members = list(party.get('members', []))
        if username in members:
            self.player_party[username] = party_id
            self._broadcast_party_state(reason='party_join')
            return

        if len(members) >= PARTY_MAX_MEMBERS:
            deny = {'type': 'party_event', 'event': 'join_denied', 'reason': 'party_full'}
            try:
                self.server_socket.sendto(json.dumps(deny).encode(), self.clients[username]['addr'])
            except Exception:
                pass
            return

        self._remove_player_from_party(username)
        members.append(username)
        party['members'] = members[:PARTY_MAX_MEMBERS]
        self.parties[party_id] = party
        self.player_party[username] = party_id
        self._broadcast_party_state(reason='party_join')

    def handle_party_leave(self, addr, msg):
        username = msg.get('username') or self.addr_to_name.get(addr)
        if not username:
            return
        self._remove_player_from_party(username)
        self._broadcast_party_state(reason='party_leave')

    def handle_party_state_request(self, addr, msg):
        username = msg.get('username') or self.addr_to_name.get(addr)
        parties_payload = {
            pid: self._party_public_view(pid, pdata)
            for pid, pdata in self.parties.items()
            if pdata.get('members')
        }
        my_party_id = self.player_party.get(username) if username else None
        payload = {
            'type': 'party_data',
            'reason': 'party_sync',
            'my_party': parties_payload.get(my_party_id) if my_party_id else None,
            'parties': parties_payload,
        }
        try:
            self.server_socket.sendto(json.dumps(payload).encode(), addr)
        except Exception:
            pass

    @staticmethod
    def _normalize_server_car(equipped_car: Any) -> Tuple[str, str]:
        if isinstance(equipped_car, (list, tuple)) and len(equipped_car) >= 2:
            return str(equipped_car[0]), str(equipped_car[1])
        if isinstance(equipped_car, str):
            return equipped_car, 'White'
        return 'MICRO', 'White'

    def _server_vehicle_profile(self, equipped_car: Any) -> Dict[str, Any]:
        model, color = self._normalize_server_car(equipped_car)
        base = SERVER_VEHICLE_PROFILES.get(model, SERVER_VEHICLE_PROFILES['MICRO'])
        return {
            'model': model,
            'color': color,
            'vehicle_class': str(base.get('vehicle_class', 'compact')),
            'max_speed': float(base.get('max_speed', 800.0)),
            'cargo_capacity': float(base.get('cargo_capacity', 70.0)),
        }

    def _is_server_vehicle_eligible(self, requirements: Dict[str, Any], equipped_car: Any) -> bool:
        profile = self._server_vehicle_profile(equipped_car)
        model = profile['model'].upper()
        vclass = profile['vehicle_class'].lower()
        max_speed = profile['max_speed']
        capacity = profile['cargo_capacity']

        required_models = [str(m).upper() for m in requirements.get('required_models', []) if m]
        if required_models and model not in required_models:
            return False

        required_class = str(requirements.get('required_class', '')).strip().lower()
        if required_class and vclass != required_class:
            return False

        min_speed = float(requirements.get('min_speed', 0.0) or 0.0)
        if min_speed > 0.0 and max_speed + 1e-6 < min_speed:
            return False

        min_capacity = float(requirements.get('min_capacity', 0.0) or 0.0)
        if min_capacity > 0.0 and capacity + 1e-6 < min_capacity:
            return False

        return True

    def _fit_requirements_to_profile(self, requirements: Dict[str, Any], profile: Dict[str, Any]) -> Dict[str, Any]:
        out = dict(requirements)
        model = str(profile.get('model', 'MICRO'))
        vclass = str(profile.get('vehicle_class', 'compact'))
        max_speed = float(profile.get('max_speed', 800.0))
        capacity = float(profile.get('cargo_capacity', 70.0))

        req_models = out.get('required_models')
        if req_models:
            req_models = [str(m) for m in req_models if m]
            if model not in req_models:
                req_models.append(model)
            out['required_models'] = sorted(set(req_models))

        req_class = out.get('required_class')
        if req_class and str(req_class).lower() != vclass.lower():
            out['required_class'] = vclass

        min_speed = float(out.get('min_speed', 0.0) or 0.0)
        if min_speed > max_speed:
            out['min_speed'] = int(max_speed)

        min_capacity = float(out.get('min_capacity', 0.0) or 0.0)
        if min_capacity > capacity:
            out['min_capacity'] = int(capacity)

        if float(out.get('min_speed', 0.0) or 0.0) <= 0.0:
            out.pop('min_speed', None)
        if float(out.get('min_capacity', 0.0) or 0.0) <= 0.0:
            out.pop('min_capacity', None)

        return out

    def _pick_target_vehicle_profile(self) -> Dict[str, Any]:
        if self.clients:
            username = random.choice(list(self.clients.keys()))
            return self._server_vehicle_profile(self.clients[username].get('car', ('MICRO', 'White')))
        return self._server_vehicle_profile(('MICRO', 'White'))

    def _compute_server_mission_weights(self, profile: Dict[str, Any]) -> Dict[str, float]:
        vclass = str(profile.get('vehicle_class', 'compact')).lower()
        model = str(profile.get('model', 'MICRO'))
        max_speed = float(profile.get('max_speed', 800.0))
        capacity = float(profile.get('cargo_capacity', 70.0))

        weights = {'standard': 60.0, 'express': 25.0, 'chain': 15.0}
        class_bonuses = {
            'utility': {'standard': 8.0, 'express': -8.0, 'chain': 20.0},
            'truck': {'standard': 6.0, 'express': -12.0, 'chain': 24.0},
            'sport': {'standard': -5.0, 'express': 20.0, 'chain': -8.0},
            'super': {'standard': -6.0, 'express': 24.0, 'chain': -10.0},
            'family': {'standard': 5.0, 'express': 0.0, 'chain': 5.0},
        }
        if vclass in class_bonuses:
            for mtype, bonus in class_bonuses[vclass].items():
                weights[mtype] += bonus

        if model in ('BOX TRUCK', 'MEDIUM TRUCK'):
            weights['chain'] += 10.0
        if model in ('SPORT', 'SUPERCAR'):
            weights['express'] += 10.0
        if max_speed < 980.0:
            weights['express'] -= 8.0
        if capacity < 90.0:
            weights['chain'] -= 8.0

        for mtype in list(weights.keys()):
            weights[mtype] = max(5.0, weights[mtype])

        return weights

    @staticmethod
    def _server_vehicle_reward_factor(profile: Dict[str, Any]) -> float:
        max_speed = float(profile.get('max_speed', 800.0) or 800.0)
        capacity = float(profile.get('cargo_capacity', 70.0) or 70.0)
        speed_score = max(0.0, min(1.0, max_speed / 1500.0))
        cargo_score = max(0.0, min(1.0, capacity / 320.0))
        tier_score = 0.7 * speed_score + 0.3 * cargo_score
        return 0.72 + tier_score * 1.08

    def _build_server_mission_requirements(self, mission_type: str, dist_factor: float, profile: Dict[str, Any]) -> Dict[str, Any]:
        requirements: Dict[str, Any] = {}

        if mission_type == 'standard':
            if random.random() < 0.45:
                requirements['min_capacity'] = random.choice([60, 80, 100, 120])
        elif mission_type == 'express':
            requirements['min_speed'] = random.choice([1000, 1120, 1250, 1350])
            if random.random() < 0.35:
                requirements['required_class'] = 'sport'
            if random.random() < 0.2:
                requirements['required_models'] = random.sample(list(SERVER_EXPRESS_MODELS), k=3)
        else:
            requirements['min_capacity'] = random.choice([130, 160, 190, 220])
            if random.random() < 0.6:
                requirements['required_class'] = 'utility'
            if random.random() < 0.35:
                requirements['required_models'] = random.sample(list(SERVER_HEAVY_MODELS), k=3)

        if 'min_speed' in requirements:
            requirements['min_speed'] = int(requirements['min_speed'] + max(0.0, dist_factor - 1.0) * 180)
        if 'min_capacity' in requirements:
            requirements['min_capacity'] = int(requirements['min_capacity'] + max(0.0, dist_factor - 1.0) * 45)

        model = str(profile.get('model', 'MICRO'))
        if model in SERVER_HEAVY_MODELS and mission_type in ('standard', 'chain') and random.random() < 0.5:
            requirements['required_models'] = [model]
        if model in SERVER_EXPRESS_MODELS and mission_type == 'express' and random.random() < 0.5:
            requirements['required_models'] = [model]

        return self._fit_requirements_to_profile(requirements, profile)

    def _assign_server_cargo(self, mission_type: str, requirements: Dict[str, Any]) -> Dict[str, Any]:
        pool = SERVER_CARGO_POOL.get(mission_type, SERVER_CARGO_POOL['standard'])
        cargo = random.choice(pool)
        w_min, w_max = cargo['weight']
        weight = random.uniform(float(w_min), float(w_max))
        max_capacity = float(requirements.get('min_capacity', 0.0) or 0.0)
        if max_capacity > 0.0:
            weight = min(weight, max_capacity)
        return {
            'cargo_type': cargo['type'],
            'cargo_icon': cargo['icon'],
            'cargo_weight': round(max(5.0, weight), 1),
        }

    def _build_server_stops(self, mission_type: str, pickup: Dict[str, Any], delivery: Dict[str, Any]) -> List[Dict[str, Any]]:
        stops = [
            {'name': pickup['name'], 'x': pickup['x'], 'y': pickup['y'], 'kind': 'pickup'},
        ]
        if mission_type == 'chain':
            extra_count = random.choice([1, 2])
            excluded = {pickup['name'], delivery['name']}
            candidates = [loc for loc in SERVER_LOCATIONS if loc['name'] not in excluded]
            for stop in random.sample(candidates, k=min(extra_count, len(candidates))):
                stops.append({'name': stop['name'], 'x': stop['x'], 'y': stop['y'], 'kind': 'stop'})
        stops.append({'name': delivery['name'], 'x': delivery['x'], 'y': delivery['y'], 'kind': 'dropoff'})
        return stops

    def _build_party_route_stops(self, pickup: Dict[str, Any], delivery: Dict[str, Any], participant_count: int) -> List[Dict[str, Any]]:
        """Construit plusieurs points de livraison (environ un par joueur de la party)."""
        count = max(2, int(participant_count or 2))
        drop_count = max(2, min(6, count))
        stops = [
            {'name': pickup['name'], 'x': pickup['x'], 'y': pickup['y'], 'kind': 'pickup'},
        ]

        excluded = {pickup['name'], delivery['name']}
        candidates = [loc for loc in SERVER_LOCATIONS if loc['name'] not in excluded]
        random.shuffle(candidates)
        dropoffs = [
            {'name': delivery['name'], 'x': delivery['x'], 'y': delivery['y'], 'kind': 'dropoff'}
        ]
        for stop in candidates[: max(0, drop_count - 1)]:
            dropoffs.append({'name': stop['name'], 'x': stop['x'], 'y': stop['y'], 'kind': 'dropoff'})

        random.shuffle(dropoffs)
        stops.extend(dropoffs)
        return stops

    @staticmethod
    def _default_required_roles(mission_type: str) -> List[str]:
        if mission_type == 'express':
            return ['sprinter', 'support']
        if mission_type == 'chain':
            return ['hauler', 'support']
        return ['runner', 'support']

    def _send_mission_denied(self, username: str, mission_id: Any, reason: str) -> None:
        if username not in self.clients:
            return
        payload = {
            'type': 'mission_denied',
            'mission_id': mission_id,
            'reason': reason,
        }
        try:
            self.server_socket.sendto(json.dumps(payload).encode(), self.clients[username]['addr'])
        except Exception:
            pass

    def handle_mission_event(self, addr, msg):
        """Relaye un événement de mission à tous les autres clients."""
        username = msg.get('username') or self.addr_to_name.get(addr)
        if not username or username not in self.clients:
            return
        event = msg.get('event', '')
        mission_data = msg.get('data', {})
        equipped_car = msg.get('equipped_car', self.clients[username].get('car', ('MICRO', 'White')))
        logging.info(f"Mission event [{username}]: {event}")

        if event == 'mission_accept':
            mission_id = mission_data.get('id')
            if mission_id is None:
                self._send_mission_denied(username, mission_id, 'invalid_mission_id')
                return
            mission = None
            for m in self.server_missions:
                if int(m.get('id', -1)) == int(mission_id) and m.get('status') == 'available':
                    mission = m
                    break

            if mission is None:
                self._send_mission_denied(username, mission_id, 'mission_not_available')
                return

            # Party leader flow: only the leader can start a shared mission.
            party_id = self.player_party.get(username)
            party = self.parties.get(party_id) if party_id else None
            if party:
                if str(party.get('leader', '')) != username:
                    self._send_mission_denied(username, mission_id, 'party_leader_required')
                    return

                participants = [m for m in party.get('members', []) if m in self.clients][:PARTY_MAX_MEMBERS]
                if len(participants) > 1:
                    leader_car = self.clients[username].get('car', equipped_car)
                    equipped_car = leader_car
                    requirements = mission.get('requirements', {}) or {}
                    if requirements and not self._is_server_vehicle_eligible(requirements, leader_car):
                        self._send_mission_denied(username, mission_id, 'leader_vehicle_incompatible')
                        return

                    leader_profile = self._server_vehicle_profile(leader_car)
                    mission['requirements'] = self._fit_requirements_to_profile(requirements, leader_profile)
                    mission['status'] = 'active'
                    mission['accepted_by'] = username
                    mission['leader'] = username
                    mission['coop'] = True
                    mission['required_players'] = len(participants)
                    mission['participants'] = participants
                    mission['mission_ready'] = True
                    mission['party_id'] = party_id
                    mission['party_mission'] = True

                    mission['stops'] = self._build_party_route_stops(
                        mission.get('pickup', {}),
                        mission.get('delivery', {}),
                        len(participants),
                    )
                    mission['current_stop_index'] = 0
                    mission['risk_level'] = 'risky'

                    base_reward = int(mission.get('base_reward', mission.get('reward', 0)) or 0)
                    if base_reward <= 0:
                        base_reward = int(mission.get('reward', 0) or 0)
                    mission['base_reward'] = base_reward
                    mission['party_bonus_multiplier'] = 1.5
                    mission['reward'] = int(round(base_reward * 1.5))

                    base_time = int(mission.get('time_limit', 0) or 0)
                    party_time = int(round(base_time * 1.35 + len(participants) * 25))
                    mission['time_limit'] = max(base_time, party_time)

                    party_challenge = self._start_party_challenge(party_id, username, participants)

                    coop_packet = json.dumps({
                        'type': 'coop_activated',
                        'mission': mission,
                        'participants': participants,
                        'leader': username,
                        'party_challenge': self._party_challenge_view(party_challenge),
                    }).encode()
                    for member in participants:
                        cdata = self.clients.get(member)
                        if not cdata:
                            continue
                        try:
                            self.server_socket.sendto(coop_packet, cdata['addr'])
                        except Exception:
                            pass

                    self._broadcast_missions()
                    # Keep relay behavior below for mission_broadcast.
                    mission_data = dict(mission_data or {})
                    mission_data['party_started'] = True
                    mission_data['participants'] = participants
                    mission_data['leader'] = username
                    mission_data['coop'] = True
                    mission_data['reward'] = int(mission.get('reward', 0) or 0)
                    # Skip legacy accept path.
                    event = 'mission_accept'
                else:
                    # Solo leader in party behaves like normal single-player accept.
                    pass

            if mission.get('coop') and not mission.get('mission_ready', False):
                self._send_mission_denied(username, mission_id, 'coop_not_ready')
                return

            requirements = mission.get('requirements', {}) or {}
            if requirements and not self._is_server_vehicle_eligible(requirements, equipped_car):
                self._send_mission_denied(username, mission_id, 'vehicle_incompatible')
                return

            mission['status'] = 'active'
            mission['accepted_by'] = username
            self._broadcast_missions()

        # Mettre à jour la progression côté serveur si authentifié
        if event == 'mission_complete' and username in self.player_data:
            self.player_data[username] = self._merge_player_defaults(self.player_data[username])
            reward = mission_data.get('reward', 0)
            self.player_data[username]['money'] = self.player_data[username].get('money', 0) + reward
            self.player_data[username]['completed_missions'] = self.player_data[username].get('completed_missions', 0) + 1
            rep_delta = int(mission_data.get('reputation_delta', 0) or 0)
            self.player_data[username]['reputation'] = max(0, int(self.player_data[username].get('reputation', 0) + rep_delta))
            self.player_data[username]['unlock_state'] = self._unlock_state_from_reputation(self.player_data[username]['reputation'])

            mission_stats = self.player_data[username].get('mission_stats', {}) if isinstance(self.player_data[username].get('mission_stats'), dict) else {}
            mission_stats['current_streak'] = int(mission_stats.get('current_streak', 0) or 0) + 1
            mission_stats['best_streak'] = max(int(mission_stats.get('best_streak', 0) or 0), mission_stats['current_streak'])
            mission_stats['bonus_earned'] = int(mission_stats.get('bonus_earned', 0) or 0) + max(0, int(reward))
            self.player_data[username]['mission_stats'] = mission_stats

            mission_id = mission_data.get('id')
            if mission_id is not None:
                for m in self.server_missions:
                    if int(m.get('id', -1)) == int(mission_id):
                        m['status'] = 'completed'
                        break
                self._broadcast_missions()

            self._progress_party_challenge(username, mission_data.get('id'))

            self._save_data()
        elif event == 'mission_fail' and username in self.player_data:
            self.player_data[username] = self._merge_player_defaults(self.player_data[username])
            self.player_data[username]['failed_missions'] = self.player_data[username].get('failed_missions', 0) + 1
            self.player_data[username]['unlock_state'] = self._unlock_state_from_reputation(self.player_data[username].get('reputation', 0))

            mission_stats = self.player_data[username].get('mission_stats', {}) if isinstance(self.player_data[username].get('mission_stats'), dict) else {}
            mission_stats['current_streak'] = 0
            mission_stats['penalty_taken'] = int(mission_stats.get('penalty_taken', 0) or 0) + 1
            self.player_data[username]['mission_stats'] = mission_stats

            mission_id = mission_data.get('id')
            if mission_id is not None:
                for m in self.server_missions:
                    if int(m.get('id', -1)) == int(mission_id):
                        m['status'] = 'failed'
                        break
                self._broadcast_missions()

            self._save_data()

        packet = json.dumps({
            'type': 'mission_broadcast',
            'username': username,
            'event': event,
            'data': mission_data
        }).encode()
        for uname, data in list(self.clients.items()):
            if uname != username:
                try:
                    self.server_socket.sendto(packet, data['addr'])
                except Exception:
                    pass

    def handle_coop_join(self, addr, msg):
        """Gère un joueur qui rejoint une mission coop."""
        username = self.addr_to_name.get(addr)
        if not username:
            return
        mission_id = msg.get('mission_id')
        if mission_id is None:
            return

        # Trouver la mission serveur
        mission = None
        for m in self.server_missions:
            if m['id'] == mission_id and m.get('coop'):
                mission = m
                break
        if not mission:
            return

        player_car = self.clients.get(username, {}).get('car', ('MICRO', 'White'))
        profile = self._server_vehicle_profile(player_car)
        player_role = SERVER_COOP_ROLE_BY_CLASS.get(profile.get('vehicle_class', 'compact'), 'runner')

        required_roles = list(mission.get('required_roles', []))
        participant_roles = mission.get('participant_roles') if isinstance(mission.get('participant_roles'), dict) else {}

        # Contrôle des slots de rôle requis.
        if required_roles and player_role not in required_roles:
            deny = {
                'type': 'coop_denied',
                'mission_id': mission_id,
                'reason': 'role_not_required',
                'required_roles': required_roles,
            }
            try:
                self.server_socket.sendto(json.dumps(deny).encode(), self.clients[username]['addr'])
            except Exception:
                pass
            return

        if required_roles:
            for uname, role in participant_roles.items():
                if uname != username and role == player_role:
                    deny = {
                        'type': 'coop_denied',
                        'mission_id': mission_id,
                        'reason': 'role_slot_taken',
                        'required_roles': required_roles,
                        'role': player_role,
                    }
                    try:
                        self.server_socket.sendto(json.dumps(deny).encode(), self.clients[username]['addr'])
                    except Exception:
                        pass
                    return

        if mission_id not in self.coop_waiting:
            self.coop_waiting[mission_id] = []
        if username not in self.coop_waiting[mission_id] and len(self.coop_waiting[mission_id]) >= PARTY_MAX_MEMBERS:
            deny = {
                'type': 'coop_denied',
                'mission_id': mission_id,
                'reason': 'coop_full',
            }
            try:
                self.server_socket.sendto(json.dumps(deny).encode(), self.clients[username]['addr'])
            except Exception:
                pass
            return
        if username not in self.coop_waiting[mission_id]:
            self.coop_waiting[mission_id].append(username)
            participant_roles[username] = player_role
            mission['participant_roles'] = participant_roles
            logging.info(f"Coop join: {username} -> mission {mission_id} ({len(self.coop_waiting[mission_id])}/{mission.get('required_players', 2)})")

        required = mission.get('required_players', 2)
        roles_ready = True
        if required_roles:
            current_roles = set(participant_roles.values())
            roles_ready = all(role in current_roles for role in required_roles)

        if len(self.coop_waiting[mission_id]) >= required and roles_ready:
            # Mission coop activée !
            participants = self.coop_waiting.pop(mission_id)
            mission['status'] = 'active'
            mission['participants'] = participants
            mission['mission_ready'] = True
            logging.info(f"Coop mission {mission_id} activée pour : {participants}")
            # Notifier les participants
            coop_packet = json.dumps({
                'type': 'coop_activated',
                'mission': mission,
                'participants': participants,
            }).encode()
            for uname in participants:
                if uname in self.clients:
                    try:
                        self.server_socket.sendto(coop_packet, self.clients[uname]['addr'])
                    except Exception:
                        pass

    def handle_save_progress(self, addr, msg):
        """Sauvegarde la progression d'un joueur (mode multi)."""
        username = self.addr_to_name.get(addr)
        if not username or username not in self.player_data:
            return
        progress = msg.get('data', {})
        pd = self._merge_player_defaults(self.player_data[username])
        for key in (
            'money',
            'owned_cars',
            'car_model',
            'car_color',
            'completed_missions',
            'failed_missions',
            'total_distance',
            'reputation',
            'unlock_state',
            'mission_stats',
            'last_vehicle_class',
            'audio_settings',
        ):
            if key in progress:
                pd[key] = progress[key]
        if 'reputation' in progress or 'unlock_state' not in pd:
            pd['unlock_state'] = self._unlock_state_from_reputation(pd.get('reputation', 0))
        self.player_data[username] = pd
        self._save_player(username)
        logging.info(f"Progression sauvegardée pour {username}")

    # === DATA PERSISTENCE ===

    def _load_data(self):
        """Charge les données persistantes depuis server_data/ (un fichier par joueur)."""
        data = {}
        for f in DATA_DIR.glob("*.json"):
            try:
                pdata = json.loads(f.read_text())
                username = f.stem
                data[username] = self._merge_player_defaults(pdata)
            except Exception as e:
                logging.error(f"Erreur chargement {f}: {e}")
        logging.info(f"Données chargées : {len(data)} joueurs")
        return data

    def _save_data(self):
        """Sauvegarde les données persistantes (un fichier par joueur)."""
        for username, pdata in self.player_data.items():
            safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in username)
            fpath = DATA_DIR / f"{safe_name}.json"
            try:
                fpath.write_text(json.dumps(pdata, indent=2, ensure_ascii=False))
            except Exception as e:
                logging.error(f"Erreur sauvegarde {username}: {e}")

    def _save_player(self, username):
        """Sauvegarde un seul joueur."""
        if username not in self.player_data:
            return
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in username)
        fpath = DATA_DIR / f"{safe_name}.json"
        try:
            fpath.write_text(json.dumps(self.player_data[username], indent=2, ensure_ascii=False))
        except Exception as e:
            logging.error(f"Erreur sauvegarde {username}: {e}")

    @staticmethod
    def _verify_password(password, salt, stored_hash):
        """Vérifie un mot de passe contre le hash stocké."""
        return hashlib.sha256((salt + password).encode()).hexdigest() == stored_hash

    # === SERVER MISSION GENERATION ===

    def _generate_missions(self, count=1):
        """Génère des missions côté serveur."""
        for _ in range(count):
            if len([m for m in self.server_missions if m.get('status') == 'available']) >= MAX_SERVER_MISSIONS:
                break
            attempts = 0
            generated = False
            while attempts < 20 and not generated:
                attempts += 1
                profile = self._pick_target_vehicle_profile()
                reward_factor = self._server_vehicle_reward_factor(profile)

                weights = self._compute_server_mission_weights(profile)
                mission_type = random.choices(
                    ['standard', 'express', 'chain'],
                    weights=[weights['standard'], weights['express'], weights['chain']],
                    k=1,
                )[0]

                locations = random.sample(SERVER_LOCATIONS, 2)
                pickup = dict(locations[0])
                delivery = dict(locations[1])

                dist = math.hypot(delivery['x'] - pickup['x'], delivery['y'] - pickup['y'])
                dist_factor = max(0.5, dist / 4000.0)
                requirements = self._build_server_mission_requirements(mission_type, dist_factor, profile)

                if not self._is_server_vehicle_eligible(requirements, (profile['model'], profile['color'])):
                    continue

                cargo = self._assign_server_cargo(mission_type, requirements)
                cargo_weight = float(cargo.get('cargo_weight', 0.0) or 0.0)
                if cargo_weight > float(requirements.get('min_capacity', 0.0) or 0.0):
                    requirements['min_capacity'] = int(math.ceil(cargo_weight))
                    requirements = self._fit_requirements_to_profile(requirements, profile)

                stops = self._build_server_stops(mission_type, pickup, delivery)

                # Les missions partagées sont déclenchées via le système de party (leader only).
                is_coop = False
                required_roles = self._default_required_roles(mission_type) if is_coop else []

                if mission_type == 'express':
                    reward = int(random.uniform(200, 500) * dist_factor * reward_factor)
                    time_limit = random.uniform(45, 90) * max(0.7, dist_factor)
                elif mission_type == 'chain':
                    reward = int(random.uniform(150, 350) * dist_factor * reward_factor)
                    time_limit = random.uniform(90, 150) * max(0.7, dist_factor)
                else:
                    reward = int(random.uniform(100, 250) * dist_factor * reward_factor)
                    time_limit = random.uniform(120, 240) * max(0.7, dist_factor)

                risky_base = float(SERVER_RISKY_TYPE_BASE_CHANCE.get(mission_type, 0.3))
                risk_level = 'risky' if random.random() < min(0.85, max(0.1, risky_base)) else 'chill'
                if risk_level == 'risky':
                    reward = int(reward * 1.24)
                    time_limit = max(35.0, time_limit * 0.86)

                base_reward = int(reward)

                self._mission_counter += 1
                mission = {
                    'id': self._mission_counter,
                    'type': mission_type,
                    'pickup': pickup,
                    'delivery': delivery,
                    'reward': base_reward,
                    'base_reward': base_reward,
                    'time_limit': int(time_limit),
                    'status': 'available',
                    'coop': is_coop,
                    'required_players': 2 if is_coop else 1,
                    'required_roles': required_roles,
                    'participant_roles': {},
                    'mission_ready': not is_coop,
                    'party_mission': False,
                    'party_bonus_multiplier': 1.0,
                    'requirements': requirements,
                    'cargo_type': str(cargo.get('cargo_type', 'colis')),
                    'cargo_icon': str(cargo.get('cargo_icon', 'PKG')),
                    'cargo_weight': float(cargo.get('cargo_weight', 0.0)),
                    'stops': stops,
                    'current_stop_index': 0,
                    'risk_level': risk_level,
                }
                self.server_missions.append(mission)
                generated = True

    def _tick_missions(self):
        """Met à jour les missions serveur (régénération)."""
        now = time.time()
        if now - self._last_mission_gen >= MISSION_GEN_INTERVAL:
            self._last_mission_gen = now
            # Supprimer les missions expirées
            self.server_missions = [m for m in self.server_missions if m.get('status') in ('available', 'active')]
            self._generate_missions(2)
            # Broadcast la liste mise à jour
            self._broadcast_missions()

    def _broadcast_missions(self):
        """Envoie la liste des missions à tous les clients."""
        available = [m for m in self.server_missions if m.get('status') == 'available']
        packet = json.dumps({'type': 'mission_list', 'missions': available}).encode()
        for uname, data in list(self.clients.items()):
            try:
                self.server_socket.sendto(packet, data['addr'])
            except Exception:
                pass

    def run(self):
        """
        Boucle principale du serveur - traite les connexions et les données
        Gère les nouveaux clients, les déconnexions et la diffusion des positions
        """
        logging.info("En attente de connexions clients...")
        try:
            while True:
                self.handle_incoming_data()
                self.check_disconnections()
                self._tick_server_ai()
                self.broadcast_positions()
                self._tick_missions()
                self._tick_party_challenges()
                time.sleep(TICK_SLEEP)
        except KeyboardInterrupt:
            logging.info("Arrêt du serveur...")
        finally:
            self.server_socket.close()  # Fermeture propre du socket


def main():
    """Fonction principale - crée et lance le serveur"""
    server = DeliveryRushServer()
    server.run()


# Point d'entrée du programme serveur
if __name__ == "__main__":
    main()