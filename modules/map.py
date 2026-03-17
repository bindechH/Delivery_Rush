"""
Module de gestion de la carte pour Delivery Rush
Utilise PyTMX et PyScroll pour charger et afficher des cartes Tiled (.tmx)
Gère le rendu, le scrolling et les collisions de la carte.
"""

import pygame
import pytmx
import pyscroll


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

        # Renderer optimisé
        self.map_layer = pyscroll.BufferedRenderer(
            self.map_data,
            screen_size
        )

        # Zoom
        self.zoom = zoom
        self.map_layer.zoom = self.zoom

        # Dimensions
        self.tile_width = self.tmx_data.tilewidth
        self.tile_height = self.tmx_data.tileheight
        self.map_width_tiles = self.tmx_data.width
        self.map_height_tiles = self.tmx_data.height
        self.width_px = self.map_width_tiles * self.tile_width
        self.height_px = self.map_height_tiles * self.tile_height

        # Debug collision display
        self.show_collisions = False

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
        self.map_layer.zoom = self.zoom

    def render(self, screen, camera_x, camera_y):
        """
        Affiche la carte centrée sur (camera_x, camera_y)
        """

        center_x = camera_x + screen.get_width() / (2.0 * self.zoom)
        center_y = camera_y + screen.get_height() / (2.0 * self.zoom)

        self.map_layer.center((center_x, center_y))

        try:
            self.map_layer.draw(screen, screen.get_rect())
        except TypeError:
            self.map_layer.draw(screen)

        # Debug: afficher les collisions si activé
        if self.show_collisions:
            self.draw_collisions(screen, camera_x, camera_y)

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

    def draw_collisions(self, screen, camera_x, camera_y):
        """
        Affiche les rectangles de collision en rouge (debug)
        """
        for rect in self.collision_rects:

            debug_rect = pygame.Rect(
                int((rect.x - camera_x) * self.zoom),
                int((rect.y - camera_y) * self.zoom),
                int(rect.width * self.zoom),
                int(rect.height * self.zoom)
            )

            pygame.draw.rect(screen, (255, 0, 0), debug_rect, 2)

