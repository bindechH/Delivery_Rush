"""
Module interface téléphone pour Delivery Rush
Interface smartphone avec applications : Livraisons, GPS, Boutique, Stats.
Animation slide-up, achat de véhicules, carte complète.
"""

import math
import pygame
from .translate import normalize_language, tr
from .missions import (
    MISSION_LOCATIONS,
    CARGO_POOL,
    REWARD_STANDARD,
    REWARD_EXPRESS,
    REWARD_CHAIN,
    TIME_STANDARD,
    TIME_EXPRESS,
    TIME_CHAIN,
    RISKY_TYPE_BASE_CHANCE,
)
from .player import (
    VEHICLE_CATALOG,
    get_available_vehicle_colors,
    resolve_car_frame_path,
    sanitize_car,
)

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

MISSION_ACTIVE_CARD_H = 92
MISSION_CARD_H = 78
MISSION_CARD_GAP = 8
SHOP_CARD_H = 148
SHOP_CARD_GAP = 8
GARAGE_CARD_H = 58
GARAGE_CARD_GAP = 8

# === APPS ===
BASE_APPS = [
    {"id": "missions", "name": "phone.deliveries", "icon": "\u25a3", "color": (70, 180, 70)},
    {"id": "gps",      "name": "phone.gps",        "icon": "\u25c9", "color": (70, 130, 230)},
    {"id": "shop",     "name": "phone.shop",       "icon": "\u2605", "color": (230, 180, 50)},
    {"id": "wiki",     "name": "phone.wiki",       "icon": "\u2139", "color": (90, 160, 220)},
    {"id": "stats",    "name": "phone.stats",      "icon": "\u25b2", "color": (180, 80, 230)},
]

MULTIPLAYER_APPS = [
    {"id": "leaderboard", "name": "phone.top10", "icon": "\u2606", "color": (240, 120, 70)},
    {"id": "party",       "name": "phone.party", "icon": "\u2630", "color": (90, 190, 220)},
]


