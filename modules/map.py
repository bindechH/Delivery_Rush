"""
Module de gestion de la carte pour Delivery Rush
Utilise PyTMX et PyScroll pour charger et afficher des cartes Tiled (.tmx)
Gère le rendu, le scrolling et les collisions de la carte.
"""

import pygame
import pytmx
import pyscroll
import heapq


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

        # Debug display modes
        self.show_collisions = False
        self.show_ai_debug = False

        # Actual camera position after pyscroll's clamping (set in render())
        self.actual_camera_x = 0
        self.actual_camera_y = 0

        # -----------------------------
        # COLLISIONS (rects from collision_8 layer)
        # -----------------------------

        self.collision_rects = []
        self._collision_grid = [[False] * self.map_width_tiles for _ in range(self.map_height_tiles)]

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
                    if 0 <= x < self.map_width_tiles and 0 <= y < self.map_height_tiles:
                        self._collision_grid[y][x] = True

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

    def render(self, screen, camera_x, camera_y):
        """
        Affiche la carte centrée sur (camera_x, camera_y)
        Renders at 1:1 to a viewport surface, then scales to screen.
        """
        vw = self._viewport.get_width()
        vh = self._viewport.get_height()

        center_x = int(camera_x + vw / 2)
        center_y = int(camera_y + vh / 2)

        self.map_layer.center((center_x, center_y))

        # Read back pyscroll's actual camera after its internal clamping.
        # This is the ground-truth for what area pyscroll actually rendered.
        self.actual_camera_x = self.map_layer.view_rect.left
        self.actual_camera_y = self.map_layer.view_rect.top

        try:
            self.map_layer.draw(self._viewport, self._viewport.get_rect())
        except TypeError:
            self.map_layer.draw(self._viewport)

        # Scale 1:1 viewport up to the full screen
        pygame.transform.scale(self._viewport, (screen.get_width(), screen.get_height()), screen)

        # Debug: afficher les collisions si activé
        if self.show_collisions:
            self.draw_collisions(screen, self.actual_camera_x, self.actual_camera_y)

    # -----------------------------
    # COLLISION CHECK
    # -----------------------------

    def _rect_tile_bounds(self, rect):
        """Convertit un rect monde en bornes tuiles clamped."""
        if not isinstance(rect, pygame.Rect):
            rect = pygame.Rect(rect)

        if self.map_width_tiles <= 0 or self.map_height_tiles <= 0:
            return 0, -1, 0, -1

        right = max(rect.left, rect.right - 1)
        bottom = max(rect.top, rect.bottom - 1)

        tx0 = max(0, int(rect.left // self.tile_width))
        ty0 = max(0, int(rect.top // self.tile_height))
        tx1 = min(self.map_width_tiles - 1, int(right // self.tile_width))
        ty1 = min(self.map_height_tiles - 1, int(bottom // self.tile_height))
        return tx0, tx1, ty0, ty1

    def check_collision(self, rect):
        """
        Vérifie si un rectangle entre en collision
        avec la carte. Retourne True/False.
        """
        tx0, tx1, ty0, ty1 = self._rect_tile_bounds(rect)
        if tx1 < tx0 or ty1 < ty0:
            return False

        for ty in range(ty0, ty1 + 1):
            row = self._collision_grid[ty]
            for tx in range(tx0, tx1 + 1):
                if row[tx]:
                    return True
        return False

    def check_rect_collision(self, rect):
        """
        Vérifie si un pygame.Rect touche des obstacles de la carte.
        Retourne la liste des Rect de tuiles en collision.
        """
        collisions = []

        tx0, tx1, ty0, ty1 = self._rect_tile_bounds(rect)
        if tx1 < tx0 or ty1 < ty0:
            return collisions

        for ty in range(ty0, ty1 + 1):
            row = self._collision_grid[ty]
            for tx in range(tx0, tx1 + 1):
                if row[tx]:
                    collisions.append(
                        pygame.Rect(
                            tx * self.tile_width,
                            ty * self.tile_height,
                            self.tile_width,
                            self.tile_height,
                        )
                    )
        return collisions

    def is_collision_at(self, world_x, world_y):
        """Vérifie si la position monde (x,y) est dans un obstacle."""
        tx = int(world_x / self.tile_width)
        ty = int(world_y / self.tile_height)
        if 0 <= tx < self.map_width_tiles and 0 <= ty < self.map_height_tiles:
            return self._collision_grid[ty][tx]
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

    def world_to_tile(self, world_x, world_y):
        """Convertit des coordonnées monde vers coordonnées tuiles."""
        return int(world_x // self.tile_width), int(world_y // self.tile_height)

    def tile_to_world(self, tile_x, tile_y):
        """Retourne le centre monde d'une tuile."""
        wx = tile_x * self.tile_width + self.tile_width * 0.5
        wy = tile_y * self.tile_height + self.tile_height * 0.5
        return wx, wy

    def get_road_neighbors(self, tile_x, tile_y):
        """Retourne les voisins routiers (4 directions) d'une tuile."""
        neighbors = []
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = tile_x + dx, tile_y + dy
            if 0 <= nx < self.map_width_tiles and 0 <= ny < self.map_height_tiles and self._road_grid[ny][nx]:
                neighbors.append((nx, ny))
        return neighbors

    def find_road_path(self, start_world, goal_world):
        """Cherche un chemin routier A* entre deux positions monde."""
        start = self.world_to_tile(start_world[0], start_world[1])
        goal = self.world_to_tile(goal_world[0], goal_world[1])

        def nearest_road(tile):
            tx, ty = tile
            if 0 <= tx < self.map_width_tiles and 0 <= ty < self.map_height_tiles and self._road_grid[ty][tx]:
                return tile
            best = None
            best_d = float('inf')
            for y in range(self.map_height_tiles):
                for x in range(self.map_width_tiles):
                    if not self._road_grid[y][x]:
                        continue
                    d = abs(x - tx) + abs(y - ty)
                    if d < best_d:
                        best_d = d
                        best = (x, y)
            return best

        start = nearest_road(start)
        goal = nearest_road(goal)
        if not start or not goal:
            return []

        open_heap = [(0.0, start)]
        came_from = {}
        g_cost = {start: 0.0}

        def heuristic(a, b):
            return abs(a[0] - b[0]) + abs(a[1] - b[1])

        while open_heap:
            _, current = heapq.heappop(open_heap)
            if current == goal:
                path_tiles = [current]
                while current in came_from:
                    current = came_from[current]
                    path_tiles.append(current)
                path_tiles.reverse()
                return [self.tile_to_world(tx, ty) for tx, ty in path_tiles]

            for nxt in self.get_road_neighbors(current[0], current[1]):
                tentative = g_cost[current] + 1.0
                if tentative >= g_cost.get(nxt, float('inf')):
                    continue
                came_from[nxt] = current
                g_cost[nxt] = tentative
                f_cost = tentative + heuristic(nxt, goal)
                heapq.heappush(open_heap, (f_cost, nxt))

        return []

    # -----------------------------
    # DEBUG COLLISION
    # -----------------------------

    def draw_collisions(self, screen, camera_x, camera_y):
        """
        Affiche les rectangles de collision en rouge (debug).
        Only draw rectangles inside the visible viewport to reduce lag.
        """
        screen_w = screen.get_width()
        screen_h = screen.get_height()
        visible_world_rect = pygame.Rect(
            int(camera_x),
            int(camera_y),
            int(screen_w / max(1.0, self.zoom)),
            int(screen_h / max(1.0, self.zoom)),
        )

        for rect in self.collision_rects:
            if not rect.colliderect(visible_world_rect):
                continue

            debug_rect = pygame.Rect(
                int((rect.x - camera_x) * self.zoom),
                int((rect.y - camera_y) * self.zoom),
                int(rect.width * self.zoom),
                int(rect.height * self.zoom)
            )
            pygame.draw.rect(screen, (255, 0, 0), debug_rect, 2)

