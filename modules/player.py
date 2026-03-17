"""
Module joueur pour Delivery Rush
Gère la physique, l'animation et le rendu du véhicule du joueur.
Inclut le système de drift, frein à main, contrôles refondus et catalogue de véhicules.
"""

import math
from pathlib import Path
import pygame

# === CONSTANTES DU JOUEUR === (30px = 1 metre)
PLAYER_START_X = 6000
PLAYER_START_Y = 6000
PLAYER_SIZE = 134
HITBOX_SCALE = 0.175

# === PHYSIQUE PAR DÉFAUT ===
DEFAULT_MAX_SPEED = 1300.0
DEFAULT_ACCEL = 465.0
DEFAULT_BRAKE = 500.0
DEFAULT_DRAG = 300.0
DEFAULT_TURN_SPEED = 300.0
DEFAULT_GRIP = 8.0

# === CONSTANTES DE GAMEPLAY ===
START_BOOST_SPEED = 240.0
START_ACCEL_BOOST = 0.8
REVERSE_DELAY = 0.3          # Réduit de 1.5 à 0.3 pour réactivité
STOP_THRESHOLD = 8.0
BURNOUT_TURN_SPEED = 180.0   # Rotation sur place (frein à main)

# === PHYSIQUE DU DRIFT ===
TIRE_GRIP_OFFROAD_MULT = 0.55
TIRE_GRIP_HANDBRAKE_MULT = 0.22
OFFROAD_DRAG_MULT = 1.4      # Réduit de 2.0 pour permettre marche arrière
OFFROAD_SPEED_MULT = 0.65
COLLISION_BOUNCE = -0.3
COLLISION_SPEED_LOSS = 0.5

# === DRIFT TRAIL ===
DRIFT_PARTICLE_THRESHOLD = 120.0
MAX_DRIFT_TRAIL = 600
DRIFT_TRAIL_FADE = 0.4

# === CATALOGUE DE VÉHICULES ===
VEHICLE_CATALOG = {
    "MICRO":        {"price": 0,     "max_speed": 800,  "accel": 380, "handling": 1.3,  "brake": 450, "grip": 7.5, "mass": 0.7,  "desc": "Citadine économique"},
    "HATCHBACK":    {"price": 800,   "max_speed": 950,  "accel": 420, "handling": 1.15, "brake": 480, "grip": 8.0, "mass": 0.85, "desc": "Polyvalente et fiable"},
    "SEDAN":        {"price": 1500,  "max_speed": 1050, "accel": 440, "handling": 1.0,  "brake": 500, "grip": 8.0, "mass": 1.0,  "desc": "Berline confortable"},
    "CIVIC":        {"price": 2000,  "max_speed": 1100, "accel": 460, "handling": 1.1,  "brake": 520, "grip": 8.5, "mass": 0.9,  "desc": "Compacte sportive"},
    "COUPE":        {"price": 3000,  "max_speed": 1200, "accel": 500, "handling": 1.05, "brake": 550, "grip": 8.5, "mass": 0.95, "desc": "Coupé élégant"},
    "WAGON":        {"price": 2500,  "max_speed": 1000, "accel": 430, "handling": 0.95, "brake": 490, "grip": 7.5, "mass": 1.1,  "desc": "Break spacieux"},
    "MINIVAN":      {"price": 3500,  "max_speed": 900,  "accel": 400, "handling": 0.85, "brake": 470, "grip": 7.0, "mass": 1.3,  "desc": "Monospace familial"},
    "SUV":          {"price": 4000,  "max_speed": 1050, "accel": 450, "handling": 0.9,  "brake": 510, "grip": 9.0, "mass": 1.4,  "desc": "Tout-terrain robuste"},
    "JEEP":         {"price": 5000,  "max_speed": 950,  "accel": 430, "handling": 0.85, "brake": 490, "grip": 9.5, "mass": 1.5,  "desc": "4x4 aventurier"},
    "PICKUP":       {"price": 4500,  "max_speed": 1000, "accel": 440, "handling": 0.8,  "brake": 480, "grip": 8.5, "mass": 1.5,  "desc": "Pick-up puissant"},
    "MUSCLECAR":    {"price": 6000,  "max_speed": 1350, "accel": 520, "handling": 0.85, "brake": 530, "grip": 7.0, "mass": 1.2,  "desc": "Muscle car américaine"},
    "SPORT":        {"price": 8000,  "max_speed": 1400, "accel": 550, "handling": 1.15, "brake": 580, "grip": 9.0, "mass": 0.9,  "desc": "Voiture de sport"},
    "LUXURY":       {"price": 10000, "max_speed": 1300, "accel": 500, "handling": 1.0,  "brake": 560, "grip": 8.5, "mass": 1.1,  "desc": "Luxe et performance"},
    "SUPERCAR":     {"price": 15000, "max_speed": 1500, "accel": 600, "handling": 1.2,  "brake": 620, "grip": 9.5, "mass": 0.85, "desc": "Supercar ultime"},
    "VAN":          {"price": 3000,  "max_speed": 850,  "accel": 380, "handling": 0.75, "brake": 440, "grip": 7.0, "mass": 1.6,  "desc": "Utilitaire spacieux"},
    "BOX TRUCK":    {"price": 5000,  "max_speed": 750,  "accel": 350, "handling": 0.65, "brake": 420, "grip": 6.5, "mass": 2.0,  "desc": "Camion de livraison"},
    "MEDIUM TRUCK": {"price": 7000,  "max_speed": 700,  "accel": 330, "handling": 0.6,  "brake": 400, "grip": 6.0, "mass": 2.5,  "desc": "Poids lourd"},
}

