"""
Module joueur pour Delivery Rush
Gère la physique, l'animation et le rendu du véhicule du joueur.
"""

import math
import os
from pathlib import Path
import pygame

# === CONSTANTES DU JOUEUR ===
PLAYER_START_X = 6000  # Position X de départ (centre de la carte)
PLAYER_START_Y = 6000  # Position Y de départ (centre de la carte)
PLAYER_SIZE = 120      # Taille du sprite du joueur en pixels
HITBOX_SCALE = 0.65    # Échelle de la hitbox (65% de la taille du sprite)

# === PHYSIQUE DES MOUVEMENTS ===
MAX_SPEED = 450.0  # Vitesse maximale en px/s (≈160 km/h)
ACCEL = 550.0      # Accélération en px/s² (≈2.0 g)
BRAKE = 800.0      # Décélération en px/s² (≈3.0 g)
DRAG = 250.0       # Résistance de l'air/frottements en px/s²
TURN_SPEED = 160.0 # Vitesse de rotation maximale en deg/s

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
        self.car = car
        self.world_width, self.world_height = world_size
        self.frames = self._load_frames(car)

    def _load_frames(self, car):
        """Loaf les frames de la voiture en fonction du modèle et de la couleur."""
        model = car[0]
        color = car[1]
        car_name = model.replace(' ', '').upper()
        frames = []
        for idx in range(48):
            path = resolve_car_frame_path(model, color, idx)
            img = pygame.image.load(path)
            img = pygame.transform.scale(img, (self.size, self.size))
            frames.append(img)
        return frames

    def update(self, keys, dt, other_rects=None):
        """Met à jour la physique avec accélération/freinage/rotation et collision basique."""
        if other_rects is None:
            other_rects = []

        # Direction
        turn_dir = 0.0
        if keys[pygame.K_LEFT] or keys[pygame.K_q]:
            turn_dir -= 1.0
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            turn_dir += 1.0

        # Accélération / freinage
        accel = 0.0
        if keys[pygame.K_UP] or keys[pygame.K_z]:
            accel += ACCEL
        if keys[pygame.K_DOWN] or keys[pygame.K_s]:
            accel -= BRAKE

        # Appliquer la direction ajustée par la vitesse
        speed = math.hypot(self.vx, self.vy)
        if speed > 0.5:
            steer_factor = min(1.0, speed / MAX_SPEED)
            # compute forward velocity along car facing to detect reverse motion
            rad = math.radians(self.angle)
            forward_vel = self.vx * math.cos(rad) + self.vy * math.sin(rad)
            effective_turn = -turn_dir if forward_vel < 0 else turn_dir
            self.angle += effective_turn * TURN_SPEED * steer_factor * dt

        # Appliquer l'accélération selon la direction actuelle
        rad = math.radians(self.angle)
        if accel != 0.0:
            self.vx += math.cos(rad) * accel * dt
            self.vy += math.sin(rad) * accel * dt

        # Résistance de l'air (adhérence de la route)
        if speed > 0:
            drag_mag = DRAG * dt
            new_speed = max(0.0, speed - drag_mag)
            if new_speed == 0:
                self.vx = self.vy = 0.0
            else:
                scale = new_speed / speed
                self.vx *= scale
                self.vy *= scale

        # Limiter la vitesse maximale
        speed = math.hypot(self.vx, self.vy)
        if speed > MAX_SPEED:
            scale = MAX_SPEED / speed
            self.vx *= scale
            self.vy *= scale

        # Intégrer la position
        prev_x, prev_y = self.x, self.y
        self.x += self.vx * dt
        self.y += self.vy * dt

        # Garder le joueur dans les limites du monde (ne bloquer que si on pousse vers l'extérieur)
        min_x = 0
        min_y = 0
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

        # Collision avec d'autres voitures ; ignorer les rects vides
        rect = self.get_hitbox_rect()
        for other in other_rects:
            if other.width < 2 or other.height < 2:
                continue
            if rect.colliderect(other):
                overlap = rect.clip(other)
                # séparer selon l'axe d'overlap le plus petit
                if overlap.width < overlap.height:
                    if self.vx > 0:
                        self.x -= overlap.width + 1
                    else:
                        self.x += overlap.width + 1
                    # réduire la composante de vitesse sur l'axe x (rebond amorti)
                    self.vx *= -0.25
                else:
                    if self.vy > 0:
                        self.y -= overlap.height + 1
                    else:
                        self.y += overlap.height + 1
                    self.vy *= -0.25
                rect = self.get_hitbox_rect()


    def render(self, screen, camera_x, camera_y):
        """Afficher le joueur avec la frame directionnelle."""
        screen_x = self.x - camera_x
        screen_y = self.y - camera_y
        frame = self._current_frame()
        screen.blit(frame, (int(screen_x), int(screen_y)))

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