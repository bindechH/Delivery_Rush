"""
Module de gestion des sons et musique pour Delivery Rush.
Gere la musique de fond et les effets sonores avec controle du volume.
"""

from pathlib import Path
import pygame


DRIFT_LOOP_GAIN = 0.26


class SoundManager:
    """
    Gestionnaire de sons et musique pour le jeu.
    Permet de jouer de la musique de fond et des effets sonores avec controle du volume.
    """

    def __init__(self, debug: bool = False):
        """
        Initialisation du gestionnaire de sons.
        debug: si True, affiche des messages de debug detailles.
        """
        self.debug = debug
        self.audio_available = True
        if not pygame.mixer.get_init():
            try:
                pygame.mixer.init()
            except Exception as exc:
                self.audio_available = False
                print(f"[SON] Mixer indisponible, audio desactive : {exc}")

        if self.audio_available:
            try:
                pygame.mixer.set_num_channels(24)
            except Exception:
                pass

        self.current_music = None
        self.sound_cache = {}
        self.current_music_state = "menu"
        self.music_state_gain = 1.0
        self.bus_volumes = {
            "master": 1.0,
            "music": 1.0,
            "ui": 1.0,
            "sfx": 1.0,
            "engine": 1.0,
            "ambience": 1.0,
        }

        self.event_registry = {}
        self._engine_loop_sound = None
        self._engine_channel = None
        self._drift_sound = None
        self._drift_channel = None
        self._ambience_sound = None
        self._ambience_channel = None
        self._ambience_path = None
        self._ambience_gain = 1.0
        self.other_engines = {}

        self.register_ui_sounds()

    def play_music(self, path=None, loops=-1, volume=1.0):
        """
        Joue une musique de fond.
        path: chemin du fichier audio (None pour changer seulement le volume)
        loops: nombre de repetitions (-1 = boucle infinie)
        volume: volume de 0.0 a 1.0 (ou 0-100 en pourcentage)
        """
        if not self.audio_available:
            return

        volume = self._normalize_volume(volume)

        # Changement de volume sans changer de piste.
        if not path:
            if self.current_music:
                try:
                    pygame.mixer.music.set_volume(self._effective_volume("music", volume * self.music_state_gain))
                    self._log(f"play_music: volume-only set to {volume} for '{self.current_music}'")
                except Exception as exc:
                    print(f"[SON] Impossible de regler le volume sans chemin : {exc}")
            return

        track_path = str(path)
        if not Path(track_path).exists():
            self._log(f"play_music: missing file '{track_path}', skip")
            return

        # Eviter de recharger la meme musique.
        if self.current_music == track_path:
            try:
                pygame.mixer.music.set_volume(self._effective_volume("music", volume * self.music_state_gain))
                if not pygame.mixer.music.get_busy():
                    pygame.mixer.music.play(loops)
                self._log(f"play_music: same track '{track_path}', set volume={volume}")
            except Exception as exc:
                print(f"[SON] Impossible de regler le volume sur la meme piste : {exc}")
            return

        try:
            pygame.mixer.music.load(track_path)
            pygame.mixer.music.set_volume(self._effective_volume("music", volume * self.music_state_gain))
            pygame.mixer.music.play(loops)
            self.current_music = track_path
            self._log(f"play_music: loaded '{track_path}', set volume={volume}")
        except Exception as exc:
            print(f"[SON] Impossible de jouer la musique {track_path} : {exc}")

    def stop_music(self):
        """Arrete la musique en cours."""
        if not self.audio_available:
            self.current_music = None
            return

        try:
            pygame.mixer.music.stop()
        finally:
            self.current_music = None

    def set_music_volume(self, volume: float):
        """Set music volume (0.0-1.0). Accepts 0-100 as percent too."""
        if not self.audio_available:
            return False

        try:
            volume = self._normalize_volume(volume)
        except Exception:
            return False

        try:
            self.bus_volumes["music"] = volume
            pygame.mixer.music.set_volume(self._effective_volume("music", self.music_state_gain))
            self._log(f"set_music_volume: set volume={volume}")
            return True
        except Exception as exc:
            print(f"[SON] Impossible de regler le volume de la musique : {exc}")
            return False

    def set_effects_volume(self, volume: float) -> bool:
        """Set UI/SFX/engine/ambience volumes together with one slider."""
        if not self.audio_available:
            return False

        try:
            vol = self._normalize_volume(volume)
        except Exception:
            return False

        self.bus_volumes["ui"] = vol
        self.bus_volumes["sfx"] = vol
        self.bus_volumes["engine"] = vol
        self.bus_volumes["ambience"] = vol

        try:
            if self._engine_channel is not None:
                self._engine_channel.set_volume(self._effective_volume("engine", 1.0))
            if self._drift_channel is not None:
                self._drift_channel.set_volume(self._effective_volume("sfx", DRIFT_LOOP_GAIN))
            if self._ambience_channel is not None:
                self._ambience_channel.set_volume(self._effective_volume("ambience", self._ambience_gain))
            return True
        except Exception:
            return False

    def get_music_volume(self) -> float:
        return float(self.bus_volumes.get("music", 1.0))

    def get_effects_volume(self) -> float:
        return float(self.bus_volumes.get("sfx", 1.0))

    def _normalize_volume(self, volume: float) -> float:
        # Ajuster le volume s'il est donne en pourcentage.
        if isinstance(volume, (int, float)) and volume > 1:
            volume = max(0.0, min(100.0, float(volume))) / 100.0
        volume = max(0.0, min(1.0, float(volume)))
        return float(volume)

    def play_sound(self, path, volume=1.0, bus="sfx"):
        if not self.audio_available:
            return
        if not path:
            return

        try:
            snd = self._load_sound(path)
            snd.set_volume(self._effective_volume(bus, self._normalize_volume(volume)))
            snd.play()
        except Exception as exc:
            print(f"[SON] Impossible de jouer le son {path} : {exc}")

    def set_bus_volume(self, bus_name: str, volume: float) -> bool:
        if not self.audio_available:
            return False

        bus = str(bus_name or "").lower()
        if bus not in self.bus_volumes:
            return False

        self.bus_volumes[bus] = self._normalize_volume(volume)
        if bus == "music" and self.current_music:
            try:
                pygame.mixer.music.set_volume(self._effective_volume("music", self.music_state_gain))
            except Exception:
                return False
        return True

    def register_ui_sounds(self):
        """Declare les evenements audio UI/gameplay et leurs fichiers."""

        def pick(*candidates):
            for candidate in candidates:
                if candidate and Path(candidate).exists():
                    return candidate
            return None

        self.event_registry = {
            "ui_open": pick("assets/sounds/ui_open.mp3", "assets/sounds/ui_open.ogg", "assets/sounds/ui_open.wav"),
            "ui_back": pick("assets/sounds/ui_back.mp3", "assets/sounds/ui_back.ogg", "assets/sounds/ui_back.wav"),
            "ui_move": pick("assets/sounds/ui_back.mp3", "assets/sounds/ui_open.mp3"),
            "shop_buy": pick("assets/sounds/shop_buy.mp3", "assets/sounds/shop_buy.ogg", "assets/sounds/shop_buy.wav"),
            "shop_denied": pick("assets/sounds/shop_denied.mp3", "assets/sounds/shop_denied.ogg", "assets/sounds/shop_denied.wav"),
            "garage_equip": pick("assets/sounds/garage_equip.mp3", "assets/sounds/garage_equip.ogg", "assets/sounds/garage_equip.wav", "assets/sounds/ui_open.mp3"),
            "mission_accept": pick("assets/sounds/mission_accept.mp3", "assets/sounds/mission_accept.ogg", "assets/sounds/mission_accept.wav"),
            "mission_pickup": pick("assets/sounds/mission_pickup.mp3", "assets/sounds/mission_pickup.ogg", "assets/sounds/mission_pickup.wav"),
            "mission_step": pick("assets/sounds/mission_pickup.mp3", "assets/sounds/mission_accept.mp3"),
            "mission_complete": pick("assets/sounds/mission_complete.mp3", "assets/sounds/mission_complete.ogg", "assets/sounds/mission_complete.wav"),
            "mission_fail": pick("assets/sounds/mission_fail.mp3", "assets/sounds/mission_fail.ogg", "assets/sounds/mission_fail.wav"),
            "mission_denied": pick("assets/sounds/shop_denied.mp3", "assets/sounds/mission_fail.mp3"),
            "collision_light": pick("assets/sounds/collision_light.mp3", "assets/sounds/collision_light.ogg", "assets/sounds/collision_light.wav"),
            "collision_heavy": pick("assets/sounds/collision_heavy.mp3", "assets/sounds/collision_heavy.ogg", "assets/sounds/collision_heavy.wav"),
            "drift_start": pick("assets/sounds/drift.mp3", "assets/sounds/drift.ogg", "assets/sounds/drift.wav"),
            "drift_stop": pick("assets/sounds/drift.mp3", "assets/sounds/drift.ogg", "assets/sounds/drift.wav"),
            "brake": pick("assets/sounds/collision_light.mp3", "assets/sounds/ui_back.mp3"),
            "engine_loop": pick("assets/sounds/engine_loop.mp3", "assets/sounds/engine_loop.ogg", "assets/sounds/engine_loop.wav"),
        }

    def play_event(self, event_name: str, volume: float = 1.0):
        """Joue un evenement audio standardise (UI, mission, collision, etc.)."""
        if not self.audio_available:
            return

        name = str(event_name or "").lower()
        path = self.event_registry.get(name)
        if not path:
            self._log(f"play_event: no file mapped for '{name}'")
            return

        bus = "ui" if name.startswith("ui_") or name.startswith("shop_") or name.startswith("garage_") else "sfx"
        self.play_sound(path, volume=volume, bus=bus)

    def set_music_state(self, state: str):
        """Ajuste dynamiquement le niveau musical selon l'intensite de gameplay."""
        if not self.audio_available:
            return

        state_key = str(state or "menu").lower()
        gains = {
            "menu": 1.0,
            "gameplay": 0.82,
            "high_intensity": 0.7,
            "mission": 0.86,
        }
        self.current_music_state = state_key
        self.music_state_gain = gains.get(state_key, 1.0)
        if self.current_music:
            try:
                pygame.mixer.music.set_volume(self._effective_volume("music", self.music_state_gain))
            except Exception:
                pass

    def start_city_ambience(self, path: str, gain: float = 1.0):
        """Starts a persistent city ambience loop on a dedicated channel."""
        if not self.audio_available:
            return
        if not path:
            return

        ambience_path = str(path)
        if not Path(ambience_path).exists():
            self._log(f"start_city_ambience: missing file '{ambience_path}', skip")
            return

        self._ambience_gain = self._normalize_volume(gain)
        if self._ambience_channel and self._ambience_channel.get_busy() and self._ambience_path == ambience_path:
            try:
                self._ambience_channel.set_volume(self._effective_volume("ambience", self._ambience_gain))
            except Exception:
                pass
            return

        try:
            if self._ambience_channel:
                self._ambience_channel.stop()
            self._ambience_sound = self._load_sound(ambience_path)
            self._ambience_channel = pygame.mixer.Channel(3)
            self._ambience_channel.play(self._ambience_sound, loops=-1)
            self._ambience_channel.set_volume(self._effective_volume("ambience", self._ambience_gain))
            self._ambience_path = ambience_path
        except Exception:
            self._ambience_sound = None
            self._ambience_channel = None
            self._ambience_path = None

    def stop_city_ambience(self):
        if not self.audio_available:
            return

        if self._ambience_channel:
            try:
                self._ambience_channel.stop()
            except Exception:
                pass
        self._ambience_channel = None
        self._ambience_sound = None
        self._ambience_path = None

    def duck_music(self, amount: float = 0.5):
        """Reduit temporairement la musique (0.0 a 1.0, plus petit = plus fort duck)."""
        if not self.audio_available:
            return

        factor = self._normalize_volume(amount)
        if self.current_music:
            try:
                pygame.mixer.music.set_volume(self._effective_volume("music", self.music_state_gain * factor))
            except Exception:
                pass

    def play_collision(self, intensity: float = 0.5):
        normalized = max(0.0, min(1.0, float(intensity)))
        event_name = "collision_heavy" if normalized >= 0.65 else "collision_light"
        hit_volume = 0.7 + normalized * 0.3
        self.play_event(event_name, volume=hit_volume)

    def play_drift_start(self):
        if not self.audio_available:
            return
        path = self.event_registry.get("drift_start")
        if not path:
            return
        try:
            if self._drift_sound is None:
                self._drift_sound = self._load_sound(path)
            if self._drift_channel is None:
                self._drift_channel = pygame.mixer.Channel(4)
            if not self._drift_channel.get_busy():
                self._drift_channel.play(self._drift_sound, loops=-1)
            self._drift_channel.set_volume(self._effective_volume("sfx", DRIFT_LOOP_GAIN))
        except Exception as exc:
            self._log(f"play_drift_start failed: {exc}")

    def play_drift_stop(self):
        if not self.audio_available:
            return
        if self._drift_channel:
            try:
                self._drift_channel.stop()
            except Exception:
                pass

    def play_brake(self):
        self.play_event("brake")

    def update_vehicle_engine(self, player=None, vehicle_profile=None):
        """Met a jour une boucle moteur en fonction de la vitesse si un asset existe."""
        if not self.audio_available:
            return

        loop_path = self.event_registry.get("engine_loop")
        if not loop_path:
            return

        speed = 0.0
        if player is not None:
            speed = float(getattr(player, "speed_kmh", 0.0) or 0.0)
        elif isinstance(vehicle_profile, dict):
            speed = float(vehicle_profile.get("speed_kmh", 0.0) or 0.0)

        # No engine sound while idling.
        if speed <= 2.0:
            if self._engine_channel and self._engine_channel.get_busy():
                try:
                    self._engine_channel.stop()
                except Exception:
                    pass
            return

        if self._engine_loop_sound is None:
            try:
                self._engine_loop_sound = self._load_sound(loop_path)
            except Exception:
                self._engine_loop_sound = None
                return

        if self._engine_channel is None:
            try:
                self._engine_channel = pygame.mixer.Channel(2)
            except Exception:
                self._engine_channel = None
                return

        if not self._engine_channel.get_busy():
            try:
                self._engine_channel.play(self._engine_loop_sound, loops=-1)
            except Exception:
                return

        speed_ratio = max(0.0, min(1.0, speed / 220.0))
        # Raised engine volume
        engine_gain = min(1.0, 0.62 + speed_ratio * 1.45)
        self._engine_channel.set_volume(self._effective_volume("engine", engine_gain))

    def update_other_engines(self, player, other_players):
        """Mise à jour dynamique de la brique de son pour les autres voitures."""
        if not self.audio_available:
            return

        loop_path = self.event_registry.get("engine_loop")
        if not loop_path or not player:
            # Arreter tous les moteurs s'il n'y a pas d'infos
            for username, data in list(self.other_engines.items()):
                try:
                    data["channel"].stop()
                except Exception:
                    pass
                del self.other_engines[username]
            return

        import math
        import time

        current_time = time.time()
        max_hearing_dist = 2500.0
        updated_users = set()

        for username, data in other_players.items():
            if not isinstance(data, dict):
                continue
            
            ox = float(data.get('x', 0.0))
            oy = float(data.get('y', 0.0))
            
            dx = player.x - ox
            dy = player.y - oy
            dist = math.sqrt(dx*dx + dy*dy)

            if dist < max_hearing_dist:
                updated_users.add(username)
                
                volume_ratio = max(0.0, 1.0 - (dist / max_hearing_dist))
                speed = float(data.get('speed_kmh', 0.0) or 0.0)
                if speed <= 2.0:
                    if username in self.other_engines:
                        try:
                            self.other_engines[username]["channel"].stop()
                        except Exception:
                            pass
                        del self.other_engines[username]
                    continue
                speed_ratio = max(0.0, min(1.0, speed / 220.0))
                # Adjusted for multiplayer cars depending on how close they are
                engine_gain = min(1.0, 0.6 + speed_ratio * 1.5) * (volume_ratio ** 2) # **2 makes it drop off faster
                target_vol = self._effective_volume("engine", engine_gain)

                if username not in self.other_engines:
                    try:
                        snd = self._load_sound(loop_path)
                        chan = None
                        for cid in range(5, 24):
                            chk = pygame.mixer.Channel(cid)
                            if not chk.get_busy():
                                chan = chk
                                break
                        if chan is None:
                            chan = pygame.mixer.find_channel(True)
                        
                        if chan:
                            chan.play(snd, loops=-1)
                            chan.set_volume(target_vol)
                            self.other_engines[username] = {
                                "channel": chan,
                                "sound": snd,
                                "last_active": current_time
                            }
                    except Exception as e:
                        if self.debug:
                            print(f"[SoundManager] Error playing other engine for {username}: {e}")
                else:
                    self.other_engines[username]["channel"].set_volume(target_vol)
                    self.other_engines[username]["last_active"] = current_time

        # Arrêt des canaux pour les joueurs trop éloignés ou déconnectés
        for username in list(self.other_engines.keys()):
            if username not in updated_users or current_time - self.other_engines[username]["last_active"] > 1.0:
                try:
                    self.other_engines[username]["channel"].stop()
                except Exception:
                    pass
                del self.other_engines[username]

    def stop_vehicle_engine(self):
        if not self.audio_available:
            return

        if self._engine_channel:
            self._engine_channel.stop()
        self._engine_channel = None
        self._engine_loop_sound = None

        for username, data in list(self.other_engines.items()):
            try:
                data["channel"].stop()
            except Exception:
                pass
            del self.other_engines[username]

    def _load_sound(self, path):
        if not self.audio_available:
            raise RuntimeError("Audio mixer unavailable")

        key = str(path)
        if not Path(key).exists():
            raise FileNotFoundError(key)
        if key not in self.sound_cache:
            self.sound_cache[key] = pygame.mixer.Sound(key)
        return self.sound_cache[key]

    def _effective_volume(self, bus: str, base: float) -> float:
        b = str(bus or "sfx").lower()
        master = self.bus_volumes.get("master", 1.0)
        bus_gain = self.bus_volumes.get(b, 1.0)
        return self._normalize_volume(master * bus_gain * float(base))

    def _log(self, msg: str):
        if self.debug:
            print(f"[SOUND] {msg}")