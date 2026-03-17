"""
Module système de missions pour Delivery Rush
Gère la génération, le suivi et la validation des missions de livraison.
Supporte 3 types de missions : standard, express, chaîne.
"""

import math
import random

# === LIEUX DE MISSION SUR LA CARTE ===
# Points d'intérêt pour les ramassages et livraisons
MISSION_LOCATIONS = [

    # Zone universitaire / culturelle (gauche)
    {"name": "Bibliothèque", "x": 750, "y": 1050},
    {"name": "École de cinéma", "x": 980, "y": 1320},
    {"name": "Campus Epita", "x": 1350, "y": 1320},
    {"name": "Université", "x": 1670, "y": 1050},

    # Zone restaurants / commerces
    {"name": "Restaurant italien", "x": 2340, "y": 1050},
    {"name": "Restaurant chinois", "x": 2430, "y": 850},
    {"name": "Épicerie", "x": 2790, "y": 850},
    {"name": "Pharmacie", "x": 2190, "y": 850},

    # Zone centre-ville
    {"name": "Centre commercial", "x": 2610, "y": 1320},
    {"name": "Agence de voyage", "x": 2660, "y": 1610},
    {"name": "Commissariat de police", "x": 2850, "y": 1830},
    {"name": "News Industry", "x": 2860, "y": 2030},
    {"name": "Tribunal", "x": 3310, "y": 2030},
    {"name": "Laboratoire", "x": 3270, "y": 1830},
    {"name": "Musée", "x": 3590, "y": 1810},
    {"name": "Fast food", "x": 3730, "y": 1810},

    # Zone santé
    {"name": "Hôpital 1", "x": 4640, "y": 1800},
    {"name": "Hôpital 2", "x": 2560, "y": 2500},
    {"name": "Hôtel", "x": 2140, "y": 2270},

    # Zone entreprises
    {"name": "Siège Vision Industry", "x": 2190, "y": 1850},
    {"name": "Siège Corp Industry", "x": 3610, "y": 2360},

    # Zone banques / affaires
    {"name": "Banque 1", "x": 4170, "y": 3420},
    {"name": "Banque 2", "x": 3330, "y": 2500},
    {"name": "Quartier d'affaires 1", "x": 4030, "y": 2360},
    {"name": "Quartier d'affaires 2", "x": 4360, "y": 2720},
    {"name": "Quartier d'affaires 3", "x": 4120, "y": 3070},

    # Zone loisirs
    {"name": "Stade", "x": 4880, "y": 310},
    {"name": "Parc", "x": 4880, "y": 1310},

    # Zone résidentielle
    {"name": "Quartier résidentiel 1", "x": 4630, "y": 610},
    {"name": "Quartier résidentiel 2", "x": 4750, "y": 280},
    {"name": "Quartier résidentiel 3", "x": 4740, "y": 120},
    {"name": "Quartier résidentiel 4", "x": 4270, "y": 610},
    {"name": "Quartier résidentiel 5", "x": 4070, "y": 460},
    {"name": "Quartier résidentiel 6", "x": 3580, "y": 220},

    # Zone logistique / livraison
    {"name": "Siège Delivery Rush", "x": 3970, "y": 4120},
    {"name": "Delivery Dispatch", "x": 4720, "y": 3790},
    {"name": "Delivery Rush Logistics", "x": 4110, "y": 4460},
    {"name": "Entrepôt Delivery Rush", "x": 3300, "y": 4630},
]


# === CONSTANTES ===
PICKUP_RADIUS = 150.0       # Rayon de ramassage en pixels (~5m)
DELIVERY_RADIUS = 150.0     # Rayon de livraison en pixels
MAX_AVAILABLE_MISSIONS = 5  # Nombre max de missions disponibles
MISSION_REGEN_TIME = 30.0   # Temps entre régénérations (s)

# Récompenses par type (min, max)
REWARD_STANDARD = (100, 250)
REWARD_EXPRESS = (200, 500)
REWARD_CHAIN = (150, 350)