VEHICLE_COLORS = ["Black", "Blue", "Brown", "Green", "Magenta", "Red", "White", "Yellow"]

def resolve_car_frame_path(model: str, color: str, idx: int) -> str:
    """Résout un chemin d'image de frame pour une voiture en essayant plusieurs variantes de dossier."""
    car_name = model.replace(' ', '').upper()
    base_candidates = [
        model,
        model.replace(' ', ''),
    ]
    base_candidates = [c for c in base_candidates if c]
    for base in base_candidates:
        path = Path("assets/images/cars") / base / color / "SEPARATED" / f"{color}_{car_name}_CLEAN_All_{idx:03d}.png"
        if path.exists():
            return str(path)
    # Fallback to original structure
    return str(Path("assets/images/cars") / model / color / "SEPARATED" / f"{color}_{car_name}_CLEAN_All_{idx:03d}.png")


class Player:
    def __init__(self, car=('SUPERCAR', 'Black'), world_size=(12000, 12000)):
        self.x = PLAYER_START_X
        self.y = PLAYER_START_Y
        self.vx = 0.0
        self.vy = 0.0
        self.angle = 0.0  # 0 deg direction est
        self.size = PLAYER_SIZE
        self.hitbox_scale = HITBOX_SCALE
        self.car = car # (modèle, couleur)
        self.world_width, self.world_height = world_size # Taille du monde pour les limites
        self.frames = self._load_frames(car)
        self.reverse_wait = 0.0
        self.speed_px_s = 0.0
        self.speed_kmh = 0.0
        # État du drift et du frein à main
        self.handbrake = False
        self.on_road = True
        self.drift_angle = 0.0
        self.lateral_speed = 0.0
        # Charger les stats du véhicule depuis le catalogue
        stats = VEHICLE_CATALOG.get(car[0], {})
        self.max_speed = stats.get('max_speed', DEFAULT_MAX_SPEED)
        self.rev_speed = min(400.0, self.max_speed * 0.3)
        self.accel = stats.get('accel', DEFAULT_ACCEL)
        self.reverse_accel = self.accel * 1.8
        self.brake = stats.get('brake', DEFAULT_BRAKE)
        self.turn_speed = DEFAULT_TURN_SPEED * stats.get('handling', 1.0)
        self.grip = stats.get('grip', DEFAULT_GRIP)
        self.drag = DEFAULT_DRAG
        self.distance_traveled = 0.0  # pixels parcourus
        self.drift_trail = []  # [(world_x, world_y, life)]

    def _load_frames(self, car):
        """Loaf les frames de la voiture en fonction du modèle et de la couleur."""
        model = car[0]
        color = car[1]
        car_name = model.replace(' ', '').upper()
        frames = []
        for idx in range(48):
            path = resolve_car_frame_path(model, color, idx)
            img = pygame.image.load(path).convert_alpha()
            img = pygame.transform.scale(img, (self.size, self.size))
            frames.append(img)
        return frames

    def update(self, keys, dt, other_rects=None, game_map=None):
        """Met à jour la physique avec drift, frein à main, collisions carte et véhicules."""
        if other_rects is None:
            other_rects = []

        # === ENTRÉES (ZQSD seulement) ===
        turn_dir = 0.0
        if keys[pygame.K_q]:
            turn_dir -= 1.0
        if keys[pygame.K_d]:
            turn_dir += 1.0

        forward_input = keys[pygame.K_z]
        reverse_input = keys[pygame.K_s]
        self.handbrake = keys[pygame.K_SPACE]

        # === DÉTECTION DE SURFACE ===
        if game_map:
            center_x = self.x + self.size / 2
            center_y = self.y + self.size / 2
            self.on_road = game_map.is_road_at(center_x, center_y)

        # === VITESSE ET DIRECTION ACTUELLE ===
        speed = math.hypot(self.vx, self.vy)
        rad = math.radians(self.angle)
        cos_a, sin_a = math.cos(rad), math.sin(rad)
        forward_vel = self.vx * cos_a + self.vy * sin_a

        # === ROTATION (dépendante de la vitesse - réaliste) ===
        if speed > 5.0:
            speed_ratio = min(1.0, speed / self.max_speed)
            # Inverse: facile à basse vitesse, dur à haute vitesse
            steer_factor = 1.0 / (1.0 + 4.0 * speed_ratio)
            # Reduce turn rate at very low speeds to prevent 360 spins
            low_speed_limit = min(1.0, speed / 200.0)
            steer_factor *= max(0.15, low_speed_limit)
            effective_turn = -turn_dir if forward_vel < 0 else turn_dir
            self.angle += effective_turn * self.turn_speed * steer_factor * dt
        elif self.handbrake and turn_dir != 0:
            # DRIFT SUR PLACE (burnout) - rotation même à l'arrêt
            self.angle += turn_dir * BURNOUT_TURN_SPEED * dt

        # === BOOST D'ACCÉLÉRATION AU DÉMARRAGE ===
        boost_factor = 1.0
        if speed < START_BOOST_SPEED:
            boost_factor += START_ACCEL_BOOST * (1.0 - min(1.0, speed / START_BOOST_SPEED))

        # === ACCÉLÉRATION / FREINAGE / MARCHE ARRIÈRE ===
        if forward_input:
            accel = self.accel * boost_factor
            self.reverse_wait = 0.0
        elif reverse_input:
            if forward_vel > STOP_THRESHOLD:
                # En mouvement vers l'avant → frein
                accel = -self.brake
                self.reverse_wait = 0.0
            elif abs(forward_vel) <= STOP_THRESHOLD:
                # À l'arrêt ou quasi-arrêt
                self.reverse_wait += dt
                if self.reverse_wait >= REVERSE_DELAY:
                    accel = -self.reverse_accel
                else:
                    # Frein léger pendant l'attente (réduit pour ne pas combattre la traînée)
                    accel = -self.brake * 0.15
            else:
                # Déjà en marche arrière
                accel = -self.reverse_accel
        else:
            accel = 0.0
            self.reverse_wait = 0.0

        # Appliquer l'accélération selon la direction actuelle
        rad = math.radians(self.angle)
        cos_a, sin_a = math.cos(rad), math.sin(rad)
        if accel != 0.0:
            self.vx += cos_a * accel * dt
            self.vy += sin_a * accel * dt

        # === SYSTÈME DE DRIFT (adhérence latérale) ===
        speed = math.hypot(self.vx, self.vy)
        if speed > 1.0:
            forward_vel = self.vx * cos_a + self.vy * sin_a
            lateral_vel = -self.vx * sin_a + self.vy * cos_a

            # Grip basé sur les stats du véhicule
            base_grip = self.grip
            if self.handbrake:
                grip = base_grip * TIRE_GRIP_HANDBRAKE_MULT
            elif not self.on_road:
                grip = base_grip * TIRE_GRIP_OFFROAD_MULT
            else:
                grip = base_grip

            # Survirage haute vitesse : perte d'adhérence en virage à grande vitesse
            speed_ratio = min(1.0, speed / self.max_speed)
            if abs(turn_dir) > 0.1 and speed_ratio > 0.4:
                oversteer_factor = 1.0 - 0.4 * min(1.0, (speed_ratio - 0.4) / 0.6)
                grip *= oversteer_factor

            grip_reduction = max(0.0, 1.0 - grip * dt)
            lateral_vel *= grip_reduction

            self.lateral_speed = abs(lateral_vel)
            self.drift_angle = math.degrees(math.atan2(lateral_vel, max(1.0, abs(forward_vel))))

            self.vx = forward_vel * cos_a - lateral_vel * sin_a
            self.vy = forward_vel * sin_a + lateral_vel * cos_a

            # Particules de dérapage quand survirage
            if self.lateral_speed > DRIFT_PARTICLE_THRESHOLD:
                cx_ = self.x + self.size / 2
                cy_ = self.y + self.size / 2
                rear_dist = self.size * 0.061
                wheel_spread = self.size * 0.07
                rear_x = cx_ - cos_a * rear_dist
                rear_y = cy_ - sin_a * rear_dist
                lw_x = rear_x + sin_a * wheel_spread
                lw_y = rear_y - cos_a * wheel_spread
                rw_x = rear_x - sin_a * wheel_spread
                rw_y = rear_y + cos_a * wheel_spread
                self.drift_trail.append([lw_x, lw_y, rw_x, rw_y, 1.0])
                if len(self.drift_trail) > MAX_DRIFT_TRAIL:
                    self.drift_trail = self.drift_trail[-MAX_DRIFT_TRAIL:]
        else:
            self.lateral_speed = 0.0
            self.drift_angle = 0.0

        # Vieillir les traces de dérapage
        for p in self.drift_trail:
            p[-1] -= DRIFT_TRAIL_FADE * dt
        self.drift_trail = [p for p in self.drift_trail if p[-1] > 0.0]

        # === RÉSISTANCE DE L'AIR (traînée) ===
        speed = math.hypot(self.vx, self.vy)
        if speed > 0:
            drag_mult = OFFROAD_DRAG_MULT if not self.on_road else 1.0
            drag_mag = self.drag * drag_mult * dt
            new_speed = max(0.0, speed - drag_mag)
            if new_speed == 0:
                self.vx = self.vy = 0.0
            else:
                scale = new_speed / speed
                self.vx *= scale
                self.vy *= scale

        # === LIMITER LA VITESSE MAXIMALE ===
        speed = math.hypot(self.vx, self.vy)
        if speed > 0.0:
            rad = math.radians(self.angle)
            forward_vel = self.vx * math.cos(rad) + self.vy * math.sin(rad)
            base_limit = self.max_speed if forward_vel >= 0 else self.rev_speed
            speed_mult = OFFROAD_SPEED_MULT if not self.on_road else 1.0
            limit = base_limit * speed_mult
            if speed > limit:
                scale = limit / speed
                self.vx *= scale
                self.vy *= scale
                speed = limit

        # Vitesse pour l'overlay
        self.speed_px_s = math.hypot(self.vx, self.vy)
        self.speed_kmh = self.speed_px_s * 0.12

        # Accumulation distance (30px = 1m)
        displacement = self.speed_px_s * dt
        self.distance_traveled += displacement

        # === INTÉGRER LA POSITION ===
        self.x += self.vx * dt
        self.y += self.vy * dt

        # === COLLISIONS AVEC LA CARTE (bâtiments/murs) ===
        if game_map:
            hitbox = self.get_hitbox_rect()
            map_collisions = game_map.check_rect_collision(hitbox)
            for tile_rect in map_collisions:
                overlap = hitbox.clip(tile_rect)
                if overlap.width <= 0 or overlap.height <= 0:
                    continue
                if overlap.width < overlap.height:
                    if hitbox.centerx < tile_rect.centerx:
                        self.x -= overlap.width
                    else:
                        self.x += overlap.width
                    self.vx *= COLLISION_BOUNCE
                    self.vy *= COLLISION_SPEED_LOSS
                else:
                    if hitbox.centery < tile_rect.centery:
                        self.y -= overlap.height
                    else:
                        self.y += overlap.height
                    self.vy *= COLLISION_BOUNCE
                    self.vx *= COLLISION_SPEED_LOSS
                hitbox = self.get_hitbox_rect()

        # === LIMITES DU MONDE ===
        min_x, min_y = 0, 0
        max_x = max(0, self.world_width - self.size)
        max_y = max(0, self.world_height - self.size)

        if self.x < min_x:
            self.x = min_x
            if self.vx < 0:
                self.vx = 0.0
        elif self.x > max_x:
            self.x = max_x
            if self.vx > 0:
                self.vx = 0.0

        if self.y < min_y:
            self.y = min_y
            if self.vy < 0:
                self.vy = 0.0
        elif self.y > max_y:
            self.y = max_y
            if self.vy > 0:
                self.vy = 0.0

        # === COLLISION AVEC D'AUTRES VOITURES ===
        rect = self.get_hitbox_rect()
        for other in other_rects:
            if other.width < 2 or other.height < 2:
                continue
            if rect.colliderect(other):
                overlap = rect.clip(other)
                if overlap.width < overlap.height:
                    if self.vx > 0:
                        self.x -= overlap.width + 1
                    else:
                        self.x += overlap.width + 1
                    self.vx *= -0.25
                else:
                    if self.vy > 0:
                        self.y -= overlap.height + 1
                    else:
                        self.y += overlap.height + 1
                    self.vy *= -0.25
                rect = self.get_hitbox_rect()


    def render(self, screen, camera_x, camera_y, zoom=1.0):
        """Afficher le joueur avec la frame directionnelle (taille fixe, centré sur position zoomée)."""
        # Centre du joueur en monde → centre en écran
        cx = (self.x + self.size / 2 - camera_x) * zoom
        cy = (self.y + self.size / 2 - camera_y) * zoom
        frame = self._current_frame()
        # Sprite à taille fixe (pas de scale par zoom), centré sur la position zoomée
        screen.blit(frame, (int(cx - frame.get_width() / 2), int(cy - frame.get_height() / 2)))

    def _current_frame(self):
        idx = int((self.angle % 360) / 7.5) % 48
        return self.frames[idx]

    def get_rect(self):
        return pygame.Rect(int(self.x), int(self.y), self.size, self.size)

    def get_hitbox_rect(self):
        hit_size = max(2, int(self.size * self.hitbox_scale))
        offset = (self.size - hit_size) / 2
        return pygame.Rect(int(self.x + offset), int(self.y + offset), hit_size, hit_size)

    def get_position(self):
        return self.x, self.y

    def change_car(self, new_car):
        """Change le véhicule du joueur (recharge les frames et stats)."""
        self.car = new_car
        self.frames = self._load_frames(new_car)
        stats = VEHICLE_CATALOG.get(new_car[0], {})
        self.max_speed = stats.get('max_speed', DEFAULT_MAX_SPEED)
        self.rev_speed = min(400.0, self.max_speed * 0.3)
        self.accel = stats.get('accel', DEFAULT_ACCEL)
        self.reverse_accel = self.accel * 1.8
        self.brake = stats.get('brake', DEFAULT_BRAKE)
        self.turn_speed = DEFAULT_TURN_SPEED * stats.get('handling', 1.0)
        self.grip = stats.get('grip', DEFAULT_GRIP)
        self.drag = DEFAULT_DRAG