import pygame

# World Constants
WORLD_WIDTH = 12000
WORLD_HEIGHT = 12000
TILE_SIZE = 100

# Screen Constants (defaults, can be overridden)
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600

class GameMap:
    def __init__(self):
        self.width = WORLD_WIDTH
        self.height = WORLD_HEIGHT
        self.tile_size = TILE_SIZE

    def render(self, screen, camera_x, camera_y):
        """Render the map grid."""
        for x in range(0, self.width, self.tile_size):
            for y in range(0, self.height, self.tile_size):
                # Only draw visible tiles
                screen_x = x - camera_x
                screen_y = y - camera_y
                if -self.tile_size < screen_x < SCREEN_WIDTH and -self.tile_size < screen_y < SCREEN_HEIGHT:
                    color = (255, 255, 255) if (x // self.tile_size + y // self.tile_size) % 2 == 0 else (128, 128, 128)
                    pygame.draw.rect(screen, color, (screen_x, screen_y, self.tile_size, self.tile_size))