class PhoneUI:
    """Interface smartphone in-game avec applications et animation slide-up."""

    def __init__(self, screen_width, screen_height, mission_system, mission_event_sender=None, sound_event_sender=None, language="fr", multiplayer=False, network_client=None):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.mission_system = mission_system
        self.mission_event_sender = mission_event_sender
        self.sound_event_sender = sound_event_sender
        self.player = None  # Set externally
        self.visible = False
        self.language = normalize_language(language)
        self.multiplayer = bool(multiplayer)
        self.network_client = network_client

        # Animation slide-up
        self.anim_progress = 0.0  # 0=caché, 1=affiché
        self.anim_target = 0.0
        self.anim_speed = 5.0

        # Navigation
        self.current_screen = "home"  # home, missions, gps, shop, wiki, stats
        self.scroll_offset = 0
        self.hovered_mission = -1
        self.shop_scroll = 0
        self.shop_selected_colors = {}  # model -> color index
        self.garage_scroll = 0
        self.guide_scroll = 0
        self._guide_scroll_max = 0

        # Keyboard navigation
        self.kb_focus = 0  # focused item index on current screen
        self.home_focus = 0  # which app icon is focused on home
        self._last_net_sync = 0.0
        self.gps_anim_progress = 0.0
        self.gps_anim_speed = 10.0
        self.gps_legend_page = 0
        self.gps_hover_local = None

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

        try:
            self._gps_minimap_bg = pygame.image.load("assets/images/HUD/minimap.png").convert_alpha()
        except Exception:
            self._gps_minimap_bg = None

        # Phone position: bottom-right corner, slide up from bottom
        self.phone_x = screen_width - PHONE_WIDTH - 15
        self.phone_y_target = screen_height - PHONE_HEIGHT - 15
        self.phone_y_hidden = screen_height - 30  # peek: show 30px strip when closed

        # Car preview cache for shop
        self._car_preview_cache = {}

    def _party_joinable_parties(self, parties, my_party):
        my_party_id = None
        if isinstance(my_party, dict):
            my_party_id = str(my_party.get('id', ''))
        elif my_party:
            my_party_id = str(my_party)

        rows = []
        for pid, party in parties.items():
            if not isinstance(party, dict):
                continue
            if my_party_id and str(pid) == my_party_id:
                continue
            rows.append((str(pid), party))
        return rows

    def get_hovered_mission_target(self):
        """Retourne la cible monde survolée dans l'app livraisons pour le rendu clignotant."""
        if not self.visible or self.current_screen != "missions":
            return None

        ms = self.mission_system
        missions = list(getattr(ms, 'available_missions', []) or [])
        idx = -1
        if 0 <= self.hovered_mission < len(missions):
            idx = self.hovered_mission
        elif 0 <= self.kb_focus < len(missions):
            idx = self.kb_focus

        if idx < 0 or idx >= len(missions):
            return None

        mission = missions[idx]
        pickup = getattr(mission, 'pickup', {}) or {}
        if 'x' not in pickup or 'y' not in pickup:
            return None
        return {
            'x': float(pickup.get('x', 0.0) or 0.0),
            'y': float(pickup.get('y', 0.0) or 0.0),
            'name': str(pickup.get('name', '')),
            'kind': 'pickup',
            'blink': True,
        }

    def _home_apps(self):
        apps = list(BASE_APPS)
        if self.multiplayer and self.network_client:
            apps.extend(MULTIPLAYER_APPS)
        return apps

    def _t(self, key, **kwargs):
        return tr(self.language, key, **kwargs)

    def _model_colors(self, model):
        return get_available_vehicle_colors(model)

    def _selected_color(self, model):
        colors = self._model_colors(model)
        idx = int(self.shop_selected_colors.get(model, 0) or 0)
        if idx < 0:
            idx = 0
        if idx >= len(colors):
            idx = len(colors) - 1
        self.shop_selected_colors[model] = idx
        return colors[idx]

    def _mission_type_label(self, mission_type):
        key = f"mission.type.{str(mission_type or 'standard').lower()}"
        value = self._t(key)
        if value == key:
            value = str(mission_type or "standard")
        return value.upper()

    def _cargo_label(self, cargo_type):
        cargo_key = str(cargo_type or "colis").lower()
        key = f"cargo.{cargo_key}"
        value = self._t(key)
        if value == key:
            return cargo_key
        return value

    def toggle(self):
        """Ouvrir/fermer le téléphone avec animation."""
        if self.anim_target == 0.0:
            self.visible = True
            self.anim_target = 1.0
        else:
            self.anim_target = 0.0
            self._emit_sound_event("ui_back")
        self.scroll_offset = 0
        self.shop_scroll = 0
        self.garage_scroll = 0
        self.guide_scroll = 0
        self._guide_scroll_max = 0
        self.gps_hover_local = None
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

        if self.visible and self.multiplayer and self.network_client:
            now_s = pygame.time.get_ticks() / 1000.0
            if now_s - self._last_net_sync >= 0.9:
                if self.current_screen == "leaderboard":
                    self.network_client.request_leaderboard()
                if self.current_screen in ("party", "home"):
                    self.network_client.request_party_state()
                self._last_net_sync = now_s

        gps_target = 1.0 if (self.visible and self.current_screen == "gps") else 0.0
        if self.gps_anim_progress < gps_target:
            self.gps_anim_progress = min(gps_target, self.gps_anim_progress + self.gps_anim_speed * dt)
        elif self.gps_anim_progress > gps_target:
            self.gps_anim_progress = max(gps_target, self.gps_anim_progress - self.gps_anim_speed * dt)

    def _phone_y(self):
        """Position Y du téléphone basée sur l'animation."""
        t = self.anim_progress
        # Ease-out cubic
        t_ease = 1.0 - (1.0 - t) ** 3
        return int(self.phone_y_hidden + (self.phone_y_target - self.phone_y_hidden) * t_ease)

    def _phone_rect(self):
        return pygame.Rect(self.phone_x, self._phone_y(), PHONE_WIDTH, PHONE_HEIGHT)

    def _gps_transform_state(self):
        t = max(0.0, min(1.0, float(self.gps_anim_progress)))
        t_ease = 1.0 - (1.0 - t) ** 3

        src_screen = pygame.Rect(
            self.phone_x + PHONE_SCREEN_X,
            self._phone_y() + PHONE_SCREEN_Y,
            PHONE_SCREEN_W,
            PHONE_SCREEN_H,
        )

        margin_x = max(22, self.screen_width // 26)
        margin_y = max(20, self.screen_height // 16)
        target_scale = min(
            (self.screen_width - margin_x * 2) / float(PHONE_HEIGHT),
            (self.screen_height - margin_y * 2) / float(PHONE_WIDTH),
        )
        target_scale = max(1.0, target_scale)
        scale = 1.0 + (target_scale - 1.0) * t_ease

        # Rotate phone to the left (counter-clockwise) into landscape.
        angle = 90.0 * t_ease

        src_cx = self.phone_x + PHONE_WIDTH / 2.0
        src_cy = self._phone_y() + PHONE_HEIGHT / 2.0
        dst_cx = self.screen_width / 2.0
        dst_cy = self.screen_height / 2.0
        cx = src_cx + (dst_cx - src_cx) * t_ease
        cy = src_cy + (dst_cy - src_cy) * t_ease

        off_x = (PHONE_SCREEN_X + PHONE_SCREEN_W / 2.0) - (PHONE_WIDTH / 2.0)
        off_y = (PHONE_SCREEN_Y + PHONE_SCREEN_H / 2.0) - (PHONE_HEIGHT / 2.0)
        dst_screen_cx = dst_cx - off_y * target_scale
        dst_screen_cy = dst_cy + off_x * target_scale
        dst_screen_w = PHONE_SCREEN_H * target_scale
        dst_screen_h = PHONE_SCREEN_W * target_scale
        dst_screen = pygame.Rect(
            int(dst_screen_cx - dst_screen_w / 2.0),
            int(dst_screen_cy - dst_screen_h / 2.0),
            int(dst_screen_w),
            int(dst_screen_h),
        )

        gps_screen_rect = pygame.Rect(
            int(src_screen.x + (dst_screen.x - src_screen.x) * t_ease),
            int(src_screen.y + (dst_screen.y - src_screen.y) * t_ease),
            int(src_screen.width + (dst_screen.width - src_screen.width) * t_ease),
            int(src_screen.height + (dst_screen.height - src_screen.height) * t_ease),
        )
        gps_screen_rect.width = max(120, gps_screen_rect.width)
        gps_screen_rect.height = max(90, gps_screen_rect.height)

        return {
            "t": t,
            "t_ease": t_ease,
            "angle": angle,
            "scale": scale,
            "center": (int(cx), int(cy)),
            "gps_screen_rect": gps_screen_rect,
        }

    def _gps_landscape_rect(self):
        return self._gps_transform_state()["gps_screen_rect"]

    def _gps_legend_page_size(self, legend_h):
        row_h = max(12, self.font_small.get_height() + 2)
        hint_h = self.font_small.get_height()
        hint_y = legend_h - hint_h - 6
        list_top = 24
        list_bottom = max(list_top, hint_y - 6)
        return max(1, (list_bottom - list_top) // row_h)

    def _equipped_car(self):
        if self.player and hasattr(self.player, "car"):
            return sanitize_car(self.player.car)
        if hasattr(self.mission_system, "current_car"):
            return sanitize_car(self.mission_system.current_car)
        return sanitize_car(("MICRO", "White"))

    def _refresh_missions_for_equipped_car(self):
        if hasattr(self.mission_system, "refresh_available_missions_for_vehicle"):
            self.mission_system.refresh_available_missions_for_vehicle(self._equipped_car())

    def _mission_is_selectable(self, mission):
        if hasattr(self.mission_system, "mission_is_selectable"):
            return self.mission_system.mission_is_selectable(mission, self._equipped_car())
        return True

    @staticmethod
    def _mission_risk_level(mission):
        value = str(getattr(mission, "risk_level", "chill") or "chill").strip().lower()
        return "risky" if value == "risky" else "chill"

    def _notify_network_mission_accept(self, mission):
        if not self.mission_event_sender:
            return
        try:
            self.mission_event_sender("mission_accept", {"id": mission.id}, self._equipped_car())
        except Exception:
            pass

    def _can_start_party_mission(self):
        """En multi, seul le leader peut démarrer une mission partagée de party."""
        if not self.multiplayer or not self.network_client:
            return True

        state = dict(getattr(self.network_client, 'party_state', {}) or {})
        my_party = state.get('my_party')
        if not isinstance(my_party, dict):
            return True

        members_raw = my_party.get('members', []) if isinstance(my_party.get('members'), list) else []
        members = [str(m) for m in members_raw if str(m)]
        if len(members) <= 1:
            return True

        leader = str(my_party.get('leader', '') or '').strip()
        me = str(getattr(self.network_client, 'username', '') or '').strip()
        if leader and me and leader != me:
            msg = self._t("phone.party_leader_start_only")
            if hasattr(self.mission_system, "set_external_notification"):
                self.mission_system.set_external_notification(msg)
            self._emit_sound_event("mission_denied")
            return False

        return True

    def _emit_sound_event(self, event_name):
        if not self.sound_event_sender:
            return
        try:
            self.sound_event_sender(event_name)
        except Exception:
            pass

    @staticmethod
    def _fit_text(font, text, max_width):
        text = str(text or "")
        if max_width <= 4:
            return ""
        if font.size(text)[0] <= max_width:
            return text
        ellipsis = "..."
        out = text
        while out and font.size(out + ellipsis)[0] > max_width:
            out = out[:-1]
        return (out + ellipsis) if out else ellipsis

    @staticmethod
    def _wrap_text(font, text, max_width, max_lines=2):
        words = str(text or "").split()
        if not words:
            return [""]

        lines = []
        current = words[0]
        for word in words[1:]:
            candidate = f"{current} {word}"
            if font.size(candidate)[0] <= max_width:
                current = candidate
            else:
                lines.append(current)
                current = word
                if len(lines) >= max_lines:
                    break

        if len(lines) < max_lines:
            lines.append(current)

        if len(lines) > max_lines:
            lines = lines[:max_lines]

        lines = [PhoneUI._fit_text(font, line, max_width) for line in lines]

        if len(lines) == max_lines and " ".join(words) != " ".join(lines):
            lines[-1] = PhoneUI._fit_text(font, lines[-1], max_width)

        return lines

    @staticmethod
    def _vehicle_mission_hint(stats):
        tags = set(str(t).lower() for t in stats.get("special_tags", []))
        if {"heavy", "cargo", "delivery", "industrial"} & tags:
            return "phone.hint_heavy"
        if {"express", "race", "vip"} & tags:
            return "phone.hint_express"
        return "phone.hint_standard"

    def handle_events(self, events):
        """Gérer les interactions avec le téléphone (souris + clavier)."""
        if not self.visible or self.anim_progress < 0.8:
            return
        phone_rect = self._phone_rect()
        gps_rect = self._gps_landscape_rect() if self.current_screen == "gps" else None

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
                        self.guide_scroll = 0
                        self.gps_hover_local = None
                        self.kb_focus = 0
                        self._emit_sound_event("ui_back")
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
                if self.current_screen == "gps" and gps_rect is not None:
                    if not gps_rect.collidepoint(mx, my):
                        continue
                    lx = (mx - gps_rect.x) * (PHONE_SCREEN_H / max(1.0, float(gps_rect.width)))
                    ly = (my - gps_rect.y) * (PHONE_SCREEN_W / max(1.0, float(gps_rect.height)))
                else:
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
                elif self.current_screen in ("stats", "gps", "leaderboard", "wiki"):
                    self._handle_back_click(lx, ly)
                elif self.current_screen == "party":
                    self._handle_party_click(lx, ly)

            elif event.type == pygame.MOUSEWHEEL:
                pointer = pygame.mouse.get_pos()
                active_rect = gps_rect if (self.current_screen == "gps" and gps_rect is not None) else phone_rect
                if active_rect.collidepoint(*pointer):
                    if self.current_screen == "missions":
                        self.scroll_offset = max(0, self.scroll_offset - event.y * 30)
                    elif self.current_screen == "shop":
                        self.shop_scroll = max(0, self.shop_scroll - event.y * 35)
                    elif self.current_screen == "garage":
                        self.garage_scroll = max(0, self.garage_scroll - event.y * 35)
                    elif self.current_screen == "gps":
                        pad = 10
                        map_area_y = 32
                        legend_row_h = max(16, self.font_small.get_height() + 4)
                        content_h = PHONE_SCREEN_W if self.gps_anim_progress >= 0.5 else PHONE_SCREEN_H
                        legend_h = max(150, content_h - map_area_y - pad - legend_row_h)
                        page_size = self._gps_legend_page_size(legend_h)
                        total = max(1, len(MISSION_LOCATIONS))
                        pages = max(1, math.ceil(total / page_size))
                        self.gps_legend_page = max(0, min(pages - 1, self.gps_legend_page - event.y))
                    elif self.current_screen == "wiki":
                        self.guide_scroll = max(0, min(self._guide_scroll_max, self.guide_scroll - event.y * 26))

            elif event.type == pygame.MOUSEMOTION:
                if self.current_screen == "missions":
                    self._update_hover(event.pos, phone_rect)
                elif self.current_screen == "gps":
                    mx, my = event.pos
                    if gps_rect is not None and gps_rect.collidepoint(mx, my):
                        self.gps_hover_local = (
                            (mx - gps_rect.x) * (PHONE_SCREEN_H / max(1.0, float(gps_rect.width))),
                            (my - gps_rect.y) * (PHONE_SCREEN_W / max(1.0, float(gps_rect.height))),
                        )
                    else:
                        self.gps_hover_local = None

    def _handle_kb_enter(self):
        """Handle Enter key on current screen."""
        if self.current_screen == "home":
            apps = self._home_apps()
            if 0 <= self.home_focus < len(apps):
                self.current_screen = apps[self.home_focus]["id"]
                self.scroll_offset = 0
                self.shop_scroll = 0
                self.garage_scroll = 0
                self.guide_scroll = 0
                self.gps_hover_local = None
                self.kb_focus = 0
                if self.current_screen == "gps":
                    self.gps_legend_page = 0
                self._emit_sound_event("ui_open")
        elif self.current_screen == "missions":
            ms = self.mission_system
            if ms.active_mission:
                return  # Can't accept while one is active
            if 0 <= self.kb_focus < len(ms.available_missions):
                if not self._can_start_party_mission():
                    return
                mission = ms.available_missions[self.kb_focus]
                ok, _ = ms.accept_mission(mission.id, self._equipped_car())
                if ok:
                    if self.player and hasattr(self.player, "reset_mission_telemetry"):
                        self.player.reset_mission_telemetry()
                    self._notify_network_mission_accept(mission)
                else:
                    self._emit_sound_event("mission_denied")
        elif self.current_screen == "shop":
            sorted_vehicles = sorted(VEHICLE_CATALOG.items(), key=lambda x: x[1]["price"])
            if 0 <= self.kb_focus < len(sorted_vehicles):
                model, stats = sorted_vehicles[self.kb_focus]
                sel_color = self._selected_color(model)
                if self.mission_system.has_car(model, sel_color):
                    if self.player:
                        self.player.change_car((model, sel_color))
                        self._refresh_missions_for_equipped_car()
                        self._emit_sound_event("garage_equip")
                else:
                    ok, _ = self.mission_system.buy_car(model, sel_color, stats["price"])
                    self._emit_sound_event("shop_buy" if ok else "shop_denied")
        elif self.current_screen == "garage":
            owned = self.mission_system.owned_cars
            if 0 <= self.kb_focus < len(owned):
                car_data = owned[self.kb_focus]
                if self.player:
                    self.player.change_car((car_data["model"], car_data["color"]))
                    self._refresh_missions_for_equipped_car()
                    self._emit_sound_event("garage_equip")
        elif self.current_screen == "party" and self.network_client:
            state = dict(getattr(self.network_client, 'party_state', {}) or {})
            my_party = state.get('my_party')
            parties = state.get('parties', {}) if isinstance(state.get('parties'), dict) else {}
            joinable = self._party_joinable_parties(parties, my_party)

            if self.kb_focus <= 0:
                if my_party is None:
                    self.network_client.create_party()
                    self._emit_sound_event("ui_open")
                else:
                    self.network_client.leave_party()
                    self._emit_sound_event("ui_back")
                self.network_client.request_party_state()
                return

            row_idx = self.kb_focus - 1
            if 0 <= row_idx < len(joinable):
                party_id, _ = joinable[row_idx]
                self.network_client.join_party(party_id=party_id)
                self.network_client.request_party_state()
                self._emit_sound_event("ui_open")

    def _handle_kb_navigate(self, direction):
        """Handle up/down navigation with auto-scroll."""
        if self.current_screen == "home":
            cols = APP_GRID_COLS
            new_focus = self.home_focus + direction * cols
            if 0 <= new_focus < len(self._home_apps()):
                self.home_focus = new_focus
        elif self.current_screen == "missions":
            ms = self.mission_system
            max_items = len(ms.available_missions)
            self.kb_focus = max(0, min(max_items - 1, self.kb_focus + direction))
            self.hovered_mission = self.kb_focus if max_items > 0 else -1
            # Auto-scroll to keep focused item visible
            card_h = MISSION_CARD_H + MISSION_CARD_GAP
            clip_h = PHONE_SCREEN_H - 22
            offset = 0
            if ms.active_mission:
                offset = MISSION_ACTIVE_CARD_H + MISSION_CARD_GAP
            offset += 22  # "Disponibles" label
            focus_y = offset + self.kb_focus * card_h
            if focus_y < self.scroll_offset:
                self.scroll_offset = focus_y
            elif focus_y + MISSION_CARD_H > self.scroll_offset + clip_h:
                self.scroll_offset = focus_y + MISSION_CARD_H - clip_h
        elif self.current_screen == "shop":
            sorted_vehicles = sorted(VEHICLE_CATALOG.items(), key=lambda x: x[1]["price"])
            self.kb_focus = max(0, min(len(sorted_vehicles) - 1, self.kb_focus + direction))
            # Auto-scroll to keep focused item visible
            card_h = SHOP_CARD_H
            card_gap = SHOP_CARD_GAP
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
            card_h = GARAGE_CARD_H
            card_gap = GARAGE_CARD_GAP
            clip_h = PHONE_SCREEN_H - 22
            focus_y = self.kb_focus * (card_h + card_gap)
            if focus_y < self.garage_scroll:
                self.garage_scroll = focus_y
            elif focus_y + card_h > self.garage_scroll + clip_h:
                self.garage_scroll = focus_y + card_h - clip_h
        elif self.current_screen == "party" and self.network_client:
            state = dict(getattr(self.network_client, 'party_state', {}) or {})
            my_party = state.get('my_party')
            parties = state.get('parties', {}) if isinstance(state.get('parties'), dict) else {}
            joinable = self._party_joinable_parties(parties, my_party)
            max_items = 1 + len(joinable)
            self.kb_focus = max(0, min(max_items - 1, self.kb_focus + direction))
        elif self.current_screen == "wiki":
            self.guide_scroll = max(0, min(self._guide_scroll_max, self.guide_scroll + direction * 26))

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
            if self.home_focus < len(self._home_apps()) - 1:
                self.home_focus += 1
        elif self.current_screen == "shop":
            sorted_vehicles = sorted(VEHICLE_CATALOG.items(), key=lambda x: x[1]["price"])
            if 0 <= self.kb_focus < len(sorted_vehicles):
                model = sorted_vehicles[self.kb_focus][0]
                colors = self._model_colors(model)
                ci = self.shop_selected_colors.get(model, 0)
                if ci < len(colors) - 1:
                    self.shop_selected_colors[model] = ci + 1

    def _handle_home_click(self, lx, ly):
        """Écran d'accueil → ouvrir une app."""
        sw = PHONE_SCREEN_W
        grid_start_y = 60
        grid_start_x = (sw - (APP_GRID_COLS * (APP_ICON_SIZE + APP_PADDING) - APP_PADDING)) // 2
        for i, app in enumerate(self._home_apps()):
            col = i % APP_GRID_COLS
            row = i // APP_GRID_COLS
            ax = grid_start_x + col * (APP_ICON_SIZE + APP_PADDING)
            ay = grid_start_y + row * (APP_ICON_SIZE + APP_PADDING + 18)
            if ax <= lx <= ax + APP_ICON_SIZE and ay <= ly <= ay + APP_ICON_SIZE:
                self.current_screen = app["id"]
                self.scroll_offset = 0
                self.shop_scroll = 0
                self.garage_scroll = 0
                self.guide_scroll = 0
                self.gps_hover_local = None
                self.kb_focus = 0
                if self.current_screen == "gps":
                    self.gps_legend_page = 0
                self._emit_sound_event("ui_open")
                return

    def _handle_party_click(self, lx, ly):
        if lx < 50 and ly < 22:
            self.current_screen = "home"
            self._emit_sound_event("ui_back")
            return
        if not self.network_client:
            return

        state = dict(getattr(self.network_client, 'party_state', {}) or {})
        my_party = state.get('my_party')
        parties = state.get('parties', {}) if isinstance(state.get('parties'), dict) else {}

        if my_party is None:
            if 8 <= lx <= 112 and 36 <= ly <= 58:
                self.kb_focus = 0
                self.network_client.create_party()
                self.network_client.request_party_state()
                self._emit_sound_event("ui_open")
                return
        else:
            if 8 <= lx <= 112 and 36 <= ly <= 58:
                self.kb_focus = 0
                self.network_client.leave_party()
                self.network_client.request_party_state()
                self._emit_sound_event("ui_back")
                return

        row_y = 92
        row_h = 48
        joinable = self._party_joinable_parties(parties, my_party)
        for idx, (pid, party) in enumerate(joinable):
            if 8 <= lx <= PHONE_SCREEN_W - 8 and row_y <= ly <= row_y + row_h:
                self.kb_focus = idx + 1
                self.network_client.join_party(party_id=pid)
                self.network_client.request_party_state()
                self._emit_sound_event("ui_open")
                return
            row_y += row_h + 8

    def _handle_back_click(self, lx, ly):
        """Bouton retour en haut à gauche."""
        if lx < 50 and ly < 22:
            self.current_screen = "home"
            self.scroll_offset = 0
            self.shop_scroll = 0
            self.garage_scroll = 0
            self.guide_scroll = 0
            self.gps_hover_local = None
            self._emit_sound_event("ui_back")

    def _handle_missions_click(self, lx, ly):
        """Clic dans l'écran missions."""
        # Back button
        if lx < 50 and ly < 22:
            self.current_screen = "home"
            self._emit_sound_event("ui_back")
            return

        ms = self.mission_system
        content_y = 22 - self.scroll_offset

        # Mission active → abandon
        if ms.active_mission:
            abandon_y = content_y + MISSION_ACTIVE_CARD_H - 36
            if PHONE_SCREEN_W - 100 < lx < PHONE_SCREEN_W - 8 and abandon_y < ly < abandon_y + 20:
                ms.abandon_mission()
                return
            content_y += MISSION_ACTIVE_CARD_H + MISSION_CARD_GAP

        content_y += 22

        # Missions disponibles → accepter
        for mission in ms.available_missions:
            if 8 < lx < PHONE_SCREEN_W - 8 and content_y < ly < content_y + MISSION_CARD_H:
                if not self._can_start_party_mission():
                    return
                ok, _ = ms.accept_mission(mission.id, self._equipped_car())
                if ok:
                    if self.player and hasattr(self.player, "reset_mission_telemetry"):
                        self.player.reset_mission_telemetry()
                    self._notify_network_mission_accept(mission)
                else:
                    self._emit_sound_event("mission_denied")
                return
            content_y += MISSION_CARD_H + MISSION_CARD_GAP

    def _handle_shop_click(self, lx, ly):
        """Clic dans la boutique."""
        if lx < 50 and ly < 22:
            self.current_screen = "home"
            self._emit_sound_event("ui_back")
            return

        ms = self.mission_system
        sorted_vehicles = sorted(VEHICLE_CATALOG.items(), key=lambda x: x[1]["price"])
        card_h = SHOP_CARD_H
        card_gap = SHOP_CARD_GAP
        content_y = 22 - self.shop_scroll

        for model, stats in sorted_vehicles:
            # Boutons couleur
            color_y = content_y + 28
            colors = self._model_colors(model)
            color_x_start = PHONE_SCREEN_W - 8 - len(colors) * 14
            for ci, color_name in enumerate(colors):
                cx = color_x_start + ci * 14
                if cx <= lx <= cx + 12 and color_y <= ly <= color_y + 12:
                    self.shop_selected_colors[model] = ci
                    self._emit_sound_event("ui_move")
                    return

            # Bouton acheter/équiper
            btn_y = content_y + card_h - 26
            btn_x = PHONE_SCREEN_W - 88
            if btn_x <= lx <= btn_x + 76 and btn_y <= ly <= btn_y + 22:
                sel_color = self._selected_color(model)
                if ms.has_car(model, sel_color):
                    # Équiper
                    if self.player:
                        self.player.change_car((model, sel_color))
                        self._refresh_missions_for_equipped_car()
                        self._emit_sound_event("garage_equip")
                else:
                    ok, _ = ms.buy_car(model, sel_color, stats["price"])
                    self._emit_sound_event("shop_buy" if ok else "shop_denied")
                return

            content_y += card_h + card_gap

    def _handle_garage_click(self, lx, ly):
        """Clic dans le garage."""
        if lx < 50 and ly < 22:
            self.current_screen = "home"
            self._emit_sound_event("ui_back")
            return
        ms = self.mission_system
        card_h = GARAGE_CARD_H
        card_gap = GARAGE_CARD_GAP
        content_y = 22 - self.garage_scroll
        for car_data in ms.owned_cars:
            if 8 < lx < PHONE_SCREEN_W - 8 and content_y < ly < content_y + card_h:
                if self.player:
                    self.player.change_car((car_data["model"], car_data["color"]))
                    self._refresh_missions_for_equipped_car()
                    self._emit_sound_event("garage_equip")
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
            content_y += MISSION_ACTIVE_CARD_H + MISSION_CARD_GAP
        content_y += 22

        for i, mission in enumerate(ms.available_missions):
            if 8 < lx < PHONE_SCREEN_W - 8 and content_y < ly < content_y + MISSION_CARD_H:
                self.hovered_mission = i
                return
            content_y += MISSION_CARD_H + MISSION_CARD_GAP

    @staticmethod
    def _format_seconds(seconds):
        total = max(0, int(seconds or 0))
        minutes = total // 60
        secs = total % 60
        return f"{minutes:02d}:{secs:02d}"

    # === RENDU ===

    def render(self, screen, player=None, game_map=None):
        """Rendre le téléphone avec animation slide-up. Always show peek strip."""
        self.player = player

        if self.current_screen == "gps" and (self.visible or self.gps_anim_progress > 0.0):
            self._render_gps_landscape(screen, player, game_map)
            return

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
            peek_label = self.font_small.render(self._t("phone.peek"), True, PHONE_TEXT_DIM)
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
        elif self.current_screen == "wiki":
            self._render_wiki(content)
        elif self.current_screen == "stats":
            self._render_stats(content)
        elif self.current_screen == "leaderboard":
            self._render_leaderboard(content)
        elif self.current_screen == "party":
            self._render_party(content)

        # Blit content into phone at screen position
        phone_surf.blit(content, (PHONE_SCREEN_X, PHONE_SCREEN_Y))

        # Overlay phone frame image
        if self._phone_frame:
            phone_surf.blit(self._phone_frame, (0, 0))

        screen.blit(phone_surf, (self.phone_x, py))

    def _render_gps_landscape(self, screen, player=None, game_map=None):
        state = self._gps_transform_state()
        t_ease = state["t_ease"]

        phone_base = pygame.Surface((PHONE_WIDTH, PHONE_HEIGHT), pygame.SRCALPHA)
        content_portrait = pygame.Surface((PHONE_SCREEN_W, PHONE_SCREEN_H), pygame.SRCALPHA)
        content_portrait.fill((14, 18, 24, 255))
        self._render_gps(content_portrait, player, game_map)

        content_landscape = pygame.Surface((PHONE_SCREEN_H, PHONE_SCREEN_W), pygame.SRCALPHA)
        content_landscape.fill((14, 18, 24, 255))
        self._render_gps(content_landscape, player, game_map)

        # Counter-rotate content so after the phone left-rotation it appears upright.
        counter_rotated = pygame.transform.rotate(content_landscape, -90)
        if counter_rotated.get_size() != (PHONE_SCREEN_W, PHONE_SCREEN_H):
            counter_rotated = pygame.transform.smoothscale(counter_rotated, (PHONE_SCREEN_W, PHONE_SCREEN_H))

        blended_content = content_portrait.copy()
        counter_rotated.set_alpha(int(255 * t_ease))
        blended_content.blit(counter_rotated, (0, 0))
        phone_base.blit(blended_content, (PHONE_SCREEN_X, PHONE_SCREEN_Y))

        if self._phone_frame is not None:
            phone_base.blit(self._phone_frame, (0, 0))
        else:
            pygame.draw.rect(phone_base, PHONE_BG, (0, 0, PHONE_WIDTH, PHONE_HEIGHT), border_radius=PHONE_RADIUS)
            pygame.draw.rect(phone_base, PHONE_BORDER, (0, 0, PHONE_WIDTH, PHONE_HEIGHT), 2, border_radius=PHONE_RADIUS)

        transformed = pygame.transform.rotozoom(phone_base, state["angle"], state["scale"])
        phone_rect = transformed.get_rect(center=state["center"])
        screen.blit(transformed, phone_rect.topleft)

    def _render_home(self, surf):
        """Écran d'accueil avec icônes d'applications."""
        sw = surf.get_width()
        sh = surf.get_height()

        # Status line only on home
        money_txt = self.font_small.render(f"${self.mission_system.money}", True, PHONE_GREEN)
        title_txt = self.font_small.render(self._t("phone.brand"), True, PHONE_TEXT_DIM)
        surf.blit(title_txt, (6, 2))
        surf.blit(money_txt, (sw - money_txt.get_width() - 6, 2))

        title = self.font_title.render(self._t("phone.home_title"), True, PHONE_TEXT)
        surf.blit(title, (sw // 2 - title.get_width() // 2, 28))

        grid_start_y = 60
        grid_start_x = (sw - (APP_GRID_COLS * (APP_ICON_SIZE + APP_PADDING) - APP_PADDING)) // 2

        for i, app in enumerate(self._home_apps()):
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
            app_key = {
                "missions": "phone.deliveries",
                "gps": "phone.gps",
                "shop": "phone.shop",
                "garage": "phone.garage",
                "wiki": "phone.wiki",
                "stats": "phone.stats",
                "leaderboard": "phone.top10",
                "party": "phone.party",
            }.get(app["id"], app["name"])
            label = self.font_app_label.render(self._t(app_key) if app_key.startswith("phone.") else app_key, True, PHONE_TEXT_DIM)
            surf.blit(label, (ax + APP_ICON_SIZE // 2 - label.get_width() // 2, ay + APP_ICON_SIZE + 4))

    def _render_wiki(self, surf):
        """App Wiki: explique calcul des missions, cargos et impact du vehicule."""
        self._render_back_button(surf, self._t("phone.wiki"))

        sw = surf.get_width()
        sh = surf.get_height()
        clip_y = 24
        clip_h = sh - clip_y - 4
        clip = pygame.Surface((sw - 8, clip_h), pygame.SRCALPHA)

        reward_ranges = {
            "standard": REWARD_STANDARD,
            "express": REWARD_EXPRESS,
            "chain": REWARD_CHAIN,
        }
        time_ranges = {
            "standard": TIME_STANDARD,
            "express": TIME_EXPRESS,
            "chain": TIME_CHAIN,
        }

        vehicle_profile = (
            self.mission_system.get_vehicle_profile(self._equipped_car())
            if hasattr(self.mission_system, "get_vehicle_profile")
            else {}
        )
        mission_weights = (
            self.mission_system._compute_mission_weights(self._equipped_car())
            if hasattr(self.mission_system, "_compute_mission_weights")
            else {"standard": 60.0, "express": 25.0, "chain": 15.0}
        )
        reward_factor = (
            float(self.mission_system._vehicle_reward_factor(self._equipped_car()))
            if hasattr(self.mission_system, "_vehicle_reward_factor")
            else 1.0
        )
        unlock_state = self.mission_system.get_unlock_state() if hasattr(self.mission_system, "get_unlock_state") else {}

        lines = []

        def add_title(text):
            lines.append((str(text), self.font_text, PHONE_TEXT, 2))

        def add_body(text):
            wrapped = self._wrap_text(self.font_small, text, clip.get_width() - 12, max_lines=3)
            for item in wrapped:
                lines.append((item, self.font_small, PHONE_TEXT_DIM, 0))

        add_title(self._t("phone.lab_formula_title"))
        add_body(self._t("phone.lab_formula_gen"))
        add_body(self._t("phone.lab_formula_risky"))
        add_body(self._t("phone.lab_formula_finish"))
        add_body(self._t("phone.lab_formula_mods"))
        lines.append(("", self.font_small, PHONE_TEXT_DIM, 4))

        add_title(self._t("phone.lab_money_title"))
        add_body(self._t("phone.lab_money_calc"))
        for mtype in ("standard", "express", "chain"):
            reward_low, reward_high = reward_ranges[mtype]
            time_low, time_high = time_ranges[mtype]
            risk_pct = int(round(float(RISKY_TYPE_BASE_CHANCE.get(mtype, 0.0)) * 100.0))
            type_name = self._mission_type_label(mtype)
            add_body(f"{type_name}: {int(reward_low)}-{int(reward_high)}$ | {int(time_low)}-{int(time_high)}s | risk {risk_pct}%")

        avail = [int(getattr(m, "reward", 0) or 0) for m in list(getattr(self.mission_system, "available_missions", []) or [])]
        if avail:
            add_body(self._t("phone.lab_current_range", low=min(avail), high=max(avail)))
        lines.append(("", self.font_small, PHONE_TEXT_DIM, 4))

        vclass_key = str(vehicle_profile.get("vehicle_class", "compact") or "compact").lower()
        vclass_label = self._t(f"mission.class.{vclass_key}")
        if vclass_label == f"mission.class.{vclass_key}":
            vclass_label = vclass_key

        model_name = str(vehicle_profile.get("model", self._equipped_car()[0]) or self._equipped_car()[0])
        max_speed = int(float(vehicle_profile.get("max_speed", 0.0) or 0.0))
        capacity = int(float(vehicle_profile.get("cargo_capacity", 0.0) or 0.0))

        add_title(self._t("phone.lab_vehicle_title"))
        add_body(self._t("phone.lab_vehicle_profile", model=model_name, vclass=vclass_label, speed=max_speed, capacity=capacity))
        add_body(
            self._t(
                "phone.lab_vehicle_weights",
                standard=int(round(float(mission_weights.get("standard", 0.0) or 0.0))),
                express=int(round(float(mission_weights.get("express", 0.0) or 0.0))),
                chain=int(round(float(mission_weights.get("chain", 0.0) or 0.0))),
            )
        )
        add_body(self._t("phone.lab_vehicle_reward_factor", factor=f"{reward_factor:.2f}"))

        if mission_weights:
            high_type = max(mission_weights, key=mission_weights.get)
            low_type = min(mission_weights, key=mission_weights.get)
            add_body(
                self._t(
                    "phone.lab_vehicle_bias",
                    high=self._mission_type_label(high_type),
                    low=self._mission_type_label(low_type),
                )
            )

        unlocked_raw = list(unlock_state.get("unlocked_types", []) or []) if isinstance(unlock_state, dict) else []
        unlocked_labels = [self._mission_type_label(name) for name in unlocked_raw if isinstance(name, str)]
        if unlocked_labels:
            add_body(
                self._t(
                    "phone.lab_vehicle_unlocks",
                    tier=str(unlock_state.get("tier", "rookie") or "rookie").upper(),
                    unlocked=", ".join(unlocked_labels),
                )
            )

        lines.append(("", self.font_small, PHONE_TEXT_DIM, 4))

        add_title(self._t("phone.lab_cargo_title"))
        for mtype in ("standard", "express", "chain"):
            type_name = self._mission_type_label(mtype)
            add_body(f"{type_name}:")
            for cargo in CARGO_POOL.get(mtype, []):
                w_min, w_max = cargo.get("weight", (0, 0))
                cargo_name = self._cargo_label(str(cargo.get("type", "colis")))
                add_body(f"- {cargo_name}: {int(w_min)}-{int(w_max)} kg")
            lines.append(("", self.font_small, PHONE_TEXT_DIM, 2))

        total_h = 4
        for _, font, _, gap in lines:
            total_h += font.get_height() + 2 + gap

        self._guide_scroll_max = max(0, total_h - clip_h)
        self.guide_scroll = max(0, min(self._guide_scroll_max, self.guide_scroll))

        y = 4 - self.guide_scroll
        for text, font, color, gap in lines:
            if text:
                txt = font.render(text, True, color)
                if y + txt.get_height() >= -2 and y <= clip_h + 2:
                    clip.blit(txt, (6, y))
            y += font.get_height() + 2 + gap

        surf.blit(clip, (4, clip_y))

        if self._guide_scroll_max > 0:
            hint = self.font_small.render(self._t("phone.lab_scroll_hint"), True, PHONE_TEXT_DIM)
            surf.blit(hint, (sw - hint.get_width() - 6, sh - hint.get_height() - 2))

    def _render_leaderboard(self, surf):
        self._render_back_button(surf, self._t("phone.top10"))
        rows = list(getattr(self.network_client, 'leaderboard_top10', []) or []) if self.network_client else []
        if not rows:
            wait = self.font_small.render(self._t("phone.loading_data"), True, PHONE_TEXT_DIM)
            surf.blit(wait, (10, 36))
            return

        y = 32
        for row in rows[:10]:
            bar = pygame.Surface((PHONE_SCREEN_W - 16, 34), pygame.SRCALPHA)
            bar.fill(PHONE_CARD_BG)
            pygame.draw.rect(bar, PHONE_BORDER, (0, 0, PHONE_SCREEN_W - 16, 34), 1, border_radius=6)
            rank = int(row.get('rank', 0) or 0)
            name = str(row.get('username', '?'))
            completed = int(row.get('completed_missions', 0) or 0)
            money = int(row.get('money', 0) or 0)
            left = self.font_small.render(f"#{rank} {name}", True, PHONE_TEXT)
            right = self.font_small.render(f"{completed} | ${money}", True, PHONE_GREEN)
            bar.blit(left, (8, 9))
            bar.blit(right, (bar.get_width() - right.get_width() - 8, 9))
            surf.blit(bar, (8, y))
            y += 38

    def _render_party(self, surf):
        self._render_back_button(surf, self._t("phone.party"))
        if not self.network_client:
            msg = self.font_small.render(self._t("phone.party_offline"), True, PHONE_TEXT_DIM)
            surf.blit(msg, (10, 36))
            return

        sw = surf.get_width()
        sh = surf.get_height()

        state = dict(getattr(self.network_client, 'party_state', {}) or {})
        my_party = state.get('my_party')
        parties = state.get('parties', {}) if isinstance(state.get('parties'), dict) else {}
        joinable = self._party_joinable_parties(parties, my_party)

        action_rect = pygame.Rect(8, 36, 104, 22)
        action_border = (255, 255, 255) if self.kb_focus == 0 else PHONE_BORDER
        if my_party is None:
            pygame.draw.rect(surf, PHONE_ACCENT, action_rect, border_radius=5)
            pygame.draw.rect(surf, action_border, action_rect, 2, border_radius=5)
            lbl = self.font_small.render(self._t("phone.party_create"), True, (255, 255, 255))
            surf.blit(lbl, (action_rect.centerx - lbl.get_width() // 2, action_rect.y + 4))
        else:
            pygame.draw.rect(surf, PHONE_RED, action_rect, border_radius=5)
            pygame.draw.rect(surf, action_border, action_rect, 2, border_radius=5)
            lbl = self.font_small.render(self._t("phone.party_leave"), True, (255, 255, 255))
            surf.blit(lbl, (action_rect.centerx - lbl.get_width() // 2, action_rect.y + 4))

            leader = str(my_party.get('leader', ''))
            members = my_party.get('members', []) if isinstance(my_party.get('members'), list) else []
            size = int(my_party.get('size', len(members)) or len(members))
            info = self.font_small.render(self._t("phone.party_you", leader=leader, size=size), True, PHONE_TEXT)
            surf.blit(info, (120, 40))

            challenge = my_party.get('challenge') if isinstance(my_party.get('challenge'), dict) else None
            if challenge:
                ch_rect = pygame.Rect(8, 62, PHONE_SCREEN_W - 16, 34)
                pygame.draw.rect(surf, (34, 34, 56), ch_rect, border_radius=6)
                pygame.draw.rect(surf, PHONE_BORDER, ch_rect, 1, border_radius=6)

                status = str(challenge.get('status', 'active'))
                completed = int(challenge.get('completed_deliveries', 0) or 0)
                target = max(1, int(challenge.get('target_deliveries', 1) or 1))
                time_left = self._format_seconds(challenge.get('time_remaining', 0))

                status_label = self._t("phone.party_challenge_live")
                status_color = PHONE_GREEN
                if status == 'completed':
                    status_label = self._t("phone.party_challenge_done")
                    status_color = PHONE_ACCENT
                elif status == 'failed':
                    status_label = self._t("phone.party_challenge_failed")
                    status_color = PHONE_RED

                left = self.font_small.render(f"{status_label}  {completed}/{target}", True, status_color)
                right = self.font_small.render(time_left, True, PHONE_TEXT)
                tip = self.font_small.render(self._t("phone.party_challenge_shared"), True, PHONE_TEXT_DIM)
                surf.blit(left, (ch_rect.x + 8, ch_rect.y + 4))
                surf.blit(right, (ch_rect.right - right.get_width() - 8, ch_rect.y + 4))
                surf.blit(tip, (ch_rect.x + 8, ch_rect.y + 18))

            bonus = self.font_small.render(self._t("phone.party_bonus_50"), True, PHONE_YELLOW)
            surf.blit(bonus, (sw - bonus.get_width() - 8, 24))

        y = 92
        for idx, (pid, party) in enumerate(joinable):

            card = pygame.Surface((PHONE_SCREEN_W - 16, 48), pygame.SRCALPHA)
            is_focus = self.kb_focus == (idx + 1)
            card.fill(PHONE_CARD_HOVER if is_focus else PHONE_CARD_BG)
            pygame.draw.rect(card, PHONE_BORDER, (0, 0, PHONE_SCREEN_W - 16, 48), 1, border_radius=6)
            if is_focus:
                pygame.draw.rect(card, (255, 255, 255), (0, 0, PHONE_SCREEN_W - 16, 48), 2, border_radius=6)
            leader = str(party.get('leader', '?'))
            size = int(party.get('size', 0) or 0)
            max_size = int(party.get('max_size', 3) or 3)
            title = self.font_small.render(f"{leader}", True, PHONE_TEXT)
            sub = self.font_small.render(f"{size}/{max_size}", True, PHONE_TEXT_DIM)
            join = self.font_small.render(self._t("phone.party_join"), True, PHONE_ACCENT)
            card.blit(title, (8, 8))
            card.blit(sub, (8, 26))
            card.blit(join, (card.get_width() - join.get_width() - 8, 15))
            surf.blit(card, (8, y))
            y += 56

        ms = self.mission_system
        if ms.active_mission:
            notif = self.font_small.render(self._t("phone.mission_in_progress"), True, PHONE_GREEN)
            surf.blit(notif, (sw // 2 - notif.get_width() // 2, sh - 40))

    def _render_back_button(self, surf, title_text):
        """Dessine le header avec bouton retour et titre."""
        y = 4
        back = self.font_title.render("< ", True, PHONE_ACCENT)
        surf.blit(back, (6, y))
        title = self.font_title.render(title_text, True, PHONE_TEXT)
        surf.blit(title, (26, y))

    def _render_missions(self, surf):
        """App Livraisons : mission active + disponibles."""
        title_text = self._t("phone.deliveries")
        self._render_back_button(surf, title_text)
        ms = self.mission_system
        sw = surf.get_width()
        sh = surf.get_height()
        car_model, car_color = self._equipped_car()

        # Keep equipped label in the free right-side header area to avoid colliding with title.
        title_w = self.font_title.size(title_text)[0]
        left_reserved = 26 + title_w + 12
        right_edge = sw - 6
        equip_max_w = max(48, right_edge - left_reserved)

        car_line = self._fit_text(
            self.font_small,
            self._t("phone.equipped", model=car_model, color=car_color),
            equip_max_w,
        )
        car_text = self.font_small.render(car_line, True, PHONE_TEXT_DIM)
        surf.blit(car_text, (right_edge - car_text.get_width(), 5))

        clip_y = 22
        clip_h = sh - clip_y
        y = 22 - self.scroll_offset
        clip_surf = pygame.Surface((sw - 8, clip_h), pygame.SRCALPHA)
        local_y = y - clip_y

        # Mission active
        if ms.active_mission:
            self._draw_active_mission(clip_surf, ms.active_mission, 0, local_y)
            local_y += MISSION_ACTIVE_CARD_H + MISSION_CARD_GAP

        # Séparateur
        label = self.font_text.render(self._t("phone.available"), True, PHONE_TEXT_DIM)
        clip_surf.blit(label, (4, local_y))
        local_y += 22

        if not ms.available_missions:
            no_msg = self.font_small.render(self._t("phone.none"), True, PHONE_TEXT_DIM)
            clip_surf.blit(no_msg, (4, local_y))
        else:
            for i, mission in enumerate(ms.available_missions):
                selectable = self._mission_is_selectable(mission)
                if selectable:
                    bg_color = PHONE_CARD_HOVER if (i == self.hovered_mission or i == self.kb_focus) else PHONE_CARD_BG
                else:
                    bg_color = (58, 30, 30) if (i == self.hovered_mission or i == self.kb_focus) else (44, 22, 22)
                self._draw_mission_card(clip_surf, mission, 0, local_y, clip_surf.get_width(), MISSION_CARD_H, bg_color, selectable=selectable)
                local_y += MISSION_CARD_H + MISSION_CARD_GAP

        surf.blit(clip_surf, (4, clip_y))

    def _draw_active_mission(self, surf, mission, x, y):
        """Dessine la mission active."""
        w = surf.get_width()
        card_h = MISSION_ACTIVE_CARD_H
        card = pygame.Surface((w, card_h), pygame.SRCALPHA)
        card.fill((30, 65, 30))
        pygame.draw.rect(card, PHONE_GREEN, (0, 0, w, card_h), 2, border_radius=6)

        type_color = self._type_color(mission.type)
        label = self.font_small.render(f"[{self._mission_type_label(mission.type)}] {self._t('phone.active_tag')}", True, type_color)
        card.blit(label, (6, 5))

        risk = self._mission_risk_level(mission)
        risk_text = self._t("phone.risky") if risk == "risky" else self._t("phone.chill")
        risk_color = PHONE_RED if risk == "risky" else PHONE_GREEN
        risk_surf = self.font_small.render(risk_text, True, risk_color)
        card.blit(risk_surf, (6, 19))

        status_text = self._t("phone.status_pickup") if not mission.picked_up else self._t("phone.status_dropoff")
        status_line = self._fit_text(self.font_small, status_text, w - label.get_width() - 22)
        status = self.font_small.render(status_line, True, PHONE_YELLOW)
        card.blit(status, (w - status.get_width() - 8, 5))

        req_label = self.mission_system.mission_requirement_label(mission) if hasattr(self.mission_system, "mission_requirement_label") else ""
        route_text = self._fit_text(
            self.font_small,
            f"{mission.pickup['name']} -> {mission.delivery['name']}",
            w - 12,
        )
        route = self.font_small.render(route_text, True, PHONE_TEXT)
        card.blit(route, (6, 22))

        cargo_text = f"{self._t('phone.cargo')}: {self._cargo_label(getattr(mission, 'cargo_type', 'colis'))} {int(getattr(mission, 'cargo_weight', 0))}kg"
        no_req = self._t("phone.no_requirement")
        if req_label and req_label != no_req:
            cargo_text = f"{cargo_text} | {req_label}"
        detail_lines = self._wrap_text(self.font_small, cargo_text, w - 96, max_lines=2)
        for idx, line in enumerate(detail_lines):
            cargo = self.font_small.render(line, True, PHONE_TEXT_DIM)
            card.blit(cargo, (6, 38 + idx * 13))

        time_color = PHONE_RED if mission.time_remaining < 30 else PHONE_TEXT
        timer = self.font_small.render(f"{int(mission.time_remaining)}s", True, time_color)
        card.blit(timer, (6, card_h - 22))

        reward = self.font_small.render(f"{mission.reward}$", True, PHONE_GREEN)
        card.blit(reward, (w - reward.get_width() - 8, card_h - 22))

        # Bouton abandon
        abandon = self.font_small.render(f"[{self._t('phone.abandon')}]", True, PHONE_RED)
        card.blit(abandon, (w - abandon.get_width() - 8, card_h - 36))

        surf.blit(card, (x, y))

    def _draw_mission_card(self, surf, mission, x, y, w, h, bg_color, selectable=True):
        """Dessine une carte de mission disponible."""
        card = pygame.Surface((w, h), pygame.SRCALPHA)
        card.fill(bg_color)
        pygame.draw.rect(card, PHONE_BORDER, (0, 0, w, h), 1, border_radius=6)

        type_color = self._type_color(mission.type)
        label = self.font_small.render(f"[{self._mission_type_label(mission.type)}]", True, type_color)
        card.blit(label, (6, 5))

        risk = self._mission_risk_level(mission)
        risk_text = self._t("phone.risky") if risk == "risky" else self._t("phone.chill")
        risk_color = PHONE_RED if risk == "risky" else PHONE_GREEN
        risk_surf = self.font_small.render(risk_text, True, risk_color if selectable else PHONE_TEXT_DIM)
        card.blit(risk_surf, (6 + label.get_width() + 8, 5))

        reward = self.font_text.render(f"{mission.reward}$", True, PHONE_GREEN if selectable else PHONE_TEXT_DIM)
        card.blit(reward, (w - reward.get_width() - 8, 5))

        route_text = self._fit_text(
            self.font_small,
            f"{mission.pickup['name']} -> {mission.delivery['name']}",
            w - 12,
        )
        route = self.font_small.render(route_text, True, PHONE_TEXT)
        card.blit(route, (6, 22))

        req_label = self.mission_system.mission_requirement_label(mission) if hasattr(self.mission_system, "mission_requirement_label") else ""
        detail = f"{self._cargo_label(getattr(mission, 'cargo_type', 'colis'))} {int(getattr(mission, 'cargo_weight', 0))}kg"
        no_req = self._t("phone.no_requirement")
        if req_label and req_label != no_req:
            detail = f"{detail} | {req_label}"
        detail_color = PHONE_TEXT_DIM if selectable else PHONE_RED
        detail_lines = self._wrap_text(self.font_small, detail, w - 12, max_lines=2)
        for idx, line in enumerate(detail_lines):
            detail_surf = self.font_small.render(line, True, detail_color)
            card.blit(detail_surf, (6, 36 + idx * 12))

        timer_color = PHONE_TEXT_DIM if selectable else PHONE_RED
        timer = self.font_small.render(f"{int(mission.time_limit)}s", True, timer_color)
        card.blit(timer, (6, h - 18))

        if not selectable:
            denied = self.font_small.render(self._t("phone.incompatible"), True, PHONE_RED)
            card.blit(denied, (w - denied.get_width() - 8, h - 18))

        surf.blit(card, (x, y))

    def _render_gps(self, surf, player=None, game_map=None):
        """App GPS : carte complète avec marqueurs."""
        surf.fill((12, 18, 24))

        self._render_back_button(surf, self._t("phone.gps"))
        ms = self.mission_system
        sw = surf.get_width()
        sh = surf.get_height()

        pad = 10
        map_area_y = 32
        legend_row_h = max(16, self.font_small.get_height() + 4)
        right_col_w = max(180, int(sw * 0.30))
        map_w_px = max(220, sw - right_col_w - pad * 3)
        map_h_px = max(150, sh - map_area_y - pad - legend_row_h)
        map_x = pad
        map_y = map_area_y

        map_surf = pygame.Surface((map_w_px, map_h_px), pygame.SRCALPHA)
        if self._gps_minimap_bg is not None:
            map_bg = pygame.transform.smoothscale(self._gps_minimap_bg, (map_w_px, map_h_px))
            map_surf.blit(map_bg, (0, 0))
            veil = pygame.Surface((map_w_px, map_h_px), pygame.SRCALPHA)
            veil.fill((10, 14, 18, 70))
            map_surf.blit(veil, (0, 0))
        else:
            map_surf.fill((25, 40, 25))
        pygame.draw.rect(map_surf, PHONE_BORDER, (0, 0, map_w_px, map_h_px), 1, border_radius=4)

        map_w = max(1.0, float(game_map.width_px) if game_map else 8192.0)
        map_h = max(1.0, float(game_map.height_px) if game_map else 8192.0)
        sx = map_w_px / map_w
        sy = map_h_px / map_h

        hover_map_pos = None
        if (
            self.current_screen == "gps"
            and isinstance(self.gps_hover_local, (tuple, list))
            and len(self.gps_hover_local) >= 2
            and sw >= sh
        ):
            hx = float(self.gps_hover_local[0])
            hy = float(self.gps_hover_local[1])
            if map_x <= hx <= map_x + map_w_px and map_y <= hy <= map_y + map_h_px:
                hover_map_pos = (hx - map_x, hy - map_y)

        hovered_poi = None
        hovered_d2 = float("inf")

        # Points d'intérêt indexés; noms complets lisibles dans la légende paginée.
        for idx, loc in enumerate(MISSION_LOCATIONS, start=1):
            lx = int(float(loc['x']) * sx)
            ly = int(float(loc['y']) * sy)
            pygame.draw.circle(map_surf, (95, 95, 95), (lx, ly), 2)
            num = self.font_gps.render(str(idx), True, (220, 220, 220))
            label_pos = (lx + 3, ly - 4)
            map_surf.blit(num, label_pos)

            if hover_map_pos is not None:
                mx, my = hover_map_pos
                label_rect = num.get_rect(topleft=label_pos).inflate(6, 6)
                if label_rect.collidepoint(mx, my):
                    cx, cy = label_rect.center
                    d2 = (mx - cx) ** 2 + (my - cy) ** 2
                    if d2 < hovered_d2:
                        hovered_d2 = d2
                        hovered_poi = (idx, lx, ly)

        if hovered_poi is not None:
            h_idx, h_x, h_y = hovered_poi
            big_num = self.font_small.render(str(h_idx), True, (255, 255, 255))
            big_pos = (h_x + 4, h_y - 6)
            bg_rect = big_num.get_rect(topleft=big_pos).inflate(6, 4)
            pygame.draw.rect(map_surf, (16, 24, 36), bg_rect, border_radius=3)
            pygame.draw.rect(map_surf, PHONE_ACCENT, bg_rect, 1, border_radius=3)
            pygame.draw.circle(map_surf, PHONE_ACCENT, (h_x, h_y), 5, 1)
            map_surf.blit(big_num, big_pos)

            if 1 <= h_idx <= len(MISSION_LOCATIONS):
                hover_name = str(MISSION_LOCATIONS[h_idx - 1].get("name", ""))
                hover_line = self._fit_text(self.font_small, f"#{h_idx} {hover_name}", map_w_px - 10)
                hover_txt = self.font_small.render(hover_line, True, (255, 255, 255))
                hover_bg = hover_txt.get_rect(topleft=(8, 6)).inflate(8, 4)
                pygame.draw.rect(map_surf, (14, 20, 32), hover_bg, border_radius=3)
                pygame.draw.rect(map_surf, PHONE_BORDER, hover_bg, 1, border_radius=3)
                map_surf.blit(hover_txt, (8, 6))

        # Missions disponibles
        for m in ms.available_missions:
            px = int(float(m.pickup['x']) * sx)
            py_ = int(float(m.pickup['y']) * sy)
            pygame.draw.circle(map_surf, PHONE_YELLOW, (px, py_), 4)

        # Mission active
        if ms.active_mission:
            m = ms.active_mission
            if not m.picked_up:
                px = int(m.pickup['x'] * sx)
                py_ = int(m.pickup['y'] * sy)
                pygame.draw.circle(map_surf, PHONE_GREEN, (px, py_), 6)
                pygame.draw.circle(map_surf, (255, 255, 255), (px, py_), 6, 1)
            dx = int(float(m.delivery['x']) * sx)
            dy = int(float(m.delivery['y']) * sy)
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

        legend_x = map_x + map_w_px + pad
        legend_y = map_y
        legend_w = sw - legend_x - pad
        legend_h = map_h_px
        legend = pygame.Surface((legend_w, legend_h), pygame.SRCALPHA)
        legend.fill((18, 24, 33, 230))
        pygame.draw.rect(legend, PHONE_BORDER, (0, 0, legend_w, legend_h), 1, border_radius=6)

        title = self.font_small.render(self._t("phone.legend_places"), True, PHONE_TEXT)
        legend.blit(title, (8, 6))

        row_h = max(12, self.font_small.get_height() + 2)
        hint = self.font_small.render(self._t("phone.legend_scroll_hint"), True, PHONE_TEXT_DIM)
        hint_y = legend_h - hint.get_height() - 6
        list_top = 24
        list_bottom = max(list_top, hint_y - 6)
        page_size = self._gps_legend_page_size(legend_h)
        total = len(MISSION_LOCATIONS)
        pages = max(1, math.ceil(total / page_size))
        page_index = max(0, min(pages - 1, int(self.gps_legend_page)))
        if sw >= sh:
            self.gps_legend_page = page_index
        page_text = self.font_small.render(f"{page_index + 1}/{pages}", True, PHONE_TEXT_DIM)
        legend.blit(page_text, (legend_w - page_text.get_width() - 8, 6))

        start = page_index * page_size
        end = min(total, start + page_size)
        y = list_top
        for idx in range(start, end):
            loc = MISSION_LOCATIONS[idx]
            line = f"{idx + 1}. {loc['name']}"
            row = self._fit_text(self.font_small, line, legend_w - 14)
            txt = self.font_small.render(row, True, (210, 210, 220))
            legend.blit(txt, (8, y))
            y += row_h

        legend.blit(hint, (8, hint_y))
        surf.blit(legend, (legend_x, legend_y))

        legends = [
            (PHONE_ACCENT, self._t("phone.legend_you")),
            (PHONE_GREEN, self._t("phone.legend_pickup")),
            (PHONE_RED, self._t("phone.legend_dropoff")),
            (PHONE_YELLOW, self._t("phone.legend_available")),
        ]
        lx_pos = map_x
        ly_pos = map_y + map_h_px + max(1, (legend_row_h - self.font_small.get_height()) // 2)
        for color, text in legends:
            t = self.font_small.render(text, True, PHONE_TEXT_DIM)
            cy = ly_pos + t.get_height() // 2
            pygame.draw.circle(surf, color, (lx_pos + 5, cy), 4)
            surf.blit(t, (lx_pos + 13, ly_pos))
            lx_pos += t.get_width() + 22

    def _render_shop(self, surf):
        """App Boutique : catalogue avec aperçu voiture, stats et achat."""
        self._render_back_button(surf, self._t("phone.shop"))
        ms = self.mission_system
        sw = surf.get_width()
        sh = surf.get_height()

        money_txt = self.font_text.render(f"${ms.money}", True, PHONE_GREEN)
        surf.blit(money_txt, (sw - money_txt.get_width() - 8, 4))

        clip_y = 22
        clip_h = sh - clip_y
        clip_surf = pygame.Surface((sw - 8, clip_h), pygame.SRCALPHA)

        sorted_vehicles = sorted(VEHICLE_CATALOG.items(), key=lambda x: x[1]["price"])
        card_h = SHOP_CARD_H
        card_gap = SHOP_CARD_GAP
        local_y = -self.shop_scroll
        preview_size = 52

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

            colors = self._model_colors(model)
            sel_color = self._selected_color(model)
            sel_ci = int(self.shop_selected_colors.get(model, 0) or 0)

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
                card.blit(preview_img, (4, 20))
                text_x_offset = preview_size + 8

            price_color = PHONE_GREEN if ms.money >= stats["price"] else PHONE_RED
            price_txt = self.font_text.render(f"${stats['price']}" if stats["price"] > 0 else self._t("phone.free"), True, price_color)
            card.blit(price_txt, (w - price_txt.get_width() - 8, 4))

            max_model_w = max(50, w - text_x_offset - price_txt.get_width() - 16)
            model_line = self._fit_text(self.font_text, model, max_model_w)
            name_surf = self.font_text.render(model_line, True, PHONE_TEXT)
            card.blit(name_surf, (text_x_offset, 4))

            # Color selector row (below name)
            color_x = w - len(colors) * 14 - 4
            for ci, color_name in enumerate(colors):
                rgb = self._color_name_to_rgb(color_name)
                cx = color_x + ci * 14
                pygame.draw.rect(card, rgb, (cx, 28, 12, 12), border_radius=2)
                if ci == sel_ci:
                    pygame.draw.rect(card, (255, 255, 255), (cx - 1, 27, 14, 14), 2, border_radius=2)

            # Stats bars (right of preview)
            bar_y = 44
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

            # Description + hint gameplay
            hint_text = self._t(self._vehicle_mission_hint(stats))
            footer_w = max(28, w - text_x_offset - 84)
            desc_line = self._fit_text(self.font_small, stats.get("desc", ""), footer_w)
            hint_lines = self._wrap_text(self.font_small, hint_text, footer_w, max_lines=2)
            desc = self.font_small.render(desc_line, True, PHONE_TEXT_DIM)
            card.blit(desc, (text_x_offset, card_h - 42))

            hint_y = card_h - 29
            for line in hint_lines:
                hint = self.font_small.render(line, True, PHONE_ACCENT)
                card.blit(hint, (text_x_offset, hint_y))
                hint_y += self.font_small.get_height() + 1

            # Buy/equip button
            owned = ms.has_car(model, sel_color)
            is_current = self.player and self.player.car == (model, sel_color)
            if is_current:
                btn_text, btn_color = self._t("phone.btn_equipped"), (100, 100, 120)
            elif owned:
                btn_text, btn_color = self._t("phone.btn_equip"), PHONE_ACCENT
            elif ms.money >= stats["price"]:
                btn_text, btn_color = self._t("phone.btn_buy"), PHONE_GREEN
            else:
                btn_text, btn_color = self._t("phone.btn_buy"), (80, 40, 40)

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
        self._render_back_button(surf, self._t("phone.garage"))
        ms = self.mission_system
        sw = surf.get_width()
        sh = surf.get_height()

        clip_y = 22
        clip_h = sh - clip_y
        clip_surf = pygame.Surface((sw - 8, clip_h), pygame.SRCALPHA)

        card_h = GARAGE_CARD_H
        card_gap = GARAGE_CARD_GAP
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
                card.blit(preview, (6, 9))

            raw_name = f"{car_data['model']} - {car_data['color']}"
            max_name_w = max(40, w - 56 - 92)
            name_txt = self.font_text.render(self._fit_text(self.font_text, raw_name, max_name_w), True, PHONE_TEXT)
            card.blit(name_txt, (52, 8))

            profile = VEHICLE_CATALOG.get(car_data['model'], {})
            hint = self._fit_text(self.font_small, self._t(self._vehicle_mission_hint(profile)), max_name_w)
            hint_txt = self.font_small.render(hint, True, PHONE_TEXT_DIM)
            card.blit(hint_txt, (52, 30))

            if is_current:
                eq_surf = self.font_small.render(self._t("phone.btn_equipped"), True, PHONE_GREEN)
                card.blit(eq_surf, (w - eq_surf.get_width() - 8, 10))
            else:
                sel_surf = self.font_small.render(self._t("phone.btn_select"), True, PHONE_ACCENT)
                card.blit(sel_surf, (w - sel_surf.get_width() - 8, 10))

            clip_surf.blit(card, (0, local_y))
            local_y += card_h + card_gap

        surf.blit(clip_surf, (4, clip_y))

    def _render_stats(self, surf):
        """App Stats : statistiques du joueur."""
        self._render_back_button(surf, self._t("phone.stats"))
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
            (self._t("phone.stats.money"), f"${ms.money}", PHONE_GREEN),
            (self._t("phone.stats.deliveries"), str(ms.completed_count), PHONE_ACCENT),
            (self._t("phone.stats.failed"), str(ms.failed_count), PHONE_RED),
            (self._t("phone.stats.vehicles"), str(len(ms.owned_cars)), PHONE_YELLOW),
            (self._t("phone.stats.distance"), dist_str, PHONE_ACCENT),
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
            vehicle_line = self._fit_text(self.font_text, self._t("phone.stats.vehicle", model=self.player.car[0], color=self.player.car[1]), sw - 20)
            car_label = self.font_text.render(vehicle_line, True, PHONE_TEXT)
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
