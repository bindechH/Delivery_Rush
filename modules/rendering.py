"""
Module de rendu pour Delivery Rush
Gère l'affichage des éléments graphiques : joueur, autres joueurs, interface utilisateur.
Fournit des fonctions utilitaires pour le texte et les sprites.
"""

import pygame
from pathlib import Path
from .player import Player, resolve_car_frame_path
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

class MainMenu:
    def __init__(self, screen, font, small_font, screen_width, screen_height, server_ip='localhost', username='', car=('SUV', 'Black'), sound_manager=None):
        self.screen = screen
        self.font = font
        # utiliser une police plus petite pour le menu
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
        # menu car display size (pixels)
        self.menu_car_size = 160
        self.volume_levels = [0.0, 0.1, 0.25, 0.5, 0.75, 1.0]
        self.volume_idx = 2
        self.logo = pygame.image.load('assets/images/HUD/Delivery Rush.png')
        self.background = pygame.image.load('assets/images/HUD/backround.png').convert()
        self.background = pygame.transform.scale(self.background, (self.screen_width, self.screen_height))
        self.show_error = False
        self.error_message = ""
        self.btn_image = pygame.image.load('assets/images/HUD/SOLOBTN.png').convert()
        self.btn_image_multi = pygame.image.load('assets/images/HUD/multibtn.png').convert()
        self.btn_image_quit = pygame.image.load('assets/images/HUD/quitbtn.png').convert()
        # load les frames de la voiture pour l'animation du menu
        self.car_frames = self._load_menu_frames(car)
        if not self.car_frames:
            car_path = resolve_car_frame_path(car[0], car[1], 0)
            self.car_frames = [pygame.image.load(car_path).convert_alpha()]
        self.car_frames = [pygame.transform.smoothscale(f, (self.menu_car_size, self.menu_car_size)) for f in self.car_frames]

    def display_menu(self):
        """Display the main menu."""
        self.screen.blit(self.background, (0, 0))

        # Dessiner le logo
        if self.logo:
            logo_rect = self.logo.get_rect(center=(self.screen_width // 2, 200))
            self.screen.blit(self.logo, logo_rect)

        frame = self._current_menu_frame()
        voiture_rect = frame.get_rect(center=(650, 370))
        self.screen.blit(frame, voiture_rect)

        # Afficher le pseudo sous la voiture
        if self.username:
            # Nom d'utilisateur sous la voiture
            draw_text_bg_center(self.screen, self.username, self.name_font, (255, 255, 255), voiture_rect.centerx, voiture_rect.bottom + 6)
            # Nom de la voiture sous le pseudo
            car_label = f"{self.car[0]} - {self.car[1]}".strip()
            draw_text_bg_center(self.screen, car_label, self.name_font, (220, 220, 220), voiture_rect.centerx, voiture_rect.bottom + 38)

        # Dessiner le bouton Solo
        solo_rect = self.btn_image.get_rect(center=(self.screen_width // 2, 350))
        self.screen.blit(self.btn_image, solo_rect)
        #draw_text(self.screen, "Solo", self.small_font, (0, 0, 0), 370, 340)

        # Dessiner le bouton Multijoueur
        multi_rect = self.btn_image_multi.get_rect(center=(self.screen_width // 2, 425))
        self.screen.blit(self.btn_image_multi, multi_rect)

        # Dessiner le bouton Quitter
        quit_rect = self.btn_image_quit.get_rect(center=(self.screen_width // 2, 500))
        self.screen.blit(self.btn_image_quit, quit_rect)

        # Afficher l'IP du serveur en haut à gauche (noir, plus petit)
        ip_font = pygame.font.Font("assets/fonts/ari-w9500-bold.ttf", 18)
        ip_font.set_bold(True)
        ip_surface = ip_font.render(f"IP DU SERVEUR: {self.server_ip}", True, (0, 0, 0))
        ip_rect = ip_surface.get_rect(topleft=(20, 20))
        self.screen.blit(ip_surface, ip_rect)

        # Bouton volume en bas à droite
        vol_label = f"SON {int(self.volume_levels[self.volume_idx]*100)}%"
        vol_font = pygame.font.Font("assets/fonts/ari-w9500-bold.ttf", 22)
        vol_font.set_bold(True)
        vol_surface = vol_font.render(vol_label, True, (255, 255, 255))
        vol_bg = pygame.Surface((vol_surface.get_width() + 12, vol_surface.get_height() + 8), pygame.SRCALPHA)
        vol_bg.fill((0, 0, 0, 160))
        vol_rect = vol_bg.get_rect(bottomright=(self.screen_width - 20, self.screen_height - 20))
        vol_bg.blit(vol_surface, (6, 4))
        self.screen.blit(vol_bg, vol_rect)

        self.vol_rect = vol_rect

        # Dessiner le message d'erreur s'il y en a
        if self.show_error:
            draw_text(self.screen, self.error_message, self.small_font, (255, 0, 0), 250, 50)
            # Effacer automatiquement l'erreur après quelques frames (environ 3 secondes à 60 FPS)
            if not hasattr(self, 'error_frame_counter'):
                self.error_frame_counter = 0
            self.error_frame_counter += 1
            if self.error_frame_counter > 180:  # 3 secondes à 60 FPS
                self.show_error = False
                self.error_frame_counter = 0

        return solo_rect, multi_rect, quit_rect, vol_rect

    def handle_menu_input(self, event, solo_rect, multi_rect, quit_rect, vol_rect=None):
        """Gérer les clics sur les boutons du menu."""
        if event.type == pygame.MOUSEBUTTONDOWN:
            if solo_rect.collidepoint(event.pos):
                return GAME, False  # Retour à l'état GAME en mode solo
            elif multi_rect.collidepoint(event.pos):
                return GAME, True   # Retour à l'état GAME en mode multijoueur
            elif quit_rect.collidepoint(event.pos):
                return 'QUIT', None # Quitter le jeu
            elif vol_rect and vol_rect.collidepoint(event.pos):
                self.volume_idx = (self.volume_idx + 1) % len(self.volume_levels)
                if self.sound_manager:
                    self.sound_manager.set_music_volume(self.volume_levels[self.volume_idx])
                return None, None
        return None, None

    def _load_menu_frames(self, car):
        """Charger les frames de la voiture pour l'animation du menu."""
        model, color = car
        car_name = model.replace(' ', '').upper()
        base_candidates = [
            model,
            model.replace(' ', ''),
        ]
        base_candidates = [c for c in base_candidates if c]
        frames = []
        for base in base_candidates:
            folder = Path("assets/images/cars") / base / color / "MOVE" / "SOUTHWEST" / "SEPARATED"
            if folder.exists():
                files = sorted(folder.glob(f"{color}_{car_name}_CLEAN_SOUTHWEST_*.png"))
                frames = [pygame.image.load(str(p)).convert_alpha() for p in files]
                if frames:
                    return frames
        return frames

    def _current_menu_frame(self):
        if not self.car_frames:
            return None
        idx = int(pygame.time.get_ticks() / 120) % len(self.car_frames)
        return self.car_frames[idx]


class GameUI:
    """Gère le rendu en jeu et les entrées."""
    
    def __init__(self, screen, font, small_font, player, game_map, other_players=None, screen_width=800, screen_height=600, username="Player", name_font=None):
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
        self.show_coords = False
        self.car_images = {}  # Cache pour différentes images de voitures
        self.car_frames = {}  # Cache pour les 48 frames directionnelles par voiture
        # Rendre l'arrière-plan
        self.background = pygame.image.load('assets/images/HUD/backround.png').convert()
        self.background = pygame.transform.scale(self.background, (self.screen_width, self.screen_height))

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
            # load 48 frames
            frames = []
            for idx in range(48):
                image_path = resolve_car_frame_path(car[0], car[1], idx)
                img = pygame.image.load(image_path)
                img = pygame.transform.scale(img, (self.player.size, self.player.size))
                frames.append(img)
            self.car_frames[car_key] = frames
        frames = self.car_frames[car_key]
        idx = int((angle % 360) / 7.5) % 48
        return frames[idx]

    def update_camera(self):
        """Centrer la caméra sur la position du joueur."""
        self.camera_x = self.player.x + self.player.size / 2 - self.screen_width / 2
        self.camera_y = self.player.y + self.player.size / 2 - self.screen_height / 2
        # Clamp camera so top-left stays at (0,0) and doesn't go past map edges
        if hasattr(self.game_map, 'width_px') and hasattr(self.game_map, 'height_px'):
            max_cam_x = max(0, self.game_map.width_px - self.screen_width)
            max_cam_y = max(0, self.game_map.height_px - self.screen_height)
            self.camera_x = max(0, min(max_cam_x, self.camera_x))
            self.camera_y = max(0, min(max_cam_y, self.camera_y))

    def handle_events(self, events):
        """Gérer les événements d'entrée du jeu."""
        for event in events:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_c:  # Basculer l'affichage des coordonnées avec la touche 'C'
                    self.show_coords = not self.show_coords

    def update(self, keys, dt, other_players_rects=None):
        """Mettre à jour l'état du jeu à chaque frame."""
        self.player.update(keys, dt, other_players_rects)
        self.update_camera()

    def render(self):
        """Rendre tous les objets du jeu et l'interface utilisateur."""
        # Draw background image
        self.screen.blit(self.background, (0, 0))
        self._render_map()
        self._render_other_players()
        self._render_player()
        self._render_ui()

    def _render_map(self):
        """Rendre la carte du jeu."""
        self.game_map.render(self.screen, self.camera_x, self.camera_y)

    def _render_other_players(self):
        """Afficher les autres joueurs en multijoueur (avec rotation si fournie)."""
        for player_username, player_data in self.other_players.items():
            if isinstance(player_data, dict):
                x, y = player_data.get('x', 0), player_data.get('y', 0)
                car = player_data.get('car', ('SUPERCAR', 'Black'))
                angle = player_data.get('angle', 0.0)
            else:
                x, y = player_data
                car = ('SUPERCAR', 'Black')
                angle = 0.0
            screen_x = x - self.camera_x
            screen_y = y - self.camera_y
            # Dessiner les voitures uniquement si dans l'écran (approx)
            if -self.player.size < screen_x < self.screen_width and -self.player.size < screen_y < self.screen_height:
                # choose frame according to angle if available
                image = self._get_car_frame(car, angle) if isinstance(player_data, dict) else self._get_car_image(car)
                self.screen.blit(image, (int(screen_x), int(screen_y)))
                # Dessiner le nom d'utilisateur au-dessus du joueur (centré)
                label_center_x = int(screen_x + self.player.size / 2)
                label_top_y = int(screen_y - 22)
                draw_text_bg_center(self.screen, player_username, self.name_font, (255, 255, 255), label_center_x, label_top_y)

    def _render_player(self):
        """Afficher le joueur local."""
        self.player.render(self.screen, self.camera_x, self.camera_y)
        # Dessiner le nom d'utilisateur au-dessus du joueur (appliquer zoom to position)
        screen_x = self.player.x - self.camera_x
        screen_y = self.player.y - self.camera_y
        label_center_x = int(screen_x + self.player.size / 2)
        label_top_y = int(screen_y - 22)
        draw_text_bg_center(self.screen, self.username, self.name_font, (255, 255, 255), label_center_x, label_top_y)

    def _render_ui(self):
        """Rendre les éléments de l'interface utilisateur (coordonnées, etc)."""
        if self.show_coords:
            coord_text = f"X: {int(round(self.player.x))} Y: {int(round(self.player.y))}"
            draw_text_bg(self.screen, coord_text, self.small_font, (255, 255, 255), 10, 10)