"""
Module de gestion des sons et musique pour Delivery Rush
Gère la musique de fond et les effets sonores avec contrôle du volume.
"""

import pygame


class SoundManager:
    """
    Gestionnaire de sons et musique pour le jeu
    Permet de jouer de la musique de fond et des effets sonores avec contrôle du volume
    """

    def __init__(self, debug: bool = False):
        """
        Initialisation du gestionnaire de sons
        debug: si True, affiche des messages de debug détaillés
        """
        if not pygame.mixer.get_init():
            pygame.mixer.init()  # Initialiser le mixer Pygame si nécessaire
        self.current_music = None  # Chemin de la musique actuellement jouée
        self.debug = debug

    def play_music(self, path=None, loops=-1, volume=1.0):
        """
        Joue une musique de fond
        path: chemin du fichier audio (None pour changer seulement le volume)
        loops: nombre de répétitions (-1 = boucle infinie)
        volume: volume de 0.0 à 1.0 (ou 0-100 en pourcentage)
        """
        volume = self._normalize_volume(volume)

        # Gestion du changement de volume sans changer de musique
        if not path:
            if self.current_music:
                try:
                    pygame.mixer.music.set_volume(volume)
                    self._log(f"play_music: volume-only set to {volume} for '{self.current_music}'")
                except Exception as exc:
                    print(f"[SON] Impossible de régler le volume sans chemin : {exc}")
            return

        # Éviter de recharger la même musique
        if self.current_music == path:
            try:
                pygame.mixer.music.set_volume(volume)
                self._log(f"play_music: same track '{path}', set volume={volume}")
            except Exception as exc:
                print(f"[SON] Impossible de régler le volume sur la même piste : {exc}")
            return

        try:
            pygame.mixer.music.load(path)
            pygame.mixer.music.set_volume(volume)
            self._log(f"play_music: loaded '{path}', set volume={volume}")
            pygame.mixer.music.play(loops)
            self.current_music = path
        except Exception as exc:
            print(f"[SON] Impossible de jouer la musique {path} : {exc}")

    def stop_music(self):
        """Arrête la musique en cours"""
        try:
            pygame.mixer.music.stop()
        finally:
            self.current_music = None

    def set_music_volume(self, volume: float):
        """Set music volume (0.0-1.0). Accepts 0-100 as percent too."""
        try:
            volume = self._normalize_volume(volume)
        except Exception:
            return False
        try:
            pygame.mixer.music.set_volume(volume)
            self._log(f"set_music_volume: set volume={volume}")
            return True
        except Exception as exc:
            print(f"[SON] Impossible de régler le volume de la musique : {exc}")
            return False

    def _normalize_volume(self, volume: float) -> float:
        # Ajuster le volume s'il est donné en pourcentage
        if isinstance(volume, (int, float)) and volume > 1:
            volume = max(0.0, min(100.0, float(volume))) / 100.0
        volume = max(0.0, min(1.0, float(volume)))
        return float(volume)

    def play_sound(self, path, volume=1.0):
        if not path:
            return
        try:
            snd = pygame.mixer.Sound(path)
            snd.set_volume(self._normalize_volume(volume))
            snd.play()
        except Exception as exc:
            print(f"[SON] Impossible de jouer le son {path} : {exc}")

    def _log(self, msg: str):
        if self.debug:
            print(f"[SOUND] {msg}")