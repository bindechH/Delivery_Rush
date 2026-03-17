"""
Module interface téléphone pour Delivery Rush
Interface smartphone avec applications : Livraisons, GPS, Boutique, Stats.
Animation slide-up, achat de véhicules, carte complète.
"""

import math
import pygame
from .missions import MISSION_LOCATIONS
from .player import VEHICLE_CATALOG, VEHICLE_COLORS, resolve_car_frame_path

# === COULEURS ===
PHONE_BG = (18, 18, 28)
PHONE_HEADER = (30, 30, 45)
PHONE_NOTCH = (10, 10, 18)
PHONE_TEXT = (240, 240, 250)
PHONE_TEXT_DIM = (140, 140, 160)
PHONE_ACCENT = (70, 130, 230)
PHONE_GREEN = (80, 200, 100)
PHONE_RED = (230, 70, 70)
PHONE_YELLOW = (255, 200, 50)
PHONE_CARD_BG = (30, 30, 48)
PHONE_CARD_HOVER = (45, 45, 68)
PHONE_BORDER = (60, 60, 90)
PHONE_STATUS_BAR = (12, 12, 20)

# === DIMENSIONS ===
PHONE_WIDTH = 300
PHONE_HEIGHT = 520
PHONE_RADIUS = 18
# Screen area within the PNG frame (scaled from 178×302 original)
PHONE_SCREEN_X = 24
PHONE_SCREEN_Y = 75
PHONE_SCREEN_W = 259
PHONE_SCREEN_H = 375
APP_ICON_SIZE = 48
APP_GRID_COLS = 3
APP_GRID_ROWS = 2
APP_PADDING = 26

# === APPS ===
APPS = [
    {"id": "missions", "name": "Livraisons", "icon": "\u25a3", "color": (70, 180, 70)},
    {"id": "gps",      "name": "GPS",        "icon": "\u25c9", "color": (70, 130, 230)},
    {"id": "shop",     "name": "Boutique",   "icon": "\u2605", "color": (230, 180, 50)},
    {"id": "garage",   "name": "Garage",     "icon": "\u25a0", "color": (180, 100, 50)},
    {"id": "stats",    "name": "Stats",      "icon": "\u25b2", "color": (180, 80, 230)},
]


