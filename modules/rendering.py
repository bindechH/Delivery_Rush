"""
Module de rendu pour Delivery Rush
Gère l'affichage des éléments graphiques : joueur, autres joueurs, interface utilisateur.
Fournit des fonctions utilitaires pour le texte et les sprites.
"""

import math
import random
import pygame
from pathlib import Path
from .player import Player, resolve_car_frame_path, VEHICLE_CATALOG, VEHICLE_COLORS
from .map import GameMap

# États du jeu (pour compatibilité)
MENU = 0
GAME = 1

def draw_text_bg(screen, text, font, color, x, y, bg=(0, 0, 0, 160), padding=4):
    """
    Affiche du texte avec un arrière-plan semi-transparent
    Utile pour les labels et informations en jeu
    """
    text_surface = font.render(text, True, color)
    bg_rect = text_surface.get_rect(topleft=(x, y)).inflate(padding * 2, padding * 2)
    box = pygame.Surface(bg_rect.size, pygame.SRCALPHA)
    box.fill(bg)
    screen.blit(box, bg_rect)
    screen.blit(text_surface, (bg_rect.x + padding, bg_rect.y + padding))

def draw_text_bg_center(screen, text, font, color, center_x, top_y, bg=(0, 0, 0, 160), padding=4):
    """
    Affiche du texte centré horizontalement avec arrière-plan semi-transparent
    Idéal pour les titres et messages centrés
    """
    text_surface = font.render(text, True, color)
    text_rect = text_surface.get_rect(midtop=(center_x, top_y))
    bg_rect = text_rect.inflate(padding * 2, padding * 2)
    box = pygame.Surface(bg_rect.size, pygame.SRCALPHA)
    box.fill(bg)
    screen.blit(box, bg_rect)
    screen.blit(text_surface, (bg_rect.x + padding, bg_rect.y + padding))


# Afficher du texte sans arrière-plan
def draw_text(screen, text, font, color, x, y):
    draw_text_bg(screen, text, font, color, x, y)


# ──────────────────────────────────────────────────
#  PASSING CARS for main menu background animation
# ──────────────────────────────────────────────────
class _PassingCar:
    """A single car that drives across the menu background."""
    def __init__(self, screen_w, screen_h):
        self.screen_w = screen_w
        self.screen_h = screen_h
        model = random.choice(list(VEHICLE_CATALOG.keys()))
        color = random.choice(VEHICLE_COLORS)
        self.car = (model, color)
        self.size = 80
        self.direction = random.randint(0, 1)
        self.speed = random.uniform(120, 300)
        self.y = random.randint(int(screen_h * 0.55), int(screen_h * 0.88))
        # East=0, West=24 in the 48-frame system
        self.frame_idx = 0 if self.direction == 0 else 24
        if self.direction == 0:
            self.x = float(-self.size - random.randint(0, 200))
        else:
            self.x = float(screen_w + random.randint(0, 200))
        self._load_frame()

    def _load_frame(self):
        try:
            path = resolve_car_frame_path(self.car[0], self.car[1], self.frame_idx)
            img = pygame.image.load(path).convert_alpha()
            self.image = pygame.transform.smoothscale(img, (self.size, self.size))
        except Exception:
            self.image = pygame.Surface((self.size, self.size), pygame.SRCALPHA)
            self.image.fill((100, 100, 100, 150))

    def update(self, dt):
        if self.direction == 0:
            self.x += self.speed * dt
        else:
            self.x -= self.speed * dt

    def off_screen(self):
        if self.direction == 0:
            return self.x > self.screen_w + 50
        return self.x < -self.size - 50

    def draw(self, screen):
        screen.blit(self.image, (int(self.x), int(self.y)))


