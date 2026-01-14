import pygame
from .player import Player
from .map import GameMap

# Game States
MENU = 0
GAME = 1

def draw_text(screen, text, font, color, x, y):
    """Draw text on screen at specified position."""
    text_surface = font.render(text, True, color)
    screen.blit(text_surface, (x, y))

class MainMenu:
    def __init__(self, screen, font, small_font, screen_width, screen_height, server_ip='localhost'):
        self.screen = screen
        self.font = font
        self.small_font = small_font
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.server_ip = server_ip
        self.logo = pygame.image.load('assets/images/HUD/Delivery Rush.png')
        self.show_error = False
        self.error_message = ""

    def display_menu(self):
        """Display the main menu."""
        self.screen.fill((50, 50, 50))

        # Draw logo (placeholder)
        if self.logo:
            logo_rect = self.logo.get_rect(center=(self.screen_width // 2, 80))
            self.screen.blit(self.logo, logo_rect)


        # Draw Solo button
        solo_rect = pygame.Rect(300, 300, 200, 50)
        pygame.draw.rect(self.screen, (0, 255, 0), solo_rect)
        draw_text(self.screen, "Solo", self.small_font, (0, 0, 0), 370, 310)

        # Draw Multiplayer button
        multi_rect = pygame.Rect(300, 400, 200, 50)
        pygame.draw.rect(self.screen, (0, 0, 255), multi_rect)
        draw_text(self.screen, "Multiplayer", self.small_font, (255, 255, 255), 330, 410)

        # Draw error message if any
        if self.show_error:
            draw_text(self.screen, self.error_message, self.small_font, (255, 0, 0), 220, 500)
            # Auto-clear error after a few frames (roughly 3 seconds at 60 FPS)
            if not hasattr(self, 'error_frame_counter'):
                self.error_frame_counter = 0
            self.error_frame_counter += 1
            if self.error_frame_counter > 180:  # 3 seconds at 60 FPS
                self.show_error = False
                self.error_frame_counter = 0

        return solo_rect, multi_rect

    def handle_menu_input(self, event, solo_rect, multi_rect):
        """Handle menu button clicks."""
        if event.type == pygame.MOUSEBUTTONDOWN:
            if solo_rect.collidepoint(event.pos):
                return GAME, False  # Return to GAME state in solo mode
            elif multi_rect.collidepoint(event.pos):
                return GAME, True   # Return to GAME state in multiplayer mode
        return None, None


class GameUI:
    """Handles in-game rendering and input."""
    
    def __init__(self, screen, font, small_font, player, game_map, other_players=None, screen_width=800, screen_height=600, username="Player"):
        self.screen = screen
        self.font = font
        self.small_font = small_font
        self.player = player
        self.game_map = game_map
        self.other_players = other_players if other_players is not None else {}
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.username = username
        self.camera_x = self.player.x - self.screen_width // 2
        self.camera_y = self.player.y - self.screen_height // 2
        self.show_coords = False
        self.car_images = {}  # Cache for different car images

    def _get_car_image(self, car):
        """Get or load the image for a specific car."""
        car_key = tuple(car)  # Make it hashable
        if car_key not in self.car_images:
            car_name = car[0].replace(' TOP DOWN', '').replace(' TOPDOWN', '').replace(' ', '').upper()
            image_path = f'assets/images/cars/{car[0]}/{car[1]}/SEPARATED/{car[1]}_{car_name}_CLEAN_All_000.png'
            image = pygame.image.load(image_path)
            image = pygame.transform.scale(image, (self.player.size, self.player.size))
            self.car_images[car_key] = image
        return self.car_images[car_key]

    def update_camera(self):
        """Center camera on player position."""
        self.camera_x = self.player.x - self.screen_width // 2
        self.camera_y = self.player.y - self.screen_height // 2

    def handle_events(self, events):
        """Process game input events."""
        for event in events:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_c:  # Toggle coordinate display with 'C' key
                    self.show_coords = not self.show_coords

    def update(self, keys):
        """Update game state each frame."""
        self.player.update(keys)
        self.update_camera()

    def render(self):
        """Render all game objects and UI."""
        self.screen.fill((0, 0, 0))  # Clear screen
        self._render_map()
        self._render_other_players()
        self._render_player()
        self._render_ui()

    def _render_map(self):
        """Render the game map."""
        self.game_map.render(self.screen, self.camera_x, self.camera_y)

    def _render_other_players(self):
        """Render other multiplayer players."""
        for player_username, player_data in self.other_players.items():
            if isinstance(player_data, dict):
                x, y = player_data.get('x', 0), player_data.get('y', 0)
                car = player_data.get('car', ('SUPERCAR TOPDOWN', 'Black'))
            else:
                x, y = player_data
                car = ('SUPERCAR TOPDOWN', 'Black')
            screen_x = x - self.camera_x
            screen_y = y - self.camera_y
            # Only render if on screen
            if -self.player.size < screen_x < self.screen_width and -self.player.size < screen_y < self.screen_height:
                image = self._get_car_image(car)
                self.screen.blit(image, (screen_x, screen_y))
                # Draw username above player
                draw_text(self.screen, player_username, self.small_font, (255, 255, 0), screen_x, screen_y - 20)

    def _render_player(self):
        """Render the local player."""
        self.player.render(self.screen, self.camera_x, self.camera_y)
        # Draw username above player
        screen_x = self.player.x - self.camera_x
        screen_y = self.player.y - self.camera_y
        draw_text(self.screen, self.username, self.small_font, (0, 255, 0), screen_x, screen_y - 20)

    def _render_ui(self):
        """Render UI elements (coordinates, etc)."""
        if self.show_coords:
            coord_text = f"X: {self.player.x} Y: {self.player.y}"
            draw_text(self.screen, coord_text, self.small_font, (255, 255, 255), 10, 10)