class PhoneUI:
    """Interface smartphone in-game avec applications et animation slide-up."""

    def __init__(self, screen_width, screen_height, mission_system):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.mission_system = mission_system
        self.player = None  # Set externally
        self.visible = False

        # Animation slide-up
        self.anim_progress = 0.0  # 0=caché, 1=affiché
        self.anim_target = 0.0
        self.anim_speed = 5.0

        # Navigation
        self.current_screen = "home"  # home, missions, gps, shop, garage, stats
        self.scroll_offset = 0
        self.hovered_mission = -1
        self.shop_scroll = 0
        self.shop_selected_colors = {}  # model -> color index
        self.garage_scroll = 0

        # Keyboard navigation
        self.kb_focus = 0  # focused item index on current screen
        self.home_focus = 0  # which app icon is focused on home

        # Polices
        self.font_title = pygame.font.Font("assets/fonts/ari-w9500-bold.ttf", 17)
        self.font_title.set_bold(True)
        self.font_text = pygame.font.Font("assets/fonts/ari-w9500-bold.ttf", 13)
        self.font_text.set_bold(True)
        self.font_small = pygame.font.Font("assets/fonts/ari-w9500-bold.ttf", 11)
        self.font_small.set_bold(True)
        self.font_gps = pygame.font.Font("assets/fonts/ari-w9500-bold.ttf", 7)
        self.font_gps.set_bold(True)
        self.font_icon = pygame.font.SysFont("Segoe UI Symbol", 28)
        self.font_app_label = pygame.font.Font("assets/fonts/ari-w9500-bold.ttf", 11)
        self.font_app_label.set_bold(True)

        # Phone frame image
        try:
            self._phone_frame_raw = pygame.image.load("assets/images/HUD/phone/Rushphone.png").convert_alpha()
            self._phone_frame = pygame.transform.smoothscale(self._phone_frame_raw, (PHONE_WIDTH, PHONE_HEIGHT))
        except Exception:
            self._phone_frame = None

        # Phone position: bottom-right corner, slide up from bottom
        self.phone_x = screen_width - PHONE_WIDTH - 15
        self.phone_y_target = screen_height - PHONE_HEIGHT - 15
        self.phone_y_hidden = screen_height - 30  # peek: show 30px strip when closed

        # Car preview cache for shop
        self._car_preview_cache = {}

    def toggle(self):
        """Ouvrir/fermer le téléphone avec animation."""
        if self.anim_target == 0.0:
            self.visible = True
            self.anim_target = 1.0
        else:
            self.anim_target = 0.0
        self.scroll_offset = 0
        self.shop_scroll = 0
        self.garage_scroll = 0
        self.hovered_mission = -1
        self.kb_focus = 0
        self.home_focus = 0

    def update(self, dt):
        """Met à jour l'animation slide-up/down."""
        if self.anim_progress < self.anim_target:
            self.anim_progress = min(1.0, self.anim_progress + self.anim_speed * dt)
        elif self.anim_progress > self.anim_target:
            self.anim_progress = max(0.0, self.anim_progress - self.anim_speed * dt)
            if self.anim_progress == 0.0:
                self.visible = False
                self.current_screen = "home"

    def _phone_y(self):
        """Position Y du téléphone basée sur l'animation."""
        t = self.anim_progress
        # Ease-out cubic
        t_ease = 1.0 - (1.0 - t) ** 3
        return int(self.phone_y_hidden + (self.phone_y_target - self.phone_y_hidden) * t_ease)

    def _phone_rect(self):
        return pygame.Rect(self.phone_x, self._phone_y(), PHONE_WIDTH, PHONE_HEIGHT)

    def handle_events(self, events):
        """Gérer les interactions avec le téléphone (souris + clavier)."""
        if not self.visible or self.anim_progress < 0.8:
            return
        phone_rect = self._phone_rect()

        for event in events:
            # Keyboard controls
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE, pygame.K_DELETE):
                    if self.current_screen == "home":
                        self.toggle()  # Close phone
                    else:
                        self.current_screen = "home"
                        self.scroll_offset = 0
                        self.shop_scroll = 0
                        self.garage_scroll = 0
                        self.kb_focus = 0
                    continue

                if event.key == pygame.K_RETURN:
                    self._handle_kb_enter()
                    continue

                if event.key == pygame.K_UP:
                    self._handle_kb_navigate(-1)
                    continue
                if event.key == pygame.K_DOWN:
                    self._handle_kb_navigate(1)
                    continue
                if event.key == pygame.K_LEFT:
                    self._handle_kb_left()
                    continue
                if event.key == pygame.K_RIGHT:
                    self._handle_kb_right()
                    continue

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos
                if not phone_rect.collidepoint(mx, my):
                    continue
                lx = mx - phone_rect.x - PHONE_SCREEN_X
                ly = my - phone_rect.y - PHONE_SCREEN_Y
                if lx < 0 or ly < 0 or lx >= PHONE_SCREEN_W or ly >= PHONE_SCREEN_H:
                    continue

                if self.current_screen == "home":
                    self._handle_home_click(lx, ly)
                elif self.current_screen == "missions":
                    self._handle_missions_click(lx, ly)
                elif self.current_screen == "shop":
                    self._handle_shop_click(lx, ly)
                elif self.current_screen == "garage":
                    self._handle_garage_click(lx, ly)
                elif self.current_screen in ("stats", "gps"):
                    self._handle_back_click(lx, ly)

            elif event.type == pygame.MOUSEWHEEL:
                if phone_rect.collidepoint(*pygame.mouse.get_pos()):
                    if self.current_screen == "missions":
                        self.scroll_offset = max(0, self.scroll_offset - event.y * 30)
                    elif self.current_screen == "shop":
                        self.shop_scroll = max(0, self.shop_scroll - event.y * 35)
                    elif self.current_screen == "garage":
                        self.garage_scroll = max(0, self.garage_scroll - event.y * 35)

            elif event.type == pygame.MOUSEMOTION:
                if self.current_screen == "missions":
                    self._update_hover(event.pos, phone_rect)

    def _handle_kb_enter(self):
        """Handle Enter key on current screen."""
        if self.current_screen == "home":
            if 0 <= self.home_focus < len(APPS):
                self.current_screen = APPS[self.home_focus]["id"]
                self.scroll_offset = 0
                self.shop_scroll = 0
                self.garage_scroll = 0
                self.kb_focus = 0
        elif self.current_screen == "missions":
            ms = self.mission_system
            if ms.active_mission:
                return  # Can't accept while one is active
            if 0 <= self.kb_focus < len(ms.available_missions):
                ms.accept_mission(ms.available_missions[self.kb_focus].id)
        elif self.current_screen == "shop":
            sorted_vehicles = sorted(VEHICLE_CATALOG.items(), key=lambda x: x[1]["price"])
            if 0 <= self.kb_focus < len(sorted_vehicles):
                model, stats = sorted_vehicles[self.kb_focus]
                sel_ci = self.shop_selected_colors.get(model, 0)
                sel_color = VEHICLE_COLORS[sel_ci]
                if self.mission_system.has_car(model, sel_color):
                    if self.player:
                        self.player.change_car((model, sel_color))
                else:
                    self.mission_system.buy_car(model, sel_color, stats["price"])
        elif self.current_screen == "garage":
            owned = self.mission_system.owned_cars
            if 0 <= self.kb_focus < len(owned):
                car_data = owned[self.kb_focus]
                if self.player:
                    self.player.change_car((car_data["model"], car_data["color"]))

    def _handle_kb_navigate(self, direction):
        """Handle up/down navigation with auto-scroll."""
        if self.current_screen == "home":
            cols = APP_GRID_COLS
            new_focus = self.home_focus + direction * cols
            if 0 <= new_focus < len(APPS):
                self.home_focus = new_focus
        elif self.current_screen == "missions":
            ms = self.mission_system
            max_items = len(ms.available_missions)
            self.kb_focus = max(0, min(max_items - 1, self.kb_focus + direction))
            # Auto-scroll to keep focused item visible
            card_h = 60
            clip_h = PHONE_SCREEN_H - 22
            offset = 0
            if ms.active_mission:
                offset = 72
            offset += 22  # "Disponibles" label
            focus_y = offset + self.kb_focus * card_h
            if focus_y < self.scroll_offset:
                self.scroll_offset = focus_y
            elif focus_y + 55 > self.scroll_offset + clip_h:
                self.scroll_offset = focus_y + 55 - clip_h
        elif self.current_screen == "shop":
            sorted_vehicles = sorted(VEHICLE_CATALOG.items(), key=lambda x: x[1]["price"])
            self.kb_focus = max(0, min(len(sorted_vehicles) - 1, self.kb_focus + direction))
            # Auto-scroll to keep focused item visible
            card_h = 130
            card_gap = 8
            clip_h = PHONE_SCREEN_H - 22
            focus_y = self.kb_focus * (card_h + card_gap)
            if focus_y < self.shop_scroll:
                self.shop_scroll = focus_y
            elif focus_y + card_h > self.shop_scroll + clip_h:
                self.shop_scroll = focus_y + card_h - clip_h
        elif self.current_screen == "garage":
            owned = self.mission_system.owned_cars
            self.kb_focus = max(0, min(len(owned) - 1, self.kb_focus + direction))
            # Auto-scroll to keep focused item visible
            card_h = 50
            card_gap = 6
            clip_h = PHONE_SCREEN_H - 22
            focus_y = self.kb_focus * (card_h + card_gap)
            if focus_y < self.garage_scroll:
                self.garage_scroll = focus_y
            elif focus_y + card_h > self.garage_scroll + clip_h:
                self.garage_scroll = focus_y + card_h - clip_h

    def _handle_kb_left(self):
        if self.current_screen == "home":
            if self.home_focus > 0:
                self.home_focus -= 1
        elif self.current_screen == "shop":
            sorted_vehicles = sorted(VEHICLE_CATALOG.items(), key=lambda x: x[1]["price"])
            if 0 <= self.kb_focus < len(sorted_vehicles):
                model = sorted_vehicles[self.kb_focus][0]
                ci = self.shop_selected_colors.get(model, 0)
                if ci > 0:
                    self.shop_selected_colors[model] = ci - 1

    def _handle_kb_right(self):
        if self.current_screen == "home":
            if self.home_focus < len(APPS) - 1:
                self.home_focus += 1
        elif self.current_screen == "shop":
            sorted_vehicles = sorted(VEHICLE_CATALOG.items(), key=lambda x: x[1]["price"])
            if 0 <= self.kb_focus < len(sorted_vehicles):
                model = sorted_vehicles[self.kb_focus][0]
                ci = self.shop_selected_colors.get(model, 0)
                if ci < len(VEHICLE_COLORS) - 1:
                    self.shop_selected_colors[model] = ci + 1

    def _handle_home_click(self, lx, ly):
        """Écran d'accueil → ouvrir une app."""
        sw = PHONE_SCREEN_W
        grid_start_y = 60
        grid_start_x = (sw - (APP_GRID_COLS * (APP_ICON_SIZE + APP_PADDING) - APP_PADDING)) // 2
        for i, app in enumerate(APPS):
            col = i % APP_GRID_COLS
            row = i // APP_GRID_COLS
            ax = grid_start_x + col * (APP_ICON_SIZE + APP_PADDING)
            ay = grid_start_y + row * (APP_ICON_SIZE + APP_PADDING + 18)
            if ax <= lx <= ax + APP_ICON_SIZE and ay <= ly <= ay + APP_ICON_SIZE:
                self.current_screen = app["id"]
                self.scroll_offset = 0
                self.shop_scroll = 0
                return

    def _handle_back_click(self, lx, ly):
        """Bouton retour en haut à gauche."""
        if lx < 50 and ly < 22:
            self.current_screen = "home"
            self.scroll_offset = 0
            self.shop_scroll = 0

    def _handle_missions_click(self, lx, ly):
        """Clic dans l'écran missions."""
        # Back button
        if lx < 50 and ly < 22:
            self.current_screen = "home"
            return

        ms = self.mission_system
        content_y = 22 - self.scroll_offset

        # Mission active → abandon
        if ms.active_mission:
            abandon_y = content_y + 52
            if PHONE_SCREEN_W - 80 < lx < PHONE_SCREEN_W - 10 and abandon_y < ly < abandon_y + 20:
                ms.abandon_mission()
                return
            content_y += 72

        content_y += 22

        # Missions disponibles → accepter
        for mission in ms.available_missions:
            if 8 < lx < PHONE_SCREEN_W - 8 and content_y < ly < content_y + 55:
                ms.accept_mission(mission.id)
                return
            content_y += 60

    def _handle_shop_click(self, lx, ly):
        """Clic dans la boutique."""
        if lx < 50 and ly < 22:
            self.current_screen = "home"
            return

        ms = self.mission_system
        sorted_vehicles = sorted(VEHICLE_CATALOG.items(), key=lambda x: x[1]["price"])
        card_h = 130
        card_gap = 8
        content_y = 22 - self.shop_scroll

        for model, stats in sorted_vehicles:
            # Boutons couleur
            color_y = content_y + 20
            color_x_start = PHONE_SCREEN_W - 8 - len(VEHICLE_COLORS) * 14
            for ci, color_name in enumerate(VEHICLE_COLORS):
                cx = color_x_start + ci * 14
                if cx <= lx <= cx + 12 and color_y <= ly <= color_y + 12:
                    self.shop_selected_colors[model] = ci
                    return

            # Bouton acheter/équiper
            btn_y = content_y + card_h - 26
            btn_x = PHONE_SCREEN_W - 88
            if btn_x <= lx <= btn_x + 76 and btn_y <= ly <= btn_y + 22:
                sel_ci = self.shop_selected_colors.get(model, 0)
                sel_color = VEHICLE_COLORS[sel_ci]
                if ms.has_car(model, sel_color):
                    # Équiper
                    if self.player:
                        self.player.change_car((model, sel_color))
                else:
                    ms.buy_car(model, sel_color, stats["price"])
                return

            content_y += card_h + card_gap

    def _handle_garage_click(self, lx, ly):
        """Clic dans le garage."""
        if lx < 50 and ly < 22:
            self.current_screen = "home"
            return
        ms = self.mission_system
        card_h = 50
        card_gap = 6
        content_y = 22 - self.garage_scroll
        for car_data in ms.owned_cars:
            if 8 < lx < PHONE_SCREEN_W - 8 and content_y < ly < content_y + card_h:
                if self.player:
                    self.player.change_car((car_data["model"], car_data["color"]))
                return
            content_y += card_h + card_gap

    def _update_hover(self, pos, phone_rect):
        """Met à jour le survol des missions."""
        self.hovered_mission = -1
        mx, my = pos
        if not phone_rect.collidepoint(mx, my):
            return
        lx = mx - phone_rect.x - PHONE_SCREEN_X
        ly = my - phone_rect.y - PHONE_SCREEN_Y
        if lx < 0 or ly < 0 or lx >= PHONE_SCREEN_W or ly >= PHONE_SCREEN_H:
            return

        ms = self.mission_system
        content_y = 22 - self.scroll_offset
        if ms.active_mission:
            content_y += 72
        content_y += 22

        for i, mission in enumerate(ms.available_missions):
            if 8 < lx < PHONE_SCREEN_W - 8 and content_y < ly < content_y + 55:
                self.hovered_mission = i
                return
            content_y += 60

    # === RENDU ===

    def render(self, screen, player=None, game_map=None):
        """Rendre le téléphone avec animation slide-up. Always show peek strip."""
        self.player = player

        py = self._phone_y()

        # Always draw something (peek strip when closed, or full phone when open)
        if not self.visible and self.anim_progress <= 0.0:
            # Draw a small peek strip at bottom-right
            peek_h = 30
            peek_w = PHONE_WIDTH
            peek_x = self.phone_x
            peek_y = self.screen_height - peek_h
            peek_surf = pygame.Surface((peek_w, peek_h), pygame.SRCALPHA)
            pygame.draw.rect(peek_surf, PHONE_BG, (0, 0, peek_w, peek_h), border_radius=PHONE_RADIUS)
            pygame.draw.rect(peek_surf, PHONE_BORDER, (0, 0, peek_w, peek_h), 2, border_radius=PHONE_RADIUS)
            # Small label
            peek_label = self.font_small.render("TELEPHONE  [UP]", True, PHONE_TEXT_DIM)
            peek_surf.blit(peek_label, (peek_w // 2 - peek_label.get_width() // 2, 8))
            screen.blit(peek_surf, (peek_x, peek_y))
            return

        # Phone surface
        phone_surf = pygame.Surface((PHONE_WIDTH, PHONE_HEIGHT), pygame.SRCALPHA)

        # Content surface (fits inside the phone PNG screen area)
        content = pygame.Surface((PHONE_SCREEN_W, PHONE_SCREEN_H), pygame.SRCALPHA)
        content.fill(PHONE_BG)

        # Contenu selon l'écran actuel
        if self.current_screen == "home":
            self._render_home(content)
        elif self.current_screen == "missions":
            self._render_missions(content)
        elif self.current_screen == "gps":
            self._render_gps(content, player, game_map)
        elif self.current_screen == "shop":
            self._render_shop(content)
        elif self.current_screen == "garage":
            self._render_garage(content)
        elif self.current_screen == "stats":
            self._render_stats(content)

        # Blit content into phone at screen position
        phone_surf.blit(content, (PHONE_SCREEN_X, PHONE_SCREEN_Y))

        # Overlay phone frame image
        if self._phone_frame:
            phone_surf.blit(self._phone_frame, (0, 0))

        screen.blit(phone_surf, (self.phone_x, py))

    def _render_home(self, surf):
        """Écran d'accueil avec icônes d'applications."""
        sw = surf.get_width()
        sh = surf.get_height()

        # Status line only on home
        money_txt = self.font_small.render(f"${self.mission_system.money}", True, PHONE_GREEN)
        title_txt = self.font_small.render("DELIVERY RUSH", True, PHONE_TEXT_DIM)
        surf.blit(title_txt, (6, 2))
        surf.blit(money_txt, (sw - money_txt.get_width() - 6, 2))

        title = self.font_title.render("Applications", True, PHONE_TEXT)
        surf.blit(title, (sw // 2 - title.get_width() // 2, 28))

        grid_start_y = 60
        grid_start_x = (sw - (APP_GRID_COLS * (APP_ICON_SIZE + APP_PADDING) - APP_PADDING)) // 2

        for i, app in enumerate(APPS):
            col = i % APP_GRID_COLS
            row = i // APP_GRID_COLS
            ax = grid_start_x + col * (APP_ICON_SIZE + APP_PADDING)
            ay = grid_start_y + row * (APP_ICON_SIZE + APP_PADDING + 18)

            # Keyboard focus highlight
            if i == self.home_focus:
                pygame.draw.rect(surf, (255, 255, 255), (ax - 4, ay - 4, APP_ICON_SIZE + 8, APP_ICON_SIZE + 8), 2, border_radius=14)

            pygame.draw.rect(surf, app["color"], (ax, ay, APP_ICON_SIZE, APP_ICON_SIZE), border_radius=12)
            icon_surf = self.font_icon.render(app["icon"], True, (255, 255, 255))
            ix = ax + (APP_ICON_SIZE - icon_surf.get_width()) // 2
            iy = ay + (APP_ICON_SIZE - icon_surf.get_height()) // 2
            surf.blit(icon_surf, (ix, iy))
            label = self.font_app_label.render(app["name"], True, PHONE_TEXT_DIM)
            surf.blit(label, (ax + APP_ICON_SIZE // 2 - label.get_width() // 2, ay + APP_ICON_SIZE + 4))

        ms = self.mission_system
        if ms.active_mission:
            notif = self.font_small.render("Mission en cours...", True, PHONE_GREEN)
            surf.blit(notif, (sw // 2 - notif.get_width() // 2, sh - 40))

    def _render_back_button(self, surf, title_text):
        """Dessine le header avec bouton retour et titre."""
        y = 2
        back = self.font_title.render("< ", True, PHONE_ACCENT)
        surf.blit(back, (6, y))
        title = self.font_title.render(title_text, True, PHONE_TEXT)
        surf.blit(title, (26, y))

    def _render_missions(self, surf):
        """App Livraisons : mission active + disponibles."""
        self._render_back_button(surf, "Livraisons")
        ms = self.mission_system
        sw = surf.get_width()
        sh = surf.get_height()

        clip_y = 22
        clip_h = sh - clip_y
        y = 22 - self.scroll_offset
        clip_surf = pygame.Surface((sw - 8, clip_h), pygame.SRCALPHA)
        local_y = y - clip_y

        # Mission active
        if ms.active_mission:
            self._draw_active_mission(clip_surf, ms.active_mission, 0, local_y)
            local_y += 72

        # Séparateur
        label = self.font_text.render("Disponibles", True, PHONE_TEXT_DIM)
        clip_surf.blit(label, (4, local_y))
        local_y += 22

        if not ms.available_missions:
            no_msg = self.font_small.render("Aucune mission", True, PHONE_TEXT_DIM)
            clip_surf.blit(no_msg, (4, local_y))
        else:
            for i, mission in enumerate(ms.available_missions):
                bg_color = PHONE_CARD_HOVER if (i == self.hovered_mission or i == self.kb_focus) else PHONE_CARD_BG
                self._draw_mission_card(clip_surf, mission, 0, local_y, clip_surf.get_width(), 55, bg_color)
                local_y += 60

        surf.blit(clip_surf, (4, clip_y))

    def _draw_active_mission(self, surf, mission, x, y):
        """Dessine la mission active."""
        w = surf.get_width()
        card = pygame.Surface((w, 65), pygame.SRCALPHA)
        card.fill((30, 65, 30))
        pygame.draw.rect(card, PHONE_GREEN, (0, 0, w, 65), 2, border_radius=6)

        type_color = self._type_color(mission.type)
        label = self.font_small.render(f"[{mission.type.upper()}] EN COURS", True, type_color)
        card.blit(label, (5, 4))

        route = self.font_small.render(
            f"{mission.pickup['name']} -> {mission.delivery['name']}", True, PHONE_TEXT
        )
        card.blit(route, (5, 20))

        time_color = PHONE_RED if mission.time_remaining < 30 else PHONE_TEXT
        timer = self.font_small.render(f"{int(mission.time_remaining)}s", True, time_color)
        card.blit(timer, (5, 40))

        reward = self.font_small.render(f"{mission.reward}$", True, PHONE_GREEN)
        card.blit(reward, (w - reward.get_width() - 8, 40))

        status_text = "Allez au ramassage" if not mission.picked_up else "Livrez le colis"
        status = self.font_small.render(status_text, True, PHONE_YELLOW)
        card.blit(status, (w - status.get_width() - 5, 4))

        # Bouton abandon
        abandon = self.font_small.render("[Abandon]", True, PHONE_RED)
        card.blit(abandon, (w - abandon.get_width() - 5, 48))

        surf.blit(card, (x, y))

    def _draw_mission_card(self, surf, mission, x, y, w, h, bg_color):
        """Dessine une carte de mission disponible."""
        card = pygame.Surface((w, h), pygame.SRCALPHA)
        card.fill(bg_color)
        pygame.draw.rect(card, PHONE_BORDER, (0, 0, w, h), 1, border_radius=6)

        type_color = self._type_color(mission.type)
        label = self.font_small.render(f"[{mission.type.upper()}]", True, type_color)
        card.blit(label, (5, 4))

        route = self.font_small.render(
            f"{mission.pickup['name']} -> {mission.delivery['name']}", True, PHONE_TEXT
        )
        card.blit(route, (5, 20))

        timer = self.font_small.render(f"{int(mission.time_limit)}s", True, PHONE_TEXT_DIM)
        card.blit(timer, (5, 36))

        reward = self.font_text.render(f"{mission.reward}$", True, PHONE_GREEN)
        card.blit(reward, (w - reward.get_width() - 8, 18))

        surf.blit(card, (x, y))

    def _render_gps(self, surf, player=None, game_map=None):
        """App GPS : carte complète avec marqueurs."""
        self._render_back_button(surf, "GPS")
        ms = self.mission_system
        sw = surf.get_width()
        sh = surf.get_height()

        map_area_y = 22
        map_size = min(sw - 16, sh - map_area_y - 50)
        map_x = (sw - map_size) // 2
        map_y = map_area_y + 4

        map_surf = pygame.Surface((map_size, map_size), pygame.SRCALPHA)
        map_surf.fill((25, 40, 25))
        pygame.draw.rect(map_surf, PHONE_BORDER, (0, 0, map_size, map_size), 1, border_radius=4)

        map_w = game_map.width_px if game_map else 8192
        map_h = game_map.height_px if game_map else 8192
        sx = map_size / map_w
        sy = map_size / map_h

        # Points d'intérêt
        for loc in MISSION_LOCATIONS:
            lx = int(loc['x'] * sx)
            ly = int(loc['y'] * sy)
            pygame.draw.circle(map_surf, (60, 60, 60), (lx, ly), 3)
            name_surf = self.font_gps.render(loc['name'][:8], True, (100, 100, 100))
            map_surf.blit(name_surf, (lx + 4, ly - 5))

        # Missions disponibles
        for m in ms.available_missions:
            px = int(m.pickup['x'] * sx)
            py_ = int(m.pickup['y'] * sy)
            pygame.draw.circle(map_surf, PHONE_YELLOW, (px, py_), 4)

        # Mission active
        if ms.active_mission:
            m = ms.active_mission
            if not m.picked_up:
                px = int(m.pickup['x'] * sx)
                py_ = int(m.pickup['y'] * sy)
                pygame.draw.circle(map_surf, PHONE_GREEN, (px, py_), 6)
                pygame.draw.circle(map_surf, (255, 255, 255), (px, py_), 6, 1)
            dx = int(m.delivery['x'] * sx)
            dy = int(m.delivery['y'] * sy)
            pygame.draw.circle(map_surf, PHONE_RED, (dx, dy), 6)
            pygame.draw.circle(map_surf, (255, 255, 255), (dx, dy), 6, 1)

        # Joueur
        if player:
            ppx = int((player.x + player.size / 2) * sx)
            ppy = int((player.y + player.size / 2) * sy)
            pygame.draw.circle(map_surf, PHONE_ACCENT, (ppx, ppy), 5)
            pygame.draw.circle(map_surf, (255, 255, 255), (ppx, ppy), 5, 1)
            rad = math.radians(player.angle)
            ax = int(ppx + math.cos(rad) * 10)
            ay = int(ppy + math.sin(rad) * 10)
            pygame.draw.line(map_surf, (255, 255, 255), (ppx, ppy), (ax, ay), 2)

        surf.blit(map_surf, (map_x, map_y))

        # Légende
        legend_y = map_y + map_size + 6
        legends = [
            (PHONE_ACCENT, "Vous"), (PHONE_GREEN, "Pickup"),
            (PHONE_RED, "Livraison"), (PHONE_YELLOW, "Dispo"),
        ]
        lx_pos = 10
        for color, text in legends:
            pygame.draw.circle(surf, color, (lx_pos + 5, legend_y + 7), 4)
            t = self.font_small.render(text, True, PHONE_TEXT_DIM)
            surf.blit(t, (lx_pos + 13, legend_y))
            lx_pos += t.get_width() + 20

    def _render_shop(self, surf):
        """App Boutique : catalogue avec aperçu voiture, stats et achat."""
        self._render_back_button(surf, "Boutique")
        ms = self.mission_system
        sw = surf.get_width()
        sh = surf.get_height()

        money_txt = self.font_text.render(f"${ms.money}", True, PHONE_GREEN)
        surf.blit(money_txt, (sw - money_txt.get_width() - 8, 4))

        clip_y = 22
        clip_h = sh - clip_y
        clip_surf = pygame.Surface((sw - 8, clip_h), pygame.SRCALPHA)

        sorted_vehicles = sorted(VEHICLE_CATALOG.items(), key=lambda x: x[1]["price"])
        card_h = 130
        card_gap = 8
        local_y = -self.shop_scroll
        preview_size = 50

        stat_max = {"max_speed": 1500, "accel": 600, "handling": 1.3, "brake": 620, "grip": 9.5}
        stat_labels = [("max_speed", "VIT"), ("accel", "ACC"), ("handling", "MAN"), ("brake", "FRN"), ("grip", "ADH")]

        for v_idx, (model, stats) in enumerate(sorted_vehicles):
            if local_y + card_h < -10:
                local_y += card_h + card_gap
                continue
            if local_y > clip_h + 10:
                break

            w = clip_surf.get_width()
            card = pygame.Surface((w, card_h), pygame.SRCALPHA)
            is_focused = (v_idx == self.kb_focus)
            bg = (40, 40, 60) if is_focused else PHONE_CARD_BG
            card.fill(bg)
            pygame.draw.rect(card, PHONE_BORDER, (0, 0, w, card_h), 1, border_radius=6)

            sel_ci = self.shop_selected_colors.get(model, 0)
            sel_color = VEHICLE_COLORS[sel_ci]

            # Car preview animation (left side)
            preview_key = (model, sel_color, preview_size)
            if preview_key not in self._car_preview_cache:
                try:
                    anim_idx = 0  # static frame
                    path = resolve_car_frame_path(model, sel_color, anim_idx)
                    img = pygame.image.load(path).convert_alpha()
                    self._car_preview_cache[preview_key] = pygame.transform.smoothscale(img, (preview_size, preview_size))
                except Exception:
                    self._car_preview_cache[preview_key] = None
            preview_img = self._car_preview_cache.get(preview_key)
            text_x_offset = 6
            if preview_img:
                card.blit(preview_img, (4, 18))
                text_x_offset = preview_size + 8

            # Nom + prix on same line, offset by preview
            name_surf = self.font_text.render(model, True, PHONE_TEXT)
            card.blit(name_surf, (text_x_offset, 4))

            price_color = PHONE_GREEN if ms.money >= stats["price"] else PHONE_RED
            price_txt = self.font_text.render(f"${stats['price']}" if stats["price"] > 0 else "GRATUIT", True, price_color)
            card.blit(price_txt, (text_x_offset + name_surf.get_width() + 8, 4))

            # Color selector row (below name)
            color_x = w - len(VEHICLE_COLORS) * 14 - 4
            for ci, color_name in enumerate(VEHICLE_COLORS):
                rgb = self._color_name_to_rgb(color_name)
                cx = color_x + ci * 14
                pygame.draw.rect(card, rgb, (cx, 20, 12, 12), border_radius=2)
                if ci == sel_ci:
                    pygame.draw.rect(card, (255, 255, 255), (cx - 1, 19, 14, 14), 2, border_radius=2)

            # Stats bars (right of preview)
            bar_y = 36
            bar_start_x = text_x_offset
            bar_w = w - bar_start_x - 8
            bar_h = 8
            for stat_key, stat_label in stat_labels:
                val = stats.get(stat_key, 0)
                ratio = min(1.0, max(0.0, val / stat_max[stat_key]))
                lbl = self.font_small.render(stat_label, True, PHONE_TEXT_DIM)
                card.blit(lbl, (bar_start_x, bar_y))
                pygame.draw.rect(card, (40, 40, 55), (bar_start_x + 34, bar_y + 2, bar_w - 34, bar_h), border_radius=3)
                fill_w = int((bar_w - 34) * ratio)
                bar_color = PHONE_GREEN if ratio > 0.6 else PHONE_YELLOW if ratio > 0.3 else PHONE_RED
                if fill_w > 0:
                    pygame.draw.rect(card, bar_color, (bar_start_x + 34, bar_y + 2, fill_w, bar_h), border_radius=3)
                bar_y += 13

            # Description
            desc = self.font_small.render(stats.get("desc", ""), True, PHONE_TEXT_DIM)
            card.blit(desc, (text_x_offset, card_h - 28))

            # Buy/equip button
            owned = ms.has_car(model, sel_color)
            is_current = self.player and self.player.car == (model, sel_color)
            if is_current:
                btn_text, btn_color = "EQUIPE", (100, 100, 120)
            elif owned:
                btn_text, btn_color = "EQUIPER", PHONE_ACCENT
            elif ms.money >= stats["price"]:
                btn_text, btn_color = "ACHETER", PHONE_GREEN
            else:
                btn_text, btn_color = "ACHETER", (80, 40, 40)

            btn_x = w - 82
            btn_y_pos = card_h - 26
            pygame.draw.rect(card, btn_color, (btn_x, btn_y_pos, 76, 22), border_radius=4)
            btn_label = self.font_small.render(btn_text, True, (255, 255, 255))
            card.blit(btn_label, (btn_x + 38 - btn_label.get_width() // 2, btn_y_pos + 4))

            clip_surf.blit(card, (0, local_y))
            local_y += card_h + card_gap

        surf.blit(clip_surf, (4, clip_y))

    def _render_garage(self, surf):
        """App Garage : sélection des voitures possédées."""
        self._render_back_button(surf, "Garage")
        ms = self.mission_system
        sw = surf.get_width()
        sh = surf.get_height()

        clip_y = 22
        clip_h = sh - clip_y
        clip_surf = pygame.Surface((sw - 8, clip_h), pygame.SRCALPHA)

        card_h = 50
        card_gap = 6
        local_y = -self.garage_scroll

        for idx, car_data in enumerate(ms.owned_cars):
            if local_y + card_h < -10:
                local_y += card_h + card_gap
                continue
            if local_y > clip_h + 10:
                break

            w = clip_surf.get_width()
            card = pygame.Surface((w, card_h), pygame.SRCALPHA)
            is_focused = (idx == self.kb_focus)
            is_current = self.player and self.player.car == (car_data["model"], car_data["color"])
            bg = (40, 40, 60) if is_focused else (30, 60, 30) if is_current else PHONE_CARD_BG
            card.fill(bg)
            pygame.draw.rect(card, PHONE_BORDER, (0, 0, w, card_h), 1, border_radius=6)

            # Car preview
            preview_key = (car_data["model"], car_data["color"], 40)
            if preview_key not in self._car_preview_cache:
                try:
                    path = resolve_car_frame_path(car_data["model"], car_data["color"], 0)
                    img = pygame.image.load(path).convert_alpha()
                    self._car_preview_cache[preview_key] = pygame.transform.smoothscale(img, (40, 40))
                except Exception:
                    self._car_preview_cache[preview_key] = None
            preview = self._car_preview_cache.get(preview_key)
            if preview:
                card.blit(preview, (5, 5))

            name_txt = self.font_text.render(f"{car_data['model']} - {car_data['color']}", True, PHONE_TEXT)
            card.blit(name_txt, (50, 8))

            if is_current:
                eq_surf = self.font_small.render("EQUIPE", True, PHONE_GREEN)
                card.blit(eq_surf, (50, 28))
            else:
                sel_surf = self.font_small.render("SELECTIONNER", True, PHONE_ACCENT)
                card.blit(sel_surf, (w - sel_surf.get_width() - 8, 16))

            clip_surf.blit(card, (0, local_y))
            local_y += card_h + card_gap

        surf.blit(clip_surf, (4, clip_y))

    def _render_stats(self, surf):
        """App Stats : statistiques du joueur."""
        self._render_back_button(surf, "Stats")
        ms = self.mission_system
        sw = surf.get_width()
        sh = surf.get_height()
        y = 30

        # Distance
        dist_m = 0.0
        if self.player:
            dist_m = self.player.distance_traveled / 30.0  # 30px = 1m
        if dist_m >= 1000:
            dist_str = f"{dist_m / 1000:.1f} km"
        else:
            dist_str = f"{dist_m:.0f} m"

        stats_data = [
            ("Argent", f"${ms.money}", PHONE_GREEN),
            ("Livraisons", str(ms.completed_count), PHONE_ACCENT),
            ("Échouées", str(ms.failed_count), PHONE_RED),
            ("Véhicules", str(len(ms.owned_cars)), PHONE_YELLOW),
            ("Distance", dist_str, PHONE_ACCENT),
        ]

        for label, value, color in stats_data:
            bar_w = sw - 16
            bar = pygame.Surface((bar_w, 42), pygame.SRCALPHA)
            bar.fill(PHONE_CARD_BG)
            pygame.draw.rect(bar, PHONE_BORDER, (0, 0, bar_w, 42), 1, border_radius=6)
            l_txt = self.font_text.render(label, True, PHONE_TEXT_DIM)
            bar.blit(l_txt, (12, 12))
            v_txt = self.font_title.render(value, True, color)
            bar.blit(v_txt, (bar_w - 12 - v_txt.get_width(), 10))
            surf.blit(bar, (10, y))
            y += 52

        # Véhicule actuel
        if self.player:
            y += 10
            car_label = self.font_text.render(f"Véhicule: {self.player.car[0]} {self.player.car[1]}", True, PHONE_TEXT)
            surf.blit(car_label, (10, y))

    def _type_color(self, mission_type):
        """Couleur selon le type de mission."""
        return {
            'standard': (200, 200, 200),
            'express': PHONE_YELLOW,
            'chain': PHONE_ACCENT,
        }.get(mission_type, (200, 200, 200))

    @staticmethod
    def _color_name_to_rgb(name):
        """Convertit un nom de couleur en RGB."""
        return {
            "Black": (40, 40, 40), "Blue": (50, 80, 200),
            "Brown": (140, 80, 40), "Green": (50, 160, 50),
            "Magenta": (200, 50, 150), "Red": (200, 50, 50),
            "White": (220, 220, 220), "Yellow": (220, 200, 50),
        }.get(name, (150, 150, 150))
