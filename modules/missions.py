"""
Module système de missions pour Delivery Rush.
Gère la génération, le suivi et la validation des missions de livraison.
Supporte 3 types de missions : standard, express, chaîne.
"""

import math
import random
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .translate import normalize_language, tr
from .player import build_vehicle_profile, is_vehicle_color_allowed, sanitize_car

# === LIEUX DE MISSION SUR LA CARTE ===
# Points d'intérêt pour les ramassages et livraisons
MISSION_LOCATIONS = [ 

    # Environ 140 points 

  

    # === FARM ZONE (nord-ouest) === 

    {"name": "Delivery Farm", "x": 5, "y": 62}, 

    {"name": "Farm Storage", "x": 22, "y": 31}, 

    {"name": "Farm Shop", "x": 35, "y": 31}, 

    {"name": "Delivery Hub (Farm)", "x": 49, "y": 31}, 

    {"name": "Farm Zone", "x": 125, "y": 31}, 

  

    # === KARTING CIRCUIT (nord-centre) === 

    {"name": "Karting Circuit", "x": 227, "y": 31}, 

    {"name": "Grandstand 1", "x": 265, "y": 27}, 

    {"name": "Kart Shop", "x": 304, "y": 27}, 

    {"name": "Pit Garage", "x": 317, "y": 27}, 

    {"name": "Pit Area", "x": 331, "y": 27}, 

    {"name": "Drive Safe School", "x": 260, "y": 25}, 

    {"name": "Delivery Kart", "x": 220, "y": 24}, 

  

    # === ZONE RÉSIDENTIELLE NORD === 

    {"name": "Maison résidentielle Nord 1", "x": 190, "y": 61}, 

    {"name": "Maison résidentielle Nord 2", "x": 149, "y": 61}, 

    {"name": "Maison résidentielle Nord 3", "x": 145, "y": 45}, 

    {"name": "Maison résidentielle Nord 4", "x": 192, "y": 45}, 

    {"name": "Maison résidentielle Nord 5", "x": 188, "y": 22}, 

    {"name": "Stade de football", "x": 503, "y": 63}, 

  

    # === ZONE COMMERCIALE / RESTAURANTS (nord-ouest, rue principale) === 

    {"name": "Pharmacy", "x": 7, "y": 86}, 

    {"name": "Aldo", "x": 21, "y": 86}, 

    {"name": "Sushi House", "x": 35, "y": 86}, 

    {"name": "Pizza Shop", "x": 49, "y": 86}, 

    {"name": "Pasta", "x": 7, "y": 106}, 

    {"name": "Pizza (place piétonne)", "x": 68, "y": 82}, 

    {"name": "Slice", "x": 20, "y": 106}, 

    {"name": "Store (épicerie)", "x": 32, "y": 106}, 

    {"name": "Pastaa", "x": 40, "y": 106}, 

    {"name": "RAT Store", "x": 55, "y": 106}, 

  

    # === DELIVERY RUSH MALL === 

    {"name": "Delivery Rush Mall – Retail", "x": 8, "y": 133}, 

    {"name": "Delivery Rush Mall – Shops", "x": 23, "y": 133}, 

    {"name": "Delivery Rush Mall – DR mall", "x": 47, "y": 133}, 

     

  

  

    # === CAMPUS EPITA / ZONE UNIVERSITAIRE === 

    {"name": "EPITA – École d'ingénieurs", "x": 133, "y": 133}, 

    {"name": "EPITA – Science", "x": 153, "y": 133}, 

    {"name": "US", "x": 100, "y": 133}, 

    {"name": "Art", "x": 115, "y": 133}, 

  

    # === ZONE COMMERCIALE CENTRE (Powergrid, Marquee, Travel…) === 

    {"name": "Powergrid", "x": 23, "y": 162}, 

    {"name": "Marquee", "x": 38, "y": 162}, 

    {"name": "Travel Agency", "x": 54, "y": 163}, 

    {"name": "Center", "x": 78, "y": 163}, 

    {"name": "Biz", "x": 108, "y": 164}, 

  

    # === ZONE VISION / REALTY / PHARMA / POLICE === 

    {"name": "Vision", "x": 7, "y": 186}, 

    {"name": "Realty", "x": 36, "y": 186}, 

    {"name": "Pharma", "x": 54, "y": 186}, 

    {"name": "Police", "x": 78, "y": 184}, 

    {"name": "CO", "x": 95, "y": 183}, 

  

    # === ZONE RESTAURATION / SHOPPING (ilot centre) === 

    {"name": "Slice (centre)", "x": 5, "y": 204}, 

    {"name": "Store (centre)", "x": 15, "y": 203}, 

    {"name": "Pastaa (centre)", "x": 22, "y": 203}, 

    {"name": "RAT Store (centre)", "x": 41, "y": 203}, 

    {"name": "Store – Books", "x": 55, "y": 203}, 

  

    # === ZONE MÉDIAS / FORUM / STAR === 

    {"name": "Forum – Latest News", "x": 78, "y": 203}, 

    {"name": "Star", "x": 107, "y": 204}, 

  

    # === ZONE MUSÉE / BURGER / BREE / BANKE === 

    {"name": "Musée", "x": 146, "y": 182}, 

    {"name": "Burger", "x": 160, "y": 182}, 

    {"name": "Bree", "x": 162, "y": 182}, 

    {"name": "Banke", "x": 176, "y": 203}, 

    {"name": "urbain1", "x": 150, "y": 204}, 

    {"name": "School", "x": 178, "y": 182}, 

  

    # === ZONE CORP / FINANCE / TOWER === 

    {"name": "Corp", "x": 148, "y": 238}, 

    {"name": "Finance", "x": 164, "y": 238}, 

    {"name": "Tower", "x": 115, "y": 229}, 

  

    # === HOTEL / ZONE MIXTE === 

    {"name": "Hotel", "x": 388, "y": 159}, 

    {"name": "Immeuble résidentiel Centre 1", "x": 440, "y": 133}, 

    {"name": "Immeuble résidentiel Centre 2", "x": 469, "y": 97}, 

    {"name": "Immeuble résidentiel Centre 3", "x": 404, "y": 134}, 

  

    # === HÔPITAL / CROIX ROUGE === 

    {"name": "Hôpital – Urgences", "x": 465, "y": 181}, 

    {"name": "Hôpital – Clinique", "x": 43, "y": 251}, 

  

    # === ZONE BANQUES / AFFAIRES (est) === 

    {"name": "Bank 1", "x": 371, "y": 274}, 

    {"name": "Bank 2", "x": 333, "y": 251}, 

    {"name": "Bank 3", "x": 323, "y": 229}, 

    {"name": "Corp (est)", "x": 359, "y": 238}, 

    {"name": "Finance (est)", "x": 375, "y": 237}, 

    {"name": "Tour d'affaires Est 1", "x": 422, "y": 273}, 

    {"name": "Tour d'affaires Est 2", "x": 471, "y": 238}, 

  

    # === ZONE RÉSIDENTIELLE MIXTE (appartements) === 

    {"name": "Appartements bleus Nord-Est 1", "x": 475, "y": 273}, 

    {"name": "Appartements bleus Nord-Est 2", "x": 478, "y": 181}, 

    {"name": "Appartements bleus Nord-Est 3", "x": 471, "y": 159}, 

    {"name": "Appartements oranges Est 1", "x": 452, "y": 82}, 

    {"name": "Appartements rouges Est 2", "x": 418, "y": 78}, 

    {"name": "Appartements Est 3", "x": 440, "y": 82}, 

    {"name": "Appartements Est 4", "x": 387, "y": 120}, 

    {"name": "Appartements Est 5", "x": 355, "y": 133}, 

    {"name": "Appartements Est 6", "x": 416, "y": 110}, 

  

    # === ZONE 24H / PIZZA SHOP / STORES (rue nord-est) === 

    {"name": "Pizza Shop 24h", "x": 217, "y": 204}, 

    {"name": "24 Hours Store", "x": 228, "y": 204}, 

    {"name": "Store – Books (nord-est)", "x": 261, "y": 204}, 

     

  

    # === ZONE LOGISTIQUE DELIVERY RUSH (sud) === 

    {"name": "DR – Dépôt Principal", "x": 333, "y": 378}, 

    {"name": "DR – HQ", "x": 358, "y": 379}, 

    {"name": "DR – Entrepôt Sud 1", "x": 408, "y": 483}, 

    {"name": "DR – Entrepôt Sud 2", "x": 425, "y": 446}, 

    {"name": "DR – Entrepôt Sud 3", "x": 371, "y": 446}, 

    {"name": "DR – Entrepôt Sud 4", "x": 474, "y": 446}, 

    {"name": "DR – Delivery", "x": 421, "y": 484}, 

    {"name": "DR – Dispatch", "x": 425, "y": 380}, 

    {"name": "DR – Express", "x": 422, "y": 424}, 

  

    # === DPX / WAREHOUSE (zone logistique est) === 

    {"name": "DPX – Dépôt", "x": 436, "y": 414}, 

    {"name": "DPX – Hub", "x": 255, "y": 414}, 

    {"name": "DPX – Depot", "x": 362, "y": 466}, 

    {"name": "DPX – Warehouse", "x": 459, "y": 414}, 

    {"name": "DPX – DPX", "x": 372, "y": 414}, 

  

    # === AÉROPORT / ZONE DELIVERY RUSH HQ === 

    {"name": "Delivery Rush HQ – Bâtiment 01", "x": 270, "y": 442}, 

    {"name": "Delivery Rush HQ – Bâtiment 02", "x": 449, "y": 446}, 

    {"name": "Delivery Rush HQ – Bâtiment 03", "x": 359, "y": 379}, 

    {"name": "Delivery Rush HQ – Bâtiment 04", "x": 219, "y": 378}, 

    {"name": "Departures", "x": 130, "y": 435}, 

    {"name": "Terminal", "x": 108, "y": 441}, 

    {"name": "Arrivals", "x": 146, "y": 435}, 

    {"name": "Hangar", "x": 153, "y": 434}, 

    {"name": "Cargo", "x": 168, "y": 434}, 

    {"name": "Piste", "x": 83, "y": 485}, 

  

    # === ZONE INDUSTRIELLE / ENTREPÔTS SUD-EST === 

    {"name": "Entrepôt Industriel 1", "x": 220, "y": 465}, 

    {"name": "Entrepôt Industriel 2", "x": 343, "y": 442}, 

    {"name": "Entrepôt Industriel 3", "x": 238, "y": 465}, 

    {"name": "Entrepôt Industriel 4", "x": 20, "y": 466}, 

    {"name": "Entrepôt Industriel 5", "x": 9, "y": 442}, 

    {"name": "Entrepôt Industriel 6", "x": 45, "y": 442}, 

    {"name": "Zone de chargement 1", "x": 45, "y": 414}, 

    {"name": "Zone de chargement 2", "x": 9, "y": 378}, 

    {"name": "Zone de chargement 3", "x": 7, "y": 415}, 

  

    # === ZONE CARREFOURS / ILOTS URBAINS (centre bas) === 

    {"name": "Immeuble urbain Sud 1", "x": 17, "y": 274}, 

    {"name": "Immeuble urbain Sud 2", "x": 45, "y": 273}, 

    {"name": "Immeuble urbain Sud 3", "x": 89, "y": 274}, 

    {"name": "Immeuble urbain Sud 4", "x": 118, "y": 273}, 

    {"name": "Immeuble urbain Sud 5", "x": 115, "y": 251}, 

    {"name": "Immeuble urbain Sud 6", "x": 10, "y": 251}, 

    {"name": "Immeuble urbain Sud 7", "x": 55, "y": 251}, 

    {"name": "Immeuble urbain Sud 8", "x": 48, "y": 228}, 

  

    # === BUS / POINTS DE PASSAGE === 

    {"name": "BUS station", "x": 90, "y": 373}, 

    {"name": "Centre tickets", "x": 106, "y": 380}, 

    {"name": "BUS delivery hub", "x": 139, "y": 373}, 

    {"name": "Machine tickets de BUS", "x": 151, "y": 351}, 

  

    # === DIVERS / POINTS UNIQUES VISIBLES === 

    {"name": "Place piétonne avec fontaine", "x": 103, "y": 106}, 

    {"name": "Delivery podium", "x": 172, "y": 88}, 

  

  

    # === COMPLÉMENTS === 

    {"name": "Immeuble SUD ouest 1", "x": 32, "y": 307}, 

    {"name": "Immeuble Sud ouest 2", "x": 152, "y": 308}, 

    {"name": "Immeuble Sud ouest 3", "x": 38, "y": 344}, 

    {"name": "DR – Sortie Livraison A", "x": 43, "y": 378}, 

    {"name": "DR – Sortie Livraison B", "x": 44, "y": 465}, 

    {"name": "DR – Sortie Livraison C", "x": 322, "y": 379}, 

    {"name": "Poste de garde logistique", "x": 318, "y": 413}, 

    {"name": "Zone de dépôt temporaire", "x": 302, "y": 413}, 

    {"name": "Centre de contrôle DR", "x": 274, "y": 442}, 

    {"name": "DR SIEGE Principal", "x": 398, "y": 413}, 

] 