class MainMenu:
    def __init__(self, screen, font, small_font, screen_width, screen_height, server_ip='localhost', username='', car=('SUV', 'Black'), sound_manager=None, fullscreen=False, map_zoom=2.0):
        self.screen = screen
        self.font = font
        self.small_font = small_font or pygame.font.Font("assets/fonts/ari-w9500-bold.ttf", 32)
        self.name_font = pygame.font.Font("assets/fonts/ari-w9500-bold.ttf", 24)
        for fnt in (self.small_font, self.name_font):
            fnt.set_bold(True)
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.server_ip = server_ip
        self.username = username
        self.car = car
        self.sound_manager = sound_manager
        self.volume_levels = [0.0, 0.1, 0.25, 0.5, 0.75, 1.0]
        self.volume_idx = 2
        self.logo = pygame.image.load('assets/images/HUD/Delivery Rush.png').convert_alpha()
        self._bg_raw = pygame.image.load('assets/images/HUD/backround.png').convert()
        self.background = pygame.transform.scale(self._bg_raw, (self.screen_width, self.screen_height))
        self.show_error = False
        self.error_message = ""
        self.error_frame_counter = 0
        self.btn_image = pygame.image.load('assets/images/HUD/SOLOBTN.png').convert_alpha()
        self.btn_image_multi = pygame.image.load('assets/images/HUD/multibtn.png').convert_alpha()
        self.btn_image_quit = pygame.image.load('assets/images/HUD/quitbtn.png').convert_alpha()

        # Passing cars animation
        self._passing_cars = []
        self._car_spawn_timer = 0.0
        self._car_spawn_interval = 1.2

        # Settings state
        self.settings_open = False
        self.cfg_server_ip = server_ip
        self.cfg_server_port = "12345"
        self.cfg_fps = "60"
        self.cfg_resolution = f"{screen_width}x{screen_height}"
        self.cfg_fullscreen = fullscreen
        self.cfg_map_zoom = str(map_zoom)
        self.settings_fields = ["server_ip", "server_port", "fps", "resolution", "fullscreen", "volume", "map_zoom"]
        self.settings_active_field = 0

        # Auth state (multi) - username from config, only password needed
        self.auth_open = False
        self.auth_username = username
        self.auth_password = ""
        self.auth_active_field = 0
        self.auth_error = ""

    def resize(self, w, h):
        self.screen_width = w
        self.screen_height = h
        self.background = pygame.transform.scale(self._bg_raw, (w, h))

    # ─── SETTINGS helpers ─────────────────────────────
    def _get_settings_value(self, idx):
        mapping = [self.cfg_server_ip, self.cfg_server_port, self.cfg_fps, self.cfg_resolution,
                    "ON" if self.cfg_fullscreen else "OFF",
                    f"{int(self.volume_levels[self.volume_idx]*100)}%",
                    self.cfg_map_zoom]
        return mapping[idx]

    def _set_settings_value(self, idx, val):
        if idx == 0: self.cfg_server_ip = val
        elif idx == 1: self.cfg_server_port = val
        elif idx == 2: self.cfg_fps = val
        elif idx == 3: self.cfg_resolution = val
        elif idx == 4: self.cfg_fullscreen = not self.cfg_fullscreen
        elif idx == 5:
            self.volume_idx = (self.volume_idx + 1) % len(self.volume_levels)
            if self.sound_manager:
                self.sound_manager.set_music_volume(self.volume_levels[self.volume_idx])
        elif idx == 6: self.cfg_map_zoom = val

    def _settings_labels(self):
        return ["IP Serveur", "Port", "FPS", "Resolution", "Fullscreen", "Volume", "Map Zoom"]

    def get_settings_dict(self):
        parts = self.cfg_resolution.split("x")
        try:
            res = [int(parts[0]), int(parts[1])]
        except Exception:
            res = [self.screen_width, self.screen_height]
        try:
            fps = int(self.cfg_fps)
        except Exception:
            fps = 60
        try:
            port = int(self.cfg_server_port)
        except Exception:
            port = 12345
        try:
            map_zoom = float(self.cfg_map_zoom)
        except Exception:
            map_zoom = 2.0
        return {
            "server_ip": self.cfg_server_ip,
            "server_port": port,
            "fps": fps,
            "resolution": res,
            "fullscreen": self.cfg_fullscreen,
            "map_zoom": map_zoom,
        }

    # ─── DISPLAY ─────────────────────────────────────
    def display_menu(self, dt=0.016):
        sw, sh = self.screen_width, self.screen_height
        self.screen.blit(self.background, (0, 0))

        # Update & draw passing cars
        self._car_spawn_timer += dt
        if self._car_spawn_timer >= self._car_spawn_interval:
            self._car_spawn_timer = 0.0
            self._passing_cars.append(_PassingCar(sw, sh))
        for c in self._passing_cars:
            c.update(dt)
            c.draw(self.screen)
        self._passing_cars = [c for c in self._passing_cars if not c.off_screen()]

        cx = sw // 2

        # If settings open
        if self.settings_open:
            return self._display_settings(cx, sh)

        # If auth open
        if self.auth_open:
            return self._display_auth(cx, sh)

        # Logo centered
        if self.logo:
            logo_rect = self.logo.get_rect(center=(cx, int(sh * 0.2)))
            self.screen.blit(self.logo, logo_rect)

        # Buttons centered
        btn_y_start = int(sh * 0.38)
        btn_gap = 75
        solo_rect = self.btn_image.get_rect(center=(cx, btn_y_start))
        self.screen.blit(self.btn_image, solo_rect)

        multi_rect = self.btn_image_multi.get_rect(center=(cx, btn_y_start + btn_gap))
        self.screen.blit(self.btn_image_multi, multi_rect)

        # Settings gear icon next to multi button
        settings_size = 40
        settings_rect = pygame.Rect(multi_rect.right + 10, multi_rect.centery - settings_size // 2, settings_size, settings_size)
        pygame.draw.rect(self.screen, (50, 50, 70), settings_rect, border_radius=8)
        pygame.draw.rect(self.screen, (120, 120, 150), settings_rect, 2, border_radius=8)
        gear_font = pygame.font.SysFont("Segoe UI Symbol", 22)
        gear_surf = gear_font.render("\u2699", True, (220, 220, 220))
        self.screen.blit(gear_surf, (settings_rect.centerx - gear_surf.get_width() // 2, settings_rect.centery - gear_surf.get_height() // 2))

        quit_rect = self.btn_image_quit.get_rect(center=(cx, btn_y_start + btn_gap * 2))
        self.screen.blit(self.btn_image_quit, quit_rect)

        # Error message
        if self.show_error:
            err_surf = self.small_font.render(self.error_message, True, (255, 60, 60))
            err_bg = pygame.Surface((err_surf.get_width() + 20, err_surf.get_height() + 12), pygame.SRCALPHA)
            err_bg.fill((0, 0, 0, 200))
            err_rect = err_bg.get_rect(center=(cx, btn_y_start - 50))
            err_bg.blit(err_surf, (10, 6))
            self.screen.blit(err_bg, err_rect)
            self.error_frame_counter += 1
            if self.error_frame_counter > 180:
                self.show_error = False
                self.error_frame_counter = 0

        return solo_rect, multi_rect, quit_rect, settings_rect

    def _display_settings(self, cx, sh):
        overlay = pygame.Surface((self.screen_width, self.screen_height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        self.screen.blit(overlay, (0, 0))

        title = self.font.render("PARAMETRES", True, (255, 255, 255))
        self.screen.blit(title, (cx - title.get_width() // 2, int(sh * 0.08)))

        labels = self._settings_labels()
        field_w = 400
        field_h = 42
        start_y = int(sh * 0.2)

        rects = []
        for i, label in enumerate(labels):
            y = start_y + i * 60
            lbl_surf = self.small_font.render(label, True, (200, 200, 220))
            self.screen.blit(lbl_surf, (cx - field_w // 2, y - 22))
            rect = pygame.Rect(cx - field_w // 2, y, field_w, field_h)
            bg_color = (40, 40, 65) if i == self.settings_active_field else (30, 30, 50)
            pygame.draw.rect(self.screen, bg_color, rect, border_radius=6)
            border_color = (100, 140, 255) if i == self.settings_active_field else (60, 60, 90)
            pygame.draw.rect(self.screen, border_color, rect, 2, border_radius=6)
            val = self._get_settings_value(i)
            val_surf = self.name_font.render(str(val), True, (240, 240, 255))
            self.screen.blit(val_surf, (rect.x + 10, rect.y + 10))
            rects.append(rect)

        btn_y = start_y + len(labels) * 60 + 30
        apply_rect = pygame.Rect(cx - 160, btn_y, 140, 44)
        back_rect = pygame.Rect(cx + 20, btn_y, 140, 44)
        pygame.draw.rect(self.screen, (50, 160, 80), apply_rect, border_radius=8)
        pygame.draw.rect(self.screen, (160, 50, 50), back_rect, border_radius=8)
        apply_surf = self.name_font.render("APPLIQUER", True, (255, 255, 255))
        back_surf = self.name_font.render("RETOUR", True, (255, 255, 255))
        self.screen.blit(apply_surf, (apply_rect.centerx - apply_surf.get_width() // 2, apply_rect.centery - apply_surf.get_height() // 2))
        self.screen.blit(back_surf, (back_rect.centerx - back_surf.get_width() // 2, back_rect.centery - back_surf.get_height() // 2))

        self._settings_rects = rects
        self._settings_apply_rect = apply_rect
        self._settings_back_rect = back_rect

        dummy = pygame.Rect(-100, -100, 1, 1)
        return dummy, dummy, dummy, dummy

    def _display_auth(self, cx, sh):
        overlay = pygame.Surface((self.screen_width, self.screen_height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        self.screen.blit(overlay, (0, 0))

        title = self.font.render("CONNEXION MULTIJOUEUR", True, (255, 255, 255))
        self.screen.blit(title, (cx - title.get_width() // 2, int(sh * 0.12)))

        # Show player name as a label (not editable)
        name_label = self.name_font.render(f"Joueur : {self.auth_username}", True, (180, 220, 255))
        self.screen.blit(name_label, (cx - name_label.get_width() // 2, int(sh * 0.22)))

        field_w = 400
        field_h = 42
        start_y = int(sh * 0.32)

        # Only password field
        lbl_surf = self.small_font.render("Mot de passe", True, (200, 200, 220))
        self.screen.blit(lbl_surf, (cx - field_w // 2, start_y - 24))
        rect = pygame.Rect(cx - field_w // 2, start_y, field_w, field_h)
        pygame.draw.rect(self.screen, (40, 40, 65), rect, border_radius=6)
        pygame.draw.rect(self.screen, (100, 140, 255), rect, 2, border_radius=6)
        val_surf = self.name_font.render("*" * len(self.auth_password), True, (240, 240, 255))
        self.screen.blit(val_surf, (rect.x + 10, rect.y + 10))

        btn_y = start_y + 70
        connect_rect = pygame.Rect(cx - 160, btn_y, 140, 44)
        back_rect = pygame.Rect(cx + 20, btn_y, 140, 44)
        pygame.draw.rect(self.screen, (50, 120, 200), connect_rect, border_radius=8)
        pygame.draw.rect(self.screen, (160, 50, 50), back_rect, border_radius=8)
        conn_surf = self.name_font.render("CONNEXION", True, (255, 255, 255))
        back_surf = self.name_font.render("RETOUR", True, (255, 255, 255))
        self.screen.blit(conn_surf, (connect_rect.centerx - conn_surf.get_width() // 2, connect_rect.centery - conn_surf.get_height() // 2))
        self.screen.blit(back_surf, (back_rect.centerx - back_surf.get_width() // 2, back_rect.centery - back_surf.get_height() // 2))

        self._auth_connect_rect = connect_rect
        self._auth_back_rect = back_rect

        if self.auth_error:
            err_surf = self.name_font.render(self.auth_error, True, (255, 70, 70))
            self.screen.blit(err_surf, (cx - err_surf.get_width() // 2, btn_y + 55))

        dummy = pygame.Rect(-100, -100, 1, 1)
        return dummy, dummy, dummy, dummy

    # ─── INPUT HANDLING ──────────────────────────────
    def handle_menu_input(self, event, solo_rect, multi_rect, quit_rect, settings_rect=None):
        # Settings mode
        if self.settings_open:
            return self._handle_settings_input(event)

        # Auth mode
        if self.auth_open:
            return self._handle_auth_input(event)

        # Normal menu
        if event.type == pygame.MOUSEBUTTONDOWN:
            if solo_rect and solo_rect.collidepoint(event.pos):
                return GAME, False
            elif multi_rect and multi_rect.collidepoint(event.pos):
                self.auth_open = True
                self.auth_error = ""
                return None, None
            elif quit_rect and quit_rect.collidepoint(event.pos):
                return 'QUIT', None
            elif settings_rect and settings_rect.collidepoint(event.pos):
                self.settings_open = True
                return None, None
        return None, None

    def _handle_settings_input(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            if hasattr(self, '_settings_back_rect') and self._settings_back_rect.collidepoint(event.pos):
                self.settings_open = False
                return None, None
            if hasattr(self, '_settings_apply_rect') and self._settings_apply_rect.collidepoint(event.pos):
                self.settings_open = False
                return 'APPLY_SETTINGS', None
            if hasattr(self, '_settings_rects'):
                for i, r in enumerate(self._settings_rects):
                    if r.collidepoint(event.pos):
                        self.settings_active_field = i
                        if i in (4, 5):  # Toggle fullscreen or cycle volume on click
                            self._set_settings_value(i, None)
                        return None, None
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.settings_open = False
                return None, None
            if event.key == pygame.K_TAB or event.key == pygame.K_DOWN:
                self.settings_active_field = (self.settings_active_field + 1) % len(self.settings_fields)
                return None, None
            if event.key == pygame.K_UP:
                self.settings_active_field = (self.settings_active_field - 1) % len(self.settings_fields)
                return None, None
            if event.key == pygame.K_RETURN:
                if self.settings_active_field in (4, 5):
                    self._set_settings_value(self.settings_active_field, None)
                return None, None
            idx = self.settings_active_field
            if idx not in (4, 5):  # Text-editable fields
                val = self._get_settings_value(idx)
                if event.key == pygame.K_BACKSPACE:
                    val = val[:-1]
                elif event.unicode and event.unicode.isprintable():
                    val += event.unicode
                self._set_settings_value(idx, val)
        return None, None

    def _handle_auth_input(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            if hasattr(self, '_auth_back_rect') and self._auth_back_rect.collidepoint(event.pos):
                self.auth_open = False
                self.auth_error = ""
                return None, None
            if hasattr(self, '_auth_connect_rect') and self._auth_connect_rect.collidepoint(event.pos):
                return self._try_auth_connect()
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.auth_open = False
                self.auth_error = ""
                return None, None
            if event.key == pygame.K_RETURN:
                return self._try_auth_connect()
            # Only password field
            if event.key == pygame.K_BACKSPACE:
                self.auth_password = self.auth_password[:-1]
            elif event.unicode and event.unicode.isprintable():
                self.auth_password += event.unicode
        return None, None

    def _try_auth_connect(self):
        if not self.auth_password.strip():
            self.auth_error = "Entrez un mot de passe"
            return None, None
        self.auth_open = False
        self.auth_error = ""
        return 'AUTH_CONNECT', True


class GameUI:
    """Gère le rendu en jeu et les entrées."""
    
    def __init__(self, screen, font, small_font, player, game_map, other_players=None, screen_width=800, screen_height=600, username="Player", name_font=None, mission_system=None, phone_ui=None):
        self.screen = screen
        self.font = font
        self.small_font = small_font
        self.name_font = name_font or small_font
        self.player = player
        self.game_map = game_map
        self.other_players = other_players if other_players is not None else {}
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.username = username
        self.camera_x = 0
        self.camera_y = 0
        # TAB-hold player list
        self.show_tab_list = False
        self.car_images = {}
        self.car_frames = {}
        self.car_images_small = {}
        self.background = pygame.image.load('assets/images/HUD/backround.png').convert()
        self.background = pygame.transform.scale(self.background, (self.screen_width, self.screen_height))
        self.mission_system = mission_system
        self.phone_ui = phone_ui
        self.hud_font = pygame.font.Font("assets/fonts/ari-w9500-bold.ttf", 20)
        self.hud_font.set_bold(True)
        self.hud_font_small = pygame.font.Font("assets/fonts/ari-w9500-bold.ttf", 16)
        self.hud_font_small.set_bold(True)
        self.hud_font_big = pygame.font.Font("assets/fonts/ari-w9500-bold.ttf", 28)
        self.hud_font_big.set_bold(True)

    def _get_car_image(self, car):
        """Obtenir ou charger l'image statique (frame 0) pour une voiture spécifique."""
        car_key = tuple(car)  # Utiliser le tuple comme clé de dictionnaire
        if car_key not in self.car_images:
            image_path = resolve_car_frame_path(car[0], car[1], 0)
            image = pygame.image.load(image_path).convert_alpha()
            image = pygame.transform.scale(image, (self.player.size, self.player.size))
            self.car_images[car_key] = image
        return self.car_images[car_key]

    def _get_car_frame(self, car, angle: float):
        """Obtienir la frame appropriée pour une voiture spécifique en fonction de l'angle."""
        car_key = tuple(car)
        if car_key not in self.car_frames:
            # Lazy cache: idx -> Surface
            self.car_frames[car_key] = {}
        frames = self.car_frames[car_key]
        idx = int((angle % 360) / 7.5) % 48
        if idx not in frames:
            image_path = resolve_car_frame_path(car[0], car[1], idx)
            img = pygame.image.load(image_path).convert_alpha()
            img = pygame.transform.scale(img, (self.player.size, self.player.size))
            frames[idx] = img
        return frames[idx]

    def update_camera(self):
        """Camera is now set by pyscroll during _render_map(). Nothing to do."""
        pass

    def handle_events(self, events):
        """Gérer les événements d'entrée du jeu."""
        pass

    def update(self, keys, dt, other_players_rects=None):
        """Mettre à jour l'état du jeu à chaque frame."""
        self.show_tab_list = keys[pygame.K_TAB]
        self.player.update(keys, dt, other_players_rects, game_map=self.game_map)
        self.update_camera()

    def render(self):
        """Rendre tous les objets du jeu et l'interface utilisateur."""
        # Draw background image
        self.screen.blit(self.background, (0, 0))
        self._render_map()
        self._render_drift_trail()
        self._render_mission_markers()
        self._render_other_players()
        self._render_player()
        self._render_hud()
        self._render_gps_arrow()
        self._render_minimap()
        self._render_notification()
        self._render_tab_list()

    def _render_map(self):
        """Render the map and set the camera from pyscroll's actual view."""
        focus_x = self.player.x + self.player.size / 2
        focus_y = self.player.y + self.player.size / 2
        self.game_map.render(self.screen, focus_x, focus_y)
        # Single source of truth: pyscroll's clamped camera
        self.camera_x = self.game_map.actual_camera_x
        self.camera_y = self.game_map.actual_camera_y

    def _render_other_players(self):
        """Afficher les autres joueurs en multijoueur (avec rotation si fournie)."""
        zoom = getattr(self.game_map, 'zoom', 1.0)
        for player_username, player_data in self.other_players.items():
            if isinstance(player_data, dict):
                x, y = player_data.get('x', 0), player_data.get('y', 0)
                car = player_data.get('car', ('SUPERCAR', 'Black'))
                angle = player_data.get('angle', 0.0)
            else:
                x, y = player_data
                car = ('SUPERCAR', 'Black')
                angle = 0.0
            # Centre du joueur en écran
            cx = (x + self.player.size / 2 - self.camera_x) * zoom
            cy = (y + self.player.size / 2 - self.camera_y) * zoom
            # Visible ?
            if -self.player.size < cx < self.screen_width + self.player.size and -self.player.size < cy < self.screen_height + self.player.size:
                raw_image = self._get_car_frame(car, angle) if isinstance(player_data, dict) else self._get_car_image(car)
                # Sprite à taille fixe, centré
                self.screen.blit(raw_image, (int(cx - raw_image.get_width() / 2), int(cy - raw_image.get_height() / 2)))
                label_center_x = int(cx)
                label_top_y = int(cy - raw_image.get_height() / 2 - 22)
                draw_text_bg_center(self.screen, player_username, self.name_font, (255, 255, 255), label_center_x, label_top_y)
                # Debug: draw other player hitbox
                if getattr(self.game_map, 'show_collisions', False):
                    hs = getattr(self.player, 'hitbox_scale', 0.175)
                    hit_size = max(2, int(self.player.size * hs))
                    hit_offset = (self.player.size - hit_size) / 2
                    screen_rect = pygame.Rect(
                        int((x + hit_offset - self.camera_x) * zoom),
                        int((y + hit_offset - self.camera_y) * zoom),
                        int(hit_size * zoom),
                        int(hit_size * zoom)
                    )
                    pygame.draw.rect(self.screen, (255, 165, 0), screen_rect, 2)

    def _render_player(self):
        """Afficher le joueur local."""
        zoom = getattr(self.game_map, 'zoom', 1.0)
        self.player.render(self.screen, self.camera_x, self.camera_y, zoom=zoom)
        # Nom d'utilisateur centré au-dessus du sprite
        cx = (self.player.x + self.player.size / 2 - self.camera_x) * zoom
        cy = (self.player.y + self.player.size / 2 - self.camera_y) * zoom
        label_center_x = int(cx)
        label_top_y = int(cy - self.player.size / 2 - 22)
        draw_text_bg_center(self.screen, self.username, self.name_font, (255, 255, 255), label_center_x, label_top_y)
        # Debug: draw hitbox when collision display is active
        if getattr(self.game_map, 'show_collisions', False):
            hitbox = self.player.get_hitbox_rect()
            screen_rect = pygame.Rect(
                int((hitbox.x - self.camera_x) * zoom),
                int((hitbox.y - self.camera_y) * zoom),
                int(hitbox.width * zoom),
                int(hitbox.height * zoom)
            )
            pygame.draw.rect(self.screen, (0, 255, 0), screen_rect, 2)

    def _render_tab_list(self):
        """Player list shown while TAB is held."""
        if not self.show_tab_list:
            return

        all_players = [(self.username, {
            'x': self.player.x, 'y': self.player.y,
            'car': self.player.car,
            'on_road': getattr(self.player, 'on_road', True),
        })]
        for uname, data in self.other_players.items():
            if isinstance(data, dict):
                all_players.append((uname, data))

        panel_w = 420
        line_h = 32
        header_h = 36
        panel_h = header_h + line_h * len(all_players) + 10
        panel_x = (self.screen_width - panel_w) // 2
        panel_y = 60

        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel.fill((10, 10, 25, 210))
        pygame.draw.rect(panel, (80, 80, 120), (0, 0, panel_w, panel_h), 2, border_radius=8)

        header_lbl = self.hud_font.render("JOUEURS EN LIGNE", True, (200, 200, 255))
        panel.blit(header_lbl, (panel_w // 2 - header_lbl.get_width() // 2, 6))

        y = header_h
        for uname, pdata in all_players:
            px = pdata.get('x', 0)
            py = pdata.get('y', 0)
            on_road = pdata.get('on_road', True)
            surface_str = "ROUTE" if on_road else "HORS-ROUTE"
            surface_col = (100, 255, 100) if on_road else (255, 180, 80)

            name_surf = self.hud_font_small.render(uname, True, (240, 240, 255))
            pos_surf = self.hud_font_small.render(f"({int(px)}, {int(py)})", True, (160, 160, 180))
            road_surf = self.hud_font_small.render(surface_str, True, surface_col)

            panel.blit(name_surf, (10, y + 4))
            panel.blit(pos_surf, (180, y + 4))
            panel.blit(road_surf, (panel_w - road_surf.get_width() - 10, y + 4))
            y += line_h

        self.screen.blit(panel, (panel_x, panel_y))

    def _render_hud(self):
        """HUD permanent : vitesse au-dessus de la minimap (bas-gauche), mission active."""
        # Minimap is at bottom-left, 200x200, margin 8
        map_size = 200
        margin = 8
        minimap_x = margin
        minimap_y = self.screen_height - map_size - margin

        # Speedometer above minimap
        speed_kmh = getattr(self.player, 'speed_kmh', 0.0)
        speed_text = f"{int(round(speed_kmh))} km/h"
        speed_surf = self.hud_font_big.render(speed_text, True, (255, 255, 255))
        speed_bg = pygame.Surface((speed_surf.get_width() + 16, speed_surf.get_height() + 10), pygame.SRCALPHA)
        speed_bg.fill((0, 0, 0, 180))
        speed_bg.blit(speed_surf, (8, 5))
        self.screen.blit(speed_bg, (minimap_x, minimap_y - speed_bg.get_height() - 6))

        if not self.mission_system:
            return

        ms = self.mission_system

        # --- Barre mission active en haut au centre ---
        if ms.active_mission:
            m = ms.active_mission
            obj_label = ms.get_objective_label()
            time_color = (255, 80, 80) if m.time_remaining < 30 else (255, 255, 255)
            timer_str = f"{int(m.time_remaining)}s"
            reward_str = f"{m.reward}$"

            bar_texts = [
                (obj_label, (255, 255, 255)),
                (f"  {timer_str}", time_color),
                (f"  {reward_str}", (100, 255, 100)),
            ]
            total_w = sum(self.hud_font_small.size(t)[0] for t, _ in bar_texts) + 20
            bar_h = 28
            bar_x = (self.screen_width - total_w) // 2
            bar_y = 8
            bar_bg = pygame.Surface((total_w, bar_h), pygame.SRCALPHA)
            bar_bg.fill((0, 0, 0, 180))
            self.screen.blit(bar_bg, (bar_x, bar_y))
            tx = bar_x + 10
            for text, color in bar_texts:
                surf = self.hud_font_small.render(text, True, color)
                self.screen.blit(surf, (tx, bar_y + 5))
                tx += surf.get_width()

    def _render_gps_arrow(self):
        """Flèche GPS pointant vers l'objectif actuel."""
        if not self.mission_system or not self.mission_system.active_mission:
            return
        obj_pos = self.mission_system.get_objective_position()
        if not obj_pos:
            return

        player_cx = self.player.x + self.player.size / 2
        player_cy = self.player.y + self.player.size / 2
        dx = obj_pos[0] - player_cx
        dy = obj_pos[1] - player_cy
        dist = math.hypot(dx, dy)
        if dist < 50:
            return

        angle = math.atan2(dy, dx)

        # Position de la flèche GPS en bas au centre
        arrow_cx = self.screen_width // 2
        arrow_cy = self.screen_height - 90
        arrow_len = 22
        arrow_w = 10

        # Points de la flèche
        tip_x = arrow_cx + math.cos(angle) * arrow_len
        tip_y = arrow_cy + math.sin(angle) * arrow_len
        left_x = arrow_cx + math.cos(angle + 2.5) * arrow_w
        left_y = arrow_cy + math.sin(angle + 2.5) * arrow_w
        right_x = arrow_cx + math.cos(angle - 2.5) * arrow_w
        right_y = arrow_cy + math.sin(angle - 2.5) * arrow_w

        # Couleur selon le statut
        m = self.mission_system.active_mission
        color = (0, 255, 100) if not m.picked_up else (255, 80, 80)

        pygame.draw.polygon(self.screen, color, [
            (int(tip_x), int(tip_y)),
            (int(left_x), int(left_y)),
            (int(right_x), int(right_y))
        ])
        pygame.draw.polygon(self.screen, (255, 255, 255), [
            (int(tip_x), int(tip_y)),
            (int(left_x), int(left_y)),
            (int(right_x), int(right_y))
        ], 2)

        # Distance en mètres (30px = 1m)
        dist_m = int(dist / 30)
        dist_label = f"{dist_m}m"
        dist_surf = self.hud_font_small.render(dist_label, True, (255, 255, 255))
        self.screen.blit(dist_surf, (arrow_cx - dist_surf.get_width() // 2, arrow_cy + 28))

    def _render_minimap(self):
        """Mini-carte en bas à gauche."""
        map_size = 200
        margin = 8
        mx = margin
        my = self.screen_height - map_size - margin

        minimap = pygame.Surface((map_size, map_size), pygame.SRCALPHA)
        minimap.fill((20, 30, 20, 200))
        pygame.draw.rect(minimap, (80, 80, 120), (0, 0, map_size, map_size), 2)

        # Échelle
        map_w = getattr(self.game_map, 'width_px', 8192)
        map_h = getattr(self.game_map, 'height_px', 8192)
        sx = map_size / map_w
        sy = map_size / map_h

        # Mission markers
        if self.mission_system:
            ms = self.mission_system
            for m in ms.available_missions:
                px = int(m.pickup['x'] * sx)
                py = int(m.pickup['y'] * sy)
                pygame.draw.circle(minimap, (255, 255, 0), (px, py), 3)
            if ms.active_mission:
                am = ms.active_mission
                if not am.picked_up:
                    px = int(am.pickup['x'] * sx)
                    py = int(am.pickup['y'] * sy)
                    pygame.draw.circle(minimap, (0, 255, 0), (px, py), 4)
                dx_ = int(am.delivery['x'] * sx)
                dy_ = int(am.delivery['y'] * sy)
                pygame.draw.circle(minimap, (255, 50, 50), (dx_, dy_), 4)

        # Autres joueurs
        for _, pdata in self.other_players.items():
            if isinstance(pdata, dict):
                ox = int(pdata.get('x', 0) * sx)
                oy = int(pdata.get('y', 0) * sy)
                pygame.draw.circle(minimap, (200, 200, 200), (ox, oy), 2)

        # Joueur
        ppx = int((self.player.x + self.player.size / 2) * sx)
        ppy = int((self.player.y + self.player.size / 2) * sy)
        pygame.draw.circle(minimap, (50, 150, 255), (ppx, ppy), 4)

        self.screen.blit(minimap, (mx, my))

    def _render_drift_trail(self):
        """Render tire marks on the ground from drifting as pixelated lines."""
        if not hasattr(self.player, 'drift_trail') or len(self.player.drift_trail) < 2:
            return
        zoom = getattr(self.game_map, 'zoom', 1.0)
        trail = self.player.drift_trail
        thickness = max(2, int(3 * zoom))
        sw, sh = self.screen_width, self.screen_height
        for i in range(1, len(trail)):
            prev = trail[i - 1]
            curr = trail[i]
            # Skip gaps (non-consecutive drift events)
            dx = curr[0] - prev[0]
            dy = curr[1] - prev[1]
            if dx * dx + dy * dy > 2500:
                continue
            shade = int(30 + (1.0 - curr[4]) * 70)
            color = (shade, shade, shade)
            # Left wheel line
            lx1 = int((prev[0] - self.camera_x) * zoom)
            ly1 = int((prev[1] - self.camera_y) * zoom)
            lx2 = int((curr[0] - self.camera_x) * zoom)
            ly2 = int((curr[1] - self.camera_y) * zoom)
            if -10 < lx2 < sw + 10 and -10 < ly2 < sh + 10:
                pygame.draw.line(self.screen, color, (lx1, ly1), (lx2, ly2), thickness)
            # Right wheel line
            rx1 = int((prev[2] - self.camera_x) * zoom)
            ry1 = int((prev[3] - self.camera_y) * zoom)
            rx2 = int((curr[2] - self.camera_x) * zoom)
            ry2 = int((curr[3] - self.camera_y) * zoom)
            if -10 < rx2 < sw + 10 and -10 < ry2 < sh + 10:
                pygame.draw.line(self.screen, color, (rx1, ry1), (rx2, ry2), thickness)

    def _render_mission_markers(self):
        """Marqueurs de mission visibles dans le monde."""
        if not self.mission_system:
            return
        ms = self.mission_system

        # Dessiner les marqueurs des missions disponibles
        for m in ms.available_missions:
            self._draw_world_marker(m.pickup['x'], m.pickup['y'], (255, 255, 0), m.pickup['name'], 12)

        # Marqueur mission active
        if ms.active_mission:
            am = ms.active_mission
            if not am.picked_up:
                self._draw_world_marker(am.pickup['x'], am.pickup['y'], (0, 255, 0), "RAMASSAGE", 18)
            self._draw_world_marker(am.delivery['x'], am.delivery['y'], (255, 50, 50), "LIVRAISON", 18)

    def _draw_world_marker(self, world_x, world_y, color, label, radius):
        """Dessine un marqueur circulaire à une position monde."""
        zoom = getattr(self.game_map, 'zoom', 1.0)
        sx = (world_x - self.camera_x) * zoom
        sy = (world_y - self.camera_y) * zoom
        # Marqueur taille fixe (pas zoomé)
        if -100 < sx < self.screen_width + 100 and -100 < sy < self.screen_height + 100:
            pygame.draw.circle(self.screen, color, (int(sx), int(sy)), radius, 3)
            pygame.draw.circle(self.screen, (255, 255, 255, 100), (int(sx), int(sy)), radius + 3, 1)
            label_surf = self.hud_font_small.render(label, True, color)
            self.screen.blit(label_surf, (int(sx) - label_surf.get_width() // 2, int(sy) - radius - 20))

    def _render_notification(self):
        """Affiche les notifications de mission."""
        if not self.mission_system:
            return
        notif = self.mission_system.get_notification()
        if not notif:
            return
        notif_surf = self.hud_font.render(notif, True, (255, 255, 100))
        notif_bg = pygame.Surface((notif_surf.get_width() + 20, notif_surf.get_height() + 12), pygame.SRCALPHA)
        notif_bg.fill((0, 0, 0, 200))
        notif_bg.blit(notif_surf, (10, 6))
        nx = (self.screen_width - notif_bg.get_width()) // 2
        ny = self.screen_height // 4
        self.screen.blit(notif_bg, (nx, ny))