# Temps limites par type (secondes)
TIME_STANDARD = (120, 240)  # 2-4 min
TIME_EXPRESS = (45, 90)     # 45s-1.5min
TIME_CHAIN = (90, 150)      # 1.5-2.5min


class Mission:
    """Représente une mission de livraison unique."""

    def __init__(self, mission_id, mission_type, pickup, delivery, reward, time_limit):
        self.id = mission_id
        self.type = mission_type  # 'standard', 'express', 'chain'
        self.pickup = pickup      # {"name": str, "x": float, "y": float}
        self.delivery = delivery  # {"name": str, "x": float, "y": float}
        self.reward = reward
        self.time_limit = time_limit
        self.time_remaining = time_limit
        self.status = 'available'  # available, accepted, picked_up, completed, failed
        self.picked_up = False

    def to_dict(self):
        """Sérialise pour le réseau."""
        return {
            'id': self.id,
            'type': self.type,
            'pickup': self.pickup,
            'delivery': self.delivery,
            'reward': self.reward,
            'time_limit': self.time_limit,
            'time_remaining': self.time_remaining,
            'status': self.status,
            'picked_up': self.picked_up,
        }

    @staticmethod
    def from_dict(data):
        """Désérialise depuis les données réseau."""
        m = Mission(
            data['id'], data['type'],
            data['pickup'], data['delivery'],
            data['reward'], data['time_limit']
        )
        m.time_remaining = data.get('time_remaining', data['time_limit'])
        m.status = data.get('status', 'available')
        m.picked_up = data.get('picked_up', False)
        return m

    def description(self):
        """Description courte."""
        labels = {'standard': 'Standard', 'express': 'Express', 'chain': 'Chaîne'}
        return f"[{labels.get(self.type, self.type)}] {self.pickup['name']} -> {self.delivery['name']} | {self.reward}$ | {int(self.time_remaining)}s"