# Mission points were authored on the 512x512 tile grid.
# Convert once to world coordinates (pixels) to align with the in-game map.
MISSION_COORD_SCALE = 16.0


def _scale_locations_to_world(locations: List[Dict[str, Any]]) -> None:
    for loc in locations:
        try:
            x = float(loc.get("x", 0.0) or 0.0)
            y = float(loc.get("y", 0.0) or 0.0)
        except Exception:
            continue
        # Guard against double-scaling if values are already in world pixels.
        if x <= 600.0 and y <= 600.0:
            loc["x"] = x * MISSION_COORD_SCALE
            loc["y"] = y * MISSION_COORD_SCALE


_scale_locations_to_world(MISSION_LOCATIONS)
 


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

MISSION_TYPES = ("standard", "express", "chain")
RISKY_TYPE_BASE_CHANCE = {
    "standard": 0.28,
    "express": 0.52,
    "chain": 0.62,
}

HEAVY_MODELS = ("PICKUP", "VAN", "BOX TRUCK", "MEDIUM TRUCK")
EXPRESS_MODELS = ("COUPE", "MUSCLECAR", "SPORT", "SUPERCAR", "LUXURY")

CARGO_POOL = {
    "standard": [
        {"type": "colis", "icon": "PKG", "weight": (20, 85)},
        {"type": "alimentaire", "icon": "FOOD", "weight": (25, 100)},
        {"type": "documents", "icon": "DOC", "weight": (5, 30)},
    ],
    "express": [
        {"type": "medical", "icon": "MED", "weight": (8, 45)},
        {"type": "vip", "icon": "VIP", "weight": (5, 25)},
        {"type": "urgent", "icon": "NOW", "weight": (10, 40)},
    ],
    "chain": [
        {"type": "materiel", "icon": "BOX", "weight": (60, 170)},
        {"type": "lourd", "icon": "HVY", "weight": (110, 260)},
        {"type": "industriel", "icon": "IND", "weight": (120, 300)},
    ],
}

