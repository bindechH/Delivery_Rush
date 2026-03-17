"""
Module de gestion de la carte pour Delivery Rush
Utilise PyTMX et PyScroll pour charger et afficher des cartes Tiled (.tmx)
Gère le rendu, le scrolling et les collisions de la carte.
"""

import pygame
import pytmx
import pyscroll
from .player import PLAYER_SIZE, HITBOX_SCALE


class GameMap:
    """
    Gestionnaire de carte Tiled pour le jeu
    Charge et affiche la carte avec scrolling optimisé
    Gère également les collisions
    """

    def __init__(self, tmx_file, screen_size, zoom=1.0):
        """
        Initialisation de la carte

        tmx_file: chemin vers le fichier .tmx
        screen_size: dimensions de l'écran (largeur, hauteur)
        zoom: facteur de zoom de la carte (ex: 2.0 = tuiles 2x plus grandes)
        """

        # Chargement des données Tiled
        self.tmx_data = pytmx.util_pygame.load_pygame(tmx_file)

        # Données utilisées par PyScroll
        self.map_data = pyscroll.data.TiledMapData(self.tmx_data)

        # Zoom — handled by rendering to a smaller viewport then scaling up,
        # NOT via pyscroll's built-in zoom (which causes sub-pixel rounding
        # mismatch between map tiles and sprites).
        self.zoom = zoom
        self._screen_size = screen_size

        # Viewport at 1:1 world scale (screen / zoom)
        vw = max(1, int(screen_size[0] / self.zoom))
        vh = max(1, int(screen_size[1] / self.zoom))

        # Renderer at 1:1 scale, viewport-sized
        self.map_layer = pyscroll.BufferedRenderer(
            self.map_data,
            (vw, vh)
        )
        self._viewport = pygame.Surface((vw, vh))

        # Dimensions
        self.tile_width = self.tmx_data.tilewidth
        self.tile_height = self.tmx_data.tileheight
        self.map_width_tiles = self.tmx_data.width
        self.map_height_tiles = self.tmx_data.height
        self.width_px = self.map_width_tiles * self.tile_width
        self.height_px = self.map_height_tiles * self.tile_height

        # Debug collision display
        self.show_collisions = False

        # Actual camera position after pyscroll's clamping (set in render())
        self.actual_camera_x = 0
        self.actual_camera_y = 0

        # -----------------------------
        # COLLISIONS (rects from collision_8 layer)
        # -----------------------------

        self.collision_rects = []

        try:
            collision_layer = self.tmx_data.get_layer_by_name("collision_8")

            for x, y, gid in collision_layer:
                if gid != 0:
                    rect = pygame.Rect(
                        x * self.tile_width,
                        y * self.tile_height,
                        self.tile_width,
                        self.tile_height
                    )
                    self.collision_rects.append(rect)

        except ValueError:
            print("⚠ couche collision_8 introuvable")

        # -----------------------------
        # ROAD GRID (for surface detection)
        # -----------------------------

        self._road_grid = [[False] * self.map_width_tiles for _ in range(self.map_height_tiles)]

        for layer in self.tmx_data.layers:
            if not isinstance(layer, pytmx.TiledTileLayer):
                continue
            if 'roads_base' not in layer.name.lower():
                continue
            for y in range(self.map_height_tiles):
                for x in range(self.map_width_tiles):
                    try:
                        gid = layer.data[y][x]
                    except (IndexError, TypeError):
                        continue
                    if gid and gid > 0:
                        self._road_grid[y][x] = True

    # -----------------------------
    # RENDU
    # -----------------------------

    def draw(self, screen, camera_pos):
        """Dessine la carte"""
        self.render(screen, camera_pos[0], camera_pos[1])

    def set_zoom(self, zoom):
        """Change le zoom de la carte."""
        self.zoom = zoom
        vw = max(1, int(self._screen_size[0] / self.zoom))
        vh = max(1, int(self._screen_size[1] / self.zoom))
        self.map_layer = pyscroll.BufferedRenderer(
            self.map_data,
            (vw, vh)
        )
        self._viewport = pygame.Surface((vw, vh))

    def render(self, screen, focus_x, focus_y):
        """
        Render the map centred on the world point (focus_x, focus_y).

        The focus point is the world-space coordinate to centre the view on
        (typically the player centre).  pyscroll handles border clamping
        internally.  After this call, actual_camera_x/y hold the true
        top-left world coordinate of the rendered viewport — this is the
        SINGLE SOURCE OF TRUTH for the camera and must be used by all
        sprite / overlay rendering.
        """
        # Let pyscroll centre + clamp
        self.map_layer.center((round(focus_x), round(focus_y)))

        # Read back the ground-truth camera after clamping
        self.actual_camera_x = self.map_layer.view_rect.left
        self.actual_camera_y = self.map_layer.view_rect.top

        try:
            self.map_layer.draw(self._viewport, self._viewport.get_rect())
        except TypeError:
            self.map_layer.draw(self._viewport)

        # Draw collisions on the viewport BEFORE scaling so they are
        # pixel-perfect with the map tiles (both get scaled together).
        if self.show_collisions:
            self._draw_collisions_viewport(self.actual_camera_x, self.actual_camera_y)

        # Scale 1:1 viewport up to the full screen
        pygame.transform.scale(self._viewport, (screen.get_width(), screen.get_height()), screen)

    # -----------------------------
    # COLLISION CHECK
    # -----------------------------

    def check_collision(self, rect):
        """
        Vérifie si un rectangle entre en collision
        avec la carte. Retourne True/False.
        """
        for collision in self.collision_rects:
            if rect.colliderect(collision):
                return True
        return False

    def check_rect_collision(self, rect):
        """
        Vérifie si un pygame.Rect touche des obstacles de la carte.
        Retourne la liste des Rect de tuiles en collision.
        """
        collisions = []
        for collision in self.collision_rects:
            if rect.colliderect(collision):
                collisions.append(collision)
        return collisions

    def is_collision_at(self, world_x, world_y):
        """Vérifie si la position monde (x,y) est dans un obstacle."""
        for collision in self.collision_rects:
            if collision.collidepoint(world_x, world_y):
                return True
        return False

    # -----------------------------
    # SURFACE DETECTION
    # -----------------------------

    def is_road_at(self, world_x, world_y):
        """Vérifie si la position est sur une route."""
        tx = int(world_x / self.tile_width)
        ty = int(world_y / self.tile_height)
        if 0 <= tx < self.map_width_tiles and 0 <= ty < self.map_height_tiles:
            return self._road_grid[ty][tx]
        return False

    def get_surface_type(self, world_x, world_y):
        """Retourne le type de surface : 'road' ou 'offroad'."""
        return 'road' if self.is_road_at(world_x, world_y) else 'offroad'

    # -----------------------------
    # DEBUG COLLISION
    # -----------------------------

    def _draw_collisions_viewport(self, camera_x, camera_y):
        """
        Draw collision rects on the 1:1 viewport surface so they scale
        together with the map tiles — guarantees pixel-perfect alignment.
        """
        vw = self._viewport.get_width()
        vh = self._viewport.get_height()
        for rect in self.collision_rects:
            dx = rect.x - camera_x
            dy = rect.y - camera_y
            # Skip rects entirely off-viewport
            if dx + rect.width < 0 or dy + rect.height < 0 or dx >= vw or dy >= vh:
                continue
            debug_rect = pygame.Rect(dx, dy, rect.width, rect.height)
            pygame.draw.rect(self._viewport, (255, 0, 0), debug_rect, 1)

    def find_safe_spawn(self, x, y):
        """Return (x, y) moved to the nearest position outside collision rects.

        Checks outward in a spiral from the requested position until a
        collision-free spot is found (max ~50 tile widths away).
        """
        hitbox_size = max(2, int(PLAYER_SIZE * HITBOX_SCALE))
        offset = (PLAYER_SIZE - hitbox_size) / 2

        def _collides(px, py):
            r = pygame.Rect(int(px + offset), int(py + offset), hitbox_size, hitbox_size)
            for c in self.collision_rects:
                if r.colliderect(c):
                    return True
            return False

        if not _collides(x, y):
            return x, y

        step = self.tile_width
        for radius in range(1, 50):
            for dx in range(-radius, radius + 1):
                for dy in range(-radius, radius + 1):
                    if abs(dx) != radius and abs(dy) != radius:
                        continue
                    nx = x + dx * step
                    ny = y + dy * step
                    if 0 <= nx <= self.width_px - PLAYER_SIZE and 0 <= ny <= self.height_px - PLAYER_SIZE:
                        if not _collides(nx, ny):
                            return nx, ny
        return x, y  # fallback