class MissionSystem:
    """
    Système de gestion des missions de livraison.
    Génère, suit et valide les missions.
    """

    def __init__(self, money=0, owned_cars=None, completed_count=0, failed_count=0):
        self.available_missions = []
        self.active_mission = None
        self.money = money
        self.completed_count = completed_count
        self.failed_count = failed_count
        self.owned_cars = owned_cars if owned_cars is not None else [{"model": "MICRO", "color": "White"}]
        self._mission_id_counter = 0
        self._regen_timer = 0.0
        self._last_notification = ""
        self._notification_timer = 0.0
        # Générer les premières missions
        self.generate_missions(MAX_AVAILABLE_MISSIONS)

    def _next_id(self):
        self._mission_id_counter += 1
        return self._mission_id_counter

    def generate_missions(self, count=1):
        """Génère de nouvelles missions disponibles."""
        for _ in range(count):
            if len(self.available_missions) >= MAX_AVAILABLE_MISSIONS:
                break

            mission_type = random.choices(
                ['standard', 'express', 'chain'],
                weights=[60, 25, 15], k=1
            )[0]

            locations = random.sample(MISSION_LOCATIONS, 2)
            pickup = dict(locations[0])
            delivery = dict(locations[1])

            dist = math.hypot(delivery['x'] - pickup['x'], delivery['y'] - pickup['y'])
            dist_factor = max(0.5, dist / 4000.0)

            if mission_type == 'standard':
                reward = int(random.uniform(*REWARD_STANDARD) * dist_factor)
                time_limit = random.uniform(*TIME_STANDARD) * max(0.7, dist_factor)
            elif mission_type == 'express':
                reward = int(random.uniform(*REWARD_EXPRESS) * dist_factor)
                time_limit = random.uniform(*TIME_EXPRESS) * max(0.7, dist_factor)
            else:
                reward = int(random.uniform(*REWARD_CHAIN) * dist_factor)
                time_limit = random.uniform(*TIME_CHAIN) * max(0.7, dist_factor)

            mission = Mission(self._next_id(), mission_type, pickup, delivery, reward, time_limit)
            self.available_missions.append(mission)

    def accept_mission(self, mission_id):
        """Accepte une mission. Retourne (succès, message)."""
        if self.active_mission is not None:
            return False, "Mission en cours"
        for i, m in enumerate(self.available_missions):
            if m.id == mission_id:
                self.active_mission = self.available_missions.pop(i)
                self.active_mission.status = 'accepted'
                self._set_notification(f"Mission acceptée ! Allez à {self.active_mission.pickup['name']}")
                return True, "OK"
        return False, "Mission non trouvée"

    def abandon_mission(self):
        """Abandonne la mission en cours."""
        if self.active_mission is None:
            return False
        self.active_mission = None
        self._set_notification("Mission abandonnée")
        return True

    def update(self, player_x, player_y, dt):
        """Met à jour le système : timer, proximité, régénération."""
        # Régénération
        self._regen_timer += dt
        if self._regen_timer >= MISSION_REGEN_TIME:
            self._regen_timer = 0.0
            if len(self.available_missions) < MAX_AVAILABLE_MISSIONS:
                self.generate_missions(1)

        # Timer notification
        if self._notification_timer > 0:
            self._notification_timer -= dt

        if self.active_mission is None:
            return

        mission = self.active_mission

        # Countdown
        if mission.status in ('accepted', 'picked_up'):
            mission.time_remaining -= dt
            if mission.time_remaining <= 0:
                mission.status = 'failed'
                self.failed_count += 1
                self._set_notification("Mission échouée ! Temps écoulé.")
                self.active_mission = None
                return

        # Proximité ramassage
        if mission.status == 'accepted' and not mission.picked_up:
            dist = math.hypot(player_x - mission.pickup['x'], player_y - mission.pickup['y'])
            if dist <= PICKUP_RADIUS:
                mission.picked_up = True
                mission.status = 'picked_up'
                self._set_notification(f"Colis récupéré ! Livrez à {mission.delivery['name']}")

        # Proximité livraison
        if mission.status == 'picked_up':
            dist = math.hypot(player_x - mission.delivery['x'], player_y - mission.delivery['y'])
            if dist <= DELIVERY_RADIUS:
                mission.status = 'completed'
                self.money += mission.reward
                self.completed_count += 1
                self._set_notification(f"Livraison réussie ! +{mission.reward}$")
                self.active_mission = None

    def _set_notification(self, text, duration=4.0):
        self._last_notification = text
        self._notification_timer = duration

    def get_notification(self):
        return self._last_notification if self._notification_timer > 0 else ""

    def get_objective_position(self):
        """Retourne (x, y) de l'objectif actuel ou None."""
        if self.active_mission is None:
            return None
        if self.active_mission.status == 'accepted':
            return (self.active_mission.pickup['x'], self.active_mission.pickup['y'])
        elif self.active_mission.status == 'picked_up':
            return (self.active_mission.delivery['x'], self.active_mission.delivery['y'])
        return None

    def get_objective_label(self):
        """Retourne le label de l'objectif actuel."""
        if self.active_mission is None:
            return ""
        if self.active_mission.status == 'accepted':
            return f"Ramassage: {self.active_mission.pickup['name']}"
        elif self.active_mission.status == 'picked_up':
            return f"Livraison: {self.active_mission.delivery['name']}"
        return ""

    def to_dict(self):
        """Sérialise pour le réseau."""
        return {
            'available': [m.to_dict() for m in self.available_missions],
            'active': self.active_mission.to_dict() if self.active_mission else None,
            'money': self.money,
            'completed': self.completed_count,
            'failed': self.failed_count,
            'owned_cars': self.owned_cars,
        }

    def has_car(self, model, color=None):
        """Vérifie si le joueur possède un véhicule."""
        for car in self.owned_cars:
            if car["model"] == model:
                if color is None or car.get("color") == color:
                    return True
        return False

    def buy_car(self, model, color, price):
        """Achète un véhicule si le joueur a assez d'argent. Retourne (succès, message)."""
        if self.has_car(model, color):
            return False, "Véhicule déjà possédé"
        if self.money < price:
            return False, "Pas assez d'argent"
        self.money -= price
        self.owned_cars.append({"model": model, "color": color})
        self._set_notification(f"{model} {color} acheté !")
        return True, "OK"