TIER_THRESHOLDS = [
    (0, "rookie"),
    (6, "trusted"),
    (16, "pro"),
    (32, "elite"),
]

TIER_UNLOCKS = {
    "rookie": ["standard"],
    "trusted": ["standard", "express"],
    "pro": ["standard", "express", "chain"],
    "elite": ["standard", "express", "chain"],
}


class Mission:
    """Représente une mission de livraison unique."""

    def __init__(
        self,
        mission_id: int,
        mission_type: str,
        pickup: Dict[str, Any],
        delivery: Dict[str, Any],
        reward: int,
        time_limit: float,
        requirements: Optional[Dict[str, Any]] = None,
        cargo_type: str = "colis",
        cargo_icon: str = "PKG",
        cargo_weight: float = 0.0,
        stops: Optional[List[Dict[str, Any]]] = None,
        current_stop_index: int = 0,
        risk_level: str = "chill",
        party_mission: bool = False,
    ):
        self.id = mission_id
        self.type = mission_type  # 'standard', 'express', 'chain'
        self.pickup = pickup      # {'name': str, 'x': float, 'y': float}
        self.delivery = delivery  # {'name': str, 'x': float, 'y': float}
        self.reward = reward
        self.time_limit = time_limit
        self.time_remaining = time_limit
        self.status = "available"  # available, accepted, picked_up, completed, failed
        self.picked_up = False
        self.requirements = requirements or {}
        self.cargo_type = cargo_type
        self.cargo_icon = cargo_icon
        self.cargo_weight = float(cargo_weight)
        self.stops = [dict(stop) for stop in (stops or self._default_stops())]
        if not self.stops:
            self.stops = self._default_stops()
        self.current_stop_index = max(0, min(int(current_stop_index or 0), len(self.stops) - 1))
        self.risk_level = "risky" if str(risk_level or "").strip().lower() == "risky" else "chill"
        self.party_mission = bool(party_mission)

    def _default_stops(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": self.pickup.get("name", "Ramassage"),
                "x": float(self.pickup.get("x", 0.0)),
                "y": float(self.pickup.get("y", 0.0)),
                "kind": "pickup",
            },
            {
                "name": self.delivery.get("name", "Livraison"),
                "x": float(self.delivery.get("x", 0.0)),
                "y": float(self.delivery.get("y", 0.0)),
                "kind": "dropoff",
            },
        ]

    def to_dict(self) -> Dict[str, Any]:
        """Sérialise pour le réseau."""
        return {
            "id": self.id,
            "type": self.type,
            "pickup": self.pickup,
            "delivery": self.delivery,
            "reward": self.reward,
            "time_limit": self.time_limit,
            "time_remaining": self.time_remaining,
            "status": self.status,
            "picked_up": self.picked_up,
            "requirements": self.requirements,
            "cargo_type": self.cargo_type,
            "cargo_icon": self.cargo_icon,
            "cargo_weight": self.cargo_weight,
            "stops": [dict(stop) for stop in self.stops],
            "current_stop_index": self.current_stop_index,
            "risk_level": self.risk_level,
            "party_mission": self.party_mission,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Mission":
        """Désérialise depuis les données réseau."""
        m = Mission(
            data["id"],
            data["type"],
            data["pickup"],
            data["delivery"],
            data["reward"],
            data["time_limit"],
            requirements=data.get("requirements", {}),
            cargo_type=data.get("cargo_type", "colis"),
            cargo_icon=data.get("cargo_icon", "PKG"),
            cargo_weight=float(data.get("cargo_weight", 0.0)),
            stops=data.get("stops"),
            current_stop_index=int(data.get("current_stop_index", 0) or 0),
            risk_level=str(data.get("risk_level", "chill") or "chill"),
            party_mission=bool(data.get("party_mission", False)),
        )
        m.time_remaining = data.get("time_remaining", data["time_limit"])
        m.status = data.get("status", "available")
        m.picked_up = data.get("picked_up", False)
        return m

    def description(self) -> str:
        """Description courte."""
        labels = {"standard": "Standard", "express": "Express", "chain": "Chaîne"}
        risk = "RISK" if self.risk_level == "risky" else "CHILL"
        return (
            f"[{labels.get(self.type, self.type)}|{risk}] "
            f"{self.pickup['name']} -> {self.delivery['name']} | "
            f"{self.reward}$ | {int(self.time_remaining)}s"
        )


class MissionSystem:
    """
    Système de gestion des missions de livraison.
    Génère, suit et valide les missions.
    """

    def __init__(
        self,
        money: int = 0,
        owned_cars: Optional[List[Dict[str, str]]] = None,
        completed_count: int = 0,
        failed_count: int = 0,
        current_car: Optional[Tuple[str, str]] = None,
        reputation: int = 0,
        unlock_state: Optional[Dict[str, Any]] = None,
        mission_stats: Optional[Dict[str, Any]] = None,
        language: str = "fr",
    ):
        self.available_missions: List[Mission] = []
        self.active_mission: Optional[Mission] = None
        self.money = money
        self.completed_count = completed_count
        self.failed_count = failed_count
        self.owned_cars = owned_cars if owned_cars is not None else [{"model": "MICRO", "color": "White"}]
        self._mission_id_counter = 0
        self._regen_timer = 0.0
        self._last_notification = ""
        self._notification_timer = 0.0
        self._last_accepted_mission: Optional[Mission] = None
        self.last_result: Optional[Dict[str, Any]] = None
        self.reputation = int(reputation)
        self.unlock_state: Dict[str, Any] = dict(unlock_state or {})
        self.mission_stats: Dict[str, Any] = {
            "current_streak": 0,
            "best_streak": 0,
            "bonus_earned": 0,
            "penalty_taken": 0,
        }
        if isinstance(mission_stats, dict):
            for key in self.mission_stats:
                self.mission_stats[key] = int(mission_stats.get(key, self.mission_stats[key]) or 0)
        self._mission_events: List[Dict[str, Any]] = []
        self.language = normalize_language(language)

        default_car = current_car if current_car is not None else self._owned_default_car()
        self.current_car = self._normalize_equipped_car(default_car)
        self._refresh_unlock_state()

        # Générer les premières missions adaptées au véhicule équipé.
        self.generate_missions_for_vehicle(self.current_car, MAX_AVAILABLE_MISSIONS)

    def _next_id(self) -> int:
        self._mission_id_counter += 1
        return self._mission_id_counter

    def _owned_default_car(self) -> Tuple[str, str]:
        if self.owned_cars:
            car = self.owned_cars[0]
            model = car.get("model", "MICRO") if isinstance(car, dict) else "MICRO"
            color = car.get("color", "White") if isinstance(car, dict) else "White"
            return sanitize_car((model, color))
        return "MICRO", "White"

    @staticmethod
    def _normalize_equipped_car(equipped_car: Optional[Any]) -> Tuple[str, str]:
        if isinstance(equipped_car, (list, tuple)) and len(equipped_car) >= 2:
            return sanitize_car((str(equipped_car[0]), str(equipped_car[1])))
        if isinstance(equipped_car, dict):
            return sanitize_car((str(equipped_car.get("model", "MICRO")), str(equipped_car.get("color", "White"))))
        if isinstance(equipped_car, str):
            return sanitize_car((equipped_car, "White"))
        return sanitize_car(("MICRO", "White"))

    def set_language(self, language: str) -> None:
        self.language = normalize_language(language)

    def _t(self, key: str, **kwargs: Any) -> str:
        return tr(self.language, key, **kwargs)

    def _vehicle_profile(self, equipped_car: Optional[Any] = None) -> Dict[str, Any]:
        car_tuple = self._normalize_equipped_car(equipped_car if equipped_car is not None else self.current_car)
        return build_vehicle_profile(car_tuple)

    def get_vehicle_profile(self, equipped_car: Optional[Any] = None) -> Dict[str, Any]:
        """Expose le profil gameplay du véhicule courant/forcé."""
        return self._vehicle_profile(equipped_car)

    @staticmethod
    def _is_vehicle_eligible_requirements(requirements: Dict[str, Any], vehicle_profile: Dict[str, Any]) -> bool:
        model = str(vehicle_profile.get("model", "")).upper()
        vclass = str(vehicle_profile.get("vehicle_class", "")).lower()
        max_speed = float(vehicle_profile.get("max_speed", 0.0))
        capacity = float(vehicle_profile.get("cargo_capacity", 0.0))

        required_models = [str(m).upper() for m in requirements.get("required_models", []) if m]
        if required_models and model not in required_models:
            return False

        required_class = str(requirements.get("required_class", "")).strip().lower()
        if required_class and vclass != required_class:
            return False

        min_speed = float(requirements.get("min_speed", 0.0) or 0.0)
        if min_speed > 0.0 and max_speed + 1e-6 < min_speed:
            return False

        min_capacity = float(requirements.get("min_capacity", 0.0) or 0.0)
        if min_capacity > 0.0 and capacity + 1e-6 < min_capacity:
            return False

        return True

    def _fit_requirements_to_vehicle(self, requirements: Dict[str, Any], vehicle_profile: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ajuste les contraintes pour garantir qu'au moins le véhicule ciblé reste valide.
        Cela permet la double validation sans générer des missions impossibles à accepter.
        """
        out = dict(requirements)
        model = str(vehicle_profile.get("model", "MICRO"))
        vclass = str(vehicle_profile.get("vehicle_class", "compact"))
        max_speed = float(vehicle_profile.get("max_speed", 800.0))
        capacity = float(vehicle_profile.get("cargo_capacity", 70.0))

        req_models = out.get("required_models", [])
        if req_models:
            req_models = [str(m) for m in req_models if m]
            if model not in req_models:
                req_models.append(model)
            out["required_models"] = sorted(set(req_models))

        req_class = out.get("required_class")
        if req_class and str(req_class).lower() != vclass.lower():
            out["required_class"] = vclass

        min_speed = float(out.get("min_speed", 0.0) or 0.0)
        if min_speed > max_speed:
            out["min_speed"] = int(max_speed)

        min_capacity = float(out.get("min_capacity", 0.0) or 0.0)
        if min_capacity > capacity:
            out["min_capacity"] = int(capacity)

        # Nettoyage des valeurs neutres.
        if float(out.get("min_speed", 0.0) or 0.0) <= 0.0:
            out.pop("min_speed", None)
        if float(out.get("min_capacity", 0.0) or 0.0) <= 0.0:
            out.pop("min_capacity", None)

        return out

    def _build_mission_requirements(
        self,
        mission_type: str,
        dist_factor: float,
        vehicle_profile: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Construit les contraintes déclaratives d'une mission."""
        requirements: Dict[str, Any] = {}

        if mission_type == "standard":
            if random.random() < 0.45:
                requirements["min_capacity"] = random.choice([60, 80, 100, 120])

        elif mission_type == "express":
            requirements["min_speed"] = random.choice([1000, 1120, 1250, 1350])
            if random.random() < 0.35:
                requirements["required_class"] = "sport"
            if random.random() < 0.2:
                requirements["required_models"] = random.sample(list(EXPRESS_MODELS), k=3)

        else:  # chain
            requirements["min_capacity"] = random.choice([130, 160, 190, 220])
            if random.random() < 0.6:
                requirements["required_class"] = "utility"
            if random.random() < 0.35:
                requirements["required_models"] = random.sample(list(HEAVY_MODELS), k=3)

        if "min_speed" in requirements:
            requirements["min_speed"] = int(requirements["min_speed"] + max(0.0, dist_factor - 1.0) * 180)
        if "min_capacity" in requirements:
            requirements["min_capacity"] = int(requirements["min_capacity"] + max(0.0, dist_factor - 1.0) * 45)

        model = str(vehicle_profile.get("model", ""))
        if model in HEAVY_MODELS and mission_type in ("standard", "chain") and random.random() < 0.5:
            requirements["required_models"] = [model]
        if model in EXPRESS_MODELS and mission_type == "express" and random.random() < 0.5:
            requirements["required_models"] = [model]

        return self._fit_requirements_to_vehicle(requirements, vehicle_profile)

    def _assign_cargo(self, mission_type: str, requirements: Dict[str, Any]) -> Dict[str, Any]:
        """Affecte une marchandise cohérente au type de mission."""
        pool = CARGO_POOL.get(mission_type, CARGO_POOL["standard"])
        cargo = random.choice(pool)

        w_min, w_max = cargo["weight"]
        weight = random.uniform(float(w_min), float(w_max))

        max_required_capacity = float(requirements.get("min_capacity", 0.0) or 0.0)
        if max_required_capacity > 0.0:
            weight = min(weight, max_required_capacity)

        return {
            "cargo_type": cargo["type"],
            "cargo_icon": cargo["icon"],
            "cargo_weight": round(max(5.0, weight), 1),
        }

    def _compute_mission_weights(self, equipped_car: Optional[Any] = None) -> Dict[str, float]:
        """Pondérations dynamiques selon le véhicule équipé."""
        profile = self._vehicle_profile(equipped_car)
        vclass = str(profile.get("vehicle_class", "compact")).lower()
        model = str(profile.get("model", "MICRO"))
        max_speed = float(profile.get("max_speed", 800.0))
        capacity = float(profile.get("cargo_capacity", 70.0))

        weights = {
            "standard": 60.0,
            "express": 25.0,
            "chain": 15.0,
        }

        class_bonuses = {
            "utility": {"standard": 8.0, "express": -8.0, "chain": 20.0},
            "truck": {"standard": 6.0, "express": -12.0, "chain": 24.0},
            "sport": {"standard": -5.0, "express": 20.0, "chain": -8.0},
            "super": {"standard": -6.0, "express": 24.0, "chain": -10.0},
            "family": {"standard": 5.0, "express": 0.0, "chain": 5.0},
        }
        if vclass in class_bonuses:
            for mtype, bonus in class_bonuses[vclass].items():
                weights[mtype] += bonus

        if model in ("BOX TRUCK", "MEDIUM TRUCK"):
            weights["chain"] += 10.0
        if model in ("SPORT", "SUPERCAR"):
            weights["express"] += 10.0

        if max_speed < 980.0:
            weights["express"] -= 8.0
        if capacity < 90.0:
            weights["chain"] -= 8.0

        for mtype in list(weights.keys()):
            weights[mtype] = max(5.0, weights[mtype])

        return weights

    def _vehicle_reward_factor(self, equipped_car: Optional[Any] = None) -> float:
        """Large reward spread between entry cars and high-end cars."""
        profile = self._vehicle_profile(equipped_car)
        max_speed = float(profile.get("max_speed", 800.0) or 800.0)
        capacity = float(profile.get("cargo_capacity", 70.0) or 70.0)
        speed_score = max(0.0, min(1.0, max_speed / 1500.0))
        cargo_score = max(0.0, min(1.0, capacity / 320.0))
        tier_score = 0.7 * speed_score + 0.3 * cargo_score
        return 0.72 + tier_score * 1.08

    def _get_player_tier(self) -> str:
        tier = "rookie"
        for threshold, name in TIER_THRESHOLDS:
            if self.reputation >= threshold:
                tier = name
        return tier

    def _refresh_unlock_state(self) -> None:
        tier = self._get_player_tier()
        unlocked_types = TIER_UNLOCKS.get(tier, ["standard"])
        self.unlock_state = {
            "tier": tier,
            "unlocked_types": list(unlocked_types),
            "reputation": int(self.reputation),
        }

    def get_unlock_state(self) -> Dict[str, Any]:
        self._refresh_unlock_state()
        return dict(self.unlock_state)

    def add_reputation(self, delta: int) -> None:
        self.reputation = max(0, int(self.reputation + int(delta)))
        self._refresh_unlock_state()

    def _eligible_mission_types(self) -> List[str]:
        self._refresh_unlock_state()
        unlocked = [m for m in self.unlock_state.get("unlocked_types", []) if m in MISSION_TYPES]
        return unlocked or ["standard"]

    def _push_event(self, event_type: str, payload: Optional[Dict[str, Any]] = None) -> None:
        self._mission_events.append({
            "type": str(event_type),
            "payload": dict(payload or {}),
        })

    def get_and_clear_mission_events(self) -> List[Dict[str, Any]]:
        events = list(self._mission_events)
        self._mission_events.clear()
        return events

    def _build_stops(self, mission_type: str, pickup: Dict[str, Any], delivery: Dict[str, Any]) -> List[Dict[str, Any]]:
        stops: List[Dict[str, Any]] = [
            {"name": pickup["name"], "x": pickup["x"], "y": pickup["y"], "kind": "pickup"},
        ]

        if mission_type == "chain":
            extra_count = random.choice([1, 2])
            excluded = {pickup["name"], delivery["name"]}
            candidates = [loc for loc in MISSION_LOCATIONS if loc["name"] not in excluded]
            for stop in random.sample(candidates, k=min(extra_count, len(candidates))):
                stops.append({"name": stop["name"], "x": stop["x"], "y": stop["y"], "kind": "stop"})

        stops.append({"name": delivery["name"], "x": delivery["x"], "y": delivery["y"], "kind": "dropoff"})
        return stops

    @staticmethod
    def _normalize_risk_level(value: Any) -> str:
        return "risky" if str(value or "").strip().lower() == "risky" else "chill"

    def _pick_risk_level(self, mission_type: str) -> str:
        base = float(RISKY_TYPE_BASE_CHANCE.get(str(mission_type or "standard"), 0.3))
        tier = str(self.get_unlock_state().get("tier", "rookie"))
        if tier in ("pro", "elite"):
            base += 0.05
        return "risky" if random.random() < min(0.85, max(0.1, base)) else "chill"

    def _is_vehicle_eligible(self, mission_or_requirements: Any, equipped_car: Optional[Any] = None) -> bool:
        requirements: Dict[str, Any]
        if isinstance(mission_or_requirements, Mission):
            requirements = dict(mission_or_requirements.requirements or {})
        elif isinstance(mission_or_requirements, dict):
            requirements = dict(mission_or_requirements)
        else:
            return True

        profile = self._vehicle_profile(equipped_car)
        return self._is_vehicle_eligible_requirements(requirements, profile)

    def mission_is_selectable(self, mission: Mission, equipped_car: Optional[Any] = None) -> bool:
        """Alias UI-friendly pour vérifier l'éligibilité d'une mission."""
        return self._is_vehicle_eligible(mission, equipped_car)

    def mission_requirement_label(self, mission: Mission) -> str:
        """Formate les contraintes d'une mission en texte court."""
        req = mission.requirements or {}
        if not req:
            return self._t("mission.none_requirement")

        chunks: List[str] = []

        models = [str(m) for m in req.get("required_models", []) if m]
        if models:
            short = ", ".join(models[:2])
            if len(models) > 2:
                short += "..."
            chunks.append(self._t("mission.label_model", value=short))

        required_class = str(req.get("required_class", "")).strip().lower()
        if required_class:
            class_label = self._t(f"mission.class.{required_class}")
            if class_label == f"mission.class.{required_class}":
                class_label = required_class
            chunks.append(self._t("mission.label_class", value=class_label))

        min_speed = float(req.get("min_speed", 0.0) or 0.0)
        if min_speed > 0.0:
            chunks.append(self._t("mission.label_speed", value=int(min_speed)))

        min_capacity = float(req.get("min_capacity", 0.0) or 0.0)
        if min_capacity > 0.0:
            chunks.append(self._t("mission.label_capacity", value=int(min_capacity)))

        return " | ".join(chunks) if chunks else self._t("mission.none_requirement")

    def generate_missions_for_vehicle(self, equipped_car: Optional[Any], count: int = 1) -> int:
        """Génère des missions compatibles avec le véhicule équipé."""
        self.current_car = self._normalize_equipped_car(equipped_car if equipped_car is not None else self.current_car)
        profile = self._vehicle_profile(self.current_car)
        reward_factor = self._vehicle_reward_factor(self.current_car)

        target_count = max(0, int(count))
        attempts = 0
        created = 0
        max_attempts = max(20, target_count * 24)

        while created < target_count and attempts < max_attempts and len(self.available_missions) < MAX_AVAILABLE_MISSIONS:
            attempts += 1

            weights = self._compute_mission_weights(profile)
            eligible_types = self._eligible_mission_types()
            mission_type = random.choices(
                eligible_types,
                weights=[weights.get(mtype, 1.0) for mtype in eligible_types],
                k=1,
            )[0]

            pickup, delivery = [dict(loc) for loc in random.sample(MISSION_LOCATIONS, 2)]
            dist = math.hypot(delivery["x"] - pickup["x"], delivery["y"] - pickup["y"])
            dist_factor = max(0.5, dist / 4000.0)

            if mission_type == "standard":
                reward = int(random.uniform(*REWARD_STANDARD) * dist_factor * reward_factor)
                time_limit = random.uniform(*TIME_STANDARD) * max(0.7, dist_factor)
            elif mission_type == "express":
                reward = int(random.uniform(*REWARD_EXPRESS) * dist_factor * reward_factor)
                time_limit = random.uniform(*TIME_EXPRESS) * max(0.7, dist_factor)
            else:
                reward = int(random.uniform(*REWARD_CHAIN) * dist_factor * reward_factor)
                time_limit = random.uniform(*TIME_CHAIN) * max(0.7, dist_factor)

            risk_level = self._pick_risk_level(mission_type)
            if risk_level == "risky":
                reward = int(reward * 1.24)
                time_limit = max(35.0, time_limit * 0.86)

            requirements = self._build_mission_requirements(mission_type, dist_factor, profile)
            cargo = self._assign_cargo(mission_type, requirements)

            cargo_weight = float(cargo.get("cargo_weight", 0.0))
            if cargo_weight > float(requirements.get("min_capacity", 0.0) or 0.0):
                requirements["min_capacity"] = int(math.ceil(cargo_weight))
                requirements = self._fit_requirements_to_vehicle(requirements, profile)

            stops = self._build_stops(mission_type, pickup, delivery)

            mission = Mission(
                self._next_id(),
                mission_type,
                pickup,
                delivery,
                reward,
                time_limit,
                requirements=requirements,
                cargo_type=str(cargo.get("cargo_type", "colis")),
                cargo_icon=str(cargo.get("cargo_icon", "PKG")),
                cargo_weight=float(cargo.get("cargo_weight", 0.0)),
                stops=stops,
                risk_level=risk_level,
            )

            # Validation n°1 au moment de la génération.
            if not self._is_vehicle_eligible(mission, self.current_car):
                continue

            self.available_missions.append(mission)
            created += 1

        return created

    def generate_missions(self, count: int = 1) -> int:
        """Compatibilité API existante: génère selon la voiture courante."""
        return self.generate_missions_for_vehicle(self.current_car, count)

    def refresh_available_missions_for_vehicle(self, equipped_car: Optional[Any]) -> None:
        """Rafraîchit la liste de missions après changement de véhicule."""
        self.current_car = self._normalize_equipped_car(equipped_car if equipped_car is not None else self.current_car)

        self.available_missions = [
            m for m in self.available_missions
            if self._is_vehicle_eligible(m, self.current_car)
        ]

        missing = MAX_AVAILABLE_MISSIONS - len(self.available_missions)
        if missing > 0:
            self.generate_missions_for_vehicle(self.current_car, missing)

    def load_server_missions(self, mission_payloads: Sequence[Dict[str, Any]], equipped_car: Optional[Any] = None) -> int:
        """Charge une liste de missions serveur, filtrée par éligibilité véhicule."""
        if equipped_car is not None:
            self.current_car = self._normalize_equipped_car(equipped_car)

        loaded: List[Mission] = []
        max_id = self._mission_id_counter
        for payload in mission_payloads or []:
            if not isinstance(payload, dict):
                continue
            if payload.get("status", "available") != "available":
                continue
            try:
                mission = Mission.from_dict(payload)
            except Exception:
                continue
            max_id = max(max_id, int(mission.id))
            if self._is_vehicle_eligible(mission, self.current_car):
                loaded.append(mission)

        loaded.sort(key=lambda m: int(m.id))
        self.available_missions = loaded[:MAX_AVAILABLE_MISSIONS]
        self._mission_id_counter = max_id
        return len(self.available_missions)

    def accept_mission(self, mission_id: int, equipped_car: Optional[Any] = None) -> Tuple[bool, str]:
        """Accepte une mission. Retourne (succès, message)."""
        if self.active_mission is not None:
            return False, self._t("mission.in_progress")

        if equipped_car is not None:
            self.current_car = self._normalize_equipped_car(equipped_car)

        for i, mission in enumerate(self.available_missions):
            if mission.id != mission_id:
                continue

            # Validation n°2 au moment de l'acceptation.
            if not self._is_vehicle_eligible(mission, self.current_car):
                req_label = self.mission_requirement_label(mission)
                self._set_notification(self._t("mission.refused", label=req_label))
                return False, self._t("mission.vehicle_incompatible", label=req_label)

            self.active_mission = self.available_missions.pop(i)
            self.active_mission.status = "accepted"
            self.active_mission.current_stop_index = 0
            self.active_mission.picked_up = False
            self._last_accepted_mission = self.active_mission
            objective_label = self.get_objective_label() or self._t("mission.objective.pickup", step=1, total=max(1, len(self.active_mission.stops)), name=self.active_mission.pickup['name'])
            self._set_notification(self._t("mission.accepted", objective=objective_label))
            self._push_event(
                "mission_accept",
                {
                    "mission_id": int(self.active_mission.id),
                    "mission_type": str(self.active_mission.type),
                },
            )
            return True, "OK"

        return False, self._t("mission.not_found")

    def handle_server_mission_denied(self, mission_id: int, reason: str = "server_validation") -> bool:
        """Annule localement une mission si le serveur la refuse en multijoueur."""
        if self.active_mission is None or int(self.active_mission.id) != int(mission_id):
            return False

        if self.active_mission.status == "accepted" and not self.active_mission.picked_up:
            self.active_mission.status = "available"
            self.available_missions.insert(0, self.active_mission)

        self.active_mission = None
        self._set_notification(self._t("mission.server_refused", reason=reason))
        self._push_event(
            "mission_denied",
            {
                "mission_id": int(mission_id),
                "reason": str(reason),
            },
        )
        return True

    def activate_network_mission(self, mission_payload: Dict[str, Any], equipped_car: Optional[Any] = None) -> bool:
        """Active/synchronise une mission imposée par le serveur (party/coop)."""
        if not isinstance(mission_payload, dict):
            return False

        status = str(mission_payload.get("status", "active") or "active").lower()
        if status not in ("active", "accepted", "picked_up", "in_progress"):
            return False

        if equipped_car is not None:
            self.current_car = self._normalize_equipped_car(equipped_car)

        try:
            synced = Mission.from_dict(mission_payload)
        except Exception:
            return False

        try:
            synced_id = int(synced.id)
        except Exception:
            return False

        if self.active_mission is not None:
            try:
                active_id = int(self.active_mission.id)
            except Exception:
                active_id = -1
            if active_id != synced_id:
                return False

        if synced.current_stop_index >= len(synced.stops):
            synced.current_stop_index = max(0, len(synced.stops) - 1)

        synced.status = "picked_up" if synced.picked_up or synced.current_stop_index > 0 else "accepted"

        self.available_missions = [
            m for m in self.available_missions
            if int(getattr(m, "id", -1)) != synced_id
        ]
        self.active_mission = synced
        self._last_accepted_mission = synced
        return True

    def abandon_mission(self) -> bool:
        """Abandonne la mission en cours."""
        if self.active_mission is None:
            return False
        mission = self.active_mission
        self.active_mission = None
        self.last_result = self._build_mission_result(
            mission,
            success=False,
            reason="abandon",
            player_stats=None,
        )
        self._set_notification(self._t("mission.abandoned"))
        self._push_event(
            "mission_fail",
            {
                "mission_id": int(mission.id),
                "reason": "abandon",
            },
        )
        return True

    def fail_active_mission(self, reason: str = "failed", player_stats: Optional[Dict[str, Any]] = None) -> bool:
        """Force l'échec de la mission active avec une raison explicite."""
        if self.active_mission is None:
            return False

        mission = self.active_mission
        mission.status = "failed"
        fail_reason = str(reason or "failed")
        self.last_result = self._build_mission_result(
            mission,
            success=False,
            reason=fail_reason,
            player_stats=player_stats,
        )

        if fail_reason == "timeout":
            self._set_notification(self._t("mission.timeout"))
        elif fail_reason == "abandon":
            self._set_notification(self._t("mission.abandoned"))
        elif fail_reason == "robbed":
            self._set_notification(self._t("mission.robbed"))
        else:
            self._set_notification(self._t("mission.failed_generic"))

        self._push_event(
            "mission_fail",
            {
                "mission_id": int(mission.id),
                "reason": fail_reason,
            },
        )
        self.active_mission = None
        return True

    def update(self, player_x: float, player_y: float, dt: float, player_stats: Optional[Dict[str, Any]] = None) -> None:
        """Met à jour le système : timer, progression d'étapes, régénération."""
        # Régénération des missions disponibles.
        self._regen_timer += dt
        if self._regen_timer >= MISSION_REGEN_TIME:
            self._regen_timer = 0.0
            if len(self.available_missions) < MAX_AVAILABLE_MISSIONS:
                self.generate_missions_for_vehicle(self.current_car, 1)

        # Timer notification
        if self._notification_timer > 0.0:
            self._notification_timer -= dt

        if self.active_mission is None:
            return

        mission = self.active_mission

        # Countdown global de mission
        if mission.status in ("accepted", "picked_up"):
            mission.time_remaining -= dt
            if mission.time_remaining <= 0.0:
                self.fail_active_mission(reason="timeout", player_stats=player_stats)
                return

        objective = self.get_current_objective()
        if not objective:
            return

        if bool(getattr(mission, "party_mission", False)) and mission.picked_up:
            matched_index: Optional[int] = None
            matched_dist: Optional[float] = None
            for idx in range(int(mission.current_stop_index), len(mission.stops)):
                stop = mission.stops[idx]
                stop_kind = str(stop.get("kind", "stop"))
                stop_radius = DELIVERY_RADIUS if stop_kind == "dropoff" else PICKUP_RADIUS
                stop_dist = math.hypot(player_x - float(stop.get("x", 0.0)), player_y - float(stop.get("y", 0.0)))
                if stop_dist > stop_radius:
                    continue
                if matched_dist is None or stop_dist < matched_dist:
                    matched_index = idx
                    matched_dist = stop_dist

            if matched_index is not None and matched_index != int(mission.current_stop_index):
                curr = int(mission.current_stop_index)
                mission.stops[curr], mission.stops[matched_index] = mission.stops[matched_index], mission.stops[curr]
                objective = self.get_current_objective() or objective

        radius = DELIVERY_RADIUS if objective.get("kind") == "dropoff" else PICKUP_RADIUS
        dist = math.hypot(player_x - float(objective.get("x", 0.0)), player_y - float(objective.get("y", 0.0)))
        if dist > radius:
            return

        reached = dict(objective)
        completed = self._advance_mission_step(mission)

        if completed:
            self.last_result = self._build_mission_result(
                mission,
                success=True,
                reason="completed",
                player_stats=player_stats,
            )
            gain = int(self.last_result.get("money_delta", 0) or 0)
            rep_delta = int(self.last_result.get("reputation_delta", 0) or 0)
            rep_hint = f" REP {rep_delta:+d}" if rep_delta else ""
            self._set_notification(self._t("mission.success", money=gain, rep=rep_hint).strip())
            self._push_event(
                "mission_complete",
                {
                    "mission_id": int(mission.id),
                    "money_delta": gain,
                    "reputation_delta": rep_delta,
                },
            )
            self.active_mission = None
            return

        reached_kind = str(reached.get("kind", "stop"))
        if reached_kind == "pickup":
            self._set_notification(self._t("mission.pickup_done", objective=self.get_objective_label()))
            self._push_event(
                "mission_pickup",
                {
                    "mission_id": int(mission.id),
                    "next_index": int(mission.current_stop_index),
                },
            )
        else:
            self._set_notification(self._t("mission.step_done", objective=self.get_objective_label()))
            self._push_event(
                "mission_step",
                {
                    "mission_id": int(mission.id),
                    "stop_name": str(reached.get("name", "Étape")),
                    "next_index": int(mission.current_stop_index),
                },
            )

    def _advance_mission_step(self, mission: Mission) -> bool:
        """Passe à l'étape suivante. Retourne True si la mission est terminée."""
        if mission.current_stop_index >= len(mission.stops):
            mission.status = "completed"
            return True

        current = mission.stops[mission.current_stop_index]
        kind = str(current.get("kind", "stop"))
        if kind == "pickup":
            mission.picked_up = True
            mission.status = "picked_up"

        mission.current_stop_index += 1
        if mission.current_stop_index >= len(mission.stops):
            mission.status = "completed"
            return True

        mission.status = "picked_up" if mission.picked_up else "accepted"
        return False

    @staticmethod
    def _extract_player_stats(player_stats: Optional[Dict[str, Any]]) -> Dict[str, float]:
        raw = dict(player_stats or {}) if isinstance(player_stats, dict) else {}
        return {
            "collision_count": max(0.0, float(raw.get("collision_count", 0.0) or 0.0)),
            "drift_time": max(0.0, float(raw.get("drift_time", 0.0) or 0.0)),
            "avg_speed_kmh": max(0.0, float(raw.get("avg_speed_kmh", 0.0) or 0.0)),
            "mission_time": max(0.0, float(raw.get("mission_time", 0.0) or 0.0)),
        }

    def _compute_reward_outcome(
        self,
        mission: Mission,
        remaining_time: float,
        elapsed_time: float,
        player_stats: Optional[Dict[str, Any]],
    ) -> Tuple[int, float, List[Dict[str, Any]]]:
        base_reward = int(mission.reward)
        telemetry = self._extract_player_stats(player_stats)
        modifiers: List[Dict[str, Any]] = []
        multiplier = 1.0

        remaining_ratio = 0.0
        if mission.time_limit > 0:
            remaining_ratio = max(0.0, min(1.0, remaining_time / float(mission.time_limit)))

        if remaining_ratio >= 0.4:
            bonus = 0.12
            multiplier += bonus
            modifiers.append({"name": "rapidite", "delta": bonus})
        elif remaining_ratio >= 0.25:
            bonus = 0.06
            multiplier += bonus
            modifiers.append({"name": "tempo", "delta": bonus})
        elif remaining_ratio <= 0.1:
            malus = 0.08
            multiplier -= malus
            modifiers.append({"name": "retard", "delta": -malus})

        collisions = telemetry["collision_count"]
        if collisions > 0:
            malus = min(0.35, collisions * 0.05)
            multiplier -= malus
            modifiers.append({"name": "collisions", "delta": -malus})

        if telemetry["drift_time"] >= 3.0 and mission.type in ("express", "chain"):
            bonus = min(0.08, telemetry["drift_time"] / 100.0)
            multiplier += bonus
            modifiers.append({"name": "style", "delta": bonus})

        stop_bonus = max(0.0, (len(mission.stops) - 2) * 0.03)
        if stop_bonus > 0.0:
            multiplier += stop_bonus
            modifiers.append({"name": "multi_etapes", "delta": stop_bonus})

        multiplier = max(0.45, min(1.85, multiplier))
        money_delta = int(round(base_reward * multiplier))
        return money_delta, multiplier, modifiers

    def _compute_reputation_delta(
        self,
        mission: Mission,
        success: bool,
        reason: str,
        remaining_time: float,
        player_stats: Optional[Dict[str, Any]],
    ) -> int:
        telemetry = self._extract_player_stats(player_stats)
        if success:
            base = {
                "standard": 2,
                "express": 3,
                "chain": 4,
            }.get(mission.type, 2)

            if mission.time_limit > 0 and (remaining_time / mission.time_limit) >= 0.3:
                base += 1
            if telemetry["collision_count"] <= 0.0:
                base += 1
            return max(1, base)

        if reason == "abandon":
            return -2
        if reason == "timeout":
            return -3
        if reason == "robbed":
            return -4
        return -2

    def _build_mission_result(
        self,
        mission: Mission,
        success: bool,
        reason: str,
        player_stats: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        remaining_time = max(0.0, float(mission.time_remaining))
        elapsed_time = max(0.0, float(mission.time_limit) - remaining_time)

        money_delta = 0
        reward_multiplier = 0.0
        modifiers: List[Dict[str, Any]] = []

        if success:
            money_delta, reward_multiplier, modifiers = self._compute_reward_outcome(
                mission,
                remaining_time,
                elapsed_time,
                player_stats,
            )
            self.money += money_delta
            self.completed_count += 1
            self.mission_stats["current_streak"] += 1
            self.mission_stats["best_streak"] = max(
                self.mission_stats["best_streak"],
                self.mission_stats["current_streak"],
            )
            self.mission_stats["bonus_earned"] += max(0, int(money_delta - int(mission.reward)))
        else:
            self.failed_count += 1
            self.mission_stats["current_streak"] = 0
            self.mission_stats["penalty_taken"] += int(mission.reward)

        reputation_delta = self._compute_reputation_delta(
            mission,
            success,
            reason,
            remaining_time,
            player_stats,
        )
        self.add_reputation(reputation_delta)

        return {
            "success": bool(success),
            "reason": str(reason),
            "mission": mission.to_dict(),
            "remaining_time": remaining_time,
            "elapsed_time": elapsed_time,
            "money_delta": int(money_delta),
            "reward_multiplier": float(reward_multiplier),
            "modifiers": [dict(item) for item in modifiers],
            "reputation_delta": int(reputation_delta),
        }

    def _set_notification(self, text: str, duration: float = 4.0) -> None:
        self._last_notification = text
        self._notification_timer = duration

    def get_notification(self) -> str:
        return self._last_notification if self._notification_timer > 0 else ""

    def set_external_notification(self, text: str, duration: float = 3.0) -> None:
        """Expose une notification UI courte pour des règles réseau."""
        self._set_notification(str(text or ""), duration=max(0.5, float(duration or 0.0)))

    def consume_last_result(self) -> Optional[Dict[str, Any]]:
        """Retourne puis efface le dernier résultat de mission (one-shot)."""
        if self.last_result is None:
            return None
        result = dict(self.last_result)
        self.last_result = None
        return result

    def get_current_objective(self) -> Optional[Dict[str, Any]]:
        """Retourne l'objectif actif courant (étape multi-stop) ou None."""
        if self.active_mission is None:
            return None
        mission = self.active_mission
        if not mission.stops:
            return None
        idx = max(0, min(int(mission.current_stop_index), len(mission.stops) - 1))
        stop = dict(mission.stops[idx])
        stop.setdefault("kind", "stop")
        stop.setdefault("cargo_type", getattr(mission, "cargo_type", "colis"))
        stop.setdefault("cargo_icon", getattr(mission, "cargo_icon", "PKG"))
        return stop

    def get_objective_position(self) -> Optional[Tuple[float, float]]:
        """Retourne (x, y) de l'objectif actuel ou None."""
        objective = self.get_current_objective()
        if objective is None:
            return None
        return float(objective.get("x", 0.0)), float(objective.get("y", 0.0))

    def get_objective_label(self) -> str:
        """Retourne le label de l'objectif actuel."""
        objective = self.get_current_objective()
        if objective is None or self.active_mission is None:
            return ""

        kind = str(objective.get("kind", "stop"))
        name = str(objective.get("name", "Objectif"))
        mission = self.active_mission
        step_idx = int(mission.current_stop_index) + 1
        total_steps = max(1, len(mission.stops))

        if kind == "pickup":
            return self._t("mission.objective.pickup", step=step_idx, total=total_steps, name=name)
        if kind == "dropoff":
            return self._t("mission.objective.dropoff", step=step_idx, total=total_steps, name=name)
        return self._t("mission.objective.step", step=step_idx, total=total_steps, name=name)

    def to_dict(self) -> Dict[str, Any]:
        """Sérialise pour le réseau."""
        return {
            "available": [m.to_dict() for m in self.available_missions],
            "active": self.active_mission.to_dict() if self.active_mission else None,
            "money": self.money,
            "completed": self.completed_count,
            "failed": self.failed_count,
            "owned_cars": self.owned_cars,
            "current_car": list(self.current_car),
            "reputation": int(self.reputation),
            "unlock_state": self.get_unlock_state(),
            "mission_stats": dict(self.mission_stats),
        }

    def has_car(self, model: str, color: Optional[str] = None) -> bool:
        """Vérifie si le joueur possède un véhicule."""
        for car in self.owned_cars:
            if car["model"] == model:
                if color is None or car.get("color") == color:
                    return True
        return False

    def buy_car(self, model: str, color: str, price: int) -> Tuple[bool, str]:
        """Achète un véhicule si le joueur a assez d'argent. Retourne (succès, message)."""
        if not is_vehicle_color_allowed(model, color):
            return False, self._t("mission.vehicle_incompatible", label=f"{model} {color}")
        if self.has_car(model, color):
            return False, self._t("mission.buy_owned")
        if self.money < price:
            return False, self._t("mission.buy_not_enough")
        self.money -= price
        self.owned_cars.append({"model": model, "color": color})
        self._set_notification(self._t("mission.buy_success", model=model, color=color))
        return True, "OK"
