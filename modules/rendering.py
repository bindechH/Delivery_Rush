"""
Module de rendu pour Delivery Rush
Gère l'affichage des éléments graphiques : joueur, autres joueurs, interface utilisateur.
Fournit des fonctions utilitaires pour le texte et les sprites.
"""

import math
import hashlib
import pygame
from pathlib import Path
from .player import Player, resolve_car_frame_path, VEHICLE_CATALOG, VEHICLE_COLORS
from .translate import normalize_language, tr
from .map import GameMap

# États du jeu (pour compatibilité)
MENU = 0
GAME = 1

# Rarity system
_RARITY_TABLE = [
    (2000,  'Common',    (190, 190, 190)),
    (5000,  'Uncommon',  (80,  200, 80)),
    (10000, 'Rare',      (80,  140, 255)),
    (14999, 'Epic',      (180, 80,  255)),
    (None,  'Legendary', (255, 180, 0)),
]

def get_vehicle_rarity(model):
    price = VEHICLE_CATALOG.get(model, {}).get('price', 0)
    for threshold, name, color in _RARITY_TABLE:
        if threshold is None or price <= threshold:
            return name, color
    return 'Common', (190, 190, 190)

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


class MainMenu:
    def __init__(self, screen, font, small_font, screen_width, screen_height, server_ip='localhost', username='', car=('SUV', 'Black'), sound_manager=None, fullscreen=False, map_zoom=2.0, volume=0.25, music_volume=None, effects_volume=None, language='fr'):
        self.screen = screen
        self.font = font
        self.small_font = small_font or pygame.font.Font("assets/fonts/ari-w9500-bold.ttf", 32)
        self.name_font = pygame.font.Font("assets/fonts/ari-w9500-bold.ttf", 24)
        self.credits_font = pygame.font.Font("assets/fonts/ari-w9500-bold.ttf", 14)
        self.title_font = pygame.font.Font("assets/fonts/ari-w9500-bold.ttf", 38)
        self.title_font.set_bold(True)
        for fnt in (self.small_font, self.name_font):
            fnt.set_bold(True)
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.server_ip = server_ip
        self.username = username
        self.car = car
        self.sound_manager = sound_manager
        self.language = normalize_language(language)
        self.volume_levels = [0.0, 0.1, 0.25, 0.5, 0.75, 1.0]
        base_music_volume = volume if music_volume is None else music_volume
        base_effects_volume = 0.75 if effects_volume is None else effects_volume
        self.music_volume_idx = min(range(len(self.volume_levels)), key=lambda i: abs(self.volume_levels[i] - base_music_volume))
        self.effects_volume_idx = min(range(len(self.volume_levels)), key=lambda i: abs(self.volume_levels[i] - base_effects_volume))
        self.bg_img = pygame.transform.scale(
            pygame.image.load('assets/images/HUD/background.png').convert(),
            (screen_width, screen_height))
        self.show_error = False
        self.error_message = ""
        self.error_frame_counter = 0
        # Right panel is always 325px wide (sw - (75 + sw-400) = 325)
        _panel_w = 325
        _btn_w = int(_panel_w * 0.82)
        def _fit_btn(orig):
            return pygame.transform.smoothscale(orig, (_btn_w, int(orig.get_height() * _btn_w / orig.get_width())))
        self.btn_solo_img = _fit_btn(pygame.image.load('assets/images/HUD/SOLOBTN.png').convert_alpha())
        self.btn_multi_img = _fit_btn(pygame.image.load('assets/images/HUD/multibtn.png').convert_alpha())
        self.btn_quit_img = _fit_btn(pygame.image.load('assets/images/HUD/quitbtn.png').convert_alpha())
        _btn_set = pygame.image.load('assets/images/HUD/setbtn.png').convert_alpha()
        self.btn_image_set = pygame.transform.scale(_btn_set, (_btn_set.get_width() // 4, _btn_set.get_height() // 4))

        # Car animation
        self._car_anim_frame = 0
        self._car_anim_timer = 0.0
        self._car_frames_cache = {}
        self._car_frames = self._load_car_frames(car)

        # Username editing
        self._username_edit = username
        self._username_active = False
        self._username_rect = None

        # Settings state
        self.settings_open = False
        self.cfg_server_ip = server_ip
        self.cfg_server_port = "12345"
        self.cfg_fps = "60"
        self.cfg_resolution = f"{screen_width}x{screen_height}"
        self.cfg_fullscreen = fullscreen
        self.cfg_map_zoom = str(map_zoom)
        self._language_cycle = ["fr", "en"]
        self.settings_fields = [
            "server_ip",
            "server_port",
            "fps",
            "resolution",
            "fullscreen",
            "music_volume",
            "effects_volume",
            "map_zoom",
            "language",
        ]
        self.settings_active_field = 0

        # Auth state (multi) - username from config, only password needed
        self.auth_open = False
        self.auth_username = username
        self.auth_password = ""
        self.auth_active_field = 0
        self.auth_error = ""

    def _t(self, key, **kwargs):
        return tr(self.language, key, **kwargs)

    def _cargo_label(self, cargo_type):
        cargo_key = str(cargo_type or "colis").lower()
        key = f"cargo.{cargo_key}"
        value = self._t(key)
        return value if value != key else cargo_key

    def _mission_type_label(self, mission_type):
        type_key = str(mission_type or "standard").lower()
        key = f"mission.type.{type_key}"
        value = self._t(key)
        if value == key:
            value = type_key
        return value.upper()

    def _mission_reason_label(self, reason):
        reason_key = str(reason or "failed").lower()
        key = f"mission.reason.{reason_key}"
        value = self._t(key)
        if value == key:
            value = reason_key
        return value.upper()

    def refresh_vehicle(self, car):
        """Update the displayed car (call when returning to menu after a game)."""
        self.car = car
        self._car_frames = self._load_car_frames(car)
        self._car_anim_frame = 0
        self._car_anim_timer = 0.0

    def resize(self, w, h):
        self.screen_width = w
        self.screen_height = h

    def _load_car_frames(self, car):
        key = (car[0], car[1])
        if key in self._car_frames_cache:
            return self._car_frames_cache[key]
        frames = []
        size = 480
        for i in range(48):
            try:
                path = resolve_car_frame_path(car[0], car[1], i)
                img = pygame.image.load(path).convert_alpha()
                frames.append(pygame.transform.smoothscale(img, (size, size)))
            except Exception:
                frames.append(pygame.Surface((size, size), pygame.SRCALPHA))
        self._car_frames_cache[key] = frames
        return frames

    def _draw_logo_grid(self, x, y, w, h, scale=None):
        s = scale if scale is not None else self.logo_grid_scale
        if s not in self._logo_tile_cache:
            orig = self._small_logo
            nw = max(1, int(orig.get_width() * s))
            nh = max(1, int(orig.get_height() * s))
            self._logo_tile_cache[s] = pygame.transform.smoothscale(orig, (nw, nh))
        tile = self._logo_tile_cache[s]
        lw, lh = tile.get_width(), tile.get_height()
        if lw <= 0 or lh <= 0:
            return
        cols = w // lw   # only full tiles
        rows = h // lh
        for r in range(rows):
            for c in range(cols):
                self.screen.blit(tile, (x + c * lw, y + r * lh))

    # ─── SETTINGS helpers ─────────────────────────────
    def _get_settings_value(self, idx):
        mapping = [
            self.cfg_server_ip,
            self.cfg_server_port,
            self.cfg_fps,
            self.cfg_resolution,
            self._t("menu.on") if self.cfg_fullscreen else self._t("menu.off"),
            f"{int(self.volume_levels[self.music_volume_idx] * 100)}%",
            f"{int(self.volume_levels[self.effects_volume_idx] * 100)}%",
            self.cfg_map_zoom,
            self._t(f"language.{self.language}"),
        ]
        return mapping[idx]

    def _set_settings_value(self, idx, val):
        if idx == 0: self.cfg_server_ip = val
        elif idx == 1: self.cfg_server_port = val
        elif idx == 2: self.cfg_fps = val
        elif idx == 3: self.cfg_resolution = val
        elif idx == 4: self.cfg_fullscreen = not self.cfg_fullscreen
        elif idx == 5:
            self.music_volume_idx = (self.music_volume_idx + 1) % len(self.volume_levels)
            if self.sound_manager:
                self.sound_manager.set_music_volume(self.volume_levels[self.music_volume_idx])
        elif idx == 6:
            self.effects_volume_idx = (self.effects_volume_idx + 1) % len(self.volume_levels)
            if self.sound_manager and hasattr(self.sound_manager, "set_effects_volume"):
                self.sound_manager.set_effects_volume(self.volume_levels[self.effects_volume_idx])
        elif idx == 7:
            self.cfg_map_zoom = val
        elif idx == 8:
            curr = self._language_cycle.index(self.language) if self.language in self._language_cycle else 0
            self.language = self._language_cycle[(curr + 1) % len(self._language_cycle)]

    def _settings_labels(self):
        return [
            self._t("menu.server_ip"),
            self._t("menu.port"),
            self._t("menu.fps"),
            self._t("menu.resolution"),
            self._t("menu.fullscreen"),
            self._t("menu.music_volume"),
            self._t("menu.effects_volume"),
            self._t("menu.map_zoom"),
            self._t("menu.language"),
        ]

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
            "music_volume": self.volume_levels[self.music_volume_idx],
            "effects_volume": self.volume_levels[self.effects_volume_idx],
            "language": self.language,
        }

    # ─── DISPLAY ─────────────────────────────────────
    def display_menu(self, dt=0.016):
        sw, sh = self.screen_width, self.screen_height

        # Solid base
        self.screen.fill((0x38, 0x38, 0x38))

        if self.settings_open:
            return self._display_settings(sw // 2, sh)
        if self.auth_open:
            return self._display_auth(sw // 2, sh)

        # ── Background ─────────────────────────────────────────────
        self.screen.blit(self.bg_img, (0, 0))

        # ── Left panel: buttons + credits ─────────────────────────
        left_panel_w = 325
        margin = 20

        # Buttons – shifted right and down
        btn_gap = 12
        btn_x = 100
        solo_rect = self.btn_solo_img.get_rect(topleft=(btn_x, 220))
        self.screen.blit(self.btn_solo_img, solo_rect)
        multi_rect = self.btn_multi_img.get_rect(topleft=(btn_x, solo_rect.bottom + btn_gap))
        self.screen.blit(self.btn_multi_img, multi_rect)
        quit_rect = self.btn_quit_img.get_rect(topleft=(btn_x, multi_rect.bottom + btn_gap))
        self.screen.blit(self.btn_quit_img, quit_rect)

        # ── Right area: spinning car + player info ─────────────────
        car_cx = (left_panel_w + 160 + (sw - 20)) // 2
        car_cy = int(sh * 0.42)
        self._car_anim_timer += dt
        if self._car_anim_timer >= 0.11:
            self._car_anim_timer = 0.0
            self._car_anim_frame = (self._car_anim_frame + 1) % 48
        if self._car_frames:
            car_img = self._car_frames[self._car_anim_frame % len(self._car_frames)]
            self.screen.blit(car_img, car_img.get_rect(center=(car_cx, car_cy)))

        # Username + vehicle name below car
        info_y = car_cy + 230
        uname_color = (255, 220, 80) if self._username_active else (230, 230, 230)
        display_name = self._username_edit.upper() or " "
        uname_surf = self.small_font.render(display_name, True, uname_color)
        uname_rect = uname_surf.get_rect(center=(car_cx, info_y))
        self._username_rect = uname_rect.inflate(20, 10)
        # Highlight box when editing
        if self._username_active:
            pygame.draw.rect(self.screen, (60, 60, 60, 180), self._username_rect, border_radius=6)
            pygame.draw.rect(self.screen, (255, 220, 80), self._username_rect, 2, border_radius=6)
        # Blinking cursor
        if self._username_active and (pygame.time.get_ticks() // 500) % 2 == 0:
            cursor_x = uname_rect.right + 3
            cursor_y1 = uname_rect.top
            cursor_y2 = uname_rect.bottom
            pygame.draw.line(self.screen, (255, 220, 80), (cursor_x, cursor_y1), (cursor_x, cursor_y2), 2)
        self.screen.blit(uname_surf, uname_rect)
        rarity_name, rarity_col = get_vehicle_rarity(self.car[0])
        veh_surf = self.name_font.render(self.car[0].lower(), True, rarity_col)
        self.screen.blit(veh_surf, veh_surf.get_rect(center=(car_cx, info_y + uname_surf.get_height() + 6)))

        # Settings button – bottom-right corner
        settings_rect = self.btn_image_set.get_rect(bottomright=(sw - margin, sh - margin))
        self.screen.blit(self.btn_image_set, settings_rect)

        # Error message
        if self.show_error:
            err_surf = self.small_font.render(self.error_message, True, (255, 60, 60))
            err_bg = pygame.Surface((err_surf.get_width() + 20, err_surf.get_height() + 12),
                                    pygame.SRCALPHA)
            err_bg.fill((0, 0, 0, 200))
            err_rect = err_bg.get_rect(center=(sw // 2, sh - 50))
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

        # Use name_font for SETTINGS title
        title = self.name_font.render(self._t("menu.settings_title"), True, (255, 255, 255))
        self.screen.blit(title, (cx - title.get_width() // 2, int(sh * 0.08)))

        labels = self._settings_labels()
        field_w = 340
        field_h = 40
        start_y = int(sh * 0.18)

        rects = []
        for i, label in enumerate(labels):
            col = 0 if i < 5 else 1
            row = i if col == 0 else (i - 5)
            x_pos = cx - 360 if col == 0 else cx + 20
            # Reduced row spacing from 80 to 60 to prevent overlap
            y = start_y + row * 60
            
            lbl_surf = self.name_font.render(label, True, (200, 200, 220))
            self.screen.blit(lbl_surf, (x_pos, y - 22))
            rect = pygame.Rect(x_pos, y, field_w, field_h)
            bg_color = (40, 40, 65) if i == self.settings_active_field else (30, 30, 50)
            pygame.draw.rect(self.screen, bg_color, rect, border_radius=6)
            border_color = (100, 140, 255) if i == self.settings_active_field else (60, 60, 90)
            pygame.draw.rect(self.screen, border_color, rect, 2, border_radius=6)
            val = self._get_settings_value(i)
            val_surf = self.name_font.render(str(val), True, (240, 240, 255))
            self.screen.blit(val_surf, (rect.x + 10, rect.y + 8))
            rects.append(rect)

        # Move buttons up tighter underneath the fields
        btn_y = start_y + 300
        apply_rect = pygame.Rect(cx - 160, btn_y, 140, 44)
        back_rect = pygame.Rect(cx + 20, btn_y, 140, 44)
        pygame.draw.rect(self.screen, (50, 160, 80), apply_rect, border_radius=8)
        pygame.draw.rect(self.screen, (160, 50, 50), back_rect, border_radius=8)
        apply_surf = self.name_font.render(self._t("menu.apply"), True, (255, 255, 255))
        back_surf = self.name_font.render(self._t("menu.back"), True, (255, 255, 255))
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

        title = self.title_font.render(self._t("menu.auth_title"), True, (255, 255, 255))
        self.screen.blit(title, (cx - title.get_width() // 2, int(sh * 0.12)))

        # Show player name as a label (not editable)
        name_label = self.name_font.render(f"{self._t('menu.player')} : {self.auth_username}", True, (180, 220, 255))
        self.screen.blit(name_label, (cx - name_label.get_width() // 2, int(sh * 0.22)))

        field_w = 400
        field_h = 42
        start_y = int(sh * 0.32)

        # Only password field
        lbl_surf = self.small_font.render(self._t("menu.password"), True, (200, 200, 220))
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
        conn_surf = self.name_font.render(self._t("menu.connect"), True, (255, 255, 255))
        back_surf = self.name_font.render(self._t("menu.back"), True, (255, 255, 255))
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
            # Username box click
            if self._username_rect and self._username_rect.collidepoint(event.pos):
                self._username_active = True
                return None, None
            # Click outside username box commits the edit
            self._username_active = False
            self.username = self._username_edit
            self.auth_username = self._username_edit
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
        elif event.type == pygame.KEYDOWN and self._username_active:
            if event.key in (pygame.K_RETURN, pygame.K_ESCAPE):
                self._username_active = False
                self.username = self._username_edit
                self.auth_username = self._username_edit
            elif event.key == pygame.K_BACKSPACE:
                self._username_edit = self._username_edit[:-1]
            elif event.unicode and event.unicode.isprintable() and len(self._username_edit) < 20:
                self._username_edit += event.unicode
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
                        if i in (4, 5, 6, 8):
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
                if self.settings_active_field in (4, 5, 6, 8):
                    self._set_settings_value(self.settings_active_field, None)
                return None, None
            idx = self.settings_active_field
            if idx not in (4, 5, 6, 8):  # Text-editable fields
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
            self.auth_error = self._t("menu.enter_password")
            return None, None
        self.auth_open = False
        self.auth_error = ""
        return 'AUTH_CONNECT', True


class GameUI:
    """Gère le rendu en jeu et les entrées."""
    
    def __init__(self, screen, font, small_font, player, game_map, other_players=None, screen_width=800, screen_height=600, username="Player", name_font=None, mission_system=None, phone_ui=None, language='fr'):
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
        self.camera_x = self.player.x - self.screen_width // 2
        self.camera_y = self.player.y - self.screen_height // 2
        # TAB-hold player list
        self.show_tab_list = False
        self.car_images = {}
        self.car_frames = {}
        self.car_images_small = {}
        self.background = pygame.Surface((self.screen_width, self.screen_height))
        self.background.fill((0, 0, 0))
        self._minimap_bg = None
        try:
            raw_minimap = pygame.image.load("assets/images/HUD/minimap.png").convert_alpha()
            self._minimap_bg = pygame.transform.smoothscale(raw_minimap, (200, 200))
        except Exception:
            self._minimap_bg = None
        self.mission_system = mission_system
        self.phone_ui = phone_ui
        self.hud_font = pygame.font.Font("assets/fonts/ari-w9500-bold.ttf", 20)
        self.hud_font.set_bold(True)
        self.hud_font_small = pygame.font.Font("assets/fonts/ari-w9500-bold.ttf", 16)
        self.hud_font_small.set_bold(True)
        self.hud_font_big = pygame.font.Font("assets/fonts/ari-w9500-bold.ttf", 28)
        self.hud_font_big.set_bold(True)
        self._mission_result_popup = None
        self._mission_result_timer = 0.0
        self._mission_result_duration = 5.5
        self._objective_sprite_cache = {}
        self.party_by_player = {}
        self.party_color_by_id = {}
        self.robbery_active = False
        self.robbery_pressure = 0.0
        self.robber_count = 0
        self.robbery_close_count = 0
        self.language = normalize_language(language)

    def _t(self, key, **kwargs):
        return tr(self.language, key, **kwargs)

    def _cargo_label(self, cargo_type):
        cargo_key = str(cargo_type or "colis").lower()
        key = f"cargo.{cargo_key}"
        value = self._t(key)
        return value if value != key else cargo_key

    def _mission_type_label(self, mission_type):
        type_key = str(mission_type or "standard").lower()
        key = f"mission.type.{type_key}"
        value = self._t(key)
        if value == key:
            value = type_key
        return value.upper()

    def _mission_reason_label(self, reason):
        reason_key = str(reason or "failed").lower()
        key = f"mission.reason.{reason_key}"
        value = self._t(key)
        if value == key:
            value = reason_key
        return value.upper()

    @staticmethod
    def _fit_text(font, text, max_width):
        value = str(text or "")
        if max_width <= 4:
            return ""
        if font.size(value)[0] <= max_width:
            return value
        out = value
        ellipsis = "..."
        while out and font.size(out + ellipsis)[0] > max_width:
            out = out[:-1]
        return (out + ellipsis) if out else ellipsis

    def _get_car_image(self, car):
        """Obtenir ou charger l'image statique (frame 0) pour une voiture spécifique."""
        car_key = tuple(car)  # Utiliser le tuple comme clé de dictionnaire
        if car_key not in self.car_images:
            image_path = resolve_car_frame_path(car[0], car[1], 0)
            image = pygame.image.load(image_path)
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
            img = pygame.image.load(image_path)
            img = pygame.transform.scale(img, (self.player.size, self.player.size))
            frames[idx] = img
        return frames[idx]

    def _get_small_car_icon(self, car, icon_size=20):
        car_key = (tuple(car), int(icon_size))
        if car_key not in self.car_images_small:
            base = self._get_car_image(car)
            self.car_images_small[car_key] = pygame.transform.smoothscale(base, (icon_size, icon_size))
        return self.car_images_small[car_key]

    @staticmethod
    def _party_color(party_id):
        digest = hashlib.md5(str(party_id).encode("utf-8")).hexdigest()
        hue_src = int(digest[:8], 16)
        hue = float(hue_src % 360)
        saturation = 78.0 + float((hue_src >> 9) % 18)   # 78..95
        value = 92.0 + float((hue_src >> 17) % 9)        # 92..100
        color = pygame.Color(255, 255, 255)
        color.hsva = (hue, saturation, value, 100.0)
        return int(color.r), int(color.g), int(color.b)

    def _name_color_for_player(self, username):
        party_id = self.party_by_player.get(str(username), "")
        if not party_id:
            return 255, 255, 255
        return self.party_color_by_id.get(party_id, (255, 255, 255))

    def update_camera(self):
        """Centrer la caméra sur la position du joueur.

        camera_x/y represent the world coordinate of the top-left corner
        of the visible viewport (screen_size / zoom).  Snapped to integer
        so that pyscroll (running at zoom=1) and our sprite formula
        (world - camera) * zoom  both produce pixel-exact results.
        """
        zoom = getattr(self.game_map, 'zoom', 1.0)
        half_vw = self.screen_width / (2.0 * zoom)
        half_vh = self.screen_height / (2.0 * zoom)

        # World center = player center
        cx = self.player.x + self.player.size / 2
        cy = self.player.y + self.player.size / 2

        # Clamp center so viewport stays within map
        if hasattr(self.game_map, 'width_px') and hasattr(self.game_map, 'height_px'):
            cx = max(half_vw, min(self.game_map.width_px - half_vw, cx))
            cy = max(half_vh, min(self.game_map.height_px - half_vh, cy))

        # Snap top-left to integer world pixels
        self.camera_x = int(cx - half_vw)
        self.camera_y = int(cy - half_vh)

    def handle_events(self, events):
        """Gérer les événements d'entrée du jeu."""
        pass

    def update(self, keys, dt, other_players_rects=None):
        """Mettre à jour l'état du jeu à chaque frame."""
        self.show_tab_list = keys[pygame.K_TAB]
        self.player.update(keys, dt, other_players_rects, game_map=self.game_map)
        if self._mission_result_timer > 0.0:
            self._mission_result_timer = max(0.0, self._mission_result_timer - dt)
            if self._mission_result_timer <= 0.0:
                self._mission_result_popup = None
        self.update_camera()

    def set_party_snapshot(self, party_state):
        """Injecte l'état de party réseau pour colorer les joueurs d'une même party."""
        mapping = {}
        color_by_party = {}
        if isinstance(party_state, dict):
            parties = party_state.get('parties', {})
            if isinstance(parties, dict):
                for party_id, pdata in parties.items():
                    if not isinstance(pdata, dict):
                        continue
                    pid = str(party_id)
                    color_by_party[pid] = self._party_color(pid)
                    members = pdata.get('members', []) if isinstance(pdata.get('members'), list) else []
                    for member in members:
                        member_name = str(member)
                        if member_name:
                            mapping[member_name] = pid
        self.party_by_player = mapping
        self.party_color_by_id = color_by_party

    def set_robbery_status(self, active=False, pressure=0.0, robber_count=0, close_count=0):
        """Injecte l'état de pression des braqueurs pour le HUD."""
        self.robbery_active = bool(active)
        self.robbery_pressure = max(0.0, min(1.0, float(pressure or 0.0)))
        self.robber_count = max(0, int(robber_count or 0))
        self.robbery_close_count = max(0, int(close_count or 0))

    def render(self):
        """Rendre tous les objets du jeu et l'interface utilisateur."""
        # Draw background image
        self.screen.blit(self.background, (0, 0))
        self._render_map()
        self._render_drift_trail()
        self._render_mission_markers()
        self._render_other_players()
        self._render_ai_debug()
        self._render_player()
        self._render_hud()
        self._render_gps_arrow()
        self._render_minimap()
        self._render_notification()
        self._render_mission_result_popup()
        self._render_tab_list()

    def _render_map(self):
        """Rendre la carte du jeu."""
        self.game_map.render(self.screen, self.camera_x, self.camera_y)
        # Use pyscroll's actual camera position (after its internal clamping)
        # so all sprite positioning matches what pyscroll actually rendered.
        self.camera_x = self.game_map.actual_camera_x
        self.camera_y = self.game_map.actual_camera_y

    def _render_other_players(self):
        """Afficher les autres joueurs en multijoueur (avec rotation si fournie)."""
        zoom = getattr(self.game_map, 'zoom', 1.0)
        for player_username, player_data in self.other_players.items():
            is_ai = isinstance(player_data, dict) and bool(player_data.get('ai', False))
            if isinstance(player_data, dict):
                x, y = player_data.get('x', 0), player_data.get('y', 0)
                car = player_data.get('car', ('SUPERCAR', 'Black'))
                angle = player_data.get('angle', 0.0)
                ai_kind = str(player_data.get('ai_kind', '') or '').lower()
            else:
                x, y = player_data
                car = ('SUPERCAR', 'Black')
                angle = 0.0
                ai_kind = ''
            # Centre du joueur en écran
            cx = (x + self.player.size / 2 - self.camera_x) * zoom
            cy = (y + self.player.size / 2 - self.camera_y) * zoom
            # Visible ?
            if -self.player.size < cx < self.screen_width + self.player.size and -self.player.size < cy < self.screen_height + self.player.size:
                if isinstance(player_data, dict):
                    raw_image = self._get_car_frame(car, angle)
                else:
                    raw_image = self._get_car_image(car)
                # Sprite à taille fixe, centré
                self.screen.blit(raw_image, (int(cx - raw_image.get_width() / 2), int(cy - raw_image.get_height() / 2)))
                if not is_ai:
                    label_center_x = int(cx)
                    label_top_y = int(cy - raw_image.get_height() / 2 - 22)
                    draw_text_bg_center(
                        self.screen,
                        player_username,
                        self.name_font,
                        self._name_color_for_player(player_username),
                        label_center_x,
                        label_top_y,
                    )
                elif ai_kind == 'robber':
                    label_center_x = int(cx)
                    label_top_y = int(cy - raw_image.get_height() / 2 - 22)
                    draw_text_bg_center(self.screen, self._t("hud.robber_tag"), self.name_font, (255, 95, 95), label_center_x, label_top_y)
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
        draw_text_bg_center(
            self.screen,
            self.username,
            self.name_font,
            self._name_color_for_player(self.username),
            label_center_x,
            label_top_y,
        )
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

        all_players = [
            (
                self.username,
                {
                    "car": self.player.car,
                },
            )
        ]
        for uname, data in self.other_players.items():
            if isinstance(data, dict) and not data.get("ai", False):
                all_players.append((uname, data))

        if len(all_players) > 1:
            first = all_players[0]
            tail = sorted(all_players[1:], key=lambda row: str(row[0]).lower())
            all_players = [first] + tail

        panel_margin = 20
        panel_y = 56
        panel_w = min(self.screen_width - panel_margin * 2, 440)
        panel_x = (self.screen_width - panel_w) // 2

        title_h = 30
        row_h = 38
        icon_size = 24
        icon_gap = 10
        footer_h = 22
        inner_pad = 14

        reserved_h = 12 + title_h
        max_rows = max(1, (self.screen_height - panel_y - panel_margin - reserved_h - footer_h) // row_h)
        visible_players = all_players[:max_rows]
        hidden_count = max(0, len(all_players) - len(visible_players))
        footer_space = footer_h if hidden_count > 0 else 0

        panel_h = 12 + title_h + row_h * len(visible_players) + footer_space

        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel.fill((10, 10, 24, 210))
        pygame.draw.rect(panel, (90, 95, 136), (0, 0, panel_w, panel_h), 2, border_radius=8)

        title_text = self.hud_font.render(self._t("hud.players_online"), True, (210, 210, 255))
        panel.blit(title_text, (panel_w // 2 - title_text.get_width() // 2, 7))

        row_y0 = 12 + title_h
        for idx, (uname, pdata) in enumerate(visible_players):
            row_y = row_y0 + idx * row_h
            row_rect = pygame.Rect(8, row_y, panel_w - 16, row_h)

            if idx % 2 == 0:
                pygame.draw.rect(panel, (16, 18, 34, 130), row_rect)

            if str(uname) == str(self.username):
                pygame.draw.rect(panel, (70, 110, 190), row_rect, 1, border_radius=4)

            car = pdata.get("car", ("MICRO", "White")) if isinstance(pdata, dict) else ("MICRO", "White")
            if isinstance(car, (list, tuple)) and len(car) >= 2:
                car_model = str(car[0])
                car_color = str(car[1])
            else:
                car_model, car_color = "MICRO", "White"

            icon = self._get_small_car_icon((car_model, car_color), icon_size=icon_size)
            icon_y = row_y + (row_h - icon_size) // 2
            max_name_w = max(50, panel_w - inner_pad * 2 - icon_size - icon_gap)
            name_text = self._fit_text(self.hud_font_small, uname, max_name_w)
            name_surf = self.hud_font_small.render(name_text, True, self._name_color_for_player(uname))
            name_y = row_y + (row_h - name_surf.get_height()) // 2

            content_w = icon_size + icon_gap + name_surf.get_width()
            content_x = max(inner_pad, (panel_w - content_w) // 2)
            panel.blit(icon, (content_x, icon_y))
            panel.blit(name_surf, (content_x + icon_size + icon_gap, name_y))

            pygame.draw.line(panel, (44, 48, 74), (8, row_y + row_h - 1), (panel_w - 8, row_y + row_h - 1), 1)

        if hidden_count > 0:
            footer_y = row_y0 + row_h * len(visible_players)
            pygame.draw.rect(panel, (14, 14, 28, 190), (8, footer_y, panel_w - 16, footer_h), border_radius=4)
            more_text = self.hud_font_small.render(f"+{hidden_count} more", True, (175, 178, 205))
            panel.blit(more_text, (panel_w // 2 - more_text.get_width() // 2, footer_y + (footer_h - more_text.get_height()) // 2))

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

        show_collisions = bool(getattr(self.game_map, 'show_collisions', False))
        show_ai_debug = bool(getattr(self.game_map, 'show_ai_debug', False))
        debug_text = None
        if show_collisions and show_ai_debug:
            debug_text = "DEBUG: FULL AI"
        elif show_ai_debug:
            debug_text = "DEBUG: AI"
        elif show_collisions:
            debug_text = "DEBUG: COLLISIONS"

        if debug_text:
            debug_label = self.hud_font_small.render(debug_text, True, (255, 210, 120))
            self.screen.blit(debug_label, (minimap_x, minimap_y - speed_bg.get_height() - 34))

        if self.robbery_active or self.robbery_pressure > 0.01:
            bar_w = 200
            bar_h = 18
            bx = minimap_x
            by = minimap_y - speed_bg.get_height() - 30
            bar_bg = pygame.Surface((bar_w, bar_h), pygame.SRCALPHA)
            bar_bg.fill((8, 8, 8, 200))
            self.screen.blit(bar_bg, (bx, by))

            fill_w = int((bar_w - 2) * self.robbery_pressure)
            if fill_w > 0:
                fill_col = (255, 70, 70) if self.robbery_pressure >= 0.65 else (255, 160, 70)
                pygame.draw.rect(self.screen, fill_col, (bx + 1, by + 1, fill_w, bar_h - 2), border_radius=4)
            pygame.draw.rect(self.screen, (220, 220, 220), (bx, by, bar_w, bar_h), 1, border_radius=4)

            label = self.hud_font_small.render(
                f"{self._t('hud.robbery')} {self.robbery_close_count}/{max(1, self.robber_count)}",
                True,
                (255, 230, 230) if self.robbery_active else (210, 210, 210),
            )
            self.screen.blit(label, (bx + 6, by - 16))

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
            req_label = ms.mission_requirement_label(m) if hasattr(ms, 'mission_requirement_label') else ""
            cargo_label = f"{self._t('hud.cargo')}: {self._cargo_label(getattr(m, 'cargo_type', 'colis'))} {int(getattr(m, 'cargo_weight', 0))}kg"
            no_req = self._t("mission.none_requirement")
            if req_label and req_label != no_req:
                details_label = f"{cargo_label} | {req_label}"
            else:
                details_label = cargo_label

            badges = self._build_requirement_badges(m)

            bar_texts = [
                (obj_label, (255, 255, 255)),
                (f"  {timer_str}", time_color),
                (f"  {reward_str}", (100, 255, 100)),
            ]
            line_w = sum(self.hud_font_small.size(t)[0] for t, _ in bar_texts) + 20
            details_w = self.hud_font_small.size(details_label)[0] + 20
            badge_w = sum(self.hud_font_small.size(lbl)[0] + 20 for lbl in badges) + 16
            total_w = max(line_w, details_w, badge_w, 360)
            total_w = min(total_w, self.screen_width - 24)
            bar_h = 74
            bar_x = (self.screen_width - total_w) // 2
            bar_y = 8
            bar_bg = pygame.Surface((total_w, bar_h), pygame.SRCALPHA)
            bar_bg.fill((0, 0, 0, 180))
            self.screen.blit(bar_bg, (bar_x, bar_y))
            tx = bar_x + 10
            for text, color in bar_texts:
                fitted = self._fit_text(self.hud_font_small, text, max(20, (bar_x + total_w - 10) - tx))
                surf = self.hud_font_small.render(fitted, True, color)
                self.screen.blit(surf, (tx, bar_y + 4))
                tx += surf.get_width()

            detail_color = (255, 230, 130) if req_label and req_label != no_req else (200, 200, 220)
            details_line = self._fit_text(self.hud_font_small, details_label, total_w - 20)
            details_surf = self.hud_font_small.render(details_line, True, detail_color)
            self.screen.blit(details_surf, (bar_x + 10, bar_y + 24))

            self._render_requirement_badges(badges, bar_x + 8, bar_y + 47, total_w - 16)

    def _build_requirement_badges(self, mission):
        req = mission.requirements or {}
        badges = []

        required_class = str(req.get('required_class', '')).strip().lower()
        if required_class:
            badges.append(f"{self._t('hud.class')} {required_class}")

        min_speed = int(float(req.get('min_speed', 0.0) or 0.0))
        if min_speed > 0:
            badges.append(f"V>={min_speed}")

        min_capacity = int(float(req.get('min_capacity', 0.0) or 0.0))
        if min_capacity > 0:
            badges.append(f"Cap>={min_capacity}")

        if getattr(mission, 'cargo_type', None):
            badges.append(self._cargo_label(mission.cargo_type).upper())

        if len(getattr(mission, 'stops', [])) > 2:
            badges.append(self._t("hud.steps", count=len(mission.stops)))

        return badges[:4]

    def _render_requirement_badges(self, badges, x, y, max_width):
        if not badges:
            return

        cursor_x = x
        max_x = x + max_width
        for badge in badges:
            txt = self.hud_font_small.render(str(badge), True, (235, 235, 245))
            bw = txt.get_width() + 14
            bh = txt.get_height() + 4
            if cursor_x + bw > max_x:
                break
            pygame.draw.rect(self.screen, (38, 52, 78, 210), (cursor_x, y, bw, bh), border_radius=6)
            pygame.draw.rect(self.screen, (110, 135, 180), (cursor_x, y, bw, bh), 1, border_radius=6)
            self.screen.blit(txt, (cursor_x + 7, y + 2))
            cursor_x += bw + 6

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
        objective = self.mission_system.get_current_objective() if hasattr(self.mission_system, 'get_current_objective') else None
        kind = str((objective or {}).get('kind', 'pickup'))
        color = (255, 80, 80) if kind == 'dropoff' else (80, 180, 255) if kind == 'stop' else (0, 255, 100)

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
        if self._minimap_bg is not None:
            minimap.blit(self._minimap_bg, (0, 0))
            frame_col = (220, 220, 220)
        else:
            minimap.fill((20, 30, 20, 200))
            frame_col = (80, 80, 120)

        # Dark glass overlay improves contrast for mission/player points.
        contrast = pygame.Surface((map_size, map_size), pygame.SRCALPHA)
        contrast.fill((0, 0, 0, 92))
        minimap.blit(contrast, (0, 0))
        pygame.draw.rect(minimap, frame_col, (0, 0, map_size, map_size), 2)

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
                pygame.draw.circle(minimap, (255, 220, 70), (px, py), 4)
                pygame.draw.circle(minimap, (40, 30, 0), (px, py), 5, 1)
            if ms.active_mission:
                am = ms.active_mission
                objective = ms.get_current_objective() if hasattr(ms, 'get_current_objective') else None

                for stop in getattr(am, 'stops', []):
                    sx_stop = int(float(stop.get('x', 0.0)) * sx)
                    sy_stop = int(float(stop.get('y', 0.0)) * sy)
                    stop_kind = str(stop.get('kind', 'stop'))
                    stop_color = (255, 80, 80) if stop_kind == 'dropoff' else (120, 180, 255) if stop_kind == 'stop' else (0, 255, 120)
                    pygame.draw.circle(minimap, stop_color, (sx_stop, sy_stop), 3)
                    pygame.draw.circle(minimap, (20, 20, 20), (sx_stop, sy_stop), 4, 1)

                if objective:
                    ox = int(float(objective.get('x', 0.0)) * sx)
                    oy = int(float(objective.get('y', 0.0)) * sy)
                    kind = str(objective.get('kind', 'pickup'))
                    color = (255, 80, 80) if kind == 'dropoff' else (80, 180, 255) if kind == 'stop' else (0, 255, 100)
                    pygame.draw.circle(minimap, color, (ox, oy), 5)
                    pygame.draw.circle(minimap, (255, 255, 255), (ox, oy), 6, 1)

        hover_target = None
        if self.phone_ui and hasattr(self.phone_ui, 'get_hovered_mission_target'):
            hover_target = self.phone_ui.get_hovered_mission_target()
        if isinstance(hover_target, dict):
            hx = int(float(hover_target.get('x', 0.0) or 0.0) * sx)
            hy = int(float(hover_target.get('y', 0.0) or 0.0) * sy)
            blink = int(pygame.time.get_ticks() / 210) % 2 == 0
            pulse_r = 8 + (2 if blink else 0)
            glow = pygame.Surface((pulse_r * 4, pulse_r * 4), pygame.SRCALPHA)
            pygame.draw.circle(glow, (255, 245, 120, 90), (glow.get_width() // 2, glow.get_height() // 2), pulse_r + 2)
            minimap.blit(glow, (hx - glow.get_width() // 2, hy - glow.get_height() // 2))
            pygame.draw.circle(minimap, (255, 250, 180), (hx, hy), pulse_r, 2)
            pygame.draw.circle(minimap, (10, 10, 10), (hx, hy), pulse_r + 1, 1)

        # Autres joueurs
        for _, pdata in self.other_players.items():
            if isinstance(pdata, dict):
                if pdata.get('ai', False):
                    continue
                ox = int(pdata.get('x', 0) * sx)
                oy = int(pdata.get('y', 0) * sy)
                pygame.draw.circle(minimap, (200, 200, 200), (ox, oy), 3)
                pygame.draw.circle(minimap, (30, 30, 30), (ox, oy), 4, 1)

        # Joueur
        ppx = int((self.player.x + self.player.size / 2) * sx)
        ppy = int((self.player.y + self.player.size / 2) * sy)
        pygame.draw.circle(minimap, (50, 150, 255), (ppx, ppy), 5)
        pygame.draw.circle(minimap, (255, 255, 255), (ppx, ppy), 6, 1)

        self.screen.blit(minimap, (mx, my))

    def _render_ai_debug(self):
        if not getattr(self.game_map, 'show_ai_debug', False):
            return

        zoom = getattr(self.game_map, 'zoom', 1.0)
        tile_w = float(getattr(self.game_map, 'tile_width', 32) or 32)
        tile_h = float(getattr(self.game_map, 'tile_height', 32) or 32)

        def world_to_screen(wx, wy):
            return int((float(wx) - self.camera_x) * zoom), int((float(wy) - self.camera_y) * zoom)

        def draw_heading(cx, cy, angle_deg, length, color, width=2):
            rad = math.radians(float(angle_deg))
            ex = int(cx + math.cos(rad) * length)
            ey = int(cy + math.sin(rad) * length)
            pygame.draw.line(self.screen, color, (cx, cy), (ex, ey), width)
            pygame.draw.circle(self.screen, color, (ex, ey), 3)

        def heading_label(angle_deg):
            idx = int(round((float(angle_deg) % 360.0) / 90.0)) % 4
            return ("E", "S", "W", "N")[idx]

        def fmt_value(value):
            if isinstance(value, float):
                return f"{value:.1f}"
            if isinstance(value, bool):
                return "1" if value else "0"
            if isinstance(value, (list, tuple)):
                items = list(value)
                out = [fmt_value(v) for v in items[:4]]
                if len(items) > 4:
                    out.append("...")
                return "[" + ",".join(out) + "]"
            if value is None:
                return "none"
            return str(value)

        for player_username, player_data in self.other_players.items():
            if not isinstance(player_data, dict) or not player_data.get('ai', False):
                continue

            x = float(player_data.get('x', 0.0) or 0.0)
            y = float(player_data.get('y', 0.0) or 0.0)
            cx, cy = world_to_screen(x + self.player.size * 0.5, y + self.player.size * 0.5)

            if cx < -80 or cy < -80 or cx > self.screen_width + 80 or cy > self.screen_height + 80:
                continue

            ai_dbg = player_data.get('debug_ai')
            if not isinstance(ai_dbg, dict):
                ai_dbg = {}

            debug_path = player_data.get('debug_path', [])
            if isinstance(debug_path, list) and len(debug_path) >= 1:
                points = []
                for point in debug_path:
                    if isinstance(point, (list, tuple)) and len(point) >= 2:
                        px = float(point[0])
                        py = float(point[1])
                        points.append(world_to_screen(px, py))
                if len(points) >= 2:
                    pygame.draw.lines(self.screen, (255, 210, 80), False, points, 2)
                    for idx, pt in enumerate(points):
                        pygame.draw.circle(self.screen, (255, 210, 80), pt, 4, 1)
                        if idx < 6:
                            draw_text_bg(
                                self.screen,
                                str(idx),
                                self.hud_font_small,
                                (255, 215, 150),
                                pt[0] + 4,
                                pt[1] - 10,
                                bg=(0, 0, 0, 120),
                                padding=2,
                            )

            target = player_data.get('debug_target')
            if isinstance(target, dict) and 'x' in target and 'y' in target:
                tx, ty = world_to_screen(float(target['x']), float(target['y']))
                pygame.draw.line(self.screen, (255, 120, 40), (cx, cy), (tx, ty), 2)
                pygame.draw.circle(self.screen, (255, 120, 40), (tx, ty), 5, 2)
                pygame.draw.circle(self.screen, (10, 10, 10), (tx, ty), 6, 1)

            waypoint = player_data.get('debug_waypoint')
            if isinstance(waypoint, dict) and 'x' in waypoint and 'y' in waypoint:
                wx, wy = world_to_screen(float(waypoint['x']), float(waypoint['y']))
                pygame.draw.circle(self.screen, (120, 220, 255), (wx, wy), 4, 1)

            current_angle = float(player_data.get('angle', 0.0) or 0.0)
            draw_heading(cx, cy, current_angle, 24, (80, 220, 255), 2)

            desired_angle = ai_dbg.get('desired_angle')
            if isinstance(desired_angle, (int, float)):
                draw_heading(cx, cy, float(desired_angle), 20, (255, 120, 255), 2)

            desired_heading = ai_dbg.get('desired_heading')
            if isinstance(desired_heading, (int, float)):
                draw_heading(cx, cy, float(desired_heading), 16, (255, 190, 90), 1)

            corridor_heading = player_data.get('debug_corridor_heading')
            if isinstance(corridor_heading, (int, float)):
                draw_heading(cx, cy, float(corridor_heading), 28, (120, 255, 120), 1)

            tile = ai_dbg.get('road_tile')
            if isinstance(tile, (list, tuple)) and len(tile) >= 2:
                tx = int(float(tile[0]))
                ty = int(float(tile[1]))
                rx, ry = world_to_screen(tx * tile_w, ty * tile_h)
                rw = max(1, int(tile_w * zoom))
                rh = max(1, int(tile_h * zoom))
                pygame.draw.rect(self.screen, (110, 170, 255), pygame.Rect(rx, ry, rw, rh), 1)

                tcx, tcy = world_to_screen(tx * tile_w + tile_w * 0.5, ty * tile_h + tile_h * 0.5)
                open_headings = ai_dbg.get('open_headings', [])
                if isinstance(open_headings, (list, tuple)):
                    ray_len = max(6, int(min(rw, rh) * 0.45))
                    for heading in open_headings:
                        if isinstance(heading, (int, float)):
                            draw_heading(tcx, tcy, float(heading), ray_len, (120, 255, 140), 1)

            ai_id = str(player_username).split(':', 1)[-1]
            kind = str(player_data.get('ai_kind', '')).upper()
            state = str(player_data.get('ai_state', '')).upper()

            debug_lines = [f"{kind} {state} {ai_id}"]

            mode = ai_dbg.get('mode')
            phase = ai_dbg.get('phase')
            if mode is not None or phase is not None:
                debug_lines.append(f"mode={fmt_value(mode)} phase={fmt_value(phase)}")

            speed = ai_dbg.get('speed', player_data.get('debug_speed'))
            desired_speed = ai_dbg.get('desired_speed')
            if isinstance(speed, (int, float)) and isinstance(desired_speed, (int, float)):
                debug_lines.append(f"spd={float(speed):.1f} -> {float(desired_speed):.1f}")
            elif isinstance(speed, (int, float)):
                debug_lines.append(f"spd={float(speed):.1f}")

            if isinstance(desired_heading, (int, float)):
                debug_lines.append(
                    f"head={heading_label(current_angle)}->{heading_label(float(desired_heading))}"
                )

            front_wall = ai_dbg.get('front_wall')
            front_blocker = ai_dbg.get('front_blocker')
            if isinstance(front_wall, (int, float)) or front_blocker is not None:
                debug_lines.append(
                    f"wall={fmt_value(front_wall)} block={fmt_value(front_blocker)}"
                )

            path_idx = player_data.get('debug_path_index', ai_dbg.get('path_index'))
            path_len = player_data.get('debug_path_len', ai_dbg.get('path_len'))
            if path_idx is not None or path_len is not None:
                debug_lines.append(f"path={fmt_value(path_idx)}/{fmt_value(path_len)}")

            open_headings = ai_dbg.get('open_headings')
            if isinstance(open_headings, (list, tuple)) and open_headings:
                labels = [heading_label(h) for h in open_headings if isinstance(h, (int, float))]
                if labels:
                    debug_lines.append("open=" + ",".join(labels))

            shown = {
                'mode',
                'phase',
                'speed',
                'desired_speed',
                'desired_heading',
                'front_wall',
                'front_blocker',
                'path_index',
                'path_len',
                'open_headings',
                'road_tile',
            }
            for key in sorted(ai_dbg.keys()):
                if key in shown:
                    continue
                debug_lines.append(f"{key}={fmt_value(ai_dbg.get(key))}")

            label_x = cx + 10
            if label_x > self.screen_width - 280:
                label_x = cx - 280
            label_y = cy - 20
            if label_y < 6:
                label_y = 6

            for line in debug_lines:
                if label_y > self.screen_height - 16:
                    break
                draw_text_bg(
                    self.screen,
                    line,
                    self.hud_font_small,
                    (255, 255, 210),
                    int(label_x),
                    int(label_y),
                    bg=(0, 0, 0, 155),
                    padding=3,
                )
                label_y += self.hud_font_small.get_height() + 3

            if isinstance(target, dict) and 'x' in target and 'y' in target:
                tx = float(target['x'])
                ty = float(target['y'])
                dist = math.hypot((tx - x), (ty - y))
                desc = f"dist {int(dist)}"
                draw_text_bg(self.screen, desc, self.hud_font_small, (255, 190, 120), cx + 8, cy + 4, bg=(0, 0, 0, 150), padding=3)

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
        hover_target = None
        if self.phone_ui and hasattr(self.phone_ui, 'get_hovered_mission_target'):
            hover_target = self.phone_ui.get_hovered_mission_target()

        # Dessiner les marqueurs des missions disponibles
        for m in ms.available_missions:
            icon = str(getattr(m, 'cargo_icon', 'PKG'))
            hover_match = (
                isinstance(hover_target, dict)
                and abs(float(hover_target.get('x', -999999.0)) - float(m.pickup.get('x', 0.0))) < 1e-3
                and abs(float(hover_target.get('y', -999999.0)) - float(m.pickup.get('y', 0.0))) < 1e-3
            )
            self._draw_world_marker(
                m.pickup['x'],
                m.pickup['y'],
                (255, 220, 60),
                m.pickup['name'],
                14 if hover_match else 12,
                icon_text=icon,
                marker_kind='pickup',
                cargo_type=getattr(m, 'cargo_type', 'colis'),
                pulse=bool(hover_match),
            )

        # Marqueur mission active
        if ms.active_mission:
            am = ms.active_mission
            objective = ms.get_current_objective() if hasattr(ms, 'get_current_objective') else None
            is_party_choices = bool(getattr(am, 'party_mission', False) and getattr(am, 'picked_up', False))

            if is_party_choices:
                start_idx = max(0, int(getattr(am, 'current_stop_index', 0) or 0))
                for offset, stop in enumerate(getattr(am, 'stops', [])[start_idx:]):
                    kind = str(stop.get('kind', 'pickup'))
                    marker_kind = 'dropoff' if kind == 'dropoff' else 'pickup'
                    color = (255, 80, 80) if kind == 'dropoff' else (0, 255, 120)
                    if kind == 'stop':
                        color = (80, 180, 255)

                    is_primary = (offset == 0)
                    label = str(stop.get('name', 'Objectif')).upper()
                    icon = str(stop.get('cargo_icon', getattr(am, 'cargo_icon', 'PKG')))
                    self._draw_world_marker(
                        float(stop.get('x', am.pickup['x'])),
                        float(stop.get('y', am.pickup['y'])),
                        color,
                        label,
                        18 if is_primary else 14,
                        icon_text=icon,
                        marker_kind=marker_kind,
                        cargo_type=stop.get('cargo_type', getattr(am, 'cargo_type', 'colis')),
                        pulse=is_primary,
                    )
            elif objective:
                kind = str(objective.get('kind', 'pickup'))
                marker_kind = 'dropoff' if kind == 'dropoff' else 'pickup'
                color = (255, 80, 80) if kind == 'dropoff' else (0, 255, 120)
                if kind == 'stop':
                    color = (80, 180, 255)
                icon = str(objective.get('cargo_icon', getattr(am, 'cargo_icon', 'PKG')))
                label = str(objective.get('name', 'Objectif')).upper()
                self._draw_world_marker(
                    float(objective.get('x', am.pickup['x'])),
                    float(objective.get('y', am.pickup['y'])),
                    color,
                    label,
                    18,
                    icon_text=icon,
                    marker_kind=marker_kind,
                    cargo_type=objective.get('cargo_type', getattr(am, 'cargo_type', 'colis')),
                    pulse=True,
                )

    def _draw_world_marker(self, world_x, world_y, color, label, radius, icon_text=None, marker_kind='default', cargo_type=None, pulse=False):
        """Dessine un marqueur circulaire à une position monde."""
        zoom = getattr(self.game_map, 'zoom', 1.0)
        sx = (world_x - self.camera_x) * zoom
        sy = (world_y - self.camera_y) * zoom
        # Marqueur taille fixe (pas zoomé)
        if -100 < sx < self.screen_width + 100 and -100 < sy < self.screen_height + 100:
            now = pygame.time.get_ticks() / 1000.0
            pulse_offset = int(2.5 * abs(math.sin(now * 3.0))) if pulse else 0
            outer_r = radius + pulse_offset

            # Halo + beacon
            halo = pygame.Surface((outer_r * 6, outer_r * 6), pygame.SRCALPHA)
            pygame.draw.circle(halo, (*color, 45), (halo.get_width() // 2, halo.get_height() // 2), outer_r + 6)
            self.screen.blit(halo, (int(sx - halo.get_width() / 2), int(sy - halo.get_height() / 2)))
            pygame.draw.line(
                self.screen,
                (*color, 120),
                (int(sx), int(sy) - outer_r - 2),
                (int(sx), int(sy) - outer_r - 22),
                2,
            )

            # Ring marker
            pygame.draw.circle(self.screen, color, (int(sx), int(sy)), outer_r, 3)
            pygame.draw.circle(self.screen, (255, 255, 255), (int(sx), int(sy)), max(2, outer_r - 6), 2)

            # Object icon in center
            self._render_mission_object_icons(
                world_x,
                world_y,
                marker_kind=marker_kind,
                cargo_type=cargo_type,
                icon_hint=icon_text,
            )

            label_surf = self.hud_font_small.render(label, True, color)
            self.screen.blit(label_surf, (int(sx) - label_surf.get_width() // 2, int(sy) - outer_r - 24))

    def _render_mission_object_icons(self, world_x, world_y, marker_kind='pickup', cargo_type=None, icon_hint=None):
        """Dessine l'icône objective (PNG si dispo, fallback sinon) au centre d'un marqueur monde."""
        sprite = self._get_objective_sprite(cargo_type=cargo_type, marker_kind=marker_kind, icon_hint=icon_hint)
        if sprite is None:
            return

        zoom = getattr(self.game_map, 'zoom', 1.0)
        sx = (world_x - self.camera_x) * zoom
        sy = (world_y - self.camera_y) * zoom
        if -80 < sx < self.screen_width + 80 and -80 < sy < self.screen_height + 80:
            self.screen.blit(sprite, (int(sx - sprite.get_width() / 2), int(sy - sprite.get_height() / 2)))

    def _get_objective_sprite(self, cargo_type=None, marker_kind='pickup', icon_hint=None):
        """Retourne le sprite objectif à afficher selon le type de cargo et la cible (pickup/dropoff)."""
        kind = 'dropoff' if str(marker_kind).lower() == 'dropoff' else 'pickup'
        cargo_key = str(cargo_type or 'default').lower()
        cache_key = (kind, cargo_key)
        if cache_key in self._objective_sprite_cache:
            return self._objective_sprite_cache[cache_key]

        objective_dir = Path('assets/images/HUD/objectives')
        pickup_map = {
            'colis': ['pickup_package.png', 'pickup_default.png'],
            'alimentaire': ['pickup_food.png', 'pickup_default.png'],
            'documents': ['pickup_documents.png', 'pickup_default.png'],
            'medical': ['pickup_medical.png', 'pickup_default.png'],
            'vip': ['pickup_vip.png', 'pickup_default.png'],
            'urgent': ['pickup_urgent.png', 'pickup_default.png'],
            'materiel': ['pickup_heavy.png', 'pickup_default.png'],
            'lourd': ['pickup_heavy.png', 'pickup_default.png'],
            'industriel': ['pickup_heavy.png', 'pickup_default.png'],
            'default': ['pickup_default.png'],
        }
        dropoff_files = ['dropoff_default.png', 'delivery_default.png']

        if kind == 'dropoff':
            candidates = dropoff_files
        else:
            candidates = pickup_map.get(cargo_key, pickup_map['default'])

        sprite = None
        for filename in candidates:
            path = objective_dir / filename
            if path.exists():
                try:
                    img = pygame.image.load(str(path)).convert_alpha()
                    sprite = pygame.transform.smoothscale(img, (20, 20))
                    break
                except Exception:
                    sprite = None

        if sprite is None:
            sprite = self._build_objective_fallback_sprite(kind=kind, cargo_key=cargo_key, icon_hint=icon_hint)

        self._objective_sprite_cache[cache_key] = sprite
        return sprite

    def _build_objective_fallback_sprite(self, kind='pickup', cargo_key='default', icon_hint=None):
        surf = pygame.Surface((20, 20), pygame.SRCALPHA)
        if kind == 'dropoff':
            pygame.draw.rect(surf, (255, 255, 255), (3, 3, 14, 14), 2, border_radius=3)
            pygame.draw.line(surf, (255, 255, 255), (4, 4), (16, 16), 2)
            pygame.draw.line(surf, (255, 255, 255), (16, 4), (4, 16), 2)
            return surf

        pygame.draw.circle(surf, (255, 255, 255), (10, 10), 8, 2)
        text = str(icon_hint or cargo_key or 'PKG').upper()[:3]
        txt = self.hud_font_small.render(text, True, (255, 255, 255))
        surf.blit(txt, (10 - txt.get_width() // 2, 10 - txt.get_height() // 2))
        return surf

    def push_mission_result(self, result):
        """Empile un popup récapitulatif de fin de mission (succès/échec)."""
        if not isinstance(result, dict):
            return

        mission = result.get('mission', {}) if isinstance(result.get('mission', {}), dict) else {}
        pickup = mission.get('pickup', {}) if isinstance(mission.get('pickup', {}), dict) else {}
        delivery = mission.get('delivery', {}) if isinstance(mission.get('delivery', {}), dict) else {}

        popup = {
            'success': bool(result.get('success', False)),
            'reason': str(result.get('reason', 'completed')),
            'type': str(mission.get('type', 'standard')),
            'route': f"{pickup.get('name', '?')} -> {delivery.get('name', '?')}",
            'cargo': str(mission.get('cargo_type', 'colis')),
            'cargo_icon': str(mission.get('cargo_icon', 'PKG')),
            'cargo_weight': int(float(mission.get('cargo_weight', 0.0) or 0.0)),
            'reward': int(mission.get('reward', 0) or 0),
            'money_delta': int(result.get('money_delta', mission.get('reward', 0)) or 0),
            'elapsed_time': int(float(result.get('elapsed_time', 0.0) or 0.0)),
            'remaining_time': int(float(result.get('remaining_time', 0.0) or 0.0)),
        }

        self._mission_result_popup = popup
        self._mission_result_timer = self._mission_result_duration

    def _render_mission_result_popup(self):
        """Popup de synthèse affiché juste après une fin de mission."""
        if not self._mission_result_popup or self._mission_result_timer <= 0.0:
            return

        p = self._mission_result_popup
        success = bool(p.get('success', False))
        title = self._t("hud.popup.success") if success else self._t("hud.popup.failed")
        accent = (80, 235, 130) if success else (255, 95, 95)
        icon = p.get('cargo_icon', 'PKG')
        reward = int(p.get('money_delta', p.get('reward', 0)) or 0)
        elapsed = int(p.get('elapsed_time', 0) or 0)
        remaining = int(p.get('remaining_time', 0) or 0)

        fade = min(1.0, self._mission_result_timer / max(0.01, self._mission_result_duration))
        alpha = int(200 + 55 * min(1.0, fade + 0.2))

        w = min(680, self.screen_width - 60)
        h = 158
        x = (self.screen_width - w) // 2
        y = max(70, int(self.screen_height * 0.13))

        panel = pygame.Surface((w, h), pygame.SRCALPHA)
        panel.fill((12, 14, 22, alpha))
        pygame.draw.rect(panel, accent, (0, 0, w, h), 2, border_radius=10)

        title_s = self.hud_font_big.render(title, True, accent)
        panel.blit(title_s, (16, 10))

        type_s = self.hud_font_small.render(
            f"{self._t('hud.popup.type')}: {self._mission_type_label(p.get('type', 'standard'))}  |  {self._t('hud.popup.object')}: {icon}",
            True,
            (230, 230, 245),
        )
        panel.blit(type_s, (18, 48))

        route_s = self.hud_font_small.render(str(p.get('route', '')), True, (190, 210, 255))
        panel.blit(route_s, (18, 72))

        cargo_s = self.hud_font_small.render(
            f"{self._t('hud.cargo')}: {self._cargo_label(p.get('cargo', 'colis'))} ({int(p.get('cargo_weight', 0) or 0)}kg)",
            True,
            (220, 220, 220),
        )
        panel.blit(cargo_s, (18, 96))

        if success:
            right_1 = self.hud_font_small.render(f"{self._t('hud.popup.gain')}: +{reward}$", True, (110, 255, 130))
            right_2 = self.hud_font_small.render(f"{self._t('hud.popup.time')}: {elapsed}s  |  {self._t('hud.popup.remaining')}: {remaining}s", True, (220, 235, 255))
        else:
            reason = self._mission_reason_label(p.get('reason', 'failed'))
            right_1 = self.hud_font_small.render(f"{self._t('hud.popup.reason')}: {reason}", True, (255, 135, 135))
            right_2 = self.hud_font_small.render(f"{self._t('hud.popup.total_time')}: {elapsed}s", True, (220, 220, 220))

        panel.blit(right_1, (w - right_1.get_width() - 18, 74))
        panel.blit(right_2, (w - right_2.get_width() - 18, 98))

        self.screen.blit(panel, (x, y))

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