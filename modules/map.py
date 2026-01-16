"""
Module de gestion de la carte pour Delivery Rush
Utilise PyTMX et PyScroll pour charger et afficher des cartes Tiled (.tmx)
Gère le rendu, le scrolling et les dimensions de la carte.
"""

import pygame
import pytmx
import pyscroll


class GameMap:
    """
    Gestionnaire de carte Tiled pour le jeu
    Charge et affiche la carte avec scrolling optimisé
    """

    def __init__(self, tmx_file, screen_size):
        """
        Initialisation de la carte
        tmx_file: chemin vers le fichier .tmx de Tiled
        screen_size: dimensions de l'écran (largeur, hauteur)
        """
        self.tmx_data = pytmx.util_pygame.load_pygame(tmx_file)  # Chargement des données TMX
        self.map_data = pyscroll.data.TiledMapData(self.tmx_data)  # Données pour PyScroll
        self.map_layer = pyscroll.BufferedRenderer(  # Renderer optimisé avec buffer
            self.map_data,
            screen_size
        )
        # Calcul des dimensions totales de la carte en pixels
        self.width_px = self.tmx_data.width * self.tmx_data.tilewidth
        self.height_px = self.tmx_data.height * self.tmx_data.tileheight

    def draw(self, screen, camera_pos):
        # Méthode de dessin de la carte centrée sur camera_pos
        self.render(screen, camera_pos[0], camera_pos[1])

    def render(self, screen, camera_x, camera_y):
        """afficher la carte centrée sur (camera_x, camera_y).

        Arguments:
            screen: pygame Surface to draw onto
            camera_x: top-left x coordinate of the camera
            camera_y: top-left y coordinate of the camera
        """
        # pyscroll veut le centre de l'écran
        center_x = camera_x + screen.get_width() // 2
        center_y = camera_y + screen.get_height() // 2
        self.map_layer.center((center_x, center_y))
        # afficher la carte
        try:
            self.map_layer.draw(screen, screen.get_rect())
        except TypeError:
            self.map_layer.draw(screen)


    
