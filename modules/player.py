import pygame

# Player Constants
PLAYER_START_X = 6000
PLAYER_START_Y = 6000
PLAYER_SPEED = 5
PLAYER_SIZE = 120

# World Constants
WORLD_WIDTH = 12000
WORLD_HEIGHT = 12000

# Server Constants
SERVER_PORT = 12345

class Player:
    def __init__(self, car=('SUPERCAR TOPDOWN', 'Black')):
        self.x = PLAYER_START_X
        self.y = PLAYER_START_Y
        self.speed = PLAYER_SPEED
        self.size = PLAYER_SIZE
        self.car = car
        car_name = car[0].replace(' TOP DOWN', '').replace(' TOPDOWN', '').replace(' ', '').upper()
        self.image_path = f'assets/images/cars/{car[0]}/{car[1]}/SEPARATED/{car[1]}_{car_name}_CLEAN_All_000.png'
        self.image = pygame.image.load(self.image_path)
        self.image = pygame.transform.scale(self.image, (self.size, self.size))

    def update(self, keys):
        """Update player position based on input."""
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            self.x -= self.speed
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            self.x += self.speed
        if keys[pygame.K_UP] or keys[pygame.K_w]:
            self.y -= self.speed
        if keys[pygame.K_DOWN] or keys[pygame.K_s]:
            self.y += self.speed

        # Keep player in world bounds
        self.x = max(0, min(WORLD_WIDTH - self.size, self.x))
        self.y = max(0, min(WORLD_HEIGHT - self.size, self.y))

    def render(self, screen, camera_x, camera_y, color=(0, 0, 255)):
        """Render the player on screen."""
        screen_x = self.x - camera_x
        screen_y = self.y - camera_y
        screen.blit(self.image, (screen_x, screen_y))

    def get_position(self):
        """Get current position as tuple."""
        return self.x, self.y